import logging
import asyncio
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import aiosqlite

# === BOT TOKEN FROM ENVIRONMENT ===
BOT_TOKEN = os.getenv("BOT_TOKEN")  # <-- এই লাইনটা যোগ করুন

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found. Please set it in Render Environment Variables.")

ADMIN_ID = 8238022212  # your Telegram user ID

logging.basicConfig(level=logging.INFO)
DB_PATH = "database.db"

# === DATABASE INIT ===
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                gender TEXT,
                age INTEGER,
                partner_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                message TEXT,
                timestamp TEXT
            )
        """)
        await db.commit()


# === /START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Male ♂️", callback_data="gender_male")],
        [InlineKeyboardButton("Female ♀️", callback_data="gender_female")]
    ]
    await update.message.reply_text(
        "👋 Welcome to *Anonymous Chat!*\nPlease select your gender:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# === GENDER SELECTION ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    async with aiosqlite.connect(DB_PATH) as db:
        if data.startswith("gender_"):
            gender = data.split("_")[1]
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, gender) VALUES (?, ?)",
                (user_id, gender)
            )
            await db.commit()
            await query.edit_message_text("✅ Gender saved!\nNow send your age (10–99):")
            context.user_data["awaiting_age"] = True


# === HANDLE MESSAGES ===
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # Admin commands
    if user_id == ADMIN_ID and text.startswith("/"):
        await handle_admin_commands(update, context)
        return

    # Handle age
    if context.user_data.get("awaiting_age"):
        if text.isdigit() and 10 <= int(text) <= 99:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE users SET age = ? WHERE user_id = ?",
                    (int(text), user_id)
                )
                await db.commit()
            await update.message.reply_text("✅ Age saved!\nType /next to find a partner.")
            context.user_data["awaiting_age"] = False
        else:
            await update.message.reply_text("❌ Please enter a valid age (10–99).")
        return

    # Normal message
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT partner_id FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row and row[0]:
            partner_id = row[0]
            try:
                await context.bot.send_message(partner_id, text)
                await db.execute(
                    "INSERT INTO messages (sender_id, receiver_id, message, timestamp) VALUES (?, ?, ?, ?)",
                    (user_id, partner_id, text, datetime.now().isoformat())
                )
                await db.commit()
            except:
                await update.message.reply_text("⚠️ Partner disconnected.")
        else:
            await update.message.reply_text("❌ You are not connected.\nUse /next to find a new partner.")


# === ADMIN COMMANDS ===
async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    async with aiosqlite.connect(DB_PATH) as db:
        if text == "/stats":
            async with db.execute("SELECT COUNT(*) FROM users") as c:
                users_count = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM messages") as c:
                msg_count = (await c.fetchone())[0]
            await update.message.reply_text(f"👥 Users: {users_count}\n💬 Messages: {msg_count}")

        elif text == "/users":
            async with db.execute("SELECT user_id, gender, age FROM users") as c:
                rows = await c.fetchall()
            info = "\n".join([f"{r[0]} — {r[1]}, {r[2]}y" for r in rows]) or "No users yet."
            await update.message.reply_text(f"📋 User List:\n{info}")

        elif text == "/chats":
            async with db.execute("SELECT sender_id, receiver_id, message FROM messages ORDER BY id DESC LIMIT 10") as c:
                rows = await c.fetchall()
            if not rows:
                await update.message.reply_text("No chats yet.")
            else:
                textlog = "\n".join([f"{r[0]} → {r[1]}: {r[2]}" for r in rows])
                await update.message.reply_text(f"🗂️ Last 10 Chats:\n{textlog}")


# === MATCHING ===
async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET partner_id = NULL WHERE user_id = ?", (user_id,))
        await db.commit()

        async with db.execute(
            "SELECT user_id FROM users WHERE partner_id IS NULL AND user_id != ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            partner_id = row[0]
            await db.execute("UPDATE users SET partner_id = ? WHERE user_id = ?", (partner_id, user_id))
            await db.execute("UPDATE users SET partner_id = ? WHERE user_id = ?", (user_id, partner_id))
            await db.commit()
            await context.bot.send_message(user_id, "🎉 Connected to a stranger! Say hi 👋")
            await context.bot.send_message(partner_id, "🎉 Connected to a stranger! Say hi 👋")
        else:
            await update.message.reply_text("⏳ Waiting for a partner...")


# === STOP ===
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET partner_id = NULL WHERE user_id = ?", (user_id,))
        await db.commit()
    await update.message.reply_text("❌ Chat ended. Type /next to start again.")


# === MAIN ===
async def main():
    await init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("next", next_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    await app.run_polling()
   
   
   logging.info("🤖 Bot is now running...")


if __name__ == "__main__":
    asyncio.run(main())