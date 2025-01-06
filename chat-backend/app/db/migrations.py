from typing import List

class Migration:
    def __init__(self, version: int, up_sql: List[str], down_sql: List[str]):
        self.version = version
        self.up_sql = up_sql
        self.down_sql = down_sql

# List of migrations
migrations: List[Migration] = [
    Migration(
        version=1,
        up_sql=[
            """CREATE TABLE channels_new (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE,
                type TEXT CHECK(type IN ('public', 'private', 'dm')),
                created_by TEXT REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            "INSERT INTO channels_new SELECT * FROM channels",
            "DROP TABLE channels",
            "ALTER TABLE channels_new RENAME TO channels"
        ],
        down_sql=[
            """CREATE TABLE channels_new (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT CHECK(type IN ('public', 'private', 'dm')),
                created_by TEXT REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            "INSERT INTO channels_new SELECT * FROM channels",
            "DROP TABLE channels",
            "ALTER TABLE channels_new RENAME TO channels"
        ]
    ),
    # Add future migrations here
]

def run_migrations(conn):
    # Create migrations table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Get current version
    current = conn.execute("SELECT MAX(version) FROM migrations").fetchone()[0] or 0
    
    # Run pending migrations
    for migration in migrations:
        if migration.version > current:
            try:
                # Execute each statement separately
                for statement in migration.up_sql:
                    conn.execute(statement)
                conn.execute("INSERT INTO migrations (version) VALUES (?)", 
                           (migration.version,))
                print(f"Applied migration {migration.version}")
            except Exception as e:
                print(f"Error applying migration {migration.version}: {e}")
                raise 