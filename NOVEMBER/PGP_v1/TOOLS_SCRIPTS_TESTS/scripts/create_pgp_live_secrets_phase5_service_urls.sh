#!/bin/bash
################################################################################
# create_pgp_live_secrets_phase5_service_urls.sh
#
# Phase 5: Service URL Secrets (14 secrets)
# Creates Cloud Run service URL secrets after services are deployed
#
# ⚠️  PREREQUISITE: All Cloud Run services MUST be deployed first!
#
# This script automatically discovers deployed Cloud Run service URLs
# and creates Secret Manager entries for each service.
#
# All secrets in this phase are HOT-RELOADABLE (zero-downtime URL updates)
#
# Usage:
#   ./create_pgp_live_secrets_phase5_service_urls.sh
#
# Author: PGP_v1 Migration Team
# Date: 2025-11-18
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
PROJECT="pgp-live"
REGION="us-central1"

# Service name mappings (Cloud Run service name → Secret name)
declare -A SERVICE_MAP=(
    ["pgp-server-v1"]="PGP_SERVER_URL"
    ["pgp-webapi-v1"]="PGP_WEBAPI_URL"
    ["pgp-np-ipn-v1"]="PGP_NP_IPN_URL"
    ["pgp-orchestrator-v1"]="PGP_ORCHESTRATOR_URL"
    ["pgp-invite-v1"]="PGP_INVITE_URL"
    ["pgp-notifications-v1"]="PGP_NOTIFICATIONS_URL"
    ["pgp-batchprocessor-v1"]="PGP_BATCHPROCESSOR_URL"
    ["pgp-microbatchprocessor-v1"]="PGP_MICROBATCH_URL"
    ["pgp-split1-v1"]="PGP_SPLIT1_URL"
    ["pgp-split2-v1"]="PGP_SPLIT2_URL"
    ["pgp-split3-v1"]="PGP_SPLIT3_URL"
    ["pgp-hostpay1-v1"]="PGP_HOSTPAY1_URL"
    ["pgp-hostpay2-v1"]="PGP_HOSTPAY2_URL"
    ["pgp-hostpay3-v1"]="PGP_HOSTPAY3_URL"
)

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Header
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Phase 5: Service URL Secrets Creation"
echo "  Project: $PROJECT"
echo "  Region: $REGION"
echo "  Secrets: 14 (All HOT-RELOADABLE)"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Set active project
gcloud config set project "$PROJECT"

# Verify Cloud Run services are deployed
log_info "Verifying Cloud Run service deployments..."
DEPLOYED_SERVICES=$(gcloud run services list --platform=managed --region="$REGION" --project="$PROJECT" --format='value(SERVICE)' 2>/dev/null || true)

if [[ -z "$DEPLOYED_SERVICES" ]]; then
    log_error "No Cloud Run services found in region $REGION"
    log_error "Please deploy all PGP_v1 services before running this script"
    exit 1
fi

echo ""
log_success "Found deployed services:"
echo "$DEPLOYED_SERVICES" | while read -r svc; do
    echo "  • $svc"
done
echo ""

# Count found vs expected
EXPECTED_COUNT=14
FOUND_COUNT=$(echo "$DEPLOYED_SERVICES" | wc -l)
log_info "Expected $EXPECTED_COUNT services, found $FOUND_COUNT deployed"

if [[ $FOUND_COUNT -lt $EXPECTED_COUNT ]]; then
    log_warning "Some services may be missing - continuing anyway"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  Creating Service URL Secrets"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

CREATED_COUNT=0
SKIPPED_COUNT=0
MISSING_COUNT=0

for SERVICE_NAME in "${!SERVICE_MAP[@]}"; do
    SECRET_NAME="${SERVICE_MAP[$SERVICE_NAME]}"

    log_info "Processing: $SERVICE_NAME → $SECRET_NAME"

    # Check if secret already exists
    if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" &>/dev/null; then
        log_warning "  Secret '$SECRET_NAME' already exists, skipping"
        ((SKIPPED_COUNT++))
        continue
    fi

    # Get service URL from Cloud Run
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --platform=managed \
        --region="$REGION" \
        --project="$PROJECT" \
        --format='value(status.url)' 2>/dev/null || true)

    if [[ -z "$SERVICE_URL" ]]; then
        log_error "  Service '$SERVICE_NAME' not found or not deployed"
        log_warning "  Skipping $SECRET_NAME - deploy service first"
        ((MISSING_COUNT++))
        continue
    fi

    # Create secret
    echo -n "$SERVICE_URL" | gcloud secrets create "$SECRET_NAME" \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"

    log_success "  Created: $SECRET_NAME = $SERVICE_URL"
    ((CREATED_COUNT++))
done

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Phase 5: Service URL Secrets - COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Summary
log_info "Deployment Summary:"
echo "  ✅ Created: $CREATED_COUNT secrets"
echo "  ⏭️  Skipped: $SKIPPED_COUNT secrets (already exist)"
echo "  ❌ Missing: $MISSING_COUNT secrets (services not deployed)"
echo ""

if [[ $MISSING_COUNT -gt 0 ]]; then
    log_warning "Some services were not found - ensure all services are deployed"
    echo ""
    log_info "Missing services can be created individually:"
    echo "  gcloud run services describe <SERVICE_NAME> --region=$REGION --project=$PROJECT --format='value(status.url)' | \\"
    echo "  gcloud secrets create <SECRET_NAME> --data-file=- --project=$PROJECT"
fi

echo ""
log_info "All Phase 5 secrets are HOT-RELOADABLE"
log_info "URL changes (blue/green deployments) can be rotated without service restart"
echo ""

# Special note for PGP_NP_IPN_URL (needs to be registered with NOWPayments)
if gcloud secrets describe PGP_NP_IPN_URL --project="$PROJECT" &>/dev/null; then
    IPN_URL=$(gcloud secrets versions access latest --secret=PGP_NP_IPN_URL --project="$PROJECT")
    echo ""
    log_warning "IMPORTANT: Register IPN webhook URL with NOWPayments"
    echo "  1. Login to NOWPayments dashboard: https://account.nowpayments.io/"
    echo "  2. Go to: Settings → IPN Callbacks"
    echo "  3. Add callback URL: ${IPN_URL}/webhook"
    echo ""
fi

log_info "Next steps:"
echo "  1. Verify all secrets: ./verify_pgp_live_secrets.sh"
echo "  2. Deploy Cloud Tasks queues"
echo "  3. Run Phase 6: ./create_pgp_live_secrets_phase6_queue_names.sh"
echo "  4. Grant IAM access: ./grant_pgp_live_secret_access.sh"
echo ""

# List all created secrets
log_info "Listing all service URL secrets..."
gcloud secrets list --project="$PROJECT" --filter="name~'PGP_.*_URL' OR name~'MICROBATCH_URL'"

echo ""
if [[ $MISSING_COUNT -eq 0 ]]; then
    log_success "Phase 5 deployment completed successfully! 🎉"
else
    log_warning "Phase 5 completed with $MISSING_COUNT missing services ⚠️"
fi
