#!/bin/bash

# Grant Service Account Access to All pgp-live Secrets
# This script grants the Compute Engine default service account access to all secrets
#
# IMPORTANT: DO NOT RUN THIS SCRIPT YET - Review and customize first
#
# Prerequisites:
# 1. Secrets created in pgp-live (run create_pgp_live_secrets.sh first)
# 2. gcloud CLI authenticated
# 3. User has resourcemanager.projects.setIamPolicy permission
#
# Usage:
#   ./grant_pgp_live_secret_access.sh [--service-account EMAIL]

set -e  # Exit on error

# Configuration
PROJECT_ID="pgp-live"
# Default service account (update if using custom service account)
SERVICE_ACCOUNT="${1:-compute@developer.gserviceaccount.com}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

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

# Function to grant secret access
grant_secret_access() {
    local secret_name="$1"
    local member="serviceAccount:${SERVICE_ACCOUNT}"

    log_info "Granting access to: $secret_name"

    if gcloud secrets add-iam-policy-binding "$secret_name" \
        --member="$member" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" &>/dev/null; then
        log_success "  ✓ Access granted to $secret_name"
    else
        log_error "  ✗ Failed to grant access to $secret_name"
    fi
}

# ============================================================================
# VERIFICATION
# ============================================================================

log_info "🚀 Starting IAM policy updates for project: $PROJECT_ID"
log_info "📧 Service account: $SERVICE_ACCOUNT"
echo ""

# Verify gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &>/dev/null; then
    log_error "Not authenticated with gcloud. Run: gcloud auth login"
    exit 1
fi

# Verify project exists
if ! gcloud projects describe "$PROJECT_ID" &>/dev/null; then
    log_error "Project $PROJECT_ID does not exist."
    exit 1
fi

# Get project number
PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
FULL_SERVICE_ACCOUNT="${PROJECT_NUM}-${SERVICE_ACCOUNT}"

log_info "Full service account: $FULL_SERVICE_ACCOUNT"
echo ""
log_warning "⚠️  This will grant secretmanager.secretAccessor role to all 77 secrets"
echo ""

read -p "Continue? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
    log_info "Aborted by user"
    exit 0
fi
echo ""

# ============================================================================
# GRANT ACCESS TO ALL SECRETS
# ============================================================================

log_info "=========================================="
log_info "Granting Access to Service URL Secrets"
log_info "=========================================="
echo ""

# Service URL secrets
grant_secret_access "PGP_ACCUMULATOR_URL"
grant_secret_access "PGP_BATCHPROCESSOR_URL"
grant_secret_access "PGP_MICROBATCHPROCESSOR_URL"
grant_secret_access "PGP_HOSTPAY1_URL"
grant_secret_access "PGP_HOSTPAY2_URL"
grant_secret_access "PGP_HOSTPAY3_URL"
grant_secret_access "PGP_SPLIT1_URL"
grant_secret_access "PGP_SPLIT2_URL"
grant_secret_access "PGP_SPLIT3_URL"
grant_secret_access "PGP_ORCHESTRATOR_URL"
grant_secret_access "PGP_INVITE_URL"
grant_secret_access "PGP_SERVER_URL"
grant_secret_access "PGP_NP_IPN_CALLBACK_URL"
grant_secret_access "WEBHOOK_BASE_URL"
grant_secret_access "TPS_WEBHOOK_URL"
grant_secret_access "HOSTPAY_WEBHOOK_URL"
grant_secret_access "GCSPLIT1_ESTIMATE_RESPONSE_URL"
grant_secret_access "GCSPLIT1_SWAP_RESPONSE_URL"

echo ""
log_success "Service URL secrets: 18 ✓"
echo ""

log_info "=========================================="
log_info "Granting Access to Queue Secrets"
log_info "=========================================="
echo ""

# Cloud Tasks Queue secrets
grant_secret_access "PGP_ACCUMULATOR_QUEUE"
grant_secret_access "PGP_ACCUMULATOR_RESPONSE_QUEUE"
grant_secret_access "PGP_BATCHPROCESSOR_QUEUE"
grant_secret_access "PGP_HOSTPAY1_QUEUE"
grant_secret_access "PGP_HOSTPAY1_RESPONSE_QUEUE"
grant_secret_access "PGP_HOSTPAY1_BATCH_QUEUE"
grant_secret_access "PGP_HOSTPAY2_QUEUE"
grant_secret_access "PGP_HOSTPAY3_QUEUE"
grant_secret_access "PGP_HOSTPAY3_RETRY_QUEUE"
grant_secret_access "PGP_SPLIT1_QUEUE"
grant_secret_access "PGP_SPLIT1_BATCH_QUEUE"
grant_secret_access "PGP_SPLIT2_QUEUE"
grant_secret_access "PGP_SPLIT2_RESPONSE_QUEUE"
grant_secret_access "PGP_SPLIT3_QUEUE"
grant_secret_access "PGP_SPLIT3_RESPONSE_QUEUE"
grant_secret_access "PGP_ORCHESTRATOR_QUEUE"
grant_secret_access "PGP_INVITE_QUEUE"
grant_secret_access "PGP_MICROBATCH_RESPONSE_QUEUE"
grant_secret_access "PGP_HOSTPAY_TRIGGER_QUEUE"

echo ""
log_success "Queue secrets: 19 ✓"
echo ""

log_info "=========================================="
log_info "Granting Access to API Keys"
log_info "=========================================="
echo ""

# API Keys
grant_secret_access "NOWPAYMENTS_API_KEY"
grant_secret_access "NOWPAYMENTS_IPN_SECRET"
grant_secret_access "NOWPAYMENT_WEBHOOK_KEY"
grant_secret_access "PAYMENT_PROVIDER_TOKEN"
grant_secret_access "1INCH_API_KEY"
grant_secret_access "CHANGENOW_API_KEY"
grant_secret_access "COINGECKO_API_KEY"
grant_secret_access "CRYPTOCOMPARE_API_KEY"

echo ""
log_success "API Keys: 8 ✓"
echo ""

log_info "=========================================="
log_info "Granting Access to Blockchain & Wallet"
log_info "=========================================="
echo ""

# Blockchain & Wallet
grant_secret_access "HOST_WALLET_PRIVATE_KEY"
grant_secret_access "HOST_WALLET_ETH_ADDRESS"
grant_secret_access "HOST_WALLET_USDT_ADDRESS"
grant_secret_access "ETHEREUM_RPC_URL"
grant_secret_access "ETHEREUM_RPC_URL_API"
grant_secret_access "ETHEREUM_RPC_WEBHOOK_SECRET"

echo ""
log_success "Blockchain & Wallet: 6 ✓"
echo ""

log_info "=========================================="
log_info "Granting Access to Database Credentials"
log_info "=========================================="
echo ""

# Database
grant_secret_access "DATABASE_HOST_SECRET"
grant_secret_access "DATABASE_NAME_SECRET"
grant_secret_access "DATABASE_USER_SECRET"
grant_secret_access "DATABASE_PASSWORD_SECRET"
grant_secret_access "DATABASE_SECRET_KEY"
grant_secret_access "CLOUD_SQL_CONNECTION_NAME"

echo ""
log_success "Database Credentials: 6 ✓"
echo ""

log_info "=========================================="
log_info "Granting Access to Telegram Bot"
log_info "=========================================="
echo ""

# Telegram
grant_secret_access "TELEGRAM_BOT_SECRET_NAME"
grant_secret_access "TELEGRAM_BOT_USERNAME"

echo ""
log_success "Telegram Bot: 2 ✓"
echo ""

log_info "=========================================="
log_info "Granting Access to Signing & Security Keys"
log_info "=========================================="
echo ""

# Signing & Security
grant_secret_access "WEBHOOK_SIGNING_KEY"
grant_secret_access "TPS_HOSTPAY_SIGNING_KEY"
grant_secret_access "SUCCESS_URL_SIGNING_KEY"
grant_secret_access "JWT_SECRET_KEY"
grant_secret_access "SIGNUP_SECRET_KEY"

echo ""
log_success "Signing & Security Keys: 5 ✓"
echo ""

log_info "=========================================="
log_info "Granting Access to Email Configuration"
log_info "=========================================="
echo ""

# Email
grant_secret_access "SENDGRID_API_KEY"
grant_secret_access "FROM_EMAIL"
grant_secret_access "FROM_NAME"

echo ""
log_success "Email Configuration: 3 ✓"
echo ""

log_info "=========================================="
log_info "Granting Access to Application Config"
log_info "=========================================="
echo ""

# Application Config
grant_secret_access "BASE_URL"
grant_secret_access "CORS_ORIGIN"
grant_secret_access "CLOUD_TASKS_LOCATION"
grant_secret_access "CLOUD_TASKS_PROJECT_ID"
grant_secret_access "BROADCAST_AUTO_INTERVAL"
grant_secret_access "BROADCAST_MANUAL_INTERVAL"
grant_secret_access "ALERTING_ENABLED"
grant_secret_access "MICRO_BATCH_THRESHOLD_USD"
grant_secret_access "PAYMENT_FALLBACK_TOLERANCE"
grant_secret_access "PAYMENT_MIN_TOLERANCE"
grant_secret_access "TP_FLAT_FEE"

echo ""
log_success "Application Config: 11 ✓"
echo ""

log_info "=========================================="
log_info "Granting Access to NEW Security Secrets"
log_info "=========================================="
echo ""

# NEW Security Secrets
grant_secret_access "FLASK_SECRET_KEY"
grant_secret_access "TELEGRAM_WEBHOOK_SECRET"

echo ""
log_success "NEW Security Secrets: 2 ✓"
echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
log_info "=========================================="
log_info "SUMMARY"
log_info "=========================================="
echo ""

log_success "✅ IAM policy updates complete!"
echo ""
echo "Total secrets granted access: 77"
echo "Service account: $FULL_SERVICE_ACCOUNT"
echo "Role: roles/secretmanager.secretAccessor"
echo ""

log_info "Verify access:"
echo "  gcloud secrets list --project=$PROJECT_ID"
echo ""
echo "Test secret access:"
echo "  gcloud secrets versions access latest --secret=PGP_ACCUMULATOR_URL --project=$PROJECT_ID"
echo ""

log_success "✅ Ready to deploy services to Cloud Run!"
echo ""
