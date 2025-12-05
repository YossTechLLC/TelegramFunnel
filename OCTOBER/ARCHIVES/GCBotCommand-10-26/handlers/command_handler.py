#!/usr/bin/env python
"""
Command Handler for GCBotCommand
Processes /start and /database commands
"""
from typing import Dict, Any
from utils.token_parser import TokenParser
from utils.http_client import HTTPClient
from utils.message_formatter import MessageFormatter
import logging
import requests

logger = logging.getLogger(__name__)

class CommandHandler:
    """Handles Telegram bot commands"""

    def __init__(self, db_manager, config):
        self.db = db_manager
        self.config = config
        self.bot_token = config['bot_token']
        self.token_parser = TokenParser()
        self.http_client = HTTPClient()
        self.message_formatter = MessageFormatter()

    def handle_start_command(self, update_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Handle /start command with token parsing

        Supports:
        - /start {hash}_{price}_{time}  → Subscription token
        - /start {hash}_DONATE  → Donation token
        - /start (no args) → Show main menu
        """
        message = update_data['message']
        chat_id = message['chat']['id']
        user = message['from']
        text = message['text']

        # Parse arguments
        args = text.split(' ', 1)[1] if ' ' in text else None

        logger.info(f"📍 /start command from user {user['id']}, args: {args}")

        if not args:
            # No token - show main menu
            return self._send_main_menu(chat_id, user)

        # Parse token
        token_data = self.token_parser.parse_token(args)

        if token_data['type'] == 'subscription':
            return self._handle_subscription_token(chat_id, user, token_data)

        elif token_data['type'] == 'donation':
            return self._handle_donation_token(chat_id, user, token_data)

        else:
            # Invalid token format
            return self._send_error_message(chat_id, "Invalid token format")

    def _send_main_menu(self, chat_id: int, user: Dict) -> Dict[str, str]:
        """Send main menu with inline keyboard"""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "💾 DATABASE", "callback_data": "CMD_DATABASE"},
                    {"text": "💳 PAYMENT GATEWAY", "callback_data": "CMD_GATEWAY"}
                ],
                [
                    {"text": "🌐 REGISTER", "url": "https://www.paygateprime.com"}
                ]
            ]
        }

        message_text = (
            f"Hi {user.get('first_name', 'there')}! 👋\n\n"
            f"Choose an option:"
        )

        return self._send_message(chat_id, message_text, reply_markup=keyboard)

    def _handle_subscription_token(self, chat_id: int, user: Dict, token_data: Dict) -> Dict[str, str]:
        """Handle subscription token - route to payment gateway"""
        channel_id = token_data['channel_id']
        price = token_data['price']
        time = token_data['time']

        logger.info(f"💰 Subscription: channel={channel_id}, price=${price}, time={time}days")

        # Fetch channel info from database
        channel_data = self.db.fetch_channel_by_id(channel_id)

        if not channel_data:
            return self._send_error_message(chat_id, "Channel not found")

        closed_channel_title = channel_data.get("closed_channel_title", "Premium Channel")
        closed_channel_description = channel_data.get("closed_channel_description", "exclusive content")

        # Send payment gateway button
        keyboard = {
            "inline_keyboard": [
                [{"text": "💰 Launch Payment Gateway", "callback_data": "TRIGGER_PAYMENT"}]
            ]
        }

        message_text = self.message_formatter.format_subscription_message(
            closed_channel_title, closed_channel_description, price, time
        )

        # Store subscription context in database for later retrieval
        self.db.save_conversation_state(user['id'], 'payment', {
            'channel_id': channel_id,
            'price': price,
            'time': time,
            'payment_type': 'subscription'
        })

        return self._send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')

    def _handle_donation_token(self, chat_id: int, user: Dict, token_data: Dict) -> Dict[str, str]:
        """Handle donation token - start donation flow"""
        channel_id = token_data['channel_id']

        logger.info(f"💝 Donation token: channel={channel_id}")

        # Store donation context
        self.db.save_conversation_state(user['id'], 'donation', {
            'channel_id': channel_id,
            'state': 'awaiting_amount'
        })

        message_text = (
            "💝 *How much would you like to donate?*\n\n"
            "Please enter an amount in USD (e.g., 25.50)\n"
            "Range: $1.00 - $9999.99"
        )

        return self._send_message(chat_id, message_text, parse_mode='Markdown')

    def handle_database_command(self, update_data: Dict[str, Any]) -> Dict[str, str]:
        """Handle /database command - start database configuration flow"""
        message = update_data['message']
        chat_id = message['chat']['id']
        user_id = message['from']['id']

        logger.info(f"💾 /database command from user {user_id}")

        # Initialize database conversation state
        self.db.save_conversation_state(user_id, 'database', {
            'state': 'awaiting_channel_id'
        })

        message_text = self.message_formatter.format_database_menu_message()

        return self._send_message(chat_id, message_text, parse_mode='Markdown')

    def handle_text_input(self, update_data: Dict[str, Any]) -> Dict[str, str]:
        """Handle text input during conversations"""
        message = update_data['message']
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        text = message['text']

        # Check if user has active conversation
        donation_state = self.db.get_conversation_state(user_id, 'donation')
        database_state = self.db.get_conversation_state(user_id, 'database')

        if donation_state:
            return self._handle_donation_input(chat_id, user_id, text, donation_state)

        elif database_state:
            return self._handle_database_input(chat_id, user_id, text, database_state)

        else:
            # No active conversation
            return self._send_message(chat_id, "Please use /start to begin")

    def _handle_donation_input(self, chat_id: int, user_id: int, text: str, state: Dict) -> Dict[str, str]:
        """Handle donation amount input"""
        from utils.validators import validate_donation_amount

        # Validate amount
        is_valid, amount = validate_donation_amount(text)

        if not is_valid:
            return self._send_message(
                chat_id,
                "❌ Invalid amount. Please enter a valid donation amount between $1.00 and $9999.99\n"
                "Examples: 25, 10.50, 100.99"
            )

        # Amount is valid - route to payment gateway
        channel_id = state.get('channel_id')

        # Call GCPaymentGateway
        payment_url = self.config['gcpaymentgateway_url']
        payload = {
            "user_id": user_id,
            "amount": amount,
            "open_channel_id": channel_id,
            "subscription_time_days": 365,  # Donation gives 1 year access
            "payment_type": "donation"
        }

        response = self.http_client.post(f"{payment_url}/create-invoice", payload)

        if response and response.get('success'):
            invoice_url = response['invoice_url']

            keyboard = {
                "inline_keyboard": [
                    [{"text": "💳 Pay Now", "web_app": {"url": invoice_url}}]
                ]
            }

            # Clear conversation state
            self.db.clear_conversation_state(user_id, 'donation')

            message_text = self.message_formatter.format_donation_message(amount)

            return self._send_message(
                chat_id,
                message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            return self._send_error_message(chat_id, "Failed to create payment invoice")

    def _handle_database_input(self, chat_id: int, user_id: int, text: str, state: Dict) -> Dict[str, str]:
        """Handle database configuration input"""
        from handlers.database_handler import DatabaseFormHandler

        # Delegate to database form handler
        db_form_handler = DatabaseFormHandler(self.db, self.config)
        return db_form_handler.handle_input(chat_id, user_id, text, state)

    def _send_message(self, chat_id: int, text: str, **kwargs) -> Dict[str, str]:
        """Send message via Telegram Bot API"""
        payload = {
            "chat_id": chat_id,
            "text": text
        }

        # Add optional parameters
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
            return {"status": "error", "message": str(e)}

    def _send_error_message(self, chat_id: int, error_text: str) -> Dict[str, str]:
        """Send error message to user"""
        formatted_error = self.message_formatter.format_error_message(error_text)
        return self._send_message(chat_id, formatted_error)
