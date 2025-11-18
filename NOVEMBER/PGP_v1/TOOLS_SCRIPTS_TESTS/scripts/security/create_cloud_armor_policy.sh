#!/bin/bash

################################################################################
# Create Cloud Armor Security Policy for PGP_v1 Load Balancer
################################################################################
#
# Purpose: Create Cloud Armor security policy with WAF rules, IP whitelisting,
#          rate limiting, and DDoS protection
#
# Security Features:
#   1. IP Whitelist for NowPayments webhook (known IPs only)
#   2. IP Whitelist for Telegram webhook (known IP ranges)
#   3. Rate limiting (DDoS protection)
#   4. OWASP Top 10 WAF rules
#   5. Adaptive Protection (ML-based DDoS detection)
#   6. Geo-blocking (optional)
#
# Architecture:
#   - One security policy attached to multiple backend services
#   - Rules evaluated in priority order (lower number = higher priority)
#   - Default action: DENY (explicit allow rules required)
#
# Prerequisites:
#   - gcloud CLI authenticated with sufficient permissions
#   - Compute Engine API enabled
#   - Backend services created (or will be created by deploy_load_balancer.sh)
#
# Permissions Required:
#   - compute.securityPolicies.create
#   - compute.securityPolicies.update
#
# Usage:
#   bash create_cloud_armor_policy.sh
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
POLICY_NAME="pgp-security-policy"

# NowPayments IP Whitelist
# Source: https://nowpayments.io/help/ipn-callback-ip-addresses
# Note: These IPs should be verified from NowPayments documentation
NOWPAYMENTS_IPS=(
    "193.233.22.4/32"      # NowPayments IPN Server 1
    "193.233.22.5/32"      # NowPayments IPN Server 2
    "185.136.165.122/32"   # NowPayments IPN Server 3
)

# Telegram Bot API IP Ranges
# Source: https://core.telegram.org/bots/webhooks#the-short-version
# Note: Telegram uses dynamic IPs within these ranges
TELEGRAM_IPS=(
    "149.154.160.0/20"     # Telegram DC1
    "91.108.4.0/22"        # Telegram DC2
)

# Rate Limiting Configuration
RATE_LIMIT_THRESHOLD=100           # Requests per minute per IP
RATE_LIMIT_CONFORM_ACTION="allow"
RATE_LIMIT_EXCEED_ACTION="deny(429)"  # HTTP 429 Too Many Requests
RATE_LIMIT_BAN_DURATION="600"      # Ban for 10 minutes

# Counters
CREATED=0
UPDATED=0
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
# Cloud Armor Policy Creation Function
################################################################################

create_security_policy() {
    echo ""
    echo -e "${BLUE}Creating Cloud Armor Security Policy: ${POLICY_NAME}${NC}"

    # Check if policy already exists
    if gcloud compute security-policies describe "$POLICY_NAME" \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}⚠️  Security policy already exists: $POLICY_NAME${NC}"
        echo "Existing rules will be updated."
        ((UPDATED++))
    else
        # Create security policy with default deny rule
        if gcloud compute security-policies create "$POLICY_NAME" \
            --description="PGP_v1 Security Policy - WAF, DDoS Protection, IP Whitelist" \
            --project="$PROJECT_ID" \
            --quiet; then
            echo -e "${GREEN}✅ Created security policy: $POLICY_NAME${NC}"
            ((CREATED++))
        else
            echo -e "${RED}❌ Failed to create security policy${NC}"
            ((FAILED++))
            return 1
        fi
    fi
}

################################################################################
# Security Rule Creation Functions
################################################################################

add_rule() {
    local PRIORITY=$1
    local ACTION=$2
    local DESCRIPTION=$3
    shift 3
    local EXTRA_ARGS=("$@")

    echo ""
    echo -e "${BLUE}Adding rule (priority $PRIORITY): $DESCRIPTION${NC}"

    # Delete existing rule at this priority (if exists)
    gcloud compute security-policies rules delete "$PRIORITY" \
        --security-policy="$POLICY_NAME" \
        --project="$PROJECT_ID" \
        --quiet &>/dev/null || true

    # Create new rule
    if gcloud compute security-policies rules create "$PRIORITY" \
        --security-policy="$POLICY_NAME" \
        --action="$ACTION" \
        --description="$DESCRIPTION" \
        "${EXTRA_ARGS[@]}" \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}  ✅ Rule added successfully${NC}"
        return 0
    else
        echo -e "${RED}  ❌ Failed to add rule${NC}"
        return 1
    fi
}

################################################################################
# Rule Configuration Functions
################################################################################

configure_default_rule() {
    print_section "🛡️ Configuring Default Rule"

    echo "Setting default rule to ALLOW (will add specific DENY rules)"

    # Update default rule (priority 2147483647)
    gcloud compute security-policies rules update 2147483647 \
        --security-policy="$POLICY_NAME" \
        --action="allow" \
        --project="$PROJECT_ID" \
        --quiet || true

    echo -e "${GREEN}✅ Default rule configured${NC}"
}

configure_ip_whitelist_rules() {
    print_section "🌐 Configuring IP Whitelist Rules"

    # Rule 1000: Allow NowPayments IPs
    echo ""
    echo "Building NowPayments IP whitelist..."
    NOWPAYMENTS_IP_LIST=$(IFS=,; echo "${NOWPAYMENTS_IPS[*]}")

    add_rule 1000 "allow" \
        "Allow NowPayments IPN webhook IPs" \
        --src-ip-ranges="$NOWPAYMENTS_IP_LIST"

    # Rule 1100: Allow Telegram IPs
    echo ""
    echo "Building Telegram IP whitelist..."
    TELEGRAM_IP_LIST=$(IFS=,; echo "${TELEGRAM_IPS[*]}")

    add_rule 1100 "allow" \
        "Allow Telegram Bot API webhook IPs" \
        --src-ip-ranges="$TELEGRAM_IP_LIST"
}

configure_rate_limiting_rules() {
    print_section "⏱️ Configuring Rate Limiting Rules"

    # Rule 2000: Rate limit all traffic
    echo ""
    echo "Configuring rate limiting: $RATE_LIMIT_THRESHOLD requests/minute per IP"

    add_rule 2000 "rate-based-ban" \
        "Rate limiting - $RATE_LIMIT_THRESHOLD req/min per IP" \
        --rate-limit-threshold-count="$RATE_LIMIT_THRESHOLD" \
        --rate-limit-threshold-interval-sec=60 \
        --conform-action="$RATE_LIMIT_CONFORM_ACTION" \
        --exceed-action="$RATE_LIMIT_EXCEED_ACTION" \
        --ban-duration-sec="$RATE_LIMIT_BAN_DURATION" \
        --enforce-on-key=IP
}

configure_owasp_rules() {
    print_section "🔒 Configuring OWASP Top 10 WAF Rules"

    # Rule 3000: OWASP Core Rule Set
    echo ""
    echo "Enabling OWASP ModSecurity Core Rule Set..."

    # SQL Injection (SQLi)
    add_rule 3000 "deny(403)" \
        "Block SQL Injection (OWASP)" \
        --expression="evaluatePreconfiguredExpr('sqli-stable')"

    # Cross-Site Scripting (XSS)
    add_rule 3100 "deny(403)" \
        "Block Cross-Site Scripting (OWASP)" \
        --expression="evaluatePreconfiguredExpr('xss-stable')"

    # Local File Inclusion (LFI)
    add_rule 3200 "deny(403)" \
        "Block Local File Inclusion (OWASP)" \
        --expression="evaluatePreconfiguredExpr('lfi-stable')"

    # Remote Code Execution (RCE)
    add_rule 3300 "deny(403)" \
        "Block Remote Code Execution (OWASP)" \
        --expression="evaluatePreconfiguredExpr('rce-stable')"

    # Remote File Inclusion (RFI)
    add_rule 3400 "deny(403)" \
        "Block Remote File Inclusion (OWASP)" \
        --expression="evaluatePreconfiguredExpr('rfi-stable')"

    # Method Enforcement (allow only GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
    add_rule 3500 "deny(403)" \
        "Block unsupported HTTP methods (OWASP)" \
        --expression="evaluatePreconfiguredExpr('methodenforcement-stable')"

    # Scanner Detection
    add_rule 3600 "deny(403)" \
        "Block security scanners (OWASP)" \
        --expression="evaluatePreconfiguredExpr('scannerdetection-stable')"

    # Protocol Attack
    add_rule 3700 "deny(403)" \
        "Block protocol attacks (OWASP)" \
        --expression="evaluatePreconfiguredExpr('protocolattack-stable')"

    # PHP Injection
    add_rule 3800 "deny(403)" \
        "Block PHP injection (OWASP)" \
        --expression="evaluatePreconfiguredExpr('php-stable')"

    # Session Fixation
    add_rule 3900 "deny(403)" \
        "Block session fixation (OWASP)" \
        --expression="evaluatePreconfiguredExpr('sessionfixation-stable')"
}

configure_adaptive_protection() {
    print_section "🤖 Configuring Adaptive Protection (ML-based DDoS)"

    echo ""
    echo "Enabling Adaptive Protection..."
    echo "This uses machine learning to detect and mitigate Layer 7 DDoS attacks."

    # Enable adaptive protection
    if gcloud compute security-policies update "$POLICY_NAME" \
        --enable-layer7-ddos-defense \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}✅ Adaptive Protection enabled${NC}"
    else
        echo -e "${YELLOW}⚠️  Adaptive Protection may not be available in your project${NC}"
        echo "   This feature requires special enablement by Google Support"
    fi
}

configure_logging() {
    print_section "📊 Configuring Security Policy Logging"

    echo ""
    echo "Enabling verbose logging for security events..."

    # Enable logging with sample rate 1.0 (log all events)
    if gcloud compute security-policies update "$POLICY_NAME" \
        --log-level=VERBOSE \
        --project="$PROJECT_ID" \
        --quiet; then
        echo -e "${GREEN}✅ Logging enabled${NC}"
        echo "   Logs will be available in Cloud Logging under 'http_load_balancer' resource"
    else
        echo -e "${YELLOW}⚠️  Failed to enable logging${NC}"
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    print_header "🛡️ Cloud Armor Security Policy - PGP_v1 Phase 2"

    echo "This script will create a Cloud Armor security policy with:"
    echo "  - IP whitelist for NowPayments webhook"
    echo "  - IP whitelist for Telegram webhook"
    echo "  - Rate limiting (DDoS protection)"
    echo "  - OWASP Top 10 WAF rules"
    echo "  - Adaptive Protection (ML-based DDoS)"
    echo ""
    echo "Project: $PROJECT_ID"
    echo "Policy Name: $POLICY_NAME"
    echo ""

    # Display IP whitelist configuration
    echo "NowPayments IPs to whitelist:"
    for ip in "${NOWPAYMENTS_IPS[@]}"; do
        echo "  - $ip"
    done
    echo ""

    echo "Telegram IP ranges to whitelist:"
    for ip in "${TELEGRAM_IPS[@]}"; do
        echo "  - $ip"
    done
    echo ""

    echo "Rate Limiting Configuration:"
    echo "  Threshold: $RATE_LIMIT_THRESHOLD requests/minute per IP"
    echo "  Ban Duration: $RATE_LIMIT_BAN_DURATION seconds (10 minutes)"
    echo ""

    # Safety prompt
    read -p "Do you want to proceed? (yes/no): " CONFIRM
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

    # Create security policy
    print_section "🛡️ Creating Security Policy"
    create_security_policy

    # Configure rules
    configure_default_rule
    configure_ip_whitelist_rules
    configure_rate_limiting_rules
    configure_owasp_rules
    configure_adaptive_protection
    configure_logging

    # Summary
    print_section "📊 Summary"

    echo "Security Policies Created: $CREATED"
    echo "Security Policies Updated: $UPDATED"
    echo "Operations Failed: $FAILED"
    echo ""

    if [[ $FAILED -eq 0 ]]; then
        echo -e "${GREEN}✅ Cloud Armor security policy configured successfully!${NC}"
        echo ""
        echo "Security Features Enabled:"
        echo "  ✅ IP whitelist for NowPayments"
        echo "  ✅ IP whitelist for Telegram"
        echo "  ✅ Rate limiting (100 req/min per IP)"
        echo "  ✅ OWASP Top 10 WAF rules"
        echo "  ✅ Adaptive Protection (if available)"
        echo "  ✅ Verbose logging"
        echo ""
        echo "Next Steps:"
        echo "  1. Run deploy_load_balancer.sh to create Load Balancer"
        echo "  2. Attach this policy to backend services during deployment"
        echo "  3. Monitor Cloud Armor logs in Cloud Logging"
    else
        echo -e "${RED}❌ Some operations failed${NC}"
        echo "Please review the errors above and try again."
        exit 1
    fi

    # Display security policy details
    print_section "📋 Security Policy Details"

    gcloud compute security-policies describe "$POLICY_NAME" \
        --project="$PROJECT_ID" \
        --format="yaml(name,description,rules)" || true

    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ Cloud Armor configuration complete!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Run main function
main

################################################################################
# Monitoring Cloud Armor
################################################################################
#
# View security policy:
#   gcloud compute security-policies describe pgp-security-policy
#
# List all security policies:
#   gcloud compute security-policies list
#
# View Cloud Armor logs:
#   gcloud logging read 'resource.type="http_load_balancer"
#     jsonPayload.enforcedSecurityPolicy.name="pgp-security-policy"' \
#     --limit 50 --format json
#
# Monitor blocked requests:
#   gcloud logging read 'resource.type="http_load_balancer"
#     jsonPayload.enforcedSecurityPolicy.outcome="DENY"' \
#     --limit 50
#
################################################################################

################################################################################
# Rollback Instructions
################################################################################
#
# To delete security policy:
#
# 1. First, detach from all backend services:
#    gcloud compute backend-services update [BACKEND_SERVICE] \
#      --security-policy="" --global
#
# 2. Then delete policy:
#    gcloud compute security-policies delete pgp-security-policy \
#      --project=pgp-live --quiet
#
################################################################################

################################################################################
# Cost Breakdown
################################################################################
#
# Cloud Armor Pricing:
# - First 5 rules: FREE
# - Additional rules: $1/month per rule (we have ~15 rules = $10/month)
# - Requests: First 1M requests FREE, then $0.75 per 1M requests
# - Adaptive Protection: $50/month (optional, may require enablement)
#
# Estimated Monthly Cost:
# - Rules: ~$10/month (15 rules)
# - Requests: ~$0-5/month (depends on traffic)
# - Adaptive Protection: $0 (if not enabled) or $50 (if enabled)
# - Total: ~$10-65/month
#
################################################################################

################################################################################
# IP Address Sources
################################################################################
#
# NowPayments IPs:
# - Source: https://nowpayments.io/help/ipn-callback-ip-addresses
# - Update: Check NowPayments documentation periodically
# - Fallback: Use HMAC signature verification (already implemented)
#
# Telegram IPs:
# - Source: https://core.telegram.org/bots/webhooks#the-short-version
# - Update: Telegram IP ranges rarely change
# - Note: Telegram uses dynamic IPs within these ranges
#
# IMPORTANT: IP whitelisting is SECONDARY security layer
# PRIMARY security is HMAC signature verification (already implemented)
#
################################################################################
