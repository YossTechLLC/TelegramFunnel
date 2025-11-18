#!/bin/bash
################################################################################
# Archive Old GC_x_ Naming Structure Files
# Purpose: Systematically move legacy files from TOOLS_SCRIPTS_TESTS to archive
# Target: /NOVEMBER/ARCHIVES_PGP_v1/OLD_TOOLS_SCRIPTS_TESTS
# Date: 2025-11-18
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SOURCE_BASE="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS"
ARCHIVE_BASE="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/ARCHIVES_PGP_v1/OLD_TOOLS_SCRIPTS_TESTS"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${SOURCE_BASE}/logs/archive_${TIMESTAMP}.log"

# Ensure log directory exists
mkdir -p "${SOURCE_BASE}/logs"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Archive Old GC_x_ Naming Structure Files                          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📋 Configuration:${NC}"
echo -e "   Source: ${SOURCE_BASE}"
echo -e "   Archive: ${ARCHIVE_BASE}"
echo -e "   Log: ${LOG_FILE}"
echo ""

# Create archive base directory structure
echo -e "${BLUE}📁 Creating archive directory structure...${NC}"
mkdir -p "${ARCHIVE_BASE}/scripts"
mkdir -p "${ARCHIVE_BASE}/scripts/security"
mkdir -p "${ARCHIVE_BASE}/tools"
mkdir -p "${ARCHIVE_BASE}/tests"
mkdir -p "${ARCHIVE_BASE}/migrations"
mkdir -p "${ARCHIVE_BASE}/docs"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Archive file function
archive_file() {
    local file_path=$1
    local relative_path=${file_path#${SOURCE_BASE}/}
    local archive_path="${ARCHIVE_BASE}/${relative_path}"
    local archive_dir=$(dirname "${archive_path}")

    # Create directory if needed
    mkdir -p "${archive_dir}"

    # Move file
    if [ -f "${file_path}" ]; then
        mv "${file_path}" "${archive_path}"
        log "✅ Archived: ${relative_path}"
        echo -e "${GREEN}   ✓${NC} ${relative_path}"
        return 0
    else
        log "⚠️  File not found: ${relative_path}"
        echo -e "${YELLOW}   ⚠${NC} File not found: ${relative_path}"
        return 1
    fi
}

################################################################################
# CATEGORY 1: Files with GC_ naming references
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 CATEGORY 1: GC_ Naming Reference Files${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "=== CATEGORY 1: GC_ Naming Reference Files ==="

# Migration files with GC references
archive_file "${SOURCE_BASE}/migrations/003_rename_gcwebhook1_columns.sql"
archive_file "${SOURCE_BASE}/migrations/003_rollback.sql"

# Deployment scripts with GC references
archive_file "${SOURCE_BASE}/scripts/deploy_gcsplit_tasks_queues.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_gcwebhook_tasks_queues.sh"

################################################################################
# CATEGORY 2: Old deployment scripts (pre-PGP_v1)
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 CATEGORY 2: Old Deployment Scripts${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "=== CATEGORY 2: Old Deployment Scripts ==="

# These scripts reference old service names or are no longer used
archive_file "${SOURCE_BASE}/scripts/deploy_backend_api.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_broadcast_scheduler.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_frontend.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_message_tracking_migration.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_notification_feature.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_np_webhook.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_telepay_bot.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_accumulator_tasks_queues.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_actual_eth_fix.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_config_fixes.sh"
archive_file "${SOURCE_BASE}/scripts/deploy_hostpay_tasks_queues.sh"

################################################################################
# CATEGORY 3: Old task queue deployment scripts
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 CATEGORY 3: Old Task Queue Scripts${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "=== CATEGORY 3: Old Task Queue Scripts ==="

archive_file "${SOURCE_BASE}/scripts/pause_broadcast_scheduler.sh"
archive_file "${SOURCE_BASE}/scripts/resume_broadcast_scheduler.sh"

################################################################################
# CATEGORY 4: Old SQL migration/schema scripts
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 CATEGORY 4: Old SQL Migration Scripts${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "=== CATEGORY 4: Old SQL Migration Scripts ==="

# Old table creation scripts
archive_file "${SOURCE_BASE}/scripts/add_actual_eth_amount_columns.sql"
archive_file "${SOURCE_BASE}/scripts/add_actual_eth_to_split_payout_que.sql"
archive_file "${SOURCE_BASE}/scripts/add_donation_message_column.sql"
archive_file "${SOURCE_BASE}/scripts/add_message_tracking_columns.sql"
archive_file "${SOURCE_BASE}/scripts/add_notification_columns.sql"
archive_file "${SOURCE_BASE}/scripts/add_nowpayments_outcome_usd_column.sql"
archive_file "${SOURCE_BASE}/scripts/create_batch_conversions_table.sql"
archive_file "${SOURCE_BASE}/scripts/create_broadcast_manager_table.sql"
archive_file "${SOURCE_BASE}/scripts/create_donation_keypad_state_table.sql"
archive_file "${SOURCE_BASE}/scripts/create_failed_transactions_table.sql"

# Rollback scripts
archive_file "${SOURCE_BASE}/scripts/rollback_actual_eth_amount_columns.sql"
archive_file "${SOURCE_BASE}/scripts/rollback_broadcast_manager_table.sql"
archive_file "${SOURCE_BASE}/scripts/rollback_donation_message_column.sql"
archive_file "${SOURCE_BASE}/scripts/rollback_message_tracking_columns.sql"
archive_file "${SOURCE_BASE}/scripts/rollback_notification_columns.sql"

# Precision fix scripts
archive_file "${SOURCE_BASE}/scripts/fix_numeric_precision_overflow.sql"
archive_file "${SOURCE_BASE}/scripts/fix_numeric_precision_overflow_v2.sql"
archive_file "${SOURCE_BASE}/scripts/fix_split_payout_hostpay_unique_id_length.sql"

# Verification scripts
archive_file "${SOURCE_BASE}/scripts/verify_broadcast_integrity.sql"

################################################################################
# CATEGORY 5: Old migration execution tools
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 CATEGORY 5: Old Migration Execution Tools${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "=== CATEGORY 5: Old Migration Execution Tools ==="

archive_file "${SOURCE_BASE}/tools/execute_actual_eth_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_actual_eth_que_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_broadcast_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_conversation_state_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_donation_keypad_state_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_donation_message_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_failed_transactions_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_landing_page_schema_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_message_tracking_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_migrations.py"
archive_file "${SOURCE_BASE}/tools/execute_notification_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_outcome_usd_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_payment_id_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_price_amount_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_processed_payments_migration.py"
archive_file "${SOURCE_BASE}/tools/execute_unique_id_migration.py"

################################################################################
# CATEGORY 6: Old broadcast/notification management tools
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 CATEGORY 6: Old Broadcast/Notification Tools${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "=== CATEGORY 6: Old Broadcast/Notification Tools ==="

archive_file "${SOURCE_BASE}/tools/backfill_missing_broadcast_entries.py"
archive_file "${SOURCE_BASE}/tools/check_broadcast_manager_table.py"
archive_file "${SOURCE_BASE}/tools/populate_broadcast_manager.py"
archive_file "${SOURCE_BASE}/tools/test_fetch_due_broadcasts.py"
archive_file "${SOURCE_BASE}/tools/test_manual_broadcast_message_tracking.py"
archive_file "${SOURCE_BASE}/tools/test_notification_flow.py"
archive_file "${SOURCE_BASE}/scripts/run_notification_test.sh"

################################################################################
# CATEGORY 7: Old schema checking/validation tools
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 CATEGORY 7: Old Schema Validation Tools${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "=== CATEGORY 7: Old Schema Validation Tools ==="

archive_file "${SOURCE_BASE}/tools/check_client_table_db.py"
archive_file "${SOURCE_BASE}/tools/check_conversion_status_schema.py"
archive_file "${SOURCE_BASE}/tools/check_migration_002.py"
archive_file "${SOURCE_BASE}/tools/check_payment_amounts.py"
archive_file "${SOURCE_BASE}/tools/check_payout_details.py"
archive_file "${SOURCE_BASE}/tools/check_payout_schema.py"
archive_file "${SOURCE_BASE}/tools/check_schema.py"
archive_file "${SOURCE_BASE}/tools/check_schema_details.py"
archive_file "${SOURCE_BASE}/tools/fix_payout_accumulation_schema.py"
archive_file "${SOURCE_BASE}/tools/run_migration_002_email_change.py"
archive_file "${SOURCE_BASE}/tools/run_migration_unique_constraints.py"

################################################################################
# CATEGORY 8: Old test scripts
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 CATEGORY 8: Old Test Scripts${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "=== CATEGORY 8: Old Test Scripts ==="

archive_file "${SOURCE_BASE}/tools/test_batch_query.py"
archive_file "${SOURCE_BASE}/tools/test_changenow_precision.py"
archive_file "${SOURCE_BASE}/tools/test_idempotency_constraint.py"
archive_file "${SOURCE_BASE}/tools/test_payout_database_methods.py"
archive_file "${SOURCE_BASE}/tools/verify_batch_success.py"
archive_file "${SOURCE_BASE}/tools/verify_package.py"
archive_file "${SOURCE_BASE}/tests/test_error_classifier.py"
archive_file "${SOURCE_BASE}/tests/test_subscription_integration.py"
archive_file "${SOURCE_BASE}/tests/test_subscription_load.py"
archive_file "${SOURCE_BASE}/tests/test_token_manager_retry.py"

################################################################################
# CATEGORY 9: Miscellaneous utility scripts
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 CATEGORY 9: Miscellaneous Utility Scripts${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "=== CATEGORY 9: Miscellaneous Utility Scripts ==="

archive_file "${SOURCE_BASE}/scripts/set_max_tokens.sh"
archive_file "${SOURCE_BASE}/scripts/fix_secret_newlines.sh"

################################################################################
# Summary and completion
################################################################################
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Archive Operation Complete${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Count archived files
ARCHIVED_COUNT=$(grep -c "✅ Archived:" "${LOG_FILE}" || echo "0")
WARNING_COUNT=$(grep -c "⚠️  File not found:" "${LOG_FILE}" || echo "0")

echo -e "${YELLOW}📊 Summary:${NC}"
echo -e "   ${GREEN}✓${NC} Files archived: ${ARCHIVED_COUNT}"
echo -e "   ${YELLOW}⚠${NC} Files not found: ${WARNING_COUNT}"
echo -e "   📄 Log file: ${LOG_FILE}"
echo ""

# List remaining files in TOOLS_SCRIPTS_TESTS
echo -e "${BLUE}📂 Remaining files in TOOLS_SCRIPTS_TESTS:${NC}"
echo ""

echo -e "${YELLOW}Scripts:${NC}"
find "${SOURCE_BASE}/scripts" -type f -name "*.sh" -o -name "*.sql" 2>/dev/null | sort | while read file; do
    echo "   • $(basename "$file")"
done

echo ""
echo -e "${YELLOW}Tools:${NC}"
find "${SOURCE_BASE}/tools" -type f -name "*.py" 2>/dev/null | sort | while read file; do
    echo "   • $(basename "$file")"
done

echo ""
echo -e "${YELLOW}Tests:${NC}"
find "${SOURCE_BASE}/tests" -type f -name "*.py" 2>/dev/null | sort | while read file; do
    echo "   • $(basename "$file")"
done

echo ""
echo -e "${YELLOW}Migrations:${NC}"
find "${SOURCE_BASE}/migrations" -type f -name "*.sql" 2>/dev/null | sort | while read file; do
    echo "   • $(basename "$file")"
done

echo ""
log "Archive operation completed successfully"
echo -e "${GREEN}✨ Done!${NC}"
echo ""
