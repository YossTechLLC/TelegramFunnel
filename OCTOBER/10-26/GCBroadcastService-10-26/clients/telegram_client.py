#!/usr/bin/env python3
"""
TelegramClient - Telegram Bot API wrapper for broadcast operations
Handles message sending with proper formatting and error handling
"""

import logging
import base64
import requests
from typing import Dict, Any, List

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
        self.bot_token = bot_token
        self.bot_username = bot_username
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger(__name__)

        # Test bot connection immediately
        try:
            response = requests.get(f"{self.api_base}/getMe", timeout=10)
            response.raise_for_status()
            bot_info = response.json()
            if bot_info.get('ok'):
                username = bot_info['result']['username']
                self.logger.info(f"🤖 TelegramClient initialized for @{username}")
            else:
                raise ValueError(f"Bot authentication failed: {bot_info}")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize bot: {e}")
            raise

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
            {'success': bool, 'error': str (if failed), 'message_id': int (if success)}
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
            inline_keyboard = []

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

                # Each button in its own row (vertical layout)
                inline_keyboard.append([{
                    "text": button_text,
                    "url": url
                }])

            if not inline_keyboard:
                error_msg = "No valid tier buttons to display"
                self.logger.warning(f"⚠️ {error_msg} for {chat_id}")
                return {'success': False, 'error': error_msg}

            # Prepare payload
            payload = {
                "chat_id": chat_id,
                "text": message_text,
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": inline_keyboard
                }
            }

            # Send message via direct HTTP
            self.logger.info(f"📤 Sending subscription message to {chat_id}")
            response = requests.post(
                f"{self.api_base}/sendMessage",
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            # Parse response
            result = response.json()
            if not result.get('ok'):
                error_msg = result.get('description', 'Unknown error')
                self.logger.error(f"❌ Telegram API error: {error_msg}")
                return {'success': False, 'error': error_msg}

            message_id = result['result']['message_id']
            self.logger.info(f"✅ Subscription message sent to {chat_id}, message_id: {message_id}")
            return {'success': True, 'error': None, 'message_id': message_id}

        except requests.exceptions.HTTPError as e:
            # Handle HTTP errors (403, 404, etc.)
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"

            if e.response.status_code == 403:
                error_msg = "Bot not admin or kicked from channel"
            elif e.response.status_code == 400:
                error_msg = f"Invalid request: {e.response.text}"

            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}", exc_info=True)
            return {'success': False, 'error': error_msg}

    def delete_message(
        self,
        chat_id: str,
        message_id: int,
        retry_on_rate_limit: bool = True
    ) -> Dict[str, Any]:
        """
        Delete a message from a Telegram chat with rate limit handling.

        Args:
            chat_id: Channel/chat ID where message exists
            message_id: Telegram message ID to delete
            retry_on_rate_limit: Whether to retry once on rate limit (default: True)

        Returns:
            {'success': bool, 'error': str or None, 'deleted': bool}

        Error Handling:
            - Message not found: Returns success=True, deleted=False (idempotent)
            - No permission: Returns success=False
            - Rate limit: Waits and retries once if retry_on_rate_limit=True

        Best Practices:
            - Add 100ms delay between deletions to avoid rate limits
            - Treat "message not found" as success (idempotent)
        """
        import time
        import re

        try:
            # Validate message_id
            if not message_id or message_id <= 0:
                self.logger.warning(f"⚠️ Invalid message_id: {message_id}")
                return {'success': False, 'error': 'Invalid message_id', 'deleted': False}

            # Prepare payload
            payload = {
                "chat_id": chat_id,
                "message_id": message_id
            }

            # Delete message via direct HTTP
            self.logger.info(f"🗑️ Deleting message {message_id} from {chat_id}")
            response = requests.post(
                f"{self.api_base}/deleteMessage",
                json=payload,
                timeout=10
            )

            # Parse response
            result = response.json()

            # Check if successful
            if result.get('ok'):
                self.logger.info(f"✅ Message {message_id} deleted from {chat_id}")
                return {'success': True, 'error': None, 'deleted': True}

            # Handle errors
            error_desc = result.get('description', 'Unknown error')
            error_lower = error_desc.lower()

            # Message already deleted - treat as success (idempotent)
            if "message to delete not found" in error_lower:
                self.logger.debug(f"⚠️ Message {message_id} already deleted from {chat_id}")
                return {'success': True, 'error': None, 'deleted': False}

            # No permission - log warning but don't fail
            if "not enough rights" in error_lower or "chat administrator" in error_lower:
                self.logger.warning(f"⚠️ No permission to delete message {message_id} from {chat_id}")
                return {'success': False, 'error': f"No permission: {error_desc}", 'deleted': False}

            # Rate limit with retry
            if "too many requests" in error_lower or "retry after" in error_lower:
                # Extract retry_after seconds from error message
                retry_after = 5  # Default
                match = re.search(r'retry after (\d+)', error_lower)
                if match:
                    retry_after = int(match.group(1))

                self.logger.warning(
                    f"⏱️ Rate limited when deleting message {message_id}, "
                    f"retry_after={retry_after}s"
                )

                if retry_on_rate_limit:
                    self.logger.info(f"⏱️ Waiting {retry_after}s before retry...")
                    time.sleep(retry_after)

                    # Retry once
                    self.logger.info(f"🔄 Retrying deletion of message {message_id}")
                    retry_response = requests.post(
                        f"{self.api_base}/deleteMessage",
                        json=payload,
                        timeout=10
                    )
                    retry_result = retry_response.json()

                    if retry_result.get('ok'):
                        self.logger.info(f"✅ Message {message_id} deleted on retry")
                        return {'success': True, 'error': None, 'deleted': True}
                    else:
                        retry_error = retry_result.get('description', 'Unknown error')
                        self.logger.error(f"❌ Retry failed: {retry_error}")
                        return {'success': False, 'error': f"Retry failed: {retry_error}", 'deleted': False}
                else:
                    return {'success': False, 'error': f"Rate limited: {error_desc}", 'deleted': False}

            # Other errors
            self.logger.error(f"❌ Cannot delete message {message_id} from {chat_id}: {error_desc}")
            return {'success': False, 'error': error_desc, 'deleted': False}

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            self.logger.error(f"❌ {error_msg} while deleting message {message_id}")
            return {'success': False, 'error': error_msg, 'deleted': False}

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"❌ {error_msg} while deleting message {message_id}", exc_info=True)
            return {'success': False, 'error': error_msg, 'deleted': False}

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
            {'success': bool, 'error': str (if failed), 'message_id': int (if success)}
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

            inline_keyboard = [[{
                "text": "💝 Donate to Support This Channel",
                "callback_data": callback_data
            }]]

            # Prepare payload
            payload = {
                "chat_id": chat_id,
                "text": message_text,
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": inline_keyboard
                }
            }

            # Send message via direct HTTP
            self.logger.info(f"📤 Sending donation message to {chat_id}")
            response = requests.post(
                f"{self.api_base}/sendMessage",
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            # Parse response
            result = response.json()
            if not result.get('ok'):
                error_msg = result.get('description', 'Unknown error')
                self.logger.error(f"❌ Telegram API error: {error_msg}")
                return {'success': False, 'error': error_msg}

            message_id = result['result']['message_id']
            self.logger.info(f"✅ Donation message sent to {chat_id}, message_id: {message_id}")
            return {'success': True, 'error': None, 'message_id': message_id}

        except requests.exceptions.HTTPError as e:
            # Handle HTTP errors (403, 404, etc.)
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"

            if e.response.status_code == 403:
                error_msg = "Bot not admin or kicked from channel"
            elif e.response.status_code == 400:
                error_msg = f"Invalid request: {e.response.text}"

            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}", exc_info=True)
            return {'success': False, 'error': error_msg}
