# SPLIT_PAYOUT TABLES IMPLEMENTATION CHECKLIST

**Date:** 2025-11-07
**Source:** SPLIT_PAYOUT_TABLES_INC_ANALYSIS_REVIEW.md
**Priority:** HIGH - Data Quality & Technical Debt Resolution
**Status:** READY FOR IMPLEMENTATION

---

## Overview

This checklist addresses the outstanding issues identified in the implementation review:
- ❌ Issue 4: Missing actual_eth_amount in split_payout_que
- ⚠️ Issue 6: split_payout_hostpay.actual_eth_amount not populated
- ❌ Issue 3: Wrong PRIMARY KEY on split_payout_que
- ❌ Issue 7: No UNIQUE constraint on cn_api_id

**Total Implementation Time:** ~2 hours
**Phases:** 2 (Phase 1: Critical, Phase 2: Schema Design)

---

## Phase 1: Add actual_eth_amount Column & Fix Population (50 minutes)

**Goal:** Store ACTUAL ETH from NowPayments in split_payout_que and split_payout_hostpay for complete audit trail

**Status:** Not Started
**Priority:** HIGH (Data Quality)
**Risk:** Low (backward compatible)

---

### Task 1.1: Database Migration - Add actual_eth_amount to split_payout_que

**Estimated Time:** 10 minutes

#### Step 1.1.1: Create Migration Script

**File:** `/OCTOBER/10-26/scripts/add_actual_eth_to_split_payout_que.sql`

```sql
-- Migration: Add actual_eth_amount column to split_payout_que
-- Date: 2025-11-07
-- Purpose: Store ACTUAL ETH from NowPayments alongside ChangeNow estimates
-- Related: SPLIT_PAYOUT_TABLES_INC_ANALYSIS_REVIEW.md Issue 4

BEGIN;

-- Add column to split_payout_que
ALTER TABLE split_payout_que
ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;

-- Add validation constraint (non-negative values)
ALTER TABLE split_payout_que
ADD CONSTRAINT actual_eth_positive_que CHECK (actual_eth_amount >= 0);

-- Create index for performance (partial index on non-zero values)
CREATE INDEX IF NOT EXISTS idx_split_payout_que_actual_eth
ON split_payout_que(actual_eth_amount)
WHERE actual_eth_amount > 0;

-- Add comment for documentation
COMMENT ON COLUMN split_payout_que.actual_eth_amount IS
'ACTUAL ETH amount received from NowPayments outcome_amount (post network fees, pre TP fee)';

COMMIT;

-- Verification query
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'split_payout_que'
  AND column_name = 'actual_eth_amount';

-- Check constraint exists
SELECT constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_name = 'actual_eth_positive_que';
```

**Checklist:**
- [ ] Create migration file: `add_actual_eth_to_split_payout_que.sql`
- [ ] Review SQL syntax
- [ ] Verify NUMERIC(20,18) matches other tables (split_payout_request, split_payout_hostpay)

#### Step 1.1.2: Execute Migration

**Method:** Use observability MCP tool to execute SQL directly

```bash
# Connect to database and execute migration
# (This will be done via observability tool, not direct psql)
```

**Verification:**
- [ ] Column exists in split_payout_que
- [ ] Column type: NUMERIC(20,18)
- [ ] Default value: 0
- [ ] Constraint: actual_eth_positive_que exists
- [ ] Index: idx_split_payout_que_actual_eth exists

---

### Task 1.2: Code Update - GCSplit1 database_manager.py

**Estimated Time:** 15 minutes

#### Step 1.2.1: Update insert_split_payout_que() Method Signature

**File:** `/OCTOBER/10-26/GCSplit1-10-26/database_manager.py`
**Lines:** 219-236

**BEFORE:**
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
    type_: str = "direct"
) -> bool:
```

**AFTER:**
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
    actual_eth_amount: float = 0.0  # ✅ NEW: ACTUAL ETH from NowPayments
) -> bool:
```

**Checklist:**
- [ ] Add `actual_eth_amount: float = 0.0` parameter (default ensures backward compatibility)
- [ ] Verify parameter position (after `type_`, before return type)

#### Step 1.2.2: Update Method Docstring

**Lines:** 237-262

**BEFORE:**
```python
"""
Insert a new record into the split_payout_que table.

This table stores the ACTUAL CHANGENOW TRANSACTION details
(actual swap amounts including all fees).

Args:
    unique_id: The SAME unique_id from split_payout_request (for linking)
    cn_api_id: ChangeNow transaction ID (from API response)
    user_id: User ID
    closed_channel_id: Channel ID
    from_currency: Source currency (e.g., "eth")
    to_currency: Target currency (e.g., "link", "btc")
    from_network: Source network
    to_network: Target network
    from_amount: Actual from amount (from ChangeNow response)
    to_amount: Actual to amount (from ChangeNow response)
    payin_address: ChangeNow deposit address
    payout_address: Client's wallet address
    refund_address: Refund address (optional)
    flow: Exchange flow type
    type_: Exchange type

Returns:
    True if successful, False otherwise
"""
```

**AFTER:**
```python
"""
Insert a new record into the split_payout_que table.

This table stores the ACTUAL CHANGENOW TRANSACTION details
(actual swap amounts including all fees).

Args:
    unique_id: The SAME unique_id from split_payout_request (for linking)
    cn_api_id: ChangeNow transaction ID (from API response)
    user_id: User ID
    closed_channel_id: Channel ID
    from_currency: Source currency (e.g., "eth")
    to_currency: Target currency (e.g., "link", "btc")
    from_network: Source network
    to_network: Target network
    from_amount: Actual from amount (from ChangeNow response)
    to_amount: Actual to amount (from ChangeNow response)
    payin_address: ChangeNow deposit address
    payout_address: Client's wallet address
    refund_address: Refund address (optional)
    flow: Exchange flow type
    type_: Exchange type
    actual_eth_amount: ACTUAL ETH from NowPayments (default 0 for backward compat)

Returns:
    True if successful, False otherwise
"""
```

**Checklist:**
- [ ] Add actual_eth_amount parameter documentation
- [ ] Note backward compatibility (default 0)

#### Step 1.2.3: Update Print Statements

**Lines:** 266-273

**BEFORE:**
```python
print(f"📝 [DB_INSERT_QUE] Preparing split_payout_que insertion")
print(f"🆔 [DB_INSERT_QUE] Unique ID: {unique_id} (linking to request)")
print(f"🆔 [DB_INSERT_QUE] ChangeNow API ID: {cn_api_id}")
print(f"👤 [DB_INSERT_QUE] User ID: {user_id}")
print(f"🏦 [DB_INSERT_QUE] Payin: {payin_address}")
print(f"🏦 [DB_INSERT_QUE] Payout: {payout_address}")
print(f"💰 [DB_INSERT_QUE] From: {from_amount} {from_currency.upper()}")
print(f"💰 [DB_INSERT_QUE] To: {to_amount} {to_currency.upper()}")
```

**AFTER:**
```python
print(f"📝 [DB_INSERT_QUE] Preparing split_payout_que insertion")
print(f"🆔 [DB_INSERT_QUE] Unique ID: {unique_id} (linking to request)")
print(f"🆔 [DB_INSERT_QUE] ChangeNow API ID: {cn_api_id}")
print(f"👤 [DB_INSERT_QUE] User ID: {user_id}")
print(f"🏦 [DB_INSERT_QUE] Payin: {payin_address}")
print(f"🏦 [DB_INSERT_QUE] Payout: {payout_address}")
print(f"💰 [DB_INSERT_QUE] From: {from_amount} {from_currency.upper()}")
print(f"💰 [DB_INSERT_QUE] To: {to_amount} {to_currency.upper()}")
print(f"💎 [DB_INSERT_QUE] ACTUAL ETH: {actual_eth_amount}")  # ✅ NEW LOG
```

**Checklist:**
- [ ] Add log for actual_eth_amount
- [ ] Use 💎 emoji for consistency with other services

#### Step 1.2.4: Update INSERT Statement

**Lines:** 275-287

**BEFORE:**
```python
# SQL INSERT statement
insert_query = """
    INSERT INTO split_payout_que (
        unique_id, cn_api_id, user_id, closed_channel_id,
        from_currency, to_currency, from_network, to_network,
        from_amount, to_amount, payin_address, payout_address, refund_address,
        flow, type
    ) VALUES (
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s
    )
"""
```

**AFTER:**
```python
# SQL INSERT statement
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

**Checklist:**
- [ ] Add `actual_eth_amount` to column list
- [ ] Add `%s` placeholder to VALUES list
- [ ] Verify column count matches placeholder count (16 columns, 16 placeholders)

#### Step 1.2.5: Update Params Tuple

**Lines:** 290-296

**BEFORE:**
```python
params = (
    unique_id, cn_api_id, user_id, closed_channel_id,
    from_currency.upper(), to_currency.upper(),
    from_network.upper(), to_network.upper(),
    from_amount, to_amount,
    payin_address, payout_address, refund_address,
    flow, type_
)
```

**AFTER:**
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

**Checklist:**
- [ ] Add `actual_eth_amount` to params tuple
- [ ] Verify tuple order matches INSERT column order
- [ ] Verify param count matches placeholder count (16 values)

---

### Task 1.3: Code Update - GCSplit1 tps1-10-26.py

**Estimated Time:** 10 minutes

#### Step 1.3.1: Update Endpoint 3 insert_split_payout_que Call

**File:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`
**Lines:** 732-744

**BEFORE:**
```python
que_success = database_manager.insert_split_payout_que(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    from_currency=from_currency,
    to_currency=to_currency,
    from_network=from_network,
    to_network=to_network,
    from_amount=from_amount,
    to_amount=to_amount,
    payin_address=payin_address,
    payout_address=payout_address,
```

**AFTER:**
```python
que_success = database_manager.insert_split_payout_que(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    from_currency=from_currency,
    to_currency=to_currency,
    from_network=from_network,
    to_network=to_network,
    from_amount=from_amount,
    to_amount=to_amount,
    payin_address=payin_address,
    payout_address=payout_address,
    refund_address=refund_address,
    flow=flow,
    type_=type_,
    actual_eth_amount=actual_eth_amount  # ✅ NEW: Pass ACTUAL ETH
```

**Note:** The `actual_eth_amount` variable should already exist in endpoint_3 scope (extracted from token at line 646).

**Checklist:**
- [ ] Add `actual_eth_amount=actual_eth_amount` parameter
- [ ] Verify variable `actual_eth_amount` exists in scope (line 646)
- [ ] Add comment explaining this is ACTUAL ETH from NowPayments

---

### Task 1.4: Code Update - GCHostPay1 database_manager.py

**Estimated Time:** 15 minutes

#### Step 1.4.1: Update insert_hostpay_transaction() Method Signature

**File:** `/OCTOBER/10-26/GCHostPay1-10-26/database_manager.py`
**Lines:** 79-82

**BEFORE:**
```python
def insert_hostpay_transaction(self, unique_id: str, cn_api_id: str, from_currency: str,
                               from_network: str, from_amount: float, payin_address: str,
                               is_complete: bool = True, tx_hash: str = None, tx_status: str = None,
                               gas_used: int = None, block_number: int = None) -> bool:
```

**AFTER:**
```python
def insert_hostpay_transaction(self, unique_id: str, cn_api_id: str, from_currency: str,
                               from_network: str, from_amount: float, payin_address: str,
                               is_complete: bool = True, tx_hash: str = None, tx_status: str = None,
                               gas_used: int = None, block_number: int = None,
                               actual_eth_amount: float = 0.0) -> bool:  # ✅ NEW
```

**Checklist:**
- [ ] Add `actual_eth_amount: float = 0.0` parameter
- [ ] Default value ensures backward compatibility

#### Step 1.4.2: Update Method Docstring

**Lines:** 83-101

**BEFORE:**
```python
"""
Insert a completed host payment transaction into split_payout_hostpay table.

Args:
    unique_id: Database linking ID (16 chars)
    cn_api_id: ChangeNow transaction ID
    from_currency: Source currency (e.g., "eth")
    from_network: Source network (e.g., "eth")
    from_amount: Amount sent
    payin_address: ChangeNow deposit address
    is_complete: Payment completion status (default: True)
    tx_hash: Ethereum transaction hash (optional)
    tx_status: Transaction status ("success" or "failed") (optional)
    gas_used: Gas used by the transaction (optional)
    block_number: Block number where transaction was mined (optional)

Returns:
    True if successful, False otherwise
"""
```

**AFTER:**
```python
"""
Insert a completed host payment transaction into split_payout_hostpay table.

Args:
    unique_id: Database linking ID (16 chars)
    cn_api_id: ChangeNow transaction ID
    from_currency: Source currency (e.g., "eth")
    from_network: Source network (e.g., "eth")
    from_amount: Amount sent (from ChangeNow estimate or actual payment)
    payin_address: ChangeNow deposit address
    is_complete: Payment completion status (default: True)
    tx_hash: Ethereum transaction hash (optional)
    tx_status: Transaction status ("success" or "failed") (optional)
    gas_used: Gas used by the transaction (optional)
    block_number: Block number where transaction was mined (optional)
    actual_eth_amount: ACTUAL ETH from NowPayments (default 0 for backward compat)

Returns:
    True if successful, False otherwise
"""
```

**Checklist:**
- [ ] Add actual_eth_amount parameter documentation
- [ ] Clarify difference between from_amount (estimate) and actual_eth_amount (actual)

#### Step 1.4.3: Update Print Statements

**Lines:** 137-149

**BEFORE:**
```python
# Log exact values being inserted for debugging
print(f"📋 [HOSTPAY_DB] Insert parameters:")
print(f"   unique_id: {unique_id} (len: {len(unique_id)})")
print(f"   cn_api_id: {cn_api_id} (len: {len(cn_api_id)})")
print(f"   from_currency: {from_currency.upper()}")
print(f"   from_network: {from_network.upper()}")
print(f"   from_amount: {from_amount_rounded} (original: {from_amount})")
print(f"   payin_address: {payin_address} (len: {len(payin_address)})")
print(f"   is_complete: {is_complete}")
print(f"   tx_hash: {tx_hash}")
print(f"   tx_status: {tx_status}")
print(f"   gas_used: {gas_used}")
print(f"   block_number: {block_number}")
```

**AFTER:**
```python
# Log exact values being inserted for debugging
print(f"📋 [HOSTPAY_DB] Insert parameters:")
print(f"   unique_id: {unique_id} (len: {len(unique_id)})")
print(f"   cn_api_id: {cn_api_id} (len: {len(cn_api_id)})")
print(f"   from_currency: {from_currency.upper()}")
print(f"   from_network: {from_network.upper()}")
print(f"   from_amount: {from_amount_rounded} (original: {from_amount})")
print(f"   actual_eth_amount: {actual_eth_amount}")  # ✅ NEW LOG
print(f"   payin_address: {payin_address} (len: {len(payin_address)})")
print(f"   is_complete: {is_complete}")
print(f"   tx_hash: {tx_hash}")
print(f"   tx_status: {tx_status}")
print(f"   gas_used: {gas_used}")
print(f"   block_number: {block_number}")
```

**Checklist:**
- [ ] Add log for actual_eth_amount
- [ ] Position after from_amount for logical grouping

#### Step 1.4.4: Update INSERT Statement

**Lines:** 130-135

**BEFORE:**
```python
insert_query = """
    INSERT INTO split_payout_hostpay
    (unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address, is_complete, tx_hash, tx_status, gas_used, block_number)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
insert_params = (unique_id, cn_api_id, from_currency.upper(), from_network.upper(), from_amount_rounded, payin_address, is_complete, tx_hash, tx_status, gas_used, block_number)
```

**AFTER:**
```python
insert_query = """
    INSERT INTO split_payout_hostpay
    (unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address, is_complete, tx_hash, tx_status, gas_used, block_number, actual_eth_amount)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
insert_params = (unique_id, cn_api_id, from_currency.upper(), from_network.upper(), from_amount_rounded, payin_address, is_complete, tx_hash, tx_status, gas_used, block_number, actual_eth_amount)
```

**Checklist:**
- [ ] Add `actual_eth_amount` to column list
- [ ] Add `%s` placeholder to VALUES list
- [ ] Add `actual_eth_amount` to insert_params tuple
- [ ] Verify column count matches placeholder count (12 columns, 12 placeholders)

---

### Task 1.5: Find and Update insert_hostpay_transaction Caller

**Estimated Time:** 10 minutes (includes research)

#### Step 1.5.1: Locate Caller

**Search Strategy:**
```bash
# Search GCHostPay1 for calls to insert_hostpay_transaction
grep -rn "insert_hostpay_transaction" /OCTOBER/10-26/GCHostPay1-10-26/*.py

# Search GCHostPay3 for calls to insert_hostpay_transaction
grep -rn "insert_hostpay_transaction" /OCTOBER/10-26/GCHostPay3-10-26/*.py
```

**Expected Location:** GCHostPay3-10-26/tphp3-10-26.py (payment execution endpoint)

**Checklist:**
- [ ] Identify which service calls `insert_hostpay_transaction`
- [ ] Identify exact file and line number
- [ ] Verify `actual_eth_amount` variable is available in scope

#### Step 1.5.2: Update Caller to Pass actual_eth_amount

**Expected File:** `/OCTOBER/10-26/GCHostPay3-10-26/tphp3-10-26.py`
**Expected Context:** After successful ETH payment execution

**BEFORE (example):**
```python
database_manager.insert_hostpay_transaction(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,
    from_network=from_network,
    from_amount=payment_amount,
    payin_address=payin_address,
    is_complete=True,
    tx_hash=tx_hash,
    tx_status="success",
    gas_used=gas_used,
    block_number=block_number
)
```

**AFTER:**
```python
database_manager.insert_hostpay_transaction(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,
    from_network=from_network,
    from_amount=payment_amount,
    payin_address=payin_address,
    is_complete=True,
    tx_hash=tx_hash,
    tx_status="success",
    gas_used=gas_used,
    block_number=block_number,
    actual_eth_amount=actual_eth_amount  # ✅ NEW: Pass ACTUAL ETH
)
```

**Note:** Based on review, GCHostPay3 already extracts `actual_eth_amount` from token (line 163).

**Checklist:**
- [ ] Locate caller file and line number
- [ ] Verify `actual_eth_amount` variable exists in scope
- [ ] Add `actual_eth_amount=actual_eth_amount` parameter to call
- [ ] Add comment explaining this is ACTUAL ETH from NowPayments

---

### Phase 1 Testing & Deployment

**Estimated Time:** 20 minutes (includes testing)

#### Test 1.1: Local Testing (Optional but Recommended)

**Goal:** Verify code compiles and basic logic works

```bash
# Build Docker image locally
cd /OCTOBER/10-26/GCSplit1-10-26
docker build -t gcr.io/telepay-459221/gcsplit1-10-26:actual-eth-que-test .

# Check for syntax errors (build should succeed)
echo "Build result: $?"

# Repeat for GCHostPay1
cd /OCTOBER/10-26/GCHostPay1-10-26
docker build -t gcr.io/telepay-459221/gchostpay1-10-26:actual-eth-hostpay-test .

# Repeat for GCHostPay3 (if modified)
cd /OCTOBER/10-26/GCHostPay3-10-26
docker build -t gcr.io/telepay-459221/gchostpay3-10-26:actual-eth-hostpay-test .
```

**Checklist:**
- [ ] GCSplit1-10-26 builds successfully
- [ ] GCHostPay1-10-26 builds successfully
- [ ] GCHostPay3-10-26 builds successfully (if modified)
- [ ] No syntax errors in any service

#### Test 1.2: Deployment - GCSplit1

**Service:** gcsplit1-10-26

```bash
cd /OCTOBER/10-26/GCSplit1-10-26

# Build and push
docker build -t gcr.io/telepay-459221/gcsplit1-10-26:actual-eth-que-fix .
docker push gcr.io/telepay-459221/gcsplit1-10-26:actual-eth-que-fix

# Deploy
gcloud run deploy gcsplit1-10-26 \
  --image gcr.io/telepay-459221/gcsplit1-10-26:actual-eth-que-fix \
  --region us-central1 \
  --platform managed

# Verify deployment
gcloud run services describe gcsplit1-10-26 --region=us-central1 --format="value(status.url)"
```

**Checklist:**
- [ ] Build successful
- [ ] Push to GCR successful
- [ ] Deploy to Cloud Run successful
- [ ] Service healthy (all 3 components: True;True;True)
- [ ] 100% traffic to new revision

#### Test 1.3: Deployment - GCHostPay1

**Service:** gchostpay1-10-26

```bash
cd /OCTOBER/10-26/GCHostPay1-10-26

# Build and push
docker build -t gcr.io/telepay-459221/gchostpay1-10-26:actual-eth-hostpay-fix .
docker push gcr.io/telepay-459221/gchostpay1-10-26:actual-eth-hostpay-fix

# Deploy
gcloud run deploy gchostpay1-10-26 \
  --image gcr.io/telepay-459221/gchostpay1-10-26:actual-eth-hostpay-fix \
  --region us-central1 \
  --platform managed

# Verify deployment
gcloud run services describe gchostpay1-10-26 --region=us-central1 --format="value(status.url)"
```

**Checklist:**
- [ ] Build successful
- [ ] Push to GCR successful
- [ ] Deploy to Cloud Run successful
- [ ] Service healthy
- [ ] 100% traffic to new revision

#### Test 1.4: Deployment - GCHostPay3 (if modified)

**Service:** gchostpay3-10-26

```bash
cd /OCTOBER/10-26/GCHostPay3-10-26

# Build and push
docker build -t gcr.io/telepay-459221/gchostpay3-10-26:actual-eth-hostpay-fix .
docker push gcr.io/telepay-459221/gchostpay3-10-26:actual-eth-hostpay-fix

# Deploy
gcloud run deploy gchostpay3-10-26 \
  --image gcr.io/telepay-459221/gchostpay3-10-26:actual-eth-hostpay-fix \
  --region us-central1 \
  --platform managed

# Verify deployment
gcloud run services describe gchostpay3-10-26 --region=us-central1 --format="value(status.url)"
```

**Checklist:**
- [ ] Build successful (if modified)
- [ ] Push to GCR successful (if modified)
- [ ] Deploy to Cloud Run successful (if modified)
- [ ] Service healthy (if modified)

#### Test 1.5: Production Validation

**Goal:** Verify actual_eth_amount is being stored correctly

**Test Case 1: Trigger Instant Payout Test Transaction**

```bash
# Monitor logs during test transaction
gcloud logging read \
  "resource.type=cloud_run_revision AND
   (resource.labels.service_name=gcsplit1-10-26 OR
    resource.labels.service_name=gchostpay1-10-26 OR
    resource.labels.service_name=gchostpay3-10-26) AND
   textPayload:\"ACTUAL ETH\"" \
  --limit=20 \
  --format=json
```

**Expected Log Output:**

From GCSplit1 endpoint_2:
```
💎 [ENDPOINT_2] ACTUAL ETH (from NowPayments): 0.0009768
💾 [ENDPOINT_2] Inserting into split_payout_request
   💎 ACTUAL ETH: 0.0009768
```

From GCSplit1 endpoint_3:
```
💎 [ENDPOINT_3] ACTUAL ETH (from NowPayments): 0.0009768 ETH
💰 [DB_INSERT_QUE] ACTUAL ETH: 0.0009768
✅ [DB_INSERT_QUE] Successfully inserted into split_payout_que
```

From GCHostPay3:
```
💎 [ENDPOINT] ACTUAL: 0.0009768 ETH (from NowPayments)
💰 [ENDPOINT] PAYMENT AMOUNT: 0.0009768 ETH
```

From GCHostPay1 (database insert):
```
   actual_eth_amount: 0.0009768
✅ [HOSTPAY_DB] Insert successful (1 row)
```

**Checklist:**
- [ ] GCSplit1 logs show ACTUAL ETH passed to insert_split_payout_que
- [ ] GCSplit1 logs show successful insertion into split_payout_que
- [ ] GCHostPay3 logs show ACTUAL ETH extracted from token
- [ ] GCHostPay1 logs show actual_eth_amount parameter passed
- [ ] No errors in any service

**Test Case 2: Database Verification**

```sql
-- Query most recent split_payout_que record
SELECT
    unique_id,
    cn_api_id,
    from_currency,
    from_amount,
    actual_eth_amount,
    created_at
FROM split_payout_que
ORDER BY created_at DESC
LIMIT 1;

-- Expected: actual_eth_amount should be NON-ZERO (e.g., 0.000976800000000000)

-- Query most recent split_payout_hostpay record
SELECT
    unique_id,
    cn_api_id,
    from_currency,
    from_amount,
    actual_eth_amount,
    created_at
FROM split_payout_hostpay
ORDER BY created_at DESC
LIMIT 1;

-- Expected: actual_eth_amount should be NON-ZERO (e.g., 0.000976800000000000)
```

**Checklist:**
- [ ] split_payout_que.actual_eth_amount > 0 (not 0 or 0E-18)
- [ ] split_payout_hostpay.actual_eth_amount > 0 (not 0 or 0E-18)
- [ ] actual_eth_amount matches across split_payout_request, split_payout_que, split_payout_hostpay

**Test Case 3: Compare Request vs Que vs Hostpay**

```sql
-- Comprehensive comparison query
SELECT
    r.unique_id,
    r.actual_eth_amount as request_actual_eth,
    q.cn_api_id,
    q.actual_eth_amount as que_actual_eth,
    h.actual_eth_amount as hostpay_actual_eth,
    ABS(r.actual_eth_amount - q.actual_eth_amount) as request_que_diff,
    ABS(r.actual_eth_amount - h.actual_eth_amount) as request_hostpay_diff,
    r.created_at as request_created,
    q.created_at as que_created,
    h.created_at as hostpay_created
FROM split_payout_request r
JOIN split_payout_que q ON r.unique_id = q.unique_id
JOIN split_payout_hostpay h ON q.cn_api_id = h.cn_api_id
WHERE r.created_at > NOW() - INTERVAL '1 hour'
ORDER BY r.created_at DESC
LIMIT 10;

-- Expected: All actual_eth_amount values should match (diff < 0.00000001)
```

**Success Criteria:**
- [ ] All three tables show same actual_eth_amount value
- [ ] Difference < 0.00000001 (accounting for floating point precision)
- [ ] No NULL or 0E-18 values

---

## Phase 1 Rollback Plan

**If Phase 1 deployment causes issues:**

### Rollback Code Changes

**GCSplit1:**
```bash
# Revert to previous revision
gcloud run services update-traffic gcsplit1-10-26 \
  --to-revisions=gcsplit1-10-26-00021-xxx=100 \
  --region=us-central1
```

**GCHostPay1:**
```bash
# Revert to previous revision
gcloud run services update-traffic gchostpay1-10-26 \
  --to-revisions=gchostpay1-10-26-00xxx-xxx=100 \
  --region=us-central1
```

**GCHostPay3 (if modified):**
```bash
# Revert to previous revision
gcloud run services update-traffic gchostpay3-10-26 \
  --to-revisions=gchostpay3-10-26-00xxx-xxx=100 \
  --region=us-central1
```

### Rollback Database Migration

**Only if necessary (should not be needed - column is backward compatible):**

```sql
-- Remove column from split_payout_que
BEGIN;

ALTER TABLE split_payout_que DROP CONSTRAINT actual_eth_positive_que;
DROP INDEX IF EXISTS idx_split_payout_que_actual_eth;
ALTER TABLE split_payout_que DROP COLUMN actual_eth_amount;

COMMIT;
```

**Note:** Database rollback should be **last resort** - column with DEFAULT 0 is backward compatible.

**Checklist:**
- [ ] Identify which service(s) need rollback
- [ ] Execute rollback commands
- [ ] Verify services return to stable state
- [ ] Document rollback reason for post-mortem

---

## Phase 2: Schema Correction - Change Primary Key (1 hour)

**Goal:** Fix underlying schema design flaw to support 1-to-many relationship

**Status:** Not Started
**Priority:** MEDIUM (Technical Debt)
**Risk:** Medium (schema change requires careful testing)

---

### Task 2.1: Database Migration - Change Primary Key

**Estimated Time:** 20 minutes

#### Step 2.1.1: Create Migration Script

**File:** `/OCTOBER/10-26/scripts/fix_split_payout_que_primary_key.sql`

```sql
-- Migration: Change split_payout_que PRIMARY KEY from unique_id to cn_api_id
-- Date: 2025-11-07
-- Purpose: Support 1-to-many relationship (multiple ChangeNow attempts per payment request)
-- Related: SPLIT_PAYOUT_TABLES_INC_ANALYSIS_REVIEW.md Issue 3

BEGIN;

-- ============================================================================
-- CRITICAL: This migration changes the PRIMARY KEY structure
-- Impact: Enables multiple ChangeNow transactions for same payment request
-- ============================================================================

-- Step 1: Drop existing primary key constraint
-- Note: This will also drop the automatic unique index on unique_id
ALTER TABLE split_payout_que DROP CONSTRAINT split_payout_que_pkey;

-- Step 2: Add new primary key on cn_api_id
-- ChangeNow transaction ID is globally unique and never reused
ALTER TABLE split_payout_que ADD PRIMARY KEY (cn_api_id);

-- Step 3: Add index on unique_id for 1-to-many lookups
-- This enables efficient queries like "find all ChangeNow attempts for payment X"
CREATE INDEX IF NOT EXISTS idx_split_payout_que_unique_id
ON split_payout_que(unique_id);

-- Step 4: Add unique constraint on cn_api_id (belt and suspenders)
-- PRIMARY KEY already enforces uniqueness, but explicit constraint improves clarity
ALTER TABLE split_payout_que ADD CONSTRAINT unique_cn_api_id UNIQUE (cn_api_id);

-- Step 5: Add comment for documentation
COMMENT ON COLUMN split_payout_que.cn_api_id IS
'ChangeNow transaction ID - PRIMARY KEY. Each ChangeNow attempt gets unique cn_api_id.';

COMMENT ON COLUMN split_payout_que.unique_id IS
'Links to split_payout_request. Multiple ChangeNow attempts can share same unique_id (1-to-many).';

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Verify primary key
SELECT
    tc.table_name,
    kcu.column_name,
    tc.constraint_type
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_name = 'split_payout_que'
  AND tc.constraint_type = 'PRIMARY KEY';

-- Expected: cn_api_id (not unique_id)

-- Verify unique constraint
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'split_payout_que'
  AND constraint_type = 'UNIQUE';

-- Expected: unique_cn_api_id

-- Verify index on unique_id
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'split_payout_que'
  AND indexname = 'idx_split_payout_que_unique_id';

-- Expected: Index exists on unique_id column
```

**Checklist:**
- [ ] Create migration file: `fix_split_payout_que_primary_key.sql`
- [ ] Review SQL syntax
- [ ] Verify DROP CONSTRAINT uses correct constraint name
- [ ] Verify all steps have comments explaining purpose

#### Step 2.1.2: Pre-Migration Verification

**Check Current State:**

```sql
-- Check current primary key
SELECT
    tc.constraint_name,
    kcu.column_name,
    tc.constraint_type
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_name = 'split_payout_que'
  AND tc.constraint_type = 'PRIMARY KEY';

-- Expected: split_payout_que_pkey on unique_id

-- Check for duplicate cn_api_id values (should be none)
SELECT cn_api_id, COUNT(*)
FROM split_payout_que
GROUP BY cn_api_id
HAVING COUNT(*) > 1;

-- Expected: 0 rows (no duplicates)
```

**Checklist:**
- [ ] Current PRIMARY KEY is unique_id
- [ ] No duplicate cn_api_id values exist
- [ ] Constraint name is `split_payout_que_pkey`

#### Step 2.1.3: Execute Migration

**Method:** Use observability MCP tool or direct database connection

```bash
# Execute migration via psql
# (This will be done via observability tool in practice)
```

**Checklist:**
- [ ] Migration executed successfully
- [ ] No errors during execution
- [ ] Transaction committed

#### Step 2.1.4: Post-Migration Verification

**Check New State:**

```sql
-- Verify primary key changed
SELECT
    tc.table_name,
    kcu.column_name,
    tc.constraint_type
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_name = 'split_payout_que'
  AND tc.constraint_type = 'PRIMARY KEY';

-- Expected: PRIMARY KEY on cn_api_id

-- Verify unique constraint exists
SELECT constraint_name
FROM information_schema.table_constraints
WHERE table_name = 'split_payout_que'
  AND constraint_name = 'unique_cn_api_id';

-- Expected: unique_cn_api_id

-- Verify index on unique_id exists
SELECT indexname
FROM pg_indexes
WHERE tablename = 'split_payout_que'
  AND indexname = 'idx_split_payout_que_unique_id';

-- Expected: idx_split_payout_que_unique_id

-- Test inserting duplicate unique_id (should succeed now)
-- (Don't actually execute this in production - just verify schema allows it)
```

**Success Criteria:**
- [ ] PRIMARY KEY is now cn_api_id
- [ ] UNIQUE constraint exists on cn_api_id
- [ ] INDEX exists on unique_id
- [ ] Schema allows multiple records with same unique_id

---

### Task 2.2: Update Code Documentation

**Estimated Time:** 10 minutes

#### Step 2.2.1: Update GCSplit1 database_manager.py Comments

**File:** `/OCTOBER/10-26/GCSplit1-10-26/database_manager.py`
**Lines:** 237-262

**Update docstring to reflect new relationship:**

```python
"""
Insert a new record into the split_payout_que table.

This table stores the ACTUAL CHANGENOW TRANSACTION details
(actual swap amounts including all fees).

RELATIONSHIP: 1-to-many with split_payout_request
- One payment request (unique_id) can have multiple ChangeNow attempts (cn_api_id)
- PRIMARY KEY: cn_api_id (unique per ChangeNow transaction)
- FOREIGN KEY: unique_id (links to split_payout_request)

Args:
    unique_id: Links to split_payout_request (allows 1-to-many)
    cn_api_id: ChangeNow transaction ID (PRIMARY KEY)
    # ... rest of args
```

**Checklist:**
- [ ] Add relationship documentation
- [ ] Clarify PRIMARY KEY is cn_api_id
- [ ] Clarify unique_id is FOREIGN KEY (conceptually)

#### Step 2.2.2: Update Idempotency Check Comments

**File:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`
**Lines:** 695-727

**Update comments to reflect new behavior:**

```python
# ============================================================================
# CRITICAL: Idempotency Check - Prevent Duplicate ChangeNow Transactions
# ============================================================================
# After Phase 2 migration:
# - PRIMARY KEY is cn_api_id (not unique_id)
# - Multiple ChangeNow attempts can exist for same payment request
# - This check prevents duplicate cn_api_id insertions
# - Same unique_id with different cn_api_id is ALLOWED (1-to-many)
# ============================================================================
```

**Checklist:**
- [ ] Update comments to reflect new PRIMARY KEY
- [ ] Clarify 1-to-many relationship is now supported
- [ ] Explain idempotency check prevents duplicate cn_api_id

---

### Task 2.3: Testing Phase 2

**Estimated Time:** 30 minutes

#### Test 2.1: Unit Test - Verify 1-to-Many Insertion

**Goal:** Verify multiple ChangeNow transactions can be inserted for same payment request

**Test Scenario:**
1. Create test payment request with unique_id = TEST_UNIQUE_001
2. Insert first ChangeNow attempt: cn_api_id = TEST_CN_001
3. Insert second ChangeNow attempt: cn_api_id = TEST_CN_002 (SAME unique_id)
4. Verify both records exist in split_payout_que

**SQL Test:**

```sql
-- Test 1: Insert first ChangeNow attempt
INSERT INTO split_payout_que (
    unique_id, cn_api_id, user_id, closed_channel_id,
    from_currency, to_currency, from_network, to_network,
    from_amount, to_amount, payin_address, payout_address,
    refund_address, flow, type, actual_eth_amount
) VALUES (
    'TEST_UNIQUE_001', 'TEST_CN_001', 12345, '1234567890',
    'ETH', 'USDT', 'ETH', 'ETH',
    0.001, 10.0, '0xTEST_PAYIN_1', '0xTEST_PAYOUT',
    '', 'standard', 'direct', 0.001
);

-- Expected: Success

-- Test 2: Insert second ChangeNow attempt (SAME unique_id, different cn_api_id)
INSERT INTO split_payout_que (
    unique_id, cn_api_id, user_id, closed_channel_id,
    from_currency, to_currency, from_network, to_network,
    from_amount, to_amount, payin_address, payout_address,
    refund_address, flow, type, actual_eth_amount
) VALUES (
    'TEST_UNIQUE_001', 'TEST_CN_002', 12345, '1234567890',
    'ETH', 'USDT', 'ETH', 'ETH',
    0.001, 10.0, '0xTEST_PAYIN_2', '0xTEST_PAYOUT',
    '', 'standard', 'direct', 0.001
);

-- Expected: Success (BEFORE Phase 2: Would fail with duplicate key error)

-- Test 3: Query both records
SELECT unique_id, cn_api_id, from_amount, created_at
FROM split_payout_que
WHERE unique_id = 'TEST_UNIQUE_001'
ORDER BY created_at;

-- Expected: 2 rows returned

-- Test 4: Try to insert duplicate cn_api_id (should fail)
INSERT INTO split_payout_que (
    unique_id, cn_api_id, user_id, closed_channel_id,
    from_currency, to_currency, from_network, to_network,
    from_amount, to_amount, payin_address, payout_address,
    refund_address, flow, type, actual_eth_amount
) VALUES (
    'DIFFERENT_UNIQUE', 'TEST_CN_001', 12345, '1234567890',
    'ETH', 'USDT', 'ETH', 'ETH',
    0.001, 10.0, '0xTEST_PAYIN_3', '0xTEST_PAYOUT',
    '', 'standard', 'direct', 0.001
);

-- Expected: Error (duplicate key violation on PRIMARY KEY cn_api_id)

-- Cleanup
DELETE FROM split_payout_que WHERE unique_id = 'TEST_UNIQUE_001';
DELETE FROM split_payout_que WHERE cn_api_id = 'TEST_CN_001' OR cn_api_id = 'TEST_CN_002';
```

**Checklist:**
- [ ] First insertion succeeds
- [ ] Second insertion succeeds (same unique_id, different cn_api_id)
- [ ] Both records exist in database
- [ ] Duplicate cn_api_id insertion fails (PRIMARY KEY enforced)
- [ ] Test data cleaned up

#### Test 2.2: Integration Test - Cloud Tasks Retry Scenario

**Goal:** Simulate real Cloud Tasks retry and verify both ChangeNow attempts are tracked

**Test Steps:**

1. Trigger test payment through full flow
2. Manually create second ChangeNow transaction (simulate retry)
3. Verify both transactions tracked in split_payout_que

**Manual Test (Production):**

```bash
# Step 1: Trigger test payment (instant payout)
# (Use test NowPayments webhook or manual trigger)

# Step 2: Monitor first ChangeNow attempt
gcloud logging read \
  "resource.type=cloud_run_revision AND
   resource.labels.service_name=gcsplit1-10-26 AND
   textPayload:\"DB_INSERT_QUE\"" \
  --limit=5 \
  --format=json

# Note the unique_id and cn_api_id

# Step 3: Query database for first attempt
```

```sql
SELECT unique_id, cn_api_id, from_amount, to_amount, created_at
FROM split_payout_que
WHERE unique_id = 'ACTUAL_UNIQUE_ID_FROM_LOGS'
ORDER BY created_at;

-- Expected: 1 row
```

```bash
# Step 4: Manually trigger Cloud Tasks retry
# (This would normally happen automatically, but can be simulated)
```

```sql
-- Step 5: After retry, query again
SELECT unique_id, cn_api_id, from_amount, to_amount, created_at
FROM split_payout_que
WHERE unique_id = 'ACTUAL_UNIQUE_ID_FROM_LOGS'
ORDER BY created_at;

-- Expected: 2 rows (if retry created new ChangeNow transaction)
-- OR: 1 row (if idempotency check prevented duplicate)
```

**Success Criteria:**
- [ ] If retry creates new ChangeNow transaction: Both tracked in split_payout_que
- [ ] If idempotency check triggers: Only first attempt tracked (expected behavior)
- [ ] No duplicate key errors in logs
- [ ] System remains stable

#### Test 2.3: Query Performance Test

**Goal:** Verify index on unique_id provides good performance for 1-to-many lookups

```sql
-- Query all ChangeNow attempts for a payment request
EXPLAIN ANALYZE
SELECT cn_api_id, from_amount, to_amount, created_at
FROM split_payout_que
WHERE unique_id = 'WVGGE301D98KABZ8'
ORDER BY created_at;

-- Expected: Index scan on idx_split_payout_que_unique_id
-- Expected: Query time < 10ms
```

**Success Criteria:**
- [ ] Query uses index scan (not sequential scan)
- [ ] Query execution time < 10ms
- [ ] No performance degradation

---

### Phase 2 Production Validation

**Estimated Time:** 10 minutes

#### Validation 2.1: Check for Multiple Attempts

**Query:** Find payment requests with multiple ChangeNow attempts

```sql
-- Find unique_ids with multiple ChangeNow transactions (after Phase 2)
SELECT
    unique_id,
    COUNT(*) as attempt_count,
    STRING_AGG(cn_api_id, ', ' ORDER BY created_at) as cn_api_ids,
    MIN(created_at) as first_attempt,
    MAX(created_at) as last_attempt,
    EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) as seconds_between
FROM split_payout_que
GROUP BY unique_id
HAVING COUNT(*) > 1
ORDER BY attempt_count DESC, first_attempt DESC
LIMIT 20;

-- Expected: May return 0 rows initially (no retries yet)
-- After retries occur: Will show 1-to-many relationships
```

**Checklist:**
- [ ] Query executes successfully
- [ ] No errors
- [ ] Results show 1-to-many relationship (if retries occurred)

#### Validation 2.2: Audit Trail Verification

**Query:** Verify complete audit trail exists

```sql
-- Complete audit trail for a specific payment
WITH payment_flow AS (
    SELECT
        r.unique_id,
        r.user_id,
        r.from_amount as request_from_amount,
        r.to_amount as request_to_amount,
        r.actual_eth_amount as request_actual_eth,
        r.created_at as request_created
    FROM split_payout_request r
    WHERE r.unique_id = 'WVGGE301D98KABZ8'
)
SELECT
    pf.unique_id,
    pf.request_from_amount,
    pf.request_actual_eth,
    q.cn_api_id,
    q.from_amount as que_from_amount,
    q.actual_eth_amount as que_actual_eth,
    h.from_amount as hostpay_from_amount,
    h.actual_eth_amount as hostpay_actual_eth,
    h.tx_hash,
    h.tx_status,
    pf.request_created,
    q.created_at as que_created,
    h.created_at as hostpay_created
FROM payment_flow pf
LEFT JOIN split_payout_que q ON pf.unique_id = q.unique_id
LEFT JOIN split_payout_hostpay h ON q.cn_api_id = h.cn_api_id
ORDER BY q.created_at;

-- Expected: Complete flow visible across all 3 tables
```

**Success Criteria:**
- [ ] All ChangeNow attempts visible
- [ ] actual_eth_amount populated in all tables
- [ ] Complete audit trail from request → que → hostpay
- [ ] Timestamps show logical progression

---

## Phase 2 Rollback Plan

**If Phase 2 migration causes critical issues:**

### Rollback Database Migration

```sql
-- Rollback: Restore original PRIMARY KEY on unique_id
BEGIN;

-- Drop new constraints and indexes
ALTER TABLE split_payout_que DROP CONSTRAINT unique_cn_api_id;
DROP INDEX IF EXISTS idx_split_payout_que_unique_id;

-- Remove PRIMARY KEY on cn_api_id
ALTER TABLE split_payout_que DROP CONSTRAINT split_payout_que_pkey;

-- Restore PRIMARY KEY on unique_id
-- WARNING: This will fail if multiple records exist with same unique_id
-- In that case, keep newest record and delete older ones
ALTER TABLE split_payout_que ADD PRIMARY KEY (unique_id);

COMMIT;
```

**CRITICAL:** If rollback fails due to duplicate unique_id values:

```sql
-- Find duplicates
SELECT unique_id, COUNT(*), STRING_AGG(cn_api_id::text, ', ') as cn_api_ids
FROM split_payout_que
GROUP BY unique_id
HAVING COUNT(*) > 1;

-- For each duplicate unique_id, keep only the NEWEST record
-- Delete older records manually:
DELETE FROM split_payout_que
WHERE cn_api_id IN (
    SELECT cn_api_id
    FROM (
        SELECT cn_api_id,
               ROW_NUMBER() OVER (PARTITION BY unique_id ORDER BY created_at DESC) as rn
        FROM split_payout_que
    ) t
    WHERE rn > 1
);

-- Then retry rollback
```

**Checklist:**
- [ ] Identify if rollback is necessary
- [ ] Check for duplicate unique_id values
- [ ] Execute rollback SQL
- [ ] Verify PRIMARY KEY restored to unique_id
- [ ] Document rollback reason

---

## Success Metrics

### Phase 1 Success Criteria

- [ ] **Column Added:** actual_eth_amount exists in split_payout_que
- [ ] **Column Populated:** actual_eth_amount shows real values (not 0 or 0E-18)
- [ ] **Code Updated:** All insert methods accept and pass actual_eth_amount
- [ ] **Audit Trail Complete:** actual_eth_amount matches across all 3 tables
- [ ] **No Errors:** No insertion failures or type mismatches
- [ ] **Production Stable:** System processes payments successfully

### Phase 2 Success Criteria

- [ ] **PRIMARY KEY Changed:** cn_api_id is PRIMARY KEY (not unique_id)
- [ ] **1-to-Many Supported:** Multiple cn_api_id records can exist for same unique_id
- [ ] **Constraints Added:** UNIQUE constraint on cn_api_id exists
- [ ] **Index Added:** Index on unique_id exists for efficient lookups
- [ ] **No Errors:** No insertion failures or constraint violations
- [ ] **Audit Trail Enhanced:** Can track all ChangeNow retry attempts
- [ ] **Performance Maintained:** Query performance not degraded

---

## Documentation Updates

### Update PROGRESS.md

**Add after Phase 1 completion:**

```markdown
## 2025-11-07 Session 70: Split_Payout Tables Phase 1 - actual_eth_amount Fix ✅

**CRITICAL DATA QUALITY FIX DEPLOYED**: Added actual_eth_amount to split_payout_que and fixed population in split_payout_hostpay

**Changes Implemented:**
- ✅ Database migration: Added actual_eth_amount NUMERIC(20,18) column to split_payout_que
- ✅ GCSplit1 database_manager: Updated insert_split_payout_que() method signature
- ✅ GCSplit1 tps1-10-26: Updated endpoint_3 to pass actual_eth_amount
- ✅ GCHostPay1 database_manager: Updated insert_hostpay_transaction() method signature
- ✅ GCHostPay3 tphp3-10-26: Updated caller to pass actual_eth_amount

**Deployments:**
- ✅ gcsplit1-10-26: Image actual-eth-que-fix, Revision 00022-xxx
- ✅ gchostpay1-10-26: Image actual-eth-hostpay-fix, Revision 00xxx-xxx
- ✅ gchostpay3-10-26: Image actual-eth-hostpay-fix, Revision 00xxx-xxx

**Impact:**
- ✅ Complete audit trail: actual_eth_amount stored in all 3 tables
- ✅ Can verify ChangeNow estimates vs NowPayments actual
- ✅ Can reconcile discrepancies between estimates and actuals
- ✅ Data quality improved for financial auditing

**Status:** ✅ **PHASE 1 COMPLETE - READY FOR PHASE 2**
```

**Add after Phase 2 completion:**

```markdown
## 2025-11-07 Session 71: Split_Payout Tables Phase 2 - Schema Correction ✅

**SCHEMA DESIGN FIX DEPLOYED**: Changed PRIMARY KEY from unique_id to cn_api_id

**Changes Implemented:**
- ✅ Database migration: Changed PRIMARY KEY to cn_api_id
- ✅ Added INDEX on unique_id for efficient 1-to-many lookups
- ✅ Added UNIQUE constraint on cn_api_id
- ✅ Updated code documentation to reflect new relationship

**Impact:**
- ✅ 1-to-many relationship supported: Multiple ChangeNow attempts tracked per payment
- ✅ Complete audit trail: Can see all retry attempts
- ✅ Technical debt resolved: Proper schema design vs workaround
- ✅ Can analyze ChangeNow API reliability
- ✅ Idempotency check still prevents duplicate cn_api_id

**Status:** ✅ **PHASE 2 COMPLETE - TECHNICAL DEBT RESOLVED**
```

### Update DECISIONS.md

**Add after Phase 1:**

```markdown
### 2025-11-07 Session 70: actual_eth_amount Storage in split_payout_que

**Decision:** Add actual_eth_amount column to split_payout_que table

**Context:**
- split_payout_request and split_payout_hostpay had actual_eth_amount, but split_payout_que did not
- Losing critical audit trail data (ACTUAL ETH from NowPayments)
- Cannot reconcile ChangeNow estimates vs NowPayments actuals

**Implementation:**
- Added NUMERIC(20,18) column with DEFAULT 0 (backward compatible)
- Updated all insert methods to accept and pass actual_eth_amount
- Updated callers to pass actual_eth_amount value

**Rationale:**
- Complete audit trail across all payment tracking tables
- Enable discrepancy analysis (estimate vs actual)
- Support financial reconciliation and auditing
- No breaking changes (DEFAULT 0 for backward compatibility)

**Impact:**
- ✅ Data quality improved
- ✅ Complete financial audit trail
- ✅ No breaking changes
```

**Add after Phase 2:**

```markdown
### 2025-11-07 Session 71: PRIMARY KEY Schema Correction

**Decision:** Change split_payout_que PRIMARY KEY from unique_id to cn_api_id

**Context:**
- Original schema used unique_id as PRIMARY KEY
- Prevented 1-to-many relationship (multiple ChangeNow attempts per payment)
- Idempotency check worked around issue but didn't fix root cause
- Lost audit trail of retry attempts

**Implementation:**
- Changed PRIMARY KEY to cn_api_id (unique per ChangeNow transaction)
- Added INDEX on unique_id (enables efficient 1-to-many lookups)
- Added UNIQUE constraint on cn_api_id (defense-in-depth)

**Rationale:**
- cn_api_id is globally unique and never reused (guaranteed by ChangeNow)
- unique_id should be FOREIGN KEY (conceptual), not PRIMARY KEY
- Enables proper 1-to-many relationship
- Complete audit trail of all ChangeNow attempts
- Can analyze ChangeNow API behavior and reliability

**Trade-offs:**
- Schema change requires migration (medium risk)
- Potential for duplicate unique_id if rollback needed
- BUT: Proper fix vs workaround (technical debt resolution)

**Impact:**
- ✅ Proper schema design
- ✅ Complete retry audit trail
- ✅ Technical debt resolved
- ✅ No functional changes (idempotency still works)
```

---

## Final Checklist

### Phase 1 Completion Checklist

- [ ] **Migration:** add_actual_eth_to_split_payout_que.sql executed
- [ ] **Code:** GCSplit1 database_manager.py updated
- [ ] **Code:** GCSplit1 tps1-10-26.py updated
- [ ] **Code:** GCHostPay1 database_manager.py updated
- [ ] **Code:** GCHostPay3 tphp3-10-26.py updated (caller)
- [ ] **Deploy:** gcsplit1-10-26 deployed
- [ ] **Deploy:** gchostpay1-10-26 deployed
- [ ] **Deploy:** gchostpay3-10-26 deployed (if modified)
- [ ] **Test:** Production validation passed
- [ ] **Test:** Database verification passed
- [ ] **Docs:** PROGRESS.md updated
- [ ] **Docs:** DECISIONS.md updated

### Phase 2 Completion Checklist

- [ ] **Migration:** fix_split_payout_que_primary_key.sql executed
- [ ] **Code:** Documentation updated in database_manager.py
- [ ] **Code:** Documentation updated in tps1-10-26.py
- [ ] **Test:** Unit test passed (1-to-many insertion)
- [ ] **Test:** Integration test passed (retry scenario)
- [ ] **Test:** Performance test passed (query speed)
- [ ] **Verify:** Production validation passed
- [ ] **Verify:** Audit trail complete
- [ ] **Docs:** PROGRESS.md updated
- [ ] **Docs:** DECISIONS.md updated

---

## Estimated Timeline

| Phase | Task | Time | Total |
|-------|------|------|-------|
| Phase 1 | Database Migration | 10 min | |
| Phase 1 | GCSplit1 Code Updates | 15 min | |
| Phase 1 | GCSplit1 Caller Updates | 10 min | |
| Phase 1 | GCHostPay1 Code Updates | 15 min | |
| Phase 1 | GCHostPay Caller Research | 10 min | |
| Phase 1 | Testing & Deployment | 20 min | |
| **Phase 1 Total** | | | **80 min** |
| | | | |
| Phase 2 | Database Migration | 20 min | |
| Phase 2 | Code Documentation | 10 min | |
| Phase 2 | Testing | 30 min | |
| **Phase 2 Total** | | | **60 min** |
| | | | |
| **Grand Total** | | | **140 min (~2.5 hours)** |

**Note:** Original estimate was 2 hours; revised to 2.5 hours after detailed task breakdown.

---

**Last Updated:** 2025-11-07
**Status:** READY FOR IMPLEMENTATION
**Next Action:** Begin Phase 1 - Task 1.1 (Database Migration)
