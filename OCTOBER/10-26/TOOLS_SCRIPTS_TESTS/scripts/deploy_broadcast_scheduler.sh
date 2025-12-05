#!/bin/bash

# Deploy GCBroadcastScheduler-10-26 to Cloud Run
# This script deploys the broadcast scheduler service with all required environment variables

set -e  # Exit on error

PROJECT_ID="telepay-459221"
REGION="us-central1"
SERVICE_NAME="gcbroadcastscheduler-10-26"
SOURCE_DIR="./GCBroadcastScheduler-10-26"

echo "🚀 Starting deployment of $SERVICE_NAME to Cloud Run..."
echo "📍 Project: $PROJECT_ID"
echo "🌍 Region: $REGION"
echo "📂 Source: $SOURCE_DIR"
echo ""

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Error: Source directory $SOURCE_DIR not found"
    echo "Please run this script from the OCTOBER/10-26 directory"
    exit 1
fi

echo "🏗️  Building and deploying service..."
echo ""

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
    --source="$SOURCE_DIR" \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=1 \
    --memory=512Mi \
    --cpu=1 \
    --timeout=300s \
    --concurrency=1 \
    --set-env-vars="BROADCAST_AUTO_INTERVAL_SECRET=projects/${PROJECT_ID}/secrets/BROADCAST_AUTO_INTERVAL/versions/latest" \
    --set-env-vars="BROADCAST_MANUAL_INTERVAL_SECRET=projects/${PROJECT_ID}/secrets/BROADCAST_MANUAL_INTERVAL/versions/latest" \
    --set-env-vars="BOT_TOKEN_SECRET=projects/${PROJECT_ID}/secrets/BOT_TOKEN/versions/latest" \
    --set-env-vars="BOT_USERNAME_SECRET=projects/${PROJECT_ID}/secrets/BOT_USERNAME/versions/latest" \
    --set-env-vars="JWT_SECRET_KEY_SECRET=projects/${PROJECT_ID}/secrets/JWT_SECRET_KEY/versions/latest" \
    --set-env-vars="DATABASE_HOST_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_HOST/versions/latest" \
    --set-env-vars="DATABASE_NAME_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_NAME/versions/latest" \
    --set-env-vars="DATABASE_USER_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_USER/versions/latest" \
    --set-env-vars="DATABASE_PASSWORD_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_PASSWORD/versions/latest" \
    --project=$PROJECT_ID

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment successful!"
    echo ""
    echo "📝 Service URL:"
    gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)" --project=$PROJECT_ID
    echo ""
    echo "🔍 Test the service:"
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)" --project=$PROJECT_ID)
    echo "  Health check: curl $SERVICE_URL/health"
    echo ""
else
    echo ""
    echo "❌ Deployment failed!"
    exit 1
fi
