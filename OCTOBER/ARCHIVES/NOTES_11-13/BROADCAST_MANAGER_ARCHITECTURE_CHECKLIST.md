# Broadcast Manager Architecture - Implementation Checklist
**Version:** 1.0
**Date:** 2025-11-11
**Reference:** BROADCAST_MANAGER_ARCHITECTURE.md
**Author:** Claude Code

---

## Overview

This checklist provides a step-by-step implementation guide for the Broadcast Manager Architecture. Each phase is broken down into specific, actionable tasks that ensure modular code structure and maintainability.

**Key Principles:**
- ✅ **Modular Design**: Each component in its own file
- ✅ **Clear Separation**: Database, business logic, API, and config separate
- ✅ **Testability**: Each module independently testable
- ✅ **Maintainability**: Single responsibility per module

---

## Implementation Progress Tracker

**Overall Status:** Not Started

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Database Setup | ⬜ Not Started | 0/8 |
| Phase 2: Service Development | ⬜ Not Started | 0/27 |
| Phase 3: Secret Manager Setup | ⬜ Not Started | 0/6 |
| Phase 4: Cloud Run Deployment | ⬜ Not Started | 0/8 |
| Phase 5: Cloud Scheduler Setup | ⬜ Not Started | 0/5 |
| Phase 6: Website Integration | ⬜ Not Started | 0/7 |
| Phase 7: Monitoring & Testing | ⬜ Not Started | 0/10 |
| Phase 8: Decommission Old System | ⬜ Not Started | 0/5 |

**Total Tasks:** 76

---

## Phase 1: Database Setup
**Goal:** Create and populate the `broadcast_manager` table
**Duration:** 1-2 days
**Dependencies:** None

### Database Migration Scripts

#### 1.1 Create Migration Script
- [ ] Create `TOOLS_SCRIPTS_TESTS/scripts/create_broadcast_manager_table.sql`
- [ ] Define table schema with all columns:
  - [ ] `id` (UUID PRIMARY KEY)
  - [ ] `user_id` (INTEGER NOT NULL)
  - [ ] `open_channel_id` (TEXT NOT NULL)
  - [ ] `closed_channel_id` (TEXT NOT NULL)
  - [ ] `last_sent_time` (TIMESTAMP WITH TIME ZONE)
  - [ ] `next_send_time` (TIMESTAMP WITH TIME ZONE DEFAULT NOW())
  - [ ] `broadcast_status` (VARCHAR(20) DEFAULT 'pending')
  - [ ] `last_manual_trigger_time` (TIMESTAMP WITH TIME ZONE)
  - [ ] `manual_trigger_count` (INTEGER DEFAULT 0)
  - [ ] `total_broadcasts` (INTEGER DEFAULT 0)
  - [ ] `successful_broadcasts` (INTEGER DEFAULT 0)
  - [ ] `failed_broadcasts` (INTEGER DEFAULT 0)
  - [ ] `last_error_message` (TEXT)
  - [ ] `last_error_time` (TIMESTAMP WITH TIME ZONE)
  - [ ] `consecutive_failures` (INTEGER DEFAULT 0)
  - [ ] `is_active` (BOOLEAN DEFAULT true)
  - [ ] `created_at` (TIMESTAMP WITH TIME ZONE DEFAULT NOW())
  - [ ] `updated_at` (TIMESTAMP WITH TIME ZONE DEFAULT NOW())
- [ ] Add foreign key constraints:
  - [ ] `fk_broadcast_user` → users(id)
  - [ ] `fk_broadcast_channels` → main_clients_database(open_channel_id)
- [ ] Add unique constraint on (open_channel_id, closed_channel_id)
- [ ] Add CHECK constraint for valid broadcast_status values
- [ ] Create indexes:
  - [ ] `idx_broadcast_next_send` on next_send_time WHERE is_active = true
  - [ ] `idx_broadcast_user` on user_id
  - [ ] `idx_broadcast_status` on broadcast_status WHERE is_active = true
  - [ ] `idx_broadcast_open_channel` on open_channel_id
- [ ] Create `update_broadcast_updated_at()` trigger function
- [ ] Create trigger to auto-update `updated_at` on row updates
- [ ] Add column comments for documentation
- [ ] Add table comments

#### 1.2 Create Rollback Script
- [ ] Create `TOOLS_SCRIPTS_TESTS/scripts/rollback_broadcast_manager_table.sql`
- [ ] Drop trigger first
- [ ] Drop trigger function
- [ ] Drop all indexes
- [ ] Drop table with CASCADE
- [ ] Add verification check to ensure table is dropped

#### 1.3 Execute Migration
- [ ] Review migration script for correctness
- [ ] Test migration on local database (if available)
- [ ] Execute migration on `telepaypsql` database:
  ```bash
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres \
       -d telepaydb \
       -f create_broadcast_manager_table.sql
  ```
- [ ] Verify table creation:
  - [ ] Check all columns exist
  - [ ] Verify indexes created
  - [ ] Verify triggers created
  - [ ] Verify constraints applied

### Data Population

#### 1.4 Create Population Script
- [ ] Create `TOOLS_SCRIPTS_TESTS/tools/populate_broadcast_manager.py`
- [ ] Implement database credential fetching from Secret Manager
- [ ] Implement database connection logic
- [ ] Query `main_clients_database` for all channel pairs:
  - [ ] SELECT user_id, open_channel_id, closed_channel_id
  - [ ] WHERE both channels are NOT NULL
- [ ] Insert entries into `broadcast_manager`:
  - [ ] Set initial `next_send_time = NOW()` (will send on first cron run)
  - [ ] Set `broadcast_status = 'pending'`
  - [ ] Set `is_active = true`
  - [ ] Use ON CONFLICT DO NOTHING for idempotency
- [ ] Add error handling and logging
- [ ] Print summary statistics (inserted, skipped, errors)

#### 1.5 Execute Population
- [ ] Run population script:
  ```bash
  python3 TOOLS_SCRIPTS_TESTS/tools/populate_broadcast_manager.py
  ```
- [ ] Verify data populated correctly:
  - [ ] Check row count matches main_clients_database
  - [ ] Verify all channel pairs created
  - [ ] Check no duplicate entries
  - [ ] Verify initial state (status=pending, next_send_time set)

### Documentation

#### 1.6 Update Documentation
- [ ] Update PROGRESS.md with Phase 1 completion
- [ ] Update DECISIONS.md if any schema decisions changed
- [ ] Document any issues encountered during migration

---

## Phase 2: Service Development
**Goal:** Create GCBroadcastScheduler-10-26 service with 5 modular components
**Duration:** 5-7 days
**Dependencies:** Phase 1 (Database Setup)

### Project Structure Setup

#### 2.1 Create Directory Structure
- [ ] Create `GCBroadcastScheduler-10-26/` directory
- [ ] Create subdirectories:
  - [ ] `api/` (API endpoints)
  - [ ] `core/` (Core business logic)
  - [ ] `utils/` (Utilities and helpers)
  - [ ] `tests/` (Unit tests)
- [ ] Create `__init__.py` in each package directory
- [ ] Create `requirements.txt`
- [ ] Create `Dockerfile`
- [ ] Create `.dockerignore`
- [ ] Create `.env.example` for local development

### Core Module 1: ConfigManager

#### 2.2 Implement ConfigManager Module
**File:** `GCBroadcastScheduler-10-26/config_manager.py`

- [ ] Create `config_manager.py` file
- [ ] Import required dependencies:
  - [ ] `os`
  - [ ] `logging`
  - [ ] `google.cloud.secretmanager`
- [ ] Implement `ConfigManager` class:
  - [ ] `__init__()` - Initialize Secret Manager client
  - [ ] `_fetch_secret(secret_env_var)` - Fetch secret from Secret Manager
  - [ ] `get_broadcast_auto_interval()` - Get automated interval (default: 24.0 hours)
  - [ ] `get_broadcast_manual_interval()` - Get manual interval (default: 0.0833 hours = 5 min)
  - [ ] `get_bot_token()` - Get Telegram bot token
  - [ ] `get_bot_username()` - Get Telegram bot username
  - [ ] `get_jwt_secret_key()` - Get JWT secret for authentication
  - [ ] `clear_cache()` - Clear secret cache for testing
- [ ] Add in-memory caching for fetched secrets
- [ ] Add error handling with fallback to default values
- [ ] Add logging for all operations
- [ ] Add type hints for all methods
- [ ] Add docstrings for class and all methods

**Testing:**
- [ ] Create `tests/test_config_manager.py`
- [ ] Test secret fetching with mocked Secret Manager
- [ ] Test caching behavior
- [ ] Test fallback to defaults on errors
- [ ] Test environment variable validation

### Core Module 2: DatabaseManager Extensions

#### 2.3 Extend DatabaseManager Module
**File:** `GCBroadcastScheduler-10-26/database_manager.py`

**Note:** This is a separate database_manager.py specific to the broadcast scheduler, NOT the one in TelePay10-26

- [ ] Create `database_manager.py` file
- [ ] Import required dependencies:
  - [ ] `psycopg2`
  - [ ] `typing` (List, Dict, Any, Optional, Tuple)
  - [ ] `google.cloud.secretmanager`
  - [ ] `datetime`
- [ ] Implement database credential fetching functions:
  - [ ] `fetch_database_host()`
  - [ ] `fetch_database_name()`
  - [ ] `fetch_database_user()`
  - [ ] `fetch_database_password()`
- [ ] Implement `DatabaseManager` class:
  - [ ] `__init__()` - Initialize connection parameters
  - [ ] `get_connection()` - Create database connection
  - [ ] `fetch_due_broadcasts()` - Get broadcasts where next_send_time <= NOW()
  - [ ] `fetch_broadcast_by_id(broadcast_id)` - Get single broadcast entry
  - [ ] `update_broadcast_status(broadcast_id, status)` - Update status field
  - [ ] `update_broadcast_success(broadcast_id, next_send_time)` - Mark success
  - [ ] `update_broadcast_failure(broadcast_id, error_msg)` - Mark failure
  - [ ] `get_manual_trigger_info(broadcast_id)` - Get last trigger time for rate limiting
  - [ ] `queue_manual_broadcast(broadcast_id)` - Set next_send_time = NOW()
  - [ ] `get_broadcast_statistics(broadcast_id)` - Get stats for API responses
- [ ] Use parameterized queries for all SQL (prevent SQL injection)
- [ ] Add comprehensive error handling
- [ ] Add logging for all database operations
- [ ] Add type hints for all methods
- [ ] Add docstrings for class and all methods

**Testing:**
- [ ] Create `tests/test_database_manager.py`
- [ ] Test connection creation
- [ ] Test all query methods with test database
- [ ] Test error handling (connection failures, query errors)
- [ ] Test SQL injection prevention

### Core Module 3: TelegramClient

#### 2.4 Implement TelegramClient Module
**File:** `GCBroadcastScheduler-10-26/telegram_client.py`

- [ ] Create `telegram_client.py` file
- [ ] Import required dependencies:
  - [ ] `logging`
  - [ ] `base64`
  - [ ] `typing` (Dict, Any, List)
  - [ ] `telegram` (Bot, InlineKeyboardButton, InlineKeyboardMarkup)
  - [ ] `telegram.error` (TelegramError, Forbidden, BadRequest)
- [ ] Implement `TelegramClient` class:
  - [ ] `__init__(bot_token, bot_username)` - Initialize Bot instance
  - [ ] `encode_id(channel_id)` - Encode ID for deep link tokens
  - [ ] `send_subscription_message(chat_id, open_title, open_desc, closed_title, closed_desc, tier_buttons)` - Send subscription message
  - [ ] `send_donation_message(chat_id, donation_message, open_channel_id)` - Send donation message
  - [ ] `_build_subscription_keyboard(tier_buttons)` - Build inline keyboard for subscriptions
  - [ ] `_build_donation_keyboard(open_channel_id)` - Build inline keyboard for donations
  - [ ] `_format_subscription_message(open_title, open_desc, closed_title, closed_desc)` - Format message text
  - [ ] `_format_donation_message(donation_message)` - Format donation message text
- [ ] Handle all Telegram API errors gracefully:
  - [ ] `Forbidden` (bot not admin/kicked)
  - [ ] `BadRequest` (invalid channel ID)
  - [ ] `TelegramError` (general errors)
- [ ] Return standardized response: `{'success': bool, 'error': str}`
- [ ] Add message length validation (4096 char limit)
- [ ] Add callback_data length validation (64 byte limit)
- [ ] Add logging for all operations
- [ ] Add type hints for all methods
- [ ] Add docstrings for class and all methods

**Testing:**
- [ ] Create `tests/test_telegram_client.py`
- [ ] Test message formatting
- [ ] Test keyboard building
- [ ] Test error handling with mocked Bot
- [ ] Test validation (message length, callback_data length)

### Core Module 4: BroadcastScheduler

#### 2.5 Implement BroadcastScheduler Module
**File:** `GCBroadcastScheduler-10-26/broadcast_scheduler.py`

- [ ] Create `broadcast_scheduler.py` file
- [ ] Import required dependencies:
  - [ ] `logging`
  - [ ] `datetime` (datetime, timedelta)
  - [ ] `typing` (List, Dict, Any, Optional)
  - [ ] `database_manager` (DatabaseManager)
  - [ ] `config_manager` (ConfigManager)
- [ ] Implement `BroadcastScheduler` class:
  - [ ] `__init__(db_manager, config_manager)` - Initialize with dependencies
  - [ ] `get_due_broadcasts()` - Query database for broadcasts due to be sent
  - [ ] `check_manual_trigger_rate_limit(broadcast_id, user_id)` - Enforce 5-min rate limit
  - [ ] `queue_manual_broadcast(broadcast_id)` - Queue for immediate send
  - [ ] `calculate_next_send_time()` - Calculate next send based on interval
  - [ ] `_validate_broadcast_entry(entry)` - Validate entry has required fields
- [ ] Implement rate limiting logic:
  - [ ] Fetch last_manual_trigger_time from database
  - [ ] Compare with BROADCAST_MANUAL_INTERVAL
  - [ ] Return `{'allowed': bool, 'reason': str, 'retry_after_seconds': int}`
- [ ] Implement ownership verification (user_id must match)
- [ ] Add logging for all operations
- [ ] Add type hints for all methods
- [ ] Add docstrings for class and all methods

**Testing:**
- [ ] Create `tests/test_broadcast_scheduler.py`
- [ ] Test get_due_broadcasts() with mocked database
- [ ] Test rate limit enforcement (allowed and blocked cases)
- [ ] Test ownership verification
- [ ] Test next_send_time calculation

### Core Module 5: BroadcastExecutor

#### 2.6 Implement BroadcastExecutor Module
**File:** `GCBroadcastScheduler-10-26/broadcast_executor.py`

- [ ] Create `broadcast_executor.py` file
- [ ] Import required dependencies:
  - [ ] `logging`
  - [ ] `typing` (Dict, Any, List)
  - [ ] `telegram_client` (TelegramClient)
  - [ ] `broadcast_tracker` (BroadcastTracker)
- [ ] Implement `BroadcastExecutor` class:
  - [ ] `__init__(telegram_client, broadcast_tracker)` - Initialize with dependencies
  - [ ] `execute_broadcast(broadcast_entry)` - Execute single broadcast
  - [ ] `execute_batch(broadcast_entries)` - Execute multiple broadcasts
  - [ ] `_send_subscription_message(broadcast_entry)` - Send to open channel
  - [ ] `_send_donation_message(broadcast_entry)` - Send to closed channel
  - [ ] `_extract_tier_buttons(broadcast_entry)` - Extract tier info from entry
- [ ] Implement execution flow:
  - [ ] Mark status as 'in_progress' (via tracker)
  - [ ] Send subscription message to open channel
  - [ ] Send donation message to closed channel
  - [ ] Collect errors from both operations
  - [ ] Determine overall success (both must succeed)
  - [ ] Update status via tracker (success or failure)
- [ ] Return execution result:
  - [ ] `{'success': bool, 'open_channel_sent': bool, 'closed_channel_sent': bool, 'errors': List[str]}`
- [ ] Add error handling for unexpected exceptions
- [ ] Add logging for all operations
- [ ] Add type hints for all methods
- [ ] Add docstrings for class and all methods

**Testing:**
- [ ] Create `tests/test_broadcast_executor.py`
- [ ] Test single broadcast execution
- [ ] Test batch execution
- [ ] Test partial failures (one channel fails)
- [ ] Test complete failures (both channels fail)
- [ ] Test success case

### Core Module 6: BroadcastTracker

#### 2.7 Implement BroadcastTracker Module
**File:** `GCBroadcastScheduler-10-26/broadcast_tracker.py`

- [ ] Create `broadcast_tracker.py` file
- [ ] Import required dependencies:
  - [ ] `logging`
  - [ ] `datetime` (datetime, timedelta)
  - [ ] `typing` (Optional)
  - [ ] `database_manager` (DatabaseManager)
  - [ ] `config_manager` (ConfigManager)
- [ ] Implement `BroadcastTracker` class:
  - [ ] `__init__(db_manager, config_manager)` - Initialize with dependencies
  - [ ] `update_status(broadcast_id, status)` - Update broadcast_status field
  - [ ] `mark_success(broadcast_id)` - Mark broadcast as completed successfully
  - [ ] `mark_failure(broadcast_id, error_message)` - Mark broadcast as failed
  - [ ] `reset_consecutive_failures(broadcast_id)` - Reset failure count (manual re-enable)
- [ ] Implement success tracking:
  - [ ] Set broadcast_status = 'completed'
  - [ ] Set last_sent_time = NOW()
  - [ ] Set next_send_time = NOW() + BROADCAST_AUTO_INTERVAL
  - [ ] Increment total_broadcasts
  - [ ] Increment successful_broadcasts
  - [ ] Reset consecutive_failures to 0
  - [ ] Clear last_error_message
- [ ] Implement failure tracking:
  - [ ] Set broadcast_status = 'failed'
  - [ ] Increment failed_broadcasts
  - [ ] Increment consecutive_failures
  - [ ] Set last_error_message
  - [ ] Set last_error_time = NOW()
  - [ ] Deactivate (is_active = false) if consecutive_failures >= 5
- [ ] Add logging for all operations
- [ ] Add type hints for all methods
- [ ] Add docstrings for class and all methods

**Testing:**
- [ ] Create `tests/test_broadcast_tracker.py`
- [ ] Test mark_success() updates all fields correctly
- [ ] Test mark_failure() updates all fields correctly
- [ ] Test auto-deactivation after 5 failures
- [ ] Test consecutive_failures reset

### API Module: BroadcastWebAPI

#### 2.8 Implement BroadcastWebAPI Module
**File:** `GCBroadcastScheduler-10-26/broadcast_web_api.py`

- [ ] Create `broadcast_web_api.py` file
- [ ] Import required dependencies:
  - [ ] `logging`
  - [ ] `typing` (Dict, Any)
  - [ ] `flask` (Blueprint, request, jsonify)
  - [ ] `functools` (wraps)
  - [ ] `jwt`
  - [ ] `os`
  - [ ] `broadcast_scheduler` (BroadcastScheduler)
- [ ] Create Flask Blueprint `broadcast_api`
- [ ] Implement `authenticate_request` decorator:
  - [ ] Extract Authorization header
  - [ ] Parse "Bearer <token>" format
  - [ ] Decode JWT token
  - [ ] Verify signature with JWT_SECRET_KEY
  - [ ] Extract user_id from payload
  - [ ] Handle expired tokens (401)
  - [ ] Handle invalid tokens (401)
- [ ] Implement `BroadcastWebAPI` class:
  - [ ] `__init__(broadcast_scheduler)` - Initialize with scheduler
  - [ ] `_register_routes()` - Register all API routes
  - [ ] `get_blueprint()` - Return Flask blueprint
- [ ] Implement API endpoints:
  - [ ] `POST /api/broadcast/trigger`:
    - [ ] Validate request body (broadcast_id required)
    - [ ] Check rate limit
    - [ ] Queue manual broadcast
    - [ ] Return success or rate limit error (429)
  - [ ] `GET /api/broadcast/status/<broadcast_id>`:
    - [ ] Fetch broadcast status from database
    - [ ] Verify ownership (user_id matches token)
    - [ ] Return status information
- [ ] Add error handling for all endpoints (500 on exceptions)
- [ ] Add request validation
- [ ] Add logging for all API calls
- [ ] Add type hints for all methods
- [ ] Add docstrings for class and all methods

**Testing:**
- [ ] Create `tests/test_broadcast_web_api.py`
- [ ] Test authentication decorator (valid, invalid, expired tokens)
- [ ] Test /api/broadcast/trigger endpoint
- [ ] Test rate limiting responses
- [ ] Test error handling

### Main Application

#### 2.9 Implement Main Application Entry Point
**File:** `GCBroadcastScheduler-10-26/main.py`

- [ ] Create `main.py` file
- [ ] Import required dependencies:
  - [ ] `os`
  - [ ] `logging`
  - [ ] `flask` (Flask, request, jsonify)
  - [ ] All custom modules
- [ ] Initialize logging configuration
- [ ] Create Flask app instance
- [ ] Initialize all components in correct order:
  - [ ] ConfigManager
  - [ ] DatabaseManager
  - [ ] TelegramClient
  - [ ] BroadcastTracker
  - [ ] BroadcastScheduler
  - [ ] BroadcastExecutor
  - [ ] BroadcastWebAPI
- [ ] Register API blueprint
- [ ] Implement main endpoints:
  - [ ] `GET /health` - Health check endpoint
  - [ ] `POST /api/broadcast/execute` - Scheduler trigger endpoint
- [ ] Implement `/api/broadcast/execute` logic:
  - [ ] Get due broadcasts from scheduler
  - [ ] Execute batch via executor
  - [ ] Return execution summary
- [ ] Add request logging middleware
- [ ] Add error handling middleware
- [ ] Configure Flask app for production
- [ ] Add `if __name__ == "__main__"` block for local testing

**Testing:**
- [ ] Create `tests/test_main.py`
- [ ] Test Flask app initialization
- [ ] Test /health endpoint
- [ ] Test /api/broadcast/execute endpoint
- [ ] Test integration of all components

### Deployment Configuration

#### 2.10 Create Requirements File
**File:** `GCBroadcastScheduler-10-26/requirements.txt`

- [ ] Add Python dependencies:
  - [ ] `flask>=2.3.0`
  - [ ] `gunicorn>=21.0.0`
  - [ ] `google-cloud-secret-manager>=2.16.0`
  - [ ] `psycopg2-binary>=2.9.0`
  - [ ] `python-telegram-bot>=20.0`
  - [ ] `PyJWT>=2.8.0`
- [ ] Pin all versions for reproducibility
- [ ] Test installation: `pip install -r requirements.txt`

#### 2.11 Create Dockerfile
**File:** `GCBroadcastScheduler-10-26/Dockerfile`

- [ ] Create Dockerfile with multi-stage build
- [ ] Use official Python 3.11 slim base image
- [ ] Set working directory to /app
- [ ] Copy requirements.txt first (layer caching)
- [ ] Install dependencies
- [ ] Copy application code
- [ ] Set environment variables (PORT=8080)
- [ ] Expose port 8080
- [ ] Use gunicorn as production server
- [ ] Add health check configuration
- [ ] Optimize image size (remove build dependencies)

#### 2.12 Create .dockerignore
**File:** `GCBroadcastScheduler-10-26/.dockerignore`

- [ ] Add entries:
  - [ ] `__pycache__/`
  - [ ] `*.pyc`
  - [ ] `.env`
  - [ ] `.git/`
  - [ ] `tests/`
  - [ ] `*.md`
  - [ ] `.dockerignore`
  - [ ] `Dockerfile`

#### 2.13 Create Environment Example
**File:** `GCBroadcastScheduler-10-26/.env.example`

- [ ] Document all required environment variables:
  - [ ] BOT_TOKEN_SECRET
  - [ ] BOT_USERNAME_SECRET
  - [ ] DATABASE_HOST_SECRET
  - [ ] DATABASE_NAME_SECRET
  - [ ] DATABASE_USER_SECRET
  - [ ] DATABASE_PASSWORD_SECRET
  - [ ] BROADCAST_AUTO_INTERVAL_SECRET
  - [ ] BROADCAST_MANUAL_INTERVAL_SECRET
  - [ ] JWT_SECRET_KEY_SECRET
- [ ] Add comments explaining each variable
- [ ] Add example Secret Manager paths

### Documentation

#### 2.14 Update Documentation
- [ ] Update PROGRESS.md with Phase 2 completion
- [ ] Document module structure in comments
- [ ] Create module interaction diagram (optional)
- [ ] Update DECISIONS.md if any design decisions changed

---

## Phase 3: Secret Manager Setup
**Goal:** Create and configure Google Cloud secrets
**Duration:** 1 day
**Dependencies:** None (can run in parallel with Phase 2)

### Create Secrets

#### 3.1 Create Broadcast Interval Secrets
- [ ] Create BROADCAST_AUTO_INTERVAL secret:
  ```bash
  echo "24" | gcloud secrets create BROADCAST_AUTO_INTERVAL \
      --project=telepay-459221 \
      --replication-policy="automatic" \
      --data-file=-
  ```
- [ ] Verify secret created:
  ```bash
  gcloud secrets describe BROADCAST_AUTO_INTERVAL --project=telepay-459221
  ```
- [ ] Create BROADCAST_MANUAL_INTERVAL secret:
  ```bash
  echo "0.0833" | gcloud secrets create BROADCAST_MANUAL_INTERVAL \
      --project=telepay-459221 \
      --replication-policy="automatic" \
      --data-file=-
  ```
- [ ] Verify secret created:
  ```bash
  gcloud secrets describe BROADCAST_MANUAL_INTERVAL --project=telepay-459221
  ```

### Grant Access

#### 3.2 Grant Service Account Access
- [ ] Grant access to BROADCAST_AUTO_INTERVAL:
  ```bash
  gcloud secrets add-iam-policy-binding BROADCAST_AUTO_INTERVAL \
      --project=telepay-459221 \
      --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
  ```
- [ ] Grant access to BROADCAST_MANUAL_INTERVAL:
  ```bash
  gcloud secrets add-iam-policy-binding BROADCAST_MANUAL_INTERVAL \
      --project=telepay-459221 \
      --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
  ```

### Verification

#### 3.3 Test Secret Access
- [ ] Test accessing BROADCAST_AUTO_INTERVAL:
  ```bash
  gcloud secrets versions access latest --secret=BROADCAST_AUTO_INTERVAL --project=telepay-459221
  ```
- [ ] Test accessing BROADCAST_MANUAL_INTERVAL:
  ```bash
  gcloud secrets versions access latest --secret=BROADCAST_MANUAL_INTERVAL --project=telepay-459221
  ```
- [ ] Verify service account has access (no permission errors)

### Documentation

#### 3.4 Create Secret Management Scripts
- [ ] Create `TOOLS_SCRIPTS_TESTS/scripts/create_broadcast_secrets.sh`
- [ ] Add secret creation commands
- [ ] Add IAM policy binding commands
- [ ] Add verification commands
- [ ] Make script executable: `chmod +x create_broadcast_secrets.sh`
- [ ] Test script execution

#### 3.5 Update Documentation
- [ ] Update PROGRESS.md with Phase 3 completion
- [ ] Document secret names and purposes in DECISIONS.md
- [ ] Add instructions for updating secret values

---

## Phase 4: Cloud Run Deployment
**Goal:** Deploy GCBroadcastScheduler-10-26 to Cloud Run
**Duration:** 1-2 days
**Dependencies:** Phase 2 (Service Development), Phase 3 (Secret Manager)

### Deployment Script

#### 4.1 Create Deployment Script
**File:** `TOOLS_SCRIPTS_TESTS/scripts/deploy_broadcast_scheduler.sh`

- [ ] Create deployment script
- [ ] Set project and region variables
- [ ] Add gcloud run deploy command with:
  - [ ] `--source=./GCBroadcastScheduler-10-26`
  - [ ] `--region=us-central1`
  - [ ] `--platform=managed`
  - [ ] `--allow-unauthenticated`
  - [ ] `--min-instances=0`
  - [ ] `--max-instances=1`
  - [ ] `--memory=512Mi`
  - [ ] `--cpu=1`
  - [ ] `--timeout=300s`
  - [ ] `--concurrency=1`
- [ ] Add all environment variables (secret paths)
- [ ] Add success/failure messages
- [ ] Make script executable: `chmod +x deploy_broadcast_scheduler.sh`

### Initial Deployment

#### 4.2 Execute Initial Deployment
- [ ] Review deployment script for correctness
- [ ] Execute deployment:
  ```bash
  ./TOOLS_SCRIPTS_TESTS/scripts/deploy_broadcast_scheduler.sh
  ```
- [ ] Wait for deployment to complete
- [ ] Note the service URL (e.g., https://gcbroadcastscheduler-10-26-...-uc.a.run.app)
- [ ] Save service URL for Cloud Scheduler configuration

### Verification

#### 4.3 Test Health Endpoint
- [ ] Test health endpoint:
  ```bash
  curl https://gcbroadcastscheduler-10-26-291176869049.us-central1.run.app/health
  ```
- [ ] Verify response: `{"status": "healthy"}`
- [ ] Check response time is reasonable

#### 4.4 Test Database Connectivity
- [ ] Check Cloud Run logs for database connection:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcbroadcastscheduler-10-26" --limit=50
  ```
- [ ] Verify no database connection errors
- [ ] Verify Secret Manager access working (no credential errors)

#### 4.5 Test Manual Execution (Direct POST)
- [ ] Test execute endpoint manually:
  ```bash
  curl -X POST https://gcbroadcastscheduler-10-26-291176869049.us-central1.run.app/api/broadcast/execute \
       -H "Content-Type: application/json" \
       -d '{"source":"manual_test"}'
  ```
- [ ] Check response for execution summary
- [ ] Check Cloud Run logs for execution details
- [ ] Verify no critical errors

### Configuration Review

#### 4.6 Review Service Configuration
- [ ] Verify environment variables set correctly:
  ```bash
  gcloud run services describe gcbroadcastscheduler-10-26 --region=us-central1 --format="yaml(spec.template.spec.containers[0].env)"
  ```
- [ ] Verify min/max instances
- [ ] Verify memory and CPU allocation
- [ ] Verify timeout setting
- [ ] Verify concurrency setting

### Documentation

#### 4.7 Update Documentation
- [ ] Update PROGRESS.md with Phase 4 completion
- [ ] Document service URL
- [ ] Document deployment process
- [ ] Add troubleshooting notes if issues encountered

---

## Phase 5: Cloud Scheduler Setup
**Goal:** Configure Cloud Scheduler to trigger daily broadcasts
**Duration:** 1 day
**Dependencies:** Phase 4 (Cloud Run Deployment)

### Scheduler Configuration

#### 5.1 Create Cloud Scheduler Job
- [ ] Create scheduler job:
  ```bash
  gcloud scheduler jobs create http broadcast-scheduler-daily \
      --location=us-central1 \
      --schedule="0 0 * * *" \
      --uri="https://gcbroadcastscheduler-10-26-291176869049.us-central1.run.app/api/broadcast/execute" \
      --http-method=POST \
      --oidc-service-account-email="291176869049-compute@developer.gserviceaccount.com" \
      --oidc-token-audience="https://gcbroadcastscheduler-10-26-291176869049.us-central1.run.app" \
      --headers="Content-Type=application/json" \
      --message-body='{"source":"cloud_scheduler"}' \
      --time-zone="UTC"
  ```
- [ ] Verify job created:
  ```bash
  gcloud scheduler jobs describe broadcast-scheduler-daily --location=us-central1
  ```

### Testing

#### 5.2 Test Manual Trigger
- [ ] Manually trigger the scheduler job:
  ```bash
  gcloud scheduler jobs run broadcast-scheduler-daily --location=us-central1
  ```
- [ ] Check execution status:
  ```bash
  gcloud scheduler jobs describe broadcast-scheduler-daily --location=us-central1
  ```
- [ ] Verify last run time updated
- [ ] Verify state = "ENABLED"

#### 5.3 Verify Cloud Run Invocation
- [ ] Check Cloud Run logs for scheduler invocation:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcbroadcastscheduler-10-26 AND jsonPayload.source=\"cloud_scheduler\"" --limit=10
  ```
- [ ] Verify request received from scheduler
- [ ] Verify OIDC authentication succeeded
- [ ] Verify broadcasts executed
- [ ] Check for any errors in execution

### Documentation

#### 5.4 Create Scheduler Management Scripts
- [ ] Create script to pause scheduler (maintenance):
  ```bash
  # pause_broadcast_scheduler.sh
  gcloud scheduler jobs pause broadcast-scheduler-daily --location=us-central1
  ```
- [ ] Create script to resume scheduler:
  ```bash
  # resume_broadcast_scheduler.sh
  gcloud scheduler jobs resume broadcast-scheduler-daily --location=us-central1
  ```
- [ ] Make scripts executable

#### 5.5 Update Documentation
- [ ] Update PROGRESS.md with Phase 5 completion
- [ ] Document scheduler configuration
- [ ] Document how to pause/resume broadcasts
- [ ] Add troubleshooting guide for scheduler issues

---

## Phase 6: Website Integration
**Goal:** Add manual broadcast trigger functionality to client dashboard
**Duration:** 2-3 days
**Dependencies:** Phase 4 (Cloud Run Deployment)

### Backend API Integration

#### 6.1 Add Broadcast API Client to GCRegisterWeb
**File:** `GCRegisterWeb-10-26/src/api/broadcastApi.ts` (or similar)

- [ ] Create broadcast API client module
- [ ] Implement API functions:
  - [ ] `triggerBroadcast(broadcastId, token)` - POST /api/broadcast/trigger
  - [ ] `getBroadcastStatus(broadcastId, token)` - GET /api/broadcast/status/:id
- [ ] Add error handling for:
  - [ ] 401 Unauthorized
  - [ ] 429 Rate Limited
  - [ ] 500 Internal Server Error
- [ ] Add TypeScript interfaces for request/response types
- [ ] Add JSDoc comments

### Frontend UI Components

#### 6.2 Add Broadcast Controls to Dashboard
**File:** `GCRegisterWeb-10-26/src/components/BroadcastControls.tsx` (or similar)

- [ ] Create BroadcastControls component
- [ ] Add "Resend Messages" button for each channel pair
- [ ] Implement button click handler:
  - [ ] Call triggerBroadcast API
  - [ ] Handle success (show success message)
  - [ ] Handle rate limit (show countdown timer)
  - [ ] Handle errors (show error message)
- [ ] Add loading state indicator
- [ ] Add confirmation dialog before triggering
- [ ] Add rate limit countdown display
- [ ] Style component consistently with existing design

#### 6.3 Add Broadcast Status Display
- [ ] Create BroadcastStatus component (optional)
- [ ] Display last broadcast time
- [ ] Display next scheduled broadcast time
- [ ] Display broadcast statistics (total, successful, failed)
- [ ] Add refresh button to update status
- [ ] Add loading skeleton for status fetch

### Dashboard Integration

#### 6.4 Integrate into Main Dashboard
**File:** `GCRegisterWeb-10-26/src/pages/DashboardPage.tsx` (or similar)

- [ ] Import BroadcastControls component
- [ ] Add BroadcastControls to channel list view
- [ ] Pass broadcast_id from channel data to component
- [ ] Ensure JWT token passed for authentication
- [ ] Test responsive design (mobile, tablet, desktop)

### User Feedback

#### 6.5 Add User Notifications
- [ ] Add toast/notification system (if not already present)
- [ ] Show success notification on successful trigger
- [ ] Show error notification on failure
- [ ] Show rate limit notification with countdown
- [ ] Add sound/visual feedback (optional)

### Documentation

#### 6.6 Update User Documentation
- [ ] Create user guide for manual broadcast trigger
- [ ] Add screenshots of broadcast controls
- [ ] Document rate limiting behavior
- [ ] Add FAQ section for common issues

#### 6.7 Update Technical Documentation
- [ ] Update PROGRESS.md with Phase 6 completion
- [ ] Document frontend-backend integration
- [ ] Add API usage examples

---

## Phase 7: Monitoring & Testing
**Goal:** Set up comprehensive monitoring and execute full system tests
**Duration:** 2-3 days
**Dependencies:** Phase 5 (Cloud Scheduler), Phase 6 (Website Integration)

### Logging Configuration

#### 7.1 Configure Cloud Logging Queries
- [ ] Create saved query for failed broadcasts:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbroadcastscheduler-10-26"
  severity="ERROR"
  textPayload=~"Broadcast.*failed"
  ```
- [ ] Create saved query for rate limit violations:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbroadcastscheduler-10-26"
  textPayload=~"Rate limit"
  ```
- [ ] Create saved query for execution statistics:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbroadcastscheduler-10-26"
  textPayload=~"Batch complete"
  ```

### Monitoring Dashboards

#### 7.2 Create Cloud Monitoring Dashboard
- [ ] Create custom dashboard "Broadcast Manager Monitoring"
- [ ] Add charts:
  - [ ] Request count by endpoint
  - [ ] Request latency (p50, p95, p99)
  - [ ] Error rate
  - [ ] Broadcast success rate
  - [ ] Broadcast failure rate
  - [ ] Active broadcasts count
  - [ ] Rate limit violations count
- [ ] Add log panels for recent errors
- [ ] Save dashboard

### Alerting

#### 7.3 Configure Alerting Policies
- [ ] Create alert: High Failure Rate
  - [ ] Condition: Failed broadcasts > 10% in 1 hour
  - [ ] Notification: Email to admin
- [ ] Create alert: Service Unavailable
  - [ ] Condition: 5xx errors > 5 in 5 minutes
  - [ ] Notification: Email to admin
- [ ] Create alert: Scheduler Job Failed
  - [ ] Condition: Cloud Scheduler job fails 3 times consecutively
  - [ ] Notification: Email to admin
- [ ] Test alerts by simulating failures

### Integration Testing

#### 7.4 End-to-End Testing - Automated Broadcast
- [ ] Wait for scheduled broadcast (or manually trigger Cloud Scheduler)
- [ ] Monitor execution in Cloud Run logs
- [ ] Verify broadcasts sent to Telegram channels:
  - [ ] Check open channels for subscription messages
  - [ ] Check closed channels for donation messages
- [ ] Verify database updates:
  - [ ] last_sent_time updated
  - [ ] next_send_time updated (NOW + 24h)
  - [ ] broadcast_status = 'completed'
  - [ ] Statistics incremented
- [ ] Check for any errors in logs

#### 7.5 End-to-End Testing - Manual Trigger
- [ ] Login to website as test user
- [ ] Navigate to dashboard
- [ ] Click "Resend Messages" button
- [ ] Verify broadcast triggered immediately
- [ ] Verify rate limit enforced on second click
- [ ] Wait 5 minutes and verify can trigger again
- [ ] Check database for manual_trigger_count increment
- [ ] Check last_manual_trigger_time updated

#### 7.6 Failure Scenario Testing
- [ ] Test with invalid channel ID (expect failure tracking)
- [ ] Test with bot removed from channel (expect Forbidden error)
- [ ] Verify consecutive_failures incremented
- [ ] Verify is_active set to false after 5 failures
- [ ] Test failure notifications (if implemented)

#### 7.7 Rate Limiting Testing
- [ ] Test automated broadcast rate limit (next_send_time enforcement)
- [ ] Test manual trigger rate limit (5 minutes)
- [ ] Test API returns 429 status code correctly
- [ ] Test retry_after_seconds calculation accurate

#### 7.8 Security Testing
- [ ] Test API authentication:
  - [ ] Invalid JWT token (expect 401)
  - [ ] Expired JWT token (expect 401)
  - [ ] Missing Authorization header (expect 401)
- [ ] Test authorization:
  - [ ] User A tries to trigger User B's broadcast (expect 403 or 404)
  - [ ] Verify ownership checks work
- [ ] Test SQL injection prevention:
  - [ ] Send malicious broadcast_id values
  - [ ] Verify parameterized queries prevent injection

#### 7.9 Load Testing
- [ ] Test with multiple broadcasts scheduled simultaneously
- [ ] Monitor Cloud Run resource usage (CPU, memory)
- [ ] Verify concurrency=1 prevents overlapping executions
- [ ] Check execution time for large batch (e.g., 50+ broadcasts)
- [ ] Verify timeout (300s) is sufficient

### Documentation

#### 7.10 Update Documentation
- [ ] Update PROGRESS.md with Phase 7 completion
- [ ] Document monitoring setup
- [ ] Document alert policies
- [ ] Create troubleshooting runbook for common issues
- [ ] Document test results and findings

---

## Phase 8: Decommission Old System
**Goal:** Remove old broadcast code and finalize migration
**Duration:** 1 day
**Dependencies:** Phase 7 (Monitoring & Testing - all tests passed)

### Code Cleanup

#### 8.1 Disable Old Broadcast Calls
**File:** `TelePay10-26/app_initializer.py`

- [ ] Comment out or remove broadcast calls:
  ```python
  # OLD CODE TO REMOVE:
  # self.broadcast_manager.fetch_open_channel_list()
  # self.broadcast_manager.broadcast_hash_links()

  # OLD CODE TO REMOVE (closed channel broadcasts):
  # result = asyncio.run(self.closed_channel_manager.send_donation_message_to_closed_channels())
  ```
- [ ] Add comment explaining why removed (migrated to scheduled service)
- [ ] Test TelePay10-26 startup (should work without broadcasts)

#### 8.2 Archive Old Broadcast Code
- [ ] Create archive directory: `OCTOBER/ARCHIVES/BroadcastManager-Legacy/`
- [ ] Move old files to archive:
  - [ ] `TelePay10-26/broadcast_manager.py` → archive
  - [ ] `TelePay10-26/closed_channel_manager.py` → archive (if fully replaced)
- [ ] Add README in archive explaining:
  - [ ] Why archived
  - [ ] When archived
  - [ ] What replaced it (link to new service)
  - [ ] How to restore if needed (rollback procedure)

### Verification

#### 8.3 Verify System Operation Without Old Code
- [ ] Test TelePay10-26 application startup:
  - [ ] No errors on initialization
  - [ ] Other functions work normally
  - [ ] No broadcast messages sent on startup
- [ ] Verify new system handling all broadcasts:
  - [ ] Check Cloud Scheduler executing daily
  - [ ] Check broadcasts being sent correctly
  - [ ] Check database tracking working
  - [ ] Check manual triggers working from website

#### 8.4 Final Database Verification
- [ ] Query broadcast_manager table:
  - [ ] Verify all channels have entries
  - [ ] Verify last_sent_time being updated
  - [ ] Verify next_send_time being calculated correctly
  - [ ] Verify statistics accumulating
- [ ] Check for orphaned data or inconsistencies

### Documentation

#### 8.5 Final Documentation Update
- [ ] Update PROGRESS.md with Phase 8 completion
- [ ] Mark BROADCAST_MANAGER_ARCHITECTURE.md as "Implemented"
- [ ] Update main README (if exists) with new architecture
- [ ] Document rollback procedure (if needed to revert to old system)
- [ ] Add deployment date to DECISIONS.md
- [ ] Create migration completion report:
  - [ ] What was migrated
  - [ ] What changed
  - [ ] Performance improvements
  - [ ] Issues encountered and resolved
  - [ ] Lessons learned

---

## Post-Implementation

### Monitoring Period

#### Week 1-2 Post-Deployment
- [ ] Monitor Cloud Run logs daily for errors
- [ ] Monitor broadcast success rate
- [ ] Monitor rate limit violations
- [ ] Monitor Cloud Run resource usage
- [ ] Review alert notifications (if any)
- [ ] Gather user feedback on manual trigger feature

### Optimization

#### Performance Review
- [ ] Review execution times for broadcasts
- [ ] Optimize slow queries (if any)
- [ ] Adjust Cloud Run resources if needed (CPU/memory)
- [ ] Consider increasing max_instances if needed
- [ ] Review and optimize Telegram API rate limiting

### Feature Enhancements (Future)

#### Potential Improvements
- [ ] Add broadcast preview feature (see message before sending)
- [ ] Add broadcast scheduling (send at specific time)
- [ ] Add broadcast templates (customize messages)
- [ ] Add broadcast analytics dashboard
- [ ] Add broadcast A/B testing
- [ ] Add multi-language support for messages
- [ ] Add broadcast audience targeting

---

## Checklist Summary

### Phase Completion Tracking

| Phase | Total Tasks | Status | Notes |
|-------|-------------|--------|-------|
| Phase 1: Database Setup | 8 | ⬜ Not Started | |
| Phase 2: Service Development | 27 | ⬜ Not Started | Core implementation |
| Phase 3: Secret Manager Setup | 6 | ⬜ Not Started | |
| Phase 4: Cloud Run Deployment | 8 | ⬜ Not Started | |
| Phase 5: Cloud Scheduler Setup | 5 | ⬜ Not Started | |
| Phase 6: Website Integration | 7 | ⬜ Not Started | |
| Phase 7: Monitoring & Testing | 10 | ⬜ Not Started | Critical before launch |
| Phase 8: Decommission Old System | 5 | ⬜ Not Started | Final step |
| **TOTAL** | **76** | **0%** | |

---

## Success Criteria

### Must Have (Phase 1-5)
- ✅ Database table created and populated
- ✅ All 5 modular components implemented and tested
- ✅ Cloud Run service deployed and healthy
- ✅ Cloud Scheduler triggering daily broadcasts
- ✅ Automated broadcasts working correctly

### Should Have (Phase 6-7)
- ✅ Website manual trigger functional
- ✅ Rate limiting enforced correctly
- ✅ Monitoring dashboards created
- ✅ Alert policies configured
- ✅ All tests passing

### Nice to Have (Phase 8 and Post)
- ✅ Old system decommissioned cleanly
- ✅ Documentation complete and accurate
- ✅ User feedback positive
- ✅ Performance optimized

---

## Rollback Plan

If critical issues are discovered after deployment:

1. **Immediate Rollback (Emergency)**
   - [ ] Pause Cloud Scheduler: `gcloud scheduler jobs pause broadcast-scheduler-daily --location=us-central1`
   - [ ] Restore old broadcast code in `app_initializer.py`
   - [ ] Redeploy TelePay10-26 with old code
   - [ ] Verify broadcasts resume from TelePay startup

2. **Database Rollback**
   - [ ] Run rollback script: `TOOLS_SCRIPTS_TESTS/scripts/rollback_broadcast_manager_table.sql`
   - [ ] Verify table dropped
   - [ ] Restore from backup if data loss occurred

3. **Investigate and Fix**
   - [ ] Review logs to identify root cause
   - [ ] Fix issues in new system
   - [ ] Test fixes thoroughly
   - [ ] Redeploy when ready

---

## Notes and Best Practices

### Modular Code Structure
- **One module = One responsibility**: Each Python file should have a single, clear purpose
- **Avoid god objects**: Don't put all logic in one class or file
- **Use dependency injection**: Pass dependencies via constructors for testability
- **Keep functions small**: Each function should do one thing well
- **Use type hints**: Make code self-documenting with proper type annotations

### Testing Strategy
- **Test each module independently**: Unit tests for each component
- **Mock external dependencies**: Use mocks for database, Telegram API, Secret Manager
- **Test error cases**: Don't just test happy paths
- **Integration tests last**: After all units tested, test full integration

### Deployment Strategy
- **Deploy to test environment first**: If available, test in non-production
- **Monitor closely after deployment**: Watch logs for first 24-48 hours
- **Have rollback plan ready**: Know how to revert quickly if needed
- **Deploy during low-traffic period**: Minimize impact if issues occur

### Security Best Practices
- **Never hardcode secrets**: Always use Secret Manager
- **Use parameterized queries**: Prevent SQL injection
- **Validate all inputs**: Never trust user input
- **Use HTTPS everywhere**: Encrypt all network traffic
- **Principle of least privilege**: Grant minimum necessary permissions

---

**End of Checklist**

**Good luck with the implementation! 🚀**
