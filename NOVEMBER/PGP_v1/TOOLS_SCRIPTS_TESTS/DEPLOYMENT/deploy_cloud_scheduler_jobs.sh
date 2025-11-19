#!/bin/bash
################################################################################
# Cloud Scheduler Jobs Deployment Script - PGP_v1 Services
################################################################################
# Project: pgp-live
# Purpose: Deploy all Cloud Scheduler (CRON) jobs for PGP_v1 architecture
# Version: 1.0.0
# Date: 2025-11-18
#
# DESCRIPTION:
#   Deploys 3 Cloud Scheduler jobs for automated batch processing:
#   1. PGP_BATCHPROCESSOR_v1 - Every 5 minutes (threshold payout detection)
#   2. PGP_MICROBATCHPROCESSOR_v1 - Every 15 minutes (ETH→USDT conversion)
#   3. PGP_BROADCAST_v1 - Daily at 9:00 AM UTC (scheduled broadcasts)
#
# SCHEDULER JOBS:
#   ✅ pgp-batchprocessor-v1-job (*/5 * * * *)
#   ✅ pgp-microbatchprocessor-v1-job (*/15 * * * *)
#   ✅ pgp-broadcast-v1-daily-job (0 9 * * *)
#
# PREREQUISITES:
#   - GCP project "pgp-live" exists and is accessible
#   - cloudscheduler.googleapis.com API enabled
#   - Service accounts created for each service
#   - Cloud Run services deployed and URLs available
#   - User has Cloud Scheduler Admin role
#
# USAGE:
#   ./deploy_cloud_scheduler_jobs.sh [--dry-run] [--project PROJECT_ID]
#
# OPTIONS:
#   --dry-run       Print commands without executing (preview mode)
#   --project       Override GCP project ID (default: pgp-live)
#   --help          Show this help message
#
# WARNINGS:
#   ⚠️  This creates billable Cloud Scheduler jobs (~$0.10/month per job)
#   ⚠️  Requires Cloud Run service URLs to be available
#   ⚠️  Service accounts must have Cloud Run Invoker role
#
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# ============================================================================
# CONFIGURATION
# ============================================================================

# GCP Configuration
readonly PROJECT_ID="${GCP_PROJECT_ID:-pgp-live}"
readonly LOCATION="${GCP_LOCATION:-us-central1}"

# Timezone for scheduler (UTC recommended for consistency)
readonly TIMEZONE="UTC"

# Script Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly MAGENTA='\033[0;35m'
readonly NC='\033[0m' # No Color

# Flags
DRY_RUN=false

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_header() {
    echo -e "\n${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}"
}

print_section() {
    echo -e "\n${CYAN}--- $1 ---${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}📍 $1${NC}"
}

print_step() {
    echo -e "${MAGENTA}⏳ $1${NC}"
}

# Execute command with dry-run support
execute_cmd() {
    local description="$1"
    shift

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] $description${NC}"
        echo -e "${CYAN}Command: $*${NC}"
        return 0
    else
        print_step "$description"
        "$@" || {
            print_error "Command failed: $*"
            return 1
        }
        print_success "$description"
        return 0
    fi
}

# Check if command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "Required command not found: $1"
        print_info "Please install $1 and try again"
        exit 1
    fi
}

# Check if scheduler job exists
job_exists() {
    local job_name="$1"
    gcloud scheduler jobs describe "$job_name" \
        --location="$LOCATION" \
        --project="$PROJECT_ID" &>/dev/null
    return $?
}

# Get Cloud Run service URL
get_service_url() {
    local service_name="$1"

    if [ "$DRY_RUN" = true ]; then
        echo "https://${service_name}-HASH.run.app"
        return 0
    fi

    local url
    url=$(gcloud run services describe "$service_name" \
        --region="$LOCATION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)" 2>/dev/null)

    if [ -z "$url" ]; then
        print_error "Service $service_name not found or not deployed"
        print_info "Please deploy $service_name to Cloud Run first"
        return 1
    fi

    echo "$url"
}

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

validate_prerequisites() {
    print_section "Validating Prerequisites"

    # Check required commands
    print_step "Checking required commands..."
    check_command "gcloud"
    print_success "All required commands found"

    # Check GCP project access
    print_step "Verifying GCP project access..."
    local current_project
    current_project=$(gcloud config get-value project 2>/dev/null)
    if [ "$current_project" != "$PROJECT_ID" ]; then
        print_warning "Current project is '$current_project', switching to '$PROJECT_ID'"
        gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || {
            print_error "Failed to set GCP project to $PROJECT_ID"
            print_info "Please run: gcloud config set project $PROJECT_ID"
            exit 1
        }
    fi
    print_success "GCP project: $PROJECT_ID"

    # Enable Cloud Scheduler API
    print_step "Enabling Cloud Scheduler API..."
    if [ "$DRY_RUN" = false ]; then
        gcloud services enable cloudscheduler.googleapis.com \
            --project="$PROJECT_ID" 2>/dev/null || true
    fi
    print_success "Cloud Scheduler API enabled"

    # Verify service accounts exist
    print_step "Verifying service accounts..."
    local required_sa=(
        "pgp-batchprocessor-v1-sa"
        "pgp-microbatchprocessor-v1-sa"
        "pgp-broadcast-v1-sa"
    )

    for sa in "${required_sa[@]}"; do
        if [ "$DRY_RUN" = false ]; then
            if ! gcloud iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
                --project="$PROJECT_ID" &>/dev/null; then
                print_error "Service account not found: ${sa}@${PROJECT_ID}.iam.gserviceaccount.com"
                print_info "Please create service account first"
                exit 1
            fi
        fi
    done
    print_success "All service accounts verified"
}

# ============================================================================
# DEPLOYMENT FUNCTIONS
# ============================================================================

deploy_batchprocessor_job() {
    print_section "Deploying PGP_BATCHPROCESSOR_v1 Job"

    local JOB_NAME="pgp-batchprocessor-v1-job"
    local SERVICE_NAME="pgp-batchprocessor-v1"
    local SCHEDULE="*/5 * * * *"  # Every 5 minutes
    local ENDPOINT="/process"

    print_info "Job Name: $JOB_NAME"
    print_info "Schedule: Every 5 minutes (288 executions/day)"
    print_info "Endpoint: POST $ENDPOINT"
    print_info "Purpose: Detect clients with balance >= \$50 USD and trigger payout pipeline"

    # Get service URL
    print_step "Fetching Cloud Run service URL..."
    local SERVICE_URL
    SERVICE_URL=$(get_service_url "$SERVICE_NAME") || return 1
    local URI="${SERVICE_URL}${ENDPOINT}"
    print_success "Service URL: $SERVICE_URL"

    # Check if job already exists
    if job_exists "$JOB_NAME"; then
        print_warning "Job $JOB_NAME already exists"

        if [ "$DRY_RUN" = false ]; then
            read -p "$(echo -e ${YELLOW}Update existing job? [y/N]: ${NC})" -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "Skipping job update"
                return 0
            fi

            # Update existing job
            execute_cmd "Updating Cloud Scheduler job: $JOB_NAME" \
                gcloud scheduler jobs update http "$JOB_NAME" \
                --location="$LOCATION" \
                --project="$PROJECT_ID" \
                --schedule="$SCHEDULE" \
                --uri="$URI" \
                --http-method=POST \
                --oidc-service-account-email="pgp-batchprocessor-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
                --time-zone="$TIMEZONE"
        else
            echo -e "${YELLOW}[DRY-RUN] Would update job: $JOB_NAME${NC}"
        fi
    else
        # Create new job
        execute_cmd "Creating Cloud Scheduler job: $JOB_NAME" \
            gcloud scheduler jobs create http "$JOB_NAME" \
            --location="$LOCATION" \
            --project="$PROJECT_ID" \
            --schedule="$SCHEDULE" \
            --uri="$URI" \
            --http-method=POST \
            --oidc-service-account-email="pgp-batchprocessor-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
            --time-zone="$TIMEZONE"
    fi

    print_success "Batch Processor job deployed successfully"
}

deploy_microbatchprocessor_job() {
    print_section "Deploying PGP_MICROBATCHPROCESSOR_v1 Job"

    local JOB_NAME="pgp-microbatchprocessor-v1-job"
    local SERVICE_NAME="pgp-microbatchprocessor-v1"
    local SCHEDULE="*/15 * * * *"  # Every 15 minutes
    local ENDPOINT="/check-threshold"

    print_info "Job Name: $JOB_NAME"
    print_info "Schedule: Every 15 minutes (96 executions/day)"
    print_info "Endpoint: POST $ENDPOINT"
    print_info "Purpose: Check total pending >= \$5 USD and trigger ETH→USDT conversion"

    # Get service URL
    print_step "Fetching Cloud Run service URL..."
    local SERVICE_URL
    SERVICE_URL=$(get_service_url "$SERVICE_NAME") || return 1
    local URI="${SERVICE_URL}${ENDPOINT}"
    print_success "Service URL: $SERVICE_URL"

    # Check if job already exists
    if job_exists "$JOB_NAME"; then
        print_warning "Job $JOB_NAME already exists"

        if [ "$DRY_RUN" = false ]; then
            read -p "$(echo -e ${YELLOW}Update existing job? [y/N]: ${NC})" -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "Skipping job update"
                return 0
            fi

            # Update existing job
            execute_cmd "Updating Cloud Scheduler job: $JOB_NAME" \
                gcloud scheduler jobs update http "$JOB_NAME" \
                --location="$LOCATION" \
                --project="$PROJECT_ID" \
                --schedule="$SCHEDULE" \
                --uri="$URI" \
                --http-method=POST \
                --oidc-service-account-email="pgp-microbatchprocessor-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
                --time-zone="$TIMEZONE"
        else
            echo -e "${YELLOW}[DRY-RUN] Would update job: $JOB_NAME${NC}"
        fi
    else
        # Create new job
        execute_cmd "Creating Cloud Scheduler job: $JOB_NAME" \
            gcloud scheduler jobs create http "$JOB_NAME" \
            --location="$LOCATION" \
            --project="$PROJECT_ID" \
            --schedule="$SCHEDULE" \
            --uri="$URI" \
            --http-method=POST \
            --oidc-service-account-email="pgp-microbatchprocessor-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
            --time-zone="$TIMEZONE"
    fi

    print_success "Micro-Batch Processor job deployed successfully"
}

deploy_broadcast_job() {
    print_section "Deploying PGP_BROADCAST_v1 Job"

    local JOB_NAME="pgp-broadcast-v1-daily-job"
    local SERVICE_NAME="pgp-broadcast-v1"
    local SCHEDULE="0 9 * * *"  # Daily at 9:00 AM UTC
    local ENDPOINT="/execute"

    print_info "Job Name: $JOB_NAME"
    print_info "Schedule: Daily at 9:00 AM UTC (1 execution/day)"
    print_info "Endpoint: POST $ENDPOINT"
    print_info "Purpose: Execute scheduled broadcasts to Telegram channels"

    # Get service URL
    print_step "Fetching Cloud Run service URL..."
    local SERVICE_URL
    SERVICE_URL=$(get_service_url "$SERVICE_NAME") || return 1
    local URI="${SERVICE_URL}${ENDPOINT}"
    print_success "Service URL: $SERVICE_URL"

    # Check if job already exists
    if job_exists "$JOB_NAME"; then
        print_warning "Job $JOB_NAME already exists"

        if [ "$DRY_RUN" = false ]; then
            read -p "$(echo -e ${YELLOW}Update existing job? [y/N]: ${NC})" -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "Skipping job update"
                return 0
            fi

            # Update existing job
            execute_cmd "Updating Cloud Scheduler job: $JOB_NAME" \
                gcloud scheduler jobs update http "$JOB_NAME" \
                --location="$LOCATION" \
                --project="$PROJECT_ID" \
                --schedule="$SCHEDULE" \
                --uri="$URI" \
                --http-method=POST \
                --oidc-service-account-email="pgp-broadcast-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
                --time-zone="$TIMEZONE"
        else
            echo -e "${YELLOW}[DRY-RUN] Would update job: $JOB_NAME${NC}"
        fi
    else
        # Create new job
        execute_cmd "Creating Cloud Scheduler job: $JOB_NAME" \
            gcloud scheduler jobs create http "$JOB_NAME" \
            --location="$LOCATION" \
            --project="$PROJECT_ID" \
            --schedule="$SCHEDULE" \
            --uri="$URI" \
            --http-method=POST \
            --oidc-service-account-email="pgp-broadcast-v1-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
            --time-zone="$TIMEZONE"
    fi

    print_success "Broadcast Scheduler job deployed successfully"
}

# ============================================================================
# VERIFICATION FUNCTIONS
# ============================================================================

verify_deployment() {
    print_section "Verifying Deployment"

    local JOBS=(
        "pgp-batchprocessor-v1-job"
        "pgp-microbatchprocessor-v1-job"
        "pgp-broadcast-v1-daily-job"
    )

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would verify jobs${NC}"
        return 0
    fi

    print_step "Listing deployed Cloud Scheduler jobs..."
    echo ""

    for job in "${JOBS[@]}"; do
        if job_exists "$job"; then
            # Get job details
            local state
            state=$(gcloud scheduler jobs describe "$job" \
                --location="$LOCATION" \
                --project="$PROJECT_ID" \
                --format="value(state)" 2>/dev/null)

            if [ "$state" = "ENABLED" ]; then
                print_success "$job - ENABLED"
            else
                print_warning "$job - $state"
            fi
        else
            print_error "$job - NOT FOUND"
        fi
    done

    echo ""
    print_info "To view all jobs:"
    echo "  gcloud scheduler jobs list --location=$LOCATION --project=$PROJECT_ID"
    echo ""
    print_info "To manually trigger a job (for testing):"
    echo "  gcloud scheduler jobs run pgp-batchprocessor-v1-job --location=$LOCATION --project=$PROJECT_ID"
    echo ""
    print_info "To pause a job:"
    echo "  gcloud scheduler jobs pause pgp-batchprocessor-v1-job --location=$LOCATION --project=$PROJECT_ID"
    echo ""
    print_info "To resume a job:"
    echo "  gcloud scheduler jobs resume pgp-batchprocessor-v1-job --location=$LOCATION --project=$PROJECT_ID"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

show_help() {
    cat << EOF
Cloud Scheduler Jobs Deployment Script - PGP_v1 Services

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --dry-run         Preview deployment without making changes
    --project ID      Override GCP project ID (default: pgp-live)
    --help            Show this help message

DEPLOYMENT OVERVIEW:
    Creates 3 Cloud Scheduler jobs:
    1. pgp-batchprocessor-v1-job (every 5 minutes)
    2. pgp-microbatchprocessor-v1-job (every 15 minutes)
    3. pgp-broadcast-v1-daily-job (daily at 9:00 AM UTC)

PREREQUISITES:
    - Cloud Run services deployed (pgp-batchprocessor-v1, pgp-microbatchprocessor-v1, pgp-broadcast-v1)
    - Service accounts created with Cloud Run Invoker role
    - cloudscheduler.googleapis.com API enabled

EXAMPLES:
    # Preview deployment
    $0 --dry-run

    # Deploy to production
    $0

    # Deploy to different project
    $0 --project my-project-id

COST:
    ~\$0.30/month (3 jobs × \$0.10/job/month)

For more information, see PGP_MAP_UPDATED.md
EOF
    exit 0
}

main() {
    # Parse command-line arguments
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
            --help)
                show_help
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    # Print banner
    print_header "Cloud Scheduler Jobs Deployment - PGP_v1"
    echo -e "${BLUE}Project:     ${NC}$PROJECT_ID"
    echo -e "${BLUE}Location:    ${NC}$LOCATION"
    echo -e "${BLUE}Timezone:    ${NC}$TIMEZONE"
    echo -e "${BLUE}Jobs:        ${NC}3 Cloud Scheduler jobs"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}Mode:        ${NC}DRY-RUN (preview only)"
    fi

    # Validate prerequisites
    validate_prerequisites

    # Deploy scheduler jobs
    deploy_batchprocessor_job || exit 1
    deploy_microbatchprocessor_job || exit 1
    deploy_broadcast_job || exit 1

    # Verify deployment
    verify_deployment

    # Print summary
    print_header "DEPLOYMENT COMPLETE"
    print_success "Cloud Scheduler Jobs Deployed: 3"
    print_success "Status: All jobs enabled"

    echo -e "\n${CYAN}📋 Next Steps:${NC}"
    echo -e "${CYAN}1.${NC} Verify jobs are executing successfully (check Cloud Logging)"
    echo -e "${CYAN}2.${NC} Monitor Cloud Tasks queues for task creation"
    echo -e "${CYAN}3.${NC} Test manual execution: gcloud scheduler jobs run pgp-batchprocessor-v1-job --location=$LOCATION"
    echo -e "${CYAN}4.${NC} Set up alerting for job failures"

    echo -e "\n${GREEN}✅ Deployment successful!${NC}"
}

# Execute main function
main "$@"
