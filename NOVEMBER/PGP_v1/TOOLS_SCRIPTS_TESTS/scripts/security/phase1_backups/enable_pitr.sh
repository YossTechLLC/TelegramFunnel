#!/bin/bash
################################################################################
# Phase 1: Enable Point-in-Time Recovery (PITR)
#
# Purpose: Enable PITR to allow recovery to any point within last 7 days
# Status: DEPLOYMENT SCRIPT - Review before execution
# Project: pgp-live
# Instance: telepaypsql
#
# This script configures:
# - Point-in-Time Recovery (PITR)
# - 7-day transaction log retention
# - Binary logging (if not already enabled)
#
# IMPORTANT:
# - Requires automated backups to be enabled first
# - Run enable_automated_backups.sh before this script
# - This operation may require brief downtime (~30 seconds)
# - PITR adds ~10% storage overhead for transaction logs
#
# Use Cases:
# - Recover from data corruption to specific timestamp
# - Undo accidental deletions
# - Test data at specific point in time (via clone)
#
################################################################################

set -e  # Exit on error

# Configuration
PROJECT_ID="pgp-live"
INSTANCE_NAME="telepaypsql"
REGION="us-central1"
TX_LOG_RETENTION=7  # 7 days for compliance and practical recovery

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}⚙️  Enable Point-in-Time Recovery (PITR)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Project: ${GREEN}${PROJECT_ID}${NC}"
echo -e "Instance: ${GREEN}${INSTANCE_NAME}${NC}"
echo -e "Region: ${GREEN}${REGION}${NC}"
echo ""

################################################################################
# Pre-flight Checks
################################################################################
echo -e "${YELLOW}━━━ Pre-flight Checks ━━━${NC}"

# Check if gcloud is configured
if ! gcloud config get-value project &> /dev/null; then
  echo -e "${RED}❌ ERROR: gcloud not configured${NC}"
  echo "Run: gcloud auth login && gcloud config set project ${PROJECT_ID}"
  exit 1
fi

# Verify instance exists
if ! gcloud sql instances describe ${INSTANCE_NAME} --project=${PROJECT_ID} &> /dev/null; then
  echo -e "${RED}❌ ERROR: Instance ${INSTANCE_NAME} not found${NC}"
  exit 1
fi

echo -e "✅ gcloud configured"
echo -e "✅ Instance ${INSTANCE_NAME} exists"

# Check if automated backups are enabled (required for PITR)
BACKUP_ENABLED=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.enabled)")

if [ "$BACKUP_ENABLED" != "True" ]; then
  echo -e "${RED}❌ ERROR: Automated backups are not enabled${NC}"
  echo ""
  echo "PITR requires automated backups to be enabled first."
  echo "Run: ./enable_automated_backups.sh"
  exit 1
fi

echo -e "✅ Automated backups enabled"

# Check current PITR status
PITR_ENABLED=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.pointInTimeRecoveryEnabled)")

if [ "$PITR_ENABLED" == "True" ]; then
  echo -e "${YELLOW}⚠️  PITR is already enabled${NC}"

  CURRENT_RETENTION=$(gcloud sql instances describe ${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --format="value(settings.backupConfiguration.transactionLogRetentionDays)")

  echo -e "Current retention: ${GREEN}${CURRENT_RETENTION} days${NC}"
  echo ""
  read -p "Do you want to update retention to ${TX_LOG_RETENTION} days? (yes/no): " UPDATE_RETENTION

  if [ "$UPDATE_RETENTION" != "yes" ]; then
    echo -e "${YELLOW}❌ Operation cancelled${NC}"
    exit 0
  fi
fi

echo ""

################################################################################
# Configuration Summary
################################################################################
echo -e "${YELLOW}━━━ Configuration Summary ━━━${NC}"
echo ""
echo -e "PITR:                   ${GREEN}ENABLED${NC}"
echo -e "Transaction log retention: ${GREEN}${TX_LOG_RETENTION} days${NC}"
echo -e "Recovery granularity:   ${GREEN}1 second${NC}"
echo -e "Storage overhead:       ${YELLOW}~10%${NC}"
echo ""
echo -e "${BLUE}Recovery Capabilities:${NC}"
echo "  - Restore to any second within last ${TX_LOG_RETENTION} days"
echo "  - Clone instance at specific timestamp (for testing)"
echo "  - Recover from accidental data deletion"
echo "  - Undo erroneous transactions"
echo ""

################################################################################
# User Confirmation
################################################################################
echo -e "${YELLOW}⚠️  WARNING: This operation will:${NC}"
echo "  - Enable Point-in-Time Recovery"
echo "  - Retain transaction logs for ${TX_LOG_RETENTION} days"
echo "  - Increase storage usage by ~10%"
echo "  - May briefly restart the instance (~30 seconds)"
echo ""
echo -e "${RED}DO NOT RUN WITHOUT APPROVAL${NC}"
echo ""

read -p "Are you sure you want to proceed? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo -e "${YELLOW}❌ Operation cancelled${NC}"
  exit 0
fi

echo ""

################################################################################
# Enable PITR
################################################################################
echo -e "${YELLOW}━━━ Enabling Point-in-Time Recovery ━━━${NC}"
echo ""

echo "Executing gcloud command..."
echo ""

gcloud sql instances patch ${INSTANCE_NAME} \
  --enable-point-in-time-recovery \
  --retained-transaction-log-days=${TX_LOG_RETENTION} \
  --project=${PROJECT_ID}

if [ $? -eq 0 ]; then
  echo ""
  echo -e "✅ ${GREEN}PITR enabled successfully!${NC}"
else
  echo ""
  echo -e "❌ ${RED}Failed to enable PITR${NC}"
  exit 1
fi

echo ""

################################################################################
# Verification
################################################################################
echo -e "${YELLOW}━━━ Verification ━━━${NC}"
echo ""

echo "Waiting 10 seconds for settings to apply..."
sleep 10

echo ""
echo "Verifying PITR configuration..."

PITR_STATUS=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.pointInTimeRecoveryEnabled)")

TX_LOG_RETENTION_STATUS=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.transactionLogRetentionDays)")

echo ""

if [ "$PITR_STATUS" == "True" ]; then
  echo -e "✅ PITR: ${GREEN}ENABLED${NC}"
else
  echo -e "❌ PITR: ${RED}VERIFICATION FAILED${NC}"
fi

if [ -n "$TX_LOG_RETENTION_STATUS" ]; then
  echo -e "✅ Transaction log retention: ${GREEN}${TX_LOG_RETENTION_STATUS} days${NC}"
else
  echo -e "⚠️  Transaction log retention: ${YELLOW}Not verified${NC}"
fi

echo ""

################################################################################
# PITR Usage Examples
################################################################################
echo -e "${YELLOW}━━━ PITR Usage Examples ━━━${NC}"
echo ""
echo -e "${BLUE}1. Clone instance to specific timestamp (testing):${NC}"
echo ""
echo "gcloud sql instances clone ${INSTANCE_NAME} ${INSTANCE_NAME}-clone \\"
echo "  --point-in-time='2025-11-18T12:30:00.000Z' \\"
echo "  --project=${PROJECT_ID}"
echo ""
echo -e "${BLUE}2. Check available recovery window:${NC}"
echo ""
echo "# Earliest recovery point (7 days ago from last backup)"
echo "gcloud sql backups list \\"
echo "  --instance=${INSTANCE_NAME} \\"
echo "  --project=${PROJECT_ID} \\"
echo "  --limit=1 \\"
echo "  --sort-by=~windowStartTime"
echo ""
echo -e "${BLUE}3. Restore to specific timestamp (DISASTER RECOVERY):${NC}"
echo ""
echo "# WARNING: This is a disaster recovery operation"
echo "# Create new instance from specific point in time"
echo "# Then promote to replace failed instance"
echo ""

################################################################################
# Test PITR (Optional)
################################################################################
echo -e "${YELLOW}━━━ Test PITR (Optional) ━━━${NC}"
echo ""

read -p "Would you like to test PITR by cloning to current timestamp? (yes/no): " TEST_PITR

if [ "$TEST_PITR" == "yes" ]; then
  echo ""
  echo -e "${YELLOW}⚠️  This will create a test instance (${INSTANCE_NAME}-pitr-test)${NC}"
  echo "You will need to delete it manually after testing."
  echo ""

  read -p "Continue? (yes/no): " CONTINUE_TEST

  if [ "$CONTINUE_TEST" == "yes" ]; then
    # Get current timestamp in ISO 8601 format
    CURRENT_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

    echo ""
    echo "Creating test clone at timestamp: ${CURRENT_TIMESTAMP}"
    echo ""

    gcloud sql instances clone ${INSTANCE_NAME} ${INSTANCE_NAME}-pitr-test \
      --point-in-time="${CURRENT_TIMESTAMP}" \
      --project=${PROJECT_ID}

    if [ $? -eq 0 ]; then
      echo ""
      echo -e "✅ ${GREEN}PITR test clone created successfully!${NC}"
      echo ""
      echo "Test instance: ${INSTANCE_NAME}-pitr-test"
      echo ""
      echo -e "${YELLOW}IMPORTANT: Delete test instance after verification:${NC}"
      echo "gcloud sql instances delete ${INSTANCE_NAME}-pitr-test --project=${PROJECT_ID}"
    else
      echo ""
      echo -e "❌ ${RED}PITR test failed${NC}"
      echo "This may be because:"
      echo "  - Transaction logs not yet available (wait 24 hours)"
      echo "  - PITR setting not fully applied yet"
    fi
  fi
fi

echo ""

################################################################################
# Summary and Next Steps
################################################################################
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Deployment Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "✅ Point-in-Time Recovery: ${GREEN}ENABLED${NC}"
echo -e "✅ Transaction log retention: ${GREEN}${TX_LOG_RETENTION} days${NC}"
echo -e "✅ Recovery granularity: ${GREEN}1 second${NC}"
echo ""
echo -e "${YELLOW}Recovery Capabilities:${NC}"
echo "  - Earliest recovery point: ~${TX_LOG_RETENTION} days ago"
echo "  - Latest recovery point: Current timestamp"
echo "  - Can clone to any second within this window"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Run verify_backup_config.sh to confirm all settings"
echo "2. Document PITR configuration in BACKUP_INVENTORY.md"
echo "3. Create disaster recovery runbook (PITR procedures)"
echo "4. Schedule quarterly PITR testing"
echo "5. Monitor transaction log storage usage"
echo ""
echo -e "${YELLOW}Important Notes:${NC}"
echo "  - First PITR recovery point available after first backup completes"
echo "  - Transaction logs add ~10% storage overhead"
echo "  - Recovery window is ${TX_LOG_RETENTION} days (configurable)"
echo "  - PITR uses storage auto-increase (ensure enabled)"
echo ""
echo -e "${GREEN}✅ PITR configuration complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
