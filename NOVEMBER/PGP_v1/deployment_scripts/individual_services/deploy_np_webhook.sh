#!/bin/bash
# Deploy np-webhook-PGP to Cloud Run
# NowPayments IPN Webhook Handler - Receives payment notifications
# DO NOT EXECUTE - Review before running

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SERVICE_NAME="pgp-npwebhook-v1"
SOURCE_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1/np-webhook-PGP"
SERVICE_ACCOUNT="pgp-services@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"

echo "🚀 Deploying np-webhook-PGP"
echo "============================"
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Region: $REGION"
echo "📍 Service: $SERVICE_NAME"
echo "📍 Source: $SOURCE_DIR"
echo ""
echo "⚠️  CRITICAL: This service handles NowPayments IPN callbacks"
echo "⚠️  Must be publicly accessible for NowPayments to send notifications"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Navigate to source directory
cd "$SOURCE_DIR"

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --source=. \
  --region=$REGION \
  --platform=managed \
  --service-account=$SERVICE_ACCOUNT \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300 \
  --concurrency=80 \
  --max-instances=10 \
  --min-instances=0 \
  --allow-unauthenticated \
  --add-cloudsql-instances=$CLOUD_SQL_INSTANCE \
  --set-env-vars=PROJECT_ID=$PROJECT_ID \
  --set-secrets="\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,\
GCWEBHOOK1_QUEUE=GCWEBHOOK1_QUEUE:latest,\
GCWEBHOOK1_URL=GCWEBHOOK1_URL:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo "✅ np-webhook-PGP deployed successfully!"
echo ""
echo "📊 Service Details:"
echo "   URL: $SERVICE_URL"
echo "   Status: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.conditions[0].status)')"
echo ""
echo "🔴 CRITICAL NEXT STEPS:"
echo "   1. Configure NowPayments IPN URL:"
echo "      → Log into https://account.nowpayments.io/"
echo "      → Navigate to Settings → API Keys"
echo "      → Set IPN Callback URL to: $SERVICE_URL/"
echo "      → Verify IPN secret matches NOWPAYMENTS_IPN_SECRET"
echo ""
echo "   2. Test IPN endpoint:"
echo "      → Use NowPayments dashboard 'Test IPN' feature"
echo "      → Check logs: gcloud run services logs read $SERVICE_NAME --region=$REGION"
echo ""
echo "   3. Verify payment status page:"
echo "      → Visit: $SERVICE_URL/payment-processing"
echo ""
echo "📝 See deployment_scripts/09_EXTERNAL_WEBHOOKS_CONFIG.md for detailed setup"
echo ""
