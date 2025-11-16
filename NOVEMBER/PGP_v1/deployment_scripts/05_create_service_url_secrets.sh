#!/bin/bash
# Create Service URL Secrets - PGP v1 Naming Scheme
# DO NOT EXECUTE - Run this AFTER deploying all Cloud Run services
# This script will fetch actual service URLs and create secrets

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"

echo "🌐 Creating Service URL Secrets (PGP v1 Naming)"
echo "================================================="
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Region: $REGION"
echo "📍 Service Naming: pgp-{service}-v1"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
echo "📋 Project Number: $PROJECT_NUMBER"
echo ""

# =============================================================================
# SERVICE URLS - Fetched from Cloud Run (PGP v1 Naming)
# =============================================================================

echo "Fetching service URLs from Cloud Run with PGP v1 naming..."
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

# PGP_WEBHOOK1_URL
echo "🔗 PGP_WEBHOOK1_URL..."
PGP_WEBHOOK1_URL=$(get_service_url "pgp-webhook1-v1")
if [ $? -eq 0 ]; then
    create_or_update_secret "PGP_WEBHOOK1_URL" "$PGP_WEBHOOK1_URL"
fi
echo ""

# PGP_WEBHOOK2_URL
echo "🔗 PGP_WEBHOOK2_URL..."
PGP_WEBHOOK2_URL=$(get_service_url "pgp-webhook2-v1")
if [ $? -eq 0 ]; then
    create_or_update_secret "PGP_WEBHOOK2_URL" "$PGP_WEBHOOK2_URL"
fi
echo ""

# PGP_SPLIT1_URL
echo "🔗 PGP_SPLIT1_URL..."
PGP_SPLIT1_URL=$(get_service_url "pgp-split1-v1")
if [ $? -eq 0 ]; then
    create_or_update_secret "PGP_SPLIT1_URL" "$PGP_SPLIT1_URL"
fi
echo ""

# PGP_SPLIT2_URL
echo "🔗 PGP_SPLIT2_URL..."
PGP_SPLIT2_URL=$(get_service_url "pgp-split2-v1")
if [ $? -eq 0 ]; then
    create_or_update_secret "PGP_SPLIT2_URL" "$PGP_SPLIT2_URL"
fi
echo ""

# PGP_SPLIT3_URL
echo "🔗 PGP_SPLIT3_URL..."
PGP_SPLIT3_URL=$(get_service_url "pgp-split3-v1")
if [ $? -eq 0 ]; then
    create_or_update_secret "PGP_SPLIT3_URL" "$PGP_SPLIT3_URL"
fi
echo ""

# PGP_ACCUMULATOR_URL
echo "🔗 PGP_ACCUMULATOR_URL..."
PGP_ACCUMULATOR_URL=$(get_service_url "pgp-accumulator-v1")
if [ $? -eq 0 ]; then
    create_or_update_secret "PGP_ACCUMULATOR_URL" "$PGP_ACCUMULATOR_URL"
fi
echo ""

# PGP_HOSTPAY1_URL
echo "🔗 PGP_HOSTPAY1_URL..."
PGP_HOSTPAY1_URL=$(get_service_url "pgp-hostpay1-v1")
if [ $? -eq 0 ]; then
    create_or_update_secret "PGP_HOSTPAY1_URL" "$PGP_HOSTPAY1_URL"
fi
echo ""

# PGP_HOSTPAY2_URL
echo "🔗 PGP_HOSTPAY2_URL..."
PGP_HOSTPAY2_URL=$(get_service_url "pgp-hostpay2-v1")
if [ $? -eq 0 ]; then
    create_or_update_secret "PGP_HOSTPAY2_URL" "$PGP_HOSTPAY2_URL"
fi
echo ""

# PGP_HOSTPAY3_URL
echo "🔗 PGP_HOSTPAY3_URL..."
PGP_HOSTPAY3_URL=$(get_service_url "pgp-hostpay3-v1")
if [ $? -eq 0 ]; then
    create_or_update_secret "PGP_HOSTPAY3_URL" "$PGP_HOSTPAY3_URL"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Service URL secrets created/updated successfully!"
echo ""
echo "📋 Service URLs (PGP v1 Naming):"
[ ! -z "$PGP_WEBHOOK1_URL" ] && echo "   - PGP_WEBHOOK1: $PGP_WEBHOOK1_URL"
[ ! -z "$PGP_WEBHOOK2_URL" ] && echo "   - PGP_WEBHOOK2: $PGP_WEBHOOK2_URL"
[ ! -z "$PGP_SPLIT1_URL" ] && echo "   - PGP_SPLIT1: $PGP_SPLIT1_URL"
[ ! -z "$PGP_SPLIT2_URL" ] && echo "   - PGP_SPLIT2: $PGP_SPLIT2_URL"
[ ! -z "$PGP_SPLIT3_URL" ] && echo "   - PGP_SPLIT3: $PGP_SPLIT3_URL"
[ ! -z "$PGP_ACCUMULATOR_URL" ] && echo "   - PGP_ACCUMULATOR: $PGP_ACCUMULATOR_URL"
[ ! -z "$PGP_HOSTPAY1_URL" ] && echo "   - PGP_HOSTPAY1: $PGP_HOSTPAY1_URL"
[ ! -z "$PGP_HOSTPAY2_URL" ] && echo "   - PGP_HOSTPAY2: $PGP_HOSTPAY2_URL"
[ ! -z "$PGP_HOSTPAY3_URL" ] && echo "   - PGP_HOSTPAY3: $PGP_HOSTPAY3_URL"
echo ""
echo "📋 Naming Formats:"
echo "   Service: pgp-{service}-v1"
echo "   Secret: PGP_{SERVICE}_URL"
echo ""
echo "⏭️  Next: Configure external webhooks with these URLs"
