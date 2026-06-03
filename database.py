import aiosqlite

DB_NAME = "sirion_hub.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS mods (user_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS member_activity (
                user_id INTEGER PRIMARY KEY, last_message_at TEXT, warned INTEGER DEFAULT 0, warned_at TEXT
            )
        """)
        await db.execute("CREATE TABLE IF NOT EXISTS user_links (user_id INTEGER PRIMARY KEY, link TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS cleanup_jobs (channel_id INTEGER PRIMARY KEY, duration_seconds INTEGER)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS welcome_settings (
                guild_id INTEGER PRIMARY KEY, channel_id INTEGER, text TEXT, title TEXT, description TEXT, color TEXT
            )
        """)
        await db.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('reg_mode', 'off')")
        await db.commit()