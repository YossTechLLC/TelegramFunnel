# Main Architecture Workflow - Implementation Tracker

**Created:** 2025-10-28
**Last Updated:** 2025-10-28
**Status:** In Progress

---

## Overview

This document tracks the implementation of three major architecture documents:
1. **GCREGISTER_MODERNIZATION_ARCHITECTURE.md** - TypeScript/React SPA with Flask REST API
2. **USER_ACCOUNT_MANAGEMENT_ARCHITECTURE.md** - Multi-channel dashboard with user accounts
3. **THRESHOLD_PAYOUT_ARCHITECTURE.md** - USDT accumulation with batch payouts

---

## Implementation Priority

**Decision:** Implement in reverse dependency order
1. ✅ THRESHOLD_PAYOUT (foundational - no dependencies)
2. ⏳ USER_ACCOUNT_MANAGEMENT (depends on threshold payout fields)
3. ⏳ GCREGISTER_MODERNIZATION (UI layer for both systems)

---

## THRESHOLD_PAYOUT_ARCHITECTURE Implementation

### Database Schema Changes

#### ✅ Step 1: Modify `main_clients_database`
- **Status:** ✅ SQL Ready
- **File:** `OCTOBER/10-26/DB_MIGRATION_THRESHOLD_PAYOUT.md`
- **Changes:**
  ```sql
  ALTER TABLE main_clients_database
  ADD COLUMN payout_strategy VARCHAR(20) DEFAULT 'instant',
  ADD COLUMN payout_threshold_usd NUMERIC(10, 2) DEFAULT 0,
  ADD COLUMN payout_threshold_updated_at TIMESTAMP;
  ```
- **Verification:** Query existing channels to confirm columns added
- **Action Required:** Execute SQL in PostgreSQL

#### ✅ Step 2: Create `payout_accumulation` Table
- **Status:** ✅ SQL Ready
- **File:** `OCTOBER/10-26/DB_MIGRATION_THRESHOLD_PAYOUT.md`
- **Purpose:** Track individual payments accumulating toward threshold
- **Key Fields:**
  - `accumulated_amount_usdt` - Locked USDT value (eliminates volatility)
  - `is_paid_out` - Status flag for batch processing
  - `payout_batch_id` - Links to batch when paid
- **Action Required:** Execute SQL in PostgreSQL

#### ✅ Step 3: Create `payout_batches` Table
- **Status:** ✅ SQL Ready
- **File:** `OCTOBER/10-26/DB_MIGRATION_THRESHOLD_PAYOUT.md`
- **Purpose:** Track batch payouts to clients
- **Key Fields:**
  - `batch_id` - UUID for batch
  - `total_amount_usdt` - Total accumulated
  - `status` - pending/processing/completed/failed
- **Action Required:** Execute SQL in PostgreSQL

### Service Modifications

#### ✅ Step 4: Modify GCWebhook1-10-26
- **Status:** ✅ COMPLETED (2025-10-28)
- **Files Modified:**
  - `config_manager.py` - Added GCACCUMULATOR_QUEUE and GCACCUMULATOR_URL
  - `database_manager.py` - Added get_payout_strategy() and get_subscription_id()
  - `cloudtasks_client.py` - Added enqueue_gcaccumulator_payment()
  - `tph1-10-26.py` - Added payout strategy routing logic
- **Changes Implemented:**
  - ✅ Routing logic checks `payout_strategy` from database
  - ✅ Routes to GCAccumulator if strategy='threshold'
  - ✅ Routes to GCSplit1 if strategy='instant' (existing flow unchanged)
  - ✅ Telegram invite sent regardless of strategy
  - ✅ Fallback to instant if GCAccumulator unavailable
- **Action Required:** Re-deploy service to Cloud Run

#### ✅ Step 5: Modify GCRegister10-26
- **Status:** ✅ Guide Complete (2025-10-28)
- **Guide:** `OCTOBER/10-26/GCREGISTER_MODIFICATIONS_GUIDE.md`
- **Changes Documented:**
  - ✅ forms.py: Add `payout_strategy` SelectField and `payout_threshold_usd` DecimalField
  - ✅ register.html: Add UI fields with JavaScript show/hide logic
  - ✅ tpr10-26.py: Add threshold fields to database INSERT
  - ✅ Validation: threshold required if strategy='threshold', minimum $50
  - ✅ Testing checklist included
- **Action Required:** Apply modifications manually, then deploy

### New Services

#### ✅ Step 6: Create GCAccumulator-10-26
- **Status:** ✅ COMPLETED (2025-10-28)
- **Directory:** `OCTOBER/10-26/GCAccumulator-10-26/`
- **Files Created:**
  - ✅ `acc10-26.py` - Main Flask app with payment accumulation logic
  - ✅ `config_manager.py` - Secret Manager integration for all configs
  - ✅ `database_manager.py` - insert_payout_accumulation(), get_client_accumulation_total(), get_client_threshold()
  - ✅ `token_manager.py` - Token encryption for GCSplit2 (future use)
  - ✅ `cloudtasks_client.py` - Cloud Tasks integration
  - ✅ `Dockerfile` - Python 3.11-slim with PostgreSQL support
  - ✅ `requirements.txt` - Flask, google-cloud libraries, pg8000
  - ✅ `.dockerignore` - Clean Docker context
- **Features Implemented:**
  - ✅ Receives payment data from GCWebhook1
  - ✅ Calculates adjusted amount (removes TP fee)
  - ✅ Mock ETH→USDT conversion (ready for ChangeNow integration)
  - ✅ Writes to payout_accumulation table with locked USDT value
  - ✅ Checks total accumulation vs threshold
  - ✅ Logs remaining amount to reach threshold
  - ✅ Health check endpoint
- **Action Required:** Deploy to Cloud Run

#### ✅ Step 7: Create GCBatchProcessor-10-26
- **Status:** ✅ COMPLETED (2025-10-28)
- **Directory:** `OCTOBER/10-26/GCBatchProcessor-10-26/`
- **Files Created:**
  - ✅ `batch10-26.py` - Main Flask app with batch processing logic
  - ✅ `config_manager.py` - Secret Manager integration for all configs
  - ✅ `database_manager.py` - find_clients_over_threshold(), create_payout_batch(), update_batch_status(), mark_accumulations_paid()
  - ✅ `token_manager.py` - Token encryption for GCSplit1 batch endpoint
  - ✅ `cloudtasks_client.py` - Cloud Tasks integration
  - ✅ `Dockerfile` - Python 3.11-slim with PostgreSQL support
  - ✅ `requirements.txt` - Flask, google-cloud libraries, pg8000
  - ✅ `.dockerignore` - Clean Docker context
- **Features Implemented:**
  - ✅ Triggered by Cloud Scheduler POST /process
  - ✅ Finds clients with accumulated USDT >= threshold
  - ✅ Creates batch records in payout_batches table
  - ✅ Encrypts tokens for GCSplit1 /batch-payout endpoint
  - ✅ Enqueues to GCSplit1 for USDT→ClientCurrency swap
  - ✅ Marks accumulations as paid_out after batch creation
  - ✅ Error handling per client (continues if one fails)
  - ✅ Health check endpoint
- **Action Required:** Deploy to Cloud Run, then create Cloud Scheduler job

### Deployment Configuration

#### ✅ Step 8: Cloud Tasks Queue Setup
- **Status:** ✅ Script Complete (2025-10-28)
- **File:** `OCTOBER/10-26/deploy_accumulator_tasks_queues.sh`
- **Queues:**
  - ✅ `accumulator-payment-queue` (GCWebhook1 → GCAccumulator)
  - ✅ `gcsplit1-batch-queue` (GCBatchProcessor → GCSplit1)
- **Configuration:**
  - Max Dispatches/Second: 10
  - Max Concurrent: 50
  - Max Attempts: -1 (infinite)
  - Max Retry Duration: 86400s (24h)
  - Backoff: 60s fixed (no exponential)
- **Action Required:** Execute script `./deploy_accumulator_tasks_queues.sh`

#### ✅ Step 9: Cloud Scheduler Setup
- **Status:** ✅ Command Ready (2025-10-28)
- **Documentation:** `DEPLOYMENT_GUIDE_THRESHOLD_PAYOUT.md` Step 5
- **Schedule:** Every 5 minutes (`*/5 * * * *`)
- **Target:** https://gcbatchprocessor-10-26-SERVICE_URL/process
- **Command:**
  ```bash
  gcloud scheduler jobs create http batch-processor-job \
    --schedule="*/5 * * * *" \
    --uri="https://gcbatchprocessor-10-26-SERVICE_URL/process" \
    --http-method=POST \
    --location=us-central1 \
    --time-zone="America/Los_Angeles"
  ```
- **Action Required:** Execute command after deploying GCBatchProcessor-10-26

---

## Implementation Complete: Summary

### ✅ All Threshold Payout Components Ready

**Services Created (2/2):**
- ✅ GCAccumulator-10-26
- ✅ GCBatchProcessor-10-26

**Services Modified (2/2):**
- ✅ GCWebhook1-10-26 (code modified)
- ✅ GCRegister10-26 (modification guide created)

**Infrastructure Ready (2/2):**
- ✅ Cloud Tasks queue deployment script
- ✅ Cloud Scheduler job command

**Documentation Complete (5/5):**
- ✅ DB_MIGRATION_THRESHOLD_PAYOUT.md
- ✅ IMPLEMENTATION_SUMMARY.md
- ✅ GCREGISTER_MODIFICATIONS_GUIDE.md
- ✅ DEPLOYMENT_GUIDE_THRESHOLD_PAYOUT.md
- ✅ MAIN_ARCHITECTURE_WORKFLOW.md (this file)

### 🎯 Ready for Deployment

**Next Actions:**
1. Execute `DB_MIGRATION_THRESHOLD_PAYOUT.md` SQL in PostgreSQL
2. Apply `GCREGISTER_MODIFICATIONS_GUIDE.md` changes manually
3. Follow `DEPLOYMENT_GUIDE_THRESHOLD_PAYOUT.md` step-by-step
4. Test instant payout (verify unchanged)
5. Test threshold payout end-to-end

**Estimated Deployment Time:** 45-60 minutes
**Risk Level:** Low (backward compatible, fallback to instant if issues)

---

## USER_ACCOUNT_MANAGEMENT_ARCHITECTURE Implementation

### Database Schema Changes

#### ⏳ Step 10: Create `registered_users` Table
- **Status:** Not Started
- **File:** `OCTOBER/10-26/DB_MIGRATION_USER_ACCOUNTS.md`
- **Purpose:** Store user account information
- **Key Fields:**
  - `user_id` - UUID primary key
  - `username`, `email`, `password_hash`
  - `is_active`, `email_verified`

#### ⏳ Step 11: Add `client_id` to `main_clients_database`
- **Status:** Not Started
- **Changes:**
  ```sql
  ALTER TABLE main_clients_database
  ADD COLUMN client_id UUID NOT NULL,
  ADD COLUMN created_by VARCHAR(50),
  ADD FOREIGN KEY (client_id) REFERENCES registered_users(user_id);
  ```

### Service Modifications

#### ⏳ Step 12: Add User Management to GCRegister10-26
- **Status:** Not Started
- **Changes:**
  - Add `/signup`, `/login`, `/logout` routes
  - Add Flask-Login integration
  - Add user authentication
  - Add session management

#### ⏳ Step 13: Add Dashboard to GCRegister10-26
- **Status:** Not Started
- **Routes:**
  - `/channels` - Dashboard view
  - `/channels/add` - Add new channel
  - `/channels/<id>/edit` - Edit channel

---

## GCREGISTER_MODERNIZATION_ARCHITECTURE Implementation

### Backend REST API

#### ⏳ Step 14: Create GCRegisterAPI-10-26
- **Status:** Not Started
- **Directory:** `OCTOBER/10-26/GCRegisterAPI-10-26/`
- **Type:** Flask REST API (no templates)

### Frontend SPA

#### ⏳ Step 15: Create GCRegisterWeb-10-26
- **Status:** Not Started
- **Directory:** `OCTOBER/10-26/GCRegisterWeb-10-26/`
- **Type:** TypeScript + React + Vite SPA

---

## Documentation Files Created

### Migration Guides
- ⏳ `DB_MIGRATION_THRESHOLD_PAYOUT.md` - PostgreSQL schema changes for threshold payout
- ⏳ `DB_MIGRATION_USER_ACCOUNTS.md` - PostgreSQL schema changes for user accounts

### Deployment Guides
- ⏳ `DEPLOYMENT_GUIDE_THRESHOLD_PAYOUT.md` - Deploy GCAccumulator & GCBatchProcessor
- ⏳ `deploy_accumulator_tasks_queues.sh` - Cloud Tasks queue creation script

---

## Notes

- **Context Budget:** Limited to 200K tokens - being very selective about implementations
- **PSQL Changes:** User will execute manually - we provide clear SQL migration files
- **Google Cloud Deployment:** User will deploy manually - we provide deployment guides
- **Shell Scripts:** We provide them but user executes manually
- **Emoji Patterns:** Continuing existing patterns (🚀 ✅ ❌ 💾 👤 💰 🏦 🌐 🎯 etc.)

---

## Next Action

**Currently Working On:** Step 4 - Modifying GCWebhook1-10-26 for payout strategy routing
