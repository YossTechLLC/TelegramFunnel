# Secret Manager Configuration Update - PGP_v1 Migration

**Project**: `telepay-459221`
**Migration**: 10-26 naming → PGP_v1 naming convention
**Date**: 2025-11-16
**Status**: Migration Required

---

## Executive Summary

This document maps all necessary changes to Google Cloud Secret Manager secrets due to the PGP_v1 architecture migration. The migration renamed 17 services from date-based naming (e.g., `GCAccumulator-10-26`) to versioned naming (e.g., `pgp-accumulator-v1`).

**Total Secrets Requiring Updates:** 23 out of 75
**Secrets Unchanged:** 52 (API keys, private keys, database credentials, etc.)

---

## Part 1: Secret Name Changes

### 1.1 Service URL Secret Names

**No secret name changes required** - All secret names can remain the same. Only the **values** within these secrets need updating to reflect new service URLs.

The following secret names are consistent with the new architecture:
- `GCACCUMULATOR_URL` ✅ (value needs update)
- `GCBATCHPROCESSOR_URL` ✅ (value needs update)
- `GCHOSTPAY1_URL` ✅ (already updated)
- `GCHOSTPAY2_URL` ✅ (already updated)
- `GCHOSTPAY3_URL` ✅ (already updated)
- `GCSPLIT1_URL` ✅ (already updated)
- `GCSPLIT2_URL` ✅ (already updated)
- `GCSPLIT3_URL` ✅ (already updated)
- `GCWEBHOOK1_URL` ✅ (already updated)
- `GCWEBHOOK2_URL` ✅ (already updated)
- `MICROBATCH_URL` ✅ (value needs update)
- `NOWPAYMENTS_IPN_CALLBACK_URL` ✅ (value needs update)
- `TELEPAY_BOT_URL` ✅ (value needs update if migrating to Cloud Run)

### 1.2 Queue Name Secret Names

**No secret name changes required** - Queue name secrets remain the same, but values need updating.

---

## Part 2: Secret Value Changes

### 2.1 Service URLs (CRITICAL - Deploy New Services First)

| Secret Name | OLD Value | NEW Value | Status |
|-------------|-----------|-----------|--------|
| `GCACCUMULATOR_URL` | `https://pgp_accumulator-10-26-291176869049.us-central1.run.app` | `https://pgp-accumulator-v1-291176869049.us-central1.run.app` | ⚠️ UPDATE REQUIRED |
| `GCBATCHPROCESSOR_URL` | `https://pgp_batchprocessor-10-26-291176869049.us-central1.run.app` | `https://pgp-batchprocessor-v1-291176869049.us-central1.run.app` | ⚠️ UPDATE REQUIRED |
| `MICROBATCH_URL` | `https://pgp_microbatchprocessor-10-26-pjxwjsdktq-uc.a.run.app` | `https://pgp-microbatchprocessor-v1-291176869049.us-central1.run.app` | ⚠️ UPDATE REQUIRED |
| `NOWPAYMENTS_IPN_CALLBACK_URL` | `https://PGP_NP_IPN_v1-pjxwjsdktq-uc.a.run.app` | `https://pgp-np-ipn-v1-291176869049.us-central1.run.app` | ⚠️ UPDATE REQUIRED |
| `TELEPAY_BOT_URL` | `http://34.58.80.152:8080` | `https://pgp-server-v1-291176869049.us-central1.run.app` | 🟡 OPTIONAL (if migrating to Cloud Run) |
| `GCHOSTPAY1_URL` | `https://pgp-hostpay1-v1-291176869049.us-central1.run.app` | No change | ✅ ALREADY UPDATED |
| `GCHOSTPAY2_URL` | `https://pgp-hostpay2-v1-291176869049.us-central1.run.app` | No change | ✅ ALREADY UPDATED |
| `GCHOSTPAY3_URL` | `https://pgp-hostpay3-v1-291176869049.us-central1.run.app` | No change | ✅ ALREADY UPDATED |
| `GCSPLIT1_URL` | `https://pgp-split1-v1-291176869049.us-central1.run.app` | No change | ✅ ALREADY UPDATED |
| `GCSPLIT2_URL` | `https://pgp-split2-v1-291176869049.us-central1.run.app` | No change | ✅ ALREADY UPDATED |
| `GCSPLIT3_URL` | `https://pgp-split3-v1-291176869049.us-central1.run.app` | No change | ✅ ALREADY UPDATED |
| `GCWEBHOOK1_URL` | `https://pgp-orchestrator-v1-pjxwjsdktq-uc.a.run.app` | No change | ✅ ALREADY UPDATED |
| `GCWEBHOOK2_URL` | `https://pgp-invite-v1-291176869049.us-central1.run.app` | No change | ✅ ALREADY UPDATED |
| `WEBHOOK_BASE_URL` | `https://pgp-orchestrator-v1-291176869049.us-central1.run.app` | No change | ✅ ALREADY UPDATED |
| `HOSTPAY_WEBHOOK_URL` | `https://pgp-hostpay1-v1-291176869049.us-central1.run.app` | No change | ✅ ALREADY UPDATED (duplicate) |

**Notes:**
- ⚠️ **CRITICAL:** Deploy new Cloud Run services BEFORE updating these URLs
- Service name pattern changed: `service-10-26` → `service-v1`
- Underscores in service names changed to hyphens: `pgp_accumulator-10-26` → `pgp-accumulator-v1`

---

### 2.2 Cloud Tasks Queue Names (Deploy Queues First)

Based on deployment scripts, the following queue names need updating:

| Secret Name | OLD Value | NEW Value | Status |
|-------------|-----------|-----------|--------|
| `GCACCUMULATOR_QUEUE` | `accumulator-payment-queue` | `pgp-accumulator-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCACCUMULATOR_RESPONSE_QUEUE` | `pgp_accumulator-swap-response-queue` | `pgp-accumulator-response-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCBATCHPROCESSOR_QUEUE` | `pgp_batchprocessor-10-26-queue` | `pgp-batchprocessor-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCHOSTPAY1_QUEUE` | `pgp-split-hostpay-trigger-queue` | `pgp-hostpay-trigger-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCHOSTPAY1_RESPONSE_QUEUE` | `gchostpay1-response-queue` | `pgp-hostpay1-response-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCHOSTPAY2_QUEUE` | `gchostpay2-status-check-queue` | `pgp-hostpay2-status-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCHOSTPAY3_QUEUE` | `gchostpay3-payment-exec-queue` | `pgp-hostpay3-payment-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCHOSTPAY3_RETRY_QUEUE` | `pgp-hostpay3-retry-queue` | `pgp-hostpay3-retry-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCSPLIT1_QUEUE` | `gcsplit-webhook-queue` | `pgp-split1-estimate-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCSPLIT1_BATCH_QUEUE` | `gcsplit1-batch-queue` | `pgp-split1-batch-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCSPLIT2_QUEUE` | `pgp-split-usdt-eth-estimate-queue` | `pgp-split2-swap-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCSPLIT2_RESPONSE_QUEUE` | `pgp-split-usdt-eth-response-queue` | `pgp-split2-response-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCSPLIT3_QUEUE` | `pgp-split-eth-client-swap-queue` | `pgp-split3-client-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCSPLIT3_RESPONSE_QUEUE` | `pgp-split-eth-client-response-queue` | `pgp-split3-response-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCWEBHOOK1_QUEUE` | `gcwebhook1-queue` | `pgp-orchestrator-queue-v1` | ⚠️ UPDATE REQUIRED |
| `GCWEBHOOK2_QUEUE` | `gcwebhook-telegram-invite-queue` | `pgp-invite-queue-v1` | ⚠️ UPDATE REQUIRED |
| `HOSTPAY_QUEUE` | `pgp-split-hostpay-trigger-queue` | `pgp-hostpay-trigger-queue-v1` | ⚠️ UPDATE REQUIRED (duplicate) |

**Queue Naming Convention:**
- Pattern: `pgp-[component]-[purpose]-queue-v1`
- Examples: `pgp-accumulator-queue-v1`, `pgp-hostpay1-response-queue-v1`

---

### 2.3 Callback URLs (Within Service Code)

These URLs appear in service code and configuration, not necessarily as separate secrets:

| Callback | OLD Value | NEW Value | Location |
|----------|-----------|-----------|----------|
| Split1 Estimate Callback | `https://pgp-split1-v1-.../usdt-eth-estimate` | No change | ✅ Already using v1 naming |
| Split1 Swap Callback | `https://pgp-split1-v1-.../eth-client-swap` | No change | ✅ Already using v1 naming |
| TPS Webhook Callback | `https://pgp-split1-v1-...` | No change | ✅ Already using v1 naming |

---

## Part 3: Secrets That DO NOT Change

### 3.1 API Keys and Tokens (52 secrets unchanged)

**These secrets remain EXACTLY THE SAME:**

✅ **Payment & Exchange APIs:**
- `NOWPAYMENTS_API_KEY` - WHY9...D9J (27 chars)
- `NOWPAYMENTS_IPN_SECRET` - 1EQD...DQs (28 chars)
- `NOWPAYMENT_WEBHOOK_KEY` - erwU...uqL (28 chars)
- `PAYMENT_PROVIDER_TOKEN` - WHY9...D9J (duplicate of NOWPAYMENTS_API_KEY)
- `1INCH_API_KEY` - tXRQ...v7c5 (32 chars)
- `CHANGENOW_API_KEY` - 0e7a...5bde (64 chars)
- `COINGECKO_API_KEY` - CG-A...Dzmo (25 chars)
- `CRYPTOCOMPARE_API_KEY` - f76f...df48 (64 chars)

✅ **Blockchain & Wallet (CRITICAL - Never Change):**
- `HOST_WALLET_PRIVATE_KEY` - 7273...8f2e (64 chars) 🔴
- `HOST_WALLET_ETH_ADDRESS` - 0x16...1bc4
- `HOST_WALLET_USDT_ADDRESS` - 0x16...1bc4
- `ETHEREUM_RPC_URL` - https://eth-mainnet.g.alchemy.com/v2/AQB6...Nohb
- `ETHEREUM_RPC_URL_API` - AQB6...Nohb (32 chars)
- `ETHEREUM_RPC_WEBHOOK_SECRET` - whse...1exs (32 chars)

✅ **Database Credentials:**
- `DATABASE_HOST_SECRET` - 34.58.246.248
- `DATABASE_NAME_SECRET` - client_table
- `DATABASE_USER_SECRET` - postgres
- `DATABASE_PASSWORD_SECRET` - Chig...st3$ (15 chars)
- `DATABASE_SECRET_KEY` - y764...3LM (43 chars)
- `CLOUD_SQL_CONNECTION_NAME` - telepay-459221:us-central1:telepaypsql

✅ **Telegram Bot:**
- `TELEGRAM_BOT_SECRET_NAME` - 8139...6Co (46 chars)
- `TELEGRAM_BOT_USERNAME` - PayGatePrime_bot

✅ **Signing & Security Keys:**
- `WEBHOOK_SIGNING_KEY` - f4e7...2345 (64 chars)
- `TPS_HOSTPAY_SIGNING_KEY` - 6b5f...df5a (64 chars)
- `SUCCESS_URL_SIGNING_KEY` - sSll...q+sI= (44 chars)
- `JWT_SECRET_KEY` - cc54...de71 (64 chars)
- `SIGNUP_SECRET_KEY` - 16a5...75d4 (64 chars)

✅ **Email Configuration:**
- `SENDGRID_API_KEY` - SG.t...tVs (69 chars)
- `FROM_EMAIL` - noreply@paygateprime.com
- `FROM_NAME` - PayGatePrime

✅ **Application Configuration:**
- `BASE_URL` - https://www.paygateprime.com
- `CORS_ORIGIN` - https://www.paygateprime.com
- `CLOUD_TASKS_LOCATION` - us-central1
- `CLOUD_TASKS_PROJECT_ID` - telepay-459221
- `BROADCAST_AUTO_INTERVAL` - 24
- `BROADCAST_MANUAL_INTERVAL` - 0.0833
- `ALERTING_ENABLED` - true
- `MICRO_BATCH_THRESHOLD_USD` - 5.00
- `PAYMENT_FALLBACK_TOLERANCE` - 0.75
- `PAYMENT_MIN_TOLERANCE` - 0.50
- `TP_FLAT_FEE` - 15

---

## Part 4: NEW Secrets Required (Security Fixes)

Based on the security fixes implementation, add these NEW secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `FLASK_SECRET_KEY` | `<generate: secrets.token_hex(32)>` | Flask CSRF protection (64 chars hex) |
| `TELEGRAM_WEBHOOK_SECRET` | `<generate: secrets.token_urlsafe(32)>` | Telegram webhook verification (future) |

**Generate Commands:**
```bash
# Flask Secret Key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Telegram Webhook Secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Add to Secret Manager:**
```bash
# Flask Secret Key
echo -n "<generated_value>" | gcloud secrets create FLASK_SECRET_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project=telepay-459221

# Telegram Webhook Secret
echo -n "<generated_value>" | gcloud secrets create TELEGRAM_WEBHOOK_SECRET \
  --data-file=- \
  --replication-policy="automatic" \
  --project=telepay-459221
```

---

## Part 5: Migration Execution Plan

### Step 1: Deploy New Cloud Run Services

**Deploy all 17 services with new naming:**

```bash
# Priority 1: Core Services
./deploy_telepay_bot.sh          # pgp-server-v1
./deploy_np_webhook.sh           # pgp-np-ipn-v1

# Priority 2: Payment Processing
./deploy_accumulator.sh          # pgp-accumulator-v1
./deploy_batch_processor.sh      # pgp-batchprocessor-v1
./deploy_microbatch.sh           # pgp-microbatchprocessor-v1

# Priority 3: HostPay Services
./deploy_hostpay1.sh             # pgp-hostpay1-v1
./deploy_hostpay2.sh             # pgp-hostpay2-v1
./deploy_hostpay3.sh             # pgp-hostpay3-v1

# Priority 4: Split Services
./deploy_split1.sh               # pgp-split1-v1
./deploy_split2.sh               # pgp-split2-v1
./deploy_split3.sh               # pgp-split3-v1

# Priority 5: Orchestration
./deploy_orchestrator.sh         # pgp-orchestrator-v1
./deploy_invite.sh               # pgp-invite-v1
./deploy_broadcast.sh            # pgp-broadcast-v1
./deploy_notifications.sh        # pgp-notifications-v1

# Priority 6: Web Services
./deploy_backend_api.sh          # pgp-webapi-v1
./deploy_frontend.sh             # pgp-web-v1
```

---

### Step 2: Deploy New Cloud Tasks Queues

**Deploy all queues with new naming:**

```bash
# Deploy queue sets
./deploy_accumulator_tasks_queues.sh
./deploy_hostpay_tasks_queues.sh
./deploy_gcsplit_tasks_queues.sh
./deploy_gcwebhook_tasks_queues.sh
```

---

### Step 3: Update Secret Manager Values

**Update Service URLs:**

```bash
# Accumulator
echo -n "https://pgp-accumulator-v1-291176869049.us-central1.run.app" | \
  gcloud secrets versions add GCACCUMULATOR_URL --data-file=- --project=telepay-459221

# Batch Processor
echo -n "https://pgp-batchprocessor-v1-291176869049.us-central1.run.app" | \
  gcloud secrets versions add GCBATCHPROCESSOR_URL --data-file=- --project=telepay-459221

# MicroBatch Processor
echo -n "https://pgp-microbatchprocessor-v1-291176869049.us-central1.run.app" | \
  gcloud secrets versions add MICROBATCH_URL --data-file=- --project=telepay-459221

# NowPayments IPN
echo -n "https://pgp-np-ipn-v1-291176869049.us-central1.run.app" | \
  gcloud secrets versions add NOWPAYMENTS_IPN_CALLBACK_URL --data-file=- --project=telepay-459221

# (Optional) TelePay Bot - if migrating to Cloud Run
echo -n "https://pgp-server-v1-291176869049.us-central1.run.app" | \
  gcloud secrets versions add TELEPAY_BOT_URL --data-file=- --project=telepay-459221
```

**Update Queue Names:**

```bash
# Accumulator Queues
echo -n "pgp-accumulator-queue-v1" | \
  gcloud secrets versions add GCACCUMULATOR_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-accumulator-response-queue-v1" | \
  gcloud secrets versions add GCACCUMULATOR_RESPONSE_QUEUE --data-file=- --project=telepay-459221

# Batch Processor
echo -n "pgp-batchprocessor-queue-v1" | \
  gcloud secrets versions add GCBATCHPROCESSOR_QUEUE --data-file=- --project=telepay-459221

# HostPay Queues
echo -n "pgp-hostpay-trigger-queue-v1" | \
  gcloud secrets versions add GCHOSTPAY1_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-hostpay1-response-queue-v1" | \
  gcloud secrets versions add GCHOSTPAY1_RESPONSE_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-hostpay2-status-queue-v1" | \
  gcloud secrets versions add GCHOSTPAY2_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-hostpay3-payment-queue-v1" | \
  gcloud secrets versions add GCHOSTPAY3_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-hostpay3-retry-queue-v1" | \
  gcloud secrets versions add GCHOSTPAY3_RETRY_QUEUE --data-file=- --project=telepay-459221

# Split Queues
echo -n "pgp-split1-estimate-queue-v1" | \
  gcloud secrets versions add GCSPLIT1_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-split1-batch-queue-v1" | \
  gcloud secrets versions add GCSPLIT1_BATCH_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-split2-swap-queue-v1" | \
  gcloud secrets versions add GCSPLIT2_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-split2-response-queue-v1" | \
  gcloud secrets versions add GCSPLIT2_RESPONSE_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-split3-client-queue-v1" | \
  gcloud secrets versions add GCSPLIT3_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-split3-response-queue-v1" | \
  gcloud secrets versions add GCSPLIT3_RESPONSE_QUEUE --data-file=- --project=telepay-459221

# Webhook Queues
echo -n "pgp-orchestrator-queue-v1" | \
  gcloud secrets versions add GCWEBHOOK1_QUEUE --data-file=- --project=telepay-459221

echo -n "pgp-invite-queue-v1" | \
  gcloud secrets versions add GCWEBHOOK2_QUEUE --data-file=- --project=telepay-459221

# Duplicate (if needed)
echo -n "pgp-hostpay-trigger-queue-v1" | \
  gcloud secrets versions add HOSTPAY_QUEUE --data-file=- --project=telepay-459221
```

---

### Step 4: Add New Security Secrets

```bash
# Generate Flask Secret Key
FLASK_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo -n "$FLASK_SECRET" | gcloud secrets create FLASK_SECRET_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project=telepay-459221

# Generate Telegram Webhook Secret
TELEGRAM_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo -n "$TELEGRAM_SECRET" | gcloud secrets create TELEGRAM_WEBHOOK_SECRET \
  --data-file=- \
  --replication-policy="automatic" \
  --project=telepay-459221
```

---

### Step 5: Grant Service Account Access

**Grant service account access to ALL secrets:**

```bash
SERVICE_ACCOUNT="291176869049-compute@developer.gserviceaccount.com"

# Grant access to new secrets
for secret in FLASK_SECRET_KEY TELEGRAM_WEBHOOK_SECRET; do
  gcloud secrets add-iam-policy-binding $secret \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --project=telepay-459221
done
```

---

### Step 6: Update NowPayments Dashboard

**Update IPN Callback URL in NowPayments:**

1. Login to NowPayments dashboard
2. Navigate to Settings → API → IPN Settings
3. Update IPN Callback URL:
   - **OLD:** `https://PGP_NP_IPN_v1-pjxwjsdktq-uc.a.run.app`
   - **NEW:** `https://pgp-np-ipn-v1-291176869049.us-central1.run.app/webhooks/nowpayments-ipn`
4. Verify IPN Secret matches: `1EQD...DQs` (28 chars)

---

### Step 7: Verify and Test

**1. Test Service Connectivity:**
```bash
# Test each new service URL
curl https://pgp-accumulator-v1-291176869049.us-central1.run.app/health
curl https://pgp-batchprocessor-v1-291176869049.us-central1.run.app/health
curl https://pgp-server-v1-291176869049.us-central1.run.app/health
# ... etc for all services
```

**2. Verify Queue Existence:**
```bash
# List all queues
gcloud tasks queues list --location=us-central1 --project=telepay-459221 | grep "pgp-.*-v1"
```

**3. Test Secret Access:**
```bash
# Test accessing updated secrets
gcloud secrets versions access latest --secret="GCACCUMULATOR_URL" --project=telepay-459221
gcloud secrets versions access latest --secret="FLASK_SECRET_KEY" --project=telepay-459221
```

---

## Part 6: Rollback Plan

**If migration fails, revert secrets to previous versions:**

```bash
# List secret versions to find previous version number
gcloud secrets versions list GCACCUMULATOR_URL --project=telepay-459221

# Revert to previous version (replace N with version number)
gcloud secrets versions enable N --secret="GCACCUMULATOR_URL" --project=telepay-459221
```

**Old services remain deployed** - can switch traffic back if needed.

---

## Part 7: Summary Checklist

### Pre-Migration
- [ ] Review all 23 secrets requiring updates
- [ ] Generate FLASK_SECRET_KEY and TELEGRAM_WEBHOOK_SECRET
- [ ] Document current secret versions for rollback

### Deployment
- [ ] Deploy all 17 Cloud Run services with new naming
- [ ] Deploy all Cloud Tasks queues with new naming
- [ ] Verify all services are healthy

### Secret Updates
- [ ] Update 4 service URL secrets
- [ ] Update 17 queue name secrets
- [ ] Create 2 new security secrets
- [ ] Grant service account access to new secrets

### External Configuration
- [ ] Update NowPayments IPN callback URL
- [ ] Verify Telegram bot webhook configuration (if using webhooks)

### Testing
- [ ] Test all service URLs respond
- [ ] Test queue task submission
- [ ] Test payment flow end-to-end
- [ ] Monitor logs for errors

### Cleanup (After 7 Days)
- [ ] Delete old Cloud Run services (10-26 naming)
- [ ] Delete old Cloud Tasks queues
- [ ] Disable old secret versions (keep for 30 days)

---

## Part 8: Quick Reference

### Service URL Pattern
```
https://pgp-[service]-v1-291176869049.us-central1.run.app
```

### Queue Name Pattern
```
pgp-[component]-[purpose]-queue-v1
```

### Secret Access Pattern
```bash
gcloud secrets versions access latest --secret="SECRET_NAME" --project=telepay-459221
```

---

**End of Secret Configuration Update Document**

**Total Changes:**
- **23 secret values** need updating (URLs + queue names)
- **2 new secrets** for security (FLASK_SECRET_KEY, TELEGRAM_WEBHOOK_SECRET)
- **52 secrets** remain unchanged (API keys, private keys, credentials)
- **0 secret names** need changing (only values update)
