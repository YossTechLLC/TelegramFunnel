# GCBroadcastService Refactoring Architecture
## Converting GCBroadcastScheduler-10-26 to Independent Webhook Service

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Architecture Design
**Branch:** TelePay-REFACTOR
**Parent Document:** TELEPAY_REFACTORING_ARCHITECTURE.md

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture Analysis](#current-architecture-analysis)
3. [Target Service Architecture](#target-service-architecture)
4. [Module-by-Module Refactoring](#module-by-module-refactoring)
5. [Self-Contained Module Strategy](#self-contained-module-strategy)
6. [Database Integration](#database-integration)
7. [API Endpoints Specification](#api-endpoints-specification)
8. [Authentication & Authorization](#authentication--authorization)
9. [Deployment Strategy](#deployment-strategy)
10. [Testing Strategy](#testing-strategy)
11. [Migration Checklist](#migration-checklist)

---

## Executive Summary

### Problem Statement
The current **GCBroadcastScheduler-10-26** is a functional broadcast management service, but it needs to be refactored to align with the TelePay microservices architecture where each webhook is **fully self-contained** with no shared module dependencies.

### Refactoring Objectives
1. ✅ **Self-Contained Design:** All modules exist within the service directory (no external shared modules)
2. ✅ **Independent Deployment:** Service can be deployed without dependencies on other services
3. ✅ **Clean Architecture:** Maintain clear separation of concerns
4. ✅ **Functionality Preservation:** All existing features remain intact
5. ✅ **Cloud Run Optimized:** Designed for serverless execution patterns

### Key Changes from Current Architecture
- ❌ **REMOVE:** Dependencies on shared modules (if any were planned)
- ✅ **ADD:** All utility modules within service directory
- ✅ **MAINTAIN:** Existing functionality (automated + manual broadcasts)
- ✅ **ENHANCE:** Better error handling and observability

---

## Current Architecture Analysis

### 📁 Current File Structure (GCBroadcastScheduler-10-26)

```
GCBroadcastScheduler-10-26/
├── main.py                      # Flask app initialization & endpoints
├── broadcast_scheduler.py       # Scheduling logic (get due broadcasts)
├── broadcast_executor.py        # Execution logic (send messages)
├── broadcast_tracker.py         # State tracking (update database)
├── broadcast_web_api.py         # API endpoints (manual triggers)
├── telegram_client.py           # Telegram Bot API wrapper
├── config_manager.py            # Secret Manager integration
├── database_manager.py          # PostgreSQL operations
├── Dockerfile                   # Container definition
├── requirements.txt             # Python dependencies
├── .dockerignore               # Docker ignore patterns
└── .env.example                # Environment variable template
```

### 🔄 Current Process Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                   GCBroadcastScheduler-10-26                        │
│                                                                     │
│  ┌──────────────────┐           ┌──────────────────┐              │
│  │ Cloud Scheduler  │──POST────▶│  /api/broadcast  │              │
│  │  (Daily Cron)    │           │    /execute      │              │
│  └──────────────────┘           └────────┬─────────┘              │
│                                           │                         │
│  ┌──────────────────┐           ┌────────▼─────────┐              │
│  │  Website (JWT)   │──POST────▶│  /api/broadcast  │              │
│  │ Manual Trigger   │           │    /trigger      │              │
│  └──────────────────┘           └────────┬─────────┘              │
│                                           │                         │
│                          ┌────────────────┴────────────┐           │
│                          │   BroadcastScheduler        │           │
│                          │   - get_due_broadcasts()    │           │
│                          │   - check_rate_limit()      │           │
│                          └────────────┬────────────────┘           │
│                                       │                             │
│                          ┌────────────▼────────────────┐           │
│                          │   BroadcastExecutor         │           │
│                          │   - execute_broadcast()     │           │
│                          │   - send_subscription_msg() │           │
│                          │   - send_donation_msg()     │           │
│                          └────────────┬────────────────┘           │
│                                       │                             │
│                    ┌──────────────────┴────────────────┐           │
│                    │                                    │           │
│           ┌────────▼────────┐              ┌───────────▼────────┐  │
│           │ TelegramClient  │              │ BroadcastTracker   │  │
│           │ - send messages │              │ - update status    │  │
│           └────────┬────────┘              └───────────┬────────┘  │
│                    │                                    │           │
│           ┌────────▼────────┐              ┌───────────▼────────┐  │
│           │  Telegram API   │              │   DatabaseManager  │  │
│           └─────────────────┘              └───────────┬────────┘  │
│                                                         │           │
│                                            ┌────────────▼────────┐  │
│                                            │  PostgreSQL DB      │  │
│                                            │  (broadcast_mgr)    │  │
│                                            └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### ⚙️ Current Component Responsibilities

| Component | Responsibility | Dependencies |
|-----------|---------------|--------------|
| **main.py** | Flask app initialization, request routing | All other modules |
| **broadcast_scheduler.py** | Determine which broadcasts are due, rate limiting | DatabaseManager, ConfigManager |
| **broadcast_executor.py** | Execute broadcasts (send messages) | TelegramClient, BroadcastTracker |
| **broadcast_tracker.py** | Update broadcast state in database | DatabaseManager, ConfigManager |
| **broadcast_web_api.py** | JWT-authenticated API endpoints | BroadcastScheduler, DatabaseManager |
| **telegram_client.py** | Telegram Bot API wrapper (HTTP requests) | None (uses requests library) |
| **config_manager.py** | Fetch secrets from Secret Manager | Google Cloud Secret Manager |
| **database_manager.py** | PostgreSQL operations via Cloud SQL Connector | ConfigManager, SQLAlchemy |

### ✅ What Works Well (Keep)

1. **Clear Separation of Concerns:** Each module has a well-defined responsibility
2. **JWT Authentication:** Secure manual trigger endpoints
3. **Rate Limiting:** Prevents abuse of manual triggers
4. **Error Handling:** Graceful failure with detailed logging
5. **Cloud SQL Connector:** Secure database connections
6. **Stateless Design:** Service can scale horizontally
7. **Comprehensive Logging:** Excellent observability with emoji markers

### ⚠️ What Needs Refactoring (Change)

1. **Module Independence:** Ensure NO external shared module dependencies
2. **Service Naming:** Rename from "Scheduler" to "Service" (more accurate)
3. **Configuration Consolidation:** Simplify Secret Manager access patterns
4. **Error Recovery:** Add retry logic for transient Telegram API failures
5. **Database Connection Pooling:** Optimize connection management

---

## Target Service Architecture

### 🎯 Service Identity

**Service Name:** `GCBroadcastService-10-26`
**Cloud Run URL:** `https://gcbroadcastservice-10-26-pjxwjsdktq-uc.a.run.app`
**Purpose:** Automated and manual broadcast management for open and closed Telegram channels

### 📁 Target File Structure (Self-Contained)

```
GCBroadcastService-10-26/
├── main.py                      # Flask app (application factory pattern)
├── routes/
│   ├── __init__.py
│   ├── broadcast_routes.py      # Broadcast execution endpoints
│   └── api_routes.py            # Manual trigger API endpoints
├── services/
│   ├── __init__.py
│   ├── broadcast_scheduler.py   # Scheduling logic
│   ├── broadcast_executor.py    # Execution logic
│   └── broadcast_tracker.py     # State tracking
├── clients/
│   ├── __init__.py
│   ├── telegram_client.py       # Telegram Bot API wrapper
│   └── database_client.py       # PostgreSQL operations (renamed for clarity)
├── utils/
│   ├── __init__.py
│   ├── config.py                # Configuration & Secret Manager
│   ├── auth.py                  # JWT authentication decorators
│   └── logging_utils.py         # Structured logging helpers
├── models/
│   ├── __init__.py
│   └── broadcast_model.py       # Data models (optional, for type hints)
├── tests/
│   ├── __init__.py
│   ├── test_routes.py
│   ├── test_services.py
│   └── test_clients.py
├── Dockerfile                   # Container definition
├── requirements.txt             # Python dependencies
├── .dockerignore               # Docker ignore patterns
├── .env.example                # Environment variable template
└── README.md                   # Service documentation
```

### 🏗️ Architecture Principles

#### 1. Application Factory Pattern
```python
# main.py
def create_app():
    app = Flask(__name__)

    # Load configuration
    config = Config()
    app.config.update(config.to_dict())

    # Initialize JWT
    jwt = JWTManager(app)

    # Register blueprints
    from routes.broadcast_routes import broadcast_bp
    from routes.api_routes import api_bp
    app.register_blueprint(broadcast_bp)
    app.register_blueprint(api_bp)

    return app
```

#### 2. Dependency Injection Pattern
```python
# Services receive dependencies via constructor
class BroadcastExecutor:
    def __init__(self, telegram_client, broadcast_tracker):
        self.telegram = telegram_client
        self.tracker = broadcast_tracker
```

#### 3. Single Responsibility Principle
- **Routes:** Handle HTTP requests/responses only
- **Services:** Contain business logic
- **Clients:** Handle external API calls
- **Utils:** Provide reusable utilities

#### 4. Error Handling Strategy
```python
# All service methods return Result[T, Error] pattern
def execute_broadcast(entry) -> Dict[str, Any]:
    return {
        'success': bool,
        'data': Any,          # Present if success=True
        'error': str,         # Present if success=False
        'error_code': str     # Machine-readable error code
    }
```

---

## Module-by-Module Refactoring

### 1️⃣ **main.py** → Application Factory

#### Current (main.py)
```python
# Single file with inline initialization
app = Flask(__name__)
CORS(app, ...)
jwt = JWTManager(app)

# Components initialized globally
config_manager = ConfigManager()
database_manager = DatabaseManager(config_manager)
# ... etc

@app.route('/health')
def health():
    pass

@app.route('/api/broadcast/execute', methods=['POST'])
def execute_broadcasts():
    pass
```

#### Refactored (main.py)
```python
#!/usr/bin/env python3
"""
GCBroadcastService-10-26 - Main Application
Flask application for automated and manual broadcast management
"""

import os
import logging
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Import routes
from routes.broadcast_routes import broadcast_bp
from routes.api_routes import api_bp

# Import utilities
from utils.config import Config
from utils.logging_utils import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


def create_app(config=None):
    """
    Application factory for GCBroadcastService.

    Args:
        config: Optional config override (for testing)

    Returns:
        Flask app instance
    """
    app = Flask(__name__)

    # Load configuration
    app_config = config or Config()
    app.config.update(app_config.to_dict())

    # Configure CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["https://www.paygateprime.com"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
            "max_age": 3600
        }
    })

    # Initialize JWT authentication
    jwt = JWTManager(app)

    # Register error handlers
    register_error_handlers(jwt)

    # Register blueprints
    app.register_blueprint(broadcast_bp)
    app.register_blueprint(api_bp)

    logger.info("✅ GCBroadcastService-10-26 initialized successfully")

    return app


def register_error_handlers(jwt):
    """Register JWT error handlers"""

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        logger.warning("⚠️ JWT token expired")
        return {'error': 'Token expired', 'message': 'Session expired. Please log in again.'}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        logger.warning(f"⚠️ Invalid JWT token: {error}")
        return {'error': 'Invalid token', 'message': 'Session expired. Please log in again.'}, 401

    @jwt.unauthorized_loader
    def unauthorized_callback(error):
        logger.warning("⚠️ Missing JWT token")
        return {'error': 'Missing Authorization header', 'message': 'Authentication required'}, 401


if __name__ == "__main__":
    # For local development only (production uses gunicorn)
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🌟 Starting development server on port {port}...")

    app = create_app()
    app.run(host='0.0.0.0', port=port, debug=True)
```

**Key Changes:**
- ✅ Application factory pattern for testability
- ✅ Routes moved to separate blueprints
- ✅ Error handlers registered cleanly
- ✅ Configuration abstracted to Config class

---

### 2️⃣ **routes/broadcast_routes.py** → Broadcast Execution Routes

#### Purpose
Handle broadcast execution triggered by Cloud Scheduler (automated) or internal calls.

#### Implementation
```python
#!/usr/bin/env python3
"""
Broadcast Execution Routes
Handles automated broadcast execution triggered by Cloud Scheduler
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

# Import services
from services.broadcast_scheduler import BroadcastScheduler
from services.broadcast_executor import BroadcastExecutor
from services.broadcast_tracker import BroadcastTracker

# Import clients
from clients.telegram_client import TelegramClient
from clients.database_client import DatabaseClient

# Import utils
from utils.config import Config

logger = logging.getLogger(__name__)

# Create blueprint
broadcast_bp = Blueprint('broadcast', __name__)

# Initialize components (singleton pattern)
config = Config()
db_client = DatabaseClient(config)
telegram_client = TelegramClient(config)
broadcast_tracker = BroadcastTracker(db_client, config)
broadcast_scheduler = BroadcastScheduler(db_client, config)
broadcast_executor = BroadcastExecutor(telegram_client, broadcast_tracker)


@broadcast_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for Cloud Run.

    Returns:
        JSON: Health status
    """
    return jsonify({
        'status': 'healthy',
        'service': 'GCBroadcastService-10-26',
        'timestamp': datetime.now().isoformat()
    }), 200


@broadcast_bp.route('/api/broadcast/execute', methods=['POST'])
def execute_broadcasts():
    """
    Execute all due broadcasts.

    Triggered by:
    - Cloud Scheduler (daily cron job)
    - Manual testing via curl

    Request Body (optional):
    {
        "source": "cloud_scheduler" | "manual_test"
    }

    Response:
    {
        "success": true,
        "total_broadcasts": 10,
        "successful": 9,
        "failed": 1,
        "execution_time_seconds": 45.2,
        "results": [...]
    }
    """
    start_time = datetime.now()

    try:
        # Get optional source from request
        data = request.get_json() or {}
        source = data.get('source', 'unknown')

        logger.info(f"🎯 Broadcast execution triggered by: {source}")

        # 1. Get all broadcasts due for sending
        logger.info("📋 Fetching due broadcasts...")
        broadcasts = broadcast_scheduler.get_due_broadcasts()

        if not broadcasts:
            logger.info("✅ No broadcasts due at this time")
            return jsonify({
                'success': True,
                'total_broadcasts': 0,
                'successful': 0,
                'failed': 0,
                'execution_time_seconds': 0,
                'message': 'No broadcasts due'
            }), 200

        # 2. Execute all broadcasts
        logger.info(f"📤 Executing {len(broadcasts)} broadcasts...")
        result = broadcast_executor.execute_batch(broadcasts)

        # Calculate execution time
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        logger.info(
            f"✅ Execution complete: {result['successful']}/{result['total']} successful "
            f"in {execution_time:.2f}s"
        )

        return jsonify({
            'success': True,
            'total_broadcasts': result['total'],
            'successful': result['successful'],
            'failed': result['failed'],
            'execution_time_seconds': execution_time,
            'results': result['results']
        }), 200

    except Exception as e:
        logger.error(f"❌ Error executing broadcasts: {e}", exc_info=True)

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        return jsonify({
            'success': False,
            'error': str(e),
            'execution_time_seconds': execution_time
        }), 500
```

**Key Features:**
- ✅ Clear separation between automated and manual triggers
- ✅ Comprehensive request/response logging
- ✅ Error handling with execution time tracking
- ✅ Health check for Cloud Run monitoring

---

### 3️⃣ **routes/api_routes.py** → Manual Trigger API Routes

#### Purpose
Handle JWT-authenticated manual trigger requests from the website.

#### Implementation
```python
#!/usr/bin/env python3
"""
Manual Trigger API Routes
JWT-authenticated endpoints for manual broadcast triggers from website
"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

# Import services
from services.broadcast_scheduler import BroadcastScheduler

# Import clients
from clients.database_client import DatabaseClient

# Import utils
from utils.config import Config
from utils.auth import extract_client_id

logger = logging.getLogger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Initialize components
config = Config()
db_client = DatabaseClient(config)
broadcast_scheduler = BroadcastScheduler(db_client, config)


@api_bp.route('/broadcast/trigger', methods=['POST'])
@jwt_required()
def trigger_broadcast():
    """
    Manually trigger a broadcast for a specific channel pair.

    Requires JWT authentication (from website login).
    Enforces rate limiting (default: 5 minutes between triggers).

    Request Body:
    {
        "broadcast_id": "uuid"
    }

    Response (Success):
    {
        "success": true,
        "message": "Broadcast queued for sending",
        "broadcast_id": "uuid"
    }

    Response (Rate Limited):
    {
        "success": false,
        "error": "Rate limit exceeded",
        "retry_after_seconds": 180
    }

    Response (Unauthorized):
    {
        "success": false,
        "error": "Unauthorized: User does not own this channel"
    }
    """
    try:
        # Extract and validate request data
        data = request.get_json()

        if not data or 'broadcast_id' not in data:
            logger.warning("⚠️ Missing broadcast_id in request")
            return jsonify({'error': 'Missing broadcast_id'}), 400

        broadcast_id = data['broadcast_id']

        # Extract client ID from JWT
        client_id = extract_client_id()

        if not client_id:
            logger.warning("⚠️ Invalid JWT payload")
            return jsonify({'error': 'Invalid token payload'}), 401

        logger.info(f"📨 Manual trigger request: broadcast={broadcast_id[:8]}..., client={client_id[:8]}...")

        # Check rate limit
        rate_limit_check = broadcast_scheduler.check_manual_trigger_rate_limit(
            broadcast_id, client_id
        )

        if not rate_limit_check['allowed']:
            logger.warning(f"⏳ Rate limit blocked: {rate_limit_check['reason']}")
            return jsonify({
                'success': False,
                'error': rate_limit_check['reason'],
                'retry_after_seconds': rate_limit_check['retry_after_seconds']
            }), 429

        # Queue broadcast for immediate execution
        success = broadcast_scheduler.queue_manual_broadcast(broadcast_id)

        if success:
            logger.info(f"✅ Manual broadcast queued: {broadcast_id[:8]}...")
            return jsonify({
                'success': True,
                'message': 'Broadcast queued for sending',
                'broadcast_id': broadcast_id
            }), 200
        else:
            logger.error(f"❌ Failed to queue broadcast: {broadcast_id[:8]}...")
            return jsonify({
                'success': False,
                'error': 'Failed to queue broadcast'
            }), 500

    except Exception as e:
        logger.error(f"❌ Error in trigger_broadcast: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/broadcast/status/<broadcast_id>', methods=['GET'])
@jwt_required()
def get_broadcast_status(broadcast_id):
    """
    Get status and statistics for a specific broadcast.

    Requires JWT authentication.
    Verifies user owns the broadcast before returning data.

    Response:
    {
        "broadcast_id": "uuid",
        "status": "completed",
        "last_sent_time": "2025-11-11T12:00:00Z",
        "next_send_time": "2025-11-12T12:00:00Z",
        "total_broadcasts": 10,
        "successful_broadcasts": 9,
        "failed_broadcasts": 1,
        "consecutive_failures": 0,
        "is_active": true,
        "manual_trigger_count": 2
    }
    """
    try:
        # Extract client ID from JWT
        client_id = extract_client_id()

        if not client_id:
            return jsonify({'error': 'Invalid token payload'}), 401

        logger.info(f"📊 Status request: broadcast={broadcast_id[:8]}..., client={client_id[:8]}...")

        # Fetch statistics
        stats = db_client.get_broadcast_statistics(broadcast_id)

        if not stats:
            logger.warning(f"⚠️ Broadcast not found: {broadcast_id[:8]}...")
            return jsonify({'error': 'Broadcast not found'}), 404

        # Verify ownership
        broadcast_entry = db_client.fetch_broadcast_by_id(broadcast_id)

        if not broadcast_entry or str(broadcast_entry.get('client_id')) != str(client_id):
            logger.warning(f"⚠️ Unauthorized status request: {broadcast_id[:8]}...")
            return jsonify({'error': 'Unauthorized'}), 403

        # Convert datetime objects to ISO format strings
        for field in ['last_sent_time', 'next_send_time', 'last_error_time']:
            if field in stats and stats[field]:
                stats[field] = stats[field].isoformat()

        logger.info(f"✅ Status retrieved: {broadcast_id[:8]}...")
        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"❌ Error in get_broadcast_status: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
```

**Key Features:**
- ✅ JWT authentication for all endpoints
- ✅ Authorization checks (user must own the broadcast)
- ✅ Rate limiting enforcement
- ✅ Detailed error responses
- ✅ ISO 8601 datetime formatting

---

### 4️⃣ **services/broadcast_scheduler.py** → Scheduling Service

#### Purpose
Determine which broadcasts are due and enforce rate limiting.

#### Implementation (Minimal Changes from Current)
```python
#!/usr/bin/env python3
"""
BroadcastScheduler Service
Determines which broadcasts should be sent and enforces rate limiting
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class BroadcastScheduler:
    """
    Handles broadcast scheduling logic and rate limiting.

    Responsibilities:
    - Identify broadcasts that are due to be sent
    - Enforce rate limiting for manual triggers
    - Calculate next send times based on intervals
    - Queue broadcasts for execution
    """

    def __init__(self, db_client, config):
        """
        Initialize the BroadcastScheduler.

        Args:
            db_client: DatabaseClient instance
            config: Config instance (for fetching intervals)
        """
        self.db = db_client
        self.config = config
        self.logger = logging.getLogger(__name__)

    def get_due_broadcasts(self) -> List[Dict[str, Any]]:
        """
        Get all broadcast entries that are due to be sent.

        Delegates to DatabaseClient.fetch_due_broadcasts()

        Returns:
            List of broadcast entries with full channel details
        """
        broadcasts = self.db.fetch_due_broadcasts()
        self.logger.info(f"📋 Scheduler found {len(broadcasts)} broadcasts due for sending")
        return broadcasts

    def check_manual_trigger_rate_limit(
        self,
        broadcast_id: str,
        client_id: str
    ) -> Dict[str, Any]:
        """
        Check if a manual trigger is allowed based on rate limiting.

        Rate limit enforced: BROADCAST_MANUAL_INTERVAL (default 5 minutes)

        Args:
            broadcast_id: UUID of the broadcast entry
            client_id: Client UUID requesting the trigger (for verification)

        Returns:
            {
                'allowed': bool,
                'reason': str,
                'retry_after_seconds': int (if not allowed)
            }
        """
        try:
            # Fetch manual interval from Secret Manager
            manual_interval_hours = self.config.get_broadcast_manual_interval()
            manual_interval = timedelta(hours=manual_interval_hours)

            # Get last manual trigger time from database
            trigger_info = self.db.get_manual_trigger_info(broadcast_id)

            if not trigger_info:
                return {
                    'allowed': False,
                    'reason': 'Broadcast entry not found',
                    'retry_after_seconds': 0
                }

            db_client_id, last_trigger = trigger_info

            # Verify ownership
            if str(db_client_id) != str(client_id):
                self.logger.warning(
                    f"⚠️ Unauthorized manual trigger attempt: "
                    f"client {str(client_id)[:8]}... trying to trigger broadcast owned by {str(db_client_id)[:8]}..."
                )
                return {
                    'allowed': False,
                    'reason': 'Unauthorized: User does not own this channel',
                    'retry_after_seconds': 0
                }

            # Check rate limit
            if last_trigger:
                # Always use timezone-aware datetimes
                now = datetime.now(timezone.utc)

                # Ensure last_trigger is timezone-aware
                if last_trigger.tzinfo is None:
                    last_trigger = last_trigger.replace(tzinfo=timezone.utc)

                time_since_last = now - last_trigger

                if time_since_last < manual_interval:
                    retry_after = manual_interval - time_since_last
                    retry_seconds = int(retry_after.total_seconds())

                    self.logger.info(
                        f"⏳ Rate limit active for {str(broadcast_id)[:8]}...: "
                        f"retry in {retry_seconds}s"
                    )

                    return {
                        'allowed': False,
                        'reason': f'Rate limit: Must wait {manual_interval_hours} hours between manual triggers',
                        'retry_after_seconds': retry_seconds
                    }

            # All checks passed
            self.logger.info(f"✅ Manual trigger allowed for {str(broadcast_id)[:8]}...")
            return {
                'allowed': True,
                'reason': 'Manual trigger allowed',
                'retry_after_seconds': 0
            }

        except Exception as e:
            self.logger.error(f"❌ Error checking rate limit: {e}", exc_info=True)
            return {
                'allowed': False,
                'reason': f'Internal error: {str(e)}',
                'retry_after_seconds': 0
            }

    def queue_manual_broadcast(self, broadcast_id: str) -> bool:
        """
        Queue a broadcast for immediate execution (manual trigger).

        Sets next_send_time = NOW() to trigger on next cron run.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successfully queued, False otherwise
        """
        return self.db.queue_manual_broadcast(broadcast_id)

    def calculate_next_send_time(self) -> datetime:
        """
        Calculate the next send time based on BROADCAST_AUTO_INTERVAL.

        Returns:
            Datetime for next scheduled send
        """
        auto_interval_hours = self.config.get_broadcast_auto_interval()
        next_send = datetime.now() + timedelta(hours=auto_interval_hours)
        self.logger.debug(f"📅 Next send time calculated: {next_send.strftime('%Y-%m-%d %H:%M:%S')}")
        return next_send
```

**Key Features:**
- ✅ Timezone-aware datetime handling
- ✅ Rate limiting with retry_after calculation
- ✅ Authorization checks (user must own broadcast)
- ✅ Clean error responses

---

### 5️⃣ **services/broadcast_executor.py** → Execution Service

#### Purpose
Execute broadcasts by sending messages to Telegram channels.

#### Implementation (Minimal Changes from Current)
```python
#!/usr/bin/env python3
"""
BroadcastExecutor Service
Executes broadcast operations by sending messages to Telegram channels
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class BroadcastExecutor:
    """
    Executes broadcast operations by sending messages to Telegram channels.

    Responsibilities:
    - Send subscription tier messages to open channels
    - Send donation messages to closed channels
    - Handle Telegram API errors gracefully
    - Update broadcast status via BroadcastTracker
    """

    def __init__(self, telegram_client, broadcast_tracker):
        """
        Initialize the BroadcastExecutor.

        Args:
            telegram_client: TelegramClient instance for sending messages
            broadcast_tracker: BroadcastTracker instance for updating status
        """
        self.telegram = telegram_client
        self.tracker = broadcast_tracker
        self.logger = logging.getLogger(__name__)

    def execute_broadcast(self, broadcast_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single broadcast operation.

        Sends both subscription and donation messages, then updates status.

        Args:
            broadcast_entry: Broadcast entry from get_due_broadcasts()

        Returns:
            {
                'success': bool,
                'open_channel_sent': bool,
                'closed_channel_sent': bool,
                'errors': List[str]
            }
        """
        broadcast_id = broadcast_entry['id']
        open_channel_id = broadcast_entry['open_channel_id']
        closed_channel_id = broadcast_entry['closed_channel_id']

        self.logger.info(f"🚀 Executing broadcast {str(broadcast_id)[:8]}...")

        # Mark as in-progress
        self.tracker.update_status(broadcast_id, 'in_progress')

        errors = []
        open_sent = False
        closed_sent = False

        try:
            # Send subscription message to open channel
            self.logger.info(f"📤 Sending to open channel: {open_channel_id}")
            open_result = self._send_subscription_message(broadcast_entry)
            open_sent = open_result['success']

            if not open_sent:
                error_msg = f"Open channel: {open_result['error']}"
                errors.append(error_msg)
                self.logger.error(f"❌ {error_msg}")

            # Send donation message to closed channel
            self.logger.info(f"📤 Sending to closed channel: {closed_channel_id}")
            closed_result = self._send_donation_message(broadcast_entry)
            closed_sent = closed_result['success']

            if not closed_sent:
                error_msg = f"Closed channel: {closed_result['error']}"
                errors.append(error_msg)
                self.logger.error(f"❌ {error_msg}")

            # Determine overall success (both must succeed)
            success = open_sent and closed_sent

            # Update broadcast status
            if success:
                self.tracker.mark_success(broadcast_id)
                self.logger.info(f"✅ Broadcast {str(broadcast_id)[:8]}... completed successfully")
            else:
                error_msg = '; '.join(errors)
                self.tracker.mark_failure(broadcast_id, error_msg)
                self.logger.error(f"❌ Broadcast {str(broadcast_id)[:8]}... failed: {error_msg}")

            return {
                'success': success,
                'open_channel_sent': open_sent,
                'closed_channel_sent': closed_sent,
                'errors': errors,
                'broadcast_id': str(broadcast_id)
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            errors.append(error_msg)
            self.tracker.mark_failure(broadcast_id, error_msg)
            self.logger.error(f"❌ Broadcast {str(broadcast_id)[:8]}... exception: {e}", exc_info=True)

            return {
                'success': False,
                'open_channel_sent': open_sent,
                'closed_channel_sent': closed_sent,
                'errors': errors,
                'broadcast_id': str(broadcast_id)
            }

    def _send_subscription_message(self, broadcast_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send subscription tier message to open channel.

        Args:
            broadcast_entry: Broadcast entry with channel details

        Returns:
            {'success': bool, 'error': str}
        """
        try:
            open_channel_id = broadcast_entry['open_channel_id']
            open_title = broadcast_entry.get('open_channel_title', 'Open Channel')
            open_desc = broadcast_entry.get('open_channel_description', '')
            closed_title = broadcast_entry.get('closed_channel_title', 'Closed Channel')
            closed_desc = broadcast_entry.get('closed_channel_description', '')

            # Build subscription tier buttons
            tier_buttons = []
            for tier_num in (1, 2, 3):
                price = broadcast_entry.get(f'sub_{tier_num}_price')
                time = broadcast_entry.get(f'sub_{tier_num}_time')

                if price is not None and time is not None:
                    tier_buttons.append({
                        'tier': tier_num,
                        'price': float(price),
                        'time': int(time)
                    })

            if not tier_buttons:
                self.logger.warning(f"⚠️ No tier buttons available for {open_channel_id}")
                return {'success': False, 'error': 'No subscription tiers configured'}

            # Send via TelegramClient
            result = self.telegram.send_subscription_message(
                chat_id=open_channel_id,
                open_title=open_title,
                open_desc=open_desc,
                closed_title=closed_title,
                closed_desc=closed_desc,
                tier_buttons=tier_buttons
            )

            return result

        except Exception as e:
            self.logger.error(f"❌ Exception sending subscription message: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _send_donation_message(self, broadcast_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send donation message to closed channel.

        Args:
            broadcast_entry: Broadcast entry with channel details

        Returns:
            {'success': bool, 'error': str}
        """
        try:
            closed_channel_id = broadcast_entry['closed_channel_id']
            donation_message = broadcast_entry.get(
                'closed_channel_donation_message',
                'Consider supporting our channel!'
            )
            open_channel_id = broadcast_entry['open_channel_id']

            # Send via TelegramClient
            result = self.telegram.send_donation_message(
                chat_id=closed_channel_id,
                donation_message=donation_message,
                open_channel_id=open_channel_id
            )

            return result

        except Exception as e:
            self.logger.error(f"❌ Exception sending donation message: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def execute_batch(self, broadcast_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute multiple broadcasts in sequence.

        Args:
            broadcast_entries: List of broadcast entries

        Returns:
            {
                'total': int,
                'successful': int,
                'failed': int,
                'results': List[Dict]
            }
        """
        total = len(broadcast_entries)
        successful = 0
        failed = 0
        results = []

        self.logger.info(f"📊 Executing batch of {total} broadcasts")

        for entry in broadcast_entries:
            result = self.execute_broadcast(entry)

            if result['success']:
                successful += 1
            else:
                failed += 1

            results.append({
                'broadcast_id': result['broadcast_id'],
                'open_channel_id': entry['open_channel_id'],
                'result': result
            })

        self.logger.info(
            f"📊 Batch complete: {successful}/{total} successful, {failed} failed"
        )

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'results': results
        }
```

**Key Features:**
- ✅ Both open and closed channels handled in single execution
- ✅ Detailed error reporting per channel
- ✅ Status tracking via BroadcastTracker
- ✅ Batch execution support

---

### 6️⃣ **services/broadcast_tracker.py** → State Tracking Service

#### Purpose
Track broadcast state and update the database.

#### Implementation (Minimal Changes from Current)
```python
#!/usr/bin/env python3
"""
BroadcastTracker Service
Tracks broadcast state and updates database
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class BroadcastTracker:
    """
    Tracks broadcast state and updates the broadcast_manager table.

    Responsibilities:
    - Update broadcast status (pending → in_progress → completed/failed)
    - Track success/failure statistics
    - Calculate and set next send times
    - Handle error logging
    """

    def __init__(self, db_client, config):
        """
        Initialize the BroadcastTracker.

        Args:
            db_client: DatabaseClient instance
            config: Config instance (for intervals)
        """
        self.db = db_client
        self.config = config
        self.logger = logging.getLogger(__name__)

    def update_status(self, broadcast_id: str, status: str) -> bool:
        """
        Update broadcast status.

        Args:
            broadcast_id: UUID of the broadcast entry
            status: New status ('pending', 'in_progress', 'completed', 'failed', 'skipped')

        Returns:
            True if successful, False otherwise
        """
        return self.db.update_broadcast_status(broadcast_id, status)

    def mark_success(self, broadcast_id: str) -> bool:
        """
        Mark broadcast as successfully completed.

        Updates:
        - broadcast_status = 'completed'
        - last_sent_time = NOW()
        - next_send_time = NOW() + BROADCAST_AUTO_INTERVAL
        - total_broadcasts += 1
        - successful_broadcasts += 1
        - consecutive_failures = 0
        - last_error_message = NULL

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successful, False otherwise
        """
        # Get auto interval from config
        auto_interval_hours = self.config.get_broadcast_auto_interval()
        next_send = datetime.now() + timedelta(hours=auto_interval_hours)

        success = self.db.update_broadcast_success(broadcast_id, next_send)

        if success:
            self.logger.info(
                f"✅ Broadcast {str(broadcast_id)[:8]}... marked as success. "
                f"Next send: {next_send.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        return success

    def mark_failure(self, broadcast_id: str, error_message: str) -> bool:
        """
        Mark broadcast as failed.

        Updates:
        - broadcast_status = 'failed'
        - failed_broadcasts += 1
        - consecutive_failures += 1
        - last_error_message = error_message
        - last_error_time = NOW()
        - is_active = false (if consecutive_failures >= 5)

        Args:
            broadcast_id: UUID of the broadcast entry
            error_message: Error description

        Returns:
            True if successful, False otherwise
        """
        # Truncate error message if too long
        if len(error_message) > 500:
            error_message = error_message[:497] + "..."

        success = self.db.update_broadcast_failure(broadcast_id, error_message)

        if success:
            self.logger.error(
                f"❌ Broadcast {str(broadcast_id)[:8]}... marked as failure: {error_message[:100]}"
            )

        return success

    def reset_consecutive_failures(self, broadcast_id: str) -> bool:
        """
        Reset consecutive failure count (useful for manual re-enable).

        This is typically called when manually reactivating a disabled broadcast.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE broadcast_manager
                        SET consecutive_failures = 0,
                            is_active = true
                        WHERE id = %s
                    """, (broadcast_id,))

                    conn.commit()
                    self.logger.info(f"🔄 Reset consecutive failures: {broadcast_id[:8]}...")
                    return True

        except Exception as e:
            self.logger.error(f"❌ Error resetting failures: {e}")
            return False
```

**Key Features:**
- ✅ Automatic next send time calculation
- ✅ Consecutive failure tracking
- ✅ Auto-disable after 5 failures
- ✅ Manual re-enable support

---

## Self-Contained Module Strategy

### 🎯 No Shared Module Dependencies

**User Requirement:** Each webhook must be fully self-contained with no external shared module dependencies.

**Implementation Strategy:**

#### 1. Copy Utility Modules (Don't Import from Shared)

Each service contains its own copies of utility modules:

```
GCBroadcastService-10-26/
├── utils/
│   ├── config.py          # Self-contained Config class
│   ├── auth.py            # JWT authentication helpers
│   └── logging_utils.py   # Logging setup
├── clients/
│   ├── telegram_client.py  # Self-contained Telegram client
│   └── database_client.py  # Self-contained database client
```

**Why This Approach?**
- ✅ **Service Independence:** Each service can be deployed independently
- ✅ **Version Control:** Services can evolve at different rates
- ✅ **No Runtime Dependencies:** No risk of shared module version conflicts
- ✅ **Simplified Deployment:** Each service is a single Docker container

#### 2. Configuration Module (utils/config.py)

```python
#!/usr/bin/env python3
"""
Configuration Management
Self-contained config module for GCBroadcastService
"""

import os
import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class Config:
    """
    Manages configuration from Google Cloud Secret Manager.

    Self-contained - no external dependencies on shared modules.
    """

    def __init__(self):
        """Initialize the Config manager."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.logger = logging.getLogger(__name__)
        self._cache = {}

    def _fetch_secret(self, secret_env_var: str, default: Optional[str] = None) -> Optional[str]:
        """
        Fetch a secret from Secret Manager.

        Args:
            secret_env_var: Environment variable containing secret path
            default: Default value if secret cannot be fetched

        Returns:
            Secret value as string, or default if error occurs
        """
        try:
            secret_path = os.getenv(secret_env_var)
            if not secret_path:
                if default is not None:
                    self.logger.warning(f"⚠️ Environment variable {secret_env_var} not set, using default")
                    return default
                raise ValueError(f"Environment variable {secret_env_var} not set and no default provided")

            # Check cache
            if secret_path in self._cache:
                return self._cache[secret_path]

            # Fetch from Secret Manager
            response = self.client.access_secret_version(request={"name": secret_path})
            value = response.payload.data.decode("UTF-8").strip()

            # Cache value
            self._cache[secret_path] = value
            return value

        except Exception as e:
            self.logger.error(f"❌ Error fetching secret {secret_env_var}: {e}")
            if default is not None:
                return default
            raise

    # Configuration getters
    def get_broadcast_auto_interval(self) -> float:
        """Get automated broadcast interval in hours (default: 24.0)"""
        try:
            value = self._fetch_secret('BROADCAST_AUTO_INTERVAL_SECRET', default='24')
            return float(value)
        except (ValueError, TypeError):
            return 24.0

    def get_broadcast_manual_interval(self) -> float:
        """Get manual trigger rate limit interval in hours (default: 0.0833 = 5 minutes)"""
        try:
            value = self._fetch_secret('BROADCAST_MANUAL_INTERVAL_SECRET', default='0.0833')
            return float(value)
        except (ValueError, TypeError):
            return 0.0833

    def get_bot_token(self) -> str:
        """Get Telegram bot token"""
        token = self._fetch_secret('BOT_TOKEN_SECRET')
        if not token:
            raise ValueError("Bot token is required but not found")
        return token

    def get_bot_username(self) -> str:
        """Get Telegram bot username"""
        username = self._fetch_secret('BOT_USERNAME_SECRET')
        if not username:
            raise ValueError("Bot username is required but not found")
        return username

    def get_jwt_secret_key(self) -> str:
        """Get JWT secret key for authentication"""
        secret_key = self._fetch_secret('JWT_SECRET_KEY_SECRET')
        if not secret_key:
            raise ValueError("JWT secret key is required but not found")
        return secret_key

    def get_database_host(self) -> str:
        """Get database host from Secret Manager"""
        return self._fetch_secret('DATABASE_HOST_SECRET')

    def get_database_name(self) -> str:
        """Get database name from Secret Manager"""
        return self._fetch_secret('DATABASE_NAME_SECRET')

    def get_database_user(self) -> str:
        """Get database user from Secret Manager"""
        return self._fetch_secret('DATABASE_USER_SECRET')

    def get_database_password(self) -> str:
        """Get database password from Secret Manager"""
        return self._fetch_secret('DATABASE_PASSWORD_SECRET')

    def get_cloud_sql_connection_name(self) -> str:
        """Get Cloud SQL instance connection name from Secret Manager"""
        return self._fetch_secret('CLOUD_SQL_CONNECTION_NAME_SECRET')

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert config to dictionary for Flask app.config.

        Returns:
            Dictionary with JWT_SECRET_KEY and JWT_ALGORITHM
        """
        return {
            'JWT_SECRET_KEY': self.get_jwt_secret_key(),
            'JWT_ALGORITHM': 'HS256',
            'JWT_DECODE_LEEWAY': 10  # 10 seconds leeway for clock skew
        }

    def clear_cache(self):
        """Clear the configuration cache (useful for testing)"""
        self._cache.clear()
```

#### 3. Authentication Utilities (utils/auth.py)

```python
#!/usr/bin/env python3
"""
Authentication Utilities
JWT authentication helpers for GCBroadcastService
"""

import logging
from flask_jwt_extended import get_jwt_identity

logger = logging.getLogger(__name__)


def extract_client_id() -> str:
    """
    Extract client_id from JWT token.

    Returns:
        str: User ID from JWT 'sub' claim
        None: If token is invalid or missing
    """
    try:
        # Flask-JWT-Extended automatically validates and decodes the token
        client_id = get_jwt_identity()

        if not client_id:
            logger.warning("⚠️ Invalid token payload - missing identity")
            return None

        logger.debug(f"✅ Authenticated client: {client_id[:8]}...")
        return client_id

    except Exception as e:
        logger.error(f"❌ Error extracting client ID: {e}", exc_info=True)
        return None
```

#### 4. Logging Utilities (utils/logging_utils.py)

```python
#!/usr/bin/env python3
"""
Logging Utilities
Structured logging setup for GCBroadcastService
"""

import logging
import sys


def setup_logging(level=logging.INFO):
    """
    Set up structured logging for the service.

    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=level,
        stream=sys.stdout
    )

    # Set specific loggers to WARNING to reduce noise
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
```

#### 5. Telegram Client (clients/telegram_client.py)

**Copy the existing `telegram_client.py` as-is** - it's already self-contained and has no external dependencies beyond `requests`.

#### 6. Database Client (clients/database_client.py)

**Rename from `database_manager.py` to `database_client.py`** for consistency with naming conventions. The implementation remains the same.

---

## Database Integration

### 🗄️ broadcast_manager Table (Existing)

**No database schema changes required.** The service uses the existing `broadcast_manager` table:

```sql
CREATE TABLE broadcast_manager (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL,
    open_channel_id TEXT NOT NULL,
    closed_channel_id TEXT NOT NULL,
    broadcast_status TEXT DEFAULT 'pending',
    last_sent_time TIMESTAMP,
    next_send_time TIMESTAMP DEFAULT NOW(),
    total_broadcasts INTEGER DEFAULT 0,
    successful_broadcasts INTEGER DEFAULT 0,
    failed_broadcasts INTEGER DEFAULT 0,
    consecutive_failures INTEGER DEFAULT 0,
    last_error_message TEXT,
    last_error_time TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    last_manual_trigger_time TIMESTAMP,
    manual_trigger_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    CONSTRAINT fk_open_channel FOREIGN KEY (open_channel_id)
        REFERENCES main_clients_database(open_channel_id) ON DELETE CASCADE
);

CREATE INDEX idx_broadcast_manager_client_id ON broadcast_manager(client_id);
CREATE INDEX idx_broadcast_manager_next_send ON broadcast_manager(next_send_time);
CREATE INDEX idx_broadcast_manager_status ON broadcast_manager(broadcast_status);
```

### 🔍 Key Queries

#### Fetch Due Broadcasts
```sql
SELECT
    bm.id,
    bm.client_id,
    bm.open_channel_id,
    bm.closed_channel_id,
    bm.last_sent_time,
    bm.next_send_time,
    bm.broadcast_status,
    bm.consecutive_failures,
    mc.open_channel_title,
    mc.open_channel_description,
    mc.closed_channel_title,
    mc.closed_channel_description,
    mc.closed_channel_donation_message,
    mc.sub_1_price,
    mc.sub_1_time,
    mc.sub_2_price,
    mc.sub_2_time,
    mc.sub_3_price,
    mc.sub_3_time
FROM broadcast_manager bm
INNER JOIN main_clients_database mc
    ON bm.open_channel_id = mc.open_channel_id
WHERE bm.is_active = true
    AND bm.broadcast_status = 'pending'
    AND bm.next_send_time <= NOW()
    AND bm.consecutive_failures < 5
ORDER BY bm.next_send_time ASC;
```

#### Mark Broadcast Success
```sql
UPDATE broadcast_manager
SET
    broadcast_status = 'completed',
    last_sent_time = NOW(),
    next_send_time = %s,
    total_broadcasts = total_broadcasts + 1,
    successful_broadcasts = successful_broadcasts + 1,
    consecutive_failures = 0,
    last_error_message = NULL,
    last_error_time = NULL
WHERE id = %s;
```

#### Mark Broadcast Failure
```sql
UPDATE broadcast_manager
SET
    broadcast_status = 'failed',
    failed_broadcasts = failed_broadcasts + 1,
    consecutive_failures = consecutive_failures + 1,
    last_error_message = %s,
    last_error_time = NOW(),
    is_active = CASE
        WHEN consecutive_failures + 1 >= 5 THEN false
        ELSE is_active
    END
WHERE id = %s
RETURNING consecutive_failures, is_active;
```

---

## API Endpoints Specification

### 📡 Endpoint Summary

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | None | Health check for Cloud Run |
| `/api/broadcast/execute` | POST | None | Execute all due broadcasts (Cloud Scheduler) |
| `/api/broadcast/trigger` | POST | JWT | Manually trigger a specific broadcast |
| `/api/broadcast/status/<id>` | GET | JWT | Get broadcast statistics |

### 🔐 Authentication

**JWT Bearer Token Required** for `/api/*` endpoints (except `/api/broadcast/execute`).

```bash
# Example request with JWT
curl -X POST https://gcbroadcastservice-10-26-pjxwjsdktq-uc.a.run.app/api/broadcast/trigger \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"broadcast_id": "123e4567-e89b-12d3-a456-426614174000"}'
```

### 📊 Response Formats

#### Success Response
```json
{
  "success": true,
  "message": "Broadcast queued for sending",
  "broadcast_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

#### Error Response (Rate Limited)
```json
{
  "success": false,
  "error": "Rate limit: Must wait 0.0833 hours between manual triggers",
  "retry_after_seconds": 180
}
```

#### Error Response (Unauthorized)
```json
{
  "success": false,
  "error": "Unauthorized: User does not own this channel"
}
```

---

## Deployment Strategy

### 🚀 Cloud Run Deployment

#### Deployment Command
```bash
gcloud run deploy gcbroadcastservice-10-26 \
  --source=./GCBroadcastService-10-26 \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="BOT_TOKEN_SECRET=projects/telepay-459221/secrets/telegram-bot-token/versions/latest" \
  --set-env-vars="BOT_USERNAME_SECRET=projects/telepay-459221/secrets/telegram-bot-username/versions/latest" \
  --set-env-vars="JWT_SECRET_KEY_SECRET=projects/telepay-459221/secrets/jwt-secret-key/versions/latest" \
  --set-env-vars="BROADCAST_AUTO_INTERVAL_SECRET=projects/telepay-459221/secrets/broadcast-auto-interval/versions/latest" \
  --set-env-vars="BROADCAST_MANUAL_INTERVAL_SECRET=projects/telepay-459221/secrets/broadcast-manual-interval/versions/latest" \
  --set-env-vars="CLOUD_SQL_CONNECTION_NAME_SECRET=projects/telepay-459221/secrets/cloud-sql-connection-name/versions/latest" \
  --set-env-vars="DATABASE_NAME_SECRET=projects/telepay-459221/secrets/database-name/versions/latest" \
  --set-env-vars="DATABASE_USER_SECRET=projects/telepay-459221/secrets/database-user/versions/latest" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/database-password/versions/latest" \
  --min-instances=0 \
  --max-instances=3 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300s \
  --concurrency=80 \
  --service-account=telepay-cloudrun@telepay-459221.iam.gserviceaccount.com
```

#### Cloud Scheduler Configuration
```bash
gcloud scheduler jobs create http broadcast-execution-daily \
  --schedule="0 12 * * *" \
  --uri="https://gcbroadcastservice-10-26-pjxwjsdktq-uc.a.run.app/api/broadcast/execute" \
  --http-method=POST \
  --message-body='{"source": "cloud_scheduler"}' \
  --location=us-central1 \
  --oidc-service-account-email=telepay-scheduler@telepay-459221.iam.gserviceaccount.com
```

**Schedule:** Daily at 12:00 PM UTC

### 🔐 IAM Permissions

```bash
# Grant Secret Manager access to Cloud Run service account
gcloud secrets add-iam-policy-binding telegram-bot-token \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant Cloud SQL Client role
gcloud projects add-iam-policy-binding telepay-459221 \
  --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

# Grant Cloud Scheduler access to invoke Cloud Run
gcloud run services add-iam-policy-binding gcbroadcastservice-10-26 \
  --region=us-central1 \
  --member="serviceAccount:telepay-scheduler@telepay-459221.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

---

## Testing Strategy

### 🧪 Unit Tests

```python
# tests/test_services.py
import pytest
from services.broadcast_scheduler import BroadcastScheduler
from unittest.mock import Mock

def test_get_due_broadcasts():
    """Test that scheduler fetches due broadcasts from database"""
    mock_db = Mock()
    mock_db.fetch_due_broadcasts.return_value = [
        {'id': '123', 'open_channel_id': '-1001234', 'closed_channel_id': '-1005678'}
    ]

    mock_config = Mock()
    scheduler = BroadcastScheduler(mock_db, mock_config)

    broadcasts = scheduler.get_due_broadcasts()

    assert len(broadcasts) == 1
    assert broadcasts[0]['id'] == '123'
    mock_db.fetch_due_broadcasts.assert_called_once()


def test_rate_limit_enforcement():
    """Test that rate limiting prevents rapid manual triggers"""
    from datetime import datetime, timezone

    mock_db = Mock()
    mock_db.get_manual_trigger_info.return_value = (
        'client-uuid-123',
        datetime.now(timezone.utc)  # Just triggered
    )

    mock_config = Mock()
    mock_config.get_broadcast_manual_interval.return_value = 0.0833  # 5 minutes

    scheduler = BroadcastScheduler(mock_db, mock_config)

    result = scheduler.check_manual_trigger_rate_limit('broadcast-id', 'client-uuid-123')

    assert result['allowed'] == False
    assert result['retry_after_seconds'] > 0
```

### 🌐 Integration Tests

```python
# tests/test_routes.py
import pytest
from main import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['service'] == 'GCBroadcastService-10-26'


def test_execute_broadcasts_no_due(client):
    """Test broadcast execution when no broadcasts are due"""
    response = client.post('/api/broadcast/execute', json={'source': 'manual_test'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] == True
    assert data['total_broadcasts'] == 0
```

### 🔒 End-to-End Tests

```python
# tests/test_e2e.py
import pytest
import requests

def test_manual_trigger_with_jwt():
    """Test manual trigger endpoint with valid JWT token"""
    # This test requires a test database and test JWT token
    jwt_token = get_test_jwt_token()
    broadcast_id = create_test_broadcast()

    response = requests.post(
        'https://gcbroadcastservice-10-26-pjxwjsdktq-uc.a.run.app/api/broadcast/trigger',
        headers={'Authorization': f'Bearer {jwt_token}'},
        json={'broadcast_id': broadcast_id}
    )

    assert response.status_code == 200
    data = response.json()
    assert data['success'] == True
```

---

## Migration Checklist

### ✅ Phase 1: Preparation (1-2 hours)

- [ ] Create new directory: `GCBroadcastService-10-26`
- [ ] Copy and refactor `main.py` to use application factory pattern
- [ ] Create `routes/` directory with `broadcast_routes.py` and `api_routes.py`
- [ ] Create `services/` directory and copy service modules (minimal changes)
- [ ] Create `clients/` directory and copy `telegram_client.py` and rename `database_manager.py` to `database_client.py`
- [ ] Create `utils/` directory with `config.py`, `auth.py`, `logging_utils.py`
- [ ] Copy `Dockerfile` and `requirements.txt` (no changes needed)
- [ ] Create `.dockerignore` and `.env.example`
- [ ] Create `README.md` with service documentation

### ✅ Phase 2: Testing (2-3 hours)

- [ ] Write unit tests for services (`tests/test_services.py`)
- [ ] Write integration tests for routes (`tests/test_routes.py`)
- [ ] Test locally with Docker:
  ```bash
  docker build -t gcbroadcastservice-10-26 .
  docker run -p 8080:8080 --env-file .env.local gcbroadcastservice-10-26
  ```
- [ ] Test health check: `curl http://localhost:8080/health`
- [ ] Test broadcast execution: `curl -X POST http://localhost:8080/api/broadcast/execute`
- [ ] Verify database queries work correctly
- [ ] Verify JWT authentication works

### ✅ Phase 3: Deployment (1 hour)

- [ ] Deploy to Cloud Run (see deployment command above)
- [ ] Verify service is running: `gcloud run services describe gcbroadcastservice-10-26 --region=us-central1`
- [ ] Test Cloud Run health check
- [ ] Create Cloud Scheduler job (see configuration above)
- [ ] Grant IAM permissions (see IAM commands above)
- [ ] Test manual trigger endpoint with real JWT token
- [ ] Test Cloud Scheduler trigger (trigger manually first)

### ✅ Phase 4: Monitoring (30 minutes)

- [ ] Set up Cloud Logging filters:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbroadcastservice-10-26"
  ```
- [ ] Set up Cloud Monitoring dashboard
- [ ] Create alert policy for error rate > 5%
- [ ] Create alert policy for failed broadcasts > 3 consecutive
- [ ] Test alert notifications

### ✅ Phase 5: Documentation (30 minutes)

- [ ] Update `TELEPAY_REFACTORING_ARCHITECTURE.md` with GCBroadcastService details
- [ ] Document API endpoints in `README.md`
- [ ] Document environment variables
- [ ] Document deployment procedure
- [ ] Document rollback procedure

### ✅ Phase 6: Decommission Old Service (1 hour)

**Only proceed after 48 hours of successful operation**

- [ ] Verify GCBroadcastService is working correctly
- [ ] Compare broadcast success rates (old vs new)
- [ ] Scale down GCBroadcastScheduler-10-26:
  ```bash
  gcloud run services update gcbroadcastscheduler-10-26 \
    --region=us-central1 \
    --min-instances=0 \
    --max-instances=0
  ```
- [ ] Disable old Cloud Scheduler jobs
- [ ] Archive GCBroadcastScheduler-10-26 code:
  ```bash
  mv GCBroadcastScheduler-10-26 ARCHIVES/GCBroadcastScheduler-10-26-ORIGINAL
  ```
- [ ] Update PROGRESS.md

---

## Conclusion

This refactoring architecture transforms **GCBroadcastScheduler-10-26** into **GCBroadcastService-10-26** - a fully self-contained, independently deployable webhook service that:

✅ **Contains all modules within the service directory** (no external shared module dependencies)
✅ **Follows Flask application factory pattern** for clean architecture
✅ **Maintains all existing functionality** (automated + manual broadcasts)
✅ **Enhances observability** with structured logging
✅ **Simplifies deployment** with clear separation of concerns
✅ **Enables independent evolution** of the broadcast service

**Total Estimated Refactoring Time:** 7-9 hours

**Risk Level:** Low (existing implementation is solid, refactoring is mostly organizational)

---

**Document Owner:** Claude
**Review Date:** 2025-11-12
**Next Review:** After deployment completion
