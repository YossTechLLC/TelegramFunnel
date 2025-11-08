# Queue Names Migration to Secret Manager - Implementation Checklist
## Date: 2025-10-26

---

## 📋 OVERVIEW

**Objective**: Migrate all Cloud Tasks queue names from environment variables to Google Cloud Secret Manager.

**Current State**: Queue names are fetched as plain environment variables using `get_env_var()`

**Target State**: Queue names fetched from Secret Manager using `fetch_secret()`

---

## 🔍 PHASE 1: DISCOVERY - IDENTIFY ALL QUEUE VARIABLES

### Queue Variables Inventory

| Variable Name | Used In Service(s) | Current Method | Config Line(s) |
|---------------|-------------------|----------------|----------------|
| **GCSPLIT2_QUEUE** | GCSplit1-10-26 | `get_env_var()` | config_manager.py:118-121 |
| **GCSPLIT3_QUEUE** | GCSplit1-10-26 | `get_env_var()` | config_manager.py:128-131 |
| **HOSTPAY_QUEUE** | GCSplit1-10-26 | `get_env_var()` | config_manager.py:138-141 |
| **GCSPLIT1_RESPONSE_QUEUE** (GCSplit2) | GCSplit2-10-26 | `get_env_var()` | config_manager.py:103-106 |
| **GCSPLIT1_RESPONSE_QUEUE** (GCSplit3) | GCSplit3-10-26 | `get_env_var()` | config_manager.py:103-106 |

**Total Queue Variables**: 4 unique variables (5 total usages across services)

---

## 🎯 PHASE 2: SECRET MANAGER SETUP

### Required Secrets to Create

Create the following secrets in Google Cloud Secret Manager:

```bash
# Project ID: 291176869049
# Region: us-central1

# 1. GCSPLIT2_QUEUE
gcloud secrets create GCSPLIT2_QUEUE \
  --project=telepay-459221 \
  --replication-policy="automatic"

echo -n "gcsplit-usdt-eth-estimate-queue" | \
  gcloud secrets versions add GCSPLIT2_QUEUE \
  --project=telepay-459221 \
  --data-file=-

# 2. GCSPLIT3_QUEUE
gcloud secrets create GCSPLIT3_QUEUE \
  --project=telepay-459221 \
  --replication-policy="automatic"

echo -n "gcsplit-eth-client-swap-queue" | \
  gcloud secrets versions add GCSPLIT3_QUEUE \
  --project=telepay-459221 \
  --data-file=-

# 3. HOSTPAY_QUEUE
gcloud secrets create HOSTPAY_QUEUE \
  --project=telepay-459221 \
  --replication-policy="automatic"

echo -n "gcsplit-hostpay-trigger-queue" | \
  gcloud secrets versions add HOSTPAY_QUEUE \
  --project=telepay-459221 \
  --data-file=-

# 4. GCSPLIT1_RESPONSE_QUEUE (for GCSplit2)
gcloud secrets create GCSPLIT2_RESPONSE_QUEUE \
  --project=telepay-459221 \
  --replication-policy="automatic"

echo -n "gcsplit-usdt-eth-response-queue" | \
  gcloud secrets versions add GCSPLIT2_RESPONSE_QUEUE \
  --project=telepay-459221 \
  --data-file=-

# 5. GCSPLIT1_RESPONSE_QUEUE (for GCSplit3)
gcloud secrets create GCSPLIT3_RESPONSE_QUEUE \
  --project=telepay-459221 \
  --replication-policy="automatic"

echo -n "gcsplit-eth-client-response-queue" | \
  gcloud secrets versions add GCSPLIT3_RESPONSE_QUEUE \
  --project=telepay-459221 \
  --data-file=-
```

### Verification Commands

```bash
# Verify all secrets exist
gcloud secrets list --project=telepay-459221 | grep -E "(GCSPLIT2_QUEUE|GCSPLIT3_QUEUE|HOSTPAY_QUEUE|GCSPLIT2_RESPONSE_QUEUE|GCSPLIT3_RESPONSE_QUEUE)"

# Verify secret values
gcloud secrets versions access latest --secret=GCSPLIT2_QUEUE --project=telepay-459221
gcloud secrets versions access latest --secret=GCSPLIT3_QUEUE --project=telepay-459221
gcloud secrets versions access latest --secret=HOSTPAY_QUEUE --project=telepay-459221
gcloud secrets versions access latest --secret=GCSPLIT2_RESPONSE_QUEUE --project=telepay-459221
gcloud secrets versions access latest --secret=GCSPLIT3_RESPONSE_QUEUE --project=telepay-459221
```

**Status**: ⬜ Secrets Created and Verified

---

## ✏️ PHASE 3: CODE CHANGES

### File 1: GCSplit1-10-26/config_manager.py

**Lines to Change**: 118-141

#### Change 1: GCSPLIT2_QUEUE
**Current** (lines 118-121):
```python
gcsplit2_queue = self.get_env_var(
    "GCSPLIT2_QUEUE",
    "GCSplit2 queue name"
)
```

**New**:
```python
gcsplit2_queue = self.fetch_secret(
    "GCSPLIT2_QUEUE",
    "GCSplit2 queue name"
)
```

**Status**: ⬜ Updated

---

#### Change 2: GCSPLIT3_QUEUE
**Current** (lines 128-131):
```python
gcsplit3_queue = self.get_env_var(
    "GCSPLIT3_QUEUE",
    "GCSplit3 queue name"
)
```

**New**:
```python
gcsplit3_queue = self.fetch_secret(
    "GCSPLIT3_QUEUE",
    "GCSplit3 queue name"
)
```

**Status**: ⬜ Updated

---

#### Change 3: HOSTPAY_QUEUE
**Current** (lines 138-141):
```python
hostpay_queue = self.get_env_var(
    "HOSTPAY_QUEUE",
    "HostPay trigger queue name"
)
```

**New**:
```python
hostpay_queue = self.fetch_secret(
    "HOSTPAY_QUEUE",
    "HostPay trigger queue name"
)
```

**Status**: ⬜ Updated

---

### File 2: GCSplit2-10-26/config_manager.py

**Lines to Change**: 103-106

#### Change 4: GCSPLIT1_RESPONSE_QUEUE (GCSplit2)
**Current** (lines 103-106):
```python
gcsplit1_response_queue = self.get_env_var(
    "GCSPLIT1_RESPONSE_QUEUE",
    "GCSplit1 response queue name"
)
```

**New**:
```python
gcsplit1_response_queue = self.fetch_secret(
    "GCSPLIT2_RESPONSE_QUEUE",
    "GCSplit1 response queue name"
)
```

**Status**: ⬜ Updated

**Note**: Renamed to GCSPLIT2_RESPONSE_QUEUE for clarity (this is the queue GCSplit2 uses to respond to GCSplit1)

---

### File 3: GCSplit3-10-26/config_manager.py

**Lines to Change**: 103-106

#### Change 5: GCSPLIT1_RESPONSE_QUEUE (GCSplit3)
**Current** (lines 103-106):
```python
gcsplit1_response_queue = self.get_env_var(
    "GCSPLIT1_RESPONSE_QUEUE",
    "GCSplit1 response queue name"
)
```

**New**:
```python
gcsplit1_response_queue = self.fetch_secret(
    "GCSPLIT3_RESPONSE_QUEUE",
    "GCSplit1 response queue name"
)
```

**Status**: ⬜ Updated

**Note**: Renamed to GCSPLIT3_RESPONSE_QUEUE for clarity (this is the queue GCSplit3 uses to respond to GCSplit1)

---

## 📝 PHASE 4: DOCUMENTATION UPDATES

### File 4: DEPLOYMENT_GUIDE.md

#### Update 1: Environment Variables Section - GCSplit1 (Lines 98-119)

**Current**:
```bash
# Cloud Tasks configuration
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
GCSPLIT2_QUEUE=gcsplit-usdt-eth-estimate-queue
GCSPLIT2_URL=https://gcsplit2-10-26-xxx.run.app
GCSPLIT3_QUEUE=gcsplit-eth-client-swap-queue
GCSPLIT3_URL=https://gcsplit3-10-26-xxx.run.app
HOSTPAY_QUEUE=gcsplit-hostpay-trigger-queue
```

**New**:
```bash
# Cloud Tasks configuration
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
GCSPLIT2_QUEUE=projects/291176869049/secrets/GCSPLIT2_QUEUE/versions/latest
GCSPLIT2_URL=https://gcsplit2-10-26-xxx.run.app
GCSPLIT3_QUEUE=projects/291176869049/secrets/GCSPLIT3_QUEUE/versions/latest
GCSPLIT3_URL=https://gcsplit3-10-26-xxx.run.app
HOSTPAY_QUEUE=projects/291176869049/secrets/HOSTPAY_QUEUE/versions/latest
```

**Status**: ⬜ Updated

---

#### Update 2: Environment Variables Section - GCSplit2 (Lines 122-132)

**Current**:
```bash
# Cloud Tasks configuration
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
GCSPLIT1_RESPONSE_QUEUE=gcsplit-usdt-eth-response-queue
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/usdt-eth-estimate
```

**New**:
```bash
# Cloud Tasks configuration
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
GCSPLIT2_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT2_RESPONSE_QUEUE/versions/latest
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/usdt-eth-estimate
```

**Status**: ⬜ Updated

**Note**: Variable renamed from GCSPLIT1_RESPONSE_QUEUE to GCSPLIT2_RESPONSE_QUEUE

---

#### Update 3: Environment Variables Section - GCSplit3 (Lines 135-145)

**Current**:
```bash
# Cloud Tasks configuration
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
GCSPLIT1_RESPONSE_QUEUE=gcsplit-eth-client-response-queue
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/eth-client-swap
```

**New**:
```bash
# Cloud Tasks configuration
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
GCSPLIT3_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT3_RESPONSE_QUEUE/versions/latest
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/eth-client-swap
```

**Status**: ⬜ Updated

**Note**: Variable renamed from GCSPLIT1_RESPONSE_QUEUE to GCSPLIT3_RESPONSE_QUEUE

---

#### Update 4: GCSplit1 Deployment Command (Lines 180-204)

**Current**:
```bash
--set-env-vars="
...
GCSPLIT2_QUEUE=gcsplit-usdt-eth-estimate-queue,
...
GCSPLIT3_QUEUE=gcsplit-eth-client-swap-queue,
...
HOSTPAY_QUEUE=gcsplit-hostpay-trigger-queue"
```

**New**:
```bash
--set-env-vars="
...
GCSPLIT2_QUEUE=projects/291176869049/secrets/GCSPLIT2_QUEUE/versions/latest,
...
GCSPLIT3_QUEUE=projects/291176869049/secrets/GCSPLIT3_QUEUE/versions/latest,
...
HOSTPAY_QUEUE=projects/291176869049/secrets/HOSTPAY_QUEUE/versions/latest"
```

**Status**: ⬜ Updated

---

#### Update 5: GCSplit2 Deployment Command (Lines 209-227)

**Current**:
```bash
--set-env-vars="
...
GCSPLIT1_RESPONSE_QUEUE=gcsplit-usdt-eth-response-queue,
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/usdt-eth-estimate"
```

**New**:
```bash
--set-env-vars="
...
GCSPLIT2_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT2_RESPONSE_QUEUE/versions/latest,
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/usdt-eth-estimate"
```

**Status**: ⬜ Updated

---

#### Update 6: GCSplit3 Deployment Command (Lines 232-250)

**Current**:
```bash
--set-env-vars="
...
GCSPLIT1_RESPONSE_QUEUE=gcsplit-eth-client-response-queue,
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/eth-client-swap"
```

**New**:
```bash
--set-env-vars="
...
GCSPLIT3_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT3_RESPONSE_QUEUE/versions/latest,
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/eth-client-swap"
```

**Status**: ⬜ Updated

---

#### Update 7: GCSplit1 Re-deployment Command (Lines 256-267)

**Current**:
```bash
gcloud run services update gcsplit1-10-26 \
  --region us-central1 \
  --update-env-vars="
GCSPLIT2_URL=https://gcsplit2-10-26-xxx.run.app,
GCSPLIT3_URL=https://gcsplit3-10-26-xxx.run.app"
```

**New**: No change needed (queue names already set in initial deployment)

**Status**: ✅ No changes required

---

### File 5: CLOUD_TASKS_ARCHITECTURE_DESIGN.md

**Search for**: Queue name references

**Action**: Update any hardcoded queue names or environment variable examples to reference Secret Manager

**Status**: ⬜ Updated

---

### File 6: SANITY_CHECK_CORRECTIONS.md

**Action**: Add a new section documenting queue names migration to Secret Manager

**Status**: ⬜ Updated

---

## 🧪 PHASE 5: TESTING & VERIFICATION

### Pre-Deployment Testing

- [ ] **Verify Secrets Exist**
  ```bash
  gcloud secrets list --project=telepay-459221 | grep QUEUE
  ```

- [ ] **Verify Secret Values**
  ```bash
  gcloud secrets versions access latest --secret=GCSPLIT2_QUEUE --project=telepay-459221
  # Should output: gcsplit-usdt-eth-estimate-queue

  gcloud secrets versions access latest --secret=GCSPLIT3_QUEUE --project=telepay-459221
  # Should output: gcsplit-eth-client-swap-queue

  gcloud secrets versions access latest --secret=HOSTPAY_QUEUE --project=telepay-459221
  # Should output: gcsplit-hostpay-trigger-queue

  gcloud secrets versions access latest --secret=GCSPLIT2_RESPONSE_QUEUE --project=telepay-459221
  # Should output: gcsplit-usdt-eth-response-queue

  gcloud secrets versions access latest --secret=GCSPLIT3_RESPONSE_QUEUE --project=telepay-459221
  # Should output: gcsplit-eth-client-response-queue
  ```

- [ ] **Verify IAM Permissions**
  ```bash
  # Ensure Cloud Run service accounts have Secret Manager access
  gcloud projects add-iam-policy-binding telepay-459221 \
    --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
  ```

### Post-Deployment Testing

- [ ] **GCSplit1 Health Check**
  ```bash
  curl https://gcsplit1-10-26-xxx.run.app/health
  # Verify "cloudtasks": "healthy"
  ```

- [ ] **GCSplit2 Health Check**
  ```bash
  curl https://gcsplit2-10-26-xxx.run.app/health
  # Verify "cloudtasks": "healthy"
  ```

- [ ] **GCSplit3 Health Check**
  ```bash
  curl https://gcsplit3-10-26-xxx.run.app/health
  # Verify "cloudtasks": "healthy"
  ```

- [ ] **Check Service Logs**
  ```bash
  # GCSplit1 logs
  gcloud run services logs tail gcsplit1-10-26 --region=us-central1 | grep QUEUE
  # Should see: "✅ [CONFIG] GCSplit2 Queue: ..."

  # GCSplit2 logs
  gcloud run services logs tail gcsplit2-10-26 --region=us-central1 | grep QUEUE
  # Should see: "✅ [CONFIG] GCSplit1 Response Queue: ..."

  # GCSplit3 logs
  gcloud run services logs tail gcsplit3-10-26 --region=us-central1 | grep QUEUE
  # Should see: "✅ [CONFIG] GCSplit1 Response Queue: ..."
  ```

- [ ] **End-to-End Payment Test**
  - Trigger test payment through GCWebhook
  - Verify GCSplit1 enqueues to GCSplit2 (check Cloud Tasks queue)
  - Verify GCSplit2 enqueues response to GCSplit1
  - Verify GCSplit1 enqueues to GCSplit3
  - Verify GCSplit3 enqueues response to GCSplit1
  - Verify GCSplit1 enqueues to GCHostPay
  - Verify all database records created correctly

---

## 📊 PROGRESS TRACKING

### Summary Checklist

**Phase 1: Discovery**
- [x] Identified all queue variables (5 usages, 4 unique variables)
- [x] Documented current locations and methods

**Phase 2: Secret Manager Setup**
- [ ] Created GCSPLIT2_QUEUE secret
- [ ] Created GCSPLIT3_QUEUE secret
- [ ] Created HOSTPAY_QUEUE secret
- [ ] Created GCSPLIT2_RESPONSE_QUEUE secret
- [ ] Created GCSPLIT3_RESPONSE_QUEUE secret
- [ ] Verified all secrets accessible

**Phase 3: Code Changes**
- [ ] Updated GCSplit1/config_manager.py (3 changes)
- [ ] Updated GCSplit2/config_manager.py (1 change)
- [ ] Updated GCSplit3/config_manager.py (1 change)

**Phase 4: Documentation Updates**
- [ ] Updated DEPLOYMENT_GUIDE.md environment variables section
- [ ] Updated DEPLOYMENT_GUIDE.md deployment commands (3 services)
- [ ] Updated CLOUD_TASKS_ARCHITECTURE_DESIGN.md
- [ ] Updated/Created SANITY_CHECK_CORRECTIONS.md addendum

**Phase 5: Testing**
- [ ] Pre-deployment verification (secrets exist)
- [ ] Pre-deployment verification (IAM permissions)
- [ ] Post-deployment health checks (3 services)
- [ ] Post-deployment log verification (3 services)
- [ ] End-to-end payment test

---

## 🔒 SECURITY NOTES

### Why Move Queue Names to Secret Manager?

1. **Consistency**: All configuration now in Secret Manager (no mixing with env vars)
2. **Auditability**: Queue name changes are tracked in Secret Manager audit logs
3. **Rotation**: Queue names can be rotated without code changes
4. **Access Control**: Fine-grained IAM control over who can view/modify queue names
5. **Environment Parity**: Same approach for dev/staging/prod environments

### Secret Naming Convention

**Pattern**: `[SERVICE]_[DIRECTION]_QUEUE`

- `GCSPLIT2_QUEUE` - Queue that GCSplit1 uses to send to GCSplit2
- `GCSPLIT3_QUEUE` - Queue that GCSplit1 uses to send to GCSplit3
- `HOSTPAY_QUEUE` - Queue that GCSplit1 uses to send to GCHostPay
- `GCSPLIT2_RESPONSE_QUEUE` - Queue that GCSplit2 uses to respond to GCSplit1
- `GCSPLIT3_RESPONSE_QUEUE` - Queue that GCSplit3 uses to respond to GCSplit1

---

## ⚠️ IMPORTANT NOTES

### Variable Renaming

**Original Design**:
- GCSplit2 and GCSplit3 both used `GCSPLIT1_RESPONSE_QUEUE`
- This was ambiguous (which queue exactly?)

**New Design**:
- GCSplit2 uses `GCSPLIT2_RESPONSE_QUEUE` (clearer naming)
- GCSplit3 uses `GCSPLIT3_RESPONSE_QUEUE` (clearer naming)
- Each service has its own dedicated response queue

**Benefits**:
- Clearer naming convention
- Easier to debug (know which service a queue belongs to)
- Prevents configuration mistakes
- Aligns with microservices best practices

### Backward Compatibility

**Breaking Change**: This is a breaking change that requires:
1. Creating new secrets
2. Updating code
3. Re-deploying all 3 services
4. Cannot roll back without reverting code changes

**Mitigation**: Test thoroughly in staging before production deployment

---

## 🎯 COMPLETION CRITERIA

This migration is complete when:

✅ All 5 queue secrets created in Secret Manager
✅ All 5 code changes implemented and tested locally
✅ All 7 documentation updates completed
✅ All 3 services deployed successfully
✅ All health checks passing
✅ End-to-end payment test successful
✅ No errors in Cloud Run logs related to queue configuration

---

**Created**: 2025-10-26
**Created By**: Claude Code
**Status**: 🟡 **READY FOR IMPLEMENTATION**
