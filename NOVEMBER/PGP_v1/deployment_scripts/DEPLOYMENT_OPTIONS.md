# PayGatePrime v1 - Deployment Options Guide

This guide explains all available deployment options for PayGatePrime v1 services.

---

## 📋 Overview

You have **two deployment approaches** to choose from:

1. **Monolithic Deployment** - Deploy all services using a single comprehensive script
2. **Granular Deployment** - Deploy services individually or in phases

Both approaches achieve the same result - choose based on your preference and needs.

---

## 🎯 Option 1: Monolithic Deployment (Quick & Simple)

**Location:** `deployment_scripts/07_deploy_backend_services.sh`

### When to Use
- First-time deployment of all services
- Quick deployment without manual intervention
- You trust the automated deployment sequence

### How to Use
```bash
cd /home/user/TelegramFunnel/NOVEMBER/PGP_v1/deployment_scripts

# Review the script
cat 07_deploy_backend_services.sh

# Execute (after reviewing)
./07_deploy_backend_services.sh
```

### What It Does
- Deploys all 15 services in one execution
- Uses a single deployment function for consistency
- Includes all required secrets and configurations
- Estimated time: 20-40 minutes

### Advantages
- ✅ Simple - one command to deploy everything
- ✅ Consistent - uses same deployment pattern for all services
- ✅ Fast - no manual intervention between services

### Disadvantages
- ❌ All-or-nothing - if one fails, harder to troubleshoot
- ❌ Less visibility into individual service configurations
- ❌ Harder to customize individual services

---

## 🔧 Option 2: Granular Deployment (Flexible & Detailed)

**Location:** `deployment_scripts/individual_services/`

### When to Use
- Need fine-grained control over each service
- Want to deploy services in stages
- Troubleshooting specific service issues
- Different resource requirements per service
- Learning deployment process step-by-step

### How to Use

#### 2A: Deploy All Services (Orchestrated)
```bash
cd /home/user/TelegramFunnel/NOVEMBER/PGP_v1/deployment_scripts/individual_services

# Review the master script
cat deploy_all_services.sh

# Execute (after reviewing)
./deploy_all_services.sh
```

This uses individual scripts but runs them in sequence with proper dependency handling.

#### 2B: Deploy Specific Service
```bash
cd /home/user/TelegramFunnel/NOVEMBER/PGP_v1/deployment_scripts/individual_services

# Example: Deploy only the main API
./deploy_gcregisterapi.sh

# Example: Deploy payment processing services
./deploy_gcwebhook1.sh
./deploy_gcwebhook2.sh
```

#### 2C: Deploy by Phase
```bash
# Phase 1: Public services
./deploy_gcregisterapi.sh
./deploy_np_webhook.sh

# Update service URLs
cd ..
./05_create_service_url_secrets.sh
cd individual_services

# Phase 2: Payment processing
./deploy_gcwebhook1.sh
./deploy_gcwebhook2.sh

# Continue with remaining phases...
```

### What It Does
- Deploys each service with its own dedicated script
- Service-specific configurations and resource allocation
- Detailed next steps after each deployment
- Allows pausing between services

### Advantages
- ✅ Granular control - deploy one service at a time
- ✅ Easy troubleshooting - isolate issues to specific services
- ✅ Service-specific configs - memory, CPU, timeout tailored per service
- ✅ Better documentation - each script includes detailed next steps
- ✅ Flexible - deploy in any order or combination

### Disadvantages
- ❌ More manual work if deploying all services
- ❌ Must remember to update service URL secrets after each phase
- ❌ Takes longer if deploying manually

---

## 📊 Comparison Table

| Feature | Monolithic (Option 1) | Granular (Option 2) |
|---------|----------------------|---------------------|
| **Script Location** | `07_deploy_backend_services.sh` | `individual_services/*.sh` |
| **Single Command** | ✅ Yes | ❌ No (unless using master script) |
| **Granular Control** | ❌ No | ✅ Yes |
| **Easy Troubleshooting** | ❌ Harder | ✅ Easier |
| **Service-Specific Docs** | ❌ No | ✅ Yes |
| **Resource Customization** | ❌ Limited | ✅ Per-service |
| **Deployment Speed** | ⚡ Fast | 🐢 Slower (if manual) |
| **Learning Curve** | 📚 Simple | 📚 More detailed |

---

## 🗂️ Service List

### All 15 Services to Deploy

1. **gcregisterapi-pgp** - Main backend API (public)
2. **np-webhook-pgp** - NowPayments IPN handler (public)
3. **gcwebhook1-pgp** - Primary payment processor (internal)
4. **gcwebhook2-pgp** - Telegram invite handler (internal)
5. **gcsplit1-pgp** - Payment splitter (internal)
6. **gcsplit2-pgp** - Payment router (internal)
7. **gcsplit3-pgp** - Accumulator enqueuer (internal)
8. **gchostpay1-pgp** - Crypto conversion executor (internal)
9. **gchostpay2-pgp** - Conversion monitor (internal)
10. **gchostpay3-pgp** - Blockchain validator (internal)
11. **gcaccumulator-pgp** - Payment accumulator (internal)
12. **gcbatchprocessor-pgp** - Batch processor (internal)
13. **gcmicrobatchprocessor-pgp** - Micro batch processor (internal)
14. **telepay-pgp** - Telegram bot (public)

---

## 🎓 Recommended Approach for Different Scenarios

### Scenario 1: First-Time Deployment (Production)
**Recommendation:** Granular with master script

```bash
cd deployment_scripts/individual_services
./deploy_all_services.sh
```

**Why:** Provides visibility and checkpoints while automating the sequence.

### Scenario 2: Development/Testing
**Recommendation:** Individual service scripts

```bash
# Deploy only what you need to test
./deploy_gcregisterapi.sh
./deploy_np_webhook.sh
```

**Why:** Save time and resources by deploying only necessary services.

### Scenario 3: Quick Demo/POC
**Recommendation:** Monolithic

```bash
./07_deploy_backend_services.sh
```

**Why:** Fastest path to full deployment.

### Scenario 4: Troubleshooting
**Recommendation:** Individual service scripts

```bash
# Redeploy only the problematic service
./deploy_gchostpay1.sh
```

**Why:** Isolate and fix specific issues without affecting other services.

---

## 📝 Deployment Sequence (Both Options Follow This)

```
1. Prerequisites
   ├── Enable APIs (01_enable_apis.sh)
   ├── Create Cloud SQL (02_create_cloudsql.sh)
   ├── Create secrets (03_create_secrets.sh, 04_create_queue_secrets.sh)
   └── Setup IAM (06_setup_iam_permissions.sh)

2. Backend Services (Option 1 OR Option 2)
   ├── Phase 1: Public services
   ├── Phase 2: Payment processing
   ├── Phase 3: Split services
   ├── Phase 4: Host payment services
   ├── Phase 5: Batch processors
   └── Phase 6: Telegram bot

3. Post-Deployment
   ├── Update service URLs (05_create_service_url_secrets.sh)
   ├── Configure external webhooks (09_EXTERNAL_WEBHOOKS_CONFIG.md)
   ├── Verify deployment (10_verify_deployment.sh)
   └── Deploy frontend (08_deploy_frontend.sh)
```

---

## ✅ Decision Checklist

Answer these questions to choose your approach:

- [ ] Is this your first deployment? → **Granular with master script**
- [ ] Do you need to deploy all 15 services? → **Monolithic OR Granular master**
- [ ] Do you need to deploy only specific services? → **Granular individual**
- [ ] Are you troubleshooting a specific service? → **Granular individual**
- [ ] Do you want maximum speed? → **Monolithic**
- [ ] Do you want maximum control? → **Granular individual**
- [ ] Do you want the best of both worlds? → **Granular master script**

---

## 🚀 Next Steps

1. **Review Prerequisites:**
   - Ensure all scripts in `deployment_scripts/` (01-06) have been run
   - Verify all secrets exist in Secret Manager
   - Confirm service account has proper IAM roles

2. **Choose Your Approach:**
   - Monolithic: Use `07_deploy_backend_services.sh`
   - Granular: Use scripts in `individual_services/`

3. **Execute Deployment:**
   - Review the script(s) before running
   - Execute with proper authentication
   - Monitor Cloud Build and Cloud Run logs

4. **Post-Deployment:**
   - Run verification script
   - Configure external webhooks
   - Test end-to-end payment flow

---

## 📚 Additional Resources

- **Deployment Scripts README:** `deployment_scripts/README.md`
- **Individual Services Guide:** `deployment_scripts/individual_services/README.md`
- **External Webhooks Config:** `deployment_scripts/09_EXTERNAL_WEBHOOKS_CONFIG.md`
- **Verification Script:** `deployment_scripts/10_verify_deployment.sh`
- **Migration Overview:** `MIGRATION_SUMMARY.md`

---

**Choose wisely based on your needs. Both approaches are fully supported and tested!**

**Last Updated:** 2025-11-16
**Total Deployment Options:** 2
**Total Scripts Available:** 26 (10 main + 16 individual)
