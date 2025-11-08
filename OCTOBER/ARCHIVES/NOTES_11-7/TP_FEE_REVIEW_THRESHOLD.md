# TP Fee Review: Threshold Payout Method

**Date:** 2025-11-07
**Status:** VERIFIED - TP Fee deducted correctly at GCAccumulator
**Flow Type:** Threshold Payout (Batch Processing)

---

## Executive Summary

In the **threshold payout method**, the TP_FEE (default 3%) is deducted **ONCE** at the **GCAccumulator-10-26** service, immediately upon receiving each individual payment. All subsequent services (GCBatchProcessor, GCSplit1, GCSplit2, GCSplit3, GCHostPay) work with the **already fee-adjusted amounts** and do NOT deduct the fee again.

---

## Complete Threshold Payout Flow

```
NowPayments → np-webhook-10-26 → GCWebhook1 → GCAccumulator [TP_FEE DEDUCTED HERE]
                                                     ↓
                                              [Accumulated in DB]
                                                     ↓
                                          GCBatchProcessor (every 5 min)
                                                     ↓
                                                 GCSplit1
                                                     ↓
                                                 GCSplit2
                                                     ↓
                                                 GCSplit3
                                                     ↓
                                                GCHostPay1
```

---

## Detailed Fee Deduction Analysis

### 1. GCWebhook1-10-26: Payment Router (NO FEE DEDUCTION)

**Location:** `GCWebhook1-10-26/tph1-10-26.py` lines 331-371

**Role:** Routes payments to GCAccumulator for threshold payouts

**Code Analysis:**
```python
if payout_mode == "threshold":
    print(f"🎯 [VALIDATED] Threshold payout mode - ${payout_threshold} threshold")
    print(f"📊 [VALIDATED] Routing to GCAccumulator for accumulation")

    # Queue to GCAccumulator with ACTUAL outcome amount
    print(f"🚀 [VALIDATED] Queuing to GCAccumulator...")
    print(f"   💰 Using ACTUAL outcome: ${outcome_amount_usd} (not ${subscription_price})")

    task_name = cloudtasks_client.enqueue_gcaccumulator_payment(
        queue_name=gcaccumulator_queue,
        target_url=gcaccumulator_url,
        user_id=user_id,
        client_id=closed_channel_id,
        wallet_address=wallet_address,
        payout_currency=payout_currency,
        payout_network=payout_network,
        subscription_price=outcome_amount_usd,  # ✅ ACTUAL USD amount (GROSS)
        subscription_id=subscription_id,
        nowpayments_payment_id=nowpayments_payment_id,
        nowpayments_pay_address=nowpayments_pay_address,
        nowpayments_outcome_amount=nowpayments_outcome_amount
    )
```

**Fee Status:** ❌ NO FEE DEDUCTION
- Passes through the ACTUAL outcome_amount_usd from NowPayments
- This is the GROSS amount (before TP fee)
- Simply routes the payment to GCAccumulator

---

### 2. GCAccumulator-10-26: Fee Deduction Point ✅

**Location:** `GCAccumulator-10-26/acc10-26.py` lines 117-129

**Role:** **DEDUCTS TP_FEE AND ACCUMULATES NET AMOUNT**

**Code Analysis:**
```python
# Calculate adjusted amount (remove TP fee like GCSplit1 does)
tp_flat_fee = Decimal(config.get('tp_flat_fee', '3'))
fee_amount = payment_amount_usd * (tp_flat_fee / Decimal('100'))
adjusted_amount_usd = payment_amount_usd - fee_amount

print(f"💸 [ENDPOINT] TP fee ({tp_flat_fee}%): ${fee_amount}")
print(f"✅ [ENDPOINT] Adjusted amount: ${adjusted_amount_usd}")

# Store accumulated_eth (the adjusted USD amount pending conversion)
# Conversion will happen asynchronously via GCSplit2
accumulated_eth = adjusted_amount_usd
print(f"⏳ [ENDPOINT] Storing payment with accumulated_eth (pending conversion)")
print(f"💰 [ENDPOINT] Accumulated ETH value: ${accumulated_eth}")
```

**Fee Calculation Example:**
- **Input (GROSS):** `payment_amount_usd = $100.00`
- **TP Fee Rate:** `tp_flat_fee = 3%`
- **Fee Amount:** `$100.00 * 0.03 = $3.00`
- **Output (NET):** `adjusted_amount_usd = $100.00 - $3.00 = $97.00`

**Database Storage:**
```python
accumulation_id = db_manager.insert_payout_accumulation_pending(
    client_id=client_id,
    user_id=user_id,
    subscription_id=subscription_id,
    payment_amount_usd=payment_amount_usd,      # GROSS: $100.00
    payment_currency='usd',
    payment_timestamp=payment_timestamp,
    accumulated_eth=accumulated_eth,            # NET: $97.00 ✅
    client_wallet_address=wallet_address,
    client_payout_currency=payout_currency,
    client_payout_network=payout_network,
    nowpayments_payment_id=nowpayments_payment_id,
    nowpayments_pay_address=nowpayments_pay_address,
    nowpayments_outcome_amount=nowpayments_outcome_amount
)
```

**Key Points:**
- ✅ **TP_FEE DEDUCTED HERE** - Single point of fee deduction
- `payment_amount_usd` = GROSS (stored for record-keeping)
- `accumulated_eth` = NET after fee (stored for batch processing)
- Field name `accumulated_eth` is legacy but now stores USD (pending conversion)

**Fee Status:** ✅ **FEE DEDUCTED** (3% default)

---

### 3. payout_accumulation Table: Stores Net Amounts

**Table Structure:**
```sql
CREATE TABLE payout_accumulation (
    id SERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    subscription_id INTEGER,
    payment_amount_usd NUMERIC(20, 8),    -- GROSS amount
    payment_currency VARCHAR(10),
    payment_timestamp TIMESTAMP,
    accumulated_eth NUMERIC(20, 8),       -- NET amount (after TP fee) ✅
    client_wallet_address TEXT,
    client_payout_currency VARCHAR(20),
    client_payout_network VARCHAR(20),
    accumulated_usdt NUMERIC(20, 8),      -- Converted USDT (after fee)
    conversion_completed BOOLEAN,
    paid_out BOOLEAN,
    batch_id UUID,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Critical Field:**
- `accumulated_eth` = NET amount (after TP fee deduction)
- This is what gets summed for batch threshold checks
- All downstream processing uses this NET value

---

### 4. GCBatchProcessor-10-26: Uses Net Amounts (NO ADDITIONAL FEE)

**Location:** `GCBatchProcessor-10-26/batch10-26.py` lines 85-116

**Role:** Aggregates NET amounts and triggers batch payouts

**Code Analysis:**
```python
# Find clients over threshold
print(f"🔍 [ENDPOINT] Searching for clients over threshold")
clients_over_threshold = db_manager.find_clients_over_threshold()

# Process each client
for client_data in clients_over_threshold:
    client_id = client_data['client_id']
    total_usdt = client_data['total_usdt']      # ✅ SUM of accumulated_eth (NET)
    payment_count = client_data['payment_count']
    wallet_address = client_data['wallet_address']
    payout_currency = client_data['payout_currency']
    payout_network = client_data['payout_network']
    threshold = client_data['threshold']

    print(f"💰 [ENDPOINT] Processing client: {client_id}")
    print(f"📊 [ENDPOINT] Total USDT: ${total_usdt} (threshold: ${threshold})")
```

**Database Query (in DatabaseManager):**
```python
def find_clients_over_threshold(self):
    """
    Find clients whose total accumulated USDT >= payout threshold.
    Returns list of clients ready for batch payout.

    Query sums accumulated_eth (which is NET after TP fee).
    """
    query = """
        SELECT
            pa.client_id,
            SUM(pa.accumulated_eth) as total_usdt,   -- ✅ NET amounts summed
            COUNT(*) as payment_count,
            MAX(pa.client_wallet_address) as wallet_address,
            MAX(pa.client_payout_currency) as payout_currency,
            MAX(pa.client_payout_network) as payout_network,
            cp.threshold_payout as threshold
        FROM payout_accumulation pa
        JOIN closed_private_channels cp ON pa.client_id = cp.channel_id
        WHERE pa.paid_out = FALSE
          AND pa.conversion_completed = TRUE
        GROUP BY pa.client_id, cp.threshold_payout
        HAVING SUM(pa.accumulated_eth) >= cp.threshold_payout
    """
```

**Fee Status:** ❌ NO ADDITIONAL FEE DEDUCTION
- Works with `accumulated_eth` which is already NET (post-fee)
- Sums up multiple NET payments
- Passes NET total to GCSplit1

---

### 5. GCSplit1-10-26: Batch Payout Endpoint (NO ADDITIONAL FEE)

**Location:** `GCSplit1-10-26/tps1-10-26.py` lines 844-977 (ENDPOINT 4: `/batch-payout`)

**Role:** Orchestrates batch payout with NET amount

**Code Analysis:**
```python
@app.route("/batch-payout", methods=["POST"])
def batch_payout():
    # Decrypt batch token
    decrypted_data = token_manager.decrypt_batch_token(encrypted_token)

    batch_id = decrypted_data.get('batch_id')
    client_id = decrypted_data.get('client_id')
    wallet_address = decrypted_data.get('wallet_address')
    payout_currency = decrypted_data.get('payout_currency')
    payout_network = decrypted_data.get('payout_network')
    amount_usdt = decrypted_data.get('amount_usdt')  # ✅ NET amount from batch

    print(f"🆔 [ENDPOINT_4] Batch ID: {batch_id}")
    print(f"🏢 [ENDPOINT_4] Client ID: {client_id}")
    print(f"💰 [ENDPOINT_4] Total Amount: ${amount_usdt} USDT")  # ✅ Already NET

    # Encrypt token for GCSplit2 (USDT estimate request)
    encrypted_token_for_split2 = token_manager.encrypt_gcsplit1_to_gcsplit2_token(
        user_id=batch_user_id,
        closed_channel_id=str(client_id),
        wallet_address=wallet_address,
        payout_currency=payout_currency,
        payout_network=payout_network,
        adjusted_amount=amount_usdt,       # ✅ NET amount (already fee-adjusted)
        swap_currency='usdt',              # Threshold always uses USDT
        payout_mode='threshold',           # Mark as threshold payout
        actual_eth_amount=0.0              # No ETH in threshold flow
    )
```

**Fee Status:** ❌ NO ADDITIONAL FEE DEDUCTION
- Receives NET amount from GCBatchProcessor
- Passes NET amount to GCSplit2
- Parameter name `adjusted_amount` reflects it's already adjusted for TP fee

---

### 6. Downstream Services (NO ADDITIONAL FEE)

**GCSplit2-10-26:** Performs USDT→ClientCurrency swap estimate
- Uses NET amount for ChangeNow API estimate
- No fee deduction

**GCSplit3-10-26:** Creates USDT→ClientCurrency swap
- Uses NET amount for actual swap creation
- No fee deduction

**GCHostPay1-10-26:** Handles ETH payment to ChangeNow
- Uses NET-derived ETH amount for payment
- No fee deduction

---

## Fee Deduction Summary

| Service | Fee Deduction? | Amount Type | Notes |
|---------|---------------|-------------|-------|
| **GCWebhook1** | ❌ No | GROSS | Routes payment to GCAccumulator |
| **GCAccumulator** | ✅ **YES (3%)** | **GROSS → NET** | **SINGLE POINT OF FEE DEDUCTION** |
| **payout_accumulation DB** | N/A | NET stored | Stores NET in `accumulated_eth` |
| **GCBatchProcessor** | ❌ No | NET | Sums NET amounts |
| **GCSplit1 (batch)** | ❌ No | NET | Passes NET to swap services |
| **GCSplit2** | ❌ No | NET | Swap estimate on NET |
| **GCSplit3** | ❌ No | NET | Swap execution on NET |
| **GCHostPay1** | ❌ No | NET | Payment with NET-derived ETH |

---

## Verification Examples

### Example 1: Single Payment

**Scenario:** User pays $100 for channel subscription (threshold payout)

1. **GCWebhook1 routes to GCAccumulator:** `$100.00` (GROSS)
2. **GCAccumulator deducts TP fee:**
   - TP Fee (3%): `$100.00 * 0.03 = $3.00`
   - NET: `$100.00 - $3.00 = $97.00`
   - Stores in DB: `accumulated_eth = $97.00`
3. **Result:** `$97.00` accumulated for client (NET)

### Example 2: Batch Threshold Reached

**Scenario:** Client has threshold of $50, receives 3 payments

**Payments:**
1. Payment 1: `$30.00` GROSS → `$29.10` NET (after 3% fee)
2. Payment 2: `$20.00` GROSS → `$19.40` NET (after 3% fee)
3. Payment 3: `$15.00` GROSS → `$14.55` NET (after 3% fee)

**Accumulation:**
- Total GROSS: `$65.00`
- Total NET: `$29.10 + $19.40 + $14.55 = $63.05`
- Threshold: `$50.00`
- Status: ✅ Over threshold (`$63.05 >= $50.00`)

**GCBatchProcessor triggers batch:**
- Batch amount: `$63.05` (NET)
- No additional fee deduction
- Entire `$63.05` goes to swap for client payout

**Fee Distribution:**
- TelePay keeps: `$1.95` (3% of $65.00 GROSS)
- Client gets: `$63.05` worth of payout currency

---

## Critical Design Points

### 1. Single Point of Fee Deduction ✅
- **Pro:** Simplifies accounting, prevents double-deduction errors
- **Pro:** Clear audit trail (one place to verify fee calculation)
- **Implementation:** GCAccumulator-10-26 lines 117-123

### 2. Database Stores Both GROSS and NET ✅
- `payment_amount_usd` = GROSS (for reporting/auditing)
- `accumulated_eth` = NET (for batch processing)
- Enables reconciliation and fee verification

### 3. Field Naming Legacy ⚠️
- Field `accumulated_eth` actually stores USD (NET)
- Name is historical from when system only handled ETH
- Functionally correct but semantically misleading

### 4. Threshold Check Uses NET ✅
- Batch processor sums `accumulated_eth` (NET amounts)
- Threshold comparison uses NET totals
- Ensures clients must accumulate NET amount to trigger payout

---

## Comparison with Instant Payout Method

| Aspect | Threshold Payout | Instant Payout |
|--------|-----------------|----------------|
| **Fee Deduction Point** | GCAccumulator | GCSplit1 |
| **Fee Deduction Timing** | Per-payment accumulation | During immediate payout |
| **Stored Amount** | NET (accumulated_eth) | N/A (not stored) |
| **Batch Processing** | Yes (GCBatchProcessor) | No (immediate) |
| **Threshold Check** | NET totals | N/A |

---

## Code Locations Reference

1. **GCWebhook1** (routing): `GCWebhook1-10-26/tph1-10-26.py:331-371`
2. **GCAccumulator** (fee deduction): `GCAccumulator-10-26/acc10-26.py:117-129` ✅
3. **Database insertion**: `GCAccumulator-10-26/database_manager.py`
4. **GCBatchProcessor** (aggregation): `GCBatchProcessor-10-26/batch10-26.py:85-200`
5. **GCSplit1 batch endpoint**: `GCSplit1-10-26/tps1-10-26.py:844-977`

---

## Conclusion

The threshold payout method correctly deducts the TP_FEE **ONCE** at the **GCAccumulator** service immediately upon receiving each payment. All subsequent services work with NET (fee-adjusted) amounts, ensuring:

1. ✅ No double-deduction of fees
2. ✅ Accurate threshold calculations on NET amounts
3. ✅ Clear fee accounting and audit trail
4. ✅ Proper client payout amounts

**Verified:** 2025-11-07
**Status:** ✅ CORRECT IMPLEMENTATION
