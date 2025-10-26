#!/bin/bash
# ==============================================================================
# Cloud Tasks Configuration - Secret Manager Setup Script
# Creates all queue name and service URL secrets in Google Cloud Secret Manager
# ==============================================================================

set -e  # Exit on error

# Configuration
PROJECT_ID="telepay-459221"
PROJECT_NUMBER="291176869049"

# Service URLs (update these with actual Cloud Run URLs after deployment)
GCSPLIT1_BASE_URL="${GCSPLIT1_BASE_URL:-https://gcsplit1-10-26-placeholder.run.app}"
GCSPLIT2_BASE_URL="${GCSPLIT2_BASE_URL:-https://gcsplit2-10-26-placeholder.run.app}"
GCSPLIT3_BASE_URL="${GCSPLIT3_BASE_URL:-https://gcsplit3-10-26-placeholder.run.app}"

echo "🔐 [SECRET_SETUP] Creating Cloud Tasks Configuration Secrets"
echo "📍 [SECRET_SETUP] Project: $PROJECT_ID ($PROJECT_NUMBER)"
echo ""
echo "📝 [SECRET_SETUP] Note: Service URL secrets will use placeholder values"
echo "   Update them with actual Cloud Run URLs after deployment using:"
echo "   ./update_service_urls.sh <gcsplit1-url> <gcsplit2-url> <gcsplit3-url>"
echo ""

# Function to create or update a secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    echo "📝 [SECRET_SETUP] Processing: $secret_name"

    # Check if secret already exists
    if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
        echo "⚠️ [SECRET_SETUP] Secret $secret_name already exists, adding new version..."

        # Add new version to existing secret
        echo -n "$secret_value" | gcloud secrets versions add "$secret_name" \
            --project="$PROJECT_ID" \
            --data-file=-

        echo "✅ [SECRET_SETUP] Secret $secret_name updated with new version"
    else
        echo "🆕 [SECRET_SETUP] Creating new secret: $secret_name"

        # Create new secret
        gcloud secrets create "$secret_name" \
            --project="$PROJECT_ID" \
            --replication-policy="automatic"

        # Add initial version
        echo -n "$secret_value" | gcloud secrets versions add "$secret_name" \
            --project="$PROJECT_ID" \
            --data-file=-

        echo "✅ [SECRET_SETUP] Secret $secret_name created successfully"
    fi

    echo ""
}

# ============================================================================
# PART 1: CLOUD TASKS QUEUE NAMES
# ============================================================================

echo "🚀 [SECRET_SETUP] PART 1: Creating 5 queue name secrets..."
echo ""

# 1. GCSPLIT2_QUEUE (GCSplit1 → GCSplit2 estimate requests)
create_or_update_secret "GCSPLIT2_QUEUE" "gcsplit-usdt-eth-estimate-queue"

# 2. GCSPLIT3_QUEUE (GCSplit1 → GCSplit3 swap requests)
create_or_update_secret "GCSPLIT3_QUEUE" "gcsplit-eth-client-swap-queue"

# 3. HOSTPAY_QUEUE (GCSplit1 → GCHostPay triggers)
create_or_update_secret "HOSTPAY_QUEUE" "gcsplit-hostpay-trigger-queue"

# 4. GCSPLIT2_RESPONSE_QUEUE (GCSplit2 → GCSplit1 responses)
create_or_update_secret "GCSPLIT2_RESPONSE_QUEUE" "gcsplit-usdt-eth-response-queue"

# 5. GCSPLIT3_RESPONSE_QUEUE (GCSplit3 → GCSplit1 responses)
create_or_update_secret "GCSPLIT3_RESPONSE_QUEUE" "gcsplit-eth-client-response-queue"

echo "✅ [SECRET_SETUP] PART 1 Complete: All queue name secrets created/updated!"
echo ""

# ============================================================================
# PART 2: SERVICE URLs
# ============================================================================

echo "🚀 [SECRET_SETUP] PART 2: Creating 4 service URL secrets..."
echo ""

# 1. GCSPLIT1_ESTIMATE_RESPONSE_URL (for GCSplit2 to respond to GCSplit1)
create_or_update_secret "GCSPLIT1_ESTIMATE_RESPONSE_URL" "${GCSPLIT1_BASE_URL}/usdt-eth-estimate"

# 2. GCSPLIT1_SWAP_RESPONSE_URL (for GCSplit3 to respond to GCSplit1)
create_or_update_secret "GCSPLIT1_SWAP_RESPONSE_URL" "${GCSPLIT1_BASE_URL}/eth-client-swap"

# 3. GCSPLIT2_URL (for GCSplit1 to call GCSplit2)
create_or_update_secret "GCSPLIT2_URL" "${GCSPLIT2_BASE_URL}"

# 4. GCSPLIT3_URL (for GCSplit1 to call GCSplit3)
create_or_update_secret "GCSPLIT3_URL" "${GCSPLIT3_BASE_URL}"

echo "✅ [SECRET_SETUP] PART 2 Complete: All service URL secrets created/updated!"
echo ""

# ============================================================================
# VERIFICATION
# ============================================================================

echo "🔍 [SECRET_SETUP] Verifying all secrets exist..."
echo ""

echo "📋 Queue Secrets:"
gcloud secrets list --project="$PROJECT_ID" | grep -E "(GCSPLIT2_QUEUE|GCSPLIT3_QUEUE|HOSTPAY_QUEUE|GCSPLIT2_RESPONSE_QUEUE|GCSPLIT3_RESPONSE_QUEUE)"
echo ""

echo "📋 URL Secrets:"
gcloud secrets list --project="$PROJECT_ID" | grep -E "(GCSPLIT1_ESTIMATE_RESPONSE_URL|GCSPLIT1_SWAP_RESPONSE_URL|GCSPLIT2_URL|GCSPLIT3_URL)"
echo ""

echo "✅ [SECRET_SETUP] Verification complete!"
echo ""

# Display secret values (for confirmation)
echo "📋 [SECRET_SETUP] Secret values:"
echo ""

echo "=== QUEUE NAMES ==="
echo ""

echo "1. GCSPLIT2_QUEUE:"
gcloud secrets versions access latest --secret=GCSPLIT2_QUEUE --project="$PROJECT_ID"
echo ""

echo "2. GCSPLIT3_QUEUE:"
gcloud secrets versions access latest --secret=GCSPLIT3_QUEUE --project="$PROJECT_ID"
echo ""

echo "3. HOSTPAY_QUEUE:"
gcloud secrets versions access latest --secret=HOSTPAY_QUEUE --project="$PROJECT_ID"
echo ""

echo "4. GCSPLIT2_RESPONSE_QUEUE:"
gcloud secrets versions access latest --secret=GCSPLIT2_RESPONSE_QUEUE --project="$PROJECT_ID"
echo ""

echo "5. GCSPLIT3_RESPONSE_QUEUE:"
gcloud secrets versions access latest --secret=GCSPLIT3_RESPONSE_QUEUE --project="$PROJECT_ID"
echo ""

echo "=== SERVICE URLS ==="
echo ""

echo "6. GCSPLIT1_ESTIMATE_RESPONSE_URL:"
gcloud secrets versions access latest --secret=GCSPLIT1_ESTIMATE_RESPONSE_URL --project="$PROJECT_ID"
echo ""

echo "7. GCSPLIT1_SWAP_RESPONSE_URL:"
gcloud secrets versions access latest --secret=GCSPLIT1_SWAP_RESPONSE_URL --project="$PROJECT_ID"
echo ""

echo "8. GCSPLIT2_URL:"
gcloud secrets versions access latest --secret=GCSPLIT2_URL --project="$PROJECT_ID"
echo ""

echo "9. GCSPLIT3_URL:"
gcloud secrets versions access latest --secret=GCSPLIT3_URL --project="$PROJECT_ID"
echo ""

# ============================================================================
# IAM PERMISSIONS
# ============================================================================

echo "🔐 [SECRET_SETUP] Granting Secret Manager access to Cloud Run service account..."
echo ""

SERVICE_ACCOUNT="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

for secret_name in GCSPLIT2_QUEUE GCSPLIT3_QUEUE HOSTPAY_QUEUE \
                   GCSPLIT2_RESPONSE_QUEUE GCSPLIT3_RESPONSE_QUEUE \
                   GCSPLIT1_ESTIMATE_RESPONSE_URL GCSPLIT1_SWAP_RESPONSE_URL \
                   GCSPLIT2_URL GCSPLIT3_URL; do
    echo "🔑 [SECRET_SETUP] Granting access to $secret_name..."

    gcloud secrets add-iam-policy-binding "$secret_name" \
        --project="$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet

    echo "✅ [SECRET_SETUP] Access granted for $secret_name"
done

echo ""
echo "🎉 [SECRET_SETUP] Setup complete!"
echo ""
echo "📝 [SECRET_SETUP] Summary:"
echo "   ✅ 5 queue name secrets created"
echo "   ✅ 4 service URL secrets created (with placeholders)"
echo "   ✅ IAM permissions granted for all 9 secrets"
echo ""
echo "📝 [SECRET_SETUP] Next steps:"
echo "   1. Verify secrets in Cloud Console: https://console.cloud.google.com/security/secret-manager?project=$PROJECT_ID"
echo "   2. Deploy all 3 services with the updated environment variables"
echo "   3. After deployment, update URL secrets with actual Cloud Run URLs:"
echo "      ./update_service_urls.sh <actual-gcsplit1-url> <actual-gcsplit2-url> <actual-gcsplit3-url>"
echo "   4. Test health checks to verify secret access"
echo "   5. Run end-to-end payment test"
echo ""
