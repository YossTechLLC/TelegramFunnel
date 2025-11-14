#!/usr/bin/env python
"""
🤖 Telegram Client for GCNotificationService
Wraps Telegram Bot API for sending messages
"""
from telegram import Bot
from telegram.error import TelegramError, Forbidden, BadRequest
import logging
import asyncio

logger = logging.getLogger(__name__)


class TelegramClient:
    """Wraps Telegram Bot API for sending messages"""

    def __init__(self, bot_token: str):
        """
        Initialize Telegram client

        Args:
            bot_token: Telegram Bot API token
        """
        if not bot_token:
            raise ValueError("Bot token is required")

        self.bot = Bot(token=bot_token)
        logger.info("🤖 [TELEGRAM] Client initialized")

    def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = 'HTML',
        disable_web_page_preview: bool = True
    ) -> bool:
        """
        Send message via Telegram Bot API

        Args:
            chat_id: Telegram user ID to send to
            text: Message text
            parse_mode: Parsing mode ('HTML', 'Markdown', or None)
            disable_web_page_preview: Disable link previews

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            logger.info(f"📤 [TELEGRAM] Sending message to chat_id {chat_id}")

            # Use synchronous wrapper for python-telegram-bot >= 20.x
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(
                self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
            )

            loop.close()

            logger.info(f"✅ [TELEGRAM] Message delivered to {chat_id}")
            return True

        except Forbidden as e:
            logger.warning(f"🚫 [TELEGRAM] Bot blocked by user {chat_id}: {e}")
            # User has blocked the bot - this is expected, don't retry
            return False

        except BadRequest as e:
            logger.error(f"❌ [TELEGRAM] Invalid request for {chat_id}: {e}")
            # Invalid chat_id or message format
            return False

        except TelegramError as e:
            logger.error(f"❌ [TELEGRAM] Telegram API error: {e}")
            # Network issues, rate limits, etc.
            return False

        except Exception as e:
            logger.error(f"❌ [TELEGRAM] Unexpected error: {e}", exc_info=True)
            return False
