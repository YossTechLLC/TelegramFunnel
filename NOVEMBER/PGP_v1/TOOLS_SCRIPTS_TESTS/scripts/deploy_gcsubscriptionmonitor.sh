#!/bin/bash
# Deploy GCSubscriptionMonitor-10-26 to Cloud Run

PROJECT_ID="telepay-459221"
REGION="us-central1"
SERVICE_NAME="gcsubscriptionmonitor-10-26"

echo "🚀 Deploying GCSubscriptionMonitor-10-26 to Cloud Run..."

gcloud run deploy ${SERVICE_NAME} \
  --source=./GCSubscriptionMonitor-10-26 \
  --region=${REGION} \
  --platform=managed \
  --no-allow-unauthenticated \
  --set-env-vars="TELEGRAM_BOT_TOKEN_SECRET=projects/${PROJECT_ID}/secrets/telegram-bot-token/versions/latest" \
  --set-env-vars="DATABASE_HOST_SECRET=projects/${PROJECT_ID}/secrets/database-host/versions/latest" \
  --set-env-vars="DATABASE_NAME_SECRET=projects/${PROJECT_ID}/secrets/database-name/versions/latest" \
  --set-env-vars="DATABASE_USER_SECRET=projects/${PROJECT_ID}/secrets/database-user/versions/latest" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=projects/${PROJECT_ID}/secrets/database-password/versions/latest" \
  --min-instances=0 \
  --max-instances=1 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300s \
  --concurrency=1 \
  --service-account=pgp_server-cloudrun@${PROJECT_ID}.iam.gserviceaccount.com

echo "✅ Deployment complete!"
