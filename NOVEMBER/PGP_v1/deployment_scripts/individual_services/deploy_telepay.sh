#!/bin/bash
# Deploy TelePay-PGP to Cloud Run
# Telegram Bot - Legacy payment notification bot
# DO NOT EXECUTE - Review before running

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SERVICE_NAME="pgp-bot-v1"
SOURCE_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1/TelePay-PGP"
SERVICE_ACCOUNT="pgp-services@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"

echo "🚀 Deploying TelePay-PGP"
echo "========================="
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
  --timeout=300 \
  --concurrency=80 \
  --max-instances=5 \
  --min-instances=0 \
  --allow-unauthenticated \
  --add-cloudsql-instances=$CLOUD_SQL_INSTANCE \
  --set-env-vars=PROJECT_ID=$PROJECT_ID \
  --set-secrets="\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo "✅ TelePay-PGP deployed successfully!"
echo ""
echo "📊 Service Details:"
echo "   URL: $SERVICE_URL"
echo "   Status: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.conditions[0].status)')"
echo "   Authentication: Public (--allow-unauthenticated)"
echo ""
echo "📝 Telegram Bot Configuration:"
echo "   This bot can run in two modes:"
echo ""
echo "   1️⃣ WEBHOOK MODE (Recommended):"
echo "      Set Telegram webhook to Cloud Run URL:"
echo "      curl -X POST \"https://api.telegram.org/bot<BOT_TOKEN>/setWebhook\" \\"
echo "        -d \"url=$SERVICE_URL/webhook\""
echo ""
echo "   2️⃣ POLLING MODE (Alternative):"
echo "      Bot will use long polling (default if webhook not set)"
echo ""
echo "📝 Next Steps:"
echo "   1. Choose webhook or polling mode"
echo "   2. If using webhook mode, set webhook URL as shown above"
echo "   3. Verify webhook: curl \"https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo\""
echo "   4. Test bot by sending /start command"
echo "   5. Check logs: gcloud run services logs read $SERVICE_NAME --region=$REGION"
echo ""
echo "⚠️  NOTE: This is a legacy bot. Main payment flow uses np-webhook and GCWebhook services."
echo ""
