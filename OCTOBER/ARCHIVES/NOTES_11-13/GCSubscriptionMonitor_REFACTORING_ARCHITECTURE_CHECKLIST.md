# GCSubscriptionMonitor Refactoring Architecture - Implementation Checklist

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Implementation Roadmap
**Branch:** TelePay-REFACTOR
**Related Architecture:** GCSubscriptionMonitor_REFACTORING_ARCHITECTURE.md

---

## Overview

This checklist guides the implementation of **GCSubscriptionMonitor-10-26**, transforming subscription expiration monitoring from a long-running background task into a standalone Cloud Run webhook service triggered by Cloud Scheduler.

**Key Principle:** Each module exists independently within the service (no shared dependencies).

---

## Phase 1: Project Setup & Directory Structure

### 1.1 Create Service Directory
- [ ] Create directory: `/OCTOBER/10-26/GCSubscriptionMonitor-10-26/`
- [ ] Navigate to new directory
- [ ] Initialize git tracking (files already in repo)
- [ ] Create `.env.example` file with required environment variables

### 1.2 Environment Variables Template
- [ ] Create `.env.example` with the following:
  ```bash
  TELEGRAM_BOT_TOKEN_SECRET=projects/telepay-459221/secrets/telegram-bot-token/versions/latest
  DATABASE_HOST_SECRET=projects/telepay-459221/secrets/database-host/versions/latest
  DATABASE_NAME_SECRET=projects/telepay-459221/secrets/database-name/versions/latest
  DATABASE_USER_SECRET=projects/telepay-459221/secrets/database-user/versions/latest
  DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/database-password/versions/latest
  PORT=8080
  ```

---

## Phase 2: Module Implementation (Modular Structure)

### 2.1 Module 1: config_manager.py (Self-Contained Configuration)
- [ ] Create file: `GCSubscriptionMonitor-10-26/config_manager.py`
- [ ] Implement `ConfigManager` class
  - [ ] Add `__init__()` method with Secret Manager client initialization
  - [ ] Add `fetch_secret()` generic method for Secret Manager access
  - [ ] Add `fetch_telegram_token()` method
  - [ ] Add `fetch_database_host()` method
  - [ ] Add `fetch_database_name()` method
  - [ ] Add `fetch_database_user()` method
  - [ ] Add `fetch_database_password()` method
  - [ ] Add `initialize_config()` method to fetch all secrets
  - [ ] Add error handling with logging (using emoji style: ❌, ✅)
  - [ ] Add validation for missing critical configuration
- [ ] Test module independently:
  - [ ] Import and instantiate ConfigManager
  - [ ] Verify all secrets can be fetched
  - [ ] Verify error handling for missing env vars

### 2.2 Module 2: database_manager.py (Self-Contained Database Operations)
- [ ] Create file: `GCSubscriptionMonitor-10-26/database_manager.py`
- [ ] Implement `DatabaseManager` class
  - [ ] Add `__init__()` method with Cloud SQL Connector initialization
  - [ ] Add `_getconn()` private method for connection creation
  - [ ] Add `get_connection()` method for retrieving connections from pool
  - [ ] Add `fetch_expired_subscriptions()` method
    - [ ] Implement SQL query to fetch active subscriptions with expiration data
    - [ ] Implement date/time parsing logic (handle both string and datetime types)
    - [ ] Implement expiration comparison logic (current_datetime > expire_datetime)
    - [ ] Return list of tuples: (user_id, private_channel_id, expire_time, expire_date)
    - [ ] Add error handling with logging (🔍, 📊, ❌)
  - [ ] Add `deactivate_subscription()` method
    - [ ] Implement UPDATE query to set is_active = FALSE
    - [ ] Add WHERE clause: user_id + private_channel_id + is_active = true (idempotency)
    - [ ] Check rowcount to verify update success
    - [ ] Add error handling with logging (📝, ⚠️, ❌)
  - [ ] Add `close()` method to close connector
- [ ] Test module independently:
  - [ ] Verify database connection works
  - [ ] Test fetch_expired_subscriptions() with test data
  - [ ] Test deactivate_subscription() with test user
  - [ ] Verify idempotency (running update twice doesn't fail)

### 2.3 Module 3: telegram_client.py (Self-Contained Telegram Bot API Wrapper)
- [ ] Create file: `GCSubscriptionMonitor-10-26/telegram_client.py`
- [ ] Implement `TelegramClient` class
  - [ ] Add `__init__()` method to initialize Bot instance
  - [ ] Add `remove_user_from_channel()` async method
    - [ ] Implement ban_chat_member API call
    - [ ] Implement unban_chat_member API call (immediate unban pattern)
    - [ ] Add error handling for TelegramError
      - [ ] Handle "user not found" (consider success)
      - [ ] Handle "user is not a member" (consider success)
      - [ ] Handle "Forbidden" (log error, return False)
      - [ ] Handle "chat not found" (log error, return False)
      - [ ] Handle other errors (log error, return False)
    - [ ] Add logging with emoji style (🚫, ℹ️, ❌)
    - [ ] Return True on success, False on failure
  - [ ] Add `remove_user_sync()` synchronous wrapper
    - [ ] Create new event loop
    - [ ] Run async method in loop with run_until_complete()
    - [ ] Close event loop
    - [ ] Add error handling
- [ ] Test module independently:
  - [ ] Verify bot token loads correctly
  - [ ] Test remove_user_sync() with test user (safely)
  - [ ] Verify error handling for invalid user IDs
  - [ ] Verify synchronous wrapper works correctly

### 2.4 Module 4: expiration_handler.py (Self-Contained Business Logic)
- [ ] Create file: `GCSubscriptionMonitor-10-26/expiration_handler.py`
- [ ] Implement `ExpirationHandler` class
  - [ ] Add `__init__()` method accepting db_manager and telegram_client
  - [ ] Add `process_expired_subscriptions()` method
    - [ ] Call db_manager.fetch_expired_subscriptions()
    - [ ] Handle case: no expired subscriptions (return early with zeros)
    - [ ] Initialize counters: expired_count, processed_count, failed_count
    - [ ] Initialize details list for tracking individual results
    - [ ] Loop through each expired subscription:
      - [ ] Call telegram_client.remove_user_sync()
      - [ ] Call db_manager.deactivate_subscription()
      - [ ] Handle success case (both operations succeed)
      - [ ] Handle partial success (removal fails, deactivation succeeds)
      - [ ] Handle failure case (both operations fail)
      - [ ] Add details entry for each subscription
      - [ ] Increment appropriate counter
      - [ ] Add try/except for individual subscription errors
    - [ ] Add logging with emoji style (🔍, 📊, ✅, ⚠️, ❌, 🏁)
    - [ ] Return dictionary with statistics and details
- [ ] Test module independently:
  - [ ] Mock database manager and telegram client
  - [ ] Test with no expired subscriptions
  - [ ] Test with successful processing
  - [ ] Test with partial failures
  - [ ] Test with complete failures
  - [ ] Verify statistics are accurate

### 2.5 Module 5: service.py (Flask Application Entry Point)
- [ ] Create file: `GCSubscriptionMonitor-10-26/service.py`
- [ ] Implement application factory pattern
  - [ ] Add imports for Flask, logging, and all custom modules
  - [ ] Configure logging with basicConfig
  - [ ] Implement `create_app()` function
    - [ ] Initialize Flask app
    - [ ] Initialize ConfigManager and fetch configuration
    - [ ] Validate bot_token exists (raise RuntimeError if missing)
    - [ ] Initialize DatabaseManager with database credentials
    - [ ] Initialize TelegramClient with bot token
    - [ ] Initialize ExpirationHandler with managers
    - [ ] Define `/check-expirations` POST route
      - [ ] Call expiration_handler.process_expired_subscriptions()
      - [ ] Log start and completion with statistics (🕐, ✅)
      - [ ] Return JSON response with status and statistics
      - [ ] Add error handling (return 500 on error)
    - [ ] Define `/health` GET route
      - [ ] Test database connectivity (execute SELECT 1)
      - [ ] Verify telegram_client.bot is initialized
      - [ ] Return JSON with healthy status
      - [ ] Add error handling (return 503 on unhealthy)
    - [ ] Return app instance
  - [ ] Add `if __name__ == "__main__"` block
    - [ ] Call create_app()
    - [ ] Get PORT from environment (default 8080)
    - [ ] Run app on 0.0.0.0
- [ ] Test module independently:
  - [ ] Run service locally with proper env vars
  - [ ] Test /health endpoint returns 200
  - [ ] Test /check-expirations endpoint returns valid JSON
  - [ ] Verify logging output is formatted correctly

---

## Phase 3: Supporting Files & Configuration

### 3.1 Requirements File
- [ ] Create file: `GCSubscriptionMonitor-10-26/requirements.txt`
- [ ] Add dependencies:
  ```txt
  Flask==3.0.0
  google-cloud-secret-manager==2.18.0
  cloud-sql-python-connector==1.7.0
  sqlalchemy==2.0.25
  pg8000==1.30.4
  python-telegram-bot==20.7
  gunicorn==21.2.0
  ```
- [ ] Verify all version numbers are compatible
- [ ] Test pip install locally

### 3.2 Dockerfile
- [ ] Create file: `GCSubscriptionMonitor-10-26/Dockerfile`
- [ ] Add base image: `FROM python:3.11-slim`
- [ ] Set working directory: `WORKDIR /app`
- [ ] Copy requirements.txt first (layer caching optimization)
- [ ] Install dependencies with pip
- [ ] Copy all Python modules:
  - [ ] service.py
  - [ ] config_manager.py
  - [ ] database_manager.py
  - [ ] telegram_client.py
  - [ ] expiration_handler.py
- [ ] Expose port 8080
- [ ] Set PYTHONUNBUFFERED=1 environment variable
- [ ] Add CMD to run service.py
- [ ] Test local Docker build: `docker build -t gcsubscriptionmonitor:test .`
- [ ] Test local Docker run with env vars

### 3.3 Docker Ignore File
- [ ] Create file: `GCSubscriptionMonitor-10-26/.dockerignore`
- [ ] Add patterns:
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

### 3.4 README Documentation
- [ ] Create file: `GCSubscriptionMonitor-10-26/README.md`
- [ ] Add service description
- [ ] Add architecture overview
- [ ] Add deployment instructions
- [ ] Add testing instructions
- [ ] Add troubleshooting section
- [ ] Add environment variables reference

---

## Phase 4: Database Verification

### 4.1 Verify Database Schema
- [ ] Connect to telepaypsql database
- [ ] Verify `private_channel_users_database` table exists
- [ ] Verify required columns exist:
  - [ ] user_id (integer)
  - [ ] private_channel_id (bigint)
  - [ ] is_active (boolean)
  - [ ] expire_time (time or text)
  - [ ] expire_date (date or text)
- [ ] Check indexes on: user_id, private_channel_id, is_active
- [ ] Verify data types match code expectations

### 4.2 Test Data Preparation
- [ ] Identify test users with expired subscriptions
- [ ] Document test user IDs and channel IDs for testing
- [ ] Create backup of test data (optional)

---

## Phase 5: Secret Manager & IAM Configuration

### 5.1 Verify Secrets Exist in Secret Manager
- [ ] Check secret exists: `telegram-bot-token`
- [ ] Check secret exists: `database-host` (should be instance connection name)
- [ ] Check secret exists: `database-name`
- [ ] Check secret exists: `database-user`
- [ ] Check secret exists: `database-password`
- [ ] Verify all secrets have latest version
- [ ] Test accessing each secret manually

### 5.2 Service Account Configuration
- [ ] Verify service account exists: `telepay-cloudrun@telepay-459221.iam.gserviceaccount.com`
- [ ] Grant required roles to service account:
  - [ ] `roles/secretmanager.secretAccessor` (for Secret Manager)
  - [ ] `roles/cloudsql.client` (for Cloud SQL)
  - [ ] `roles/logging.logWriter` (for Cloud Logging)
- [ ] Verify service account has permissions:
  ```bash
  gcloud projects get-iam-policy telepay-459221 \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com"
  ```

### 5.3 Scheduler Service Account Configuration
- [ ] Verify service account exists: `telepay-scheduler@telepay-459221.iam.gserviceaccount.com`
- [ ] Grant `roles/run.invoker` role to scheduler service account
- [ ] Verify permissions are set correctly

---

## Phase 6: Deployment to Cloud Run

### 6.1 Create Deployment Script
- [ ] Create file: `/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts/deploy_gcsubscriptionmonitor.sh`
- [ ] Add shebang and variables:
  ```bash
  #!/bin/bash
  PROJECT_ID="telepay-459221"
  REGION="us-central1"
  SERVICE_NAME="gcsubscriptionmonitor-10-26"
  ```
- [ ] Add gcloud run deploy command with:
  - [ ] `--source` pointing to GCSubscriptionMonitor-10-26 directory
  - [ ] `--region=us-central1`
  - [ ] `--platform=managed`
  - [ ] `--no-allow-unauthenticated` (OIDC only)
  - [ ] All environment variables (5 secrets)
  - [ ] `--min-instances=0` (scale to zero)
  - [ ] `--max-instances=1` (only one needed)
  - [ ] `--memory=512Mi`
  - [ ] `--cpu=1`
  - [ ] `--timeout=300s`
  - [ ] `--concurrency=1`
  - [ ] `--service-account=telepay-cloudrun@telepay-459221.iam.gserviceaccount.com`
- [ ] Add success message with emoji
- [ ] Make script executable: `chmod +x deploy_gcsubscriptionmonitor.sh`

### 6.2 Initial Deployment
- [ ] Run deployment script: `./deploy_gcsubscriptionmonitor.sh`
- [ ] Wait for deployment to complete
- [ ] Verify deployment success in Cloud Console
- [ ] Capture service URL from output
- [ ] Document service URL in architecture file

### 6.3 Verify Deployment
- [ ] Check Cloud Run service exists:
  ```bash
  gcloud run services describe gcsubscriptionmonitor-10-26 --region=us-central1
  ```
- [ ] Verify service is running
- [ ] Check logs for startup messages:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsubscriptionmonitor-10-26" --limit=50
  ```

---

## Phase 7: Cloud Scheduler Setup

### 7.1 Create Scheduler Job Script
- [ ] Create file: `/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts/create_subscription_monitor_scheduler.sh`
- [ ] Add shebang and variables
- [ ] Add gcloud scheduler jobs create command with:
  - [ ] Job name: `subscription-monitor`
  - [ ] Schedule: `*/1 * * * *` (every minute)
  - [ ] Target URI: `${SERVICE_URL}/check-expirations`
  - [ ] HTTP method: POST
  - [ ] Location: us-central1
  - [ ] OIDC service account: telepay-scheduler@telepay-459221.iam.gserviceaccount.com
  - [ ] OIDC token audience: ${SERVICE_URL}
  - [ ] Time zone: America/New_York
  - [ ] Attempt deadline: 300s
- [ ] Add success message and manual test command
- [ ] Make script executable

### 7.2 Create Scheduler Job (Initially Paused)
- [ ] Run script to create scheduler job
- [ ] Verify job created in Cloud Console
- [ ] **PAUSE the job immediately** (for parallel testing):
  ```bash
  gcloud scheduler jobs pause subscription-monitor --location=us-central1
  ```
- [ ] Verify job is paused

---

## Phase 8: Testing

### 8.1 Health Check Testing
- [ ] Test health endpoint using gcloud proxy:
  ```bash
  gcloud run services proxy gcsubscriptionmonitor-10-26 --region=us-central1
  ```
- [ ] Verify health check returns:
  - [ ] Status code: 200
  - [ ] JSON: `{"status": "healthy", "database": "connected", "telegram": "initialized"}`
- [ ] Check Cloud Logging for health check logs

### 8.2 Manual Endpoint Testing
- [ ] Trigger /check-expirations manually via gcloud proxy:
  ```bash
  curl -X POST http://localhost:8080/check-expirations
  ```
- [ ] Verify response JSON contains:
  - [ ] "status": "success"
  - [ ] "expired_count": <number>
  - [ ] "processed_count": <number>
  - [ ] "failed_count": <number>
  - [ ] "details": [...]
- [ ] Check Cloud Logging for processing logs
- [ ] Verify database updates (check is_active changed to FALSE)
- [ ] Verify users removed from Telegram channels

### 8.3 Cloud Scheduler Manual Trigger
- [ ] Trigger scheduler job manually:
  ```bash
  gcloud scheduler jobs run subscription-monitor --location=us-central1
  ```
- [ ] Wait for execution to complete
- [ ] Check scheduler job execution history in Cloud Console
- [ ] Verify Cloud Run was triggered (check logs)
- [ ] Verify processing completed successfully

### 8.4 Parallel Testing with Existing System
- [ ] **Keep TelePay10-26 subscription_manager.py running**
- [ ] Manually trigger GCSubscriptionMonitor every 60 seconds for 1 hour
- [ ] Compare results between both systems:
  - [ ] Same number of expirations processed
  - [ ] Same users removed from channels
  - [ ] Same database updates
  - [ ] No race conditions or conflicts
- [ ] Monitor error rates (should be < 1%)
- [ ] Monitor latency (p95 should be < 2 seconds)
- [ ] Document any discrepancies

### 8.5 Load Testing (Optional)
- [ ] Create multiple test subscriptions with various expiration times
- [ ] Verify service handles batch processing correctly
- [ ] Monitor memory and CPU usage
- [ ] Verify timeout doesn't occur (should complete < 300s)

---

## Phase 9: Gradual Cutover

### 9.1 Enable Cloud Scheduler (Production)
- [ ] Verify parallel testing completed successfully
- [ ] Review any errors from testing phase
- [ ] Resume Cloud Scheduler job:
  ```bash
  gcloud scheduler jobs resume subscription-monitor --location=us-central1
  ```
- [ ] Verify job starts triggering every minute
- [ ] Monitor initial runs for errors

### 9.2 Disable Old Subscription Manager
- [ ] **BACKUP TelePay10-26 code before changes**
- [ ] Open `TelePay10-26/telepay10-26.py` (or main bot file)
- [ ] Locate subscription_manager initialization code
- [ ] Comment out or remove:
  - [ ] `from subscription_manager import SubscriptionManager`
  - [ ] `subscription_manager = SubscriptionManager(...)`
  - [ ] `await subscription_manager.start_monitoring()`
- [ ] Save changes
- [ ] Redeploy TelePay10-26 bot
- [ ] Verify bot still functions (without subscription monitoring)

### 9.3 Monitor Cutover (24 Hours)
- [ ] Create Cloud Logging query to monitor GCSubscriptionMonitor:
  ```bash
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcsubscriptionmonitor-10-26"
  severity>="INFO"
  ```
- [ ] Monitor for 24 hours continuously
- [ ] Check for:
  - [ ] All expirations being processed
  - [ ] No missed expirations
  - [ ] No duplicate processing
  - [ ] Error rate < 1%
  - [ ] Successful database updates
- [ ] Verify users are being removed from channels
- [ ] Check for user complaints (none expected)

### 9.4 Rollback Plan (If Needed)
- [ ] If critical issues found, execute rollback:
  - [ ] Pause Cloud Scheduler job immediately
  - [ ] Re-enable subscription_manager.py in TelePay10-26
  - [ ] Redeploy bot
  - [ ] Verify bot resumes subscription monitoring
  - [ ] Investigate issues in GCSubscriptionMonitor
  - [ ] Fix issues and restart cutover process

---

## Phase 10: Cleanup & Documentation

### 10.1 Archive Old Code
- [ ] Verify GCSubscriptionMonitor is stable (running for 1 week)
- [ ] Move old subscription_manager.py to archives:
  ```bash
  mv TelePay10-26/subscription_manager.py ARCHIVES/TelePay10-26-subscription_manager.py.bak
  ```
- [ ] Document archive location in architecture file

### 10.2 Update Progress Files
- [ ] Update PROGRESS.md with implementation summary
- [ ] Add entry to DECISIONS.md documenting architectural decision
- [ ] Document any bugs found in BUGS.md
- [ ] Move old entries to archives if files are getting large

### 10.3 Update Documentation
- [ ] Update main project README (if exists)
- [ ] Document new service in architecture overview
- [ ] Add GCSubscriptionMonitor to list of deployed services
- [ ] Document Cloud Scheduler job details
- [ ] Add monitoring and alerting information

### 10.4 Create Monitoring & Alerting (Optional)
- [ ] Create Cloud Monitoring dashboard for GCSubscriptionMonitor
- [ ] Add metrics:
  - [ ] Request count
  - [ ] Error rate
  - [ ] Latency (p50, p95, p99)
  - [ ] Expirations processed per run
- [ ] Create alert policies:
  - [ ] Error rate > 10% for 3 consecutive runs
  - [ ] No successful runs for 10 minutes
  - [ ] Failed count > 50 in single run
- [ ] Configure notification channels (email, Slack, etc.)

---

## Phase 11: Verification & Sign-off

### 11.1 Final Verification Checklist
- [ ] Service is deployed and running on Cloud Run
- [ ] Cloud Scheduler triggers service every 60 seconds
- [ ] Health checks pass consistently
- [ ] Expired subscriptions are processed correctly
- [ ] Users are removed from Telegram channels
- [ ] Database is updated (is_active = FALSE)
- [ ] Logging is comprehensive and clear
- [ ] Error handling works correctly
- [ ] No errors in logs for 7 consecutive days
- [ ] Performance metrics are acceptable:
  - [ ] Latency p95 < 2 seconds
  - [ ] Error rate < 1%
  - [ ] Success rate > 99%

### 11.2 Performance Benchmarks
- [ ] Document average processing time per expiration
- [ ] Document average number of expirations per run
- [ ] Document resource usage (memory, CPU)
- [ ] Document cost per run (estimated)

### 11.3 Knowledge Transfer
- [ ] Document operational procedures
- [ ] Document troubleshooting steps
- [ ] Document rollback procedures
- [ ] Document how to modify schedule if needed
- [ ] Document how to scale up/down if needed

---

## Rollback Procedures (Emergency)

### If Service Fails Completely
1. **Pause Cloud Scheduler immediately:**
   ```bash
   gcloud scheduler jobs pause subscription-monitor --location=us-central1
   ```

2. **Re-enable subscription_manager.py in TelePay10-26:**
   - Restore code from backup
   - Redeploy bot
   - Verify monitoring resumes

3. **Investigate issues:**
   - Check Cloud Logging for errors
   - Review recent deployments
   - Test health endpoint
   - Verify database connectivity
   - Verify Telegram bot token

4. **Fix and retry:**
   - Deploy fix to Cloud Run
   - Test manually
   - Resume Cloud Scheduler if successful

---

## Success Criteria

### Technical Success
- [x] All 5 modules implemented and tested independently
- [x] Service deployed to Cloud Run successfully
- [x] Cloud Scheduler triggers service every 60 seconds
- [x] Health checks pass consistently (7 days)
- [x] Expirations processed correctly (no missed expirations)
- [x] Error rate < 1%
- [x] Latency p95 < 2 seconds

### Business Success
- [x] Users are removed from channels when subscriptions expire
- [x] No user complaints about access issues
- [x] No revenue loss due to failed processing
- [x] Monitoring and alerting in place

### Operational Success
- [x] Service runs independently of bot
- [x] Clear logs and metrics available
- [x] Rollback procedures tested and documented
- [x] Knowledge transfer completed
- [x] Old code archived

---

## Notes & Reminders

1. **Module Independence:** Each module must be self-contained within the service. Do NOT create shared modules outside the service directory.

2. **Emoji Logging:** Maintain consistent emoji usage in logging:
   - ✅ = Success
   - ❌ = Error/Failure
   - ⚠️ = Warning
   - 🔍 = Searching/Finding
   - 📊 = Statistics
   - 📝 = Database update
   - 🚫 = User removal
   - ℹ️ = Info
   - 🕐 = Time/Schedule
   - 🔌 = Connection
   - 🤖 = Telegram bot
   - 🏁 = Completion

3. **Testing:** Always test each module independently before integration. This ensures issues can be isolated quickly.

4. **Database Operations:** All database operations must be idempotent (safe to run multiple times).

5. **Error Handling:** Always mark subscriptions as inactive even if user removal fails (user may have already left).

6. **Secrets:** Never hardcode secrets. Always use Secret Manager with environment variables.

7. **Deployment:** Always deploy to Cloud Run with `--no-allow-unauthenticated` to ensure only Cloud Scheduler can invoke.

8. **Monitoring:** Monitor Cloud Logging actively during cutover period.

---

## Checklist Progress Tracker

**Total Tasks:** 200+
**Completed:** 0
**In Progress:** 0
**Blocked:** 0

**Estimated Timeline:** 6 days
**Started:** [DATE]
**Completed:** [DATE]

---

**Document Status:** Ready for Implementation
**Last Updated:** 2025-11-12
**Next Review:** After Phase 6 completion
