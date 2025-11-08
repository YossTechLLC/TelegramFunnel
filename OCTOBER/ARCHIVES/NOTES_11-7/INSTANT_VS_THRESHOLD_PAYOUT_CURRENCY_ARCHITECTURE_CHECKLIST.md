# INSTANT vs THRESHOLD PAYOUT CURRENCY - IMPLEMENTATION CHECKLIST

**Document Purpose:** Step-by-step implementation checklist for enabling dual-mode payout currency routing (ETH for instant, USDT for threshold).

**Created:** 2025-11-07
**Status:** NOT STARTED
**Estimated Time:** 18 hours

---

## Overview

This checklist implements the architecture outlined in `INSTANT_VS_THRESHOLD_PAYOUT_CURRENCY_ARCHITECTURE.md`. The goal is to enable:

- **INSTANT payouts:** Use (actual_eth - TP_FEE) → ClientCurrency swaps
- **THRESHOLD payouts:** Continue using USDT → ClientCurrency swaps (current behavior)

---

## Pre-Implementation Tasks

### 1. Code Backup & Preparation
- [ ] Create backup branch: `git checkout -b backup-pre-currency-routing-$(date +%Y%m%d)`
- [ ] Push backup to remote: `git push origin backup-pre-currency-routing-$(date +%Y%m%d)`
- [ ] Create feature branch: `git checkout -b feature/dual-mode-currency-routing`
- [ ] Document current deployed service versions (run `gcloud run services list --format="table(SERVICE,REVISION)"`)
- [ ] Save current environment variable state for all services

### 2. Environment Verification
- [ ] Verify all services are healthy: `gcloud run services list`
- [ ] Check Cloud Tasks queues are operational: `gcloud tasks queues list`
- [ ] Verify database connection: Test connection to `telepaypsql`
- [ ] Confirm ChangeNow API key is active and has sufficient balance

---

## Phase 1: Token Manager Updates

### 1.1 GCWebhook1 Token Manager

**File:** `/OCTOBER/10-26/GCWebhook1-10-26/cloudtasks_client.py`

- [ ] **Update `enqueue_gcsplit1_payment_split()` method signature**
  - Add parameter: `payout_mode: str = 'instant'`
  - Location: Method definition (approx line 100-120)

- [ ] **Update payload structure**
  - Add to payload dict: `"payout_mode": payout_mode`
  - Location: Inside `enqueue_gcsplit1_payment_split()` method

- [ ] **Test token creation**
  - Create test script to verify token includes `payout_mode`
  - Verify token encrypts/decrypts correctly

**Verification:**
```python
# Test token includes payout_mode
token = cloudtasks_client.enqueue_gcsplit1_payment_split(
    payout_mode='instant',
    # ... other params
)
# Should not error and should include payout_mode in payload
```

---

### 1.2 GCSplit1 Token Manager

**File:** `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py`

#### A) Update encrypt_gcsplit1_to_gcsplit2_token()

- [ ] **Add parameters to method signature:**
  - `swap_currency: str = 'usdt'`
  - `payout_mode: str = 'instant'`
  - Location: Method definition (approx line 80-95)

- [ ] **Update token_data dictionary:**
  - Rename: `adjusted_amount_usdt` → `adjusted_amount` (more generic)
  - Add: `'swap_currency': swap_currency`
  - Add: `'payout_mode': payout_mode`
  - Location: Inside method (approx line 100-115)

- [ ] **Update docstring:**
  - Document new parameters
  - Explain `adjusted_amount` now accepts ETH or USDT

**Code snippet:**
```python
def encrypt_gcsplit1_to_gcsplit2_token(
    self,
    user_id: int,
    closed_channel_id: str,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    adjusted_amount: float,         # ✅ RENAMED
    swap_currency: str = 'usdt',    # ✅ NEW
    payout_mode: str = 'instant',   # ✅ NEW
    actual_eth_amount: float = 0.0
) -> Optional[str]:
    token_data = {
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'wallet_address': wallet_address,
        'payout_currency': payout_currency,
        'payout_network': payout_network,
        'adjusted_amount': adjusted_amount,           # ✅ RENAMED
        'swap_currency': swap_currency,               # ✅ NEW
        'payout_mode': payout_mode,                   # ✅ NEW
        'actual_eth_amount': actual_eth_amount,
        'timestamp': int(time.time())
    }
    # ... encryption logic
```

#### B) Update encrypt_gcsplit2_to_gcsplit1_token()

- [ ] **Add parameters to method signature:**
  - `swap_currency: str`
  - `payout_mode: str`
  - Location: Method definition (approx line 150-165)

- [ ] **Update token_data dictionary:**
  - Add: `'swap_currency': swap_currency`
  - Add: `'payout_mode': payout_mode`
  - Location: Inside method (approx line 170-185)

#### C) Update encrypt_gcsplit1_to_gcsplit3_token()

- [ ] **Add parameters to method signature:**
  - `swap_currency: str = 'usdt'`
  - `payout_mode: str = 'instant'`
  - Location: Method definition (approx line 230-245)

- [ ] **Update token_data dictionary:**
  - Add: `'swap_currency': swap_currency`
  - Add: `'payout_mode': payout_mode`
  - Location: Inside method (approx line 250-265)

#### D) Update decrypt methods

- [ ] **Update `decrypt_gcsplit1_to_gcsplit2_token()`:**
  - Ensure it extracts `swap_currency` with default: `.get('swap_currency', 'usdt')`
  - Ensure it extracts `payout_mode` with default: `.get('payout_mode', 'instant')`

- [ ] **Update `decrypt_gcsplit2_to_gcsplit1_token()`:**
  - Ensure it extracts `swap_currency` with default
  - Ensure it extracts `payout_mode` with default

- [ ] **Update `decrypt_gcsplit3_to_gcsplit1_token()`:**
  - Ensure it extracts `swap_currency` with default
  - Ensure it extracts `payout_mode` with default

**Verification:**
```python
# Test backward compatibility
old_token_without_new_fields = {...}  # Token missing swap_currency/payout_mode
decrypted = token_manager.decrypt_gcsplit1_to_gcsplit2_token(old_token_without_new_fields)
assert decrypted['swap_currency'] == 'usdt'  # Should default
assert decrypted['payout_mode'] == 'instant'  # Should default
```

---

### 1.3 GCSplit2 Token Manager

**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py`

#### A) Update encrypt_gcsplit2_to_gcsplit1_token()

- [ ] **Add parameters to method signature:**
  - `swap_currency: str`
  - `payout_mode: str`
  - Location: Method definition

- [ ] **Update token_data dictionary:**
  - Add: `'swap_currency': swap_currency`
  - Add: `'payout_mode': payout_mode`

#### B) Update decrypt_gcsplit1_to_gcsplit2_token()

- [ ] **Ensure extraction of new fields:**
  - Extract `swap_currency` with default: `.get('swap_currency', 'usdt')`
  - Extract `payout_mode` with default: `.get('payout_mode', 'instant')`

**Verification:**
```python
# Test token round-trip
encrypted = token_manager.encrypt_gcsplit2_to_gcsplit1_token(
    swap_currency='eth',
    payout_mode='instant',
    # ... other params
)
decrypted = token_manager.decrypt_gcsplit2_to_gcsplit1_token(encrypted)
assert decrypted['swap_currency'] == 'eth'
assert decrypted['payout_mode'] == 'instant'
```

---

### 1.4 GCSplit3 Token Manager

**File:** `/OCTOBER/10-26/GCSplit3-10-26/token_manager.py`

#### A) Update decrypt_gcsplit1_to_gcsplit3_token()

- [ ] **Ensure extraction of new fields:**
  - Extract `swap_currency` with default: `.get('swap_currency', 'usdt')`
  - Extract `payout_mode` with default: `.get('payout_mode', 'instant')`

**Verification:**
```python
# Test backward compatibility for GCSplit3 tokens
old_token = {...}  # Without swap_currency/payout_mode
decrypted = token_manager.decrypt_gcsplit1_to_gcsplit3_token(old_token)
assert decrypted['swap_currency'] == 'usdt'  # Should default
```

---

## Phase 2: GCWebhook1 - Pass payout_mode to GCSplit1

### 2.1 GCWebhook1 Main Service

**File:** `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`

- [ ] **Extract payout_mode from database (already exists)**
  - Verify line 290-291: `payout_mode, payout_threshold = db_manager.get_payout_strategy(closed_channel_id)`
  - Confirm it's already being fetched

- [ ] **Pass payout_mode to Cloud Tasks client**
  - Location: Line 353 - `enqueue_gcsplit1_payment_split()` call
  - Add parameter: `payout_mode=payout_mode`

**Code snippet:**
```python
# Around line 353
task_name = cloudtasks_client.enqueue_gcsplit1_payment_split(
    queue_name=gcsplit1_queue,
    target_url=gcsplit1_url,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_price=outcome_amount_usd,
    actual_eth_amount=float(nowpayments_outcome_amount),
    payout_mode=payout_mode  # ✅ ADD THIS
)
```

- [ ] **Add logging for payout_mode**
  - Location: After line 291
  - Log statement: `print(f"🎯 [VALIDATED] Payout mode: {payout_mode}")`

**Verification:**
```bash
# Test with real payment
# Check GCWebhook1 logs should show:
# 🎯 [VALIDATED] Payout mode: instant
# Or:
# 🎯 [VALIDATED] Payout mode: threshold
```

---

## Phase 3: GCSplit1 - Implement Dual-Mode Logic

### 3.1 GCSplit1 Endpoint 1 - Payment Split Request

**File:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

#### A) Extract payout_mode from webhook payload

- [ ] **Add extraction logic**
  - Location: Around line 309 (where other fields are extracted)
  - Extract: `payout_mode = webhook_data.get('payout_mode', 'instant').lower()`

- [ ] **Add logging**
  - Log: `print(f"🎯 [ENDPOINT_1] Payout Mode: {payout_mode}")`

**Code snippet:**
```python
# Around line 309
user_id = webhook_data.get('user_id')
closed_channel_id = webhook_data.get('closed_channel_id')
wallet_address = (webhook_data.get('wallet_address') or '').strip()
payout_currency = (webhook_data.get('payout_currency') or '').strip().lower()
payout_network = (webhook_data.get('payout_network') or '').strip().lower()
subscription_price = webhook_data.get('subscription_price') or webhook_data.get('sub_price') or '0'
actual_eth_amount = float(webhook_data.get('actual_eth_amount', 0.0))
payout_mode = webhook_data.get('payout_mode', 'instant').lower()  # ✅ ADD THIS

print(f"👤 [ENDPOINT_1] User ID: {user_id}")
print(f"🏢 [ENDPOINT_1] Channel ID: {closed_channel_id}")
print(f"💰 [ENDPOINT_1] Subscription Price: ${subscription_price}")
print(f"💎 [ENDPOINT_1] ACTUAL ETH Amount (NowPayments): {actual_eth_amount}")
print(f"🎯 [ENDPOINT_1] Payout Mode: {payout_mode}")  # ✅ ADD THIS
```

#### B) Implement dual-mode swap currency logic

- [ ] **Add swap currency determination**
  - Location: After line 338 (after TP_FEE calculation)
  - Implement conditional logic based on payout_mode

**Code snippet:**
```python
# Around line 338 - AFTER TP fee calculation
tp_flat_fee = config.get('tp_flat_fee')
original_amount, adjusted_amount = calculate_adjusted_amount(subscription_price, tp_flat_fee)

# ✅ ADD: Determine swap currency and amount based on payout_mode
if payout_mode == 'instant':
    # For instant payouts: Use ACTUAL ETH amount from NowPayments
    # Apply TP_FEE to the actual ETH received
    swap_currency = 'eth'
    tp_fee_decimal = float(tp_flat_fee if tp_flat_fee else "3") / 100
    swap_amount = actual_eth_amount * (1 - tp_fee_decimal)

    print(f"⚡ [ENDPOINT_1] INSTANT PAYOUT MODE")
    print(f"💎 [ENDPOINT_1] Swap currency: ETH")
    print(f"💰 [ENDPOINT_1] Actual ETH from NowPayments: {actual_eth_amount}")
    print(f"📊 [ENDPOINT_1] TP Fee: {tp_flat_fee}%")
    print(f"✅ [ENDPOINT_1] Adjusted swap amount: {swap_amount} ETH")

    # Validation warning if actual_eth_amount is missing/zero
    if actual_eth_amount == 0.0:
        print(f"⚠️ [ENDPOINT_1] WARNING: actual_eth_amount is zero - cannot process instant payout")
        abort(400, "Missing actual_eth_amount for instant payout")

else:  # threshold mode (or any other mode defaults to USDT)
    # For threshold payouts: Use USDT equivalent (current behavior)
    swap_currency = 'usdt'
    swap_amount = adjusted_amount  # This is subscription_price - TP_FEE

    print(f"🔄 [ENDPOINT_1] THRESHOLD PAYOUT MODE")
    print(f"💵 [ENDPOINT_1] Swap currency: USDT")
    print(f"✅ [ENDPOINT_1] Adjusted swap amount: {swap_amount} USDT")
```

- [ ] **Import abort if not already imported**
  - Check imports at top of file
  - Add if missing: `from flask import Flask, request, abort, jsonify`

#### C) Update token encryption for GCSplit2

- [ ] **Update encrypt call with new parameters**
  - Location: Around line 346
  - Pass `swap_currency` and `payout_mode` to token

**Code snippet:**
```python
# Around line 346
encrypted_token = token_manager.encrypt_gcsplit1_to_gcsplit2_token(
    user_id=user_id,
    closed_channel_id=str(closed_channel_id),
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    adjusted_amount=swap_amount,      # ✅ RENAMED (now ETH or USDT)
    swap_currency=swap_currency,      # ✅ ADD THIS
    payout_mode=payout_mode,          # ✅ ADD THIS
    actual_eth_amount=actual_eth_amount
)
```

**Verification:**
```bash
# Test instant payout
# Check GCSplit1 logs should show:
# ⚡ [ENDPOINT_1] INSTANT PAYOUT MODE
# 💎 [ENDPOINT_1] Swap currency: ETH
# ✅ [ENDPOINT_1] Adjusted swap amount: 0.00048178 ETH

# Test threshold payout
# Check GCSplit1 logs should show:
# 🔄 [ENDPOINT_1] THRESHOLD PAYOUT MODE
# 💵 [ENDPOINT_1] Swap currency: USDT
# ✅ [ENDPOINT_1] Adjusted swap amount: 1.5467691434 USDT
```

---

### 3.2 GCSplit1 Endpoint 2 - USDT→ETH Estimate Response Handler

**File:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

- [ ] **Extract new fields from GCSplit2 token**
  - Location: Around line 433 (token decryption)
  - Extract: `swap_currency = decrypted_data.get('swap_currency', 'usdt')`
  - Extract: `payout_mode = decrypted_data.get('payout_mode', 'instant')`

- [ ] **Update logging to show swap_currency**
  - Location: Around line 453
  - Update logs to show dynamic currency

**Code snippet:**
```python
# Around line 433
decrypted_data = token_manager.decrypt_gcsplit2_to_gcsplit1_token(encrypted_token)
if not decrypted_data:
    print(f"❌ [ENDPOINT_2] Failed to decrypt token")
    abort(401, "Invalid token")

# Extract data
user_id = decrypted_data['user_id']
closed_channel_id = decrypted_data['closed_channel_id']
wallet_address = decrypted_data['wallet_address']
payout_currency = decrypted_data['payout_currency']
payout_network = decrypted_data['payout_network']
from_amount = decrypted_data['from_amount']
swap_currency = decrypted_data.get('swap_currency', 'usdt')   # ✅ ADD THIS
payout_mode = decrypted_data.get('payout_mode', 'instant')    # ✅ ADD THIS
to_amount_eth_post_fee = decrypted_data['to_amount_post_fee']
deposit_fee = decrypted_data['deposit_fee']
withdrawal_fee = decrypted_data['withdrawal_fee']
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)

print(f"👤 [ENDPOINT_2] User ID: {user_id}")
print(f"🎯 [ENDPOINT_2] Payout Mode: {payout_mode}")           # ✅ ADD THIS
print(f"💱 [ENDPOINT_2] Swap Currency: {swap_currency.upper()}")  # ✅ ADD THIS
print(f"💰 [ENDPOINT_2] From: {from_amount} {swap_currency.upper()}")  # ✅ UPDATED
print(f"💰 [ENDPOINT_2] To (post-fee): {to_amount_eth_post_fee} {payout_currency.upper()}")
print(f"💎 [ENDPOINT_2] ACTUAL ETH (from NowPayments): {actual_eth_amount}")
```

- [ ] **Update database insert to use dynamic from_currency**
  - Location: Around line 478 (`insert_split_payout_request`)
  - Change `from_currency="usdt"` to `from_currency=swap_currency`

**Code snippet:**
```python
# Around line 478
unique_id = database_manager.insert_split_payout_request(
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    from_currency=swap_currency,         # ✅ DYNAMIC: 'eth' or 'usdt'
    to_currency=payout_currency,
    from_network="eth",
    to_network=payout_network,
    from_amount=from_amount,
    to_amount=pure_market_value,
    client_wallet_address=wallet_address,
    refund_address="",
    flow="standard",
    type_="direct",
    actual_eth_amount=actual_eth_amount
)
```

- [ ] **Update token for GCSplit3**
  - Location: Around line 503 (`encrypt_gcsplit1_to_gcsplit3_token`)
  - Pass `swap_currency` and `payout_mode`

**Code snippet:**
```python
# Around line 503
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    eth_amount=from_amount,  # Historical naming
    swap_currency=swap_currency,              # ✅ ADD THIS
    payout_mode=payout_mode,                  # ✅ ADD THIS
    actual_eth_amount=actual_eth_amount
)
```

**Verification:**
```bash
# Check database after endpoint 2 execution
# SELECT from_currency, from_amount FROM split_payout_request ORDER BY created_at DESC LIMIT 1;
# Should show 'eth' for instant, 'usdt' for threshold
```

---

### 3.3 GCSplit1 Endpoint 3 - ETH→Client Swap Response Handler

**File:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

- [ ] **Update from_currency extraction from GCSplit3 token**
  - Location: Around line 584 (token decryption)
  - Verify `from_currency` is extracted (should already exist)

- [ ] **Add logging for from_currency**
  - Location: After token decryption
  - Log: `print(f"💱 [ENDPOINT_3] From Currency: {from_currency.upper()}")`

- [ ] **Update payment amount logic**
  - Location: Around line 620-640 (before building GCHostPay token)
  - Implement conditional logic for ETH vs USDT

**Code snippet:**
```python
# Around line 620-640
print(f"🆔 [ENDPOINT_3] Unique ID: {unique_id}")
print(f"🆔 [ENDPOINT_3] ChangeNow API ID: {cn_api_id}")
print(f"👤 [ENDPOINT_3] User ID: {user_id}")
print(f"💱 [ENDPOINT_3] From Currency: {from_currency.upper()}")  # ✅ ADD LOG
print(f"💰 [ENDPOINT_3] ChangeNow estimate: {from_amount} {from_currency.upper()}")  # ✅ UPDATED
print(f"💎 [ENDPOINT_3] ACTUAL ETH (from NowPayments): {actual_eth_amount} ETH")
print(f"💰 [ENDPOINT_3] To: {to_amount} {to_currency.upper()}")

# ✅ UPDATED: Use ACTUAL amount for payment based on from_currency
if from_currency.lower() == 'eth' and actual_eth_amount > 0:
    # For ETH swaps: Use actual ETH from NowPayments
    payment_amount = actual_eth_amount
    estimated_amount = from_amount
    print(f"⚡ [ENDPOINT_3] ETH swap detected: Using ACTUAL ETH for payment: {payment_amount}")
else:
    # For USDT swaps: Use ChangeNow estimate (no actual_eth_amount applicable)
    payment_amount = from_amount
    estimated_amount = from_amount
    print(f"🔄 [ENDPOINT_3] USDT swap detected: Using ChangeNow estimate: {payment_amount}")
```

- [ ] **Update GCHostPay token builder**
  - Location: Around line 650
  - Use `payment_amount` instead of hardcoded `actual_eth_amount`

**Code snippet:**
```python
# Around line 650
hostpay_token = build_hostpay_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,         # ✅ Already dynamic
    from_network=from_network,
    actual_eth_amount=payment_amount,    # ✅ UPDATED: Use payment_amount
    estimated_eth_amount=estimated_amount,
    payin_address=payin_address,
    signing_key=tps_hostpay_signing_key
)
```

**Verification:**
```bash
# For ETH swaps, check logs:
# ⚡ [ENDPOINT_3] ETH swap detected: Using ACTUAL ETH for payment: 0.0005668

# For USDT swaps, check logs:
# 🔄 [ENDPOINT_3] USDT swap detected: Using ChangeNow estimate: 1.5467691434
```

---

## Phase 4: GCSplit2 - Currency-Aware Estimator

### 4.1 GCSplit2 Main Endpoint

**File:** `/OCTOBER/10-26/GCSplit2-10-26/tps2-10-26.py`

#### A) Extract swap_currency and payout_mode from token

- [ ] **Update token decryption section**
  - Location: Around line 102 (token decryption)
  - Extract new fields with defaults

**Code snippet:**
```python
# Around line 102
decrypted_data = token_manager.decrypt_gcsplit1_to_gcsplit2_token(encrypted_token)
if not decrypted_data:
    print(f"❌ [ENDPOINT] Failed to decrypt token")
    abort(401, "Invalid token")

# Extract data
user_id = decrypted_data['user_id']
closed_channel_id = decrypted_data['closed_channel_id']
wallet_address = decrypted_data['wallet_address']
payout_currency = decrypted_data['payout_currency']
payout_network = decrypted_data['payout_network']
adjusted_amount = decrypted_data['adjusted_amount']           # ✅ GENERIC NAME
swap_currency = decrypted_data.get('swap_currency', 'usdt')   # ✅ ADD THIS
payout_mode = decrypted_data.get('payout_mode', 'instant')    # ✅ ADD THIS
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)
```

#### B) Update logging to show swap_currency

- [ ] **Add mode-specific logging**
  - Location: After token decryption

**Code snippet:**
```python
print(f"🔓 [TOKEN_DEC] GCSplit1→GCSplit2: Decrypting token")
print(f"💰 [TOKEN_DEC] ACTUAL ETH extracted: {actual_eth_amount}")
print(f"✅ [TOKEN_DEC] Token decrypted successfully")

print(f"👤 [ENDPOINT] User ID: {user_id}")
print(f"🏦 [ENDPOINT] Wallet: {wallet_address}")
print(f"🎯 [ENDPOINT] Payout Mode: {payout_mode}")           # ✅ ADD THIS
print(f"💱 [ENDPOINT] Swap Currency: {swap_currency.upper()}")  # ✅ ADD THIS
print(f"💰 [ENDPOINT] Amount: {adjusted_amount} {swap_currency.upper()}")  # ✅ UPDATED
print(f"💎 [ENDPOINT] ACTUAL ETH (from NowPayments): {actual_eth_amount}")
print(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")

# ✅ ADD: Log the swap type
if payout_mode == 'instant':
    print(f"⚡ [ENDPOINT] INSTANT mode: Estimating {swap_currency.upper()}→{payout_currency.upper()}")
else:
    print(f"🔄 [ENDPOINT] THRESHOLD mode: Estimating {swap_currency.upper()}→{payout_currency.upper()}")
```

#### C) Update ChangeNow estimate call

- [ ] **Replace hardcoded "usdt" with swap_currency**
  - Location: Around line 130 (ChangeNow API call)
  - Change: `from_currency="usdt"` → `from_currency=swap_currency`

**Code snippet:**
```python
# Around line 130
print(f"🌐 [ENDPOINT] Calling ChangeNow API for {swap_currency.upper()}→{payout_currency.upper()} estimate (with retry)")

# ✅ UPDATED: Use swap_currency instead of hardcoded "usdt"
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency=swap_currency,        # ✅ DYNAMIC: 'eth' or 'usdt'
    to_currency=payout_currency,
    from_network="eth",                 # Both ETH and USDT are on ETH network
    to_network=payout_network,
    from_amount=str(adjusted_amount),
    flow="standard",
    type_="direct"
)
```

#### D) Update response token encryption

- [ ] **Pass swap_currency and payout_mode to response token**
  - Location: Around line 155 (encrypt response token)

**Code snippet:**
```python
# Around line 155
# Extract estimate data
from_amount = estimate_response.get('fromAmount')
to_amount = estimate_response.get('toAmount')
deposit_fee = estimate_response.get('depositFee', 0)
withdrawal_fee = estimate_response.get('withdrawalFee', 0)

print(f"✅ [ENDPOINT] ChangeNow estimate received")
print(f"💰 [ENDPOINT] From: {from_amount} {swap_currency.upper()}")  # ✅ UPDATED
print(f"💰 [ENDPOINT] To: {to_amount} {payout_currency.upper()} (post-fee)")
print(f"📊 [ENDPOINT] Deposit fee: {deposit_fee}")
print(f"📊 [ENDPOINT] Withdrawal fee: {withdrawal_fee}")

# Encrypt response token for GCSplit1
encrypted_response_token = token_manager.encrypt_gcsplit2_to_gcsplit1_token(
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    from_amount=float(from_amount),          # Amount in swap_currency
    swap_currency=swap_currency,              # ✅ ADD THIS
    payout_mode=payout_mode,                  # ✅ ADD THIS
    to_amount_post_fee=float(to_amount),
    deposit_fee=float(deposit_fee),
    withdrawal_fee=float(withdrawal_fee),
    actual_eth_amount=actual_eth_amount
)
```

**Verification:**
```bash
# Test instant payout estimate
# Check GCSplit2 logs should show:
# ⚡ [ENDPOINT] INSTANT mode: Estimating ETH→SHIB
# 🌐 [ENDPOINT] Calling ChangeNow API for ETH→SHIB estimate
# ✅ [ENDPOINT] ChangeNow estimate received
# 💰 [ENDPOINT] From: 0.00048178 ETH

# Test threshold payout estimate
# Check GCSplit2 logs should show:
# 🔄 [ENDPOINT] THRESHOLD mode: Estimating USDT→SHIB
# 🌐 [ENDPOINT] Calling ChangeNow API for USDT→SHIB estimate
```

---

## Phase 5: GCSplit3 - Currency-Aware Swap Creator

### 5.1 GCSplit3 Main Endpoint

**File:** `/OCTOBER/10-26/GCSplit3-10-26/tps3-10-26.py`

#### A) Extract swap_currency and payout_mode from token

- [ ] **Update token decryption section**
  - Location: Around line 100 (token decryption)

**Code snippet:**
```python
# Around line 100
decrypted_data = token_manager.decrypt_gcsplit1_to_gcsplit3_token(encrypted_token)
if not decrypted_data:
    print(f"❌ [ENDPOINT] Failed to decrypt token")
    abort(401, "Invalid token")

# Extract data
unique_id = decrypted_data['unique_id']
user_id = decrypted_data['user_id']
closed_channel_id = decrypted_data['closed_channel_id']
wallet_address = decrypted_data['wallet_address']
payout_currency = decrypted_data['payout_currency']
payout_network = decrypted_data['payout_network']
swap_amount = decrypted_data['eth_amount']  # Historical naming, actually contains swap amount
swap_currency = decrypted_data.get('swap_currency', 'usdt')   # ✅ ADD THIS
payout_mode = decrypted_data.get('payout_mode', 'instant')    # ✅ ADD THIS
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)
```

#### B) Update logging to show swap_currency

- [ ] **Add mode-specific logging**
  - Location: After token decryption

**Code snippet:**
```python
print(f"🆔 [ENDPOINT] Unique ID: {unique_id}")
print(f"👤 [ENDPOINT] User ID: {user_id}")
print(f"🏦 [ENDPOINT] Wallet: {wallet_address}")
print(f"🎯 [ENDPOINT] Payout Mode: {payout_mode}")           # ✅ ADD THIS
print(f"💱 [ENDPOINT] Swap Currency: {swap_currency.upper()}")  # ✅ ADD THIS
print(f"💰 [ENDPOINT] Swap Amount: {swap_amount} {swap_currency.upper()}")  # ✅ UPDATED
print(f"💎 [ENDPOINT] ACTUAL ETH (from NowPayments): {actual_eth_amount}")
print(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")

# ✅ ADD: Log the swap type
if payout_mode == 'instant':
    print(f"⚡ [ENDPOINT] INSTANT mode: Creating {swap_currency.upper()}→{payout_currency.upper()} swap")
else:
    print(f"🔄 [ENDPOINT] THRESHOLD mode: Creating {swap_currency.upper()}→{payout_currency.upper()} swap")
```

#### C) Update ChangeNow transaction creation

- [ ] **Replace hardcoded "usdt" with swap_currency**
  - Location: Around line 129 (ChangeNow API call)

**Code snippet:**
```python
# Around line 129
print(f"🌐 [ENDPOINT] Creating ChangeNow transaction {swap_currency.upper()}→{payout_currency.upper()} (with retry)")

# ✅ UPDATED: Use swap_currency instead of hardcoded "usdt"
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency=swap_currency,        # ✅ DYNAMIC: 'eth' or 'usdt'
    to_currency=payout_currency,
    from_amount=swap_amount,
    address=wallet_address,
    from_network="eth",                 # Both ETH and USDT are on ETH network
    to_network=payout_network,
    user_id=str(user_id)
)
```

#### D) Update response logging

- [ ] **Update currency display in logs**
  - Location: Around line 159

**Code snippet:**
```python
# Around line 159
# Extract transaction data
cn_api_id = transaction.get('id', '')
api_from_amount = float(transaction.get('fromAmount', 0))
api_to_amount = float(transaction.get('toAmount', 0))
api_from_currency = transaction.get('fromCurrency', swap_currency)  # ✅ UPDATED
api_to_currency = transaction.get('toCurrency', payout_currency)
api_from_network = transaction.get('fromNetwork', 'eth')
api_to_network = transaction.get('toNetwork', payout_network)
api_payin_address = transaction.get('payinAddress', '')
api_payout_address = transaction.get('payoutAddress', wallet_address)
api_refund_address = transaction.get('refundAddress', '')
api_flow = transaction.get('flow', 'standard')
api_type = transaction.get('type', 'direct')

print(f"✅ [ENDPOINT] ChangeNow transaction created")
print(f"🆔 [ENDPOINT] ChangeNow API ID: {cn_api_id}")
print(f"🏦 [ENDPOINT] Payin address: {api_payin_address}")
print(f"💰 [ENDPOINT] From: {api_from_amount} {api_from_currency.upper()}")  # ✅ DYNAMIC
print(f"💰 [ENDPOINT] To: {api_to_amount} {api_to_currency.upper()}")
```

**Verification:**
```bash
# Test instant payout swap creation
# Check GCSplit3 logs should show:
# ⚡ [ENDPOINT] INSTANT mode: Creating ETH→SHIB swap
# 🌐 [ENDPOINT] Creating ChangeNow transaction ETH→SHIB
# ✅ [ENDPOINT] ChangeNow transaction created
# 💰 [ENDPOINT] From: 0.00048178 ETH

# Test threshold payout swap creation
# Check GCSplit3 logs should show:
# 🔄 [ENDPOINT] THRESHOLD mode: Creating USDT→SHIB swap
```

---

## Phase 6: Testing & Validation

### 6.1 Unit Tests

#### A) GCSplit1 Tests

- [ ] **Create test for instant mode calculation**
  ```python
  def test_gcsplit1_instant_mode_eth_calculation():
      """Test ETH swap amount calculation for instant payout."""
      # Input: actual_eth_amount = 0.0005668, TP_FEE = 15%
      # Expected: swap_amount = 0.0005668 * 0.85 = 0.00048178 ETH
      # Expected: swap_currency = 'eth'
      pass
  ```

- [ ] **Create test for threshold mode calculation**
  ```python
  def test_gcsplit1_threshold_mode_usdt_calculation():
      """Test USDT swap amount calculation for threshold payout."""
      # Input: subscription_price = 1.82, TP_FEE = 15%
      # Expected: swap_amount = 1.82 * 0.85 = 1.547 USDT
      # Expected: swap_currency = 'usdt'
      pass
  ```

- [ ] **Create test for missing actual_eth_amount in instant mode**
  ```python
  def test_gcsplit1_instant_mode_missing_eth_error():
      """Test error when actual_eth_amount is missing in instant mode."""
      # Should abort with 400 error
      pass
  ```

#### B) GCSplit2 Tests

- [ ] **Create test for ETH estimate**
  ```python
  def test_gcsplit2_eth_estimate():
      """Test ChangeNow estimate call with ETH currency."""
      # Mock ChangeNow API response for ETH→SHIB
      # Verify from_currency='eth' in API call
      pass
  ```

- [ ] **Create test for USDT estimate**
  ```python
  def test_gcsplit2_usdt_estimate():
      """Test ChangeNow estimate call with USDT currency."""
      # Mock ChangeNow API response for USDT→SHIB
      # Verify from_currency='usdt' in API call
      pass
  ```

#### C) GCSplit3 Tests

- [ ] **Create test for ETH swap creation**
  ```python
  def test_gcsplit3_eth_swap():
      """Test ChangeNow transaction creation with ETH."""
      # Mock ChangeNow API response for ETH→SHIB
      # Verify from_currency='eth' in API call
      pass
  ```

- [ ] **Create test for USDT swap creation**
  ```python
  def test_gcsplit3_usdt_swap():
      """Test ChangeNow transaction creation with USDT."""
      # Mock ChangeNow API response for USDT→SHIB
      # Verify from_currency='usdt' in API call
      pass
  ```

#### D) Token Manager Tests

- [ ] **Create test for backward compatibility**
  ```python
  def test_token_backward_compatibility():
      """Test old tokens without swap_currency/payout_mode still work."""
      # Create token without new fields
      # Verify decrypt returns defaults (usdt, instant)
      pass
  ```

- [ ] **Create test for new token fields**
  ```python
  def test_token_new_fields():
      """Test new tokens include swap_currency and payout_mode."""
      # Create token with new fields
      # Verify decrypt returns correct values
      pass
  ```

**Test Execution:**
```bash
# Run all unit tests
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26
python -m pytest tests/ -v

# Or run specific test files
python -m pytest tests/test_gcsplit1.py -v
python -m pytest tests/test_gcsplit2.py -v
python -m pytest tests/test_gcsplit3.py -v
```

---

### 6.2 Integration Tests

#### A) End-to-End Test: Instant Payout (ETH→SHIB)

- [ ] **Test Setup:**
  - Channel with `payout_mode='instant'`
  - Payout currency: SHIB
  - Subscription price: $1.35
  - NowPayments sends: 0.0005668 ETH

- [ ] **Test Execution Steps:**
  1. Trigger payment in NowPayments (or use test endpoint)
  2. Monitor GCWebhook1 logs for payout_mode detection
  3. Monitor GCSplit1 logs for ETH swap calculation
  4. Monitor GCSplit2 logs for ETH→SHIB estimate
  5. Monitor GCSplit3 logs for ETH→SHIB swap creation
  6. Monitor GCHostPay3 logs for native ETH payment
  7. Verify ChangeNow receives ETH and sends SHIB

- [ ] **Expected Results:**
  - GCWebhook1: Routes to GCSplit1 with payout_mode='instant'
  - GCSplit1: Calculates swap_amount = 0.00048178 ETH
  - GCSplit2: Calls ChangeNow with from_currency='eth'
  - GCSplit3: Creates ChangeNow transaction with from_currency='eth'
  - GCHostPay3: Sends 0.00048178 ETH to ChangeNow payin address
  - ChangeNow: Converts ETH→SHIB and sends to client wallet
  - Database: All tables show from_currency='eth'

- [ ] **Validation Queries:**
  ```sql
  -- Check split_payout_request
  SELECT unique_id, from_currency, from_amount, to_currency, to_amount
  FROM split_payout_request
  WHERE user_id = <test_user_id>
  ORDER BY created_at DESC LIMIT 1;
  -- Expected: from_currency='eth', from_amount≈0.00048178

  -- Check split_payout_que
  SELECT unique_id, from_currency, from_amount, cn_api_id
  FROM split_payout_que
  WHERE unique_id = <unique_id>;
  -- Expected: from_currency='eth'

  -- Check split_payout_hostpay
  SELECT unique_id, from_currency, from_amount, payment_status
  FROM split_payout_hostpay
  WHERE unique_id = <unique_id>;
  -- Expected: from_currency='eth', payment_status='completed'
  ```

#### B) End-to-End Test: Threshold Payout (USDT→SHIB)

- [ ] **Test Setup:**
  - Channel with `payout_mode='threshold'`, `payout_threshold=$5.00`
  - Payout currency: SHIB
  - Multiple payments totaling $5.40 after accumulation

- [ ] **Test Execution Steps:**
  1. Make multiple payments to reach threshold
  2. Wait for micro-batch ETH→USDT conversion
  3. Wait for batch processor to trigger payout
  4. Monitor GCSplit1 logs for USDT swap setup
  5. Monitor GCSplit2 logs for USDT→SHIB estimate
  6. Monitor GCSplit3 logs for USDT→SHIB swap creation
  7. Monitor GCHostPay3 logs for ERC-20 USDT transfer
  8. Verify ChangeNow receives USDT and sends SHIB

- [ ] **Expected Results:**
  - GCBatchProcessor: Detects threshold met, creates batch
  - GCSplit1: Uses swap_currency='usdt', swap_amount=5.40
  - GCSplit2: Calls ChangeNow with from_currency='usdt'
  - GCSplit3: Creates ChangeNow transaction with from_currency='usdt'
  - GCHostPay3: Sends 5.40 USDT to ChangeNow payin address
  - ChangeNow: Converts USDT→SHIB and sends to client wallet
  - Database: All tables show from_currency='usdt'

- [ ] **Validation Queries:**
  ```sql
  -- Check split_payout_request
  SELECT unique_id, from_currency, from_amount, to_currency, to_amount
  FROM split_payout_request
  WHERE user_id = <test_user_id>
  ORDER BY created_at DESC LIMIT 1;
  -- Expected: from_currency='usdt', from_amount≈5.40

  -- Check split_payout_hostpay
  SELECT unique_id, from_currency, from_amount, payment_status
  FROM split_payout_hostpay
  WHERE unique_id = <unique_id>;
  -- Expected: from_currency='usdt', payment_status='completed'
  ```

#### C) Test Backward Compatibility

- [ ] **Test old workflow without payout_mode**
  - Manually enqueue task to GCSplit1 WITHOUT payout_mode field
  - Verify system defaults to 'instant' and 'usdt'
  - Verify payment completes successfully

**Verification:**
```bash
# Check logs show defaults being used
# GCSplit1 should log:
# 🎯 [ENDPOINT_1] Payout Mode: instant (defaulted)
# 🔄 [ENDPOINT_1] THRESHOLD PAYOUT MODE (because defaults to USDT)
```

---

### 6.3 ChangeNow Minimum Amount Testing

- [ ] **Test minimum amount handling for ETH**
  - Query ChangeNow minimum: `GET /min-amount?from_currency=eth&to_currency=shib`
  - Note minimum amount (e.g., 0.001 ETH)
  - Test with amount BELOW minimum
  - Verify error handling (should get 400 from ChangeNow)

- [ ] **Optional: Implement minimum amount pre-check**
  - Add check in GCSplit2 before calling estimate API
  - If below minimum, log warning and optionally fallback to USDT
  - This is OPTIONAL for initial deployment

**Fallback Logic (Optional):**
```python
# In GCSplit2, before estimate call
if payout_mode == 'instant' and swap_currency == 'eth':
    min_amount = changenow_client.get_minimum_amount(
        from_currency='eth',
        to_currency=payout_currency
    )

    if adjusted_amount < min_amount:
        print(f"⚠️ [ENDPOINT] ETH amount {adjusted_amount} below minimum {min_amount}")
        print(f"🔄 [ENDPOINT] Falling back to USDT swap")
        # Fallback to USDT
        swap_currency = 'usdt'
        # Recalculate amount in USDT (would need exchange rate API)
```

---

## Phase 7: Deployment

### 7.1 Pre-Deployment Checklist

- [ ] **Code Review:**
  - All token manager changes reviewed
  - All service endpoint changes reviewed
  - Logging statements consistent with existing style

- [ ] **Testing Complete:**
  - All unit tests passing
  - Integration tests passing for both modes
  - Backward compatibility verified

- [ ] **Documentation:**
  - PROGRESS.md updated with changes
  - DECISIONS.md updated with architectural decisions
  - No bugs found → BUGS.md not updated
  - Architecture documents reviewed

- [ ] **Database Verification:**
  - Confirmed `from_currency` columns exist and are VARCHAR(10)
  - Confirmed columns accept 'eth', 'usdt', and other currency codes
  - No schema migrations needed

---

### 7.2 Build & Push Docker Images

#### GCWebhook1

- [ ] **Build image:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26
  docker build -t gcr.io/telepay-459221/gcwebhook1-10-26:dual-currency .
  ```

- [ ] **Push image:**
  ```bash
  docker push gcr.io/telepay-459221/gcwebhook1-10-26:dual-currency
  ```

#### GCSplit1

- [ ] **Build image:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit1-10-26
  docker build -t gcr.io/telepay-459221/gcsplit1-10-26:dual-currency .
  ```

- [ ] **Push image:**
  ```bash
  docker push gcr.io/telepay-459221/gcsplit1-10-26:dual-currency
  ```

#### GCSplit2

- [ ] **Build image:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit2-10-26
  docker build -t gcr.io/telepay-459221/gcsplit2-10-26:dual-currency .
  ```

- [ ] **Push image:**
  ```bash
  docker push gcr.io/telepay-459221/gcsplit2-10-26:dual-currency
  ```

#### GCSplit3

- [ ] **Build image:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit3-10-26
  docker build -t gcr.io/telepay-459221/gcsplit3-10-26:dual-currency .
  ```

- [ ] **Push image:**
  ```bash
  docker push gcr.io/telepay-459221/gcsplit3-10-26:dual-currency
  ```

---

### 7.3 Staged Deployment

#### Stage 1: Deploy GCWebhook1 Only (Canary)

- [ ] **Deploy GCWebhook1:**
  ```bash
  gcloud run deploy gcwebhook1-10-26 \
    --image gcr.io/telepay-459221/gcwebhook1-10-26:dual-currency \
    --region us-central1 \
    --platform managed \
    --no-traffic
  ```

- [ ] **Route 10% traffic to new revision:**
  ```bash
  gcloud run services update-traffic gcwebhook1-10-26 \
    --to-revisions=<new-revision>=10 \
    --region us-central1
  ```

- [ ] **Monitor for 1 hour:**
  - Check logs for `payout_mode` being passed
  - Verify no errors
  - Confirm old flow still works (GCSplit1 defaults to 'instant'/'usdt')

- [ ] **If successful, route 100% traffic:**
  ```bash
  gcloud run services update-traffic gcwebhook1-10-26 \
    --to-latest \
    --region us-central1
  ```

**Rollback Command (if needed):**
```bash
gcloud run services update-traffic gcwebhook1-10-26 \
  --to-revisions=<previous-revision>=100 \
  --region us-central1
```

---

#### Stage 2: Deploy GCSplit Services (Full Deployment)

- [ ] **Deploy GCSplit1:**
  ```bash
  gcloud run deploy gcsplit1-10-26 \
    --image gcr.io/telepay-459221/gcsplit1-10-26:dual-currency \
    --region us-central1 \
    --platform managed
  ```

- [ ] **Deploy GCSplit2:**
  ```bash
  gcloud run deploy gcsplit2-10-26 \
    --image gcr.io/telepay-459221/gcsplit2-10-26:dual-currency \
    --region us-central1 \
    --platform managed
  ```

- [ ] **Deploy GCSplit3:**
  ```bash
  gcloud run deploy gcsplit3-10-26 \
    --image gcr.io/telepay-459221/gcsplit3-10-26:dual-currency \
    --region us-central1 \
    --platform managed
  ```

- [ ] **Verify all services healthy:**
  ```bash
  curl https://gcsplit1-10-26-<project-hash>.us-central1.run.app/health
  curl https://gcsplit2-10-26-<project-hash>.us-central1.run.app/health
  curl https://gcsplit3-10-26-<project-hash>.us-central1.run.app/health
  ```

---

### 7.4 Post-Deployment Monitoring (First 24 Hours)

#### Immediate Checks (First 2 Hours)

- [ ] **Monitor service logs:**
  ```bash
  # GCWebhook1
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcwebhook1-10-26" --limit 50 --format json

  # GCSplit1
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26" --limit 50 --format json

  # GCSplit2
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit2-10-26" --limit 50 --format json

  # GCSplit3
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit3-10-26" --limit 50 --format json
  ```

- [ ] **Check for errors:**
  - Any 400 errors from ChangeNow API?
  - Any token decryption failures?
  - Any missing field errors?

- [ ] **Verify instant payments work:**
  - Make test payment with instant payout
  - Check logs show "INSTANT PAYOUT MODE"
  - Check logs show "Swap currency: ETH"
  - Verify payment completes

- [ ] **Verify threshold payments unchanged:**
  - Check existing threshold accumulations
  - Verify they still use USDT swaps
  - Verify no disruption to existing flow

#### Extended Monitoring (Next 22 Hours)

- [ ] **Monitor payment success rates:**
  ```sql
  -- Check instant payout success rate
  SELECT
    COUNT(*) as total_instant,
    SUM(CASE WHEN payment_status = 'completed' THEN 1 ELSE 0 END) as completed,
    ROUND(100.0 * SUM(CASE WHEN payment_status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
  FROM split_payout_hostpay
  WHERE from_currency = 'eth'
  AND created_at >= NOW() - INTERVAL '24 hours';

  -- Check threshold payout success rate (unchanged)
  SELECT
    COUNT(*) as total_threshold,
    SUM(CASE WHEN payment_status = 'completed' THEN 1 ELSE 0 END) as completed,
    ROUND(100.0 * SUM(CASE WHEN payment_status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
  FROM split_payout_hostpay
  WHERE from_currency = 'usdt'
  AND created_at >= NOW() - INTERVAL '24 hours';
  ```

- [ ] **Monitor ChangeNow minimum amount errors:**
  ```bash
  # Check for 400 errors in GCSplit2
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit2-10-26 AND jsonPayload.message=~'400'" --limit 50
  ```

- [ ] **Check database consistency:**
  ```sql
  -- Check for currency mismatches across tables
  SELECT
    spr.unique_id,
    spr.from_currency as request_currency,
    spq.from_currency as que_currency,
    sph.from_currency as hostpay_currency
  FROM split_payout_request spr
  LEFT JOIN split_payout_que spq ON spr.unique_id = spq.unique_id
  LEFT JOIN split_payout_hostpay sph ON spr.unique_id = sph.unique_id
  WHERE spr.created_at >= NOW() - INTERVAL '24 hours'
  AND (spr.from_currency != spq.from_currency OR spr.from_currency != sph.from_currency);
  -- Should return 0 rows
  ```

---

## Phase 8: Post-Deployment Validation

### 8.1 Week 1 Metrics Collection

- [ ] **Collect instant payout metrics:**
  ```sql
  -- ETH→Client swaps (instant)
  SELECT
    COUNT(*) as total_eth_swaps,
    AVG(from_amount) as avg_eth_amount,
    SUM(from_amount) as total_eth_volume,
    COUNT(DISTINCT user_id) as unique_users
  FROM split_payout_request
  WHERE from_currency = 'eth'
  AND created_at >= NOW() - INTERVAL '7 days';
  ```

- [ ] **Collect threshold payout metrics:**
  ```sql
  -- USDT→Client swaps (threshold)
  SELECT
    COUNT(*) as total_usdt_swaps,
    AVG(from_amount) as avg_usdt_amount,
    SUM(from_amount) as total_usdt_volume,
    COUNT(DISTINCT user_id) as unique_users
  FROM split_payout_request
  WHERE from_currency = 'usdt'
  AND created_at >= NOW() - INTERVAL '7 days';
  ```

- [ ] **Compare success rates:**
  ```sql
  SELECT
    from_currency,
    COUNT(*) as total_payments,
    SUM(CASE WHEN payment_status = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN payment_status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
  FROM split_payout_hostpay
  WHERE created_at >= NOW() - INTERVAL '7 days'
  GROUP BY from_currency;
  ```

- [ ] **Track ChangeNow minimum amount failures:**
  ```sql
  -- Check for payments that failed due to minimum amounts
  -- (Would need to add error logging to track this)
  -- Alternative: Count 400 errors in logs
  ```

---

### 8.2 Cost-Benefit Analysis

- [ ] **Calculate ChangeNow fee savings:**
  - Compare ETH pair fees vs historical USDT pair fees
  - Expected: ~0.5% savings on instant payouts

- [ ] **Measure swap rate improvements:**
  - Compare actual received amounts for ETH vs USDT swaps
  - Expected: 1-2% better rates on ETH pairs

- [ ] **Assess minimum amount rejection reduction:**
  - Count 400 errors before vs after
  - Expected: ~10% reduction in rejections

- [ ] **Measure latency improvements:**
  - Compare average time from payment to completion
  - Expected: ~20% faster for instant payouts

---

### 8.3 Documentation Updates

- [ ] **Update PROGRESS.md:**
  ```markdown
  ## 2025-11-07: Dual-Mode Currency Routing Implementation
  - ✅ Implemented payout_mode-based swap currency routing
  - ✅ Instant payouts now use ETH→Client swaps
  - ✅ Threshold payouts continue using USDT→Client swaps
  - ✅ All services deployed and tested
  - ✅ Backward compatibility maintained
  ```

- [ ] **Update DECISIONS.md:**
  ```markdown
  ## 2025-11-07: Dual-Mode Currency Routing Architecture
  - **Decision:** Implement dynamic swap currency based on payout_mode
  - **Rationale:** ETH swaps provide better rates and lower minimums for instant payouts
  - **Implementation:** Added payout_mode and swap_currency to token chain
  - **Impact:** Estimated $18k annual savings, 20% faster instant payouts
  ```

- [ ] **Update architecture documents:**
  - Add actual metrics to `INSTANT_VS_THRESHOLD_PAYOUT_CURRENCY_ARCHITECTURE.md`
  - Update any other relevant documentation

---

## Phase 9: Optional Enhancements

### 9.1 Minimum Amount Pre-Check (Optional)

- [ ] **Implement ChangeNow minimum amount pre-check:**
  - Add method to `changenow_client.py`: `get_minimum_amount()`
  - Add logic in GCSplit2 to check minimum before estimate
  - Implement fallback to USDT if below minimum

**Implementation:**
```python
# In changenow_client.py
def get_minimum_amount(self, from_currency: str, to_currency: str) -> float:
    """
    Get minimum amount for a currency pair.

    Args:
        from_currency: Source currency code
        to_currency: Target currency code

    Returns:
        Minimum amount in from_currency
    """
    url = f"{self.base_url}/min-amount/{from_currency}_{to_currency}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return float(data.get('minAmount', 0))
    return 0
```

```python
# In GCSplit2 tps2-10-26.py, before estimate call
if payout_mode == 'instant' and swap_currency == 'eth':
    min_amount = changenow_client.get_minimum_amount(
        from_currency='eth',
        to_currency=payout_currency
    )

    if adjusted_amount < min_amount:
        print(f"⚠️ [ENDPOINT] ETH amount {adjusted_amount} below minimum {min_amount}")
        print(f"🔄 [ENDPOINT] Falling back to USDT swap")

        # Fallback logic
        swap_currency = 'usdt'
        # Recalculate adjusted_amount in USDT
        # (Would need ETH→USD rate API call)
```

---

### 9.2 Enhanced Monitoring & Alerts (Optional)

- [ ] **Set up Cloud Monitoring alerts:**
  - Alert on ChangeNow 400 errors (minimum amounts)
  - Alert on ETH swap success rate below 95%
  - Alert on USDT swap success rate change (should stay same)

- [ ] **Create custom dashboard:**
  - Panel: Instant vs Threshold payment volume
  - Panel: ETH vs USDT swap success rates
  - Panel: Average payment amounts by currency
  - Panel: ChangeNow API response times

---

### 9.3 Performance Optimization (Optional)

- [ ] **Cache ChangeNow minimum amounts:**
  - Store minimums in Redis/Memcache
  - Refresh every 1 hour
  - Reduces API calls to ChangeNow

- [ ] **Parallel estimate/swap creation:**
  - Currently: GCSplit1 → GCSplit2 → GCSplit1 → GCSplit3 (sequential)
  - Optimization: Combine estimate + swap creation in single service
  - Expected: 30-40% latency reduction

---

## Rollback Plan

### If Critical Issues Arise

#### Immediate Rollback (< 5 minutes)

- [ ] **Rollback all services to previous revision:**
  ```bash
  # Get previous revision IDs
  gcloud run revisions list --service=gcwebhook1-10-26 --region=us-central1
  gcloud run revisions list --service=gcsplit1-10-26 --region=us-central1
  gcloud run revisions list --service=gcsplit2-10-26 --region=us-central1
  gcloud run revisions list --service=gcsplit3-10-26 --region=us-central1

  # Rollback each service
  gcloud run services update-traffic gcwebhook1-10-26 --to-revisions=<prev-rev>=100 --region=us-central1
  gcloud run services update-traffic gcsplit1-10-26 --to-revisions=<prev-rev>=100 --region=us-central1
  gcloud run services update-traffic gcsplit2-10-26 --to-revisions=<prev-rev>=100 --region=us-central1
  gcloud run services update-traffic gcsplit3-10-26 --to-revisions=<prev-rev>=100 --region=us-central1
  ```

- [ ] **Verify rollback successful:**
  ```bash
  # Check all services are on previous revision
  gcloud run services describe gcwebhook1-10-26 --region=us-central1
  # ... repeat for all services
  ```

- [ ] **Monitor for recovery:**
  - Check error rate drops
  - Verify payments resume normally
  - Check database for any stuck records

#### Post-Rollback Analysis

- [ ] **Identify root cause:**
  - Review error logs
  - Check specific failure point (which service?)
  - Identify what assumption was incorrect

- [ ] **Document issue in BUGS.md:**
  ```markdown
  ## 2025-11-XX: Dual-Currency Rollback - [Issue Description]
  - **Problem:** [Describe what went wrong]
  - **Root Cause:** [Why it failed]
  - **Resolution:** Rolled back to previous revision
  - **Next Steps:** [What needs to be fixed before retry]
  ```

- [ ] **Plan fix and redeployment:**
  - Fix identified issue
  - Add additional tests for failure scenario
  - Schedule new deployment with extra monitoring

---

## Success Criteria

### Deployment Considered Successful When:

- [ ] **No errors for 24 hours:**
  - No 500 errors in any service
  - No token decryption failures
  - No database consistency issues

- [ ] **Instant payouts working:**
  - At least 10 successful instant payouts with ETH swaps
  - Success rate ≥ 95%
  - Database shows from_currency='eth' correctly

- [ ] **Threshold payouts unchanged:**
  - Threshold payouts still use USDT swaps
  - Success rate unchanged from previous week
  - No disruption to accumulation flow

- [ ] **Performance improvements visible:**
  - Instant payouts are faster (measurable latency reduction)
  - ChangeNow fees are lower for ETH pairs
  - Fewer minimum amount rejections

---

## Checklist Summary

### Total Tasks: ~120

#### Phase 1 (Token Managers): 25 tasks
#### Phase 2 (GCWebhook1): 5 tasks
#### Phase 3 (GCSplit1): 15 tasks
#### Phase 4 (GCSplit2): 10 tasks
#### Phase 5 (GCSplit3): 10 tasks
#### Phase 6 (Testing): 25 tasks
#### Phase 7 (Deployment): 15 tasks
#### Phase 8 (Validation): 10 tasks
#### Phase 9 (Optional): 5 tasks

---

## Estimated Timeline

| Phase | Duration | Dependency |
|-------|----------|------------|
| **Pre-Implementation** | 1 hour | None |
| **Phase 1: Token Managers** | 3 hours | Pre-Implementation |
| **Phase 2: GCWebhook1** | 1 hour | Phase 1 |
| **Phase 3: GCSplit1** | 2 hours | Phase 1 |
| **Phase 4: GCSplit2** | 1.5 hours | Phase 1 |
| **Phase 5: GCSplit3** | 1.5 hours | Phase 1 |
| **Phase 6: Testing** | 4 hours | Phases 2-5 |
| **Phase 7: Deployment** | 2 hours | Phase 6 |
| **Phase 8: Monitoring** | 24 hours (passive) | Phase 7 |
| **Phase 9: Optional** | 3 hours | Phase 8 |

**Total Active Work: ~16 hours**
**Total Timeline (with monitoring): ~40 hours**

---

## Final Notes

- This checklist is comprehensive but can be adapted based on specific needs
- Each task has clear acceptance criteria
- Rollback plan is in place for safety
- Success criteria are measurable
- Optional enhancements can be done later

**Ready to begin implementation?** Start with Phase 1, Section 1.1 (GCWebhook1 Token Manager)!

---

**Document Version:** 1.0
**Created:** 2025-11-07
**Last Updated:** 2025-11-07
**Status:** READY FOR IMPLEMENTATION
