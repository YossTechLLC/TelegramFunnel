# echo.py
from telegram import Update, ForceReply
from telegram.ext import ContextTypes

async def script1_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! (EchoBot) - here are the commands you are use right now /start /help /start_crypto /start_payment /shipping /noshipping /database",
        reply_markup=ForceReply(selective=True),
    )

async def script1_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Help! (EchoBot)")

async def script1_echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Prevent echoing during an active conversation
    if context.user_data.get("_conversation") == "database":
        return
    await update.message.reply_text(update.message.text)

echo_handlers = [
    # The echo command handlers are registered in main.py individually
]
