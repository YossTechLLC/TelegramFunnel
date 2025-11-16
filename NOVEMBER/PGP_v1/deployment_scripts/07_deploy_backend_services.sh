#!/bin/bash
# Deploy All Backend Services to Cloud Run
# DO NOT EXECUTE - Review and customize before running
# This script deploys all 14 backend services

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SERVICE_ACCOUNT_EMAIL="pgp-services@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"

echo "🚀 Deploying Backend Services to Cloud Run"
echo "==========================================="
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Region: $REGION"
echo "📍 Service Account: $SERVICE_ACCOUNT_EMAIL"
echo "📍 Cloud SQL: $CLOUD_SQL_INSTANCE"
echo ""
echo "⚠️  This will deploy 14 backend services"
echo "⚠️  Estimated time: 20-40 minutes"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Base directory
BASE_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1"

# =============================================================================
# Deployment Function
# =============================================================================

deploy_service() {
    local service_name=$1
    local source_dir=$2
    local memory=${3:-512Mi}
    local cpu=${4:-1}
    local allow_unauth=${5:-false}
    local extra_args=$6

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 Deploying: $service_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "   Source: $source_dir"
    echo "   Memory: $memory"
    echo "   CPU: $cpu"
    echo "   Public: $allow_unauth"
    echo ""

    cd "$BASE_DIR/$source_dir"

    # Build command
    local cmd="gcloud run deploy $service_name \
        --source=. \
        --region=$REGION \
        --platform=managed \
        --service-account=$SERVICE_ACCOUNT_EMAIL \
        --memory=$memory \
        --cpu=$cpu \
        --timeout=300 \
        --concurrency=80 \
        --max-instances=10 \
        --add-cloudsql-instances=$CLOUD_SQL_INSTANCE \
        --set-env-vars=PROJECT_ID=$PROJECT_ID"

    # Add authentication
    if [ "$allow_unauth" = "true" ]; then
        cmd="$cmd --allow-unauthenticated"
    else
        cmd="$cmd --no-allow-unauthenticated"
    fi

    # Add extra args if provided
    if [ ! -z "$extra_args" ]; then
        cmd="$cmd $extra_args"
    fi

    echo "   Executing deployment..."
    eval $cmd

    # Get service URL
    local service_url=$(gcloud run services describe $service_name --region=$REGION --format="value(status.url)")
    echo ""
    echo "   ✅ Deployed: $service_url"

    cd "$BASE_DIR"
}

# =============================================================================
# PRIORITY 1: Critical Public Services
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PRIORITY 1: Critical Public Services"
echo "═══════════════════════════════════════════════════════════════"

# 1. GCRegisterAPI (Main Backend API - Public)
deploy_service \
    "gcregisterapi-pgp" \
    "GCRegisterAPI-PGP" \
    "512Mi" \
    "1" \
    "true" \
    "--set-secrets=JWT_SECRET_KEY=JWT_SECRET_KEY:latest,SIGNUP_SECRET_KEY=SIGNUP_SECRET_KEY:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,SENDGRID_API_KEY=SENDGRID_API_KEY:latest,FROM_EMAIL=FROM_EMAIL:latest,FROM_NAME=FROM_NAME:latest,BASE_URL=BASE_URL:latest,CORS_ORIGIN=CORS_ORIGIN:latest"

# 2. np-webhook (NowPayments IPN Handler - Public)
deploy_service \
    "np-webhook-pgp" \
    "np-webhook-PGP" \
    "512Mi" \
    "1" \
    "true" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,GCWEBHOOK1_QUEUE=GCWEBHOOK1_QUEUE:latest,GCWEBHOOK1_URL=GCWEBHOOK1_URL:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# =============================================================================
# PRIORITY 2: Payment Processing Services (Internal)
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PRIORITY 2: Payment Processing Services (Internal)"
echo "═══════════════════════════════════════════════════════════════"

# 3. GCWebhook1 (Primary Payment Processor)
deploy_service \
    "gcwebhook1-pgp" \
    "GCWebhook1-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,GCWEBHOOK2_QUEUE=GCWEBHOOK2_QUEUE:latest,GCWEBHOOK2_URL=GCWEBHOOK2_URL:latest,GCSPLIT1_QUEUE=GCSPLIT1_QUEUE:latest,GCSPLIT1_URL=GCSPLIT1_URL:latest,GCACCUMULATOR_QUEUE=GCACCUMULATOR_QUEUE:latest,GCACCUMULATOR_URL=GCACCUMULATOR_URL:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# 4. GCHostPay1 (Crypto Payment Execution #1)
deploy_service \
    "gchostpay1-pgp" \
    "GCHostPay1-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,CHANGENOW_USDT_WALLET=CHANGENOW_USDT_WALLET:latest,GCHOSTPAY2_QUEUE=GCHOSTPAY2_QUEUE:latest,GCHOSTPAY2_URL=GCHOSTPAY2_URL:latest,GCHOSTPAY3_QUEUE=GCHOSTPAY3_QUEUE:latest,GCHOSTPAY3_URL=GCHOSTPAY3_URL:latest,GCHOSTPAY1_URL=GCHOSTPAY1_URL:latest,GCHOSTPAY1_RESPONSE_QUEUE=GCHOSTPAY1_RESPONSE_QUEUE:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# 5. GCHostPay2 (Crypto Payment Execution #2)
deploy_service \
    "gchostpay2-pgp" \
    "GCHostPay2-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,CHANGENOW_USDT_WALLET=CHANGENOW_USDT_WALLET:latest,GCHOSTPAY1_RESPONSE_QUEUE=GCHOSTPAY1_RESPONSE_QUEUE:latest,GCHOSTPAY1_URL=GCHOSTPAY1_URL:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# 6. GCHostPay3 (Crypto Payment Execution #3)
deploy_service \
    "gchostpay3-pgp" \
    "GCHostPay3-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,GCHOSTPAY1_RESPONSE_QUEUE=GCHOSTPAY1_RESPONSE_QUEUE:latest,GCHOSTPAY1_URL=GCHOSTPAY1_URL:latest,GCACCUMULATOR_RESPONSE_QUEUE=GCACCUMULATOR_RESPONSE_QUEUE:latest,GCACCUMULATOR_URL=GCACCUMULATOR_URL:latest,GCHOSTPAY3_RETRY_QUEUE=GCHOSTPAY3_RETRY_QUEUE:latest,GCHOSTPAY3_URL=GCHOSTPAY3_URL:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# =============================================================================
# PRIORITY 3: Split Payment Services (Internal)
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PRIORITY 3: Split Payment Services (Internal)"
echo "═══════════════════════════════════════════════════════════════"

# 7. GCSplit1
deploy_service \
    "gcsplit1-pgp" \
    "GCSplit1-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,GCSPLIT2_QUEUE=GCSPLIT2_QUEUE:latest,GCSPLIT2_URL=GCSPLIT2_URL:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# 8. GCSplit2
deploy_service \
    "gcsplit2-pgp" \
    "GCSplit2-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,GCSPLIT2_RESPONSE_QUEUE=GCSPLIT2_RESPONSE_QUEUE:latest,GCSPLIT3_QUEUE=GCSPLIT3_QUEUE:latest,GCSPLIT3_URL=GCSPLIT3_URL:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# 9. GCSplit3
deploy_service \
    "gcsplit3-pgp" \
    "GCSplit3-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,GCHOSTPAY1_QUEUE=GCHOSTPAY1_QUEUE:latest,GCHOSTPAY1_URL=GCHOSTPAY1_URL:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# =============================================================================
# PRIORITY 4: Supporting Services (Internal)
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "PRIORITY 4: Supporting Services (Internal)"
echo "═══════════════════════════════════════════════════════════════"

# 10. GCWebhook2 (Telegram Invite Handler)
deploy_service \
    "gcwebhook2-pgp" \
    "GCWebhook2-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# 11. GCAccumulator
deploy_service \
    "gcaccumulator-pgp" \
    "GCAccumulator-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,GCACCUMULATOR_RESPONSE_QUEUE=GCACCUMULATOR_RESPONSE_QUEUE:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# 12. GCBatchProcessor
deploy_service \
    "gcbatchprocessor-pgp" \
    "GCBatchProcessor-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,GCSPLIT1_BATCH_QUEUE=GCSPLIT1_BATCH_QUEUE:latest,GCSPLIT1_URL=GCSPLIT1_URL:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# 13. GCMicroBatchProcessor
deploy_service \
    "gcmicrobatchprocessor-pgp" \
    "GCMicroBatchProcessor-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,GCHOSTPAY1_THRESHOLD_QUEUE=GCHOSTPAY1_THRESHOLD_QUEUE:latest,GCHOSTPAY1_URL=GCHOSTPAY1_URL:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# 14. TelePay (Telegram Bot - Optional)
deploy_service \
    "telepay-pgp" \
    "TelePay-PGP" \
    "512Mi" \
    "1" \
    "false" \
    "--set-secrets=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,NOWPAYMENTS_API_KEY=NOWPAYMENTS_API_KEY:latest,NOWPAYMENTS_USDT_WALLET=NOWPAYMENTS_USDT_WALLET:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ALL BACKEND SERVICES DEPLOYED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Deployed Services:"
echo ""
echo "   Public Services (allow-unauthenticated):"
echo "   ✅ gcregisterapi-pgp (Main API)"
echo "   ✅ np-webhook-pgp (NowPayments IPN)"
echo ""
echo "   Internal Services (no-allow-unauthenticated):"
echo "   ✅ gcwebhook1-pgp (Payment Processor)"
echo "   ✅ gcwebhook2-pgp (Telegram Invites)"
echo "   ✅ gcsplit1-pgp, gcsplit2-pgp, gcsplit3-pgp"
echo "   ✅ gchostpay1-pgp, gchostpay2-pgp, gchostpay3-pgp"
echo "   ✅ gcaccumulator-pgp"
echo "   ✅ gcbatchprocessor-pgp"
echo "   ✅ gcmicrobatchprocessor-pgp"
echo "   ✅ telepay-pgp"
echo ""
echo "⏭️  NEXT STEPS:"
echo ""
echo "1. Run script 05 to update service URL secrets"
echo "2. Grant IAM run.invoker permissions (see script 06)"
echo "3. Create Cloud Tasks queues (TOOLS_SCRIPTS_TESTS/scripts/)"
echo "4. Deploy frontend (script 08)"
echo "5. Update NowPayments webhook URL (script 09)"
echo "6. Run verification (script 10)"
echo ""
