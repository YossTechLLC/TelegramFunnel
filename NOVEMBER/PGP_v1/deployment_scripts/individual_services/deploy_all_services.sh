#!/bin/bash
# Master Deployment Script - Deploy All 15 Services in Correct Order
# DO NOT EXECUTE - Review before running
# This script orchestrates the deployment of all PayGatePrime v1 services

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 PayGatePrime v1 - Master Deployment Script"
echo "=============================================="
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Region: $REGION"
echo "📍 Services: 15 total"
echo ""
echo "⏱️  Estimated time: 30-60 minutes"
echo ""
echo "⚠️  This will deploy all services in the following order:"
echo "   1. Critical public services (gcregisterapi, np-webhook)"
echo "   2. Payment processing chain (gcwebhook1, gcwebhook2)"
echo "   3. Split payment services (gcsplit1-3)"
echo "   4. Host payment services (gchostpay1-3)"
echo "   5. Accumulator and batch processors"
echo "   6. Telegram bot (telepay)"
echo ""

read -p "Do you want to continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Deployment cancelled"
    exit 1
fi

# Set project
gcloud config set project $PROJECT_ID

# Track deployment status
DEPLOYED_SERVICES=()
FAILED_SERVICES=()

# Function to deploy a service
deploy_service() {
    local service_script=$1
    local service_name=$2

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📦 Deploying: $service_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if bash "$SCRIPT_DIR/$service_script"; then
        DEPLOYED_SERVICES+=("$service_name")
        echo "✅ $service_name deployed successfully"
    else
        FAILED_SERVICES+=("$service_name")
        echo "❌ $service_name deployment failed"
        echo ""
        read -p "Continue with remaining deployments? (yes/no): " CONTINUE
        if [ "$CONTINUE" != "yes" ]; then
            echo "❌ Deployment stopped"
            print_summary
            exit 1
        fi
    fi
}

# Function to print deployment summary
print_summary() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 DEPLOYMENT SUMMARY"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "✅ Successfully deployed: ${#DEPLOYED_SERVICES[@]} services"
    for service in "${DEPLOYED_SERVICES[@]}"; do
        echo "   ✓ $service"
    done
    echo ""

    if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
        echo "❌ Failed deployments: ${#FAILED_SERVICES[@]} services"
        for service in "${FAILED_SERVICES[@]}"; do
            echo "   ✗ $service"
        done
        echo ""
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# =============================================================================
# PHASE 1: Critical Public Services
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PHASE 1: Critical Public Services"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "These services must be deployed first as they are entry points"
echo ""

deploy_service "deploy_gcregisterapi.sh" "gcregisterapi-pgp"
deploy_service "deploy_np_webhook.sh" "np-webhook-pgp"

# After deploying these services, update service URL secrets
echo ""
echo "📝 Updating service URL secrets for deployed services..."
cd "$SCRIPT_DIR/../.."
bash deployment_scripts/05_create_service_url_secrets.sh

# =============================================================================
# PHASE 2: Payment Processing Chain
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PHASE 2: Payment Processing Chain"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "These services handle payment processing and Telegram invites"
echo ""

deploy_service "deploy_gcwebhook1.sh" "gcwebhook1-pgp"
deploy_service "deploy_gcwebhook2.sh" "gcwebhook2-pgp"

# Update service URLs
echo ""
echo "📝 Updating service URL secrets..."
bash deployment_scripts/05_create_service_url_secrets.sh

# =============================================================================
# PHASE 3: Split Payment Services
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PHASE 3: Split Payment Services"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "These services handle payment splitting and routing"
echo ""

deploy_service "deploy_gcsplit1.sh" "gcsplit1-pgp"
deploy_service "deploy_gcsplit2.sh" "gcsplit2-pgp"
deploy_service "deploy_gcsplit3.sh" "gcsplit3-pgp"

# Update service URLs
echo ""
echo "📝 Updating service URL secrets..."
bash deployment_scripts/05_create_service_url_secrets.sh

# =============================================================================
# PHASE 4: Host Payment Services
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PHASE 4: Host Payment Services"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "These services handle crypto conversions and blockchain validation"
echo ""

deploy_service "deploy_gchostpay1.sh" "gchostpay1-pgp"
deploy_service "deploy_gchostpay2.sh" "gchostpay2-pgp"
deploy_service "deploy_gchostpay3.sh" "gchostpay3-pgp"

# Update service URLs
echo ""
echo "📝 Updating service URL secrets..."
bash deployment_scripts/05_create_service_url_secrets.sh

# =============================================================================
# PHASE 5: Accumulator and Batch Processors
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PHASE 5: Accumulator and Batch Processors"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "These services handle payment accumulation and batch processing"
echo ""

deploy_service "deploy_gcaccumulator.sh" "gcaccumulator-pgp"
deploy_service "deploy_gcbatchprocessor.sh" "gcbatchprocessor-pgp"
deploy_service "deploy_gcmicrobatchprocessor.sh" "gcmicrobatchprocessor-pgp"

# Update service URLs
echo ""
echo "📝 Updating service URL secrets..."
bash deployment_scripts/05_create_service_url_secrets.sh

# =============================================================================
# PHASE 6: Telegram Bot
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PHASE 6: Telegram Bot"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Legacy Telegram bot for payment notifications"
echo ""

deploy_service "deploy_telepay.sh" "telepay-pgp"

# =============================================================================
# FINAL: Print Summary and Next Steps
# =============================================================================

print_summary

if [ ${#FAILED_SERVICES[@]} -eq 0 ]; then
    echo ""
    echo "🎉 ALL SERVICES DEPLOYED SUCCESSFULLY!"
    echo ""
    echo "📝 CRITICAL NEXT STEPS:"
    echo ""
    echo "1️⃣ Configure NowPayments IPN Webhook:"
    echo "   → See deployment_scripts/09_EXTERNAL_WEBHOOKS_CONFIG.md"
    echo ""
    echo "2️⃣ Run Verification Script:"
    echo "   → bash deployment_scripts/10_verify_deployment.sh"
    echo ""
    echo "3️⃣ Test End-to-End Payment Flow:"
    echo "   → Create test account"
    echo "   → Initiate test payment"
    echo "   → Monitor logs for each service"
    echo ""
    echo "4️⃣ Set Up Monitoring:"
    echo "   → Create Cloud Monitoring dashboards"
    echo "   → Set up alert policies"
    echo "   → Configure log-based metrics"
    echo ""
    echo "5️⃣ Deploy Frontend:"
    echo "   → bash deployment_scripts/08_deploy_frontend.sh"
    echo ""
else
    echo ""
    echo "⚠️  DEPLOYMENT COMPLETED WITH ERRORS"
    echo ""
    echo "📋 Please review failed services and redeploy individually:"
    for service in "${FAILED_SERVICES[@]}"; do
        echo "   • $service"
    done
    echo ""
    echo "📝 Check logs for each failed service to diagnose issues"
    echo ""
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Deployment script completed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
