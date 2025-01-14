from typing import Optional, List, Dict, Set
from datetime import datetime, timezone
import uuid
import boto3
from boto3.dynamodb.conditions import Key, Attr
from ..models.message import Message
from ..models.reaction import Reaction
from .base_service import BaseService
from .user_service import UserService
from .channel_service import ChannelService
import time

class MessageService(BaseService):
    """Message service for managing chat messages in DynamoDB.
    
    Schema Usage:
    - Messages (Parent):
        PK=MSG#{message_id} SK=MSG#{message_id}
        GSI1PK=CHANNEL#{channel_id} GSI1SK=TS#{timestamp}  # For chronological channel messages
        GSI2PK=USER#{user_id} GSI2SK=TS#{timestamp}       # For user message history
        
    - Messages (Replies):
        PK=MSG#{thread_id} SK=REPLY#{message_id}          # Thread messages stored under parent
        GSI1PK=CHANNEL#{channel_id} GSI1SK=TS#{timestamp} # For chronological channel messages
        GSI2PK=USER#{user_id} GSI2SK=TS#{timestamp}      # For user message history
        
    - Word Index (for search):
        PK=WORD#{word} SK=MESSAGE#{message_id}            # Word to message mapping
        GSI3PK=CONTENT#{word} GSI3SK=TS#{timestamp}       # For chronological word search
        
    Access Patterns:
    - Get channel messages: Query GSI1 with CHANNEL#{id} prefix, ordered by timestamp
    - Get thread messages: Query PK=MSG#{thread_id} with SK prefix REPLY#
    - Get user messages: Query GSI2 with USER#{id} prefix, ordered by timestamp
    - Search messages by word: Query GSI3 with CONTENT#{word} prefix, ordered by timestamp
    """
    def __init__(self, table_name: str = None):
        super().__init__(table_name)
        self.user_service = UserService(table_name)
        self.channel_service = ChannelService(table_name)
        
    def create_message(self, channel_id: str, user_id: str, content: str, thread_id: str = None, attachments: List[str] = None, created_at: str = None) -> Message:
        """Create a new message.
        
        Args:
            channel_id: The ID of the channel to create the message in
            user_id: The ID of the user creating the message
            content: The message content
            thread_id: Optional ID of parent message if this is a reply
            attachments: Optional list of attachment URLs
            created_at: Optional ISO format timestamp for when message was created
            
        Returns:
            The created Message object
        """
        # Verify channel exists
        channel = self.channel_service.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")
            
        # Verify user exists
        user = self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
            
        # Verify thread exists if thread_id provided
        if thread_id:
            thread = self.get_message(thread_id)
            if not thread:
                raise ValueError("Thread not found")
            
        message_id = self._generate_id()
        timestamp = created_at or self._now()
        
        # Create message item
        item = {
            'PK': f'MSG#{thread_id or message_id}',
            'SK': f'{"REPLY#" if thread_id else "MSG#"}{message_id}',
            'GSI1PK': f'CHANNEL#{channel_id}',
            'GSI1SK': f'TS#{timestamp}',
            'GSI2PK': f'USER#{user_id}',
            'GSI2SK': f'TS#{timestamp}',
            'id': message_id,
            'content': content,
            'user_id': user_id,
            'channel_id': channel_id,
            'created_at': timestamp,
            'reactions': {},
            'version': 1,
            'is_edited': False
        }
        
        if thread_id:
            item['thread_id'] = thread_id
            
        if attachments:
            item['attachments'] = attachments
            
        try:
            # Write to DynamoDB
            self.table.put_item(Item=item)
            
            # Index words for search
            if content:
                words = set(content.lower().split())
                for word in words:
                    word_item = {
                        'PK': f'WORD#{word}',
                        'SK': f'MESSAGE#{message_id}',
                        'GSI3PK': f'CONTENT#{word}',
                        'GSI3SK': f'TS#{timestamp}',
                        'message_id': message_id,
                        'channel_id': channel_id
                    }
                    self.table.put_item(Item=word_item)
                
            message = Message(
                id=message_id,
                content=content,
                user_id=user_id,
                channel_id=channel_id,
                created_at=timestamp,
                thread_id=thread_id,
                attachments=attachments,
                reactions={},
                is_edited=False,
                version=1
            )
            
            # Attach user data
            message.user = user
            
            return message
            
        except Exception as e:
            print(f"Error creating message: {type(e).__name__} - {str(e)}")
            print("Failed item:", item)
            raise

    def get_message(self, message_id: str, thread_id: Optional[str] = None) -> Optional[Message]:
        """Get a message by ID
        
        Args:
            message_id: The ID of the message to get
            thread_id: Optional thread ID if this is a reply message
            
        Returns:
            Message if found, None otherwise
        """
        # For thread replies, use thread_id as PK and message_id as SK
        if thread_id:
            response = self.table.get_item(
                Key={
                    'PK': f'MSG#{thread_id}',
                    'SK': f'REPLY#{message_id}'
                }
            )
        else:
            response = self.table.get_item(
                Key={
                    'PK': f'MSG#{message_id}',
                    'SK': f'MSG#{message_id}'
                }
            )
        
        if 'Item' not in response:
            return None
            
        item = self._clean_item(response['Item'])
        item['reactions'] = response['Item'].get('reactions', {})
        message = Message(**item)
        
        # Add user data
        user = self.user_service.get_user_by_id(message.user_id)
        if user:
            message.user = user
            
        return message

    def get_messages(self, channel_id: str, before: str = None, limit: int = 10000, reverse: bool = False) -> List[Message]:
        """Get messages from a channel
        
        Args:
            channel_id: The channel to get messages from
            before: Optional timestamp to get messages before
            limit: Maximum number of messages to return (default 10000)
            reverse: If True, returns messages in reverse chronological order (newest first)
            
        Returns:
            List of messages in chronological order (or reverse if reverse=True)
        """
        # Verify channel exists
        channel = self.channel_service.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError("Channel not found")
            
        query_params = {
            'IndexName': 'GSI1',
            'KeyConditionExpression': Key('GSI1PK').eq(f'CHANNEL#{channel_id}'),
            'ScanIndexForward': not reverse  # False = newest first
        }
        
        if before:
            query_params['ExclusiveStartKey'] = {
                'GSI1PK': f'CHANNEL#{channel_id}',
                'GSI1SK': f'TS#{before}'
            }
        
        # Query messages with pagination
        all_items = []
        last_evaluated_key = None
        
        while True:
            if last_evaluated_key:
                query_params['ExclusiveStartKey'] = last_evaluated_key
                
            response = self.table.query(**query_params)
            all_items.extend(response['Items'])
            
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key or len(all_items) >= limit:
                break
                
        # Get all unique user IDs first
        user_ids = set(item['user_id'] for item in all_items)
        users = {user.id: user for user in self.user_service._batch_get_users(user_ids)}
        
        # Process messages
        messages = []
        for item in all_items[:limit]:  # Apply limit here
            cleaned = self._clean_item(item)
            cleaned['reactions'] = item.get('reactions', {})
            message = Message(**cleaned)
            
            # Add user data
            if message.user_id in users:
                message.user = users[message.user_id]
                
            messages.append(message)
        
        return messages

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        """Get messages in a thread
        
        Args:
            thread_id: The ID of the thread to get messages from
            
        Returns:
            List of messages in chronological order
        """
        # Query messages
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'MSG#{thread_id}') & Key('SK').begins_with('REPLY#'),
            ScanIndexForward=True  # Return in chronological order
        )
        
        # Get all unique user IDs first
        user_ids = set(item['user_id'] for item in response['Items'])
        users = {user.id: user for user in self.user_service._batch_get_users(user_ids)}
        
        # Process messages and sort by timestamp
        messages = []
        for item in response['Items']:
            cleaned = self._clean_item(item)
            cleaned['reactions'] = item.get('reactions', {})
            message = Message(**cleaned)
            
            # Add user data
            if message.user_id in users:
                message.user = users[message.user_id]
                
            messages.append(message)
            
        # Sort by timestamp to ensure chronological order
        messages.sort(key=lambda m: m.created_at)
            
        return messages

    def add_reaction(self, message_id: str, user_id: str, emoji: str) -> Reaction:
        """Add a reaction by updating the reactions map in the message item"""
        print(f"\n=== Adding reaction to message {message_id} ===")
        print(f"User: {user_id}")
        print(f"Emoji: {emoji}")
        timestamp = self._now()
        
        # First get the message
        message = self.get_message(message_id)
        if not message:
            raise ValueError("Message not found")
            
        print(f"Found message. Current reactions: {message.reactions}")
            
        # Get existing reactions map from the message item
        reactions = message.reactions if message.reactions else {}
        print(f"Initial reactions map: {reactions}")
            
        # Add the new reaction
        if emoji not in reactions:
            print(f"Creating new reactions list for emoji {emoji}")
            reactions[emoji] = []
        if user_id not in reactions[emoji]:
            print(f"Adding user {user_id} to reactions for {emoji}")
            reactions[emoji].append(user_id)
        else:
            print(f"User {user_id} already reacted with {emoji}")
            
        print(f"Final reactions map to save: {reactions}")
            
        # Update reactions
        self.table.update_item(
            Key={
                'PK': f'MSG#{message_id}',
                'SK': f'MSG#{message_id}'
            },
            UpdateExpression='SET reactions = :reactions',
            ExpressionAttributeValues={
                ':reactions': reactions
            }
        )
        
        print("Saved reactions to DynamoDB")
        
        return Reaction(
            message_id=message_id,
            user_id=user_id,
            emoji=emoji,
            created_at=timestamp
        )

    def remove_reaction(self, message_id: str, user_id: str, emoji: str) -> None:
        """Remove a reaction from a message"""
        print(f"\n=== Removing reaction from message {message_id} ===")
        print(f"User: {user_id}")
        print(f"Emoji: {emoji}")
        
        # First get the message
        message = self.get_message(message_id)
        if not message:
            raise ValueError("Message not found")
            
        print(f"Found message. Current reactions: {message.reactions}")
            
        # Get existing reactions map from the message item
        reactions = message.reactions if message.reactions else {}
        print(f"Initial reactions map: {reactions}")
            
        # Remove the reaction
        if emoji in reactions and user_id in reactions[emoji]:
            print(f"Removing user {user_id} from reactions for {emoji}")
            reactions[emoji].remove(user_id)
            
            # Remove the emoji key if no users are left
            if not reactions[emoji]:
                print(f"No users left for {emoji}, removing emoji key")
                del reactions[emoji]
        else:
            print(f"User {user_id} has not reacted with {emoji}")
            return
            
        print(f"Final reactions map to save: {reactions}")
            
        # Update reactions
        self.table.update_item(
            Key={
                'PK': f'MSG#{message_id}',
                'SK': f'MSG#{message_id}'
            },
            UpdateExpression='SET reactions = :reactions',
            ExpressionAttributeValues={
                ':reactions': reactions
            }
        )
        
        print("Saved reactions to DynamoDB")

    def update_message(self, message_id: str, content: str) -> Message:
        """Update a message's content and maintain edit history"""
        timestamp = self._now()
        
        # First get the message
        message = self.get_message(message_id)
        if not message:
            raise ValueError("Message not found")
            
        # Verify channel still exists
        channel = self.channel_service.get_channel_by_id(message.channel_id)
        if not channel:
            raise ValueError("Channel not found")
            
        # Create a version entry with the current content and timestamp
        version_entry = {
            'content': message.content,  # Current content becomes old version
            'edited_at': message.edited_at if hasattr(message, 'edited_at') else message.created_at
        }
            
        # Update message
        self.table.update_item(
            Key={
                'PK': f'MSG#{message_id}',
                'SK': f'MSG#{message_id}'
            },
            UpdateExpression='SET content = :content, edited_at = :edited_at, is_edited = :is_edited, edit_history = list_append(if_not_exists(edit_history, :empty_list), :version)',
            ExpressionAttributeValues={
                ':content': content,
                ':edited_at': timestamp,
                ':is_edited': True,
                ':version': [version_entry],
                ':empty_list': []
            }
        )
            
        # Get updated message and attach user data
        updated_message = self.get_message(message_id)
        if updated_message:
            user = self.user_service.get_user_by_id(updated_message.user_id)
            if user:
                updated_message.user = user
        return updated_message 

    def get_user_messages(self, user_id: str, before: str = None, limit: int = 50) -> List[Message]:
        """Get messages created by a user.
        
        Args:
            user_id: The ID of the user
            before: Optional timestamp to get messages before
            limit: Maximum number of messages to return (default 50)
            
        Returns:
            List of messages in reverse chronological order
        """
        # Verify user exists
        user = self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Query messages
        query_params = {
            'IndexName': 'GSI2',
            'KeyConditionExpression': Key('GSI2PK').eq(f'USER#{user_id}') & Key('GSI2SK').begins_with('TS#'),
            'Limit': limit,
            'ScanIndexForward': False  # Return in reverse chronological order
        }
        
        if before:
            # For pagination we need:
            # 1. The GSI2 keys (partition and sort)
            # 2. The table's primary key attributes (PK and SK)
            query_params['ExclusiveStartKey'] = {
                'GSI2PK': f'USER#{user_id}',
                'GSI2SK': f'TS#{before}',
                'PK': f'MSG#{before}',  # Using timestamp as message ID for simplicity
                'SK': f'MSG#{before}'
            }
        
        response = self.table.query(**query_params)

        # Process messages
        messages = []
        for item in response['Items']:
            cleaned = self._clean_item(item)
            cleaned['reactions'] = item.get('reactions', {})
            cleaned['attachments'] = item.get('attachments', [])
            cleaned['edit_history'] = item.get('edit_history', [])
            cleaned['is_edited'] = item.get('is_edited', False)
            cleaned['edited_at'] = item.get('edited_at')
            
            message = Message(**cleaned)
            message.user = user
            messages.append(message)
        
        return messages 