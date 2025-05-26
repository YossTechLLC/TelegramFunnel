# database.py
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, ConversationHandler, filters
from utils import get_db_connection

ID_INPUT, NAME_INPUT, AGE_INPUT = range(3)

async def start_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["_conversation"] = "database"
    await update.message.reply_text("Please enter the ID (integer):")
    return ID_INPUT

async def receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
        context.user_data["id"] = user_id
        await update.message.reply_text("Now enter the name:")
        return NAME_INPUT
    except ValueError:
        await update.message.reply_text("Invalid ID. Please enter a valid integer:")
        return ID_INPUT

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    context.user_data["name"] = name
    await update.message.reply_text("Now enter the age (integer):")
    return AGE_INPUT

async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        user_id = context.user_data["id"]
        name = context.user_data["name"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (id, name, age) VALUES (%s, %s, %s)", (user_id, name, age))
        conn.commit()
        cur.close()
        conn.close()

        await update.message.reply_text(f"✅ Saved to database: ID={user_id}, Name={name}, Age={age}")
    except ValueError:
        await update.message.reply_text("Invalid age. Please enter a valid integer:")
        return AGE_INPUT
    except Exception as e:
        await update.message.reply_text(f"❌ Error inserting into database: {e}")
    context.user_data.pop("_conversation", None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("_conversation", None)
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

database_handler = ConversationHandler(
    entry_points=[CommandHandler("database", start_database)],
    states={
        ID_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id)],
        NAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        AGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
