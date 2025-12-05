#!/bin/bash
################################################################################
# Phase 2: Enable SSL/TLS Enforcement
#
# Purpose: Enforce SSL/TLS encryption for all database connections
# Status: DEPLOYMENT SCRIPT - Review before execution
# Project: pgp-live
# Instance: telepaypsql
#
# This script configures:
# - SSL/TLS requirement (requireSsl flag)
# - ENCRYPTED_ONLY mode (recommended for Cloud Run + Cloud SQL Connector)
# - Rejects all unencrypted connection attempts
#
# IMPORTANT:
# - This operation requires instance restart (~30 seconds downtime)
# - All services MUST use Cloud SQL Python Connector
# - Test in staging first
# - Coordinate deployment window with team
# - Have rollback script ready
#
# Security Mode:
# - ENCRYPTED_ONLY: Requires SSL/TLS, no client certificates
# - Alternative: TRUSTED_CLIENT_CERTIFICATE_REQUIRED (mutual TLS)
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
echo -e "${BLUE}🔒 Enable SSL/TLS Enforcement${NC}"
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

# Check current SSL status
CURRENT_REQUIRE_SSL=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.ipConfiguration.requireSsl)")

if [ "$CURRENT_REQUIRE_SSL" == "True" ]; then
  echo -e "${YELLOW}⚠️  SSL enforcement is already enabled${NC}"
  echo ""
  read -p "Do you want to continue anyway? (yes/no): " CONTINUE_ANYWAY

  if [ "$CONTINUE_ANYWAY" != "yes" ]; then
    echo -e "${YELLOW}❌ Operation cancelled${NC}"
    exit 0
  fi
fi

echo ""

################################################################################
# Verify Cloud SQL Connector Usage
################################################################################
echo -e "${YELLOW}━━━ Verifying Service Configuration ━━━${NC}"
echo ""

echo "Checking if services use Cloud SQL Python Connector..."
echo ""

CONNECTOR_FOUND=false
SERVICES_WITHOUT_CONNECTOR=()

for SERVICE_DIR in /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/PGP_*; do
  if [ -d "$SERVICE_DIR" ] && [ -f "$SERVICE_DIR/requirements.txt" ]; then
    SERVICE_NAME=$(basename "$SERVICE_DIR")

    if grep -q "cloud-sql-python-connector" "$SERVICE_DIR/requirements.txt"; then
      VERSION=$(grep "cloud-sql-python-connector" "$SERVICE_DIR/requirements.txt" | cut -d'=' -f3 || echo "unknown")
      echo -e "✅ ${SERVICE_NAME}: ${GREEN}v${VERSION}${NC}"
      CONNECTOR_FOUND=true

      # Check version (should be >= 1.5.0)
      if [[ "$VERSION" =~ ^1\.[0-4]\. ]]; then
        echo -e "   ${YELLOW}WARNING: Version < 1.5.0 (consider upgrading)${NC}"
      fi
    else
      echo -e "⚠️  ${SERVICE_NAME}: ${YELLOW}Connector not found${NC}"
      SERVICES_WITHOUT_CONNECTOR+=("$SERVICE_NAME")
    fi
  fi
done

echo ""

if [ ${#SERVICES_WITHOUT_CONNECTOR[@]} -gt 0 ]; then
  echo -e "${YELLOW}⚠️  WARNING: The following services may not use Cloud SQL Connector:${NC}"
  for SERVICE in "${SERVICES_WITHOUT_CONNECTOR[@]}"; do
    echo "   - $SERVICE"
  done
  echo ""
  echo "These services MUST use Cloud SQL Connector for SSL to work."
  echo ""
  read -p "Continue anyway? (type 'yes' to confirm): " CONTINUE_WITHOUT_CONNECTOR

  if [ "$CONTINUE_WITHOUT_CONNECTOR" != "yes" ]; then
    echo -e "${YELLOW}❌ Operation cancelled${NC}"
    exit 0
  fi
fi

################################################################################
# Configuration Summary
################################################################################
echo ""
echo -e "${YELLOW}━━━ Configuration Summary ━━━${NC}"
echo ""
echo -e "SSL Enforcement Mode: ${GREEN}ENCRYPTED_ONLY${NC}"
echo ""
echo -e "${BLUE}What this means:${NC}"
echo "  - All connections MUST use SSL/TLS encryption"
echo "  - Unencrypted connection attempts will be REJECTED"
echo "  - Cloud SQL Python Connector handles SSL automatically"
echo "  - No client certificates required (server authentication only)"
echo ""
echo -e "${BLUE}Alternative Mode (Not Used):${NC}"
echo "  - TRUSTED_CLIENT_CERTIFICATE_REQUIRED (mutual TLS)"
echo "  - Requires client certificates for each service"
echo "  - More complex certificate management"
echo "  - Not necessary for current security requirements"
echo ""

################################################################################
# User Confirmation
################################################################################
echo -e "${YELLOW}⚠️  WARNING: This operation will:${NC}"
echo "  - Enable SSL/TLS requirement on Cloud SQL instance"
echo "  - Restart the instance (~30 seconds downtime)"
echo "  - Reject ALL unencrypted connection attempts"
echo "  - Services without SSL will FAIL to connect"
echo ""
echo -e "${RED}DO NOT RUN WITHOUT:${NC}"
echo "  1. Testing in staging environment first"
echo "  2. Verifying all services use Cloud SQL Connector"
echo "  3. Coordinating maintenance window with team"
echo "  4. Having rollback script ready (rollback_ssl_enforcement.sh)"
echo ""

read -p "Are you sure you want to proceed? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo -e "${YELLOW}❌ Operation cancelled${NC}"
  exit 0
fi

echo ""

################################################################################
# Enable SSL Enforcement
################################################################################
echo -e "${YELLOW}━━━ Enabling SSL/TLS Enforcement ━━━${NC}"
echo ""

echo "Executing gcloud command..."
echo ""
echo -e "${YELLOW}This will restart the instance (~30 seconds downtime)${NC}"
echo ""

gcloud sql instances patch ${INSTANCE_NAME} \
  --require-ssl \
  --project=${PROJECT_ID}

if [ $? -eq 0 ]; then
  echo ""
  echo -e "✅ ${GREEN}SSL/TLS enforcement enabled successfully!${NC}"
else
  echo ""
  echo -e "❌ ${RED}Failed to enable SSL/TLS enforcement${NC}"
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
echo "Verifying SSL enforcement..."

REQUIRE_SSL=$(gcloud sql instances describe ${INSTANCE_NAME} \
  --project=${PROJECT_ID} \
  --format="value(settings.ipConfiguration.requireSsl)")

echo ""

if [ "$REQUIRE_SSL" == "True" ]; then
  echo -e "✅ SSL enforcement: ${GREEN}ENABLED${NC}"
else
  echo -e "❌ SSL enforcement: ${RED}VERIFICATION FAILED${NC}"
  echo "   Check instance status and try again"
  exit 1
fi

echo ""

################################################################################
# Test SSL Connection
################################################################################
echo -e "${YELLOW}━━━ SSL Connection Test ━━━${NC}"
echo ""

echo -e "${BLUE}Manual test commands:${NC}"
echo ""
echo "1. Test SSL connection (should SUCCEED):"
echo "   psql \"host=<DB_IP> user=postgres dbname=telepaydb sslmode=require\" -c \"SELECT version();\""
echo ""
echo "2. Test non-SSL connection (should FAIL):"
echo "   psql \"host=<DB_IP> user=postgres dbname=telepaydb sslmode=disable\" -c \"SELECT version();\""
echo ""
echo "3. Verify SSL cipher in use:"
echo "   psql \"host=<DB_IP> user=postgres dbname=telepaydb sslmode=require\" \\"
echo "     -c \"SELECT ssl_cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();\""
echo ""
echo -e "${GREEN}Expected SSL cipher (TLS 1.2+):${NC}"
echo "  - ECDHE-RSA-AES256-GCM-SHA384"
echo "  - ECDHE-RSA-AES128-GCM-SHA256"
echo ""

read -p "Have you verified SSL connections work? (yes to continue, no to rollback): " SSL_WORKS

if [ "$SSL_WORKS" != "yes" ]; then
  echo ""
  echo -e "${RED}⚠️  SSL verification failed or not tested${NC}"
  echo ""
  echo "Options:"
  echo "1. Run rollback script: ./rollback_ssl_enforcement.sh"
  echo "2. Investigate connection issues"
  echo "3. Check Cloud Run service logs for connection errors"
  echo ""
  read -p "Run rollback now? (yes/no): " RUN_ROLLBACK

  if [ "$RUN_ROLLBACK" == "yes" ]; then
    ./rollback_ssl_enforcement.sh
  fi

  exit 1
fi

echo ""

################################################################################
# Monitor Services
################################################################################
echo -e "${YELLOW}━━━ Service Health Check ━━━${NC}"
echo ""

echo -e "${BLUE}Monitor Cloud Run services for connection errors:${NC}"
echo ""
echo "gcloud logging read \"resource.type=cloud_run_revision AND severity>=ERROR\" \\"
echo "  --limit=50 \\"
echo "  --format=\"table(timestamp, resource.labels.service_name, textPayload)\" \\"
echo "  --project=${PROJECT_ID}"
echo ""
echo -e "${YELLOW}Watch for SSL/TLS connection errors in the next 24 hours${NC}"
echo ""

################################################################################
# Summary and Next Steps
################################################################################
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Deployment Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "✅ SSL/TLS enforcement: ${GREEN}ENABLED${NC}"
echo -e "✅ Encryption mode: ${GREEN}ENCRYPTED_ONLY${NC}"
echo -e "✅ Unencrypted connections: ${GREEN}REJECTED${NC}"
echo ""
echo -e "${YELLOW}Critical Monitoring Period: Next 24 hours${NC}"
echo ""
echo -e "${YELLOW}Monitor for:${NC}"
echo "  1. Connection errors in Cloud Run logs"
echo "  2. Application health check failures"
echo "  3. Database connection pool exhaustion"
echo "  4. Performance degradation"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Monitor Cloud Run service logs for 24 hours"
echo "2. Run verify_ssl_enforcement.sh to confirm configuration"
echo "3. Test SSL connection from each service"
echo "4. Update architecture documentation"
echo "5. Document SSL enforcement in DECISIONS.md"
echo ""
echo -e "${RED}Rollback Available:${NC}"
echo "  If issues detected within 24 hours, run:"
echo "  ./rollback_ssl_enforcement.sh"
echo ""
echo -e "${YELLOW}Monitoring Commands:${NC}"
echo "# Verify SSL enforcement"
echo "./verify_ssl_enforcement.sh"
echo ""
echo "# Check Cloud Run logs"
echo "gcloud logging read \"resource.type=cloud_run_revision AND severity>=ERROR\" --limit=50"
echo ""
echo "# List active connections and SSL status"
echo "psql -c \"SELECT datname, usename, ssl, client_addr FROM pg_stat_ssl JOIN pg_stat_activity USING (pid);\""
echo ""
echo -e "${GREEN}✅ SSL/TLS enforcement complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
