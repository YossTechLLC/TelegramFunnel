# PayGatePrime v1 - Complete Secrets Configuration Reference

**Project:** `pgp-live`
**Region:** `us-central1`
**Database Instance:** `pgp-live-psql`
**Database Name:** `pgpdb`

---

## ✅ Secrets Deployment Scripts Verification

All 3 secrets deployment scripts exist and are ready:

1. ✅ **03_create_secrets.sh** (16 KB) - Core application secrets
2. ✅ **04_create_queue_secrets.sh** (3.5 KB) - Cloud Tasks queue name secrets
3. ✅ **05_create_service_url_secrets.sh** (4.6 KB) - Service URL secrets (auto-populated)

---

## 📋 Complete Secrets List (46 Total)

### SECTION 1: Authentication & Security (Critical 🔴)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **JWT_SECRET_KEY** | `<MANUAL>` | ⚠️ MANUAL | Generate new 256-bit key: `openssl rand -base64 32` |
| **SIGNUP_SECRET_KEY** | `<MANUAL>` | ⚠️ MANUAL | Generate new 256-bit key: `openssl rand -base64 32` |

**Commands to create:**
```bash
# Generate and create JWT_SECRET_KEY
JWT_KEY=$(openssl rand -base64 32)
echo -n "$JWT_KEY" | gcloud secrets create JWT_SECRET_KEY --data-file=- --project=pgp-live

# Generate and create SIGNUP_SECRET_KEY
SIGNUP_KEY=$(openssl rand -base64 32)
echo -n "$SIGNUP_KEY" | gcloud secrets create SIGNUP_SECRET_KEY --data-file=- --project=pgp-live
```

---

### SECTION 2: Database Configuration (Critical 🔴)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **CLOUD_SQL_CONNECTION_NAME** | `pgp-live:us-central1:pgp-live-psql` | ✅ AUTO | Created by script |
| **DATABASE_NAME_SECRET** | `pgpdb` | ✅ AUTO | Created by script |
| **DATABASE_USER_SECRET** | `postgres` | ✅ AUTO | Created by script |
| **DATABASE_PASSWORD_SECRET** | `<MANUAL>` | ⚠️ MANUAL | Use password from Cloud SQL instance creation |

**Command to create:**
```bash
# Use the password you set when creating the Cloud SQL instance
echo -n 'YOUR_POSTGRES_PASSWORD' | gcloud secrets create DATABASE_PASSWORD_SECRET --data-file=- --project=pgp-live
```

---

### SECTION 3: Frontend & CORS Configuration (Critical 🔴)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **BASE_URL** | `https://www.paygateprime.com` | ✅ AUTO | Created by script |
| **CORS_ORIGIN** | `https://www.paygateprime.com` | ✅ AUTO | Created by script |

---

### SECTION 4: Email Service - SendGrid (Critical 🔴)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **SENDGRID_API_KEY** | `<MANUAL>` | ⚠️ MANUAL | Get from SendGrid dashboard |
| **FROM_EMAIL** | `noreply@paygateprime.com` | ✅ AUTO | Created by script |
| **FROM_NAME** | `PayGatePrime` | ✅ AUTO | Created by script |

**Command to create:**
```bash
echo -n 'SG.xxxxxxxxxxxxxxxxx' | gcloud secrets create SENDGRID_API_KEY --data-file=- --project=pgp-live
```

---

### SECTION 5: Payment Gateway - ChangeNOW (Critical 🔴)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **CHANGENOW_API_KEY** | `<MANUAL>` | ⚠️ MANUAL | Get from ChangeNOW dashboard |
| **CHANGENOW_USDT_WALLET** | `<MANUAL>` | ⚠️ MANUAL | Your USDT wallet address for receiving |

**Commands to create:**
```bash
echo -n 'YOUR_CHANGENOW_API_KEY' | gcloud secrets create CHANGENOW_API_KEY --data-file=- --project=pgp-live
echo -n 'YOUR_USDT_WALLET_ADDRESS' | gcloud secrets create CHANGENOW_USDT_WALLET --data-file=- --project=pgp-live
```

---

### SECTION 6: Payment Gateway - NowPayments (Critical 🔴)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **NOWPAYMENTS_API_KEY** | `<MANUAL>` | ⚠️ MANUAL | Get from NowPayments dashboard |
| **NOWPAYMENTS_IPN_SECRET** | `<MANUAL>` | ⚠️ MANUAL | Get from NowPayments IPN settings |
| **NOWPAYMENTS_USDT_WALLET** | `<MANUAL>` | ⚠️ MANUAL | Your USDT wallet for NowPayments |

**Commands to create:**
```bash
echo -n 'YOUR_NOWPAYMENTS_API_KEY' | gcloud secrets create NOWPAYMENTS_API_KEY --data-file=- --project=pgp-live
echo -n 'YOUR_NOWPAYMENTS_IPN_SECRET' | gcloud secrets create NOWPAYMENTS_IPN_SECRET --data-file=- --project=pgp-live
echo -n 'YOUR_USDT_WALLET_ADDRESS' | gcloud secrets create NOWPAYMENTS_USDT_WALLET --data-file=- --project=pgp-live
```

---

### SECTION 7: Platform Wallet Configuration (Critical 🔴)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **PLATFORM_USDT_WALLET_ADDRESS** | `<MANUAL>` | ⚠️ MANUAL | Platform's main USDT receiving wallet |
| **TP_PERCENTAGE** | `0.05` | ✅ AUTO | 5% fee (configurable) |
| **TP_FLAT_FEE** | `1.00` | ✅ AUTO | $1.00 USDT flat fee (configurable) |

**Command to create:**
```bash
echo -n 'YOUR_PLATFORM_USDT_WALLET' | gcloud secrets create PLATFORM_USDT_WALLET_ADDRESS --data-file=- --project=pgp-live
```

---

### SECTION 8: Blockchain Integration - Alchemy (Critical 🔴)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **ALCHEMY_API_KEY_POLYGON** | `<MANUAL>` | ⚠️ MANUAL | Get from Alchemy dashboard (Polygon network) |

**Command to create:**
```bash
echo -n 'YOUR_ALCHEMY_API_KEY' | gcloud secrets create ALCHEMY_API_KEY_POLYGON --data-file=- --project=pgp-live
```

---

### SECTION 9: Telegram Bot Integration (High 🟡)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **TELEGRAM_BOT_TOKEN** | `<MANUAL>` | ⚠️ MANUAL | Get from @BotFather on Telegram |

**Command to create:**
```bash
echo -n 'YOUR_BOT_TOKEN' | gcloud secrets create TELEGRAM_BOT_TOKEN --data-file=- --project=pgp-live
```

---

### SECTION 10: Cloud Tasks Configuration (Critical 🔴)

| Secret Name | Value | Status | Notes |
|------------|-------|--------|-------|
| **CLOUD_TASKS_PROJECT_ID** | `pgp-live` | ✅ AUTO | Created by script |
| **CLOUD_TASKS_LOCATION** | `us-central1` | ✅ AUTO | Created by script |

---

### SECTION 11: Cloud Tasks Queue Names (16 Queues)

**Script:** `04_create_queue_secrets.sh`

All queue names are auto-created with standardized naming:

| Secret Name | Queue Name Value | Status |
|------------|------------------|--------|
| **GCWEBHOOK1_QUEUE** | `gcwebhook1-queue` | ✅ AUTO |
| **GCWEBHOOK2_QUEUE** | `gcwebhook2-queue` | ✅ AUTO |
| **GCSPLIT1_QUEUE** | `gcsplit1-queue` | ✅ AUTO |
| **GCSPLIT2_QUEUE** | `gcsplit2-queue` | ✅ AUTO |
| **GCSPLIT3_QUEUE** | `gcsplit3-queue` | ✅ AUTO |
| **GCACCUMULATOR_QUEUE** | `gcaccumulator-queue` | ✅ AUTO |
| **GCACCUMULATOR_RESPONSE_QUEUE** | `gcaccumulator-response-queue` | ✅ AUTO |
| **GCBATCHPROCESSOR_QUEUE** | `gcbatchprocessor-queue` | ✅ AUTO |
| **GCHOSTPAY1_QUEUE** | `gchostpay1-queue` | ✅ AUTO |
| **GCHOSTPAY2_QUEUE** | `gchostpay2-queue` | ✅ AUTO |
| **GCHOSTPAY3_QUEUE** | `gchostpay3-queue` | ✅ AUTO |
| **GCHOSTPAY1_RESPONSE_QUEUE** | `gchostpay1-response-queue` | ✅ AUTO |
| **GCHOSTPAY1_THRESHOLD_QUEUE** | `gchostpay1-threshold-queue` | ✅ AUTO |
| **GCHOSTPAY3_RETRY_QUEUE** | `gchostpay3-retry-queue` | ✅ AUTO |
| **GCSPLIT1_BATCH_QUEUE** | `gcsplit1-batch-queue` | ✅ AUTO |
| **GCSPLIT2_RESPONSE_QUEUE** | `gcsplit2-response-queue` | ✅ AUTO |

**All created automatically by script** - No manual action required for queue names.

---

### SECTION 12: Service URLs (Auto-Populated After Deployment)

**Script:** `05_create_service_url_secrets.sh`

These are **auto-fetched** from Cloud Run after services are deployed:

| Secret Name | Example Value | Status | Notes |
|------------|---------------|--------|-------|
| **GCWEBHOOK1_URL** | `https://gcwebhook1-pgp-{PROJECT_NUMBER}.us-central1.run.app` | 🔄 AUTO | Fetched after deployment |
| **GCWEBHOOK2_URL** | `https://gcwebhook2-pgp-{PROJECT_NUMBER}.us-central1.run.app` | 🔄 AUTO | Fetched after deployment |
| **GCSPLIT1_URL** | `https://gcsplit1-pgp-{PROJECT_NUMBER}.us-central1.run.app` | 🔄 AUTO | Fetched after deployment |
| **GCSPLIT2_URL** | `https://gcsplit2-pgp-{PROJECT_NUMBER}.us-central1.run.app` | 🔄 AUTO | Fetched after deployment |
| **GCSPLIT3_URL** | `https://gcsplit3-pgp-{PROJECT_NUMBER}.us-central1.run.app` | 🔄 AUTO | Fetched after deployment |
| **GCACCUMULATOR_URL** | `https://gcaccumulator-pgp-{PROJECT_NUMBER}.us-central1.run.app` | 🔄 AUTO | Fetched after deployment |
| **GCHOSTPAY1_URL** | `https://gchostpay1-pgp-{PROJECT_NUMBER}.us-central1.run.app` | 🔄 AUTO | Fetched after deployment |
| **GCHOSTPAY2_URL** | `https://gchostpay2-pgp-{PROJECT_NUMBER}.us-central1.run.app` | 🔄 AUTO | Fetched after deployment |
| **GCHOSTPAY3_URL** | `https://gchostpay3-pgp-{PROJECT_NUMBER}.us-central1.run.app` | 🔄 AUTO | Fetched after deployment |

**Run after deploying services** - Script automatically fetches and creates these secrets.

---

## 📊 Summary Statistics

### Secrets Breakdown:
- **Total Secrets:** 46
- **Auto-Created:** 30 (65%)
- **Manual Required:** 16 (35%)

### By Category:
- **Database:** 4 secrets (3 auto, 1 manual)
- **Authentication:** 2 secrets (0 auto, 2 manual)
- **Frontend/CORS:** 2 secrets (2 auto, 0 manual)
- **Email (SendGrid):** 3 secrets (2 auto, 1 manual)
- **Payment Gateways:** 6 secrets (0 auto, 6 manual)
- **Blockchain:** 1 secret (0 auto, 1 manual)
- **Telegram:** 1 secret (0 auto, 1 manual)
- **Platform Config:** 3 secrets (2 auto, 1 manual)
- **Cloud Tasks:** 2 secrets (2 auto, 0 manual)
- **Queue Names:** 16 secrets (16 auto, 0 manual)
- **Service URLs:** 9 secrets (9 auto after deployment, 0 manual)

### By Priority:
- **Critical (🔴):** 30 secrets
- **High (🟡):** 1 secret
- **Auto-Generated:** 15 secrets

---

## 🔐 Manual Secrets Checklist

Before deployment, you MUST create these 12 manual secrets:

### Required API Keys & Tokens:
- [ ] **JWT_SECRET_KEY** - Generate: `openssl rand -base64 32`
- [ ] **SIGNUP_SECRET_KEY** - Generate: `openssl rand -base64 32`
- [ ] **DATABASE_PASSWORD_SECRET** - From Cloud SQL instance creation
- [ ] **SENDGRID_API_KEY** - From SendGrid dashboard
- [ ] **CHANGENOW_API_KEY** - From ChangeNOW dashboard
- [ ] **NOWPAYMENTS_API_KEY** - From NowPayments dashboard
- [ ] **NOWPAYMENTS_IPN_SECRET** - From NowPayments IPN settings
- [ ] **ALCHEMY_API_KEY_POLYGON** - From Alchemy dashboard (Polygon)
- [ ] **TELEGRAM_BOT_TOKEN** - From @BotFather

### Required Wallet Addresses:
- [ ] **CHANGENOW_USDT_WALLET** - Your USDT receiving wallet
- [ ] **NOWPAYMENTS_USDT_WALLET** - Your USDT wallet for NowPayments
- [ ] **PLATFORM_USDT_WALLET_ADDRESS** - Platform's main USDT wallet

---

## 🚀 Deployment Sequence

### Step 1: Run Core Secrets Script
```bash
cd /home/user/TelegramFunnel/NOVEMBER/PGP_v1/deployment_scripts
./03_create_secrets.sh
```

**Creates:** 11 auto secrets
**Requires:** You to manually create 12 remaining secrets

### Step 2: Create Manual Secrets
Use the commands provided in each section above to create the 12 manual secrets.

### Step 3: Run Queue Secrets Script
```bash
./04_create_queue_secrets.sh
```

**Creates:** 16 queue name secrets automatically

### Step 4: Deploy Services
Deploy all Cloud Run services using either:
- Monolithic: `./07_deploy_backend_services.sh`
- Individual: `./individual_services/deploy_all_services.sh`

### Step 5: Run Service URL Secrets Script
```bash
./05_create_service_url_secrets.sh
```

**Creates:** 9 service URL secrets automatically by fetching from Cloud Run

---

## ✅ Verification

After all secrets are created, verify:

```bash
# List all secrets
gcloud secrets list --project=pgp-live

# Should show 46 secrets total

# Verify specific secret exists
gcloud secrets describe JWT_SECRET_KEY --project=pgp-live

# View secret value (for testing only)
gcloud secrets versions access latest --secret=CLOUD_SQL_CONNECTION_NAME --project=pgp-live
```

---

## 🔧 Naming Architecture Changes

### Old Project (telepay-459221) → New Project (pgp-live)

| Component | Old Name | New Name |
|-----------|----------|----------|
| **Project ID** | `telepay-459221` | `pgp-live` |
| **Database Instance** | `telepaypsql` | `pgp-live-psql` |
| **Database Name** | `telepaydb` | `pgpdb` |
| **Connection String** | `telepay-459221:us-central1:telepaypsql` | `pgp-live:us-central1:pgp-live-psql` |
| **Service Names** | `gcwebhook1-10-26` | `gcwebhook1-pgp` |
| **Queue Names** | `gcwebhook1-queue` | `gcwebhook1-queue` (unchanged) |
| **Frontend URL** | `www.paygateprime.com` | `www.paygateprime.com` (unchanged) |

### Secret Name Consistency
All secret names remain the same across both projects. Only the **values** change to reflect the new project architecture.

---

**Last Updated:** 2025-11-16
**Project:** pgp-live
**Total Secrets:** 46
**Deployment Scripts:** 3 (core + queues + URLs)
