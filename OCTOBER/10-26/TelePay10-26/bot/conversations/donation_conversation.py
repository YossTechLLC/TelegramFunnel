#!/usr/bin/env python
"""
Donation conversation handler using ConversationHandler.
Multi-step conversation flow for processing donations with numeric keypad.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters
)
from bot.utils.keyboards import create_donation_keypad

logger = logging.getLogger(__name__)

# Conversation states
AMOUNT_INPUT, MESSAGE_INPUT, CONFIRM_PAYMENT = range(3)


async def start_donation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start donation conversation.

    Entry point when user clicks "Donate" button in a channel.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        AMOUNT_INPUT state
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    logger.info(f"💝 [DONATION] Starting donation flow for user {user.id} (@{user.username})")

    # Parse channel ID from callback data
    # Expected format: donate_start_{open_channel_id}
    callback_parts = query.data.split('_')
    if len(callback_parts) < 3:
        logger.error(f"❌ [DONATION] Invalid callback data: {query.data}")
        await query.edit_message_text("❌ Invalid donation link. Please try again.")
        return ConversationHandler.END

    open_channel_id = '_'.join(callback_parts[2:])  # Handle IDs with underscores

    # Store donation context
    context.user_data['donation_channel_id'] = open_channel_id
    context.user_data['donation_amount_building'] = "0"
    context.user_data['chat_id'] = query.message.chat.id

    # Send keypad message
    keypad_message = await context.bot.send_message(
        chat_id=query.message.chat.id,
        text="<b>💝 Enter Donation Amount</b>\n\n"
             "Use the keypad below to enter your donation amount in USD.\n\n"
             "💡 <b>Minimum:</b> $4.99\n"
             "💡 <b>Maximum:</b> $9,999.99\n\n"
             "Your support helps creators continue producing great content!",
        parse_mode="HTML",
        reply_markup=create_donation_keypad("0")
    )

    # Store message ID for later updates/deletion
    context.user_data['keypad_message_id'] = keypad_message.message_id

    logger.info(f"✅ [DONATION] Keypad sent to user {user.id}")

    return AMOUNT_INPUT


async def handle_keypad_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle keypad button presses during amount input.

    Processes digit inputs, backspace, clear, confirm, and cancel actions.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        AMOUNT_INPUT or END state depending on action
    """
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    current_amount = context.user_data.get('donation_amount_building', '0')

    logger.debug(f"💝 [DONATION] Keypad input: {callback_data}, current: {current_amount}")

    # Handle different button types
    if callback_data.startswith('donate_digit_'):
        # Digit or decimal point pressed
        digit = callback_data.split('_')[-1]

        if digit == 'dot':
            # Add decimal point if not already present
            if '.' not in current_amount:
                current_amount = current_amount + '.'
        else:
            # Add digit
            # Limit to 7 characters (9999.99)
            if len(current_amount) < 7:
                if current_amount == '0':
                    current_amount = digit
                else:
                    current_amount = current_amount + digit

    elif callback_data == 'donate_backspace':
        # Remove last character
        if len(current_amount) > 1:
            current_amount = current_amount[:-1]
        else:
            current_amount = '0'

    elif callback_data == 'donate_clear':
        # Clear amount
        current_amount = '0'

    elif callback_data == 'donate_confirm':
        # User confirmed amount, move to payment
        return await confirm_donation(update, context)

    elif callback_data == 'donate_cancel':
        # User cancelled
        return await cancel_donation(update, context)

    elif callback_data == 'donate_display':
        # Display button clicked (no action)
        return AMOUNT_INPUT

    # Update amount in context
    context.user_data['donation_amount_building'] = current_amount

    # Update keypad display
    try:
        await query.edit_message_reply_markup(
            reply_markup=create_donation_keypad(current_amount)
        )
    except Exception as e:
        logger.error(f"❌ [DONATION] Error updating keypad: {e}")

    return AMOUNT_INPUT


async def confirm_donation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Confirm donation amount and ask for optional message.

    Validates amount and prompts user for optional message.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        MESSAGE_INPUT state
    """
    query = update.callback_query
    user = update.effective_user

    # Get and validate amount
    current_amount = context.user_data.get('donation_amount_building', '0')

    try:
        amount_float = float(current_amount)
    except ValueError:
        logger.warning(f"⚠️ [DONATION] Invalid amount format: {current_amount}")
        await query.answer("❌ Invalid amount. Please try again.", show_alert=True)
        return AMOUNT_INPUT

    # Validate minimum amount
    if amount_float < 4.99:
        logger.warning(f"⚠️ [DONATION] Amount below minimum: ${amount_float:.2f}")
        await query.answer("⚠️ Minimum donation: $4.99", show_alert=True)
        return AMOUNT_INPUT

    # Validate maximum amount
    if amount_float > 9999.99:
        logger.warning(f"⚠️ [DONATION] Amount above maximum: ${amount_float:.2f}")
        await query.answer("⚠️ Maximum donation: $9,999.99", show_alert=True)
        return AMOUNT_INPUT

    # Store final amount
    context.user_data['donation_amount'] = amount_float
    open_channel_id = context.user_data.get('donation_channel_id')

    logger.info(f"💝 [DONATION] User {user.id} confirmed ${amount_float:.2f} for channel {open_channel_id}")

    # Delete keypad message
    keypad_message_id = context.user_data.get('keypad_message_id')
    if keypad_message_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat.id,
                message_id=keypad_message_id
            )
        except Exception as e:
            logger.warning(f"⚠️ [DONATION] Could not delete keypad: {e}")

    # Ask for optional message
    keyboard = [
        [InlineKeyboardButton("💬 Add Message", callback_data="donation_add_message")],
        [InlineKeyboardButton("⏭️ Skip Message", callback_data="donation_skip_message")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=f"✅ <b>Donation Amount Confirmed</b>\n\n"
             f"💰 Amount: <b>${amount_float:.2f}</b>\n\n"
             f"Would you like to include a message with your donation?\n"
             f"(Optional, max 256 characters)",
        parse_mode="HTML",
        reply_markup=reply_markup
    )

    return MESSAGE_INPUT


async def handle_message_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle user's choice to add or skip message.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        MESSAGE_INPUT state or calls finalize_payment
    """
    query = update.callback_query
    await query.answer()

    if query.data == "donation_skip_message":
        # User chose to skip message
        logger.info(f"💝 [DONATION] User {update.effective_user.id} skipped message")
        context.user_data['donation_message'] = None
        return await finalize_payment(update, context)

    elif query.data == "donation_add_message":
        # User wants to add a message
        user = update.effective_user
        logger.info(f"💝 [DONATION] User {user.id} adding message")
        logger.info(f"🔍 [DEBUG] Current chat_id: {query.message.chat.id}")
        logger.info(f"🔍 [DEBUG] User private chat_id: {user.id}")
        logger.info(f"🔍 [DEBUG] Returning MESSAGE_INPUT state (value: {MESSAGE_INPUT})")
        logger.info(f"🔍 [DEBUG] ConversationHandler should now accept text messages IN PRIVATE CHAT")

        # CRITICAL FIX: Send message to user's PRIVATE CHAT, not channel
        # Users cannot send text messages in channels - they can only send in private chat with bot
        await context.bot.send_message(
            chat_id=user.id,  # Send to USER's private chat with bot
            text="💬 <b>Enter Your Message</b>\n\n"
                 "Please type your message here (max 256 characters).\n"
                 "This message will be delivered to the channel owner with your donation.\n\n"
                 "💡 <b>Tip:</b> Send /cancel to skip this step",
            parse_mode="HTML"
        )

        # Also acknowledge the button press in the channel
        await query.answer("✅ Message prompt sent to your private chat with the bot!", show_alert=True)

        return MESSAGE_INPUT


async def handle_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle user's text message input.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        MESSAGE_INPUT state or calls finalize_payment
    """
    # DEBUG: Log function entry
    logger.info(f"🔍 [DEBUG] handle_message_text() CALLED")
    logger.info(f"🔍 [DEBUG] update object: {update}")
    logger.info(f"🔍 [DEBUG] update.message exists: {update.message is not None}")

    user = update.effective_user
    logger.info(f"🔍 [DEBUG] user: {user.id if user else 'None'}")

    message_text = update.message.text if update.message else None
    logger.info(f"🔍 [DEBUG] message_text: '{message_text}'")

    # Validate length
    if len(message_text) > 256:
        logger.warning(f"⚠️ [DONATION] Message too long: {len(message_text)} chars")
        await update.message.reply_text(
            f"⚠️ Message too long ({len(message_text)} characters).\n"
            f"Please keep it under 256 characters.",
            parse_mode="HTML"
        )
        return MESSAGE_INPUT

    # Store message
    context.user_data['donation_message'] = message_text
    logger.info(f"💝 [DONATION] User {user.id} entered message ({len(message_text)} chars)")

    # Proceed to payment
    return await finalize_payment(update, context)


async def finalize_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Finalize payment creation with optional message.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        END state (conversation complete)
    """
    user = update.effective_user
    amount_float = context.user_data.get('donation_amount')
    open_channel_id = context.user_data.get('donation_channel_id')
    donation_message = context.user_data.get('donation_message')

    # Get chat_id (handle both callback query and message)
    if update.callback_query:
        chat_id = update.callback_query.message.chat.id
    else:
        chat_id = update.message.chat.id

    logger.info(f"💝 [DONATION] Finalizing payment for user {user.id}")
    logger.info(f"   Amount: ${amount_float:.2f}")
    logger.info(f"   Channel: {open_channel_id}")
    logger.info(f"   Message: {'Yes' if donation_message else 'No'}")

    # Send processing message
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ <b>Payment Processing</b>\n\n"
             f"💰 Amount: <b>${amount_float:.2f}</b>\n"
             f"📍 Channel: <code>{open_channel_id}</code>\n"
             f"💬 Message: {'✅ Included' if donation_message else '❌ None'}\n\n"
             f"⏳ Creating your payment link...",
        parse_mode="HTML"
    )

    # Get payment service from application
    payment_service = context.application.bot_data.get('payment_service')

    if not payment_service:
        logger.error("❌ [DONATION] Payment service not available")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Payment service temporarily unavailable. Please try again later."
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Create order_id
    order_id = f"PGP-{user.id}|{open_channel_id}"

    # Create invoice with encrypted message in success_url
    try:
        # DEBUG: Log original donation message before passing to payment service
        if donation_message:
            logger.info(f"📝 [DEBUG] Original donation message received:")
            logger.info(f"   Input text: '{donation_message}'")
            logger.info(f"   Length: {len(donation_message)} chars")
            logger.info(f"   Type: {type(donation_message).__name__}")
        else:
            logger.info(f"📝 [DEBUG] No donation message provided (Skip Message clicked)")

        result = await payment_service.create_donation_invoice(
            user_id=user.id,
            amount=amount_float,
            order_id=order_id,
            description=f"Donation for {open_channel_id}",
            donation_message=donation_message
        )

        if result['success']:
            invoice_url = result['invoice_url']

            # DEBUG: Log final invoice URL
            logger.info(f"🔗 [DEBUG] Final invoice URL returned from payment_service:")
            logger.info(f"   URL: {invoice_url}")
            logger.info(f"   URL length: {len(invoice_url)} chars")

            await context.bot.send_message(
                chat_id=chat_id,
                text=f"💳 <b>Payment Link Ready!</b>\n\n"
                     f"Click the link below to complete your donation:\n\n"
                     f"{invoice_url}\n\n"
                     f"✅ Secure payment via NowPayments",
                parse_mode="HTML"
            )

            logger.info(f"✅ [DONATION] Invoice created: {invoice_url}")
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ [DONATION] Invoice creation failed: {error_msg}")

            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Failed to create payment link.\n\n"
                     f"Error: {error_msg}\n\n"
                     f"Please try again or contact support."
            )

    except Exception as e:
        logger.error(f"❌ [DONATION] Exception during invoice creation: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ An error occurred while creating your payment link. Please try again."
        )

    # Clean up user data
    context.user_data.clear()

    return ConversationHandler.END


async def cancel_donation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancel donation conversation.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        END state (conversation cancelled)
    """
    query = update.callback_query
    user = update.effective_user

    logger.info(f"💝 [DONATION] User {user.id} cancelled donation")

    # Delete keypad message
    keypad_message_id = context.user_data.get('keypad_message_id')
    if keypad_message_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat.id,
                message_id=keypad_message_id
            )
        except Exception as e:
            logger.warning(f"⚠️ [DONATION] Could not delete keypad: {e}")

    await query.edit_message_text("❌ Donation cancelled.")

    # Clean up user data
    context.user_data.clear()

    return ConversationHandler.END


async def conversation_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle conversation timeout.

    Called when user doesn't interact with conversation within timeout period.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        END state (conversation timed out)
    """
    user = update.effective_user if update and update.effective_user else None
    user_id = user.id if user else 'Unknown'

    logger.warning(f"⏱️ [DONATION] Conversation timeout for user {user_id}")

    # Clean up keypad message if possible
    keypad_message_id = context.user_data.get('keypad_message_id')
    chat_id = context.user_data.get('chat_id')

    if keypad_message_id and chat_id:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=keypad_message_id
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏱️ Donation session expired. Please start again with /start."
            )
        except Exception as e:
            logger.warning(f"⚠️ [DONATION] Error during timeout cleanup: {e}")

    # Clean up user data
    context.user_data.clear()

    return ConversationHandler.END


def create_donation_conversation_handler() -> ConversationHandler:
    """
    Create and return ConversationHandler for donations.

    Configures the conversation flow with entry points, states, and fallbacks.

    Returns:
        ConversationHandler instance ready to be added to Application

    Usage:
        donation_handler = create_donation_conversation_handler()
        application.add_handler(donation_handler)
    """
    logger.info(f"🔍 [DEBUG] Creating donation ConversationHandler")
    logger.info(f"🔍 [DEBUG] MESSAGE_INPUT state value: {MESSAGE_INPUT}")
    logger.info(f"🔍 [DEBUG] MESSAGE_INPUT handlers: CallbackQueryHandler + MessageHandler(TEXT & ~COMMAND)")

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_donation, pattern=r'^donate_start_')
        ],
        states={
            AMOUNT_INPUT: [
                CallbackQueryHandler(handle_keypad_input, pattern=r'^donate_')
            ],
            MESSAGE_INPUT: [
                # Handle button choices
                CallbackQueryHandler(handle_message_choice, pattern=r'^donation_(add|skip)_message$'),
                # Handle text input
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_text)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_donation, pattern=r'^donate_cancel$'),
            CommandHandler('cancel', cancel_donation)
        ],
        conversation_timeout=300,  # 5 minutes
        name='donation_conversation',
        persistent=False,  # Set to True when adding persistence layer
        per_message=False,  # Track conversation per user, not per message
        per_chat=False,  # CRITICAL: Allow conversation to continue across different chats (channel → private)
        per_user=True  # CRITICAL: Track conversation per user ID regardless of which chat they're in
    )


logger.info("✅ [DONATION_CONV] Donation conversation handler module loaded")
