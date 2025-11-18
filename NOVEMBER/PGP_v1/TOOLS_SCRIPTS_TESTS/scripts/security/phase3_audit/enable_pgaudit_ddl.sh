#!/bin/bash
################################################################################
# Phase 3: Enable pgAudit (DDL Only)
#
# Purpose: Enable audit logging for DDL operations (schema changes)
# Status: DEPLOYMENT SCRIPT - Review before execution
# Project: pgp-live
# Instance: telepaypsql
#
# This script configures:
# - pgAudit extension (DDL logging only)
# - Logs CREATE, ALTER, DROP operations
# - Low performance impact (~2-5%)
# - Minimal storage overhead
#
# IMPORTANT:
# - Start with DDL only to minimize performance impact
# - Monitor for 1 week before expanding to DML
# - Requires instance restart (~30 seconds downtime)
# - Enable storage auto-increase first
#
################################################################################

set -e

PROJECT_ID="pgp-live"
INSTANCE_NAME="telepaypsql"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📝 Enable pgAudit (DDL Operations Only)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

################################################################################
# Pre-flight Checks
################################################################################
echo -e "${YELLOW}━━━ Pre-flight Checks ━━━${NC}"

# Verify storage auto-increase is enabled
STORAGE_AUTO=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.storageAutoResize)")

if [ "$STORAGE_AUTO" != "True" ]; then
  echo -e "${RED}❌ ERROR: Storage auto-increase is not enabled${NC}"
  echo "Audit logs can fill disk. Enable storage auto-increase first."
  exit 1
fi

echo -e "✅ Storage auto-increase enabled"
echo ""

################################################################################
# Enable pgAudit (DDL Only)
################################################################################
echo -e "${YELLOW}━━━ Enabling pgAudit (DDL Only) ━━━${NC}"
echo ""

gcloud sql instances patch ${INSTANCE_NAME} \
  --database-flags=cloudsql.enable_pgaudit=on,pgaudit.log=ddl \
  --project=${PROJECT_ID}

if [ $? -eq 0 ]; then
  echo ""
  echo -e "✅ ${GREEN}pgAudit enabled (DDL only)${NC}"
else
  echo ""
  echo -e "❌ ${RED}Failed to enable pgAudit${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}Audit logging active for:${NC}"
echo "  - CREATE (tables, indexes, etc.)"
echo "  - ALTER (schema changes)"
echo "  - DROP (deletions)"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Monitor performance for 1 week"
echo "2. Check disk usage daily"
echo "3. Run enable_pgaudit_full.sh to add DML logging"
echo ""
