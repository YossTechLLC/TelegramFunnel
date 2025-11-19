# PGP_ACCUMULATOR_v1 Cleanup Checklist - Manual GCP Operations

**Date Created:** 2025-11-18
**Status:** 🟡 PENDING MANUAL EXECUTION
**Reference:** THINK/AUTO/PGP_THRESHOLD_REVIEW.md, PROGRESS.md (2025-11-18)

---

## Overview

PGP_ACCUMULATOR_v1 has been **removed from the codebase** and its logic moved inline to PGP_ORCHESTRATOR_v1. This document tracks the remaining **manual Google Cloud Platform operations** that need to be performed to complete the cleanup.

**⚠️ IMPORTANT**: These operations **CANNOT** be performed from this local environment as per project constraints. They require manual execution via GCP Console or gcloud CLI.

---

## ✅ Completed (Local Operations)

- [x] Archive PGP_ACCUMULATOR_v1 folder → `ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/PGP_ACCUMULATOR_v1_REMOVED_20251118/`
- [x] Update deployment script → `TOOLS_SCRIPTS_TESTS/scripts/deploy_all_pgp_services.sh` (removed lines 207-209)
- [x] Add inline accumulation logic to PGP_ORCHESTRATOR_v1
- [x] Update PGP_COMMON with `insert_payout_accumulation_pending()` method
- [x] Fix race condition in PGP_BATCHPROCESSOR_v1
- [x] Update documentation (PROGRESS.md, DECISIONS.md, BUGS.md)

---

## 🔴 Pending (Manual GCP Operations)

### 1. Disable Cloud Scheduler Jobs ⏰

**Service:** Cloud Scheduler
**Priority:** HIGH (prevents unnecessary Cloud Task creation)
**Estimated Cost Savings:** Minimal (~$0.10/month)

**Actions Required:**

```bash
# List all Cloud Scheduler jobs to identify PGP_ACCUMULATOR_v1 jobs
gcloud scheduler jobs list --project=pgp-live --location=us-central1 | grep accumulator

# EXAMPLE jobs that may exist (verify actual job names):
# - pgp-accumulator-v1-trigger
# - accumulator-cleanup
# - accumulator-health-check

# Disable each job (DO NOT DELETE - allows rollback if needed)
gcloud scheduler jobs pause pgp-accumulator-v1-trigger \
    --project=pgp-live \
    --location=us-central1

# Verify job is paused
gcloud scheduler jobs describe pgp-accumulator-v1-trigger \
    --project=pgp-live \
    --location=us-central1 | grep state
# Expected output: state: PAUSED
```

**Verification:**
- [ ] All PGP_ACCUMULATOR_v1 Cloud Scheduler jobs identified
- [ ] Jobs paused (NOT deleted - allows rollback)
- [ ] No new Cloud Tasks being created for PGP_ACCUMULATOR_v1

---

### 2. Deprovision Cloud Run Service 🚀

**Service:** Cloud Run
**Priority:** MEDIUM (reduces costs and clutter)
**Estimated Cost Savings:** ~$20/month (512Mi memory, 0 min instances)

**Actions Required:**

```bash
# Verify service exists
gcloud run services describe pgp-accumulator-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --format="value(metadata.name, status.url)"

# Get current service configuration (BACKUP before deletion)
gcloud run services describe pgp-accumulator-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --format=yaml > /tmp/pgp-accumulator-v1-backup-$(date +%Y%m%d).yaml

# Delete the Cloud Run service
gcloud run services delete pgp-accumulator-v1 \
    --project=pgp-live \
    --region=us-central1 \
    --quiet

# Verify deletion
gcloud run services list --project=pgp-live --region=us-central1 | grep accumulator
# Expected: No results
```

**Verification:**
- [ ] Service configuration backed up to YAML
- [ ] Service deleted from Cloud Run
- [ ] Service no longer appears in `gcloud run services list`
- [ ] No billing charges for pgp-accumulator-v1

---

### 3. Remove Cloud Tasks Queues 📬

**Service:** Cloud Tasks
**Priority:** LOW (queue will remain empty, minimal cost)
**Estimated Cost Savings:** ~$0.01/month

**Actions Required:**

```bash
# List all Cloud Tasks queues
gcloud tasks queues list --project=pgp-live --location=us-central1 | grep accumulator

# EXAMPLE queue names (verify actual names):
# - pgp-accumulator-queue
# - accumulator-processing-queue

# OPTION 1: Pause queue (recommended - allows rollback)
gcloud tasks queues pause pgp-accumulator-queue \
    --project=pgp-live \
    --location=us-central1

# OPTION 2: Delete queue (permanent - only if confident)
# gcloud tasks queues delete pgp-accumulator-queue \
#     --project=pgp-live \
#     --location=us-central1 \
#     --quiet

# Verify queue status
gcloud tasks queues describe pgp-accumulator-queue \
    --project=pgp-live \
    --location=us-central1 | grep state
# Expected (if paused): state: PAUSED
```

**Verification:**
- [ ] All PGP_ACCUMULATOR_v1 Cloud Tasks queues identified
- [ ] Queues paused or deleted
- [ ] No new tasks being enqueued

---

### 4. Revoke IAM Service Account Permissions 🔐

**Service:** IAM & Admin
**Priority:** MEDIUM (security best practice - remove unused permissions)
**Estimated Cost Savings:** None (security improvement)

**Actions Required:**

```bash
# List service account
gcloud iam service-accounts list --project=pgp-live | grep accumulator
# Expected: pgp-accumulator-v1-sa@pgp-live.iam.gserviceaccount.com

# Get current IAM policy bindings (BACKUP before changes)
gcloud projects get-iam-policy pgp-live \
    --flatten="bindings[].members" \
    --filter="bindings.members:pgp-accumulator-v1-sa@pgp-live.iam.gserviceaccount.com" \
    --format=yaml > /tmp/pgp-accumulator-v1-iam-backup-$(date +%Y%m%d).yaml

# OPTION 1: Disable service account (recommended - allows rollback)
gcloud iam service-accounts disable pgp-accumulator-v1-sa@pgp-live.iam.gserviceaccount.com \
    --project=pgp-live

# OPTION 2: Delete service account (permanent)
# gcloud iam service-accounts delete pgp-accumulator-v1-sa@pgp-live.iam.gserviceaccount.com \
#     --project=pgp-live \
#     --quiet

# Verify service account disabled
gcloud iam service-accounts describe pgp-accumulator-v1-sa@pgp-live.iam.gserviceaccount.com \
    --project=pgp-live | grep disabled
# Expected: disabled: true
```

**Verification:**
- [ ] IAM policy backed up to YAML
- [ ] Service account disabled or deleted
- [ ] No active tokens for pgp-accumulator-v1-sa

---

### 5. Remove Secret Manager References 🔑

**Service:** Secret Manager
**Priority:** LOW (secrets remain unused, no cost impact)
**Estimated Cost Savings:** None

**Actions Required:**

```bash
# List all secrets related to PGP_ACCUMULATOR_v1
gcloud secrets list --project=pgp-live | grep -i accumulator

# EXAMPLE secrets that may exist (verify actual names):
# - PGP_ACCUMULATOR_SIGNING_KEY
# - PGP_ACCUMULATOR_URL
# - pgp_accumulator_config

# OPTION 1: No action needed (secrets remain for historical reference)
# OPTION 2: Delete secrets if confirmed unused
# gcloud secrets delete PGP_ACCUMULATOR_SIGNING_KEY \
#     --project=pgp-live \
#     --quiet
```

**Verification:**
- [ ] All PGP_ACCUMULATOR_v1 secrets identified
- [ ] Decision made: keep for historical reference OR delete

---

### 6. Update Monitoring & Alerting 📊

**Service:** Cloud Monitoring
**Priority:** LOW (prevents confusing metrics)
**Estimated Cost Savings:** None

**Actions Required:**

1. **Remove PGP_ACCUMULATOR_v1 from Dashboards**:
   - Open Cloud Monitoring Console → Dashboards
   - Identify dashboards with "PGP_ACCUMULATOR_v1" or "Accumulator" charts
   - Remove or hide charts related to the service

2. **Disable Alerting Policies**:
   ```bash
   # List alerting policies
   gcloud alpha monitoring policies list --project=pgp-live | grep -i accumulator

   # Disable each policy (DO NOT DELETE - allows rollback)
   gcloud alpha monitoring policies update [POLICY_ID] \
       --project=pgp-live \
       --no-enabled
   ```

3. **Update Uptime Checks**:
   ```bash
   # List uptime checks
   gcloud monitoring uptime list --project=pgp-live | grep -i accumulator

   # Delete uptime checks (service no longer exists)
   gcloud monitoring uptime delete [CHECK_ID] \
       --project=pgp-live \
       --quiet
   ```

**Verification:**
- [ ] Dashboards updated (no PGP_ACCUMULATOR_v1 charts)
- [ ] Alerting policies disabled
- [ ] Uptime checks removed

---

## 📋 Rollback Plan (In Case of Issues)

If PGP_ACCUMULATOR_v1 needs to be restored:

1. **Restore from Archive**:
   ```bash
   cp -r ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/PGP_ACCUMULATOR_v1_REMOVED_20251118/* PGP_ACCUMULATOR_v1/
   ```

2. **Revert Code Changes**:
   - Revert PGP_ORCHESTRATOR_v1 changes (remove inline accumulation logic)
   - Revert PGP_COMMON changes (remove insert_payout_accumulation_pending method)
   - Revert deployment script changes

3. **Re-enable GCP Resources**:
   - Resume Cloud Scheduler jobs
   - Redeploy Cloud Run service from backup YAML
   - Resume Cloud Tasks queues
   - Re-enable service account

4. **Restore PGP_ORCHESTRATOR_v1 enqueue logic**:
   - Add back Cloud Task enqueue to PGP_ACCUMULATOR_v1

---

## 💰 Total Cost Savings

| Resource | Monthly Cost (Before) | Monthly Cost (After) | Savings |
|----------|----------------------|---------------------|---------|
| Cloud Run (pgp-accumulator-v1) | ~$20/month | $0 | **$20** |
| Cloud Scheduler | ~$0.10/month | $0 | **$0.10** |
| Cloud Tasks | ~$0.01/month | $0 | **$0.01** |
| **TOTAL** | **~$20.11/month** | **$0** | **~$20.11/month** |
| **Annual Savings** | | | **~$241/year** |

---

## 🎯 Completion Criteria

PGP_ACCUMULATOR_v1 cleanup is **COMPLETE** when:

- [x] Local code changes applied (inline accumulation logic)
- [x] Archive created
- [x] Deployment scripts updated
- [ ] Cloud Scheduler jobs paused
- [ ] Cloud Run service deprovisioned
- [ ] Cloud Tasks queues paused/deleted
- [ ] IAM service account disabled
- [ ] Monitoring/alerting updated
- [ ] Cost savings verified in billing dashboard

---

## 📝 Execution Log

| Date | Action | Status | Notes |
|------|--------|--------|-------|
| 2025-11-18 | Local code changes | ✅ COMPLETE | Inline accumulation logic added to PGP_ORCHESTRATOR_v1 |
| 2025-11-18 | Archive created | ✅ COMPLETE | Backed up to ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/ |
| 2025-11-18 | Deployment scripts updated | ✅ COMPLETE | deploy_all_pgp_services.sh updated (16 services) |
| TBD | Cloud Scheduler jobs paused | 🔴 PENDING | Requires manual GCP Console/CLI access |
| TBD | Cloud Run service deleted | 🔴 PENDING | Requires manual GCP Console/CLI access |
| TBD | Cloud Tasks queues paused | 🔴 PENDING | Requires manual GCP Console/CLI access |
| TBD | IAM service account disabled | 🔴 PENDING | Requires manual GCP Console/CLI access |
| TBD | Monitoring updated | 🔴 PENDING | Requires manual GCP Console/CLI access |

---

## 🔗 References

- **Analysis Document**: `/THINK/AUTO/PGP_THRESHOLD_REVIEW.md`
- **Progress Tracker**: `/PROGRESS.md` (2025-11-18 entry)
- **Architectural Decision**: `/DECISIONS.md` (Decision 13.1)
- **Archive Location**: `/ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/PGP_ACCUMULATOR_v1_REMOVED_20251118/`
- **Deployment Script**: `/TOOLS_SCRIPTS_TESTS/scripts/deploy_all_pgp_services.sh`

---

**End of Document**
