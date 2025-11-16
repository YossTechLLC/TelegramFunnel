#!/bin/bash
################################################################################
# Deploy pgp-np-ipn-v1 (NowPayments IPN Webhook)
# Purpose: Deploy updated webhook with notification trigger
# Version: 2.0
# Date: 2025-11-15
################################################################################

set -e  # Exit on error

echo ""
echo "========================================================================"
echo "🚀 Deploying pgp-np-ipn-v1 (IPN Webhook)"
echo "========================================================================"
echo ""

# Configuration
SERVICE_NAME="pgp-np-ipn-v1"
REGION="us-central1"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../PGP_NP_IPN_v1"

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

# Check if PGP_SERVER_URL secret exists
echo "🔍 Checking PGP_SERVER_URL secret..."
if gcloud secrets describe PGP_SERVER_URL &>/dev/null; then
    PGP_SERVER_URL=$(gcloud secrets versions access latest --secret=PGP_SERVER_URL)
    echo "   ✅ PGP_SERVER_URL found: $PGP_SERVER_URL"
else
    echo "   ⚠️ PGP_SERVER_URL secret not found!"
    echo "   Creating secret..."

    # Check if PGP server URL was saved
    if [ -f "/tmp/pgp_server_url.txt" ]; then
        PGP_SERVER_URL=$(cat /tmp/pgp_server_url.txt)
        echo "$PGP_SERVER_URL" | gcloud secrets create PGP_SERVER_URL --data-file=-
        echo "   ✅ Created PGP_SERVER_URL secret with: $PGP_SERVER_URL"
    else
        echo "   ❌ Error: PGP server URL not found. Please deploy pgp-server-v1 first."
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
    "PGP_ORCHESTRATOR_QUEUE"
    "PGP_ORCHESTRATOR_URL"
    "PGP_INVITE_QUEUE"
    "PGP_INVITE_URL"
    "PGP_SERVER_URL"
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
    echo "✅ pgp-np-ipn-v1 deployed successfully!"
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
