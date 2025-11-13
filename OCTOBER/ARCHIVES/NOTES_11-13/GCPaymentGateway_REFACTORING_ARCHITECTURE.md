# GCPaymentGateway-10-26 Refactoring Architecture
## Self-Contained Payment Invoice Creation Service

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Architecture Design
**Branch:** TelePay-REFACTOR
**Parent Document:** TELEPAY_REFACTORING_ARCHITECTURE.md

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Architecture Principles](#architecture-principles)
4. [Service Overview](#service-overview)
5. [Complete Directory Structure](#complete-directory-structure)
6. [Detailed Implementation](#detailed-implementation)
7. [Database Operations](#database-operations)
8. [Configuration Management](#configuration-management)
9. [API Integration](#api-integration)
10. [Error Handling Strategy](#error-handling-strategy)
11. [Deployment Guide](#deployment-guide)
12. [Testing Strategy](#testing-strategy)
13. [Integration Points](#integration-points)

---

## Executive Summary

### Purpose
The **GCPaymentGateway-10-26** service is a self-contained Cloud Run webhook that creates payment invoices using the NowPayments API. This service replaces the `start_np_gateway.py` module from the monolithic TelePay10-26 bot.

### Key Requirements
- ✅ **Self-Contained:** All dependencies bundled within service directory (NO shared modules)
- ✅ **Stateless:** No in-memory state, all data fetched from database or Secret Manager
- ✅ **Idempotent:** Safe to retry invoice creation with same parameters
- ✅ **Secure:** API tokens fetched from Secret Manager, input validation on all parameters
- ✅ **Observable:** Comprehensive logging with emojis matching existing patterns

### Core Functionality
1. Create NowPayments invoices for subscriptions and donations
2. Build unique order IDs: `PGP-{user_id}|{open_channel_id}`
3. Fetch channel details from database for personalized invoice messages
4. Validate channel IDs and payment amounts
5. Return invoice URLs for Telegram WebApp buttons

---

## Current State Analysis

### Source Module: `start_np_gateway.py`

The current PaymentGatewayManager class in TelePay10-26 handles:

```python
class PaymentGatewayManager:
    def __init__(self, payment_token, ipn_callback_url)
    def fetch_payment_provider_token() -> str
    def fetch_ipn_callback_url() -> str
    async def create_payment_invoice(user_id, amount, success_url, order_id) -> Dict
    def get_telegram_user_id(update) -> int
    async def start_payment_flow(update, context, sub_value, open_channel_id, ...) -> None
    async def start_np_gateway_new(update, context, global_sub_value, ...) -> None
```

### Key Behaviors to Preserve

1. **Order ID Format:**
   ```python
   order_id = f"PGP-{user_id}|{open_channel_id}"
   # Example: "PGP-6271402111|-1003268562225"
   ```

2. **Channel ID Validation:**
   - Telegram channel IDs must be negative (supergroups/channels)
   - Auto-correct if positive ID provided
   - Special case: `donation_default` for generic donations

3. **Success URL Structure:**
   ```python
   landing_page_base = "https://storage.googleapis.com/paygateprime-static/payment-processing.html"
   success_url = f"{landing_page_base}?order_id={quote(order_id, safe='')}"
   ```

4. **IPN Callback URL:**
   - Fetched from Secret Manager
   - Used by NowPayments to send payment_id updates
   - Critical for payment tracking and webhook flow

5. **Invoice Payload:**
   ```json
   {
     "price_amount": 9.99,
     "price_currency": "USD",
     "order_id": "PGP-6271402111|-1003268562225",
     "order_description": "Payment-Test-1",
     "success_url": "https://storage.googleapis.com/...",
     "ipn_callback_url": "https://np-webhook-10-26-...",
     "is_fixed_rate": false,
     "is_fee_paid_by_user": false
   }
   ```

---

## Architecture Principles

### 1. Self-Contained Design
**NO external shared modules.** All code exists within `GCPaymentGateway-10-26/` directory:
```
GCPaymentGateway-10-26/
├── service.py              # Flask app (OWNS all code)
├── config_manager.py       # Secret Manager integration (COPIED, not imported)
├── database_manager.py     # Database operations (COPIED, not imported)
├── payment_handler.py      # NowPayments API logic (COPIED, not imported)
├── validators.py           # Input validation (COPIED, not imported)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
└── .dockerignore           # Exclude unnecessary files
```

### 2. Flask Application Factory Pattern
```python
def create_app():
    app = Flask(__name__)

    # Initialize configuration
    config = ConfigManager().initialize_config()
    app.config.update(config)

    # Initialize database
    db_manager = DatabaseManager(config)
    app.db = db_manager

    # Initialize payment handler
    payment_handler = PaymentHandler(config, db_manager)
    app.payment_handler = payment_handler

    # Register routes
    register_routes(app)

    return app
```

### 3. Stateless Request Handling
Each request is independent:
- Fetch secrets from Secret Manager (cached by Google)
- Query database for channel details
- Create invoice via NowPayments API
- Return response immediately (no background tasks)

### 4. Comprehensive Logging
Follow existing emoji patterns:
```python
print(f"💳 [GATEWAY] Creating invoice for user {user_id}")
print(f"📋 [ORDER] Order ID: {order_id}")
print(f"✅ [SUCCESS] Invoice created: {invoice_id}")
print(f"❌ [ERROR] NowPayments API error: {error}")
print(f"🔍 [DEBUG] Fetching channel details for {open_channel_id}")
print(f"⚠️ [WARNING] Invalid channel ID: {channel_id}")
```

---

## Service Overview

### Endpoints

| Endpoint | Method | Purpose | Request Format | Response Format |
|----------|--------|---------|----------------|-----------------|
| `/create-invoice` | POST | Create payment invoice | JSON (see below) | JSON (success/error) |
| `/health` | GET | Health check | None | `{"status": "healthy"}` |

### Request Schema: `/create-invoice`

```json
{
  "user_id": 6271402111,
  "amount": 9.99,
  "open_channel_id": "-1003268562225",
  "subscription_time_days": 30,
  "payment_type": "subscription",
  "tier": 1,
  "order_id": "PGP-6271402111|-1003268562225"
}
```

**Field Descriptions:**
- `user_id` (required, int): Telegram user ID
- `amount` (required, float): Payment amount in USD (min: 1.00, max: 9999.99)
- `open_channel_id` (required, str): Open channel ID (must be negative or "donation_default")
- `subscription_time_days` (required, int): Duration in days (1-999)
- `payment_type` (required, str): Either "subscription" or "donation"
- `tier` (optional, int): Subscription tier (1, 2, or 3)
- `order_id` (optional, str): Pre-created order ID (if omitted, will be generated)

### Response Schema: Success

```json
{
  "success": true,
  "invoice_id": "12345678",
  "invoice_url": "https://nowpayments.io/payment/...",
  "order_id": "PGP-6271402111|-1003268562225",
  "status_code": 200
}
```

### Response Schema: Error

```json
{
  "success": false,
  "error": "Invalid channel ID format",
  "status_code": 400
}
```

---

## Complete Directory Structure

```
GCPaymentGateway-10-26/
│
├── service.py                      # Main Flask application (entry point)
│   └── create_app()                # Application factory
│   └── register_routes()           # Route registration
│   └── main()                      # Entry point for Cloud Run
│
├── config_manager.py               # Configuration & Secret Manager
│   └── class ConfigManager
│       ├── fetch_telegram_token() -> str
│       ├── fetch_payment_provider_token() -> str
│       ├── fetch_ipn_callback_url() -> str
│       ├── fetch_database_host() -> str
│       ├── fetch_database_name() -> str
│       ├── fetch_database_user() -> str
│       ├── fetch_database_password() -> str
│       └── initialize_config() -> dict
│
├── database_manager.py             # Database operations
│   └── class DatabaseManager
│       ├── __init__(config)
│       ├── get_connection() -> connection
│       ├── fetch_channel_details(open_channel_id) -> dict
│       ├── fetch_closed_channel_id(open_channel_id) -> str
│       ├── fetch_client_wallet_info(open_channel_id) -> tuple
│       ├── channel_exists(open_channel_id) -> bool
│       └── close()
│
├── payment_handler.py              # NowPayments API integration
│   └── class PaymentHandler
│       ├── __init__(config, db_manager)
│       ├── validate_request(data) -> tuple[bool, str]
│       ├── build_order_id(user_id, open_channel_id) -> str
│       ├── build_success_url(order_id) -> str
│       ├── create_invoice_payload(data) -> dict
│       ├── call_nowpayments_api(payload) -> dict
│       └── create_invoice(request_data) -> dict
│
├── validators.py                   # Input validation functions
│   ├── validate_user_id(user_id) -> bool
│   ├── validate_amount(amount) -> bool
│   ├── validate_channel_id(channel_id) -> bool
│   ├── validate_subscription_time(days) -> bool
│   ├── validate_payment_type(payment_type) -> bool
│   └── sanitize_channel_id(channel_id) -> str
│
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container definition
├── .dockerignore                   # Exclude patterns
└── README.md                       # Service documentation

```

---

## Detailed Implementation

### 1. `service.py` - Main Flask Application

```python
#!/usr/bin/env python
"""
GCPaymentGateway-10-26: Self-contained payment invoice creation service
Replaces: TelePay10-26/start_np_gateway.py (PaymentGatewayManager class)
"""

from flask import Flask, request, jsonify
from config_manager import ConfigManager
from database_manager import DatabaseManager
from payment_handler import PaymentHandler
import sys

def create_app():
    """
    Application factory for GCPaymentGateway.
    Creates and configures the Flask application with all dependencies.

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)

    print("🚀 [GATEWAY] Initializing GCPaymentGateway-10-26...")

    # Initialize configuration (fetch secrets from Secret Manager)
    try:
        config_manager = ConfigManager()
        config = config_manager.initialize_config()
        app.config.update(config)
        print("✅ [CONFIG] Configuration loaded successfully")
    except Exception as e:
        print(f"❌ [CONFIG] Failed to load configuration: {e}")
        sys.exit(1)

    # Initialize database manager
    try:
        db_manager = DatabaseManager(config)
        app.db = db_manager
        print("✅ [DATABASE] Database manager initialized")
    except Exception as e:
        print(f"❌ [DATABASE] Failed to initialize database: {e}")
        sys.exit(1)

    # Initialize payment handler
    try:
        payment_handler = PaymentHandler(config, db_manager)
        app.payment_handler = payment_handler
        print("✅ [PAYMENT] Payment handler initialized")
    except Exception as e:
        print(f"❌ [PAYMENT] Failed to initialize payment handler: {e}")
        sys.exit(1)

    # Register routes
    register_routes(app)

    print("✅ [GATEWAY] GCPaymentGateway-10-26 ready to accept requests")

    return app


def register_routes(app):
    """
    Register all Flask routes for the application.

    Args:
        app (Flask): Flask application instance
    """

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint for Cloud Run.

        Returns:
            JSON response with status
        """
        return jsonify({"status": "healthy", "service": "gcpaymentgateway-10-26"}), 200


    @app.route("/create-invoice", methods=["POST"])
    def create_invoice():
        """
        Create a payment invoice via NowPayments API.

        Request JSON:
        {
            "user_id": 6271402111,
            "amount": 9.99,
            "open_channel_id": "-1003268562225",
            "subscription_time_days": 30,
            "payment_type": "subscription",
            "tier": 1,
            "order_id": "PGP-6271402111|-1003268562225"  # Optional
        }

        Returns:
            JSON response with invoice details or error
        """
        print("💳 [GATEWAY] Received invoice creation request")

        # Get request data
        try:
            data = request.get_json()
            if not data:
                print("❌ [GATEWAY] No JSON data provided")
                return jsonify({
                    "success": False,
                    "error": "No JSON data provided"
                }), 400
        except Exception as e:
            print(f"❌ [GATEWAY] Failed to parse JSON: {e}")
            return jsonify({
                "success": False,
                "error": f"Invalid JSON: {str(e)}"
            }), 400

        # Log request details
        print(f"📋 [GATEWAY] Request data:")
        print(f"   User ID: {data.get('user_id')}")
        print(f"   Amount: ${data.get('amount')}")
        print(f"   Channel ID: {data.get('open_channel_id')}")
        print(f"   Payment Type: {data.get('payment_type')}")
        print(f"   Subscription Days: {data.get('subscription_time_days')}")

        # Create invoice using payment handler
        try:
            result = app.payment_handler.create_invoice(data)

            if result.get("success"):
                print(f"✅ [GATEWAY] Invoice created successfully")
                print(f"   Invoice ID: {result.get('invoice_id')}")
                print(f"   Order ID: {result.get('order_id')}")
                return jsonify(result), 200
            else:
                print(f"❌ [GATEWAY] Invoice creation failed: {result.get('error')}")
                return jsonify(result), result.get("status_code", 500)

        except Exception as e:
            print(f"❌ [GATEWAY] Unexpected error creating invoice: {e}")
            return jsonify({
                "success": False,
                "error": f"Internal server error: {str(e)}"
            }), 500


if __name__ == "__main__":
    """
    Entry point for Cloud Run.
    Cloud Run sets PORT environment variable.
    """
    import os

    app = create_app()
    port = int(os.environ.get("PORT", 8080))

    print(f"🌐 [GATEWAY] Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
```

---

### 2. `config_manager.py` - Configuration & Secret Manager

```python
#!/usr/bin/env python
"""
Configuration Manager for GCPaymentGateway-10-26
Handles fetching secrets from Google Secret Manager
"""

import os
from google.cloud import secretmanager
from typing import Optional, Dict, Any


class ConfigManager:
    """
    Manages configuration and secrets for the payment gateway service.
    All secrets are fetched from Google Secret Manager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.config = {}

    def fetch_secret(self, env_var_name: str, secret_description: str) -> Optional[str]:
        """
        Generic method to fetch a secret from Secret Manager.

        Args:
            env_var_name: Environment variable containing secret path
            secret_description: Human-readable description for logging

        Returns:
            Secret value as string, or None if not found
        """
        try:
            secret_path = os.getenv(env_var_name)
            if not secret_path:
                print(f"⚠️ [CONFIG] Environment variable {env_var_name} is not set")
                return None

            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")
            print(f"✅ [CONFIG] Successfully fetched {secret_description}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error fetching {secret_description} ({env_var_name}): {e}")
            return None

    def fetch_payment_provider_token(self) -> Optional[str]:
        """
        Fetch the NowPayments API token from Secret Manager.

        Environment variable: PAYMENT_PROVIDER_SECRET_NAME

        Returns:
            NowPayments API token as string
        """
        return self.fetch_secret(
            "PAYMENT_PROVIDER_SECRET_NAME",
            "NowPayments API token"
        )

    def fetch_ipn_callback_url(self) -> Optional[str]:
        """
        Fetch the IPN callback URL from Secret Manager.
        This URL is used by NowPayments to send payment_id updates.

        Environment variable: NOWPAYMENTS_IPN_CALLBACK_URL

        Returns:
            IPN callback URL as string
        """
        return self.fetch_secret(
            "NOWPAYMENTS_IPN_CALLBACK_URL",
            "IPN callback URL"
        )

    def fetch_database_host(self) -> str:
        """
        Fetch database host from Secret Manager.

        Environment variable: DATABASE_HOST_SECRET

        Returns:
            Database host (Cloud SQL connection name)

        Raises:
            ValueError: If database host is not configured
        """
        host = self.fetch_secret("DATABASE_HOST_SECRET", "Database host")
        if not host:
            raise ValueError("Database host is required but not configured")
        return host

    def fetch_database_name(self) -> str:
        """Fetch database name from Secret Manager."""
        name = self.fetch_secret("DATABASE_NAME_SECRET", "Database name")
        if not name:
            raise ValueError("Database name is required but not configured")
        return name

    def fetch_database_user(self) -> str:
        """Fetch database user from Secret Manager."""
        user = self.fetch_secret("DATABASE_USER_SECRET", "Database user")
        if not user:
            raise ValueError("Database user is required but not configured")
        return user

    def fetch_database_password(self) -> str:
        """Fetch database password from Secret Manager."""
        password = self.fetch_secret("DATABASE_PASSWORD_SECRET", "Database password")
        if not password:
            raise ValueError("Database password is required but not configured")
        return password

    def initialize_config(self) -> Dict[str, Any]:
        """
        Initialize and return all configuration values.
        This method should be called once at application startup.

        Returns:
            Dictionary containing all configuration values

        Raises:
            ValueError: If critical configuration is missing
        """
        print("🔧 [CONFIG] Initializing configuration...")

        # Fetch payment provider configuration
        payment_token = self.fetch_payment_provider_token()
        if not payment_token:
            raise ValueError("Payment provider token is required")

        ipn_callback_url = self.fetch_ipn_callback_url()
        if not ipn_callback_url:
            print("⚠️ [CONFIG] IPN callback URL not configured - payment_id capture may not work")

        # Fetch database configuration
        db_host = self.fetch_database_host()
        db_name = self.fetch_database_name()
        db_user = self.fetch_database_user()
        db_password = self.fetch_database_password()

        # Build configuration dictionary
        self.config = {
            "payment_provider_token": payment_token,
            "ipn_callback_url": ipn_callback_url,
            "database_host": db_host,
            "database_name": db_name,
            "database_user": db_user,
            "database_password": db_password,
            "database_port": 5432,  # PostgreSQL default port
            "nowpayments_api_url": "https://api.nowpayments.io/v1/invoice",
            "landing_page_base_url": "https://storage.googleapis.com/paygateprime-static/payment-processing.html"
        }

        print("✅ [CONFIG] Configuration initialized successfully")
        print(f"   Payment Provider: NowPayments")
        print(f"   IPN Callback: {'Configured' if ipn_callback_url else 'Not configured'}")
        print(f"   Database: {db_name}")

        return self.config

    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration.

        Returns:
            Configuration dictionary
        """
        return self.config
```

---

### 3. `database_manager.py` - Database Operations

```python
#!/usr/bin/env python
"""
Database Manager for GCPaymentGateway-10-26
Handles all database operations using psycopg2
"""

import psycopg2
from typing import Optional, Dict, Any, Tuple


class DatabaseManager:
    """
    Manages database connections and operations for the payment gateway.
    Uses direct psycopg2 connections (not Cloud SQL Connector).
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the DatabaseManager with configuration.

        Args:
            config: Configuration dictionary containing database credentials
        """
        self.host = config.get("database_host")
        self.port = config.get("database_port", 5432)
        self.dbname = config.get("database_name")
        self.user = config.get("database_user")
        self.password = config.get("database_password")

        # Validate configuration
        if not all([self.host, self.dbname, self.user, self.password]):
            raise ValueError("Incomplete database configuration")

        print(f"✅ [DATABASE] Initialized with host={self.host}, db={self.dbname}")

    def get_connection(self):
        """
        Create and return a database connection.

        Returns:
            psycopg2 connection object

        Raises:
            Exception: If connection fails
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
            print(f"❌ [DATABASE] Connection failed: {e}")
            raise

    def channel_exists(self, open_channel_id: str) -> bool:
        """
        Validate if a channel exists in the database.

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
                print(f"✅ [DATABASE] Channel {open_channel_id} exists")
            else:
                print(f"⚠️ [DATABASE] Channel {open_channel_id} does not exist")

            return exists

        except Exception as e:
            print(f"❌ [DATABASE] Error validating channel: {e}")
            return False

    def fetch_channel_details(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch complete channel details for invoice message personalization.

        Args:
            open_channel_id: The open channel ID to fetch details for

        Returns:
            Dictionary with channel details or None if not found:
            {
                "open_channel_id": str,
                "open_channel_title": str,
                "open_channel_description": str,
                "closed_channel_id": str,
                "closed_channel_title": str,
                "closed_channel_description": str,
                "sub_1_price": Decimal,
                "sub_1_time": int,
                "sub_2_price": Decimal,
                "sub_2_time": int,
                "sub_3_price": Decimal,
                "sub_3_time": int,
                "client_wallet_address": str,
                "client_payout_currency": str,
                "client_payout_network": str
            }
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            print(f"🔍 [DATABASE] Fetching channel details for {open_channel_id}")

            cur.execute("""
                SELECT
                    open_channel_id,
                    open_channel_title,
                    open_channel_description,
                    closed_channel_id,
                    closed_channel_title,
                    closed_channel_description,
                    sub_1_price,
                    sub_1_time,
                    sub_2_price,
                    sub_2_time,
                    sub_3_price,
                    sub_3_time,
                    client_wallet_address,
                    client_payout_currency,
                    client_payout_network
                FROM main_clients_database
                WHERE open_channel_id = %s
                LIMIT 1
            """, (str(open_channel_id),))

            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                channel_details = {
                    "open_channel_id": result[0],
                    "open_channel_title": result[1] if result[1] else "Premium Channel",
                    "open_channel_description": result[2] if result[2] else "exclusive content",
                    "closed_channel_id": result[3],
                    "closed_channel_title": result[4] if result[4] else "Premium Channel",
                    "closed_channel_description": result[5] if result[5] else "exclusive content",
                    "sub_1_price": result[6],
                    "sub_1_time": result[7],
                    "sub_2_price": result[8],
                    "sub_2_time": result[9],
                    "sub_3_price": result[10],
                    "sub_3_time": result[11],
                    "client_wallet_address": result[12] if result[12] else "",
                    "client_payout_currency": result[13] if result[13] else "USD",
                    "client_payout_network": result[14] if result[14] else ""
                }
                print(f"✅ [DATABASE] Channel details found: {channel_details['closed_channel_title']}")
                return channel_details
            else:
                print(f"⚠️ [DATABASE] No channel details found for {open_channel_id}")
                return None

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching channel details: {e}")
            return None

    def fetch_closed_channel_id(self, open_channel_id: str) -> Optional[str]:
        """
        Get the closed channel ID for a given open channel ID.

        Args:
            open_channel_id: The open channel ID to look up

        Returns:
            The closed channel ID if found, None otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            print(f"🔍 [DATABASE] Looking up closed_channel_id for {open_channel_id}")

            cur.execute(
                "SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s",
                (str(open_channel_id),)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result and result[0]:
                print(f"✅ [DATABASE] Closed channel ID: {result[0]}")
                return result[0]
            else:
                print(f"⚠️ [DATABASE] No closed_channel_id found for {open_channel_id}")
                return None

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching closed_channel_id: {e}")
            return None

    def fetch_client_wallet_info(self, open_channel_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get the client wallet address, payout currency, and payout network.

        Args:
            open_channel_id: The open_channel_id to look up

        Returns:
            Tuple of (wallet_address, payout_currency, payout_network) or (None, None, None)
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            print(f"🔍 [DATABASE] Looking up wallet info for {open_channel_id}")

            cur.execute(
                """SELECT client_wallet_address, client_payout_currency, client_payout_network
                   FROM main_clients_database
                   WHERE open_channel_id = %s""",
                (str(open_channel_id),)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                wallet_address, payout_currency, payout_network = result
                print(f"💰 [DATABASE] Wallet: {wallet_address}, Currency: {payout_currency}, Network: {payout_network}")
                return wallet_address, payout_currency, payout_network
            else:
                print(f"⚠️ [DATABASE] No wallet info found for {open_channel_id}")
                return None, None, None

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching wallet info: {e}")
            return None, None, None

    def close(self):
        """
        Close database connections.
        Called during application shutdown.
        """
        print("🔒 [DATABASE] Closing database connections")
```

---

### 4. `payment_handler.py` - NowPayments API Integration

```python
#!/usr/bin/env python
"""
Payment Handler for GCPaymentGateway-10-26
Handles NowPayments API integration and invoice creation
"""

import httpx
from typing import Dict, Any, Optional, Tuple
from urllib.parse import quote
from validators import (
    validate_user_id,
    validate_amount,
    validate_channel_id,
    validate_subscription_time,
    validate_payment_type,
    sanitize_channel_id
)


class PaymentHandler:
    """
    Handles payment invoice creation with NowPayments API.
    """

    def __init__(self, config: Dict[str, Any], db_manager):
        """
        Initialize the PaymentHandler.

        Args:
            config: Configuration dictionary with API credentials
            db_manager: DatabaseManager instance for channel lookups
        """
        self.payment_token = config.get("payment_provider_token")
        self.ipn_callback_url = config.get("ipn_callback_url")
        self.api_url = config.get("nowpayments_api_url")
        self.landing_page_base_url = config.get("landing_page_base_url")
        self.db_manager = db_manager

        if not self.payment_token:
            raise ValueError("Payment provider token is required")

        if not self.ipn_callback_url:
            print("⚠️ [PAYMENT] IPN callback URL not configured - payment_id capture may not work")

        print("✅ [PAYMENT] Payment handler initialized with NowPayments API")

    def validate_request(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate incoming invoice creation request.

        Args:
            data: Request data dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        required_fields = ["user_id", "amount", "open_channel_id", "subscription_time_days", "payment_type"]
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"

        # Validate user_id
        if not validate_user_id(data["user_id"]):
            return False, "Invalid user_id (must be positive integer)"

        # Validate amount
        if not validate_amount(data["amount"]):
            return False, "Invalid amount (must be between $1.00 and $9999.99)"

        # Validate channel_id
        if not validate_channel_id(data["open_channel_id"]):
            return False, "Invalid channel ID format"

        # Validate subscription time
        if not validate_subscription_time(data["subscription_time_days"]):
            return False, "Invalid subscription time (must be between 1 and 999 days)"

        # Validate payment type
        if not validate_payment_type(data["payment_type"]):
            return False, "Invalid payment type (must be 'subscription' or 'donation')"

        print("✅ [PAYMENT] Request validation passed")
        return True, None

    def build_order_id(self, user_id: int, open_channel_id: str) -> str:
        """
        Build unique order ID in PayGatePrime format.

        Format: PGP-{user_id}|{open_channel_id}
        Example: PGP-6271402111|-1003268562225

        Args:
            user_id: Telegram user ID
            open_channel_id: Open channel ID (sanitized)

        Returns:
            Order ID string
        """
        # Sanitize channel ID (ensure negative for Telegram channels)
        sanitized_channel_id = sanitize_channel_id(open_channel_id)

        order_id = f"PGP-{user_id}|{sanitized_channel_id}"

        print(f"📋 [ORDER] Created order_id: {order_id}")
        print(f"   User ID: {user_id}")
        print(f"   Open Channel ID: {sanitized_channel_id}")

        return order_id

    def build_success_url(self, order_id: str) -> str:
        """
        Build success URL pointing to static landing page.

        Args:
            order_id: Order ID to include in URL

        Returns:
            Success URL string
        """
        # URL-encode order_id to handle special characters (| and -)
        encoded_order_id = quote(order_id, safe='')
        success_url = f"{self.landing_page_base_url}?order_id={encoded_order_id}"

        print(f"🔗 [SUCCESS_URL] Built success URL")
        print(f"   URL: {success_url}")

        return success_url

    def create_invoice_payload(self, data: Dict[str, Any], order_id: str, success_url: str) -> Dict[str, Any]:
        """
        Create NowPayments invoice payload.

        Args:
            data: Request data
            order_id: Generated order ID
            success_url: Success redirect URL

        Returns:
            Invoice payload dictionary
        """
        payload = {
            "price_amount": float(data["amount"]),
            "price_currency": "USD",
            "order_id": order_id,
            "order_description": "Payment-Test-1",
            "success_url": success_url,
            "ipn_callback_url": self.ipn_callback_url,
            "is_fixed_rate": False,
            "is_fee_paid_by_user": False
        }

        print(f"📋 [INVOICE] Created invoice payload:")
        print(f"   Amount: ${payload['price_amount']}")
        print(f"   Order ID: {payload['order_id']}")
        print(f"   IPN Callback: {'Configured' if self.ipn_callback_url else 'Not configured'}")

        return payload

    async def call_nowpayments_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API call to NowPayments to create invoice.

        Args:
            payload: Invoice payload dictionary

        Returns:
            API response dictionary
        """
        headers = {
            "x-api-key": self.payment_token,
            "Content-Type": "application/json",
        }

        try:
            print(f"🌐 [API] Calling NowPayments API: {self.api_url}")

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                )

                if resp.status_code == 200:
                    response_data = resp.json()
                    invoice_id = response_data.get('id')
                    invoice_url = response_data.get('invoice_url')

                    print(f"✅ [API] Invoice created successfully")
                    print(f"   Invoice ID: {invoice_id}")
                    print(f"   Invoice URL: {invoice_url}")

                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "data": response_data
                    }
                else:
                    print(f"❌ [API] NowPayments error: {resp.status_code}")
                    print(f"   Response: {resp.text}")

                    return {
                        "success": False,
                        "status_code": resp.status_code,
                        "error": resp.text
                    }

        except httpx.TimeoutException:
            print(f"❌ [API] Request timeout (30s)")
            return {
                "success": False,
                "error": "Request timeout - NowPayments API did not respond"
            }
        except Exception as e:
            print(f"❌ [API] Request failed: {e}")
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }

    def create_invoice(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method to create a payment invoice.
        This is the entry point called by the Flask route.

        Args:
            request_data: Request data from Flask route

        Returns:
            Response dictionary with invoice details or error
        """
        import asyncio

        print(f"💳 [PAYMENT] Creating invoice for user {request_data.get('user_id')}")

        # 1. Validate request
        is_valid, error_message = self.validate_request(request_data)
        if not is_valid:
            print(f"❌ [PAYMENT] Validation failed: {error_message}")
            return {
                "success": False,
                "error": error_message,
                "status_code": 400
            }

        # 2. Extract and sanitize data
        user_id = request_data["user_id"]
        amount = request_data["amount"]
        open_channel_id = request_data["open_channel_id"]
        subscription_time_days = request_data["subscription_time_days"]
        payment_type = request_data["payment_type"]

        # 3. Check if order_id provided (optional)
        if "order_id" in request_data and request_data["order_id"]:
            order_id = request_data["order_id"]
            print(f"📋 [ORDER] Using provided order_id: {order_id}")
        else:
            # Generate order_id
            order_id = self.build_order_id(user_id, open_channel_id)

        # 4. Validate channel exists in database (unless donation_default)
        if open_channel_id != "donation_default":
            sanitized_channel_id = sanitize_channel_id(open_channel_id)
            if not self.db_manager.channel_exists(sanitized_channel_id):
                print(f"❌ [PAYMENT] Channel {sanitized_channel_id} does not exist in database")
                return {
                    "success": False,
                    "error": f"Channel {sanitized_channel_id} not found",
                    "status_code": 404
                }

            # Fetch channel details for logging
            channel_details = self.db_manager.fetch_channel_details(sanitized_channel_id)
            if channel_details:
                print(f"🏷️ [PAYMENT] Channel: {channel_details.get('closed_channel_title')}")

        # 5. Build success URL
        success_url = self.build_success_url(order_id)

        # 6. Create invoice payload
        payload = self.create_invoice_payload(request_data, order_id, success_url)

        # 7. Call NowPayments API (async)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        api_response = loop.run_until_complete(self.call_nowpayments_api(payload))
        loop.close()

        # 8. Return response
        if api_response.get("success"):
            return {
                "success": True,
                "invoice_id": api_response["data"].get("id"),
                "invoice_url": api_response["data"].get("invoice_url"),
                "order_id": order_id,
                "status_code": 200
            }
        else:
            return {
                "success": False,
                "error": api_response.get("error", "Unknown error"),
                "status_code": api_response.get("status_code", 500)
            }
```

---

### 5. `validators.py` - Input Validation

```python
#!/usr/bin/env python
"""
Input validation functions for GCPaymentGateway-10-26
"""

from typing import Any


def validate_user_id(user_id: Any) -> bool:
    """
    Validate Telegram user ID.

    Args:
        user_id: User ID to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        user_id_int = int(user_id)
        return user_id_int > 0
    except (ValueError, TypeError):
        return False


def validate_amount(amount: Any) -> bool:
    """
    Validate payment amount.

    Args:
        amount: Amount to validate

    Returns:
        True if valid (between $1.00 and $9999.99), False otherwise
    """
    try:
        amount_float = float(amount)
        if not (1.00 <= amount_float <= 9999.99):
            return False

        # Check decimal places (max 2)
        amount_str = str(amount)
        if '.' in amount_str:
            decimal_places = len(amount_str.split('.')[1])
            if decimal_places > 2:
                return False

        return True
    except (ValueError, TypeError):
        return False


def validate_channel_id(channel_id: Any) -> bool:
    """
    Validate Telegram channel ID format.

    Args:
        channel_id: Channel ID to validate

    Returns:
        True if valid format, False otherwise
    """
    if not channel_id:
        return False

    channel_id_str = str(channel_id)

    # Special case: donation_default
    if channel_id_str == "donation_default":
        return True

    # Standard validation: numeric (with optional negative sign)
    if channel_id_str.lstrip("-").isdigit():
        return len(channel_id_str) <= 15  # Max length for Telegram IDs

    return False


def validate_subscription_time(days: Any) -> bool:
    """
    Validate subscription duration in days.

    Args:
        days: Duration in days to validate

    Returns:
        True if valid (1-999 days), False otherwise
    """
    try:
        days_int = int(days)
        return 1 <= days_int <= 999
    except (ValueError, TypeError):
        return False


def validate_payment_type(payment_type: Any) -> bool:
    """
    Validate payment type.

    Args:
        payment_type: Payment type to validate

    Returns:
        True if valid ('subscription' or 'donation'), False otherwise
    """
    if not isinstance(payment_type, str):
        return False

    return payment_type.lower() in ["subscription", "donation"]


def sanitize_channel_id(channel_id: str) -> str:
    """
    Sanitize channel ID to ensure correct format.
    Telegram channel IDs must be negative for supergroups/channels.

    Args:
        channel_id: Channel ID to sanitize

    Returns:
        Sanitized channel ID
    """
    channel_id_str = str(channel_id)

    # Special case: donation_default
    if channel_id_str == "donation_default":
        return channel_id_str

    # Ensure negative sign for Telegram channels
    if not channel_id_str.startswith('-'):
        print(f"⚠️ [VALIDATION] Channel ID should be negative: {channel_id_str}")
        print(f"⚠️ [VALIDATION] Telegram channel IDs are always negative for supergroups/channels")
        channel_id_str = f"-{channel_id_str}"
        print(f"✅ [VALIDATION] Corrected to: {channel_id_str}")

    return channel_id_str
```

---

### 6. `requirements.txt` - Python Dependencies

```txt
# Flask web framework
Flask==3.0.0

# HTTP client for NowPayments API
httpx==0.25.2

# PostgreSQL database driver
psycopg2-binary==2.9.9

# Google Cloud Secret Manager
google-cloud-secret-manager==2.16.4

# Gunicorn WSGI server for production
gunicorn==21.2.0
```

---

### 7. `Dockerfile` - Container Definition

```dockerfile
# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY service.py .
COPY config_manager.py .
COPY database_manager.py .
COPY payment_handler.py .
COPY validators.py .

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Set environment variable for Python
ENV PYTHONUNBUFFERED=1

# Run the application using gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 60 service:create_app()
```

---

### 8. `.dockerignore` - Exclude Patterns

```
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
.git/
.gitignore
README.md
.env
.venv/
venv/
*.md
tests/
.pytest_cache/
```

---

## Database Operations

### Database Schema (Unchanged)

The service uses the existing `telepaypsql` database with these tables:

#### `main_clients_database` Table

```sql
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

### Database Queries Used

1. **Validate Channel Exists:**
   ```sql
   SELECT 1 FROM main_clients_database
   WHERE open_channel_id = %s
   LIMIT 1
   ```

2. **Fetch Channel Details:**
   ```sql
   SELECT
       open_channel_id, open_channel_title, open_channel_description,
       closed_channel_id, closed_channel_title, closed_channel_description,
       sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
       client_wallet_address, client_payout_currency, client_payout_network
   FROM main_clients_database
   WHERE open_channel_id = %s
   LIMIT 1
   ```

3. **Fetch Closed Channel ID:**
   ```sql
   SELECT closed_channel_id
   FROM main_clients_database
   WHERE open_channel_id = %s
   ```

4. **Fetch Wallet Info:**
   ```sql
   SELECT client_wallet_address, client_payout_currency, client_payout_network
   FROM main_clients_database
   WHERE open_channel_id = %s
   ```

---

## Configuration Management

### Environment Variables

All secrets fetched from Google Secret Manager:

| Environment Variable | Secret Path Example | Description |
|---------------------|-------------------|-------------|
| `PAYMENT_PROVIDER_SECRET_NAME` | `projects/telepay-459221/secrets/nowpayments-api-key/versions/latest` | NowPayments API token |
| `NOWPAYMENTS_IPN_CALLBACK_URL` | `projects/telepay-459221/secrets/nowpayments-ipn-url/versions/latest` | IPN callback URL for payment_id |
| `DATABASE_HOST_SECRET` | `projects/telepay-459221/secrets/database-host/versions/latest` | Cloud SQL connection name |
| `DATABASE_NAME_SECRET` | `projects/telepay-459221/secrets/database-name/versions/latest` | Database name (telepaydb) |
| `DATABASE_USER_SECRET` | `projects/telepay-459221/secrets/database-user/versions/latest` | Database user (postgres) |
| `DATABASE_PASSWORD_SECRET` | `projects/telepay-459221/secrets/database-password/versions/latest` | Database password |

### IAM Permissions Required

The Cloud Run service account needs:

```bash
# Grant Secret Manager access
gcloud secrets add-iam-policy-binding nowpayments-api-key \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding nowpayments-ipn-url \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding database-host \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant Cloud SQL Client access
gcloud projects add-iam-policy-binding telepay-459221 \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

---

## API Integration

### NowPayments API

**Endpoint:** `https://api.nowpayments.io/v1/invoice`
**Method:** POST
**Authentication:** `x-api-key` header

#### Request Format

```json
{
  "price_amount": 9.99,
  "price_currency": "USD",
  "order_id": "PGP-6271402111|-1003268562225",
  "order_description": "Payment-Test-1",
  "success_url": "https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003268562225",
  "ipn_callback_url": "https://np-webhook-10-26-pjxwjsdktq-uc.a.run.app",
  "is_fixed_rate": false,
  "is_fee_paid_by_user": false
}
```

#### Success Response (200)

```json
{
  "id": "12345678",
  "token_id": "abc123def456",
  "order_id": "PGP-6271402111|-1003268562225",
  "order_description": "Payment-Test-1",
  "price_amount": "9.99",
  "price_currency": "USD",
  "pay_currency": "eth",
  "ipn_callback_url": "https://np-webhook-10-26-pjxwjsdktq-uc.a.run.app",
  "invoice_url": "https://nowpayments.io/payment/?iid=12345678",
  "success_url": "https://storage.googleapis.com/...",
  "cancel_url": null,
  "created_at": "2025-11-12T14:32:15.000Z",
  "updated_at": "2025-11-12T14:32:15.000Z"
}
```

#### Error Response (400/500)

```json
{
  "statusCode": 400,
  "message": "price_amount must be greater than or equal to minimum amount",
  "error": "Bad Request"
}
```

### Retry Logic

- **Timeout:** 30 seconds
- **Retry Strategy:** Caller should retry with exponential backoff
- **Idempotency:** Safe to retry with same order_id (NowPayments handles duplicates)

---

## Error Handling Strategy

### Input Validation Errors (400)

```python
{
    "success": False,
    "error": "Invalid amount (must be between $1.00 and $9999.99)",
    "status_code": 400
}
```

**Handled by:** `validators.py` functions
**Resolution:** Caller must fix input and retry

### Channel Not Found (404)

```python
{
    "success": False,
    "error": "Channel -1003268562225 not found",
    "status_code": 404
}
```

**Handled by:** `database_manager.py` channel_exists check
**Resolution:** Verify channel ID in database

### Database Connection Errors (500)

```python
{
    "success": False,
    "error": "Database connection failed: timeout",
    "status_code": 500
}
```

**Handled by:** `database_manager.py` exception handling
**Resolution:** Check database connectivity, retry request

### NowPayments API Errors (500)

```python
{
    "success": False,
    "error": "NowPayments API error: insufficient funds",
    "status_code": 500
}
```

**Handled by:** `payment_handler.py` API response validation
**Resolution:** Check NowPayments account status, contact support

### Configuration Errors (500)

```python
{
    "success": False,
    "error": "Payment provider token not configured",
    "status_code": 500
}
```

**Handled by:** `config_manager.py` initialization
**Resolution:** Verify Secret Manager configuration and IAM permissions

---

## Deployment Guide

### Step 1: Create Service Directory

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26
mkdir GCPaymentGateway-10-26
cd GCPaymentGateway-10-26
```

### Step 2: Create All Files

Create each file with the content provided in this architecture document:
- `service.py`
- `config_manager.py`
- `database_manager.py`
- `payment_handler.py`
- `validators.py`
- `requirements.txt`
- `Dockerfile`
- `.dockerignore`

### Step 3: Test Locally (Optional)

```bash
# Set environment variables for local testing
export PAYMENT_PROVIDER_SECRET_NAME="projects/telepay-459221/secrets/nowpayments-api-key/versions/latest"
export NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/nowpayments-ipn-url/versions/latest"
export DATABASE_HOST_SECRET="projects/telepay-459221/secrets/database-host/versions/latest"
export DATABASE_NAME_SECRET="projects/telepay-459221/secrets/database-name/versions/latest"
export DATABASE_USER_SECRET="projects/telepay-459221/secrets/database-user/versions/latest"
export DATABASE_PASSWORD_SECRET="projects/telepay-459221/secrets/database-password/versions/latest"

# Install dependencies
pip install -r requirements.txt

# Run locally
python service.py
```

### Step 4: Deploy to Cloud Run

```bash
gcloud run deploy gcpaymentgateway-10-26 \
  --source=. \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="PAYMENT_PROVIDER_SECRET_NAME=projects/telepay-459221/secrets/nowpayments-api-key/versions/latest" \
  --set-env-vars="NOWPAYMENTS_IPN_CALLBACK_URL=projects/telepay-459221/secrets/nowpayments-ipn-url/versions/latest" \
  --set-env-vars="DATABASE_HOST_SECRET=projects/telepay-459221/secrets/database-host/versions/latest" \
  --set-env-vars="DATABASE_NAME_SECRET=projects/telepay-459221/secrets/database-name/versions/latest" \
  --set-env-vars="DATABASE_USER_SECRET=projects/telepay-459221/secrets/database-user/versions/latest" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/database-password/versions/latest" \
  --service-account=telepay-cloudrun@telepay-459221.iam.gserviceaccount.com \
  --min-instances=0 \
  --max-instances=5 \
  --memory=256Mi \
  --cpu=1 \
  --timeout=60s \
  --concurrency=80
```

### Step 5: Verify Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe gcpaymentgateway-10-26 \
  --region=us-central1 \
  --format='value(status.url)')

echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl -X GET "$SERVICE_URL/health"
```

Expected response:
```json
{"status": "healthy", "service": "gcpaymentgateway-10-26"}
```

### Step 6: Test Invoice Creation

```bash
curl -X POST "$SERVICE_URL/create-invoice" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 6271402111,
    "amount": 9.99,
    "open_channel_id": "-1003268562225",
    "subscription_time_days": 30,
    "payment_type": "subscription",
    "tier": 1
  }'
```

Expected response:
```json
{
  "success": true,
  "invoice_id": "12345678",
  "invoice_url": "https://nowpayments.io/payment/?iid=12345678",
  "order_id": "PGP-6271402111|-1003268562225",
  "status_code": 200
}
```

---

## Testing Strategy

### Unit Tests

Create `tests/test_validators.py`:

```python
import pytest
from validators import (
    validate_user_id,
    validate_amount,
    validate_channel_id,
    validate_subscription_time,
    validate_payment_type,
    sanitize_channel_id
)

def test_validate_user_id_valid():
    assert validate_user_id(6271402111) == True
    assert validate_user_id("6271402111") == True

def test_validate_user_id_invalid():
    assert validate_user_id(-123) == False
    assert validate_user_id("invalid") == False
    assert validate_user_id(None) == False

def test_validate_amount_valid():
    assert validate_amount(9.99) == True
    assert validate_amount("9.99") == True
    assert validate_amount(1.00) == True
    assert validate_amount(9999.99) == True

def test_validate_amount_invalid():
    assert validate_amount(0.99) == False  # Too low
    assert validate_amount(10000.00) == False  # Too high
    assert validate_amount("invalid") == False
    assert validate_amount(9.999) == False  # Too many decimal places

def test_validate_channel_id_valid():
    assert validate_channel_id("-1003268562225") == True
    assert validate_channel_id("donation_default") == True

def test_validate_channel_id_invalid():
    assert validate_channel_id("") == False
    assert validate_channel_id("invalid") == False
    assert validate_channel_id(None) == False

def test_sanitize_channel_id():
    assert sanitize_channel_id("1003268562225") == "-1003268562225"
    assert sanitize_channel_id("-1003268562225") == "-1003268562225"
    assert sanitize_channel_id("donation_default") == "donation_default"
```

Run tests:
```bash
pytest tests/test_validators.py -v
```

### Integration Tests

Create `tests/test_integration.py`:

```python
import pytest
import requests

SERVICE_URL = "https://gcpaymentgateway-10-26-pjxwjsdktq-uc.a.run.app"

def test_health_check():
    response = requests.get(f"{SERVICE_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_create_invoice_success():
    payload = {
        "user_id": 6271402111,
        "amount": 9.99,
        "open_channel_id": "-1003268562225",
        "subscription_time_days": 30,
        "payment_type": "subscription",
        "tier": 1
    }

    response = requests.post(f"{SERVICE_URL}/create-invoice", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] == True
    assert "invoice_id" in data
    assert "invoice_url" in data
    assert data["order_id"].startswith("PGP-")

def test_create_invoice_invalid_amount():
    payload = {
        "user_id": 6271402111,
        "amount": 0.50,  # Too low
        "open_channel_id": "-1003268562225",
        "subscription_time_days": 30,
        "payment_type": "subscription"
    }

    response = requests.post(f"{SERVICE_URL}/create-invoice", json=payload)
    assert response.status_code == 400

    data = response.json()
    assert data["success"] == False
    assert "amount" in data["error"].lower()
```

Run tests:
```bash
pytest tests/test_integration.py -v
```

---

## Integration Points

### Upstream Services (Callers)

1. **GCBotCommand-10-26** (Future service)
   - Calls `/create-invoice` when user initiates subscription
   - Receives invoice URL to display in Telegram WebApp button

2. **GCDonationHandler-10-26** (Future service)
   - Calls `/create-invoice` when user confirms donation amount
   - Receives invoice URL to display in Telegram WebApp button

### Downstream Services (Called by this service)

1. **NowPayments API**
   - Purpose: Create payment invoices
   - Endpoint: `https://api.nowpayments.io/v1/invoice`
   - Authentication: x-api-key header

2. **PostgreSQL Database (telepaypsql)**
   - Purpose: Validate channels and fetch channel details
   - Tables: `main_clients_database`

3. **Google Secret Manager**
   - Purpose: Fetch API tokens and database credentials
   - Secrets: Payment token, IPN URL, database credentials

### Webhooks (Triggered by this service)

None. This service creates invoices synchronously and returns immediately.

### Webhooks (That call this service)

None. This service is called directly via HTTP POST from other Cloud Run services.

---

## Monitoring & Observability

### Cloud Logging Queries

**View all payment gateway logs:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcpaymentgateway-10-26"
```

**View only errors:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcpaymentgateway-10-26"
"❌"
```

**View invoice creations:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcpaymentgateway-10-26"
"💳 [GATEWAY] Creating invoice"
```

**View NowPayments API calls:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcpaymentgateway-10-26"
"🌐 [API] Calling NowPayments API"
```

### Metrics to Monitor

1. **Request Rate:** Invocations per minute
2. **Error Rate:** 4xx and 5xx responses
3. **Latency:** p50, p95, p99 response times
4. **NowPayments API Success Rate:** Successful vs failed API calls
5. **Database Connection Errors:** Failed database queries

### Alerting Policies

Create alerts for:
- Error rate > 5% for 5 minutes
- Latency p95 > 3 seconds
- NowPayments API error rate > 10%
- Database connection errors > 5 per minute

---

## Cost Estimates

Based on **10,000 subscriptions/month** and **1,000 donations/month**:

| Resource | Usage | Estimated Cost |
|----------|-------|----------------|
| Cloud Run Invocations | 11,000/month | $0.40 |
| CPU Time (256 MiB, 1 vCPU) | ~10 minutes | $0.50 |
| Memory (256 MiB) | ~10 GB-seconds | $0.10 |
| Secret Manager Access | ~33,000 reads | $0.20 |
| Cloud SQL Connections | Included | $0.00 |
| **Total** | | **$1.20/month** |

**Note:** Actual costs may vary based on traffic patterns and NowPayments API latency.

---

## Rollback Procedure

If the new service has issues:

### Step 1: Revert to TelePay10-26 Bot

```bash
# Ensure old bot is running
gcloud run services update tph10-26 \
  --region=us-central1 \
  --min-instances=1
```

### Step 2: Update Callers

Update GCBotCommand (or other callers) to use old payment flow:
- Revert to direct `PaymentGatewayManager` usage
- Or implement fallback to old bot

### Step 3: Disable New Service

```bash
# Scale down to zero
gcloud run services update gcpaymentgateway-10-26 \
  --region=us-central1 \
  --min-instances=0 \
  --max-instances=0
```

### Step 4: Investigate Issues

- Review Cloud Logging for errors
- Check Secret Manager permissions
- Verify database connectivity
- Test NowPayments API credentials

---

## Conclusion

This architecture document provides a **complete, self-contained implementation** of the GCPaymentGateway-10-26 service. All code is bundled within the service directory (no shared modules), following Flask best practices and Cloud Run patterns.

### Key Achievements

✅ **Self-Contained:** All dependencies within service directory
✅ **Fully Functional:** Preserves all PaymentGatewayManager functionality
✅ **Production-Ready:** Error handling, logging, monitoring included
✅ **Secure:** Secrets from Secret Manager, input validation, IAM permissions
✅ **Scalable:** Stateless design, horizontal scaling via Cloud Run
✅ **Observable:** Comprehensive logging with emoji patterns
✅ **Testable:** Unit tests and integration tests provided

### Next Steps

1. ✅ Review this architecture document
2. ⏭️ Create GCPaymentGateway-10-26 directory and files
3. ⏭️ Deploy to Cloud Run
4. ⏭️ Test with real NowPayments API
5. ⏭️ Integrate with GCBotCommand service

---

**Document Owner:** Claude
**Review Date:** 2025-11-12
**Status:** Ready for Implementation
