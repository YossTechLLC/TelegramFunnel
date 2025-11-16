#!/bin/bash
# Deploy Cloud Tasks queues for GCWebhook1 and GCWebhook2
# Run this script to create/update the queue configurations

set -e

PROJECT_ID="pgp-live"
LOCATION="us-central1"

echo "🚀 Deploying Cloud Tasks queues for GCWebhook services..."
echo "📍 Project: $PROJECT_ID"
echo "📍 Location: $LOCATION"

# =============================================================================
# Queue 1: gcwebhook-telegram-invite-queue (GCWebhook1 → GCWebhook2)
# =============================================================================

echo ""
echo "📨 Creating/Updating gcwebhook-telegram-invite-queue..."
echo "   Purpose: GCWebhook1 → GCWebhook2 (Telegram invite dispatch)"
echo "   Rate: 8 dispatches/second (80% of Telegram bot API limit)"
echo "   Concurrency: 24 concurrent tasks"
echo "   Retry: Infinite for 24h (60s fixed backoff)"

gcloud tasks queues create gcwebhook-telegram-invite-queue \
  --location=$LOCATION \
  --max-dispatches-per-second=8 \
  --max-concurrent-dispatches=24 \
  --max-attempts=-1 \
  --max-retry-duration=86400s \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-doublings=0 \
  2>/dev/null || \
gcloud tasks queues update gcwebhook-telegram-invite-queue \
  --location=$LOCATION \
  --max-dispatches-per-second=8 \
  --max-concurrent-dispatches=24 \
  --max-attempts=-1 \
  --max-retry-duration=86400s \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-doublings=0

echo "✅ gcwebhook-telegram-invite-queue configured successfully"

# =============================================================================
# Queue 2: Verify gcsplit-webhook-queue still exists (GCWebhook1 → GCSplit1)
# =============================================================================

echo ""
echo "🔍 Verifying gcsplit-webhook-queue exists..."
echo "   Purpose: GCWebhook1 → GCSplit1 (Payment split dispatch)"

if gcloud tasks queues describe gcsplit-webhook-queue --location=$LOCATION &>/dev/null; then
    echo "✅ gcsplit-webhook-queue already exists"
else
    echo "⚠️  gcsplit-webhook-queue not found - creating..."
    gcloud tasks queues create gcsplit-webhook-queue \
      --location=$LOCATION \
      --max-dispatches-per-second=100 \
      --max-concurrent-dispatches=150 \
      --max-attempts=-1 \
      --max-retry-duration=86400s \
      --min-backoff=60s \
      --max-backoff=60s \
      --max-doublings=0
    echo "✅ gcsplit-webhook-queue created successfully"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "🎉 All Cloud Tasks queues for GCWebhook services deployed successfully!"
echo ""
echo "📊 Queue Summary:"
echo "   1. gcwebhook-telegram-invite-queue (GCWebhook1 → GCWebhook2)"
echo "   2. gcsplit-webhook-queue (GCWebhook1 → GCSplit1)"
echo ""
echo "📋 Next steps:"
echo "   1. Deploy GCWebhook1 service: gcloud run deploy gcwebhook1-10-26 ..."
echo "   2. Deploy GCWebhook2 service: gcloud run deploy gcwebhook2-10-26 ..."
echo "   3. Update service URLs in Secret Manager"
echo "   4. Test the full flow with a test payment"
