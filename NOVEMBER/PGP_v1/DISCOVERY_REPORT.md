# Discovery Report: telepay-459221 → pgp-live Migration

**Generated:** 2025-11-16
**Analysis Directory:** /home/user/TelegramFunnel/OCTOBER/10-26

---

## 📊 Summary Statistics

- **Total Project ID Occurrences:** 26
- **Python Files Affected:** 15
- **Shell Scripts Affected:** 6
- **Total Files Requiring Updates:** 21

---

## 🐍 Python Files with `telepay-459221`

### Core Configuration Files
1. `./GCRegisterAPI-10-26/config_manager.py`
2. `./GCMicroBatchProcessor-10-26/config_manager.py`

### Database Migration/Tool Scripts
3. `./TOOLS_SCRIPTS_TESTS/tools/execute_actual_eth_que_migration.py`
4. `./TOOLS_SCRIPTS_TESTS/tools/manual_insert_payment_4479119533.py`
5. `./TOOLS_SCRIPTS_TESTS/tools/execute_processed_payments_migration.py`
6. `./TOOLS_SCRIPTS_TESTS/tools/check_conversion_status_schema.py`
7. `./TOOLS_SCRIPTS_TESTS/tools/execute_landing_page_schema_migration.py`
8. `./TOOLS_SCRIPTS_TESTS/tools/test_idempotency_constraint.py`
9. `./TOOLS_SCRIPTS_TESTS/tools/execute_actual_eth_migration.py`
10. `./TOOLS_SCRIPTS_TESTS/tools/check_payout_schema.py`
11. `./TOOLS_SCRIPTS_TESTS/tools/execute_migrations.py`
12. `./TOOLS_SCRIPTS_TESTS/tools/fix_payout_accumulation_schema.py`
13. `./TOOLS_SCRIPTS_TESTS/tools/execute_failed_transactions_migration.py`
14. `./TOOLS_SCRIPTS_TESTS/tools/execute_unique_id_migration.py`
15. `./TOOLS_SCRIPTS_TESTS/tools/execute_outcome_usd_migration.py`

---

## 🔧 Shell Scripts with `telepay-459221`

### Cloud Tasks/Queue Deployment Scripts
1. `./TOOLS_SCRIPTS_TESTS/scripts/deploy_gcwebhook_tasks_queues.sh`
2. `./TOOLS_SCRIPTS_TESTS/scripts/deploy_hostpay_tasks_queues.sh`
3. `./TOOLS_SCRIPTS_TESTS/scripts/deploy_accumulator_tasks_queues.sh`
4. `./TOOLS_SCRIPTS_TESTS/scripts/deploy_config_fixes.sh`
5. `./TOOLS_SCRIPTS_TESTS/scripts/deploy_actual_eth_fix.sh`
6. `./TOOLS_SCRIPTS_TESTS/scripts/deploy_gcsplit_tasks_queues.sh`

---

## 🔍 Detailed Analysis by Category

### Category 1: Core Configuration (HIGH PRIORITY)
**Files:**
- `GCRegisterAPI-10-26/config_manager.py`
- `GCMicroBatchProcessor-10-26/config_manager.py`

**Impact:** These files initialize Secret Manager and Cloud SQL connections. All services depend on these.

**Required Changes:**
- Update project ID in Secret Manager client initialization
- Update Cloud SQL connection string format
- Verify all secret access paths

---

### Category 2: Database Tools/Migrations (MEDIUM PRIORITY)
**Files:** All 13 migration scripts in `TOOLS_SCRIPTS_TESTS/tools/`

**Impact:** These are one-time migration scripts. May not be needed for new deployment, but should be updated for consistency.

**Required Changes:**
- Update Cloud SQL connection name
- Update project ID in psql connection strings
- Consider if these need to be re-run for new database

---

### Category 3: Deployment Scripts (HIGH PRIORITY)
**Files:** All 6 scripts in `TOOLS_SCRIPTS_TESTS/scripts/`

**Impact:** Critical for Cloud Tasks queue deployment. Must be updated before any deployment.

**Required Changes:**
- Update project ID in gcloud commands
- Update queue names (if changing from -10-26 suffix)
- Update service URLs
- Update region if needed

---

## 🔎 Next Steps for Discovery

1. ✅ Identify all files with `telepay-459221` references
2. ⏳ Search for database connection patterns
3. ⏳ Search for Secret Manager access patterns
4. ⏳ Identify all queue names
5. ⏳ Identify all service URLs
6. ⏳ Document all environment variables

---

