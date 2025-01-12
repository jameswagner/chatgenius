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
from ..services.channel_service import ChannelService
from ..services.message_service import MessageService
from ..services.search_service import SearchService
import os

class DynamoDB:
    def __init__(self, table_name: str = None):
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
        self.table_name = table_name or os.getenv('DYNAMODB_TABLE')
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(self.table_name)
        self.user_service = UserService(table_name)
        self.channel_service = ChannelService(table_name)
        self.message_service = MessageService(table_name)
        self.search_service = SearchService(table_name)
        
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
    
    def create_channel(self, name: str, type: str = 'public', created_by: str = None, other_user_id: str = None) -> Channel:
        return self.channel_service.create_channel(name, type, created_by, other_user_id)

    def add_channel_member(self, channel_id: str, user_id: str) -> None:
        return self.channel_service.add_channel_member(channel_id, user_id)

    def mark_channel_read(self, channel_id: str, user_id: str) -> None:
        """Mark a channel as read for a user."""
        return self.channel_service.mark_channel_read(channel_id, user_id)

    def get_channels_for_user(self, user_id: str) -> List[Channel]:
        return self.channel_service.get_channels_for_user(user_id)
    
    def get_available_channels(self, user_id: str) -> List[Channel]:
        return self.channel_service.get_available_channels(user_id)

    def get_dm_channel(self, user1_id: str, user2_id: str) -> Optional[Channel]:
        return self.channel_service.get_dm_channel(user1_id, user2_id)

    def get_channel_by_id(self, channel_id: str) -> Optional[Channel]:
        return self.channel_service.get_channel_by_id(channel_id)

    def get_channel_message_count(self, channel_id: str) -> int:
        return self.channel_service.get_channel_message_count(channel_id)

    def get_other_dm_user(self, channel_id: str, user_id: str) -> Optional[str]:
        """Get the other user's ID in a DM channel"""
        return self.channel_service.get_other_dm_user(channel_id, user_id)

    def get_channel_members(self, channel_id: str) -> List[dict]:
        """Get members of a channel"""
        return self.channel_service.get_channel_members(channel_id)


    def create_message(self, channel_id: str, user_id: str, content: str, thread_id: str = None, attachments: List[str] = None) -> Message:
        """Create a new message"""
        return self.message_service.create_message(channel_id, user_id, content, thread_id, attachments)

    def get_message(self, message_id: str) -> Optional[Message]:
        return self.message_service.get_message(message_id)

    def get_messages(self, channel_id: str, before: str = None, limit: int = 50) -> List[Message]:
        return self.message_service.get_messages(channel_id, before, limit)

    def add_reaction(self, message_id: str, user_id: str, emoji: str) -> Reaction:
        return self.message_service.add_reaction(message_id, user_id, emoji)

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        return self.message_service.get_thread_messages(thread_id)

    def get_message_reactions(self, message_id: str) -> List[Reaction]:
        return self.message_service.get_message_reactions(message_id)

    def remove_reaction(self, message_id: str, user_id: str, emoji: str) -> None:
        return self.message_service.remove_reaction(message_id, user_id, emoji)

    def update_message(self, message_id: str, content: str) -> Message:
        return self.message_service.update_message(message_id, content)

    def search_messages(self, user_id: str, query: str) -> List[Message]:
        return self.search_service.search_messages(user_id, query)

    def is_channel_member(self, channel_id: str, user_id: str) -> bool:
        """Check if a user is a member of a channel."""
        return self.channel_service.is_channel_member(channel_id, user_id)
