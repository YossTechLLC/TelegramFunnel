#!/bin/bash
################################################################################
# create_pgp_live_secrets_phase6_queue_names.sh
#
# Phase 6: Cloud Tasks Queue Name Secrets (17 secrets)
# Creates queue name secrets after Cloud Tasks queues are deployed
#
# ⚠️  PREREQUISITE: All Cloud Tasks queues MUST be created first!
#
# This script automatically discovers deployed Cloud Tasks queues
# and creates Secret Manager entries for each queue.
#
# All secrets in this phase are HOT-RELOADABLE (zero-downtime queue migration)
#
# Usage:
#   ./create_pgp_live_secrets_phase6_queue_names.sh
#
# Author: PGP_v1 Migration Team
# Date: 2025-11-18
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
PROJECT="pgp-live"
LOCATION="us-central1"

# Queue name mappings (Cloud Tasks queue name → Secret name)
declare -A QUEUE_MAP=(
    ["pgp-orchestrator-queue-v1"]="PGP_ORCHESTRATOR_QUEUE"
    ["pgp-invite-queue-v1"]="PGP_INVITE_QUEUE"
    ["pgp-notifications-queue-v1"]="PGP_NOTIFICATIONS_QUEUE"
    ["pgp-batchprocessor-queue-v1"]="PGP_BATCHPROCESSOR_QUEUE"
    ["pgp-split1-estimate-queue-v1"]="PGP_SPLIT1_QUEUE"
    ["pgp-split1-batch-queue-v1"]="PGP_SPLIT1_BATCH_QUEUE"
    ["pgp-split1-response-queue-v1"]="PGP_SPLIT1_RESPONSE_QUEUE"
    ["pgp-split2-swap-queue-v1"]="PGP_SPLIT2_ESTIMATE_QUEUE"
    ["pgp-split3-client-queue-v1"]="PGP_SPLIT3_SWAP_QUEUE"
    ["pgp-hostpay-trigger-queue-v1"]="PGP_HOSTPAY_TRIGGER_QUEUE"
    ["pgp-hostpay1-batch-queue-v1"]="PGP_HOSTPAY1_BATCH_QUEUE"
    ["pgp-hostpay1-response-queue-v1"]="PGP_HOSTPAY1_RESPONSE_QUEUE"
    ["pgp-hostpay2-status-queue-v1"]="PGP_HOSTPAY2_STATUS_QUEUE"
    ["pgp-hostpay3-payment-queue-v1"]="PGP_HOSTPAY3_PAYMENT_QUEUE"
    ["pgp-hostpay3-retry-queue-v1"]="PGP_HOSTPAY3_RETRY_QUEUE"
    ["pgp-microbatch-response-queue-v1"]="PGP_MICROBATCH_RESPONSE_QUEUE"
)

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
echo "  Phase 6: Cloud Tasks Queue Name Secrets"
echo "  Project: $PROJECT"
echo "  Location: $LOCATION"
echo "  Secrets: 16 (All HOT-RELOADABLE)"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Set active project
gcloud config set project "$PROJECT"

# Verify Cloud Tasks queues are created
log_info "Verifying Cloud Tasks queue deployments..."
DEPLOYED_QUEUES=$(gcloud tasks queues list --location="$LOCATION" --project="$PROJECT" --format='value(name)' 2>/dev/null || true)

if [[ -z "$DEPLOYED_QUEUES" ]]; then
    log_error "No Cloud Tasks queues found in location $LOCATION"
    log_error "Please create all Cloud Tasks queues before running this script"
    echo ""
    log_info "Example queue creation:"
    echo "  gcloud tasks queues create pgp-orchestrator-queue-v1 \\"
    echo "    --location=$LOCATION \\"
    echo "    --max-dispatches-per-second=100 \\"
    echo "    --max-concurrent-dispatches=100 \\"
    echo "    --project=$PROJECT"
    exit 1
fi

echo ""
log_success "Found deployed queues:"
echo "$DEPLOYED_QUEUES" | while read -r queue_path; do
    queue_name=$(basename "$queue_path")
    echo "  • $queue_name"
done
echo ""

# Count found vs expected
EXPECTED_COUNT=16
FOUND_COUNT=$(echo "$DEPLOYED_QUEUES" | wc -l)
log_info "Expected $EXPECTED_COUNT queues, found $FOUND_COUNT deployed"

if [[ $FOUND_COUNT -lt $EXPECTED_COUNT ]]; then
    log_warning "Some queues may be missing - continuing anyway"
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────────"
echo "  Creating Queue Name Secrets"
echo "────────────────────────────────────────────────────────────────────────────"
echo ""

CREATED_COUNT=0
SKIPPED_COUNT=0
MISSING_COUNT=0

for QUEUE_NAME in "${!QUEUE_MAP[@]}"; do
    SECRET_NAME="${QUEUE_MAP[$QUEUE_NAME]}"

    log_info "Processing: $QUEUE_NAME → $SECRET_NAME"

    # Check if secret already exists
    if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" &>/dev/null; then
        log_warning "  Secret '$SECRET_NAME' already exists, skipping"
        ((SKIPPED_COUNT++))
        continue
    fi

    # Verify queue exists
    QUEUE_EXISTS=$(gcloud tasks queues describe "$QUEUE_NAME" \
        --location="$LOCATION" \
        --project="$PROJECT" \
        --format='value(name)' 2>/dev/null || true)

    if [[ -z "$QUEUE_EXISTS" ]]; then
        log_error "  Queue '$QUEUE_NAME' not found"
        log_warning "  Skipping $SECRET_NAME - create queue first"
        ((MISSING_COUNT++))
        continue
    fi

    # Create secret (store just the queue name, not the full path)
    echo -n "$QUEUE_NAME" | gcloud secrets create "$SECRET_NAME" \
        --data-file=- \
        --replication-policy="automatic" \
        --project="$PROJECT"

    log_success "  Created: $SECRET_NAME = $QUEUE_NAME"
    ((CREATED_COUNT++))
done

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  Phase 6: Queue Name Secrets - COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Summary
log_info "Deployment Summary:"
echo "  ✅ Created: $CREATED_COUNT secrets"
echo "  ⏭️  Skipped: $SKIPPED_COUNT secrets (already exist)"
echo "  ❌ Missing: $MISSING_COUNT secrets (queues not created)"
echo ""

if [[ $MISSING_COUNT -gt 0 ]]; then
    log_warning "Some queues were not found - ensure all Cloud Tasks queues are created"
    echo ""
    log_info "Missing queues can be created with:"
    echo "  gcloud tasks queues create <QUEUE_NAME> \\"
    echo "    --location=$LOCATION \\"
    echo "    --max-dispatches-per-second=100 \\"
    echo "    --max-concurrent-dispatches=100 \\"
    echo "    --project=$PROJECT"
    echo ""
    log_info "Then create corresponding secret:"
    echo "  echo -n '<QUEUE_NAME>' | gcloud secrets create <SECRET_NAME> --data-file=- --project=$PROJECT"
fi

echo ""
log_info "All Phase 6 secrets are HOT-RELOADABLE"
log_info "Queue names can be updated for migration scenarios without service restart"
echo ""

log_info "Next steps:"
echo "  1. Grant IAM access to service accounts: ./grant_pgp_live_secret_access.sh"
echo "  2. Verify all 69 secrets: ./verify_pgp_live_secrets.sh"
echo "  3. Deploy PGP_v1 services with new secret configuration"
echo "  4. Test end-to-end payment flow"
echo ""

# List all created secrets
log_info "Listing all queue name secrets..."
gcloud secrets list --project="$PROJECT" --filter="name~'.*QUEUE'"

echo ""
if [[ $MISSING_COUNT -eq 0 ]]; then
    log_success "Phase 6 deployment completed successfully! 🎉"
else
    log_warning "Phase 6 completed with $MISSING_COUNT missing queues ⚠️"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "  🎉 All 6 Phases Complete!"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
log_success "Secret Manager deployment finished!"
log_info "Total secrets expected: 69 (across all phases)"
echo ""
log_info "Final verification steps:"
echo "  1. Run: ./verify_pgp_live_secrets.sh"
echo "  2. Grant IAM permissions: ./grant_pgp_live_secret_access.sh"
echo "  3. Test secret access from Cloud Run services"
echo ""
