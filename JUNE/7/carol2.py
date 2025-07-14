import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# carousel steps: each asks for user input
carousel_steps = [
    {"title": "Enter Your Name", "desc": "what should we call you?"},
    {"title": "Enter Your Age", "desc": "how old are you?"},
    {"title": "Enter Your Favorite Color", "desc": "which color do you like most?"},
    {"title": "Enter Your Hobby", "desc": "what's something you enjoy doing?"},
]

# store user state in memory (use db for production)
user_states = {}

# send first step
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"index": 0, "answers": {}}
    await send_carousel_step(update, context, user_id)

# send a carousel step asking for input
async def send_carousel_step(update_or_query, context, user_id):
    state = user_states[user_id]
    index = state["index"]
    step = carousel_steps[index]
    text = f"**{step['title']}**\n\n{step['desc']}\n\nPlease type your answer:"
    keyboard = []
    if index > 0:
        keyboard.append(InlineKeyboardButton("« prev", callback_data=f"step_{index-1}"))
    if index < len(carousel_steps) - 1:
        keyboard.append(InlineKeyboardButton("next »", callback_data=f"step_{index+1}"))
    markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
    if update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update_or_query.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

# handle navigation
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    index = int(query.data.split("_")[1])
    user_states[user_id]["index"] = index
    await send_carousel_step(update, context, user_id)

# handle user input at each step
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states:
        await update.message.reply_text("please start with /start")
        return

    state = user_states[user_id]
    index = state["index"]
    step = carousel_steps[index]
    answer = update.message.text
    state["answers"][step["title"]] = answer

    # move to next or finish
    if index < len(carousel_steps) - 1:
        state["index"] += 1
        await send_carousel_step(update, context, user_id)
    else:
        answers = "\n".join(f"*{k}*: {v}" for k, v in state["answers"].items())
        await update.message.reply_markdown(f"✅ **all done!** here are your answers:\n\n{answers}")
        del user_states[user_id]

# main app
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern=r"^step_\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_input))
    app.run_polling()

if __name__ == "__main__":
    main()
