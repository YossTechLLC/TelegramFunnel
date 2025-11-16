#!/bin/bash
# Deploy GCHostPay3-PGP to Cloud Run
# Blockchain Validator - Validates crypto payments on-chain
# DO NOT EXECUTE - Review before running

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SERVICE_NAME="gchostpay3-pgp"
SOURCE_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1/GCHostPay3-PGP"
SERVICE_ACCOUNT="pgp-services@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"

echo "🚀 Deploying GCHostPay3-PGP"
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
ALCHEMY_API_KEY_POLYGON=ALCHEMY_API_KEY_POLYGON:latest,\
PLATFORM_USDT_WALLET_ADDRESS=PLATFORM_USDT_WALLET_ADDRESS:latest,\
SENDGRID_API_KEY=SENDGRID_API_KEY:latest,\
FROM_EMAIL=FROM_EMAIL:latest,\
FROM_NAME=FROM_NAME:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo "✅ GCHostPay3-PGP deployed successfully!"
echo ""
echo "📊 Service Details:"
echo "   URL: $SERVICE_URL"
echo "   Status: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.conditions[0].status)')"
echo "   Authentication: Internal only (--no-allow-unauthenticated)"
echo ""
echo "🔗 Service Flow:"
echo "   GCHostPay2 → GCHostPay3 (blockchain validation) → Payment complete"
echo ""
echo "📝 Next Steps:"
echo "   1. Verify GCHOSTPAY3_URL secret is created/updated"
echo "   2. Ensure Cloud Tasks queue 'gchostpay3-queue' exists"
echo "   3. Verify Alchemy API key for Polygon network"
echo "   4. Verify PLATFORM_USDT_WALLET_ADDRESS is correct"
echo "   5. Test blockchain validation logic"
echo "   6. Check logs: gcloud run services logs read $SERVICE_NAME --region=$REGION"
echo ""
