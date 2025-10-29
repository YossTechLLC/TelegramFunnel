# Bug Tracker - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-10-29

---

## Active Bugs

**None currently** - All critical bugs fixed as of 2025-10-29

---

## Recently Fixed

### 🐛 Threshold Payout Strategy Defaulting to Instant (GCWebhook1 Secret Configuration)
- **Date Fixed:** October 29, 2025
- **Severity:** CRITICAL
- **Description:** Channels configured with `payout_strategy='threshold'` were being processed as instant payouts instead of accumulating funds
- **Example:** Channel `-1003296084379` with $2.00 threshold and $1.35 payment was processed instantly instead of accumulating
- **Root Cause:**
  - GCWebhook1's Cloud Run deployment used environment variables with secret PATHS (e.g., `DATABASE_NAME_SECRET=projects/.../secrets/DATABASE_NAME_SECRET/versions/latest`)
  - config_manager.py uses `os.getenv()` expecting secret VALUES
  - When `get_payout_strategy()` queried database, it received the PATH as the value
  - Database query failed silently, defaulting to `('instant', 0)`
  - All threshold payments processed as instant via GCSplit1 instead of accumulating via GCAccumulator
- **Impact:**
  - ALL threshold-based channels broken since deployment
  - Payments not accumulating, processed instantly regardless of threshold
  - `split_payout_request.type` marked as `direct` instead of `accumulation`
  - No entries in `payout_accumulation` table
  - Threshold payout architecture completely bypassed
- **Solution:**
  - Changed GCWebhook1 deployment to use `--set-secrets` flag instead of environment variables
  - Cloud Run now injects secret VALUES directly, compatible with `os.getenv()`
  - Removed old environment variables with `--clear-env-vars`
  - Rebuilt service from source to ensure latest code deployed
  - Removed invalid VPC connector configuration
- **Files/Commands Modified:**
  - Deployment: `gcloud run deploy gcwebhook1-10-26 --set-secrets="DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,..."`
  - Cleared old env vars and VPC connector
- **Verification:**
  - Revision `gcwebhook1-10-26-00011-npq` logs show all credentials loading correctly
  - Health check shows `"database":"healthy"`
  - DatabaseManager initialized with correct database: `client_table`
- **Reference Document:** `THRESHOLD_PAYOUT_BUG_FIX_CHECKLIST.md`
- **Status:** ✅ FIXED and deployed (revision 00011-npq), ready to process threshold payouts correctly

### 🐛 Database Credentials Not Loading in GCHostPay1 and GCHostPay3
- **Date Discovered:** October 29, 2025
- **Severity:** CRITICAL
- **Description:** GCHostPay1 and GCHostPay3 showing "❌ [DATABASE] Missing required database credentials" on startup
- **Root Cause:**
  - database_manager.py used its own `_fetch_secret()` method that called Secret Manager API
  - Expected environment variables to contain secret PATHS instead of VALUES
  - Cloud Run `--set-secrets` injects secret VALUES directly via environment variables
  - Inconsistency: config_manager.py used `os.getenv()` (correct), database_manager.py used `access_secret_version()` (incorrect)
- **Impact:** GCHostPay1 and GCHostPay3 could not connect to database, payment processing completely broken
- **Solution:**
  - Removed `_fetch_secret()` and `_initialize_credentials()` methods from database_manager.py
  - Changed DatabaseManager to accept credentials via constructor parameters (like other services)
  - Updated main service files to pass credentials from config_manager to DatabaseManager
  - Follows single responsibility principle: config_manager handles secrets, database_manager handles database
- **Files Modified:**
  - `GCHostPay1-10-26/database_manager.py` - Converted to constructor-based initialization
  - `GCHostPay1-10-26/tphp1-10-26.py:53` - Pass credentials to DatabaseManager()
  - `GCHostPay3-10-26/database_manager.py` - Converted to constructor-based initialization
  - `GCHostPay3-10-26/tphp3-10-26.py:67` - Pass credentials to DatabaseManager()
- **Reference Document:** `DATABASE_CREDENTIALS_FIX_CHECKLIST.md`
- **Status:** ✅ FIXED and deployed, credentials now loading correctly

---

## Recently Fixed

### 🐛 GCWebhook2 Event Loop Closure Error
- **Date Fixed:** October 26, 2025
- **Severity:** High
- **Description:** GCWebhook2 was encountering "Event loop is closed" errors when running as async Flask route in Cloud Run
- **Root Cause:**
  - Async Flask route reused event loop between requests
  - Bot instance created at module level shared httpx connection pool
  - Cloud Run's stateless model closed event loops between requests
- **Solution:**
  - Changed to sync Flask route with `asyncio.run()`
  - Create fresh Bot instance per-request
  - Isolated event loop lifecycle within each request
  - Event loop and connections properly cleaned up after each request
- **Files Modified:**
  - `GCWebhook2-10-26/tph2-10-26.py`
- **Status:** ✅ Fixed and tested in production

### 🐛 Database Connection Pool Exhaustion
- **Date Fixed:** October 25, 2025
- **Severity:** Medium
- **Description:** Database connection pool running out under high load
- **Root Cause:** Connections not being properly closed in some error paths
- **Solution:**
  - Wrapped all database operations in context managers
  - Ensured connections closed even on exceptions
  - Added connection pool monitoring
- **Files Modified:**
  - `TelePay10-26/database.py`
  - `GCWebhook1-10-26/database_manager.py`
  - `GCSplit1-10-26/database_manager.py`
  - `GCHostPay1-10-26/database_manager.py`
  - `GCHostPay3-10-26/database_manager.py`
- **Status:** ✅ Fixed

### 🐛 Database Field Name Mismatch (db_password vs database_password)
- **Date Fixed:** October 26, 2025
- **Severity:** Low
- **Description:** Inconsistent naming between config_manager (db_password) and some services expecting database_password
- **Root Cause:** Refactoring left some references outdated
- **Solution:** Standardized to `database_password` in config_manager.py across all services
- **Files Modified:**
  - Multiple `config_manager.py` files
- **Status:** ✅ Fixed

---

## Known Issues (Non-Critical)

### ⚠️ Rate Limiting Disabled in GCRegister
- **Severity:** Low (testing phase)
- **Description:** Flask-Limiter rate limiting is currently commented out in GCRegister10-26
- **Impact:** Potential abuse during testing, but manageable
- **Plan:** Re-enable before full production launch
- **File:** `GCRegister10-26/tpr10-26.py:35-48`
- **Status:** 📋 Tracked for future fix

### ⚠️ Webhook Signature Verification Incomplete
- **Severity:** Low
- **Description:** Not all services verify webhook signatures (only GCSplit1 currently does)
- **Impact:** Relying on Cloud Tasks internal network security
- **Plan:** Implement signature verification across all webhook endpoints
- **Files Affected:**
  - `GCWebhook1-10-26/tph1-10-26.py`
  - `GCHostPay1-10-26/tphp1-10-26.py`
  - Others
- **Status:** 📋 Tracked for future enhancement

---

## Testing Notes

### Areas Requiring Testing
1. **New Telegram Bot UI**
   - Inline form navigation
   - Tier toggle functionality
   - Save/Cancel operations
   - Field validation

2. **Cloud Tasks Retry Scenarios**
   - ChangeNow API downtime
   - Ethereum RPC failures
   - Database connection issues
   - Token decryption errors

3. **Concurrent Payment Processing**
   - Multiple users subscribing simultaneously
   - Queue throughput limits
   - Database connection pool under load

---

## Bug Reporting Guidelines

When reporting bugs, please include:

1. **Service Name** - Which service exhibited the bug
2. **Severity** - Critical / High / Medium / Low
3. **Description** - What happened vs what should happen
4. **Steps to Reproduce** - Exact steps to trigger the bug
5. **Logs** - Relevant log entries with emojis for context
6. **Environment** - Production / Staging / Local
7. **User Impact** - How many users affected
8. **Proposed Solution** - If known

---

## Resolved (Archived)

### ✅ Cloud Tasks Queue Configuration Inconsistency
- **Date Fixed:** October 21, 2025
- **Description:** Some queues had exponential backoff, others had fixed
- **Solution:** Standardized all queues to 60s fixed backoff
- **Status:** ✅ Resolved

### ✅ Pure Market Value Calculation Missing
- **Date Fixed:** October 20, 2025
- **Description:** split_payout_request was storing post-fee amounts instead of pure market value
- **Solution:** Implemented calculate_pure_market_conversion() in GCSplit1
- **Status:** ✅ Resolved

---

## Notes

- All bugs are tracked with emoji prefixes for consistency
- Critical bugs should be addressed immediately
- Include relevant file paths and line numbers when possible
- Update this file after every bug fix or discovery
