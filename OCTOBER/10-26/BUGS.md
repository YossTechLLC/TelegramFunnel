# Bug Tracker - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-13 Session 141

---

## Recently Resolved

### ✅ [FIXED] Donation Flow Database Connection Timeout - GCDonationHandler Missing Cloud SQL Socket

**Date Discovered:** 2025-11-13 Session 141
**Date Resolved:** 2025-11-13 Session 141
**File:** `GCDonationHandler-10-26/database_manager.py`
**Severity:** 🔴 CRITICAL - Blocks ALL donation functionality
**Resolution Time:** Same session (30 minutes)

**Issue:**
After deploying Session 140's callback routing fix, users clicking "💝 Donate" button received error: "❌ Failed to start donation flow. Please try again or contact support." after 60 second wait. ALL donation attempts failed.

**User Impact:**
- ❌ 100% donation failure rate
- ⏱️ 60 second timeout on every attempt
- ❌ Zero donation revenue possible
- 😞 Poor user experience (long wait → generic error)

**Root Cause:**
GCDonationHandler was using raw TCP connection to Cloud SQL instead of Unix socket. Cloud Run's security sandbox blocks direct TCP connections to external IPs, causing all database queries to timeout after 60 seconds.

**Database Connection Attempted:**
```python
# BROKEN: Direct TCP connection
psycopg2.connect(
    host="34.58.246.248",  # ❌ Public IP blocked from Cloud Run
    port=5432,
    dbname="telepaydb",
    user="postgres",
    password="***"
)
```

**Logs Evidence:**
```
2025-11-13 20:34:36 - ❌ Database connection error: connection to server at "34.58.246.248", port 5432 failed: Connection timed out
2025-11-13 20:34:36 - ❌ Error checking channel existence: Connection timed out
2025-11-13 20:34:36 - ⚠️ Invalid channel ID (misleading - actual cause: database timeout)
HTTP 504 Gateway Timeout (latency: 60.000665692s)
```

**Fix Applied:**
**Location:** `GCDonationHandler-10-26/database_manager.py`

**Changes:**
1. Added `import os` (line 11)
2. Modified `__init__()` to detect Cloud SQL connection mode (lines 55-67):
   ```python
   # Check if running in Cloud Run (use Unix socket) or locally (use TCP)
   cloud_sql_connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME")

   if cloud_sql_connection_name:
       # Cloud Run mode - use Unix socket
       self.db_host = f"/cloudsql/{cloud_sql_connection_name}"
       self.db_port = None
       logger.info(f"🔌 Using Cloud SQL Unix socket: {self.db_host}")
   else:
       # Local/VM mode - use TCP connection
       self.db_host = db_host
       self.db_port = db_port
       logger.info(f"🔌 Using TCP connection to: {self.db_host}:{self.db_port}")
   ```

3. Updated `_get_connection()` to handle Unix socket (lines 88-105):
   ```python
   # Build connection parameters
   conn_params = {
       "host": self.db_host,
       "dbname": self.db_name,
       "user": self.db_user,
       "password": self.db_password
   }

   # Only include port for TCP connections (not Unix socket)
   if self.db_port is not None:
       conn_params["port"] = self.db_port

   conn = psycopg2.connect(**conn_params)
   ```

4. Added `CLOUD_SQL_CONNECTION_NAME` environment variable to Cloud Run service:
   ```bash
   CLOUD_SQL_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql
   ```

**Deployment:**
- ✅ Built and deployed GCDonationHandler revision: gcdonationhandler-10-26-00003-q5z
- ✅ Deployment succeeded in ~45 seconds
- ✅ Service healthy and serving 100% traffic
- ✅ Environment variable properly configured

**Expected Behavior After Fix:**
- ⚡ Database queries complete in < 100ms (vs 60 second timeout)
- ✅ Keypad appears within 2-3 seconds of button click
- ✅ No more "Invalid channel ID" errors for valid channels
- 📋 Logs show "🔌 Using Cloud SQL Unix socket: /cloudsql/telepay-459221:us-central1:telepaypsql"

**Verification Status:**
- ⏳ Awaiting user testing of donation button flow
- 📋 Expected log on first request: "🔌 Using Cloud SQL Unix socket"

**Lessons Learned:**
1. **Cloud Run requires Cloud SQL Unix socket** - TCP connections to public IPs are blocked by security sandbox
2. **Deployment success ≠ functional correctness** - health checks passed, but business logic was broken
3. **Integration testing gap** - tested callback routing, but not database connectivity from GCDonationHandler
4. **Misleading error messages** - "Invalid channel ID" was actually "database timeout"
5. **Standardize database patterns** - GCBotCommand had Unix socket support, GCDonationHandler didn't

**Related Documentation:**
- WORKFLOW_ERROR_MONEYFLOW.md: 45-page comprehensive root cause analysis
- WORKFLOW_ERROR_REVIEW.md: Initial callback routing issue (Session 140)
- WORKFLOW_ERROR_REVIEW_CHECKLIST.md: Implementation plan

**Follow-Up Actions:**
1. Create shared database module for all services (prevent recurrence)
2. Add integration tests covering database operations
3. Implement startup database connectivity check (fail-fast)
4. Audit other services for Cloud SQL configuration

---

### ✅ [FIXED] Donation Button Not Working - GCBotCommand Missing Callback Handlers

**Date Discovered:** 2025-11-13 Session 140
**Date Resolved:** 2025-11-13 Session 140
**File:** `GCBotCommand-10-26/handlers/callback_handler.py`
**Severity:** 🔴 CRITICAL - Core business functionality broken
**Resolution Time:** Same session

**Issue:**
Donation buttons in closed channel broadcasts were completely non-functional. When users clicked the "💝 Donate" button, nothing happened - no keypad appeared, no error message shown to user.

**User Impact:**
- ❌ ALL donation attempts failed silently
- ❌ Users couldn't complete donation flow
- ❌ No visual feedback - buttons appeared to do nothing
- ✅ Subscription workflow unaffected (uses different code path)

**Root Cause:**
GCBotCommand `callback_handler.py` was missing routing logic for donation callbacks. The refactored microservice architecture moved donation handling to GCDonationHandler service, but GCBotCommand (the Telegram webhook receiver) had no code to forward donation callbacks to that service.

**Logs Evidence:**
```
2025-11-13 18:40:32 - 🔘 Callback: donate_start_-1003268562225 from user 6271402111
2025-11-13 18:40:33 - ⚠️ Unknown callback_data: donate_start_-1003268562225
```

Callbacks were received but fell through to the `else` block and were silently ignored.

**Fix Applied:**
**Location:** `GCBotCommand-10-26/handlers/callback_handler.py`

**Changes:**
1. Added routing for `donate_start_*` callbacks (lines 70-71):
   ```python
   elif callback_data.startswith("donate_start_"):
       return self._handle_donate_start(chat_id, user_id, callback_data, callback_query)
   ```

2. Added routing for `donate_*` keypad callbacks (lines 73-75):
   ```python
   elif callback_data.startswith("donate_"):
       return self._handle_donate_keypad(chat_id, user_id, callback_data, callback_query)
   ```

3. Implemented `_handle_donate_start()` method (lines 240-307):
   - Extracts `open_channel_id` from callback_data
   - Calls GCDonationHandler `/start-donation-input` endpoint
   - Includes error handling and user-friendly error messages

4. Implemented `_handle_donate_keypad()` method (lines 309-369):
   - Forwards all keypad actions to GCDonationHandler `/keypad-input` endpoint
   - Handles digits, backspace, clear, confirm, cancel, noop
   - Fails silently to avoid disrupting keypad interaction

**Deployment:**
- ✅ Built and deployed GCBotCommand revision: gcbotcommand-10-26-00004-26n
- ✅ Deployment succeeded in 29 seconds
- ✅ Service healthy and serving 100% traffic
- ✅ Build ID: 1a7dfc9b-b18f-4ca9-a73f-80ef6ead9233

**Verification:**
- ⏳ Awaiting user testing of donation button flow
- ⏳ Need to confirm keypad appears on button click
- ⏳ Need to confirm keypad interactions work correctly
- 📋 Logs should now show: "💝 Donate button clicked" and "🌐 Calling GCDonationHandler"

**Lessons Learned:**
1. When refactoring to microservices, ensure ALL callback patterns are routed
2. Missing routing can cause silent failures (callbacks ignored with no error to user)
3. Integration testing should cover all button interaction flows
4. Log analysis crucial for identifying missing handler patterns

**Related:**
- WORKFLOW_ERROR_REVIEW.md: Documented root cause analysis
- WORKFLOW_ERROR_REVIEW_CHECKLIST.md: Implementation plan
- WORKFLOW_ERROR_REVIEW_CHECKLIST_PROGRESS.md: Execution tracking

---

## Active Bugs

### 🐛 Documentation: Invalid Example EVM Address (Low Priority)

**Date Discovered:** 2025-11-08 Session 83
**File:** WALLET_ADDRESS_VALIDATION_ANALYSIS.md
**Severity:** LOW - Documentation only, no production impact
**Status:** 🔍 **DOCUMENTED - NOT URGENT**

**Issue:**
Example EVM address used throughout documentation has only 39 hex characters instead of required 40.

**Invalid Address:**
```
0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb  ← Only 39 hex chars (should be 40)
```

**Locations:**
- Line 43: Input placeholder example
- Line 56: Address format explanation
- Line 788: Test addresses object
- Line 847: User scenario example

**Expected Format:**
- EVM addresses: `0x` + exactly 40 hexadecimal characters
- Total length: 42 characters
- Example of valid address: `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0` (added one char)

**Impact:**
- ✅ Production code unaffected - validation working correctly
- ✅ Rejects invalid addresses as expected
- ⚠️ Documentation examples misleading (shows invalid address as example)
- ⚠️ Could confuse developers reading the docs

**Fix Required:**
Replace all instances with valid 40-hex-char EVM address like:
`0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0`

**Priority:** Low - Can be fixed during next documentation update

---

## Recently Resolved

### ✅ [FIXED] Database Query Error - sub_value Column in Donation Workflow

**Date Discovered:** 2025-11-11 Session 105g
**Date Resolved:** 2025-11-11 Session 105g
**File:** `database.py`
**Severity:** HIGH - Blocked all donation attempts
**Resolution Time:** Immediate

**Issue:**
Donation workflow crashed when users tried to make donations due to database column error.

**Error Message:**
```
❌ Error fetching channel details: column "sub_value" does not exist
LINE 5:                     sub_value
```

**Root Cause:**
- `get_channel_details_by_open_id()` method queried `sub_value` column
- This method was created in Session 105e for donation message formatting
- `sub_value` is subscription pricing data, not relevant for donations
- Donations use user-entered amounts from numeric keypad
- Mixing donation and subscription logic caused database query failure

**Impact:**
- ❌ ALL donation attempts failed
- ❌ Users couldn't complete donation flow
- ✅ Subscription workflow unaffected (uses different methods)

**Fix Applied:**
**Location:** `database.py::get_channel_details_by_open_id()` lines 314-367

**Changes:**
1. Removed `sub_value` from SELECT query
2. Updated method to only fetch:
   - `closed_channel_title`
   - `closed_channel_description`
3. Updated docstring to clarify "exclusively for donation workflow"
4. Verified only title/description are used in `donation_input_handler.py`

**Before:**
```sql
SELECT
    closed_channel_title,
    closed_channel_description,
    sub_value  -- ❌ Doesn't exist / not needed
FROM main_clients_database
WHERE open_channel_id = %s
```

**After:**
```sql
SELECT
    closed_channel_title,
    closed_channel_description  -- ✅ Only what's needed
FROM main_clients_database
WHERE open_channel_id = %s
```

**Verification:**
- ✅ Method only used by donation workflow
- ✅ Donation flow only needs title/description for display
- ✅ Donation amount comes from user keypad input (not database)
- ✅ Subscription workflow uses separate methods (unaffected)

**Lessons Learned:**
1. Separate donation and subscription logic - they're different business flows
2. Don't assume column existence - verify schema before querying
3. Document method scope clearly - added "donation-specific" to docstring
4. Test all user-facing flows after database changes

**Related:**
- Session 105e: Created `get_channel_details_by_open_id()` method (introduced bug)
- Session 105g: Fixed by removing subscription-specific column query

---

