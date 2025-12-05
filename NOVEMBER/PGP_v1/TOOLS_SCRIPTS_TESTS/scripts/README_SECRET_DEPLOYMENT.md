# PGP_v1 Secret Manager Deployment Guide

**Project:** PayGatePrime (PGP_v1)
**Target:** pgp-live (Google Cloud Project)
**Total Secrets:** 69 (51 hot-reloadable, 18 static)
**Last Updated:** 2025-11-18

---

## 📋 Overview

This directory contains comprehensive deployment scripts for creating and managing all 69 Secret Manager secrets required for the PGP_v1 system.

### Deployment Scripts

| Script | Secrets | Description | Prerequisites |
|--------|---------|-------------|---------------|
| `create_pgp_live_secrets_phase1_infrastructure.sh` | 9 | Database, Cloud Tasks, Redis infrastructure | Cloud SQL, Memorystore provisioned |
| `create_pgp_live_secrets_phase2_security.sh` | 10 | Signing keys, wallet, payment webhooks | Phase 1 complete |
| `create_pgp_live_secrets_phase3_apis.sh` | 5 | External API keys (NOWPayments, ChangeNow, etc.) | Phase 1-2 complete |
| `create_pgp_live_secrets_phase4_config.sh` | 12 | Application configuration values | Phase 1-3 complete |
| `create_pgp_live_secrets_phase5_service_urls.sh` | 14 | Cloud Run service URLs | All services deployed |
| `create_pgp_live_secrets_phase6_queue_names.sh` | 16 | Cloud Tasks queue names | All queues created |
| **Total** | **66** | Phases 1-6 total | |

### Utility Scripts

| Script | Purpose |
|--------|---------|
| `grant_pgp_live_secret_access.sh` | Grant IAM permissions to service accounts |
| `verify_pgp_live_secrets.sh` | Verify all secrets exist and have correct formats |

---

## 🚀 Quick Start

### Prerequisites Checklist

- [ ] GCP Project `pgp-live` created
- [ ] Secret Manager API enabled
- [ ] Cloud SQL instance `pgp-live-psql` provisioned
- [ ] Memorystore Redis instance provisioned
- [ ] `gcloud` CLI authenticated
- [ ] External API keys obtained (NOWPayments, ChangeNow, SendGrid, Alchemy/Infura)
- [ ] Telegram bot token from BotFather
- [ ] Wallet private key securely stored

### Deployment Workflow

```bash
# Phase 1: Infrastructure (9 secrets)
./create_pgp_live_secrets_phase1_infrastructure.sh

# Phase 2: Security (10 secrets)
./create_pgp_live_secrets_phase2_security.sh

# Phase 3: External APIs (5 secrets)
./create_pgp_live_secrets_phase3_apis.sh

# Phase 4: Application Configuration (12 secrets)
./create_pgp_live_secrets_phase4_config.sh

# ⚠️  DEPLOY ALL CLOUD RUN SERVICES BEFORE PHASE 5

# Phase 5: Service URLs (14 secrets)
./create_pgp_live_secrets_phase5_service_urls.sh

# ⚠️  DEPLOY ALL CLOUD TASKS QUEUES BEFORE PHASE 6

# Phase 6: Queue Names (16 secrets)
./create_pgp_live_secrets_phase6_queue_names.sh

# Grant IAM Permissions
./grant_pgp_live_secret_access.sh <SERVICE_ACCOUNT_EMAIL>

# Verify All Secrets
./verify_pgp_live_secrets.sh
```

---

## 📊 Secret Categories

### 1. Database Credentials (5 secrets - ALL STATIC)

| Secret | Hot-Reload | Value Example |
|--------|------------|---------------|
| `CLOUD_SQL_CONNECTION_NAME` | ❌ STATIC | `pgp-live:us-central1:pgp-live-psql` |
| `DATABASE_NAME_SECRET` | ❌ STATIC | `pgp-live-db` |
| `DATABASE_USER_SECRET` | ❌ STATIC | `postgres` |
| `DATABASE_PASSWORD_SECRET` | ❌ STATIC | `<64-char hex>` |

**Why STATIC:** Connection pool initialization at startup

### 2. Service URLs (14 secrets - ALL HOT-RELOADABLE)

All Cloud Run service URLs follow pattern:
```
https://pgp-{service}-v1-{PROJECT_NUM}.us-central1.run.app
```

**Why HOT-RELOADABLE:** Blue/green deployments, zero-downtime URL updates

### 3. Cloud Tasks Queue Names (16 secrets - ALL HOT-RELOADABLE)

All queue names follow pattern:
```
pgp-{component}-{purpose}-queue-v1
```

**Why HOT-RELOADABLE:** Queue migration without service restart

### 4. Signing & Encryption Keys (5 secrets - ALL STATIC)

| Secret | Length | Usage |
|--------|--------|-------|
| `SUCCESS_URL_SIGNING_KEY` | 64-char hex | JWT signing, token encryption |
| `TPS_HOSTPAY_SIGNING_KEY` | 64-char hex | HostPay inter-service tokens |
| `JWT_SECRET_KEY` | 64-char hex | JWT authentication |
| `SIGNUP_SECRET_KEY` | 64-char hex | Email verification tokens |
| `PGP_INTERNAL_SIGNING_KEY` | 64-char hex | Future internal auth |

**Why STATIC:** Hot-reload invalidates all existing tokens

### 5. Wallet & Blockchain (5 secrets - MIXED)

| Secret | Hot-Reload | Security Rating |
|--------|------------|-----------------|
| `HOST_WALLET_PRIVATE_KEY` | ❌ STATIC | 🔴 ULTRA-CRITICAL |
| `HOST_WALLET_ETH_ADDRESS` | ✅ HOT | 🟠 HIGH |
| `HOST_WALLET_USDT_ADDRESS` | ✅ HOT | 🟠 HIGH |
| `ETHEREUM_RPC_URL` | ✅ HOT | 🟠 HIGH |
| `ETHEREUM_RPC_URL_API` | ✅ HOT | 🟠 HIGH |

**ULTRA-CRITICAL:** `HOST_WALLET_PRIVATE_KEY` controls all funds

### 6. Payment Provider APIs (4 secrets - MIXED)

| Secret | Hot-Reload | Provider |
|--------|------------|----------|
| `NOWPAYMENTS_API_KEY` | ✅ HOT | NOWPayments |
| `NOWPAYMENTS_IPN_SECRET` | ❌ STATIC | NOWPayments |
| `CHANGENOW_API_KEY` | ✅ HOT | ChangeNow |
| `SENDGRID_API_KEY` | ✅ HOT | SendGrid |

### 7-10. Additional Categories

- Telegram Bot (2 secrets - HOT)
- Redis / Nonce Tracking (2 secrets - STATIC)
- Cloud Tasks Infrastructure (2 secrets - STATIC)
- Application Configuration (12 secrets - ALL HOT)

---

## 🔐 Security Best Practices

### Critical Security Rules

🔴 **NEVER** commit secrets to version control
🔴 **NEVER** log secret values or lengths
🔴 **NEVER** hot-reload signing keys (invalidates all tokens)
🔴 **NEVER** hot-reload wallet private key (controls funds)
🔴 **ALWAYS** use Secret Manager (never hardcode)
🔴 **ALWAYS** rotate secrets every 90 days (except wallet private key)

### Secret Access Control

1. **Principle of Least Privilege:** Only grant access to secrets that services actually need
2. **Service Account Isolation:** Use separate service accounts for different service tiers
3. **Audit Logging:** Monitor who accesses `HOST_WALLET_PRIVATE_KEY`
4. **2-Person Rule:** Ultra-critical secrets require 2-person access approval

### Rotation Schedules

| Secret Category | Rotation Frequency | Downtime Required |
|-----------------|-------------------|-------------------|
| Database Password | Every 90 days | 5 min (rolling restart) |
| Signing Keys | Every 180 days | 2 hours (planned) |
| API Keys | As needed | None (hot-reload) |
| Wallet Private Key | **NEVER** (fund migration only) | N/A |

---

## 🔍 Verification & Testing

### Verify All Secrets

```bash
./verify_pgp_live_secrets.sh
```

Output example:
```
✅ Found: 69 secrets
❌ Missing: 0 secrets
⚠️  Format Errors: 0 secrets
```

### Test Secret Access from Cloud Run

```bash
# Read secret from Cloud Run service
gcloud run services update pgp-orchestrator-v1 \
  --region=us-central1 \
  --project=pgp-live \
  --set-env-vars="TEST_SECRET_ACCESS=true"
```

### Test Hot-Reload Functionality

```bash
# Update a hot-reloadable secret
echo -n "10.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=- --project=pgp-live

# Wait 60 seconds (cache TTL)
sleep 60

# Verify service uses new value (check logs)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=pgp-microbatchprocessor-v1" --limit=10 --project=pgp-live
```

---

## 📚 Reference Documentation

### Secret Naming Conventions

| Pattern | Example | Usage |
|---------|---------|-------|
| `PGP_{SERVICE}_URL` | `PGP_ORCHESTRATOR_URL` | Service URLs |
| `PGP_{SERVICE}_{PURPOSE}_QUEUE` | `PGP_SPLIT1_BATCH_QUEUE` | Queue names |
| `{PROVIDER}_{KEY_TYPE}` | `NOWPAYMENTS_API_KEY` | API keys |
| `{COMPONENT}_{PROPERTY}` | `DATABASE_NAME_SECRET` | Infrastructure |

### Hot-Reload vs Static Classification

**Hot-Reloadable (51 secrets):**
- Service URLs (14)
- Queue names (16)
- Wallet addresses (2)
- API keys (5)
- Application config (14)

**Static-Only (18 secrets):**
- Database credentials (5)
- Signing keys (5)
- Wallet private key (1)
- Payment webhooks (2)
- Redis infrastructure (2)
- Cloud Tasks infrastructure (2)

### Value Formats

#### Hex Keys (64 characters)
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### Cloud Run URLs
```
https://pgp-{service}-v1-{PROJECT_NUMBER}.us-central1.run.app
```

#### Queue Names
```
pgp-{component}-{purpose}-queue-v1
```

#### Ethereum Addresses
```
0x[0-9a-fA-F]{40}
```

---

## 🐛 Troubleshooting

### Issue: Secret not found

**Error:**
```
Permission denied on secret 'projects/123/secrets/DATABASE_NAME_SECRET'
```

**Solution:**
```bash
# Grant service account access
gcloud secrets add-iam-policy-binding DATABASE_NAME_SECRET \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@pgp-live.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=pgp-live
```

### Issue: Hot-reload not working

**Error:**
```
Old secret value still in use after update
```

**Solution:**
```
Wait 60 seconds for cache TTL to expire
BaseConfigManager uses 60-second TTL for hot-reloadable secrets
```

### Issue: Secret value has trailing newline

**Error:**
```
Invalid database password (extra character)
```

**Solution:**
```bash
# Always use echo -n (no newline)
echo -n "value" | gcloud secrets create SECRET_NAME --data-file=-
# NOT: echo "value" (adds newline)
```

---

## 📝 Migration from telepay-459221

### Secrets That DON'T Change

✅ **API Keys (copy as-is):**
- `NOWPAYMENTS_API_KEY`
- `NOWPAYMENTS_IPN_SECRET`
- `CHANGENOW_API_KEY`
- `SENDGRID_API_KEY`
- `TELEGRAM_BOT_API_TOKEN`

✅ **Wallet Secrets (copy as-is):**
- `HOST_WALLET_PRIVATE_KEY` (ULTRA-SECURE migration)
- `HOST_WALLET_ETH_ADDRESS`
- `HOST_WALLET_USDT_ADDRESS`
- `ETHEREUM_RPC_URL`

✅ **Application Config (copy as-is):**
- `TP_FLAT_FEE`
- `PAYMENT_MIN_TOLERANCE`
- `BROADCAST_AUTO_INTERVAL`
- etc.

### Secrets That MUST Change

❌ **Database Connection:**
- `CLOUD_SQL_CONNECTION_NAME` → `pgp-live:us-central1:pgp-live-psql`
- `DATABASE_NAME_SECRET` → `pgp-live-db`

❌ **Service URLs (14):** All new Cloud Run URLs

❌ **Queue Names (16):** All new Cloud Tasks queues

❌ **IPN Callback:**
- `NOWPAYMENTS_IPN_CALLBACK_URL` → New PGP_NP_IPN_v1 URL

---

## 🎯 Next Steps After Deployment

1. **Deploy PGP_v1 Services**
   - Use deployment scripts in `/TOOLS_SCRIPTS_TESTS/scripts/deploy_*.sh`
   - All services configured to use new secrets

2. **Update External Webhooks**
   - Register `PGP_NP_IPN_URL` in NOWPayments dashboard
   - Verify Telegram bot webhook

3. **End-to-End Testing**
   - Payment flow (NOWPayments → IPN → Orchestrator → Invite)
   - Payout flow (Batch → Split → HostPay → Blockchain)
   - Hot-reload testing
   - Security verification

4. **Production Cutover**
   - Gradual traffic migration
   - Monitor metrics and logs
   - Rollback plan ready

---

## 📞 Support

For issues or questions:
- Review `/DECISIONS.md` for architectural decisions
- Check `/BUGS.md` for known issues
- See `SECRET_SCHEME_UPDATED.md` for complete reference

---

**Generated:** 2025-11-18
**Version:** 1.0
**Status:** 🟢 PRODUCTION READY
