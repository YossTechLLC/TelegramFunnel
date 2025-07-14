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
        self.tele_open_list = []
        self.tele_info_open_map = {}
    
    @staticmethod
    def encode_id(i):
        return base64.urlsafe_b64encode(str(i).encode()).decode()
    
    @staticmethod
    def decode_hash(s):
        return base64.urlsafe_b64decode(s.encode()).decode()
    
    def fetch_tele_open_list(self):
        self.tele_open_list.clear()
        self.tele_info_open_map.clear()
        
        new_list, new_map = self.db_manager.fetch_tele_open_list()
        self.tele_open_list.extend(new_list)
        self.tele_info_open_map.update(new_map)
    
    @staticmethod
    def build_menu_buttons(buttons_config):
        buttons = []
        for b in buttons_config:
            if "callback_data" in b:
                buttons.append(InlineKeyboardButton(text=b["text"], callback_data=b["callback_data"]))
            elif "url" in b:
                buttons.append(InlineKeyboardButton(text=b["text"], url=b["url"]))
        return InlineKeyboardMarkup([buttons])
    
    def broadcast_hash_links(self):
        if not self.tele_open_list:
            self.fetch_tele_open_list()
        
        for chat_id in self.tele_open_list:
            data = self.tele_info_open_map.get(chat_id, {})
            base_hash = self.encode_id(chat_id)
            buttons_cfg = []
            
            # Add subscription tier buttons
            for idx in (1, 2, 3):
                price = data.get(f"sub_{idx}")
                days = data.get(f"sub_{idx}_time")
                if price is None or days is None:
                    continue
                safe_sub = str(price).replace(".", "d")
                # Include subscription time in token: {hash}_{price}_{time}
                token = f"{base_hash}_{safe_sub}_{days}"
                url = f"https://t.me/{self.bot_username}?start={token}"
                buttons_cfg.append({"text": f"${price} for {days} days", "url": url})
            
            # Add donation button
            donation_token = f"{base_hash}_DONATE"
            donation_url = f"https://t.me/{self.bot_username}?start={donation_token}"
            buttons_cfg.append({"text": "💝 Donate", "url": donation_url})
            
            if not buttons_cfg:
                continue
            
            reply_markup = self.build_menu_buttons(buttons_cfg)
            try:
                resp = requests.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "<b>Choose your Subscription Tier</b>",
                        "parse_mode": "HTML",
                        "reply_markup": reply_markup.to_dict(),
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                msg_id = resp.json()["result"]["message_id"]
                del_url = f"https://api.telegram.org/bot{self.bot_token}/deleteMessage"
                asyncio.get_event_loop().call_later(
                    60,
                    lambda: requests.post(
                        del_url,
                        json={"chat_id": chat_id, "message_id": msg_id},
                        timeout=5,
                    ),
                )
            except Exception as e:
                logging.error("send error to %s: %s", chat_id, e)