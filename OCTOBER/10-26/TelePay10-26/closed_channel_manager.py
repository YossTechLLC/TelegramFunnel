#!/usr/bin/env python
"""
Closed Channel Donation Manager
Sends donate buttons to closed/private channels with inline numeric input.

This module handles all closed channel donation message operations, providing
separation of concerns from broadcast_manager (which handles open channels).
"""

import logging
from typing import Optional, List, Dict, Any
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError, Forbidden, BadRequest
from database import DatabaseManager
import asyncio

logger = logging.getLogger(__name__)


class ClosedChannelManager:
    """
    Manages donation messages in closed/private channels.

    This class is responsible for:
    - Sending donation button messages to closed channels
    - Creating donation inline keyboards
    - Formatting donation messages with channel metadata
    - Handling errors when bot lacks permissions

    Attributes:
        bot: Telegram Bot instance
        db_manager: DatabaseManager instance for database queries
        logger: Logger instance for this module
    """

    def __init__(self, bot_token: str, db_manager: DatabaseManager):
        """
        Initialize the ClosedChannelManager.

        Args:
            bot_token: Telegram bot token for API authentication
            db_manager: DatabaseManager instance for database operations
        """
        self.bot = Bot(token=bot_token)
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

    async def send_donation_message_to_closed_channels(
        self,
        force_resend: bool = False
    ) -> Dict[str, Any]:
        """
        Send donation button to all closed channels where bot is admin.

        This method fetches all closed channels from the database and attempts
        to send a donation message with an inline button to each one. It handles
        errors gracefully and returns a summary of successes and failures.

        Args:
            force_resend: If True, sends even if message was recently sent.
                         Currently not implemented - reserved for future use.

        Returns:
            Dictionary with summary statistics:
            {
                "total_channels": 5,
                "successful": 4,
                "failed": 1,
                "errors": [{"channel_id": "-100XXX", "error": "Bot not admin"}]
            }

        Example:
            >>> result = await manager.send_donation_message_to_closed_channels()
            >>> print(f"Sent to {result['successful']}/{result['total_channels']} channels")
        """
        # Fetch all closed channel IDs from database
        closed_channels = self.db_manager.fetch_all_closed_channels()

        total_channels = len(closed_channels)
        successful = 0
        failed = 0
        errors = []

        self.logger.info(f"📨 Starting donation message broadcast to {total_channels} closed channels")

        for channel_info in closed_channels:
            closed_channel_id = channel_info["closed_channel_id"]
            open_channel_id = channel_info["open_channel_id"]
            channel_title = channel_info.get("closed_channel_title", "Premium Channel")
            channel_description = channel_info.get("closed_channel_description", "exclusive content")

            try:
                # Create inline keyboard with single donate button
                reply_markup = self._create_donation_button(open_channel_id)

                # Format message content
                message_text = self._format_donation_message(channel_title, channel_description)

                # Send to closed channel
                await self.bot.send_message(
                    chat_id=closed_channel_id,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

                successful += 1
                self.logger.info(f"📨 Sent donation message to {closed_channel_id} ({channel_title})")

            except Forbidden as e:
                # Bot not in channel or was kicked
                failed += 1
                error_msg = f"Bot not admin or kicked from channel"
                errors.append({"channel_id": closed_channel_id, "error": error_msg})
                self.logger.warning(f"⚠️ {error_msg}: {closed_channel_id}")

            except BadRequest as e:
                # Invalid channel ID or other API error
                failed += 1
                error_msg = f"Invalid channel ID or API error: {str(e)}"
                errors.append({"channel_id": closed_channel_id, "error": error_msg})
                self.logger.error(f"❌ {error_msg}: {closed_channel_id}")

            except TelegramError as e:
                # General Telegram API errors
                failed += 1
                error_msg = f"Telegram API error: {str(e)}"
                errors.append({"channel_id": closed_channel_id, "error": error_msg})
                self.logger.error(f"❌ {error_msg}: {closed_channel_id}")

            except Exception as e:
                # Unexpected errors (database, network, etc.)
                failed += 1
                error_msg = f"Unexpected error: {str(e)}"
                errors.append({"channel_id": closed_channel_id, "error": error_msg})
                self.logger.error(f"❌ {error_msg}: {closed_channel_id}")

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        # Log summary
        self.logger.info(
            f"✅ Donation broadcast complete: {successful}/{total_channels} successful, "
            f"{failed} failed"
        )

        return {
            "total_channels": total_channels,
            "successful": successful,
            "failed": failed,
            "errors": errors
        }

    def _create_donation_button(self, open_channel_id: str) -> InlineKeyboardMarkup:
        """
        Create inline keyboard with single donation button.

        The callback_data includes the open_channel_id so the bot can
        later identify which channel the donation is for when the user
        clicks the button.

        Args:
            open_channel_id: The open channel ID to encode in callback data

        Returns:
            InlineKeyboardMarkup with single donation button

        Note:
            Callback data is limited to 64 bytes. Current format:
            "donate_start_{open_channel_id}" should fit within this limit
            for standard Telegram channel IDs (14-15 characters).

        Example:
            >>> markup = manager._create_donation_button("-1003268562225")
            >>> # Creates button with callback_data: "donate_start_-1003268562225"
        """
        # Validate callback_data length (Telegram limit: 64 bytes)
        callback_data = f"donate_start_{open_channel_id}"
        if len(callback_data.encode('utf-8')) > 64:
            self.logger.warning(
                f"⚠️ Callback data too long ({len(callback_data)} chars) for channel {open_channel_id}"
            )
            # Truncate if needed (should not happen with standard channel IDs)
            callback_data = callback_data[:64]

        button = InlineKeyboardButton(
            text="💝 Donate to Support This Channel",
            callback_data=callback_data
        )

        # Single button, single row layout
        keyboard = [[button]]
        return InlineKeyboardMarkup(keyboard)

    def _format_donation_message(
        self,
        channel_title: str,
        channel_description: str
    ) -> str:
        """
        Format the donation message text with channel information.

        Args:
            channel_title: Title of the closed channel
            channel_description: Description of the channel content

        Returns:
            Formatted HTML message text

        Note:
            Message is limited to 4096 characters by Telegram API.
            Current implementation should stay well under this limit.

        Example:
            >>> message = manager._format_donation_message(
            ...     "Premium Content",
            ...     "exclusive access"
            ... )
            >>> print(message)
            <b>💝 Support Premium Content</b>

            Enjoying the content? Consider making a donation to help us
            continue providing quality exclusive access.

            Click the button below to donate any amount you choose.
        """
        message_text = (
            f"<b>💝 Support {channel_title}</b>\n\n"
            f"Enjoying the content? Consider making a donation to help us "
            f"continue providing quality {channel_description}.\n\n"
            f"Click the button below to donate any amount you choose."
        )

        # Validate message length (Telegram limit: 4096 characters)
        if len(message_text) > 4096:
            self.logger.warning(
                f"⚠️ Message too long ({len(message_text)} chars) for {channel_title}, truncating"
            )
            message_text = message_text[:4090] + "..."

        return message_text
