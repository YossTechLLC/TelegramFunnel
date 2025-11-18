#!/bin/bash
################################################################################
# IAM Permissions Granting Script for PGP_v1 Security Implementation
# Purpose: Grant minimal required IAM permissions to all service accounts
# Version: 1.0.0
# Date: 2025-01-18
# ⚠️  DO NOT RUN WITHOUT REVIEW - THIS MODIFIES GCP IAM POLICIES
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-pgp-live}"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🔒 PGP_v1 IAM Permissions Granting Script${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will grant IAM permissions to 17 service accounts!${NC}"
echo ""
echo "Configuration:"
echo "   Project ID: $PROJECT_ID"
echo ""
echo "Permissions to grant:"
echo "   - roles/cloudsql.client (Cloud SQL Client)"
echo "   - roles/secretmanager.secretAccessor (Secret Manager Secret Accessor)"
echo "   - roles/cloudtasks.enqueuer (Cloud Tasks Enqueuer)"
echo "   - roles/logging.logWriter (Cloud Logging Writer)"
echo ""

# Safety check
read -p "Are you sure you want to proceed? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}IAM permission granting cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}Starting IAM permission granting...${NC}"
echo ""

# Tracking
GRANTED=0
FAILED=0
declare -a FAILED_GRANTS

################################################################################
# Helper Function: Grant IAM Role
################################################################################

grant_iam_role() {
    local SA_NAME=$1
    local ROLE=$2
    local ROLE_DISPLAY=$3

    local SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

    echo -ne "   Granting ${ROLE_DISPLAY}... "

    if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$ROLE" \
        --condition=None \
        --quiet &>/dev/null; then

        echo -e "${GREEN}✅${NC}"
        ((GRANTED++))
        return 0
    else
        echo -e "${RED}❌${NC}"
        FAILED_GRANTS+=("${SA_NAME} - ${ROLE}")
        ((FAILED++))
        return 1
    fi
}

################################################################################
# Helper Function: Grant All Permissions to Service Account
################################################################################

grant_all_permissions() {
    local SA_NAME=$1
    local DISPLAY_NAME=$2
    local NEEDS_CLOUD_TASKS=${3:-false}

    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────────────────${NC}"
    echo -e "${BLUE}📝 Granting permissions: $DISPLAY_NAME${NC}"
    echo -e "${BLUE}────────────────────────────────────────────────────────────────────${NC}"

    # 1. Cloud SQL Client (all services need database access)
    grant_iam_role "$SA_NAME" "roles/cloudsql.client" "Cloud SQL Client"

    # 2. Secret Manager Secret Accessor (all services need secrets)
    grant_iam_role "$SA_NAME" "roles/secretmanager.secretAccessor" "Secret Manager Accessor"

    # 3. Cloud Tasks Enqueuer (only services that send tasks)
    if [ "$NEEDS_CLOUD_TASKS" = true ]; then
        grant_iam_role "$SA_NAME" "roles/cloudtasks.enqueuer" "Cloud Tasks Enqueuer"
    fi

    # 4. Cloud Logging Writer (all services need logging)
    grant_iam_role "$SA_NAME" "roles/logging.logWriter" "Cloud Logging Writer"
}

################################################################################
# Grant Permissions to All Service Accounts
################################################################################

echo ""
echo -e "${GREEN}Phase 1: Core Infrastructure Services${NC}"
echo "========================================="

# Services that send Cloud Tasks: true
# Services that only receive: false

grant_all_permissions \
    "pgp-server-v1-sa" \
    "PGP Server v1" \
    false  # Receives webhooks, doesn't send tasks

grant_all_permissions \
    "pgp-web-v1-sa" \
    "PGP Web v1" \
    false  # Frontend, no task sending

grant_all_permissions \
    "pgp-webapi-v1-sa" \
    "PGP WebAPI v1" \
    true  # API may send tasks

echo ""
echo -e "${GREEN}Phase 2: Payment Processing Pipeline${NC}"
echo "========================================="

grant_all_permissions \
    "pgp-np-ipn-v1-sa" \
    "PGP NowPayments IPN v1" \
    true  # Sends tasks to orchestrator

grant_all_permissions \
    "pgp-orchestrator-v1-sa" \
    "PGP Orchestrator v1" \
    true  # Orchestrates tasks to downstream services

grant_all_permissions \
    "pgp-invite-v1-sa" \
    "PGP Invite v1" \
    false  # Generates invite links, no task sending

grant_all_permissions \
    "pgp-split1-v1-sa" \
    "PGP Split1 v1" \
    true  # Sends to split2

grant_all_permissions \
    "pgp-split2-v1-sa" \
    "PGP Split2 v1" \
    true  # Sends to split3

grant_all_permissions \
    "pgp-split3-v1-sa" \
    "PGP Split3 v1" \
    true  # Final split stage, may send to hostpay

echo ""
echo -e "${GREEN}Phase 3: Payout Services${NC}"
echo "========================================="

grant_all_permissions \
    "pgp-hostpay1-v1-sa" \
    "PGP HostPay1 v1" \
    true  # Sends to hostpay2

grant_all_permissions \
    "pgp-hostpay2-v1-sa" \
    "PGP HostPay2 v1" \
    true  # Sends to hostpay3

grant_all_permissions \
    "pgp-hostpay3-v1-sa" \
    "PGP HostPay3 v1" \
    false  # Final stage, no downstream tasks

echo ""
echo -e "${GREEN}Phase 4: Batch Processing Services${NC}"
echo "========================================="

grant_all_permissions \
    "pgp-accumulator-v1-sa" \
    "PGP Accumulator v1" \
    true  # Sends tasks to batch processors

grant_all_permissions \
    "pgp-batchprocessor-v1-sa" \
    "PGP BatchProcessor v1" \
    true  # Sends tasks to micro batch

grant_all_permissions \
    "pgp-microbatchprocessor-v1-sa" \
    "PGP MicroBatchProcessor v1" \
    false  # Final processor, no downstream tasks

echo ""
echo -e "${GREEN}Phase 5: Notification & Broadcast Services${NC}"
echo "========================================="

grant_all_permissions \
    "pgp-notifications-v1-sa" \
    "PGP Notifications v1" \
    true  # Sends notification tasks to server

grant_all_permissions \
    "pgp-broadcast-v1-sa" \
    "PGP Broadcast v1" \
    true  # Sends broadcast tasks to server

################################################################################
# Summary
################################################################################

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}📊 IAM Permissions Granting Summary${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${GREEN}✅ Successfully granted: $GRANTED permissions${NC}"
echo -e "${RED}❌ Failed: $FAILED permissions${NC}"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed grants:${NC}"
    for grant in "${FAILED_GRANTS[@]}"; do
        echo "   - $grant"
    done
    echo ""
    echo -e "${YELLOW}⚠️  Some permissions failed. Please review errors above.${NC}"
    exit 1
fi

################################################################################
# Verification
################################################################################

echo -e "${GREEN}Verification${NC}"
echo "========================================="
echo ""
echo "Sample IAM policy check (pgp-server-v1-sa):"
echo ""

gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:pgp-server-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --format="table(bindings.role)" \
    2>/dev/null || echo "Unable to verify (may require additional permissions)"

echo ""
echo -e "${GREEN}🎉 IAM permissions granted successfully!${NC}"
echo ""
echo -e "${YELLOW}⚠️  Next Steps:${NC}"
echo "   1. Run configure_invoker_permissions.sh to set up service-to-service auth"
echo "   2. Verify permissions in Cloud Console IAM page"
echo "   3. Update deploy_all_pgp_services.sh to use these service accounts"
echo ""

################################################################################
# Save Permissions Metadata
################################################################################

OUTPUT_FILE="/tmp/pgp_iam_permissions_$(date +%Y%m%d_%H%M%S).txt"
cat > "$OUTPUT_FILE" <<EOF
PGP_v1 IAM Permissions Granted
===============================
Date: $(date)
Project: $PROJECT_ID
Total Granted: $GRANTED
Failed: $FAILED

Service Accounts:
$(gcloud iam service-accounts list \
    --project="$PROJECT_ID" \
    --filter="email:pgp-*-v1-sa@*" \
    --format="value(email)")

Roles Granted:
- roles/cloudsql.client (All service accounts)
- roles/secretmanager.secretAccessor (All service accounts)
- roles/cloudtasks.enqueuer (Services that send tasks)
- roles/logging.logWriter (All service accounts)
EOF

echo "IAM permissions log saved to: $OUTPUT_FILE"
echo ""
