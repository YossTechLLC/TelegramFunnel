#!/bin/bash
################################################################################
# verify_pgp_live_secrets.sh
#
# Verify All Secret Manager Secrets for PGP_v1
# Checks existence, format, and value patterns for all 69 secrets
#
# This script performs comprehensive validation:
# - Existence check (secret exists in Secret Manager)
# - Format validation (length, pattern matching)
# - Value verification (hex keys, URLs, numeric values)
#
# Usage:
#   ./verify_pgp_live_secrets.sh [--show-values]
#
# Options:
#   --show-values    Show secret values (DANGEROUS - use only in secure environment)
#
# Author: PGP_v1 Migration Team
# Date: 2025-11-18
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
PROJECT="pgp-live"
SHOW_VALUES=false

# Parse arguments
if [[ "${1:-}" == "--show-values" ]]; then
    SHOW_VALUES=true
fi

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Counters
TOTAL_SECRETS=0
FOUND_SECRETS=0
MISSING_SECRETS=0
FORMAT_ERRORS=0

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

log_critical() {
    echo -e "${MAGENTA}🔴 $1${NC}"
}

# Verification function
verify_secret() {
    local secret_name=$1
    local expected_format=${2:-"any"}
    local description=${3:-""}

    ((TOTAL_SECRETS++))

    printf "  %-45s " "$secret_name"

    # Check if secret exists
    if ! gcloud secrets describe "$secret_name" --project="$PROJECT" &>/dev/null; then
        echo -e "${RED}[MISSING]${NC}"
        ((MISSING_SECRETS++))
        return 1
    fi

    # Get secret value
    VALUE=$(gcloud secrets versions access latest --secret="$secret_name" --project="$PROJECT" 2>/dev/null || echo "")

    if [[ -z "$VALUE" ]]; then
        echo -e "${RED}[EMPTY]${NC}"
        ((FORMAT_ERRORS++))
        return 1
    fi

    # Validate format
    case "$expected_format" in
        "hex64")
            if [[ ${#VALUE} -eq 64 ]] && [[ "$VALUE" =~ ^[0-9a-fA-F]+$ ]]; then
                echo -e "${GREEN}[OK]${NC} (64-char hex)"
            else
                echo -e "${YELLOW}[FORMAT ERROR]${NC} (expected 64-char hex, got ${#VALUE} chars)"
                ((FORMAT_ERRORS++))
            fi
            ;;
        "url")
            if [[ "$VALUE" =~ ^https:// ]]; then
                echo -e "${GREEN}[OK]${NC} (URL)"
            else
                echo -e "${YELLOW}[FORMAT ERROR]${NC} (expected https:// URL)"
                ((FORMAT_ERRORS++))
            fi
            ;;
        "queue")
            if [[ "$VALUE" =~ ^pgp-.+-queue-v1$ ]]; then
                echo -e "${GREEN}[OK]${NC} (queue name)"
            else
                echo -e "${YELLOW}[FORMAT ERROR]${NC} (expected pgp-*-queue-v1 pattern)"
                ((FORMAT_ERRORS++))
            fi
            ;;
        "eth_address")
            if [[ "$VALUE" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
                echo -e "${GREEN}[OK]${NC} (ETH address)"
            else
                echo -e "${YELLOW}[FORMAT ERROR]${NC} (expected 0x + 40 hex chars)"
                ((FORMAT_ERRORS++))
            fi
            ;;
        "numeric")
            if [[ "$VALUE" =~ ^[0-9]+\.?[0-9]*$ ]]; then
                echo -e "${GREEN}[OK]${NC} ($VALUE)"
            else
                echo -e "${YELLOW}[FORMAT ERROR]${NC} (expected numeric value)"
                ((FORMAT_ERRORS++))
            fi
            ;;
        *)
            echo -e "${GREEN}[OK]${NC} (${#VALUE} chars)"
            ;;
    esac

    ((FOUND_SECRETS++))

    # Show value if requested (DANGEROUS!)
    if [[ "$SHOW_VALUES" == "true" ]]; then
        echo "    Value: $VALUE"
    fi
}

# Header
echo "════════════════════════════════════════════════════════════════════════════"
echo "  PGP_v1 Secret Verification"
echo "  Project: $PROJECT"
echo "  Expected Secrets: 69"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

if [[ "$SHOW_VALUES" == "true" ]]; then
    log_critical "⚠️  WARNING: --show-values enabled (secrets will be displayed)"
    echo ""
fi

# Set active project
gcloud config set project "$PROJECT"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  1. Database Credentials (5 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

verify_secret "CLOUD_SQL_CONNECTION_NAME" "any" "Cloud SQL instance connection name"
verify_secret "DATABASE_NAME_SECRET" "any" "Database name"
verify_secret "DATABASE_USER_SECRET" "any" "Database username"
verify_secret "DATABASE_PASSWORD_SECRET" "hex64" "Database password (64-char hex)"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  2. Service URLs (14 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

verify_secret "PGP_SERVER_URL" "url"
verify_secret "PGP_WEBAPI_URL" "url"
verify_secret "PGP_NP_IPN_URL" "url"
verify_secret "PGP_ORCHESTRATOR_URL" "url"
verify_secret "PGP_INVITE_URL" "url"
verify_secret "PGP_NOTIFICATIONS_URL" "url"
verify_secret "PGP_BATCHPROCESSOR_URL" "url"
verify_secret "PGP_MICROBATCH_URL" "url"
verify_secret "PGP_SPLIT1_URL" "url"
verify_secret "PGP_SPLIT2_URL" "url"
verify_secret "PGP_SPLIT3_URL" "url"
verify_secret "PGP_HOSTPAY1_URL" "url"
verify_secret "PGP_HOSTPAY2_URL" "url"
verify_secret "PGP_HOSTPAY3_URL" "url"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  3. Cloud Tasks Queue Names (16 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

verify_secret "PGP_ORCHESTRATOR_QUEUE" "queue"
verify_secret "PGP_INVITE_QUEUE" "queue"
verify_secret "PGP_NOTIFICATIONS_QUEUE" "queue"
verify_secret "PGP_BATCHPROCESSOR_QUEUE" "queue"
verify_secret "PGP_SPLIT1_QUEUE" "queue"
verify_secret "PGP_SPLIT1_BATCH_QUEUE" "queue"
verify_secret "PGP_SPLIT1_RESPONSE_QUEUE" "queue"
verify_secret "PGP_SPLIT2_ESTIMATE_QUEUE" "queue"
verify_secret "PGP_SPLIT3_SWAP_QUEUE" "queue"
verify_secret "PGP_HOSTPAY_TRIGGER_QUEUE" "queue"
verify_secret "PGP_HOSTPAY1_BATCH_QUEUE" "queue"
verify_secret "PGP_HOSTPAY1_RESPONSE_QUEUE" "queue"
verify_secret "PGP_HOSTPAY2_STATUS_QUEUE" "queue"
verify_secret "PGP_HOSTPAY3_PAYMENT_QUEUE" "queue"
verify_secret "PGP_HOSTPAY3_RETRY_QUEUE" "queue"
verify_secret "PGP_MICROBATCH_RESPONSE_QUEUE" "queue"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  4. Signing & Encryption Keys (5 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

verify_secret "SUCCESS_URL_SIGNING_KEY" "hex64"
verify_secret "TPS_HOSTPAY_SIGNING_KEY" "hex64"
verify_secret "JWT_SECRET_KEY" "hex64"
verify_secret "SIGNUP_SECRET_KEY" "hex64"
verify_secret "PGP_INTERNAL_SIGNING_KEY" "hex64"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  5. Wallet & Blockchain (5 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

log_critical "HOST_WALLET_PRIVATE_KEY (ULTRA-CRITICAL - NEVER display)"
verify_secret "HOST_WALLET_PRIVATE_KEY" "hex64"
verify_secret "HOST_WALLET_ETH_ADDRESS" "eth_address"
verify_secret "HOST_WALLET_USDT_ADDRESS" "eth_address"
verify_secret "ETHEREUM_RPC_URL" "url"
verify_secret "ETHEREUM_RPC_URL_API" "any"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  6. Payment Provider APIs (4 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

verify_secret "NOWPAYMENTS_API_KEY" "any"
verify_secret "NOWPAYMENTS_IPN_SECRET" "any"
verify_secret "CHANGENOW_API_KEY" "hex64"
verify_secret "SENDGRID_API_KEY" "any"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  7. Telegram Bot (2 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

verify_secret "TELEGRAM_BOT_API_TOKEN" "any"
verify_secret "TELEGRAM_BOT_USERNAME" "any"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  8. Redis / Nonce Tracking (2 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

verify_secret "PGP_REDIS_HOST" "any"
verify_secret "PGP_REDIS_PORT" "numeric"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  9. Cloud Tasks Infrastructure (2 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

verify_secret "CLOUD_TASKS_PROJECT_ID" "any"
verify_secret "CLOUD_TASKS_LOCATION" "any"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  10. Application Configuration (12 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

verify_secret "BASE_URL" "url"
verify_secret "CORS_ORIGIN" "url"
verify_secret "FROM_EMAIL" "any"
verify_secret "FROM_NAME" "any"
verify_secret "TP_FLAT_FEE" "numeric"
verify_secret "PAYMENT_MIN_TOLERANCE" "numeric"
verify_secret "PAYMENT_FALLBACK_TOLERANCE" "numeric"
verify_secret "MICRO_BATCH_THRESHOLD_USD" "numeric"
verify_secret "BROADCAST_AUTO_INTERVAL" "numeric"
verify_secret "BROADCAST_MANUAL_INTERVAL" "numeric"
verify_secret "NOWPAYMENTS_IPN_CALLBACK_URL" "url"

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Verification Summary"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

log_info "Results:"
echo "  📊 Total Secrets: $TOTAL_SECRETS"
echo "  ✅ Found: $FOUND_SECRETS"
echo "  ❌ Missing: $MISSING_SECRETS"
echo "  ⚠️  Format Errors: $FORMAT_ERRORS"
echo ""

if [[ $MISSING_SECRETS -eq 0 ]] && [[ $FORMAT_ERRORS -eq 0 ]]; then
    log_success "✅ All secrets verified successfully!"
    echo ""
    log_info "Next steps:"
    echo "  1. Grant IAM access: ./grant_pgp_live_secret_access.sh"
    echo "  2. Deploy PGP_v1 services"
    echo "  3. Test secret access from Cloud Run"
    exit 0
else
    log_error "❌ Verification failed"
    echo ""
    if [[ $MISSING_SECRETS -gt 0 ]]; then
        log_error "$MISSING_SECRETS secrets are missing"
        echo "  Run appropriate phase scripts to create missing secrets"
    fi
    if [[ $FORMAT_ERRORS -gt 0 ]]; then
        log_warning "$FORMAT_ERRORS secrets have format errors"
        echo "  Review and update secret values"
    fi
    exit 1
fi
