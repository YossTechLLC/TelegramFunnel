#!/bin/bash
# ==============================================================================
# Cloud Tasks Queue Deployment Script for GCHostPay Service
# Creates the queue required for ETH payment processing from GCSplit
# ==============================================================================

set -e  # Exit on error

# Configuration
PROJECT_ID="${CLOUD_TASKS_PROJECT_ID:-telepay-459221}"
LOCATION="${CLOUD_TASKS_LOCATION:-us-central1}"

# Queue name
QUEUE_NAME="gcsplit-hostpay-trigger-queue"

# Retry configuration
# Note: Conservative rate limits for blockchain transactions
# - Ethereum RPC providers typically have 10-100 RPS limits
# - Each ETH transaction takes time to sign, send, and confirm
# - 5 RPS ensures we don't overload the wallet manager or RPC provider
MAX_DISPATCHES_PER_SECOND=5
MAX_CONCURRENT_DISPATCHES=10
MAX_ATTEMPTS=-1          # Infinite retries
MAX_RETRY_DURATION=86400s  # 24 hours
MIN_BACKOFF=60s          # 60 second minimum backoff
MAX_BACKOFF=60s          # 60 second maximum backoff (no exponential backoff)
MAX_DOUBLINGS=0          # Disable exponential backoff

echo "🚀 [DEPLOY] Starting Cloud Tasks queue deployment for GCHostPay"
echo "📍 [DEPLOY] Project: $PROJECT_ID"
echo "📍 [DEPLOY] Location: $LOCATION"
echo ""

# =============================================================================
# Queue: gcsplit-hostpay-trigger-queue (GCSplit1 → GCHostPay)
# =============================================================================

echo "💰 [DEPLOY] Creating/Updating $QUEUE_NAME..."
echo "   Purpose: GCSplit1 → GCHostPay (ETH payment dispatch)"
echo "   Rate: $MAX_DISPATCHES_PER_SECOND dispatches/second (conservative for blockchain transactions)"
echo "   Concurrency: $MAX_CONCURRENT_DISPATCHES concurrent tasks"
echo "   Retry: Infinite for 24h (60s fixed backoff)"
echo ""

# Check if queue already exists
if gcloud tasks queues describe "$QUEUE_NAME" \
    --location="$LOCATION" \
    --project="$PROJECT_ID" &>/dev/null; then

    echo "⚠️ [DEPLOY] Queue $QUEUE_NAME already exists, updating configuration..."

    # Update existing queue
    gcloud tasks queues update "$QUEUE_NAME" \
        --location="$LOCATION" \
        --project="$PROJECT_ID" \
        --max-dispatches-per-second="$MAX_DISPATCHES_PER_SECOND" \
        --max-concurrent-dispatches="$MAX_CONCURRENT_DISPATCHES" \
        --max-attempts="$MAX_ATTEMPTS" \
        --max-retry-duration="$MAX_RETRY_DURATION" \
        --min-backoff="$MIN_BACKOFF" \
        --max-backoff="$MAX_BACKOFF" \
        --max-doublings="$MAX_DOUBLINGS"

    echo "✅ [DEPLOY] Queue $QUEUE_NAME updated successfully"
else
    # Create new queue
    gcloud tasks queues create "$QUEUE_NAME" \
        --location="$LOCATION" \
        --project="$PROJECT_ID" \
        --max-dispatches-per-second="$MAX_DISPATCHES_PER_SECOND" \
        --max-concurrent-dispatches="$MAX_CONCURRENT_DISPATCHES" \
        --max-attempts="$MAX_ATTEMPTS" \
        --max-retry-duration="$MAX_RETRY_DURATION" \
        --min-backoff="$MIN_BACKOFF" \
        --max-backoff="$MAX_BACKOFF" \
        --max-doublings="$MAX_DOUBLINGS"

    echo "✅ [DEPLOY] Queue $QUEUE_NAME created successfully"
fi

echo ""

# =============================================================================
# Summary
# =============================================================================

echo "🎉 [DEPLOY] Cloud Tasks queue for GCHostPay deployed successfully!"
echo ""
echo "📊 [DEPLOY] Queue configuration:"
echo "   Queue Name: $QUEUE_NAME"
echo "   Max Dispatches/Second: $MAX_DISPATCHES_PER_SECOND"
echo "   Max Concurrent Dispatches: $MAX_CONCURRENT_DISPATCHES"
echo "   Max Attempts: $MAX_ATTEMPTS (infinite)"
echo "   Max Retry Duration: $MAX_RETRY_DURATION"
echo "   Backoff: $MIN_BACKOFF - $MAX_BACKOFF (fixed, no exponential)"
echo ""
echo "📋 [DEPLOY] Next steps:"
echo "   1. Deploy GCHostPay service: gcloud run deploy gchostpay10-26 ..."
echo "   2. Update HOSTPAY_URL in Secret Manager"
echo "   3. Ensure HOSTPAY_QUEUE secret = $QUEUE_NAME"
echo "   4. Test ETH payment flow from GCSplit1"
echo ""
echo "✅ [DEPLOY] Deployment complete!"
