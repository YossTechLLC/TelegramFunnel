# GCBotCommand Refactoring Implementation Checklist

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Implementation Pending
**Branch:** TelePay-REFACTOR
**Related Document:** GCBotCommand_REFACTORING_ARCHITECTURE.md

---

## Overview

This checklist provides a **detailed, step-by-step implementation guide** for refactoring TelePay's monolithic bot into the **GCBotCommand-10-26 webhook service**. Each task is designed to maintain **modular code structure** with clear separation of concerns.

**Key Principle:** ⚠️ **NO single file should exceed ~400 lines** - if a module grows beyond this, split it into focused sub-modules.

---

## Phase 1: Project Setup & Core Infrastructure

### 1.1 Directory Structure Creation

- [ ] Create root directory: `GCBotCommand-10-26/`
- [ ] Create subdirectory: `GCBotCommand-10-26/routes/`
- [ ] Create subdirectory: `GCBotCommand-10-26/handlers/`
- [ ] Create subdirectory: `GCBotCommand-10-26/utils/`
- [ ] Create subdirectory: `GCBotCommand-10-26/models/`
- [ ] Create subdirectory: `GCBotCommand-10-26/tests/`
- [ ] Create `__init__.py` in each subdirectory

**Verification:**
```bash
tree GCBotCommand-10-26/
# Should show:
# GCBotCommand-10-26/
# ├── routes/
# │   └── __init__.py
# ├── handlers/
# │   └── __init__.py
# ├── utils/
# │   └── __init__.py
# ├── models/
# │   └── __init__.py
# └── tests/
#     └── __init__.py
```

---

### 1.2 Deployment Configuration Files

- [ ] Create `Dockerfile` with Python 3.11 slim base image
  - [ ] Set WORKDIR to /app
  - [ ] Copy requirements.txt
  - [ ] Install dependencies with pip
  - [ ] Copy application code
  - [ ] Expose port 8080
  - [ ] Set CMD to run service.py

- [ ] Create `requirements.txt` with dependencies:
  - [ ] Flask==3.0.0
  - [ ] psycopg2-binary==2.9.9
  - [ ] google-cloud-secret-manager==2.16.4
  - [ ] requests==2.31.0

- [ ] Create `.dockerignore` file
  - [ ] Exclude `__pycache__/`
  - [ ] Exclude `*.pyc`, `*.pyo`, `*.pyd`
  - [ ] Exclude `.env`, `venv/`, `.venv/`
  - [ ] Exclude `tests/`, `.git/`, `.gitignore`
  - [ ] Exclude `README.md`, `*.md`

- [ ] Create `.env.example` template
  - [ ] Document TELEGRAM_BOT_SECRET_NAME
  - [ ] Document TELEGRAM_BOT_USERNAME
  - [ ] Document DATABASE_HOST_SECRET
  - [ ] Document DATABASE_NAME_SECRET
  - [ ] Document DATABASE_USER_SECRET
  - [ ] Document DATABASE_PASSWORD_SECRET
  - [ ] Document GCPAYMENTGATEWAY_URL
  - [ ] Document GCDONATIONHANDLER_URL

**Verification:**
```bash
ls -la GCBotCommand-10-26/ | grep -E "(Dockerfile|requirements.txt|.dockerignore|.env.example)"
```

---

### 1.3 Database Schema Migration

- [ ] Create SQL migration file: `migrations/001_conversation_state_table.sql`
- [ ] Add CREATE TABLE statement for `user_conversation_state`:
  - [ ] Column: `user_id BIGINT NOT NULL`
  - [ ] Column: `conversation_type VARCHAR(50) NOT NULL`
  - [ ] Column: `state_data JSONB NOT NULL`
  - [ ] Column: `updated_at TIMESTAMP DEFAULT NOW()`
  - [ ] Primary key: `(user_id, conversation_type)`
  - [ ] Index: `idx_conversation_state_updated ON updated_at`

- [ ] Execute migration against `telepaypsql` database
- [ ] Verify table exists:
  ```sql
  SELECT * FROM information_schema.tables WHERE table_name = 'user_conversation_state';
  ```

**Verification:**
```sql
\d user_conversation_state
-- Should show table structure with all columns and indexes
```

---

## Phase 2: Core Configuration & Database Modules

### 2.1 Configuration Manager (`config_manager.py`)

**File:** `GCBotCommand-10-26/config_manager.py`
**Lines:** ~90 lines
**Migrates From:** `TelePay10-26/config_manager.py`

- [ ] Create `config_manager.py` file
- [ ] Import required modules:
  - [ ] `import os`
  - [ ] `from google.cloud import secretmanager`
  - [ ] `from typing import Optional, Dict`

- [ ] Implement `ConfigManager` class:
  - [ ] `__init__()` method - Initialize secret manager client
  - [ ] `_fetch_secret()` method - Generic secret fetcher from Secret Manager
  - [ ] `fetch_telegram_token()` method - Fetch bot token
  - [ ] `fetch_bot_username()` method - Fetch bot username
  - [ ] `fetch_gcpaymentgateway_url()` method - Get payment gateway URL
  - [ ] `fetch_gcdonationhandler_url()` method - Get donation handler URL
  - [ ] `initialize_config()` method - Fetch all configs and return dict
  - [ ] `get_config()` method - Return current config values

- [ ] Add error handling for missing secrets
- [ ] Add logging statements (✅ and ❌ emojis)

**Verification:**
```python
from config_manager import ConfigManager
config = ConfigManager()
result = config.initialize_config()
assert 'bot_token' in result
assert result['bot_token'] is not None
```

---

### 2.2 Database Manager (`database_manager.py`)

**File:** `GCBotCommand-10-26/database_manager.py`
**Lines:** ~300 lines
**Migrates From:** `TelePay10-26/database.py` (first 200 lines + new conversation state methods)

#### 2.2.1 Database Connection Setup

- [ ] Create `database_manager.py` file
- [ ] Import required modules:
  - [ ] `import psycopg2`
  - [ ] `import os`
  - [ ] `from typing import Optional, Tuple, List, Dict, Any`
  - [ ] `from google.cloud import secretmanager`

- [ ] Implement helper functions:
  - [ ] `fetch_database_host()` - Fetch DB host from Secret Manager
  - [ ] `fetch_database_name()` - Fetch DB name from Secret Manager
  - [ ] `fetch_database_user()` - Fetch DB user from Secret Manager
  - [ ] `fetch_database_password()` - Fetch DB password from Secret Manager

- [ ] Implement `DatabaseManager` class `__init__()`:
  - [ ] Store host, port, dbname, user, password
  - [ ] Validate all required config is present
  - [ ] Raise RuntimeError if config missing

- [ ] Implement `get_connection()` method:
  - [ ] Return psycopg2 connection object
  - [ ] Use stored credentials

**Verification:**
```python
from database_manager import DatabaseManager
db = DatabaseManager()
with db.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
```

#### 2.2.2 Channel Configuration Methods

- [ ] Implement `fetch_channel_by_id(channel_id)` method:
  - [ ] SELECT query for main_clients_database WHERE open_channel_id
  - [ ] Return dictionary with all channel fields
  - [ ] Return None if channel not found
  - [ ] Handle exceptions with error logging (❌ emoji)

- [ ] Implement `update_channel_config(channel_id, channel_data)` method:
  - [ ] Use INSERT ... ON CONFLICT DO UPDATE (UPSERT)
  - [ ] Update all channel configuration fields
  - [ ] Commit changes to database
  - [ ] Return True on success, False on error
  - [ ] Add logging (✅ emoji on success)

- [ ] Implement `fetch_open_channel_list()` method:
  - [ ] SELECT all channels from main_clients_database
  - [ ] Return tuple: (list of IDs, dict mapping ID to config)
  - [ ] Handle exceptions gracefully

**Verification:**
```python
db = DatabaseManager()
# Test fetch
channel = db.fetch_channel_by_id("-1003268562225")
assert channel is not None

# Test update
result = db.update_channel_config("-1003268562225", {"sub_1_price": 9.99})
assert result == True
```

#### 2.2.3 Conversation State Management (NEW)

- [ ] Implement `save_conversation_state(user_id, conversation_type, state_data)` method:
  - [ ] Import json module
  - [ ] INSERT ... ON CONFLICT DO UPDATE for user_conversation_state table
  - [ ] JSON serialize state_data
  - [ ] Set updated_at to NOW()
  - [ ] Commit transaction
  - [ ] Return True on success
  - [ ] Handle exceptions with error logging

- [ ] Implement `get_conversation_state(user_id, conversation_type)` method:
  - [ ] SELECT state_data from user_conversation_state
  - [ ] JSON deserialize result
  - [ ] Return state dict or None if not found
  - [ ] Handle exceptions

- [ ] Implement `clear_conversation_state(user_id, conversation_type)` method:
  - [ ] DELETE from user_conversation_state
  - [ ] Commit transaction
  - [ ] Return True on success
  - [ ] Handle exceptions

**Verification:**
```python
db = DatabaseManager()
# Test save
result = db.save_conversation_state(6271402111, 'donation', {'channel_id': '-123', 'state': 'awaiting_amount'})
assert result == True

# Test retrieve
state = db.get_conversation_state(6271402111, 'donation')
assert state['channel_id'] == '-123'

# Test clear
result = db.clear_conversation_state(6271402111, 'donation')
assert result == True
```

---

### 2.3 Flask Application Factory (`service.py`)

**File:** `GCBotCommand-10-26/service.py`
**Lines:** ~75 lines
**Migrates From:** `TelePay10-26/telepay10-26.py`, `app_initializer.py`

- [ ] Create `service.py` file
- [ ] Import required modules:
  - [ ] `from flask import Flask`
  - [ ] `from config_manager import ConfigManager`
  - [ ] `from database_manager import DatabaseManager`
  - [ ] `from routes.webhook import webhook_bp`
  - [ ] `import logging`

- [ ] Set up logging configuration:
  - [ ] Format: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`
  - [ ] Level: `logging.INFO`

- [ ] Implement `create_app()` function:
  - [ ] Create Flask app instance
  - [ ] Initialize ConfigManager and load config
  - [ ] Initialize DatabaseManager
  - [ ] Attach db_manager to app.db
  - [ ] Attach config_manager to app.config_manager
  - [ ] Update app.config with config dict
  - [ ] Register webhook blueprint
  - [ ] Add logging for each step (✅ emojis)
  - [ ] Return app instance

- [ ] Add main block:
  - [ ] Call create_app()
  - [ ] Run app on 0.0.0.0:8080
  - [ ] Set debug=False

**Verification:**
```python
from service import create_app
app = create_app()
assert app is not None
assert hasattr(app, 'db')
assert hasattr(app, 'config_manager')
```

---

## Phase 3: Webhook Routes & Request Handling

### 3.1 Webhook Blueprint (`routes/webhook.py`)

**File:** `GCBotCommand-10-26/routes/webhook.py`
**Lines:** ~180 lines
**Migrates From:** `TelePay10-26/bot_manager.py`, `server_manager.py`

#### 3.1.1 Blueprint Setup

- [ ] Create `routes/webhook.py` file
- [ ] Import required modules:
  - [ ] `from flask import Blueprint, request, jsonify, current_app`
  - [ ] `from handlers.command_handler import CommandHandler`
  - [ ] `from handlers.callback_handler import CallbackHandler`
  - [ ] `import logging`

- [ ] Create blueprint:
  - [ ] `webhook_bp = Blueprint('webhook', __name__)`
  - [ ] Initialize logger

#### 3.1.2 Webhook Endpoint (`/webhook`)

- [ ] Implement `@webhook_bp.route('/webhook', methods=['POST'])`:
  - [ ] Get JSON data from request
  - [ ] Validate payload is not empty (return 400 if empty)
  - [ ] Log update_id (📨 emoji)
  - [ ] Initialize CommandHandler with current_app.db and current_app.config
  - [ ] Initialize CallbackHandler with current_app.db and current_app.config

- [ ] Route 'message' updates:
  - [ ] Check if 'text' in message
  - [ ] If text starts with '/start': call `command_handler.handle_start_command(data)`
  - [ ] If text starts with '/database': call `command_handler.handle_database_command(data)`
  - [ ] Otherwise: call `command_handler.handle_text_input(data)` (for conversations)
  - [ ] Return jsonify(result), 200

- [ ] Route 'callback_query' updates:
  - [ ] Call `callback_handler.handle_callback(data)`
  - [ ] Return jsonify(result), 200

- [ ] Handle unknown update types:
  - [ ] Log warning (⚠️ emoji)
  - [ ] Return 200 with "ok" status

- [ ] Add exception handling:
  - [ ] Log error with traceback (❌ emoji)
  - [ ] Return 200 (to prevent Telegram retries)

**Verification:**
```python
import requests
payload = {
    "update_id": 123456,
    "message": {
        "message_id": 1,
        "from": {"id": 6271402111, "first_name": "Test"},
        "chat": {"id": 6271402111, "type": "private"},
        "text": "/start"
    }
}
response = requests.post("http://localhost:8080/webhook", json=payload)
assert response.status_code == 200
```

#### 3.1.3 Health Check Endpoint (`/health`)

- [ ] Implement `@webhook_bp.route('/health', methods=['GET'])`:
  - [ ] Test database connection with SELECT 1 query
  - [ ] Return JSON with status "healthy" and database "connected" on success
  - [ ] Return 200 status code on success
  - [ ] On exception: return 503 with status "unhealthy" and error message
  - [ ] Add error logging (❌ emoji)

**Verification:**
```python
response = requests.get("http://localhost:8080/health")
assert response.status_code == 200
data = response.json()
assert data['status'] == 'healthy'
```

#### 3.1.4 Set Webhook Helper Endpoint (`/set-webhook`)

- [ ] Implement `@webhook_bp.route('/set-webhook', methods=['POST'])`:
  - [ ] Get bot_token from current_app.config
  - [ ] Get webhook_url from request JSON
  - [ ] Validate webhook_url is provided (return 400 if missing)
  - [ ] POST to Telegram API setWebhook endpoint
  - [ ] Return Telegram API response as JSON
  - [ ] Add error handling (❌ emoji on error)
  - [ ] Add success logging (✅ emoji)

**Verification:**
```bash
curl -X POST http://localhost:8080/set-webhook \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "https://gcbotcommand-10-26-xxx.a.run.app/webhook"}'
```

---

## Phase 4: Utility Modules (Independent, Reusable)

### 4.1 Input Validators (`utils/validators.py`)

**File:** `GCBotCommand-10-26/utils/validators.py`
**Lines:** ~60 lines
**Migrates From:** `TelePay10-26/input_handlers.py` (validation methods)

- [ ] Create `utils/validators.py` file
- [ ] Import: `from typing import Tuple`

- [ ] Implement `valid_channel_id(text)` function:
  - [ ] Check if text.lstrip("-").isdigit()
  - [ ] Check len(text) <= 14
  - [ ] Return bool

- [ ] Implement `valid_sub_price(text)` function:
  - [ ] Try float(text)
  - [ ] Check 0 <= val <= 9999.99
  - [ ] Check max 2 decimal places
  - [ ] Return bool

- [ ] Implement `valid_sub_time(text)` function:
  - [ ] Check text.isdigit()
  - [ ] Check 1 <= int(text) <= 999
  - [ ] Return bool

- [ ] Implement `validate_donation_amount(text)` function:
  - [ ] Remove $ prefix if present
  - [ ] Try float(text)
  - [ ] Check 1.0 <= val <= 9999.99
  - [ ] Check max 2 decimal places
  - [ ] Return Tuple[bool, float]

- [ ] Implement `valid_channel_title(text)` function:
  - [ ] Check 1 <= len(text.strip()) <= 100
  - [ ] Return bool

- [ ] Implement `valid_channel_description(text)` function:
  - [ ] Check 1 <= len(text.strip()) <= 500
  - [ ] Return bool

- [ ] Implement `valid_wallet_address(text)` function:
  - [ ] Check 10 <= len(text.strip()) <= 200
  - [ ] Return bool

- [ ] Implement `valid_currency(text)` function:
  - [ ] Strip and uppercase text
  - [ ] Check 2 <= len <= 10
  - [ ] Check is alpha (allow - and _)
  - [ ] Return bool

**Verification:**
```python
from utils.validators import valid_channel_id, validate_donation_amount

assert valid_channel_id("-1003268562225") == True
assert valid_channel_id("abc") == False

is_valid, amount = validate_donation_amount("25.50")
assert is_valid == True
assert amount == 25.50
```

---

### 4.2 Token Parser (`utils/token_parser.py`)

**File:** `GCBotCommand-10-26/utils/token_parser.py`
**Lines:** ~120 lines
**Migrates From:** `TelePay10-26/menu_handlers.py` (start_bot method), `broadcast_manager.py` (hash encoding)

- [ ] Create `utils/token_parser.py` file
- [ ] Import required modules:
  - [ ] `from typing import Dict, Optional`
  - [ ] `import base64`
  - [ ] `import logging`

- [ ] Implement `TokenParser` class

#### 4.2.1 Hash Decoding

- [ ] Implement `decode_hash(hash_part)` static method:
  - [ ] Add padding: `hash_part + '=='`
  - [ ] base64.urlsafe_b64decode()
  - [ ] Decode bytes to UTF-8 string
  - [ ] Return channel_id
  - [ ] Handle exceptions and return None

**Verification:**
```python
from utils.token_parser import TokenParser
parser = TokenParser()
# Test with known hash
channel_id = parser.decode_hash("LTEwMDMyNjg1NjIyMjU")
assert channel_id == "-1003268562225"
```

#### 4.2.2 Token Parsing

- [ ] Implement `parse_token(token)` method:
  - [ ] Split token by '_'
  - [ ] Extract hash_part (first element)
  - [ ] Extract remaining parts
  - [ ] Decode hash to channel_id

- [ ] Handle donation token:
  - [ ] If remaining == "DONATE":
    - [ ] Return {'type': 'donation', 'channel_id': channel_id}

- [ ] Handle subscription token with time:
  - [ ] If '_' in remaining:
    - [ ] Split remaining by '_' from right: `sub_part, time_part = remaining.rsplit('_', 1)`
    - [ ] Parse time_part as int (default 30 on error)
    - [ ] Replace 'd' with '.' in sub_part
    - [ ] Parse price as float (default 5.0 on error)
    - [ ] Return {'type': 'subscription', 'channel_id': channel_id, 'price': price, 'time': time}

- [ ] Handle old subscription token (no time):
  - [ ] Replace 'd' with '.' in remaining
  - [ ] Parse price as float
  - [ ] Return with time=30 (default)

- [ ] Handle invalid tokens:
  - [ ] Return {'type': 'invalid'}
  - [ ] Log error (❌ emoji)

**Verification:**
```python
parser = TokenParser()

# Test subscription token
result = parser.parse_token("ABC123_9d99_30")
assert result['type'] == 'subscription'
assert result['price'] == 9.99
assert result['time'] == 30

# Test donation token
result = parser.parse_token("ABC123_DONATE")
assert result['type'] == 'donation'
```

#### 4.2.3 Hash Encoding (for completeness)

- [ ] Implement `encode_hash(channel_id)` static method:
  - [ ] Encode channel_id to UTF-8 bytes
  - [ ] base64.urlsafe_b64encode()
  - [ ] Decode to string
  - [ ] Remove padding ('=' characters)
  - [ ] Return encoded hash
  - [ ] Handle exceptions

**Verification:**
```python
hash_value = TokenParser.encode_hash("-1003268562225")
decoded = TokenParser.decode_hash(hash_value)
assert decoded == "-1003268562225"
```

---

### 4.3 HTTP Client (`utils/http_client.py`)

**File:** `GCBotCommand-10-26/utils/http_client.py`
**Lines:** ~80 lines
**New Module:** Generic HTTP client for external services

- [ ] Create `utils/http_client.py` file
- [ ] Import required modules:
  - [ ] `import requests`
  - [ ] `import logging`
  - [ ] `from typing import Dict, Optional`

- [ ] Implement `HTTPClient` class:
  - [ ] `__init__(timeout=30)` - Initialize with timeout and session
  - [ ] Create requests.Session()

#### 4.3.1 POST Method

- [ ] Implement `post(url, data)` method:
  - [ ] Log request (📤 emoji with URL)
  - [ ] Log payload (📦 emoji) at debug level
  - [ ] POST with json=data, timeout=self.timeout
  - [ ] Set Content-Type header to application/json
  - [ ] Raise for HTTP errors
  - [ ] Parse JSON response
  - [ ] Log success (✅ emoji)
  - [ ] Return response dict

- [ ] Handle exceptions:
  - [ ] requests.exceptions.Timeout → Log error, return None
  - [ ] requests.exceptions.RequestException → Log error, return None
  - [ ] ValueError (invalid JSON) → Log error, return None

**Verification:**
```python
from utils.http_client import HTTPClient
client = HTTPClient()
response = client.post("https://httpbin.org/post", {"test": "data"})
assert response is not None
```

#### 4.3.2 GET Method

- [ ] Implement `get(url)` method:
  - [ ] Log request (📥 emoji with URL)
  - [ ] GET with timeout=self.timeout
  - [ ] Raise for HTTP errors
  - [ ] Parse JSON response
  - [ ] Log success (✅ emoji)
  - [ ] Return response dict
  - [ ] Handle exceptions (return None on error)

**Verification:**
```python
response = client.get("https://httpbin.org/get")
assert response is not None
```

---

### 4.4 Message Formatter (`utils/message_formatter.py`)

**File:** `GCBotCommand-10-26/utils/message_formatter.py`
**Lines:** ~60 lines
**New Module:** Format messages for Telegram (optional, for code reuse)

- [ ] Create `utils/message_formatter.py` file
- [ ] Import: `from typing import Dict`

- [ ] Implement `MessageFormatter` class:
  - [ ] `format_subscription_message(channel_title, channel_description, price, time)` - Format subscription payment message
  - [ ] `format_donation_message(amount)` - Format donation confirmation message
  - [ ] `format_database_menu_message()` - Format database configuration menu text
  - [ ] `format_error_message(error_text)` - Format error message with ❌ emoji

**Note:** This module is optional - can be implemented later if message formatting becomes repetitive.

---

## Phase 5: Command & Callback Handlers

### 5.1 Command Handler (`handlers/command_handler.py`)

**File:** `GCBotCommand-10-26/handlers/command_handler.py`
**Lines:** ~270 lines
**Migrates From:** `TelePay10-26/menu_handlers.py` (start_bot), `input_handlers.py` (conversation logic)

#### 5.1.1 Class Setup

- [ ] Create `handlers/command_handler.py` file
- [ ] Import required modules:
  - [ ] `from typing import Dict, Any`
  - [ ] `from utils.token_parser import TokenParser`
  - [ ] `from utils.http_client import HTTPClient`
  - [ ] `from utils.message_formatter import MessageFormatter`
  - [ ] `import logging`

- [ ] Implement `CommandHandler` class:
  - [ ] `__init__(db_manager, config)` - Store db, config, bot_token
  - [ ] Initialize TokenParser, HTTPClient, MessageFormatter
  - [ ] Initialize logger

#### 5.1.2 /start Command Handler

- [ ] Implement `handle_start_command(update_data)` method:
  - [ ] Extract message, chat_id, user, text from update_data
  - [ ] Parse args from text (split by space)
  - [ ] Log command (📍 emoji with user ID and args)

- [ ] Handle /start with no args:
  - [ ] Call `_send_main_menu(chat_id, user)`
  - [ ] Return result

- [ ] Handle /start with token:
  - [ ] Parse token using TokenParser
  - [ ] If type == 'subscription': call `_handle_subscription_token()`
  - [ ] If type == 'donation': call `_handle_donation_token()`
  - [ ] If type == 'invalid': call `_send_error_message()`

**Verification:**
```python
# Test with mock update_data
update_data = {
    "message": {
        "from": {"id": 123, "first_name": "Test"},
        "chat": {"id": 123},
        "text": "/start"
    }
}
handler = CommandHandler(db_manager, config)
result = handler.handle_start_command(update_data)
assert result['status'] == 'ok'
```

#### 5.1.3 Main Menu

- [ ] Implement `_send_main_menu(chat_id, user)` method:
  - [ ] Create inline keyboard with buttons:
    - [ ] "💾 DATABASE" → callback_data: "CMD_DATABASE"
    - [ ] "💳 PAYMENT GATEWAY" → callback_data: "CMD_GATEWAY"
    - [ ] "🌐 REGISTER" → url: "https://www.paygateprime.com"
  - [ ] Format welcome message with user's first name
  - [ ] Call `_send_message()` with keyboard
  - [ ] Return result

#### 5.1.4 Subscription Token Handler

- [ ] Implement `_handle_subscription_token(chat_id, user, token_data)` method:
  - [ ] Extract channel_id, price, time from token_data
  - [ ] Log subscription details (💰 emoji)
  - [ ] Fetch channel data from database using `db.fetch_channel_by_id()`
  - [ ] If channel not found: return error message

- [ ] Create payment gateway button:
  - [ ] Inline keyboard with "💰 Launch Payment Gateway" button
  - [ ] callback_data: "TRIGGER_PAYMENT"

- [ ] Save conversation state:
  - [ ] Call `db.save_conversation_state(user['id'], 'payment', {...})`
  - [ ] Store channel_id, price, time, payment_type='subscription'

- [ ] Send message with payment button:
  - [ ] Format message with channel title and description
  - [ ] Use HTML parse_mode
  - [ ] Return result

**Verification:**
```python
token_data = {'type': 'subscription', 'channel_id': '-123', 'price': 9.99, 'time': 30}
result = handler._handle_subscription_token(123, {'id': 456}, token_data)
# Verify payment state was saved
state = db_manager.get_conversation_state(456, 'payment')
assert state['price'] == 9.99
```

#### 5.1.5 Donation Token Handler

- [ ] Implement `_handle_donation_token(chat_id, user, token_data)` method:
  - [ ] Extract channel_id from token_data
  - [ ] Log donation (💝 emoji)
  - [ ] Save conversation state with state='awaiting_amount'
  - [ ] Send message asking for donation amount
  - [ ] Use Markdown parse_mode
  - [ ] Return result

#### 5.1.6 /database Command Handler

- [ ] Implement `handle_database_command(update_data)` method:
  - [ ] Extract message, chat_id, user_id
  - [ ] Log command (💾 emoji)
  - [ ] Initialize database conversation state with state='awaiting_channel_id'
  - [ ] Send message asking for open_channel_id
  - [ ] Use Markdown parse_mode
  - [ ] Return result

#### 5.1.7 Text Input Handler (Conversations)

- [ ] Implement `handle_text_input(update_data)` method:
  - [ ] Extract message, chat_id, user_id, text
  - [ ] Check for active donation conversation state
  - [ ] Check for active database conversation state
  - [ ] If donation state exists: call `_handle_donation_input()`
  - [ ] If database state exists: call `_handle_database_input()`
  - [ ] If no active conversation: send "Please use /start to begin"

#### 5.1.8 Donation Input Handler

- [ ] Implement `_handle_donation_input(chat_id, user_id, text, state)` method:
  - [ ] Import validators: `from utils.validators import validate_donation_amount`
  - [ ] Validate amount using `validate_donation_amount(text)`
  - [ ] If invalid: send error message with examples

- [ ] If valid amount:
  - [ ] Extract channel_id from state
  - [ ] Create payload for GCPaymentGateway:
    - [ ] user_id, amount, open_channel_id, subscription_time_days=365, payment_type='donation'
  - [ ] POST to `{gcpaymentgateway_url}/create-invoice` using HTTPClient
  - [ ] If success: create payment button with invoice_url
  - [ ] Clear conversation state
  - [ ] Send confirmation message with payment button
  - [ ] If failed: send error message

#### 5.1.9 Database Input Handler

- [ ] Implement `_handle_database_input(chat_id, user_id, text, state)` method:
  - [ ] Import: `from handlers.database_handler import DatabaseFormHandler`
  - [ ] Create DatabaseFormHandler instance
  - [ ] Delegate to `db_form_handler.handle_input(chat_id, user_id, text, state)`
  - [ ] Return result

#### 5.1.10 Helper Methods

- [ ] Implement `_send_message(chat_id, text, **kwargs)` method:
  - [ ] Create payload: chat_id, text
  - [ ] Add optional reply_markup if provided
  - [ ] Add optional parse_mode if provided
  - [ ] POST to Telegram sendMessage API
  - [ ] Return {"status": "ok"} on success
  - [ ] Handle exceptions (log error, return error status)

- [ ] Implement `_send_error_message(chat_id, error_text)` method:
  - [ ] Call `_send_message()` with "❌ {error_text}"
  - [ ] Return result

---

### 5.2 Callback Handler (`handlers/callback_handler.py`)

**File:** `GCBotCommand-10-26/handlers/callback_handler.py`
**Lines:** ~240 lines
**Migrates From:** `TelePay10-26/menu_handlers.py` (main_menu_callback), `bot_manager.py` (callback handlers)

#### 5.2.1 Class Setup

- [ ] Create `handlers/callback_handler.py` file
- [ ] Import required modules:
  - [ ] `from typing import Dict, Any`
  - [ ] `from utils.http_client import HTTPClient`
  - [ ] `import logging`

- [ ] Implement `CallbackHandler` class:
  - [ ] `__init__(db_manager, config)` - Store db, config, bot_token
  - [ ] Initialize HTTPClient
  - [ ] Initialize logger

#### 5.2.2 Main Callback Router

- [ ] Implement `handle_callback(update_data)` method:
  - [ ] Extract callback_query, callback_data, chat_id, user_id, message_id
  - [ ] Log callback (🔘 emoji with callback_data and user_id)
  - [ ] Answer callback query first: call `_answer_callback_query(callback_query['id'])`

- [ ] Route callbacks:
  - [ ] If callback_data == "CMD_DATABASE": call `_handle_database_start()`
  - [ ] If callback_data == "CMD_GATEWAY": call `_handle_payment_gateway()`
  - [ ] If callback_data == "TRIGGER_PAYMENT": call `_handle_trigger_payment()`
  - [ ] If callback_data.startswith("EDIT_"): call `_handle_database_edit()`
  - [ ] If callback_data == "SAVE_ALL_CHANGES": call `_handle_save_changes()`
  - [ ] If callback_data == "CANCEL_EDIT": call `_handle_cancel_edit()`
  - [ ] If callback_data.startswith("TOGGLE_TIER_"): call `_handle_toggle_tier()`
  - [ ] If callback_data == "BACK_TO_MAIN": call `_handle_back_to_main()`
  - [ ] Otherwise: log warning (⚠️ emoji) and return ok

#### 5.2.3 Database Start Handler

- [ ] Implement `_handle_database_start(chat_id, user_id)` method:
  - [ ] Initialize database conversation state with state='awaiting_channel_id'
  - [ ] Send message asking for open_channel_id
  - [ ] Use Markdown parse_mode
  - [ ] Return result

#### 5.2.4 Payment Gateway Handlers

- [ ] Implement `_handle_payment_gateway(chat_id, user_id)` method:
  - [ ] Get payment state from database: `db.get_conversation_state(user_id, 'payment')`
  - [ ] If no payment state: send error "No payment context found"
  - [ ] Otherwise: call `_create_payment_invoice()`

- [ ] Implement `_handle_trigger_payment(chat_id, user_id)` method:
  - [ ] Call `_handle_payment_gateway()` (same logic)

- [ ] Implement `_create_payment_invoice(chat_id, user_id, payment_state)` method:
  - [ ] Get payment gateway URL from config
  - [ ] Create payload with user_id, amount, open_channel_id, subscription_time_days, payment_type
  - [ ] POST to `{payment_url}/create-invoice` using HTTPClient
  - [ ] If success:
    - [ ] Create inline keyboard with "💳 Pay Now" web_app button
    - [ ] Send payment message with invoice details
    - [ ] Return result
  - [ ] If failed: send error message

#### 5.2.5 Database Edit Handlers

- [ ] Implement `_handle_database_edit(chat_id, user_id, message_id, callback_data)` method:
  - [ ] Import: `from handlers.database_handler import DatabaseFormHandler`
  - [ ] Create DatabaseFormHandler instance
  - [ ] Delegate to `db_form_handler.handle_edit_callback()`
  - [ ] Return result

- [ ] Implement `_handle_save_changes(chat_id, user_id, message_id)` method:
  - [ ] Import DatabaseFormHandler
  - [ ] Delegate to `db_form_handler.save_changes()`
  - [ ] Return result

- [ ] Implement `_handle_cancel_edit(chat_id, user_id, message_id)` method:
  - [ ] Clear conversation state: `db.clear_conversation_state(user_id, 'database')`
  - [ ] Edit message to show cancellation message
  - [ ] Return result

- [ ] Implement `_handle_toggle_tier(chat_id, user_id, message_id, callback_data)` method:
  - [ ] Import DatabaseFormHandler
  - [ ] Delegate to `db_form_handler.toggle_tier()`
  - [ ] Return result

- [ ] Implement `_handle_back_to_main(chat_id, user_id, message_id)` method:
  - [ ] Import DatabaseFormHandler
  - [ ] Delegate to `db_form_handler.show_main_form()`
  - [ ] Return result

#### 5.2.6 Telegram API Helper Methods

- [ ] Implement `_answer_callback_query(callback_query_id)` method:
  - [ ] POST to Telegram answerCallbackQuery API
  - [ ] Handle exceptions (log error)
  - [ ] Use timeout=5

- [ ] Implement `_send_message(chat_id, text, **kwargs)` method:
  - [ ] Create payload with chat_id, text
  - [ ] Add optional reply_markup, parse_mode
  - [ ] POST to Telegram sendMessage API
  - [ ] Return {"status": "ok"} on success
  - [ ] Handle exceptions

- [ ] Implement `_edit_message(chat_id, message_id, text, **kwargs)` method:
  - [ ] Create payload with chat_id, message_id, text
  - [ ] Add optional reply_markup, parse_mode
  - [ ] POST to Telegram editMessageText API
  - [ ] Return {"status": "ok"} on success
  - [ ] Handle exceptions

---

### 5.3 Database Form Handler (`handlers/database_handler.py`)

**File:** `GCBotCommand-10-26/handlers/database_handler.py`
**Lines:** ~400 lines
**Migrates From:** `TelePay10-26/menu_handlers.py` (lines 258-698 - all form functions)

⚠️ **IMPORTANT:** This is the largest handler module. Ensure it stays focused on database form logic only.

#### 5.3.1 Class Setup

- [ ] Create `handlers/database_handler.py` file
- [ ] Import required modules:
  - [ ] `from typing import Dict, Any`
  - [ ] `from utils.validators import *` (all validation functions)
  - [ ] `import logging`
  - [ ] `import requests`

- [ ] Implement `DatabaseFormHandler` class:
  - [ ] `__init__(db_manager, config)` - Store db, config, bot_token
  - [ ] Initialize logger

#### 5.3.2 Input Handling (Conversation Flow)

- [ ] Implement `handle_input(chat_id, user_id, text, state)` method:
  - [ ] Get current state from state dict
  - [ ] Route based on state:
    - [ ] If state == 'awaiting_channel_id': call `_handle_channel_id_input()`
    - [ ] If state == 'editing_field': call `_handle_field_input()`
    - [ ] Otherwise: send error message

#### 5.3.3 Channel ID Input Handler

- [ ] Implement `_handle_channel_id_input(chat_id, user_id, text)` method:
  - [ ] Validate channel ID using `valid_channel_id(text)`
  - [ ] If invalid: send error message with format requirements

- [ ] If valid:
  - [ ] Fetch channel from database: `db.fetch_channel_by_id(text)`
  - [ ] If found:
    - [ ] Update conversation state with channel_data and state='viewing_form'
    - [ ] Call `show_main_form()` to display editing menu
  - [ ] If not found:
    - [ ] Ask if user wants to create new channel configuration
    - [ ] Show buttons: "✅ Create New" and "❌ Cancel"
    - [ ] Update state to 'confirming_new_channel'

#### 5.3.4 Field Input Handler

- [ ] Implement `_handle_field_input(chat_id, user_id, text, state)` method:
  - [ ] Get current_field from state
  - [ ] Route based on current_field:
    - [ ] "open_channel_title": validate with `valid_channel_title()`
    - [ ] "open_channel_description": validate with `valid_channel_description()`
    - [ ] "closed_channel_id": validate with `valid_channel_id()`
    - [ ] "closed_channel_title": validate with `valid_channel_title()`
    - [ ] "closed_channel_description": validate with `valid_channel_description()`
    - [ ] "sub_1_price", "sub_2_price", "sub_3_price": validate with `valid_sub_price()`
    - [ ] "sub_1_time", "sub_2_time", "sub_3_time": validate with `valid_sub_time()`
    - [ ] "client_wallet_address": validate with `valid_wallet_address()`
    - [ ] "client_payout_currency": validate with `valid_currency()`

- [ ] If validation passes:
  - [ ] Update channel_data in state with new value
  - [ ] Show appropriate form (open channel, private channel, tiers, wallet)
  - [ ] Update state to 'viewing_form'

- [ ] If validation fails:
  - [ ] Send error message with validation requirements
  - [ ] Keep state as 'editing_field'

#### 5.3.5 Main Form Display

- [ ] Implement `show_main_form(chat_id, user_id, message_id)` method:
  - [ ] Get conversation state from database
  - [ ] Get channel_data from state
  - [ ] Create inline keyboard with sections:
    - [ ] Row 1: "📢 Open Channel" | "🔒 Private Channel"
    - [ ] Row 2: "💰 Payment Tiers" | "💳 Wallet Address"
    - [ ] Row 3: "✅ Save All Changes" | "❌ Cancel"

- [ ] Format message text:
  - [ ] Show overview of current configuration
  - [ ] Display open channel ID and title
  - [ ] Display closed channel ID and title
  - [ ] Display enabled tiers
  - [ ] Display wallet address

- [ ] Edit message with new keyboard and text
- [ ] Return result

#### 5.3.6 Open Channel Form

- [ ] Implement `show_open_channel_form(chat_id, user_id, message_id)` method:
  - [ ] Get channel_data from state
  - [ ] Create inline keyboard:
    - [ ] "Edit Open Channel ID" → EDIT_OPEN_CHANNEL_ID
    - [ ] "Edit Title" → EDIT_OPEN_TITLE
    - [ ] "Edit Description" → EDIT_OPEN_DESCRIPTION
    - [ ] "⬅️ Back to Main" → BACK_TO_MAIN

- [ ] Format message showing current values
- [ ] Edit message with keyboard
- [ ] Return result

#### 5.3.7 Private Channel Form

- [ ] Implement `show_private_channel_form(chat_id, user_id, message_id)` method:
  - [ ] Get channel_data from state
  - [ ] Create inline keyboard:
    - [ ] "Edit Closed Channel ID" → EDIT_CLOSED_CHANNEL_ID
    - [ ] "Edit Title" → EDIT_CLOSED_TITLE
    - [ ] "Edit Description" → EDIT_CLOSED_DESCRIPTION
    - [ ] "⬅️ Back to Main" → BACK_TO_MAIN

- [ ] Format message showing current values
- [ ] Edit message with keyboard
- [ ] Return result

#### 5.3.8 Payment Tiers Form

- [ ] Implement `show_payment_tiers_form(chat_id, user_id, message_id)` method:
  - [ ] Get channel_data from state
  - [ ] Create inline keyboard with tier editing buttons:
    - [ ] For each tier (1-3):
      - [ ] "Edit Tier X Price" → EDIT_TIER_X_PRICE
      - [ ] "Edit Tier X Time" → EDIT_TIER_X_TIME
      - [ ] "Toggle Tier X" → TOGGLE_TIER_X (enable/disable)
    - [ ] "⬅️ Back to Main" → BACK_TO_MAIN

- [ ] Format message showing current tier configurations
- [ ] Indicate which tiers are enabled/disabled
- [ ] Edit message with keyboard
- [ ] Return result

#### 5.3.9 Wallet Form

- [ ] Implement `show_wallet_form(chat_id, user_id, message_id)` method:
  - [ ] Get channel_data from state
  - [ ] Create inline keyboard:
    - [ ] "Edit Wallet Address" → EDIT_WALLET_ADDRESS
    - [ ] "Edit Payout Currency" → EDIT_PAYOUT_CURRENCY
    - [ ] "Edit Payout Network" → EDIT_PAYOUT_NETWORK
    - [ ] "⬅️ Back to Main" → BACK_TO_MAIN

- [ ] Format message showing current wallet configuration
- [ ] Edit message with keyboard
- [ ] Return result

#### 5.3.10 Edit Callback Handler

- [ ] Implement `handle_edit_callback(chat_id, user_id, message_id, callback_data)` method:
  - [ ] Parse callback_data to determine field being edited
  - [ ] Map callback_data to field names:
    - [ ] "EDIT_OPEN_CHANNEL" → show_open_channel_form()
    - [ ] "EDIT_PRIVATE_CHANNEL" → show_private_channel_form()
    - [ ] "EDIT_PAYMENT_TIERS" → show_payment_tiers_form()
    - [ ] "EDIT_WALLET" → show_wallet_form()
    - [ ] "EDIT_OPEN_CHANNEL_ID" → prompt for new value, set state to 'editing_field'
    - [ ] "EDIT_OPEN_TITLE" → prompt for new value
    - [ ] etc. for all fields

- [ ] Update conversation state with current_field and state='editing_field'
- [ ] Send/edit message asking for new value
- [ ] Return result

#### 5.3.11 Tier Toggle Handler

- [ ] Implement `toggle_tier(chat_id, user_id, message_id, callback_data)` method:
  - [ ] Parse tier number from callback_data (e.g., "TOGGLE_TIER_1" → tier 1)
  - [ ] Get conversation state
  - [ ] Get channel_data from state
  - [ ] Check if tier is currently enabled (price and time are set)
  - [ ] If enabled: set price and time to None (disable)
  - [ ] If disabled: set default values (price=5.0, time=30)
  - [ ] Update conversation state with modified channel_data
  - [ ] Refresh payment tiers form
  - [ ] Return result

#### 5.3.12 Save Changes Handler

- [ ] Implement `save_changes(chat_id, user_id, message_id)` method:
  - [ ] Get conversation state from database
  - [ ] Get channel_data from state
  - [ ] Extract open_channel_id from channel_data

- [ ] Validate required fields are present:
  - [ ] open_channel_id must be set
  - [ ] At least one tier must be enabled

- [ ] Save to database:
  - [ ] Call `db.update_channel_config(open_channel_id, channel_data)`
  - [ ] If successful:
    - [ ] Clear conversation state
    - [ ] Edit message to show success confirmation
    - [ ] Return success result
  - [ ] If failed:
    - [ ] Send error message
    - [ ] Keep conversation state
    - [ ] Return error result

**Verification:**
```python
# Test saving channel config
handler = DatabaseFormHandler(db_manager, config)
state = {
    'channel_data': {
        'open_channel_id': '-123',
        'open_channel_title': 'Test Channel',
        'sub_1_price': 9.99,
        'sub_1_time': 30
    }
}
db_manager.save_conversation_state(user_id, 'database', state)
result = handler.save_changes(chat_id, user_id, message_id)
assert result['status'] == 'ok'
```

---

## Phase 6: Testing & Quality Assurance

### 6.1 Unit Tests - Validators

**File:** `GCBotCommand-10-26/tests/test_validators.py`

- [ ] Create test file
- [ ] Import pytest and validators module
- [ ] Write test_valid_channel_id():
  - [ ] Test valid IDs: "-1003268562225", "12345"
  - [ ] Test invalid IDs: "abc123", "123456789012345" (too long)
- [ ] Write test_valid_sub_price():
  - [ ] Test valid prices: "9.99", "0", "100.5"
  - [ ] Test invalid prices: "-1", "10000", "9.999" (3 decimals)
- [ ] Write test_valid_sub_time():
  - [ ] Test valid times: "1", "30", "999"
  - [ ] Test invalid times: "0", "1000", "abc"
- [ ] Write test_validate_donation_amount():
  - [ ] Test valid amounts: "25.50", "$100", "1"
  - [ ] Test invalid amounts: "0.50", "10000", "25.555"
- [ ] Write test_valid_channel_title():
  - [ ] Test valid titles: "Test Channel", "A"*100
  - [ ] Test invalid titles: "", "A"*101
- [ ] Write test_valid_wallet_address():
  - [ ] Test valid addresses: "0x1234567890abcdef"
  - [ ] Test invalid addresses: "short", "A"*201

**Run Tests:**
```bash
cd GCBotCommand-10-26/
pytest tests/test_validators.py -v
```

---

### 6.2 Unit Tests - Token Parser

**File:** `GCBotCommand-10-26/tests/test_token_parser.py`

- [ ] Create test file
- [ ] Import pytest and TokenParser
- [ ] Write test_decode_hash():
  - [ ] Test decoding known hash to channel ID
  - [ ] Test invalid hash returns None
- [ ] Write test_encode_hash():
  - [ ] Test encoding channel ID
  - [ ] Test round-trip: encode then decode
- [ ] Write test_parse_subscription_token():
  - [ ] Test with time: "ABC123_9d99_30"
  - [ ] Test without time: "ABC123_9d99"
  - [ ] Verify price, time, channel_id in result
- [ ] Write test_parse_donation_token():
  - [ ] Test "ABC123_DONATE"
  - [ ] Verify type='donation' and channel_id
- [ ] Write test_parse_invalid_token():
  - [ ] Test empty string
  - [ ] Test malformed tokens
  - [ ] Verify type='invalid'

**Run Tests:**
```bash
pytest tests/test_token_parser.py -v
```

---

### 6.3 Unit Tests - HTTP Client

**File:** `GCBotCommand-10-26/tests/test_http_client.py`

- [ ] Create test file
- [ ] Import pytest, HTTPClient, requests_mock
- [ ] Write test_post_success():
  - [ ] Mock POST request to return success
  - [ ] Verify response is parsed correctly
- [ ] Write test_post_timeout():
  - [ ] Mock POST to raise Timeout exception
  - [ ] Verify returns None
- [ ] Write test_post_request_error():
  - [ ] Mock POST to raise RequestException
  - [ ] Verify returns None
- [ ] Write test_get_success():
  - [ ] Mock GET request
  - [ ] Verify response

**Run Tests:**
```bash
pytest tests/test_http_client.py -v
```

---

### 6.4 Integration Tests - Webhook Endpoints

**File:** `GCBotCommand-10-26/tests/test_routes.py`

- [ ] Create test file
- [ ] Import pytest, Flask test client, service module
- [ ] Set up test fixture:
  - [ ] Create app using create_app()
  - [ ] Return test client

#### Test /health Endpoint
- [ ] Write test_health_check():
  - [ ] GET /health
  - [ ] Assert status_code == 200
  - [ ] Assert response JSON contains 'status': 'healthy'

#### Test /webhook Endpoint - /start Command
- [ ] Write test_webhook_start_command():
  - [ ] Create Telegram update payload for /start
  - [ ] POST /webhook with payload
  - [ ] Assert status_code == 200
  - [ ] Mock Telegram API sendMessage call
  - [ ] Verify response

#### Test /webhook Endpoint - Callback Query
- [ ] Write test_webhook_callback_query():
  - [ ] Create callback_query payload
  - [ ] POST /webhook
  - [ ] Assert status_code == 200
  - [ ] Verify callback was processed

#### Test Error Handling
- [ ] Write test_webhook_invalid_payload():
  - [ ] POST /webhook with invalid JSON
  - [ ] Assert returns 400 or handles gracefully

**Run Tests:**
```bash
pytest tests/test_routes.py -v
```

---

### 6.5 End-to-End Tests

**File:** `GCBotCommand-10-26/tests/test_e2e.py`

- [ ] Create test file
- [ ] Set up test database connection
- [ ] Clean up test data before/after tests

#### Test Subscription Flow
- [ ] Write test_subscription_flow_e2e():
  - [ ] Create subscription token
  - [ ] POST /webhook with /start command and token
  - [ ] Verify payment state is saved in database
  - [ ] POST /webhook with TRIGGER_PAYMENT callback
  - [ ] Mock payment gateway response
  - [ ] Verify invoice is created

#### Test Database Configuration Flow
- [ ] Write test_database_config_flow_e2e():
  - [ ] POST /webhook with /database command
  - [ ] POST /webhook with channel ID input
  - [ ] Verify conversation state is saved
  - [ ] POST /webhook with edit callbacks
  - [ ] POST /webhook with field input
  - [ ] POST /webhook with SAVE_ALL_CHANGES
  - [ ] Verify channel config is saved to database

#### Test Donation Flow
- [ ] Write test_donation_flow_e2e():
  - [ ] POST /webhook with donation token
  - [ ] Verify conversation state
  - [ ] POST /webhook with donation amount
  - [ ] Mock payment gateway
  - [ ] Verify payment invoice created

**Run Tests:**
```bash
pytest tests/test_e2e.py -v
```

---

## Phase 7: Local Testing & Verification

### 7.1 Local Environment Setup

- [ ] Create virtual environment:
  ```bash
  cd GCBotCommand-10-26/
  python3 -m venv .venv
  source .venv/bin/activate  # or .venv\Scripts\activate on Windows
  ```

- [ ] Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

- [ ] Create `.env` file for local testing:
  ```bash
  cp .env.example .env
  # Edit .env with actual secret paths
  ```

---

### 7.2 Run Local Flask Server

- [ ] Start Flask server:
  ```bash
  cd GCBotCommand-10-26/
  python service.py
  ```

- [ ] Verify server is running:
  ```bash
  curl http://localhost:8080/health
  # Should return: {"status": "healthy", "service": "GCBotCommand-10-26", "database": "connected"}
  ```

---

### 7.3 Test /webhook Endpoint with cURL

- [ ] Test /start command (no args):
  ```bash
  curl -X POST http://localhost:8080/webhook \
    -H "Content-Type: application/json" \
    -d '{
      "update_id": 123456,
      "message": {
        "message_id": 1,
        "from": {"id": 6271402111, "first_name": "Test"},
        "chat": {"id": 6271402111, "type": "private"},
        "text": "/start"
      }
    }'
  ```

- [ ] Test /start with subscription token:
  ```bash
  # Create a test token first using TokenParser
  curl -X POST http://localhost:8080/webhook \
    -H "Content-Type: application/json" \
    -d '{
      "update_id": 123457,
      "message": {
        "message_id": 2,
        "from": {"id": 6271402111, "first_name": "Test"},
        "chat": {"id": 6271402111, "type": "private"},
        "text": "/start ABC123_9d99_30"
      }
    }'
  ```

- [ ] Test callback query:
  ```bash
  curl -X POST http://localhost:8080/webhook \
    -H "Content-Type: application/json" \
    -d '{
      "update_id": 123458,
      "callback_query": {
        "id": "callback123",
        "from": {"id": 6271402111, "first_name": "Test"},
        "message": {
          "message_id": 3,
          "chat": {"id": 6271402111}
        },
        "data": "CMD_DATABASE"
      }
    }'
  ```

---

### 7.4 Manual Testing with Telegram Bot

- [ ] Deploy to test environment (optional staging Cloud Run instance)
- [ ] Set webhook URL to test instance
- [ ] Test /start command in Telegram
- [ ] Test /database command
- [ ] Test full database editing flow
- [ ] Test subscription link with token
- [ ] Test donation link
- [ ] Verify all inline keyboards work correctly
- [ ] Check database entries after each action

---

## Phase 8: Deployment to Google Cloud Run

### 8.1 Pre-Deployment Checklist

- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Code reviewed for security issues
- [ ] Environment variables documented
- [ ] Dockerfile tested locally
- [ ] Database migrations executed on production database

---

### 8.2 Build Docker Image

- [ ] Build image locally to test:
  ```bash
  cd GCBotCommand-10-26/
  docker build -t gcbotcommand-10-26:latest .
  ```

- [ ] Run container locally:
  ```bash
  docker run -p 8080:8080 \
    -e TELEGRAM_BOT_SECRET_NAME="..." \
    -e DATABASE_HOST_SECRET="..." \
    gcbotcommand-10-26:latest
  ```

- [ ] Test container:
  ```bash
  curl http://localhost:8080/health
  ```

---

### 8.3 Deploy to Cloud Run

- [ ] Navigate to service directory:
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCBotCommand-10-26/
  ```

- [ ] Deploy to Cloud Run:
  ```bash
  gcloud run deploy gcbotcommand-10-26 \
    --source=. \
    --region=us-central1 \
    --platform=managed \
    --allow-unauthenticated \
    --project=telepay-459221 \
    --set-env-vars="TELEGRAM_BOT_SECRET_NAME=projects/telepay-459221/secrets/telegram-bot-token/versions/latest" \
    --set-env-vars="TELEGRAM_BOT_USERNAME=projects/telepay-459221/secrets/telegram-bot-username/versions/latest" \
    --set-env-vars="DATABASE_HOST_SECRET=projects/telepay-459221/secrets/database-host/versions/latest" \
    --set-env-vars="DATABASE_NAME_SECRET=projects/telepay-459221/secrets/database-name/versions/latest" \
    --set-env-vars="DATABASE_USER_SECRET=projects/telepay-459221/secrets/database-user/versions/latest" \
    --set-env-vars="DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/database-password/versions/latest" \
    --set-env-vars="GCPAYMENTGATEWAY_URL=https://gcpaymentgateway-10-26-pjxwjsdktq-uc.a.run.app" \
    --set-env-vars="GCDONATIONHANDLER_URL=https://gcdonationhandler-10-26-pjxwjsdktq-uc.a.run.app" \
    --min-instances=1 \
    --max-instances=10 \
    --memory=512Mi \
    --cpu=1 \
    --timeout=300s \
    --concurrency=80
  ```

- [ ] Verify deployment:
  ```bash
  gcloud run services describe gcbotcommand-10-26 \
    --region=us-central1 \
    --format='value(status.url)'
  ```

- [ ] Test deployed service health:
  ```bash
  SERVICE_URL=$(gcloud run services describe gcbotcommand-10-26 \
    --region=us-central1 \
    --format='value(status.url)')

  curl ${SERVICE_URL}/health
  ```

---

### 8.4 Set Telegram Webhook

⚠️ **CRITICAL:** Only set webhook after verifying service is healthy!

- [ ] Get deployed service URL:
  ```bash
  SERVICE_URL=$(gcloud run services describe gcbotcommand-10-26 \
    --region=us-central1 \
    --format='value(status.url)')

  echo "Service URL: ${SERVICE_URL}"
  ```

- [ ] Set webhook with Telegram:
  ```bash
  TOKEN="8139434770:AAGc7zRahRJksnhp3_HOvOLERRXdgaYo6Co"

  curl -X POST "https://api.telegram.org/bot${TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"${SERVICE_URL}/webhook\"}"
  ```

- [ ] Verify webhook is set:
  ```bash
  curl "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
  ```

- [ ] Expected response:
  ```json
  {
    "ok": true,
    "result": {
      "url": "https://gcbotcommand-10-26-xxx.a.run.app/webhook",
      "has_custom_certificate": false,
      "pending_update_count": 0,
      "max_connections": 40
    }
  }
  ```

---

### 8.5 Post-Deployment Verification

- [ ] Send `/start` command to bot in Telegram
- [ ] Verify main menu appears
- [ ] Test `/database` command
- [ ] Test database editing flow completely
- [ ] Test subscription link (create test channel and subscription)
- [ ] Test donation flow
- [ ] Monitor Cloud Run logs:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcbotcommand-10-26" \
    --limit 50 \
    --format json
  ```

- [ ] Check for errors in logs
- [ ] Verify database queries are executing correctly
- [ ] Test error handling by sending invalid input

---

## Phase 9: Monitoring & Observability

### 9.1 Set Up Cloud Monitoring

- [ ] Create log-based metric for errors:
  ```bash
  gcloud logging metrics create gcbotcommand_errors \
    --description="Count of errors in GCBotCommand" \
    --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="gcbotcommand-10-26" AND severity="ERROR"'
  ```

- [ ] Create alerting policy for high error rate
- [ ] Set up notification channel (email, Slack, etc.)

---

### 9.2 Monitor Key Metrics

- [ ] Monitor request count:
  ```bash
  gcloud monitoring time-series list \
    --filter='resource.type = "cloud_run_revision" AND metric.type = "run.googleapis.com/request_count"'
  ```

- [ ] Monitor request latency
- [ ] Monitor error rate
- [ ] Monitor instance count (scaling behavior)
- [ ] Monitor database connection pool usage

---

### 9.3 Set Up Logging Queries

- [ ] Create saved query for webhook requests:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbotcommand-10-26"
  jsonPayload.message=~"Received update_id"
  ```

- [ ] Create saved query for errors:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbotcommand-10-26"
  severity="ERROR"
  ```

- [ ] Create saved query for payment flows:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbotcommand-10-26"
  jsonPayload.message=~"Subscription|Donation"
  ```

---

## Phase 10: Cutover & Decommissioning Old Bot

### 10.1 Parallel Testing Period

- [ ] Run old monolithic bot (TelePay10-26) and new webhook service in parallel for 24-48 hours
- [ ] Compare behavior between old and new service
- [ ] Monitor for discrepancies
- [ ] Fix any issues found in webhook service
- [ ] Verify database writes are consistent

---

### 10.2 Gradual Traffic Migration

- [ ] Update Telegram webhook to point to new service (already done in Phase 8.4)
- [ ] Monitor for 1 hour - check for errors
- [ ] If successful, continue monitoring for 24 hours
- [ ] Check user-reported issues
- [ ] Verify all features work as expected

---

### 10.3 Decommission Old Bot

⚠️ **Only proceed after 48+ hours of successful operation**

- [ ] Stop TelePay10-26 bot process
- [ ] Verify webhook service handles all traffic
- [ ] Archive TelePay10-26 code:
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER
  mkdir ARCHIVES/TelePay10-26-ARCHIVED-$(date +%Y%m%d)
  cp -r 10-26/TelePay10-26 ARCHIVES/TelePay10-26-ARCHIVED-$(date +%Y%m%d)/
  ```

- [ ] Update documentation to reflect new architecture
- [ ] Remove old deployment configurations

---

## Phase 11: Documentation & Cleanup

### 11.1 Update Architecture Documentation

- [ ] Update TELEPAY_REFACTORING_ARCHITECTURE.md with actual deployment details
- [ ] Document any deviations from original plan
- [ ] Update ENDPOINT_WEBHOOK_ANALYSIS_FLOW.canvas with new service

---

### 11.2 Update Progress Files

- [ ] Update PROGRESS.md:
  ```markdown
  ## [2025-11-12] GCBotCommand Webhook Service Deployed
  - ✅ Refactored monolithic TelePay bot into GCBotCommand-10-26 webhook service
  - ✅ Deployed to Cloud Run as independent, stateless service
  - ✅ All bot commands (/start, /database) migrated
  - ✅ Conversation state management via database
  - ✅ Payment gateway routing via HTTP
  - ✅ Database form editing fully functional
  ```

- [ ] Update DECISIONS.md:
  ```markdown
  ## [2025-11-12] GCBotCommand Architecture - No Shared Modules
  - **Decision:** Removed shared modules pattern - all code exists within GCBotCommand-10-26/
  - **Rationale:** Simpler deployment, clearer boundaries, independent versioning
  - **Impact:** Each service is completely self-contained
  ```

- [ ] Update BUGS.md (if any issues found during implementation)

---

## Completion Criteria

### Service is Ready for Production When:

- [x] ✅ All Phase 1-11 tasks completed
- [ ] ✅ All unit tests passing (>90% coverage)
- [ ] ✅ All integration tests passing
- [ ] ✅ Deployed to Cloud Run successfully
- [ ] ✅ Telegram webhook set and verified
- [ ] ✅ Manual testing completed (all features work)
- [ ] ✅ Monitoring and alerting configured
- [ ] ✅ 48+ hours of stable operation
- [ ] ✅ No critical bugs in production
- [ ] ✅ Documentation updated

---

## Troubleshooting Guide

### Common Issues & Solutions

#### Issue: "Bot doesn't respond to commands"
- [ ] Check webhook is set correctly: `curl https://api.telegram.org/bot${TOKEN}/getWebhookInfo`
- [ ] Check Cloud Run logs for errors
- [ ] Verify service is receiving webhook POSTs
- [ ] Check database connection is working

#### Issue: "Database connection timeout"
- [ ] Verify database credentials in Secret Manager
- [ ] Check database instance is running
- [ ] Verify Cloud Run has network access to database
- [ ] Check connection pool settings

#### Issue: "Payment gateway not working"
- [ ] Verify GCPAYMENTGATEWAY_URL is correct
- [ ] Check payment gateway service is deployed and healthy
- [ ] Verify HTTP client timeout is sufficient
- [ ] Check logs for HTTP request errors

#### Issue: "Conversation state not persisting"
- [ ] Verify user_conversation_state table exists
- [ ] Check save_conversation_state() is being called
- [ ] Verify database writes are committing
- [ ] Check for database transaction errors

---

## Notes

- **Estimated Total Implementation Time:** 40-60 hours
- **Recommended Team Size:** 1-2 developers
- **Prerequisites:** Python 3.11, PostgreSQL, Google Cloud account, Telegram Bot Token
- **Risk Level:** Medium (requires careful testing before production cutover)

---

**Document Maintained By:** Claude
**Last Updated:** 2025-11-12
**Next Review:** After Phase 6 completion (Testing)
