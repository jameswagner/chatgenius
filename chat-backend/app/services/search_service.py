from typing import List
from boto3.dynamodb.conditions import Key
from .base_service import BaseService
from .channel_service import ChannelService
from .user_service import UserService
from ..models.message import Message
import os
import boto3

class SearchService(BaseService):
    def __init__(self, table_name: str = None):
        super().__init__(table_name)
        self.channel_service = ChannelService(table_name)
        self.user_service = UserService(table_name)
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )

    def search_messages(self, user_id: str, query: str) -> List[Message]:
        """Search for messages containing the query word in channels the user has access to"""
        print(f"\n=== Searching messages for query: '{query}' ===")
        channels = self.channel_service.get_channels_for_user(user_id)
        channel_ids = [channel.id for channel in channels]
        print(f"User's channels: {channel_ids}")
        
        word = query.lower()
        print(f"Searching GSI3 for word: '{word}'")
        response = self.table.query(
            IndexName='GSI3',
            KeyConditionExpression=Key('GSI3PK').eq(f'CONTENT#{word}')
        )
        print(f"GSI3 query response: {response}")
        
        message_ids = []
        for item in response['Items']:
            message_ids.extend(item['messages'])
        print(f"Found message IDs: {message_ids}")
        messages = []
        
        for message_id in message_ids:
            parts = message_id.split('#')
            msg_id = parts[0]
            thread_id = parts[1] if len(parts) > 1 else None
            message = self.message_service.get_message(msg_id, thread_id)
            if message and message.channel_id in channel_ids:
                user = self.user_service.get_user_by_id(message.user_id)
                if user:
                    message.user = user
                messages.append(message)
                print(f"Added message {msg_id} to results")
        
        print(f"Returning {len(messages)} messages")
        return messages[:50]