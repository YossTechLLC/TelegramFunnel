# Bug Tracker - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-10-29

---

## Active Bugs

**None currently** - All critical bugs fixed as of 2025-10-29

---

## Recently Fixed

### 🐛 Token Expiration Too Short for Cloud Tasks Retry Timing
- **Date Fixed:** October 29, 2025
- **Severity:** CRITICAL
- **Description:** GCHostPay services (GCHostPay1, GCHostPay2, GCHostPay3) using 60-second token expiration window, causing "Token expired" errors when Cloud Tasks retries exceeded this window
- **Example Error:**
  ```
  2025-10-29 11:18:34.747 EDT
  🎯 [ENDPOINT] Payment execution request received (from GCHostPay1)
  ❌ [ENDPOINT] Token validation error: Token expired
  ❌ [ENDPOINT] Unexpected error: 400 Bad Request: Token error: Token expired
  ```
- **Root Cause:**
  - All GCHostPay TokenManager files validated tokens with 60-second expiration: `if not (current_time - 60 <= timestamp <= current_time + 5)`
  - Cloud Tasks has variable delivery delays (10-30 seconds) + 60-second retry backoff
  - Total time from token creation to retry delivery could exceed 60 seconds
  - Token validation failed on legitimate Cloud Tasks retries
- **Timeline Example:**
  - Token created at time T
  - First request at T+20s - SUCCESS (within 60s window)
  - Cloud Tasks retry at T+80s - FAIL (token expired, outside 60s window)
  - Cloud Tasks retry at T+140s - FAIL (token expired)
- **Impact:**
  - Payment execution failures on Cloud Tasks retries
  - Manual intervention required to reprocess failed payments
  - User payments stuck in processing state
  - System appears unreliable due to retry failures
- **Solution:**
  - Extended token expiration from 60 seconds to 300 seconds (5 minutes)
  - Updated validation logic in all GCHostPay TokenManager files
  - New validation: `if not (current_time - 300 <= timestamp <= current_time + 5)`
  - Accommodates: Initial delivery (30s) + Multiple retries (60s each) + Buffer (30s)
- **Files Modified:**
  - `GCHostPay1-10-26/token_manager.py` - Updated 5 token validation methods
  - `GCHostPay2-10-26/token_manager.py` - Copied from GCHostPay1
  - `GCHostPay3-10-26/token_manager.py` - Copied from GCHostPay1
- **Deployment:**
  - GCHostPay1: revision `gchostpay1-10-26-00005-htc`
  - GCHostPay2: revision `gchostpay2-10-26-00005-hb9`
  - GCHostPay3: revision `gchostpay3-10-26-00006-ndl`
- **Verification:**
  - All services deployed successfully (status: True)
  - Token validation now allows 5-minute window
  - Cloud Tasks retries no longer fail with "Token expired"
- **Status:** ✅ FIXED and deployed, payment retries now working correctly

### 🐛 GCSplit1 Missing /batch-payout Endpoint Causing 404 Errors
- **Date Fixed:** October 29, 2025
- **Severity:** CRITICAL
- **Description:** GCSplit1 did not have a `/batch-payout` endpoint to handle batch payout requests from GCBatchProcessor, resulting in 404 errors
- **Root Causes:**
  1. **Missing endpoint implementation** - GCSplit1 only had endpoints for instant payouts (/, /usdt-eth-estimate, /eth-client-swap)
  2. **Missing token decryption method** - TokenManager lacked `decrypt_batch_token()` method to handle batch tokens
  3. **Incorrect signing key** - GCSplit1 TokenManager initialized with SUCCESS_URL_SIGNING_KEY but batch tokens encrypted with TPS_HOSTPAY_SIGNING_KEY
- **Example Error:**
  - GCBatchProcessor successfully created batch and enqueued task to `gcsplit1-batch-queue`
  - Cloud Tasks sent POST to `https://gcsplit1-10-26.../batch-payout`
  - GCSplit1 returned 404 - endpoint not found
  - Cloud Tasks retried with exponential backoff
- **Impact:**
  - Batch payouts could not be processed
  - Tasks accumulated in Cloud Tasks queue
  - Clients over threshold had batches created but never executed
  - Split workflow broken for batch payouts
- **Solution:**
  1. **Added `/batch-payout` endpoint** to GCSplit1 (tps1-10-26.py lines 700-833)
  2. **Implemented `decrypt_batch_token()`** in TokenManager (token_manager.py lines 637-686)
  3. **Updated TokenManager constructor** to accept separate `batch_signing_key` parameter
  4. **Modified GCSplit1 initialization** to pass TPS_HOSTPAY_SIGNING_KEY for batch token decryption
  5. **Deployed GCSplit1 revision 00009-krs** with all fixes
- **Files Modified:**
  - `GCSplit1-10-26/tps1-10-26.py` - Added /batch-payout endpoint
  - `GCSplit1-10-26/token_manager.py` - Added decrypt_batch_token() method, updated constructor
- **Verification:**
  - Endpoint now exists and returns proper responses
  - Token decryption uses correct signing key
  - Batch payout flow: GCBatchProcessor → GCSplit1 /batch-payout → GCSplit2 → GCSplit3 → GCHostPay
- **Status:** ✅ FIXED and deployed (revision gcsplit1-10-26-00009-krs)

### 🐛 Batch Payout System Not Processing Due to Secret Newlines and Query Bug
- **Date Fixed:** October 29, 2025
- **Severity:** CRITICAL
- **Description:** Threshold payout batches were not being created despite accumulations exceeding threshold
- **Root Causes:**
  1. **GCSPLIT1_BATCH_QUEUE secret had trailing newline** - Cloud Tasks API rejected task creation with "400 Queue ID" error
  2. **GCAccumulator used wrong ID field** - Queried `open_channel_id` instead of `closed_channel_id` for threshold lookup
- **Example:**
  - Client -1003296084379 accumulated $2.295 USDT (threshold: $2.00)
  - GCBatchProcessor found the client but Cloud Tasks enqueue failed
  - GCAccumulator logs showed "threshold: $0" due to wrong query column
- **Impact:**
  - No batch payouts being created since threshold payout deployment
  - `payout_batches` table remained empty
  - Accumulated payments stuck in `payout_accumulation` indefinitely
  - Manual intervention required to process accumulated funds
- **Solution:**
  1. **Fixed Secret Newlines:**
     - Removed trailing `\n` from GCSPLIT1_BATCH_QUEUE using `echo -n`
     - Created `fix_secret_newlines.sh` to audit and fix all queue/URL secrets
     - Redeployed GCBatchProcessor to pick up new secret version
  2. **Fixed GCAccumulator Threshold Query:**
     - Changed `WHERE open_channel_id = %s` to `WHERE closed_channel_id = %s`
     - Aligned with how `payout_accumulation.client_id` stores the value
     - Redeployed GCAccumulator with fix
- **Files Modified:**
  - `GCSPLIT1_BATCH_QUEUE` secret (version 2 created)
  - `GCAccumulator-10-26/database_manager.py:206` - Fixed WHERE clause
  - `GCBatchProcessor-10-26/database_manager.py` - Added debug logging (temporary)
  - `fix_secret_newlines.sh` - Created utility script
- **Verification:**
  - Batch `bd90fadf-fdc8-4f9e-b575-9de7a7ff41e0` created successfully
  - Task enqueued: `projects/.../queues/gcsplit1-batch-queue/tasks/79768775309535645311`
  - Both payout_accumulation records marked `is_paid_out=TRUE`
  - Batch status: `processing`
- **Reference Document:** `THRESHOLD_PAYOUT_BUG_FIX_SUMMARY.md`
- **Status:** ✅ FIXED and deployed, batch payouts now working correctly

### 🐛 Trailing Newlines in Secret Manager Queue Names Breaking Cloud Tasks
- **Date Fixed:** October 29, 2025
- **Severity:** CRITICAL
- **Description:** Queue names stored in Secret Manager had trailing newline characters (`\n`), causing Cloud Tasks API to reject task creation with "Queue ID can contain only letters, numbers, or hyphens" error
- **Example Error:** `Queue ID "accumulator-payment-queue\n" can contain only letters ([A-Za-z]), numbers ([0-9]), or hyphens (-)`
- **Root Cause:**
  - Secrets were created with `echo` instead of `echo -n`, adding unwanted newlines
  - Affected secrets:
    - `GCACCUMULATOR_QUEUE` = `"accumulator-payment-queue\n"`
    - `GCSPLIT3_QUEUE` = `"gcsplit-eth-client-swap-queue\n"`
    - `GCHOSTPAY1_RESPONSE_QUEUE` = `"gchostpay1-response-queue\n"`
    - `GCACCUMULATOR_URL` = `"https://gcaccumulator-10-26-291176869049.us-central1.run.app\n"`
    - `GCWEBHOOK2_URL` = `"https://gcwebhook2-10-26-291176869049.us-central1.run.app\n"`
  - When `config_manager.py` loaded these via `os.getenv()`, it included the `\n`
  - Cloud Tasks queue creation failed validation
- **Impact:**
  - GCWebhook1 could NOT route threshold payments to GCAccumulator (fell back to instant payout)
  - All threshold payout functionality broken
  - Payments that should accumulate were processed instantly
- **Solution (Two-Pronged):**
  1. **Fixed Secret Manager values** - Created new versions without trailing newlines using `echo -n`
  2. **Added defensive `.strip()`** - Updated `fetch_secret()` in all config_manager.py files to strip whitespace
- **Files Modified:**
  - Secret Manager: Created version 2 of all affected secrets
  - `GCWebhook1-10-26/config_manager.py:40` - Added `.strip()`
  - `GCSplit3-10-26/config_manager.py:40` - Added `.strip()`
  - `GCHostPay3-10-26/config_manager.py:40` - Added `.strip()`
- **Verification:**
  - All secrets verified with `cat -A` (no `$` at end = no newline)
  - GCWebhook1 revision `00012-9pb` logs show successful queue name loading
  - Health check shows all components healthy
- **Status:** ✅ FIXED and deployed, threshold routing now works correctly

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
