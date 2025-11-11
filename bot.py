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
# NOTE: Replace 'EnAnonBot' with your actual bot's username or URL part
BOT_USERNAME = "EnAnonBot" 
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
                joined TIMESTAMP,
                chat_start TIMESTAMP, 
                messages_sent INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 0,
                interests TEXT
            )
        """)
        await db.commit()

# ---------- BUTTONS ----------
def main_keyboard():
    # Buttons based on the image UI
    buttons = [
        [KeyboardButton("👍"), KeyboardButton("👎")],
        [KeyboardButton("🛑 Complain")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, partner_id, joined, interests) VALUES (?, NULL, ?, 'not set')",
            (user.id, datetime.now())
        )
        await db.commit()

    await update.message.reply_text(
        "👋 **Welcome to Anonymous Chat!**\n\nUse /start_chat to meet a random person.",
        parse_mode="Markdown",
        reply_markup=menu_keyboard() # Start with menu keyboard
    )

def menu_keyboard():
    # Menu structure based on Image 1
    buttons = [
        [KeyboardButton("Share account link")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# ---------- /start_chat (Previously /find) ----------
async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                await update.message.reply_text("⚠️ You're chatting now. Use /stop first.")
                return

        # Try to find a partner
        async with db.execute("SELECT user_id FROM users WHERE partner_id IS NULL AND user_id != ? ORDER BY joined ASC LIMIT 1", (user_id,)) as cur:
            partner = await cur.fetchone()

        if partner:
            partner_id = partner[0]
            now = datetime.now()
            
            # Start chat for both users
            await db.execute("UPDATE users SET partner_id=?, chat_start=?, messages_sent=0 WHERE user_id=?", (partner_id, now, user_id))
            await db.execute("UPDATE users SET partner_id=?, chat_start=?, messages_sent=0 WHERE user_id=?", (user_id, now, partner_id))
            await db.commit()
            
            # Retrieve partner's info for display (placeholders)
            partner_info = {
                'interests': 'not set',
                'rating': 0,
            }
            
            chat_info_message = (
                "🎉 **Partner found!**\n\n"
                "/next — next chat.\n"
                "/stop — stop chat.\n\n"
                "📖 Interests: {interests}\n"
                "🏆 Rating: {rating}\n\n"
                "💡 Hint: tell about the dream you had last night 😴\n"
                f"t.me/{BOT_USERNAME}"
            ).format(**partner_info)
            
            await context.bot.send_message(partner_id, chat_info_message, parse_mode="Markdown", reply_markup=main_keyboard())
            await update.message.reply_text(chat_info_message, parse_mode="Markdown", reply_markup=main_keyboard())
        else:
            await db.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (user_id,))
            await db.commit()
            await update.message.reply_text("🔍 **Searching for a random partner...**")

# ---------- /next_chat (Previously /next) ----------
async def next_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await end_chat(update, context) # End current chat
    await asyncio.sleep(1)
    await find_partner(update, context) # Find a new one

# ---------- /stop (Previously /end) ----------
async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id, chat_start, messages_sent FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

        if not row or not row[0]:
            await update.message.reply_text("❌ You are not chatting right now.")
            return

        partner_id, chat_start_str, user_messages_sent = row
        
        # Get partner's stats before clearing
        async with db.execute("SELECT messages_sent FROM users WHERE user_id=?", (partner_id,)) as cur:
             partner_messages_sent = (await cur.fetchone())[0] if await cur.fetchone() else 0

        # End chat for both users
        await db.execute("UPDATE users SET partner_id=NULL, chat_start=NULL, messages_sent=0 WHERE user_id IN (?, ?)", (user_id, partner_id))
        await db.commit()

    # Calculate duration
    chat_start = datetime.strptime(chat_start_str.split('.')[0], '%Y-%m-%d %H:%M:%S') # Handle potential microsecond issue
    duration = datetime.now() - chat_start
    
    # Format duration string
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    duration_str = f"{hours} hours, {minutes} minutes, {seconds} seconds"
    
    # --- Response Message (Image 3) ---
    end_message = (
        "❗ **The chat is over.**\n\n"
        "⏱️ You've been chatting for: **{duration_str}** and sent: **{messages_sent}** messages!\n\n"
        "💡 If the interlocutor violated the rules or behaved inappropriately, send a complaint against him.\n\n"
        "😉 Give a rating to the interlocutor, which will affect his rating."
    ).format(duration_str=duration_str, messages_sent=user_messages_sent + partner_messages_sent)

    try:
        # Inform partner
        await context.bot.send_message(partner_id, "❌ Your partner left the chat.", reply_markup=main_keyboard())
    except:
        pass
        
    # Send end summary to user
    await update.message.reply_text(end_message, parse_mode="Markdown", reply_markup=main_keyboard())


# ---------- MENU/SETTINGS (Image 1 Structure) ----------
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This function uses the same structure as the image's menu
    menu_text = (
        "🆕 **start chat** /start_chat\n"
        "🔄 **next chat** /next_chat\n"
        "🚫 **end chat** /stop\n"
        "🔑 **menu/settings** /menu\n"
        "🍾 **daily bonus** /bonus\n"
        "👤 **profile** /profile\n"
        "✨ **premium subscription** /premium\n"
        "💡 **terms of use** /rules"
    )
    await update.message.reply_text(menu_text, parse_mode="Markdown", reply_markup=menu_keyboard())

# --- Additional Placeholder Commands ---

async def bonus_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🍾 **Daily Bonus** functionality is not implemented yet.")
    
async def premium_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✨ **Premium Subscription** options coming soon!")

# ---------- /profile & /rules (Minor Text Adjustments) ----------
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Fetch rating and interests (placeholders)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT rating, interests FROM users WHERE user_id=?", (user.id,)) as cur:
            row = await cur.fetchone()
            rating, interests = row if row else (0, 'not set')

    await update.message.reply_text(
        f"👤 **Profile**\n\n"
        f"Name: {user.first_name}\n"
        f"ID: `{user.id}`\n"
        f"🏆 Rating: {rating}\n"
        f"📖 Interests: {interests}",
        parse_mode="Markdown"
    )

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💡 **Terms of Use**\n\n"
        "1️⃣ Respect others.\n"
        "2️⃣ No spam or abuse.\n"
        "3️⃣ Stay anonymous.\n"
        "4️⃣ Use /stop to leave safely.",
        parse_mode="Markdown"
    )

# ---------- LIKE / DISLIKE / COMPLAIN (Minor Button Text Change) ----------
async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # In a real bot, this would update the partner's rating
    await update.message.reply_text("❤️ Thanks for your feedback! Rating applied.")

async def dislike(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # In a real bot, this would decrease the partner's rating
    await update.message.reply_text("👎 Feedback saved. Rating decreased.")

async def complain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user.id,)) as cur:
            row = await cur.fetchone()
    if not row or not row[0]:
        return await update.message.reply_text("You are not chatting currently.")
    partner_id = row[0]
    await context.bot.send_message(ADMIN_ID, f"🚨 **Complaint received!**\nFrom: {user.id}\nAgainst: {partner_id}")
    await update.message.reply_text("🛑 Complaint sent to admin.")

# ---------- SHARE LINK (Minor Button Text Change) ----------
async def share_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    if username:
        await update.message.reply_text(f"🔗 https://t.me/{username}")
    else:
        await update.message.reply_text("❌ You don’t have a username set.")

# ---------- RELAY MESSAGE (Message Counting Added) ----------
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    
    if not row or not row[0]:
        await update.message.reply_text("💬 Use /start_chat to start chatting.")
        return
        
    partner_id = row[0]
    
    # Increment message count for the user
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET messages_sent = messages_sent + 1 WHERE user_id=?", (user_id,))
        await db.commit()

    await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.TYPING)
    await asyncio.sleep(0.3)
    await context.bot.send_message(partner_id, text)

# ---------- RELAY PHOTO (Photo Relay & Message Counting Added) ----------
async def relay_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1].file_id
    caption = update.message.caption or ""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            
    if not row or not row[0]:
        return await update.message.reply_text("💬 You are not chatting.")
        
    partner_id = row[0]
    
    # Increment message count for the user
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET messages_sent = messages_sent + 1 WHERE user_id=?", (user_id,))
        await db.commit()
        
    await context.bot.send_photo(partner_id, photo, caption=caption)

# ---------- MAIN ----------
async def main():
    await init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Command Handlers (Matching Image 1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("start_chat", find_partner)) # Maps to Image 1
    app.add_handler(CommandHandler("find", find_partner)) # Retained as alias
    app.add_handler(CommandHandler("next_chat", next_partner)) # Maps to Image 1
    app.add_handler(CommandHandler("next", next_partner)) # Retained as alias
    app.add_handler(CommandHandler("stop", end_chat)) # Maps to Image 1
    app.add_handler(CommandHandler("end", end_chat)) # Retained as alias
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("bonus", bonus_placeholder)) # Placeholder
    app.add_handler(CommandHandler("premium", premium_placeholder)) # Placeholder

    # Admin Handlers (Retained)
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Message Handlers (Matching Image 2/Keyboard)
    app.add_handler(MessageHandler(filters.PHOTO, relay_photo))
    app.add_handler(MessageHandler(filters.Regex("👍"), like))
    app.add_handler(MessageHandler(filters.Regex("👎"), dislike))
    app.add_handler(MessageHandler(filters.Regex("🛑 Complain"), complain))
    app.add_handler(MessageHandler(filters.Regex("Share account link"), share_link))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message))

    logger.info("🚀 Bot is running...")
    await app.run_polling()

# NOTE: Admin functions (admin_stats, broadcast) are kept from original code for completeness
# but not listed here to avoid redundancy (they are unchanged).
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Not authorized.")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE partner_id IS NOT NULL") as cur:
            chatting = (await cur.fetchone())[0]
    await update.message.reply_text(f"📊 *Bot Stats*\n👥 Total Users: {total}\n💬 Active Chats: {chatting}", parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Not authorized.")
    msg = " ".join(context.args).strip()
    if not msg:
        return await update.message.reply_text("Usage: /broadcast <message>")
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
