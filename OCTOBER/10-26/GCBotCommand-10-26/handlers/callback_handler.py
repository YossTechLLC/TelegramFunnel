#!/usr/bin/env python
"""
Callback Handler for GCBotCommand
Processes button callback queries
"""
from typing import Dict, Any
from utils.http_client import HTTPClient
import logging
import requests

logger = logging.getLogger(__name__)

class CallbackHandler:
    """Handles Telegram callback queries (button clicks)"""

    def __init__(self, db_manager, config):
        self.db = db_manager
        self.config = config
        self.bot_token = config['bot_token']
        self.http_client = HTTPClient()

    def handle_callback(self, update_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Route callback queries to appropriate handlers

        Callback patterns:
        - CMD_DATABASE → Start database flow
        - CMD_GATEWAY → Launch payment gateway
        - TRIGGER_PAYMENT → Process payment
        - EDIT_* → Database form editing
        - SAVE_ALL_CHANGES → Save database changes
        - etc.
        """
        callback_query = update_data['callback_query']
        callback_data = callback_query['data']
        chat_id = callback_query['message']['chat']['id']
        user_id = callback_query['from']['id']
        message_id = callback_query['message']['message_id']

        logger.info(f"🔘 Callback: {callback_data} from user {user_id}")

        # Answer callback query first (required by Telegram)
        self._answer_callback_query(callback_query['id'])

        # Route based on callback_data
        if callback_data == "CMD_DATABASE":
            return self._handle_database_start(chat_id, user_id)

        elif callback_data == "CMD_GATEWAY":
            return self._handle_payment_gateway(chat_id, user_id)

        elif callback_data == "TRIGGER_PAYMENT":
            return self._handle_trigger_payment(chat_id, user_id)

        elif callback_data.startswith("EDIT_"):
            return self._handle_database_edit(chat_id, user_id, message_id, callback_data)

        elif callback_data == "SAVE_ALL_CHANGES":
            return self._handle_save_changes(chat_id, user_id, message_id)

        elif callback_data == "CANCEL_EDIT":
            return self._handle_cancel_edit(chat_id, user_id, message_id)

        elif callback_data.startswith("TOGGLE_TIER_"):
            return self._handle_toggle_tier(chat_id, user_id, message_id, callback_data)

        elif callback_data == "BACK_TO_MAIN":
            return self._handle_back_to_main(chat_id, user_id, message_id)

        else:
            logger.warning(f"⚠️ Unknown callback_data: {callback_data}")
            return {"status": "ok"}

    def _handle_database_start(self, chat_id: int, user_id: int) -> Dict[str, str]:
        """Start database configuration flow"""
        from utils.message_formatter import MessageFormatter

        # Initialize database conversation state
        self.db.save_conversation_state(user_id, 'database', {
            'state': 'awaiting_channel_id'
        })

        message_text = MessageFormatter.format_database_menu_message()

        return self._send_message(chat_id, message_text, parse_mode='Markdown')

    def _handle_payment_gateway(self, chat_id: int, user_id: int) -> Dict[str, str]:
        """Handle CMD_GATEWAY callback"""
        # Check if user has payment context
        payment_state = self.db.get_conversation_state(user_id, 'payment')

        if not payment_state:
            return self._send_message(chat_id, "❌ No payment context found. Please start from a subscription link.")

        # Call GCPaymentGateway
        return self._create_payment_invoice(chat_id, user_id, payment_state)

    def _handle_trigger_payment(self, chat_id: int, user_id: int) -> Dict[str, str]:
        """Handle TRIGGER_PAYMENT callback"""
        # Same as CMD_GATEWAY
        return self._handle_payment_gateway(chat_id, user_id)

    def _create_payment_invoice(self, chat_id: int, user_id: int, payment_state: Dict) -> Dict[str, str]:
        """Create payment invoice via GCPaymentGateway"""
        from utils.message_formatter import MessageFormatter

        payment_url = self.config['gcpaymentgateway_url']

        payload = {
            "user_id": user_id,
            "amount": payment_state['price'],
            "open_channel_id": payment_state['channel_id'],
            "subscription_time_days": payment_state['time'],
            "payment_type": payment_state['payment_type']
        }

        response = self.http_client.post(f"{payment_url}/create-invoice", payload)

        if response and response.get('success'):
            invoice_url = response['invoice_url']

            keyboard = {
                "inline_keyboard": [
                    [{"text": "💳 Pay Now", "web_app": {"url": invoice_url}}]
                ]
            }

            message_text = MessageFormatter.format_payment_invoice_message(
                payment_state['price'], payment_state['time']
            )

            return self._send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            return self._send_message(chat_id, "❌ Failed to create payment invoice")

    def _handle_database_edit(self, chat_id: int, user_id: int, message_id: int, callback_data: str) -> Dict[str, str]:
        """Handle database form editing callbacks"""
        from handlers.database_handler import DatabaseFormHandler

        db_form_handler = DatabaseFormHandler(self.db, self.config)
        return db_form_handler.handle_edit_callback(chat_id, user_id, message_id, callback_data)

    def _handle_save_changes(self, chat_id: int, user_id: int, message_id: int) -> Dict[str, str]:
        """Save database changes"""
        from handlers.database_handler import DatabaseFormHandler

        db_form_handler = DatabaseFormHandler(self.db, self.config)
        return db_form_handler.save_changes(chat_id, user_id, message_id)

    def _handle_cancel_edit(self, chat_id: int, user_id: int, message_id: int) -> Dict[str, str]:
        """Cancel database editing"""
        # Clear conversation state
        self.db.clear_conversation_state(user_id, 'database')

        return self._edit_message(chat_id, message_id, "❌ Editing cancelled. No changes were saved.")

    def _handle_toggle_tier(self, chat_id: int, user_id: int, message_id: int, callback_data: str) -> Dict[str, str]:
        """Handle tier enable/disable toggle"""
        from handlers.database_handler import DatabaseFormHandler

        db_form_handler = DatabaseFormHandler(self.db, self.config)
        return db_form_handler.toggle_tier(chat_id, user_id, message_id, callback_data)

    def _handle_back_to_main(self, chat_id: int, user_id: int, message_id: int) -> Dict[str, str]:
        """Navigate back to main database form"""
        from handlers.database_handler import DatabaseFormHandler

        db_form_handler = DatabaseFormHandler(self.db, self.config)
        return db_form_handler.show_main_form(chat_id, user_id, message_id)

    def _answer_callback_query(self, callback_query_id: str) -> None:
        """Answer callback query (required by Telegram)"""
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id},
                timeout=5
            )
        except Exception as e:
            logger.error(f"❌ Error answering callback query: {e}")

    def _send_message(self, chat_id: int, text: str, **kwargs) -> Dict[str, str]:
        """Send message via Telegram Bot API"""
        payload = {
            "chat_id": chat_id,
            "text": text
        }

        if 'reply_markup' in kwargs:
            payload['reply_markup'] = kwargs['reply_markup']
        if 'parse_mode' in kwargs:
            payload['parse_mode'] = kwargs['parse_mode']

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"✅ Message sent to chat_id {chat_id}")
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return {"status": "error"}

    def _edit_message(self, chat_id: int, message_id: int, text: str, **kwargs) -> Dict[str, str]:
        """Edit existing message"""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }

        if 'reply_markup' in kwargs:
            payload['reply_markup'] = kwargs['reply_markup']
        if 'parse_mode' in kwargs:
            payload['parse_mode'] = kwargs['parse_mode']

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/editMessageText",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"✅ Message edited in chat_id {chat_id}")
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"❌ Error editing message: {e}")
            return {"status": "error"}
