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
    user: Optional[dict] = None
    reactions: Dict[str, List[str]] = field(default_factory=dict)  # emoji -> list of user_ids

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
            'user': self.user,
            'reactions': self.reactions
        } 