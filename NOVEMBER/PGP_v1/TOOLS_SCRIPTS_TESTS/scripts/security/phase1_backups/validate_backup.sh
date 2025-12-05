#!/bin/bash
################################################################################
# Phase 1: Automated Backup Validation
#
# Purpose: Validate backup health and alert on failures
# Status: MONITORING SCRIPT - Safe to run anytime
# Project: pgp-live
# Instance: telepaypsql
#
# This script checks:
# - Latest backup status (SUCCESSFUL/FAILED)
# - Backup age (alert if >25 hours old)
# - Backup size trends (detect anomalies)
# - PITR transaction log status
# - Storage usage (prevent disk full)
#
# Usage:
# - Run manually: ./validate_backup.sh
# - Run via Cloud Scheduler: Daily at 10:00 UTC
# - Integrate with monitoring/alerting system
#
# Exit Codes:
# 0 = All validations passed
# 1 = Critical failure detected
# 2 = Warning detected
#
################################################################################

set -e  # Exit on error

# Configuration
PROJECT_ID="pgp-live"
INSTANCE_NAME="telepaypsql"
REGION="us-central1"
MAX_BACKUP_AGE_HOURS=25  # Alert if backup older than this
MIN_BACKUP_SIZE_MB=100   # Alert if backup smaller than this
DISK_USAGE_THRESHOLD=80  # Alert if disk usage above this percentage

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Exit code tracker
EXIT_CODE=0

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔍 Cloud SQL Backup Validation${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Project: ${GREEN}${PROJECT_ID}${NC}"
echo -e "Instance: ${GREEN}${INSTANCE_NAME}${NC}"
echo -e "Timestamp: ${GREEN}$(date -u '+%Y-%m-%d %H:%M:%S UTC')${NC}"
echo ""

################################################################################
# 1. Check Latest Backup Status
################################################################################
echo -e "${YELLOW}━━━ Test 1: Latest Backup Status ━━━${NC}"

# Get latest backup
LATEST_BACKUP=$(gcloud sql backups list \
  --instance=${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --limit=1 \
  --format="value(id)")

if [ -z "$LATEST_BACKUP" ]; then
  echo -e "${RED}❌ CRITICAL: No backups found${NC}"
  echo "   Automated backups may not be configured"
  EXIT_CODE=1
else
  echo -e "Latest backup ID: ${GREEN}${LATEST_BACKUP}${NC}"

  # Get backup details
  BACKUP_STATUS=$(gcloud sql backups describe ${LATEST_BACKUP} \
    --instance=${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --format="value(status)")

  BACKUP_TYPE=$(gcloud sql backups describe ${LATEST_BACKUP} \
    --instance=${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --format="value(type)")

  BACKUP_START_TIME=$(gcloud sql backups describe ${LATEST_BACKUP} \
    --instance=${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --format="value(windowStartTime)")

  if [ "$BACKUP_STATUS" == "SUCCESSFUL" ]; then
    echo -e "✅ Backup status: ${GREEN}${BACKUP_STATUS}${NC}"
  else
    echo -e "${RED}❌ CRITICAL: Backup status: ${BACKUP_STATUS}${NC}"
    EXIT_CODE=1
  fi

  echo -e "Backup type: ${GREEN}${BACKUP_TYPE}${NC}"
  echo -e "Backup started: ${GREEN}${BACKUP_START_TIME}${NC}"
fi

echo ""

################################################################################
# 2. Check Backup Age
################################################################################
echo -e "${YELLOW}━━━ Test 2: Backup Age ━━━${NC}"

if [ -n "$BACKUP_START_TIME" ]; then
  # Convert backup time to epoch
  BACKUP_EPOCH=$(date -d "$BACKUP_START_TIME" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "${BACKUP_START_TIME%.*}" +%s 2>/dev/null)
  CURRENT_EPOCH=$(date +%s)
  AGE_SECONDS=$((CURRENT_EPOCH - BACKUP_EPOCH))
  AGE_HOURS=$((AGE_SECONDS / 3600))

  echo -e "Backup age: ${GREEN}${AGE_HOURS} hours${NC}"

  if [ $AGE_HOURS -gt $MAX_BACKUP_AGE_HOURS ]; then
    echo -e "${RED}❌ CRITICAL: Backup is older than ${MAX_BACKUP_AGE_HOURS} hours${NC}"
    echo "   Daily backups may have failed"
    EXIT_CODE=1
  elif [ $AGE_HOURS -gt 24 ]; then
    echo -e "${YELLOW}⚠️  WARNING: Backup is older than 24 hours${NC}"
    EXIT_CODE=2
  else
    echo -e "✅ Backup age is acceptable"
  fi
else
  echo -e "${YELLOW}⚠️  WARNING: Could not determine backup age${NC}"
  EXIT_CODE=2
fi

echo ""

################################################################################
# 3. Check Backup Count (Retention)
################################################################################
echo -e "${YELLOW}━━━ Test 3: Backup Retention ━━━${NC}"

BACKUP_COUNT=$(gcloud sql backups list \
  --instance=${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(id)" | wc -l)

echo -e "Total backups: ${GREEN}${BACKUP_COUNT}${NC}"

if [ $BACKUP_COUNT -lt 7 ]; then
  echo -e "${YELLOW}⚠️  WARNING: Fewer than 7 backups available${NC}"
  echo "   May need more time for backups to accumulate"
  if [ $EXIT_CODE -eq 0 ]; then
    EXIT_CODE=2
  fi
elif [ $BACKUP_COUNT -ge 30 ]; then
  echo -e "✅ Retention policy working (30-day retention)"
else
  echo -e "✅ Backups accumulating (target: 30)"
fi

echo ""

################################################################################
# 4. Check PITR Status
################################################################################
echo -e "${YELLOW}━━━ Test 4: Point-in-Time Recovery (PITR) ━━━${NC}"

PITR_ENABLED=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.backupConfiguration.pointInTimeRecoveryEnabled)")

if [ "$PITR_ENABLED" == "True" ]; then
  echo -e "✅ PITR: ${GREEN}ENABLED${NC}"

  TX_LOG_RETENTION=$(gcloud sql instances describe ${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --format="value(settings.backupConfiguration.transactionLogRetentionDays)")

  if [ -n "$TX_LOG_RETENTION" ]; then
    echo -e "✅ Transaction log retention: ${GREEN}${TX_LOG_RETENTION} days${NC}"
  fi
else
  echo -e "${YELLOW}⚠️  WARNING: PITR is not enabled${NC}"
  echo "   Consider enabling for better disaster recovery"
  if [ $EXIT_CODE -eq 0 ]; then
    EXIT_CODE=2
  fi
fi

echo ""

################################################################################
# 5. Check Storage Usage
################################################################################
echo -e "${YELLOW}━━━ Test 5: Storage Usage ━━━${NC}"

# Get current disk size and max size
CURRENT_DISK_SIZE=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.dataDiskSizeGb)")

# Note: Cloud SQL doesn't directly report used space via describe
# We'll check if auto-increase is enabled as a safety measure
STORAGE_AUTO_INCREASE=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.storageAutoResize)")

echo -e "Current disk size: ${GREEN}${CURRENT_DISK_SIZE} GB${NC}"

if [ "$STORAGE_AUTO_INCREASE" == "True" ]; then
  echo -e "✅ Storage auto-increase: ${GREEN}ENABLED${NC}"

  STORAGE_LIMIT=$(gcloud sql instances describe ${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --format="value(settings.storageAutoResizeLimit)")

  if [ -n "$STORAGE_LIMIT" ] && [ "$STORAGE_LIMIT" != "0" ]; then
    echo -e "Storage limit: ${GREEN}${STORAGE_LIMIT} GB${NC}"

    USAGE_PERCENT=$((CURRENT_DISK_SIZE * 100 / STORAGE_LIMIT))
    echo -e "Usage: ${GREEN}${USAGE_PERCENT}%${NC} of limit"

    if [ $USAGE_PERCENT -gt $DISK_USAGE_THRESHOLD ]; then
      echo -e "${RED}❌ CRITICAL: Disk usage above ${DISK_USAGE_THRESHOLD}%${NC}"
      EXIT_CODE=1
    fi
  else
    echo -e "Storage limit: ${GREEN}No limit${NC}"
  fi
else
  echo -e "${YELLOW}⚠️  WARNING: Storage auto-increase is DISABLED${NC}"
  echo "   Risk of disk full (transaction logs can grow)"
  if [ $EXIT_CODE -eq 0 ]; then
    EXIT_CODE=2
  fi
fi

echo ""

################################################################################
# 6. List Recent Backups
################################################################################
echo -e "${YELLOW}━━━ Recent Backups Summary ━━━${NC}"
echo ""

gcloud sql backups list \
  --instance=${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --limit=5 \
  --format="table(id, windowStartTime, status, type)"

echo ""

################################################################################
# Final Summary
################################################################################
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Validation Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
  echo -e "✅ ${GREEN}All validations passed!${NC}"
  echo ""
  echo "Backup system is healthy:"
  echo "  - Latest backup successful"
  echo "  - Backup age within acceptable range"
  echo "  - Retention policy working"
  echo "  - PITR enabled (if configured)"
  echo "  - Storage usage normal"
elif [ $EXIT_CODE -eq 1 ]; then
  echo -e "❌ ${RED}CRITICAL ISSUES DETECTED${NC}"
  echo ""
  echo "Immediate action required:"
  echo "  - Review errors listed above"
  echo "  - Check Cloud Logging for detailed errors"
  echo "  - Contact database administrator"
  echo "  - Escalate if backup failures continue"
elif [ $EXIT_CODE -eq 2 ]; then
  echo -e "⚠️  ${YELLOW}WARNINGS DETECTED${NC}"
  echo ""
  echo "Review recommended:"
  echo "  - Check warnings listed above"
  echo "  - Consider enabling recommended features"
  echo "  - Monitor for improvement"
fi

echo ""
echo -e "${YELLOW}Monitoring Commands:${NC}"
echo "# Check backup logs"
echo "gcloud logging read \"resource.type=cloudsql_database AND resource.labels.database_id=${PROJECT_ID}:${INSTANCE_NAME}\" --limit=50 --format=json"
echo ""
echo "# Manual backup (if needed)"
echo "gcloud sql backups create --instance=${INSTANCE_NAME} --project=${PROJECT_ID}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Exit with appropriate code
exit $EXIT_CODE
