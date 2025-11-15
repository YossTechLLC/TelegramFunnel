#!/usr/bin/env python
import requests
import asyncio

class MessageUtils:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
    
    def send_message(self, chat_id: int, html_text: str) -> None:
        """Send a message to a Telegram chat."""
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
        except Exception as e:
            print(f"❌ send error to {chat_id}: {e}")