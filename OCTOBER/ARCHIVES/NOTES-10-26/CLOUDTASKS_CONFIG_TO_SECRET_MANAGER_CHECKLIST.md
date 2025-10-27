# Cloud Tasks Configuration to Secret Manager - Migration Checklist
## Date: 2025-10-26

---

## 📋 **OBJECTIVE**

Migrate Cloud Tasks configuration values (PROJECT_ID and LOCATION) from plain environment variables to Google Cloud Secret Manager for consistency and security.

**Variables to Migrate**:
1. `CLOUD_TASKS_PROJECT_ID` → Secret Manager
2. `CLOUD_TASKS_LOCATION` → Secret Manager

---

## 🔍 **PHASE 1: DISCOVERY**

### **Step 1: Identify All Occurrences**

**Files Containing These Variables**:
- ✅ `GCSplit1-10-26/config_manager.py` (Lines 108-116)
- ✅ `GCSplit2-10-26/config_manager.py` (Lines 93-101)
- ✅ `GCSplit3-10-26/config_manager.py` (Lines 93-101)
- ✅ `DEPLOYMENT_GUIDE.md` (Multiple sections)
- ✅ `deploy_cloud_tasks_queues.sh` (Script uses these for queue deployment)
- ⚠️ `QUEUE_NAMES_TO_SECRET_MANAGER_CHECKLIST.md` (Documentation only)
- ⚠️ `CLOUD_TASKS_ARCHITECTURE_DESIGN.md` (Documentation only)

**Legend**:
- ✅ = Requires code/configuration changes
- ⚠️ = Documentation reference only (may need updating for consistency)

---

### **Step 2: Current Implementation Analysis**

#### **GCSplit1-10-26/config_manager.py** (Lines 108-116)

**Current Code**:
```python
cloud_tasks_project_id = self.get_env_var(
    "CLOUD_TASKS_PROJECT_ID",
    "Cloud Tasks project ID"
)

cloud_tasks_location = self.get_env_var(
    "CLOUD_TASKS_LOCATION",
    "Cloud Tasks location/region"
)
```

**Status**: ❌ Uses `get_env_var()` - needs migration to `fetch_secret()`

---

#### **GCSplit2-10-26/config_manager.py** (Lines 93-101)

**Current Code**:
```python
cloud_tasks_project_id = self.get_env_var(
    "CLOUD_TASKS_PROJECT_ID",
    "Cloud Tasks project ID"
)

cloud_tasks_location = self.get_env_var(
    "CLOUD_TASKS_LOCATION",
    "Cloud Tasks location/region"
)
```

**Status**: ❌ Uses `get_env_var()` - needs migration to `fetch_secret()`

---

#### **GCSplit3-10-26/config_manager.py** (Lines 93-101)

**Current Code**:
```python
cloud_tasks_project_id = self.get_env_var(
    "CLOUD_TASKS_PROJECT_ID",
    "Cloud Tasks project ID"
)

cloud_tasks_location = self.get_env_var(
    "CLOUD_TASKS_LOCATION",
    "Cloud Tasks location/region"
)
```

**Status**: ❌ Uses `get_env_var()` - needs migration to `fetch_secret()`

---

#### **DEPLOYMENT_GUIDE.md**

**Current Configuration** (Lines 112-113, 128-129, 141-142):
```bash
# GCSplit1
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1

# GCSplit2
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1

# GCSplit3
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
```

**Status**: ❌ All three services need updated environment variable format

---

## 🎯 **PHASE 2: SECRET MANAGER SETUP**

### **Step 3: Create Secrets in Google Cloud**

**Secrets to Create**:

1. **CLOUD_TASKS_PROJECT_ID**
   - Value: `telepay-459221`
   - Purpose: Project ID for Cloud Tasks API calls

2. **CLOUD_TASKS_LOCATION**
   - Value: `us-central1`
   - Purpose: Region/location for Cloud Tasks queues

**Creation Commands**:
```bash
# 1. Create CLOUD_TASKS_PROJECT_ID secret
gcloud secrets create CLOUD_TASKS_PROJECT_ID \
    --project=telepay-459221 \
    --replication-policy="automatic"

echo -n "telepay-459221" | gcloud secrets versions add CLOUD_TASKS_PROJECT_ID \
    --project=telepay-459221 \
    --data-file=-

# 2. Create CLOUD_TASKS_LOCATION secret
gcloud secrets create CLOUD_TASKS_LOCATION \
    --project=telepay-459221 \
    --replication-policy="automatic"

echo -n "us-central1" | gcloud secrets versions add CLOUD_TASKS_LOCATION \
    --project=telepay-459221 \
    --data-file=-
```

**Verification**:
```bash
# Verify secrets exist
gcloud secrets list --project=telepay-459221 | grep CLOUD_TASKS

# Verify values
gcloud secrets versions access latest --secret=CLOUD_TASKS_PROJECT_ID --project=telepay-459221
gcloud secrets versions access latest --secret=CLOUD_TASKS_LOCATION --project=telepay-459221
```

---

### **Step 4: Grant IAM Permissions**

**Service Account**:
```
291176869049-compute@developer.gserviceaccount.com
```

**Grant Access Commands**:
```bash
# Grant access to CLOUD_TASKS_PROJECT_ID
gcloud secrets add-iam-policy-binding CLOUD_TASKS_PROJECT_ID \
    --project=telepay-459221 \
    --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Grant access to CLOUD_TASKS_LOCATION
gcloud secrets add-iam-policy-binding CLOUD_TASKS_LOCATION \
    --project=telepay-459221 \
    --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 🔧 **PHASE 3: CODE CHANGES**

### **Change 1: GCSplit1-10-26/config_manager.py (Lines 108-116)**

**Before**:
```python
# Get environment variables for Cloud Tasks
cloud_tasks_project_id = self.get_env_var(
    "CLOUD_TASKS_PROJECT_ID",
    "Cloud Tasks project ID"
)

cloud_tasks_location = self.get_env_var(
    "CLOUD_TASKS_LOCATION",
    "Cloud Tasks location/region"
)
```

**After**:
```python
# Get Cloud Tasks configuration from Secret Manager
cloud_tasks_project_id = self.fetch_secret(
    "CLOUD_TASKS_PROJECT_ID",
    "Cloud Tasks project ID"
)

cloud_tasks_location = self.fetch_secret(
    "CLOUD_TASKS_LOCATION",
    "Cloud Tasks location/region"
)
```

**Status**: ⏳ Pending

---

### **Change 2: GCSplit2-10-26/config_manager.py (Lines 93-101)**

**Before**:
```python
# Get environment variables for Cloud Tasks
cloud_tasks_project_id = self.get_env_var(
    "CLOUD_TASKS_PROJECT_ID",
    "Cloud Tasks project ID"
)

cloud_tasks_location = self.get_env_var(
    "CLOUD_TASKS_LOCATION",
    "Cloud Tasks location/region"
)
```

**After**:
```python
# Get Cloud Tasks configuration from Secret Manager
cloud_tasks_project_id = self.fetch_secret(
    "CLOUD_TASKS_PROJECT_ID",
    "Cloud Tasks project ID"
)

cloud_tasks_location = self.fetch_secret(
    "CLOUD_TASKS_LOCATION",
    "Cloud Tasks location/region"
)
```

**Status**: ⏳ Pending

---

### **Change 3: GCSplit3-10-26/config_manager.py (Lines 93-101)**

**Before**:
```python
# Get environment variables for Cloud Tasks
cloud_tasks_project_id = self.get_env_var(
    "CLOUD_TASKS_PROJECT_ID",
    "Cloud Tasks project ID"
)

cloud_tasks_location = self.get_env_var(
    "CLOUD_TASKS_LOCATION",
    "Cloud Tasks location/region"
)
```

**After**:
```python
# Get Cloud Tasks configuration from Secret Manager
cloud_tasks_project_id = self.fetch_secret(
    "CLOUD_TASKS_PROJECT_ID",
    "Cloud Tasks project ID"
)

cloud_tasks_location = self.fetch_secret(
    "CLOUD_TASKS_LOCATION",
    "Cloud Tasks location/region"
)
```

**Status**: ⏳ Pending

---

## 📝 **PHASE 4: DOCUMENTATION UPDATES**

### **Update 1: DEPLOYMENT_GUIDE.md - GCSplit1 Environment Variables**

**Location**: Lines 97-119

**Before**:
```bash
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
```

**After**:
```bash
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest
```

**Status**: ⏳ Pending

---

### **Update 2: DEPLOYMENT_GUIDE.md - GCSplit2 Environment Variables**

**Location**: Lines 121-132

**Before**:
```bash
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
```

**After**:
```bash
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest
```

**Status**: ⏳ Pending

---

### **Update 3: DEPLOYMENT_GUIDE.md - GCSplit3 Environment Variables**

**Location**: Lines 134-145

**Before**:
```bash
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1
```

**After**:
```bash
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest
```

**Status**: ⏳ Pending

---

### **Update 4: DEPLOYMENT_GUIDE.md - GCSplit1 Deployment Command**

**Location**: Lines 176-204

**Before**:
```bash
CLOUD_TASKS_PROJECT_ID=telepay-459221,
CLOUD_TASKS_LOCATION=us-central1,
```

**After**:
```bash
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest,
```

**Status**: ⏳ Pending

---

### **Update 5: DEPLOYMENT_GUIDE.md - GCSplit2 Deployment Command**

**Location**: Lines 208-227

**Before**:
```bash
CLOUD_TASKS_PROJECT_ID=telepay-459221,
CLOUD_TASKS_LOCATION=us-central1,
```

**After**:
```bash
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest,
```

**Status**: ⏳ Pending

---

### **Update 6: DEPLOYMENT_GUIDE.md - GCSplit3 Deployment Command**

**Location**: Lines 231-250

**Before**:
```bash
CLOUD_TASKS_PROJECT_ID=telepay-459221,
CLOUD_TASKS_LOCATION=us-central1,
```

**After**:
```bash
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest,
```

**Status**: ⏳ Pending

---

### **Update 7: SANITY_CHECK_CORRECTIONS.md - Add Addendum 3**

Add new section documenting this migration with:
- Before/after comparison
- Rationale
- Setup & verification commands

**Status**: ⏳ Pending

---

## 🚀 **PHASE 5: AUTOMATION SCRIPT UPDATE**

### **Update 8: setup_cloudtasks_secrets.sh**

**Current**: Creates 9 secrets (5 queues + 4 URLs)

**After**: Creates 11 secrets (5 queues + 4 URLs + 2 config values)

**New Secrets to Add**:
```bash
# 10. CLOUD_TASKS_PROJECT_ID
create_or_update_secret "CLOUD_TASKS_PROJECT_ID" "telepay-459221"

# 11. CLOUD_TASKS_LOCATION
create_or_update_secret "CLOUD_TASKS_LOCATION" "us-central1"
```

**Also Update**:
- Summary counts (9 → 11)
- IAM permissions loop to include new secrets
- Verification section

**Status**: ⏳ Pending

---

## ✅ **PHASE 6: TESTING & VERIFICATION**

### **Verification Checklist**

After implementation:

- [ ] All 2 new secrets exist in Secret Manager
- [ ] IAM permissions granted for both secrets
- [ ] GCSplit1/config_manager.py uses `fetch_secret()` for both variables
- [ ] GCSplit2/config_manager.py uses `fetch_secret()` for both variables
- [ ] GCSplit3/config_manager.py uses `fetch_secret()` for both variables
- [ ] DEPLOYMENT_GUIDE.md environment variables updated (3 sections)
- [ ] DEPLOYMENT_GUIDE.md deployment commands updated (3 commands)
- [ ] setup_cloudtasks_secrets.sh creates 11 total secrets
- [ ] SANITY_CHECK_CORRECTIONS.md ADDENDUM 3 added

### **Testing Steps**

```bash
# 1. Verify secrets in Cloud Console
gcloud secrets list --project=telepay-459221 | grep CLOUD_TASKS

# 2. Verify secret values
gcloud secrets versions access latest --secret=CLOUD_TASKS_PROJECT_ID --project=telepay-459221
gcloud secrets versions access latest --secret=CLOUD_TASKS_LOCATION --project=telepay-459221

# 3. Deploy services with new configuration
# (Follow DEPLOYMENT_GUIDE.md)

# 4. Check service logs for configuration loading
gcloud run services logs tail gcsplit1-10-26 --region=us-central1 | grep "CLOUD_TASKS"
gcloud run services logs tail gcsplit2-10-26 --region=us-central1 | grep "CLOUD_TASKS"
gcloud run services logs tail gcsplit3-10-26 --region=us-central1 | grep "CLOUD_TASKS"

# 5. Test health endpoints
curl https://gcsplit1-10-26-xxx.run.app/health
curl https://gcsplit2-10-26-xxx.run.app/health
curl https://gcsplit3-10-26-xxx.run.app/health

# 6. Trigger test payment to verify Cloud Tasks functionality
```

---

## 📊 **IMPLEMENTATION SUMMARY**

### **Total Changes Required**

| Category | Count |
|----------|-------|
| **Code Files to Modify** | 3 |
| **Code Changes** | 3 (2 lines each = 6 total lines) |
| **Documentation Updates** | 7 |
| **Script Updates** | 1 |
| **New Secrets to Create** | 2 |
| **Total Secrets in Secret Manager** | 11 (queues + URLs + config) |

### **Files Requiring Changes**

1. ✅ `GCSplit1-10-26/config_manager.py` - Change 2 lines
2. ✅ `GCSplit2-10-26/config_manager.py` - Change 2 lines
3. ✅ `GCSplit3-10-26/config_manager.py` - Change 2 lines
4. ✅ `DEPLOYMENT_GUIDE.md` - 6 updates
5. ✅ `SANITY_CHECK_CORRECTIONS.md` - Add ADDENDUM 3
6. ✅ `setup_cloudtasks_secrets.sh` - Expand to include config secrets

---

## 🎯 **BENEFITS OF THIS MIGRATION**

### **Security**
- ✅ No hardcoded project IDs or regions in code
- ✅ Centralized configuration management
- ✅ Audit trail for all configuration changes
- ✅ Fine-grained IAM access control

### **Flexibility**
- ✅ Can change project/region without code changes
- ✅ Environment-specific configuration (dev/staging/prod)
- ✅ No service re-deployment needed for config updates
- ✅ Easier A/B testing across regions

### **Consistency**
- ✅ **100% of Cloud Tasks configuration now in Secret Manager**
- ✅ No mixing of secrets and environment variables
- ✅ Uniform approach across all configuration
- ✅ Aligns with existing queue names and URLs migration

### **Operations**
- ✅ Single source of truth for configuration
- ✅ Simplified deployment process
- ✅ Reduced configuration drift
- ✅ Better change management

---

## 📋 **COMPLETE SECRET MANAGER CONFIGURATION**

After this migration, all Cloud Tasks configuration will be in Secret Manager:

### **Cloud Tasks Configuration** (11 secrets)
1. `CLOUD_TASKS_PROJECT_ID` ⭐ **NEW**
2. `CLOUD_TASKS_LOCATION` ⭐ **NEW**
3. `GCSPLIT2_QUEUE`
4. `GCSPLIT3_QUEUE`
5. `HOSTPAY_QUEUE`
6. `GCSPLIT2_RESPONSE_QUEUE`
7. `GCSPLIT3_RESPONSE_QUEUE`
8. `GCSPLIT1_ESTIMATE_RESPONSE_URL`
9. `GCSPLIT1_SWAP_RESPONSE_URL`
10. `GCSPLIT2_URL`
11. `GCSPLIT3_URL`

### **Database Credentials** (4 secrets)
12. `CLOUD_SQL_CONNECTION_NAME`
13. `DATABASE_NAME_SECRET`
14. `DATABASE_USER_SECRET`
15. `DATABASE_PASSWORD_SECRET`

### **Other Configuration** (Various)
16. `SUCCESS_URL_SIGNING_KEY`
17. `CHANGENOW_API_KEY`
18. `TPS_HOSTPAY_SIGNING_KEY`
19. `HOSTPAY_WEBHOOK_URL`
20. `TP_FLAT_FEE`

**Total Secrets**: 20+

---

## ⚠️ **BREAKING CHANGES**

This migration introduces breaking changes:

1. **Configuration Method Changed**:
   - CLOUD_TASKS_PROJECT_ID now fetched from Secret Manager (not env var)
   - CLOUD_TASKS_LOCATION now fetched from Secret Manager (not env var)

2. **Deployment Required**:
   - Cannot use old deployment commands
   - Must create new secrets before deployment
   - All 3 services must be re-deployed

3. **Secret Manager Dependency**:
   - Services will fail to start if secrets don't exist
   - Must have proper IAM permissions configured

**Mitigation**: Follow deployment workflow in order and test thoroughly.

---

## 📚 **RELATED DOCUMENTATION**

- **Queue Names Migration**: `QUEUE_MIGRATION_SUMMARY.md`
- **Service URLs Migration**: `URLS_MIGRATION_SUMMARY.md`
- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **Sanity Check**: `SANITY_CHECK_CORRECTIONS.md`
- **Setup Script**: `setup_cloudtasks_secrets.sh`
- **Architecture Design**: `CLOUD_TASKS_ARCHITECTURE_DESIGN.md`

---

**Created By**: Claude Code
**Date**: 2025-10-26
**Status**: ⏳ **READY FOR IMPLEMENTATION**
