#!/bin/bash
# Deploy GCRegisterAPI-PGP to Cloud Run
# Main Backend API - Handles user registration, authentication, and payment initiation
# DO NOT EXECUTE - Review before running

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SERVICE_NAME="pgp-server-v1"
SOURCE_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1/GCRegisterAPI-PGP"
SERVICE_ACCOUNT="pgp-services@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"

echo "🚀 Deploying GCRegisterAPI-PGP"
echo "=============================="
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
  --max-instances=10 \
  --min-instances=0 \
  --allow-unauthenticated \
  --add-cloudsql-instances=$CLOUD_SQL_INSTANCE \
  --set-env-vars=PROJECT_ID=$PROJECT_ID \
  --set-secrets="\
JWT_SECRET_KEY=JWT_SECRET_KEY:latest,\
SIGNUP_SECRET_KEY=SIGNUP_SECRET_KEY:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
SENDGRID_API_KEY=SENDGRID_API_KEY:latest,\
FROM_EMAIL=FROM_EMAIL:latest,\
FROM_NAME=FROM_NAME:latest,\
BASE_URL=BASE_URL:latest,\
CORS_ORIGIN=CORS_ORIGIN:latest,\
NOWPAYMENTS_API_KEY=NOWPAYMENTS_API_KEY:latest,\
NOWPAYMENTS_USDT_WALLET=NOWPAYMENTS_USDT_WALLET:latest,\
TP_PERCENTAGE=TP_PERCENTAGE:latest,\
TP_FLAT_FEE=TP_FLAT_FEE:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo "✅ GCRegisterAPI-PGP deployed successfully!"
echo ""
echo "📊 Service Details:"
echo "   URL: $SERVICE_URL"
echo "   Status: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.conditions[0].status)')"
echo ""
echo "🧪 Test the service:"
echo "   curl $SERVICE_URL/"
echo ""
echo "📝 Next Steps:"
echo "   1. Update CORS_ORIGIN secret if needed"
echo "   2. Test authentication endpoints"
echo "   3. Verify database connectivity"
echo "   4. Check Cloud Logging for any errors"
echo ""
