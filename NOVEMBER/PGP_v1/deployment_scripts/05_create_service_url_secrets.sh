#!/bin/bash
# Create Service URL Secrets
# DO NOT EXECUTE - Run this AFTER deploying all Cloud Run services
# This script will fetch actual service URLs and create secrets

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"

echo "🌐 Creating Service URL Secrets"
echo "================================="
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Region: $REGION"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
echo "📋 Project Number: $PROJECT_NUMBER"
echo ""

# =============================================================================
# SERVICE URLS - Fetched from Cloud Run
# =============================================================================

echo "Fetching service URLs from Cloud Run..."
echo ""

# Function to get service URL
get_service_url() {
    local service_name=$1
    local url=$(gcloud run services describe $service_name --region=$REGION --format="value(status.url)" 2>/dev/null)
    if [ -z "$url" ]; then
        echo "   ⚠️  WARNING: Service '$service_name' not found or not deployed"
        return 1
    fi
    echo "$url"
}

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    if gcloud secrets describe $secret_name --project=$PROJECT_ID &>/dev/null; then
        echo "   🔄 Updating existing secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=- --project=$PROJECT_ID
    else
        echo "   ✨ Creating new secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=- --project=$PROJECT_ID
    fi
    echo "   ✅ $secret_name = $secret_value"
}

# GCWEBHOOK1_URL
echo "🔗 GCWEBHOOK1_URL..."
GCWEBHOOK1_URL=$(get_service_url "gcwebhook1-pgp")
if [ $? -eq 0 ]; then
    create_or_update_secret "GCWEBHOOK1_URL" "$GCWEBHOOK1_URL"
fi
echo ""

# GCWEBHOOK2_URL
echo "🔗 GCWEBHOOK2_URL..."
GCWEBHOOK2_URL=$(get_service_url "gcwebhook2-pgp")
if [ $? -eq 0 ]; then
    create_or_update_secret "GCWEBHOOK2_URL" "$GCWEBHOOK2_URL"
fi
echo ""

# GCSPLIT1_URL
echo "🔗 GCSPLIT1_URL..."
GCSPLIT1_URL=$(get_service_url "gcsplit1-pgp")
if [ $? -eq 0 ]; then
    create_or_update_secret "GCSPLIT1_URL" "$GCSPLIT1_URL"
fi
echo ""

# GCSPLIT2_URL
echo "🔗 GCSPLIT2_URL..."
GCSPLIT2_URL=$(get_service_url "gcsplit2-pgp")
if [ $? -eq 0 ]; then
    create_or_update_secret "GCSPLIT2_URL" "$GCSPLIT2_URL"
fi
echo ""

# GCSPLIT3_URL
echo "🔗 GCSPLIT3_URL..."
GCSPLIT3_URL=$(get_service_url "gcsplit3-pgp")
if [ $? -eq 0 ]; then
    create_or_update_secret "GCSPLIT3_URL" "$GCSPLIT3_URL"
fi
echo ""

# GCACCUMULATOR_URL
echo "🔗 GCACCUMULATOR_URL..."
GCACCUMULATOR_URL=$(get_service_url "gcaccumulator-pgp")
if [ $? -eq 0 ]; then
    create_or_update_secret "GCACCUMULATOR_URL" "$GCACCUMULATOR_URL"
fi
echo ""

# GCHOSTPAY1_URL
echo "🔗 GCHOSTPAY1_URL..."
GCHOSTPAY1_URL=$(get_service_url "gchostpay1-pgp")
if [ $? -eq 0 ]; then
    create_or_update_secret "GCHOSTPAY1_URL" "$GCHOSTPAY1_URL"
fi
echo ""

# GCHOSTPAY2_URL
echo "🔗 GCHOSTPAY2_URL..."
GCHOSTPAY2_URL=$(get_service_url "gchostpay2-pgp")
if [ $? -eq 0 ]; then
    create_or_update_secret "GCHOSTPAY2_URL" "$GCHOSTPAY2_URL"
fi
echo ""

# GCHOSTPAY3_URL
echo "🔗 GCHOSTPAY3_URL..."
GCHOSTPAY3_URL=$(get_service_url "gchostpay3-pgp")
if [ $? -eq 0 ]; then
    create_or_update_secret "GCHOSTPAY3_URL" "$GCHOSTPAY3_URL"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Service URL secrets created/updated successfully!"
echo ""
echo "📋 Service URLs:"
[ ! -z "$GCWEBHOOK1_URL" ] && echo "   - GCWEBHOOK1: $GCWEBHOOK1_URL"
[ ! -z "$GCWEBHOOK2_URL" ] && echo "   - GCWEBHOOK2: $GCWEBHOOK2_URL"
[ ! -z "$GCSPLIT1_URL" ] && echo "   - GCSPLIT1: $GCSPLIT1_URL"
[ ! -z "$GCSPLIT2_URL" ] && echo "   - GCSPLIT2: $GCSPLIT2_URL"
[ ! -z "$GCSPLIT3_URL" ] && echo "   - GCSPLIT3: $GCSPLIT3_URL"
[ ! -z "$GCACCUMULATOR_URL" ] && echo "   - GCACCUMULATOR: $GCACCUMULATOR_URL"
[ ! -z "$GCHOSTPAY1_URL" ] && echo "   - GCHOSTPAY1: $GCHOSTPAY1_URL"
[ ! -z "$GCHOSTPAY2_URL" ] && echo "   - GCHOSTPAY2: $GCHOSTPAY2_URL"
[ ! -z "$GCHOSTPAY3_URL" ] && echo "   - GCHOSTPAY3: $GCHOSTPAY3_URL"
echo ""
echo "⏭️  Next: Configure external webhooks with these URLs"
