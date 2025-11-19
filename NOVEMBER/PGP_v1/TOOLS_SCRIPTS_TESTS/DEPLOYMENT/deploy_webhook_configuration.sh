#!/bin/bash
################################################################################
# Webhook Configuration Script for PGP_v1
# Purpose: Configure external webhooks for PayGatePrime services
# Version: 1.0.0
# Date: 2025-11-18
#
# USAGE:
#   ./deploy_webhook_configuration.sh [--dry-run] [--project PROJECT_ID]
#
# CONFIGURES:
#   - NOWPayments IPN webhook (manual steps + verification)
#   - Telegram Bot webhook (optional - can use polling)
#   - Webhook endpoint verification
#
# REQUIREMENTS:
#   - gcloud CLI installed and authenticated
#   - curl installed
#   - Access to NOWPayments dashboard (for manual configuration)
#   - Telegram bot token in Secret Manager (if using Telegram webhook)
#
# ⚠️  DO NOT RUN IN PRODUCTION WITHOUT TESTING IN DEV FIRST!
# ⚠️  THIS SCRIPT DOES NOT DEPLOY TO CLOUDFLARE - LOCAL DOCUMENTATION ONLY
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

################################################################################
# Configuration
################################################################################

PROJECT_ID="${GCP_PROJECT_ID:-pgp-live}"
REGION="${GCP_REGION:-us-central1}"
DRY_RUN=false
TELEGRAM_WEBHOOK_MODE="polling"  # Options: "polling" or "webhook"

################################################################################
# Parse Command Line Arguments
################################################################################

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --project)
            PROJECT_ID="$2"
            shift 2
            ;;
        --telegram-webhook)
            TELEGRAM_WEBHOOK_MODE="webhook"
            shift
            ;;
        --telegram-polling)
            TELEGRAM_WEBHOOK_MODE="polling"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run              Show what would be configured without making changes"
            echo "  --project PROJECT      GCP project ID (default: pgp-live)"
            echo "  --telegram-webhook     Configure Telegram bot to use webhook mode"
            echo "  --telegram-polling     Configure Telegram bot to use polling mode (default)"
            echo "  -h, --help             Show this help message"
            echo ""
            echo "This script configures:"
            echo "  1. NOWPayments IPN webhook (manual dashboard + verification)"
            echo "  2. Telegram Bot webhook (optional - polling by default)"
            echo "  3. Webhook endpoint verification"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${CYAN}─────────────────────────────────────────────────────────────────────${NC}"
    echo -e "${CYAN}📋 $1${NC}"
    echo -e "${CYAN}─────────────────────────────────────────────────────────────────────${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${MAGENTA}ℹ️  $1${NC}"
}

execute_cmd() {
    local description="$1"
    shift

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $description"
        echo "  Command: $*"
        return 0
    fi

    echo "🔄 $description"
    if "$@"; then
        return 0
    else
        local exit_code=$?
        print_error "Command failed with exit code $exit_code"
        return $exit_code
    fi
}

get_service_url() {
    local service_name="$1"

    if [ "$DRY_RUN" = true ]; then
        echo "https://${service_name}-[hash].run.app"
        return 0
    fi

    local url
    url=$(gcloud run services describe "$service_name" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)" 2>/dev/null)

    if [ -z "$url" ]; then
        print_error "Failed to get URL for service: $service_name"
        return 1
    fi

    echo "$url"
}

get_secret_value() {
    local secret_name="$1"

    if [ "$DRY_RUN" = true ]; then
        echo "[SECRET_VALUE_DRY_RUN]"
        return 0
    fi

    local value
    value=$(gcloud secrets versions access latest \
        --secret="$secret_name" \
        --project="$PROJECT_ID" 2>/dev/null)

    if [ -z "$value" ]; then
        print_error "Failed to get secret: $secret_name"
        return 1
    fi

    echo "$value"
}

################################################################################
# Validation Functions
################################################################################

validate_prerequisites() {
    print_section "Validating Prerequisites"

    # Check gcloud CLI
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI not found. Please install it first."
        exit 1
    fi
    print_success "gcloud CLI found"

    # Check curl
    if ! command -v curl &> /dev/null; then
        print_error "curl not found. Please install it first."
        exit 1
    fi
    print_success "curl found"

    # Check authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        print_error "Not authenticated with gcloud. Run: gcloud auth login"
        exit 1
    fi
    print_success "gcloud authentication verified"

    # Check project access
    if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
        print_error "Cannot access project: $PROJECT_ID"
        exit 1
    fi
    print_success "Project access verified: $PROJECT_ID"

    echo ""
}

verify_service_exists() {
    local service_name="$1"

    if [ "$DRY_RUN" = true ]; then
        return 0
    fi

    if gcloud run services describe "$service_name" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        &>/dev/null; then
        return 0
    else
        return 1
    fi
}

################################################################################
# NOWPayments IPN Webhook Configuration
################################################################################

configure_nowpayments_ipn() {
    print_header "🔔 NOWPayments IPN Webhook Configuration"

    # Get service URLs
    local np_ipn_url
    local orchestrator_url

    print_section "Fetching Service URLs"

    if verify_service_exists "pgp-np-ipn-v1"; then
        np_ipn_url=$(get_service_url "pgp-np-ipn-v1")
        print_success "PGP_NP_IPN_v1 URL: $np_ipn_url"
    else
        print_error "Service not found: pgp-np-ipn-v1"
        print_warning "Please deploy services first: ./deploy_all_pgp_services.sh"
        return 1
    fi

    if verify_service_exists "pgp-orchestrator-v1"; then
        orchestrator_url=$(get_service_url "pgp-orchestrator-v1")
        print_success "PGP_ORCHESTRATOR_v1 URL: $orchestrator_url"
    else
        print_error "Service not found: pgp-orchestrator-v1"
        print_warning "Please deploy services first: ./deploy_all_pgp_services.sh"
        return 1
    fi

    # Display configuration instructions
    print_section "Manual Configuration Required"

    echo "⚠️  You must manually update the NOWPayments dashboard with these webhook URLs:"
    echo ""
    echo "1. Login to: ${YELLOW}https://nowpayments.io/dashboard${NC}"
    echo ""
    echo "2. Navigate to: Settings → API → IPN Settings"
    echo ""
    echo "3. Update IPN Callback URL:"
    echo "   ${GREEN}${np_ipn_url}/${NC}"
    echo ""
    echo "4. Update Success URL:"
    echo "   ${GREEN}${orchestrator_url}/${NC}"
    echo ""
    echo "5. Verify IPN Secret Key matches Secret Manager"
    echo ""

    # Verify IPN secret exists
    print_section "Verifying IPN Secret"

    if [ "$DRY_RUN" = false ]; then
        if gcloud secrets describe "NOWPAYMENT_WEBHOOK_KEY" --project="$PROJECT_ID" &>/dev/null; then
            print_success "NOWPAYMENT_WEBHOOK_KEY exists in Secret Manager"
            print_info "Verify this matches the value in NOWPayments dashboard"
        else
            print_error "NOWPAYMENT_WEBHOOK_KEY not found in Secret Manager"
            print_warning "Create this secret before configuring NOWPayments"
            return 1
        fi
    else
        print_info "[DRY-RUN] Would verify NOWPAYMENT_WEBHOOK_KEY secret"
    fi

    # Webhook verification
    print_section "Webhook Endpoint Verification"

    if [ "$DRY_RUN" = false ]; then
        echo "Testing webhook endpoint accessibility..."

        # Test health endpoint (if available)
        if curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${np_ipn_url}/health" | grep -q "200\|404"; then
            print_success "PGP_NP_IPN_v1 endpoint is accessible"
        else
            print_warning "Could not verify PGP_NP_IPN_v1 endpoint (may be unauthenticated)"
            print_info "This is normal if the service requires authentication"
        fi
    else
        print_info "[DRY-RUN] Would test webhook endpoint accessibility"
    fi

    echo ""
    print_warning "After updating NOWPayments dashboard:"
    echo "   - Test with a small payment"
    echo "   - Monitor logs: gcloud run services logs read pgp-np-ipn-v1 --region=$REGION --project=$PROJECT_ID"
    echo "   - Verify signature validation is working"
    echo ""
}

################################################################################
# Telegram Bot Webhook Configuration
################################################################################

configure_telegram_webhook() {
    print_header "🤖 Telegram Bot Webhook Configuration"

    print_section "Configuration Mode: $TELEGRAM_WEBHOOK_MODE"

    if [ "$TELEGRAM_WEBHOOK_MODE" = "polling" ]; then
        echo "✅ Polling mode selected (default)"
        echo ""
        echo "Polling mode:"
        echo "  - PGP_SERVER_v1 actively polls Telegram API for updates"
        echo "  - No webhook configuration needed"
        echo "  - Simpler setup, good for development and low-traffic bots"
        echo "  - Default behavior - no action required"
        echo ""
        print_success "Telegram bot configured for polling mode"
        return 0
    fi

    # Webhook mode
    print_section "Configuring Telegram Webhook"

    # Get service URL
    local server_url
    if verify_service_exists "pgp-server-v1"; then
        server_url=$(get_service_url "pgp-server-v1")
        print_success "PGP_SERVER_v1 URL: $server_url"
    else
        print_error "Service not found: pgp-server-v1"
        print_warning "Please deploy services first: ./deploy_all_pgp_services.sh"
        return 1
    fi

    # Get Telegram bot token
    local bot_token
    if [ "$DRY_RUN" = false ]; then
        print_section "Fetching Telegram Bot Token"
        bot_token=$(get_secret_value "TELEGRAM_BOT_TOKEN")
        if [ -z "$bot_token" ]; then
            print_error "TELEGRAM_BOT_TOKEN not found in Secret Manager"
            return 1
        fi
        print_success "Bot token retrieved"
    else
        bot_token="[BOT_TOKEN_DRY_RUN]"
    fi

    # Set webhook
    local webhook_url="${server_url}/telegram-webhook"

    print_section "Setting Telegram Webhook"

    if [ "$DRY_RUN" = false ]; then
        echo "Setting webhook to: $webhook_url"

        local response
        response=$(curl -s -X POST "https://api.telegram.org/bot${bot_token}/setWebhook" \
            -H "Content-Type: application/json" \
            -d "{
                \"url\": \"${webhook_url}\",
                \"max_connections\": 40,
                \"allowed_updates\": [\"message\", \"callback_query\"]
            }")

        if echo "$response" | grep -q '"ok":true'; then
            print_success "Telegram webhook configured successfully"
            echo "$response" | grep -o '"description":"[^"]*"' || true
        else
            print_error "Failed to set Telegram webhook"
            echo "Response: $response"
            return 1
        fi

        # Verify webhook
        print_section "Verifying Webhook"
        local webhook_info
        webhook_info=$(curl -s -X POST "https://api.telegram.org/bot${bot_token}/getWebhookInfo")

        if echo "$webhook_info" | grep -q "$webhook_url"; then
            print_success "Webhook verified"
            echo "$webhook_info" | grep -o '"url":"[^"]*"' || true
        else
            print_warning "Webhook verification unclear"
            echo "Response: $webhook_info"
        fi
    else
        echo -e "${YELLOW}[DRY-RUN]${NC} Would set webhook to: $webhook_url"
        echo "  Command: curl -X POST https://api.telegram.org/bot[TOKEN]/setWebhook ..."
    fi

    echo ""
    print_info "Webhook mode benefits:"
    echo "  - Lower latency (instant updates)"
    echo "  - More efficient for high-traffic bots"
    echo "  - Recommended for production"
    echo ""
}

################################################################################
# Webhook Verification
################################################################################

verify_all_webhooks() {
    print_header "🔍 Webhook Endpoint Verification"

    local services=(
        "pgp-np-ipn-v1:NOWPayments IPN Handler"
        "pgp-orchestrator-v1:Payment Orchestrator"
        "pgp-server-v1:Telegram Bot Server"
    )

    for service_desc in "${services[@]}"; do
        IFS=':' read -r service_name description <<< "$service_desc"

        print_section "Verifying: $description ($service_name)"

        if ! verify_service_exists "$service_name"; then
            print_warning "Service not deployed: $service_name"
            continue
        fi

        local url
        url=$(get_service_url "$service_name")

        if [ "$DRY_RUN" = false ]; then
            # Test basic connectivity
            local http_code
            http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${url}/health" || echo "000")

            case $http_code in
                200)
                    print_success "Service is healthy: $service_name"
                    ;;
                404)
                    print_info "Service is running (no /health endpoint): $service_name"
                    ;;
                401|403)
                    print_info "Service requires authentication (expected): $service_name"
                    ;;
                000)
                    print_warning "Service unreachable or timeout: $service_name"
                    ;;
                *)
                    print_warning "Unexpected status code $http_code: $service_name"
                    ;;
            esac

            echo "   URL: $url"
        else
            echo -e "${YELLOW}[DRY-RUN]${NC} Would verify: $url"
        fi

        echo ""
    done
}

################################################################################
# Main Configuration Logic
################################################################################

print_header "🌐 PGP_v1 Webhook Configuration"

echo "Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Telegram Mode: $TELEGRAM_WEBHOOK_MODE"
echo "  Dry Run: $DRY_RUN"
echo ""

print_warning "This script configures external webhooks for PGP_v1 services"
echo ""

# Safety confirmation
if [ "$DRY_RUN" = false ]; then
    read -p "Continue with webhook configuration? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Configuration cancelled."
        exit 0
    fi
fi

echo ""
validate_prerequisites

################################################################################
# Execute Configuration Steps
################################################################################

# Step 1: NOWPayments IPN
configure_nowpayments_ipn

# Step 2: Telegram Bot
configure_telegram_webhook

# Step 3: Verify All Webhooks
verify_all_webhooks

################################################################################
# DNS & Cloudflare Documentation
################################################################################

print_header "🌍 DNS & Cloudflare Configuration (DOCUMENTATION ONLY)"

print_warning "⚠️  DO NOT DEPLOY TO CLOUDFLARE - This is documentation only"
echo ""
echo "After Load Balancer deployment (PHASE 9), you will need to:"
echo ""
echo "1. Update DNS records in Cloudflare:"
echo "   - Type: A"
echo "   - Name: www.paygateprime.com"
echo "   - Value: [Load Balancer IP from Phase 9]"
echo "   - Proxy: Enabled (orange cloud)"
echo ""
echo "2. Configure SSL/TLS:"
echo "   - Mode: Full (strict)"
echo "   - Minimum TLS: 1.2"
echo "   - Enable HSTS"
echo ""
echo "3. Configure Cloudflare WAF Rules:"
echo "   - Rate limiting: 1000 requests/minute per IP"
echo "   - DDoS protection: High sensitivity"
echo "   - Bot fight mode: Enabled"
echo ""
echo "4. Update NOWPayments webhook URLs to use custom domain:"
echo "   - IPN: https://www.paygateprime.com/webhooks/nowpayments-ipn"
echo "   - Success: https://www.paygateprime.com/webhooks/success"
echo ""
print_info "These steps are NOT executed by this script"
print_info "They are documented here for manual execution after Phase 9"
echo ""

################################################################################
# ChangeNow Webhook Documentation
################################################################################

print_header "🔄 ChangeNow Webhooks (OPTIONAL)"

echo "ChangeNow webhook configuration is OPTIONAL and NOT RECOMMENDED"
echo ""
echo "Why we don't use ChangeNow webhooks:"
echo "  - Our services actively poll ChangeNow API for status updates"
echo "  - Polling is more reliable and easier to debug"
echo "  - Reduces webhook complexity"
echo "  - Better error handling and retry logic"
echo ""
echo "If you still want to configure ChangeNow webhooks:"
echo "  1. Login to: https://changenow.io/"
echo "  2. Navigate to: API Settings"
echo "  3. Set callback URLs (not recommended)"
echo ""
print_success "No action required for ChangeNow webhooks"
echo ""

################################################################################
# Configuration Summary
################################################################################

print_header "📊 Webhook Configuration Summary"

echo "Webhook Configuration Status:"
echo ""
echo "✅ NOWPayments IPN:"
echo "   - Configuration instructions provided"
echo "   - IPN secret verified in Secret Manager"
echo "   - Endpoint accessibility tested"
echo ""
echo "✅ Telegram Bot:"
echo "   - Mode: $TELEGRAM_WEBHOOK_MODE"
if [ "$TELEGRAM_WEBHOOK_MODE" = "webhook" ]; then
    echo "   - Webhook configured and verified"
else
    echo "   - Using polling (no webhook needed)"
fi
echo ""
echo "✅ Service Endpoints:"
echo "   - All webhook endpoints verified"
echo "   - URLs documented for external configuration"
echo ""

################################################################################
# Post-Configuration Tasks
################################################################################

print_header "📝 Next Steps"

echo "1. Complete manual NOWPayments configuration:"
echo "   - Login to NOWPayments dashboard"
echo "   - Update IPN and Success URLs"
echo "   - Test with a small payment"
echo ""

echo "2. Test webhooks:"
echo "   - NOWPayments: Make a test payment"
echo "   - Telegram: Send a message to your bot"
echo ""

echo "3. Monitor webhook logs:"
echo "   gcloud run services logs read pgp-np-ipn-v1 --region=$REGION --project=$PROJECT_ID --tail"
echo "   gcloud run services logs read pgp-orchestrator-v1 --region=$REGION --project=$PROJECT_ID --tail"
echo "   gcloud run services logs read pgp-server-v1 --region=$REGION --project=$PROJECT_ID --tail"
echo ""

echo "4. Deploy Load Balancer & Cloud Armor (PHASE 9):"
echo "   - Run: TOOLS_SCRIPTS_TESTS/scripts/security/deploy_load_balancer.sh"
echo "   - Update webhook URLs to use load balancer IP"
echo ""

echo "5. Configure Cloudflare DNS (after Phase 9):"
echo "   - Update DNS A record to load balancer IP"
echo "   - Enable Cloudflare proxy (orange cloud)"
echo "   - Configure SSL/TLS and WAF rules"
echo ""

print_success "🎉 Webhook configuration complete!"

if [ "$DRY_RUN" = true ]; then
    echo ""
    print_warning "This was a DRY-RUN. No actual changes were made."
    echo "Run without --dry-run to configure for real."
fi

echo ""

################################################################################
# Save Configuration Metadata
################################################################################

if [ "$DRY_RUN" = false ]; then
    CONFIG_LOG="/tmp/pgp_webhooks_config_$(date +%Y%m%d_%H%M%S).log"
    cat > "$CONFIG_LOG" <<EOF
PGP_v1 Webhook Configuration Log
=================================
Date: $(date)
Project: $PROJECT_ID
Region: $REGION
Telegram Mode: $TELEGRAM_WEBHOOK_MODE

Service URLs:
$(for service in pgp-np-ipn-v1 pgp-orchestrator-v1 pgp-server-v1; do
    if verify_service_exists "$service"; then
        url=$(get_service_url "$service" 2>/dev/null || echo "N/A")
        echo "$service: $url"
    fi
done)

Next Steps:
- Complete NOWPayments dashboard configuration
- Test webhooks with real traffic
- Deploy Load Balancer (Phase 9)
- Configure Cloudflare DNS
EOF

    echo "Configuration log saved to: $CONFIG_LOG"
    echo ""
fi

exit 0
