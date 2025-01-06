import sqlite3
from typing import List, Optional
from datetime import datetime
import uuid
from ..models.user import User
from ..models.channel import Channel
from ..models.message import Message

class SQLiteDB:
    def __init__(self, db_path: str = "chat.db"):
        self.db_path = db_path
        self._init_db()
        
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE,
                    name TEXT,
                    password TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS channels (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    type TEXT CHECK(type IN ('public', 'private', 'dm')),
                    created_by TEXT REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    channel_id TEXT REFERENCES channels(id),
                    user_id TEXT REFERENCES users(id),
                    content TEXT,
                    thread_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create default channel if it doesn't exist
            row = conn.execute("SELECT id FROM channels WHERE name = 'general'").fetchone()
            if not row:
                channel_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO channels (id, name, type, created_by) VALUES (?, 'general', 'public', NULL)",
                    (channel_id,)
                )

    def create_user(self, email: str, name: str, password: str) -> User:
        user_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO users (id, email, name, password) VALUES (?, ?, ?, ?)",
                (user_id, email, name, password)
            )
        return self.get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
        return User(**dict(row)) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
        return User(**dict(row)) if row else None

    def get_channels_for_user(self, user_id: str) -> List[Channel]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM channels WHERE type = 'public' ORDER BY name ASC"
            ).fetchall()
            return [Channel(**dict(row)) for row in rows]

    def create_message(self, channel_id: str, user_id: str, content: str, thread_id: Optional[str] = None) -> Message:
        message_id = str(uuid.uuid4())
        # If no thread_id provided, message starts its own thread
        actual_thread_id = thread_id or message_id
        
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (id, channel_id, user_id, content, thread_id) VALUES (?, ?, ?, ?, ?)",
                (message_id, channel_id, user_id, content, actual_thread_id)
            )
            row = conn.execute("""
                SELECT m.*, u.name as user_name 
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.id
                WHERE m.id = ?
            """, (message_id,)).fetchone()
            data = dict(row)
            data['user'] = {'name': data.pop('user_name')}
            return Message(**data)

    def get_messages(self, channel_id: str) -> List[Message]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                WITH ThreadInfo AS (
                    SELECT thread_id, MIN(created_at) as thread_created_at
                    FROM messages 
                    GROUP BY thread_id
                )
                SELECT m.*, u.name as user_name
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.id
                LEFT JOIN ThreadInfo t ON m.thread_id = t.thread_id
                WHERE m.channel_id = ?
                ORDER BY t.thread_created_at ASC, m.created_at ASC
            """, (channel_id,)).fetchall()
            messages = []
            for row in rows:
                data = dict(row)
                data['user'] = {'name': data.pop('user_name')}
                messages.append(Message(**data))
            return messages

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT m.*, u.name as user_name
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.id
                WHERE m.thread_id = ?
                ORDER BY m.created_at ASC
            """, (thread_id,)).fetchall()
            messages = []
            for row in rows:
                data = dict(row)
                data['user'] = {'name': data.pop('user_name')}
                messages.append(Message(**data))
            return messages
