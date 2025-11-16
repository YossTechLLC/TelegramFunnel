#!/bin/bash
# Deploy GCHostPay2-PGP to Cloud Run
# Conversion Monitor - Monitors ChangeNOW conversion status
# DO NOT EXECUTE - Review before running

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SERVICE_NAME="gchostpay2-pgp"
SOURCE_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1/GCHostPay2-PGP"
SERVICE_ACCOUNT="pgp-services@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"

echo "🚀 Deploying GCHostPay2-PGP"
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
GCHOSTPAY3_QUEUE=GCHOSTPAY3_QUEUE:latest,\
GCHOSTPAY3_URL=GCHOSTPAY3_URL:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo "✅ GCHostPay2-PGP deployed successfully!"
echo ""
echo "📊 Service Details:"
echo "   URL: $SERVICE_URL"
echo "   Status: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.conditions[0].status)')"
echo "   Authentication: Internal only (--no-allow-unauthenticated)"
echo ""
echo "🔗 Service Flow:"
echo "   GCHostPay1 → GCHostPay2 (status monitoring) → GCHostPay3"
echo ""
echo "📝 Next Steps:"
echo "   1. Verify GCHOSTPAY2_URL secret is created/updated"
echo "   2. Ensure Cloud Tasks queue 'gchostpay2-queue' exists"
echo "   3. Test ChangeNOW status polling"
echo "   4. Check logs: gcloud run services logs read $SERVICE_NAME --region=$REGION"
echo ""
