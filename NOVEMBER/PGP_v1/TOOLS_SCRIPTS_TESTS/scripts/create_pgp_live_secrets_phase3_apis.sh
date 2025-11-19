#!/bin/bash
################################################################################
# create_pgp_live_secrets_phase3_apis.sh
#
# Phase 3: External API Secrets (5 secrets)
# Creates API keys for external providers (NOWPayments, ChangeNow, SendGrid, Ethereum RPC)
#
# Prerequisites:
# - Phase 1 & 2 completed
# - API keys from external providers
#
# Usage:
#   ./create_pgp_live_secrets_phase3_apis.sh
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
echo "  Phase 3: External API Secrets Creation"
echo "  Project: $PROJECT"
echo "  Secrets: 5 (Payment + Exchange + Email + Blockchain)"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Set active project
gcloud config set project "$PROJECT"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  1. NOWPayments API (1 secret)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 1.1 NOWPAYMENTS_API_KEY
log_info "Creating NOWPAYMENTS_API_KEY"
if gcloud secrets describe NOWPAYMENTS_API_KEY --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'NOWPAYMENTS_API_KEY' already exists, skipping"
else
    echo ""
    log_info "Get API key from NOWPayments dashboard:"
    echo "  1. Login: https://account.nowpayments.io/"
    echo "  2. Go to: Settings → API Keys"
    echo "  3. Copy the API key (27 characters)"
    echo ""
    read -p "Enter NOWPAYMENTS_API_KEY (27 chars): " NP_API

    if [[ ${#NP_API} -ne 27 ]]; then
        log_warning "Expected 27 chars, got ${#NP_API} (format may vary)"
    fi

    echo -n "$NP_API" | gcloud secrets create NOWPAYMENTS_API_KEY \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: NOWPAYMENTS_API_KEY (HOT-RELOADABLE)"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  2. ChangeNow Exchange API (1 secret)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 2.1 CHANGENOW_API_KEY
log_info "Creating CHANGENOW_API_KEY"
if gcloud secrets describe CHANGENOW_API_KEY --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'CHANGENOW_API_KEY' already exists, skipping"
else
    echo ""
    log_info "Get API key from ChangeNow:"
    echo "  1. Login: https://changenow.io/accounts/api"
    echo "  2. Generate API key (Standard API)"
    echo "  3. Copy the 64-character hex key"
    echo ""
    read -p "Enter CHANGENOW_API_KEY (64-char hex): " CN_API

    if [[ ${#CN_API} -ne 64 ]]; then
        log_error "Invalid key length (expected 64 chars, got ${#CN_API})"
        exit 1
    fi

    if [[ ! "$CN_API" =~ ^[0-9a-fA-F]+$ ]]; then
        log_error "Invalid hex format (must contain only 0-9, a-f, A-F)"
        exit 1
    fi

    echo -n "$CN_API" | gcloud secrets create CHANGENOW_API_KEY \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: CHANGENOW_API_KEY (HOT-RELOADABLE)"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  3. SendGrid Email API (1 secret)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 3.1 SENDGRID_API_KEY
log_info "Creating SENDGRID_API_KEY"
if gcloud secrets describe SENDGRID_API_KEY --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'SENDGRID_API_KEY' already exists, skipping"
else
    echo ""
    log_info "Get API key from SendGrid:"
    echo "  1. Login: https://app.sendgrid.com/"
    echo "  2. Go to: Settings → API Keys → Create API Key"
    echo "  3. Choose 'Full Access' or 'Mail Send' permission"
    echo "  4. Copy the key (format: SG.xxx, ~69 chars)"
    echo ""
    read -p "Enter SENDGRID_API_KEY: " SG_API

    if [[ ! "$SG_API" =~ ^SG\. ]]; then
        log_warning "Expected format: SG.xxx (key may not start with SG.)"
    fi

    echo -n "$SG_API" | gcloud secrets create SENDGRID_API_KEY \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: SENDGRID_API_KEY (HOT-RELOADABLE)"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  4. Ethereum RPC (Alchemy/Infura) (2 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 4.1 ETHEREUM_RPC_URL
log_info "Creating ETHEREUM_RPC_URL"
if gcloud secrets describe ETHEREUM_RPC_URL --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'ETHEREUM_RPC_URL' already exists, skipping"
else
    echo ""
    log_info "Get Ethereum RPC URL (Alchemy or Infura):"
    echo ""
    echo "  Option 1 - Alchemy (Recommended):"
    echo "    1. Login: https://dashboard.alchemy.com/"
    echo "    2. Create App: Network=Ethereum Mainnet"
    echo "    3. Copy HTTPS endpoint URL"
    echo "    Format: https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"
    echo ""
    echo "  Option 2 - Infura:"
    echo "    1. Login: https://infura.io/"
    echo "    2. Create Project: Network=Ethereum Mainnet"
    echo "    3. Copy HTTPS endpoint URL"
    echo "    Format: https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
    echo ""
    read -p "Enter ETHEREUM_RPC_URL (full URL): " ETH_RPC

    if [[ ! "$ETH_RPC" =~ ^https:// ]]; then
        log_error "Invalid URL format (must start with https://)"
        exit 1
    fi

    echo -n "$ETH_RPC" | gcloud secrets create ETHEREUM_RPC_URL \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: ETHEREUM_RPC_URL (HOT-RELOADABLE)"
fi

# 4.2 ETHEREUM_RPC_URL_API
log_info "Creating ETHEREUM_RPC_URL_API"
if gcloud secrets describe ETHEREUM_RPC_URL_API --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'ETHEREUM_RPC_URL_API' already exists, skipping"
else
    echo ""
    log_info "Extract API key from RPC URL:"
    echo "  - Alchemy: Key after /v2/ (32 chars)"
    echo "  - Infura: Project ID after /v3/ (32 chars)"
    echo ""
    read -p "Enter ETHEREUM_RPC_URL_API (API key only, 32 chars): " ETH_API

    if [[ ${#ETH_API} -ne 32 ]]; then
        log_warning "Expected 32 chars, got ${#ETH_API} (length may vary by provider)"
    fi

    echo -n "$ETH_API" | gcloud secrets create ETHEREUM_RPC_URL_API \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: ETHEREUM_RPC_URL_API (HOT-RELOADABLE)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Phase 3: External API Secrets - COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Summary
log_success "Created 5 external API secrets:"
echo "  ✅ NOWPayments API (1 secret)"
echo "  ✅ ChangeNow Exchange API (1 secret)"
echo "  ✅ SendGrid Email API (1 secret)"
echo "  ✅ Ethereum RPC (Alchemy/Infura) (2 secrets)"
echo ""

log_info "All Phase 3 secrets are HOT-RELOADABLE (zero-downtime rotation)"
echo ""

log_info "Next steps:"
echo "  1. Run Phase 4: ./create_pgp_live_secrets_phase4_config.sh"
echo "  2. Deploy Cloud Run services to get service URLs"
echo "  3. Run Phase 5: ./create_pgp_live_secrets_phase5_service_urls.sh"
echo ""

# List all created secrets
log_info "Verifying created API secrets..."
gcloud secrets list --project="$PROJECT" --filter="name:NOWPAYMENTS_API_KEY OR name:CHANGENOW_API_KEY OR name:SENDGRID_API_KEY OR name:ETHEREUM_RPC_URL OR name:ETHEREUM_RPC_URL_API"

echo ""
log_success "Phase 3 deployment completed successfully! 🎉"
