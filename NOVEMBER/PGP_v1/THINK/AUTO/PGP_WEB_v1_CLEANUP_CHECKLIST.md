# PGP_WEB_v1 Cleanup Checklist - Manual GCP Operations

**Date Created:** 2025-11-18
**Status:** 🟡 PENDING MANUAL EXECUTION
**Reference:** Plan agent analysis, PROGRESS.md (2025-11-18)

---

## Overview

PGP_WEB_v1 has been **removed from the codebase** as a **ghost service** - it contained no source code, only an empty directory with a single HTML file referencing non-existent `/src/main.tsx`. This document tracks the remaining **manual Google Cloud Platform operations** that need to be performed to complete the cleanup.

**⚠️ IMPORTANT**: These operations **CANNOT** be performed from this local environment as per project constraints. They require manual execution via GCP Console or gcloud CLI.

---

## ✅ Completed (Local Operations)

- [x] Archive PGP_WEB_v1 folder → `ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/PGP_WEB_v1_REMOVED_20251118/`
- [x] Update deployment script → `TOOLS_SCRIPTS_TESTS/scripts/deploy_all_pgp_services.sh` (removed lines 159-161, renumbered services)
- [x] Update PGP_MAP.md → Removed service section, added deprecation notice
- [x] Update PGP_WEBAPI_v1 documentation → Removed references to PGP_WEB_v1 as frontend
- [x] Update documentation (PROGRESS.md, DECISIONS.md)

---

## 🔴 Pending (Manual GCP Operations)

### 1. Verify Cloud Run Service Status 🚀

**Service:** Cloud Run
**Priority:** HIGH (determine if service was ever deployed)
**Estimated Cost Impact:** Unknown (service may not exist)

**Actions Required:**

```bash
# Check if PGP_WEB_v1 Cloud Run service exists
gcloud run services describe pgp-web-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --format="value(metadata.name, status.url)" 2>/dev/null

# Expected outcome: Either service doesn't exist (ERROR) or service details shown
```

**Possible Scenarios:**

**Scenario A: Service Does NOT Exist** (most likely)
- Service was never deployed (no Dockerfile, no source code)
- No action needed
- Proceed to Step 2 (revoke service account)

**Scenario B: Service EXISTS** (unlikely but possible)
- Service was somehow deployed (possibly old stub or test)
- Proceed with deletion below

**If Service Exists - Delete It:**

```bash
# Backup service configuration
gcloud run services describe pgp-web-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --format=yaml > /tmp/pgp-web-v1-backup-$(date +%Y%m%d).yaml

# Delete the Cloud Run service
gcloud run services delete pgp-web-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --quiet

# Verify deletion
gcloud run services list --project=pgp-live --region=us-central1 | grep pgp-web-v1
# Expected: No results
```

**Verification:**
- [ ] Checked if service exists
- [ ] If exists: Service configuration backed up to YAML
- [ ] If exists: Service deleted from Cloud Run
- [ ] Service no longer appears in `gcloud run services list`

---

### 2. Revoke IAM Service Account Permissions 🔐

**Service:** IAM & Admin
**Priority:** MEDIUM (security best practice - remove unused permissions)
**Estimated Cost Savings:** None (security improvement)

**Actions Required:**

```bash
# List service account
gcloud iam service-accounts list --project=pgp-live | grep pgp-web-v1
# Expected: pgp-web-v1-sa@pgp-live.iam.gserviceaccount.com

# Get current IAM policy bindings (BACKUP before changes)
gcloud projects get-iam-policy pgp-live \
    --flatten="bindings[].members" \
    --filter="bindings.members:pgp-web-v1-sa@pgp-live.iam.gserviceaccount.com" \
    --format=yaml > /tmp/pgp-web-v1-iam-backup-$(date +%Y%m%d).yaml

# OPTION 1: Disable service account (recommended - allows rollback)
gcloud iam service-accounts disable pgp-web-v1-sa@pgp-live.iam.gserviceaccount.com \
    --project=pgp-live

# OPTION 2: Delete service account (permanent - only if confident)
# gcloud iam service-accounts delete pgp-web-v1-sa@pgp-live.iam.gserviceaccount.com \
#     --project=pgp-live \
#     --quiet

# Verify service account disabled
gcloud iam service-accounts describe pgp-web-v1-sa@pgp-live.iam.gserviceaccount.com \
    --project=pgp-live | grep disabled
# Expected: disabled: true
```

**Verification:**
- [ ] IAM policy backed up to YAML
- [ ] Service account disabled or deleted
- [ ] No active tokens for pgp-web-v1-sa

---

### 3. Remove Secret Manager References 🔑

**Service:** Secret Manager
**Priority:** LOW (secrets remain unused, no cost impact)
**Estimated Cost Savings:** None

**Actions Required:**

```bash
# List all secrets related to PGP_WEB_v1
gcloud secrets list --project=pgp-live | grep -i "web-v1\|gcregisterweb"

# EXAMPLE secrets that may exist (verify actual names):
# - PGP_WEB_V1_CONFIG
# - PGP_WEB_V1_API_URL
# - GCREGISTERWEB_CONFIG (old naming)

# OPTION 1: No action needed (secrets remain for historical reference)
# OPTION 2: Delete secrets if confirmed unused
# gcloud secrets delete PGP_WEB_V1_CONFIG \
#     --project=pgp-live \
#     --quiet
```

**Verification:**
- [ ] All PGP_WEB_v1 secrets identified
- [ ] Decision made: keep for historical reference OR delete

---

### 4. Update Monitoring & Alerting 📊

**Service:** Cloud Monitoring
**Priority:** LOW (prevents confusing metrics)
**Estimated Cost Savings:** None

**Actions Required:**

1. **Remove PGP_WEB_v1 from Dashboards**:
   - Open Cloud Monitoring Console → Dashboards
   - Identify dashboards with "PGP_WEB_v1" or "Web v1" charts
   - Remove or hide charts related to the service

2. **Disable Alerting Policies**:
   ```bash
   # List alerting policies
   gcloud alpha monitoring policies list --project=pgp-live | grep -i "web-v1\|gcregisterweb"

   # Disable each policy (DO NOT DELETE - allows rollback)
   gcloud alpha monitoring policies update [POLICY_ID] \
       --project=pgp-live \
       --no-enabled
   ```

3. **Update Uptime Checks**:
   ```bash
   # List uptime checks
   gcloud monitoring uptime list --project=pgp-live | grep -i "web-v1\|gcregisterweb"

   # Delete uptime checks (service doesn't exist)
   gcloud monitoring uptime delete [CHECK_ID] \
       --project=pgp-live \
       --quiet
   ```

**Verification:**
- [ ] Dashboards updated (no PGP_WEB_v1 charts)
- [ ] Alerting policies disabled
- [ ] Uptime checks removed

---

## 📋 Rollback Plan (In Case of Issues)

If PGP_WEB_v1 needs to be restored (unlikely, but documented for completeness):

1. **Restore from Archive**:
   ```bash
   cp -r ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/PGP_WEB_v1_REMOVED_20251118/* PGP_WEB_v1/
   ```

2. **Revert Documentation Changes**:
   - Revert PGP_MAP.md changes (restore PGP_WEB_v1 section)
   - Revert PGP_WEBAPI_v1 documentation (restore frontend references)
   - Revert deployment script changes

3. **Re-enable GCP Resources** (if they existed):
   - Redeploy Cloud Run service from backup YAML (if service existed)
   - Re-enable service account
   - Restore monitoring dashboards

**Note:** Since PGP_WEB_v1 contained no source code, restoration would only recover the empty directory structure. To make it functional, you would need to:
- Create React/TypeScript source code from scratch
- Build the application
- Create a Dockerfile
- Deploy to Cloud Storage/CDN (preferred) or Cloud Run

---

## 💰 Total Cost Savings

| Resource | Monthly Cost (Before) | Monthly Cost (After) | Savings |
|----------|----------------------|---------------------|------------|
| Cloud Run (pgp-web-v1) | ~$0/month (likely never deployed) | $0 | **$0** |
| Service Account | ~$0/month (no cost) | $0 | **$0** |
| **TOTAL** | **~$0/month** | **$0** | **~$0/month** |

**Primary Benefits:**
- **Complexity Reduction**: Eliminated ghost service from architecture (16 → 15 services)
- **Reduced Confusion**: Removed misleading documentation about non-existent frontend
- **Security Improvement**: Disabled unused service account
- **Maintenance Burden**: One less service to document and explain

---

## 🎯 Completion Criteria

PGP_WEB_v1 cleanup is **COMPLETE** when:

- [x] Local code changes applied (documentation updated)
- [x] Archive created
- [x] Deployment scripts updated
- [x] PGP_MAP.md updated
- [x] PGP_WEBAPI_v1 documentation updated
- [ ] Cloud Run service verified (exists or not)
- [ ] IAM service account disabled (if exists)
- [ ] Monitoring/alerting updated (if exists)
- [ ] Complexity reduction verified (service count reduced)

---

## 📝 Execution Log

| Date | Action | Status | Notes |
|------|--------|--------|-------|
| 2025-11-18 | Local code changes | ✅ COMPLETE | Documentation updated across all files |
| 2025-11-18 | Archive created | ✅ COMPLETE | Backed up to ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/ |
| 2025-11-18 | Deployment scripts updated | ✅ COMPLETE | deploy_all_pgp_services.sh updated (service count 16→15) |
| 2025-11-18 | PGP_MAP.md updated | ✅ COMPLETE | Added deprecation notice, updated service count |
| 2025-11-18 | PGP_WEBAPI_v1 updated | ✅ COMPLETE | Removed frontend references |
| TBD | Cloud Run service verification | 🔴 PENDING | Requires manual GCP Console/CLI access |
| TBD | IAM service account disabled | 🔴 PENDING | Requires manual GCP Console/CLI access |
| TBD | Monitoring updated | 🔴 PENDING | Requires manual GCP Console/CLI access |

---

## 🔗 References

- **Analysis Report**: Plan agent analysis (comprehensive investigation)
- **Progress Tracker**: `/PROGRESS.md` (2025-11-18 entry)
- **Architectural Decision**: `/DECISIONS.md` (Decision 14.1)
- **Archive Location**: `/ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/PGP_WEB_v1_REMOVED_20251118/`
- **Deployment Script**: `/TOOLS_SCRIPTS_TESTS/scripts/deploy_all_pgp_services.sh`
- **Architecture Map**: `/PGP_MAP.md` (version 1.2)

---

## 🧩 Key Findings from Analysis

**What Was PGP_WEB_v1?**
- Empty directory with 1 HTML file (493 bytes)
- 1 `.env.example` file with stale `GCRegisterAPI` reference
- Empty `dist/` directory (no build output)
- `node_modules/` directory (dependencies with no source code)
- **ZERO TypeScript/React source files**

**Why Did It Exist?**
- Part of original `GCRegisterWeb-10-26` architecture
- Never migrated from OCTOBER codebase to NOVEMBER
- Documentation was written for planned features that were never implemented
- Empty directory was renamed during PGP_* migration but never removed

**Impact of Removal:**
- Zero services broken (no dependencies)
- Zero deployments affected (deployment would have failed)
- Architecture simplified (18 → 15 services after PGP_ACCUMULATOR_v1 + PGP_WEB_v1 removal)
- PGP_WEBAPI_v1 remains fully functional as standalone REST API

---

**End of Document**
