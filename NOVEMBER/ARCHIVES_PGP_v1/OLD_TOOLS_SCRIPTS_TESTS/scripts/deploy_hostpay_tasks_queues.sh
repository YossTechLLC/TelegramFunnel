#!/bin/bash
# ==============================================================================
# Cloud Tasks Queue Deployment Script for PGP_v1 HostPay Services
# Creates all 4 queues required for the split pgp-hostpay-v1 microservices architecture
# ==============================================================================

set -e  # Exit on error

# Configuration
PROJECT_ID="${CLOUD_TASKS_PROJECT_ID:-pgp-live}"
LOCATION="${CLOUD_TASKS_LOCATION:-us-central1}"

# Retry configuration (shared across all queues)
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

echo "🚀 [DEPLOY] Starting Cloud Tasks queue deployment for PGP_v1 HostPay Services"
echo "📍 [DEPLOY] Project: $PROJECT_ID"
echo "📍 [DEPLOY] Location: $LOCATION"
echo ""

# =============================================================================
# Define all 4 queues required for GCHostPay architecture
# =============================================================================

# Queue 1: pgp-split1-v1 → pgp-hostpay1-v1 (Initial payment request)
QUEUE_1_NAME="pgp-hostpay-trigger-queue-v1"
QUEUE_1_PURPOSE="pgp-split1-v1 → pgp-hostpay1-v1 (Initial ETH payment orchestration request)"

# Queue 2: pgp-hostpay1-v1 → pgp-hostpay2-v1 (ChangeNow status check)
QUEUE_2_NAME="pgp-hostpay2-status-queue-v1"
QUEUE_2_PURPOSE="pgp-hostpay1-v1 → pgp-hostpay2-v1 (ChangeNow status verification with infinite retry)"

# Queue 3: pgp-hostpay1-v1 → pgp-hostpay3-v1 (ETH payment execution)
QUEUE_3_NAME="pgp-hostpay3-payment-queue-v1"
QUEUE_3_PURPOSE="pgp-hostpay1-v1 → pgp-hostpay3-v1 (ETH blockchain payment execution with infinite retry)"

# Queue 4: pgp-hostpay2/3-v1 → pgp-hostpay1-v1 (Response callbacks)
QUEUE_4_NAME="pgp-hostpay1-response-queue-v1"
QUEUE_4_PURPOSE="pgp-hostpay2-v1/pgp-hostpay3-v1 → pgp-hostpay1-v1 (Status verification and payment completion responses)"

# Array of all queues
declare -a QUEUES=(
    "$QUEUE_1_NAME|$QUEUE_1_PURPOSE"
    "$QUEUE_2_NAME|$QUEUE_2_PURPOSE"
    "$QUEUE_3_NAME|$QUEUE_3_PURPOSE"
    "$QUEUE_4_NAME|$QUEUE_4_PURPOSE"
)

# =============================================================================
# Create/Update all queues
# =============================================================================

for QUEUE_INFO in "${QUEUES[@]}"; do
    # Split queue name and purpose
    IFS='|' read -r QUEUE_NAME QUEUE_PURPOSE <<< "$QUEUE_INFO"

    echo "═══════════════════════════════════════════════════════════════════════════"
    echo "💼 [DEPLOY] Processing: $QUEUE_NAME"
    echo "   Purpose: $QUEUE_PURPOSE"
    echo "   Rate: $MAX_DISPATCHES_PER_SECOND dispatches/second"
    echo "   Concurrency: $MAX_CONCURRENT_DISPATCHES concurrent tasks"
    echo "   Retry: Infinite for 24h (60s fixed backoff)"
    echo ""

    # Check if queue already exists
    if gcloud tasks queues describe "$QUEUE_NAME" \
        --location="$LOCATION" \
        --project="$PROJECT_ID" &>/dev/null; then

        echo "⚠️  [DEPLOY] Queue $QUEUE_NAME already exists, updating configuration..."

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
        echo "🆕 [DEPLOY] Queue $QUEUE_NAME does not exist, creating new queue..."

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
done

# =============================================================================
# Summary
# =============================================================================

echo "═══════════════════════════════════════════════════════════════════════════"
echo "🎉 [DEPLOY] All Cloud Tasks queues for PGP_v1 HostPay Services deployed successfully!"
echo ""
echo "📊 [DEPLOY] Queue Summary:"
echo ""
echo "   1️⃣  $QUEUE_1_NAME"
echo "      └─ $QUEUE_1_PURPOSE"
echo ""
echo "   2️⃣  $QUEUE_2_NAME"
echo "      └─ $QUEUE_2_PURPOSE"
echo ""
echo "   3️⃣  $QUEUE_3_NAME"
echo "      └─ $QUEUE_3_PURPOSE"
echo ""
echo "   4️⃣  $QUEUE_4_NAME"
echo "      └─ $QUEUE_4_PURPOSE"
echo ""
echo "⚙️  [DEPLOY] Shared Configuration:"
echo "   • Max Dispatches/Second: $MAX_DISPATCHES_PER_SECOND"
echo "   • Max Concurrent Dispatches: $MAX_CONCURRENT_DISPATCHES"
echo "   • Max Attempts: $MAX_ATTEMPTS (infinite)"
echo "   • Max Retry Duration: $MAX_RETRY_DURATION"
echo "   • Backoff: $MIN_BACKOFF - $MAX_BACKOFF (fixed, no exponential)"
echo ""
echo "📋 [DEPLOY] Next steps:"
echo "   1. Deploy pgp-hostpay1-v1 service: gcloud run deploy pgp-hostpay1-v1 ..."
echo "   2. Deploy pgp-hostpay2-v1 service: gcloud run deploy pgp-hostpay2-v1 ..."
echo "   3. Deploy pgp-hostpay3-v1 service: gcloud run deploy pgp-hostpay3-v1 ..."
echo "   4. Update Secret Manager with queue names:"
echo "      • PGP_HOSTPAY2_QUEUE=$QUEUE_2_NAME"
echo "      • PGP_HOSTPAY3_QUEUE=$QUEUE_3_NAME"
echo "      • PGP_HOSTPAY1_RESPONSE_QUEUE=$QUEUE_4_NAME"
echo "   5. Update PGP_HOSTPAY1_URL, PGP_HOSTPAY2_URL, PGP_HOSTPAY3_URL in Secret Manager"
echo "   6. Test end-to-end workflow: pgp-split1-v1 → pgp-hostpay1-v1 → pgp-hostpay2-v1 → pgp-hostpay3-v1"
echo ""
echo "✅ [DEPLOY] Deployment complete!"
echo "═══════════════════════════════════════════════════════════════════════════"
