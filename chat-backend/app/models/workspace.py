from typing import List
from datetime import datetime

class Workspace:
    def __init__(self, id: str, name: str, created_at: datetime, channels: List[str] = None, entity_type: str = 'WORKSPACE'):
        self.id = id
        self.name = name
        self.created_at = created_at
        self.channels = channels or []
        self.entity_type = entity_type

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at,
            'channels': self.channels,
            'entity_type': self.entity_type
        } 