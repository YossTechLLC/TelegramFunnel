# Config Manager Systematic Fix - Environment Variable Pattern

## Problem Overview

**Root Cause**: Multiple services are using an OUTDATED Secret Manager API pattern that tries to call `access_secret_version()` API. This pattern expects environment variables to contain SECRET PATHS (e.g., `projects/123/secrets/foo/versions/latest`), but Cloud Run's `--set-secrets` flag injects the actual SECRET VALUES directly into environment variables.

**Result**: Services fail to load configuration and show `❌ [CONFIG] Environment variable XXX is not set` errors.

## Pattern Comparison

### ❌ WRONG Pattern (Old Secret Manager API):
```python
def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
    try:
        secret_path = os.getenv(secret_name_env)  # Expects SECRET PATH
        if not secret_path:
            return None

        # ❌ Makes API call to Secret Manager
        response = self.client.access_secret_version(request={"name": secret_path})
        secret_value = response.payload.data.decode("UTF-8")
        return secret_value
    except Exception as e:
        print(f"❌ [CONFIG] Error fetching {description}: {e}")
        return None
```

### ✅ CORRECT Pattern (Direct Environment Variable Read):
```python
def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
    """
    Fetch a secret value from environment variable.
    Cloud Run automatically injects secret values when using --set-secrets.
    """
    try:
        secret_value = os.getenv(secret_name_env)  # Directly reads SECRET VALUE
        if not secret_value:
            print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set")
            return None

        print(f"✅ [CONFIG] Successfully loaded {description or secret_name_env}")
        return secret_value
    except Exception as e:
        print(f"❌ [CONFIG] Error loading {description or secret_name_env}: {e}")
        return None
```

## Services Status

### ✅ Services Already Fixed:
1. **GCWebhook1-10-26** - Fixed in current session, deploying now
2. **GCAccumulator-10-26** - Fixed earlier, already deployed
3. **GCBatchProcessor-10-26** - Fixed earlier, already deployed

### ❌ Services Requiring Fix:
1. **GCWebhook2-10-26** - Uses access_secret_version() ❌
2. **GCSplit1-10-26** - Uses access_secret_version() ❌
3. **GCSplit2-10-26** - Uses access_secret_version() ❌
4. **GCSplit3-10-26** - Uses access_secret_version() ❌
5. **GCHostPay1-10-26** - Uses access_secret_version() ❌
6. **GCHostPay2-10-26** - Uses access_secret_version() ❌
7. **GCHostPay3-10-26** - Uses access_secret_version() ❌

## Impact Assessment

### Current State:
- **7 services are deployed with broken config loading**
- They may appear to work IF they don't require secrets at runtime
- They WILL fail when trying to access any secret value
- Logs will show `❌ [CONFIG] Environment variable XXX is not set`

### Risk Level by Service:

#### HIGH PRIORITY (Used in payment flow):
- **GCWebhook2-10-26**: Handles ChangeNOW confirmation webhooks - CRITICAL
- **GCSplit1-10-26**: Processes instant payouts - CRITICAL
- **GCSplit2-10-26**: Handles ChangeNOW API for split - CRITICAL
- **GCSplit3-10-26**: Completes split payout - CRITICAL

#### MEDIUM PRIORITY (Used in threshold flow):
- **GCHostPay1-10-26**: Creates HostPay wallets - IMPORTANT
- **GCHostPay2-10-26**: Handles ChangeNOW for host pay - IMPORTANT
- **GCHostPay3-10-26**: Completes host pay - IMPORTANT

## Fix Strategy

### Approach:
1. Update `fetch_secret()` method in each service's config_manager.py
2. Remove `access_secret_version()` API call
3. Change to direct `os.getenv()` read
4. Update docstrings to reflect Cloud Run secret injection
5. Rebuild and redeploy each service

### Order of Execution:
1. **Phase 1**: Fix GCWebhook2 + GCSplit services (HIGH priority - payment flow)
2. **Phase 2**: Fix GCHostPay services (MEDIUM priority - threshold flow)

## Files to Modify

### GCWebhook2-10-26:
- File: `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook2-10-26/config_manager.py`
- Method: `fetch_secret()` at line ~21

### GCSplit1-10-26:
- File: `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit1-10-26/config_manager.py`
- Method: `fetch_secret()` at line ~21

### GCSplit2-10-26:
- File: `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit2-10-26/config_manager.py`
- Method: `fetch_secret()` at line ~21

### GCSplit3-10-26:
- File: `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit3-10-26/config_manager.py`
- Method: `fetch_secret()` at line ~21

### GCHostPay1-10-26:
- File: `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay1-10-26/config_manager.py`
- Method: `fetch_secret()` at line ~21

### GCHostPay2-10-26:
- File: `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay2-10-26/config_manager.py`
- Method: `fetch_secret()` at line ~21

### GCHostPay3-10-26:
- File: `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay3-10-26/config_manager.py`
- Method: `fetch_secret()` at line ~21

## Standard Fix Template

Replace existing `fetch_secret()` method with:

```python
def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
    """
    Fetch a secret value from environment variable.
    Cloud Run automatically injects secret values when using --set-secrets.

    Args:
        secret_name_env: Environment variable name containing the secret value
        description: Description for logging purposes

    Returns:
        Secret value or None if failed
    """
    try:
        secret_value = os.getenv(secret_name_env)
        if not secret_value:
            print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set")
            return None

        print(f"✅ [CONFIG] Successfully loaded {description or secret_name_env}")
        return secret_value

    except Exception as e:
        print(f"❌ [CONFIG] Error loading {description or secret_name_env}: {e}")
        return None
```

## Testing After Fix

### Verification Steps:
1. Check service startup logs for configuration loading
2. Verify all environment variables show ✅ instead of ❌
3. Test actual functionality (process a payment for payment services)

### Log Verification Command:
```bash
# Check service config loading
gcloud logging read "resource.labels.service_name={SERVICE_NAME} AND timestamp>='{TIMESTAMP}' AND textPayload:'CONFIG'" --limit=50
```

## Expected Timeline

- **Per Service**: ~5-10 minutes (edit + build + deploy)
- **Phase 1 (4 services)**: ~30-40 minutes
- **Phase 2 (3 services)**: ~20-30 minutes
- **Total**: ~60-70 minutes for all fixes

## Rollback Plan

If any service has issues after fix:
1. Previous revision still available in Cloud Run
2. Can rollback via: `gcloud run services update-traffic {SERVICE} --to-revisions={OLD_REVISION}=100`
3. Re-analyze logs for specific error
4. Apply corrected fix

---
**Document Created**: October 29, 2025
**Issue**: Environment variable configuration pattern inconsistency
**Priority**: HIGH (blocks threshold payout + may impact instant payout)
