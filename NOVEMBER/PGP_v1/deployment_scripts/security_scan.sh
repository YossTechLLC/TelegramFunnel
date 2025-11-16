#!/bin/bash
# PayGatePrime v1 - Automated Security Scanner
# DO NOT EXECUTE without reviewing - for security assessment only
# This script performs automated security checks on all services

set -e

BASE_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1"
REPORT_DIR="${BASE_DIR}/security_reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🔐 PayGatePrime v1 - Security Scanner"
echo "======================================"
echo ""
echo "📍 Base Directory: $BASE_DIR"
echo "📍 Report Directory: $REPORT_DIR"
echo "📍 Timestamp: $TIMESTAMP"
echo ""

# Create reports directory
mkdir -p "$REPORT_DIR"

# Initialize report
REPORT_FILE="${REPORT_DIR}/security_scan_${TIMESTAMP}.md"
echo "# PayGatePrime v1 - Security Scan Report" > "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**Scan Date:** $(date)" >> "$REPORT_FILE"
echo "**Services Scanned:** 15" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Counters
TOTAL_ISSUES=0
CRITICAL_ISSUES=0
HIGH_ISSUES=0
MEDIUM_ISSUES=0

# =============================================================================
# FUNCTION: Scan for hardcoded secrets
# =============================================================================

scan_hardcoded_secrets() {
    local service_dir=$1
    local service_name=$2

    echo -e "${BLUE}🔍 Scanning $service_name for hardcoded secrets...${NC}"

    local secrets_found=0

    # Patterns to search for
    patterns=(
        "api_key\s*=\s*['\"][^'\"]{10,}"
        "password\s*=\s*['\"][^'\"]{5,}"
        "secret\s*=\s*['\"][^'\"]{10,}"
        "token\s*=\s*['\"][^'\"]{10,}"
        "NOWPAYMENTS_API_KEY\s*=\s*['\"]"
        "CHANGENOW_API_KEY\s*=\s*['\"]"
        "TELEGRAM_BOT_TOKEN\s*=\s*['\"]"
        "JWT_SECRET_KEY\s*=\s*['\"]"
    )

    for pattern in "${patterns[@]}"; do
        result=$(grep -rn -E "$pattern" "$service_dir" --include="*.py" 2>/dev/null | grep -v "get_secret\|SECRET_NAME\|config_manager\|# Example" || true)
        if [ ! -z "$result" ]; then
            secrets_found=$((secrets_found + 1))
            echo -e "${RED}  ❌ CRITICAL: Potential hardcoded secret found${NC}"
            echo "$result"

            echo "### 🔴 CRITICAL: Hardcoded Secret in $service_name" >> "$REPORT_FILE"
            echo '```' >> "$REPORT_FILE"
            echo "$result" >> "$REPORT_FILE"
            echo '```' >> "$REPORT_FILE"
            echo "" >> "$REPORT_FILE"

            CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        fi
    done

    if [ $secrets_found -eq 0 ]; then
        echo -e "${GREEN}  ✅ No hardcoded secrets found${NC}"
    fi

    TOTAL_ISSUES=$((TOTAL_ISSUES + secrets_found))
}

# =============================================================================
# FUNCTION: Scan for SQL injection vulnerabilities
# =============================================================================

scan_sql_injection() {
    local service_dir=$1
    local service_name=$2

    echo -e "${BLUE}🔍 Scanning $service_name for SQL injection risks...${NC}"

    local sql_issues=0

    # Look for dangerous SQL patterns
    patterns=(
        "execute.*f\""
        "execute.*\.format"
        "execute.*%.*%"
    )

    for pattern in "${patterns[@]}"; do
        result=$(grep -rn -E "$pattern" "$service_dir" --include="*.py" 2>/dev/null || true)
        if [ ! -z "$result" ]; then
            sql_issues=$((sql_issues + 1))
            echo -e "${RED}  ❌ CRITICAL: Potential SQL injection vulnerability${NC}"
            echo "$result"

            echo "### 🔴 CRITICAL: SQL Injection Risk in $service_name" >> "$REPORT_FILE"
            echo '```' >> "$REPORT_FILE"
            echo "$result" >> "$REPORT_FILE"
            echo '```' >> "$REPORT_FILE"
            echo "" >> "$REPORT_FILE"

            CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        fi
    done

    if [ $sql_issues -eq 0 ]; then
        echo -e "${GREEN}  ✅ No SQL injection vulnerabilities found${NC}"
    fi

    TOTAL_ISSUES=$((TOTAL_ISSUES + sql_issues))
}

# =============================================================================
# FUNCTION: Scan for old naming scheme
# =============================================================================

scan_old_naming() {
    local service_dir=$1
    local service_name=$2

    echo -e "${BLUE}🔍 Scanning $service_name for old GC* naming...${NC}"

    local naming_issues=0

    # Look for old secret names
    result=$(grep -rn "GCWEBHOOK1_QUEUE\|GCWEBHOOK2_QUEUE\|GCSPLIT1_QUEUE\|GCSPLIT2_QUEUE\|GCSPLIT3_QUEUE\|GCACCUMULATOR_QUEUE\|GCHOSTPAY1_QUEUE\|GCHOSTPAY2_QUEUE\|GCHOSTPAY3_QUEUE\|GCWEBHOOK1_URL\|GCWEBHOOK2_URL\|GCSPLIT1_URL\|GCSPLIT2_URL\|GCSPLIT3_URL\|GCACCUMULATOR_URL\|GCHOSTPAY1_URL\|GCHOSTPAY2_URL\|GCHOSTPAY3_URL" "$service_dir" --include="*.py" 2>/dev/null || true)

    if [ ! -z "$result" ]; then
        naming_issues=$((naming_issues + 1))
        echo -e "${YELLOW}  ⚠️  HIGH: Old GC* naming scheme found${NC}"
        echo "$result"

        echo "### 🟡 HIGH: Old Naming Scheme in $service_name" >> "$REPORT_FILE"
        echo '```' >> "$REPORT_FILE"
        echo "$result" >> "$REPORT_FILE"
        echo '```' >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"

        HIGH_ISSUES=$((HIGH_ISSUES + 1))
    else
        echo -e "${GREEN}  ✅ Using correct PGP v1 naming${NC}"
    fi

    TOTAL_ISSUES=$((TOTAL_ISSUES + naming_issues))
}

# =============================================================================
# FUNCTION: Scan for logging sensitive data
# =============================================================================

scan_logging_issues() {
    local service_dir=$1
    local service_name=$2

    echo -e "${BLUE}🔍 Scanning $service_name for logging issues...${NC}"

    local log_issues=0

    # Look for dangerous logging patterns
    patterns=(
        "logger.*password"
        "logger.*api_key"
        "logger.*token"
        "logger.*secret"
        "print.*password"
        "print.*api_key"
    )

    for pattern in "${patterns[@]}"; do
        result=$(grep -rn -i -E "$pattern" "$service_dir" --include="*.py" 2>/dev/null | grep -v "# Example\|\"password_reset\"\|\"token_expires\"" || true)
        if [ ! -z "$result" ]; then
            log_issues=$((log_issues + 1))
            echo -e "${RED}  ❌ CRITICAL: Sensitive data may be logged${NC}"
            echo "$result"

            echo "### 🔴 CRITICAL: Sensitive Data Logging in $service_name" >> "$REPORT_FILE"
            echo '```' >> "$REPORT_FILE"
            echo "$result" >> "$REPORT_FILE"
            echo '```' >> "$REPORT_FILE"
            echo "" >> "$REPORT_FILE"

            CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
        fi
    done

    if [ $log_issues -eq 0 ]; then
        echo -e "${GREEN}  ✅ No sensitive data logging found${NC}"
    fi

    TOTAL_ISSUES=$((TOTAL_ISSUES + log_issues))
}

# =============================================================================
# FUNCTION: Check requirements.txt
# =============================================================================

check_requirements() {
    local service_dir=$1
    local service_name=$2

    echo -e "${BLUE}🔍 Checking $service_name requirements.txt...${NC}"

    if [ ! -f "$service_dir/requirements.txt" ]; then
        echo -e "${YELLOW}  ⚠️  No requirements.txt found${NC}"
        echo "### 🟡 HIGH: Missing requirements.txt in $service_name" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        HIGH_ISSUES=$((HIGH_ISSUES + 1))
        TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
        return
    fi

    # Check for unpinned versions
    unpinned=$(grep -v "^#" "$service_dir/requirements.txt" | grep -v "==" | grep -v "^\s*$" || true)
    if [ ! -z "$unpinned" ]; then
        echo -e "${YELLOW}  ⚠️  Unpinned dependencies found:${NC}"
        echo "$unpinned"
        echo "### 🟡 HIGH: Unpinned Dependencies in $service_name" >> "$REPORT_FILE"
        echo '```' >> "$REPORT_FILE"
        echo "$unpinned" >> "$REPORT_FILE"
        echo '```' >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        HIGH_ISSUES=$((HIGH_ISSUES + 1))
        TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
    else
        echo -e "${GREEN}  ✅ All dependencies pinned${NC}"
    fi
}

# =============================================================================
# FUNCTION: Check for CORS configuration
# =============================================================================

check_cors() {
    local service_dir=$1
    local service_name=$2

    echo -e "${BLUE}🔍 Checking $service_name CORS configuration...${NC}"

    # Look for permissive CORS
    result=$(grep -rn "CORS.*\*\|Access-Control-Allow-Origin.*\*" "$service_dir" --include="*.py" 2>/dev/null || true)

    if [ ! -z "$result" ]; then
        echo -e "${YELLOW}  ⚠️  Permissive CORS configuration found${NC}"
        echo "$result"
        echo "### 🟡 HIGH: Permissive CORS in $service_name" >> "$REPORT_FILE"
        echo "CORS is set to allow all origins (*). This should be restricted to specific domains." >> "$REPORT_FILE"
        echo '```' >> "$REPORT_FILE"
        echo "$result" >> "$REPORT_FILE"
        echo '```' >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        HIGH_ISSUES=$((HIGH_ISSUES + 1))
        TOTAL_ISSUES=$((TOTAL_ISSUES + 1))
    else
        echo -e "${GREEN}  ✅ No permissive CORS found${NC}"
    fi
}

# =============================================================================
# MAIN SCANNING LOOP
# =============================================================================

echo "## Scan Results" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Define services to scan
declare -A SERVICES=(
    ["GCRegisterAPI-PGP"]="pgp-server-v1"
    ["np-webhook-PGP"]="pgp-npwebhook-v1"
    ["GCWebhook1-PGP"]="pgp-webhook1-v1"
    ["GCWebhook2-PGP"]="pgp-webhook2-v1"
    ["GCSplit1-PGP"]="pgp-split1-v1"
    ["GCSplit2-PGP"]="pgp-split2-v1"
    ["GCSplit3-PGP"]="pgp-split3-v1"
    ["GCHostPay1-PGP"]="pgp-hostpay1-v1"
    ["GCHostPay2-PGP"]="pgp-hostpay2-v1"
    ["GCHostPay3-PGP"]="pgp-hostpay3-v1"
    ["GCAccumulator-PGP"]="pgp-accumulator-v1"
    ["GCBatchProcessor-PGP"]="pgp-batchprocessor-v1"
    ["GCMicroBatchProcessor-PGP"]="pgp-microbatchprocessor-v1"
    ["TelePay-PGP"]="pgp-bot-v1"
)

for service_dir in "${!SERVICES[@]}"; do
    service_name="${SERVICES[$service_dir]}"
    full_path="${BASE_DIR}/${service_dir}"

    if [ ! -d "$full_path" ]; then
        echo -e "${RED}⚠️  Directory not found: $full_path${NC}"
        continue
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}📦 Scanning: $service_name ($service_dir)${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    echo "### Service: $service_name" >> "$REPORT_FILE"
    echo "**Directory:** $service_dir" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Run all scans
    scan_hardcoded_secrets "$full_path" "$service_name"
    scan_sql_injection "$full_path" "$service_name"
    scan_old_naming "$full_path" "$service_name"
    scan_logging_issues "$full_path" "$service_name"
    check_requirements "$full_path" "$service_name"

    # CORS only for API service
    if [ "$service_name" == "pgp-server-v1" ]; then
        check_cors "$full_path" "$service_name"
    fi

    echo "" >> "$REPORT_FILE"
    echo "---" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
done

# =============================================================================
# SUMMARY
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 SCAN SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "Total Issues Found: ${YELLOW}$TOTAL_ISSUES${NC}"
echo -e "  🔴 Critical: ${RED}$CRITICAL_ISSUES${NC}"
echo -e "  🟡 High: ${YELLOW}$HIGH_ISSUES${NC}"
echo -e "  🟢 Medium: ${GREEN}$MEDIUM_ISSUES${NC}"
echo ""

# Write summary to report
echo "## Summary" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| Severity | Count |" >> "$REPORT_FILE"
echo "|----------|-------|" >> "$REPORT_FILE"
echo "| 🔴 Critical | $CRITICAL_ISSUES |" >> "$REPORT_FILE"
echo "| 🟡 High | $HIGH_ISSUES |" >> "$REPORT_FILE"
echo "| 🟢 Medium | $MEDIUM_ISSUES |" >> "$REPORT_FILE"
echo "| **Total** | **$TOTAL_ISSUES** |" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Deployment recommendation
if [ $CRITICAL_ISSUES -gt 0 ]; then
    echo -e "${RED}❌ DO NOT DEPLOY - Critical security issues found!${NC}"
    echo "## Recommendation" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "🔴 **DO NOT DEPLOY** - Critical security issues must be fixed before deployment." >> "$REPORT_FILE"
elif [ $HIGH_ISSUES -gt 0 ]; then
    echo -e "${YELLOW}⚠️  REVIEW REQUIRED - High priority issues found${NC}"
    echo "## Recommendation" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "🟡 **REVIEW REQUIRED** - High priority issues should be addressed before deployment." >> "$REPORT_FILE"
else
    echo -e "${GREEN}✅ No critical or high priority issues found${NC}"
    echo "## Recommendation" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "✅ **APPROVED** - No critical or high priority security issues found. Manual review recommended." >> "$REPORT_FILE"
fi

echo ""
echo "📄 Full report saved to: $REPORT_FILE"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Scan completed at: $(date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 0
