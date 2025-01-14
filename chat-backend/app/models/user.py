from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class User:
    id: str
    email: str
    name: str
    type: str = 'user'  # 'user' or 'persona'
    status: str = 'offline'
    last_active: Optional[datetime] = None
    created_at: datetime = None
    password: Optional[str] = None  # Make password optional since we don't always need it
    role: Optional[str] = None  # Role for persona users
    bio: Optional[str] = None   # Bio for persona users

    def to_dict(self):
        # Convert string timestamps to datetime objects if needed
        if isinstance(self.last_active, str):
            try:
                self.last_active = datetime.fromisoformat(self.last_active.replace(' ', 'T'))
            except (ValueError, AttributeError):
                self.last_active = None

        if isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at.replace(' ', 'T'))
            except (ValueError, AttributeError):
                self.created_at = datetime.now()

        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'type': self.type,
            'status': self.status,
            'lastActive': self.last_active.isoformat() if self.last_active else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'role': self.role,
            'bio': self.bio
        } 