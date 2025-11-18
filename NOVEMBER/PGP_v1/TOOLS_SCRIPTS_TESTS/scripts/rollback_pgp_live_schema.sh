#!/bin/bash
################################################################################
# PayGatePrime PGP-LIVE Schema Rollback Script
################################################################################
# Project: pgp-live
# Database: telepaydb
# Instance: pgp-live:us-central1:pgp-telepaypsql
#
# ⚠️⚠️⚠️ WARNING: THIS WILL DELETE ALL DATA ⚠️⚠️⚠️
#
# This script rolls back the pgp-live database schema.
#
# Usage:
#   ./rollback_pgp_live_schema.sh
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TOOLS_DIR="$PROJECT_ROOT/TOOLS_SCRIPTS_TESTS/tools"
VENV_DIR="$PROJECT_ROOT/.venv"

echo -e "${RED}============================================${NC}"
echo -e "${RED}🚨 PGP-LIVE Schema Rollback${NC}"
echo -e "${RED}⚠️  THIS WILL DELETE ALL DATA ⚠️${NC}"
echo -e "${RED}============================================${NC}"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ Error: Virtual environment not found at $VENV_DIR${NC}"
    echo -e "${YELLOW}   Please run: python3 -m venv .venv${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "\n${BLUE}⏳ Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✅ Virtual environment activated${NC}"

# Verify Python script exists
ROLLBACK_SCRIPT="$TOOLS_DIR/rollback_pgp_live_schema.py"
if [ ! -f "$ROLLBACK_SCRIPT" ]; then
    echo -e "${RED}❌ Error: Rollback script not found at $ROLLBACK_SCRIPT${NC}"
    exit 1
fi

# Set GCP project
echo -e "\n${BLUE}⏳ Setting GCP project to pgp-live...${NC}"
gcloud config set project pgp-live 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Warning: Could not set GCP project (continuing anyway)${NC}"
}

# Execute rollback script
echo -e "\n${BLUE}⏳ Executing rollback script...${NC}"
echo -e "${RED}⚠️  You will be asked for confirmation multiple times${NC}"
python3 "$ROLLBACK_SCRIPT"

ROLLBACK_EXIT_CODE=$?

# Deactivate virtual environment
deactivate

# Print final status
echo -e "\n${BLUE}============================================${NC}"
if [ $ROLLBACK_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Rollback completed successfully${NC}"
    echo -e "${YELLOW}⚠️  Database is now empty${NC}"
else
    echo -e "${RED}❌ Rollback script failed or was cancelled${NC}"
fi
echo -e "${BLUE}============================================${NC}"

exit $ROLLBACK_EXIT_CODE
