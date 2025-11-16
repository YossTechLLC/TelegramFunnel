#!/usr/bin/env python
"""
Telegram Client for GCSubscriptionMonitor
Handles Telegram Bot API operations for removing users from channels
"""
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import logging

logger = logging.getLogger(__name__)


class TelegramClient:
    """Wrapper for Telegram Bot API operations"""

    def __init__(self, bot_token: str):
        """
        Initialize Telegram client.

        Args:
            bot_token: Telegram bot token
        """
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        logger.info("🤖 Telegram client initialized")

    async def remove_user_from_channel(self, user_id: int, private_channel_id: int) -> bool:
        """
        Remove user from private channel using Telegram Bot API.
        Uses ban + immediate unban pattern to remove user while allowing future rejoins.

        Args:
            user_id: User's Telegram ID
            private_channel_id: Private channel ID to remove user from

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ban user from channel
            await self.bot.ban_chat_member(
                chat_id=private_channel_id,
                user_id=user_id
            )

            # Immediately unban to allow future rejoining if they pay again
            await self.bot.unban_chat_member(
                chat_id=private_channel_id,
                user_id=user_id,
                only_if_banned=True
            )

            logger.info(
                f"🚫 Successfully removed user {user_id} from channel {private_channel_id}"
            )
            return True

        except TelegramError as e:
            # Handle specific Telegram errors
            error_message = str(e)

            if "user not found" in error_message.lower() or "user is not a member" in error_message.lower():
                # User already left - consider this successful
                logger.info(
                    f"ℹ️ User {user_id} is no longer in channel {private_channel_id} "
                    f"(already left)"
                )
                return True

            elif "forbidden" in error_message.lower():
                # Bot lacks permissions
                logger.error(
                    f"❌ Bot lacks permission to remove user {user_id} "
                    f"from channel {private_channel_id}"
                )
                return False

            elif "chat not found" in error_message.lower():
                # Channel doesn't exist or bot is not a member
                logger.error(
                    f"❌ Channel {private_channel_id} not found or bot is not a member"
                )
                return False

            else:
                # Other Telegram API errors
                logger.error(
                    f"❌ Telegram API error removing user {user_id} "
                    f"from channel {private_channel_id}: {e}"
                )
                return False

        except Exception as e:
            # Unexpected errors
            logger.error(
                f"❌ Unexpected error removing user {user_id} "
                f"from channel {private_channel_id}: {e}",
                exc_info=True
            )
            return False

    def remove_user_sync(self, user_id: int, private_channel_id: int) -> bool:
        """
        Synchronous wrapper for remove_user_from_channel.
        Needed for Flask route handlers that aren't async.

        Args:
            user_id: User's Telegram ID
            private_channel_id: Private channel ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self.remove_user_from_channel(user_id, private_channel_id)
            )

            loop.close()
            return result

        except Exception as e:
            logger.error(f"❌ Error in synchronous wrapper: {e}", exc_info=True)
            return False
