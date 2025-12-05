#!/bin/bash
################################################################################
# Deploy GCRegisterWeb-10-26 (Frontend)
# Purpose: Build and deploy frontend with notification settings UI
# Version: 1.0
# Date: 2025-11-11
################################################################################

set -e  # Exit on error

echo ""
echo "========================================================================"
echo "🚀 Deploying GCRegisterWeb-10-26 (Frontend)"
echo "========================================================================"
echo ""

# Configuration
BUCKET_NAME="www-paygateprime-com"
SOURCE_DIR="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCRegisterWeb-10-26"

echo "📋 Configuration:"
echo "   Bucket: $BUCKET_NAME"
echo "   Source: $SOURCE_DIR"
echo ""

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Error: Source directory not found: $SOURCE_DIR"
    exit 1
fi

cd "$SOURCE_DIR"

echo "📦 Installing dependencies..."
npm install

echo ""
echo "🏗️ Building production bundle..."
npm run build

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

echo ""
echo "📤 Uploading to Cloud Storage..."
gsutil -m rsync -r -d dist/ gs://$BUCKET_NAME/

if [ $? -eq 0 ]; then
    echo ""
    echo "🔧 Setting cache control headers..."

    # HTML files - no cache
    gsutil -m setmeta -h "Cache-Control:no-cache, no-store, must-revalidate" gs://$BUCKET_NAME/index.html

    # Static assets - long cache
    gsutil -m setmeta -h "Cache-Control:public, max-age=31536000, immutable" "gs://$BUCKET_NAME/assets/**"

    echo ""
    echo "========================================================================"
    echo "✅ Frontend deployed successfully!"
    echo "========================================================================"
    echo ""
    echo "🌐 Website URL: https://www.paygateprime.com"
    echo ""
    echo "ℹ️ Note: CDN cache may take a few minutes to update"
    echo ""
    exit 0
else
    echo ""
    echo "========================================================================"
    echo "❌ Deployment failed!"
    echo "========================================================================"
    echo ""
    exit 1
fi
