from typing import List, Optional
from datetime import datetime
from ..models.user import User
from ..models.channel import Channel
from ..models.message import Message
from ..models.reaction import Reaction

class Database:
    def create_user(self, email: str, name: str) -> User:
        raise NotImplementedError
        
    def get_user_by_email(self, email: str) -> Optional[User]:
        raise NotImplementedError
        
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        raise NotImplementedError
        
    def create_channel(self, name: str, type: str, created_by: str) -> Channel:
        raise NotImplementedError
        
    def get_channel(self, channel_id: str) -> Optional[Channel]:
        raise NotImplementedError
        
    def get_channels_for_user(self, user_id: str) -> List[Channel]:
        raise NotImplementedError
        
    def add_channel_member(self, channel_id: str, user_id: str) -> None:
        raise NotImplementedError
        
    def remove_channel_member(self, channel_id: str, user_id: str) -> None:
        raise NotImplementedError
        
    def create_message(self, channel_id: str, user_id: str, content: str, thread_id: Optional[str] = None) -> Message:
        raise NotImplementedError
        
    def get_messages(self, channel_id: str, limit: int = 50, before: Optional[datetime] = None) -> List[Message]:
        raise NotImplementedError
        
    def get_thread_messages(self, thread_id: str) -> List[Message]:
        raise NotImplementedError
        
    def add_reaction(self, message_id: str, user_id: str, emoji: str) -> Reaction:
        raise NotImplementedError
        
    def remove_reaction(self, message_id: str, user_id: str, emoji: str) -> None:
        raise NotImplementedError 