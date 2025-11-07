# GCMicroBatchProcessor-10-26 Dynamic Threshold Deployment Configuration

## Current Deployment Analysis

### Service Configuration
- **Service Name**: `gcmicrobatchprocessor-10-26`
- **Region**: `us-central1`
- **Image**: `gcr.io/telepay-459221/gcmicrobatchprocessor-10-26:latest`
- **Service Account**: `291176869049-compute@developer.gserviceaccount.com`
- **Memory**: `512Mi`
- **CPU**: `1`
- **Max Instances**: `10`
- **Container Concurrency**: `80`
- **Timeout**: `3600` seconds
- **Cloud SQL Instance**: `telepay-459221:us-central1:telepaypsql`

---

## Current Environment Variables

### All Environment Variables (via Secret Manager)

| Env Var Name | Type | Current Value | Description |
|-------------|------|---------------|-------------|
| `SUCCESS_URL_SIGNING_KEY` | secretKeyRef | `latest` | Token encryption/decryption key |
| `CLOUD_TASKS_PROJECT_ID` | secretKeyRef | `latest` | GCP project ID for Cloud Tasks |
| `CLOUD_TASKS_LOCATION` | secretKeyRef | `latest` | Region for Cloud Tasks queues |
| `GCHOSTPAY1_BATCH_QUEUE` | secretKeyRef | `latest` | Queue name for batch execution |
| `GCHOSTPAY1_URL` | secretKeyRef | `latest` | GCHostPay1 service URL |
| `CHANGENOW_API_KEY` | secretKeyRef | `latest` | ChangeNow API key |
| `HOST_WALLET_USDT_ADDRESS` | secretKeyRef | `latest` | Destination USDT wallet |
| `CLOUD_SQL_CONNECTION_NAME` | secretKeyRef | `latest` | Cloud SQL connection string |
| `DATABASE_NAME_SECRET` | secretKeyRef | `latest` | Database name |
| `DATABASE_USER_SECRET` | secretKeyRef | `latest` | Database username |
| `DATABASE_PASSWORD_SECRET` | secretKeyRef | `latest` | Database password |
| `MICRO_BATCH_THRESHOLD_USD` | secretKeyRef | `latest` | **Target for removal** |

---

## Current Secret Manager Configuration

### MICRO_BATCH_THRESHOLD_USD Secret
- **Secret Name**: `MICRO_BATCH_THRESHOLD_USD`
- **Current Value**: `2.00`
- **Full Path**: `projects/291176869049/secrets/MICRO_BATCH_THRESHOLD_USD`
- **Replication**: Automatic (multi-region)

---

## Service Account Permissions

### Current Service Account: `291176869049-compute@developer.gserviceaccount.com`

**Relevant Roles:**
- ✅ `roles/secretmanager.secretAccessor` - Can read Secret Manager secrets
- ✅ `roles/secretmanager.admin` - Full Secret Manager access
- ✅ `roles/cloudsql.client` - Can connect to Cloud SQL
- ✅ `roles/cloudtasks.admin` - Can create Cloud Tasks
- ✅ `roles/run.admin` - Can manage Cloud Run services

**Verdict**: Service account has ALL necessary permissions for dynamic Secret Manager access.

---

## Code Analysis: Current Threshold Access Pattern

### Current Implementation (config_manager.py lines 48-75)
```python
def get_micro_batch_threshold(self) -> Decimal:
    """
    Fetch micro-batch threshold from Google Cloud Secret Manager.
    
    Returns:
        Decimal threshold value (e.g., Decimal('20.00'))
    """
    try:
        # Try to get from env variable first (for Cloud Run deployment)
        threshold_str = os.getenv('MICRO_BATCH_THRESHOLD_USD')
        
        if not threshold_str:
            # Fallback to direct Secret Manager access
            project_id = os.getenv('CLOUD_TASKS_PROJECT_ID', 'telepay-459221')
            secret_name = f"projects/{project_id}/secrets/MICRO_BATCH_THRESHOLD_USD/versions/latest"
            
            print(f"🔐 [CONFIG] Fetching threshold from Secret Manager")
            response = self.client.access_secret_version(request={"name": secret_name})
            threshold_str = response.payload.data.decode('UTF-8')
        
        threshold = Decimal(threshold_str)
        print(f"✅ [CONFIG] Threshold fetched: ${threshold}")
        return threshold
        
    except Exception as e:
        print(f"❌ [CONFIG] Failed to fetch threshold: {e}")
        print(f"⚠️ [CONFIG] Using fallback threshold: $20.00")
        return Decimal('20.00')
```

**Key Insight**: The code ALREADY has a fallback to Secret Manager API if env var is not set!

---

## Deployment Strategy: Remove MICRO_BATCH_THRESHOLD_USD from --set-secrets

### Secrets to KEEP in --set-secrets (11 total)
```
SUCCESS_URL_SIGNING_KEY:latest
CLOUD_TASKS_PROJECT_ID:latest
CLOUD_TASKS_LOCATION:latest
GCHOSTPAY1_BATCH_QUEUE:latest
GCHOSTPAY1_URL:latest
CHANGENOW_API_KEY:latest
HOST_WALLET_USDT_ADDRESS:latest
CLOUD_SQL_CONNECTION_NAME:latest
DATABASE_NAME_SECRET:latest
DATABASE_USER_SECRET:latest
DATABASE_PASSWORD_SECRET:latest
```

### Secret to REMOVE from --set-secrets
```
MICRO_BATCH_THRESHOLD_USD:latest  ❌ Remove this
```

---

## Ready-to-Execute Deployment Command

```bash
gcloud run deploy gcmicrobatchprocessor-10-26 \
  --region=us-central1 \
  --image=gcr.io/telepay-459221/gcmicrobatchprocessor-10-26:latest \
  --service-account=291176869049-compute@developer.gserviceaccount.com \
  --memory=512Mi \
  --cpu=1 \
  --max-instances=10 \
  --timeout=3600 \
  --concurrency=80 \
  --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql \
  --set-secrets=SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,GCHOSTPAY1_BATCH_QUEUE=GCHOSTPAY1_BATCH_QUEUE:latest,GCHOSTPAY1_URL=GCHOSTPAY1_URL:latest,CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,HOST_WALLET_USDT_ADDRESS=HOST_WALLET_USDT_ADDRESS:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest \
  --allow-unauthenticated
```

---

## Post-Deployment Behavior

### What Happens After Deployment

1. **On Service Startup:**
   - `config_manager.py` initializes
   - `initialize_config()` loads all secrets from env vars (11 secrets)
   - `MICRO_BATCH_THRESHOLD_USD` env var will NOT exist

2. **When /check-threshold is Called:**
   - Line 101: `threshold = config_manager.get_micro_batch_threshold()`
   - Line 57: `os.getenv('MICRO_BATCH_THRESHOLD_USD')` returns `None`
   - Line 59-66: Code falls back to Secret Manager API
   - Line 62-66: Direct API call to `projects/telepay-459221/secrets/MICRO_BATCH_THRESHOLD_USD/versions/latest`
   - Line 68: Converts to `Decimal`
   - ✅ **Threshold is fetched fresh on EVERY request**

3. **Dynamic Updates:**
   - Admin updates secret: `gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=- <<< "5.00"`
   - Next `/check-threshold` call will use `$5.00` immediately
   - **No service restart required**

---

## Verification Checklist

After deployment, verify:

### 1. Service Health
```bash
curl https://gcmicrobatchprocessor-10-26-pjxwjsdktq-uc.a.run.app/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "GCMicroBatchProcessor-10-26",
  "timestamp": 1699999999
}
```

### 2. Check Logs for Dynamic Threshold Fetching
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcmicrobatchprocessor-10-26" --limit=50 --format=json
```

**Look for:**
```
🔐 [CONFIG] Fetching threshold from Secret Manager
✅ [CONFIG] Threshold fetched: $2.00
```

### 3. Test Dynamic Update

**Step 1: Update threshold to $5.00**
```bash
echo "5.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=-
```

**Step 2: Trigger threshold check (via Cloud Scheduler or manual)**
```bash
curl -X POST https://gcmicrobatchprocessor-10-26-pjxwjsdktq-uc.a.run.app/check-threshold \
  -H "Content-Type: application/json"
```

**Step 3: Check logs**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcmicrobatchprocessor-10-26 AND textPayload:threshold" --limit=10 --format=json
```

**Expected Log Output:**
```
🔐 [CONFIG] Fetching threshold from Secret Manager
✅ [CONFIG] Threshold fetched: $5.00
💰 [ENDPOINT] Current threshold: $5.00
```

---

## Risk Assessment

### Risks
1. **Increased API Calls**: Secret Manager API call on every `/check-threshold` invocation
   - **Mitigation**: Service is scheduled every 15 minutes (96 calls/day)
   - **Cost**: Negligible (<$0.01/month for 3,000 API calls free tier)

2. **Secret Manager API Failure**: If Secret Manager is down
   - **Mitigation**: Code has fallback to `$20.00` (line 75)
   - **Impact**: Service continues with hardcoded fallback

3. **Latency**: Additional ~50-100ms per request
   - **Mitigation**: Scheduled endpoint, not user-facing
   - **Impact**: Negligible

### Benefits
1. ✅ **Dynamic Updates**: Change threshold without redeployment
2. ✅ **No Downtime**: Instant updates on next scheduled run
3. ✅ **Centralized Management**: Single source of truth in Secret Manager
4. ✅ **Audit Trail**: Secret Manager logs all access and updates

---

## Implementation Status

### Current State: ✅ READY FOR DEPLOYMENT

**Why No Code Changes Needed:**
- Code ALREADY supports dynamic Secret Manager fetching (lines 59-66)
- Code ALREADY has fallback to `$20.00` on failure
- Only deployment configuration needs to change

**Deployment Action:**
- Remove `MICRO_BATCH_THRESHOLD_USD` from `--set-secrets` flag
- Keep all other secrets
- Redeploy with updated command

---

## Additional Considerations

### Optional: Add Caching for Secret Manager API

If you want to reduce Secret Manager API calls while maintaining some dynamism:

```python
# config_manager.py - Optional enhancement
def __init__(self):
    self.client = secretmanager.SecretManagerServiceClient()
    self._threshold_cache = None
    self._threshold_cache_time = 0
    self.CACHE_TTL = 300  # 5 minutes
    print(f"⚙️ [CONFIG] ConfigManager initialized")

def get_micro_batch_threshold(self) -> Decimal:
    """
    Fetch micro-batch threshold with 5-minute cache.
    """
    import time
    current_time = time.time()
    
    # Check cache first
    if self._threshold_cache and (current_time - self._threshold_cache_time) < self.CACHE_TTL:
        print(f"💾 [CONFIG] Using cached threshold: ${self._threshold_cache}")
        return self._threshold_cache
    
    try:
        # ... existing Secret Manager fetch logic ...
        threshold = Decimal(threshold_str)
        
        # Update cache
        self._threshold_cache = threshold
        self._threshold_cache_time = current_time
        
        print(f"✅ [CONFIG] Threshold fetched and cached: ${threshold}")
        return threshold
        
    except Exception as e:
        # ... existing error handling ...
```

**Trade-offs:**
- ✅ Reduces Secret Manager API calls by ~95%
- ✅ Still updates within 5 minutes of secret change
- ❌ Adds caching complexity
- ❌ Not immediate (5-minute delay)

**Recommendation**: NOT needed for now (only 96 calls/day is negligible cost)

---

## Conclusion

**GCMicroBatchProcessor-10-26 is FULLY READY for dynamic threshold switching.**

**Next Steps:**
1. Execute deployment command (remove MICRO_BATCH_THRESHOLD_USD from --set-secrets)
2. Verify health endpoint
3. Check logs for dynamic Secret Manager fetching
4. Test threshold update with `gcloud secrets versions add`

**Expected Outcome:**
- ✅ Service continues operating normally
- ✅ Threshold fetched from Secret Manager API on every check
- ✅ Admin can update threshold anytime without redeployment
- ✅ Changes take effect on next scheduled run (15 minutes max)

