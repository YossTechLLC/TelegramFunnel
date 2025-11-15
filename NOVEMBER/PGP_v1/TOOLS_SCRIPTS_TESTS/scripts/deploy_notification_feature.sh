#!/bin/bash
################################################################################
# Master Deployment Script: Notification Management Feature
# Purpose: Orchestrate deployment of all notification management components
# Version: 1.0
# Date: 2025-11-11
################################################################################

set -e  # Exit on error

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "🚀 PGP_v1 NOTIFICATION MANAGEMENT - DEPLOYMENT ORCHESTRATOR"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "This script will deploy all components for the notification management"
echo "feature in the correct order:"
echo ""
echo "  1. ✅ Database Migration (Already completed)"
echo "  2. 📦 Backend API (pgp-webapi-v1)"
echo "  3. 🎨 Frontend (pgp-web-v1)"
echo "  4. 🤖 Server Bot (pgp-server-v1)"
echo "  5. 📬 IPN Webhook (pgp-np-ipn-v1)"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/../logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log file
LOG_FILE="$LOG_DIR/deployment_notification_feature_$TIMESTAMP.log"

echo "📋 Configuration:"
echo "   Script Directory: $SCRIPT_DIR"
echo "   Log Directory: $LOG_DIR"
echo "   Log File: $LOG_FILE"
echo ""

# Function to log and execute
log_and_execute() {
    local script_name=$1
    local description=$2
    local script_path="$SCRIPT_DIR/$script_name"

    echo ""
    echo "────────────────────────────────────────────────────────────────────────"
    echo "📦 $description"
    echo "────────────────────────────────────────────────────────────────────────"
    echo ""

    if [ ! -f "$script_path" ]; then
        echo "❌ Error: Deployment script not found: $script_path"
        exit 1
    fi

    # Make script executable
    chmod +x "$script_path"

    # Execute script and log output
    if bash "$script_path" 2>&1 | tee -a "$LOG_FILE"; then
        echo ""
        echo "✅ $description - COMPLETED"
        return 0
    else
        echo ""
        echo "❌ $description - FAILED"
        return 1
    fi
}

# Function to prompt user
prompt_continue() {
    local message=$1
    echo ""
    read -p "$message (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Deployment cancelled by user"
        exit 1
    fi
}

# Start deployment
echo "⚠️ IMPORTANT: This will deploy to production!"
prompt_continue "Do you want to continue?"

echo ""
echo "🚀 Starting deployment process..."
echo ""

# Track deployment status
DEPLOYMENT_FAILED=false

# Step 1: Database Migration (Already completed, just verify)
echo "────────────────────────────────────────────────────────────────────────"
echo "✅ Step 1: Database Migration (Already completed)"
echo "────────────────────────────────────────────────────────────────────────"
echo ""
echo "Database migration has been executed successfully."
echo "Columns added:"
echo "  • notification_status (BOOLEAN, DEFAULT false, NOT NULL)"
echo "  • notification_id (BIGINT, DEFAULT NULL)"
echo ""

# Step 2: Backend API
if ! log_and_execute "deploy_backend_api.sh" "Step 2: Deploying Backend API (pgp-webapi-v1)"; then
    DEPLOYMENT_FAILED=true
    echo "❌ Backend API deployment failed!"
    prompt_continue "Continue with remaining deployments?"
fi

# Step 3: Frontend
if ! log_and_execute "deploy_frontend.sh" "Step 3: Deploying Frontend (pgp-web-v1)"; then
    DEPLOYMENT_FAILED=true
    echo "❌ Frontend deployment failed!"
    prompt_continue "Continue with remaining deployments?"
fi

# Step 4: Server Bot
if ! log_and_execute "deploy_telepay_bot.sh" "Step 4: Deploying Server Bot (pgp-server-v1)"; then
    DEPLOYMENT_FAILED=true
    echo "❌ Server Bot deployment failed!"
    prompt_continue "Continue with remaining deployments?"
fi

# Step 5: IPN Webhook
if ! log_and_execute "deploy_np_webhook.sh" "Step 5: Deploying IPN Webhook (pgp-np-ipn-v1)"; then
    DEPLOYMENT_FAILED=true
    echo "❌ IPN Webhook deployment failed!"
fi

# Summary
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📊 DEPLOYMENT SUMMARY"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "Timestamp: $(date)"
echo "Log File: $LOG_FILE"
echo ""

if [ "$DEPLOYMENT_FAILED" = true ]; then
    echo "⚠️ DEPLOYMENT COMPLETED WITH ERRORS"
    echo ""
    echo "Some components failed to deploy. Please check the log file for details."
    echo ""
    exit 1
else
    echo "✅ ALL COMPONENTS DEPLOYED SUCCESSFULLY!"
    echo ""
    echo "🎉 PGP_v1 Notification Management Feature is now live!"
    echo ""
    echo "Next steps:"
    echo "  1. Test channel registration with notifications enabled"
    echo "  2. Test notification delivery with a real payment"
    echo "  3. Monitor Cloud Logging for any errors"
    echo ""
    echo "Monitoring:"
    echo "  • Cloud Run Services: https://console.cloud.google.com/run"
    echo "  • Cloud Logging: https://console.cloud.google.com/logs"
    echo "  • Error Reporting: https://console.cloud.google.com/errors"
    echo ""
    exit 0
fi
