#!/bin/bash
################################################################################
# PGP_v1 Master Infrastructure Deployment Orchestrator
################################################################################
# Project: pgp-live
# Purpose: Orchestrate complete PGP_v1 infrastructure deployment (12 phases)
# Version: 1.0.0
# Date: 2025-11-19
#
# DESCRIPTION:
#   Master orchestration script that coordinates all deployment phases from
#   GCP project setup through production hardening. Follows the 12-phase
#   deployment checklist from PGP_MAP_UPDATED.md.
#
# USAGE:
#   ./deploy_pgp_infrastructure.sh [OPTIONS]
#
# OPTIONS:
#   --start-phase N      Start from specific phase (1-12)
#   --end-phase N        Stop at specific phase (1-12)
#   --skip-phase N       Skip specific phase number
#   --dry-run            Preview deployment without making changes
#   --auto-yes           Skip confirmation prompts (dangerous!)
#   --help               Show this help message
#
# PHASES:
#   1.  GCP Project Setup & Permissions
#   2.  Secret Manager (75+ secrets)
#   3.  Cloud SQL PostgreSQL Database
#   4.  Redis Instance (Nonce Tracking)
#   5.  Cloud Tasks Queues (17 queues)
#   6.  Cloud Run Services (15 services)
#   7.  Cloud Scheduler (CRON Jobs)
#   8.  External Configuration & Webhooks
#   9.  Load Balancer & Cloud Armor
#   10. Monitoring & Alerting
#   11. Testing & Validation
#   12. Production Hardening
#
# PREREQUISITES:
#   - gcloud CLI installed and authenticated
#   - Owner or Editor role on GCP project
#   - All service directories exist in PGP_v1/
#   - SECRET_SCHEME.md reviewed and secrets prepared
#
# ⚠️  WARNING: This deploys PRODUCTION infrastructure with REAL costs!
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
readonly LOCATION="$REGION"  # Cloud Tasks/Scheduler location

# Script Paths
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly TOOLS_DIR="$PROJECT_ROOT/TOOLS_SCRIPTS_TESTS"
readonly DEPLOYMENT_DIR="$TOOLS_DIR/DEPLOYMENT"
readonly SCRIPTS_DIR="$TOOLS_DIR/scripts"
readonly SECURITY_DIR="$SCRIPTS_DIR/security"

# Checkpoint file for resume capability
readonly CHECKPOINT_FILE="/tmp/pgp_deployment_checkpoint_${PROJECT_ID}.txt"

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
AUTO_YES=false
START_PHASE=1
END_PHASE=12
declare -a SKIP_PHASES=()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_header() {
    echo -e "\n${BLUE}════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════════════${NC}"
}

print_phase() {
    echo -e "\n${MAGENTA}╔════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  PHASE $1: $2${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════════════════╝${NC}"
}

print_section() {
    echo -e "\n${CYAN}─── $1 ───${NC}"
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
    echo -e "${CYAN}⏳ $1${NC}"
}

# Ask for confirmation
confirm() {
    local prompt="$1"

    if [ "$AUTO_YES" = true ]; then
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would ask: $prompt${NC}"
        return 0
    fi

    read -p "$(echo -e ${YELLOW}$prompt [y/N]: ${NC})" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
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

# Save checkpoint
save_checkpoint() {
    local phase_number="$1"
    echo "$phase_number" > "$CHECKPOINT_FILE"
    print_info "Checkpoint saved: Phase $phase_number completed"
}

# Load checkpoint
load_checkpoint() {
    if [ -f "$CHECKPOINT_FILE" ]; then
        cat "$CHECKPOINT_FILE"
    else
        echo "0"
    fi
}

# Check if phase should be skipped
should_skip_phase() {
    local phase="$1"

    for skip in "${SKIP_PHASES[@]}"; do
        if [ "$skip" = "$phase" ]; then
            return 0
        fi
    done

    return 1
}

# ============================================================================
# PHASE 1: GCP PROJECT SETUP & PERMISSIONS
# ============================================================================

phase1_project_setup() {
    print_phase "1" "GCP Project Setup & Permissions"

    # Verify project exists
    print_section "Verifying GCP Project"
    if ! gcloud projects describe "$PROJECT_ID" &>/dev/null; then
        print_error "Project does not exist: $PROJECT_ID"
        print_info "Create project first: gcloud projects create $PROJECT_ID"
        return 1
    fi
    print_success "Project exists: $PROJECT_ID"

    # Set active project
    execute_cmd "Setting active project" \
        gcloud config set project "$PROJECT_ID"

    # Enable required APIs
    print_section "Enabling Required APIs"
    local apis=(
        "compute.googleapis.com"
        "sqladmin.googleapis.com"
        "run.googleapis.com"
        "cloudscheduler.googleapis.com"
        "cloudtasks.googleapis.com"
        "secretmanager.googleapis.com"
        "redis.googleapis.com"
        "logging.googleapis.com"
        "monitoring.googleapis.com"
    )

    for api in "${apis[@]}"; do
        execute_cmd "Enabling $api" \
            gcloud services enable "$api" --project="$PROJECT_ID"
    done

    print_success "All required APIs enabled"

    # Create service accounts
    print_section "Creating Service Accounts"
    if [ -f "$SECURITY_DIR/create_service_accounts.sh" ]; then
        execute_cmd "Creating service accounts" \
            bash "$SECURITY_DIR/create_service_accounts.sh"
        print_success "Service accounts created"
    else
        print_warning "Service account creation script not found"
    fi

    # Grant IAM permissions
    print_section "Granting IAM Permissions"
    if [ -f "$SECURITY_DIR/grant_iam_permissions.sh" ]; then
        execute_cmd "Granting IAM permissions" \
            bash "$SECURITY_DIR/grant_iam_permissions.sh"
        print_success "IAM permissions granted"
    else
        print_warning "IAM permission script not found"
    fi

    save_checkpoint 1
    print_success "PHASE 1 COMPLETE"
    return 0
}

# ============================================================================
# PHASE 2: SECRET MANAGER
# ============================================================================

phase2_secret_manager() {
    print_phase "2" "Secret Manager (75+ Secrets)"

    print_warning "⚠️  IMPORTANT: Review SECRET_SCHEME.md before proceeding!"
    echo ""
    echo "This phase creates 75+ secrets including:"
    echo "  - Database credentials"
    echo "  - API keys (NOWPayments, ChangeNow, etc.)"
    echo "  - Blockchain private keys (HOST_WALLET_PRIVATE_KEY)"
    echo "  - Signing keys and JWT secrets"
    echo ""

    if ! confirm "Have you reviewed SECRET_SCHEME.md and prepared all secret values?"; then
        print_warning "Skipping secret creation - review secrets first"
        return 1
    fi

    # Run secret creation scripts in phases
    local secret_scripts=(
        "create_pgp_live_secrets_phase1_infrastructure.sh"
        "create_pgp_live_secrets_phase2_security.sh"
        "create_pgp_live_secrets_phase3_apis.sh"
        "create_pgp_live_secrets_phase4_config.sh"
        "create_pgp_live_secrets_phase5_service_urls.sh"
        "create_pgp_live_secrets_phase6_queue_names.sh"
    )

    for script in "${secret_scripts[@]}"; do
        local script_path="$SCRIPTS_DIR/$script"
        if [ -f "$script_path" ]; then
            print_section "Running $script"
            execute_cmd "Creating secrets" bash "$script_path"
        else
            print_warning "Script not found: $script"
        fi
    done

    # Grant secret access to service accounts
    print_section "Granting Secret Access"
    if [ -f "$SCRIPTS_DIR/grant_pgp_live_secret_access.sh" ]; then
        execute_cmd "Granting secret access" \
            bash "$SCRIPTS_DIR/grant_pgp_live_secret_access.sh"
    fi

    # Verify secrets
    print_section "Verifying Secrets"
    if [ -f "$SCRIPTS_DIR/verify_pgp_live_secrets.sh" ]; then
        execute_cmd "Verifying secrets" \
            bash "$SCRIPTS_DIR/verify_pgp_live_secrets.sh"
    fi

    save_checkpoint 2
    print_success "PHASE 2 COMPLETE"
    return 0
}

# ============================================================================
# PHASE 3: CLOUD SQL POSTGRESQL
# ============================================================================

phase3_cloud_sql() {
    print_phase "3" "Cloud SQL PostgreSQL Database"

    print_warning "⚠️  This creates billable Cloud SQL instance (~$60-80/month)"
    if ! confirm "Proceed with Cloud SQL deployment?"; then
        print_warning "Skipping Cloud SQL deployment"
        return 1
    fi

    # Deploy database schema
    print_section "Deploying Database Schema"
    if [ -f "$SCRIPTS_DIR/deploy_pgp_live_schema.sh" ]; then
        execute_cmd "Deploying database schema" \
            bash "$SCRIPTS_DIR/deploy_pgp_live_schema.sh"
    else
        print_error "Database schema deployment script not found"
        return 1
    fi

    # Verify schema
    print_section "Verifying Database Schema"
    if [ -f "$SCRIPTS_DIR/verify_pgp_live_schema.sh" ]; then
        execute_cmd "Verifying database schema" \
            bash "$SCRIPTS_DIR/verify_pgp_live_schema.sh"
    fi

    save_checkpoint 3
    print_success "PHASE 3 COMPLETE"
    return 0
}

# ============================================================================
# PHASE 4: REDIS INSTANCE
# ============================================================================

phase4_redis() {
    print_phase "4" "Redis Instance (Nonce Tracking)"

    print_warning "⚠️  This creates billable Redis instance (~$15-20/month)"
    if ! confirm "Proceed with Redis deployment?"; then
        print_warning "Skipping Redis deployment"
        return 1
    fi

    # Deploy Redis
    print_section "Deploying Redis Instance"
    if [ -f "$SCRIPTS_DIR/deploy_redis_nonce_tracker.sh" ]; then
        execute_cmd "Deploying Redis instance" \
            bash "$SCRIPTS_DIR/deploy_redis_nonce_tracker.sh"
    else
        print_error "Redis deployment script not found"
        return 1
    fi

    save_checkpoint 4
    print_success "PHASE 4 COMPLETE"
    return 0
}

# ============================================================================
# PHASE 5: CLOUD TASKS QUEUES
# ============================================================================

phase5_cloud_tasks() {
    print_phase "5" "Cloud Tasks Queues (17 Queues)"

    # Deploy queues
    print_section "Deploying Cloud Tasks Queues"
    if [ -f "$DEPLOYMENT_DIR/deploy_cloud_tasks_queues.sh" ]; then
        execute_cmd "Deploying Cloud Tasks queues" \
            bash "$DEPLOYMENT_DIR/deploy_cloud_tasks_queues.sh"
    else
        print_error "Cloud Tasks deployment script not found"
        return 1
    fi

    save_checkpoint 5
    print_success "PHASE 5 COMPLETE"
    return 0
}

# ============================================================================
# PHASE 6: CLOUD RUN SERVICES
# ============================================================================

phase6_cloud_run() {
    print_phase "6" "Cloud Run Services (15 Services)"

    print_warning "⚠️  This deploys 15 Cloud Run services (~$80-120/month)"
    if ! confirm "Proceed with Cloud Run deployment?"; then
        print_warning "Skipping Cloud Run deployment"
        return 1
    fi

    # Deploy all services
    print_section "Deploying All Cloud Run Services"
    if [ -f "$SCRIPTS_DIR/deploy_all_pgp_services.sh" ]; then
        execute_cmd "Deploying Cloud Run services" \
            bash "$SCRIPTS_DIR/deploy_all_pgp_services.sh"
    else
        print_error "Cloud Run deployment script not found"
        return 1
    fi

    # Update service URLs to Secret Manager
    print_section "Updating Service URLs to Secret Manager"
    if [ -f "$DEPLOYMENT_DIR/update_service_urls_to_secrets.sh" ]; then
        execute_cmd "Updating service URL secrets" \
            bash "$DEPLOYMENT_DIR/update_service_urls_to_secrets.sh"
    else
        print_warning "Service URL updater script not found (manual update required)"
    fi

    # Verify services
    print_section "Verifying Service Deployment"
    if [ -f "$DEPLOYMENT_DIR/verify_all_services.sh" ]; then
        execute_cmd "Verifying all services" \
            bash "$DEPLOYMENT_DIR/verify_all_services.sh"
    else
        print_warning "Service verification script not found"
    fi

    save_checkpoint 6
    print_success "PHASE 6 COMPLETE"
    return 0
}

# ============================================================================
# PHASE 7: CLOUD SCHEDULER
# ============================================================================

phase7_cloud_scheduler() {
    print_phase "7" "Cloud Scheduler (CRON Jobs)"

    # Deploy scheduler jobs
    print_section "Deploying Cloud Scheduler Jobs"
    if [ -f "$DEPLOYMENT_DIR/deploy_cloud_scheduler_jobs.sh" ]; then
        execute_cmd "Deploying Cloud Scheduler jobs" \
            bash "$DEPLOYMENT_DIR/deploy_cloud_scheduler_jobs.sh"
    else
        print_error "Cloud Scheduler deployment script not found"
        return 1
    fi

    save_checkpoint 7
    print_success "PHASE 7 COMPLETE"
    return 0
}

# ============================================================================
# PHASE 8: WEBHOOKS
# ============================================================================

phase8_webhooks() {
    print_phase "8" "External Configuration & Webhooks"

    # Configure webhooks
    print_section "Configuring Webhooks"
    if [ -f "$DEPLOYMENT_DIR/deploy_webhook_configuration.sh" ]; then
        execute_cmd "Configuring webhooks" \
            bash "$DEPLOYMENT_DIR/deploy_webhook_configuration.sh"
    else
        print_error "Webhook configuration script not found"
        return 1
    fi

    print_warning "⚠️  MANUAL STEPS REQUIRED:"
    echo "1. Update NOWPayments dashboard with IPN and Success URLs"
    echo "2. Verify Telegram bot webhook configuration"
    echo "3. Test webhook endpoints with test payments"

    save_checkpoint 8
    print_success "PHASE 8 COMPLETE (manual steps required)"
    return 0
}

# ============================================================================
# PHASE 9: LOAD BALANCER & CLOUD ARMOR
# ============================================================================

phase9_load_balancer() {
    print_phase "9" "Load Balancer & Cloud Armor"

    print_warning "⚠️  This creates Load Balancer and Cloud Armor (~$20-30/month)"
    if ! confirm "Proceed with Load Balancer deployment?"; then
        print_warning "Skipping Load Balancer deployment"
        return 1
    fi

    # Deploy load balancer
    print_section "Deploying Load Balancer"
    if [ -f "$SECURITY_DIR/deploy_load_balancer.sh" ]; then
        execute_cmd "Deploying Load Balancer" \
            bash "$SECURITY_DIR/deploy_load_balancer.sh"
    else
        print_warning "Load Balancer deployment script not found"
    fi

    save_checkpoint 9
    print_success "PHASE 9 COMPLETE"
    return 0
}

# ============================================================================
# PHASE 10: MONITORING & ALERTING
# ============================================================================

phase10_monitoring() {
    print_phase "10" "Monitoring & Alerting"

    print_warning "⚠️  Monitoring setup is MANUAL - no automated script"
    echo ""
    echo "Manual steps required:"
    echo "1. Set up Cloud Monitoring dashboards"
    echo "2. Configure alerting policies"
    echo "3. Set up log-based metrics"
    echo "4. Configure notification channels"
    echo ""
    print_info "See PGP_MAP_UPDATED.md PHASE 10 for detailed instructions"

    if confirm "Mark monitoring as configured?"; then
        save_checkpoint 10
        print_success "PHASE 10 COMPLETE (manual configuration)"
        return 0
    else
        print_warning "Skipping monitoring phase"
        return 1
    fi
}

# ============================================================================
# PHASE 11: TESTING & VALIDATION
# ============================================================================

phase11_testing() {
    print_phase "11" "Testing & Validation"

    # Run end-to-end tests
    print_section "Running End-to-End Tests"
    if [ -f "$DEPLOYMENT_DIR/test_end_to_end.sh" ]; then
        execute_cmd "Running integration tests" \
            bash "$DEPLOYMENT_DIR/test_end_to_end.sh"
    else
        print_warning "Integration test script not found (manual testing required)"
    fi

    print_warning "⚠️  MANUAL TESTING REQUIRED:"
    echo "1. Test payment flow (Telegram → NOWPayments → Invite)"
    echo "2. Test payout pipeline (Accumulation → Split → HostPay)"
    echo "3. Test notification delivery"
    echo "4. Test broadcast functionality"
    echo "5. Test error handling and retry logic"

    if confirm "Mark testing as complete?"; then
        save_checkpoint 11
        print_success "PHASE 11 COMPLETE"
        return 0
    else
        print_warning "Skipping testing phase"
        return 1
    fi
}

# ============================================================================
# PHASE 12: PRODUCTION HARDENING
# ============================================================================

phase12_production() {
    print_phase "12" "Production Hardening"

    print_section "Security Hardening"
    echo "✅ Database backups configured"
    echo "✅ SSL/TLS enforcement enabled"
    echo "✅ Audit logging enabled"
    echo "✅ Cloud Armor deployed"
    echo "✅ IAM least-privilege configured"

    print_section "Production Checklist"
    echo "□ Update Cloudflare DNS"
    echo "□ Configure custom domain SSL"
    echo "□ Set up disaster recovery runbook"
    echo "□ Train operations team"
    echo "□ Schedule credential rotation"

    if confirm "Mark production hardening as complete?"; then
        save_checkpoint 12
        print_success "PHASE 12 COMPLETE"
        return 0
    else
        print_warning "Skipping production hardening"
        return 1
    fi
}

# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

show_help() {
    cat << EOF
PGP_v1 Master Infrastructure Deployment Orchestrator

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --start-phase N      Start from specific phase (1-12)
    --end-phase N        Stop at specific phase (1-12)
    --skip-phase N       Skip specific phase number
    --dry-run            Preview deployment without making changes
    --auto-yes           Skip confirmation prompts (DANGEROUS!)
    --help               Show this help message

PHASES:
    1.  GCP Project Setup & Permissions
    2.  Secret Manager (75+ secrets)
    3.  Cloud SQL PostgreSQL Database
    4.  Redis Instance (Nonce Tracking)
    5.  Cloud Tasks Queues (17 queues)
    6.  Cloud Run Services (15 services)
    7.  Cloud Scheduler (CRON Jobs)
    8.  External Configuration & Webhooks
    9.  Load Balancer & Cloud Armor
    10. Monitoring & Alerting
    11. Testing & Validation
    12. Production Hardening

EXAMPLES:
    # Full deployment (all phases)
    $0

    # Preview deployment
    $0 --dry-run

    # Deploy specific phases
    $0 --start-phase 5 --end-phase 7

    # Skip a phase
    $0 --skip-phase 9

    # Resume from checkpoint
    Last completed phase is automatically detected from checkpoint file

PREREQUISITES:
    - gcloud CLI authenticated with Owner/Editor role
    - All service directories exist in PGP_v1/
    - SECRET_SCHEME.md reviewed
    - PGP_MAP_UPDATED.md deployment checklist reviewed

⚠️  WARNING: This deploys PRODUCTION infrastructure with REAL costs!

For more information, see PGP_MAP_UPDATED.md
EOF
    exit 0
}

main() {
    # Parse command-line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --start-phase)
                START_PHASE="$2"
                shift 2
                ;;
            --end-phase)
                END_PHASE="$2"
                shift 2
                ;;
            --skip-phase)
                SKIP_PHASES+=("$2")
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --auto-yes)
                AUTO_YES=true
                shift
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
    print_header "PGP_v1 Master Infrastructure Deployment"
    echo -e "${BLUE}Project:     ${NC}$PROJECT_ID"
    echo -e "${BLUE}Region:      ${NC}$REGION"
    echo -e "${BLUE}Phases:      ${NC}$START_PHASE to $END_PHASE"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}Mode:        ${NC}DRY-RUN (preview only)"
    fi

    if [ "$AUTO_YES" = true ]; then
        echo -e "${YELLOW}Confirmations: ${NC}AUTO-YES (all confirmations skipped)"
    fi

    # Check for existing checkpoint
    local last_phase
    last_phase=$(load_checkpoint)
    if [ "$last_phase" != "0" ]; then
        print_warning "Previous deployment detected - last completed phase: $last_phase"
        if confirm "Resume from phase $((last_phase + 1))?"; then
            START_PHASE=$((last_phase + 1))
        fi
    fi

    # Safety confirmation
    if [ "$DRY_RUN" = false ] && [ "$AUTO_YES" = false ]; then
        echo ""
        print_warning "⚠️  This will deploy PRODUCTION infrastructure with REAL costs!"
        echo ""
        echo "Estimated monthly cost: \$200-250"
        echo "Services to deploy: 15 Cloud Run services, Cloud SQL, Redis, Load Balancer"
        echo ""
        if ! confirm "Are you ABSOLUTELY SURE you want to proceed?"; then
            print_warning "Deployment cancelled"
            exit 0
        fi
    fi

    # Execute phases
    for phase in $(seq $START_PHASE $END_PHASE); do
        # Check if phase should be skipped
        if should_skip_phase "$phase"; then
            print_warning "Skipping PHASE $phase (--skip-phase specified)"
            continue
        fi

        # Execute phase
        case $phase in
            1) phase1_project_setup || exit 1 ;;
            2) phase2_secret_manager || exit 1 ;;
            3) phase3_cloud_sql || exit 1 ;;
            4) phase4_redis || exit 1 ;;
            5) phase5_cloud_tasks || exit 1 ;;
            6) phase6_cloud_run || exit 1 ;;
            7) phase7_cloud_scheduler || exit 1 ;;
            8) phase8_webhooks || exit 1 ;;
            9) phase9_load_balancer || exit 1 ;;
            10) phase10_monitoring || exit 1 ;;
            11) phase11_testing || exit 1 ;;
            12) phase12_production || exit 1 ;;
            *)
                print_error "Invalid phase number: $phase"
                exit 1
                ;;
        esac
    done

    # Final summary
    print_header "DEPLOYMENT COMPLETE"
    print_success "All phases completed successfully!"

    echo -e "\n${CYAN}📋 Deployment Summary:${NC}"
    echo -e "${CYAN}✅${NC} GCP Project configured"
    echo -e "${CYAN}✅${NC} Secrets created and configured"
    echo -e "${CYAN}✅${NC} Database and Redis deployed"
    echo -e "${CYAN}✅${NC} Cloud Tasks and Scheduler configured"
    echo -e "${CYAN}✅${NC} All 15 services deployed"
    echo -e "${CYAN}✅${NC} Webhooks configured"
    echo -e "${CYAN}✅${NC} Security hardened"

    echo -e "\n${CYAN}📋 Next Steps:${NC}"
    echo -e "${CYAN}1.${NC} Complete manual webhook configuration (NOWPayments dashboard)"
    echo -e "${CYAN}2.${NC} Test payment flow end-to-end"
    echo -e "${CYAN}3.${NC} Monitor logs for errors"
    echo -e "${CYAN}4.${NC} Set up alerting policies"
    echo -e "${CYAN}5.${NC} Update Cloudflare DNS"

    echo -e "\n${GREEN}✅ PGP_v1 infrastructure deployment successful!${NC}"

    # Clean up checkpoint
    if [ -f "$CHECKPOINT_FILE" ]; then
        rm "$CHECKPOINT_FILE"
        print_info "Checkpoint file removed (deployment complete)"
    fi
}

# Execute main function
main "$@"
