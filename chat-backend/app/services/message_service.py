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

class MessageService(BaseService):
    def __init__(self, table_name: str = None):
        super().__init__(table_name)
        self.user_service = UserService(table_name)
        self.channel_service = ChannelService(table_name)
        
    def create_message(self, channel_id: str, user_id: str, content: str, thread_id: str = None, attachments: List[str] = None) -> Message:
        """Create a new message"""
        print(f"\n=== Creating message ===")
        print(f"Channel: {channel_id}")
        print(f"User: {user_id}")
        print(f"Content: {content}")
        print(f"Thread: {thread_id}")
        print(f"Attachments: {attachments}")
        
        # Verify channel exists
        channel = self.channel_service.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError("Channel not found")
            
        # Verify user exists
        user = self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
            
        message_id = self._generate_id()
        timestamp = self._now()
        
        # Create main message item - new format
        item = {
            'PK': f'MSG#{message_id}',
            'SK': f'MSG#{message_id}',
            'GSI1PK': f'CHANNEL#{channel_id}',
            'GSI1SK': f'TS#{timestamp}',
            'GSI2PK': f'USER#{user_id}',
            'GSI2SK': f'TS#{timestamp}',
            'id': message_id,
            'channel_id': channel_id,
            'user_id': user_id,
            'content': content,
            'created_at': timestamp,
            'reactions': {},
            'version': 1
        }
        
        if thread_id:
            item['thread_id'] = thread_id
            item['GSI1PK'] = f'THREAD#{thread_id}'
            
        if attachments:
            item['attachments'] = attachments

        # Write new format
        self.table.put_item(Item=item)
        
        # Write old format for backward compatibility
        old_item = {
            'PK': f'CHANNEL#{channel_id}',
            'SK': f'MSG#{timestamp}#{message_id}',
            'GSI1PK': f'USER#{user_id}',
            'GSI1SK': f'TS#{timestamp}',
            'id': message_id,
            'channel_id': channel_id,
            'user_id': user_id,
            'content': content,
            'created_at': timestamp,
            'reactions': {},
            'version': 1
        }
        if thread_id:
            old_item['thread_id'] = thread_id
        if attachments:
            old_item['attachments'] = attachments
            
        self.table.put_item(Item=old_item)
        
        # Index words for search
        if content:
            print("\nIndexing words for search...")
            words = set(content.lower().split())
            print(f"Words to index: {words}")
            
            for word in words:
                word_item = {
                    'PK': f'WORD#{word}',
                    'SK': f'MESSAGE#{message_id}',
                    'GSI3PK': f'CONTENT#{word}',
                    'GSI3SK': f'TS#{timestamp}',
                    'message_id': message_id
                }
                self.table.put_item(Item=word_item)
            print("Word indexing complete")
        
        message = Message(**self._clean_item(item))
        if user:
            message.user = user
            print(f"Added user data to message: {user.name}")
            
        return message

    def get_message(self, message_id: str) -> Optional[Message]:
        """Get a message by ID"""
        # Try new format first
        response = self.table.get_item(
            Key={
                'PK': f'MSG#{message_id}',
                'SK': f'MSG#{message_id}'
            }
        )
        
        if 'Item' in response:
            item = self._clean_item(response['Item'])
            item['reactions'] = response['Item'].get('reactions', {})
            message = Message(**item)
            
            # Add user data
            user = self.user_service.get_user_by_id(message.user_id)
            if user:
                message.user = user
                
            return message
            
        # Fall back to old format
        response = self.table.scan(
            FilterExpression=Attr('id').eq(message_id) & 
                           Attr('SK').begins_with('MSG#')
        )
        
        if not response['Items']:
            return None
            
        item = self._clean_item(response['Items'][0])
        item['reactions'] = response['Items'][0].get('reactions', {})
        message = Message(**item)
        
        # Add user data
        user = self.user_service.get_user_by_id(message.user_id)
        if user:
            message.user = user
            
        return message

    def get_messages(self, channel_id: str, before: str = None, limit: int = 50) -> List[Message]:
        """Get messages from a channel"""
        # Verify channel exists
        channel = self.channel_service.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError("Channel not found")
            
        # Try new format first
        query_params = {
            'IndexName': 'GSI1',
            'KeyConditionExpression': Key('GSI1PK').eq(f'CHANNEL#{channel_id}'),
            'Limit': limit,
            'ScanIndexForward': True  # Return in chronological order
        }
        
        if before:
            query_params['ExclusiveStartKey'] = {
                'GSI1PK': f'CHANNEL#{channel_id}',
                'GSI1SK': f'TS#{before}'
            }
            
        response = self.table.query(**query_params)
        
        if response['Items']:
            # Get all unique user IDs first
            user_ids = set(item['user_id'] for item in response['Items'])
            users = {user.id: user for user in [self.user_service.get_user_by_id(uid) for uid in user_ids] if user}
            
            messages = []
            for item in response['Items']:
                cleaned = self._clean_item(item)
                cleaned['reactions'] = item.get('reactions', {})
                
                message = Message(**cleaned)
                if message.user_id in users:
                    message.user = users[message.user_id]
                messages.append(message)
            
            return messages
            
        # Fall back to old format
        query_params = {
            'KeyConditionExpression': Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                    Key('SK').begins_with('MSG#'),
            'Limit': limit,
            'ScanIndexForward': True  # Return in chronological order
        }
        
        if before:
            query_params['ExclusiveStartKey'] = {
                'PK': f'CHANNEL#{channel_id}',
                'SK': f'MSG#{before}'
            }
            
        response = self.table.query(**query_params)
        
        # Get all unique user IDs first
        user_ids = set(item['user_id'] for item in response['Items'])
        users = {user.id: user for user in [self.user_service.get_user_by_id(uid) for uid in user_ids] if user}
        
        messages = []
        for item in response['Items']:
            cleaned = self._clean_item(item)
            cleaned['reactions'] = item.get('reactions', {})
            
            message = Message(**cleaned)
            if message.user_id in users:
                message.user = users[message.user_id]
            messages.append(message)
        
        return messages

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        """Get messages in a thread"""
        # Try new format first
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq(f'THREAD#{thread_id}')
        )
        
        if response['Items']:
            # Get all unique user IDs first
            user_ids = set(item['user_id'] for item in response['Items'])
            users = {user.id: user for user in [self.user_service.get_user_by_id(uid) for uid in user_ids] if user}
            
            messages = []
            for item in response['Items']:
                cleaned = self._clean_item(item)
                cleaned['reactions'] = item.get('reactions', {})
                
                message = Message(**cleaned)
                if message.user_id in users:
                    message.user = users[message.user_id]
                messages.append(message)
            
            return messages
            
        # Fall back to old format
        response = self.table.scan(
            FilterExpression=Attr('thread_id').eq(thread_id)
        )
        
        # Get all unique user IDs first
        user_ids = set(item['user_id'] for item in response['Items'])
        users = {user.id: user for user in [self.user_service.get_user_by_id(uid) for uid in user_ids] if user}
        
        messages = []
        for item in response['Items']:
            cleaned = self._clean_item(item)
            cleaned['reactions'] = item.get('reactions', {})
            
            message = Message(**cleaned)
            if message.user_id in users:
                message.user = users[message.user_id]
            messages.append(message)
        
        return messages

    def add_reaction(self, message_id: str, user_id: str, emoji: str) -> Reaction:
        """Add a reaction by updating the reactions map in the message item"""
        print(f"\n=== Adding reaction to message {message_id} ===")
        print(f"User: {user_id}")
        print(f"Emoji: {emoji}")
        timestamp = self._now()
        
        # First get the message to get its channel_id and created_at
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
            
        # Update both new and old format
        # New format
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
        
        # Old format
        self.table.update_item(
            Key={
                'PK': f'CHANNEL#{message.channel_id}',
                'SK': f'MSG#{message.created_at}#{message_id}'
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
            
        # Update both new and old format
        # New format
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
        
        # Old format
        self.table.update_item(
            Key={
                'PK': f'CHANNEL#{message.channel_id}',
                'SK': f'MSG#{message.created_at}#{message_id}'
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

    def remove_reaction(self, message_id: str, user_id: str, emoji: str) -> None:
        """Remove a reaction from a message"""
        print(f"\n=== Removing reaction from message {message_id} ===")
        print(f"User: {user_id}")
        print(f"Emoji: {emoji}")
        
        # First get the message to get its channel_id and created_at
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
            
        # Update both new and old format
        # New format
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
        
        # Old format
        self.table.update_item(
            Key={
                'PK': f'CHANNEL#{message.channel_id}',
                'SK': f'MSG#{message.created_at}#{message_id}'
            },
            UpdateExpression='SET reactions = :reactions',
            ExpressionAttributeValues={
                ':reactions': reactions
            }
        )
        
        print("Saved reactions to DynamoDB") 