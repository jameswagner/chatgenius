from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict

@dataclass
class Channel:
    id: str
    name: str
    type: str
    created_by: str
    created_at: str | datetime
    members: List[dict] = field(default_factory=list)
    last_read: Optional[str] = None  # Last read timestamp for current user
    unread_count: int = 0  # Unread count for current user

    def to_dict(self, current_user_id=None):
        """Format channel data for output"""
        data = {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'createdBy': self.created_by,
            'createdAt': self.created_at,
            'members': self.members,
            'lastRead': self.last_read,
            'unreadCount': self.unread_count
        }
        return data 