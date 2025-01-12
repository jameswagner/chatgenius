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
        
        # Create main message item
        item = {
            'PK': f'CHANNEL#{channel_id}',
            'SK': f'MSG#{timestamp}#{message_id}',
            'GSI1PK': f'USER#{user_id}',
            'GSI1SK': f'TS#{timestamp}',
            'id': message_id,
            'channel_id': channel_id,
            'user_id': user_id,
            'content': content,
            'created_at': timestamp,
            'version': 1
        }
        
        if thread_id:
            item['thread_id'] = thread_id
            
        if attachments:
            item['attachments'] = attachments

        print(f"\nPutting message item: {item}")
        self.table.put_item(Item=item)
        print("Message item created successfully")
        
        # Index words for search
        if content:
            print("\nIndexing words for search...")
            # Split content into words and normalize
            words = set(content.lower().split())
            print(f"Words to index: {words}")
            
            # Create index items for each word
            for word in words:
                word_item = {
                    'PK': f'WORD#{word}',
                    'SK': f'MESSAGE#{message_id}',
                    'GSI3PK': f'CONTENT#{word}',
                    'GSI3SK': f'TS#{timestamp}',
                    'message_id': message_id
                }
                print(f"Creating index item for word '{word}': {word_item}")
                self.table.put_item(Item=word_item)
            print("Word indexing complete")
        
        message = Message(**self._clean_item(item))
        user = self.user_service.get_user_by_id(user_id)
        if user:
            message.user = user
            print(f"Added user data to message: {user.name}")
            
        return message

    def get_message(self, message_id: str) -> Optional[Message]:
        response = self.table.scan(
            FilterExpression=Attr('id').eq(message_id) & 
                           Attr('SK').begins_with('MSG#')
        )
        
        if not response['Items']:
            return None
            
        item = self._clean_item(response['Items'][0])
        # Get reactions from the item itself since they're denormalized
        item['reactions'] = response['Items'][0].get('reactions', {})
        message = Message(**item)
        
        # Add user data
        user = self.user_service.get_user_by_id(message.user_id)
        if user:
            message.user = user
            
        return message

    def get_messages(self, channel_id: str, before: str = None, limit: int = 50) -> List[Message]:
        # Verify channel exists
        channel = self.channel_service.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError("Channel not found")
            
        query_params = {
            'KeyConditionExpression': Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                    Key('SK').begins_with('MSG#'),
            'Limit': limit,
            'ScanIndexForward': True
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
            
        # Update the entire reactions map
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


    def get_thread_messages(self, thread_id: str) -> List[Message]:
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

    def get_message_reactions(self, message_id: str) -> List[Reaction]:
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'MESSAGE#{message_id}') & 
                                 Key('SK').begins_with('REACTION#')
        )
        return [Reaction(**self._clean_item(item)) for item in response['Items']]

    def remove_reaction(self, message_id: str, user_id: str, emoji: str) -> None:
        self.table.delete_item(
            Key={
                'PK': f'MESSAGE#{message_id}',
                'SK': f'REACTION#{user_id}#{emoji}'
            }
        )

  
    def update_message(self, message_id: str, content: str) -> Message:
        """Update a message's content and maintain edit history"""
        timestamp = self._now()
        
        # First get the message to get its channel_id and created_at
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
            
        # Update the message
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