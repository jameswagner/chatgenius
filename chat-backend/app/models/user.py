from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class User:
    id: str
    email: str
    name: str
    password: str
    created_at: datetime
    status: str = 'offline'
    last_active: Optional[datetime] = None

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
            'status': self.status,
            'lastActive': self.last_active.isoformat() if self.last_active else None,
            'createdAt': self.created_at.isoformat()
        } 