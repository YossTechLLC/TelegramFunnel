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
            donation_message = channel_info.get("closed_channel_donation_message", "Consider supporting our channel!")

            # NEW: Get old message ID for deletion
            message_ids = self.db_manager.get_last_broadcast_message_ids(open_channel_id)
            old_message_id = message_ids.get('last_closed_message_id')

            try:
                # NEW: Delete old message if exists
                if old_message_id:
                    self.logger.info(
                        f"🗑️ Deleting old message {old_message_id} from {closed_channel_id}"
                    )
                    try:
                        # Validate message_id
                        if old_message_id and old_message_id > 0:
                            await self.bot.delete_message(
                                chat_id=closed_channel_id,
                                message_id=old_message_id
                            )
                            self.logger.info(f"✅ Deleted old message {old_message_id}")
                    except BadRequest as del_error:
                        error_str = str(del_error).lower()
                        if "message to delete not found" in error_str:
                            self.logger.debug(f"⚠️ Message {old_message_id} already deleted")
                            # Idempotent - continue
                        elif "not enough rights" in error_str or "chat administrator" in error_str:
                            self.logger.warning(
                                f"⚠️ No permission to delete message {old_message_id}"
                            )
                        else:
                            self.logger.warning(f"⚠️ Could not delete old message: {del_error}")
                        # Continue even if deletion fails
                    except Exception as del_error:
                        # Handle RetryAfter (already imported from telegram.error)
                        from telegram.error import RetryAfter
                        if isinstance(del_error, RetryAfter):
                            retry_after = del_error.retry_after
                            self.logger.warning(
                                f"⏱️ Rate limited when deleting, waiting {retry_after}s..."
                            )
                            await asyncio.sleep(retry_after)
                            # Retry once
                            try:
                                await self.bot.delete_message(
                                    chat_id=closed_channel_id,
                                    message_id=old_message_id
                                )
                                self.logger.info(f"✅ Deleted old message {old_message_id} on retry")
                            except Exception as retry_err:
                                self.logger.warning(f"⚠️ Retry failed: {retry_err}")
                        else:
                            self.logger.warning(f"⚠️ Could not delete old message: {del_error}")
                        # Continue even if deletion fails

                # Create inline keyboard with single donate button
                reply_markup = self._create_donation_button(open_channel_id)

                # Format message content
                message_text = self._format_donation_message(donation_message)

                # Send to closed channel
                message = await self.bot.send_message(
                    chat_id=closed_channel_id,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

                # NEW: Update message ID in database
                new_message_id = message.message_id
                self.db_manager.update_broadcast_message_ids(
                    open_channel_id=open_channel_id,
                    closed_message_id=new_message_id
                )

                successful += 1
                self.logger.info(
                    f"📨 Sent donation message to {closed_channel_id} "
                    f"(message_id={new_message_id})"
                )

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
        donation_message: str
    ) -> str:
        """
        Format the donation message text with custom message.

        Args:
            donation_message: Custom donation message from the database

        Returns:
            Formatted HTML message text

        Note:
            Message is limited to 4096 characters by Telegram API.
            Format: "Enjoying the content? Consider making a donation " + bold custom message

        Example:
            >>> message = manager._format_donation_message(
            ...     "Your support helps us create amazing content!"
            ... )
            >>> print(message)
            Enjoying the content? Consider making a donation <b>Your support helps us create amazing content!</b>
        """
        message_text = (
            f"Enjoying the content? Consider making a donation.\n<b>{donation_message}</b>"
        )

        # Validate message length (Telegram limit: 4096 characters)
        if len(message_text) > 4096:
            self.logger.warning(
                f"⚠️ Message too long ({len(message_text)} chars), truncating"
            )
            message_text = message_text[:4090] + "..."

        return message_text
