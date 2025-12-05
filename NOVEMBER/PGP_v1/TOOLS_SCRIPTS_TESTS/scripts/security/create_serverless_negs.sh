#!/bin/bash

################################################################################
# Create Serverless Network Endpoint Groups (NEGs) for PGP_v1 Services
################################################################################
#
# Purpose: Create Serverless NEGs for external-facing Cloud Run services
#          to enable Cloud Load Balancer integration
#
# Services Configured:
#   1. pgp-web-v1          - Frontend (public access)
#   2. pgp-np-ipn-v1       - NowPayments IPN webhook
#   3. pgp-server-v1       - Telegram Bot webhook
#
# Architecture:
#   - Serverless NEGs connect Cloud Load Balancer to Cloud Run services
#   - Each NEG represents a Cloud Run service in a specific region
#   - NEGs are referenced by backend services in the Load Balancer
#
# Prerequisites:
#   - Cloud Run services must be deployed
#   - gcloud CLI authenticated with sufficient permissions
#   - Compute Engine API enabled
#
# Permissions Required:
#   - compute.networkEndpointGroups.create
#   - compute.networkEndpointGroups.get
#
# Usage:
#   bash create_serverless_negs.sh
#
# Created: 2025-01-18
# Phase: 2 - Network Security (Load Balancer & Cloud Armor)
#
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="pgp-live"
REGION="us-central1"

# Counters
CREATED=0
SKIPPED=0
FAILED=0

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${YELLOW}───────────────────────────────────────────────────────────────${NC}"
    echo -e "${YELLOW}  $1${NC}"
    echo -e "${YELLOW}───────────────────────────────────────────────────────────────${NC}"
}

################################################################################
# Serverless NEG Creation Function
################################################################################

create_serverless_neg() {
    local NEG_NAME=$1
    local SERVICE_NAME=$2
    local DESCRIPTION=$3

    echo ""
    echo -e "${BLUE}Creating Serverless NEG: ${NEG_NAME}${NC}"
    echo "  Service: $SERVICE_NAME"
    echo "  Region: $REGION"
    echo "  Description: $DESCRIPTION"

    # Check if NEG already exists
    if gcloud compute network-endpoint-groups describe "$NEG_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}⚠️  Serverless NEG already exists: $NEG_NAME${NC}"
        ((SKIPPED++))
        return 0
    fi

    # Create serverless NEG
    if gcloud compute network-endpoint-groups create "$NEG_NAME" \
        --region="$REGION" \
        --network-endpoint-type=serverless \
        --cloud-run-service="$SERVICE_NAME" \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}✅ Created: $NEG_NAME${NC}"
        ((CREATED++))
        return 0
    else
        echo -e "${RED}❌ Failed to create: $NEG_NAME${NC}"
        ((FAILED++))
        return 1
    fi
}

################################################################################
# Verification Function
################################################################################

verify_serverless_neg() {
    local NEG_NAME=$1

    echo -n "  Verifying NEG: $NEG_NAME... "

    if gcloud compute network-endpoint-groups describe "$NEG_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(name)" &>/dev/null; then
        echo -e "${GREEN}✅ Exists${NC}"
        return 0
    else
        echo -e "${RED}❌ Not found${NC}"
        return 1
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    print_header "🌐 Serverless NEG Creation - PGP_v1 Phase 2"

    echo "This script will create Serverless Network Endpoint Groups (NEGs)"
    echo "for external-facing Cloud Run services to enable Load Balancer integration."
    echo ""
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo ""
    echo "Services to configure:"
    echo "  1. pgp-web-v1 (Frontend - Public)"
    echo "  2. pgp-np-ipn-v1 (NowPayments Webhook)"
    echo "  3. pgp-server-v1 (Telegram Webhook)"
    echo ""

    # Safety prompt
    read -p "Do you want to proceed? (yes/no): " CONFIRM
    if [[ "$CONFIRM" != "yes" ]]; then
        echo -e "${YELLOW}⚠️  Operation cancelled by user${NC}"
        exit 0
    fi

    # Verify gcloud authentication
    print_section "🔐 Verifying Authentication"

    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    CURRENT_ACCOUNT=$(gcloud config get-value account 2>/dev/null)

    echo "Current account: $CURRENT_ACCOUNT"
    echo "Current project: $CURRENT_PROJECT"

    if [[ "$CURRENT_PROJECT" != "$PROJECT_ID" ]]; then
        echo -e "${YELLOW}⚠️  Warning: Current project ($CURRENT_PROJECT) does not match target project ($PROJECT_ID)${NC}"
        read -p "Do you want to continue anyway? (yes/no): " PROCEED
        if [[ "$PROCEED" != "yes" ]]; then
            echo -e "${YELLOW}⚠️  Operation cancelled${NC}"
            exit 0
        fi
    fi

    # Verify Cloud Run services exist
    print_section "🔍 Verifying Cloud Run Services"

    SERVICES=("pgp-web-v1" "pgp-np-ipn-v1" "pgp-server-v1")
    ALL_EXIST=true

    for SERVICE in "${SERVICES[@]}"; do
        echo -n "  Checking $SERVICE... "
        if gcloud run services describe "$SERVICE" \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --format="value(status.url)" &>/dev/null; then
            echo -e "${GREEN}✅ Exists${NC}"
        else
            echo -e "${RED}❌ Not found${NC}"
            ALL_EXIST=false
        fi
    done

    if [[ "$ALL_EXIST" != "true" ]]; then
        echo ""
        echo -e "${RED}❌ Error: One or more Cloud Run services not found${NC}"
        echo "Please deploy Cloud Run services first using deploy_all_pgp_services.sh"
        exit 1
    fi

    # Create Serverless NEGs
    print_section "🌐 Creating Serverless NEGs"

    # 1. Frontend (Public)
    create_serverless_neg \
        "pgp-web-v1-neg" \
        "pgp-web-v1" \
        "Serverless NEG for PGP Frontend Web Application"

    # 2. NowPayments IPN Webhook
    create_serverless_neg \
        "pgp-np-ipn-v1-neg" \
        "pgp-np-ipn-v1" \
        "Serverless NEG for NowPayments IPN Webhook Handler"

    # 3. Telegram Bot Webhook
    create_serverless_neg \
        "pgp-server-v1-neg" \
        "pgp-server-v1" \
        "Serverless NEG for Telegram Bot Webhook Handler"

    # Verification
    print_section "✅ Verification"

    echo "Verifying all Serverless NEGs were created successfully:"
    verify_serverless_neg "pgp-web-v1-neg"
    verify_serverless_neg "pgp-np-ipn-v1-neg"
    verify_serverless_neg "pgp-server-v1-neg"

    # Summary
    print_section "📊 Summary"

    echo "Serverless NEGs Created: $CREATED"
    echo "Serverless NEGs Skipped (already exist): $SKIPPED"
    echo "Serverless NEGs Failed: $FAILED"
    echo ""

    if [[ $FAILED -eq 0 ]]; then
        echo -e "${GREEN}✅ All Serverless NEGs configured successfully!${NC}"
        echo ""
        echo "Next Steps:"
        echo "  1. Run provision_ssl_certificates.sh to create SSL certificates"
        echo "  2. Run create_cloud_armor_policy.sh to create security policies"
        echo "  3. Run deploy_load_balancer.sh to create Load Balancer"
    else
        echo -e "${RED}❌ Some Serverless NEGs failed to create${NC}"
        echo "Please review the errors above and try again."
        exit 1
    fi

    # List created NEGs
    print_section "📋 Created Serverless NEGs"

    gcloud compute network-endpoint-groups list \
        --filter="networkEndpointType=SERVERLESS AND region=$REGION" \
        --project="$PROJECT_ID" \
        --format="table(name,region,cloudRun.service,size)" || true

    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ Serverless NEG creation complete!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Run main function
main

################################################################################
# Rollback Instructions
################################################################################
#
# To delete Serverless NEGs:
#
# gcloud compute network-endpoint-groups delete pgp-web-v1-neg \
#   --region=us-central1 --project=pgp-live --quiet
#
# gcloud compute network-endpoint-groups delete pgp-np-ipn-v1-neg \
#   --region=us-central1 --project=pgp-live --quiet
#
# gcloud compute network-endpoint-groups delete pgp-server-v1-neg \
#   --region=us-central1 --project=pgp-live --quiet
#
################################################################################

################################################################################
# Additional Notes
################################################################################
#
# Serverless NEG Configuration:
# - Network Endpoint Type: SERVERLESS (for Cloud Run)
# - Region: us-central1 (must match Cloud Run service region)
# - Cloud Run Service: Bound to specific Cloud Run service
#
# Cost:
# - Serverless NEGs: FREE (no separate charge)
# - Load Balancer forwarding rules: $18/month per rule (charged separately)
#
# Architecture:
# - Each NEG represents a Cloud Run service in the Load Balancer backend
# - NEGs are regional (not global)
# - NEGs automatically update when Cloud Run service scales
#
# Security:
# - NEGs do not provide security (use Cloud Armor for security)
# - NEGs are a connectivity layer between Load Balancer and Cloud Run
#
# Limitations:
# - Serverless NEGs only support Cloud Run (not Cloud Functions or App Engine)
# - NEGs must be in same region as Cloud Run service
# - One NEG per Cloud Run service
#
################################################################################
