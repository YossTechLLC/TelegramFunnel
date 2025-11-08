# Database Credentials Fix Checklist

## Problem Identification

**Issue**: GCHostPay1 and GCHostPay3 services are failing to load database credentials, showing:
```
❌ [DATABASE] Missing required database credentials
Database Name: ❌
Database User: ❌
Database Password: ❌
Cloud SQL Connection Name: ❌
```

**Root Cause**:
- The `database_manager.py` in GCHostPay1 and GCHostPay3 has its own `_fetch_secret()` method that attempts to call Secret Manager API directly
- It expects environment variables to contain **paths** to secrets (e.g., `projects/123/secrets/name/versions/latest`)
- However, Cloud Run services are deployed with `--set-secrets`, which automatically injects secret **values** into environment variables
- The `config_manager.py` correctly uses `os.getenv()` to fetch values directly
- But `database_manager.py` tries to use the environment variable value as a **path** to fetch from Secret Manager again, which fails

## Services Affected

### ✅ Confirmed Issues:
1. **GCHostPay1-10-26** - Has broken `database_manager.py` with `_fetch_secret()` method
2. **GCHostPay3-10-26** - Has broken `database_manager.py` with `_fetch_secret()` method

### ✅ Already Correct (use constructor parameters):
1. **GCHostPay2-10-26** - No database access needed (stateless)
2. **GCAccumulator-10-26** - Receives credentials via constructor
3. **GCBatchProcessor-10-26** - Receives credentials via constructor
4. **GCSplit1-10-26** - Receives credentials via constructor
5. **GCWebhook1-10-26** - Receives credentials via constructor

## Solution Design

### Architectural Decision:
- **Standardize on constructor-based credential injection** across all services
- Remove duplicate `_fetch_secret()` logic from `database_manager.py`
- Let `config_manager.py` be the single source of truth for loading secrets
- Pass credentials to `DatabaseManager` via constructor

### Benefits:
1. **Single Responsibility**: ConfigManager handles secrets, DatabaseManager handles database operations
2. **Consistency**: All services follow the same pattern
3. **Testability**: Easier to mock and test with injected credentials
4. **DRY**: No duplicate secret-fetching logic

## Fix Implementation Steps

### Step 1: Fix GCHostPay1-10-26/database_manager.py
- [ ] Remove `_fetch_secret()` method
- [ ] Remove `_initialize_credentials()` method
- [ ] Modify `__init__()` to accept credentials as parameters
- [ ] Update instantiation in main service file to pass credentials from config

### Step 2: Fix GCHostPay3-10-26/database_manager.py
- [ ] Remove `_fetch_secret()` method
- [ ] Remove `_initialize_credentials()` method
- [ ] Modify `__init__()` to accept credentials as parameters
- [ ] Update instantiation in main service file to pass credentials from config

### Step 3: Verify No Other Services Have This Issue
- [x] GCHostPay2-10-26 - No database manager
- [x] GCAccumulator-10-26 - Already correct
- [x] GCBatchProcessor-10-26 - Already correct
- [x] GCSplit1-10-26 - Already correct (need to verify)
- [x] GCSplit2-10-26 - Need to check
- [x] GCSplit3-10-26 - Need to check
- [x] GCWebhook1-10-26 - Already correct
- [x] GCWebhook2-10-26 - Need to check

### Step 4: Deploy Fixed Services
- [ ] Build and deploy GCHostPay1-10-26
- [ ] Build and deploy GCHostPay3-10-26

### Step 5: Verification
- [ ] Check GCHostPay1-10-26 logs for successful credential loading
- [ ] Check GCHostPay3-10-26 logs for successful credential loading
- [ ] Verify database connections work properly
- [ ] Test end-to-end payment flow

## Expected Log Output (After Fix)

```
⚙️ [CONFIG] ConfigManager initialized
⚙️ [CONFIG] Initializing GCHostPay1-10-26 configuration
✅ [CONFIG] Successfully loaded TPS HostPay signing key
✅ [CONFIG] Successfully loaded Success URL signing key
✅ [CONFIG] Successfully loaded Cloud Tasks project ID
✅ [CONFIG] Successfully loaded Cloud Tasks location/region
✅ [CONFIG] Successfully loaded GCHostPay2 queue name
✅ [CONFIG] Successfully loaded GCHostPay2 service URL
✅ [CONFIG] Successfully loaded GCHostPay3 queue name
✅ [CONFIG] Successfully loaded GCHostPay3 service URL
✅ [CONFIG] Successfully loaded Cloud SQL instance connection name
✅ [CONFIG] Successfully loaded Database name
✅ [CONFIG] Successfully loaded Database user
✅ [CONFIG] Successfully loaded Database password
📊 [CONFIG] Configuration status:
   TPS_HOSTPAY_SIGNING_KEY: ✅
   SUCCESS_URL_SIGNING_KEY: ✅
   Cloud Tasks Project: ✅
   Cloud Tasks Location: ✅
   GCHostPay2 Queue: ✅
   GCHostPay2 URL: ✅
   GCHostPay3 Queue: ✅
   GCHostPay3 URL: ✅
   CLOUD_SQL_CONNECTION_NAME: ✅
   DATABASE_NAME_SECRET: ✅
   DATABASE_USER_SECRET: ✅
   DATABASE_PASSWORD_SECRET: ✅
🗄️ [DATABASE] DatabaseManager initialized
📊 [DATABASE] Instance: telepay-459221:us-central1:telepaypsql
📊 [DATABASE] Database: telepaypsql
```

## Documentation Updates

- [ ] Update PROGRESS.md with fix details
- [ ] Add bug report to BUGS.md
- [ ] Document architectural decision in DECISIONS.md
