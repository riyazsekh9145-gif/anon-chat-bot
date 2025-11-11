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
        "👋 <b>Welcome to Anonymous Chat!</b>\n\nUse /start_chat to meet a random person.",
        parse_mode="HTML", # Changed to HTML
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
            
            # Use HTML formatting (<b> instead of **)
            chat_info_message = (
                "🎉 <b>Partner found!</b>\n\n"
                "/next — next chat.\n"
                "/stop — stop chat.\n\n"
                "📖 Interests: {interests}\n"
                "🏆 Rating: {rating}\n\n"
                "💡 Hint: tell about the dream you had last night 😴\n"
                f"t.me/{BOT_USERNAME}"
            ).format(**partner_info)
            
            await context.bot.send_message(partner_id, chat_info_message, parse_mode="HTML", reply_markup=main_keyboard()) # Changed to HTML
            await update.message.reply_text(chat_info_message, parse_mode="HTML", reply_markup=main_keyboard()) # Changed to HTML
        else:
            await db.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (user_id,))
            await db.commit()
            await update.message.reply_text("🔍 <b>Searching for a random partner...</b>", parse_mode="HTML") # Changed to HTML

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
    # This line is robust but still relies on the DB timestamp format matching the code's expectation
    try:
        chat_start = datetime.strptime(chat_start_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
    except ValueError:
         chat_start = datetime.strptime(chat_start_str, '%Y-%m-%d %H:%M:%S.%f') # Fallback for full microsecond format

    duration = datetime.now() - chat_start
    
    # Format duration string
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    duration_str = f"{hours} hours, {minutes} minutes, {seconds} seconds"
    
    # --- Response Message (Image 3) - Using HTML (<b> instead of **) ---
    end_message = (
        "❗ <b>The chat is over.</b>\n\n"
        "⏱️ You've been chatting for: <b>{duration_str}</b> and sent: <b>{messages_sent}</b> messages!\n\n"
        "💡 If the interlocutor violated the rules or behaved inappropriately, send a complaint against him.\n\n"
        "😉 Give a rating to the interlocutor, which will affect his rating."
    ).format(duration_str=duration_str, messages_sent=user_messages_sent + partner_messages_sent)

    try:
        # Inform partner
        await context.bot.send_message(partner_id, "❌ Your partner left the chat.", reply_markup=main_keyboard())
    except:
        pass
        
    # Send end summary to user
    await update.message.reply_text(end_message, parse_mode="HTML", reply_markup=main_keyboard()) # Changed to HTML


# ---------- MENU/SETTINGS (Image 1 Structure) ----------
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This function uses the same structure as the image's menu - Using HTML (<b> instead of **)
    menu_text = (
        "🆕 <b>start chat</b> /start_chat\n"
        "🔄 <b>next chat</b> /next_chat\n"
        "🚫 <b>end chat</b> /stop\n"
        "🔑 <b>menu/settings</b> /menu\n"
        "🍾 <b>daily bonus</b> /bonus\n"
        "👤 <b>profile</b> /profile\n"
        "✨ <b>premium subscription</b> /premium\n"
        "💡 <b>terms of use</b> /rules"
    )
    await update.message.reply_text(menu_text, parse_mode="HTML", reply_markup=menu_keyboard()) # Changed to HTML

# --- Additional Placeholder Commands ---

async def bonus_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🍾 <b>Daily Bonus</b> functionality is not implemented yet.", parse_mode="HTML") # Changed to HTML
    
async def premium_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✨ <b>Premium Subscription</b> options coming soon!", parse_mode="HTML") # Changed to HTML

# ---------- /profile & /rules (Minor Text Adjustments) ----------
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Fetch rating and interests (placeholders)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT rating, interests FROM users WHERE user_id=?", (user.id,)) as cur:
            row = await cur.fetchone()
            rating, interests = row if row else (0, 'not set')

    # Using HTML (<b> instead of **)
    await update.message.reply_text(
        f"👤 <b>Profile</b>\n\n"
        f"Name: {user.first_name}\n"
        f"ID: <code>{user.id}</code>\n" # Using <code> for ID as a standard practice
        f"🏆 Rating: {rating}\n"
        f"📖 Interests: {interests}",
        parse_mode="HTML" # Changed to HTML
    )

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💡 <b>Terms of Use</b>\n\n"
        "1️⃣ Respect others.\n"
        "2️⃣ No spam or abuse.\n"
        "3️⃣ Stay anonymous.\n"
        "4️⃣ Use /stop to leave safely.",
        parse_mode="HTML" # Changed to HTML
    )

# ---------- LIKE / DISLIKE / COMPLAIN (Minor Button Text Change) ----------
async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❤️ Thanks for your feedback! Rating applied.")

async def dislike(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👎 Feedback saved. Rating decreased.")

async def complain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user.id,)) as cur:
            row = await cur.fetchone()
    if not row or not row[0]:
        return await update.message.reply_text("You are not chatting currently.")
    partner_id = row[0]
    await context.bot.send_message(ADMIN_ID, f"🚨 <b>Complaint received!</b>\nFrom: {user.id}\nAgainst: {partner_id}", parse_mode="HTML")
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

# ---------- ADMIN FUNCTIONS (Formatting Fixed) ----------
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Not authorized.")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE partner_id IS NOT NULL") as cur:
            chatting = (await cur.fetchone())[0]
    # Using HTML (<b> instead of *)
    await update.message.reply_text(f"📊 <b>Bot Stats</b>\n👥 Total Users: {total}\n💬 Active Chats: {chatting}", parse_mode="HTML")

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

# ---------- MAIN ----------
async def main():
    await init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Command Handlers (Matching Image 1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("start_chat", find_partner)) 
    app.add_handler(CommandHandler("find", find_partner)) 
    app.add_handler(CommandHandler("next_chat", next_partner)) 
    app.add_handler(CommandHandler("next", next_partner)) 
    app.add_handler(CommandHandler("stop", end_chat)) 
    app.add_handler(CommandHandler("end", end_chat)) 
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("bonus", bonus_placeholder)) 
    app.add_handler(CommandHandler("premium", premium_placeholder)) 

    # Admin Handlers
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
