#!/bin/bash
# Create Cloud Tasks Queue Name Secrets
# DO NOT EXECUTE - Review before running
# Run this AFTER deploying Cloud Run services

set -e

PROJECT_ID="pgp-live"

echo "📦 Creating Cloud Tasks Queue Name Secrets"
echo "============================================"
echo ""
echo "📍 Project: $PROJECT_ID"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# =============================================================================
# CLOUD TASKS - QUEUE NAMES
# =============================================================================

echo "Creating queue name secrets..."
echo ""

echo "📨 GCWEBHOOK1_QUEUE..."
echo -n "gcwebhook1-queue" | gcloud secrets create GCWEBHOOK1_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCWEBHOOK2_QUEUE..."
echo -n "gcwebhook2-queue" | gcloud secrets create GCWEBHOOK2_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCSPLIT1_QUEUE..."
echo -n "gcsplit1-queue" | gcloud secrets create GCSPLIT1_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCSPLIT2_QUEUE..."
echo -n "gcsplit2-queue" | gcloud secrets create GCSPLIT2_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCSPLIT3_QUEUE..."
echo -n "gcsplit3-queue" | gcloud secrets create GCSPLIT3_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCACCUMULATOR_QUEUE..."
echo -n "gcaccumulator-queue" | gcloud secrets create GCACCUMULATOR_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCACCUMULATOR_RESPONSE_QUEUE..."
echo -n "gcaccumulator-response-queue" | gcloud secrets create GCACCUMULATOR_RESPONSE_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCBATCHPROCESSOR_QUEUE..."
echo -n "gcbatchprocessor-queue" | gcloud secrets create GCBATCHPROCESSOR_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCHOSTPAY1_QUEUE..."
echo -n "gchostpay1-queue" | gcloud secrets create GCHOSTPAY1_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCHOSTPAY2_QUEUE..."
echo -n "gchostpay2-queue" | gcloud secrets create GCHOSTPAY2_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCHOSTPAY3_QUEUE..."
echo -n "gchostpay3-queue" | gcloud secrets create GCHOSTPAY3_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCHOSTPAY1_RESPONSE_QUEUE..."
echo -n "gchostpay1-response-queue" | gcloud secrets create GCHOSTPAY1_RESPONSE_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCHOSTPAY1_THRESHOLD_QUEUE..."
echo -n "gchostpay1-threshold-queue" | gcloud secrets create GCHOSTPAY1_THRESHOLD_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCHOSTPAY3_RETRY_QUEUE..."
echo -n "gchostpay3-retry-queue" | gcloud secrets create GCHOSTPAY3_RETRY_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCSPLIT1_BATCH_QUEUE..."
echo -n "gcsplit1-batch-queue" | gcloud secrets create GCSPLIT1_BATCH_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo "📨 GCSPLIT2_RESPONSE_QUEUE..."
echo -n "gcsplit2-response-queue" | gcloud secrets create GCSPLIT2_RESPONSE_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created"

echo ""
echo "✅ All queue name secrets created!"
echo ""
echo "⏭️  Next: Deploy Cloud Run services, then run 05_create_service_url_secrets.sh"
