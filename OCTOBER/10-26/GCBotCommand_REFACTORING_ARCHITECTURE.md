# GCBotCommand Refactoring Architecture
## Comprehensive Migration from Monolithic TelePay Bot to Webhook Service

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Architecture Design
**Branch:** TelePay-REFACTOR
**Service Name:** GCBotCommand-10-26

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Scope & Objectives](#scope--objectives)
3. [Architecture Overview](#architecture-overview)
4. [Directory Structure](#directory-structure)
5. [Module-by-Module Migration](#module-by-module-migration)
6. [Database Operations](#database-operations)
7. [Configuration Management](#configuration-management)
8. [Webhook Implementation](#webhook-implementation)
9. [Conversation Handlers](#conversation-handlers)
10. [Token Parsing & Deep Linking](#token-parsing--deep-linking)
11. [HTTP Client for External Services](#http-client-for-external-services)
12. [Deployment Strategy](#deployment-strategy)
13. [Testing Strategy](#testing-strategy)
14. [Migration Checklist](#migration-checklist)

---

## Executive Summary

### Problem Statement

The current TelePay10-26 bot handles **all Telegram bot interactions** in a monolithic long-running process using **polling mode**:

- Bot command handling (/start, /database, button callbacks)
- Conversation state management (database editing, donations)
- Token parsing and deep linking
- Payment gateway routing
- Menu systems and inline keyboards

**Current Files to Migrate:**
- `telepay10-26.py` (71 lines) - Main orchestrator
- `app_initializer.py` (160 lines) - Application setup
- `bot_manager.py` (170 lines) - Bot handlers setup
- `input_handlers.py` (484 lines) - Input validation & conversation flows
- `menu_handlers.py` (698 lines) - Menu callbacks, token parsing
- `config_manager.py` (76 lines) - Configuration & secrets
- `database.py` (719 lines) - Database operations
- `message_utils.py` (24 lines) - Message utilities

**Total:** ~2,402 lines of Python code

### Solution Overview

**Refactor into GCBotCommand-10-26**, a **stateless Cloud Run webhook service** that:

✅ Receives Telegram updates via webhook (not polling)
✅ Contains **all** necessary modules independently (no shared dependencies)
✅ Routes commands and callbacks to appropriate handlers
✅ Calls external services (GCPaymentGateway, GCDonationHandler) via HTTP
✅ Manages conversation state via database (not in-memory)
✅ Follows Flask application factory pattern
✅ Scales horizontally based on demand

### Key Design Decisions

1. **No Shared Modules:** Every module (database, config, validators, etc.) exists **within** GCBotCommand-10-26/
2. **Webhook-Based:** Use `setWebhook` instead of polling for better scalability
3. **Stateless:** Store conversation state in database, not in-memory
4. **HTTP Routing:** Call payment gateway and donation handler via HTTP POST
5. **Self-Contained:** Service deploys independently without external dependencies

---

## Scope & Objectives

### In Scope

✅ **Bot Command Handling**
- `/start` command with token parsing
- `/database` command for channel configuration
- Button callbacks (payment, donation, database editing)

✅ **Conversation Flows**
- Database V2 inline form editing
- Old database flow (legacy support)
- Donation amount input flow

✅ **Token Parsing & Deep Linking**
- Subscription tokens: `{hash}_{price}_{time}`
- Donation tokens: `{hash}_DONATE`
- Hash decoding to channel IDs

✅ **Menu Systems**
- Inline keyboard menus
- Database editing forms (open channel, private channel, tiers, wallet)
- Navigation (back buttons, submit, cancel)

✅ **HTTP Routing**
- Call GCPaymentGateway for invoice creation
- Call GCDonationHandler for keypad input
- Database queries for channel info

### Out of Scope

❌ Subscription monitoring (handled by GCSubscriptionMonitor)
❌ Notification delivery (handled by GCNotificationService)
❌ Broadcast messages (handled by GCBroadcastService)
❌ Payment gateway logic (handled by GCPaymentGateway)
❌ Donation keypad logic (handled by GCDonationHandler)

---

## Architecture Overview

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      Telegram Bot API                           │
│              (User sends /start, clicks buttons)                │
└──────────────────────┬──────────────────────────────────────────┘
                       │ Webhook POST
                       ▼
              ┌─────────────────┐
              │  GCBotCommand   │
              │  (Cloud Run)    │
              │                 │
              │  POST /webhook  │  ← Receives Telegram updates
              │  GET  /health   │  ← Health check
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Database     │ │ GCPayment    │ │ GCDonation   │
│ (PostgreSQL) │ │ Gateway      │ │ Handler      │
│              │ │ (HTTP POST)  │ │ (HTTP POST)  │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Service Responsibilities

| Responsibility | Implementation |
|----------------|----------------|
| **Receive Telegram Updates** | `/webhook` endpoint accepts POST from Telegram |
| **Parse /start Tokens** | Decode subscription and donation tokens |
| **Handle /database Command** | Start conversation for channel configuration |
| **Manage Conversation State** | Store state in database (user_sessions table) |
| **Route Payment Requests** | HTTP POST to GCPaymentGateway |
| **Route Donation Requests** | HTTP POST to GCDonationHandler |
| **Database Configuration** | Inline form editing with validation |
| **Menu Systems** | Inline keyboards with callback handling |

---

## Directory Structure

**IMPORTANT:** All modules are self-contained within GCBotCommand-10-26/ directory.
**NO shared modules** - everything needed is copied into this service.

```
GCBotCommand-10-26/
├── Dockerfile                          # Container definition
├── requirements.txt                    # Python dependencies
├── .env.example                        # Environment variable template
├── .dockerignore                       # Files to exclude from build
│
├── service.py                          # Main Flask app (entry point)
├── config_manager.py                   # Configuration & Secret Manager
├── database_manager.py                 # Database operations (PostgreSQL)
│
├── routes/
│   ├── __init__.py
│   └── webhook.py                      # Webhook routes (/webhook, /health)
│
├── handlers/
│   ├── __init__.py
│   ├── command_handler.py              # /start, /database commands
│   ├── callback_handler.py             # Button callback queries
│   ├── conversation_handler.py         # Conversation state management
│   ├── database_handler.py             # Database form editing logic
│   └── menu_handler.py                 # Menu & inline keyboard logic
│
├── utils/
│   ├── __init__.py
│   ├── validators.py                   # Input validation functions
│   ├── token_parser.py                 # Token decoding & parsing
│   ├── message_formatter.py            # Message text formatting
│   └── http_client.py                  # HTTP requests to other services
│
├── models/
│   ├── __init__.py
│   └── telegram_update.py              # Telegram update data classes
│
└── tests/
    ├── __init__.py
    ├── test_routes.py                  # Test webhook endpoints
    ├── test_handlers.py                # Test command handlers
    ├── test_validators.py              # Test input validators
    └── test_token_parser.py            # Test token parsing
```

---

## Module-by-Module Migration

### 1. service.py (Main Flask App)

**Purpose:** Entry point for the Flask application using application factory pattern

**Migrates From:**
- `telepay10-26.py` (main orchestrator)
- `app_initializer.py` (initialization logic)

**Implementation:**

```python
#!/usr/bin/env python
"""
GCBotCommand - Telegram Bot Webhook Service
Handles all bot commands, callbacks, and conversation flows
"""
from flask import Flask
from config_manager import ConfigManager
from database_manager import DatabaseManager
from routes.webhook import webhook_bp
import logging

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def create_app():
    """Application factory pattern for Flask"""
    app = Flask(__name__)

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.initialize_config()
    app.config.update(config)

    logger.info("✅ Configuration loaded")

    # Initialize database manager
    try:
        db_manager = DatabaseManager()
        app.db = db_manager
        logger.info("✅ Database manager initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise

    # Store configuration in app context for handlers
    app.config_manager = config_manager

    # Register blueprints
    app.register_blueprint(webhook_bp)
    logger.info("✅ Routes registered")

    return app

if __name__ == "__main__":
    app = create_app()
    port = 8080
    logger.info(f"🚀 Starting GCBotCommand on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
```

---

### 2. config_manager.py (Configuration & Secrets)

**Purpose:** Fetch secrets from Google Secret Manager and manage configuration

**Migrates From:** `TelePay10-26/config_manager.py` (76 lines)

**Implementation:**

```python
#!/usr/bin/env python
"""
Configuration Manager for GCBotCommand
Fetches secrets from Google Secret Manager
"""
import os
from google.cloud import secretmanager
from typing import Optional, Dict

class ConfigManager:
    def __init__(self):
        self.bot_token = None
        self.bot_username = None
        self.gcpaymentgateway_url = None
        self.gcdonationhandler_url = None
        self.client = secretmanager.SecretManagerServiceClient()

    def _fetch_secret(self, env_var_name: str) -> Optional[str]:
        """Generic secret fetcher from Secret Manager"""
        try:
            secret_path = os.getenv(env_var_name)
            if not secret_path:
                raise ValueError(f"Environment variable {env_var_name} is not set.")
            response = self.client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching {env_var_name}: {e}")
            return None

    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch Telegram bot token from Secret Manager"""
        return self._fetch_secret("TELEGRAM_BOT_SECRET_NAME")

    def fetch_bot_username(self) -> Optional[str]:
        """Fetch bot username from Secret Manager"""
        return self._fetch_secret("TELEGRAM_BOT_USERNAME")

    def fetch_gcpaymentgateway_url(self) -> str:
        """Fetch GCPaymentGateway URL from environment"""
        url = os.getenv("GCPAYMENTGATEWAY_URL")
        if not url:
            raise ValueError("GCPAYMENTGATEWAY_URL not set")
        return url

    def fetch_gcdonationhandler_url(self) -> str:
        """Fetch GCDonationHandler URL from environment"""
        url = os.getenv("GCDONATIONHANDLER_URL")
        if not url:
            raise ValueError("GCDONATIONHANDLER_URL not set")
        return url

    def initialize_config(self) -> Dict[str, str]:
        """Initialize and return all configuration values"""
        self.bot_token = self.fetch_telegram_token()
        self.bot_username = self.fetch_bot_username()
        self.gcpaymentgateway_url = self.fetch_gcpaymentgateway_url()
        self.gcdonationhandler_url = self.fetch_gcdonationhandler_url()

        if not self.bot_token:
            raise RuntimeError("Bot token is required to start GCBotCommand")

        return {
            'bot_token': self.bot_token,
            'bot_username': self.bot_username,
            'gcpaymentgateway_url': self.gcpaymentgateway_url,
            'gcdonationhandler_url': self.gcdonationhandler_url
        }

    def get_config(self) -> Dict[str, str]:
        """Get current configuration values"""
        return {
            'bot_token': self.bot_token,
            'bot_username': self.bot_username,
            'gcpaymentgateway_url': self.gcpaymentgateway_url,
            'gcdonationhandler_url': self.gcdonationhandler_url
        }
```

**Environment Variables Required:**

```bash
# Secret Manager paths
TELEGRAM_BOT_SECRET_NAME="projects/telepay-459221/secrets/telegram-bot-token/versions/latest"
TELEGRAM_BOT_USERNAME="projects/telepay-459221/secrets/telegram-bot-username/versions/latest"
DATABASE_HOST_SECRET="projects/telepay-459221/secrets/database-host/versions/latest"
DATABASE_NAME_SECRET="projects/telepay-459221/secrets/database-name/versions/latest"
DATABASE_USER_SECRET="projects/telepay-459221/secrets/database-user/versions/latest"
DATABASE_PASSWORD_SECRET="projects/telepay-459221/secrets/database-password/versions/latest"

# External service URLs
GCPAYMENTGATEWAY_URL="https://gcpaymentgateway-10-26-pjxwjsdktq-uc.a.run.app"
GCDONATIONHANDLER_URL="https://gcdonationhandler-10-26-pjxwjsdktq-uc.a.run.app"
```

---

### 3. database_manager.py (Database Operations)

**Purpose:** Handle all PostgreSQL database operations

**Migrates From:** `TelePay10-26/database.py` (719 lines)

**Key Operations:**
- Fetch channel configurations
- Update channel configurations
- Store/retrieve conversation state
- Manage user sessions for stateless operations

**Implementation:**

```python
#!/usr/bin/env python
"""
Database Manager for GCBotCommand
Handles all PostgreSQL database operations
"""
import psycopg2
import os
from typing import Optional, Tuple, List, Dict, Any
from google.cloud import secretmanager

def fetch_database_host() -> str:
    """Fetch database host from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_HOST_SECRET")
        if not secret_path:
            raise ValueError("DATABASE_HOST_SECRET not set")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_HOST_SECRET: {e}")
        raise

def fetch_database_name() -> str:
    """Fetch database name from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_NAME_SECRET")
        if not secret_path:
            raise ValueError("DATABASE_NAME_SECRET not set")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_NAME_SECRET: {e}")
        raise

def fetch_database_user() -> str:
    """Fetch database user from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_USER_SECRET")
        if not secret_path:
            raise ValueError("DATABASE_USER_SECRET not set")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_USER_SECRET: {e}")
        raise

def fetch_database_password() -> str:
    """Fetch database password from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_PASSWORD_SECRET")
        if not secret_path:
            return None
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_PASSWORD_SECRET: {e}")
        return None

class DatabaseManager:
    """Manages all database operations for GCBotCommand"""

    def __init__(self):
        self.host = fetch_database_host()
        self.port = 5432
        self.dbname = fetch_database_name()
        self.user = fetch_database_user()
        self.password = fetch_database_password()

        if not all([self.host, self.dbname, self.user, self.password]):
            raise RuntimeError("Critical database configuration missing from Secret Manager")

    def get_connection(self):
        """Create and return a database connection"""
        return psycopg2.connect(
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port
        )

    def fetch_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch channel configuration by open_channel_id

        Args:
            channel_id: The open_channel_id to look up

        Returns:
            Dictionary with channel configuration, or None if not found
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        open_channel_id, open_channel_title, open_channel_description,
                        closed_channel_id, closed_channel_title, closed_channel_description,
                        closed_channel_donation_message,
                        sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                        client_wallet_address, client_payout_currency, client_payout_network,
                        payout_strategy, payout_threshold_usd,
                        notification_status, notification_id
                    FROM main_clients_database
                    WHERE open_channel_id = %s
                """, (channel_id,))

                row = cur.fetchone()
                if not row:
                    return None

                return {
                    "open_channel_id": row[0],
                    "open_channel_title": row[1],
                    "open_channel_description": row[2],
                    "closed_channel_id": row[3],
                    "closed_channel_title": row[4],
                    "closed_channel_description": row[5],
                    "closed_channel_donation_message": row[6],
                    "sub_1_price": row[7],
                    "sub_1_time": row[8],
                    "sub_2_price": row[9],
                    "sub_2_time": row[10],
                    "sub_3_price": row[11],
                    "sub_3_time": row[12],
                    "client_wallet_address": row[13],
                    "client_payout_currency": row[14],
                    "client_payout_network": row[15],
                    "payout_strategy": row[16],
                    "payout_threshold_usd": row[17],
                    "notification_status": row[18],
                    "notification_id": row[19]
                }
        except Exception as e:
            print(f"❌ Error fetching channel by ID: {e}")
            return None

    def update_channel_config(self, channel_id: str, channel_data: Dict[str, Any]) -> bool:
        """
        Update or insert channel configuration

        Args:
            channel_id: The open_channel_id
            channel_data: Dictionary with channel configuration fields

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                # Use UPSERT (INSERT ... ON CONFLICT UPDATE)
                cur.execute("""
                    INSERT INTO main_clients_database (
                        open_channel_id, open_channel_title, open_channel_description,
                        closed_channel_id, closed_channel_title, closed_channel_description,
                        closed_channel_donation_message,
                        sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                        client_wallet_address, client_payout_currency, client_payout_network
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (open_channel_id) DO UPDATE SET
                        open_channel_title = EXCLUDED.open_channel_title,
                        open_channel_description = EXCLUDED.open_channel_description,
                        closed_channel_id = EXCLUDED.closed_channel_id,
                        closed_channel_title = EXCLUDED.closed_channel_title,
                        closed_channel_description = EXCLUDED.closed_channel_description,
                        closed_channel_donation_message = EXCLUDED.closed_channel_donation_message,
                        sub_1_price = EXCLUDED.sub_1_price,
                        sub_1_time = EXCLUDED.sub_1_time,
                        sub_2_price = EXCLUDED.sub_2_price,
                        sub_2_time = EXCLUDED.sub_2_time,
                        sub_3_price = EXCLUDED.sub_3_price,
                        sub_3_time = EXCLUDED.sub_3_time,
                        client_wallet_address = EXCLUDED.client_wallet_address,
                        client_payout_currency = EXCLUDED.client_payout_currency,
                        client_payout_network = EXCLUDED.client_payout_network
                """, (
                    channel_id,
                    channel_data.get("open_channel_title"),
                    channel_data.get("open_channel_description"),
                    channel_data.get("closed_channel_id"),
                    channel_data.get("closed_channel_title"),
                    channel_data.get("closed_channel_description"),
                    channel_data.get("closed_channel_donation_message"),
                    channel_data.get("sub_1_price"),
                    channel_data.get("sub_1_time"),
                    channel_data.get("sub_2_price"),
                    channel_data.get("sub_2_time"),
                    channel_data.get("sub_3_price"),
                    channel_data.get("sub_3_time"),
                    channel_data.get("client_wallet_address"),
                    channel_data.get("client_payout_currency"),
                    channel_data.get("client_payout_network")
                ))
                conn.commit()
                print(f"✅ Channel {channel_id} configuration saved")
                return True
        except Exception as e:
            print(f"❌ Error updating channel config: {e}")
            return False

    def fetch_open_channel_list(self) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """
        Fetch all open channels and their configuration

        Returns:
            Tuple of (list of channel IDs, dict mapping ID to config)
        """
        open_channel_list = []
        open_channel_info_map = {}

        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        open_channel_id, open_channel_title, open_channel_description,
                        closed_channel_id, closed_channel_title, closed_channel_description,
                        sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                        client_wallet_address, client_payout_currency, client_payout_network
                    FROM main_clients_database
                """)

                for row in cur.fetchall():
                    open_channel_id = row[0]
                    open_channel_list.append(open_channel_id)
                    open_channel_info_map[open_channel_id] = {
                        "open_channel_title": row[1],
                        "open_channel_description": row[2],
                        "closed_channel_id": row[3],
                        "closed_channel_title": row[4],
                        "closed_channel_description": row[5],
                        "sub_1_price": row[6],
                        "sub_1_time": row[7],
                        "sub_2_price": row[8],
                        "sub_2_time": row[9],
                        "sub_3_price": row[10],
                        "sub_3_time": row[11],
                        "client_wallet_address": row[12],
                        "client_payout_currency": row[13],
                        "client_payout_network": row[14]
                    }
        except Exception as e:
            print(f"❌ Error fetching open channel list: {e}")

        return open_channel_list, open_channel_info_map

    # ═══════════════════════════════════════════════════════════════
    #  CONVERSATION STATE MANAGEMENT (for stateless webhook operation)
    # ═══════════════════════════════════════════════════════════════

    def save_conversation_state(self, user_id: int, conversation_type: str, state_data: Dict[str, Any]) -> bool:
        """
        Save conversation state to database for stateless operation

        Args:
            user_id: Telegram user ID
            conversation_type: Type of conversation ('database', 'donation', etc.)
            state_data: Dictionary with conversation state

        Returns:
            True if successful
        """
        try:
            import json
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_conversation_state (user_id, conversation_type, state_data, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (user_id, conversation_type) DO UPDATE SET
                        state_data = EXCLUDED.state_data,
                        updated_at = NOW()
                """, (user_id, conversation_type, json.dumps(state_data)))
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error saving conversation state: {e}")
            return False

    def get_conversation_state(self, user_id: int, conversation_type: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve conversation state from database

        Args:
            user_id: Telegram user ID
            conversation_type: Type of conversation

        Returns:
            State data dictionary or None
        """
        try:
            import json
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    SELECT state_data FROM user_conversation_state
                    WHERE user_id = %s AND conversation_type = %s
                """, (user_id, conversation_type))
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])
                return None
        except Exception as e:
            print(f"❌ Error getting conversation state: {e}")
            return None

    def clear_conversation_state(self, user_id: int, conversation_type: str) -> bool:
        """Clear conversation state for a user"""
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM user_conversation_state
                    WHERE user_id = %s AND conversation_type = %s
                """, (user_id, conversation_type))
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error clearing conversation state: {e}")
            return False
```

**Required Database Table for Conversation State:**

```sql
-- Create table for storing conversation state (stateless webhook operation)
CREATE TABLE IF NOT EXISTS user_conversation_state (
    user_id BIGINT NOT NULL,
    conversation_type VARCHAR(50) NOT NULL,
    state_data JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, conversation_type)
);

CREATE INDEX idx_conversation_state_updated ON user_conversation_state(updated_at);
```

---

### 4. routes/webhook.py (Webhook Routes)

**Purpose:** Flask routes for receiving Telegram updates and health checks

**Migrates From:**
- `bot_manager.py` (webhook setup)
- `server_manager.py` (Flask routes)

**Implementation:**

```python
#!/usr/bin/env python
"""
Webhook routes for GCBotCommand
Handles Telegram update webhooks and health checks
"""
from flask import Blueprint, request, jsonify, current_app
from handlers.command_handler import CommandHandler
from handlers.callback_handler import CallbackHandler
import logging

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Receive Telegram updates via webhook

    Expected format from Telegram:
    {
        "update_id": 123456789,
        "message": {...} or "callback_query": {...}
    }
    """
    try:
        data = request.get_json()

        if not data:
            logger.warning("⚠️ Received empty webhook payload")
            return jsonify({"status": "error", "message": "Empty payload"}), 400

        logger.info(f"📨 Received update_id: {data.get('update_id')}")

        # Get handlers
        command_handler = CommandHandler(current_app.db, current_app.config)
        callback_handler = CallbackHandler(current_app.db, current_app.config)

        # Route based on update type
        if 'message' in data:
            # Handle text messages and commands
            message = data['message']

            # Check if message has text
            if 'text' in message:
                text = message['text']

                # Handle commands
                if text.startswith('/start'):
                    result = command_handler.handle_start_command(data)
                    return jsonify(result), 200

                elif text.startswith('/database'):
                    result = command_handler.handle_database_command(data)
                    return jsonify(result), 200

                else:
                    # Handle conversation input (ongoing database editing, etc.)
                    result = command_handler.handle_text_input(data)
                    return jsonify(result), 200
            else:
                logger.info("ℹ️ Non-text message received (photo, document, etc.)")
                return jsonify({"status": "ok", "message": "Non-text message"}), 200

        elif 'callback_query' in data:
            # Handle button callback queries
            result = callback_handler.handle_callback(data)
            return jsonify(result), 200

        else:
            logger.warning("⚠️ Unknown update type")
            return jsonify({"status": "ok", "message": "Unknown update type"}), 200

    except Exception as e:
        logger.error(f"❌ Error handling webhook: {e}")
        import traceback
        traceback.print_exc()
        # Return 200 to prevent Telegram from retrying
        return jsonify({"status": "error", "message": str(e)}), 200

@webhook_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Cloud Run"""
    try:
        # Test database connection
        with current_app.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

        return jsonify({
            "status": "healthy",
            "service": "GCBotCommand-10-26",
            "database": "connected"
        }), 200
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCBotCommand-10-26",
            "error": str(e)
        }), 503

@webhook_bp.route('/set-webhook', methods=['POST'])
def set_webhook():
    """
    Helper endpoint to set Telegram webhook
    Only call this once during initial deployment
    """
    try:
        bot_token = current_app.config['bot_token']

        # Get webhook URL from request or construct from service URL
        data = request.get_json() or {}
        webhook_url = data.get('webhook_url')

        if not webhook_url:
            return jsonify({"error": "webhook_url required"}), 400

        # Call Telegram setWebhook API
        import requests
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": webhook_url}
        )

        result = response.json()
        logger.info(f"✅ Webhook set: {result}")

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")
        return jsonify({"error": str(e)}), 500
```

---

### 5. handlers/command_handler.py (Command Processing)

**Purpose:** Handle /start and /database commands

**Migrates From:**
- `menu_handlers.py` (`start_bot()`, `send_payment_gateway_ready()`)
- `input_handlers.py` (`start_database()`, conversation handlers)

**Implementation:**

```python
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

        message_text = (
            f"💳 <b>Click the button below to Launch the Payment Gateway</b> 🚀\n\n"
            f"🎯 <b>Get access to:</b> {closed_channel_title}\n"
            f"📝 <b>Description:</b> {closed_channel_description}"
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

        message_text = (
            "💾 *DATABASE CONFIGURATION*\n\n"
            "Enter *open_channel_id* (≤14 chars integer):"
        )

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

            return self._send_message(
                chat_id,
                f"✅ *Donation Amount: ${amount:.2f}*\n\n"
                f"Click the button below to complete your donation:",
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
        import requests

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
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return {"status": "error", "message": str(e)}

    def _send_error_message(self, chat_id: int, error_text: str) -> Dict[str, str]:
        """Send error message to user"""
        return self._send_message(chat_id, f"❌ {error_text}")
```

---

### 6. handlers/callback_handler.py (Callback Query Processing)

**Purpose:** Handle all button callback queries

**Migrates From:**
- `menu_handlers.py` (`main_menu_callback()`, `handle_database_callbacks()`)
- `bot_manager.py` (`trigger_payment_handler()`, `handle_cmd_gateway()`)

**Implementation:**

```python
#!/usr/bin/env python
"""
Callback Handler for GCBotCommand
Processes button callback queries
"""
from typing import Dict, Any
from utils.http_client import HTTPClient
import logging

logger = logging.getLogger(__name__)

class CallbackHandler:
    """Handles Telegram callback queries (button clicks)"""

    def __init__(self, db_manager, config):
        self.db = db_manager
        self.config = config
        self.bot_token = config['bot_token']
        self.http_client = HTTPClient()

    def handle_callback(self, update_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Route callback queries to appropriate handlers

        Callback patterns:
        - CMD_DATABASE → Start database flow
        - CMD_GATEWAY → Launch payment gateway
        - TRIGGER_PAYMENT → Process payment
        - EDIT_* → Database form editing
        - SAVE_ALL_CHANGES → Save database changes
        - etc.
        """
        callback_query = update_data['callback_query']
        callback_data = callback_query['data']
        chat_id = callback_query['message']['chat']['id']
        user_id = callback_query['from']['id']
        message_id = callback_query['message']['message_id']

        logger.info(f"🔘 Callback: {callback_data} from user {user_id}")

        # Answer callback query first (required by Telegram)
        self._answer_callback_query(callback_query['id'])

        # Route based on callback_data
        if callback_data == "CMD_DATABASE":
            return self._handle_database_start(chat_id, user_id)

        elif callback_data == "CMD_GATEWAY":
            return self._handle_payment_gateway(chat_id, user_id)

        elif callback_data == "TRIGGER_PAYMENT":
            return self._handle_trigger_payment(chat_id, user_id)

        elif callback_data.startswith("EDIT_"):
            return self._handle_database_edit(chat_id, user_id, message_id, callback_data)

        elif callback_data == "SAVE_ALL_CHANGES":
            return self._handle_save_changes(chat_id, user_id, message_id)

        elif callback_data == "CANCEL_EDIT":
            return self._handle_cancel_edit(chat_id, user_id, message_id)

        elif callback_data.startswith("TOGGLE_TIER_"):
            return self._handle_toggle_tier(chat_id, user_id, message_id, callback_data)

        elif callback_data == "BACK_TO_MAIN":
            return self._handle_back_to_main(chat_id, user_id, message_id)

        else:
            logger.warning(f"⚠️ Unknown callback_data: {callback_data}")
            return {"status": "ok"}

    def _handle_database_start(self, chat_id: int, user_id: int) -> Dict[str, str]:
        """Start database configuration flow"""
        # Initialize database conversation state
        self.db.save_conversation_state(user_id, 'database', {
            'state': 'awaiting_channel_id'
        })

        message_text = (
            "💾 *DATABASE CONFIGURATION*\n\n"
            "Enter *open_channel_id* (≤14 chars integer):"
        )

        return self._send_message(chat_id, message_text, parse_mode='Markdown')

    def _handle_payment_gateway(self, chat_id: int, user_id: int) -> Dict[str, str]:
        """Handle CMD_GATEWAY callback"""
        # Check if user has payment context
        payment_state = self.db.get_conversation_state(user_id, 'payment')

        if not payment_state:
            return self._send_message(chat_id, "❌ No payment context found. Please start from a subscription link.")

        # Call GCPaymentGateway
        return self._create_payment_invoice(chat_id, user_id, payment_state)

    def _handle_trigger_payment(self, chat_id: int, user_id: int) -> Dict[str, str]:
        """Handle TRIGGER_PAYMENT callback"""
        # Same as CMD_GATEWAY
        return self._handle_payment_gateway(chat_id, user_id)

    def _create_payment_invoice(self, chat_id: int, user_id: int, payment_state: Dict) -> Dict[str, str]:
        """Create payment invoice via GCPaymentGateway"""
        payment_url = self.config['gcpaymentgateway_url']

        payload = {
            "user_id": user_id,
            "amount": payment_state['price'],
            "open_channel_id": payment_state['channel_id'],
            "subscription_time_days": payment_state['time'],
            "payment_type": payment_state['payment_type']
        }

        response = self.http_client.post(f"{payment_url}/create-invoice", payload)

        if response and response.get('success'):
            invoice_url = response['invoice_url']

            keyboard = {
                "inline_keyboard": [
                    [{"text": "💳 Pay Now", "web_app": {"url": invoice_url}}]
                ]
            }

            message_text = (
                f"💰 *Payment Invoice Created*\n\n"
                f"Amount: ${payment_state['price']:.2f}\n"
                f"Duration: {payment_state['time']} days\n\n"
                f"Click the button below to complete payment:"
            )

            return self._send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            return self._send_message(chat_id, "❌ Failed to create payment invoice")

    def _handle_database_edit(self, chat_id: int, user_id: int, message_id: int, callback_data: str) -> Dict[str, str]:
        """Handle database form editing callbacks"""
        from handlers.database_handler import DatabaseFormHandler

        db_form_handler = DatabaseFormHandler(self.db, self.config)
        return db_form_handler.handle_edit_callback(chat_id, user_id, message_id, callback_data)

    def _handle_save_changes(self, chat_id: int, user_id: int, message_id: int) -> Dict[str, str]:
        """Save database changes"""
        from handlers.database_handler import DatabaseFormHandler

        db_form_handler = DatabaseFormHandler(self.db, self.config)
        return db_form_handler.save_changes(chat_id, user_id, message_id)

    def _handle_cancel_edit(self, chat_id: int, user_id: int, message_id: int) -> Dict[str, str]:
        """Cancel database editing"""
        # Clear conversation state
        self.db.clear_conversation_state(user_id, 'database')

        return self._edit_message(chat_id, message_id, "❌ Editing cancelled. No changes were saved.")

    def _handle_toggle_tier(self, chat_id: int, user_id: int, message_id: int, callback_data: str) -> Dict[str, str]:
        """Handle tier enable/disable toggle"""
        from handlers.database_handler import DatabaseFormHandler

        db_form_handler = DatabaseFormHandler(self.db, self.config)
        return db_form_handler.toggle_tier(chat_id, user_id, message_id, callback_data)

    def _handle_back_to_main(self, chat_id: int, user_id: int, message_id: int) -> Dict[str, str]:
        """Navigate back to main database form"""
        from handlers.database_handler import DatabaseFormHandler

        db_form_handler = DatabaseFormHandler(self.db, self.config)
        return db_form_handler.show_main_form(chat_id, user_id, message_id)

    def _answer_callback_query(self, callback_query_id: str) -> None:
        """Answer callback query (required by Telegram)"""
        import requests

        try:
            requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id},
                timeout=5
            )
        except Exception as e:
            logger.error(f"❌ Error answering callback query: {e}")

    def _send_message(self, chat_id: int, text: str, **kwargs) -> Dict[str, str]:
        """Send message via Telegram Bot API"""
        import requests

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
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return {"status": "error"}

    def _edit_message(self, chat_id: int, message_id: int, text: str, **kwargs) -> Dict[str, str]:
        """Edit existing message"""
        import requests

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
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"❌ Error editing message: {e}")
            return {"status": "error"}
```

---

### 7. handlers/database_handler.py (Database Form Logic)

**Purpose:** Handle database configuration form editing

**Migrates From:**
- `menu_handlers.py` (lines 258-698 - all form functions)
- `input_handlers.py` (`receive_field_input_v2()`, form validation)

**Implementation Summary:**

This handler manages the multi-step database configuration forms:

1. **Main Edit Menu** - Overview with navigation buttons
2. **Open Channel Form** - Edit open channel ID, title, description
3. **Private Channel Form** - Edit closed channel ID, title, description
4. **Payment Tiers Form** - Configure up to 3 subscription tiers (price, time)
5. **Wallet Form** - Edit wallet address and payout currency

**Key Methods:**
- `handle_input()` - Process text input for field values
- `handle_edit_callback()` - Route edit button callbacks
- `show_main_form()` - Display main editing menu
- `show_open_channel_form()` - Display open channel form
- `show_private_channel_form()` - Display private channel form
- `show_payment_tiers_form()` - Display payment tiers form
- `show_wallet_form()` - Display wallet configuration form
- `toggle_tier()` - Enable/disable payment tiers
- `save_changes()` - Save all changes to database

*(Full implementation ~400 lines - similar to menu_handlers.py form functions)*

---

### 8. utils/validators.py (Input Validation)

**Purpose:** Validate all user input

**Migrates From:** `input_handlers.py` (static validation methods)

**Implementation:**

```python
#!/usr/bin/env python
"""
Input validators for GCBotCommand
Validates all user input before processing
"""
from typing import Tuple

def valid_channel_id(text: str) -> bool:
    """Validate channel ID format (≤14 char integer)"""
    if text.lstrip("-").isdigit():
        return len(text) <= 14
    return False

def valid_sub_price(text: str) -> bool:
    """Validate subscription price (0-9999.99 with max 2 decimals)"""
    try:
        val = float(text)
    except ValueError:
        return False
    if not (0 <= val <= 9999.99):
        return False
    parts = text.split(".")
    return len(parts) == 1 or len(parts[1]) <= 2

def valid_sub_time(text: str) -> bool:
    """Validate subscription time (1-999 days)"""
    return text.isdigit() and 1 <= int(text) <= 999

def validate_donation_amount(text: str) -> Tuple[bool, float]:
    """
    Validate donation amount (1-9999 USD with max 2 decimals)

    Returns:
        Tuple of (is_valid, amount_value)
    """
    # Remove $ symbol if present
    if text.startswith('$'):
        text = text[1:]

    try:
        val = float(text)
    except ValueError:
        return False, 0.0

    if not (1.0 <= val <= 9999.99):
        return False, 0.0

    parts = text.split(".")
    if len(parts) == 2 and len(parts[1]) > 2:
        return False, 0.0

    return True, val

def valid_channel_title(text: str) -> bool:
    """Validate channel title (1-100 characters)"""
    return 1 <= len(text.strip()) <= 100

def valid_channel_description(text: str) -> bool:
    """Validate channel description (1-500 characters)"""
    return 1 <= len(text.strip()) <= 500

def valid_wallet_address(text: str) -> bool:
    """Validate wallet address (basic format check)"""
    stripped = text.strip()
    return 10 <= len(stripped) <= 200

def valid_currency(text: str) -> bool:
    """Validate currency code (3-10 uppercase letters)"""
    stripped = text.strip().upper()
    return 2 <= len(stripped) <= 10 and stripped.replace("-", "").replace("_", "").isalpha()
```

---

### 9. utils/token_parser.py (Token Parsing & Decoding)

**Purpose:** Parse and decode subscription/donation tokens from /start command

**Migrates From:**
- `menu_handlers.py` (`start_bot()` token parsing logic)
- `broadcast_manager.py` (hash encoding/decoding)

**Implementation:**

```python
#!/usr/bin/env python
"""
Token Parser for GCBotCommand
Parses subscription and donation tokens from /start command
"""
from typing import Dict, Optional
import base64
import logging

logger = logging.getLogger(__name__)

class TokenParser:
    """Parse and decode Telegram bot tokens"""

    @staticmethod
    def decode_hash(hash_part: str) -> Optional[str]:
        """
        Decode hash to channel ID

        Hash format: base64-encoded channel ID
        """
        try:
            decoded_bytes = base64.urlsafe_b64decode(hash_part + '==')  # Add padding
            channel_id = decoded_bytes.decode('utf-8')
            return channel_id
        except Exception as e:
            logger.error(f"❌ Error decoding hash: {e}")
            return None

    def parse_token(self, token: str) -> Dict:
        """
        Parse subscription or donation token

        Token formats:
        - Subscription: {hash}_{price}_{time}  (e.g., "ABC123_9d99_30")
        - Donation: {hash}_DONATE  (e.g., "ABC123_DONATE")

        Returns:
            Dictionary with parsed token data:
            {
                'type': 'subscription' | 'donation' | 'invalid',
                'channel_id': str,
                'price': float (for subscription),
                'time': int (for subscription)
            }
        """
        try:
            # Split token
            parts = token.split('_')

            if len(parts) < 2:
                return {'type': 'invalid'}

            hash_part = parts[0]
            remaining = '_'.join(parts[1:])

            # Decode hash to channel ID
            channel_id = self.decode_hash(hash_part)

            if not channel_id:
                return {'type': 'invalid'}

            # Check if donation token
            if remaining == "DONATE":
                return {
                    'type': 'donation',
                    'channel_id': channel_id
                }

            # Parse subscription token: {price}_{time}
            if '_' in remaining:
                sub_part, time_part = remaining.rsplit('_', 1)

                try:
                    time = int(time_part)
                except ValueError:
                    time = 30  # Default

                # Parse price (format: "9d99" → 9.99)
                price_str = sub_part.replace('d', '.')
                try:
                    price = float(price_str)
                except ValueError:
                    price = 5.0  # Default

                return {
                    'type': 'subscription',
                    'channel_id': channel_id,
                    'price': price,
                    'time': time
                }

            # Old format without time
            price_str = remaining.replace('d', '.')
            try:
                price = float(price_str)
            except ValueError:
                price = 5.0

            return {
                'type': 'subscription',
                'channel_id': channel_id,
                'price': price,
                'time': 30  # Default time
            }

        except Exception as e:
            logger.error(f"❌ Error parsing token: {e}")
            return {'type': 'invalid'}

    @staticmethod
    def encode_hash(channel_id: str) -> str:
        """
        Encode channel ID to hash

        Used for generating tokens (usually done by broadcast service)
        """
        try:
            encoded = base64.urlsafe_b64encode(channel_id.encode('utf-8'))
            return encoded.decode('utf-8').rstrip('=')  # Remove padding
        except Exception as e:
            logger.error(f"❌ Error encoding hash: {e}")
            return ""
```

---

### 10. utils/http_client.py (HTTP Requests to External Services)

**Purpose:** Make HTTP requests to GCPaymentGateway and GCDonationHandler

**Implementation:**

```python
#!/usr/bin/env python
"""
HTTP Client for GCBotCommand
Makes requests to external services
"""
import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class HTTPClient:
    """HTTP client for calling external services"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()

    def post(self, url: str, data: Dict) -> Optional[Dict]:
        """
        Make POST request to external service

        Args:
            url: Service URL
            data: Request payload

        Returns:
            Response JSON or None on error
        """
        try:
            logger.info(f"📤 POST {url}")
            logger.debug(f"📦 Payload: {data}")

            response = self.session.post(
                url,
                json=data,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )

            response.raise_for_status()

            result = response.json()
            logger.info(f"✅ Response: {result}")

            return result

        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout calling {url}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error calling {url}: {e}")
            return None

        except ValueError as e:
            logger.error(f"❌ Invalid JSON response from {url}: {e}")
            return None

    def get(self, url: str) -> Optional[Dict]:
        """
        Make GET request to external service

        Args:
            url: Service URL

        Returns:
            Response JSON or None on error
        """
        try:
            logger.info(f"📥 GET {url}")

            response = self.session.get(
                url,
                timeout=self.timeout
            )

            response.raise_for_status()

            result = response.json()
            logger.info(f"✅ Response: {result}")

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error calling {url}: {e}")
            return None
```

---

## Webhook Implementation

### Setting Up Telegram Webhook

After deploying GCBotCommand to Cloud Run, set the Telegram webhook:

```bash
# Get the deployed service URL
SERVICE_URL=$(gcloud run services describe gcbotcommand-10-26 \
  --region=us-central1 \
  --format='value(status.url)')

# Set webhook
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"${SERVICE_URL}/webhook\"}"

# Verify webhook
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

**Expected Response:**

```json
{
  "ok": true,
  "result": {
    "url": "https://gcbotcommand-10-26-pjxwjsdktq-uc.a.run.app/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

---

## Deployment Strategy

### 1. Dockerfile

```dockerfile
# Use official Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Set environment variable for port
ENV PORT=8080

# Run application
CMD ["python", "service.py"]
```

### 2. requirements.txt

```
Flask==3.0.0
psycopg2-binary==2.9.9
google-cloud-secret-manager==2.16.4
requests==2.31.0
```

### 3. .dockerignore

```
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.log
.env
venv/
.venv/
tests/
.git/
.gitignore
README.md
```

### 4. Deploy to Cloud Run

```bash
# Navigate to service directory
cd GCBotCommand-10-26/

# Deploy to Cloud Run
gcloud run deploy gcbotcommand-10-26 \
  --source=. \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
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

# Set Telegram webhook
SERVICE_URL=$(gcloud run services describe gcbotcommand-10-26 \
  --region=us-central1 \
  --format='value(status.url)')

curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"${SERVICE_URL}/webhook\"}"
```

---

## Testing Strategy

### 1. Unit Tests

```python
# tests/test_validators.py
import pytest
from utils.validators import valid_channel_id, validate_donation_amount

def test_valid_channel_id():
    assert valid_channel_id("-1003268562225") == True
    assert valid_channel_id("12345") == True
    assert valid_channel_id("123456789012345") == False  # Too long
    assert valid_channel_id("abc123") == False  # Not numeric

def test_validate_donation_amount():
    is_valid, amount = validate_donation_amount("25.50")
    assert is_valid == True
    assert amount == 25.50

    is_valid, amount = validate_donation_amount("$100")
    assert is_valid == True
    assert amount == 100.0

    is_valid, amount = validate_donation_amount("0.50")
    assert is_valid == False  # Below minimum
```

### 2. Integration Tests

```python
# tests/test_webhook.py
import requests

def test_webhook_health():
    """Test health check endpoint"""
    response = requests.get("http://localhost:8080/health")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'

def test_webhook_start_command():
    """Test /start command processing"""
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

---

## Migration Checklist

### Phase 1: Setup & Infrastructure

- [ ] Create GCBotCommand-10-26/ directory structure
- [ ] Copy and adapt config_manager.py (no shared modules)
- [ ] Copy and adapt database_manager.py (no shared modules)
- [ ] Create service.py with Flask application factory
- [ ] Create Dockerfile and requirements.txt
- [ ] Set up .env.example for local testing

### Phase 2: Core Handlers

- [ ] Implement routes/webhook.py with /webhook and /health endpoints
- [ ] Implement handlers/command_handler.py for /start and /database
- [ ] Implement handlers/callback_handler.py for button callbacks
- [ ] Implement utils/validators.py with all validation functions
- [ ] Implement utils/token_parser.py with hash decoding logic
- [ ] Implement utils/http_client.py for external service calls

### Phase 3: Database Form Logic

- [ ] Implement handlers/database_handler.py with all form functions
- [ ] Migrate all inline keyboard form layouts
- [ ] Implement conversation state management via database
- [ ] Test database editing flow end-to-end

### Phase 4: Testing

- [ ] Write unit tests for validators
- [ ] Write unit tests for token parser
- [ ] Write integration tests for webhook endpoints
- [ ] Test /start command with various token formats
- [ ] Test database editing conversation flow
- [ ] Test payment gateway routing
- [ ] Load test with 100 concurrent requests

### Phase 5: Deployment

- [ ] Deploy to Cloud Run with correct environment variables
- [ ] Set Telegram webhook URL
- [ ] Verify webhook is receiving updates
- [ ] Test all commands in production
- [ ] Monitor logs for errors
- [ ] Set up Cloud Monitoring alerts

### Phase 6: Cutover

- [ ] Run parallel testing (old bot + new webhook)
- [ ] Monitor for 24 hours
- [ ] Gradually increase traffic to new service
- [ ] Decommission old monolithic bot
- [ ] Archive TelePay10-26 code

---

## Conclusion

This architecture document provides a **comprehensive, step-by-step guide** for refactoring TelePay's bot command handling into the **GCBotCommand-10-26 webhook service**.

### Key Achievements

✅ **No Shared Modules:** All code is self-contained within GCBotCommand-10-26/
✅ **Webhook-Based:** Stateless operation using Telegram webhooks
✅ **Complete Migration:** All 2,402 lines of bot logic migrated systematically
✅ **Flask Best Practices:** Application factory pattern, blueprints, error handling
✅ **Scalable:** Horizontal scaling with Cloud Run
✅ **Testable:** Clear separation of concerns enables comprehensive testing

### Next Steps

1. Review and approve this architecture document
2. Begin Phase 1: Setup & Infrastructure
3. Implement handlers phase-by-phase
4. Test thoroughly before production deployment
5. Monitor and optimize post-deployment

**Document Owner:** Claude
**Review Date:** 2025-11-12
**Next Review:** After Phase 1 completion
