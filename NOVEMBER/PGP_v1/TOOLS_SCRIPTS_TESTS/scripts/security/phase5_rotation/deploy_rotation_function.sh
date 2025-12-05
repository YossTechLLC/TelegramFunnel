#!/bin/bash
################################################################################
# Phase 5: Deploy Password Rotation Cloud Function
#
# Purpose: Deploy automated database password rotation
# Status: DEPLOYMENT SCRIPT - Review before execution
# Project: pgp-live
#
# This script deploys:
# - Cloud Function for password rotation
# - Pub/Sub topic for triggering
# - Cloud Scheduler job (90-day schedule)
# - IAM permissions
#
################################################################################

set -e

PROJECT_ID="pgp-live"
FUNCTION_NAME="rotate-db-password"
REGION="us-central1"
TOPIC_NAME="db-password-rotation"
SCHEDULE="0 0 1 */3 *"  # Every 90 days (every 3 months on the 1st at midnight)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔐 Deploy Password Rotation Cloud Function${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

################################################################################
# Create Pub/Sub Topic
################################################################################
echo -e "${YELLOW}━━━ Creating Pub/Sub Topic ━━━${NC}"

if gcloud pubsub topics describe ${TOPIC_NAME} --project=${PROJECT_ID} &>/dev/null; then
  echo -e "${YELLOW}Topic already exists${NC}"
else
  gcloud pubsub topics create ${TOPIC_NAME} --project=${PROJECT_ID}
  echo -e "✅ ${GREEN}Topic created${NC}"
fi

################################################################################
# Deploy Cloud Function
################################################################################
echo -e "${YELLOW}━━━ Deploying Cloud Function ━━━${NC}"

cd rotate_db_password

gcloud functions deploy ${FUNCTION_NAME} \
  --gen2 \
  --runtime=python311 \
  --region=${REGION} \
  --source=. \
  --entry-point=rotate_database_password \
  --trigger-topic=${TOPIC_NAME} \
  --set-env-vars=GCP_PROJECT=${PROJECT_ID},INSTANCE_CONNECTION_NAME=pgp-live:us-central1:telepaypsql,DB_USER=postgres,SECRET_NAME=DATABASE_PASSWORD_SECRET \
  --service-account=pgp-rotation@${PROJECT_ID}.iam.gserviceaccount.com \
  --memory=256MB \
  --timeout=300s \
  --project=${PROJECT_ID}

echo -e "✅ ${GREEN}Cloud Function deployed${NC}"

cd ..

################################################################################
# Create Cloud Scheduler Job
################################################################################
echo -e "${YELLOW}━━━ Creating Cloud Scheduler Job ━━━${NC}"

gcloud scheduler jobs create pubsub rotate-db-password-schedule \
  --schedule="${SCHEDULE}" \
  --topic=${TOPIC_NAME} \
  --message-body='{"trigger":"scheduled"}' \
  --time-zone="UTC" \
  --location=${REGION} \
  --project=${PROJECT_ID}

echo -e "✅ ${GREEN}Scheduler job created (90-day rotation)${NC}"

echo ""
echo -e "${GREEN}✅ Password rotation deployed successfully!${NC}"
echo ""
