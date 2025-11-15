import logging
from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler,
    ConversationHandler, CallbackQueryHandler, filters
)
import random

ADMINS = [8238022212]  # Put your Telegram User ID here

# Simple in-memory user data. Use a DB for production!
user_data = {}
chat_sessions = {}

main_keyboard = [
    ["/start", "/next", "/stop"],
    ["/menu", "/bonus", "/profile"],
    ["/premium", "/rules"]
]
reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)

admin_keyboard = [
    [InlineKeyboardButton("Broadcast Message", callback_data='broadcast')],
    [InlineKeyboardButton("View All Profiles", callback_data='profiles')],
    [InlineKeyboardButton("Ban User", callback_data='ban')],
]
admin_markup = InlineKeyboardMarkup(admin_keyboard)

def is_admin(user_id):
    return user_id in ADMINS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data.setdefault(user_id, {"chats": 0, "rating": None, "bonus": False, "banned": False, "premium": False})
    if user_data[user_id]["banned"]:
        await update.message.reply_text("You are banned from the bot.", reply_markup=reply_markup)
        return
    await update.message.reply_text(
        "Welcome! Use the menu buttons for options.",
        reply_markup=reply_markup
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("Admin Panel", callback_data='admin_panel')],
        [InlineKeyboardButton("Share Your Link", url="https://t.me/anonymousbrobot")]
    ]
    await update.message.reply_text("Menu:", reply_markup=InlineKeyboardMarkup(kb))

async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_data.get(user_id, {}).get("banned", False):
        await update.message.reply_text("You are banned from chat.", reply_markup=reply_markup)
        return
    # Simplified partner matching: Finds any other available user
    available = [uid for uid in user_data if uid != user_id and not user_data[uid]["banned"]]
    if available:
        partner_id = random.choice(available)
        chat_sessions[user_id] = partner_id
        chat_sessions[partner_id] = user_id
        user_data[user_id]["chats"] += 1
        user_data[partner_id]["chats"] += 1
        await update.message.reply_text(f"🙈 Partner found! Type /stop to end chat.")
        # Inform partner
        context.bot.send_message(partner_id, "🤝 A random partner found! Type /stop to end.")
    else:
        await update.message.reply_text("No partners available. Try again later.")

async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rating_kb = [
        [InlineKeyboardButton("👍", callback_data='rate_good'), InlineKeyboardButton("👎", callback_data='rate_bad')],
        [InlineKeyboardButton("❗Submit Complaint", callback_data='complain')]
    ]
    await update.message.reply_text(
        "❗ The chat is over.
Please rate your partner:",
        reply_markup=InlineKeyboardMarkup(rating_kb)
    )
    # Clean up session
    partner_id = chat_sessions.pop(user_id, None)
    if partner_id:
        chat_sessions.pop(partner_id, None)

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_data[user_id]["bonus"]:
        user_data[user_id]["bonus"] = True
        await update.message.reply_text("🎉 You've claimed your daily bonus!")
    else:
        await update.message.reply_text("You have already claimed today's bonus.")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data[user_id]
    await update.message.reply_text(f"Profile:
Chats: {data['chats']}
Rating: {data['rating']}
Premium: {data['premium']}
Banned: {data['banned']}")

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data[user_id]
    if data["premium"]:
        await update.message.reply_text("You're a premium user! Enjoy all features.")
    else:
        data["premium"] = True
        await update.message.reply_text("Premium activated! You now have full access.")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Terms and Rules:
- Don't spam
- Be respectful
- Admins can ban users who violate rules.")

# Inline button callbacks: ratings, complaints, admin panel etc.
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "rate_good":
        user_data[user_id]["rating"] = "Good"
        await query.answer("Thanks for rating 👍")
        await query.edit_message_text("Thanks for rating 👍")
    elif data == "rate_bad":
        user_data[user_id]["rating"] = "Bad"
        await query.answer("Thanks for your feedback 👎")
        await query.edit_message_text("Rating saved 👎")
    elif data == "complain":
        await query.answer("Complaint reported to admins.")
        for admin in ADMINS:
            context.bot.send_message(admin, f"User {user_id} has made a complaint.")
        await query.edit_message_text("Complaint submitted.")
    elif data == "admin_panel":
        if is_admin(user_id):
            await query.message.reply_text("Admin Panel:", reply_markup=admin_markup)
        else:
            await query.answer("You are not admin.")
    elif data == "broadcast" and is_admin(user_id):
        await query.message.reply_text("Reply to this message to broadcast.")
    elif data == "profiles" and is_admin(user_id):
        profiles = "
".join([f"User {uid}: {user_data[uid]}" for uid in user_data])
        await query.message.reply_text(f"All profiles:
{profiles}")
    elif data == "ban" and is_admin(user_id):
        await query.message.reply_text("Send user ID to ban:")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text.isdigit() and is_admin(user_id):
        # Ban command: If admin sends a user ID
        uid_to_ban = int(update.message.text)
        if uid_to_ban in user_data:
            user_data[uid_to_ban]["banned"] = True
            await update.message.reply_text(f"User {uid_to_ban} banned.")
        else:
            await update.message.reply_text(f"User {uid_to_ban} not found.")
    else:
        await update.message.reply_text("Message received.")

if __name__ == '__main__':
    app = ApplicationBuilder().token("7479192169:AAHXQbfhgFY3GHZFQbH87ZOo4gPxD7upi_o").build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', menu))
    app.add_handler(CommandHandler('next', next_chat))
    app.add_handler(CommandHandler('stop', stop_chat))
    app.add_handler(CommandHandler('bonus', bonus))
    app.add_handler(CommandHandler('profile', profile))
    app.add_handler(CommandHandler('premium', premium))
    app.add_handler(CommandHandler('rules', rules))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()