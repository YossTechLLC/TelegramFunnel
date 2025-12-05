# TOOLS_SCRIPTS_TESTS Migration Checklist

**Project:** TelegramFunnel NOVEMBER/PGP_v1
**Date:** 2025-11-16
**Purpose:** Audit and migration plan for TOOLS_SCRIPTS_TESTS directory
**Scope:** 87 files across migrations/, scripts/, tests/, and tools/

---

## Executive Summary

This document provides a comprehensive analysis of all files in the TOOLS_SCRIPTS_TESTS directory to determine which files:
- ✅ **KEEP** - Already use PGP_v1 naming, ready for pgp-live deployment
- 🔄 **MODIFY** - Need updates to use PGP_v1 naming and pgp-live project
- ❌ **DELETE** - Obsolete files referencing old GC naming scheme

**Key Findings:**
- **Total Files:** 87 files
- **PGP_v1 Ready:** 2 files (create_pgp_live_secrets.sh, grant_pgp_live_secret_access.sh)
- **Need Modification:** 42+ files (deployment scripts, migrations, Python tools)
- **Old Naming References:** 85 files reference telepay-459221 or old GC naming
- **Migration Required:** Most files need project ID update (telepay-459221 → pgp-live)

---

## Table of Contents

1. [Part 1: MIGRATIONS Directory (2 files)](#part-1-migrations-directory)
2. [Part 2: SCRIPTS Directory (40 files)](#part-2-scripts-directory)
3. [Part 3: TESTS Directory (4 files)](#part-3-tests-directory)
4. [Part 4: TOOLS Directory (41 files)](#part-4-tools-directory)
5. [Part 5: Migration Strategy](#part-5-migration-strategy)
6. [Part 6: Action Plan](#part-6-action-plan)

---

## Part 1: MIGRATIONS Directory

**Location:** `/TOOLS_SCRIPTS_TESTS/migrations/`
**Total Files:** 2

### 1.1 Migration Files Analysis

#### ✅ KEEP (with modifications)

| File | Purpose | Action Required | Notes |
|------|---------|----------------|-------|
| `003_rename_gcwebhook1_columns.sql` | Renames gcwebhook1_* → pgp_orchestrator_* columns | 🔄 **MODIFY** - Already uses PGP naming but needs testing | Migration 003 updates processed_payments table columns to PGP naming |
| `003_rollback.sql` | Rollback script for migration 003 | 🔄 **MODIFY** - Companion to 003, needs testing | Reverses pgp_orchestrator_* → gcwebhook1_* |

**Detailed Analysis:**

**File: `003_rename_gcwebhook1_columns.sql`**
- **Status:** 🟢 PGP_v1 naming ready
- **Purpose:** Renames database columns from old GC naming to new PGP naming
- **Changes Required:** None (already uses PGP naming)
- **Risk:** LOW - Column rename only, no data loss
- **Dependencies:** Must run AFTER create_processed_payments_table.sql
- **Action:** ✅ KEEP - Test in pgp-live database
- **Changes:**
  - `gcwebhook1_processed` → `pgp_orchestrator_processed`
  - `gcwebhook1_processed_at` → `pgp_orchestrator_processed_at`
  - Index: `idx_gcwebhook1_processed` → `idx_pgp_orchestrator_processed`

**File: `003_rollback.sql`**
- **Status:** 🟢 PGP_v1 rollback ready
- **Purpose:** Rollback migration 003 if needed
- **Changes Required:** None (already uses PGP naming)
- **Risk:** MEDIUM - Only use if migration 003 fails
- **Action:** ✅ KEEP - Companion to migration 003

### 1.2 Migration Summary

**Decision:** ✅ **KEEP BOTH FILES**

These migration files are specifically designed for the PGP_v1 naming migration. They should be:
1. Tested in pgp-live database after initial schema setup
2. Executed AFTER all table creation scripts
3. Kept as part of migration history

**Next Steps:**
- Run after `create_processed_payments_table.sql` completes
- Verify column names match PGP_ORCHESTRATOR_v1 service expectations
- Document in pgp-live migration log

---

## Part 2: SCRIPTS Directory

**Location:** `/TOOLS_SCRIPTS_TESTS/scripts/`
**Total Files:** 40

### 2.1 Database Schema Scripts (SQL)

#### 2.1.1 Table Creation Scripts

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `create_batch_conversions_table.sql` | Create batch_conversions table | Generic (no GC/PGP refs) | ✅ KEEP |
| `create_broadcast_manager_table.sql` | Create broadcast_manager table | Generic | ✅ KEEP |
| `create_donation_keypad_state_table.sql` | Create donation_keypad_state table | ⚠️ References GCDonationHandler | 🔄 MODIFY |
| `create_failed_transactions_table.sql` | Create failed_transactions table | ⚠️ References GCWebhook1 | 🔄 MODIFY |
| `create_processed_payments_table.sql` | Create processed_payments table | ⚠️ Uses gcwebhook1_* columns | 🔄 MODIFY |

**Detailed Analysis:**

**`create_batch_conversions_table.sql`**
- **Status:** 🟢 Ready for pgp-live
- **Action:** ✅ KEEP AS-IS
- **Changes:** None needed
- **Notes:** Generic table, no service-specific naming

**`create_broadcast_manager_table.sql`**
- **Status:** 🟢 Ready for pgp-live
- **Action:** ✅ KEEP AS-IS
- **Changes:** None needed
- **Notes:** Used by PGP_BROADCAST_v1 service

**`create_donation_keypad_state_table.sql`**
- **Status:** 🟡 Needs review
- **Action:** 🔄 MODIFY - Update comments/documentation
- **Changes Required:**
  - Line ~5: Comment references "GCDonationHandler" → Update to "PGP_DONATIONS_v1"
- **Risk:** LOW - Comment only
- **Notes:** Table name is generic, only comments need updating

**`create_failed_transactions_table.sql`**
- **Status:** 🟡 Needs review
- **Action:** 🔄 MODIFY - Update comments
- **Changes Required:**
  - Comments reference "GCWebhook1" → Update to "PGP_ORCHESTRATOR_v1"
- **Risk:** LOW - Comment only

**`create_processed_payments_table.sql`**
- **Status:** 🔴 OLD NAMING - CRITICAL
- **Action:** 🔄 MODIFY - Update column names
- **Changes Required:**
  - Line 17-18: `gcwebhook1_processed` → `pgp_orchestrator_processed`
  - Line 17-18: `gcwebhook1_processed_at` → `pgp_orchestrator_processed_at`
  - Line 42: Index `idx_processed_payments_webhook1_status` → `idx_processed_payments_orchestrator_status`
  - Line 50: Comment "GCWebhook1" → "PGP_ORCHESTRATOR_v1"
- **Alternative:** ❌ DELETE this script if migration 003 handles it
- **Decision:** Keep MODIFIED version OR delete if migration 003 creates table with correct names

#### 2.1.2 Column Addition/Migration Scripts

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `add_actual_eth_amount_columns.sql` | Add actual_eth_amount columns | ⚠️ References GCSplit1 | 🔄 MODIFY |
| `add_actual_eth_to_split_payout_que.sql` | Add actual_eth to split_payout_que | ⚠️ References GCSplit1 | 🔄 MODIFY |
| `add_donation_message_column.sql` | Add donation_message_id column | Generic | ✅ KEEP |
| `add_message_tracking_columns.sql` | Add message tracking columns | Generic | ✅ KEEP |
| `add_notification_columns.sql` | Add notification columns | Generic | ✅ KEEP |
| `add_nowpayments_outcome_usd_column.sql` | Add nowpayments_outcome_usd column | ⚠️ References GCWebhook1 | 🔄 MODIFY |

**Detailed Analysis:**

**`add_actual_eth_amount_columns.sql`**
- **Status:** 🟡 Needs review
- **Action:** 🔄 MODIFY - Update comments
- **Changes Required:**
  - Comments reference "GCSplit1" → "PGP_SPLIT1_v1"
- **Risk:** LOW - Comment only

**`add_nowpayments_outcome_usd_column.sql`**
- **Status:** 🟡 Needs review
- **Action:** 🔄 MODIFY - Update comments
- **Changes Required:**
  - Comments reference "GCWebhook1" → "PGP_ORCHESTRATOR_v1"
- **Risk:** LOW - Comment only

**Others (add_donation_message_column.sql, add_message_tracking_columns.sql, add_notification_columns.sql)**
- **Status:** 🟢 Ready
- **Action:** ✅ KEEP AS-IS
- **Changes:** None needed

#### 2.1.3 Fix/Maintenance Scripts

| File | Purpose | Action |
|------|---------|--------|
| `fix_numeric_precision_overflow.sql` | Fix NUMERIC precision | ✅ KEEP |
| `fix_numeric_precision_overflow_v2.sql` | Fix NUMERIC precision v2 | ✅ KEEP |
| `fix_split_payout_hostpay_unique_id_length.sql` | Fix unique_id length | ✅ KEEP |

**Decision:** ✅ **KEEP ALL** - Generic database fixes

#### 2.1.4 Rollback Scripts

| File | Purpose | Action |
|------|---------|--------|
| `rollback_actual_eth_amount_columns.sql` | Rollback actual_eth columns | ✅ KEEP |
| `rollback_broadcast_manager_table.sql` | Rollback broadcast_manager table | ✅ KEEP |
| `rollback_donation_message_column.sql` | Rollback donation_message_id | ✅ KEEP |
| `rollback_message_tracking_columns.sql` | Rollback message tracking | ✅ KEEP |
| `rollback_notification_columns.sql` | Rollback notification columns | ✅ KEEP |

**Decision:** ✅ **KEEP ALL** - Important for disaster recovery

#### 2.1.5 Verification Scripts

| File | Purpose | Action |
|------|---------|--------|
| `verify_broadcast_integrity.sql` | Verify broadcast data integrity | ✅ KEEP |

**Decision:** ✅ **KEEP** - Important for validation

---

### 2.2 Deployment Scripts (Bash)

#### 2.2.1 Cloud Run Service Deployment Scripts

| File | Service Target | Naming Scheme | Action |
|------|---------------|--------------|--------|
| `deploy_broadcast_scheduler.sh` | PGP_BROADCAST_v1 | 🟢 PGP_v1 naming | 🔄 MODIFY |
| `deploy_telepay_bot.sh` | PGP_SERVER_v1 | 🟢 PGP_v1 naming | 🔄 MODIFY |
| `deploy_np_webhook.sh` | PGP_NP_IPN_v1 | 🟢 PGP_v1 naming | 🔄 MODIFY |
| `deploy_backend_api.sh` | PGP_WEBAPI_v1 | 🟢 PGP_v1 naming | 🔄 MODIFY |
| `deploy_frontend.sh` | Frontend web | Generic | 🔄 MODIFY |
| `deploy_gcbroadcastservice_message_tracking.sh` | ❌ OLD: GCBroadcastService-10-26 | 🔴 OLD naming | ❌ DELETE |
| `deploy_gcsubscriptionmonitor.sh` | ❌ OLD: GCSubscriptionMonitor-10-26 | 🔴 OLD naming | ❌ DELETE |

**Detailed Analysis:**

**`deploy_broadcast_scheduler.sh`**
- **Status:** 🟢 PGP_v1 ready, telepay-459221 hardcoded
- **Action:** 🔄 **MODIFY** - Update project ID
- **Changes Required:**
  - Line 8: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`
  - Line 11: `SOURCE_DIR=...PGP_BROADCAST_v1` ✅ Already correct
  - Line 43-44: `BOT_USERNAME_SECRET` → `TELEGRAM_BOT_USERNAME` (secret name)
  - Verify all 10 environment variables match NEW secret names from SECRET_NAMING_MIGRATION_CHECKLIST.md
- **Service Name:** `pgp-broadcast-v1` ✅ Correct
- **Secret Names:** Need updating to match NEW naming scheme (PGP_*)
- **Risk:** MEDIUM - Must match new secret names exactly

**`deploy_telepay_bot.sh`**
- **Status:** 🟢 PGP_v1 ready, telepay-459221 hardcoded
- **Action:** 🔄 **MODIFY** - Update project ID + Cloud SQL instance
- **Changes Required:**
  - No explicit `PROJECT_ID` variable, but uses defaults
  - Line 20: `SOURCE_DIR=...PGP_SERVER_v1` ✅ Already correct
  - Line 86: `--add-cloudsql-instances=telepay-459221:us-central1:telepaypsql` → `pgp-live:us-central1:pgp-telepaypsql`
  - Secret names in lines 56-64: Already use generic names (TELEGRAM_BOT_SECRET_NAME, etc.)
  - Line 69: `--set-secrets=$SECRET=$SECRET:latest` - Correct pattern
- **Service Name:** `pgp-server-v1` ✅ Correct
- **Risk:** MEDIUM - Cloud SQL instance name must match pgp-live

**`deploy_np_webhook.sh`**
- **Status:** 🟢 PGP_v1 ready, no hardcoded project
- **Action:** 🔄 **MODIFY** - Update secret names
- **Changes Required:**
  - Line 20: `SOURCE_DIR=...PGP_NP_IPN_v1` ✅ Already correct
  - Lines 64-77: Secret names already use NEW naming:
    - `PGP_ORCHESTRATOR_QUEUE` ✅
    - `PGP_ORCHESTRATOR_URL` ✅
    - `PGP_INVITE_QUEUE` ✅
    - `PGP_INVITE_URL` ✅
    - `PGP_SERVER_URL` ✅
  - All secret names already match PGP_v1 scheme ✅
- **Service Name:** `pgp-np-ipn-v1` ✅ Correct
- **Risk:** LOW - Already uses correct naming
- **Action:** 🔄 **VERIFY** - Confirm secret names exist in pgp-live

**`deploy_backend_api.sh`**
- **Status:** 🟢 PGP_v1 ready
- **Action:** ✅ **KEEP AS-IS**
- **Changes Required:** None - No secrets, no hardcoded project
- **Service Name:** `pgp-webapi-v1` ✅ Correct
- **Risk:** VERY LOW

**`deploy_frontend.sh`**
- **Status:** 🟢 Generic
- **Action:** 🔄 **MODIFY** - Update project ID if hardcoded
- **Changes Required:** Need to read file to verify
- **Risk:** LOW

**`deploy_gcbroadcastservice_message_tracking.sh`**
- **Status:** 🔴 OLD NAMING - OBSOLETE
- **Action:** ❌ **DELETE**
- **Reason:**
  - Line 9: Service name `pgp_broadcastservice-10-26` (OLD naming)
  - Line 16: Source dir `/OCTOBER/10-26/GCBroadcastService-10-26` (OLD location)
  - This service has been replaced by `PGP_BROADCAST_v1`
  - `deploy_broadcast_scheduler.sh` is the NEW deployment script
- **Migration:** Already replaced by `deploy_broadcast_scheduler.sh`

**`deploy_gcsubscriptionmonitor.sh`**
- **Status:** 🔴 OLD NAMING - OBSOLETE
- **Action:** ❌ **DELETE**
- **Reason:**
  - Deploys `GCSubscriptionMonitor-10-26` from OCTOBER directory
  - This functionality was consolidated into `PGP_SERVER_v1`
  - No longer a separate service
- **Migration:** Functionality moved to PGP_SERVER_v1

#### 2.2.2 Cloud Tasks Queue Deployment Scripts

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `deploy_accumulator_tasks_queues.sh` | Deploy accumulator queues | 🟢 PGP_v1 naming | 🔄 MODIFY |
| `deploy_gcsplit_tasks_queues.sh` | Deploy split queues | 🟢 PGP_v1 naming | 🔄 MODIFY |
| `deploy_gcwebhook_tasks_queues.sh` | Deploy orchestrator/invite queues | 🟢 PGP_v1 naming | 🔄 MODIFY |
| `deploy_hostpay_tasks_queues.sh` | Deploy hostpay queues | 🟢 PGP_v1 naming | 🔄 MODIFY |

**Detailed Analysis:**

**All queue deployment scripts (`deploy_*_tasks_queues.sh`)**
- **Status:** 🟢 PGP_v1 queue naming ready
- **Action:** 🔄 **MODIFY** - Update project ID only
- **Changes Required:**
  - Line ~7: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`
  - Queue names already use PGP_v1 naming:
    - `pgp-accumulator-queue-v1` ✅
    - `pgp-invite-queue-v1` ✅
    - `pgp-orchestrator-queue-v1` ✅
    - `pgp-split1-queue-v1` ✅
    - etc.
- **Risk:** LOW - Only project ID needs updating
- **Example from `deploy_gcwebhook_tasks_queues.sh`:**
  - Line 7: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`
  - Line 25: Queue name `pgp-invite-queue-v1` ✅ Already correct

#### 2.2.3 Feature Deployment Scripts

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `deploy_actual_eth_fix.sh` | Deploy actual_eth migration | ⚠️ Unknown | 🔄 REVIEW |
| `deploy_config_fixes.sh` | Deploy config fixes | ⚠️ Unknown | 🔄 REVIEW |
| `deploy_message_tracking_migration.sh` | Deploy message tracking | ⚠️ Unknown | 🔄 REVIEW |
| `deploy_notification_feature.sh` | Deploy notification feature | ⚠️ Unknown | 🔄 REVIEW |

**Note:** Need to read these files to determine if they're for old GC services or PGP_v1 services.

#### 2.2.4 Operational Scripts

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `pause_broadcast_scheduler.sh` | Pause Cloud Scheduler job | telepay-459221 | 🔄 MODIFY |
| `resume_broadcast_scheduler.sh` | Resume Cloud Scheduler job | telepay-459221 | 🔄 MODIFY |
| `fix_secret_newlines.sh` | Fix secret formatting | telepay-459221 | 🔄 MODIFY |

**Detailed Analysis:**

**`pause_broadcast_scheduler.sh` & `resume_broadcast_scheduler.sh`**
- **Status:** 🟢 Generic functionality
- **Action:** 🔄 **MODIFY** - Update project ID
- **Changes Required:**
  - Line 8: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`
  - Line 10: `JOB_NAME="broadcast-scheduler-daily"` - Verify this job name in pgp-live
- **Risk:** LOW - Simple project ID update

**`fix_secret_newlines.sh`**
- **Status:** 🟢 Utility script
- **Action:** 🔄 **MODIFY** - Update project ID
- **Changes Required:**
  - Update any hardcoded project references
- **Risk:** LOW

#### 2.2.5 PGP-Live Specific Scripts

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `create_pgp_live_secrets.sh` | Create all 77 secrets in pgp-live | 🟢 PGP_v1 naming | ✅ KEEP |
| `grant_pgp_live_secret_access.sh` | Grant service account access | 🟢 PGP_v1 naming | ✅ KEEP |

**Decision:** ✅ **KEEP BOTH** - These are NEW scripts specifically designed for pgp-live deployment

---

### 2.3 Scripts Summary

**Total Files:** 40

**Action Breakdown:**
- ✅ **KEEP AS-IS:** 15 files (generic SQL, rollbacks, verification, pgp-live scripts)
- 🔄 **MODIFY:** 23 files (deployment scripts needing project ID update, SQL needing comment updates)
- ❌ **DELETE:** 2 files (deploy_gcbroadcastservice_message_tracking.sh, deploy_gcsubscriptionmonitor.sh)

**Priority Actions:**
1. **CRITICAL:** Update `deploy_broadcast_scheduler.sh` secret names to match NEW scheme
2. **HIGH:** Update all deployment scripts `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`
3. **HIGH:** Update Cloud SQL instance names in deployment scripts
4. **MEDIUM:** Update SQL script comments (GC* → PGP_*)
5. **LOW:** Delete 2 obsolete deployment scripts

---

## Part 3: TESTS Directory

**Location:** `/TOOLS_SCRIPTS_TESTS/tests/`
**Total Files:** 4

### 3.1 Test Files Analysis

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `test_error_classifier.py` | Test error classification logic | Generic | ✅ KEEP |
| `test_subscription_integration.py` | Test subscription integration | ⚠️ telepay-459221 | 🔄 MODIFY |
| `test_subscription_load.py` | Test subscription load handling | ⚠️ telepay-459221 | 🔄 MODIFY |
| `test_token_manager_retry.py` | Test token manager retry logic | Generic | ✅ KEEP |

**Detailed Analysis:**

**`test_error_classifier.py`**
- **Status:** 🟢 Generic test
- **Action:** ✅ **KEEP AS-IS**
- **Changes:** None needed
- **Risk:** NONE

**`test_subscription_integration.py`**
- **Status:** 🟡 Needs review
- **Action:** 🔄 **MODIFY** - Update project ID
- **Expected Changes:**
  - PROJECT_ID or connection strings referencing telepay-459221
  - Update to pgp-live
- **Risk:** LOW

**`test_subscription_load.py`**
- **Status:** 🟡 Needs review
- **Action:** 🔄 **MODIFY** - Update project ID
- **Expected Changes:**
  - PROJECT_ID or connection strings referencing telepay-459221
  - Update to pgp-live
- **Risk:** LOW

**`test_token_manager_retry.py`**
- **Status:** 🟢 Generic test
- **Action:** ✅ **KEEP AS-IS**
- **Changes:** None needed
- **Risk:** NONE

### 3.2 Tests Summary

**Total Files:** 4

**Action Breakdown:**
- ✅ **KEEP AS-IS:** 2 files (test_error_classifier.py, test_token_manager_retry.py)
- 🔄 **MODIFY:** 2 files (test_subscription_integration.py, test_subscription_load.py)
- ❌ **DELETE:** 0 files

---

## Part 4: TOOLS Directory

**Location:** `/TOOLS_SCRIPTS_TESTS/tools/`
**Total Files:** 41

### 4.1 Database Migration Execution Tools

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `execute_actual_eth_migration.py` | Execute actual_eth migration | telepay-459221 | 🔄 MODIFY |
| `execute_actual_eth_que_migration.py` | Execute actual_eth queue migration | telepay-459221 | 🔄 MODIFY |
| `execute_broadcast_migration.py` | Execute broadcast_manager migration | telepay-459221 | 🔄 MODIFY |
| `execute_conversation_state_migration.py` | Execute conversation_state migration | telepay-459221 | 🔄 MODIFY |
| `execute_donation_keypad_state_migration.py` | Execute donation_keypad_state migration | telepay-459221 | 🔄 MODIFY |
| `execute_donation_message_migration.py` | Execute donation_message migration | telepay-459221 | 🔄 MODIFY |
| `execute_failed_transactions_migration.py` | Execute failed_transactions migration | telepay-459221 | 🔄 MODIFY |
| `execute_landing_page_schema_migration.py` | Execute landing_page migration | telepay-459221 | 🔄 MODIFY |
| `execute_message_tracking_migration.py` | Execute message_tracking migration | telepay-459221 | 🔄 MODIFY |
| `execute_migrations.py` | Generic migration executor | telepay-459221 | 🔄 MODIFY |
| `execute_notification_migration.py` | Execute notification migration | telepay-459221 | 🔄 MODIFY |
| `execute_outcome_usd_migration.py` | Execute outcome_usd migration | telepay-459221 | 🔄 MODIFY |
| `execute_payment_id_migration.py` | Execute payment_id migration | telepay-459221 | 🔄 MODIFY |
| `execute_price_amount_migration.py` | Execute price_amount migration | telepay-459221 | 🔄 MODIFY |
| `execute_processed_payments_migration.py` | Execute processed_payments migration | telepay-459221 | 🔄 MODIFY |
| `execute_unique_id_migration.py` | Execute unique_id migration | telepay-459221 | 🔄 MODIFY |

**Analysis:**

All `execute_*_migration.py` files follow the same pattern:
- **Status:** 🟡 telepay-459221 hardcoded
- **Action:** 🔄 **MODIFY** - Update project ID
- **Changes Required (common pattern):**
  ```python
  # Line ~18: Update project ID
  project_id = "telepay-459221"  →  project_id = "pgp-live"

  # Cloud SQL connection name
  INSTANCE_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"
  →  INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"
  ```
- **Risk:** MEDIUM - Database connection strings must be exact
- **Dependencies:** All depend on Secret Manager secrets (DATABASE_HOST_SECRET, etc.)

**Example from `execute_broadcast_migration.py`:**
- Line 18: `project_id = "telepay-459221"` → `project_id = "pgp-live"`
- Line 38-40: Database credentials fetched from Secret Manager ✅ (no changes needed)
- Line 50: Migration SQL path is relative ✅ (no changes needed)

### 4.2 Database Schema Check Tools

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `check_broadcast_manager_table.py` | Check broadcast_manager schema | telepay-459221 | 🔄 MODIFY |
| `check_client_table_db.py` | Check client_table schema | telepay-459221 | 🔄 MODIFY |
| `check_conversion_status_schema.py` | Check conversion_status schema | telepay-459221 | 🔄 MODIFY |
| `check_migration_002.py` | Check migration 002 status | telepay-459221 | 🔄 MODIFY |
| `check_payment_amounts.py` | Check payment amounts | telepay-459221 | 🔄 MODIFY |
| `check_payout_details.py` | Check payout details | telepay-459221 | 🔄 MODIFY |
| `check_payout_schema.py` | Check payout schema | telepay-459221 | 🔄 MODIFY |
| `check_schema.py` | Generic schema checker | telepay-459221 | 🔄 MODIFY |
| `check_schema_details.py` | Detailed schema checker | telepay-459221 | 🔄 MODIFY |

**Analysis:**

All `check_*_schema.py` and `check_*.py` files need the same updates:
- **Status:** 🟡 telepay-459221 hardcoded
- **Action:** 🔄 **MODIFY** - Update project ID + Cloud SQL instance
- **Changes Required:**
  ```python
  PROJECT_ID = "telepay-459221"  →  PROJECT_ID = "pgp-live"
  INSTANCE_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"
  →  INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"
  ```
- **Risk:** MEDIUM - Important for verifying pgp-live database state

### 4.3 Database Fix/Population Tools

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `fix_payout_accumulation_schema.py` | Fix payout schema issues | telepay-459221 | 🔄 MODIFY |
| `backfill_missing_broadcast_entries.py` | Backfill broadcast data | telepay-459221 | 🔄 MODIFY |
| `populate_broadcast_manager.py` | Populate broadcast_manager | telepay-459221 | 🔄 MODIFY |
| `manual_insert_payment_4479119533.py` | Manual payment insertion | telepay-459221 | ❌ DELETE |

**Analysis:**

**`fix_payout_accumulation_schema.py`, `backfill_missing_broadcast_entries.py`, `populate_broadcast_manager.py`**
- **Status:** 🟡 telepay-459221 hardcoded
- **Action:** 🔄 **MODIFY** - Update project ID
- **Changes:** Same pattern as migration scripts

**`manual_insert_payment_4479119533.py`**
- **Status:** 🔴 ONE-TIME MANUAL FIX
- **Action:** ❌ **DELETE**
- **Reason:** This is a one-off script for a specific payment_id (4479119533) in telepay-459221
- **Migration:** Not needed in pgp-live (fresh database)

### 4.4 Database Migration Scripts (run_* pattern)

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `run_migration_002_email_change.py` | Run migration 002 | telepay-459221 | 🔄 MODIFY |
| `run_migration_unique_constraints.py` | Run unique constraint migration | telepay-459221 | 🔄 MODIFY |

**Analysis:**

Same pattern as `execute_*_migration.py` scripts:
- **Status:** 🟡 telepay-459221 hardcoded
- **Action:** 🔄 **MODIFY** - Update project ID

### 4.5 Test/Validation Tools

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `test_batch_query.py` | Test batch query performance | telepay-459221 | 🔄 MODIFY |
| `test_changenow_precision.py` | Test ChangeNOW precision | Generic | ✅ KEEP |
| `test_fetch_due_broadcasts.py` | Test broadcast fetching | telepay-459221 | 🔄 MODIFY |
| `test_idempotency_constraint.py` | Test idempotency constraints | telepay-459221 | 🔄 MODIFY |
| `test_manual_broadcast_message_tracking.py` | Test broadcast message tracking | telepay-459221 | 🔄 MODIFY |
| `test_notification_flow.py` | Test notification workflow | telepay-459221 + PGP_v1 URLs | 🔄 MODIFY |
| `test_payout_database_methods.py` | Test payout database methods | telepay-459221 | 🔄 MODIFY |
| `verify_batch_success.py` | Verify batch success | telepay-459221 | 🔄 MODIFY |
| `verify_package.py` | Verify package installation | Generic | ✅ KEEP |

**Analysis:**

**`test_notification_flow.py`** (Special Case)
- **Status:** 🟡 MIXED - Has both telepay-459221 AND PGP_v1 naming
- **Action:** 🔄 **MODIFY** - Update project ID + service URLs
- **Changes Required:**
  - Line 21: `PROJECT_ID = "telepay-459221"` → `PROJECT_ID = "pgp-live"`
  - Line 22: `INSTANCE_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"` → `pgp-live:us-central1:pgp-telepaypsql`
  - Line 28: `NP_WEBHOOK_URL = "https://PGP_NP_IPN_v1-291176869049..."` → Update to pgp-live URL
  - Service URL format needs updating to pgp-live project number
- **Risk:** MEDIUM - Tests full notification flow

**All other test_*.py files:**
- **Status:** 🟡 telepay-459221 hardcoded
- **Action:** 🔄 **MODIFY** - Update project ID
- **Risk:** MEDIUM - Important for validating pgp-live

**`test_changenow_precision.py`, `verify_package.py`:**
- **Status:** 🟢 Generic
- **Action:** ✅ **KEEP AS-IS**

### 4.6 Bash Test Scripts

| File | Purpose | Naming Scheme | Action |
|------|---------|--------------|--------|
| `run_notification_test.sh` | Run notification test | ⚠️ Unknown | 🔄 REVIEW |

**Note:** Need to read this file to determine action

### 4.7 Tools Summary

**Total Files:** 41

**Action Breakdown:**
- ✅ **KEEP AS-IS:** 2 files (test_changenow_precision.py, verify_package.py)
- 🔄 **MODIFY:** 38 files (all migration, check, test, and validation tools)
- ❌ **DELETE:** 1 file (manual_insert_payment_4479119533.py)

**Common Modifications Needed:**
1. **PROJECT_ID:** `"telepay-459221"` → `"pgp-live"`
2. **Cloud SQL Instance:** `telepay-459221:us-central1:telepaypsql` → `pgp-live:us-central1:pgp-telepaypsql`
3. **Service URLs:** Update project number in Cloud Run URLs (e.g., `291176869049` → pgp-live project number)

---

## Part 5: Migration Strategy

### 5.1 Overall Statistics

**Total Files:** 87

**By Directory:**
- migrations/: 2 files
- scripts/: 40 files
- tests/: 4 files
- tools/: 41 files

**By Action Required:**

| Action | Count | Percentage |
|--------|-------|-----------|
| ✅ KEEP AS-IS | 19 | 21.8% |
| 🔄 MODIFY | 65 | 74.7% |
| ❌ DELETE | 3 | 3.4% |

**Files Ready for pgp-live (KEEP AS-IS):**
1. create_pgp_live_secrets.sh ✅
2. grant_pgp_live_secret_access.sh ✅
3. create_batch_conversions_table.sql ✅
4. create_broadcast_manager_table.sql ✅
5. add_donation_message_column.sql ✅
6. add_message_tracking_columns.sql ✅
7. add_notification_columns.sql ✅
8. fix_numeric_precision_overflow.sql ✅
9. fix_numeric_precision_overflow_v2.sql ✅
10. fix_split_payout_hostpay_unique_id_length.sql ✅
11. rollback_actual_eth_amount_columns.sql ✅
12. rollback_broadcast_manager_table.sql ✅
13. rollback_donation_message_column.sql ✅
14. rollback_message_tracking_columns.sql ✅
15. rollback_notification_columns.sql ✅
16. verify_broadcast_integrity.sql ✅
17. deploy_backend_api.sh ✅
18. test_error_classifier.py ✅
19. test_token_manager_retry.py ✅
20. test_changenow_precision.py ✅
21. verify_package.py ✅

**Files to DELETE:**
1. deploy_gcbroadcastservice_message_tracking.sh ❌ (replaced by deploy_broadcast_scheduler.sh)
2. deploy_gcsubscriptionmonitor.sh ❌ (functionality moved to PGP_SERVER_v1)
3. manual_insert_payment_4479119533.py ❌ (one-time fix for telepay-459221)

**Files to MODIFY (65 total):**
- 2 migration files (003_*.sql) - Already use PGP naming, just need testing
- 23 scripts - Mostly project ID updates
- 2 test files - Project ID updates
- 38 tools - Project ID + Cloud SQL instance updates

### 5.2 Modification Patterns

**Pattern 1: Simple Project ID Update (60+ files)**
```python
# OLD
PROJECT_ID = "telepay-459221"
INSTANCE_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"

# NEW
PROJECT_ID = "pgp-live"
INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"
```

**Pattern 2: Cloud Run Service URLs (test_notification_flow.py, others)**
```python
# OLD
NP_WEBHOOK_URL = "https://PGP_NP_IPN_v1-291176869049.us-central1.run.app"

# NEW (after pgp-live deployment)
NP_WEBHOOK_URL = "https://pgp-np-ipn-v1-{PGP_LIVE_PROJECT_NUM}.us-central1.run.app"
```

**Pattern 3: Secret Names in Deployment Scripts**
```bash
# deploy_broadcast_scheduler.sh needs secret name updates
# OLD secret names (telepay-459221)
BOT_TOKEN → TELEGRAM_BOT_SECRET_NAME
BOT_USERNAME → TELEGRAM_BOT_USERNAME

# NEW secret names (pgp-live) - From SECRET_NAMING_MIGRATION_CHECKLIST.md
# Need to verify all environment variables match NEW secret names
```

**Pattern 4: SQL Comment Updates**
```sql
-- OLD
COMMENT ON COLUMN processed_payments.gcwebhook1_processed IS 'Flag indicating if GCWebhook1...';

-- NEW
COMMENT ON COLUMN processed_payments.pgp_orchestrator_processed IS 'Flag indicating if PGP_ORCHESTRATOR_v1...';
```

### 5.3 Critical Dependencies

**Before modifying any files, ensure:**

1. ✅ **pgp-live project exists** in Google Cloud
2. ✅ **All 77 secrets created** in pgp-live (run create_pgp_live_secrets.sh)
3. ✅ **Service account permissions granted** (run grant_pgp_live_secret_access.sh)
4. ✅ **Cloud SQL instance created** in pgp-live (pgp-telepaypsql)
5. ✅ **Database created** (client_table or equivalent)
6. ✅ **Cloud Run services deployed** (to get project number for URLs)

**Order of Operations:**
1. Create pgp-live infrastructure (Cloud SQL, Secret Manager)
2. Run create_pgp_live_secrets.sh (create all 77 secrets)
3. Run grant_pgp_live_secret_access.sh (grant service account access)
4. Modify TOOLS_SCRIPTS_TESTS files (update project IDs)
5. Run database schema creation scripts
6. Run migration scripts
7. Deploy Cloud Run services
8. Create Cloud Tasks queues
9. Update test scripts with deployed service URLs
10. Run validation tests

---

## Part 6: Action Plan

### 6.1 Phase 1: Cleanup (Delete Obsolete Files)

**Priority:** HIGH
**Risk:** NONE
**Duration:** 5 minutes

```bash
# Delete obsolete deployment scripts
rm /TOOLS_SCRIPTS_TESTS/scripts/deploy_gcbroadcastservice_message_tracking.sh
rm /TOOLS_SCRIPTS_TESTS/scripts/deploy_gcsubscriptionmonitor.sh

# Delete one-time manual fix
rm /TOOLS_SCRIPTS_TESTS/tools/manual_insert_payment_4479119533.py
```

**Verification:**
```bash
# Should return 84 files (87 - 3)
find /TOOLS_SCRIPTS_TESTS -type f | wc -l
```

---

### 6.2 Phase 2: Update Deployment Scripts (HIGH Priority)

**Priority:** HIGH
**Risk:** MEDIUM
**Duration:** 2-4 hours

**Files to Update (23 files):**

#### 6.2.1 Service Deployment Scripts (7 files)

1. **deploy_broadcast_scheduler.sh** 🔴 CRITICAL
   - Update: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`
   - **CRITICAL:** Update secret environment variable names to match NEW scheme:
     ```bash
     # OLD (telepay-459221 secret names)
     BOT_TOKEN_SECRET=projects/${PROJECT_ID}/secrets/BOT_TOKEN/versions/latest
     BOT_USERNAME_SECRET=projects/${PROJECT_ID}/secrets/BOT_USERNAME/versions/latest

     # NEW (pgp-live secret names)
     BOT_TOKEN_SECRET=projects/${PROJECT_ID}/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest
     BOT_USERNAME_SECRET=projects/${PROJECT_ID}/secrets/TELEGRAM_BOT_USERNAME/versions/latest
     BROADCAST_AUTO_INTERVAL_SECRET=projects/${PROJECT_ID}/secrets/BROADCAST_AUTO_INTERVAL/versions/latest
     BROADCAST_MANUAL_INTERVAL_SECRET=projects/${PROJECT_ID}/secrets/BROADCAST_MANUAL_INTERVAL/versions/latest
     # ... all 10 environment variables
     ```
   - Reference: SECRET_NAMING_MIGRATION_CHECKLIST.md for correct secret names

2. **deploy_telepay_bot.sh**
   - Update: Cloud SQL instance `telepay-459221:us-central1:telepaypsql` → `pgp-live:us-central1:pgp-telepaypsql`
   - Secret names already correct ✅

3. **deploy_np_webhook.sh**
   - Verify secret names (already use PGP_* naming) ✅
   - No changes needed

4. **deploy_backend_api.sh**
   - No changes needed ✅

5. **deploy_frontend.sh**
   - Read file and update if needed

6. **deploy_config_fixes.sh** (need to review)

7. **deploy_message_tracking_migration.sh** (need to review)

#### 6.2.2 Queue Deployment Scripts (4 files)

1. **deploy_accumulator_tasks_queues.sh**
   - Update: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`

2. **deploy_gcsplit_tasks_queues.sh**
   - Update: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`

3. **deploy_gcwebhook_tasks_queues.sh**
   - Update: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`

4. **deploy_hostpay_tasks_queues.sh**
   - Update: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`

#### 6.2.3 Operational Scripts (3 files)

1. **pause_broadcast_scheduler.sh**
   - Update: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`

2. **resume_broadcast_scheduler.sh**
   - Update: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`

3. **fix_secret_newlines.sh**
   - Update: `PROJECT_ID="telepay-459221"` → `PROJECT_ID="pgp-live"`

**Verification:**
```bash
# After updates, search for any remaining telepay-459221 references in scripts
grep -r "telepay-459221" /TOOLS_SCRIPTS_TESTS/scripts/*.sh
# Should only appear in comments/documentation
```

---

### 6.3 Phase 3: Update SQL Scripts (MEDIUM Priority)

**Priority:** MEDIUM
**Risk:** LOW (mostly comment updates)
**Duration:** 1-2 hours

**Files to Update (5 files):**

1. **create_donation_keypad_state_table.sql**
   - Update comment: "GCDonationHandler" → "PGP_DONATIONS_v1"

2. **create_failed_transactions_table.sql**
   - Update comment: "GCWebhook1" → "PGP_ORCHESTRATOR_v1"

3. **create_processed_payments_table.sql** 🔴 CRITICAL DECISION NEEDED
   - **Option A:** Modify to use `pgp_orchestrator_*` column names
   - **Option B:** Delete this file if migration 003 handles table creation
   - **Recommendation:** DELETE - Migration 003 handles the renaming

4. **add_actual_eth_amount_columns.sql**
   - Update comment: "GCSplit1" → "PGP_SPLIT1_v1"

5. **add_nowpayments_outcome_usd_column.sql**
   - Update comment: "GCWebhook1" → "PGP_ORCHESTRATOR_v1"

**Verification:**
```bash
# Search for old GC naming in SQL files
grep -i "gcwebhook1\|gcsplit1\|gcdonation" /TOOLS_SCRIPTS_TESTS/scripts/*.sql
# Should only appear in migration 003 and rollback scripts
```

---

### 6.4 Phase 4: Update Python Migration Tools (HIGH Priority)

**Priority:** HIGH
**Risk:** MEDIUM
**Duration:** 2-3 hours

**Files to Update (16 execute_*.py files):**

All follow the same pattern. Create a shell script to automate:

```bash
#!/bin/bash
# auto_update_migration_tools.sh

FILES=(
    "execute_actual_eth_migration.py"
    "execute_actual_eth_que_migration.py"
    "execute_broadcast_migration.py"
    "execute_conversation_state_migration.py"
    "execute_donation_keypad_state_migration.py"
    "execute_donation_message_migration.py"
    "execute_failed_transactions_migration.py"
    "execute_landing_page_schema_migration.py"
    "execute_message_tracking_migration.py"
    "execute_migrations.py"
    "execute_notification_migration.py"
    "execute_outcome_usd_migration.py"
    "execute_payment_id_migration.py"
    "execute_price_amount_migration.py"
    "execute_processed_payments_migration.py"
    "execute_unique_id_migration.py"
)

for FILE in "${FILES[@]}"; do
    sed -i 's/project_id = "telepay-459221"/project_id = "pgp-live"/g' "/TOOLS_SCRIPTS_TESTS/tools/$FILE"
    sed -i 's/telepay-459221:us-central1:telepaypsql/pgp-live:us-central1:pgp-telepaypsql/g' "/TOOLS_SCRIPTS_TESTS/tools/$FILE"
    echo "✅ Updated: $FILE"
done

echo ""
echo "🎉 All migration tools updated!"
```

**Manual Verification:**
After running the script, manually verify 2-3 files to ensure correct updates.

---

### 6.5 Phase 5: Update Python Check/Test Tools (MEDIUM Priority)

**Priority:** MEDIUM
**Risk:** MEDIUM
**Duration:** 2 hours

**Files to Update (22 files):**

**Check Tools (9 files):**
- check_broadcast_manager_table.py
- check_client_table_db.py
- check_conversion_status_schema.py
- check_migration_002.py
- check_payment_amounts.py
- check_payout_details.py
- check_payout_schema.py
- check_schema.py
- check_schema_details.py

**Test/Validation Tools (11 files):**
- test_batch_query.py
- test_fetch_due_broadcasts.py
- test_idempotency_constraint.py
- test_manual_broadcast_message_tracking.py
- test_notification_flow.py (special case - also needs service URLs)
- test_payout_database_methods.py
- verify_batch_success.py
- test_subscription_integration.py
- test_subscription_load.py
- backfill_missing_broadcast_entries.py
- populate_broadcast_manager.py

**Fix/Utility Tools (2 files):**
- fix_payout_accumulation_schema.py
- run_migration_002_email_change.py
- run_migration_unique_constraints.py

**Automated Update Script:**
```bash
#!/bin/bash
# auto_update_tools.sh

TOOLS_DIR="/TOOLS_SCRIPTS_TESTS/tools"

# Find all Python files with telepay-459221
FILES=$(grep -l "telepay-459221" "$TOOLS_DIR"/*.py)

for FILE in $FILES; do
    # Skip manual_insert_payment (we're deleting it)
    if [[ "$FILE" == *"manual_insert_payment"* ]]; then
        continue
    fi

    sed -i 's/PROJECT_ID = "telepay-459221"/PROJECT_ID = "pgp-live"/g' "$FILE"
    sed -i 's/project_id = "telepay-459221"/project_id = "pgp-live"/g' "$FILE"
    sed -i 's/telepay-459221:us-central1:telepaypsql/pgp-live:us-central1:pgp-telepaypsql/g' "$FILE"

    echo "✅ Updated: $(basename $FILE)"
done

echo ""
echo "🎉 All tools updated!"
```

**Special Case: test_notification_flow.py**

After automated update, manually update service URLs:
```python
# Line 28: Update NP_WEBHOOK_URL after pgp-live deployment
NP_WEBHOOK_URL = "https://pgp-np-ipn-v1-{PGP_LIVE_PROJECT_NUM}.us-central1.run.app"
```

---

### 6.6 Phase 6: Final Verification

**Priority:** HIGH
**Risk:** NONE
**Duration:** 30 minutes

**Checklist:**

1. **Search for remaining old references:**
   ```bash
   # Should only appear in comments, not code
   grep -r "telepay-459221" /TOOLS_SCRIPTS_TESTS/ --exclude-dir=logs

   # Should only appear in migration 003 and comments
   grep -r "gcwebhook1\|GCWebhook1" /TOOLS_SCRIPTS_TESTS/ --exclude-dir=logs

   # Should NOT appear anywhere
   grep -r "10-26" /TOOLS_SCRIPTS_TESTS/ --exclude-dir=logs
   ```

2. **Verify file count:**
   ```bash
   # Should be 84 files (87 - 3 deleted)
   find /TOOLS_SCRIPTS_TESTS -type f -name "*.py" -o -name "*.sh" -o -name "*.sql" | wc -l
   ```

3. **Verify pgp-live secrets script:**
   ```bash
   # Should create 77 secrets with NEW naming
   grep -c "create_secret" /TOOLS_SCRIPTS_TESTS/scripts/create_pgp_live_secrets.sh
   # Should output: 77
   ```

4. **Verify deployment scripts use correct service names:**
   ```bash
   # Should all use pgp-*-v1 naming
   grep "SERVICE_NAME=" /TOOLS_SCRIPTS_TESTS/scripts/deploy_*.sh
   ```

---

## Summary and Next Steps

### Current State
- **87 files** analyzed across 4 directories
- **19 files (21.8%)** ready for pgp-live as-is
- **65 files (74.7%)** need project ID updates
- **3 files (3.4%)** should be deleted (obsolete)

### Critical Path for pgp-live Deployment

**Step 1: Infrastructure Setup**
1. Create pgp-live project in GCP
2. Create Cloud SQL instance (pgp-telepaypsql)
3. Create database (client_table)

**Step 2: Secret Management**
1. Run `create_pgp_live_secrets.sh` (create 77 secrets)
2. Run `grant_pgp_live_secret_access.sh` (grant access)

**Step 3: Update TOOLS_SCRIPTS_TESTS**
1. Delete 3 obsolete files (Phase 1)
2. Update 23 deployment scripts (Phase 2)
3. Update 5 SQL scripts (Phase 3)
4. Update 16 migration tools (Phase 4)
5. Update 22 check/test tools (Phase 5)
6. Run final verification (Phase 6)

**Step 4: Database Setup**
1. Run table creation scripts
2. Run migration 003 (rename columns)
3. Verify schema

**Step 5: Service Deployment**
1. Deploy Cloud Run services
2. Create Cloud Tasks queues
3. Configure Cloud Scheduler
4. Update test scripts with deployed URLs
5. Run validation tests

### Risk Assessment

**HIGH RISK:**
- ❌ Incorrect secret names in deployment scripts → Services fail to start
- ❌ Incorrect Cloud SQL instance name → Database connection failures
- ❌ Incorrect project ID → Deployment failures

**MEDIUM RISK:**
- ⚠️ Old column names in database → PGP_ORCHESTRATOR_v1 compatibility issues
- ⚠️ Missing migration scripts → Incomplete database schema
- ⚠️ Incorrect service URLs in tests → Test failures

**LOW RISK:**
- ⚠️ Comments still referencing old GC naming → No functional impact

### Estimated Timeline

| Phase | Duration | Risk |
|-------|----------|------|
| Phase 1: Delete obsolete files | 5 minutes | NONE |
| Phase 2: Update deployment scripts | 2-4 hours | MEDIUM |
| Phase 3: Update SQL scripts | 1-2 hours | LOW |
| Phase 4: Update migration tools | 2-3 hours | MEDIUM |
| Phase 5: Update check/test tools | 2 hours | MEDIUM |
| Phase 6: Final verification | 30 minutes | NONE |
| **Total** | **8-12 hours** | **MEDIUM** |

### Recommendations

1. **CRITICAL:** Update `deploy_broadcast_scheduler.sh` secret names FIRST
   - This is the most complex deployment script
   - Requires matching SECRET_NAMING_MIGRATION_CHECKLIST.md exactly

2. **Use automation:** Create shell scripts for batch updates
   - Phase 4 and 5 are repetitive and error-prone
   - Automated sed replacement reduces human error

3. **Test incrementally:**
   - Update and test deployment scripts one at a time
   - Verify each service deploys successfully before moving to next

4. **Keep old files as backup:**
   - Before deleting 3 obsolete files, archive them
   - May contain useful logic for troubleshooting

5. **Document changes:**
   - Update PROGRESS.md after each phase
   - Track which files have been updated

---

## Appendix: Quick Reference Tables

### Files to Delete (3 total)

| File | Reason |
|------|--------|
| `scripts/deploy_gcbroadcastservice_message_tracking.sh` | Replaced by deploy_broadcast_scheduler.sh |
| `scripts/deploy_gcsubscriptionmonitor.sh` | Functionality moved to PGP_SERVER_v1 |
| `tools/manual_insert_payment_4479119533.py` | One-time fix for telepay-459221 |

### Files Ready for pgp-live (19 total)

**Scripts (17):**
- create_pgp_live_secrets.sh ✅
- grant_pgp_live_secret_access.sh ✅
- create_batch_conversions_table.sql ✅
- create_broadcast_manager_table.sql ✅
- add_donation_message_column.sql ✅
- add_message_tracking_columns.sql ✅
- add_notification_columns.sql ✅
- fix_numeric_precision_overflow.sql ✅
- fix_numeric_precision_overflow_v2.sql ✅
- fix_split_payout_hostpay_unique_id_length.sql ✅
- All 5 rollback scripts ✅
- verify_broadcast_integrity.sql ✅
- deploy_backend_api.sh ✅

**Tests/Tools (4):**
- test_error_classifier.py ✅
- test_token_manager_retry.py ✅
- test_changenow_precision.py ✅
- verify_package.py ✅

### Critical Modifications Required

| File | Critical Change | Impact |
|------|----------------|--------|
| `deploy_broadcast_scheduler.sh` | Update 10 secret environment variable names | Service fails to start if incorrect |
| `deploy_telepay_bot.sh` | Update Cloud SQL instance name | Database connection fails |
| `create_processed_payments_table.sql` | Decide: Modify or Delete | Column naming mismatch with services |
| All `execute_*.py` (16 files) | Update project ID + Cloud SQL | Migration tools won't connect |
| `test_notification_flow.py` | Update service URLs + project ID | End-to-end test fails |

---

**END OF TOOLS_SCRIPTS_TESTS MIGRATION CHECKLIST**

**Document Version:** 1.0
**Last Updated:** 2025-11-16
**Author:** Claude Code Analysis
**Status:** Ready for Review
**Next Action:** User review → Proceed with Phase 1 cleanup
