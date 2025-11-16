#!/usr/bin/env python
"""
Subscription Manager for automated expiration handling.
Runs background task to check for expired subscriptions and remove users from channels.
"""
import asyncio
import logging
from datetime import datetime, date, time
from typing import List, Tuple, Optional
from telegram import Bot
from telegram.error import TelegramError
from database import DatabaseManager

class SubscriptionManager:
    def __init__(self, bot_token: str, db_manager: DatabaseManager):
        """
        Initialize the Subscription Manager.
        
        Args:
            bot_token: Telegram bot token for API calls
            db_manager: Database manager instance for database operations
        """
        self.bot_token = bot_token
        self.db_manager = db_manager
        self.bot = Bot(token=bot_token)
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        
    async def start_monitoring(self):
        """Start the subscription monitoring background task."""
        if self.is_running:
            self.logger.warning("Subscription monitoring is already running")
            return
            
        self.is_running = True
        self.logger.info("🕐 Starting subscription expiration monitoring (60-second intervals)")
        
        while self.is_running:
            try:
                await self.check_expired_subscriptions()
                await asyncio.sleep(60)  # Wait 60 seconds before next check
            except Exception as e:
                self.logger.error(f"Error in subscription monitoring loop: {e}")
                await asyncio.sleep(60)  # Continue loop even after errors
    
    def stop_monitoring(self):
        """Stop the subscription monitoring task."""
        self.is_running = False
        self.logger.info("⏹️ Stopping subscription expiration monitoring")
    
    async def check_expired_subscriptions(self):
        """Check for expired subscriptions and process them."""
        try:
            # Get all active subscriptions with expiration data
            expired_subscriptions = self.fetch_expired_subscriptions()
            
            if not expired_subscriptions:
                self.logger.debug("No expired subscriptions found")
                return
            
            self.logger.info(f"🔍 Found {len(expired_subscriptions)} expired subscriptions to process")
            
            # Process each expired subscription
            for subscription in expired_subscriptions:
                user_id, private_channel_id, expire_time, expire_date = subscription
                
                try:
                    # Remove user from channel
                    success = await self.remove_user_from_channel(user_id, private_channel_id)
                    
                    if success:
                        # Update database to mark subscription as inactive
                        self.deactivate_subscription(user_id, private_channel_id)
                        self.logger.info(f"✅ Successfully processed expired subscription: user {user_id} removed from channel {private_channel_id}")
                    else:
                        self.logger.warning(f"❌ Failed to remove user {user_id} from channel {private_channel_id}, but marking as inactive")
                        # Still mark as inactive even if removal failed
                        self.deactivate_subscription(user_id, private_channel_id)
                        
                except Exception as e:
                    self.logger.error(f"❌ Error processing expired subscription for user {user_id}, channel {private_channel_id}: {e}")
                    
        except Exception as e:
            self.logger.error(f"❌ Error checking expired subscriptions: {e}")
    
    def fetch_expired_subscriptions(self) -> List[Tuple[int, int, str, str]]:
        """
        Fetch all expired subscriptions from database.
        
        Returns:
            List of tuples: (user_id, private_channel_id, expire_time, expire_date)
        """
        expired_subscriptions = []
        
        try:
            with self.db_manager.get_connection() as conn, conn.cursor() as cur:
                # Query active subscriptions with expiration data
                query = """
                    SELECT user_id, private_channel_id, expire_time, expire_date
                    FROM private_channel_users_database 
                    WHERE is_active = true 
                    AND expire_time IS NOT NULL 
                    AND expire_date IS NOT NULL
                """
                
                cur.execute(query)
                results = cur.fetchall()
                
                current_datetime = datetime.now()
                
                for row in results:
                    user_id, private_channel_id, expire_time_str, expire_date_str = row
                    
                    try:
                        # Parse expiration time and date
                        if isinstance(expire_date_str, str):
                            expire_date_obj = datetime.strptime(expire_date_str, '%Y-%m-%d').date()
                        else:
                            expire_date_obj = expire_date_str
                            
                        if isinstance(expire_time_str, str):
                            expire_time_obj = datetime.strptime(expire_time_str, '%H:%M:%S').time()
                        else:
                            expire_time_obj = expire_time_str
                        
                        # Combine date and time
                        expire_datetime = datetime.combine(expire_date_obj, expire_time_obj)
                        
                        # Check if subscription has expired
                        if current_datetime > expire_datetime:
                            expired_subscriptions.append((user_id, private_channel_id, expire_time_str, expire_date_str))
                            self.logger.debug(f"Found expired subscription: user {user_id}, channel {private_channel_id}, expired at {expire_datetime}")
                    
                    except Exception as e:
                        self.logger.error(f"Error parsing expiration data for user {user_id}: {e}")
                        continue
                        
        except Exception as e:
            self.logger.error(f"Database error fetching expired subscriptions: {e}")
            
        return expired_subscriptions
    
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
    
    def deactivate_subscription(self, user_id: int, private_channel_id: int) -> bool:
        """
        Mark subscription as inactive in database.
        
        Args:
            user_id: User's Telegram ID
            private_channel_id: Private channel ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_manager.get_connection() as conn, conn.cursor() as cur:
                update_query = """
                    UPDATE private_channel_users_database 
                    SET is_active = false 
                    WHERE user_id = %s AND private_channel_id = %s AND is_active = true
                """
                
                cur.execute(update_query, (user_id, private_channel_id))
                rows_affected = cur.rowcount
                
                if rows_affected > 0:
                    self.logger.info(f"📝 Marked subscription as inactive: user {user_id}, channel {private_channel_id}")
                    return True
                else:
                    self.logger.warning(f"⚠️ No active subscription found to deactivate: user {user_id}, channel {private_channel_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"❌ Database error deactivating subscription for user {user_id}, channel {private_channel_id}: {e}")
            return False