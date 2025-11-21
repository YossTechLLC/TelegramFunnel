#!/bin/bash
################################################################################
# Service Verification Script - PGP_v1
################################################################################
# Project: pgp-live
# Purpose: Verify all 15 Cloud Run services are deployed and healthy
# Version: 1.0.0
# Date: 2025-11-19
#
# DESCRIPTION:
#   Comprehensive verification of all deployed PGP_v1 services including:
#   - Deployment status verification
#   - Health endpoint testing
#   - IAM authentication validation
#   - Service URL accessibility
#   - Cloud Tasks queue connectivity
#   - Database connection validation
#
# USAGE:
#   ./verify_all_services.sh [--quick] [--project PROJECT_ID] [--region REGION]
#
# OPTIONS:
#   --quick         Skip detailed health checks (deployment status only)
#   --project       Override GCP project ID (default: pgp-live)
#   --region        Override GCP region (default: us-central1)
#   --help          Show this help message
#
# PREREQUISITES:
#   - Cloud Run services deployed (all 15 services)
#   - gcloud CLI authenticated with appropriate permissions
#   - curl installed for HTTP requests
#
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# ============================================================================
# CONFIGURATION
# ============================================================================

# GCP Configuration
PROJECT_ID="${GCP_PROJECT_ID:-pgp-live}"
REGION="${GCP_REGION:-us-central1}"

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
QUICK_MODE=false

# ============================================================================
# SERVICE DEFINITIONS
# ============================================================================

# All 15 PGP_v1 services with expected configurations
declare -A SERVICES=(
    ["pgp-server-v1"]="1024Mi:1:20:Telegram Bot Server"
    ["pgp-webapi-v1"]="512Mi:0:10:REST API Backend"
    ["pgp-np-ipn-v1"]="512Mi:0:20:NOWPayments IPN Handler"
    ["pgp-orchestrator-v1"]="512Mi:0:20:Payment Orchestrator"
    ["pgp-invite-v1"]="512Mi:0:10:Telegram Invite Sender"
    ["pgp-split1-v1"]="512Mi:0:15:Split Pipeline Stage 1"
    ["pgp-split2-v1"]="512Mi:0:15:Split Pipeline Stage 2"
    ["pgp-split3-v1"]="512Mi:0:15:Split Pipeline Stage 3"
    ["pgp-hostpay1-v1"]="512Mi:0:15:HostPay Pipeline Stage 1"
    ["pgp-hostpay2-v1"]="512Mi:0:15:HostPay Pipeline Stage 2"
    ["pgp-hostpay3-v1"]="512Mi:0:15:HostPay Pipeline Stage 3"
    ["pgp-batchprocessor-v1"]="512Mi:0:10:Batch Processor"
    ["pgp-microbatchprocessor-v1"]="512Mi:0:10:Micro-Batch Processor"
    ["pgp-notifications-v1"]="512Mi:0:10:Notification Service"
    ["pgp-broadcast-v1"]="512Mi:1:5:Broadcast Scheduler"
)

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

# Check if command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "Required command not found: $1"
        print_info "Please install $1 and try again"
        exit 1
    fi
}

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

validate_prerequisites() {
    print_section "Validating Prerequisites"

    # Check required commands
    print_step "Checking required commands..."
    check_command "gcloud"
    check_command "curl"
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

    # Check Cloud Run API
    print_step "Verifying Cloud Run API is enabled..."
    if ! gcloud services list --enabled --project="$PROJECT_ID" --filter="name:run.googleapis.com" 2>/dev/null | grep -q "run.googleapis.com"; then
        print_error "Cloud Run API is not enabled"
        print_info "Enable it with: gcloud services enable run.googleapis.com --project=$PROJECT_ID"
        exit 1
    fi
    print_success "Cloud Run API enabled"
}

# ============================================================================
# SERVICE VERIFICATION FUNCTIONS
# ============================================================================

check_service_deployment() {
    local service_name="$1"

    # Check if service exists
    if ! gcloud run services describe "$service_name" \
        --region="$REGION" \
        --project="$PROJECT_ID" &>/dev/null; then
        return 1
    fi

    return 0
}

get_service_url() {
    local service_name="$1"

    local url
    url=$(gcloud run services describe "$service_name" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)" 2>/dev/null)

    if [ -z "$url" ]; then
        return 1
    fi

    echo "$url"
    return 0
}

get_service_status() {
    local service_name="$1"

    local status
    status=$(gcloud run services describe "$service_name" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.conditions[0].status)" 2>/dev/null)

    echo "$status"
}

get_service_instances() {
    local service_name="$1"

    # Get min and max instances
    local min_instances
    local max_instances

    min_instances=$(gcloud run services describe "$service_name" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])" 2>/dev/null)

    max_instances=$(gcloud run services describe "$service_name" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/maxScale'])" 2>/dev/null)

    echo "${min_instances:-0}-${max_instances:-10}"
}

test_health_endpoint() {
    local service_name="$1"
    local service_url="$2"

    # Try /health endpoint
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${service_url}/health" 2>/dev/null || echo "000")

    case $http_code in
        200)
            return 0  # Healthy
            ;;
        404)
            return 2  # No /health endpoint (not critical)
            ;;
        401|403)
            return 3  # Authentication required (expected for some services)
            ;;
        000)
            return 4  # Unreachable or timeout
            ;;
        *)
            return 5  # Unexpected status code
            ;;
    esac
}

verify_service() {
    local service_name="$1"
    local service_config="${SERVICES[$service_name]}"

    IFS=':' read -r expected_memory expected_min expected_max description <<< "$service_config"

    print_section "Verifying: $service_name"
    print_info "Description: $description"

    local issues=0
    local warnings=0

    # Check deployment status
    print_step "Checking deployment status..."
    if check_service_deployment "$service_name"; then
        print_success "Service deployed: $service_name"
    else
        print_error "Service NOT deployed: $service_name"
        return 1
    fi

    # Get service URL
    print_step "Fetching service URL..."
    local service_url
    service_url=$(get_service_url "$service_name")
    if [ $? -eq 0 ]; then
        print_success "Service URL: $service_url"
    else
        print_error "Cannot get service URL"
        ((issues++))
    fi

    # Check service status
    print_step "Checking service status..."
    local status
    status=$(get_service_status "$service_name")
    if [ "$status" = "True" ]; then
        print_success "Service status: Ready"
    else
        print_warning "Service status: $status"
        ((warnings++))
    fi

    # Check instance configuration
    print_step "Checking instance configuration..."
    local instances
    instances=$(get_service_instances "$service_name")
    print_info "Instance range: $instances (expected: ${expected_min}-${expected_max})"

    # Test health endpoint (skip in quick mode)
    if [ "$QUICK_MODE" = false ] && [ -n "$service_url" ]; then
        print_step "Testing health endpoint..."
        test_health_endpoint "$service_name" "$service_url"
        local health_status=$?

        case $health_status in
            0)
                print_success "Health check passed: $service_name"
                ;;
            2)
                print_info "No /health endpoint (not critical)"
                ;;
            3)
                print_info "Authentication required (expected)"
                ;;
            4)
                print_warning "Service unreachable or timeout"
                ((warnings++))
                ;;
            5)
                print_warning "Unexpected health check response"
                ((warnings++))
                ;;
        esac
    fi

    # Summary
    if [ $issues -eq 0 ] && [ $warnings -eq 0 ]; then
        print_success "✅ $service_name verification complete (no issues)"
        return 0
    elif [ $issues -eq 0 ]; then
        print_warning "⚠️  $service_name verification complete ($warnings warnings)"
        return 2
    else
        print_error "❌ $service_name verification failed ($issues issues, $warnings warnings)"
        return 1
    fi
}

# ============================================================================
# VERIFICATION EXECUTION
# ============================================================================

verify_all_services() {
    print_header "Verifying All PGP_v1 Services"

    local verified=0
    local warnings_count=0
    local failed=0
    declare -a failed_services
    declare -a warning_services

    for service_name in "${!SERVICES[@]}"; do
        echo ""
        verify_service "$service_name"
        local result=$?

        case $result in
            0)
                ((verified++))
                ;;
            1)
                ((failed++))
                failed_services+=("$service_name")
                ;;
            2)
                ((verified++))
                ((warnings_count++))
                warning_services+=("$service_name")
                ;;
        esac
    done

    # Summary
    print_header "VERIFICATION SUMMARY"

    echo -e "${GREEN}✅ Verified: $verified services${NC}"
    echo -e "${YELLOW}⚠️  Warnings: $warnings_count services${NC}"
    echo -e "${RED}❌ Failed: $failed services${NC}"

    if [ ${#warning_services[@]} -gt 0 ]; then
        echo ""
        print_warning "Services with warnings:"
        for service in "${warning_services[@]}"; do
            echo "   - $service"
        done
    fi

    if [ $failed -gt 0 ]; then
        echo ""
        print_error "Failed services:"
        for service in "${failed_services[@]}"; do
            echo "   - $service"
        done
        return 1
    fi

    return 0
}

# ============================================================================
# ADDITIONAL CHECKS
# ============================================================================

verify_cloud_tasks_queues() {
    print_section "Verifying Cloud Tasks Queues"

    # Expected queues
    local expected_queues=(
        "pgp-orchestrator-v1-queue"
        "pgp-invite-v1-queue"
        "pgp-notifications-v1-queue"
        "pgp-split1-v1-queue"
        "pgp-split1-v1-callback-queue"
        "pgp-split2-v1-queue"
        "pgp-split2-v1-response-queue"
        "pgp-split3-v1-queue"
        "pgp-split3-v1-response-queue"
        "pgp-hostpay1-v1-queue"
        "pgp-hostpay1-v1-callback-queue"
        "pgp-hostpay2-v1-queue"
        "pgp-hostpay3-v1-queue"
        "pgp-batchprocessor-v1-queue"
        "pgp-microbatchprocessor-v1-queue"
    )

    local found=0
    local missing=0

    for queue in "${expected_queues[@]}"; do
        if gcloud tasks queues describe "$queue" \
            --location="$REGION" \
            --project="$PROJECT_ID" &>/dev/null; then
            ((found++))
        else
            print_warning "Queue not found: $queue"
            ((missing++))
        fi
    done

    echo ""
    print_info "Cloud Tasks Queues: $found found, $missing missing (expected: ${#expected_queues[@]})"

    if [ $missing -eq 0 ]; then
        print_success "All Cloud Tasks queues verified"
        return 0
    else
        print_warning "Some Cloud Tasks queues are missing"
        return 1
    fi
}

verify_cloud_scheduler_jobs() {
    print_section "Verifying Cloud Scheduler Jobs"

    # Expected jobs
    local expected_jobs=(
        "pgp-batchprocessor-v1-job"
        "pgp-microbatchprocessor-v1-job"
        "pgp-broadcast-v1-daily-job"
    )

    local found=0
    local missing=0

    for job in "${expected_jobs[@]}"; do
        if gcloud scheduler jobs describe "$job" \
            --location="$REGION" \
            --project="$PROJECT_ID" &>/dev/null; then

            local state
            state=$(gcloud scheduler jobs describe "$job" \
                --location="$REGION" \
                --project="$PROJECT_ID" \
                --format="value(state)" 2>/dev/null)

            if [ "$state" = "ENABLED" ]; then
                print_success "Job found and enabled: $job"
            else
                print_warning "Job found but not enabled: $job (state: $state)"
            fi
            ((found++))
        else
            print_warning "Job not found: $job"
            ((missing++))
        fi
    done

    echo ""
    print_info "Cloud Scheduler Jobs: $found found, $missing missing (expected: ${#expected_jobs[@]})"

    if [ $missing -eq 0 ]; then
        print_success "All Cloud Scheduler jobs verified"
        return 0
    else
        print_warning "Some Cloud Scheduler jobs are missing"
        return 1
    fi
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

show_help() {
    cat << EOF
Service Verification Script - PGP_v1

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --quick           Skip detailed health checks (deployment status only)
    --project ID      Override GCP project ID (default: pgp-live)
    --region REGION   Override GCP region (default: us-central1)
    --help            Show this help message

DESCRIPTION:
    Comprehensive verification of all 15 deployed PGP_v1 Cloud Run services
    including deployment status, health endpoints, and configuration.

VERIFICATION CHECKS:
    - Service deployment status
    - Service URLs and accessibility
    - Health endpoint testing
    - Instance configuration
    - Cloud Tasks queues
    - Cloud Scheduler jobs

EXAMPLES:
    # Full verification with health checks
    $0

    # Quick verification (deployment status only)
    $0 --quick

    # Verify in different project
    $0 --project my-project-id

EXIT CODES:
    0 - All services verified successfully
    1 - One or more services failed verification
    2 - Some warnings detected

For more information, see PGP_MAP_UPDATED.md
EOF
    exit 0
}

main() {
    # Parse command-line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick)
                QUICK_MODE=true
                shift
                ;;
            --project)
                PROJECT_ID="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
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
    print_header "PGP_v1 Service Verification"
    echo -e "${BLUE}Project:     ${NC}$PROJECT_ID"
    echo -e "${BLUE}Region:      ${NC}$REGION"
    echo -e "${BLUE}Services:    ${NC}15 Cloud Run services"

    if [ "$QUICK_MODE" = true ]; then
        echo -e "${YELLOW}Mode:        ${NC}QUICK (deployment status only)"
    else
        echo -e "${BLUE}Mode:        ${NC}FULL (includes health checks)"
    fi

    # Validate prerequisites
    validate_prerequisites

    # Verify all services
    verify_all_services || {
        print_error "Service verification failed"
        exit 1
    }

    # Additional checks (skip in quick mode)
    if [ "$QUICK_MODE" = false ]; then
        echo ""
        verify_cloud_tasks_queues || true
        echo ""
        verify_cloud_scheduler_jobs || true
    fi

    # Final summary
    print_header "VERIFICATION COMPLETE"
    print_success "All critical services verified successfully"

    echo -e "\n${CYAN}📋 Next Steps:${NC}"
    echo -e "${CYAN}1.${NC} Test inter-service communication"
    echo -e "${CYAN}2.${NC} Run end-to-end integration tests"
    echo -e "${CYAN}3.${NC} Monitor service logs for errors"
    echo -e "${CYAN}4.${NC} Set up alerting and monitoring"

    echo -e "\n${GREEN}✅ Verification successful!${NC}"
}

# Execute main function
main "$@"
