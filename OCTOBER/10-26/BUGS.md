# Bug Tracker - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-14 Session 155

---

## Recently Resolved

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
1. Created `BroadcastService` module (`api/services/broadcast_service.py`)
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
**Files:** `TelePay10-26/database.py`, `TelePay10-26/subscription_manager.py`
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
- `TelePay10-26/database.py` - 6 methods fixed
- `TelePay10-26/subscription_manager.py` - 2 methods fixed

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
**File:** `TelePay10-26/database.py`
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
- `TelePay10-26/database.py:64-87` - Added fetch_cloud_sql_connection_name() function
- `TelePay10-26/database.py:95` - Added DB_CLOUD_SQL_CONNECTION_NAME module variable
- `TelePay10-26/database.py:119` - Updated init_connection_pool() to use fetched value

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
- ⚠️ Lower conversion rate (some users abandon at confirmation)
- ✅ Payments still functional (not blocking)

**Root Cause:**
URL buttons in groups/channels ALWAYS show Telegram's security confirmation dialog. This is an intentional anti-phishing feature per Telegram Bot API documentation and CANNOT be bypassed when using URL buttons in groups.

**Initial Fix (Session 142.5):**
Replaced WebApp button with URL button to avoid `Button_type_invalid` error:
```python
# Fixed Button_type_invalid but introduced confirmation dialog
button = InlineKeyboardButton(
    text="💰 Complete Donation Payment",
    url=invoice_url  # ❌ URL buttons in groups show confirmation
)
```

**Final Fix (Session 143):**
Send payment to user's private chat using WebApp button:
```python
# Group notification
group_notification = "📨 A secure payment link has been sent to your private messages."
self.telegram_client.send_message(chat_id=chat_id, text=group_notification)

# Private chat with WebApp button
button = InlineKeyboardButton(
    text="💳 Open Payment Gateway",
    web_app=WebAppInfo(url=invoice_url)  # ✅ Opens instantly in DMs
)
self.telegram_client.send_message(
    chat_id=user_id,  # ✅ User's private chat (DM)
    text=private_text,
    reply_markup=InlineKeyboardMarkup([[button]])
)
```

**Error Handling Added:**
```python
if not dm_result['success']:
    # User hasn't started bot - send fallback to group
    fallback_text = (
        f"⚠️ <b>Cannot Send Payment Link</b>\n\n"
        f"Please <b>start a private chat</b> with me first:\n"
        f"1. Click my username above\n"
        f"2. Press \"Start\" button\n"
        f"3. Return here and try again\n\n"
        f"Your payment link: {invoice_url}"
    )
    self.telegram_client.send_message(chat_id=chat_id, text=fallback_text)
```

**Deployment:**
- ✅ Built and deployed GCDonationHandler revision: gcdonationhandler-10-26-00008-5k4
- ✅ Service deployed and serving 100% traffic
- ✅ Build ID: 9851b106-f997-485b-827d-bb1094edeefd (SUCCESS)

**Expected Behavior After Fix:**
- ✅ Payment gateway opens INSTANTLY without confirmation dialog
- ✅ Better UX (users expect payments in private)
- ✅ More secure (payment details not visible in group)
- ✅ Clear error recovery if user hasn't started bot

**Verification Status:**
- ⏳ Awaiting user testing of payment flow
- 📋 Expected: Payment button appears in user's private chat
- 📋 Expected: WebApp button opens seamlessly (no confirmation)

**Lessons Learned:**
1. **Telegram Button Restrictions:** URL buttons in groups ALWAYS show confirmation (anti-phishing feature)
2. **Best Practices:** Send payment links to private chat (industry standard per @DurgerKingBot, @PizzaHut_Bot)
3. **Documentation Research:** Context7 MCP revealed Telegram official recommendations for payment flows
4. **Error Handling:** Must handle users who haven't started bot (graceful degradation)

**Related Documentation:**
- PAYMENT_LINK_DM_FIX_CHECKLIST.md: Comprehensive solution plan
- WEBAPP_BUTTON_FIX_CHECKLIST.md: Initial fix attempt (URL button)
- Telegram Bot API Docs: Button types and restrictions

---

### ✅ [FIXED] WebApp Button Invalid in Groups - Payment Link Not Appearing

**Date Discovered:** 2025-11-13 Session 142.5
**Date Resolved:** 2025-11-13 Session 142.5
**File:** `GCDonationHandler-10-26/keypad_handler.py`
**Severity:** 🔴 CRITICAL - Payment workflow completely broken
**Resolution Time:** Same session (15 minutes)

**Issue:**
After donation confirmation, users saw "✅ Donation Confirmed / 💰 Amount: $584.00 / Preparing your payment gateway..." but no payment button appeared. Workflow terminated without sending payment link.

**User Impact:**
- ❌ 100% payment link delivery failure
- ❌ Users couldn't complete donation after confirming amount
- ❌ Revenue completely blocked

**Root Cause:**
WebApp buttons (`web_app` parameter) only work in private chats, NOT in groups/channels. Telegram rejects WebApp buttons in groups with `Button_type_invalid` error.

**Logs Evidence:**
```
2025-11-13 22:22:47,400 - telegram_client - ERROR - ❌ Failed to send message to chat -1003111266231: Button_type_invalid
```

Chat ID `-1003111266231` is a group/channel (negative ID). WebApp buttons are only allowed in private chats (positive user IDs).

**Fix Applied:**
**Location:** `GCDonationHandler-10-26/keypad_handler.py` lines 498-510

**Changed from WebApp button:**
```python
self.telegram_client.send_message_with_webapp_button(
    chat_id=chat_id,
    text=text,
    button_text="💰 Complete Donation Payment",
    webapp_url=invoice_url  # ❌ FAILS: WebApp not allowed in groups
)
```

**To URL button:**
```python
button = InlineKeyboardButton(
    text="💰 Complete Donation Payment",
    url=invoice_url  # ✅ Works everywhere (including groups)
)
keyboard = InlineKeyboardMarkup([[button]])

self.telegram_client.send_message(
    chat_id=chat_id,
    text=text,
    reply_markup=keyboard,
    parse_mode="HTML"
)
```

**Deployment:**
- ✅ Built and deployed GCDonationHandler revision: gcdonationhandler-10-26-00007-ghm
- ✅ Service deployed successfully

**Verification:**
- ✅ Payment button now appears after donation confirmation
- ✅ No more `Button_type_invalid` errors in logs
- ⚠️ Introduced new issue: URL buttons show "Open this link?" confirmation (fixed in Session 143)

**Lessons Learned:**
1. **WebApp Button Restrictions:** Only work in private chats, not groups/channels
2. **URL Buttons:** Work everywhere but show confirmation dialog in groups
3. **Testing Gap:** Didn't test button types in group context before deployment

**Related Documentation:**
- WEBAPP_BUTTON_FIX_CHECKLIST.md: Initial fix documentation

---

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

