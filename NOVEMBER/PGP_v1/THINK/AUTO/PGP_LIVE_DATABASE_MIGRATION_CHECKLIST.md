# PayGatePrime Database Migration to pgp-live Checklist

**Project Migration:** telepay-459221 → pgp-live
**Database Migration:** telepaypsql (telepaydb) → pgp-telepaypsql (telepaydb)
**Instance:** pgp-live:us-central1:pgp-telepaypsql
**Tables to Migrate:** 13 (excluding user_conversation_state & donation_keypad_state)
**Date:** 2025-11-18
**Status:** Planning Phase - DO NOT DEPLOY YET

---

## ⚠️ CRITICAL CONTEXT WARNING

**Current Context Usage:** ~50k/200k tokens
**Estimated Checklist Execution:** ~100k tokens
**Status:** ✅ SUFFICIENT - Safe to proceed

---

## 📋 Executive Summary

This checklist guides the creation of SQL migration scripts to build the PayGatePrime database schema on the new **pgp-live** Google Cloud project. The migration will:

1. Create 13 core tables (excluding 2 deprecated state tables)
2. Create 4 custom ENUM types for currency/network validation
3. Create 5 auto-increment sequences
4. Create 60+ indexes for query performance
5. Establish foreign key relationships and constraints
6. Add PGP_v1 comments for documentation

### Key Changes from Existing Schema

| Change | Old | New | Reason |
|--------|-----|-----|--------|
| **Tables** | 15 tables | 13 tables | Exclude user_conversation_state, donation_keypad_state |
| **Project** | telepay-459221 | pgp-live | New GCP project |
| **Database Name** | client_table (in code) | pgp_live_db (in code) | Consistent naming |
| **Instance** | telepay-459221:us-central1:telepaypsql | pgp-live:us-central1:pgp-telepaypsql | New instance |

---

## 🎯 Pre-Migration Checklist

### Phase 0: Verification & Preparation

- [ ] **0.1** Review DATABASE_SCHEMA_OUTLINE.md completely
- [ ] **0.2** Verify pgp-live GCP project exists and is accessible
- [ ] **0.3** Verify pgp-live:us-central1:pgp-telepaypsql Cloud SQL instance exists
- [ ] **0.4** Verify database "telepaydb" exists on pgp-telepaypsql instance
- [ ] **0.5** Confirm we have necessary IAM permissions (cloudsql.admin role)
- [ ] **0.6** Review SECRET_SCHEME.md for database connection secrets
- [ ] **0.7** Document current telepaydb schema (reference only, read-only access)
- [ ] **0.8** Create backup of existing 001_create_complete_schema.sql
- [ ] **0.9** Create /TOOLS_SCRIPTS_TESTS/migrations/pgp-live/ directory
- [ ] **0.10** Review NAMING_SCHEME.md for service name mappings

---

## 📝 Phase 1: Create Migration Script Structure

### 1.1 Create Main Schema Migration Script

**File:** `TOOLS_SCRIPTS_TESTS/migrations/pgp-live/001_pgp_live_complete_schema.sql`

**Script Components:**
- [ ] **1.1.1** Add comprehensive header with project/instance details
- [ ] **1.1.2** Add migration metadata (date, version, author)
- [ ] **1.1.3** Add service mapping reference (old GC → new PGP_v1)
- [ ] **1.1.4** Add warning: "DO NOT RUN ON PRODUCTION WITHOUT BACKUP"
- [ ] **1.1.5** Begin transaction with `BEGIN;`

### 1.2 Create ENUM Types Section

**Order:** Create ENUMs before tables that reference them

- [ ] **1.2.1** Create `currency_type` ENUM
  - Values: BTC, ETH, USDT, USDC, LTC, XMR, BCH, BNB, TRX, DOGE, XRP, ADA, DOT, SOL, MATIC, AVAX
  - Add duplicate_object exception handler
  - Add comment: 'PGP_v1: Supported cryptocurrency types'

- [ ] **1.2.2** Create `network_type` ENUM
  - Values: BTC, ETH, TRX, BSC, MATIC, AVAX, SOL, LTC, BCH, XMR
  - Add duplicate_object exception handler
  - Add comment: 'PGP_v1: Supported blockchain networks'

- [ ] **1.2.3** Create `flow_type` ENUM
  - Values: standard, fixed-rate
  - Add duplicate_object exception handler
  - Add comment: 'PGP_v1: ChangeNOW exchange flow types'

- [ ] **1.2.4** Create `type_type` ENUM
  - Values: direct, reverse
  - Add duplicate_object exception handler
  - Add comment: 'PGP_v1: ChangeNOW exchange direction types'

### 1.3 Create Tables in Dependency Order

**Order:** Parent tables before child tables (FK dependencies)

#### 1.3.1 Core Tables (No Dependencies)

- [ ] **1.3.1.1** Create `registered_users` table
  - Primary Key: user_id (UUID)
  - 18 columns total
  - Unique constraints: username, email
  - Check constraint: pending_email must differ from email
  - 9 indexes (including partial indexes)
  - Add table comment: 'PGP_v1: User accounts for PGP_SERVER_v1 web portal'
  - Add column comments for complex fields

- [ ] **1.3.1.2** Create `currency_to_network` table
  - No primary key (reference table)
  - 4 columns: currency, network, currency_name, network_name
  - No indexes needed (small lookup table)
  - Add comment: 'PGP_v1: Currency to network mapping lookup table'

#### 1.3.2 Client & Channel Tables (FK to registered_users)

- [ ] **1.3.2.1** Create `main_clients_database` table
  - Primary Key: id (SERIAL)
  - 19 columns total
  - Foreign Key: client_id → registered_users.user_id (ON DELETE CASCADE)
  - Unique constraints: open_channel_id, closed_channel_id, (open_channel_id, closed_channel_id)
  - Check constraints: pricing, wallet address, channel ID format, donation message
  - 2 indexes: idx_payout_strategy, idx_main_clients_client_id
  - Add comment: 'PGP_v1: Channel configurations for PGP_SERVER_v1, PGP_ORCHESTRATOR_v1, PGP_BROADCAST_v1'

- [ ] **1.3.2.2** Create `broadcast_manager` table
  - Primary Key: id (UUID)
  - 22 columns total
  - Foreign Key: client_id → registered_users.user_id (ON DELETE CASCADE)
  - Unique constraints: open_channel_id, closed_channel_id, (open_channel_id, closed_channel_id)
  - Check constraint: broadcast_status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')
  - 7 indexes (including partial indexes)
  - Add comment: 'PGP_v1: Broadcast scheduling for PGP_BROADCAST_v1'

#### 1.3.3 Subscription Tables (No FK Dependencies)

- [ ] **1.3.3.1** Create `private_channel_users_database` table
  - Primary Key: id (SERIAL)
  - 24 columns total
  - Unique constraints: (user_id, private_channel_id), user_id, private_channel_id
  - 4 indexes including composite index on (user_id, private_channel_id)
  - Add comment: 'PGP_v1: User subscriptions for PGP_SERVER_v1, PGP_MONITOR_v1, PGP_ORCHESTRATOR_v1'

#### 1.3.4 Payment Tables

- [ ] **1.3.4.1** Create `processed_payments` table
  - Primary Key: payment_id (BIGINT)
  - 9 columns total
  - Check constraints: payment_id > 0, user_id > 0
  - 4 indexes including composite and timestamp indexes
  - Add comment: 'PGP_v1: Payment processing tracking for PGP_ORCHESTRATOR_v1, PGP_INVITE_v1'
  - Add column comment for gcwebhook1_processed: 'Legacy naming from GCWebhook1 (now PGP_ORCHESTRATOR_v1)'

#### 1.3.5 Conversion Tables

- [ ] **1.3.5.1** Create `batch_conversions` table
  - Primary Key: id (SERIAL)
  - 10 columns total
  - Unique constraint: batch_conversion_id (UUID)
  - 3 indexes: status, cn_api_id, created_at
  - Add comment: 'PGP_v1: ETH→USDT batch conversions for PGP_MICROBATCHPROCESSOR_v1'

- [ ] **1.3.5.2** Create `payout_accumulation` table (depends on batch_conversions)
  - Primary Key: id (SERIAL)
  - 26 columns total
  - Foreign Key: batch_conversion_id → batch_conversions.batch_conversion_id
  - 8 indexes including composite indexes
  - Add comment: 'PGP_v1: Payment accumulation for PGP_ACCUMULATOR_v1, PGP_MICROBATCHPROCESSOR_v1'

- [ ] **1.3.5.3** Create `payout_batches` table
  - Primary Key: batch_id (VARCHAR)
  - 15 columns total
  - 3 indexes: client_id, status, created_at
  - Add comment: 'PGP_v1: Batch payout transactions for PGP_MICROBATCHPROCESSOR_v1, PGP_HOSTPAY_v1'

#### 1.3.6 Split Payout Tables

- [ ] **1.3.6.1** Create `split_payout_request` table
  - Primary Key: unique_id (CHAR(16))
  - 13 columns total
  - Check constraints: amounts >= 0
  - 1 partial index on actual_eth_amount
  - Add comment: 'PGP_v1: Split payout requests for PGP_SPLIT1_v1'

- [ ] **1.3.6.2** Create `split_payout_que` table
  - Primary Key: unique_id (CHAR(16))
  - 16 columns total
  - Check constraints: amounts >= 0
  - 1 partial index on actual_eth_amount
  - Add comment: 'PGP_v1: Split payout queue for PGP_SPLIT1_v1, PGP_SPLIT2_v1'

- [ ] **1.3.6.3** Create `split_payout_hostpay` table
  - No explicit primary key defined (unique_id is NOT NULL but not PK)
  - 13 columns total
  - Check constraint: actual_eth_amount >= 0
  - 1 partial index on actual_eth_amount
  - Add comment: 'PGP_v1: Host payment portion for PGP_HOSTPAY_v1'

#### 1.3.7 Utility Tables

- [ ] **1.3.7.1** Create `failed_transactions` table
  - Primary Key: id (SERIAL)
  - 17 columns total
  - 6 indexes including composite index for retry logic
  - Add comment: 'PGP_v1: Failed ChangeNOW transactions for PGP_ORCHESTRATOR_v1 error handling'

### 1.4 Verify Schema Completeness

- [ ] **1.4.1** Count tables: Should be exactly 13 (not 15)
- [ ] **1.4.2** Confirm user_conversation_state is NOT in script
- [ ] **1.4.3** Confirm donation_keypad_state is NOT in script
- [ ] **1.4.4** Verify all foreign keys point to existing tables
- [ ] **1.4.5** Verify ENUM types are created before tables use them
- [ ] **1.4.6** Add COMMIT; at end of script
- [ ] **1.4.7** Add completion notice with stats

---

## 📝 Phase 2: Create Rollback Script

### 2.1 Create Rollback Script

**File:** `TOOLS_SCRIPTS_TESTS/migrations/pgp-live/001_pgp_live_rollback.sql`

- [ ] **2.1.1** Add header with WARNING: THIS DELETES ALL DATA
- [ ] **2.1.2** Begin transaction with `BEGIN;`
- [ ] **2.1.3** Drop tables in reverse dependency order (13 tables)
  - failed_transactions
  - currency_to_network
  - broadcast_manager
  - split_payout_hostpay
  - split_payout_que
  - split_payout_request
  - payout_batches
  - payout_accumulation
  - batch_conversions
  - processed_payments
  - private_channel_users_database
  - main_clients_database
  - registered_users
- [ ] **2.1.4** Drop ENUM types (4 types)
- [ ] **2.1.5** Drop sequences (5 sequences)
- [ ] **2.1.6** Add COMMIT;
- [ ] **2.1.7** Add completion notice: "Dropped 13 tables"

---

## 📝 Phase 3: Create Data Population Scripts

### 3.1 Currency to Network Population

**File:** `TOOLS_SCRIPTS_TESTS/migrations/pgp-live/002_pgp_live_populate_currency_to_network.sql`

- [ ] **3.1.1** Copy from existing 002_populate_currency_to_network.sql
- [ ] **3.1.2** Update header for pgp-live project
- [ ] **3.1.3** Add 87 currency-to-network mappings
- [ ] **3.1.4** Add completion notice

### 3.2 Initial Data Verification Script (Optional)

**File:** `TOOLS_SCRIPTS_TESTS/migrations/pgp-live/003_pgp_live_verify_schema.sql`

- [ ] **3.2.1** Query to count all tables (should be 13)
- [ ] **3.2.2** Query to count all indexes (should be 60+)
- [ ] **3.2.3** Query to list all foreign keys
- [ ] **3.2.4** Query to verify ENUM types exist
- [ ] **3.2.5** Query to check currency_to_network has 87 rows

---

## 📝 Phase 4: Create Python Migration Tools

### 4.1 Schema Deployment Tool

**File:** `TOOLS_SCRIPTS_TESTS/tools/deploy_pgp_live_schema.py`

- [ ] **4.1.1** Import required libraries (google.cloud.sql.connector, sqlalchemy)
- [ ] **4.1.2** Load connection details from secrets (pgp-live project)
- [ ] **4.1.3** Connect using Cloud SQL Python Connector
- [ ] **4.1.4** Read 001_pgp_live_complete_schema.sql
- [ ] **4.1.5** Execute migration with transaction handling
- [ ] **4.1.6** Add error handling and rollback on failure
- [ ] **4.1.7** Log each step with emoji markers (✅ ❌ ⏳)
- [ ] **4.1.8** Add dry-run mode (--dry-run flag)
- [ ] **4.1.9** Add confirmation prompt before execution
- [ ] **4.1.10** Print summary: tables created, indexes created, etc.

### 4.2 Schema Verification Tool

**File:** `TOOLS_SCRIPTS_TESTS/tools/verify_pgp_live_schema.py`

- [ ] **4.2.1** Connect to pgp-live database
- [ ] **4.2.2** Query information_schema for table list
- [ ] **4.2.3** Verify exactly 13 tables exist
- [ ] **4.2.4** Verify user_conversation_state does NOT exist
- [ ] **4.2.5** Verify donation_keypad_state does NOT exist
- [ ] **4.2.6** Verify all indexes exist
- [ ] **4.2.7** Verify all foreign keys exist
- [ ] **4.2.8** Verify all ENUM types exist
- [ ] **4.2.9** Generate comparison report: expected vs actual
- [ ] **4.2.10** Exit with status code 0 (success) or 1 (failure)

### 4.3 Rollback Tool

**File:** `TOOLS_SCRIPTS_TESTS/tools/rollback_pgp_live_schema.py`

- [ ] **4.3.1** Connect to pgp-live database
- [ ] **4.3.2** Add TRIPLE confirmation prompt (type "DELETE ALL DATA")
- [ ] **4.3.3** Read 001_pgp_live_rollback.sql
- [ ] **4.3.4** Execute rollback with transaction handling
- [ ] **4.3.5** Log each dropped table
- [ ] **4.3.6** Print completion summary

---

## 📝 Phase 5: Create Shell Script Wrappers

### 5.1 Deployment Script

**File:** `TOOLS_SCRIPTS_TESTS/scripts/deploy_pgp_live_schema.sh`

- [ ] **5.1.1** Add shebang and script header
- [ ] **5.1.2** Activate virtual environment
- [ ] **5.1.3** Set GCP project to pgp-live
- [ ] **5.1.4** Call deploy_pgp_live_schema.py
- [ ] **5.1.5** Add error handling
- [ ] **5.1.6** Make executable: chmod +x

### 5.2 Verification Script

**File:** `TOOLS_SCRIPTS_TESTS/scripts/verify_pgp_live_schema.sh`

- [ ] **5.2.1** Add shebang and script header
- [ ] **5.2.2** Activate virtual environment
- [ ] **5.2.3** Set GCP project to pgp-live
- [ ] **5.2.4** Call verify_pgp_live_schema.py
- [ ] **5.2.5** Make executable: chmod +x

### 5.3 Rollback Script

**File:** `TOOLS_SCRIPTS_TESTS/scripts/rollback_pgp_live_schema.sh`

- [ ] **5.3.1** Add shebang and script header
- [ ] **5.3.2** Add WARNING banner
- [ ] **5.3.3** Activate virtual environment
- [ ] **5.3.4** Set GCP project to pgp-live
- [ ] **5.3.5** Call rollback_pgp_live_schema.py
- [ ] **5.3.6** Make executable: chmod +x

---

## 📝 Phase 6: Create Documentation

### 6.1 Migration README

**File:** `TOOLS_SCRIPTS_TESTS/migrations/pgp-live/README_PGP_LIVE_MIGRATION.md`

- [ ] **6.1.1** Overview of migration purpose
- [ ] **6.1.2** Prerequisites checklist
- [ ] **6.1.3** Step-by-step deployment instructions
- [ ] **6.1.4** Verification instructions
- [ ] **6.1.5** Rollback instructions
- [ ] **6.1.6** Troubleshooting section
- [ ] **6.1.7** File structure reference
- [ ] **6.1.8** Table dependency diagram
- [ ] **6.1.9** Service-to-table mapping reference

### 6.2 Schema Comparison Document

**File:** `THINK/AUTO/PGP_LIVE_SCHEMA_COMPARISON.md`

- [ ] **6.2.1** Side-by-side comparison: old vs new
- [ ] **6.2.2** List tables removed (2)
- [ ] **6.2.3** List tables retained (13)
- [ ] **6.2.4** Explain why tables were removed
- [ ] **6.2.5** Database name changes (client_table → pgp_live_db)
- [ ] **6.2.6** Project changes (telepay-459221 → pgp-live)

---

## 📝 Phase 7: Testing & Validation (DO NOT EXECUTE YET)

### 7.1 Pre-Deployment Validation

- [ ] **7.1.1** Review all SQL files for syntax errors
- [ ] **7.1.2** Validate Python scripts run without errors (import test)
- [ ] **7.1.3** Check shell scripts are executable
- [ ] **7.1.4** Verify secret references use correct project (pgp-live)
- [ ] **7.1.5** Review all file paths are absolute where needed
- [ ] **7.1.6** Confirm no hard-coded credentials in code

### 7.2 Dry Run Testing (Local)

- [ ] **7.2.1** Run deploy_pgp_live_schema.py with --dry-run
- [ ] **7.2.2** Review printed SQL without executing
- [ ] **7.2.3** Verify connection can be established
- [ ] **7.2.4** Test secret retrieval from Secret Manager

### 7.3 Schema Deployment (WAIT FOR USER APPROVAL)

- [ ] **7.3.1** ⛔ **STOP - DO NOT DEPLOY WITHOUT USER APPROVAL**
- [ ] **7.3.2** User reviews all migration files
- [ ] **7.3.3** User approves deployment to pgp-live
- [ ] **7.3.4** Execute: ./scripts/deploy_pgp_live_schema.sh
- [ ] **7.3.5** Monitor deployment logs
- [ ] **7.3.6** Verify no errors occurred

### 7.4 Post-Deployment Verification

- [ ] **7.4.1** Execute: ./scripts/verify_pgp_live_schema.sh
- [ ] **7.4.2** Verify 13 tables exist
- [ ] **7.4.3** Verify 60+ indexes exist
- [ ] **7.4.4** Verify 4 ENUM types exist
- [ ] **7.4.5** Verify 5 sequences exist
- [ ] **7.4.6** Verify all foreign keys established
- [ ] **7.4.7** Query currency_to_network (should have 87 rows)

---

## 📝 Phase 8: Final Documentation Updates

### 8.1 Update Project Documentation

- [ ] **8.1.1** Update PROGRESS.md with migration completion
- [ ] **8.1.2** Update DECISIONS.md with architectural choices
- [ ] **8.1.3** Create entry in BUGS.md if issues found
- [ ] **8.1.4** Update DATABASE_SCHEMA_OUTLINE.md with pgp-live details

### 8.2 Archive Old Files

- [ ] **8.2.1** Move old 001_create_complete_schema.sql to archive
- [ ] **8.2.2** Label as "15-table version (includes deprecated tables)"
- [ ] **8.2.3** Keep for reference only

---

## 🔍 Key Differences Summary

### Tables Excluded (2)

1. **user_conversation_state** - Bot conversation state management (deprecated)
2. **donation_keypad_state** - Donation UI state management (deprecated)

**Reason for Exclusion:** These tables were part of the old bot architecture and are no longer needed in PGP_v1.

### Tables Included (13)

| Category | Tables | Services Using |
|----------|--------|----------------|
| **Core** | registered_users, main_clients_database, private_channel_users_database | PGP_SERVER_v1, PGP_ORCHESTRATOR_v1 |
| **Payment** | processed_payments, payout_accumulation, payout_batches | PGP_ORCHESTRATOR_v1, PGP_INVITE_v1, PGP_MICROBATCHPROCESSOR_v1 |
| **Conversion** | batch_conversions, split_payout_request, split_payout_que, split_payout_hostpay | PGP_SPLIT1_v1, PGP_SPLIT2_v1, PGP_HOSTPAY_v1 |
| **Feature** | broadcast_manager | PGP_BROADCAST_v1 |
| **Utility** | currency_to_network, failed_transactions | All services, PGP_ORCHESTRATOR_v1 |

### Database Name Changes

| Component | Old Value | New Value |
|-----------|-----------|-----------|
| **GCP Project** | telepay-459221 | pgp-live |
| **Cloud SQL Instance** | telepay-459221:us-central1:telepaypsql | pgp-live:us-central1:pgp-telepaypsql |
| **Database Name** | telepaydb | telepaydb (unchanged) |
| **Code Reference** | client_table | pgp_live_db |

---

## 🚨 Critical Reminders

1. **DO NOT DEPLOY YET** - All scripts must be reviewed by user first
2. **DO NOT RUN ON PRODUCTION** - This is for pgp-live (new project) only
3. **READ-ONLY ACCESS** - We have read-only access to telepaypsql (old database)
4. **NO GITHUB COMMITS** - All changes remain local to PGP_v1 directory
5. **NO GCP DEPLOYMENTS** - Do not deploy services or queues
6. **USE VIRTUAL ENV** - All Python scripts must run in /PGP_v1/.venv

---

## 📊 Progress Tracking

**Total Tasks:** 170
**Completed:** 0
**In Progress:** 0
**Pending:** 170

**Estimated Time:** 4-6 hours for script creation (not including deployment)
**Files to Create:** ~15 files (SQL, Python, Shell, Markdown)
**Lines of Code:** ~2500 lines total

---

## ✅ Next Steps

1. **Review this checklist** - Ensure all requirements are captured
2. **Begin Phase 1** - Create SQL migration scripts
3. **Create Python tools** - Deployment and verification scripts
4. **Create shell wrappers** - Easy-to-use deployment commands
5. **Write documentation** - README and comparison docs
6. **WAIT FOR APPROVAL** - Do not deploy without explicit user permission

---

**End of Checklist**
**Status:** Ready for implementation
**User Approval Required Before:** Phase 7 (Testing & Validation)
