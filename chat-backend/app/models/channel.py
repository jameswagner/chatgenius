from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class Channel:
    id: str
    name: str
    type: str
    created_by: str
    created_at: str | datetime
    members: List[dict] = field(default_factory=list)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'createdBy': self.created_by,
            'createdAt': (self.created_at.strftime('%Y-%m-%d %H:%M:%S') 
                         if isinstance(self.created_at, datetime) 
                         else self.created_at),
            'members': self.members
        } 