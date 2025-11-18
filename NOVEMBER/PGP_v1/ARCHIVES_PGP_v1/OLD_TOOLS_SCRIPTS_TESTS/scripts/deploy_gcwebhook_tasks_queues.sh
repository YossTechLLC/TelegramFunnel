#!/bin/bash
# Deploy Cloud Tasks queues for PGP_v1 Orchestrator and Invite Services
# Run this script to create/update the queue configurations

set -e

PROJECT_ID="pgp-live"
LOCATION="us-central1"

echo "🚀 Deploying Cloud Tasks queues for PGP_v1 Orchestrator and Invite Services..."
echo "📍 Project: $PROJECT_ID"
echo "📍 Location: $LOCATION"

# =============================================================================
# Queue 1: pgp-invite-queue-v1 (pgp-orchestrator-v1 → pgp-invite-v1)
# =============================================================================

echo ""
echo "📨 Creating/Updating pgp-invite-queue-v1..."
echo "   Purpose: pgp-orchestrator-v1 → pgp-invite-v1 (Telegram invite dispatch)"
echo "   Rate: 8 dispatches/second (80% of Telegram bot API limit)"
echo "   Concurrency: 24 concurrent tasks"
echo "   Retry: Infinite for 24h (60s fixed backoff)"

gcloud tasks queues create pgp-invite-queue-v1 \
  --location=$LOCATION \
  --max-dispatches-per-second=8 \
  --max-concurrent-dispatches=24 \
  --max-attempts=-1 \
  --max-retry-duration=86400s \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-doublings=0 \
  2>/dev/null || \
gcloud tasks queues update pgp-invite-queue-v1 \
  --location=$LOCATION \
  --max-dispatches-per-second=8 \
  --max-concurrent-dispatches=24 \
  --max-attempts=-1 \
  --max-retry-duration=86400s \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-doublings=0

echo "✅ pgp-invite-queue-v1 configured successfully"

# =============================================================================
# Queue 2: Verify pgp-orchestrator-queue-v1 exists (pgp-orchestrator-v1 → pgp-split1-v1)
# =============================================================================

echo ""
echo "🔍 Verifying pgp-orchestrator-queue-v1 exists..."
echo "   Purpose: pgp-orchestrator-v1 → pgp-split1-v1 (Payment split dispatch)"

if gcloud tasks queues describe pgp-orchestrator-queue-v1 --location=$LOCATION &>/dev/null; then
    echo "✅ pgp-orchestrator-queue-v1 already exists"
else
    echo "⚠️  pgp-orchestrator-queue-v1 not found - creating..."
    gcloud tasks queues create pgp-orchestrator-queue-v1 \
      --location=$LOCATION \
      --max-dispatches-per-second=100 \
      --max-concurrent-dispatches=150 \
      --max-attempts=-1 \
      --max-retry-duration=86400s \
      --min-backoff=60s \
      --max-backoff=60s \
      --max-doublings=0
    echo "✅ pgp-orchestrator-queue-v1 created successfully"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "🎉 All Cloud Tasks queues for PGP_v1 Orchestrator and Invite Services deployed successfully!"
echo ""
echo "📊 Queue Summary:"
echo "   1. pgp-invite-queue-v1 (pgp-orchestrator-v1 → pgp-invite-v1)"
echo "   2. pgp-orchestrator-queue-v1 (pgp-orchestrator-v1 → pgp-split1-v1)"
echo ""
echo "📋 Next steps:"
echo "   1. Deploy pgp-orchestrator-v1 service: gcloud run deploy pgp-orchestrator-v1 ..."
echo "   2. Deploy pgp-invite-v1 service: gcloud run deploy pgp-invite-v1 ..."
echo "   3. Update service URLs in Secret Manager"
echo "   4. Test the full flow with a test payment"
