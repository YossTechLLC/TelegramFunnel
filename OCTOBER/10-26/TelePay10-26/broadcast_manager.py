#!/usr/bin/env python
import requests
import base64
import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import DatabaseManager

logger = logging.getLogger(__name__)

class BroadcastManager:
    def __init__(self, bot_token: str, bot_username: str, db_manager: DatabaseManager):
        self.bot_token = bot_token
        self.bot_username = bot_username
        self.db_manager = db_manager
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
    
    def broadcast_hash_links(self):
        """
        Broadcast subscription links to open channels.

        Note: Donation buttons are no longer included in open channel broadcasts.
        Donations are now handled in closed channels. See closed_channel_manager.py.
        """
        if not self.open_channel_list:
            self.fetch_open_channel_list()

        for chat_id in self.open_channel_list:
            data = self.open_channel_info_map.get(chat_id, {})
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
                resp = requests.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": welcome_message,
                        "parse_mode": "HTML",
                        "reply_markup": reply_markup.to_dict(),
                    },
                    timeout=10,
                )
                resp.raise_for_status()
            except Exception as e:
                logging.error("send error to %s: %s", chat_id, e)