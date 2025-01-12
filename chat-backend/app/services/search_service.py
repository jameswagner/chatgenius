from typing import List
from boto3.dynamodb.conditions import Key
from .base_service import BaseService
from .channel_service import ChannelService
from .user_service import UserService
from ..models.message import Message

class SearchService(BaseService):
    def __init__(self, table_name: str = None):
        super().__init__(table_name)
        self.channel_service = ChannelService(table_name)
        self.user_service = UserService(table_name)

    def get_message(self, message_id: str) -> Message:
        """Get a message by its ID"""
        response = self.table.get_item(
            Key={
                'PK': f'MSG#{message_id}',
                'SK': f'MSG#{message_id}'
            }
        )
        
        if 'Item' not in response:
            return None
            
        item = self._clean_item(response['Item'])
        # Get reactions from the item itself since they're denormalized
        item['reactions'] = response['Item'].get('reactions', {})
        return Message(**item)

    def search_messages(self, user_id: str, query: str) -> List[Message]:
        """Search for messages containing the query word in channels the user has access to"""
        print(f"\n=== Searching messages for query: '{query}' ===")
        # Get user's channels
        channels = self.channel_service.get_channels_for_user(user_id)
        channel_ids = [channel.id for channel in channels]
        print(f"User's channels: {channel_ids}")
        
        # Search for messages containing the query word
        word = query.lower()
        print(f"Searching GSI3 for word: '{word}'")
        response = self.table.query(
            IndexName='GSI3',
            KeyConditionExpression=Key('GSI3PK').eq(f'CONTENT#{word}'),
            ScanIndexForward=False  # Latest first
        )
        print(f"GSI3 query response: {response}")
        
        message_ids = [item['message_id'] for item in response['Items']]
        print(f"Found message IDs: {message_ids}")
        messages = []
        
        # Get full message details and filter by user's channels
        for message_id in message_ids:
            message = self.get_message(message_id)
            if message and message.channel_id in channel_ids:
                user = self.user_service.get_user_by_id(message.user_id)
                if user:
                    message.user = user
                messages.append(message)
                print(f"Added message {message_id} to results")
                
        print(f"Returning {len(messages)} messages")
        return messages[:50]  # Limit results