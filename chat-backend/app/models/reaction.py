from dataclasses import dataclass
from datetime import datetime

@dataclass
class Reaction:
    message_id: str
    user_id: str
    emoji: str
    created_at: datetime 