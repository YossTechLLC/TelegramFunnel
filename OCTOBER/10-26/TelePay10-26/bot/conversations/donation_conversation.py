#!/usr/bin/env python
"""
Donation conversation handler using ConversationHandler.
Multi-step conversation flow for processing donations with numeric keypad.
"""
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from bot.utils.keyboards import create_donation_keypad

logger = logging.getLogger(__name__)

# Conversation states
AMOUNT_INPUT, CONFIRM_PAYMENT = range(2)


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
    Confirm donation and trigger payment gateway.

    Validates amount, creates payment invoice, and sends payment link to user.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        END state (conversation complete)
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

    # Send confirmation message
    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=f"✅ <b>Donation Amount Confirmed</b>\n\n"
             f"💰 Amount: <b>${amount_float:.2f}</b>\n"
             f"📍 Channel: <code>{open_channel_id}</code>\n\n"
             f"⏳ Preparing your payment gateway...",
        parse_mode="HTML"
    )

    # TODO: Trigger payment gateway
    # Get payment service from bot_data
    # payment_service = context.application.bot_data.get('payment_service')
    # if payment_service:
    #     result = await payment_service.create_invoice(
    #         user_id=user.id,
    #         amount=amount_float,
    #         order_id=f"DONATE-{user.id}-{open_channel_id}",
    #         description=f"Donation for {open_channel_id}"
    #     )
    #     if result['success']:
    #         await context.bot.send_message(
    #             chat_id=query.message.chat.id,
    #             text=f"💳 Payment link ready!\n\n{result['invoice_url']}"
    #         )

    logger.info(f"✅ [DONATION] Donation flow complete for user {user.id}")

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
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_donation, pattern=r'^donate_start_')
        ],
        states={
            AMOUNT_INPUT: [
                CallbackQueryHandler(handle_keypad_input, pattern=r'^donate_')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_donation, pattern=r'^donate_cancel$'),
        ],
        conversation_timeout=300,  # 5 minutes
        name='donation_conversation',
        persistent=False  # Set to True when adding persistence layer
    )


logger.info("✅ [DONATION_CONV] Donation conversation handler module loaded")
