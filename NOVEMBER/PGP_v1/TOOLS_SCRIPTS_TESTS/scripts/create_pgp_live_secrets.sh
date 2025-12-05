#!/bin/bash

# Create All Secrets in pgp-live with PGP_v1 Naming Scheme
# This script creates ALL 77 secrets required for pgp-live deployment
#
# IMPORTANT: DO NOT RUN THIS SCRIPT YET - Review and customize first
#
# Prerequisites:
# 1. gcloud CLI authenticated
# 2. pgp-live project created
# 3. Secret Manager API enabled
# 4. User has secretmanager.admin role
#
# Usage:
#   ./create_pgp_live_secrets.sh [--dry-run]

set -e  # Exit on error

# Configuration
PROJECT_ID="pgp-live"
REGION="us-central1"
DRY_RUN=false

# Check for dry-run flag
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "🔍 DRY RUN MODE - No secrets will be created"
    echo ""
fi

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

# Function to create a secret
create_secret() {
    local secret_name="$1"
    local secret_value="$2"
    local description="$3"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would create secret: $secret_name"
        return 0
    fi

    # Check if secret already exists
    if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
        log_warning "Secret $secret_name already exists, adding new version"
        echo -n "$secret_value" | gcloud secrets versions add "$secret_name" \
            --data-file=- \
            --project="$PROJECT_ID"
    else
        log_info "Creating secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create "$secret_name" \
            --data-file=- \
            --replication-policy="automatic" \
            --project="$PROJECT_ID"

        # Add description as label (gcloud doesn't support descriptions directly)
        # Labels can only contain lowercase letters, numbers, hyphens, and underscores
        local label_desc=$(echo "$description" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g' | cut -c1-63)
        if [[ -n "$label_desc" ]]; then
            gcloud secrets update "$secret_name" \
                --update-labels="description=$label_desc" \
                --project="$PROJECT_ID" &>/dev/null || true
        fi
    fi

    log_success "Created/Updated: $secret_name"
}

# Function to generate secure random key
generate_secret_key() {
    python3 -c "import secrets; print(secrets.token_hex(32))"
}

generate_url_safe_key() {
    python3 -c "import secrets; print(secrets.token_urlsafe(32))"
}

# ============================================================================
# VERIFICATION
# ============================================================================

log_info "🚀 Starting secret creation for project: $PROJECT_ID"
echo ""

# Verify gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &>/dev/null; then
    log_error "Not authenticated with gcloud. Run: gcloud auth login"
    exit 1
fi

# Verify project exists
if ! gcloud projects describe "$PROJECT_ID" &>/dev/null; then
    log_error "Project $PROJECT_ID does not exist. Create it first."
    exit 1
fi

# Verify Secret Manager API is enabled
if ! gcloud services list --enabled --project="$PROJECT_ID" | grep -q secretmanager; then
    log_warning "Secret Manager API not enabled. Enabling now..."
    if [[ "$DRY_RUN" == false ]]; then
        gcloud services enable secretmanager.googleapis.com --project="$PROJECT_ID"
        log_success "Secret Manager API enabled"
    fi
fi

echo ""
log_info "Prerequisites verified ✓"
echo ""
log_warning "⚠️  IMPORTANT: This script will create 77 secrets in $PROJECT_ID"
log_warning "⚠️  Review the values below before proceeding"
echo ""

if [[ "$DRY_RUN" == false ]]; then
    read -p "Continue? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "Aborted by user"
        exit 0
    fi
    echo ""
fi

# ============================================================================
# PART 1: SERVICE URL SECRETS (13 secrets with NEW NAMES)
# ============================================================================

log_info "=========================================="
log_info "PART 1: Creating Service URL Secrets"
log_info "=========================================="
echo ""

# NOTE: Replace <PROJECT_NUM> with actual project number after Cloud Run deployment
# For now, using placeholder - UPDATE THESE VALUES after services are deployed
PROJECT_NUM="YOUR_PROJECT_NUMBER_HERE"  # UPDATE THIS

create_secret "PGP_ACCUMULATOR_URL" \
    "https://pgp-accumulator-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_ACCUMULATOR_v1 service URL"

create_secret "PGP_BATCHPROCESSOR_URL" \
    "https://pgp-batchprocessor-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_BATCHPROCESSOR_v1 service URL"

create_secret "PGP_MICROBATCHPROCESSOR_URL" \
    "https://pgp-microbatchprocessor-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_MICROBATCHPROCESSOR_v1 service URL"

create_secret "PGP_HOSTPAY1_URL" \
    "https://pgp-hostpay1-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_HOSTPAY1_v1 service URL"

create_secret "PGP_HOSTPAY2_URL" \
    "https://pgp-hostpay2-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_HOSTPAY2_v1 service URL"

create_secret "PGP_HOSTPAY3_URL" \
    "https://pgp-hostpay3-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_HOSTPAY3_v1 service URL"

create_secret "PGP_SPLIT1_URL" \
    "https://pgp-split1-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_SPLIT1_v1 service URL"

create_secret "PGP_SPLIT2_URL" \
    "https://pgp-split2-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_SPLIT2_v1 service URL"

create_secret "PGP_SPLIT3_URL" \
    "https://pgp-split3-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_SPLIT3_v1 service URL"

create_secret "PGP_ORCHESTRATOR_URL" \
    "https://pgp-orchestrator-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_ORCHESTRATOR_v1 service URL"

create_secret "PGP_INVITE_URL" \
    "https://pgp-invite-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_INVITE_v1 service URL"

create_secret "PGP_SERVER_URL" \
    "https://pgp-server-v1-${PROJECT_NUM}.us-central1.run.app" \
    "PGP_SERVER_v1 service URL"

create_secret "PGP_NP_IPN_CALLBACK_URL" \
    "https://pgp-np-ipn-v1-${PROJECT_NUM}.us-central1.run.app/webhooks/nowpayments-ipn" \
    "PGP_NP_IPN_v1 IPN callback URL"

# Additional URL secrets (names unchanged)
create_secret "WEBHOOK_BASE_URL" \
    "https://pgp-orchestrator-v1-${PROJECT_NUM}.us-central1.run.app" \
    "Webhook base URL (alias for PGP_ORCHESTRATOR_URL)"

create_secret "TPS_WEBHOOK_URL" \
    "https://pgp-split1-v1-${PROJECT_NUM}.us-central1.run.app" \
    "TelePay webhook callback URL"

create_secret "HOSTPAY_WEBHOOK_URL" \
    "https://pgp-hostpay1-v1-${PROJECT_NUM}.us-central1.run.app" \
    "HostPay webhook URL (duplicate)"

# Callback endpoints
create_secret "GCSPLIT1_ESTIMATE_RESPONSE_URL" \
    "https://pgp-split1-v1-${PROJECT_NUM}.us-central1.run.app/usdt-eth-estimate" \
    "Split1 estimate response callback"

create_secret "GCSPLIT1_SWAP_RESPONSE_URL" \
    "https://pgp-split1-v1-${PROJECT_NUM}.us-central1.run.app/eth-client-swap" \
    "Split1 swap response callback"

echo ""
log_success "Service URL secrets created: 16"
echo ""

# ============================================================================
# PART 2: CLOUD TASKS QUEUE SECRETS (17 secrets with NEW NAMES)
# ============================================================================

log_info "=========================================="
log_info "PART 2: Creating Cloud Tasks Queue Secrets"
log_info "=========================================="
echo ""

create_secret "PGP_ACCUMULATOR_QUEUE" \
    "pgp-accumulator-queue-v1" \
    "PGP_ACCUMULATOR_v1 main queue"

create_secret "PGP_ACCUMULATOR_RESPONSE_QUEUE" \
    "pgp-accumulator-response-queue-v1" \
    "PGP_ACCUMULATOR_v1 response queue"

create_secret "PGP_BATCHPROCESSOR_QUEUE" \
    "pgp-batchprocessor-queue-v1" \
    "PGP_BATCHPROCESSOR_v1 queue"

create_secret "PGP_HOSTPAY1_QUEUE" \
    "pgp-hostpay1-trigger-queue-v1" \
    "PGP_HOSTPAY1_v1 trigger queue"

create_secret "PGP_HOSTPAY1_RESPONSE_QUEUE" \
    "pgp-hostpay1-response-queue-v1" \
    "PGP_HOSTPAY1_v1 response queue"

create_secret "PGP_HOSTPAY1_BATCH_QUEUE" \
    "pgp-hostpay1-batch-queue-v1" \
    "PGP_HOSTPAY1_v1 batch queue"

create_secret "PGP_HOSTPAY2_QUEUE" \
    "pgp-hostpay2-status-queue-v1" \
    "PGP_HOSTPAY2_v1 status queue"

create_secret "PGP_HOSTPAY3_QUEUE" \
    "pgp-hostpay3-payment-queue-v1" \
    "PGP_HOSTPAY3_v1 payment queue"

create_secret "PGP_HOSTPAY3_RETRY_QUEUE" \
    "pgp-hostpay3-retry-queue-v1" \
    "PGP_HOSTPAY3_v1 retry queue"

create_secret "PGP_SPLIT1_QUEUE" \
    "pgp-split1-estimate-queue-v1" \
    "PGP_SPLIT1_v1 estimate queue"

create_secret "PGP_SPLIT1_BATCH_QUEUE" \
    "pgp-split1-batch-queue-v1" \
    "PGP_SPLIT1_v1 batch queue"

create_secret "PGP_SPLIT2_QUEUE" \
    "pgp-split2-swap-queue-v1" \
    "PGP_SPLIT2_v1 swap queue"

create_secret "PGP_SPLIT2_RESPONSE_QUEUE" \
    "pgp-split2-response-queue-v1" \
    "PGP_SPLIT2_v1 response queue"

create_secret "PGP_SPLIT3_QUEUE" \
    "pgp-split3-client-queue-v1" \
    "PGP_SPLIT3_v1 client queue"

create_secret "PGP_SPLIT3_RESPONSE_QUEUE" \
    "pgp-split3-response-queue-v1" \
    "PGP_SPLIT3_v1 response queue"

create_secret "PGP_ORCHESTRATOR_QUEUE" \
    "pgp-orchestrator-queue-v1" \
    "PGP_ORCHESTRATOR_v1 queue"

create_secret "PGP_INVITE_QUEUE" \
    "pgp-invite-queue-v1" \
    "PGP_INVITE_v1 queue"

# Additional queue secrets
create_secret "PGP_MICROBATCH_RESPONSE_QUEUE" \
    "pgp-microbatch-response-queue-v1" \
    "PGP_MICROBATCHPROCESSOR_v1 response queue"

create_secret "PGP_HOSTPAY_TRIGGER_QUEUE" \
    "pgp-hostpay1-trigger-queue-v1" \
    "HostPay trigger queue (duplicate)"

echo ""
log_success "Cloud Tasks queue secrets created: 19"
echo ""

# ============================================================================
# PART 3: API KEYS & TOKENS (Copy from telepay-459221)
# ============================================================================

log_info "=========================================="
log_info "PART 3: API Keys & Tokens"
log_info "=========================================="
echo ""

log_warning "⚠️  The following secrets require VALUES from telepay-459221"
log_warning "⚠️  Fetch each value and replace <VALUE_FROM_TELEPAY> below"
echo ""

# Payment & Exchange APIs
create_secret "NOWPAYMENTS_API_KEY" \
    "<VALUE_FROM_TELEPAY>" \
    "NOWPayments API key"

create_secret "NOWPAYMENTS_IPN_SECRET" \
    "<VALUE_FROM_TELEPAY>" \
    "NOWPayments IPN secret"

create_secret "NOWPAYMENT_WEBHOOK_KEY" \
    "<VALUE_FROM_TELEPAY>" \
    "NOWPayments webhook key"

create_secret "PAYMENT_PROVIDER_TOKEN" \
    "<VALUE_FROM_TELEPAY>" \
    "Payment provider token (duplicate)"

create_secret "1INCH_API_KEY" \
    "<VALUE_FROM_TELEPAY>" \
    "1inch DEX API key"

create_secret "CHANGENOW_API_KEY" \
    "<VALUE_FROM_TELEPAY>" \
    "ChangeNOW API key"

create_secret "COINGECKO_API_KEY" \
    "<VALUE_FROM_TELEPAY>" \
    "CoinGecko API key"

create_secret "CRYPTOCOMPARE_API_KEY" \
    "<VALUE_FROM_TELEPAY>" \
    "CryptoCompare API key"

echo ""
log_success "API Keys created: 8"
echo ""

# ============================================================================
# PART 4: BLOCKCHAIN & WALLET (Copy from telepay-459221)
# ============================================================================

log_info "=========================================="
log_info "PART 4: Blockchain & Wallet Secrets"
log_info "=========================================="
echo ""

log_error "🔴 CRITICAL: These are HIGHLY SENSITIVE secrets"
log_warning "⚠️  Fetch these values SECURELY from telepay-459221"
echo ""

create_secret "HOST_WALLET_PRIVATE_KEY" \
    "<VALUE_FROM_TELEPAY_CRITICAL>" \
    "Host wallet private key (CRITICAL)"

create_secret "HOST_WALLET_ETH_ADDRESS" \
    "<VALUE_FROM_TELEPAY>" \
    "Host wallet ETH address"

create_secret "HOST_WALLET_USDT_ADDRESS" \
    "<VALUE_FROM_TELEPAY>" \
    "Host wallet USDT address"

create_secret "ETHEREUM_RPC_URL" \
    "<VALUE_FROM_TELEPAY>" \
    "Alchemy RPC full URL"

create_secret "ETHEREUM_RPC_URL_API" \
    "<VALUE_FROM_TELEPAY>" \
    "Alchemy API key only"

create_secret "ETHEREUM_RPC_WEBHOOK_SECRET" \
    "<VALUE_FROM_TELEPAY>" \
    "Alchemy webhook secret"

echo ""
log_success "Blockchain & wallet secrets created: 6"
echo ""

# ============================================================================
# PART 5: DATABASE CREDENTIALS (New values for pgp-live)
# ============================================================================

log_info "=========================================="
log_info "PART 5: Database Credentials"
log_info "=========================================="
echo ""

log_warning "⚠️  Update these values AFTER creating Cloud SQL instance in pgp-live"
echo ""

create_secret "DATABASE_HOST_SECRET" \
    "<NEW_CLOUD_SQL_IP>" \
    "PostgreSQL host IP (from Cloud SQL)"

create_secret "DATABASE_NAME_SECRET" \
    "pgp_live_db" \
    "PostgreSQL database name"

create_secret "DATABASE_USER_SECRET" \
    "postgres" \
    "PostgreSQL user"

# Generate new password for pgp-live database
NEW_DB_PASSWORD="<GENERATE_NEW_PASSWORD>"  # TODO: Generate secure password
create_secret "DATABASE_PASSWORD_SECRET" \
    "$NEW_DB_PASSWORD" \
    "PostgreSQL password (NEW for pgp-live)"

# Generate new encryption key
NEW_DB_KEY=$(generate_secret_key)
create_secret "DATABASE_SECRET_KEY" \
    "$NEW_DB_KEY" \
    "Database encryption key (NEW for pgp-live)"

create_secret "CLOUD_SQL_CONNECTION_NAME" \
    "pgp-live:us-central1:pgp-live-psql" \
    "Cloud SQL connection name"

echo ""
log_success "Database credentials created: 6"
echo ""

# ============================================================================
# PART 6: TELEGRAM BOT (Copy from telepay-459221 OR create new bot)
# ============================================================================

log_info "=========================================="
log_info "PART 6: Telegram Bot Secrets"
log_info "=========================================="
echo ""

log_warning "⚠️  Option A: Copy from telepay-459221 (use same bot)"
log_warning "⚠️  Option B: Create NEW bot via @BotFather (recommended for new project)"
echo ""

create_secret "TELEGRAM_BOT_SECRET_NAME" \
    "<VALUE_FROM_TELEPAY_OR_NEW_BOT>" \
    "Telegram bot token"

create_secret "TELEGRAM_BOT_USERNAME" \
    "PayGatePrime_bot" \
    "Telegram bot username"

echo ""
log_success "Telegram bot secrets created: 2"
echo ""

# ============================================================================
# PART 7: SIGNING & SECURITY KEYS (Generate NEW for pgp-live)
# ============================================================================

log_info "=========================================="
log_info "PART 7: Signing & Security Keys"
log_info "=========================================="
echo ""

log_info "🔐 Generating NEW signing keys for pgp-live (recommended for security)"
echo ""

WEBHOOK_SIGNING=$(generate_secret_key)
create_secret "WEBHOOK_SIGNING_KEY" \
    "$WEBHOOK_SIGNING" \
    "Webhook payload signing key (NEW)"

TPS_SIGNING=$(generate_secret_key)
create_secret "TPS_HOSTPAY_SIGNING_KEY" \
    "$TPS_SIGNING" \
    "TelePay to HostPay signing key (NEW)"

SUCCESS_SIGNING=$(generate_url_safe_key)
create_secret "SUCCESS_URL_SIGNING_KEY" \
    "$SUCCESS_SIGNING" \
    "Payment success URL signing key (NEW)"

JWT_SECRET=$(generate_secret_key)
create_secret "JWT_SECRET_KEY" \
    "$JWT_SECRET" \
    "JWT signing key (NEW)"

SIGNUP_SECRET=$(generate_secret_key)
create_secret "SIGNUP_SECRET_KEY" \
    "$SIGNUP_SECRET" \
    "User signup key (NEW)"

echo ""
log_success "Signing & security keys created: 5"
echo ""

# ============================================================================
# PART 8: EMAIL CONFIGURATION (Copy from telepay-459221)
# ============================================================================

log_info "=========================================="
log_info "PART 8: Email Configuration"
log_info "=========================================="
echo ""

create_secret "SENDGRID_API_KEY" \
    "<VALUE_FROM_TELEPAY>" \
    "SendGrid API key"

create_secret "FROM_EMAIL" \
    "noreply@paygateprime.com" \
    "Sender email address"

create_secret "FROM_NAME" \
    "PayGatePrime" \
    "Sender name"

echo ""
log_success "Email configuration secrets created: 3"
echo ""

# ============================================================================
# PART 9: APPLICATION CONFIGURATION
# ============================================================================

log_info "=========================================="
log_info "PART 9: Application Configuration"
log_info "=========================================="
echo ""

create_secret "BASE_URL" \
    "https://www.paygateprime.com" \
    "Main application URL"

create_secret "CORS_ORIGIN" \
    "https://www.paygateprime.com" \
    "CORS origin"

create_secret "CLOUD_TASKS_LOCATION" \
    "us-central1" \
    "Cloud Tasks region"

create_secret "CLOUD_TASKS_PROJECT_ID" \
    "pgp-live" \
    "Cloud Tasks project ID"

create_secret "BROADCAST_AUTO_INTERVAL" \
    "24" \
    "Auto broadcast interval (hours)"

create_secret "BROADCAST_MANUAL_INTERVAL" \
    "0.0833" \
    "Manual broadcast interval (hours)"

create_secret "ALERTING_ENABLED" \
    "true" \
    "System alerting enabled flag"

create_secret "MICRO_BATCH_THRESHOLD_USD" \
    "5.00" \
    "Micro batch threshold USD"

create_secret "PAYMENT_FALLBACK_TOLERANCE" \
    "0.75" \
    "Payment fallback tolerance USD"

create_secret "PAYMENT_MIN_TOLERANCE" \
    "0.50" \
    "Minimum payment tolerance USD"

create_secret "TP_FLAT_FEE" \
    "15" \
    "TelePay flat fee percentage"

echo ""
log_success "Application configuration secrets created: 11"
echo ""

# ============================================================================
# PART 10: NEW SECURITY SECRETS (PGP_v1 additions)
# ============================================================================

log_info "=========================================="
log_info "PART 10: NEW Security Secrets"
log_info "=========================================="
echo ""

log_info "🔐 Generating NEW security secrets for PGP_v1"
echo ""

FLASK_SECRET=$(generate_secret_key)
create_secret "FLASK_SECRET_KEY" \
    "$FLASK_SECRET" \
    "Flask CSRF protection key (NEW)"

TELEGRAM_WEBHOOK_SECRET=$(generate_url_safe_key)
create_secret "TELEGRAM_WEBHOOK_SECRET" \
    "$TELEGRAM_WEBHOOK_SECRET" \
    "Telegram webhook verification secret (NEW)"

echo ""
log_success "New security secrets created: 2"
echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
log_info "=========================================="
log_info "SUMMARY"
log_info "=========================================="
echo ""

log_success "Total secrets processed: 77"
echo ""
echo "Breakdown:"
echo "  - Service URLs: 18"
echo "  - Cloud Tasks Queues: 19"
echo "  - API Keys & Tokens: 8"
echo "  - Blockchain & Wallet: 6"
echo "  - Database Credentials: 6"
echo "  - Telegram Bot: 2"
echo "  - Signing & Security: 5"
echo "  - Email Configuration: 3"
echo "  - Application Config: 11"
echo "  - NEW Security Secrets: 2"
echo ""

log_warning "⚠️  NEXT STEPS:"
echo ""
echo "1. Review all secrets in Secret Manager:"
echo "   gcloud secrets list --project=$PROJECT_ID"
echo ""
echo "2. Update placeholder values:"
echo "   - <VALUE_FROM_TELEPAY>: Fetch from telepay-459221"
echo "   - <NEW_CLOUD_SQL_IP>: Set after Cloud SQL creation"
echo "   - <PROJECT_NUM>: Set after Cloud Run deployment"
echo ""
echo "3. Grant service account access:"
echo "   ./grant_secret_access.sh"
echo ""
echo "4. Update code to reference NEW secret names"
echo ""

if [[ "$DRY_RUN" == false ]]; then
    log_success "✅ Secret creation complete!"
else
    log_info "🔍 Dry run complete - no secrets created"
fi

echo ""
