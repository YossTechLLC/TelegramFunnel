#!/usr/bin/env python
"""
Keyboard builders for Telegram bot.
Creates inline keyboards for donations, subscriptions, and navigation.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional

logger = logging.getLogger(__name__)


def create_donation_keypad(current_amount: str = "0") -> InlineKeyboardMarkup:
    """
    Create numeric keypad for donation amount input.

    Creates a calculator-style keypad with digits 0-9, decimal point,
    backspace, clear, and confirm/cancel buttons.

    Args:
        current_amount: Current amount string to display

    Returns:
        InlineKeyboardMarkup with numeric keypad

    Button Layout:
        [  Amount: $X.XX  ]
        [ 1 ][ 2 ][ 3 ]
        [ 4 ][ 5 ][ 6 ]
        [ 7 ][ 8 ][ 9 ]
        [ . ][ 0 ][ ← ]
        [ Clear ][ ✓ Confirm ]
        [   ✕ Cancel   ]
    """
    # Format amount display
    try:
        amount_float = float(current_amount) if current_amount and current_amount != "0" else 0.0
        display_amount = f"${amount_float:.2f}" if amount_float > 0 else "$0.00"
    except ValueError:
        display_amount = "$0.00"

    keyboard = []

    # Amount display (non-clickable)
    keyboard.append([
        InlineKeyboardButton(f"💰 Amount: {display_amount}", callback_data="donate_display")
    ])

    # Numeric keypad rows (3x3 grid)
    keyboard.append([
        InlineKeyboardButton("1", callback_data="donate_digit_1"),
        InlineKeyboardButton("2", callback_data="donate_digit_2"),
        InlineKeyboardButton("3", callback_data="donate_digit_3")
    ])
    keyboard.append([
        InlineKeyboardButton("4", callback_data="donate_digit_4"),
        InlineKeyboardButton("5", callback_data="donate_digit_5"),
        InlineKeyboardButton("6", callback_data="donate_digit_6")
    ])
    keyboard.append([
        InlineKeyboardButton("7", callback_data="donate_digit_7"),
        InlineKeyboardButton("8", callback_data="donate_digit_8"),
        InlineKeyboardButton("9", callback_data="donate_digit_9")
    ])

    # Bottom row: decimal, zero, backspace
    keyboard.append([
        InlineKeyboardButton(".", callback_data="donate_digit_dot"),
        InlineKeyboardButton("0", callback_data="donate_digit_0"),
        InlineKeyboardButton("←", callback_data="donate_backspace")
    ])

    # Action buttons
    keyboard.append([
        InlineKeyboardButton("🗑 Clear", callback_data="donate_clear"),
        InlineKeyboardButton("✓ Confirm", callback_data="donate_confirm")
    ])
    keyboard.append([
        InlineKeyboardButton("✕ Cancel", callback_data="donate_cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def create_subscription_tiers_keyboard(
    channel_id: str,
    tiers: List[dict]
) -> InlineKeyboardMarkup:
    """
    Create keyboard with subscription tier options.

    Args:
        channel_id: Open channel ID
        tiers: List of tier dictionaries
            [
                {'tier': 1, 'price': 9.99, 'duration': 30, 'description': 'Basic'},
                {'tier': 2, 'price': 24.99, 'duration': 90, 'description': 'Standard'},
                {'tier': 3, 'price': 89.99, 'duration': 365, 'description': 'Premium'}
            ]

    Returns:
        InlineKeyboardMarkup with subscription tiers

    Button Layout:
        [ Tier 1: Basic - $9.99/month ]
        [ Tier 2: Standard - $24.99/3 months ]
        [ Tier 3: Premium - $89.99/year ]
        [ « Back to Channels ]
    """
    keyboard = []

    # Add tier buttons
    for tier in tiers:
        tier_num = tier.get('tier', 1)
        price = tier.get('price', 0.0)
        duration_days = tier.get('duration', 30)
        description = tier.get('description', f'Tier {tier_num}')

        # Format duration
        if duration_days >= 365:
            duration_text = f"{duration_days // 365} year" + ("s" if duration_days >= 730 else "")
        elif duration_days >= 30:
            months = duration_days // 30
            duration_text = f"{months} month" + ("s" if months > 1 else "")
        else:
            duration_text = f"{duration_days} days"

        button_text = f"💎 {description} - ${price:.2f}/{duration_text}"
        callback_data = f"sub_tier_{channel_id}_{tier_num}"

        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    # Add back button
    keyboard.append([InlineKeyboardButton("« Back to Channels", callback_data="back_to_channels")])

    return InlineKeyboardMarkup(keyboard)


def create_back_button(callback_data: str = "back") -> InlineKeyboardMarkup:
    """
    Create simple back button keyboard.

    Args:
        callback_data: Callback data for back button

    Returns:
        InlineKeyboardMarkup with single back button
    """
    keyboard = [[InlineKeyboardButton("« Back", callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)


def create_payment_confirmation_keyboard(
    invoice_url: str,
    cancel_callback: str = "payment_cancel"
) -> InlineKeyboardMarkup:
    """
    Create keyboard with payment link and cancel button.

    Args:
        invoice_url: NowPayments invoice URL
        cancel_callback: Callback data for cancel button

    Returns:
        InlineKeyboardMarkup with payment buttons

    Button Layout:
        [ 💳 Pay Now ]
        [ ✕ Cancel Payment ]
    """
    keyboard = [
        [InlineKeyboardButton("💳 Pay Now", url=invoice_url)],
        [InlineKeyboardButton("✕ Cancel Payment", callback_data=cancel_callback)]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_channel_list_keyboard(
    channels: List[dict],
    page: int = 1,
    per_page: int = 5
) -> InlineKeyboardMarkup:
    """
    Create paginated channel list keyboard.

    Args:
        channels: List of channel dictionaries
            [
                {
                    'channel_id': '-1003268562225',
                    'title': 'Premium Channel',
                    'price': 9.99
                },
                ...
            ]
        page: Current page number (1-indexed)
        per_page: Channels per page

    Returns:
        InlineKeyboardMarkup with channel buttons and navigation

    Button Layout:
        [ Channel 1 - $9.99/mo ]
        [ Channel 2 - $19.99/mo ]
        [ Channel 3 - $29.99/mo ]
        [ « Prev ] [ Page 1/3 ] [ Next » ]
    """
    keyboard = []

    # Calculate pagination
    total_channels = len(channels)
    total_pages = (total_channels + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_channels)

    # Add channel buttons for current page
    for channel in channels[start_idx:end_idx]:
        channel_id = channel.get('channel_id')
        title = channel.get('title', 'Premium Channel')
        price = channel.get('price', 0.0)

        button_text = f"💎 {title} - ${price:.2f}/mo"
        callback_data = f"channel_{channel_id}"

        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    # Add pagination buttons if needed
    if total_pages > 1:
        nav_buttons = []

        if page > 1:
            nav_buttons.append(InlineKeyboardButton("« Prev", callback_data=f"channels_page_{page - 1}"))

        nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="page_info"))

        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("Next »", callback_data=f"channels_page_{page + 1}"))

        keyboard.append(nav_buttons)

    return InlineKeyboardMarkup(keyboard)


logger.info("✅ [KEYBOARDS] Keyboard builders module loaded")
