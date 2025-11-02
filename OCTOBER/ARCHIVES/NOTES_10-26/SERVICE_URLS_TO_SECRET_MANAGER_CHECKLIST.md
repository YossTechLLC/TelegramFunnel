# Service URLs Migration to Secret Manager - Implementation Checklist
## Date: 2025-10-26

---

## 📋 OVERVIEW

**Objective**: Migrate all GCSplit service URLs from environment variables to Google Cloud Secret Manager.

**Current State**: Service URLs are fetched as plain environment variables using `get_env_var()`

**Target State**: Service URLs fetched from Secret Manager using `fetch_secret()`

**Rationale**: Consistency with queue names and database credentials - all configuration in Secret Manager.

---

## 🔍 PHASE 1: DISCOVERY - IDENTIFY ALL URL VARIABLES

### Service URL Variables Inventory

| Variable Name | Used In Service(s) | Current Method | Config Line(s) |
|---------------|-------------------|----------------|----------------|
| **GCSPLIT1_URL** | GCSplit2-10-26 | `get_env_var()` | config_manager.py:108-111 |
| **GCSPLIT1_URL** | GCSplit3-10-26 | `get_env_var()` | config_manager.py:108-111 |
| **GCSPLIT2_URL** | GCSplit1-10-26 | `get_env_var()` | config_manager.py:123-126 |
| **GCSPLIT3_URL** | GCSplit1-10-26 | `get_env_var()` | config_manager.py:133-136 |

**Total URL Variables**: 3 unique variables (4 total usages across services)

### URL Endpoints Stored

| Secret Name | Typical Value | Purpose |
|-------------|---------------|---------|
| **GCSPLIT1_URL** | `https://gcsplit1-10-26-xxx.run.app/usdt-eth-estimate` (GCSplit2)<br>`https://gcsplit1-10-26-xxx.run.app/eth-client-swap` (GCSplit3) | Callback URLs for GCSplit2 & GCSplit3 to respond to GCSplit1 |
| **GCSPLIT2_URL** | `https://gcsplit2-10-26-xxx.run.app` | GCSplit1 calls GCSplit2 for USDT→ETH estimates |
| **GCSPLIT3_URL** | `https://gcsplit3-10-26-xxx.run.app` | GCSplit1 calls GCSplit3 for ETH→Client swaps |

**Note**: GCSPLIT1_URL has **different values** in GCSplit2 vs GCSplit3 (different endpoints)

---

## 🎯 PHASE 2: SECRET MANAGER SETUP

### Required Secrets to Create

Create the following secrets in Google Cloud Secret Manager:

```bash
# Project ID: 291176869049
# Region: us-central1

# 1. GCSPLIT1_URL (for GCSplit2 to respond to GCSplit1)
gcloud secrets create GCSPLIT1_ESTIMATE_RESPONSE_URL \
  --project=telepay-459221 \
  --replication-policy="automatic"

echo -n "https://gcsplit1-10-26-xxx.run.app/usdt-eth-estimate" | \
  gcloud secrets versions add GCSPLIT1_ESTIMATE_RESPONSE_URL \
  --project=telepay-459221 \
  --data-file=-

# 2. GCSPLIT1_URL (for GCSplit3 to respond to GCSplit1)
gcloud secrets create GCSPLIT1_SWAP_RESPONSE_URL \
  --project=telepay-459221 \
  --replication-policy="automatic"

echo -n "https://gcsplit1-10-26-xxx.run.app/eth-client-swap" | \
  gcloud secrets versions add GCSPLIT1_SWAP_RESPONSE_URL \
  --project=telepay-459221 \
  --data-file=-

# 3. GCSPLIT2_URL (for GCSplit1 to call GCSplit2)
gcloud secrets create GCSPLIT2_URL \
  --project=telepay-459221 \
  --replication-policy="automatic"

echo -n "https://gcsplit2-10-26-xxx.run.app" | \
  gcloud secrets versions add GCSPLIT2_URL \
  --project=telepay-459221 \
  --data-file=-

# 4. GCSPLIT3_URL (for GCSplit1 to call GCSplit3)
gcloud secrets create GCSPLIT3_URL \
  --project=telepay-459221 \
  --replication-policy="automatic"

echo -n "https://gcsplit3-10-26-xxx.run.app" | \
  gcloud secrets versions add GCSPLIT3_URL \
  --project=telepay-459221 \
  --data-file=-
```

### 🔄 Important: Variable Renaming for Clarity

**Problem**: GCSplit2 and GCSplit3 both use `GCSPLIT1_URL` with **different endpoint values**:
- GCSplit2 uses: `https://gcsplit1-10-26-xxx.run.app/usdt-eth-estimate`
- GCSplit3 uses: `https://gcsplit1-10-26-xxx.run.app/eth-client-swap`

**Solution**: Rename for clarity:
- `GCSPLIT1_URL` (in GCSplit2) → `GCSPLIT1_ESTIMATE_RESPONSE_URL`
- `GCSPLIT1_URL` (in GCSplit3) → `GCSPLIT1_SWAP_RESPONSE_URL`

**Benefits**:
- Eliminates naming collision
- Clearly indicates which endpoint
- Prevents configuration mistakes

### Verification Commands

```bash
# Verify all secrets exist
gcloud secrets list --project=telepay-459221 | grep -E "(GCSPLIT1_ESTIMATE_RESPONSE_URL|GCSPLIT1_SWAP_RESPONSE_URL|GCSPLIT2_URL|GCSPLIT3_URL)"

# Verify secret values
gcloud secrets versions access latest --secret=GCSPLIT1_ESTIMATE_RESPONSE_URL --project=telepay-459221
gcloud secrets versions access latest --secret=GCSPLIT1_SWAP_RESPONSE_URL --project=telepay-459221
gcloud secrets versions access latest --secret=GCSPLIT2_URL --project=telepay-459221
gcloud secrets versions access latest --secret=GCSPLIT3_URL --project=telepay-459221
```

**Status**: ⬜ Secrets Created and Verified

---

## ✏️ PHASE 3: CODE CHANGES

### File 1: GCSplit1-10-26/config_manager.py

**Lines to Change**: 123-136

#### Change 1: GCSPLIT2_URL
**Current** (lines 123-126):
```python
gcsplit2_url = self.get_env_var(
    "GCSPLIT2_URL",
    "GCSplit2 service URL"
)
```

**New**:
```python
gcsplit2_url = self.fetch_secret(
    "GCSPLIT2_URL",
    "GCSplit2 service URL"
)
```

**Status**: ⬜ Updated

---

#### Change 2: GCSPLIT3_URL
**Current** (lines 133-136):
```python
gcsplit3_url = self.get_env_var(
    "GCSPLIT3_URL",
    "GCSplit3 service URL"
)
```

**New**:
```python
gcsplit3_url = self.fetch_secret(
    "GCSPLIT3_URL",
    "GCSplit3 service URL"
)
```

**Status**: ⬜ Updated

---

### File 2: GCSplit2-10-26/config_manager.py

**Lines to Change**: 108-111

#### Change 3: GCSPLIT1_URL (GCSplit2)
**Current** (lines 108-111):
```python
gcsplit1_url = self.get_env_var(
    "GCSPLIT1_URL",
    "GCSplit1 /usdt-eth-estimate endpoint URL"
)
```

**New**:
```python
gcsplit1_url = self.fetch_secret(
    "GCSPLIT1_ESTIMATE_RESPONSE_URL",
    "GCSplit1 /usdt-eth-estimate endpoint URL"
)
```

**Status**: ⬜ Updated

**Note**: Variable renamed from GCSPLIT1_URL to GCSPLIT1_ESTIMATE_RESPONSE_URL for clarity

---

### File 3: GCSplit3-10-26/config_manager.py

**Lines to Change**: 108-111

#### Change 4: GCSPLIT1_URL (GCSplit3)
**Current** (lines 108-111):
```python
gcsplit1_url = self.get_env_var(
    "GCSPLIT1_URL",
    "GCSplit1 /eth-client-swap endpoint URL"
)
```

**New**:
```python
gcsplit1_url = self.fetch_secret(
    "GCSPLIT1_SWAP_RESPONSE_URL",
    "GCSplit1 /eth-client-swap endpoint URL"
)
```

**Status**: ⬜ Updated

**Note**: Variable renamed from GCSPLIT1_URL to GCSPLIT1_SWAP_RESPONSE_URL for clarity

---

## 📝 PHASE 4: DOCUMENTATION UPDATES

### File 4: DEPLOYMENT_GUIDE.md

#### Update 1: Environment Variables Section - GCSplit1 (Lines ~114-118)

**Current**:
```bash
GCSPLIT2_QUEUE=projects/291176869049/secrets/GCSPLIT2_QUEUE/versions/latest
GCSPLIT2_URL=https://gcsplit2-10-26-xxx.run.app
GCSPLIT3_QUEUE=projects/291176869049/secrets/GCSPLIT3_QUEUE/versions/latest
GCSPLIT3_URL=https://gcsplit3-10-26-xxx.run.app
```

**New**:
```bash
GCSPLIT2_QUEUE=projects/291176869049/secrets/GCSPLIT2_QUEUE/versions/latest
GCSPLIT2_URL=projects/291176869049/secrets/GCSPLIT2_URL/versions/latest
GCSPLIT3_QUEUE=projects/291176869049/secrets/GCSPLIT3_QUEUE/versions/latest
GCSPLIT3_URL=projects/291176869049/secrets/GCSPLIT3_URL/versions/latest
```

**Status**: ⬜ Updated

---

#### Update 2: Environment Variables Section - GCSplit2 (Lines ~130-131)

**Current**:
```bash
GCSPLIT2_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT2_RESPONSE_QUEUE/versions/latest
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/usdt-eth-estimate
```

**New**:
```bash
GCSPLIT2_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT2_RESPONSE_QUEUE/versions/latest
GCSPLIT1_ESTIMATE_RESPONSE_URL=projects/291176869049/secrets/GCSPLIT1_ESTIMATE_RESPONSE_URL/versions/latest
```

**Status**: ⬜ Updated

**Note**: Variable renamed from GCSPLIT1_URL to GCSPLIT1_ESTIMATE_RESPONSE_URL

---

#### Update 3: Environment Variables Section - GCSplit3 (Lines ~143-144)

**Current**:
```bash
GCSPLIT3_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT3_RESPONSE_QUEUE/versions/latest
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/eth-client-swap
```

**New**:
```bash
GCSPLIT3_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT3_RESPONSE_QUEUE/versions/latest
GCSPLIT1_SWAP_RESPONSE_URL=projects/291176869049/secrets/GCSPLIT1_SWAP_RESPONSE_URL/versions/latest
```

**Status**: ⬜ Updated

**Note**: Variable renamed from GCSPLIT1_URL to GCSPLIT1_SWAP_RESPONSE_URL

---

#### Update 4: GCSplit1 Initial Deployment Command

**Current**:
```bash
GCSPLIT2_URL=https://temporary-placeholder.run.app,
...
GCSPLIT3_URL=https://temporary-placeholder.run.app,
```

**New**:
```bash
GCSPLIT2_URL=projects/291176869049/secrets/GCSPLIT2_URL/versions/latest,
...
GCSPLIT3_URL=projects/291176869049/secrets/GCSPLIT3_URL/versions/latest,
```

**Status**: ⬜ Updated

---

#### Update 5: GCSplit2 Deployment Command

**Current**:
```bash
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/usdt-eth-estimate"
```

**New**:
```bash
GCSPLIT1_ESTIMATE_RESPONSE_URL=projects/291176869049/secrets/GCSPLIT1_ESTIMATE_RESPONSE_URL/versions/latest"
```

**Status**: ⬜ Updated

---

#### Update 6: GCSplit3 Deployment Command

**Current**:
```bash
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app/eth-client-swap"
```

**New**:
```bash
GCSPLIT1_SWAP_RESPONSE_URL=projects/291176869049/secrets/GCSPLIT1_SWAP_RESPONSE_URL/versions/latest"
```

**Status**: ⬜ Updated

---

#### Update 7: GCSplit1 Re-deployment Section (Lines ~256-267)

**Current**:
```bash
gcloud run services update gcsplit1-10-26 \
  --region us-central1 \
  --update-env-vars="
GCSPLIT2_URL=https://gcsplit2-10-26-xxx.run.app,
GCSPLIT3_URL=https://gcsplit3-10-26-xxx.run.app"
```

**New**:
```bash
# NOTE: Service URLs are now in Secret Manager
# Update secret values instead of re-deploying:

# Update GCSPLIT2_URL secret
echo -n "https://gcsplit2-10-26-xxx.run.app" | \
  gcloud secrets versions add GCSPLIT2_URL \
  --project=telepay-459221 \
  --data-file=-

# Update GCSPLIT3_URL secret
echo -n "https://gcsplit3-10-26-xxx.run.app" | \
  gcloud secrets versions add GCSPLIT3_URL \
  --project=telepay-459221 \
  --data-file=-

# GCSplit1 will automatically fetch new values on next request
```

**Status**: ⬜ Updated

---

### File 5: setup_queue_secrets.sh

**Action**: Add URL secret creation to the existing script

**New Secrets to Add**:
1. GCSPLIT1_ESTIMATE_RESPONSE_URL
2. GCSPLIT1_SWAP_RESPONSE_URL
3. GCSPLIT2_URL
4. GCSPLIT3_URL

**Status**: ⬜ Updated

---

### File 6: SANITY_CHECK_CORRECTIONS.md

**Action**: Add new section documenting service URL migration

**Status**: ⬜ Updated

---

## 🧪 PHASE 5: TESTING & VERIFICATION

### Pre-Deployment Testing

- [ ] **Verify Secrets Exist**
  ```bash
  gcloud secrets list --project=telepay-459221 | grep URL
  ```

- [ ] **Verify Secret Values**
  ```bash
  # Note: These will initially have placeholder values
  # Update with actual Cloud Run URLs after deployment

  gcloud secrets versions access latest --secret=GCSPLIT1_ESTIMATE_RESPONSE_URL --project=telepay-459221
  gcloud secrets versions access latest --secret=GCSPLIT1_SWAP_RESPONSE_URL --project=telepay-459221
  gcloud secrets versions access latest --secret=GCSPLIT2_URL --project=telepay-459221
  gcloud secrets versions access latest --secret=GCSPLIT3_URL --project=telepay-459221
  ```

- [ ] **Verify IAM Permissions**
  ```bash
  # Ensure Cloud Run service accounts have Secret Manager access
  gcloud projects add-iam-policy-binding telepay-459221 \
    --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
  ```

### Post-Deployment Testing

- [ ] **GCSplit1 Health Check**
  ```bash
  curl https://gcsplit1-10-26-xxx.run.app/health
  # Verify service URLs loaded correctly
  ```

- [ ] **GCSplit2 Health Check**
  ```bash
  curl https://gcsplit2-10-26-xxx.run.app/health
  ```

- [ ] **GCSplit3 Health Check**
  ```bash
  curl https://gcsplit3-10-26-xxx.run.app/health
  ```

- [ ] **Check Service Logs**
  ```bash
  # GCSplit1 logs
  gcloud run services logs tail gcsplit1-10-26 --region=us-central1 | grep URL
  # Should see: "✅ [CONFIG] GCSplit2 URL: https://..."

  # GCSplit2 logs
  gcloud run services logs tail gcsplit2-10-26 --region=us-central1 | grep URL
  # Should see: "✅ [CONFIG] GCSplit1 ... endpoint URL: https://..."

  # GCSplit3 logs
  gcloud run services logs tail gcsplit3-10-26 --region=us-central1 | grep URL
  # Should see: "✅ [CONFIG] GCSplit1 ... endpoint URL: https://..."
  ```

- [ ] **End-to-End Payment Test**
  - Trigger test payment
  - Verify GCSplit1 → GCSplit2 communication works
  - Verify GCSplit2 → GCSplit1 response works
  - Verify GCSplit1 → GCSplit3 communication works
  - Verify GCSplit3 → GCSplit1 response works

---

## 📊 PROGRESS TRACKING

### Summary Checklist

**Phase 1: Discovery**
- [x] Identified all URL variables (4 usages, 3 unique variables)
- [x] Documented current locations and methods
- [x] Identified naming collision (GCSPLIT1_URL used twice)

**Phase 2: Secret Manager Setup**
- [ ] Created GCSPLIT1_ESTIMATE_RESPONSE_URL secret
- [ ] Created GCSPLIT1_SWAP_RESPONSE_URL secret
- [ ] Created GCSPLIT2_URL secret
- [ ] Created GCSPLIT3_URL secret
- [ ] Verified all secrets accessible

**Phase 3: Code Changes**
- [ ] Updated GCSplit1/config_manager.py (2 changes)
- [ ] Updated GCSplit2/config_manager.py (1 change + rename)
- [ ] Updated GCSplit3/config_manager.py (1 change + rename)

**Phase 4: Documentation Updates**
- [ ] Updated DEPLOYMENT_GUIDE.md environment variables sections
- [ ] Updated DEPLOYMENT_GUIDE.md deployment commands (3 services)
- [ ] Updated DEPLOYMENT_GUIDE.md re-deployment section
- [ ] Updated setup_queue_secrets.sh (add URL secrets)
- [ ] Updated SANITY_CHECK_CORRECTIONS.md

**Phase 5: Testing**
- [ ] Pre-deployment verification (secrets exist)
- [ ] Pre-deployment verification (IAM permissions)
- [ ] Post-deployment health checks (3 services)
- [ ] Post-deployment log verification (3 services)
- [ ] End-to-end payment test

---

## 🔒 SECURITY & OPERATIONAL BENEFITS

### Why Move Service URLs to Secret Manager?

1. **Consistency**: All configuration in Secret Manager (no mixing)
2. **Flexibility**: Can change URLs without re-deploying services
3. **Environment Management**: Easy dev/staging/prod URL management
4. **Auditability**: URL changes tracked in Secret Manager audit logs
5. **Access Control**: Fine-grained IAM control over URL access
6. **Rotation**: URLs can be updated by just adding new secret versions

### Secret Naming Convention

**Pattern**: `[TARGET_SERVICE]_[PURPOSE]_URL`

- `GCSPLIT1_ESTIMATE_RESPONSE_URL` - URL for GCSplit2 to send estimate responses to GCSplit1
- `GCSPLIT1_SWAP_RESPONSE_URL` - URL for GCSplit3 to send swap responses to GCSplit1
- `GCSPLIT2_URL` - URL for GCSplit1 to call GCSplit2 estimate service
- `GCSPLIT3_URL` - URL for GCSplit1 to call GCSplit3 swap service

---

## ⚠️ IMPORTANT NOTES

### Variable Renaming

**Original Design**:
- GCSplit2 and GCSplit3 both used `GCSPLIT1_URL`
- Different endpoint paths stored in same variable name
- Ambiguous and error-prone

**New Design**:
- GCSplit2 uses `GCSPLIT1_ESTIMATE_RESPONSE_URL`
- GCSplit3 uses `GCSPLIT1_SWAP_RESPONSE_URL`
- Clear naming indicates purpose

**Benefits**:
- Eliminates naming collision
- Clearer purpose/intent
- Prevents configuration mistakes
- Aligns with microservices best practices

### Deployment Sequence

**Important**: After deploying services, you'll need to update URL secrets with actual Cloud Run URLs:

1. Deploy GCSplit1 (with placeholder URL secrets)
2. Deploy GCSplit2 (with placeholder URL secrets)
3. Deploy GCSplit3 (with placeholder URL secrets)
4. Update GCSPLIT1_ESTIMATE_RESPONSE_URL with actual GCSplit1 URL + `/usdt-eth-estimate`
5. Update GCSPLIT1_SWAP_RESPONSE_URL with actual GCSplit1 URL + `/eth-client-swap`
6. Update GCSPLIT2_URL with actual GCSplit2 URL
7. Update GCSPLIT3_URL with actual GCSplit3 URL

Services will automatically fetch updated URLs on next request (no re-deployment needed).

---

## 🎯 COMPLETION CRITERIA

This migration is complete when:

✅ All 4 URL secrets created in Secret Manager
✅ All 4 code changes implemented
✅ All 7+ documentation updates completed
✅ All 3 services deployed successfully
✅ All health checks passing
✅ End-to-end payment test successful
✅ No errors in logs related to URL configuration

---

**Created**: 2025-10-26
**Created By**: Claude Code
**Status**: 🟡 **READY FOR IMPLEMENTATION**
