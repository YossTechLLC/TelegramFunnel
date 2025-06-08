import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# dummy carousel data
carousel_data = [
    {"title": "Magic Mushroom", "desc": "a mystical item with unknown powers."},
    {"title": "Pixel Wizard", "desc": "summons retro enchantments."},
    {"title": "Dragon Scroll", "desc": "contains ancient dragon secrets."},
    {"title": "Quantum Banana", "desc": "peels reality into parallel layers."},
    {"title": "Time Mirror", "desc": "reflects both past and future."}
]

# build the inline keyboard
def build_keyboard(index):
    buttons = []
    if index > 0:
        buttons.append(InlineKeyboardButton("« prev", callback_data=f"carousel_{index-1}"))
    if index < len(carousel_data) - 1:
        buttons.append(InlineKeyboardButton("next »", callback_data=f"carousel_{index+1}"))
    return InlineKeyboardMarkup([buttons]) if buttons else None

# send the first card
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    index = 0
    item = carousel_data[index]
    text = f"**{item['title']}**\n\n{item['desc']}"
    await update.message.reply_markdown(text, reply_markup=build_keyboard(index))

# handle navigation
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, index_str = query.data.split("_")
    index = int(index_str)
    item = carousel_data[index]
    text = f"**{item['title']}**\n\n{item['desc']}"
    await query.edit_message_text(text=text, reply_markup=build_keyboard(index), parse_mode="Markdown")

# setup and run the bot
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern=r"^carousel_\d+$"))
    app.run_polling()

if __name__ == "__main__":
    main()
