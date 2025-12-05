# GCDonationHandler Refactoring Architecture
## Detailed Migration Plan from TelePay10-26 Monolith to Independent Webhook Service

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Architecture Design
**Branch:** TelePay-REFACTOR
**Parent Document:** TELEPAY_REFACTORING_ARCHITECTURE.md

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Self-Contained Module Strategy](#self-contained-module-strategy)
5. [Detailed Service Structure](#detailed-service-structure)
6. [API Endpoints Specification](#api-endpoints-specification)
7. [Database Operations](#database-operations)
8. [Configuration Management](#configuration-management)
9. [Error Handling & Resilience](#error-handling--resilience)
10. [Deployment Strategy](#deployment-strategy)
11. [Testing Strategy](#testing-strategy)
12. [Migration Checklist](#migration-checklist)

---

## Executive Summary

### Purpose
**GCDonationHandler** is a Flask-based Cloud Run webhook service that handles all donation-related functionality for the TelePay system. This service provides an inline numeric keypad interface for users to enter custom donation amounts and integrates with the NowPayments gateway for payment processing.

### Key Responsibilities
1. ✅ **Donation Keypad Interface** - Inline calculator-style numeric input
2. ✅ **Amount Validation** - Min $4.99, Max $9999.99, 2 decimal places
3. ✅ **Payment Gateway Integration** - Create NowPayments invoices for donations
4. ✅ **Closed Channel Broadcast** - Send donation buttons to private channels
5. ✅ **Channel Validation** - Security checks for callback data
6. ✅ **Message Lifecycle** - Auto-delete temporary messages

### Architecture Principle
**Self-Contained Modules**: Unlike the shared module approach, this service contains ALL dependencies within its own codebase. Each module is fully independent and can evolve without affecting other services.

---

## Current State Analysis

### 🔍 Source Files to Migrate

#### Primary Source Files (TelePay10-26/)
```
donation_input_handler.py       # 654 lines - Keypad logic & validation
closed_channel_manager.py       # 230 lines - Broadcast donation messages
database.py                     # 719 lines - Database operations
config_manager.py               # 76 lines - Secret Manager integration
start_np_gateway.py             # 314 lines - Payment gateway integration
```

#### Current Functionality Breakdown

**1. DonationKeypadHandler Class** (`donation_input_handler.py`)
- ✅ `start_donation_input()` - Initialize keypad for donation entry
- ✅ `handle_keypad_input()` - Process button presses (digits, backspace, clear, confirm, cancel)
- ✅ `_create_donation_keypad()` - Generate inline keyboard markup
- ✅ `_format_amount_display()` - Format currency display
- ✅ `_handle_digit_press()` - Digit validation and state update
- ✅ `_handle_backspace()` - Delete last character
- ✅ `_handle_clear()` - Reset to $0.00
- ✅ `_handle_confirm()` - Validate final amount and trigger payment
- ✅ `_handle_cancel()` - Abort donation flow
- ✅ `_trigger_payment_gateway()` - Create NowPayments invoice
- ✅ `_schedule_message_deletion()` - Auto-delete temporary messages

**2. ClosedChannelManager Class** (`closed_channel_manager.py`)
- ✅ `send_donation_message_to_closed_channels()` - Broadcast to all closed channels
- ✅ `_create_donation_button()` - Generate inline keyboard with donate button
- ✅ `_format_donation_message()` - Format message with custom donation text

**3. Database Operations** (`database.py`)
- ✅ `channel_exists()` - Validate channel ID
- ✅ `get_channel_details_by_open_id()` - Fetch channel metadata
- ✅ `fetch_all_closed_channels()` - Get all closed channels for broadcast
- ✅ Database connection management via psycopg2

**4. Configuration** (`config_manager.py`)
- ✅ Telegram bot token from Secret Manager
- ✅ Database credentials from Secret Manager
- ✅ NowPayments API token from Secret Manager

**5. Payment Gateway** (`start_np_gateway.py`)
- ✅ `PaymentGatewayManager.create_payment_invoice()` - NowPayments API integration
- ✅ `PaymentGatewayManager.fetch_payment_provider_token()` - API key from Secret Manager
- ✅ `PaymentGatewayManager.fetch_ipn_callback_url()` - IPN callback URL from Secret Manager

### ⚠️ Current Limitations

1. **Tight Coupling**: Donation handler is embedded in monolithic bot, cannot scale independently
2. **State Management**: Uses `context.user_data` which doesn't work across multiple bot instances
3. **Resource Waste**: Bot must run 24/7 even if donations are infrequent
4. **Testing Challenges**: Cannot test donation flow without running entire bot
5. **Deployment Risk**: Any change requires full bot restart

---

## Target Architecture

### 🏗️ High-Level Service Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        User Interaction Flow                              │
└──────────────────────────────────────────────────────────────────────────┘

1. User clicks [💝 Donate] button in closed channel
   │
   ▼
2. Telegram sends callback_query to GCBotCommand webhook
   │
   ▼
3. GCBotCommand extracts callback_data and forwards to GCDonationHandler
   │
   ├─ POST /start-donation-input
   │  {
   │    "user_id": 6271402111,
   │    "chat_id": -1002345678901,
   │    "open_channel_id": "-1003268562225",
   │    "callback_query_id": "abc123"
   │  }
   │
   ▼
4. GCDonationHandler sends keypad message via Telegram Bot API
   │
   ▼
5. User enters amount via keypad (digits, backspace, clear)
   │
   ├─ POST /keypad-input (for each button press)
   │  {
   │    "user_id": 6271402111,
   │    "callback_data": "donate_digit_5",
   │    "message_id": 12345,
   │    "chat_id": -1002345678901
   │  }
   │
   ▼
6. User clicks [✅ Confirm & Pay]
   │
   ├─ POST /keypad-input
   │  {
   │    "user_id": 6271402111,
   │    "callback_data": "donate_confirm",
   │    "amount": "25.50"
   │  }
   │
   ▼
7. GCDonationHandler validates amount ($4.99 - $9999.99)
   │
   ▼
8. GCDonationHandler creates NowPayments invoice
   │
   ├─ POST https://api.nowpayments.io/v1/invoice
   │  {
   │    "price_amount": 25.50,
   │    "price_currency": "USD",
   │    "order_id": "PGP-6271402111|-1003268562225"
   │  }
   │
   ▼
9. GCDonationHandler sends payment button to user's private chat
   │
   ▼
10. User completes payment via NowPayments gateway
```

### 📋 Service Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GCDonationHandler Service                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Flask Application (Port 8080)                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                  │                                       │
│         ┌────────────────────────┼────────────────────────┐             │
│         │                        │                        │             │
│         ▼                        ▼                        ▼             │
│  ┌─────────────┐        ┌───────────────┐       ┌──────────────┐      │
│  │ /start-     │        │ /keypad-input │       │ /broadcast-  │      │
│  │  donation-  │        │               │       │  closed-     │      │
│  │  input      │        │               │       │  channels    │      │
│  └──────┬──────┘        └───────┬───────┘       └──────┬───────┘      │
│         │                       │                       │               │
│         └───────────────────────┼───────────────────────┘               │
│                                 │                                       │
│                    ┌────────────▼────────────┐                          │
│                    │  KeypadHandler Module   │                          │
│                    │  - State management     │                          │
│                    │  - Amount validation    │                          │
│                    │  - Keyboard generation  │                          │
│                    └────────────┬────────────┘                          │
│                                 │                                       │
│                    ┌────────────▼────────────┐                          │
│                    │ PaymentGateway Module   │                          │
│                    │ - NowPayments API       │                          │
│                    │ - Invoice creation      │                          │
│                    └────────────┬────────────┘                          │
│                                 │                                       │
│         ┌───────────────────────┼───────────────────────┐               │
│         │                       │                       │               │
│         ▼                       ▼                       ▼               │
│  ┌─────────────┐        ┌──────────────┐       ┌─────────────┐        │
│  │ Database    │        │ Config       │       │ Telegram    │        │
│  │ Manager     │        │ Manager      │       │ Client      │        │
│  │ (PostgreSQL)│        │ (Secrets)    │       │ (Bot API)   │        │
│  └─────────────┘        └──────────────┘       └─────────────┘        │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

External Dependencies:
├── PostgreSQL (telepaypsql) - Channel data, validation
├── Google Secret Manager - Credentials, API keys
├── Telegram Bot API - Message sending, keyboard rendering
└── NowPayments API - Invoice creation, payment processing
```

---

## Self-Contained Module Strategy

### 🎯 Why Self-Contained Modules?

**Decision**: Each service contains its own copies of all required modules instead of using shared libraries.

**Rationale**:
1. ✅ **Deployment Simplicity** - Single container image, no external dependencies
2. ✅ **Independent Evolution** - Each service can modify its modules without affecting others
3. ✅ **Reduced Coordination** - No need to version-sync shared libraries
4. ✅ **Clearer Ownership** - Each team/service owns its complete codebase
5. ✅ **Easier Debugging** - All code is in one place, no version conflicts

**Trade-offs**:
- ❌ Code duplication across services (acceptable trade-off for autonomy)
- ❌ Bug fixes must be applied to each service (mitigated by clear documentation)
- ✅ Services are completely independent (outweighs downsides)

### 📦 Module Organization

Each module is a **standalone Python file** with zero dependencies on other internal modules (only standard library and external packages).

```
GCDonationHandler-10-26/
├── service.py                      # Flask app (main entry point)
├── keypad_handler.py               # Donation keypad logic
├── payment_gateway_manager.py      # NowPayments integration
├── database_manager.py             # PostgreSQL operations
├── config_manager.py               # Secret Manager integration
├── telegram_client.py              # Telegram Bot API wrapper
├── broadcast_manager.py            # Closed channel broadcast logic
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container definition
└── .env.example                    # Environment variable template
```

**No imports between internal modules** - Each module is imported directly by `service.py`.

---

## Detailed Service Structure

### 📁 File-by-File Specification

#### 1. **service.py** - Flask Application Entry Point

```python
#!/usr/bin/env python
"""
GCDonationHandler - Flask Webhook Service
Handles donation keypad input, validation, and payment gateway integration.

Architecture: Flask application factory pattern with self-contained modules.
"""

from flask import Flask, request, jsonify, abort
import logging
from config_manager import ConfigManager
from database_manager import DatabaseManager
from keypad_handler import KeypadHandler
from telegram_client import TelegramClient
from broadcast_manager import BroadcastManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """
    Application factory for GCDonationHandler Flask app.

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)

    # Initialize configuration from Secret Manager
    logger.info("🔧 Initializing configuration...")
    config_manager = ConfigManager()
    config = config_manager.initialize_config()

    if not config['bot_token']:
        logger.error("❌ Failed to load bot token from Secret Manager")
        raise RuntimeError("Bot token not available")

    # Initialize database manager
    logger.info("🗄️ Initializing database connection...")
    db_manager = DatabaseManager(
        db_host=config['db_host'],
        db_port=config['db_port'],
        db_name=config['db_name'],
        db_user=config['db_user'],
        db_password=config['db_password']
    )

    # Initialize Telegram client
    logger.info("📱 Initializing Telegram client...")
    telegram_client = TelegramClient(bot_token=config['bot_token'])

    # Initialize keypad handler
    keypad_handler = KeypadHandler(
        db_manager=db_manager,
        telegram_client=telegram_client,
        payment_token=config['payment_token'],
        ipn_callback_url=config['ipn_callback_url']
    )

    # Initialize broadcast manager
    broadcast_manager = BroadcastManager(
        db_manager=db_manager,
        telegram_client=telegram_client
    )

    # Store in app context
    app.config.update(config)
    app.db_manager = db_manager
    app.telegram_client = telegram_client
    app.keypad_handler = keypad_handler
    app.broadcast_manager = broadcast_manager

    logger.info("✅ GCDonationHandler initialized successfully")

    # ==================== ROUTES ====================

    @app.route("/health", methods=["GET"])
    def health():
        """
        Health check endpoint for Cloud Run.

        Returns:
            JSON response with status
        """
        return jsonify({
            "status": "healthy",
            "service": "GCDonationHandler",
            "version": "1.0"
        }), 200

    @app.route("/start-donation-input", methods=["POST"])
    def start_donation_input():
        """
        Initialize donation keypad for user.

        Called by GCBotCommand when user clicks [💝 Donate] button.

        Request Body:
            {
                "user_id": 6271402111,
                "chat_id": -1002345678901,
                "open_channel_id": "-1003268562225",
                "callback_query_id": "abc123"
            }

        Returns:
            JSON response with success status
        """
        try:
            data = request.get_json()

            # Validate required fields
            required = ['user_id', 'chat_id', 'open_channel_id', 'callback_query_id']
            if not all(k in data for k in required):
                logger.warning(f"⚠️ Missing required fields in request: {data}")
                abort(400, "Missing required fields")

            user_id = data['user_id']
            chat_id = data['chat_id']
            open_channel_id = data['open_channel_id']
            callback_query_id = data['callback_query_id']

            logger.info(f"💝 Starting donation input for user {user_id}, channel {open_channel_id}")

            # Security validation: Check if channel exists
            if not app.db_manager.channel_exists(open_channel_id):
                logger.warning(f"⚠️ Invalid channel ID: {open_channel_id}")

                # Answer callback query with error
                app.telegram_client.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="❌ Invalid channel",
                    show_alert=True
                )

                return jsonify({
                    "success": False,
                    "error": "Invalid channel ID"
                }), 400

            # Initialize donation keypad
            result = app.keypad_handler.start_donation_input(
                user_id=user_id,
                chat_id=chat_id,
                open_channel_id=open_channel_id,
                callback_query_id=callback_query_id
            )

            if result['success']:
                logger.info(f"✅ Donation keypad sent to user {user_id}")
                return jsonify(result), 200
            else:
                logger.error(f"❌ Failed to send donation keypad: {result.get('error')}")
                return jsonify(result), 500

        except Exception as e:
            logger.error(f"❌ Error in start_donation_input: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route("/keypad-input", methods=["POST"])
    def keypad_input():
        """
        Process keypad button presses.

        Handles: digits (0-9), decimal (.), backspace, clear, confirm, cancel.

        Request Body:
            {
                "user_id": 6271402111,
                "callback_data": "donate_digit_5",
                "callback_query_id": "xyz789",
                "message_id": 12345,
                "chat_id": -1002345678901
            }

        Returns:
            JSON response with action result
        """
        try:
            data = request.get_json()

            # Validate required fields
            required = ['user_id', 'callback_data', 'callback_query_id']
            if not all(k in data for k in required):
                logger.warning(f"⚠️ Missing required fields in keypad request: {data}")
                abort(400, "Missing required fields")

            user_id = data['user_id']
            callback_data = data['callback_data']
            callback_query_id = data['callback_query_id']
            message_id = data.get('message_id')
            chat_id = data.get('chat_id')

            logger.info(f"🔢 Processing keypad input: user={user_id}, action={callback_data}")

            # Process keypad input
            result = app.keypad_handler.handle_keypad_input(
                user_id=user_id,
                callback_data=callback_data,
                callback_query_id=callback_query_id,
                message_id=message_id,
                chat_id=chat_id
            )

            return jsonify(result), 200

        except Exception as e:
            logger.error(f"❌ Error in keypad_input: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route("/broadcast-closed-channels", methods=["POST"])
    def broadcast_closed_channels():
        """
        Broadcast donation messages to all closed channels.

        This endpoint can be triggered manually or by Cloud Scheduler.

        Request Body (optional):
            {
                "force_resend": false
            }

        Returns:
            JSON response with broadcast summary
        """
        try:
            data = request.get_json() or {}
            force_resend = data.get('force_resend', False)

            logger.info(f"📢 Starting closed channel broadcast (force_resend={force_resend})")

            # Execute broadcast
            result = app.broadcast_manager.broadcast_to_closed_channels(
                force_resend=force_resend
            )

            logger.info(
                f"✅ Broadcast complete: {result['successful']}/{result['total_channels']} successful"
            )

            return jsonify(result), 200

        except Exception as e:
            logger.error(f"❌ Error in broadcast_closed_channels: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    return app


if __name__ == "__main__":
    # Create and run app
    app = create_app()

    # Cloud Run expects port 8080
    port = 8080
    logger.info(f"🚀 Starting GCDonationHandler on port {port}")

    app.run(host="0.0.0.0", port=port)
```

---

#### 2. **keypad_handler.py** - Donation Keypad Logic

**Self-Contained**: No internal imports, only external packages and standard library.

```python
#!/usr/bin/env python
"""
Keypad Handler Module
Manages donation amount input via inline numeric keypad.

Validation Rules:
- Minimum amount: $4.99
- Maximum amount: $9999.99
- Maximum 2 decimal places
- Maximum 4 digits before decimal point
- Single decimal point only
- No leading zeros (except "0.XX")
"""

import logging
import time
from typing import Dict, Any, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


class KeypadHandler:
    """
    Handles inline numeric keypad for donation amount input.

    This class provides a calculator-style interface for users to enter
    custom donation amounts, with real-time validation and user-friendly
    error messages.
    """

    # Validation constants
    MIN_AMOUNT = 4.99
    MAX_AMOUNT = 9999.99
    MAX_DECIMALS = 2
    MAX_DIGITS_BEFORE_DECIMAL = 4

    def __init__(self, db_manager, telegram_client, payment_token, ipn_callback_url):
        """
        Initialize the KeypadHandler.

        Args:
            db_manager: DatabaseManager instance for validation queries
            telegram_client: TelegramClient instance for sending messages
            payment_token: NowPayments API token
            ipn_callback_url: IPN callback URL for NowPayments
        """
        self.db_manager = db_manager
        self.telegram_client = telegram_client
        self.payment_token = payment_token
        self.ipn_callback_url = ipn_callback_url

        # In-memory state storage (keyed by user_id)
        # In production, consider using Redis for distributed state
        self.user_states = {}

    def start_donation_input(
        self,
        user_id: int,
        chat_id: int,
        open_channel_id: str,
        callback_query_id: str
    ) -> Dict[str, Any]:
        """
        Initialize donation keypad for user.

        Args:
            user_id: User's Telegram ID
            chat_id: Chat ID where keypad should be sent
            open_channel_id: Channel ID for payment routing
            callback_query_id: Callback query ID to answer

        Returns:
            Dictionary with success status and message_id
        """
        try:
            # Answer callback query
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text="💝 Opening donation keypad..."
            )

            # Initialize user state
            self.user_states[user_id] = {
                'amount_building': '0',
                'open_channel_id': open_channel_id,
                'started_at': time.time()
            }

            logger.info(f"💝 User {user_id} started donation for channel {open_channel_id}")

            # Create keypad message
            text = (
                "<b>💝 Enter Donation Amount</b>\n\n"
                "Use the keypad below to enter your donation amount in USD.\n"
                f"Range: ${self.MIN_AMOUNT:.2f} - ${self.MAX_AMOUNT:.2f}"
            )

            reply_markup = self._create_donation_keypad('0')

            # Send keypad message
            result = self.telegram_client.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

            if result.get('success'):
                message_id = result['message_id']

                # Store message_id in state for later editing
                self.user_states[user_id]['keypad_message_id'] = message_id
                self.user_states[user_id]['chat_id'] = chat_id

                logger.info(f"📋 Sent keypad message {message_id} to chat {chat_id}")

                return {
                    'success': True,
                    'message_id': message_id
                }
            else:
                logger.error(f"❌ Failed to send keypad message: {result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error')
                }

        except Exception as e:
            logger.error(f"❌ Error in start_donation_input: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def handle_keypad_input(
        self,
        user_id: int,
        callback_data: str,
        callback_query_id: str,
        message_id: Optional[int] = None,
        chat_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process keypad button press.

        Args:
            user_id: User's Telegram ID
            callback_data: Callback data from button press
            callback_query_id: Callback query ID to answer
            message_id: Message ID of keypad (for editing)
            chat_id: Chat ID (for message operations)

        Returns:
            Dictionary with success status and action taken
        """
        try:
            # Get user state
            if user_id not in self.user_states:
                logger.warning(f"⚠️ No state found for user {user_id}")
                self.telegram_client.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="❌ Session expired. Please start again.",
                    show_alert=True
                )
                return {
                    'success': False,
                    'error': 'Session expired'
                }

            state = self.user_states[user_id]
            current_amount = state['amount_building']

            # Route to appropriate handler based on callback_data
            if callback_data.startswith("donate_digit_"):
                return self._handle_digit_press(
                    user_id, callback_data, callback_query_id, current_amount
                )

            elif callback_data == "donate_backspace":
                return self._handle_backspace(
                    user_id, callback_query_id, current_amount
                )

            elif callback_data == "donate_clear":
                return self._handle_clear(user_id, callback_query_id)

            elif callback_data == "donate_confirm":
                return self._handle_confirm(user_id, callback_query_id, current_amount)

            elif callback_data == "donate_cancel":
                return self._handle_cancel(user_id, callback_query_id)

            elif callback_data == "donate_noop":
                # Display button, no action
                self.telegram_client.answer_callback_query(callback_query_id)
                return {'success': True, 'action': 'noop'}

            else:
                logger.warning(f"⚠️ Unknown callback_data: {callback_data}")
                self.telegram_client.answer_callback_query(
                    callback_query_id=callback_query_id,
                    text="❌ Unknown action",
                    show_alert=True
                )
                return {
                    'success': False,
                    'error': 'Unknown action'
                }

        except Exception as e:
            logger.error(f"❌ Error in handle_keypad_input: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _handle_digit_press(
        self,
        user_id: int,
        callback_data: str,
        callback_query_id: str,
        current_amount: str
    ) -> Dict[str, Any]:
        """
        Handle digit or decimal button press with validation.

        Validation Rules:
        1. Replace leading zero: "0" + "5" → "5"
        2. Single decimal: "2.5" + "." → REJECT
        3. Max 2 decimal places: "2.55" + "0" → REJECT
        4. Max 4 digits before decimal: "9999" + "9" → REJECT
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
                return {'success': False, 'error': 'Max decimals exceeded'}
            new_amount = current_amount + digit

        # Validation Rule 4: Max 4 digits before decimal
        elif digit != "." and len(current_amount) >= self.MAX_DIGITS_BEFORE_DECIMAL:
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text=f"⚠️ Maximum amount: ${self.MAX_AMOUNT:.2f}",
                show_alert=True
            )
            return {'success': False, 'error': 'Max amount exceeded'}

        else:
            new_amount = current_amount + digit

        # Update state
        self.user_states[user_id]['amount_building'] = new_amount

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Edit keyboard with updated amount
        state = self.user_states[user_id]
        message_id = state.get('keypad_message_id')
        chat_id = state.get('chat_id')

        if message_id and chat_id:
            self.telegram_client.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self._create_donation_keypad(new_amount)
            )

        return {
            'success': True,
            'action': 'digit_added',
            'new_amount': new_amount
        }

    def _handle_backspace(
        self,
        user_id: int,
        callback_query_id: str,
        current_amount: str
    ) -> Dict[str, Any]:
        """Handle backspace button - delete last character."""
        # Remove last character, reset to "0" if empty
        new_amount = current_amount[:-1] if len(current_amount) > 1 else "0"

        # Update state
        self.user_states[user_id]['amount_building'] = new_amount

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Edit keyboard
        state = self.user_states[user_id]
        message_id = state.get('keypad_message_id')
        chat_id = state.get('chat_id')

        if message_id and chat_id:
            self.telegram_client.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self._create_donation_keypad(new_amount)
            )

        return {
            'success': True,
            'action': 'backspace',
            'new_amount': new_amount
        }

    def _handle_clear(
        self,
        user_id: int,
        callback_query_id: str
    ) -> Dict[str, Any]:
        """Handle clear button - reset to $0.00."""
        # Update state
        self.user_states[user_id]['amount_building'] = "0"

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Edit keyboard
        state = self.user_states[user_id]
        message_id = state.get('keypad_message_id')
        chat_id = state.get('chat_id')

        if message_id and chat_id:
            self.telegram_client.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self._create_donation_keypad("0")
            )

        return {
            'success': True,
            'action': 'clear'
        }

    def _handle_confirm(
        self,
        user_id: int,
        callback_query_id: str,
        current_amount: str
    ) -> Dict[str, Any]:
        """
        Handle confirm button - validate amount and trigger payment gateway.

        Final Validations:
        - Amount must be parseable as float
        - Amount >= MIN_AMOUNT ($4.99)
        - Amount <= MAX_AMOUNT ($9999.99)
        """
        # Validation: Parse amount
        try:
            amount_float = float(current_amount)
        except ValueError:
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text="❌ Invalid amount format",
                show_alert=True
            )
            return {'success': False, 'error': 'Invalid amount format'}

        # Validation: Check minimum
        if amount_float < self.MIN_AMOUNT:
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text=f"⚠️ Minimum donation: ${self.MIN_AMOUNT:.2f}",
                show_alert=True
            )
            return {'success': False, 'error': 'Below minimum amount'}

        # Validation: Check maximum
        if amount_float > self.MAX_AMOUNT:
            self.telegram_client.answer_callback_query(
                callback_query_id=callback_query_id,
                text=f"⚠️ Maximum donation: ${self.MAX_AMOUNT:.2f}",
                show_alert=True
            )
            return {'success': False, 'error': 'Above maximum amount'}

        # Get state
        state = self.user_states[user_id]
        open_channel_id = state['open_channel_id']
        chat_id = state.get('chat_id')
        keypad_message_id = state.get('keypad_message_id')

        logger.info(f"✅ Donation confirmed: ${amount_float:.2f} for channel {open_channel_id} by user {user_id}")

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Delete keypad message
        if keypad_message_id and chat_id:
            self.telegram_client.delete_message(
                chat_id=chat_id,
                message_id=keypad_message_id
            )

        # Send confirmation message
        if chat_id:
            confirmation_text = (
                f"✅ <b>Donation Confirmed</b>\n"
                f"💰 Amount: <b>${amount_float:.2f}</b>\n"
                f"Preparing your payment gateway... Check your messages with @PayGatePrime_bot"
            )

            self.telegram_client.send_message(
                chat_id=chat_id,
                text=confirmation_text,
                parse_mode="HTML"
            )

        # Trigger payment gateway
        payment_result = self._trigger_payment_gateway(
            user_id=user_id,
            amount=amount_float,
            open_channel_id=open_channel_id
        )

        # Clean up state
        del self.user_states[user_id]

        return {
            'success': True,
            'action': 'confirmed',
            'amount': amount_float,
            'payment_result': payment_result
        }

    def _handle_cancel(
        self,
        user_id: int,
        callback_query_id: str
    ) -> Dict[str, Any]:
        """Handle cancel button - abort donation flow."""
        logger.info(f"🚫 User {user_id} cancelled donation")

        # Get state
        state = self.user_states.get(user_id, {})
        chat_id = state.get('chat_id')
        keypad_message_id = state.get('keypad_message_id')

        # Answer callback query
        self.telegram_client.answer_callback_query(callback_query_id)

        # Delete keypad message
        if keypad_message_id and chat_id:
            self.telegram_client.delete_message(
                chat_id=chat_id,
                message_id=keypad_message_id
            )

        # Send cancellation message
        if chat_id:
            self.telegram_client.send_message(
                chat_id=chat_id,
                text="❌ Donation cancelled.",
                parse_mode="HTML"
            )

        # Clean up state
        if user_id in self.user_states:
            del self.user_states[user_id]

        return {
            'success': True,
            'action': 'cancelled'
        }

    def _trigger_payment_gateway(
        self,
        user_id: int,
        amount: float,
        open_channel_id: str
    ) -> Dict[str, Any]:
        """
        Create NowPayments invoice and send payment button to user.

        Args:
            user_id: User's Telegram ID
            amount: Donation amount in USD
            open_channel_id: Channel ID for payment routing

        Returns:
            Dictionary with payment gateway result
        """
        try:
            # Import payment gateway manager
            from payment_gateway_manager import PaymentGatewayManager

            # Initialize gateway
            gateway = PaymentGatewayManager(
                payment_token=self.payment_token,
                ipn_callback_url=self.ipn_callback_url
            )

            # Create order_id
            order_id = f"PGP-{user_id}|{open_channel_id}"

            logger.info(f"💰 Creating payment invoice for ${amount:.2f} - order_id: {order_id}")

            # Create invoice
            invoice_result = gateway.create_payment_invoice(
                user_id=user_id,
                amount=amount,
                order_id=order_id
            )

            if invoice_result.get("success"):
                invoice_url = invoice_result["data"].get("invoice_url", "")

                if invoice_url:
                    logger.info(f"✅ Payment invoice created successfully for ${amount:.2f}")

                    # Fetch channel details for message formatting
                    channel_details = self.db_manager.get_channel_details_by_open_id(open_channel_id)

                    if channel_details:
                        closed_channel_title = channel_details["closed_channel_title"]
                        closed_channel_description = channel_details["closed_channel_description"]
                    else:
                        # Fallback if channel details not found
                        closed_channel_title = "Premium Channel"
                        closed_channel_description = "Exclusive content"
                        logger.warning(f"⚠️ Channel details not found for {open_channel_id}, using fallback")

                    # Send payment button to user
                    text = (
                        f"💝 <b>Click the button below to Complete Your ${amount:.2f} Donation</b> 💝\n\n"
                        f"🔒 <b>Private Channel:</b> {closed_channel_title}\n"
                        f"📝 <b>Channel Description:</b> {closed_channel_description}\n"
                        f"💰 <b>Price:</b> ${amount:.2f}"
                    )

                    # Send with Web App button
                    self.telegram_client.send_message_with_webapp_button(
                        chat_id=user_id,
                        text=text,
                        button_text="💰 Complete Donation Payment",
                        webapp_url=invoice_url
                    )

                    logger.info(f"📨 Payment button sent to user {user_id}")

                    return {
                        'success': True,
                        'invoice_url': invoice_url
                    }
                else:
                    raise ValueError("No invoice URL in response")

            else:
                # Invoice creation failed
                error_msg = invoice_result.get("error", "Unknown error")
                status_code = invoice_result.get("status_code", "N/A")

                logger.error(f"❌ Invoice creation failed: {error_msg} (status: {status_code})")

                # Send error message to user
                error_text = (
                    f"❌ <b>Payment Gateway Error</b>\n\n"
                    f"We encountered an error creating your payment invoice.\n\n"
                    f"Error: {error_msg}\n"
                    f"Status: {status_code}\n\n"
                    f"Please try again later or contact support."
                )

                self.telegram_client.send_message(
                    chat_id=user_id,
                    text=error_text,
                    parse_mode="HTML"
                )

                return {
                    'success': False,
                    'error': error_msg
                }

        except Exception as e:
            logger.error(f"❌ Failed to create payment invoice: {e}")

            # Send error message to user
            error_text = (
                "❌ <b>Payment Gateway Error</b>\n\n"
                "We encountered an unexpected error creating your payment invoice. "
                "Please try again later or contact support."
            )

            self.telegram_client.send_message(
                chat_id=user_id,
                text=error_text,
                parse_mode="HTML"
            )

            return {
                'success': False,
                'error': str(e)
            }

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
```

---

#### 3. **payment_gateway_manager.py** - NowPayments Integration

**Self-Contained**: No internal imports.

```python
#!/usr/bin/env python
"""
Payment Gateway Manager Module
Handles NowPayments API integration for invoice creation.

This module is responsible for:
- Creating payment invoices via NowPayments API
- Managing API authentication and error handling
- Formatting invoice payloads with IPN callbacks
"""

import logging
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PaymentGatewayManager:
    """
    Manages NowPayments API integration for payment invoice creation.
    """

    def __init__(self, payment_token: str, ipn_callback_url: Optional[str] = None):
        """
        Initialize the PaymentGatewayManager.

        Args:
            payment_token: NowPayments API token
            ipn_callback_url: IPN callback URL for payment notifications
        """
        self.payment_token = payment_token
        self.ipn_callback_url = ipn_callback_url
        self.api_url = "https://api.nowpayments.io/v1/invoice"

    def create_payment_invoice(
        self,
        user_id: int,
        amount: float,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Create a payment invoice with NowPayments.

        Args:
            user_id: User's Telegram ID
            amount: Payment amount in USD
            order_id: Unique order identifier (format: "PGP-{user_id}|{channel_id}")

        Returns:
            Dictionary containing API response:
            {
                "success": true,
                "status_code": 200,
                "data": {
                    "id": "12345",
                    "invoice_url": "https://nowpayments.io/payment/...",
                    "order_id": "PGP-6271402111|-1003268562225"
                }
            }
        """
        if not self.payment_token:
            logger.error("❌ Payment provider token not available")
            return {
                "success": False,
                "error": "Payment provider token not available"
            }

        # Warn if IPN callback URL not configured
        if not self.ipn_callback_url:
            logger.warning("⚠️ IPN callback URL not configured - payment_id won't be captured")

        # Build invoice payload
        invoice_payload = {
            "price_amount": amount,
            "price_currency": "USD",
            "order_id": order_id,
            "order_description": f"Donation - User {user_id}",
            "success_url": "https://storage.googleapis.com/paygateprime-static/payment-processing.html",
            "ipn_callback_url": self.ipn_callback_url,  # IPN endpoint for payment_id capture
            "is_fixed_rate": False,
            "is_fee_paid_by_user": False
        }

        headers = {
            "x-api-key": self.payment_token,
            "Content-Type": "application/json",
        }

        try:
            # Make API request (synchronous - use httpx instead of async)
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    self.api_url,
                    headers=headers,
                    json=invoice_payload,
                )

                if resp.status_code == 200:
                    response_data = resp.json()
                    invoice_id = response_data.get('id')

                    # Log invoice creation
                    logger.info(f"📋 Created invoice_id: {invoice_id}")
                    logger.info(f"📋 Order ID: {order_id}")
                    if self.ipn_callback_url:
                        logger.info(f"📋 IPN will be sent to: {self.ipn_callback_url}")
                    else:
                        logger.warning(f"⚠️ IPN callback URL not set - payment_id won't be captured")

                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "data": response_data
                    }
                else:
                    logger.error(f"❌ NowPayments API error: {resp.status_code} - {resp.text}")
                    return {
                        "success": False,
                        "status_code": resp.status_code,
                        "error": resp.text
                    }

        except httpx.TimeoutException as e:
            logger.error(f"❌ Request timeout: {e}")
            return {
                "success": False,
                "error": f"Request timeout: {str(e)}"
            }

        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }
```

---

#### 4. **database_manager.py** - PostgreSQL Operations

**Self-Contained**: No internal imports.

```python
#!/usr/bin/env python
"""
Database Manager Module
Handles all PostgreSQL database operations for donation handler.

This module is responsible for:
- Database connection management
- Channel validation queries
- Channel details retrieval
- Closed channel listing for broadcasts
"""

import logging
import psycopg2
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages PostgreSQL database connections and queries.
    """

    def __init__(self, db_host: str, db_port: int, db_name: str, db_user: str, db_password: str):
        """
        Initialize the DatabaseManager.

        Args:
            db_host: Database host (Cloud SQL connection string)
            db_port: Database port (typically 5432)
            db_name: Database name
            db_user: Database user
            db_password: Database password
        """
        self.host = db_host
        self.port = db_port
        self.dbname = db_name
        self.user = db_user
        self.password = db_password

        # Validate credentials
        if not self.password:
            raise RuntimeError("Database password not available. Cannot initialize DatabaseManager.")
        if not self.host or not self.dbname or not self.user:
            raise RuntimeError("Critical database configuration missing.")

    def get_connection(self):
        """
        Create and return a database connection.

        Returns:
            psycopg2 connection object

        Raises:
            Exception if connection fails
        """
        try:
            return psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            raise

    def channel_exists(self, open_channel_id: str) -> bool:
        """
        Validate if a channel exists in the database.
        Used for security validation of callback data.

        Args:
            open_channel_id: The open channel ID to validate

        Returns:
            True if channel exists, False otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM main_clients_database WHERE open_channel_id = %s LIMIT 1",
                (str(open_channel_id),)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()

            exists = result is not None
            if exists:
                logger.info(f"✅ Channel validation: {open_channel_id} exists")
            else:
                logger.warning(f"⚠️ Channel validation: {open_channel_id} does not exist")

            return exists

        except Exception as e:
            logger.error(f"❌ Error validating channel: {e}")
            return False

    def get_channel_details_by_open_id(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch channel details by open_channel_id for donation message formatting.

        This method is used exclusively by the donation workflow to display
        channel information to users.

        Args:
            open_channel_id: The open channel ID to fetch details for

        Returns:
            Dict containing channel details or None if not found:
            {
                "closed_channel_title": str,
                "closed_channel_description": str
            }
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    closed_channel_title,
                    closed_channel_description
                FROM main_clients_database
                WHERE open_channel_id = %s
                LIMIT 1
            """, (str(open_channel_id),))
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                channel_details = {
                    "closed_channel_title": result[0] if result[0] else "Premium Channel",
                    "closed_channel_description": result[1] if result[1] else "Exclusive content"
                }
                logger.info(f"✅ Fetched channel details for {open_channel_id}")
                return channel_details
            else:
                logger.warning(f"⚠️ No channel details found for {open_channel_id}")
                return None

        except Exception as e:
            logger.error(f"❌ Error fetching channel details: {e}")
            return None

    def fetch_all_closed_channels(self) -> List[Dict[str, Any]]:
        """
        Fetch all closed channels with their associated metadata for donation messages.

        Returns:
            List of dicts containing:
            - closed_channel_id: The closed channel ID
            - open_channel_id: The associated open channel ID
            - closed_channel_title: Title of the closed channel
            - closed_channel_description: Description of the closed channel
            - closed_channel_donation_message: Custom donation message for the channel
            - payout_strategy: "instant" or "threshold"
            - payout_threshold_usd: Threshold amount for batch payouts
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
                    closed_channel_donation_message,
                    payout_strategy,
                    payout_threshold_usd
                FROM main_clients_database
                WHERE closed_channel_id IS NOT NULL
                    AND closed_channel_id != ''
                ORDER BY closed_channel_id
            """)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            result = []
            for row in rows:
                result.append({
                    "closed_channel_id": row[0],
                    "open_channel_id": row[1],
                    "closed_channel_title": row[2] if row[2] else "Premium Channel",
                    "closed_channel_description": row[3] if row[3] else "exclusive content",
                    "closed_channel_donation_message": row[4] if row[4] else "Consider supporting our channel!",
                    "payout_strategy": row[5] if row[5] else "instant",
                    "payout_threshold_usd": row[6] if row[6] else 0.0
                })

            logger.info(f"📋 Fetched {len(result)} closed channels for donation messages")
            return result

        except Exception as e:
            logger.error(f"❌ Error fetching closed channels: {e}")
            return []
```

---

#### 5. **config_manager.py** - Configuration & Secrets Management

**Self-Contained**: No internal imports.

```python
#!/usr/bin/env python
"""
Configuration Manager Module
Handles fetching configuration from Google Secret Manager.

This module is responsible for:
- Fetching Telegram bot token
- Fetching database credentials
- Fetching NowPayments API credentials
- Managing environment variables
"""

import os
import logging
from google.cloud import secretmanager
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configuration loading from Google Secret Manager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.secret_client = secretmanager.SecretManagerServiceClient()

    def fetch_secret(self, secret_env_var: str) -> Optional[str]:
        """
        Generic method to fetch a secret from Secret Manager.

        Args:
            secret_env_var: Environment variable name containing secret path

        Returns:
            Secret value as string, or None if error
        """
        try:
            secret_path = os.getenv(secret_env_var)
            if not secret_path:
                logger.error(f"❌ Environment variable {secret_env_var} is not set")
                return None

            response = self.secret_client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")

            logger.info(f"✅ Successfully fetched secret from {secret_env_var}")
            return secret_value

        except Exception as e:
            logger.error(f"❌ Error fetching secret from {secret_env_var}: {e}")
            return None

    def fetch_telegram_token(self) -> Optional[str]:
        """
        Fetch the Telegram bot token from Secret Manager.

        Environment Variable: TELEGRAM_BOT_SECRET_NAME

        Returns:
            Telegram bot token or None if error
        """
        return self.fetch_secret("TELEGRAM_BOT_SECRET_NAME")

    def fetch_database_host(self) -> Optional[str]:
        """
        Fetch database host from Secret Manager.

        Environment Variable: DATABASE_HOST_SECRET

        Returns:
            Database host (Cloud SQL connection string) or None if error
        """
        return self.fetch_secret("DATABASE_HOST_SECRET")

    def fetch_database_name(self) -> Optional[str]:
        """
        Fetch database name from Secret Manager.

        Environment Variable: DATABASE_NAME_SECRET

        Returns:
            Database name or None if error
        """
        return self.fetch_secret("DATABASE_NAME_SECRET")

    def fetch_database_user(self) -> Optional[str]:
        """
        Fetch database user from Secret Manager.

        Environment Variable: DATABASE_USER_SECRET

        Returns:
            Database user or None if error
        """
        return self.fetch_secret("DATABASE_USER_SECRET")

    def fetch_database_password(self) -> Optional[str]:
        """
        Fetch database password from Secret Manager.

        Environment Variable: DATABASE_PASSWORD_SECRET

        Returns:
            Database password or None if error
        """
        return self.fetch_secret("DATABASE_PASSWORD_SECRET")

    def fetch_payment_provider_token(self) -> Optional[str]:
        """
        Fetch NowPayments API token from Secret Manager.

        Environment Variable: PAYMENT_PROVIDER_SECRET_NAME

        Returns:
            NowPayments API token or None if error
        """
        return self.fetch_secret("PAYMENT_PROVIDER_SECRET_NAME")

    def fetch_ipn_callback_url(self) -> Optional[str]:
        """
        Fetch IPN callback URL from Secret Manager.

        Environment Variable: NOWPAYMENTS_IPN_CALLBACK_URL

        Returns:
            IPN callback URL or None if error
        """
        ipn_url = self.fetch_secret("NOWPAYMENTS_IPN_CALLBACK_URL")
        if ipn_url:
            logger.info("✅ IPN callback URL configured")
        else:
            logger.warning("⚠️ IPN callback URL not configured - payment_id capture will not work")
        return ipn_url

    def initialize_config(self) -> Dict[str, Any]:
        """
        Initialize and return all configuration values.

        Returns:
            Dictionary with all configuration values:
            {
                'bot_token': str,
                'db_host': str,
                'db_port': int,
                'db_name': str,
                'db_user': str,
                'db_password': str,
                'payment_token': str,
                'ipn_callback_url': str
            }

        Raises:
            RuntimeError if critical configuration is missing
        """
        logger.info("🔧 Loading configuration from Secret Manager...")

        config = {
            'bot_token': self.fetch_telegram_token(),
            'db_host': self.fetch_database_host(),
            'db_port': 5432,  # Standard PostgreSQL port
            'db_name': self.fetch_database_name(),
            'db_user': self.fetch_database_user(),
            'db_password': self.fetch_database_password(),
            'payment_token': self.fetch_payment_provider_token(),
            'ipn_callback_url': self.fetch_ipn_callback_url()
        }

        # Validate critical configuration
        critical_fields = ['bot_token', 'db_host', 'db_name', 'db_user', 'db_password', 'payment_token']
        missing_fields = [field for field in critical_fields if not config[field]]

        if missing_fields:
            error_msg = f"❌ Critical configuration missing: {', '.join(missing_fields)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.info("✅ Configuration loaded successfully")
        return config
```

---

#### 6. **telegram_client.py** - Telegram Bot API Wrapper

**Self-Contained**: No internal imports.

```python
#!/usr/bin/env python
"""
Telegram Client Module
Wrapper for Telegram Bot API operations.

This module is responsible for:
- Sending messages
- Editing messages
- Deleting messages
- Answering callback queries
- Creating inline keyboards
"""

import logging
from typing import Dict, Any, Optional
from telegram import Bot, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class TelegramClient:
    """
    Wrapper for Telegram Bot API operations.
    """

    def __init__(self, bot_token: str):
        """
        Initialize the TelegramClient.

        Args:
            bot_token: Telegram bot token
        """
        self.bot = Bot(token=bot_token)

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a text message to a chat.

        Args:
            chat_id: Chat ID to send message to
            text: Message text
            reply_markup: Optional inline keyboard markup
            parse_mode: Optional parse mode (HTML, Markdown)

        Returns:
            Dictionary with success status and message_id
        """
        try:
            # Use Bot.send_message (synchronous)
            import asyncio
            message = asyncio.run(self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            ))

            logger.info(f"📨 Sent message {message.message_id} to chat {chat_id}")

            return {
                'success': True,
                'message_id': message.message_id
            }

        except TelegramError as e:
            logger.error(f"❌ Telegram API error sending message: {e}")
            return {
                'success': False,
                'error': str(e)
            }

        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def send_message_with_webapp_button(
        self,
        chat_id: int,
        text: str,
        button_text: str,
        webapp_url: str
    ) -> Dict[str, Any]:
        """
        Send a message with a Web App button (for payment gateway).

        Args:
            chat_id: Chat ID to send message to
            text: Message text
            button_text: Button label
            webapp_url: Web App URL (NowPayments invoice URL)

        Returns:
            Dictionary with success status
        """
        try:
            reply_markup = ReplyKeyboardMarkup.from_button(
                KeyboardButton(
                    text=button_text,
                    web_app=WebAppInfo(url=webapp_url),
                )
            )

            import asyncio
            message = asyncio.run(self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            ))

            logger.info(f"📨 Sent Web App button message {message.message_id} to chat {chat_id}")

            return {
                'success': True,
                'message_id': message.message_id
            }

        except TelegramError as e:
            logger.error(f"❌ Telegram API error sending Web App button: {e}")
            return {
                'success': False,
                'error': str(e)
            }

        except Exception as e:
            logger.error(f"❌ Error sending Web App button: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        reply_markup: InlineKeyboardMarkup
    ) -> Dict[str, Any]:
        """
        Edit an existing message's inline keyboard.

        Args:
            chat_id: Chat ID where message is located
            message_id: Message ID to edit
            reply_markup: New inline keyboard markup

        Returns:
            Dictionary with success status
        """
        try:
            import asyncio
            asyncio.run(self.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup
            ))

            logger.info(f"✏️ Edited message {message_id} keyboard in chat {chat_id}")

            return {'success': True}

        except TelegramError as e:
            logger.error(f"❌ Telegram API error editing keyboard: {e}")
            return {
                'success': False,
                'error': str(e)
            }

        except Exception as e:
            logger.error(f"❌ Error editing keyboard: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def delete_message(
        self,
        chat_id: int,
        message_id: int
    ) -> Dict[str, Any]:
        """
        Delete a message.

        Args:
            chat_id: Chat ID where message is located
            message_id: Message ID to delete

        Returns:
            Dictionary with success status
        """
        try:
            import asyncio
            asyncio.run(self.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            ))

            logger.info(f"🗑️ Deleted message {message_id} from chat {chat_id}")

            return {'success': True}

        except TelegramError as e:
            logger.warning(f"⚠️ Telegram API error deleting message: {e}")
            return {
                'success': False,
                'error': str(e)
            }

        except Exception as e:
            logger.error(f"❌ Error deleting message: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> Dict[str, Any]:
        """
        Answer a callback query.

        Args:
            callback_query_id: Callback query ID
            text: Optional text to display to user
            show_alert: If True, show as alert instead of notification

        Returns:
            Dictionary with success status
        """
        try:
            import asyncio
            asyncio.run(self.bot.answer_callback_query(
                callback_query_id=callback_query_id,
                text=text,
                show_alert=show_alert
            ))

            if text:
                logger.info(f"✅ Answered callback query: {text}")

            return {'success': True}

        except TelegramError as e:
            logger.error(f"❌ Telegram API error answering callback: {e}")
            return {
                'success': False,
                'error': str(e)
            }

        except Exception as e:
            logger.error(f"❌ Error answering callback: {e}")
            return {
                'success': False,
                'error': str(e)
            }
```

---

#### 7. **broadcast_manager.py** - Closed Channel Broadcast Logic

**Self-Contained**: No internal imports.

```python
#!/usr/bin/env python
"""
Broadcast Manager Module
Handles broadcasting donation messages to closed channels.

This module is responsible for:
- Sending donation buttons to all closed channels
- Creating inline keyboards with donation buttons
- Formatting donation messages
- Error handling for channels where bot lacks permissions
"""

import logging
import time
from typing import Dict, Any, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError, Forbidden, BadRequest

logger = logging.getLogger(__name__)


class BroadcastManager:
    """
    Manages donation message broadcasts to closed channels.
    """

    def __init__(self, db_manager, telegram_client):
        """
        Initialize the BroadcastManager.

        Args:
            db_manager: DatabaseManager instance
            telegram_client: TelegramClient instance
        """
        self.db_manager = db_manager
        self.telegram_client = telegram_client

    def broadcast_to_closed_channels(
        self,
        force_resend: bool = False
    ) -> Dict[str, Any]:
        """
        Send donation button to all closed channels where bot is admin.

        Args:
            force_resend: If True, sends even if message was recently sent

        Returns:
            Dictionary with summary statistics:
            {
                "total_channels": 5,
                "successful": 4,
                "failed": 1,
                "errors": [{"channel_id": "-100XXX", "error": "Bot not admin"}]
            }
        """
        # Fetch all closed channel IDs from database
        closed_channels = self.db_manager.fetch_all_closed_channels()

        total_channels = len(closed_channels)
        successful = 0
        failed = 0
        errors = []

        logger.info(f"📨 Starting donation message broadcast to {total_channels} closed channels")

        for channel_info in closed_channels:
            closed_channel_id = channel_info["closed_channel_id"]
            open_channel_id = channel_info["open_channel_id"]
            donation_message = channel_info.get(
                "closed_channel_donation_message",
                "Consider supporting our channel!"
            )

            try:
                # Create inline keyboard with single donate button
                reply_markup = self._create_donation_button(open_channel_id)

                # Format message content
                message_text = self._format_donation_message(donation_message)

                # Send to closed channel
                result = self.telegram_client.send_message(
                    chat_id=closed_channel_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )

                if result.get('success'):
                    successful += 1
                    logger.info(f"📨 Sent donation message to {closed_channel_id}")
                else:
                    failed += 1
                    error_msg = result.get('error', 'Unknown error')
                    errors.append({"channel_id": closed_channel_id, "error": error_msg})
                    logger.warning(f"⚠️ Failed to send to {closed_channel_id}: {error_msg}")

            except Exception as e:
                # Unexpected errors (database, network, etc.)
                failed += 1
                error_msg = f"Unexpected error: {str(e)}"
                errors.append({"channel_id": closed_channel_id, "error": error_msg})
                logger.error(f"❌ {error_msg}: {closed_channel_id}")

            # Small delay to avoid rate limiting
            time.sleep(0.1)

        # Log summary
        logger.info(
            f"✅ Donation broadcast complete: {successful}/{total_channels} successful, "
            f"{failed} failed"
        )

        return {
            "total_channels": total_channels,
            "successful": successful,
            "failed": failed,
            "errors": errors
        }

    def _create_donation_button(self, open_channel_id: str) -> InlineKeyboardMarkup:
        """
        Create inline keyboard with single donation button.

        The callback_data includes the open_channel_id so the bot can
        later identify which channel the donation is for when the user
        clicks the button.

        Args:
            open_channel_id: The open channel ID to encode in callback data

        Returns:
            InlineKeyboardMarkup with single donation button
        """
        # Validate callback_data length (Telegram limit: 64 bytes)
        callback_data = f"donate_start_{open_channel_id}"
        if len(callback_data.encode('utf-8')) > 64:
            logger.warning(
                f"⚠️ Callback data too long ({len(callback_data)} chars) for channel {open_channel_id}"
            )
            # Truncate if needed (should not happen with standard channel IDs)
            callback_data = callback_data[:64]

        button = InlineKeyboardButton(
            text="💝 Donate to Support This Channel",
            callback_data=callback_data
        )

        # Single button, single row layout
        keyboard = [[button]]
        return InlineKeyboardMarkup(keyboard)

    def _format_donation_message(
        self,
        donation_message: str
    ) -> str:
        """
        Format the donation message text with custom message.

        Args:
            donation_message: Custom donation message from the database

        Returns:
            Formatted HTML message text
        """
        message_text = (
            f"Enjoying the content? Consider making a donation.\n<b>{donation_message}</b>"
        )

        # Validate message length (Telegram limit: 4096 characters)
        if len(message_text) > 4096:
            logger.warning(
                f"⚠️ Message too long ({len(message_text)} chars), truncating"
            )
            message_text = message_text[:4090] + "..."

        return message_text
```

---

#### 8. **requirements.txt** - Python Dependencies

```txt
# Flask web framework
Flask==3.0.0

# Telegram Bot API
python-telegram-bot==21.0

# HTTP client for NowPayments API
httpx==0.25.0

# PostgreSQL adapter
psycopg2-binary==2.9.9

# Google Cloud Secret Manager
google-cloud-secret-manager==2.16.4

# Cloud SQL Connector (optional, for Cloud SQL connections)
cloud-sql-python-connector[pg8000]==1.4.3

# Logging
python-json-logger==2.0.7
```

---

#### 9. **Dockerfile** - Container Definition

```dockerfile
# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PostgreSQL
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY service.py .
COPY keypad_handler.py .
COPY payment_gateway_manager.py .
COPY database_manager.py .
COPY config_manager.py .
COPY telegram_client.py .
COPY broadcast_manager.py .

# Expose port 8080 (Cloud Run standard)
EXPOSE 8080

# Set environment variable for Flask
ENV FLASK_APP=service.py

# Run the Flask application
CMD ["python", "service.py"]
```

---

#### 10. **.env.example** - Environment Variable Template

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_SECRET_NAME="projects/telepay-459221/secrets/telegram-bot-token/versions/latest"

# Database Configuration
DATABASE_HOST_SECRET="projects/telepay-459221/secrets/database-host/versions/latest"
DATABASE_NAME_SECRET="projects/telepay-459221/secrets/database-name/versions/latest"
DATABASE_USER_SECRET="projects/telepay-459221/secrets/database-user/versions/latest"
DATABASE_PASSWORD_SECRET="projects/telepay-459221/secrets/database-password/versions/latest"

# Payment Provider Configuration
PAYMENT_PROVIDER_SECRET_NAME="projects/telepay-459221/secrets/nowpayments-api-key/versions/latest"
NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/nowpayments-ipn-url/versions/latest"

# Service Configuration
PORT=8080
```

---

## API Endpoints Specification

### 🆕 IMPORTANT: HTTP Call Chain Clarification

**GCDonationHandler does NOT register a Telegram webhook.**

All Telegram updates (messages, callback_queries) are received by **GCBotCommand first**, which then proxies donation-related callbacks to GCDonationHandler via HTTP POST requests.

#### Webhook Registration Architecture

```
❌ INCORRECT ASSUMPTION:
    Telegram → GCDonationHandler /webhook  (GCDonationHandler does NOT have a Telegram webhook)

✅ ACTUAL FLOW:
    Telegram → GCBotCommand /webhook  (ONLY GCBotCommand registers webhook)
        → GCBotCommand routes callback to GCDonationHandler
            → GCDonationHandler /start-donation-input (HTTP POST from GCBotCommand)
            → GCDonationHandler /keypad-input (HTTP POST from GCBotCommand)
```

#### Who Calls What?

| Caller | Endpoint | Purpose |
|--------|----------|---------|
| **GCBotCommand** | `POST /start-donation-input` | User clicked "💝 Donate" button in broadcast |
| **GCBotCommand** | `POST /keypad-input` | User pressed keypad button (digit, backspace, etc.) |
| **GCDonationHandler** | `POST /create-invoice` (GCPaymentGateway) | User confirmed amount, create invoice |
| **GCBroadcastService** | `POST /broadcast-closed-channels` | Trigger broadcast to all closed channels |

#### Complete Donation Flow from User Perspective

```
1. User sees "💝 Donate $X.XX or more" in closed channel broadcast
2. User clicks "💝 Donate" button
3. Telegram sends callback_query to GCBotCommand (only service with registered webhook)
4. GCBotCommand: callback_handler.py identifies callback_data.startswith("donate_start_")
5. GCBotCommand → HTTP POST to GCDonationHandler /start-donation-input
6. GCDonationHandler sends numeric keypad to user via Telegram Bot API
7. User presses digit button (e.g., "2", "5", ".", "0", "0")
8. Telegram sends callback_query to GCBotCommand for EACH button press
9. GCBotCommand → HTTP POST to GCDonationHandler /keypad-input for EACH press
10. GCDonationHandler updates keypad display after each input
11. User presses "✅ Confirm" button
12. Telegram sends callback_query to GCBotCommand
13. GCBotCommand → HTTP POST to GCDonationHandler /keypad-input
14. GCDonationHandler validates amount ($4.99 minimum)
15. GCDonationHandler → HTTP POST to GCPaymentGateway /create-invoice
16. GCPaymentGateway → NowPayments API to create invoice
17. GCDonationHandler sends payment button with invoice_url to user
18. User clicks payment button → redirected to NowPayments payment page
```

#### Security Note

⚠️ **Issue #5:** HTTP calls between GCBotCommand and GCDonationHandler are currently **NOT authenticated**.

🔧 **Fix Required:** Implement JWT-based inter-service authentication (see MAIN_REFACTOR_REVIEW_TELEPAY_CHECKLIST.md Task 4.1-4.4)

**Recommended Implementation:**
- GCBotCommand generates JWT token with claims: `{source_service: 'gcbotcommand', target_service: 'gcdonationhandler'}`
- GCDonationHandler verifies JWT signature and checks target_service matches itself
- Reject requests without valid JWT (return 401 Unauthorized)

#### State Management Note

⚠️ **Issue #3:** GCDonationHandler currently uses **in-memory state** (`user_states` dict) to track keypad amounts.

This creates a problem:
- If GCDonationHandler scales to 2+ instances (horizontal scaling)
- User presses digit "2" → goes to instance A
- User presses digit "5" → goes to instance B (doesn't know about "2")
- User sees "$5.00" instead of "$25.00"

🔧 **Fix Required:** Migrate to database-backed state using `donation_keypad_state` table (see MAIN_REFACTOR_REVIEW_TELEPAY_CHECKLIST.md Task 3.1-3.4)

---

### 🌐 Complete API Reference

#### 1. Health Check Endpoint

**Endpoint:** `GET /health`

**Purpose:** Health check for Cloud Run monitoring

**Response:**
```json
{
  "status": "healthy",
  "service": "GCDonationHandler",
  "version": "1.0"
}
```

**Status Codes:**
- `200 OK` - Service is healthy

---

#### 2. Start Donation Input

**Endpoint:** `POST /start-donation-input`

**Purpose:** Initialize donation keypad for user

**Request Body:**
```json
{
  "user_id": 6271402111,
  "chat_id": -1002345678901,
  "open_channel_id": "-1003268562225",
  "callback_query_id": "abc123xyz789"
}
```

**Request Fields:**
- `user_id` (integer, required) - User's Telegram ID
- `chat_id` (integer, required) - Chat ID where keypad should be sent
- `open_channel_id` (string, required) - Channel ID for payment routing
- `callback_query_id` (string, required) - Callback query ID to answer

**Response (Success):**
```json
{
  "success": true,
  "message_id": 12345
}
```

**Response (Error - Invalid Channel):**
```json
{
  "success": false,
  "error": "Invalid channel ID"
}
```

**Status Codes:**
- `200 OK` - Keypad sent successfully
- `400 Bad Request` - Missing required fields or invalid channel
- `500 Internal Server Error` - Server error

---

#### 3. Keypad Input Processing

**Endpoint:** `POST /keypad-input`

**Purpose:** Process keypad button presses (digits, backspace, clear, confirm, cancel)

**Request Body:**
```json
{
  "user_id": 6271402111,
  "callback_data": "donate_digit_5",
  "callback_query_id": "xyz789abc123",
  "message_id": 12345,
  "chat_id": -1002345678901
}
```

**Request Fields:**
- `user_id` (integer, required) - User's Telegram ID
- `callback_data` (string, required) - Button callback data
- `callback_query_id` (string, required) - Callback query ID to answer
- `message_id` (integer, optional) - Message ID of keypad
- `chat_id` (integer, optional) - Chat ID

**Callback Data Patterns:**
- `donate_digit_0` through `donate_digit_9` - Digit buttons
- `donate_digit_.` - Decimal point button
- `donate_backspace` - Delete last character
- `donate_clear` - Reset to $0.00
- `donate_confirm` - Validate and proceed to payment
- `donate_cancel` - Cancel donation flow
- `donate_noop` - Display button (no action)

**Response (Digit Added):**
```json
{
  "success": true,
  "action": "digit_added",
  "new_amount": "25.5"
}
```

**Response (Confirmed):**
```json
{
  "success": true,
  "action": "confirmed",
  "amount": 25.50,
  "payment_result": {
    "success": true,
    "invoice_url": "https://nowpayments.io/payment/abc123"
  }
}
```

**Response (Cancelled):**
```json
{
  "success": true,
  "action": "cancelled"
}
```

**Response (Error - Below Minimum):**
```json
{
  "success": false,
  "error": "Below minimum amount"
}
```

**Status Codes:**
- `200 OK` - Action processed successfully
- `400 Bad Request` - Missing required fields or validation error
- `500 Internal Server Error` - Server error

---

#### 4. Broadcast Closed Channels

**Endpoint:** `POST /broadcast-closed-channels`

**Purpose:** Broadcast donation messages to all closed channels

**Request Body (Optional):**
```json
{
  "force_resend": false
}
```

**Request Fields:**
- `force_resend` (boolean, optional) - Force resend even if recently sent

**Response:**
```json
{
  "total_channels": 10,
  "successful": 9,
  "failed": 1,
  "errors": [
    {
      "channel_id": "-1002345678999",
      "error": "Bot not admin or kicked from channel"
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Broadcast completed (check success/failed counts)
- `500 Internal Server Error` - Server error

---

## Database Operations

### 🗄️ Database Schema (No Changes Required)

The existing PostgreSQL schema in `telepaypsql` remains **unchanged**:

```sql
-- Main channel configuration table
CREATE TABLE main_clients_database (
    open_channel_id TEXT PRIMARY KEY,
    open_channel_title TEXT,
    open_channel_description TEXT,
    closed_channel_id TEXT,
    closed_channel_title TEXT,
    closed_channel_description TEXT,
    closed_channel_donation_message TEXT,
    sub_1_price DECIMAL(10,2),
    sub_1_time INTEGER,
    sub_2_price DECIMAL(10,2),
    sub_2_time INTEGER,
    sub_3_price DECIMAL(10,2),
    sub_3_time INTEGER,
    client_wallet_address TEXT,
    client_payout_currency TEXT,
    client_payout_network TEXT,
    payout_strategy TEXT DEFAULT 'instant',
    payout_threshold_usd DECIMAL(10,2) DEFAULT 0.00,
    notification_status BOOLEAN DEFAULT FALSE,
    notification_id BIGINT
);
```

### 📊 Database Queries Used by GCDonationHandler

**1. Channel Validation:**
```sql
SELECT 1 FROM main_clients_database
WHERE open_channel_id = %s
LIMIT 1;
```

**2. Channel Details Retrieval:**
```sql
SELECT closed_channel_title, closed_channel_description
FROM main_clients_database
WHERE open_channel_id = %s
LIMIT 1;
```

**3. Closed Channels Listing:**
```sql
SELECT
    closed_channel_id,
    open_channel_id,
    closed_channel_title,
    closed_channel_description,
    closed_channel_donation_message,
    payout_strategy,
    payout_threshold_usd
FROM main_clients_database
WHERE closed_channel_id IS NOT NULL
    AND closed_channel_id != ''
ORDER BY closed_channel_id;
```

---

## Configuration Management

### 🔐 Google Secret Manager Configuration

All secrets are stored in Google Secret Manager and accessed via environment variables:

| Secret Name | Environment Variable | Description |
|-------------|---------------------|-------------|
| `telegram-bot-token` | `TELEGRAM_BOT_SECRET_NAME` | Telegram bot authentication token |
| `database-host` | `DATABASE_HOST_SECRET` | Cloud SQL connection string |
| `database-name` | `DATABASE_NAME_SECRET` | PostgreSQL database name |
| `database-user` | `DATABASE_USER_SECRET` | PostgreSQL username |
| `database-password` | `DATABASE_PASSWORD_SECRET` | PostgreSQL password |
| `nowpayments-api-key` | `PAYMENT_PROVIDER_SECRET_NAME` | NowPayments API token |
| `nowpayments-ipn-url` | `NOWPAYMENTS_IPN_CALLBACK_URL` | IPN callback URL |

### 🎛️ Environment Variables

**Required:**
```bash
TELEGRAM_BOT_SECRET_NAME="projects/telepay-459221/secrets/telegram-bot-token/versions/latest"
DATABASE_HOST_SECRET="projects/telepay-459221/secrets/database-host/versions/latest"
DATABASE_NAME_SECRET="projects/telepay-459221/secrets/database-name/versions/latest"
DATABASE_USER_SECRET="projects/telepay-459221/secrets/database-user/versions/latest"
DATABASE_PASSWORD_SECRET="projects/telepay-459221/secrets/database-password/versions/latest"
PAYMENT_PROVIDER_SECRET_NAME="projects/telepay-459221/secrets/nowpayments-api-key/versions/latest"
NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/nowpayments-ipn-url/versions/latest"
```

**Optional:**
```bash
PORT=8080  # Cloud Run default port
```

---

## Error Handling & Resilience

### ⚠️ Error Handling Strategy

**1. Input Validation Errors (400 Bad Request)**
- Missing required fields in API requests
- Invalid amount format
- Amount below minimum ($4.99)
- Amount above maximum ($9999.99)
- Invalid channel ID

**2. Authentication Errors (401 Unauthorized)**
- Invalid Telegram bot token (caught during initialization)
- Expired secrets (caught during config loading)

**3. Resource Not Found Errors (404 Not Found)**
- Channel not found in database
- User session expired

**4. Telegram API Errors (handled gracefully)**
- Bot not in channel (Forbidden) → Log warning, continue
- Invalid chat ID (BadRequest) → Log error, skip channel
- Rate limiting (TooManyRequests) → Retry with exponential backoff

**5. Database Errors (500 Internal Server Error)**
- Connection failures → Retry with exponential backoff (3 attempts)
- Query timeouts → Log error, return graceful error response

**6. Payment Gateway Errors (handled gracefully)**
- NowPayments API failures → Send user-friendly error message
- Invoice creation timeout → Retry once, then fail gracefully

### 🔄 Retry Strategy

**Database Connections:**
```python
max_retries = 3
retry_delay = 1  # seconds
for attempt in range(max_retries):
    try:
        conn = get_connection()
        break
    except Exception as e:
        if attempt < max_retries - 1:
            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
        else:
            raise
```

**Telegram API Calls:**
- Built-in retry logic from python-telegram-bot library
- Automatic rate limit handling

**NowPayments API:**
- Single retry for transient errors
- Timeout: 30 seconds per request

---

## Deployment Strategy

### 🚀 Google Cloud Run Deployment

**Service Name:** `gcdonationhandler-10-26`
**Region:** `us-central1`
**Platform:** Cloud Run (fully managed)

#### Deployment Command

```bash
gcloud run deploy gcdonationhandler-10-26 \
  --source=./GCDonationHandler-10-26 \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="TELEGRAM_BOT_SECRET_NAME=projects/telepay-459221/secrets/telegram-bot-token/versions/latest" \
  --set-env-vars="DATABASE_HOST_SECRET=projects/telepay-459221/secrets/database-host/versions/latest" \
  --set-env-vars="DATABASE_NAME_SECRET=projects/telepay-459221/secrets/database-name/versions/latest" \
  --set-env-vars="DATABASE_USER_SECRET=projects/telepay-459221/secrets/database-user/versions/latest" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/database-password/versions/latest" \
  --set-env-vars="PAYMENT_PROVIDER_SECRET_NAME=projects/telepay-459221/secrets/nowpayments-api-key/versions/latest" \
  --set-env-vars="NOWPAYMENTS_IPN_CALLBACK_URL=projects/telepay-459221/secrets/nowpayments-ipn-url/versions/latest" \
  --min-instances=0 \
  --max-instances=5 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60s \
  --concurrency=80 \
  --service-account=telepay-cloudrun@telepay-459221.iam.gserviceaccount.com
```

#### IAM Configuration

**Service Account:** `telepay-cloudrun@telepay-459221.iam.gserviceaccount.com`

**Required IAM Roles:**
```bash
# Grant Secret Manager access
gcloud projects add-iam-policy-binding telepay-459221 \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant Cloud SQL Client access
gcloud projects add-iam-policy-binding telepay-459221 \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

# Grant Logging access
gcloud projects add-iam-policy-binding telepay-459221 \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"
```

### 📊 Resource Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **CPU** | 1 vCPU | Sufficient for Flask + database queries |
| **Memory** | 512Mi | Adequate for Python runtime + libraries |
| **Min Instances** | 0 | Cost optimization (scale to zero when idle) |
| **Max Instances** | 5 | Handle concurrent donation requests |
| **Timeout** | 60s | Enough for keypad operations + payment gateway |
| **Concurrency** | 80 | Standard for I/O-bound Flask apps |

### 💰 Cost Estimation

**Assumptions:**
- 1,000 donations/month
- Average 10 keypad button presses per donation
- 2 broadcast runs per month (manual trigger)

**Estimated Monthly Cost:**
- Donation keypad requests: ~10,000 requests × $0.0000004 = **$0.004**
- Broadcast requests: ~2 requests × $0.0000004 = **$0.000001**
- CPU-time: ~5 CPU-hours × $0.00002400 = **$0.12**
- Memory: ~2.5 GB-hours × $0.00000250 = **$0.006**

**Total Estimated Cost: ~$0.13/month** (excluding Cloud SQL costs, which are shared)

---

## Testing Strategy

### 🧪 Testing Pyramid

**1. Unit Tests (70% coverage target)**

Test individual handler methods:

```python
# test_keypad_handler.py
import pytest
from keypad_handler import KeypadHandler

def test_validate_amount_below_minimum():
    """Test validation rejects amounts below minimum."""
    handler = KeypadHandler(mock_db, mock_telegram, mock_token, mock_ipn)

    # Attempt to confirm $3.00 (below $4.99 minimum)
    result = handler._handle_confirm(
        user_id=123456,
        callback_query_id="test_query",
        current_amount="3.00"
    )

    assert result['success'] == False
    assert 'Below minimum amount' in result['error']

def test_validate_amount_above_maximum():
    """Test validation rejects amounts above maximum."""
    handler = KeypadHandler(mock_db, mock_telegram, mock_token, mock_ipn)

    # Attempt to confirm $10,000 (above $9999.99 maximum)
    result = handler._handle_confirm(
        user_id=123456,
        callback_query_id="test_query",
        current_amount="10000"
    )

    assert result['success'] == False
    assert 'Above maximum amount' in result['error']

def test_validate_decimal_places():
    """Test validation rejects more than 2 decimal places."""
    handler = KeypadHandler(mock_db, mock_telegram, mock_token, mock_ipn)

    # Build amount "25.55" and try to add another digit
    handler.user_states[123456] = {'amount_building': '25.55'}

    result = handler._handle_digit_press(
        user_id=123456,
        callback_data="donate_digit_0",
        callback_query_id="test_query",
        current_amount="25.55"
    )

    assert result['success'] == False
    assert 'Max decimals exceeded' in result['error']
```

**2. Integration Tests (20% coverage target)**

Test service-to-service communication:

```python
# test_integration.py
import requests

def test_start_donation_input_flow():
    """Test complete flow from start to keypad display."""
    response = requests.post(
        "http://localhost:8080/start-donation-input",
        json={
            "user_id": 123456,
            "chat_id": -1002345678901,
            "open_channel_id": "-1003268562225",
            "callback_query_id": "test_query"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data['success'] == True
    assert 'message_id' in data

def test_invalid_channel_rejection():
    """Test rejection of invalid channel ID."""
    response = requests.post(
        "http://localhost:8080/start-donation-input",
        json={
            "user_id": 123456,
            "chat_id": -1002345678901,
            "open_channel_id": "-1009999999999",  # Invalid
            "callback_query_id": "test_query"
        }
    )

    assert response.status_code == 400
    data = response.json()
    assert data['success'] == False
    assert 'Invalid channel ID' in data['error']
```

**3. End-to-End Tests (10% coverage target)**

Test complete user flows:

```python
# test_e2e.py
def test_complete_donation_flow():
    """Test full donation flow from button click to payment gateway."""
    # 1. User clicks [💝 Donate] button
    start_response = requests.post(
        f"{BASE_URL}/start-donation-input",
        json={
            "user_id": TEST_USER_ID,
            "chat_id": TEST_CHAT_ID,
            "open_channel_id": TEST_CHANNEL_ID,
            "callback_query_id": "test_query"
        }
    )
    assert start_response.status_code == 200

    # 2. User enters amount: 2, 5, ., 5, 0
    for digit in ["2", "5", ".", "5", "0"]:
        digit_response = requests.post(
            f"{BASE_URL}/keypad-input",
            json={
                "user_id": TEST_USER_ID,
                "callback_data": f"donate_digit_{digit}",
                "callback_query_id": "test_query"
            }
        )
        assert digit_response.status_code == 200

    # 3. User clicks [✅ Confirm & Pay]
    confirm_response = requests.post(
        f"{BASE_URL}/keypad-input",
        json={
            "user_id": TEST_USER_ID,
            "callback_data": "donate_confirm",
            "callback_query_id": "test_query"
        }
    )
    assert confirm_response.status_code == 200
    data = confirm_response.json()
    assert data['success'] == True
    assert data['amount'] == 25.50
    assert 'payment_result' in data
    assert 'invoice_url' in data['payment_result']
```

---

## Migration Checklist

### ✅ Pre-Deployment

- [ ] Create GCDonationHandler-10-26 directory
- [ ] Copy and adapt all 8 Python modules (service.py, keypad_handler.py, etc.)
- [ ] Create requirements.txt with all dependencies
- [ ] Create Dockerfile for containerization
- [ ] Create .env.example for documentation
- [ ] Verify all Secret Manager paths are correct
- [ ] Test database connectivity from local environment
- [ ] Test NowPayments API integration (sandbox mode)

### ✅ IAM & Permissions

- [ ] Create/verify service account: `telepay-cloudrun@telepay-459221.iam.gserviceaccount.com`
- [ ] Grant `roles/secretmanager.secretAccessor` role
- [ ] Grant `roles/cloudsql.client` role
- [ ] Grant `roles/logging.logWriter` role

### ✅ Deployment

- [ ] Build and deploy to Cloud Run: `gcloud run deploy gcdonationhandler-10-26`
- [ ] Verify service is healthy: `curl https://gcdonationhandler-10-26-xxx.a.run.app/health`
- [ ] Test `/start-donation-input` endpoint with test data
- [ ] Test `/keypad-input` endpoint with all button types
- [ ] Test `/broadcast-closed-channels` endpoint
- [ ] Monitor logs in Cloud Logging for errors

### ✅ Integration Testing

- [ ] Update GCBotCommand to call GCDonationHandler endpoints
- [ ] Test donation flow end-to-end with real Telegram bot
- [ ] Verify keypad rendering in Telegram client
- [ ] Verify amount validation (min, max, decimals)
- [ ] Verify payment gateway integration
- [ ] Verify broadcast to closed channels
- [ ] Verify error handling (invalid channel, session expired, etc.)

### ✅ Monitoring & Observability

- [ ] Set up Cloud Monitoring dashboard for GCDonationHandler
- [ ] Create alerts for error rate > 5%
- [ ] Create alerts for request latency p95 > 2s
- [ ] Set up log-based metrics for donation confirmations
- [ ] Verify structured logging in Cloud Logging

### ✅ Documentation

- [ ] Document API endpoints for GCBotCommand integration
- [ ] Document environment variables and secrets
- [ ] Document deployment procedure
- [ ] Document rollback procedure
- [ ] Update PROGRESS.md with migration status

---

## Appendix: File Tree

### 📁 Complete Service Structure

```
GCDonationHandler-10-26/
│
├── service.py                      # Flask application (main entry point)
├── keypad_handler.py               # Donation keypad logic & validation
├── payment_gateway_manager.py      # NowPayments API integration
├── database_manager.py             # PostgreSQL operations
├── config_manager.py               # Secret Manager integration
├── telegram_client.py              # Telegram Bot API wrapper
├── broadcast_manager.py            # Closed channel broadcast logic
│
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container definition
├── .env.example                    # Environment variable template
├── .dockerignore                   # Files to exclude from Docker build
│
└── tests/                          # Unit & integration tests
    ├── __init__.py
    ├── test_keypad_handler.py
    ├── test_payment_gateway.py
    ├── test_database_manager.py
    ├── test_integration.py
    └── test_e2e.py
```

---

## Conclusion

This architecture document provides a **complete, production-ready specification** for migrating the donation handler functionality from the TelePay10-26 monolith to an independent, self-contained GCDonationHandler Cloud Run webhook service.

### Key Achievements

✅ **Self-Contained Modules**: All dependencies embedded within the service
✅ **Zero Coupling**: No shared libraries, complete autonomy
✅ **Production-Ready**: Comprehensive error handling, logging, and monitoring
✅ **Scalable**: Cloud Run auto-scaling from 0 to 5 instances
✅ **Cost-Efficient**: ~$0.13/month for typical donation volumes
✅ **Well-Tested**: Unit, integration, and E2E test strategies defined
✅ **Fully Documented**: API specs, deployment procedures, and migration checklist

### Next Steps

1. **Review & Approve**: Review this architecture document with stakeholders
2. **Create Service Directory**: Set up GCDonationHandler-10-26 directory structure
3. **Implement Modules**: Copy and adapt source code with self-contained modules
4. **Deploy to Staging**: Deploy to staging environment for testing
5. **Integration Testing**: Test integration with GCBotCommand
6. **Production Deployment**: Deploy to production with monitoring
7. **Update Documentation**: Update PROGRESS.md and DECISIONS.md

---

**Document Owner:** Claude
**Review Date:** 2025-11-12
**Status:** Ready for Implementation