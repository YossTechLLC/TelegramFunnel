#!/bin/bash
# ==============================================================================
# Cloud Tasks Queue Deployment Script for PGP_v1 Accumulator & Batch Processor
# Creates all required queues for pgp-accumulator-v1 and pgp-batchprocessor-v1
# ==============================================================================

set -e  # Exit on error

# Configuration
PROJECT_ID="${CLOUD_TASKS_PROJECT_ID:-pgp-live}"
LOCATION="${CLOUD_TASKS_LOCATION:-us-central1}"

# Queue names
QUEUES=(
    "pgp-accumulator-queue-v1"
    "pgp-batchprocessor-queue-v1"
)

# Retry configuration
# Note: Threshold payout system uses same retry config as other services
MAX_DISPATCHES_PER_SECOND=10
MAX_CONCURRENT_DISPATCHES=50
MAX_ATTEMPTS=-1          # Infinite retries
MAX_RETRY_DURATION=86400s  # 24 hours
MIN_BACKOFF=60s          # 60 second minimum backoff
MAX_BACKOFF=60s          # 60 second maximum backoff (no exponential backoff)
MAX_DOUBLINGS=0          # Disable exponential backoff

echo "🚀 [DEPLOY] Starting Cloud Tasks queue deployment (Threshold Payout)"
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
echo "📝 [DEPLOY] Next steps:"
echo "   1. Deploy pgp-accumulator-v1 service"
echo "   2. Deploy pgp-batchprocessor-v1 service"
echo "   3. Update Secret Manager with:"
echo "      - PGP_ACCUMULATOR_QUEUE=pgp-accumulator-queue-v1"
echo "      - PGP_ACCUMULATOR_URL=https://pgp-accumulator-v1-SERVICE_URL"
echo "      - PGP_BATCHPROCESSOR_QUEUE=pgp-batchprocessor-queue-v1"
echo "   4. Create Cloud Scheduler job:"
echo "      gcloud scheduler jobs create http pgp-batchprocessor-job \\"
echo "        --schedule=\"*/5 * * * *\" \\"
echo "        --uri=\"https://pgp-batchprocessor-v1-SERVICE_URL/process\" \\"
echo "        --http-method=POST \\"
echo "        --location=$LOCATION \\"
echo "        --time-zone=\"America/Los_Angeles\""
echo ""
echo "✅ [DEPLOY] Deployment complete!"

