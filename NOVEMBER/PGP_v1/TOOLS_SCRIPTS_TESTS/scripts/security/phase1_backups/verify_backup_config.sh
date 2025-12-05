#!/bin/bash
################################################################################
# Phase 1: Verify Current Backup Configuration
#
# Purpose: Check current backup settings on Cloud SQL instance
# Status: READ-ONLY - Safe to run anytime
# Project: pgp-live
# Instance: telepaypsql
#
# This script verifies:
# - Automated backup status (enabled/disabled)
# - Backup start time (scheduled window)
# - Backup retention (number of backups kept)
# - PITR status (Point-in-Time Recovery)
# - Transaction log retention
# - Storage auto-increase settings
#
################################################################################

set -e  # Exit on error

# Configuration
PROJECT_ID="pgp-live"
INSTANCE_NAME="telepaypsql"
REGION="us-central1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📋 Cloud SQL Backup Configuration Verification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Project: ${GREEN}${PROJECT_ID}${NC}"
echo -e "Instance: ${GREEN}${INSTANCE_NAME}${NC}"
echo -e "Region: ${GREEN}${REGION}${NC}"
echo ""

################################################################################
# 1. Check Backup Configuration
################################################################################
echo -e "${YELLOW}━━━ Step 1: Backup Configuration ━━━${NC}"

BACKUP_ENABLED=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.enabled)")

if [ "$BACKUP_ENABLED" == "True" ]; then
  echo -e "✅ Automated backups: ${GREEN}ENABLED${NC}"
else
  echo -e "❌ Automated backups: ${RED}DISABLED${NC}"
  echo -e "   ${YELLOW}ACTION REQUIRED: Enable automated backups${NC}"
fi

# Get backup start time
BACKUP_START_TIME=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.startTime)")

if [ -n "$BACKUP_START_TIME" ]; then
  echo -e "🕐 Backup window: ${GREEN}${BACKUP_START_TIME} UTC${NC}"
else
  echo -e "⚠️  Backup window: ${YELLOW}Not configured${NC}"
fi

# Get backup location
BACKUP_LOCATION=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.location)")

if [ -n "$BACKUP_LOCATION" ]; then
  echo -e "📍 Backup location: ${GREEN}${BACKUP_LOCATION}${NC}"
else
  echo -e "📍 Backup location: ${YELLOW}Default (single region)${NC}"
fi

echo ""

################################################################################
# 2. Check Backup Retention
################################################################################
echo -e "${YELLOW}━━━ Step 2: Backup Retention ━━━${NC}"

RETAINED_BACKUPS=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.backupRetentionSettings.retainedBackups)")

if [ -n "$RETAINED_BACKUPS" ]; then
  echo -e "📦 Retained backups: ${GREEN}${RETAINED_BACKUPS} backups${NC}"
  if [ "$RETAINED_BACKUPS" -lt 30 ]; then
    echo -e "   ${YELLOW}RECOMMENDATION: Increase to 30 for compliance${NC}"
  fi
else
  echo -e "📦 Retained backups: ${YELLOW}Default (7 backups)${NC}"
  echo -e "   ${YELLOW}ACTION REQUIRED: Configure 30-day retention${NC}"
fi

RETENTION_UNIT=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.backupRetentionSettings.retentionUnit)")

if [ -n "$RETENTION_UNIT" ]; then
  echo -e "📅 Retention unit: ${GREEN}${RETENTION_UNIT}${NC}"
fi

echo ""

################################################################################
# 3. Check Point-in-Time Recovery (PITR)
################################################################################
echo -e "${YELLOW}━━━ Step 3: Point-in-Time Recovery (PITR) ━━━${NC}"

PITR_ENABLED=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.pointInTimeRecoveryEnabled)")

if [ "$PITR_ENABLED" == "True" ]; then
  echo -e "✅ PITR: ${GREEN}ENABLED${NC}"
else
  echo -e "❌ PITR: ${RED}DISABLED${NC}"
  echo -e "   ${YELLOW}ACTION REQUIRED: Enable Point-in-Time Recovery${NC}"
fi

# Get transaction log retention
TX_LOG_RETENTION=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.transactionLogRetentionDays)")

if [ -n "$TX_LOG_RETENTION" ]; then
  echo -e "📝 Transaction log retention: ${GREEN}${TX_LOG_RETENTION} days${NC}"
  if [ "$TX_LOG_RETENTION" -lt 7 ]; then
    echo -e "   ${YELLOW}RECOMMENDATION: Increase to 7 days${NC}"
  fi
else
  echo -e "📝 Transaction log retention: ${YELLOW}Not configured${NC}"
  echo -e "   ${YELLOW}ACTION REQUIRED: Configure 7-day retention${NC}"
fi

echo ""

################################################################################
# 4. Check Storage Auto-Increase
################################################################################
echo -e "${YELLOW}━━━ Step 4: Storage Auto-Increase ━━━${NC}"

STORAGE_AUTO_INCREASE=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.storageAutoResize)")

if [ "$STORAGE_AUTO_INCREASE" == "True" ]; then
  echo -e "✅ Storage auto-increase: ${GREEN}ENABLED${NC}"
else
  echo -e "❌ Storage auto-increase: ${RED}DISABLED${NC}"
  echo -e "   ${YELLOW}ACTION REQUIRED: Enable to prevent disk full${NC}"
fi

STORAGE_AUTO_INCREASE_LIMIT=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.storageAutoResizeLimit)")

if [ -n "$STORAGE_AUTO_INCREASE_LIMIT" ] && [ "$STORAGE_AUTO_INCREASE_LIMIT" != "0" ]; then
  echo -e "💾 Storage limit: ${GREEN}${STORAGE_AUTO_INCREASE_LIMIT} GB${NC}"
else
  echo -e "💾 Storage limit: ${YELLOW}No limit set${NC}"
fi

# Get current disk size
DISK_SIZE=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.dataDiskSizeGb)")

echo -e "💿 Current disk size: ${GREEN}${DISK_SIZE} GB${NC}"

echo ""

################################################################################
# 5. List Recent Backups
################################################################################
echo -e "${YELLOW}━━━ Step 5: Recent Backups ━━━${NC}"

echo "Fetching last 5 backups..."
gcloud sql backups list \
  --instance=${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --limit=5 \
  --format="table(id, windowStartTime, status, type)"

echo ""

################################################################################
# 6. Summary and Recommendations
################################################################################
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Summary and Recommendations${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Compile status
ISSUES_FOUND=0

if [ "$BACKUP_ENABLED" != "True" ]; then
  echo -e "❌ ${RED}CRITICAL:${NC} Automated backups are disabled"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

if [ "$PITR_ENABLED" != "True" ]; then
  echo -e "❌ ${RED}CRITICAL:${NC} Point-in-Time Recovery is disabled"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

if [ "$STORAGE_AUTO_INCREASE" != "True" ]; then
  echo -e "⚠️  ${YELLOW}WARNING:${NC} Storage auto-increase is disabled (risk of disk full)"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

if [ -z "$RETAINED_BACKUPS" ] || [ "$RETAINED_BACKUPS" -lt 30 ]; then
  echo -e "⚠️  ${YELLOW}WARNING:${NC} Backup retention is less than 30 days (compliance risk)"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

if [ -z "$TX_LOG_RETENTION" ] || [ "$TX_LOG_RETENTION" -lt 7 ]; then
  echo -e "⚠️  ${YELLOW}WARNING:${NC} Transaction log retention is less than 7 days"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

echo ""

if [ $ISSUES_FOUND -eq 0 ]; then
  echo -e "✅ ${GREEN}All backup settings are properly configured!${NC}"
else
  echo -e "⚠️  ${YELLOW}Found ${ISSUES_FOUND} configuration issue(s) to address${NC}"
  echo ""
  echo -e "${YELLOW}Next Steps:${NC}"
  echo "1. Review the issues listed above"
  echo "2. Run the appropriate configuration scripts:"
  echo "   - enable_automated_backups.sh"
  echo "   - enable_pitr.sh"
  echo "3. Re-run this script to verify changes"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Verification complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
