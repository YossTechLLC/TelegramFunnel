#!/bin/bash
################################################################################
# Deploy np-webhook-10-26 (NowPayments IPN Webhook)
# Purpose: Deploy updated webhook with notification trigger
# Version: 1.0
# Date: 2025-11-11
################################################################################

set -e  # Exit on error

echo ""
echo "========================================================================"
echo "🚀 Deploying np-webhook-10-26 (IPN Webhook)"
echo "========================================================================"
echo ""

# Configuration
SERVICE_NAME="np-webhook-10-26"
REGION="us-central1"
SOURCE_DIR="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26"

echo "📋 Configuration:"
echo "   Service: $SERVICE_NAME"
echo "   Region: $REGION"
echo "   Source: $SOURCE_DIR"
echo ""

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Error: Source directory not found: $SOURCE_DIR"
    exit 1
fi

cd "$SOURCE_DIR"

echo "🔍 Checking current deployment status..."
gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)" 2>/dev/null || echo "   Service not found or not deployed yet"
echo ""

# Check if TELEPAY_BOT_URL secret exists
echo "🔍 Checking TELEPAY_BOT_URL secret..."
if gcloud secrets describe TELEPAY_BOT_URL &>/dev/null; then
    TELEPAY_BOT_URL=$(gcloud secrets versions access latest --secret=TELEPAY_BOT_URL)
    echo "   ✅ TELEPAY_BOT_URL found: $TELEPAY_BOT_URL"
else
    echo "   ⚠️ TELEPAY_BOT_URL secret not found!"
    echo "   Creating secret..."

    # Check if TelePay bot URL was saved
    if [ -f "/tmp/telepay_bot_url.txt" ]; then
        TELEPAY_BOT_URL=$(cat /tmp/telepay_bot_url.txt)
        echo "$TELEPAY_BOT_URL" | gcloud secrets create TELEPAY_BOT_URL --data-file=-
        echo "   ✅ Created TELEPAY_BOT_URL secret with: $TELEPAY_BOT_URL"
    else
        echo "   ❌ Error: TelePay bot URL not found. Please deploy TelePay bot first."
        exit 1
    fi
fi

echo ""

# Get all secrets and configure them
echo "🔐 Configuring secrets..."
SECRET_NAMES=(
    "NOWPAYMENTS_IPN_SECRET"
    "CLOUD_SQL_CONNECTION_NAME"
    "DATABASE_NAME_SECRET"
    "DATABASE_USER_SECRET"
    "DATABASE_PASSWORD_SECRET"
    "CLOUD_TASKS_PROJECT_ID"
    "CLOUD_TASKS_LOCATION"
    "GCWEBHOOK1_QUEUE"
    "GCWEBHOOK1_URL"
    "GCWEBHOOK2_QUEUE"
    "GCWEBHOOK2_URL"
    "TELEPAY_BOT_URL"
)

SECRET_ARGS=""
for SECRET in "${SECRET_NAMES[@]}"; do
    SECRET_ARGS="$SECRET_ARGS --set-secrets=$SECRET=$SECRET:latest"
done

echo "   Secrets configured: ${#SECRET_NAMES[@]} secrets"
echo ""

echo "📦 Building and deploying service..."
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --timeout=300 \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=1 \
    --max-instances=10 \
    --execution-environment=gen2 \
    $SECRET_ARGS

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================================================"
    echo "✅ np-webhook-10-26 deployed successfully!"
    echo "========================================================================"
    echo ""

    # Get service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
    echo "🌐 Service URL: $SERVICE_URL"
    echo ""

    echo "ℹ️ Important: Update NowPayments IPN URL with:"
    echo "   $SERVICE_URL/ipn"
    echo ""

    # Test health endpoint
    echo "🏥 Testing health endpoint..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/health")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "   ✅ Health check passed (HTTP $HTTP_CODE)"
    else
        echo "   ⚠️ Health check returned HTTP $HTTP_CODE"
    fi
    echo ""

    echo "✅ Deployment completed successfully!"
    exit 0
else
    echo ""
    echo "========================================================================"
    echo "❌ Deployment failed!"
    echo "========================================================================"
    echo ""
    exit 1
fi
