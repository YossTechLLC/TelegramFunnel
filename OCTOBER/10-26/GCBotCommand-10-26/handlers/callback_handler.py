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

        elif callback_data.startswith("donate_start_"):
            return self._handle_donate_start(chat_id, user_id, callback_data, callback_query)

        elif callback_data.startswith("donate_"):
            # All keypad callbacks: donate_digit_*, donate_backspace, donate_clear, donate_confirm, donate_cancel, donate_noop
            return self._handle_donate_keypad(chat_id, user_id, callback_data, callback_query)

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

    def _handle_donate_start(self, chat_id: int, user_id: int, callback_data: str, callback_query: Dict) -> Dict[str, str]:
        """
        Handle donate_start callback - forward to GCDonationHandler service.

        This method is triggered when a user clicks the "💝 Donate" button
        in a closed channel's broadcast message.

        Args:
            chat_id: Chat ID where callback originated
            user_id: User ID who clicked the button
            callback_data: Format "donate_start_{open_channel_id}"
            callback_query: Full callback query object from Telegram

        Returns:
            {"status": "ok"} on success, {"status": "error"} on failure
        """
        # Extract open_channel_id from callback_data
        # Format: "donate_start_-1003202734748" → "-1003202734748"
        open_channel_id = callback_data.replace("donate_start_", "")

        logger.info(f"💝 Donate button clicked: user={user_id}, channel={open_channel_id}")

        # Get GCDonationHandler URL from config
        donation_handler_url = self.config.get('gcdonationhandler_url')

        if not donation_handler_url:
            logger.error("❌ GCDonationHandler URL not configured in Secret Manager")
            return self._send_message(
                chat_id,
                "❌ Donation service temporarily unavailable. Please try again later."
            )

        # Prepare payload for GCDonationHandler /start-donation-input endpoint
        payload = {
            "user_id": user_id,
            "chat_id": chat_id,
            "open_channel_id": open_channel_id,
            "callback_query_id": callback_query['id']
        }

        # Call GCDonationHandler service
        try:
            logger.info(f"🌐 Calling GCDonationHandler: {donation_handler_url}/start-donation-input")

            response = self.http_client.post(
                f"{donation_handler_url}/start-donation-input",
                payload
            )

            if response and response.get('success'):
                logger.info(f"✅ Donation flow started successfully for user {user_id}")
                return {"status": "ok"}
            else:
                error = response.get('error', 'Unknown error') if response else 'No response from service'
                logger.error(f"❌ GCDonationHandler returned error: {error}")

                return self._send_message(
                    chat_id,
                    "❌ Failed to start donation flow. Please try again or contact support."
                )

        except Exception as e:
            logger.error(f"❌ HTTP error calling GCDonationHandler: {e}", exc_info=True)

            return self._send_message(
                chat_id,
                "❌ Service error. Please try again in a few moments."
            )

    def _handle_donate_keypad(self, chat_id: int, user_id: int, callback_data: str, callback_query: Dict) -> Dict[str, str]:
        """
        Handle keypad callback - forward to GCDonationHandler service.

        This method handles all numeric keypad interactions during donation input:
        - donate_digit_0 through donate_digit_9
        - donate_digit_. (decimal point)
        - donate_backspace
        - donate_clear
        - donate_confirm
        - donate_cancel
        - donate_noop (display-only button)

        Args:
            chat_id: Chat ID where callback originated
            user_id: User ID who clicked the button
            callback_data: Keypad action (e.g., "donate_digit_5", "donate_confirm")
            callback_query: Full callback query object from Telegram

        Returns:
            {"status": "ok"} - always returns success to avoid user-facing errors
        """
        logger.info(f"🔢 Keypad input: user={user_id}, action={callback_data}")

        # Get GCDonationHandler URL from config
        donation_handler_url = self.config.get('gcdonationhandler_url')

        if not donation_handler_url:
            logger.error("❌ GCDonationHandler URL not configured")
            # Fail silently for keypad inputs - user already has keypad open
            return {"status": "ok"}

        # Prepare payload for GCDonationHandler /keypad-input endpoint
        payload = {
            "user_id": user_id,
            "callback_data": callback_data,
            "callback_query_id": callback_query['id'],
            "message_id": callback_query['message']['message_id'],
            "chat_id": chat_id
        }

        # Call GCDonationHandler service
        try:
            response = self.http_client.post(
                f"{donation_handler_url}/keypad-input",
                payload
            )

            if response and response.get('success'):
                logger.info(f"✅ Keypad input processed: user={user_id}, action={callback_data}")
            else:
                error = response.get('error', 'Unknown error') if response else 'No response'
                logger.warning(f"⚠️ GCDonationHandler keypad error: {error}")

            # Always return success - GCDonationHandler handles user feedback
            return {"status": "ok"}

        except Exception as e:
            logger.error(f"❌ HTTP error calling GCDonationHandler keypad: {e}")
            # Fail silently - don't disrupt user's keypad interaction
            return {"status": "ok"}
