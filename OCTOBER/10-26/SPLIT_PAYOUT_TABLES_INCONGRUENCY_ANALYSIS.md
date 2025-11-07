# SPLIT_PAYOUT TABLES INCONGRUENCY ANALYSIS

**Status:** CRITICAL DATABASE DESIGN FLAW IDENTIFIED
**Date:** 2025-11-07
**Severity:** HIGH - Causing 100% failure rate on retry scenarios

---

## Executive Summary

The system is experiencing **duplicate key violations** when inserting into `split_payout_que` due to a fundamental schema design flaw. The table uses `unique_id` as the primary key, but the system allows multiple ChangeNow transactions for the same payment request (due to Cloud Tasks retries or ChangeNow API retries).

### Error Evidence

```
❌ [DB_INSERT_QUE] Error: duplicate key value violates unique constraint "split_payout_que_pkey"
Key (unique_id)=(WVGGE301D98KABZ8) already exists.
```

### Root Cause

**Primary Key Constraint Violation**: `split_payout_que.unique_id` is defined as PRIMARY KEY, but the system design requires a **1-to-many relationship** (one payment request can have multiple ChangeNow transaction attempts).

---

## Current Database Schema

### Table 1: `split_payout_request`
**Purpose:** Stores initial payment split request with PURE MARKET VALUE estimate

| Column | Type | Length | Nullable | Constraint |
|--------|------|--------|----------|------------|
| unique_id | CHAR | 16 | NO | **PRIMARY KEY** |
| user_id | BIGINT | - | NO | - |
| closed_channel_id | VARCHAR | 14 | YES | - |
| from_currency | ENUM | - | NO | - |
| to_currency | ENUM | - | NO | - |
| from_network | ENUM | - | NO | - |
| to_network | ENUM | - | NO | - |
| from_amount | NUMERIC | - | YES | - |
| to_amount | NUMERIC | - | YES | ⚠️ Stores PURE MARKET value |
| client_wallet_address | VARCHAR | 95 | NO | - |
| refund_address | VARCHAR | 95 | YES | - |
| flow | ENUM | - | NO | - |
| type | ENUM | - | NO | - |
| created_at | TIMESTAMP | - | NO | - |
| updated_at | TIMESTAMP | - | NO | - |
| actual_eth_amount | NUMERIC | - | YES | ✅ Added for NowPayments outcome |

**Relationship:** 1-to-1 (one record per payment request)

---

### Table 2: `split_payout_que`
**Purpose:** Stores ACTUAL ChangeNow transaction details

| Column | Type | Length | Nullable | Constraint |
|--------|------|--------|----------|------------|
| unique_id | CHAR | 16 | NO | **PRIMARY KEY** ❌ |
| cn_api_id | VARCHAR | 14 | NO | ⚠️ Should be UNIQUE |
| user_id | BIGINT | - | NO | - |
| closed_channel_id | VARCHAR | 14 | NO | - |
| from_currency | ENUM | - | NO | - |
| to_currency | ENUM | - | NO | - |
| from_network | ENUM | - | NO | - |
| to_network | ENUM | - | NO | - |
| from_amount | NUMERIC | - | YES | - |
| to_amount | NUMERIC | - | YES | - |
| payin_address | VARCHAR | 95 | NO | ChangeNow deposit address |
| payout_address | VARCHAR | 95 | NO | Client's wallet |
| refund_address | VARCHAR | 95 | YES | - |
| flow | ENUM | - | NO | - |
| type | ENUM | - | NO | - |
| created_at | TIMESTAMP | - | NO | - |
| updated_at | TIMESTAMP | - | NO | - |

**MISSING FIELD:** `actual_eth_amount` (losing critical data!)

**Relationship:** Should be 1-to-many (multiple ChangeNow attempts per request), but PRIMARY KEY constraint prevents this ❌

---

### Table 3: `split_payout_hostpay`
**Purpose:** Stores host wallet payment transaction to ChangeNow

| Column | Type | Length | Nullable | Constraint |
|--------|------|--------|----------|------------|
| unique_id | VARCHAR | 64 | NO | ⚠️ NO PRIMARY KEY SHOWN |
| cn_api_id | VARCHAR | 16 | NO | - |
| from_currency | ENUM | - | NO | - |
| from_network | ENUM | - | NO | - |
| from_amount | NUMERIC | - | NO | - |
| payin_address | VARCHAR | 95 | NO | ChangeNow deposit address |
| is_complete | BOOLEAN | - | NO | - |
| created_at | TIMESTAMP | - | NO | - |
| updated_at | TIMESTAMP | - | NO | - |
| tx_hash | VARCHAR | 66 | YES | Ethereum transaction hash |
| tx_status | VARCHAR | 20 | YES | - |
| gas_used | INTEGER | - | YES | - |
| block_number | INTEGER | - | YES | - |
| actual_eth_amount | NUMERIC | - | YES | ✅ Present but NOT populated (0E-18) |

**Relationship:** 1-to-1 (one payment per ChangeNow transaction)

---

## Critical Issues Identified

### Issue 1: Primary Key Constraint Violation ❌ CRITICAL

**Problem:** `split_payout_que` uses `unique_id` as PRIMARY KEY, preventing multiple ChangeNow transactions for the same payment request.

**Evidence from production:**
- `unique_id: WVGGE301D98KABZ8`
- First insertion: `cn_api_id: 2613f186d2ca97` ✅ Success (2025-11-07 16:44:46)
- Second insertion: `cn_api_id: e0671475fecaf9` ❌ Failed (2025-11-07 16:46:48)
- Error: `duplicate key value violates unique constraint "split_payout_que_pkey"`

**Why this happens:**
1. GCSplit1 generates `unique_id` and inserts into `split_payout_request`
2. GCSplit1 sends token to GCSplit3 via Cloud Tasks
3. Cloud Tasks task fails or times out → **RETRY**
4. GCSplit3 called AGAIN with same `unique_id`
5. GCSplit3 creates NEW ChangeNow transaction → Different `cn_api_id`
6. GCSplit3 sends response back to GCSplit1 endpoint_3
7. GCSplit1 endpoint_3 tries to insert into `split_payout_que` → **DUPLICATE KEY ERROR**

**Impact:**
- 100% failure rate on retry scenarios
- Lost ChangeNow transactions (created but not tracked)
- Potential financial loss (multiple ChangeNow swaps for same request)

---

### Issue 2: Missing Idempotency Protection ❌ CRITICAL

**Problem:** GCSplit1 endpoint_3 doesn't check if record already exists before inserting.

**Code location:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py` Lines 702-718

```python
que_success = database_manager.insert_split_payout_que(
    unique_id=unique_id,  # ❌ No duplicate check before insertion
    cn_api_id=cn_api_id,
    # ... other params
)
```

**Expected behavior:**
- Check if `unique_id` already exists in `split_payout_que`
- If exists, log warning and skip insertion (idempotent operation)
- Return success (200 OK) to prevent Cloud Tasks retry

**Actual behavior:**
- Blindly tries to insert
- Raises duplicate key error → 500 Internal Server Error
- Cloud Tasks retries the task again → Infinite loop

---

### Issue 3: Wrong Primary Key on `split_payout_que` ❌ CRITICAL

**Problem:** `unique_id` should NOT be the primary key. `cn_api_id` should be.

**Correct schema design:**

```sql
-- WRONG (current)
ALTER TABLE split_payout_que ADD PRIMARY KEY (unique_id);

-- CORRECT (should be)
ALTER TABLE split_payout_que DROP CONSTRAINT split_payout_que_pkey;
ALTER TABLE split_payout_que ADD PRIMARY KEY (cn_api_id);
ALTER TABLE split_payout_que ADD INDEX idx_unique_id (unique_id);  -- For lookups
```

**Reasoning:**
- `cn_api_id` is UNIQUE across ALL ChangeNow transactions (guaranteed by ChangeNow API)
- `unique_id` links multiple ChangeNow attempts to the original payment request
- Multiple ChangeNow transactions can share the same `unique_id` (retry scenario)

**Table relationship:**
```
split_payout_request (unique_id: PRIMARY KEY)
    ↓ 1-to-many
split_payout_que (cn_api_id: PRIMARY KEY, unique_id: FOREIGN KEY)
    ↓ 1-to-1
split_payout_hostpay (unique_id: links back to original request)
```

---

### Issue 4: Missing `actual_eth_amount` in `split_payout_que` ⚠️ HIGH

**Problem:** `split_payout_que` doesn't have `actual_eth_amount` field.

**Impact:**
- Losing critical data: ACTUAL ETH received from NowPayments
- Cannot track discrepancy between ChangeNow estimates and NowPayments outcome
- Cannot audit payment flows end-to-end

**Evidence:**
- `split_payout_request.actual_eth_amount`: ✅ Present (0.000976800000000000)
- `split_payout_que.actual_eth_amount`: ❌ Missing
- `split_payout_hostpay.actual_eth_amount`: ✅ Present but NOT populated (0E-18)

**Code location:** `/OCTOBER/10-26/GCSplit1-10-26/database_manager.py` Lines 219-332

The `insert_split_payout_que()` method doesn't accept `actual_eth_amount` parameter.

---

### Issue 5: Data Type Inconsistencies ⚠️ MEDIUM

**Problem:** `unique_id` has different data types across tables.

| Table | Type | Length | Issue |
|-------|------|--------|-------|
| split_payout_request | CHAR | 16 | ✅ Fixed length |
| split_payout_que | CHAR | 16 | ✅ Fixed length |
| split_payout_hostpay | VARCHAR | 64 | ⚠️ Variable length for batch IDs |

**Why this is inconsistent:**
- Instant payments use 16-char `unique_id` (e.g., `WVGGE301D98KABZ8`)
- Batch conversions use 42-char `unique_id` (e.g., `batch_e0514205-7777-4444-8888-123456789012`)
- `split_payout_request` and `split_payout_que` can NEVER store batch IDs (16-char limit)
- `split_payout_hostpay` can store both (64-char limit)

**Impact:**
- Batch conversions cannot be tracked in `split_payout_request` or `split_payout_que`
- Schema fragmentation (different rules for instant vs threshold payouts)

**Evidence:** Recent migration extended `split_payout_hostpay.unique_id` from VARCHAR(16) to VARCHAR(64) to fix batch ID truncation.

**File:** `/OCTOBER/10-26/scripts/fix_split_payout_hostpay_unique_id_length.sql`

---

### Issue 6: `split_payout_hostpay.actual_eth_amount` Not Populated ⚠️ HIGH

**Problem:** Field exists but contains garbage value `0E-18` (scientific notation for 0).

**Evidence from production:**
```
split_payout_hostpay:
  unique_id: WVGGE301D98KABZ8
  cn_api_id: 2613f186d2ca97
  from_amount: 0.00097680  ✅ Correct (ACTUAL ETH)
  actual_eth_amount: 0E-18  ❌ Not populated
```

**Code location:** `/OCTOBER/10-26/GCHostPay1-10-26/database_manager.py` Line 79

The `insert_hostpay_transaction()` method accepts `actual_eth_amount` parameter but it's not being passed from the caller.

**Caller location:** Check GCHostPay1 main endpoint to see if `actual_eth_amount` is being passed.

---

### Issue 7: No Composite Unique Constraint on `cn_api_id` ⚠️ MEDIUM

**Problem:** `split_payout_que` has no UNIQUE constraint on `cn_api_id`.

**Risk:**
- Same ChangeNow transaction could be inserted twice with different `unique_id` values
- Data duplication
- Financial tracking errors

**Expected constraint:**
```sql
ALTER TABLE split_payout_que ADD CONSTRAINT unique_cn_api_id UNIQUE (cn_api_id);
```

---

## Data Flow Analysis

### Instant Payout Flow (ETH source)

```
1. NowPayments IPN → GCWebhook1
   ↓ actual_eth_amount = 0.0009768 ETH (from NowPayments outcome)

2. GCWebhook1 → GCSplit1 endpoint_1
   ↓ Creates split_payout_request
   ↓ unique_id = WVGGE301D98KABZ8 (generated)
   ↓ from_currency = ETH, from_amount = 0.00083028 (after TP fee)
   ↓ to_amount = 281709.38735868 (PURE MARKET VALUE in SHIB)
   ↓ actual_eth_amount = 0.0009768 (stored) ✅

3. GCSplit1 → GCSplit2 (get estimate)
   ↓ Returns encrypted token with fee-adjusted amounts

4. GCSplit1 endpoint_2 → GCSplit3 (via Cloud Tasks)
   ↓ Sends: unique_id, swap_currency=eth, payout_mode=instant
   ↓ Sends: actual_eth_amount = 0.0009768 ✅

5. GCSplit3 → ChangeNow API
   ↓ Creates transaction: cn_api_id = 2613f186d2ca97
   ↓ Returns: from_amount = 0.00083028 ETH (estimate)
   ↓ Returns: to_amount = 161245.77561010 SHIB

6. GCSplit3 → GCSplit1 endpoint_3 (via Cloud Tasks)
   ↓ Receives: unique_id, cn_api_id, amounts
   ↓ Tries to insert into split_payout_que
   ↓ ✅ SUCCESS (first attempt)

7. ⚠️ CLOUD TASKS RETRY (network timeout/failure)
   ↓ GCSplit1 → GCSplit3 (RETRY)
   ↓ GCSplit3 creates NEW ChangeNow transaction: cn_api_id = e0671475fecaf9
   ↓ GCSplit3 → GCSplit1 endpoint_3
   ↓ Tries to insert into split_payout_que with SAME unique_id
   ↓ ❌ FAILURE: duplicate key constraint violation

8. split_payout_que insertion fails
   ↓ Returns 500 Internal Server Error
   ↓ Cloud Tasks retries AGAIN
   ↓ Infinite retry loop ❌
```

---

## Correct Schema Design

### Option A: Change Primary Key (RECOMMENDED)

**Change `split_payout_que` primary key from `unique_id` to `cn_api_id`:**

```sql
BEGIN;

-- Step 1: Drop existing primary key constraint
ALTER TABLE split_payout_que DROP CONSTRAINT split_payout_que_pkey;

-- Step 2: Add new primary key on cn_api_id
ALTER TABLE split_payout_que ADD PRIMARY KEY (cn_api_id);

-- Step 3: Add index on unique_id for lookups (1-to-many relationship)
CREATE INDEX IF NOT EXISTS idx_split_payout_que_unique_id ON split_payout_que(unique_id);

-- Step 4: Add unique constraint on cn_api_id (belt and suspenders)
ALTER TABLE split_payout_que ADD CONSTRAINT unique_cn_api_id UNIQUE (cn_api_id);

-- Step 5: Add actual_eth_amount column
ALTER TABLE split_payout_que ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;

-- Step 6: Add constraint for positive values
ALTER TABLE split_payout_que ADD CONSTRAINT actual_eth_positive_que CHECK (actual_eth_amount >= 0);

COMMIT;
```

**Update code to match:**
- `insert_split_payout_que()`: Add `actual_eth_amount` parameter
- Endpoint_3: Pass `actual_eth_amount` when inserting
- Add idempotency check: Query by `unique_id` OR `cn_api_id` before inserting

---

### Option B: Add Composite Primary Key

**Use `(unique_id, cn_api_id)` as composite primary key:**

```sql
BEGIN;

-- Drop existing primary key
ALTER TABLE split_payout_que DROP CONSTRAINT split_payout_que_pkey;

-- Add composite primary key
ALTER TABLE split_payout_que ADD PRIMARY KEY (unique_id, cn_api_id);

-- Add unique constraint on cn_api_id
ALTER TABLE split_payout_que ADD CONSTRAINT unique_cn_api_id UNIQUE (cn_api_id);

-- Add actual_eth_amount column
ALTER TABLE split_payout_que ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;

COMMIT;
```

**Pros:**
- Maintains `unique_id` as part of primary key
- Allows multiple ChangeNow transactions per request
- Enforces uniqueness on `cn_api_id`

**Cons:**
- More complex primary key
- Requires both fields for lookups

---

## Idempotency Implementation

### Add Check Before Insertion

**Location:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py` Lines 695-723

**BEFORE:**
```python
# Insert into split_payout_que table
que_success = database_manager.insert_split_payout_que(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    # ... other params
)

if not que_success:
    print(f"❌ [ENDPOINT_3] Failed to insert into split_payout_que")
    abort(500, "Database insertion failed")  # ❌ Causes infinite retry
```

**AFTER (Option 1: Check by unique_id):**
```python
# Check if this unique_id already has a record in split_payout_que
existing_record = database_manager.check_split_payout_que_exists(unique_id=unique_id)

if existing_record:
    print(f"⚠️ [ENDPOINT_3] Record already exists for unique_id: {unique_id}")
    print(f"   Existing cn_api_id: {existing_record['cn_api_id']}")
    print(f"   Current cn_api_id: {cn_api_id}")

    if existing_record['cn_api_id'] == cn_api_id:
        print(f"✅ [ENDPOINT_3] Idempotent request - same ChangeNow transaction")
    else:
        print(f"⚠️ [ENDPOINT_3] Different ChangeNow transaction - likely retry")
        print(f"   Using existing record, skipping insertion")

    # Return success to prevent Cloud Tasks retry
    return jsonify({
        "status": "success",
        "message": "Record already processed (idempotent)",
        "unique_id": unique_id,
        "cn_api_id": existing_record['cn_api_id']
    }), 200

# Insert into split_payout_que table (only if not exists)
que_success = database_manager.insert_split_payout_que(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    actual_eth_amount=actual_eth_amount,  # ✅ NEW PARAMETER
    # ... other params
)
```

**AFTER (Option 2: Check by cn_api_id - BETTER):**
```python
# Check if this ChangeNow transaction already processed
existing_record = database_manager.check_split_payout_que_by_cn_api_id(cn_api_id=cn_api_id)

if existing_record:
    print(f"✅ [ENDPOINT_3] ChangeNow transaction already processed: {cn_api_id}")
    print(f"   Idempotent request - returning success")

    # Return success to prevent Cloud Tasks retry
    return jsonify({
        "status": "success",
        "message": "ChangeNow transaction already processed (idempotent)",
        "unique_id": existing_record['unique_id'],
        "cn_api_id": cn_api_id
    }), 200

# Insert into split_payout_que table
que_success = database_manager.insert_split_payout_que(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    actual_eth_amount=actual_eth_amount,  # ✅ NEW PARAMETER
    # ... other params
)

if not que_success:
    print(f"❌ [ENDPOINT_3] Failed to insert into split_payout_que")
    # Check if failure is due to duplicate (race condition)
    existing_record = database_manager.check_split_payout_que_by_cn_api_id(cn_api_id=cn_api_id)
    if existing_record:
        print(f"✅ [ENDPOINT_3] Record inserted by concurrent request - treating as success")
        return jsonify({
            "status": "success",
            "message": "Concurrent insertion handled (idempotent)",
            "unique_id": unique_id,
            "cn_api_id": cn_api_id
        }), 200
    else:
        abort(500, "Database insertion failed")
```

---

## Database Manager Updates Needed

### File: `/OCTOBER/10-26/GCSplit1-10-26/database_manager.py`

#### 1. Add `check_split_payout_que_by_cn_api_id()` method

```python
def check_split_payout_que_by_cn_api_id(self, cn_api_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if a ChangeNow transaction already exists in split_payout_que.

    Args:
        cn_api_id: ChangeNow transaction ID

    Returns:
        Dictionary with record data if exists, None otherwise
    """
    conn = None
    cur = None
    try:
        conn = self.get_database_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT unique_id, cn_api_id, created_at FROM split_payout_que WHERE cn_api_id = %s",
            (cn_api_id,)
        )

        row = cur.fetchone()
        if row:
            print(f"✅ [DB_CHECK] ChangeNow transaction exists: {cn_api_id}")
            return {
                'unique_id': row[0],
                'cn_api_id': row[1],
                'created_at': row[2]
            }
        else:
            print(f"✅ [DB_CHECK] ChangeNow transaction not found: {cn_api_id}")
            return None

    except Exception as e:
        print(f"❌ [DB_CHECK] Error checking ChangeNow transaction: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
```

#### 2. Update `insert_split_payout_que()` to accept `actual_eth_amount`

**Line 219:** Add parameter
```python
def insert_split_payout_que(
    self,
    unique_id: str,
    cn_api_id: str,
    user_id: int,
    closed_channel_id: str,
    from_currency: str,
    to_currency: str,
    from_network: str,
    to_network: str,
    from_amount: float,
    to_amount: float,
    payin_address: str,
    payout_address: str,
    refund_address: str = "",
    flow: str = "standard",
    type_: str = "direct",
    actual_eth_amount: float = 0.0  # ✅ NEW PARAMETER
) -> bool:
```

**Line 275:** Update INSERT statement
```python
insert_query = """
    INSERT INTO split_payout_que (
        unique_id, cn_api_id, user_id, closed_channel_id,
        from_currency, to_currency, from_network, to_network,
        from_amount, to_amount, payin_address, payout_address, refund_address,
        flow, type, actual_eth_amount
    ) VALUES (
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s
    )
"""
```

**Line 290:** Update params tuple
```python
params = (
    unique_id, cn_api_id, user_id, closed_channel_id,
    from_currency.upper(), to_currency.upper(),
    from_network.upper(), to_network.upper(),
    from_amount, to_amount,
    payin_address, payout_address, refund_address,
    flow, type_,
    actual_eth_amount  # ✅ NEW VALUE
)
```

---

## Recommended Fix Strategy

### Phase 1: Emergency Hotfix (Immediate)

**Goal:** Stop duplicate key errors WITHOUT schema changes

**Steps:**
1. Add idempotency check to GCSplit1 endpoint_3 (check by `unique_id`)
2. If record exists, return 200 OK (skip insertion)
3. Deploy GCSplit1

**Time:** 30 minutes
**Risk:** Low
**Impact:** Stops errors, but doesn't fix underlying schema flaw

---

### Phase 2: Schema Correction (Next session)

**Goal:** Fix schema design to support 1-to-many relationship

**Steps:**
1. Run SQL migration to change primary key from `unique_id` to `cn_api_id`
2. Add `actual_eth_amount` column to `split_payout_que`
3. Update `insert_split_payout_que()` method to accept `actual_eth_amount`
4. Update GCSplit1 endpoint_3 to pass `actual_eth_amount`
5. Update idempotency check to use `cn_api_id` (more accurate)
6. Deploy all changes

**Time:** 1 hour
**Risk:** Medium (schema change)
**Impact:** Fixes root cause, enables proper tracking

---

### Phase 3: Data Type Consistency (Future)

**Goal:** Extend `unique_id` length in all tables for batch support

**Steps:**
1. Extend `split_payout_request.unique_id` from CHAR(16) to VARCHAR(64)
2. Extend `split_payout_que.unique_id` from CHAR(16) to VARCHAR(64)
3. Verify all code handles variable-length IDs
4. Test batch conversions end-to-end

**Time:** 2 hours
**Risk:** Low
**Impact:** Enables batch processing in all tables

---

## Testing Strategy

### Test Case 1: Duplicate unique_id (Retry Scenario)

**Setup:**
1. Create payment request with `unique_id = TEST123456789012`
2. Send to GCSplit3 → Creates `cn_api_id = aaa111`
3. GCSplit3 responds to endpoint_3 → Inserts into split_payout_que ✅
4. **Simulate retry:** Send to GCSplit3 again with SAME `unique_id`
5. GCSplit3 creates NEW ChangeNow transaction → `cn_api_id = bbb222`
6. GCSplit3 responds to endpoint_3 → Tries to insert into split_payout_que

**Expected Result (BEFORE fix):**
- ❌ Duplicate key error on `unique_id`
- 500 Internal Server Error
- Cloud Tasks retry loop

**Expected Result (AFTER Phase 1 fix):**
- ✅ Idempotency check detects existing `unique_id`
- Skips insertion, returns 200 OK
- No error, no retry

**Expected Result (AFTER Phase 2 fix):**
- ✅ Both ChangeNow transactions inserted (different `cn_api_id`)
- Database shows 2 records with same `unique_id`, different `cn_api_id`
- Proper 1-to-many relationship

---

### Test Case 2: Duplicate cn_api_id (Race Condition)

**Setup:**
1. Two Cloud Tasks execute endpoint_3 simultaneously
2. Both have same `cn_api_id = xyz789` (shouldn't happen, but test anyway)
3. Both try to insert into split_payout_que

**Expected Result (BEFORE fix):**
- One succeeds, one fails with duplicate `unique_id` error

**Expected Result (AFTER Phase 2 fix):**
- One succeeds, one fails with duplicate `cn_api_id` error (PRIMARY KEY)
- Failed request checks for existing record by `cn_api_id`
- Finds record, treats as idempotent, returns 200 OK

---

## Verification Queries

### Check for Multiple ChangeNow Transactions per Request

```sql
-- Find unique_ids with multiple ChangeNow transactions
SELECT
    unique_id,
    COUNT(*) as transaction_count,
    STRING_AGG(cn_api_id, ', ') as cn_api_ids,
    MIN(created_at) as first_attempt,
    MAX(created_at) as last_attempt
FROM split_payout_que
GROUP BY unique_id
HAVING COUNT(*) > 1
ORDER BY transaction_count DESC;
```

### Check for Orphaned ChangeNow Transactions

```sql
-- Find ChangeNow transactions not linked to any request
SELECT
    q.unique_id,
    q.cn_api_id,
    q.created_at as que_created
FROM split_payout_que q
LEFT JOIN split_payout_request r ON q.unique_id = r.unique_id
WHERE r.unique_id IS NULL;
```

### Check actual_eth_amount Discrepancies

```sql
-- Compare request vs que actual_eth_amount (after Phase 2 fix)
SELECT
    r.unique_id,
    r.actual_eth_amount as request_actual_eth,
    q.cn_api_id,
    q.actual_eth_amount as que_actual_eth,
    q.from_amount as que_from_amount,
    ABS(r.actual_eth_amount - q.actual_eth_amount) as discrepancy
FROM split_payout_request r
JOIN split_payout_que q ON r.unique_id = q.unique_id
WHERE r.actual_eth_amount > 0
ORDER BY discrepancy DESC
LIMIT 20;
```

---

## Summary of Changes Needed

### Database Schema (Phase 2)

| Table | Column | Change | Reason |
|-------|--------|--------|--------|
| split_payout_que | PRIMARY KEY | `unique_id` → `cn_api_id` | Support 1-to-many relationship |
| split_payout_que | actual_eth_amount | ADD COLUMN NUMERIC(20,18) | Track NowPayments outcome |
| split_payout_que | cn_api_id | ADD UNIQUE CONSTRAINT | Prevent duplicate ChangeNow transactions |
| split_payout_que | unique_id | ADD INDEX | Optimize 1-to-many lookups |

### Code Changes (Phase 1 & 2)

| File | Method | Change | Phase |
|------|--------|--------|-------|
| GCSplit1/database_manager.py | check_split_payout_que_by_cn_api_id() | ADD METHOD | Phase 1 |
| GCSplit1/database_manager.py | insert_split_payout_que() | ADD actual_eth_amount param | Phase 2 |
| GCSplit1/tps1-10-26.py | endpoint_3 | ADD idempotency check | Phase 1 |
| GCSplit1/tps1-10-26.py | endpoint_3 | PASS actual_eth_amount | Phase 2 |

---

## Estimated Time & Risk

| Phase | Time | Risk | Impact |
|-------|------|------|--------|
| Phase 1 (Hotfix) | 30 min | Low | Stop errors immediately |
| Phase 2 (Schema Fix) | 1 hour | Medium | Fix root cause |
| Phase 3 (Data Types) | 2 hours | Low | Enable batch processing |
| **Total** | **3.5 hours** | - | - |

---

**Last Updated:** 2025-11-07
**Priority:** CRITICAL - Deploy Phase 1 immediately
**Status:** Ready for implementation
