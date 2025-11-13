# Donation Button Migration Architecture
## From Open Channel to Closed Channel with Custom Amount Input

**Document Version:** 1.0
**Created:** 2025-11-11
**Status:** Architecture Proposal

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Critical Telegram API Limitations](#critical-telegram-api-limitations)
3. [Current vs Proposed Architecture](#current-vs-proposed-architecture)
4. [Database Schema & Mapping](#database-schema--mapping)
5. [Technical Solution: Inline Keyboard Numeric Keypad](#technical-solution-inline-keyboard-numeric-keypad)
6. [Implementation Details](#implementation-details)
7. [Complete Workflow Diagram](#complete-workflow-diagram)
8. [Required Code Changes](#required-code-changes)
9. [Integration with NOWPayments API](#integration-with-nowpayments-api)
10. [Testing & Validation Plan](#testing--validation-plan)
11. [Rollback Strategy](#rollback-strategy)

---

## Executive Summary

### Objective
Migrate the "Donate" button from **open_channel_id** (public channels) to **closed_channel_id** (private/premium channels) while enabling customers to enter **custom donation amounts** and processing payments through the existing NOWPayments API workflow.

### Feasibility: ✅ **YES - POSSIBLE**

### Key Findings
1. ✅ **Telegram bots CAN send messages to closed/private channels** when added as admin
2. ⚠️ **ForceReply does NOT work in channels** (only private chats/groups)
3. ✅ **Solution: Inline Keyboard Numeric Keypad** for custom amount input
4. ✅ **Existing NOWPayments workflow is reusable** (instant & threshold strategies)
5. ✅ **Database mapping already exists** (open_channel_id → closed_channel_id)

---

## Critical Telegram API Limitations

### 1. ForceReply Limitation
**Source:** Telegram Bot API Official Documentation

```
ForceReply: Not supported in channels and for messages sent on behalf
of a Telegram Business account.
```

**Impact:**
- Cannot use ForceReply to prompt text input in channels
- Must use alternative method for amount input

### 2. Channel Message Restrictions
**Workaround Available:**
- Bot must be added as **admin** to the closed channel
- Use chat_id with `-100` prefix for private channels (e.g., `-1003268562225`)
- Inline keyboards **DO work** in channels for button-based interactions

### 3. Callback Data Limit
- **Maximum:** 64 bytes per callback_data
- **Impact:** Must encode data efficiently in button callbacks

---

## Current vs Proposed Architecture

### Current: Donate Button in Open Channel

```
┌─────────────────────────────────────────────────┐
│  OPEN CHANNEL (Public)                          │
│  ID: -1003268562225                             │
│                                                  │
│  [🥇 $10 for 30 days]                           │
│  [🥈 $25 for 60 days]                           │
│  [🥉 $50 for 90 days]                           │
│  [💝 Donate]  ← Currently here                  │
│                                                  │
└─────────────────────────────────────────────────┘
         │ User clicks donate
         ▼
┌─────────────────────────────────────────────────┐
│  PRIVATE CHAT with Bot                          │
│  - Bot asks: "How much to donate?"             │
│  - User types: "25.50"                         │
│  - Bot validates & creates payment             │
└─────────────────────────────────────────────────┘
```

**Issues:**
- Donation button visible to non-members
- No incentive for members to donate after subscribing

### Proposed: Donate Button in Closed Channel

```
┌─────────────────────────────────────────────────┐
│  OPEN CHANNEL (Public)                          │
│  ID: -1003268562225                             │
│                                                  │
│  [🥇 $10 for 30 days]                           │
│  [🥈 $25 for 60 days]                           │
│  [🥉 $50 for 90 days]                           │
│  ← Donate button REMOVED                       │
│                                                  │
└─────────────────────────────────────────────────┘
         │ User pays & subscribes
         ▼
┌─────────────────────────────────────────────────┐
│  CLOSED CHANNEL (Private Members-Only)          │
│  ID: -1002345678901                             │
│                                                  │
│  Premium Content Here...                        │
│                                                  │
│  [💝 Donate to Support This Channel]           │
│  ↑ NOW HERE - Members only                     │
│                                                  │
└─────────────────────────────────────────────────┘
         │ User clicks donate
         ▼
┌─────────────────────────────────────────────────┐
│  INLINE NUMERIC KEYPAD (In Channel Message)     │
│  ┌─────────────────────────────────────┐       │
│  │ Enter donation amount:              │       │
│  │ Current: $0                         │       │
│  ┌─────┬─────┬─────┐                   │       │
│  │  1  │  2  │  3  │                   │       │
│  ├─────┼─────┼─────┤                   │       │
│  │  4  │  5  │  6  │                   │       │
│  ├─────┼─────┼─────┤                   │       │
│  │  7  │  8  │  9  │                   │       │
│  ├─────┼─────┼─────┤                   │       │
│  │  .  │  0  │ ⌫   │                   │       │
│  └─────┴─────┴─────┘                   │       │
│  [Clear] [✅ Confirm - $25.50]         │       │
└─────────────────────────────────────────────────┘
```

**Benefits:**
- ✅ Only paying members see donation option
- ✅ Creates ongoing revenue stream from satisfied customers
- ✅ Better user experience (no context switching to private chat)
- ✅ Amount input happens inline within channel

---

## Database Schema & Mapping

### Main Clients Database Table

**Table:** `main_clients_database`

**Relevant Columns:**
```sql
Column                      | Type         | Purpose
----------------------------|--------------|----------------------------------
open_channel_id             | VARCHAR(14)  | Public channel ID (source)
closed_channel_id           | VARCHAR(14)  | Private channel ID (destination)
client_wallet_address       | TEXT         | Payout destination wallet
client_payout_currency      | VARCHAR(10)  | Currency for payout (USDT, BTC, etc)
client_payout_network       | VARCHAR(50)  | Network (TRX, ETH, BTC, etc)
client_payout_strategy      | VARCHAR(20)  | "instant" or "threshold"
client_payout_threshold_usd | NUMERIC      | Threshold amount for batch payouts
```

### Example Mapping

```
open_channel_id: "-1003268562225"
    ↓ maps to
closed_channel_id: "-1002345678901"
    ↓ with payout config
wallet_address: "THfXtXYWGzqXZjXdJ5V6fQvV3oK3BpQw8N"
payout_currency: "usdt"
payout_network: "trx"
payout_strategy: "threshold"
threshold_usd: 100.00
```

### Lookup Functions (Already Exist)

**File:** `database.py:126-152`

```python
def fetch_closed_channel_id(self, open_channel_id: str) -> Optional[str]:
    """Get closed channel ID for a given open channel"""
    cur.execute(
        "SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s",
        (str(open_channel_id),)
    )
    return cur.fetchone()[0] if result else None

def fetch_client_wallet_info(self, open_channel_id: str):
    """Get wallet address, currency, and network"""
    cur.execute(
        "SELECT client_wallet_address, client_payout_currency, client_payout_network
         FROM main_clients_database WHERE open_channel_id = %s",
        (str(open_channel_id),)
    )
    return cur.fetchone()
```

---

## Technical Solution: Inline Keyboard Numeric Keypad

### Why Inline Keyboard Instead of ForceReply?

| Feature           | ForceReply | Inline Keyboard |
|-------------------|------------|-----------------|
| Works in channels | ❌ NO      | ✅ YES          |
| Custom input      | ✅ YES     | ⚠️ Via buttons  |
| User privacy      | ✅ High    | ✅ High         |
| Validation        | Server     | Client + Server |
| Message editable  | ❌ NO      | ✅ YES          |

### Implementation Pattern

**Based on:** Stack Overflow & python-telegram-bot documentation

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

# Step 1: Create numeric keypad
def create_donation_keypad(current_amount: str = "0") -> InlineKeyboardMarkup:
    """
    Generate inline keyboard with numeric input.
    callback_data format: "donate_input_{action}_{value}"
    """
    keyboard = [
        # Display current amount (non-clickable text)
        [InlineKeyboardButton(f"💰 Amount: ${current_amount}", callback_data="donate_display")],

        # Numeric buttons (rows of 3)
        [
            InlineKeyboardButton("1", callback_data="donate_input_digit_1"),
            InlineKeyboardButton("2", callback_data="donate_input_digit_2"),
            InlineKeyboardButton("3", callback_data="donate_input_digit_3"),
        ],
        [
            InlineKeyboardButton("4", callback_data="donate_input_digit_4"),
            InlineKeyboardButton("5", callback_data="donate_input_digit_5"),
            InlineKeyboardButton("6", callback_data="donate_input_digit_6"),
        ],
        [
            InlineKeyboardButton("7", callback_data="donate_input_digit_7"),
            InlineKeyboardButton("8", callback_data="donate_input_digit_8"),
            InlineKeyboardButton("9", callback_data="donate_input_digit_9"),
        ],
        [
            InlineKeyboardButton(".", callback_data="donate_input_digit_."),
            InlineKeyboardButton("0", callback_data="donate_input_digit_0"),
            InlineKeyboardButton("⌫", callback_data="donate_input_backspace"),
        ],

        # Action buttons
        [
            InlineKeyboardButton("🗑️ Clear", callback_data="donate_input_clear"),
            InlineKeyboardButton("✅ Confirm", callback_data="donate_input_confirm"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

# Step 2: Handle button presses
async def handle_donation_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle numeric keypad button presses.
    Accumulates digits in context.user_data["donation_amount_building"]
    """
    query = update.callback_query
    await query.answer()  # Required by Telegram API

    # Parse callback data
    action_parts = query.data.split("_")  # e.g., ["donate", "input", "digit", "5"]

    # Get current amount being built
    current_amount = context.user_data.get("donation_amount_building", "0")

    if action_parts[2] == "digit":
        digit = action_parts[3]

        # Validation rules
        if current_amount == "0" and digit != ".":
            current_amount = digit
        elif digit == "." and "." in current_amount:
            # Prevent multiple decimals
            await query.answer("Only one decimal point allowed", show_alert=True)
            return
        elif len(current_amount.split(".")[-1]) >= 2 and "." in current_amount:
            # Prevent more than 2 decimal places
            await query.answer("Maximum 2 decimal places", show_alert=True)
            return
        elif len(current_amount.replace(".", "")) >= 6:
            # Prevent amounts over $9999.99
            await query.answer("Maximum amount: $9999.99", show_alert=True)
            return
        else:
            current_amount += digit

    elif action_parts[2] == "backspace":
        current_amount = current_amount[:-1] if len(current_amount) > 1 else "0"

    elif action_parts[2] == "clear":
        current_amount = "0"

    elif action_parts[2] == "confirm":
        # Validate final amount
        try:
            amount_float = float(current_amount)
            if amount_float < 1.00:
                await query.answer("Minimum donation: $1.00", show_alert=True)
                return
            if amount_float > 9999.99:
                await query.answer("Maximum donation: $9999.99", show_alert=True)
                return

            # Store final amount and proceed to payment
            context.user_data["donation_amount"] = amount_float
            await query.edit_message_text(
                f"✅ Donation confirmed: ${amount_float:.2f}\n\n"
                "Preparing payment gateway..."
            )

            # Trigger payment gateway (existing code)
            return await trigger_payment_gateway(update, context)

        except ValueError:
            await query.answer("Invalid amount format", show_alert=True)
            return

    # Update keyboard with new amount
    context.user_data["donation_amount_building"] = current_amount
    await query.edit_message_reply_markup(
        reply_markup=create_donation_keypad(current_amount)
    )
```

### Callback Data Structure

**Format:** `donate_input_{action}_{value}`

| Callback Data                | Action              | Value    |
|------------------------------|---------------------|----------|
| `donate_input_digit_1`       | Add digit           | 1        |
| `donate_input_digit_.`       | Add decimal         | .        |
| `donate_input_backspace`     | Delete last digit   | N/A      |
| `donate_input_clear`         | Reset to 0          | N/A      |
| `donate_input_confirm`       | Validate & proceed  | N/A      |
| `donate_display`             | No action (header)  | N/A      |

---

## Implementation Details

### Phase 1: Remove Donate Button from Open Channel

**File:** `TelePay10-26/broadcast_manager.py:69-72`

**Current Code:**
```python
# Add donation button
donation_token = f"{base_hash}_DONATE"
donation_url = f"https://t.me/{self.bot_username}?start={donation_token}"
buttons_cfg.append({"text": "💝 Donate", "url": donation_url})
```

**Change:**
```python
# REMOVED: Donation button no longer in open channel
# Moved to closed channel implementation (see closed_channel_manager.py)
```

### Phase 2: Create Closed Channel Donation Manager

**New File:** `TelePay10-26/closed_channel_manager.py`

```python
#!/usr/bin/env python
"""
Closed Channel Donation Manager
Sends donate buttons to closed/private channels with inline numeric input.
"""

import logging
from typing import Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from database import DatabaseManager

logger = logging.getLogger(__name__)


class ClosedChannelManager:
    """Manages donation messages in closed/private channels."""

    def __init__(self, bot_token: str, db_manager: DatabaseManager):
        self.bot = Bot(token=bot_token)
        self.db_manager = db_manager

    async def send_donation_message_to_closed_channels(self):
        """
        Send donation button to all closed channels.
        Bot must be admin in these channels.
        """
        # Fetch all closed channel IDs from database
        closed_channels = await self._fetch_all_closed_channels()

        for channel_info in closed_channels:
            closed_channel_id = channel_info["closed_channel_id"]
            open_channel_id = channel_info["open_channel_id"]
            channel_title = channel_info.get("closed_channel_title", "Premium Channel")

            try:
                # Create inline keyboard with single donate button
                keyboard = [
                    [InlineKeyboardButton(
                        "💝 Donate to Support This Channel",
                        callback_data=f"donate_start_{open_channel_id}"
                    )]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Message content
                message_text = (
                    f"<b>💝 Support {channel_title}</b>\n\n"
                    "Enjoying the content? Consider making a donation to help us "
                    "continue providing quality content.\n\n"
                    "Click the button below to donate any amount you choose."
                )

                # Send to closed channel
                await self.bot.send_message(
                    chat_id=closed_channel_id,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

                logger.info(f"📨 Sent donation message to closed channel: {closed_channel_id}")

            except TelegramError as e:
                logger.error(f"❌ Failed to send to {closed_channel_id}: {e}")
                # Common errors:
                # - Bot not admin in channel
                # - Invalid channel ID
                # - Bot blocked/kicked

    async def _fetch_all_closed_channels(self) -> list:
        """Fetch all closed channels from database with their metadata."""
        return self.db_manager.fetch_all_closed_channels()  # Implement in database.py
```

### Phase 3: Handle Donate Button Click

**File:** `TelePay10-26/donation_handlers.py` (New)

```python
#!/usr/bin/env python
"""
Donation Input Handlers with Inline Numeric Keypad
Replaces ForceReply with inline keyboard for channel compatibility.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database import DatabaseManager

logger = logging.getLogger(__name__)

class DonationKeypadHandler:
    """Handles inline numeric keypad for donation amount input."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def start_donation_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        User clicked 'Donate' button in closed channel.
        Show numeric keypad for amount input.

        Callback data format: donate_start_{open_channel_id}
        """
        query = update.callback_query
        await query.answer()

        # Parse open_channel_id from callback data
        callback_parts = query.data.split("_")  # ["donate", "start", "{open_channel_id}"]
        open_channel_id = callback_parts[2]

        # Store channel context
        context.user_data["donation_open_channel_id"] = open_channel_id
        context.user_data["donation_amount_building"] = "0"

        logger.info(f"💝 User {update.effective_user.id} started donation for channel {open_channel_id}")

        # Show numeric keypad
        await query.edit_message_text(
            text="💝 <b>Enter Donation Amount</b>\n\n"
                 "Use the keypad below to enter your donation amount in USD.\n"
                 "Range: $1.00 - $9999.99",
            parse_mode="HTML",
            reply_markup=self._create_donation_keypad("0")
        )

    def _create_donation_keypad(self, current_amount: str) -> InlineKeyboardMarkup:
        """Generate inline numeric keypad."""
        # Format amount for display
        display_amount = f"${current_amount}" if current_amount != "0" else "$0.00"

        keyboard = [
            # Display row
            [InlineKeyboardButton(f"💰 {display_amount}", callback_data="donate_noop")],

            # Numeric pad
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
            [
                InlineKeyboardButton("🗑️ Clear", callback_data="donate_clear"),
            ],
            [
                InlineKeyboardButton("✅ Confirm & Pay", callback_data="donate_confirm"),
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="donate_cancel"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def handle_keypad_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Process numeric keypad button presses.
        Handles: digits, decimal, backspace, clear, confirm, cancel
        """
        query = update.callback_query
        callback_data = query.data

        # Get current building amount
        current_amount = context.user_data.get("donation_amount_building", "0")

        # Parse action
        if callback_data.startswith("donate_digit_"):
            # User pressed a digit or decimal
            digit = callback_data.split("_")[2]
            new_amount = self._add_digit(current_amount, digit, query)

            if new_amount is None:
                return  # Validation error, alert already shown

            context.user_data["donation_amount_building"] = new_amount

            # Update keyboard
            await query.edit_message_reply_markup(
                reply_markup=self._create_donation_keypad(new_amount)
            )

        elif callback_data == "donate_backspace":
            new_amount = current_amount[:-1] if len(current_amount) > 1 else "0"
            context.user_data["donation_amount_building"] = new_amount

            await query.edit_message_reply_markup(
                reply_markup=self._create_donation_keypad(new_amount)
            )

        elif callback_data == "donate_clear":
            context.user_data["donation_amount_building"] = "0"
            await query.edit_message_reply_markup(
                reply_markup=self._create_donation_keypad("0")
            )

        elif callback_data == "donate_confirm":
            await self._confirm_and_pay(update, context, current_amount)

        elif callback_data == "donate_cancel":
            await query.edit_message_text("❌ Donation cancelled.")
            # Clear user data
            context.user_data.pop("donation_amount_building", None)
            context.user_data.pop("donation_open_channel_id", None)

        elif callback_data == "donate_noop":
            # Display button, no action needed
            await query.answer()

    async def _add_digit(self, current: str, digit: str, query) -> Optional[str]:
        """
        Add digit to current amount with validation.
        Returns new amount or None if invalid.
        """
        # Rule 1: Replace leading zero
        if current == "0" and digit != ".":
            return digit

        # Rule 2: Only one decimal point
        if digit == "." and "." in current:
            await query.answer("⚠️ Only one decimal point allowed", show_alert=True)
            return None

        # Rule 3: Max 2 decimal places
        if "." in current:
            decimal_part = current.split(".")[1]
            if len(decimal_part) >= 2:
                await query.answer("⚠️ Maximum 2 decimal places", show_alert=True)
                return None

        # Rule 4: Max amount $9999.99 (4 digits before decimal)
        if digit != "." and "." not in current:
            if len(current) >= 4:
                await query.answer("⚠️ Maximum amount: $9999.99", show_alert=True)
                return None

        await query.answer()  # Acknowledge button press
        return current + digit

    async def _confirm_and_pay(self, update: Update, context: ContextTypes.DEFAULT_TYPE, amount_str: str):
        """Validate final amount and trigger payment gateway."""
        query = update.callback_query

        # Validation
        try:
            amount_float = float(amount_str)
        except ValueError:
            await query.answer("❌ Invalid amount format", show_alert=True)
            return

        if amount_float < 1.00:
            await query.answer("⚠️ Minimum donation: $1.00", show_alert=True)
            return

        if amount_float > 9999.99:
            await query.answer("⚠️ Maximum donation: $9999.99", show_alert=True)
            return

        # Store final amount
        context.user_data["donation_amount"] = amount_float
        open_channel_id = context.user_data.get("donation_open_channel_id")

        logger.info(f"✅ Donation confirmed: ${amount_float:.2f} for channel {open_channel_id}")

        # Update message
        await query.edit_message_text(
            f"✅ <b>Donation Confirmed</b>\n\n"
            f"Amount: <b>${amount_float:.2f}</b>\n\n"
            f"Preparing your payment gateway...",
            parse_mode="HTML"
        )

        # Trigger existing payment gateway
        # Import and use existing start_np_gateway logic
        from start_np_gateway import start_payment_flow

        # Note: This needs adaptation since start_payment_flow expects Update with message
        # We'll need to create a synthetic flow or refactor start_payment_flow
        # to accept callback query updates

        await self._trigger_donation_payment_gateway(update, context, amount_float, open_channel_id)

    async def _trigger_donation_payment_gateway(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        amount: float,
        open_channel_id: str
    ):
        """
        Integrate with existing NOWPayments gateway.
        Reuses logic from start_np_gateway.py
        """
        from start_np_gateway import NowPaymentsGateway

        gateway = NowPaymentsGateway(
            api_key=context.bot_data["nowpayments_api_key"],
            ipn_callback_url=context.bot_data["ipn_callback_url"]
        )

        user_id = update.effective_user.id
        order_id = f"PGP-{user_id}|{open_channel_id}"

        # Create invoice
        invoice_url = await gateway.create_invoice(
            amount=amount,
            order_id=order_id,
            user_id=user_id
        )

        if invoice_url:
            # Send payment button to user's private chat
            keyboard = [[InlineKeyboardButton(
                "💰 Complete Payment",
                web_app={"url": invoice_url}
            )]]

            await context.bot.send_message(
                chat_id=user_id,
                text=f"💝 <b>Complete Your ${amount:.2f} Donation</b>\n\n"
                     f"Click below to proceed to payment gateway.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            logger.info(f"💰 Payment gateway sent to user {user_id} for ${amount:.2f}")
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Failed to create payment invoice. Please try again later."
            )
            logger.error(f"❌ Failed to create invoice for user {user_id}")
```

### Phase 4: Register Handlers

**File:** `TelePay10-26/tpr10-26.py` (Main bot file)

```python
from donation_handlers import DonationKeypadHandler
from closed_channel_manager import ClosedChannelManager

# Initialize donation handler
donation_handler = DonationKeypadHandler(db_manager=db_manager)

# Register callback query handlers
application.add_handler(CallbackQueryHandler(
    donation_handler.start_donation_input,
    pattern=r"^donate_start_"
))

application.add_handler(CallbackQueryHandler(
    donation_handler.handle_keypad_input,
    pattern=r"^donate_(digit|backspace|clear|confirm|cancel|noop)"
))

# Send donation messages to closed channels on startup (or via cron)
closed_channel_mgr = ClosedChannelManager(bot_token=BOT_TOKEN, db_manager=db_manager)
# await closed_channel_mgr.send_donation_message_to_closed_channels()
```

---

## Complete Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER SUBSCRIBES & JOINS CLOSED CHANNEL                      │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. BOT SENDS DONATION MESSAGE TO CLOSED CHANNEL                 │
│    - Message contains inline button: [💝 Donate]                │
│    - callback_data: "donate_start_{open_channel_id}"            │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. USER CLICKS [💝 Donate] IN CLOSED CHANNEL                    │
│    - Callback query received by bot                             │
│    - Extract open_channel_id from callback_data                 │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. BOT EDITS MESSAGE TO SHOW NUMERIC KEYPAD                     │
│    ┌─────────────────────────────┐                              │
│    │ 💰 Amount: $0.00           │                              │
│    ├───────┬───────┬───────┐     │                              │
│    │   1   │   2   │   3   │     │                              │
│    ├───────┼───────┼───────┤     │                              │
│    │   4   │   5   │   6   │     │                              │
│    ├───────┼───────┼───────┤     │                              │
│    │   7   │   8   │   9   │     │                              │
│    ├───────┼───────┼───────┤     │                              │
│    │   .   │   0   │   ⌫   │     │                              │
│    └───────┴───────┴───────┘     │                              │
│    [Clear] [✅ Confirm & Pay]    │                              │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. USER ENTERS AMOUNT VIA KEYPAD                                │
│    - Each button press updates display in real-time             │
│    - Validation: 1-9999.99, max 2 decimals, no leading zeros   │
│    - Example: User presses: 2 → 5 → . → 5 → 0                  │
│    - Display shows: $25.50                                      │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. USER CLICKS [✅ Confirm & Pay]                               │
│    - Final validation: $1.00 <= amount <= $9999.99             │
│    - Store amount in context.user_data["donation_amount"]      │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. BOT CREATES NOWPAYMENTS INVOICE                              │
│    - order_id: "PGP-{user_id}|{open_channel_id}"               │
│    - price_amount: {donation_amount}                            │
│    - price_currency: "USD"                                      │
│    - ipn_callback_url: {webhook_url}                            │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. BOT SENDS PAYMENT LINK TO USER'S PRIVATE CHAT                │
│    "💝 Complete Your $25.50 Donation"                           │
│    [💰 Complete Payment] ← Web App Button                       │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. USER COMPLETES PAYMENT ON NOWPAYMENTS                        │
│    - Selects crypto (BTC, ETH, USDT, etc.)                      │
│    - Sends payment to generated address                         │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. NOWPAYMENTS SENDS IPN CALLBACK TO WEBHOOK                   │
│     - payment_status: "finished"                                │
│     - Webhook parses order_id → extracts open_channel_id        │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 11. WEBHOOK DETERMINES PAYOUT STRATEGY                          │
│     Query: SELECT client_payout_strategy, client_payout_threshold│
│            FROM main_clients_database                           │
│            WHERE open_channel_id = {parsed_id}                  │
└─────────────────────────────────────────────────────────────────┘
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
    ┌─────────────────┐   ┌─────────────────┐
    │  INSTANT        │   │  THRESHOLD      │
    └─────────────────┘   └─────────────────┘
         │                         │
         │                         ▼
         │              ┌─────────────────────────────┐
         │              │ Add to payout_accumulation  │
         │              │ WHERE open_channel_id = X   │
         │              └─────────────────────────────┘
         │                         │
         │                         ▼
         │              ┌─────────────────────────────┐
         │              │ Check if >= threshold       │
         │              │ If YES: Trigger batch payout│
         │              │ If NO: Wait for more        │
         │              └─────────────────────────────┘
         │                         │
         └─────────┬───────────────┘
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ 12. PAYOUT TO CLIENT WALLET                                     │
│     - Wallet: client_wallet_address                             │
│     - Currency: client_payout_currency (USDT/BTC/ETH)           │
│     - Network: client_payout_network (TRX/ETH/BTC)              │
│     - Record transaction in database                            │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 13. CONFIRMATION MESSAGE (Optional)                             │
│     Send thank you message to closed channel or user            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration with NOWPayments API

### Existing Workflow Compatibility

The current NOWPayments integration **already supports donations**. Only minor modifications needed:

**File:** `TelePay10-26/start_np_gateway.py:235-316`

**Current Code (Works for Donations):**
```python
# Create invoice
invoice_payload = {
    "price_amount": amount,
    "price_currency": "USD",
    "order_id": order_id,  # Format: PGP-{user_id}|{open_channel_id}
    "order_description": "Payment-Test-1",
    "success_url": success_url,
    "ipn_callback_url": self.ipn_callback_url,
    "is_fixed_rate": False,
    "is_fee_paid_by_user": False
}
```

**Modification Needed:**
```python
# Detect if order is donation vs subscription
is_donation = context.user_data.get("is_donation", False)

order_description = "Donation" if is_donation else "Subscription"

invoice_payload = {
    "price_amount": amount,
    "price_currency": "USD",
    "order_id": order_id,
    "order_description": order_description,  # ← Updated
    # ... rest unchanged
}
```

### Webhook Processing

**File:** `np-webhook-10-26/app.py:218-267`

**Current Logic (Already Handles Donations):**
```python
# Parse order_id
order_id = payment_data.get("order_id")  # "PGP-123456789|{open_channel_id}"
parts = order_id.split("|")
user_id = parts[0].replace("PGP-", "")
open_channel_id = parts[1]

# Fetch closed channel
closed_channel_id = db_manager.fetch_closed_channel_id(open_channel_id)

# Add user to channel (for subscriptions)
# OR
# Process payout (for donations)
```

**No changes required** - webhook already extracts `open_channel_id` and processes payouts based on `client_payout_strategy`.

---

## Required Code Changes

### Summary of Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `broadcast_manager.py` | **MODIFY** | Remove donate button from open channel |
| `closed_channel_manager.py` | **CREATE** | Send donate button to closed channels |
| `donation_handlers.py` | **CREATE** | Handle inline numeric keypad input |
| `database.py` | **MODIFY** | Add `fetch_all_closed_channels()` method |
| `tpr10-26.py` | **MODIFY** | Register new callback handlers |
| `start_np_gateway.py` | **MODIFY** | Add order_description for donations |

### Database Changes Required

**New Method in `database.py`:**

```python
def fetch_all_closed_channels(self) -> list:
    """
    Fetch all closed channels with their associated metadata.

    Returns:
        List of dicts containing:
        - closed_channel_id
        - open_channel_id
        - closed_channel_title
        - closed_channel_description
        - client_payout_strategy
    """
    try:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                closed_channel_id,
                open_channel_id,
                closed_channel_title,
                closed_channel_description,
                client_payout_strategy
            FROM main_clients_database
            WHERE closed_channel_id IS NOT NULL
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        result = []
        for row in rows:
            result.append({
                "closed_channel_id": row[0],
                "open_channel_id": row[1],
                "closed_channel_title": row[2],
                "closed_channel_description": row[3],
                "payout_strategy": row[4]
            })

        print(f"📋 [DEBUG] Fetched {len(result)} closed channels")
        return result

    except Exception as e:
        print(f"❌ Error fetching closed channels: {e}")
        return []
```

---

## Testing & Validation Plan

### Phase 1: Unit Testing

**Test Cases:**

1. **Numeric Keypad Validation**
   - ✅ Input: "2" → "5" → "." → "5" → "0" = $25.50
   - ✅ Input: "1" → "0" → "0" → "0" → "0" = $10000 → REJECT (max $9999.99)
   - ✅ Input: "0" → "." → "5" → "0" = $0.50 → REJECT (min $1.00)
   - ✅ Input: "2" → "5" → "." → "5" → "0" → "5" → REJECT (max 2 decimals)
   - ✅ Input: "2" → "." → "." → REJECT (multiple decimals)

2. **Callback Data Parsing**
   - ✅ `donate_start_-1003268562225` → Extract channel ID correctly
   - ✅ `donate_digit_5` → Add "5" to amount
   - ✅ `donate_backspace` → Remove last digit

3. **Database Lookups**
   - ✅ `fetch_closed_channel_id("-1003268562225")` → Returns correct closed ID
   - ✅ `fetch_all_closed_channels()` → Returns all configured channels

### Phase 2: Integration Testing

**Test Scenarios:**

1. **End-to-End Donation Flow**
   ```
   1. User joins closed channel after subscribing
   2. Bot sends donation message to closed channel
   3. User clicks [💝 Donate]
   4. Keypad appears with $0.00
   5. User enters: 2 → 5 → . → 0 → 0
   6. Display shows: $25.00
   7. User clicks [✅ Confirm & Pay]
   8. Payment gateway link sent to private chat
   9. User pays via NOWPayments
   10. Webhook processes payment
   11. Payout sent to client wallet (based on strategy)
   ```

2. **Error Handling**
   - ❌ Bot not admin in closed channel → Log error, skip channel
   - ❌ Invalid channel ID → Log error, continue to next
   - ❌ Payment creation fails → Show error to user
   - ❌ Webhook signature invalid → Reject IPN callback

### Phase 3: Load Testing

**Metrics to Monitor:**
- Concurrent users using keypad simultaneously
- Message edit rate limits (Telegram has rate limits on edits)
- Database connection pool under load
- Webhook processing latency

---

## Rollback Strategy

### Rollback Trigger Conditions

1. **Critical:** Bot fails to send messages to closed channels
2. **Critical:** Payment gateway creation fails > 10% of requests
3. **High:** User complaints about keypad not working
4. **Medium:** Webhook fails to parse order_id correctly

### Rollback Steps

**Step 1: Restore Donate Button to Open Channel**
```bash
# Revert broadcast_manager.py
git checkout HEAD~1 -- TelePay10-26/broadcast_manager.py

# Redeploy bot
gcloud run deploy telepay-bot --source . --region us-central1
```

**Step 2: Disable Closed Channel Messages**
```python
# In tpr10-26.py, comment out:
# await closed_channel_mgr.send_donation_message_to_closed_channels()
```

**Step 3: Remove Callback Handlers**
```python
# In tpr10-26.py, comment out:
# application.add_handler(CallbackQueryHandler(donation_handler.start_donation_input))
# application.add_handler(CallbackQueryHandler(donation_handler.handle_keypad_input))
```

**Step 4: Verify Old Flow Still Works**
```bash
# Test donation from open channel
# User clicks donate → Private chat opens → Enters amount via text → Payment works
```

### Data Migration

**No database schema changes required** - all existing tables support this feature.

**IF rollback needed:**
- No data cleanup necessary
- Existing donation records remain valid
- Switch back to old flow instantly

---

## Deployment Checklist

### Pre-Deployment

- [ ] Review and test `closed_channel_manager.py`
- [ ] Review and test `donation_handlers.py`
- [ ] Verify bot is admin in all closed channels
- [ ] Test numeric keypad validation exhaustively
- [ ] Create staging environment replica
- [ ] Test end-to-end donation flow in staging
- [ ] Monitor logs for errors/warnings

### Deployment

- [ ] Deploy new code to Cloud Run
- [ ] Verify bot restarts successfully
- [ ] Send test donation message to ONE closed channel
- [ ] Complete test donation transaction
- [ ] Verify webhook processes donation correctly
- [ ] Verify payout logic executes (instant or threshold)
- [ ] Check database for transaction records

### Post-Deployment

- [ ] Monitor bot logs for 24 hours
- [ ] Track donation conversion rate
- [ ] Monitor user feedback in closed channels
- [ ] Verify no errors in GCP Cloud Logging
- [ ] Document any issues in BUGS.md
- [ ] Update PROGRESS.md with deployment status

---

## Metrics & Success Criteria

### Key Performance Indicators (KPIs)

1. **Adoption Rate**
   - Target: >10% of closed channel members donate within 30 days

2. **Average Donation Amount**
   - Target: >$15.00 (higher than minimum subscription tier)

3. **Completion Rate**
   - Target: >70% of users who open keypad complete donation

4. **Technical Metrics**
   - Keypad response time: <500ms per button press
   - Payment creation success rate: >95%
   - Webhook processing success rate: >99%

### Monitoring Queries

**GCP Cloud Logging:**

```
# Track donation initiations
resource.type="cloud_run_revision"
textPayload=~"started donation for channel"

# Track payment completions
resource.type="cloud_run_revision"
textPayload=~"Donation confirmed"

# Track errors
resource.type="cloud_run_revision"
severity="ERROR"
textPayload=~"donation|keypad"
```

---

## Security Considerations

### 1. Callback Data Validation

**Risk:** Malicious users could craft fake callback_data

**Mitigation:**
```python
# Validate channel ID exists in database
open_channel_id = callback_parts[2]
if not db_manager.channel_exists(open_channel_id):
    logger.warning(f"⚠️ Invalid channel ID in callback: {open_channel_id}")
    await query.answer("Invalid channel", show_alert=True)
    return
```

### 2. Amount Validation

**Risk:** Users could manipulate amount via client-side tampering

**Mitigation:**
- Server-side validation in `_confirm_and_pay()`
- Double-check amount before creating invoice
- Log all amounts for audit trail

### 3. Webhook Signature Verification

**Risk:** Fake IPN callbacks could trigger fraudulent payouts

**Mitigation:**
- Already implemented HMAC-SHA512 signature verification
- Reject any callback with invalid signature
- Rate limit webhook endpoint

### 4. Bot Token Security

**Risk:** Exposed bot token allows unauthorized access

**Mitigation:**
- Store in Google Secret Manager
- Never log bot token
- Rotate token if compromised

---

## Conclusion

### Feasibility: ✅ **CONFIRMED**

This architecture is **technically sound and fully implementable** using:
1. ✅ Telegram Bot API inline keyboards (works in channels)
2. ✅ Callback queries for numeric input accumulation
3. ✅ Existing NOWPayments integration
4. ✅ Existing database schema
5. ✅ Proven design patterns from Stack Overflow & python-telegram-bot docs

### Estimated Implementation Time

| Phase | Task | Time Estimate |
|-------|------|---------------|
| 1 | Create `closed_channel_manager.py` | 4 hours |
| 2 | Create `donation_handlers.py` | 6 hours |
| 3 | Modify existing files | 2 hours |
| 4 | Testing & debugging | 6 hours |
| 5 | Deployment & monitoring | 2 hours |
| **TOTAL** | | **20 hours** |

### Recommended Next Steps

1. **Approval:** Review this architecture with stakeholders
2. **Staging:** Set up test closed channel for validation
3. **Development:** Implement `closed_channel_manager.py` first
4. **Testing:** Exhaustive keypad validation testing
5. **Deployment:** Gradual rollout (1 channel → all channels)
6. **Monitoring:** Track metrics for 2 weeks before declaring success

---

## Appendix A: Alternative Approaches Considered

### Option 1: ForceReply in Private Chat (REJECTED)

**Reason:** Requires context switch from channel to private chat, poor UX

### Option 2: Web App Form (CONSIDERED)

**Pros:** Rich UI, easier validation
**Cons:** More complex, requires separate web hosting
**Decision:** Inline keyboard is simpler and sufficient

### Option 3: Preset Donation Amounts (REJECTED)

**Reason:** User requested custom amount input capability

---

## Appendix B: External References

1. **Telegram Bot API Documentation**
   - https://core.telegram.org/bots/api
   - InlineKeyboardMarkup: https://core.telegram.org/bots/api#inlinekeyboardmarkup
   - CallbackQuery: https://core.telegram.org/bots/api#callbackquery

2. **python-telegram-bot Documentation**
   - https://docs.python-telegram-bot.org/
   - Inline Keyboard Examples: https://github.com/python-telegram-bot/python-telegram-bot/wiki/InlineKeyboard-Example

3. **Stack Overflow References**
   - Numeric keypad implementation: https://stackoverflow.com/questions/63415226/number-keyboard-for-python-telegram-bot
   - Accumulating callback data: https://stackoverflow.com/questions/60601179/how-to-get-data-from-inline-keyboard-as-single-result

4. **NOWPayments API**
   - IPN Callbacks: https://documenter.getpostman.com/view/7907941/2s93JusNJt

---

**END OF ARCHITECTURE DOCUMENT**
