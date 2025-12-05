#!/bin/bash
# Deploy actual_eth_amount fix to Cloud Run services
# Must deploy in REVERSE order (downstream first to maintain compatibility)

set -e  # Exit on error

echo "🚀 [DEPLOY] Starting actual_eth_amount deployment..."
echo "📋 [DEPLOY] Deployment order: Downstream → Upstream (for compatibility)"
echo ""

# Project and region
PROJECT_ID="pgp-live"
REGION="us-central1"
BASE_DIR="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26"

# Service order (downstream first for backward compatibility)
# Format: "directory:service-name"
SERVICES=(
    "PGP_HOSTPAY3_v1:pgp-hostpay3-v1"
    "PGP_HOSTPAY1_v1:pgp-hostpay1-v1"
    "PGP_SPLIT3_v1:pgp-split3-v1"
    "PGP_SPLIT2_v1:pgp-split2-v1"
    "PGP_SPLIT1_v1:pgp-split1-v1"
    "PGP_ORCHESTRATOR_v1:pgp-orchestrator-v1"
    "PGP_BATCHPROCESSOR_v1:pgp_batchprocessor-10-26"
    "PGP_MICROBATCHPROCESSOR_v1:pgp_microbatchprocessor-10-26"
)

# Track deployment progress
TOTAL_SERVICES=${#SERVICES[@]}
CURRENT=0

for service in "${SERVICES[@]}"; do
    IFS=':' read -r dir name <<< "$service"
    CURRENT=$((CURRENT + 1))

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📦 [DEPLOY] [$CURRENT/$TOTAL_SERVICES] Deploying $name..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    cd "$BASE_DIR/$dir"

    # Build container image
    echo "🔨 [BUILD] Building container image..."
    gcloud builds submit \
        --tag "gcr.io/$PROJECT_ID/$name" \
        --project="$PROJECT_ID" \
        --quiet

    if [ $? -ne 0 ]; then
        echo "❌ [BUILD] Failed to build $name"
        exit 1
    fi

    echo "✅ [BUILD] Container image built successfully"
    echo ""

    # Deploy to Cloud Run
    echo "☁️  [DEPLOY] Deploying to Cloud Run..."
    gcloud run deploy "$name" \
        --image "gcr.io/$PROJECT_ID/$name" \
        --region "$REGION" \
        --project="$PROJECT_ID" \
        --quiet

    if [ $? -ne 0 ]; then
        echo "❌ [DEPLOY] Failed to deploy $name"
        exit 1
    fi

    echo "✅ [DEPLOY] $name deployed successfully"
    echo ""

    # Wait 30 seconds between deployments (except for last service)
    if [ $CURRENT -lt $TOTAL_SERVICES ]; then
        echo "⏱️  [WAIT] Waiting 30 seconds before next deployment..."
        sleep 30
        echo ""
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 [DEPLOY] All services deployed successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 [SUMMARY] Deployed services:"
for service in "${SERVICES[@]}"; do
    IFS=':' read -r dir name <<< "$service"
    echo "   ✅ $name"
done
echo ""
echo "🔍 [NEXT] Verify deployments with:"
echo "   gcloud run services list --region=$REGION --project=$PROJECT_ID"
