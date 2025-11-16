# PayGatePrime v1 Migration Checklist
## Project Migration: telepay-459221 → pgp-live

**Status:** 🚧 IN PROGRESS
**Created:** 2025-11-16
**Target:** Prepare codebase for deployment to new GCP project `pgp-live`

---

## 📋 Overview

This checklist tracks the migration of the TelegramFunnel payment processing system from the `telepay-459221` GCP project to a new `pgp-live` project for PayGatePrime v1.

**Key Services to Migrate:**
1. ✅ GCRegisterAPI-10-26 (Main Backend API)
2. ✅ GCRegisterWeb-10-26 (React Frontend)
3. ✅ GCWebhook1-10-26 (Webhook Handler #1)
4. ✅ GCWebhook2-10-26 (Webhook Handler #2)
5. ✅ GCSplit1-10-26 (Split Payment Service #1)
6. ✅ GCSplit2-10-26 (Split Payment Service #2)
7. ✅ GCSplit3-10-26 (Split Payment Service #3)
8. ✅ GCHostPay1-10-26 (Host Payment Service #1)
9. ✅ GCHostPay2-10-26 (Host Payment Service #2)
10. ✅ GCHostPay3-10-26 (Host Payment Service #3)
11. ✅ GCAccumulator-10-26 (Payment Accumulator)
12. ✅ GCBatchProcessor-10-26 (Batch Processor)
13. ✅ GCMicroBatchProcessor-10-26 (Micro Batch Processor)
14. ✅ TelePay10-26 (Legacy TelePay Service)

---

## 🔍 Phase 1: Discovery & Analysis

### 1.1 Identify All Project ID References
- [ ] Search for hardcoded `telepay-459221` in Python files
- [ ] Search for hardcoded `telepay-459221` in config files
- [ ] Search for hardcoded `telepay-459221` in Dockerfiles
- [ ] Search for hardcoded `telepay-459221` in deployment scripts
- [ ] Search for hardcoded `telepay-459221` in documentation

### 1.2 Identify Database References
- [ ] Document current Cloud SQL instance: `telepaypsql`
- [ ] Document connection name format: `telepay-459221:us-central1:telepaypsql`
- [ ] Identify all database connection points in code
- [ ] Identify all database migrations/schema files

### 1.3 Identify Secret Manager References
- [ ] List all secrets currently used (from config_manager.py files)
- [ ] Document secret access patterns
- [ ] Identify environment variable mappings

### 1.4 Identify Cloud Tasks/Queues
- [ ] List all queue names
- [ ] Document task queue locations
- [ ] Identify queue creation scripts

### 1.5 Identify Webhook URLs
- [ ] Document all external webhook endpoints
- [ ] Identify service-to-service communication URLs
- [ ] Map Cloud Run service names

---

## 📦 Phase 2: Code Migration

### 2.1 Copy Services to PGP_v1
- [ ] Create service directory structure in `/NOVEMBER/PGP_v1/`
- [ ] Copy GCRegisterAPI-10-26 → GCRegisterAPI-PGP
- [ ] Copy GCRegisterWeb-10-26 → GCRegisterWeb-PGP
- [ ] Copy GCWebhook1-10-26 → GCWebhook1-PGP
- [ ] Copy GCWebhook2-10-26 → GCWebhook2-PGP
- [ ] Copy GCSplit1-10-26 → GCSplit1-PGP
- [ ] Copy GCSplit2-10-26 → GCSplit2-PGP
- [ ] Copy GCSplit3-10-26 → GCSplit3-PGP
- [ ] Copy GCHostPay1-10-26 → GCHostPay1-PGP
- [ ] Copy GCHostPay2-10-26 → GCHostPay2-PGP
- [ ] Copy GCHostPay3-10-26 → GCHostPay3-PGP
- [ ] Copy GCAccumulator-10-26 → GCAccumulator-PGP
- [ ] Copy GCBatchProcessor-10-26 → GCBatchProcessor-PGP
- [ ] Copy GCMicroBatchProcessor-10-26 → GCMicroBatchProcessor-PGP
- [ ] Copy TelePay10-26 → TelePay-PGP
- [ ] Copy TOOLS_SCRIPTS_TESTS directory
- [ ] Copy relevant documentation files

---

## 🔧 Phase 3: Update Project ID References

### 3.1 Update Python Files
- [ ] Update config_manager.py files (GCRegisterAPI, GCMicroBatchProcessor)
- [ ] Update database connection strings in all services
- [ ] Update Cloud Tasks client initialization
- [ ] Update Secret Manager client initialization
- [ ] Update tool/migration scripts

### 3.2 Update Configuration Files
- [ ] Update Dockerfile ENV variables (if any)
- [ ] Update requirements.txt dependencies (if project-specific)
- [ ] Update .env.example files

### 3.3 Update Documentation
- [ ] Update deployment instructions
- [ ] Update README files
- [ ] Update API documentation

---

## 🗄️ Phase 4: Database Configuration Updates

### 4.1 Cloud SQL Connection
- [ ] Update connection name format: `pgp-live:us-central1:pgp-psql` (new instance name TBD)
- [ ] Update all `CLOUD_SQL_CONNECTION_NAME` references
- [ ] Update database_manager.py files in all services
- [ ] Update connection pooling configurations

### 4.2 Database Credentials
- [ ] Update `DATABASE_NAME_SECRET` references
- [ ] Update `DATABASE_USER_SECRET` references
- [ ] Update `DATABASE_PASSWORD_SECRET` references
- [ ] Ensure secrets point to pgp-live Secret Manager

---

## 🔐 Phase 5: Secret Manager Updates

### 5.1 Map All Secrets
Current secrets to migrate:
- [ ] DATABASE_NAME_SECRET
- [ ] DATABASE_USER_SECRET
- [ ] DATABASE_PASSWORD_SECRET
- [ ] CLOUD_SQL_CONNECTION_NAME
- [ ] BASE_URL
- [ ] CORS_ORIGIN
- [ ] SENDGRID_API_KEY
- [ ] JWT_SECRET_KEY
- [ ] CHANGENOW_API_KEY
- [ ] CHANGENOW_USDT_WALLET
- [ ] NOWPAYMENTS_API_KEY
- [ ] NOWPAYMENTS_IPN_SECRET
- [ ] NOWPAYMENTS_USDT_WALLET
- [ ] PLATFORM_USDT_WALLET_ADDRESS
- [ ] TP_PERCENTAGE
- [ ] TP_FLAT_FEE
- [ ] ALCHEMY_API_KEY_POLYGON
- [ ] TELEGRAM_BOT_TOKEN
- [ ] Queue-related secrets (GCWEBHOOK1_QUEUE, GCWEBHOOK2_QUEUE, etc.)
- [ ] URL-related secrets (GCSPLIT1_URL, GCSPLIT2_URL, etc.)

### 5.2 Update Secret Access
- [ ] Update project ID in all `access_secret()` calls
- [ ] Update project ID in SecretManagerServiceClient initialization
- [ ] Verify secret path format: `projects/pgp-live/secrets/{SECRET_NAME}/versions/latest`

---

## 🌐 Phase 6: Webhook & Service URL Updates

### 6.1 Cloud Run Service URLs
Update service URLs to new pattern: `https://[SERVICE_NAME]-[PROJECT_NUMBER].us-central1.run.app`

- [ ] Document new service naming convention (remove -10-26 suffix)
- [ ] Update webhook callback URLs
- [ ] Update service-to-service communication URLs
- [ ] Update frontend API base URL

### 6.2 Queue Task URLs
- [ ] Update GCSPLIT1_URL
- [ ] Update GCSPLIT2_URL
- [ ] Update GCSPLIT3_URL
- [ ] Update GCACCUMULATOR_URL
- [ ] Update GCWEBHOOK1_URL
- [ ] Update GCWEBHOOK2_URL
- [ ] Update GCHOSTPAY1_URL
- [ ] Update GCHOSTPAY2_URL
- [ ] Update GCHOSTPAY3_URL

### 6.3 External Webhooks
- [ ] Update NowPayments IPN callback URL
- [ ] Update ChangeNow webhook URL
- [ ] Update any other third-party webhook configurations

---

## 📝 Phase 7: Deployment Preparation

### 7.1 Create Deployment Scripts
- [ ] Create secret creation script for pgp-live
- [ ] Create Cloud SQL instance creation script
- [ ] Create Cloud Tasks queue creation script
- [ ] Create Cloud Scheduler job creation script
- [ ] Create service deployment scripts (Cloud Run)
- [ ] Create IAM permissions script

### 7.2 Environment-Specific Configuration
- [ ] Create pgp-live environment variable template
- [ ] Document required GCP APIs to enable
- [ ] Document IAM service account requirements
- [ ] Create database migration execution plan

### 7.3 Documentation
- [ ] Create DEPLOYMENT_GUIDE.md for pgp-live
- [ ] Create SECRET_SETUP_GUIDE.md
- [ ] Create DATABASE_MIGRATION_GUIDE.md
- [ ] Update main README.md

---

## ✅ Phase 8: Verification

### 8.1 Code Verification
- [ ] No hardcoded `telepay-459221` references remain
- [ ] All config_manager.py files use correct project ID
- [ ] All database connections use pgp-live format
- [ ] All secret access uses pgp-live project

### 8.2 Configuration Verification
- [ ] All Dockerfiles build successfully
- [ ] All requirements.txt are complete
- [ ] All environment variables documented
- [ ] All service dependencies mapped

### 8.3 Documentation Verification
- [ ] All README files updated
- [ ] All deployment guides accurate
- [ ] All API documentation current
- [ ] PROGRESS.md, BUGS.md, DECISIONS.md updated

---

## 📊 Migration Statistics

**Total Files to Update:** TBD
**Total Services:** 14
**Total Secrets:** ~30+
**Estimated Completion:** TBD

---

## 🚨 Important Notes

1. **No Deployment Yet:** This is code preparation only. No actual GCP resources will be created/deployed.
2. **Database Instance:** New Cloud SQL instance name needs to be decided (suggest: `pgp-psql`)
3. **Service Naming:** Remove `-10-26` suffix, use `-PGP` or clean names
4. **Domain:** Frontend domain may change from `www.paygateprime.com` to new domain (TBD)
5. **Testing:** All code changes are pre-deployment; actual testing will occur post-deployment

---

## 🎯 Next Steps

1. Execute Phase 1: Discovery & Analysis
2. Document all findings
3. Proceed with systematic code migration
4. Create deployment scripts (not to be executed)
5. Final verification before handoff for deployment

