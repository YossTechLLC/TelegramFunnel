# Bug Tracker - TelegramFunnel NOVEMBER/PGP_v1

**Last Updated:** 2025-11-14 Session 157

---

## Recently Resolved

## 2025-11-14 Session 157: ✅ RESOLVED - Flask JSON Parsing Errors (415 & 400)

**Severity:** 🔴 CRITICAL - Production service errors blocking Cloud Scheduler
**Status:** ✅ RESOLVED (Deployed in pgp_broadcastscheduler-10-26-00020-j6n)
**Service:** PGP_BROADCAST_v1
**Endpoint:** `POST /api/broadcast/execute`

**Error 1: 415 Unsupported Media Type**
```
2025-11-14 23:46:36,016 - main - ERROR - ❌ Error executing broadcasts: 415 Unsupported Media Type: Did not attempt to load JSON data because the request Content-Type was not 'application/json'.

Traceback (most recent call last):
  File "/app/pgp_broadcast_v1.py", line 143, in execute_broadcasts
    data = request.get_json() or {}
  File "/usr/local/lib/python3.11/site-packages/werkzeug/wrappers/request.py", line 604, in get_json
    return self.on_json_loading_failed(None)
  File "/usr/local/lib/python3.11/site-packages/flask/wrappers.py", line 130, in on_json_loading_failed
    return super().on_json_loading_failed(e)
  File "/usr/local/lib/python3.11/site-packages/werkzeug/wrappers/request.py", line 647, in on_json_loading_failed
    raise UnsupportedMediaType(
werkzeug.exceptions.UnsupportedMediaType: 415 Unsupported Media Type
```

**Error 2: 400 Bad Request - JSON Decode Error**
```
2025-11-14 23:46:40,515 - main - ERROR - ❌ Error executing broadcasts: 400 Bad Request: The browser (or proxy) sent a request that this server could not understand.

Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/werkzeug/wrappers/request.py", line 611, in get_json
    rv = self.json_module.loads(data)
  File "/usr/local/lib/python3.11/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
  File "/usr/local/lib/python3.11/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
  File "/usr/local/lib/python3.11/json/decoder.py", line 355, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Root Cause:**
- Flask's default `request.get_json()` raises exceptions instead of returning `None`
- **Error 1 Trigger**: Missing or incorrect `Content-Type` header (manual tests, proxy issues)
- **Error 2 Trigger**: Empty request body or malformed JSON with correct `Content-Type` header
- Cloud Scheduler was configured correctly, but endpoint couldn't handle edge cases

**Affected Code:**
- File: `PGP_BROADCAST_v1/pgp_broadcast_v1.py`
- Location: Line 143 in `execute_broadcasts()` function

**Before (Problematic):**
```python
try:
    # Get optional source from request body
    data = request.get_json() or {}  # ❌ Raises exceptions
    source = data.get('source', 'unknown')
```

**After (Fixed):**
```python
try:
    # Get optional source from request body
    # Use force=True to handle Content-Type issues (proxies/gateways)
    # Use silent=True to return None instead of raising exceptions on parse errors
    data = request.get_json(force=True, silent=True) or {}  # ✅ Returns None on errors
    source = data.get('source', 'unknown')

    logger.info(f"🎯 Broadcast execution triggered by: {source}")
    logger.debug(f"📦 Request data: {data}")
```

**Fix Explanation:**
1. `force=True`: Parse JSON regardless of Content-Type header
   - Solves Error 1 (415 Unsupported Media Type)
   - Handles missing/incorrect Content-Type headers gracefully

2. `silent=True`: Return `None` instead of raising exceptions on parse errors
   - Solves Error 2 (400 Bad Request)
   - Handles empty body and malformed JSON gracefully

3. `or {}`: Fallback to empty dictionary for safe access
   - Ensures `data.get('source', 'unknown')` never fails

**Testing Performed:**
1. ✅ **Test 1**: Request without Content-Type header
   - Before: 415 Unsupported Media Type ❌
   - After: HTTP 200 ✅

2. ✅ **Test 2**: Request with Content-Type but empty body
   - Before: 400 Bad Request ❌
   - After: HTTP 200 ✅

3. ✅ **Test 3**: Request with proper JSON payload
   - Before: HTTP 200 ✅
   - After: HTTP 200 ✅

4. ✅ **Test 4**: Cloud Scheduler manual trigger
   - Before: Intermittent failures ❌
   - After: HTTP 200 with "cloud_scheduler" source logged ✅

**Verification Logs:**
```
2025-11-14 23:56:39,000 - main - INFO - 🎯 Broadcast execution triggered by: cloud_scheduler
2025-11-14 23:56:39,000 - main - INFO - 📋 Fetching due broadcasts...
2025-11-14 23:56:39,060 - main - INFO - ✅ No broadcasts due at this time
2025-11-14 23:56:39,060 - main - INFO - 📮 POST /api/broadcast/execute -> 200
```

**Impact:**
- ✅ Cloud Scheduler executing successfully every 5 minutes
- ✅ Manual API testing now works regardless of headers
- ✅ Production errors eliminated
- ✅ Endpoint robust to proxy/gateway header modifications

**Prevention for Future:**
- Apply `request.get_json(force=True, silent=True)` pattern to ALL API endpoints
- Document pattern in DECISIONS.md for team reference
- Review other services: PGP_NOTIFICATIONS, GCHostPay, TelePay webhooks

**Related Documentation:**
- ✅ `DECISIONS.md`: Added Flask JSON handling best practice decision
- ✅ `PROGRESS.md`: Added implementation details and testing results
- ✅ Flask Documentation: Verified pattern via Context7 MCP research

---

## 2025-11-14 Session 156: ✅ RESOLVED - Missing Environment Variables (3 Total)

**Severity:** 🟡 HIGH - Service initialization errors and warnings
**Status:** ✅ RESOLVED (Deployed in pgp_broadcastscheduler-10-26-00019-nzk)
**Service:** PGP_BROADCAST_v1
**Errors:**
1. `Environment variable BOT_USERNAME_SECRET not set and no default provided`
2. `Environment variable BROADCAST_MANUAL_INTERVAL_SECRET not set, using default`
3. `Environment variable BROADCAST_AUTO_INTERVAL_SECRET not set, using default`

**Symptom:**
```
config_manager - ERROR - ❌ Error fetching secret BOT_USERNAME_SECRET: Environment variable BOT_USERNAME_SECRET not set
config_manager - WARNING - ⚠️ Environment variable BROADCAST_MANUAL_INTERVAL_SECRET not set, using default
config_manager - WARNING - ⚠️ Environment variable BROADCAST_AUTO_INTERVAL_SECRET not set, using default
```

**Root Cause:**
- Incomplete review of `config_manager.py` - only identified 8 of 10 required environment variables
- `BOT_USERNAME_SECRET` was missing entirely (initially pointed to wrong secret: `BOT_USERNAME` instead of `TELEGRAM_BOT_USERNAME`)
- `BROADCAST_AUTO_INTERVAL_SECRET` and `BROADCAST_MANUAL_INTERVAL_SECRET` were not included in deployment

**Fix Applied:**
```bash
# Missing variables (3):
BOT_USERNAME_SECRET=projects/telepay-459221/secrets/TELEGRAM_BOT_USERNAME/versions/latest
BROADCAST_AUTO_INTERVAL_SECRET=projects/telepay-459221/secrets/BROADCAST_AUTO_INTERVAL/versions/latest
BROADCAST_MANUAL_INTERVAL_SECRET=projects/telepay-459221/secrets/BROADCAST_MANUAL_INTERVAL/versions/latest
```

**Solution:**
1. ✅ Read ENTIRE `config_manager.py` file to identify ALL 10 environment variable calls
2. ✅ Referenced `SECRET_CONFIG.md` for correct secret name mappings
3. ✅ Deployed service with complete set of 10 environment variables
4. ✅ Verified no errors or warnings in logs

**Verification:**
```
2025-11-14 23:46:02 - config_manager - INFO - 🤖 Bot username: @PayGatePrime_bot
2025-11-14 23:46:02 - telegram_client - INFO - 🤖 TelegramClient initialized for @PayGatePrime_bot
2025-11-14 23:46:02 - main - INFO - ✅ All components initialized successfully
```
(No warnings about BROADCAST intervals)

**Documentation Updated:**
- ✅ `DECISIONS.md`: Added complete 10-variable secret mapping reference table
- ✅ `CON_CURSOR_CLEANUP_PROGRESS.md`: Updated deployment section with all 10 variables
- ✅ `PROGRESS.md`: Updated with complete environment variable fix details

---

## 2025-11-14 Session 156: ✅ RESOLVED - PGP_BROADCAST Cursor Context Manager Error

**Severity:** 🔴 CRITICAL - Production service error
**Status:** ✅ RESOLVED (Deployed in pgp_broadcastscheduler-10-26-00018-fgq)
**Service:** PGP_BROADCAST_v1
**Error:** `'Cursor' object does not support the context manager protocol`

**Symptom:**
```
2025-11-14 23:10:06,862 - database_manager - ERROR - ❌ Database error: 'Cursor' object does not support the context manager protocol
2025-11-14 23:10:06,862 - broadcast_tracker - ERROR - ❌ Failed to update message IDs: 'Cursor' object does not support the context manager protocol
```

**Root Cause:**
- pg8000 database driver cursors do NOT support the `with` statement (context manager protocol)
- Code attempted: `with conn.cursor() as cur:` which is invalid for pg8000
- Error occurred in `broadcast_tracker.py` line 199 when calling `update_message_ids()`
- This pattern existed in 11 methods across 2 files

**Affected Methods:**
1. `database_manager.py`:
   - `fetch_due_broadcasts()`
   - `fetch_broadcast_by_id()`
   - `update_broadcast_status()`
   - `update_broadcast_success()`
   - `update_broadcast_failure()`
   - `get_manual_trigger_info()`
   - `queue_manual_broadcast()`
   - `get_broadcast_statistics()`

2. `broadcast_tracker.py`:
   - `reset_consecutive_failures()`
   - `update_message_ids()` **[PRIMARY ERROR SOURCE]**

**Fix Applied:**
Migrated all methods to NEW_ARCHITECTURE SQLAlchemy `text()` pattern:

**Before (Problematic):**
```python
with self.db.get_connection() as conn:
    with conn.cursor() as cur:  # ❌ pg8000 cursors don't support this
        cur.execute("SELECT ... WHERE id = %s", (id,))
        result = cur.fetchone()
```

**After (Fixed):**
```python
engine = self.db._get_engine()
with engine.connect() as conn:
    query = text("SELECT ... WHERE id = :id")  # ✅ Named parameters
    result = conn.execute(query, {"id": id})
    row = result.fetchone()
    # SQLAlchemy handles cursor lifecycle automatically
```

**Benefits of Fix:**
1. ✅ Error eliminated - no more cursor context manager issues
2. ✅ Automatic resource management by SQLAlchemy
3. ✅ Better SQL injection protection (named parameters)
4. ✅ Consistent with NEW_ARCHITECTURE pattern
5. ✅ Future ORM migration path available
6. ✅ Better error messages from SQLAlchemy

**Testing:**
- ✅ Deployed to Cloud Run successfully
- ✅ Service health checks passing
- ✅ Broadcast execution working correctly
- ✅ No cursor errors in logs
- ✅ Message tracking functional
- ✅ Database operations healthy

**Deployment:**
- Build: `gcr.io/telepay-459221/pgp_broadcastscheduler-10-26:latest`
- Revision: `pgp_broadcastscheduler-10-26-00013-snr`
- Deployment time: 2025-11-14 23:25:37 UTC
- Status: LIVE and OPERATIONAL

**Documentation:**
- ✅ CON_CURSOR_CLEANUP_PROGRESS.md created
- ✅ PROGRESS.md updated
- ✅ DECISIONS.md updated
- ✅ BUGS.md updated

**Lesson Learned:**
pg8000 cursors require explicit `.close()` or automatic management through SQLAlchemy. Never use `with conn.cursor() as cur:` with pg8000. Always prefer SQLAlchemy `text()` pattern for consistency and safety.

---

## 2025-11-14 Session 155: ✅ RESOLVED - Missing broadcast_manager Entries for New Users

**Severity:** 🔴 CRITICAL
**Status:** ✅ RESOLVED (Deployed in gcregisterapi-10-26-00028-khd)
**Reported By:** User UUID 7e1018e4-5644-4031-a05c-4166cc877264
**Affected Users:** All newly registered users after 2025-10-26

**Symptom:**
User sees "Not Configured" button instead of "Resend Notification" after registering channel and restarting broadcast manager.

**Root Cause:**
Channel registration flow only created `main_clients_database` entry. NO `broadcast_manager` entry created. `populate_broadcast_manager.py` was one-time migration, not automated.

**Fix:**
1. Created `BroadcastService` module (`api/services/broadcast_pgp_notifications_v1.py`)
2. Integrated into channel registration with transactional safety
3. Backfill script executed: 1 entry created for target user (broadcast_id=613acae7-a8a4-4d15-a046-4d6a1b6add49)
4. Database integrity verification SQL created

**Prevention:**
- New registrations auto-create broadcast_manager entries
- Verification queries available for monitoring

---

### ✅ [FIXED] Incorrect Context Manager Pattern Causing "_ConnectionFairy' object does not support the context manager protocol" Error

**Date Discovered:** 2025-11-14 Session 154
**Date Resolved:** 2025-11-14 Session 154
**Files:** `PGP_SERVER_v1/database.py`, `PGP_SERVER_v1/subscription_manager.py`
**Severity:** 🔴 CRITICAL - Database queries failing on startup
**Resolution Time:** Same session (30 minutes)

**Issue:**
Multiple methods in `database.py` and `subscription_manager.py` used an incorrect nested context manager pattern that caused database operations to fail. The pattern `with self.get_connection() as conn, conn.cursor() as cur:` failed because `conn.cursor()` does not return a context-manager-compatible object when using SQLAlchemy's `_ConnectionFairy` wrapper.

Error message:
```
❌ db open_channel error: '_ConnectionFairy' object does not support the context manager protocol
```

**User Impact:**
- 🔴 Open channel list fetching failed on startup (subscription system broken)
- 🔴 Closed channel operations failed (donation flow broken)
- 🔴 Channel configuration queries failed (management dashboard broken)
- 🔴 Subscription expiration monitoring failed (users not removed when expired)
- 🔴 Database updates failed (channel configs couldn't be saved)

**Affected Methods (8 total):**

**database.py (6 methods):**
1. `fetch_open_channel_list()` - Line 209
2. `get_default_donation_channel()` - Line 305
3. `fetch_channel_by_id()` - Line 537
4. `update_channel_config()` - Line 590
5. `fetch_expired_subscriptions()` - Line 650
6. `deactivate_subscription()` - Line 708

**subscription_manager.py (2 methods):**
7. `fetch_expired_subscriptions()` - Line 96
8. `deactivate_subscription()` - Line 197

**Root Cause:**
The incorrect pattern attempted to use nested context managers:
```python
# ❌ BROKEN - conn.cursor() not a context manager
with self.get_connection() as conn, conn.cursor() as cur:
    cur.execute("SELECT ...")
```

The `get_connection()` method (database.py:147) returns `self.pool.engine.raw_connection()`, which is a SQLAlchemy `_ConnectionFairy` object. While `_ConnectionFairy` supports the context manager protocol, calling `.cursor()` on it returns a raw psycopg2 cursor that does **NOT** support nested context manager syntax.

**Fix Applied:**
Replaced all 8 occurrences with SQLAlchemy's recommended pattern using `text()`:

```python
# ✅ FIXED - Use SQLAlchemy engine connection with text()
from sqlalchemy import text

with self.pool.engine.connect() as conn:
    result = conn.execute(text("SELECT ..."))
    rows = result.fetchall()
    # For UPDATE/INSERT/DELETE:
    conn.commit()
```

**Key Changes:**
- SELECT queries: Use `conn.execute(text(query))` and `result.fetchall()`
- Parameterized queries: Changed from `%s` placeholders to `:param_name` with dict parameters
- UPDATE queries: Added `conn.commit()` after execution
- Consistent error handling maintained
- All return values unchanged (backward compatible)

**Files Modified:**
- `PGP_SERVER_v1/database.py` - 6 methods fixed
- `PGP_SERVER_v1/subscription_manager.py` - 2 methods fixed

**Expected Behavior After Fix:**
- ✅ Open channel list fetches successfully on startup
- ✅ Closed channel donation messages send correctly
- ✅ Channel configurations can be queried and updated
- ✅ Expired subscriptions detected and processed
- ✅ Database operations use proper connection pooling

**Lessons Learned:**
1. **Follow NEW_ARCHITECTURE patterns:** Always use `pool.engine.connect()` with SQLAlchemy `text()` for consistency
2. **Avoid raw connection patterns:** The `get_connection()` method is deprecated for good reason
3. **Test context manager compatibility:** Not all objects support nested context managers
4. **Search thoroughly:** Found 8 instances across 2 files, not just the initial 6

**Related Issue:**
This complements the Session 153 fix for `CLOUD_SQL_CONNECTION_NAME` - both were blocking database connectivity on startup.

---

### ✅ [FIXED] CLOUD_SQL_CONNECTION_NAME Secret Manager Path Not Fetched

**Date Discovered:** 2025-11-14 Session 153
**Date Resolved:** 2025-11-14 Session 153
**File:** `PGP_SERVER_v1/database.py`
**Severity:** 🔴 CRITICAL - All database operations failing on startup
**Resolution Time:** Same session (15 minutes)

**Issue:**
Application failed to connect to Cloud SQL database on startup. All database operations failed with error:
```
Arg `instance_connection_string` must have format: PROJECT:REGION:INSTANCE,
got projects/291176869049/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest
```

**User Impact:**
- 🔴 Subscription monitoring failed to fetch expired subscriptions
- 🔴 Open channel queries failed during startup
- 🔴 Payment gateway database access failed
- 🔴 Donation flow database queries failed
- 🔴 COMPLETE DATABASE FAILURE - Application non-functional

**Root Cause:**
The `CLOUD_SQL_CONNECTION_NAME` environment variable contained a Secret Manager path instead of the actual connection string value. Unlike other database secrets (DATABASE_HOST_SECRET, DATABASE_NAME_SECRET, etc.) which were correctly fetched using Secret Manager helper functions, `CLOUD_SQL_CONNECTION_NAME` was read directly via `os.getenv()` without fetching the secret value.

**Code Flow (BEFORE FIX):**
```python
# database.py:118 - Direct os.getenv() call
self.pool = init_connection_pool({
    'instance_connection_name': os.getenv('CLOUD_SQL_CONNECTION_NAME', 'telepay-459221:us-central1:telepaypsql'),
    # ❌ Gets: projects/291176869049/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest
    # ✅ Expected: telepay-459221:us-central1:telepaypsql
})
```

**Fix Applied:**
Added `fetch_cloud_sql_connection_name()` function following existing Secret Manager pattern:

```python
def fetch_cloud_sql_connection_name() -> str:
    """Fetch Cloud SQL connection name from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("CLOUD_SQL_CONNECTION_NAME")
        if not secret_path:
            print("⚠️ CLOUD_SQL_CONNECTION_NAME not set, using default")
            return "telepay-459221:us-central1:telepaypsql"

        # Check if already in correct format (PROJECT:REGION:INSTANCE)
        if ':' in secret_path and not secret_path.startswith('projects/'):
            return secret_path

        # Fetch from Secret Manager
        response = client.access_secret_version(request={"name": secret_path})
        connection_name = response.payload.data.decode("UTF-8").strip()
        print(f"✅ Fetched Cloud SQL connection name from Secret Manager: {connection_name}")
        return connection_name
    except Exception as e:
        print(f"❌ Error fetching CLOUD_SQL_CONNECTION_NAME: {e}")
        return "telepay-459221:us-central1:telepaypsql"

# Module-level initialization
DB_CLOUD_SQL_CONNECTION_NAME = fetch_cloud_sql_connection_name()
```

Updated DatabaseManager to use fetched value:
```python
self.pool = init_connection_pool({
    'instance_connection_name': DB_CLOUD_SQL_CONNECTION_NAME,  # ✅ Now uses fetched value
    ...
})
```

**Files Changed:**
- `PGP_SERVER_v1/database.py:64-87` - Added fetch_cloud_sql_connection_name() function
- `PGP_SERVER_v1/database.py:95` - Added DB_CLOUD_SQL_CONNECTION_NAME module variable
- `PGP_SERVER_v1/database.py:119` - Updated init_connection_pool() to use fetched value

**Expected Behavior After Fix:**
- ✅ Cloud SQL connection string properly fetched from Secret Manager
- ✅ Connection pool initialized with correct format: `telepay-459221:us-central1:telepaypsql`
- ✅ All database operations functional
- ✅ Subscription monitoring works
- ✅ Payment gateway database access restored

**Verification Status:**
- ⏳ Awaiting application restart to verify fix

**Lessons Learned:**
1. **Consistent Pattern Enforcement:** ALL Secret Manager secrets must use fetch functions, not direct `os.getenv()`
2. **Environment Variable Naming:** Secret paths should end with `_SECRET` to indicate Secret Manager usage
3. **Connection String Format:** Cloud SQL Connector requires `PROJECT:REGION:INSTANCE` format, not secret paths
4. **Testing:** Need comprehensive checks for similar issues across codebase

**Related Issues:**
- Searching codebase for similar Secret Manager path issues (in progress)

---

### ✅ [FIXED] Payment Button Confirmation Dialog - URL Buttons in Groups Show "Open this link?"

**Date Discovered:** 2025-11-13 Session 142.5
**Date Resolved:** 2025-11-13 Session 143
**File:** `GCDonationHandler-10-26/keypad_handler.py`
**Severity:** 🟡 MEDIUM - UX friction in payment flow, not blocking but suboptimal
**Resolution Time:** Same session (30 minutes)

**Issue:**
After fixing the `Button_type_invalid` error, payment buttons worked but showed Telegram's security confirmation dialog: "Open this link? https://nowpayments.io/payment/?iid=..." Users had to click "Open" before payment gateway appeared, adding friction to donation flow.

**User Impact:**
- ⚠️ Extra click required to open payment gateway
- ⚠️ Reduced user confidence (confirmation dialog looks suspicious)
