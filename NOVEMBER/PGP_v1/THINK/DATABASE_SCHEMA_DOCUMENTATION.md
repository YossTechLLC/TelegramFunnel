# Database Schema & Deployment Documentation - PGP_v1 → pgp-live

**Project:** TelegramFunnel Payment System - PGP_v1 Architecture
**Target Environment:** pgp-live (GCP Project)
**Last Updated:** 2025-11-18
**Status:** 📋 DOCUMENTATION COMPLETE - Deployment NOT Started

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Deployment Status](#current-deployment-status)
3. [Phase 1: GCP Project Setup](#phase-1-gcp-project-setup)
4. [Phase 2: Secret Manager (75+ Secrets)](#phase-2-secret-manager-75-secrets)
5. [Phase 3: Cloud SQL + Database Schema](#phase-3-cloud-sql--database-schema)
6. [Phase 4: Cloud Tasks (17 Queues)](#phase-4-cloud-tasks-17-queues)
7. [Phase 5: Cloud Run (17 Services)](#phase-5-cloud-run-17-services)
8. [Phase 6: External Configuration](#phase-6-external-configuration)
9. [Phase 7: Testing & Validation](#phase-7-testing--validation)
10. [Phase 8: Production Hardening](#phase-8-production-hardening)
11. [Appendices](#appendices)

---

## Executive Summary

### Overview

This document provides the complete deployment plan for migrating the PGP_v1 payment system architecture from the legacy `telepay-459221` project to the new `pgp-live` GCP project. The deployment follows an 8-phase approach designed to minimize risk and ensure comprehensive validation at each stage.

### Key Metrics

- **Total Services:** 17 Cloud Run microservices
- **Database Tables:** 15 tables + 4 ENUM types
- **Secrets Required:** 75+ (API keys, credentials, configuration)
- **Cloud Tasks Queues:** 17 async processing queues
- **Deployment Timeline:** 5-8 weeks (full production deployment)
- **Accelerated Timeline:** 3-4 weeks (staging/testing deployment)

### Current Status

**Code Readiness:** ✅ **EXCELLENT**
- 17 microservices fully implemented and tested
- PGP_COMMON shared library achieving ~57% code reduction
- 852 Python files, comprehensive documentation
- All Phase 1-4 security fixes implemented in code

**Infrastructure Status:** ❌ **GREENFIELD**
- pgp-live GCP project exists but not configured
- No resources deployed (Cloud SQL, Cloud Run, Secret Manager)
- All deployment scripts ready and tested
- **Deployment Status: Phase 0 of 8 (Not Started)**

### Risk Assessment

**Overall Risk Level:** 🟡 **MEDIUM**

- **Code Quality Risk:** ✅ LOW (production-ready, well-tested)
- **Security Risk:** 🟡 MEDIUM (73 vulnerabilities identified, 7 CRITICAL)
- **Deployment Risk:** 🟡 MEDIUM (greenfield deployment, complex dependencies)
- **Operational Risk:** 🟡 MEDIUM (monitoring/alerting not yet configured)

### Cost Impact

Based on `GCP_SECURITY_VERIFICATION_REPORT.md`:

| Environment | Monthly Cost | Details |
|-------------|--------------|---------|
| Current (telepay-459221) | ~$185/month | Legacy monolithic architecture |
| pgp-live (Standard) | ~$303/month | 17 microservices, full monitoring |
| pgp-live (Optimized) | ~$253/month | Reduced min instances, optimized memory |
| **Monthly Increase** | **+$68 to +$118** | **37% to 64% increase** |

**One-Time Costs:**
- Security hardening: $45K-$80K (optional, recommended)
- External security audit: $15K-$30K (optional)
- Compliance certification (PCI DSS): $25K-$50K (if pursuing)

---

## Current Deployment Status

### Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    pgp-live GCP Project                      │
│                                                               │
│  Status: GREENFIELD (No resources deployed)                  │
│                                                               │
│  ❌ Cloud SQL Instance: Not created                          │
│  ❌ Secret Manager: 0 of 75+ secrets created                 │
│  ❌ Cloud Tasks: 0 of 17 queues created                      │
│  ❌ Cloud Run: 0 of 17 services deployed                     │
│  ❌ Monitoring: Not configured                               │
│  ❌ External Config: Not configured                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Phase Completion Status

| Phase | Description | Status | Progress |
|-------|-------------|--------|----------|
| Phase 1 | GCP Project Setup | ❌ Not Started | 0% |
| Phase 2 | Secret Manager | ❌ Not Started | 0% |
| Phase 3 | Cloud SQL + Migrations | ❌ Not Started | 0% |
| Phase 4 | Cloud Tasks Queues | ❌ Not Started | 0% |
| Phase 5 | Cloud Run Services | ❌ Not Started | 0% |
| Phase 6 | External Configuration | ❌ Not Started | 0% |
| Phase 7 | Testing & Validation | ❌ Not Started | 0% |
| Phase 8 | Production Hardening | 🟡 Partial (Code Only) | 50% |

**Overall Deployment Progress:** 6% (Phase 8 code-level security fixes only)

### Evidence

From `PROGRESS.md` (2025-11-16):
> "Infrastructure: ❌ NOT DEPLOYED - pgp-live project is greenfield"

From `DECISIONS.md` (2025-11-16):
> "Deployment Readiness: ⏳ STAGING READY, NOT PRODUCTION READY"

---

## Phase 1: GCP Project Setup

### Objective

Initialize the pgp-live GCP project with all required APIs, IAM roles, service accounts, and networking configuration.

### Prerequisites

- [ ] GCP Account with billing enabled
- [ ] Organization/Folder permissions (if applicable)
- [ ] Owner or Editor role on `pgp-live` project
- [ ] gcloud CLI installed and authenticated

### Checklist

#### 1.1 Project Verification

- [ ] Verify project exists: `gcloud projects describe pgp-live`
- [ ] Verify billing account linked
- [ ] Set default project: `gcloud config set project pgp-live`
- [ ] Verify current user has required permissions

#### 1.2 Enable Required GCP APIs

```bash
# Core compute and networking
gcloud services enable compute.googleapis.com
gcloud services enable vpcaccess.googleapis.com

# Cloud Run and containerization
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Cloud SQL
gcloud services enable sqladmin.googleapis.com
gcloud services enable sql-component.googleapis.com

# Cloud Tasks
gcloud services enable cloudtasks.googleapis.com

# Secret Manager
gcloud services enable secretmanager.googleapis.com

# Monitoring and logging
gcloud services enable logging.googleapis.com
gcloud services enable monitoring.googleapis.com
gcloud services enable cloudtrace.googleapis.com

# Cloud Scheduler (for broadcast service)
gcloud services enable cloudscheduler.googleapis.com

# IAM and security
gcloud services enable iam.googleapis.com
gcloud services enable iamcredentials.googleapis.com
```

**Checklist:**
- [ ] All APIs enabled successfully
- [ ] No billing quota errors
- [ ] API enablement propagated (wait 2-3 minutes)

#### 1.3 Create Service Accounts

Create dedicated service accounts for each major service:

```bash
# PGP Server (Telegram Bot)
gcloud iam service-accounts create pgp-server-sa \
    --display-name="PGP Server Service Account" \
    --description="Service account for PGP_SERVER_v1 Cloud Run service"

# PGP WebAPI
gcloud iam service-accounts create pgp-webapi-sa \
    --display-name="PGP WebAPI Service Account" \
    --description="Service account for PGP_WEBAPI_v1 Cloud Run service"

# PGP Orchestrator (Payment Processing)
gcloud iam service-accounts create pgp-orchestrator-sa \
    --display-name="PGP Orchestrator Service Account" \
    --description="Service account for PGP_ORCHESTRATOR_v1 Cloud Run service"

# PGP Notifications
gcloud iam service-accounts create pgp-notifications-sa \
    --display-name="PGP Notifications Service Account" \
    --description="Service account for PGP_NOTIFICATIONS_v1 Cloud Run service"

# PGP Broadcast
gcloud iam service-accounts create pgp-broadcast-sa \
    --display-name="PGP Broadcast Service Account" \
    --description="Service account for PGP_BROADCAST_v1 Cloud Run service"

# Generic service account for other services
gcloud iam service-accounts create pgp-services-sa \
    --display-name="PGP Services Service Account" \
    --description="Service account for remaining PGP services"
```

**Checklist:**
- [ ] All service accounts created
- [ ] Service account emails noted for Phase 5 deployment

#### 1.4 Configure IAM Roles

Grant necessary permissions to service accounts:

```bash
PROJECT_ID="pgp-live"

# Grant Cloud SQL Client role (all services need database access)
for SA in pgp-server-sa pgp-webapi-sa pgp-orchestrator-sa pgp-notifications-sa pgp-broadcast-sa pgp-services-sa; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/cloudsql.client"
done

# Grant Secret Manager Secret Accessor (all services need secrets)
for SA in pgp-server-sa pgp-webapi-sa pgp-orchestrator-sa pgp-notifications-sa pgp-broadcast-sa pgp-services-sa; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor"
done

# Grant Cloud Tasks Enqueuer (services that create tasks)
for SA in pgp-server-sa pgp-orchestrator-sa pgp-notifications-sa; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/cloudtasks.enqueuer"
done

# Grant Logging Writer (all services)
for SA in pgp-server-sa pgp-webapi-sa pgp-orchestrator-sa pgp-notifications-sa pgp-broadcast-sa pgp-services-sa; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/logging.logWriter"
done

# Grant Monitoring Metric Writer (all services)
for SA in pgp-server-sa pgp-webapi-sa pgp-orchestrator-sa pgp-notifications-sa pgp-broadcast-sa pgp-services-sa; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/monitoring.metricWriter"
done
```

**Checklist:**
- [ ] IAM roles granted to all service accounts
- [ ] Permissions verified: `gcloud projects get-iam-policy pgp-live`
- [ ] No permission errors in test commands

#### 1.5 Networking Configuration (Optional)

**Note:** Cloud Run can use default networking. Configure VPC only if:
- You need static IP addresses for external services
- You require Cloud NAT for outbound connections
- You want VPC Service Controls for additional security

**Skip this section for initial staging deployment.**

**For production deployment with static IPs:**

```bash
# Create VPC network
gcloud compute networks create pgp-vpc \
    --subnet-mode=custom \
    --bgp-routing-mode=regional

# Create subnet
gcloud compute networks subnets create pgp-subnet \
    --network=pgp-vpc \
    --region=us-central1 \
    --range=10.0.0.0/24

# Create Cloud NAT router
gcloud compute routers create pgp-router \
    --network=pgp-vpc \
    --region=us-central1

# Reserve static IP for NAT
gcloud compute addresses create pgp-nat-ip \
    --region=us-central1

# Configure Cloud NAT
gcloud compute routers nats create pgp-nat \
    --router=pgp-router \
    --region=us-central1 \
    --nat-external-ip-pool=pgp-nat-ip \
    --nat-all-subnet-ip-ranges

# Create Serverless VPC Connector
gcloud compute networks vpc-access connectors create pgp-connector \
    --region=us-central1 \
    --subnet=pgp-subnet \
    --min-instances=2 \
    --max-instances=10
```

**Checklist (if implementing):**
- [ ] VPC network created
- [ ] Subnet created
- [ ] Cloud NAT configured
- [ ] Serverless VPC Connector created
- [ ] Static IP noted for IP whitelist configuration

#### 1.6 Verification

```bash
# Verify project configuration
gcloud config get-value project

# List enabled APIs
gcloud services list --enabled

# List service accounts
gcloud iam service-accounts list

# Test IAM permissions
gcloud projects get-iam-policy pgp-live | grep pgp-server-sa

# Verify networking (if configured)
gcloud compute networks list
gcloud compute routers list
```

**Checklist:**
- [ ] Project ID confirmed as `pgp-live`
- [ ] All required APIs enabled (15+ services)
- [ ] Service accounts created (6 accounts)
- [ ] IAM roles properly assigned
- [ ] Networking configured (if applicable)
- [ ] No error messages in verification commands

### Time Estimate

- **Initial Setup:** 2-3 hours
- **Networking (Optional):** +2-3 hours
- **Verification:** 30 minutes

### Rollback Procedure

If Phase 1 needs to be rolled back:

1. Disable APIs: `gcloud services disable [API_NAME] --force`
2. Delete service accounts: `gcloud iam service-accounts delete [SA_EMAIL]`
3. Delete VPC resources (if created):
   - Delete VPC connector
   - Delete Cloud NAT
   - Delete router
   - Delete subnet
   - Delete VPC network

**Note:** Project itself is not deleted - only resources within it.

### Next Phase

Once Phase 1 is complete, proceed to **Phase 2: Secret Manager**.

---

## Phase 2: Secret Manager (75+ Secrets)

### Objective

Create all required secrets in Google Cloud Secret Manager for PGP_v1 services. Secrets include API keys, database credentials, encryption keys, service URLs, and configuration parameters.

### Prerequisites

- [ ] Phase 1 completed (GCP project setup)
- [ ] Secret Manager API enabled
- [ ] Service accounts created with Secret Accessor role
- [ ] Review `SECRET_SCHEME.md` for complete secret list

### Secret Categories

The PGP_v1 architecture requires 75+ secrets across 8 categories:

| Category | Count | Examples |
|----------|-------|----------|
| Database Credentials | 5 | DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, CLOUD_SQL_CONNECTION |
| Service URLs | 13 | PGP_SERVER_URL, PGP_ORCHESTRATOR_URL, PGP_SPLIT1_URL, etc. |
| Queue Names | 17 | PGP_ORCHESTRATOR_QUEUE, PGP_SPLIT1_ESTIMATE_QUEUE, etc. |
| API Keys | 8 | NOWPAYMENTS_API_KEY, TELEGRAM_BOT_TOKEN, SENDGRID_API_KEY, etc. |
| Encryption Keys | 6 | HMAC_SECRET_KEY, JWT_SECRET_KEY, DATABASE_SECRET_KEY, etc. |
| Wallet Keys | 3 | WALLET_PRIVATE_KEY, WALLET_ADDRESS, WALLET_PASSPHRASE |
| Configuration | 15 | LOG_LEVEL, BROADCAST_AUTO_INTERVAL, IP_WHITELIST, etc. |
| Telegram Config | 8 | TELEGRAM_BOT_USERNAME, CHANNEL_LINK_BASE_URL, etc. |

### Deployment Scripts

**Primary Script:** `TOOLS_SCRIPTS_TESTS/scripts/create_pgp_live_secrets.sh`
**Secondary Script:** `TOOLS_SCRIPTS_TESTS/scripts/grant_pgp_live_secret_access.sh`

### Checklist

#### 2.1 Review Secret Scheme

- [ ] Read `SECRET_SCHEME.md` completely
- [ ] Understand PGP_X_v1 naming scheme
- [ ] Note differences from old telepay-459221 scheme
- [ ] Identify secrets requiring manual values vs. auto-generated

#### 2.2 Prepare Secret Values

**CRITICAL: Use TEST/SANDBOX values for initial deployment**

For staging/testing deployment:
- [ ] Use NowPayments SANDBOX API key (not production)
- [ ] Use Telegram TEST bot token (create separate test bot)
- [ ] Generate NEW encryption keys (do not copy from production)
- [ ] Use TEST wallet addresses (testnet or low-value wallets)
- [ ] Set LOG_LEVEL=DEBUG for testing

For production deployment:
- [ ] Use production NowPayments API key
- [ ] Use production Telegram bot token (@PayGatePrime_bot)
- [ ] Use HSM-backed wallet keys (recommended) or secure key storage
- [ ] Set LOG_LEVEL=INFO

**Wallet Private Key Security:**
```
⚠️  CRITICAL SECURITY WARNING ⚠️

Wallet private keys control cryptocurrency funds. NEVER:
- Store in plaintext files
- Commit to git repositories
- Share via email/chat
- Use production keys in test environments

RECOMMENDED:
- Use Google Cloud KMS for production wallet keys
- Use hardware security modules (HSM) if available
- Implement multi-sig wallets for high-value operations
- Rotate keys regularly
- Maintain offline backup in secure location
```

#### 2.3 Customize Secret Creation Script

Edit `TOOLS_SCRIPTS_TESTS/scripts/create_pgp_live_secrets.sh`:

1. Review the warning at line 6:
   ```bash
   # IMPORTANT: DO NOT RUN THIS SCRIPT YET - Review and customize first
   ```

2. Verify PROJECT_ID (line 20):
   ```bash
   PROJECT_ID="pgp-live"
   ```

3. Update secret values (lines 30+):
   - Replace placeholder values with actual configuration
   - For TEST deployment: use sandbox/test values
   - For PRODUCTION deployment: use production values

4. Review sensitive secrets section:
   - Database credentials
   - API keys
   - Encryption keys
   - Wallet private keys

**Checklist:**
- [ ] Script reviewed and customized
- [ ] PROJECT_ID set to "pgp-live"
- [ ] Test vs. Production values determined
- [ ] Sensitive values prepared (not in script, will be set manually)
- [ ] Warning comment removed (indicates script is ready)

#### 2.4 Execute Secret Creation Script

**Test Deployment (Recommended First):**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/scripts

# Review script one more time
cat create_pgp_live_secrets.sh

# Execute (this will take 5-10 minutes)
bash create_pgp_live_secrets.sh

# Monitor progress
# Script will output: "Created secret: [SECRET_NAME]" for each secret
```

**Manual Secret Creation (for sensitive values):**

Some secrets should be created manually for security:

```bash
# Wallet private key (NEVER commit this value)
echo -n "YOUR_WALLET_PRIVATE_KEY_HERE" | \
    gcloud secrets create WALLET_PRIVATE_KEY \
    --project=pgp-live \
    --replication-policy="automatic" \
    --data-file=-

# NowPayments API key
echo -n "YOUR_NOWPAYMENTS_API_KEY" | \
    gcloud secrets create NOWPAYMENTS_API_KEY \
    --project=pgp-live \
    --replication-policy="automatic" \
    --data-file=-

# Telegram Bot Token
echo -n "YOUR_TELEGRAM_BOT_TOKEN" | \
    gcloud secrets create TELEGRAM_BOT_TOKEN \
    --project=pgp-live \
    --replication-policy="automatic" \
    --data-file=-

# Database Password
echo -n "YOUR_STRONG_DB_PASSWORD" | \
    gcloud secrets create DB_PASSWORD \
    --project=pgp-live \
    --replication-policy="automatic" \
    --data-file=-

# HMAC Secret Key (generate random 64-char hex)
openssl rand -hex 32 | \
    gcloud secrets create HMAC_SECRET_KEY \
    --project=pgp-live \
    --replication-policy="automatic" \
    --data-file=-

# JWT Secret Key (generate random 64-char string)
openssl rand -base64 48 | \
    gcloud secrets create JWT_SECRET_KEY \
    --project=pgp-live \
    --replication-policy="automatic" \
    --data-file=-

# Database Secret Key (for encryption at application level)
openssl rand -base64 48 | \
    gcloud secrets create DATABASE_SECRET_KEY \
    --project=pgp-live \
    --replication-policy="automatic" \
    --data-file=-
```

**Checklist:**
- [ ] Secret creation script executed successfully
- [ ] All 75+ secrets created
- [ ] Sensitive secrets created manually (not in script)
- [ ] No error messages during creation
- [ ] Secrets visible in GCP Console

#### 2.5 Grant Secret Access to Service Accounts

Execute the access grant script:

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/scripts

# Review script
cat grant_pgp_live_secret_access.sh

# Execute
bash grant_pgp_live_secret_access.sh
```

This script grants `roles/secretmanager.secretAccessor` to service accounts for their required secrets.

**Checklist:**
- [ ] Access grant script executed
- [ ] All service accounts have access to required secrets
- [ ] No permission errors

#### 2.6 Verification

```bash
# List all secrets
gcloud secrets list --project=pgp-live

# Count secrets (should be 75+)
gcloud secrets list --project=pgp-live --format="value(name)" | wc -l

# Test secret access (example)
gcloud secrets versions access latest --secret="DB_HOST" --project=pgp-live

# Verify service account access
gcloud secrets get-iam-policy TELEGRAM_BOT_TOKEN --project=pgp-live
```

**Manual Verification Checklist:**

Database Secrets (5):
- [ ] DB_HOST
- [ ] DB_NAME
- [ ] DB_USER
- [ ] DB_PASSWORD
- [ ] CLOUD_SQL_CONNECTION_NAME

Service URL Secrets (13):
- [ ] PGP_SERVER_URL
- [ ] PGP_WEBAPI_URL
- [ ] PGP_WEB_URL
- [ ] PGP_ORCHESTRATOR_URL
- [ ] PGP_NP_IPN_URL
- [ ] PGP_INVITE_URL
- [ ] PGP_SPLIT1_URL
- [ ] PGP_SPLIT2_URL
- [ ] PGP_SPLIT3_URL
- [ ] PGP_HOSTPAY1_URL
- [ ] PGP_HOSTPAY2_URL
- [ ] PGP_HOSTPAY3_URL
- [ ] PGP_NOTIFICATIONS_URL

Queue Name Secrets (17):
- [ ] PGP_ORCHESTRATOR_QUEUE
- [ ] PGP_INVITE_QUEUE
- [ ] PGP_SPLIT1_ESTIMATE_QUEUE
- [ ] PGP_SPLIT1_BATCH_QUEUE
- [ ] PGP_SPLIT2_SWAP_QUEUE
- [ ] PGP_SPLIT2_RESPONSE_QUEUE
- [ ] PGP_SPLIT3_CLIENT_QUEUE
- [ ] PGP_SPLIT3_RESPONSE_QUEUE
- [ ] PGP_HOSTPAY_TRIGGER_QUEUE
- [ ] PGP_HOSTPAY1_RESPONSE_QUEUE
- [ ] PGP_HOSTPAY2_STATUS_QUEUE
- [ ] PGP_HOSTPAY3_PAYMENT_QUEUE
- [ ] PGP_HOSTPAY3_RETRY_QUEUE
- [ ] PGP_ACCUMULATOR_QUEUE
- [ ] PGP_ACCUMULATOR_RESPONSE_QUEUE
- [ ] PGP_BATCHPROCESSOR_QUEUE
- [ ] PGP_MICROBATCHPROCESSOR_QUEUE

API Key Secrets (8):
- [ ] NOWPAYMENTS_API_KEY
- [ ] TELEGRAM_BOT_TOKEN
- [ ] SENDGRID_API_KEY
- [ ] SENDGRID_FROM_EMAIL
- [ ] TELEGRAM_BOT_USERNAME
- [ ] NOWPAYMENTS_IPN_SECRET_KEY
- [ ] And others as defined in SECRET_SCHEME.md

Encryption Secrets (6):
- [ ] HMAC_SECRET_KEY
- [ ] JWT_SECRET_KEY
- [ ] DATABASE_SECRET_KEY
- [ ] ENCRYPTION_KEY_V1
- [ ] ENCRYPTION_KEY_V2
- [ ] SIGNATURE_TIMESTAMP_MAX_AGE

Wallet Secrets (3):
- [ ] WALLET_PRIVATE_KEY
- [ ] WALLET_ADDRESS
- [ ] WALLET_PASSPHRASE (if applicable)

Configuration Secrets (15):
- [ ] LOG_LEVEL
- [ ] BROADCAST_AUTO_INTERVAL
- [ ] BROADCAST_MANUAL_INTERVAL
- [ ] IP_WHITELIST
- [ ] RATE_LIMIT_MAX_REQUESTS
- [ ] And others as defined in SECRET_SCHEME.md

**Verification Complete When:**
- [ ] Secret count ≥ 75
- [ ] All categories have secrets created
- [ ] Service accounts can access secrets
- [ ] Test secret retrieval successful
- [ ] No "NOT_FOUND" or "PERMISSION_DENIED" errors

### Time Estimate

- **Script customization:** 1-2 hours
- **Script execution:** 10-15 minutes
- **Manual secret creation:** 30 minutes
- **Access grant execution:** 5 minutes
- **Verification:** 30 minutes

**Total:** 2-3 hours

### Security Considerations

**Production Secrets Checklist:**

- [ ] Wallet private keys use KMS or HSM
- [ ] API keys rotated regularly (every 90 days)
- [ ] Database password is strong (32+ characters, random)
- [ ] Encryption keys are cryptographically random
- [ ] Secret versions enabled (for rotation)
- [ ] Audit logging enabled for secret access
- [ ] Secrets not stored in git or local files
- [ ] Test secrets separate from production secrets

### Rollback Procedure

If Phase 2 needs to be rolled back:

```bash
# Delete all secrets (WARNING: Cannot be undone after 7 days)
gcloud secrets list --project=pgp-live --format="value(name)" | \
    xargs -I {} gcloud secrets delete {} --project=pgp-live --quiet

# Or delete specific secret
gcloud secrets delete [SECRET_NAME] --project=pgp-live
```

**Note:** Deleted secrets enter a 7-day grace period and can be restored. After 7 days, they are permanently deleted.

### Next Phase

Once Phase 2 is complete, proceed to **Phase 3: Cloud SQL + Database Schema**.

---

## Phase 3: Cloud SQL + Database Schema

### Objective

Deploy the complete PostgreSQL database schema to pgp-live Cloud SQL instance, including all tables, ENUMs, indexes, and initial data.

### Prerequisites

- [ ] Phase 1 completed (GCP project setup)
- [ ] Phase 2 completed (Secret Manager secrets created)
- [ ] Cloud SQL API enabled
- [ ] Database credentials created as secrets
- [ ] Review `TOOLS_SCRIPTS_TESTS/migrations/` directory

### Database Architecture

**Instance Details:**
- **Instance ID:** `pgp-telepaypsql`
- **Connection Name:** `pgp-live:us-central1:pgp-telepaypsql`
- **Database Engine:** PostgreSQL 14
- **Region:** us-central1
- **Tier:** db-custom-2-7680 (2 vCPU, 7.5 GB RAM)

**Schema Overview:**
- **15 Tables:** Complete payment processing schema
- **4 ENUM Types:** subscription_status, payment_status, payout_status, conversion_status
- **87 Currency Mappings:** currency_to_network table initial data
- **1 Legacy User:** UUID 00000000-0000-0000-0000-000000000000 (system user)

### Migration Scripts

**Location:** `TOOLS_SCRIPTS_TESTS/migrations/`

**Execution Order:**
1. `001_create_complete_schema.sql` - Complete database schema
2. `002_populate_currency_to_network.sql` - Currency mapping data
3. `003_rename_gcwebhook1_columns.sql` - Column renaming (optional, for migration from old schema)

**Rollback Scripts:**
- `001_rollback.sql` - Drop all tables and ENUMs
- `003_rollback.sql` - Revert column renames

### Checklist

#### 3.1 Create Cloud SQL Instance

**Option A: Using gcloud CLI (Recommended)**

```bash
# Create Cloud SQL instance
gcloud sql instances create pgp-telepaypsql \
    --project=pgp-live \
    --database-version=POSTGRES_14 \
    --tier=db-custom-2-7680 \
    --region=us-central1 \
    --network=projects/pgp-live/global/networks/default \
    --allocated-ip-range-name=google-managed-services-default \
    --database-flags=max_connections=100 \
    --backup \
    --backup-start-time=03:00 \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=04 \
    --retained-backups-count=7 \
    --retained-transaction-log-days=7

# Set root password (use strong password from DB_PASSWORD secret)
DB_PASSWORD=$(gcloud secrets versions access latest --secret=DB_PASSWORD --project=pgp-live)
gcloud sql users set-password postgres \
    --instance=pgp-telepaypsql \
    --project=pgp-live \
    --password="$DB_PASSWORD"
```

**Option B: Using GCP Console**

1. Navigate to Cloud SQL → Create Instance
2. Choose PostgreSQL
3. Configure:
   - Instance ID: `pgp-telepaypsql`
   - Password: Use value from DB_PASSWORD secret
   - Version: PostgreSQL 14
   - Region: us-central1
   - Zone: Any
   - Machine type: Standard (2 vCPU, 7.5 GB)
   - Storage: 10 GB SSD (auto-increase enabled)
   - Backups: Enabled (daily at 3:00 AM)
   - Point-in-time recovery: Enabled
4. Click Create

**Checklist:**
- [ ] Cloud SQL instance created
- [ ] Instance status: RUNNABLE
- [ ] Connection name verified: `pgp-live:us-central1:pgp-telepaypsql`
- [ ] Root password set
- [ ] Backups configured
- [ ] Maintenance window configured

#### 3.2 Create Database

```bash
# Create database
gcloud sql databases create telepaydb \
    --instance=pgp-telepaypsql \
    --project=pgp-live

# Verify database created
gcloud sql databases list --instance=pgp-telepaypsql --project=pgp-live
```

**Checklist:**
- [ ] Database `telepaydb` created
- [ ] Database visible in instance

#### 3.3 Create Database User (Application Access)

```bash
# Get DB user and password from secrets
DB_USER=$(gcloud secrets versions access latest --secret=DB_USER --project=pgp-live)
DB_PASSWORD=$(gcloud secrets versions access latest --secret=DB_PASSWORD --project=pgp-live)

# Create application user
gcloud sql users create "$DB_USER" \
    --instance=pgp-telepaypsql \
    --project=pgp-live \
    --password="$DB_PASSWORD"

# Verify user created
gcloud sql users list --instance=pgp-telepaypsql --project=pgp-live
```

**Checklist:**
- [ ] Application user created
- [ ] Password set from DB_PASSWORD secret
- [ ] User visible in instance

#### 3.4 Deploy Complete Schema (Migration 001)

**Using Python Deployment Script (Recommended):**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/tools

# Review script configuration
cat deploy_complete_schema_pgp_live.py

# Verify script is configured for pgp-live
# Line 22: PROJECT_ID = "pgp-live"
# Line 23: INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"

# Execute deployment
python3 deploy_complete_schema_pgp_live.py

# Script will:
# 1. Connect to Cloud SQL via Cloud SQL Connector
# 2. Execute 001_create_complete_schema.sql
# 3. Execute 002_populate_currency_to_network.sql
# 4. Verify schema deployment
# 5. Print confirmation
```

**Manual Deployment (Alternative):**

If deployment script fails, use Cloud SQL Proxy:

```bash
# Download Cloud SQL Proxy
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.7.0/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy

# Start proxy in background
./cloud-sql-proxy pgp-live:us-central1:pgp-telepaypsql --port=5432 &
PROXY_PID=$!

# Wait for proxy to initialize
sleep 5

# Execute migration 001
psql "host=127.0.0.1 port=5432 dbname=telepaydb user=postgres" \
    -f ../migrations/001_create_complete_schema.sql

# Execute migration 002
psql "host=127.0.0.1 port=5432 dbname=telepaydb user=postgres" \
    -f ../migrations/002_populate_currency_to_network.sql

# Kill proxy
kill $PROXY_PID
```

**Checklist:**
- [ ] Migration script executed without errors
- [ ] All 15 tables created
- [ ] All 4 ENUM types created
- [ ] 87 currency mappings inserted
- [ ] No SQL errors in output

#### 3.5 Verify Schema Deployment

**Using Verification Script:**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/tools

# Run schema verification
python3 verify_schema_match.py

# Expected output:
# ✅ All 15 tables exist
# ✅ All 4 ENUM types exist
# ✅ 87 currency mappings exist
# ✅ Schema deployment verified
```

**Manual Verification:**

```bash
# Connect via Cloud SQL Proxy
./cloud-sql-proxy pgp-live:us-central1:pgp-telepaypsql --port=5432 &
sleep 5

# Verify tables
psql "host=127.0.0.1 port=5432 dbname=telepaydb user=postgres" -c "\dt"

# Verify ENUMs
psql "host=127.0.0.1 port=5432 dbname=telepaydb user=postgres" -c "\dT"

# Verify currency_to_network data
psql "host=127.0.0.1 port=5432 dbname=telepaydb user=postgres" -c "SELECT COUNT(*) FROM currency_to_network;"

# Expected: 87 rows
```

**Schema Verification Checklist:**

**Tables (15):**
- [ ] registered_users
- [ ] closed_channels
- [ ] subscriptions
- [ ] broadcast_manager
- [ ] conversation_state
- [ ] donation_keypad_state
- [ ] failed_transactions
- [ ] landing_page_visits
- [ ] nowpayments_transactions
- [ ] payout_requests
- [ ] batch_conversions
- [ ] processed_payments
- [ ] currency_to_network
- [ ] [additional tables as defined in 001_create_complete_schema.sql]

**ENUM Types (4):**
- [ ] subscription_status (active, expired, cancelled)
- [ ] payment_status (pending, completed, failed, cancelled)
- [ ] payout_status (pending, processing, completed, failed)
- [ ] conversion_status (pending, processing, completed, failed)

**Initial Data:**
- [ ] currency_to_network: 87 rows
- [ ] Legacy user UUID: 00000000-0000-0000-0000-000000000000 (if applicable)

**Indexes and Constraints:**
- [ ] Primary keys on all tables
- [ ] Foreign key constraints (where applicable)
- [ ] Unique constraints (email, channel_id, etc.)
- [ ] Indexes on frequently queried columns

#### 3.6 Configure Cloud SQL IAM Database Authentication (Optional - Recommended for Production)

**For enhanced security, enable IAM authentication:**

```bash
# Enable IAM authentication on instance
gcloud sql instances patch pgp-telepaypsql \
    --database-flags=cloudsql.iam_authentication=on \
    --project=pgp-live

# Create IAM database user for each service account
for SA in pgp-server-sa pgp-webapi-sa pgp-orchestrator-sa pgp-notifications-sa pgp-broadcast-sa pgp-services-sa; do
    gcloud sql users create "${SA}@pgp-live.iam" \
        --instance=pgp-telepaypsql \
        --type=CLOUD_IAM_SERVICE_ACCOUNT \
        --project=pgp-live
done
```

**Note:** This requires updating database connection code to use IAM authentication. Skip for initial deployment if using password-based authentication.

**Checklist (if implementing):**
- [ ] IAM authentication enabled
- [ ] IAM database users created for service accounts
- [ ] Connection strings updated to use IAM auth
- [ ] Application code updated to use IAM auth

#### 3.7 Configure Database Connections in Secrets

Update database connection secrets with actual values:

```bash
# Update DB_HOST secret (for Cloud SQL Proxy)
echo -n "/cloudsql/pgp-live:us-central1:pgp-telepaypsql" | \
    gcloud secrets versions add DB_HOST --project=pgp-live --data-file=-

# Update CLOUD_SQL_CONNECTION_NAME secret
echo -n "pgp-live:us-central1:pgp-telepaypsql" | \
    gcloud secrets versions add CLOUD_SQL_CONNECTION_NAME --project=pgp-live --data-file=-

# DB_NAME should already be set to "telepaydb"
# DB_USER should already be set
# DB_PASSWORD should already be set
```

**Checklist:**
- [ ] DB_HOST secret updated
- [ ] CLOUD_SQL_CONNECTION_NAME secret updated
- [ ] DB_NAME verified (telepaydb)
- [ ] DB_USER verified
- [ ] DB_PASSWORD verified

### Database Schema Details

#### Core Tables

**1. registered_users**
- Stores user registration data
- Telegram user ID, email, subscription status
- Timestamps: created_at, last_login

**2. subscriptions**
- Active and historical subscription records
- Links to registered_users
- Tracks subscription_status ENUM
- Payment amounts, expiration dates

**3. closed_channels**
- Private channel information
- Telegram channel ID, invite link
- Owner information

**4. nowpayments_transactions**
- NowPayments webhook data
- Payment status tracking
- Currency, amount, wallet addresses

**5. processed_payments**
- Idempotency tracking for payment webhooks
- Columns: pgp_orchestrator_processed, pgp_orchestrator_processed_at
- Prevents duplicate payment processing

**6. broadcast_manager**
- Scheduled broadcast messages
- Broadcast type (auto vs manual)
- Execution timestamps, status

**7. conversation_state**
- Telegram bot conversation state tracking
- User ID, state key, state data JSON

**8. donation_keypad_state**
- Donation flow state management
- Custom amount input tracking

**9. payout_requests**
- Cryptocurrency payout tracking
- User wallet addresses
- Payout status ENUM

**10. batch_conversions**
- Batch payment processing
- Conversion status ENUM
- Accumulation and processing timestamps

**11-15. Additional Tables**
- failed_transactions
- landing_page_visits
- And others as defined in schema

#### ENUM Types

**subscription_status:**
- `active` - Active subscription
- `expired` - Expired subscription
- `cancelled` - User-cancelled subscription

**payment_status:**
- `pending` - Payment initiated
- `completed` - Payment confirmed
- `failed` - Payment failed
- `cancelled` - Payment cancelled

**payout_status:**
- `pending` - Payout requested
- `processing` - Payout in progress
- `completed` - Payout sent
- `failed` - Payout failed

**conversion_status:**
- `pending` - Conversion queued
- `processing` - Conversion in progress
- `completed` - Conversion successful
- `failed` - Conversion failed

### Time Estimate

- **Instance creation:** 10-15 minutes
- **Database and user setup:** 5 minutes
- **Schema deployment:** 5-10 minutes
- **Verification:** 10-15 minutes
- **IAM authentication (optional):** +30 minutes

**Total:** 30-45 minutes (without IAM), 60-75 minutes (with IAM)

### Rollback Procedure

**Drop All Tables and ENUMs:**

```bash
# Execute rollback script
psql "host=127.0.0.1 port=5432 dbname=telepaydb user=postgres" \
    -f TOOLS_SCRIPTS_TESTS/migrations/001_rollback.sql

# Verify tables dropped
psql "host=127.0.0.1 port=5432 dbname=telepaydb user=postgres" -c "\dt"
# Should return "Did not find any relations"
```

**Delete Cloud SQL Instance (Complete Rollback):**

```bash
# WARNING: This permanently deletes all data
gcloud sql instances delete pgp-telepaypsql \
    --project=pgp-live \
    --quiet
```

**Note:** Cloud SQL instances can be restored from backups within the retention period (7 days by default).

### Troubleshooting

**Issue: Connection timeout to Cloud SQL**
- **Solution:** Verify instance status is RUNNABLE
- **Solution:** Check firewall rules if using VPC
- **Solution:** Ensure Cloud SQL Admin API is enabled

**Issue: Migration script fails with permission error**
- **Solution:** Verify database user has CREATE TABLE permissions
- **Solution:** Try connecting as postgres superuser
- **Solution:** Grant necessary permissions: `GRANT ALL ON DATABASE telepaydb TO [DB_USER];`

**Issue: ENUM already exists error**
- **Solution:** Schema was partially deployed, run rollback script first
- **Solution:** Manually drop conflicting ENUMs: `DROP TYPE IF EXISTS [ENUM_NAME] CASCADE;`

**Issue: Foreign key constraint violation**
- **Solution:** Ensure tables are created in correct order
- **Solution:** Check migration script for proper ordering
- **Solution:** Temporarily disable foreign key checks if necessary (not recommended)

### Next Phase

Once Phase 3 is complete, proceed to **Phase 4: Cloud Tasks (17 Queues)**.

---

## Phase 4: Cloud Tasks (17 Queues)

### Objective

Create all Cloud Tasks queues required for asynchronous payment processing and inter-service communication.

### Prerequisites

- [ ] Phase 1 completed (GCP project setup)
- [ ] Cloud Tasks API enabled
- [ ] Service accounts have Cloud Tasks Enqueuer role
- [ ] Review queue architecture in DECISIONS.md

### Queue Architecture

PGP_v1 uses Cloud Tasks for reliable asynchronous processing across 17 queues organized into 5 categories:

**Orchestration Queues (2):**
- `pgp-orchestrator-queue-v1` - Main payment orchestration
- `pgp-invite-queue-v1` - Telegram channel invites

**Payment Splitting Queues (6):**
- `pgp-split1-estimate-queue-v1` - Split estimation stage 1
- `pgp-split1-batch-queue-v1` - Split batching stage 1
- `pgp-split2-swap-queue-v1` - Split swap stage 2
- `pgp-split2-response-queue-v1` - Split response stage 2
- `pgp-split3-client-queue-v1` - Split client notification stage 3
- `pgp-split3-response-queue-v1` - Split response stage 3

**Payout Processing Queues (5):**
- `pgp-hostpay-trigger-queue-v1` - Payout trigger
- `pgp-hostpay1-response-queue-v1` - Payout stage 1 response
- `pgp-hostpay2-status-queue-v1` - Payout stage 2 status
- `pgp-hostpay3-payment-queue-v1` - Payout stage 3 payment
- `pgp-hostpay3-retry-queue-v1` - Payout stage 3 retry

**Batch Processing Queues (4):**
- `pgp-accumulator-queue-v1` - Payment accumulation
- `pgp-accumulator-response-queue-v1` - Accumulation response
- `pgp-batchprocessor-queue-v1` - Batch processing
- `pgp-microbatchprocessor-queue-v1` - Micro-batch processing

### Deployment Scripts

**Location:** `TOOLS_SCRIPTS_TESTS/scripts/`

**Scripts by Category:**
- `deploy_gcwebhook_tasks_queues.sh` - Orchestrator and invite queues
- `deploy_gcsplit_tasks_queues.sh` - Payment splitting queues
- `deploy_hostpay_tasks_queues.sh` - Payout processing queues
- `deploy_accumulator_tasks_queues.sh` - Batch processing queues

### Checklist

#### 4.1 Review Queue Configuration

Each queue has specific configuration parameters:

**Standard Configuration:**
- **max-dispatches-per-second:** 100 (can be adjusted per queue)
- **max-concurrent-dispatches:** 10 (can be adjusted per queue)
- **max-attempts:** 5 (with exponential backoff)
- **min-backoff:** 10s
- **max-backoff:** 300s
- **max-retry-duration:** 3600s (1 hour)

**High-Priority Queues (payment processing):**
- Higher dispatch rates (500-1000/second)
- Higher concurrency (50-100)
- Shorter retry duration (30 minutes)

**Low-Priority Queues (batch processing):**
- Lower dispatch rates (10-50/second)
- Lower concurrency (5-10)
- Longer retry duration (2-4 hours)

**Checklist:**
- [ ] Queue configuration reviewed
- [ ] Dispatch rates appropriate for expected load
- [ ] Retry configuration suitable for each queue type

#### 4.2 Deploy Orchestration Queues

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/scripts

# Review script
cat deploy_gcwebhook_tasks_queues.sh

# Verify PROJECT_ID is set to pgp-live
# Verify LOCATION is us-central1

# Execute deployment
bash deploy_gcwebhook_tasks_queues.sh

# Expected output:
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-orchestrator-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-invite-queue-v1]
```

**Checklist:**
- [ ] `pgp-orchestrator-queue-v1` created
- [ ] `pgp-invite-queue-v1` created
- [ ] No error messages
- [ ] Queues visible in GCP Console

#### 4.3 Deploy Payment Splitting Queues

```bash
# Execute deployment
bash deploy_gcsplit_tasks_queues.sh

# Expected output:
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-split1-estimate-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-split1-batch-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-split2-swap-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-split2-response-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-split3-client-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-split3-response-queue-v1]
```

**Checklist:**
- [ ] All 6 split queues created
- [ ] No error messages
- [ ] Queues visible in GCP Console

#### 4.4 Deploy Payout Processing Queues

```bash
# Execute deployment
bash deploy_hostpay_tasks_queues.sh

# Expected output:
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-hostpay-trigger-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-hostpay1-response-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-hostpay2-status-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-hostpay3-payment-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-hostpay3-retry-queue-v1]
```

**Checklist:**
- [ ] All 5 hostpay queues created
- [ ] No error messages
- [ ] Queues visible in GCP Console

#### 4.5 Deploy Batch Processing Queues

```bash
# Execute deployment
bash deploy_accumulator_tasks_queues.sh

# Expected output:
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-accumulator-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-accumulator-response-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-batchprocessor-queue-v1]
# Created queue [projects/pgp-live/locations/us-central1/queues/pgp-microbatchprocessor-queue-v1]
```

**Checklist:**
- [ ] All 4 batch processing queues created
- [ ] No error messages
- [ ] Queues visible in GCP Console

#### 4.6 Update Queue Name Secrets

Update Secret Manager with queue resource names:

```bash
PROJECT_ID="pgp-live"
LOCATION="us-central1"

# Update each queue name secret with full resource path
echo -n "projects/${PROJECT_ID}/locations/${LOCATION}/queues/pgp-orchestrator-queue-v1" | \
    gcloud secrets versions add PGP_ORCHESTRATOR_QUEUE --project=$PROJECT_ID --data-file=-

echo -n "projects/${PROJECT_ID}/locations/${LOCATION}/queues/pgp-invite-queue-v1" | \
    gcloud secrets versions add PGP_INVITE_QUEUE --project=$PROJECT_ID --data-file=-

# Repeat for all 17 queues...
# (See complete list in Phase 2 verification checklist)
```

**Or use automation script (if available):**

```bash
# Update all queue secrets
bash TOOLS_SCRIPTS_TESTS/scripts/update_queue_secrets.sh
```

**Checklist:**
- [ ] All 17 queue name secrets updated
- [ ] Secrets contain full resource paths (not just queue names)
- [ ] Format: `projects/pgp-live/locations/us-central1/queues/[QUEUE_NAME]`

#### 4.7 Verification

```bash
# List all queues
gcloud tasks queues list --project=pgp-live --location=us-central1

# Count queues (should be 17)
gcloud tasks queues list --project=pgp-live --location=us-central1 --format="value(name)" | wc -l

# Describe specific queue
gcloud tasks queues describe pgp-orchestrator-queue-v1 \
    --project=pgp-live \
    --location=us-central1

# Test queue accessibility (create a test task - will fail gracefully if target service not deployed)
gcloud tasks create-http-task test-task-$(date +%s) \
    --queue=pgp-orchestrator-queue-v1 \
    --location=us-central1 \
    --project=pgp-live \
    --url=https://example.com/test \
    --method=POST \
    --header="Content-Type:application/json" \
    --body-content='{"test": true}'

# Delete test task
gcloud tasks delete test-task-* --queue=pgp-orchestrator-queue-v1 --location=us-central1 --project=pgp-live --quiet
```

**Queue Verification Checklist:**

**Orchestration (2):**
- [ ] pgp-orchestrator-queue-v1
- [ ] pgp-invite-queue-v1

**Payment Splitting (6):**
- [ ] pgp-split1-estimate-queue-v1
- [ ] pgp-split1-batch-queue-v1
- [ ] pgp-split2-swap-queue-v1
- [ ] pgp-split2-response-queue-v1
- [ ] pgp-split3-client-queue-v1
- [ ] pgp-split3-response-queue-v1

**Payout Processing (5):**
- [ ] pgp-hostpay-trigger-queue-v1
- [ ] pgp-hostpay1-response-queue-v1
- [ ] pgp-hostpay2-status-queue-v1
- [ ] pgp-hostpay3-payment-queue-v1
- [ ] pgp-hostpay3-retry-queue-v1

**Batch Processing (4):**
- [ ] pgp-accumulator-queue-v1
- [ ] pgp-accumulator-response-queue-v1
- [ ] pgp-batchprocessor-queue-v1
- [ ] pgp-microbatchprocessor-queue-v1

**Verification Complete When:**
- [ ] Queue count = 17
- [ ] All queues in READY state
- [ ] No creation errors
- [ ] Test task creation successful
- [ ] Queue secrets updated in Secret Manager

### Queue Configuration Details

**High-Priority Queues (Payment Critical):**

- pgp-orchestrator-queue-v1
- pgp-split1-estimate-queue-v1
- pgp-hostpay3-payment-queue-v1

Configuration:
```yaml
max_dispatches_per_second: 500
max_concurrent_dispatches: 50
max_attempts: 5
min_backoff: 5s
max_backoff: 120s
```

**Medium-Priority Queues (Processing):**

- All split queues (2, 3 stages)
- hostpay response queues

Configuration:
```yaml
max_dispatches_per_second: 100
max_concurrent_dispatches: 20
max_attempts: 5
min_backoff: 10s
max_backoff: 300s
```

**Low-Priority Queues (Batch/Background):**

- pgp-accumulator-queue-v1
- pgp-batchprocessor-queue-v1
- pgp-microbatchprocessor-queue-v1

Configuration:
```yaml
max_dispatches_per_second: 50
max_concurrent_dispatches: 10
max_attempts: 3
min_backoff: 30s
max_backoff: 600s
```

### Time Estimate

- **Script review:** 15 minutes
- **Queue deployment (all 4 scripts):** 10 minutes
- **Secret updates:** 15 minutes
- **Verification:** 10 minutes

**Total:** 50 minutes

### Rollback Procedure

```bash
# Delete all queues
gcloud tasks queues list --project=pgp-live --location=us-central1 --format="value(name)" | \
    xargs -I {} gcloud tasks queues delete {} --location=us-central1 --project=pgp-live --quiet

# Or delete specific queue
gcloud tasks queues delete pgp-orchestrator-queue-v1 \
    --location=us-central1 \
    --project=pgp-live \
    --quiet
```

**Note:** Deleting a queue also deletes all tasks in the queue. This cannot be undone.

### Troubleshooting

**Issue: Queue already exists error**
- **Solution:** Queue was created previously, skip creation or delete and recreate
- **Solution:** Verify queue name matches expected convention

**Issue: Permission denied when creating queue**
- **Solution:** Verify Cloud Tasks Admin role: `gcloud projects get-iam-policy pgp-live | grep cloudtasks`
- **Solution:** Grant role: `gcloud projects add-iam-policy-binding pgp-live --member=user:[YOUR_EMAIL] --role=roles/cloudtasks.admin`

**Issue: Queue creation hangs**
- **Solution:** Cloud Tasks API may not be fully enabled, wait 2-3 minutes
- **Solution:** Verify API status: `gcloud services list --enabled | grep cloudtasks`

**Issue: Cannot create task in queue**
- **Solution:** Verify service account has Cloud Tasks Enqueuer role
- **Solution:** Check queue state is READY, not PAUSED
- **Solution:** Verify target URL is accessible (for testing, use dummy URL)

### Next Phase

Once Phase 4 is complete, proceed to **Phase 5: Cloud Run (17 Services)**.

---

## Phase 5: Cloud Run (17 Services)

### Objective

Deploy all 17 PGP_v1 microservices to Cloud Run in correct dependency order, with proper configuration, environment variables, and resource allocation.

### Prerequisites

- [ ] Phase 1 completed (GCP project setup)
- [ ] Phase 2 completed (Secrets created)
- [ ] Phase 3 completed (Database deployed)
- [ ] Phase 4 completed (Queues created)
- [ ] Docker images built and pushed to Artifact Registry
- [ ] Review `deploy_all_pgp_services.sh` script

### Service Architecture

**17 Cloud Run Services organized in 5 deployment phases:**

**Phase 5.1: Core Infrastructure (3 services)**
1. `pgp-server-v1` - Telegram bot + webhook receiver
2. `pgp-web-v1` - React frontend (SPA)
3. `pgp-webapi-v1` - REST API backend

**Phase 5.2: Payment Processing Pipeline (6 services)**
4. `pgp-np-ipn-v1` - NowPayments IPN webhook
5. `pgp-orchestrator-v1` - Payment orchestration
6. `pgp-invite-v1` - Telegram channel invites
7. `pgp-split1-v1` - Payment splitting stage 1
8. `pgp-split2-v1` - Payment splitting stage 2
9. `pgp-split3-v1` - Payment splitting stage 3

**Phase 5.3: Payout Services (3 services)**
10. `pgp-hostpay1-v1` - Payout hosting stage 1
11. `pgp-hostpay2-v1` - Payout hosting stage 2
12. `pgp-hostpay3-v1` - Payout hosting stage 3

**Phase 5.4: Batch Processing (3 services)**
13. `pgp-accumulator-v1` - Payment accumulation
14. `pgp-batchprocessor-v1` - Batch processing
15. `pgp-microbatchprocessor-v1` - Micro-batch processing

**Phase 5.5: Notification & Broadcast (2 services)**
16. `pgp-notifications-v1` - Telegram notifications
17. `pgp-broadcast-v1` - Scheduled broadcasts

### Service Configuration

**Resource Allocation Matrix:**

| Service | Memory | CPU | Min Instances | Max Instances | Timeout | Priority |
|---------|--------|-----|---------------|---------------|---------|----------|
| pgp-server-v1 | 1Gi | 1 | 1 | 20 | 300s | CRITICAL |
| pgp-web-v1 | 128Mi | 0.08 | 0 | 5 | 60s | HIGH |
| pgp-webapi-v1 | 512Mi | 1 | 0 | 10 | 120s | HIGH |
| pgp-np-ipn-v1 | 512Mi | 1 | 0 | 20 | 120s | CRITICAL |
| pgp-orchestrator-v1 | 512Mi | 1 | 0 | 20 | 300s | CRITICAL |
| pgp-invite-v1 | 512Mi | 1 | 0 | 10 | 120s | HIGH |
| pgp-split1-v1 | 512Mi | 1 | 0 | 15 | 180s | HIGH |
| pgp-split2-v1 | 512Mi | 1 | 0 | 15 | 180s | HIGH |
| pgp-split3-v1 | 512Mi | 1 | 0 | 15 | 180s | HIGH |
| pgp-hostpay1-v1 | 512Mi | 1 | 0 | 15 | 180s | HIGH |
| pgp-hostpay2-v1 | 512Mi | 1 | 0 | 15 | 180s | HIGH |
| pgp-hostpay3-v1 | 512Mi | 1 | 0 | 15 | 180s | HIGH |
| pgp-accumulator-v1 | 512Mi | 1 | 0 | 10 | 300s | MEDIUM |
| pgp-batchprocessor-v1 | 512Mi | 1 | 0 | 10 | 300s | MEDIUM |
| pgp-microbatchprocessor-v1 | 512Mi | 1 | 0 | 10 | 300s | MEDIUM |
| pgp-notifications-v1 | 512Mi | 1 | 0 | 10 | 120s | HIGH |
| pgp-broadcast-v1 | 512Mi | 1 | 1 | 5 | 180s | MEDIUM |

**Cost Optimization Notes:**
- Services with `min-instances: 0` scale to zero when idle (save costs)
- Services with `min-instances: 1` are always warm (critical services)
- Adjust max-instances based on expected load and budget

### Deployment Master Script

**Location:** `TOOLS_SCRIPTS_TESTS/scripts/deploy_all_pgp_services.sh`

**What it does:**
1. Builds Docker images for all 17 services
2. Pushes images to Google Artifact Registry
3. Deploys services in dependency order
4. Configures environment variables from Secret Manager
5. Sets up IAM permissions
6. Configures service-to-service authentication
7. Verifies deployment health

### Checklist

#### 5.1 Prepare Docker Images

**Option A: Build all images locally (Recommended for first deployment)**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1

# Build each service
services=(
    "PGP_SERVER_v1"
    "PGP_WEB_v1"
    "PGP_WEBAPI_v1"
    "PGP_NP_IPN_v1"
    "PGP_ORCHESTRATOR_v1"
    "PGP_INVITE_v1"
    "PGP_SPLIT1_v1"
    "PGP_SPLIT2_v1"
    "PGP_SPLIT3_v1"
    "PGP_HOSTPAY1_v1"
    "PGP_HOSTPAY2_v1"
    "PGP_HOSTPAY3_v1"
    "PGP_ACCUMULATOR_v1"
    "PGP_BATCHPROCESSOR_v1"
    "PGP_MICROBATCHPROCESSOR_v1"
    "PGP_NOTIFICATIONS_v1"
    "PGP_BROADCAST_v1"
)

for service in "${services[@]}"; do
    echo "Building $service..."
    cd "$service"
    docker build -t "gcr.io/pgp-live/${service,,}:latest" .
    cd ..
done
```

**Option B: Use Cloud Build (Automated)**

```bash
# Submit all builds to Cloud Build
for service in "${services[@]}"; do
    gcloud builds submit "./$service" \
        --project=pgp-live \
        --tag="gcr.io/pgp-live/${service,,}:latest"
done
```

**Checklist:**
- [ ] All 17 Docker images built successfully
- [ ] No build errors
- [ ] Images tagged with `gcr.io/pgp-live/[service]:latest`

#### 5.2 Push Images to Container Registry

```bash
# Configure Docker for gcr.io
gcloud auth configure-docker gcr.io

# Push all images
for service in "${services[@]}"; do
    echo "Pushing $service..."
    docker push "gcr.io/pgp-live/${service,,}:latest"
done

# Verify images pushed
gcloud container images list --project=pgp-live
```

**Checklist:**
- [ ] All 17 images pushed to gcr.io/pgp-live
- [ ] Images visible in GCP Console (Container Registry)
- [ ] Image sizes reasonable (500MB-1GB per service)

#### 5.3 Review Deployment Script

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/scripts

# Review master deployment script
cat deploy_all_pgp_services.sh

# Verify configuration:
# - PROJECT_ID="pgp-live"
# - REGION="us-central1"
# - All service names match
# - Environment variables reference Secret Manager secrets
# - IAM roles configured correctly
```

**Key Configuration Items to Verify:**

1. **Project ID:** `pgp-live` (line ~15)
2. **Region:** `us-central1` (line ~16)
3. **Service Account Mapping:** Correct SA for each service (line ~20-40)
4. **Environment Variables:** All secrets referenced correctly (line ~100-500)
5. **Memory Allocation:** Matches table above (line ~600-800)
6. **Scaling Configuration:** Min/max instances correct (line ~900-1100)

**Checklist:**
- [ ] Deployment script reviewed
- [ ] PROJECT_ID set to `pgp-live`
- [ ] Region set to `us-central1`
- [ ] Service accounts mapped correctly
- [ ] Environment variables reference pgp-live secrets
- [ ] Resource allocation appropriate

#### 5.4 Deploy Phase 5.1: Core Infrastructure Services

**Deploy in order:**

```bash
# 1. PGP Server (Telegram bot)
gcloud run deploy pgp-server-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --image=gcr.io/pgp-live/pgp_server_v1:latest \
    --platform=managed \
    --service-account=pgp-server-sa@pgp-live.iam.gserviceaccount.com \
    --memory=1Gi \
    --cpu=1 \
    --min-instances=1 \
    --max-instances=20 \
    --timeout=300s \
    --set-env-vars="^::^PROJECT_ID=pgp-live" \
    --set-secrets="TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,DB_HOST=DB_HOST:latest,DB_NAME=DB_NAME:latest,DB_USER=DB_USER:latest,DB_PASSWORD=DB_PASSWORD:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,HMAC_SECRET_KEY=HMAC_SECRET_KEY:latest,JWT_SECRET_KEY=JWT_SECRET_KEY:latest" \
    --add-cloudsql-instances=pgp-live:us-central1:pgp-telepaypsql \
    --allow-unauthenticated

# 2. PGP Web (Frontend)
gcloud run deploy pgp-web-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --image=gcr.io/pgp-live/pgp_web_v1:latest \
    --platform=managed \
    --memory=128Mi \
    --cpu=0.08 \
    --min-instances=0 \
    --max-instances=5 \
    --timeout=60s \
    --allow-unauthenticated

# 3. PGP WebAPI (Backend API)
gcloud run deploy pgp-webapi-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --image=gcr.io/pgp-live/pgp_webapi_v1:latest \
    --platform=managed \
    --service-account=pgp-webapi-sa@pgp-live.iam.gserviceaccount.com \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=10 \
    --timeout=120s \
    --set-env-vars="^::^PROJECT_ID=pgp-live" \
    --set-secrets="DB_HOST=DB_HOST:latest,DB_NAME=DB_NAME:latest,DB_USER=DB_USER:latest,DB_PASSWORD=DB_PASSWORD:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,JWT_SECRET_KEY=JWT_SECRET_KEY:latest" \
    --add-cloudsql-instances=pgp-live:us-central1:pgp-telepaypsql \
    --no-allow-unauthenticated

# Wait for deployments to complete
sleep 30
```

**Checklist:**
- [ ] pgp-server-v1 deployed and READY
- [ ] pgp-web-v1 deployed and READY
- [ ] pgp-webapi-v1 deployed and READY
- [ ] All services have URLs assigned
- [ ] Health checks passing

#### 5.5 Update Service URL Secrets

After core services are deployed, update their URL secrets:

```bash
# Get service URLs
SERVER_URL=$(gcloud run services describe pgp-server-v1 --project=pgp-live --region=us-central1 --format="value(status.url)")
WEB_URL=$(gcloud run services describe pgp-web-v1 --project=pgp-live --region=us-central1 --format="value(status.url)")
WEBAPI_URL=$(gcloud run services describe pgp-webapi-v1 --project=pgp-live --region=us-central1 --format="value(status.url)")

# Update secrets
echo -n "$SERVER_URL" | gcloud secrets versions add PGP_SERVER_URL --project=pgp-live --data-file=-
echo -n "$WEB_URL" | gcloud secrets versions add PGP_WEB_URL --project=pgp-live --data-file=-
echo -n "$WEBAPI_URL" | gcloud secrets versions add PGP_WEBAPI_URL --project=pgp-live --data-file=-
```

**Checklist:**
- [ ] Service URLs retrieved
- [ ] URL secrets updated
- [ ] URLs follow pattern: `https://[service]-[hash]-uc.a.run.app`

#### 5.6 Deploy Phase 5.2-5.5: Remaining Services

**Use Master Script (Recommended):**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/scripts

# Execute master deployment script
# This will deploy remaining 14 services in correct order
bash deploy_all_pgp_services.sh

# Script will:
# 1. Deploy each service sequentially
# 2. Wait for each deployment to complete
# 3. Update URL secrets after each deployment
# 4. Verify health of each service
# 5. Print summary at the end

# Estimated time: 45-60 minutes for all services
```

**Manual Deployment (Alternative):**

If master script fails, deploy each service manually:

```bash
# Phase 5.2: Payment Processing Pipeline
gcloud run deploy pgp-np-ipn-v1 --[full configuration]...
gcloud run deploy pgp-orchestrator-v1 --[full configuration]...
gcloud run deploy pgp-invite-v1 --[full configuration]...
gcloud run deploy pgp-split1-v1 --[full configuration]...
gcloud run deploy pgp-split2-v1 --[full configuration]...
gcloud run deploy pgp-split3-v1 --[full configuration]...

# Phase 5.3: Payout Services
gcloud run deploy pgp-hostpay1-v1 --[full configuration]...
gcloud run deploy pgp-hostpay2-v1 --[full configuration]...
gcloud run deploy pgp-hostpay3-v1 --[full configuration]...

# Phase 5.4: Batch Processing
gcloud run deploy pgp-accumulator-v1 --[full configuration]...
gcloud run deploy pgp-batchprocessor-v1 --[full configuration]...
gcloud run deploy pgp-microbatchprocessor-v1 --[full configuration]...

# Phase 5.5: Notification & Broadcast
gcloud run deploy pgp-notifications-v1 --[full configuration]...
gcloud run deploy pgp-broadcast-v1 --[full configuration]...
```

**Checklist:**
- [ ] All 17 services deployed
- [ ] All services in READY state
- [ ] All service URLs updated in Secret Manager
- [ ] No deployment errors

#### 5.7 Configure Service-to-Service Authentication

Services need to call each other securely:

```bash
# Grant Cloud Run Invoker role for service-to-service calls
# Format: ServiceA's SA needs Invoker role on ServiceB

# PGP Orchestrator can invoke Split services
for service in pgp-split1-v1 pgp-split2-v1 pgp-split3-v1; do
    gcloud run services add-iam-policy-binding $service \
        --project=pgp-live \
        --region=us-central1 \
        --member="serviceAccount:pgp-orchestrator-sa@pgp-live.iam.gserviceaccount.com" \
        --role="roles/run.invoker"
done

# PGP Orchestrator can invoke Hostpay services
for service in pgp-hostpay1-v1 pgp-hostpay2-v1 pgp-hostpay3-v1; do
    gcloud run services add-iam-policy-binding $service \
        --project=pgp-live \
        --region=us-central1 \
        --member="serviceAccount:pgp-orchestrator-sa@pgp-live.iam.gserviceaccount.com" \
        --role="roles/run.invoker"
done

# PGP Server can invoke Notifications service
gcloud run services add-iam-policy-binding pgp-notifications-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --member="serviceAccount:pgp-server-sa@pgp-live.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Add similar bindings for other service-to-service calls
# (See full list in deploy_all_pgp_services.sh)
```

**Checklist:**
- [ ] Service-to-service IAM bindings configured
- [ ] Authentication tested between services
- [ ] No 403 Forbidden errors in service logs

#### 5.8 Configure Cloud Scheduler for Broadcast Service

```bash
# Create scheduler job for broadcast service
BROADCAST_URL=$(gcloud run services describe pgp-broadcast-v1 --project=pgp-live --region=us-central1 --format="value(status.url)")

gcloud scheduler jobs create http pgp-broadcast-scheduler \
    --project=pgp-live \
    --location=us-central1 \
    --schedule="*/5 * * * *" \
    --uri="${BROADCAST_URL}/api/broadcast/execute" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{"source":"cloud_scheduler"}' \
    --oidc-service-account-email=pgp-broadcast-sa@pgp-live.iam.gserviceaccount.com \
    --oidc-token-audience="${BROADCAST_URL}"

# Enable scheduler
gcloud scheduler jobs resume pgp-broadcast-scheduler --project=pgp-live --location=us-central1
```

**Checklist:**
- [ ] Cloud Scheduler job created
- [ ] Schedule set to every 5 minutes
- [ ] OIDC authentication configured
- [ ] Scheduler enabled

#### 5.9 Verification

**List All Services:**

```bash
# List all Cloud Run services
gcloud run services list --project=pgp-live --region=us-central1

# Expected output: 17 services, all READY
```

**Test Service Health:**

```bash
# Test each service health endpoint
services=(pgp-server-v1 pgp-web-v1 pgp-webapi-v1 pgp-np-ipn-v1 pgp-orchestrator-v1 pgp-invite-v1 pgp-split1-v1 pgp-split2-v1 pgp-split3-v1 pgp-hostpay1-v1 pgp-hostpay2-v1 pgp-hostpay3-v1 pgp-accumulator-v1 pgp-batchprocessor-v1 pgp-microbatchprocessor-v1 pgp-notifications-v1 pgp-broadcast-v1)

for service in "${services[@]}"; do
    URL=$(gcloud run services describe $service --project=pgp-live --region=us-central1 --format="value(status.url)")
    echo "Testing $service: $URL"
    curl -s -o /dev/null -w "%{http_code}" "$URL/health" || echo " - Health endpoint may not exist"
done
```

**Check Service Logs:**

```bash
# View logs for each service to verify successful initialization
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=pgp-server-v1" \
    --project=pgp-live \
    --limit=50 \
    --format=json

# Look for initialization success messages
# Example: "✅ All components initialized successfully"
```

**Service Deployment Verification Checklist:**

**Core Infrastructure (3):**
- [ ] pgp-server-v1 - READY, URL assigned, health check passing
- [ ] pgp-web-v1 - READY, URL assigned, serving frontend
- [ ] pgp-webapi-v1 - READY, URL assigned, API responding

**Payment Processing (6):**
- [ ] pgp-np-ipn-v1 - READY, webhook endpoint accessible
- [ ] pgp-orchestrator-v1 - READY, can enqueue tasks
- [ ] pgp-invite-v1 - READY, Telegram integration working
- [ ] pgp-split1-v1 - READY, stage 1 processing functional
- [ ] pgp-split2-v1 - READY, stage 2 processing functional
- [ ] pgp-split3-v1 - READY, stage 3 processing functional

**Payout Services (3):**
- [ ] pgp-hostpay1-v1 - READY, stage 1 functional
- [ ] pgp-hostpay2-v1 - READY, stage 2 functional
- [ ] pgp-hostpay3-v1 - READY, stage 3 functional

**Batch Processing (3):**
- [ ] pgp-accumulator-v1 - READY, accumulation working
- [ ] pgp-batchprocessor-v1 - READY, batch processing working
- [ ] pgp-microbatchprocessor-v1 - READY, micro-batch working

**Notification & Broadcast (2):**
- [ ] pgp-notifications-v1 - READY, Telegram notifications working
- [ ] pgp-broadcast-v1 - READY, Cloud Scheduler triggering

**Overall Verification:**
- [ ] All 17 services deployed and READY
- [ ] No services in ERROR or FAILED state
- [ ] All service URLs updated in Secret Manager
- [ ] Service-to-service authentication configured
- [ ] Cloud Scheduler configured for broadcast service
- [ ] No critical errors in logs
- [ ] Database connections working (check service logs)
- [ ] Cloud Tasks queues receiving tasks (check queue metrics)

### Time Estimate

- **Image building:** 30-45 minutes (all services)
- **Image pushing:** 15-20 minutes
- **Service deployment:** 45-60 minutes (sequential)
- **Configuration and verification:** 30 minutes

**Total:** 2-3 hours

### Troubleshooting

**Issue: Deployment fails with "container failed to start"**
- **Solution:** Check service logs: `gcloud logging read "resource.labels.service_name=[SERVICE_NAME]"`
- **Solution:** Verify Docker image builds locally: `docker run -it [IMAGE_NAME]`
- **Solution:** Check for missing environment variables or secrets

**Issue: Service crashes on startup**
- **Solution:** Review logs for Python exceptions (import errors, missing dependencies)
- **Solution:** Verify all secrets are accessible
- **Solution:** Check database connection (Cloud SQL instance accessible?)
- **Solution:** Verify PGP_COMMON library is included in Docker image

**Issue: "Permission denied" when accessing secrets**
- **Solution:** Verify service account has Secret Accessor role
- **Solution:** Check secret IAM policy: `gcloud secrets get-iam-policy [SECRET_NAME]`
- **Solution:** Grant access: `gcloud secrets add-iam-policy-binding [SECRET] --member=serviceAccount:[SA] --role=roles/secretmanager.secretAccessor`

**Issue: Database connection timeout**
- **Solution:** Verify Cloud SQL instance is RUNNABLE
- **Solution:** Check `--add-cloudsql-instances` flag in deployment command
- **Solution:** Verify CLOUD_SQL_CONNECTION_NAME secret is correct
- **Solution:** Ensure service account has Cloud SQL Client role

**Issue: Service-to-service call returns 403 Forbidden**
- **Solution:** Grant Cloud Run Invoker role on target service
- **Solution:** Verify OIDC token is being sent in Authorization header
- **Solution:** Check target service IAM policy

**Issue: Cloud Scheduler job fails**
- **Solution:** Verify OIDC configuration (service account and audience)
- **Solution:** Check broadcast service URL is correct
- **Solution:** Review scheduler job logs: `gcloud scheduler jobs describe [JOB_NAME]`

### Rollback Procedure

**Delete All Services:**

```bash
# Delete all Cloud Run services
gcloud run services list --project=pgp-live --region=us-central1 --format="value(metadata.name)" | \
    xargs -I {} gcloud run services delete {} --project=pgp-live --region=us-central1 --quiet

# Delete Cloud Scheduler job
gcloud scheduler jobs delete pgp-broadcast-scheduler --project=pgp-live --location=us-central1 --quiet
```

**Delete Specific Service:**

```bash
gcloud run services delete [SERVICE_NAME] \
    --project=pgp-live \
    --region=us-central1 \
    --quiet
```

**Note:** Deleting a service does not delete its Docker images in Container Registry. Images can be reused for redeployment.

### Next Phase

Once Phase 5 is complete, proceed to **Phase 6: External Configuration**.

---

## Phase 6: External Configuration

### Objective

Configure external services (NowPayments, Telegram, DNS, Cloudflare) to route traffic to pgp-live Cloud Run services.

### Prerequisites

- [ ] Phase 5 completed (All services deployed)
- [ ] Access to NowPayments merchant account
- [ ] Access to Telegram Bot settings
- [ ] Access to domain registrar (paygateprime.com)
- [ ] Access to Cloudflare account
- [ ] Service URLs documented

### Checklist

#### 6.1 Configure NowPayments IPN Callback

**Get PGP_NP_IPN_v1 Service URL:**

```bash
NP_IPN_URL=$(gcloud run services describe pgp-np-ipn-v1 --project=pgp-live --region=us-central1 --format="value(status.url)")
echo "NowPayments IPN URL: ${NP_IPN_URL}/webhooks/nowpayments"
```

**Update NowPayments Dashboard:**

1. Log in to NowPayments merchant dashboard
2. Navigate to Settings → API → IPN Callbacks
3. Update IPN callback URL to: `[NP_IPN_URL]/webhooks/nowpayments`
4. Set IPN secret key (must match NOWPAYMENTS_IPN_SECRET_KEY secret)
5. Enable IPN notifications
6. Test IPN endpoint (NowPayments provides test button)

**Checklist:**
- [ ] NowPayments IPN URL updated
- [ ] IPN secret key configured
- [ ] Test IPN successful (check service logs)
- [ ] Webhook receives test payment notifications

#### 6.2 Configure Telegram Bot Webhook

**Get PGP_SERVER_v1 Service URL:**

```bash
SERVER_URL=$(gcloud run services describe pgp-server-v1 --project=pgp-live --region=us-central1 --format="value(status.url)")
BOT_TOKEN=$(gcloud secrets versions access latest --secret=TELEGRAM_BOT_TOKEN --project=pgp-live)

echo "Telegram Webhook URL: ${SERVER_URL}/webhooks/telegram"
```

**Set Telegram Webhook:**

```bash
# Set webhook via Telegram Bot API
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"${SERVER_URL}/webhooks/telegram\"}"

# Verify webhook set
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

**Expected Response:**
```json
{
  "ok": true,
  "result": {
    "url": "https://pgp-server-v1-[hash]-uc.a.run.app/webhooks/telegram",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "max_connections": 40
  }
}
```

**Checklist:**
- [ ] Telegram webhook URL set
- [ ] Webhook info shows correct URL
- [ ] pending_update_count is 0
- [ ] Test bot command works (send /start to bot)
- [ ] Bot responds correctly

#### 6.3 Configure DNS Records (paygateprime.com)

**Current Architecture:**
- Frontend: paygateprime.com → PGP_WEB_v1
- API: api.paygateprime.com → PGP_WEBAPI_v1
- Webhooks: webhooks.paygateprime.com → PGP_SERVER_v1 (optional)

**Get Service URLs:**

```bash
WEB_URL=$(gcloud run services describe pgp-web-v1 --project=pgp-live --region=us-central1 --format="value(status.url)")
WEBAPI_URL=$(gcloud run services describe pgp-webapi-v1 --project=pgp-live --region=us-central1 --format="value(status.url)")
SERVER_URL=$(gcloud run services describe pgp-server-v1 --project=pgp-live --region=us-central1 --format="value(status.url)")

echo "Frontend: $WEB_URL"
echo "API: $WEBAPI_URL"
echo "Server: $SERVER_URL"
```

**DNS Configuration Options:**

**Option A: Direct CNAME (Simple, No Custom Domain Needed)**
- Use Cloud Run default URLs
- No DNS configuration required
- URLs are: `https://[service]-[hash]-uc.a.run.app`
- **Recommended for staging/testing**

**Option B: Custom Domain via Cloud Run Domain Mapping**
- Cloud Run manages SSL certificates automatically
- Requires domain verification
- **Recommended for production**

**Option C: Cloudflare + Load Balancer**
- Full Cloudflare features (WAF, DDoS protection)
- Requires GCP Load Balancer
- More complex, higher cost
- **Recommended for high-traffic production**

#### 6.4 Configure Custom Domain (Option B - Cloud Run Domain Mapping)

**Map Frontend Domain:**

```bash
# Add domain mapping for paygateprime.com
gcloud run domain-mappings create \
    --service=pgp-web-v1 \
    --domain=paygateprime.com \
    --project=pgp-live \
    --region=us-central1

# Get DNS records to configure
gcloud run domain-mappings describe paygateprime.com \
    --project=pgp-live \
    --region=us-central1
```

**Output will show required DNS records:**
```
resourceRecords:
- name: paygateprime.com
  rrdata: ghs.googlehosted.com
  type: A
```

**Configure DNS at Registrar:**

1. Log in to domain registrar (e.g., GoDaddy, Namecheap)
2. Add A record:
   - Host: @ (or paygateprime.com)
   - Points to: ghs.googlehosted.com
   - TTL: 3600
3. Wait for DNS propagation (5-60 minutes)

**Repeat for API subdomain:**

```bash
# Add domain mapping for api.paygateprime.com
gcloud run domain-mappings create \
    --service=pgp-webapi-v1 \
    --domain=api.paygateprime.com \
    --project=pgp-live \
    --region=us-central1

# Configure DNS CNAME
# Host: api
# Points to: ghs.googlehosted.com
```

**Checklist:**
- [ ] Domain mappings created
- [ ] DNS records configured at registrar
- [ ] DNS propagation verified: `nslookup paygateprime.com`
- [ ] SSL certificate issued (automatic, check domain mapping status)
- [ ] Frontend accessible at https://paygateprime.com
- [ ] API accessible at https://api.paygateprime.com
- [ ] HTTPS working (no certificate warnings)

#### 6.5 Configure Cloudflare (Option C - If Using Cloudflare)

**Note:** This is optional and adds complexity. Only implement if you need Cloudflare's advanced features.

**Cloudflare Configuration:**

1. Add paygateprime.com to Cloudflare
2. Update nameservers at domain registrar to Cloudflare's NS
3. Configure proxy settings:
   - Proxy status: Proxied (orange cloud)
   - SSL/TLS mode: Full (strict)
4. Configure Page Rules:
   - Always Use HTTPS
   - Automatic HTTPS Rewrites
5. Configure Firewall Rules (optional):
   - Allow only expected traffic patterns
   - Rate limiting on API endpoints
6. Configure WAF (Web Application Firewall):
   - OWASP Core Ruleset
   - Custom rules for payment endpoints

**Create GCP Load Balancer:**

```bash
# Reserve static IP
gcloud compute addresses create pgp-lb-ip \
    --global \
    --project=pgp-live

# Create backend service for each Cloud Run service
# Configure load balancer routing
# Point Cloudflare to Load Balancer IP
```

**Full instructions:** See GCP Load Balancer documentation

**Checklist (if implementing):**
- [ ] Cloudflare account configured
- [ ] Nameservers updated
- [ ] SSL/TLS configured
- [ ] WAF rules configured
- [ ] Load Balancer created
- [ ] Traffic routing through Cloudflare
- [ ] Firewall rules tested

#### 6.6 Update Service URL Secrets (Final)

After custom domains are configured, update service URL secrets:

```bash
# If using custom domains
echo -n "https://paygateprime.com" | gcloud secrets versions add PGP_WEB_URL --project=pgp-live --data-file=-
echo -n "https://api.paygateprime.com" | gcloud secrets versions add PGP_WEBAPI_URL --project=pgp-live --data-file=-

# If using Cloud Run default URLs (no custom domain)
# URLs already updated in Phase 5.5
```

**Checklist:**
- [ ] Service URL secrets updated with final URLs
- [ ] Services can call each other using updated URLs
- [ ] No broken inter-service communication

#### 6.7 Configure IP Whitelisting (If Applicable)

If using Cloud NAT for static IPs (Phase 1.5):

**Get Static NAT IP:**

```bash
NAT_IP=$(gcloud compute addresses describe pgp-nat-ip --region=us-central1 --project=pgp-live --format="value(address)")
echo "Static NAT IP: $NAT_IP"
```

**Update IP Whitelist Secret:**

```bash
# Add NAT IP to IP_WHITELIST secret
# Format: comma-separated list of IPs
# Example: "1.2.3.4,5.6.7.8,10.0.0.0/24"

WHITELIST="$NAT_IP,$(gcloud secrets versions access latest --secret=IP_WHITELIST --project=pgp-live)"
echo -n "$WHITELIST" | gcloud secrets versions add IP_WHITELIST --project=pgp-live --data-file=-
```

**Whitelist IPs at External Services:**

1. NowPayments: Add NAT IP to allowed IPs
2. Any other services requiring IP whitelist

**Checklist:**
- [ ] Static NAT IP documented
- [ ] IP_WHITELIST secret updated
- [ ] External services configured to accept NAT IP
- [ ] IP whitelist tested (service logs show successful validation)

#### 6.8 Verification

**Test Complete Payment Flow:**

1. **User Registration:**
   - Navigate to https://paygateprime.com (or Cloud Run URL)
   - Register new account
   - Verify registration email received (if SendGrid configured)
   - Check `registered_users` table in database

2. **Payment Processing:**
   - Initiate test payment (use NowPayments sandbox)
   - Verify NowPayments IPN received (check pgp-np-ipn-v1 logs)
   - Verify payment orchestration (check pgp-orchestrator-v1 logs)
   - Verify database updates (`nowpayments_transactions`, `processed_payments`)

3. **Telegram Bot:**
   - Send /start command to bot
   - Verify bot responds
   - Test subscription purchase flow
   - Verify channel invite received

4. **Broadcast System:**
   - Wait for Cloud Scheduler trigger (every 5 minutes)
   - Verify broadcast execution (check pgp-broadcast-v1 logs)
   - Verify scheduled messages sent

**External Configuration Verification Checklist:**

- [ ] NowPayments IPN endpoint receiving webhooks
- [ ] Telegram bot responding to commands
- [ ] Custom domains accessible (if configured)
- [ ] SSL certificates valid (no warnings)
- [ ] Frontend loading correctly
- [ ] API endpoints responding
- [ ] Complete payment flow working end-to-end
- [ ] Cloudflare protection active (if configured)
- [ ] IP whitelist validation working
- [ ] No external access errors

### Time Estimate

- **NowPayments configuration:** 15 minutes
- **Telegram webhook setup:** 10 minutes
- **DNS configuration:** 30-60 minutes (including propagation wait)
- **Cloudflare setup (optional):** +60-90 minutes
- **Verification:** 30 minutes

**Total:** 1.5-3 hours (without Cloudflare), 3-4.5 hours (with Cloudflare)

### Rollback Procedure

**Revert to Old Configuration:**

1. **NowPayments:** Change IPN URL back to old service
2. **Telegram:** Set webhook back to old service: `curl -X POST "https://api.telegram.org/bot[TOKEN]/setWebhook" -d "url=[OLD_URL]"`
3. **DNS:** Update DNS records to point to old services
4. **Cloudflare:** Update proxy targets to old infrastructure

**Note:** DNS changes take 5-60 minutes to propagate. During this time, traffic may be split between old and new services.

### Next Phase

Once Phase 6 is complete, proceed to **Phase 7: Testing & Validation**.

---

## Phase 7: Testing & Validation

### Objective

Comprehensive testing of all pgp-live services to ensure correct functionality, performance, and security before production traffic.

### Prerequisites

- [ ] Phase 6 completed (External configuration)
- [ ] All services deployed and accessible
- [ ] Test data available (test users, test payments)
- [ ] Monitoring configured (Cloud Logging accessible)

### Testing Categories

**7 Testing Phases:**
1. Unit Tests (Code-level)
2. Integration Tests (Service-to-service)
3. End-to-End Tests (Complete user flows)
4. Load Tests (Performance)
5. Security Tests (Vulnerability validation)
6. Database Tests (Data integrity)
7. Monitoring Tests (Observability)

### Checklist

#### 7.1 Unit Tests

**Run Existing Test Suites:**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1

# Activate virtual environment
source .venv/bin/activate

# Run unit tests for each service
services=(PGP_SERVER_v1 PGP_WEBAPI_v1 PGP_ORCHESTRATOR_v1 PGP_COMMON)

for service in "${services[@]}"; do
    echo "Testing $service..."
    cd "$service"
    python -m pytest tests/ -v
    cd ..
done
```

**Checklist:**
- [ ] All unit tests pass
- [ ] No Python import errors
- [ ] No uncaught exceptions
- [ ] Test coverage ≥ 70% (if measured)

#### 7.2 Integration Tests

**Test Service-to-Service Communication:**

**Available Test Scripts:**
- `TOOLS_SCRIPTS_TESTS/tests/test_subscription_integration.py`
- `TOOLS_SCRIPTS_TESTS/tests/test_subscription_load.py`

**Run Integration Tests:**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/tests

# Set environment variables for pgp-live
export PROJECT_ID="pgp-live"
export PGP_ORCHESTRATOR_URL=$(gcloud secrets versions access latest --secret=PGP_ORCHESTRATOR_URL --project=pgp-live)
export PGP_SERVER_URL=$(gcloud secrets versions access latest --secret=PGP_SERVER_URL --project=pgp-live)

# Run integration tests
python test_subscription_integration.py

# Expected output:
# ✅ Test 1: User registration - PASS
# ✅ Test 2: Payment initiation - PASS
# ✅ Test 3: IPN webhook handling - PASS
# ✅ Test 4: Subscription activation - PASS
# ✅ Test 5: Channel invite - PASS
```

**Manual Integration Tests:**

**Test 1: NowPayments IPN → Orchestrator Flow**

```bash
# Simulate NowPayments IPN webhook
NP_IPN_URL=$(gcloud secrets versions access latest --secret=PGP_NP_IPN_URL --project=pgp-live)
HMAC_KEY=$(gcloud secrets versions access latest --secret=HMAC_SECRET_KEY --project=pgp-live)

# Create test payload
PAYLOAD='{"payment_id":"test123","payment_status":"finished","price_amount":10,"price_currency":"usd","pay_address":"0xTestAddress"}'

# Calculate HMAC signature
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "${TIMESTAMP}.${PAYLOAD}" | openssl dgst -sha256 -hmac "$HMAC_KEY" | cut -d' ' -f2)

# Send webhook
curl -X POST "$NP_IPN_URL/webhooks/nowpayments" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $SIGNATURE" \
    -H "X-Timestamp: $TIMESTAMP" \
    -d "$PAYLOAD"

# Check logs for successful processing
gcloud logging read "resource.labels.service_name=pgp-np-ipn-v1" --project=pgp-live --limit=10
```

**Test 2: Telegram Bot → Server Flow**

```bash
# Send test message to bot via Telegram
# (Use Telegram mobile app or web client)
# Send: /start

# Check logs
gcloud logging read "resource.labels.service_name=pgp-server-v1" --project=pgp-live --limit=10

# Expected: "Received /start command from user [USER_ID]"
```

**Test 3: Cloud Tasks Queue Processing**

```bash
# Enqueue test task
ORCHESTRATOR_URL=$(gcloud secrets versions access latest --secret=PGP_ORCHESTRATOR_URL --project=pgp-live)
QUEUE_NAME="pgp-orchestrator-queue-v1"

gcloud tasks create-http-task test-task-$(date +%s) \
    --queue=$QUEUE_NAME \
    --location=us-central1 \
    --project=pgp-live \
    --url="${ORCHESTRATOR_URL}/process" \
    --method=POST \
    --header="Content-Type:application/json" \
    --body-content='{"test": true}' \
    --oidc-service-account-email=pgp-orchestrator-sa@pgp-live.iam.gserviceaccount.com

# Check task execution in logs
gcloud logging read "resource.labels.service_name=pgp-orchestrator-v1" --project=pgp-live --limit=10
```

**Checklist:**
- [ ] NowPayments IPN → Orchestrator flow working
- [ ] Telegram webhook → Server flow working
- [ ] Cloud Tasks enqueue and process successfully
- [ ] Service-to-service authentication working
- [ ] No 403 or 500 errors in service calls
- [ ] Database updates reflect correct data

#### 7.3 End-to-End Tests

**Complete User Journey Tests:**

**E2E Test 1: New User Registration → Payment → Subscription Activation**

1. Navigate to https://paygateprime.com
2. Register new user account (email: test@example.com)
3. Verify email confirmation sent (check SendGrid logs)
4. Log in to account
5. Select subscription plan ($10/month)
6. Initiate payment via NowPayments (use sandbox)
7. Complete payment (simulate successful payment in NowPayments dashboard)
8. Verify subscription activated (check database: `SELECT * FROM subscriptions WHERE user_id='[USER_ID]'`)
9. Verify Telegram channel invite received
10. Join private channel via invite link
11. Verify access granted to channel

**E2E Test 2: Broadcast Message Delivery**

1. Create scheduled broadcast in admin panel (or database)
2. Wait for Cloud Scheduler trigger (every 5 minutes)
3. Verify broadcast executed (check pgp-broadcast-v1 logs)
4. Verify Telegram messages sent to all users
5. Check broadcast_manager table for completion status

**E2E Test 3: Payout Request → Cryptocurrency Transfer**

1. User requests payout (trigger payout flow)
2. Verify payout_requests table updated
3. Verify Cloud Tasks enqueued (pgp-hostpay-trigger-queue-v1)
4. Check pgp-hostpay1-v1 logs (stage 1 processing)
5. Check pgp-hostpay2-v1 logs (stage 2 status check)
6. Check pgp-hostpay3-v1 logs (stage 3 payment execution)
7. Verify blockchain transaction (check wallet explorer)
8. Verify payout_requests status = 'completed'

**Checklist:**
- [ ] Complete registration → payment → subscription flow works
- [ ] Broadcast system delivers messages to all users
- [ ] Payout system processes requests correctly
- [ ] All database tables update correctly
- [ ] No errors in any service logs
- [ ] User experience is smooth (no delays >5 seconds)

#### 7.4 Load Tests

**Performance Testing:**

**Load Test Script:** `TOOLS_SCRIPTS_TESTS/tests/test_subscription_load.py`

**Configure Load Test:**

```python
# Edit test_subscription_load.py
CONCURRENT_USERS = 100  # Start with 100
REQUESTS_PER_USER = 10
DURATION_SECONDS = 300  # 5 minutes
```

**Run Load Test:**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/tests

# Run load test
python test_subscription_load.py

# Monitor Cloud Run metrics during test
gcloud run services describe pgp-orchestrator-v1 --project=pgp-live --region=us-central1
```

**Load Test Targets:**

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Response Time (p50) | <200ms | <500ms |
| Response Time (p95) | <500ms | <2000ms |
| Response Time (p99) | <1000ms | <5000ms |
| Error Rate | <0.1% | <1% |
| Throughput | ≥100 req/s | ≥50 req/s |
| Database Connections | <80 concurrent | <95 concurrent |

**Monitor During Load Test:**

```bash
# Watch Cloud Run metrics
watch -n 5 'gcloud run services describe pgp-orchestrator-v1 --project=pgp-live --region=us-central1 --format="table(status.traffic)"'

# Watch Cloud SQL connections
gcloud sql operations list --instance=pgp-telepaypsql --project=pgp-live --limit=10

# Watch Cloud Tasks queue depth
gcloud tasks queues describe pgp-orchestrator-queue-v1 --location=us-central1 --project=pgp-live
```

**Checklist:**
- [ ] Load test completes without errors
- [ ] Response times within target ranges
- [ ] Error rate <1%
- [ ] Services auto-scale correctly (check instance count)
- [ ] Database connections stable (no connection pool exhaustion)
- [ ] Cloud Tasks queues process without backlog
- [ ] No OOM (Out of Memory) errors in logs
- [ ] No timeout errors

#### 7.5 Security Tests

**Security Validation Tests:**

**Test 1: HMAC Timestamp Validation**

```bash
# Test 1a: Valid HMAC signature, valid timestamp
# Should succeed (HTTP 200)

# Test 1b: Valid HMAC signature, expired timestamp (>5 minutes old)
# Should fail (HTTP 401) with "Signature expired" error

# Test 1c: Invalid HMAC signature
# Should fail (HTTP 401) with "Invalid signature" error

# Test 1d: Missing signature header
# Should fail (HTTP 401) with "Missing signature" error
```

**Test Script:** `PGP_SERVER_v1/tests/test_hmac_timestamp_validation.py`

**Test 2: IP Whitelist Validation**

```bash
# Test 2a: Request from whitelisted IP
# Should succeed (HTTP 200)

# Test 2b: Request from non-whitelisted IP
# Should fail (HTTP 403) with "IP not whitelisted" error

# Test 2c: Request with spoofed X-Forwarded-For header
# Should fail (HTTP 403) - uses rightmost IP from Cloud Run
```

**Test Script:** `PGP_SERVER_v1/tests/test_ip_whitelist.py`

**Test 3: SQL Injection Prevention**

```bash
# Test 3a: Attempt SQL injection in user input
# Example: email="test'; DROP TABLE users; --"
# Should be sanitized (no SQL execution)

# Test 3b: Verify parameterized queries used
# Check code: all database queries use SQLAlchemy text() or ORM
```

**Test 4: Authentication & Authorization**

```bash
# Test 4a: Access protected endpoint without token
# Should fail (HTTP 401)

# Test 4b: Access with expired JWT token
# Should fail (HTTP 401)

# Test 4c: Access with valid token but insufficient permissions
# Should fail (HTTP 403)

# Test 4d: Access with valid token and correct permissions
# Should succeed (HTTP 200)
```

**Run Security Test Suite:**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/PGP_SERVER_v1/tests

# Run all security tests
python -m pytest test_hmac_timestamp_validation.py -v
python -m pytest test_ip_whitelist.py -v
python -m pytest test_authentication.py -v
python -m pytest test_authorization.py -v
```

**Checklist:**
- [ ] HMAC timestamp validation working correctly
- [ ] IP whitelist blocking unauthorized IPs
- [ ] SQL injection attempts blocked
- [ ] Authentication requires valid JWT tokens
- [ ] Authorization enforces role-based access
- [ ] No security test failures
- [ ] All 7 CRITICAL vulnerabilities from audit addressed (see Phase 8)

#### 7.6 Database Tests

**Database Integrity & Performance Tests:**

**Test 1: Schema Validation**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/tools

# Verify schema matches expected structure
python verify_schema_match.py

# Expected output:
# ✅ All 15 tables exist
# ✅ All 4 ENUM types exist
# ✅ All primary keys exist
# ✅ All foreign keys exist
# ✅ All indexes exist
# ✅ Schema verification PASSED
```

**Test 2: Data Integrity Constraints**

```sql
-- Connect to database
-- Test unique constraints
INSERT INTO registered_users (email, ...) VALUES ('test@example.com', ...);
INSERT INTO registered_users (email, ...) VALUES ('test@example.com', ...);
-- Should fail on second insert (UNIQUE constraint violation)

-- Test foreign key constraints
INSERT INTO subscriptions (user_id, ...) VALUES ('non-existent-uuid', ...);
-- Should fail (FOREIGN KEY constraint violation)

-- Test ENUM constraints
INSERT INTO subscriptions (status, ...) VALUES ('invalid_status', ...);
-- Should fail (invalid ENUM value)
```

**Test 3: Query Performance**

```sql
-- Test slow query log
-- Queries should complete in <100ms

-- Test 1: User lookup (indexed)
EXPLAIN ANALYZE SELECT * FROM registered_users WHERE email = 'test@example.com';
-- Execution time should be <10ms (index scan)

-- Test 2: Subscription lookup (indexed)
EXPLAIN ANALYZE SELECT * FROM subscriptions WHERE user_id = '[UUID]';
-- Execution time should be <10ms (index scan)

-- Test 3: Payment idempotency check (indexed)
EXPLAIN ANALYZE SELECT * FROM processed_payments WHERE payment_id = 'test123';
-- Execution time should be <5ms (index scan)

-- Test 4: Currency mapping lookup (indexed)
EXPLAIN ANALYZE SELECT * FROM currency_to_network WHERE currency = 'BTC';
-- Execution time should be <5ms (index scan)
```

**Test 4: Connection Pool**

```bash
# Monitor active database connections during load
gcloud sql operations list --instance=pgp-telepaypsql --project=pgp-live

# Verify connection pool limits not exceeded
# Max connections: 100 (configured in Phase 3)
# Target utilization: <80% (≤80 concurrent connections)
```

**Checklist:**
- [ ] Schema verification passes
- [ ] All constraints working (unique, foreign key, ENUM)
- [ ] Queries use indexes (no sequential scans on large tables)
- [ ] Query performance <100ms for all common queries
- [ ] Connection pool stable (no exhaustion)
- [ ] No deadlocks or lock contention
- [ ] Backup system working (check Cloud SQL backups)
- [ ] Point-in-time recovery available (check transaction logs)

#### 7.7 Monitoring & Observability Tests

**Test Logging and Monitoring:**

**Test 1: Cloud Logging**

```bash
# Verify logs are being collected
gcloud logging read "resource.type=cloud_run_revision" \
    --project=pgp-live \
    --limit=50 \
    --freshness=10m

# Verify log levels appropriate
# INFO logs for normal operation
# ERROR logs for failures
# DEBUG logs disabled in production (LOG_LEVEL=INFO)

# Verify structured logging (JSON format)
gcloud logging read "resource.labels.service_name=pgp-orchestrator-v1 AND jsonPayload.level=ERROR" \
    --project=pgp-live \
    --limit=10
```

**Test 2: Cloud Monitoring Metrics**

```bash
# View Cloud Run metrics
gcloud monitoring time-series list \
    --filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count"' \
    --project=pgp-live

# View Cloud SQL metrics
gcloud monitoring time-series list \
    --filter='resource.type="cloudsql_database" AND metric.type="cloudsql.googleapis.com/database/cpu/utilization"' \
    --project=pgp-live
```

**Test 3: Error Reporting**

```bash
# View errors grouped by type
gcloud error-reporting events list --project=pgp-live --limit=20

# Should see errors caught and reported
# Should NOT see sensitive information in error messages (PII, secrets)
```

**Test 4: Cloud Trace (Distributed Tracing)**

```bash
# View traces for a request
gcloud logging read "trace=projects/pgp-live/traces/[TRACE_ID]" --project=pgp-live

# Verify trace spans cover all services in request chain
# Example: NowPayments IPN → Orchestrator → Split1 → Split2 → Split3
```

**Checklist:**
- [ ] Logs visible in Cloud Logging
- [ ] Log levels appropriate (no DEBUG in production)
- [ ] Structured logging working (JSON format)
- [ ] No sensitive data in logs (PII, secrets, passwords)
- [ ] Metrics collected for all services
- [ ] Error Reporting capturing exceptions
- [ ] Cloud Trace showing request flows
- [ ] Dashboards created (optional)
- [ ] Alerts configured (optional, recommended)

#### 7.8 Final Verification Checklist

**All Tests Complete:**

**Unit Tests:**
- [ ] All unit tests pass (pytest)
- [ ] No import errors
- [ ] Code coverage ≥70%

**Integration Tests:**
- [ ] Service-to-service communication working
- [ ] Cloud Tasks processing correctly
- [ ] Database operations successful

**End-to-End Tests:**
- [ ] Complete user flows working
- [ ] Registration → Payment → Subscription flow
- [ ] Broadcast system functional
- [ ] Payout system functional

**Load Tests:**
- [ ] Performance targets met (response time, throughput)
- [ ] Services auto-scale correctly
- [ ] No errors under load
- [ ] Database stable under load

**Security Tests:**
- [ ] HMAC validation working
- [ ] IP whitelist blocking unauthorized access
- [ ] SQL injection prevented
- [ ] Authentication and authorization enforced

**Database Tests:**
- [ ] Schema correct and complete
- [ ] Constraints enforced
- [ ] Query performance good
- [ ] Connection pool stable

**Monitoring Tests:**
- [ ] Logs collected
- [ ] Metrics visible
- [ ] Errors reported
- [ ] Tracing functional

### Time Estimate

- **Unit tests:** 30 minutes
- **Integration tests:** 1 hour
- **End-to-end tests:** 1.5 hours
- **Load tests:** 1 hour (including monitoring)
- **Security tests:** 1 hour
- **Database tests:** 30 minutes
- **Monitoring tests:** 30 minutes

**Total:** 6 hours

### Troubleshooting

**Issue: Tests fail with authentication errors**
- **Solution:** Verify test scripts use correct service URLs from secrets
- **Solution:** Check service account permissions
- **Solution:** Verify OIDC tokens being sent correctly

**Issue: Load test causes service crashes**
- **Solution:** Increase service memory allocation
- **Solution:** Increase max-instances limit
- **Solution:** Optimize slow queries (add indexes)
- **Solution:** Increase database connection pool size

**Issue: Database tests show slow queries**
- **Solution:** Add indexes on frequently queried columns
- **Solution:** Optimize query patterns (avoid N+1 queries)
- **Solution:** Consider database tier upgrade

**Issue: Monitoring shows no data**
- **Solution:** Verify Cloud Logging API enabled
- **Solution:** Check service account has Logging Writer role
- **Solution:** Wait 5-10 minutes for metric aggregation

### Next Phase

Once Phase 7 is complete, proceed to **Phase 8: Production Hardening**.

---

## Phase 8: Production Hardening

### Objective

Implement remaining security fixes, monitoring, and operational improvements to make pgp-live production-ready.

### Prerequisites

- [ ] Phase 7 completed (Testing successful)
- [ ] All services stable
- [ ] Review `COMPREHENSIVE_SECURITY_AUDIT_CHECKLIST.md`
- [ ] Review `SECURITY_VULNERABILITY_ANALYSIS_OWASP_VERIFICATION.md`

### Security Status

**Current Status (from Phase 0-7):**

**✅ COMPLETE - Code-Level Security:**
- HMAC timestamp validation (replay attack protection)
- IP whitelist configuration (external webhook security)
- Debug logging cleanup (LOG_LEVEL controls)
- Security documentation (HMAC_TIMESTAMP_SECURITY.md, IP_WHITELIST_SECURITY.md)

**⏳ PENDING - Infrastructure Security:**
- Distributed rate limiting with Redis/Memorystore
- Cloud Logging monitoring and alerting
- Security audit (external, recommended)
- OWASP Top 10 2021 vulnerability remediation (73 findings)

### OWASP Top 10 2021 Remediation Roadmap

**From COMPREHENSIVE_SECURITY_AUDIT_CHECKLIST.md:**

**Phase 8.1: CRITICAL Vulnerabilities (P1 - 0-7 days) - 7 vulnerabilities**

1. **Wallet Address Validation** - Prevent fund loss
2. **Replay Attack Prevention** - Nonce tracking in Redis
3. **IP Whitelist Security** - Trust only rightmost X-Forwarded-For
4. **Race Condition Prevention** - Use SELECT FOR UPDATE
5. **Transaction Limits** - Configurable min/max amounts
6. **Security Headers** - CSP, HSTS, X-Frame-Options
7. **Information Disclosure** - Generic error messages

**Phase 8.2: HIGH Vulnerabilities (P2 - 30 days) - 15 vulnerabilities**

Includes:
- Service-to-Service mTLS
- Role-Based Access Control (RBAC)
- SIEM Integration
- HTTPS Enforcement
- Database IAM Authentication

**Phase 8.3: MEDIUM Vulnerabilities (P3 - 90 days) - 26 vulnerabilities**

Includes:
- Idempotency Keys
- Argon2id Password Hashing
- Input Validation Framework
- Rate Limiting Improvements

**Phase 8.4: LOW Vulnerabilities (P4 - 180 days) - 25 vulnerabilities**

Includes:
- Automated Vulnerability Scanning
- Log Sanitization
- Security Headers Hardening
- Code Signing

### Checklist

#### 8.1 Implement Distributed Rate Limiting (Redis)

**Current:** In-memory rate limiting (not distributed, resets on service restart)
**Target:** Redis-based distributed rate limiting

**Deploy Redis (Memorystore):**

```bash
# Create Redis instance
gcloud redis instances create pgp-rate-limiter \
    --project=pgp-live \
    --region=us-central1 \
    --tier=basic \
    --size=1 \
    --redis-version=redis_7_0

# Get Redis connection details
gcloud redis instances describe pgp-rate-limiter \
    --region=us-central1 \
    --project=pgp-live \
    --format="value(host,port)"

# Update REDIS_HOST secret
REDIS_HOST=$(gcloud redis instances describe pgp-rate-limiter --region=us-central1 --project=pgp-live --format="value(host)")
echo -n "$REDIS_HOST" | gcloud secrets versions add REDIS_HOST --project=pgp-live --data-file=-
```

**Update Rate Limiting Code:**

See: `PGP_SERVER_v1/security/rate_limiter.py`

**Checklist:**
- [ ] Redis instance deployed
- [ ] REDIS_HOST secret updated
- [ ] Rate limiting code updated to use Redis
- [ ] Services redeployed with Redis configuration
- [ ] Rate limiting tested (check 429 errors after limit exceeded)

#### 8.2 Configure Cloud Logging Monitoring and Alerting

**Create Log-Based Metrics:**

```bash
# Metric 1: Error count
gcloud logging metrics create error_count \
    --project=pgp-live \
    --description="Count of ERROR level logs" \
    --log-filter='severity=ERROR'

# Metric 2: Critical errors (payment processing failures)
gcloud logging metrics create payment_errors \
    --project=pgp-live \
    --description="Payment processing errors" \
    --log-filter='severity=ERROR AND (resource.labels.service_name="pgp-orchestrator-v1" OR resource.labels.service_name="pgp-np-ipn-v1")'

# Metric 3: Database connection failures
gcloud logging metrics create database_connection_failures \
    --project=pgp-live \
    --description="Database connection failures" \
    --log-filter='severity=ERROR AND textPayload=~"database connection"'
```

**Create Alerting Policies:**

```bash
# Alert 1: High error rate
gcloud alpha monitoring policies create \
    --project=pgp-live \
    --notification-channels=[YOUR_NOTIFICATION_CHANNEL_ID] \
    --display-name="High Error Rate Alert" \
    --condition-display-name="Error rate > 10/minute" \
    --condition-threshold-value=10 \
    --condition-threshold-duration=60s \
    --condition-filter='metric.type="logging.googleapis.com/user/error_count"'

# Alert 2: Payment processing failures
gcloud alpha monitoring policies create \
    --project=pgp-live \
    --notification-channels=[YOUR_NOTIFICATION_CHANNEL_ID] \
    --display-name="Payment Processing Failure Alert" \
    --condition-display-name="Payment error rate > 5/minute" \
    --condition-threshold-value=5 \
    --condition-threshold-duration=60s \
    --condition-filter='metric.type="logging.googleapis.com/user/payment_errors"'

# Alert 3: Service availability
gcloud alpha monitoring policies create \
    --project=pgp-live \
    --notification-channels=[YOUR_NOTIFICATION_CHANNEL_ID] \
    --display-name="Service Unavailable Alert" \
    --condition-display-name="Service uptime < 99%" \
    --condition-threshold-value=0.99 \
    --condition-threshold-duration=300s \
    --condition-filter='metric.type="run.googleapis.com/request_count"'
```

**Create Notification Channels:**

```bash
# Email notification
gcloud alpha monitoring channels create \
    --project=pgp-live \
    --type=email \
    --display-name="Admin Email Alert" \
    --channel-labels=email_address=[YOUR_EMAIL]

# Slack notification (if using Slack)
gcloud alpha monitoring channels create \
    --project=pgp-live \
    --type=slack \
    --display-name="Slack Alerts" \
    --channel-labels=url=[SLACK_WEBHOOK_URL]
```

**Checklist:**
- [ ] Log-based metrics created
- [ ] Alerting policies configured
- [ ] Notification channels set up
- [ ] Test alerts triggered (simulate error condition)
- [ ] Alerts received via email/Slack
- [ ] Alert fatigue avoided (thresholds appropriate)

#### 8.3 Implement Remaining CRITICAL Security Fixes

**Priority 1 (Implement Immediately):**

**Fix 1: Wallet Address Validation**

File: `PGP_COMMON/crypto/wallet_validator.py` (create new)

```python
from web3 import Web3

def validate_wallet_address(address: str) -> bool:
    """Validate Ethereum wallet address using EIP-55 checksum"""
    if not address:
        return False
    try:
        return Web3.is_checksum_address(address)
    except Exception:
        return False
```

**Update payment processing:**
- Add validation before storing wallet addresses
- Reject invalid addresses with clear error message
- Log validation failures for monitoring

**Fix 2: Transaction Amount Limits**

File: `PGP_COMMON/config/limits.py` (create new)

```python
# Transaction limits (configurable via secrets)
MIN_TRANSACTION_AMOUNT = 5.00  # USD
MAX_TRANSACTION_AMOUNT = 10000.00  # USD
MAX_DAILY_TRANSACTION_AMOUNT = 50000.00  # USD per user
```

**Implement limit checks:**
- Validate transaction amounts before processing
- Track daily transaction totals per user
- Store limits in Secret Manager for easy adjustment

**Fix 3: Race Condition Prevention**

Update: `PGP_ORCHESTRATOR_v1/database_manager.py`

```python
# OLD: UPDATE then INSERT pattern
# NEW: Use SELECT FOR UPDATE or UPSERT

def record_private_channel_user(user_id, channel_id):
    with get_connection() as conn:
        # Use SELECT FOR UPDATE to lock row
        result = conn.execute(
            text("SELECT * FROM subscriptions WHERE user_id = :user_id AND channel_id = :channel_id FOR UPDATE"),
            {"user_id": user_id, "channel_id": channel_id}
        ).fetchone()

        if result:
            # Update existing
            conn.execute(
                text("UPDATE subscriptions SET updated_at = NOW() WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
        else:
            # Insert new
            conn.execute(
                text("INSERT INTO subscriptions (user_id, channel_id, ...) VALUES (:user_id, :channel_id, ...)"),
                {"user_id": user_id, "channel_id": channel_id}
            )
        conn.commit()
```

**Fix 4: Security Headers**

Update: `PGP_SERVER_v1/app_initializer.py` and `PGP_WEBAPI_v1/app_initializer.py`

```python
@app.after_request
def add_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response
```

**Checklist:**
- [ ] Wallet address validation implemented
- [ ] Transaction limits implemented
- [ ] Race condition fixes deployed
- [ ] Security headers added
- [ ] All fixes tested
- [ ] Services redeployed with fixes

#### 8.4 Security Audit (Optional but Recommended)

**Internal Security Review:**

- [ ] Code review of all payment processing logic
- [ ] Review of all database queries (SQL injection check)
- [ ] Review of all authentication/authorization logic
- [ ] Review of all external API integrations
- [ ] Review of secrets management practices
- [ ] Review of logging practices (no sensitive data logged)

**External Security Audit (Recommended):**

Consider hiring external security firm to audit:
- Penetration testing
- Code review
- Infrastructure review
- Compliance assessment (PCI DSS, SOC 2)

**Cost:** $15K-$30K for comprehensive audit

**Checklist:**
- [ ] Internal security review completed
- [ ] Vulnerabilities documented
- [ ] Fixes implemented
- [ ] External audit scheduled (optional)

#### 8.5 Compliance Roadmap

**From COMPREHENSIVE_SECURITY_AUDIT_CHECKLIST.md:**

**PCI DSS 3.2.1 Compliance:**
- **Current Status:** NON-COMPLIANT (6 violations)
- **Timeline:** 6 months
- **Cost:** $25K-$50K (certification)
- **Required:** For processing credit card payments (if applicable)

**SOC 2 Type II Compliance:**
- **Current Status:** NON-COMPLIANT (8 control gaps)
- **Timeline:** 9-12 months
- **Cost:** $40K-$80K (audit + certification)
- **Required:** For enterprise customers

**OWASP ASVS Level 2:**
- **Current Status:** 60% compliant
- **Timeline:** 4 months
- **Target:** 90%+ compliance

**Checklist:**
- [ ] Compliance requirements documented
- [ ] Timeline and budget approved
- [ ] Compliance team engaged (if pursuing)
- [ ] Compliance progress tracked

#### 8.6 Operational Readiness

**Runbook Creation:**

Create operational runbooks for:
- [ ] Service deployment procedure
- [ ] Incident response procedure
- [ ] Database backup and restore procedure
- [ ] Secret rotation procedure
- [ ] Scaling and performance tuning
- [ ] Common troubleshooting scenarios

**On-Call Setup:**

- [ ] On-call schedule defined
- [ ] Escalation path documented
- [ ] PagerDuty or similar integrated
- [ ] Runbooks accessible 24/7

**Disaster Recovery:**

- [ ] Backup strategy documented
- [ ] Recovery Time Objective (RTO) defined
- [ ] Recovery Point Objective (RPO) defined
- [ ] DR procedure tested

**Checklist:**
- [ ] Runbooks created and accessible
- [ ] On-call rotation established
- [ ] DR procedures tested
- [ ] Backup strategy validated

### Production Hardening Complete

**Final Checklist:**

**Security:**
- [ ] All CRITICAL vulnerabilities addressed
- [ ] Security headers implemented
- [ ] Rate limiting distributed (Redis)
- [ ] Wallet validation implemented
- [ ] Transaction limits configured

**Monitoring:**
- [ ] Cloud Logging configured
- [ ] Alerting policies active
- [ ] Notification channels working
- [ ] Dashboards created

**Compliance:**
- [ ] Compliance roadmap defined
- [ ] Security audit completed (or scheduled)
- [ ] Compliance gaps documented

**Operations:**
- [ ] Runbooks created
- [ ] On-call setup complete
- [ ] DR procedures tested
- [ ] Team trained

**Deployment Status:** ✅ **PRODUCTION READY**

### Time Estimate

- **Redis deployment:** 1 hour
- **Monitoring and alerting:** 2 hours
- **CRITICAL security fixes:** 8 hours
- **Security audit:** Variable (1-2 weeks if external)
- **Runbooks and operations:** 4 hours

**Total:** 15-20 hours (excluding external audit)

---

## Appendices

### Appendix A: Complete File Reference

**Deployment Scripts:**
- `TOOLS_SCRIPTS_TESTS/scripts/create_pgp_live_secrets.sh`
- `TOOLS_SCRIPTS_TESTS/scripts/grant_pgp_live_secret_access.sh`
- `TOOLS_SCRIPTS_TESTS/scripts/deploy_all_pgp_services.sh`
- `TOOLS_SCRIPTS_TESTS/scripts/deploy_gcwebhook_tasks_queues.sh`
- `TOOLS_SCRIPTS_TESTS/scripts/deploy_gcsplit_tasks_queues.sh`
- `TOOLS_SCRIPTS_TESTS/scripts/deploy_hostpay_tasks_queues.sh`
- `TOOLS_SCRIPTS_TESTS/scripts/deploy_accumulator_tasks_queues.sh`

**Migration Scripts:**
- `TOOLS_SCRIPTS_TESTS/migrations/001_create_complete_schema.sql`
- `TOOLS_SCRIPTS_TESTS/migrations/001_rollback.sql`
- `TOOLS_SCRIPTS_TESTS/migrations/002_populate_currency_to_network.sql`
- `TOOLS_SCRIPTS_TESTS/migrations/003_rename_gcwebhook1_columns.sql`
- `TOOLS_SCRIPTS_TESTS/migrations/003_rollback.sql`

**Testing Scripts:**
- `TOOLS_SCRIPTS_TESTS/tests/test_subscription_integration.py`
- `TOOLS_SCRIPTS_TESTS/tests/test_subscription_load.py`
- `PGP_SERVER_v1/tests/test_hmac_timestamp_validation.py`
- `PGP_SERVER_v1/tests/test_ip_whitelist.py`

**Verification Tools:**
- `TOOLS_SCRIPTS_TESTS/tools/deploy_complete_schema_pgp_live.py`
- `TOOLS_SCRIPTS_TESTS/tools/verify_schema_match.py`
- `TOOLS_SCRIPTS_TESTS/tools/extract_complete_schema.py`
- `TOOLS_SCRIPTS_TESTS/tools/export_currency_to_network.py`

### Appendix B: Secret Naming Scheme Reference

See `SECRET_SCHEME.md` for complete list of 75+ secrets.

**Key Secret Categories:**
- Database: `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `CLOUD_SQL_CONNECTION_NAME`
- Service URLs: `PGP_*_URL` (13 services)
- Queue Names: `PGP_*_QUEUE` (17 queues)
- API Keys: `NOWPAYMENTS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `SENDGRID_API_KEY`
- Encryption: `HMAC_SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_SECRET_KEY`
- Wallet: `WALLET_PRIVATE_KEY`, `WALLET_ADDRESS`

### Appendix C: Service Naming Scheme

See `NAMING_SCHEME.md` for complete mapping.

**PGP_v1 Services:**
- `PGP_SERVER_v1` → `pgp-server-v1` (Cloud Run)
- `PGP_WEBAPI_v1` → `pgp-webapi-v1` (Cloud Run)
- `PGP_WEB_v1` → `pgp-web-v1` (Cloud Run)
- And 14 more services...

### Appendix D: Database Schema ERD

**Core Tables:**
1. `registered_users` - User accounts
2. `subscriptions` - Active subscriptions
3. `closed_channels` - Private Telegram channels
4. `nowpayments_transactions` - Payment transactions
5. `processed_payments` - Idempotency tracking
6. `broadcast_manager` - Scheduled broadcasts
7. `payout_requests` - Cryptocurrency payouts

**Supporting Tables:**
8. `conversation_state` - Bot conversation state
9. `donation_keypad_state` - Donation flow state
10. `failed_transactions` - Failed payment tracking
11. `landing_page_visits` - Analytics
12. `batch_conversions` - Batch processing
13. `currency_to_network` - Currency mappings
14-15. Additional tables...

### Appendix E: Troubleshooting Guide

**Common Issues:**

1. **Service fails to deploy**
   - Check Docker image builds locally
   - Verify all secrets exist
   - Check service account permissions
   - Review Cloud Run logs

2. **Database connection timeout**
   - Verify Cloud SQL instance is RUNNABLE
   - Check Cloud SQL Proxy configuration
   - Ensure service account has Cloud SQL Client role
   - Verify connection name in secrets

3. **Service-to-service 403 errors**
   - Grant Cloud Run Invoker role
   - Verify OIDC token in Authorization header
   - Check target service IAM policy

4. **High error rate**
   - Check Cloud Logging for error details
   - Review recent deployments (rollback if necessary)
   - Check database health
   - Verify external services (NowPayments, Telegram) accessible

5. **Slow performance**
   - Check service resource allocation (memory, CPU)
   - Review database query performance
   - Check for N+1 query patterns
   - Increase max-instances if scaling limited

### Appendix F: Cost Optimization

**Baseline Costs:**
- Cloud Run: $150-200/month (17 services, standard traffic)
- Cloud SQL: $50-100/month (db-custom-2-7680)
- Cloud Tasks: $10-20/month (17 queues, moderate load)
- Secret Manager: $5/month (75 secrets)
- Cloud Logging: $20-30/month (standard retention)
- Monitoring: $10/month (metrics and alerts)
- **Total: $245-365/month**

**Optimization Strategies:**
1. Reduce min-instances to 0 for non-critical services
2. Use smaller Cloud SQL tier (db-f1-micro for testing)
3. Reduce Cloud Logging retention (30 days → 7 days)
4. Use committed use discounts for predictable workloads
5. Scale max-instances based on actual traffic

**Optimized Costs:**
- **Testing/Staging: $100-150/month**
- **Production (Low Traffic): $200-250/month**
- **Production (High Traffic): $300-400/month**

---

## Document Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-18 | Claude | Initial comprehensive deployment documentation |

---

## Conclusion

This document provides a complete deployment roadmap for migrating PGP_v1 architecture to pgp-live GCP project. Follow the 8 phases sequentially, validating each phase before proceeding to the next.

**Estimated Timeline:**
- **Minimum (Staging):** 3-4 weeks
- **Standard (Production):** 5-8 weeks
- **With Full Security Hardening:** 10-12 weeks

**Current Status:** Phase 0 of 8 (Documentation Complete, Deployment Not Started)

**Next Step:** Begin Phase 1 - GCP Project Setup

---

**For Questions or Issues:**
- Review troubleshooting sections in each phase
- Check Cloud Logging for detailed error messages
- Consult GCP documentation for service-specific issues
- Refer to `COMPREHENSIVE_SECURITY_AUDIT_CHECKLIST.md` for security guidance

**Remember:** This is a greenfield deployment to a new GCP project. Take time to validate each phase thoroughly before proceeding. Production traffic should only be switched after Phase 7 (Testing) is successfully completed.
