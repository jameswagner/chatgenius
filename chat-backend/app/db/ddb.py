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
from ..services.workspace_service import WorkspaceService
from ..models.workspace import Workspace
import os

class DynamoDB:
    def __init__(self, table_name: str = None):
        """Initialize DynamoDB connection and create table if needed
        
        Table Structure:
        - Users: 
            PK=USER#{id} SK=#METADATA
            GSI1PK=TYPE#{type} GSI1SK=NAME#{name}
            GSI2PK=EMAIL#{email} GSI2SK=#METADATA
            GSI4PK=NAME#{name} GSI4SK=#METADATA  # For username uniqueness and lookup
            
        - Channels:
            PK=CHANNEL#{id} SK=#METADATA
            GSI1PK=TYPE#{type} GSI1SK=NAME#{name}
            GSI4PK=WORKSPACE#{workspace_id} GSI4SK=CHANNEL#{channel_id}  # For workspace channel membership
            
        - Channel Members:
            PK=CHANNEL#{channel_id} SK=MEMBER#{user_id}
            GSI2PK=USER#{user_id} GSI2SK=CHANNEL#{channel_id}
            
        - Messages (Parent):
            PK=MSG#{message_id} SK=MSG#{message_id}
            GSI1PK=CHANNEL#{channel_id} GSI1SK=TS#{timestamp}
            GSI2PK=USER#{user_id} GSI2SK=TS#{timestamp}
            Attributes:
                - reactions: Map<emoji, List<user_id>>
                - attachments: Optional[List[str]]
                
        - Messages (Replies):
            PK=MSG#{thread_id} SK=REPLY#{message_id}
            GSI1PK=CHANNEL#{channel_id} GSI1SK=TS#{timestamp}
            GSI2PK=USER#{user_id} GSI2SK=TS#{timestamp}
            Attributes:
                - reactions: Map<emoji, List<user_id>>
                - thread_id: str  # Parent message ID
                - attachments: Optional[List[str]]
                
        - Search Index:
            PK=WORD#{word} SK=MESSAGE#{message_id}
            GSI3PK=CONTENT#{word} GSI3SK=TS#{timestamp}
            
        Access Patterns:
        - Get channel messages: Query GSI1 (CHANNEL#{id})
        - Get thread messages: Query PK=MSG#{thread_id}, SK begins_with REPLY#
        - Get user's messages: Query GSI2 (USER#{id})
        - Search messages: Query GSI3 (CONTENT#{word})
        - Get user by username: Query GSI4 (NAME#{name})
        """
        self.table_name = table_name or os.getenv('DYNAMODB_TABLE', 'chat_app_jrw')
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        self.table = self.dynamodb.Table(self.table_name)
        self.user_service = UserService(table_name)
        self.channel_service = ChannelService(table_name)
        self.message_service = MessageService(table_name)
        self.search_service = SearchService(table_name)
        self.workspace_service = WorkspaceService(table_name)
        
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

    def get_message(self, message_id: str, thread_id: Optional[str] = None) -> Optional[Message]:
        """Get a message by ID. If thread_id is provided, the message is retrieved as a reply in that thread."""
        return self.message_service.get_message(message_id, thread_id)

    def get_messages(self, channel_id: str, limit: int = 50, start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[Message]:
        return self.message_service.get_messages(channel_id, limit, start_time=start_time, end_time=end_time)

    def get_user_messages(self, user_id: str, before: str = None, limit: int = 50) -> List[Message]:
        """Get messages created by a user."""
        return self.message_service.get_user_messages(user_id, before, limit)

    def add_reaction(self, message_id: str, user_id: str, emoji: str, thread_id: Optional[str] = None) -> Reaction:
        return self.message_service.add_reaction(message_id, user_id, emoji, thread_id)

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        return self.message_service.get_thread_messages(thread_id)

    def get_message_reactions(self, message_id: str) -> List[Reaction]:
        return self.message_service.get_message_reactions(message_id)

    def remove_reaction(self, message_id: str, user_id: str, emoji: str, thread_id: Optional[str] = None) -> None:
        return self.message_service.remove_reaction(message_id, user_id, emoji, thread_id)

    def update_message(self, message_id: str, content: str) -> Message:
        return self.message_service.update_message(message_id, content)

    def search_messages(self, user_id: str, query: str) -> List[Message]:
        return self.search_service.search_messages(user_id, query)

    def is_channel_member(self, channel_id: str, user_id: str) -> bool:
        """Check if a user is a member of a channel."""
        return self.channel_service.is_channel_member(channel_id, user_id)

    def get_user_by_name(self, name: str) -> Optional[User]:
        """Get a user by their username."""
        return self.user_service.get_user_by_name(name)

    def get_workspace_channels(self, workspace_id: str, user_id: str) -> List[Channel]:
        """Get all channels in a workspace.
        
        Args:
            workspace_id: The ID of the workspace
            
        Returns:
            List of channels in the workspace
        """
        return self.channel_service.get_workspace_channels(workspace_id, user_id)

    def find_channels_without_workspace(self) -> List[Channel]:
        """Find all channels that don't have a workspace assigned and assign them to NO_WORKSPACE.
        
        Returns:
            List of channels that were updated with NO_WORKSPACE
        """
        return self.channel_service.find_channels_without_workspace()

    def add_channel_to_workspace(self, channel_id: str, workspace_id: str) -> None:
        """Add a channel to a workspace.
        
        Args:
            channel_id: The ID of the channel
            workspace_id: The ID of the workspace
        """
        self.channel_service.add_channel_to_workspace(channel_id, workspace_id)

    def get_all_workspaces(self) -> List[Workspace]:
        return self.workspace_service.get_all_workspaces()

    def create_workspace(self, name: str) -> Workspace:
        return self.workspace_service.create_workspace(name)

    def get_workspace_by_id(self, workspace_id: str) -> Optional[Workspace]:
        return self.workspace_service.get_workspace_by_id(workspace_id)
