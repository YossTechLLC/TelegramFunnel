#!/bin/bash
################################################################################
# IAM Invoker Permissions Configuration Script for PGP_v1
# Purpose: Grant roles/run.invoker permissions for service-to-service auth
# Version: 1.0.0
# Date: 2025-01-18
# ⚠️  DO NOT RUN UNTIL SERVICES ARE DEPLOYED WITH --no-allow-unauthenticated
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-pgp-live}"
REGION="${GCP_REGION:-us-central1}"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🔒 PGP_v1 IAM Invoker Permissions Configuration Script${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This configures service-to-service authentication!${NC}"
echo ""
echo "Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   Region: $REGION"
echo ""
echo "This script grants roles/run.invoker permission to allow:"
echo "   - Cloud Run service A to call Cloud Run service B"
echo "   - Based on the PGP_v1 architecture communication flow"
echo ""

# Safety check
read -p "Are you sure you want to proceed? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Invoker permission configuration cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}Starting invoker permission configuration...${NC}"
echo ""

# Tracking
GRANTED=0
FAILED=0
declare -a FAILED_GRANTS

################################################################################
# Helper Function: Grant Invoker Permission
################################################################################

grant_invoker_permission() {
    local CALLER_SA=$1      # Service account that will call the service
    local TARGET_SERVICE=$2  # Cloud Run service that will be called
    local DESCRIPTION=$3     # Description of the flow

    local CALLER_EMAIL="${CALLER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

    echo ""
    echo -e "${BLUE}📞 ${DESCRIPTION}${NC}"
    echo "   Caller: $CALLER_SA"
    echo "   Target: $TARGET_SERVICE"

    # Check if target service exists
    if ! gcloud run services describe "$TARGET_SERVICE" \
        --region="$REGION" \
        --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}   ⚠️  Target service not found (skipping - deploy service first)${NC}"
        return 0
    fi

    # Grant invoker permission
    if gcloud run services add-iam-policy-binding "$TARGET_SERVICE" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --member="serviceAccount:${CALLER_EMAIL}" \
        --role="roles/run.invoker" \
        --quiet &>/dev/null; then

        echo -e "${GREEN}   ✅ Granted invoker permission${NC}"
        ((GRANTED++))
        return 0
    else
        echo -e "${RED}   ❌ Failed to grant invoker permission${NC}"
        FAILED_GRANTS+=("${CALLER_SA} → ${TARGET_SERVICE}")
        ((FAILED++))
        return 1
    fi
}

################################################################################
# Payment Processing Pipeline Permissions
################################################################################

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Payment Processing Pipeline${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# NowPayments IPN → Orchestrator
grant_invoker_permission \
    "pgp-np-ipn-v1-sa" \
    "pgp-orchestrator-v1" \
    "NowPayments IPN → Orchestrator (payment received)"

# Orchestrator → Invite Service
grant_invoker_permission \
    "pgp-orchestrator-v1-sa" \
    "pgp-invite-v1" \
    "Orchestrator → Invite (generate channel invite)"

# Orchestrator → Split1 (payment splitting)
grant_invoker_permission \
    "pgp-orchestrator-v1-sa" \
    "pgp-split1-v1" \
    "Orchestrator → Split1 (initiate payment split)"

# Split1 → Split2 (split calculation stage 2)
grant_invoker_permission \
    "pgp-split1-v1-sa" \
    "pgp-split2-v1" \
    "Split1 → Split2 (split calculation stage 2)"

# Split2 → Split3 (split calculation stage 3)
grant_invoker_permission \
    "pgp-split2-v1-sa" \
    "pgp-split3-v1" \
    "Split2 → Split3 (split calculation stage 3)"

################################################################################
# Payout Pipeline Permissions
################################################################################

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Payout Pipeline${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Accumulator → HostPay1 (initiate host payout)
grant_invoker_permission \
    "pgp-accumulator-v1-sa" \
    "pgp-hostpay1-v1" \
    "Accumulator → HostPay1 (initiate host payout)"

# HostPay1 → HostPay2 (payout stage 2)
grant_invoker_permission \
    "pgp-hostpay1-v1-sa" \
    "pgp-hostpay2-v1" \
    "HostPay1 → HostPay2 (payout processing stage 2)"

# HostPay2 → HostPay3 (payout stage 3)
grant_invoker_permission \
    "pgp-hostpay2-v1-sa" \
    "pgp-hostpay3-v1" \
    "HostPay2 → HostPay3 (payout processing stage 3)"

# Accumulator → BatchProcessor (scheduled batch payouts)
grant_invoker_permission \
    "pgp-accumulator-v1-sa" \
    "pgp-batchprocessor-v1" \
    "Accumulator → BatchProcessor (scheduled batch payouts)"

# BatchProcessor → MicroBatchProcessor (real-time micro batches)
grant_invoker_permission \
    "pgp-batchprocessor-v1-sa" \
    "pgp-microbatchprocessor-v1" \
    "BatchProcessor → MicroBatchProcessor (micro batch payouts)"

################################################################################
# Notification Pipeline Permissions
################################################################################

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Notification Pipeline${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Orchestrator → Notifications (send payment notification)
grant_invoker_permission \
    "pgp-orchestrator-v1-sa" \
    "pgp-notifications-v1" \
    "Orchestrator → Notifications (payment notification trigger)"

# Notifications → Server (deliver notification via Telegram)
grant_invoker_permission \
    "pgp-notifications-v1-sa" \
    "pgp-server-v1" \
    "Notifications → Server (deliver notification via Telegram)"

################################################################################
# Broadcast System Permissions
################################################################################

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Broadcast System${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Broadcast → Server (send broadcast message via Telegram)
grant_invoker_permission \
    "pgp-broadcast-v1-sa" \
    "pgp-server-v1" \
    "Broadcast → Server (scheduled broadcast via Telegram)"

################################################################################
# Web API Permissions
################################################################################

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Web API${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Web → WebAPI (frontend → backend communication)
grant_invoker_permission \
    "pgp-web-v1-sa" \
    "pgp-webapi-v1" \
    "Web → WebAPI (frontend to backend API calls)"

################################################################################
# Summary
################################################################################

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}📊 Invoker Permissions Configuration Summary${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${GREEN}✅ Successfully granted: $GRANTED invoker permissions${NC}"
echo -e "${RED}❌ Failed: $FAILED invoker permissions${NC}"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed grants:${NC}"
    for grant in "${FAILED_GRANTS[@]}"; do
        echo "   - $grant"
    done
    echo ""
    echo -e "${YELLOW}⚠️  Some permissions failed. Please review errors above.${NC}"
    exit 1
fi

################################################################################
# Verification
################################################################################

echo -e "${GREEN}Verification${NC}"
echo "========================================="
echo ""
echo "Sample invoker permission check (pgp-orchestrator-v1):"
echo ""

gcloud run services get-iam-policy pgp-orchestrator-v1 \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="table(bindings.role,bindings.members)" \
    2>/dev/null || echo "Service not deployed yet"

echo ""
echo -e "${GREEN}🎉 Invoker permissions configured successfully!${NC}"
echo ""
echo -e "${YELLOW}⚠️  Next Steps:${NC}"
echo "   1. Update application code to use call_authenticated_service()"
echo "   2. Deploy services with --no-allow-unauthenticated flag"
echo "   3. Test service-to-service authentication"
echo "   4. Monitor logs for authentication errors"
echo ""
echo -e "${YELLOW}⚠️  Important Notes:${NC}"
echo "   - Services must be deployed with --no-allow-unauthenticated for auth to work"
echo "   - Calling services must use identity tokens in Authorization header"
echo "   - See /PGP_COMMON/auth/service_auth.py for helper functions"
echo ""

################################################################################
# Save Configuration Metadata
################################################################################

OUTPUT_FILE="/tmp/pgp_invoker_permissions_$(date +%Y%m%d_%H%M%S).txt"
cat > "$OUTPUT_FILE" <<EOF
PGP_v1 Invoker Permissions Configured
======================================
Date: $(date)
Project: $PROJECT_ID
Region: $REGION
Total Granted: $GRANTED
Failed: $FAILED

Service-to-Service Communication Flows:
=======================================

Payment Processing Pipeline:
- pgp-np-ipn-v1 → pgp-orchestrator-v1
- pgp-orchestrator-v1 → pgp-invite-v1
- pgp-orchestrator-v1 → pgp-split1-v1
- pgp-split1-v1 → pgp-split2-v1
- pgp-split2-v1 → pgp-split3-v1

Payout Pipeline:
- pgp-accumulator-v1 → pgp-hostpay1-v1
- pgp-hostpay1-v1 → pgp-hostpay2-v1
- pgp-hostpay2-v1 → pgp-hostpay3-v1
- pgp-accumulator-v1 → pgp-batchprocessor-v1
- pgp-batchprocessor-v1 → pgp-microbatchprocessor-v1

Notification Pipeline:
- pgp-orchestrator-v1 → pgp-notifications-v1
- pgp-notifications-v1 → pgp-server-v1

Broadcast System:
- pgp-broadcast-v1 → pgp-server-v1

Web API:
- pgp-web-v1 → pgp-webapi-v1
EOF

echo "Invoker permissions log saved to: $OUTPUT_FILE"
echo ""
