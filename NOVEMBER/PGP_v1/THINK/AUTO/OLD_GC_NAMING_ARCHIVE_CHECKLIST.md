# Old GC_x_ Naming Structure Archive Checklist

**Date**: 2025-11-18
**Purpose**: Systematically archive legacy files from TOOLS_SCRIPTS_TESTS to ARCHIVES_PGP_v1/OLD_TOOLS_SCRIPTS_TESTS
**Script**: `TOOLS_SCRIPTS_TESTS/scripts/archive_old_gc_naming_files.sh`

---

## Overview

This checklist documents all files that will be archived from the `TOOLS_SCRIPTS_TESTS` directory. These files contain references to the old GC_x_ naming scheme (GCBroadcast, GCNotification, etc.) or are no longer relevant to the PGP_v1 architecture.

---

## Category 1: GC_ Naming Reference Files (3 files)

Files that explicitly reference old GC service names or gcwebhook naming:

### Migrations
- [ ] `migrations/003_rename_gcwebhook1_columns.sql` - Renames gcwebhook1_* to pgp_orchestrator_*
- [ ] `migrations/003_rollback.sql` - Rollback for above migration

### Deployment Scripts
- [ ] `scripts/deploy_gcsplit_tasks_queues.sh` - Cloud Tasks for old GC split services
- [ ] `scripts/deploy_gcwebhook_tasks_queues.sh` - Cloud Tasks for old GC webhook/orchestrator

---

## Category 2: Old Deployment Scripts (12 files)

Deployment scripts that reference old service names or are superseded by `deploy_all_pgp_services.sh`:

### Service Deployment
- [ ] `scripts/deploy_backend_api.sh` - Old pgp-webapi-v1 deployment
- [ ] `scripts/deploy_broadcast_scheduler.sh` - Old pgp-broadcast-v1 deployment
- [ ] `scripts/deploy_frontend.sh` - Old pgp-web-v1 deployment
- [ ] `scripts/deploy_np_webhook.sh` - Old NowPayments webhook deployment
- [ ] `scripts/deploy_telepay_bot.sh` - Old TelePay bot deployment

### Feature Deployment
- [ ] `scripts/deploy_message_tracking_migration.sh` - Old message tracking feature
- [ ] `scripts/deploy_notification_feature.sh` - Old notification feature
- [ ] `scripts/deploy_config_fixes.sh` - Old configuration fixes

### Task Queue Deployment
- [ ] `scripts/deploy_accumulator_tasks_queues.sh` - Old accumulator queue setup
- [ ] `scripts/deploy_hostpay_tasks_queues.sh` - Old HostPay queue setup

### Migration Deployment
- [ ] `scripts/deploy_actual_eth_fix.sh` - Old ETH amount fix deployment

---

## Category 3: Old Task Queue Scripts (2 files)

Scripts for managing old broadcast scheduler queues:

- [ ] `scripts/pause_broadcast_scheduler.sh` - Pause old broadcast service
- [ ] `scripts/resume_broadcast_scheduler.sh` - Resume old broadcast service

---

## Category 4: Old SQL Migration Scripts (19 files)

SQL scripts for incremental schema changes (now replaced by complete schema migrations):

### Column Addition Scripts
- [ ] `scripts/add_actual_eth_amount_columns.sql` - Add ETH amount tracking
- [ ] `scripts/add_actual_eth_to_split_payout_que.sql` - Add ETH to payout queue
- [ ] `scripts/add_donation_message_column.sql` - Add donation message tracking
- [ ] `scripts/add_message_tracking_columns.sql` - Add message tracking columns
- [ ] `scripts/add_notification_columns.sql` - Add notification columns
- [ ] `scripts/add_nowpayments_outcome_usd_column.sql` - Add USD outcome tracking

### Table Creation Scripts
- [ ] `scripts/create_batch_conversions_table.sql` - Create batch conversions table
- [ ] `scripts/create_broadcast_manager_table.sql` - Create broadcast manager table
- [ ] `scripts/create_donation_keypad_state_table.sql` - Create keypad state table
- [ ] `scripts/create_failed_transactions_table.sql` - Create failed transactions table

### Rollback Scripts
- [ ] `scripts/rollback_actual_eth_amount_columns.sql` - Rollback ETH columns
- [ ] `scripts/rollback_broadcast_manager_table.sql` - Rollback broadcast table
- [ ] `scripts/rollback_donation_message_column.sql` - Rollback donation column
- [ ] `scripts/rollback_message_tracking_columns.sql` - Rollback message tracking
- [ ] `scripts/rollback_notification_columns.sql` - Rollback notification columns

### Fix Scripts
- [ ] `scripts/fix_numeric_precision_overflow.sql` - Fix numeric precision issues v1
- [ ] `scripts/fix_numeric_precision_overflow_v2.sql` - Fix numeric precision issues v2
- [ ] `scripts/fix_split_payout_hostpay_unique_id_length.sql` - Fix unique ID length

### Verification Scripts
- [ ] `scripts/verify_broadcast_integrity.sql` - Verify broadcast data integrity

---

## Category 5: Old Migration Execution Tools (17 files)

Python tools that execute incremental migrations (superseded by complete schema deployment):

- [ ] `tools/execute_actual_eth_migration.py` - Execute ETH amount migration
- [ ] `tools/execute_actual_eth_que_migration.py` - Execute ETH queue migration
- [ ] `tools/execute_broadcast_migration.py` - Execute broadcast table migration
- [ ] `tools/execute_conversation_state_migration.py` - Execute conversation state migration
- [ ] `tools/execute_donation_keypad_state_migration.py` - Execute keypad state migration
- [ ] `tools/execute_donation_message_migration.py` - Execute donation message migration
- [ ] `tools/execute_failed_transactions_migration.py` - Execute failed transactions migration
- [ ] `tools/execute_landing_page_schema_migration.py` - Execute landing page migration
- [ ] `tools/execute_message_tracking_migration.py` - Execute message tracking migration
- [ ] `tools/execute_migrations.py` - Generic migration executor
- [ ] `tools/execute_notification_migration.py` - Execute notification migration
- [ ] `tools/execute_outcome_usd_migration.py` - Execute USD outcome migration
- [ ] `tools/execute_payment_id_migration.py` - Execute payment ID migration
- [ ] `tools/execute_price_amount_migration.py` - Execute price amount migration
- [ ] `tools/execute_processed_payments_migration.py` - Execute processed payments migration
- [ ] `tools/execute_unique_id_migration.py` - Execute unique ID migration

---

## Category 6: Old Broadcast/Notification Tools (7 files)

Tools for managing old broadcast and notification systems:

### Broadcast Management
- [ ] `tools/backfill_missing_broadcast_entries.py` - Backfill broadcast data
- [ ] `tools/check_broadcast_manager_table.py` - Check broadcast table
- [ ] `tools/populate_broadcast_manager.py` - Populate broadcast table
- [ ] `tools/test_fetch_due_broadcasts.py` - Test broadcast fetching
- [ ] `tools/test_manual_broadcast_message_tracking.py` - Test message tracking

### Notification Management
- [ ] `tools/test_notification_flow.py` - Test notification flow
- [ ] `scripts/run_notification_test.sh` - Run notification tests

---

## Category 7: Old Schema Validation Tools (12 files)

Tools for checking and validating old schema migrations:

- [ ] `tools/check_client_table_db.py` - Check client table structure
- [ ] `tools/check_conversion_status_schema.py` - Check conversion status schema
- [ ] `tools/check_migration_002.py` - Check migration 002 status
- [ ] `tools/check_payment_amounts.py` - Check payment amount data
- [ ] `tools/check_payout_details.py` - Check payout detail data
- [ ] `tools/check_payout_schema.py` - Check payout schema structure
- [ ] `tools/check_schema.py` - Generic schema checker
- [ ] `tools/check_schema_details.py` - Detailed schema checker
- [ ] `tools/fix_payout_accumulation_schema.py` - Fix payout accumulation schema
- [ ] `tools/run_migration_002_email_change.py` - Run email change migration
- [ ] `tools/run_migration_unique_constraints.py` - Run unique constraint migration

---

## Category 8: Old Test Scripts (9 files)

Legacy test scripts that are no longer relevant:

### Tools Tests
- [ ] `tools/test_batch_query.py` - Test batch query functionality
- [ ] `tools/test_changenow_precision.py` - Test ChangeNow precision handling
- [ ] `tools/test_idempotency_constraint.py` - Test idempotency constraints
- [ ] `tools/test_payout_database_methods.py` - Test payout database methods
- [ ] `tools/verify_batch_success.py` - Verify batch operation success
- [ ] `tools/verify_package.py` - Verify package installation

### Tests Directory
- [ ] `tests/test_error_classifier.py` - Test error classification
- [ ] `tests/test_subscription_integration.py` - Test subscription integration
- [ ] `tests/test_subscription_load.py` - Test subscription load handling
- [ ] `tests/test_token_manager_retry.py` - Test token manager retry logic

---

## Category 9: Miscellaneous Utility Scripts (2 files)

Old utility scripts:

- [ ] `scripts/set_max_tokens.sh` - Set max tokens configuration
- [ ] `scripts/fix_secret_newlines.sh` - Fix newlines in secrets

---

## Files That Will REMAIN in TOOLS_SCRIPTS_TESTS

### Current/Active Scripts
- ✓ `scripts/activate_venv.sh` - Virtual environment activation
- ✓ `scripts/setup_venv.sh` - Virtual environment setup
- ✓ `scripts/create_pgp_live_secrets.sh` - Current secret creation
- ✓ `scripts/grant_pgp_live_secret_access.sh` - Current secret access
- ✓ `scripts/deploy_all_pgp_services.sh` - Current deployment script
- ✓ `scripts/README_HOT_RELOAD_DEPLOYMENT.md` - Current deployment docs

### Current Security Scripts
- ✓ `scripts/security/configure_invoker_permissions.sh`
- ✓ `scripts/security/create_cloud_armor_policy.sh`
- ✓ `scripts/security/create_serverless_negs.sh`
- ✓ `scripts/security/create_service_accounts.sh`
- ✓ `scripts/security/deploy_load_balancer.sh`
- ✓ `scripts/security/grant_iam_permissions.sh`
- ✓ `scripts/security/provision_ssl_certificates.sh`
- ✓ `scripts/security/phase1_backups/` - Backup scripts
- ✓ `scripts/security/phase2_ssl/` - SSL enforcement scripts

### Current Migration Files
- ✓ `migrations/001_create_complete_schema.sql` - Current schema
- ✓ `migrations/001_rollback.sql` - Current schema rollback
- ✓ `migrations/002_populate_currency_to_network.sql` - Currency mapping

### Current Tools
- ✓ `tools/deploy_complete_schema_pgp_live.py` - Current schema deployment
- ✓ `tools/export_currency_to_network.py` - Current currency export
- ✓ `tools/extract_complete_schema.py` - Current schema extraction
- ✓ `tools/verify_schema_match.py` - Current schema verification

### Documentation
- ✓ `docs/SERVICE_AUTH_MIGRATION.md` - Current service auth docs

---

## Summary Statistics

| Category | File Count | Description |
|----------|-----------|-------------|
| Category 1 | 4 | GC_ naming references |
| Category 2 | 11 | Old deployment scripts |
| Category 3 | 2 | Old task queue scripts |
| Category 4 | 19 | Old SQL migrations |
| Category 5 | 17 | Old migration executors |
| Category 6 | 7 | Old broadcast/notification tools |
| Category 7 | 11 | Old schema validation tools |
| Category 8 | 9 | Old test scripts |
| Category 9 | 2 | Miscellaneous utilities |
| **TOTAL** | **82** | **Files to archive** |

---

## Post-Archive Structure

```
ARCHIVES_PGP_v1/OLD_TOOLS_SCRIPTS_TESTS/
├── scripts/
│   ├── security/
│   ├── deploy_*.sh (11 files)
│   ├── pause/resume_*.sh (2 files)
│   ├── *.sql (19 files)
│   └── misc utilities (2 files)
├── tools/
│   ├── execute_*.py (17 files)
│   ├── check_*.py (11 files)
│   ├── test_*.py (6 files)
│   └── verify_*.py (2 files)
├── tests/
│   └── test_*.py (4 files)
├── migrations/
│   ├── 003_rename_gcwebhook1_columns.sql
│   └── 003_rollback.sql
└── docs/
    └── (future documentation)
```

---

## Execution Instructions

1. **Review this checklist** to ensure all files are correctly categorized
2. **Make the script executable**:
   ```bash
   chmod +x TOOLS_SCRIPTS_TESTS/scripts/archive_old_gc_naming_files.sh
   ```
3. **Run the script**:
   ```bash
   ./TOOLS_SCRIPTS_TESTS/scripts/archive_old_gc_naming_files.sh
   ```
4. **Review the log file** at `TOOLS_SCRIPTS_TESTS/logs/archive_YYYYMMDD_HHMMSS.log`
5. **Verify remaining files** match the "Files That Will REMAIN" section

---

## Safety Notes

- ✅ Script uses `set -e` to exit on error
- ✅ Creates complete directory structure before moving files
- ✅ Logs all operations to timestamped log file
- ✅ Moves files (not copies) to save disk space
- ✅ Preserves directory structure in archive
- ✅ Provides summary of archived vs. missing files
- ✅ Lists remaining files after completion

---

## Rollback Plan

If you need to restore any archived files:

```bash
# Restore specific file
cp ARCHIVES_PGP_v1/OLD_TOOLS_SCRIPTS_TESTS/path/to/file TOOLS_SCRIPTS_TESTS/path/to/file

# Restore entire category
cp -r ARCHIVES_PGP_v1/OLD_TOOLS_SCRIPTS_TESTS/scripts/* TOOLS_SCRIPTS_TESTS/scripts/

# Restore everything
cp -r ARCHIVES_PGP_v1/OLD_TOOLS_SCRIPTS_TESTS/* TOOLS_SCRIPTS_TESTS/
```

---

**Status**: Ready for review and execution
**Next Step**: Review this checklist, then execute the archive script
