# TelePay Refactoring Architecture
## Comprehensive Migration from Monolithic Bot to Modular Webhook Services

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Architecture Design
**Branch:** TelePay-REFACTOR

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Architecture Principles](#architecture-principles)
4. [Target Architecture Overview](#target-architecture-overview)
5. [Service Decomposition Strategy](#service-decomposition-strategy)
6. [Detailed Service Specifications](#detailed-service-specifications)
7. [Database Strategy](#database-strategy)
8. [Deployment Strategy](#deployment-strategy)
9. [Migration Phases](#migration-phases)
10. [Risk Assessment & Mitigation](#risk-assessment--mitigation)
11. [Testing Strategy](#testing-strategy)
12. [Rollback Procedures](#rollback-procedures)

---

## Executive Summary

### Problem Statement
The current `TelePay10-26` application is a **monolithic Telegram bot** that handles all functionality in a single long-running process:
- Bot command handling (subscriptions, donations, database management)
- Subscription monitoring (background task checking expirations)
- Notification delivery
- Broadcast message management
- Payment gateway initialization
- Closed channel management

This architecture presents several challenges:
- **Single Point of Failure:** If the bot crashes, all functionality stops
- **Scalability Constraints:** Cannot scale individual components independently
- **Deployment Complexity:** Any change requires full bot restart
- **Resource Inefficiency:** Long-running processes consume resources even when idle
- **Difficult Testing:** Tight coupling makes unit testing and integration testing challenging
- **Limited Observability:** Mixed concerns make debugging and monitoring difficult

### Solution Overview
**Refactor TelePay10-26 into a microservices architecture** using Google Cloud Run webhooks, following the established patterns from existing services (GCWebhook1-2, GCHostPay1-3, GCSplit1-3).

### Key Objectives
1. ✅ **Modularity:** Each service has a single, well-defined responsibility
2. ✅ **Scalability:** Services can scale independently based on load
3. ✅ **Reliability:** Service failures are isolated and don't cascade
4. ✅ **Maintainability:** Clean separation of concerns enables easier debugging
5. ✅ **Cost Efficiency:** Serverless architecture only charges for actual usage
6. ✅ **Observability:** Each service logs independently for better monitoring

---

## Current State Analysis

### Existing TelePay10-26 Components

#### 📁 **File Structure**
```
TelePay10-26/
├── telepay10-26.py              # Main orchestrator
├── app_initializer.py           # Application setup
├── server_manager.py            # Flask server for notifications
├── bot_manager.py               # Telegram bot handlers
├── database.py                  # Database operations
├── config_manager.py            # Configuration management
├── subscription_manager.py      # Background expiration monitoring
├── notification_service.py      # Payment notification delivery
├── broadcast_manager.py         # Open channel broadcast messages
├── closed_channel_manager.py   # Closed channel donation messages
├── start_np_gateway.py         # Payment gateway (NowPayments)
├── secure_webhook.py           # Webhook security utilities
├── input_handlers.py           # User input handling
├── menu_handlers.py            # Menu & callback handling
├── donation_input_handler.py   # Donation keypad logic
└── message_utils.py            # Message formatting utilities
```

#### 🔄 **Current Process Flow**

```
┌─────────────────────────────────────────────────────────────┐
│                   TelePay10-26 (Single Process)             │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Telegram Bot │    │ Flask Server │    │ Subscription │ │
│  │   Polling    │    │ (Notifications)│   │  Monitor    │ │
│  │              │    │              │    │   (60s loop) │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                    │                    │         │
│         └────────────────────┼────────────────────┘         │
│                              │                              │
│                     ┌────────▼────────┐                     │
│                     │    Database     │                     │
│                     │   (PostgreSQL)  │                     │
│                     └─────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

#### ⚠️ **Current Limitations**

1. **Resource Waste**
   - Bot polls 24/7 even with no activity
   - Subscription monitor runs every 60s regardless of subscription count
   - Flask server runs continuously for occasional notification requests

2. **Tight Coupling**
   - Changes to notification logic require bot restart
   - Payment gateway changes affect entire application
   - Database schema changes impact all components simultaneously

3. **Deployment Bottleneck**
   - Single deployment artifact
   - No gradual rollout capability
   - All-or-nothing deployment risk

4. **Observability Challenges**
   - Mixed logs from multiple concerns
   - Difficult to trace specific functionality
   - Performance bottlenecks hard to isolate

---

## Architecture Principles

### 🎯 Core Design Principles

Following **Flask best practices** and **Cloud Run patterns** from existing webhooks:

#### 1. **Single Responsibility Principle (SRP)**
Each service should do **one thing well**:
- ✅ GCBotCommand handles bot commands
- ✅ GCSubscriptionMonitor handles expiration checks
- ✅ GCNotificationService handles notification delivery
- ❌ NO service handles multiple unrelated concerns

#### 2. **Application Factory Pattern**
All Flask services follow the **application factory pattern**:
```python
def create_app(config=None):
    app = Flask(__name__)

    # Load configuration
    if config:
        app.config.update(config)

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app
```

#### 3. **Stateless Service Design**
Services must be **stateless** and horizontally scalable:
- All state stored in PostgreSQL or Cloud Tasks queues
- No in-memory caching across requests
- Each request is independent and idempotent

#### 4. **Fail-Fast & Graceful Degradation**
Services should fail quickly and gracefully:
- Validate inputs immediately
- Return appropriate HTTP status codes
- Log errors comprehensively
- Don't cascade failures to other services

#### 5. **Defense in Depth**
Multiple layers of validation and security:
- Token/signature verification at service boundaries
- Database constraint validation
- Input sanitization and validation
- Rate limiting and request throttling

#### 6. **Observability First**
All services emit structured logs:
- Request ID tracking
- Performance metrics
- Error details with context
- Cloud Logging integration

---

## Target Architecture Overview

### 🏗️ High-Level Service Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Telegram Bot API                            │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
         ┌────────────────────┐
         │  GCBotCommand      │  ← Handles /start, /database, button clicks
         │  (Cloud Run)       │     Routes to payment gateway
         └────────┬───────────┘
                  │
        ┌─────────┴─────────────────────────────────────────┐
        │                                                     │
        ▼                                                     ▼
┌───────────────────┐                            ┌────────────────────┐
│ GCPaymentGateway  │                            │ GCDonationHandler  │
│ (Cloud Run)       │                            │ (Cloud Run)        │
│ - Creates invoices│                            │ - Keypad logic     │
│ - NowPayments API │                            │ - Amount validation│
└────────┬──────────┘                            └──────────┬─────────┘
         │                                                   │
         │                                                   │
         ▼                                                   ▼
┌────────────────────┐                            ┌────────────────────┐
│   NP-Webhook-10-26 │◄───(IPN)───┐              │   Database         │
│   (Cloud Run)      │             │              │   (PostgreSQL)     │
│   - IPN validation │             │              └──────────┬─────────┘
│   - Price fetch    │             │                         │
└────────┬───────────┘             │                         │
         │                         │                         │
         ▼                         │                         │
┌────────────────────┐             │              ┌──────────▼─────────┐
│  GCWebhook1-10-26  │             │              │ GCBroadcastService │
│  (Cloud Run)       │             │              │ (Cloud Run)        │
│  - Payment routing │             │              │ - Open channels    │
│  - Instant/Threshold│            │              │ - Closed channels  │
└────────┬───────────┘             │              └────────────────────┘
         │                         │
    ┌────┴────┐           ┌────────┴────────┐
    ▼         ▼           ▼                 ▼
┌────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐
│GCSplit1│ │GCWebhook2│ │GCHostPay1│ │GCSubscription  │
│(Instant│ │(Telegram │ │(Payout   │ │Monitor         │
│Payout) │ │ Invite)  │ │ Split)   │ │(Cloud Scheduler│
└────────┘ └────┬─────┘ └──────────┘ │ + Cloud Run)   │
                │                     │ - Checks DB    │
                ▼                     │ - Removes users│
       ┌────────────────┐             └────────────────┘
       │GCNotification  │                     │
       │Service         │◄────────────────────┘
       │(Cloud Run)     │
       │- Send to owners│
       └────────────────┘
```

### 📋 Service Responsibilities Matrix

| Service | Responsibility | Trigger | Dependencies |
|---------|---------------|---------|--------------|
| **GCBotCommand** | Handle all Telegram bot interactions | Telegram webhook | Database, GCPaymentGateway |
| **GCPaymentGateway** | Create NowPayments invoices | HTTP POST from GCBotCommand | NowPayments API, Database |
| **GCDonationHandler** | Process donation keypad input | Callback queries from bot | Database, GCPaymentGateway |
| **GCSubscriptionMonitor** | Check & remove expired subscriptions | Cloud Scheduler (every 60s) | Database, Telegram Bot API |
| **GCNotificationService** | Send payment notifications to owners | HTTP POST from webhooks | Database, Telegram Bot API |
| **GCBroadcastService** | Send subscription/donation messages | HTTP POST (manual/scheduled) | Database, Telegram Bot API |
| **NP-Webhook-10-26** | *(Existing)* Validate IPN, fetch prices | NowPayments IPN | CoinGecko API, Database |
| **GCWebhook1-10-26** | *(Existing)* Route payments instant/threshold | Cloud Tasks from NP-Webhook | Database, Cloud Tasks |
| **GCWebhook2-10-26** | *(Existing)* Send Telegram channel invites | Cloud Tasks from GCWebhook1 | Telegram Bot API |
| **GCSplit1-10-26** | *(Existing)* Process instant payouts | Cloud Tasks from GCWebhook1 | Database, GCHostPay1 |
| **GCHostPay1-3-10-26** | *(Existing)* Execute crypto payouts | Cloud Tasks from GCSplit1 | ChangeNow API, Database |

---

## Service Decomposition Strategy

### 🎨 Modular Structure (Flask Application Factory Pattern)

Each service will follow this structure:

```
GCServiceName/
├── Dockerfile                    # Container definition
├── requirements.txt              # Python dependencies
├── service.py                    # Main Flask app (application factory)
├── config_manager.py             # Configuration & secrets
├── database_manager.py           # Database operations
├── routes/
│   ├── __init__.py
│   └── main.py                   # Route blueprints
├── handlers/
│   ├── __init__.py
│   └── business_logic.py         # Core business logic
├── utils/
│   ├── __init__.py
│   └── helpers.py                # Utility functions
└── tests/
    ├── __init__.py
    ├── test_routes.py
    └── test_handlers.py
```

### 📦 Shared Module Pattern

To avoid code duplication across services, create shared modules:

```
OCTOBER/10-26/shared/
├── __init__.py
├── database.py                   # Common DB utilities
├── config.py                     # Common config loading
├── telegram_client.py            # Telegram API wrapper
└── validators.py                 # Input validation
```

**Note:** Shared modules are **copied** into each service during build (not imported as packages). This ensures:
- ✅ Each service is fully self-contained
- ✅ No runtime dependencies on external modules
- ✅ Services can evolve independently
- ✅ Deployment is simplified (single container per service)

---

## Detailed Service Specifications

### 🤖 **1. GCBotCommand** (NEW)

**Purpose:** Handle all Telegram bot command and callback interactions

**Replaces:** `bot_manager.py`, `input_handlers.py`, `menu_handlers.py`, `app_initializer.py`, `telepay10-26.py`

#### Architecture
```python
# service.py (Application Factory)
from flask import Flask
from config_manager import ConfigManager
from database_manager import DatabaseManager
from routes.webhook import webhook_bp

def create_app():
    app = Flask(__name__)

    # Load configuration
    config = ConfigManager().initialize_config()
    app.config.update(config)

    # Initialize database
    db_manager = DatabaseManager(
        config['instance_connection_name'],
        config['db_name'],
        config['db_user'],
        config['db_password']
    )
    app.db = db_manager

    # Register blueprints
    app.register_blueprint(webhook_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080)
```

#### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhook` | POST | Receive Telegram updates (commands, callbacks) |
| `/health` | GET | Health check for Cloud Run |

#### Key Operations

1. **Handle /start Command**
   - Parse start parameter (tier tokens, donation tokens)
   - Decode channel ID and subscription info
   - Route to payment gateway or donation handler

2. **Handle /database Command**
   - Start conversation for channel configuration
   - Inline keyboard for field editing
   - Validate and save to database

3. **Handle Callback Queries**
   - Payment button clicks → GCPaymentGateway
   - Donation button clicks → GCDonationHandler
   - Database edit callbacks → Update database

#### Environment Variables
```bash
TELEGRAM_BOT_TOKEN_SECRET="projects/.../secrets/telegram-bot-token/versions/latest"
DATABASE_HOST_SECRET="projects/.../secrets/database-host/versions/latest"
DATABASE_NAME_SECRET="projects/.../secrets/database-name/versions/latest"
DATABASE_USER_SECRET="projects/.../secrets/database-user/versions/latest"
DATABASE_PASSWORD_SECRET="projects/.../secrets/database-password/versions/latest"
GCPAYMENTGATEWAY_URL="https://gcpaymentgateway-10-26-pjxwjsdktq-uc.a.run.app"
GCDONATIONHANDLER_URL="https://gcdonationhandler-10-26-pjxwjsdktq-uc.a.run.app"
```

#### Error Handling
- Invalid tokens → 400 Bad Request
- Database errors → 500 Internal Server Error, retry with exponential backoff
- Telegram API errors → Log and return 200 (acknowledge webhook)

---

### 💳 **2. GCPaymentGateway** (NEW)

**Purpose:** Create payment invoices with NowPayments API

**Replaces:** `start_np_gateway.py` (PaymentGatewayManager class)

#### Architecture
```python
# service.py
from flask import Flask, request, jsonify, abort
from config_manager import ConfigManager
from handlers.payment_handler import PaymentHandler

def create_app():
    app = Flask(__name__)
    config = ConfigManager().initialize_config()
    app.payment_handler = PaymentHandler(config)

    @app.route("/create-invoice", methods=["POST"])
    def create_invoice():
        data = request.get_json()

        # Validate required fields
        required = ['user_id', 'amount', 'open_channel_id',
                   'subscription_time_days', 'payment_type']
        if not all(k in data for k in required):
            abort(400, "Missing required fields")

        # Create invoice
        result = app.payment_handler.create_invoice(
            user_id=data['user_id'],
            amount=data['amount'],
            open_channel_id=data['open_channel_id'],
            subscription_time_days=data['subscription_time_days'],
            payment_type=data['payment_type']  # 'subscription' or 'donation'
        )

        return jsonify(result), 200

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy"}), 200

    return app
```

#### Request Format
```json
{
  "user_id": 6271402111,
  "amount": 9.99,
  "open_channel_id": "-1003268562225",
  "subscription_time_days": 30,
  "payment_type": "subscription",
  "tier": 1
}
```

#### Response Format
```json
{
  "success": true,
  "invoice_url": "https://nowpayments.io/payment/...",
  "invoice_id": "12345",
  "order_id": "PGP-6271402111|-1003268562225"
}
```

#### Key Operations
1. Fetch NowPayments API token from Secret Manager
2. Fetch IPN callback URL from Secret Manager
3. Create invoice with NowPayments API
4. Return invoice URL for Telegram WebApp button

#### Dependencies
- NowPayments API (`https://api.nowpayments.io/v1/invoice`)
- Google Secret Manager
- Database (for channel info lookup)

---

### 💝 **3. GCDonationHandler** (NEW)

**Purpose:** Handle donation keypad input and validation

**Replaces:** `donation_input_handler.py` (DonationKeypadHandler class)

#### Architecture
```python
# service.py
from flask import Flask, request, jsonify, abort
from handlers.keypad_handler import KeypadHandler

def create_app():
    app = Flask(__name__)
    app.keypad_handler = KeypadHandler()

    @app.route("/keypad-input", methods=["POST"])
    def process_keypad():
        data = request.get_json()

        # Extract callback query data
        user_id = data.get('user_id')
        callback_data = data.get('callback_data')
        open_channel_id = data.get('open_channel_id')

        # Process keypad action
        result = app.keypad_handler.handle_input(
            user_id=user_id,
            callback_data=callback_data,
            open_channel_id=open_channel_id
        )

        return jsonify(result), 200

    return app
```

#### Callback Data Patterns
- `donate_digit_0` through `donate_digit_9` → Append digit
- `donate_backspace` → Remove last digit
- `donate_clear` → Clear all input
- `donate_confirm` → Submit donation amount
- `donate_cancel` → Cancel donation flow

#### Key Operations
1. Maintain donation amount state (via database session table)
2. Validate donation amount (min $1.00, max $9999.99)
3. Create inline keyboard for numeric input
4. Route confirmed amount to GCPaymentGateway

---

### ⏰ **4. GCSubscriptionMonitor** (NEW)

**Purpose:** Check for expired subscriptions and remove users from channels

**Replaces:** `subscription_manager.py` (SubscriptionManager class)

#### Architecture
```python
# service.py
from flask import Flask, jsonify
from handlers.expiration_handler import ExpirationHandler

def create_app():
    app = Flask(__name__)
    app.expiration_handler = ExpirationHandler()

    @app.route("/check-expirations", methods=["POST"])
    def check_expirations():
        """Triggered by Cloud Scheduler every 60 seconds"""
        result = app.expiration_handler.process_expired_subscriptions()

        return jsonify({
            "status": "success",
            "expired_count": result['expired_count'],
            "removed_count": result['removed_count']
        }), 200

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy"}), 200

    return app
```

#### Triggered By
**Cloud Scheduler** job configured as:
```bash
gcloud scheduler jobs create http subscription-monitor \
  --schedule="*/1 * * * *" \
  --uri="https://gcsubscriptionmonitor-10-26-pjxwjsdktq-uc.a.run.app/check-expirations" \
  --http-method=POST \
  --location=us-central1 \
  --oidc-service-account-email=telepay-scheduler@telepay-459221.iam.gserviceaccount.com
```

#### Key Operations
1. Query database for active subscriptions with `expire_date < NOW()`
2. For each expired subscription:
   - Call Telegram Bot API `banChatMember`
   - Immediately call `unbanChatMember` (allow future rejoins)
   - Update database: `is_active = FALSE`
3. Return summary statistics

#### Optimization Strategies
- **Batch Processing:** Process up to 100 expirations per invocation
- **Exponential Backoff:** Retry Telegram API errors with backoff
- **Idempotency:** Safe to run multiple times (checks `is_active` flag)

---

### 📬 **5. GCNotificationService** (NEW)

**Purpose:** Send payment notifications to channel owners

**Replaces:** `notification_service.py` (NotificationService class)

#### Architecture
```python
# service.py
from flask import Flask, request, jsonify, abort
from handlers.notification_handler import NotificationHandler

def create_app():
    app = Flask(__name__)
    app.notification_handler = NotificationHandler()

    @app.route("/send-notification", methods=["POST"])
    def send_notification():
        """
        Called by np-webhook or gcwebhook1 after successful payment
        """
        data = request.get_json()

        # Validate required fields
        required = ['open_channel_id', 'payment_type', 'payment_data']
        if not all(k in data for k in required):
            abort(400, "Missing required fields")

        # Send notification
        result = app.notification_handler.send_payment_notification(
            open_channel_id=data['open_channel_id'],
            payment_type=data['payment_type'],
            payment_data=data['payment_data']
        )

        if result:
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "failed"}), 200

    return app
```

#### Request Format (Subscription)
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

#### Request Format (Donation)
```json
{
  "open_channel_id": "-1003268562225",
  "payment_type": "donation",
  "payment_data": {
    "user_id": 6271402111,
    "username": "jane_smith",
    "amount_crypto": "0.00050",
    "amount_usd": "15.00",
    "crypto_currency": "ETH",
    "timestamp": "2025-11-12 15:45:30 UTC"
  }
}
```

#### Key Operations
1. Fetch notification settings from database (`notification_status`, `notification_id`)
2. Check if notifications enabled for channel
3. Format message based on payment type (subscription vs donation)
4. Send via Telegram Bot API `sendMessage`
5. Handle errors gracefully (user blocked bot, invalid chat_id, etc.)

---

### 📢 **6. GCBroadcastService** (NEW)

**Purpose:** Send subscription and donation messages to channels

**Replaces:** `broadcast_manager.py` (BroadcastManager class), `closed_channel_manager.py` (ClosedChannelManager class)

#### Architecture
```python
# service.py
from flask import Flask, request, jsonify, abort
from handlers.broadcast_handler import BroadcastHandler

def create_app():
    app = Flask(__name__)
    app.broadcast_handler = BroadcastHandler()

    @app.route("/broadcast-open-channels", methods=["POST"])
    def broadcast_open():
        """Send subscription tier buttons to all open channels"""
        result = app.broadcast_handler.broadcast_to_open_channels()
        return jsonify(result), 200

    @app.route("/broadcast-closed-channels", methods=["POST"])
    def broadcast_closed():
        """Send donation buttons to all closed channels"""
        result = app.broadcast_handler.broadcast_to_closed_channels()
        return jsonify(result), 200

    @app.route("/broadcast-single-channel", methods=["POST"])
    def broadcast_single():
        """Send message to a specific channel"""
        data = request.get_json()
        result = app.broadcast_handler.broadcast_to_channel(
            channel_id=data['channel_id'],
            channel_type=data['channel_type']  # 'open' or 'closed'
        )
        return jsonify(result), 200

    return app
```

#### Trigger Options
1. **Manual:** HTTP POST to endpoints (via curl or Postman)
2. **Scheduled:** Cloud Scheduler for periodic broadcasts
3. **Event-Based:** New channel creation triggers broadcast

#### Key Operations
1. **Open Channel Broadcast:**
   - Fetch all open channels from database
   - For each channel, create subscription tier buttons
   - Format message with channel title/description
   - Send via Telegram Bot API

2. **Closed Channel Broadcast:**
   - Fetch all closed channels from database
   - For each channel, create donation button
   - Format message with custom donation message
   - Send via Telegram Bot API

---

## Database Strategy

### 🗄️ Database Schema (No Changes Required)

The existing PostgreSQL schema in `telepaypsql` remains **unchanged**:

```sql
-- Main channel configuration
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

-- User subscriptions
CREATE TABLE private_channel_users_database (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    private_channel_id BIGINT NOT NULL,
    sub_time INTEGER,
    sub_price DECIMAL(10,2),
    expire_time TIME,
    expire_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payment tracking (idempotency)
CREATE TABLE processed_payments (
    payment_id TEXT PRIMARY KEY,
    order_id TEXT UNIQUE,
    gcwebhook1_processed BOOLEAN DEFAULT FALSE,
    gcwebhook1_processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Additional tables (batch_conversions, payout_accumulation_que, etc.) remain unchanged
```

### 🔗 Database Connection Pattern

All services use the **Cloud SQL Connector** for secure connections:

```python
# database_manager.py (shared module)
from google.cloud.sql.connector import Connector
import sqlalchemy

class DatabaseManager:
    def __init__(self, instance_connection_name, db_name, db_user, db_password):
        self.connector = Connector()
        self.pool = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=lambda: self.connector.connect(
                instance_connection_name,
                "pg8000",
                user=db_user,
                password=db_password,
                db=db_name,
            )
        )

    def get_connection(self):
        return self.pool.connect()

    def close(self):
        self.connector.close()
```

### 🔐 Connection Security
- ✅ Uses IAM authentication (no hardcoded passwords)
- ✅ Cloud SQL Proxy via Connector (encrypted connections)
- ✅ Connection pooling for efficiency
- ✅ Automatic retry with exponential backoff

---

## Deployment Strategy

### 🚀 Google Cloud Run Deployment

Each service is deployed as a **separate Cloud Run service**:

```bash
# Example: Deploy GCBotCommand
gcloud run deploy gcbotcommand-10-26 \
  --source=./GCBotCommand-10-26 \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="TELEGRAM_BOT_TOKEN_SECRET=projects/.../secrets/telegram-bot-token/versions/latest" \
  --set-env-vars="DATABASE_HOST_SECRET=projects/.../secrets/database-host/versions/latest" \
  --min-instances=1 \
  --max-instances=10 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300s \
  --concurrency=80
```

### 📦 Dockerfile Template

Each service uses a consistent Dockerfile:

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

### 🔧 Configuration Management

All secrets managed via **Google Secret Manager**:

```bash
# Create secrets
gcloud secrets create telegram-bot-token --data-file=token.txt
gcloud secrets create database-password --data-file=password.txt

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding telegram-bot-token \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 📊 Service Dependencies

```
GCBotCommand ──┬──> GCPaymentGateway
               ├──> GCDonationHandler
               └──> Database

GCPaymentGateway ──> NowPayments API
                   └──> Database

GCDonationHandler ──> Database

GCSubscriptionMonitor ──> Database
                         └──> Telegram Bot API

GCNotificationService ──> Database
                         └──> Telegram Bot API

GCBroadcastService ──> Database
                      └──> Telegram Bot API
```

---

## Migration Phases

### 📅 Phase 1: Infrastructure Setup (Week 1)

**Goal:** Prepare environment for new services

**Tasks:**
1. ✅ Create service directories and boilerplate code
2. ✅ Set up shared modules (`shared/database.py`, `shared/config.py`)
3. ✅ Create Dockerfiles and requirements.txt for each service
4. ✅ Set up Cloud Run service accounts and IAM permissions
5. ✅ Create Cloud Scheduler jobs for GCSubscriptionMonitor
6. ✅ Document deployment procedures

**Deliverables:**
- 6 new service directories with boilerplate code
- Deployment scripts for each service
- Updated IAM policies

---

### 📅 Phase 2: Core Services Migration (Week 2-3)

**Goal:** Deploy and test core payment and bot services

**Priority Order:**
1. **GCPaymentGateway** (highest priority - critical path)
2. **GCBotCommand** (depends on GCPaymentGateway)
3. **GCDonationHandler** (depends on GCBotCommand)

**Testing Strategy:**
- Deploy to staging environment first
- Test with test Telegram bot token
- Verify NowPayments sandbox integration
- Load test with 100 concurrent requests

**Success Criteria:**
- ✅ Users can initiate subscriptions via bot
- ✅ Payment invoices are created successfully
- ✅ Donation flow works end-to-end
- ✅ No data loss during migration

---

### 📅 Phase 3: Background Services Migration (Week 4)

**Goal:** Deploy subscription monitoring and notification services

**Priority Order:**
1. **GCSubscriptionMonitor** (automated expiration handling)
2. **GCNotificationService** (payment notifications)

**Testing Strategy:**
- Create test subscriptions with short expiration times
- Verify users are removed from channels correctly
- Test notification delivery to channel owners
- Monitor Cloud Scheduler logs

**Success Criteria:**
- ✅ Expired subscriptions are processed within 60 seconds
- ✅ Notifications are delivered to channel owners
- ✅ No false positives (active subscriptions not removed)

---

### 📅 Phase 4: Broadcast Services Migration (Week 5)

**Goal:** Deploy broadcast messaging services

**Priority Order:**
1. **GCBroadcastService** (open and closed channel messages)

**Testing Strategy:**
- Test broadcast to single channel first
- Test batch broadcast to all channels
- Verify message formatting and buttons
- Monitor rate limits and errors

**Success Criteria:**
- ✅ Messages sent to all configured channels
- ✅ Buttons function correctly
- ✅ Error handling for channels where bot is not admin

---

### 📅 Phase 5: Decommission Monolithic Bot (Week 6)

**Goal:** Safely decommission TelePay10-26 monolithic bot

**Tasks:**
1. ✅ Verify all functionality migrated to new services
2. ✅ Run parallel testing (old bot + new services)
3. ✅ Monitor for 48 hours with both systems active
4. ✅ Gradually reduce old bot instances
5. ✅ Archive TelePay10-26 code to `ARCHIVES/TelePay10-26-MONOLITHIC`

**Rollback Plan:**
- Keep old bot deployment configuration
- Maintain ability to redeploy within 5 minutes
- Keep database unchanged (no schema migrations)

**Success Criteria:**
- ✅ Zero downtime during cutover
- ✅ All metrics (payment success rate, notification delivery) maintained or improved
- ✅ Old bot can be redeployed if needed

---

## Risk Assessment & Mitigation

### ⚠️ Risk Matrix

| Risk | Probability | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| **Service Downtime During Migration** | Medium | High | Blue-green deployment, gradual rollout |
| **Database Connection Pool Exhaustion** | Low | High | Configure connection limits, monitoring |
| **Telegram Rate Limits** | Medium | Medium | Implement exponential backoff, batch processing |
| **NowPayments API Failures** | Low | High | Retry logic, fallback notifications |
| **Cloud Run Cold Start Latency** | Medium | Low | Use min-instances=1 for critical services |
| **Webhook URL Changes** | Low | High | Use stable URLs, version endpoints |
| **Secret Manager Access Errors** | Low | High | IAM validation, fallback to env vars |
| **Data Loss During Cutover** | Low | Critical | No database changes, parallel testing |

### 🛡️ Mitigation Strategies

#### 1. Blue-Green Deployment
- Deploy new services alongside old bot
- Route 10% of traffic to new services
- Gradually increase to 100% over 48 hours
- Keep old bot running for quick rollback

#### 2. Database Safety
- ❌ NO schema changes during migration
- ✅ All services use existing tables
- ✅ Database queries are idempotent
- ✅ Connection pooling prevents exhaustion

#### 3. Monitoring & Alerting
- Set up Cloud Monitoring dashboards for:
  - Request latency (p50, p95, p99)
  - Error rates (4xx, 5xx)
  - Database connection pool usage
  - Telegram API rate limit consumption
- Configure alerts for:
  - Error rate > 5%
  - Latency p95 > 2 seconds
  - Database connection errors

#### 4. Rollback Procedures
- Maintain old bot deployment configuration
- Document rollback steps (see [Rollback Procedures](#rollback-procedures))
- Test rollback in staging environment
- Keep rollback playbook accessible 24/7

---

## Testing Strategy

### 🧪 Testing Pyramid

```
         ┌─────────────────┐
         │  E2E Tests      │  ← Full user flow testing
         │  (5%)           │
         └─────────────────┘
        ┌─────────────────────┐
        │  Integration Tests  │  ← Service-to-service
        │  (20%)              │
        └─────────────────────┘
       ┌─────────────────────────┐
       │  Unit Tests             │  ← Business logic
       │  (75%)                  │
       └─────────────────────────┘
```

### 1. Unit Tests (75% Coverage Target)

Test individual functions and handlers:

```python
# test_payment_handler.py
import pytest
from handlers.payment_handler import PaymentHandler

def test_create_invoice_success():
    handler = PaymentHandler(mock_config)
    result = handler.create_invoice(
        user_id=123456,
        amount=9.99,
        open_channel_id="-1003268562225",
        subscription_time_days=30,
        payment_type="subscription"
    )

    assert result['success'] == True
    assert 'invoice_url' in result
    assert result['order_id'].startswith('PGP-')

def test_create_invoice_invalid_amount():
    handler = PaymentHandler(mock_config)
    with pytest.raises(ValueError):
        handler.create_invoice(
            user_id=123456,
            amount=-5.00,  # Invalid
            open_channel_id="-1003268562225",
            subscription_time_days=30,
            payment_type="subscription"
        )
```

### 2. Integration Tests (20% Coverage Target)

Test service-to-service communication:

```python
# test_integration.py
import requests

def test_bot_to_payment_gateway_flow():
    # Simulate bot sending payment request
    response = requests.post(
        "https://gcpaymentgateway-10-26-pjxwjsdktq-uc.a.run.app/create-invoice",
        json={
            "user_id": 123456,
            "amount": 9.99,
            "open_channel_id": "-1003268562225",
            "subscription_time_days": 30,
            "payment_type": "subscription",
            "tier": 1
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data['success'] == True
    assert 'invoice_url' in data
```

### 3. End-to-End Tests (5% Coverage Target)

Test complete user flows:

```python
# test_e2e.py
from telegram import Bot
import time

def test_complete_subscription_flow():
    """Test full subscription flow from /start to channel access"""
    bot = Bot(token=TEST_BOT_TOKEN)

    # 1. User clicks /start with tier token
    bot.send_message(
        chat_id=TEST_USER_ID,
        text="/start encoded_tier_token"
    )

    # 2. Verify payment invoice created
    # 3. Simulate payment completion
    # 4. Verify user added to closed channel
    # 5. Verify notification sent to channel owner

    # This test requires NowPayments sandbox and test database
```

### 4. Load Testing

Use `locust` for load testing:

```python
# locustfile.py
from locust import HttpUser, task, between

class GCBotCommandUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def webhook_request(self):
        self.client.post("/webhook", json={
            "update_id": 123456,
            "message": {
                "message_id": 1,
                "from": {"id": 123456, "first_name": "Test"},
                "chat": {"id": 123456, "type": "private"},
                "text": "/start"
            }
        })
```

Run load test:
```bash
locust -f locustfile.py --host=https://gcbotcommand-10-26-pjxwjsdktq-uc.a.run.app
```

Target: **100 requests/second** with **p95 latency < 500ms**

---

## Rollback Procedures

### 🔄 Emergency Rollback (< 5 minutes)

If critical issues arise during migration:

#### Step 1: Revert Bot Webhook
```bash
# Point Telegram webhook back to old bot
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://tph10-26-pjxwjsdktq-uc.a.run.app/webhook"
```

#### Step 2: Scale Up Old Bot
```bash
# Ensure old bot is running
gcloud run services update tph10-26 \
  --region=us-central1 \
  --min-instances=1 \
  --max-instances=10
```

#### Step 3: Disable Cloud Scheduler Jobs
```bash
# Pause new subscription monitor
gcloud scheduler jobs pause subscription-monitor --location=us-central1
```

#### Step 4: Monitor & Verify
```bash
# Check old bot logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=tph10-26" \
  --limit=50 \
  --format=json
```

### 📊 Rollback Decision Criteria

Trigger rollback if any of these conditions occur:

| Metric | Threshold | Action |
|--------|-----------|--------|
| **Error Rate** | > 10% for 5 minutes | Immediate rollback |
| **Payment Success Rate** | < 90% for 10 minutes | Immediate rollback |
| **Notification Delivery Rate** | < 80% for 15 minutes | Investigate, rollback if no fix |
| **Database Connection Errors** | > 5 errors/minute | Immediate rollback |
| **User Reports** | > 10 complaints in 30 minutes | Investigate, rollback if critical |

### ✅ Post-Rollback Actions

1. **Root Cause Analysis:** Document what went wrong
2. **Fix & Re-test:** Address issues in staging environment
3. **Stakeholder Communication:** Notify team of rollback and next steps
4. **Retry Timeline:** Plan next migration attempt

---

## Appendix: Service Configuration Reference

### Environment Variables Summary

| Service | Required Env Vars |
|---------|-------------------|
| **GCBotCommand** | `TELEGRAM_BOT_TOKEN_SECRET`, `DATABASE_*_SECRET`, `GCPAYMENTGATEWAY_URL`, `GCDONATIONHANDLER_URL` |
| **GCPaymentGateway** | `NOWPAYMENTS_API_KEY_SECRET`, `NOWPAYMENTS_IPN_CALLBACK_URL_SECRET`, `DATABASE_*_SECRET` |
| **GCDonationHandler** | `DATABASE_*_SECRET`, `GCPAYMENTGATEWAY_URL` |
| **GCSubscriptionMonitor** | `TELEGRAM_BOT_TOKEN_SECRET`, `DATABASE_*_SECRET` |
| **GCNotificationService** | `TELEGRAM_BOT_TOKEN_SECRET`, `DATABASE_*_SECRET` |
| **GCBroadcastService** | `TELEGRAM_BOT_TOKEN_SECRET`, `DATABASE_*_SECRET` |

### Cloud Run Service Sizing

| Service | CPU | Memory | Min Instances | Max Instances | Timeout |
|---------|-----|--------|--------------|--------------|---------|
| **GCBotCommand** | 1 | 512Mi | 1 | 10 | 300s |
| **GCPaymentGateway** | 1 | 256Mi | 0 | 5 | 60s |
| **GCDonationHandler** | 0.5 | 256Mi | 0 | 5 | 30s |
| **GCSubscriptionMonitor** | 1 | 512Mi | 0 | 1 | 300s |
| **GCNotificationService** | 0.5 | 256Mi | 0 | 10 | 60s |
| **GCBroadcastService** | 1 | 512Mi | 0 | 3 | 300s |

### Cost Estimates (Monthly)

Based on **10,000 subscriptions/month** and **1,000 donations/month**:

| Service | Estimated Requests/Month | Estimated Cost |
|---------|--------------------------|----------------|
| **GCBotCommand** | ~50,000 | $5-10 |
| **GCPaymentGateway** | ~11,000 | $2-5 |
| **GCDonationHandler** | ~5,000 | $1-3 |
| **GCSubscriptionMonitor** | ~43,200 (60s × 30 days) | $3-5 |
| **GCNotificationService** | ~11,000 | $2-5 |
| **GCBroadcastService** | ~100 (manual triggers) | $0-1 |
| **Total** | | **$13-29/month** |

**Note:** Costs include Cloud Run invocations, CPU/memory usage, and database connections. Does not include Cloud SQL costs (existing).

---

## Conclusion

This refactoring architecture transforms TelePay from a monolithic, long-running bot into a **modern, scalable, microservices architecture** following industry best practices:

✅ **Modularity:** Each service has a single, well-defined responsibility
✅ **Scalability:** Services scale independently based on demand
✅ **Reliability:** Failures are isolated and don't cascade
✅ **Maintainability:** Clean separation enables easier debugging
✅ **Cost Efficiency:** Serverless architecture minimizes idle costs
✅ **Observability:** Each service logs independently for better monitoring

The phased migration approach ensures **zero downtime** and provides **rollback safety** at every step. By following Flask application factory patterns and Cloud Run best practices, we create a robust, production-ready system that can evolve with future requirements.

---

**Next Steps:**
1. Review and approve this architecture document
2. Begin Phase 1: Infrastructure Setup
3. Schedule weekly progress reviews
4. Maintain this document as living documentation

**Document Owner:** Claude
**Review Date:** 2025-11-12
**Next Review:** After Phase 1 completion
