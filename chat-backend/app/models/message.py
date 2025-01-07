from dataclasses import dataclass
from datetime import datetime

@dataclass
class Message:
    id: str
    content: str
    user_id: str
    channel_id: str
    thread_id: str
    created_at: str  # Just a string
    user: dict | None = None

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'userId': self.user_id,
            'channelId': self.channel_id,
            'threadId': self.thread_id,
            'createdAt': self.created_at,  # Pass through the UTC string
            'user': self.user
        } 