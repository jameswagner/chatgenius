from dataclasses import dataclass
from datetime import datetime

@dataclass
class User:
    id: str
    email: str
    name: str
    password: str  # This will be the hashed password
    created_at: datetime 