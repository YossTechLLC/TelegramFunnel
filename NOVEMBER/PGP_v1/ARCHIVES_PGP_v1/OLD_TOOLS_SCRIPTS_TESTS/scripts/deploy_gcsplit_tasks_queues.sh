#!/bin/bash
# ==============================================================================
# Cloud Tasks Queue Deployment Script for PGP_v1 Split Services
# Creates all required queues with appropriate retry configuration
# ==============================================================================

set -e  # Exit on error

# Configuration
PROJECT_ID="${CLOUD_TASKS_PROJECT_ID:-pgp-live}"
LOCATION="${CLOUD_TASKS_LOCATION:-us-central1}"

# Queue names
QUEUES=(
    "pgp-split1-estimate-queue-v1"
    "pgp-split1-response-queue-v1"
    "pgp-split2-swap-queue-v1"
    "pgp-split2-response-queue-v1"
    "pgp-hostpay-trigger-queue-v1"
)

# Retry configuration
# Note: Adjust max-dispatches-per-second and max-concurrent-dispatches based on:
# - ChangeNow API rate limits (typically ~10-20 RPS for standard plans)
# - Expected load
# - Target p95 latency
MAX_DISPATCHES_PER_SECOND=10
MAX_CONCURRENT_DISPATCHES=50
MAX_ATTEMPTS=-1          # Infinite retries
MAX_RETRY_DURATION=86400s  # 24 hours
MIN_BACKOFF=60s          # 60 second minimum backoff
MAX_BACKOFF=60s          # 60 second maximum backoff (no exponential backoff)
MAX_DOUBLINGS=0          # Disable exponential backoff

echo "🚀 [DEPLOY] Starting Cloud Tasks queue deployment"
echo "📍 [DEPLOY] Project: $PROJECT_ID"
echo "📍 [DEPLOY] Location: $LOCATION"
echo ""

# Function to create a queue
create_queue() {
    local queue_name=$1

    echo "📦 [DEPLOY] Creating queue: $queue_name"

    # Check if queue already exists
    if gcloud tasks queues describe "$queue_name" \
        --location="$LOCATION" \
        --project="$PROJECT_ID" &>/dev/null; then

        echo "⚠️ [DEPLOY] Queue $queue_name already exists, updating configuration..."

        # Update existing queue
        gcloud tasks queues update "$queue_name" \
            --location="$LOCATION" \
            --project="$PROJECT_ID" \
            --max-dispatches-per-second="$MAX_DISPATCHES_PER_SECOND" \
            --max-concurrent-dispatches="$MAX_CONCURRENT_DISPATCHES" \
            --max-attempts="$MAX_ATTEMPTS" \
            --max-retry-duration="$MAX_RETRY_DURATION" \
            --min-backoff="$MIN_BACKOFF" \
            --max-backoff="$MAX_BACKOFF" \
            --max-doublings="$MAX_DOUBLINGS"

        echo "✅ [DEPLOY] Queue $queue_name updated successfully"
    else
        # Create new queue
        gcloud tasks queues create "$queue_name" \
            --location="$LOCATION" \
            --project="$PROJECT_ID" \
            --max-dispatches-per-second="$MAX_DISPATCHES_PER_SECOND" \
            --max-concurrent-dispatches="$MAX_CONCURRENT_DISPATCHES" \
            --max-attempts="$MAX_ATTEMPTS" \
            --max-retry-duration="$MAX_RETRY_DURATION" \
            --min-backoff="$MIN_BACKOFF" \
            --max-backoff="$MAX_BACKOFF" \
            --max-doublings="$MAX_DOUBLINGS"

        echo "✅ [DEPLOY] Queue $queue_name created successfully"
    fi

    echo ""
}

# Create all queues
for queue in "${QUEUES[@]}"; do
    create_queue "$queue"
done

echo "🎉 [DEPLOY] All Cloud Tasks queues deployed successfully!"
echo ""
echo "📋 [DEPLOY] Deployed queues:"
for queue in "${QUEUES[@]}"; do
    echo "   ✓ $queue"
done
echo ""
echo "📊 [DEPLOY] Queue configuration:"
echo "   Max Dispatches/Second: $MAX_DISPATCHES_PER_SECOND"
echo "   Max Concurrent Dispatches: $MAX_CONCURRENT_DISPATCHES"
echo "   Max Attempts: $MAX_ATTEMPTS (infinite)"
echo "   Max Retry Duration: $MAX_RETRY_DURATION"
echo "   Backoff: $MIN_BACKOFF - $MAX_BACKOFF (fixed, no exponential)"
echo ""
echo "✅ [DEPLOY] Deployment complete!"
