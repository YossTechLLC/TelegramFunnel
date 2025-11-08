# INSTANT vs THRESHOLD PAYOUT CURRENCY ARCHITECTURE

**Document Purpose:** Architectural design for implementing dual-mode payout currency handling based on payout_scheme. Ensures optimal swap rates by using different source currencies for instant vs threshold payouts.

**Created:** 2025-11-07

---

## Problem Statement

### Current Issue

The current architecture has an **implicit assumption** that all payments route through **USDT→ClientCurrency** swaps, regardless of payout scheme:

```
Current Flow (ALL PAYOUTS):
Payment (ETH from NowPayments)
    ↓
GCWebhook1 (routes based on payout_scheme)
    ↓
GCSplit1 (calculates adjusted_amount_usdt after TP_FEE)
    ↓
GCSplit2 (estimates USDT→ClientCurrency)  ❌ ALWAYS USDT
    ↓
GCSplit3 (creates USDT→ClientCurrency swap)  ❌ ALWAYS USDT
    ↓
GCHostPay (sends USDT to ChangeNow)  ❌ ALWAYS USDT
```

**This works fine for THRESHOLD payouts** (where ETH is first converted to USDT for accumulation stability), but **fails to optimize INSTANT payouts** where we should swap directly from the actual ETH received.

### Specific Example from Logs

From the user's log (2025-11-07 07:47:15 EST):

```
💰 [ENDPOINT] Amount: 1.5467691434000002 USDT
💎 [ENDPOINT] ACTUAL ETH (from NowPayments): 0.0005668
🎯 [ENDPOINT] Target: SHIB on ETH
📈 [CHANGENOW_ESTIMATE_V2] Getting estimate: 1.5467691434000002 USDT → SHIB
📊 [CHANGENOW_ESTIMATE_V2] Response status: 400
```

**Analysis:**
- `Amount: 1.5467691434000002 USDT` = This is `subscription_price - TP_FEE` (15%)
- `ACTUAL ETH: 0.0005668` = This is the ACTUAL crypto received from NowPayments (does NOT include TP_FEE deduction)
- For an **instant payout**, the swap should be: `(0.0005668 ETH - 15% TP_FEE) → SHIB`
- Instead, the system tried: `1.5467691434 USDT → SHIB` ❌

### Why This Matters

**For INSTANT payouts, using ETH→ClientCurrency is superior:**

| Aspect | USDT→ClientCurrency (current) | ETH→ClientCurrency (proposed) |
|--------|-------------------------------|-------------------------------|
| **Swap rates** | Often poor liquidity for small USDT amounts | Better liquidity for ETH pairs |
| **Minimum amounts** | ChangeNow minimums often reject small USDT swaps | ETH minimums are more favorable |
| **Fees** | Higher fees on USDT pairs | Lower fees on ETH pairs |
| **Speed** | Two-step process (conceptually) | Single-step direct conversion |
| **Use case** | Accumulation stability (threshold) | Immediate conversion (instant) |

**For THRESHOLD payouts, using USDT→ClientCurrency is correct:**
- ETH is first accumulated and converted to USDT in micro-batches
- USDT provides price stability during accumulation period
- Clients are paid in their chosen currency after threshold is met
- Two-swap architecture (ETH→USDT→ClientCurrency) is intentional and working correctly

---

## Proposed Solution: Dual-Mode Currency Routing

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ GCWebhook1: Detect payout_scheme and route accordingly          │
└─────────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
          ▼ instant                         ▼ threshold
┌─────────────────────────┐       ┌─────────────────────────┐
│ INSTANT PAYOUT PATH     │       │ THRESHOLD PAYOUT PATH   │
│ (ETH→ClientCurrency)    │       │ (USDT→ClientCurrency)   │
└─────────────────────────┘       └─────────────────────────┘
          │                                 │
          │                                 │
          ▼                                 ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│ GCSplit1                │       │ GCAccumulator           │
│ (orchestrator)          │       │ (stores pending)        │
└────────┬────────────────┘       └────────┬────────────────┘
         │                                 │
         │ payout_mode='instant'           │ (accumulates)
         │ currency='eth'                  │
         │ amount=(actual_eth - TP_FEE)    │
         │                                 ▼
         ▼                         (ETH→USDT conversion)
┌─────────────────────────┐               │
│ GCSplit2                │               │
│ Estimate:               │               │
│ ETH→ClientCurrency ✅   │               │
└────────┬────────────────┘               │
         │                                 │
         ▼                                 ▼
┌─────────────────────────┐       (Client batching)
│ GCSplit3                │               │
│ Create Swap:            │               │
│ ETH→ClientCurrency ✅   │               ▼
└────────┬────────────────┘       ┌─────────────────────────┐
         │                        │ GCSplit2                │
         │                        │ Estimate:               │
         │                        │ USDT→ClientCurrency ✅  │
         │                        └────────┬────────────────┘
         │                                 │
         │                                 ▼
         │                        ┌─────────────────────────┐
         │                        │ GCSplit3                │
         │                        │ Create Swap:            │
         │                        │ USDT→ClientCurrency ✅  │
         │                        └────────┬────────────────┘
         │                                 │
         └────────────────┬────────────────┘
                          │
                          ▼
                ┌─────────────────────────┐
                │ GCHostPay1              │
                │ (sends correct currency)│
                └─────────────────────────┘
```

---

## Detailed Implementation Plan

### Phase 1: Token Chain - Pass `payout_mode` Through Services

#### 1.1 GCWebhook1 Changes

**File:** `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`

**Current:** GCWebhook1 detects `payout_mode` (line 290-291) but doesn't pass it to GCSplit1.

**Change:** Pass `payout_mode` in the Cloud Task payload to GCSplit1.

**Location:** Line 353 - `enqueue_gcsplit1_payment_split()`

**New payload:**
```python
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

---

#### 1.2 CloudTasks Client Changes (GCWebhook1)

**File:** `/OCTOBER/10-26/GCWebhook1-10-26/cloudtasks_client.py`

**Current:** `enqueue_gcsplit1_payment_split()` doesn't include `payout_mode`.

**Change:** Add `payout_mode` parameter to method signature and payload.

**Location:** `enqueue_gcsplit1_payment_split()` method

**Update:**
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
    actual_eth_amount: float,
    payout_mode: str = 'instant'  # ✅ ADD THIS (default to instant for backward compat)
) -> Optional[str]:
    """
    Enqueue payment split task to GCSplit1 for instant payouts.

    Args:
        ...
        payout_mode: 'instant' or 'threshold' - determines swap currency
    """
    payload = {
        "user_id": user_id,
        "closed_channel_id": closed_channel_id,
        "wallet_address": wallet_address,
        "payout_currency": payout_currency,
        "payout_network": payout_network,
        "subscription_price": subscription_price,
        "actual_eth_amount": actual_eth_amount,
        "payout_mode": payout_mode  # ✅ ADD THIS
    }

    # ... rest of method
```

---

#### 1.3 GCSplit1 Changes

**File:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

**Current:** GCSplit1 receives payment request but doesn't extract or process `payout_mode`.

**Changes needed:**

**A) Extract payout_mode from webhook payload (Line ~309)**

```python
# Extract required data with null-safe handling
user_id = webhook_data.get('user_id')
closed_channel_id = webhook_data.get('closed_channel_id')
wallet_address = (webhook_data.get('wallet_address') or '').strip()
payout_currency = (webhook_data.get('payout_currency') or '').strip().lower()
payout_network = (webhook_data.get('payout_network') or '').strip().lower()
subscription_price = webhook_data.get('subscription_price') or webhook_data.get('sub_price') or '0'
actual_eth_amount = float(webhook_data.get('actual_eth_amount', 0.0))
payout_mode = webhook_data.get('payout_mode', 'instant').lower()  # ✅ ADD THIS (default to instant)

print(f"👤 [ENDPOINT_1] User ID: {user_id}")
print(f"🏢 [ENDPOINT_1] Channel ID: {closed_channel_id}")
print(f"💰 [ENDPOINT_1] Subscription Price: ${subscription_price}")
print(f"💎 [ENDPOINT_1] ACTUAL ETH Amount (NowPayments): {actual_eth_amount}")
print(f"🎯 [ENDPOINT_1] Payout Mode: {payout_mode}")  # ✅ ADD THIS
print(f"🏦 [ENDPOINT_1] Target: {wallet_address} ({payout_currency.upper()} on {payout_network.upper()})")
```

**B) Calculate amount based on payout_mode (Line ~338)**

```python
# Calculate adjusted amount (remove TP fee)
tp_flat_fee = config.get('tp_flat_fee')
original_amount, adjusted_amount = calculate_adjusted_amount(subscription_price, tp_flat_fee)

# ✅ ADD: Determine swap currency and amount based on payout_mode
if payout_mode == 'instant':
    # For instant payouts: Use ACTUAL ETH amount from NowPayments
    # Apply TP_FEE to the actual ETH received
    swap_currency = 'eth'
    swap_amount = actual_eth_amount * (1 - (float(tp_flat_fee if tp_flat_fee else "3") / 100))

    print(f"⚡ [ENDPOINT_1] INSTANT PAYOUT MODE")
    print(f"💎 [ENDPOINT_1] Swap currency: ETH")
    print(f"💰 [ENDPOINT_1] Actual ETH from NowPayments: {actual_eth_amount}")
    print(f"📊 [ENDPOINT_1] TP Fee: {tp_flat_fee}%")
    print(f"✅ [ENDPOINT_1] Adjusted swap amount: {swap_amount} ETH")

    # Validation warning if actual_eth_amount is missing/zero
    if actual_eth_amount == 0.0:
        print(f"⚠️ [ENDPOINT_1] WARNING: actual_eth_amount is zero - cannot process instant payout")
        abort(400, "Missing actual_eth_amount for instant payout")

else:  # threshold mode
    # For threshold payouts: Use USDT equivalent (current behavior)
    swap_currency = 'usdt'
    swap_amount = adjusted_amount  # This is subscription_price - TP_FEE

    print(f"🔄 [ENDPOINT_1] THRESHOLD PAYOUT MODE")
    print(f"💵 [ENDPOINT_1] Swap currency: USDT")
    print(f"✅ [ENDPOINT_1] Adjusted swap amount: {swap_amount} USDT")
```

**C) Pass payout_mode and swap_currency to GCSplit2 token (Line ~346)**

```python
encrypted_token = token_manager.encrypt_gcsplit1_to_gcsplit2_token(
    user_id=user_id,
    closed_channel_id=str(closed_channel_id),
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    adjusted_amount=swap_amount,  # ✅ RENAMED: This is now either ETH or USDT
    swap_currency=swap_currency,  # ✅ ADD THIS: 'eth' or 'usdt'
    payout_mode=payout_mode,      # ✅ ADD THIS: 'instant' or 'threshold'
    actual_eth_amount=actual_eth_amount
)
```

---

#### 1.4 TokenManager Changes (GCSplit1)

**File:** `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py`

**Current:** `encrypt_gcsplit1_to_gcsplit2_token()` doesn't include `swap_currency` or `payout_mode`.

**Change:** Add these fields to the token structure.

**Location:** `encrypt_gcsplit1_to_gcsplit2_token()` method

**Update:**
```python
def encrypt_gcsplit1_to_gcsplit2_token(
    self,
    user_id: int,
    closed_channel_id: str,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    adjusted_amount: float,         # ✅ RENAMED (was adjusted_amount_usdt)
    swap_currency: str = 'usdt',    # ✅ ADD THIS: 'eth' or 'usdt'
    payout_mode: str = 'instant',   # ✅ ADD THIS: 'instant' or 'threshold'
    actual_eth_amount: float = 0.0
) -> Optional[str]:
    """
    Encrypt token for GCSplit2 estimate request.

    Args:
        adjusted_amount: Swap amount (ETH or USDT depending on payout_mode)
        swap_currency: 'eth' for instant, 'usdt' for threshold
        payout_mode: 'instant' or 'threshold'
    """
    try:
        # Build token data dictionary
        token_data = {
            'user_id': user_id,
            'closed_channel_id': closed_channel_id,
            'wallet_address': wallet_address,
            'payout_currency': payout_currency,
            'payout_network': payout_network,
            'adjusted_amount': adjusted_amount,           # ✅ GENERIC NAME
            'swap_currency': swap_currency,               # ✅ ADD THIS
            'payout_mode': payout_mode,                   # ✅ ADD THIS
            'actual_eth_amount': actual_eth_amount,
            'timestamp': int(time.time())
        }

        # ... rest of encryption logic
```

---

### Phase 2: GCSplit2 - Currency-Aware Estimator

#### 2.1 GCSplit2 Main Changes

**File:** `/OCTOBER/10-26/GCSplit2-10-26/tps2-10-26.py`

**Current:** Always calls ChangeNow with `from_currency="usdt"` (line 130).

**Change:** Use `swap_currency` from token to determine estimate currency.

**Location:** Lines 102-137 (main endpoint processing)

**Update:**
```python
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

# Call ChangeNow API with appropriate currency
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

**Continue with response handling:**
```python
# Extract estimate data
from_amount = estimate_response.get('fromAmount')
to_amount = estimate_response.get('toAmount')
deposit_fee = estimate_response.get('depositFee', 0)
withdrawal_fee = estimate_response.get('withdrawalFee', 0)

print(f"✅ [ENDPOINT] ChangeNow estimate received")
print(f"💰 [ENDPOINT] From: {from_amount} {swap_currency.upper()}")
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

---

#### 2.2 TokenManager Changes (GCSplit2)

**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py`

**Update both decrypt and encrypt methods:**

**A) Decrypt method update:**
```python
def decrypt_gcsplit1_to_gcsplit2_token(self, token: str) -> Optional[dict]:
    """
    Decrypt token from GCSplit1.

    Returns dict with:
        - adjusted_amount (ETH or USDT)
        - swap_currency ('eth' or 'usdt')  # ✅ ADD THIS
        - payout_mode ('instant' or 'threshold')  # ✅ ADD THIS
        - ... other fields
    """
    # ... decryption logic
    # Ensure these fields are extracted:
    # - token_data.get('swap_currency', 'usdt')
    # - token_data.get('payout_mode', 'instant')
```

**B) Encrypt method update:**
```python
def encrypt_gcsplit2_to_gcsplit1_token(
    self,
    user_id: int,
    closed_channel_id: str,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    from_amount: float,
    swap_currency: str,          # ✅ ADD THIS
    payout_mode: str,             # ✅ ADD THIS
    to_amount_post_fee: float,
    deposit_fee: float,
    withdrawal_fee: float,
    actual_eth_amount: float
) -> Optional[str]:
    """
    Encrypt response token for GCSplit1.

    Args:
        swap_currency: 'eth' or 'usdt' - currency used for estimate
        payout_mode: 'instant' or 'threshold'
    """
    token_data = {
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'wallet_address': wallet_address,
        'payout_currency': payout_currency,
        'payout_network': payout_network,
        'from_amount': from_amount,
        'swap_currency': swap_currency,           # ✅ ADD THIS
        'payout_mode': payout_mode,               # ✅ ADD THIS
        'to_amount_post_fee': to_amount_post_fee,
        'deposit_fee': deposit_fee,
        'withdrawal_fee': withdrawal_fee,
        'actual_eth_amount': actual_eth_amount,
        'timestamp': int(time.time())
    }
    # ... encryption logic
```

---

### Phase 3: GCSplit3 - Currency-Aware Swap Creator

#### 3.1 GCSplit3 Main Changes

**File:** `/OCTOBER/10-26/GCSplit3-10-26/tps3-10-26.py`

**Current:** Always creates transaction with `from_currency="usdt"` (line 130).

**Change:** Use `swap_currency` from token to determine transaction currency.

**Location:** Lines 100-137 (main endpoint processing)

**Update:**
```python
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

# Create ChangeNow fixed-rate transaction with appropriate currency
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

**Continue with response handling:**
```python
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
print(f"💰 [ENDPOINT] From: {api_from_amount} {api_from_currency.upper()}")
print(f"💰 [ENDPOINT] To: {api_to_amount} {api_to_currency.upper()}")

# Encrypt response token for GCSplit1
encrypted_response_token = token_manager.encrypt_gcsplit3_to_gcsplit1_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    cn_api_id=cn_api_id,
    from_currency=api_from_currency,     # ✅ DYNAMIC: 'eth' or 'usdt'
    to_currency=api_to_currency,
    from_network=api_from_network,
    to_network=api_to_network,
    from_amount=api_from_amount,
    to_amount=api_to_amount,
    payin_address=api_payin_address,
    payout_address=api_payout_address,
    refund_address=api_refund_address,
    flow=api_flow,
    type_=api_type,
    actual_eth_amount=actual_eth_amount
)
```

---

### Phase 4: GCSplit1 Response Handling

#### 4.1 GCSplit1 - Endpoint 2 Changes

**File:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

**Location:** Lines 403-552 (`/usdt-eth-estimate` endpoint)

**Current:** Assumes `from_currency="usdt"` for all database operations.

**Change:** Use `swap_currency` from token.

**Update:**
```python
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

# Calculate pure market conversion
pure_market_value = calculate_pure_market_conversion(
    from_amount, to_amount_eth_post_fee, deposit_fee, withdrawal_fee
)

# Insert into split_payout_request table
print(f"💾 [ENDPOINT_2] Inserting into split_payout_request")
print(f"   NOTE: to_amount = PURE MARKET VALUE ({pure_market_value} {payout_currency.upper()})")
print(f"   💎 ACTUAL ETH: {actual_eth_amount}")

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

**Continue with token encryption for GCSplit3:**
```python
# Encrypt token for GCSplit3
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

---

#### 4.2 GCSplit1 - Endpoint 3 Changes

**File:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

**Location:** Lines 559-744 (`/eth-client-swap` endpoint)

**Current:** Builds GCHostPay token with hardcoded `from_currency="eth"` assumption.

**Change:** Extract `from_currency` from GCSplit3 response token.

**Update:**
```python
decrypted_data = token_manager.decrypt_gcsplit3_to_gcsplit1_token(encrypted_token)
if not decrypted_data:
    print(f"❌ [ENDPOINT_3] Failed to decrypt token")
    abort(401, "Invalid token")

# Extract data
unique_id = decrypted_data['unique_id']
user_id = decrypted_data['user_id']
closed_channel_id = decrypted_data['closed_channel_id']
cn_api_id = decrypted_data['cn_api_id']
from_currency = decrypted_data['from_currency']  # ✅ DYNAMIC: 'eth' or 'usdt'
to_currency = decrypted_data['to_currency']
from_network = decrypted_data['from_network']
to_network = decrypted_data['to_network']
from_amount = decrypted_data['from_amount']
to_amount = decrypted_data['to_amount']
payin_address = decrypted_data['payin_address']
payout_address = decrypted_data['payout_address']
refund_address = decrypted_data['refund_address']
flow = decrypted_data['flow']
type_ = decrypted_data['type']
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)

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

# Build GCHostPay token
hostpay_token = build_hostpay_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,         # ✅ DYNAMIC: 'eth' or 'usdt'
    from_network=from_network,
    actual_eth_amount=payment_amount,    # ✅ UPDATED: Correct payment amount
    estimated_eth_amount=estimated_amount,
    payin_address=payin_address,
    signing_key=tps_hostpay_signing_key
)
```

---

### Phase 5: GCHostPay Integration

#### 5.1 No Changes Required to GCHostPay Services

**Critical Note:** GCHostPay1/2/3 already support both ETH and USDT (ERC-20) payments!

**Evidence from MAIN_ARCHITECTURE_INSTANT_PAYOUT.md (lines 948-1085):**

```python
# GCHostPay3 already handles currency detection:
if from_currency == 'eth':
    currency_type = "NATIVE ETH"
elif from_currency in ['usdt', 'usdc', 'dai']:
    currency_type = f"ERC-20 TOKEN ({TOKEN_CONFIGS[from_currency]['name']})"
```

**No changes needed because:**
1. GCHostPay1 already receives `from_currency` in token (line 728)
2. GCHostPay3 already detects currency type (line 984)
3. GCHostPay3 already routes to correct payment method (lines 1006-1024)

**The only requirement:** Ensure GCSplit1 passes correct `from_currency` in the token (already done in Phase 4.2).

---

## Database Schema Considerations

### No Schema Changes Required

**Reason:** All database tables already use generic column names:

```sql
-- split_payout_request
from_currency VARCHAR(10)  -- Can store 'eth', 'usdt', 'btc', etc.
from_amount NUMERIC        -- Amount in from_currency

-- split_payout_que
from_currency VARCHAR(10)  -- Can store 'eth', 'usdt', 'btc', etc.
from_amount NUMERIC        -- Amount in from_currency

-- split_payout_hostpay
from_currency VARCHAR(10)  -- Can store 'eth', 'usdt', 'btc', etc.
from_amount NUMERIC        -- Amount in from_currency
```

**These columns are already flexible and support any currency code.**

---

## Backward Compatibility & Migration

### Compatibility Strategy

**Default to `payout_mode='instant'` and `swap_currency='usdt'` for missing fields:**

```python
# All token decrypt methods should include defaults:
payout_mode = decrypted_data.get('payout_mode', 'instant')
swap_currency = decrypted_data.get('swap_currency', 'usdt')
```

**This ensures:**
1. Old tokens (without payout_mode/swap_currency) continue to work
2. New tokens with these fields route correctly
3. No breaking changes to existing flows

### Migration Path

**Phase 1: Deploy with backward compatibility**
- All services default to 'instant' + 'usdt' for missing fields
- Old tokens continue to work as before

**Phase 2: Monitor and validate**
- Track dual-mode usage in logs
- Verify instant ETH swaps work correctly
- Verify threshold USDT swaps unchanged

**Phase 3: Cleanup (optional)**
- Remove defaults after confirming all tokens include new fields
- Add validation to reject tokens missing payout_mode

---

## Testing Strategy

### Unit Tests

**Test Cases for GCSplit2:**

```python
def test_gcsplit2_instant_mode_eth_estimate():
    """Test ETH→SHIB estimate for instant payout."""
    token = create_test_token(
        payout_mode='instant',
        swap_currency='eth',
        adjusted_amount=0.0005668
    )
    response = gcsplit2.process_usdt_eth_estimate(token)
    assert response['from_currency'] == 'eth'
    assert response['from_amount'] == 0.0005668

def test_gcsplit2_threshold_mode_usdt_estimate():
    """Test USDT→SHIB estimate for threshold payout."""
    token = create_test_token(
        payout_mode='threshold',
        swap_currency='usdt',
        adjusted_amount=1.5467691434
    )
    response = gcsplit2.process_usdt_eth_estimate(token)
    assert response['from_currency'] == 'usdt'
    assert response['from_amount'] == 1.5467691434
```

**Test Cases for GCSplit3:**

```python
def test_gcsplit3_instant_mode_eth_swap():
    """Test ETH→SHIB swap creation for instant payout."""
    token = create_test_token(
        payout_mode='instant',
        swap_currency='eth',
        swap_amount=0.0005668
    )
    response = gcsplit3.process_eth_client_swap(token)
    assert response['from_currency'] == 'eth'
    assert response['from_amount'] == 0.0005668

def test_gcsplit3_threshold_mode_usdt_swap():
    """Test USDT→SHIB swap creation for threshold payout."""
    token = create_test_token(
        payout_mode='threshold',
        swap_currency='usdt',
        swap_amount=1.5467691434
    )
    response = gcsplit3.process_eth_client_swap(token)
    assert response['from_currency'] == 'usdt'
    assert response['from_amount'] == 1.5467691434
```

### Integration Tests

**End-to-End Test: Instant Payout with ETH→ClientCurrency**

```
1. Create test payment:
   - User pays $1.35 subscription
   - NowPayments converts to 0.0005668 ETH
   - Payout strategy: instant

2. Verify GCWebhook1:
   - Routes to GCSplit1 with payout_mode='instant'
   - Passes actual_eth_amount=0.0005668

3. Verify GCSplit1:
   - Calculates swap_amount = 0.0005668 * 0.85 = 0.00048178 ETH
   - Sets swap_currency='eth'
   - Passes to GCSplit2

4. Verify GCSplit2:
   - Calls ChangeNow with from_currency='eth'
   - Returns estimate for ETH→SHIB

5. Verify GCSplit3:
   - Creates ChangeNow transaction from_currency='eth'
   - Returns payin_address

6. Verify GCHostPay3:
   - Detects from_currency='eth'
   - Routes to native ETH payment
   - Sends 0.00048178 ETH to ChangeNow

7. Verify ChangeNow:
   - Receives 0.00048178 ETH
   - Converts to SHIB
   - Sends to client wallet
```

**End-to-End Test: Threshold Payout with USDT→ClientCurrency**

```
1. Create test payments:
   - Multiple payments accumulate
   - Total: $5.40 USDT after micro-batch conversion

2. Verify GCBatchProcessor:
   - Detects client over threshold
   - Creates batch with total_usdt=$5.40

3. Verify GCSplit1:
   - Routes batch to GCSplit2 with swap_currency='usdt'

4. Verify GCSplit2:
   - Calls ChangeNow with from_currency='usdt'
   - Returns estimate for USDT→SHIB

5. Verify GCSplit3:
   - Creates ChangeNow transaction from_currency='usdt'

6. Verify GCHostPay3:
   - Detects from_currency='usdt'
   - Routes to ERC-20 token transfer
   - Sends 5.40 USDT to ChangeNow

7. Verify ChangeNow:
   - Receives 5.40 USDT
   - Converts to SHIB
   - Sends to client wallet
```

---

## Monitoring & Observability

### Key Metrics to Track

**Split by payout_mode:**

| Metric | Instant | Threshold |
|--------|---------|-----------|
| **Total payments** | Count instant payouts | Count threshold payouts |
| **Average amount** | Avg ETH per payment | Avg USDT per batch |
| **Swap currency** | 'eth' usage % | 'usdt' usage % |
| **ChangeNow success rate** | ETH→Client success % | USDT→Client success % |
| **ChangeNow fees** | Avg fee % for ETH pairs | Avg fee % for USDT pairs |
| **Minimum amount failures** | Track 400 errors (ETH minimums) | Track 400 errors (USDT minimums) |

### Logging Additions

**Add payout_mode to all log statements:**

```python
# Before
print(f"💰 [ENDPOINT] Amount: {amount} USDT")

# After
print(f"💰 [ENDPOINT] Amount: {amount} {swap_currency.upper()}")
print(f"🎯 [ENDPOINT] Payout Mode: {payout_mode}")
```

**Log swap currency transitions:**

```python
print(f"⚡ [INSTANT] Using ETH→{payout_currency.upper()} swap")
print(f"🔄 [THRESHOLD] Using USDT→{payout_currency.upper()} swap")
```

---

## Risk Analysis & Mitigation

### Risk 1: ChangeNow API Minimum Amounts

**Risk:** ETH minimums may be higher than small subscription amounts.

**Example:** ChangeNow minimum for ETH→SHIB might be 0.001 ETH ($2.50), but subscription is $1.35 (0.0005668 ETH).

**Mitigation:**
1. **Pre-check minimums:** Query ChangeNow `/min-amount` endpoint before creating estimate
2. **Fallback to USDT:** If actual_eth_amount < minimum_eth, fallback to USDT swap
3. **Alert on repeated failures:** Track 400 errors from ChangeNow, alert if threshold exceeded

**Implementation:**
```python
# In GCSplit2, before calling estimate API:
if payout_mode == 'instant' and swap_currency == 'eth':
    min_amount = changenow_client.get_minimum_amount(
        from_currency='eth',
        to_currency=payout_currency
    )

    if adjusted_amount < min_amount:
        print(f"⚠️ [ENDPOINT] ETH amount {adjusted_amount} below minimum {min_amount}")
        print(f"🔄 [ENDPOINT] Falling back to USDT swap")

        # Fallback: Use USDT equivalent instead
        swap_currency = 'usdt'
        adjusted_amount = calculate_usdt_equivalent(adjusted_amount)
```

### Risk 2: Token Expiration During Workflow

**Risk:** Long-running ChangeNow conversions may cause token expiration.

**Current expiration windows:**
- GCSplit1 → GCSplit2: 5 minutes
- GCSplit2 → GCSplit1: 5 minutes
- GCSplit1 → GCHostPay: 2 hours

**Mitigation:** No changes needed - 5 minutes sufficient for estimate/swap creation, 2 hours sufficient for payment execution.

### Risk 3: Database Inconsistency

**Risk:** `from_currency` mismatch between tables (e.g., 'eth' in `split_payout_request`, 'usdt' in `split_payout_hostpay`).

**Mitigation:**
1. **Use transaction IDs for linking:** All tables use `unique_id` or `cn_api_id` for joins, not currency columns
2. **Validation queries:** Periodic check for currency mismatches across linked records
3. **Logging:** Always log `from_currency` at each stage

### Risk 4: Backward Compatibility Break

**Risk:** Old tokens without `payout_mode` cause failures.

**Mitigation:**
1. **Default values:** All decrypt methods default to `payout_mode='instant'` and `swap_currency='usdt'`
2. **Graceful degradation:** Missing fields fallback to current behavior (USDT swaps)
3. **Staged rollout:** Deploy to staging first, monitor for 24h before production

---

## Implementation Checklist

### Pre-Deployment

- [ ] **Code Review:** All token manager changes reviewed
- [ ] **Unit Tests:** All test cases passing for GCSplit1/2/3
- [ ] **Integration Tests:** End-to-end tests passing for both modes
- [ ] **ChangeNow Minimum Checks:** Fallback logic implemented and tested
- [ ] **Logging:** All services log `payout_mode` and `swap_currency`
- [ ] **Documentation:** Architecture docs updated
- [ ] **Database Validation:** Queries validated for currency flexibility

### Deployment

- [ ] **Stage 1: Deploy to Staging**
  - Deploy all services with backward compatibility
  - Run integration tests on staging
  - Monitor logs for 24 hours

- [ ] **Stage 2: Deploy to Production (Canary)**
  - Deploy GCWebhook1 only (starts passing payout_mode)
  - Monitor for 1 hour
  - Verify old flow still works (defaults to USDT)

- [ ] **Stage 3: Deploy GCSplit Services**
  - Deploy GCSplit1, GCSplit2, GCSplit3
  - Monitor for 24 hours
  - Verify instant ETH swaps work
  - Verify threshold USDT swaps unchanged

- [ ] **Stage 4: Full Production**
  - All services deployed
  - Monitor key metrics
  - Alert on ChangeNow 400 errors (minimums)

### Post-Deployment

- [ ] **Monitor Metrics (Week 1)**
  - Instant payout success rate
  - Threshold payout success rate (unchanged)
  - ChangeNow fee comparison (ETH vs USDT)
  - Minimum amount failures

- [ ] **Validate Cost Savings**
  - Compare gas costs: instant ETH vs previous instant USDT
  - Compare ChangeNow fees: ETH pairs vs USDT pairs
  - Measure latency: ETH swaps vs USDT swaps

- [ ] **Document Findings**
  - Update architecture docs with actual metrics
  - Create runbook for handling minimum amount failures
  - Update alerts/dashboards

---

## Cost-Benefit Analysis

### Expected Benefits (Instant Payouts Only)

**1. Lower ChangeNow Fees**
- ETH pairs typically have ~0.5% lower fees than USDT pairs
- For $100k/month in instant payouts: **$500/month savings**

**2. Better Swap Rates**
- ETH pairs have better liquidity for exotic tokens
- Estimated improvement: **1-2% better rates**

**3. Fewer Minimum Amount Rejections**
- ETH minimums often more favorable than USDT
- Reduced 400 errors: **~10% improvement**

**4. Faster Processing**
- Single swap instead of conceptual two-step (ETH→USDT→Client)
- Estimated latency reduction: **~20% faster**

### Costs

**1. Development Time**
- Token manager updates: 2 hours
- Service updates (GCSplit1/2/3): 4 hours
- Testing: 4 hours
- **Total: ~10 hours**

**2. Testing & Validation**
- Integration tests: 2 hours
- Staging validation: 4 hours
- **Total: ~6 hours**

**3. Monitoring & Alerts**
- New metrics setup: 1 hour
- Dashboard updates: 1 hour
- **Total: ~2 hours**

**Total implementation cost: ~18 hours**

### ROI Calculation

**Monthly savings: $500 (fees) + $1000 (better rates) = $1500**
**Implementation cost: 18 hours × $100/hour = $1800**

**Break-even: ~1.2 months**

**Annual benefit: $18,000**

---

## Appendix A: Token Structure Comparison

### Before (Current)

**GCSplit1 → GCSplit2:**
```json
{
  "user_id": 123456,
  "wallet_address": "0xabc...",
  "payout_currency": "shib",
  "adjusted_amount_usdt": 1.5467691434,
  "actual_eth_amount": 0.0005668
}
```

**GCSplit2 → GCSplit1:**
```json
{
  "user_id": 123456,
  "from_amount_usdt": 1.5467691434,
  "to_amount_eth_post_fee": 586726.70,
  "actual_eth_amount": 0.0005668
}
```

**GCSplit3 creates:** `USDT→SHIB` transaction (always)

---

### After (Proposed)

**GCSplit1 → GCSplit2:**
```json
{
  "user_id": 123456,
  "wallet_address": "0xabc...",
  "payout_currency": "shib",
  "adjusted_amount": 0.00048178,
  "swap_currency": "eth",
  "payout_mode": "instant",
  "actual_eth_amount": 0.0005668
}
```

**GCSplit2 → GCSplit1:**
```json
{
  "user_id": 123456,
  "from_amount": 0.00048178,
  "swap_currency": "eth",
  "payout_mode": "instant",
  "to_amount_post_fee": 586726.70,
  "actual_eth_amount": 0.0005668
}
```

**GCSplit3 creates:**
- **Instant:** `ETH→SHIB` transaction ✅
- **Threshold:** `USDT→SHIB` transaction ✅

---

## Appendix B: Example Log Output

### Instant Payout (ETH→SHIB)

```
🎯 [GCWebhook1] Payment confirmed
💰 [GCWebhook1] Subscription Price: $1.35
💎 [GCWebhook1] ACTUAL ETH (NowPayments): 0.0005668
🎯 [GCWebhook1] Payout Mode: instant
⚡ [GCWebhook1] Routing to GCSplit1 (instant payout)

🎯 [GCSplit1] Payment split request received
⚡ [GCSplit1] INSTANT PAYOUT MODE detected
💎 [GCSplit1] Swap currency: ETH
💰 [GCSplit1] Actual ETH from NowPayments: 0.0005668
📊 [GCSplit1] TP Fee: 15%
✅ [GCSplit1] Adjusted swap amount: 0.00048178 ETH
🚀 [GCSplit1] Enqueueing to GCSplit2

🎯 [GCSplit2] ETH→SHIB estimate request received
💱 [GCSplit2] Swap Currency: ETH
💰 [GCSplit2] Amount: 0.00048178 ETH
🎯 [GCSplit2] Target: SHIB on ETH
⚡ [GCSplit2] INSTANT mode: Estimating ETH→SHIB
🌐 [GCSplit2] Calling ChangeNow API for ETH→SHIB estimate
✅ [GCSplit2] ChangeNow estimate received
💰 [GCSplit2] From: 0.00048178 ETH
💰 [GCSplit2] To: 586726.70 SHIB (post-fee)

🎯 [GCSplit3] ETH→SHIB swap request received
💱 [GCSplit3] Swap Currency: ETH
💰 [GCSplit3] Swap Amount: 0.00048178 ETH
🎯 [GCSplit3] Target: SHIB on ETH
⚡ [GCSplit3] INSTANT mode: Creating ETH→SHIB swap
🌐 [GCSplit3] Creating ChangeNow transaction ETH→SHIB
✅ [GCSplit3] ChangeNow transaction created
🆔 [GCSplit3] ChangeNow API ID: 613c822e844358
💰 [GCSplit3] From: 0.00048178 ETH
💰 [GCSplit3] To: 586726.70 SHIB

🎯 [GCHostPay3] Payment execution request received
💱 [GCHostPay3] Currency: ETH (NATIVE ETH)
💰 [GCHostPay3] Amount: 0.00048178 ETH
✅ [GCHostPay3] Wallet balance sufficient
🚀 [GCHostPay3] Sending native ETH payment
✅ [GCHostPay3] Payment sent successfully
🔗 [GCHostPay3] Tx Hash: 0xabc123...

✅ [COMPLETE] Instant payout completed
💎 [COMPLETE] Client receives 586,726.70 SHIB
```

### Threshold Payout (USDT→SHIB)

```
🎯 [GCWebhook1] Payment confirmed
💰 [GCWebhook1] Subscription Price: $1.35
💎 [GCWebhook1] ACTUAL ETH (NowPayments): 0.0005668
🎯 [GCWebhook1] Payout Mode: threshold
🔄 [GCWebhook1] Routing to GCAccumulator (threshold payout)

🎯 [GCAccumulator] Payment accumulation received
💰 [GCAccumulator] Amount: $1.35 USD
📊 [GCAccumulator] Status: pending (awaiting threshold)

... (micro-batch conversion: ETH→USDT) ...

🎯 [GCBatchProcessor] Client over threshold
💵 [GCBatchProcessor] Total: $5.40 USDT
🚀 [GCBatchProcessor] Creating batch payout to GCSplit1

🎯 [GCSplit1] Batch payout request received
🔄 [GCSplit1] THRESHOLD PAYOUT MODE detected
💵 [GCSplit1] Swap currency: USDT
✅ [GCSplit1] Adjusted swap amount: $5.40 USDT
🚀 [GCSplit1] Enqueueing to GCSplit2

🎯 [GCSplit2] USDT→SHIB estimate request received
💱 [GCSplit2] Swap Currency: USDT
💰 [GCSplit2] Amount: 5.40 USDT
🎯 [GCSplit2] Target: SHIB on ETH
🔄 [GCSplit2] THRESHOLD mode: Estimating USDT→SHIB
🌐 [GCSplit2] Calling ChangeNow API for USDT→SHIB estimate
✅ [GCSplit2] ChangeNow estimate received
💰 [GCSplit2] From: 5.40 USDT
💰 [GCSplit2] To: 2,151,724.53 SHIB (post-fee)

🎯 [GCSplit3] USDT→SHIB swap request received
💱 [GCSplit3] Swap Currency: USDT
💰 [GCSplit3] Swap Amount: 5.40 USDT
🎯 [GCSplit3] Target: SHIB on ETH
🔄 [GCSplit3] THRESHOLD mode: Creating USDT→SHIB swap
🌐 [GCSplit3] Creating ChangeNow transaction USDT→SHIB
✅ [GCSplit3] ChangeNow transaction created
🆔 [GCSplit3] ChangeNow API ID: 787d944f955469
💰 [GCSplit3] From: 5.40 USDT
💰 [GCSplit3] To: 2,151,724.53 SHIB

🎯 [GCHostPay3] Payment execution request received
💱 [GCHostPay3] Currency: USDT (ERC-20 TOKEN)
💰 [GCHostPay3] Amount: 5.40 USDT
✅ [GCHostPay3] Wallet balance sufficient
🚀 [GCHostPay3] Sending ERC-20 token transfer
✅ [GCHostPay3] Payment sent successfully
🔗 [GCHostPay3] Tx Hash: 0xdef456...

✅ [COMPLETE] Threshold payout completed
💎 [COMPLETE] Client receives 2,151,724.53 SHIB
```

---

## Conclusion

This architecture enables **optimal swap routing** based on payout scheme:

**✅ INSTANT PAYOUTS:** Use ETH→ClientCurrency for better rates and lower minimums
**✅ THRESHOLD PAYOUTS:** Use USDT→ClientCurrency for price stability during accumulation

**Key Success Factors:**
1. Backward compatible (defaults to current USDT behavior)
2. No database schema changes required
3. Minimal code changes (token managers + routing logic)
4. Leverages existing GCHostPay ERC-20 support
5. Clear separation of concerns (payout_mode determines swap_currency)

**Expected Outcome:**
- Faster instant payouts
- Lower fees for instant payouts
- Fewer minimum amount rejections
- Unchanged threshold payout behavior
- Better overall user experience

---

**Document Version:** 1.0
**Created:** 2025-11-07
**Author:** Claude Code Analysis
