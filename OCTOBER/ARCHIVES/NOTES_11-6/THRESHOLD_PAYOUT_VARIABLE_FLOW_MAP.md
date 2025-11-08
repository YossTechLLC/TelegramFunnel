# Threshold Payout Variable Flow Map
**Date**: 2025-11-03
**Payment Method**: Threshold Accumulation
**Flow Type**: NPGateway → GCWebhook1 → GCAccumulator → MicroBatch → GCHostPay → ChangeNow → Completion

---

## 🎯 Executive Summary

This document traces the complete variable flow for **threshold payout method** from NOWPayments IPN through final USDT distribution. Unlike instant payouts, threshold payouts accumulate multiple small payments until a minimum threshold is reached, then batch-convert ETH→USDT for better exchange rates.

**Key Stages**:
1. Initial payment capture (NOWPayments → np-webhook → GCWebhook1)
2. Accumulation storage (GCAccumulator)
3. Threshold detection (GCMicroBatchProcessor)
4. Batch conversion (ETH → USDT via ChangeNow)
5. ETH payment execution (GCHostPay1/2/3)
6. Proportional USDT distribution (back to MicroBatchProcessor)

---

## 📊 Stage 1: NOWPayments IPN → np-webhook-10-26

**Source**: NOWPayments IPN callback
**Endpoint**: `POST https://np-webhook-10-26/`
**File**: `np-webhook-10-26/app.py:489-820`

### Variables Received (IPN Payload)
```json
{
  "payment_id": "6271827386",           // string - NOWPayments payment ID
  "invoice_id": "INV-123456",           // string - Optional invoice reference
  "order_id": "PGP-6271402111|-1003268562225",  // string - Format: user_id|channel_id
  "payment_status": "finished",         // string - Payment status
  "pay_address": "0x1234...5678",       // string - Customer's payment address
  "pay_amount": "0.01234567",           // decimal as string - Amount customer sent
  "pay_currency": "eth",                // string - Currency customer used
  "price_amount": "35.00",              // decimal as string - Original price (USD)
  "price_currency": "usd",              // string - Price currency
  "outcome_amount": "0.01200000",       // decimal as string - Amount after processing
  "outcome_currency": "eth"             // string - Final currency
}
```

### Processing Steps
```python
# 1. Signature Verification (line 501-518)
signature = request.headers.get('x-nowpayments-sig')
payload = request.get_data()
verify_ipn_signature(payload, signature)

# 2. Parse order_id to extract user_id and channel_id (line 541)
order_id = "PGP-6271402111|-1003268562225"
parts = order_id.split('|')
user_id = 6271402111            # int
closed_channel_id = -1003268562225  # int

# 3. Fetch CoinGecko price for outcome_currency (line 580-610)
outcome_currency = "eth"
outcome_amount = 0.01200000     # float
crypto_usd_price = 2451.25      # float - from CoinGecko
outcome_amount_usd = outcome_amount * crypto_usd_price = 29.415  # float

# 4. Database insertion (line 612-720)
INSERT INTO processed_payments (
  payment_id, user_id, channel_id, wallet_address,
  payout_currency, payout_network, subscription_time_days,
  subscription_price, outcome_amount_usd, payment_status,
  nowpayments_payment_id, nowpayments_pay_address,
  nowpayments_outcome_amount
)
```

### Variables Prepared for GCWebhook1
```python
# np-webhook-10-26/cloudtasks_client.py:76-88
payload = {
    "user_id": 6271402111,                      # int
    "closed_channel_id": -1003268562225,        # int
    "wallet_address": "0xABC...DEF",            # string - Client's payout wallet
    "payout_currency": "usdt",                  # string - Client's chosen currency
    "payout_network": "eth",                    # string - Client's chosen network
    "subscription_time_days": 30,               # int - Subscription duration
    "subscription_price": "35.00",              # string - Declared subscription price
    "outcome_amount_usd": 29.415,               # float - ACTUAL USD value received
    "nowpayments_payment_id": "6271827386",     # string - NOWPayments ID
    "nowpayments_pay_address": "0x1234...5678", # string - Customer payment address
    "nowpayments_outcome_amount": "0.01200000"  # string - Actual ETH received
}
```

**Cloud Tasks Enqueue**:
- Queue: `gcwebhook1-queue`
- Target: `https://gcwebhook1-10-26/`

---

## 📊 Stage 2: np-webhook → GCWebhook1-10-26

**Source**: np-webhook via Cloud Tasks
**Endpoint**: `POST https://gcwebhook1-10-26/`
**File**: `GCWebhook1-10-26/tph1-10-26.py:145-530`

### Variables Received (from np-webhook)
```python
# GCWebhook1-10-26/tph1-10-26.py:234-267
request_data = request.get_json()

user_id = 6271402111                          # int
closed_channel_id = -1003268562225            # int
wallet_address = "0xABC...DEF"                # string
payout_currency = "usdt"                      # string
payout_network = "eth"                        # string
subscription_time_days = 30                   # int
subscription_price = "35.00"                  # string
outcome_amount_usd = 29.415                   # float
nowpayments_payment_id = "6271827386"         # string
nowpayments_pay_address = "0x1234...5678"     # string
nowpayments_outcome_amount = "0.01200000"     # string (ETH)
```

### Processing Steps
```python
# 1. Type conversion and validation (line 250-260)
user_id = int(user_id)                        # 6271402111
closed_channel_id = int(closed_channel_id)    # -1003268562225
subscription_time_days = int(subscription_time_days)  # 30
subscription_price = float(subscription_price)        # 35.0
outcome_amount_usd = float(outcome_amount_usd)        # 29.415

# 2. Database query for subscription_id (line 274-313)
query = """
    SELECT id FROM private_channel_users_database
    WHERE user_id = %s AND closed_channel_id = %s
"""
result = execute_query(user_id, closed_channel_id)
subscription_id = result[0][0]  # int - e.g., 42

# 3. Determine payout method (line 360-395)
query = """
    SELECT payout_method FROM private_channel_users_database
    WHERE id = %s
"""
result = execute_query(subscription_id)
payout_method = result[0][0]  # string - "threshold" or "instant"

print(f"💎 [ROUTING] Payout method: {payout_method}")

# 4. Route based on payout_method
if payout_method == "threshold":
    print(f"📊 [ROUTING] Threshold payout - sending to GCAccumulator")
    # ROUTE A: GCAccumulator path (see next stage)
elif payout_method == "instant":
    print(f"⚡ [ROUTING] Instant payout - sending to GCSplit1")
    # ROUTE B: GCSplit1 path (not covered in this document)
```

### Variables for GCAccumulator (Threshold Path)
```python
# GCWebhook1-10-26/cloudtasks_client.py:223-294
payload = {
    "user_id": 6271402111,                      # int
    "client_id": -1003268562225,                # int (renamed from closed_channel_id)
    "wallet_address": "0xABC...DEF",            # string
    "payout_currency": "usdt",                  # string
    "payout_network": "eth",                    # string
    "payment_amount_usd": "35.00",              # string - subscription_price
    "subscription_id": 42,                      # int - Database subscription ID
    "payment_timestamp": "2025-11-03T12:00:00", # ISO 8601 timestamp

    # NEW: NOWPayments fields for audit trail
    "nowpayments_payment_id": "6271827386",     # string
    "nowpayments_pay_address": "0x1234...5678", # string
    "nowpayments_outcome_amount": "0.01200000"  # string (ETH)
}
```

### Variables for GCWebhook2 (Telegram Invite - Parallel)
```python
# GCWebhook1-10-26 also sends Telegram invite in parallel
# GCWebhook1-10-26/cloudtasks_client.py:101-136
payload = {
    "token": "encrypted_base64_token",  # Encrypted token with user/channel data
    "payment_id": 6271827386            # int - NOWPayments payment ID
}
```

**Cloud Tasks Enqueue (2 parallel tasks)**:
1. Queue: `accumulator-payment-queue` → Target: `https://gcaccumulator-10-26/`
2. Queue: `gcwebhook-telegram-invite-queue` → Target: `https://gcwebhook2-10-26/`

---

## 📊 Stage 3: GCWebhook1 → GCAccumulator-10-26

**Source**: GCWebhook1 via Cloud Tasks
**Endpoint**: `POST https://gcaccumulator-10-26/`
**File**: `GCAccumulator-10-26/acc10-26.py:63-178`

### Variables Received
```python
# GCAccumulator-10-26/acc10-26.py:90-103
request_data = request.get_json()

user_id = 6271402111                          # int
client_id = -1003268562225                    # int
wallet_address = "0xABC...DEF"                # string
payout_currency = "usdt"                      # string
payout_network = "eth"                        # string
payment_amount_usd = Decimal("35.00")         # Decimal
subscription_id = 42                          # int
payment_timestamp = "2025-11-03T12:00:00"     # string

# NEW: NOWPayments fields (optional)
nowpayments_payment_id = "6271827386"         # string (or None)
nowpayments_pay_address = "0x1234...5678"     # string (or None)
nowpayments_outcome_amount = "0.01200000"     # string (or None)
```

### Processing Steps
```python
# 1. Calculate adjusted amount (remove TP fee) (line 118-123)
tp_flat_fee = Decimal("3")  # 3% fee
fee_amount = payment_amount_usd * (tp_flat_fee / Decimal("100"))
#           = 35.00 * 0.03 = 1.05

adjusted_amount_usd = payment_amount_usd - fee_amount
#                   = 35.00 - 1.05 = 33.95

print(f"💸 [ENDPOINT] TP fee (3%): ${fee_amount}")
print(f"✅ [ENDPOINT] Adjusted amount: ${adjusted_amount_usd}")

# 2. Store as accumulated_eth (pending conversion) (line 127-129)
# Note: "accumulated_eth" is misleading name - it's actually USD value
accumulated_eth = adjusted_amount_usd  # 33.95 USD
print(f"💰 [ENDPOINT] Accumulated ETH value: ${accumulated_eth}")
```

### Database Insertion
```python
# GCAccumulator-10-26/acc10-26.py:138-152
accumulation_id = db_manager.insert_payout_accumulation_pending(
    client_id=-1003268562225,
    user_id=6271402111,
    subscription_id=42,
    payment_amount_usd=Decimal("35.00"),
    payment_currency='usd',
    payment_timestamp="2025-11-03T12:00:00",
    accumulated_eth=Decimal("33.95"),           # USD value pending conversion
    client_wallet_address="0xABC...DEF",
    client_payout_currency="usdt",
    client_payout_network="eth",
    nowpayments_payment_id="6271827386",
    nowpayments_pay_address="0x1234...5678",
    nowpayments_outcome_amount="0.01200000"
)
# Returns: accumulation_id (e.g., 101)

print(f"✅ [ENDPOINT] Payment accumulated (awaiting micro-batch conversion)")
print(f"🆔 [ENDPOINT] Accumulation ID: {accumulation_id}")
```

### Database Table: `payout_accumulation`
```sql
INSERT INTO payout_accumulation (
    id,                          -- 101 (auto-increment)
    client_id,                   -- -1003268562225
    user_id,                     -- 6271402111
    subscription_id,             -- 42
    payment_amount_usd,          -- 35.00
    payment_currency,            -- 'usd'
    payment_timestamp,           -- '2025-11-03T12:00:00'
    accumulated_eth,             -- 33.95 (USD value, not ETH!)
    client_wallet_address,       -- '0xABC...DEF'
    client_payout_currency,      -- 'usdt'
    client_payout_network,       -- 'eth'
    conversion_status,           -- 'pending'
    nowpayments_payment_id,      -- '6271827386'
    nowpayments_pay_address,     -- '0x1234...5678'
    nowpayments_outcome_amount,  -- '0.01200000'
    created_at                   -- CURRENT_TIMESTAMP
)
```

**Response**:
```json
{
  "status": "success",
  "message": "Payment accumulated successfully (micro-batch pending)",
  "accumulation_id": 101,
  "accumulated_eth": "33.95",
  "conversion_status": "pending"
}
```

**⚠️ IMPORTANT**: At this stage, payment is stored in database with `conversion_status='pending'`. **NO immediate conversion happens**. The payment waits for the micro-batch threshold to be reached.

---

## 📊 Stage 4: Cloud Scheduler → GCMicroBatchProcessor-10-26

**Source**: Cloud Scheduler (every 15 minutes)
**Endpoint**: `POST https://gcmicrobatchprocessor-10-26/check-threshold`
**File**: `GCMicroBatchProcessor-10-26/microbatch10-26.py:73-290`

### Trigger
```bash
# Cloud Scheduler Job Configuration
Schedule: */15 * * * *  # Every 15 minutes
Target: https://gcmicrobatchprocessor-10-26/check-threshold
Method: POST
Body: {} (empty - scheduled job)
```

### Processing Steps

#### Step 4.1: Fetch Threshold
```python
# microbatch10-26.py:99-102
threshold = config_manager.get_micro_batch_threshold()
# Example: threshold = Decimal("50.00")  # $50 USD minimum

print(f"💰 [ENDPOINT] Current threshold: ${threshold}")
```

#### Step 4.2: Query Total Pending USD
```python
# microbatch10-26.py:105-107
total_pending = db_manager.get_total_pending_usd()
# Query:
"""
SELECT SUM(accumulated_eth)
FROM payout_accumulation
WHERE conversion_status = 'pending'
"""
# Example result: 61.85 (sum of multiple payments)

print(f"📊 [ENDPOINT] Total pending: ${total_pending}")
```

#### Step 4.3: Query Total ACTUAL ETH
```python
# microbatch10-26.py:109-111
total_actual_eth = db_manager.get_total_pending_actual_eth()
# Query:
"""
SELECT SUM(
    CAST(nowpayments_outcome_amount AS DECIMAL(20,10))
)
FROM payout_accumulation
WHERE conversion_status = 'pending'
  AND nowpayments_outcome_amount IS NOT NULL
"""
# Example result: 0.02523456 ETH (actual ETH from NowPayments)

print(f"💎 [ENDPOINT] Total ACTUAL ETH: {total_actual_eth} ETH")
```

#### Step 4.4: Threshold Check
```python
# microbatch10-26.py:114-123
if total_pending < threshold:
    print(f"⏳ [ENDPOINT] Total pending (${total_pending}) < Threshold (${threshold}) - no action")
    return {"status": "success", "batch_created": False}

# Threshold reached!
print(f"✅ [ENDPOINT] Threshold reached! Creating batch conversion")
print(f"📊 [ENDPOINT] Total pending: ${total_pending} >= Threshold: ${threshold}")
```

**Example Scenario**:
- Payment 1: $33.95 (0.01200000 ETH)
- Payment 2: $27.90 (0.01323456 ETH)
- **Total**: $61.85 (0.02523456 ETH)
- **Threshold**: $50.00
- **Result**: ✅ Threshold reached → Create batch

#### Step 4.5: Generate Batch ID
```python
# microbatch10-26.py:142-143
import uuid
batch_conversion_id = str(uuid.uuid4())
# Example: "a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"

print(f"🆔 [ENDPOINT] Generated batch conversion ID: {batch_conversion_id}")
```

#### Step 4.6: Get Host Wallet Address
```python
# microbatch10-26.py:145-151
host_wallet_usdt = config.get('host_wallet_usdt_address')
# Example: "0x9876543210FEDCBA9876543210FEDCBA98765432"

print(f"🏦 [ENDPOINT] Host USDT wallet: {host_wallet_usdt}")
```

#### Step 4.7: Determine ETH Amount for Swap
```python
# microbatch10-26.py:154-183
# PRIORITY: Use ACTUAL ETH from NowPayments
if total_actual_eth > 0:
    eth_for_swap = total_actual_eth  # 0.02523456 ETH
    print(f"✅ [ENDPOINT] Using ACTUAL ETH from NowPayments: {eth_for_swap} ETH")
    print(f"📊 [ENDPOINT] This represents ${total_pending} USD in accumulated payments")
else:
    # FALLBACK: Estimate USD→ETH conversion
    print(f"⚠️ [ENDPOINT] WARNING: No actual ETH found, falling back to USD→ETH estimation")

    # Call ChangeNow estimate API: USDT → ETH
    estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
        from_currency='usdt',
        to_currency='eth',
        from_network='eth',
        to_network='eth',
        from_amount=str(total_pending),  # "61.85"
        flow='standard',
        type_='direct'
    )

    eth_for_swap = estimate_response['toAmount']  # e.g., 0.0252 ETH
    print(f"✅ [ENDPOINT] USD→ETH conversion estimate received")
    print(f"💰 [ENDPOINT] ${total_pending} USD ≈ {eth_for_swap} ETH")
```

#### Step 4.8: Create ChangeNow ETH→USDT Swap
```python
# microbatch10-26.py:185-199
swap_result = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency='eth',
    to_currency='usdt',
    from_amount=float(eth_for_swap),  # 0.02523456
    address=host_wallet_usdt,         # "0x9876...5432"
    from_network='eth',
    to_network='eth'                  # USDT on Ethereum (ERC-20)
)

# ChangeNow Response
cn_api_id = swap_result['id']               # "cn_abc123def456"
payin_address = swap_result['payinAddress']  # "0xCHANGENOW...ADDRESS"

print(f"✅ [ENDPOINT] ChangeNow swap created successfully")
print(f"🆔 [ENDPOINT] ChangeNow ID: {cn_api_id}")
print(f"📬 [ENDPOINT] Payin address: {payin_address}")
```

**ChangeNow Swap Details**:
```json
{
  "id": "cn_abc123def456",
  "fromCurrency": "eth",
  "toCurrency": "usdt",
  "fromAmount": 0.02523456,
  "toAmount": 60.15,  // Estimated USDT after fees
  "payinAddress": "0xCHANGENOW_RECEIVING_ADDRESS",
  "payoutAddress": "0x9876543210FEDCBA9876543210FEDCBA98765432",
  "status": "waiting",
  "flow": "standard",
  "type": "direct"
}
```

#### Step 4.9: Create batch_conversions Record
```python
# microbatch10-26.py:209-216
batch_created = db_manager.create_batch_conversion(
    batch_conversion_id="a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
    total_eth_usd=61.85,
    threshold=50.00,
    cn_api_id="cn_abc123def456",
    payin_address="0xCHANGENOW_RECEIVING_ADDRESS"
)
```

### Database Table: `batch_conversions`
```sql
INSERT INTO batch_conversions (
    batch_conversion_id,          -- 'a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f'
    total_eth_usd,                -- 61.85
    threshold,                    -- 50.00
    cn_api_id,                    -- 'cn_abc123def456'
    payin_address,                -- '0xCHANGENOW_RECEIVING_ADDRESS'
    status,                       -- 'pending'
    created_at                    -- CURRENT_TIMESTAMP
)
```

#### Step 4.10: Update Pending Records to 'swapping'
```python
# microbatch10-26.py:223-230
records_updated = db_manager.update_records_to_swapping(batch_conversion_id)

# Query:
"""
UPDATE payout_accumulation
SET
    conversion_status = 'swapping',
    batch_conversion_id = 'a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f'
WHERE
    conversion_status = 'pending'
"""

print(f"✅ [ENDPOINT] Updated {records_updated} record(s) to 'swapping' status")
```

**Example Updated Records**:
```
ID  | client_id        | accumulated_eth | conversion_status | batch_conversion_id
----|------------------|-----------------|-------------------|---------------------
101 | -1003268562225   | 33.95           | swapping          | a7f3c9e1-2b4d...
102 | -1003268562225   | 27.90           | swapping          | a7f3c9e1-2b4d...
```

#### Step 4.11: Encrypt Token for GCHostPay1
```python
# microbatch10-26.py:242-254
encrypted_token = token_manager.encrypt_microbatch_to_gchostpay1_token(
    batch_conversion_id="a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
    cn_api_id="cn_abc123def456",
    from_currency='eth',
    from_network='eth',
    from_amount=0.02523456,  # ACTUAL ETH, not USD!
    payin_address="0xCHANGENOW_RECEIVING_ADDRESS"
)

print(f"💰 [ENDPOINT] Passing ACTUAL ETH amount: {eth_for_swap} ETH")
```

**Encrypted Token Contents** (Base64-encoded):
```python
{
    'batch_conversion_id': 'a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f',
    'cn_api_id': 'cn_abc123def456',
    'from_currency': 'eth',
    'from_network': 'eth',
    'from_amount': 0.02523456,  # ETH amount to send
    'payin_address': '0xCHANGENOW_RECEIVING_ADDRESS',
    'context': 'batch',  # Important for routing
    'timestamp': 1699012345
}
```

#### Step 4.12: Enqueue to GCHostPay1
```python
# microbatch10-26.py:259-263
gchostpay1_batch_queue = config.get('gchostpay1_batch_queue')
gchostpay1_url = config.get('gchostpay1_url')

task_name = cloudtasks_client.enqueue_gchostpay1_batch_execution(
    queue_name=gchostpay1_batch_queue,  # "gchostpay1-batch-queue"
    target_url=f"{gchostpay1_url}/",    # "https://gchostpay1-10-26/"
    encrypted_token=encrypted_token
)

print(f"✅ [ENDPOINT] Batch execution task enqueued successfully")
print(f"🆔 [ENDPOINT] Task: {task_name}")
```

**Cloud Tasks Enqueue**:
- Queue: `gchostpay1-batch-queue`
- Target: `https://gchostpay1-10-26/`
- Payload: `{"token": "eyJhbGciOi..."}`

### Response
```json
{
  "status": "success",
  "message": "Batch conversion created successfully",
  "total_pending": "61.85",
  "threshold": "50.00",
  "batch_conversion_id": "a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
  "cn_api_id": "cn_abc123def456",
  "payment_count": 2,
  "task_name": "projects/.../tasks/...",
  "batch_created": true
}
```

---

## 📊 Stage 5: GCMicroBatchProcessor → GCHostPay1-10-26

**Source**: GCMicroBatchProcessor via Cloud Tasks
**Endpoint**: `POST https://gchostpay1-10-26/`
**File**: `GCHostPay1-10-26/tphp1-10-26.py:182-368`

### Variables Received
```python
# GCHostPay1-10-26/tphp1-10-26.py:212-269
request_data = request.get_json()
token = request_data.get('token')

# Decrypt token (try multiple sources)
decrypted_data = token_manager.decrypt_microbatch_to_gchostpay1_token(token)

# Extracted fields
batch_conversion_id = "a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"
cn_api_id = "cn_abc123def456"
from_currency = 'eth'
from_network = 'eth'
from_amount = 0.02523456  # ETH
payin_address = "0xCHANGENOW_RECEIVING_ADDRESS"
context = 'batch'

# Create unique_id for tracking
unique_id = f"batch_{batch_conversion_id}"
# = "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"

print(f"✅ [ENDPOINT_1] GCMicroBatchProcessor token decoded (batch conversion)")
print(f"📋 [ENDPOINT_1] Context: {context}")
print(f"🆔 [ENDPOINT_1] Batch Conversion ID: {batch_conversion_id}")
print(f"🆔 [ENDPOINT_1] CN API ID: {cn_api_id}")
print(f"💰 [ENDPOINT_1] Amount: {from_amount} {from_currency.upper()}")
```

### Processing Steps

#### Step 5.1: Check for Duplicates
```python
# GCHostPay1-10-26/tphp1-10-26.py:302-312
if db_manager.check_transaction_exists(unique_id):
    print(f"⚠️ [ENDPOINT_1] Transaction {unique_id} already processed")
    return {
        "status": "already_processed",
        "unique_id": unique_id
    }
```

#### Step 5.2: Encrypt Token for GCHostPay2
```python
# GCHostPay1-10-26/tphp1-10-26.py:314-322
encrypted_token = token_manager.encrypt_gchostpay1_to_gchostpay2_token(
    unique_id="batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
    cn_api_id="cn_abc123def456",
    from_currency='eth',
    from_network='eth',
    from_amount=0.02523456,
    payin_address="0xCHANGENOW_RECEIVING_ADDRESS"
)
```

**Token Contents** (for GCHostPay2):
```python
{
    'unique_id': 'batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f',
    'cn_api_id': 'cn_abc123def456',
    'from_currency': 'eth',
    'from_network': 'eth',
    'from_amount': 0.02523456,
    'payin_address': '0xCHANGENOW_RECEIVING_ADDRESS',
    'timestamp': 1699012456
}
```

#### Step 5.3: Enqueue to GCHostPay2 (Status Check)
```python
# GCHostPay1-10-26/tphp1-10-26.py:329-344
gchostpay2_queue = config.get('gchostpay2_queue')
gchostpay2_url = config.get('gchostpay2_url')

task_name = cloudtasks_client.enqueue_gchostpay2_status_check(
    queue_name=gchostpay2_queue,  # "gchostpay2-queue"
    target_url=gchostpay2_url,    # "https://gchostpay2-10-26/"
    encrypted_token=encrypted_token
)

print(f"✅ [ENDPOINT_1] Enqueued status check to GCHostPay2")
```

**Cloud Tasks Enqueue**:
- Queue: `gchostpay2-queue`
- Target: `https://gchostpay2-10-26/`
- Payload: `{"token": "eyJhbGciOi..."}`

### Response
```json
{
  "status": "success",
  "message": "Status check enqueued to GCHostPay2",
  "unique_id": "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
  "cn_api_id": "cn_abc123def456",
  "task_id": "projects/.../tasks/..."
}
```

---

## 📊 Stage 6: GCHostPay1 → GCHostPay2-10-26 (Status Check)

**Source**: GCHostPay1 via Cloud Tasks
**Endpoint**: `POST https://gchostpay2-10-26/`
**File**: `GCHostPay2-10-26/tphp2-10-26.py:71-206`

### Variables Received
```python
# GCHostPay2-10-26/tphp2-10-26.py:99-130
request_data = request.get_json()
token = request_data.get('token')

# Decrypt token from GCHostPay1
decrypted_data = token_manager.decrypt_gchostpay1_to_gchostpay2_token(token)

unique_id = "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"
cn_api_id = "cn_abc123def456"
from_currency = 'eth'
from_network = 'eth'
from_amount = 0.02523456
payin_address = "0xCHANGENOW_RECEIVING_ADDRESS"

print(f"✅ [ENDPOINT] Token decoded successfully")
print(f"🆔 [ENDPOINT] Unique ID: {unique_id}")
print(f"🆔 [ENDPOINT] CN API ID: {cn_api_id}")
```

### Processing Steps

#### Step 6.1: Check ChangeNow Status (Infinite Retry)
```python
# GCHostPay2-10-26/tphp2-10-26.py:131-145
status = changenow_client.check_transaction_status_with_retry(cn_api_id)

# API Call: GET https://api.changenow.io/v2/exchange/by-id?id=cn_abc123def456
# Response:
{
  "id": "cn_abc123def456",
  "status": "waiting",  // Waiting for ETH deposit
  "fromCurrency": "eth",
  "toCurrency": "usdt",
  "fromAmount": 0.02523456,
  "toAmount": 60.15,
  "payinAddress": "0xCHANGENOW_RECEIVING_ADDRESS",
  "payoutAddress": "0x9876543210FEDCBA9876543210FEDCBA98765432"
}

# Note: Infinite retry with 60s backoff until status != "waiting"
print(f"✅ [ENDPOINT] ChangeNow status retrieved: {status}")
# status = "waiting"
```

#### Step 6.2: Encrypt Response Token
```python
# GCHostPay2-10-26/tphp2-10-26.py:148-157
encrypted_response_token = token_manager.encrypt_gchostpay2_to_gchostpay1_token(
    unique_id="batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
    cn_api_id="cn_abc123def456",
    status="waiting",
    from_currency='eth',
    from_network='eth',
    from_amount=0.02523456,
    payin_address="0xCHANGENOW_RECEIVING_ADDRESS"
)
```

**Token Contents** (for GCHostPay1):
```python
{
    'unique_id': 'batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f',
    'cn_api_id': 'cn_abc123def456',
    'status': 'waiting',  # ChangeNow status
    'from_currency': 'eth',
    'from_network': 'eth',
    'from_amount': 0.02523456,
    'payin_address': '0xCHANGENOW_RECEIVING_ADDRESS',
    'timestamp': 1699012567
}
```

#### Step 6.3: Enqueue Response to GCHostPay1
```python
# GCHostPay2-10-26/tphp2-10-26.py:164-182
gchostpay1_response_queue = config.get('gchostpay1_response_queue')
gchostpay1_url = config.get('gchostpay1_url')

# Target the /status-verified endpoint
target_url = f"{gchostpay1_url}/status-verified"

task_name = cloudtasks_client.enqueue_gchostpay1_status_response(
    queue_name=gchostpay1_response_queue,  # "gchostpay1-response-queue"
    target_url=target_url,                 # "https://gchostpay1-10-26/status-verified"
    encrypted_token=encrypted_response_token
)

print(f"✅ [ENDPOINT] Successfully enqueued response to GCHostPay1")
```

**Cloud Tasks Enqueue**:
- Queue: `gchostpay1-response-queue`
- Target: `https://gchostpay1-10-26/status-verified`
- Payload: `{"token": "eyJhbGciOi..."}`

### Response
```json
{
  "status": "success",
  "message": "Status check completed and response enqueued",
  "unique_id": "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
  "cn_api_id": "cn_abc123def456",
  "changenow_status": "waiting",
  "task_id": "projects/.../tasks/..."
}
```

---

## 📊 Stage 7: GCHostPay2 → GCHostPay1-10-26 (Status Verified)

**Source**: GCHostPay2 via Cloud Tasks
**Endpoint**: `POST https://gchostpay1-10-26/status-verified`
**File**: `GCHostPay1-10-26/tphp1-10-26.py:374-506`

### Variables Received
```python
# GCHostPay1-10-26/tphp1-10-26.py:399-428
request_data = request.get_json()
token = request_data.get('token')

# Decrypt token from GCHostPay2
decrypted_data = token_manager.decrypt_gchostpay2_to_gchostpay1_token(token)

unique_id = "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"
cn_api_id = "cn_abc123def456"
status = "waiting"
from_currency = 'eth'
from_network = 'eth'
from_amount = 0.02523456
payin_address = "0xCHANGENOW_RECEIVING_ADDRESS"

print(f"✅ [ENDPOINT_2] Token decoded successfully")
print(f"📊 [ENDPOINT_2] Status: {status}")
```

### Processing Steps

#### Step 7.1: Validate Status
```python
# GCHostPay1-10-26/tphp1-10-26.py:434-442
if status != "waiting":
    print(f"⚠️ [ENDPOINT_2] Invalid status: {status} (expected 'waiting')")
    return {
        "status": "invalid_status",
        "message": f"ChangeNow status is '{status}', expected 'waiting'"
    }

# Status is valid → Proceed with payment execution
```

#### Step 7.2: Detect Context
```python
# GCHostPay1-10-26/tphp1-10-26.py:444-448
# Detect context from unique_id prefix
context = 'batch' if unique_id.startswith('batch_') else 'instant'
print(f"📋 [ENDPOINT_2] Detected context: {context}")
# context = 'batch'
```

#### Step 7.3: Encrypt Token for GCHostPay3
```python
# GCHostPay1-10-26/tphp1-10-26.py:450-459
encrypted_token_payment = token_manager.encrypt_gchostpay1_to_gchostpay3_token(
    unique_id="batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
    cn_api_id="cn_abc123def456",
    from_currency='eth',
    from_network='eth',
    from_amount=0.02523456,
    payin_address="0xCHANGENOW_RECEIVING_ADDRESS",
    context='batch'  # Pass context for routing
)
```

**Token Contents** (for GCHostPay3):
```python
{
    'unique_id': 'batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f',
    'cn_api_id': 'cn_abc123def456',
    'from_currency': 'eth',
    'from_network': 'eth',
    'from_amount': 0.02523456,  # ETH to send
    'payin_address': '0xCHANGENOW_RECEIVING_ADDRESS',
    'context': 'batch',  # Important for response routing
    'attempt_count': 1,  # Retry tracking
    'first_attempt_at': 1699012678,
    'timestamp': 1699012678
}
```

#### Step 7.4: Enqueue to GCHostPay3 (Payment Execution)
```python
# GCHostPay1-10-26/tphp1-10-26.py:466-481
gchostpay3_queue = config.get('gchostpay3_queue')
gchostpay3_url = config.get('gchostpay3_url')

task_name = cloudtasks_client.enqueue_gchostpay3_payment_execution(
    queue_name=gchostpay3_queue,  # "gchostpay3-queue"
    target_url=gchostpay3_url,    # "https://gchostpay3-10-26/"
    encrypted_token=encrypted_token_payment
)

print(f"✅ [ENDPOINT_2] Enqueued payment execution to GCHostPay3")
```

**Cloud Tasks Enqueue**:
- Queue: `gchostpay3-queue`
- Target: `https://gchostpay3-10-26/`
- Payload: `{"token": "eyJhbGciOi..."}`

### Response
```json
{
  "status": "success",
  "message": "Status verified, payment execution enqueued",
  "unique_id": "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
  "cn_api_id": "cn_abc123def456",
  "changenow_status": "waiting",
  "task_id": "projects/.../tasks/..."
}
```

---

## 📊 Stage 8: GCHostPay1 → GCHostPay3-10-26 (ETH Payment Execution)

**Source**: GCHostPay1 via Cloud Tasks
**Endpoint**: `POST https://gchostpay3-10-26/`
**File**: `GCHostPay3-10-26/tphp3-10-26.py:111-533`

### Variables Received
```python
# GCHostPay3-10-26/tphp3-10-26.py:140-201
request_data = request.get_json()
token = request_data.get('token')

# Decrypt token from GCHostPay1
decrypted_data = token_manager.decrypt_gchostpay1_to_gchostpay3_token(token)

unique_id = "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"
cn_api_id = "cn_abc123def456"
from_currency = 'eth'
from_network = 'eth'
from_amount = 0.0  # Legacy field (deprecated)
actual_eth_amount = 0.02523456  # ✅ ACTUAL ETH from NowPayments
estimated_eth_amount = 0.0252  # ChangeNow estimate
payin_address = "0xCHANGENOW_RECEIVING_ADDRESS"
context = 'batch'

# Retry tracking
attempt_count = 1
first_attempt_at = 1699012678
last_error_code = None

print(f"✅ [ENDPOINT] Token decoded successfully")
print(f"🔢 [ENDPOINT] Attempt #{attempt_count}/3")
print(f"📋 [ENDPOINT] Context: {context}")
print(f"💎 [ENDPOINT] ACTUAL ETH: {actual_eth_amount} (from NowPayments)")
```

### Processing Steps

#### Step 8.1: Determine Payment Amount
```python
# GCHostPay3-10-26/tphp3-10-26.py:174-185
# CRITICAL: Determine which amount to use for payment
if actual_eth_amount > 0:
    payment_amount = actual_eth_amount  # 0.02523456 ETH
    print(f"✅ [ENDPOINT] Using ACTUAL ETH from NowPayments: {payment_amount}")
elif estimated_eth_amount > 0:
    payment_amount = estimated_eth_amount
    print(f"⚠️ [ENDPOINT] Using ESTIMATED ETH (actual not available): {payment_amount}")
elif from_amount > 0:
    payment_amount = from_amount
    print(f"⚠️ [ENDPOINT] Using legacy from_amount (backward compat): {payment_amount}")
else:
    abort(400, "Invalid payment amount")
```

**Decision**: `payment_amount = 0.02523456 ETH` (ACTUAL)

#### Step 8.2: Check Wallet Balance
```python
# GCHostPay3-10-26/tphp3-10-26.py:217-226
wallet_balance = wallet_manager.get_wallet_balance()
# Returns: 1.523456 ETH (example)

if wallet_balance < payment_amount:
    error_msg = f"Insufficient funds: need {payment_amount} ETH, have {wallet_balance} ETH"
    abort(400, error_msg)
else:
    print(f"✅ [ENDPOINT] Sufficient balance: {wallet_balance} ETH >= {payment_amount} ETH")
```

#### Step 8.3: Execute ETH Payment
```python
# GCHostPay3-10-26/tphp3-10-26.py:228-241
print(f"💰 [ENDPOINT] Executing ETH payment (attempt {attempt_count}/3)")
print(f"💎 [ENDPOINT] Amount to send: {payment_amount} ETH (ACTUAL from NowPayments)")

tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
    to_address=payin_address,  # "0xCHANGENOW_RECEIVING_ADDRESS"
    amount=payment_amount,     # 0.02523456 ETH
    unique_id=unique_id        # "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"
)

# Blockchain Transaction
{
  "tx_hash": "0x789abc...def123",
  "status": "success",
  "gas_used": 21000,
  "block_number": 18234567,
  "from": "0xHOST_WALLET_ADDRESS",
  "to": "0xCHANGENOW_RECEIVING_ADDRESS",
  "value": "0.02523456 ETH",
  "gas_price": "30 Gwei"
}

print(f"✅ [ENDPOINT] Payment successful after {attempt_count} attempt(s)")
print(f"🔗 [ENDPOINT] TX Hash: {tx_result['tx_hash']}")
```

#### Step 8.4: Log to Database
```python
# GCHostPay3-10-26/tphp3-10-26.py:253-277
db_success = db_manager.insert_hostpay_transaction(
    unique_id="batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
    cn_api_id="cn_abc123def456",
    from_currency='eth',
    from_network='eth',
    from_amount=0.02523456,
    payin_address="0xCHANGENOW_RECEIVING_ADDRESS",
    is_complete=True,
    tx_hash="0x789abc...def123",
    tx_status="success",
    gas_used=21000,
    block_number=18234567
)

print(f"✅ [ENDPOINT] Database: Successfully logged payment")
```

### Database Table: `hostpay_transactions`
```sql
INSERT INTO hostpay_transactions (
    unique_id,                   -- 'batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f'
    cn_api_id,                   -- 'cn_abc123def456'
    from_currency,               -- 'eth'
    from_network,                -- 'eth'
    from_amount,                 -- 0.02523456
    payin_address,               -- '0xCHANGENOW_RECEIVING_ADDRESS'
    is_complete,                 -- TRUE
    tx_hash,                     -- '0x789abc...def123'
    tx_status,                   -- 'success'
    gas_used,                    -- 21000
    block_number,                -- 18234567
    created_at                   -- CURRENT_TIMESTAMP
)
```

#### Step 8.5: Encrypt Response Token
```python
# GCHostPay3-10-26/tphp3-10-26.py:279-287
encrypted_response_token = token_manager.encrypt_gchostpay3_to_gchostpay1_token(
    unique_id="batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
    cn_api_id="cn_abc123def456",
    tx_hash="0x789abc...def123",
    tx_status="success",
    gas_used=21000,
    block_number=18234567
)
```

**Token Contents** (for GCHostPay1):
```python
{
    'unique_id': 'batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f',
    'cn_api_id': 'cn_abc123def456',
    'tx_hash': '0x789abc...def123',
    'tx_status': 'success',
    'gas_used': 21000,
    'block_number': 18234567,
    'timestamp': 1699012789
}
```

#### Step 8.6: Route Response Based on Context
```python
# GCHostPay3-10-26/tphp3-10-26.py:293-331
# Detect routing from context
if context == 'threshold':
    # Route to GCAccumulator (NOT USED IN THIS FLOW)
    print(f"🎯 [ENDPOINT] Context: threshold → Routing to GCAccumulator")
else:
    # Route to GCHostPay1 (BATCH USES THIS PATH)
    print(f"🎯 [ENDPOINT] Context: batch → Routing to GCHostPay1")

    gchostpay1_response_queue = config.get('gchostpay1_response_queue')
    gchostpay1_url = config.get('gchostpay1_url')

    # Target the /payment-completed endpoint
    target_url = f"{gchostpay1_url}/payment-completed"
    queue_name = gchostpay1_response_queue
```

#### Step 8.7: Enqueue Response to GCHostPay1
```python
# GCHostPay3-10-26/tphp3-10-26.py:333-342
task_name = cloudtasks_client.enqueue_gchostpay1_payment_response(
    queue_name=queue_name,      # "gchostpay1-response-queue"
    target_url=target_url,      # "https://gchostpay1-10-26/payment-completed"
    encrypted_token=encrypted_response_token
)

print(f"✅ [ENDPOINT] Successfully enqueued response")
```

**Cloud Tasks Enqueue**:
- Queue: `gchostpay1-response-queue`
- Target: `https://gchostpay1-10-26/payment-completed`
- Payload: `{"token": "eyJhbGciOi..."}`

### Response
```json
{
  "status": "success",
  "message": "Payment executed and response enqueued",
  "unique_id": "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
  "cn_api_id": "cn_abc123def456",
  "tx_hash": "0x789abc...def123",
  "tx_status": "success",
  "gas_used": 21000,
  "block_number": 18234567,
  "attempt": 1,
  "task_id": "projects/.../tasks/..."
}
```

**⚠️ IMPORTANT**: At this point, ETH has been sent to ChangeNow. ChangeNow will convert ETH→USDT and send USDT to host wallet. This takes ~5-15 minutes depending on blockchain confirmation times.

---

## 📊 Stage 9: GCHostPay3 → GCHostPay1-10-26 (Payment Completed)

**Source**: GCHostPay3 via Cloud Tasks
**Endpoint**: `POST https://gchostpay1-10-26/payment-completed`
**File**: `GCHostPay1-10-26/tphp1-10-26.py:512-651`

### Variables Received
```python
# GCHostPay1-10-26/tphp1-10-26.py:537-567
request_data = request.get_json()
token = request_data.get('token')

# Decrypt token from GCHostPay3
decrypted_data = token_manager.decrypt_gchostpay3_to_gchostpay1_token(token)

unique_id = "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"
cn_api_id = "cn_abc123def456"
tx_hash = "0x789abc...def123"
tx_status = "success"
gas_used = 21000
block_number = 18234567

print(f"✅ [ENDPOINT_3] Token decoded successfully")
print(f"🔗 [ENDPOINT_3] TX Hash: {tx_hash}")
print(f"📊 [ENDPOINT_3] TX Status: {tx_status}")
```

### Processing Steps

#### Step 9.1: Detect Context
```python
# GCHostPay1-10-26/tphp1-10-26.py:575-588
# Detect context from unique_id prefix
context = None
if unique_id.startswith('batch_'):
    context = 'batch'
    print(f"🔀 [ENDPOINT_3] Detected batch conversion context")
elif unique_id.startswith('acc_'):
    context = 'threshold'
    print(f"🔀 [ENDPOINT_3] Detected threshold payout context")
else:
    context = 'instant'
    print(f"🔀 [ENDPOINT_3] Detected instant conversion context (no callback needed)")

# context = 'batch'
```

#### Step 9.2: Query ChangeNow for Actual USDT Received
```python
# GCHostPay1-10-26/tphp1-10-26.py:590-608
# CRITICAL: Query ChangeNow API for actual USDT received
actual_usdt_received = None

print(f"🔍 [ENDPOINT_3] Querying ChangeNow for actual USDT received...")
cn_status = changenow_client.get_transaction_status(cn_api_id)

# ChangeNow API Response (after conversion completes)
{
  "id": "cn_abc123def456",
  "status": "finished",  // Conversion completed
  "fromCurrency": "eth",
  "toCurrency": "usdt",
  "fromAmount": 0.02523456,
  "toAmount": 60.15,  // ACTUAL USDT received
  "amountTo": 60.15,  // Same as toAmount
  "payinHash": "0x789abc...def123",  // Our payment
  "payoutHash": "0xabc123...789def",  // ChangeNow's USDT transfer
  "payinAddress": "0xCHANGENOW_RECEIVING_ADDRESS",
  "payoutAddress": "0x9876543210FEDCBA9876543210FEDCBA98765432"
}

if cn_status and cn_status.get('status') == 'finished':
    actual_usdt_received = float(cn_status.get('amountTo', 0))  # 60.15
    print(f"✅ [ENDPOINT_3] Actual USDT received: ${actual_usdt_received}")
else:
    print(f"⚠️ [ENDPOINT_3] ChangeNow transaction not finished yet: {cn_status.get('status')}")
```

**Critical**: `actual_usdt_received = 60.15 USDT`

#### Step 9.3: Extract Batch Conversion ID
```python
# GCHostPay1-10-26/tphp1-10-26.py:610-614
# Extract batch_conversion_id from unique_id
batch_conversion_id = unique_id.replace('batch_', '')
# = "a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"

print(f"🆔 [ENDPOINT_3] Batch conversion ID: {batch_conversion_id}")
```

#### Step 9.4: Route Batch Callback
```python
# GCHostPay1-10-26/tphp1-10-26.py:616-622
print(f"🎯 [ENDPOINT_3] Routing batch callback to GCMicroBatchProcessor")

_route_batch_callback(
    batch_conversion_id="a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
    cn_api_id="cn_abc123def456",
    tx_hash="0x789abc...def123",
    actual_usdt_received=60.15
)
```

### Function: _route_batch_callback()
```python
# GCHostPay1-10-26/tphp1-10-26.py:92-176
def _route_batch_callback(
    batch_conversion_id: str,
    cn_api_id: str,
    tx_hash: str,
    actual_usdt_received: float
) -> bool:
    print(f"📤 [BATCH_CALLBACK] Preparing callback to GCMicroBatchProcessor")
    print(f"🆔 [BATCH_CALLBACK] Batch ID: {batch_conversion_id}")
    print(f"💰 [BATCH_CALLBACK] Actual USDT: ${actual_usdt_received}")

    # Encrypt response token for MicroBatchProcessor
    response_token = token_manager.encrypt_gchostpay1_to_microbatch_response_token(
        batch_conversion_id="a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
        cn_api_id="cn_abc123def456",
        tx_hash="0x789abc...def123",
        actual_usdt_received=60.15
    )

    # Get MicroBatchProcessor config
    microbatch_response_queue = config.get('microbatch_response_queue')
    microbatch_url = config.get('microbatch_url')

    # Prepare callback payload
    payload = {
        'token': response_token
    }

    # Append endpoint path
    callback_url = f"{microbatch_url}/swap-executed"
    print(f"📡 [BATCH_CALLBACK] Enqueueing callback to: {callback_url}")

    # Enqueue callback task
    task_success = cloudtasks_client.enqueue_task(
        queue_name=microbatch_response_queue,  # "microbatch-response-queue"
        url=callback_url,                       # "https://gcmicrobatchprocessor-10-26/swap-executed"
        payload=payload
    )

    print(f"✅ [BATCH_CALLBACK] Callback enqueued successfully")
    return True
```

**Encrypted Token Contents** (for MicroBatchProcessor):
```python
{
    'batch_conversion_id': 'a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f',
    'cn_api_id': 'cn_abc123def456',
    'tx_hash': '0x789abc...def123',
    'actual_usdt_received': 60.15,  # CRITICAL: ACTUAL amount received
    'timestamp': 1699012890
}
```

**Cloud Tasks Enqueue**:
- Queue: `microbatch-response-queue`
- Target: `https://gcmicrobatchprocessor-10-26/swap-executed`
- Payload: `{"token": "eyJhbGciOi..."}`

### Response
```json
{
  "status": "success",
  "message": "Payment workflow completed",
  "unique_id": "batch_a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
  "cn_api_id": "cn_abc123def456",
  "tx_hash": "0x789abc...def123",
  "tx_status": "success",
  "gas_used": 21000,
  "block_number": 18234567
}
```

---

## 📊 Stage 10: GCHostPay1 → GCMicroBatchProcessor-10-26 (Swap Executed Callback)

**Source**: GCHostPay1 via Cloud Tasks
**Endpoint**: `POST https://gcmicrobatchprocessor-10-26/swap-executed`
**File**: `GCMicroBatchProcessor-10-26/microbatch10-26.py:292-415`

### Variables Received
```python
# GCMicroBatchProcessor-10-26/microbatch10-26.py:317-340
request_data = request.get_json()
encrypted_token = request_data.get('token')

# Decrypt token from GCHostPay1
decrypted_data = token_manager.decrypt_gchostpay1_to_microbatch_token(encrypted_token)

batch_conversion_id = "a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f"
cn_api_id = "cn_abc123def456"
tx_hash = "0x789abc...def123"
actual_usdt_received = Decimal("60.15")

print(f"✅ [ENDPOINT] Token decrypted successfully")
print(f"🆔 [ENDPOINT] Batch Conversion ID: {batch_conversion_id}")
print(f"💰 [ENDPOINT] Actual USDT received: ${actual_usdt_received}")
print(f"🔗 [ENDPOINT] TX Hash: {tx_hash}")
```

### Processing Steps

#### Step 10.1: Fetch Batch Records
```python
# GCMicroBatchProcessor-10-26/microbatch10-26.py:348-354
batch_records = db_manager.get_records_by_batch(batch_conversion_id)

# Query:
"""
SELECT
    id, client_id, user_id, subscription_id,
    payment_amount_usd, accumulated_eth,
    client_wallet_address, client_payout_currency, client_payout_network
FROM payout_accumulation
WHERE batch_conversion_id = %s
  AND conversion_status = 'swapping'
"""

# Results:
[
  {
    'id': 101,
    'client_id': -1003268562225,
    'user_id': 6271402111,
    'accumulated_eth': Decimal('33.95'),
    'payment_amount_usd': Decimal('35.00'),
    ...
  },
  {
    'id': 102,
    'client_id': -1003268562225,
    'user_id': 6271402222,
    'accumulated_eth': Decimal('27.90'),
    'payment_amount_usd': Decimal('29.00'),
    ...
  }
]

print(f"📊 [ENDPOINT] Found {len(batch_records)} record(s) in batch")
# len(batch_records) = 2
```

#### Step 10.2: Calculate Proportional Distribution
```python
# GCMicroBatchProcessor-10-26/microbatch10-26.py:359-367
distributions = db_manager.distribute_usdt_proportionally(
    pending_records=batch_records,
    actual_usdt_received=Decimal("60.15")
)

# Calculation Logic:
# Total accumulated_eth: 33.95 + 27.90 = 61.85
# Actual USDT received: 60.15

# Record 101:
#   Share = (33.95 / 61.85) * 60.15 = 33.01 USDT
# Record 102:
#   Share = (27.90 / 61.85) * 60.15 = 27.14 USDT
# Total: 33.01 + 27.14 = 60.15 ✅

# Returns:
[
  {'id': 101, 'usdt_share': Decimal('33.01')},
  {'id': 102, 'usdt_share': Decimal('27.14')}
]

print(f"💰 [ENDPOINT] Calculating proportional USDT distribution")
```

#### Step 10.3: Update Records with USDT Shares
```python
# GCMicroBatchProcessor-10-26/microbatch10-26.py:370-384
for distribution in distributions:
    record_id = distribution['id']
    usdt_share = distribution['usdt_share']

    success = db_manager.update_record_usdt_share(
        record_id=record_id,
        usdt_share=usdt_share,
        tx_hash=tx_hash
    )

    if success:
        print(f"✅ [ENDPOINT] Record {record_id}: ${usdt_share} USDT")

# Updates:
# Record 101: usdt_share=33.01, tx_hash='0x789abc...def123'
# Record 102: usdt_share=27.14, tx_hash='0x789abc...def123'
```

### Database Updates: `payout_accumulation`
```sql
-- Record 101
UPDATE payout_accumulation
SET
    usdt_share = 33.01,
    tx_hash = '0x789abc...def123',
    conversion_status = 'completed',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 101;

-- Record 102
UPDATE payout_accumulation
SET
    usdt_share = 27.14,
    tx_hash = '0x789abc...def123',
    conversion_status = 'completed',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 102;
```

#### Step 10.4: Finalize Batch Conversion
```python
# GCMicroBatchProcessor-10-26/microbatch10-26.py:386-396
batch_finalized = db_manager.finalize_batch_conversion(
    batch_conversion_id="a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
    actual_usdt_received=Decimal("60.15"),
    tx_hash="0x789abc...def123"
)

print(f"✅ [ENDPOINT] Batch conversion finalized successfully")
```

### Database Update: `batch_conversions`
```sql
UPDATE batch_conversions
SET
    status = 'completed',
    actual_usdt_received = 60.15,
    tx_hash = '0x789abc...def123',
    completed_at = CURRENT_TIMESTAMP
WHERE batch_conversion_id = 'a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f';
```

### Response
```json
{
  "status": "success",
  "message": "Swap executed and USDT distributed successfully",
  "batch_conversion_id": "a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d5e6f",
  "actual_usdt_received": "60.15",
  "records_updated": 2,
  "tx_hash": "0x789abc...def123"
}
```

**🎉 COMPLETION**: The threshold payout workflow is now complete!

---

## 📊 Final Database State Summary

### Table: `payout_accumulation`
```
ID  | client_id        | user_id    | accumulated_eth | usdt_share | conversion_status | batch_conversion_id           | tx_hash
----|------------------|------------|-----------------|------------|-------------------|-------------------------------|-------------------
101 | -1003268562225   | 6271402111 | 33.95           | 33.01      | completed         | a7f3c9e1-2b4d-4f8a-9c3e...   | 0x789abc...def123
102 | -1003268562225   | 6271402222 | 27.90           | 27.14      | completed         | a7f3c9e1-2b4d-4f8a-9c3e...   | 0x789abc...def123
```

### Table: `batch_conversions`
```
batch_conversion_id                  | total_eth_usd | threshold | cn_api_id       | payin_address          | actual_usdt_received | status    | tx_hash
-------------------------------------|---------------|-----------|-----------------|------------------------|----------------------|-----------|-------------------
a7f3c9e1-2b4d-4f8a-9c3e-1a2b3c4d... | 61.85         | 50.00     | cn_abc123def456 | 0xCHANGENOW_...        | 60.15                | completed | 0x789abc...def123
```

### Table: `hostpay_transactions`
```
unique_id                           | cn_api_id       | from_amount  | payin_address          | tx_hash           | tx_status | block_number
------------------------------------|-----------------|--------------|------------------------|-------------------|-----------|-------------
batch_a7f3c9e1-2b4d-4f8a-9c3e...   | cn_abc123def456 | 0.02523456   | 0xCHANGENOW_...        | 0x789abc...def123 | success   | 18234567
```

---

## 🔑 Key Variables Summary

### Critical Amounts Tracked Throughout Flow

| Variable Name | Stage | Value | Type | Description |
|---------------|-------|-------|------|-------------|
| `subscription_price` | NOWPayments → np-webhook | "35.00" | string | Declared subscription price (USD) |
| `outcome_amount` | NOWPayments IPN | "0.01200000" | string | Actual ETH customer paid |
| `outcome_amount_usd` | np-webhook calculation | 29.415 | float | USD value of received ETH |
| `payment_amount_usd` | GCWebhook1 → GCAccumulator | "35.00" | string | Original subscription price |
| `accumulated_eth` | GCAccumulator storage | 33.95 | Decimal | USD value after TP fee (3%) |
| `total_pending` | MicroBatchProcessor check | 61.85 | Decimal | Sum of accumulated_eth |
| `total_actual_eth` | MicroBatchProcessor check | 0.02523456 | float | Sum of actual ETH from NowPayments |
| `eth_for_swap` | ChangeNow swap creation | 0.02523456 | float | ETH to send to ChangeNow |
| `payment_amount` | GCHostPay3 execution | 0.02523456 | float | ETH sent to ChangeNow |
| `actual_usdt_received` | ChangeNow completion | 60.15 | Decimal | USDT received from ChangeNow |
| `usdt_share` | Proportional distribution | 33.01, 27.14 | Decimal | Individual user's USDT share |

---

## 🎓 Architecture Notes

### Why Threshold Payout?

**Problem**: Small payments (e.g., $35) have high percentage fees on crypto exchanges.

**Example**:
- Payment: $35
- Exchange fee: $3
- User receives: $32 (91% efficiency)

**Solution**: Accumulate multiple small payments, then batch-convert:
- Payment 1: $35 → Accumulate
- Payment 2: $29 → Accumulate
- Total: $64 → Batch convert
- Exchange fee: $3.85
- Total received: $60.15 (94% efficiency)

**Benefit**: 3% efficiency improvement + better exchange rates for larger amounts

### Critical Design Decisions

1. **Accumulated_eth Misnomer**: Despite the name, this field stores USD value, not ETH. This is a legacy naming issue.

2. **ACTUAL vs ESTIMATED ETH**: The system tracks both:
   - `nowpayments_outcome_amount`: ACTUAL ETH received from customer
   - ChangeNow estimates: ESTIMATED ETH for planning
   - **Payment uses ACTUAL** for accuracy

3. **Proportional Distribution**: USDT is distributed based on USD contribution, not payment count:
   - User A: $33.95 / $61.85 = 54.8% → 33.01 USDT
   - User B: $27.90 / $61.85 = 45.2% → 27.14 USDT

4. **Batch Threshold**: Set via Secret Manager for easy adjustment without code changes.

5. **15-Minute Scheduler**: Balances between:
   - Too frequent: Wasteful if threshold not reached
   - Too infrequent: Users wait longer for payouts

6. **Context-Based Routing**: `unique_id` prefix determines response routing:
   - `batch_*` → Route to MicroBatchProcessor
   - `acc_*` → Route to Accumulator
   - Regular → Route to GCHostPay1

---

## 🔄 Flow Comparison: Threshold vs Instant

| Stage | Threshold Payout | Instant Payout |
|-------|------------------|----------------|
| 1-2 | NOWPayments → np-webhook → GCWebhook1 | Same |
| 3 | GCWebhook1 → **GCAccumulator** (storage only) | GCWebhook1 → **GCSplit1** (immediate conversion) |
| 4 | Wait for threshold (Cloud Scheduler) | GCSplit1 → GCSplit2 (USDT estimate) |
| 5 | **GCMicroBatchProcessor** creates batch | GCSplit2 → GCSplit1 (estimate response) |
| 6 | MicroBatch → GCHostPay1 | GCSplit1 → GCSplit3 (ETH→Client swap) |
| 7 | GCHostPay1 → GCHostPay2 → GCHostPay1 | GCSplit3 → GCSplit1 (swap response) |
| 8 | GCHostPay1 → GCHostPay3 (execute ETH payment) | GCSplit1 → GCHostPay1 |
| 9 | GCHostPay3 → GCHostPay1 (payment complete) | GCHostPay1 → GCHostPay2 → GCHostPay3 |
| 10 | GCHostPay1 → **MicroBatchProcessor** (distribute USDT) | GCHostPay3 → GCHostPay1 (complete) |

**Key Difference**: Threshold payout adds accumulation + batch processing stages.

---

## 📝 Glossary

| Term | Definition |
|------|------------|
| **IPN** | Instant Payment Notification - Webhook from NOWPayments |
| **outcome_amount** | Actual crypto amount received after processing |
| **accumulated_eth** | Misleading name - stores USD value pending conversion |
| **batch_conversion_id** | UUID identifying a group of accumulated payments |
| **threshold** | Minimum USD value required to trigger batch conversion |
| **usdt_share** | Individual user's proportional share of USDT |
| **payin_address** | ChangeNow's wallet address for receiving ETH |
| **payout_address** | Client's wallet address for receiving final crypto |
| **context** | Routing indicator: 'instant', 'threshold', or 'batch' |

---

**Document Generated**: 2025-11-03
**Flow Analysis Complete**: Threshold Payout Method
**Total Stages**: 10
**Total Services**: 9 (np-webhook, GCWebhook1, GCWebhook2, GCAccumulator, MicroBatchProcessor, GCHostPay1, GCHostPay2, GCHostPay3, ChangeNow)
**Total Database Tables**: 3 (payout_accumulation, batch_conversions, hostpay_transactions)
