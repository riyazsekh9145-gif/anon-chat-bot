import logging
import asyncio
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
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8238022212  # replace with your Telegram ID

logging.basicConfig(level=logging.INFO)
DB_PATH = "chat_users.db"

##========== DATABASE SETUP ==========

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

##========== START COMMAND ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
user = update.effective_user
async with aiosqlite.connect(DB_PATH) as db:
await db.execute("INSERT OR IGNORE INTO users (user_id, partner_id) VALUES (?, NULL)", (user.id,))
await db.commit()

await update.message.reply_text(  
    "👋 Welcome to Anonymous Chat Bot!\n\nUse /find to start chatting with a random person."  
)

##========== FIND PARTNER ==========

async def find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
user_id = update.effective_user.id

async with aiosqlite.connect(DB_PATH) as db:  
    # Check if already chatting  
    async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:  
        row = await cur.fetchone()  
        if row and row[0]:  
            await update.message.reply_text("⚠️ You’re already in a chat! Use /end to stop.")  
            return  

    # Find a waiting user  
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
        await update.message.reply_text("⏳ Waiting for a partner...")

##========== END CHAT ==========

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

await context.bot.send_message(partner_id, "❌ Your partner has ended the chat.")  
await update.message.reply_text("✅ You ended the chat.")

#========== MESSAGE RELAY ==========

async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
user_id = update.effective_user.id
text = update.message.text

async with aiosqlite.connect(DB_PATH) as db:  
    async with db.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,)) as cur:  
        row = await cur.fetchone()  

if not row or not row[0]:  
    await update.message.reply_text("❗ You are not connected. Use /find to start chatting.")  
    return  

partner_id = row[0]  
await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.TYPING)  
await asyncio.sleep(1)  
await context.bot.send_message(partner_id, text)

##========== ADMIN COMMAND ==========

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != ADMIN_ID:
await update.message.reply_text("⛔ You are not authorized.")
return

msg = " ".join(context.args)  
async with aiosqlite.connect(DB_PATH) as db:  
    async with db.execute("SELECT user_id FROM users") as cur:  
        users = await cur.fetchall()  
for u in users:  
    try:  
        await context.bot.send_message(u[0], f"📢 Admin Message:\n{msg}")  
    except:  
        pass  
await update.message.reply_text("✅ Broadcast sent.")

##========== MAIN FUNCTION ==========

async def main():
await init_db()
app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))  
app.add_handler(CommandHandler("find", find_partner))  
app.add_handler(CommandHandler("end", end_chat))  
app.add_handler(CommandHandler("broadcast", broadcast))  
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message))  

print("✅ Bot is running...")  
await app.run_polling()

if name == "main":
asyncio.run(main())