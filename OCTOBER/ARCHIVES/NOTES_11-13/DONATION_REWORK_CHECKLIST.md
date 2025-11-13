# Donation Rework Implementation Checklist
## Modular Implementation Plan for Closed Channel Donations

**Reference Document:** `DONATION_REWORK.md`
**Target:** Migrate donations from open channels to closed channels with custom amount input
**Estimated Total Time:** 20 hours
**Status:** 🔴 Not Started

---

## Table of Contents
1. [Phase 0: Pre-Implementation Setup](#phase-0-pre-implementation-setup)
2. [Phase 1: Database Layer Enhancement](#phase-1-database-layer-enhancement)
3. [Phase 2: Closed Channel Management Module](#phase-2-closed-channel-management-module)
4. [Phase 3: Donation Input Handler Module](#phase-3-donation-input-handler-module)
5. [Phase 4: Payment Gateway Integration](#phase-4-payment-gateway-integration)
6. [Phase 5: Main Application Integration](#phase-5-main-application-integration)
7. [Phase 6: Broadcast Manager Cleanup](#phase-6-broadcast-manager-cleanup)
8. [Phase 7: Testing & Validation](#phase-7-testing--validation)
9. [Phase 8: Deployment](#phase-8-deployment)
10. [Phase 9: Monitoring & Optimization](#phase-9-monitoring--optimization)

---

## Phase 0: Pre-Implementation Setup
**Estimated Time:** 1 hour
**Status:** ⬜ Not Started

### 0.1 Environment Preparation
- [ ] **Task:** Review current codebase structure
  - **File:** Entire `OCTOBER/10-26/TelePay10-26/` directory
  - **Action:** Document current file organization
  - **Output:** Understanding of existing module dependencies

- [ ] **Task:** Create backup of current working code
  - **Command:** `git branch backup-pre-donation-rework`
  - **Verify:** Branch created successfully
  - **Rollback Plan:** `git checkout backup-pre-donation-rework`

- [ ] **Task:** Verify bot is admin in all closed channels
  - **Method:** Manual check or script
  - **Critical:** Bot MUST have admin rights to post messages
  - **Action Items:**
    - Query database for all `closed_channel_id` values
    - For each channel, verify bot has `can_post_messages` permission
    - Document any channels where bot is not admin

- [ ] **Task:** Set up test closed channel
  - **Create:** Test channel for development: `-100XXXXXXXXXX`
  - **Add:** Bot as admin with posting rights
  - **Add:** Your personal account as member
  - **Purpose:** Isolated testing environment

- [ ] **Task:** Review architectural decisions
  - **File:** `DONATION_REWORK.md`
  - **Focus:** Sections 5, 6, 7 (implementation details)
  - **Clarify:** Any ambiguities before coding

---

## Phase 1: Database Layer Enhancement
**Estimated Time:** 2 hours
**Status:** ⬜ Not Started
**Module:** `database.py`

### 1.1 Add Closed Channel Query Method
- [ ] **Task:** Implement `fetch_all_closed_channels()` method
  - **File:** `TelePay10-26/database.py`
  - **Location:** After `get_default_donation_channel()` (line ~208)
  - **Function Signature:**
    ```python
    def fetch_all_closed_channels(self) -> List[Dict[str, Any]]:
    ```
  - **SQL Query:**
    ```sql
    SELECT
        closed_channel_id,
        open_channel_id,
        closed_channel_title,
        closed_channel_description,
        client_payout_strategy,
        client_payout_threshold_usd
    FROM main_clients_database
    WHERE closed_channel_id IS NOT NULL
        AND closed_channel_id != ''
    ORDER BY closed_channel_id
    ```
  - **Return Format:**
    ```python
    [
        {
            "closed_channel_id": "-1002345678901",
            "open_channel_id": "-1003268562225",
            "closed_channel_title": "Premium Content",
            "closed_channel_description": "Exclusive access",
            "payout_strategy": "threshold",
            "payout_threshold_usd": 100.00
        },
        ...
    ]
    ```
  - **Error Handling:** Try-except with logging
  - **Logging:** Use existing emoji patterns (📋, ❌)

- [ ] **Task:** Add channel existence validation method
  - **File:** `TelePay10-26/database.py`
  - **Location:** After `fetch_all_closed_channels()`
  - **Function Signature:**
    ```python
    def channel_exists(self, open_channel_id: str) -> bool:
    ```
  - **Purpose:** Security validation for callback data
  - **Query:**
    ```sql
    SELECT 1 FROM main_clients_database
    WHERE open_channel_id = %s LIMIT 1
    ```
  - **Return:** `True` if exists, `False` otherwise

- [ ] **Task:** Test database methods
  - **Test Script:** Create `TelePay10-26/tests/test_database_donations.py`
  - **Test Cases:**
    - `fetch_all_closed_channels()` returns correct structure
    - `channel_exists()` returns True for valid channel
    - `channel_exists()` returns False for invalid channel
    - Handles database connection errors gracefully
  - **Run:** `python3 tests/test_database_donations.py`

### 1.2 Documentation
- [ ] **Task:** Add docstrings to new methods
  - **Standard:** Follow existing docstring format in `database.py`
  - **Include:** Args, Returns, Raises, Example usage

- [ ] **Task:** Update DECISIONS.md
  - **Entry:**
    ```
    [2025-11-11] Database: Added fetch_all_closed_channels() and channel_exists()
    - Enables querying all closed channels for donation message broadcasting
    - Validates channel IDs in callback data for security
    - No schema changes required - uses existing columns
    ```

---

## Phase 2: Closed Channel Management Module
**Estimated Time:** 4 hours
**Status:** ⬜ Not Started
**Module:** NEW FILE - `closed_channel_manager.py`

### 2.1 Create Module File
- [ ] **Task:** Create `TelePay10-26/closed_channel_manager.py`
  - **Location:** Same directory as `broadcast_manager.py`
  - **Size Target:** ~200-300 lines (keep focused)
  - **Dependencies:**
    ```python
    import logging
    from typing import Optional, List, Dict, Any
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.error import TelegramError, Forbidden, BadRequest
    from database import DatabaseManager
    ```

### 2.2 Implement ClosedChannelManager Class
- [ ] **Task:** Define class structure
  - **Class Name:** `ClosedChannelManager`
  - **Purpose:** Manage donation messages in closed/private channels
  - **Init Method:**
    ```python
    def __init__(self, bot_token: str, db_manager: DatabaseManager):
        self.bot = Bot(token=bot_token)
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    ```

- [ ] **Task:** Implement `send_donation_message_to_closed_channels()`
  - **Method Signature:**
    ```python
    async def send_donation_message_to_closed_channels(
        self,
        force_resend: bool = False
    ) -> Dict[str, Any]:
    ```
  - **Functionality:**
    1. Fetch all closed channels from database
    2. For each channel:
       - Create donation button with callback_data
       - Format message with channel title
       - Send to closed channel
       - Log success/failure
    3. Return summary statistics
  - **Return Format:**
    ```python
    {
        "total_channels": 5,
        "successful": 4,
        "failed": 1,
        "errors": [{"channel_id": "-100XXX", "error": "Bot not admin"}]
    }
    ```

- [ ] **Task:** Implement `_create_donation_button()`
  - **Method Signature:**
    ```python
    def _create_donation_button(
        self,
        open_channel_id: str
    ) -> InlineKeyboardMarkup:
    ```
  - **Button Configuration:**
    ```python
    button = InlineKeyboardButton(
        text="💝 Donate to Support This Channel",
        callback_data=f"donate_start_{open_channel_id}"
    )
    ```
  - **Layout:** Single button, single row
  - **Validation:** Ensure callback_data <= 64 bytes

- [ ] **Task:** Implement `_format_donation_message()`
  - **Method Signature:**
    ```python
    def _format_donation_message(
        self,
        channel_title: str,
        channel_description: str
    ) -> str:
    ```
  - **Message Template:**
    ```python
    f"<b>💝 Support {channel_title}</b>\n\n"
    f"Enjoying the content? Consider making a donation to help us "
    f"continue providing quality {channel_description}.\n\n"
    f"Click the button below to donate any amount you choose."
    ```
  - **Parse Mode:** HTML
  - **Max Length:** <4096 characters (Telegram limit)

### 2.3 Error Handling & Logging
- [ ] **Task:** Implement comprehensive error handling
  - **Error Types to Handle:**
    - `Forbidden`: Bot not in channel or kicked
    - `BadRequest`: Invalid channel ID
    - `TelegramError`: General API errors
    - `Exception`: Database/connection errors
  - **Logging Pattern:**
    ```python
    # Success
    self.logger.info(f"📨 Sent donation message to {closed_channel_id}")

    # Failure
    self.logger.error(f"❌ Failed to send to {closed_channel_id}: {error}")

    # Warning
    self.logger.warning(f"⚠️ Bot not admin in {closed_channel_id}")
    ```

- [ ] **Task:** Add retry logic for transient failures
  - **Retry Count:** 3 attempts
  - **Backoff:** Exponential (1s, 2s, 4s)
  - **Retry Conditions:** Network errors, rate limits
  - **Skip Conditions:** Forbidden, BadRequest (permanent failures)

### 2.4 Testing
- [ ] **Task:** Create unit tests
  - **File:** `TelePay10-26/tests/test_closed_channel_manager.py`
  - **Test Cases:**
    - Mock successful message send
    - Mock bot not admin error
    - Mock invalid channel ID error
    - Verify correct callback_data format
    - Test message formatting with various inputs

- [ ] **Task:** Manual testing with test channel
  - **Action:** Run `send_donation_message_to_closed_channels()` on test channel
  - **Verify:**
    - Message appears in closed channel
    - Button displays correctly
    - Callback_data is correct format
    - No errors in logs

### 2.5 Documentation
- [ ] **Task:** Add module docstring
  - **Location:** Top of `closed_channel_manager.py`
  - **Content:** Module purpose, usage example, dependencies

- [ ] **Task:** Update DECISIONS.md
  - **Entry:**
    ```
    [2025-11-11] Module: Created closed_channel_manager.py
    - Handles all closed channel donation message operations
    - Separation of concerns: broadcast_manager (open) vs closed_channel_manager (closed)
    - Async implementation for better performance
    - Comprehensive error handling for channel permissions
    ```

---

## Phase 3: Donation Input Handler Module
**Estimated Time:** 6 hours
**Status:** ⬜ Not Started
**Module:** NEW FILE - `donation_input_handler.py`

### 3.1 Create Module File
- [ ] **Task:** Create `TelePay10-26/donation_input_handler.py`
  - **Location:** Same directory as `input_handlers.py`
  - **Size Target:** ~400-500 lines (complex validation logic)
  - **Dependencies:**
    ```python
    import logging
    from typing import Optional, Dict, Any
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ContextTypes, CallbackQueryHandler
    from database import DatabaseManager
    ```

### 3.2 Implement DonationKeypadHandler Class
- [ ] **Task:** Define class structure
  - **Class Name:** `DonationKeypadHandler`
  - **Purpose:** Handle inline numeric keypad for donation amount input
  - **Init Method:**
    ```python
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

        # Validation constants
        self.MIN_AMOUNT = 1.00
        self.MAX_AMOUNT = 9999.99
        self.MAX_DECIMALS = 2
        self.MAX_DIGITS_BEFORE_DECIMAL = 4
    ```

### 3.3 Implement Keypad UI
- [ ] **Task:** Implement `_create_donation_keypad()`
  - **Method Signature:**
    ```python
    def _create_donation_keypad(
        self,
        current_amount: str = "0"
    ) -> InlineKeyboardMarkup:
    ```
  - **Layout:**
    ```
    Row 1: [💰 Amount: $0.00]  ← Display only
    Row 2: [1] [2] [3]
    Row 3: [4] [5] [6]
    Row 4: [7] [8] [9]
    Row 5: [.] [0] [⌫]
    Row 6: [🗑️ Clear]
    Row 7: [✅ Confirm & Pay]
    Row 8: [❌ Cancel]
    ```
  - **Callback Data Format:**
    - Digit: `donate_digit_0` through `donate_digit_9`
    - Decimal: `donate_digit_.`
    - Backspace: `donate_backspace`
    - Clear: `donate_clear`
    - Confirm: `donate_confirm`
    - Cancel: `donate_cancel`
    - Display: `donate_noop` (no action)

- [ ] **Task:** Implement `_format_amount_display()`
  - **Method Signature:**
    ```python
    def _format_amount_display(self, amount_str: str) -> str:
    ```
  - **Formatting Rules:**
    - Input: "0" → Output: "$0.00"
    - Input: "25" → Output: "$25.00"
    - Input: "25.5" → Output: "$25.50"
    - Input: "25.50" → Output: "$25.50"
    - Input: "1000" → Output: "$1000.00"

### 3.4 Implement Callback Handlers
- [ ] **Task:** Implement `start_donation_input()`
  - **Triggered By:** User clicks [💝 Donate] button in closed channel
  - **Callback Pattern:** `donate_start_{open_channel_id}`
  - **Actions:**
    1. Answer callback query
    2. Parse open_channel_id from callback_data
    3. Validate channel exists (security check)
    4. Initialize user context:
       ```python
       context.user_data["donation_open_channel_id"] = open_channel_id
       context.user_data["donation_amount_building"] = "0"
       context.user_data["donation_started_at"] = time.time()
       ```
    5. Edit message to show keypad
  - **Logging:**
    ```python
    self.logger.info(f"💝 User {user_id} started donation for channel {open_channel_id}")
    ```

- [ ] **Task:** Implement `handle_keypad_input()`
  - **Triggered By:** User presses any keypad button
  - **Callback Pattern:** `donate_(digit|backspace|clear|confirm|cancel|noop)`
  - **Router Logic:**
    ```python
    if callback_data.startswith("donate_digit_"):
        await self._handle_digit_press(update, context)
    elif callback_data == "donate_backspace":
        await self._handle_backspace(update, context)
    elif callback_data == "donate_clear":
        await self._handle_clear(update, context)
    elif callback_data == "donate_confirm":
        await self._handle_confirm(update, context)
    elif callback_data == "donate_cancel":
        await self._handle_cancel(update, context)
    elif callback_data == "donate_noop":
        await query.answer()  # No action
    ```

### 3.5 Implement Input Validation
- [ ] **Task:** Implement `_handle_digit_press()`
  - **Method Signature:**
    ```python
    async def _handle_digit_press(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
    ```
  - **Validation Rules:**
    1. **Replace leading zero:** "0" + "5" → "5"
    2. **Single decimal:** "2.5" + "." → REJECT (show alert)
    3. **Max 2 decimal places:** "2.55" + "0" → REJECT (show alert)
    4. **Max 4 digits before decimal:** "9999" + "9" → REJECT (show alert)
    5. **Valid sequences:** "2" → "2.5" → "2.50" → "2.50" ✅
  - **Error Messages:**
    ```python
    "⚠️ Only one decimal point allowed"
    "⚠️ Maximum 2 decimal places"
    "⚠️ Maximum amount: $9999.99"
    ```
  - **Show Alert:** `await query.answer("message", show_alert=True)`

- [ ] **Task:** Implement `_handle_backspace()`
  - **Logic:**
    ```python
    current = context.user_data["donation_amount_building"]
    new_amount = current[:-1] if len(current) > 1 else "0"
    context.user_data["donation_amount_building"] = new_amount
    ```
  - **Update Keyboard:** Show new amount

- [ ] **Task:** Implement `_handle_clear()`
  - **Logic:**
    ```python
    context.user_data["donation_amount_building"] = "0"
    ```
  - **Update Keyboard:** Reset to $0.00

- [ ] **Task:** Implement `_handle_confirm()`
  - **Validation:**
    1. Parse amount: `float(amount_str)`
    2. Check min: `>= 1.00`
    3. Check max: `<= 9999.99`
    4. Check format: No more than 2 decimals
  - **Success Actions:**
    ```python
    context.user_data["donation_amount"] = amount_float
    context.user_data["is_donation"] = True
    await query.edit_message_text(
        f"✅ <b>Donation Confirmed</b>\n\n"
        f"Amount: <b>${amount_float:.2f}</b>\n\n"
        f"Preparing payment gateway...",
        parse_mode="HTML"
    )
    # Proceed to payment gateway
    await self._trigger_payment_gateway(update, context)
    ```
  - **Error Actions:**
    ```python
    await query.answer("⚠️ Minimum donation: $1.00", show_alert=True)
    await query.answer("⚠️ Maximum donation: $9999.99", show_alert=True)
    await query.answer("❌ Invalid amount format", show_alert=True)
    ```

- [ ] **Task:** Implement `_handle_cancel()`
  - **Actions:**
    ```python
    await query.edit_message_text("❌ Donation cancelled.")
    # Clear context
    context.user_data.pop("donation_amount_building", None)
    context.user_data.pop("donation_open_channel_id", None)
    context.user_data.pop("donation_started_at", None)
    ```
  - **Logging:**
    ```python
    self.logger.info(f"🚫 User {user_id} cancelled donation")
    ```

### 3.6 Implement Payment Gateway Trigger
- [ ] **Task:** Implement `_trigger_payment_gateway()`
  - **Method Signature:**
    ```python
    async def _trigger_payment_gateway(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
    ```
  - **Integration Point:** Calls existing payment gateway module
  - **Data to Pass:**
    ```python
    {
        "amount": context.user_data["donation_amount"],
        "open_channel_id": context.user_data["donation_open_channel_id"],
        "user_id": update.effective_user.id,
        "is_donation": True
    }
    ```
  - **Note:** This will be completed in Phase 4 (integration with existing gateway)

### 3.7 Testing
- [ ] **Task:** Create unit tests
  - **File:** `TelePay10-26/tests/test_donation_input_handler.py`
  - **Test Cases:**
    - Keypad layout generation
    - Digit validation (all rules)
    - Amount formatting
    - Confirm validation (min/max)
    - Cancel cleanup
    - Callback data parsing

- [ ] **Task:** Integration testing
  - **Test Flow:**
    1. Click donate button in test channel
    2. Keypad appears with $0.00
    3. Press: 2 → 5 → . → 5 → 0
    4. Display updates to $25.50
    5. Click Confirm
    6. Validation passes
    7. Payment gateway trigger called
  - **Test Edge Cases:**
    - Multiple decimal attempts
    - Max amount exceeded
    - Backspace on single digit
    - Cancel mid-input

### 3.8 Documentation
- [ ] **Task:** Add comprehensive docstrings
  - **Each Method:** Purpose, args, returns, raises, example

- [ ] **Task:** Update DECISIONS.md
  - **Entry:**
    ```
    [2025-11-11] Module: Created donation_input_handler.py
    - Inline numeric keypad for custom amount input
    - Replaces ForceReply (doesn't work in channels)
    - Real-time validation with user-friendly error messages
    - Maintains separation: input handling separate from payment processing
    - Extensive validation constants prevent invalid amounts
    ```

---

## Phase 4: Payment Gateway Integration
**Estimated Time:** 2 hours
**Status:** ⬜ Not Started
**Module:** MODIFY - `start_np_gateway.py`

### 4.1 Review Existing Payment Gateway
- [ ] **Task:** Analyze current implementation
  - **File:** `TelePay10-26/start_np_gateway.py`
  - **Key Methods:**
    - `start_payment_flow()` - Entry point
    - Invoice creation logic
    - Order ID format
  - **Current Support:** Already handles donations (order_id format)

### 4.2 Enhance Gateway for Donations
- [ ] **Task:** Add donation detection
  - **Location:** `start_payment_flow()` method
  - **Check Context:**
    ```python
    is_donation = context.user_data.get("is_donation", False)
    donation_amount = context.user_data.get("donation_amount")
    ```
  - **Conditional Logic:**
    ```python
    if is_donation and donation_amount:
        order_description = "Donation"
        # Use donation amount instead of subscription price
    else:
        order_description = "Subscription"
        # Existing subscription logic
    ```

- [ ] **Task:** Update order_id format validation
  - **Current Format:** `PGP-{user_id}|{open_channel_id}`
  - **Ensure:** Works for both donations and subscriptions
  - **Validation:** No changes needed (format already supports both)

- [ ] **Task:** Modify invoice payload
  - **Location:** Invoice creation section
  - **Change:**
    ```python
    invoice_payload = {
        "price_amount": amount,  # Could be donation or subscription
        "price_currency": "USD",
        "order_id": order_id,
        "order_description": order_description,  # ← New: "Donation" vs "Subscription"
        "success_url": success_url,
        "ipn_callback_url": self.ipn_callback_url,
        "is_fixed_rate": False,
        "is_fee_paid_by_user": False
    }
    ```

### 4.3 Create Payment Gateway Adapter
- [ ] **Task:** Create adapter method in `donation_input_handler.py`
  - **Method Name:** `_trigger_payment_gateway()`
  - **Purpose:** Bridge between donation handler and payment gateway
  - **Implementation:**
    ```python
    async def _trigger_payment_gateway(self, update, context):
        # Import gateway
        from start_np_gateway import NowPaymentsGateway

        # Get donation data
        amount = context.user_data["donation_amount"]
        open_channel_id = context.user_data["donation_open_channel_id"]
        user_id = update.effective_user.id

        # Create order_id
        order_id = f"PGP-{user_id}|{open_channel_id}"

        # Initialize gateway
        gateway = NowPaymentsGateway(
            api_key=context.bot_data.get("nowpayments_api_key"),
            ipn_callback_url=context.bot_data.get("ipn_callback_url")
        )

        # Create invoice
        invoice_url = await gateway.create_invoice(
            amount=amount,
            order_id=order_id,
            order_description="Donation"
        )

        # Send payment button to user
        if invoice_url:
            await self._send_payment_button(update, context, invoice_url, amount)
        else:
            await self._handle_payment_creation_failure(update, context)
    ```

- [ ] **Task:** Implement `_send_payment_button()`
  - **Method Signature:**
    ```python
    async def _send_payment_button(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        invoice_url: str,
        amount: float
    ) -> None:
    ```
  - **Button Creation:**
    ```python
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    from telegram.web import WebAppInfo

    reply_markup = ReplyKeyboardMarkup.from_button(
        KeyboardButton(
            text="💰 Complete Payment",
            web_app=WebAppInfo(url=invoice_url)
        )
    )
    ```
  - **Message:**
    ```python
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=f"💝 <b>Complete Your ${amount:.2f} Donation</b>\n\n"
             f"Click below to proceed to the payment gateway.\n\n"
             f"You can pay with various cryptocurrencies.",
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    ```

- [ ] **Task:** Implement `_handle_payment_creation_failure()`
  - **Method Signature:**
    ```python
    async def _handle_payment_creation_failure(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
    ```
  - **Actions:**
    ```python
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="❌ <b>Payment Gateway Error</b>\n\n"
             "We encountered an error creating your payment invoice. "
             "Please try again later or contact support.",
        parse_mode="HTML"
    )
    self.logger.error(f"❌ Failed to create invoice for user {user_id}")
    ```

### 4.4 Webhook Compatibility Check
- [ ] **Task:** Verify webhook handles donations
  - **File:** `np-webhook-10-26/app.py`
  - **Check:** Order ID parsing logic
  - **Current Code (lines ~218-267):**
    ```python
    order_id = payment_data.get("order_id")  # "PGP-123|{open_channel_id}"
    parts = order_id.split("|")
    user_id = parts[0].replace("PGP-", "")
    open_channel_id = parts[1]
    ```
  - **Verify:** This already works for donations ✅
  - **No Changes Needed:** Webhook logic is agnostic to donation vs subscription

- [ ] **Task:** Add donation-specific logging to webhook
  - **Enhancement:**
    ```python
    order_description = payment_data.get("order_description", "Unknown")
    if order_description == "Donation":
        logger.info(f"💝 Processing donation payment for channel {open_channel_id}")
    else:
        logger.info(f"🎫 Processing subscription payment for channel {open_channel_id}")
    ```

### 4.5 Testing
- [ ] **Task:** Create integration test
  - **File:** `TelePay10-26/tests/test_donation_payment_integration.py`
  - **Test Flow:**
    1. Mock donation amount = $25.50
    2. Mock open_channel_id = "-1003268562225"
    3. Mock user_id = 123456789
    4. Call `_trigger_payment_gateway()`
    5. Verify invoice creation called with correct params
    6. Verify payment button sent to user
    7. Verify order_id format correct

- [ ] **Task:** Manual end-to-end test
  - **Steps:**
    1. Complete donation input via keypad
    2. Click Confirm
    3. Receive payment button in private chat
    4. Click payment button
    5. NOWPayments page loads correctly
    6. Complete mock payment (sandbox mode)
    7. Webhook receives IPN callback
    8. Verify donation logged correctly

### 4.6 Documentation
- [ ] **Task:** Update payment gateway docstrings
  - **File:** `start_np_gateway.py`
  - **Add:** Documentation for donation support

- [ ] **Task:** Update DECISIONS.md
  - **Entry:**
    ```
    [2025-11-11] Integration: Enhanced payment gateway for donations
    - Added order_description field to differentiate donations vs subscriptions
    - Created adapter method in donation_input_handler for clean separation
    - No changes to webhook required (order_id format already compatible)
    - Reused existing NOWPayments integration
    ```

---

## Phase 5: Main Application Integration
**Estimated Time:** 2 hours
**Status:** ⬜ Not Started
**Module:** MODIFY - `tpr10-26.py`

### 5.1 Import New Modules
- [ ] **Task:** Add imports to main bot file
  - **File:** `TelePay10-26/tpr10-26.py`
  - **Location:** Top of file with other imports
  - **Add:**
    ```python
    from closed_channel_manager import ClosedChannelManager
    from donation_input_handler import DonationKeypadHandler
    ```

### 5.2 Initialize New Handlers
- [ ] **Task:** Instantiate closed channel manager
  - **Location:** After database manager initialization
  - **Code:**
    ```python
    # Initialize Closed Channel Manager
    closed_channel_mgr = ClosedChannelManager(
        bot_token=BOT_TOKEN,
        db_manager=db_manager
    )
    logger.info("✅ Closed Channel Manager initialized")
    ```

- [ ] **Task:** Instantiate donation input handler
  - **Location:** After closed channel manager initialization
  - **Code:**
    ```python
    # Initialize Donation Input Handler
    donation_handler = DonationKeypadHandler(
        db_manager=db_manager
    )
    logger.info("✅ Donation Input Handler initialized")
    ```

### 5.3 Register Callback Query Handlers
- [ ] **Task:** Register donation start handler
  - **Location:** With other `application.add_handler()` calls
  - **Code:**
    ```python
    # Donation: Handle "Donate" button click in closed channels
    application.add_handler(CallbackQueryHandler(
        donation_handler.start_donation_input,
        pattern=r"^donate_start_"
    ))
    logger.info("📝 Registered: donate_start handler")
    ```

- [ ] **Task:** Register keypad input handler
  - **Location:** After donate_start handler
  - **Code:**
    ```python
    # Donation: Handle numeric keypad button presses
    application.add_handler(CallbackQueryHandler(
        donation_handler.handle_keypad_input,
        pattern=r"^donate_(digit|backspace|clear|confirm|cancel|noop)"
    ))
    logger.info("📝 Registered: donate_keypad handler")
    ```

- [ ] **Task:** Verify handler order
  - **Critical:** More specific patterns should be registered BEFORE general patterns
  - **Order:**
    1. `donate_start_` (most specific)
    2. `donate_(digit|backspace|...)` (specific)
    3. General callback handlers (least specific)

### 5.4 Add Donation Message Broadcast
- [ ] **Task:** Create broadcast command/function
  - **Option A:** Manual command
    ```python
    async def broadcast_donations_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to send donation messages to all closed channels"""
        # Check if user is admin (implement admin check)
        if not await is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin only command")
            return

        await update.message.reply_text("📨 Broadcasting donation messages...")

        result = await closed_channel_mgr.send_donation_message_to_closed_channels()

        await update.message.reply_text(
            f"✅ Broadcast complete\n\n"
            f"Total channels: {result['total_channels']}\n"
            f"Successful: {result['successful']}\n"
            f"Failed: {result['failed']}"
        )

    # Register command
    application.add_handler(CommandHandler("broadcast_donations", broadcast_donations_command))
    ```

  - **Option B:** Automatic on startup
    ```python
    async def post_init(application):
        """Run after bot starts"""
        logger.info("🚀 Running post-initialization tasks...")

        # Send donation messages to closed channels
        result = await closed_channel_mgr.send_donation_message_to_closed_channels()
        logger.info(f"📨 Donation broadcast: {result['successful']}/{result['total_channels']} successful")

    # Register post_init
    application.post_init = post_init
    ```

  - **Recommendation:** Start with Option A (manual command), switch to Option B after testing

### 5.5 Add Admin Command for Testing
- [ ] **Task:** Create test donation flow command
  - **Purpose:** Admins can test donation flow without going through channel
  - **Code:**
    ```python
    async def test_donation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to test donation input handler"""
        if not await is_admin(update.effective_user.id):
            return

        # Simulate donate button click
        # Create mock callback query
        # Trigger donation_handler.start_donation_input()

        await update.message.reply_text("🧪 Testing donation flow...")

    application.add_handler(CommandHandler("test_donation", test_donation_command))
    ```

### 5.6 Configuration & Environment
- [ ] **Task:** Verify all required environment variables
  - **Required:**
    - `BOT_TOKEN` - Telegram bot token
    - `NOWPAYMENTS_API_KEY` - NOWPayments API key
    - `IPN_CALLBACK_URL` - Webhook URL for payment notifications
    - Database connection variables
  - **Action:** Add validation on startup

- [ ] **Task:** Add bot_data storage
  - **Purpose:** Share config across handlers
  - **Code:**
    ```python
    # Store in bot_data for access by handlers
    application.bot_data["nowpayments_api_key"] = NOWPAYMENTS_API_KEY
    application.bot_data["ipn_callback_url"] = IPN_CALLBACK_URL
    application.bot_data["db_manager"] = db_manager
    ```

### 5.7 Testing
- [ ] **Task:** Test handler registration
  - **Verify:** No duplicate handler errors
  - **Check:** Handler patterns don't conflict
  - **Test:** Bot starts without errors

- [ ] **Task:** Test broadcast command
  - **Action:** Run `/broadcast_donations` as admin
  - **Verify:** Messages sent to closed channels
  - **Check:** Logs show success/failure counts

- [ ] **Task:** Test donation flow end-to-end
  - **Steps:**
    1. Start bot
    2. Broadcast donation messages
    3. Click donate in closed channel
    4. Complete keypad input
    5. Confirm payment
    6. Verify payment button received

### 5.8 Documentation
- [ ] **Task:** Update main bot docstring
  - **File:** `tpr10-26.py`
  - **Add:** Section on donation features

- [ ] **Task:** Update DECISIONS.md
  - **Entry:**
    ```
    [2025-11-11] Integration: Connected donation modules to main bot
    - Registered callback handlers for donate_start and donate_keypad patterns
    - Added broadcast_donations command for admin control
    - Handler order optimized for specificity
    - Bot_data used to share config across modules
    ```

---

## Phase 6: Broadcast Manager Cleanup
**Estimated Time:** 0.5 hours
**Status:** ⬜ Not Started
**Module:** MODIFY - `broadcast_manager.py`

### 6.1 Remove Donation Button from Open Channel
- [ ] **Task:** Comment out or remove donation button code
  - **File:** `TelePay10-26/broadcast_manager.py`
  - **Lines:** 69-72
  - **Current Code:**
    ```python
    # Add donation button
    donation_token = f"{base_hash}_DONATE"
    donation_url = f"https://t.me/{self.bot_username}?start={donation_token}"
    buttons_cfg.append({"text": "💝 Donate", "url": donation_url})
    ```
  - **Change To:**
    ```python
    # REMOVED: Donation button migrated to closed channels
    # See: closed_channel_manager.py for new donation implementation
    # See: DONATION_REWORK.md for architecture details
    # donation_token = f"{base_hash}_DONATE"
    # donation_url = f"https://t.me/{self.bot_username}?start={donation_token}"
    # buttons_cfg.append({"text": "💝 Donate", "url": donation_url})
    ```

- [ ] **Task:** Update docstring
  - **Location:** `broadcast_hash_links()` method
  - **Add Note:**
    ```python
    """
    Broadcast subscription links to open channels.

    Note: Donation buttons are no longer included in open channel broadcasts.
    Donations are now handled in closed channels. See closed_channel_manager.py.
    """
    ```

### 6.2 Clean Up Old Donation Handler (if exists)
- [ ] **Task:** Check for old donation handling code
  - **Files to Check:**
    - `input_handlers.py` - Old text-based donation input
    - `menu_handlers.py` - Old donation button handling
  - **Action:**
    - Comment out old donation code
    - Add deprecation notice
    - Keep for reference (don't delete yet)

- [ ] **Task:** Update `input_handlers.py` if needed
  - **Check:** Is there old donation input code?
  - **Lines:** ~153-238 (from our earlier read)
  - **Action:**
    - Leave old code for now (may have other dependencies)
    - Add comment: "# NOTE: Donation flow now in donation_input_handler.py"

### 6.3 Testing
- [ ] **Task:** Verify open channel messages
  - **Action:** Run `broadcast_hash_links()`
  - **Verify:** Donation button no longer appears
  - **Check:** Only subscription tier buttons show

- [ ] **Task:** Verify no broken references
  - **Search:** `grep -r "DONATE" TelePay10-26/`
  - **Check:** No unexpected references to old donation token

### 6.4 Documentation
- [ ] **Task:** Update DECISIONS.md
  - **Entry:**
    ```
    [2025-11-11] Cleanup: Removed donation button from open channels
    - Donation button removed from broadcast_manager.py (lines 69-72)
    - Old code commented out (not deleted) for reference
    - Open channels now show only subscription tiers
    - Donations exclusively in closed channels via new system
    ```

---

## Phase 7: Testing & Validation
**Estimated Time:** 3 hours
**Status:** ⬜ Not Started

### 7.1 Unit Testing
- [ ] **Task:** Run all unit tests
  - **Command:**
    ```bash
    cd TelePay10-26
    python3 -m pytest tests/ -v
    ```
  - **Expected:** All tests pass
  - **Files to Test:**
    - `test_database_donations.py`
    - `test_closed_channel_manager.py`
    - `test_donation_input_handler.py`
    - `test_donation_payment_integration.py`

### 7.2 Integration Testing
- [ ] **Task:** Test complete donation flow
  - **Test Case 1: Happy Path**
    - Step 1: User subscribes to paid channel
    - Step 2: User joins closed channel
    - Step 3: Bot sends donation message (manual broadcast)
    - Step 4: User clicks [💝 Donate]
    - Step 5: Keypad appears with $0.00
    - Step 6: User enters 25.50 via keypad
    - Step 7: User clicks Confirm
    - Step 8: Payment button sent to private chat
    - Step 9: User clicks payment button
    - Step 10: NOWPayments page loads
    - Step 11: Complete test payment (sandbox)
    - Step 12: Webhook receives IPN
    - Step 13: Donation logged in database
    - **Expected:** ✅ All steps succeed

  - **Test Case 2: Validation Errors**
    - Enter $0.50 → REJECT (min $1.00)
    - Enter $10000 → REJECT (max $9999.99)
    - Enter 25.555 → REJECT (max 2 decimals)
    - Enter multiple decimals → REJECT
    - **Expected:** ✅ All validations work

  - **Test Case 3: Cancel Flow**
    - Start donation
    - Enter partial amount (e.g., "2")
    - Click Cancel
    - Verify context cleared
    - **Expected:** ✅ Clean cancellation

  - **Test Case 4: Bot Not Admin**
    - Attempt broadcast to channel where bot isn't admin
    - **Expected:** ✅ Error logged, other channels succeed

### 7.3 Load Testing (Optional)
- [ ] **Task:** Test concurrent users
  - **Scenario:** 10 users press keypad simultaneously
  - **Monitor:**
    - Message edit rate limits
    - Database connection pool
    - Bot responsiveness
  - **Tool:** Custom script or locust.io

### 7.4 Security Testing
- [ ] **Task:** Test callback data validation
  - **Test:** Send fake callback_data with invalid channel ID
  - **Expected:** ✅ Rejected with security log

- [ ] **Task:** Test amount manipulation
  - **Test:** Try to send malformed amounts to payment gateway
  - **Expected:** ✅ Server-side validation catches it

### 7.5 User Acceptance Testing
- [ ] **Task:** Get feedback from test users
  - **Participants:** 3-5 real users
  - **Feedback Areas:**
    - Is keypad intuitive?
    - Are error messages clear?
    - Is payment flow smooth?
    - Any confusion points?

### 7.6 Documentation
- [ ] **Task:** Document test results
  - **File:** Create `DONATION_TESTING_REPORT.md`
  - **Include:**
    - Test cases executed
    - Pass/fail results
    - Issues discovered
    - Performance metrics
    - User feedback summary

- [ ] **Task:** Update PROGRESS.md
  - **Entry:**
    ```
    [2025-11-11] ✅ Donation rework testing complete
    - Unit tests: X/X passing
    - Integration tests: X/X passing
    - Load testing: Passed (10 concurrent users)
    - Security testing: Passed (validation working)
    - UAT: Positive feedback from 5 test users
    ```

---

## Phase 8: Deployment
**Estimated Time:** 1 hour
**Status:** ⬜ Not Started

### 8.1 Pre-Deployment Checklist
- [ ] **Task:** Verify all tests pass
  - **Command:** `pytest tests/ -v`
  - **Status:** All green ✅

- [ ] **Task:** Verify bot is admin in ALL closed channels
  - **Query:**
    ```sql
    SELECT closed_channel_id, closed_channel_title
    FROM main_clients_database
    WHERE closed_channel_id IS NOT NULL
    ```
  - **Manual Check:** For each channel, verify bot has admin rights

- [ ] **Task:** Review deployment diff
  - **Command:** `git diff main`
  - **Check:**
    - No debug code left in
    - No hardcoded test values
    - All logs use proper emoji patterns
    - No sensitive data in code

- [ ] **Task:** Create deployment branch
  - **Command:**
    ```bash
    git checkout -b feature/donation-rework
    git add .
    git commit -m "feat: Migrate donations to closed channels with custom amounts"
    ```

### 8.2 Staging Deployment
- [ ] **Task:** Deploy to staging environment
  - **Command:**
    ```bash
    gcloud run deploy telepay-bot-staging \
      --source . \
      --region us-central1 \
      --allow-unauthenticated
    ```
  - **Verify:** Deployment succeeds

- [ ] **Task:** Run smoke tests in staging
  - **Tests:**
    - Bot starts without errors
    - Broadcast command works
    - Donation flow works end-to-end
    - Payment gateway integration works
  - **Duration:** 15 minutes

### 8.3 Production Deployment
- [ ] **Task:** Deploy to production
  - **Command:**
    ```bash
    gcloud run deploy telepay-bot \
      --source . \
      --region us-central1 \
      --allow-unauthenticated
    ```
  - **Verify:** Deployment succeeds

- [ ] **Task:** Monitor logs during deployment
  - **Command:**
    ```bash
    gcloud run services logs read telepay-bot \
      --region us-central1 \
      --tail
    ```
  - **Watch For:**
    - Initialization success logs
    - Handler registration logs
    - No error messages

### 8.4 Post-Deployment Verification
- [ ] **Task:** Verify bot is running
  - **Test:** Send `/start` command to bot
  - **Expected:** Bot responds normally

- [ ] **Task:** Broadcast donation messages
  - **Command:** Send `/broadcast_donations` (if using manual trigger)
  - **Verify:**
    - Messages appear in closed channels
    - Buttons work correctly
    - No errors in logs

- [ ] **Task:** Test full donation flow in production
  - **Action:** Complete one real test donation
  - **Verify:**
    - Keypad works
    - Payment gateway works
    - Webhook processes correctly
    - Payout logic executes

### 8.5 Rollback Plan (if needed)
- [ ] **Task:** If critical issues found, rollback
  - **Command:**
    ```bash
    gcloud run services update-traffic telepay-bot \
      --to-revisions=PREVIOUS_REVISION=100
    ```
  - **Then:** Investigate issues in staging

### 8.6 Documentation
- [ ] **Task:** Update PROGRESS.md
  - **Entry:**
    ```
    [2025-11-11] 🚀 Donation rework deployed to production
    - Closed channel donations live
    - Custom amount input via inline keypad
    - Successfully tested with real transaction
    - All closed channels receiving donation messages
    - Performance: Normal (no issues detected)
    ```

- [ ] **Task:** Document deployment
  - **File:** Create `DEPLOYMENT_LOG_DONATION_REWORK.md`
  - **Include:**
    - Deployment timestamp
    - Services deployed
    - Verification steps completed
    - Issues encountered (if any)
    - Rollback procedure (if needed)

---

## Phase 9: Monitoring & Optimization
**Estimated Time:** Ongoing (1 hour initial setup)
**Status:** ⬜ Not Started

### 9.1 Set Up Monitoring
- [ ] **Task:** Create GCP logging queries
  - **Query 1: Donation Initiations**
    ```
    resource.type="cloud_run_revision"
    textPayload=~"started donation for channel"
    ```
  - **Query 2: Donation Completions**
    ```
    resource.type="cloud_run_revision"
    textPayload=~"Donation confirmed"
    ```
  - **Query 3: Errors**
    ```
    resource.type="cloud_run_revision"
    severity="ERROR"
    textPayload=~"donation|keypad"
    ```
  - **Save:** As custom queries in GCP Console

- [ ] **Task:** Set up alerts
  - **Alert 1:** Error rate > 5% of donation attempts
  - **Alert 2:** Payment creation failure > 10%
  - **Alert 3:** Broadcast failures > 20% of channels

### 9.2 Track Metrics
- [ ] **Task:** Define KPIs
  - **Metric 1:** Donation conversion rate
    - Formula: (Donations completed) / (Donate button clicks)
    - Target: >70%
  - **Metric 2:** Average donation amount
    - Target: >$15.00
  - **Metric 3:** Donation adoption rate
    - Formula: (Users who donated) / (Total closed channel members)
    - Target: >10% within 30 days
  - **Metric 4:** Keypad completion rate
    - Formula: (Confirms clicked) / (Keypad opened)
    - Target: >80%

- [ ] **Task:** Create metrics dashboard
  - **Tool:** GCP Monitoring or custom dashboard
  - **Widgets:**
    - Donation count (last 7 days)
    - Average amount (last 7 days)
    - Conversion funnel visualization
    - Error rate chart

### 9.3 Performance Optimization (if needed)
- [ ] **Task:** Monitor message edit latency
  - **Metric:** Time from button press to keyboard update
  - **Target:** <500ms
  - **If slow:** Investigate:
    - Rate limiting
    - Database query performance
    - Network latency

- [ ] **Task:** Optimize database queries
  - **Check:** `fetch_all_closed_channels()` execution time
  - **If slow:** Add index on `closed_channel_id`

### 9.4 User Feedback Collection
- [ ] **Task:** Monitor user complaints
  - **Channels:**
    - Support messages to bot
    - Closed channel comments
    - Direct user feedback
  - **Track:** Common issues or confusion points

- [ ] **Task:** Iterate based on feedback
  - **Example Issues:**
    - "Keypad confusing" → Add instructions
    - "Amount limit too low" → Consider raising max
    - "Want to donate twice" → Implement cooldown or allow

### 9.5 Documentation
- [ ] **Task:** Create monitoring runbook
  - **File:** `DONATION_MONITORING_RUNBOOK.md`
  - **Include:**
    - How to access logs
    - Key metrics to watch
    - Alert response procedures
    - Common issues & solutions

- [ ] **Task:** Final PROGRESS.md update
  - **Entry:**
    ```
    [2025-11-11] 📊 Donation monitoring established
    - GCP logging queries saved
    - Alerts configured for error thresholds
    - KPIs defined and tracked
    - Metrics dashboard created
    - Performance: Keypad latency <300ms ✅
    ```

---

## Completion Criteria

### Definition of Done
- [ ] All code files created/modified as specified
- [ ] All unit tests passing (100% pass rate)
- [ ] All integration tests passing
- [ ] Deployed to production without errors
- [ ] First real donation completed successfully end-to-end
- [ ] Monitoring and alerts active
- [ ] Documentation complete:
  - [ ] PROGRESS.md updated
  - [ ] DECISIONS.md updated
  - [ ] BUGS.md updated (if any bugs found)
  - [ ] All new files have docstrings
  - [ ] README updated (if exists)

### Sign-Off Checklist
- [ ] **Code Review:** All code reviewed for quality, security, style
- [ ] **Testing:** All test phases completed successfully
- [ ] **Deployment:** Production deployment verified
- [ ] **Monitoring:** Dashboards and alerts operational
- [ ] **Documentation:** All documentation complete and accurate
- [ ] **Stakeholder Approval:** Feature accepted by product owner
- [ ] **User Feedback:** Initial feedback collected and positive

---

## Rollback & Contingency Plans

### When to Rollback
1. **Critical:** Bot completely non-functional
2. **Critical:** Payment gateway failing >50% of attempts
3. **High:** Donation flow broken for all users
4. **High:** Security vulnerability discovered

### Rollback Procedure
```bash
# Step 1: Rollback Cloud Run deployment
gcloud run services update-traffic telepay-bot \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region us-central1

# Step 2: Verify rollback
gcloud run revisions list \
  --service=telepay-bot \
  --region=us-central1

# Step 3: Check bot functionality
# Send /start command to bot

# Step 4: Document rollback
# Update BUGS.md with issue details
# Update PROGRESS.md with rollback event

# Step 5: Debug in staging
# Fix issues in feature branch
# Re-test thoroughly
# Re-deploy when ready
```

### Partial Rollback
If only donation feature needs to be disabled:
```python
# In tpr10-26.py, comment out:
# application.add_handler(CallbackQueryHandler(donation_handler.start_donation_input))
# application.add_handler(CallbackQueryHandler(donation_handler.handle_keypad_input))

# Redeploy
gcloud run deploy telepay-bot --source . --region us-central1
```

---

## Notes & Reminders

### Code Style
- Follow existing emoji patterns in logs
- Use type hints for all function parameters
- Keep functions under 50 lines when possible
- Add comprehensive docstrings
- Use descriptive variable names

### Security
- Validate all callback_data on server
- Never trust client-side input
- Log all donation amounts for audit
- Verify bot permissions before posting
- Protect against SQL injection (use parameterized queries)

### Performance
- Minimize database queries in hot paths
- Cache channel lists when appropriate
- Use async/await consistently
- Handle Telegram rate limits gracefully

### Testing
- Test both happy path and error cases
- Include edge cases (empty input, max values, etc.)
- Test with real Telegram channels (staging)
- Mock external APIs (NOWPayments) in unit tests

---

## Quick Reference: File Changes Summary

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `database.py` | MODIFY | +50 | Add closed channel queries |
| `closed_channel_manager.py` | CREATE | ~250 | Manage closed channel donations |
| `donation_input_handler.py` | CREATE | ~450 | Handle keypad input & validation |
| `start_np_gateway.py` | MODIFY | +20 | Support donation order type |
| `tpr10-26.py` | MODIFY | +30 | Register handlers & initialize |
| `broadcast_manager.py` | MODIFY | -4 | Remove donate button from open |
| `tests/test_*.py` | CREATE | ~400 | Unit & integration tests |

**Total Lines Added:** ~1,200
**Total New Files:** 5
**Total Modified Files:** 4

---

## Support & Resources

### Documentation References
- **Architecture:** `DONATION_REWORK.md`
- **Telegram Bot API:** https://core.telegram.org/bots/api
- **python-telegram-bot:** https://docs.python-telegram-bot.org/
- **NOWPayments:** https://documenter.getpostman.com/view/7907941/2s93JusNJt

### Key Contacts
- **Database:** Existing `database.py` has all needed methods
- **Payment Gateway:** `start_np_gateway.py` already handles donations
- **Webhook:** `np-webhook-10-26/app.py` already parses order_id correctly

### Common Issues & Solutions
1. **Bot not admin in channel:**
   - Solution: Manually add bot as admin with posting rights
2. **Callback data too long:**
   - Solution: Keep channel IDs short, use abbreviations
3. **Rate limiting on message edits:**
   - Solution: Implement debouncing or cooldown on rapid button presses
4. **Payment gateway errors:**
   - Solution: Check NOWPayments API key and IPN callback URL

---

**END OF CHECKLIST**

---

## Checklist Usage Instructions

1. **Before Starting:** Read entire checklist to understand scope
2. **During Implementation:** Check off items as completed
3. **Testing:** Don't skip test phases (they catch issues early)
4. **Documentation:** Update as you go (don't leave for end)
5. **Questions:** Refer back to `DONATION_REWORK.md` for details
6. **Blockers:** Document in BUGS.md immediately
7. **Progress:** Update PROGRESS.md after each phase

**Status Legend:**
- ⬜ Not Started
- 🔄 In Progress
- ✅ Completed
- ❌ Blocked
- ⚠️ Issues Found
