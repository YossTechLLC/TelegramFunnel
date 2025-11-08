# GCHostPay3 from_amount Architecture Fix - Comprehensive Architecture

**Date:** 2025-11-02
**Issue:** Architecture design for fixing GCHostPay3 amount discrepancy
**Status:** 🟡 ARCHITECTURE DESIGN
**Approach:** Analyze current system, design robust solution, prevent cascading effects

---

## Table of Contents
1. [Current System Analysis](#current-system-analysis)
2. [Core Problem Statement](#core-problem-statement)
3. [Design Principles](#design-principles)
4. [Proposed Architecture](#proposed-architecture)
5. [Cascading Effects Analysis](#cascading-effects-analysis)
6. [Implementation Strategy](#implementation-strategy)
7. [Testing & Validation](#testing--validation)

---

## Current System Analysis

### Existing Database Schema

**Table: `private_channel_users_database`**
```sql
-- Stores user subscription data and NowPayments metadata
CREATE TABLE private_channel_users_database (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    private_channel_id BIGINT,
    sub_time INTEGER,
    sub_price TEXT,
    expire_time TIME,
    expire_date DATE,
    is_active BOOLEAN,
    wallet_address TEXT,
    payout_currency TEXT,
    payout_network TEXT,
    nowpayments_payment_id TEXT,               -- ✅ NowPayments ID
    nowpayments_pay_address TEXT,              -- ✅ NowPayments deposit address
    nowpayments_outcome_amount NUMERIC(20,18), -- ✅ ACTUAL ETH received
    nowpayments_outcome_amount_usd NUMERIC(20,2), -- ✅ ACTUAL USD equivalent
    payment_status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Table: `split_payout_request`**
```sql
-- Stores payment split workflow tracking
CREATE TABLE split_payout_request (
    unique_id TEXT PRIMARY KEY,
    user_id BIGINT,
    closed_channel_id BIGINT,
    from_currency TEXT,           -- "usdt"
    to_currency TEXT,             -- Client's desired currency (e.g., "btc")
    from_network TEXT,            -- "eth"
    to_network TEXT,              -- Client's network (e.g., "btc")
    from_amount NUMERIC(20,18),   -- ❌ Currently: USDT amount after fees
    to_amount NUMERIC(20,18),     -- ❌ Currently: Estimated ETH (pure market value)
    client_wallet_address TEXT,   -- Client's receiving wallet
    refund_address TEXT,
    flow TEXT,                    -- "standard"
    type TEXT,                    -- "direct"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Table: `split_payout_hostpay`** (aka `split_payout_que`)
```sql
-- Stores ChangeNow transaction data and HostPay tracking
CREATE TABLE split_payout_hostpay (
    unique_id TEXT PRIMARY KEY,  -- References split_payout_request
    cn_api_id TEXT,              -- ChangeNow transaction ID
    user_id BIGINT,
    closed_channel_id BIGINT,
    from_currency TEXT,          -- "eth"
    to_currency TEXT,            -- Client's currency (e.g., "btc")
    from_network TEXT,           -- "eth"
    to_network TEXT,
    from_amount NUMERIC(20,18),  -- ❌ Currently: ChangeNow estimate (WRONG!)
    to_amount NUMERIC(20,18),    -- Expected client amount
    payin_address TEXT,          -- ChangeNow's deposit address
    payout_address TEXT,         -- Client's wallet (same as client_wallet_address)
    refund_address TEXT,
    flow TEXT,
    type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Current Token Flow Architecture

**Token Chain:**
```
np-webhook
    ↓ (HTTP POST with JSON payload)
GCWebhook1
    ↓ (Cloud Tasks + encrypted token)
GCSplit1
    ↓ (Cloud Tasks + encrypted token)
GCSplit2 (USDT→ETH estimate)
    ↓ (Cloud Tasks response + encrypted token)
GCSplit1
    ↓ (Cloud Tasks + encrypted token)
GCSplit3 (ETH→Client swap)
    ↓ (Cloud Tasks response + encrypted token)
GCSplit1
    ↓ (Cloud Tasks + binary packed token)
GCHostPay1
    ↓ (Cloud Tasks + encrypted token)
GCHostPay3
```

**Current Token Structure (GCWebhook1 → GCSplit1):**
```python
# File: GCWebhook1-10-26/cloudtasks_client.py
payload = {
    'user_id': user_id,
    'closed_channel_id': closed_channel_id,
    'wallet_address': wallet_address,
    'payout_currency': payout_currency,
    'payout_network': payout_network,
    'subscription_price': subscription_price  # ✅ Has USD
    # ❌ MISSING: nowpayments_outcome_amount (ACTUAL ETH)
}
```

### Payment Flow Types

The system supports **THREE** distinct payment flows:

#### 1. Instant Payouts (Current Focus)
```
User Payment → NowPayments → GCWebhook1 → GCSplit1 → GCHostPay → Client
```
- **Trigger:** Single user payment
- **Amount:** Individual subscription price
- **Context:** `instant`

#### 2. Threshold Payouts (Accumulation)
```
Multiple Payments → GCAccumulator → GCHostPay → Client
(when accumulated amount ≥ threshold)
```
- **Trigger:** Accumulated amount reaches threshold
- **Amount:** Sum of multiple payments
- **Context:** `threshold`

#### 3. Batch Conversions (Micro-batching)
```
Multiple Payments → GCBatchProcessor → GCMicroBatchProcessor → GCHostPay
```
- **Trigger:** Batch timer or size threshold
- **Amount:** Aggregated batch amount
- **Context:** `batch`

---

## Core Problem Statement

### The Fundamental Flaw

**Current Flow (WRONG):**
```
1. NowPayments: User pays $5 → Converts to ETH → Deposits 0.00115 ETH to wallet
   ✅ ACTUAL ETH: 0.00115340416715763 ETH

2. GCWebhook1: Passes only USD ($3.46) to GCSplit1
   ❌ ACTUAL ETH: LOST

3. GCSplit2: "How much ETH can I get for $3.36 USDT?"
   ChangeNow: "You'll get ~0.00112 ETH" (ESTIMATE)
   ❌ Using wrong question - we already HAVE ETH!

4. GCSplit3: "Create swap: 0.00115 ETH → BTC"
   ChangeNow: "OK, send 4.48 ETH to this address" (WRONG!)
   ❌ ChangeNow estimate doesn't match actual

5. GCHostPay3: Try to send 4.48 ETH
   Wallet: "I only have 0.00115 ETH"
   ❌ RESULT: Transaction timeout
```

### Why the Current Approach Fails

**Conceptual Error:**
We're asking ChangeNow to estimate how much ETH we'll get for USD, when we **already have the ETH** from NowPayments. This creates two independent conversion workflows that don't align:

1. **NowPayments Workflow:** USD → ETH (actual conversion)
2. **ChangeNow Workflow:** USD → ETH (estimate) → ClientCurrency

**Correct Conceptual Model:**
We should have ONE workflow:

1. **NowPayments:** USD → ETH (actual conversion - DONE)
2. **ChangeNow:** ETH (actual) → ClientCurrency (new conversion)

### The Missing Link

The `nowpayments_outcome_amount` (ACTUAL ETH) exists in the database but is never used for the actual payment. This is the architectural flaw.

---

## Design Principles

### Principle 1: Single Source of Truth

**Rule:** `nowpayments_outcome_amount` is the ONLY authoritative source for the ETH amount to send.

**Rationale:**
- This is the ACTUAL ETH in the wallet
- This is what we CAN send
- Everything else is estimation or calculation

**Implementation:**
- All services must receive and preserve this value
- No service may substitute an estimate for this value
- This value must be in the final payment token

### Principle 2: Explicit vs Implicit Amounts

**Rule:** Distinguish between "actual" amounts and "estimated" amounts.

**Naming Convention:**
- `actual_eth_amount` - The real ETH from NowPayments (authoritative)
- `estimated_eth_amount` - ChangeNow's estimate (informational only)
- `from_amount` - Generic field (deprecated in favor of explicit naming)

**Implementation:**
- Database columns: `actual_eth_amount`, `estimated_eth_amount`
- Token fields: `actual_eth_amount`, `estimated_eth_amount`
- Logs: Always prefix with "ACTUAL" or "ESTIMATED"

### Principle 3: Validation at Service Boundaries

**Rule:** Every service must validate amounts make sense before processing.

**Validation Checks:**
1. **GCWebhook1:** Does `outcome_amount_usd` match `nowpayments_outcome_amount * ETH_price`?
2. **GCSplit1:** Does `actual_eth_amount` exist and is > 0?
3. **GCHostPay1:** Does `actual_eth_amount` vs `estimated_eth_amount` differ by < 5%?
4. **GCHostPay3:** Does wallet balance ≥ `actual_eth_amount`?

**Implementation:**
- Each service logs validation results
- Alerts triggered if validation fails
- Payment blocked if critical validation fails

### Principle 4: Backward Compatibility

**Rule:** Changes must not break in-flight payments or threshold/batch flows.

**Strategy:**
- Token managers support BOTH old and new formats (graceful degradation)
- Database migrations use DEFAULT values for new columns
- Services check for field existence before using

**Implementation:**
- `token_manager.decrypt()` tries new format, falls back to old
- Database: `ALTER TABLE ... ADD COLUMN ... DEFAULT 0`
- Code: `actual_eth = data.get('actual_eth_amount') or data.get('from_amount')`

### Principle 5: Audit Trail

**Rule:** Store both actual and estimated amounts for forensic analysis.

**Rationale:**
- Helps debug discrepancies
- Provides evidence for financial audits
- Enables monitoring and alerting

**Implementation:**
- Database stores both `actual_eth_amount` and `estimated_eth_amount`
- Logs show both values at each step
- Discrepancy reports generated daily

---

## Proposed Architecture

### Architecture Change 1: Database Schema Evolution

**Add `actual_eth_amount` column to tracking tables:**

```sql
-- Migration 1: Add column to split_payout_request
ALTER TABLE split_payout_request
ADD COLUMN actual_eth_amount NUMERIC(20,18) DEFAULT 0;

-- Migration 2: Add column to split_payout_hostpay
ALTER TABLE split_payout_hostpay
ADD COLUMN actual_eth_amount NUMERIC(20,18) DEFAULT 0;

-- Migration 3: Rename ambiguous columns for clarity
ALTER TABLE split_payout_request
RENAME COLUMN from_amount TO estimated_usdt_amount;

ALTER TABLE split_payout_request
RENAME COLUMN to_amount TO estimated_eth_amount;

-- Migration 4: Add validation constraint
ALTER TABLE split_payout_request
ADD CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0);

ALTER TABLE split_payout_hostpay
ADD CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0);

-- Migration 5: Create index for lookup performance
CREATE INDEX idx_split_payout_request_actual_eth
ON split_payout_request(actual_eth_amount)
WHERE actual_eth_amount > 0;
```

**Rationale:**
- `actual_eth_amount` holds the NowPayments outcome (authoritative)
- `estimated_usdt_amount` holds the USDT estimate from GCSplit2 (informational)
- `estimated_eth_amount` holds the ETH estimate from GCSplit2 (informational)
- Renamed columns make intent explicit

### Architecture Change 2: Token Structure Evolution

**New Token Format (GCWebhook1 → GCSplit1):**

```python
# File: GCWebhook1-10-26/cloudtasks_client.py
payload = {
    'user_id': user_id,
    'closed_channel_id': closed_channel_id,
    'wallet_address': wallet_address,
    'payout_currency': payout_currency,
    'payout_network': payout_network,

    # Financial amounts (explicit naming)
    'subscription_price_usd': subscription_price,           # Declared price
    'outcome_amount_usd': outcome_amount_usd,               # ACTUAL USD (CoinGecko)
    'actual_eth_amount': nowpayments_outcome_amount,        # ✅ ACTUAL ETH (NowPayments)

    # NowPayments metadata
    'nowpayments_payment_id': nowpayments_payment_id,
    'nowpayments_pay_address': nowpayments_pay_address
}
```

**New Token Format (GCSplit1 → GCHostPay1):**

```python
# File: GCSplit1-10-26/tps1-10-26.py (build_hostpay_token)
def build_hostpay_token(
    unique_id: str,
    cn_api_id: str,
    from_currency: str,
    from_network: str,
    actual_eth_amount: float,      # ✅ Changed from from_amount
    estimated_eth_amount: float,   # ✅ Added for validation
    payin_address: str,
    signing_key: str
):
    packed_data = bytearray()
    packed_data.extend(unique_id_bytes)
    packed_data.append(len(cn_api_id_bytes))
    packed_data.extend(cn_api_id_bytes)
    packed_data.append(len(from_currency_bytes))
    packed_data.extend(from_currency_bytes)
    packed_data.append(len(from_network_bytes))
    packed_data.extend(from_network_bytes)
    packed_data.extend(struct.pack(">d", actual_eth_amount))     # ✅ ACTUAL
    packed_data.extend(struct.pack(">d", estimated_eth_amount))  # ✅ ESTIMATED
    packed_data.append(len(payin_address_bytes))
    packed_data.extend(payin_address_bytes)
    packed_data.extend(struct.pack(">I", current_timestamp))
    # ... signature
```

**Backward Compatibility Strategy:**

```python
# File: GCHostPay1-10-26/token_manager.py
def decrypt_gcsplit1_to_gchostpay1_token(self, token: str):
    """
    Decrypt token with backward compatibility.

    Old format: unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address
    New format: unique_id, cn_api_id, from_currency, from_network, actual_eth_amount, estimated_eth_amount, payin_address
    """
    try:
        # Try new format first (has both actual and estimated)
        payload = self._unpack_token(token)

        # Check if we have enough bytes for new format
        expected_new_size = 16 + len(cn_api_id) + len(from_currency) + len(from_network) + 8 + 8 + len(payin_address) + 4 + 16

        if len(payload) >= expected_new_size:
            # New format
            actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            estimated_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            return {
                'unique_id': unique_id,
                'cn_api_id': cn_api_id,
                'from_currency': from_currency,
                'from_network': from_network,
                'actual_eth_amount': actual_eth_amount,
                'estimated_eth_amount': estimated_eth_amount,
                'payin_address': payin_address
            }
        else:
            # Old format (single amount field)
            from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            print(f"⚠️ [TOKEN] Old token format detected - using from_amount as actual_eth_amount")

            return {
                'unique_id': unique_id,
                'cn_api_id': cn_api_id,
                'from_currency': from_currency,
                'from_network': from_network,
                'actual_eth_amount': from_amount,  # Assume old amount is actual
                'estimated_eth_amount': from_amount,  # Same value for backward compat
                'payin_address': payin_address
            }

    except Exception as e:
        print(f"❌ [TOKEN] Decryption failed: {e}")
        return None
```

### Architecture Change 3: Service Flow Redesign

**Current Flow (6 services):**
```
GCWebhook1 → GCSplit1 → GCSplit2 → GCSplit1 → GCSplit3 → GCSplit1 → GCHostPay1 → GCHostPay3
```

**Problems:**
1. GCSplit2 asks wrong question ("how much ETH for USD?")
2. Too many hops (complexity)
3. Actual ETH never makes it through

**Proposed Flow Option A (Keep All Services):**
```
GCWebhook1 → GCSplit1 → GCSplit3 → GCSplit1 → GCHostPay1 → GCHostPay3
                ↓ (bypass GCSplit2, or change its role)
           GCSplit2 (optional: validation only)
```

**GCSplit2 New Role (Optional Validation):**
- **Old:** "How much ETH for $X USDT?" (main workflow)
- **New:** "Validate: Does $X USD ≈ Y ETH at current rates?" (validation only)
- **Purpose:** Alert if NowPayments gave us significantly different rate than market

**GCSplit3 Modified Role:**
- **Old Input:** Estimated ETH amount from GCSplit2
- **New Input:** ACTUAL ETH amount from NowPayments (via GCSplit1)
- **API Call:** "I have X ETH, convert to ClientCurrency"

**Proposed Flow Option B (Simplify):**
```
GCWebhook1 → GCSplit1 → GCSplit3 → GCHostPay1 → GCHostPay3
```

**GCSplit2 Removed:**
- Estimation not needed if we use ACTUAL ETH
- Reduces complexity
- Faster processing

**Recommendation:** Start with Option A (keep GCSplit2 for validation), migrate to Option B later.

### Architecture Change 4: Service-by-Service Modifications

#### Service 1: np-webhook (No changes needed)

**Status:** ✅ Already stores `nowpayments_outcome_amount`

**Current Code:**
```python
# File: np-webhook-10-26/app.py (lines 724-752)
cur.execute("""
    INSERT INTO private_channel_users_database (
        nowpayments_outcome_amount,        # ✅ Already storing
        nowpayments_outcome_amount_usd,    # ✅ Already storing
        ...
    ) VALUES (%s, %s, ...)
""", (outcome_amount, outcome_amount_usd, ...))
```

**Action:** None required

---

#### Service 2: GCWebhook1 (Modify to pass actual_eth_amount)

**File:** `/GCWebhook1-10-26/tph1-10-26.py`

**Current Code (lines 240-246):**
```python
# CRITICAL: This is the ACTUAL outcome amount in USD from CoinGecko
outcome_amount_usd = payment_data.get('outcome_amount_usd')

# NowPayments metadata
nowpayments_payment_id = payment_data.get('nowpayments_payment_id')
nowpayments_pay_address = payment_data.get('nowpayments_pay_address')
nowpayments_outcome_amount = payment_data.get('nowpayments_outcome_amount')  # ✅ Has it!
```

**Problem:** Line 352 doesn't pass `nowpayments_outcome_amount` to GCSplit1

**Fix:**
```python
# Line 352: Pass ACTUAL ETH to GCSplit1
task_name = cloudtasks_client.enqueue_gcsplit1_payment_split(
    queue_name=gcsplit1_queue,
    target_url=gcsplit1_url,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_price=outcome_amount_usd,
    actual_eth_amount=nowpayments_outcome_amount  # ✅ ADD THIS
)
```

**File:** `/GCWebhook1-10-26/cloudtasks_client.py`

**Modify Method:**
```python
def enqueue_gcsplit1_payment_split(
    self,
    queue_name: str,
    target_url: str,
    user_id: int,
    closed_channel_id: int,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    subscription_price: float,
    actual_eth_amount: float  # ✅ ADD PARAMETER
) -> Optional[str]:
    payload = {
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'wallet_address': wallet_address,
        'payout_currency': payout_currency,
        'payout_network': payout_network,
        'subscription_price': subscription_price,
        'actual_eth_amount': actual_eth_amount  # ✅ ADD FIELD
    }
```

---

#### Service 3: GCSplit1 (Store actual_eth_amount, pass to GCSplit3, use for GCHostPay)

**File:** `/GCSplit1-10-26/tps1-10-26.py`

**Endpoint 1 Modification (receive from GCWebhook1):**
```python
# Line 299: Extract actual_eth_amount from webhook
webhook_data = request.get_json()
user_id = webhook_data.get('user_id')
closed_channel_id = webhook_data.get('closed_channel_id')
wallet_address = webhook_data.get('wallet_address')
payout_currency = webhook_data.get('payout_currency')
payout_network = webhook_data.get('payout_network')
subscription_price = webhook_data.get('subscription_price')
actual_eth_amount = webhook_data.get('actual_eth_amount')  # ✅ ADD THIS

print(f"💰 [ENDPOINT_1] Subscription Price: ${subscription_price}")
print(f"💰 [ENDPOINT_1] ACTUAL ETH: {actual_eth_amount}")  # ✅ LOG IT
```

**Endpoint 2 Modification (store in database):**
```python
# Line 462: Store actual_eth_amount in database
unique_id = database_manager.insert_split_payout_request(
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    from_currency="usdt",
    to_currency=payout_currency,
    from_network="eth",
    to_network=payout_network,
    from_amount=from_amount_usdt,                    # Estimated USDT
    to_amount=pure_market_eth_value,                 # Estimated ETH
    client_wallet_address=wallet_address,
    refund_address="",
    flow="standard",
    type_="direct",
    actual_eth_amount=actual_eth_amount  # ✅ ADD THIS
)
```

**Endpoint 2 Token Encryption:**
```python
# Line 485: Pass actual_eth_amount to GCSplit3
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    eth_amount=pure_market_eth_value,        # Estimated ETH
    actual_eth_amount=actual_eth_amount  # ✅ ADD THIS (ACTUAL ETH)
)
```

**Endpoint 3 Modification (use actual_eth_amount for GCHostPay):**
```python
# Line 593: Extract both amounts
from_amount = decrypted_data['from_amount']  # ChangeNow estimate
actual_eth_amount = decrypted_data.get('actual_eth_amount')  # ✅ ACTUAL ETH

print(f"💰 [ENDPOINT_3] ChangeNow estimate: {from_amount} ETH")
print(f"💰 [ENDPOINT_3] ACTUAL ETH amount: {actual_eth_amount} ETH")

# Validation check
if actual_eth_amount and from_amount:
    discrepancy_pct = abs(from_amount - actual_eth_amount) / actual_eth_amount * 100
    print(f"📊 [ENDPOINT_3] Discrepancy: {discrepancy_pct:.2f}%")

    if discrepancy_pct > 5:
        print(f"⚠️ [ENDPOINT_3] WARNING: Estimate differs by >5%!")

# Line 645: Use ACTUAL amount for GCHostPay token
hostpay_token = build_hostpay_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,
    from_network=from_network,
    actual_eth_amount=actual_eth_amount,     # ✅ ACTUAL ETH
    estimated_eth_amount=from_amount,        # ✅ ChangeNow estimate
    payin_address=payin_address,
    signing_key=tps_hostpay_signing_key
)
```

**File:** `/GCSplit1-10-26/database_manager.py`

**Modify Method:**
```python
def insert_split_payout_request(
    self,
    user_id: int,
    closed_channel_id: int,
    from_currency: str,
    to_currency: str,
    from_network: str,
    to_network: str,
    from_amount: float,
    to_amount: float,
    client_wallet_address: str,
    refund_address: str,
    flow: str,
    type_: str,
    actual_eth_amount: float  # ✅ ADD PARAMETER
) -> Optional[str]:

    cur.execute("""
        INSERT INTO split_payout_request (
            unique_id, user_id, closed_channel_id,
            from_currency, to_currency,
            from_network, to_network,
            from_amount, to_amount,
            client_wallet_address, refund_address,
            flow, type,
            actual_eth_amount,  -- ✅ ADD COLUMN
            created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
        )
    """, (
        unique_id, user_id, closed_channel_id,
        from_currency, to_currency,
        from_network, to_network,
        from_amount, to_amount,
        client_wallet_address, refund_address,
        flow, type_,
        actual_eth_amount  # ✅ ADD VALUE
    ))
```

---

#### Service 4: GCSplit3 (Receive actual_eth_amount, pass to response)

**File:** `/GCSplit3-10-26/token_manager.py`

**Modify decrypt method:**
```python
def decrypt_gcsplit1_to_gcsplit3_token(self, token: str):
    # ... existing decryption logic ...

    eth_amount = decrypted_data['eth_amount']  # Estimated ETH
    actual_eth_amount = decrypted_data.get('actual_eth_amount')  # ✅ ACTUAL ETH

    print(f"💰 [TOKEN] Estimated ETH: {eth_amount}")
    print(f"💰 [TOKEN] ACTUAL ETH: {actual_eth_amount}")

    return {
        'unique_id': unique_id,
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'wallet_address': wallet_address,
        'payout_currency': payout_currency,
        'payout_network': payout_network,
        'eth_amount': eth_amount,
        'actual_eth_amount': actual_eth_amount  # ✅ ADD FIELD
    }
```

**Modify encrypt response method:**
```python
def encrypt_gcsplit3_to_gcsplit1_token(
    self,
    unique_id: str,
    user_id: int,
    closed_channel_id: int,
    cn_api_id: str,
    from_currency: str,
    to_currency: str,
    from_network: str,
    to_network: str,
    from_amount: float,
    to_amount: float,
    payin_address: str,
    payout_address: str,
    refund_address: str,
    flow: str,
    type_: str,
    actual_eth_amount: float  # ✅ ADD PARAMETER
):
    data = {
        'unique_id': unique_id,
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'cn_api_id': cn_api_id,
        'from_currency': from_currency,
        'to_currency': to_currency,
        'from_network': from_network,
        'to_network': to_network,
        'from_amount': from_amount,  # ChangeNow estimate
        'to_amount': to_amount,
        'payin_address': payin_address,
        'payout_address': payout_address,
        'refund_address': refund_address,
        'flow': flow,
        'type': type_,
        'actual_eth_amount': actual_eth_amount  # ✅ ADD FIELD
    }
```

**File:** `/GCSplit3-10-26/tps3-10-26.py`

**Modify endpoint:**
```python
# Line 106: Extract both amounts
eth_amount = decrypted_data['eth_amount']  # Estimated
actual_eth_amount = decrypted_data.get('actual_eth_amount')  # ✅ ACTUAL

print(f"💰 [ENDPOINT] Estimated ETH: {eth_amount}")
print(f"💰 [ENDPOINT] ACTUAL ETH: {actual_eth_amount}")

# Line 164: Pass actual_eth_amount to response token
encrypted_response_token = token_manager.encrypt_gcsplit3_to_gcsplit1_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    cn_api_id=cn_api_id,
    from_currency=api_from_currency,
    to_currency=api_to_currency,
    from_network=api_from_network,
    to_network=api_to_network,
    from_amount=api_from_amount,  # ChangeNow's fromAmount
    to_amount=api_to_amount,
    payin_address=api_payin_address,
    payout_address=api_payout_address,
    refund_address=api_refund_address,
    flow=api_flow,
    type_=api_type,
    actual_eth_amount=actual_eth_amount  # ✅ PASS ACTUAL
)
```

---

#### Service 5: GCHostPay1 (No changes - passes through)

**Status:** ✅ Token structure change handled in token_manager (see Architecture Change 2)

**Note:** GCHostPay1 receives token from GCSplit1 and forwards to GCHostPay3. The binary packed token format change (with both actual and estimated amounts) is sufficient.

---

#### Service 6: GCHostPay3 (Use actual_eth_amount, validate balance)

**File:** `/GCHostPay3-10-26/tphp3-10-26.py`

**Modify token decryption:**
```python
# Line 168: Extract actual_eth_amount
from_amount = decrypted_data['from_amount']  # Legacy field
actual_eth_amount = decrypted_data.get('actual_eth_amount')  # ✅ ACTUAL ETH
estimated_eth_amount = decrypted_data.get('estimated_eth_amount')  # ChangeNow estimate

# Use actual_eth_amount if available, fallback to from_amount for backward compat
payment_amount = actual_eth_amount if actual_eth_amount is not None else from_amount

print(f"💰 [ENDPOINT] ACTUAL ETH to send: {payment_amount}")

if actual_eth_amount and estimated_eth_amount:
    discrepancy = abs(actual_eth_amount - estimated_eth_amount)
    discrepancy_pct = (discrepancy / actual_eth_amount) * 100
    print(f"📊 [ENDPOINT] ChangeNow estimate: {estimated_eth_amount} ETH")
    print(f"📊 [ENDPOINT] Discrepancy: {discrepancy} ETH ({discrepancy_pct:.2f}%)")

    if discrepancy_pct > 5:
        print(f"⚠️ [ENDPOINT] WARNING: Estimate differs by >5%!")
```

**Add wallet balance validation:**
```python
# Line 203: Validate before payment
print(f"🔍 [ENDPOINT] Checking wallet balance before payment...")

wallet_balance = wallet_manager.get_wallet_balance()
print(f"💰 [ENDPOINT] Wallet balance: {wallet_balance} ETH")
print(f"💰 [ENDPOINT] Amount to send: {payment_amount} ETH")

if payment_amount > wallet_balance:
    print(f"❌ [ENDPOINT] INSUFFICIENT BALANCE!")
    print(f"   Required: {payment_amount} ETH")
    print(f"   Available: {wallet_balance} ETH")
    print(f"   Shortfall: {payment_amount - wallet_balance} ETH")

    # Log to database for tracking
    # ... (add failed transaction record)

    return jsonify({
        "status": "error",
        "message": f"Insufficient wallet balance (need {payment_amount}, have {wallet_balance})"
    }), 400

print(f"✅ [ENDPOINT] Sufficient balance, proceeding with payment")

# Line 203: Use payment_amount (actual)
tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
    to_address=payin_address,
    amount=payment_amount,  # ✅ ACTUAL ETH
    unique_id=unique_id
)
```

**File:** `/GCHostPay3-10-26/wallet_manager.py`

**Add balance check method:**
```python
def get_wallet_balance(self) -> float:
    """
    Get current wallet balance in ETH.

    Returns:
        Balance in ETH (as float)
    """
    try:
        balance_wei = self.w3.eth.get_balance(self.wallet_address)
        balance_eth = self.w3.from_wei(balance_wei, 'ether')

        print(f"💰 [WALLET] Current balance: {balance_eth} ETH ({balance_wei} Wei)")

        return float(balance_eth)

    except Exception as e:
        print(f"❌ [WALLET] Failed to get balance: {e}")
        return 0.0
```

---

### Architecture Change 5: Threshold & Batch Payouts

**Challenge:** Threshold and batch payouts accumulate multiple payments before converting.

**Current Flow (Threshold):**
```
Payment 1 ($5) → GCAccumulator
Payment 2 ($5) → GCAccumulator
Payment 3 ($5) → GCAccumulator
(Total: $15 ≥ $10 threshold)
GCAccumulator → GCSplit3 → GCHostPay
```

**Problem:** Each payment has its own `nowpayments_outcome_amount`, but we need ONE amount for the batch.

**Solution 1: Sum Actual ETH Amounts**

**File:** `/GCAccumulator-10-26/database_manager.py`

**Add method to sum actual ETH:**
```python
def get_accumulated_actual_eth(self, client_id: int) -> float:
    """
    Get total ACTUAL ETH accumulated for a client.

    Sums all nowpayments_outcome_amount values for pending payments.

    Args:
        client_id: Channel/client ID

    Returns:
        Total actual ETH amount
    """
    conn = self.get_connection()
    if not conn:
        return 0.0

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT SUM(nowpayments_outcome_amount)
            FROM private_channel_users_database
            WHERE private_channel_id = %s
              AND payment_status = 'confirmed'
              AND payout_status = 'pending'
        """, (client_id,))

        result = cur.fetchone()
        total_eth = float(result[0]) if result and result[0] else 0.0

        cur.close()
        conn.close()

        print(f"💰 [ACCUMULATOR] Total actual ETH for client {client_id}: {total_eth}")

        return total_eth

    except Exception as e:
        print(f"❌ [ACCUMULATOR] Failed to get accumulated ETH: {e}")
        return 0.0
```

**File:** `/GCAccumulator-10-26/acc10-26.py`

**Use actual ETH sum:**
```python
# When threshold reached
accumulated_usd = check_threshold_reached(client_id, threshold)

if accumulated_usd >= threshold:
    print(f"🎯 [ACCUMULATOR] Threshold reached: ${accumulated_usd} ≥ ${threshold}")

    # Get ACTUAL ETH accumulated (not USD estimate!)
    actual_eth_total = database_manager.get_accumulated_actual_eth(client_id)

    print(f"💰 [ACCUMULATOR] Accumulated USD: ${accumulated_usd}")
    print(f"💰 [ACCUMULATOR] ACTUAL ETH total: {actual_eth_total} ETH")

    # Send to GCHostPay with ACTUAL ETH
    token = token_manager.encrypt_accumulator_to_gchostpay1_token(
        accumulation_id=accumulation_id,
        client_id=client_id,
        cn_api_id=cn_api_id,
        from_currency="eth",
        from_network="eth",
        from_amount=actual_eth_total,  # ✅ ACTUAL ETH (summed)
        payin_address=payin_address,
        context="threshold"
    )
```

**Solution 2: Track Accumulation in Separate Table**

**Create new table:**
```sql
CREATE TABLE eth_accumulation (
    accumulation_id UUID PRIMARY KEY,
    client_id BIGINT,
    total_actual_eth NUMERIC(20,18),
    total_usd NUMERIC(20,2),
    payment_count INTEGER,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);
```

**Update on each payment:**
```python
# When payment confirmed
database_manager.add_to_accumulation(
    client_id=client_id,
    actual_eth=nowpayments_outcome_amount,
    usd_amount=outcome_amount_usd
)
```

**Recommendation:** Use Solution 1 (simpler, leverages existing data).

---

## Cascading Effects Analysis

### Effect 1: In-Flight Payments

**Risk:** Payments currently in Cloud Tasks queues may fail if token format changes.

**Mitigation:**
1. **Backward Compatible Tokens:** Token managers support BOTH old and new formats
2. **Graceful Degradation:** If `actual_eth_amount` missing, use `from_amount`
3. **Version Field:** Add version number to tokens for future changes

**Code:**
```python
def decrypt_token(self, token: str):
    try:
        data = self._decrypt(token)

        # Check version
        version = data.get('version', 1)  # Default to v1 for old tokens

        if version == 2:
            # New format with actual_eth_amount
            return self._parse_v2(data)
        else:
            # Old format
            print(f"⚠️ [TOKEN] Old token format (v1) - migrating...")
            return self._parse_v1_compat(data)

    except Exception as e:
        print(f"❌ [TOKEN] Decryption failed: {e}")
        return None
```

### Effect 2: Database Migration During Traffic

**Risk:** ALTER TABLE on live database may lock table, block payments.

**Mitigation:**
1. **Use CONCURRENTLY:** `ALTER TABLE ... ADD COLUMN ... DEFAULT 0 NOT NULL;` (PostgreSQL allows this)
2. **Staged Migration:**
   - Phase 1: Add column with DEFAULT
   - Phase 2: Backfill data (if needed)
   - Phase 3: Deploy code changes
3. **Rollback Plan:** Keep DEFAULT 0 so old code still works

**Migration Script:**
```sql
-- Phase 1: Add column (no data migration yet)
BEGIN;

ALTER TABLE split_payout_request
ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;

ALTER TABLE split_payout_hostpay
ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;

COMMIT;

-- Phase 2: Backfill (optional - only if we want to populate historical data)
-- This can run separately, no blocking
UPDATE split_payout_request
SET actual_eth_amount = (
    SELECT nowpayments_outcome_amount
    FROM private_channel_users_database
    WHERE private_channel_users_database.user_id = split_payout_request.user_id
      AND private_channel_users_database.private_channel_id = split_payout_request.closed_channel_id
    ORDER BY created_at DESC
    LIMIT 1
)
WHERE actual_eth_amount = 0;
```

### Effect 3: GCSplit2 Role Change

**Current:** GCSplit2 is critical path (estimates USDT→ETH)

**Proposed:** GCSplit2 becomes optional (validation only)

**Risk:** Code that depends on GCSplit2 estimate may break.

**Mitigation:**
1. **Keep GCSplit2 in flow:** Don't remove it yet
2. **Change behavior:** GCSplit2 still returns estimate, but we don't use it for payment
3. **Use for validation:** Compare estimate vs actual, alert if >5% difference
4. **Future removal:** After monitoring shows it's safe, remove GCSplit2

**Code (GCSplit1):**
```python
# Option: Skip GCSplit2 entirely
if actual_eth_amount:
    print(f"✅ [ENDPOINT_1] ACTUAL ETH available: {actual_eth_amount}")
    print(f"⏭️ [ENDPOINT_1] Skipping GCSplit2 estimate, going straight to GCSplit3")

    # Encrypt token for GCSplit3 directly
    encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
        unique_id=unique_id,
        user_id=user_id,
        closed_channel_id=closed_channel_id,
        wallet_address=wallet_address,
        payout_currency=payout_currency,
        payout_network=payout_network,
        eth_amount=actual_eth_amount,  # Use ACTUAL, not estimate
        actual_eth_amount=actual_eth_amount
    )

    # Enqueue to GCSplit3
    cloudtasks_client.enqueue_gcsplit3_swap_request(...)
else:
    print(f"⚠️ [ENDPOINT_1] ACTUAL ETH not available, falling back to GCSplit2 estimate")
    # ... existing GCSplit2 flow
```

### Effect 4: ChangeNow API Compatibility

**Risk:** ChangeNow API may reject payment if amount doesn't match their estimate.

**Investigation Needed:**
1. Does ChangeNow's `create_fixed_rate_transaction` lock in a specific `fromAmount`?
2. Will they reject if we send slightly different amount?
3. What's the tolerance range?

**Testing Strategy:**
1. **Test Case 1:** Create swap with estimate, send exact estimated amount
2. **Test Case 2:** Create swap with estimate, send 1% more
3. **Test Case 3:** Create swap with estimate, send 1% less
4. **Test Case 4:** Create swap with actual amount directly (no estimate step)

**Mitigation:**
- If ChangeNow requires exact match: Use `actual_eth_amount` when calling `create_fixed_rate_transaction`
- If ChangeNow allows tolerance: Continue with current approach but send actual amount

### Effect 5: Monitoring & Alerting

**New Monitoring Needed:**
1. **Discrepancy Alerts:** actual vs estimated differs by >5%
2. **Balance Alerts:** Wallet balance insufficient for payment
3. **Missing Data Alerts:** `actual_eth_amount` is NULL or 0
4. **Validation Alerts:** Amount validation fails

**Implementation:**
```python
# File: GCHostPay1-10-26/tphp1-10-26.py
def validate_and_alert(actual_eth: float, estimated_eth: float, unique_id: str):
    """
    Validate amounts and send alerts if needed.
    """
    if not actual_eth or actual_eth <= 0:
        send_alert(
            severity="CRITICAL",
            message=f"Missing actual_eth_amount for {unique_id}",
            details={"actual_eth": actual_eth, "estimated_eth": estimated_eth}
        )
        return False

    discrepancy_pct = abs(actual_eth - estimated_eth) / actual_eth * 100

    if discrepancy_pct > 10:
        send_alert(
            severity="HIGH",
            message=f"Large discrepancy for {unique_id}: {discrepancy_pct:.2f}%",
            details={"actual_eth": actual_eth, "estimated_eth": estimated_eth}
        )
    elif discrepancy_pct > 5:
        send_alert(
            severity="MEDIUM",
            message=f"Moderate discrepancy for {unique_id}: {discrepancy_pct:.2f}%",
            details={"actual_eth": actual_eth, "estimated_eth": estimated_eth}
        )

    return True

def send_alert(severity: str, message: str, details: dict):
    """
    Send alert to monitoring system.
    """
    # Integration with Google Cloud Monitoring, Slack, PagerDuty, etc.
    print(f"🚨 [{severity}] ALERT: {message}")
    print(f"📋 [ALERT] Details: {details}")
    # ... actual alerting code
```

---

## Implementation Strategy

### Phase 1: Database Preparation (Day 1)

**Tasks:**
1. Run database migration (add columns)
2. Verify migration success
3. Test backward compatibility (old code still works)

**SQL:**
```sql
-- Migration script
ALTER TABLE split_payout_request ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;
ALTER TABLE split_payout_hostpay ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;
```

**Verification:**
```bash
psql -h /cloudsql/... -U postgres -d telepaydb -c "\d split_payout_request"
psql -h /cloudsql/... -U postgres -d telepaydb -c "\d split_payout_hostpay"
```

### Phase 2: Token Manager Updates (Day 2)

**Tasks:**
1. Update all token_manager.py files to support new format
2. Implement backward compatibility
3. Add version field to tokens
4. Test encryption/decryption both ways

**Files to Update:**
- `/GCWebhook1-10-26/cloudtasks_client.py`
- `/GCSplit1-10-26/token_manager.py`
- `/GCSplit3-10-26/token_manager.py`
- `/GCHostPay1-10-26/token_manager.py`

**Testing:**
```python
# Test backward compatibility
old_token = create_old_format_token()
new_data = token_manager.decrypt(old_token)
assert new_data['actual_eth_amount'] == new_data['from_amount']  # Fallback works

new_token = create_new_format_token()
new_data = token_manager.decrypt(new_token)
assert new_data['actual_eth_amount'] != new_data['estimated_eth_amount']  # Distinction works
```

### Phase 3: Service Code Updates (Day 3-4)

**Deploy Order (Reverse of Flow):**
1. Deploy GCHostPay3 first (accepts both old and new tokens)
2. Deploy GCHostPay1
3. Deploy GCSplit3
4. Deploy GCSplit1
5. Deploy GCWebhook1 last (starts sending new tokens)

**Rationale:** Downstream services must accept new format before upstream services send it.

**Deployment Script:**
```bash
#!/bin/bash
# deploy_actual_eth_fix.sh

set -e  # Exit on error

echo "🚀 Deploying actual_eth_amount fix..."

# Phase 1: Deploy downstream services first
echo "📦 [1/6] Deploying GCHostPay3..."
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay3-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gchostpay3-10-26
gcloud run deploy gchostpay3-10-26 --image gcr.io/telepay-459221/gchostpay3-10-26 --region us-central1

echo "📦 [2/6] Deploying GCHostPay1..."
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay1-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gchostpay1-10-26
gcloud run deploy gchostpay1-10-26 --image gcr.io/telepay-459221/gchostpay1-10-26 --region us-central1

echo "📦 [3/6] Deploying GCSplit3..."
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit3-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gcsplit3-10-26
gcloud run deploy gcsplit3-10-26 --image gcr.io/telepay-459221/gcsplit3-10-26 --region us-central1

echo "📦 [4/6] Deploying GCSplit1..."
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit1-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gcsplit1-10-26
gcloud run deploy gcsplit1-10-26 --image gcr.io/telepay-459221/gcsplit1-10-26 --region us-central1

echo "📦 [5/6] Deploying GCWebhook1..."
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook1-10-26
gcloud run deploy gcwebhook1-10-26 --image gcr.io/telepay-459221/gcwebhook1-10-26 --region us-central1

echo "✅ Deployment complete!"
```

### Phase 4: Validation & Monitoring (Day 5)

**Tasks:**
1. Create test payment ($5)
2. Monitor logs across all services
3. Verify `actual_eth_amount` flows through chain
4. Compare actual vs estimated amounts
5. Verify GCHostPay3 sends correct amount
6. Confirm ChangeNow swap completes

**Monitoring Queries:**
```bash
# Check GCWebhook1 logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcwebhook1-10-26 AND textPayload=~'ACTUAL ETH'" --limit 50 --format json

# Check GCSplit1 database
psql -h /cloudsql/... -U postgres -d telepaydb -c "SELECT unique_id, actual_eth_amount, from_amount, to_amount FROM split_payout_request ORDER BY created_at DESC LIMIT 5;"

# Check GCHostPay3 logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gchostpay3-10-26 AND textPayload=~'ACTUAL ETH'" --limit 50
```

**Success Criteria:**
- [ ] `actual_eth_amount` appears in GCWebhook1 logs
- [ ] `actual_eth_amount` stored in split_payout_request table
- [ ] `actual_eth_amount` appears in GCHostPay3 logs
- [ ] Amount sent to ChangeNow matches `nowpayments_outcome_amount`
- [ ] No more 3,886x discrepancies
- [ ] Payment completes successfully

### Phase 5: Rollback Plan

**If deployment fails:**

```bash
#!/bin/bash
# rollback_actual_eth_fix.sh

echo "⏮️ Rolling back actual_eth_amount deployment..."

# Rollback in reverse order (upstream first)
gcloud run services update-traffic gcwebhook1-10-26 --to-revisions PREVIOUS=100 --region us-central1
gcloud run services update-traffic gcsplit1-10-26 --to-revisions PREVIOUS=100 --region us-central1
gcloud run services update-traffic gcsplit3-10-26 --to-revisions PREVIOUS=100 --region us-central1
gcloud run services update-traffic gchostpay1-10-26 --to-revisions PREVIOUS=100 --region us-central1
gcloud run services update-traffic gchostpay3-10-26 --to-revisions PREVIOUS=100 --region us-central1

echo "✅ Rollback complete - services reverted to previous revision"
```

**Database rollback NOT needed:**
- New columns have DEFAULT values
- Old code ignores new columns
- No data loss

---

## Testing & Validation

### Test Case 1: End-to-End Happy Path

**Scenario:** User pays $5, receives BTC payout

**Steps:**
1. Create test payment via TelePay bot
2. NowPayments processes, sends IPN
3. Track payment through all services
4. Verify ChangeNow swap completes
5. Verify client receives BTC

**Expected Results:**
```
np-webhook: nowpayments_outcome_amount = 0.00115340416715763 ETH
GCWebhook1: actual_eth_amount = 0.00115340416715763 ETH
GCSplit1: actual_eth_amount = 0.00115340416715763 ETH (stored in DB)
GCSplit3: actual_eth_amount = 0.00115340416715763 ETH
GCHostPay1: actual_eth_amount = 0.00115340416715763 ETH
GCHostPay3: Sending 0.00115340416715763 ETH to ChangeNow
ChangeNow: Transaction complete, client receives ~0.00003 BTC
```

**Validation:**
```sql
-- Check database records
SELECT
    spr.unique_id,
    spr.actual_eth_amount AS split_request_actual_eth,
    sph.actual_eth_amount AS hostpay_actual_eth,
    spr.from_amount AS estimated_usdt,
    spr.to_amount AS estimated_eth,
    pcu.nowpayments_outcome_amount AS nowpayments_actual_eth
FROM split_payout_request spr
JOIN split_payout_hostpay sph ON spr.unique_id = sph.unique_id
JOIN private_channel_users_database pcu ON spr.user_id = pcu.user_id
WHERE spr.unique_id = '<test_unique_id>';
```

### Test Case 2: Amount Discrepancy Detection

**Scenario:** Simulate scenario where ChangeNow estimate differs significantly from actual

**Steps:**
1. Modify GCSplit2 to return wrong estimate (for testing)
2. Create payment
3. Verify alert triggers

**Expected Results:**
```
GCHostPay1 logs:
📊 [ENDPOINT_2] ChangeNow estimate: 0.005 ETH
📊 [ENDPOINT_2] ACTUAL amount to send: 0.00115 ETH
⚠️ [ENDPOINT_2] Discrepancy: 0.00385 ETH (334.78%)
🚨 [HIGH] ALERT: Large discrepancy for unique_id: 334.78%
```

### Test Case 3: Insufficient Balance

**Scenario:** Wallet balance too low for payment

**Steps:**
1. Drain host wallet to minimal balance
2. Create payment
3. Verify payment blocked

**Expected Results:**
```
GCHostPay3 logs:
💰 [ENDPOINT] Wallet balance: 0.0005 ETH
💰 [ENDPOINT] Amount to send: 0.00115 ETH
❌ [ENDPOINT] INSUFFICIENT BALANCE!
   Required: 0.00115 ETH
   Available: 0.0005 ETH
   Shortfall: 0.00065 ETH

HTTP Response: 400 Bad Request
{
  "status": "error",
  "message": "Insufficient wallet balance (need 0.00115, have 0.0005)"
}
```

### Test Case 4: Backward Compatibility

**Scenario:** Old format token sent to new service

**Steps:**
1. Deploy new GCHostPay3
2. Send old format token (no `actual_eth_amount`)
3. Verify graceful handling

**Expected Results:**
```
GCHostPay3 logs:
⚠️ [TOKEN] Old token format detected - using from_amount as actual_eth_amount
💰 [ENDPOINT] ACTUAL ETH to send: 0.00115 ETH (from legacy field)
✅ [ENDPOINT] Sufficient balance, proceeding with payment
```

### Test Case 5: Threshold Payout

**Scenario:** Multiple payments accumulate, trigger threshold payout

**Steps:**
1. Configure channel with $10 threshold
2. Make 3 payments of $5 each
3. Verify accumulated ETH = sum of individual amounts
4. Verify payout uses accumulated amount

**Expected Results:**
```
Payment 1: nowpayments_outcome_amount = 0.00115 ETH
Payment 2: nowpayments_outcome_amount = 0.00113 ETH
Payment 3: nowpayments_outcome_amount = 0.00114 ETH

GCAccumulator:
💰 [ACCUMULATOR] Total actual ETH: 0.00342 ETH
🎯 [ACCUMULATOR] Threshold reached: $15.00 ≥ $10.00

GCHostPay3:
💰 [ENDPOINT] ACTUAL ETH to send: 0.00342 ETH
✅ Payment sent successfully
```

---

## Summary & Recommendations

### Architecture Summary

**Current State:**
- `nowpayments_outcome_amount` (ACTUAL ETH) is stored but never used
- Payment flow uses ChangeNow estimates instead of actual amounts
- Results in 3,886x discrepancy and transaction timeouts

**Proposed State:**
- `actual_eth_amount` flows through entire payment chain
- All services preserve and pass this value
- GCHostPay3 uses ACTUAL amount for payment
- Validation at every step ensures correctness

### Key Changes

1. **Database:** Add `actual_eth_amount` columns
2. **Tokens:** Include both `actual_eth_amount` and `estimated_eth_amount`
3. **Services:** Pass actual amount through all 6 services
4. **Validation:** Check balance, compare actual vs estimate
5. **Monitoring:** Alert on discrepancies

### Implementation Timeline

- **Day 1:** Database migration
- **Day 2:** Token manager updates
- **Day 3-4:** Service code updates and deployment
- **Day 5:** Validation and monitoring

### Risk Mitigation

- **Backward compatibility:** Support old token format
- **Staged deployment:** Deploy downstream first
- **Rollback plan:** Revert to previous revisions if needed
- **Database safety:** Use DEFAULT values, no data loss

### Success Metrics

- ✅ No more 3,886x discrepancies in logs
- ✅ Payment amounts match `nowpayments_outcome_amount`
- ✅ Transaction timeouts eliminated
- ✅ ChangeNow swaps complete successfully
- ✅ Clients receive expected payouts

### Recommendation

**Proceed with implementation using staged approach:**
1. Start with database migration (low risk)
2. Update token managers with backward compatibility
3. Deploy services in reverse order (downstream first)
4. Monitor carefully during rollout
5. Keep rollback option ready

**Alternative Option (If Concerned):**
- Implement "database query" solution first (simpler)
- GCHostPay3 queries DB for `nowpayments_outcome_amount`
- Test in production with low volume
- If successful, refactor to full token-based approach later

**Final Decision:** Your call based on risk tolerance and timeline constraints.
