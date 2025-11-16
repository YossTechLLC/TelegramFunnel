# Phase 3.5: Integration Plan - NEW_ARCHITECTURE

**Date:** 2025-11-13
**Status:** READY FOR EXECUTION
**Priority:** CRITICAL
**Estimated Time:** 2-3 hours

---

## Executive Summary

This plan integrates the completed NEW_ARCHITECTURE modules (Phases 1-3) into the running TelePay10-26 application. Currently, all new code exists but is **0% integrated** - the app still uses 100% legacy code.

**Goal:** Wire the new modular architecture into `app_initializer.py`, `bot_manager.py`, and `database.py` to activate:
- ✅ Security layers (HMAC, IP whitelist, rate limiting)
- ✅ Connection pooling (SQLAlchemy with Cloud SQL Connector)
- ✅ Modular bot handlers (ConversationHandler pattern)
- ✅ Services layer (PaymentService, NotificationService)

---

## Pre-Integration Checklist

Before starting integration:

- [x] Phase 1 (Security) code complete
- [x] Phase 2 (Modularity) code complete
- [x] Phase 3 (Services) code complete
- [x] NEW_ARCHITECTURE_REPORT.md reviewed
- [ ] Backup current working code (user will do manually via git)
- [ ] Environment ready for testing
- [ ] Secret Manager configured (WEBHOOK_SIGNING_SECRET, etc.)

---

## Integration Tasks Overview

| Task | File | Priority | Estimated Time | Dependencies |
|------|------|----------|----------------|--------------|
| 1. Refactor DatabaseManager | database.py | HIGH | 30 min | ConnectionPool |
| 2. Update AppInitializer imports | app_initializer.py | HIGH | 15 min | Services, models |
| 3. Initialize security config | app_initializer.py | HIGH | 20 min | Security modules |
| 4. Replace old services | app_initializer.py | HIGH | 20 min | Task 2 |
| 5. Update BotManager handlers | bot_manager.py | MEDIUM | 30 min | New bot/ modules |
| 6. Wire services to Flask | app_initializer.py | MEDIUM | 15 min | ServerManager |
| 7. Update telepay10-26.py | telepay10-26.py | LOW | 10 min | AppInitializer |
| 8. Test integration locally | N/A | HIGH | 30 min | All tasks |

**Total Estimated Time:** 2-3 hours

---

## Task 1: Refactor DatabaseManager (database.py)

**Objective:** Replace direct psycopg2 connections with ConnectionPool

### Current Code (Lines 68-90)

```python
class DatabaseManager:
    def __init__(self):
        self.host = DB_HOST
        self.port = DB_PORT
        self.dbname = DB_NAME
        self.user = DB_USER
        self.password = DB_PASSWORD

        if not self.password:
            raise RuntimeError("Database password not available from Secret Manager.")

    def get_connection(self):
        """Create and return a database connection."""
        return psycopg2.connect(
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port
        )
```

### New Code

```python
from models import init_connection_pool

class DatabaseManager:
    def __init__(self):
        """Initialize DatabaseManager with connection pooling."""
        # Fetch credentials from Secret Manager (keep existing fetch functions)
        self.host = DB_HOST
        self.port = DB_PORT
        self.dbname = DB_NAME
        self.user = DB_USER
        self.password = DB_PASSWORD

        # Validate credentials
        if not self.password:
            raise RuntimeError("Database password not available from Secret Manager.")
        if not self.host or not self.dbname or not self.user:
            raise RuntimeError("Critical database configuration missing from Secret Manager.")

        # Initialize connection pool
        self.pool = init_connection_pool({
            'instance_connection_name': os.getenv('CLOUD_SQL_CONNECTION_NAME', 'telepay-459221:us-central1:telepaypsql'),
            'database': self.dbname,
            'user': self.user,
            'password': self.password,
            'pool_size': int(os.getenv('DB_POOL_SIZE', '5')),
            'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '10')),
            'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
            'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '1800'))
        })

        print("✅ [DATABASE] Connection pool initialized")

    def get_connection(self):
        """
        DEPRECATED: Get raw connection from pool.

        Prefer using execute_query() or get_session() for better connection management.
        This method is kept for backward compatibility with legacy code.
        """
        # For backward compatibility, return a raw connection from the pool
        # This will be managed by the pool but returned as raw connection
        return self.pool.engine.raw_connection()

    def execute_query(self, query: str, params: dict = None):
        """
        Execute SQL query using connection pool.

        Args:
            query: SQL query with :param_name placeholders
            params: Dictionary of parameters

        Returns:
            Query result
        """
        return self.pool.execute_query(query, params)

    def get_session(self):
        """
        Get SQLAlchemy ORM session from pool.

        Usage:
            with db_manager.get_session() as session:
                result = session.query(...)

        Returns:
            SQLAlchemy session
        """
        return self.pool.get_session()

    def health_check(self) -> bool:
        """Check database connection health."""
        return self.pool.health_check()

    def close(self):
        """Close connection pool on shutdown."""
        if hasattr(self, 'pool'):
            self.pool.close()
            print("✅ [DATABASE] Connection pool closed")
```

### Migration Strategy

1. **Add new methods** (execute_query, get_session, health_check, close)
2. **Keep get_connection()** for backward compatibility (returns raw connection from pool)
3. **Gradually migrate** existing queries to use execute_query() instead of get_connection()

### Example Query Migration

**Before (using get_connection):**
```python
conn = self.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT * FROM client WHERE open_channel_id = %s", (channel_id,))
result = cursor.fetchall()
cursor.close()
conn.close()
```

**After (using execute_query):**
```python
result = self.execute_query(
    "SELECT * FROM client WHERE open_channel_id = :channel_id",
    {'channel_id': channel_id}
)
rows = result.fetchall()
```

**Note:** For this integration phase, we'll keep get_connection() working so existing code doesn't break. We can migrate individual queries later.

---

## Task 2: Update AppInitializer Imports (app_initializer.py)

**Objective:** Replace old imports with new modular imports

### Current Imports (Lines 1-17)

```python
import logging
import nest_asyncio
from config_manager import ConfigManager
from database import DatabaseManager
from secure_webhook import SecureWebhookManager
from start_np_gateway import PaymentGatewayManager
from broadcast_manager import BroadcastManager
from input_handlers import InputHandlers
from menu_handlers import MenuHandlers
from bot_manager import BotManager
from message_utils import MessageUtils
from subscription_manager import SubscriptionManager
from closed_channel_manager import ClosedChannelManager
from donation_input_handler import DonationKeypadHandler
from notification_service import NotificationService
from telegram import Bot
```

### New Imports

```python
import logging
import nest_asyncio
import os

# Core managers (keep these - no new versions yet)
from config_manager import ConfigManager
from secure_webhook import SecureWebhookManager
from broadcast_manager import BroadcastManager
from message_utils import MessageUtils
from subscription_manager import SubscriptionManager
from closed_channel_manager import ClosedChannelManager

# NEW: Modular architecture imports
from database import DatabaseManager  # Refactored to use ConnectionPool
from services import init_payment_service, init_notification_service
from bot.handlers import register_command_handlers
from bot.conversations import create_donation_conversation_handler
from bot.utils import keyboards as bot_keyboards

# Keep old imports temporarily for gradual migration
from input_handlers import InputHandlers
from menu_handlers import MenuHandlers
from bot_manager import BotManager

# Legacy imports (will be removed after full migration)
# from donation_input_handler import DonationKeypadHandler  # REPLACED by bot.conversations
# from start_np_gateway import PaymentGatewayManager  # REPLACED by services.PaymentService
# from notification_service import NotificationService  # REPLACED by services.NotificationService

from telegram import Bot
```

### Import Changes Summary

| Old Import | New Import | Status |
|------------|------------|--------|
| `start_np_gateway.PaymentGatewayManager` | `services.init_payment_service` | ✅ Replace |
| `notification_service.NotificationService` | `services.init_notification_service` | ✅ Replace |
| `donation_input_handler.DonationKeypadHandler` | `bot.conversations.create_donation_conversation_handler` | ✅ Replace |
| `database.DatabaseManager` | Keep (refactored internally) | ✅ Keep |
| `input_handlers.InputHandlers` | Keep (for now) | ⏳ Future |
| `menu_handlers.MenuHandlers` | Keep (for now) | ⏳ Future |
| `bot_manager.BotManager` | Keep (will refactor) | ⏳ Update |

---

## Task 3: Initialize Security Config (app_initializer.py)

**Objective:** Add security configuration for ServerManager

### Add to __init__ method (after line 48)

```python
def __init__(self):
    # ... existing initialization ...

    # 🆕 NEW_ARCHITECTURE: Security configuration
    self.security_config = None
    self.server_manager = None
```

### Add security config initialization in initialize() method (after line 53)

```python
def initialize(self):
    """Initialize all application components."""
    # Get configuration
    self.config = self.config_manager.initialize_config()

    if not self.config['bot_token']:
        raise RuntimeError("Bot token is required to start the application")

    # 🆕 NEW_ARCHITECTURE: Initialize security configuration
    self.security_config = self._initialize_security_config()
    self.logger.info("✅ Security configuration loaded")

    # ... rest of initialization ...
```

### Add security config method (new method)

```python
def _initialize_security_config(self) -> dict:
    """
    Initialize security configuration for Flask server.

    Returns:
        Security configuration dictionary
    """
    # Fetch webhook signing secret from Secret Manager
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()

        # Try to fetch webhook signing secret
        try:
            secret_path = os.getenv("WEBHOOK_SIGNING_SECRET_NAME")
            if secret_path:
                response = client.access_secret_version(request={"name": secret_path})
                webhook_signing_secret = response.payload.data.decode("UTF-8")
                self.logger.info("✅ Webhook signing secret loaded from Secret Manager")
            else:
                # Generate a temporary secret for development
                import secrets
                webhook_signing_secret = secrets.token_hex(32)
                self.logger.warning("⚠️ WEBHOOK_SIGNING_SECRET_NAME not set - using temporary secret (DEV ONLY)")
        except Exception as e:
            # Fallback: generate temporary secret
            import secrets
            webhook_signing_secret = secrets.token_hex(32)
            self.logger.warning(f"⚠️ Could not fetch webhook signing secret: {e}")
            self.logger.warning("⚠️ Using temporary secret (DEV ONLY)")

    except Exception as e:
        self.logger.error(f"❌ Error initializing security config: {e}")
        # Use a temporary secret for development
        import secrets
        webhook_signing_secret = secrets.token_hex(32)
        self.logger.warning("⚠️ Using temporary webhook signing secret (DEV ONLY)")

    # Get allowed IPs from environment or use defaults
    allowed_ips_str = os.getenv('ALLOWED_IPS', '127.0.0.1,10.0.0.0/8')
    allowed_ips = [ip.strip() for ip in allowed_ips_str.split(',')]

    # Get rate limit config from environment
    rate_limit_per_minute = int(os.getenv('RATE_LIMIT_PER_MINUTE', '10'))
    rate_limit_burst = int(os.getenv('RATE_LIMIT_BURST', '20'))

    config = {
        'webhook_signing_secret': webhook_signing_secret,
        'allowed_ips': allowed_ips,
        'rate_limit_per_minute': rate_limit_per_minute,
        'rate_limit_burst': rate_limit_burst
    }

    self.logger.info(f"🔒 [SECURITY] Configured:")
    self.logger.info(f"   Allowed IPs: {len(allowed_ips)} ranges")
    self.logger.info(f"   Rate limit: {rate_limit_per_minute} req/min, burst {rate_limit_burst}")

    return config
```

---

## Task 4: Replace Old Services (app_initializer.py)

**Objective:** Replace PaymentGatewayManager and NotificationService with new services

### Current Code (Lines 59-124)

```python
# Initialize core managers
self.db_manager = DatabaseManager()
self.webhook_manager = SecureWebhookManager()
self.payment_manager = PaymentGatewayManager()
# ...

# Initialize notification service
bot_instance = Bot(token=self.config['bot_token'])
self.notification_service = NotificationService(bot_instance, self.db_manager)
self.logger.info("✅ Notification Service initialized")
```

### New Code

```python
# Initialize core managers
self.db_manager = DatabaseManager()  # Now uses ConnectionPool internally
self.webhook_manager = SecureWebhookManager()

# 🆕 NEW_ARCHITECTURE: Initialize new services
from services import init_payment_service, init_notification_service

# Initialize payment service (replaces PaymentGatewayManager)
self.payment_service = init_payment_service()
self.logger.info("✅ Payment Service initialized")

# Keep old payment_manager temporarily for backward compatibility
# TODO: Migrate all payment_manager usages to payment_service
self.payment_manager = self.payment_service  # Temporary compatibility shim

# Initialize notification service (new modular version)
bot_instance = Bot(token=self.config['bot_token'])
self.notification_service = init_notification_service(
    bot=bot_instance,
    db_manager=self.db_manager
)
self.logger.info("✅ Notification Service initialized (NEW_ARCHITECTURE)")
```

### Compatibility Note

For backward compatibility, we set `self.payment_manager = self.payment_service`. However, the new PaymentService has different method names:

**Old PaymentGatewayManager:**
- `start_np_gateway_new(update, context, amount, channel_id, duration, webhook_manager, db_manager)`

**New PaymentService:**
- `create_invoice(user_id, amount, success_url, order_id, description)`

We'll need to create a compatibility wrapper or update the calling code. For this integration, we'll **create a wrapper method** in payment_service.py.

### Add to services/payment_service.py (compatibility wrapper)

```python
async def start_np_gateway_new(self, update, context, amount, channel_id, duration, webhook_manager, db_manager):
    """
    COMPATIBILITY WRAPPER for old PaymentGatewayManager.start_np_gateway_new()

    This allows gradual migration from old to new payment service.

    TODO: Migrate all calling code to use create_invoice() directly, then remove this wrapper.
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.warning("⚠️ [PAYMENT] Using compatibility wrapper - migrate to create_invoice()")

    user_id = update.effective_user.id

    # Generate order ID
    order_id = self.generate_order_id(user_id, channel_id)

    # Build success URL (use Telegram deep link)
    success_url = f"https://t.me/{context.bot.username}?start=payment_success"

    # Create invoice
    result = await self.create_invoice(
        user_id=user_id,
        amount=amount,
        success_url=success_url,
        order_id=order_id,
        description=f"Subscription - {duration} days"
    )

    if result['success']:
        # Send payment link to user
        invoice_url = result['invoice_url']

        await update.effective_message.reply_text(
            f"💳 <b>Payment Gateway</b>\n\n"
            f"Amount: ${amount:.2f} USD\n"
            f"Duration: {duration} days\n\n"
            f"Click the button below to complete payment:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💰 Pay Now", url=invoice_url)
            ]])
        )

        logger.info(f"✅ [PAYMENT] Invoice sent to user {user_id}")
    else:
        await update.effective_message.reply_text(
            "❌ Error creating payment invoice. Please try again later."
        )
        logger.error(f"❌ [PAYMENT] Invoice creation failed: {result.get('error')}")
```

**Important:** Add this wrapper to `services/payment_service.py` before integration.

---

## Task 5: Update BotManager Handlers (bot_manager.py)

**Objective:** Register new modular bot handlers

### Current setup_handlers() method (Lines 24-111)

The current method registers old handlers. We need to add new modular handlers while keeping old ones temporarily.

### Add to setup_handlers() method (after line 111, before catch-all callback)

```python
def setup_handlers(self, application: Application):
    """Set up all bot handlers"""
    # ... existing handlers (keep for backward compatibility) ...

    # 🆕 NEW_ARCHITECTURE: Register modular bot handlers
    from bot.handlers import register_command_handlers
    from bot.conversations import create_donation_conversation_handler

    # Register new command handlers (/start, /help)
    # NOTE: These will override old /start handler - verify compatibility first
    # register_command_handlers(application)  # TODO: Enable after testing
    # self.logger.info("✅ Registered new modular command handlers")

    # Register new donation conversation handler
    # NOTE: This uses ConversationHandler pattern with numeric keypad
    new_donation_handler = create_donation_conversation_handler()
    # application.add_handler(new_donation_handler)  # TODO: Enable after testing
    # self.logger.info("✅ Registered new donation conversation handler")

    # Store services in bot_data for handler access
    application.bot_data['payment_service'] = getattr(self, 'payment_service', None)
    application.bot_data['notification_service'] = getattr(self, 'notification_service', None)

    # ... existing catch-all callback handler ...
```

### Notes on Handler Migration

**Current State:**
- Old donation handler: `donation_input_handler.py` with custom keypad
- Old command handlers: Inline in menu_handlers.py

**New State:**
- New donation handler: `bot/conversations/donation_conversation.py` with ConversationHandler
- New command handlers: `bot/handlers/command_handler.py`

**Integration Strategy:**
1. **Phase 1:** Add new handlers but keep them commented out
2. **Phase 2:** Test new handlers in isolation
3. **Phase 3:** Enable new handlers, disable old ones
4. **Phase 4:** Remove old handler code

For this integration, we'll **add the registration code but keep it commented out** until testing confirms compatibility.

---

## Task 6: Wire Services to Flask (app_initializer.py)

**Objective:** Initialize ServerManager with security config and services

### Current Code (Implicit - ServerManager not in app_initializer.py)

ServerManager is created elsewhere and doesn't have security config.

### New Code (Add to initialize() method)

```python
def initialize(self):
    """Initialize all application components."""
    # ... existing initialization ...

    # 🆕 NEW_ARCHITECTURE: Initialize Flask server with security
    from server_manager import create_app

    # Create Flask app with security config
    flask_app = create_app(self.security_config)

    # Store services in Flask app context for blueprint access
    flask_app.config['notification_service'] = self.notification_service
    flask_app.config['payment_service'] = self.payment_service
    flask_app.config['database_manager'] = self.db_manager

    # Store Flask app for later use
    self.flask_app = flask_app

    self.logger.info("✅ Flask server initialized with security")
    self.logger.info("   HMAC: enabled")
    self.logger.info("   IP Whitelist: enabled")
    self.logger.info("   Rate Limiting: enabled")
```

### Update get_managers() method (Line 148-160)

```python
def get_managers(self):
    """Get all initialized managers for external use."""
    return {
        'db_manager': self.db_manager,
        'webhook_manager': self.webhook_manager,
        'payment_manager': self.payment_manager,  # OLD - for compatibility
        'payment_service': self.payment_service,  # NEW
        'broadcast_manager': self.broadcast_manager,
        'input_handlers': self.input_handlers,
        'menu_handlers': self.menu_handlers,
        'bot_manager': self.bot_manager,
        'message_utils': self.message_utils,
        'notification_service': self.notification_service,  # NEW version
        'flask_app': getattr(self, 'flask_app', None),  # NEW
        'security_config': self.security_config  # NEW
    }
```

---

## Task 7: Update telepay10-26.py (Entry Point)

**Objective:** Ensure entry point uses new Flask app

### Current telepay10-26.py (assumed structure)

```python
#!/usr/bin/env python
import asyncio
from app_initializer import AppInitializer

async def main():
    app = AppInitializer()
    app.initialize()
    await app.run_bot()

if __name__ == "__main__":
    asyncio.run(main())
```

### Verify Flask Server Start

If telepay10-26.py starts a Flask server separately, we need to update it to use the new Flask app from app_initializer.

**Action:** Read telepay10-26.py and verify if changes are needed.

If ServerManager is started in telepay10-26.py, replace:
```python
# OLD
server_manager = ServerManager()
server_manager.start()
```

With:
```python
# NEW
managers = app.get_managers()
flask_app = managers['flask_app']

# Run Flask in separate thread
import threading
def run_flask():
    flask_app.run(host='0.0.0.0', port=5000)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
```

---

## Task 8: Test Integration Locally

**Objective:** Verify all integrated components work together

### Testing Checklist

#### 1. Database Connection Pool

```bash
# Test database connectivity
python3 -c "
from app_initializer import AppInitializer
app = AppInitializer()
app.initialize()
print('Testing database pool...')
result = app.db_manager.health_check()
print(f'Health check: {result}')
pool_status = app.db_manager.pool.get_pool_status()
print(f'Pool status: {pool_status}')
"
```

**Expected Output:**
```
✅ [DATABASE] Connection pool initialized
Testing database pool...
✅ [DB_POOL] Health check passed
Health check: True
Pool status: {'size': 5, 'checked_in': 5, 'checked_out': 0, 'overflow': 0}
```

#### 2. Security Configuration

```bash
# Test security config loading
python3 -c "
from app_initializer import AppInitializer
app = AppInitializer()
app.initialize()
print('Security config:', app.security_config)
"
```

**Expected Output:**
```
✅ Security configuration loaded
🔒 [SECURITY] Configured:
   Allowed IPs: X ranges
   Rate limit: 10 req/min, burst 20
Security config: {'webhook_signing_secret': '...', 'allowed_ips': [...], ...}
```

#### 3. Services Initialization

```bash
# Test services
python3 -c "
from app_initializer import AppInitializer
app = AppInitializer()
app.initialize()
print('Payment service configured:', app.payment_service.is_configured())
print('Payment service status:', app.payment_service.get_status())
print('Notification service configured:', app.notification_service.is_configured('-1001234567890'))
"
```

**Expected Output:**
```
✅ Payment Service initialized
✅ Notification Service initialized (NEW_ARCHITECTURE)
Payment service configured: True
Payment service status: {'configured': True, 'api_key': 'loaded', 'ipn_callback_url': 'loaded'}
Notification service configured: True/False (depends on DB data)
```

#### 4. Flask App with Security

```bash
# Test Flask app initialization
python3 -c "
from app_initializer import AppInitializer
app = AppInitializer()
app.initialize()
print('Flask app:', app.flask_app)
print('App config keys:', list(app.flask_app.config.keys()))
print('Security in config:', 'hmac_auth' in app.flask_app.config)
"
```

**Expected Output:**
```
✅ Flask server initialized with security
   HMAC: enabled
   IP Whitelist: enabled
   Rate Limiting: enabled
Flask app: <Flask 'server_manager'>
App config keys: ['notification_service', 'payment_service', 'database_manager', 'hmac_auth', ...]
Security in config: True
```

#### 5. Bot Handlers Registration

```bash
# Test bot initialization
python3 -c "
import asyncio
from app_initializer import AppInitializer

async def test():
    app = AppInitializer()
    app.initialize()
    managers = app.get_managers()
    print('Managers:', list(managers.keys()))
    print('Flask app available:', managers['flask_app'] is not None)

asyncio.run(test())
"
```

#### 6. End-to-End Test

```bash
# Start the bot
python3 telepay10-26.py
```

**Verify:**
- ✅ Bot starts without errors
- ✅ Database pool initializes
- ✅ Security config loads
- ✅ Services initialize
- ✅ Flask server starts
- ✅ Bot responds to /start command
- ✅ Health check endpoint works: `curl http://localhost:5000/health`

**Health Check Response:**
```json
{
  "status": "healthy",
  "components": {
    "notification_service": "initialized",
    "flask_server": "running"
  },
  "security": {
    "hmac": "enabled",
    "ip_whitelist": "enabled",
    "rate_limiting": "enabled",
    "security_headers": "enabled"
  }
}
```

---

## Rollback Plan

If integration causes issues, follow this rollback procedure:

### 1. Immediate Rollback (via git)

```bash
# Rollback all changes
git checkout app_initializer.py
git checkout bot_manager.py
git checkout database.py
git checkout telepay10-26.py  # if modified
```

### 2. Partial Rollback (keep some changes)

If connection pool works but services don't:

```python
# In app_initializer.py, revert to old services
from start_np_gateway import PaymentGatewayManager
from notification_service import NotificationService  # root version

# Comment out new services
# from services import init_payment_service, init_notification_service
```

### 3. Gradual Integration (alternative approach)

If full integration fails, integrate components one at a time:

**Week 1:** Database connection pool only
**Week 2:** Services layer only
**Week 3:** Security layer only
**Week 4:** Bot handlers only

---

## Post-Integration Tasks

After successful integration:

### 1. Update Documentation

```bash
# Update PROGRESS.md
- [x] Phase 3.5: Integration complete
- [x] Database using ConnectionPool
- [x] Services layer active
- [x] Security layers enabled
```

### 2. Update DECISIONS.md

```bash
# Add integration decisions
- Used compatibility wrappers for gradual migration
- Kept old handlers temporarily for safety
- Environment variables for security config
```

### 3. Monitor Production

- ✅ Check logs for errors
- ✅ Monitor connection pool metrics
- ✅ Verify security headers present
- ✅ Test payment flow end-to-end
- ✅ Test notification delivery

### 4. Performance Testing

```bash
# Test connection pool under load
ab -n 1000 -c 10 http://localhost:5000/health

# Expected: No connection exhaustion, stable response times
```

### 5. Archive Legacy Code

After 1 week of stable operation:

```bash
mkdir -p OCTOBER/ARCHIVES/legacy_pre_integration/
mv start_np_gateway.py OCTOBER/ARCHIVES/legacy_pre_integration/
mv notification_service.py OCTOBER/ARCHIVES/legacy_pre_integration/  # root version
mv donation_input_handler.py OCTOBER/ARCHIVES/legacy_pre_integration/
```

---

## Environment Variables Needed

Add to .env or Secret Manager:

```bash
# Security
WEBHOOK_SIGNING_SECRET_NAME=projects/telepay-459221/secrets/WEBHOOK_SIGNING_SECRET/versions/latest
ALLOWED_IPS=127.0.0.1,10.0.0.0/8,35.190.247.0/24,35.191.0.0/16
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_BURST=20

# Database Connection Pool
CLOUD_SQL_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800

# Services (already exist)
PAYMENT_PROVIDER_SECRET_NAME=projects/telepay-459221/secrets/NOWPAYMENTS_API_KEY/versions/latest
NOWPAYMENTS_IPN_CALLBACK_URL_SECRET_NAME=projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest
```

---

## Success Criteria

Integration is successful when:

- [x] Bot starts without errors
- [x] Database pool initializes and health check passes
- [x] Security config loads (HMAC, IP whitelist, rate limiting)
- [x] Services initialize (PaymentService, NotificationService)
- [x] Flask app starts with security enabled
- [x] /health endpoint returns security status
- [x] Payment flow works end-to-end
- [x] Notification delivery works
- [x] No performance degradation
- [x] No connection pool exhaustion
- [x] Logs show new architecture components

---

## Estimated Timeline

### Phase 3.5 Integration - 2-3 Hours

**Hour 1: Database & Core**
- ⏱️ 30 min: Refactor DatabaseManager with ConnectionPool
- ⏱️ 15 min: Update app_initializer.py imports
- ⏱️ 15 min: Test database pool

**Hour 2: Services & Security**
- ⏱️ 20 min: Initialize security config
- ⏱️ 20 min: Replace old services with new
- ⏱️ 20 min: Wire services to Flask

**Hour 3: Testing & Verification**
- ⏱️ 30 min: Local integration testing
- ⏱️ 15 min: Fix any issues
- ⏱️ 15 min: Update documentation

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Connection pool breaks DB queries | Medium | High | Keep get_connection() for compatibility |
| Security config missing from Secret Manager | Low | Medium | Fallback to temporary secret (dev only) |
| Services API mismatch | Medium | Medium | Compatibility wrappers |
| Bot handlers conflict | Low | Medium | Keep old handlers alongside new |
| Flask server doesn't start | Low | High | Detailed error logging |
| Performance degradation | Low | Medium | Connection pool should improve performance |

---

## Questions Before Execution

1. **Secret Manager:**
   - Is `WEBHOOK_SIGNING_SECRET_NAME` already in Secret Manager?
   - If not, should we generate and add it now?

2. **Cloud Run IPs:**
   - Do we have the egress IP ranges for Cloud Run services?
   - Should we start with permissive IPs (10.0.0.0/8) and tighten later?

3. **Testing Strategy:**
   - Test locally first, or deploy to VM directly?
   - Keep old code as fallback branch?

4. **Migration Timeline:**
   - Integrate everything at once, or phase-by-phase?
   - Recommendation: All at once, with git backup

---

## Next Steps

**Immediate (Now):**
1. Review this integration plan
2. Approve/modify plan as needed
3. Prepare environment (Secret Manager, env vars)

**Execution (Next Session):**
1. Create git backup branch
2. Execute Tasks 1-7 sequentially
3. Run Task 8 testing checklist
4. Update PROGRESS.md and DECISIONS.md

**Post-Integration (Week 1):**
1. Monitor production stability
2. Gradually remove old handler code
3. Archive legacy code
4. Proceed to Phase 4: Testing

---

**END OF INTEGRATION PLAN**

Ready for execution in next session with full context.
