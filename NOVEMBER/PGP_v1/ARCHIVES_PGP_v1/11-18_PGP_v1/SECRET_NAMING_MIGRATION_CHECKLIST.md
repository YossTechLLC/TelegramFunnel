# Secret Name Migration Checklist - PGP_v1 Naming Scheme

**Project**: `pgp-live` (NEW) | `telepay-459221` (OLD)
**Date**: 2025-11-16
**Status**: ⚠️ **MIGRATION REQUIRED - SECRET NAMES MUST CHANGE**

---

## Critical Understanding

**ISSUE IDENTIFIED:** Current SECRET_SCHEME.md incorrectly states "No secret name changes required"

**CORRECT APPROACH:** Secret **NAMES** must be updated to match PGP_v1 naming scheme:
- ❌ OLD: `GCACCUMULATOR_URL`, `GCWEBHOOK1_QUEUE`, etc.
- ✅ NEW: `PGP_ACCUMULATOR_URL`, `PGP_ORCHESTRATOR_QUEUE`, etc.

**Why This Matters:**
- Naming consistency across codebase, services, and secrets
- Clearer mapping to actual service names
- Eliminates GC (GoogleCloud) legacy naming confusion
- Aligns with NAMING_SCHEME.md service names

---

## Part 1: Service URL Secret Name Changes

### 1.1 URL Secrets Requiring Name Changes (13 secrets)

| OLD Secret Name | NEW Secret Name | Service | Value (Updated) | Priority |
|-----------------|-----------------|---------|-----------------|----------|
| `GCACCUMULATOR_URL` | `PGP_ACCUMULATOR_URL` | PGP_ACCUMULATOR_v1 | `https://pgp-accumulator-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `GCBATCHPROCESSOR_URL` | `PGP_BATCHPROCESSOR_URL` | PGP_BATCHPROCESSOR_v1 | `https://pgp-batchprocessor-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `MICROBATCH_URL` | `PGP_MICROBATCHPROCESSOR_URL` | PGP_MICROBATCHPROCESSOR_v1 | `https://pgp-microbatchprocessor-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `GCHOSTPAY1_URL` | `PGP_HOSTPAY1_URL` | PGP_HOSTPAY1_v1 | `https://pgp-hostpay1-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `GCHOSTPAY2_URL` | `PGP_HOSTPAY2_URL` | PGP_HOSTPAY2_v1 | `https://pgp-hostpay2-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `GCHOSTPAY3_URL` | `PGP_HOSTPAY3_URL` | PGP_HOSTPAY3_v1 | `https://pgp-hostpay3-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `GCSPLIT1_URL` | `PGP_SPLIT1_URL` | PGP_SPLIT1_v1 | `https://pgp-split1-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `GCSPLIT2_URL` | `PGP_SPLIT2_URL` | PGP_SPLIT2_v1 | `https://pgp-split2-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `GCSPLIT3_URL` | `PGP_SPLIT3_URL` | PGP_SPLIT3_v1 | `https://pgp-split3-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `GCWEBHOOK1_URL` | `PGP_ORCHESTRATOR_URL` | PGP_ORCHESTRATOR_v1 | `https://pgp-orchestrator-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 CRITICAL |
| `GCWEBHOOK2_URL` | `PGP_INVITE_URL` | PGP_INVITE_v1 | `https://pgp-invite-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 HIGH |
| `TELEPAY_BOT_URL` | `PGP_SERVER_URL` | PGP_SERVER_v1 | `https://pgp-server-v1-<PROJECT_NUM>.us-central1.run.app` | 🟡 MEDIUM |
| `NOWPAYMENTS_IPN_CALLBACK_URL` | `PGP_NP_IPN_CALLBACK_URL` | PGP_NP_IPN_v1 | `https://pgp-np-ipn-v1-<PROJECT_NUM>.us-central1.run.app` | 🔴 CRITICAL |

**Additional URL Secrets (Keep Same Name, Update Value):**
| Secret Name | Service | Value (Updated) | Notes |
|-------------|---------|-----------------|-------|
| `WEBHOOK_BASE_URL` | PGP_ORCHESTRATOR_v1 | `https://pgp-orchestrator-v1-<PROJECT_NUM>.us-central1.run.app` | ✅ Name OK |
| `HOSTPAY_WEBHOOK_URL` | PGP_HOSTPAY1_v1 | `https://pgp-hostpay1-v1-<PROJECT_NUM>.us-central1.run.app` | ⚠️ Duplicate of PGP_HOSTPAY1_URL |
| `TPS_WEBHOOK_URL` | PGP_SPLIT1_v1 | `https://pgp-split1-v1-<PROJECT_NUM>.us-central1.run.app` | ✅ Name OK |

### 1.2 Callback URL Secrets (Keep Same Name)

| Secret Name | Service | Notes |
|-------------|---------|-------|
| `GCSPLIT1_ESTIMATE_RESPONSE_URL` | PGP_SPLIT1_v1 | ✅ Name OK - specific callback endpoint |
| `GCSPLIT1_SWAP_RESPONSE_URL` | PGP_SPLIT1_v1 | ✅ Name OK - specific callback endpoint |

---

## Part 2: Cloud Tasks Queue Secret Name Changes

### 2.1 Queue Secrets Requiring Name Changes (17 secrets)

| OLD Secret Name | NEW Secret Name | Service | Queue Name (Value) | Priority |
|-----------------|-----------------|---------|-------------------|----------|
| `GCACCUMULATOR_QUEUE` | `PGP_ACCUMULATOR_QUEUE` | PGP_ACCUMULATOR_v1 | `pgp-accumulator-queue-v1` | 🔴 HIGH |
| `GCACCUMULATOR_RESPONSE_QUEUE` | `PGP_ACCUMULATOR_RESPONSE_QUEUE` | PGP_ACCUMULATOR_v1 | `pgp-accumulator-response-queue-v1` | 🔴 HIGH |
| `GCBATCHPROCESSOR_QUEUE` | `PGP_BATCHPROCESSOR_QUEUE` | PGP_BATCHPROCESSOR_v1 | `pgp-batchprocessor-queue-v1` | 🔴 HIGH |
| `GCHOSTPAY1_QUEUE` | `PGP_HOSTPAY1_QUEUE` | PGP_HOSTPAY1_v1 | `pgp-hostpay1-trigger-queue-v1` | 🔴 HIGH |
| `GCHOSTPAY1_RESPONSE_QUEUE` | `PGP_HOSTPAY1_RESPONSE_QUEUE` | PGP_HOSTPAY1_v1 | `pgp-hostpay1-response-queue-v1` | 🔴 HIGH |
| `GCHOSTPAY1_BATCH_QUEUE` | `PGP_HOSTPAY1_BATCH_QUEUE` | PGP_HOSTPAY1_v1 | `pgp-hostpay1-batch-queue-v1` | 🟡 MEDIUM |
| `GCHOSTPAY2_QUEUE` | `PGP_HOSTPAY2_QUEUE` | PGP_HOSTPAY2_v1 | `pgp-hostpay2-status-queue-v1` | 🔴 HIGH |
| `GCHOSTPAY3_QUEUE` | `PGP_HOSTPAY3_QUEUE` | PGP_HOSTPAY3_v1 | `pgp-hostpay3-payment-queue-v1` | 🔴 HIGH |
| `GCHOSTPAY3_RETRY_QUEUE` | `PGP_HOSTPAY3_RETRY_QUEUE` | PGP_HOSTPAY3_v1 | `pgp-hostpay3-retry-queue-v1` | 🔴 HIGH |
| `GCSPLIT1_QUEUE` | `PGP_SPLIT1_QUEUE` | PGP_SPLIT1_v1 | `pgp-split1-estimate-queue-v1` | 🔴 HIGH |
| `GCSPLIT1_BATCH_QUEUE` | `PGP_SPLIT1_BATCH_QUEUE` | PGP_SPLIT1_v1 | `pgp-split1-batch-queue-v1` | 🟡 MEDIUM |
| `GCSPLIT2_QUEUE` | `PGP_SPLIT2_QUEUE` | PGP_SPLIT2_v1 | `pgp-split2-swap-queue-v1` | 🔴 HIGH |
| `GCSPLIT2_RESPONSE_QUEUE` | `PGP_SPLIT2_RESPONSE_QUEUE` | PGP_SPLIT2_v1 | `pgp-split2-response-queue-v1` | 🔴 HIGH |
| `GCSPLIT3_QUEUE` | `PGP_SPLIT3_QUEUE` | PGP_SPLIT3_v1 | `pgp-split3-client-queue-v1` | 🔴 HIGH |
| `GCSPLIT3_RESPONSE_QUEUE` | `PGP_SPLIT3_RESPONSE_QUEUE` | PGP_SPLIT3_v1 | `pgp-split3-response-queue-v1` | 🔴 HIGH |
| `GCWEBHOOK1_QUEUE` | `PGP_ORCHESTRATOR_QUEUE` | PGP_ORCHESTRATOR_v1 | `pgp-orchestrator-queue-v1` | 🔴 HIGH |
| `GCWEBHOOK2_QUEUE` | `PGP_INVITE_QUEUE` | PGP_INVITE_v1 | `pgp-invite-queue-v1` | 🔴 HIGH |

**Additional Queue Secrets (Duplicates):**
| OLD Secret Name | NEW Secret Name | Notes |
|-----------------|-----------------|-------|
| `HOSTPAY_QUEUE` | `PGP_HOSTPAY_TRIGGER_QUEUE` | ⚠️ Duplicate of PGP_HOSTPAY1_QUEUE - consider removing |
| `MICROBATCH_RESPONSE_QUEUE` | `PGP_MICROBATCH_RESPONSE_QUEUE` | ✅ Rename needed |

---

## Part 3: Secrets That DO NOT Require Name Changes (52 secrets)

### 3.1 API Keys & Tokens ✅ NO CHANGE

| Secret Name | Description | Action |
|-------------|-------------|--------|
| `1INCH_API_KEY` | 1inch DEX API | ✅ Keep name, copy value |
| `NOWPAYMENTS_API_KEY` | NOWPayments API | ✅ Keep name, copy value |
| `NOWPAYMENTS_IPN_SECRET` | NOWPayments IPN secret | ✅ Keep name, copy value |
| `NOWPAYMENT_WEBHOOK_KEY` | NOWPayments webhook key | ✅ Keep name, copy value |
| `PAYMENT_PROVIDER_TOKEN` | Duplicate of NOWPAYMENTS_API_KEY | ⚠️ Duplicate - keep for compatibility |
| `CHANGENOW_API_KEY` | ChangeNOW exchange | ✅ Keep name, copy value |
| `COINGECKO_API_KEY` | CoinGecko price API | ✅ Keep name, copy value |
| `CRYPTOCOMPARE_API_KEY` | CryptoCompare API | ✅ Keep name, copy value |

### 3.2 Blockchain & Wallet ✅ NO CHANGE

| Secret Name | Description | Action |
|-------------|-------------|--------|
| `HOST_WALLET_PRIVATE_KEY` | 🔴 CRITICAL: Wallet private key | ✅ Keep name, copy value |
| `HOST_WALLET_ETH_ADDRESS` | Host wallet ETH address | ✅ Keep name, copy value |
| `HOST_WALLET_USDT_ADDRESS` | Host wallet USDT address | ✅ Keep name, copy value |
| `ETHEREUM_RPC_URL` | Alchemy RPC full URL | ✅ Keep name, copy value |
| `ETHEREUM_RPC_URL_API` | Alchemy API key only | ✅ Keep name, copy value |
| `ETHEREUM_RPC_WEBHOOK_SECRET` | Alchemy webhook secret | ✅ Keep name, copy value |

### 3.3 Database Credentials ⚠️ UPDATE VALUES

| Secret Name | Description | OLD Value | NEW Value (pgp-live) |
|-------------|-------------|-----------|---------------------|
| `DATABASE_HOST_SECRET` | PostgreSQL host IP | `34.58.246.248` | ⚠️ **NEW IP after Cloud SQL creation** |
| `DATABASE_NAME_SECRET` | Database name | `client_table` | ✅ Keep or change to `pgp_live_db` |
| `DATABASE_USER_SECRET` | PostgreSQL user | `postgres` | ✅ Keep |
| `DATABASE_PASSWORD_SECRET` | PostgreSQL password | `Chig...st3$` | ⚠️ **GENERATE NEW PASSWORD** |
| `DATABASE_SECRET_KEY` | DB encryption key | `y764...3LM` | ⚠️ **GENERATE NEW KEY** |
| `CLOUD_SQL_CONNECTION_NAME` | Cloud SQL instance | `telepay-459221:us-central1:telepaypsql` | ⚠️ **NEW: `pgp-live:us-central1:pgp-live-psql`** |

### 3.4 Telegram Bot ✅ NO CHANGE

| Secret Name | Description | Action |
|-------------|-------------|--------|
| `TELEGRAM_BOT_SECRET_NAME` | Telegram bot token | ✅ Keep name, copy value (or use NEW bot) |
| `TELEGRAM_BOT_USERNAME` | Bot username | ✅ Keep name, copy value |

### 3.5 Signing & Security Keys ⚠️ REGENERATE RECOMMENDED

| Secret Name | Description | Action |
|-------------|-------------|--------|
| `WEBHOOK_SIGNING_KEY` | Webhook payload signing | ⚠️ Keep name, REGENERATE value for pgp-live |
| `TPS_HOSTPAY_SIGNING_KEY` | TelePay→HostPay signing | ⚠️ Keep name, REGENERATE value for pgp-live |
| `SUCCESS_URL_SIGNING_KEY` | Payment success URL signing | ⚠️ Keep name, REGENERATE value for pgp-live |
| `JWT_SECRET_KEY` | JWT signing key | ⚠️ Keep name, REGENERATE value for pgp-live |
| `SIGNUP_SECRET_KEY` | User signup key | ⚠️ Keep name, REGENERATE value for pgp-live |

### 3.6 Email Configuration ✅ NO CHANGE

| Secret Name | Description | Action |
|-------------|-------------|--------|
| `SENDGRID_API_KEY` | SendGrid email API | ✅ Keep name, copy value |
| `FROM_EMAIL` | Sender email | ✅ Keep name, copy value |
| `FROM_NAME` | Sender name | ✅ Keep name, copy value |

### 3.7 Application Configuration ⚠️ UPDATE VALUES

| Secret Name | OLD Value | NEW Value (pgp-live) |
|-------------|-----------|---------------------|
| `BASE_URL` | `https://www.paygateprime.com` | ✅ Keep (unless using different domain) |
| `CORS_ORIGIN` | `https://www.paygateprime.com` | ✅ Keep (unless using different domain) |
| `CLOUD_TASKS_LOCATION` | `us-central1` | ✅ Keep |
| `CLOUD_TASKS_PROJECT_ID` | `telepay-459221` | ⚠️ **NEW: `pgp-live`** |
| `BROADCAST_AUTO_INTERVAL` | `24` | ✅ Keep |
| `BROADCAST_MANUAL_INTERVAL` | `0.0833` | ✅ Keep |
| `ALERTING_ENABLED` | `true` | ✅ Keep |
| `MICRO_BATCH_THRESHOLD_USD` | `5.00` | ✅ Keep |
| `PAYMENT_FALLBACK_TOLERANCE` | `0.75` | ✅ Keep |
| `PAYMENT_MIN_TOLERANCE` | `0.50` | ✅ Keep |
| `TP_FLAT_FEE` | `15` | ✅ Keep |

---

## Part 4: NEW Secrets Required (2 secrets)

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `FLASK_SECRET_KEY` | `<generate: secrets.token_hex(32)>` | Flask CSRF protection (64 chars hex) |
| `TELEGRAM_WEBHOOK_SECRET` | `<generate: secrets.token_urlsafe(32)>` | Telegram webhook verification |

---

## Part 5: Complete Migration Summary

### 5.1 Secret Name Changes Required

**Total Secrets Requiring Name Changes:** 32

**Breakdown:**
- 13 Service URL secrets (GC* → PGP_*)
- 17 Cloud Tasks Queue secrets (GC* → PGP_*)
- 2 Additional queue secrets (MICROBATCH_RESPONSE_QUEUE, HOSTPAY_QUEUE)

**Total Secrets Unchanged (Name):** 45
- 52 API keys, credentials, signing keys (names stay same, values copied/regenerated)
- -7 secrets needing both name AND value updates (counted in name changes)

### 5.2 Migration Strategy

**Option A: Create New Secrets in pgp-live (RECOMMENDED)**
1. Create all secrets with NEW names in pgp-live
2. Update all code references to use NEW secret names
3. Deploy all services to pgp-live with updated secret references
4. Test thoroughly
5. Decommission telepay-459221 secrets after successful migration

**Option B: Dual-Project Transition (NOT RECOMMENDED)**
- Too complex, maintains split between projects
- Higher risk of misconfiguration

### 5.3 Code Impact Analysis

**Files Requiring Updates (Secret Name References):**

Every service's `config_manager.py` file that references old secret names:
- `PGP_ACCUMULATOR_v1/config_manager.py`
- `PGP_BATCHPROCESSOR_v1/config_manager.py`
- `PGP_MICROBATCHPROCESSOR_v1/config_manager.py`
- `PGP_HOSTPAY1_v1/config_manager.py`
- `PGP_HOSTPAY2_v1/config_manager.py`
- `PGP_HOSTPAY3_v1/config_manager.py`
- `PGP_SPLIT1_v1/config_manager.py`
- `PGP_SPLIT2_v1/config_manager.py`
- `PGP_SPLIT3_v1/config_manager.py`
- `PGP_ORCHESTRATOR_v1/config_manager.py`
- `PGP_INVITE_v1/config_manager.py`
- `PGP_NP_IPN_v1/config_manager.py`
- `PGP_BROADCAST_v1/config_manager.py`
- `PGP_NOTIFICATIONS_v1/config_manager.py`
- `PGP_SERVER_v1/config_manager.py`
- `PGP_WEBAPI_v1/config_manager.py`

Plus any `cloudtasks_client.py` files that reference queue secrets.

---

## Part 6: Migration Checklist

### Phase 1: Documentation Update ✅
- [x] Create SECRET_NAMING_MIGRATION_CHECKLIST.md (this file)
- [ ] Update SECRET_SCHEME.md with correct naming
- [ ] Update NAMING_SCHEME.md to reference secret naming

### Phase 2: Code Updates (Before Deployment)
- [ ] Update all config_manager.py files with NEW secret names
- [ ] Update all cloudtasks_client.py files with NEW queue secret names
- [ ] Update deployment scripts with NEW secret environment variables
- [ ] Search and replace ALL `GC[A-Z]*_URL` → `PGP_*_URL` references
- [ ] Search and replace ALL `GC[A-Z]*_QUEUE` → `PGP_*_QUEUE` references
- [ ] Update CLOUD_TASKS_PROJECT_ID references to pgp-live

### Phase 3: Secret Creation in pgp-live
- [ ] Generate new security keys (FLASK_SECRET_KEY, TELEGRAM_WEBHOOK_SECRET, signing keys)
- [ ] Create all 32 renamed secrets with NEW names
- [ ] Create all 45 unchanged secrets (copy values from telepay-459221)
- [ ] Create new database secrets (after Cloud SQL instance created)
- [ ] Verify all 77 secrets exist in pgp-live Secret Manager

### Phase 4: Infrastructure Setup
- [ ] Create Cloud SQL instance in pgp-live
- [ ] Create database and schema
- [ ] Deploy all Cloud Tasks queues with NEW names
- [ ] Configure service accounts and IAM

### Phase 5: Service Deployment
- [ ] Deploy all 17 services to pgp-live Cloud Run
- [ ] Verify environment variables use NEW secret paths
- [ ] Test service health endpoints

### Phase 6: Testing & Validation
- [ ] End-to-end payment flow test
- [ ] Verify all secret references resolve correctly
- [ ] Monitor logs for secret access errors
- [ ] Load testing

### Phase 7: Cleanup (After Successful Migration)
- [ ] Archive telepay-459221 secrets (DO NOT DELETE)
- [ ] Remove duplicate secrets (HOSTPAY_QUEUE, PAYMENT_PROVIDER_TOKEN)
- [ ] Document migration completion

---

## Part 7: Risk Mitigation

### 7.1 High-Risk Items

1. **Secret Name Mismatches**
   - Risk: Services fail to start due to missing secrets
   - Mitigation: Comprehensive grep search, test in staging first

2. **Database Connection Failures**
   - Risk: Wrong CLOUD_SQL_CONNECTION_NAME or DATABASE_HOST
   - Mitigation: Update values AFTER Cloud SQL creation, verify connection strings

3. **Queue Name Mismatches**
   - Risk: Tasks fail to enqueue due to missing queues
   - Mitigation: Deploy queues BEFORE services, verify queue names match secrets

### 7.2 Rollback Plan

If migration fails:
1. Keep telepay-459221 running during entire migration
2. Revert DNS to telepay-459221 services
3. All secrets preserved in telepay-459221 (DO NOT DELETE during migration)
4. Can delete pgp-live secrets and retry migration

---

## Part 8: Next Steps

1. ✅ Review this checklist with user
2. ⏳ Update SECRET_SCHEME.md with correct naming
3. ⏳ Create automated migration scripts:
   - `migrate_secret_names_in_code.sh` - Update code references
   - `create_pgp_live_secrets.sh` - Create secrets in pgp-live
4. ⏳ Test secret name changes locally
5. ⏳ Deploy to pgp-live staging environment
6. ⏳ Full migration to pgp-live production

---

**End of Checklist**

**Total Secrets:** 77 (75 existing + 2 new)
**Name Changes Required:** 32 secrets
**Value Updates Required:** ~50 secrets (URLs, queue names, database, project ID)
**Code Files Impacted:** ~30+ config/cloudtasks files
**Estimated Migration Time:** 8-12 hours for code updates + secret creation
