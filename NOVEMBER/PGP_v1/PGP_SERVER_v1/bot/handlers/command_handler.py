#!/usr/bin/env python
"""
Command handlers for basic bot commands.
Handles /start, /help, and other simple commands.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.

    Shows welcome message and available channels.
    Gets channel list from database via context.application.bot_data.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    logger.info(f"📱 [BOT] /start command from user {user.id} (@{user.username})")

    # Get database manager from context
    db_manager = context.application.bot_data.get('database_manager')

    if not db_manager:
        logger.error("❌ [BOT] Database manager not available")
        await update.message.reply_text(
            "❌ Service temporarily unavailable. Please try again later."
        )
        return

    try:
        # Fetch channel list from database
        channel_ids, channel_info = db_manager.fetch_open_channel_list()

        if not channel_ids:
            await update.message.reply_text(
                "👋 <b>Welcome to TelePay Bot!</b>\n\n"
                "No channels available at the moment.\n"
                "Please check back later.",
                parse_mode='HTML'
            )
            return

        # Build channel list message
        message = "👋 <b>Welcome to TelePay Bot!</b>\n\n"
        message += "💎 <b>Available Premium Channels:</b>\n\n"

        # Show up to 10 channels
        for i, channel_id in enumerate(channel_ids[:10], 1):
            info = channel_info.get(channel_id, {})
            title = info.get('closed_channel_title', 'Premium Channel')
            description = info.get('closed_channel_description', '')
            price = info.get('subscription_price', 0.0)

            message += f"{i}. <b>{title}</b>\n"
            if description:
                # Truncate long descriptions
                desc = description[:80] + "..." if len(description) > 80 else description
                message += f"   📝 {desc}\n"
            message += f"   💰 <b>${price:.2f}/month</b>\n\n"

        message += "\n💡 Use /help to see available commands."

        await update.message.reply_text(message, parse_mode='HTML')

        logger.info(f"✅ [BOT] Sent channel list to user {user.id}")

    except Exception as e:
        logger.error(f"❌ [BOT] Error in /start command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred. Please try again later."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command.

    Shows help text with available commands and usage instructions.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user = update.effective_user
    logger.info(f"📱 [BOT] /help command from user {user.id} (@{user.username})")

    help_text = """
<b>🤖 TelePay Bot - Help</b>

<b>📋 Available Commands:</b>
/start - Show available premium channels
/help - Show this help message

<b>💎 How to Subscribe:</b>
1. Use /start to see available channels
2. Select a channel from the list
3. Choose your subscription tier
4. Complete the payment process
5. Get instant access to the channel

<b>💝 Making Donations:</b>
Click the 💝 <b>Donate</b> button in any channel to make a one-time donation to support the content creator.

<b>💳 Payment Methods:</b>
We accept cryptocurrency payments via NowPayments:
• Bitcoin (BTC)
• Ethereum (ETH)
• USDT
• And many more...

<b>🔒 Security:</b>
All payments are processed securely through NowPayments. Your personal information is protected.

<b>❓ Need Help?</b>
If you encounter any issues, please contact our support team.

<b>📱 Enjoy your premium content!</b>
"""

    await update.message.reply_text(help_text, parse_mode='HTML')

    logger.info(f"✅ [BOT] Sent help text to user {user.id}")


def register_command_handlers(application):
    """
    Register command handlers with the Telegram application.

    This function should be called during bot initialization to register
    all command handlers.

    Args:
        application: telegram.ext.Application instance

    Example:
        from bot.handlers.command_handler import register_command_handlers
        register_command_handlers(application)
    """
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))

    logger.info("✅ [BOT] Command handlers registered (/start, /help)")
