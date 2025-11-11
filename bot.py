import logging
import asyncio
import os
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import aiosqlite

# ================= SETTINGS =================
BOT_TOKEN = os.getenv("BOT_TOKEN") or "7479192169:AAHXQbfhgFY3GHZFQbH87ZOo4gPxD7upi_o"  # <-- put token here or use environment variable
ADMIN_ID = 8238022212  # your Telegram numeric ID
DB_PATH = "chat_users.db"

logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
async def init_db():
    """Create users table if not exists"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                partner_id INTEGER
            )
        """)
        await db.commit()

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, partner_id) VALUES (?, NULL)",
            (user.id,)
        )
        await db.commit()

    await update.message.reply_text(
        "👋 Welcome to Anonymous Chat Bot!\n\n"
        "Use /find to connect with a random person.\n"
        "Use /end to leave the chat anytime."
    )

# ================= FIND PARTNER =================
async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

        if row and row[0]:
            await update.message.reply_text("⚠️ You're already chatting! Use /end to stop.")
            return

        # Find another waiting user
        async with db.execute(
            "SELECT user_id FROM users WHERE partner_id IS NULL AND user_id != ?",
            (user_id,)
        ) as cur:
            partner = await cur.fetchone()

        if partner:
            partner_id = partner[0]
            await db.execute("UPDATE users SET partner_id=? WHERE user_id=?", (partner_id, user_id))
            await db.execute("UPDATE users SET partner_id=? WHERE user_id=?", (user_id, partner_id))
            await db.commit()

            await context.bot.send_message(partner_id, "💬 Connected! Say hi 👋")
            await update.message.reply_text("💬 Connected! Say hi 👋")
        else:
            await db.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (user_id,))
            await db.commit()
            await update.message.reply_text("⏳ Waiting for a partner... Please wait!")

# ================= END CHAT =================
async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

        if not row or not row[0]:
            await update.message.reply_text("❌ You’re not in a chat.")
            return

        partner_id = row[0]
        await db.execute(
            "UPDATE users SET partner_id=NULL WHERE user_id IN (?, ?)",
            (user_id, partner_id)
        )
        await db.commit()

    await context.bot.send_message(partner_id, "❌ Your partner ended the chat.")
    await update.message.reply_text("✅ Chat ended successfully.")

# ================= MESSAGE RELAY =================
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

    if not row or not row[0]:
        await update.message.reply_text("❗ You are not connected. Use /find to start chatting.")
        return

    partner_id = row[0]
    await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.TYPING)
    await asyncio.sleep(0.5)
    try:
        await context.bot.send_message(partner_id, text)
    except Exception as e:
        logging.error(f"Failed to send message: {e}")

# ================= ADMIN BROADCAST =================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: /broadcast your_message_here")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()

    success = 0
    for (uid,) in users:
        try:
            await context.bot.send_message(uid, f"📢 Admin Message:\n{msg}")
            success += 1
        except:
            pass

    await update.message.reply_text(f"✅ Broadcast sent to {success} users.")

# ================= RUN BOT =================
async def main():
    await init_db()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find_partner))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message))

    print("🚀 Bot is running...")
    await app.run_polling(close_loop=False)

# ==== FIXED LOOP HANDLING ====
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(main())