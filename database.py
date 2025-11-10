import aiosqlite

DB_PATH = "anon_chat.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                chat_partner INTEGER,
                active INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def set_chat_partner(user_id, partner_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, chat_partner, active)
            VALUES (?, ?, 1)
        """, (user_id, partner_id))
        await db.commit()

async def get_chat_partner(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT chat_partner FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def end_chat(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET active = 0, chat_partner = NULL WHERE user_id = ?", (user_id,))
        await db.commit()

async def is_in_chat(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT active FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0] == 1)