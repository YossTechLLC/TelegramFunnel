# GCNotificationService Refactoring Architecture
## Standalone Webhook Service for Payment Notifications

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Architecture Design
**Branch:** TelePay-REFACTOR
**Service Type:** Cloud Run Webhook (Flask)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Service Purpose & Scope](#service-purpose--scope)
3. [Current State Analysis](#current-state-analysis)
4. [Target Architecture](#target-architecture)
5. [Detailed File Structure](#detailed-file-structure)
6. [Module Specifications](#module-specifications)
7. [API Endpoints](#api-endpoints)
8. [Integration Points](#integration-points)
9. [Database Schema Requirements](#database-schema-requirements)
10. [Deployment Configuration](#deployment-configuration)
11. [Migration Steps](#migration-steps)
12. [Testing Strategy](#testing-strategy)
13. [Monitoring & Observability](#monitoring--observability)

---

## Executive Summary

### Problem Statement

Currently, payment notifications are handled by `notification_service.py` within the **monolithic TelePay10-26 bot**. This creates several issues:
- Notifications depend on the bot process being running
- Cannot scale notification delivery independently
- Difficult to test notification logic in isolation
- Mixed concerns with bot command handling

### Solution Overview

**Extract notification functionality into a standalone Cloud Run webhook service** that can be called by any payment-processing webhook (np-webhook, gcwebhook1, gcwebhook2, gcsplit1, gchostpay1).

### Architecture Principle: Self-Contained Service

🚨 **CRITICAL:** This service will **NOT use shared modules**. All required functionality will be **copied and included directly** within the service directory. This ensures:
- ✅ Service is fully self-contained
- ✅ No external dependencies on shared code
- ✅ Independent deployment and evolution
- ✅ Simplified debugging and testing
- ✅ No version conflicts between services

---

## Service Purpose & Scope

### Primary Responsibility

**Send payment notifications to channel owners via Telegram Bot API**

### Specific Functions

1. ✅ Receive notification requests via HTTP POST
2. ✅ Fetch notification settings from database (notification_status, notification_id)
3. ✅ Fetch channel details for message formatting
4. ✅ Format notification messages based on payment type (subscription vs donation)
5. ✅ Send formatted message to channel owner via Telegram Bot API
6. ✅ Handle errors gracefully (user blocked bot, invalid chat_id, etc.)
7. ✅ Return success/failure status to caller

### Out of Scope

- ❌ Payment validation (handled by np-webhook-10-26)
- ❌ Payment routing (handled by gcwebhook1-10-26)
- ❌ Channel invitation (handled by gcwebhook2-10-26)
- ❌ Payout processing (handled by gcsplit1/gchostpay1)
- ❌ Database schema changes
- ❌ Subscription expiration monitoring

---

## Current State Analysis

### Source Code Location

```
TelePay10-26/
├── notification_service.py       # Main notification logic (274 lines)
├── database.py                    # Database operations (contains methods we need)
│   ├── get_notification_settings()     # Lines 621-658
│   └── get_channel_details_by_open_id() # Lines 318-367
└── config_manager.py              # Secret Manager integration
```

### Key Dependencies

#### 1. notification_service.py
- **NotificationService class** (lines 16-273)
- Methods:
  - `send_payment_notification()` - Main entry point
  - `_format_notification_message()` - Message formatting
  - `_send_telegram_message()` - Telegram API integration
  - `test_notification()` - Test functionality

#### 2. database.py (Partial)
- **get_notification_settings()** - Fetch (notification_status, notification_id)
- **get_channel_details_by_open_id()** - Fetch channel title/description
- **Database connection management** - psycopg2 connection setup

#### 3. config_manager.py (Partial)
- **Secret Manager integration** - Fetch secrets from Google Secret Manager
- **fetch_telegram_token()** - Get bot token
- **fetch_database_*()** - Get database credentials

### Current Integration Points

The notification service is currently called from:
1. **np-webhook-10-26** - After IPN validation
2. **gcwebhook1-10-26** - After payment routing
3. **gcwebhook2-10-26** - After telegram invite
4. **gcsplit1-10-26** - After instant payout
5. **gchostpay1-10-26** - After crypto payout

❌ **Problem:** All these services currently assume notification_service.py is running in the same process (monolithic bot)

✅ **Solution:** Convert to HTTP webhook so any service can call via POST request

---

## Target Architecture

### High-Level Service Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Payment Processing Webhooks                   │
│  (np-webhook, gcwebhook1, gcwebhook2, gcsplit1, gchostpay1)    │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP POST
                          │ /send-notification
                          ▼
                 ┌────────────────────┐
                 │ GCNotificationService│
                 │   (Cloud Run)       │
                 │                     │
                 │  ┌──────────────┐  │
                 │  │ Flask Server │  │
                 │  │  (Port 8080) │  │
                 │  └──────┬───────┘  │
                 │         │          │
                 │         ▼          │
                 │  ┌──────────────┐  │
                 │  │  Notification│  │
                 │  │    Handler   │  │
                 │  └──────┬───────┘  │
                 │         │          │
                 │    ┌────┴────┐     │
                 │    ▼         ▼     │
                 │  ┌────┐   ┌────┐  │
                 │  │ DB │   │ TG │  │
                 │  │Mgr │   │Bot │  │
                 │  └────┘   └────┘  │
                 └────────────────────┘
                          │
                          ▼
                 ┌────────────────────┐
                 │   PostgreSQL DB    │
                 │  (telepaypsql)     │
                 └────────────────────┘
                          │
                          ▼
                 ┌────────────────────┐
                 │ Telegram Bot API   │
                 │  (sendMessage)     │
                 └────────────────────┘
```

### Service Components

1. **Flask Application** - HTTP server (application factory pattern)
2. **Config Manager** - Secret Manager integration
3. **Database Manager** - PostgreSQL connection & queries
4. **Notification Handler** - Business logic (formatting, sending)
5. **Telegram Client** - Bot API wrapper

### Request/Response Flow

```
1. POST /send-notification
   ↓
2. Validate request payload
   ↓
3. Fetch notification settings from database
   ↓
4. Check if notifications enabled
   ↓
5. Fetch channel details for formatting
   ↓
6. Format notification message
   ↓
7. Send via Telegram Bot API
   ↓
8. Return success/failure response
```

---

## Detailed File Structure

### Complete Service Directory

```
GCNotificationService-10-26/
├── Dockerfile                          # Container definition
├── requirements.txt                    # Python dependencies
├── .dockerignore                       # Exclude unnecessary files
├── .env.example                        # Example environment variables
│
├── service.py                          # Main Flask app (application factory)
│
├── config_manager.py                   # Secret Manager integration
│                                       # (COPIED from TelePay10-26)
│
├── database_manager.py                 # Database operations
│                                       # (EXTRACTED from TelePay10-26/database.py)
│
├── notification_handler.py             # Notification business logic
│                                       # (EXTRACTED from TelePay10-26/notification_service.py)
│
├── telegram_client.py                  # Telegram Bot API wrapper
│                                       # (NEW - wraps python-telegram-bot)
│
├── validators.py                       # Input validation utilities
│                                       # (NEW)
│
└── README.md                           # Service documentation
```

### Why Self-Contained?

Each file is **completely independent** and includes all necessary code:

| File | Source | Action | Reason |
|------|--------|--------|--------|
| `config_manager.py` | TelePay10-26/config_manager.py | **COPY** | Avoid shared config dependency |
| `database_manager.py` | TelePay10-26/database.py | **EXTRACT** | Only include needed methods |
| `notification_handler.py` | TelePay10-26/notification_service.py | **EXTRACT** | Core notification logic |
| `telegram_client.py` | N/A | **NEW** | Wrap Telegram Bot API |
| `validators.py` | N/A | **NEW** | Input validation |
| `service.py` | N/A | **NEW** | Flask application factory |

---

## Module Specifications

### 1. service.py (Main Flask Application)

**Purpose:** HTTP server with application factory pattern

**Structure:**
```python
#!/usr/bin/env python
"""
📬 GCNotificationService - Standalone Notification Webhook
Sends payment notifications to channel owners via Telegram Bot API
Version: 1.0
Date: 2025-11-12
"""
from flask import Flask, request, jsonify, abort
from config_manager import ConfigManager
from database_manager import DatabaseManager
from notification_handler import NotificationHandler
from telegram_client import TelegramClient
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def create_app():
    """
    Application factory for Flask app

    Returns:
        Flask application instance
    """
    app = Flask(__name__)

    # Initialize configuration
    logger.info("📬 [INIT] Initializing GCNotificationService...")
    config_manager = ConfigManager()
    config = config_manager.initialize_config()

    # Validate configuration
    if not config['bot_token']:
        logger.error("❌ [INIT] Bot token not available")
        raise RuntimeError("Bot token not available from Secret Manager")

    if not config['database_credentials']['host']:
        logger.error("❌ [INIT] Database credentials not available")
        raise RuntimeError("Database credentials not available from Secret Manager")

    # Initialize database manager
    db_manager = DatabaseManager(
        host=config['database_credentials']['host'],
        port=config['database_credentials']['port'],
        dbname=config['database_credentials']['dbname'],
        user=config['database_credentials']['user'],
        password=config['database_credentials']['password']
    )

    # Initialize Telegram client
    telegram_client = TelegramClient(bot_token=config['bot_token'])

    # Initialize notification handler
    notification_handler = NotificationHandler(
        db_manager=db_manager,
        telegram_client=telegram_client
    )

    # Store in app context
    app.config['notification_handler'] = notification_handler

    logger.info("✅ [INIT] GCNotificationService initialized successfully")

    # ============== ROUTES ==============

    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint for Cloud Run"""
        return jsonify({
            'status': 'healthy',
            'service': 'GCNotificationService',
            'version': '1.0'
        }), 200

    @app.route('/send-notification', methods=['POST'])
    def send_notification():
        """
        Send payment notification to channel owner

        Request Body:
        {
            "open_channel_id": "-1003268562225",
            "payment_type": "subscription",  // or "donation"
            "payment_data": {
                "user_id": 6271402111,
                "username": "john_doe",
                "amount_crypto": "0.00034",
                "amount_usd": "9.99",
                "crypto_currency": "ETH",
                "tier": 1,                    // subscription only
                "tier_price": "9.99",         // subscription only
                "duration_days": 30,          // subscription only
                "timestamp": "2025-11-12 14:32:15 UTC"
            }
        }

        Response:
        {
            "status": "success",
            "message": "Notification sent successfully"
        }
        """
        try:
            # Validate request
            if not request.is_json:
                logger.warning("⚠️ [REQUEST] Non-JSON request received")
                abort(400, "Content-Type must be application/json")

            data = request.get_json()

            # Validate required fields
            required = ['open_channel_id', 'payment_type', 'payment_data']
            if not all(k in data for k in required):
                missing = [k for k in required if k not in data]
                logger.warning(f"⚠️ [REQUEST] Missing fields: {missing}")
                abort(400, f"Missing required fields: {missing}")

            # Extract data
            open_channel_id = data['open_channel_id']
            payment_type = data['payment_type']
            payment_data = data['payment_data']

            # Validate payment_type
            if payment_type not in ['subscription', 'donation']:
                logger.warning(f"⚠️ [REQUEST] Invalid payment_type: {payment_type}")
                abort(400, "payment_type must be 'subscription' or 'donation'")

            logger.info(f"📬 [REQUEST] Notification request received")
            logger.info(f"   Channel ID: {open_channel_id}")
            logger.info(f"   Payment Type: {payment_type}")

            # Process notification
            handler = app.config['notification_handler']
            success = handler.send_payment_notification(
                open_channel_id=open_channel_id,
                payment_type=payment_type,
                payment_data=payment_data
            )

            if success:
                logger.info("✅ [REQUEST] Notification sent successfully")
                return jsonify({
                    'status': 'success',
                    'message': 'Notification sent successfully'
                }), 200
            else:
                logger.warning("⚠️ [REQUEST] Notification failed (disabled or error)")
                return jsonify({
                    'status': 'failed',
                    'message': 'Notification not sent (disabled or error)'
                }), 200

        except Exception as e:
            logger.error(f"❌ [REQUEST] Unexpected error: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    @app.route('/test-notification', methods=['POST'])
    def test_notification():
        """
        Send a test notification

        Request Body:
        {
            "chat_id": 123456789,
            "channel_title": "Test Channel"
        }
        """
        try:
            data = request.get_json()

            if not data or 'chat_id' not in data:
                abort(400, "Missing 'chat_id' field")

            chat_id = data['chat_id']
            channel_title = data.get('channel_title', 'Test Channel')

            handler = app.config['notification_handler']
            success = handler.test_notification(
                chat_id=chat_id,
                channel_title=channel_title
            )

            if success:
                return jsonify({
                    'status': 'success',
                    'message': 'Test notification sent'
                }), 200
            else:
                return jsonify({
                    'status': 'failed',
                    'message': 'Test notification failed'
                }), 200

        except Exception as e:
            logger.error(f"❌ [TEST] Error: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
```

---

### 2. config_manager.py (Secret Manager Integration)

**Purpose:** Fetch configuration from Google Secret Manager

**Source:** COPIED from TelePay10-26/config_manager.py with modifications

**Structure:**
```python
#!/usr/bin/env python
"""
🔐 Configuration Manager for GCNotificationService
Fetches secrets from Google Secret Manager
"""
import os
from google.cloud import secretmanager
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration and secrets for notification service"""

    def __init__(self):
        """Initialize configuration manager"""
        self.bot_token = None
        self.database_credentials = {}

    def fetch_secret(self, env_var_name: str, secret_name: str) -> Optional[str]:
        """
        Fetch a secret from Google Secret Manager

        Args:
            env_var_name: Name of environment variable containing secret path
            secret_name: Human-readable name for logging

        Returns:
            Secret value or None if error
        """
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv(env_var_name)

            if not secret_path:
                logger.error(f"❌ [CONFIG] Environment variable {env_var_name} is not set")
                return None

            response = client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")

            logger.info(f"✅ [CONFIG] Successfully fetched {secret_name}")
            return secret_value

        except Exception as e:
            logger.error(f"❌ [CONFIG] Error fetching {secret_name}: {e}")
            return None

    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch Telegram bot token from Secret Manager"""
        return self.fetch_secret(
            env_var_name="TELEGRAM_BOT_TOKEN_SECRET",
            secret_name="Telegram Bot Token"
        )

    def fetch_database_credentials(self) -> Dict[str, Optional[str]]:
        """
        Fetch all database credentials from Secret Manager

        Returns:
            Dictionary with keys: host, port, dbname, user, password
        """
        return {
            'host': self.fetch_secret(
                env_var_name="DATABASE_HOST_SECRET",
                secret_name="Database Host"
            ),
            'port': 5432,  # Standard PostgreSQL port
            'dbname': self.fetch_secret(
                env_var_name="DATABASE_NAME_SECRET",
                secret_name="Database Name"
            ),
            'user': self.fetch_secret(
                env_var_name="DATABASE_USER_SECRET",
                secret_name="Database User"
            ),
            'password': self.fetch_secret(
                env_var_name="DATABASE_PASSWORD_SECRET",
                secret_name="Database Password"
            )
        }

    def initialize_config(self) -> Dict:
        """
        Initialize and return all configuration values

        Returns:
            Dictionary containing all config values
        """
        logger.info("🔐 [CONFIG] Initializing configuration...")

        # Fetch bot token
        self.bot_token = self.fetch_telegram_token()

        # Fetch database credentials
        self.database_credentials = self.fetch_database_credentials()

        # Validate critical config
        if not self.bot_token:
            logger.error("❌ [CONFIG] Bot token is missing")

        if not all([
            self.database_credentials['host'],
            self.database_credentials['dbname'],
            self.database_credentials['user'],
            self.database_credentials['password']
        ]):
            logger.error("❌ [CONFIG] Database credentials are incomplete")

        logger.info("✅ [CONFIG] Configuration initialized")

        return {
            'bot_token': self.bot_token,
            'database_credentials': self.database_credentials
        }
```

---

### 3. database_manager.py (Database Operations)

**Purpose:** PostgreSQL connection and notification-specific queries

**Source:** EXTRACTED from TelePay10-26/database.py (only relevant methods)

**Structure:**
```python
#!/usr/bin/env python
"""
🗄️ Database Manager for GCNotificationService
Handles PostgreSQL connections and notification queries
"""
import psycopg2
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and notification queries"""

    def __init__(self, host: str, port: int, dbname: str, user: str, password: str):
        """
        Initialize database manager

        Args:
            host: Database host (Cloud SQL Unix socket or IP)
            port: Database port (default 5432)
            dbname: Database name
            user: Database user
            password: Database password
        """
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password

        # Validate credentials
        if not self.password:
            raise RuntimeError("Database password not available. Cannot initialize DatabaseManager.")
        if not all([self.host, self.dbname, self.user]):
            raise RuntimeError("Critical database configuration missing.")

        logger.info(f"🗄️ [DATABASE] Initialized (host={host}, dbname={dbname})")

    def get_connection(self):
        """
        Create and return a database connection

        Returns:
            psycopg2 connection object
        """
        try:
            conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            return conn
        except Exception as e:
            logger.error(f"❌ [DATABASE] Connection error: {e}")
            raise

    def get_notification_settings(self, open_channel_id: str) -> Optional[Tuple[bool, Optional[int]]]:
        """
        Get notification settings for a channel

        Args:
            open_channel_id: The open channel ID to look up

        Returns:
            Tuple of (notification_status, notification_id) if found, None otherwise

        Example:
            >>> db.get_notification_settings("-1003268562225")
            (True, 123456789)
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT notification_status, notification_id
                FROM main_clients_database
                WHERE open_channel_id = %s
            """, (str(open_channel_id),))

            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                notification_status, notification_id = result
                logger.info(
                    f"✅ [DATABASE] Settings for {open_channel_id}: "
                    f"enabled={notification_status}, id={notification_id}"
                )
                return notification_status, notification_id
            else:
                logger.warning(f"⚠️ [DATABASE] No settings found for {open_channel_id}")
                return None

        except Exception as e:
            logger.error(f"❌ [DATABASE] Error fetching notification settings: {e}")
            return None

    def get_channel_details_by_open_id(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch channel details by open_channel_id for notification message formatting

        Args:
            open_channel_id: The open channel ID to fetch details for

        Returns:
            Dict containing channel details or None if not found:
            {
                "closed_channel_title": str,
                "closed_channel_description": str
            }

        Example:
            >>> db.get_channel_details_by_open_id("-1003268562225")
            {
                "closed_channel_title": "Premium SHIBA Channel",
                "closed_channel_description": "Exclusive content"
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
                logger.info(f"✅ [DATABASE] Fetched channel details for {open_channel_id}")
                return channel_details
            else:
                logger.warning(f"⚠️ [DATABASE] No channel details found for {open_channel_id}")
                return None

        except Exception as e:
            logger.error(f"❌ [DATABASE] Error fetching channel details: {e}")
            return None
```

---

### 4. notification_handler.py (Business Logic)

**Purpose:** Core notification logic (formatting, sending)

**Source:** EXTRACTED from TelePay10-26/notification_service.py

**Structure:**
```python
#!/usr/bin/env python
"""
📬 Notification Handler for GCNotificationService
Handles notification formatting and delivery logic
"""
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class NotificationHandler:
    """Handles notification business logic"""

    def __init__(self, db_manager, telegram_client):
        """
        Initialize notification handler

        Args:
            db_manager: DatabaseManager instance
            telegram_client: TelegramClient instance
        """
        self.db_manager = db_manager
        self.telegram_client = telegram_client
        logger.info("📬 [HANDLER] Notification handler initialized")

    def send_payment_notification(
        self,
        open_channel_id: str,
        payment_type: str,  # 'subscription' or 'donation'
        payment_data: Dict[str, Any]
    ) -> bool:
        """
        Send payment notification to channel owner

        Args:
            open_channel_id: The channel ID to fetch notification settings for
            payment_type: Type of payment ('subscription' or 'donation')
            payment_data: Dictionary containing payment details
                Required keys:
                - user_id: Customer's Telegram user ID
                - amount_crypto: Amount in cryptocurrency
                - amount_usd: Amount in USD
                - crypto_currency: Cryptocurrency symbol
                - timestamp: Payment timestamp (optional)
                For subscriptions:
                - tier: Subscription tier number
                - tier_price: Tier price in USD
                - duration_days: Subscription duration

        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            logger.info("")
            logger.info("📬 [HANDLER] Processing notification request")
            logger.info(f"   Channel ID: {open_channel_id}")
            logger.info(f"   Payment Type: {payment_type}")

            # Step 1: Fetch notification settings
            settings = self.db_manager.get_notification_settings(open_channel_id)

            if not settings:
                logger.warning(f"⚠️ [HANDLER] No settings found for channel {open_channel_id}")
                return False

            notification_status, notification_id = settings

            # Step 2: Check if notifications enabled
            if not notification_status:
                logger.info(f"📭 [HANDLER] Notifications disabled for channel {open_channel_id}")
                return False

            if not notification_id:
                logger.warning(f"⚠️ [HANDLER] No notification_id set for channel {open_channel_id}")
                return False

            logger.info(f"✅ [HANDLER] Notifications enabled, sending to {notification_id}")

            # Step 3: Format notification message
            message = self._format_notification_message(
                open_channel_id,
                payment_type,
                payment_data
            )

            # Step 4: Send notification
            success = self.telegram_client.send_message(
                chat_id=notification_id,
                text=message,
                parse_mode='HTML'
            )

            if success:
                logger.info(f"✅ [HANDLER] Successfully sent to {notification_id}")
            else:
                logger.warning(f"⚠️ [HANDLER] Failed to send to {notification_id}")

            return success

        except Exception as e:
            logger.error(f"❌ [HANDLER] Error sending notification: {e}", exc_info=True)
            return False

    def _format_notification_message(
        self,
        open_channel_id: str,
        payment_type: str,
        payment_data: Dict[str, Any]
    ) -> str:
        """
        Format notification message based on payment type

        Args:
            open_channel_id: Channel ID
            payment_type: 'subscription' or 'donation'
            payment_data: Payment details

        Returns:
            Formatted message string
        """
        # Fetch channel details for context
        channel_info = self.db_manager.get_channel_details_by_open_id(open_channel_id)
        channel_title = channel_info['closed_channel_title'] if channel_info else 'Your Channel'

        # Extract common fields
        user_id = payment_data.get('user_id', 'Unknown')
        username = payment_data.get('username', None)
        amount_crypto = payment_data.get('amount_crypto', '0')
        amount_usd = payment_data.get('amount_usd', '0')
        crypto_currency = payment_data.get('crypto_currency', 'CRYPTO')
        timestamp = payment_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'))

        # Format user display
        user_display = f"@{username}" if username else f"User ID: {user_id}"

        if payment_type == 'subscription':
            # Subscription payment notification
            tier = payment_data.get('tier', 'Unknown')
            tier_price = payment_data.get('tier_price', '0')
            duration_days = payment_data.get('duration_days', '30')

            message = f"""🎉 <b>New Subscription Payment!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Customer:</b> {user_display}
<b>User ID:</b> <code>{user_id}</code>

<b>Subscription Details:</b>
├ Tier: {tier}
├ Price: ${tier_price} USD
└ Duration: {duration_days} days

<b>Payment Amount:</b>
├ Crypto: {amount_crypto} {crypto_currency}
└ USD Value: ${amount_usd}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via NowPayments IPN"""

        elif payment_type == 'donation':
            # Donation payment notification
            message = f"""💝 <b>New Donation Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Donor:</b> {user_display}
<b>User ID:</b> <code>{user_id}</code>

<b>Donation Amount:</b>
├ Crypto: {amount_crypto} {crypto_currency}
└ USD Value: ${amount_usd}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via NowPayments IPN

Thank you for creating valuable content! 🙏"""

        else:
            # Fallback for unknown payment types
            message = f"""💳 <b>New Payment Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Customer:</b> {user_display}
<b>User ID:</b> <code>{user_id}</code>

<b>Amount:</b> {amount_crypto} {crypto_currency} (${amount_usd} USD)

<b>Timestamp:</b> {timestamp}"""

        return message

    def test_notification(self, chat_id: int, channel_title: str = "Test Channel") -> bool:
        """
        Send a test notification to verify setup

        Args:
            chat_id: Telegram user ID to send test to
            channel_title: Channel name for test message

        Returns:
            True if test successful, False otherwise
        """
        test_message = f"""🧪 <b>Test Notification</b>

This is a test notification for your channel: <b>{channel_title}</b>

If you receive this message, your notification settings are configured correctly!

You will receive notifications when:
• A customer subscribes to a tier
• A customer makes a donation

✅ Notification system is working!"""

        try:
            return self.telegram_client.send_message(
                chat_id=chat_id,
                text=test_message,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ [HANDLER] Test failed: {e}")
            return False
```

---

### 5. telegram_client.py (Telegram Bot API Wrapper)

**Purpose:** Wrap Telegram Bot API for sending messages

**Source:** NEW (wraps python-telegram-bot library)

**Structure:**
```python
#!/usr/bin/env python
"""
🤖 Telegram Client for GCNotificationService
Wraps Telegram Bot API for sending messages
"""
from telegram import Bot
from telegram.error import TelegramError, Forbidden, BadRequest
import logging

logger = logging.getLogger(__name__)


class TelegramClient:
    """Wraps Telegram Bot API for sending messages"""

    def __init__(self, bot_token: str):
        """
        Initialize Telegram client

        Args:
            bot_token: Telegram Bot API token
        """
        if not bot_token:
            raise ValueError("Bot token is required")

        self.bot = Bot(token=bot_token)
        logger.info("🤖 [TELEGRAM] Client initialized")

    def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = 'HTML',
        disable_web_page_preview: bool = True
    ) -> bool:
        """
        Send message via Telegram Bot API

        Args:
            chat_id: Telegram user ID to send to
            text: Message text
            parse_mode: Parsing mode ('HTML', 'Markdown', or None)
            disable_web_page_preview: Disable link previews

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            logger.info(f"📤 [TELEGRAM] Sending message to chat_id {chat_id}")

            # Use synchronous send_message (python-telegram-bot >= 20.x)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(
                self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
            )

            logger.info(f"✅ [TELEGRAM] Message delivered to {chat_id}")
            return True

        except Forbidden as e:
            logger.warning(f"🚫 [TELEGRAM] Bot blocked by user {chat_id}: {e}")
            # User has blocked the bot - this is expected, don't retry
            return False

        except BadRequest as e:
            logger.error(f"❌ [TELEGRAM] Invalid request for {chat_id}: {e}")
            # Invalid chat_id or message format
            return False

        except TelegramError as e:
            logger.error(f"❌ [TELEGRAM] Telegram API error: {e}")
            # Network issues, rate limits, etc.
            return False

        except Exception as e:
            logger.error(f"❌ [TELEGRAM] Unexpected error: {e}", exc_info=True)
            return False
```

---

### 6. validators.py (Input Validation)

**Purpose:** Validate incoming request data

**Source:** NEW

**Structure:**
```python
#!/usr/bin/env python
"""
✅ Validators for GCNotificationService
Input validation utilities
"""
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def validate_notification_request(data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate notification request payload

    Args:
        data: Request data dictionary

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Check required top-level fields
    required_fields = ['open_channel_id', 'payment_type', 'payment_data']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return False, errors

    # Validate open_channel_id format
    if not isinstance(data['open_channel_id'], str):
        errors.append("open_channel_id must be a string")
    elif not data['open_channel_id'].startswith('-'):
        errors.append("open_channel_id must start with '-'")

    # Validate payment_type
    if data['payment_type'] not in ['subscription', 'donation']:
        errors.append("payment_type must be 'subscription' or 'donation'")

    # Validate payment_data
    if not isinstance(data['payment_data'], dict):
        errors.append("payment_data must be a dictionary")
    else:
        payment_data = data['payment_data']

        # Check common required fields
        common_fields = ['user_id', 'amount_crypto', 'amount_usd', 'crypto_currency']
        for field in common_fields:
            if field not in payment_data:
                errors.append(f"payment_data missing field: {field}")

        # Check subscription-specific fields
        if data['payment_type'] == 'subscription':
            subscription_fields = ['tier', 'tier_price', 'duration_days']
            for field in subscription_fields:
                if field not in payment_data:
                    errors.append(f"payment_data missing subscription field: {field}")

    return (len(errors) == 0, errors)


def validate_channel_id(channel_id: str) -> bool:
    """
    Validate that a channel ID is properly formatted

    Args:
        channel_id: Channel ID string

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(channel_id, str):
        return False

    if not channel_id.startswith('-'):
        return False

    if not channel_id.lstrip("-").isdigit():
        return False

    if len(channel_id) > 14:
        return False

    return True
```

---

### 7. Additional Files

#### Dockerfile

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

# Run application
CMD ["python", "service.py"]
```

#### requirements.txt

```txt
flask==3.0.0
psycopg2-binary==2.9.9
python-telegram-bot==20.7
google-cloud-secret-manager==2.16.4
gunicorn==21.2.0
```

#### .dockerignore

```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
*.log
.git/
.gitignore
README.md
.env
.env.example
tests/
```

#### .env.example

```bash
# Environment variables for GCNotificationService

# Telegram Bot Token (Secret Manager path)
TELEGRAM_BOT_TOKEN_SECRET="projects/telepay-459221/secrets/telegram-bot-token/versions/latest"

# Database Credentials (Secret Manager paths)
DATABASE_HOST_SECRET="projects/telepay-459221/secrets/database-host/versions/latest"
DATABASE_NAME_SECRET="projects/telepay-459221/secrets/database-name/versions/latest"
DATABASE_USER_SECRET="projects/telepay-459221/secrets/database-user/versions/latest"
DATABASE_PASSWORD_SECRET="projects/telepay-459221/secrets/database-password/versions/latest"

# Cloud Run port (auto-set by Cloud Run)
PORT=8080
```

---

## API Endpoints

### POST /send-notification

**Purpose:** Send payment notification to channel owner

**Request:**
```json
{
  "open_channel_id": "-1003268562225",
  "payment_type": "subscription",
  "payment_data": {
    "user_id": 6271402111,
    "username": "john_doe",
    "amount_crypto": "0.00034",
    "amount_usd": "9.99",
    "crypto_currency": "ETH",
    "tier": 1,
    "tier_price": "9.99",
    "duration_days": 30,
    "timestamp": "2025-11-12 14:32:15 UTC"
  }
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Notification sent successfully"
}
```

**Response (Disabled):**
```json
{
  "status": "failed",
  "message": "Notification not sent (disabled or error)"
}
```

**Response (Error):**
```json
{
  "status": "error",
  "message": "Missing required fields: ['payment_data']"
}
```

**HTTP Status Codes:**
- `200 OK` - Request processed (check status field for success/failure)
- `400 Bad Request` - Invalid request format
- `500 Internal Server Error` - Unexpected server error

---

### POST /test-notification

**Purpose:** Send test notification to verify setup

**Request:**
```json
{
  "chat_id": 123456789,
  "channel_title": "My Channel"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Test notification sent"
}
```

---

### GET /health

**Purpose:** Health check for Cloud Run

**Response:**
```json
{
  "status": "healthy",
  "service": "GCNotificationService",
  "version": "1.0"
}
```

---

## Integration Points

### Calling Services (Who calls this service?)

All existing payment webhooks will call GCNotificationService:

1. **np-webhook-10-26** (After IPN validation)
2. **gcwebhook1-10-26** (After payment routing)
3. **gcwebhook2-10-26** (After telegram invite)
4. **gcsplit1-10-26** (After instant payout)
5. **gchostpay1-10-26** (After crypto payout)

### Example Integration (np-webhook-10-26)

**Current Code (Before):**
```python
# In np-webhook-10-26 after IPN validation
# Currently trying to call notification_service from monolithic bot
# ❌ This doesn't work because notification_service.py is in TelePay10-26
```

**New Code (After):**
```python
# In np-webhook-10-26 after IPN validation
import requests

GCNOTIFICATIONSERVICE_URL = os.getenv(
    "GCNOTIFICATIONSERVICE_URL",
    "https://gcnotificationservice-10-26-pjxwjsdktq-uc.a.run.app"
)

def send_notification(open_channel_id, payment_type, payment_data):
    """Send notification via GCNotificationService"""
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

### Required Updates to Calling Services

Each webhook needs:
1. **Add environment variable:** `GCNOTIFICATIONSERVICE_URL`
2. **Add dependency:** `requests` library
3. **Replace notification calls** with HTTP POST to GCNotificationService
4. **Handle failures gracefully** (notification failure shouldn't block payment processing)

---

## Database Schema Requirements

### Tables Used

#### main_clients_database

**Columns Used:**
- `open_channel_id` (TEXT, PRIMARY KEY)
- `closed_channel_title` (TEXT)
- `closed_channel_description` (TEXT)
- `notification_status` (BOOLEAN)
- `notification_id` (BIGINT)

**Queries:**
```sql
-- Get notification settings
SELECT notification_status, notification_id
FROM main_clients_database
WHERE open_channel_id = %s;

-- Get channel details
SELECT closed_channel_title, closed_channel_description
FROM main_clients_database
WHERE open_channel_id = %s;
```

### No Schema Changes Required

✅ Service uses **existing schema only**
✅ No new tables needed
✅ No new columns needed
✅ Safe to deploy without database migrations

---

## Deployment Configuration

### Cloud Run Deployment

```bash
#!/bin/bash
# deploy_gcnotificationservice.sh

# Set variables
PROJECT_ID="telepay-459221"
SERVICE_NAME="gcnotificationservice-10-26"
REGION="us-central1"
SERVICE_ACCOUNT="telepay-cloudrun@telepay-459221.iam.gserviceaccount.com"

# Secret Manager paths
TELEGRAM_BOT_TOKEN_SECRET="projects/${PROJECT_ID}/secrets/telegram-bot-token/versions/latest"
DATABASE_HOST_SECRET="projects/${PROJECT_ID}/secrets/database-host/versions/latest"
DATABASE_NAME_SECRET="projects/${PROJECT_ID}/secrets/database-name/versions/latest"
DATABASE_USER_SECRET="projects/${PROJECT_ID}/secrets/database-user/versions/latest"
DATABASE_PASSWORD_SECRET="projects/${PROJECT_ID}/secrets/database-password/versions/latest"

echo "📬 Deploying GCNotificationService..."

gcloud run deploy ${SERVICE_NAME} \
  --source=. \
  --region=${REGION} \
  --platform=managed \
  --allow-unauthenticated \
  --service-account=${SERVICE_ACCOUNT} \
  --set-env-vars="TELEGRAM_BOT_TOKEN_SECRET=${TELEGRAM_BOT_TOKEN_SECRET}" \
  --set-env-vars="DATABASE_HOST_SECRET=${DATABASE_HOST_SECRET}" \
  --set-env-vars="DATABASE_NAME_SECRET=${DATABASE_NAME_SECRET}" \
  --set-env-vars="DATABASE_USER_SECRET=${DATABASE_USER_SECRET}" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=${DATABASE_PASSWORD_SECRET}" \
  --min-instances=0 \
  --max-instances=10 \
  --memory=256Mi \
  --cpu=0.5 \
  --timeout=60s \
  --concurrency=80

echo "✅ Deployment complete!"
echo "Service URL: https://${SERVICE_NAME}-pjxwjsdktq-${REGION:0:2}.a.run.app"
```

### Resource Configuration

| Setting | Value | Reason |
|---------|-------|--------|
| **CPU** | 0.5 | Lightweight service (formatting + API calls) |
| **Memory** | 256Mi | Minimal memory needed |
| **Min Instances** | 0 | Cost optimization (serverless) |
| **Max Instances** | 10 | Handle burst traffic |
| **Timeout** | 60s | Telegram API can be slow |
| **Concurrency** | 80 | Handle multiple notifications |

### Environment Variables

```bash
TELEGRAM_BOT_TOKEN_SECRET="projects/telepay-459221/secrets/telegram-bot-token/versions/latest"
DATABASE_HOST_SECRET="projects/telepay-459221/secrets/database-host/versions/latest"
DATABASE_NAME_SECRET="projects/telepay-459221/secrets/database-name/versions/latest"
DATABASE_USER_SECRET="projects/telepay-459221/secrets/database-user/versions/latest"
DATABASE_PASSWORD_SECRET="projects/telepay-459221/secrets/database-password/versions/latest"
```

### IAM Permissions

Service account `telepay-cloudrun@telepay-459221.iam.gserviceaccount.com` needs:

```bash
# Secret Manager access
gcloud secrets add-iam-policy-binding telegram-bot-token \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding database-host \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Repeat for all database secrets...

# Cloud SQL access (if using Cloud SQL Proxy)
gcloud projects add-iam-policy-binding telepay-459221 \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

---

## Migration Steps

### Phase 1: Build & Test Locally

**Step 1: Create Service Directory**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26
mkdir GCNotificationService-10-26
cd GCNotificationService-10-26
```

**Step 2: Copy Files**
- Copy `notification_service.py` → Extract to `notification_handler.py`
- Copy `database.py` → Extract relevant methods to `database_manager.py`
- Copy `config_manager.py` → Adapt to `config_manager.py`
- Create `service.py` (Flask app)
- Create `telegram_client.py` (Bot API wrapper)
- Create `validators.py` (Input validation)

**Step 3: Test Locally**
```bash
# Set environment variables
export TELEGRAM_BOT_TOKEN_SECRET="projects/telepay-459221/secrets/telegram-bot-token/versions/latest"
export DATABASE_HOST_SECRET="projects/telepay-459221/secrets/database-host/versions/latest"
# ... other secrets

# Run service
python service.py

# Test health endpoint
curl http://localhost:8080/health

# Test notification (with real data)
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

---

### Phase 2: Deploy to Cloud Run

**Step 1: Deploy Service**
```bash
cd GCNotificationService-10-26
bash deploy_gcnotificationservice.sh
```

**Step 2: Get Service URL**
```bash
gcloud run services describe gcnotificationservice-10-26 \
  --region=us-central1 \
  --format='value(status.url)'
```

**Step 3: Test Deployed Service**
```bash
SERVICE_URL="https://gcnotificationservice-10-26-pjxwjsdktq-uc.a.run.app"

# Health check
curl ${SERVICE_URL}/health

# Test notification
curl -X POST ${SERVICE_URL}/send-notification \
  -H "Content-Type: application/json" \
  -d '{...}'  # Same payload as local test
```

---

### Phase 3: Update Calling Services

**Update each webhook to call GCNotificationService:**

**Services to Update:**
1. np-webhook-10-26
2. gcwebhook1-10-26
3. gcwebhook2-10-26
4. gcsplit1-10-26
5. gchostpay1-10-26

**For each service:**

1. **Add environment variable:**
```bash
gcloud run services update <service-name> \
  --set-env-vars="GCNOTIFICATIONSERVICE_URL=https://gcnotificationservice-10-26-pjxwjsdktq-uc.a.run.app"
```

2. **Update code to call HTTP endpoint:**
```python
# Replace old notification calls
# OLD:
# notification_service.send_payment_notification(...)

# NEW:
import requests

response = requests.post(
    f"{GCNOTIFICATIONSERVICE_URL}/send-notification",
    json={...},
    timeout=10
)
```

3. **Redeploy service:**
```bash
gcloud run deploy <service-name> --source=.
```

---

### Phase 4: Monitor & Validate

**Step 1: Check Logs**
```bash
# GCNotificationService logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcnotificationservice-10-26" \
  --limit=50 \
  --format=json

# Look for:
# ✅ "Notification sent successfully"
# ⚠️ "Notifications disabled"
# ❌ "Error sending notification"
```

**Step 2: Test End-to-End**
1. Create a test payment (via Telegram bot)
2. Wait for IPN callback
3. Check if notification delivered to channel owner
4. Verify logs show successful processing

**Step 3: Metrics**
```bash
# Request count
# Error rate
# Latency (p50, p95, p99)
# Success rate
```

---

## Testing Strategy

### Unit Tests

**test_notification_handler.py:**
```python
import pytest
from notification_handler import NotificationHandler
from unittest.mock import Mock

def test_format_subscription_notification():
    db_mock = Mock()
    telegram_mock = Mock()
    handler = NotificationHandler(db_mock, telegram_mock)

    payment_data = {
        "user_id": 123456,
        "username": "test_user",
        "amount_crypto": "0.00034",
        "amount_usd": "9.99",
        "crypto_currency": "ETH",
        "tier": 1,
        "tier_price": "9.99",
        "duration_days": 30
    }

    message = handler._format_notification_message(
        open_channel_id="-1003268562225",
        payment_type="subscription",
        payment_data=payment_data
    )

    assert "New Subscription Payment!" in message
    assert "Tier: 1" in message
    assert "$9.99" in message

def test_send_notification_disabled():
    db_mock = Mock()
    db_mock.get_notification_settings.return_value = (False, None)

    telegram_mock = Mock()
    handler = NotificationHandler(db_mock, telegram_mock)

    result = handler.send_payment_notification(
        open_channel_id="-1003268562225",
        payment_type="subscription",
        payment_data={...}
    )

    assert result == False
    telegram_mock.send_message.assert_not_called()
```

### Integration Tests

**test_integration.py:**
```python
import requests

def test_send_notification_endpoint():
    """Test full HTTP endpoint"""
    response = requests.post(
        "http://localhost:8080/send-notification",
        json={
            "open_channel_id": "-1003268562225",
            "payment_type": "subscription",
            "payment_data": {
                "user_id": 123456,
                "amount_crypto": "0.00034",
                "amount_usd": "9.99",
                "crypto_currency": "ETH",
                "tier": 1,
                "tier_price": "9.99",
                "duration_days": 30
            }
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data['status'] in ['success', 'failed']
```

### Load Testing

**locustfile.py:**
```python
from locust import HttpUser, task, between

class NotificationUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def send_notification(self):
        self.client.post("/send-notification", json={
            "open_channel_id": "-1003268562225",
            "payment_type": "subscription",
            "payment_data": {
                "user_id": 123456,
                "amount_crypto": "0.00034",
                "amount_usd": "9.99",
                "crypto_currency": "ETH",
                "tier": 1,
                "tier_price": "9.99",
                "duration_days": 30
            }
        })
```

Run: `locust -f locustfile.py --host=https://gcnotificationservice-10-26-pjxwjsdktq-uc.a.run.app`

---

## Monitoring & Observability

### Cloud Logging Queries

**All Notifications:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcnotificationservice-10-26"
```

**Successful Notifications:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcnotificationservice-10-26"
"Notification sent successfully"
```

**Failed Notifications:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcnotificationservice-10-26"
"Notification failed"
```

**Errors:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcnotificationservice-10-26"
severity>=ERROR
```

### Metrics to Monitor

| Metric | Target | Alert Threshold |
|--------|--------|----------------|
| **Request Count** | N/A | N/A |
| **Success Rate** | > 90% | < 85% |
| **Latency (p95)** | < 2s | > 5s |
| **Error Rate** | < 5% | > 10% |
| **Database Connection Errors** | 0 | > 5/hour |
| **Telegram API Errors** | < 2% | > 5% |

### Dashboards

Create Cloud Monitoring dashboard with:
1. Request rate (requests/second)
2. Error rate (%)
3. Latency percentiles (p50, p95, p99)
4. Success vs failure count
5. Database query latency
6. Telegram API response time

---

## Appendix: Self-Contained Design Benefits

### Why NO Shared Modules?

**Problems with Shared Modules:**
- ❌ Version conflicts between services
- ❌ Deployment complexity (must update all services)
- ❌ Tight coupling (change in shared module breaks multiple services)
- ❌ Debugging difficulty (which version is running?)
- ❌ Testing complexity (must mock shared dependencies)

**Benefits of Self-Contained Services:**
- ✅ **Independence:** Each service evolves at its own pace
- ✅ **Simplicity:** No external dependencies
- ✅ **Reliability:** Service A doesn't break Service B
- ✅ **Debugging:** All code is in one place
- ✅ **Testing:** Easy to mock and test
- ✅ **Deployment:** Deploy once, works forever

### Code Duplication is Acceptable

**"Duplication is far cheaper than the wrong abstraction"** - Sandi Metz

In microservices architecture, **copying code is better than sharing code** when:
- Services have different lifecycles
- Services are owned by different teams
- Services have different performance requirements
- Services need to evolve independently

---

## Summary Checklist

### Before Starting Migration

- [ ] Review this architecture document
- [ ] Understand current notification_service.py functionality
- [ ] Identify all services that call notification functionality
- [ ] Test database queries in PostgreSQL
- [ ] Verify Secret Manager secrets exist
- [ ] Confirm Telegram bot token works

### During Migration

- [ ] Create GCNotificationService-10-26 directory
- [ ] Copy and adapt all modules (self-contained)
- [ ] Test locally with curl
- [ ] Deploy to Cloud Run
- [ ] Test deployed service with curl
- [ ] Update calling services one by one
- [ ] Monitor logs for errors

### After Migration

- [ ] All notifications working via HTTP
- [ ] No errors in Cloud Logging
- [ ] Success rate > 90%
- [ ] Latency < 2 seconds (p95)
- [ ] Archive TelePay10-26/notification_service.py
- [ ] Document service URL for future reference

---

**Document Owner:** Claude
**Review Date:** 2025-11-12
**Status:** Ready for Implementation
**Next Steps:** Begin Phase 1 - Build & Test Locally
