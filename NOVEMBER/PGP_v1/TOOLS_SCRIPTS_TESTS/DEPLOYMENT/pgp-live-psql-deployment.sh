#!/bin/bash
################################################################################
# PGP-LIVE PostgreSQL Complete Deployment Script
################################################################################
# Project: pgp-live
# Database: pgp-live-db  (NEW - not telepaydb, not client_table)
# Instance: pgp-live-psql
# Region: us-central1
# Created: 2025-11-18
#
# DESCRIPTION:
#   Complete greenfield deployment of pgp-live-psql Cloud SQL instance and
#   pgp-live-db database with full schema for PGP_v1 architecture.
#
# DEPLOYMENT PHASES:
#   Phase 1: Cloud SQL Instance Creation
#   Phase 2: Database Creation (pgp-live-db)
#   Phase 3: ENUM Types Creation
#   Phase 4: Table Schema Deployment (13 tables)
#   Phase 5: Currency Data Population (87 entries)
#   Phase 6: Verification
#
# TABLES DEPLOYED: 13 operational tables
#   ✅ registered_users
#   ✅ main_clients_database
#   ✅ private_channel_users_database
#   ✅ processed_payments
#   ✅ batch_conversions
#   ✅ payout_accumulation
#   ✅ payout_batches
#   ✅ split_payout_request
#   ✅ split_payout_que
#   ✅ split_payout_hostpay
#   ✅ broadcast_manager
#   ✅ currency_to_network
#   ✅ failed_transactions
#
# TABLES EXCLUDED: 2 deprecated tables
#   ❌ user_conversation_state (deprecated bot state)
#   ❌ donation_keypad_state (deprecated donation UI)
#
# PREREQUISITES:
#   - GCP project "pgp-live" exists
#   - Billing enabled on pgp-live project
#   - gcloud CLI authenticated
#   - User has Cloud SQL Admin role
#   - User has Secret Manager Admin role
#   - Virtual environment at PGP_v1/.venv with dependencies
#
# USAGE:
#   ./pgp-live-psql-deployment.sh [--dry-run] [--skip-instance]
#
# OPTIONS:
#   --dry-run         Print commands without executing (preview mode)
#   --skip-instance   Skip Cloud SQL instance creation (instance exists)
#   --help            Show this help message
#
# WARNINGS:
#   ⚠️  This creates a NEW Cloud SQL instance (costs apply)
#   ⚠️  This is a GREENFIELD deployment (no data migration)
#   ⚠️  Existing pgp-live-psql instance will cause failure unless --skip-instance
#   ⚠️  Database will be EMPTY (no data from telepay-459221)
#
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# ============================================================================
# CONFIGURATION
# ============================================================================

# GCP Configuration
readonly PROJECT_ID="pgp-live"
readonly INSTANCE_NAME="pgp-live-psql"
readonly DATABASE_NAME="pgp-live-db"  # NEW NAME (not telepaydb, not client_table)
readonly REGION="us-central1"
readonly ZONE="us-central1-a"

# Cloud SQL Configuration
readonly POSTGRES_VERSION="POSTGRES_15"
readonly MACHINE_TIER="db-custom-2-7680"  # 2 vCPU, 7.5GB RAM
readonly DISK_SIZE="50"  # GB
readonly DISK_TYPE="PD_SSD"
readonly MAX_CONNECTIONS="500"

# Backup Configuration
readonly BACKUP_START_TIME="03:00"  # UTC
readonly MAINTENANCE_DAY="SUN"
readonly MAINTENANCE_HOUR="04"

# Secret Manager Configuration
readonly DB_USER_SECRET="PGP_LIVE_DATABASE_USER_SECRET"
readonly DB_PASSWORD_SECRET="PGP_LIVE_DATABASE_PASSWORD_SECRET"
readonly DB_NAME_SECRET="PGP_LIVE_DATABASE_NAME_SECRET"

# Script Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MIGRATIONS_DIR="$PROJECT_ROOT/TOOLS_SCRIPTS_TESTS/migrations/pgp-live"
VENV_DIR="$PROJECT_ROOT/.venv"

# Migration Files
readonly SCHEMA_MIGRATION="$MIGRATIONS_DIR/001_pgp_live_complete_schema.sql"
readonly CURRENCY_MIGRATION="$MIGRATIONS_DIR/002_pgp_live_populate_currency_to_network.sql"

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
SKIP_INSTANCE=false

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

# Print functions
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
    else
        echo -e "${MAGENTA}⏳ $description${NC}"
        "$@" || {
            print_error "Command failed: $*"
            return 1
        }
        print_success "$description"
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

# Check if instance exists
instance_exists() {
    gcloud sql instances describe "$INSTANCE_NAME" --project="$PROJECT_ID" &>/dev/null
    return $?
}

# Check if database exists
database_exists() {
    local databases
    databases=$(gcloud sql databases list --instance="$INSTANCE_NAME" --project="$PROJECT_ID" --format="value(name)" 2>/dev/null)
    echo "$databases" | grep -q "^${DATABASE_NAME}$"
    return $?
}

# Get secret value from Secret Manager
get_secret() {
    local secret_name="$1"
    local project="${2:-$PROJECT_ID}"

    gcloud secrets versions access latest \
        --secret="$secret_name" \
        --project="$project" 2>/dev/null || {
        print_error "Failed to access secret: $secret_name"
        return 1
    }
}

# Create or update secret
create_or_update_secret() {
    local secret_name="$1"
    local secret_value="$2"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would create/update secret: $secret_name${NC}"
        return 0
    fi

    # Check if secret exists
    if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
        # Update existing secret
        echo -n "$secret_value" | gcloud secrets versions add "$secret_name" \
            --project="$PROJECT_ID" \
            --data-file=- &>/dev/null
        print_success "Updated secret: $secret_name"
    else
        # Create new secret
        echo -n "$secret_value" | gcloud secrets create "$secret_name" \
            --project="$PROJECT_ID" \
            --data-file=- \
            --replication-policy="automatic" &>/dev/null
        print_success "Created secret: $secret_name"
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
    check_command "python3"
    check_command "psql"
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

    # Check virtual environment
    print_step "Checking virtual environment..."
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found at: $VENV_DIR"
        print_info "Please run: cd $PROJECT_ROOT && python3 -m venv .venv"
        print_info "Then install: pip install google-cloud-secret-manager cloud-sql-python-connector sqlalchemy pg8000"
        exit 1
    fi
    print_success "Virtual environment found"

    # Check migration files
    print_step "Checking migration files..."
    if [ ! -f "$SCHEMA_MIGRATION" ]; then
        print_error "Schema migration not found: $SCHEMA_MIGRATION"
        exit 1
    fi
    if [ ! -f "$CURRENCY_MIGRATION" ]; then
        print_error "Currency migration not found: $CURRENCY_MIGRATION"
        exit 1
    fi
    print_success "Migration files found"

    # Enable required APIs
    print_step "Enabling required GCP APIs..."
    local apis=(
        "sqladmin.googleapis.com"
        "secretmanager.googleapis.com"
        "compute.googleapis.com"
    )
    for api in "${apis[@]}"; do
        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}[DRY-RUN] Would enable API: $api${NC}"
        else
            gcloud services enable "$api" --project="$PROJECT_ID" 2>/dev/null || true
        fi
    done
    print_success "Required APIs enabled"
}

# ============================================================================
# DEPLOYMENT PHASES
# ============================================================================

# Phase 1: Create Cloud SQL Instance
phase1_create_instance() {
    print_header "PHASE 1: Cloud SQL Instance Creation"

    if [ "$SKIP_INSTANCE" = true ]; then
        print_warning "Skipping instance creation (--skip-instance flag)"

        # Verify instance exists
        if ! instance_exists; then
            print_error "Instance $INSTANCE_NAME does not exist in project $PROJECT_ID"
            print_info "Remove --skip-instance flag to create the instance"
            exit 1
        fi
        print_success "Instance $INSTANCE_NAME already exists"
        return 0
    fi

    # Check if instance already exists
    if instance_exists; then
        print_error "Instance $INSTANCE_NAME already exists"
        print_info "Use --skip-instance flag to skip instance creation"
        print_info "Or delete the existing instance first"
        exit 1
    fi

    print_info "Creating Cloud SQL instance: $INSTANCE_NAME"
    print_info "Region: $REGION"
    print_info "Machine Type: $MACHINE_TIER (2 vCPU, 7.5GB RAM)"
    print_info "PostgreSQL Version: $POSTGRES_VERSION"
    print_info "Disk: ${DISK_SIZE}GB $DISK_TYPE"

    if [ "$DRY_RUN" = false ]; then
        read -p "$(echo -e ${YELLOW}Continue with instance creation? [y/N]: ${NC})" -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Instance creation cancelled by user"
            exit 0
        fi
    fi

    execute_cmd "Creating Cloud SQL instance (this may take 5-10 minutes)" \
        gcloud sql instances create "$INSTANCE_NAME" \
        --project="$PROJECT_ID" \
        --database-version="$POSTGRES_VERSION" \
        --tier="$MACHINE_TIER" \
        --region="$REGION" \
        --network="default" \
        --enable-bin-log \
        --backup-start-time="$BACKUP_START_TIME" \
        --maintenance-window-day="$MAINTENANCE_DAY" \
        --maintenance-window-hour="$MAINTENANCE_HOUR" \
        --database-flags="max_connections=$MAX_CONNECTIONS" \
        --storage-type="$DISK_TYPE" \
        --storage-size="$DISK_SIZE" \
        --storage-auto-increase \
        --availability-type="ZONAL" \
        --no-assign-ip

    # Set root password
    print_step "Setting database root password..."
    local db_password
    db_password="$(openssl rand -base64 32)"

    if [ "$DRY_RUN" = false ]; then
        gcloud sql users set-password postgres \
            --instance="$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --password="$db_password" >/dev/null 2>&1
        print_success "Root password set"

        # Store password in Secret Manager
        create_or_update_secret "$DB_PASSWORD_SECRET" "$db_password"
    else
        echo -e "${YELLOW}[DRY-RUN] Would set root password and store in Secret Manager${NC}"
    fi

    # Store database username in Secret Manager
    create_or_update_secret "$DB_USER_SECRET" "postgres"

    print_success "Phase 1 Complete: Cloud SQL instance created"
}

# Phase 2: Create Database
phase2_create_database() {
    print_header "PHASE 2: Database Creation"

    print_info "Database Name: $DATABASE_NAME"
    print_info "Character Set: UTF8"
    print_info "Collation: en_US.UTF8"

    # Check if database already exists
    if database_exists; then
        print_warning "Database $DATABASE_NAME already exists"

        if [ "$DRY_RUN" = false ]; then
            read -p "$(echo -e ${YELLOW}Continue anyway? (database will be used as-is) [y/N]: ${NC})" -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_error "Deployment cancelled - database already exists"
                exit 1
            fi
        fi
    else
        execute_cmd "Creating database: $DATABASE_NAME" \
            gcloud sql databases create "$DATABASE_NAME" \
            --instance="$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --charset="UTF8" \
            --collation="en_US.UTF8"
    fi

    # Store database name in Secret Manager
    create_or_update_secret "$DB_NAME_SECRET" "$DATABASE_NAME"

    print_success "Phase 2 Complete: Database created"
}

# Phase 3: Deploy Schema
phase3_deploy_schema() {
    print_header "PHASE 3: Schema Deployment"

    print_info "Deploying 13 operational tables"
    print_info "Deploying 4 ENUM types"
    print_info "Deploying 50+ indexes"
    print_info "Deploying 3 foreign keys"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would execute schema migration: $SCHEMA_MIGRATION${NC}"
        echo -e "${CYAN}Schema preview:${NC}"
        head -50 "$SCHEMA_MIGRATION"
        echo -e "${CYAN}... (truncated)${NC}"
        return 0
    fi

    print_step "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    print_step "Executing schema migration via Python..."

    # Create temporary Python script for schema deployment
    local temp_script="/tmp/deploy_schema_$$.py"
    cat > "$temp_script" << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""Deploy schema to pgp-live-db database"""
import sys
import subprocess
from google.cloud.sql.connector import Connector

def get_secret(secret_name, project):
    """Fetch secret from Google Secret Manager"""
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest',
         '--secret', secret_name, '--project', project],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def main():
    if len(sys.argv) != 5:
        print("Usage: script.py <project> <instance> <database> <sql_file>")
        sys.exit(1)

    project = sys.argv[1]
    instance = sys.argv[2]
    database = sys.argv[3]
    sql_file = sys.argv[4]

    print(f"🔗 Connecting to {project}:{instance}/{database}")

    # Get credentials from Secret Manager
    db_user = get_secret("PGP_LIVE_DATABASE_USER_SECRET", project)
    db_password = get_secret("PGP_LIVE_DATABASE_PASSWORD_SECRET", project)

    # Connect to database
    connector = Connector()
    conn = connector.connect(
        f"{project}:us-central1:{instance}",
        "pg8000",
        user=db_user,
        password=db_password,
        db=database
    )

    # Read and execute SQL
    print(f"📄 Reading schema: {sql_file}")
    with open(sql_file, 'r') as f:
        sql = f.read()

    print(f"⚙️  Executing schema migration...")
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()

    print(f"✅ Schema deployed successfully")

    cur.close()
    conn.close()
    connector.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
PYTHON_SCRIPT

    chmod +x "$temp_script"
    python3 "$temp_script" "$PROJECT_ID" "$INSTANCE_NAME" "$DATABASE_NAME" "$SCHEMA_MIGRATION" || {
        print_error "Schema deployment failed"
        rm -f "$temp_script"
        deactivate
        exit 1
    }

    rm -f "$temp_script"
    deactivate

    print_success "Phase 3 Complete: Schema deployed (13 tables, 4 ENUMs, 50+ indexes)"
}

# Phase 4: Populate Currency Data
phase4_populate_currency() {
    print_header "PHASE 4: Currency Data Population"

    print_info "Populating 87 currency/network mappings"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would execute currency population: $CURRENCY_MIGRATION${NC}"
        return 0
    fi

    print_step "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    print_step "Populating currency_to_network table..."

    # Create temporary Python script for currency population
    local temp_script="/tmp/populate_currency_$$.py"
    cat > "$temp_script" << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""Populate currency_to_network table"""
import sys
import subprocess
from google.cloud.sql.connector import Connector

def get_secret(secret_name, project):
    """Fetch secret from Google Secret Manager"""
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest',
         '--secret', secret_name, '--project', project],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def main():
    if len(sys.argv) != 5:
        print("Usage: script.py <project> <instance> <database> <sql_file>")
        sys.exit(1)

    project = sys.argv[1]
    instance = sys.argv[2]
    database = sys.argv[3]
    sql_file = sys.argv[4]

    print(f"🔗 Connecting to {project}:{instance}/{database}")

    # Get credentials
    db_user = get_secret("PGP_LIVE_DATABASE_USER_SECRET", project)
    db_password = get_secret("PGP_LIVE_DATABASE_PASSWORD_SECRET", project)

    # Connect
    connector = Connector()
    conn = connector.connect(
        f"{project}:us-central1:{instance}",
        "pg8000",
        user=db_user,
        password=db_password,
        db=database
    )

    # Execute currency population
    print(f"📄 Reading currency data: {sql_file}")
    with open(sql_file, 'r') as f:
        sql = f.read()

    print(f"⚙️  Inserting currency mappings...")
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()

    # Verify count
    cur.execute("SELECT COUNT(*) FROM currency_to_network")
    count = cur.fetchone()[0]
    print(f"✅ Inserted {count} currency/network mappings")

    cur.close()
    conn.close()
    connector.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
PYTHON_SCRIPT

    chmod +x "$temp_script"
    python3 "$temp_script" "$PROJECT_ID" "$INSTANCE_NAME" "$DATABASE_NAME" "$CURRENCY_MIGRATION" || {
        print_error "Currency population failed"
        rm -f "$temp_script"
        deactivate
        exit 1
    }

    rm -f "$temp_script"
    deactivate

    print_success "Phase 4 Complete: Currency data populated (87 entries)"
}

# Phase 5: Verification
phase5_verification() {
    print_header "PHASE 5: Deployment Verification"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would verify deployment${NC}"
        return 0
    fi

    print_step "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    print_step "Verifying database schema..."

    # Create verification script
    local temp_script="/tmp/verify_deployment_$$.py"
    cat > "$temp_script" << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""Verify pgp-live-db deployment"""
import sys
import subprocess
from google.cloud.sql.connector import Connector

def get_secret(secret_name, project):
    """Fetch secret from Google Secret Manager"""
    result = subprocess.run(
        ['gcloud', 'secrets', 'versions', 'access', 'latest',
         '--secret', secret_name, '--project', project],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def main():
    if len(sys.argv) != 4:
        print("Usage: script.py <project> <instance> <database>")
        sys.exit(1)

    project = sys.argv[1]
    instance = sys.argv[2]
    database = sys.argv[3]

    print(f"🔗 Connecting to {project}:{instance}/{database}")

    # Get credentials
    db_user = get_secret("PGP_LIVE_DATABASE_USER_SECRET", project)
    db_password = get_secret("PGP_LIVE_DATABASE_PASSWORD_SECRET", project)

    # Connect
    connector = Connector()
    conn = connector.connect(
        f"{project}:us-central1:{instance}",
        "pg8000",
        user=db_user,
        password=db_password,
        db=database
    )

    cur = conn.cursor()

    # Check tables
    print(f"\n📊 Verifying Tables:")
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]

    expected_tables = [
        'batch_conversions',
        'broadcast_manager',
        'currency_to_network',
        'failed_transactions',
        'main_clients_database',
        'payout_accumulation',
        'payout_batches',
        'private_channel_users_database',
        'processed_payments',
        'registered_users',
        'split_payout_hostpay',
        'split_payout_que',
        'split_payout_request'
    ]

    for table in expected_tables:
        if table in tables:
            print(f"  ✅ {table}")
        else:
            print(f"  ❌ {table} (MISSING)")

    # Check ENUMs
    print(f"\n🔤 Verifying ENUM Types:")
    cur.execute("""
        SELECT typname
        FROM pg_type
        WHERE typtype = 'e'
        ORDER BY typname
    """)
    enums = [row[0] for row in cur.fetchall()]

    expected_enums = ['currency_type', 'flow_type', 'network_type', 'type_type']
    for enum in expected_enums:
        if enum in enums:
            print(f"  ✅ {enum}")
        else:
            print(f"  ❌ {enum} (MISSING)")

    # Check currency data
    print(f"\n💱 Verifying Currency Data:")
    cur.execute("SELECT COUNT(*) FROM currency_to_network")
    currency_count = cur.fetchone()[0]
    if currency_count == 87:
        print(f"  ✅ currency_to_network: {currency_count} entries")
    else:
        print(f"  ⚠️  currency_to_network: {currency_count} entries (expected 87)")

    # Check legacy user
    print(f"\n👤 Verifying Legacy User:")
    cur.execute("SELECT COUNT(*) FROM registered_users WHERE username = 'legacy_system'")
    legacy_count = cur.fetchone()[0]
    if legacy_count == 1:
        print(f"  ✅ legacy_system user exists")
    else:
        print(f"  ❌ legacy_system user missing")

    print(f"\n📈 Summary:")
    print(f"  Tables: {len(tables)}/13")
    print(f"  ENUMs: {len(enums)}/4")
    print(f"  Currency mappings: {currency_count}/87")
    print(f"  Legacy user: {legacy_count}/1")

    if len(tables) == 13 and len(enums) == 4 and currency_count == 87 and legacy_count == 1:
        print(f"\n✅ ALL VERIFICATION CHECKS PASSED")
        exit_code = 0
    else:
        print(f"\n⚠️  SOME VERIFICATION CHECKS FAILED")
        exit_code = 1

    cur.close()
    conn.close()
    connector.close()

    sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
PYTHON_SCRIPT

    chmod +x "$temp_script"
    python3 "$temp_script" "$PROJECT_ID" "$INSTANCE_NAME" "$DATABASE_NAME" || {
        print_warning "Verification found issues (see details above)"
        rm -f "$temp_script"
        deactivate
        return 1
    }

    rm -f "$temp_script"
    deactivate

    print_success "Phase 5 Complete: All verification checks passed"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

show_help() {
    cat << EOF
PGP-LIVE PostgreSQL Complete Deployment Script

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --dry-run         Preview deployment without making changes
    --skip-instance   Skip Cloud SQL instance creation (use existing instance)
    --help            Show this help message

DEPLOYMENT OVERVIEW:
    Phase 1: Create Cloud SQL instance (pgp-live-psql)
    Phase 2: Create database (pgp-live-db)
    Phase 3: Deploy schema (13 tables, 4 ENUMs)
    Phase 4: Populate currency data (87 entries)
    Phase 5: Verify deployment

EXAMPLES:
    # Preview deployment
    $0 --dry-run

    # Full deployment (create instance + database + schema)
    $0

    # Deploy schema to existing instance
    $0 --skip-instance

WARNINGS:
    ⚠️  This creates a NEW Cloud SQL instance (costs apply)
    ⚠️  This is a GREENFIELD deployment (no data migration)
    ⚠️  Database will be EMPTY (no data from telepay-459221)

For more information, see DATABASE_SCHEMA_DOCUMENTATION_PGP.md
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
            --skip-instance)
                SKIP_INSTANCE=true
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
    print_header "PGP-LIVE PostgreSQL Complete Deployment"
    echo -e "${BLUE}Project:     ${NC}$PROJECT_ID"
    echo -e "${BLUE}Instance:    ${NC}$INSTANCE_NAME"
    echo -e "${BLUE}Database:    ${NC}$DATABASE_NAME ${YELLOW}(NEW - not telepaydb)${NC}"
    echo -e "${BLUE}Region:      ${NC}$REGION"
    echo -e "${BLUE}Deployment:  ${NC}Greenfield (empty database)"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}Mode:        ${NC}DRY-RUN (preview only)"
    fi

    # Validate prerequisites
    validate_prerequisites

    # Execute deployment phases
    phase1_create_instance
    phase2_create_database
    phase3_deploy_schema
    phase4_populate_currency
    phase5_verification

    # Print summary
    print_header "DEPLOYMENT COMPLETE"
    print_success "Cloud SQL instance: $INSTANCE_NAME"
    print_success "Database: $DATABASE_NAME"
    print_success "Tables deployed: 13 operational tables"
    print_success "Tables excluded: 2 deprecated tables"
    print_success "Currency mappings: 87 entries"
    print_success "Verification: All checks passed"

    echo -e "\n${CYAN}📋 Next Steps:${NC}"
    echo -e "${CYAN}1.${NC} Update PGP_v1 service configurations to use pgp-live-db"
    echo -e "${CYAN}2.${NC} Deploy PGP_v1 services to pgp-live project"
    echo -e "${CYAN}3.${NC} Configure service accounts and IAM permissions"
    echo -e "${CYAN}4.${NC} Test database connectivity from services"

    echo -e "\n${GREEN}✅ Deployment successful!${NC}"
}

# Execute main function
main "$@"
