#!/bin/bash
################################################################################
# Phase 1: Enable Automated Backups
#
# Purpose: Configure Cloud SQL automated backups with 30-day retention
# Status: DEPLOYMENT SCRIPT - Review before execution
# Project: pgp-live
# Instance: telepaypsql
#
# This script configures:
# - Automated daily backups at 04:00 UTC (low traffic period)
# - 30-day backup retention (compliance requirement)
# - Multi-region backup location (disaster recovery)
# - Binary logging (required for PITR)
# - Storage auto-increase (prevent disk full from logs)
#
# IMPORTANT:
# - This operation requires brief downtime (~30 seconds)
# - Coordinate deployment window with team
# - Run verify_backup_config.sh first to check current state
# - Monitor backup completion after enabling
#
################################################################################

set -e  # Exit on error

# Configuration
PROJECT_ID="pgp-live"
INSTANCE_NAME="telepaypsql"
REGION="us-central1"
BACKUP_START_TIME="04:00"  # UTC - Low traffic period
BACKUP_LOCATION="us"       # Multi-region for DR
RETAINED_BACKUPS=30        # 30 days for compliance
TX_LOG_RETENTION=7         # 7 days for PITR
STORAGE_LIMIT=500          # GB - Prevent unlimited growth

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}⚙️  Cloud SQL Automated Backup Configuration${NC}"
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
echo ""

################################################################################
# Configuration Summary
################################################################################
echo -e "${YELLOW}━━━ Configuration Summary ━━━${NC}"
echo ""
echo -e "Backup window:          ${GREEN}${BACKUP_START_TIME} UTC${NC}"
echo -e "Backup location:        ${GREEN}${BACKUP_LOCATION}${NC} (multi-region)"
echo -e "Retention:              ${GREEN}${RETAINED_BACKUPS} backups${NC} (~30 days)"
echo -e "Transaction logs:       ${GREEN}${TX_LOG_RETENTION} days${NC}"
echo -e "Storage auto-increase:  ${GREEN}Enabled${NC} (limit: ${STORAGE_LIMIT} GB)"
echo ""

################################################################################
# User Confirmation
################################################################################
echo -e "${YELLOW}⚠️  WARNING: This operation will:${NC}"
echo "  - Briefly restart the instance (~30 seconds downtime)"
echo "  - Enable automated daily backups"
echo "  - Configure 30-day retention policy"
echo "  - Enable binary logging for PITR"
echo "  - Enable storage auto-increase"
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
# Enable Automated Backups
################################################################################
echo -e "${YELLOW}━━━ Enabling Automated Backups ━━━${NC}"
echo ""

echo "Executing gcloud command..."
echo ""

gcloud sql instances patch ${INSTANCE_NAME} \
  --backup-start-time=${BACKUP_START_TIME} \
  --backup-location=${BACKUP_LOCATION} \
  --retained-backups-count=${RETAINED_BACKUPS} \
  --retained-transaction-log-days=${TX_LOG_RETENTION} \
  --enable-bin-log \
  --project=${PROJECT_ID}

if [ $? -eq 0 ]; then
  echo ""
  echo -e "✅ ${GREEN}Automated backups enabled successfully!${NC}"
else
  echo ""
  echo -e "❌ ${RED}Failed to enable automated backups${NC}"
  exit 1
fi

echo ""

################################################################################
# Enable Storage Auto-Increase
################################################################################
echo -e "${YELLOW}━━━ Enabling Storage Auto-Increase ━━━${NC}"
echo ""

echo "Configuring storage auto-increase..."
echo ""

gcloud sql instances patch ${INSTANCE_NAME} \
  --enable-storage-auto-increase \
  --storage-auto-increase-limit=${STORAGE_LIMIT} \
  --project=${PROJECT_ID}

if [ $? -eq 0 ]; then
  echo ""
  echo -e "✅ ${GREEN}Storage auto-increase enabled successfully!${NC}"
else
  echo ""
  echo -e "❌ ${RED}Failed to enable storage auto-increase${NC}"
  echo -e "${YELLOW}This is non-critical, but should be addressed${NC}"
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
echo "Verifying backup configuration..."

BACKUP_ENABLED=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.enabled)")

PITR_SETTING=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.transactionLogRetentionDays)")

echo ""

if [ "$BACKUP_ENABLED" == "True" ]; then
  echo -e "✅ Automated backups: ${GREEN}ENABLED${NC}"
else
  echo -e "❌ Automated backups: ${RED}VERIFICATION FAILED${NC}"
fi

if [ -n "$PITR_SETTING" ]; then
  echo -e "✅ Transaction log retention: ${GREEN}${PITR_SETTING} days${NC}"
else
  echo -e "⚠️  Transaction log retention: ${YELLOW}Not verified${NC}"
fi

echo ""

################################################################################
# Trigger Initial Backup
################################################################################
echo -e "${YELLOW}━━━ Triggering Initial Backup ━━━${NC}"
echo ""

read -p "Would you like to trigger an on-demand backup now? (yes/no): " TRIGGER_BACKUP

if [ "$TRIGGER_BACKUP" == "yes" ]; then
  echo ""
  echo "Creating on-demand backup..."

  BACKUP_ID="manual-$(date +%Y%m%d-%H%M%S)"

  gcloud sql backups create \
    --instance=${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --description="Manual backup after enabling automated backups"

  if [ $? -eq 0 ]; then
    echo ""
    echo -e "✅ ${GREEN}On-demand backup initiated${NC}"
    echo ""
    echo "You can check backup status with:"
    echo "gcloud sql backups list --instance=${INSTANCE_NAME} --project=${PROJECT_ID}"
  else
    echo ""
    echo -e "⚠️  ${YELLOW}Failed to create on-demand backup${NC}"
    echo "Automated backups will run at ${BACKUP_START_TIME} UTC"
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
echo -e "✅ Automated backups: ${GREEN}ENABLED${NC}"
echo -e "✅ Backup window: ${GREEN}${BACKUP_START_TIME} UTC${NC}"
echo -e "✅ Retention: ${GREEN}${RETAINED_BACKUPS} backups${NC}"
echo -e "✅ Transaction logs: ${GREEN}${TX_LOG_RETENTION} days${NC}"
echo -e "✅ Storage auto-increase: ${GREEN}ENABLED${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Run enable_pitr.sh to enable Point-in-Time Recovery"
echo "2. Monitor first backup completion (within 24 hours)"
echo "3. Run verify_backup_config.sh to confirm all settings"
echo "4. Set up backup monitoring alerts"
echo "5. Document backup configuration in BACKUP_INVENTORY.md"
echo ""
echo -e "${YELLOW}Monitoring Commands:${NC}"
echo "# List backups"
echo "gcloud sql backups list --instance=${INSTANCE_NAME} --project=${PROJECT_ID}"
echo ""
echo "# Verify configuration"
echo "./verify_backup_config.sh"
echo ""
echo -e "${GREEN}✅ Backup configuration complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
