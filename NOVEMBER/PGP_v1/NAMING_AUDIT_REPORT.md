# Remaining GC Naming References - Audit Report

## 🔍 Comprehensive Search Results

Found **multiple files** still using old GC* naming scheme that need to be updated to PGP v1 naming.

---

## 📋 Files Requiring Updates

### CATEGORY 1: Python Source Code (CRITICAL) ⚠️
**10+ Python files** with old secret names in config_manager.py:

1. `GCWebhook1-PGP/config_manager.py`
   - References: GCWEBHOOK2_QUEUE, GCWEBHOOK2_URL, GCSPLIT1_QUEUE, GCSPLIT1_URL, GCACCUMULATOR_QUEUE, GCACCUMULATOR_URL

2. `GCWebhook2-PGP/config_manager.py` (likely)
3. `GCSplit1-PGP/config_manager.py`
4. `GCSplit2-PGP/config_manager.py`
5. `GCSplit3-PGP/config_manager.py`
6. `GCHostPay1-PGP/config_manager.py`
7. `GCHostPay2-PGP/config_manager.py`
8. `GCHostPay3-PGP/config_manager.py`
9. `GCAccumulator-PGP/config_manager.py`
10. `GCBatchProcessor-PGP/config_manager.py`
11. `GCMicroBatchProcessor-PGP/config_manager.py`
12. `np-webhook-PGP/app.py`

**Old Secret Names to Update:**
- GCWEBHOOK1_QUEUE → PGP_WEBHOOK1_QUEUE
- GCWEBHOOK2_QUEUE → PGP_WEBHOOK2_QUEUE
- GCWEBHOOK1_URL → PGP_WEBHOOK1_URL
- GCWEBHOOK2_URL → PGP_WEBHOOK2_URL
- GCSPLIT1_QUEUE → PGP_SPLIT1_QUEUE
- GCSPLIT2_QUEUE → PGP_SPLIT2_QUEUE
- GCSPLIT3_QUEUE → PGP_SPLIT3_QUEUE
- GCSPLIT1_URL → PGP_SPLIT1_URL
- GCSPLIT2_URL → PGP_SPLIT2_URL
- GCSPLIT3_URL → PGP_SPLIT3_URL
- GCACCUMULATOR_QUEUE → PGP_ACCUMULATOR_QUEUE
- GCACCUMULATOR_URL → PGP_ACCUMULATOR_URL
- GCBATCHPROCESSOR_QUEUE → PGP_BATCHPROCESSOR_QUEUE
- GCHOSTPAY1_QUEUE → PGP_HOSTPAY1_QUEUE
- GCHOSTPAY2_QUEUE → PGP_HOSTPAY2_QUEUE
- GCHOSTPAY3_QUEUE → PGP_HOSTPAY3_QUEUE
- GCHOSTPAY1_URL → PGP_HOSTPAY1_URL
- GCHOSTPAY2_URL → PGP_HOSTPAY2_URL
- GCHOSTPAY3_URL → PGP_HOSTPAY3_URL
- All *_RESPONSE_QUEUE, *_THRESHOLD_QUEUE, *_RETRY_QUEUE, *_BATCH_QUEUE variants

---

### CATEGORY 2: Deployment Scripts (IMPORTANT) ⚠️

**deployment_scripts/06_setup_iam_permissions.sh**
- Lines with old service names: gcwebhook1-pgp, gcwebhook2-pgp, gcsplit1-pgp, etc.
- Need to update to: pgp-webhook1-v1, pgp-webhook2-v1, pgp-split1-v1, etc.

**deployment_scripts/07_deploy_backend_services.sh**
- Lines 104-278: ALL service names in deploy_service() calls
- Service names like "gcregisterapi-pgp" → "pgp-server-v1"
- SERVICE_NAME variables need updating

**deployment_scripts/individual_services/*.sh** (16 files)
- 28 references to old service names across individual scripts
- SERVICE_NAME variables in each script
- Service name parameters in deploy commands

**deployment_scripts/individual_services/deploy_all_services.sh**
- get_service_url() calls with old service names
- Service names in orchestration logic

---

### CATEGORY 3: Documentation Files (LOWER PRIORITY) 📄

**deployment_scripts/09_EXTERNAL_WEBHOOKS_CONFIG.md**
- Multiple references to old service names in examples
- URLs like `https://np-webhook-pgp-XXX.run.app/`
- Service names in gcloud commands

**DEPLOYMENT_NEEDS_ANALYSIS.md**
- Service names in deployment URLs
- Example: `https://np-webhook-pgp-XXXXXX.us-central1.run.app/`

**MIGRATION_SUMMARY.md**
- Example gcloud commands with old service names
- Example: `gcloud run deploy gcregisterapi-pgp`

**deployment_scripts/NAMING_SCHEME.md**
- This is OK - it's a REFERENCE showing old → new mappings

---

## 🎯 Priority Order for Updates

### PRIORITY 1 (CRITICAL): Python Source Code
**Must be updated** - Services will fail if secret names don't match deployment!

### PRIORITY 2 (HIGH): Deployment Scripts
**Must be updated** - Scripts won't deploy services with correct names!

### PRIORITY 3 (MEDIUM): Documentation
**Should be updated** - For consistency and accuracy

---

## 📊 Impact Analysis

| Category | Files Affected | References | Impact |
|----------|---------------|------------|--------|
| Python Code | 12 files | ~50+ | 🔴 CRITICAL - Services won't work |
| Deployment Scripts | 19 files | ~100+ | 🔴 CRITICAL - Can't deploy |
| Documentation | 3 files | ~30+ | 🟡 MEDIUM - Confusion |
| **TOTAL** | **34 files** | **~180+** | **HIGH** |

---

## ✅ Recommendation

**UPDATE ALL FILES** to ensure complete consistency across:
1. Python source code (secret names)
2. Deployment scripts (service names)
3. Documentation (examples and references)

This will ensure the codebase is fully aligned with PGP v1 naming architecture.

---

**Generated:** 2025-11-16
**Status:** AUDIT COMPLETE - UPDATES REQUIRED
