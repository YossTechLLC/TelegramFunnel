#!/bin/bash
# Deploy GCNotificationService to Cloud Run
# This script deploys the notification webhook service with all required configurations

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}📬 Deploying GCNotificationService to Cloud Run...${NC}"

# Configuration variables
PROJECT_ID="telepay-459221"
SERVICE_NAME="gcnotificationservice-10-26"
REGION="us-central1"
SERVICE_ACCOUNT="291176869049-compute@developer.gserviceaccount.com"

# Secret Manager paths
TELEGRAM_BOT_TOKEN_SECRET="projects/${PROJECT_ID}/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest"
DATABASE_HOST_SECRET="projects/${PROJECT_ID}/secrets/DATABASE_HOST_SECRET/versions/latest"
DATABASE_NAME_SECRET="projects/${PROJECT_ID}/secrets/DATABASE_NAME_SECRET/versions/latest"
DATABASE_USER_SECRET="projects/${PROJECT_ID}/secrets/DATABASE_USER_SECRET/versions/latest"
DATABASE_PASSWORD_SECRET="projects/${PROJECT_ID}/secrets/DATABASE_PASSWORD_SECRET/versions/latest"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Project ID: ${PROJECT_ID}"
echo "  Service Name: ${SERVICE_NAME}"
echo "  Region: ${REGION}"
echo "  Service Account: ${SERVICE_ACCOUNT}"
echo ""

echo -e "${YELLOW}Deploying to Cloud Run...${NC}"

gcloud run deploy ${SERVICE_NAME} \
  --source=. \
  --region=${REGION} \
  --platform=managed \
  --allow-unauthenticated \
  --service-account=${SERVICE_ACCOUNT} \
  --set-env-vars="TELEGRAM_BOT_TOKEN_SECRET=${TELEGRAM_BOT_TOKEN_SECRET}" \
  --set-env-vars="DATABASE_HOST_SECRET=${DATABASE_HOST_SECRET}" \
  --set-env-vars="DATABASE_NAME_SECRET=${DATABASE_NAME_SECRET}" \
  --set-env-vars="DATABASE_USER_SECRET=${DATABASE_USER_SECRET}" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=${DATABASE_PASSWORD_SECRET}" \
  --set-env-vars="CLOUD_SQL_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql" \
  --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql \
  --min-instances=0 \
  --max-instances=10 \
  --memory=256Mi \
  --cpu=1 \
  --timeout=60s \
  --concurrency=80 \
  --project=${PROJECT_ID}

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --format='value(status.url)')

echo ""
echo -e "${GREEN}Service URL:${NC} ${SERVICE_URL}"
echo ""
echo -e "${YELLOW}Test the service:${NC}"
echo "  Health check:"
echo "    curl ${SERVICE_URL}/health"
echo ""
echo "  Test notification:"
echo "    curl -X POST ${SERVICE_URL}/test-notification \\"
echo "      -H \"Content-Type: application/json\" \\"
echo "      -d '{\"chat_id\": YOUR_CHAT_ID, \"channel_title\": \"Test Channel\"}'"
echo ""
echo -e "${GREEN}📬 GCNotificationService is ready!${NC}"
