#!/bin/bash
# Setup Google Cloud Secret Manager secrets for GCWebhook1 and GCWebhook2
# Run this script after deploying the services to set their URLs

set -e

PROJECT_ID="telepay-f7f59"
LOCATION="us-central1"

echo "🔐 Setting up Secret Manager secrets for GCWebhook services..."
echo "📍 Project: $PROJECT_ID"

# =============================================================================
# Instructions
# =============================================================================

echo ""
echo "📋 This script will help you set up the following secrets:"
echo "   1. GCWEBHOOK2_URL - GCWebhook2 service URL"
echo "   2. GCWEBHOOK2_QUEUE - GCWebhook2 queue name"
echo "   3. GCSPLIT1_QUEUE - GCSplit1 queue name (for GCWebhook1 → GCSplit1)"
echo ""
echo "⚠️  You must deploy the services first to get their URLs!"
echo ""

# =============================================================================
# Get GCWebhook2 URL
# =============================================================================

echo "🔍 Step 1: Getting GCWebhook2 service URL..."
echo ""
echo "Run this command to get the URL:"
echo "gcloud run services describe gcwebhook2-10-26 --region=$LOCATION --format='value(status.url)'"
echo ""
read -p "Enter GCWebhook2 URL (or press Enter to skip): " GCWEBHOOK2_URL

if [ -n "$GCWEBHOOK2_URL" ]; then
    echo "📝 Creating/Updating GCWEBHOOK2_URL secret..."
    echo -n "$GCWEBHOOK2_URL" | gcloud secrets create GCWEBHOOK2_URL \
      --data-file=- \
      --replication-policy="automatic" \
      2>/dev/null || \
    echo -n "$GCWEBHOOK2_URL" | gcloud secrets versions add GCWEBHOOK2_URL \
      --data-file=-

    GCWEBHOOK2_URL_SECRET="projects/$PROJECT_ID/secrets/GCWEBHOOK2_URL/versions/latest"
    echo "✅ GCWEBHOOK2_URL secret created: $GCWEBHOOK2_URL_SECRET"
else
    echo "⏭️  Skipped GCWEBHOOK2_URL"
fi

# =============================================================================
# Set GCWEBHOOK2_QUEUE
# =============================================================================

echo ""
echo "📝 Step 2: Setting GCWEBHOOK2_QUEUE secret..."
GCWEBHOOK2_QUEUE="gcwebhook-telegram-invite-queue"
echo "   Queue name: $GCWEBHOOK2_QUEUE"

echo -n "$GCWEBHOOK2_QUEUE" | gcloud secrets create GCWEBHOOK2_QUEUE \
  --data-file=- \
  --replication-policy="automatic" \
  2>/dev/null || \
echo -n "$GCWEBHOOK2_QUEUE" | gcloud secrets versions add GCWEBHOOK2_QUEUE \
  --data-file=-

GCWEBHOOK2_QUEUE_SECRET="projects/$PROJECT_ID/secrets/GCWEBHOOK2_QUEUE/versions/latest"
echo "✅ GCWEBHOOK2_QUEUE secret created: $GCWEBHOOK2_QUEUE_SECRET"

# =============================================================================
# Set GCSPLIT1_QUEUE
# =============================================================================

echo ""
echo "📝 Step 3: Setting GCSPLIT1_QUEUE secret (for GCWebhook1 → GCSplit1)..."
GCSPLIT1_QUEUE="gcsplit-webhook-queue"
echo "   Queue name: $GCSPLIT1_QUEUE"

echo -n "$GCSPLIT1_QUEUE" | gcloud secrets create GCSPLIT1_QUEUE \
  --data-file=- \
  --replication-policy="automatic" \
  2>/dev/null || \
echo -n "$GCSPLIT1_QUEUE" | gcloud secrets versions add GCSPLIT1_QUEUE \
  --data-file=-

GCSPLIT1_QUEUE_SECRET="projects/$PROJECT_ID/secrets/GCSPLIT1_QUEUE/versions/latest"
echo "✅ GCSPLIT1_QUEUE secret created: $GCSPLIT1_QUEUE_SECRET"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "🎉 Secret Manager setup completed!"
echo ""
echo "📊 Created/Updated secrets:"
if [ -n "$GCWEBHOOK2_URL" ]; then
    echo "   ✅ GCWEBHOOK2_URL: $GCWEBHOOK2_URL_SECRET"
fi
echo "   ✅ GCWEBHOOK2_QUEUE: $GCWEBHOOK2_QUEUE_SECRET"
echo "   ✅ GCSPLIT1_QUEUE: $GCSPLIT1_QUEUE_SECRET"
echo ""
echo "📋 Environment variables to set for GCWebhook1:"
if [ -n "$GCWEBHOOK2_URL" ]; then
    echo "   GCWEBHOOK2_URL=$GCWEBHOOK2_URL_SECRET"
fi
echo "   GCWEBHOOK2_QUEUE=$GCWEBHOOK2_QUEUE_SECRET"
echo "   GCSPLIT1_QUEUE=$GCSPLIT1_QUEUE_SECRET"
echo ""
echo "📋 Environment variables to set for GCWebhook2:"
echo "   SUCCESS_URL_SIGNING_KEY=projects/$PROJECT_ID/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest"
echo "   TELEGRAM_BOT_SECRET_NAME=projects/$PROJECT_ID/secrets/TELEGRAM_BOT_TOKEN/versions/latest"
echo ""
echo "📋 Next steps:"
echo "   1. Update GCWebhook1 service with new environment variables"
echo "   2. Update GCWebhook2 service with new environment variables"
echo "   3. Test the full flow with a test payment"
