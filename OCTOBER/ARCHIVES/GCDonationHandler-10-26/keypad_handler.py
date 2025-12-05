#!/usr/bin/env python
"""
Keypad Handler for GCDonationHandler
Handles inline numeric keypad for donation amount input

This module provides a calculator-style interface for users to enter
custom donation amounts with real-time validation. It manages user state
in database for horizontal scaling support.
"""

import logging
import time
from typing import Optional, Dict, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from keypad_state_manager import KeypadStateManager

logger = logging.getLogger(__name__)


class KeypadHandler:
    """
    Handles inline numeric keypad for donation amount input.

    This class provides a calculator-style interface with validation rules
    to ensure valid donation amounts. User state is stored in database using
    KeypadStateManager to enable horizontal scaling.

    Validation Constants:
        MIN_AMOUNT: Minimum donation amount ($4.99)
        MAX_AMOUNT: Maximum donation amount ($9999.99)
        MAX_DECIMALS: Maximum decimal places (2)
        MAX_DIGITS_BEFORE_DECIMAL: Maximum digits before decimal (4)

    Attributes:
        db_manager: DatabaseManager instance for channel validation
        telegram_client: TelegramClient instance for bot operations
        payment_gateway: PaymentGatewayManager instance for invoices
        state_manager: KeypadStateManager instance for database-backed state
    """

    # Validation constants
    MIN_AMOUNT = 4.99
    MAX_AMOUNT = 9999.99
    MAX_DECIMALS = 2
    MAX_DIGITS_BEFORE_DECIMAL = 4

    def __init__(self, db_manager, telegram_client, payment_token: str, ipn_callback_url: str, state_manager: Optional[KeypadStateManager] = None):
        """
        Initialize the KeypadHandler.

        Args:
            db_manager: DatabaseManager instance
            telegram_client: TelegramClient instance
            payment_token: NowPayments API token
            ipn_callback_url: IPN callback URL for payment notifications
            state_manager: Optional KeypadStateManager instance (auto-created if not provided)
        """
        self.db_manager = db_manager
        self.telegram_client = telegram_client

        # Import and initialize payment gateway internally
        from payment_gateway_manager import PaymentGatewayManager
        self.payment_gateway = PaymentGatewayManager(payment_token, ipn_callback_url)

        # Database-backed state storage (replaces in-memory user_states dict)
        self.state_manager = state_manager or KeypadStateManager(db_manager)

        logger.info("🔢 KeypadHandler initialized (database-backed state)")

    def start_donation_input(
        self,
        user_id: int,
        chat_id: int,
        open_channel_id: str,
        callback_query_id: str
    ) -> Dict[str, Any]:
        """
        Start donation input flow - send keypad to user.

        Args:
            user_id: Telegram user ID
            chat_id: Chat ID where to send keypad
            open_channel_id: Channel for which donation is being made
            callback_query_id: Callback query ID to answer

        Returns:
            Dictionary with result:
            {'success': True, 'message_id': int} on success
            {'success': False, 'error': str} on failure
        """
        try:
            # Answer callback query
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text="💝 Opening donation keypad..."
            )

            # Initialize user state in database
            success = self.state_manager.create_state(
                user_id=user_id,
                channel_id=open_channel_id,
                chat_id=chat_id,
                state_type='keypad_input'
            )

            if not success:
                logger.error(f"❌ Failed to create state for user {user_id}")
                return {'success': False, 'error': 'Failed to initialize state'}

            # Create keypad message text
            text = (
                "<b>💝 Enter Donation Amount</b>\n\n"
                "Use the keypad below to enter your donation amount in USD.\n"
                f"Range: ${self.MIN_AMOUNT:.2f} - ${self.MAX_AMOUNT:.2f}"
            )

            # Send keypad message
            result = self.telegram_client.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=self._create_donation_keypad('0'),
                parse_mode="HTML"
            )

            if result['success']:
                logger.info(f"💝 User {user_id} started donation for channel {open_channel_id}")
                return {'success': True, 'message_id': result['message_id']}
            else:
                return {'success': False, 'error': result.get('error', 'Failed to send keypad')}

        except Exception as e:
            logger.error(f"❌ Error starting donation input for user {user_id}: {e}")
            return {'success': False, 'error': str(e)}

    def handle_keypad_input(
        self,
        user_id: int,
        callback_data: str,
        callback_query_id: str,
        message_id: Optional[int] = None,
        chat_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Handle keypad button press.

        Routes to appropriate handler based on callback_data prefix.

        Args:
            user_id: Telegram user ID
            callback_data: Button callback data
            callback_query_id: Callback query ID to answer
            message_id: Message ID (for editing keyboard)
            chat_id: Chat ID (for new messages)

        Returns:
            Dictionary with result:
            {'success': True, ...} on success
            {'success': False, 'error': str} on failure
        """
        try:
            # Check if user has active session in database
            user_state = self.state_manager.get_state(user_id)

            if not user_state:
                self.telegram_client.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="⚠️ Session expired. Please start a new donation.",
                    show_alert=True
                )
                return {'success': False, 'error': 'Session expired'}

            # Get current amount from state
            current_amount = user_state['amount_building']

            # Note: message_id and chat_id are provided by GCBotCommand in the HTTP request
            # We don't need to store them in state anymore

            # Route to appropriate handler
            if callback_data.startswith("donate_digit_"):
                return self._handle_digit_press(user_id, callback_data, callback_query_id, current_amount, message_id, chat_id)

            elif callback_data == "donate_backspace":
                return self._handle_backspace(user_id, callback_query_id, current_amount, message_id, chat_id)

            elif callback_data == "donate_clear":
                return self._handle_clear(user_id, callback_query_id, message_id, chat_id)

            elif callback_data == "donate_confirm":
                return self._handle_confirm(user_id, callback_query_id, current_amount, message_id, chat_id)

            elif callback_data == "donate_cancel":
                return self._handle_cancel(user_id, callback_query_id, message_id, chat_id)

            elif callback_data == "donate_noop":
                # Display button, no action
                self.telegram_client.answer_callback_query(callback_query_id)
                return {'success': True}

            else:
                logger.warning(f"⚠️ Unknown callback data: {callback_data}")
                return {'success': False, 'error': 'Unknown callback data'}

        except Exception as e:
            logger.error(f"❌ Error handling keypad input for user {user_id}: {e}")
            return {'success': False, 'error': str(e)}

    def _handle_digit_press(
        self,
        user_id: int,
        callback_data: str,
        callback_query_id: str,
        current_amount: str,
        message_id: int,
        chat_id: int
    ) -> Dict[str, Any]:
        """
        Handle digit or decimal button press with validation.

        Validation Rules:
        1. Replace leading zero: "0" + "5" → "5"
        2. Single decimal: "2.5" + "." → REJECT
        3. Max 2 decimal places: "2.55" + "0" → REJECT
        4. Max 4 digits before decimal: "9999" + "9" → REJECT

        Args:
            user_id: Telegram user ID
            callback_data: Button callback data (e.g., "donate_digit_5")
            callback_query_id: Callback query ID
            current_amount: Current amount string
            message_id: Message ID to edit
            chat_id: Chat ID

        Returns:
            Dictionary with success status
        """
        # Extract digit from callback data
        digit = callback_data.split("_")[2]  # "donate_digit_5" → "5"

        # Validation Rule 1: Replace leading zero
        if current_amount == "0" and digit != ".":
            new_amount = digit

        # Validation Rule 2: Only one decimal point
        elif digit == "." and "." in current_amount:
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text="⚠️ Only one decimal point allowed",
                show_alert=True
            )
            return {'success': False, 'error': 'Multiple decimal points'}

        # Validation Rule 3: Max 2 decimal places
        elif "." in current_amount:
            decimal_part = current_amount.split(".")[1]
            if len(decimal_part) >= self.MAX_DECIMALS and digit != ".":
                self.telegram_client.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text=f"⚠️ Maximum {self.MAX_DECIMALS} decimal places",
                    show_alert=True
                )
                return {'success': False, 'error': 'Too many decimals'}
            new_amount = current_amount + digit

        # Validation Rule 4: Max 4 digits before decimal
        elif digit != "." and len(current_amount) >= self.MAX_DIGITS_BEFORE_DECIMAL:
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text=f"⚠️ Maximum amount: ${self.MAX_AMOUNT:.2f}",
                show_alert=True
            )
            return {'success': False, 'error': 'Amount too large'}

        else:
            new_amount = current_amount + digit

        # Update user state in database
        self.state_manager.update_amount(user_id, new_amount)

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Update keyboard
        self.telegram_client.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=self._create_donation_keypad(new_amount)
        )

        logger.debug(f"💰 User {user_id} amount updated: {new_amount}")
        return {'success': True}

    def _handle_backspace(
        self,
        user_id: int,
        callback_query_id: str,
        current_amount: str,
        message_id: int,
        chat_id: int
    ) -> Dict[str, Any]:
        """Handle backspace button - delete last character."""
        # Remove last character, reset to "0" if empty
        new_amount = current_amount[:-1] if len(current_amount) > 1 else "0"

        # Update user state in database
        self.state_manager.update_amount(user_id, new_amount)

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Update keyboard
        self.telegram_client.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=self._create_donation_keypad(new_amount)
        )

        logger.debug(f"⌫ User {user_id} backspace: {new_amount}")
        return {'success': True}

    def _handle_clear(
        self,
        user_id: int,
        callback_query_id: str,
        message_id: int,
        chat_id: int
    ) -> Dict[str, Any]:
        """Handle clear button - reset to $0.00."""
        # Reset amount in database
        self.state_manager.update_amount(user_id, "0")

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Update keyboard
        self.telegram_client.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=self._create_donation_keypad("0")
        )

        logger.debug(f"🗑️ User {user_id} cleared amount")
        return {'success': True}

    def _handle_confirm(
        self,
        user_id: int,
        callback_query_id: str,
        current_amount: str,
        message_id: int,
        chat_id: int
    ) -> Dict[str, Any]:
        """Handle confirm button - validate amount and trigger payment."""
        # Parse amount
        try:
            amount_float = float(current_amount)
        except ValueError:
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text="❌ Invalid amount format",
                show_alert=True
            )
            return {'success': False, 'error': 'Invalid amount'}

        # Validate minimum
        if amount_float < self.MIN_AMOUNT:
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text=f"⚠️ Minimum donation: ${self.MIN_AMOUNT:.2f}",
                show_alert=True
            )
            return {'success': False, 'error': 'Amount below minimum'}

        # Validate maximum
        if amount_float > self.MAX_AMOUNT:
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text=f"⚠️ Maximum donation: ${self.MAX_AMOUNT:.2f}",
                show_alert=True
            )
            return {'success': False, 'error': 'Amount above maximum'}

        # Get open_channel_id from database state
        user_state = self.state_manager.get_state(user_id)
        if not user_state:
            return {'success': False, 'error': 'State not found'}

        open_channel_id = user_state['open_channel_id']

        logger.info(f"✅ Donation confirmed: ${amount_float:.2f} for channel {open_channel_id} by user {user_id}")

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Delete keypad message
        self.telegram_client.delete_message(chat_id=chat_id, message_id=message_id)

        # Send confirmation message with DM notification
        self.telegram_client.send_message(
            chat_id=chat_id,
            text=f"✅ <b>Donation Confirmed</b>\n"
                 f"💰 <b>Amount:</b> ${amount_float:.2f}\n\n"
                 f"📨 <b>Check your private messages</b> to complete the payment.",
            parse_mode="HTML"
        )

        # Trigger payment gateway
        payment_result = self._trigger_payment_gateway(user_id, amount_float, open_channel_id, chat_id)

        # Clean up user state from database (optional: could keep for analytics)
        # self.state_manager.delete_state(user_id)

        return {'success': True, 'payment_result': payment_result}

    def _handle_cancel(
        self,
        user_id: int,
        callback_query_id: str,
        message_id: int,
        chat_id: int
    ) -> Dict[str, Any]:
        """Handle cancel button - abort donation flow."""
        logger.info(f"🚫 User {user_id} cancelled donation")

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Delete keypad message
        self.telegram_client.delete_message(chat_id=chat_id, message_id=message_id)

        # Send cancellation message
        self.telegram_client.send_message(
            chat_id=chat_id,
            text="❌ Donation cancelled.",
            parse_mode="HTML"
        )

        # Clean up user state from database
        self.state_manager.delete_state(user_id)

        return {'success': True}

    def _trigger_payment_gateway(
        self,
        user_id: int,
        amount: float,
        open_channel_id: str,
        chat_id: int
    ) -> Dict[str, Any]:
        """
        Trigger payment gateway - create invoice and send payment button.

        Args:
            user_id: Telegram user ID
            amount: Donation amount in USD
            open_channel_id: Channel ID for routing
            chat_id: Chat ID to send payment button

        Returns:
            Dictionary with payment result
        """
        try:
            # Create order_id
            order_id = f"PGP-{user_id}|{open_channel_id}"

            logger.info(f"💰 Creating payment invoice for ${amount:.2f} - order_id: {order_id}")

            # Create invoice
            invoice_result = self.payment_gateway.create_payment_invoice(
                user_id=user_id,
                amount=amount,
                order_id=order_id
            )

            if invoice_result['success']:
                invoice_url = invoice_result['data']['invoice_url']

                logger.info(f"✅ Payment invoice created successfully for ${amount:.2f}")

                # Fetch channel details for message formatting
                channel_details = self.db_manager.get_channel_details_by_open_id(open_channel_id)

                if channel_details:
                    closed_channel_title = channel_details.get("closed_channel_title", "Premium Channel")
                    closed_channel_description = channel_details.get("closed_channel_description", "Exclusive content")
                else:
                    closed_channel_title = "Premium Channel"
                    closed_channel_description = "Exclusive content"
                    logger.warning(f"⚠️ Channel details not found for {open_channel_id}, using fallback")

                # Send notification to group chat
                group_notification = (
                    f"💝 <b>Payment Link Ready</b>\n"
                    f"💰 <b>Amount:</b> ${amount:.2f}\n\n"
                    f"📨 A secure payment link has been sent to your private messages."
                )

                self.telegram_client.send_message(
                    chat_id=chat_id,
                    text=group_notification,
                    parse_mode="HTML"
                )

                # Prepare payment message for PRIVATE CHAT (DM)
                private_text = (
                    f"💝 <b>Complete Your ${amount:.2f} Donation</b>\n\n"
                    f"🔒 <b>Private Channel:</b> {closed_channel_title}\n"
                    f"📝 <b>Description:</b> {closed_channel_description}\n"
                    f"💰 <b>Amount:</b> ${amount:.2f}\n\n"
                    f"Click the button below to open the secure payment gateway:"
                )

                # Create WebApp button (opens seamlessly in private chats)
                button = InlineKeyboardButton(
                    text="💳 Open Payment Gateway",
                    web_app=WebAppInfo(url=invoice_url)
                )
                keyboard = InlineKeyboardMarkup([[button]])

                # Send to user's PRIVATE CHAT (not group)
                dm_result = self.telegram_client.send_message(
                    chat_id=user_id,  # Send to user's DM
                    text=private_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                # Handle case where bot is blocked/never started
                if not dm_result['success']:
                    error = dm_result.get('error', '').lower()

                    if 'bot was blocked' in error or 'chat not found' in error or 'forbidden' in error:
                        logger.warning(f"⚠️ Cannot DM user {user_id} - bot not started or blocked")

                        # Send fallback message to group with instructions
                        fallback_text = (
                            f"⚠️ <b>Cannot Send Payment Link</b>\n\n"
                            f"Please <b>start a private chat</b> with me first:\n"
                            f"1. Click my username above\n"
                            f"2. Press the \"Start\" button\n"
                            f"3. Return here and try donating again\n\n"
                            f"Your payment link: {invoice_url}"
                        )

                        self.telegram_client.send_message(
                            chat_id=chat_id,
                            text=fallback_text,
                            parse_mode="HTML"
                        )

                        return {'success': False, 'error': 'User must start bot first', 'invoice_url': invoice_url}

                logger.info(f"📨 Payment button sent to user {user_id} private chat")
                return {'success': True, 'invoice_url': invoice_url}

            else:
                # Invoice creation failed
                error_msg = invoice_result.get('error', 'Unknown error')
                logger.error(f"❌ Invoice creation failed: {error_msg}")

                self.telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"❌ <b>Payment Gateway Error</b>\n\n"
                         f"We encountered an error creating your payment invoice.\n\n"
                         f"Error: {error_msg}\n\n"
                         f"Please try again later or contact support.",
                    parse_mode="HTML"
                )

                return {'success': False, 'error': error_msg}

        except Exception as e:
            logger.error(f"❌ Failed to create payment invoice: {e}")

            self.telegram_client.send_message(
                chat_id=chat_id,
                text="❌ <b>Payment Gateway Error</b>\n\n"
                     "We encountered an unexpected error creating your payment invoice. "
                     "Please try again later or contact support.",
                parse_mode="HTML"
            )

            return {'success': False, 'error': str(e)}

    def _create_donation_keypad(self, current_amount: str) -> InlineKeyboardMarkup:
        """
        Generate inline numeric keypad with current amount display.

        Layout:
        Row 1: [💰 Amount: $0.00]  ← Display only
        Row 2: [1] [2] [3]
        Row 3: [4] [5] [6]
        Row 4: [7] [8] [9]
        Row 5: [.] [0] [⌫]
        Row 6: [🗑️ Clear]
        Row 7: [✅ Confirm & Pay]
        Row 8: [❌ Cancel]

        Args:
            current_amount: Current amount being built (e.g., "25.50")

        Returns:
            InlineKeyboardMarkup with calculator-style layout
        """
        # Format amount for display
        display_amount = self._format_amount_display(current_amount)

        keyboard = [
            # Display row (non-interactive)
            [InlineKeyboardButton(f"💰 {display_amount}", callback_data="donate_noop")],

            # Numeric pad rows
            [
                InlineKeyboardButton("1", callback_data="donate_digit_1"),
                InlineKeyboardButton("2", callback_data="donate_digit_2"),
                InlineKeyboardButton("3", callback_data="donate_digit_3"),
            ],
            [
                InlineKeyboardButton("4", callback_data="donate_digit_4"),
                InlineKeyboardButton("5", callback_data="donate_digit_5"),
                InlineKeyboardButton("6", callback_data="donate_digit_6"),
            ],
            [
                InlineKeyboardButton("7", callback_data="donate_digit_7"),
                InlineKeyboardButton("8", callback_data="donate_digit_8"),
                InlineKeyboardButton("9", callback_data="donate_digit_9"),
            ],
            [
                InlineKeyboardButton(".", callback_data="donate_digit_."),
                InlineKeyboardButton("0", callback_data="donate_digit_0"),
                InlineKeyboardButton("⌫", callback_data="donate_backspace"),
            ],

            # Action buttons
            [InlineKeyboardButton("🗑️ Clear", callback_data="donate_clear")],
            [InlineKeyboardButton("✅ Confirm & Pay", callback_data="donate_confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="donate_cancel")],
        ]

        return InlineKeyboardMarkup(keyboard)

    def _format_amount_display(self, amount_str: str) -> str:
        """
        Format amount string for display.

        Formatting Rules:
        - Input: "0" → Output: "$0.00"
        - Input: "25" → Output: "$25.00"
        - Input: "25.5" → Output: "$25.50"
        - Input: "25.50" → Output: "$25.50"
        - Input: "1000" → Output: "$1000.00"

        Args:
            amount_str: Raw amount string from user input

        Returns:
            Formatted display string with dollar sign and proper decimals
        """
        try:
            # Parse as float to handle proper decimal formatting
            amount_float = float(amount_str)
            return f"${amount_float:.2f}"
        except ValueError:
            # If parsing fails, show raw input
            return f"${amount_str}"
