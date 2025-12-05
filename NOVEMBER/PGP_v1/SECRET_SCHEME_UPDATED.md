# Secret Manager Configuration - PGP_v1 Complete Reference

**Project:** PayGatePrime (PGP_v1)
**Target Environment:** pgp-live (Google Cloud Project)
**Database:** pgp-live-psql / pgp-live-db
**Last Updated:** 2025-11-18
**Status:** 🔒 READY FOR DEPLOYMENT

---

## 📋 TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Complete Secret Inventory by Category](#complete-secret-inventory-by-category)
3. [Service-to-Secret Dependency Matrix](#service-to-secret-dependency-matrix)
4. [Hot-Reload Classification & Rationale](#hot-reload-classification--rationale)
5. [Security Risk Ratings](#security-risk-ratings)
6. [Naming Conventions & Standards](#naming-conventions--standards)
7. [Value Formats & Generation](#value-formats--generation)
8. [Deployment Checklist](#deployment-checklist)
9. [Secret Creation Commands](#secret-creation-commands)
10. [Troubleshooting & Reference](#troubleshooting--reference)

---

## EXECUTIVE SUMMARY

### Overview

This document provides the **complete and authoritative reference** for all Google Cloud Secret Manager secrets required to deploy and operate the PayGatePrime (PGP_v1) system in the **pgp-live** project.

### Secret Inventory

| Category | Count | Hot-Reloadable | Static |
|----------|-------|----------------|--------|
| **Database Credentials** | 5 | 0 | 5 |
| **Service URLs** | 14 | 14 | 0 |
| **Cloud Tasks Queues** | 17 | 17 | 0 |
| **Signing & Encryption Keys** | 5 | 0 | 5 |
| **Wallet & Blockchain** | 5 | 4 | 1 |
| **Payment Provider APIs** | 4 | 2 | 2 |
| **Exchange & Pricing APIs** | 1 | 1 | 0 |
| **Email & Communication** | 3 | 3 | 0 |
| **Telegram Bot** | 3 | 2 | 1 |
| **Redis / Nonce Tracking** | 2 | 0 | 2 |
| **Cloud Tasks Infrastructure** | 2 | 0 | 2 |
| **Application Configuration** | 8 | 8 | 0 |
| **TOTAL** | **69** | **51** | **18** |

### Hot-Reload Breakdown

- ✅ **Hot-Reloadable (51 secrets):** Can be rotated without service restart - zero-downtime updates
- ❌ **Static-Only (18 secrets):** Require service restart to take effect - security-critical or infrastructure

### Migration from telepay-459221

**Project Migration:**
- **Old Project:** telepay-459221
- **New Project:** pgp-live
- **Database:** telepaydb → **pgp-live-db**
- **Services:** 17 GC*-10-26 → 15 PGP_*_v1

**Secret Updates Required:**
- **14 service URL values** (new Cloud Run service URLs)
- **17 queue name values** (new Cloud Tasks queue names)
- **5 configuration values** (project ID, connection names, URLs)
- **Secret names:** NO CHANGES (all secret names remain the same)

### Critical Security Notes

🔴 **NEVER commit secrets to version control**
🔴 **NEVER log secret values or lengths**
🔴 **NEVER hot-reload signing keys** (invalidates all tokens)
🔴 **NEVER hot-reload wallet private keys** (controls funds)
🔴 **ALWAYS use Secret Manager** (never hardcode)
🔴 **ALWAYS rotate secrets every 90 days** (except wallet private key)

---

## COMPLETE SECRET INVENTORY BY CATEGORY

### 1. DATABASE CREDENTIALS (5 secrets - ALL STATIC)

| Secret Name | Example Value | Services Using | Hot-Reload | Security Rating |
|-------------|---------------|----------------|------------|-----------------|
| `CLOUD_SQL_CONNECTION_NAME` | `pgp-live:us-central1:pgp-live-psql` | All 15 services | ❌ STATIC | 🔴 CRITICAL |
| `DATABASE_NAME_SECRET` | `pgp-live-db` | All 15 services | ❌ STATIC | 🔴 CRITICAL |
| `DATABASE_USER_SECRET` | `postgres` | All 15 services | ❌ STATIC | 🔴 CRITICAL |
| `DATABASE_PASSWORD_SECRET` | `<64-char random>` | All 15 services | ❌ STATIC | 🔴 CRITICAL |
| ~~`DATABASE_HOST_SECRET`~~ | ~~`34.58.246.248`~~ | ~~PGP_SERVER_v1~~ | DEPRECATED | Remove |

**Implementation:** `PGP_COMMON/config/base_config.py` → `fetch_database_config()` (lines 184-222)

**Why STATIC:**
- Connection pool initialization occurs at service startup
- Hot-reload would require draining all existing connections (disruptive)
- Database credentials rarely change (rotate every 90 days with planned restart)

**Rotation Procedure:**
1. Create new database user with temporary password
2. Update `DATABASE_USER_SECRET` and `DATABASE_PASSWORD_SECRET` in Secret Manager
3. Redeploy all 15 services (rolling deployment, <5 min downtime)
4. Verify all services healthy
5. Delete old database user

**Notes:**
- `DATABASE_HOST_SECRET` is **DEPRECATED** - Cloud SQL Connector uses `CLOUD_SQL_CONNECTION_NAME` (Unix socket connection)
- Remove from PGP_SERVER_v1 config during next deployment

---

### 2. SERVICE URLs (14 secrets - ALL HOT-RELOADABLE)

| Secret Name | Current Value Pattern | Consuming Service(s) | Hot-Reload | Security Rating |
|-------------|----------------------|---------------------|------------|-----------------|
| `PGP_SERVER_URL` | `https://pgp-server-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_WEBAPI_v1, External | ✅ HOT | 🟡 MEDIUM |
| `PGP_WEBAPI_URL` | `https://pgp-webapi-v1-{PROJECT_NUMBER}.us-central1.run.app` | Frontend (future) | ✅ HOT | 🟡 MEDIUM |
| `PGP_NP_IPN_URL` | `https://pgp-np-ipn-v1-{PROJECT_NUMBER}.us-central1.run.app` | NOWPayments webhook | ✅ HOT | 🔴 CRITICAL |
| `PGP_ORCHESTRATOR_URL` | `https://pgp-orchestrator-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_NP_IPN_v1 | ✅ HOT | 🔴 CRITICAL |
| `PGP_INVITE_URL` | `https://pgp-invite-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_ORCHESTRATOR_v1 | ✅ HOT | 🟠 HIGH |
| `PGP_NOTIFICATIONS_URL` | `https://pgp-notifications-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_ORCHESTRATOR_v1 | ✅ HOT | 🟡 MEDIUM |
| `PGP_BATCHPROCESSOR_URL` | `https://pgp-batchprocessor-v1-{PROJECT_NUMBER}.us-central1.run.app` | Cloud Scheduler | ✅ HOT | 🟠 HIGH |
| `PGP_MICROBATCH_URL` | `https://pgp-microbatchprocessor-v1-{PROJECT_NUMBER}.us-central1.run.app` | Cloud Scheduler | ✅ HOT | 🟠 HIGH |
| `PGP_SPLIT1_URL` | `https://pgp-split1-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_ORCHESTRATOR_v1, BATCHPROCESSOR | ✅ HOT | 🟠 HIGH |
| `PGP_SPLIT2_URL` | `https://pgp-split2-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_SPLIT1_v1 | ✅ HOT | 🟠 HIGH |
| `PGP_SPLIT3_URL` | `https://pgp-split3-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_SPLIT1_v1 | ✅ HOT | 🟠 HIGH |
| `PGP_HOSTPAY1_URL` | `https://pgp-hostpay1-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_SPLIT2_v1, SPLIT3 | ✅ HOT | 🟠 HIGH |
| `PGP_HOSTPAY2_URL` | `https://pgp-hostpay2-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_HOSTPAY1_v1 | ✅ HOT | 🟠 HIGH |
| `PGP_HOSTPAY3_URL` | `https://pgp-hostpay3-v1-{PROJECT_NUMBER}.us-central1.run.app` | PGP_HOSTPAY1_v1 | ✅ HOT | 🟠 HIGH |

**Legacy Naming (TO BE UPDATED):**
- ~~`GCACCUMULATOR_URL`~~ → **REMOVED** (service deprecated 2025-11-18)
- ~~`GCBATCHPROCESSOR_URL`~~ → **USE** `PGP_BATCHPROCESSOR_URL`
- ~~`GCNOTIFICATIONSERVICE_URL`~~ → **USE** `PGP_NOTIFICATIONS_URL` (naming inconsistency - fix in code)
- ~~`MICROBATCH_URL`~~ → **USE** `PGP_MICROBATCH_URL`

**Implementation:** All services use `build_secret_path() + fetch_secret_dynamic()` pattern with 60-second TTL cache

**Why HOT-RELOADABLE:**
- Service URLs may change during redeployment (blue/green deployments)
- Emergency traffic rerouting requires immediate URL updates
- No security risk (URLs are public, authentication via HMAC signatures)
- Zero-downtime updates critical for payment processing

**Rotation Procedure:**
1. Deploy new service version (Cloud Run generates new URL)
2. Update secret value in Secret Manager
3. Wait 60 seconds (cache TTL expires)
4. All services automatically fetch new URL
5. Verify service-to-service communication
6. Decommission old service version

**Notes:**
- `{PROJECT_NUMBER}` is replaced with actual pgp-live project number (e.g., 123456789012)
- All URLs follow pattern: `https://pgp-{service}-v1-{PROJECT_NUMBER}.us-central1.run.app`
- IPN webhook URL (`PGP_NP_IPN_URL`) must be registered in NOWPayments dashboard

---

### 3. CLOUD TASKS QUEUE NAMES (17 secrets - ALL HOT-RELOADABLE)

| Secret Name | Queue Name Pattern | Purpose | Hot-Reload | Security Rating |
|-------------|-------------------|---------|------------|-----------------|
| `PGP_ORCHESTRATOR_QUEUE` | `pgp-orchestrator-queue-v1` | Payment orchestration tasks | ✅ HOT | 🟠 HIGH |
| `PGP_INVITE_QUEUE` | `pgp-invite-queue-v1` | Telegram invite tasks | ✅ HOT | 🟠 HIGH |
| `PGP_NOTIFICATIONS_QUEUE` | `pgp-notifications-queue-v1` | Payment notification tasks | ✅ HOT | 🟡 MEDIUM |
| `PGP_BATCHPROCESSOR_QUEUE` | `pgp-batchprocessor-queue-v1` | Batch payout tasks | ✅ HOT | 🟠 HIGH |
| `PGP_SPLIT1_QUEUE` | `pgp-split1-estimate-queue-v1` | Split estimate requests | ✅ HOT | 🟠 HIGH |
| `PGP_SPLIT1_BATCH_QUEUE` | `pgp-split1-batch-queue-v1` | Split batch processing | ✅ HOT | 🟠 HIGH |
| `PGP_SPLIT1_RESPONSE_QUEUE` | `pgp-split1-response-queue-v1` | Split estimate responses | ✅ HOT | 🟠 HIGH |
| `PGP_SPLIT2_ESTIMATE_QUEUE` | `pgp-split2-swap-queue-v1` | USDT→ETH swap requests | ✅ HOT | 🟠 HIGH |
| `PGP_SPLIT3_SWAP_QUEUE` | `pgp-split3-client-queue-v1` | ETH→Client swap requests | ✅ HOT | 🟠 HIGH |
| `PGP_HOSTPAY_TRIGGER_QUEUE` | `pgp-hostpay-trigger-queue-v1` | HostPay orchestration | ✅ HOT | 🟠 HIGH |
| `PGP_HOSTPAY1_BATCH_QUEUE` | `pgp-hostpay1-batch-queue-v1` | HostPay batch processing | ✅ HOT | 🟠 HIGH |
| `PGP_HOSTPAY1_RESPONSE_QUEUE` | `pgp-hostpay1-response-queue-v1` | HostPay payment responses | ✅ HOT | 🟠 HIGH |
| `PGP_HOSTPAY2_STATUS_QUEUE` | `pgp-hostpay2-status-queue-v1` | ChangeNow status checks | ✅ HOT | 🟠 HIGH |
| `PGP_HOSTPAY3_PAYMENT_QUEUE` | `pgp-hostpay3-payment-queue-v1` | ETH payment execution | ✅ HOT | 🟠 HIGH |
| `PGP_HOSTPAY3_RETRY_QUEUE` | `pgp-hostpay3-retry-queue-v1` | Payment retry queue | ✅ HOT | 🟠 HIGH |
| `PGP_MICROBATCH_RESPONSE_QUEUE` | `pgp-microbatch-response-queue-v1` | Microbatch conversion responses | ✅ HOT | 🟠 HIGH |
| ~~`PGP_ACCUMULATOR_QUEUE`~~ | ~~`pgp-accumulator-queue-v1`~~ | **REMOVED** (service deprecated) | N/A | REMOVE |

**Legacy Naming (TO BE UPDATED):**
- ~~`GCACCUMULATOR_QUEUE`~~ → **REMOVED**
- ~~`GCACCUMULATOR_RESPONSE_QUEUE`~~ → **REMOVED**
- ~~`GCBATCHPROCESSOR_QUEUE`~~ → `PGP_BATCHPROCESSOR_QUEUE`
- ~~`GCWEBHOOK1_QUEUE`~~ → `PGP_ORCHESTRATOR_QUEUE`
- ~~`GCWEBHOOK2_QUEUE`~~ → `PGP_INVITE_QUEUE`
- ~~`GCSPLIT1_QUEUE`~~ → `PGP_SPLIT1_QUEUE`
- ~~`GCSPLIT2_QUEUE`~~ → `PGP_SPLIT2_ESTIMATE_QUEUE`
- ~~`GCSPLIT3_QUEUE`~~ → `PGP_SPLIT3_SWAP_QUEUE`
- ~~`GCHOSTPAY1_QUEUE`~~ → `PGP_HOSTPAY_TRIGGER_QUEUE`
- ~~`GCHOSTPAY1_RESPONSE_QUEUE`~~ → `PGP_HOSTPAY1_RESPONSE_QUEUE`
- ~~`GCHOSTPAY2_QUEUE`~~ → `PGP_HOSTPAY2_STATUS_QUEUE`
- ~~`GCHOSTPAY3_QUEUE`~~ → `PGP_HOSTPAY3_PAYMENT_QUEUE`
- ~~`GCHOSTPAY3_RETRY_QUEUE`~~ → `PGP_HOSTPAY3_RETRY_QUEUE`

**Naming Convention:**
```
pgp-{component}-{purpose}-queue-v1
```

**Why HOT-RELOADABLE:**
- Queue names may change for operational reasons (e.g., quota exhaustion, regional migration)
- Allows traffic redirection without service restart
- Emergency queue swaps for incident response

**Rotation Procedure:**
1. Create new Cloud Tasks queue with new name
2. Update secret value in Secret Manager
3. Wait 60 seconds (cache TTL expires)
4. Services automatically enqueue to new queue
5. Drain old queue (wait for all tasks to complete)
6. Delete old queue after 24 hours

---

### 4. SIGNING & ENCRYPTION KEYS (5 secrets - ALL STATIC)

| Secret Name | Length | Usage | Services Using | Hot-Reload | Security Rating |
|-------------|--------|-------|----------------|------------|-----------------|
| `SUCCESS_URL_SIGNING_KEY` | 64-char hex | JWT signing, token encryption | ORCHESTRATOR, INVITE, SPLIT*, HOSTPAY* | ❌ STATIC | 🔴 CRITICAL |
| `TPS_HOSTPAY_SIGNING_KEY` | 64-char hex | HostPay inter-service token signing | SPLIT1, HOSTPAY1, HOSTPAY2, HOSTPAY3 | ❌ STATIC | 🔴 CRITICAL |
| `JWT_SECRET_KEY` | 64-char hex | JWT authentication for WEBAPI | WEBAPI, BROADCAST | ❌ STATIC | 🔴 CRITICAL |
| `SIGNUP_SECRET_KEY` | 64-char hex | Email verification token signing | WEBAPI | ❌ STATIC | 🔴 CRITICAL |
| `PGP_INTERNAL_SIGNING_KEY` | 64-char hex | Future internal service auth | Reserved for future use | ❌ STATIC | 🔴 CRITICAL |

**Generation Command:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Generates: a1b2c3d4e5f6...xyz (64 characters)
```

**Why STATIC (⚠️ CRITICAL):**
- **Token Invalidation:** Hot-reloading invalidates ALL existing tokens/JWTs
- **User Sessions:** Users forced to re-authenticate (bad UX)
- **Payment Tokens:** In-flight payments fail mid-transaction
- **Security Boundary:** These keys define trust boundaries between services

**Rotation Procedure (PLANNED DOWNTIME REQUIRED):**
1. **Schedule Maintenance Window** (2-hour window recommended)
2. **Pre-rotation:**
   - Notify users via Telegram broadcast
   - Disable payment link generation (no new payments)
   - Wait for in-flight payments to complete (monitor queue depth)
3. **Generate new key:**
   ```bash
   NEW_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
   echo -n "$NEW_KEY" | gcloud secrets versions add SUCCESS_URL_SIGNING_KEY --data-file=-
   ```
4. **Redeploy all services using this key** (rolling deployment)
5. **Verify:**
   - Test end-to-end payment flow
   - Check JWT authentication
   - Monitor error rates
6. **Re-enable payment generation**
7. **Post-rotation:**
   - Monitor for 24 hours
   - Disable old secret version after 7 days

**NEVER:**
- ❌ Hot-reload these keys (breaks all existing tokens)
- ❌ Log key values or lengths
- ❌ Share keys between environments (dev vs prod)
- ❌ Commit keys to version control

---

### 5. WALLET & BLOCKCHAIN (5 secrets - MIXED)

| Secret Name | Type | Example Value | Hot-Reload | Security Rating |
|-------------|------|---------------|------------|-----------------|
| `HOST_WALLET_PRIVATE_KEY` | 64-char hex | `72738abc...def8f2e` | ❌ STATIC | 🔴 **ULTRA-CRITICAL** |
| `HOST_WALLET_ETH_ADDRESS` | Ethereum address | `0x16Db...1bc4` | ✅ HOT | 🟠 HIGH |
| `HOST_WALLET_USDT_ADDRESS` | Ethereum address | `0x16Db...1bc4` | ✅ HOT | 🟠 HIGH |
| `ETHEREUM_RPC_URL` | Alchemy/Infura URL | `https://eth-mainnet.g.alchemy.com/v2/{API_KEY}` | ✅ HOT | 🟠 HIGH |
| `ETHEREUM_RPC_URL_API` | API key | `AQB6...Nohb` (32 chars) | ✅ HOT | 🟠 HIGH |

**Why HOST_WALLET_PRIVATE_KEY is STATIC (🔴 ULTRA-CRITICAL):**
- **CONTROLS ALL FUNDS** - This key has signing authority over all ETH/USDT balances
- **NEVER ROTATE** without fund migration plan
- **NEVER LOG** even the length or format
- **NEVER HOT-RELOAD** (would cause signing failures mid-transaction)

**Why wallet addresses are HOT-RELOADABLE:**
- Address rotation for operational security (move funds to new wallet)
- Can be updated without disrupting in-flight transactions
- Services simply read new address from Secret Manager

**Private Key Security Checklist:**
- ✅ Stored in Secret Manager with restricted IAM (2-person rule)
- ✅ Accessed only by HOSTPAY3 (single service)
- ✅ Never logged or printed
- ✅ Separate key for dev/staging/prod
- ✅ Hardware security module (HSM) storage (future upgrade)

**RPC URL Rotation:**
```bash
# Example: Switching from Alchemy to Infura
NEW_RPC="https://mainnet.infura.io/v3/YOUR_NEW_API_KEY"
echo -n "$NEW_RPC" | gcloud secrets versions add ETHEREUM_RPC_URL --data-file=-
# Services auto-reload after 60s
```

---

### 6. PAYMENT PROVIDER APIs (4 secrets - MIXED)

| Secret Name | Length | Provider | Hot-Reload | Security Rating |
|-------------|--------|----------|------------|-----------------|
| `NOWPAYMENTS_API_KEY` | 27-char | NOWPayments | ✅ HOT | 🟠 HIGH |
| `NOWPAYMENTS_IPN_SECRET` | 28-char | NOWPayments | ❌ STATIC | 🔴 CRITICAL |
| `NOWPAYMENTS_IPN_CALLBACK_URL` | URL | NOWPayments | ✅ HOT | 🟠 HIGH |
| ~~`NOWPAYMENT_WEBHOOK_KEY`~~ | 28-char | **DUPLICATE** | DEPRECATED | VERIFY USAGE |

**Why IPN_SECRET is STATIC:**
- Used to verify HMAC signatures on incoming webhooks
- Changing requires coordination with NOWPayments dashboard
- Mid-flight payments would fail signature verification

**Why API_KEY is HOT-RELOADABLE:**
- Used for outbound API calls only
- Rotation doesn't affect webhook verification
- Can rotate immediately if compromised

**Rotation Procedure for API_KEY:**
1. Generate new API key in NOWPayments dashboard
2. Update `NOWPAYMENTS_API_KEY` in Secret Manager
3. Wait 60 seconds (cache TTL)
4. Services auto-reload new key
5. Verify payment link creation works
6. Revoke old API key in dashboard after 24 hours

**Rotation Procedure for IPN_SECRET (REQUIRES COORDINATION):**
1. Contact NOWPayments support to schedule rotation
2. Coordinate timing with NOWPayments team
3. Update `NOWPAYMENTS_IPN_SECRET` in Secret Manager
4. Update IPN secret in NOWPayments dashboard (atomic operation)
5. Redeploy PGP_NP_IPN_v1 service
6. Verify webhook signature validation
7. Monitor for failed IPN deliveries

**Note on NOWPAYMENT_WEBHOOK_KEY:**
- Appears to be duplicate of NOWPAYMENTS_IPN_SECRET
- Verify usage in PGP_NP_IPN_v1
- Remove if confirmed duplicate

---

### 7. EXCHANGE & PRICING APIs (1 secret - HOT-RELOADABLE)

| Secret Name | Provider | Length | Hot-Reload | Security Rating |
|-------------|----------|--------|------------|-----------------|
| `CHANGENOW_API_KEY` | ChangeNow | 64-char hex | ✅ HOT | 🟠 HIGH |

**Services Using:**
- PGP_SPLIT2_v1 (USDT→ETH estimates)
- PGP_HOSTPAY1_v1 (payment orchestration)
- PGP_HOSTPAY2_v1 (status polling)
- PGP_MICROBATCHPROCESSOR_v1 (batch conversions)

**Unused APIs (REMOVE from deployment):**
- ~~`COINGECKO_API_KEY`~~ - CryptoPricingClient uses free tier (no auth)
- ~~`CRYPTOCOMPARE_API_KEY`~~ - Not implemented
- ~~`1INCH_API_KEY`~~ - Not found in codebase

**Why HOT-RELOADABLE:**
- Used only for outbound API calls (estimates, conversions)
- No webhook signature verification
- Immediate rotation if compromised
- Zero impact on in-flight transactions

**Rotation:**
```bash
# Get new API key from ChangeNow dashboard
NEW_KEY="your_new_64char_hex_key"
echo -n "$NEW_KEY" | gcloud secrets versions add CHANGENOW_API_KEY --data-file=-
```

---

### 8. EMAIL & COMMUNICATION (3 secrets - ALL HOT-RELOADABLE)

| Secret Name | Example Value | Usage | Hot-Reload | Security Rating |
|-------------|---------------|-------|------------|-----------------|
| `SENDGRID_API_KEY` | `SG.t...tVs` (69 chars) | Email delivery via SendGrid | ✅ HOT | 🟠 HIGH |
| `FROM_EMAIL` | `noreply@paygateprime.com` | Sender email address | ✅ HOT | 🟢 LOW |
| `FROM_NAME` | `PayGatePrime` | Email sender display name | ✅ HOT | 🟢 LOW |

**Services Using:** PGP_WEBAPI_v1 only

**Why HOT-RELOADABLE:**
- Email settings can change for operational reasons
- No security dependency (no signature verification)
- Immediate rotation if API key compromised

**Rotation Procedure:**
1. Generate new SendGrid API key in dashboard
2. Update secret in Secret Manager
3. Wait 60 seconds
4. Services auto-reload
5. Test email delivery
6. Revoke old API key after 24 hours

---

### 9. TELEGRAM BOT (3 secrets - MIXED)

| Secret Name | Format | Services | Hot-Reload | Security Rating |
|-------------|--------|----------|------------|-----------------|
| `TELEGRAM_BOT_API_TOKEN` | 46-char token | INVITE, BROADCAST, NOTIFICATIONS | ✅ HOT | 🔴 CRITICAL |
| `TELEGRAM_BOT_USERNAME` | `@PayGatePrime_bot` | SERVER, BROADCAST | ✅ HOT | 🟢 LOW |
| ~~`TELEGRAM_BOT_SECRET_NAME`~~ | Secret Manager path | SERVER (legacy) | DEPRECATED | MIGRATE |

**Why BOT_API_TOKEN is HOT-RELOADABLE:**
- Modern services use fetch_secret_dynamic() pattern
- Can rotate immediately if compromised
- Telegram API validates on per-request basis
- No persistent sessions to invalidate

**Why TELEGRAM_BOT_SECRET_NAME is DEPRECATED:**
- PGP_SERVER_v1 uses legacy Secret Manager path format
- Should migrate to TELEGRAM_BOT_API_TOKEN for consistency
- Current implementation: `os.getenv('TELEGRAM_BOT_SECRET_NAME')` → Secret Manager path
- New pattern: `build_secret_path('TELEGRAM_BOT_API_TOKEN')`

**Migration Plan:**
1. Update PGP_SERVER_v1/config_manager.py to use new pattern
2. Update deployment script to inject TELEGRAM_BOT_API_TOKEN
3. Redeploy PGP_SERVER_v1
4. Verify bot functionality
5. Remove TELEGRAM_BOT_SECRET_NAME secret after 7 days

**Rotation Procedure:**
1. Revoke current bot token via BotFather (@BotFather on Telegram)
2. Generate new token via BotFather
3. Update `TELEGRAM_BOT_API_TOKEN` in Secret Manager
4. Wait 60 seconds (cache TTL)
5. Services auto-reload new token
6. Verify bot responds to commands

---

### 10. REDIS / NONCE TRACKING (2 secrets - STATIC)

| Secret Name | Example Value | Usage | Hot-Reload | Security Rating |
|-------------|---------------|-------|------------|-----------------|
| `PGP_REDIS_HOST` | `10.0.0.3` (internal IP) | Redis connection for replay attack prevention | ❌ STATIC | 🔴 CRITICAL |
| `PGP_REDIS_PORT` | `6379` | Redis port | ❌ STATIC | 🟡 MEDIUM |

**Implementation:** Security Fix C-02 (Replay Attack Prevention)

**Services Using:**
- PGP_ORCHESTRATOR_v1 (nonce tracking for payment requests)
- PGP_INVITE_v1 (nonce tracking for invite tokens)
- Future: All services receiving HMAC-authenticated requests

**Why STATIC:**
- Redis connection pool initialized at service startup
- Hot-reload would require draining connection pool
- Rare changes (infrastructure-level configuration)

**Infrastructure:**
- Google Cloud Memorystore (managed Redis)
- VPC-native connection (internal IP only)
- M1 instance (1GB memory) - ~$50/month
- Automatic failover with Standard tier (future upgrade)

**Rotation Procedure (INFRASTRUCTURE CHANGE):**
1. Provision new Redis instance
2. Update secrets in Secret Manager
3. Redeploy all services using Redis
4. Verify nonce tracking works
5. Migrate data from old to new instance (if needed)
6. Decommission old instance after 7 days

---

### 11. CLOUD TASKS INFRASTRUCTURE (2 secrets - STATIC)

| Secret Name | Example Value | Usage | Hot-Reload | Security Rating |
|-------------|---------------|-------|------------|-----------------|
| `CLOUD_TASKS_PROJECT_ID` | `pgp-live` | GCP project for Cloud Tasks | ❌ STATIC | 🟠 HIGH |
| `CLOUD_TASKS_LOCATION` | `us-central1` | Cloud Tasks region | ❌ STATIC | 🟡 MEDIUM |

**Services Using:** All services that enqueue tasks

**Why STATIC:**
- Infrastructure-level configuration
- Changing project ID requires complete redeploy
- Region changes require queue migration

**Note:** These are configuration values, not security secrets, but stored in Secret Manager for consistency

---

### 12. APPLICATION CONFIGURATION (8 secrets - ALL HOT-RELOADABLE)

| Secret Name | Default Value | Usage | Hot-Reload | Security Rating |
|-------------|---------------|-------|------------|-----------------|
| `BASE_URL` | `https://www.paygateprime.com` | Frontend base URL | ✅ HOT | 🟢 LOW |
| `CORS_ORIGIN` | `https://www.paygateprime.com` | CORS allowed origin | ✅ HOT | 🟡 MEDIUM |
| `TP_FLAT_FEE` | `3` | TelePay fee percentage | ✅ HOT | 🟢 LOW |
| `PAYMENT_MIN_TOLERANCE` | `0.50` | Minimum payment tolerance (50%) | ✅ HOT | 🟡 MEDIUM |
| `PAYMENT_FALLBACK_TOLERANCE` | `0.75` | Fallback tolerance (75%) | ✅ HOT | 🟡 MEDIUM |
| `MICRO_BATCH_THRESHOLD_USD` | `5.00` | Microbatch conversion threshold | ✅ HOT | 🟢 LOW |
| `BROADCAST_AUTO_INTERVAL` | `24.0` | Automated broadcast interval (hours) | ✅ HOT | 🟢 LOW |
| `BROADCAST_MANUAL_INTERVAL` | `0.0833` | Manual broadcast cooldown (5 min) | ✅ HOT | 🟢 LOW |

**Why HOT-RELOADABLE:**
- Operational tuning parameters
- Need to adjust without service restart
- No security implications
- Business logic configuration

**Rotation (ADJUSTMENT):**
```bash
# Example: Increase microbatch threshold to $10 USD
echo -n "10.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=-
# Services reload after 60s, new threshold applies immediately
```

---

## SERVICE-TO-SECRET DEPENDENCY MATRIX

### Complete Dependency Table

| Service | Database (5) | Service URLs (14) | Queues (17) | Signing (5) | Wallet (5) | APIs (8) | Config (8) | **Total Secrets** |
|---------|--------------|------------------|-------------|-------------|------------|----------|------------|-------------------|
| **PGP_SERVER_v1** | 5 | 1 | 0 | 0 | 0 | 1 | 3 | **10** |
| **PGP_WEBAPI_v1** | 5 | 1 | 0 | 2 | 0 | 3 | 2 | **13** |
| **PGP_NP_IPN_v1** | 5 | 2 | 2 | 0 | 0 | 3 | 2 | **14** |
| **PGP_ORCHESTRATOR_v1** | 5 | 3 | 3 | 1 | 0 | 2 | 3 | **17** |
| **PGP_INVITE_v1** | 5 | 0 | 0 | 1 | 0 | 1 | 2 | **9** |
| **PGP_SPLIT1_v1** | 5 | 3 | 4 | 2 | 0 | 0 | 1 | **15** |
| **PGP_SPLIT2_v1** | 5 | 2 | 2 | 1 | 0 | 1 | 0 | **11** |
| **PGP_SPLIT3_v1** | 5 | 2 | 2 | 1 | 0 | 0 | 0 | **10** |
| **PGP_HOSTPAY1_v1** | 5 | 4 | 3 | 1 | 0 | 1 | 0 | **14** |
| **PGP_HOSTPAY2_v1** | 5 | 2 | 1 | 1 | 0 | 1 | 0 | **10** |
| **PGP_HOSTPAY3_v1** | 5 | 2 | 2 | 1 | 5 | 0 | 0 | **15** |
| **PGP_BATCHPROCESSOR_v1** | 5 | 1 | 1 | 0 | 0 | 0 | 1 | **8** |
| **PGP_MICROBATCHPROCESSOR_v1** | 5 | 0 | 1 | 0 | 0 | 1 | 1 | **8** |
| **PGP_NOTIFICATIONS_v1** | 5 | 0 | 0 | 0 | 0 | 1 | 0 | **6** |
| **PGP_BROADCAST_v1** | 5 | 0 | 0 | 1 | 0 | 1 | 2 | **9** |

### Secrets Shared Across All Services

**Universal Secrets (used by all 15 services):**
1. `CLOUD_SQL_CONNECTION_NAME`
2. `DATABASE_NAME_SECRET`
3. `DATABASE_USER_SECRET`
4. `DATABASE_PASSWORD_SECRET`

### Critical Path Secrets (Payment Flow)

**User → Payment → Invite Flow:**
```
User Payment Initiated
↓ [TELEGRAM_BOT_API_TOKEN]
PGP_SERVER_v1
↓ [NOWPAYMENTS_API_KEY]
NOWPayments Gateway
↓ [NOWPAYMENTS_IPN_SECRET]
PGP_NP_IPN_v1
↓ [PGP_ORCHESTRATOR_URL + PGP_ORCHESTRATOR_QUEUE]
PGP_ORCHESTRATOR_v1
↓ [SUCCESS_URL_SIGNING_KEY + PGP_INVITE_URL + PGP_INVITE_QUEUE]
PGP_INVITE_v1
↓ [TELEGRAM_BOT_API_TOKEN]
User Receives Invite Link
```

**Payment → Payout Flow:**
```
Threshold Detected (≥$50 USD)
↓ [PGP_SPLIT1_URL + PGP_SPLIT1_QUEUE]
PGP_SPLIT1_v1
↓ [PGP_SPLIT2_URL + PGP_SPLIT2_ESTIMATE_QUEUE + CHANGENOW_API_KEY]
PGP_SPLIT2_v1 (USDT→ETH estimate)
↓ [PGP_SPLIT3_URL + PGP_SPLIT3_SWAP_QUEUE]
PGP_SPLIT3_v1 (ETH→Client currency)
↓ [PGP_HOSTPAY1_URL + PGP_HOSTPAY_TRIGGER_QUEUE + TPS_HOSTPAY_SIGNING_KEY]
PGP_HOSTPAY1_v1
↓ [PGP_HOSTPAY2_URL + PGP_HOSTPAY2_STATUS_QUEUE + CHANGENOW_API_KEY]
PGP_HOSTPAY2_v1 (status polling)
↓ [PGP_HOSTPAY3_URL + PGP_HOSTPAY3_PAYMENT_QUEUE + HOST_WALLET_PRIVATE_KEY]
PGP_HOSTPAY3_v1 (ETH payment execution)
↓ [HOST_WALLET_ETH_ADDRESS + ETHEREUM_RPC_URL]
Blockchain Transaction
```

---

## HOT-RELOAD CLASSIFICATION & RATIONALE

### Static-Only Secrets (18 secrets) - Require Service Restart

| Secret | Category | Why STATIC |
|--------|----------|------------|
| **Database Credentials (5)** | Infrastructure | Connection pool initialization |
| `CLOUD_SQL_CONNECTION_NAME` | Infrastructure | Connection pool uses Unix socket |
| `DATABASE_NAME_SECRET` | Infrastructure | Connection pool initialization |
| `DATABASE_USER_SECRET` | Infrastructure | Connection pool authentication |
| `DATABASE_PASSWORD_SECRET` | Infrastructure | Connection pool authentication |
| **Signing Keys (5)** | Security | Token invalidation |
| `SUCCESS_URL_SIGNING_KEY` | Security | Invalidates all payment tokens |
| `TPS_HOSTPAY_SIGNING_KEY` | Security | Invalidates all HostPay tokens |
| `JWT_SECRET_KEY` | Security | Invalidates all user sessions |
| `SIGNUP_SECRET_KEY` | Security | Invalidates all email verification tokens |
| `PGP_INTERNAL_SIGNING_KEY` | Security | Future internal service auth |
| **Wallet Private Key (1)** | Ultra-Critical | Controls all funds |
| `HOST_WALLET_PRIVATE_KEY` | Ultra-Critical | Signing authority for blockchain txs |
| **Payment Webhooks (2)** | Security | Webhook signature verification |
| `NOWPAYMENTS_IPN_SECRET` | Security | HMAC signature verification |
| ~~`TELEGRAM_BOT_SECRET_NAME`~~ | Legacy | Deprecated - migrate to hot-reload |
| **Redis Infrastructure (2)** | Infrastructure | Connection pool initialization |
| `PGP_REDIS_HOST` | Infrastructure | Redis connection pool |
| `PGP_REDIS_PORT` | Infrastructure | Redis connection pool |
| **Cloud Tasks (2)** | Infrastructure | Infrastructure-level config |
| `CLOUD_TASKS_PROJECT_ID` | Infrastructure | GCP project |
| `CLOUD_TASKS_LOCATION` | Infrastructure | Cloud Tasks region |

### Hot-Reloadable Secrets (51 secrets) - Zero-Downtime Updates

| Category | Count | Rationale |
|----------|-------|-----------|
| **Service URLs** | 14 | Blue/green deployments, traffic routing |
| **Cloud Tasks Queues** | 17 | Queue migration, operational flexibility |
| **Wallet Addresses** | 2 | Fund migration, operational security |
| **Ethereum RPC** | 2 | Provider switching (Alchemy → Infura) |
| **API Keys** | 3 | Outbound calls only, no signature verification |
| **Email Config** | 3 | Operational settings |
| **Telegram Bot** | 2 | Modern fetch_secret_dynamic() pattern |
| **Application Config** | 8 | Business logic tuning |

---

## SECURITY RISK RATINGS

### 🔴 ULTRA-CRITICAL (1 secret)

| Secret | Impact if Compromised | Mitigation |
|--------|----------------------|------------|
| `HOST_WALLET_PRIVATE_KEY` | **TOTAL FUND LOSS** - Attacker can drain all ETH/USDT | 2-person access rule, HSM storage (future), never log |

### 🔴 CRITICAL (12 secrets)

| Secret | Impact if Compromised |
|--------|----------------------|
| Database Credentials (4) | Full database access, PII exposure, financial data theft |
| Signing Keys (4) | Token forgery, unauthorized payments, session hijacking |
| `NOWPAYMENTS_IPN_SECRET` | Payment spoofing, fake payment confirmations |
| `PGP_NP_IPN_URL` | Payment flow disruption (if attacker changes URL) |
| `PGP_ORCHESTRATOR_URL` | Payment processing bypass |
| `TELEGRAM_BOT_API_TOKEN` | Bot takeover, spam, phishing |
| `PGP_REDIS_HOST` | Nonce tracking bypass, replay attacks |

### 🟠 HIGH (23 secrets)

| Category | Impact if Compromised |
|----------|----------------------|
| Service URLs (11) | Service impersonation, traffic interception |
| Queue Names (10) | Task injection, workflow disruption |
| `CHANGENOW_API_KEY` | Unauthorized exchange API usage, rate limit exhaustion |
| `SENDGRID_API_KEY` | Email spoofing, phishing campaigns |

### 🟡 MEDIUM (25 secrets)

| Category | Impact if Compromised |
|----------|----------------------|
| Queue Names (7) | Limited workflow disruption |
| `CORS_ORIGIN` | CORS bypass (if wildcard introduced) |
| `PAYMENT_MIN_TOLERANCE` | Payment validation bypass |
| `PAYMENT_FALLBACK_TOLERANCE` | Payment validation bypass |
| `CLOUD_TASKS_PROJECT_ID` | Configuration confusion |

### 🟢 LOW (8 secrets)

| Category | Impact if Compromised |
|----------|----------------------|
| Application Config (6) | Operational disruption, no security risk |
| `FROM_EMAIL` | Cosmetic email changes |
| `FROM_NAME` | Cosmetic email changes |

---

## NAMING CONVENTIONS & STANDARDS

### Current Naming Pattern

**Service URLs:**
```
PGP_{SERVICE}_URL
Examples: PGP_ORCHESTRATOR_URL, PGP_SPLIT1_URL
```

**Queue Names:**
```
PGP_{SERVICE}_{PURPOSE}_QUEUE
Examples: PGP_SPLIT1_BATCH_QUEUE, PGP_HOSTPAY3_RETRY_QUEUE
```

**API Keys:**
```
{PROVIDER}_{KEY_TYPE}
Examples: NOWPAYMENTS_API_KEY, CHANGENOW_API_KEY
```

**Infrastructure:**
```
{COMPONENT}_{PROPERTY}
Examples: DATABASE_NAME_SECRET, CLOUD_SQL_CONNECTION_NAME
```

### Naming Inconsistencies to Fix

| Current Name (WRONG) | Correct Name (RIGHT) | Location | Priority |
|---------------------|---------------------|----------|----------|
| ~~`GCNOTIFICATIONSERVICE_URL`~~ | `PGP_NOTIFICATIONS_URL` | PGP_NP_IPN_v1:184 | 🔴 HIGH |
| ~~`TELEGRAM_BOT_SECRET_NAME`~~ | `TELEGRAM_BOT_API_TOKEN` | PGP_SERVER_v1 | 🟠 MEDIUM |
| ~~`NOWPAYMENT_WEBHOOK_KEY`~~ | Verify duplicate → Remove | All services | 🟡 LOW |
| ~~`DATABASE_HOST_SECRET`~~ | Remove (use Cloud SQL Connector) | PGP_SERVER_v1 | 🟡 LOW |
| ~~Legacy GC* prefixes~~ | Update to PGP_* | Documentation | 🟢 LOW |

### Secret Naming Rules

✅ **DO:**
- Use UPPER_CASE_SNAKE_CASE
- Prefix with service/component name
- Suffix with _SECRET, _KEY, _URL, _QUEUE as appropriate
- Be descriptive (avoid abbreviations)

❌ **DON'T:**
- Use camelCase or lowercase
- Mix naming conventions
- Use generic names (SECRET1, KEY_A)
- Include version numbers (handled by Secret Manager versions)

---

## VALUE FORMATS & GENERATION

### Hex Keys (64 characters)

**Used for:** Signing keys, encryption keys, private keys

**Generation:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Output: a1b2c3d4e5f6789012345678901234567890abcdefabcdef1234567890abcd
```

**Example Secrets:**
- `SUCCESS_URL_SIGNING_KEY`
- `TPS_HOSTPAY_SIGNING_KEY`
- `JWT_SECRET_KEY`
- `SIGNUP_SECRET_KEY`
- `HOST_WALLET_PRIVATE_KEY`
- `CHANGENOW_API_KEY`

### URLs

**Cloud Run Service URLs:**
```
https://pgp-{service}-v1-{PROJECT_NUMBER}.us-central1.run.app
```

**Example:**
```
https://pgp-orchestrator-v1-123456789012.us-central1.run.app
```

**Get Project Number:**
```bash
gcloud projects describe pgp-live --format='value(projectNumber)'
```

### Queue Names

**Pattern:**
```
pgp-{component}-{purpose}-queue-v1
```

**Examples:**
```
pgp-split1-estimate-queue-v1
pgp-hostpay3-retry-queue-v1
pgp-orchestrator-queue-v1
```

### Database Connection

**Cloud SQL Connection Name:**
```
{PROJECT_ID}:{REGION}:{INSTANCE_NAME}
Example: pgp-live:us-central1:pgp-live-psql
```

**Database Name:**
```
pgp-live-db
```

### Boolean Values

**Format:** Lowercase string
```
true
false
```

### Numeric Values

**Format:** String representation
```
24         # Integer
0.0833     # Float
5.00       # Float with decimal
```

---

## DEPLOYMENT CHECKLIST

### Pre-Deployment

- [ ] Review all 69 secrets in this document
- [ ] Verify project ID: `pgp-live`
- [ ] Verify database name: `pgp-live-db`
- [ ] Generate all new signing keys (5 keys)
- [ ] Obtain API keys from providers (NOWPayments, ChangeNow, SendGrid, Telegram)
- [ ] Document current wallet private key location (ultra-secure storage)
- [ ] Create Secret Manager service account with restricted IAM
- [ ] Enable Secret Manager API in pgp-live project

### Deployment Phases

**Phase 1: Infrastructure Secrets (9 secrets)**
- [ ] `CLOUD_SQL_CONNECTION_NAME` = `pgp-live:us-central1:pgp-live-psql`
- [ ] `DATABASE_NAME_SECRET` = `pgp-live-db`
- [ ] `DATABASE_USER_SECRET` = `postgres`
- [ ] `DATABASE_PASSWORD_SECRET` = `<generate-64-char-hex>`
- [ ] `CLOUD_TASKS_PROJECT_ID` = `pgp-live`
- [ ] `CLOUD_TASKS_LOCATION` = `us-central1`
- [ ] `PGP_REDIS_HOST` = `<Memorystore-internal-IP>`
- [ ] `PGP_REDIS_PORT` = `6379`

**Phase 2: Security Secrets (10 secrets)**
- [ ] `SUCCESS_URL_SIGNING_KEY` = `<generate-64-char-hex>`
- [ ] `TPS_HOSTPAY_SIGNING_KEY` = `<generate-64-char-hex>`
- [ ] `JWT_SECRET_KEY` = `<generate-64-char-hex>`
- [ ] `SIGNUP_SECRET_KEY` = `<generate-64-char-hex>`
- [ ] `PGP_INTERNAL_SIGNING_KEY` = `<generate-64-char-hex>`
- [ ] `HOST_WALLET_PRIVATE_KEY` = `<secure-migration-from-telepay-459221>`
- [ ] `HOST_WALLET_ETH_ADDRESS` = `0x16Db...1bc4`
- [ ] `HOST_WALLET_USDT_ADDRESS` = `0x16Db...1bc4`
- [ ] `NOWPAYMENTS_IPN_SECRET` = `<from-NOWPayments-dashboard>`
- [ ] `TELEGRAM_BOT_API_TOKEN` = `<from-BotFather>`

**Phase 3: Service URLs (14 secrets)**

Deploy all Cloud Run services first, then capture URLs:
```bash
# Example script to get all service URLs
PROJECT_NUM=$(gcloud projects describe pgp-live --format='value(projectNumber)')

for service in server webapi np-ipn orchestrator invite notifications \
                batchprocessor microbatchprocessor \
                split1 split2 split3 \
                hostpay1 hostpay2 hostpay3; do
  URL="https://pgp-${service}-v1-${PROJECT_NUM}.us-central1.run.app"
  SECRET_NAME="PGP_${service^^}_URL"  # Convert to uppercase
  echo -n "$URL" | gcloud secrets create "$SECRET_NAME" --data-file=- --project=pgp-live
done
```

**Phase 4: Cloud Tasks Queues (17 secrets)**

Deploy all queues first, then store queue names:
```bash
# Queue names follow pattern: pgp-{component}-{purpose}-queue-v1
# See section 3 for complete list
```

**Phase 5: API Keys (4 secrets)**
- [ ] `NOWPAYMENTS_API_KEY` = `<from-NOWPayments-dashboard>`
- [ ] `CHANGENOW_API_KEY` = `<from-ChangeNow-dashboard>`
- [ ] `SENDGRID_API_KEY` = `<from-SendGrid-dashboard>`
- [ ] `ETHEREUM_RPC_URL` = `https://eth-mainnet.g.alchemy.com/v2/{API_KEY}`
- [ ] `ETHEREUM_RPC_URL_API` = `<Alchemy-API-key>`

**Phase 6: Application Configuration (11 secrets)**
- [ ] `BASE_URL` = `https://www.paygateprime.com`
- [ ] `CORS_ORIGIN` = `https://www.paygateprime.com`
- [ ] `NOWPAYMENTS_IPN_CALLBACK_URL` = `<PGP_NP_IPN_URL>`
- [ ] `FROM_EMAIL` = `noreply@paygateprime.com`
- [ ] `FROM_NAME` = `PayGatePrime`
- [ ] `TELEGRAM_BOT_USERNAME` = `@PayGatePrime_bot`
- [ ] `TP_FLAT_FEE` = `3`
- [ ] `PAYMENT_MIN_TOLERANCE` = `0.50`
- [ ] `PAYMENT_FALLBACK_TOLERANCE` = `0.75`
- [ ] `MICRO_BATCH_THRESHOLD_USD` = `5.00`
- [ ] `BROADCAST_AUTO_INTERVAL` = `24.0`
- [ ] `BROADCAST_MANUAL_INTERVAL` = `0.0833`

### Post-Deployment Validation

- [ ] Test database connectivity from all 15 services
- [ ] Verify all service URLs respond with 200/503 (health checks)
- [ ] Test payment flow end-to-end (NOWPayments → IPN → Orchestrator → Invite)
- [ ] Verify signature validation (HMAC, JWT, token decryption)
- [ ] Test hot-reload (update a config secret, verify auto-reload)
- [ ] Monitor logs for secret access errors
- [ ] Verify queue task enqueueing and processing
- [ ] Test email delivery (SendGrid)
- [ ] Test Telegram bot commands
- [ ] Verify blockchain transaction signing (test wallet)

### Security Validation

- [ ] Audit IAM permissions (principle of least privilege)
- [ ] Verify 2-person access rule for `HOST_WALLET_PRIVATE_KEY`
- [ ] Check Secret Manager audit logs
- [ ] Verify no secrets in environment variables (Cloud Run UI)
- [ ] Confirm HTTPS-only access to all services
- [ ] Test IP whitelisting (PGP_SERVER_v1)
- [ ] Verify rate limiting active
- [ ] Test nonce tracking (Redis connectivity)

---

## SECRET CREATION COMMANDS

### Batch Create All Secrets

```bash
#!/bin/bash
# create_all_secrets.sh
# Creates all 69 secrets in pgp-live project

PROJECT="pgp-live"

echo "🔐 Creating secrets for project: $PROJECT"

# Phase 1: Infrastructure (9 secrets)
echo "📦 Phase 1: Infrastructure Secrets"

echo -n "pgp-live:us-central1:pgp-live-psql" | gcloud secrets create CLOUD_SQL_CONNECTION_NAME --data-file=- --project=$PROJECT
echo -n "pgp-live-db" | gcloud secrets create DATABASE_NAME_SECRET --data-file=- --project=$PROJECT
echo -n "postgres" | gcloud secrets create DATABASE_USER_SECRET --data-file=- --project=$PROJECT

# Generate database password
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo -n "$DB_PASSWORD" | gcloud secrets create DATABASE_PASSWORD_SECRET --data-file=- --project=$PROJECT
echo "✅ Generated DATABASE_PASSWORD_SECRET: ${DB_PASSWORD:0:8}...${DB_PASSWORD: -8}"

echo -n "pgp-live" | gcloud secrets create CLOUD_TASKS_PROJECT_ID --data-file=- --project=$PROJECT
echo -n "us-central1" | gcloud secrets create CLOUD_TASKS_LOCATION --data-file=- --project=$PROJECT

# Redis (requires Memorystore provisioning first)
read -p "Enter Redis host IP (Memorystore internal IP): " REDIS_HOST
echo -n "$REDIS_HOST" | gcloud secrets create PGP_REDIS_HOST --data-file=- --project=$PROJECT
echo -n "6379" | gcloud secrets create PGP_REDIS_PORT --data-file=- --project=$PROJECT

# Phase 2: Security Secrets (10 secrets)
echo "🔒 Phase 2: Security Secrets (Signing Keys)"

# Generate signing keys
SUCCESS_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
TPS_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
JWT_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
SIGNUP_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
INTERNAL_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo -n "$SUCCESS_KEY" | gcloud secrets create SUCCESS_URL_SIGNING_KEY --data-file=- --project=$PROJECT
echo -n "$TPS_KEY" | gcloud secrets create TPS_HOSTPAY_SIGNING_KEY --data-file=- --project=$PROJECT
echo -n "$JWT_KEY" | gcloud secrets create JWT_SECRET_KEY --data-file=- --project=$PROJECT
echo -n "$SIGNUP_KEY" | gcloud secrets create SIGNUP_SECRET_KEY --data-file=- --project=$PROJECT
echo -n "$INTERNAL_KEY" | gcloud secrets create PGP_INTERNAL_SIGNING_KEY --data-file=- --project=$PROJECT

echo "✅ Generated 5 signing keys (64-char hex each)"

# Wallet secrets (MANUAL INPUT REQUIRED)
echo "⚠️  ULTRA-CRITICAL: Wallet Private Key"
read -sp "Enter HOST_WALLET_PRIVATE_KEY (64-char hex): " WALLET_KEY
echo
echo -n "$WALLET_KEY" | gcloud secrets create HOST_WALLET_PRIVATE_KEY --data-file=- --project=$PROJECT
echo "✅ Created HOST_WALLET_PRIVATE_KEY (NEVER log this value)"

read -p "Enter HOST_WALLET_ETH_ADDRESS (0x...): " ETH_ADDR
echo -n "$ETH_ADDR" | gcloud secrets create HOST_WALLET_ETH_ADDRESS --data-file=- --project=$PROJECT

read -p "Enter HOST_WALLET_USDT_ADDRESS (0x...): " USDT_ADDR
echo -n "$USDT_ADDR" | gcloud secrets create HOST_WALLET_USDT_ADDRESS --data-file=- --project=$PROJECT

# External API secrets (MANUAL INPUT REQUIRED)
read -p "Enter NOWPAYMENTS_IPN_SECRET (28-char from dashboard): " NP_IPN
echo -n "$NP_IPN" | gcloud secrets create NOWPAYMENTS_IPN_SECRET --data-file=- --project=$PROJECT

read -p "Enter TELEGRAM_BOT_API_TOKEN (46-char from BotFather): " TG_TOKEN
echo -n "$TG_TOKEN" | gcloud secrets create TELEGRAM_BOT_API_TOKEN --data-file=- --project=$PROJECT

# Phase 3: Service URLs (14 secrets) - AFTER service deployment
echo "🌐 Phase 3: Service URLs (create AFTER deploying Cloud Run services)"
echo "   Run: ./create_service_url_secrets.sh"

# Phase 4: Queue Names (17 secrets) - AFTER queue deployment
echo "📮 Phase 4: Cloud Tasks Queues (create AFTER deploying queues)"
echo "   Run: ./create_queue_name_secrets.sh"

# Phase 5: API Keys (MANUAL INPUT REQUIRED)
echo "🔑 Phase 5: External API Keys"

read -p "Enter NOWPAYMENTS_API_KEY (27-char): " NP_API
echo -n "$NP_API" | gcloud secrets create NOWPAYMENTS_API_KEY --data-file=- --project=$PROJECT

read -p "Enter CHANGENOW_API_KEY (64-char hex): " CN_API
echo -n "$CN_API" | gcloud secrets create CHANGENOW_API_KEY --data-file=- --project=$PROJECT

read -p "Enter SENDGRID_API_KEY (69-char): " SG_API
echo -n "$SG_API" | gcloud secrets create SENDGRID_API_KEY --data-file=- --project=$PROJECT

read -p "Enter ETHEREUM_RPC_URL (Alchemy full URL): " ETH_RPC
echo -n "$ETH_RPC" | gcloud secrets create ETHEREUM_RPC_URL --data-file=- --project=$PROJECT

read -p "Enter ETHEREUM_RPC_URL_API (Alchemy API key only): " ETH_API
echo -n "$ETH_API" | gcloud secrets create ETHEREUM_RPC_URL_API --data-file=- --project=$PROJECT

# Phase 6: Application Configuration (11 secrets)
echo "⚙️  Phase 6: Application Configuration"

echo -n "https://www.paygateprime.com" | gcloud secrets create BASE_URL --data-file=- --project=$PROJECT
echo -n "https://www.paygateprime.com" | gcloud secrets create CORS_ORIGIN --data-file=- --project=$PROJECT
echo -n "noreply@paygateprime.com" | gcloud secrets create FROM_EMAIL --data-file=- --project=$PROJECT
echo -n "PayGatePrime" | gcloud secrets create FROM_NAME --data-file=- --project=$PROJECT
echo -n "@PayGatePrime_bot" | gcloud secrets create TELEGRAM_BOT_USERNAME --data-file=- --project=$PROJECT
echo -n "3" | gcloud secrets create TP_FLAT_FEE --data-file=- --project=$PROJECT
echo -n "0.50" | gcloud secrets create PAYMENT_MIN_TOLERANCE --data-file=- --project=$PROJECT
echo -n "0.75" | gcloud secrets create PAYMENT_FALLBACK_TOLERANCE --data-file=- --project=$PROJECT
echo -n "5.00" | gcloud secrets create MICRO_BATCH_THRESHOLD_USD --data-file=- --project=$PROJECT
echo -n "24.0" | gcloud secrets create BROADCAST_AUTO_INTERVAL --data-file=- --project=$PROJECT
echo -n "0.0833" | gcloud secrets create BROADCAST_MANUAL_INTERVAL --data-file=- --project=$PROJECT

# NOWPAYMENTS_IPN_CALLBACK_URL (after PGP_NP_IPN_v1 deployment)
read -p "Enter NOWPAYMENTS_IPN_CALLBACK_URL (full URL): " NP_CALLBACK
echo -n "$NP_CALLBACK" | gcloud secrets create NOWPAYMENTS_IPN_CALLBACK_URL --data-file=- --project=$PROJECT

echo ""
echo "✅ Secret creation complete!"
echo "📊 Created secrets in phases 1, 2, 5, 6"
echo "⏳ Still needed: Service URLs (phase 3), Queue Names (phase 4)"
echo ""
echo "Next steps:"
echo "  1. Deploy Cloud Run services"
echo "  2. Run: ./create_service_url_secrets.sh"
echo "  3. Deploy Cloud Tasks queues"
echo "  4. Run: ./create_queue_name_secrets.sh"
echo "  5. Grant service account access: ./grant_secret_access.sh"
```

### Grant Service Account Access

```bash
#!/bin/bash
# grant_secret_access.sh
# Grants service account access to all secrets

PROJECT="pgp-live"
SERVICE_ACCOUNT="<SERVICE_ACCOUNT_EMAIL>"

echo "🔐 Granting secret access to: $SERVICE_ACCOUNT"

# Get all secret names
SECRETS=$(gcloud secrets list --project=$PROJECT --format='value(name)')

for secret in $SECRETS; do
  echo "  Granting access to: $secret"
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT
done

echo "✅ Access granted to all secrets"
```

---

## TROUBLESHOOTING & REFERENCE

### Common Issues

**Issue: Service can't access secret**
```
Error: Permission denied on secret 'projects/123/secrets/DATABASE_NAME_SECRET'
```

**Solution:**
```bash
# Grant service account access
gcloud secrets add-iam-policy-binding DATABASE_NAME_SECRET \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@pgp-live.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=pgp-live
```

**Issue: Hot-reload not working**
```
Error: Old secret value still in use after update
```

**Solution:**
```
Wait 60 seconds for cache TTL to expire
BaseConfigManager uses 60-second TTL for hot-reloadable secrets
```

**Issue: Secret value has trailing newline**
```
Error: Invalid database password (extra character)
```

**Solution:**
```bash
# Always use echo -n (no newline)
echo -n "value" | gcloud secrets create SECRET_NAME --data-file=-
# NOT: echo "value" (adds newline)
```

**Issue: Signing key rotation breaks tokens**
```
Error: Invalid token signature
```

**Solution:**
```
This is EXPECTED for signing keys (they are STATIC)
Rotating signing keys requires planned downtime
See section 4 for rotation procedure
```

### Quick Reference Commands

**List all secrets:**
```bash
gcloud secrets list --project=pgp-live
```

**Get secret value:**
```bash
gcloud secrets versions access latest --secret=SECRET_NAME --project=pgp-live
```

**Update secret (add new version):**
```bash
echo -n "new_value" | gcloud secrets versions add SECRET_NAME --data-file=- --project=pgp-live
```

**View secret versions:**
```bash
gcloud secrets versions list SECRET_NAME --project=pgp-live
```

**Check who has access:**
```bash
gcloud secrets get-iam-policy SECRET_NAME --project=pgp-live
```

**Delete secret (DANGEROUS):**
```bash
gcloud secrets delete SECRET_NAME --project=pgp-live
# WARNING: Irreversible - service will fail
```

### Secret Value Verification

```bash
# Verify database secrets
gcloud secrets versions access latest --secret=CLOUD_SQL_CONNECTION_NAME --project=pgp-live
# Should output: pgp-live:us-central1:pgp-live-psql

gcloud secrets versions access latest --secret=DATABASE_NAME_SECRET --project=pgp-live
# Should output: pgp-live-db

# Verify signing keys are 64-char hex
gcloud secrets versions access latest --secret=SUCCESS_URL_SIGNING_KEY --project=pgp-live | wc -c
# Should output: 64

# Verify service URLs
gcloud secrets versions access latest --secret=PGP_ORCHESTRATOR_URL --project=pgp-live
# Should output: https://pgp-orchestrator-v1-{PROJECT_NUM}.us-central1.run.app
```

### Audit Log Queries

```bash
# Who accessed HOST_WALLET_PRIVATE_KEY in last 7 days?
gcloud logging read "protoPayload.serviceName=\"secretmanager.googleapis.com\" AND protoPayload.resourceName=~\"HOST_WALLET_PRIVATE_KEY\" AND timestamp>=\"$(date -d '7 days ago' --iso-8601)\"" --project=pgp-live --limit=50

# What secrets were updated today?
gcloud logging read "protoPayload.methodName=\"google.cloud.secretmanager.v1.SecretManagerService.AddSecretVersion\" AND timestamp>=\"$(date --iso-8601)\"" --project=pgp-live

# Failed secret access attempts
gcloud logging read "protoPayload.serviceName=\"secretmanager.googleapis.com\" AND severity=ERROR" --project=pgp-live --limit=50
```

---

## APPENDIX A: SECRET MIGRATION CHECKLIST

### From telepay-459221 to pgp-live

- [ ] **Phase 1:** Copy all STATIC secrets (18 secrets)
  - [ ] Database credentials (5)
  - [ ] Signing keys (5)
  - [ ] Wallet private key (1) - ULTRA-SECURE migration
  - [ ] Payment webhooks (2)
  - [ ] Redis (2)
  - [ ] Cloud Tasks (2)

- [ ] **Phase 2:** Generate NEW service URLs (14 secrets)
  - [ ] Deploy all Cloud Run services in pgp-live
  - [ ] Capture new URLs
  - [ ] Create secrets with new URL values

- [ ] **Phase 3:** Generate NEW queue names (17 secrets)
  - [ ] Deploy all Cloud Tasks queues in pgp-live
  - [ ] Create secrets with new queue names

- [ ] **Phase 4:** Update configuration values (11 secrets)
  - [ ] Update `CLOUD_SQL_CONNECTION_NAME` (new instance)
  - [ ] Update `DATABASE_NAME_SECRET` (telepaydb → pgp-live-db)
  - [ ] Update `NOWPAYMENTS_IPN_CALLBACK_URL` (new IPN service URL)
  - [ ] Update `CLOUD_TASKS_PROJECT_ID` (telepay-459221 → pgp-live)
  - [ ] Copy all other config values

- [ ] **Phase 5:** Update external webhooks
  - [ ] NOWPayments dashboard: Update IPN callback URL
  - [ ] Telegram BotFather: Verify bot token (same bot, no change needed)
  - [ ] Verify all external integrations

- [ ] **Phase 6:** Test migration
  - [ ] End-to-end payment flow
  - [ ] Signature verification
  - [ ] Queue processing
  - [ ] Email delivery
  - [ ] Telegram bot

### Secrets That DON'T Change

✅ **API Keys (copy as-is):**
- `NOWPAYMENTS_API_KEY`
- `NOWPAYMENTS_IPN_SECRET`
- `CHANGENOW_API_KEY`
- `SENDGRID_API_KEY`
- `TELEGRAM_BOT_API_TOKEN`

✅ **Wallet Secrets (copy as-is):**
- `HOST_WALLET_PRIVATE_KEY`
- `HOST_WALLET_ETH_ADDRESS`
- `HOST_WALLET_USDT_ADDRESS`
- `ETHEREUM_RPC_URL`
- `ETHEREUM_RPC_URL_API`

✅ **Application Config (copy as-is):**
- `BASE_URL`
- `CORS_ORIGIN`
- `TP_FLAT_FEE`
- `PAYMENT_MIN_TOLERANCE`
- `PAYMENT_FALLBACK_TOLERANCE`
- `MICRO_BATCH_THRESHOLD_USD`
- `BROADCAST_AUTO_INTERVAL`
- `BROADCAST_MANUAL_INTERVAL`

---

## APPENDIX B: SECRET ROTATION SCHEDULE

| Secret | Rotation Frequency | Downtime Required | Priority |
|--------|-------------------|-------------------|----------|
| **Database Password** | Every 90 days | 5 min (rolling restart) | 🔴 CRITICAL |
| **Signing Keys** | Every 180 days | 2 hours (planned) | 🔴 CRITICAL |
| **API Keys** | As needed | None (hot-reload) | 🟠 HIGH |
| **Wallet Private Key** | **NEVER** (fund migration only) | N/A | 🔴 ULTRA-CRITICAL |
| **Service URLs** | As needed | None (blue/green) | 🟡 MEDIUM |
| **Queue Names** | As needed | None (traffic shift) | 🟡 MEDIUM |
| **Config Values** | As needed | None (hot-reload) | 🟢 LOW |

---

## DOCUMENT VERSION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-18 | Initial comprehensive documentation for pgp-live project |
| | | - 69 secrets documented with hot-reload classification |
| | | - Service dependency matrix |
| | | - Security risk ratings |
| | | - Deployment checklists |
| | | - Creation commands |

---

**END OF SECRET_SCHEME_UPDATED.md**

**Total Secrets Documented:** 69
**Hot-Reloadable:** 51 (74%)
**Static-Only:** 18 (26%)
**Security Ratings:** Ultra-Critical (1), Critical (12), High (23), Medium (25), Low (8)

🔒 **This document is the authoritative reference for all pgp-live secrets**
