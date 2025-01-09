from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import boto3
from boto3.dynamodb.conditions import Key, Attr
from ..models.user import User
from ..models.channel import Channel
from ..models.message import Message
from ..models.reaction import Reaction

class DynamoDB:
    def __init__(self, table_name: str = "chat_app_jrw"):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        
    def _generate_id(self) -> str:
        return str(uuid.uuid4())
        
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    """
    Data Structure:
    
    Single Table Design with the following patterns:
    
    PK (Partition Key) | SK (Sort Key)     | GSI1PK          | GSI1SK           | Attributes
    -------------------------------------------------------------------------------
    USER#<id>         | #METADATA          | STATUS#<status> | TS#<timestamp>   | user data
    CHANNEL#<id>      | #METADATA          | TYPE#<type>     | NAME#<name>      | channel data
    CHANNEL#<id>      | MEMBER#<user_id>   | USER#<user_id>  | TS#<timestamp>   | member data
    CHANNEL#<id>      | MSG#<timestamp>    | USER#<user_id>  | THREAD#<id>      | message data
    MESSAGE#<id>      | REACTION#<user_id> | EMOJI#<emoji>   | TS#<timestamp>   | reaction data
    
    GSI1: Global Secondary Index for queries by status, type, etc.
    GSI2: Global Secondary Index for user's channels (USER#<id> | CHANNEL#<id>)
    GSI3: Global Secondary Index for message search (CONTENT#<word> | TS#<timestamp>)
    """

    def create_user(self, email: str, name: str, password: str) -> User:
        user_id = self._generate_id()
        timestamp = self._now()
        
        item = {
            'PK': f'USER#{user_id}',
            'SK': '#METADATA',
            'GSI1PK': 'STATUS#offline',
            'GSI1SK': f'TS#{timestamp}',
            'id': user_id,
            'email': email,
            'name': name,
            'password': password,
            'status': 'offline',
            'last_active': timestamp,
            'created_at': timestamp,
            'type': 'user'
        }
        
        self.table.put_item(Item=item)
        
        # Add user to general channel
        self.add_channel_member('general', user_id)
        
        return User(
            id=user_id,
            email=email,
            name=name,
            password=password,
            status='offline',
            last_active=timestamp,
            created_at=timestamp
        )

    def get_user_by_email(self, email: str) -> Optional[User]:
        response = self.table.scan(
            FilterExpression=Attr('email').eq(email) & Attr('type').eq('user')
        )
        
        if not response['Items']:
            return None
            
        item = response['Items'][0]
        return User(**self._clean_item(item))

    def update_user_status(self, user_id: str, status: str) -> Optional[User]:
        timestamp = self._now()
        
        # Update user status
        self.table.update_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': '#METADATA'
            },
            UpdateExpression='SET #status = :status, #last_active = :ts, GSI1PK = :gsi1pk',
            ExpressionAttributeNames={
                '#status': 'status',
                '#last_active': 'last_active'
            },
            ExpressionAttributeValues={
                ':status': status,
                ':ts': timestamp,
                ':gsi1pk': f'STATUS#{status}'
            }
        )
        
        return self.get_user_by_id(user_id) 

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        response = self.table.get_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': '#METADATA'
            }
        )
        
        if 'Item' not in response:
            return None
            
        item = response['Item']
        return User(**self._clean_item(item))

    def _clean_item(self, item: dict) -> dict:
        """Clean DynamoDB item for model creation"""
        cleaned = {}
        for key, value in item.items():
            # Skip DynamoDB system attributes
            if key in ['PK', 'SK', 'GSI1PK', 'GSI1SK', 'GSI2PK', 'GSI2SK']:
                continue
                
            # Only keep type field for channels
            if key == 'type' and not ('CHANNEL#' in item.get('PK', '') and '#METADATA' in item.get('SK', '')):
                continue
                
            # Keep all other fields
            cleaned[key] = value
            
        return cleaned

    def create_channel(self, name: str, type: str = 'public', created_by: str = None, other_user_id: str = None) -> Channel:
        channel_id = self._generate_id()
        timestamp = self._now()
        
        # For DM channels, use a consistent naming convention
        if type == 'dm' and other_user_id:
            user_ids = sorted([created_by, other_user_id])
            name = f"dm_{user_ids[0]}_{user_ids[1]}"
        
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
            
        # For DM channels, get the channel with members
        if type == 'dm':
            channel = Channel(**self._clean_item(item))
            channel.members = self.get_channel_members(channel_id)
            return channel
            
        return Channel(**self._clean_item(item))

    def add_channel_member(self, channel_id: str, user_id: str) -> None:
        timestamp = self._now()
        
        self.table.put_item(Item={
            'PK': f'CHANNEL#{channel_id}',
            'SK': f'MEMBER#{user_id}',
            'GSI2PK': f'USER#{user_id}',
            'GSI2SK': f'CHANNEL#{channel_id}',
            'joined_at': timestamp,
            'last_read': timestamp  # Initialize last_read
        })

    def mark_channel_read(self, channel_id: str, user_id: str) -> None:
        """Mark all current messages in a channel as read for a user"""
        timestamp = self._now()
        print(f"\n[DB] Marking channel {channel_id} as read for user {user_id} at {timestamp}")
        
        # Update the member's last_read timestamp
        self.table.update_item(
            Key={
                'PK': f'CHANNEL#{channel_id}',
                'SK': f'MEMBER#{user_id}'
            },
            UpdateExpression='SET last_read = :ts',
            ExpressionAttributeValues={
                ':ts': timestamp
            }
        )

    def get_channels_for_user(self, user_id: str) -> List[Channel]:
        print(f"\n[DB] Getting channels for user {user_id}")
        # Query GSI2 to get all channels for user
        response = self.table.query(
            IndexName='GSI2',
            KeyConditionExpression=Key('GSI2PK').eq(f'USER#{user_id}')
        )
        
        channel_ids = [item['GSI2SK'].split('#')[1] for item in response['Items']]
        
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
                print(f"\n[DB] Processing channel '{channel_data['name']}' ({channel_id})")
                
                # Get member data including last_read
                member_response = self.table.get_item(
                    Key={
                        'PK': f'CHANNEL#{channel_id}',
                        'SK': f'MEMBER#{user_id}'
                    }
                )
                
                last_read = None
                if 'Item' in member_response:
                    last_read = member_response['Item'].get('last_read')
                    print(f"[DB] Found last_read for channel '{channel_data['name']}': {last_read}")
                
                # Calculate unread count
                unread_count = 0
                if last_read:
                    # Query messages after last_read
                    messages_response = self.table.query(
                        KeyConditionExpression='PK = :pk AND SK > :last_read',
                        ExpressionAttributeValues={
                            ':pk': f'CHANNEL#{channel_id}',
                            ':last_read': f'MSG#{last_read}'
                        }
                    )
                    
                    # Only count messages from other users
                    unread_count = sum(1 for item in messages_response.get('Items', [])
                                     if item.get('userId') != user_id)
                    print(f"[DB] Channel '{channel_data['name']}' unread count: {unread_count}")
                    print(f"[DB] Messages after last_read in '{channel_data['name']}': {[item['SK'] for item in messages_response.get('Items', [])]}")
                else:
                    print(f"[DB] No last_read timestamp for channel '{channel_data['name']}'")
                
                # Get members if DM channel
                members = []
                if channel_data['type'] == 'dm':
                    members = self.get_channel_members(channel_id)
                
                channel = Channel(
                    id=channel_id,
                    name=channel_data['name'],
                    type=channel_data['type'],
                    created_by=channel_data['created_by'],
                    created_at=channel_data['created_at'],
                    members=members,
                    last_read=last_read,
                    unread_count=unread_count
                )
                channels.append(channel)
                
        print(f"\n[DB] Found {len(channels)} channels for user {user_id}: {[c.name for c in channels]}")
        return channels

    def create_message(self, channel_id: str, user_id: str, content: str, thread_id: str = None, attachments: List[str] = None) -> Message:
        """Create a new message"""
        message_id = self._generate_id()
        timestamp = self._now()
        
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

        self.table.put_item(Item=item)
        
        message = Message(**self._clean_item(item))
        user = self.get_user_by_id(user_id)
        if user:
            message.user = user
            
        return message

    def _get_message_reactions(self, message_id: str) -> dict:
        """Get reactions grouped by emoji with arrays of user IDs"""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'MESSAGE#{message_id}') & 
                                 Key('SK').begins_with('REACTION#')
        )
        
        # Group reactions by emoji
        reactions = {}
        for item in response['Items']:
            cleaned = self._clean_item(item)
            emoji = cleaned['emoji']
            user_id = cleaned['user_id']
            if emoji not in reactions:
                reactions[emoji] = []
            reactions[emoji].append(user_id)
            
        return reactions

    def get_message(self, message_id: str) -> Optional[Message]:
        response = self.table.scan(
            FilterExpression=Attr('id').eq(message_id) & 
                           Attr('SK').begins_with('MSG#')
        )
        
        if not response['Items']:
            return None
            
        item = self._clean_item(response['Items'][0])
        # Add reactions to the message
        item['reactions'] = self._get_message_reactions(message_id)
        return Message(**item)

    def get_messages(self, channel_id: str, before: str = None, limit: int = 50) -> List[Message]:
        print(f"\n[DB] Getting messages for channel {channel_id}")
        query_params = {
            'KeyConditionExpression': Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                    Key('SK').begins_with('MSG#'),
            'Limit': limit,
            'ScanIndexForward': True  # Changed to True for ascending order (oldest first)
        }
        
        if before:
            query_params['ExclusiveStartKey'] = {
                'PK': f'CHANNEL#{channel_id}',
                'SK': f'MSG#{before}'
            }
            
        response = self.table.query(**query_params)
        print(f"[DB] Raw DynamoDB response: {len(response['Items'])} messages")
        print("[DB] First few SK values:", [item['SK'] for item in response['Items'][:3]])
        
        messages = []
        for item in response['Items']:
            cleaned = self._clean_item(item)
            
            cleaned['reactions'] = self._get_message_reactions(cleaned['id'])
            message = Message(**cleaned)
            user = self.get_user_by_id(message.user_id)
            if user:
                message.user = user
            messages.append(message)
        
        return messages

    def add_reaction(self, message_id: str, user_id: str, emoji: str) -> Reaction:
        timestamp = self._now()
        
        item = {
            'PK': f'MESSAGE#{message_id}',
            'SK': f'REACTION#{user_id}#{emoji}',
            'GSI1PK': f'EMOJI#{emoji}',
            'GSI1SK': f'TS#{timestamp}',
            'message_id': message_id,
            'user_id': user_id,
            'emoji': emoji,
            'created_at': timestamp
        }
        
        self.table.put_item(Item=item)
        return Reaction(**self._clean_item(item))

    def search_messages(self, user_id: str, query: str) -> List[Message]:
        # Get user's channels
        channels = self.get_channels_for_user(user_id)
        channel_ids = [channel.id for channel in channels]
        
        # Search for messages containing the query word
        word = query.lower()
        response = self.table.query(
            IndexName='GSI3',
            KeyConditionExpression=Key('GSI3PK').eq(f'CONTENT#{word}'),
            ScanIndexForward=False  # Latest first
        )
        
        message_ids = [item['message_id'] for item in response['Items']]
        messages = []
        
        # Get full message details and filter by user's channels
        for message_id in message_ids:
            message = self.get_message(message_id)
            if message and message.channel_id in channel_ids:
                user = self.get_user_by_id(message.user_id)
                if user:
                    message.user = user
                messages.append(message)
                
        return messages[:50]  # Limit results 

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        # Scan for messages in thread (could be optimized with a GSI)
        response = self.table.scan(
            FilterExpression=Attr('thread_id').eq(thread_id)
        )
        
        messages = [Message(**self._clean_item(item)) for item in response['Items']]
        
        # Fetch user info
        for message in messages:
            user = self.get_user_by_id(message.user_id)
            if user:
                message.user = user
                
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

    def get_all_users(self) -> List[Dict]:
        """Get all users except password field"""
        response = self.table.scan(
            FilterExpression=Attr('type').eq('user')
        )
        
        # Clean items and only return necessary fields
        return [{
            'id': self._clean_item(item)['id'],
            'name': self._clean_item(item)['name']
        } for item in response['Items']]

    def get_available_channels(self, user_id: str) -> List[Channel]:
        # Get public channels
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('TYPE#public')
        )
        
        # Filter out channels user is already member of
        user_channels = self.get_channels_for_user(user_id)
        user_channel_ids = {c.id for c in user_channels}
        
        channels = []
        for item in response['Items']:
            cleaned = self._clean_item(item)
            if cleaned['id'] not in user_channel_ids:
                channels.append(Channel(**cleaned))
        return channels

    def get_dm_channel(self, user1_id: str, user2_id: str) -> Optional[Channel]:
        user_ids = sorted([user1_id, user2_id])
        dm_name = f"dm_{user_ids[0]}_{user_ids[1]}"
        
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('TYPE#dm') & 
                                 Key('GSI1SK').eq(f'NAME#{dm_name}')
        )
        
        if not response['Items']:
            return None
            
        return Channel(**self._clean_item(response['Items'][0]))

    def get_channel_by_id(self, channel_id: str) -> Optional[Channel]:
        """Get a channel by its ID"""
        response = self.table.get_item(
            Key={
                'PK': f'CHANNEL#{channel_id}',
                'SK': '#METADATA'
            }
        )
        
        if 'Item' not in response:
            return None
            
        return Channel(**self._clean_item(response['Item'])) 

    def get_channel_message_count(self, channel_id: str) -> int:
        """Get the number of messages in a channel"""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MSG#'),
            Select='COUNT'  # Only return the count, not the items
        )
        
        count = response.get('Count', 0)
        print(f"[DB] Message count for channel {channel_id}: {count}")
        return count

    def get_other_dm_user(self, channel_id: str, current_user_id: str) -> Optional[str]:
        """Get the other user's ID in a DM channel"""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MEMBER#')
        )
        
        for item in response['Items']:
            member_id = item['SK'].split('#')[1]
            if member_id != current_user_id:
                print(f"[DB] Found other user {member_id} in channel {channel_id}")
                return member_id
                
        print(f"[DB] No other user found in channel {channel_id}")
        return None 

    def get_channel_members(self, channel_id: str) -> List[dict]:
        """Get members of a channel"""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MEMBER#')
        )
        
        members = []
        for item in response['Items']:
            user_id = item['SK'].split('#')[1]
            user = self.get_user_by_id(user_id)
            if user:
                members.append({
                    'id': user.id,
                    'name': user.name
                })
                
        return members 

    def update_message(self, message_id: str, content: str) -> Message:
        """Update a message's content and maintain edit history"""
        timestamp = self._now()
        
        # First get the message to get its channel_id and created_at
        message = self.get_message(message_id)
        if not message:
            raise ValueError("Message not found")
            
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
            user = self.get_user_by_id(updated_message.user_id)
            if user:
                updated_message.user = user
                
        return updated_message 