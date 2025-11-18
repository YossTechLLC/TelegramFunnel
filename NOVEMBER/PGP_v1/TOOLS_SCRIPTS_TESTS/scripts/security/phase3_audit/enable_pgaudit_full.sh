#!/bin/bash
################################################################################
# Phase 3: Enable pgAudit (Full Logging)
#
# Purpose: Enable audit logging for ALL operations (DDL + DML)
# Status: DEPLOYMENT SCRIPT - Only run after DDL monitoring period
# Project: pgp-live
# Instance: telepaypsql
#
# This script configures:
# - pgAudit extension (ALL operations)
# - Logs DDL: CREATE, ALTER, DROP
# - Logs DML: INSERT, UPDATE, DELETE
# - Performance impact (~5-10%)
# - Higher storage overhead
#
# PREREQUISITES:
# - DDL logging running for at least 1 week
# - Performance impact acceptable (<5%)
# - Disk usage stable
# - Storage auto-increase enabled
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
echo -e "${BLUE}📝 Enable pgAudit (Full Logging - DDL + DML)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

################################################################################
# Enable pgAudit (Full)
################################################################################
echo -e "${YELLOW}━━━ Enabling pgAudit (DDL + DML + READ) ━━━${NC}"
echo ""

gcloud sql instances patch ${INSTANCE_NAME} \
  --database-flags=cloudsql.enable_pgaudit=on,pgaudit.log=all \
  --project=${PROJECT_ID}

if [ $? -eq 0 ]; then
  echo ""
  echo -e "✅ ${GREEN}pgAudit enabled (full logging)${NC}"
else
  echo ""
  echo -e "❌ ${RED}Failed to enable full pgAudit${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}Audit logging active for:${NC}"
echo "  - DDL: CREATE, ALTER, DROP"
echo "  - DML: INSERT, UPDATE, DELETE"
echo "  - READ: SELECT queries"
echo "  - ALL: Complete audit trail"
echo ""
echo -e "${YELLOW}Monitor closely:${NC}"
echo "  - Performance impact (should be <10%)"
echo "  - Disk usage (logs can grow quickly)"
echo "  - Cloud Logging ingestion costs"
echo ""
