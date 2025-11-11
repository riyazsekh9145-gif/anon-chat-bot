import telebot
from telebot import types

# 🔹 এখানে নিজের Bot Token বসান
BOT_TOKEN = "7479192169:AAHXQbfhgFY3GHZFQbH87ZOo4gPxD7upi_o"
bot = telebot.TeleBot(BOT_TOKEN)

# Chat pairs & ratings memory
waiting_users = []
active_chats = {}
ratings = {}
admins = [8238022212]  # এখানে নিজের Telegram user ID দিন (admin)

def make_main_buttons():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('/start', '/next', '/stop')
    markup.row('👍', '👎', '🚫 Complain')
    markup.row('📎 Share account link')
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Welcome to Anonymous Chat!\n\nPress /next to find a random partner.",
        reply_markup=make_main_buttons()
    )

@bot.message_handler(commands=['next'])
def next_partner(message):
    user_id = message.chat.id
    if user_id in active_chats:
        bot.send_message(user_id, "❌ You are already chatting. Use /stop first.")
        return
    if waiting_users and waiting_users[0] != user_id:
        partner_id = waiting_users.pop(0)
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id
        bot.send_message(user_id, "👫 Partner found! Say Hi 👋")
        bot.send_message(partner_id, "👫 Partner found! Say Hi 👋")
    else:
        waiting_users.append(user_id)
        bot.send_message(user_id, "🔍 Searching for a random partner...")

@bot.message_handler(commands=['stop'])
def stop_chat(message):
    user_id = message.chat.id
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id)
        active_chats.pop(partner_id, None)
        bot.send_message(user_id, "🛑 Chat ended.")
        bot.send_message(partner_id, "🛑 Partner left the chat.")
    elif user_id in waiting_users:
        waiting_users.remove(user_id)
        bot.send_message(user_id, "🛑 Searching stopped.")
    else:
        bot.send_message(user_id, "⚠️ You are not chatting.")

@bot.message_handler(func=lambda m: m.text == '👍')
def like_partner(message):
    user_id = message.chat.id
    partner_id = active_chats.get(user_id)
    if partner_id:
        ratings[partner_id] = ratings.get(partner_id, 0) + 1
        bot.send_message(user_id, "Thanks for rating 👍")
    else:
        bot.send_message(user_id, "You have no partner right now.")

@bot.message_handler(func=lambda m: m.text == '👎')
def dislike_partner(message):
    user_id = message.chat.id
    partner_id = active_chats.get(user_id)
    if partner_id:
        ratings[partner_id] = ratings.get(partner_id, 0) - 1
        bot.send_message(user_id, "Feedback saved 👎")
    else:
        bot.send_message(user_id, "You have no partner right now.")

@bot.message_handler(func=lambda m: m.text == '🚫 Complain')
def complain(message):
    user_id = message.chat.id
    partner_id = active_chats.get(user_id)
    if partner_id:
        for admin_id in admins:
            bot.send_message(admin_id, f"⚠️ Complaint received from {user_id} about {partner_id}")
        bot.send_message(user_id, "Your complaint has been sent 🚫")
    else:
        bot.send_message(user_id, "You are not chatting currently.")

@bot.message_handler(func=lambda m: m.text == '📎 Share account link')
def share_link(message):
    username = message.from_user.username
    if username:
        bot.send_message(message.chat.id, f"🔗 t.me/{username}")
    else:
        bot.send_message(message.chat.id, "❌ You don’t have a username set.")

@bot.message_handler(func=lambda message: True)
def relay_messages(message):
    user_id = message.chat.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        bot.send_message(partner_id, message.text)
    else:
        bot.send_message(user_id, "💬 Use /next to find a partner.")

bot.polling()
