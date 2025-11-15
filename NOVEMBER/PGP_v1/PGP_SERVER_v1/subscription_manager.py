#!/usr/bin/env python
"""
Subscription Manager for automated expiration handling.
Runs background task to check for expired subscriptions and remove users from channels.

Architecture:
- Delegates all database operations to DatabaseManager (single source of truth for SQL)
- Handles Telegram Bot API calls directly for removing users from channels
- Runs as background async task checking for expirations at regular intervals
"""
import asyncio
import logging
from telegram import Bot
from telegram.error import TelegramError
from database import DatabaseManager

class SubscriptionManager:
    """
    Subscription Manager for automated expiration handling.

    Orchestrates background monitoring of expired subscriptions:
    - Fetches expired subscriptions via DatabaseManager (single source of truth)
    - Removes users from Telegram channels via Bot API
    - Updates subscription status via DatabaseManager

    Architecture Pattern:
    - Background task: Runs every 60 seconds checking for expirations
    - Database delegation: All SQL queries handled by DatabaseManager
    - Telegram API: Direct bot.ban_chat_member() + unban for user removal
    """

    def __init__(self, bot_token: str, db_manager: DatabaseManager, check_interval: int = 60):
        """
        Initialize the Subscription Manager.

        Args:
            bot_token: Telegram bot token for API calls
            db_manager: Database manager instance (single source of truth for SQL)
            check_interval: Seconds between expiration checks (default: 60)
        """
        self.bot_token = bot_token
        self.db_manager = db_manager
        self.bot = Bot(token=bot_token)
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        self.check_interval = check_interval
        
    async def start_monitoring(self):
        """Start the subscription monitoring background task."""
        if self.is_running:
            self.logger.warning("Subscription monitoring is already running")
            return

        self.is_running = True
        self.logger.info(
            f"🕐 Starting subscription expiration monitoring "
            f"({self.check_interval}-second intervals)"
        )

        while self.is_running:
            try:
                stats = await self.check_expired_subscriptions()

                # Log warning if high failure rate
                if stats['expired_count'] > 0:
                    failure_rate = (stats['failed_count'] / stats['expired_count']) * 100
                    if failure_rate > 10:  # More than 10% failures
                        self.logger.warning(
                            f"⚠️ High failure rate: {failure_rate:.1f}% "
                            f"({stats['failed_count']}/{stats['expired_count']})"
                        )

                await asyncio.sleep(self.check_interval)  # Use configurable interval

            except Exception as e:
                self.logger.error(f"Error in subscription monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)  # Continue loop even after errors
    
    def stop_monitoring(self):
        """Stop the subscription monitoring task."""
        self.is_running = False
        self.logger.info("⏹️ Stopping subscription expiration monitoring")
    
    async def check_expired_subscriptions(self):
        """
        Check for expired subscriptions and process them.

        Returns:
            Dict with processing statistics:
            {
                "expired_count": int,     # Total found
                "processed_count": int,   # Successfully processed
                "failed_count": int       # Failed to process
            }
        """
        try:
            # Get all active subscriptions with expiration data (delegate to DatabaseManager)
            expired_subscriptions = self.db_manager.fetch_expired_subscriptions()

            expired_count = len(expired_subscriptions)

            if not expired_subscriptions:
                self.logger.debug("No expired subscriptions found")
                return {"expired_count": 0, "processed_count": 0, "failed_count": 0}

            self.logger.info(f"🔍 Found {expired_count} expired subscriptions to process")

            processed_count = 0
            failed_count = 0

            # Process each expired subscription
            for subscription in expired_subscriptions:
                user_id, private_channel_id, expire_time, expire_date = subscription

                try:
                    # Remove user from channel
                    success = await self.remove_user_from_channel(user_id, private_channel_id)

                    # Deactivate in database (delegate to DatabaseManager)
                    if success:
                        self.db_manager.deactivate_subscription(user_id, private_channel_id)
                        processed_count += 1
                        self.logger.info(
                            f"✅ Successfully processed: user {user_id}, channel {private_channel_id}"
                        )
                    else:
                        # Still mark as inactive even if removal failed
                        self.db_manager.deactivate_subscription(user_id, private_channel_id)
                        failed_count += 1
                        self.logger.warning(
                            f"⚠️ Removal failed but marked inactive: user {user_id}"
                        )

                except Exception as e:
                    failed_count += 1
                    self.logger.error(
                        f"❌ Error processing expired subscription: "
                        f"user {user_id}, channel {private_channel_id}: {e}"
                    )

            # Log summary statistics
            self.logger.info(
                f"📊 Expiration check complete: "
                f"{expired_count} found, {processed_count} processed, {failed_count} failed"
            )

            return {
                "expired_count": expired_count,
                "processed_count": processed_count,
                "failed_count": failed_count
            }

        except Exception as e:
            self.logger.error(f"❌ Error checking expired subscriptions: {e}")
            return {"expired_count": 0, "processed_count": 0, "failed_count": 0}

    async def remove_user_from_channel(self, user_id: int, private_channel_id: int) -> bool:
        """
        Remove user from private channel using Telegram Bot API.
        
        Args:
            user_id: User's Telegram ID
            private_channel_id: Private channel ID to remove user from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use ban_chat_member to remove user from channel
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
            
            self.logger.info(f"🚫 Successfully removed user {user_id} from channel {private_channel_id}")
            return True
            
        except TelegramError as e:
            if "Bad Request: user not found" in str(e) or "user is not a member" in str(e):
                self.logger.info(f"ℹ️ User {user_id} is no longer in channel {private_channel_id} (already left)")
                return True  # Consider this successful since user is already gone
            elif "Forbidden" in str(e):
                self.logger.error(f"❌ Bot lacks permission to remove user {user_id} from channel {private_channel_id}")
                return False
            else:
                self.logger.error(f"❌ Telegram API error removing user {user_id} from channel {private_channel_id}: {e}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Unexpected error removing user {user_id} from channel {private_channel_id}: {e}")
            return False