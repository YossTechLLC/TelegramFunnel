#!/bin/bash
# ==============================================================================
# Update Service URLs in Secret Manager
# Run this script after deploying services to update URL secrets with actual URLs
# ==============================================================================

set -e  # Exit on error

# Configuration
PROJECT_ID="telepay-459221"

# Check arguments
if [ "$#" -ne 3 ]; then
    echo "❌ [ERROR] Invalid arguments"
    echo ""
    echo "Usage: ./update_service_urls.sh <gcsplit1-url> <gcsplit2-url> <gcsplit3-url>"
    echo ""
    echo "Example:"
    echo "  ./update_service_urls.sh \\"
    echo "    https://gcsplit1-10-26-abc123.run.app \\"
    echo "    https://gcsplit2-10-26-def456.run.app \\"
    echo "    https://gcsplit3-10-26-ghi789.run.app"
    echo ""
    exit 1
fi

GCSPLIT1_URL="$1"
GCSPLIT2_URL="$2"
GCSPLIT3_URL="$3"

echo "🔄 [URL_UPDATE] Updating Service URL Secrets"
echo "📍 [URL_UPDATE] Project: $PROJECT_ID"
echo ""
echo "📝 [URL_UPDATE] URLs to set:"
echo "   GCSplit1: $GCSPLIT1_URL"
echo "   GCSplit2: $GCSPLIT2_URL"
echo "   GCSplit3: $GCSPLIT3_URL"
echo ""

# Validate URLs
for url in "$GCSPLIT1_URL" "$GCSPLIT2_URL" "$GCSPLIT3_URL"; do
    if [[ ! "$url" =~ ^https:// ]]; then
        echo "❌ [ERROR] Invalid URL format: $url"
        echo "   URLs must start with https://"
        exit 1
    fi
done

echo "✅ [URL_UPDATE] URL validation passed"
echo ""

# Update GCSPLIT1_ESTIMATE_RESPONSE_URL
echo "📝 [URL_UPDATE] Updating GCSPLIT1_ESTIMATE_RESPONSE_URL..."
echo -n "${GCSPLIT1_URL}/usdt-eth-estimate" | \
    gcloud secrets versions add GCSPLIT1_ESTIMATE_RESPONSE_URL \
    --project="$PROJECT_ID" \
    --data-file=-
echo "✅ [URL_UPDATE] GCSPLIT1_ESTIMATE_RESPONSE_URL updated"
echo ""

# Update GCSPLIT1_SWAP_RESPONSE_URL
echo "📝 [URL_UPDATE] Updating GCSPLIT1_SWAP_RESPONSE_URL..."
echo -n "${GCSPLIT1_URL}/eth-client-swap" | \
    gcloud secrets versions add GCSPLIT1_SWAP_RESPONSE_URL \
    --project="$PROJECT_ID" \
    --data-file=-
echo "✅ [URL_UPDATE] GCSPLIT1_SWAP_RESPONSE_URL updated"
echo ""

# Update GCSPLIT2_URL
echo "📝 [URL_UPDATE] Updating GCSPLIT2_URL..."
echo -n "$GCSPLIT2_URL" | \
    gcloud secrets versions add GCSPLIT2_URL \
    --project="$PROJECT_ID" \
    --data-file=-
echo "✅ [URL_UPDATE] GCSPLIT2_URL updated"
echo ""

# Update GCSPLIT3_URL
echo "📝 [URL_UPDATE] Updating GCSPLIT3_URL..."
echo -n "$GCSPLIT3_URL" | \
    gcloud secrets versions add GCSPLIT3_URL \
    --project="$PROJECT_ID" \
    --data-file=-
echo "✅ [URL_UPDATE] GCSPLIT3_URL updated"
echo ""

echo "🎉 [URL_UPDATE] All service URL secrets updated successfully!"
echo ""

# Verify updated values
echo "🔍 [URL_UPDATE] Verifying updated values..."
echo ""

echo "1. GCSPLIT1_ESTIMATE_RESPONSE_URL:"
gcloud secrets versions access latest --secret=GCSPLIT1_ESTIMATE_RESPONSE_URL --project="$PROJECT_ID"
echo ""

echo "2. GCSPLIT1_SWAP_RESPONSE_URL:"
gcloud secrets versions access latest --secret=GCSPLIT1_SWAP_RESPONSE_URL --project="$PROJECT_ID"
echo ""

echo "3. GCSPLIT2_URL:"
gcloud secrets versions access latest --secret=GCSPLIT2_URL --project="$PROJECT_ID"
echo ""

echo "4. GCSPLIT3_URL:"
gcloud secrets versions access latest --secret=GCSPLIT3_URL --project="$PROJECT_ID"
echo ""

echo "✅ [URL_UPDATE] Verification complete!"
echo ""
echo "📝 [URL_UPDATE] Next steps:"
echo "   1. Services will automatically fetch new URLs on next request (no re-deployment needed)"
echo "   2. Test health checks: curl https://<service-url>/health"
echo "   3. Run end-to-end payment test to verify inter-service communication"
echo ""
