#!/bin/bash
################################################################################
# Redis Nonce Tracker Deployment Script
################################################################################
# Project: pgp-live
# Purpose: Deploy Redis instance for replay attack prevention (C-02)
#
# This script provisions a Redis instance for storing nonces used in
# HMAC signature verification to prevent replay attacks.
#
# Security Fix: C-02 - Replay Attack Prevention
# OWASP: A07:2021 - Identification and Authentication Failures
# CWE: CWE-294 (Authentication Bypass by Capture-replay)
#
# Usage:
#   ./deploy_redis_nonce_tracker.sh [--dry-run] [--skip-confirmation]
#
# Options:
#   --dry-run           Print commands without executing
#   --skip-confirmation Skip user confirmation prompt
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Active GCP project: pgp-live
#   - Billing enabled on project
#   - Redis API enabled (will be enabled automatically)
#
# Cost Estimate:
#   - Basic Tier (M1): ~$50/month
#   - Standard Tier (M1-HA): ~$100/month (high availability)
#
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="pgp-live"
REDIS_INSTANCE_NAME="pgp-nonce-tracker"
REDIS_REGION="us-central1"
REDIS_ZONE="us-central1-a"
REDIS_TIER="BASIC"  # Options: BASIC, STANDARD_HA
REDIS_MEMORY_SIZE_GB=1  # Minimum for Basic tier
REDIS_VERSION="redis_6_x"  # Latest stable version

# Secret names for connection details
SECRET_REDIS_HOST="PGP_REDIS_HOST"
SECRET_REDIS_PORT="PGP_REDIS_PORT"
SECRET_REDIS_PASSWORD="PGP_REDIS_PASSWORD"  # Not used for Memorystore (auth optional)

# Parse command-line arguments
DRY_RUN=false
SKIP_CONFIRMATION=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-confirmation)
            SKIP_CONFIRMATION=true
            shift
            ;;
        *)
            echo -e "${RED}❌ Unknown argument: $arg${NC}"
            echo "Usage: $0 [--dry-run] [--skip-confirmation]"
            exit 1
            ;;
    esac
done

# Helper function to execute or print commands
execute_or_print() {
    local cmd="$1"
    local description="$2"

    if [ -n "$description" ]; then
        echo -e "\n${CYAN}⏳ $description${NC}"
    fi

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would execute: $cmd${NC}"
    else
        echo -e "${BLUE}Executing: $cmd${NC}"
        eval "$cmd"
    fi
}

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🚀 Redis Nonce Tracker Deployment${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${CYAN}Configuration:${NC}"
echo -e "  Project ID:       ${GREEN}$PROJECT_ID${NC}"
echo -e "  Instance Name:    ${GREEN}$REDIS_INSTANCE_NAME${NC}"
echo -e "  Region:           ${GREEN}$REDIS_REGION${NC}"
echo -e "  Zone:             ${GREEN}$REDIS_ZONE${NC}"
echo -e "  Tier:             ${GREEN}$REDIS_TIER${NC}"
echo -e "  Memory Size:      ${GREEN}${REDIS_MEMORY_SIZE_GB}GB${NC}"
echo -e "  Redis Version:    ${GREEN}$REDIS_VERSION${NC}"
echo ""
echo -e "${YELLOW}Cost Estimate:${NC}"
echo -e "  Basic Tier (M1):      ~$50/month"
echo -e "  Standard HA (M1):     ~$100/month"
echo ""

# Confirmation prompt
if [ "$SKIP_CONFIRMATION" = false ] && [ "$DRY_RUN" = false ]; then
    echo -e "${YELLOW}⚠️  This will provision a Redis instance that incurs ongoing costs.${NC}"
    read -p "Do you want to continue? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo -e "${RED}❌ Deployment cancelled by user${NC}"
        exit 0
    fi
fi

# Set GCP project
execute_or_print \
    "gcloud config set project $PROJECT_ID 2>/dev/null" \
    "Setting GCP project to $PROJECT_ID"

# Enable Redis API
echo -e "\n${CYAN}⏳ Enabling Redis (Memorystore) API...${NC}"
if [ "$DRY_RUN" = false ]; then
    if gcloud services list --enabled --filter="name:redis.googleapis.com" --format="value(name)" 2>/dev/null | grep -q "redis.googleapis.com"; then
        echo -e "${GREEN}✅ Redis API already enabled${NC}"
    else
        execute_or_print \
            "gcloud services enable redis.googleapis.com --quiet" \
            "Enabling Redis API (this may take 1-2 minutes)"
        echo -e "${GREEN}✅ Redis API enabled${NC}"
    fi
else
    echo -e "${YELLOW}[DRY-RUN] Would enable redis.googleapis.com${NC}"
fi

# Check if Redis instance already exists
echo -e "\n${CYAN}⏳ Checking if Redis instance already exists...${NC}"
if [ "$DRY_RUN" = false ]; then
    if gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REDIS_REGION 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Redis instance '$REDIS_INSTANCE_NAME' already exists${NC}"
        echo -e "${YELLOW}   Skipping creation. Use existing instance.${NC}"
        REDIS_ALREADY_EXISTS=true
    else
        echo -e "${GREEN}✅ Redis instance does not exist - will create${NC}"
        REDIS_ALREADY_EXISTS=false
    fi
else
    echo -e "${YELLOW}[DRY-RUN] Would check for existing instance${NC}"
    REDIS_ALREADY_EXISTS=false
fi

# Create Redis instance (if not exists)
if [ "$REDIS_ALREADY_EXISTS" = false ]; then
    echo -e "\n${CYAN}⏳ Creating Redis instance (this takes 5-10 minutes)...${NC}"
    execute_or_print \
        "gcloud redis instances create $REDIS_INSTANCE_NAME \
            --region=$REDIS_REGION \
            --zone=$REDIS_ZONE \
            --tier=$REDIS_TIER \
            --size=$REDIS_MEMORY_SIZE_GB \
            --redis-version=$REDIS_VERSION \
            --network=projects/$PROJECT_ID/global/networks/default \
            --quiet" \
        "Creating Redis instance"

    if [ "$DRY_RUN" = false ]; then
        echo -e "${GREEN}✅ Redis instance created successfully${NC}"
    fi
else
    echo -e "${GREEN}✅ Using existing Redis instance${NC}"
fi

# Get Redis connection details
echo -e "\n${CYAN}⏳ Retrieving Redis connection details...${NC}"
if [ "$DRY_RUN" = false ]; then
    REDIS_HOST=$(gcloud redis instances describe $REDIS_INSTANCE_NAME \
        --region=$REDIS_REGION \
        --format="value(host)")
    REDIS_PORT=$(gcloud redis instances describe $REDIS_INSTANCE_NAME \
        --region=$REDIS_REGION \
        --format="value(port)")

    echo -e "${GREEN}✅ Redis connection details:${NC}"
    echo -e "   Host: ${CYAN}$REDIS_HOST${NC}"
    echo -e "   Port: ${CYAN}$REDIS_PORT${NC}"
else
    echo -e "${YELLOW}[DRY-RUN] Would retrieve Redis host and port${NC}"
    REDIS_HOST="10.0.0.3"  # Example for dry-run
    REDIS_PORT="6379"
fi

# Store connection details in Secret Manager
echo -e "\n${CYAN}⏳ Storing Redis connection details in Secret Manager...${NC}"

# Create or update REDIS_HOST secret
if [ "$DRY_RUN" = false ]; then
    if gcloud secrets describe $SECRET_REDIS_HOST 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Secret $SECRET_REDIS_HOST already exists - adding new version${NC}"
        echo -n "$REDIS_HOST" | gcloud secrets versions add $SECRET_REDIS_HOST --data-file=-
    else
        echo -e "${GREEN}✅ Creating secret $SECRET_REDIS_HOST${NC}"
        echo -n "$REDIS_HOST" | gcloud secrets create $SECRET_REDIS_HOST --data-file=-
    fi
else
    echo -e "${YELLOW}[DRY-RUN] Would create/update secret: $SECRET_REDIS_HOST = $REDIS_HOST${NC}"
fi

# Create or update REDIS_PORT secret
if [ "$DRY_RUN" = false ]; then
    if gcloud secrets describe $SECRET_REDIS_PORT 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Secret $SECRET_REDIS_PORT already exists - adding new version${NC}"
        echo -n "$REDIS_PORT" | gcloud secrets versions add $SECRET_REDIS_PORT --data-file=-
    else
        echo -e "${GREEN}✅ Creating secret $SECRET_REDIS_PORT${NC}"
        echo -n "$REDIS_PORT" | gcloud secrets create $SECRET_REDIS_PORT --data-file=-
    fi
else
    echo -e "${YELLOW}[DRY-RUN] Would create/update secret: $SECRET_REDIS_PORT = $REDIS_PORT${NC}"
fi

# Grant secret access to Cloud Run services
echo -e "\n${CYAN}⏳ Granting secret access to Cloud Run services...${NC}"
SERVICES=(
    "pgp-orchestrator-v1"
    "pgp-server-v1"
    "pgp-webapi-v1"
    "pgp-np-ipn-v1"
    "pgp-invite-v1"
)

for service in "${SERVICES[@]}"; do
    if [ "$DRY_RUN" = false ]; then
        SERVICE_ACCOUNT="${service}@${PROJECT_ID}.iam.gserviceaccount.com"

        # Grant access to REDIS_HOST
        gcloud secrets add-iam-policy-binding $SECRET_REDIS_HOST \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || echo -e "${YELLOW}⚠️  Warning: Could not grant access to $service (may not exist yet)${NC}"

        # Grant access to REDIS_PORT
        gcloud secrets add-iam-policy-binding $SECRET_REDIS_PORT \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || echo -e "${YELLOW}⚠️  Warning: Could not grant access to $service (may not exist yet)${NC}"
    else
        echo -e "${YELLOW}[DRY-RUN] Would grant secret access to: $service${NC}"
    fi
done

# Print summary
echo -e "\n${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Redis Nonce Tracker Deployment Complete${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${CYAN}Connection Details:${NC}"
echo -e "  Host Secret:     ${GREEN}projects/$PROJECT_ID/secrets/$SECRET_REDIS_HOST${NC}"
echo -e "  Port Secret:     ${GREEN}projects/$PROJECT_ID/secrets/$SECRET_REDIS_PORT${NC}"
echo -e "  Host Value:      ${GREEN}$REDIS_HOST${NC}"
echo -e "  Port Value:      ${GREEN}$REDIS_PORT${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo -e "  1. Update service requirements.txt to include: ${GREEN}redis>=5.0.0${NC}"
echo -e "  2. Deploy updated services with Redis client"
echo -e "  3. Test nonce tracking with replay attack simulation"
echo -e "  4. Monitor Redis performance in Cloud Console"
echo ""
echo -e "${CYAN}Monitoring:${NC}"
echo -e "  Console: ${GREEN}https://console.cloud.google.com/memorystore/redis/locations/$REDIS_REGION/instances/$REDIS_INSTANCE_NAME?project=$PROJECT_ID${NC}"
echo ""
echo -e "${YELLOW}⚠️  Remember: This Redis instance incurs ongoing costs (~$50/month)${NC}"
echo -e "${BLUE}============================================${NC}"

exit 0
