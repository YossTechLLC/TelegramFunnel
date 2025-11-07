# NP-Webhook CloudTasks Import Fix Checklist

**Issue:** CloudTasks client initialization failing in np-webhook-10-26
**Error:** `No module named 'cloudtasks_client'`
**Root Cause:** Incorrect import statement for local module
**Created:** 2025-11-02

---

## Problem Analysis

### Error Details
```
❌ [CLOUDTASKS] Failed to initialize client: No module named 'cloudtasks_client'
⚠️ [CLOUDTASKS] GCWebhook1 triggering will not work!
```

### Root Cause
**Line 103 in app.py:**
```python
from cloudtasks_client import CloudTasksClient
```

**Issue:** This import statement assumes `cloudtasks_client` is an installed Python package, but it's actually a **local file** in the same directory as `app.py`.

**Files in np-webhook-10-26 directory:**
```
app.py
cloudtasks_client.py  ← Local module, NOT a package
requirements.txt
Dockerfile
.dockerignore
```

**Solution:** Use a relative import or import from the same directory:
```python
from .cloudtasks_client import CloudTasksClient  # Option 1 (relative import)
```

OR ensure the current directory is in Python path (which Cloud Run does by default), so:
```python
from cloudtasks_client import CloudTasksClient  # Should work, but may need verification
```

**The most reliable approach for Cloud Run:** Import directly since the working directory is `/app`:
```python
import cloudtasks_client
cloudtasks_client_instance = cloudtasks_client.CloudTasksClient(...)
```

OR add explicit path handling at the top of app.py before imports.

---

## Fix Checklist

### ✅ Step 1: Identify Import Pattern Used in Other Services
**Action:** Check how GCWebhook1, GCSplit1, GCAccumulator handle local module imports
**Status:** Pending

### ✅ Step 2: Fix np-webhook app.py Import Statement
**Action:** Update line 103 to use correct import pattern
**Expected Change:**
```python
# BEFORE (line 103):
from cloudtasks_client import CloudTasksClient

# AFTER:
import cloudtasks_client
cloudtasks_client_instance = cloudtasks_client.CloudTasksClient(CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION)
```

OR keep the from-import but verify it works:
```python
from cloudtasks_client import CloudTasksClient  # Works if cwd is /app
```

**Status:** Pending

### ✅ Step 3: Update Variable Reference
**Action:** If changing to `import cloudtasks_client`, update line 104
**Expected Change:**
```python
# BEFORE (line 104):
cloudtasks_client = CloudTasksClient(CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION)

# AFTER:
cloudtasks_client = cloudtasks_client.CloudTasksClient(CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION)
```

**Status:** Pending

### ✅ Step 4: Verify All Other Services
**Action:** Check for similar import issues in:
- [x] GCWebhook1-10-26
- [x] GCWebhook2-10-26
- [x] GCSplit1-10-26
- [x] GCSplit2-10-26
- [x] GCSplit3-10-26
- [x] GCAccumulator-10-26
- [x] GCBatchProcessor-10-26
- [x] GCMicroBatchProcessor-10-26
- [x] GCHostPay1-10-26
- [x] GCHostPay2-10-26
- [x] GCHostPay3-10-26

**Status:** Pending

### ✅ Step 5: Rebuild and Redeploy np-webhook
**Action:** Deploy fixed np-webhook service
**Command:**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26
gcloud run deploy np-webhook-10-26 \
  --source . \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-secrets=NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,GCWEBHOOK1_QUEUE=GCWEBHOOK1_QUEUE:latest,GCWEBHOOK1_URL=GCWEBHOOK1_URL:latest \
  --memory=512Mi \
  --timeout=300
```
**Status:** Pending

### ✅ Step 6: Verify CloudTasks Initialization in Logs
**Action:** Check logs for successful initialization
**Expected Log:**
```
✅ [CLOUDTASKS] Client initialized successfully
```
**Command:**
```bash
gcloud run services logs tail np-webhook-10-26 --region=us-central1 | grep CLOUDTASKS
```
**Status:** Pending

### ✅ Step 7: Test Health Endpoint
**Action:** Verify service is healthy
**Command:**
```bash
curl https://np-webhook-10-26-291176869049.us-central1.run.app/health
```
**Expected Response:**
```json
{
  "service": "np-webhook-10-26 NowPayments IPN Handler",
  "status": "healthy",
  "components": {
    "ipn_secret": "configured",
    "database_credentials": "configured",
    "connector": "initialized"
  }
}
```
**Status:** Pending

---

## Verification Plan

### Test 1: Startup Logs
**Check for:**
- ✅ `✅ [CLOUDTASKS] Client initialized successfully`
- ❌ `❌ [CLOUDTASKS] Failed to initialize client`

### Test 2: IPN Callback Simulation
**Check for:**
- CloudTasks client can enqueue tasks to GCWebhook1
- No import errors in runtime

### Test 3: Check All Services
**Ensure pattern is consistent across all microservices**

---

## Related Files
- `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26/app.py` (line 103)
- `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26/cloudtasks_client.py`

---

## Expected Outcome
✅ CloudTasks client initializes successfully on startup
✅ np-webhook can trigger GCWebhook1 via Cloud Tasks
✅ No import errors in any service
✅ Consistent import pattern across all services
