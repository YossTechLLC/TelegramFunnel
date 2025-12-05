#!/bin/bash
################################################################################
# PayGatePrime PGP-LIVE Schema Verification Script
################################################################################
# Project: pgp-live
# Database: telepaydb
# Instance: pgp-live:us-central1:pgp-telepaypsql
#
# This script verifies the pgp-live database schema deployment.
#
# Usage:
#   ./verify_pgp_live_schema.sh
#
# Expected:
#   • 13 tables
#   • 4 ENUM types
#   • 60+ indexes
#   • 3 foreign keys
#   • 5 sequences
#   • 87 currency mappings
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

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🔍 PGP-LIVE Schema Verification${NC}"
echo -e "${BLUE}============================================${NC}"

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
VERIFY_SCRIPT="$TOOLS_DIR/verify_pgp_live_schema.py"
if [ ! -f "$VERIFY_SCRIPT" ]; then
    echo -e "${RED}❌ Error: Verification script not found at $VERIFY_SCRIPT${NC}"
    exit 1
fi

# Set GCP project
echo -e "\n${BLUE}⏳ Setting GCP project to pgp-live...${NC}"
gcloud config set project pgp-live 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Warning: Could not set GCP project (continuing anyway)${NC}"
}

# Execute verification script
echo -e "\n${BLUE}⏳ Executing verification script...${NC}"
python3 "$VERIFY_SCRIPT"

VERIFY_EXIT_CODE=$?

# Deactivate virtual environment
deactivate

# Print final status
echo -e "\n${BLUE}============================================${NC}"
if [ $VERIFY_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Verification passed - Schema is correct${NC}"
else
    echo -e "${RED}❌ Verification failed - Issues found${NC}"
fi
echo -e "${BLUE}============================================${NC}"

exit $VERIFY_EXIT_CODE
