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
        
        # Create message item
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

        # Write to DynamoDB
        self.table.put_item(Item=item)
        
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
                    'message_id': message_id,
                    'channel_id': channel_id
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

    def get_messages(self, channel_id: str, before: str = None, limit: int = 50) -> List[Message]:
        """Get messages from a channel"""
        start_time = time.time()
        print("\n" + "="*50)
        print(f"GETTING MESSAGES FOR CHANNEL {channel_id}")
        print("="*50)
        
        # Verify channel exists
        channel_start = time.time()
        print("\n[1/4] Looking up channel...")
        channel = self.channel_service.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError("Channel not found")
        print(f"✓ Channel lookup took: {time.time() - channel_start:.3f}s")
            
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
        
        # Query messages
        print("\n[2/4] Querying messages...")
        query_start = time.time()    
        response = self.table.query(**query_params)
        print(f"✓ DynamoDB query took: {time.time() - query_start:.3f}s")
        print(f"✓ Found {len(response['Items'])} messages")
        
        # Get all unique user IDs first
        print("\n[3/4] Looking up user data...")
        users_start = time.time()
        user_ids = set(item['user_id'] for item in response['Items'])
        print(f"✓ Found {len(user_ids)} unique users")
        print(f"✓ User IDs: {user_ids}")
        users = {user.id: user for user in self.user_service._batch_get_users(user_ids)}
        print(f"✓ User data lookup took: {time.time() - users_start:.3f}s")
        
        # Process messages
        print("\n[4/4] Processing messages...")
        process_start = time.time()
        messages = []
        for item in response['Items']:
            cleaned = self._clean_item(item)
            cleaned['reactions'] = item.get('reactions', {})
            
            message = Message(**cleaned)
            if message.user_id in users:
                message.user = users[message.user_id]
            messages.append(message)
        print(f"✓ Message processing took: {time.time() - process_start:.3f}s")
        
        total_time = time.time() - start_time
        print("\n" + "-"*50)
        print(f"TOTAL TIME: {total_time:.3f}s")
        print("-"*50 + "\n")
        return messages

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        """Get messages in a thread"""
        start_time = time.time()
        print("\n" + "="*50)
        print(f"GETTING THREAD MESSAGES FOR {thread_id}")
        print("="*50)
        
        # Query messages
        print("\n[1/3] Querying messages...")
        query_start = time.time()
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq(f'THREAD#{thread_id}')
        )
        print(f"✓ DynamoDB query took: {time.time() - query_start:.3f}s")
        print(f"✓ Found {len(response['Items'])} messages")
        
        # Get all unique user IDs first
        print("\n[2/3] Looking up user data...")
        users_start = time.time()
        user_ids = set(item['user_id'] for item in response['Items'])
        print(f"✓ Found {len(user_ids)} unique users")
        print(f"✓ User IDs: {user_ids}")
        users = {user.id: user for user in self.user_service._batch_get_users(user_ids)}
        print(f"✓ User data lookup took: {time.time() - users_start:.3f}s")
        
        # Process messages
        print("\n[3/3] Processing messages...")
        process_start = time.time()
        messages = []
        for item in response['Items']:
            cleaned = self._clean_item(item)
            cleaned['reactions'] = item.get('reactions', {})
            
            message = Message(**cleaned)
            if message.user_id in users:
                message.user = users[message.user_id]
            messages.append(message)
        print(f"✓ Message processing took: {time.time() - process_start:.3f}s")
        
        total_time = time.time() - start_time
        print("\n" + "-"*50)
        print(f"TOTAL TIME: {total_time:.3f}s")
        print("-"*50 + "\n")
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