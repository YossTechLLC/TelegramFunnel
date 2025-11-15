#!/bin/bash

# Redeploy GCRegisterAPI-10-26
# This script:
# 1. Deletes the deprecated gcregister10-26 service
# 2. Redeploys gcregisterapi-10-26 with correct configuration

set -e  # Exit on error

PROJECT_ID="telepay-459221"
REGION="us-central1"
SERVICE_NAME="gcregisterapi-10-26"
DEPRECATED_SERVICE="gcregister10-26"

echo "========================================="
echo "🚀 GCRegisterAPI-10-26 Redeployment"
echo "========================================="
echo ""

# Step 1: Delete deprecated gcregister10-26
echo "📋 Step 1: Checking for deprecated service..."
if gcloud run services describe $DEPRECATED_SERVICE --region=$REGION --project=$PROJECT_ID &>/dev/null; then
    echo "⚠️  Found deprecated service: $DEPRECATED_SERVICE"
    echo "🗑️  Deleting $DEPRECATED_SERVICE..."

    gcloud run services delete $DEPRECATED_SERVICE \
        --region=$REGION \
        --project=$PROJECT_ID \
        --quiet

    echo "✅ Deleted $DEPRECATED_SERVICE"
else
    echo "✅ Deprecated service not found (already deleted)"
fi

echo ""

# Step 2: Build and deploy gcregisterapi-10-26
echo "📋 Step 2: Building and deploying $SERVICE_NAME..."
echo ""

cd "$(dirname "$0")/../../GCRegisterAPI-10-26"

echo "📦 Building Docker image..."
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --project=$PROJECT_ID

echo ""
echo "🚀 Deploying to Cloud Run..."

gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --region=$REGION \
    --project=$PROJECT_ID \
    --platform managed \
    --allow-unauthenticated \
    --memory 8Gi \
    --cpu 4 \
    --timeout 300 \
    --concurrency 80 \
    --max-instances 2 \
    --min-instances 0 \
    --port 8080 \
    --add-cloudsql-instances=$PROJECT_ID:$REGION:telepaypsql \
    --set-secrets="JWT_SECRET_KEY=JWT_SECRET_KEY:latest,CORS_ORIGIN=CORS_ORIGIN:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,SIGNUP_SECRET_KEY=SIGNUP_SECRET_KEY:latest,SENDGRID_API_KEY=SENDGRID_API_KEY:latest,FROM_EMAIL=FROM_EMAIL:latest,FROM_NAME=FROM_NAME:latest,BASE_URL=BASE_URL:latest" \
    --set-env-vars="ENVIRONMENT=production"

echo ""
echo "========================================="
echo "✅ Deployment Complete!"
echo "========================================="
echo ""
echo "Service URL:"
gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID --format="value(status.url)"
echo ""
echo "📊 Verify deployment:"
echo "   gcloud run services describe $SERVICE_NAME --region=$REGION"
echo ""
