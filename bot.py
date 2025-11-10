import logging
import asyncio
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import aiosqlite

# === CONFIGURATION ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8238022212  # Replace with your own Telegram ID
DB_PATH = "anon_chat.db"

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found. Set it in Render Environment Variables.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# === DATABASE INIT ===
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER
            )
        """)
        await db.commit()


# === /START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, partner_id) VALUES (?, ?)", (user_id, None))
        await db.commit()
    await update.message.reply_text(
        "👋 Welcome to *Anonymous Chat!*\n\nUse /next to find a partner.",
        parse_mode="Markdown"
    )


# === FIND PARTNER ===
async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET partner_id = NULL WHERE user_id = ?", (user_id,))
        await db.commit()

        async with db.execute("SELECT user_id FROM users WHERE partner_id IS NULL AND user_id != ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            partner_id = row[0]
            await db.execute("UPDATE users SET partner_id = ? WHERE user_id = ?", (partner_id, user_id))
            await db.execute("UPDATE users SET partner_id = ? WHERE user_id = ?", (user_id, partner_id))
            await db.commit()
            await context.bot.send_message(user_id, "🎉 You are now connected to a stranger! Say hi 👋")
            await context.bot.send_message(partner_id, "🎉 You are now connected to a stranger! Say hi 👋")
        else:
            await update.message.reply_text("⏳ Waiting for a partner...")


# === STOP CHAT ===
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if row and row[0]:
            partner_id = row[0]
            await context.bot.send_message(partner_id, "❌ Your partner left the chat.")
            await db.execute("UPDATE users SET partner_id = NULL WHERE user_id IN (?, ?)", (user_id, partner_id))
            await db.commit()
            await update.message.reply_text("✅ You left the chat.")
        else:
            await update.message.reply_text("⚠️ You are not in a chat.")


# === MESSAGE HANDLER ===
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if not row or not row[0]:
            await update.message.reply_text("❌ You are not connected. Use /next to find a partner.")
            return

        partner_id = row[0]
        try:
            await context.bot.send_chat_action(partner_id, ChatAction.TYPING)
            await asyncio.sleep(0.5)
            await context.bot.send_message(partner_id, text)
        except Exception:
            await update.message.reply_text("⚠️ Partner disconnected.")
            await db.execute("UPDATE users SET partner_id = NULL WHERE user_id = ?", (user_id,))
            await db.commit()


# === ADMIN COMMANDS ===
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    await update.message.reply_text("📢 Sending message to all users...")

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            async for (uid,) in cursor:
                try:
                    await context.bot.send_message(uid, f"📢 *Admin Broadcast:*\n{message}", parse_mode="Markdown")
                except:
                    pass

    await update.message.reply_text("✅ Broadcast sent to all users.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized.")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
    await update.message.reply_text(f"📊 Total registered users: {total_users}")


# === MAIN ===
async def main():
    await init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("next", next_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logging.info("🤖 Bot is running...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())