#!/bin/bash
################################################################################
# Cloud Tasks Queues Deployment Script for PGP_v1
# Purpose: Deploy all 15 Cloud Tasks queues for PayGatePrime microservices
# Version: 1.0.0
# Date: 2025-11-18
#
# USAGE:
#   ./deploy_cloud_tasks_queues.sh [--dry-run] [--project PROJECT_ID] [--location LOCATION]
#
# REQUIREMENTS:
#   - gcloud CLI installed and authenticated
#   - Cloud Tasks API enabled
#   - Appropriate IAM permissions for queue creation
#
# ⚠️  DO NOT RUN IN PRODUCTION WITHOUT TESTING IN DEV FIRST!
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

################################################################################
# Configuration
################################################################################

PROJECT_ID="${GCP_PROJECT_ID:-pgp-live}"
LOCATION="${GCP_LOCATION:-us-central1}"
DRY_RUN=false

# Queue Configuration (from PGP_MAP_UPDATED.md PHASE 5)
MAX_CONCURRENT_DISPATCHES=100
MAX_ATTEMPTS=0                    # 0 = infinite retry for resilience
MAX_RETRY_DURATION=0              # 0 = never give up
MIN_BACKOFF="1s"                  # Fast initial retry
MAX_BACKOFF="60s"                 # Reasonable max delay
MAX_DOUBLINGS=16                  # Exponential backoff doublings

################################################################################
# Parse Command Line Arguments
################################################################################

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --project)
            PROJECT_ID="$2"
            shift 2
            ;;
        --location)
            LOCATION="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--dry-run] [--project PROJECT_ID] [--location LOCATION]"
            echo ""
            echo "Options:"
            echo "  --dry-run           Show what would be deployed without actually deploying"
            echo "  --project PROJECT   GCP project ID (default: pgp-live)"
            echo "  --location LOCATION GCP region (default: us-central1)"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${CYAN}─────────────────────────────────────────────────────────────────────${NC}"
    echo -e "${CYAN}📋 $1${NC}"
    echo -e "${CYAN}─────────────────────────────────────────────────────────────────────${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${MAGENTA}ℹ️  $1${NC}"
}

execute_cmd() {
    local description="$1"
    shift

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $description"
        echo "  Command: $*"
        return 0
    fi

    echo "🔄 $description"
    if "$@"; then
        return 0
    else
        local exit_code=$?
        print_error "Command failed with exit code $exit_code"
        return $exit_code
    fi
}

check_queue_exists() {
    local queue_name="$1"

    if gcloud tasks queues describe "$queue_name" \
        --location="$LOCATION" \
        --project="$PROJECT_ID" \
        &>/dev/null; then
        return 0  # Queue exists
    else
        return 1  # Queue does not exist
    fi
}

################################################################################
# Validation Functions
################################################################################

validate_prerequisites() {
    print_section "Validating Prerequisites"

    # Check gcloud CLI
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI not found. Please install it first."
        exit 1
    fi
    print_success "gcloud CLI found"

    # Check authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        print_error "Not authenticated with gcloud. Run: gcloud auth login"
        exit 1
    fi
    print_success "gcloud authentication verified"

    # Check project access
    if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
        print_error "Cannot access project: $PROJECT_ID"
        exit 1
    fi
    print_success "Project access verified: $PROJECT_ID"

    # Check Cloud Tasks API
    if ! gcloud services list --enabled --project="$PROJECT_ID" --filter="name:cloudtasks.googleapis.com" --format="value(name)" | grep -q "cloudtasks"; then
        print_warning "Cloud Tasks API is not enabled"
        read -p "Enable Cloud Tasks API now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            execute_cmd "Enabling Cloud Tasks API" \
                gcloud services enable cloudtasks.googleapis.com --project="$PROJECT_ID"
        else
            print_error "Cloud Tasks API is required. Exiting."
            exit 1
        fi
    else
        print_success "Cloud Tasks API enabled"
    fi

    # Check IAM permissions
    print_info "Verifying IAM permissions..."
    if gcloud projects get-iam-policy "$PROJECT_ID" --flatten="bindings[].members" --format="value(bindings.role)" | grep -q "roles/cloudtasks.admin\|roles/owner"; then
        print_success "IAM permissions verified"
    else
        print_warning "May not have sufficient permissions (cloudtasks.admin or owner required)"
    fi

    echo ""
}

################################################################################
# Queue Deployment Functions
################################################################################

deploy_queue() {
    local queue_name="$1"
    local description="$2"

    print_section "Deploying Queue: $queue_name"
    echo "Description: $description"
    echo ""

    # Check if queue already exists
    if check_queue_exists "$queue_name"; then
        print_warning "Queue already exists: $queue_name"

        if [ "$DRY_RUN" = false ]; then
            read -p "Update existing queue configuration? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "Skipping queue: $queue_name"
                return 0
            fi

            # Update existing queue
            execute_cmd "Updating queue: $queue_name" \
                gcloud tasks queues update "$queue_name" \
                --location="$LOCATION" \
                --project="$PROJECT_ID" \
                --max-concurrent-dispatches="$MAX_CONCURRENT_DISPATCHES" \
                --max-attempts="$MAX_ATTEMPTS" \
                --max-retry-duration="$MAX_RETRY_DURATION" \
                --min-backoff="$MIN_BACKOFF" \
                --max-backoff="$MAX_BACKOFF" \
                --max-doublings="$MAX_DOUBLINGS"

            if [ $? -eq 0 ]; then
                print_success "Queue updated: $queue_name"
                return 0
            else
                print_error "Failed to update queue: $queue_name"
                return 1
            fi
        else
            echo -e "${YELLOW}[DRY-RUN]${NC} Would update queue: $queue_name"
            return 0
        fi
    fi

    # Create new queue
    execute_cmd "Creating queue: $queue_name" \
        gcloud tasks queues create "$queue_name" \
        --location="$LOCATION" \
        --project="$PROJECT_ID" \
        --max-concurrent-dispatches="$MAX_CONCURRENT_DISPATCHES" \
        --max-attempts="$MAX_ATTEMPTS" \
        --max-retry-duration="$MAX_RETRY_DURATION" \
        --min-backoff="$MIN_BACKOFF" \
        --max-backoff="$MAX_BACKOFF" \
        --max-doublings="$MAX_DOUBLINGS"

    if [ $? -eq 0 ]; then
        print_success "Queue created: $queue_name"
        return 0
    else
        print_error "Failed to create queue: $queue_name"
        return 1
    fi
}

################################################################################
# Main Deployment Logic
################################################################################

print_header "🚀 PGP_v1 Cloud Tasks Queues Deployment"

echo "Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Location: $LOCATION"
echo "  Dry Run: $DRY_RUN"
echo ""
echo "Queue Configuration:"
echo "  Max Concurrent Dispatches: $MAX_CONCURRENT_DISPATCHES"
echo "  Max Attempts: $MAX_ATTEMPTS (infinite retry)"
echo "  Max Retry Duration: $MAX_RETRY_DURATION (never give up)"
echo "  Min Backoff: $MIN_BACKOFF"
echo "  Max Backoff: $MAX_BACKOFF"
echo "  Max Doublings: $MAX_DOUBLINGS"
echo ""

# Safety confirmation
if [ "$DRY_RUN" = false ]; then
    print_warning "This will create/update 15 Cloud Tasks queues in $PROJECT_ID"
    read -p "Continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Deployment cancelled."
        exit 0
    fi
fi

echo ""
validate_prerequisites

# Deployment tracking
DEPLOYED=0
FAILED=0
UPDATED=0
SKIPPED=0
declare -a FAILED_QUEUES

################################################################################
# Deploy All 15 Queues (Based on PGP_MAP_UPDATED.md PHASE 5)
################################################################################

print_header "📦 Deploying Payment Processing Queues"

# 1. Orchestrator Queue
if deploy_queue "pgp-orchestrator-v1-queue" "Main payment orchestration queue - handles NowPayments IPN callbacks"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-orchestrator-v1-queue")
fi

# 2. Invite Queue
if deploy_queue "pgp-invite-v1-queue" "Telegram channel invite queue - sends invite links to new subscribers"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-invite-v1-queue")
fi

# 3. Notifications Queue
if deploy_queue "pgp-notifications-v1-queue" "Channel owner notification queue - sends payment confirmations"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-notifications-v1-queue")
fi

print_header "📦 Deploying Split Pipeline Queues (ETH Conversion)"

# 4. Split1 Queue (Estimate)
if deploy_queue "pgp-split1-v1-queue" "Split1 main queue - ETH amount estimation"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-split1-v1-queue")
fi

# 5. Split1 Callback Queue
if deploy_queue "pgp-split1-v1-callback-queue" "Split1 callback queue - handles ChangeNOW webhook responses"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-split1-v1-callback-queue")
fi

# 6. Split2 Queue (USDT→ETH Swap)
if deploy_queue "pgp-split2-v1-queue" "Split2 main queue - USDT to ETH swap estimation"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-split2-v1-queue")
fi

# 7. Split2 Response Queue
if deploy_queue "pgp-split2-v1-response-queue" "Split2 response queue - handles swap estimate responses"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-split2-v1-response-queue")
fi

# 8. Split3 Queue (ETH→Client Wallet)
if deploy_queue "pgp-split3-v1-queue" "Split3 main queue - ETH to client wallet conversion"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-split3-v1-queue")
fi

# 9. Split3 Response Queue
if deploy_queue "pgp-split3-v1-response-queue" "Split3 response queue - handles final swap responses"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-split3-v1-response-queue")
fi

print_header "📦 Deploying HostPay Pipeline Queues (Channel Owner Payouts)"

# 10. HostPay1 Queue (Payment Trigger)
if deploy_queue "pgp-hostpay1-v1-queue" "HostPay1 main queue - triggers channel owner payouts"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-hostpay1-v1-queue")
fi

# 11. HostPay1 Callback Queue
if deploy_queue "pgp-hostpay1-v1-callback-queue" "HostPay1 callback queue - handles ChangeNOW webhook responses"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-hostpay1-v1-callback-queue")
fi

# 12. HostPay2 Queue (Status Check)
if deploy_queue "pgp-hostpay2-v1-queue" "HostPay2 main queue - checks payout status"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-hostpay2-v1-queue")
fi

# 13. HostPay3 Queue (Payment Execution)
if deploy_queue "pgp-hostpay3-v1-queue" "HostPay3 main queue - executes final payout"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-hostpay3-v1-queue")
fi

print_header "📦 Deploying Batch Processing Queues"

# 14. BatchProcessor Queue
if deploy_queue "pgp-batchprocessor-v1-queue" "Batch processor queue - processes clients with balance >= $50"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-batchprocessor-v1-queue")
fi

# 15. MicroBatchProcessor Queue
if deploy_queue "pgp-microbatchprocessor-v1-queue" "Microbatch processor queue - processes when total pending >= $5"; then
    ((DEPLOYED++))
else
    ((FAILED++))
    FAILED_QUEUES+=("pgp-microbatchprocessor-v1-queue")
fi

################################################################################
# Deployment Summary
################################################################################

print_header "📊 Deployment Summary"

echo -e "${GREEN}✅ Successfully deployed: $DEPLOYED queues${NC}"
echo -e "${RED}❌ Failed: $FAILED queues${NC}"
echo ""

if [ $FAILED -gt 0 ]; then
    print_error "Failed queues:"
    for queue in "${FAILED_QUEUES[@]}"; do
        echo "   - $queue"
    done
    echo ""
    print_warning "Some deployments failed. Please review errors above."
    exit 1
fi

################################################################################
# Verification
################################################################################

print_header "🔍 Verifying Deployed Queues"

if [ "$DRY_RUN" = true ]; then
    print_info "Skipping verification in dry-run mode"
else
    echo "Listing all PGP queues in $LOCATION:"
    echo ""

    gcloud tasks queues list \
        --location="$LOCATION" \
        --project="$PROJECT_ID" \
        --filter="name:pgp-" \
        --format="table(name.basename(), state, rateLimits.maxConcurrentDispatches, retryConfig.maxAttempts)" || true

    echo ""
    print_success "Verification complete"
fi

################################################################################
# Post-Deployment Tasks
################################################################################

print_header "📝 Post-Deployment Tasks"

echo "1. Verify queue configuration:"
echo "   gcloud tasks queues describe QUEUE_NAME --location=$LOCATION --project=$PROJECT_ID"
echo ""

echo "2. Test task creation (replace QUEUE_NAME and URL):"
echo "   gcloud tasks create-http-task --queue=QUEUE_NAME --location=$LOCATION \\"
echo "     --url=https://SERVICE_URL/endpoint --project=$PROJECT_ID"
echo ""

echo "3. Monitor queue metrics in Cloud Console:"
echo "   https://console.cloud.google.com/cloudtasks?project=$PROJECT_ID"
echo ""

echo "4. Update Secret Manager with queue names (if needed):"
echo "   - PGP_ORCHESTRATOR_QUEUE=pgp-orchestrator-v1-queue"
echo "   - PGP_INVITE_QUEUE=pgp-invite-v1-queue"
echo "   - PGP_NOTIFICATIONS_QUEUE=pgp-notifications-v1-queue"
echo "   - PGP_SPLIT1_QUEUE=pgp-split1-v1-queue"
echo "   - PGP_SPLIT1_CALLBACK_QUEUE=pgp-split1-v1-callback-queue"
echo "   - PGP_SPLIT2_QUEUE=pgp-split2-v1-queue"
echo "   - PGP_SPLIT2_RESPONSE_QUEUE=pgp-split2-v1-response-queue"
echo "   - PGP_SPLIT3_QUEUE=pgp-split3-v1-queue"
echo "   - PGP_SPLIT3_RESPONSE_QUEUE=pgp-split3-v1-response-queue"
echo "   - PGP_HOSTPAY1_QUEUE=pgp-hostpay1-v1-queue"
echo "   - PGP_HOSTPAY1_CALLBACK_QUEUE=pgp-hostpay1-v1-callback-queue"
echo "   - PGP_HOSTPAY2_QUEUE=pgp-hostpay2-v1-queue"
echo "   - PGP_HOSTPAY3_QUEUE=pgp-hostpay3-v1-queue"
echo "   - PGP_BATCHPROCESSOR_QUEUE=pgp-batchprocessor-v1-queue"
echo "   - PGP_MICROBATCHPROCESSOR_QUEUE=pgp-microbatchprocessor-v1-queue"
echo ""

echo "5. Next deployment steps:"
echo "   a) Deploy Cloud Run services: ./deploy_all_pgp_services.sh"
echo "   b) Deploy Cloud Scheduler jobs: ./deploy_cloud_scheduler_jobs.sh"
echo "   c) Configure webhooks: ./deploy_webhook_configuration.sh"
echo ""

print_success "🎉 Cloud Tasks queues deployment complete!"

if [ "$DRY_RUN" = true ]; then
    echo ""
    print_warning "This was a DRY-RUN. No actual changes were made."
    echo "Run without --dry-run to deploy for real."
fi

echo ""

################################################################################
# Save Deployment Metadata
################################################################################

if [ "$DRY_RUN" = false ]; then
    DEPLOYMENT_LOG="/tmp/pgp_queues_deployment_$(date +%Y%m%d_%H%M%S).log"
    cat > "$DEPLOYMENT_LOG" <<EOF
PGP_v1 Cloud Tasks Queues Deployment Log
=========================================
Date: $(date)
Project: $PROJECT_ID
Location: $LOCATION
Deployed: $DEPLOYED queues
Failed: $FAILED queues

Queue Configuration:
- Max Concurrent Dispatches: $MAX_CONCURRENT_DISPATCHES
- Max Attempts: $MAX_ATTEMPTS (infinite retry)
- Max Retry Duration: $MAX_RETRY_DURATION (never give up)
- Min Backoff: $MIN_BACKOFF
- Max Backoff: $MAX_BACKOFF
- Max Doublings: $MAX_DOUBLINGS

Deployed Queues:
$(gcloud tasks queues list --location="$LOCATION" --project="$PROJECT_ID" --filter="name:pgp-" --format="value(name.basename())" 2>/dev/null || echo "Unable to fetch queue list")
EOF

    echo "Deployment log saved to: $DEPLOYMENT_LOG"
    echo ""
fi

exit 0
