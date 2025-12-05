# PGP_v1 Shell Scripts Inventory & Analysis

**Date**: 2025-11-18
**Purpose**: Comprehensive inventory and classification of all shell scripts in PGP_v1 architecture
**Total Scripts Found**: 24

---

## Executive Summary

This document catalogs all shell scripts generated for the PGP_v1 architecture, categorizing them by purpose and relevance to the current PGP_v1 implementation. The scripts fall into **5 primary categories**:

1. **Infrastructure & Secrets Management** (3 scripts)
2. **Cloud Tasks Queue Deployment** (4 scripts)
3. **Service Deployment Scripts** (9 scripts)
4. **Development & Testing** (5 scripts)
5. **Legacy/Maintenance Scripts** (3 scripts)

### Key Findings:

- **Core PGP_v1 Scripts**: 16 scripts directly support the new PGP_v1 architecture
- **Legacy Scripts**: 3 scripts reference old naming schemes (telepay-459221 project)
- **Mixed/Transition Scripts**: 5 scripts contain both old and new references
- **Production-Ready**: Scripts with `--dry-run` flags and safety checks

---

## Category 1: Infrastructure & Secrets Management

### 1.1 `create_pgp_live_secrets.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Initialize ALL 77 secrets in Google Cloud Secret Manager for pgp-live project
**Status**: ✅ **Core PGP_v1 Script**

**Key Features**:
- Creates 77 secrets organized in 10 categories
- Uses new PGP_v1 naming scheme (e.g., `PGP_ACCUMULATOR_URL`, `PGP_HOSTPAY1_QUEUE`)
- Generates new cryptographic keys for security
- Supports `--dry-run` mode for testing
- Interactive confirmation prompts

**Secret Categories Created**:
1. Service URLs (18 secrets)
2. Cloud Tasks Queues (19 secrets)
3. API Keys & Tokens (8 secrets)
4. Blockchain & Wallet (6 secrets)
5. Database Credentials (6 secrets)
6. Telegram Bot (2 secrets)
7. Signing & Security Keys (5 secrets)
8. Email Configuration (3 secrets)
9. Application Config (11 secrets)
10. NEW Security Secrets (2 secrets)

**Critical Notes**:
- Requires manual update of placeholder values: `<VALUE_FROM_TELEPAY>`, `<PROJECT_NUM>`
- Contains CRITICAL wallet private keys
- Must run BEFORE service deployment

**Target Project**: `pgp-live`

---

### 1.2 `grant_pgp_live_secret_access.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Grant IAM permissions to service accounts for accessing all 77 secrets
**Status**: ✅ **Core PGP_v1 Script**

**Key Features**:
- Grants `roles/secretmanager.secretAccessor` to all 77 secrets
- Default service account: `compute@developer.gserviceaccount.com`
- Interactive confirmation
- Organized by secret category

**Dependencies**:
- Must run AFTER `create_pgp_live_secrets.sh`
- Requires project-level IAM permissions

**Target Project**: `pgp-live`

---

### 1.3 `fix_secret_newlines.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Fix trailing newlines in secret values that break URL/queue name parsing
**Status**: ✅ **Maintenance/Utility Script**

**Fixes 19 Secrets**:
- Queue names: `PGP_INVITE_QUEUE`, `PGP_SPLIT1_QUEUE`, etc.
- Service URLs: `PGP_SPLIT1_URL`, `PGP_ACCUMULATOR_URL`, etc.

**Why Needed**:
- Secrets created via `echo` instead of `echo -n` get trailing newlines
- Cloud Tasks fails to find queues with `\n` in name
- HTTP requests fail with newlines in URLs

---

## Category 2: Cloud Tasks Queue Deployment

All queue deployment scripts follow a consistent pattern:
- Check if queue exists → Update OR Create
- Use PGP_v1 naming: `pgp-{service}-{purpose}-queue-v1`
- Infinite retry configuration (24h max duration)
- Fixed 60s backoff (no exponential backoff)

### 2.1 `deploy_gcwebhook_tasks_queues.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy queues for PGP_ORCHESTRATOR_v1 and PGP_INVITE_v1
**Status**: ✅ **Core PGP_v1 Script**

**Queues Created**:
1. `pgp-invite-queue-v1`
   - Flow: `pgp-orchestrator-v1` → `pgp-invite-v1`
   - Purpose: Telegram invite dispatch
   - Rate: 8 dispatches/sec (80% of Telegram API limit)
   - Concurrency: 24 concurrent tasks

2. `pgp-orchestrator-queue-v1`
   - Flow: `pgp-orchestrator-v1` → `pgp-split1-v1`
   - Purpose: Payment split dispatch
   - Rate: 100 dispatches/sec
   - Concurrency: 150 concurrent tasks

**Target Project**: `pgp-live`

---

### 2.2 `deploy_accumulator_tasks_queues.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy queues for threshold payout system
**Status**: ✅ **Core PGP_v1 Script**

**Queues Created**:
1. `pgp-accumulator-queue-v1`
2. `pgp-batchprocessor-queue-v1`

**Configuration**:
- Rate: 10 dispatches/sec
- Concurrency: 50 concurrent tasks
- Use case: Batch payment processing

**Target Project**: `pgp-live`

---

### 2.3 `deploy_gcsplit_tasks_queues.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy queues for PGP_SPLIT1/2/3_v1 services
**Status**: ✅ **Core PGP_v1 Script**

**Queues Created** (5 queues):
1. `pgp-split1-estimate-queue-v1`
2. `pgp-split1-response-queue-v1`
3. `pgp-split2-swap-queue-v1`
4. `pgp-split2-response-queue-v1`
5. `pgp-hostpay-trigger-queue-v1`

**Configuration**:
- Rate: 10 dispatches/sec (respects ChangeNow API limits)
- Concurrency: 50 concurrent tasks

**Target Project**: `pgp-live`

---

### 2.4 `deploy_hostpay_tasks_queues.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy queues for PGP_HOSTPAY1/2/3_v1 services
**Status**: ✅ **Core PGP_v1 Script**

**Queues Created** (4 queues):
1. `pgp-hostpay-trigger-queue-v1`
   - Flow: `pgp-split1-v1` → `pgp-hostpay1-v1`
   - Purpose: Initial ETH payment orchestration

2. `pgp-hostpay2-status-queue-v1`
   - Flow: `pgp-hostpay1-v1` → `pgp-hostpay2-v1`
   - Purpose: ChangeNow status verification

3. `pgp-hostpay3-payment-queue-v1`
   - Flow: `pgp-hostpay1-v1` → `pgp-hostpay3-v1`
   - Purpose: ETH blockchain payment execution

4. `pgp-hostpay1-response-queue-v1`
   - Flow: `pgp-hostpay2/3-v1` → `pgp-hostpay1-v1`
   - Purpose: Response callbacks

**Configuration**:
- Rate: 5 dispatches/sec (conservative for blockchain transactions)
- Concurrency: 10 concurrent tasks
- Reason: Ethereum RPC providers have 10-100 RPS limits

**Target Project**: `pgp-live`

---

## Category 3: Service Deployment Scripts

### 3.1 `deploy_all_pgp_services.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Master deployment script for all 17 PGP_v1 services
**Status**: ⚠️ **Legacy References**

**Services Deployed** (in dependency order):
1. **Phase 1**: Core Infrastructure
   - `pgp-server-v1` (1Gi memory, min 1 instance)
   - `pgp-web-v1` (128Mi memory)
   - `pgp-webapi-v1` (512Mi memory)

2. **Phase 2**: Payment Processing
   - `pgp-np-ipn-v1`
   - `pgp-orchestrator-v1`
   - `pgp-invite-v1`
   - `pgp-split1-v1`, `pgp-split2-v1`, `pgp-split3-v1`

3. **Phase 3**: Payout Services
   - `pgp-hostpay1-v1`, `pgp-hostpay2-v1`, `pgp-hostpay3-v1`

4. **Phase 4**: Batch Processing
   - `pgp-accumulator-v1`
   - `pgp-batchprocessor-v1`, `pgp-microbatchprocessor-v1`

5. **Phase 5**: Notifications & Broadcast
   - `pgp-notifications-v1`
   - `pgp-broadcast-v1`

**Issues**:
- ❌ References old project: `telepay-459221`
- ❌ Old Cloud SQL instance: `telepay-459221:us-central1:telepaypsql`
- ✅ Service names use new PGP_v1 scheme

**Target Project**: `telepay-459221` (should be `pgp-live`)

**Recommendation**: Update PROJECT_ID and CLOUD_SQL_INSTANCE variables before use

---

### 3.2 `deploy_backend_api.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy PGP_WEBAPI_v1 backend API
**Status**: ✅ **Core PGP_v1 Script**

**Configuration**:
- Service: `pgp-webapi-v1`
- Region: `us-central1`
- Memory: 512Mi
- CPU: 1
- Timeout: 300s
- Min instances: 0, Max: 10

**Features**:
- Notification fields support
- Health endpoint testing
- Auto-saves service URL to `/tmp/`

---

### 3.3 `deploy_frontend.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Build and deploy PGP_WEB_v1 React frontend to Cloud Storage
**Status**: ✅ **Core PGP_v1 Script**

**Deployment Target**: `gs://www-paygateprime-com`

**Process**:
1. `npm install`
2. `npm run build`
3. `gsutil rsync` to Cloud Storage
4. Set cache headers:
   - HTML: `no-cache`
   - Assets: `max-age=31536000` (1 year)

**URL**: `https://www.paygateprime.com`

---

### 3.4 `deploy_telepay_bot.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy PGP_SERVER_v1 Telegram bot with notification service
**Status**: ✅ **Core PGP_v1 Script**

**Configuration**:
- Service: `pgp-server-v1`
- Memory: 1Gi
- CPU: 2
- Timeout: 3600s (1 hour)
- Min instances: 1, Max: 3
- Cloud SQL: `pgp-live:us-central1:pgp-telepaypsql`

**Secrets Configured** (7 secrets):
- `TELEGRAM_BOT_SECRET_NAME`
- `TELEGRAM_BOT_USERNAME`
- `CLOUD_SQL_CONNECTION_NAME`
- `DATABASE_HOST_SECRET`
- `DATABASE_NAME_SECRET`
- `DATABASE_USER_SECRET`
- `DATABASE_PASSWORD_SECRET`

**Features**:
- Notification service integration
- Subscription management (60s check interval)
- Health endpoint testing
- Saves URL for `pgp-np-ipn-v1` configuration

---

### 3.5 `deploy_np_webhook.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy PGP_NP_IPN_v1 NowPayments IPN webhook
**Status**: ✅ **Core PGP_v1 Script**

**Configuration**:
- Service: `pgp-np-ipn-v1`
- Memory: 512Mi
- CPU: 1
- Timeout: 300s
- Min instances: 1, Max: 10

**Secrets Configured** (12 secrets):
- `NOWPAYMENTS_IPN_SECRET`
- `CLOUD_SQL_CONNECTION_NAME`
- `DATABASE_NAME_SECRET`, `DATABASE_USER_SECRET`, `DATABASE_PASSWORD_SECRET`
- `CLOUD_TASKS_PROJECT_ID`, `CLOUD_TASKS_LOCATION`
- `PGP_ORCHESTRATOR_QUEUE`, `PGP_ORCHESTRATOR_URL`
- `PGP_INVITE_QUEUE`, `PGP_INVITE_URL`
- `PGP_SERVER_URL`

**Features**:
- Auto-creates `PGP_SERVER_URL` secret if missing
- Reads from `/tmp/pgp_server_url.txt`
- Health endpoint testing

**IPN Endpoint**: `{SERVICE_URL}/ipn`

---

### 3.6 `deploy_broadcast_scheduler.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy PGP_BROADCAST_v1 scheduled broadcast service
**Status**: ✅ **Core PGP_v1 Script**

**Configuration**:
- Service: `pgp-broadcast-v1`
- Memory: 512Mi
- CPU: 1
- Timeout: 300s
- Concurrency: 1 (single instance only)
- Min instances: 0, Max: 1

**Environment Variables** (10 secret paths):
- `BROADCAST_AUTO_INTERVAL_SECRET`
- `BROADCAST_MANUAL_INTERVAL_SECRET`
- `BOT_TOKEN_SECRET`
- `BOT_USERNAME_SECRET`
- `JWT_SECRET_KEY_SECRET`
- Database connection secrets

**Target Project**: `pgp-live`

---

### 3.7 `deploy_notification_feature.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Master orchestrator for notification management feature deployment
**Status**: ✅ **Core PGP_v1 Script**

**Deployment Order**:
1. ✅ Database Migration (verification only)
2. Backend API (`deploy_backend_api.sh`)
3. Frontend (`deploy_frontend.sh`)
4. Server Bot (`deploy_telepay_bot.sh`)
5. IPN Webhook (`deploy_np_webhook.sh`)

**Features**:
- Orchestrates multi-component deployment
- Logging to `../logs/deployment_notification_feature_{timestamp}.log`
- Interactive prompts
- Error handling with continue/abort options

---

### 3.8 `deploy_gcnotificationservice.sh`
**Location**: `PGP_NOTIFICATIONS_v1/`
**Purpose**: Deploy notification webhook service
**Status**: ⚠️ **Legacy Project Reference**

**Service**: `pgp_notificationservice-10-26`

**Issues**:
- ❌ Project: `telepay-459221` (should be `pgp-live`)
- ❌ Old naming: `pgp_notificationservice-10-26` vs `pgp-notifications-v1`
- ❌ Cloud SQL: `telepay-459221:us-central1:telepaypsql`

**Configuration**:
- Memory: 256Mi (lightweight)
- Timeout: 60s
- Concurrency: 80

**Recommendation**: Update for pgp-live or mark as deprecated

---

### 3.9 `pause_broadcast_scheduler.sh` & `resume_broadcast_scheduler.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Pause/resume Cloud Scheduler broadcast job
**Status**: ✅ **Core PGP_v1 Script**

**Controls**: Cloud Scheduler job `broadcast-scheduler-daily`

**Target Project**: `pgp-live`
**Location**: `us-central1`

**Use Cases**:
- Maintenance windows
- Emergency broadcast halt
- Testing periods

---

## Category 4: Development & Testing

### 4.1 `setup_venv.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Create Python virtual environment with all dependencies
**Status**: ✅ **Core Development Script**

**Location**: `{SCRIPT_DIR}/.venv`

**Dependencies Installed**:
- **Core**: Flask, Google Cloud SDK packages
- **Database**: `cloud-sql-python-connector`, `pg8000`, `psycopg2-binary`, SQLAlchemy
- **Cloud**: `google-cloud-secret-manager`, `google-cloud-tasks`, `google-cloud-logging`
- **Auth**: `flask-jwt-extended`, `bcrypt`
- **Communication**: `python-telegram-bot`, `sendgrid`, `httpx`
- **Utilities**: `pydantic`, `pytz`, `nest-asyncio`

**Features**:
- Interactive recreate prompt if venv exists
- Pip/setuptools/wheel upgrade
- Package list output

---

### 4.2 `activate_venv.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Quick activation wrapper for virtual environment
**Status**: ✅ **Development Utility**

**Usage**: `source activate_venv.sh`

**Features**:
- Checks venv exists
- Activates and displays Python version

---

### 4.3 `set_max_tokens.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Configure Claude Code max output tokens in .venv
**Status**: ✅ **Development Utility**

**Sets**: `CLAUDE_CODE_MAX_OUTPUT_TOKENS=200000`

**Mechanism**:
- Modifies `.venv/bin/activate` script
- Adds `export CLAUDE_CODE_MAX_OUTPUT_TOKENS=200000`
- Creates backup before modification
- Persistent across venv activations

---

### 4.4 `run_notification_test.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Execute notification flow integration test
**Status**: ✅ **Testing Script**

**Process**:
1. Fetch `DATABASE_PASSWORD_SECRET` from Secret Manager
2. Fetch `NOWPAYMENTS_IPN_SECRET` from Secret Manager
3. Export as environment variables
4. Run `python3 test_notification_flow.py`

**Target Project**: `pgp-live`

---

### 4.5 `deploy_message_tracking_migration.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy database migration for broadcast message tracking
**Status**: ⚠️ **Legacy Project Reference**

**Target Database**: `telepay-459221:us-central1:telepaypsql`

**Migration**: `add_message_tracking_columns.sql`

**Adds 4 Columns to `broadcast_manager`**:
- `last_auto_message_id`
- `last_auto_message_date`
- `last_manual_message_id`
- `last_manual_message_date`

**Issues**:
- ❌ Project: Uses old `telepay-459221` instance
- ✅ Verification logic checks all 4 columns

**Recommendation**: Update Cloud SQL connection string for pgp-live

---

## Category 5: Legacy/Maintenance Scripts

### 5.1 `deploy_actual_eth_fix.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy `actual_eth_amount` fix across 8 services
**Status**: ⚠️ **Mixed Legacy/New**

**Deployment Order** (downstream → upstream):
1. `pgp-hostpay3-v1`
2. `pgp-hostpay1-v1`
3. `pgp-split3-v1`
4. `pgp-split2-v1`
5. `pgp-split1-v1`
6. `pgp-orchestrator-v1`
7. `pgp_batchprocessor-10-26` ❌ (old naming)
8. `pgp_microbatchprocessor-10-26` ❌ (old naming)

**Issues**:
- ⚠️ Mixed naming: Some services use old `10-26` suffix
- ✅ Project: References `pgp-live`
- ❌ Base directory: Points to `/OCTOBER/10-26` (old location)

**Process**:
1. Build container with `gcloud builds submit`
2. Deploy to Cloud Run
3. Wait 30s between deployments

**Recommendation**: Update service names and base directory

---

### 5.2 `deploy_config_fixes.sh`
**Location**: `TOOLS_SCRIPTS_TESTS/scripts/`
**Purpose**: Deploy `config_manager.py` environment variable pattern fixes
**Status**: ⚠️ **Legacy Project Reference**

**Services Updated** (7 services):
- `pgp-invite-v1`
- `pgp-split1-v1`, `pgp-split2-v1`, `pgp-split3-v1`
- `pgp-hostpay1-v1`, `pgp-hostpay2-v1`, `pgp-hostpay3-v1`

**Fix Applied**: Changed from custom secret loading to direct `os.getenv()`

**Issues**:
- ❌ Project: `pgp-live` but references incorrect secret names
- ❌ Base directory: `/OCTOBER/10-26`
- ⚠️ Secrets use old naming: `GCSPLIT2_QUEUE` vs `PGP_SPLIT2_QUEUE`

**Recommendation**: Update to PGP_v1 secret naming scheme

---

### 5.3 Scripts NOT in PGP_v1 (Found in git status)

The following scripts exist but are NOT in `/PGP_v1`:

**In `/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts/`**:
- `add_donation_message_column.sql`
- `add_message_tracking_columns.sql`
- `add_notification_columns.sql`
- `create_broadcast_manager_table.sql`
- `create_donation_keypad_state_table.sql`
- `deploy_backend_api.sh` (duplicate)
- `deploy_broadcast_scheduler.sh` (duplicate)
- `deploy_frontend.sh` (duplicate)
- `deploy_gcbroadcastservice_message_tracking.sh`
- `deploy_gcsubscriptionmonitor.sh`
- `deploy_message_tracking_migration.sh` (duplicate)
- `deploy_notification_feature.sh` (duplicate)
- `deploy_np_webhook.sh` (duplicate)
- `deploy_telepay_bot.sh` (duplicate)
- `pause_broadcast_scheduler.sh` (duplicate)
- `resume_broadcast_scheduler.sh` (duplicate)
- `rollback_*.sql` (multiple)
- `verify_broadcast_integrity.sql`

**These are LEGACY scripts from the OCTOBER iteration** and should be ignored for PGP_v1.

---

## Webhook & Database Initialization Analysis

### Webhook Initialization Scripts

**Cloud Tasks Queue Creation**: 4 dedicated scripts
1. `deploy_gcwebhook_tasks_queues.sh` - Orchestrator & Invite queues
2. `deploy_accumulator_tasks_queues.sh` - Batch processing queues
3. `deploy_gcsplit_tasks_queues.sh` - Payment split queues
4. `deploy_hostpay_tasks_queues.sh` - ETH payout queues

**Total Queues Created**: 17 queues across all services

### Database Initialization Scripts

**No explicit database creation scripts in PGP_v1**

The following database operations are handled through:
1. **Cloud SQL**: Assumes database instance already exists
2. **Schema**: No `CREATE DATABASE` or full schema creation scripts
3. **Migrations**: Only column addition scripts (message tracking, notifications)

**Missing from PGP_v1**:
- ❌ Database instance creation script
- ❌ Complete schema initialization (tables, indexes, constraints)
- ❌ Database migration tool (e.g., Alembic, Flyway)
- ❌ Seed data scripts

**Found in OCTOBER/10-26** (but not migrated to PGP_v1):
- `create_broadcast_manager_table.sql`
- `create_donation_keypad_state_table.sql`
- `add_message_tracking_columns.sql`
- `add_notification_columns.sql`

**Recommendation**:
- Migrate schema creation scripts from `TOOLS_SCRIPTS_TESTS/migrations/` to PGP_v1
- Create comprehensive database initialization script
- Implement migration tracking system

---

## Secret Initialization

### Comprehensive Secret Creation: ✅ COMPLETE

**Script**: `create_pgp_live_secrets.sh`

Creates **ALL 77 secrets** required for PGP_v1 deployment across 10 categories.

### Secrets by Service

| Service | Secret Count | Categories |
|---------|--------------|------------|
| PGP_ACCUMULATOR_v1 | 3 | URL, Queue, Response Queue |
| PGP_BATCHPROCESSOR_v1 | 2 | URL, Queue |
| PGP_MICROBATCHPROCESSOR_v1 | 2 | URL, Response Queue |
| PGP_HOSTPAY1_v1 | 4 | URL, Queue, Response Queue, Batch Queue |
| PGP_HOSTPAY2_v1 | 2 | URL, Queue |
| PGP_HOSTPAY3_v1 | 3 | URL, Queue, Retry Queue |
| PGP_SPLIT1_v1 | 4 | URL, Queue, Batch Queue, Callback URLs |
| PGP_SPLIT2_v1 | 3 | URL, Queue, Response Queue |
| PGP_SPLIT3_v1 | 3 | URL, Queue, Response Queue |
| PGP_ORCHESTRATOR_v1 | 2 | URL, Queue |
| PGP_INVITE_v1 | 2 | URL, Queue |
| PGP_SERVER_v1 | 1 | URL |
| PGP_NP_IPN_v1 | 1 | Callback URL |
| Shared/Global | 48 | API keys, DB creds, signing keys, config |

---

## Scripts Pertaining to Latest PGP_v1 Architecture

### ✅ Core PGP_v1 Scripts (16 scripts)

**Infrastructure & Secrets**:
1. ✅ `create_pgp_live_secrets.sh` - Initialize all 77 secrets
2. ✅ `grant_pgp_live_secret_access.sh` - Grant IAM permissions
3. ✅ `fix_secret_newlines.sh` - Fix secret formatting issues

**Cloud Tasks Queues**:
4. ✅ `deploy_gcwebhook_tasks_queues.sh` - Orchestrator/Invite queues
5. ✅ `deploy_accumulator_tasks_queues.sh` - Batch processing queues
6. ✅ `deploy_gcsplit_tasks_queues.sh` - Split service queues
7. ✅ `deploy_hostpay_tasks_queues.sh` - HostPay service queues

**Service Deployments**:
8. ✅ `deploy_backend_api.sh` - PGP_WEBAPI_v1
9. ✅ `deploy_frontend.sh` - PGP_WEB_v1
10. ✅ `deploy_telepay_bot.sh` - PGP_SERVER_v1
11. ✅ `deploy_np_webhook.sh` - PGP_NP_IPN_v1
12. ✅ `deploy_broadcast_scheduler.sh` - PGP_BROADCAST_v1
13. ✅ `deploy_notification_feature.sh` - Orchestrator script
14. ✅ `pause_broadcast_scheduler.sh` - Pause broadcasts
15. ✅ `resume_broadcast_scheduler.sh` - Resume broadcasts

**Development**:
16. ✅ `setup_venv.sh` - Virtual environment setup
17. ✅ `activate_venv.sh` - Quick venv activation
18. ✅ `set_max_tokens.sh` - Claude Code configuration
19. ✅ `run_notification_test.sh` - Integration testing

---

### ⚠️ Scripts Requiring Updates (4 scripts)

**Issues**: Reference old project or naming schemes

1. ⚠️ `deploy_all_pgp_services.sh`
   - **Issue**: PROJECT_ID=`telepay-459221` (should be `pgp-live`)
   - **Issue**: Cloud SQL instance uses old project
   - **Fix Required**: Update lines 20-22

2. ⚠️ `deploy_gcnotificationservice.sh`
   - **Issue**: PROJECT_ID=`telepay-459221`
   - **Issue**: Service name: `pgp_notificationservice-10-26`
   - **Fix Required**: Update for pgp-live, rename service

3. ⚠️ `deploy_actual_eth_fix.sh`
   - **Issue**: Base directory points to `/OCTOBER/10-26`
   - **Issue**: Mixed service naming (some use `10-26` suffix)
   - **Fix Required**: Update BASE_DIR, standardize service names

4. ⚠️ `deploy_config_fixes.sh`
   - **Issue**: Base directory: `/OCTOBER/10-26`
   - **Issue**: Secret names use old scheme (`GCSPLIT2_QUEUE` vs `PGP_SPLIT2_QUEUE`)
   - **Fix Required**: Update paths and secret references

5. ⚠️ `deploy_message_tracking_migration.sh`
   - **Issue**: Cloud SQL instance: `telepay-459221:us-central1:telepaypsql`
   - **Fix Required**: Update to `pgp-live:us-central1:pgp-telepaypsql`

---

### ❌ Legacy Scripts (NOT for PGP_v1)

Scripts in `/OCTOBER/10-26/` directory are legacy and should not be used for PGP_v1.

---

## Recommended Execution Order for PGP_v1 Deployment

### Phase 1: Prerequisites (GCP Project Setup)
```bash
# Manual steps (not scripted):
# 1. Create pgp-live GCP project
# 2. Enable required APIs (Secret Manager, Cloud Run, Cloud SQL, Cloud Tasks)
# 3. Create Cloud SQL instance: pgp-live:us-central1:pgp-telepaypsql
# 4. Set up gcloud authentication
```

### Phase 2: Secrets & Infrastructure
```bash
# 1. Create all 77 secrets
./TOOLS_SCRIPTS_TESTS/scripts/create_pgp_live_secrets.sh

# 2. Update placeholder values in secrets:
#    - <VALUE_FROM_TELEPAY>: Copy from telepay-459221
#    - <PROJECT_NUM>: Get from Cloud Run after deployment
#    - <NEW_CLOUD_SQL_IP>: From Cloud SQL instance

# 3. Grant service account access
./TOOLS_SCRIPTS_TESTS/scripts/grant_pgp_live_secret_access.sh

# 4. Fix any newline issues
./TOOLS_SCRIPTS_TESTS/scripts/fix_secret_newlines.sh
```

### Phase 3: Cloud Tasks Queues
```bash
# Deploy all 17 queues in order:
./TOOLS_SCRIPTS_TESTS/scripts/deploy_gcwebhook_tasks_queues.sh
./TOOLS_SCRIPTS_TESTS/scripts/deploy_accumulator_tasks_queues.sh
./TOOLS_SCRIPTS_TESTS/scripts/deploy_gcsplit_tasks_queues.sh
./TOOLS_SCRIPTS_TESTS/scripts/deploy_hostpay_tasks_queues.sh
```

### Phase 4: Core Services Deployment
```bash
# Deploy in dependency order:
./TOOLS_SCRIPTS_TESTS/scripts/deploy_telepay_bot.sh        # PGP_SERVER_v1
./TOOLS_SCRIPTS_TESTS/scripts/deploy_backend_api.sh        # PGP_WEBAPI_v1
./TOOLS_SCRIPTS_TESTS/scripts/deploy_frontend.sh           # PGP_WEB_v1
./TOOLS_SCRIPTS_TESTS/scripts/deploy_np_webhook.sh         # PGP_NP_IPN_v1
./TOOLS_SCRIPTS_TESTS/scripts/deploy_broadcast_scheduler.sh # PGP_BROADCAST_v1
```

### Phase 5: Payment Processing Services
```bash
# Deploy remaining services:
# Use deploy_all_pgp_services.sh (after updating PROJECT_ID)
# OR deploy individually:
# - pgp-orchestrator-v1
# - pgp-invite-v1
# - pgp-split1/2/3-v1
# - pgp-hostpay1/2/3-v1
# - pgp-accumulator-v1
# - pgp-batchprocessor-v1
# - pgp-microbatchprocessor-v1
# - pgp-notifications-v1
```

### Phase 6: Post-Deployment
```bash
# 1. Update service URL secrets with actual Cloud Run URLs
# 2. Test notification flow
./TOOLS_SCRIPTS_TESTS/scripts/run_notification_test.sh

# 3. Verify all services are running
gcloud run services list --region=us-central1 --project=pgp-live

# 4. Set up Cloud Scheduler for broadcasts (if needed)
```

---

## Critical Files Missing from PGP_v1

### Database Schema Scripts
- ❌ Complete schema creation (CREATE TABLE statements)
- ❌ Index creation
- ❌ Constraint definitions
- ❌ Stored procedures/functions (if any)

**Found in**: `TOOLS_SCRIPTS_TESTS/migrations/001_create_complete_schema.sql`
**Status**: Exists but may need review for PGP_v1

### Database Migration Scripts
- ❌ Migration tracking system
- ❌ Rollback scripts for all migrations
- ❌ Migration execution order documentation

**Partial in**: `TOOLS_SCRIPTS_TESTS/migrations/` (needs organization)

### Individual Service Deployment Scripts
Missing individual deployment scripts for:
- ❌ `pgp-orchestrator-v1`
- ❌ `pgp-invite-v1`
- ❌ `pgp-split1-v1`, `pgp-split2-v1`, `pgp-split3-v1`
- ❌ `pgp-hostpay1-v1`, `pgp-hostpay2-v1`, `pgp-hostpay3-v1`
- ❌ `pgp-accumulator-v1`
- ❌ `pgp-batchprocessor-v1`, `pgp-microbatchprocessor-v1`

**Workaround**: Use `deploy_all_pgp_services.sh` after fixing PROJECT_ID

### Monitoring & Logging Setup
- ❌ Cloud Logging configuration
- ❌ Cloud Monitoring dashboards
- ❌ Alerting policies setup
- ❌ Error reporting configuration

### CI/CD Pipeline
- ❌ GitHub Actions workflows
- ❌ Cloud Build triggers
- ❌ Automated testing pipeline

---

## Security Considerations

### Secrets Management
✅ **GOOD**:
- All secrets use Google Cloud Secret Manager
- IAM permissions script provided
- Secrets rotated from old project (new keys generated)

⚠️ **CONCERNS**:
- CRITICAL wallet private keys stored as secrets
- No secret rotation policy defined
- No audit logging configuration for secret access

### Service Authentication
✅ **GOOD**:
- Services use signing keys for inter-service communication
- `TPS_HOSTPAY_SIGNING_KEY` for payment flow
- `WEBHOOK_SIGNING_KEY` for webhooks
- JWT tokens for API authentication

⚠️ **CONCERNS**:
- Some services deployed with `--allow-unauthenticated`
- No mention of VPC Service Controls
- No Cloud Armor (DDoS protection) configuration

### Database Security
✅ **GOOD**:
- Uses Cloud SQL with private IP
- Credentials in Secret Manager

⚠️ **CONCERNS**:
- No mention of SSL/TLS for database connections
- No database encryption at rest verification
- No backup strategy documented

---

## Performance Considerations

### Cloud Tasks Configuration
✅ **GOOD**:
- Rate limits configured per service type:
  - Telegram API: 8/sec (80% limit)
  - ChangeNow API: 10/sec
  - Blockchain: 5/sec
- Concurrency limits prevent overload

⚠️ **OPTIMIZATION NEEDED**:
- Fixed 60s backoff may be too aggressive for some failures
- No exponential backoff (max-doublings=0)
- 24h retry duration may be excessive for some operations

### Cloud Run Scaling
✅ **GOOD**:
- Min/max instances configured per service
- Resource limits (CPU/memory) defined

⚠️ **CONCERNS**:
- PGP_SERVER_v1: min-instances=1 (always running = cost)
- PGP_BROADCAST_v1: max-instances=1, concurrency=1 (bottleneck?)
- No autoscaling metrics configured

---

## Cost Optimization Opportunities

### Always-Running Services
```
PGP_SERVER_v1: min-instances=1 (1Gi memory)
PGP_NP_IPN_v1: min-instances=1 (512Mi memory)
```
**Recommendation**: Evaluate if these can use min-instances=0 with health checks

### Secret Access Frequency
**77 secrets × multiple service reads = high API calls**

**Recommendation**:
- Cache secrets in memory (with TTL)
- Use environment variable injection where possible

### Cloud Tasks Retries
**Infinite retries for 24h = potential cost accumulation on persistent failures**

**Recommendation**:
- Implement dead letter queue after N attempts
- Add alerting for stuck tasks

---

## Conclusion

### Summary

**Total Scripts Analyzed**: 24
**Core PGP_v1 Scripts**: 16 (66%)
**Scripts Needing Updates**: 5 (21%)
**Legacy/Deprecated**: 3 (13%)

### PGP_v1 Architecture Coverage

✅ **COMPLETE**:
- Secret initialization (77 secrets)
- IAM permission grants
- Cloud Tasks queue creation (17 queues)
- Core service deployments (5 critical services)
- Development environment setup

⚠️ **INCOMPLETE**:
- Individual service deployment scripts (missing 9 services)
- Database schema initialization
- Migration management
- Monitoring/logging setup
- CI/CD pipeline

❌ **MISSING**:
- Rollback procedures
- Disaster recovery scripts
- Load testing scripts
- Security hardening scripts

### Recommendations

1. **Immediate Actions**:
   - Update `deploy_all_pgp_services.sh` PROJECT_ID to `pgp-live`
   - Create individual deployment scripts for all 17 services
   - Document database schema migration strategy

2. **Short-Term**:
   - Implement database migration tracking
   - Create rollback scripts for all deployments
   - Set up monitoring and alerting
   - Document secret rotation procedures

3. **Long-Term**:
   - Implement CI/CD pipeline
   - Create infrastructure-as-code (Terraform/Pulumi)
   - Set up disaster recovery procedures
   - Implement cost optimization strategies

---

## Appendix: Quick Reference

### All 24 Scripts by Location

**TOOLS_SCRIPTS_TESTS/scripts/** (23 scripts):
- activate_venv.sh
- create_pgp_live_secrets.sh ✅
- deploy_accumulator_tasks_queues.sh ✅
- deploy_actual_eth_fix.sh ⚠️
- deploy_all_pgp_services.sh ⚠️
- deploy_backend_api.sh ✅
- deploy_broadcast_scheduler.sh ✅
- deploy_config_fixes.sh ⚠️
- deploy_frontend.sh ✅
- deploy_gcsplit_tasks_queues.sh ✅
- deploy_gcwebhook_tasks_queues.sh ✅
- deploy_hostpay_tasks_queues.sh ✅
- deploy_message_tracking_migration.sh ⚠️
- deploy_notification_feature.sh ✅
- deploy_np_webhook.sh ✅
- deploy_telepay_bot.sh ✅
- fix_secret_newlines.sh ✅
- grant_pgp_live_secret_access.sh ✅
- pause_broadcast_scheduler.sh ✅
- resume_broadcast_scheduler.sh ✅
- run_notification_test.sh ✅
- set_max_tokens.sh ✅
- setup_venv.sh ✅

**PGP_NOTIFICATIONS_v1/** (1 script):
- deploy_gcnotificationservice.sh ⚠️

**Legend**:
- ✅ = Core PGP_v1 script, ready to use
- ⚠️ = Needs updates (project ID, paths, naming)
- ❌ = Legacy/deprecated

---

**End of Analysis**
