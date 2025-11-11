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
BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 8238022212
DB_PATH = "chat_users.db"

logging.basicConfig(level=logging.INFO)
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
        "👋 Welcome to *Anon Chat Bot!*\n\n"
        "Start chatting anonymously with strangers.\n"
        "Use /find to find a partner.",
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
                await update.message.reply_text("⚠️ You are already chatting. Use /end first.")
                return

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
            await update.message.reply_text("🔍 Searching for a random partner...")

# ---------- /end ----------
async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

        if not row or not row[0]:
            await update.message.reply_text("❌ You are not chatting right now.")
            return

        partner_id = row[0]
        await db.execute("UPDATE users SET partner_id=NULL WHERE user_id IN (?, ?)", (user_id, partner_id))
        await db.commit()

    try:
        await context.bot.send_message(partner_id, "❌ Your partner ended the chat.")
    except:
        pass
    await update.message.reply_text("✅ Chat ended. Use /find to meet someone new!")

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
        f"👤 *Profile*\n\n"
        f"Name: {user.first_name}\n"
        f"ID: `{user.id}`",
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
        await update.message.reply_text("⚠️ You are not chatting. Use /find to start.")
        return
    partner_id = row[0]

    await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.TYPING)
    await asyncio.sleep(0.4)
    try:
        anon_name = "anonymous_bro"
        msg = f"*{anon_name}:*\n{text}"
        await context.bot.send_message(partner_id, msg, parse_mode="Markdown")
    except Exception as e:
        logger.error("Relay failed: %s", e)

# ---------- RELAY PHOTO ----------
async def relay_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1].file_id
    caption = update.message.caption or ""

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    if not row or not row[0]:
        await update.message.reply_text("⚠️ You are not chatting. Use /find to start.")
        return
    partner_id = row[0]

    await context.bot.send_photo(partner_id, photo, caption=f"📸 {caption}")

# ---------- ADMIN FEATURES ----------
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Not authorized.")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE partner_id IS NOT NULL") as cur:
            chatting = (await cur.fetchone())[0]
    await update.message.reply_text(f"📊 *Bot Stats*\n\n👥 Total Users: {total}\n💬 Active Chats: {chatting}", parse_mode="Markdown")

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Not authorized.")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = [str(row[0]) for row in await cur.fetchall()]
    await update.message.reply_text("👥 *User List:*\n" + "\n".join(users), parse_mode="Markdown")

async def admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /remove <user_id>")
    user_id = int(context.args[0])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        await db.commit()
    await update.message.reply_text(f"✅ Removed user {user_id}")

# ---------- /broadcast ----------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 Not authorized.")
        return
    msg = " ".join(context.args).strip()
    if not msg:
        await update.message.reply_text("Usage: /broadcast <message>")
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
    await update.message.reply_text(f"✅ Message sent to {sent} users.")

# ---------- MAIN ----------
async def main():
    await init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find_partner))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("remove", admin_remove))
    app.add_handler(MessageHandler(filters.PHOTO, relay_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message))

    logger.info("🚀 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
