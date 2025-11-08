# accumulated_amount_usdt Calculation Incongruency Analysis

**Date:** 2025-10-30
**Issue:** Discrepancy between documented TP fee (3%) and actual TP fee (15%) applied in production
**Status:** ROOT CAUSE IDENTIFIED

---

## Executive Summary

The `accumulated_amount_usdt` calculation in the `payout_accumulation` table is working **correctly according to the code logic**, but is applying a **15% fee instead of the documented 3% fee** due to an **incorrect Secret Manager configuration**.

### Expected Behavior (Per Documentation)
- **payment_amount_usd**: $1.35
- **TP fee (3%)**: $0.0405
- **accumulated_amount_usdt**: $1.3095 (1.35 - 0.0405)

### Actual Behavior (Current Production)
- **payment_amount_usd**: $1.35
- **TP fee (15%)**: $0.2025
- **accumulated_amount_usdt**: $1.1475 (1.35 - 0.2025)

**Difference**: $0.162 per payment ($1.3095 - $1.1475)

---

## Root Cause Analysis

### 1. Secret Manager Configuration Error

**Finding:**
```bash
$ gcloud secrets versions access latest --secret=TP_FLAT_FEE
15
```

**Expected Value:** `3` (3% TelePay platform fee)
**Actual Value:** `15` (15% fee - likely a typo or testing value)

**Impact:**
- All payments processed through GCAccumulator are having **15% deducted** instead of **3%**
- This represents a **12% over-deduction** on every payment
- Channel owners are receiving significantly less than intended

---

## Data Evidence

### Database Query Results

**Query:**
```sql
SELECT
    id,
    payment_amount_usd,
    accumulated_amount_usdt,
    (payment_amount_usd - accumulated_amount_usdt) as fee_deducted,
    ((payment_amount_usd - accumulated_amount_usdt) / payment_amount_usd * 100) as fee_percentage
FROM payout_accumulation
ORDER BY id;
```

**Results:**
```
ID  | payment_amount_usd | accumulated_amount_usdt | fee_deducted | fee_percentage
----|-------------------|------------------------|--------------|---------------
1   | 1.35              | 1.14750000             | 0.20250000   | 15.00%
2   | 1.35              | 1.14750000             | 0.20250000   | 15.00%
3   | 1.35              | 1.14750000             | 0.20250000   | 15.00%
```

**Analysis:**
- **Consistency**: All records show exactly **15.00%** fee deduction
- **Calculation**: $1.35 × 15% = $0.2025 (matches database)
- **Result**: $1.35 - $0.2025 = $1.1475 (matches `accumulated_amount_usdt`)

---

## Code Flow Analysis

### Step-by-Step Trace

#### 1. Payment Gateway → GCWebhook1
**File:** `GCWebhook1-10-26/tph1-10-26.py`

```python
# Line 135: Token decoded with subscription_price
user_id, closed_channel_id, wallet_address, payout_currency,
payout_network, subscription_time_days, subscription_price =
    token_manager.decode_and_verify_token(token)

# subscription_price = "1.35" (original payment amount)
```

**No fee calculation at this stage** - GCWebhook1 simply forwards the original payment amount.

---

#### 2. GCWebhook1 → GCAccumulator (Cloud Tasks Payload)
**File:** `GCWebhook1-10-26/tph1-10-26.py` (lines 196-206)

```python
task_name_accumulator = cloudtasks_client.enqueue_gcaccumulator_payment(
    queue_name=gcaccumulator_queue,
    target_url=gcaccumulator_url,
    user_id=user_id,
    client_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_price=subscription_price,  # <-- ORIGINAL AMOUNT: "1.35"
    subscription_id=subscription_id
)
```

**File:** `GCWebhook1-10-26/cloudtasks_client.py` (line 257)

```python
payload = {
    "user_id": user_id,
    "client_id": client_id,
    "wallet_address": wallet_address,
    "payout_currency": payout_currency,
    "payout_network": payout_network,
    "payment_amount_usd": subscription_price,  # <-- Field renamed, still "1.35"
    "subscription_id": subscription_id,
    "payment_timestamp": datetime.datetime.now().isoformat()
}
```

**Key Point:** The **original payment amount** is forwarded unchanged to GCAccumulator.

---

#### 3. GCAccumulator Receives Payload
**File:** `GCAccumulator-10-26/acc10-26.py` (line 94)

```python
payment_amount_usd = Decimal(str(request_data.get('payment_amount_usd')))
# payment_amount_usd = Decimal('1.35')
```

---

#### 4. TP Fee Calculation (WHERE THE ISSUE OCCURS)
**File:** `GCAccumulator-10-26/acc10-26.py` (lines 103-109)

```python
# Calculate adjusted amount (remove TP fee)
tp_flat_fee = Decimal(config.get('tp_flat_fee', '3'))  # <-- PULLS FROM SECRET MANAGER
fee_amount = payment_amount_usd * (tp_flat_fee / Decimal('100'))
adjusted_amount_usd = payment_amount_usd - fee_amount

print(f"💸 [ENDPOINT] TP fee ({tp_flat_fee}%): ${fee_amount}")
print(f"✅ [ENDPOINT] Adjusted amount: ${adjusted_amount_usd}")
```

**Actual Execution with Current Secret:**
```python
tp_flat_fee = Decimal('15')  # <-- FROM SECRET MANAGER (WRONG VALUE!)
fee_amount = Decimal('1.35') * (Decimal('15') / Decimal('100'))
           = Decimal('1.35') * Decimal('0.15')
           = Decimal('0.2025')

adjusted_amount_usd = Decimal('1.35') - Decimal('0.2025')
                    = Decimal('1.1475')
```

**Expected Execution with Correct Secret:**
```python
tp_flat_fee = Decimal('3')  # <-- SHOULD BE THIS
fee_amount = Decimal('1.35') * (Decimal('3') / Decimal('100'))
           = Decimal('1.35') * Decimal('0.03')
           = Decimal('0.0405')

adjusted_amount_usd = Decimal('1.35') - Decimal('0.0405')
                    = Decimal('1.3095')
```

---

#### 5. USDT Conversion (1:1 Mock)
**File:** `GCAccumulator-10-26/acc10-26.py` (lines 111-121)

```python
# For now, we'll use a 1:1 ETH→USDT mock conversion
accumulated_usdt = adjusted_amount_usd  # <-- Uses WRONG adjusted amount
eth_to_usdt_rate = Decimal('1.0')  # Mock rate for now
```

**Actual:**
```python
accumulated_usdt = Decimal('1.1475')  # <-- WRONG (15% fee applied)
```

**Expected:**
```python
accumulated_usdt = Decimal('1.3095')  # <-- CORRECT (3% fee applied)
```

---

#### 6. Database Insertion
**File:** `GCAccumulator-10-26/database_manager.py` (lines 109-125)

```sql
INSERT INTO payout_accumulation (
    client_id, user_id, subscription_id,
    payment_amount_usd, payment_currency, payment_timestamp,
    accumulated_amount_usdt,  -- <-- WRONG VALUE INSERTED HERE
    eth_to_usdt_rate,
    conversion_timestamp, conversion_tx_hash,
    client_wallet_address, client_payout_currency, client_payout_network
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
```

**Actual Values Inserted:**
- `payment_amount_usd`: 1.35 ✓ (CORRECT)
- `accumulated_amount_usdt`: 1.14750000 ✗ (WRONG - should be 1.3095)

---

## Comparison: Documentation vs Reality

### ACCUMULATED_AMOUNT_USDT_FUNCTIONS.md (Documentation)

**Example from documentation:**
```
payment_amount_usd = $10.00
tp_flat_fee = 3%

fee_amount = $10.00 * 0.03 = $0.30
adjusted_amount_usd = $10.00 - $0.30 = $9.70
accumulated_usdt = $9.70 * 1.0 = 9.70 USDT

Output: accumulated_amount_usdt = 9.70 USDT (3% fee)
```

### Actual Production Behavior

**With current Secret Manager value (TP_FLAT_FEE = 15):**
```
payment_amount_usd = $10.00
tp_flat_fee = 15%  <-- WRONG VALUE

fee_amount = $10.00 * 0.15 = $1.50
adjusted_amount_usd = $10.00 - $1.50 = $8.50
accumulated_usdt = $8.50 * 1.0 = 8.50 USDT

Output: accumulated_amount_usdt = 8.50 USDT (15% fee)
```

**Difference:** $9.70 - $8.50 = **$1.20 per $10 payment**

---

## Impact Assessment

### Financial Impact

**Per Payment:**
- **Payment Amount**: $1.35
- **Expected Fee (3%)**: $0.0405
- **Actual Fee (15%)**: $0.2025
- **Over-Deduction**: $0.162 (12% extra)

**For 3 Payments (Current Database):**
- **Total Payment Amount**: $4.05 (3 × $1.35)
- **Expected Accumulated**: $3.9285 (3 × $1.3095)
- **Actual Accumulated**: $3.4425 (3 × $1.1475)
- **Total Over-Deduction**: $0.486

**Percentage of Revenue Lost to Clients:**
- Clients should receive: **97% of payment** (100% - 3%)
- Clients actually receive: **85% of payment** (100% - 15%)
- **Loss**: 12% of all payment revenue

---

### Affected Services

**Direct Impact:**
1. **GCAccumulator-10-26** - Applies wrong fee percentage
2. **payout_accumulation** table - Contains under-accumulated values
3. **GCBatchProcessor-10-26** - Will trigger payouts based on wrong totals

**Indirect Impact:**
- Channel owners reach payout threshold slower than intended
- Payouts will be smaller than expected
- Trust/reputation risk if clients discover discrepancy

---

## Why the Documentation Was Correct

The `ACCUMULATED_AMOUNT_USDT_FUNCTIONS.md` documentation is **100% accurate** in describing:
1. The intended fee percentage (3%)
2. The calculation logic (correct)
3. The code flow (correct)
4. The expected results (correct)

**The issue is NOT in the code or documentation** - it's purely a **configuration error** in Google Cloud Secret Manager.

---

## Configuration Source Analysis

### Where TP_FLAT_FEE is Read

**File:** `GCAccumulator-10-26/config_manager.py`

```python
def get_config():
    """Load configuration from Secret Manager."""
    config = {}

    secrets = [
        'TP_FLAT_FEE',  # <-- READS FROM HERE
        'CLOUD_SQL_CONNECTION_NAME',
        'DATABASE_NAME_SECRET',
        'DATABASE_USER_SECRET',
        'DATABASE_PASSWORD_SECRET'
    ]

    for secret_name in secrets:
        config[secret_name.lower().replace('_secret', '')] = get_secret(secret_name)

    return config
```

**Secret Manager Query:**
```bash
$ gcloud secrets versions access latest --secret=TP_FLAT_FEE
15  # <-- WRONG VALUE
```

**Should be:**
```bash
$ gcloud secrets versions access latest --secret=TP_FLAT_FEE
3  # <-- CORRECT VALUE
```

---

## Verification of Code Logic

### Code is Working Correctly

The GCAccumulator code is functioning **exactly as designed**:

1. ✅ Reads `TP_FLAT_FEE` from Secret Manager
2. ✅ Converts to Decimal for precision
3. ✅ Calculates fee: `payment_amount_usd * (tp_flat_fee / 100)`
4. ✅ Subtracts fee: `adjusted_amount_usd = payment_amount_usd - fee_amount`
5. ✅ Sets accumulated USDT: `accumulated_usdt = adjusted_amount_usd`
6. ✅ Stores in database correctly

**The problem:** Step 1 retrieves `15` instead of `3` from Secret Manager.

---

## Solution

### Immediate Fix Required

**Update Secret Manager:**
```bash
# Option 1: Update existing secret version
echo -n "3" | gcloud secrets versions add TP_FLAT_FEE --data-file=-

# Option 2: Verify current value first
gcloud secrets versions access latest --secret=TP_FLAT_FEE
# If shows "15", then update to "3"
```

**Expected Result:**
```bash
$ gcloud secrets versions access latest --secret=TP_FLAT_FEE
3
```

### Post-Fix Verification

**Test with New Payment:**
1. Trigger a new payment (subscription_price = $1.35)
2. Check `payout_accumulation` table
3. Verify: `accumulated_amount_usdt` should be **$1.3095** (not $1.1475)

**Database Query:**
```sql
SELECT
    id,
    payment_amount_usd,
    accumulated_amount_usdt,
    (payment_amount_usd - accumulated_amount_usdt) as fee,
    ((payment_amount_usd - accumulated_amount_usdt) / payment_amount_usd * 100) as fee_pct
FROM payout_accumulation
ORDER BY id DESC
LIMIT 1;
```

**Expected Output (after fix):**
```
payment_amount_usd: 1.35
accumulated_amount_usdt: 1.30950000
fee: 0.04050000
fee_pct: 3.00%
```

---

## Historical Data Correction

### Option 1: Leave Historical Data (Recommended)

**Rationale:**
- Only 3 payments affected (total loss: $0.486)
- Changing historical data is complex and risky
- Future payments will be correct after secret fix

**Action:**
- Update Secret Manager to `3`
- Monitor new payments to ensure 3% fee
- Accept $0.486 loss on existing 3 payments

---

### Option 2: Retroactive Correction (Complex)

**If you choose to fix historical data:**

1. **Identify Affected Records:**
```sql
SELECT id, payment_amount_usd, accumulated_amount_usdt
FROM payout_accumulation
WHERE (payment_amount_usd - accumulated_amount_usdt) / payment_amount_usd > 0.05;
-- Returns records with > 5% fee (catches 15% cases)
```

2. **Recalculate Correct Values:**
```sql
UPDATE payout_accumulation
SET accumulated_amount_usdt = payment_amount_usd * 0.97  -- Apply 3% fee
WHERE (payment_amount_usd - accumulated_amount_usdt) / payment_amount_usd > 0.05;
```

3. **Verify Update:**
```sql
SELECT
    id,
    payment_amount_usd,
    accumulated_amount_usdt,
    ((payment_amount_usd - accumulated_amount_usdt) / payment_amount_usd * 100) as fee_pct
FROM payout_accumulation;
```

**Expected After Update:**
```
ID | payment_amount_usd | accumulated_amount_usdt | fee_pct
---|-------------------|------------------------|--------
1  | 1.35              | 1.30950000             | 3.00%
2  | 1.35              | 1.30950000             | 3.00%
3  | 1.35              | 1.30950000             | 3.00%
```

---

## Prevention Measures

### 1. Add Validation to GCAccumulator

**File:** `GCAccumulator-10-26/acc10-26.py`

Add sanity check after reading config:
```python
tp_flat_fee = Decimal(config.get('tp_flat_fee', '3'))

# Sanity check: TP fee should be reasonable (0-10%)
if tp_flat_fee < 0 or tp_flat_fee > 10:
    print(f"⚠️ [CONFIG] WARNING: TP fee {tp_flat_fee}% seems unusual (expected 0-10%)")
    print(f"⚠️ [CONFIG] Using default 3% instead")
    tp_flat_fee = Decimal('3')
```

---

### 2. Secret Manager Validation Script

Create script to verify all secrets have expected values:
```bash
#!/bin/bash
# verify_secrets.sh

echo "Checking TP_FLAT_FEE..."
TP_FEE=$(gcloud secrets versions access latest --secret=TP_FLAT_FEE)

if [ "$TP_FEE" != "3" ]; then
    echo "❌ ERROR: TP_FLAT_FEE is '$TP_FEE' (expected '3')"
    exit 1
else
    echo "✅ TP_FLAT_FEE is correct: 3%"
fi
```

---

### 3. Database Trigger for Anomaly Detection

Create database trigger to alert on unusual fee percentages:
```sql
CREATE OR REPLACE FUNCTION check_fee_percentage()
RETURNS TRIGGER AS $$
DECLARE
    fee_pct NUMERIC;
BEGIN
    fee_pct := ((NEW.payment_amount_usd - NEW.accumulated_amount_usdt) /
                 NEW.payment_amount_usd * 100);

    IF fee_pct > 5 OR fee_pct < 0 THEN
        RAISE WARNING 'Unusual fee percentage detected: %% (ID: %)', fee_pct, NEW.id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_fee_on_insert
BEFORE INSERT ON payout_accumulation
FOR EACH ROW
EXECUTE FUNCTION check_fee_percentage();
```

---

## Summary

### The Incongruency Explained

| Aspect | Documentation | Reality | Root Cause |
|--------|--------------|---------|------------|
| **TP Fee Percentage** | 3% | 15% | Secret Manager value wrong |
| **Code Logic** | Correct | Correct | No code issue |
| **Calculation Formula** | Correct | Correct | No formula issue |
| **payment_amount_usd = $1.35** | Expected | Actual | ✓ Match |
| **accumulated_amount_usdt** | $1.3095 | $1.1475 | ✗ Mismatch |
| **Fee Deducted** | $0.0405 | $0.2025 | ✗ 5× too high |

**Root Cause:** `TP_FLAT_FEE` secret in Google Cloud Secret Manager is set to `15` instead of `3`.

**Impact:** Channel owners receive 85% of payments instead of 97% (12% under-payment).

**Solution:** Update `TP_FLAT_FEE` secret to `3`.

---

## Action Items

### Critical (Do Immediately)
1. ✅ Verify current `TP_FLAT_FEE` value in Secret Manager
2. ⬜ Update `TP_FLAT_FEE` to `3` if currently `15`
3. ⬜ Test with new payment to verify 3% fee is applied

### Important (Do Soon)
4. ⬜ Decide on historical data correction strategy
5. ⬜ Add config validation to GCAccumulator
6. ⬜ Create secret validation script

### Optional (Nice to Have)
7. ⬜ Add database trigger for fee anomaly detection
8. ⬜ Create monitoring alert for unusual fee percentages
9. ⬜ Document secret values in a secure checklist

---

## Related Documents

- `ACCUMULATED_AMOUNT_USDT_FUNCTIONS.md` - Correct documentation of intended behavior
- `THRESHOLD_PAYOUT_ARCHITECTURE.md` - Overall payout system design
- `DB_MIGRATION_THRESHOLD_PAYOUT.md` - Database schema details

---

**Document Created:** 2025-10-30
**Analysis By:** Claude Code
**Status:** Investigation Complete - Action Required
