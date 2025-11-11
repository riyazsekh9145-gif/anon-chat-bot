import logging
import asyncio
import os
import aiosqlite
from datetime import datetime
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup, ChatAction
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "7479192169:AAHXQbfhgFY3GHZFQbH87ZOo4gPxD7upi_o"
ADMIN_ID = 8238022212
DB_PATH = "chat_users.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- DB INIT ----------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                partner_id INTEGER,
                joined TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("📁 Database initialized.")

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, partner_id, joined) VALUES (?, NULL, ?)",
            (user.id, datetime.now())
        )
        await db.commit()

    buttons = [
        [KeyboardButton("/find"), KeyboardButton("/end")],
        [KeyboardButton("/menu"), KeyboardButton("/profile")]
    ]
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    await update.message.reply_text(
        "👋 *Welcome to Anon Chat Bot!*\n\n"
        "Start chatting anonymously with strangers.\n"
        "Use /find to start finding someone.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ---------- /find ----------
async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                return await update.message.reply_text("⚠️ You’re already chatting. Use /end first.")

        async with db.execute("SELECT user_id FROM users WHERE partner_id IS NULL AND user_id != ?", (user_id,)) as cur:
            partner = await cur.fetchone()

        if partner:
            partner_id = partner[0]
            await db.execute("UPDATE users SET partner_id=? WHERE user_id=?", (partner_id, user_id))
            await db.execute("UPDATE users SET partner_id=? WHERE user_id=?", (user_id, partner_id))
            await db.commit()
            await context.bot.send_message(partner_id, "🎉 Partner found! Say hi 👋")
            await update.message.reply_text("🎉 Partner found! Say hi 👋")
        else:
            await db.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (user_id,))
            await db.commit()
            await update.message.reply_text("🔍 Searching for a random partner... Please wait...")

# ---------- /end ----------
async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

        if not row or not row[0]:
            return await update.message.reply_text("❌ You are not chatting right now.")

        partner_id = row[0]
        await db.execute("UPDATE users SET partner_id=NULL WHERE user_id IN (?, ?)", (user_id, partner_id))
        await db.commit()

    try:
        await context.bot.send_message(partner_id, "❌ Your partner ended the chat.")
    except Exception:
        pass
    await update.message.reply_text("✅ Chat ended. Use /find to meet a new person.")

# ---------- /menu ----------
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ *Menu*\n\n"
        "/find - Find a random partner\n"
        "/end - End current chat\n"
        "/profile - View your info\n"
        "/rules - Terms of use\n"
        "/next - Skip to next partner\n"
        "/photo1 - Send 1-time photo\n"
        "/photo - Send lifetime photo",
        parse_mode="Markdown"
    )

# ---------- /profile ----------
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 *Profile*\nName: {user.first_name}\nID: `{user.id}`",
        parse_mode="Markdown"
    )

# ---------- /rules ----------
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 *Rules*\n\n"
        "1️⃣ Stay respectful.\n"
        "2️⃣ No spam or abuse.\n"
        "3️⃣ Stay anonymous.\n"
        "4️⃣ Use /end to leave safely.",
        parse_mode="Markdown"
    )

# ---------- RELAY TEXT ----------
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    if not row or not row[0]:
        return await update.message.reply_text("⚠️ You’re not chatting. Use /find first.")
    partner_id = row[0]
    await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.TYPING)
    await asyncio.sleep(0.4)
    try:
        msg = f"*anonymous_bro:*\n{text}"
        await context.bot.send_message(partner_id, msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Relay failed: {e}")

# ---------- RELAY PHOTO ----------
async def relay_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1].file_id
    caption = update.message.caption or ""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    if not row or not row[0]:
        return await update.message.reply_text("⚠️ You’re not chatting. Use /find first.")
    partner_id = row[0]
    await context.bot.send_photo(partner_id, photo, caption=f"📸 {caption}")

# ---------- ADMIN ----------
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Not authorized.")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE partner_id IS NOT NULL") as cur:
            chatting = (await cur.fetchone())[0]
    await update.message.reply_text(
        f"📊 *Bot Stats*\n👥 Total Users: {total}\n💬 Active Chats: {chatting}",
        parse_mode="Markdown"
    )

# ---------- MAIN ----------
async def main():
    await init_db()
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        print("❌ Please paste your real BOT TOKEN in the code first!")
        return
    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find_partner))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(MessageHandler(filters.PHOTO, relay_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message))

    logger.info("🚀 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped.")