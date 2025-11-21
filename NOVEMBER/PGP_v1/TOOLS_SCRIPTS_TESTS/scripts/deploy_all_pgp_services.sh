#!/bin/bash
################################################################################
# Master Deployment Script for All PGP_v1 Services
# Purpose: Deploy all 15 PayGatePrime services to Google Cloud Run
# Version: 1.3.0
# Date: 2025-11-19 (Updated: Project ID changed to pgp-live)
# Previous Updates: 2025-11-18 (PGP_WEB_v1 removed - ghost service)
# ⚠️  DO NOT RUN WITHOUT TESTING IN DEV ENVIRONMENT FIRST!
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-pgp-live}"
REGION="${GCP_REGION:-us-central1}"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"  # Navigate to PGP_v1 root

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🚀 PGP_v1 Master Deployment Script${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will deploy all 15 PGP_v1 services!${NC}"
echo ""
echo "Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Cloud SQL: $CLOUD_SQL_INSTANCE"
echo "   Base Dir: $BASE_DIR"
echo ""

# Safety check
read -p "Are you sure you want to proceed? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}Starting deployment...${NC}"
echo ""

# Deployment tracking
DEPLOYED=0
FAILED=0
SKIPPED=0
declare -a FAILED_SERVICES

################################################################################
# Helper Functions
################################################################################

deploy_service() {
    local SERVICE_NAME=$1
    local SERVICE_DIR=$2
    local MEMORY=${3:-512Mi}
    local MIN_INSTANCES=${4:-0}
    local MAX_INSTANCES=${5:-10}
    local TIMEOUT=${6:-300}
    local AUTHENTICATION=${7:-"require"}         # NEW: "require" or "allow-unauthenticated"
    local SERVICE_ACCOUNT=${8:-""}               # NEW: Service account email

    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────────────────${NC}"
    echo -e "${BLUE}📦 Deploying: $SERVICE_NAME${NC}"
    echo -e "${BLUE}────────────────────────────────────────────────────────────────────${NC}"

    if [ ! -d "$SERVICE_DIR" ]; then
        echo -e "${RED}❌ Error: Service directory not found: $SERVICE_DIR${NC}"
        ((FAILED++))
        FAILED_SERVICES+=("$SERVICE_NAME (directory not found)")
        return 1
    fi

    cd "$SERVICE_DIR"

    # Determine authentication flag
    local AUTH_FLAG=""
    local AUTH_STATUS=""
    if [ "$AUTHENTICATION" = "allow-unauthenticated" ]; then
        AUTH_FLAG="--allow-unauthenticated"
        AUTH_STATUS="${YELLOW}⚠️  PUBLIC ACCESS (unauthenticated)${NC}"
    else
        AUTH_FLAG="--no-allow-unauthenticated"
        AUTH_STATUS="${GREEN}🔒 AUTHENTICATED (IAM required)${NC}"
    fi

    # Build service account flag
    local SA_FLAG=""
    if [ -n "$SERVICE_ACCOUNT" ]; then
        SA_FLAG="--service-account=${SERVICE_ACCOUNT}"
    fi

    echo "📋 Service Configuration:"
    echo "   Memory: $MEMORY"
    echo "   Min Instances: $MIN_INSTANCES"
    echo "   Max Instances: $MAX_INSTANCES"
    echo "   Timeout: ${TIMEOUT}s"
    echo -e "   Authentication: ${AUTH_STATUS}"
    if [ -n "$SERVICE_ACCOUNT" ]; then
        echo "   Service Account: $SERVICE_ACCOUNT"
    fi

    # Build and deploy
    echo ""
    echo "🔨 Building and deploying..."

    if gcloud run deploy "$SERVICE_NAME" \
        --source . \
        --platform managed \
        --region "$REGION" \
        --memory "$MEMORY" \
        --min-instances "$MIN_INSTANCES" \
        --max-instances "$MAX_INSTANCES" \
        --timeout "$TIMEOUT" \
        --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION" \
        --add-cloudsql-instances "$CLOUD_SQL_INSTANCE" \
        $AUTH_FLAG \
        $SA_FLAG \
        --quiet; then

        echo -e "${GREEN}✅ $SERVICE_NAME deployed successfully${NC}"
        ((DEPLOYED++))

        # Get service URL
        SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)" 2>/dev/null)
        echo "   URL: $SERVICE_URL"

        # Save URL for cross-service references
        echo "$SERVICE_URL" > "/tmp/${SERVICE_NAME}_url.txt"

        return 0
    else
        echo -e "${RED}❌ $SERVICE_NAME deployment failed${NC}"
        ((FAILED++))
        FAILED_SERVICES+=("$SERVICE_NAME")
        return 1
    fi
}

################################################################################
# Deployment Order (Based on Dependencies)
################################################################################

echo ""
echo -e "${GREEN}Phase 1: Core Infrastructure Services${NC}"
echo "========================================="

# 1. Telegram Bot Server - REQUIRES AUTH (webhooks will come via Load Balancer)
deploy_service "pgp-server-v1" "$BASE_DIR/PGP_SERVER_v1" "1Gi" "1" "20" "300" \
    "require" "pgp-server-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# NOTE: PGP_WEB_v1 has been REMOVED (2025-11-18)
# Service was a ghost service - empty directory with no source code
# See: THINK/AUTO/PGP_WEB_v1_CLEANUP_CHECKLIST.md, PROGRESS.md (2025-11-18)

# 2. Web API - REQUIRES AUTH (standalone REST API, no frontend exists)
deploy_service "pgp-webapi-v1" "$BASE_DIR/PGP_WEBAPI_v1" "512Mi" "0" "10" "300" \
    "require" "pgp-webapi-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo -e "${GREEN}Phase 2: Payment Processing Pipeline${NC}"
echo "========================================="

# 3. NowPayments IPN - REQUIRES AUTH (webhook via Load Balancer + Cloud Armor)
deploy_service "pgp-np-ipn-v1" "$BASE_DIR/PGP_NP_IPN_v1" "512Mi" "0" "20" "300" \
    "require" "pgp-np-ipn-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# 4. Orchestrator - REQUIRES AUTH (internal service-to-service only)
deploy_service "pgp-orchestrator-v1" "$BASE_DIR/PGP_ORCHESTRATOR_v1" "512Mi" "0" "20" "300" \
    "require" "pgp-orchestrator-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# 5. Invite service - REQUIRES AUTH (internal service-to-service only)
deploy_service "pgp-invite-v1" "$BASE_DIR/PGP_INVITE_v1" "512Mi" "0" "10" "300" \
    "require" "pgp-invite-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# 6. Split services (3-stage pipeline) - ALL REQUIRE AUTH (internal only)
deploy_service "pgp-split1-v1" "$BASE_DIR/PGP_SPLIT1_v1" "512Mi" "0" "15" "300" \
    "require" "pgp-split1-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"
deploy_service "pgp-split2-v1" "$BASE_DIR/PGP_SPLIT2_v1" "512Mi" "0" "15" "300" \
    "require" "pgp-split2-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"
deploy_service "pgp-split3-v1" "$BASE_DIR/PGP_SPLIT3_v1" "512Mi" "0" "15" "300" \
    "require" "pgp-split3-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo -e "${GREEN}Phase 3: Payout Services${NC}"
echo "========================================="

# 7. HostPay services (3-stage pipeline) - ALL REQUIRE AUTH (internal only)
deploy_service "pgp-hostpay1-v1" "$BASE_DIR/PGP_HOSTPAY1_v1" "512Mi" "0" "15" "300" \
    "require" "pgp-hostpay1-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"
deploy_service "pgp-hostpay2-v1" "$BASE_DIR/PGP_HOSTPAY2_v1" "512Mi" "0" "15" "300" \
    "require" "pgp-hostpay2-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"
deploy_service "pgp-hostpay3-v1" "$BASE_DIR/PGP_HOSTPAY3_v1" "512Mi" "0" "15" "300" \
    "require" "pgp-hostpay3-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo -e "${GREEN}Phase 4: Batch Processing Services${NC}"
echo "========================================="

# NOTE: PGP_ACCUMULATOR_v1 has been REMOVED (2025-11-18)
# Accumulation logic moved inline to PGP_ORCHESTRATOR_v1
# See: THINK/AUTO/PGP_THRESHOLD_REVIEW.md, PROGRESS.md (2025-11-18)

# 8. Batch processors - ALL REQUIRE AUTH (internal only)
deploy_service "pgp-batchprocessor-v1" "$BASE_DIR/PGP_BATCHPROCESSOR_v1" "512Mi" "0" "10" "300" \
    "require" "pgp-batchprocessor-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"
deploy_service "pgp-microbatchprocessor-v1" "$BASE_DIR/PGP_MICROBATCHPROCESSOR_v1" "512Mi" "0" "10" "300" \
    "require" "pgp-microbatchprocessor-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo -e "${GREEN}Phase 5: Notification & Broadcast Services${NC}"
echo "========================================="

# 9. Notifications - REQUIRES AUTH (internal only)
deploy_service "pgp-notifications-v1" "$BASE_DIR/PGP_NOTIFICATIONS_v1" "512Mi" "0" "10" "300" \
    "require" "pgp-notifications-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# 10. Broadcast scheduler - REQUIRES AUTH (internal only)
deploy_service "pgp-broadcast-v1" "$BASE_DIR/PGP_BROADCAST_v1" "512Mi" "1" "5" "300" \
    "require" "pgp-broadcast-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com"

################################################################################
# Deployment Summary
################################################################################

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}📊 Deployment Summary${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${GREEN}✅ Successfully deployed: $DEPLOYED services${NC}"
echo -e "${RED}❌ Failed: $FAILED services${NC}"
echo -e "${YELLOW}⏭️  Skipped: $SKIPPED services${NC}"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed services:${NC}"
    for service in "${FAILED_SERVICES[@]}"; do
        echo "   - $service"
    done
    echo ""
    echo -e "${YELLOW}⚠️  Some deployments failed. Please review errors above.${NC}"
    exit 1
fi

################################################################################
# Post-Deployment Tasks
################################################################################

echo -e "${GREEN}Post-Deployment Tasks${NC}"
echo "========================================="
echo ""

echo "1. Verify all services are running:"
echo "   gcloud run services list --region=$REGION | grep pgp-"
echo ""

echo "2. Check service URLs have been saved to /tmp/*_url.txt"
echo ""

echo "3. Update Secret Manager with service URLs if needed:"
for url_file in /tmp/pgp-*_url.txt; do
    if [ -f "$url_file" ]; then
        SERVICE=$(basename "$url_file" _url.txt | tr '[:lower:]' '[:upper:]' | tr '-' '_')
        URL=$(cat "$url_file")
        echo "   ${SERVICE}_URL: $URL"
    fi
done
echo ""

echo "4. Test critical endpoints:"
echo "   - PGP_NP_IPN_v1 webhook endpoint"
echo "   - PGP_SERVER_v1 bot webhook"
echo "   - PGP_WEB_v1 frontend"
echo ""

echo "5. Configure Cloud Tasks queues (if not already done):"
echo "   - Run queue creation scripts in TOOLS_SCRIPTS_TESTS/scripts/"
echo ""

echo "6. Set up Cloud Scheduler for PGP_BROADCAST_v1:"
echo "   - Configure scheduled broadcast jobs"
echo ""

echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo ""
echo -e "${YELLOW}⚠️  Remember to:${NC}"
echo "   - Test all services thoroughly"
echo "   - Monitor logs for errors"
echo "   - Set up alerting and monitoring"
echo "   - Update DNS records if needed"
echo "   - Configure load balancers"
echo ""

################################################################################
# Save Deployment Metadata
################################################################################

DEPLOYMENT_LOG="/tmp/pgp_deployment_$(date +%Y%m%d_%H%M%S).log"
cat > "$DEPLOYMENT_LOG" <<EOF
PGP_v1 Deployment Log
=====================
Date: $(date)
Project: $PROJECT_ID
Region: $REGION
Deployed: $DEPLOYED services
Failed: $FAILED services
Skipped: $SKIPPED services

Service URLs:
$(for url_file in /tmp/pgp-*_url.txt; do
    if [ -f "$url_file" ]; then
        SERVICE=$(basename "$url_file" _url.txt)
        URL=$(cat "$url_file")
        echo "$SERVICE: $URL"
    fi
done)
EOF

echo "Deployment log saved to: $DEPLOYMENT_LOG"
echo ""
