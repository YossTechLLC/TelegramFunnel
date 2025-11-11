#!/usr/bin/env python
"""
Donation Input Handler with Inline Numeric Keypad
Replaces ForceReply (which doesn't work in channels) with inline keyboard.

This module provides a custom numeric keypad interface for users to enter
donation amounts directly within the channel, with real-time validation
and user-friendly error messages.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import DatabaseManager

logger = logging.getLogger(__name__)


class DonationKeypadHandler:
    """
    Handles inline numeric keypad for donation amount input.

    This class provides a calculator-style interface for users to enter
    custom donation amounts, with validation rules to ensure valid inputs.

    Validation Rules:
    - Minimum amount: $4.99
    - Maximum amount: $9999.99
    - Maximum 2 decimal places
    - Maximum 4 digits before decimal point
    - Single decimal point only
    - No leading zeros (except "0.XX")

    Attributes:
        db_manager: DatabaseManager instance for database queries
        logger: Logger instance for this module
        MIN_AMOUNT: Minimum donation amount ($4.99)
        MAX_AMOUNT: Maximum donation amount ($9999.99)
        MAX_DECIMALS: Maximum decimal places (2)
        MAX_DIGITS_BEFORE_DECIMAL: Maximum digits before decimal (4)
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the DonationKeypadHandler.

        Args:
            db_manager: DatabaseManager instance for validation queries
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

        # Validation constants
        self.MIN_AMOUNT = 4.99
        self.MAX_AMOUNT = 9999.99
        self.MAX_DECIMALS = 2
        self.MAX_DIGITS_BEFORE_DECIMAL = 4

    async def start_donation_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        User clicked 'Donate' button in closed channel.
        Show numeric keypad for amount input.

        Callback data format: donate_start_{open_channel_id}

        Args:
            update: Telegram Update object containing callback query
            context: Telegram context for storing user data

        Example Flow:
            1. User clicks [💝 Donate] button in closed channel
            2. This method is triggered via callback query
            3. Message is edited to show numeric keypad
            4. User enters amount via keypad buttons
        """
        query = update.callback_query
        await query.answer()

        # Parse open_channel_id from callback data
        callback_parts = query.data.split("_")  # ["donate", "start", "{open_channel_id}"]
        if len(callback_parts) != 3:
            self.logger.error(f"❌ Invalid callback data format: {query.data}")
            await query.edit_message_text("❌ Error: Invalid donation link. Please try again.")
            return

        open_channel_id = callback_parts[2]

        # Security validation: Verify channel exists in database
        if not self.db_manager.channel_exists(open_channel_id):
            self.logger.warning(f"⚠️ Invalid channel ID in donation callback: {open_channel_id}")
            await query.answer("❌ Invalid channel", show_alert=True)
            await query.edit_message_text("❌ Error: Invalid channel. Please contact support.")
            return

        # Store channel context and initialize amount
        context.user_data["donation_open_channel_id"] = open_channel_id
        context.user_data["donation_amount_building"] = "0"
        import time
        context.user_data["donation_started_at"] = time.time()

        user_id = update.effective_user.id
        self.logger.info(f"💝 User {user_id} started donation for channel {open_channel_id}")

        # Send NEW keypad message (don't edit the original "Donate" button message)
        keypad_message = await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="<b>💝 Enter Donation Amount</b>\n\n"
                 "Use the keypad below to enter your donation amount in USD.\n"
                 f"Range: ${self.MIN_AMOUNT:.2f} - ${self.MAX_AMOUNT:.2f}",
            parse_mode="HTML",
            reply_markup=self._create_donation_keypad("0")
        )

        # Store keypad message ID for later editing/deletion
        context.user_data["donation_keypad_message_id"] = keypad_message.message_id
        self.logger.info(f"📋 Sent keypad message {keypad_message.message_id} to chat {query.message.chat.id}")

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

        Note:
            The display button (Row 1) uses "donate_noop" callback which
            does nothing - it's just for showing the current amount.
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

    async def handle_keypad_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Process numeric keypad button presses.
        Handles: digits, decimal, backspace, clear, confirm, cancel, noop

        Callback patterns:
        - donate_digit_{0-9|.} - User pressed a digit or decimal
        - donate_backspace - Delete last character
        - donate_clear - Reset to "0"
        - donate_confirm - Validate and proceed to payment
        - donate_cancel - Cancel donation flow
        - donate_noop - No action (display button)

        Args:
            update: Telegram Update object containing callback query
            context: Telegram context with user data
        """
        query = update.callback_query
        callback_data = query.data

        # Get current building amount
        current_amount = context.user_data.get("donation_amount_building", "0")

        # Route to appropriate handler
        if callback_data.startswith("donate_digit_"):
            await self._handle_digit_press(update, context, current_amount, query)

        elif callback_data == "donate_backspace":
            await self._handle_backspace(update, context, current_amount, query)

        elif callback_data == "donate_clear":
            await self._handle_clear(update, context, query)

        elif callback_data == "donate_confirm":
            await self._handle_confirm(update, context, current_amount, query)

        elif callback_data == "donate_cancel":
            await self._handle_cancel(update, context, query)

        elif callback_data == "donate_noop":
            # Display button, no action needed
            await query.answer()

    async def _handle_digit_press(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        current_amount: str,
        query
    ) -> None:
        """
        Handle digit or decimal button press with validation.

        Validation Rules:
        1. Replace leading zero: "0" + "5" → "5"
        2. Single decimal: "2.5" + "." → REJECT
        3. Max 2 decimal places: "2.55" + "0" → REJECT
        4. Max 4 digits before decimal: "9999" + "9" → REJECT

        Args:
            update: Telegram Update object
            context: Telegram context
            current_amount: Current amount string
            query: Callback query object
        """
        # Extract digit from callback data
        digit = query.data.split("_")[2]  # "donate_digit_5" → "5"

        # Validation Rule 1: Replace leading zero
        if current_amount == "0" and digit != ".":
            new_amount = digit
        # Validation Rule 2: Only one decimal point
        elif digit == "." and "." in current_amount:
            await query.answer("⚠️ Only one decimal point allowed", show_alert=True)
            return
        # Validation Rule 3: Max 2 decimal places
        elif "." in current_amount:
            decimal_part = current_amount.split(".")[1]
            if len(decimal_part) >= self.MAX_DECIMALS and digit != ".":
                await query.answer(f"⚠️ Maximum {self.MAX_DECIMALS} decimal places", show_alert=True)
                return
            new_amount = current_amount + digit
        # Validation Rule 4: Max 4 digits before decimal
        elif digit != "." and len(current_amount) >= self.MAX_DIGITS_BEFORE_DECIMAL:
            await query.answer(f"⚠️ Maximum amount: ${self.MAX_AMOUNT:.2f}", show_alert=True)
            return
        else:
            new_amount = current_amount + digit

        # Update context and keyboard
        context.user_data["donation_amount_building"] = new_amount
        await query.answer()  # Acknowledge button press
        await query.edit_message_reply_markup(
            reply_markup=self._create_donation_keypad(new_amount)
        )

    async def _handle_backspace(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        current_amount: str,
        query
    ) -> None:
        """
        Handle backspace button - delete last character.

        Args:
            update: Telegram Update object
            context: Telegram context
            current_amount: Current amount string
            query: Callback query object
        """
        # Remove last character, reset to "0" if empty
        new_amount = current_amount[:-1] if len(current_amount) > 1 else "0"

        context.user_data["donation_amount_building"] = new_amount
        await query.answer()
        await query.edit_message_reply_markup(
            reply_markup=self._create_donation_keypad(new_amount)
        )

    async def _handle_clear(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        query
    ) -> None:
        """
        Handle clear button - reset to $0.00.

        Args:
            update: Telegram Update object
            context: Telegram context
            query: Callback query object
        """
        context.user_data["donation_amount_building"] = "0"
        await query.answer()
        await query.edit_message_reply_markup(
            reply_markup=self._create_donation_keypad("0")
        )

    async def _schedule_message_deletion(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        message_id: int,
        delay_seconds: int
    ) -> None:
        """
        Schedule automatic message deletion after specified delay.

        This method creates a background task that waits for the specified
        delay and then deletes the message. Used for temporary status messages
        that should not clutter the channel permanently.

        Args:
            context: Telegram context for bot operations
            chat_id: Chat ID where message is located
            message_id: Message ID to delete
            delay_seconds: Delay in seconds before deletion

        Note:
            Errors are caught gracefully (e.g., if user manually deletes message
            or bot loses permissions). Deletion failures are logged as warnings.
        """
        try:
            await asyncio.sleep(delay_seconds)
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            self.logger.info(f"🗑️ Auto-deleted message {message_id} after {delay_seconds}s")
        except Exception as e:
            # Message may have been manually deleted or chat no longer accessible
            self.logger.warning(f"⚠️ Could not delete message {message_id}: {e}")

    async def _handle_confirm(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        current_amount: str,
        query
    ) -> None:
        """
        Handle confirm button - validate amount and trigger payment gateway.

        Final Validations:
        - Amount must be parseable as float
        - Amount >= MIN_AMOUNT ($4.99)
        - Amount <= MAX_AMOUNT ($9999.99)

        Args:
            update: Telegram Update object
            context: Telegram context
            current_amount: Current amount string
            query: Callback query object
        """
        # Validation: Parse amount
        try:
            amount_float = float(current_amount)
        except ValueError:
            await query.answer("❌ Invalid amount format", show_alert=True)
            return

        # Validation: Check minimum
        if amount_float < self.MIN_AMOUNT:
            await query.answer(f"⚠️ Minimum donation: ${self.MIN_AMOUNT:.2f}", show_alert=True)
            return

        # Validation: Check maximum
        if amount_float > self.MAX_AMOUNT:
            await query.answer(f"⚠️ Maximum donation: ${self.MAX_AMOUNT:.2f}", show_alert=True)
            return

        # Store final amount and metadata
        context.user_data["donation_amount"] = amount_float
        context.user_data["is_donation"] = True
        open_channel_id = context.user_data.get("donation_open_channel_id")

        user_id = update.effective_user.id
        self.logger.info(f"✅ Donation confirmed: ${amount_float:.2f} for channel {open_channel_id} by user {user_id}")

        await query.answer()

        # Delete the keypad message
        keypad_message_id = context.user_data.get("donation_keypad_message_id")
        if keypad_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat.id,
                    message_id=keypad_message_id
                )
                self.logger.info(f"🗑️ Deleted keypad message {keypad_message_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete keypad message {keypad_message_id}: {e}")

        # Send NEW independent confirmation message
        confirmation_message = await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=f"✅ <b>Donation Confirmed</b>\n"
                 f"💰 Amount: <b>${amount_float:.2f}</b>\n"
                 f"Preparing your payment gateway... Check your messages with @PayGatePrime_bot",
            parse_mode="HTML"
        )

        # Schedule deletion of confirmation message after 60 seconds
        asyncio.create_task(
            self._schedule_message_deletion(
                context,
                query.message.chat.id,
                confirmation_message.message_id,
                60
            )
        )

        # Trigger payment gateway
        await self._trigger_payment_gateway(update, context, amount_float, open_channel_id)

    async def _handle_cancel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        query
    ) -> None:
        """
        Handle cancel button - abort donation flow.

        Args:
            update: Telegram Update object
            context: Telegram context
            query: Callback query object
        """
        user_id = update.effective_user.id
        self.logger.info(f"🚫 User {user_id} cancelled donation")

        await query.answer()

        # Delete the keypad message
        keypad_message_id = context.user_data.get("donation_keypad_message_id")
        if keypad_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat.id,
                    message_id=keypad_message_id
                )
                self.logger.info(f"🗑️ Deleted keypad message {keypad_message_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete keypad message {keypad_message_id}: {e}")

        # Send NEW independent cancellation message
        cancellation_message = await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="❌ Donation cancelled.",
            parse_mode="HTML"
        )

        # Schedule deletion of cancellation message after 15 seconds
        asyncio.create_task(
            self._schedule_message_deletion(
                context,
                query.message.chat.id,
                cancellation_message.message_id,
                15
            )
        )

        # Clear user data
        context.user_data.pop("donation_amount_building", None)
        context.user_data.pop("donation_open_channel_id", None)
        context.user_data.pop("donation_started_at", None)
        context.user_data.pop("donation_keypad_message_id", None)

    async def _trigger_payment_gateway(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        amount: float,
        open_channel_id: str
    ) -> None:
        """
        Integrate with existing NOWPayments gateway.
        Creates invoice and sends payment button to user's private chat.

        This method bridges the donation input handler with the existing
        payment gateway infrastructure. It reuses the NOWPayments integration
        from start_np_gateway.py.

        Args:
            update: Telegram Update object
            context: Telegram context
            amount: Donation amount in USD
            open_channel_id: Channel ID for payout routing
        """
        user_id = update.effective_user.id

        try:
            # Import payment gateway
            from start_np_gateway import PaymentGatewayManager

            # Initialize gateway manager
            payment_gateway = PaymentGatewayManager()

            # Create order_id in same format as subscriptions
            order_id = f"PGP-{user_id}|{open_channel_id}"

            self.logger.info(f"💰 Creating payment invoice for ${amount:.2f} - order_id: {order_id}")

            # Get success URL from environment or use default
            import os
            base_url = os.getenv("BASE_URL", "https://www.paygateprime.com")
            success_url = f"{base_url}/payment-success"

            # Create invoice using existing payment gateway
            invoice_result = await payment_gateway.create_payment_invoice(
                user_id=user_id,
                amount=amount,
                success_url=success_url,
                order_id=order_id
            )

            # Get user's private chat ID (not the channel where button was clicked)
            # Must send payment button to user's DM, not to the channel
            chat_id = update.effective_user.id

            if invoice_result.get("success"):
                invoice_url = invoice_result["data"].get("invoice_url", "")

                if invoice_url:
                    self.logger.info(f"✅ Payment invoice created successfully for ${amount:.2f}")

                    # Fetch channel details for message formatting
                    channel_details = self.db_manager.get_channel_details_by_open_id(open_channel_id)

                    if channel_details:
                        closed_channel_title = channel_details["closed_channel_title"]
                        closed_channel_description = channel_details["closed_channel_description"]
                    else:
                        # Fallback if channel details not found
                        closed_channel_title = "Premium Channel"
                        closed_channel_description = "Exclusive content"
                        self.logger.warning(f"⚠️ Channel details not found for {open_channel_id}, using fallback")

                    # Create payment button with Web App
                    from telegram import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

                    reply_markup = ReplyKeyboardMarkup.from_button(
                        KeyboardButton(
                            text="💰 Complete Donation Payment",
                            web_app=WebAppInfo(url=invoice_url),
                        )
                    )

                    # Send payment button to user's private chat with new format
                    text = (
                        f"💝 <b>Click the button below to Complete Your ${amount:.2f} Donation</b> 💝\n\n"
                        f"🔒 <b>Private Channel:</b> {closed_channel_title}\n"
                        f"📝 <b>Channel Description:</b> {closed_channel_description}\n"
                        f"💰 <b>Price:</b> ${amount:.2f}"
                    )

                    await context.bot.send_message(
                        chat_id,
                        text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )

                    self.logger.info(f"📨 Payment button sent to user {user_id}")
                else:
                    raise ValueError("No invoice URL in response")

            else:
                # Invoice creation failed
                error_msg = invoice_result.get("error", "Unknown error")
                status_code = invoice_result.get("status_code", "N/A")

                self.logger.error(f"❌ Invoice creation failed: {error_msg} (status: {status_code})")

                await context.bot.send_message(
                    chat_id,
                    f"❌ <b>Payment Gateway Error</b>\n\n"
                    f"We encountered an error creating your payment invoice.\n\n"
                    f"Error: {error_msg}\n"
                    f"Status: {status_code}\n\n"
                    f"Please try again later or contact support.",
                    parse_mode="HTML"
                )

        except Exception as e:
            self.logger.error(f"❌ Failed to create payment invoice: {e}")

            # Send error message to user
            try:
                chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
                await context.bot.send_message(
                    chat_id,
                    "❌ <b>Payment Gateway Error</b>\n\n"
                    "We encountered an unexpected error creating your payment invoice. "
                    "Please try again later or contact support.",
                    parse_mode="HTML"
                )
            except Exception as send_error:
                self.logger.error(f"❌ Failed to send error message to user: {send_error}")
