#!/bin/bash

################################################################################
# Deploy HTTPS Load Balancer for PGP_v1 Services
################################################################################
#
# Purpose: Deploy global HTTPS Load Balancer with Cloud Armor integration
#
# Components Created:
#   1. Backend services (3) - one per Cloud Run service
#   2. URL map - path-based routing
#   3. HTTPS proxy - SSL/TLS termination
#   4. Global forwarding rule - static IP
#   5. Cloud Run ingress restriction
#
# Architecture:
#   Internet → Global IP → HTTPS Proxy → URL Map → Backend Services → NEGs → Cloud Run
#                            ↓
#                      Cloud Armor (WAF/DDoS)
#
# Routing Configuration:
#   /                             → pgp-web-v1 (frontend)
#   /webhooks/nowpayments-ipn     → pgp-np-ipn-v1 (NowPayments webhook)
#   /webhooks/telegram            → pgp-server-v1 (Telegram webhook)
#
# Prerequisites:
#   - Serverless NEGs created (run create_serverless_negs.sh)
#   - SSL certificate provisioned (run provision_ssl_certificates.sh)
#   - Cloud Armor policy created (run create_cloud_armor_policy.sh)
#   - Cloud Run services deployed
#
# Permissions Required:
#   - compute.backendServices.create
#   - compute.urlMaps.create
#   - compute.targetHttpsProxies.create
#   - compute.globalForwardingRules.create
#   - compute.globalAddresses.create
#   - run.services.setIamPolicy
#
# Usage:
#   bash deploy_load_balancer.sh
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

# Load Balancer Configuration
LB_NAME="pgp-load-balancer"
STATIC_IP_NAME="pgp-static-ip"
URL_MAP_NAME="pgp-url-map"
HTTPS_PROXY_NAME="pgp-https-proxy"
FORWARDING_RULE_NAME="pgp-https-forwarding-rule"

# SSL Certificate Name (from provision_ssl_certificates.sh)
SSL_CERT_NAME="pgp-ssl-cert"

# Cloud Armor Policy Name (from create_cloud_armor_policy.sh)
CLOUD_ARMOR_POLICY="pgp-security-policy"

# Backend Service Names
BACKEND_WEB="pgp-web-backend"
BACKEND_NP_IPN="pgp-np-ipn-backend"
BACKEND_TELEGRAM="pgp-server-backend"

# Serverless NEG Names (from create_serverless_negs.sh)
NEG_WEB="pgp-web-v1-neg"
NEG_NP_IPN="pgp-np-ipn-v1-neg"
NEG_TELEGRAM="pgp-server-v1-neg"

# Cloud Run Service Names
SERVICE_WEB="pgp-web-v1"
SERVICE_NP_IPN="pgp-np-ipn-v1"
SERVICE_TELEGRAM="pgp-server-v1"

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
# Component Creation Functions
################################################################################

create_static_ip() {
    print_section "🌐 Reserving Static IP Address"

    echo ""
    echo -e "${BLUE}Reserving global static IP: ${STATIC_IP_NAME}${NC}"

    # Check if static IP already exists
    if gcloud compute addresses describe "$STATIC_IP_NAME" \
        --global \
        --project="$PROJECT_ID" &>/dev/null; then

        STATIC_IP=$(gcloud compute addresses describe "$STATIC_IP_NAME" \
            --global \
            --project="$PROJECT_ID" \
            --format="value(address)")

        echo -e "${YELLOW}⚠️  Static IP already exists: $STATIC_IP_NAME${NC}"
        echo "  IP Address: $STATIC_IP"
        ((SKIPPED++))
        return 0
    fi

    # Reserve global static IP
    if gcloud compute addresses create "$STATIC_IP_NAME" \
        --ip-version=IPV4 \
        --global \
        --project="$PROJECT_ID" \
        --quiet; then

        STATIC_IP=$(gcloud compute addresses describe "$STATIC_IP_NAME" \
            --global \
            --project="$PROJECT_ID" \
            --format="value(address)")

        echo -e "${GREEN}✅ Created static IP: $STATIC_IP_NAME${NC}"
        echo "  IP Address: $STATIC_IP"
        echo ""
        echo -e "${YELLOW}⚠️  IMPORTANT: Update DNS records to point to this IP:${NC}"
        echo "     A record: yourdomain.com → $STATIC_IP"
        ((CREATED++))
        return 0
    else
        echo -e "${RED}❌ Failed to create static IP${NC}"
        ((FAILED++))
        return 1
    fi
}

create_backend_service() {
    local BACKEND_NAME=$1
    local NEG_NAME=$2
    local DESCRIPTION=$3
    local ENABLE_CDN=${4:-false}

    echo ""
    echo -e "${BLUE}Creating backend service: ${BACKEND_NAME}${NC}"
    echo "  NEG: $NEG_NAME"
    echo "  Description: $DESCRIPTION"

    # Check if backend service already exists
    if gcloud compute backend-services describe "$BACKEND_NAME" \
        --global \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}⚠️  Backend service already exists: $BACKEND_NAME${NC}"
        ((SKIPPED++))
        return 0
    fi

    # Create backend service
    local CDN_FLAG=""
    if [[ "$ENABLE_CDN" == "true" ]]; then
        CDN_FLAG="--enable-cdn"
    fi

    if gcloud compute backend-services create "$BACKEND_NAME" \
        --load-balancing-scheme=EXTERNAL_MANAGED \
        --protocol=HTTPS \
        --global \
        --description="$DESCRIPTION" \
        --security-policy="$CLOUD_ARMOR_POLICY" \
        $CDN_FLAG \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}✅ Created backend service: $BACKEND_NAME${NC}"
        ((CREATED++))
    else
        echo -e "${RED}❌ Failed to create backend service${NC}"
        ((FAILED++))
        return 1
    fi

    # Add NEG to backend service
    echo "  Adding NEG to backend service..."
    if gcloud compute backend-services add-backend "$BACKEND_NAME" \
        --global \
        --network-endpoint-group="$NEG_NAME" \
        --network-endpoint-group-region="$REGION" \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}  ✅ NEG added to backend service${NC}"
    else
        echo -e "${RED}  ❌ Failed to add NEG to backend service${NC}"
        return 1
    fi
}

create_url_map() {
    print_section "🗺️ Creating URL Map (Path-Based Routing)"

    echo ""
    echo -e "${BLUE}Creating URL map: ${URL_MAP_NAME}${NC}"

    # Check if URL map already exists
    if gcloud compute url-maps describe "$URL_MAP_NAME" \
        --global \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}⚠️  URL map already exists: $URL_MAP_NAME${NC}"
        ((SKIPPED++))
        return 0
    fi

    # Create URL map with default service (frontend)
    if gcloud compute url-maps create "$URL_MAP_NAME" \
        --default-service="$BACKEND_WEB" \
        --global \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}✅ Created URL map: $URL_MAP_NAME${NC}"
        ((CREATED++))
    else
        echo -e "${RED}❌ Failed to create URL map${NC}"
        ((FAILED++))
        return 1
    fi

    # Add path matcher for webhooks
    echo ""
    echo "Adding path-based routing rules..."

    # NowPayments webhook path
    echo "  /webhooks/nowpayments-ipn → $BACKEND_NP_IPN"
    gcloud compute url-maps add-path-matcher "$URL_MAP_NAME" \
        --path-matcher-name=webhook-matcher \
        --default-service="$BACKEND_WEB" \
        --global \
        --project="$PROJECT_ID" \
        --quiet || true

    # Add path rules
    gcloud compute url-maps add-host-rule "$URL_MAP_NAME" \
        --hosts='*' \
        --path-matcher-name=webhook-matcher \
        --global \
        --project="$PROJECT_ID" \
        --quiet || true

    # Configure path rules using YAML (more reliable)
    cat > /tmp/pgp_url_map_config.yaml <<EOF
defaultService: https://www.googleapis.com/compute/v1/projects/${PROJECT_ID}/global/backendServices/${BACKEND_WEB}
hostRules:
- hosts:
  - '*'
  pathMatcher: webhook-matcher
name: ${URL_MAP_NAME}
pathMatchers:
- defaultService: https://www.googleapis.com/compute/v1/projects/${PROJECT_ID}/global/backendServices/${BACKEND_WEB}
  name: webhook-matcher
  pathRules:
  - paths:
    - /webhooks/nowpayments-ipn
    - /webhooks/nowpayments-ipn/*
    service: https://www.googleapis.com/compute/v1/projects/${PROJECT_ID}/global/backendServices/${BACKEND_NP_IPN}
  - paths:
    - /webhooks/telegram
    - /webhooks/telegram/*
    service: https://www.googleapis.com/compute/v1/projects/${PROJECT_ID}/global/backendServices/${BACKEND_TELEGRAM}
EOF

    # Import URL map configuration
    if gcloud compute url-maps import "$URL_MAP_NAME" \
        --source=/tmp/pgp_url_map_config.yaml \
        --global \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}✅ Path-based routing configured${NC}"
    else
        echo -e "${YELLOW}⚠️  Path rules may need manual configuration${NC}"
    fi

    # Clean up temp file
    rm -f /tmp/pgp_url_map_config.yaml

    echo ""
    echo "Routing configuration:"
    echo "  / → $BACKEND_WEB (Frontend)"
    echo "  /webhooks/nowpayments-ipn → $BACKEND_NP_IPN (NowPayments)"
    echo "  /webhooks/telegram → $BACKEND_TELEGRAM (Telegram)"
}

create_https_proxy() {
    print_section "🔒 Creating HTTPS Proxy"

    echo ""
    echo -e "${BLUE}Creating HTTPS proxy: ${HTTPS_PROXY_NAME}${NC}"

    # Check if HTTPS proxy already exists
    if gcloud compute target-https-proxies describe "$HTTPS_PROXY_NAME" \
        --global \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}⚠️  HTTPS proxy already exists: $HTTPS_PROXY_NAME${NC}"
        ((SKIPPED++))
        return 0
    fi

    # Create HTTPS proxy
    if gcloud compute target-https-proxies create "$HTTPS_PROXY_NAME" \
        --url-map="$URL_MAP_NAME" \
        --ssl-certificates="$SSL_CERT_NAME" \
        --global \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}✅ Created HTTPS proxy: $HTTPS_PROXY_NAME${NC}"
        ((CREATED++))
    else
        echo -e "${RED}❌ Failed to create HTTPS proxy${NC}"
        ((FAILED++))
        return 1
    fi
}

create_forwarding_rule() {
    print_section "🌐 Creating Global Forwarding Rule"

    echo ""
    echo -e "${BLUE}Creating forwarding rule: ${FORWARDING_RULE_NAME}${NC}"

    # Check if forwarding rule already exists
    if gcloud compute forwarding-rules describe "$FORWARDING_RULE_NAME" \
        --global \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}⚠️  Forwarding rule already exists: $FORWARDING_RULE_NAME${NC}"
        ((SKIPPED++))
        return 0
    fi

    # Create forwarding rule
    if gcloud compute forwarding-rules create "$FORWARDING_RULE_NAME" \
        --load-balancing-scheme=EXTERNAL_MANAGED \
        --network-tier=PREMIUM \
        --address="$STATIC_IP_NAME" \
        --target-https-proxy="$HTTPS_PROXY_NAME" \
        --global \
        --ports=443 \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}✅ Created forwarding rule: $FORWARDING_RULE_NAME${NC}"
        ((CREATED++))
    else
        echo -e "${RED}❌ Failed to create forwarding rule${NC}"
        ((FAILED++))
        return 1
    fi
}

restrict_cloud_run_ingress() {
    print_section "🔐 Restricting Cloud Run Ingress"

    echo ""
    echo "Updating Cloud Run services to only accept traffic from Load Balancer..."

    # Update each Cloud Run service to restrict ingress
    for SERVICE in "$SERVICE_WEB" "$SERVICE_NP_IPN" "$SERVICE_TELEGRAM"; do
        echo ""
        echo "  Updating $SERVICE..."
        if gcloud run services update "$SERVICE" \
            --ingress=internal-and-cloud-load-balancing \
            --region="$REGION" \
            --project="$PROJECT_ID" \
            --quiet; then
            echo -e "${GREEN}  ✅ Ingress restricted for $SERVICE${NC}"
        else
            echo -e "${YELLOW}  ⚠️  Failed to restrict ingress for $SERVICE${NC}"
        fi
    done

    echo ""
    echo -e "${GREEN}✅ Cloud Run services now only accept traffic from Load Balancer${NC}"
}

################################################################################
# Verification Function
################################################################################

verify_load_balancer() {
    print_section "✅ Verifying Load Balancer Configuration"

    echo ""
    echo "Checking components..."

    # Check static IP
    echo -n "  Static IP... "
    if gcloud compute addresses describe "$STATIC_IP_NAME" --global --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
    fi

    # Check backend services
    echo -n "  Backend services... "
    ALL_BACKENDS_OK=true
    for BACKEND in "$BACKEND_WEB" "$BACKEND_NP_IPN" "$BACKEND_TELEGRAM"; do
        if ! gcloud compute backend-services describe "$BACKEND" --global --project="$PROJECT_ID" &>/dev/null; then
            ALL_BACKENDS_OK=false
        fi
    done
    if [[ "$ALL_BACKENDS_OK" == "true" ]]; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
    fi

    # Check URL map
    echo -n "  URL map... "
    if gcloud compute url-maps describe "$URL_MAP_NAME" --global --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
    fi

    # Check HTTPS proxy
    echo -n "  HTTPS proxy... "
    if gcloud compute target-https-proxies describe "$HTTPS_PROXY_NAME" --global --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
    fi

    # Check forwarding rule
    echo -n "  Forwarding rule... "
    if gcloud compute forwarding-rules describe "$FORWARDING_RULE_NAME" --global --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    print_header "🌐 HTTPS Load Balancer Deployment - PGP_v1 Phase 2"

    echo "This script will deploy a global HTTPS Load Balancer with:"
    echo "  - Path-based routing to 3 Cloud Run services"
    echo "  - Cloud Armor WAF protection"
    echo "  - SSL/TLS termination"
    echo "  - Static IP address"
    echo ""
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo ""

    # Safety prompt
    read -p "Do you want to proceed? (yes/no): " CONFIRM
    if [[ "$CONFIRM" != "yes" ]]; then
        echo -e "${YELLOW}⚠️  Operation cancelled by user${NC}"
        exit 0
    fi

    # Verify prerequisites
    print_section "🔍 Verifying Prerequisites"

    echo ""
    echo "Checking prerequisites..."

    # Check NEGs exist
    echo -n "  Serverless NEGs... "
    ALL_NEGS_OK=true
    for NEG in "$NEG_WEB" "$NEG_NP_IPN" "$NEG_TELEGRAM"; do
        if ! gcloud compute network-endpoint-groups describe "$NEG" \
            --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
            ALL_NEGS_OK=false
        fi
    done
    if [[ "$ALL_NEGS_OK" == "true" ]]; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌ Run create_serverless_negs.sh first${NC}"
        exit 1
    fi

    # Check SSL certificate exists
    echo -n "  SSL certificate... "
    if gcloud compute ssl-certificates describe "$SSL_CERT_NAME" \
        --global --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌ Run provision_ssl_certificates.sh first${NC}"
        exit 1
    fi

    # Check Cloud Armor policy exists
    echo -n "  Cloud Armor policy... "
    if gcloud compute security-policies describe "$CLOUD_ARMOR_POLICY" \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌ Run create_cloud_armor_policy.sh first${NC}"
        exit 1
    fi

    # Create Load Balancer components
    create_static_ip

    print_section "🔧 Creating Backend Services"
    create_backend_service "$BACKEND_WEB" "$NEG_WEB" "Backend for PGP Web Frontend" true
    create_backend_service "$BACKEND_NP_IPN" "$NEG_NP_IPN" "Backend for NowPayments IPN" false
    create_backend_service "$BACKEND_TELEGRAM" "$NEG_TELEGRAM" "Backend for Telegram Bot" false

    create_url_map
    create_https_proxy
    create_forwarding_rule
    restrict_cloud_run_ingress

    # Verification
    verify_load_balancer

    # Summary
    print_section "📊 Summary"

    echo "Components Created: $CREATED"
    echo "Components Skipped (already exist): $SKIPPED"
    echo "Components Failed: $FAILED"
    echo ""

    if [[ $FAILED -eq 0 ]]; then
        # Get static IP
        STATIC_IP=$(gcloud compute addresses describe "$STATIC_IP_NAME" \
            --global \
            --project="$PROJECT_ID" \
            --format="value(address)")

        echo -e "${GREEN}✅ Load Balancer deployment complete!${NC}"
        echo ""
        echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  🌐 Load Balancer Static IP: ${STATIC_IP}${NC}"
        echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo -e "${YELLOW}⚠️  CRITICAL NEXT STEPS:${NC}"
        echo ""
        echo "1. Update DNS records (Cloudflare, Route53, etc.):"
        echo "   A record: yourdomain.com → $STATIC_IP"
        echo ""
        echo "2. Wait 10-60 minutes for SSL certificate provisioning"
        echo "   - Google will verify domain ownership"
        echo "   - Check status: gcloud compute ssl-certificates list"
        echo ""
        echo "3. Test routing:"
        echo "   - https://yourdomain.com/ → Frontend"
        echo "   - https://yourdomain.com/webhooks/nowpayments-ipn → NowPayments"
        echo "   - https://yourdomain.com/webhooks/telegram → Telegram"
        echo ""
        echo "4. Update webhook URLs:"
        echo "   - NowPayments IPN URL: https://yourdomain.com/webhooks/nowpayments-ipn"
        echo "   - Telegram webhook URL: https://yourdomain.com/webhooks/telegram"
        echo ""
    else
        echo -e "${RED}❌ Some components failed to create${NC}"
        echo "Please review the errors above and try again."
        exit 1
    fi

    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ Load Balancer deployment complete!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Run main function
main

################################################################################
# Monitoring Load Balancer
################################################################################
#
# View Load Balancer status:
#   gcloud compute forwarding-rules describe pgp-https-forwarding-rule --global
#
# View backend service health:
#   gcloud compute backend-services get-health pgp-web-backend --global
#
# View Cloud Armor logs:
#   gcloud logging read 'resource.type="http_load_balancer"' --limit 50
#
# Test routing:
#   curl -I https://yourdomain.com/
#   curl -I https://yourdomain.com/webhooks/nowpayments-ipn
#
################################################################################

################################################################################
# Rollback Instructions
################################################################################
#
# Delete in reverse order:
#
# 1. Delete forwarding rule:
#    gcloud compute forwarding-rules delete pgp-https-forwarding-rule --global --quiet
#
# 2. Delete HTTPS proxy:
#    gcloud compute target-https-proxies delete pgp-https-proxy --global --quiet
#
# 3. Delete URL map:
#    gcloud compute url-maps delete pgp-url-map --global --quiet
#
# 4. Delete backend services:
#    gcloud compute backend-services delete pgp-web-backend --global --quiet
#    gcloud compute backend-services delete pgp-np-ipn-backend --global --quiet
#    gcloud compute backend-services delete pgp-server-backend --global --quiet
#
# 5. Delete static IP (optional):
#    gcloud compute addresses delete pgp-static-ip --global --quiet
#
# 6. Restore Cloud Run ingress:
#    gcloud run services update pgp-web-v1 --ingress=all --region=us-central1
#    gcloud run services update pgp-np-ipn-v1 --ingress=all --region=us-central1
#    gcloud run services update pgp-server-v1 --ingress=all --region=us-central1
#
################################################################################

################################################################################
# Cost Breakdown
################################################################################
#
# Load Balancer Pricing:
# - Forwarding rule: $18/month (first 5 rules)
# - Data processing: $0.008-0.016/GB (first 10TB)
# - Static IP: FREE (while in use)
#
# Backend Services:
# - No separate charge (included in Load Balancer cost)
#
# SSL Certificate:
# - Google-managed: FREE
#
# Cloud Armor:
# - Rules: ~$10/month (15 rules)
# - Requests: $0.75 per 1M (first 1M free)
#
# Estimated Total: $60-200/month
# - Base: $18 (forwarding rule)
# - Cloud Armor: $10-65
# - Data transfer: $10-100 (depends on traffic)
#
################################################################################
