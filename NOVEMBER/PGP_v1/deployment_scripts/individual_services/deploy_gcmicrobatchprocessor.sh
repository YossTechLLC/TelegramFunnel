#!/bin/bash
# Deploy GCMicroBatchProcessor-PGP to Cloud Run
# Micro Batch Processor - Processes smaller batches via Cloud Scheduler
# DO NOT EXECUTE - Review before running

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SERVICE_NAME="pgp-microbatchprocessor-v1"
SOURCE_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1/GCMicroBatchProcessor-PGP"
SERVICE_ACCOUNT="pgp-services@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"

echo "🚀 Deploying GCMicroBatchProcessor-PGP"
echo "========================================="
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
  --memory=1Gi \
  --cpu=2 \
  --timeout=900 \
  --concurrency=40 \
  --max-instances=5 \
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
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo "✅ GCMicroBatchProcessor-PGP deployed successfully!"
echo ""
echo "📊 Service Details:"
echo "   URL: $SERVICE_URL"
echo "   Status: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.conditions[0].status)')"
echo "   Authentication: Internal only (--no-allow-unauthenticated)"
echo "   Memory: 1Gi (higher for batch processing)"
echo "   CPU: 2 vCPUs (higher for batch processing)"
echo "   Timeout: 900s (15 minutes for batch operations)"
echo ""
echo "🔗 Triggered By:"
echo "   Cloud Scheduler → GCMicroBatchProcessor (scheduled batch execution)"
echo ""
echo "📝 Next Steps:"
echo "   1. Create Cloud Scheduler job to trigger this service"
echo "   2. Configure schedule (e.g., every 15 minutes)"
echo "   3. Grant Cloud Scheduler permission to invoke service"
echo "   4. Example scheduler job creation:"
echo ""
echo "   gcloud scheduler jobs create http micro-batch-processor \\"
echo "     --location=$REGION \\"
echo "     --schedule='*/15 * * * *' \\"
echo "     --uri='$SERVICE_URL/process-micro-batch' \\"
echo "     --http-method=POST \\"
echo "     --oidc-service-account-email=$SERVICE_ACCOUNT"
echo ""
echo "   5. Check logs: gcloud run services logs read $SERVICE_NAME --region=$REGION"
echo ""
