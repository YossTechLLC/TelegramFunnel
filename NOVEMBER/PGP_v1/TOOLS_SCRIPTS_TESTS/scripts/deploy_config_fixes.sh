#!/bin/bash
# Deploy script for config_manager.py fixes across 7 services
# October 29, 2025 - Config Manager Environment Variable Pattern Fix

set -e  # Exit on error

BASE_DIR="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26"
PROJECT_ID="telepay-459221"
REGION="us-central1"
SQL_INSTANCE="telepay-459221:us-central1:telepaypsql"

echo "🚀 Starting deployment of config_manager.py fixes..."
echo "📦 Services to deploy: PGP_INVITE_v1, PGP_SPLIT1_v1-3, PGP_HOSTPAY1_v1-3"
echo ""

# Function to build and deploy a service
deploy_service() {
    local service_dir=$1
    local service_name=$2
    local secrets=$3

    echo "=================================="
    echo "🔨 Building $service_name..."
    echo "=================================="

    cd "$BASE_DIR/$service_dir"

    # Build Docker image
    gcloud builds submit --tag gcr.io/$PROJECT_ID/$service_name:latest

    echo ""
    echo "🚀 Deploying $service_name..."

    # Deploy to Cloud Run
    gcloud run deploy $service_name \
        --image gcr.io/$PROJECT_ID/$service_name:latest \
        --region $REGION \
        --platform managed \
        --allow-unauthenticated \
        --memory 512Mi \
        --cpu 1 \
        --timeout 60 \
        --max-instances 10 \
        --add-cloudsql-instances $SQL_INSTANCE \
        --set-secrets $secrets

    echo "✅ $service_name deployed successfully!"
    echo ""
}

# Deploy PGP_INVITE_v1
deploy_service "PGP_INVITE_v1" "pgp-invite-v1" \
    "SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
BOT_TOKEN=BOT_TOKEN:latest"

# Deploy PGP_SPLIT1_v1
deploy_service "PGP_SPLIT1_v1" "pgp-split1-v1" \
    "SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
TPS_HOSTPAY_SIGNING_KEY=TPS_HOSTPAY_SIGNING_KEY:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,\
GCSPLIT2_QUEUE=GCSPLIT2_QUEUE:latest,\
GCSPLIT2_URL=GCSPLIT2_URL:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest"

# Deploy PGP_SPLIT2_v1
deploy_service "PGP_SPLIT2_v1" "pgp-split2-v1" \
    "SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
TPS_HOSTPAY_SIGNING_KEY=TPS_HOSTPAY_SIGNING_KEY:latest,\
CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,\
GCSPLIT3_QUEUE=GCSPLIT3_QUEUE:latest,\
GCSPLIT3_URL=GCSPLIT3_URL:latest"

# Deploy PGP_SPLIT3_v1
deploy_service "PGP_SPLIT3_v1" "pgp-split3-v1" \
    "SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
TPS_HOSTPAY_SIGNING_KEY=TPS_HOSTPAY_SIGNING_KEY:latest,\
CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# Deploy PGP_HOSTPAY1_v1
deploy_service "PGP_HOSTPAY1_v1" "pgp-hostpay1-v1" \
    "SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
TPS_HOSTPAY_SIGNING_KEY=TPS_HOSTPAY_SIGNING_KEY:latest,\
ALCHEMY_API_KEY=ALCHEMY_API_KEY:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,\
GCHOSTPAY2_QUEUE=GCHOSTPAY2_QUEUE:latest,\
GCHOSTPAY2_URL=GCHOSTPAY2_URL:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest"

# Deploy PGP_HOSTPAY2_v1
deploy_service "PGP_HOSTPAY2_v1" "pgp-hostpay2-v1" \
    "SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
TPS_HOSTPAY_SIGNING_KEY=TPS_HOSTPAY_SIGNING_KEY:latest,\
CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,\
GCHOSTPAY3_QUEUE=GCHOSTPAY3_QUEUE:latest,\
GCHOSTPAY3_URL=GCHOSTPAY3_URL:latest"

# Deploy PGP_HOSTPAY3_v1
deploy_service "PGP_HOSTPAY3_v1" "pgp-hostpay3-v1" \
    "SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
TPS_HOSTPAY_SIGNING_KEY=TPS_HOSTPAY_SIGNING_KEY:latest,\
CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest"

echo "=================================="
echo "🎉 All services deployed successfully!"
echo "=================================="
echo ""
echo "✅ Services fixed and deployed:"
echo "   1. PGP_INVITE_v1"
echo "   2. PGP_SPLIT1_v1"
echo "   3. PGP_SPLIT2_v1"
echo "   4. PGP_SPLIT3_v1"
echo "   5. PGP_HOSTPAY1_v1"
echo "   6. PGP_HOSTPAY2_v1"
echo "   7. PGP_HOSTPAY3_v1"
echo ""
echo "📝 All services now use direct os.getenv() for secrets"
echo "🔐 Cloud Run --set-secrets flag properly injects values"
echo ""
