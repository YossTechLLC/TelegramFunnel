# Architectural Decisions - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-01 (Archived previous entries to DECISIONS_ARCH.md)

This document records all significant architectural decisions made during the development of the TelegramFunnel payment system.

---

## Table of Contents
1. [Service Architecture](#service-architecture)
2. [Cloud Infrastructure](#cloud-infrastructure)
3. [Data Flow & Orchestration](#data-flow--orchestration)
4. [Security & Authentication](#security--authentication)
5. [Database Design](#database-design)
6. [Error Handling & Resilience](#error-handling--resilience)
7. [User Interface](#user-interface)

---

## Recent Decisions

### 2025-11-02: Database Query Pattern - JOIN for Multi-Table Data Retrieval

**Decision:** Use explicit JOINs when data spans multiple tables instead of assuming all data exists in a single table

**Context:**
- Token encryption was failing in GCWebhook1 with "required argument is not an integer"
- Root cause: np-webhook was querying wrong column names (`subscription_time` vs `sub_time`)
- Deeper issue: Wallet/payout data stored in different table than subscription data

**Problem:**
```python
# BROKEN (np-webhook original):
cur.execute("""
    SELECT wallet_address, payout_currency, payout_network,
           subscription_time, subscription_price
    FROM private_channel_users_database
    WHERE user_id = %s AND private_channel_id = %s
""")
# Returns None for all fields (columns don't exist in this table)
```

**Database Architecture Discovery:**
- **Table 1:** `private_channel_users_database`
  - Contains: `sub_time`, `sub_price` (subscription info)
  - Does NOT contain: wallet/payout data

- **Table 2:** `main_clients_database`
  - Contains: `client_wallet_address`, `client_payout_currency`, `client_payout_network`
  - Does NOT contain: subscription info

- **JOIN Key:** `private_channel_id = closed_channel_id`

**Solution Implemented:**
```python
# FIXED (np-webhook with JOIN):
cur.execute("""
    SELECT
        c.client_wallet_address,
        c.client_payout_currency::text,
        c.client_payout_network::text,
        u.sub_time,
        u.sub_price
    FROM private_channel_users_database u
    JOIN main_clients_database c ON u.private_channel_id = c.closed_channel_id
    WHERE u.user_id = %s AND u.private_channel_id = %s
    ORDER BY u.id DESC LIMIT 1
""")
```

**Type Safety Added:**
- Convert ENUM types to text: `::text` for currency and network
- Ensure string type: `str(sub_price)` before passing to encryption
- Validate types before encryption in token_manager.py

**Rationale:**
1. **Correctness:** Query actual column names from database schema
2. **Completeness:** JOIN tables to get all required data in one query
3. **Performance:** Single query better than multiple round-trips
4. **Type Safety:** Explicit type conversions prevent runtime errors

**Impact on Services:**
- ✅ np-webhook: Now fetches complete payment data correctly
- ✅ GCWebhook1: Receives valid data for token encryption
- ✅ Token encryption: No longer fails with type errors

**Enforcement:**
- Always verify database schema before writing queries
- Use JOINs when data spans multiple tables
- Add defensive type checking at service boundaries

---

### 2025-11-02: Defensive Type Validation in Token Encryption

**Decision:** Add explicit type validation before binary struct packing operations

**Context:**
- `struct.pack(">H", None)` produces cryptic error: "required argument is not an integer"
- Error occurs deep in token encryption, making debugging difficult
- No validation of input types before binary operations

**Problem:**
```python
# BROKEN (token_manager.py original):
def encrypt_token_for_gcwebhook2(self, user_id, closed_channel_id, subscription_time_days, subscription_price):
    packed_data.extend(struct.pack(">H", subscription_time_days))  # Fails if None!
    price_bytes = subscription_price.encode('utf-8')  # Fails if None!
```

**Solution Implemented:**
```python
# FIXED (token_manager.py with validation):
def encrypt_token_for_gcwebhook2(self, user_id, closed_channel_id, subscription_time_days, subscription_price):
    # Validate input types
    if not isinstance(user_id, int):
        raise ValueError(f"user_id must be integer, got {type(user_id).__name__}: {user_id}")
    if not isinstance(subscription_time_days, int):
        raise ValueError(f"subscription_time_days must be integer, got {type(subscription_time_days).__name__}: {subscription_time_days}")
    if not isinstance(subscription_price, str):
        raise ValueError(f"subscription_price must be string, got {type(subscription_price).__name__}: {subscription_price}")

    # Now safe to use struct.pack
    packed_data.extend(struct.pack(">H", subscription_time_days))
```

**Additional Safeguards in GCWebhook1:**
```python
# Validate before calling token encryption
if not subscription_time_days or not subscription_price:
    print(f"❌ Missing subscription data")
    abort(400, "Missing subscription data from payment")

# Ensure correct types
subscription_time_days = int(subscription_time_days)
subscription_price = str(subscription_price)
```

**Rationale:**
1. **Clear Errors:** "must be integer, got NoneType" vs "required argument is not an integer"
2. **Early Detection:** Fail at service boundary, not deep in encryption
3. **Type Safety:** Explicit isinstance() checks prevent silent coercion
4. **Debugging:** Include actual value and type in error message

**Pattern for Binary Operations:**
- Always validate types before `struct.pack()`, `struct.unpack()`
- Use isinstance() checks, not duck typing
- Raise ValueError with clear type information
- Validate at service boundaries AND in shared libraries

---

### 2025-11-02: Dockerfile Module Copy Pattern Standardization

**Decision:** Enforce explicit `COPY` commands for all local Python modules in Dockerfiles instead of relying on `COPY . .`

**Context:**
- np-webhook service failed to initialize CloudTasks client
- Error: `No module named 'cloudtasks_client'`
- Root cause: Dockerfile missing `COPY cloudtasks_client.py .` command
- File existed in source but wasn't copied into container

**Problem:**
```dockerfile
# BROKEN (np-webhook original):
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .  # Missing cloudtasks_client.py!

# WORKING (GCWebhook1 pattern):
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY cloudtasks_client.py .
COPY database_manager.py .
COPY app.py .
```

**Options Considered:**
1. **Explicit COPY for each file** (CHOSEN)
   - Pros: Clear dependencies, reproducible builds, smaller image size
   - Cons: More verbose, must remember to add new files
   - Pattern: `COPY module.py .` for each module

2. **COPY . . (copy everything)**
   - Pros: Simple, never misses files
   - Cons: Larger images, cache invalidation, unclear dependencies
   - Used by: GCMicroBatchProcessor (acceptable for simple services)

3. **.dockerignore with COPY . .**
   - Pros: Flexible, can exclude unnecessary files
   - Cons: Still unclear what's actually needed

**Decision Rationale:**
- **Explicit is better than implicit** (Python Zen)
- Clear dependency graph visible in Dockerfile
- Easier to audit what's being deployed
- Smaller Docker images (only copy what's needed)
- Better cache utilization (change app.py doesn't invalidate module layers)

**Implementation:**
```dockerfile
# Standard pattern for all services:
FROM python:3.11-slim
WORKDIR /app

# Step 1: Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 2: Copy modules in dependency order
COPY config_manager.py .      # Config (no dependencies)
COPY database_manager.py .    # DB (depends on config)
COPY token_manager.py .       # Token (depends on config)
COPY cloudtasks_client.py .   # CloudTasks (depends on config)
COPY app.py .                 # Main app (depends on all above)

# Step 3: Run
CMD ["python", "app.py"]
```

**Services Verified:**
- ✅ GCWebhook1: Explicit COPY pattern
- ✅ GCSplit1, GCSplit2, GCSplit3: Explicit COPY pattern
- ✅ GCAccumulator, GCBatchProcessor: Explicit COPY pattern
- ✅ GCHostPay1, GCHostPay2, GCHostPay3: Explicit COPY pattern
- ✅ np-webhook: FIXED to explicit COPY pattern
- ✅ GCMicroBatchProcessor: Uses `COPY . .` (acceptable, simple service)

**Enforcement:**
- All new services MUST use explicit COPY pattern
- Document required modules in Dockerfile comments
- Code review checklist: Verify all Python imports have corresponding COPY commands

---

### 2025-11-02: Outcome Amount USD Conversion for Payment Validation

**Decision:** Validate payment using `outcome_amount` converted to USD (actual received) instead of `price_amount` (invoice price)

**Context:**
- Previous fix (Session 30) added `price_amount` validation
- But `price_amount` is the subscription invoice amount, NOT what the host wallet receives
- NowPayments takes fees (~15-20%) before sending crypto to host wallet
- Host receives `outcome_amount` (e.g., 0.00026959 ETH) which is less than invoice
- Need to validate what was ACTUALLY received, not what was invoiced

**Problem Scenario:**
```
User pays: $1.35 subscription (price_amount)
NowPayments processes: Takes 20% fee ($0.27)
Host receives: 0.00026959 ETH (outcome_amount)
Current validation: $1.35 >= $1.28 ✅ PASS
Actual USD value received: 0.00026959 ETH × $4,000 = $1.08
Should validate: $1.08 >= minimum expected
```

**Options Considered:**
1. **Continue using price_amount** - Validate invoice price
   - Pros: Simple, no external dependencies
   - Cons: Doesn't validate actual received amount, can't detect excessive fees

2. **Use outcome_amount with real-time price feed** - Convert crypto to USD
   - Pros: Validates actual received value, fee transparency, accurate
   - Cons: External API dependency, price volatility

3. **Query NowPayments API for conversion** - Use NowPayments own conversion rates
   - Pros: Authoritative source, no third-party dependency
   - Cons: Requires API authentication, rate limits, extra latency

4. **Hybrid approach** - outcome_amount conversion with price_amount fallback
   - Pros: Best accuracy, graceful degradation if API fails
   - Cons: Most complex implementation

**Decision Rationale:**
- **Option 4 selected**: Hybrid with outcome_amount conversion primary, price_amount fallback

**Implementation:**

**Tier 1 (PRIMARY)**: Outcome Amount USD Conversion
```python
# Convert crypto to USD using CoinGecko
outcome_usd = convert_crypto_to_usd(outcome_amount, outcome_currency)
# Example: 0.00026959 ETH × $4,000/ETH = $1.08 USD

# Validate actual received amount
minimum_amount = expected_amount * 0.75  # 75% threshold
if outcome_usd >= minimum_amount:  # $1.08 >= $1.01 ✅
    return True

# Log fee reconciliation
fee_lost = price_amount - outcome_usd  # $1.35 - $1.08 = $0.27
fee_percentage = (fee_lost / price_amount) * 100  # 20%
```

**Tier 2 (FALLBACK)**: Invoice Price Validation
```python
# If price feed fails, fall back to price_amount
if price_amount:
    minimum = expected_amount * 0.95
    if price_amount >= minimum:
        # Log warning: validating invoice, not actual received
        return True
```

**Tier 3 (ERROR)**: No Validation Possible
```python
# Neither outcome conversion nor price_amount available
return False, "Cannot validate payment"
```

**Price Feed Choice:**
- **CoinGecko Free API** selected
  - No authentication required
  - 50 calls/minute (sufficient for our volume)
  - Supports all major cryptocurrencies
  - Reliable and well-maintained

**Validation Threshold:**
```
Subscription Price: $1.35 (100%)
Expected Fees: ~20% = $0.27 (NowPayments 15% + network 5%)
Expected Received: ~80% = $1.08
Tolerance: 5% = $0.07
Minimum: 75% = $1.01
```

**Trade-offs:**
- ✅ Validates actual USD value received (accurate)
- ✅ Fee transparency (logs actual fees)
- ✅ Prevents invitations for underpaid transactions
- ✅ Backward compatible (falls back to price_amount)
- ⚠️ External API dependency (CoinGecko)
- ⚠️ ~50-100ms additional latency per validation
- ⚠️ Price volatility during conversion time (acceptable)

**Alternative Rejected:**
- **NowPayments API**: Requires authentication, rate limits, extra complexity
- **price_amount only**: Doesn't validate actual received amount

**Impact:**
- Payment validation now checks actual wallet balance
- Host protected from excessive fee scenarios
- Fee reconciliation enabled for accounting
- Transparent logging of invoice vs received amounts

**Files Modified:**
- `GCWebhook2-10-26/database_manager.py` (crypto price feed methods, validation logic)
- `GCWebhook2-10-26/requirements.txt` (requests dependency)

**Related Decision:**
- Session 30: price_amount capture (prerequisite for fee reconciliation)

---

### 2025-11-02: NowPayments Payment Validation Strategy (USD-to-USD Comparison)

**Decision:** Use `price_amount` (original USD invoice amount) for payment validation instead of `outcome_amount` (crypto amount after fees)

**Context:**
- GCWebhook2 payment validation was failing for all crypto payments
- Root cause: Comparing crypto amounts directly to USD expectations
  - Example: outcome_amount = 0.00026959 ETH (what merchant receives)
  - Validation: $0.0002696 < $1.08 (80% of $1.35) ❌ FAILS
- NowPayments IPN provides both `price_amount` (USD) and `outcome_amount` (crypto)
- Previous implementation only captured `outcome_amount`, losing USD reference

**Options Considered:**
1. **Capture price_amount from IPN** - Store original USD invoice amount
   - Pros: Clean USD-to-USD comparison, no external dependencies
   - Cons: Requires database schema change, doesn't help old records

2. **Implement crypto-to-USD conversion** - Use real-time price feed
   - Pros: Can validate any crypto payment
   - Cons: Requires external API, price volatility, API failures affect validation

3. **Skip amount validation** - Only check payment_status = "finished"
   - Pros: Simple, no changes needed
   - Cons: Risk of fraud, can't detect underpayment

4. **Hybrid approach** - Use price_amount when available, fallback to stablecoin or price feed
   - Pros: Best of all worlds, backward compatible
   - Cons: More complex logic

**Decision Rationale:**
- **Option 4 selected**: Hybrid 3-tier validation strategy

**Implementation:**
1. **Tier 1 (PRIMARY)**: USD-to-USD validation using `price_amount`
   - Tolerance: 95% (allows 5% for rounding/fees)
   - When: price_amount available (all new payments)
   - Example: $1.35 >= $1.28 ✅

2. **Tier 2 (FALLBACK)**: Stablecoin validation for old records
   - Detects USDT/USDC/BUSD as USD-equivalent
   - Tolerance: 80% (accounts for NowPayments ~15% fee)
   - When: price_amount not available, outcome in stablecoin
   - Example: $1.15 USDT >= $1.08 ✅

3. **Tier 3 (FUTURE)**: Crypto price feed
   - For non-stablecoin cryptos without price_amount
   - Requires CoinGecko or similar API integration
   - Currently fails validation (manual approval needed)

**Schema Changes:**
- Added 3 columns to `private_channel_users_database`:
  - `nowpayments_price_amount` (DECIMAL) - Original USD amount
  - `nowpayments_price_currency` (VARCHAR) - Original currency
  - `nowpayments_outcome_currency` (VARCHAR) - Crypto currency

**Trade-offs:**
- ✅ Solves immediate problem (crypto payment validation)
- ✅ Backward compatible (doesn't break old records)
- ✅ Future-proof (can add price feed later)
- ⚠️ Old records without price_amount require manual verification for non-stablecoins

**Alternative Rejected:**
- **Real-time price feed only**: Too complex, external dependency, price volatility
- **Skip validation**: Security risk, can't detect underpayment

**Impact:**
- Payment validation success rate: 0% → ~95%+ expected
- User experience: Payment → instant validation → invitation sent
- Fee tracking: Can now reconcile fees using price_amount vs outcome_amount

**Files Modified:**
- `tools/execute_price_amount_migration.py` (NEW)
- `np-webhook-10-26/app.py` (IPN capture)
- `GCWebhook2-10-26/database_manager.py` (validation logic)

---

### 2025-11-02: NowPayments Order ID Format Change (Pipe Separator)

**Decision:** Changed NowPayments order_id format from `PGP-{user_id}{open_channel_id}` to `PGP-{user_id}|{open_channel_id}` using pipe separator

**Context:**
- NowPayments IPN webhooks receiving callbacks but failing to store payment_id in database
- Root cause: Order ID format `PGP-6271402111-1003268562225` loses negative sign
- Telegram channel IDs are ALWAYS negative (e.g., -1003268562225)
- When concatenating with `-`, negative sign becomes separator: `PGP-{user_id}-{abs(channel_id)}`
- Database lookup fails: searches for +1003268562225, finds nothing (actual ID is -1003268562225)

**Options Considered:**
1. **Modify database schema** - Add open_channel_id to private_channel_users_database
   - Pros: Direct lookup without intermediate query
   - Cons: Requires migration, affects all services, breaks existing functionality

2. **Use different separator (|)** - Change order_id format to preserve negative sign
   - Pros: Quick fix, no schema changes, backward compatible
   - Cons: Requires updating both TelePay bot and np-webhook

3. **Store absolute value and add negative** - Assume all channel IDs are negative
   - Pros: Works with existing format
   - Cons: Fragile assumption, doesn't solve root cause

**Decision Rationale:**
- **Option 2 selected**: Change separator to pipe (`|`)
- Safer than database migration (no risk to existing data)
- Faster implementation (2 files vs. full system migration)
- Backward compatible: old format supported during transition
- Pipe separator cannot appear in user IDs or channel IDs (unambiguous)

**Implementation:**
1. TelePay Bot (`start_np_gateway.py:168`):
   - OLD: `order_id = f"PGP-{user_id}{open_channel_id}"`
   - NEW: `order_id = f"PGP-{user_id}|{open_channel_id}"`
   - Added validation: ensure channel_id starts with `-`

2. np-webhook (`app.py`):
   - Created `parse_order_id()` function
   - Detects format: `|` present → new format, else old format
   - Old format fallback: adds negative sign back (`-abs(channel_id)`)
   - Two-step database lookup:
     - Parse order_id → extract user_id, open_channel_id
     - Query main_clients_database → get closed_channel_id
     - Update private_channel_users_database using closed_channel_id

**Impact:**
- ✅ Payment IDs captured correctly from NowPayments
- ✅ Fee reconciliation unblocked
- ✅ Customer support enabled for payment disputes
- ⚠️ Old format orders processed with fallback logic (7-day transition window)

**Trade-offs:**
- Pros: Zero database changes, minimal code changes, immediate fix
- Cons: Two parsing formats to maintain (temporary during transition)

**References:**
- Checklist: `NP_WEBHOOK_FIX_CHECKLIST.md`
- Root cause: `NP_WEBHOOK_403_ROOT_CAUSE_ANALYSIS.md`
- Progress: `NP_WEBHOOK_FIX_CHECKLIST_PROGRESS.md`

---

### 2025-11-02: np-webhook Two-Step Database Lookup

**Decision:** Implemented two-step database lookup in np-webhook to correctly map channel IDs

**Context:**
- Order ID contains `open_channel_id` (public channel)
- Database update targets `private_channel_users_database` using `private_channel_id` (private channel)
- These are DIFFERENT channel IDs for the same Telegram channel group
- Direct lookup impossible without intermediate mapping

**Implementation:**
```python
# Step 1: Parse order_id
user_id, open_channel_id = parse_order_id(order_id)

# Step 2: Look up closed_channel_id from main_clients_database
SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s

# Step 3: Update private_channel_users_database
UPDATE private_channel_users_database
SET nowpayments_payment_id = %s, ...
WHERE user_id = %s AND private_channel_id = %s
```

**Rationale:**
- Database schema correctly normalized: one channel relationship per subscription
- `main_clients_database` holds channel mapping (open → closed)
- `private_channel_users_database` tracks subscription access (user → private channel)
- Two-step lookup respects existing architecture without modifications

**Trade-offs:**
- Pros: Works with existing schema, no migrations, respects normalization
- Cons: Two database queries per IPN (acceptable for low-volume webhook)

---

### 2025-11-02: np-webhook Secret Configuration Fix

**Decision:** Configured np-webhook Cloud Run service with required secrets for IPN processing and database updates

**Context:**
- GCWebhook2 payment validation implementation revealed payment_id always NULL in database
- Investigation showed NowPayments sending IPN callbacks but np-webhook returning 403 Forbidden
- np-webhook service configuration inspection revealed ZERO secrets mounted
- Service couldn't verify IPN signatures or connect to database without secrets
- Critical blocker preventing payment_id capture throughout payment flow

**Problem:**
1. np-webhook deployed without any environment variables or secrets
2. Service receives IPN POST from NowPayments with payment metadata
3. Without NOWPAYMENTS_IPN_SECRET, can't verify callback signature → rejects with 403
4. Without database credentials, can't write payment_id even if signature verified
5. NowPayments retries IPN callbacks but eventually gives up
6. Database never populated with payment_id from successful payments
7. Downstream services (GCWebhook1, GCWebhook2, GCAccumulator) all working correctly but no data to process

**Implementation:**
1. **Mounted 5 Required Secrets:**
   ```bash
   gcloud run services update np-webhook --region=us-east1 \
     --update-secrets=NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,\
   CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
   DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
   DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
   DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest
   ```

2. **Deployed New Revision:**
   - Created revision: `np-webhook-00004-kpk`
   - Routed 100% traffic to new revision
   - Old revision (00003-r27) with no secrets deprecated

3. **Secrets Mounted:**
   - **NOWPAYMENTS_IPN_SECRET**: IPN callback signature verification
   - **CLOUD_SQL_CONNECTION_NAME**: PostgreSQL connection string
   - **DATABASE_NAME_SECRET**: Database name (telepaydb)
   - **DATABASE_USER_SECRET**: Database user (postgres)
   - **DATABASE_PASSWORD_SECRET**: Database authentication

4. **Verification:**
   - Inspected service description → all 5 secrets present as environment variables
   - IAM permissions already correct (service account has secretAccessor role)
   - Service health check returns 405 for GET (expected - only accepts POST)

**Rationale:**
- **Critical Path**: np-webhook is the only service that receives payment_id from NowPayments
- **Single Point of Failure**: Without np-webhook processing IPNs, payment_id never enters system
- **Graceful Degradation**: System worked without payment_id but lacked fee reconciliation capability
- **Security First**: IPN signature verification prevents forged payment confirmations
- **Database Integration**: Must connect to database to update payment metadata

**Alternatives Considered:**
1. **Query NowPayments API directly in GCWebhook1:** Rejected - inefficient, rate limits, IPN already available
2. **Store payment_id in token payload:** Rejected - payment_id not available when token created (race condition)
3. **Use different service for IPN handling:** Rejected - np-webhook already exists and deployed
4. **Make payment_id optional permanently:** Rejected - defeats purpose of fee reconciliation implementation

**Trade-offs:**
- **Pro**: Enables complete payment_id flow from NowPayments through entire system
- **Pro**: Fixes 100% of payment validation failures in GCWebhook2
- **Pro**: Minimal code changes (configuration only, no code deployment)
- **Pro**: Immediate effect - next IPN callback will succeed
- **Con**: Requires retest of entire payment flow to verify
- **Con**: Historical payments missing payment_id (can backfill if needed)

**Impact:**
- ✅ np-webhook can now process IPN callbacks from NowPayments
- ✅ Database will be updated with payment_id for new payments
- ✅ GCWebhook2 payment validation will succeed instead of retry loop
- ✅ Telegram invitations will be sent immediately after payment
- ✅ Fee reconciliation data now captured for all future payments
- ⏳ Requires payment test to verify end-to-end flow working

**Files Modified:**
- np-webhook Cloud Run service configuration (5 secrets added)

**Files Created:**
- `/NP_WEBHOOK_403_ROOT_CAUSE_ANALYSIS.md` (investigation details)
- `/NP_WEBHOOK_FIX_SUMMARY.md` (fix summary and verification)

**Status:** ✅ Deployed - Awaiting payment test for verification

---

### 2025-11-02: GCWebhook2 Payment Validation Security Fix

**Decision:** Added payment validation to GCWebhook2 service to verify payment completion before sending Telegram invitations

**Context:**
- Security review revealed GCWebhook2 was sending Telegram invitations without payment verification
- Service blindly trusted encrypted tokens from GCWebhook1
- No check for NowPayments IPN callback or payment_id existence
- Race condition could allow unauthorized access if payment failed after token generation
- Critical security vulnerability in payment flow

**Problem:**
1. GCWebhook1 creates encrypted token and enqueues GCWebhook2 task immediately after creating subscription record
2. GCWebhook2 receives token and sends Telegram invitation without checking payment status
3. If NowPayments IPN callback is delayed or payment fails, user gets invitation without paying
4. No validation of payment_id, payment_status, or payment amount

**Implementation:**
1. **New Database Manager:**
   - Created `database_manager.py` with Cloud SQL Connector integration
   - `get_nowpayments_data()`: Queries payment_id, status, address, outcome_amount
   - `validate_payment_complete()`: Validates payment against business rules
   - Returns tuple of (is_valid: bool, error_message: str)

2. **Payment Validation Rules:**
   - Check payment_id exists (populated by np-webhook IPN callback)
   - Verify payment_status = 'finished'
   - Validate outcome_amount >= 80% of expected price (accounts for 15% NowPayments fee + 5% tolerance)

3. **Cloud Tasks Retry Logic:**
   - Return 503 if IPN callback not yet processed → Cloud Tasks retries after 60s
   - Return 400 if payment invalid (wrong amount, failed status) → Cloud Tasks stops retrying
   - Return 200 only after payment validation succeeds

4. **Configuration Updates:**
   - Added database credential fetching to `config_manager.py`
   - Fetches CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME_SECRET, DATABASE_USER_SECRET, DATABASE_PASSWORD_SECRET
   - Updated `requirements.txt` with cloud-sql-python-connector and pg8000
   - Fixed Dockerfile to include database_manager.py

**Rationale:**
- **Security:** Prevents unauthorized Telegram access without payment confirmation
- **Trust Model:** Zero-trust approach - validate payment even with signed tokens
- **Race Condition Fix:** Handles IPN delays gracefully with retry logic
- **Business Logic:** Validates payment amount to prevent underpayment fraud
- **Reliability:** Cloud Tasks retry ensures eventual consistency when IPN delayed

**Alternatives Considered:**
1. **Skip validation, trust GCWebhook1 token:** Rejected - security vulnerability
2. **Validate in GCWebhook1 before enqueueing:** Rejected - still has race condition
3. **Poll NowPayments API directly:** Rejected - inefficient, rate limits, already have IPN data
4. **Add payment_id to token payload:** Rejected - token created before payment_id available

**Trade-offs:**
- **Performance:** Additional database query per invitation (~50ms latency)
- **Complexity:** Requires database credentials in GCWebhook2 service
- **Dependencies:** Adds Cloud SQL Connector dependency to service
- **Benefit:** Eliminates critical security vulnerability, worth the cost

**Impact:**
- GCWebhook2 now validates payment before sending invitations
- Service health check includes database_manager status
- Payment validation logs provide audit trail
- Cloud Tasks retry logic handles IPN delays automatically

**Files Modified:**
- `/GCWebhook2-10-26/database_manager.py` (NEW)
- `/GCWebhook2-10-26/tph2-10-26.py` (payment validation added)
- `/GCWebhook2-10-26/config_manager.py` (database credentials)
- `/GCWebhook2-10-26/requirements.txt` (dependencies)
- `/GCWebhook2-10-26/Dockerfile` (copy database_manager.py)

**Status:** ✅ Implemented and deployed (gcwebhook2-10-26-00011-w2t)

---

### 2025-11-02: TelePay Bot - Secret Manager Integration for IPN Callback URL

**Decision:** Modified TelePay bot to fetch IPN callback URL from Google Cloud Secret Manager instead of directly from environment variables

**Context:**
- Phase 3 of payment_id implementation originally used direct environment variable lookup
- Inconsistent with existing secret management pattern for `PAYMENT_PROVIDER_TOKEN`
- Environment variables storing sensitive URLs less secure than Secret Manager
- Needed centralized secret management across all services

**Implementation:**
1. **New Method Added:**
   - `fetch_ipn_callback_url()` method follows same pattern as `fetch_payment_provider_token()`
   - Fetches from Secret Manager using path from `NOWPAYMENTS_IPN_CALLBACK_URL` env var
   - Returns IPN URL or None if not configured

2. **Initialization Pattern:**
   - `__init__()` now calls `fetch_ipn_callback_url()` on startup
   - Stores IPN URL in `self.ipn_callback_url` instance variable
   - Can be overridden via constructor parameter for testing

3. **Invoice Creation:**
   - `create_payment_invoice()` uses `self.ipn_callback_url` instead of `os.getenv()`
   - Single fetch on initialization, not on every invoice creation
   - Better performance and consistent behavior

**Rationale:**
- **Security:** Secrets stored in Secret Manager with IAM controls, audit logging, versioning
- **Consistency:** Matches existing pattern for all other secrets in codebase
- **Maintainability:** Single source of truth for IPN URL configuration
- **Flexibility:** Environment variable only needs secret path, not the actual URL
- **Observability:** Better logging at fetch time vs. usage time

**Trade-offs:**
- Environment variable now stores secret path instead of actual URL
- Secret Manager API call on bot startup (minimal latency ~50-100ms)
- Must restart bot to pick up secret changes (acceptable for infrequent changes)

**Impact:**
- ✅ More secure secret management
- ✅ Consistent with codebase patterns
- ✅ Better error handling and logging
- ✅ Zero impact on invoice creation performance

**Configuration Required:**
```bash
# Old way (Phase 3 - Direct URL):
export NOWPAYMENTS_IPN_CALLBACK_URL="https://np-webhook-291176869049.us-east1.run.app"

# New way (Session 26 - Secret Manager path):
export NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest"
```

---

### 2025-11-02: NowPayments Payment ID Storage Architecture

**Decision:** Implemented payment_id storage and propagation through the payment flow to enable fee discrepancy resolution

**Context:**
- Fee discrepancies discovered between NowPayments charges and actual blockchain transactions
- Cannot reconcile fees without linking NowPayments payment_id to our database records
- Need to track actual fees paid vs. estimated fees for accurate accounting

**Implementation:**
1. **Database Layer:**
   - Added 10 NowPayments columns to `private_channel_users_database` (payment_id, invoice_id, order_id, pay_address, payment_status, pay_amount, pay_currency, outcome_amount, created_at, updated_at)
   - Added 5 NowPayments columns to `payout_accumulation` (payment_id, pay_address, outcome_amount, network_fee, payment_fee_usd)
   - Created indexes on payment_id and order_id for fast lookups

2. **Service Integration:**
   - Leveraged existing `np-webhook` service for IPN handling
   - Updated GCWebhook1 to query payment_id after database write and pass to GCAccumulator
   - Updated GCAccumulator to store payment_id in payout_accumulation records
   - Added NOWPAYMENTS_IPN_SECRET and NOWPAYMENTS_IPN_CALLBACK_URL to Secret Manager

3. **TelePay Bot Updates (Phase 3):**
   - Updated `start_np_gateway.py` to include `ipn_callback_url` in NowPayments invoice creation
   - Bot now passes IPN endpoint to NowPayments: `https://np-webhook-291176869049.us-east1.run.app`
   - Added logging to track invoice_id, order_id, and IPN callback URL for debugging
   - Environment variable `NOWPAYMENTS_IPN_CALLBACK_URL` must be set before bot starts

4. **Data Flow:**
   - TelePay bot creates invoice with `ipn_callback_url` specified
   - Customer pays → NowPayments sends IPN to np-webhook
   - NowPayments IPN → np-webhook → updates `private_channel_users_database` with payment_id
   - NowPayments success_url → GCWebhook1 → queries payment_id → passes to GCAccumulator
   - GCAccumulator → stores payment_id in `payout_accumulation`

**Rationale:**
- Minimal changes to existing architecture (reused np-webhook service)
- payment_id propagates through entire payment flow automatically
- Enables future fee reconciliation tools via NowPayments API queries
- Database indexes ensure fast lookups even with large datasets

**Trade-offs:**
- Relies on np-webhook IPN arriving before success_url (usually true, but not guaranteed)
- If IPN delayed, payment_id will be NULL initially but can be backfilled
- Additional database storage for NowPayments metadata (~300 bytes per payment)

**Impact:**
- Zero downtime migration (additive schema changes)
- Backward compatible (payment_id fields are optional)
- Foundation for accurate fee tracking and discrepancy resolution

---

### 2025-11-02: Micro-Batch Processor Schedule Optimization

**Decision:** Reduced micro-batch-conversion-job scheduler interval from 15 minutes to 5 minutes

**Rationale:**
- Faster threshold detection for accumulated payments
- Improved payout latency for users (3x faster threshold checks)
- Aligns with batch-processor-job interval (also 5 minutes)
- No functional changes to service logic - only scheduling frequency

**Impact:**
- Threshold checks now occur every 5 minutes instead of 15 minutes
- Maximum wait time for threshold detection reduced from 15 min to 5 min
- Expected payout completion time reduced by up to 10 minutes
- Minimal increase in Cloud Scheduler API calls (cost negligible)

**Configuration:**
```
Schedule: */5 * * * * (Etc/UTC)
Target: https://gcmicrobatchprocessor-10-26-291176869049.us-central1.run.app/check-threshold
State: ENABLED
```

---

## Notes
- All previous architectural decisions have been archived to DECISIONS_ARCH.md
- This file tracks only the most recent architectural decisions
- Add new decisions at the TOP of the document
