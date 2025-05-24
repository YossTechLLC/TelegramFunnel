from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

API_KEY = "8139434770:AAGQNpGzbpeY1FgENcuJ_rctuXOAmRuPVJU"

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hello! I'm an echo bot. Send me any message, and I'll echo it back!")

# Echo handler
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text
    await update.message.reply_text(message)

def main():
    app = ApplicationBuilder().token(API_KEY).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    print("Bot is running... Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
