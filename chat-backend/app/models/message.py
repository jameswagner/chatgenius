from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List

@dataclass
class Message:
    id: str
    content: str
    user_id: str
    channel_id: str
    created_at: str | datetime
    thread_id: Optional[str] = None
    edited_at: Optional[str] = None
    is_edited: bool = False
    version: int = 1
    reactions: Dict[str, List[str]] = field(default_factory=dict)
    attachments: List[str] = field(default_factory=list)
    reply_count: Optional[int] = 0
    user: Optional[dict] = None
    edit_history: List[Dict] = field(default_factory=list)
    replies: List[str] = field(default_factory=list)

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
            'editHistory': self.edit_history,
            'replies': self.replies,
            'replyCount': len(self.replies)
        } 