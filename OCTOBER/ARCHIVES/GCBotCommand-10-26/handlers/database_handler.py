#!/usr/bin/env python
"""
Database Form Handler for GCBotCommand
Handles database configuration form editing logic
"""
from typing import Dict, Any
from utils.validators import (
    valid_channel_id, valid_sub_price, valid_sub_time,
    valid_channel_title, valid_channel_description,
    valid_wallet_address, valid_currency
)
import logging
import requests

logger = logging.getLogger(__name__)

class DatabaseFormHandler:
    """Handles database configuration form editing"""

    def __init__(self, db_manager, config):
        self.db = db_manager
        self.config = config
        self.bot_token = config['bot_token']

    def handle_input(self, chat_id: int, user_id: int, text: str, state: Dict) -> Dict[str, str]:
        """
        Handle text input during database configuration

        Routes based on current state:
        - awaiting_channel_id → Validate and fetch channel
        - editing_field → Validate field input
        """
        current_state = state.get('state')

        if current_state == 'awaiting_channel_id':
            return self._handle_channel_id_input(chat_id, user_id, text)

        elif current_state == 'editing_field':
            return self._handle_field_input(chat_id, user_id, text, state)

        else:
            return self._send_message(chat_id, "❌ Invalid state. Please start over with /database")

    def _handle_channel_id_input(self, chat_id: int, user_id: int, text: str) -> Dict[str, str]:
        """Handle channel ID input"""
        # Validate channel ID
        if not valid_channel_id(text):
            return self._send_message(
                chat_id,
                "❌ Invalid channel ID format. Must be ≤14 character integer (e.g., -1003268562225)"
            )

        # Fetch channel from database
        channel_data = self.db.fetch_channel_by_id(text)

        if channel_data:
            # Channel exists - show editing form
            self.db.save_conversation_state(user_id, 'database', {
                'state': 'viewing_form',
                'channel_id': text,
                'channel_data': channel_data
            })

            return self._show_main_form(chat_id, user_id, None, channel_data)

        else:
            # Channel not found - ask if user wants to create new
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Create New", "callback_data": "CREATE_NEW_CHANNEL"},
                        {"text": "❌ Cancel", "callback_data": "CANCEL_EDIT"}
                    ]
                ]
            }

            # Initialize empty channel data
            new_channel_data = {
                'open_channel_id': text,
                'open_channel_title': '',
                'open_channel_description': '',
                'closed_channel_id': '',
                'closed_channel_title': '',
                'closed_channel_description': '',
                'sub_1_price': None,
                'sub_1_time': None,
                'sub_2_price': None,
                'sub_2_time': None,
                'sub_3_price': None,
                'sub_3_time': None,
                'client_wallet_address': '',
                'client_payout_currency': '',
                'client_payout_network': ''
            }

            self.db.save_conversation_state(user_id, 'database', {
                'state': 'confirming_new_channel',
                'channel_id': text,
                'channel_data': new_channel_data
            })

            return self._send_message(
                chat_id,
                f"Channel {text} not found in database.\n\n"
                f"Would you like to create a new configuration?",
                reply_markup=keyboard
            )

    def _handle_field_input(self, chat_id: int, user_id: int, text: str, state: Dict) -> Dict[str, str]:
        """Handle field value input during editing"""
        current_field = state.get('current_field')
        channel_data = state.get('channel_data')

        if not current_field or not channel_data:
            return self._send_message(chat_id, "❌ Invalid state. Please start over.")

        # Validate based on field type
        is_valid = False
        error_message = ""

        if current_field == "open_channel_title":
            is_valid = valid_channel_title(text)
            error_message = "Title must be 1-100 characters"

        elif current_field == "open_channel_description":
            is_valid = valid_channel_description(text)
            error_message = "Description must be 1-500 characters"

        elif current_field == "closed_channel_id":
            is_valid = valid_channel_id(text)
            error_message = "Must be ≤14 character integer"

        elif current_field == "closed_channel_title":
            is_valid = valid_channel_title(text)
            error_message = "Title must be 1-100 characters"

        elif current_field == "closed_channel_description":
            is_valid = valid_channel_description(text)
            error_message = "Description must be 1-500 characters"

        elif current_field in ["sub_1_price", "sub_2_price", "sub_3_price"]:
            is_valid = valid_sub_price(text)
            error_message = "Price must be 0-9999.99 with max 2 decimals"
            if is_valid:
                text = float(text)

        elif current_field in ["sub_1_time", "sub_2_time", "sub_3_time"]:
            is_valid = valid_sub_time(text)
            error_message = "Time must be 1-999 days"
            if is_valid:
                text = int(text)

        elif current_field == "client_wallet_address":
            is_valid = valid_wallet_address(text)
            error_message = "Wallet address must be 10-200 characters"

        elif current_field == "client_payout_currency":
            is_valid = valid_currency(text)
            error_message = "Currency must be 2-10 uppercase letters"
            if is_valid:
                text = text.strip().upper()

        elif current_field == "client_payout_network":
            is_valid = True  # Network is freeform text

        if is_valid:
            # Update channel_data
            channel_data[current_field] = text

            # Update state
            self.db.save_conversation_state(user_id, 'database', {
                'state': 'viewing_form',
                'channel_id': state.get('channel_id'),
                'channel_data': channel_data
            })

            # Show appropriate form based on which field was edited
            if current_field.startswith("open_channel"):
                return self._show_open_channel_form(chat_id, user_id, None, channel_data)
            elif current_field.startswith("closed_channel"):
                return self._show_private_channel_form(chat_id, user_id, None, channel_data)
            elif current_field.startswith("sub_"):
                return self._show_payment_tiers_form(chat_id, user_id, None, channel_data)
            elif current_field.startswith("client_"):
                return self._show_wallet_form(chat_id, user_id, None, channel_data)
            else:
                return self._show_main_form(chat_id, user_id, None, channel_data)

        else:
            # Validation failed
            return self._send_message(chat_id, f"❌ {error_message}. Please try again:")

    def handle_edit_callback(self, chat_id: int, user_id: int, message_id: int, callback_data: str) -> Dict[str, str]:
        """Handle edit callback buttons"""
        # Get current state
        state = self.db.get_conversation_state(user_id, 'database')

        if not state:
            return self._send_message(chat_id, "❌ Session expired. Please start over with /database")

        channel_data = state.get('channel_data')

        # Route based on callback_data
        if callback_data == "EDIT_OPEN_CHANNEL":
            return self._show_open_channel_form(chat_id, user_id, message_id, channel_data)

        elif callback_data == "EDIT_PRIVATE_CHANNEL":
            return self._show_private_channel_form(chat_id, user_id, message_id, channel_data)

        elif callback_data == "EDIT_PAYMENT_TIERS":
            return self._show_payment_tiers_form(chat_id, user_id, message_id, channel_data)

        elif callback_data == "EDIT_WALLET":
            return self._show_wallet_form(chat_id, user_id, message_id, channel_data)

        # Individual field edits
        elif callback_data.startswith("EDIT_"):
            return self._prompt_field_edit(chat_id, user_id, message_id, callback_data, state)

        elif callback_data == "CREATE_NEW_CHANNEL":
            # User confirmed creation of new channel
            return self._show_main_form(chat_id, user_id, message_id, channel_data)

        else:
            logger.warning(f"⚠️ Unknown edit callback: {callback_data}")
            return {"status": "ok"}

    def _prompt_field_edit(self, chat_id: int, user_id: int, message_id: int, callback_data: str, state: Dict) -> Dict[str, str]:
        """Prompt user to enter new value for field"""
        # Map callback_data to field name and prompt
        field_map = {
            "EDIT_OPEN_CHANNEL_ID": ("open_channel_id", "Enter *open_channel_id*:"),
            "EDIT_OPEN_TITLE": ("open_channel_title", "Enter *open channel title*:"),
            "EDIT_OPEN_DESCRIPTION": ("open_channel_description", "Enter *open channel description*:"),
            "EDIT_CLOSED_CHANNEL_ID": ("closed_channel_id", "Enter *closed_channel_id*:"),
            "EDIT_CLOSED_TITLE": ("closed_channel_title", "Enter *closed channel title*:"),
            "EDIT_CLOSED_DESCRIPTION": ("closed_channel_description", "Enter *closed channel description*:"),
            "EDIT_TIER_1_PRICE": ("sub_1_price", "Enter *Tier 1 price* (0-9999.99):"),
            "EDIT_TIER_1_TIME": ("sub_1_time", "Enter *Tier 1 time* (1-999 days):"),
            "EDIT_TIER_2_PRICE": ("sub_2_price", "Enter *Tier 2 price* (0-9999.99):"),
            "EDIT_TIER_2_TIME": ("sub_2_time", "Enter *Tier 2 time* (1-999 days):"),
            "EDIT_TIER_3_PRICE": ("sub_3_price", "Enter *Tier 3 price* (0-9999.99):"),
            "EDIT_TIER_3_TIME": ("sub_3_time", "Enter *Tier 3 time* (1-999 days):"),
            "EDIT_WALLET_ADDRESS": ("client_wallet_address", "Enter *wallet address*:"),
            "EDIT_PAYOUT_CURRENCY": ("client_payout_currency", "Enter *payout currency* (e.g., USDT):"),
            "EDIT_PAYOUT_NETWORK": ("client_payout_network", "Enter *payout network* (e.g., TRC20):")
        }

        if callback_data not in field_map:
            return {"status": "ok"}

        field_name, prompt = field_map[callback_data]

        # Update state to editing_field
        state['state'] = 'editing_field'
        state['current_field'] = field_name
        self.db.save_conversation_state(user_id, 'database', state)

        return self._send_message(chat_id, prompt, parse_mode='Markdown')

    def _show_main_form(self, chat_id: int, user_id: int, message_id: int, channel_data: Dict) -> Dict[str, str]:
        """Show main database configuration form"""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📢 Open Channel", "callback_data": "EDIT_OPEN_CHANNEL"},
                    {"text": "🔒 Private Channel", "callback_data": "EDIT_PRIVATE_CHANNEL"}
                ],
                [
                    {"text": "💰 Payment Tiers", "callback_data": "EDIT_PAYMENT_TIERS"},
                    {"text": "💳 Wallet Address", "callback_data": "EDIT_WALLET"}
                ],
                [
                    {"text": "✅ Save All Changes", "callback_data": "SAVE_ALL_CHANGES"},
                    {"text": "❌ Cancel", "callback_data": "CANCEL_EDIT"}
                ]
            ]
        }

        # Format overview message
        open_channel_id = channel_data.get('open_channel_id', 'Not set')
        open_title = channel_data.get('open_channel_title', 'Not set')
        closed_channel_id = channel_data.get('closed_channel_id', 'Not set')
        closed_title = channel_data.get('closed_channel_title', 'Not set')
        wallet = channel_data.get('client_wallet_address', 'Not set')

        # Count enabled tiers
        enabled_tiers = []
        for i in range(1, 4):
            price = channel_data.get(f'sub_{i}_price')
            time = channel_data.get(f'sub_{i}_time')
            if price is not None and time is not None:
                enabled_tiers.append(f"Tier {i}: ${price} / {time}d")

        tiers_text = "\n".join(enabled_tiers) if enabled_tiers else "No tiers enabled"

        message_text = (
            f"💾 *DATABASE CONFIGURATION*\n\n"
            f"📢 *Open Channel:*\n"
            f"  ID: `{open_channel_id}`\n"
            f"  Title: {open_title}\n\n"
            f"🔒 *Private Channel:*\n"
            f"  ID: `{closed_channel_id}`\n"
            f"  Title: {closed_title}\n\n"
            f"💰 *Payment Tiers:*\n{tiers_text}\n\n"
            f"💳 *Wallet:* {wallet[:20]}...\n\n"
            f"Select a section to edit:"
        )

        if message_id:
            return self._edit_message(chat_id, message_id, message_text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            return self._send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='Markdown')

    def _show_open_channel_form(self, chat_id: int, user_id: int, message_id: int, channel_data: Dict) -> Dict[str, str]:
        """Show open channel editing form"""
        keyboard = {
            "inline_keyboard": [
                [{"text": "Edit Channel ID", "callback_data": "EDIT_OPEN_CHANNEL_ID"}],
                [{"text": "Edit Title", "callback_data": "EDIT_OPEN_TITLE"}],
                [{"text": "Edit Description", "callback_data": "EDIT_OPEN_DESCRIPTION"}],
                [{"text": "⬅️ Back to Main", "callback_data": "BACK_TO_MAIN"}]
            ]
        }

        open_channel_id = channel_data.get('open_channel_id', 'Not set')
        open_title = channel_data.get('open_channel_title', 'Not set')
        open_desc = channel_data.get('open_channel_description', 'Not set')

        message_text = (
            f"📢 *OPEN CHANNEL CONFIGURATION*\n\n"
            f"*Channel ID:* `{open_channel_id}`\n"
            f"*Title:* {open_title}\n"
            f"*Description:* {open_desc}\n\n"
            f"Select a field to edit:"
        )

        if message_id:
            return self._edit_message(chat_id, message_id, message_text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            return self._send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='Markdown')

    def _show_private_channel_form(self, chat_id: int, user_id: int, message_id: int, channel_data: Dict) -> Dict[str, str]:
        """Show private channel editing form"""
        keyboard = {
            "inline_keyboard": [
                [{"text": "Edit Channel ID", "callback_data": "EDIT_CLOSED_CHANNEL_ID"}],
                [{"text": "Edit Title", "callback_data": "EDIT_CLOSED_TITLE"}],
                [{"text": "Edit Description", "callback_data": "EDIT_CLOSED_DESCRIPTION"}],
                [{"text": "⬅️ Back to Main", "callback_data": "BACK_TO_MAIN"}]
            ]
        }

        closed_channel_id = channel_data.get('closed_channel_id', 'Not set')
        closed_title = channel_data.get('closed_channel_title', 'Not set')
        closed_desc = channel_data.get('closed_channel_description', 'Not set')

        message_text = (
            f"🔒 *PRIVATE CHANNEL CONFIGURATION*\n\n"
            f"*Channel ID:* `{closed_channel_id}`\n"
            f"*Title:* {closed_title}\n"
            f"*Description:* {closed_desc}\n\n"
            f"Select a field to edit:"
        )

        if message_id:
            return self._edit_message(chat_id, message_id, message_text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            return self._send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='Markdown')

    def _show_payment_tiers_form(self, chat_id: int, user_id: int, message_id: int, channel_data: Dict) -> Dict[str, str]:
        """Show payment tiers editing form"""
        keyboard = {
            "inline_keyboard": []
        }

        # Build tier buttons
        for i in range(1, 4):
            price = channel_data.get(f'sub_{i}_price')
            time = channel_data.get(f'sub_{i}_time')
            is_enabled = price is not None and time is not None

            status = "✅" if is_enabled else "❌"

            keyboard["inline_keyboard"].append([
                {"text": f"Edit Tier {i} Price", "callback_data": f"EDIT_TIER_{i}_PRICE"},
                {"text": f"Edit Tier {i} Time", "callback_data": f"EDIT_TIER_{i}_TIME"}
            ])
            keyboard["inline_keyboard"].append([
                {"text": f"{status} Toggle Tier {i}", "callback_data": f"TOGGLE_TIER_{i}"}
            ])

        keyboard["inline_keyboard"].append([
            {"text": "⬅️ Back to Main", "callback_data": "BACK_TO_MAIN"}
        ])

        # Format tier information
        tier_info = []
        for i in range(1, 4):
            price = channel_data.get(f'sub_{i}_price')
            time = channel_data.get(f'sub_{i}_time')
            if price is not None and time is not None:
                tier_info.append(f"*Tier {i}:* ${price} / {time} days ✅")
            else:
                tier_info.append(f"*Tier {i}:* Disabled ❌")

        tier_text = "\n".join(tier_info)

        message_text = (
            f"💰 *PAYMENT TIERS CONFIGURATION*\n\n"
            f"{tier_text}\n\n"
            f"Select a tier to edit:"
        )

        if message_id:
            return self._edit_message(chat_id, message_id, message_text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            return self._send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='Markdown')

    def _show_wallet_form(self, chat_id: int, user_id: int, message_id: int, channel_data: Dict) -> Dict[str, str]:
        """Show wallet configuration form"""
        keyboard = {
            "inline_keyboard": [
                [{"text": "Edit Wallet Address", "callback_data": "EDIT_WALLET_ADDRESS"}],
                [{"text": "Edit Payout Currency", "callback_data": "EDIT_PAYOUT_CURRENCY"}],
                [{"text": "Edit Payout Network", "callback_data": "EDIT_PAYOUT_NETWORK"}],
                [{"text": "⬅️ Back to Main", "callback_data": "BACK_TO_MAIN"}]
            ]
        }

        wallet_address = channel_data.get('client_wallet_address', 'Not set')
        payout_currency = channel_data.get('client_payout_currency', 'Not set')
        payout_network = channel_data.get('client_payout_network', 'Not set')

        message_text = (
            f"💳 *WALLET CONFIGURATION*\n\n"
            f"*Wallet Address:* `{wallet_address}`\n"
            f"*Payout Currency:* {payout_currency}\n"
            f"*Payout Network:* {payout_network}\n\n"
            f"Select a field to edit:"
        )

        if message_id:
            return self._edit_message(chat_id, message_id, message_text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            return self._send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='Markdown')

    def show_main_form(self, chat_id: int, user_id: int, message_id: int) -> Dict[str, str]:
        """Public method to show main form (called from callback_handler)"""
        state = self.db.get_conversation_state(user_id, 'database')
        if not state:
            return self._send_message(chat_id, "❌ Session expired. Please start over with /database")

        channel_data = state.get('channel_data')
        return self._show_main_form(chat_id, user_id, message_id, channel_data)

    def toggle_tier(self, chat_id: int, user_id: int, message_id: int, callback_data: str) -> Dict[str, str]:
        """Toggle tier enable/disable"""
        # Parse tier number from callback_data (e.g., "TOGGLE_TIER_1" → 1)
        tier_num = int(callback_data.split('_')[-1])

        # Get current state
        state = self.db.get_conversation_state(user_id, 'database')
        if not state:
            return self._send_message(chat_id, "❌ Session expired.")

        channel_data = state.get('channel_data')

        # Check if tier is currently enabled
        price = channel_data.get(f'sub_{tier_num}_price')
        time = channel_data.get(f'sub_{tier_num}_time')

        if price is not None and time is not None:
            # Disable tier
            channel_data[f'sub_{tier_num}_price'] = None
            channel_data[f'sub_{tier_num}_time'] = None
            logger.info(f"✅ Tier {tier_num} disabled")
        else:
            # Enable tier with default values
            channel_data[f'sub_{tier_num}_price'] = 5.0
            channel_data[f'sub_{tier_num}_time'] = 30
            logger.info(f"✅ Tier {tier_num} enabled")

        # Update state
        self.db.save_conversation_state(user_id, 'database', state)

        # Refresh payment tiers form
        return self._show_payment_tiers_form(chat_id, user_id, message_id, channel_data)

    def save_changes(self, chat_id: int, user_id: int, message_id: int) -> Dict[str, str]:
        """Save all changes to database"""
        # Get current state
        state = self.db.get_conversation_state(user_id, 'database')
        if not state:
            return self._send_message(chat_id, "❌ Session expired.")

        channel_data = state.get('channel_data')
        channel_id = state.get('channel_id')

        if not channel_id:
            return self._send_message(chat_id, "❌ No channel ID found.")

        # Validate required fields
        if not channel_data.get('open_channel_id'):
            return self._send_message(chat_id, "❌ Open channel ID is required.")

        # Check at least one tier is enabled
        at_least_one_tier = False
        for i in range(1, 4):
            if channel_data.get(f'sub_{i}_price') is not None and channel_data.get(f'sub_{i}_time') is not None:
                at_least_one_tier = True
                break

        if not at_least_one_tier:
            return self._send_message(chat_id, "❌ At least one payment tier must be enabled.")

        # Save to database
        success = self.db.update_channel_config(channel_id, channel_data)

        if success:
            # Clear conversation state
            self.db.clear_conversation_state(user_id, 'database')

            return self._edit_message(
                chat_id,
                message_id,
                f"✅ *Configuration saved successfully!*\n\n"
                f"Channel ID: `{channel_id}`\n\n"
                f"Use /database to edit again.",
                parse_mode='Markdown'
            )
        else:
            return self._send_message(chat_id, "❌ Failed to save configuration. Please try again.")

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
