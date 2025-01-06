from dataclasses import dataclass
from datetime import datetime

@dataclass
class Message:
    id: str
    content: str
    user_id: str
    channel_id: str
    thread_id: str
    created_at: datetime
    user: dict | None = None

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'userId': self.user_id,
            'channelId': self.channel_id,
            'threadId': self.thread_id,
            'createdAt': self.created_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ') if isinstance(self.created_at, datetime) else self.created_at,
            'user': self.user
        } 