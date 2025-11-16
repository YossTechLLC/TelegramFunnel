#!/bin/bash
# Create Cloud Tasks Queue Name Secrets - PGP v1 Naming Scheme
# DO NOT EXECUTE - Review before running
# Run this AFTER deploying Cloud Run services

set -e

PROJECT_ID="pgp-live"

echo "📦 Creating Cloud Tasks Queue Name Secrets (PGP v1 Naming)"
echo "============================================================="
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Naming Scheme: pgp-{service}-queue"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# =============================================================================
# CLOUD TASKS - QUEUE NAMES (PGP v1 Naming Scheme)
# =============================================================================

echo "Creating queue name secrets with PGP v1 naming..."
echo ""

echo "📨 PGP_WEBHOOK1_QUEUE..."
echo -n "pgp-webhook1-queue" | gcloud secrets create PGP_WEBHOOK1_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-webhook1-queue"

echo "📨 PGP_WEBHOOK2_QUEUE..."
echo -n "pgp-webhook2-queue" | gcloud secrets create PGP_WEBHOOK2_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-webhook2-queue"

echo "📨 PGP_SPLIT1_QUEUE..."
echo -n "pgp-split1-queue" | gcloud secrets create PGP_SPLIT1_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-split1-queue"

echo "📨 PGP_SPLIT2_QUEUE..."
echo -n "pgp-split2-queue" | gcloud secrets create PGP_SPLIT2_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-split2-queue"

echo "📨 PGP_SPLIT3_QUEUE..."
echo -n "pgp-split3-queue" | gcloud secrets create PGP_SPLIT3_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-split3-queue"

echo "📨 PGP_ACCUMULATOR_QUEUE..."
echo -n "pgp-accumulator-queue" | gcloud secrets create PGP_ACCUMULATOR_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-accumulator-queue"

echo "📨 PGP_ACCUMULATOR_RESPONSE_QUEUE..."
echo -n "pgp-accumulator-response-queue" | gcloud secrets create PGP_ACCUMULATOR_RESPONSE_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-accumulator-response-queue"

echo "📨 PGP_BATCHPROCESSOR_QUEUE..."
echo -n "pgp-batchprocessor-queue" | gcloud secrets create PGP_BATCHPROCESSOR_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-batchprocessor-queue"

echo "📨 PGP_HOSTPAY1_QUEUE..."
echo -n "pgp-hostpay1-queue" | gcloud secrets create PGP_HOSTPAY1_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-hostpay1-queue"

echo "📨 PGP_HOSTPAY2_QUEUE..."
echo -n "pgp-hostpay2-queue" | gcloud secrets create PGP_HOSTPAY2_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-hostpay2-queue"

echo "📨 PGP_HOSTPAY3_QUEUE..."
echo -n "pgp-hostpay3-queue" | gcloud secrets create PGP_HOSTPAY3_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-hostpay3-queue"

echo "📨 PGP_HOSTPAY1_RESPONSE_QUEUE..."
echo -n "pgp-hostpay1-response-queue" | gcloud secrets create PGP_HOSTPAY1_RESPONSE_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-hostpay1-response-queue"

echo "📨 PGP_HOSTPAY1_THRESHOLD_QUEUE..."
echo -n "pgp-hostpay1-threshold-queue" | gcloud secrets create PGP_HOSTPAY1_THRESHOLD_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-hostpay1-threshold-queue"

echo "📨 PGP_HOSTPAY3_RETRY_QUEUE..."
echo -n "pgp-hostpay3-retry-queue" | gcloud secrets create PGP_HOSTPAY3_RETRY_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-hostpay3-retry-queue"

echo "📨 PGP_SPLIT1_BATCH_QUEUE..."
echo -n "pgp-split1-batch-queue" | gcloud secrets create PGP_SPLIT1_BATCH_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-split1-batch-queue"

echo "📨 PGP_SPLIT2_RESPONSE_QUEUE..."
echo -n "pgp-split2-response-queue" | gcloud secrets create PGP_SPLIT2_RESPONSE_QUEUE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: pgp-split2-response-queue"

echo ""
echo "✅ All queue name secrets created with PGP v1 naming!"
echo ""
echo "📋 Queue Name Format: pgp-{service}-queue"
echo "📋 Secret Name Format: PGP_{SERVICE}_QUEUE"
echo ""
echo "⏭️  Next: Deploy Cloud Run services, then run 05_create_service_url_secrets.sh"
