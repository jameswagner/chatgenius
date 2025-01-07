from dataclasses import dataclass
from datetime import datetime

@dataclass
class Reaction:
    message_id: str
    user_id: str
    emoji: str
    created_at: str | datetime

    def to_dict(self):
        return {
            'messageId': self.message_id,
            'userId': self.user_id,
            'emoji': self.emoji,
            'createdAt': (self.created_at.strftime('%Y-%m-%d %H:%M:%S') 
                         if isinstance(self.created_at, datetime) 
                         else self.created_at)
        } 