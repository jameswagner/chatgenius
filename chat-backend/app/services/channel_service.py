"""Channel service for managing channels in DynamoDB

Schema for Channels:
    PK=CHANNEL#{id} SK=#METADATA  # Primary key for channel metadata
    GSI1PK=TYPE#{type}#NAME#{name} GSI1SK=#METADATA  # For looking up channels by type and name
    GSI2PK=USER#{user_id} GSI2SK=CHANNEL#{channel_id}  # For user-channel memberships
    GSI3PK=CHANNEL#{channel_id} GSI3SK=MESSAGE#{timestamp}  # For retrieving messages in a channel
    GSI4PK=WORKSPACE#{workspace_id} GSI4SK=CHANNEL#{channel_id}  # For workspace channel membership

Key Usage:
- Primary key (PK/SK): Stores channel metadata and properties
- GSI1: Used to look up channels by type (public/private/dm) and name
- GSI2: Maps users to channels they are members of, enabling efficient channel membership lookups
- GSI3: Enables chronological retrieval of messages within a channel
- GSI4: Enables efficient lookup of channels within a workspace

Channel Members:
    PK=CHANNEL#{channel_id} SK=MEMBER#{user_id}  # Primary key for channel membership
    GSI2PK=USER#{user_id} GSI2SK=CHANNEL#{channel_id}  # For user's channel memberships
"""

from typing import Optional, List, Dict
from datetime import datetime, timezone
import uuid
import logging
from boto3.dynamodb.conditions import Key, Attr
from .base_service import BaseService
from .user_service import UserService
from ..models.channel import Channel
from ..models.workspace import Workspace
import time
import boto3
import os

class ChannelService(BaseService):
    def __init__(self, table_name: str = None):
        super().__init__(table_name)
        self.user_service = UserService(table_name)
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )

    def _clean_item(self, item: Dict) -> Dict:
        """Clean DynamoDB item for channel model creation"""
        cleaned = super()._clean_item(item)
        # Only keep type field for channel metadata items
        if 'type' in cleaned and not ('CHANNEL#' in item.get('PK', '') and '#METADATA' in item.get('SK', '')):
            cleaned.pop('type')
        return cleaned

    def create_channel(self, name: str, type: str = 'public', created_by: str = None, other_user_id: str = None, workspace_id: str = "NO_WORKSPACE") -> Channel:
        """Create a new channel.
        
        Args:
            name: Channel name
            type: Channel type (public/private/dm)
            created_by: User ID of creator
            other_user_id: For DM channels, the other user's ID
            workspace_id: Workspace ID to assign channel to (defaults to NO_WORKSPACE)
        """
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
            'GSI4PK': f'WORKSPACE#{workspace_id}',
            'GSI4SK': f'CHANNEL#{channel_id}',
            'id': channel_id,
            'name': name,
            'type': type,
            'created_by': created_by,
            'created_at': timestamp,
            'workspace_id': workspace_id,
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
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'CHANNEL#{channel_id}',
                    'SK': '#METADATA'
                }
            )
            
            if 'Item' not in response:
                return None
                
            item = response['Item']
            return Channel(**self._clean_item(item))
        except Exception as e:
            logging.error(f"Error getting channel by ID: {str(e)}")
            raise

    def get_channels_for_user(self, user_id: str) -> List[Channel]:
        """Get all channels a user is a member of."""
        # Query GSI2 to get all channels for user
        response = self.table.query(
            IndexName='GSI2',
            KeyConditionExpression=Key('GSI2PK').eq(f'USER#{user_id}')
        )
        
        # Get channel IDs and last_read timestamps
        channel_data = {
            item['GSI2SK'].split('#')[1]: item.get('last_read')
            for item in response['Items']
        }
        channel_ids = list(channel_data.keys())
        
        if not channel_ids:
            return []
            
        # Batch get channel metadata
        channels_data = []
        for i in range(0, len(channel_ids), 100):
            batch_ids = channel_ids[i:i+100]
            response = self.table.meta.client.batch_get_item(
                RequestItems={
                    self.table.name: {
                        'Keys': [
                            {
                                'PK': f'CHANNEL#{channel_id}',
                                'SK': '#METADATA'
                            }
                            for channel_id in batch_ids
                        ]
                    }
                }
            )
            if 'Responses' in response and self.table.name in response['Responses']:
                channels_data.extend(response['Responses'][self.table.name])
        
        # Get unread counts for each channel
        unread_counts = {}
        for channel_id in channel_ids:
            last_read = channel_data[channel_id]
            if last_read:
                # Query messages after last_read
                response = self.table.query(
                    IndexName='GSI1',
                    KeyConditionExpression=Key('GSI1PK').eq(f'CHANNEL#{channel_id}') & 
                                         Key('GSI1SK').gt(f'TS#{last_read}'),
                    Select='COUNT'
                )
                unread_counts[channel_id] = response['Count']
            else:
                # If no last_read, all messages are unread
                response = self.table.query(
                    IndexName='GSI1',
                    KeyConditionExpression=Key('GSI1PK').eq(f'CHANNEL#{channel_id}'),
                    Select='COUNT'
                )
                unread_counts[channel_id] = response['Count']
        
        # Process channels
        channels = []
        for item in channels_data:
            channel_data = self._clean_item(item)
            channel_id = channel_data['id']
            
            # Add unread count
            channel_data['unread_count'] = unread_counts.get(channel_id, 0)
            
            # Add members for DM channels
            if channel_data.get('type') == 'dm':
                channel_data['members'] = self.get_channel_members(channel_data['id'])
                
            channels.append(Channel(**channel_data))
            
        return channels

    def get_available_channels(self, user_id: str) -> List[Channel]:
        """Get public channels the user is not a member of."""
        # Query GSI2 for user's channel memberships (just need IDs)
        membership_response = self.table.query(
            IndexName='GSI2',
            KeyConditionExpression=Key('GSI2PK').eq(f'USER#{user_id}'),
            ProjectionExpression='GSI2SK'  # Only get channel IDs
        )
        
        # Query GSI1 for public channels
        public_response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('TYPE#public')
        )
        
        # Process results
        user_channel_ids = {item['GSI2SK'].split('#')[1] for item in membership_response['Items']}
        
        channels = []
        for item in public_response['Items']:
            channel_id = item['id']
            if channel_id not in user_channel_ids:
                channels.append(Channel(**self._clean_item(item)))
                
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
        # First check if channel exists
        channel = self.get_channel_by_id(channel_id)
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
        
        timestamp = self._now()
        item = {
            'PK': f'CHANNEL#{channel_id}',
            'SK': f'MEMBER#{user_id}',
            'GSI2PK': f'USER#{user_id}',
            'GSI2SK': f'CHANNEL#{channel_id}',
            'joined_at': timestamp,
            'last_read': timestamp
        }
        
        try:
            self.table.put_item(Item=item)
        except Exception as e:
            logging.error(f"Error adding channel member: {str(e)}")
            raise

    def get_channel_members(self, channel_id: str) -> List[dict]:
        """Get members of a channel"""
        # Get member records
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MEMBER#')
        )
        
        if not response['Items']:
            return []
            
        # Extract user IDs and batch get user data
        user_ids = [item['SK'].split('#')[1] for item in response['Items']]
        users = {
            user.id: user 
            for user in self.user_service._batch_get_users(user_ids)
        }
        
        # Process members
        members = []
        for item in response['Items']:
            user_id = item['SK'].split('#')[1]
            if user_id in users:
                user = users[user_id]
                members.append({
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'joined_at': item.get('joined_at'),
                    'last_read': item.get('last_read')
                })
                
        return members

    def get_channel_message_count(self, channel_id: str) -> int:
        """Get the number of messages in a channel."""
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq(f'CHANNEL#{channel_id}'),
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
        # Get existing member record
        if not self.is_channel_member(channel_id, user_id):
            raise ValueError("User is not a member")
            
        # Update the member's last_read timestamp while preserving other fields
        response = self.table.get_item(
            Key={
                'PK': f'CHANNEL#{channel_id}',
                'SK': f'MEMBER#{user_id}'
            }
        )
        item = response['Item']
        item['last_read'] = self._now()
        
        try:
            self.table.put_item(Item=item)
        except Exception as e:
            logging.error(f"Error marking channel as read: {str(e)}")
            raise
            
    def is_channel_member(self, channel_id: str, user_id: str) -> bool:
        """Check if a user is a member of a channel."""
        response = self.table.get_item(
            Key={
                'PK': f'CHANNEL#{channel_id}',
                'SK': f'MEMBER#{user_id}'
            }
        )
        return 'Item' in response 

    def get_channel_by_name(self, name: str) -> Optional[Channel]:
        """Get a channel by its name.
        
        Args:
            name: The name of the channel to retrieve
            
        Returns:
            Channel object if found, None otherwise
        """
        try:
            # Try each possible channel type in sequence
            for channel_type in ['public', 'private', 'dm']:
                print(f"  Looking for channel {name} with type {channel_type}...")
                response = self.table.query(
                    IndexName='GSI1',
                    KeyConditionExpression=Key('GSI1PK').eq(f'TYPE#{channel_type}') & 
                                         Key('GSI1SK').eq(f'NAME#{name}'),
                    Limit=1
                )
                
                if response['Items']:
                    item = response['Items'][0]
                    channel = self.get_channel_by_id(item['id'])
                    print(f"  ✓ Found channel {name} with type {channel_type}")
                    return channel
            
            print(f"  ✗ Could not find channel {name} with any type")
            return None
        except Exception as e:
            print(f"Error getting channel by name: {e}")
            return None 

    def get_workspace_channels(self, workspace_id: str, user_id: Optional[str] = None) -> List[Channel]:
        """Get all channels in a workspace, optionally including membership status for a specific user.
        
        Args:
            workspace_id: The ID of the workspace
            user_id: The ID of the user (optional)
            
        Returns:
            List of channels in the workspace, with optional membership status
        """
        logging.info(f'Querying channels for workspace_id: {workspace_id}, user_id: {user_id}')
        response = self.table.query(
            IndexName='GSI4',
            KeyConditionExpression=Key('GSI4PK').eq(f'WORKSPACE#{workspace_id}') & 
                                 Key('GSI4SK').begins_with('CHANNEL#')
        )
        
        
        channels = []
        for item in response['Items']:
            channel_data = self._clean_item(item)
            channel_id = channel_data['id']
            # Check if the user is a member of the channel, if user_id is provided
            if user_id:
                is_member = self.is_channel_member(channel_id, user_id)
                channel_data['is_member'] = is_member
            channels.append(Channel(**channel_data))
        print(channels)
        return channels

    def add_channel_to_workspace(self, channel_id: str, workspace_id: str) -> None:
        """Add a channel to a workspace.
        
        Args:
            channel_id: The ID of the channel
            workspace_id: The ID of the workspace
        """
        # First check if channel exists
        channel = self.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError("Channel not found")
            
        # Update both workspace_id and GSI4 index
        self.table.update_item(
            Key={
                'PK': f'CHANNEL#{channel_id}',
                'SK': '#METADATA'
            },
            UpdateExpression='SET workspace_id = :wid, GSI4PK = :workspace_pk, GSI4SK = :channel_sk',
            ExpressionAttributeValues={
                ':wid': workspace_id,
                ':workspace_pk': f'WORKSPACE#{workspace_id}',
                ':channel_sk': f'CHANNEL#{channel_id}'
            }
        )

    def find_channels_without_workspace(self) -> List[Channel]:
        """Find all channels that don't have a workspace assigned and assign them to NO_WORKSPACE.
        
        Returns:
            List of channels that were updated with NO_WORKSPACE
        """
        # Query all channels using GSI1 for public and private channels
        channels = []
        for channel_type in ['public', 'private']:
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq(f'TYPE#{channel_type}')
            )
            
            for item in response['Items']:
                if item['SK'] == '#METADATA' and (
                    'workspace_id' not in item or 
                    not item.get('workspace_id', '').strip()  # Handle both missing and empty workspace_id
                ):
                    # Update channel with NO_WORKSPACE
                    try:
                        self.table.update_item(
                            Key={
                                'PK': item['PK'],
                                'SK': '#METADATA'
                            },
                            UpdateExpression='SET workspace_id = :wid, GSI4PK = :wpk, GSI4SK = :csk',
                            ExpressionAttributeValues={
                                ':wid': 'NO_WORKSPACE',
                                ':wpk': 'WORKSPACE#NO_WORKSPACE',
                                ':csk': f'CHANNEL#{item["id"]}'
                            }
                        )
                        channels.append(Channel(**self._clean_item(item)))
                    except Exception as e:
                        logging.error(f"Error updating channel {item['id']}: {str(e)}")
                        
        return channels

    def assign_default_workspace_to_channels(self) -> int:
        """Find all channels without workspace and assign them to NO_WORKSPACE.
        This is now handled directly in find_channels_without_workspace.
        
        Returns:
            Number of channels updated
        """
        return len(self.find_channels_without_workspace()) 

    def create_workspace(self, name: str) -> Workspace:
        """Create a new workspace."""
        workspace_id = self._generate_id()
        timestamp = self._now()
        item = {
            'PK': f'WORKSPACE#{workspace_id}',
            'SK': '#METADATA',
            'id': workspace_id,
            'name': name,
            'created_at': timestamp
        }
        self.table.put_item(Item=item)
        return Workspace(id=workspace_id, name=name, created_at=timestamp)

    def get_workspace_by_id(self, workspace_id: str) -> Optional[Workspace]:
        """Get a workspace by its ID."""
        response = self.table.get_item(
            Key={
                'PK': f'WORKSPACE#{workspace_id}',
                'SK': '#METADATA'
            }
        )
        if 'Item' not in response:
            return None
        item = response['Item']
        return Workspace(id=item['id'], name=item['name'], created_at=item['created_at']) 

    def get_channel_name_by_id(self, channel_id: str) -> Optional[str]:
        """Retrieve the name of a channel given its ID."""
        channel = self.get_channel_by_id(channel_id)
        return channel.name if channel else None 