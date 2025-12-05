#!/usr/bin/env python
"""
📬 Notification Service for TelePay10-26
Handles sending payment notifications to channel owners.
Refactored from root notification_service.py for better modularity.

Version: 2.0
Date: 2025-11-13
Architecture: NEW_ARCHITECTURE Phase 3.2
"""
import logging
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError, Forbidden, BadRequest
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending payment notifications to channel owners.

    Features:
    - Payment notifications (subscription & donation)
    - Template-based message formatting
    - Telegram Bot API integration
    - Comprehensive error handling
    - Test notification support

    Usage:
        notification_service = NotificationService(bot, db_manager)
        await notification_service.send_payment_notification(
            open_channel_id="-1001234567890",
            payment_type="subscription",
            payment_data={...}
        )
    """

    def __init__(self, bot: Bot, db_manager):
        """
        Initialize notification service.

        Args:
            bot: Telegram Bot instance
            db_manager: DatabaseManager instance for fetching notification settings
        """
        self.bot = bot
        self.db_manager = db_manager
        logger.info("📬 [NOTIFICATION] Service initialized")

    async def send_payment_notification(
        self,
        open_channel_id: str,
        payment_type: str,
        payment_data: Dict[str, Any]
    ) -> bool:
        """
        Send payment notification to channel owner.

        Args:
            open_channel_id: Channel ID to fetch notification settings for
            payment_type: Type of payment ('subscription' or 'donation')
            payment_data: Dictionary containing payment details
                Required keys:
                - user_id: Customer's Telegram user ID
                - amount_crypto: Amount in cryptocurrency
                - amount_usd: Amount in USD
                - crypto_currency: Cryptocurrency symbol
                Optional keys:
                - username: Customer's Telegram username
                - timestamp: Payment timestamp (defaults to now)
                For subscriptions:
                - tier: Subscription tier number
                - tier_price: Tier price in USD
                - duration_days: Subscription duration

        Returns:
            True if notification sent successfully, False otherwise

        Example:
            success = await notification_service.send_payment_notification(
                open_channel_id="-1001234567890",
                payment_type="subscription",
                payment_data={
                    'user_id': 123456789,
                    'username': 'johndoe',
                    'amount_crypto': '0.001',
                    'amount_usd': '29.99',
                    'crypto_currency': 'BTC',
                    'tier': 1,
                    'tier_price': '29.99',
                    'duration_days': 30
                }
            )
        """
        try:
            logger.info("")
            logger.info(f"📬 [NOTIFICATION] Processing notification request")
            logger.info(f"   Channel ID: {open_channel_id}")
            logger.info(f"   Payment Type: {payment_type}")

            # Step 1: Fetch notification settings from database
            settings = self.db_manager.get_notification_settings(open_channel_id)

            if not settings:
                logger.warning(f"⚠️ [NOTIFICATION] No settings found for channel {open_channel_id}")
                return False

            notification_status, notification_id = settings

            # Step 2: Check if notifications are enabled
            if not notification_status:
                logger.info(f"📭 [NOTIFICATION] Notifications disabled for channel {open_channel_id}")
                return False

            if not notification_id:
                logger.warning(f"⚠️ [NOTIFICATION] No notification_id set for channel {open_channel_id}")
                return False

            logger.info(f"✅ [NOTIFICATION] Notifications enabled, sending to {notification_id}")

            # Step 3: Format notification message based on payment type
            message = self._format_notification_message(
                open_channel_id,
                payment_type,
                payment_data
            )

            # Step 4: Send notification via Telegram Bot API
            await self._send_telegram_message(notification_id, message)

            logger.info(f"✅ [NOTIFICATION] Successfully sent to {notification_id}")
            return True

        except Exception as e:
            logger.error(f"❌ [NOTIFICATION] Error sending notification: {e}", exc_info=True)
            return False

    def _format_notification_message(
        self,
        open_channel_id: str,
        payment_type: str,
        payment_data: Dict[str, Any]
    ) -> str:
        """
        Format notification message based on payment type.

        Uses template-based formatting with channel context.

        Args:
            open_channel_id: Channel ID
            payment_type: 'subscription' or 'donation'
            payment_data: Payment details dictionary

        Returns:
            Formatted HTML message string
        """
        # Fetch channel details for context
        channel_info = self.db_manager.get_channel_details_by_open_id(open_channel_id)
        channel_title = channel_info['closed_channel_title'] if channel_info else 'Your Channel'

        # Extract common payment fields
        user_id = payment_data.get('user_id', 'Unknown')
        username = payment_data.get('username', None)
        amount_crypto = payment_data.get('amount_crypto', '0')
        amount_usd = payment_data.get('amount_usd', '0')
        crypto_currency = payment_data.get('crypto_currency', 'CRYPTO')
        timestamp = payment_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'))

        # Format user display (prefer username over user_id)
        user_display = f"@{username}" if username else f"User ID: {user_id}"

        # Select template based on payment type
        if payment_type == 'subscription':
            return self._format_subscription_notification(
                channel_title, open_channel_id, user_display, user_id,
                amount_crypto, amount_usd, crypto_currency, timestamp, payment_data
            )
        elif payment_type == 'donation':
            return self._format_donation_notification(
                channel_title, open_channel_id, user_display, user_id,
                amount_crypto, amount_usd, crypto_currency, timestamp
            )
        else:
            return self._format_generic_notification(
                channel_title, open_channel_id, user_display, user_id,
                amount_crypto, amount_usd, crypto_currency, timestamp
            )

    def _format_subscription_notification(
        self,
        channel_title: str,
        open_channel_id: str,
        user_display: str,
        user_id: str,
        amount_crypto: str,
        amount_usd: str,
        crypto_currency: str,
        timestamp: str,
        payment_data: Dict[str, Any]
    ) -> str:
        """Format subscription payment notification."""
        tier = payment_data.get('tier', 'Unknown')
        tier_price = payment_data.get('tier_price', '0')
        duration_days = payment_data.get('duration_days', '30')

        message = f"""🎉 <b>New Subscription Payment!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Customer:</b> {user_display}
<b>User ID:</b> <code>{user_id}</code>

<b>Subscription Details:</b>
├ Tier: {tier}
├ Price: ${tier_price} USD
└ Duration: {duration_days} days

<b>Payment Amount:</b>
├ Crypto: {amount_crypto} {crypto_currency}
└ USD Value: ${amount_usd}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via NowPayments IPN"""

        return message

    def _format_donation_notification(
        self,
        channel_title: str,
        open_channel_id: str,
        user_display: str,
        user_id: str,
        amount_crypto: str,
        amount_usd: str,
        crypto_currency: str,
        timestamp: str
    ) -> str:
        """Format donation payment notification."""
        message = f"""💝 <b>New Donation Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Donor:</b> {user_display}
<b>User ID:</b> <code>{user_id}</code>

<b>Donation Amount:</b>
├ Crypto: {amount_crypto} {crypto_currency}
└ USD Value: ${amount_usd}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via NowPayments IPN

Thank you for creating valuable content! 🙏"""

        return message

    def _format_generic_notification(
        self,
        channel_title: str,
        open_channel_id: str,
        user_display: str,
        user_id: str,
        amount_crypto: str,
        amount_usd: str,
        crypto_currency: str,
        timestamp: str
    ) -> str:
        """Format generic payment notification (fallback)."""
        message = f"""💳 <b>New Payment Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Customer:</b> {user_display}
<b>User ID:</b> <code>{user_id}</code>

<b>Amount:</b> {amount_crypto} {crypto_currency} (${amount_usd} USD)

<b>Timestamp:</b> {timestamp}"""

        return message

    async def _send_telegram_message(self, chat_id: int, message: str) -> bool:
        """
        Send message via Telegram Bot API.

        Handles all Telegram API errors gracefully.

        Args:
            chat_id: Telegram user ID to send to
            message: Message text (supports HTML formatting)

        Returns:
            True if sent successfully, False otherwise

        Raises:
            Does not raise exceptions - returns False on all errors
        """
        try:
            logger.debug(f"📤 [NOTIFICATION] Sending message to chat_id {chat_id}")

            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )

            logger.info(f"✅ [NOTIFICATION] Message delivered to {chat_id}")
            return True

        except Forbidden as e:
            logger.warning(f"🚫 [NOTIFICATION] Bot blocked by user {chat_id}: {e}")
            # User has blocked the bot - this is expected, don't retry
            return False

        except BadRequest as e:
            logger.error(f"❌ [NOTIFICATION] Invalid request for {chat_id}: {e}")
            # Invalid chat_id or message format - permanent error
            return False

        except TelegramError as e:
            logger.error(f"❌ [NOTIFICATION] Telegram API error: {e}")
            # Network issues, rate limits, etc. - may be transient
            return False

        except Exception as e:
            logger.error(f"❌ [NOTIFICATION] Unexpected error: {e}", exc_info=True)
            return False

    async def test_notification(
        self,
        chat_id: int,
        channel_title: str = "Test Channel"
    ) -> bool:
        """
        Send a test notification to verify setup.

        Useful for channel owners to verify their notification settings.

        Args:
            chat_id: Telegram user ID to send test to
            channel_title: Channel name for test message

        Returns:
            True if test successful, False otherwise

        Example:
            success = await notification_service.test_notification(
                chat_id=123456789,
                channel_title="My Premium Channel"
            )
        """
        test_message = f"""🧪 <b>Test Notification</b>

This is a test notification for your channel: <b>{channel_title}</b>

If you receive this message, your notification settings are configured correctly!

You will receive notifications when:
• A customer subscribes to a tier
• A customer makes a donation

✅ Notification system is working!"""

        try:
            logger.info(f"🧪 [NOTIFICATION] Sending test notification to {chat_id}")
            return await self._send_telegram_message(chat_id, test_message)
        except Exception as e:
            logger.error(f"❌ [NOTIFICATION] Test failed: {e}", exc_info=True)
            return False

    def is_configured(self, open_channel_id: str) -> bool:
        """
        Check if notifications are configured for a channel.

        Args:
            open_channel_id: Channel ID to check

        Returns:
            True if notifications are enabled and configured, False otherwise
        """
        try:
            settings = self.db_manager.get_notification_settings(open_channel_id)

            if not settings:
                return False

            notification_status, notification_id = settings
            return notification_status and notification_id is not None

        except Exception as e:
            logger.error(f"❌ [NOTIFICATION] Error checking configuration: {e}")
            return False

    def get_status(self, open_channel_id: str) -> Dict[str, Any]:
        """
        Get notification status for a channel.

        Args:
            open_channel_id: Channel ID to check

        Returns:
            Dictionary with notification status:
            {
                'enabled': True/False,
                'notification_id': xxx or None,
                'configured': True/False
            }
        """
        try:
            settings = self.db_manager.get_notification_settings(open_channel_id)

            if not settings:
                return {
                    'enabled': False,
                    'notification_id': None,
                    'configured': False
                }

            notification_status, notification_id = settings

            return {
                'enabled': notification_status,
                'notification_id': notification_id,
                'configured': notification_status and notification_id is not None
            }

        except Exception as e:
            logger.error(f"❌ [NOTIFICATION] Error getting status: {e}")
            return {
                'enabled': False,
                'notification_id': None,
                'configured': False,
                'error': str(e)
            }


def init_notification_service(bot: Bot, db_manager) -> NotificationService:
    """
    Factory function to initialize notification service.

    Args:
        bot: Telegram Bot instance
        db_manager: DatabaseManager instance

    Returns:
        NotificationService instance

    Usage:
        notification_service = init_notification_service(bot, db_manager)
    """
    return NotificationService(bot=bot, db_manager=db_manager)


logger.info("✅ [NOTIFICATION] Notification service module loaded")
