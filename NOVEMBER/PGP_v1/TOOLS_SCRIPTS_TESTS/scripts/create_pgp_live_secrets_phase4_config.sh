#!/bin/bash
################################################################################
# create_pgp_live_secrets_phase4_config.sh
#
# Phase 4: Application Configuration Secrets (12 secrets)
# Creates business logic and operational configuration values
#
# All secrets in this phase are HOT-RELOADABLE (zero-downtime updates)
#
# Prerequisites:
# - Phase 1, 2, 3 completed
# - Domain name configured (www.paygateprime.com)
#
# Usage:
#   ./create_pgp_live_secrets_phase4_config.sh
#
# Author: PGP_v1 Migration Team
# Date: 2025-11-18
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
PROJECT="pgp-live"
DOMAIN="https://www.paygateprime.com"
BOT_USERNAME="@PayGatePrime_bot"

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
echo "  Phase 4: Application Configuration Secrets"
echo "  Project: $PROJECT"
echo "  Secrets: 12 (All HOT-RELOADABLE)"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Set active project
gcloud config set project "$PROJECT"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  1. Web & Email Configuration (4 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 1.1 BASE_URL
log_info "Creating BASE_URL"
if gcloud secrets describe BASE_URL --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'BASE_URL' already exists, skipping"
else
    echo -n "$DOMAIN" | gcloud secrets create BASE_URL \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: BASE_URL = $DOMAIN"
fi

# 1.2 CORS_ORIGIN
log_info "Creating CORS_ORIGIN"
if gcloud secrets describe CORS_ORIGIN --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'CORS_ORIGIN' already exists, skipping"
else
    echo -n "$DOMAIN" | gcloud secrets create CORS_ORIGIN \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: CORS_ORIGIN = $DOMAIN"
fi

# 1.3 FROM_EMAIL
log_info "Creating FROM_EMAIL"
if gcloud secrets describe FROM_EMAIL --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'FROM_EMAIL' already exists, skipping"
else
    echo -n "noreply@paygateprime.com" | gcloud secrets create FROM_EMAIL \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: FROM_EMAIL = noreply@paygateprime.com"
fi

# 1.4 FROM_NAME
log_info "Creating FROM_NAME"
if gcloud secrets describe FROM_NAME --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'FROM_NAME' already exists, skipping"
else
    echo -n "PayGatePrime" | gcloud secrets create FROM_NAME \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: FROM_NAME = PayGatePrime"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  2. Telegram Configuration (1 secret)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 2.1 TELEGRAM_BOT_USERNAME
log_info "Creating TELEGRAM_BOT_USERNAME"
if gcloud secrets describe TELEGRAM_BOT_USERNAME --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'TELEGRAM_BOT_USERNAME' already exists, skipping"
else
    echo -n "$BOT_USERNAME" | gcloud secrets create TELEGRAM_BOT_USERNAME \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: TELEGRAM_BOT_USERNAME = $BOT_USERNAME"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  3. Payment & Tolerance Configuration (3 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 3.1 TP_FLAT_FEE
log_info "Creating TP_FLAT_FEE"
if gcloud secrets describe TP_FLAT_FEE --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'TP_FLAT_FEE' already exists, skipping"
else
    echo -n "3" | gcloud secrets create TP_FLAT_FEE \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: TP_FLAT_FEE = 3 (3% fee)"
fi

# 3.2 PAYMENT_MIN_TOLERANCE
log_info "Creating PAYMENT_MIN_TOLERANCE"
if gcloud secrets describe PAYMENT_MIN_TOLERANCE --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'PAYMENT_MIN_TOLERANCE' already exists, skipping"
else
    echo -n "0.50" | gcloud secrets create PAYMENT_MIN_TOLERANCE \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: PAYMENT_MIN_TOLERANCE = 0.50 (50% minimum)"
fi

# 3.3 PAYMENT_FALLBACK_TOLERANCE
log_info "Creating PAYMENT_FALLBACK_TOLERANCE"
if gcloud secrets describe PAYMENT_FALLBACK_TOLERANCE --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'PAYMENT_FALLBACK_TOLERANCE' already exists, skipping"
else
    echo -n "0.75" | gcloud secrets create PAYMENT_FALLBACK_TOLERANCE \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: PAYMENT_FALLBACK_TOLERANCE = 0.75 (75% fallback)"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  4. Payout Threshold (1 secret)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 4.1 MICRO_BATCH_THRESHOLD_USD
log_info "Creating MICRO_BATCH_THRESHOLD_USD"
if gcloud secrets describe MICRO_BATCH_THRESHOLD_USD --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'MICRO_BATCH_THRESHOLD_USD' already exists, skipping"
else
    echo -n "5.00" | gcloud secrets create MICRO_BATCH_THRESHOLD_USD \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: MICRO_BATCH_THRESHOLD_USD = 5.00 ($5 USD threshold)"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  5. Broadcast Configuration (2 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 5.1 BROADCAST_AUTO_INTERVAL
log_info "Creating BROADCAST_AUTO_INTERVAL"
if gcloud secrets describe BROADCAST_AUTO_INTERVAL --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'BROADCAST_AUTO_INTERVAL' already exists, skipping"
else
    echo -n "24.0" | gcloud secrets create BROADCAST_AUTO_INTERVAL \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: BROADCAST_AUTO_INTERVAL = 24.0 (24 hours)"
fi

# 5.2 BROADCAST_MANUAL_INTERVAL
log_info "Creating BROADCAST_MANUAL_INTERVAL"
if gcloud secrets describe BROADCAST_MANUAL_INTERVAL --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'BROADCAST_MANUAL_INTERVAL' already exists, skipping"
else
    echo -n "0.0833" | gcloud secrets create BROADCAST_MANUAL_INTERVAL \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: BROADCAST_MANUAL_INTERVAL = 0.0833 (5 minutes)"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  6. NOWPayments IPN Callback URL (1 secret)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 6.1 NOWPAYMENTS_IPN_CALLBACK_URL
log_info "Creating NOWPAYMENTS_IPN_CALLBACK_URL"
if gcloud secrets describe NOWPAYMENTS_IPN_CALLBACK_URL --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'NOWPAYMENTS_IPN_CALLBACK_URL' already exists, skipping"
else
    echo ""
    log_warning "This URL will be set after PGP_NP_IPN_v1 is deployed"
    log_info "Expected format: https://pgp-np-ipn-v1-{PROJECT_NUM}.us-central1.run.app/webhook"
    echo ""
    read -p "Enter NOWPAYMENTS_IPN_CALLBACK_URL (or press Enter to skip): " NP_CALLBACK

    if [[ -z "$NP_CALLBACK" ]]; then
        log_warning "Skipping NOWPAYMENTS_IPN_CALLBACK_URL - create it after PGP_NP_IPN_v1 deployment"
    else
        if [[ ! "$NP_CALLBACK" =~ ^https:// ]]; then
            log_error "Invalid URL format (must start with https://)"
            exit 1
        fi

        echo -n "$NP_CALLBACK" | gcloud secrets create NOWPAYMENTS_IPN_CALLBACK_URL \
            --data-file=- \
            --replication-policy="automatic" \
            --project="$PROJECT"
        log_success "Created: NOWPAYMENTS_IPN_CALLBACK_URL"
    fi
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Phase 4: Application Configuration - COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Summary
log_success "Created application configuration secrets:"
echo "  ✅ Web & Email Configuration (4 secrets)"
echo "  ✅ Telegram Configuration (1 secret)"
echo "  ✅ Payment & Tolerance Configuration (3 secrets)"
echo "  ✅ Payout Threshold (1 secret)"
echo "  ✅ Broadcast Configuration (2 secrets)"
echo "  ✅ NOWPayments IPN Callback (1 secret, may be skipped)"
echo ""

log_info "All Phase 4 secrets are HOT-RELOADABLE"
log_info "You can update these values without service restart (60s cache TTL)"
echo ""

log_info "Next steps:"
echo "  1. Deploy all Cloud Run services"
echo "  2. Run Phase 5: ./create_pgp_live_secrets_phase5_service_urls.sh"
echo "  3. Deploy all Cloud Tasks queues"
echo "  4. Run Phase 6: ./create_pgp_live_secrets_phase6_queue_names.sh"
echo "  5. Grant IAM access: ./grant_pgp_live_secret_access.sh"
echo ""

# List all created secrets
log_info "Verifying created configuration secrets..."
gcloud secrets list --project="$PROJECT" --filter="name:BASE_URL OR name:CORS_ORIGIN OR name:FROM_EMAIL OR name:FROM_NAME OR name:TELEGRAM_BOT_USERNAME OR name:TP_FLAT_FEE OR name:PAYMENT_MIN_TOLERANCE OR name:PAYMENT_FALLBACK_TOLERANCE OR name:MICRO_BATCH_THRESHOLD_USD OR name:BROADCAST_AUTO_INTERVAL OR name:BROADCAST_MANUAL_INTERVAL OR name:NOWPAYMENTS_IPN_CALLBACK_URL"

echo ""
log_success "Phase 4 deployment completed successfully! 🎉"
