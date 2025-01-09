import sqlite3
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from ..models.user import User
from ..models.channel import Channel
from ..models.message import Message
from ..models.reaction import Reaction

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
                    status TEXT DEFAULT 'offline' CHECK(status IN ('online', 'away', 'busy', 'offline')),
                    last_active TIMESTAMP,
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
                    created_at TIMESTAMP DEFAULT (datetime('now'))
                );
                
                CREATE TABLE IF NOT EXISTS channel_members (
                    channel_id TEXT REFERENCES channels(id),
                    user_id TEXT REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (channel_id, user_id)
                );
                
                CREATE TABLE IF NOT EXISTS reactions (
                    message_id TEXT REFERENCES messages(id),
                    user_id TEXT REFERENCES users(id),
                    emoji TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (message_id, user_id, emoji)
                );
                
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    message_id TEXT REFERENCES messages(id),
                    filename TEXT NOT NULL,
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

            # Add all users to general channel
            general = conn.execute("SELECT id FROM channels WHERE name = 'general'").fetchone()
            if general:
                users = conn.execute("SELECT id FROM users").fetchall()
                for user in users:
                    try:
                        conn.execute(
                            "INSERT INTO channel_members (channel_id, user_id) VALUES (?, ?)",
                            (general['id'], user['id'])
                        )
                    except sqlite3.IntegrityError:
                        pass  # User already in channel

    def create_user(self, email: str, name: str, password: str) -> User:
        user_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO users (id, email, name, password) VALUES (?, ?, ?, ?)",
                (user_id, email, name, password)
            )
            # Add new user to general channel
            general = conn.execute("SELECT id FROM channels WHERE name = 'general'").fetchone()
            if general:
                try:
                    conn.execute(
                        "INSERT INTO channel_members (channel_id, user_id) VALUES (?, ?)",
                        (general['id'], user_id)
                    )
                except sqlite3.IntegrityError:
                    pass  # User already in channel
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
            rows = conn.execute("""
                SELECT DISTINCT c.*, 
                       GROUP_CONCAT(DISTINCT cm2.user_id) as member_ids,
                       GROUP_CONCAT(DISTINCT u2.name) as member_names
                FROM channels c
                LEFT JOIN channel_members cm ON c.id = cm.channel_id
                LEFT JOIN channel_members cm2 ON c.id = cm2.channel_id
                LEFT JOIN users u2 ON cm2.user_id = u2.id
                WHERE (cm.user_id = ? OR c.name = 'general')
                GROUP BY c.id
                ORDER BY c.name ASC
            """, (user_id,)).fetchall()
            
            channels = []
            for row in rows:
                data = dict(row)
                # Add members info
                member_ids = data.pop('member_ids', '').split(',') if data.get('member_ids') else []
                member_names = data.pop('member_names', '').split(',') if data.get('member_names') else []
                data['members'] = [
                    {'id': uid, 'name': name} 
                    for uid, name in zip(member_ids, member_names)
                    if uid and name  # Filter out empty values
                ]
                
                channels.append(Channel(**data))
            return channels

    def create_message(self, channel_id: str, user_id: str, content: str, thread_id: str = None, attachments: List[str] = None) -> Message:
        """Create a new message"""
        timestamp = datetime.utcnow().isoformat()
        message_id = str(uuid.uuid4())
        
        # Save message
        self._get_connection().execute('''
            INSERT INTO messages (id, channel_id, user_id, content, thread_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (message_id, channel_id, user_id, content, thread_id, timestamp))
        
        # Save attachments if any
        if attachments:
            for attachment in attachments:
                self._get_connection().execute('''
                    INSERT INTO attachments (id, message_id, filename)
                    VALUES (?, ?, ?)
                ''', (str(uuid.uuid4()), message_id, attachment))
        
        self._get_connection().commit()
        
        # Get message data
        data = {
            'id': message_id,
            'channel_id': channel_id,
            'user_id': user_id,
            'content': content,
            'thread_id': thread_id,
            'created_at': timestamp,
            'attachments': attachments or []
        }
        
        message = Message(**data)
        user = self.get_user_by_id(user_id)
        if user:
            message.user = user
            
        return message

    def get_messages(self, channel_id: str) -> List[Message]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT m.*, u.name as user_name, u.status as user_status,
                       GROUP_CONCAT(a.filename) as attachment_files
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.id
                LEFT JOIN attachments a ON m.id = a.message_id
                WHERE m.channel_id = ?
                GROUP BY m.id
                ORDER BY m.created_at ASC
            """, (channel_id,)).fetchall()
            messages = []
            for row in rows:
                data = dict(row)
                data['user'] = {
                    'name': data.pop('user_name'),
                    'status': data.pop('user_status', 'offline')
                }
                # Add attachments
                data['attachments'] = (data.pop('attachment_files') or '').split(',')
                if data['attachments'] == ['']: data['attachments'] = []
                # Add reactions
                data['reactions'] = self.get_message_reactions(data['id'])
                messages.append(Message(**data))
            return messages

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT m.*, u.name as user_name, u.status as user_status,
                       GROUP_CONCAT(a.filename) as attachment_files
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.id
                LEFT JOIN attachments a ON m.id = a.message_id
                WHERE m.thread_id = ? AND m.id != ?
                GROUP BY m.id
                ORDER BY m.created_at ASC
            """, (thread_id, thread_id)).fetchall()
            messages = []
            for row in rows:
                data = dict(row)
                data['user'] = {
                    'name': data.pop('user_name'),
                    'status': data.pop('user_status', 'offline')
                }
                # Add attachments
                data['attachments'] = (data.pop('attachment_files') or '').split(',')
                if data['attachments'] == ['']: data['attachments'] = []
                # Add reactions
                data['reactions'] = self.get_message_reactions(data['id'])
                messages.append(Message(**data))
            return messages

    def get_message(self, message_id: str) -> Message:
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT m.*, u.name as user_name, u.status as user_status,
                       GROUP_CONCAT(a.filename) as attachment_files
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.id
                LEFT JOIN attachments a ON m.id = a.message_id
                WHERE m.id = ?
                GROUP BY m.id
            """, (message_id,)).fetchone()
            data = dict(row)
            data['user'] = {
                'name': data.pop('user_name'),
                'status': data.pop('user_status', 'offline')
            }
            # Add attachments
            data['attachments'] = (data.pop('attachment_files') or '').split(',')
            if data['attachments'] == ['']: data['attachments'] = []
            # Add reactions
            data['reactions'] = self.get_message_reactions(message_id)
            return Message(**data)

    def create_channel(self, name: str, type: str = 'public', created_by: str = None, other_user_id: str = None) -> Channel:
        channel_id = str(uuid.uuid4())
        
        with self._get_connection() as conn:
            try:
                print(f"Creating channel with type: {type}")  # Debug log
                conn.execute(
                    "INSERT INTO channels (id, name, type, created_by) VALUES (?, ?, ?, ?)",
                    (channel_id, name, type, created_by)
                )
                # Auto-join creator to channel
                if created_by:
                    conn.execute(
                        "INSERT INTO channel_members (channel_id, user_id) VALUES (?, ?)",
                        (channel_id, created_by)
                    )
                    
                # For DM channels, add the other user
                if type == 'dm' and other_user_id:
                    conn.execute(
                        "INSERT INTO channel_members (channel_id, user_id) VALUES (?, ?)",
                        (channel_id, other_user_id)
                    )

                row = conn.execute(
                    "SELECT * FROM channels WHERE id = ?", 
                    (channel_id,)
                ).fetchone()
                return Channel(**dict(row))
            except sqlite3.IntegrityError:
                raise ValueError(f"Channel name '{name}' already exists")

    def add_channel_member(self, channel_id: str, user_id: str) -> None:
        with self._get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO channel_members (channel_id, user_id) VALUES (?, ?)",
                    (channel_id, user_id)
                )
            except sqlite3.IntegrityError:
                raise ValueError("User is already a member of this channel")

    def remove_channel_member(self, channel_id: str, user_id: str) -> None:
        with self._get_connection() as conn:
            result = conn.execute(
                "DELETE FROM channel_members WHERE channel_id = ? AND user_id = ?",
                (channel_id, user_id)
            )
            if result.rowcount == 0:
                raise ValueError("User is not a member of this channel")

    def get_available_channels(self, user_id: str) -> List[Channel]:
        """Get all public channels that the user hasn't joined yet"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT c.* FROM channels c
                WHERE c.type = 'public'
                AND c.id NOT IN (
                    SELECT channel_id 
                    FROM channel_members 
                    WHERE user_id = ?
                )
                AND c.name != 'general'
                ORDER BY c.name ASC
            """, (user_id,)).fetchall()
            return [Channel(**dict(row)) for row in rows]

    def add_reaction(self, message_id: str, user_id: str, emoji: str) -> Reaction:
        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO reactions (message_id, user_id, emoji, created_at) 
                    VALUES (?, ?, ?, strftime('%Y-%m-%d %H:%M:%S', 'now', 'utc'))
                    """,
                    (message_id, user_id, emoji)
                )
                
                row = conn.execute(
                    "SELECT * FROM reactions WHERE message_id = ? AND user_id = ? AND emoji = ?",
                    (message_id, user_id, emoji)
                ).fetchone()
                
                return Reaction(**dict(row))
                
            except sqlite3.IntegrityError:
                # If reaction already exists, treat it as a delete
                self.remove_reaction(message_id, user_id, emoji)
                raise ValueError("Reaction removed")

    def remove_reaction(self, message_id: str, user_id: str, emoji: str) -> None:
        with self._get_connection() as conn:
            result = conn.execute(
                """
                DELETE FROM reactions 
                WHERE message_id = ? AND user_id = ? AND emoji = ?
                """,
                (message_id, user_id, emoji)
            )
            if result.rowcount == 0:
                raise ValueError("Reaction not found")

    def get_message_reactions(self, message_id: str) -> dict:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT emoji, GROUP_CONCAT(user_id) as user_ids
                FROM reactions
                WHERE message_id = ?
                GROUP BY emoji
            """, (message_id,)).fetchall()
            
            reactions = {}
            for row in rows:
                reactions[row['emoji']] = row['user_ids'].split(',')
            return reactions

    def get_all_users(self) -> List[User]:
        """Get all users except password field"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT id, name, email, created_at 
                FROM users 
                ORDER BY name ASC
            """).fetchall()
            return [{
                'id': row['id'],
                'name': row['name'],
                'email': row['email'],
                'created_at': row['created_at']
            } for row in rows]

    def update_user_status(self, user_id: str, status: str) -> Optional[User]:
        """Update a user's status and last_active timestamp"""
        print(f"[DB] 1. Updating status for {user_id} to {status}")  # Debug log
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE users 
                SET status = ?, 
                    last_active = strftime('%Y-%m-%d %H:%M:%S', 'now', 'utc')
                WHERE id = ?
            """, (status, user_id))
            
            # Verify the update
            row = conn.execute("SELECT status FROM users WHERE id = ?", (user_id,)).fetchone()
            print(f"[DB] 2. Status after update: {row['status'] if row else 'No user found'}")  # Debug log
            
            return self.get_user_by_id(user_id)

    def get_user_status(self, user_id: str) -> Optional[str]:
        """Get a user's current status"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            return row['status'] if row else None

    def get_dm_channel(self, user1_id: str, user2_id: str) -> Optional[Channel]:
        """Find an existing DM channel between two users"""
        with self._get_connection() as conn:
            # Get channels where both users are members
            rows = conn.execute("""
                SELECT c.* FROM channels c
                JOIN channel_members cm1 ON c.id = cm1.channel_id
                JOIN channel_members cm2 ON c.id = cm2.channel_id
                WHERE c.type = 'dm'
                AND cm1.user_id = ?
                AND cm2.user_id = ?
            """, (user1_id, user2_id)).fetchall()
            
            # Return the first matching channel if found
            return Channel(**dict(rows[0])) if rows else None

    def get_channel_by_id(self, channel_id: str) -> Optional[Channel]:
        """Get a channel by its ID"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM channels WHERE id = ?",
                (channel_id,)
            ).fetchone()
            return Channel(**dict(row)) if row else None

    def get_channel_message_count(self, channel_id: str) -> int:
        """Get the number of messages in a channel"""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as count 
                FROM messages 
                WHERE channel_id = ?
            """, (channel_id,))
            count = row.fetchone()['count']
            print(f"[DB] Message count for channel {channel_id}: {count}")
            return count

    def get_other_dm_user(self, channel_id: str, current_user_id: str) -> Optional[str]:
        """Get the other user's ID in a DM channel"""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT user_id, channel_id 
                FROM channel_members 
                WHERE channel_id = ? AND user_id != ?
                LIMIT 1
            """, (channel_id, current_user_id)).fetchone()
            
            if row:
                print(f"[DB] Found other user {row['user_id']} in channel {row['channel_id']}")
            else:
                print(f"[DB] No other user found in channel {channel_id}")
            
            return row['user_id'] if row else None

    def get_channel_members(self, channel_id: str) -> List[dict]:
        """Get members of a channel"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT u.id, u.name
                FROM channel_members cm
                JOIN users u ON cm.user_id = u.id
                WHERE cm.channel_id = ?
            """, (channel_id,)).fetchall()
            return [{'id': row['id'], 'name': row['name']} for row in rows]

    def search_messages(self, user_id: str, query: str) -> List[Message]:
        """Search messages in channels the user has access to"""
        with self._get_connection() as conn:
            # Get messages that match the query and are in channels the user is a member of
            rows = conn.execute("""
                SELECT DISTINCT m.*, u.name as user_name, u.status as user_status
                FROM messages m
                JOIN channels c ON m.channel_id = c.id
                JOIN channel_members cm ON c.id = cm.channel_id
                JOIN users u ON m.user_id = u.id
                WHERE cm.user_id = ?  -- User has access to the channel
                AND m.content LIKE ?  -- Message contains the query
                ORDER BY m.created_at DESC
                LIMIT 50  -- Limit results for performance
            """, (user_id, f"%{query}%")).fetchall()

            messages = []
            for row in rows:
                data = dict(row)
                # Add user info
                data['user'] = {
                    'name': data.pop('user_name'),
                    'status': data.pop('user_status', 'offline')
                }
                # Add attachments
                data['attachments'] = self.get_message_attachments(data['id'])
                # Add reactions
                data['reactions'] = self.get_message_reactions(data['id'])
                messages.append(Message(**data))

            return messages

    def get_message_attachments(self, message_id: str) -> List[str]:
        """Get attachments for a message"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT filename 
                FROM attachments 
                WHERE message_id = ?
            """, (message_id,)).fetchall()
            return [row['filename'] for row in rows]

    def update_message(self, message_id: str, content: str) -> Message:
        """Update a message's content"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE messages 
                SET content = ?
                WHERE id = ?
            """, (content, message_id))
            
            return self.get_message(message_id)
