#!/bin/bash
################################################################################
# Deploy pgp-server-v1 (Telegram Bot with NotificationService)
# Purpose: Deploy updated PGP server bot with notification service
# Version: 2.0
# Date: 2025-11-15
################################################################################

set -e  # Exit on error

echo ""
echo "========================================================================"
echo "🚀 Deploying pgp-server-v1 (Telegram Bot)"
echo "========================================================================"
echo ""

# Configuration
SERVICE_NAME="pgp-server-v1"
REGION="us-central1"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../PGP_SERVER_v1"

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

echo "🔍 Checking for new files..."
if [ -f "notification_pgp_notifications_v1.py" ]; then
    echo "   ✅ notification_pgp_notifications_v1.py found"
else
    echo "   ⚠️ notification_pgp_notifications_v1.py not found"
fi

if [ -f "server_manager.py" ]; then
    echo "   ✅ server_manager.py found"
else
    echo "   ⚠️ server_manager.py not found"
fi

echo ""
echo "🔍 Checking current deployment status..."
gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)" 2>/dev/null || echo "   Service not found or not deployed yet"
echo ""

# Get all secrets and configure them
echo "🔐 Configuring secrets..."
SECRET_NAMES=(
    "TELEGRAM_BOT_SECRET_NAME"
    "TELEGRAM_BOT_USERNAME"
    "CLOUD_SQL_CONNECTION_NAME"
    "DATABASE_HOST_SECRET"
    "DATABASE_NAME_SECRET"
    "DATABASE_USER_SECRET"
    "DATABASE_PASSWORD_SECRET"
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
    --timeout=3600 \
    --memory=1Gi \
    --cpu=2 \
    --min-instances=1 \
    --max-instances=3 \
    --execution-environment=gen2 \
    --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql \
    --set-env-vars=SUBSCRIPTION_CHECK_INTERVAL=60 \
    $SECRET_ARGS

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================================================"
    echo "✅ pgp-server-v1 deployed successfully!"
    echo "========================================================================"
    echo ""

    # Get service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
    echo "🌐 Service URL: $SERVICE_URL"
    echo ""

    # Save URL for pgp-np-ipn-v1 configuration
    echo "📝 Saving service URL for pgp-np-ipn-v1 configuration..."
    echo "$SERVICE_URL" > /tmp/pgp_server_url.txt
    echo "   Saved to: /tmp/pgp_server_url.txt"
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

    echo "ℹ️ Important: Update PGP_SERVER_URL secret with this URL:"
    echo "   gcloud secrets versions add PGP_SERVER_URL --data-file=- <<< \"$SERVICE_URL\""
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
