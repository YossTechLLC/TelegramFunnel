#!/bin/bash
# Verify PayGatePrime v1 Deployment
# Run this after completing all deployment steps

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"

echo "✅ PayGatePrime v1 Deployment Verification"
echo "==========================================="
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Region: $REGION"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# =============================================================================
# Check 1: Cloud SQL Instance
# =============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 1: Cloud SQL Instance"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if gcloud sql instances describe pgp-live-psql &>/dev/null; then
    STATUS=$(gcloud sql instances describe pgp-live-psql --format="value(state)")
    echo "✅ Cloud SQL instance exists: pgp-live-psql"
    echo "   Status: $STATUS"
else
    echo "❌ Cloud SQL instance NOT FOUND"
fi

# =============================================================================
# Check 2: Secrets in Secret Manager
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 2: Critical Secrets"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

CRITICAL_SECRETS=(
    "JWT_SECRET_KEY"
    "SIGNUP_SECRET_KEY"
    "DATABASE_PASSWORD_SECRET"
    "CLOUD_SQL_CONNECTION_NAME"
    "SENDGRID_API_KEY"
    "NOWPAYMENTS_API_KEY"
    "NOWPAYMENTS_IPN_SECRET"
    "CHANGENOW_API_KEY"
)

MISSING_SECRETS=()
for secret in "${CRITICAL_SECRETS[@]}"; do
    if gcloud secrets describe $secret &>/dev/null; then
        echo "✅ $secret"
    else
        echo "❌ $secret - MISSING"
        MISSING_SECRETS+=($secret)
    fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    echo ""
    echo "⚠️  WARNING: ${#MISSING_SECRETS[@]} critical secrets missing!"
fi

# =============================================================================
# Check 3: Cloud Run Services
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 3: Cloud Run Services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

SERVICES=(
    "gcregisterapi-pgp"
    "np-webhook-pgp"
    "gcwebhook1-pgp"
    "gcwebhook2-pgp"
    "gcsplit1-pgp"
    "gcsplit2-pgp"
    "gcsplit3-pgp"
    "gchostpay1-pgp"
    "gchostpay2-pgp"
    "gchostpay3-pgp"
    "gcaccumulator-pgp"
    "gcbatchprocessor-pgp"
    "gcmicrobatchprocessor-pgp"
    "telepay-pgp"
)

MISSING_SERVICES=()
for service in "${SERVICES[@]}"; do
    if gcloud run services describe $service --region=$REGION &>/dev/null; then
        URL=$(gcloud run services describe $service --region=$REGION --format="value(status.url)")
        echo "✅ $service"
        echo "   URL: $URL"
    else
        echo "❌ $service - NOT DEPLOYED"
        MISSING_SERVICES+=($service)
    fi
done

if [ ${#MISSING_SERVICES[@]} -gt 0 ]; then
    echo ""
    echo "⚠️  WARNING: ${#MISSING_SERVICES[@]} services not deployed!"
fi

# =============================================================================
# Check 4: Cloud Tasks Queues
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 4: Cloud Tasks Queues"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

QUEUES=(
    "gcwebhook1-queue"
    "gcwebhook2-queue"
    "gcsplit1-queue"
    "gcsplit2-queue"
    "gcsplit3-queue"
    "gcaccumulator-queue"
    "gchostpay1-queue"
    "gchostpay2-queue"
    "gchostpay3-queue"
)

MISSING_QUEUES=()
for queue in "${QUEUES[@]}"; do
    if gcloud tasks queues describe $queue --location=$REGION &>/dev/null; then
        echo "✅ $queue"
    else
        echo "❌ $queue - NOT CREATED"
        MISSING_QUEUES+=($queue)
    fi
done

if [ ${#MISSING_QUEUES[@]} -gt 0 ]; then
    echo ""
    echo "⚠️  WARNING: ${#MISSING_QUEUES[@]} queues not created!"
fi

# =============================================================================
# Check 5: Service Health Checks
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 5: Public Service Health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test GCRegisterAPI
if gcloud run services describe gcregisterapi-pgp --region=$REGION &>/dev/null; then
    API_URL=$(gcloud run services describe gcregisterapi-pgp --region=$REGION --format="value(status.url)")
    echo "Testing GCRegisterAPI..."
    if curl -s -o /dev/null -w "%{http_code}" "$API_URL/" | grep -q "200\|404"; then
        echo "✅ gcregisterapi-pgp is responding"
    else
        echo "⚠️  gcregisterapi-pgp may not be responding correctly"
    fi
fi

# Test np-webhook
if gcloud run services describe np-webhook-pgp --region=$REGION &>/dev/null; then
    NP_URL=$(gcloud run services describe np-webhook-pgp --region=$REGION --format="value(status.url)")
    echo ""
    echo "Testing np-webhook..."
    if curl -s -o /dev/null -w "%{http_code}" "$NP_URL/payment-processing" | grep -q "200"; then
        echo "✅ np-webhook-pgp is responding"
        echo "   Payment page: $NP_URL/payment-processing"
    else
        echo "⚠️  np-webhook-pgp may not be responding correctly"
    fi
fi

# =============================================================================
# Check 6: Frontend Bucket
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 6: Frontend Bucket"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if gsutil ls -b gs://pgp-frontend &>/dev/null; then
    echo "✅ Frontend bucket exists: gs://pgp-frontend"
    FILE_COUNT=$(gsutil ls gs://pgp-frontend/** | wc -l)
    echo "   Files: $FILE_COUNT"
else
    echo "❌ Frontend bucket NOT FOUND"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 VERIFICATION SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

TOTAL_ISSUES=$((${#MISSING_SECRETS[@]} + ${#MISSING_SERVICES[@]} + ${#MISSING_QUEUES[@]}))

if [ $TOTAL_ISSUES -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED!"
    echo ""
    echo "🎉 PayGatePrime v1 deployment appears successful!"
    echo ""
    echo "⏭️  FINAL STEPS:"
    echo "1. Configure NowPayments IPN URL (see 09_EXTERNAL_WEBHOOKS_CONFIG.md)"
    echo "2. Test end-to-end payment flow"
    echo "3. Monitor logs for errors"
    echo "4. Set up monitoring dashboards"
else
    echo "⚠️  ISSUES FOUND: $TOTAL_ISSUES"
    echo ""
    [ ${#MISSING_SECRETS[@]} -gt 0 ] && echo "   Missing Secrets: ${#MISSING_SECRETS[@]}"
    [ ${#MISSING_SERVICES[@]} -gt 0 ] && echo "   Missing Services: ${#MISSING_SERVICES[@]}"
    [ ${#MISSING_QUEUES[@]} -gt 0 ] && echo "   Missing Queues: ${#MISSING_QUEUES[@]}"
    echo ""
    echo "📋 Review the checks above and fix any issues"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
