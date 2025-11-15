#!/usr/bin/env python
import requests
import base64
import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from database import DatabaseManager

logger = logging.getLogger(__name__)

class BroadcastManager:
    def __init__(self, bot_token: str, bot_username: str, db_manager: DatabaseManager):
        self.bot_token = bot_token
        self.bot_username = bot_username
        self.db_manager = db_manager
        self.bot = Bot(token=bot_token)  # NEW: Add Bot instance for async operations
        self.open_channel_list = []
        self.open_channel_info_map = {}
    
    @staticmethod
    def encode_id(i):
        return base64.urlsafe_b64encode(str(i).encode()).decode()
    
    @staticmethod
    def decode_hash(s):
        return base64.urlsafe_b64decode(s.encode()).decode()
    
    def fetch_open_channel_list(self):
        self.open_channel_list.clear()
        self.open_channel_info_map.clear()
        
        new_list, new_map = self.db_manager.fetch_open_channel_list()
        self.open_channel_list.extend(new_list)
        self.open_channel_info_map.update(new_map)
    
    @staticmethod
    def build_menu_buttons(buttons_config):
        buttons = []
        for b in buttons_config:
            if "callback_data" in b:
                buttons.append(InlineKeyboardButton(text=b["text"], callback_data=b["callback_data"]))
            elif "url" in b:
                buttons.append(InlineKeyboardButton(text=b["text"], url=b["url"]))
        # Create vertical layout - each button gets its own row
        return InlineKeyboardMarkup([[button] for button in buttons])
    
    async def delete_message_safe(
        self,
        chat_id: str,
        message_id: int,
        retry_on_rate_limit: bool = True
    ) -> bool:
        """
        Safely delete a message with rate limit handling.

        Args:
            chat_id: Channel ID
            message_id: Telegram message ID
            retry_on_rate_limit: Whether to retry once on rate limit (default: True)

        Returns:
            True if deleted or already gone, False if error

        Best Practices:
            - Add 100ms delay between deletions to avoid rate limits
            - Treats "message not found" as success (idempotent)
            - Handles RetryAfter errors with automatic retry
        """
        try:
            from telegram.error import BadRequest, RetryAfter

            # Validate message_id
            if not message_id or message_id <= 0:
                logger.warning(f"⚠️ Invalid message_id: {message_id}")
                return False

            await self.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )
            logger.info(f"🗑️ Deleted message {message_id} from {chat_id}")
            return True

        except BadRequest as e:
            error_str = str(e).lower()
            if "message to delete not found" in error_str:
                logger.debug(f"⚠️ Message {message_id} already deleted from {chat_id}")
                return True  # Treat as success (idempotent)

            if "not enough rights" in error_str or "chat administrator" in error_str:
                logger.warning(f"⚠️ No permission to delete message {message_id} from {chat_id}")
                return False

            logger.error(f"❌ Cannot delete message {message_id} from {chat_id}: {e}")
            return False

        except RetryAfter as e:
            if retry_on_rate_limit:
                retry_after = e.retry_after
                logger.warning(
                    f"⏱️ Rate limited when deleting message {message_id}, "
                    f"waiting {retry_after}s..."
                )
                await asyncio.sleep(retry_after)

                # Retry once
                logger.info(f"🔄 Retrying deletion of message {message_id}")
                try:
                    await self.bot.delete_message(
                        chat_id=chat_id,
                        message_id=message_id
                    )
                    logger.info(f"✅ Message {message_id} deleted on retry")
                    return True
                except Exception as retry_err:
                    logger.error(f"❌ Retry failed: {retry_err}")
                    return False
            else:
                logger.warning(f"⏱️ Rate limited, skipping retry for message {message_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error deleting message {message_id} from {chat_id}: {e}")
            return False

    async def broadcast_hash_links(self):
        """
        Broadcast subscription links to open channels.

        NEW BEHAVIOR:
        - Deletes old subscription message before sending new one
        - Tracks message ID of new message for future deletion

        Note: Donation buttons are no longer included in open channel broadcasts.
        Donations are now handled in closed channels. See closed_channel_manager.py.
        """
        if not self.open_channel_list:
            self.fetch_open_channel_list()

        for chat_id in self.open_channel_list:
            data = self.open_channel_info_map.get(chat_id, {})

            # NEW: Get old message ID for deletion
            message_ids = self.db_manager.get_last_broadcast_message_ids(chat_id)
            old_message_id = message_ids.get('last_open_message_id')

            # NEW: Delete old message if exists
            if old_message_id:
                logger.info(f"🗑️ Deleting old message {old_message_id} from {chat_id}")
                await self.delete_message_safe(chat_id, old_message_id)

            base_hash = self.encode_id(chat_id)
            buttons_cfg = []

            # Add subscription tier buttons with emojis
            tier_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
            for idx in (1, 2, 3):
                price = data.get(f"sub_{idx}_price")
                days = data.get(f"sub_{idx}_time")
                if price is None or days is None:
                    continue
                safe_sub = str(price).replace(".", "d")
                # Include subscription time in token: {hash}_{price}_{time}
                token = f"{base_hash}_{safe_sub}_{days}"
                url = f"https://t.me/{self.bot_username}?start={token}"
                emoji = tier_emojis.get(idx, "💰")
                buttons_cfg.append({"text": f"{emoji} ${price} for {days} days", "url": url})

            # REMOVED: Donation button migrated to closed channels
            # See: closed_channel_manager.py for new donation implementation
            # See: DONATION_REWORK.md for architecture details
            # Donations are now handled exclusively in closed channels via inline keypad
            # donation_token = f"{base_hash}_DONATE"
            # donation_url = f"https://t.me/{self.bot_username}?start={donation_token}"
            # buttons_cfg.append({"text": "💝 Donate", "url": donation_url})

            if not buttons_cfg:
                continue

            # Create dynamic message using channel titles and descriptions
            open_channel_title = data.get("open_channel_title", "Channel")
            open_channel_description = data.get("open_channel_description", "open channel")
            closed_channel_title = data.get("closed_channel_title", "Premium Channel")
            closed_channel_description = data.get("closed_channel_description", "exclusive content")

            welcome_message = (
                f"Hello, welcome to <b>{open_channel_title}: {open_channel_description}</b>\n\n"
                f"Choose your Subscription Tier to gain access to <b>{closed_channel_title}: {closed_channel_description}</b>."
            )

            reply_markup = self.build_menu_buttons(buttons_cfg)
            try:
                # NEW: Send new message using async Bot
                message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=welcome_message,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

                # NEW: Update message ID in database
                new_message_id = message.message_id
                self.db_manager.update_broadcast_message_ids(
                    open_channel_id=chat_id,
                    open_message_id=new_message_id
                )

                logger.info(
                    f"✅ Sent subscription message to {chat_id} "
                    f"(message_id={new_message_id})"
                )

            except Exception as e:
                logging.error(f"❌ Send error to {chat_id}: {e}")