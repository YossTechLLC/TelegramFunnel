#!/usr/bin/env python
import requests
import asyncio

class MessageUtils:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
    
    def send_message(self, chat_id: int, html_text: str) -> None:
        """Send a message to a Telegram chat with auto-deletion after 60 seconds."""
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": html_text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            r.raise_for_status()
            msg_id = r.json()["result"]["message_id"]
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
            print(f"❌ send error to {chat_id}: {e}")