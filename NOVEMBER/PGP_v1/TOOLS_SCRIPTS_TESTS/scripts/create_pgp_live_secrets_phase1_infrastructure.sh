#!/bin/bash
################################################################################
# create_pgp_live_secrets_phase1_infrastructure.sh
#
# Phase 1: Infrastructure Secrets (9 secrets)
# Creates database, Cloud Tasks, and Redis infrastructure secrets
#
# Prerequisites:
# - Cloud SQL instance 'pgp-live-psql' must exist
# - Memorystore Redis instance must be provisioned
# - Secret Manager API enabled
#
# Usage:
#   ./create_pgp_live_secrets_phase1_infrastructure.sh
#
# Author: PGP_v1 Migration Team
# Date: 2025-11-18
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
PROJECT="pgp-live"
REGION="us-central1"
SQL_INSTANCE="pgp-live-psql"
DATABASE_NAME="pgp-live-db"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Header
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Phase 1: Infrastructure Secrets Creation"
echo "  Project: $PROJECT"
echo "  Secrets: 9 (Database + Cloud Tasks + Redis)"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Verify project exists
log_info "Verifying GCP project: $PROJECT"
if ! gcloud projects describe "$PROJECT" &>/dev/null; then
    log_error "Project '$PROJECT' not found or inaccessible"
    exit 1
fi
log_success "Project verified"

# Set active project
gcloud config set project "$PROJECT"

# Enable Secret Manager API
log_info "Ensuring Secret Manager API is enabled..."
gcloud services enable secretmanager.googleapis.com --project="$PROJECT"
log_success "Secret Manager API enabled"

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  1. Database Credentials (5 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 1.1 CLOUD_SQL_CONNECTION_NAME
log_info "Creating CLOUD_SQL_CONNECTION_NAME"
CONNECTION_NAME="${PROJECT}:${REGION}:${SQL_INSTANCE}"
if gcloud secrets describe CLOUD_SQL_CONNECTION_NAME --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'CLOUD_SQL_CONNECTION_NAME' already exists, skipping"
else
    echo -n "$CONNECTION_NAME" | gcloud secrets create CLOUD_SQL_CONNECTION_NAME \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: CLOUD_SQL_CONNECTION_NAME = $CONNECTION_NAME"
fi

# 1.2 DATABASE_NAME_SECRET
log_info "Creating DATABASE_NAME_SECRET"
if gcloud secrets describe DATABASE_NAME_SECRET --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'DATABASE_NAME_SECRET' already exists, skipping"
else
    echo -n "$DATABASE_NAME" | gcloud secrets create DATABASE_NAME_SECRET \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: DATABASE_NAME_SECRET = $DATABASE_NAME"
fi

# 1.3 DATABASE_USER_SECRET
log_info "Creating DATABASE_USER_SECRET"
DB_USER="postgres"
if gcloud secrets describe DATABASE_USER_SECRET --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'DATABASE_USER_SECRET' already exists, skipping"
else
    echo -n "$DB_USER" | gcloud secrets create DATABASE_USER_SECRET \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: DATABASE_USER_SECRET = $DB_USER"
fi

# 1.4 DATABASE_PASSWORD_SECRET
log_info "Generating DATABASE_PASSWORD_SECRET"
if gcloud secrets describe DATABASE_PASSWORD_SECRET --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'DATABASE_PASSWORD_SECRET' already exists, skipping"
else
    DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo -n "$DB_PASSWORD" | gcloud secrets create DATABASE_PASSWORD_SECRET \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: DATABASE_PASSWORD_SECRET (64-char hex)"
    log_warning "Password preview: ${DB_PASSWORD:0:8}...${DB_PASSWORD: -8}"
    log_warning "IMPORTANT: Update Cloud SQL instance password to match this value!"
    echo ""
    echo "  Run this command to update database password:"
    echo "  gcloud sql users set-password postgres \\"
    echo "    --instance=$SQL_INSTANCE \\"
    echo "    --password='$DB_PASSWORD' \\"
    echo "    --project=$PROJECT"
    echo ""
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  2. Cloud Tasks Infrastructure (2 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 2.1 CLOUD_TASKS_PROJECT_ID
log_info "Creating CLOUD_TASKS_PROJECT_ID"
if gcloud secrets describe CLOUD_TASKS_PROJECT_ID --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'CLOUD_TASKS_PROJECT_ID' already exists, skipping"
else
    echo -n "$PROJECT" | gcloud secrets create CLOUD_TASKS_PROJECT_ID \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: CLOUD_TASKS_PROJECT_ID = $PROJECT"
fi

# 2.2 CLOUD_TASKS_LOCATION
log_info "Creating CLOUD_TASKS_LOCATION"
if gcloud secrets describe CLOUD_TASKS_LOCATION --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'CLOUD_TASKS_LOCATION' already exists, skipping"
else
    echo -n "$REGION" | gcloud secrets create CLOUD_TASKS_LOCATION \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: CLOUD_TASKS_LOCATION = $REGION"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  3. Redis / Nonce Tracking (2 secrets)"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

# 3.1 PGP_REDIS_HOST
log_info "Redis configuration required"
if gcloud secrets describe PGP_REDIS_HOST --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'PGP_REDIS_HOST' already exists, skipping"
else
    echo ""
    log_warning "You must provision a Memorystore Redis instance first:"
    echo "  1. Go to: https://console.cloud.google.com/memorystore/redis/instances?project=$PROJECT"
    echo "  2. Create instance: Name='pgp-redis-nonce', Tier=Basic, Capacity=1GB"
    echo "  3. Note the internal IP address"
    echo ""

    read -p "Enter Redis host IP (Memorystore internal IP, e.g., 10.0.0.3): " REDIS_HOST

    if [[ -z "$REDIS_HOST" ]]; then
        log_error "Redis host IP cannot be empty"
        exit 1
    fi

    echo -n "$REDIS_HOST" | gcloud secrets create PGP_REDIS_HOST \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: PGP_REDIS_HOST = $REDIS_HOST"
fi

# 3.2 PGP_REDIS_PORT
log_info "Creating PGP_REDIS_PORT"
if gcloud secrets describe PGP_REDIS_PORT --project="$PROJECT" &>/dev/null; then
    log_warning "Secret 'PGP_REDIS_PORT' already exists, skipping"
else
    echo -n "6379" | gcloud secrets create PGP_REDIS_PORT \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"
    log_success "Created: PGP_REDIS_PORT = 6379"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Phase 1: Infrastructure Secrets - COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Summary
log_success "Created 9 infrastructure secrets:"
echo "  ✅ Database Credentials (5 secrets)"
echo "  ✅ Cloud Tasks Infrastructure (2 secrets)"
echo "  ✅ Redis / Nonce Tracking (2 secrets)"
echo ""

log_info "Next steps:"
echo "  1. Update Cloud SQL database password to match DATABASE_PASSWORD_SECRET"
echo "  2. Run Phase 2: ./create_pgp_live_secrets_phase2_security.sh"
echo ""

# List all created secrets
log_info "Verifying created secrets..."
gcloud secrets list --project="$PROJECT" --filter="name:CLOUD_SQL_CONNECTION_NAME OR name:DATABASE_NAME_SECRET OR name:DATABASE_USER_SECRET OR name:DATABASE_PASSWORD_SECRET OR name:CLOUD_TASKS_PROJECT_ID OR name:CLOUD_TASKS_LOCATION OR name:PGP_REDIS_HOST OR name:PGP_REDIS_PORT"

echo ""
log_success "Phase 1 deployment completed successfully! 🎉"
