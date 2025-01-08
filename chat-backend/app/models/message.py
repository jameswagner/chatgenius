from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List

@dataclass
class Message:
    id: str
    content: str
    user_id: str
    channel_id: str
    thread_id: str
    created_at: str | datetime
    attachments: List[str] = field(default_factory=list)
    user: Optional[dict] = None
    reactions: Dict[str, List[str]] = field(default_factory=dict)
    edited_at: Optional[str | datetime] = None
    is_edited: bool = False
    edit_history: List[dict] = field(default_factory=list)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'userId': self.user_id,
            'channelId': self.channel_id,
            'threadId': self.thread_id,
            'createdAt': (self.created_at.strftime('%Y-%m-%d %H:%M:%S') 
                         if isinstance(self.created_at, datetime) 
                         else self.created_at),
            'attachments': self.attachments,
            'user': self.user.to_dict() if hasattr(self.user, 'to_dict') else self.user,
            'reactions': self.reactions,
            'editedAt': (self.edited_at.strftime('%Y-%m-%d %H:%M:%S')
                        if isinstance(self.edited_at, datetime)
                        else self.edited_at),
            'isEdited': self.is_edited,
            'editHistory': self.edit_history
        } 