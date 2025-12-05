#!/bin/bash
################################################################################
# Deploy GCRegisterAPI-10-26 (Backend API)
# Purpose: Deploy updated backend API with notification fields support
# Version: 1.0
# Date: 2025-11-11
################################################################################

set -e  # Exit on error

echo ""
echo "========================================================================"
echo "🚀 Deploying GCRegisterAPI-10-26 (Backend API)"
echo "========================================================================"
echo ""

# Configuration
SERVICE_NAME="gcregisterapi-10-26"
REGION="us-central1"
SOURCE_DIR="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCRegisterAPI-10-26"

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

echo "📦 Building and deploying service..."
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --timeout=300 \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=10

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================================================"
    echo "✅ GCRegisterAPI-10-26 deployed successfully!"
    echo "========================================================================"
    echo ""

    # Get service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
    echo "🌐 Service URL: $SERVICE_URL"
    echo ""

    # Test health endpoint
    echo "🏥 Testing health endpoint..."
    curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/health" || echo "Health check endpoint not available"
    echo ""
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
