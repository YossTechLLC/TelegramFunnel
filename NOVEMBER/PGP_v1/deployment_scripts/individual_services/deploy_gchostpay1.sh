#!/bin/bash
# Deploy GCHostPay1-PGP to Cloud Run
# Crypto Payment Executor - Executes crypto conversions via ChangeNOW API
# DO NOT EXECUTE - Review before running

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SERVICE_NAME="pgp-hostpay1-v1"
SOURCE_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1/GCHostPay1-PGP"
SERVICE_ACCOUNT="pgp-services@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"

echo "🚀 Deploying GCHostPay1-PGP"
echo "============================="
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Region: $REGION"
echo "📍 Service: $SERVICE_NAME"
echo "📍 Source: $SOURCE_DIR"
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
  --timeout=540 \
  --concurrency=80 \
  --max-instances=10 \
  --min-instances=0 \
  --no-allow-unauthenticated \
  --add-cloudsql-instances=$CLOUD_SQL_INSTANCE \
  --set-env-vars=PROJECT_ID=$PROJECT_ID \
  --set-secrets="\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,\
CHANGENOW_USDT_WALLET=CHANGENOW_USDT_WALLET:latest,\
GCHOSTPAY2_QUEUE=GCHOSTPAY2_QUEUE:latest,\
GCHOSTPAY2_URL=GCHOSTPAY2_URL:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo "✅ GCHostPay1-PGP deployed successfully!"
echo ""
echo "📊 Service Details:"
echo "   URL: $SERVICE_URL"
echo "   Status: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.conditions[0].status)')"
echo "   Authentication: Internal only (--no-allow-unauthenticated)"
echo ""
echo "🔗 Service Flow:"
echo "   GCSplit2 → GCHostPay1 (ChangeNOW conversion) → GCHostPay2"
echo ""
echo "📝 Next Steps:"
echo "   1. Verify GCHOSTPAY1_URL secret is created/updated"
echo "   2. Ensure Cloud Tasks queue 'gchostpay1-queue' exists"
echo "   3. Verify ChangeNOW API key is valid"
echo "   4. Verify CHANGENOW_USDT_WALLET address is correct"
echo "   5. Test ChangeNOW API connectivity"
echo "   6. Check logs: gcloud run services logs read $SERVICE_NAME --region=$REGION"
echo ""
