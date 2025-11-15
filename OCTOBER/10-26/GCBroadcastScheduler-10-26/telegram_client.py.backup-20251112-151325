#!/usr/bin/env python3
"""
TelegramClient - Telegram Bot API wrapper for broadcast operations
Handles message sending with proper formatting and error handling
"""

import logging
import base64
from typing import Dict, Any, List
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError, Forbidden, BadRequest

logger = logging.getLogger(__name__)


class TelegramClient:
    """
    Wrapper for Telegram Bot API operations specific to broadcast messages.

    Responsibilities:
    - Send subscription tier messages with inline buttons
    - Send donation messages with inline buttons
    - Format messages with proper HTML
    - Handle Telegram API errors gracefully
    """

    def __init__(self, bot_token: str, bot_username: str):
        """
        Initialize the TelegramClient.

        Args:
            bot_token: Telegram bot token
            bot_username: Bot username (for deep links)
        """
        self.bot = Bot(token=bot_token)
        self.bot_username = bot_username
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🤖 TelegramClient initialized for @{bot_username}")

    @staticmethod
    def encode_id(channel_id: str) -> str:
        """
        Encode channel ID for deep link tokens.

        Args:
            channel_id: Telegram channel ID

        Returns:
            Base64-encoded ID
        """
        return base64.urlsafe_b64encode(str(channel_id).encode()).decode()

    def send_subscription_message(
        self,
        chat_id: str,
        open_title: str,
        open_desc: str,
        closed_title: str,
        closed_desc: str,
        tier_buttons: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Send subscription tier message to open channel.

        Args:
            chat_id: Open channel ID
            open_title: Open channel title
            open_desc: Open channel description
            closed_title: Closed channel title
            closed_desc: Closed channel description
            tier_buttons: List of tier info [{'tier': 1, 'price': 5.0, 'time': 30}, ...]

        Returns:
            {'success': bool, 'error': str (if failed)}
        """
        try:
            # Build message text
            message_text = (
                f"Hello, welcome to <b>{open_title}: {open_desc}</b>\n\n"
                f"Choose your Subscription Tier to gain access to <b>{closed_title}: {closed_desc}</b>."
            )

            # Validate message length (Telegram limit: 4096 characters)
            if len(message_text) > 4096:
                self.logger.warning(f"⚠️ Message too long ({len(message_text)} chars), truncating")
                message_text = message_text[:4093] + "..."

            # Build inline keyboard
            tier_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
            buttons = []

            for tier_info in tier_buttons:
                tier_num = tier_info.get('tier')
                price = tier_info.get('price')
                days = tier_info.get('time')

                if price is None or days is None:
                    continue

                # Encode subscription token
                base_hash = self.encode_id(chat_id)
                safe_sub = str(price).replace(".", "d")
                token = f"{base_hash}_{safe_sub}_{days}"
                url = f"https://t.me/{self.bot_username}?start={token}"

                emoji = tier_emojis.get(tier_num, "💰")
                button_text = f"{emoji} ${price} for {days} days"

                buttons.append([InlineKeyboardButton(text=button_text, url=url)])

            if not buttons:
                error_msg = "No valid tier buttons to display"
                self.logger.warning(f"⚠️ {error_msg} for {chat_id}")
                return {'success': False, 'error': error_msg}

            reply_markup = InlineKeyboardMarkup(buttons)

            # Send message
            self.logger.info(f"📤 Sending subscription message to {chat_id}")
            self.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

            self.logger.info(f"✅ Subscription message sent to {chat_id}")
            return {'success': True, 'error': None}

        except Forbidden as e:
            error_msg = "Bot not admin or kicked from channel"
            self.logger.warning(f"⚠️ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except BadRequest as e:
            error_msg = f"Invalid channel or API error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except TelegramError as e:
            error_msg = f"Telegram API error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}", exc_info=True)
            return {'success': False, 'error': error_msg}

    def send_donation_message(
        self,
        chat_id: str,
        donation_message: str,
        open_channel_id: str
    ) -> Dict[str, Any]:
        """
        Send donation message to closed channel.

        Args:
            chat_id: Closed channel ID
            donation_message: Custom donation message
            open_channel_id: Associated open channel (for callback data)

        Returns:
            {'success': bool, 'error': str (if failed)}
        """
        try:
            # Build message text
            message_text = (
                f"Enjoying the content? Consider making a donation.\n<b>{donation_message}</b>"
            )

            # Validate message length (Telegram limit: 4096 characters)
            if len(message_text) > 4096:
                self.logger.warning(f"⚠️ Message too long ({len(message_text)} chars), truncating")
                message_text = message_text[:4093] + "..."

            # Build inline keyboard
            callback_data = f"donate_start_{open_channel_id}"

            # Validate callback_data length (Telegram limit: 64 bytes)
            if len(callback_data.encode('utf-8')) > 64:
                self.logger.warning(f"⚠️ Callback data too long, truncating")
                callback_data = callback_data[:60]  # Leave some margin

            button = InlineKeyboardButton(
                text="💝 Donate to Support This Channel",
                callback_data=callback_data
            )

            reply_markup = InlineKeyboardMarkup([[button]])

            # Send message
            self.logger.info(f"📤 Sending donation message to {chat_id}")
            self.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

            self.logger.info(f"✅ Donation message sent to {chat_id}")
            return {'success': True, 'error': None}

        except Forbidden as e:
            error_msg = "Bot not admin or kicked from channel"
            self.logger.warning(f"⚠️ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except BadRequest as e:
            error_msg = f"Invalid channel or API error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except TelegramError as e:
            error_msg = f"Telegram API error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}", exc_info=True)
            return {'success': False, 'error': error_msg}
