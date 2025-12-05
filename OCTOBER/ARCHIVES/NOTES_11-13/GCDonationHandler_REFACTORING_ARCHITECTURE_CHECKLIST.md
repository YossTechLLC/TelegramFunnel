# GCDonationHandler Refactoring Implementation Checklist

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Implementation Ready
**Branch:** TelePay-REFACTOR
**Parent Document:** GCDonationHandler_REFACTORING_ARCHITECTURE.md

---

## Overview

This checklist provides a **step-by-step implementation guide** for refactoring the donation handler functionality from the TelePay10-26 monolith into an independent, self-contained GCDonationHandler Cloud Run webhook service.

**Key Principle:** Each module is implemented as a **standalone Python file** with zero internal dependencies, ensuring a modular code structure that avoids one monolithic file.

---

## Phase 1: Pre-Implementation Setup

### 1.1 Directory Structure Creation
- [ ] Create `GCDonationHandler-10-26/` directory in `/OCTOBER/10-26/`
- [ ] Create `GCDonationHandler-10-26/tests/` subdirectory for test files
- [ ] Verify directory is in correct location: `/OCTOBER/10-26/GCDonationHandler-10-26/`

### 1.2 Environment Verification
- [ ] Verify Python version: `python --version` (should be 3.11+)
- [ ] Verify gcloud CLI is authenticated: `gcloud auth list`
- [ ] Verify project is set: `gcloud config get-value project` (should be `telepay-459221`)
- [ ] Verify access to Secret Manager: `gcloud secrets list`
- [ ] Verify database instance exists: `gcloud sql instances describe telepaypsql`

### 1.3 Source Code Review
- [ ] Review `TelePay10-26/donation_input_handler.py` (654 lines) - understand keypad logic
- [ ] Review `TelePay10-26/closed_channel_manager.py` (230 lines) - understand broadcast logic
- [ ] Review `TelePay10-26/database.py` (719 lines) - identify database methods used
- [ ] Review `TelePay10-26/config_manager.py` (76 lines) - understand Secret Manager patterns
- [ ] Review `TelePay10-26/start_np_gateway.py` (314 lines) - understand payment gateway integration
- [ ] Document all validation constants (MIN_AMOUNT, MAX_AMOUNT, etc.)
- [ ] Document all callback_data patterns used (donate_digit_, donate_backspace, etc.)

---

## Phase 2: Core Module Implementation

### 2.1 Module: config_manager.py (SECRET MANAGER INTEGRATION)
**Purpose:** Fetch configuration from Google Secret Manager
**Source:** `TelePay10-26/config_manager.py`
**Location:** `GCDonationHandler-10-26/config_manager.py`

#### Implementation Tasks:
- [ ] Create `config_manager.py` file
- [ ] Import required packages: `google-cloud-secret-manager`, `logging`, `typing`
- [ ] Define `ConfigManager` class with `__init__()` method
- [ ] Implement `fetch_secret(secret_env_var)` method:
  - [ ] Parse secret path from environment variable
  - [ ] Access Secret Manager client
  - [ ] Fetch secret value
  - [ ] Handle errors gracefully (SecretNotFound, PermissionDenied)
  - [ ] Return secret as string or None
- [ ] Implement `initialize_config()` method:
  - [ ] Fetch bot token: `TELEGRAM_BOT_SECRET_NAME`
  - [ ] Fetch database host: `DATABASE_HOST_SECRET`
  - [ ] Fetch database port: default to `5432`
  - [ ] Fetch database name: `DATABASE_NAME_SECRET`
  - [ ] Fetch database user: `DATABASE_USER_SECRET`
  - [ ] Fetch database password: `DATABASE_PASSWORD_SECRET`
  - [ ] Fetch payment token: `PAYMENT_PROVIDER_SECRET_NAME`
  - [ ] Fetch IPN callback URL: `NOWPAYMENTS_IPN_CALLBACK_URL`
  - [ ] Return dictionary with all config values
  - [ ] Log success/failure with emojis (🔧, ✅, ❌)

#### Verification:
- [ ] Module has NO imports from other internal modules (only external packages)
- [ ] Module can be imported independently: `from config_manager import ConfigManager`
- [ ] All methods have docstrings with Args and Returns sections
- [ ] All error cases are handled with appropriate logging

---

### 2.2 Module: database_manager.py (POSTGRESQL OPERATIONS)
**Purpose:** Handle all PostgreSQL database operations
**Source:** `TelePay10-26/database.py`
**Location:** `GCDonationHandler-10-26/database_manager.py`

#### Implementation Tasks:
- [ ] Create `database_manager.py` file
- [ ] Import required packages: `psycopg2`, `logging`, `typing`
- [ ] Define `DatabaseManager` class with `__init__()` method:
  - [ ] Accept parameters: `db_host`, `db_port`, `db_name`, `db_user`, `db_password`
  - [ ] Store connection parameters
  - [ ] Initialize connection pool (optional, or use simple connect/close pattern)
- [ ] Implement `_get_connection()` private method:
  - [ ] Create psycopg2 connection with stored credentials
  - [ ] Handle connection errors gracefully
  - [ ] Return connection object or None
- [ ] Implement `channel_exists(open_channel_id)` method:
  - [ ] Query: `SELECT 1 FROM main_clients_database WHERE open_channel_id = %s`
  - [ ] Return True if found, False otherwise
  - [ ] Handle database errors (log and return False)
- [ ] Implement `get_channel_details_by_open_id(open_channel_id)` method:
  - [ ] Query: `SELECT * FROM main_clients_database WHERE open_channel_id = %s`
  - [ ] Return dictionary with channel details or None
  - [ ] Include fields: `closed_channel_id`, `closed_channel_title`, `closed_channel_description`, `closed_channel_donation_message`, `payout_strategy`, `payout_threshold_usd`
- [ ] Implement `fetch_all_closed_channels()` method:
  - [ ] Query: `SELECT open_channel_id, closed_channel_id, closed_channel_donation_message FROM main_clients_database WHERE closed_channel_id IS NOT NULL`
  - [ ] Return list of dictionaries with channel info
  - [ ] Handle empty results gracefully
- [ ] Implement `close()` method for cleanup

#### Verification:
- [ ] Module has NO imports from other internal modules (only external packages)
- [ ] Module can be imported independently: `from database_manager import DatabaseManager`
- [ ] All SQL queries use parameterized statements (no string interpolation)
- [ ] All database errors are caught and logged with emojis (🗄️, ✅, ❌)
- [ ] Connection cleanup is handled properly (using context managers or explicit close)

---

### 2.3 Module: telegram_client.py (TELEGRAM BOT API WRAPPER)
**Purpose:** Wrapper for Telegram Bot API operations
**Source:** Uses `python-telegram-bot` library patterns
**Location:** `GCDonationHandler-10-26/telegram_client.py`

#### Implementation Tasks:
- [ ] Create `telegram_client.py` file
- [ ] Import required packages: `telegram`, `asyncio`, `logging`, `typing`
- [ ] Define `TelegramClient` class with `__init__(bot_token)` method:
  - [ ] Initialize `Bot` object with token: `Bot(token=bot_token)`
  - [ ] Store bot instance
- [ ] Implement `send_message(chat_id, text, reply_markup, parse_mode)` method:
  - [ ] Use `asyncio.run()` to call async `bot.send_message()`
  - [ ] Accept optional `reply_markup` (InlineKeyboardMarkup)
  - [ ] Accept optional `parse_mode` (default "HTML")
  - [ ] Return dictionary: `{'success': True, 'message_id': int}` or `{'success': False, 'error': str}`
  - [ ] Handle TelegramError exceptions
- [ ] Implement `send_message_with_webapp_button(chat_id, text, button_text, webapp_url)` method:
  - [ ] Create InlineKeyboardButton with WebAppInfo
  - [ ] Send message with button
  - [ ] Return success/error dictionary
- [ ] Implement `edit_message_reply_markup(chat_id, message_id, reply_markup)` method:
  - [ ] Use `asyncio.run()` to call async `bot.edit_message_reply_markup()`
  - [ ] Handle "message not modified" error gracefully (not a real error)
  - [ ] Return success/error dictionary
- [ ] Implement `delete_message(chat_id, message_id)` method:
  - [ ] Use `asyncio.run()` to call async `bot.delete_message()`
  - [ ] Handle "message not found" error gracefully
  - [ ] Return success/error dictionary
- [ ] Implement `answer_callback_query(callback_query_id, text, show_alert)` method:
  - [ ] Use `asyncio.run()` to call async `bot.answer_callback_query()`
  - [ ] Accept optional `text` and `show_alert` (default False)
  - [ ] Return success/error dictionary

#### Verification:
- [ ] Module has NO imports from other internal modules (only external packages)
- [ ] Module can be imported independently: `from telegram_client import TelegramClient`
- [ ] All async operations are wrapped with `asyncio.run()` for Flask compatibility
- [ ] All Telegram errors are caught and logged with emojis (📱, ✅, ❌)
- [ ] All methods return consistent dictionary format

---

### 2.4 Module: payment_gateway_manager.py (NOWPAYMENTS INTEGRATION)
**Purpose:** Create payment invoices via NowPayments API
**Source:** `TelePay10-26/start_np_gateway.py`
**Location:** `GCDonationHandler-10-26/payment_gateway_manager.py`

#### Implementation Tasks:
- [ ] Create `payment_gateway_manager.py` file
- [ ] Import required packages: `httpx`, `logging`, `typing`
- [ ] Define `PaymentGatewayManager` class with `__init__(payment_token, ipn_callback_url)` method:
  - [ ] Store payment token
  - [ ] Store IPN callback URL
  - [ ] Define API base URL: `https://api.nowpayments.io/v1/invoice`
- [ ] Implement `create_payment_invoice(user_id, amount, order_id)` method:
  - [ ] Construct payload:
    ```python
    {
        "price_amount": amount,
        "price_currency": "USD",
        "order_id": order_id,
        "order_description": f"Donation for channel",
        "ipn_callback_url": self.ipn_callback_url,
        "success_url": "https://paygateprime.com/success",
        "cancel_url": "https://paygateprime.com/cancel"
    }
    ```
  - [ ] Set headers: `{"x-api-key": self.payment_token, "Content-Type": "application/json"}`
  - [ ] Use synchronous `httpx.Client()` for Flask compatibility
  - [ ] POST request to NowPayments API
  - [ ] Parse response JSON
  - [ ] Extract `invoice_url` from response
  - [ ] Return dictionary: `{'success': True, 'data': {'invoice_url': str}}` or `{'success': False, 'error': str}`
  - [ ] Handle HTTP errors (400, 401, 500, etc.)
  - [ ] Handle network errors (timeout, connection refused)

#### Verification:
- [ ] Module has NO imports from other internal modules (only external packages)
- [ ] Module can be imported independently: `from payment_gateway_manager import PaymentGatewayManager`
- [ ] Uses synchronous HTTP client (httpx.Client, NOT httpx.AsyncClient)
- [ ] All API errors are caught and logged with emojis (💳, ✅, ❌)
- [ ] Invoice URLs are validated before returning

---

### 2.5 Module: keypad_handler.py (DONATION KEYPAD LOGIC)
**Purpose:** Handle inline numeric keypad for donation amount input
**Source:** `TelePay10-26/donation_input_handler.py`
**Location:** `GCDonationHandler-10-26/keypad_handler.py`

#### Implementation Tasks:
- [ ] Create `keypad_handler.py` file
- [ ] Import required packages: `telegram`, `logging`, `typing`, `time`
- [ ] Define validation constants as class attributes:
  - [ ] `MIN_AMOUNT = 4.99`
  - [ ] `MAX_AMOUNT = 9999.99`
  - [ ] `MAX_DECIMALS = 2`
  - [ ] `MAX_DIGITS_BEFORE_DECIMAL = 4`
- [ ] Define `KeypadHandler` class with `__init__(db_manager, telegram_client, payment_token, ipn_callback_url)` method:
  - [ ] Store dependencies (db_manager, telegram_client)
  - [ ] Initialize payment gateway manager internally
  - [ ] Initialize in-memory state storage: `self.user_states = {}`
- [ ] Implement `start_donation_input(user_id, chat_id, open_channel_id, callback_query_id)` method:
  - [ ] Answer callback query with confirmation message
  - [ ] Initialize user state dictionary:
    ```python
    self.user_states[user_id] = {
        'amount_building': '0',
        'open_channel_id': open_channel_id,
        'started_at': time.time(),
        'chat_id': chat_id,
        'keypad_message_id': None
    }
    ```
  - [ ] Create keypad message text with instructions and min/max amounts
  - [ ] Generate keypad with `_create_donation_keypad('0')`
  - [ ] Send message via telegram_client
  - [ ] Store message_id in user state
  - [ ] Return success/error dictionary
- [ ] Implement `handle_keypad_input(user_id, callback_data, callback_query_id, message_id, chat_id)` method:
  - [ ] Validate user state exists (handle expired sessions)
  - [ ] Route to appropriate handler based on callback_data prefix:
    - [ ] `donate_digit_` → `_handle_digit_press()`
    - [ ] `donate_backspace` → `_handle_backspace()`
    - [ ] `donate_clear` → `_handle_clear()`
    - [ ] `donate_confirm` → `_handle_confirm()`
    - [ ] `donate_cancel` → `_handle_cancel()`
    - [ ] `donate_noop` → Answer callback query only
  - [ ] Return success/error dictionary
- [ ] Implement `_handle_digit_press(user_id, callback_data, callback_query_id, current_amount)` private method:
  - [ ] Extract digit from callback_data: `callback_data.split("_")[2]`
  - [ ] **Validation Rule 1:** Replace leading zero: `"0" + "5" → "5"`
  - [ ] **Validation Rule 2:** Single decimal point: reject if "." already in amount
  - [ ] **Validation Rule 3:** Max 2 decimal places: reject if decimal part has 2 digits
  - [ ] **Validation Rule 4:** Max 4 digits before decimal: reject if length >= 4
  - [ ] Update user state with new amount
  - [ ] Edit message keyboard with updated amount display
  - [ ] Return success/error dictionary
- [ ] Implement `_handle_backspace(user_id, callback_query_id, current_amount)` private method:
  - [ ] Remove last character: `current_amount[:-1]`
  - [ ] Reset to "0" if empty
  - [ ] Update user state and edit keyboard
  - [ ] Return success dictionary
- [ ] Implement `_handle_clear(user_id, callback_query_id)` private method:
  - [ ] Reset amount to "0"
  - [ ] Update user state and edit keyboard
  - [ ] Return success dictionary
- [ ] Implement `_handle_confirm(user_id, callback_query_id, current_amount)` private method:
  - [ ] Parse amount as float (handle ValueError)
  - [ ] Validate amount >= MIN_AMOUNT (reject with alert if below)
  - [ ] Validate amount <= MAX_AMOUNT (reject with alert if above)
  - [ ] Get open_channel_id from user state
  - [ ] Delete keypad message
  - [ ] Send confirmation message to user
  - [ ] Call `_trigger_payment_gateway(user_id, amount, open_channel_id)`
  - [ ] Clean up user state (optional: or keep for analytics)
  - [ ] Return success dictionary
- [ ] Implement `_handle_cancel(user_id, callback_query_id)` private method:
  - [ ] Answer callback query with cancellation message
  - [ ] Delete keypad message
  - [ ] Clean up user state
  - [ ] Return success dictionary
- [ ] Implement `_trigger_payment_gateway(user_id, amount, open_channel_id)` private method:
  - [ ] Create order_id: `f"PGP-{user_id}|{open_channel_id}"`
  - [ ] Call payment gateway manager to create invoice
  - [ ] Extract invoice_url from response
  - [ ] Send message with Web App button linking to invoice_url
  - [ ] Return success/error dictionary
- [ ] Implement `_create_donation_keypad(amount_display)` private method:
  - [ ] Create 4×3 grid of digit buttons (1-9, 0, .)
  - [ ] Add row with Clear, Backspace buttons
  - [ ] Add row with Cancel, Amount Display (noop button), Confirm buttons
  - [ ] Format amount display: `$XX.XX` or `$XXXX.XX`
  - [ ] Return InlineKeyboardMarkup object
- [ ] Implement `_format_amount_display(amount)` private method:
  - [ ] Convert string amount to formatted display: `$25.50`
  - [ ] Handle edge cases: "0" → "$0.00", "5" → "$5.00", "5." → "$5."
  - [ ] Return formatted string

#### Verification:
- [ ] Module has NO imports from other internal modules (only external packages)
- [ ] Module can be imported independently: `from keypad_handler import KeypadHandler`
- [ ] All validation rules are implemented exactly as specified
- [ ] All validation constants are defined as class attributes (not hardcoded)
- [ ] User state management is clean and predictable
- [ ] All error messages use emojis for user feedback
- [ ] Keyboard layout matches calculator style (3×4 grid)

---

### 2.6 Module: broadcast_manager.py (CLOSED CHANNEL BROADCAST)
**Purpose:** Send donation button to closed/private channels
**Source:** `TelePay10-26/closed_channel_manager.py`
**Location:** `GCDonationHandler-10-26/broadcast_manager.py`

#### Implementation Tasks:
- [ ] Create `broadcast_manager.py` file
- [ ] Import required packages: `telegram`, `logging`, `typing`, `asyncio`
- [ ] Define `BroadcastManager` class with `__init__(db_manager, telegram_client)` method:
  - [ ] Store dependencies (db_manager, telegram_client)
- [ ] Implement `broadcast_to_closed_channels(force_resend)` method:
  - [ ] Fetch all closed channels from database: `db_manager.fetch_all_closed_channels()`
  - [ ] Initialize counters: `total_channels`, `successful`, `failed`, `errors = []`
  - [ ] Loop through each channel:
    - [ ] Extract `closed_channel_id`, `open_channel_id`, `donation_message`
    - [ ] Create donation button with `_create_donation_button(open_channel_id)`
    - [ ] Format message text with `_format_donation_message(donation_message)`
    - [ ] Send message to closed channel via telegram_client
    - [ ] Increment success counter on success
    - [ ] Catch exceptions (Forbidden, BadRequest, TelegramError) and increment fail counter
    - [ ] Add error details to errors list
    - [ ] Add small delay between messages: `asyncio.sleep(0.1)` to avoid rate limiting
  - [ ] Log summary with emojis (📨, ✅, ❌)
  - [ ] Return dictionary with statistics:
    ```python
    {
        'total_channels': int,
        'successful': int,
        'failed': int,
        'errors': [{'channel_id': str, 'error': str}, ...]
    }
    ```
- [ ] Implement `_create_donation_button(open_channel_id)` private method:
  - [ ] Create callback_data: `f"donate_start_{open_channel_id}"`
  - [ ] Validate callback_data length <= 64 bytes (Telegram limit)
  - [ ] Create InlineKeyboardButton with text "💝 Donate to Support This Channel"
  - [ ] Return InlineKeyboardMarkup with single button
- [ ] Implement `_format_donation_message(donation_message)` private method:
  - [ ] Format message: `f"Enjoying the content? Consider making a donation.\n<b>{donation_message}</b>"`
  - [ ] Validate message length <= 4096 characters (Telegram limit)
  - [ ] Truncate if necessary with "..." suffix
  - [ ] Return formatted string

#### Verification:
- [ ] Module has NO imports from other internal modules (only external packages)
- [ ] Module can be imported independently: `from broadcast_manager import BroadcastManager`
- [ ] Error handling covers all Telegram error types (Forbidden, BadRequest, TelegramError)
- [ ] Rate limiting is implemented with delay between messages
- [ ] Callback data length is validated (64-byte Telegram limit)
- [ ] Message length is validated (4096-character Telegram limit)
- [ ] Summary statistics are accurate and comprehensive

---

### 2.7 Module: service.py (FLASK APPLICATION ENTRY POINT)
**Purpose:** Flask application with API endpoints
**Source:** Flask application factory pattern
**Location:** `GCDonationHandler-10-26/service.py`

#### Implementation Tasks:
- [ ] Create `service.py` file
- [ ] Import required packages: `flask`, `logging`
- [ ] Import all internal modules:
  - [ ] `from config_manager import ConfigManager`
  - [ ] `from database_manager import DatabaseManager`
  - [ ] `from telegram_client import TelegramClient`
  - [ ] `from keypad_handler import KeypadHandler`
  - [ ] `from broadcast_manager import BroadcastManager`
- [ ] Configure logging with emoji support
- [ ] Define `create_app()` application factory function:
  - [ ] Create Flask app instance
  - [ ] Initialize ConfigManager and load configuration
  - [ ] Validate bot_token is available (raise RuntimeError if missing)
  - [ ] Initialize DatabaseManager with DB credentials
  - [ ] Initialize TelegramClient with bot_token
  - [ ] Initialize KeypadHandler with dependencies
  - [ ] Initialize BroadcastManager with dependencies
  - [ ] Store all managers in app context: `app.db_manager`, `app.telegram_client`, etc.
  - [ ] Return app instance
- [ ] Implement `@app.route("/health", methods=["GET"])` endpoint:
  - [ ] Return JSON: `{"status": "healthy", "service": "GCDonationHandler", "version": "1.0"}`
  - [ ] HTTP 200 status
- [ ] Implement `@app.route("/start-donation-input", methods=["POST"])` endpoint:
  - [ ] Parse JSON request body
  - [ ] Validate required fields: `user_id`, `chat_id`, `open_channel_id`, `callback_query_id`
  - [ ] Return HTTP 400 if missing fields
  - [ ] Validate channel exists via `app.db_manager.channel_exists()`
  - [ ] Return HTTP 400 with error if invalid channel
  - [ ] Call `app.keypad_handler.start_donation_input()`
  - [ ] Return HTTP 200 with success result or HTTP 500 with error
  - [ ] Log all actions with emojis (💝, ✅, ❌)
- [ ] Implement `@app.route("/keypad-input", methods=["POST"])` endpoint:
  - [ ] Parse JSON request body
  - [ ] Validate required fields: `user_id`, `callback_data`, `callback_query_id`
  - [ ] Return HTTP 400 if missing fields
  - [ ] Call `app.keypad_handler.handle_keypad_input()`
  - [ ] Return HTTP 200 with result (success or error)
  - [ ] Log all actions with emojis (🔢, ✅, ❌)
- [ ] Implement `@app.route("/broadcast-closed-channels", methods=["POST"])` endpoint:
  - [ ] Parse optional JSON request body (for `force_resend` flag)
  - [ ] Call `app.broadcast_manager.broadcast_to_closed_channels()`
  - [ ] Return HTTP 200 with broadcast statistics
  - [ ] Log summary with emojis (📢, ✅, ❌)
- [ ] Add `if __name__ == "__main__":` block:
  - [ ] Call `create_app()` to create app instance
  - [ ] Run Flask app on port 8080 (Cloud Run default)
  - [ ] Use `host="0.0.0.0"` for external access

#### Verification:
- [ ] Module imports ALL 5 internal modules (config_manager, database_manager, telegram_client, keypad_handler, broadcast_manager)
- [ ] Application factory pattern is used (`create_app()` function)
- [ ] All endpoints have proper error handling (try/except blocks)
- [ ] All endpoints validate input before processing
- [ ] All endpoints return consistent JSON format
- [ ] Health check endpoint is accessible without authentication
- [ ] All logs use emoji prefixes for visual clarity

---

## Phase 3: Supporting Files

### 3.1 requirements.txt (PYTHON DEPENDENCIES)
**Purpose:** Define all Python package dependencies
**Location:** `GCDonationHandler-10-26/requirements.txt`

#### Implementation Tasks:
- [ ] Create `requirements.txt` file
- [ ] Add Flask: `Flask==3.0.0`
- [ ] Add python-telegram-bot: `python-telegram-bot==21.0`
- [ ] Add httpx: `httpx==0.25.0` (for synchronous HTTP requests)
- [ ] Add psycopg2-binary: `psycopg2-binary==2.9.9` (PostgreSQL driver)
- [ ] Add google-cloud-secret-manager: `google-cloud-secret-manager==2.16.4`
- [ ] Add cloud-sql-python-connector: `cloud-sql-python-connector[pg8000]==1.4.3`
- [ ] Add python-json-logger: `python-json-logger==2.0.7` (structured logging)

#### Verification:
- [ ] All dependencies have pinned versions (no `>=` or `~=`)
- [ ] No duplicate packages listed
- [ ] File is valid: `pip install -r requirements.txt` runs without errors

---

### 3.2 Dockerfile (CONTAINER DEFINITION)
**Purpose:** Define Docker container for Cloud Run deployment
**Location:** `GCDonationHandler-10-26/Dockerfile`

#### Implementation Tasks:
- [ ] Create `Dockerfile` file
- [ ] Use Python 3.11 slim base image: `FROM python:3.11-slim`
- [ ] Set working directory: `WORKDIR /app`
- [ ] Install system dependencies:
  ```dockerfile
  RUN apt-get update && apt-get install -y \
      gcc \
      libpq-dev \
      && rm -rf /var/lib/apt/lists/*
  ```
- [ ] Copy requirements.txt: `COPY requirements.txt .`
- [ ] Install Python dependencies: `RUN pip install --no-cache-dir -r requirements.txt`
- [ ] Copy all Python modules:
  ```dockerfile
  COPY service.py keypad_handler.py payment_gateway_manager.py \
       database_manager.py config_manager.py telegram_client.py \
       broadcast_manager.py .
  ```
- [ ] Expose port 8080: `EXPOSE 8080`
- [ ] Set entrypoint: `CMD ["python", "service.py"]`

#### Verification:
- [ ] Dockerfile uses multi-line format for readability
- [ ] Build cache is optimized (requirements.txt copied before source code)
- [ ] No unnecessary files are copied (no tests/, no .git/)
- [ ] Port 8080 is exposed (Cloud Run default)

---

### 3.3 .dockerignore (EXCLUDE FILES FROM BUILD)
**Purpose:** Exclude unnecessary files from Docker build context
**Location:** `GCDonationHandler-10-26/.dockerignore`

#### Implementation Tasks:
- [ ] Create `.dockerignore` file
- [ ] Add patterns:
  ```
  tests/
  __pycache__/
  *.pyc
  *.pyo
  *.pyd
  .Python
  .env
  .venv
  venv/
  .git/
  .gitignore
  README.md
  *.md
  .DS_Store
  ```

#### Verification:
- [ ] File excludes test files and virtual environments
- [ ] File excludes Git metadata
- [ ] File excludes documentation files

---

### 3.4 .env.example (ENVIRONMENT VARIABLE TEMPLATE)
**Purpose:** Document required environment variables
**Location:** `GCDonationHandler-10-26/.env.example`

#### Implementation Tasks:
- [ ] Create `.env.example` file
- [ ] Add template with comments:
  ```bash
  # Telegram Bot Token (Secret Manager path)
  TELEGRAM_BOT_SECRET_NAME=projects/telepay-459221/secrets/telegram-bot-token/versions/latest

  # Database Configuration (Secret Manager paths)
  DATABASE_HOST_SECRET=projects/telepay-459221/secrets/database-host/versions/latest
  DATABASE_NAME_SECRET=projects/telepay-459221/secrets/database-name/versions/latest
  DATABASE_USER_SECRET=projects/telepay-459221/secrets/database-user/versions/latest
  DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/database-password/versions/latest

  # Payment Gateway Configuration (Secret Manager paths)
  PAYMENT_PROVIDER_SECRET_NAME=projects/telepay-459221/secrets/nowpayments-api-key/versions/latest
  NOWPAYMENTS_IPN_CALLBACK_URL=projects/telepay-459221/secrets/nowpayments-ipn-url/versions/latest

  # Google Cloud Configuration
  GOOGLE_CLOUD_PROJECT=telepay-459221
  ```

#### Verification:
- [ ] All environment variables are documented
- [ ] All Secret Manager paths use correct format
- [ ] Comments explain purpose of each variable

---

## Phase 4: Testing Implementation

### 4.1 Test Infrastructure Setup
- [ ] Create `GCDonationHandler-10-26/tests/__init__.py` file
- [ ] Create test fixtures file: `tests/conftest.py` with pytest fixtures
- [ ] Create mock objects for database, telegram client, payment gateway

### 4.2 Unit Tests: test_keypad_handler.py
**Purpose:** Test keypad logic and validation rules
**Location:** `GCDonationHandler-10-26/tests/test_keypad_handler.py`

#### Implementation Tasks:
- [ ] Import pytest and KeypadHandler
- [ ] Create mock dependencies (db_manager, telegram_client)
- [ ] Test: `test_validate_amount_below_minimum()` - rejects $3.00
- [ ] Test: `test_validate_amount_above_maximum()` - rejects $10000
- [ ] Test: `test_validate_decimal_places()` - rejects third decimal digit
- [ ] Test: `test_validate_single_decimal_point()` - rejects second decimal point
- [ ] Test: `test_validate_max_digits_before_decimal()` - rejects fifth digit
- [ ] Test: `test_leading_zero_replacement()` - "0" + "5" = "5"
- [ ] Test: `test_backspace_functionality()` - removes last character
- [ ] Test: `test_clear_functionality()` - resets to "0"
- [ ] Test: `test_confirm_valid_amount()` - accepts $25.50
- [ ] Test: `test_cancel_functionality()` - cleans up state

#### Verification:
- [ ] All tests pass: `pytest tests/test_keypad_handler.py -v`
- [ ] Code coverage > 70% for keypad_handler.py: `pytest --cov=keypad_handler`

---

### 4.3 Unit Tests: test_payment_gateway.py
**Purpose:** Test payment gateway integration
**Location:** `GCDonationHandler-10-26/tests/test_payment_gateway.py`

#### Implementation Tasks:
- [ ] Import pytest and PaymentGatewayManager
- [ ] Mock httpx.Client for HTTP requests
- [ ] Test: `test_create_invoice_success()` - successful invoice creation
- [ ] Test: `test_create_invoice_api_error()` - handles 400 error
- [ ] Test: `test_create_invoice_auth_error()` - handles 401 error
- [ ] Test: `test_create_invoice_network_error()` - handles timeout

#### Verification:
- [ ] All tests pass: `pytest tests/test_payment_gateway.py -v`
- [ ] Code coverage > 70% for payment_gateway_manager.py

---

### 4.4 Unit Tests: test_database_manager.py
**Purpose:** Test database operations
**Location:** `GCDonationHandler-10-26/tests/test_database_manager.py`

#### Implementation Tasks:
- [ ] Import pytest and DatabaseManager
- [ ] Mock psycopg2 connection
- [ ] Test: `test_channel_exists_found()` - returns True for existing channel
- [ ] Test: `test_channel_exists_not_found()` - returns False for non-existent channel
- [ ] Test: `test_get_channel_details()` - returns channel dictionary
- [ ] Test: `test_fetch_all_closed_channels()` - returns list of channels

#### Verification:
- [ ] All tests pass: `pytest tests/test_database_manager.py -v`
- [ ] Code coverage > 70% for database_manager.py

---

### 4.5 Integration Tests: test_integration.py
**Purpose:** Test API endpoints end-to-end
**Location:** `GCDonationHandler-10-26/tests/test_integration.py`

#### Implementation Tasks:
- [ ] Import pytest and requests
- [ ] Start Flask test server with test configuration
- [ ] Test: `test_health_endpoint()` - GET /health returns 200
- [ ] Test: `test_start_donation_input_success()` - POST /start-donation-input with valid data
- [ ] Test: `test_start_donation_input_invalid_channel()` - POST with invalid channel returns 400
- [ ] Test: `test_keypad_input_digit()` - POST /keypad-input with digit callback
- [ ] Test: `test_keypad_input_confirm()` - POST /keypad-input with confirm callback
- [ ] Test: `test_broadcast_closed_channels()` - POST /broadcast-closed-channels

#### Verification:
- [ ] All tests pass: `pytest tests/test_integration.py -v`
- [ ] Tests use test database or mocks (not production database)

---

### 4.6 End-to-End Tests: test_e2e.py
**Purpose:** Test complete donation flow
**Location:** `GCDonationHandler-10-26/tests/test_e2e.py`

#### Implementation Tasks:
- [ ] Import pytest and requests
- [ ] Test: `test_complete_donation_flow()`:
  - [ ] POST /start-donation-input
  - [ ] POST /keypad-input with multiple digits
  - [ ] POST /keypad-input with confirm
  - [ ] Verify payment gateway was called
  - [ ] Verify Telegram message was sent
- [ ] Test: `test_donation_flow_with_cancel()`:
  - [ ] POST /start-donation-input
  - [ ] POST /keypad-input with cancel
  - [ ] Verify state is cleaned up

#### Verification:
- [ ] All tests pass: `pytest tests/test_e2e.py -v`
- [ ] Tests simulate real user interactions

---

## Phase 5: Deployment Preparation

### 5.1 Secret Manager Verification
- [ ] Verify bot token secret exists: `gcloud secrets describe telegram-bot-token`
- [ ] Verify database secrets exist:
  - [ ] `gcloud secrets describe database-host`
  - [ ] `gcloud secrets describe database-name`
  - [ ] `gcloud secrets describe database-user`
  - [ ] `gcloud secrets describe database-password`
- [ ] Verify payment secrets exist:
  - [ ] `gcloud secrets describe nowpayments-api-key`
  - [ ] `gcloud secrets describe nowpayments-ipn-url`
- [ ] Test secret access from local environment with service account

### 5.2 IAM Role Configuration
- [ ] Verify service account exists: `telepay-cloudrun@telepay-459221.iam.gserviceaccount.com`
- [ ] Grant Secret Manager access:
  ```bash
  gcloud projects add-iam-policy-binding telepay-459221 \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
  ```
- [ ] Grant Cloud SQL Client access:
  ```bash
  gcloud projects add-iam-policy-binding telepay-459221 \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"
  ```
- [ ] Grant Logging access:
  ```bash
  gcloud projects add-iam-policy-binding telepay-459221 \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"
  ```
- [ ] Verify IAM bindings: `gcloud projects get-iam-policy telepay-459221 --flatten="bindings[].members" --filter="bindings.members:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com"`

### 5.3 Database Connectivity Test
- [ ] Test local connection to telepaypsql database
- [ ] Verify `main_clients_database` table exists and has data
- [ ] Verify schema matches expected structure (open_channel_id, closed_channel_id, etc.)
- [ ] Test all SQL queries from database_manager.py manually

### 5.4 Local Testing
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Set environment variables from .env.example
- [ ] Run Flask app locally: `python service.py`
- [ ] Test /health endpoint: `curl http://localhost:8080/health`
- [ ] Test /start-donation-input with test data (use curl or Postman)
- [ ] Monitor logs for errors

---

## Phase 6: Deployment Execution

### 6.1 Docker Build Test
- [ ] Build Docker image locally:
  ```bash
  docker build -t gcdonationhandler-10-26:test ./GCDonationHandler-10-26
  ```
- [ ] Verify image size is reasonable (< 500MB)
- [ ] Run container locally:
  ```bash
  docker run -p 8080:8080 \
    -e TELEGRAM_BOT_SECRET_NAME="..." \
    gcdonationhandler-10-26:test
  ```
- [ ] Test /health endpoint on containerized app

### 6.2 Cloud Run Deployment
- [ ] Navigate to service directory: `cd GCDonationHandler-10-26`
- [ ] Deploy to Cloud Run:
  ```bash
  gcloud run deploy gcdonationhandler-10-26 \
    --source=. \
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
- [ ] Wait for deployment to complete (typically 3-5 minutes)
- [ ] Note the service URL: `https://gcdonationhandler-10-26-xxx.a.run.app`

### 6.3 Post-Deployment Verification
- [ ] Test health endpoint: `curl https://gcdonationhandler-10-26-xxx.a.run.app/health`
- [ ] Verify response: `{"status": "healthy", "service": "GCDonationHandler", "version": "1.0"}`
- [ ] Check Cloud Logging for startup logs:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcdonationhandler-10-26" --limit 50
  ```
- [ ] Verify no errors in startup sequence
- [ ] Check service metrics in Cloud Console (request count, latency, error rate)

---

## Phase 7: Integration Testing

### 7.1 API Endpoint Testing
- [ ] Test /start-donation-input with curl:
  ```bash
  curl -X POST https://gcdonationhandler-10-26-xxx.a.run.app/start-donation-input \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": 6271402111,
      "chat_id": -1002345678901,
      "open_channel_id": "-1003268562225",
      "callback_query_id": "test_query_123"
    }'
  ```
- [ ] Verify response: `{"success": true, "message_id": 12345}`
- [ ] Test /keypad-input with digit press:
  ```bash
  curl -X POST https://gcdonationhandler-10-26-xxx.a.run.app/keypad-input \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": 6271402111,
      "callback_data": "donate_digit_5",
      "callback_query_id": "test_query_456"
    }'
  ```
- [ ] Test /broadcast-closed-channels:
  ```bash
  curl -X POST https://gcdonationhandler-10-26-xxx.a.run.app/broadcast-closed-channels \
    -H "Content-Type: application/json" \
    -d '{"force_resend": false}'
  ```
- [ ] Verify broadcast statistics in response

### 7.2 GCBotCommand Integration
- [ ] Update GCBotCommand to call GCDonationHandler endpoints (not part of this checklist, but document the integration points)
- [ ] Document the webhook flow:
  1. User clicks [💝 Donate] button in closed channel
  2. Telegram sends callback_query to GCBotCommand
  3. GCBotCommand extracts callback_data and forwards to GCDonationHandler /start-donation-input
  4. GCDonationHandler sends keypad message to user
  5. User interacts with keypad (each button press → GCBotCommand → GCDonationHandler /keypad-input)
  6. User confirms amount → GCDonationHandler creates payment invoice
- [ ] Test integration points manually with real Telegram bot

### 7.3 End-to-End User Flow Testing
- [ ] Open Telegram client
- [ ] Navigate to a closed channel where bot is admin
- [ ] Trigger broadcast: `curl -X POST https://gcdonationhandler-10-26-xxx.a.run.app/broadcast-closed-channels`
- [ ] Verify donation message appears in closed channel
- [ ] Click [💝 Donate] button
- [ ] Verify keypad message appears in private chat
- [ ] Enter donation amount using keypad (test digits, backspace, clear)
- [ ] Verify amount display updates in real-time
- [ ] Click [✅ Confirm & Pay]
- [ ] Verify confirmation message appears
- [ ] Verify payment gateway button appears
- [ ] Click payment button and verify NowPayments invoice opens
- [ ] Monitor Cloud Logging for all events

### 7.4 Error Handling Testing
- [ ] Test invalid channel ID: expect 400 error with message
- [ ] Test expired session: start keypad, wait 10 minutes, try to interact (expect session expired error)
- [ ] Test amount below minimum: enter $3.00, confirm (expect rejection)
- [ ] Test amount above maximum: enter $10000, confirm (expect rejection)
- [ ] Test invalid decimal places: enter $25.555 (expect rejection at third decimal)
- [ ] Test broadcast to channel where bot is kicked (expect error in broadcast response)

---

## Phase 8: Monitoring & Observability

### 8.1 Cloud Logging Configuration
- [ ] Verify logs are being written to Cloud Logging
- [ ] Create log-based metric for donation confirmations:
  - Metric name: `donation_confirmations`
  - Filter: `textPayload=~"Donation confirmed"`
- [ ] Create log-based metric for errors:
  - Metric name: `donation_handler_errors`
  - Filter: `severity=ERROR`
- [ ] Verify emoji prefixes are visible in logs (🔧, 💝, 🔢, etc.)

### 8.2 Cloud Monitoring Dashboard
- [ ] Create custom dashboard: "GCDonationHandler Monitoring"
- [ ] Add chart: Request count (broken down by endpoint)
- [ ] Add chart: Request latency (p50, p95, p99)
- [ ] Add chart: Error rate (%)
- [ ] Add chart: Container instance count
- [ ] Add chart: Memory utilization
- [ ] Add chart: CPU utilization
- [ ] Add chart: Custom metric - donation confirmations
- [ ] Add chart: Custom metric - error count

### 8.3 Alert Policy Configuration
- [ ] Create alert: "Error rate > 5%"
  - Condition: `error_rate > 0.05` for 5 minutes
  - Notification channel: Email or Slack
- [ ] Create alert: "Request latency p95 > 2s"
  - Condition: `request_latency_p95 > 2000ms` for 5 minutes
- [ ] Create alert: "No requests in 24 hours"
  - Condition: `request_count = 0` for 24 hours (indicates potential issue)

### 8.4 Trace Configuration (Optional)
- [ ] Enable Cloud Trace for request tracing
- [ ] Verify traces are being collected
- [ ] Analyze trace data for bottlenecks (database queries, API calls)

---

## Phase 9: Documentation Updates

### 9.1 Update PROGRESS.md
- [ ] Add entry to PROGRESS.md:
  ```markdown
  ## 2025-11-12 - GCDonationHandler Refactoring Complete
  - ✅ Created GCDonationHandler-10-26 service with 7 self-contained modules
  - ✅ Implemented donation keypad with validation (min $4.99, max $9999.99)
  - ✅ Integrated NowPayments gateway for invoice creation
  - ✅ Implemented broadcast manager for closed channels
  - ✅ Deployed to Cloud Run: gcdonationhandler-10-26
  - ✅ Configured IAM roles and Secret Manager access
  - ✅ Implemented comprehensive testing (unit, integration, E2E)
  - ✅ Set up monitoring dashboard and alerts
  ```

### 9.2 Update DECISIONS.md
- [ ] Add architectural decision to DECISIONS.md:
  ```markdown
  ## 2025-11-12 - Self-Contained Module Architecture
  **Decision:** Implemented GCDonationHandler with self-contained modules instead of shared libraries

  **Rationale:**
  - Each service contains its own copies of all required modules
  - Enables independent evolution without coordination overhead
  - Simplifies deployment (single container, no external dependencies)
  - Reduces risk of version conflicts across services

  **Trade-offs:**
  - Code duplication across services (acceptable for autonomy)
  - Bug fixes must be applied to each service (mitigated by clear documentation)
  ```

### 9.3 Update BUGS.md (if applicable)
- [ ] If any bugs were discovered during implementation, document them in BUGS.md
- [ ] Example format:
  ```markdown
  ## 2025-11-12 - GCDonationHandler Known Issues
  ### Bug: Session state lost on container restart
  - **Severity:** Medium
  - **Description:** User state stored in-memory is lost when container restarts
  - **Workaround:** Implement Redis for persistent state storage (future enhancement)
  - **Status:** Documented, not blocking for MVP
  ```

### 9.4 Create API Documentation
- [ ] Create `GCDonationHandler-10-26/API.md` file
- [ ] Document all endpoints with request/response examples
- [ ] Document callback_data patterns
- [ ] Document error codes and messages
- [ ] Include example curl commands

### 9.5 Create Deployment Guide
- [ ] Create `GCDonationHandler-10-26/DEPLOYMENT.md` file
- [ ] Document deployment steps
- [ ] Document rollback procedure
- [ ] Document monitoring and debugging procedures
- [ ] Include troubleshooting section

---

## Phase 10: Post-Deployment Validation

### 10.1 Production Smoke Tests
- [ ] Wait 24 hours after deployment
- [ ] Review Cloud Logging for any unexpected errors
- [ ] Check monitoring dashboard for anomalies
- [ ] Verify donation flow still works end-to-end
- [ ] Check database for new donation records (if applicable)

### 10.2 Performance Validation
- [ ] Review request latency metrics (p50, p95, p99)
- [ ] Verify latency is < 500ms for keypad operations
- [ ] Verify cold start time is < 3s
- [ ] Check memory usage (should be < 300MB)
- [ ] Check CPU usage (should be < 50% under normal load)

### 10.3 Cost Analysis
- [ ] Review Cloud Run billing after 1 week
- [ ] Compare actual costs to estimates (~$0.13/month)
- [ ] Optimize if costs are higher than expected

### 10.4 User Feedback Collection
- [ ] Monitor for user complaints about donation flow
- [ ] Check if keypad is rendering correctly on all devices
- [ ] Verify payment gateway integration is smooth
- [ ] Collect feedback on validation messages (are they clear?)

---

## Appendix A: Checklist Summary

**Total Tasks:** 180+

**By Phase:**
- Phase 1 (Setup): 14 tasks
- Phase 2 (Modules): 80+ tasks
- Phase 3 (Supporting): 12 tasks
- Phase 4 (Testing): 24 tasks
- Phase 5 (Prep): 15 tasks
- Phase 6 (Deploy): 9 tasks
- Phase 7 (Integration): 15 tasks
- Phase 8 (Monitoring): 11 tasks
- Phase 9 (Docs): 8 tasks
- Phase 10 (Validation): 8 tasks

**Critical Path:**
1. Setup → Config Manager → Database Manager → Telegram Client
2. Payment Gateway Manager → Keypad Handler → Broadcast Manager
3. Service.py (ties everything together)
4. Supporting files → Testing → Deployment

---

## Appendix B: Module Dependency Graph

```
service.py (Flask App)
├── config_manager.py (no dependencies)
├── database_manager.py (no dependencies)
├── telegram_client.py (no dependencies)
├── keypad_handler.py
│   ├── uses database_manager (passed as dependency)
│   ├── uses telegram_client (passed as dependency)
│   └── creates payment_gateway_manager internally
├── payment_gateway_manager.py (no dependencies)
└── broadcast_manager.py
    ├── uses database_manager (passed as dependency)
    └── uses telegram_client (passed as dependency)
```

**Key Insight:** Only `service.py` imports other internal modules. All other modules are self-contained and accept dependencies via constructor injection.

---

## Appendix C: Validation Rules Reference

### Keypad Amount Validation
1. **Replace leading zero:** `"0" + "5" → "5"` (not "05")
2. **Single decimal point:** Reject second "." if one already exists
3. **Max 2 decimal places:** Reject digit after "XX.YY" format
4. **Max 4 digits before decimal:** Reject fifth digit in "9999" (max $9999.99)
5. **Minimum amount:** $4.99 on confirm
6. **Maximum amount:** $9999.99 on confirm

### Callback Data Patterns
- `donate_digit_0` through `donate_digit_9` - Digit buttons
- `donate_digit_.` - Decimal point button
- `donate_backspace` - Delete last character
- `donate_clear` - Reset to $0.00
- `donate_confirm` - Validate and create payment invoice
- `donate_cancel` - Abort donation flow
- `donate_noop` - Display button (amount display, no action)
- `donate_start_{open_channel_id}` - Initial donate button in closed channels

---

## Appendix D: Secret Manager Paths

All secrets use the format: `projects/telepay-459221/secrets/{SECRET_NAME}/versions/latest`

**Required Secrets:**
- `telegram-bot-token` - Telegram bot API token
- `database-host` - PostgreSQL host (Cloud SQL connection name)
- `database-name` - Database name (telepaydb)
- `database-user` - Database user (postgres)
- `database-password` - Database password
- `nowpayments-api-key` - NowPayments API key
- `nowpayments-ipn-url` - IPN callback URL

---

## Appendix E: Testing Checklist Quick Reference

**Unit Tests (70% coverage target):**
- [ ] test_keypad_handler.py - 10 tests
- [ ] test_payment_gateway.py - 4 tests
- [ ] test_database_manager.py - 4 tests

**Integration Tests (20% coverage target):**
- [ ] test_integration.py - 6 tests

**End-to-End Tests (10% coverage target):**
- [ ] test_e2e.py - 2 tests

**Total Tests:** 26 tests minimum

---

**End of Checklist**

**Status:** Ready for implementation
**Estimated Time:** 12-16 hours (for experienced developer)
**Priority:** High (blocks other webhook service refactoring)
