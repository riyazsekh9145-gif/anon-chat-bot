# bot.py
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

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # set this in env (Termux: export BOT_TOKEN="xxx")
ADMIN_ID = 8238022212              # change to your Telegram numeric id
DB_PATH = "chat_users.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- DB init ----------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                partner_id INTEGER
            )
        """)
        await db.commit()

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, partner_id) VALUES (?, NULL)",
                         (user.id,))
        await db.commit()
    await update.message.reply_text(
        "👋 Welcome!\nUse /find to connect with a random user. Use /end to leave."
    )

# ---------- /find ----------
async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        # already chatting?
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                await update.message.reply_text("⚠️ You are already in a chat. Use /end first.")
                return

        # find waiting user
        async with db.execute("SELECT user_id FROM users WHERE partner_id IS NULL AND user_id != ?", (user_id,)) as cur:
            partner = await cur.fetchone()

        if partner:
            partner_id = partner[0]
            await db.execute("UPDATE users SET partner_id=? WHERE user_id=?", (partner_id, user_id))
            await db.execute("UPDATE users SET partner_id=? WHERE user_id=?", (user_id, partner_id))
            await db.commit()
            await context.bot.send_message(partner_id, "💬 Connected! Say hi 👋")
            await update.message.reply_text("💬 Connected! Say hi 👋")
        else:
            # mark user as waiting
            await db.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (user_id,))
            await db.commit()
            await update.message.reply_text("⏳ Waiting for a partner...")

# ---------- /end ----------
async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        if not row or not row[0]:
            await update.message.reply_text("❌ You are not in a chat.")
            return
        partner_id = row[0]
        await db.execute("UPDATE users SET partner_id=NULL WHERE user_id IN (?, ?)", (user_id, partner_id))
        await db.commit()

    # notify both
    try:
        await context.bot.send_message(partner_id, "❌ Your partner ended the chat.")
    except Exception:
        pass
    await update.message.reply_text("✅ Chat ended.")

# ---------- message relay ----------
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

    if not row or not row[0]:
        await update.message.reply_text("❗ You are not connected. Use /find to start.")
        return

    partner_id = row[0]
    await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.TYPING)
    await asyncio.sleep(0.4)
    try:
        await context.bot.send_message(partner_id, text)
    except Exception as e:
        logger.error("Failed send_message: %s", e)
        await update.message.reply_text("⚠️ Failed to deliver message to partner.")

# ---------- admin broadcast ----------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Not authorized.")
        return
    msg = " ".join(context.args).strip()
    if not msg:
        await update.message.reply_text("Usage: /broadcast your message")
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()
    sent = 0
    for (uid,) in rows:
        try:
            await context.bot.send_message(uid, f"📢 Admin:\n{msg}")
            sent += 1
        except:
            pass
    await update.message.reply_text(f"✅ Sent to {sent} users.")

# ---------- main ----------
def main():
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN env var missing. export BOT_TOKEN=your_token")

    # init DB (run once before start)
    asyncio.get_event_loop().run_until_complete(init_db())

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find_partner))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message))

    logger.info("Bot started — running app.run_polling() (blocking).")
    # IMPORTANT: run_polling() here - DO NOT await it with asyncio.run()
    app.run_polling()

if __name__ == "__main__":
    main()
