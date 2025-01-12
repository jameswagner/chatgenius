from typing import Optional, List, Dict
from datetime import datetime, timezone
import uuid
import logging
from boto3.dynamodb.conditions import Key, Attr
from .base_service import BaseService
from .user_service import UserService

class ChannelService(BaseService):
    def __init__(self, table_name: str = None):
        super().__init__(table_name)
        self.user_service = UserService(table_name)

    def create_channel(self, name: str, type: str, created_by: str, other_user_id: str = None) -> Dict:
        """Create a new channel."""
        channel_id = self._generate_id()
        timestamp = self._now()
        
        # For DM channels, use a consistent naming convention
        if type == 'dm':
            if not other_user_id:
                raise ValueError("other_user_id is required for DM channels")
            # Check if DM already exists
            existing = self.get_dm_channel(created_by, other_user_id)
            if existing:
                raise ValueError("DM channel already exists")
            name = f"dm_{created_by}_{other_user_id}"
        else:
            # Check for duplicate channel names
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq(f'TYPE#{type}') & 
                                     Key('GSI1SK').eq(f'NAME#{name}')
            )
            if response['Items']:
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
            'created_at': timestamp
        }
        
        self.table.put_item(Item=item)
        
        # Add creator to channel
        self.add_channel_member(channel_id, created_by)
        
        # For DM channels, add other user
        if type == 'dm' and other_user_id:
            self.add_channel_member(channel_id, other_user_id)
        
        return self.get_channel_by_id(channel_id)

    def get_channel_by_id(self, channel_id: str) -> Optional[Dict]:
        """Get a channel by its ID."""
        response = self.table.get_item(
            Key={
                'PK': f'CHANNEL#{channel_id}',
                'SK': '#METADATA'
            }
        )
        
        if 'Item' not in response:
            return None
            
        channel = self._clean_item(response['Item'])
        channel['members'] = self.get_channel_members(channel_id)
        return channel

    def get_channels_for_user(self, user_id: str) -> List[Dict]:
        """Get all channels a user is a member of."""
        # Query GSI2 to get all channels for user
        response = self.table.query(
            IndexName='GSI2',
            KeyConditionExpression=Key('GSI2PK').eq(f'USER#{user_id}')
        )
        
        channels = []
        for item in response.get('Items', []):
            channel_id = item['GSI2SK'].split('#')[1]
            channel = self.get_channel_by_id(channel_id)
            if channel:
                channels.append(channel)
        
        return channels

    def get_available_channels(self, user_id: str) -> List[Dict]:
        """Get public channels the user is not a member of."""
        # Get public channels
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('TYPE#public')
        )
        
        # Filter out channels user is already member of
        user_channels = self.get_channels_for_user(user_id)
        user_channel_ids = {c['id'] for c in user_channels}
        
        channels = []
        for item in response.get('Items', []):
            channel = self._clean_item(item)
            if channel['id'] not in user_channel_ids:
                channel['members'] = self.get_channel_members(channel['id'])
                channels.append(channel)
        
        return channels

    def get_dm_channel(self, user1_id: str, user2_id: str) -> Optional[Dict]:
        """Get the DM channel between two users if it exists."""
        name1 = f"dm_{user1_id}_{user2_id}"
        name2 = f"dm_{user2_id}_{user1_id}"
        
        response = self.table.scan(
            FilterExpression='SK = :sk AND #type = :type AND (#name = :name1 OR #name = :name2)',
            ExpressionAttributeNames={
                '#type': 'type',
                '#name': 'name'
            },
            ExpressionAttributeValues={
                ':sk': '#METADATA',
                ':type': 'dm',
                ':name1': name1,
                ':name2': name2
            }
        )
        
        items = response.get('Items', [])
        if not items:
            return None
            
        channel = self._clean_item(items[0])
        channel['members'] = self.get_channel_members(channel['id'])
        return channel

    def add_channel_member(self, channel_id: str, user_id: str) -> None:
        """Add a member to a channel."""
        # Get channel to verify it exists
        channel = self.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError("Channel not found")
            
        # Check if user exists
        user = self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
            
        # Check if already a member
        members = self.get_channel_members(channel_id)
        if any(m['id'] == user_id for m in members):
            raise ValueError("User is already a member")
            
        timestamp = self._now()
        item = {
            'PK': f'CHANNEL#{channel_id}',
            'SK': f'MEMBER#{user_id}',
            'GSI2PK': f'USER#{user_id}',
            'GSI2SK': f'CHANNEL#{channel_id}',
            'joined_at': timestamp,
            'last_read': timestamp
        }
        
        self.table.put_item(Item=item)

    def get_channel_members(self, channel_id: str) -> List[Dict]:
        """Get all members of a channel."""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MEMBER#')
        )
        
        members = []
        for item in response.get('Items', []):
            user_id = item['SK'].split('#')[1]
            user = self.user_service.get_user_by_id(user_id)
            if user:
                members.append({
                    'id': user_id,
                    'name': user.get('name'),
                    'joined_at': item.get('joined_at'),
                    'last_read': item.get('last_read')
                })
        
        return members

    def get_channel_message_count(self, channel_id: str) -> int:
        """Get the number of messages in a channel."""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MSG#'),
            Select='COUNT'
        )
        
        return response.get('Count', 0)

    def get_other_dm_user(self, channel_id: str, current_user_id: str) -> Optional[Dict]:
        """Get the other user in a DM channel."""
        channel = self.get_channel_by_id(channel_id)
        if not channel or channel['type'] != 'dm':
            raise ValueError("Not a DM channel")
            
        members = self.get_channel_members(channel_id)
        for member in members:
            if member['id'] != current_user_id:
                return member
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