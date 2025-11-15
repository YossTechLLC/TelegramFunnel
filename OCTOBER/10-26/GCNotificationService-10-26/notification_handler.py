#!/usr/bin/env python
"""
📬 Notification Handler for GCNotificationService
Handles notification formatting and delivery logic
"""
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class NotificationHandler:
    """Handles notification business logic"""

    def __init__(self, db_manager, telegram_client):
        """
        Initialize notification handler

        Args:
            db_manager: DatabaseManager instance
            telegram_client: TelegramClient instance
        """
        self.db_manager = db_manager
        self.telegram_client = telegram_client
        logger.info("📬 [HANDLER] Notification handler initialized")

    def send_payment_notification(
        self,
        open_channel_id: str,
        payment_type: str,  # 'subscription' or 'donation'
        payment_data: Dict[str, Any]
    ) -> bool:
        """
        Send payment notification to channel owner

        Args:
            open_channel_id: The channel ID to fetch notification settings for
            payment_type: Type of payment ('subscription' or 'donation')
            payment_data: Dictionary containing payment details
                Required keys:
                - user_id: Customer's Telegram user ID
                - amount_crypto: Amount in cryptocurrency
                - amount_usd: Amount in USD
                - crypto_currency: Cryptocurrency symbol
                - timestamp: Payment timestamp (optional)
                For subscriptions:
                - tier: Subscription tier number
                - tier_price: Tier price in USD
                - duration_days: Subscription duration

        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            logger.info("")
            logger.info("📬 [HANDLER] Processing notification request")
            logger.info(f"   Channel ID: {open_channel_id}")
            logger.info(f"   Payment Type: {payment_type}")

            # Step 1: Fetch notification settings
            settings = self.db_manager.get_notification_settings(open_channel_id)

            if not settings:
                logger.warning(f"⚠️ [HANDLER] No settings found for channel {open_channel_id}")
                return False

            notification_status, notification_id = settings

            # Step 2: Check if notifications enabled
            if not notification_status:
                logger.info(f"📭 [HANDLER] Notifications disabled for channel {open_channel_id}")
                return False

            if not notification_id:
                logger.warning(f"⚠️ [HANDLER] No notification_id set for channel {open_channel_id}")
                return False

            logger.info(f"✅ [HANDLER] Notifications enabled, sending to {notification_id}")

            # Step 3: Format notification message
            message = self._format_notification_message(
                open_channel_id,
                payment_type,
                payment_data
            )

            # Step 4: Send notification
            success = self.telegram_client.send_message(
                chat_id=notification_id,
                text=message,
                parse_mode='HTML'
            )

            if success:
                logger.info(f"✅ [HANDLER] Successfully sent to {notification_id}")
            else:
                logger.warning(f"⚠️ [HANDLER] Failed to send to {notification_id}")

            return success

        except Exception as e:
            logger.error(f"❌ [HANDLER] Error sending notification: {e}", exc_info=True)
            return False

    def _format_notification_message(
        self,
        open_channel_id: str,
        payment_type: str,
        payment_data: Dict[str, Any]
    ) -> str:
        """
        Format notification message based on payment type

        Args:
            open_channel_id: Channel ID
            payment_type: 'subscription' or 'donation'
            payment_data: Payment details

        Returns:
            Formatted message string
        """
        # Fetch channel details for context
        channel_info = self.db_manager.get_channel_details_by_open_id(open_channel_id)
        channel_title = channel_info['closed_channel_title'] if channel_info else 'Your Channel'

        # Fetch payout configuration (NEW)
        payout_config = self.db_manager.get_payout_configuration(open_channel_id)

        # Extract common fields
        user_id = payment_data.get('user_id', 'Unknown')
        username = payment_data.get('username', None)
        timestamp = payment_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'))

        # Format user display (simplified - no duplicate User ID)
        user_display = f"User ID: <code>{user_id}</code>"
        if username:
            user_display = f"@{username} (<code>{user_id}</code>)"

        # Build payout section based on configuration
        payout_section = self._format_payout_section(open_channel_id, payout_config)

        if payment_type == 'subscription':
            # Subscription payment notification
            tier = payment_data.get('tier', 'Unknown')
            tier_price = payment_data.get('tier_price', '0')
            duration_days = payment_data.get('duration_days', '30')

            message = f"""🎉 <b>New Subscription Payment!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Customer:</b> {user_display}

<b>Subscription Details:</b>
├ Tier: {tier}
├ Price: ${tier_price} USD
└ Duration: {duration_days} days

{payout_section}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via PayGatePrime"""

        elif payment_type == 'donation':
            # Donation payment notification
            donor_message = payment_data.get('donor_message')  # Get decrypted message

            # Build message section
            message_section = ""
            if donor_message:
                # Escape HTML special characters
                import html
                escaped_message = html.escape(donor_message)
                message_section = f"\n<b>💬 Message from Donor:</b>\n<i>\"{escaped_message}\"</i>\n"

            message = f"""💝 <b>New Donation Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Donor:</b> {user_display}
{message_section}
{payout_section}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via PayGatePrime

Thank you for creating valuable content! 🙏"""

        else:
            # Fallback for unknown payment types
            message = f"""💳 <b>New Payment Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Customer:</b> {user_display}

{payout_section}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via PayGatePrime"""

        return message

    def _format_payout_section(
        self,
        open_channel_id: str,
        payout_config: Optional[Dict[str, Any]]
    ) -> str:
        """
        Format the payout method section of the notification

        Args:
            open_channel_id: Channel ID for threshold progress lookup
            payout_config: Payout configuration dict from database

        Returns:
            Formatted payout section string
        """
        if not payout_config:
            return "<b>Payout Method:</b> Not configured"

        payout_strategy = payout_config.get('payout_strategy', 'instant')
        wallet_address = payout_config.get('wallet_address', 'N/A')
        payout_currency = payout_config.get('payout_currency', 'N/A')
        payout_network = payout_config.get('payout_network', 'N/A')
        threshold_usd = payout_config.get('threshold_usd')

        # Handle long wallet addresses (truncate if > 48 chars)
        wallet_display = wallet_address
        if wallet_address and len(wallet_address) > 48:
            wallet_display = f"{wallet_address[:20]}...{wallet_address[-20:]}"

        if payout_strategy == 'instant':
            # Instant payout mode
            return f"""<b>Payout Method:</b> INSTANT
├ Currency: {payout_currency}
├ Network: {payout_network}
└ Wallet: <code>{wallet_display}</code>"""

        elif payout_strategy == 'threshold':
            # Threshold payout mode with live progress tracking
            current_accumulated = self.db_manager.get_threshold_progress(open_channel_id)

            # Handle None return (query error)
            if current_accumulated is None:
                current_accumulated = Decimal('0.00')

            # Calculate progress percentage (with division-by-zero protection)
            if threshold_usd and threshold_usd > 0:
                progress_percent = (current_accumulated / threshold_usd) * 100
            else:
                progress_percent = Decimal('0.0')

            # Format amounts with 2 decimal places
            current_str = f"{current_accumulated:.2f}"
            threshold_str = f"{threshold_usd:.2f}" if threshold_usd else "0.00"
            progress_str = f"{progress_percent:.1f}"

            return f"""<b>Payout Method:</b> THRESHOLD
├ Currency: {payout_currency}
├ Network: {payout_network}
├ Wallet: <code>{wallet_display}</code>
├ Threshold: ${threshold_str} USD
└ Progress: ${current_str} / ${threshold_str} ({progress_str}%)"""

        else:
            # Unknown strategy
            return f"<b>Payout Method:</b> {payout_strategy} (unknown)"

    def test_notification(self, chat_id: int, channel_title: str = "Test Channel") -> bool:
        """
        Send a test notification to verify setup

        Args:
            chat_id: Telegram user ID to send test to
            channel_title: Channel name for test message

        Returns:
            True if test successful, False otherwise
        """
        test_message = f"""🧪 <b>Test Notification</b>

This is a test notification for your channel: <b>{channel_title}</b>

If you receive this message, your notification settings are configured correctly!

You will receive notifications when:
• A customer subscribes to a tier
• A customer makes a donation

✅ Notification system is working!"""

        try:
            return self.telegram_client.send_message(
                chat_id=chat_id,
                text=test_message,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ [HANDLER] Test failed: {e}")
            return False
