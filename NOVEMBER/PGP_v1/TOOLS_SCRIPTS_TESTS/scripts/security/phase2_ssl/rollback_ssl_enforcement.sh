#!/bin/bash
################################################################################
# Phase 2: Rollback SSL/TLS Enforcement
#
# Purpose: Disable SSL/TLS enforcement (emergency rollback)
# Status: ROLLBACK SCRIPT - Use only if SSL enforcement causes issues
# Project: pgp-live
# Instance: telepaypsql
#
# IMPORTANT:
# - This is an EMERGENCY rollback script
# - Only use if SSL enforcement breaks connectivity
# - This operation requires instance restart (~30 seconds downtime)
# - After rollback, investigate and fix SSL issues before re-enabling
#
# WARNING:
# - Rollback allows UNENCRYPTED connections (security risk)
# - This should be temporary (24-48 hours maximum)
# - Must re-enable SSL enforcement after fixing issues
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

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}⚠️  ROLLBACK SSL/TLS ENFORCEMENT${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

# Check current SSL status
CURRENT_REQUIRE_SSL=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.ipConfiguration.requireSsl)")

if [ "$CURRENT_REQUIRE_SSL" != "True" ]; then
  echo -e "${YELLOW}⚠️  SSL enforcement is already disabled${NC}"
  echo "No rollback needed"
  exit 0
fi

echo ""

################################################################################
# Rollback Justification
################################################################################
echo -e "${RED}━━━ ROLLBACK JUSTIFICATION REQUIRED ━━━${NC}"
echo ""
echo "This rollback will DISABLE SSL enforcement, allowing unencrypted connections."
echo "This is a SECURITY RISK and should only be used in emergencies."
echo ""
echo -e "${YELLOW}Common reasons for rollback:${NC}"
echo "  1. Services cannot connect after enabling SSL"
echo "  2. Cloud SQL Connector not properly configured"
echo "  3. Certificate validation failing"
echo "  4. Critical production outage"
echo ""

read -p "What is the reason for this rollback? (required): " ROLLBACK_REASON

if [ -z "$ROLLBACK_REASON" ]; then
  echo -e "${RED}❌ Rollback reason is required${NC}"
  exit 1
fi

echo ""
echo -e "Rollback reason: ${YELLOW}${ROLLBACK_REASON}${NC}"
echo ""

# Log rollback event
echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] SSL ROLLBACK: ${ROLLBACK_REASON}" >> /tmp/ssl_rollback_log.txt

################################################################################
# User Confirmation
################################################################################
echo -e "${RED}⚠️  CRITICAL WARNING:${NC}"
echo ""
echo "This operation will:"
echo "  - DISABLE SSL/TLS enforcement"
echo "  - ALLOW unencrypted database connections"
echo "  - EXPOSE data to potential interception"
echo "  - Restart the instance (~30 seconds downtime)"
echo ""
echo -e "${RED}This is a SECURITY REGRESSION${NC}"
echo ""
echo -e "${YELLOW}You MUST:${NC}"
echo "  1. Fix SSL issues within 24-48 hours"
echo "  2. Re-enable SSL enforcement ASAP"
echo "  3. Document incident and resolution"
echo "  4. Notify security team of temporary vulnerability"
echo ""

read -p "Type 'ROLLBACK' to confirm this emergency action: " CONFIRM

if [ "$CONFIRM" != "ROLLBACK" ]; then
  echo -e "${YELLOW}❌ Rollback cancelled${NC}"
  exit 0
fi

echo ""

################################################################################
# Disable SSL Enforcement
################################################################################
echo -e "${YELLOW}━━━ Disabling SSL/TLS Enforcement ━━━${NC}"
echo ""

echo "Executing gcloud command..."
echo ""

gcloud sql instances patch ${INSTANCE_NAME} \
  --no-require-ssl \
  --project=${PROJECT_ID}

if [ $? -eq 0 ]; then
  echo ""
  echo -e "✅ ${GREEN}SSL/TLS enforcement disabled${NC}"
  echo -e "${RED}⚠️  Unencrypted connections are now allowed (SECURITY RISK)${NC}"
else
  echo ""
  echo -e "❌ ${RED}Failed to disable SSL/TLS enforcement${NC}"
  exit 1
fi

echo ""

################################################################################
# Verification
################################################################################
echo -e "${YELLOW}━━━ Verification ━━━${NC}"
echo ""

echo "Waiting 15 seconds for instance to restart..."
sleep 15

echo ""
echo "Verifying SSL enforcement is disabled..."

REQUIRE_SSL=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.ipConfiguration.requireSsl)")

echo ""

if [ "$REQUIRE_SSL" == "False" ] || [ -z "$REQUIRE_SSL" ]; then
  echo -e "✅ SSL enforcement: ${RED}DISABLED${NC}"
  echo -e "${RED}⚠️  Unencrypted connections allowed${NC}"
else
  echo -e "❌ SSL enforcement: ${RED}VERIFICATION FAILED${NC}"
  exit 1
fi

echo ""

################################################################################
# Incident Report
################################################################################
echo -e "${YELLOW}━━━ Creating Incident Report ━━━${NC}"
echo ""

INCIDENT_REPORT="/tmp/ssl_rollback_incident_$(date +%Y%m%d_%H%M%S).txt"

cat > "$INCIDENT_REPORT" << EOF
SSL/TLS ENFORCEMENT ROLLBACK INCIDENT REPORT
============================================

Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')
Project: ${PROJECT_ID}
Instance: ${INSTANCE_NAME}

ROLLBACK REASON:
${ROLLBACK_REASON}

CURRENT STATUS:
- SSL Enforcement: DISABLED
- Unencrypted Connections: ALLOWED
- Security Risk: HIGH

REQUIRED ACTIONS:
1. Investigate and fix SSL issues within 24-48 hours
2. Test SSL connectivity in staging
3. Re-enable SSL enforcement using: ./enable_ssl_enforcement.sh
4. Notify security team
5. Document root cause and resolution

INVESTIGATION CHECKLIST:
[ ] Check Cloud SQL Connector version in all services
[ ] Verify cloud-sql-python-connector >= 1.5.0
[ ] Check service connection strings
[ ] Review Cloud Run logs for SSL errors
[ ] Test SSL connection manually
[ ] Verify server CA certificate
[ ] Check for network/firewall issues

TIMELINE:
- Rollback: $(date -u '+%Y-%m-%d %H:%M:%S UTC')
- Target Re-enable: [TO BE DETERMINED]
- Actual Re-enable: [TO BE FILLED]

NOTES:
[Add investigation notes here]

EOF

echo -e "Incident report created: ${GREEN}${INCIDENT_REPORT}${NC}"
echo ""

################################################################################
# Summary and Next Steps
################################################################################
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}📊 Rollback Summary${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "❌ SSL/TLS enforcement: ${RED}DISABLED${NC}"
echo -e "⚠️  Unencrypted connections: ${RED}ALLOWED${NC}"
echo -e "⚠️  Security risk: ${RED}HIGH${NC}"
echo ""
echo -e "${YELLOW}IMMEDIATE ACTIONS REQUIRED:${NC}"
echo ""
echo "1. Verify services can now connect:"
echo "   - Check Cloud Run health checks"
echo "   - Monitor application logs"
echo "   - Test critical workflows"
echo ""
echo "2. Investigate SSL issues:"
echo "   - Review incident report: ${INCIDENT_REPORT}"
echo "   - Check Cloud SQL Connector version"
echo "   - Review service connection strings"
echo "   - Test SSL connection manually"
echo ""
echo "3. Fix SSL issues and re-enable (within 24-48 hours):"
echo "   - Update Cloud SQL Connector if needed"
echo "   - Fix service configuration"
echo "   - Test in staging"
echo "   - Run: ./enable_ssl_enforcement.sh"
echo ""
echo "4. Notify stakeholders:"
echo "   - Security team"
echo "   - Operations team"
echo "   - Management (if critical incident)"
echo ""
echo -e "${RED}TEMPORARY SECURITY REGRESSION:${NC}"
echo "  - Database connections may be unencrypted"
echo "  - Data in transit is NOT protected"
echo "  - This violates compliance requirements (PCI-DSS, etc.)"
echo "  - Re-enable SSL enforcement ASAP"
echo ""
echo -e "${YELLOW}Investigation Commands:${NC}"
echo "# Check Cloud Run service logs"
echo "gcloud logging read \"resource.type=cloud_run_revision AND severity>=ERROR\" --limit=50"
echo ""
echo "# Test SSL connection manually"
echo "psql \"host=<DB_IP> user=postgres dbname=telepaydb sslmode=require\" -c \"SELECT version();\""
echo ""
echo "# Verify Cloud SQL Connector version"
echo "grep cloud-sql-python-connector */requirements.txt"
echo ""
echo -e "${YELLOW}Rollback logged to:${NC}"
echo "  - ${INCIDENT_REPORT}"
echo "  - /tmp/ssl_rollback_log.txt"
echo ""
echo -e "${RED}⚠️  ROLLBACK COMPLETE - FIX SSL ISSUES WITHIN 24-48 HOURS${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
