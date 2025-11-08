# Threshold Payout Assumption Review

## Executive Summary

This document analyzes how the `actual_eth_amount` variable flows through the **threshold payout** architecture and validates whether the proposed fix in `INSTANT_PAYOUT_ISSUE_ANALYSIS.md` would affect threshold payouts.

**Conclusion**: The proposed fix in `INSTANT_PAYOUT_ISSUE_ANALYSIS.md` is **INCORRECT** and would **BREAK BOTH instant AND threshold payouts**. A different fix is required.

## The Real Root Cause

After comprehensive analysis, the actual bug is in **GCHostPay1's token_manager.py** (line 238), not in GCHostPay3.

### Bug Location

**File**: `GCHostPay1-10-26/token_manager.py`
**Function**: `decrypt_gcsplit1_to_gchostpay1_token()`
**Line**: 238

```python
return {
    "unique_id": unique_id,
    "cn_api_id": cn_api_id,
    "from_currency": from_currency,
    "from_network": from_network,
    "from_amount": first_amount,  # ❌ BUG: Uses actual_eth_amount (unadjusted)
    "actual_eth_amount": actual_eth_amount,      # 0.00149302 (unadjusted)
    "estimated_eth_amount": estimated_eth_amount, # 0.001269067 (fee-adjusted)
    "payin_address": payin_address,
    "timestamp": timestamp
}
```

**Problem**: `from_amount` is set to `first_amount`, which equals `actual_eth_amount` (the UNADJUSTED amount before TP fee deduction).

## Threshold Payout Flow Analysis

### Phase 1: Payment Reception (NowPayments → GCWebhook1 → GCAccumulator)

**Step 1**: User makes payment via NowPayments
- NowPayments reports: `outcome_amount = 0.00149302 ETH`
- This is stored as `nowpayments_outcome_amount`

**Step 2**: GCWebhook1 receives IPN callback from np-webhook
- Location: `GCWebhook1-10-26/tph1-10-26.py:198-349`
- Extracts:
  - `nowpayments_outcome_amount = 0.00149302 ETH` (ACTUAL ETH from NowPayments)
  - `outcome_amount_usd = $4.95` (Actual USD value from CoinGecko)
  - `payout_mode = "threshold"` (from database lookup)

**Step 3**: GCWebhook1 routes to GCAccumulator (not GCSplit1)
- Location: `GCWebhook1-10-26/tph1-10-26.py:331-370`
- Since `payout_mode = "threshold"`, payment is routed to GCAccumulator
- Payload includes:
  ```python
  {
      'user_id': user_id,
      'client_id': client_id,
      'payment_amount_usd': outcome_amount_usd,  # $4.95 USD
      'nowpayments_outcome_amount': 0.00149302,  # ACTUAL ETH
      ...
  }
  ```

**Step 4**: GCAccumulator stores payment
- Location: `GCAccumulator-10-26/acc10-26.py:63-170`
- Calculates `adjusted_amount_usd` by removing TP fee:
  ```python
  tp_flat_fee = 15%
  adjusted_amount_usd = $4.95 * (1 - 0.15) = $4.2075
  ```
- Stores in `payout_accumulation` table:
  - `accumulated_eth = $4.2075` (USD value, NOT ETH!)
  - `nowpayments_outcome_amount = 0.00149302 ETH`
  - `conversion_status = 'pending'`

**Key Observation**: At this point, `actual_eth_amount` (0.00149302) is stored in the database but is NOT used for immediate payment processing. The USD value is what matters for threshold accumulation.

### Phase 2: Accumulation & Batch Trigger (GCMicroBatchProcessor)

**Step 5**: Cloud Scheduler triggers threshold check every 15 minutes
- Location: `GCMicroBatchProcessor-10-26/microbatch10-26.py:73-290`
- Queries total pending USD: `total_pending = $420.75` (sum of accumulated_eth)
- Queries total actual ETH: `total_actual_eth = 0.12843 ETH` (sum of nowpayments_outcome_amount)

**Step 6**: If threshold reached, create ETH→USDT batch swap
- Location: `GCMicroBatchProcessor-10-26/microbatch10-26.py:155-195`
- Decision logic:
  ```python
  if total_actual_eth > 0:
      eth_for_swap = total_actual_eth  # Use ACTUAL ETH from NowPayments
      print(f"✅ Using ACTUAL ETH: {eth_for_swap} ETH")
  else:
      # Fallback: estimate ETH from USD amount
      eth_for_swap = estimate_from_changenow(total_pending)
  ```
- Creates ChangeNOW swap: `0.12843 ETH → ~$420 USDT`

**Step 7**: Encrypt token for GCHostPay1
- Location: `GCMicroBatchProcessor-10-26/microbatch10-26.py:246-253`
- Token contains:
  ```python
  {
      'batch_conversion_id': 'uuid',
      'cn_api_id': 'changenow_id',
      'from_currency': 'eth',
      'from_network': 'eth',
      'from_amount': 0.12843,  # total_actual_eth
      'payin_address': 'changenow_payin_address',
      'context': 'batch'
  }
  ```

**Critical Point**: The `from_amount` here is the UNADJUSTED total_actual_eth (sum of all actual_eth_amount values). This is CORRECT for batch swaps because:
1. The ChangeNOW swap was created with this ACTUAL amount
2. We want to send the ACTUAL ETH we collected from users
3. The TP fee was already deducted at the accumulation stage (in USD)

### Phase 3: Batch Payment Execution (GCHostPay1 → GCHostPay3)

**Step 8**: GCHostPay1 receives batch token
- Location: `GCHostPay1-10-26/tphp1-10-26.py:349-361`
- Decrypts token:
  ```python
  {
      'unique_id': 'batch_uuid',
      'cn_api_id': 'changenow_id',
      'from_currency': 'eth',
      'from_amount': 0.12843,  # total_actual_eth
      'payin_address': 'changenow_payin_address',
      'context': 'batch'
  }
  ```

**Step 9**: GCHostPay1 validates ChangeNOW status via GCHostPay2
- ChangeNOW status = "waiting"
- Passes token to GCHostPay3

**Step 10**: GCHostPay3 executes ETH payment
- Location: `GCHostPay3-10-26/tphp3-10-26.py:112-291`
- Decrypts token:
  ```python
  {
      'from_currency': 'eth',
      'from_amount': 0.12843,
      'actual_eth_amount': 0.0,  # NOT in token (defaults to 0.0)
      'estimated_eth_amount': 0.0,  # NOT in token (defaults to 0.0)
      'payin_address': 'changenow_payin_address',
      'context': 'batch'
  }
  ```

**Step 11**: Payment amount determination (CURRENT CODE)
- Location: `GCHostPay3-10-26/tphp3-10-26.py:174-185`
  ```python
  if actual_eth_amount > 0:
      payment_amount = actual_eth_amount  # NOT triggered (=0.0)
  elif estimated_eth_amount > 0:
      payment_amount = estimated_eth_amount  # NOT triggered (=0.0)
  elif from_amount > 0:
      payment_amount = from_amount  # ✅ TRIGGERED (=0.12843)
  ```

**Step 12**: Send 0.12843 ETH to ChangeNOW payin address
- This is CORRECT for batch swaps
- ChangeNOW receives the exact amount specified in swap creation

### Summary: Threshold Payout Flow is CORRECT

For threshold payouts (batch conversions):
- `from_amount` = total_actual_eth (UNADJUSTED, which is correct)
- `actual_eth_amount` = 0.0 (not in token)
- `estimated_eth_amount` = 0.0 (not in token)
- Payment amount = from_amount ✅

**Threshold payouts work correctly** because:
1. The TP fee is deducted during accumulation (in USD)
2. The batch swap is created with the ACTUAL ETH collected
3. GCHostPay3 sends the ACTUAL ETH to ChangeNOW
4. No fee adjustment is needed at payment time

## Instant Payout Flow Analysis (The Bug)

### Phase 1: Payment Reception (NowPayments → GCWebhook1 → GCSplit1)

**Step 1**: User makes payment via NowPayments
- NowPayments reports: `outcome_amount = 0.00149302 ETH`

**Step 2**: GCWebhook1 routes to GCSplit1 (not GCAccumulator)
- Since `payout_mode = "instant"`, payment is routed to GCSplit1
- Payload includes:
  ```python
  {
      'actual_eth_amount': 0.00149302,  # ACTUAL ETH from NowPayments
      'subscription_price': 5.00,
      'payout_mode': 'instant',
      ...
  }
  ```

**Step 3**: GCSplit1 calculates adjusted amount
- Location: `GCSplit1-10-26/tps1-10-26.py:350-357`
  ```python
  tp_fee_decimal = 0.15  # 15%
  adjusted_amount = 0.00149302 * (1 - 0.15) = 0.001269067 ETH
  ```

### Phase 2: Market Estimate (GCSplit1 → GCSplit2 → GCSplit1)

**Step 4**: GCSplit1 requests ETH→SHIB estimate from GCSplit2
- Sends `adjusted_amount = 0.001269067 ETH` (fee-adjusted)
- GCSplit2 returns estimate

**Step 5**: GCSplit1 stores in split_payout_request table
- `from_amount = 0.001269067 ETH` (fee-adjusted)

### Phase 3: Swap Creation (GCSplit1 → GCSplit3 → GCSplit1)

**Step 6**: GCSplit3 creates ChangeNOW swap
- Location: `GCSplit3-10-26/tps3-10-26.py:133-141`
- Creates swap with:
  ```python
  from_amount = 0.001269067 ETH  # fee-adjusted
  ```
- ChangeNOW responds:
  ```json
  {
      "id": "36b4cdde6bde04",
      "fromAmount": 0.001269067,  # What we told ChangeNOW to expect
      "payinAddress": "0x233893..."
  }
  ```

**Step 7**: GCSplit1 builds GCHostPay token
- Location: `GCSplit1-10-26/tps1-10-26.py:783-792`
- **Critical Decision**: Which amount to use?
  ```python
  # Current code (WRONG for instant payouts)
  if actual_eth_amount > 0:
      payment_amount_eth = actual_eth_amount  # 0.00149302 (UNADJUSTED)
      estimated_amount_eth = from_amount      # 0.001269067 (fee-adjusted)
  ```
- Builds token with:
  ```python
  actual_eth_amount = 0.00149302     # UNADJUSTED (FIRST in token)
  estimated_eth_amount = 0.001269067  # FEE-ADJUSTED (SECOND in token)
  ```

### Phase 4: Token Decryption Bug (GCHostPay1)

**Step 8**: GCHostPay1 decrypts GCSplit1 token
- Location: `GCHostPay1-10-26/token_manager.py:233-243`
- Token structure:
  ```
  - actual_eth_amount (FIRST) = 0.00149302
  - estimated_eth_amount (SECOND) = 0.001269067
  ```
- Decryption logic:
  ```python
  first_amount = 0.00149302    # actual_eth_amount
  second_amount = 0.001269067  # estimated_eth_amount

  # Set return values
  actual_eth_amount = first_amount       # 0.00149302
  estimated_eth_amount = second_amount   # 0.001269067
  from_amount = first_amount  # ❌ BUG: Uses UNADJUSTED amount!

  return {
      "from_amount": 0.00149302,          # ❌ WRONG
      "actual_eth_amount": 0.00149302,     # ✅ Correct
      "estimated_eth_amount": 0.001269067  # ✅ Correct
  }
  ```

**Root Cause**: Line 238 sets `from_amount = first_amount` for "backward compatibility", but `first_amount` is the UNADJUSTED amount!

### Phase 5: Wrong Amount Propagation (GCHostPay1 → GCHostPay3)

**Step 9**: GCHostPay1 encrypts token for GCHostPay3
- Location: `GCHostPay1-10-26/tphp1-10-26.py:544-552`
  ```python
  encrypted_token_payment = token_manager.encrypt_gchostpay1_to_gchostpay3_token(
      from_amount=from_amount,  # 0.00149302 (WRONG!)
      ...
  )
  ```

**Step 10**: GCHostPay3 receives and uses wrong amount
- `from_amount = 0.00149302` (UNADJUSTED)
- `actual_eth_amount = 0.0` (not in token)
- `estimated_eth_amount = 0.0` (not in token)
- Payment amount = from_amount = 0.00149302 ❌

**Step 11**: ChangeNOW receives wrong amount
- Expected: 0.001269067 ETH
- Received: 0.00149302 ETH
- Difference: 0.000223953 ETH (15% TP fee sent to ChangeNOW instead of retained)

## Why the Proposed Fix is Wrong

### Original Proposed Fix (INCORRECT)

In `INSTANT_PAYOUT_ISSUE_ANALYSIS.md`, the proposed fix was to modify GCHostPay3:

```python
# Proposed in original analysis (WRONG)
if from_currency.lower() == 'eth':
    if estimated_eth_amount > 0:
        payment_amount = estimated_eth_amount  # Would use 0.0
    elif from_amount > 0:
        payment_amount = from_amount  # Fallback
```

### Why This Fails

**For Instant Payouts**:
- `estimated_eth_amount = 0.0` (not in GCHostPay3 token)
- Would fall back to `from_amount = 0.00149302` (STILL WRONG)
- No fix achieved

**For Threshold Payouts (Batch)**:
- `estimated_eth_amount = 0.0` (not in token)
- Would fall back to `from_amount = 0.12843` (correct)
- Works by accident, but fragile

### Token Structure Problem

The issue is that **GCHostPay1 → GCHostPay3 tokens do NOT contain**:
- `actual_eth_amount` (always 0.0)
- `estimated_eth_amount` (always 0.0)

They only contain:
- `from_amount` (which is already wrong)

So fixing GCHostPay3 alone cannot solve the problem!

## The Correct Fix

### Option 1: Fix GCHostPay1 Token Decryption (RECOMMENDED)

**File**: `GCHostPay1-10-26/token_manager.py`
**Line**: 238
**Change**:

```python
# BEFORE (WRONG)
return {
    ...
    "from_amount": first_amount,  # Uses actual_eth_amount (unadjusted)
    "actual_eth_amount": actual_eth_amount,
    "estimated_eth_amount": estimated_eth_amount,
    ...
}

# AFTER (CORRECT)
return {
    ...
    "from_amount": estimated_eth_amount,  # ✅ Use fee-adjusted amount
    "actual_eth_amount": actual_eth_amount,
    "estimated_eth_amount": estimated_eth_amount,
    ...
}
```

**Why This Works**:

For **Instant Payouts**:
- `from_amount = estimated_eth_amount = 0.001269067` (fee-adjusted) ✅
- GCHostPay3 sends 0.001269067 ETH to ChangeNOW ✅
- TP fee retained by platform ✅

For **Threshold Payouts (Batch)**:
- Token from GCMicroBatchProcessor has only ONE amount (no actual/estimated separation)
- Falls back to old format: `actual_eth_amount = estimated_eth_amount = total_actual_eth`
- `from_amount = estimated_eth_amount = total_actual_eth = 0.12843` ✅
- GCHostPay3 sends 0.12843 ETH to ChangeNOW ✅
- Still works correctly ✅

### Option 2: Fix GCSplit1 Token Building (ALTERNATIVE)

**File**: `GCSplit1-10-26/tps1-10-26.py`
**Lines**: 788-789, and `build_hostpay_token` function lines 172-173
**Change**:

Swap the order of amounts in the token so estimated comes first:

```python
# In build_hostpay_token function:
# BEFORE
packed_data.extend(struct.pack(">d", actual_eth_amount))      # FIRST
packed_data.extend(struct.pack(">d", estimated_eth_amount))   # SECOND

# AFTER
packed_data.extend(struct.pack(">d", estimated_eth_amount))   # FIRST ✅
packed_data.extend(struct.pack(">d", actual_eth_amount))      # SECOND
```

And in GCSplit1 ENDPOINT 3:
```python
# BEFORE
hostpay_token = build_hostpay_token(
    actual_eth_amount=payment_amount_eth,
    estimated_eth_amount=estimated_amount_eth,
    ...
)

# AFTER
hostpay_token = build_hostpay_token(
    actual_eth_amount=estimated_amount_eth,   # Swap order ✅
    estimated_eth_amount=payment_amount_eth,  # Swap order ✅
    ...
)
```

**Why This Works**:
- first_amount becomes estimated_eth_amount (fee-adjusted)
- from_amount = first_amount = estimated_eth_amount ✅
- Threshold payouts unaffected (still use single amount)

## Comparison: Option 1 vs Option 2

| Aspect | Option 1 (Fix GCHostPay1) | Option 2 (Fix GCSplit1) |
|--------|---------------------------|-------------------------|
| **Simplicity** | ✅ Single line change | ❌ Multiple changes, parameter swap |
| **Safety** | ✅ Low risk | ⚠️ Higher risk (parameter order confusion) |
| **Clarity** | ✅ Clear: use estimated_eth_amount | ❌ Confusing: parameters named opposite to values |
| **Testing** | ✅ Easy to test | ⚠️ Need to verify parameter semantics |
| **Threshold Impact** | ✅ No impact (falls back correctly) | ✅ No impact (single amount) |
| **Instant Impact** | ✅ Fixes issue | ✅ Fixes issue |
| **Maintainability** | ✅ Easy to understand | ❌ Confusing (actual != actual) |

**Recommendation**: **Option 1** is strongly preferred.

## Impact on Variable Flow

### Variable: `actual_eth_amount`

**Instant Payouts**:
- **Source**: NowPayments (`outcome_amount = 0.00149302 ETH`)
- **GCWebhook1**: Extracted as `actual_eth_amount`
- **GCSplit1**: Received as `actual_eth_amount`
- **GCSplit1 Token**: Packed as FIRST amount (0.00149302)
- **GCHostPay1 Decrypt**: Retrieved as `first_amount`, assigned to `from_amount` ❌
- **GCHostPay1 → GCHostPay3 Token**: NOT included (only `from_amount`)
- **GCHostPay3**: Defaults to 0.0 (not in token)
- **Usage**: NOT used (but `from_amount` incorrectly set to this value)

**Threshold Payouts**:
- **Source**: NowPayments (`outcome_amount` per payment)
- **GCAccumulator**: Stored as `nowpayments_outcome_amount`
- **GCMicroBatchProcessor**: Summed as `total_actual_eth`, used for batch swap
- **GCMicroBatchProcessor → GCHostPay1 Token**: Sent as `from_amount` (single amount)
- **GCHostPay1**: Received as `from_amount`
- **GCHostPay1 → GCHostPay3 Token**: Passed as `from_amount`
- **GCHostPay3**: Used as `from_amount` ✅
- **Usage**: Correctly used for payment

### Variable: `estimated_eth_amount`

**Instant Payouts**:
- **Source**: ChangeNOW estimate (0.001269067 ETH, fee-adjusted)
- **GCSplit1**: Calculated from `from_amount` (ChangeNOW estimate response)
- **GCSplit1 Token**: Packed as SECOND amount (0.001269067)
- **GCHostPay1 Decrypt**: Retrieved as `second_amount`, stored as `estimated_eth_amount`
- **GCHostPay1 → GCHostPay3 Token**: NOT included (only `from_amount`)
- **GCHostPay3**: Defaults to 0.0 (not in token)
- **Usage**: NOT used (but SHOULD be used for payment)

**Threshold Payouts**:
- **Source**: N/A (not applicable)
- **Usage**: Never used in threshold flow

### Variable: `from_amount`

**Instant Payouts**:
- **GCHostPay1 Decrypt**: Set to `first_amount` = `actual_eth_amount` = 0.00149302 ❌
- **GCHostPay1 → GCHostPay3 Token**: Passed as 0.00149302 ❌
- **GCHostPay3**: Used as payment amount ❌
- **Result**: WRONG amount sent to ChangeNOW

**Threshold Payouts**:
- **GCMicroBatchProcessor**: Set to `total_actual_eth` = 0.12843 ✅
- **GCHostPay1**: Passed through as 0.12843 ✅
- **GCHostPay3**: Used as payment amount ✅
- **Result**: CORRECT amount sent to ChangeNOW

## Testing Plan

### Pre-Deployment Testing

**Test 1: Instant Payout (Fee-Adjusted)**
1. Create instant payout with known amounts:
   - actual_eth_amount = 0.00149302 ETH (from NowPayments)
   - TP fee = 15%
   - Expected payment to ChangeNOW = 0.001269067 ETH
2. Verify logs:
   - GCHostPay1 from_amount = 0.001269067 ✅
   - GCHostPay3 payment_amount = 0.001269067 ✅
3. Query ChangeNOW API:
   - `amountFrom` should equal 0.001269067 ✅

**Test 2: Threshold Payout (Batch)**
1. Accumulate payments to trigger batch:
   - total_actual_eth = 0.12843 ETH
2. Verify logs:
   - GCMicroBatchProcessor eth_for_swap = 0.12843 ✅
   - GCHostPay1 from_amount = 0.12843 ✅
   - GCHostPay3 payment_amount = 0.12843 ✅
3. Query ChangeNOW API:
   - `amountFrom` should equal 0.12843 ✅

**Test 3: Backward Compatibility (Single Amount Token)**
1. Create token with old format (single amount)
2. Verify GCHostPay1 decryption:
   - from_amount = estimated_eth_amount = actual_eth_amount ✅
3. Verify GCHostPay3 uses correct amount ✅

### Post-Deployment Monitoring

1. Monitor first 10 instant payouts
2. Check ChangeNOW API `amountFrom` matches expected (fee-adjusted)
3. Verify platform TP fee retention
4. Monitor first batch conversion
5. Verify ChangeNOW receives correct total_actual_eth

## Deployment Checklist

### Phase 1: Code Changes
- [ ] Modify `GCHostPay1-10-26/token_manager.py` line 238
- [ ] Change `"from_amount": first_amount` to `"from_amount": estimated_eth_amount"`
- [ ] Add comment: `# Use fee-adjusted amount (estimated) for instant payouts`
- [ ] Review change with team
- [ ] Test locally with sample tokens

### Phase 2: Testing
- [ ] Deploy to staging/testnet
- [ ] Run Test 1 (instant payout)
- [ ] Run Test 2 (threshold batch)
- [ ] Run Test 3 (backward compat)
- [ ] Verify all tests pass

### Phase 3: Production Deployment
- [ ] Deploy GCHostPay1 to production
- [ ] Monitor logs for first 10 instant payouts
- [ ] Verify ChangeNOW API responses
- [ ] Monitor first batch conversion
- [ ] Calculate TP fee retention improvement

### Phase 4: Documentation
- [ ] Update PROGRESS.md with deployment status
- [ ] Document fix in DECISIONS.md
- [ ] Archive original bug report

## Critical Notes

1. **DO NOT** modify GCHostPay3 - the bug is not there
2. **DO NOT** swap parameter order in GCSplit1 - too risky and confusing
3. **ONLY** change line 238 in GCHostPay1 token_manager.py
4. The fix is a **single-line change**: `from_amount = estimated_eth_amount`
5. Threshold payouts will continue to work because they fall back to old format (single amount)
6. Instant payouts will be fixed because fee-adjusted amount is now used

## Conclusion

The bug is a **single-line issue** in GCHostPay1's token decryption logic. The variable `from_amount` is incorrectly set to `first_amount` (actual_eth_amount, unadjusted) instead of `estimated_eth_amount` (fee-adjusted).

**The Fix**:
- File: `GCHostPay1-10-26/token_manager.py`
- Line: 238
- Change: `"from_amount": estimated_eth_amount`

This ensures:
1. ✅ Instant payouts use fee-adjusted amount
2. ✅ Threshold payouts continue to work correctly
3. ✅ Platform retains TP fee as intended
4. ✅ ChangeNOW receives the amount specified in swap creation
5. ✅ No impact on existing threshold payout functionality

The proposed fix in `INSTANT_PAYOUT_ISSUE_ANALYSIS.md` was incorrect because it attempted to fix GCHostPay3, which doesn't have access to the necessary variables (`actual_eth_amount` and `estimated_eth_amount` are not passed in the GCHostPay1 → GCHostPay3 token).
