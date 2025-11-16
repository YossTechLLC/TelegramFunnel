# Secret Configuration Update: pgp-live Project

**Project Migration:** `telepay-459221` → `pgp-live`
**Created:** 2025-11-16
**Status:** 🔧 PREPARATION (Not Deployed)

---

## 📋 Overview

This document catalogs ALL secrets that must be created in the `pgp-live` project's Secret Manager before deploying any services. These secrets replace references to the `telepay-459221` project.

---

## 🔐 Required Secrets in pgp-live

### **Core Authentication & Security**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `JWT_SECRET_KEY` | JSON Web Token signing key for user authentication | `<random-256-bit-key>` | 🔴 CRITICAL |
| `SIGNUP_SECRET_KEY` | Token signing for email verification & password reset | `<random-256-bit-key>` | 🔴 CRITICAL |

---

### **Database Configuration**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `CLOUD_SQL_CONNECTION_NAME` | Cloud SQL instance connection string | `pgp-live:us-central1:pgp-psql` | 🔴 CRITICAL |
| `DATABASE_NAME_SECRET` | PostgreSQL database name | `pgpdb` | 🔴 CRITICAL |
| `DATABASE_USER_SECRET` | PostgreSQL username | `postgres` | 🔴 CRITICAL |
| `DATABASE_PASSWORD_SECRET` | PostgreSQL password | `<secure-password>` | 🔴 CRITICAL |

**📝 Note:** Database instance name `pgp-psql` is suggested. Actual name TBD during deployment.

---

### **Frontend & CORS Configuration**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `BASE_URL` | Frontend base URL (for emails, links) | `https://www.paygateprime.com` | 🔴 CRITICAL |
| `CORS_ORIGIN` | Allowed CORS origin for API | `https://www.paygateprime.com` | 🔴 CRITICAL |

**⚠️ Important:** If domain changes for PGP v1, update both secrets accordingly.

---

### **Email Service (SendGrid)**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `SENDGRID_API_KEY` | SendGrid API key for transactional emails | `SG.xxxxxxxxxxxxx` | 🔴 CRITICAL |
| `FROM_EMAIL` | Sender email address | `noreply@paygateprime.com` | 🔴 CRITICAL |
| `FROM_NAME` | Sender display name | `PayGatePrime` | 🟡 HIGH |

**Usage:** Password reset, email verification, account notifications

---

### **Payment Gateway - ChangeNOW**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `CHANGENOW_API_KEY` | ChangeNOW API authentication key | `<api-key>` | 🔴 CRITICAL |
| `CHANGENOW_USDT_WALLET` | ChangeNOW USDT wallet address | `0x...` | 🔴 CRITICAL |

---

### **Payment Gateway - NowPayments**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `NOWPAYMENTS_API_KEY` | NowPayments API key | `<api-key>` | 🔴 CRITICAL |
| `NOWPAYMENTS_IPN_SECRET` | IPN callback signature verification | `<ipn-secret>` | 🔴 CRITICAL |
| `NOWPAYMENTS_USDT_WALLET` | NowPayments USDT wallet address | `0x...` | 🔴 CRITICAL |

---

### **Platform Wallet Configuration**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `PLATFORM_USDT_WALLET_ADDRESS` | Platform's main USDT receiving wallet | `0x...` | 🔴 CRITICAL |
| `TP_PERCENTAGE` | TelePay fee percentage | `0.05` (5%) | 🔴 CRITICAL |
| `TP_FLAT_FEE` | TelePay flat fee in USDT | `1.00` | 🔴 CRITICAL |

---

### **Blockchain Integration - Alchemy**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `ALCHEMY_API_KEY_POLYGON` | Alchemy API key for Polygon network | `<alchemy-key>` | 🔴 CRITICAL |

**Usage:** Real-time blockchain transaction verification on Polygon

---

### **Telegram Bot Integration**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot API token | `<bot-token>` | 🟡 HIGH |

---

### **Cloud Tasks - Queue Names**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `GCWEBHOOK1_QUEUE` | Webhook 1 task queue name | `gcwebhook1-queue` | 🔴 CRITICAL |
| `GCWEBHOOK2_QUEUE` | Webhook 2 task queue name | `gcwebhook2-queue` | 🔴 CRITICAL |
| `GCSPLIT1_QUEUE` | Split service 1 task queue | `gcsplit1-queue` | 🔴 CRITICAL |
| `GCSPLIT2_QUEUE` | Split service 2 task queue | `gcsplit2-queue` | 🔴 CRITICAL |
| `GCSPLIT3_QUEUE` | Split service 3 task queue | `gcsplit3-queue` | 🔴 CRITICAL |
| `GCACCUMULATOR_QUEUE` | Accumulator task queue | `gcaccumulator-queue` | 🔴 CRITICAL |
| `GCACCUMULATOR_RESPONSE_QUEUE` | Accumulator response queue | `gcaccumulator-response-queue` | 🔴 CRITICAL |
| `GCBATCHPROCESSOR_QUEUE` | Batch processor task queue | `gcbatchprocessor-queue` | 🔴 CRITICAL |
| `GCHOSTPAY1_QUEUE` | Host pay 1 task queue | `gchostpay1-queue` | 🔴 CRITICAL |
| `GCHOSTPAY2_QUEUE` | Host pay 2 task queue | `gchostpay2-queue` | 🔴 CRITICAL |
| `GCHOSTPAY3_QUEUE` | Host pay 3 task queue | `gchostpay3-queue` | 🔴 CRITICAL |
| `GCHOSTPAY1_RESPONSE_QUEUE` | Host pay 1 response queue | `gchostpay1-response-queue` | 🔴 CRITICAL |
| `GCHOSTPAY1_THRESHOLD_QUEUE` | Host pay 1 threshold queue | `gchostpay1-threshold-queue` | 🟡 HIGH |
| `GCHOSTPAY3_RETRY_QUEUE` | Host pay 3 retry queue | `gchostpay3-retry-queue` | 🟡 HIGH |
| `GCSPLIT1_BATCH_QUEUE` | Split 1 batch queue | `gcsplit1-batch-queue` | 🟡 HIGH |
| `GCSPLIT2_RESPONSE_QUEUE` | Split 2 response queue | `gcsplit2-response-queue` | 🟡 HIGH |

**📝 Note:** Queue names can remain the same or be updated for PGP branding (e.g., `pgp-webhook1-queue`)

---

### **Cloud Tasks - Service URLs**

| Secret Name | Description | Example Value | Priority |
|------------|-------------|---------------|----------|
| `GCWEBHOOK1_URL` | Webhook 1 service URL | `https://gcwebhook1-<PROJECT_NUMBER>.us-central1.run.app` | 🔴 CRITICAL |
| `GCWEBHOOK2_URL` | Webhook 2 service URL | `https://gcwebhook2-<PROJECT_NUMBER>.us-central1.run.app` | 🔴 CRITICAL |
| `GCSPLIT1_URL` | Split service 1 URL | `https://gcsplit1-<PROJECT_NUMBER>.us-central1.run.app` | 🔴 CRITICAL |
| `GCSPLIT2_URL` | Split service 2 URL | `https://gcsplit2-<PROJECT_NUMBER>.us-central1.run.app` | 🔴 CRITICAL |
| `GCSPLIT3_URL` | Split service 3 URL | `https://gcsplit3-<PROJECT_NUMBER>.us-central1.run.app` | 🔴 CRITICAL |
| `GCACCUMULATOR_URL` | Accumulator service URL | `https://gcaccumulator-<PROJECT_NUMBER>.us-central1.run.app` | 🔴 CRITICAL |
| `GCHOSTPAY1_URL` | Host pay 1 service URL | `https://gchostpay1-<PROJECT_NUMBER>.us-central1.run.app` | 🔴 CRITICAL |
| `GCHOSTPAY2_URL` | Host pay 2 service URL | `https://gchostpay2-<PROJECT_NUMBER>.us-central1.run.app` | 🔴 CRITICAL |
| `GCHOSTPAY3_URL` | Host pay 3 service URL | `https://gchostpay3-<PROJECT_NUMBER>.us-central1.run.app` | 🔴 CRITICAL |

**⚠️ Important:** `<PROJECT_NUMBER>` will be the numeric project number for `pgp-live` (obtained after project creation)

---

## 📊 Secret Summary

| Category | Count |
|----------|-------|
| Authentication & Security | 2 |
| Database | 4 |
| Frontend & CORS | 2 |
| Email Service | 3 |
| Payment - ChangeNOW | 2 |
| Payment - NowPayments | 3 |
| Platform Configuration | 3 |
| Blockchain (Alchemy) | 1 |
| Telegram | 1 |
| Cloud Tasks - Queues | 16 |
| Cloud Tasks - URLs | 9 |
| **TOTAL** | **46 secrets** |

---

## 🚀 Deployment Sequence

### Step 1: Create Project Infrastructure Secrets (Do First)
1. `CLOUD_SQL_CONNECTION_NAME`
2. `DATABASE_NAME_SECRET`
3. `DATABASE_USER_SECRET`
4. `DATABASE_PASSWORD_SECRET`

### Step 2: Create Application Secrets
5. `JWT_SECRET_KEY`
6. `SIGNUP_SECRET_KEY`
7. `BASE_URL`
8. `CORS_ORIGIN`

### Step 3: Create Third-Party Integration Secrets
9-17. All payment gateway, email, and blockchain secrets

### Step 4: Create Cloud Tasks Queue Names
18-33. All queue name secrets

### Step 5: Create Service URLs (After Cloud Run Deployment)
34-42. All service URL secrets (must wait for Cloud Run to generate URLs)

### Step 6: Create Cloud Tasks Queues
- Use deployment scripts to create actual Cloud Tasks queues
- Reference queue name secrets created in Step 4

---

## 🔧 Secret Creation Script Template

```bash
#!/bin/bash
# Create secrets in pgp-live project
PROJECT_ID="pgp-live"

# Authentication
echo -n "<value>" | gcloud secrets create JWT_SECRET_KEY --data-file=- --project=$PROJECT_ID
echo -n "<value>" | gcloud secrets create SIGNUP_SECRET_KEY --data-file=- --project=$PROJECT_ID

# Database
echo -n "pgp-live:us-central1:pgp-psql" | gcloud secrets create CLOUD_SQL_CONNECTION_NAME --data-file=- --project=$PROJECT_ID
echo -n "pgpdb" | gcloud secrets create DATABASE_NAME_SECRET --data-file=- --project=$PROJECT_ID
echo -n "postgres" | gcloud secrets create DATABASE_USER_SECRET --data-file=- --project=$PROJECT_ID
echo -n "<password>" | gcloud secrets create DATABASE_PASSWORD_SECRET --data-file=- --project=$PROJECT_ID

# ... (continue for all 46 secrets)
```

---

## 📝 Migration Notes

1. **Project ID References:** All `telepay-459221` in code → `pgp-live`
2. **Database Instance:** `telepaypsql` → `pgp-psql` (or chosen name)
3. **Service Naming:** Consider removing `-10-26` suffix → use `-pgp` or clean names
4. **Service URLs:** Will be auto-generated after Cloud Run deployment
5. **Queue Names:** Can keep same logical names, just in new project
6. **Domain:** Verify if `www.paygateprime.com` stays or changes

---

## ⚠️ Critical Reminders

- **DO NOT** commit secret values to git
- **DO NOT** hardcode secrets in code
- **DO** use Secret Manager exclusively
- **DO** rotate `JWT_SECRET_KEY` and `SIGNUP_SECRET_KEY` (different from telepay-459221)
- **DO** verify all service URLs after Cloud Run deployment
- **DO** test all webhook callbacks with new URLs

---

## 📍 Current Status

- [ ] Secrets documented
- [ ] Project `pgp-live` created
- [ ] Secrets created in Secret Manager
- [ ] Cloud SQL instance created
- [ ] Services deployed to Cloud Run
- [ ] Service URLs updated in secrets
- [ ] Cloud Tasks queues created
- [ ] Webhook callbacks configured
- [ ] End-to-end testing complete

---

**Next Step:** Begin Phase 2 - Copy services to `/NOVEMBER/PGP_v1/` and update all references

