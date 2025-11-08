# GCHostPay3 from_amount Architecture Fix

**Date:** 2025-11-02
**Issue:** GCHostPay3 receiving wrong `from_amount` value - using ChangeNow estimates instead of actual NowPayments outcome amount
**Impact:** 3,886x amount discrepancy (4.48 ETH vs 0.00115 ETH)
**Status:** 🔴 CRITICAL - ARCHITECTURE FLAW

---

## Executive Summary

### The Problem

GCHostPay3 is receiving `from_amount` from **ChangeNow API estimates** instead of the **ACTUAL ETH** that NowPayments deposited into the host wallet (`nowpayments_outcome_amount`).

This creates a fundamental architecture flaw:
- **What we have:** X ETH in the wallet
- **What we're trying to pay:** Y ETH (from ChangeNow estimate)
- **Result:** Amount mismatch causing transaction timeouts and potential financial loss

### The Constraint (User Requirement)

> "The from_amount field should be populated either from `nowpayments_outcome_amount` (ETH value) or `nowpayments_outcome_amount_usd` (USD equivalent), since this is the REAL value that hit the host wallet address and is live in the host wallet. This should represent the real sum of money that the host wallet has and can pay out."

### Root Cause

The `from_amount` data flows through 6 services before reaching GCHostPay3, and somewhere in this chain, we're substituting the ACTUAL amount with a ChangeNow ESTIMATE.

---

## Current Data Flow Mapping

### Step 1: NowPayments IPN → np-webhook

**File:** `/np-webhook-10-26/app.py`

```python
# Line 442-453: IPN data extraction
outcome_amount = payment_data.get('outcome_amount')  # e.g., "0.00115340416715763"
outcome_currency = payment_data.get('outcome_currency')  # "eth"

# Line 565-582: CoinGecko price fetch
coingecko_price = fetch_coingecko_price("ethereum")  # e.g., $3,000/ETH

# Line 584-596: Calculate USD value
outcome_amount_usd = float(outcome_amount) * coingecko_price
# e.g., 0.00115340416715763 * $3,000 = $3.46 USD

# Line 724-752: Database insert
cur.execute("""
    INSERT INTO private_channel_users_database (
        nowpayments_outcome_amount,        -- ✅ ACTUAL ETH: 0.00115340416715763
        nowpayments_outcome_amount_usd,    -- ✅ ACTUAL USD: $3.46
        ...
    ) VALUES (%s, %s, ...)
""", (outcome_amount, outcome_amount_usd, ...))
```

**Data at this point:**
- ✅ `nowpayments_outcome_amount` = **0.00115340416715763 ETH** (ACTUAL amount in wallet)
- ✅ `nowpayments_outcome_amount_usd` = **$3.46 USD** (ACTUAL USD value)

---

### Step 2: np-webhook → GCWebhook1

**File:** `/np-webhook-10-26/app.py` (lines 843-892)

```python
# Send validated payment to GCWebhook1
payload = {
    'user_id': user_id,
    'closed_channel_id': closed_channel_id,
    'wallet_address': wallet_address,
    'payout_currency': payout_currency,
    'payout_network': payout_network,
    'subscription_time_days': subscription_time_days,
    'subscription_price': subscription_price,
    'outcome_amount_usd': outcome_amount_usd,  # ✅ ACTUAL USD: $3.46
    'nowpayments_payment_id': payment_id,
    'nowpayments_pay_address': pay_address,
    'nowpayments_outcome_amount': outcome_amount  # ✅ ACTUAL ETH: 0.00115340416715763
}
```

**Data at this point:**
- ✅ `outcome_amount_usd` = **$3.46 USD**
- ✅ `nowpayments_outcome_amount` = **0.00115340416715763 ETH**

---

### Step 3: GCWebhook1 → GCSplit1

**File:** `/GCWebhook1-10-26/tph1-10-26.py` (lines 348-361)

```python
# Line 241: Extract ACTUAL outcome USD
outcome_amount_usd = payment_data.get('outcome_amount_usd')  # $3.46 USD

# Line 350: Pass to GCSplit1
task_name = cloudtasks_client.enqueue_gcsplit1_payment_split(
    queue_name=gcsplit1_queue,
    target_url=gcsplit1_url,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_price=outcome_amount_usd  # ✅ ACTUAL USD: $3.46
)
```

**⚠️ CRITICAL OBSERVATION:**
- `nowpayments_outcome_amount` (ACTUAL ETH) is **NOT** passed to GCSplit1
- Only `outcome_amount_usd` (USD equivalent) is passed
- The ACTUAL ETH amount is **LOST** here

**Data at this point:**
- ✅ `subscription_price` = **$3.46 USD** (ACTUAL USD value)
- ❌ `nowpayments_outcome_amount` = **LOST** (not passed downstream)

---

### Step 4: GCSplit1 → GCSplit2 (USDT Estimate)

**File:** `/GCSplit1-10-26/tps1-10-26.py` (lines 327-343)

```python
# Line 329: Calculate adjusted amount (remove TP fee)
tp_flat_fee = config.get('tp_flat_fee')  # e.g., 3%
original_amount, adjusted_amount_usdt = calculate_adjusted_amount(
    subscription_price,  # $3.46
    tp_flat_fee  # 3%
)
# Result: adjusted_amount_usdt = $3.46 * 0.97 = $3.36 USDT

# Line 336: Encrypt token for GCSplit2
encrypted_token = token_manager.encrypt_gcsplit1_to_gcsplit2_token(
    user_id=user_id,
    closed_channel_id=str(closed_channel_id),
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    adjusted_amount_usdt=adjusted_amount_usdt  # $3.36 USDT
)
```

**Data at this point:**
- 🔄 `adjusted_amount_usdt` = **$3.36 USDT** (after TP fee)
- ❌ Still no reference to ACTUAL ETH (0.00115340416715763)

---

### Step 5: GCSplit2 → ChangeNow API (USDT→ETH Estimate)

**File:** `/GCSplit2-10-26/tps2-10-26.py` (lines 127-154)

```python
# Line 127: Call ChangeNow for USDT→ETH estimate
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency="usdt",
    to_currency="eth",
    from_network="eth",
    to_network="eth",
    from_amount=str(adjusted_amount_usdt),  # $3.36 USDT
    flow="standard",
    type_="direct"
)

# Line 145-154: Extract estimate data
from_amount = estimate_response.get('fromAmount')  # e.g., 3.36 USDT
to_amount = estimate_response.get('toAmount')      # e.g., 0.00112 ETH
deposit_fee = estimate_response.get('depositFee')  # e.g., 0
withdrawal_fee = estimate_response.get('withdrawalFee')  # e.g., 0.00003 ETH
```

**Data at this point:**
- 🔄 `to_amount` = **0.00112 ETH** (ChangeNow ESTIMATE for $3.36 USDT)
- ⚠️ This is an ESTIMATE, not the ACTUAL ETH in the wallet

---

### Step 6: GCSplit1 → GCSplit3 (ETH→ClientCurrency Swap)

**File:** `/GCSplit1-10-26/tps1-10-26.py` (lines 449-493)

```python
# Line 450: Calculate pure market conversion
pure_market_eth_value = calculate_pure_market_conversion(
    from_amount_usdt,      # $3.36
    to_amount_eth_post_fee,  # 0.00112 ETH
    deposit_fee,
    withdrawal_fee
)
# Result: pure_market_eth_value ≈ 0.00115 ETH (back-calculated from estimate)

# Line 485: Encrypt token for GCSplit3
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    eth_amount=pure_market_eth_value  # 0.00115 ETH (from calculation, not actual)
)
```

**Data at this point:**
- 🔄 `eth_amount` = **0.00115 ETH** (calculated from ChangeNow estimate)
- ⚠️ This HAPPENS to be close to the actual amount (0.00115340416715763) but is NOT sourced from it

---

### Step 7: GCSplit3 → ChangeNow API (ETH→ClientCurrency Swap)

**File:** `/GCSplit3-10-26/tps3-10-26.py` (lines 127-161)

```python
# Line 127: Create ChangeNow fixed-rate transaction
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="eth",
    to_currency=payout_currency,  # e.g., "btc"
    from_amount=eth_amount,       # 0.00115 ETH (from previous calculation)
    address=wallet_address,
    from_network="eth",
    to_network=payout_network,
    user_id=str(user_id)
)

# Line 144-156: Extract transaction data
cn_api_id = transaction.get('id')
api_from_amount = float(transaction.get('fromAmount', 0))  # ⚠️ ChangeNow says: "4.48 ETH needed"
api_to_amount = float(transaction.get('toAmount', 0))      # e.g., "0.00005 BTC expected"
api_payin_address = transaction.get('payinAddress')        # ChangeNow deposit address
```

**🚨 CRITICAL ISSUE:**
- We asked ChangeNow to convert **0.00115 ETH** → BTC
- ChangeNow responded: **"You need 4.48 ETH for this swap"**
- This is the **3,886x discrepancy** showing up in logs!

**Why the discrepancy?**
Possible reasons:
1. **Minimum swap amount**: ChangeNow has minimum swap amounts (e.g., $5 worth of ETH ≈ 4.48 ETH if miscalculated)
2. **API field confusion**: We may be reading the wrong field (e.g., `toAmount` instead of `fromAmount` in wrong direction)
3. **Fixed-rate vs standard**: Fixed-rate API may have different amount requirements
4. **Fee calculation error**: ChangeNow may be adding fees incorrectly

**Data at this point:**
- ❌ `api_from_amount` = **4.48 ETH** (ChangeNow says this is needed)
- ⚠️ We only have **0.00115 ETH** in the wallet

---

### Step 8: GCSplit3 → GCSplit1 → GCHostPay1

**File:** `/GCSplit1-10-26/tps1-10-26.py` (lines 645-653)

```python
# Line 645: Build GCHostPay token
hostpay_token = build_hostpay_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,      # "eth"
    from_network=from_network,        # "eth"
    from_amount=from_amount,          # ❌ 4.48 ETH (ChangeNow estimate)
    payin_address=payin_address,
    signing_key=tps_hostpay_signing_key
)
```

**Data at this point:**
- ❌ `from_amount` = **4.48 ETH** (ChangeNow estimate from wrong API response)

---

### Step 9: GCHostPay1 → GCHostPay3

**File:** `/GCHostPay1-10-26/tphp1-10-26.py` (lines 447-455)

```python
# Line 447: Encrypt token for GCHostPay3
encrypted_token_payment = token_manager.encrypt_gchostpay1_to_gchostpay3_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,      # "eth"
    from_network=from_network,        # "eth"
    from_amount=from_amount,          # ❌ 4.48 ETH
    payin_address=payin_address,
    context=context
)
```

**Data at this point:**
- ❌ `from_amount` = **4.48 ETH**

---

### Step 10: GCHostPay3 Payment Execution

**File:** `/GCHostPay3-10-26/tphp3-10-26.py` (lines 152-180, 203-207)

```python
# Line 168: Decrypt token
from_amount = decrypted_data['from_amount']  # ❌ 4.48 ETH

print(f"💰 [ENDPOINT] Amount: {from_amount} {from_currency.upper()}")
# Output: "💰 [ENDPOINT] Amount: 4.48 ETH"

# Line 203: Try to pay 4.48 ETH
tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
    to_address=payin_address,
    amount=from_amount,  # ❌ 4.48 ETH
    unique_id=unique_id
)
```

**File:** `/GCHostPay3-10-26/wallet_manager.py` (lines 127-176)

```python
def send_eth_payment_with_infinite_retry(
    self,
    to_address: str,
    amount: float,  # ❌ 4.48 ETH
    unique_id: str
):
    print(f"💸 [ETH_PAYMENT] Amount: {amount} ETH")
    # Output: "💸 [ETH_PAYMENT] Amount: 4.48 ETH"

    # Convert to Wei
    amount_wei = self.w3.to_wei(amount, 'ether')
    # amount_wei = 4,483,328,090,000,000,000 Wei

    # Build transaction
    transaction = {
        'value': amount_wei,  # ❌ Trying to send 4.48 ETH
        ...
    }

    # ❌ RESULT: Transaction timeout (wallet only has 0.00115 ETH)
```

**🚨 FINAL OUTCOME:**
- **Wallet has:** 0.00115340416715763 ETH (from NowPayments)
- **Trying to send:** 4.48332809 ETH (from ChangeNow estimate)
- **Discrepancy:** 3,886x difference
- **Result:** Transaction confirmation timeout after 300s

---

## Root Cause Analysis

### Primary Issue: Lost Data

The ACTUAL `nowpayments_outcome_amount` (0.00115340416715763 ETH) is:
1. ✅ **Stored** in np-webhook database
2. ✅ **Passed** from np-webhook to GCWebhook1
3. ❌ **LOST** when GCWebhook1 sends to GCSplit1 (only USD is passed)
4. ❌ **NEVER RECOVERED** in the downstream flow

### Secondary Issue: Wrong Data Source

Instead of using the ACTUAL ETH amount, the system:
1. Converts USD → USDT estimate (GCSplit2)
2. Converts USDT estimate → ETH estimate (GCSplit2 response)
3. Creates ETH → ClientCurrency swap (GCSplit3)
4. Gets ChangeNow's `fromAmount` which is either:
   - A different estimate
   - A minimum swap amount
   - The wrong API field
   - An error in the API response

### Tertiary Issue: No Validation

There are no checks to validate:
- Does `from_amount` match `nowpayments_outcome_amount`?
- Is `from_amount` within reasonable range of expected value?
- Does the wallet have sufficient balance for `from_amount`?

---

## Proposed Architecture Fix

### Principle

**The `from_amount` field in GCHostPay3 MUST come from `nowpayments_outcome_amount` (the ACTUAL ETH in the wallet), NOT from ChangeNow estimates.**

### Solution 1: Pass ACTUAL ETH Through Entire Chain (Recommended)

**Modify the data flow to preserve `nowpayments_outcome_amount` at every step:**

#### Step 1: GCWebhook1 → GCSplit1

**File:** `/GCWebhook1-10-26/cloudtasks_client.py`

**Current:**
```python
def enqueue_gcsplit1_payment_split(
    self,
    queue_name, target_url, user_id, closed_channel_id,
    wallet_address, payout_currency, payout_network,
    subscription_price  # Only USD
):
    payload = {
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'wallet_address': wallet_address,
        'payout_currency': payout_currency,
        'payout_network': payout_network,
        'subscription_price': subscription_price  # $3.46 USD
    }
```

**Fixed:**
```python
def enqueue_gcsplit1_payment_split(
    self,
    queue_name, target_url, user_id, closed_channel_id,
    wallet_address, payout_currency, payout_network,
    subscription_price,
    nowpayments_outcome_amount  # ✅ ADD ACTUAL ETH
):
    payload = {
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'wallet_address': wallet_address,
        'payout_currency': payout_currency,
        'payout_network': payout_network,
        'subscription_price': subscription_price,  # $3.46 USD
        'nowpayments_outcome_amount': nowpayments_outcome_amount  # ✅ 0.00115340416715763 ETH
    }
```

**File:** `/GCWebhook1-10-26/tph1-10-26.py` (line 352)

**Current:**
```python
task_name = cloudtasks_client.enqueue_gcsplit1_payment_split(
    queue_name=gcsplit1_queue,
    target_url=gcsplit1_url,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_price=outcome_amount_usd  # Only USD
)
```

**Fixed:**
```python
task_name = cloudtasks_client.enqueue_gcsplit1_payment_split(
    queue_name=gcsplit1_queue,
    target_url=gcsplit1_url,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_price=outcome_amount_usd,  # $3.46 USD
    nowpayments_outcome_amount=nowpayments_outcome_amount  # ✅ 0.00115340416715763 ETH
)
```

#### Step 2: GCSplit1 Database Storage

**File:** `/GCSplit1-10-26/database_manager.py`

**Add field to `split_payout_request` table:**
```sql
ALTER TABLE split_payout_request
ADD COLUMN nowpayments_outcome_amount NUMERIC(20, 18);
```

**Modify `insert_split_payout_request()` method:**
```python
def insert_split_payout_request(
    self, user_id, closed_channel_id,
    from_currency, to_currency,
    from_network, to_network,
    from_amount, to_amount,
    client_wallet_address, refund_address,
    flow, type_,
    nowpayments_outcome_amount  # ✅ ADD PARAMETER
):
    cur.execute("""
        INSERT INTO split_payout_request (
            ...,
            nowpayments_outcome_amount
        ) VALUES (..., %s)
    """, (..., nowpayments_outcome_amount))
```

#### Step 3: GCSplit1 → GCSplit3 Token

**File:** `/GCSplit1-10-26/token_manager.py`

**Modify `encrypt_gcsplit1_to_gcsplit3_token()` to include `nowpayments_outcome_amount`:**
```python
def encrypt_gcsplit1_to_gcsplit3_token(
    self, unique_id, user_id, closed_channel_id,
    wallet_address, payout_currency, payout_network,
    eth_amount,
    nowpayments_outcome_amount  # ✅ ADD PARAMETER
):
    data = {
        'unique_id': unique_id,
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'wallet_address': wallet_address,
        'payout_currency': payout_currency,
        'payout_network': payout_network,
        'eth_amount': eth_amount,
        'nowpayments_outcome_amount': nowpayments_outcome_amount  # ✅ ADD FIELD
    }
```

#### Step 4: GCSplit3 → GCSplit1 Response

**File:** `/GCSplit3-10-26/token_manager.py`

**Modify `encrypt_gcsplit3_to_gcsplit1_token()` to preserve `nowpayments_outcome_amount`:**
```python
def encrypt_gcsplit3_to_gcsplit1_token(
    self, unique_id, user_id, closed_channel_id,
    cn_api_id, from_currency, to_currency,
    from_network, to_network,
    from_amount, to_amount,  # from_amount = ChangeNow estimate
    payin_address, payout_address,
    refund_address, flow, type_,
    nowpayments_outcome_amount  # ✅ ADD PARAMETER (ACTUAL ETH)
):
    data = {
        ...,
        'from_amount': from_amount,  # ChangeNow estimate (for logging)
        'nowpayments_outcome_amount': nowpayments_outcome_amount,  # ✅ ACTUAL ETH
        ...
    }
```

#### Step 5: GCSplit1 → GCHostPay1 Token

**File:** `/GCSplit1-10-26/tps1-10-26.py` (line 645)

**Current:**
```python
hostpay_token = build_hostpay_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,
    from_network=from_network,
    from_amount=from_amount,  # ❌ ChangeNow estimate
    payin_address=payin_address,
    signing_key=tps_hostpay_signing_key
)
```

**Fixed:**
```python
# Extract ACTUAL ETH from decrypted token
nowpayments_outcome_amount = decrypted_data.get('nowpayments_outcome_amount')

hostpay_token = build_hostpay_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,
    from_network=from_network,
    from_amount=nowpayments_outcome_amount,  # ✅ ACTUAL ETH
    payin_address=payin_address,
    signing_key=tps_hostpay_signing_key
)

print(f"💰 [ENDPOINT_3] ChangeNow estimate: {from_amount} ETH")
print(f"💰 [ENDPOINT_3] ACTUAL amount to send: {nowpayments_outcome_amount} ETH")
print(f"⚠️ [ENDPOINT_3] Discrepancy: {abs(from_amount - nowpayments_outcome_amount)} ETH")
```

#### Step 6: GCHostPay3 Validation

**File:** `/GCHostPay3-10-26/tphp3-10-26.py`

**Add validation before payment:**
```python
from_amount = decrypted_data['from_amount']  # Now contains ACTUAL ETH

# Validate wallet balance
wallet_balance = wallet_manager.get_wallet_balance()
print(f"💰 [ENDPOINT] Wallet balance: {wallet_balance} ETH")
print(f"💰 [ENDPOINT] Amount to send: {from_amount} ETH")

if from_amount > wallet_balance:
    print(f"❌ [ENDPOINT] Insufficient balance!")
    print(f"   Required: {from_amount} ETH")
    print(f"   Available: {wallet_balance} ETH")
    print(f"   Shortfall: {from_amount - wallet_balance} ETH")
    abort(400, "Insufficient wallet balance")

print(f"✅ [ENDPOINT] Sufficient balance, proceeding with payment")
```

---

## Alternative Solution 2: Bypass Estimates (Simpler)

Instead of passing `nowpayments_outcome_amount` through the entire chain, we could:

1. **Store in database:** np-webhook stores `nowpayments_outcome_amount` in `private_channel_users_database`
2. **Query when needed:** GCHostPay3 queries the database for `nowpayments_outcome_amount` using `user_id` and `closed_channel_id`
3. **Use for payment:** GCHostPay3 uses the queried amount instead of the token amount

**Pros:**
- Simpler implementation (no token changes across 6 services)
- Single source of truth (database)
- Less code changes

**Cons:**
- Requires database query in GCHostPay3
- Couples GCHostPay3 to private_channel_users_database schema
- Harder to trace data flow in logs

---

## Implementation Checklist

### Phase 1: Database Schema Updates ⏳

#### Task 1.1: Add column to split_payout_request table
- **Status:** PENDING
- **SQL:**
  ```sql
  ALTER TABLE split_payout_request
  ADD COLUMN nowpayments_outcome_amount NUMERIC(20, 18);
  ```

#### Task 1.2: Verify column added
- **Status:** PENDING
- **Action:** Query table schema to confirm

---

### Phase 2: Update GCWebhook1 ⏳

#### Task 2.1: Modify cloudtasks_client.py
- **Status:** PENDING
- **File:** `/GCWebhook1-10-26/cloudtasks_client.py`
- **Change:** Add `nowpayments_outcome_amount` parameter to `enqueue_gcsplit1_payment_split()`

#### Task 2.2: Modify tph1-10-26.py
- **Status:** PENDING
- **File:** `/GCWebhook1-10-26/tph1-10-26.py` line 352
- **Change:** Pass `nowpayments_outcome_amount` when calling `enqueue_gcsplit1_payment_split()`

---

### Phase 3: Update GCSplit1 ⏳

#### Task 3.1: Modify database_manager.py
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/database_manager.py`
- **Change:** Add `nowpayments_outcome_amount` parameter to `insert_split_payout_request()`

#### Task 3.2: Modify token_manager.py (GCSplit1→GCSplit3)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/token_manager.py`
- **Change:** Add `nowpayments_outcome_amount` to `encrypt_gcsplit1_to_gcsplit3_token()`

#### Task 3.3: Modify tps1-10-26.py (extract from webhook)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/tps1-10-26.py` line 299
- **Change:** Extract `nowpayments_outcome_amount` from webhook payload

#### Task 3.4: Modify tps1-10-26.py (pass to database)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/tps1-10-26.py` line 462
- **Change:** Pass `nowpayments_outcome_amount` to `insert_split_payout_request()`

#### Task 3.5: Modify tps1-10-26.py (pass to GCSplit3)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/tps1-10-26.py` line 485
- **Change:** Pass `nowpayments_outcome_amount` to `encrypt_gcsplit1_to_gcsplit3_token()`

#### Task 3.6: Modify tps1-10-26.py (use ACTUAL amount for GCHostPay)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/tps1-10-26.py` line 645
- **Change:** Use `nowpayments_outcome_amount` instead of `from_amount` when building hostpay token

---

### Phase 4: Update GCSplit3 ⏳

#### Task 4.1: Modify token_manager.py (decrypt GCSplit1→GCSplit3)
- **Status:** PENDING
- **File:** `/GCSplit3-10-26/token_manager.py`
- **Change:** Extract `nowpayments_outcome_amount` from `decrypt_gcsplit1_to_gcsplit3_token()`

#### Task 4.2: Modify token_manager.py (encrypt GCSplit3→GCSplit1)
- **Status:** PENDING
- **File:** `/GCSplit3-10-26/token_manager.py`
- **Change:** Add `nowpayments_outcome_amount` to `encrypt_gcsplit3_to_gcsplit1_token()`

#### Task 4.3: Modify tps3-10-26.py
- **Status:** PENDING
- **File:** `/GCSplit3-10-26/tps3-10-26.py`
- **Change:** Pass `nowpayments_outcome_amount` through the response token

---

### Phase 5: Update GCHostPay3 Validation ⏳

#### Task 5.1: Add wallet balance check
- **Status:** PENDING
- **File:** `/GCHostPay3-10-26/wallet_manager.py`
- **Change:** Add `get_wallet_balance()` method

#### Task 5.2: Add validation before payment
- **Status:** PENDING
- **File:** `/GCHostPay3-10-26/tphp3-10-26.py` line 203
- **Change:** Validate `from_amount` against wallet balance before payment

#### Task 5.3: Add logging for discrepancies
- **Status:** PENDING
- **File:** `/GCHostPay3-10-26/tphp3-10-26.py`
- **Change:** Log difference between ChangeNow estimate and ACTUAL amount

---

### Phase 6: Testing & Verification ⏳

#### Task 6.1: Test with small payment
- **Status:** PENDING
- **Action:** Create test payment for $5
- **Verify:**
  - `nowpayments_outcome_amount` stored correctly in database
  - Value passed through all services
  - GCHostPay3 receives correct amount
  - Payment executes successfully

#### Task 6.2: Compare amounts in logs
- **Status:** PENDING
- **Action:** Check logs for each service
- **Verify:**
  - np-webhook logs ACTUAL ETH
  - GCSplit1 logs ACTUAL ETH
  - GCHostPay3 logs ACTUAL ETH
  - No 3,886x discrepancy

#### Task 6.3: Verify ChangeNow swap completion
- **Status:** PENDING
- **Action:** Check ChangeNow transaction status
- **Verify:**
  - Transaction completes successfully
  - Client receives expected amount
  - No timeout errors

---

## Expected Outcomes

### Before Fix
```
NowPayments sends: 0.00115340416715763 ETH → Host Wallet
↓
GCSplit2 estimates: $3.36 USDT → 0.00112 ETH (estimate)
↓
GCSplit3 creates swap: 0.00115 ETH → BTC
↓
ChangeNow responds: "Send 4.48 ETH" (WRONG!)
↓
GCHostPay3 tries to send: 4.48 ETH ❌ TIMEOUT
```

### After Fix
```
NowPayments sends: 0.00115340416715763 ETH → Host Wallet
↓ (ACTUAL amount stored)
GCSplit1 passes: 0.00115340416715763 ETH
↓ (ACTUAL amount preserved)
GCSplit3 creates swap: 0.00115340416715763 ETH → BTC
↓ (ChangeNow estimate ignored)
GCHostPay3 sends: 0.00115340416715763 ETH ✅ SUCCESS
```

---

## Financial Impact

### Current Risk
- **Per $5 transaction:** Attempting to send $13,444 worth of ETH
- **Loss if executed:** $13,439 per transaction
- **Good news:** Timeouts preventing actual loss (but users not receiving payouts)

### After Fix
- **Per $5 transaction:** Send actual ~$3.46 worth of ETH (after fees)
- **Expected outcome:** Successful ChangeNow conversion
- **Client receives:** Expected BTC amount
- **Platform retains:** TP fee ($0.17 per $5 transaction)

---

## Questions to Resolve

### Q1: Why does ChangeNow return 4.48 ETH?

**Hypothesis 1:** Minimum swap amount
- ChangeNow may have minimum swap amounts (e.g., $10 worth of ETH)
- Our $3.36 swap is below minimum
- ChangeNow returns minimum required amount (4.48 ETH ≈ $13,440 @ $3,000/ETH is wrong)

**Hypothesis 2:** API field confusion
- We may be reading `toAmount` (BTC) as `fromAmount` (ETH)
- Or reading response from wrong direction

**Hypothesis 3:** Fixed-rate API error
- Fixed-rate endpoint may have bugs
- Standard flow endpoint may work correctly

**Action:** Test with ChangeNow API directly to understand response

### Q2: Should we still use ChangeNow estimates for anything?

**Current use:** Informational only (to compare with actual)
**Proposed use:**
- Log ChangeNow estimate
- Compare with ACTUAL amount
- Alert if discrepancy > 5%
- Always use ACTUAL amount for payment

### Q3: Do we need GCSplit2 at all?

**Current purpose:** Get USDT→ETH estimate (not used for payment)
**Proposed:**
- Keep for logging/monitoring
- Remove from critical path
- Use only for validation checks

---

## Summary

**The Fix:**
1. Pass `nowpayments_outcome_amount` (ACTUAL ETH) through entire payment chain
2. Store in database at every step
3. Use ACTUAL amount (not ChangeNow estimate) for GCHostPay3 payment
4. Add validation to ensure wallet has sufficient balance
5. Log discrepancies between estimates and actuals

**Benefits:**
- Eliminates 3,886x amount discrepancy
- Ensures payments match actual wallet balance
- Prevents transaction timeouts
- Enables successful ChangeNow conversions
- Users receive expected payouts

**Next Steps:**
1. Approve architecture
2. Implement database schema changes
3. Update GCWebhook1, GCSplit1, GCSplit3
4. Add validation to GCHostPay3
5. Deploy and test with small payment
6. Monitor logs for correctness
7. Resume production payments
