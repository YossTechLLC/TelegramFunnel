# Hot-Reload Implementation Progress Tracker

**Started**: 2025-11-18
**Status**: 🟢 IN PROGRESS - Pilot Complete
**Current Phase**: Phase 2 - Service Implementation (1/17 completed)

---

## Progress Overview

- ✅ Phase 1.1: Update BaseConfigManager (COMPLETED)
  - ✅ Secret Manager client already initialized
  - ✅ Added `fetch_secret_dynamic()` method with request-level caching
  - ✅ Added `build_secret_path()` helper method
  - ✅ Updated `fetch_secret()` docstring to clarify static usage
  - ✅ Added Flask `g` context caching to prevent duplicate API calls

- 🟢 Phase 2: Service-by-Service Implementation (1/17 completed)
  - ✅ PGP_SPLIT2_v1 (PILOT COMPLETE - hot-reload enabled for 5 secrets)
  - ⏸️ Remaining 16 services pending

- ⏸️ Phase 3: Security Verification
- ⏸️ Phase 4: Testing Strategy
- ⏸️ Phase 5: Deployment Scripts
- ⏸️ Phase 6: Verification
- ⏸️ Phase 7: Operational Runbooks

---

## Phase 1 Progress: Infrastructure Foundation

### 1.1 BaseConfigManager Updates

**File**: `PGP_COMMON/config/base_config.py`

**Completed**:
- ✅ Secret Manager client already initialized in `__init__`

**In Progress**:
- 🔄 Adding `fetch_secret_dynamic()` method
- 🔄 Adding `build_secret_path()` helper
- 🔄 Adding request-level caching support

**Pending**:
- ⏸️ Update `fetch_secret()` docstring to clarify static vs dynamic usage
- ⏸️ Test dynamic fetch with sample secret

---

## Security Critical Reminders

### ❌ NEVER Hot-Reload These 3 Secrets:
1. `HOST_WALLET_PRIVATE_KEY` (PGP_HOSTPAY3_v1) - ETH wallet private key
2. `SUCCESS_URL_SIGNING_KEY` (PGP_ORCHESTRATOR_v1) - JWT signing key
3. `TPS_HOSTPAY_SIGNING_KEY` (PGP_SERVER_v1, PGP_HOSTPAY1_v1) - HMAC signing key

### ⚠️ Keep Static (Complex Cases):
- `DATABASE_PASSWORD_SECRET` - Requires connection pool restart
- All database connection secrets

---

## Services to Implement (17 Total)

### Priority 1: Pilot Service
- [ ] PGP_SPLIT2_v1 (pilot - ChangeNow API key hot-reload)

### Priority 2: Core Payment Services
- [ ] PGP_ORCHESTRATOR_v1 ⚠️ (has SUCCESS_URL_SIGNING_KEY - static)
- [ ] PGP_SPLIT1_v1
- [ ] PGP_HOSTPAY1_v1 ⚠️ (has TPS_HOSTPAY_SIGNING_KEY - static)
- [ ] PGP_HOSTPAY2_v1
- [ ] PGP_HOSTPAY3_v1 ⚠️ (has HOST_WALLET_PRIVATE_KEY - static)

### Priority 3: Webhook & Bot Services
- [ ] PGP_NP_IPN_v1 (formerly PGP_NPWEBHOOK_v1)
- [ ] PGP_SERVER_v1 ⚠️ (has TPS_HOSTPAY_SIGNING_KEY - static)
- [ ] PGP_NOTIFICATIONS_v1
- [ ] PGP_INVITE_v1
- [ ] PGP_BOTCOMMAND_v1 (if exists)

### Priority 4: Remaining Services
- [ ] PGP_ACCUMULATOR_v1
- [ ] PGP_BATCHPROCESSOR_v1
- [ ] PGP_SCHEDULER_v1 (if exists)
- [ ] PGP_BROADCAST_v1
- [ ] PGP_CFWEBHOOK_v1 (if exists)
- [ ] PGP_TELEPAY_v1 (if exists - legacy bot)

---

## Implementation Notes

### Date: 2025-11-18 - Session Start
- Reviewed project structure: /NOVEMBER/PGP_v1
- Reviewed CLAUDE.md instructions
- Reviewed SECRET_SCHEME.md for secret naming
- Reviewed NAMING_SCHEME.md for service name mapping
- Found BaseConfigManager already has Secret Manager client initialized
- Found 15 service config_manager.py files (2 missing from expected 17)

### Completed Work Session 1 (2025-11-18):

**Phase 1 - BaseConfigManager Updates**:
- ✅ Added `build_secret_path()` helper method
- ✅ Added `fetch_secret_dynamic()` method with:
  - Secret Manager API integration
  - Flask `g` context caching for request-level deduplication
  - Comprehensive error handling
  - Security warnings in docstring (NEVER use for private keys)
- ✅ Updated `fetch_secret()` docstring to clarify static usage
- ✅ Added `from flask import g` import

**Phase 2.1 - PGP_SPLIT2_v1 Pilot Service**:
- ✅ Updated `PGP_SPLIT2_v1/config_manager.py`:
  - Added 5 dynamic getter methods:
    - `get_changenow_api_key()` - HOT-RELOADABLE
    - `get_split1_response_queue()` - HOT-RELOADABLE
    - `get_split1_url()` - HOT-RELOADABLE
    - `get_batchprocessor_queue()` - HOT-RELOADABLE
    - `get_batchprocessor_url()` - HOT-RELOADABLE
  - Removed hot-reloadable secrets from `initialize_config()`
  - Kept `SUCCESS_URL_SIGNING_KEY` as STATIC (security-critical)

- ✅ Updated `PGP_SPLIT2_v1/changenow_client.py`:
  - Changed `__init__()` to accept `config_manager` instead of `api_key`
  - Updated `get_estimated_amount_v2_with_retry()` to fetch API key dynamically on each request
  - Added validation and retry logic if API key fetch fails

- ✅ Updated `PGP_SPLIT2_v1/pgp_split2_v1.py`:
  - Changed ChangeNowClient initialization to pass `config_manager`
  - Updated Cloud Tasks enqueue logic to use dynamic getters for queue name and URL
  - Kept static secret usage for `success_url_signing_key` (token decryption)

**Security Verification**:
- ✅ Verified `SUCCESS_URL_SIGNING_KEY` remains static in PGP_SPLIT2_v1
- ✅ Verified database credentials remain static

### Next Steps:
1. Implement hot-reload for security-critical services (PGP_ORCHESTRATOR_v1, PGP_HOSTPAY1_v1, PGP_HOSTPAY3_v1, PGP_SERVER_v1)
2. Implement hot-reload for remaining 12 services
3. Create deployment scripts in /TOOLS_SCRIPTS_TESTS/scripts/
4. Perform security audit to verify 3 static secrets never use dynamic fetch

---

## Hot-Reloadable Secrets Count by Category

- ✅ API Keys: 5 secrets
- ✅ Service URLs: 13 secrets
- ✅ Queue Names: 15 secrets
- ✅ Webhook/IPN Secrets: 4 secrets
- ✅ Application Config: 6 secrets
- **Total: 43 secrets to make hot-reloadable**

---

## Deployment Scripts to Create

1. `deploy_hot_reload_base_config.sh` - Update PGP_COMMON
2. `deploy_hot_reload_pilot.sh` - Deploy PGP_SPLIT2_v1 with hot-reload
3. `deploy_hot_reload_all_services.sh` - Staged rollout for all 17 services
4. `test_hot_reload_functionality.sh` - Test script for verification

---

**Last Updated**: 2025-11-18 (Session Start)
