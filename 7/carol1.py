import logging
import random
from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ApplicationBuilder, InlineQueryHandler, ContextTypes
from uuid import uuid4

# your bot token
BOT_TOKEN = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"

# enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# dummy data generator
def generate_fake_data():
    titles = ["Magic Mushroom", "Pixel Wizard", "Dragon Scroll", "Quantum Banana", "Time Mirror"]
    descriptions = ["A mystical item.", "Used by wizards.", "From ancient dragons.", "Powered by qubits.", "Reflects past and future."]
    data = []
    for i in range(5):
        title = random.choice(titles)
        description = random.choice(descriptions)
        content = f"You chose: {title} — {description}"
        result = InlineQueryResultArticle(
            id=uuid4(),
            title=title,
            input_message_content=InputTextMessageContent(content),
            description=description
        )
        data.append(result)
    return data

# inline query handler
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query
    results = generate_fake_data()
    await update.inline_query.answer(results, cache_time=1)

# main function
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(InlineQueryHandler(inline_query))
    app.run_polling()

if __name__ == '__main__':
    main()
