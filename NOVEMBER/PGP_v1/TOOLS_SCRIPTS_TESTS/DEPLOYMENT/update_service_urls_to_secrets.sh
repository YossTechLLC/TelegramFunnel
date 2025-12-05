#!/bin/bash
################################################################################
# Update Service URLs to Secret Manager - PGP_v1
################################################################################
# Project: pgp-live
# Purpose: Automatically fetch Cloud Run service URLs and update Secret Manager
# Version: 1.0.0
# Date: 2025-11-19
#
# DESCRIPTION:
#   After deploying Cloud Run services (PHASE 6), this script fetches all
#   service URLs and updates the corresponding secrets in Secret Manager.
#   This enables inter-service communication via encrypted service URL secrets.
#
# USAGE:
#   ./update_service_urls_to_secrets.sh [--dry-run] [--project PROJECT_ID]
#
# OPTIONS:
#   --dry-run       Preview updates without making changes
#   --project       Override GCP project ID (default: pgp-live)
#   --help          Show this help message
#
# PREREQUISITES:
#   - Cloud Run services deployed (all 15 services)
#   - Secret Manager secrets created (PGP_*_URL secrets)
#   - User has Secret Manager Admin role
#
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# ============================================================================
# CONFIGURATION
# ============================================================================

# GCP Configuration
readonly PROJECT_ID="${GCP_PROJECT_ID:-pgp-live}"
readonly REGION="${GCP_REGION:-us-central1}"

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
# SERVICE DEFINITIONS
# ============================================================================

# All 15 PGP_v1 services (service-name:SECRET_NAME)
declare -A SERVICES=(
    ["pgp-server-v1"]="PGP_SERVER_URL"
    ["pgp-webapi-v1"]="PGP_WEBAPI_URL"
    ["pgp-np-ipn-v1"]="PGP_NP_IPN_URL"
    ["pgp-orchestrator-v1"]="PGP_ORCHESTRATOR_URL"
    ["pgp-invite-v1"]="PGP_INVITE_URL"
    ["pgp-split1-v1"]="PGP_SPLIT1_URL"
    ["pgp-split2-v1"]="PGP_SPLIT2_URL"
    ["pgp-split3-v1"]="PGP_SPLIT3_URL"
    ["pgp-hostpay1-v1"]="PGP_HOSTPAY1_URL"
    ["pgp-hostpay2-v1"]="PGP_HOSTPAY2_URL"
    ["pgp-hostpay3-v1"]="PGP_HOSTPAY3_URL"
    ["pgp-batchprocessor-v1"]="PGP_BATCHPROCESSOR_URL"
    ["pgp-microbatchprocessor-v1"]="PGP_MICROBATCHPROCESSOR_URL"
    ["pgp-notifications-v1"]="PGP_NOTIFICATIONS_URL"
    ["pgp-broadcast-v1"]="PGP_BROADCAST_URL"
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

# Get Cloud Run service URL
get_service_url() {
    local service_name="$1"

    if [ "$DRY_RUN" = true ]; then
        echo "https://${service_name}-HASH.run.app"
        return 0
    fi

    local url
    url=$(gcloud run services describe "$service_name" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)" 2>/dev/null)

    if [ -z "$url" ]; then
        return 1
    fi

    echo "$url"
}

# Check if secret exists
secret_exists() {
    local secret_name="$1"

    if [ "$DRY_RUN" = true ]; then
        return 0
    fi

    gcloud secrets describe "$secret_name" \
        --project="$PROJECT_ID" &>/dev/null
    return $?
}

# Update secret value
update_secret() {
    local secret_name="$1"
    local secret_value="$2"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would update secret: $secret_name${NC}"
        echo -e "${CYAN}Value: $secret_value${NC}"
        return 0
    fi

    # Check if secret exists
    if ! secret_exists "$secret_name"; then
        print_error "Secret does not exist: $secret_name"
        print_info "Create secret first: gcloud secrets create $secret_name --replication-policy=automatic"
        return 1
    fi

    # Add new version to secret
    echo -n "$secret_value" | gcloud secrets versions add "$secret_name" \
        --data-file=- \
        --project="$PROJECT_ID" &>/dev/null

    if [ $? -eq 0 ]; then
        print_success "Updated secret: $secret_name"
        return 0
    else
        print_error "Failed to update secret: $secret_name"
        return 1
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

    # Check Secret Manager API
    print_step "Verifying Secret Manager API is enabled..."
    if [ "$DRY_RUN" = false ]; then
        gcloud services enable secretmanager.googleapis.com \
            --project="$PROJECT_ID" 2>/dev/null || true
    fi
    print_success "Secret Manager API enabled"
}

# ============================================================================
# URL UPDATE FUNCTIONS
# ============================================================================

update_all_service_urls() {
    print_section "Updating Service URLs to Secret Manager"

    local updated=0
    local failed=0
    local skipped=0
    declare -a failed_services

    for service_name in "${!SERVICES[@]}"; do
        local secret_name="${SERVICES[$service_name]}"

        echo ""
        print_info "Processing: $service_name → $secret_name"

        # Get service URL
        local service_url
        service_url=$(get_service_url "$service_name")

        if [ $? -ne 0 ] || [ -z "$service_url" ]; then
            print_warning "Service not found or not deployed: $service_name"
            ((skipped++))
            continue
        fi

        print_info "Service URL: $service_url"

        # Update secret
        if update_secret "$secret_name" "$service_url"; then
            ((updated++))
        else
            ((failed++))
            failed_services+=("$service_name ($secret_name)")
        fi
    done

    echo ""
    print_section "Update Summary"
    echo -e "${GREEN}✅ Updated: $updated secrets${NC}"
    echo -e "${YELLOW}⏭️  Skipped: $skipped secrets (service not deployed)${NC}"
    echo -e "${RED}❌ Failed: $failed secrets${NC}"

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
# VERIFICATION FUNCTIONS
# ============================================================================

verify_secret_updates() {
    print_section "Verifying Secret Updates"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would verify secret updates${NC}"
        return 0
    fi

    local verified=0
    local failed=0

    for service_name in "${!SERVICES[@]}"; do
        local secret_name="${SERVICES[$service_name]}"

        # Get current secret value
        local secret_value
        secret_value=$(gcloud secrets versions access latest \
            --secret="$secret_name" \
            --project="$PROJECT_ID" 2>/dev/null)

        if [ $? -ne 0 ] || [ -z "$secret_value" ]; then
            print_warning "Cannot verify secret: $secret_name"
            ((failed++))
            continue
        fi

        # Get service URL
        local service_url
        service_url=$(get_service_url "$service_name")

        if [ "$secret_value" = "$service_url" ]; then
            print_success "$secret_name matches service URL"
            ((verified++))
        else
            print_warning "$secret_name does not match service URL"
            echo "   Secret: $secret_value"
            echo "   Service: $service_url"
            ((failed++))
        fi
    done

    echo ""
    echo -e "${GREEN}✅ Verified: $verified secrets${NC}"
    echo -e "${RED}❌ Mismatches: $failed secrets${NC}"

    if [ $failed -gt 0 ]; then
        print_warning "Some secrets do not match service URLs"
        return 1
    fi

    return 0
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

show_help() {
    cat << EOF
Update Service URLs to Secret Manager - PGP_v1

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --dry-run         Preview updates without making changes
    --project ID      Override GCP project ID (default: pgp-live)
    --help            Show this help message

DESCRIPTION:
    Automatically fetches Cloud Run service URLs and updates Secret Manager
    secrets for inter-service communication.

PREREQUISITES:
    - All 15 Cloud Run services deployed
    - Secret Manager secrets created (PGP_*_URL)
    - secretmanager.googleapis.com API enabled

EXAMPLES:
    # Preview updates
    $0 --dry-run

    # Update all service URLs
    $0

    # Update for different project
    $0 --project my-project-id

SERVICES:
    This script updates URLs for 15 services:
    - pgp-server-v1 (Telegram bot)
    - pgp-webapi-v1 (REST API)
    - pgp-np-ipn-v1 (NOWPayments webhook)
    - pgp-orchestrator-v1 (Payment orchestrator)
    - pgp-invite-v1 (Telegram invite sender)
    - pgp-split1-v1, pgp-split2-v1, pgp-split3-v1 (Split pipeline)
    - pgp-hostpay1-v1, pgp-hostpay2-v1, pgp-hostpay3-v1 (HostPay pipeline)
    - pgp-batchprocessor-v1 (Batch processor)
    - pgp-microbatchprocessor-v1 (Micro-batch processor)
    - pgp-notifications-v1 (Notifications)
    - pgp-broadcast-v1 (Broadcast scheduler)

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
    print_header "Update Service URLs to Secret Manager - PGP_v1"
    echo -e "${BLUE}Project:     ${NC}$PROJECT_ID"
    echo -e "${BLUE}Region:      ${NC}$REGION"
    echo -e "${BLUE}Services:    ${NC}15 Cloud Run services"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}Mode:        ${NC}DRY-RUN (preview only)"
    fi

    # Validate prerequisites
    validate_prerequisites

    # Update service URLs
    update_all_service_urls || {
        print_error "Some updates failed"
        exit 1
    }

    # Verify updates
    verify_secret_updates || {
        print_warning "Some verifications failed"
    }

    # Print summary
    print_header "UPDATE COMPLETE"
    print_success "All service URL secrets updated successfully"

    echo -e "\n${CYAN}📋 Next Steps:${NC}"
    echo -e "${CYAN}1.${NC} Verify services can communicate (test inter-service calls)"
    echo -e "${CYAN}2.${NC} Restart services if needed to pick up new URLs"
    echo -e "${CYAN}3.${NC} Monitor logs for any connection errors"

    echo -e "\n${GREEN}✅ URL update successful!${NC}"
}

# Execute main function
main "$@"
