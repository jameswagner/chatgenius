from dataclasses import dataclass
from typing import Optional

@dataclass
class UserProfile:
    user_id: str
    profile_id: str
    entity_type: str = 'USER_PROFILE'
    text: Optional[str] = None
    last_message_timestamp_epoch: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'profile_id': self.profile_id,
            'entity_type': self.entity_type,
            'text': self.text,
            'last_message_timestamp_epoch': self.last_message_timestamp_epoch
        } 