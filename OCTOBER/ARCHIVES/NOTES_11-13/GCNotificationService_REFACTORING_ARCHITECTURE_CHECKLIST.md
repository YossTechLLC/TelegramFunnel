# GCNotificationService Refactoring Implementation Checklist

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Implementation Checklist
**Reference:** GCNotificationService_REFACTORING_ARCHITECTURE.md
**Service:** gcnotificationservice-10-26 (Cloud Run Webhook)

---

## Overview

This checklist guides the implementation of GCNotificationService as a standalone, self-contained Cloud Run webhook service. Each module is created independently to ensure **modular code structure** and maintainability.

**Architecture Principle:** NO shared modules - all functionality is self-contained within the service.

---

## Phase 1: Project Setup & Directory Structure

### 1.1 Create Service Directory
- [ ] Navigate to working directory: `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26`
- [ ] Create service directory: `mkdir GCNotificationService-10-26`
- [ ] Navigate into directory: `cd GCNotificationService-10-26`
- [ ] Initialize empty README.md with service description
- [ ] Verify directory is empty and ready for implementation

### 1.2 Create Configuration Files
- [ ] Create `requirements.txt` with dependencies:
  - flask==3.0.0
  - psycopg2-binary==2.9.9
  - python-telegram-bot==20.7
  - google-cloud-secret-manager==2.16.4
  - gunicorn==21.2.0

- [ ] Create `Dockerfile` for containerization
  - Use python:3.11-slim base image
  - Set working directory to /app
  - Copy requirements.txt
  - Install dependencies
  - Copy application code
  - Expose port 8080
  - Set CMD to run service.py

- [ ] Create `.dockerignore` to exclude:
  - `__pycache__`
  - `*.pyc`, `*.pyo`, `*.pyd`
  - `.Python`, `env/`, `venv/`, `.venv/`
  - `*.log`
  - `.git/`, `.gitignore`
  - `README.md`
  - `.env`, `.env.example`
  - `tests/`

- [ ] Create `.env.example` with Secret Manager environment variable templates:
  - TELEGRAM_BOT_TOKEN_SECRET
  - DATABASE_HOST_SECRET
  - DATABASE_NAME_SECRET
  - DATABASE_USER_SECRET
  - DATABASE_PASSWORD_SECRET
  - PORT=8080

---

## Phase 2: Module Implementation (Self-Contained)

### 2.1 Module: config_manager.py (Secret Manager Integration)

**Purpose:** Fetch configuration from Google Secret Manager
**Source:** COPIED from TelePay10-26/config_manager.py with modifications

#### Implementation Steps:
- [ ] Create file: `config_manager.py`
- [ ] Add file header with docstring:
  ```python
  """
  🔐 Configuration Manager for GCNotificationService
  Fetches secrets from Google Secret Manager
  """
  ```

- [ ] Add imports:
  - `import os`
  - `from google.cloud import secretmanager`
  - `from typing import Optional, Dict`
  - `import logging`

- [ ] Create `ConfigManager` class
- [ ] Implement `__init__()` method:
  - Initialize `self.bot_token = None`
  - Initialize `self.database_credentials = {}`

- [ ] Implement `fetch_secret()` method:
  - Parameters: `env_var_name: str`, `secret_name: str`
  - Create Secret Manager client
  - Fetch secret path from environment variable
  - Access secret version
  - Decode payload
  - Return secret value or None on error
  - Log success/failure with emoji indicators

- [ ] Implement `fetch_telegram_token()` method:
  - Call `fetch_secret()` with "TELEGRAM_BOT_TOKEN_SECRET"
  - Return bot token

- [ ] Implement `fetch_database_credentials()` method:
  - Fetch DATABASE_HOST_SECRET
  - Fetch DATABASE_NAME_SECRET
  - Fetch DATABASE_USER_SECRET
  - Fetch DATABASE_PASSWORD_SECRET
  - Set port = 5432 (standard PostgreSQL)
  - Return dictionary with all credentials

- [ ] Implement `initialize_config()` method:
  - Log initialization start
  - Call `fetch_telegram_token()`
  - Call `fetch_database_credentials()`
  - Validate critical config (bot_token and database credentials)
  - Log validation results
  - Return configuration dictionary

#### Verification:
- [ ] Code uses existing emoji patterns (🔐, ✅, ❌)
- [ ] All methods have type hints
- [ ] Error handling for Secret Manager failures
- [ ] Logging at appropriate levels (INFO, ERROR)
- [ ] No external dependencies on shared modules

---

### 2.2 Module: database_manager.py (Database Operations)

**Purpose:** PostgreSQL connection and notification-specific queries
**Source:** EXTRACTED from TelePay10-26/database.py (only relevant methods)

#### Implementation Steps:
- [ ] Create file: `database_manager.py`
- [ ] Add file header with docstring:
  ```python
  """
  🗄️ Database Manager for GCNotificationService
  Handles PostgreSQL connections and notification queries
  """
  ```

- [ ] Add imports:
  - `import psycopg2`
  - `from typing import Optional, Tuple, Dict, Any`
  - `import logging`

- [ ] Create `DatabaseManager` class
- [ ] Implement `__init__()` method:
  - Parameters: `host`, `port`, `dbname`, `user`, `password`
  - Store all credentials as instance variables
  - Validate credentials (raise RuntimeError if missing)
  - Log initialization with database info

- [ ] Implement `get_connection()` method:
  - Create psycopg2 connection using stored credentials
  - Return connection object
  - Handle connection errors with logging

- [ ] Implement `get_notification_settings()` method:
  - **Purpose:** Fetch notification_status and notification_id for a channel
  - Parameter: `open_channel_id: str`
  - Returns: `Optional[Tuple[bool, Optional[int]]]`
  - SQL Query:
    ```sql
    SELECT notification_status, notification_id
    FROM main_clients_database
    WHERE open_channel_id = %s
    ```
  - Create connection
  - Execute query with parameterized open_channel_id
  - Fetch one result
  - Close cursor and connection
  - Log success with settings details or warning if not found
  - Return tuple (notification_status, notification_id) or None

- [ ] Implement `get_channel_details_by_open_id()` method:
  - **Purpose:** Fetch channel title and description for notification formatting
  - Parameter: `open_channel_id: str`
  - Returns: `Optional[Dict[str, Any]]`
  - SQL Query:
    ```sql
    SELECT closed_channel_title, closed_channel_description
    FROM main_clients_database
    WHERE open_channel_id = %s
    LIMIT 1
    ```
  - Create connection
  - Execute query with parameterized open_channel_id
  - Fetch one result
  - Close cursor and connection
  - Build dictionary with channel_title and channel_description
  - Provide defaults if values are NULL
  - Log success or warning if not found
  - Return dictionary or None

#### Verification:
- [ ] Code uses existing emoji patterns (🗄️, ✅, ⚠️, ❌)
- [ ] All SQL queries use parameterized statements (prevent SQL injection)
- [ ] Connections are properly closed after use
- [ ] Methods match signatures from TelePay10-26/database.py
- [ ] Error handling for database connection failures
- [ ] No external dependencies on shared modules

---

### 2.3 Module: telegram_client.py (Telegram Bot API Wrapper)

**Purpose:** Wrap Telegram Bot API for sending messages
**Source:** NEW module

#### Implementation Steps:
- [ ] Create file: `telegram_client.py`
- [ ] Add file header with docstring:
  ```python
  """
  🤖 Telegram Client for GCNotificationService
  Wraps Telegram Bot API for sending messages
  """
  ```

- [ ] Add imports:
  - `from telegram import Bot`
  - `from telegram.error import TelegramError, Forbidden, BadRequest`
  - `import logging`
  - `import asyncio`

- [ ] Create `TelegramClient` class
- [ ] Implement `__init__()` method:
  - Parameter: `bot_token: str`
  - Validate bot_token is not empty (raise ValueError if missing)
  - Create `self.bot = Bot(token=bot_token)`
  - Log initialization

- [ ] Implement `send_message()` method:
  - **Purpose:** Send message via Telegram Bot API
  - Parameters:
    - `chat_id: int` - Telegram user ID
    - `text: str` - Message text
    - `parse_mode: str = 'HTML'` - Parsing mode
    - `disable_web_page_preview: bool = True` - Disable previews
  - Returns: `bool` (True if successful, False otherwise)
  - Log sending attempt with chat_id
  - Create asyncio event loop
  - Call `bot.send_message()` using `loop.run_until_complete()`
  - Pass all parameters (chat_id, text, parse_mode, disable_web_page_preview)
  - Handle exceptions:
    - `Forbidden` - User blocked bot (log warning, return False)
    - `BadRequest` - Invalid chat_id/message (log error, return False)
    - `TelegramError` - API error (log error, return False)
    - Generic `Exception` - Unexpected error (log with traceback, return False)
  - Log success if message delivered
  - Return True on success

#### Verification:
- [ ] Code uses existing emoji patterns (🤖, 📤, ✅, 🚫, ❌)
- [ ] Proper asyncio handling for python-telegram-bot >= 20.x
- [ ] All exception types handled gracefully
- [ ] Returns boolean for success/failure (not raising exceptions)
- [ ] Logging includes chat_id for debugging
- [ ] No external dependencies on shared modules

---

### 2.4 Module: validators.py (Input Validation)

**Purpose:** Validate incoming request data
**Source:** NEW module

#### Implementation Steps:
- [ ] Create file: `validators.py`
- [ ] Add file header with docstring:
  ```python
  """
  ✅ Validators for GCNotificationService
  Input validation utilities
  """
  ```

- [ ] Add imports:
  - `from typing import Dict, Any, List`
  - `import logging`

- [ ] Implement `validate_notification_request()` function:
  - **Purpose:** Validate notification request payload
  - Parameter: `data: Dict[str, Any]`
  - Returns: `tuple[bool, List[str]]` (is_valid, error_messages)
  - Initialize `errors = []`
  - Check required top-level fields: ['open_channel_id', 'payment_type', 'payment_data']
  - Validate `open_channel_id` is string and starts with '-'
  - Validate `payment_type` is 'subscription' or 'donation'
  - Validate `payment_data` is dictionary
  - Check common payment_data fields: ['user_id', 'amount_crypto', 'amount_usd', 'crypto_currency']
  - If payment_type is 'subscription', check fields: ['tier', 'tier_price', 'duration_days']
  - Return (True, []) if no errors, else (False, errors)

- [ ] Implement `validate_channel_id()` function:
  - **Purpose:** Validate channel ID format
  - Parameter: `channel_id: str`
  - Returns: `bool`
  - Check is string
  - Check starts with '-'
  - Check remaining characters are digits
  - Check length <= 14
  - Return True if valid, False otherwise

#### Verification:
- [ ] Code uses existing emoji patterns (✅)
- [ ] All validation rules match expected request format
- [ ] Returns detailed error messages for debugging
- [ ] Functions are pure (no side effects)
- [ ] Type hints on all parameters and returns
- [ ] No external dependencies on shared modules

---

### 2.5 Module: notification_handler.py (Business Logic)

**Purpose:** Core notification logic (formatting, sending)
**Source:** EXTRACTED from TelePay10-26/notification_service.py

#### Implementation Steps:
- [ ] Create file: `notification_handler.py`
- [ ] Add file header with docstring:
  ```python
  """
  📬 Notification Handler for GCNotificationService
  Handles notification formatting and delivery logic
  """
  ```

- [ ] Add imports:
  - `from typing import Optional, Dict, Any`
  - `from datetime import datetime`
  - `import logging`

- [ ] Create `NotificationHandler` class
- [ ] Implement `__init__()` method:
  - Parameters: `db_manager`, `telegram_client`
  - Store both as instance variables
  - Log initialization

- [ ] Implement `send_payment_notification()` method:
  - **Purpose:** Send payment notification to channel owner
  - Parameters:
    - `open_channel_id: str`
    - `payment_type: str` - 'subscription' or 'donation'
    - `payment_data: Dict[str, Any]`
  - Returns: `bool`
  - Log processing start with channel_id and payment_type
  - Step 1: Call `db_manager.get_notification_settings(open_channel_id)`
  - Check if settings exist (return False if None)
  - Extract notification_status and notification_id from settings
  - Step 2: Check if notification_status is True (return False if disabled)
  - Check if notification_id exists (return False if None)
  - Log that notifications are enabled
  - Step 3: Call `_format_notification_message()` with parameters
  - Step 4: Call `telegram_client.send_message()` with notification_id and message
  - Log success or failure
  - Return success boolean
  - Handle exceptions with logging and return False

- [ ] Implement `_format_notification_message()` method:
  - **Purpose:** Format notification message based on payment type
  - Parameters:
    - `open_channel_id: str`
    - `payment_type: str`
    - `payment_data: Dict[str, Any]`
  - Returns: `str` (formatted message)
  - Fetch channel details using `db_manager.get_channel_details_by_open_id()`
  - Extract channel_title (default to 'Your Channel' if not found)
  - Extract common fields from payment_data:
    - user_id, username, amount_crypto, amount_usd, crypto_currency, timestamp
  - Format user_display: "@{username}" or "User ID: {user_id}"
  - If payment_type == 'subscription':
    - Extract: tier, tier_price, duration_days
    - Build subscription message template with HTML formatting
    - Include: channel info, customer info, subscription details, payment amount, timestamp
  - Elif payment_type == 'donation':
    - Build donation message template with HTML formatting
    - Include: channel info, donor info, donation amount, timestamp
  - Else:
    - Build generic payment message template
  - Return formatted message string

- [ ] Implement `test_notification()` method:
  - **Purpose:** Send test notification to verify setup
  - Parameters: `chat_id: int`, `channel_title: str = "Test Channel"`
  - Returns: `bool`
  - Build test message template
  - Include: test indicator, channel_title, success message
  - Call `telegram_client.send_message()` with test message
  - Return success boolean
  - Handle exceptions with logging

#### Verification:
- [ ] Code uses existing emoji patterns (📬, ✅, ⚠️, ❌, 📭, 🎉, 💝, 💳, 🧪)
- [ ] Message templates match exactly from notification_service.py
- [ ] All HTML formatting preserved (<b>, <code> tags)
- [ ] Proper fallback values for missing data
- [ ] Step-by-step processing with logging
- [ ] Error handling with detailed traceback
- [ ] No external dependencies on shared modules
- [ ] Business logic is separate from HTTP handling

---

### 2.6 Module: service.py (Main Flask Application)

**Purpose:** HTTP server with application factory pattern
**Source:** NEW module

#### Implementation Steps:
- [ ] Create file: `service.py`
- [ ] Add file header with docstring:
  ```python
  """
  📬 GCNotificationService - Standalone Notification Webhook
  Sends payment notifications to channel owners via Telegram Bot API
  Version: 1.0
  Date: 2025-11-12
  """
  ```

- [ ] Add imports:
  - `from flask import Flask, request, jsonify, abort`
  - `from config_manager import ConfigManager`
  - `from database_manager import DatabaseManager`
  - `from notification_handler import NotificationHandler`
  - `from telegram_client import TelegramClient`
  - `import logging, sys, os`

- [ ] Configure logging:
  - Set level to INFO
  - Format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  - Stream to stdout
  - Create logger instance

- [ ] Implement `create_app()` function (Application Factory):
  - Create Flask app instance
  - Log initialization start
  - Initialize ConfigManager
  - Call `config_manager.initialize_config()`
  - Validate bot_token exists (raise RuntimeError if missing)
  - Validate database_credentials exist (raise RuntimeError if incomplete)
  - Initialize DatabaseManager with credentials
  - Initialize TelegramClient with bot_token
  - Initialize NotificationHandler with db_manager and telegram_client
  - Store notification_handler in app.config
  - Log successful initialization

- [ ] Implement Route: `GET /health`
  - **Purpose:** Health check for Cloud Run
  - Return JSON: `{'status': 'healthy', 'service': 'GCNotificationService', 'version': '1.0'}`
  - Status code: 200

- [ ] Implement Route: `POST /send-notification`
  - **Purpose:** Send payment notification to channel owner
  - Validate request is JSON (abort 400 if not)
  - Parse JSON body
  - Validate required fields: ['open_channel_id', 'payment_type', 'payment_data']
  - If missing fields, abort 400 with error message
  - Extract: open_channel_id, payment_type, payment_data
  - Validate payment_type is 'subscription' or 'donation' (abort 400 if invalid)
  - Log request received with channel_id and payment_type
  - Get notification_handler from app.config
  - Call `handler.send_payment_notification()` with parameters
  - If success:
    - Log success
    - Return JSON: `{'status': 'success', 'message': 'Notification sent successfully'}`, 200
  - If failure:
    - Log warning
    - Return JSON: `{'status': 'failed', 'message': 'Notification not sent (disabled or error)'}`, 200
  - Handle exceptions:
    - Log error with traceback
    - Return JSON: `{'status': 'error', 'message': str(e)}`, 500

- [ ] Implement Route: `POST /test-notification`
  - **Purpose:** Send test notification to verify setup
  - Parse JSON body
  - Validate 'chat_id' field exists (abort 400 if missing)
  - Extract chat_id and channel_title (default "Test Channel")
  - Get notification_handler from app.config
  - Call `handler.test_notification()` with parameters
  - If success:
    - Return JSON: `{'status': 'success', 'message': 'Test notification sent'}`, 200
  - If failure:
    - Return JSON: `{'status': 'failed', 'message': 'Test notification failed'}`, 200
  - Handle exceptions:
    - Log error with traceback
    - Return JSON: `{'status': 'error', 'message': str(e)}`, 500

- [ ] Add main execution block:
  - `if __name__ == "__main__":`
  - Create app using `create_app()`
  - Get PORT from environment (default 8080)
  - Run app on host="0.0.0.0" with specified port

#### Verification:
- [ ] Code uses existing emoji patterns (📬, ✅, ⚠️, ❌, 📭, 📤, 🧪)
- [ ] Application factory pattern properly implemented
- [ ] All routes have proper error handling
- [ ] Logging at appropriate levels for each operation
- [ ] HTTP status codes match API specification
- [ ] Request validation before processing
- [ ] Graceful error handling (doesn't crash on invalid input)
- [ ] No external dependencies on shared modules
- [ ] Service is stateless (suitable for Cloud Run)

---

## Phase 3: Deployment Configuration

### 3.1 Create Deployment Script
- [ ] Create file: `deploy_gcnotificationservice.sh`
- [ ] Add bash shebang: `#!/bin/bash`
- [ ] Define variables:
  - PROJECT_ID="telepay-459221"
  - SERVICE_NAME="gcnotificationservice-10-26"
  - REGION="us-central1"
  - SERVICE_ACCOUNT="telepay-cloudrun@telepay-459221.iam.gserviceaccount.com"

- [ ] Define Secret Manager paths:
  - TELEGRAM_BOT_TOKEN_SECRET
  - DATABASE_HOST_SECRET
  - DATABASE_NAME_SECRET
  - DATABASE_USER_SECRET
  - DATABASE_PASSWORD_SECRET

- [ ] Add gcloud run deploy command with:
  - `--source=.` (build from source)
  - `--region=${REGION}`
  - `--platform=managed`
  - `--allow-unauthenticated` (public webhook)
  - `--service-account=${SERVICE_ACCOUNT}`
  - `--set-env-vars` for all secrets
  - `--min-instances=0` (serverless scaling)
  - `--max-instances=10`
  - `--memory=256Mi`
  - `--cpu=0.5`
  - `--timeout=60s`
  - `--concurrency=80`

- [ ] Add echo statements for deployment start/complete
- [ ] Add echo statement with service URL
- [ ] Make script executable: `chmod +x deploy_gcnotificationservice.sh`

### 3.2 Verify IAM Permissions
- [ ] Verify service account exists: `telepay-cloudrun@telepay-459221.iam.gserviceaccount.com`
- [ ] Verify Secret Manager access for telegram-bot-token
- [ ] Verify Secret Manager access for database-host
- [ ] Verify Secret Manager access for database-name
- [ ] Verify Secret Manager access for database-user
- [ ] Verify Secret Manager access for database-password
- [ ] Verify Cloud SQL client role (if using Cloud SQL Proxy)

### 3.3 Create README.md
- [ ] Add service description
- [ ] Document API endpoints
- [ ] Add example requests/responses
- [ ] Document environment variables
- [ ] Add deployment instructions
- [ ] Add testing instructions
- [ ] Add troubleshooting section

---

## Phase 4: Local Testing

### 4.1 Setup Local Environment
- [ ] Ensure Python 3.11 installed
- [ ] Create virtual environment: `python -m venv .venv`
- [ ] Activate virtual environment
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Export environment variables (Secret Manager paths)

### 4.2 Unit Testing
- [ ] Test ConfigManager initialization
- [ ] Test ConfigManager.fetch_secret() with valid/invalid secrets
- [ ] Test DatabaseManager connection
- [ ] Test DatabaseManager.get_notification_settings() with valid channel_id
- [ ] Test DatabaseManager.get_channel_details_by_open_id() with valid channel_id
- [ ] Test TelegramClient initialization
- [ ] Test TelegramClient.send_message() with valid chat_id
- [ ] Test NotificationHandler.send_payment_notification() with subscription
- [ ] Test NotificationHandler.send_payment_notification() with donation
- [ ] Test NotificationHandler._format_notification_message() for both types
- [ ] Test validators.validate_notification_request() with valid/invalid data
- [ ] Test validators.validate_channel_id() with valid/invalid IDs

### 4.3 Integration Testing
- [ ] Start Flask app locally: `python service.py`
- [ ] Verify app starts without errors
- [ ] Test GET /health endpoint:
  ```bash
  curl http://localhost:8080/health
  ```
  - Verify returns 200 OK
  - Verify JSON response matches schema

- [ ] Test POST /send-notification with subscription:
  ```bash
  curl -X POST http://localhost:8080/send-notification \
    -H "Content-Type: application/json" \
    -d '{
      "open_channel_id": "-1003268562225",
      "payment_type": "subscription",
      "payment_data": {
        "user_id": 6271402111,
        "username": "test_user",
        "amount_crypto": "0.00034",
        "amount_usd": "9.99",
        "crypto_currency": "ETH",
        "tier": 1,
        "tier_price": "9.99",
        "duration_days": 30
      }
    }'
  ```
  - Verify returns 200 OK
  - Verify status is 'success' or 'failed'
  - Check logs for proper flow

- [ ] Test POST /send-notification with donation:
  ```bash
  curl -X POST http://localhost:8080/send-notification \
    -H "Content-Type: application/json" \
    -d '{
      "open_channel_id": "-1003268562225",
      "payment_type": "donation",
      "payment_data": {
        "user_id": 6271402111,
        "username": "donor_user",
        "amount_crypto": "0.001",
        "amount_usd": "50.00",
        "crypto_currency": "ETH"
      }
    }'
  ```
  - Verify returns 200 OK
  - Check logs and Telegram message delivery

- [ ] Test POST /test-notification:
  ```bash
  curl -X POST http://localhost:8080/test-notification \
    -H "Content-Type: application/json" \
    -d '{
      "chat_id": YOUR_CHAT_ID,
      "channel_title": "Test Channel"
    }'
  ```
  - Verify returns 200 OK
  - Check Telegram for test message

- [ ] Test error handling:
  - Send request with missing fields (expect 400)
  - Send request with invalid payment_type (expect 400)
  - Send non-JSON request (expect 400)

### 4.4 Database Query Testing
- [ ] Query notification settings for test channel
- [ ] Verify notification_status and notification_id are correct
- [ ] Query channel details for test channel
- [ ] Verify closed_channel_title and description are returned
- [ ] Test with non-existent channel_id (should return None)

---

## Phase 5: Cloud Deployment

### 5.1 Pre-Deployment Checks
- [ ] All local tests passing
- [ ] No errors in local logs
- [ ] Code follows existing emoji patterns
- [ ] All modules are self-contained (no shared dependencies)
- [ ] Dockerfile builds successfully
- [ ] Requirements.txt includes all dependencies
- [ ] Environment variables documented in .env.example

### 5.2 Deploy to Cloud Run
- [ ] Navigate to service directory
- [ ] Run deployment script:
  ```bash
  bash deploy_gcnotificationservice.sh
  ```
- [ ] Wait for build to complete
- [ ] Verify deployment successful
- [ ] Note service URL from output

### 5.3 Test Deployed Service
- [ ] Get service URL:
  ```bash
  gcloud run services describe gcnotificationservice-10-26 \
    --region=us-central1 \
    --format='value(status.url)'
  ```

- [ ] Test /health endpoint:
  ```bash
  curl https://gcnotificationservice-10-26-pjxwjsdktq-uc.a.run.app/health
  ```

- [ ] Test /send-notification with real data:
  ```bash
  curl -X POST https://gcnotificationservice-10-26-pjxwjsdktq-uc.a.run.app/send-notification \
    -H "Content-Type: application/json" \
    -d '{...}'
  ```

- [ ] Check Cloud Logging for errors:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcnotificationservice-10-26" \
    --limit=50 \
    --format=json
  ```

- [ ] Verify no errors in logs
- [ ] Verify notification delivered to Telegram
- [ ] Document service URL for integration

---

## Phase 6: Integration with Calling Services

### 6.1 Update np-webhook-10-26
- [ ] Navigate to np-webhook-10-26 directory
- [ ] Add environment variable to deployment:
  ```bash
  gcloud run services update np-webhook-10-26 \
    --set-env-vars="GCNOTIFICATIONSERVICE_URL=https://gcnotificationservice-10-26-pjxwjsdktq-uc.a.run.app" \
    --region=us-central1
  ```

- [ ] Add `requests` to requirements.txt if not present
- [ ] Locate notification call in code (after IPN validation)
- [ ] Replace old notification code with HTTP POST:
  ```python
  import requests

  GCNOTIFICATIONSERVICE_URL = os.getenv("GCNOTIFICATIONSERVICE_URL")

  def send_notification(open_channel_id, payment_type, payment_data):
      try:
          response = requests.post(
              f"{GCNOTIFICATIONSERVICE_URL}/send-notification",
              json={
                  "open_channel_id": open_channel_id,
                  "payment_type": payment_type,
                  "payment_data": payment_data
              },
              timeout=10
          )

          if response.status_code == 200:
              result = response.json()
              if result['status'] == 'success':
                  print(f"✅ Notification sent successfully")
                  return True
              else:
                  print(f"⚠️ Notification failed: {result['message']}")
                  return False
          else:
              print(f"❌ Notification service error: {response.status_code}")
              return False

      except Exception as e:
          print(f"❌ Error calling notification service: {e}")
          return False
  ```

- [ ] Deploy updated service:
  ```bash
  gcloud run deploy np-webhook-10-26 --source=. --region=us-central1
  ```

- [ ] Test end-to-end: create test payment and verify notification sent
- [ ] Check logs for successful notification calls

### 6.2 Update gcwebhook1-10-26
- [ ] Repeat same steps as 6.1 for gcwebhook1-10-26
- [ ] Locate notification call (after payment routing)
- [ ] Replace with HTTP POST to GCNotificationService
- [ ] Deploy updated service
- [ ] Test end-to-end

### 6.3 Update gcwebhook2-10-26
- [ ] Repeat same steps as 6.1 for gcwebhook2-10-26
- [ ] Locate notification call (after Telegram invite)
- [ ] Replace with HTTP POST to GCNotificationService
- [ ] Deploy updated service
- [ ] Test end-to-end

### 6.4 Update gcsplit1-10-26
- [ ] Repeat same steps as 6.1 for gcsplit1-10-26
- [ ] Locate notification call (after instant payout)
- [ ] Replace with HTTP POST to GCNotificationService
- [ ] Deploy updated service
- [ ] Test end-to-end

### 6.5 Update gchostpay1-10-26
- [ ] Repeat same steps as 6.1 for gchostpay1-10-26
- [ ] Locate notification call (after crypto payout)
- [ ] Replace with HTTP POST to GCNotificationService
- [ ] Deploy updated service
- [ ] Test end-to-end

---

## Phase 7: Monitoring & Validation

### 7.1 Cloud Logging Setup
- [ ] Create log query for all notifications:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcnotificationservice-10-26"
  ```

- [ ] Create log query for successful notifications:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcnotificationservice-10-26"
  "Notification sent successfully"
  ```

- [ ] Create log query for failed notifications:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcnotificationservice-10-26"
  "Notification failed"
  ```

- [ ] Create log query for errors:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcnotificationservice-10-26"
  severity>=ERROR
  ```

### 7.2 Performance Testing
- [ ] Monitor request latency (target: p95 < 2s)
- [ ] Monitor error rate (target: < 5%)
- [ ] Monitor success rate (target: > 90%)
- [ ] Monitor database connection errors (target: 0)
- [ ] Monitor Telegram API errors (target: < 2%)

### 7.3 End-to-End Validation
- [ ] Create real subscription payment via bot
- [ ] Verify notification delivered to channel owner
- [ ] Check logs for complete flow
- [ ] Create real donation payment via bot
- [ ] Verify donation notification delivered
- [ ] Test with notifications disabled (should not send)
- [ ] Test with invalid chat_id (should handle gracefully)

### 7.4 Metrics Dashboard
- [ ] Create Cloud Monitoring dashboard
- [ ] Add request rate chart (requests/second)
- [ ] Add error rate chart (%)
- [ ] Add latency percentiles chart (p50, p95, p99)
- [ ] Add success vs failure count chart
- [ ] Add database query latency chart
- [ ] Add Telegram API response time chart

---

## Phase 8: Documentation & Cleanup

### 8.1 Update PROGRESS.md
- [ ] Add entry at TOP of file (newest first):
  ```markdown
  ## 2025-11-12 - GCNotificationService Implementation
  - ✅ Created standalone notification webhook service
  - ✅ Implemented 6 self-contained modules (config, database, telegram, notification, validators, service)
  - ✅ Deployed to Cloud Run as gcnotificationservice-10-26
  - ✅ Updated 5 calling services (np-webhook, gcwebhook1/2, gcsplit1, gchostpay1)
  - ✅ All notifications routing through HTTP webhook
  - ✅ No shared module dependencies
  - ✅ End-to-end testing successful
  ```

### 8.2 Update DECISIONS.md
- [ ] Add entry at TOP of file:
  ```markdown
  ## 2025-11-12 - Self-Contained Service Architecture
  - **Decision:** No shared modules - all functionality copied/extracted into service
  - **Rationale:** "Duplication is far cheaper than the wrong abstraction"
  - **Benefits:** Service independence, simplified deployment, no version conflicts
  - **Trade-off:** Code duplication acceptable for microservices
  ```

### 8.3 Update BUGS.md
- [ ] Add entry at TOP if any bugs discovered during implementation
- [ ] Document workarounds or fixes applied

### 8.4 Archive Old Code
- [ ] ⚠️ DO NOT DELETE TelePay10-26/notification_service.py
- [ ] Add comment to notification_service.py noting it's archived
- [ ] Document that functionality now in gcnotificationservice-10-26

### 8.5 Service Documentation
- [ ] Document service URL in shared location
- [ ] Update integration guide for future webhooks
- [ ] Document API endpoints in team wiki/docs
- [ ] Create runbook for troubleshooting

---

## Verification Checklist

### Code Quality
- [ ] All modules use existing emoji patterns (📬, 🔐, 🗄️, 🤖, ✅, ⚠️, ❌)
- [ ] No shared module dependencies (100% self-contained)
- [ ] Type hints on all function parameters and returns
- [ ] Docstrings on all classes and methods
- [ ] Error handling with proper logging
- [ ] SQL queries use parameterized statements
- [ ] No hardcoded credentials (all from Secret Manager)

### Functionality
- [ ] All existing notification functionality preserved
- [ ] Subscription notifications working
- [ ] Donation notifications working
- [ ] Test notifications working
- [ ] Notifications can be disabled per channel
- [ ] Handles missing notification_id gracefully
- [ ] Handles user blocked bot gracefully

### Deployment
- [ ] Service deployed to Cloud Run
- [ ] Environment variables configured
- [ ] IAM permissions correct
- [ ] Service URL is publicly accessible
- [ ] Health endpoint responding
- [ ] Logs appearing in Cloud Logging

### Integration
- [ ] All 5 calling services updated
- [ ] All services deployed with GCNOTIFICATIONSERVICE_URL
- [ ] End-to-end tests passing for all services
- [ ] No breaking changes to payment flow
- [ ] Notification failures don't block payments

### Monitoring
- [ ] Cloud Logging queries created
- [ ] Metrics dashboard created
- [ ] Success rate > 90%
- [ ] Latency < 2s (p95)
- [ ] Error rate < 5%
- [ ] No database connection errors

---

## Rollback Plan

### If Critical Issues Found:

1. **Pause Deployment**
   - [ ] Stop deployment script if in progress
   - [ ] Document the issue in BUGS.md

2. **Restore Old Integration (if needed)**
   - [ ] Revert calling services to previous version
   - [ ] Redeploy calling services
   - [ ] Monitor for stability

3. **Debug GCNotificationService**
   - [ ] Check Cloud Logging for error details
   - [ ] Test locally with same data
   - [ ] Fix issue in code
   - [ ] Redeploy service
   - [ ] Test before re-enabling integration

4. **Communicate**
   - [ ] Document issue and resolution
   - [ ] Update BUGS.md
   - [ ] Update PROGRESS.md

---

## Success Criteria

✅ **Implementation Complete When:**

1. GCNotificationService deployed to Cloud Run
2. All 6 modules created as self-contained files
3. /health endpoint returning 200 OK
4. /send-notification endpoint processing requests
5. All 5 calling services updated and deployed
6. End-to-end test successful (payment → notification delivery)
7. Logs show no errors
8. Success rate > 90%
9. Latency < 2 seconds (p95)
10. PROGRESS.md, DECISIONS.md updated
11. Service URL documented
12. Monitoring dashboard created

---

## Notes

- **Context Limit:** Check remaining context before starting implementation
- **Emoji Patterns:** Preserve existing emoji usage for consistency
- **No GitHub:** Do NOT create branches or commits (manual only)
- **Database:** Use telepaypsql, avoid telepaypsql-clone-preclaude
- **Modular Structure:** Each module in separate file (not one monolithic file)
- **Self-Contained:** No shared module dependencies
- **Testing:** Test locally before deploying to Cloud Run
- **Incremental:** Deploy and test one service at a time

---

**Ready to begin Phase 1: Project Setup & Directory Structure**
