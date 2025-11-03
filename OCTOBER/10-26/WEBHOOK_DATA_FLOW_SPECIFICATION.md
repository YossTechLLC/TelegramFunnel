# Webhook Data Flow Specification
**Document Version**: 1.0
**Date**: 2025-11-03
**Purpose**: Complete specification of data structures and types flowing between NOWPayments → np-webhook → GCWebhook1

---

## Table of Contents
1. [Overview](#overview)
2. [Stage 1: NOWPayments IPN → np-webhook](#stage-1-nowpayments-ipn--np-webhook)
3. [Stage 2: np-webhook → GCWebhook1](#stage-2-np-webhook--gcwebhook1)
4. [Type Safety Issues](#type-safety-issues)
5. [Data Transformation](#data-transformation)
6. [Validation Rules](#validation-rules)

---

## Overview

### Payment Processing Pipeline

```
┌─────────────────┐
│  NOWPayments    │  User pays with crypto
│   (External)    │  Creates IPN callback
└────────┬────────┘
         │ HTTP POST / with IPN payload
         │ Header: x-nowpayments-sig (HMAC-SHA512)
         ▼
┌─────────────────┐
│   np-webhook    │  1. Verify signature
│   -10-26        │  2. Update database
│                 │  3. Fetch CoinGecko price
│                 │  4. Calculate outcome_amount_usd
└────────┬────────┘
         │ Cloud Tasks JSON payload
         │ Queue: gcwebhook1-queue
         ▼
┌─────────────────┐
│  GCWebhook1     │  1. Route to instant/accumulator
│   -10-26        │  2. Queue to GCSplit1/GCAccumulator
│                 │  3. Queue Telegram invite
└─────────────────┘
```

---

## Stage 1: NOWPayments IPN → np-webhook

### HTTP Request Details

**Endpoint**: `POST https://np-webhook-10-26-pjxwjsdktq-uc.a.run.app/`

**Headers**:
```
Content-Type: application/json
x-nowpayments-sig: <HMAC-SHA512 signature of request body>
User-Agent: NOWPayments v1.0
```

**Signature Verification**:
```python
# Calculate expected signature
expected_sig = hmac.new(
    NOWPAYMENTS_IPN_SECRET.encode('utf-8'),
    raw_request_body_bytes,
    hashlib.sha512
).hexdigest()

# Compare with x-nowpayments-sig header
is_valid = hmac.compare_digest(expected_sig, received_signature)
```

### IPN Payload Structure

**JSON Body** (from NOWPayments):

```json
{
  "payment_id": "6271827386",
  "invoice_id": "1234567890",
  "order_id": "PGP-6271402111|-1003268562225",
  "order_description": "Subscription to private channel",
  "price_amount": "35.00",
  "price_currency": "USD",
  "pay_amount": "0.01234567",
  "pay_currency": "ETH",
  "pay_address": "0x1234567890abcdef1234567890abcdef12345678",
  "payment_status": "finished",
  "outcome_amount": "0.01200000",
  "outcome_currency": "ETH"
}
```

### Field Specifications (NOWPayments → np-webhook)

| Field Name | Data Type | Source Type | Description | Required | Example |
|------------|-----------|-------------|-------------|----------|---------|
| `payment_id` | string | string | Unique NOWPayments payment identifier | ✅ Yes | `"6271827386"` |
| `invoice_id` | string | string | Invoice ID from NOWPayments | ❌ No | `"1234567890"` |
| `order_id` | string | string | Custom order ID (format: `PGP-{user_id}\|{channel_id}`) | ✅ Yes | `"PGP-6271402111\|-1003268562225"` |
| `order_description` | string | string | Human-readable order description | ❌ No | `"Subscription to channel"` |
| `price_amount` | decimal | string | Original declared price (what user agreed to pay) | ✅ Yes | `"35.00"` |
| `price_currency` | string | string | Currency of declared price (usually USD) | ✅ Yes | `"USD"` |
| `pay_amount` | decimal | string | Amount user actually paid in crypto | ✅ Yes | `"0.01234567"` |
| `pay_currency` | string | string | Cryptocurrency user paid with | ✅ Yes | `"ETH"`, `"BTC"`, `"USDT"` |
| `pay_address` | string | string | Blockchain address where payment was sent | ✅ Yes | `"0x123...789"` |
| `payment_status` | string | string | Payment status from NOWPayments | ✅ Yes | `"finished"`, `"confirmed"`, `"sending"` |
| `outcome_amount` | decimal | string | Amount received after fees (in crypto) | ✅ Yes | `"0.01200000"` |
| `outcome_currency` | string | string | Cryptocurrency of outcome amount | ⚠️ Optional | `"ETH"` (if missing, infer from `pay_currency`) |

**Notes**:
- ⚠️ **Type Warning**: NOWPayments sends numeric values as **strings** in JSON (e.g., `"35.00"`, not `35.00`)
- All amount fields (`price_amount`, `pay_amount`, `outcome_amount`) are **decimal strings**, not numbers
- `order_id` contains user and channel information encoded as: `PGP-{user_id}|{channel_id}`
- Negative channel IDs are preserved using `|` separator (e.g., `-1003268562225`)

### np-webhook Processing

**Code Location**: `np-webhook-10-26/app.py:489-820`

**Steps**:
1. **Signature Verification** (lines 501-518)
   - Extract `x-nowpayments-sig` header
   - Calculate HMAC-SHA512 of raw request body
   - Compare signatures (constant-time comparison)
   - Return 403 if invalid

2. **Database Update** (lines 546-578)
   - Parse `order_id` to extract `user_id` and `open_channel_id`
   - Lookup `closed_channel_id` from `main_clients_database`
   - Update `private_channel_users_database` with NOWPayments fields:
     ```python
     {
       'payment_id': str,           # NOWPayments ID
       'invoice_id': str,           # Invoice ID
       'order_id': str,             # PGP-{user}|{channel}
       'pay_address': str,          # Blockchain address
       'payment_status': str,       # "finished", "confirmed"
       'pay_amount': Decimal,       # Amount paid (as stored in DB)
       'pay_currency': str,         # "ETH", "BTC", etc.
       'outcome_amount': Decimal,   # After-fee amount (as stored in DB)
       'price_amount': Decimal,     # Original USD price
       'price_currency': str,       # "USD"
       'outcome_currency': str      # "ETH", "USDT", etc.
     }
     ```

3. **CoinGecko Price Fetching** (lines 580-610)
   - Check if `outcome_currency` is already USD/stablecoin
   - If stablecoin: `outcome_amount_usd = outcome_amount` (1:1)
   - If crypto: Fetch current price from CoinGecko API
   - Calculate: `outcome_amount_usd = outcome_amount * crypto_usd_price`
   - Store result in `private_channel_users_database.nowpayments_outcome_amount_usd`

4. **Idempotency Check** (lines 672-752)
   - Query `processed_payments` table for `payment_id`
   - If already processed: Return 200 (skip re-processing)
   - If new: Insert record with `gcwebhook1_processed = FALSE`
   - Prevents race conditions and duplicate processing

5. **GCWebhook1 Trigger** (lines 754-820)
   - Enqueue payment to `gcwebhook1-queue` via Cloud Tasks
   - See [Stage 2](#stage-2-np-webhook--gcwebhook1) for payload details

### CoinGecko Integration

**API Endpoint**: `https://api.coingecko.com/api/v3/simple/price`

**Supported Cryptocurrencies**:
```python
{
  'ETH': 'ethereum',
  'BTC': 'bitcoin',
  'USDT': 'tether',      # ← Treated as $1.00 (no API call)
  'USDC': 'usd-coin',    # ← Treated as $1.00 (no API call)
  'LTC': 'litecoin',
  'TRX': 'tron',
  'BNB': 'binancecoin',
  'SOL': 'solana',
  'MATIC': 'matic-network'
}
```

**Price Calculation Example**:
```
User pays: 0.012 ETH
ETH/USD price from CoinGecko: $2,450.50
outcome_amount_usd = 0.012 * 2450.50 = $29.41

# This is the ACTUAL value received, NOT the declared price
# Declared price was $35.00, but due to slippage/fees, only $29.41 received
```

---

## Stage 2: np-webhook → GCWebhook1

### HTTP Request Details

**Method**: Cloud Tasks HTTP POST (internal Google infrastructure)

**Endpoint**: `POST https://gcwebhook1-10-26-pjxwjsdktq-uc.a.run.app/process-validated-payment`

**Headers**:
```
Content-Type: application/json
User-Agent: Google-Cloud-Tasks
X-CloudTasks-QueueName: gcwebhook1-queue
X-CloudTasks-TaskName: ...
X-CloudTasks-TaskRetryCount: 0
```

**Authentication**: None (relies on Cloud Run service-to-service auth)

### Payload Structure (np-webhook → GCWebhook1)

**Code Location**:
- **Sender**: `np-webhook-10-26/cloudtasks_client.py:76-88`
- **Receiver**: `GCWebhook1-10-26/tph1-10-26.py:224-246`

**JSON Body**:
```json
{
  "user_id": 6271402111,
  "closed_channel_id": -1003268562225,
  "wallet_address": "TXyz123ABC456def789GHI012jkl345MNO678pqr",
  "payout_currency": "USDT",
  "payout_network": "trc20",
  "subscription_time_days": 30,
  "subscription_price": "35.00",
  "outcome_amount_usd": 29.41,
  "nowpayments_payment_id": "6271827386",
  "nowpayments_pay_address": "0x1234567890abcdef1234567890abcdef12345678",
  "nowpayments_outcome_amount": 0.012
}
```

### Field Specifications (np-webhook → GCWebhook1)

| Field Name | Data Type | Sent As | Received As | Description | Source |
|------------|-----------|---------|-------------|-------------|--------|
| `user_id` | integer | int | int/string ⚠️ | Telegram user ID | Parsed from `order_id` |
| `closed_channel_id` | integer | int | int/string ⚠️ | Private channel ID (negative) | Looked up from database |
| `wallet_address` | string | string | string | User's payout wallet address | Database (`main_clients_database`) |
| `payout_currency` | string | string | string | Desired payout currency | Database (`client_payout_currency`) |
| `payout_network` | string | string | string | Blockchain network for payout | Database (`client_payout_network`) |
| `subscription_time_days` | integer | int | int/string ⚠️ | Subscription duration (days) | Database (`sub_time`) |
| `subscription_price` | string/float | string | string/float ⚠️ | **Original declared price** | Database (`sub_price`) |
| `outcome_amount_usd` | float | float | float/string ⚠️ | **🔥 ACTUAL USD value received** | Calculated by np-webhook |
| `nowpayments_payment_id` | string | string | string | NOWPayments payment ID | IPN field `payment_id` |
| `nowpayments_pay_address` | string | string | string | Blockchain address used for payment | IPN field `pay_address` |
| `nowpayments_outcome_amount` | float | float | float/string ⚠️ | Crypto amount after fees | IPN field `outcome_amount` |

**Critical Field Explanations**:

### 🔥 `outcome_amount_usd` (MOST IMPORTANT)
- **Purpose**: The **ACTUAL** USD value of what was received
- **Calculation**: `outcome_amount (crypto) × current_market_price (from CoinGecko)`
- **Why Important**: Determines actual payout amounts to channel owner
- **Example**: User pays ETH, declared price is $35, but actual value received is $29.41
- **Used For**: Splitting payments, calculating channel owner payout

### 📋 `subscription_price` (REFERENCE ONLY)
- **Purpose**: The **DECLARED** price user agreed to pay
- **Type**: String (converted from Decimal in database)
- **Why String**: Used for token encryption/validation (needs deterministic serialization)
- **Example**: `"35.00"` (string, not number)
- **Used For**: Telegram invite validation, subscription record-keeping, analytics

### Data Type Warning ⚠️

**JSON Serialization Issues**:
```python
# What np-webhook SENDS (Python types):
payload = {
    "user_id": 6271402111,                    # int
    "closed_channel_id": -1003268562225,      # int
    "subscription_time_days": 30,             # int
    "subscription_price": "35.00",            # string
    "outcome_amount_usd": 29.41,              # float
    "nowpayments_outcome_amount": 0.012       # float
}

# What GCWebhook1 RECEIVES (after JSON serialization):
# Depends on json.dumps() behavior and Cloud Tasks handling:
{
    "user_id": "6271402111",                  # ⚠️ MAY BE STRING
    "closed_channel_id": "-1003268562225",    # ⚠️ MAY BE STRING
    "subscription_time_days": "30",           # ⚠️ MAY BE STRING
    "subscription_price": "35.00",            # string (intended)
    "outcome_amount_usd": "29.41",            # ⚠️ MAY BE STRING
    "nowpayments_outcome_amount": "0.012"     # ⚠️ MAY BE STRING
}
```

**Root Cause**: JSON doesn't preserve Python types. Numbers can be serialized as strings depending on:
- How `json.dumps()` is called
- Source data type (Decimal vs float vs int)
- Cloud Tasks internal JSON handling

---

## Type Safety Issues

### Current Problems

#### Problem 1: No Type Validation at Entry Point

**Code**: `GCWebhook1-10-26/tph1-10-26.py:232-246`

```python
# ❌ CURRENT CODE (unsafe):
user_id = payment_data.get('user_id')
closed_channel_id = payment_data.get('closed_channel_id')
subscription_price = payment_data.get('subscription_price')
outcome_amount_usd = payment_data.get('outcome_amount_usd')

# Types are UNKNOWN here - could be int, str, float, None
```

**What Goes Wrong**:
```python
# Line 469: Calculate difference
"difference": outcome_amount_usd - subscription_price
# ❌ TypeError: unsupported operand type(s) for -: 'float' and 'str'

# If outcome_amount_usd=29.41 (float) and subscription_price="35.00" (string)
# Python cannot subtract string from float
```

#### Problem 2: Inconsistent Type Conversion

**Code**: `GCWebhook1-10-26/tph1-10-26.py:250-259`

```python
# ✅ CONVERTS integers:
try:
    user_id = int(user_id) if user_id is not None else None
    closed_channel_id = int(closed_channel_id) if closed_channel_id is not None else None
    subscription_time_days = int(subscription_time_days) if subscription_time_days is not None else None
except (ValueError, TypeError) as e:
    abort(400, f"Invalid integer field types: {e}")

# ❌ DOES NOT CONVERT floats:
# subscription_price, outcome_amount_usd left as-is (could be strings!)
```

#### Problem 3: Late Conversion

**Code**: `GCWebhook1-10-26/tph1-10-26.py:392`

```python
# Convert to string for token encryption (line 392):
subscription_price = str(subscription_price)

# But then use for arithmetic without converting back (line 469):
"difference": outcome_amount_usd - subscription_price  # ❌ str cannot be subtracted
```

**Fix Applied** (revision 00021-2pp):
```python
# Line 469 (TEMPORARY FIX):
"difference": outcome_amount_usd - float(subscription_price)  # ✅ Works
```

### Recommended Solution

**Implement Type Validation at Entry Point**:

```python
# File: GCWebhook1-10-26/tph1-10-26.py
# Location: Lines 232-280 (expand existing validation)

# Extract all fields
user_id = payment_data.get('user_id')
closed_channel_id = payment_data.get('closed_channel_id')
wallet_address = payment_data.get('wallet_address')
payout_currency = payment_data.get('payout_currency')
payout_network = payment_data.get('payout_network')
subscription_time_days = payment_data.get('subscription_time_days')
subscription_price = payment_data.get('subscription_price')
outcome_amount_usd = payment_data.get('outcome_amount_usd')
nowpayments_payment_id = payment_data.get('nowpayments_payment_id')
nowpayments_pay_address = payment_data.get('nowpayments_pay_address')
nowpayments_outcome_amount = payment_data.get('nowpayments_outcome_amount')

# NORMALIZE ALL TYPES (defensive programming)
try:
    # Convert integers
    user_id = int(user_id) if user_id is not None else None
    closed_channel_id = int(closed_channel_id) if closed_channel_id is not None else None
    subscription_time_days = int(subscription_time_days) if subscription_time_days is not None else None

    # ✅ ADD: Convert floats
    subscription_price = float(subscription_price) if subscription_price is not None else None
    outcome_amount_usd = float(outcome_amount_usd) if outcome_amount_usd is not None else None
    if nowpayments_outcome_amount:
        nowpayments_outcome_amount = float(nowpayments_outcome_amount)

    # Strings are already strings (wallet_address, payout_currency, etc.)

except (ValueError, TypeError) as e:
    print(f"❌ [VALIDATED] Type conversion error: {e}")
    print(f"   user_id: {payment_data.get('user_id')} (type: {type(payment_data.get('user_id'))})")
    print(f"   subscription_price: {payment_data.get('subscription_price')} (type: {type(payment_data.get('subscription_price'))})")
    print(f"   outcome_amount_usd: {payment_data.get('outcome_amount_usd')} (type: {type(payment_data.get('outcome_amount_usd'))})")
    abort(400, f"Invalid field types: {e}")

# NOW types are guaranteed:
# user_id: int
# closed_channel_id: int
# subscription_time_days: int
# subscription_price: float
# outcome_amount_usd: float
# nowpayments_outcome_amount: float
# All string fields: str
```

**Benefits**:
1. ✅ Catches type errors early with clear error messages
2. ✅ All downstream code can assume correct types
3. ✅ No need for `float()` casts later in code
4. ✅ Consistent with existing int conversion pattern
5. ✅ Can still convert to string for token encryption (line 392)

---

## Data Transformation

### order_id Parsing

**Input Format**: `"PGP-{user_id}|{channel_id}"`
**Example**: `"PGP-6271402111|-1003268562225"`

**Parsing Logic** (`np-webhook-10-26/app.py:218-266`):

```python
def parse_order_id(order_id: str) -> tuple:
    # New format (with | separator - preserves negative sign)
    if '|' in order_id:
        prefix_and_user, channel_id_str = order_id.split('|')
        # "PGP-6271402111" → remove "PGP-" → "6271402111"
        user_id_str = prefix_and_user[4:]
        user_id = int(user_id_str)          # 6271402111
        channel_id = int(channel_id_str)    # -1003268562225
        return user_id, channel_id

    # Old format (backward compatibility - loses negative sign)
    else:
        parts = order_id.split('-')
        # ["PGP", "6271402111", "1003268562225"]
        user_id = int(parts[1])              # 6271402111
        channel_id = int(parts[2])           # 1003268562225
        # Re-add negative sign (all Telegram channels are negative)
        open_channel_id = -abs(channel_id)   # -1003268562225
        return user_id, open_channel_id
```

**Why This Matters**:
- Telegram channel IDs are **always negative** for private channels
- Old format: `PGP-6271402111-1003268562225` (loses `-` sign)
- New format: `PGP-6271402111|-1003268562225` (preserves `-` sign)

### Channel ID Mapping

**Database Lookup** (`np-webhook-10-26/app.py:327-350`):

```sql
-- Query main_clients_database
SELECT closed_channel_id
FROM main_clients_database
WHERE open_channel_id = '-1003268562225'

-- Result: -1002268562225 (different number!)
```

**Concept**:
- `open_channel_id`: Public/invite channel ID (user joins here first)
- `closed_channel_id`: Private/premium channel ID (user gets invited here after payment)
- Same channel owner, different channels

**Flow**:
```
User pays → order_id contains open_channel_id
         ↓
Database lookup → find closed_channel_id
         ↓
Send invite → to closed_channel_id (private premium channel)
```

### Subscription Data Lookup

**Database Query** (`np-webhook-10-26/app.py:652-663`):

```sql
SELECT
    c.client_wallet_address,           -- Where to send payout
    c.client_payout_currency::text,    -- USDT, BTC, etc.
    c.client_payout_network::text,     -- trc20, erc20, etc.
    u.sub_time,                         -- Subscription duration (days)
    u.sub_price                         -- Declared price (Decimal)
FROM private_channel_users_database u
JOIN main_clients_database c
    ON u.private_channel_id = c.closed_channel_id
WHERE u.user_id = 6271402111
  AND u.private_channel_id = -1002268562225
ORDER BY u.id DESC LIMIT 1
```

**Result Mapping**:
```python
wallet_address = "TXyz123ABC456def789GHI012jkl345MNO678pqr"
payout_currency = "USDT"
payout_network = "trc20"
subscription_time_days = 30
subscription_price = "35.00"  # Converted to string
```

---

## Validation Rules

### np-webhook Validation

**Required Fields from NOWPayments IPN**:
- ✅ `payment_id` - Must be non-empty string
- ✅ `order_id` - Must match format `PGP-{digits}|{negative_digits}`
- ✅ `payment_status` - Must be present (any status accepted)
- ✅ `pay_amount` - Must be numeric string
- ✅ `pay_currency` - Must be non-empty string
- ✅ `outcome_amount` - Must be numeric string
- ✅ `x-nowpayments-sig` header - Must match HMAC-SHA512 signature

**Optional Fields**:
- ⚠️ `invoice_id` - Can be empty/null
- ⚠️ `outcome_currency` - If missing, infer from `pay_currency`
- ⚠️ `price_amount` - Used for reference, not validated
- ⚠️ `price_currency` - Used for reference, not validated

**Database Validation**:
- ✅ `order_id` must parse successfully
- ✅ `open_channel_id` must exist in `main_clients_database`
- ✅ `user_id` + `closed_channel_id` must exist in `private_channel_users_database`

**CoinGecko Validation**:
- ✅ `outcome_currency` must be in supported crypto list OR stablecoin
- ✅ CoinGecko API must return valid price (timeout: 10 seconds)
- ⚠️ If CoinGecko fails, `outcome_amount_usd` will be NULL (warning, not error)

### GCWebhook1 Validation

**Required Fields from np-webhook**:
```python
# Line 274: Must all be non-null
if not all([user_id, closed_channel_id, outcome_amount_usd]):
    abort(400, "Missing required payment data")
```

**Type Validation** (after fix):
```python
# Integers must be convertible
user_id = int(user_id)                         # ValueError if not numeric
closed_channel_id = int(closed_channel_id)     # ValueError if not numeric
subscription_time_days = int(subscription_time_days)  # ValueError if not numeric

# Floats must be convertible
subscription_price = float(subscription_price)         # ValueError if not numeric
outcome_amount_usd = float(outcome_amount_usd)         # ValueError if not numeric
```

**Business Logic Validation**:
```python
# Database lookup must succeed
payout_mode, payout_threshold = db_manager.get_payout_strategy(closed_channel_id)
# Returns: ("instant", None) or ("threshold", 100.00)

if payout_mode == "threshold":
    subscription_id = db_manager.get_subscription_id(user_id, closed_channel_id)
    # Must return valid subscription_id or abort
```

---

## Summary Tables

### Data Type Mapping

| Field | NOWPayments IPN | np-webhook Storage | np-webhook → GCWebhook1 | GCWebhook1 Processing |
|-------|----------------|-------------------|------------------------|---------------------|
| `payment_id` | string | string | string | string |
| `user_id` | — | int | int/string ⚠️ | **MUST CONVERT TO INT** |
| `closed_channel_id` | — | bigint | int/string ⚠️ | **MUST CONVERT TO INT** |
| `wallet_address` | — | string | string | string |
| `payout_currency` | — | enum | string | string |
| `payout_network` | — | enum | string | string |
| `subscription_time_days` | — | int | int/string ⚠️ | **MUST CONVERT TO INT** |
| `subscription_price` | — | numeric(10,2) | string | **MUST CONVERT TO FLOAT** |
| `outcome_amount_usd` | — | numeric(10,2) | float/string ⚠️ | **MUST CONVERT TO FLOAT** |
| `nowpayments_payment_id` | string | string | string | string |
| `nowpayments_pay_address` | string | string | string | string |
| `nowpayments_outcome_amount` | string (decimal) | numeric(18,8) | float/string ⚠️ | **MUST CONVERT TO FLOAT** |

### Critical Fields Explained

| Field | Purpose | Where Calculated | Where Used | Impact if Wrong |
|-------|---------|-----------------|------------|-----------------|
| `outcome_amount_usd` | **Actual USD value received** | np-webhook (CoinGecko) | GCWebhook1 (splits), GCAccumulator | Wrong payout amounts, financial loss |
| `subscription_price` | **Declared price (reference)** | Database (`sub_price`) | Token encryption, validation | Invalid invites, user confusion |
| `user_id` | **User identifier** | Parsed from `order_id` | All services | Wrong user gets invite, data corruption |
| `closed_channel_id` | **Target channel for invite** | Database lookup | GCWebhook2 (invite) | Invite to wrong channel, access denied |
| `wallet_address` | **Where to send payout** | Database | GCSplit, GCHostPay | Lost funds if wrong address |
| `payment_id` | **Idempotency key** | NOWPayments | Duplicate detection | Duplicate processing, double payout |

---

## Common Failure Scenarios

### Scenario 1: Type Conversion Error (FIXED)

**Symptom**: `TypeError: unsupported operand type(s) for -: 'float' and 'str'`

**Cause**: `subscription_price` is string, `outcome_amount_usd` is float

**Location**: `GCWebhook1-10-26/tph1-10-26.py:469`

**Fix Status**: ✅ Fixed in revision 00021-2pp with `float(subscription_price)`

**Permanent Fix**: Add type normalization at lines 250-260

### Scenario 2: Invalid Signature (ACTIVE)

**Symptom**: `403 Forbidden` from np-webhook

**Cause**:
- Wrong IPN secret in Secret Manager
- Secret has invisible characters (newlines, spaces)
- NOWPayments signature calculation differs

**Impact**: Legitimate payments rejected, users pay but system doesn't know

**Debug**:
```bash
# Check secret value (hex dump)
gcloud secrets versions access latest --secret="NOWPAYMENTS_IPN_SECRET" | xxd

# Compare with NOWPayments dashboard
# Navigate to: NOWPayments Dashboard → Settings → IPN Settings
```

### Scenario 3: Missing Database Record

**Symptom**: `No closed_channel_id found for open_channel_id`

**Cause**: Channel not registered in `main_clients_database`

**Impact**: Payment received but cannot be processed

**Fix**: Register channel in database:
```sql
INSERT INTO main_clients_database (
    open_channel_id,
    closed_channel_id,
    client_wallet_address,
    client_payout_currency,
    client_payout_network
) VALUES (
    '-1003268562225',     -- Open channel ID
    '-1002268562225',     -- Closed channel ID
    'TXyz...pqr',         -- Wallet
    'USDT',               -- Currency
    'trc20'               -- Network
);
```

### Scenario 4: CoinGecko API Failure

**Symptom**: `outcome_amount_usd` is NULL in database

**Cause**:
- CoinGecko API timeout (>10 seconds)
- Unsupported cryptocurrency
- Rate limiting

**Impact**: Payment processed but no USD value calculated, splits cannot be determined

**Mitigation**:
- Retry mechanism (currently not implemented)
- Fallback to manual price entry
- Queue for later processing

---

## Appendix: Example Complete Flow

### User Payment: $35 Subscription (Pays with ETH)

**1. NOWPayments IPN Callback**:
```json
POST https://np-webhook-10-26.../
x-nowpayments-sig: abc123...def789

{
  "payment_id": "6271827386",
  "order_id": "PGP-6271402111|-1003268562225",
  "price_amount": "35.00",
  "price_currency": "USD",
  "pay_amount": "0.014286",
  "pay_currency": "ETH",
  "pay_address": "0x1234...5678",
  "payment_status": "finished",
  "outcome_amount": "0.012000",
  "outcome_currency": "ETH"
}
```

**2. np-webhook Processing**:
```
✅ Signature verified
✅ Database updated with payment_id
📊 CoinGecko: ETH/USD = $2,450.50
💰 Calculated: 0.012 ETH × $2,450.50 = $29.41 USD
✅ Database updated with outcome_amount_usd = 29.41
```

**3. Cloud Tasks Payload to GCWebhook1**:
```json
POST https://gcwebhook1-10-26.../process-validated-payment

{
  "user_id": 6271402111,
  "closed_channel_id": -1002268562225,
  "wallet_address": "TXyz123ABC456def789GHI012jkl345MNO678pqr",
  "payout_currency": "USDT",
  "payout_network": "trc20",
  "subscription_time_days": 30,
  "subscription_price": "35.00",
  "outcome_amount_usd": 29.41,
  "nowpayments_payment_id": "6271827386",
  "nowpayments_pay_address": "0x1234...5678",
  "nowpayments_outcome_amount": 0.012
}
```

**4. GCWebhook1 Processing**:
```
✅ Type conversion: all fields normalized
📊 Payout mode: instant
🚀 Routing to GCSplit1 with $29.41 USD (not $35!)
📱 Queuing Telegram invite to GCWebhook2
```

**Key Points**:
- User paid for $35 subscription
- Due to fees/slippage, only $29.41 received
- System uses **$29.41** for splits (ACTUAL value)
- System records **$35** for subscription (DECLARED value)
- Both values preserved for analytics

---

**Document End**

For questions or clarifications, review:
- `np-webhook-10-26/app.py` (IPN handler)
- `GCWebhook1-10-26/tph1-10-26.py` (payment orchestration)
- `CRITICAL_ISSUES_DEEP_DIVE_INVESTIGATION.md` (type safety analysis)
