#!/bin/bash

################################################################################
# Provision SSL/TLS Certificates for PGP_v1 Load Balancer
################################################################################
#
# Purpose: Create Google-managed SSL certificates for HTTPS Load Balancer
#
# Certificate Types:
#   1. Primary domain certificate (e.g., paygateprime.com)
#   2. Wildcard certificate (optional, e.g., *.paygateprime.com)
#
# Features:
#   - Google-managed certificates (automatic renewal)
#   - FREE (no cost for Google-managed certs)
#   - Automatic renewal (no manual intervention)
#   - Supports multiple domains per certificate
#
# Prerequisites:
#   - Domain name registered and DNS accessible
#   - DNS configured to point to Load Balancer IP (can be done after)
#   - gcloud CLI authenticated with sufficient permissions
#   - Compute Engine API enabled
#
# Permissions Required:
#   - compute.sslCertificates.create
#   - compute.sslCertificates.get
#
# DNS Configuration Required (AFTER Load Balancer deployment):
#   - A record: paygateprime.com → Load Balancer IP
#   - CNAME (optional): www.paygateprime.com → paygateprime.com
#
# Usage:
#   bash provision_ssl_certificates.sh
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

# Domain configuration (CUSTOMIZE THESE)
PRIMARY_DOMAIN="paygateprime.com"           # Replace with your domain
WWW_DOMAIN="www.paygateprime.com"           # Optional: www subdomain
API_SUBDOMAIN="api.paygateprime.com"        # Optional: API subdomain

# Certificate names
PRIMARY_CERT_NAME="pgp-ssl-cert"
WILDCARD_CERT_NAME="pgp-wildcard-ssl-cert"

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
# SSL Certificate Creation Function
################################################################################

create_ssl_certificate() {
    local CERT_NAME=$1
    shift  # Remaining arguments are domains
    local DOMAINS=("$@")

    echo ""
    echo -e "${BLUE}Creating SSL Certificate: ${CERT_NAME}${NC}"
    echo "  Domains:"
    for domain in "${DOMAINS[@]}"; do
        echo "    - $domain"
    done

    # Check if certificate already exists
    if gcloud compute ssl-certificates describe "$CERT_NAME" \
        --global \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}⚠️  SSL certificate already exists: $CERT_NAME${NC}"

        # Show existing certificate details
        echo ""
        echo "Existing certificate details:"
        gcloud compute ssl-certificates describe "$CERT_NAME" \
            --global \
            --project="$PROJECT_ID" \
            --format="yaml(name,managed.status,managed.domains)" || true

        ((SKIPPED++))
        return 0
    fi

    # Build domains argument
    local DOMAINS_ARG=""
    for domain in "${DOMAINS[@]}"; do
        if [[ -z "$DOMAINS_ARG" ]]; then
            DOMAINS_ARG="$domain"
        else
            DOMAINS_ARG="$DOMAINS_ARG,$domain"
        fi
    done

    # Create Google-managed SSL certificate
    if gcloud compute ssl-certificates create "$CERT_NAME" \
        --domains="$DOMAINS_ARG" \
        --global \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}✅ Created: $CERT_NAME${NC}"
        echo ""
        echo -e "${YELLOW}⚠️  Important: Certificate provisioning can take 10-60 minutes${NC}"
        echo "   Google must verify domain ownership via DNS challenge"
        ((CREATED++))
        return 0
    else
        echo -e "${RED}❌ Failed to create: $CERT_NAME${NC}"
        ((FAILED++))
        return 1
    fi
}

################################################################################
# Verification Function
################################################################################

verify_ssl_certificate() {
    local CERT_NAME=$1

    echo ""
    echo -e "${BLUE}Verifying SSL Certificate: ${CERT_NAME}${NC}"

    if ! gcloud compute ssl-certificates describe "$CERT_NAME" \
        --global \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${RED}❌ Certificate not found: $CERT_NAME${NC}"
        return 1
    fi

    # Get certificate status
    local STATUS=$(gcloud compute ssl-certificates describe "$CERT_NAME" \
        --global \
        --project="$PROJECT_ID" \
        --format="value(managed.status)" 2>/dev/null || echo "UNKNOWN")

    echo "  Status: $STATUS"

    case "$STATUS" in
        "ACTIVE")
            echo -e "${GREEN}  ✅ Certificate is ACTIVE and ready to use${NC}"
            return 0
            ;;
        "PROVISIONING")
            echo -e "${YELLOW}  ⏳ Certificate is PROVISIONING (this can take 10-60 minutes)${NC}"
            echo "     Google is verifying domain ownership via DNS"
            return 0
            ;;
        "FAILED_NOT_VISIBLE")
            echo -e "${RED}  ❌ Certificate FAILED: Domain not visible via DNS${NC}"
            echo "     Ensure DNS A record points to Load Balancer IP"
            return 1
            ;;
        "FAILED_CAA_FORBIDDEN")
            echo -e "${RED}  ❌ Certificate FAILED: CAA record forbids Google CA${NC}"
            echo "     Check DNS CAA records"
            return 1
            ;;
        "FAILED_CAA_CHECKING")
            echo -e "${RED}  ❌ Certificate FAILED: CAA check error${NC}"
            return 1
            ;;
        *)
            echo -e "${YELLOW}  ⚠️  Unknown status: $STATUS${NC}"
            return 1
            ;;
    esac
}

################################################################################
# Domain Configuration Prompt
################################################################################

prompt_domain_configuration() {
    print_section "🌐 Domain Configuration"

    echo "Current domain configuration:"
    echo "  Primary Domain: $PRIMARY_DOMAIN"
    echo "  WWW Domain: $WWW_DOMAIN"
    echo "  API Subdomain: $API_SUBDOMAIN"
    echo ""

    read -p "Do you want to use these domains? (yes/no): " USE_DEFAULTS

    if [[ "$USE_DEFAULTS" != "yes" ]]; then
        echo ""
        read -p "Enter primary domain (e.g., paygateprime.com): " PRIMARY_DOMAIN
        read -p "Enter www domain (optional, press Enter to skip): " WWW_DOMAIN
        read -p "Enter API subdomain (optional, press Enter to skip): " API_SUBDOMAIN
    fi

    echo ""
    echo "Final domain configuration:"
    echo "  Primary: $PRIMARY_DOMAIN"
    [[ -n "$WWW_DOMAIN" ]] && echo "  WWW: $WWW_DOMAIN"
    [[ -n "$API_SUBDOMAIN" ]] && echo "  API: $API_SUBDOMAIN"
    echo ""
}

################################################################################
# Main Execution
################################################################################

main() {
    print_header "🔒 SSL Certificate Provisioning - PGP_v1 Phase 2"

    echo "This script will create Google-managed SSL certificates for your"
    echo "HTTPS Load Balancer. Certificates are FREE and renew automatically."
    echo ""
    echo "Project: $PROJECT_ID"
    echo ""

    # Prompt for domain configuration
    prompt_domain_configuration

    # Safety prompt
    read -p "Do you want to proceed with certificate creation? (yes/no): " CONFIRM
    if [[ "$CONFIRM" != "yes" ]]; then
        echo -e "${YELLOW}⚠️  Operation cancelled by user${NC}"
        exit 0
    fi

    # Verify gcloud authentication
    print_section "🔐 Verifying Authentication"

    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    CURRENT_ACCOUNT=$(gcloud config get-value account 2>/dev/null)

    echo "Current account: $CURRENT_ACCOUNT"
    echo "Current project: $CURRENT_PROJECT"

    if [[ "$CURRENT_PROJECT" != "$PROJECT_ID" ]]; then
        echo -e "${YELLOW}⚠️  Warning: Current project ($CURRENT_PROJECT) does not match target project ($PROJECT_ID)${NC}"
        read -p "Do you want to continue anyway? (yes/no): " PROCEED
        if [[ "$PROCEED" != "yes" ]]; then
            echo -e "${YELLOW}⚠️  Operation cancelled${NC}"
            exit 0
        fi
    fi

    # Create SSL Certificates
    print_section "🔒 Creating SSL Certificates"

    # Build domain list
    CERT_DOMAINS=("$PRIMARY_DOMAIN")
    [[ -n "$WWW_DOMAIN" ]] && CERT_DOMAINS+=("$WWW_DOMAIN")
    [[ -n "$API_SUBDOMAIN" ]] && CERT_DOMAINS+=("$API_SUBDOMAIN")

    # Create primary certificate
    create_ssl_certificate "$PRIMARY_CERT_NAME" "${CERT_DOMAINS[@]}"

    # Verification
    print_section "✅ Verification"

    verify_ssl_certificate "$PRIMARY_CERT_NAME"

    # Summary
    print_section "📊 Summary"

    echo "SSL Certificates Created: $CREATED"
    echo "SSL Certificates Skipped (already exist): $SKIPPED"
    echo "SSL Certificates Failed: $FAILED"
    echo ""

    if [[ $FAILED -eq 0 ]]; then
        echo -e "${GREEN}✅ SSL certificate creation initiated successfully!${NC}"
        echo ""
        echo -e "${YELLOW}⚠️  IMPORTANT NEXT STEPS:${NC}"
        echo ""
        echo "1. Deploy Load Balancer (run deploy_load_balancer.sh)"
        echo "   This will give you a static IP address"
        echo ""
        echo "2. Update DNS records to point to Load Balancer IP:"
        echo "   - A record: $PRIMARY_DOMAIN → [LOAD_BALANCER_IP]"
        [[ -n "$WWW_DOMAIN" ]] && echo "   - CNAME: $WWW_DOMAIN → $PRIMARY_DOMAIN"
        [[ -n "$API_SUBDOMAIN" ]] && echo "   - CNAME: $API_SUBDOMAIN → $PRIMARY_DOMAIN"
        echo ""
        echo "3. Wait 10-60 minutes for certificate provisioning"
        echo "   - Google will verify domain ownership via DNS"
        echo "   - Check status with: gcloud compute ssl-certificates list"
        echo ""
        echo "4. Certificate will automatically activate once DNS is verified"
        echo ""
    else
        echo -e "${RED}❌ Some SSL certificates failed to create${NC}"
        echo "Please review the errors above and try again."
        exit 1
    fi

    # DNS Configuration Instructions
    print_section "📝 DNS Configuration Instructions"

    echo "After deploying the Load Balancer, configure these DNS records:"
    echo ""
    echo "  Record Type: A"
    echo "  Name: $PRIMARY_DOMAIN"
    echo "  Value: [LOAD_BALANCER_IP]"
    echo "  TTL: 300 (5 minutes)"
    echo ""

    if [[ -n "$WWW_DOMAIN" ]]; then
        echo "  Record Type: CNAME"
        echo "  Name: www"
        echo "  Value: $PRIMARY_DOMAIN"
        echo "  TTL: 300 (5 minutes)"
        echo ""
    fi

    if [[ -n "$API_SUBDOMAIN" ]]; then
        echo "  Record Type: CNAME"
        echo "  Name: api"
        echo "  Value: $PRIMARY_DOMAIN"
        echo "  TTL: 300 (5 minutes)"
        echo ""
    fi

    # List created certificates
    print_section "📋 SSL Certificates"

    gcloud compute ssl-certificates list \
        --project="$PROJECT_ID" \
        --format="table(name,managed.status,managed.domains:label=DOMAINS)" || true

    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ SSL certificate provisioning initiated!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Run main function
main

################################################################################
# Monitoring Certificate Status
################################################################################
#
# Check certificate status:
#   gcloud compute ssl-certificates describe pgp-ssl-cert --global
#
# List all certificates:
#   gcloud compute ssl-certificates list
#
# Certificate Status Values:
#   PROVISIONING - Google is verifying domain ownership (10-60 minutes)
#   ACTIVE - Certificate is ready to use
#   FAILED_NOT_VISIBLE - Domain not visible via DNS
#   FAILED_CAA_FORBIDDEN - CAA record forbids Google CA
#
################################################################################

################################################################################
# Rollback Instructions
################################################################################
#
# To delete SSL certificates:
#
# gcloud compute ssl-certificates delete pgp-ssl-cert \
#   --global --project=pgp-live --quiet
#
# Note: Delete Load Balancer HTTPS proxy first, or certificate deletion will fail
#
################################################################################

################################################################################
# Additional Notes
################################################################################
#
# Google-Managed SSL Certificates:
# - FREE (no cost)
# - Automatic renewal (no manual intervention)
# - DV (Domain Validation) only (not EV or OV)
# - Provisioning time: 10-60 minutes
# - Requires DNS to point to Load Balancer IP
#
# Domain Validation:
# - Google verifies domain ownership via DNS challenge
# - DNS A record must point to Load Balancer IP
# - Validation can take 10-60 minutes
#
# Certificate Renewal:
# - Automatic renewal 30 days before expiration
# - No downtime during renewal
# - No action required from you
#
# Limitations:
# - Max 100 domains per certificate
# - Wildcard domains not supported in Google-managed certs
#   (use self-managed cert for wildcards)
# - Must be attached to Load Balancer (not standalone)
#
# Cost:
# - Google-managed certificates: FREE
# - Self-managed certificates: FREE (if you provide your own)
# - Load Balancer HTTPS proxy: Included in Load Balancer cost
#
################################################################################
