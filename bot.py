import asyncio
import random
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Your Bot Token (Replace with your value)
API_TOKEN = "8460707876:AAFRyIAbp-O79aFvfbxOXkeU3YN5VfLJprw"

# Your Bot Link
BOT_LINK = "https://t.me/anonchatmeetbot"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)

# --- User data simulation ---
user_data = {}
chat_ends = {}

class ProfileStates(StatesGroup):
    WaitingForAge = State()
    WaitingForCaptcha = State()
    SelectingInterests = State()
    SelectingLanguage = State()

def main_menu_keyboard(user_id):
    buttons = [
        [KeyboardButton(text="Find Partner 😎"), KeyboardButton(text="Settings ⚙️")],
        [KeyboardButton(text="Share Profile Link 🔗"), KeyboardButton(text="End Chat 🛑")],
        [KeyboardButton(text="Help ℹ️")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def inline_find_partner_buttons():
    buttons = [
        [InlineKeyboardButton("Find Partner", callback_data="find_partner")],
        [InlineKeyboardButton("Premium Search 💎", callback_data="premium_search")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def inline_premium_plans():
    text = (
        """💎 Premium Features

🔍 Search by gender (M/F)
🦋 Exchange private photos and videos
🌸 Send photos, videos, GIFs, stickers
🤡 Partner's info (Gender, Age)
🚫 No ads

⭐️ The longer the premium, the better the price

Plans:
149 tg star/week
349 tg star/month
400 tg star/3 months
999 tg star/year"""
    )
    return text

def profile_buttons():
    buttons = [
        [InlineKeyboardButton("Become VIP Member", callback_data="become_vip")],
        [InlineKeyboardButton("Reset Ratings (49 tg stars)", callback_data="reset_ratings")],
        [InlineKeyboardButton("Change Age", callback_data="change_age")],
        [InlineKeyboardButton("Change Gender", callback_data="change_gender")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def settings_menu():
    buttons = [
        [InlineKeyboardButton("Select Interests", callback_data="settings_interests")],
        [InlineKeyboardButton("Language", callback_data="settings_language")],
        [InlineKeyboardButton("Help and Support", callback_data="settings_help")],
        [InlineKeyboardButton("Manage Subscription", callback_data="settings_subscription")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def interests_keyboard(selected_interests):
    interests = [
        ("❤️ Loves", "loves"),
        ("🎮 Game", "game"),
        ("💞 Relationship", "relationship"),
        ("👫 Friendship", "friendship"),
        ("🦄 Virtual", "virtual"),
        ("🔄 Exchange", "exchange")
    ]
    keyboard = []
    for label, key in interests:
        prefix = "✅ " if key in selected_interests else "⬜️ "
        keyboard.append([InlineKeyboardButton(prefix + label, callback_data=f"interest_{key}")])
    keyboard.append([
        InlineKeyboardButton("❌ Cancel All", callback_data="interest_cancel_all"),
        InlineKeyboardButton("✅ Select All", callback_data="interest_select_all"),
        InlineKeyboardButton("💾 Save Changes", callback_data="interest_save")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def language_keyboard(selected_language):
    languages = ["English", "Hindi", "Bangla"]
    keyboard = []
    for lang in languages:
        prefix = "✅ " if lang == selected_language else "⬜️ "
        keyboard.append([InlineKeyboardButton(prefix + lang, callback_data=f"lang_{lang.lower()}")])
    keyboard.append([InlineKeyboardButton("💾 Save Changes", callback_data="lang_save")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {
            "gender": None,
            "age": None,
            "total_chats": 0,
            "today_chats": 0,
            "chat_duration": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "ratings_pos": 0,
            "ratings_neg": 0,
            "premium": False,
            "interests": set(),
            "language": "English"
        }
    await message.answer(
        f"Welcome, {message.from_user.first_name}! Use the menu below.",
        reply_markup=main_menu_keyboard(user_id)
    )

@dp.message(F.text == "Find Partner 😎")
async def find_partner(message: types.Message):
    await message.answer("Choose an option:", reply_markup=inline_find_partner_buttons())

@dp.callback_query(lambda c: c.data == "find_partner")
async def callback_find_partner(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Starting random partner search...")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "premium_search")
async def callback_premium_search(callback_query: types.CallbackQuery):
    text = inline_premium_plans()
    await callback_query.message.edit_text(text)
    await callback_query.answer()

@dp.message(F.text == "Share Profile Link 🔗")
async def share_profile(message: types.Message):
    user_id = message.from_user.id
    profile_link = f"{BOT_LINK}?start={user_id}"
    await message.answer(f"Your profile link to share: {profile_link}")

@dp.message(F.text == "End Chat 🛑")
async def end_chat(message: types.Message):
    user_id = message.from_user.id
    chat_ends[user_id] = chat_ends.get(user_id, 0) + 1

    if chat_ends[user_id] >= 10:
        a, b = random.randint(1, 10), random.randint(1, 10)
        answer = a + b
        await message.answer(f"Please solve this captcha to continue: {a} + {b} = ?")
        state = dp.current_state(chat=user_id)
        await state.set_state(ProfileStates.WaitingForCaptcha)
        await state.update_data(captcha_answer=answer)
    else:
        await message.answer("You ended the chat. Type /start to find a new partner.")

@dp.message(ProfileStates.WaitingForCaptcha)
async def captcha_check(message: types.Message, state: FSMContext):
    data = await state.get_data()
    correct = data.get("captcha_answer")
    try:
        if int(message.text) == correct:
            await message.answer("Captcha passed! You can continue chatting.")
            chat_ends[message.from_user.id] = 0
            await state.clear()
        else:
            await message.answer("Wrong answer, try again.")
    except:
        await message.answer("Please send a number.")

@dp.message(F.text == "Help ℹ️")
async def help_support(message: types.Message):
    text = (
        "Welcome to Random Meet Bot! Chat with random strangers anonymously.🌐

"
        "Commands:
"
        "/chat or /newchat - Start a new chat 🚀
"
        "/end - End the current chat ✋
"
        "/help - Bot help ℹ️
"
        "/report - Report spam
"
        "/clear - Remove keyboard
"
        "/settings - Bot settings ⚙️

"
        "For further assistance or issues, contact admins @Theversee"
    )
    await message.answer(text)

@dp.message(F.text == "Settings ⚙️")
async def settings(message: types.Message):
    await message.answer("Settings menu:", reply_markup=settings_menu())

@dp.callback_query(lambda c: c.data == "settings_interests")
async def settings_interests(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    interests = user_data.get(user_id, {}).get("interests", set())
    await callback.message.edit_text("Select your interests:", reply_markup=interests_keyboard(interests))
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("interest_"))
async def interest_toggle(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    interests = user_data.get(user_id, {}).get("interests", set())
    data = callback.data
    if data == "interest_cancel_all":
        interests.clear()
    elif data == "interest_select_all":
        interests.update(["loves", "game", "relationship", "friendship", "virtual", "exchange"])
    elif data == "interest_save":
        user_data[user_id]["interests"] = interests
        await callback.message.edit_text("Interests saved.", reply_markup=settings_menu())
        await callback.answer()
        return
    else:
        interest = data.split("_")[1]
        if interest in interests:
            interests.remove(interest)
        else:
            interests.add(interest)
    user_data[user_id]["interests"] = interests
    await callback.message.edit_text("Select your interests:", reply_markup=interests_keyboard(interests))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "settings_language")
async def settings_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    selected_lang = user_data.get(user_id, {}).get("language", "English")
    await callback.message.edit_text("Select language:", reply_markup=language_keyboard(selected_lang))
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("lang_"))
async def language_toggle(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    if data == "lang_save":
        await callback.message.edit_text("Language saved.", reply_markup=settings_menu())
        await callback.answer()
        return
    lang = data.split("_")[1]
    lang_name = lang.capitalize()
    user_data[user_id]["language"] = lang_name
    await callback.message.edit_text("Select language:", reply_markup=language_keyboard(lang_name))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "settings_help")
async def settings_help(callback: types.CallbackQuery):
    text = (
        "For help and support, use /help.
"
        "Contact admins @Theversee for assistance."
    )
    await callback.message.edit_text(text, reply_markup=settings_menu())

@dp.callback_query(lambda c: c.data == "settings_subscription")
async def settings_subscription(callback: types.CallbackQuery):
    text = "Manage your subscription here. (Add your payment integration)"
    await callback.message.edit_text(text, reply_markup=settings_menu())

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    if not data:
        await message.answer("No profile data found. Start with /start")
        return
    profile_msg = (
        f"#️⃣ ID — {user_id}
"
        f"👫 Gender — {data['gender'] or 'Not set'}
"
        f"🔞 Age — {data['age'] or 'Not set'}

"
        f"⚡️ Chats
"
        f"├ Total: {data['total_chats']}
"
        f"├ Today: {data['today_chats']}
"
        f"└ Duration: {data['chat_duration']} min

"
        f"✉️ Messages
"
        f"├ Sent: {data['messages_sent']}
"
        f"└ Received: {data['messages_received']}

"
        f"⭐️ Ratings: {data['ratings_pos']}👍 {data['ratings_neg']}👎"
    )
    await message.answer(profile_msg, reply_markup=profile_buttons())

@dp.callback_query(lambda c: c.data)
async def callback_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = user_data.get(user_id)
    cb_data = callback.data

    # Profile buttons handling
    if cb_data == "become_vip":
        await callback.message.edit_text(inline_premium_plans())
    elif cb_data == "reset_ratings":
        if data and data.get("premium"):
            data["ratings_pos"] = 0
            data["ratings_neg"] = 0
            await callback.message.edit_text("Ratings reset completed.")
        else:
            await callback.message.edit_text("Resetting ratings costs 49 tg stars. Please become VIP.")
    elif cb_data == "change_age":
        await callback.message.edit_text("Please send your new age as a number.")
        await state.set_state(ProfileStates.WaitingForAge)
    elif cb_data == "change_gender":
        buttons = [
            InlineKeyboardButton("Male", callback_data="gender_male"),
            InlineKeyboardButton("Female", callback_data="gender_female"),
            InlineKeyboardButton("Other", callback_data="gender_other")
        ]
        await callback.message.edit_text("Select your gender:", reply_markup=InlineKeyboardMarkup(row_width=3, inline_keyboard=[buttons]))
    elif cb_data.startswith("gender_"):
        gender = cb_data.split("_")[1].capitalize()
        if data:
            data["gender"] = gender
        await callback.message.edit_text(f"Gender changed to {gender}")

@dp.message(ProfileStates.WaitingForAge)
async def age_received(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        user_data[message.from_user.id]["age"] = age
        await message.answer(f"Age changed to {age}")
        await state.clear()
    except:
        await message.answer("Please enter a valid number for age.")

@dp.message(Command("restart"))
async def cmd_restart(message: types.Message):
    user_id = message.from_user.id
    user_data.pop(user_id, None)
    chat_ends.pop(user_id, None)
    await message.answer("Bot restarted for you. Use /start to begin.")

async def on_startup():
    await bot.set_my_commands([
        BotCommand("restart", "🔄 Restart bot"),
        BotCommand("find_partner", "😎 Find a partner"),
        BotCommand("share_link", "🔗 Share profile link"),
        BotCommand("end_chat", "🛑 End chat"),
        BotCommand("settings", "⚙️ Settings"),
        BotCommand("help", "ℹ️ Help and Support"),
        BotCommand("profile", "👤 Profile"),
    ])

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
