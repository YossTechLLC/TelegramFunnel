# accumulated_amount_usdt Calculation Flow Documentation

**Last Updated:** 2025-10-29
**Purpose:** Document the complete logic flow for how `accumulated_amount_usdt` is calculated and stored in the `payout_accumulation` table

---

## Overview

The `accumulated_amount_usdt` field in the `payout_accumulation` table stores the locked USDT value of user payments to eliminate cryptocurrency volatility risk. This document traces the complete calculation flow from initial payment receipt to database storage.

---

## Complete Flow Diagram

```
Payment Gateway (Stripe/NowPayments)
         ↓
    GCWebhook1 (Payment Processor)
         ↓
    Cloud Tasks (accumulator-payment-queue)
         ↓
    GCAccumulator (Payment Accumulation Service)
         ↓ [CALCULATION HAPPENS HERE]
    payout_accumulation table
```

---

## Step-by-Step Calculation Flow

### 1. Payment Gateway → GCWebhook1

**Service:** `GCWebhook1-10-26/tph1-10-26.py`

**Input Variables:**
- `subscription_price` (string) - Original payment amount in USD from payment gateway
- Example: `"10.00"` for a $10 subscription

**Relevant Code:** Lines 95-105 in `tph1-10-26.py`
```python
# Extract from webhook payload
subscription_price = data.get('sub_price')  # Example: "10.00"
```

---

### 2. GCWebhook1 → Cloud Tasks Payload

**Service:** `GCWebhook1-10-26/cloudtasks_client.py`

**Function:** `enqueue_gcaccumulator_payment()`

**Input Parameters:**
- `subscription_price` (string) - Passed from GCWebhook1
- `user_id` (int) - Telegram user ID
- `client_id` (int) - Channel ID (closed_channel_id)
- `wallet_address` (string) - Client's payout wallet
- `payout_currency` (string) - Target currency (e.g., "xmr")
- `payout_network` (string) - Target network
- `subscription_id` (int) - FK to private_channel_users_database

**Relevant Code:** Lines 216-270 in `cloudtasks_client.py`
```python
def enqueue_gcaccumulator_payment(
    self,
    queue_name: str,
    target_url: str,
    user_id: int,
    client_id: int,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    subscription_price: str,  # <-- Original payment amount
    subscription_id: int
) -> Optional[str]:
    # Prepare payload
    payload = {
        "user_id": user_id,
        "client_id": client_id,
        "wallet_address": wallet_address,
        "payout_currency": payout_currency,
        "payout_network": payout_network,
        "payment_amount_usd": subscription_price,  # <-- Renamed to payment_amount_usd
        "subscription_id": subscription_id,
        "payment_timestamp": datetime.datetime.now().isoformat()
    }
```

**Key Transformation:**
- `subscription_price` → `payment_amount_usd` (field name change for clarity)
- No calculation at this stage, just data forwarding

---

### 3. GCAccumulator Endpoint Receives Payload

**Service:** `GCAccumulator-10-26/acc10-26.py`

**Endpoint:** `POST /` (main accumulation endpoint)

**Input Variables from Cloud Tasks Payload:**
- `payment_amount_usd` (string) - Original payment amount
- `user_id` (int)
- `client_id` (int)
- `wallet_address` (string)
- `payout_currency` (string)
- `payout_network` (string)
- `subscription_id` (int)
- `payment_timestamp` (string ISO format)

**Relevant Code:** Lines 88-101 in `acc10-26.py`
```python
# Extract payment data from Cloud Tasks payload
user_id = request_data.get('user_id')
client_id = request_data.get('client_id')
wallet_address = request_data.get('wallet_address')
payout_currency = request_data.get('payout_currency')
payout_network = request_data.get('payout_network')
payment_amount_usd = Decimal(str(request_data.get('payment_amount_usd')))  # <-- Converted to Decimal
subscription_id = request_data.get('subscription_id')
payment_timestamp = request_data.get('payment_timestamp')
```

**Key Transformation:**
- String converted to `Decimal` for precise financial calculations
- Example: `"10.00"` → `Decimal('10.00')`

---

### 4. TP Fee Calculation (TelePay Platform Fee)

**Service:** `GCAccumulator-10-26/acc10-26.py`

**Function:** Lines 103-109 in `acc10-26.py`

**Input Variables:**
- `payment_amount_usd` (Decimal) - Original payment amount from step 3
- `tp_flat_fee` (Decimal) - TelePay platform fee percentage from config (default: 3%)

**Calculation Logic:**
```python
# Calculate adjusted amount (remove TP fee like GCSplit1 does)
tp_flat_fee = Decimal(config.get('tp_flat_fee', '3'))  # Default 3%
fee_amount = payment_amount_usd * (tp_flat_fee / Decimal('100'))
adjusted_amount_usd = payment_amount_usd - fee_amount
```

**Example Calculation:**
```
payment_amount_usd = $10.00
tp_flat_fee = 3%

fee_amount = $10.00 * (3 / 100)
           = $10.00 * 0.03
           = $0.30

adjusted_amount_usd = $10.00 - $0.30
                    = $9.70
```

**Result:**
- `fee_amount` = $0.30 (removed from payment)
- `adjusted_amount_usd` = $9.70 (amount after platform fee)

---

### 5. USDT Conversion (Volatility Lock)

**Service:** `GCAccumulator-10-26/acc10-26.py`

**Function:** Lines 111-121 in `acc10-26.py`

**Input Variables:**
- `adjusted_amount_usd` (Decimal) - Post-fee amount from step 4

**Current Implementation (MOCK):**
```python
# For now, we'll use a 1:1 ETH→USDT mock conversion
# In production, this would call GCSplit2 for actual ChangeNow estimate
# CRITICAL: This locks the USD value in USDT to eliminate volatility
accumulated_usdt = adjusted_amount_usd
eth_to_usdt_rate = Decimal('1.0')  # Mock rate for now
conversion_tx_hash = f"mock_cn_tx_{int(time.time())}"
```

**Future Production Implementation:**
This section is designed to call GCSplit2 for real-time ChangeNow ETH→USDT conversion rate:
```python
# FUTURE PRODUCTION CODE (not yet implemented):
# 1. Call GCSplit2 with adjusted_amount_usd
# 2. GCSplit2 queries ChangeNow API for ETH→USDT rate
# 3. Calculate: accumulated_usdt = adjusted_amount_usd * eth_to_usdt_rate
# 4. Get actual conversion_tx_hash from ChangeNow
# 5. This locks the USD value in USDT to protect against crypto volatility
```

**Example Calculation (Current):**
```
adjusted_amount_usd = $9.70
eth_to_usdt_rate = 1.0 (mock)

accumulated_usdt = $9.70 * 1.0
                 = 9.70 USDT
```

**Result:**
- `accumulated_usdt` = 9.70 USDT
- `eth_to_usdt_rate` = 1.0 (mock)
- `conversion_tx_hash` = "mock_cn_tx_1730216400" (timestamp-based)

---

### 6. Database Insertion

**Service:** `GCAccumulator-10-26/database_manager.py`

**Function:** `insert_payout_accumulation()`

**Input Parameters:**
```python
def insert_payout_accumulation(
    self,
    client_id: str,                      # From payload
    user_id: int,                        # From payload
    subscription_id: int,                # From payload
    payment_amount_usd: Decimal,         # Original payment ($10.00)
    payment_currency: str,               # 'usd'
    payment_timestamp: str,              # ISO timestamp from payload
    accumulated_amount_usdt: Decimal,    # CALCULATED VALUE ($9.70 USDT)
    eth_to_usdt_rate: Decimal,          # Mock rate (1.0)
    conversion_timestamp: str,           # Current timestamp
    conversion_tx_hash: str,            # Mock TX hash
    client_wallet_address: str,         # From payload
    client_payout_currency: str,        # From payload (e.g., 'xmr')
    client_payout_network: str          # From payload
) -> Optional[int]:
```

**SQL Insert Statement:** Lines 109-125 in `database_manager.py`
```sql
INSERT INTO payout_accumulation (
    client_id, user_id, subscription_id,
    payment_amount_usd, payment_currency, payment_timestamp,
    accumulated_amount_usdt,  -- <-- CALCULATED VALUE INSERTED HERE
    eth_to_usdt_rate,
    conversion_timestamp, conversion_tx_hash,
    client_wallet_address, client_payout_currency, client_payout_network
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id
```

**Example Database Record:**
```
id: 1
client_id: -1003296084379
user_id: 123456789
subscription_id: 42
payment_amount_usd: 10.00
payment_currency: usd
payment_timestamp: 2025-10-29T10:30:00
accumulated_amount_usdt: 9.70  <-- FINAL CALCULATED VALUE
eth_to_usdt_rate: 1.0
conversion_timestamp: 2025-10-29T10:31:00
conversion_tx_hash: mock_cn_tx_1730216400
client_wallet_address: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
client_payout_currency: xmr
client_payout_network: mainnet
is_paid_out: FALSE
created_at: 2025-10-29T10:31:00
```

---

## Summary of Calculation

### Formula

```
accumulated_amount_usdt = (payment_amount_usd - fee_amount) * eth_to_usdt_rate

Where:
  fee_amount = payment_amount_usd * (tp_flat_fee / 100)
  eth_to_usdt_rate = 1.0 (currently mock, will be real rate in production)
```

### Simplified Current Formula (Mock Rate)

```
accumulated_amount_usdt = payment_amount_usd * (1 - (tp_flat_fee / 100))
```

### Example with Real Numbers

```
Input:  payment_amount_usd = $10.00
        tp_flat_fee = 3%

Step 1: fee_amount = $10.00 * 0.03 = $0.30
Step 2: adjusted_amount_usd = $10.00 - $0.30 = $9.70
Step 3: accumulated_usdt = $9.70 * 1.0 = 9.70 USDT

Output: accumulated_amount_usdt = 9.70 USDT
```

---

## Configuration Variables

### Source: `GCAccumulator-10-26/config_manager.py`

**TP_FLAT_FEE**
- **Type:** Decimal (percentage)
- **Default:** 3% (if not set in Secret Manager)
- **Source:** Secret Manager secret `TP_FLAT_FEE`
- **Purpose:** TelePay platform fee percentage deducted from all payments
- **Used in:** `acc10-26.py` line 104

**Example Configuration Values:**
```python
{
    "tp_flat_fee": "3",  # 3% platform fee
    "instance_connection_name": "telepay-459221:us-central1:telepaypsql",
    "db_name": "client_table",
    "db_user": "postgres",
    "db_password": "[SECRET]"
}
```

---

## Code Locations Reference

### Files Involved in Calculation

1. **GCWebhook1-10-26/tph1-10-26.py**
   - Line 95-105: Extract `subscription_price` from webhook
   - Line 189-210: Call `enqueue_gcaccumulator_payment()`

2. **GCWebhook1-10-26/cloudtasks_client.py**
   - Line 216-270: `enqueue_gcaccumulator_payment()` function
   - Line 257: Rename `subscription_price` → `payment_amount_usd`

3. **GCAccumulator-10-26/acc10-26.py**
   - Line 88-101: Extract payload variables
   - Line 94: Convert `payment_amount_usd` to Decimal
   - Line 103-109: **TP fee calculation** (where `adjusted_amount_usd` is calculated)
   - Line 111-121: **USDT conversion** (where `accumulated_usdt` is set)
   - Line 130-144: Call `db_manager.insert_payout_accumulation()`

4. **GCAccumulator-10-26/database_manager.py**
   - Line 59-141: `insert_payout_accumulation()` function
   - Line 67: Parameter definition for `accumulated_amount_usdt`
   - Line 109-125: SQL INSERT statement

---

## Data Type Evolution

```
Payment Gateway (Stripe/NowPayments)
    ↓ string: "10.00"
GCWebhook1
    ↓ string: "10.00" (as subscription_price)
Cloud Tasks Payload
    ↓ string: "10.00" (as payment_amount_usd)
GCAccumulator Extract
    ↓ Decimal('10.00') (converted for precision)
TP Fee Calculation
    ↓ Decimal('9.70') (as adjusted_amount_usd)
USDT Conversion
    ↓ Decimal('9.70') (as accumulated_usdt)
Database Storage
    ↓ NUMERIC(20,8): 9.70000000
```

---

## Important Notes

### Current vs Future Implementation

**Current (Mock):**
- `eth_to_usdt_rate = 1.0` (hardcoded)
- No actual ChangeNow API call
- Direct 1:1 conversion USD → USDT
- Mock transaction hash generated

**Future (Production):**
- Real-time ChangeNow API query via GCSplit2
- Actual ETH→USDT market rate
- Real ChangeNow transaction hash
- True volatility protection by locking USDT value immediately

### Why This Design?

**Volatility Elimination:**
- By converting to USDT immediately and locking the value, the system protects against cryptocurrency price fluctuations
- Example: User pays $10, we lock $9.70 USDT. Even if crypto markets crash, the client is guaranteed $9.70 worth of value

**Transparency:**
- `payment_amount_usd` stores what user originally paid
- `accumulated_amount_usdt` stores what client will receive (after platform fee)
- Audit trail preserved for both user and client

**Threshold Payout:**
- Multiple `accumulated_amount_usdt` values sum up per client
- When `SUM(accumulated_amount_usdt)` >= `payout_threshold_usd`, batch payout triggers
- Each payment's USDT value is locked at conversion time, preventing volatility issues

---

## Testing Example

**Scenario:** User pays $10.00 for subscription

**Expected Flow:**
```
1. GCWebhook1 receives: subscription_price = "10.00"
2. Cloud Tasks payload: payment_amount_usd = "10.00"
3. GCAccumulator receives: payment_amount_usd = Decimal('10.00')
4. TP fee calculation:
   - tp_flat_fee = 3%
   - fee_amount = $0.30
   - adjusted_amount_usd = $9.70
5. USDT conversion:
   - eth_to_usdt_rate = 1.0 (mock)
   - accumulated_usdt = 9.70 USDT
6. Database stores: accumulated_amount_usdt = 9.70
```

**Database Query to Verify:**
```sql
SELECT
    payment_amount_usd,
    accumulated_amount_usdt,
    (payment_amount_usd - accumulated_amount_usdt) as fee_deducted
FROM payout_accumulation
WHERE user_id = 123456789;

Expected Result:
payment_amount_usd | accumulated_amount_usdt | fee_deducted
10.00              | 9.70                    | 0.30
```

---

## Related Documents

- `THRESHOLD_PAYOUT_ARCHITECTURE.md` - Overall threshold payout system design
- `DB_MIGRATION_THRESHOLD_PAYOUT.md` - Database schema for payout_accumulation table
- `MAIN_ARCHITECTURE_WORKFLOW.md` - Complete system workflow

---

## Version History

- **2025-10-29**: Initial documentation created
- **Current Status**: Mock implementation (1:1 USD→USDT conversion)
- **Planned**: Real ChangeNow API integration for ETH→USDT conversion
