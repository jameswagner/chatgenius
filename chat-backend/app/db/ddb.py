from typing import Optional, List, Dict, Set
from datetime import datetime, timezone
import uuid
import boto3
from boto3.dynamodb.conditions import Key, Attr
from ..models.user import User
from ..models.channel import Channel
from ..models.message import Message
from ..models.reaction import Reaction
from ..services.user_service import UserService

class DynamoDB:
    def __init__(self, table_name: str = "chat_app_jrw"):
        """Initialize DynamoDB connection and create table if needed
        
        Table Structure:
        - Users: 
            PK=USER#{id} SK=#METADATA
            GSI1PK=TYPE#user GSI1SK=NAME#{name}
            
        - Channels:
            PK=CHANNEL#{id} SK=#METADATA
            GSI1PK=TYPE#{type} GSI1SK=NAME#{name}
            
        - Channel Members:
            PK=CHANNEL#{channel_id} SK=MEMBER#{user_id}
            
        - Messages:
            PK=CHANNEL#{channel_id} SK=MSG#{timestamp}#{id}
            GSI1PK=USER#{user_id} GSI1SK=TS#{timestamp}
            Attributes:
                - reactions: Map<emoji, List<user_id>>
                - thread_id: Optional[str]
                - attachments: Optional[List[str]]
                
        - Search Index:
            PK=WORD#{word} SK=MESSAGE#{message_id}
            GSI3PK=CONTENT#{word} GSI3SK=TS#{timestamp}
        """
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.user_service = UserService(table_name)
        
        # Ensure general channel exists
        try:
            response = self.table.get_item(
                Key={
                    'PK': 'CHANNEL#general',
                    'SK': '#METADATA'
                }
            )
            
            if 'Item' not in response:
                # Create general channel
                timestamp = self._now()
                self.table.put_item(
                    Item={
                        'PK': 'CHANNEL#general',
                        'SK': '#METADATA',
                        'GSI1PK': 'TYPE#public',
                        'GSI1SK': 'NAME#general',
                        'id': 'general',
                        'name': 'general',
                        'type': 'public',
                        'created_by': 'system',
                        'created_at': timestamp,
                        'members': []
                    }
                )
                print("Created general channel")
        except Exception as e:
            print(f"Error checking/creating general channel: {e}")
        
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

    def create_user(self, email: str, name: str, password: str, type: str = 'user') -> User:
        return self.user_service.create_user(email, name, password, type)

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.user_service.get_user_by_email(email)

    def update_user_status(self, user_id: str, status: str) -> Optional[User]:
        return self.user_service.update_user_status(user_id, status)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.user_service.get_user_by_id(user_id)

    def get_all_users(self) -> List[Dict]:
        return self.user_service.get_all_users()

    def get_persona_users(self) -> List[User]:
        return self.user_service.get_persona_users()

    def _batch_get_users(self, user_ids: Set[str]) -> List[User]:
        return self.user_service._batch_get_users(user_ids)

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
        print(f"\n=== Adding user {user_id} to channel {channel_id} ===")
        timestamp = self._now()
        
        # First check if channel exists
        channel = self.get_channel_by_id(channel_id)
        print(f"Channel exists check: {channel is not None}")
        
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

    def mark_channel_read(self, channel_id: str, user_id: str) -> None:
        """Mark all current messages in a channel as read for a user"""
        timestamp = self._now()
        
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

    def create_message(self, channel_id: str, user_id: str, content: str, thread_id: str = None, attachments: List[str] = None) -> Message:
        """Create a new message"""
        print(f"\n=== Creating message ===")
        print(f"Channel: {channel_id}")
        print(f"User: {user_id}")
        print(f"Content: {content}")
        print(f"Thread: {thread_id}")
        print(f"Attachments: {attachments}")
        
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
        user = self.get_user_by_id(user_id)
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
        return Message(**item)

    def get_messages(self, channel_id: str, before: str = None, limit: int = 50) -> List[Message]:
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
        users = {user.id: user for user in self._batch_get_users(user_ids)}
        
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

    def search_messages(self, user_id: str, query: str) -> List[Message]:
        print(f"\n=== Searching messages for query: '{query}' ===")
        # Get user's channels
        channels = self.get_channels_for_user(user_id)
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
                user = self.get_user_by_id(message.user_id)
                if user:
                    message.user = user
                messages.append(message)
                print(f"Added message {message_id} to results")
                
        print(f"Returning {len(messages)} messages")
        return messages[:50]  # Limit results

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        response = self.table.scan(
            FilterExpression=Attr('thread_id').eq(thread_id)
        )
        
        # Get all unique user IDs first
        user_ids = set(item['user_id'] for item in response['Items'])
        users = {user.id: user for user in self._batch_get_users(user_ids)}
        
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

    def get_available_channels(self, user_id: str) -> List[Channel]:
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

    def get_channel_message_count(self, channel_id: str) -> int:
        """Get the number of messages in a channel"""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MSG#'),
            Select='COUNT'  # Only return the count, not the items
        )
        
        count = response.get('Count', 0)
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
                return member_id
                
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

    def get_channel_messages(self, channel_id: str) -> List[Message]:
        print(f"\n=== Getting messages for channel: {channel_id} ===")
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & Key('SK').begins_with('MESSAGE#')
            )
            
            messages = []
            for item in response['Items']:
                message = Message(
                    id=item['id'],
                    channel_id=channel_id,
                    user_id=item['user_id'],
                    content=item['content'],
                    created_at=item['created_at'],
                    thread_id=item.get('thread_id'),
                    reactions=self._get_message_reactions(item['id']),
                    attachments=item.get('attachments', [])
                )
                messages.append(message)
            
            print(f"Found {len(messages)} messages")
            return messages
        except Exception as e:
            print(f"Error getting channel messages: {str(e)}")
            raise 