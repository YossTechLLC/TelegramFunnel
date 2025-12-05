#!/bin/bash
################################################################################
# Service Account Creation Script for PGP_v1 Security Implementation
# Purpose: Create dedicated service accounts for all 17 Cloud Run services
# Version: 1.0.0
# Date: 2025-01-18
# ⚠️  DO NOT RUN WITHOUT REVIEW - THIS CREATES GCP RESOURCES
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
echo -e "${BLUE}🔒 PGP_v1 Service Account Creation Script${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will create 17 service accounts in ${PROJECT_ID}!${NC}"
echo ""
echo "Configuration:"
echo "   Project ID: $PROJECT_ID"
echo ""

# Safety check
read -p "Are you sure you want to proceed? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Service account creation cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}Starting service account creation...${NC}"
echo ""

# Tracking
CREATED=0
FAILED=0
SKIPPED=0
declare -a FAILED_ACCOUNTS

################################################################################
# Helper Function: Create Service Account
################################################################################

create_service_account() {
    local SA_NAME=$1
    local DISPLAY_NAME=$2
    local DESCRIPTION=$3

    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────────────────${NC}"
    echo -e "${BLUE}📝 Creating: $SA_NAME${NC}"
    echo -e "${BLUE}────────────────────────────────────────────────────────────────────${NC}"

    # Check if service account already exists
    if gcloud iam service-accounts describe "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}⚠️  Service account already exists: $SA_NAME${NC}"
        ((SKIPPED++))
        return 0
    fi

    # Create service account
    if gcloud iam service-accounts create "$SA_NAME" \
        --display-name="$DISPLAY_NAME" \
        --description="$DESCRIPTION" \
        --project="$PROJECT_ID" \
        --quiet; then

        echo -e "${GREEN}✅ Created: $SA_NAME${NC}"
        echo "   Email: ${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
        ((CREATED++))
        return 0
    else
        echo -e "${RED}❌ Failed to create: $SA_NAME${NC}"
        FAILED_ACCOUNTS+=("$SA_NAME")
        ((FAILED++))
        return 1
    fi
}

################################################################################
# Service Account Definitions (17 Total)
################################################################################

echo ""
echo -e "${GREEN}Phase 1: Core Infrastructure Service Accounts${NC}"
echo "========================================="

# 1. PGP_SERVER_v1 - Main Telegram Bot Server
create_service_account \
    "pgp-server-v1-sa" \
    "PGP Server v1 Service Account" \
    "Service account for PGP_SERVER_v1 - Main Telegram bot server with webhook handlers"

# 2. PGP_WEB_v1 - Frontend Web Application
create_service_account \
    "pgp-web-v1-sa" \
    "PGP Web v1 Service Account" \
    "Service account for PGP_WEB_v1 - Frontend web application (React/Next.js)"

# 3. PGP_WEBAPI_v1 - Web API Backend
create_service_account \
    "pgp-webapi-v1-sa" \
    "PGP WebAPI v1 Service Account" \
    "Service account for PGP_WEBAPI_v1 - Web API backend for frontend communication"

echo ""
echo -e "${GREEN}Phase 2: Payment Processing Pipeline Service Accounts${NC}"
echo "========================================="

# 4. PGP_NP_IPN_v1 - NowPayments IPN Webhook Receiver
create_service_account \
    "pgp-np-ipn-v1-sa" \
    "PGP NowPayments IPN v1 Service Account" \
    "Service account for PGP_NP_IPN_v1 - NowPayments IPN webhook receiver (entry point for payment processing)"

# 5. PGP_ORCHESTRATOR_v1 - Payment Orchestrator
create_service_account \
    "pgp-orchestrator-v1-sa" \
    "PGP Orchestrator v1 Service Account" \
    "Service account for PGP_ORCHESTRATOR_v1 - Payment orchestration and routing service"

# 6. PGP_INVITE_v1 - Invite Handler
create_service_account \
    "pgp-invite-v1-sa" \
    "PGP Invite v1 Service Account" \
    "Service account for PGP_INVITE_v1 - Telegram channel invite link generation and management"

# 7. PGP_SPLIT1_v1 - Split Service Stage 1
create_service_account \
    "pgp-split1-v1-sa" \
    "PGP Split1 v1 Service Account" \
    "Service account for PGP_SPLIT1_v1 - Payment split calculation service (stage 1 of 3)"

# 8. PGP_SPLIT2_v1 - Split Service Stage 2
create_service_account \
    "pgp-split2-v1-sa" \
    "PGP Split2 v1 Service Account" \
    "Service account for PGP_SPLIT2_v1 - Payment split calculation service (stage 2 of 3)"

# 9. PGP_SPLIT3_v1 - Split Service Stage 3
create_service_account \
    "pgp-split3-v1-sa" \
    "PGP Split3 v1 Service Account" \
    "Service account for PGP_SPLIT3_v1 - Payment split calculation service (stage 3 of 3)"

echo ""
echo -e "${GREEN}Phase 3: Payout Services Service Accounts${NC}"
echo "========================================="

# 10. PGP_HOSTPAY1_v1 - HostPay Service Stage 1
create_service_account \
    "pgp-hostpay1-v1-sa" \
    "PGP HostPay1 v1 Service Account" \
    "Service account for PGP_HOSTPAY1_v1 - Host payout processing service (stage 1 of 3)"

# 11. PGP_HOSTPAY2_v1 - HostPay Service Stage 2
create_service_account \
    "pgp-hostpay2-v1-sa" \
    "PGP HostPay2 v1 Service Account" \
    "Service account for PGP_HOSTPAY2_v1 - Host payout processing service (stage 2 of 3)"

# 12. PGP_HOSTPAY3_v1 - HostPay Service Stage 3
create_service_account \
    "pgp-hostpay3-v1-sa" \
    "PGP HostPay3 v1 Service Account" \
    "Service account for PGP_HOSTPAY3_v1 - Host payout processing service (stage 3 of 3)"

echo ""
echo -e "${GREEN}Phase 4: Batch Processing Service Accounts${NC}"
echo "========================================="

# 13. PGP_ACCUMULATOR_v1 - Payout Accumulator
create_service_account \
    "pgp-accumulator-v1-sa" \
    "PGP Accumulator v1 Service Account" \
    "Service account for PGP_ACCUMULATOR_v1 - Payout accumulation and aggregation service"

# 14. PGP_BATCHPROCESSOR_v1 - Batch Processor
create_service_account \
    "pgp-batchprocessor-v1-sa" \
    "PGP BatchProcessor v1 Service Account" \
    "Service account for PGP_BATCHPROCESSOR_v1 - Batch payment processor for scheduled payouts"

# 15. PGP_MICROBATCHPROCESSOR_v1 - Micro Batch Processor
create_service_account \
    "pgp-microbatchprocessor-v1-sa" \
    "PGP MicroBatchProcessor v1 Service Account" \
    "Service account for PGP_MICROBATCHPROCESSOR_v1 - Micro-batch payment processor for real-time payouts"

echo ""
echo -e "${GREEN}Phase 5: Notification & Broadcast Service Accounts${NC}"
echo "========================================="

# 16. PGP_NOTIFICATIONS_v1 - Notification Service
create_service_account \
    "pgp-notifications-v1-sa" \
    "PGP Notifications v1 Service Account" \
    "Service account for PGP_NOTIFICATIONS_v1 - Payment notification and messaging service"

# 17. PGP_BROADCAST_v1 - Broadcast Scheduler
create_service_account \
    "pgp-broadcast-v1-sa" \
    "PGP Broadcast v1 Service Account" \
    "Service account for PGP_BROADCAST_v1 - Scheduled broadcast message service"

################################################################################
# Summary
################################################################################

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}📊 Service Account Creation Summary${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${GREEN}✅ Successfully created: $CREATED service accounts${NC}"
echo -e "${YELLOW}⚠️  Already existed (skipped): $SKIPPED service accounts${NC}"
echo -e "${RED}❌ Failed: $FAILED service accounts${NC}"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed service accounts:${NC}"
    for account in "${FAILED_ACCOUNTS[@]}"; do
        echo "   - $account"
    done
    echo ""
    echo -e "${YELLOW}⚠️  Some service accounts failed. Please review errors above.${NC}"
    exit 1
fi

################################################################################
# Verification
################################################################################

echo -e "${GREEN}Verification${NC}"
echo "========================================="
echo ""
echo "Listing all PGP service accounts:"
echo ""

gcloud iam service-accounts list \
    --project="$PROJECT_ID" \
    --filter="email:pgp-*-v1-sa@*" \
    --format="table(email,displayName)"

echo ""
echo -e "${GREEN}🎉 Service account creation complete!${NC}"
echo ""
echo -e "${YELLOW}⚠️  Next Steps:${NC}"
echo "   1. Run grant_iam_permissions.sh to grant Cloud SQL, Secret Manager permissions"
echo "   2. Run configure_invoker_permissions.sh to set up service-to-service auth"
echo "   3. Update deploy_all_pgp_services.sh to use these service accounts"
echo ""

################################################################################
# Save Service Account Metadata
################################################################################

OUTPUT_FILE="/tmp/pgp_service_accounts_$(date +%Y%m%d_%H%M%S).txt"
cat > "$OUTPUT_FILE" <<EOF
PGP_v1 Service Accounts Created
================================
Date: $(date)
Project: $PROJECT_ID
Created: $CREATED
Skipped: $SKIPPED
Failed: $FAILED

Service Account Emails:
$(gcloud iam service-accounts list \
    --project="$PROJECT_ID" \
    --filter="email:pgp-*-v1-sa@*" \
    --format="value(email)")
EOF

echo "Service account list saved to: $OUTPUT_FILE"
echo ""
