# GCSubscriptionMonitor Refactoring Architecture
## Standalone Webhook Service for Subscription Expiration Monitoring

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Architecture Design
**Branch:** TelePay-REFACTOR
**Service Type:** Cloud Run HTTP Webhook (Triggered by Cloud Scheduler)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Service Structure](#service-structure)
5. [Module Specifications](#module-specifications)
6. [Database Operations](#database-operations)
7. [Telegram Bot API Integration](#telegram-bot-api-integration)
8. [Error Handling & Recovery](#error-handling--recovery)
9. [Deployment Configuration](#deployment-configuration)
10. [Testing Strategy](#testing-strategy)
11. [Migration Plan](#migration-plan)

---

## Executive Summary

### Purpose
Transform the subscription monitoring functionality from a long-running background task in the monolithic TelePay bot into a **standalone, serverless Cloud Run webhook** triggered by Cloud Scheduler.

### Current Problem
The existing `subscription_manager.py` runs as an **infinite loop** within the TelePay bot:
- Consumes resources 24/7 with `asyncio.sleep(60)` loops
- Cannot scale independently
- Tied to bot uptime (if bot crashes, monitoring stops)
- Difficult to monitor and debug

### Solution
Create **GCSubscriptionMonitor-10-26** as a standalone Flask webhook service that:
- ✅ Runs only when triggered by Cloud Scheduler (every 60 seconds)
- ✅ Scales automatically based on load
- ✅ Operates independently of bot availability
- ✅ Provides clear observability through Cloud Logging
- ✅ Contains all necessary modules internally (no shared dependencies)

### Key Responsibilities
1. **Query Expired Subscriptions:** Fetch all active subscriptions where `expire_datetime < NOW()`
2. **Remove Users from Channels:** Use Telegram Bot API to ban + unban users
3. **Update Database:** Mark subscriptions as `is_active = FALSE`
4. **Return Statistics:** Report number of processed expirations

---

## Current State Analysis

### Existing Implementation

**File:** `TelePay10-26/subscription_manager.py`

**Key Components:**
```python
class SubscriptionManager:
    def __init__(self, bot_token: str, db_manager: DatabaseManager):
        self.bot_token = bot_token
        self.db_manager = db_manager
        self.bot = Bot(token=bot_token)
        self.is_running = False

    async def start_monitoring(self):
        """Infinite loop running every 60 seconds"""
        self.is_running = True
        while self.is_running:
            try:
                await self.check_expired_subscriptions()
                await asyncio.sleep(60)  # ⚠️ Long-running background task
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)

    async def check_expired_subscriptions(self):
        """Main processing logic"""
        expired_subscriptions = self.fetch_expired_subscriptions()

        for subscription in expired_subscriptions:
            user_id, private_channel_id, expire_time, expire_date = subscription

            # Remove user from channel
            success = await self.remove_user_from_channel(user_id, private_channel_id)

            # Mark as inactive in database
            if success:
                self.deactivate_subscription(user_id, private_channel_id)
```

**Process Flow:**
```
┌─────────────────────────────────────────────────────┐
│       TelePay10-26 (Long-Running Process)          │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │   SubscriptionManager                        │  │
│  │   - start_monitoring() → infinite loop       │  │
│  │   - asyncio.sleep(60) between checks         │  │
│  │   - check_expired_subscriptions()            │  │
│  │   - fetch_expired_subscriptions()            │  │
│  │   - remove_user_from_channel()               │  │
│  │   - deactivate_subscription()                │  │
│  └──────────────────────────────────────────────┘  │
│                       │                             │
│                       ▼                             │
│           ┌───────────────────────┐                 │
│           │  PostgreSQL Database  │                 │
│           │  (telepaypsql)        │                 │
│           └───────────────────────┘                 │
└─────────────────────────────────────────────────────┘
```

**Dependencies:**
- `database.py` → `DatabaseManager` class
- `config_manager.py` → Telegram token fetching
- Telegram Bot API (`python-telegram-bot` library)
- PostgreSQL database connection (`psycopg2`)

**Limitations:**
1. ❌ Runs continuously even when no expirations to process
2. ❌ Single point of failure (bot crash = monitoring stops)
3. ❌ Cannot scale horizontally
4. ❌ Mixed logs with other bot functionality
5. ❌ Difficult to test in isolation

---

## Target Architecture

### High-Level Design

```
┌──────────────────────────────────────────────────────────────┐
│                    Cloud Scheduler                           │
│  Job: subscription-monitor                                   │
│  Schedule: */1 * * * * (every 60 seconds)                   │
│  Target: POST /check-expirations                            │
└────────────────┬─────────────────────────────────────────────┘
                 │ HTTP POST (OIDC Auth)
                 ▼
┌──────────────────────────────────────────────────────────────┐
│         GCSubscriptionMonitor-10-26 (Cloud Run)              │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Flask Application                                     │ │
│  │  - POST /check-expirations → Main endpoint            │ │
│  │  - GET /health → Health check                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                       │                                      │
│  ┌────────────────────┴──────────────────────────────────┐  │
│  │  Modules (All Self-Contained)                         │  │
│  │  ├── config_manager.py → Fetch secrets                │  │
│  │  ├── database_manager.py → DB operations              │  │
│  │  ├── telegram_client.py → Bot API calls               │  │
│  │  └── expiration_handler.py → Business logic           │  │
│  └───────────────────────────────────────────────────────┘  │
│                       │                                      │
│          ┌────────────┴────────────┐                         │
│          ▼                         ▼                         │
│  ┌───────────────┐        ┌────────────────┐                │
│  │  PostgreSQL   │        │ Telegram Bot   │                │
│  │  (telepaypsql)│        │  API           │                │
│  └───────────────┘        └────────────────┘                │
└──────────────────────────────────────────────────────────────┘
```

### Request Flow

1. **Cloud Scheduler Triggers:** Every 60 seconds, Cloud Scheduler sends authenticated POST request to `/check-expirations`
2. **Service Authenticates:** Cloud Run validates OIDC token from scheduler
3. **Query Database:** Fetch all active subscriptions where `expire_datetime < NOW()`
4. **Process Each Expiration:**
   - Call Telegram Bot API: `banChatMember(user_id, channel_id)`
   - Immediately call: `unbanChatMember(user_id, channel_id)` to allow future rejoins
   - Update database: `UPDATE private_channel_users_database SET is_active = FALSE`
5. **Return Summary:** JSON response with count of processed expirations
6. **Log Results:** Cloud Logging captures all operations for monitoring

---

## Service Structure

### Directory Layout

```
GCSubscriptionMonitor-10-26/
├── service.py                    # Flask application (main entry point)
├── config_manager.py             # Secret Manager integration
├── database_manager.py           # PostgreSQL operations
├── telegram_client.py            # Telegram Bot API wrapper
├── expiration_handler.py         # Core business logic
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container definition
├── .dockerignore                 # Files to exclude from container
├── .env.example                  # Example environment variables
└── README.md                     # Service documentation
```

**Note:** All modules are **self-contained within the service**. No shared module dependencies.

---

## Module Specifications

### 1. service.py (Flask Application Entry Point)

**Purpose:** Main Flask application factory and route definitions

**Code Structure:**
```python
#!/usr/bin/env python
"""
GCSubscriptionMonitor-10-26: Subscription Expiration Monitoring Service
Cloud Run webhook triggered by Cloud Scheduler every 60 seconds
"""
from flask import Flask, request, jsonify
import logging
from config_manager import ConfigManager
from database_manager import DatabaseManager
from telegram_client import TelegramClient
from expiration_handler import ExpirationHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)

    # Initialize configuration
    config_manager = ConfigManager()
    config = config_manager.initialize_config()

    if not config['bot_token']:
        logger.error("❌ Failed to initialize: Telegram bot token not available")
        raise RuntimeError("Cannot start service without bot token")

    # Initialize managers
    db_manager = DatabaseManager(
        instance_connection_name=config['instance_connection_name'],
        db_name=config['db_name'],
        db_user=config['db_user'],
        db_password=config['db_password']
    )

    telegram_client = TelegramClient(bot_token=config['bot_token'])

    expiration_handler = ExpirationHandler(
        db_manager=db_manager,
        telegram_client=telegram_client
    )

    @app.route('/check-expirations', methods=['POST'])
    def check_expirations():
        """
        Main endpoint triggered by Cloud Scheduler every 60 seconds.
        Processes expired subscriptions and returns summary statistics.
        """
        try:
            logger.info("🕐 Checking for expired subscriptions...")

            result = expiration_handler.process_expired_subscriptions()

            logger.info(
                f"✅ Expiration check complete: "
                f"{result['expired_count']} found, "
                f"{result['processed_count']} processed, "
                f"{result['failed_count']} failed"
            )

            return jsonify({
                "status": "success",
                "expired_count": result['expired_count'],
                "processed_count": result['processed_count'],
                "failed_count": result['failed_count'],
                "details": result.get('details', [])
            }), 200

        except Exception as e:
            logger.error(f"❌ Error in expiration check: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint for Cloud Run"""
        try:
            # Verify database connectivity
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")

            # Verify Telegram client is initialized
            if telegram_client.bot is None:
                raise RuntimeError("Telegram client not initialized")

            return jsonify({
                "status": "healthy",
                "service": "GCSubscriptionMonitor-10-26",
                "database": "connected",
                "telegram": "initialized"
            }), 200

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return jsonify({
                "status": "unhealthy",
                "error": str(e)
            }), 503

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
```

**Key Features:**
- ✅ Application factory pattern for testability
- ✅ Comprehensive error handling
- ✅ Health check endpoint validates all dependencies
- ✅ Structured logging with emojis (matching existing style)
- ✅ JSON responses for monitoring/alerting

---

### 2. config_manager.py (Secret Manager Integration)

**Purpose:** Fetch configuration and secrets from Google Secret Manager

**Code Structure:**
```python
#!/usr/bin/env python
"""
Configuration Manager for GCSubscriptionMonitor
Fetches secrets from Google Secret Manager
"""
import os
from google.cloud import secretmanager
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration and secret fetching"""

    def __init__(self):
        self.client = secretmanager.SecretManagerServiceClient()

    def fetch_secret(self, env_var_name: str, secret_name_for_logging: str) -> Optional[str]:
        """
        Generic method to fetch a secret from Secret Manager.

        Args:
            env_var_name: Environment variable containing secret path
            secret_name_for_logging: Human-readable name for logging

        Returns:
            Secret value as string, or None if error
        """
        try:
            secret_path = os.getenv(env_var_name)
            if not secret_path:
                logger.error(f"❌ Environment variable {env_var_name} is not set")
                return None

            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")

            logger.info(f"✅ Successfully fetched {secret_name_for_logging}")
            return secret_value

        except Exception as e:
            logger.error(f"❌ Error fetching {secret_name_for_logging}: {e}")
            return None

    def fetch_telegram_token(self) -> Optional[str]:
        """Fetch Telegram bot token from Secret Manager"""
        return self.fetch_secret(
            env_var_name="TELEGRAM_BOT_TOKEN_SECRET",
            secret_name_for_logging="Telegram bot token"
        )

    def fetch_database_host(self) -> Optional[str]:
        """Fetch database host from Secret Manager"""
        return self.fetch_secret(
            env_var_name="DATABASE_HOST_SECRET",
            secret_name_for_logging="database host"
        )

    def fetch_database_name(self) -> Optional[str]:
        """Fetch database name from Secret Manager"""
        return self.fetch_secret(
            env_var_name="DATABASE_NAME_SECRET",
            secret_name_for_logging="database name"
        )

    def fetch_database_user(self) -> Optional[str]:
        """Fetch database user from Secret Manager"""
        return self.fetch_secret(
            env_var_name="DATABASE_USER_SECRET",
            secret_name_for_logging="database user"
        )

    def fetch_database_password(self) -> Optional[str]:
        """Fetch database password from Secret Manager"""
        return self.fetch_secret(
            env_var_name="DATABASE_PASSWORD_SECRET",
            secret_name_for_logging="database password"
        )

    def initialize_config(self) -> Dict[str, Optional[str]]:
        """
        Initialize and return all configuration values.

        Returns:
            Dictionary with all configuration values
        """
        logger.info("🔧 Initializing configuration...")

        config = {
            'bot_token': self.fetch_telegram_token(),
            'instance_connection_name': self.fetch_database_host(),
            'db_name': self.fetch_database_name(),
            'db_user': self.fetch_database_user(),
            'db_password': self.fetch_database_password()
        }

        # Validate critical configuration
        missing = [k for k, v in config.items() if v is None]
        if missing:
            logger.error(f"❌ Missing critical configuration: {', '.join(missing)}")
            raise RuntimeError(f"Cannot initialize without: {', '.join(missing)}")

        logger.info("✅ Configuration initialized successfully")
        return config
```

**Environment Variables Required:**
```bash
TELEGRAM_BOT_TOKEN_SECRET="projects/telepay-459221/secrets/telegram-bot-token/versions/latest"
DATABASE_HOST_SECRET="projects/telepay-459221/secrets/database-host/versions/latest"
DATABASE_NAME_SECRET="projects/telepay-459221/secrets/database-name/versions/latest"
DATABASE_USER_SECRET="projects/telepay-459221/secrets/database-user/versions/latest"
DATABASE_PASSWORD_SECRET="projects/telepay-459221/secrets/database-password/versions/latest"
```

---

### 3. database_manager.py (PostgreSQL Operations)

**Purpose:** Handle all database operations for subscription queries and updates

**Code Structure:**
```python
#!/usr/bin/env python
"""
Database Manager for GCSubscriptionMonitor
Handles PostgreSQL operations using Cloud SQL Connector
"""
from google.cloud.sql.connector import Connector
import sqlalchemy
from datetime import datetime
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and operations"""

    def __init__(self, instance_connection_name: str, db_name: str,
                 db_user: str, db_password: str):
        """
        Initialize database manager with Cloud SQL Connector.

        Args:
            instance_connection_name: Format "project:region:instance"
            db_name: Database name
            db_user: Database user
            db_password: Database password
        """
        self.instance_connection_name = instance_connection_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password

        logger.info("🔌 Initializing Cloud SQL Connector...")

        self.connector = Connector()
        self.pool = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=self._getconn
        )

        logger.info("✅ Database connection pool initialized")

    def _getconn(self):
        """Create database connection via Cloud SQL Connector"""
        return self.connector.connect(
            self.instance_connection_name,
            "pg8000",
            user=self.db_user,
            password=self.db_password,
            db=self.db_name
        )

    def get_connection(self):
        """Get a database connection from the pool"""
        return self.pool.connect()

    def fetch_expired_subscriptions(self) -> List[Tuple[int, int, str, str]]:
        """
        Fetch all expired subscriptions from database.

        Returns:
            List of tuples: (user_id, private_channel_id, expire_time, expire_date)
        """
        expired_subscriptions = []

        try:
            with self.get_connection() as conn:
                query = sqlalchemy.text("""
                    SELECT user_id, private_channel_id, expire_time, expire_date
                    FROM private_channel_users_database
                    WHERE is_active = true
                        AND expire_time IS NOT NULL
                        AND expire_date IS NOT NULL
                """)

                result = conn.execute(query)
                rows = result.fetchall()

                current_datetime = datetime.now()

                for row in rows:
                    user_id = row[0]
                    private_channel_id = row[1]
                    expire_time_str = row[2]
                    expire_date_str = row[3]

                    try:
                        # Parse expiration time and date
                        if isinstance(expire_date_str, str):
                            expire_date_obj = datetime.strptime(expire_date_str, '%Y-%m-%d').date()
                        else:
                            expire_date_obj = expire_date_str

                        if isinstance(expire_time_str, str):
                            expire_time_obj = datetime.strptime(expire_time_str, '%H:%M:%S').time()
                        else:
                            expire_time_obj = expire_time_str

                        # Combine date and time
                        expire_datetime = datetime.combine(expire_date_obj, expire_time_obj)

                        # Check if subscription has expired
                        if current_datetime > expire_datetime:
                            expired_subscriptions.append((
                                user_id,
                                private_channel_id,
                                str(expire_time_str),
                                str(expire_date_str)
                            ))
                            logger.debug(
                                f"🔍 Found expired subscription: "
                                f"user {user_id}, channel {private_channel_id}, "
                                f"expired at {expire_datetime}"
                            )

                    except Exception as e:
                        logger.error(f"❌ Error parsing expiration data for user {user_id}: {e}")
                        continue

                logger.info(f"📊 Found {len(expired_subscriptions)} expired subscriptions")

        except Exception as e:
            logger.error(f"❌ Database error fetching expired subscriptions: {e}", exc_info=True)

        return expired_subscriptions

    def deactivate_subscription(self, user_id: int, private_channel_id: int) -> bool:
        """
        Mark subscription as inactive in database.

        Args:
            user_id: User's Telegram ID
            private_channel_id: Private channel ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                query = sqlalchemy.text("""
                    UPDATE private_channel_users_database
                    SET is_active = false
                    WHERE user_id = :user_id
                        AND private_channel_id = :private_channel_id
                        AND is_active = true
                """)

                result = conn.execute(
                    query,
                    {"user_id": user_id, "private_channel_id": private_channel_id}
                )
                conn.commit()

                rows_affected = result.rowcount

                if rows_affected > 0:
                    logger.info(
                        f"📝 Marked subscription as inactive: "
                        f"user {user_id}, channel {private_channel_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"⚠️ No active subscription found to deactivate: "
                        f"user {user_id}, channel {private_channel_id}"
                    )
                    return False

        except Exception as e:
            logger.error(
                f"❌ Database error deactivating subscription "
                f"for user {user_id}, channel {private_channel_id}: {e}",
                exc_info=True
            )
            return False

    def close(self):
        """Close database connections"""
        self.connector.close()
        logger.info("🔌 Database connections closed")
```

**Key Features:**
- ✅ Uses Cloud SQL Connector for secure connections
- ✅ Connection pooling for efficiency
- ✅ Handles date/time parsing from database
- ✅ Comprehensive error logging
- ✅ Idempotent operations (safe to run multiple times)

---

### 4. telegram_client.py (Telegram Bot API Wrapper)

**Purpose:** Wrapper for Telegram Bot API operations (ban/unban users)

**Code Structure:**
```python
#!/usr/bin/env python
"""
Telegram Client for GCSubscriptionMonitor
Handles Telegram Bot API operations for removing users from channels
"""
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import logging

logger = logging.getLogger(__name__)

class TelegramClient:
    """Wrapper for Telegram Bot API operations"""

    def __init__(self, bot_token: str):
        """
        Initialize Telegram client.

        Args:
            bot_token: Telegram bot token
        """
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        logger.info("🤖 Telegram client initialized")

    async def remove_user_from_channel(self, user_id: int, private_channel_id: int) -> bool:
        """
        Remove user from private channel using Telegram Bot API.
        Uses ban + immediate unban pattern to remove user while allowing future rejoins.

        Args:
            user_id: User's Telegram ID
            private_channel_id: Private channel ID to remove user from

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ban user from channel
            await self.bot.ban_chat_member(
                chat_id=private_channel_id,
                user_id=user_id
            )

            # Immediately unban to allow future rejoining if they pay again
            await self.bot.unban_chat_member(
                chat_id=private_channel_id,
                user_id=user_id,
                only_if_banned=True
            )

            logger.info(
                f"🚫 Successfully removed user {user_id} from channel {private_channel_id}"
            )
            return True

        except TelegramError as e:
            # Handle specific Telegram errors
            error_message = str(e)

            if "user not found" in error_message.lower() or "user is not a member" in error_message.lower():
                # User already left - consider this successful
                logger.info(
                    f"ℹ️ User {user_id} is no longer in channel {private_channel_id} "
                    f"(already left)"
                )
                return True

            elif "forbidden" in error_message.lower():
                # Bot lacks permissions
                logger.error(
                    f"❌ Bot lacks permission to remove user {user_id} "
                    f"from channel {private_channel_id}"
                )
                return False

            elif "chat not found" in error_message.lower():
                # Channel doesn't exist or bot is not a member
                logger.error(
                    f"❌ Channel {private_channel_id} not found or bot is not a member"
                )
                return False

            else:
                # Other Telegram API errors
                logger.error(
                    f"❌ Telegram API error removing user {user_id} "
                    f"from channel {private_channel_id}: {e}"
                )
                return False

        except Exception as e:
            # Unexpected errors
            logger.error(
                f"❌ Unexpected error removing user {user_id} "
                f"from channel {private_channel_id}: {e}",
                exc_info=True
            )
            return False

    def remove_user_sync(self, user_id: int, private_channel_id: int) -> bool:
        """
        Synchronous wrapper for remove_user_from_channel.
        Needed for Flask route handlers that aren't async.

        Args:
            user_id: User's Telegram ID
            private_channel_id: Private channel ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self.remove_user_from_channel(user_id, private_channel_id)
            )

            loop.close()
            return result

        except Exception as e:
            logger.error(f"❌ Error in synchronous wrapper: {e}", exc_info=True)
            return False
```

**Key Features:**
- ✅ Ban + unban pattern to remove users while allowing future rejoins
- ✅ Comprehensive error handling for Telegram API errors
- ✅ Synchronous wrapper for Flask compatibility
- ✅ Detailed logging for debugging

---

### 5. expiration_handler.py (Core Business Logic)

**Purpose:** Orchestrate the subscription expiration processing workflow

**Code Structure:**
```python
#!/usr/bin/env python
"""
Expiration Handler for GCSubscriptionMonitor
Core business logic for processing expired subscriptions
"""
from typing import Dict, List
import logging
from database_manager import DatabaseManager
from telegram_client import TelegramClient

logger = logging.getLogger(__name__)

class ExpirationHandler:
    """Handles expired subscription processing workflow"""

    def __init__(self, db_manager: DatabaseManager, telegram_client: TelegramClient):
        """
        Initialize expiration handler.

        Args:
            db_manager: Database manager instance
            telegram_client: Telegram client instance
        """
        self.db_manager = db_manager
        self.telegram_client = telegram_client

    def process_expired_subscriptions(self) -> Dict:
        """
        Main processing workflow for expired subscriptions.

        Returns:
            Dictionary with processing statistics:
            {
                "expired_count": int,       # Total expired found
                "processed_count": int,     # Successfully processed
                "failed_count": int,        # Failed to process
                "details": List[Dict]       # Details of each processed subscription
            }
        """
        logger.info("🔍 Starting expired subscriptions check...")

        # Fetch expired subscriptions from database
        expired_subscriptions = self.db_manager.fetch_expired_subscriptions()

        expired_count = len(expired_subscriptions)

        if expired_count == 0:
            logger.info("✅ No expired subscriptions found")
            return {
                "expired_count": 0,
                "processed_count": 0,
                "failed_count": 0,
                "details": []
            }

        logger.info(f"📊 Found {expired_count} expired subscriptions to process")

        processed_count = 0
        failed_count = 0
        details = []

        # Process each expired subscription
        for subscription in expired_subscriptions:
            user_id, private_channel_id, expire_time, expire_date = subscription

            try:
                # Remove user from channel via Telegram Bot API
                removal_success = self.telegram_client.remove_user_sync(
                    user_id=user_id,
                    private_channel_id=private_channel_id
                )

                # Update database regardless of removal success
                # (user may have already left, but we still mark inactive)
                deactivation_success = self.db_manager.deactivate_subscription(
                    user_id=user_id,
                    private_channel_id=private_channel_id
                )

                if removal_success and deactivation_success:
                    processed_count += 1
                    logger.info(
                        f"✅ Successfully processed expired subscription: "
                        f"user {user_id} removed from channel {private_channel_id}"
                    )

                    details.append({
                        "user_id": user_id,
                        "channel_id": private_channel_id,
                        "status": "success",
                        "removed_from_channel": removal_success,
                        "deactivated_in_db": deactivation_success
                    })

                elif deactivation_success:
                    # Removal failed but deactivation succeeded
                    processed_count += 1
                    logger.warning(
                        f"⚠️ Partially processed: user {user_id}, channel {private_channel_id} "
                        f"(removal failed but marked inactive)"
                    )

                    details.append({
                        "user_id": user_id,
                        "channel_id": private_channel_id,
                        "status": "partial",
                        "removed_from_channel": removal_success,
                        "deactivated_in_db": deactivation_success
                    })

                else:
                    # Both operations failed
                    failed_count += 1
                    logger.error(
                        f"❌ Failed to process expired subscription: "
                        f"user {user_id}, channel {private_channel_id}"
                    )

                    details.append({
                        "user_id": user_id,
                        "channel_id": private_channel_id,
                        "status": "failed",
                        "removed_from_channel": removal_success,
                        "deactivated_in_db": deactivation_success
                    })

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"❌ Error processing expired subscription "
                    f"for user {user_id}, channel {private_channel_id}: {e}",
                    exc_info=True
                )

                details.append({
                    "user_id": user_id,
                    "channel_id": private_channel_id,
                    "status": "error",
                    "error": str(e)
                })

        logger.info(
            f"🏁 Expiration processing complete: "
            f"{expired_count} found, {processed_count} processed, {failed_count} failed"
        )

        return {
            "expired_count": expired_count,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "details": details
        }
```

**Key Features:**
- ✅ Orchestrates entire workflow (query → remove → update)
- ✅ Tracks detailed statistics for monitoring
- ✅ Handles partial failures gracefully
- ✅ Returns structured data for logging/alerting
- ✅ Marks inactive even if removal fails (user may have already left)

---

## Database Operations

### Query: Fetch Expired Subscriptions

**SQL Query:**
```sql
SELECT user_id, private_channel_id, expire_time, expire_date
FROM private_channel_users_database
WHERE is_active = true
    AND expire_time IS NOT NULL
    AND expire_date IS NOT NULL
```

**Logic:**
1. Fetch all active subscriptions with expiration data
2. For each row, combine `expire_date` + `expire_time` into `expire_datetime`
3. Compare `expire_datetime` with `NOW()`
4. If `NOW() > expire_datetime`, add to expired list

**Example Data:**
```python
[
    (6271402111, -1003268562225, "14:30:00", "2025-11-10"),  # Expired 2 days ago
    (5555555555, -1002345678901, "09:15:00", "2025-11-11"),  # Expired 1 day ago
    (7777777777, -1003268562225, "18:45:00", "2025-11-12"),  # Expired today
]
```

### Update: Deactivate Subscription

**SQL Query:**
```sql
UPDATE private_channel_users_database
SET is_active = false
WHERE user_id = :user_id
    AND private_channel_id = :private_channel_id
    AND is_active = true
```

**Idempotency:** Safe to run multiple times (only updates if `is_active = true`)

**Constraints:**
- Primary key: `id` (auto-increment)
- Unique constraint: None (user can have multiple subscriptions per channel with different time periods)
- Indexes: `user_id`, `private_channel_id`, `is_active` for query performance

---

## Telegram Bot API Integration

### Ban + Unban Pattern

**Why This Pattern?**
- Telegram Bot API doesn't have a "remove_member" method
- `ban_chat_member` removes user from channel
- Immediate `unban_chat_member` allows future rejoins if they pay again
- This pattern is already used in existing `subscription_manager.py`

**API Calls:**

1. **Ban User:**
```python
await bot.ban_chat_member(
    chat_id=private_channel_id,  # Channel ID (negative integer)
    user_id=user_id              # User ID (positive integer)
)
```

2. **Unban User:**
```python
await bot.unban_chat_member(
    chat_id=private_channel_id,
    user_id=user_id,
    only_if_banned=True  # Only unban if currently banned
)
```

**Error Handling:**
| Error | Meaning | Action |
|-------|---------|--------|
| `user not found` | User already left channel | Consider success, mark inactive |
| `user is not a member` | User not in channel | Consider success, mark inactive |
| `Forbidden` | Bot lacks permissions | Log error, still mark inactive |
| `chat not found` | Channel doesn't exist | Log error, still mark inactive |
| Other errors | API issues | Log error, retry logic optional |

---

## Error Handling & Recovery

### Retry Strategy

**Database Errors:**
- Connection errors → Cloud SQL Connector automatically retries
- Query errors → Log and continue to next subscription
- Transaction errors → Rollback handled by SQLAlchemy

**Telegram API Errors:**
- Rate limits → Built-in retry logic in `python-telegram-bot`
- Network errors → Automatic retry with exponential backoff
- Permission errors → Log and mark inactive anyway

**Partial Failures:**
- If removal fails but database update succeeds → **Mark as processed**
- If removal succeeds but database update fails → **Retry database update**
- If both fail → **Mark as failed, will retry on next invocation**

### Monitoring & Alerting

**Cloud Logging Queries:**
```bash
# Check for failed expirations
resource.type="cloud_run_revision"
resource.labels.service_name="gcsubscriptionmonitor-10-26"
severity="ERROR"
textPayload=~"Failed to process expired subscription"

# Monitor processing statistics
resource.type="cloud_run_revision"
resource.labels.service_name="gcsubscriptionmonitor-10-26"
jsonPayload.message=~"Expiration processing complete"
```

**Alerting Thresholds:**
- Error rate > 10% for 3 consecutive invocations → Alert
- No successful runs for 10 minutes → Alert
- Failed count > 50 in single run → Alert

---

## Deployment Configuration

### Dockerfile

```dockerfile
# Use official Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY service.py .
COPY config_manager.py .
COPY database_manager.py .
COPY telegram_client.py .
COPY expiration_handler.py .

# Expose port
EXPOSE 8080

# Set environment variable for Python unbuffered output
ENV PYTHONUNBUFFERED=1

# Run application
CMD ["python", "service.py"]
```

### requirements.txt

```txt
Flask==3.0.0
google-cloud-secret-manager==2.18.0
cloud-sql-python-connector==1.7.0
sqlalchemy==2.0.25
pg8000==1.30.4
python-telegram-bot==20.7
gunicorn==21.2.0
```

### .dockerignore

```
__pycache__/
*.pyc
*.pyo
*.pyd
.env
.env.*
*.log
.git/
.gitignore
README.md
.vscode/
.idea/
```

### Deploy to Cloud Run

```bash
#!/bin/bash
# deploy_gcsubscriptionmonitor.sh

PROJECT_ID="telepay-459221"
REGION="us-central1"
SERVICE_NAME="gcsubscriptionmonitor-10-26"

gcloud run deploy ${SERVICE_NAME} \
  --source=./GCSubscriptionMonitor-10-26 \
  --region=${REGION} \
  --platform=managed \
  --no-allow-unauthenticated \
  --set-env-vars="TELEGRAM_BOT_TOKEN_SECRET=projects/${PROJECT_ID}/secrets/telegram-bot-token/versions/latest" \
  --set-env-vars="DATABASE_HOST_SECRET=projects/${PROJECT_ID}/secrets/database-host/versions/latest" \
  --set-env-vars="DATABASE_NAME_SECRET=projects/${PROJECT_ID}/secrets/database-name/versions/latest" \
  --set-env-vars="DATABASE_USER_SECRET=projects/${PROJECT_ID}/secrets/database-user/versions/latest" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=projects/${PROJECT_ID}/secrets/database-password/versions/latest" \
  --min-instances=0 \
  --max-instances=1 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300s \
  --concurrency=1 \
  --service-account=telepay-cloudrun@${PROJECT_ID}.iam.gserviceaccount.com

echo "✅ Deployment complete!"
```

**Key Configuration:**
- `--no-allow-unauthenticated` → Only Cloud Scheduler can invoke
- `--min-instances=0` → Scale to zero when not in use
- `--max-instances=1` → Only one instance needed (60-second intervals)
- `--concurrency=1` → Process one request at a time
- `--timeout=300s` → 5-minute timeout for processing large batches

### Cloud Scheduler Configuration

```bash
#!/bin/bash
# create_subscription_monitor_scheduler.sh

PROJECT_ID="telepay-459221"
REGION="us-central1"
SERVICE_URL="https://gcsubscriptionmonitor-10-26-pjxwjsdktq-uc.a.run.app"

gcloud scheduler jobs create http subscription-monitor \
  --schedule="*/1 * * * *" \
  --uri="${SERVICE_URL}/check-expirations" \
  --http-method=POST \
  --location=${REGION} \
  --oidc-service-account-email=telepay-scheduler@${PROJECT_ID}.iam.gserviceaccount.com \
  --oidc-token-audience="${SERVICE_URL}" \
  --time-zone="America/New_York" \
  --attempt-deadline=300s

echo "✅ Cloud Scheduler job created!"
echo "To test manually: gcloud scheduler jobs run subscription-monitor --location=${REGION}"
```

**Schedule:** `*/1 * * * *` = Every minute (matches existing 60-second interval)

**Authentication:** OIDC token signed by `telepay-scheduler` service account

---

## Testing Strategy

### Unit Tests

**test_database_manager.py**
```python
import pytest
from database_manager import DatabaseManager
from datetime import datetime, timedelta

def test_fetch_expired_subscriptions(mock_db):
    """Test fetching expired subscriptions"""
    db_manager = DatabaseManager(
        instance_connection_name="test:us-central1:test",
        db_name="testdb",
        db_user="testuser",
        db_password="testpass"
    )

    # Insert test data with expired subscription
    # ... setup code ...

    expired = db_manager.fetch_expired_subscriptions()

    assert len(expired) == 1
    assert expired[0][0] == 123456  # user_id

def test_deactivate_subscription(mock_db):
    """Test marking subscription as inactive"""
    db_manager = DatabaseManager(...)

    result = db_manager.deactivate_subscription(
        user_id=123456,
        private_channel_id=-1003268562225
    )

    assert result is True
```

**test_telegram_client.py**
```python
import pytest
from telegram_client import TelegramClient
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_remove_user_success():
    """Test successful user removal"""
    client = TelegramClient(bot_token="test_token")

    with patch.object(client.bot, 'ban_chat_member', new_callable=AsyncMock) as mock_ban, \
         patch.object(client.bot, 'unban_chat_member', new_callable=AsyncMock) as mock_unban:

        result = await client.remove_user_from_channel(
            user_id=123456,
            private_channel_id=-1003268562225
        )

        assert result is True
        mock_ban.assert_called_once()
        mock_unban.assert_called_once()
```

### Integration Tests

**test_integration.py**
```python
import requests

def test_check_expirations_endpoint():
    """Test /check-expirations endpoint"""
    url = "http://localhost:8080/check-expirations"

    response = requests.post(url)

    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert data["status"] == "success"
    assert "expired_count" in data

def test_health_endpoint():
    """Test /health endpoint"""
    url = "http://localhost:8080/health"

    response = requests.get(url)

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["database"] == "connected"
```

### Manual Testing

**Local Testing:**
```bash
# Set environment variables
export TELEGRAM_BOT_TOKEN_SECRET="projects/telepay-459221/secrets/telegram-bot-token/versions/latest"
export DATABASE_HOST_SECRET="projects/telepay-459221/secrets/database-host/versions/latest"
# ... other env vars ...

# Run service locally
python service.py

# Test endpoint
curl -X POST http://localhost:8080/check-expirations
```

**Cloud Run Testing:**
```bash
# Deploy to Cloud Run
./deploy_gcsubscriptionmonitor.sh

# Get service URL
gcloud run services describe gcsubscriptionmonitor-10-26 --region=us-central1 --format="value(status.url)"

# Test with authentication
gcloud run services proxy gcsubscriptionmonitor-10-26 --region=us-central1
curl -X POST http://localhost:8080/check-expirations
```

---

## Migration Plan

### Phase 1: Build & Deploy Service (Day 1)

**Tasks:**
1. ✅ Create directory structure: `GCSubscriptionMonitor-10-26/`
2. ✅ Implement all 5 modules (service.py, config_manager.py, etc.)
3. ✅ Create Dockerfile and requirements.txt
4. ✅ Deploy to Cloud Run (staging environment first)
5. ✅ Create Cloud Scheduler job (initially paused)

**Validation:**
- Service deploys successfully
- Health check returns 200 OK
- Manual POST to `/check-expirations` works
- Cloud Scheduler job created but not running

---

### Phase 2: Parallel Testing (Days 2-3)

**Tasks:**
1. ✅ Run existing `TelePay10-26` bot (with subscription_manager.py)
2. ✅ Manually trigger `GCSubscriptionMonitor-10-26` every 60 seconds
3. ✅ Compare results (both should process same expirations)
4. ✅ Monitor Cloud Logging for errors
5. ✅ Verify database updates are identical

**Success Criteria:**
- Both systems process same number of expirations
- No database conflicts or race conditions
- Error rates < 1%
- Latency p95 < 2 seconds

---

### Phase 3: Gradual Cutover (Days 4-5)

**Tasks:**
1. ✅ Enable Cloud Scheduler job
2. ✅ Disable `subscription_manager.py` in TelePay10-26
3. ✅ Monitor for 24 hours
4. ✅ Verify all expirations processed correctly
5. ✅ Check for missed expirations or duplicate processing

**Rollback Plan:**
- Re-enable `subscription_manager.py` in bot
- Pause Cloud Scheduler job
- Verify bot resumes processing

---

### Phase 4: Decommission Old Code (Day 6)

**Tasks:**
1. ✅ Remove `subscription_manager.py` from TelePay10-26
2. ✅ Remove related imports and initialization code
3. ✅ Archive old code to `ARCHIVES/`
4. ✅ Update documentation

---

## Appendix

### Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN_SECRET` | Secret Manager path for bot token | `projects/telepay-459221/secrets/telegram-bot-token/versions/latest` |
| `DATABASE_HOST_SECRET` | Secret Manager path for DB host | `projects/telepay-459221/secrets/database-host/versions/latest` |
| `DATABASE_NAME_SECRET` | Secret Manager path for DB name | `projects/telepay-459221/secrets/database-name/versions/latest` |
| `DATABASE_USER_SECRET` | Secret Manager path for DB user | `projects/telepay-459221/secrets/database-user/versions/latest` |
| `DATABASE_PASSWORD_SECRET` | Secret Manager path for DB password | `projects/telepay-459221/secrets/database-password/versions/latest` |
| `PORT` | HTTP port (auto-set by Cloud Run) | `8080` |

### IAM Permissions Required

**Service Account:** `telepay-cloudrun@telepay-459221.iam.gserviceaccount.com`

**Roles:**
- `roles/secretmanager.secretAccessor` → Access Secret Manager
- `roles/cloudsql.client` → Connect to Cloud SQL
- `roles/logging.logWriter` → Write to Cloud Logging

**Scheduler Service Account:** `telepay-scheduler@telepay-459221.iam.gserviceaccount.com`

**Roles:**
- `roles/run.invoker` → Invoke Cloud Run service

---

## Conclusion

This architecture transforms subscription monitoring from a resource-intensive background task into a **lightweight, serverless webhook** that:

✅ **Reduces Costs:** Only runs when triggered (60s intervals), scales to zero between invocations
✅ **Improves Reliability:** Operates independently of bot availability
✅ **Enhances Observability:** Clear logs and metrics in Cloud Logging
✅ **Simplifies Maintenance:** Self-contained service with no external dependencies
✅ **Enables Scalability:** Can handle increased load by adjusting Cloud Scheduler frequency

**Next Steps:**
1. Review and approve architecture
2. Begin Phase 1: Build & Deploy Service
3. Schedule parallel testing period
4. Plan cutover date

**Document Owner:** Claude
**Review Date:** 2025-11-12
**Status:** Ready for Implementation
