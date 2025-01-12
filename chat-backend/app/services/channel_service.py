from typing import Optional, List, Dict
from datetime import datetime, timezone
import uuid
import logging
from boto3.dynamodb.conditions import Key, Attr
from .base_service import BaseService
from .user_service import UserService
from ..models.channel import Channel

class ChannelService(BaseService):
    def __init__(self, table_name: str = None):
        super().__init__(table_name)
        self.user_service = UserService(table_name)

    def _clean_item(self, item: Dict) -> Dict:
        """Clean DynamoDB item for channel model creation"""
        cleaned = super()._clean_item(item)
        # Only keep type field for channel metadata items
        if 'type' in cleaned and not ('CHANNEL#' in item.get('PK', '') and '#METADATA' in item.get('SK', '')):
            cleaned.pop('type')
        return cleaned

    def create_channel(self, name: str, type: str = 'public', created_by: str = None, other_user_id: str = None) -> Channel:
        """Create a new channel."""
        channel_id = self._generate_id()
        timestamp = self._now()
        
        # For DM channels, use a consistent naming convention
        if type == 'dm' and other_user_id:
            user_ids = sorted([created_by, other_user_id])
            name = f"dm_{user_ids[0]}_{user_ids[1]}"
            
            # Check if DM channel already exists
            existing = self.get_dm_channel(created_by, other_user_id)
            if existing:
                raise ValueError("DM channel already exists")
        else:
            # Check for duplicate channel name
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq(f'TYPE#{type}') & 
                                     Key('GSI1SK').eq(f'NAME#{name}')
            )
            if response.get('Items'):
                raise ValueError("Channel name already exists")
        
        item = {
            'PK': f'CHANNEL#{channel_id}',
            'SK': '#METADATA',
            'GSI1PK': f'TYPE#{type}',
            'GSI1SK': f'NAME#{name}',
            'id': channel_id,
            'name': name,
            'type': type,
            'created_by': created_by,
            'created_at': timestamp,
            'members': []
        }
        
        self.table.put_item(Item=item)
        
        # Add creator to channel
        if created_by:
            self.add_channel_member(channel_id, created_by)
            
        # For DM channels, add other user
        if type == 'dm' and other_user_id:
            self.add_channel_member(channel_id, other_user_id)
            
        # Get channel with members
        channel = Channel(**self._clean_item(item))
        channel.members = self.get_channel_members(channel_id)
        return channel

    def get_channel_by_id(self, channel_id: str) -> Optional[Channel]:
        """Get a channel by its ID."""
        print(f"\n=== Getting channel by ID: {channel_id} ===")
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'CHANNEL#{channel_id}',
                    'SK': '#METADATA'
                }
            )
            
            if 'Item' not in response:
                print(f"No channel found with ID: {channel_id}")
                return None
                
            item = response['Item']
            print(f"Found channel: {item.get('name')} (type: {item.get('type')})")
            return Channel(**self._clean_item(item))
        except Exception as e:
            print(f"Error getting channel by ID: {str(e)}")
            print(f"Error type: {type(e)}")
            raise

    def get_channels_for_user(self, user_id: str) -> List[Channel]:
        """Get all channels a user is a member of."""
        print(f"\n=== Getting channels for user {user_id} ===")
        # Query GSI2 to get all channels for user
        response = self.table.query(
            IndexName='GSI2',
            KeyConditionExpression=Key('GSI2PK').eq(f'USER#{user_id}')
        )
        
        channel_ids = [item['GSI2SK'].split('#')[1] for item in response['Items']]
        print(f"Found channel IDs: {channel_ids}")
        
        channels = []
        
        # Get channel details
        for channel_id in channel_ids:
            # Get channel metadata
            response = self.table.get_item(
                Key={
                    'PK': f'CHANNEL#{channel_id}',
                    'SK': '#METADATA'
                }
            )
            if 'Item' in response:
                channel_data = self._clean_item(response['Item'])
                print(f"Found channel: {channel_data['name']}")
                
                # Add members for DM channels
                if channel_data.get('type') == 'dm':
                    channel_data['members'] = self.get_channel_members(channel_id)
                    print(f"Added members for DM channel: {channel_data['members']}")
                
                channels.append(Channel(**channel_data))
            else:
                print(f"Warning: Channel {channel_id} metadata not found")
        
        return channels

    def get_available_channels(self, user_id: str) -> List[Channel]:
        """Get public channels the user is not a member of."""
        print(f"\n=== Getting available channels for user {user_id} ===")
        # Get public channels
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('TYPE#public')
        )
        
        # Filter out channels user is already member of
        user_channels = self.get_channels_for_user(user_id)
        user_channel_ids = {c.id for c in user_channels}
        print(f"User is already member of channels: {user_channel_ids}")
        
        channels = []
        for item in response['Items']:
            cleaned = self._clean_item(item)
            if cleaned['id'] not in user_channel_ids:
                print(f"Adding available channel: {cleaned['name']}")
                channels.append(Channel(**cleaned))
            else:
                print(f"Skipping channel {cleaned['name']} as user is already a member")
        return channels

    def get_dm_channel(self, user1_id: str, user2_id: str) -> Optional[Channel]:
        """Get the DM channel between two users if it exists."""
        user_ids = sorted([user1_id, user2_id])
        dm_name = f"dm_{user_ids[0]}_{user_ids[1]}"
        
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('TYPE#dm') & 
                                 Key('GSI1SK').eq(f'NAME#{dm_name}')
        )
        
        if not response['Items']:
            return None
            
        channel = Channel(**self._clean_item(response['Items'][0]))
        channel.members = self.get_channel_members(channel.id)
        return channel

    def add_channel_member(self, channel_id: str, user_id: str) -> None:
        """Add a member to a channel."""
        print(f"\n=== Adding user {user_id} to channel {channel_id} ===")
        timestamp = self._now()
        
        # First check if channel exists
        channel = self.get_channel_by_id(channel_id)
        print(f"Channel exists check: {channel is not None}")
        if not channel:
            raise ValueError("Channel not found")
        
        # Check if user exists
        user = self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Check if user is already a member
        response = self.table.get_item(
            Key={
                'PK': f'CHANNEL#{channel_id}',
                'SK': f'MEMBER#{user_id}'
            }
        )
        if 'Item' in response:
            raise ValueError("User is already a member")
        
        item = {
            'PK': f'CHANNEL#{channel_id}',
            'SK': f'MEMBER#{user_id}',
            'GSI2PK': f'USER#{user_id}',
            'GSI2SK': f'CHANNEL#{channel_id}',
            'joined_at': timestamp,
            'last_read': timestamp
        }
        
        try:
            print(f"Attempting to add member item: {item}")
            self.table.put_item(Item=item)
            print("Successfully added channel member")
        except Exception as e:
            print(f"Error adding channel member: {str(e)}")
            print(f"Error type: {type(e)}")
            raise

    def get_channel_members(self, channel_id: str) -> List[dict]:
        """Get members of a channel"""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MEMBER#')
        )
        
        members = []
        for item in response['Items']:
            user_id = item['SK'].split('#')[1]
            user = self.user_service.get_user_by_id(user_id)
            if user:
                members.append({
                    'id': user.id,
                    'name': user.name
                })
                
        return members

    def get_channel_message_count(self, channel_id: str) -> int:
        """Get the number of messages in a channel."""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MSG#'),
            Select='COUNT'
        )
        
        return response['Count']

    def get_other_dm_user(self, channel_id: str, user_id: str) -> Optional[str]:
        """Get the other user in a DM channel."""
        channel = self.get_channel_by_id(channel_id)
        if channel.type != "dm":
            raise ValueError("Not a DM channel")

        members = self.get_channel_members(channel_id)
        for member in members:
            if member['id'] != user_id:
                return member['id']
        return None

    def mark_channel_read(self, channel_id: str, user_id: str) -> None:
        """Mark all current messages in a channel as read for a user."""
        # Verify user is a member
        members = self.get_channel_members(channel_id)
        if not any(m['id'] == user_id for m in members):
            raise ValueError("User is not a member")
            
        timestamp = self._now()
        
        # Update the member's last_read timestamp
        item = {
            'PK': f'CHANNEL#{channel_id}',
            'SK': f'MEMBER#{user_id}',
            'GSI2PK': f'USER#{user_id}',
            'GSI2SK': f'CHANNEL#{channel_id}',
            'last_read': timestamp
        }
        
        self.table.put_item(Item=item) 