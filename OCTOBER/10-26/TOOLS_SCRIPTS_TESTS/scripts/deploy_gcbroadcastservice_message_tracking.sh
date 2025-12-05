#!/bin/bash
# Deploy GCBroadcastService-10-26 with Message Tracking Feature
# Date: 2025-11-14
# Purpose: Deploy updated service with message deletion capability

set -e  # Exit on error

echo "=========================================="
echo "🚀 Deploying GCBroadcastService-10-26"
echo "=========================================="

# Configuration
PROJECT_ID="telepay-459221"
REGION="us-central1"
SERVICE_NAME="gcbroadcastservice-10-26"
SERVICE_DIR="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCBroadcastService-10-26"

# Navigate to service directory
echo "📂 Navigating to service directory..."
cd "$SERVICE_DIR"

# Build and deploy using Cloud Run source-based deployment
echo "🔨 Building and deploying service..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300 \
  --concurrency=10 \
  --min-instances=0 \
  --max-instances=10 \
  --set-env-vars="BOT_TOKEN_SECRET=projects/telepay-459221/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest" \
  --set-env-vars="BOT_USERNAME_SECRET=projects/telepay-459221/secrets/TELEGRAM_BOT_USERNAME/versions/latest" \
  --set-env-vars="JWT_SECRET_KEY_SECRET=projects/telepay-459221/secrets/JWT_SECRET_KEY/versions/latest" \
  --set-env-vars="BROADCAST_AUTO_INTERVAL_SECRET=projects/telepay-459221/secrets/BROADCAST_AUTO_INTERVAL/versions/latest" \
  --set-env-vars="BROADCAST_MANUAL_INTERVAL_SECRET=projects/telepay-459221/secrets/BROADCAST_MANUAL_INTERVAL/versions/latest" \
  --set-env-vars="CLOUD_SQL_CONNECTION_NAME_SECRET=projects/telepay-459221/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest" \
  --set-env-vars="DATABASE_NAME_SECRET=projects/telepay-459221/secrets/DATABASE_NAME_SECRET/versions/latest" \
  --set-env-vars="DATABASE_USER_SECRET=projects/telepay-459221/secrets/DATABASE_USER_SECRET/versions/latest" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/DATABASE_PASSWORD_SECRET/versions/latest" \
  --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql

# Check deployment status
if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"

    # Get service URL
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)")

    echo ""
    echo "🌐 Service URL: $SERVICE_URL"
    echo "📊 Health check: $SERVICE_URL/health"
    echo ""
    echo "🔍 To view logs:"
    echo "   gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME\" --project=$PROJECT_ID --limit=50 --format=json"
    echo ""
else
    echo "❌ Deployment failed!"
    exit 1
fi

echo "=========================================="
echo "✅ Deployment Complete"
echo "=========================================="
