#!/bin/bash
################################################################################
# grant_pgp_live_secret_access.sh
#
# Grant Secret Manager Access to Service Accounts
# Adds IAM policy bindings for all 69 secrets to specified service account(s)
#
# This script grants 'roles/secretmanager.secretAccessor' permission
# which allows services to read secret values at runtime.
#
# ⚠️  UPDATED for PGP_v1 (69 secrets, no deprecated secrets)
#
# Usage:
#   ./grant_pgp_live_secret_access.sh [SERVICE_ACCOUNT_EMAIL]
#
# If no service account is provided, script will prompt for it.
#
# Author: PGP_v1 Migration Team
# Date: 2025-11-18
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
PROJECT="pgp-live"
ROLE="roles/secretmanager.secretAccessor"

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
echo "  Grant Secret Manager Access"
echo "  Project: $PROJECT"
echo "  Role: $ROLE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Set active project
gcloud config set project "$PROJECT"

# Get service account email
if [[ -n "${1:-}" ]]; then
    SERVICE_ACCOUNT="$1"
else
    echo ""
    log_info "Available service accounts in project:"
    gcloud iam service-accounts list --project="$PROJECT" --format='table(email,displayName)'
    echo ""
    read -p "Enter service account email: " SERVICE_ACCOUNT
fi

# Validate service account format
if [[ ! "$SERVICE_ACCOUNT" =~ ^.+@.+\.iam\.gserviceaccount\.com$ ]]; then
    log_error "Invalid service account format (should end with .iam.gserviceaccount.com)"
    exit 1
fi

# Verify service account exists
log_info "Verifying service account: $SERVICE_ACCOUNT"
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT" --project="$PROJECT" &>/dev/null; then
    log_error "Service account not found: $SERVICE_ACCOUNT"
    exit 1
fi
log_success "Service account verified"

echo ""
log_info "Fetching all secrets in project..."
SECRETS=$(gcloud secrets list --project="$PROJECT" --format='value(name)')

if [[ -z "$SECRETS" ]]; then
    log_error "No secrets found in project $PROJECT"
    log_error "Run secret creation scripts first (Phase 1-6)"
    exit 1
fi

SECRET_COUNT=$(echo "$SECRETS" | wc -l)
log_success "Found $SECRET_COUNT secrets"

echo ""
log_warning "This will grant secretAccessor role to $SECRET_COUNT secrets"
echo "  Service Account: $SERVICE_ACCOUNT"
echo "  Role: $ROLE"
echo ""
read -p "Continue? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    log_info "Aborted by user"
    exit 0
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  Granting Access to All Secrets"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

GRANTED_COUNT=0
SKIPPED_COUNT=0
ERROR_COUNT=0

echo "$SECRETS" | while read -r SECRET_NAME; do
    printf "  Processing: %-40s " "$SECRET_NAME"

    # Check if binding already exists
    EXISTING_MEMBERS=$(gcloud secrets get-iam-policy "$SECRET_NAME" \
        --project="$PROJECT" \
        --format='json' 2>/dev/null | \
        jq -r ".bindings[]? | select(.role==\"$ROLE\") | .members[]?" 2>/dev/null || true)

    if echo "$EXISTING_MEMBERS" | grep -q "serviceAccount:$SERVICE_ACCOUNT"; then
        echo -e "${YELLOW}[SKIP]${NC}"
        ((SKIPPED_COUNT++))
        continue
    fi

    # Grant access
    if gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="$ROLE" \
        --project="$PROJECT" &>/dev/null; then
        echo -e "${GREEN}[OK]${NC}"
        ((GRANTED_COUNT++))
    else
        echo -e "${RED}[FAIL]${NC}"
        ((ERROR_COUNT++))
    fi
done

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  IAM Policy Binding - COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Summary
log_info "Grant Summary:"
echo "  ✅ Granted: $GRANTED_COUNT secrets"
echo "  ⏭️  Skipped: $SKIPPED_COUNT secrets (already had access)"
echo "  ❌ Errors: $ERROR_COUNT secrets"
echo "  📊 Total: $SECRET_COUNT secrets"
echo ""

log_success "Service account can now access secrets:"
echo "  Service Account: $SERVICE_ACCOUNT"
echo "  Role: $ROLE"
echo "  Secrets: $SECRET_COUNT"
echo ""

log_info "Verify access:"
echo "  gcloud secrets get-iam-policy <SECRET_NAME> --project=$PROJECT"
echo ""

log_info "Next steps:"
echo "  1. Deploy PGP_v1 services with this service account"
echo "  2. Test secret access from Cloud Run"
echo "  3. Verify hot-reload functionality"
echo ""

if [[ $ERROR_COUNT -gt 0 ]]; then
    log_warning "Some secrets had errors - check IAM permissions"
    exit 1
fi

log_success "All IAM bindings created successfully! 🎉"
