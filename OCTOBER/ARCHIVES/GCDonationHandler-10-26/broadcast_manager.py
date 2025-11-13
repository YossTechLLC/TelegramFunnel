#!/usr/bin/env python
"""
Broadcast Manager for GCDonationHandler
Handles donation button broadcasts to closed/private channels

This module manages sending donation buttons to all closed channels
where the bot is an admin. It is a self-contained module with dependency
injection for database and Telegram operations.
"""

import logging
import time
from typing import Dict, Any, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


class BroadcastManager:
    """
    Manages donation message broadcasts to closed channels.

    This class sends donation buttons to all closed/private channels
    registered in the database. It handles errors gracefully and provides
    detailed statistics about broadcast success/failure.

    Attributes:
        db_manager: DatabaseManager instance for fetching channel list
        telegram_client: TelegramClient instance for sending messages
    """

    def __init__(self, db_manager, telegram_client):
        """
        Initialize the BroadcastManager.

        Args:
            db_manager: DatabaseManager instance
            telegram_client: TelegramClient instance
        """
        self.db_manager = db_manager
        self.telegram_client = telegram_client

        logger.info("📢 BroadcastManager initialized")

    def broadcast_to_closed_channels(self, force_resend: bool = False) -> Dict[str, Any]:
        """
        Send donation button to all closed channels.

        Fetches all closed channels from database and sends a donation
        message with inline button to each one. Handles errors gracefully
        and returns detailed statistics.

        Args:
            force_resend: If True, sends even if recently sent (not implemented yet)

        Returns:
            Dictionary with broadcast statistics:
            {
                'total_channels': int,
                'successful': int,
                'failed': int,
                'errors': [
                    {'channel_id': str, 'error': str},
                    ...
                ]
            }

        Example:
            >>> result = broadcast_manager.broadcast_to_closed_channels()
            >>> print(f"Sent to {result['successful']}/{result['total_channels']} channels")
            >>> if result['errors']:
            ...     print(f"Errors: {result['errors']}")
        """
        # Fetch all closed channels
        closed_channels = self.db_manager.fetch_all_closed_channels()

        total_channels = len(closed_channels)
        successful = 0
        failed = 0
        errors = []

        logger.info(f"📨 Starting donation message broadcast to {total_channels} closed channels")

        for channel_info in closed_channels:
            closed_channel_id = channel_info.get("closed_channel_id")
            open_channel_id = channel_info.get("open_channel_id")
            donation_message = channel_info.get("closed_channel_donation_message", "Consider supporting our channel!")

            try:
                # Create donation button
                reply_markup = self._create_donation_button(open_channel_id)

                # Format message text
                message_text = self._format_donation_message(donation_message)

                # Send to closed channel
                result = self.telegram_client.send_message(
                    chat_id=int(closed_channel_id),
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )

                if result['success']:
                    successful += 1
                    logger.info(f"✅ Sent donation message to channel {closed_channel_id}")
                else:
                    failed += 1
                    error_msg = result.get('error', 'Unknown error')
                    errors.append({
                        'channel_id': closed_channel_id,
                        'error': error_msg
                    })
                    logger.error(f"❌ Failed to send to channel {closed_channel_id}: {error_msg}")

                # Small delay to avoid rate limiting (Telegram: 30 msgs/sec for bots)
                time.sleep(0.1)

            except Exception as e:
                failed += 1
                error_msg = str(e)
                errors.append({
                    'channel_id': closed_channel_id,
                    'error': error_msg
                })
                logger.error(f"❌ Exception sending to channel {closed_channel_id}: {e}")

        # Log summary
        logger.info(f"📨 Broadcast complete: {successful}/{total_channels} successful, {failed} failed")
        if errors:
            logger.warning(f"⚠️ Broadcast errors: {len(errors)} channels failed")

        return {
            'total_channels': total_channels,
            'successful': successful,
            'failed': failed,
            'errors': errors
        }

    def _create_donation_button(self, open_channel_id: str) -> InlineKeyboardMarkup:
        """
        Create inline keyboard with donate button.

        Args:
            open_channel_id: Channel ID to include in callback data

        Returns:
            InlineKeyboardMarkup with single donation button

        Raises:
            ValueError: If callback_data exceeds Telegram's 64-byte limit
        """
        # Create callback data
        callback_data = f"donate_start_{open_channel_id}"

        # Validate callback data length (Telegram limit: 64 bytes)
        if len(callback_data.encode('utf-8')) > 64:
            logger.error(f"❌ Callback data too long: {callback_data}")
            raise ValueError(f"Callback data exceeds 64 bytes: {callback_data}")

        # Create button
        button = InlineKeyboardButton(
            text="💝 Donate to Support This Channel",
            callback_data=callback_data
        )

        # Create keyboard with single button
        keyboard = [[button]]

        return InlineKeyboardMarkup(keyboard)

    def _format_donation_message(self, donation_message: str) -> str:
        """
        Format donation message with HTML formatting.

        Args:
            donation_message: Custom donation message from channel owner

        Returns:
            Formatted message text with HTML tags

        Note:
            Telegram message limit is 4096 characters. Messages longer
            than this will be truncated with "..." suffix.
        """
        # Format message with custom donation text
        message_text = (
            f"Enjoying the content? Consider making a donation.\n"
            f"<b>{donation_message}</b>"
        )

        # Validate message length (Telegram limit: 4096 characters)
        if len(message_text) > 4096:
            logger.warning(f"⚠️ Message too long ({len(message_text)} chars), truncating to 4096")
            message_text = message_text[:4093] + "..."

        return message_text
