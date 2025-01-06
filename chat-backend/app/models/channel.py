from dataclasses import dataclass, asdict
from datetime import datetime, timezone

@dataclass
class Channel:
    id: str
    name: str
    type: str
    created_by: str
    created_at: datetime

    def to_dict(self):
        data = asdict(self)
        # Handle datetime serialization
        if isinstance(self.created_at, str):
            dt = datetime.fromisoformat(self.created_at)
            data['created_at'] = dt.replace(tzinfo=timezone.utc).isoformat()
        else:
            data['created_at'] = self.created_at.replace(tzinfo=timezone.utc).isoformat()
        return data 