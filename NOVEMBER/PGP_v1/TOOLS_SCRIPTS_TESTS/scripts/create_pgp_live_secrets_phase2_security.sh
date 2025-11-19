#!/bin/bash
################################################################################
# create_pgp_live_secrets_phase2_security.sh
#
# Phase 2: Security Secrets (10 secrets)
# Creates signing keys, wallet secrets, and payment provider webhooks
#
# ⚠️  CRITICAL: This script handles ULTRA-SENSITIVE secrets
# - All signing keys are STATIC (cannot hot-reload)
# - Wallet private key controls ALL FUNDS
# - Use secure input methods (read -sp for sensitive data)
#
# Prerequisites:
# - Phase 1 completed
# - Wallet private key available from secure storage
# - NOWPayments IPN secret from dashboard
# - Telegram bot token from BotFather
#
# Usage:
#   ./create_pgp_live_secrets_phase2_security.sh
#
# Author: PGP_v1 Migration Team
# Date: 2025-11-18
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
PROJECT="pgp-live"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
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

log_critical() {
    echo -e "${MAGENTA}🔴 ULTRA-CRITICAL: $1${NC}"
}

# Validation function for hex keys
validate_hex_key() {
    local key=$1
    local expected_length=$2
    local actual_length=${#key}

    if [[ ! "$key" =~ ^[0-9a-fA-F]+$ ]]; then
        log_error "Invalid hex format (must contain only 0-9, a-f, A-F)"
        return 1
    fi

    if [[ $actual_length -ne $expected_length ]]; then
        log_error "Invalid length: expected $expected_length chars, got $actual_length chars"
        return 1
    fi

    return 0
}

# Header
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Phase 2: Security Secrets Creation"
echo "  Project: $PROJECT"
echo "  Secrets: 10 (Signing Keys + Wallet + Webhooks)"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

log_critical "This script handles ULTRA-SENSITIVE cryptographic secrets"
log_warning "All values are STATIC (cannot hot-reload without service restart)"
log_warning "Ensure secure environment before proceeding"
echo ""

read -p "Are you in a secure environment? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    log_error "Aborted by user"
    exit 1
fi

# Set active project
gcloud config set project "$PROJECT"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  1. Signing & Encryption Keys (5 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

log_info "Generating cryptographic signing keys (64-char hex)"
log_warning "These keys are STATIC - rotation requires planned downtime"
echo ""

# 1.1 SUCCESS_URL_SIGNING_KEY
log_info "Creating SUCCESS_URL_SIGNING_KEY"
if gcloud secrets describe SUCCESS_URL_SIGNING_KEY --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'SUCCESS_URL_SIGNING_KEY' already exists, skipping"
else
    SUCCESS_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo -n "$SUCCESS_KEY" | gcloud secrets create SUCCESS_URL_SIGNING_KEY \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: SUCCESS_URL_SIGNING_KEY (64-char hex)"
    log_info "Preview: ${SUCCESS_KEY:0:8}...${SUCCESS_KEY: -8}"
fi

# 1.2 TPS_HOSTPAY_SIGNING_KEY
log_info "Creating TPS_HOSTPAY_SIGNING_KEY"
if gcloud secrets describe TPS_HOSTPAY_SIGNING_KEY --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'TPS_HOSTPAY_SIGNING_KEY' already exists, skipping"
else
    TPS_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo -n "$TPS_KEY" | gcloud secrets create TPS_HOSTPAY_SIGNING_KEY \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: TPS_HOSTPAY_SIGNING_KEY (64-char hex)"
    log_info "Preview: ${TPS_KEY:0:8}...${TPS_KEY: -8}"
fi

# 1.3 JWT_SECRET_KEY
log_info "Creating JWT_SECRET_KEY"
if gcloud secrets describe JWT_SECRET_KEY --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'JWT_SECRET_KEY' already exists, skipping"
else
    JWT_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo -n "$JWT_KEY" | gcloud secrets create JWT_SECRET_KEY \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: JWT_SECRET_KEY (64-char hex)"
    log_info "Preview: ${JWT_KEY:0:8}...${JWT_KEY: -8}"
fi

# 1.4 SIGNUP_SECRET_KEY
log_info "Creating SIGNUP_SECRET_KEY"
if gcloud secrets describe SIGNUP_SECRET_KEY --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'SIGNUP_SECRET_KEY' already exists, skipping"
else
    SIGNUP_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo -n "$SIGNUP_KEY" | gcloud secrets create SIGNUP_SECRET_KEY \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: SIGNUP_SECRET_KEY (64-char hex)"
    log_info "Preview: ${SIGNUP_KEY:0:8}...${SIGNUP_KEY: -8}"
fi

# 1.5 PGP_INTERNAL_SIGNING_KEY
log_info "Creating PGP_INTERNAL_SIGNING_KEY"
if gcloud secrets describe PGP_INTERNAL_SIGNING_KEY --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'PGP_INTERNAL_SIGNING_KEY' already exists, skipping"
else
    INTERNAL_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo -n "$INTERNAL_KEY" | gcloud secrets create PGP_INTERNAL_SIGNING_KEY \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: PGP_INTERNAL_SIGNING_KEY (64-char hex)"
    log_info "Preview: ${INTERNAL_KEY:0:8}...${INTERNAL_KEY: -8}"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  2. Wallet & Blockchain Secrets (3 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

log_critical "Wallet Private Key - CONTROLS ALL FUNDS"
log_warning "This key must be migrated from telepay-459221 securely"
log_warning "NEVER log, print, or share this value"
echo ""

# 2.1 HOST_WALLET_PRIVATE_KEY
if gcloud secrets describe HOST_WALLET_PRIVATE_KEY --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'HOST_WALLET_PRIVATE_KEY' already exists, skipping"
else
    echo ""
    log_critical "Enter wallet private key (64-char hex, input hidden)"
    read -sp "HOST_WALLET_PRIVATE_KEY: " WALLET_KEY
    echo ""

    # Validate format
    if ! validate_hex_key "$WALLET_KEY" 64; then
        log_error "Invalid wallet private key format"
        exit 1
    fi

    echo -n "$WALLET_KEY" | gcloud secrets create HOST_WALLET_PRIVATE_KEY \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: HOST_WALLET_PRIVATE_KEY (NEVER logged)"

    # Clear variable from memory
    unset WALLET_KEY
fi

# 2.2 HOST_WALLET_ETH_ADDRESS
log_info "Creating HOST_WALLET_ETH_ADDRESS"
if gcloud secrets describe HOST_WALLET_ETH_ADDRESS --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'HOST_WALLET_ETH_ADDRESS' already exists, skipping"
else
    read -p "Enter HOST_WALLET_ETH_ADDRESS (0x...): " ETH_ADDR

    # Basic validation for Ethereum address
    if [[ ! "$ETH_ADDR" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
        log_error "Invalid Ethereum address format (must be 0x followed by 40 hex chars)"
        exit 1
    fi

    echo -n "$ETH_ADDR" | gcloud secrets create HOST_WALLET_ETH_ADDRESS \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: HOST_WALLET_ETH_ADDRESS = $ETH_ADDR"
fi

# 2.3 HOST_WALLET_USDT_ADDRESS
log_info "Creating HOST_WALLET_USDT_ADDRESS"
if gcloud secrets describe HOST_WALLET_USDT_ADDRESS --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'HOST_WALLET_USDT_ADDRESS' already exists, skipping"
else
    log_info "Note: USDT is ERC-20, so address is typically same as ETH address"
    read -p "Enter HOST_WALLET_USDT_ADDRESS (0x..., or press Enter to use ETH address): " USDT_ADDR

    if [[ -z "$USDT_ADDR" ]] && [[ -n "${ETH_ADDR:-}" ]]; then
        USDT_ADDR="$ETH_ADDR"
        log_info "Using ETH address for USDT"
    fi

    # Basic validation for Ethereum address
    if [[ ! "$USDT_ADDR" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
        log_error "Invalid Ethereum address format (must be 0x followed by 40 hex chars)"
        exit 1
    fi

    echo -n "$USDT_ADDR" | gcloud secrets create HOST_WALLET_USDT_ADDRESS \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: HOST_WALLET_USDT_ADDRESS = $USDT_ADDR"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  3. Payment Provider Webhooks (2 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 3.1 NOWPAYMENTS_IPN_SECRET
log_info "Creating NOWPAYMENTS_IPN_SECRET"
if gcloud secrets describe NOWPAYMENTS_IPN_SECRET --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'NOWPAYMENTS_IPN_SECRET' already exists, skipping"
else
    echo ""
    log_warning "Get IPN secret from NOWPayments dashboard:"
    echo "  1. Login: https://account.nowpayments.io/"
    echo "  2. Go to: Settings → API Keys → IPN Secret"
    echo "  3. Copy the 28-character IPN secret"
    echo ""
    read -p "Enter NOWPAYMENTS_IPN_SECRET (28 chars): " NP_IPN

    if [[ ${#NP_IPN} -ne 28 ]]; then
        log_error "Invalid IPN secret length (expected 28 chars, got ${#NP_IPN})"
        exit 1
    fi

    echo -n "$NP_IPN" | gcloud secrets create NOWPAYMENTS_IPN_SECRET \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: NOWPAYMENTS_IPN_SECRET (28 chars)"
fi

# 3.2 TELEGRAM_BOT_API_TOKEN
log_info "Creating TELEGRAM_BOT_API_TOKEN"
if gcloud secrets describe TELEGRAM_BOT_API_TOKEN --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'TELEGRAM_BOT_API_TOKEN' already exists, skipping"
else
    echo ""
    log_info "Get bot token from BotFather:"
    echo "  1. Open Telegram and search for @BotFather"
    echo "  2. Send: /mybots → Select your bot → API Token"
    echo "  3. Copy the token (format: 123456789:ABCdef...)"
    echo ""
    read -p "Enter TELEGRAM_BOT_API_TOKEN (46 chars): " TG_TOKEN

    if [[ ${#TG_TOKEN} -ne 46 ]]; then
        log_warning "Expected 46 chars, got ${#TG_TOKEN} (token format may vary)"
    fi

    if [[ ! "$TG_TOKEN" =~ ^[0-9]+:.+$ ]]; then
        log_error "Invalid token format (should be number:hash)"
        exit 1
    fi

    echo -n "$TG_TOKEN" | gcloud secrets create TELEGRAM_BOT_API_TOKEN \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: TELEGRAM_BOT_API_TOKEN"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Phase 2: Security Secrets - COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Summary
log_success "Created 10 security secrets:"
echo "  ✅ Signing & Encryption Keys (5 secrets)"
echo "  ✅ Wallet & Blockchain Secrets (3 secrets)"
echo "  ✅ Payment Provider Webhooks (2 secrets)"
echo ""

log_critical "SECURITY REMINDERS:"
echo "  🔴 NEVER hot-reload signing keys (breaks all tokens)"
echo "  🔴 NEVER log wallet private key"
echo "  🔴 Rotate signing keys every 180 days with planned maintenance"
echo "  🔴 HOST_WALLET_PRIVATE_KEY rotation requires fund migration"
echo ""

log_info "Next steps:"
echo "  1. Run Phase 3: ./create_pgp_live_secrets_phase3_apis.sh"
echo "  2. Verify all secrets: ./verify_pgp_live_secrets.sh"
echo ""

# List all created secrets
log_info "Verifying created security secrets..."
gcloud secrets list --project="$PROJECT" --filter="name:SUCCESS_URL_SIGNING_KEY OR name:TPS_HOSTPAY_SIGNING_KEY OR name:JWT_SECRET_KEY OR name:SIGNUP_SECRET_KEY OR name:PGP_INTERNAL_SIGNING_KEY OR name:HOST_WALLET_PRIVATE_KEY OR name:HOST_WALLET_ETH_ADDRESS OR name:HOST_WALLET_USDT_ADDRESS OR name:NOWPAYMENTS_IPN_SECRET OR name:TELEGRAM_BOT_API_TOKEN"

echo ""
log_success "Phase 2 deployment completed successfully! 🎉"
