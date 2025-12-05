# GCBroadcastService Refactoring Implementation Checklist
## Converting GCBroadcastScheduler-10-26 to Independent Webhook Service

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Implementation Checklist
**Parent Document:** GCBroadcastService_REFACTORING_ARCHITECTURE.md
**Estimated Total Time:** 7-9 hours

---

## 📋 Overview

This checklist ensures the proper refactoring of **GCBroadcastScheduler-10-26** into **GCBroadcastService-10-26** with:
- ✅ Self-contained modules (no shared dependencies)
- ✅ Modular code structure (clear separation of concerns)
- ✅ Independent deployment capability
- ✅ All existing functionality preserved

---

## Phase 1: Project Setup & Directory Structure
**Estimated Time:** 30 minutes

### 1.1 Create Base Directory Structure
- [ ] Create new service directory: `GCBroadcastService-10-26/`
- [ ] Create subdirectories:
  - [ ] `routes/`
  - [ ] `services/`
  - [ ] `clients/`
  - [ ] `utils/`
  - [ ] `models/` (optional, for type hints)
  - [ ] `tests/`

### 1.2 Copy Core Configuration Files
- [ ] Copy `Dockerfile` from GCBroadcastScheduler-10-26 (no changes needed)
- [ ] Copy `requirements.txt` (no changes needed)
- [ ] Copy `.dockerignore` (no changes needed)
- [ ] Create `.env.example` with all required environment variables
- [ ] Create `README.md` with service documentation

### 1.3 Create Package Initializers
- [ ] Create `routes/__init__.py`
- [ ] Create `services/__init__.py`
- [ ] Create `clients/__init__.py`
- [ ] Create `utils/__init__.py`
- [ ] Create `models/__init__.py`
- [ ] Create `tests/__init__.py`

---

## Phase 2: Utility Modules (Self-Contained)
**Estimated Time:** 1-1.5 hours

### 2.1 Configuration Module (utils/config.py)
**Purpose:** Centralized Secret Manager access, self-contained configuration
**Dependencies:** google-cloud-secret-manager

- [ ] Create `utils/config.py`
- [ ] Implement `Config` class with:
  - [ ] `__init__()` - Initialize Secret Manager client
  - [ ] `_fetch_secret()` - Generic secret fetching with caching
  - [ ] `get_broadcast_auto_interval()` - Default: 24 hours
  - [ ] `get_broadcast_manual_interval()` - Default: 0.0833 hours (5 minutes)
  - [ ] `get_bot_token()` - Required
  - [ ] `get_bot_username()` - Required
  - [ ] `get_jwt_secret_key()` - Required
  - [ ] `get_database_host()`
  - [ ] `get_database_name()`
  - [ ] `get_database_user()`
  - [ ] `get_database_password()`
  - [ ] `get_cloud_sql_connection_name()`
  - [ ] `to_dict()` - Convert to Flask config format
  - [ ] `clear_cache()` - For testing
- [ ] Add secret caching mechanism (dict)
- [ ] Add error handling with default fallbacks
- [ ] Add logging for secret access attempts

### 2.2 Authentication Utilities (utils/auth.py)
**Purpose:** JWT authentication helpers
**Dependencies:** flask-jwt-extended

- [ ] Create `utils/auth.py`
- [ ] Implement `extract_client_id()` function:
  - [ ] Use `get_jwt_identity()` from Flask-JWT-Extended
  - [ ] Validate identity is not None
  - [ ] Return client_id or None
  - [ ] Add error logging
- [ ] Add type hints for function signatures

### 2.3 Logging Utilities (utils/logging_utils.py)
**Purpose:** Structured logging setup
**Dependencies:** logging (built-in)

- [ ] Create `utils/logging_utils.py`
- [ ] Implement `setup_logging()` function:
  - [ ] Configure basicConfig with timestamp, name, level, message format
  - [ ] Set level to INFO by default
  - [ ] Silence noisy loggers (google, urllib3, werkzeug)
  - [ ] Stream to stdout for Cloud Run

---

## Phase 3: Client Modules (External API Wrappers)
**Estimated Time:** 1-1.5 hours

### 3.1 Telegram Client (clients/telegram_client.py)
**Purpose:** Telegram Bot API wrapper for sending messages
**Dependencies:** requests

- [ ] Copy `telegram_client.py` from GCBroadcastScheduler-10-26 to `clients/telegram_client.py`
- [ ] Verify `TelegramClient` class contains:
  - [ ] `__init__(bot_token, bot_username)` - Initialize with bot credentials
  - [ ] `encode_id(channel_id)` - Base64 encoding for deep links
  - [ ] `send_subscription_message(chat_id, open_title, open_desc, closed_title, closed_desc, tier_buttons)`
  - [ ] `send_donation_message(chat_id, donation_message, open_channel_id)`
- [ ] Verify bot connection test in `__init__()` (getMe call)
- [ ] Verify error handling for HTTP errors (403, 400, network errors)
- [ ] Verify message length validation (4096 chars for Telegram)
- [ ] Verify callback_data length validation (64 bytes for Telegram)
- [ ] Verify tier emoji mapping (1: 🥇, 2: 🥈, 3: 🥉)
- [ ] No changes needed if all checks pass

### 3.2 Database Client (clients/database_client.py)
**Purpose:** PostgreSQL operations via Cloud SQL Connector
**Dependencies:** cloud-sql-python-connector, psycopg2-binary

- [ ] Copy `database_manager.py` from GCBroadcastScheduler-10-26 to `clients/database_client.py`
- [ ] Rename class from `DatabaseManager` to `DatabaseClient` (for consistency)
- [ ] Update all references in copied code
- [ ] Verify `DatabaseClient` class contains:
  - [ ] `__init__(config)` - Initialize with Config instance
  - [ ] `get_connection()` - Context manager for Cloud SQL connections
  - [ ] `fetch_due_broadcasts()` - JOIN with main_clients_database
  - [ ] `fetch_broadcast_by_id(broadcast_id)`
  - [ ] `update_broadcast_status(broadcast_id, status)`
  - [ ] `update_broadcast_success(broadcast_id, next_send_time)`
  - [ ] `update_broadcast_failure(broadcast_id, error_message)`
  - [ ] `get_manual_trigger_info(broadcast_id)` - For rate limiting
  - [ ] `queue_manual_broadcast(broadcast_id)` - Set next_send_time = NOW()
  - [ ] `get_broadcast_statistics(broadcast_id)` - For API responses
- [ ] Verify Cloud SQL Connector initialization with pg8000
- [ ] Verify all SQL queries match architecture document
- [ ] Verify context manager pattern for connections
- [ ] Update constructor to accept `config` instead of `config_manager`

---

## Phase 4: Service Modules (Business Logic)
**Estimated Time:** 1.5-2 hours

### 4.1 Broadcast Scheduler Service (services/broadcast_scheduler.py)
**Purpose:** Determine which broadcasts are due, enforce rate limiting
**Dependencies:** clients.database_client, utils.config

- [ ] Copy `broadcast_scheduler.py` from GCBroadcastScheduler-10-26 to `services/broadcast_scheduler.py`
- [ ] Update constructor parameter:
  - [ ] Change `DatabaseManager` to `DatabaseClient`
  - [ ] Change `ConfigManager` to `Config`
- [ ] Update all internal references (`self.db` instead of `self.db_manager`)
- [ ] Verify `BroadcastScheduler` class contains:
  - [ ] `__init__(db_client, config)` - Accept DatabaseClient and Config
  - [ ] `get_due_broadcasts()` - Delegate to DatabaseClient
  - [ ] `check_manual_trigger_rate_limit(broadcast_id, client_id)`:
    - [ ] Fetch manual interval from config
    - [ ] Get last trigger time from database
    - [ ] Verify ownership (client_id match)
    - [ ] Check if time_since_last < manual_interval
    - [ ] Return {'allowed': bool, 'reason': str, 'retry_after_seconds': int}
  - [ ] `queue_manual_broadcast(broadcast_id)` - Delegate to DatabaseClient
  - [ ] `calculate_next_send_time()` - Use config.get_broadcast_auto_interval()
- [ ] Ensure timezone-aware datetime handling (timezone.utc)
- [ ] Verify authorization checks are in place

### 4.2 Broadcast Executor Service (services/broadcast_executor.py)
**Purpose:** Execute broadcasts by sending messages to Telegram
**Dependencies:** clients.telegram_client, services.broadcast_tracker

- [ ] Copy `broadcast_executor.py` from GCBroadcastScheduler-10-26 to `services/broadcast_executor.py`
- [ ] No class name changes needed
- [ ] Verify `BroadcastExecutor` class contains:
  - [ ] `__init__(telegram_client, broadcast_tracker)` - Accept both clients
  - [ ] `execute_broadcast(broadcast_entry)`:
    - [ ] Mark as 'in_progress' via tracker
    - [ ] Send subscription message to open channel
    - [ ] Send donation message to closed channel
    - [ ] Mark as success/failure via tracker
    - [ ] Return {'success': bool, 'open_channel_sent': bool, 'closed_channel_sent': bool, 'errors': List[str]}
  - [ ] `_send_subscription_message(broadcast_entry)`:
    - [ ] Extract channel details from entry
    - [ ] Build tier_buttons list from sub_1/2/3 prices and times
    - [ ] Call telegram_client.send_subscription_message()
    - [ ] Return {'success': bool, 'error': str}
  - [ ] `_send_donation_message(broadcast_entry)`:
    - [ ] Extract donation message and channel IDs
    - [ ] Call telegram_client.send_donation_message()
    - [ ] Return {'success': bool, 'error': str}
  - [ ] `execute_batch(broadcast_entries)`:
    - [ ] Loop through entries
    - [ ] Execute each broadcast
    - [ ] Collect statistics (total, successful, failed)
    - [ ] Return batch results
- [ ] Verify error handling for all Telegram API calls
- [ ] Verify both channels must succeed for overall success

### 4.3 Broadcast Tracker Service (services/broadcast_tracker.py)
**Purpose:** Track broadcast state and update database
**Dependencies:** clients.database_client, utils.config

- [ ] Copy `broadcast_tracker.py` from GCBroadcastScheduler-10-26 to `services/broadcast_tracker.py`
- [ ] Update constructor parameter:
  - [ ] Change `DatabaseManager` to `DatabaseClient`
  - [ ] Change `ConfigManager` to `Config`
- [ ] Verify `BroadcastTracker` class contains:
  - [ ] `__init__(db_client, config)` - Accept DatabaseClient and Config
  - [ ] `update_status(broadcast_id, status)` - Delegate to DatabaseClient
  - [ ] `mark_success(broadcast_id)`:
    - [ ] Calculate next_send_time using config.get_broadcast_auto_interval()
    - [ ] Call db_client.update_broadcast_success()
    - [ ] Log success with next send time
  - [ ] `mark_failure(broadcast_id, error_message)`:
    - [ ] Truncate error_message if > 500 chars
    - [ ] Call db_client.update_broadcast_failure()
    - [ ] Log failure
  - [ ] `reset_consecutive_failures(broadcast_id)`:
    - [ ] Update consecutive_failures = 0
    - [ ] Set is_active = true
    - [ ] Log reset action
- [ ] Verify auto-disable logic (consecutive_failures >= 5)
- [ ] Update all internal references

---

## Phase 5: Route Modules (HTTP Endpoints)
**Estimated Time:** 1.5-2 hours

### 5.1 Broadcast Execution Routes (routes/broadcast_routes.py)
**Purpose:** Handle automated broadcast execution (Cloud Scheduler)
**Dependencies:** services.*, clients.*, utils.config

- [ ] Create `routes/broadcast_routes.py`
- [ ] Define Flask Blueprint: `broadcast_bp = Blueprint('broadcast', __name__)`
- [ ] Initialize components (singleton pattern):
  - [ ] `config = Config()`
  - [ ] `db_client = DatabaseClient(config)`
  - [ ] `telegram_client = TelegramClient(config.get_bot_token(), config.get_bot_username())`
  - [ ] `broadcast_tracker = BroadcastTracker(db_client, config)`
  - [ ] `broadcast_scheduler = BroadcastScheduler(db_client, config)`
  - [ ] `broadcast_executor = BroadcastExecutor(telegram_client, broadcast_tracker)`
- [ ] Implement endpoints:
  - [ ] `GET /health`:
    - [ ] Return {'status': 'healthy', 'service': 'GCBroadcastService-10-26', 'timestamp': ISO8601}
    - [ ] Status code: 200
  - [ ] `POST /api/broadcast/execute`:
    - [ ] Extract optional 'source' from request body
    - [ ] Log execution trigger source
    - [ ] Call `broadcast_scheduler.get_due_broadcasts()`
    - [ ] If no broadcasts due, return success with 0 counts
    - [ ] Call `broadcast_executor.execute_batch(broadcasts)`
    - [ ] Calculate execution time
    - [ ] Return {'success': bool, 'total_broadcasts': int, 'successful': int, 'failed': int, 'execution_time_seconds': float, 'results': list}
    - [ ] Status code: 200 on success, 500 on error
- [ ] Add comprehensive logging with emojis (🎯, 📋, 📤, ✅, ❌)
- [ ] Add error handling with try-except blocks
- [ ] Add execution time tracking

### 5.2 Manual Trigger API Routes (routes/api_routes.py)
**Purpose:** Handle JWT-authenticated manual triggers from website
**Dependencies:** services.broadcast_scheduler, clients.database_client, utils.config, utils.auth

- [ ] Create `routes/api_routes.py`
- [ ] Define Flask Blueprint: `api_bp = Blueprint('api', __name__, url_prefix='/api')`
- [ ] Initialize components:
  - [ ] `config = Config()`
  - [ ] `db_client = DatabaseClient(config)`
  - [ ] `broadcast_scheduler = BroadcastScheduler(db_client, config)`
- [ ] Implement endpoints:
  - [ ] `POST /api/broadcast/trigger` (JWT required):
    - [ ] Add `@jwt_required()` decorator
    - [ ] Extract 'broadcast_id' from request body
    - [ ] Validate broadcast_id is present
    - [ ] Extract client_id using `extract_client_id()` from utils.auth
    - [ ] Validate client_id is present
    - [ ] Call `broadcast_scheduler.check_manual_trigger_rate_limit(broadcast_id, client_id)`
    - [ ] If not allowed, return 429 with retry_after_seconds
    - [ ] If allowed, call `broadcast_scheduler.queue_manual_broadcast(broadcast_id)`
    - [ ] Return {'success': bool, 'message': str, 'broadcast_id': str}
    - [ ] Status codes: 200 (success), 400 (missing data), 401 (invalid token), 429 (rate limited), 500 (error)
  - [ ] `GET /api/broadcast/status/<broadcast_id>` (JWT required):
    - [ ] Add `@jwt_required()` decorator
    - [ ] Extract client_id using `extract_client_id()`
    - [ ] Call `db_client.get_broadcast_statistics(broadcast_id)`
    - [ ] If not found, return 404
    - [ ] Call `db_client.fetch_broadcast_by_id(broadcast_id)` to verify ownership
    - [ ] If owner doesn't match client_id, return 403 (Unauthorized)
    - [ ] Convert datetime fields to ISO 8601 format
    - [ ] Return statistics JSON
    - [ ] Status codes: 200 (success), 401 (invalid token), 403 (not owner), 404 (not found), 500 (error)
- [ ] Add comprehensive logging with emojis (📨, ⏳, ✅, ⚠️, ❌)
- [ ] Add request validation
- [ ] Add authorization checks

---

## Phase 6: Main Application (Application Factory)
**Estimated Time:** 30-45 minutes

### 6.1 Main Application Module (main.py)
**Purpose:** Flask application factory, initialization, and entry point
**Dependencies:** flask, flask-cors, flask-jwt-extended, routes.*, utils.*

- [ ] Create `main.py` in service root
- [ ] Import required modules:
  - [ ] Flask, CORS, JWTManager
  - [ ] Blueprint imports (broadcast_bp, api_bp)
  - [ ] Config and logging_utils
- [ ] Implement `create_app(config=None)` function:
  - [ ] Initialize Flask app
  - [ ] Load configuration using Config class or override
  - [ ] Apply config to app.config
  - [ ] Configure CORS with:
    - [ ] Resources: `/api/*`
    - [ ] Origins: `https://www.paygateprime.com`
    - [ ] Methods: GET, POST, OPTIONS
    - [ ] Headers: Content-Type, Authorization
    - [ ] Credentials: True
    - [ ] Max age: 3600
  - [ ] Initialize JWTManager
  - [ ] Register JWT error handlers
  - [ ] Register broadcast_bp blueprint
  - [ ] Register api_bp blueprint
  - [ ] Log successful initialization
  - [ ] Return app instance
- [ ] Implement `register_error_handlers(jwt)` function:
  - [ ] `@jwt.expired_token_loader` - Return 401 with message
  - [ ] `@jwt.invalid_token_loader` - Return 401 with message
  - [ ] `@jwt.unauthorized_loader` - Return 401 with message
- [ ] Add `if __name__ == "__main__":` block:
  - [ ] Get port from environment (default 8080)
  - [ ] Call `setup_logging()` from utils
  - [ ] Create app instance
  - [ ] Run Flask dev server (debug=True for local)
- [ ] Verify application factory pattern enables testing
- [ ] Add comprehensive logging for initialization

---

## Phase 7: Testing
**Estimated Time:** 2-3 hours

### 7.1 Unit Tests (tests/test_services.py)
- [ ] Create `tests/test_services.py`
- [ ] Import pytest, Mock, services modules
- [ ] Test `BroadcastScheduler`:
  - [ ] `test_get_due_broadcasts()` - Verify delegation to db_client
  - [ ] `test_rate_limit_enforcement()` - Verify rate limiting logic
  - [ ] `test_rate_limit_authorization()` - Verify ownership checks
  - [ ] `test_queue_manual_broadcast()` - Verify queuing logic
  - [ ] `test_calculate_next_send_time()` - Verify interval calculation
- [ ] Test `BroadcastExecutor`:
  - [ ] `test_execute_broadcast_success()` - Both channels succeed
  - [ ] `test_execute_broadcast_partial_failure()` - One channel fails
  - [ ] `test_execute_broadcast_complete_failure()` - Both channels fail
  - [ ] `test_execute_batch()` - Batch processing statistics
- [ ] Test `BroadcastTracker`:
  - [ ] `test_mark_success()` - Success updates
  - [ ] `test_mark_failure()` - Failure updates
  - [ ] `test_auto_disable()` - Disable after 5 failures
  - [ ] `test_reset_consecutive_failures()` - Manual re-enable

### 7.2 Integration Tests (tests/test_routes.py)
- [ ] Create `tests/test_routes.py`
- [ ] Create test fixture for Flask app:
  - [ ] Use `create_app()` with test config
  - [ ] Set `TESTING = True`
  - [ ] Provide test client
- [ ] Test `broadcast_routes`:
  - [ ] `test_health_check()` - Verify 200 and correct response
  - [ ] `test_execute_broadcasts_no_due()` - Empty broadcast list
  - [ ] `test_execute_broadcasts_with_due()` - Successful execution (requires mock)
- [ ] Test `api_routes`:
  - [ ] `test_trigger_without_jwt()` - Verify 401 response
  - [ ] `test_trigger_with_invalid_jwt()` - Verify 401 response
  - [ ] `test_trigger_missing_broadcast_id()` - Verify 400 response
  - [ ] `test_trigger_rate_limited()` - Verify 429 response
  - [ ] `test_trigger_success()` - Verify 200 response (requires mock)
  - [ ] `test_status_without_jwt()` - Verify 401 response
  - [ ] `test_status_not_found()` - Verify 404 response
  - [ ] `test_status_unauthorized()` - Verify 403 response (different owner)
  - [ ] `test_status_success()` - Verify 200 response (requires mock)

### 7.3 Local Docker Testing
- [ ] Create `.env.local` with test credentials
- [ ] Build Docker image:
  ```bash
  docker build -t gcbroadcastservice-10-26-test .
  ```
- [ ] Run container locally:
  ```bash
  docker run -p 8080:8080 --env-file .env.local gcbroadcastservice-10-26-test
  ```
- [ ] Test endpoints:
  - [ ] Health check: `curl http://localhost:8080/health`
  - [ ] Execute broadcasts: `curl -X POST http://localhost:8080/api/broadcast/execute`
  - [ ] Manual trigger (with JWT): `curl -X POST http://localhost:8080/api/broadcast/trigger -H "Authorization: Bearer <token>" -d '{"broadcast_id": "..."}'`
- [ ] Verify Cloud SQL Connector connection works
- [ ] Verify Secret Manager access works
- [ ] Verify Telegram API calls work (test bot)
- [ ] Monitor logs for errors

### 7.4 Test Database Queries
- [ ] Create test broadcast entries in database
- [ ] Test `fetch_due_broadcasts()`:
  - [ ] Verify JOIN with main_clients_database works
  - [ ] Verify filtering by is_active, next_send_time, consecutive_failures
  - [ ] Verify ORDER BY next_send_time ASC
- [ ] Test `update_broadcast_success()`:
  - [ ] Verify status = 'completed'
  - [ ] Verify counters increment correctly
  - [ ] Verify consecutive_failures resets to 0
  - [ ] Verify next_send_time is calculated correctly
- [ ] Test `update_broadcast_failure()`:
  - [ ] Verify status = 'failed'
  - [ ] Verify consecutive_failures increments
  - [ ] Verify is_active = false after 5 failures
  - [ ] Verify error_message and error_time are set
- [ ] Test `queue_manual_broadcast()`:
  - [ ] Verify next_send_time is set to NOW()
  - [ ] Verify last_manual_trigger_time is updated
  - [ ] Verify manual_trigger_count increments
- [ ] Clean up test data after validation

---

## Phase 8: Deployment to Cloud Run
**Estimated Time:** 1 hour

### 8.1 Pre-Deployment Verification
- [ ] Verify all tests pass (unit, integration, local Docker)
- [ ] Verify code follows architecture (no shared module dependencies)
- [ ] Verify Dockerfile is correct
- [ ] Verify requirements.txt has all dependencies
- [ ] Verify .dockerignore excludes unnecessary files

### 8.2 Secret Manager Configuration
- [ ] Verify secrets exist in Secret Manager:
  - [ ] `telegram-bot-token`
  - [ ] `telegram-bot-username`
  - [ ] `jwt-secret-key`
  - [ ] `broadcast-auto-interval`
  - [ ] `broadcast-manual-interval`
  - [ ] `cloud-sql-connection-name`
  - [ ] `database-name`
  - [ ] `database-user`
  - [ ] `database-password`
- [ ] Create secrets if missing:
  ```bash
  echo -n "24" | gcloud secrets create broadcast-auto-interval --data-file=-
  echo -n "0.0833" | gcloud secrets create broadcast-manual-interval --data-file=-
  ```

### 8.3 Cloud Run Deployment
- [ ] Deploy service to Cloud Run:
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
- [ ] Verify deployment succeeded:
  ```bash
  gcloud run services describe gcbroadcastservice-10-26 --region=us-central1
  ```
- [ ] Note the service URL from deployment output

### 8.4 IAM Permissions Configuration
- [ ] Grant Secret Manager access to Cloud Run service account:
  ```bash
  for secret in telegram-bot-token telegram-bot-username jwt-secret-key broadcast-auto-interval broadcast-manual-interval cloud-sql-connection-name database-name database-user database-password; do
    gcloud secrets add-iam-policy-binding $secret \
      --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
  done
  ```
- [ ] Grant Cloud SQL Client role:
  ```bash
  gcloud projects add-iam-policy-binding telepay-459221 \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"
  ```
- [ ] Grant Cloud Run Invoker role to Cloud Scheduler service account:
  ```bash
  gcloud run services add-iam-policy-binding gcbroadcastservice-10-26 \
    --region=us-central1 \
    --member="serviceAccount:telepay-scheduler@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/run.invoker"
  ```

### 8.5 Cloud Run Testing
- [ ] Test health check endpoint:
  ```bash
  curl https://gcbroadcastservice-10-26-XXXXXXX-uc.a.run.app/health
  ```
- [ ] Verify response is 200 with correct JSON
- [ ] Test execute broadcasts endpoint (should work even with no due broadcasts):
  ```bash
  curl -X POST https://gcbroadcastservice-10-26-XXXXXXX-uc.a.run.app/api/broadcast/execute
  ```
- [ ] Check Cloud Logging for execution logs
- [ ] Verify no errors in logs

---

## Phase 9: Cloud Scheduler Configuration
**Estimated Time:** 30 minutes

### 9.1 Create Cloud Scheduler Job
- [ ] Create daily broadcast execution job:
  ```bash
  gcloud scheduler jobs create http broadcast-execution-daily \
    --schedule="0 12 * * *" \
    --uri="https://gcbroadcastservice-10-26-XXXXXXX-uc.a.run.app/api/broadcast/execute" \
    --http-method=POST \
    --message-body='{"source": "cloud_scheduler"}' \
    --location=us-central1 \
    --time-zone="Etc/UTC" \
    --oidc-service-account-email=telepay-scheduler@telepay-459221.iam.gserviceaccount.com \
    --oidc-token-audience="https://gcbroadcastservice-10-26-XXXXXXX-uc.a.run.app"
  ```
- [ ] Verify job was created:
  ```bash
  gcloud scheduler jobs describe broadcast-execution-daily --location=us-central1
  ```

### 9.2 Test Cloud Scheduler Job
- [ ] Manually trigger job to test:
  ```bash
  gcloud scheduler jobs run broadcast-execution-daily --location=us-central1
  ```
- [ ] Check Cloud Logging for execution logs:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbroadcastservice-10-26"
  textPayload=~"Broadcast execution triggered by: cloud_scheduler"
  ```
- [ ] Verify job executed successfully
- [ ] Verify broadcast operations completed (if any were due)
- [ ] Check for any errors in logs

---

## Phase 10: Monitoring & Observability
**Estimated Time:** 30 minutes

### 10.1 Cloud Logging Configuration
- [ ] Create log filter for service:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbroadcastservice-10-26"
  ```
- [ ] Create log filter for errors:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbroadcastservice-10-26"
  severity>=ERROR
  ```
- [ ] Create log filter for broadcast execution:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbroadcastservice-10-26"
  textPayload=~"Broadcast execution triggered"
  ```
- [ ] Save useful filters for quick access

### 10.2 Cloud Monitoring Alerts
- [ ] Create alert policy for error rate > 5%:
  - [ ] Condition: Error rate threshold
  - [ ] Resource: Cloud Run service (gcbroadcastservice-10-26)
  - [ ] Threshold: 5% over 5 minutes
  - [ ] Notification: Email/SMS
- [ ] Create alert policy for failed broadcasts:
  - [ ] Condition: Log-based metric (consecutive_failures >= 3)
  - [ ] Resource: Cloud Run service
  - [ ] Notification: Email/SMS
- [ ] Create alert policy for high latency:
  - [ ] Condition: Response time > 30 seconds
  - [ ] Resource: Cloud Run service
  - [ ] Notification: Email
- [ ] Test alert notifications

### 10.3 Dashboard Creation
- [ ] Create Cloud Monitoring dashboard
- [ ] Add charts:
  - [ ] Request count (total, by endpoint)
  - [ ] Request latency (p50, p95, p99)
  - [ ] Error rate (4xx, 5xx)
  - [ ] Container instance count
  - [ ] Memory utilization
  - [ ] CPU utilization
  - [ ] Broadcast execution count (custom metric)
  - [ ] Broadcast success rate (custom metric)
- [ ] Save dashboard as "GCBroadcastService-10-26 Overview"

---

## Phase 11: Documentation
**Estimated Time:** 30 minutes

### 11.1 Service Documentation (README.md)
- [ ] Create `GCBroadcastService-10-26/README.md`
- [ ] Document sections:
  - [ ] Service Overview - Purpose and responsibilities
  - [ ] Architecture - Self-contained module design
  - [ ] Directory Structure - Explanation of each module
  - [ ] API Endpoints - Complete endpoint documentation
  - [ ] Authentication - JWT token requirements
  - [ ] Environment Variables - All required secrets
  - [ ] Local Development - Docker setup instructions
  - [ ] Deployment - Cloud Run deployment procedure
  - [ ] Testing - How to run tests
  - [ ] Monitoring - Log filters and dashboards
  - [ ] Troubleshooting - Common issues and solutions

### 11.2 Architecture Document Updates
- [ ] Update `TELEPAY_REFACTORING_ARCHITECTURE.md`:
  - [ ] Add GCBroadcastService to completed services section
  - [ ] Document Cloud Run URL
  - [ ] Document Cloud Scheduler configuration
  - [ ] Mark as "DEPLOYED"

### 11.3 Progress Tracking
- [ ] Add entry to `PROGRESS.md`:
  - [ ] Date: 2025-11-12
  - [ ] Summary: "Completed GCBroadcastService refactoring and deployment"
  - [ ] Changes: List all new files created
  - [ ] Deployment: Cloud Run URL and status
- [ ] Add entry to `DECISIONS.md`:
  - [ ] Date: 2025-11-12
  - [ ] Decision: "Self-contained module architecture for all webhooks"
  - [ ] Rationale: Independent deployment, no shared dependencies
  - [ ] Impact: Each service has its own utils/, clients/, services/
- [ ] Create `BUGS.md` entry if any issues found during deployment:
  - [ ] Issue description
  - [ ] Severity
  - [ ] Workaround (if applicable)
  - [ ] Status

---

## Phase 12: Validation & Testing Period
**Estimated Time:** 48 hours (passive monitoring)

### 12.1 Production Monitoring (First 24 Hours)
- [ ] Monitor Cloud Logging for errors every 2 hours
- [ ] Check Cloud Scheduler execution logs (daily at 12:00 PM UTC)
- [ ] Verify broadcasts are being sent successfully
- [ ] Monitor Telegram channel for broadcast messages
- [ ] Check database for updated broadcast statistics
- [ ] Verify no rate limiting issues with manual triggers
- [ ] Monitor Cloud Run metrics (latency, error rate)

### 12.2 Broadcast Statistics Validation
- [ ] Query database for broadcast success rate:
  ```sql
  SELECT
    COUNT(*) as total,
    SUM(CASE WHEN successful_broadcasts > 0 THEN 1 ELSE 0 END) as successful,
    AVG(successful_broadcasts * 100.0 / NULLIF(total_broadcasts, 0)) as success_rate
  FROM broadcast_manager
  WHERE last_sent_time >= NOW() - INTERVAL '24 hours';
  ```
- [ ] Compare success rate with GCBroadcastScheduler-10-26 historical data
- [ ] Investigate any significant differences
- [ ] Document findings

### 12.3 Manual Trigger Testing
- [ ] Test manual trigger via website (authenticated user)
- [ ] Verify rate limiting (trigger twice within 5 minutes)
- [ ] Verify authorization (try triggering another user's broadcast)
- [ ] Check response times
- [ ] Verify broadcast is queued and executed
- [ ] Monitor logs for JWT authentication flow

---

## Phase 13: Old Service Decommission
**Estimated Time:** 1 hour
**⚠️ Only proceed after 48 hours of successful GCBroadcastService operation**

### 13.1 Pre-Decommission Verification
- [ ] Verify GCBroadcastService has been running successfully for 48+ hours
- [ ] Verify no critical errors in logs
- [ ] Verify broadcast success rate is >= 95%
- [ ] Verify Cloud Scheduler job is executing daily
- [ ] Verify manual triggers are working
- [ ] Get user confirmation before proceeding

### 13.2 Disable GCBroadcastScheduler-10-26
- [ ] Scale down GCBroadcastScheduler Cloud Run service:
  ```bash
  gcloud run services update gcbroadcastscheduler-10-26 \
    --region=us-central1 \
    --min-instances=0 \
    --max-instances=0
  ```
- [ ] Disable old Cloud Scheduler jobs (if any):
  ```bash
  gcloud scheduler jobs pause OLD_JOB_NAME --location=us-central1
  ```
- [ ] Monitor for 24 hours to ensure no issues

### 13.3 Archive Old Service
- [ ] Create archive directory:
  ```bash
  mkdir -p ARCHIVES/GCBroadcastScheduler-10-26-ORIGINAL
  ```
- [ ] Move old service files:
  ```bash
  mv GCBroadcastScheduler-10-26/* ARCHIVES/GCBroadcastScheduler-10-26-ORIGINAL/
  ```
- [ ] Create archive README with:
  - [ ] Archive date
  - [ ] Reason for archiving (replaced by GCBroadcastService-10-26)
  - [ ] Reference to new service
  - [ ] Restoration procedure (if needed)

### 13.4 Final Documentation
- [ ] Update `PROGRESS.md`:
  - [ ] Date: [Current date]
  - [ ] Summary: "Decommissioned GCBroadcastScheduler-10-26, replaced by GCBroadcastService-10-26"
  - [ ] Status: Archived
- [ ] Update `DECISIONS.md`:
  - [ ] Date: [Current date]
  - [ ] Decision: "Fully migrated to self-contained GCBroadcastService architecture"
  - [ ] Impact: Old scheduler no longer active

---

## ✅ Completion Criteria

The refactoring is considered **complete** when:

1. ✅ **All modules are self-contained** - No external shared dependencies
2. ✅ **All tests pass** - Unit, integration, and local Docker tests
3. ✅ **Service is deployed** - Cloud Run deployment successful
4. ✅ **Cloud Scheduler is configured** - Automated execution working
5. ✅ **Monitoring is active** - Logs, alerts, and dashboards configured
6. ✅ **Documentation is complete** - README, architecture docs updated
7. ✅ **48-hour validation passed** - No critical errors, success rate >= 95%
8. ✅ **Old service decommissioned** - GCBroadcastScheduler-10-26 archived

---

## 🚨 Rollback Procedure

If critical issues are discovered during validation:

1. **Immediate Actions:**
   - [ ] Re-enable GCBroadcastScheduler-10-26:
     ```bash
     gcloud run services update gcbroadcastscheduler-10-26 \
       --region=us-central1 \
       --min-instances=0 \
       --max-instances=3
     ```
   - [ ] Disable GCBroadcastService Cloud Scheduler job:
     ```bash
     gcloud scheduler jobs pause broadcast-execution-daily --location=us-central1
     ```
   - [ ] Re-enable old Cloud Scheduler jobs

2. **Investigation:**
   - [ ] Review Cloud Logging for errors
   - [ ] Review database for failed broadcasts
   - [ ] Review Telegram API error responses
   - [ ] Document root cause

3. **Fix and Redeploy:**
   - [ ] Fix identified issues in GCBroadcastService
   - [ ] Re-test locally
   - [ ] Redeploy to Cloud Run
   - [ ] Resume validation period

---

## 📝 Notes

- **Emoji Convention:** Maintain existing emoji usage in logs (🎯, 📋, 📤, ✅, ❌, ⚠️, 📨, ⏳, 📊, 🔄, 🚀, 🤖, 💰, 🥇, 🥈, 🥉, 💝)
- **Error Handling:** All service methods return structured error responses with `{'success': bool, 'error': str}`
- **Database Connections:** Always use context manager pattern (`with db.get_connection() as conn:`)
- **Timezone Handling:** All datetime operations use `datetime.now(timezone.utc)` for consistency
- **JWT Tokens:** Extract identity with `get_jwt_identity()` from Flask-JWT-Extended
- **Rate Limiting:** Manual trigger interval is 5 minutes (0.0833 hours) by default
- **Auto Disable:** Broadcasts are automatically disabled after 5 consecutive failures
- **Logging:** All logs use structured format with timestamp, name, level, message
- **Security:** CORS is configured for `https://www.paygateprime.com` only
- **Scalability:** Cloud Run configured with min=0, max=3 instances

---

**Document Owner:** Claude
**Review Date:** 2025-11-12
**Next Review:** After deployment completion
