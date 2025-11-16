# Deployment Needs Analysis - PayGatePrime v1

**Generated:** 2025-11-16
**Status:** 🔍 COMPREHENSIVE REVIEW

---

## 🚨 Critical Findings

### Missing Service Discovered
- **np-webhook-PGP** - NowPayments IPN webhook handler was NOT in original migration
- ✅ **NOW ADDED** to PGP_v1

### Total Services: 15 (was 14)
1. GCRegisterAPI-PGP (Backend API)
2. GCRegisterWeb-PGP (React Frontend - **SPECIAL DEPLOYMENT**)
3. GCWebhook1-PGP (Primary webhook)
4. GCWebhook2-PGP (Telegram invite handler)
5. GCSplit1-PGP (Split payment #1)
6. GCSplit2-PGP (Split payment #2)
7. GCSplit3-PGP (Split payment #3)
8. GCHostPay1-PGP (Host payment #1)
9. GCHostPay2-PGP (Host payment #2)
10. GCHostPay3-PGP (Host payment #3)
11. GCAccumulator-PGP (Payment accumulator)
12. GCBatchProcessor-PGP (Batch processor)
13. GCMicroBatchProcessor-PGP (Micro batch processor)
14. TelePay-PGP (Telegram bot/legacy)
15. **np-webhook-PGP** (NowPayments IPN handler) ⚠️ **NEWLY ADDED**

---

## 📋 Missing Deployment Scripts

### 1️⃣ Cloud Run Service Deployment Scripts
**Status:** ❌ MISSING

**Need individual deployment scripts for:**
- 14 backend services (all except GCRegisterWeb)
- Each script should include:
  - Docker image build
  - Secret references
  - Cloud SQL connection
  - Environment variables
  - IAM permissions
  - Memory/CPU allocation
  - Service URL output

**Critical Services (External Webhooks):**
- ✅ **GCWebhook1-PGP** - Receives NowPayments validated payments
- ✅ **np-webhook-PGP** - Receives NowPayments IPN callbacks (HTTPS only!)
- ⚠️ Both must be HTTPS with valid domain

---

### 2️⃣ Frontend Deployment Script
**Status:** ❌ MISSING

**GCRegisterWeb-PGP** needs special handling:
- Option A: Firebase Hosting
- Option B: Cloud Storage + Cloud CDN + Load Balancer
- Option C: Cloud Run (with nginx)

**Current Setup (telepay-459221):**
- Likely using Cloud Storage + CDN
- Custom domain: www.paygateprime.com

**Needs:**
- Build script (npm run build)
- Upload to storage bucket
- CDN configuration
- SSL certificate
- Domain mapping

---

### 3️⃣ External Webhook Configuration Scripts
**Status:** ❌ MISSING

**NowPayments Webhook URL Update:**
- Must update IPN callback URL in NowPayments dashboard
- New URL: `https://pgp-npwebhook-v1-XXXXXX.us-central1.run.app/`
- ⚠️ **CRITICAL:** Must be HTTPS (Cloud Run provides this)

**ChangeNOW Webhook URL Update:**
- If ChangeNOW uses webhooks, update callback URL
- Likely handled by GCHostPay services

**Webhook Endpoints to Configure:**
```
NowPayments IPN → https://pgp-npwebhook-v1-{PROJECT_NUMBER}.us-central1.run.app/
Payment Processing Page → https://pgp-npwebhook-v1-{PROJECT_NUMBER}.us-central1.run.app/payment-processing
```

---

### 4️⃣ IAM Permission Scripts
**Status:** ❌ MISSING

**Need scripts to grant:**

**A. Service Account Creation:**
```bash
# Create dedicated service account for services
gcloud iam service-accounts create pgp-services \
  --display-name="PayGatePrime Services Account"
```

**B. Secret Manager Access:**
```bash
# Grant all services access to Secret Manager
gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-services@pgp-live.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**C. Cloud SQL Access:**
```bash
# Grant Cloud SQL Client role
gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-services@pgp-live.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

**D. Cloud Tasks Access:**
```bash
# Grant Cloud Tasks Enqueuer role
gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-services@pgp-live.iam.gserviceaccount.com" \
  --role="roles/cloudtasks.enqueuer"
```

**E. Service Invoker (for service-to-service calls):**
```bash
# Each service needs to invoke other services
gcloud run services add-iam-policy-binding SERVICE_NAME \
  --member="serviceAccount:pgp-services@pgp-live.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=us-central1
```

---

### 5️⃣ Cloud Scheduler Jobs
**Status:** ⚠️ UNKNOWN - Need to check if any exist

**Potential scheduled tasks:**
- Token cleanup (expired JWT tokens)
- Database maintenance
- Payment reconciliation
- Batch processing triggers

**Action:** Review TOOLS_SCRIPTS_TESTS for cron jobs

---

### 6️⃣ Monitoring & Alerting Setup
**Status:** ❌ MISSING

**Need scripts for:**
- Cloud Monitoring dashboards
- Alert policies (error rates, latency, uptime)
- Log-based metrics
- Uptime checks for critical endpoints

---

### 7️⃣ Database Migration Deployment
**Status:** ⚠️ PARTIAL - Scripts exist but need execution plan

**Migration scripts exist in TOOLS_SCRIPTS_TESTS/tools/**
- Need ordered execution plan
- Need rollback scripts
- Need verification queries

---

## 🔍 Service-by-Service Analysis

### Backend Services (Cloud Run - Public)

#### GCRegisterAPI-PGP
- **Port:** 8080 (Flask)
- **Auth:** JWT-based
- **Endpoints:** User registration, login, channel management
- **Secrets Needed:** 8 (JWT, DB, Email, CORS)
- **Cloud SQL:** ✅ Yes
- **External Access:** ✅ Yes (API for frontend)

#### np-webhook-PGP ⚠️ **NEWLY ADDED**
- **Port:** 8080 (Flask)
- **Auth:** HMAC signature verification (NowPayments IPN secret)
- **Endpoints:**
  - `POST /` - IPN callback (must be HTTPS!)
  - `GET /payment-processing` - Payment status page
  - `GET /api/check-payment-status` - Status API
- **Secrets Needed:** 5 (DB, NOWPAYMENTS_IPN_SECRET, queues)
- **Cloud SQL:** ✅ Yes
- **External Access:** ✅ Yes (NowPayments callback)
- **⚠️ CRITICAL:** Must configure NowPayments dashboard with new URL

---

### Backend Services (Cloud Run - Internal)

#### GCWebhook1-PGP
- **Port:** 8080
- **Auth:** Internal (Cloud Tasks)
- **Triggered by:** np-webhook after validation
- **Secrets Needed:** 7 (DB, queues, URLs)
- **Cloud SQL:** ✅ Yes
- **External Access:** ⚠️ Should be internal only (Cloud Tasks invoker)

#### GCWebhook2-PGP
- **Port:** 8080
- **Auth:** Internal (Cloud Tasks)
- **Purpose:** Telegram invite dispatch
- **Secrets Needed:** 4 (DB, Telegram token)
- **Cloud SQL:** ✅ Yes
- **External Access:** ❌ No

#### GCSplit1-PGP, GCSplit2-PGP, GCSplit3-PGP
- **Port:** 8080
- **Auth:** Internal (Cloud Tasks)
- **Purpose:** Split payments across multiple services
- **Secrets Needed:** 5-7 each
- **Cloud SQL:** ✅ Yes
- **External Access:** ❌ No

#### GCHostPay1-PGP, GCHostPay2-PGP, GCHostPay3-PGP
- **Port:** 8080
- **Auth:** Internal (Cloud Tasks)
- **Purpose:** Execute actual crypto payments via ChangeNOW
- **Secrets Needed:** 8-10 (ChangeNOW API, wallets)
- **Cloud SQL:** ✅ Yes (some services)
- **External Access:** ❌ No

#### GCAccumulator-PGP
- **Port:** 8080
- **Auth:** Internal (Cloud Tasks)
- **Purpose:** Accumulate small payments
- **Secrets Needed:** 5
- **Cloud SQL:** ✅ Yes
- **External Access:** ❌ No

#### GCBatchProcessor-PGP
- **Port:** 8080
- **Auth:** Internal (Cloud Tasks)
- **Purpose:** Batch process conversions
- **Secrets Needed:** 4
- **Cloud SQL:** ✅ Yes
- **External Access:** ❌ No

#### GCMicroBatchProcessor-PGP
- **Port:** 8080
- **Auth:** Internal (Cloud Tasks / Cloud Scheduler)
- **Purpose:** Handle micro-batch conversions
- **Secrets Needed:** 6
- **Cloud SQL:** ✅ Yes
- **External Access:** ❌ No (possibly Cloud Scheduler)

#### TelePay-PGP
- **Port:** 8080
- **Auth:** Telegram webhook
- **Purpose:** Legacy Telegram bot
- **Secrets Needed:** 8 (Telegram, DB)
- **Cloud SQL:** ✅ Yes
- **External Access:** ⚠️ If webhook mode (Telegram callback)

---

### Frontend (Special Deployment)

#### GCRegisterWeb-PGP
- **Type:** React SPA (Vite)
- **Build:** `npm run build` → static files
- **Deployment:** Cloud Storage + CDN (recommended)
- **Domain:** www.paygateprime.com
- **CDN:** Cloud CDN or Firebase Hosting
- **SSL:** Managed certificate
- **API Backend:** Points to GCRegisterAPI-PGP URL

---

## 🎯 Required Scripts to Create

### Priority 1 (Critical)
1. ✅ **06_setup_iam_permissions.sh** - Service account + IAM roles
2. ✅ **07_deploy_backend_services.sh** - Deploy all 14 backend services to Cloud Run
3. ✅ **08_deploy_frontend.sh** - Build and deploy React frontend
4. ✅ **09_update_external_webhooks.md** - Guide for NowPayments/external webhook config
5. ✅ **10_verify_deployment.sh** - Health check all services

### Priority 2 (Important)
6. ⚠️ **service_deployment_configs/** - Individual service deployment configs
7. ⚠️ **check_scheduled_jobs.sh** - Identify if Cloud Scheduler jobs needed
8. ⚠️ **setup_monitoring.sh** - Create monitoring dashboards

### Priority 3 (Nice to Have)
9. ⚠️ **rollback_deployment.sh** - Rollback script
10. ⚠️ **database_migration_plan.md** - Ordered migration execution

---

## 📊 Deployment Complexity Matrix

| Service | Complexity | External Access | Critical Path |
|---------|------------|-----------------|---------------|
| np-webhook-PGP | 🔴 HIGH | ✅ Yes (NowPayments) | ✅ CRITICAL |
| GCRegisterAPI-PGP | 🔴 HIGH | ✅ Yes (Frontend) | ✅ CRITICAL |
| GCRegisterWeb-PGP | 🟡 MEDIUM | ✅ Yes (Users) | ✅ CRITICAL |
| GCWebhook1-PGP | 🟡 MEDIUM | ⚠️ Internal | ✅ CRITICAL |
| GCHostPay1/2/3-PGP | 🟡 MEDIUM | ❌ No | ✅ CRITICAL |
| GCSplit1/2/3-PGP | 🟢 LOW | ❌ No | 🟡 IMPORTANT |
| GCWebhook2-PGP | 🟢 LOW | ❌ No | 🟡 IMPORTANT |
| GCAccumulator-PGP | 🟢 LOW | ❌ No | 🟢 OPTIONAL |
| GCBatchProcessor-PGP | 🟢 LOW | ❌ No | 🟢 OPTIONAL |
| GCMicroBatchProcessor-PGP | 🟢 LOW | ❌ No | 🟢 OPTIONAL |
| TelePay-PGP | 🟢 LOW | ⚠️ Maybe | 🟢 OPTIONAL |

---

## ⚠️ Critical Deployment Order

1. **Infrastructure** (Already have scripts)
   - Enable APIs ✅
   - Create Cloud SQL ✅
   - Create core secrets ✅

2. **IAM & Permissions** ⚠️ **NEED SCRIPT**
   - Create service account
   - Grant permissions

3. **Backend Services** ⚠️ **NEED SCRIPT**
   - Deploy in order:
     1. GCRegisterAPI-PGP (frontend needs this first)
     2. np-webhook-PGP (external webhook)
     3. GCWebhook1-PGP (payment processor)
     4. GCHostPay1/2/3-PGP (payment execution)
     5. GCSplit1/2/3-PGP (split logic)
     6. GCWebhook2-PGP (telegram)
     7. Others (accumulator, batch, etc.)

4. **Service URL Secrets** ✅ **HAVE SCRIPT** (05_create_service_url_secrets.sh)

5. **Cloud Tasks Queues** ✅ **HAVE SCRIPTS** (in TOOLS_SCRIPTS_TESTS)

6. **Frontend** ⚠️ **NEED SCRIPT**
   - Build React app
   - Deploy to Cloud Storage/CDN

7. **Database Migrations** ⚠️ **HAVE SCRIPTS, NEED PLAN**
   - Execute migration scripts

8. **External Webhook Config** ⚠️ **NEED GUIDE**
   - Update NowPayments IPN URL
   - Test webhooks

9. **Verification** ⚠️ **NEED SCRIPT**
   - Health checks
   - End-to-end payment test

---

## 🔐 Security Considerations

### Public Services (Must Have Auth)
- ✅ GCRegisterAPI-PGP - JWT authentication
- ✅ np-webhook-PGP - HMAC signature verification
- ⚠️ GCRegisterWeb-PGP - Public (static files)

### Internal Services (Should Restrict)
- All other services should only accept requests from:
  - Cloud Tasks (with service account auth)
  - Cloud Scheduler (with service account auth)
  - Other Cloud Run services (with IAM invoker role)

**Action:** Set `--no-allow-unauthenticated` for internal services

---

## 📝 Next Steps

1. Create np-webhook update (copy service) ✅ **DONE**
2. Create IAM permission script
3. Create backend deployment script
4. Create frontend deployment script
5. Create webhook configuration guide
6. Create verification script
7. Update MIGRATION_SUMMARY.md with new findings
8. Update SECRET_CONFIG_UPDATE.md (add np-webhook service)

---

**Status:** Analysis complete - Ready to create missing scripts
**Critical Finding:** np-webhook service added, multiple deployment scripts needed
