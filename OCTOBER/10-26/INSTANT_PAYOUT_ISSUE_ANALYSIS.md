# Instant Payout Issue Analysis

## Issue Summary

For the instant payout flow, ChangeNOW API shows `amountFrom: 0.00149302` (unadjusted amount) instead of the expected `amountFrom: 0.001269067` (fee-adjusted amount that was passed in the swap creation request).

**Transaction Details:**
- ChangeNOW Transaction ID: `36b4cdde6bde04`
- Expected `fromAmount` (swap creation): `0.001269067 ETH` (after TP_FEE deduction)
- Actual `amountFrom` (ChangeNOW response): `0.00149302 ETH` (before TP_FEE deduction)

## Root Cause Analysis

### Flow Breakdown

1. **NowPayments Payment Receipt** (actual_eth_amount)
   - User subscribes via NowPayments
   - NowPayments reports: `actual_eth_amount = 0.00149302 ETH`
   - This is the FULL amount received from the user (before TP fee deduction)

2. **TP Fee Calculation** (GCSplit1)
   - Location: `GCSplit1-10-26/tps1-10-26.py:350-357`
   - For instant payouts (swap_currency='eth'):
   ```python
   tp_fee_decimal = float(tp_flat_fee if tp_flat_fee else "3") / 100
   adjusted_amount = actual_eth_amount * (1 - tp_fee_decimal)
   # adjusted_amount = 0.00149302 * (1 - 0.15) = 0.001269067 ETH
   ```
   - Result: `adjusted_amount = 0.001269067 ETH`

3. **ChangeNOW Swap Creation** (GCSplit3)
   - Location: `GCSplit3-10-26/tps3-10-26.py:133-141`
   - Creates swap with:
   ```python
   transaction = changenow_client.create_fixed_rate_transaction_with_retry(
       from_currency='eth',
       to_currency='shib',
       from_amount='0.001269067',  # ✅ FEE-ADJUSTED AMOUNT
       ...
   )
   ```
   - This tells ChangeNOW: "Expect to receive 0.001269067 ETH"

4. **Token Flow to GCHostPay** (GCSplit3 → GCSplit1 → GCHostPay1)
   - GCSplit3 encrypts response with BOTH amounts:
     - `actual_eth_amount = 0.00149302` (from NowPayments)
     - `from_amount = 0.001269067` (ChangeNOW estimate)
   - GCSplit1 receives the swap response and builds HostPay token
   - Location: `GCSplit1-10-26/tps1-10-26.py:783-792`
   ```python
   hostpay_token = build_hostpay_token(
       ...
       actual_eth_amount=payment_amount_eth,      # ❌ 0.00149302 (UNADJUSTED)
       estimated_eth_amount=estimated_amount_eth, # ✅ 0.001269067 (ChangeNOW)
       ...
   )
   ```

5. **ETH Payment Execution** (GCHostPay3) ⚠️ **BUG LOCATION**
   - Location: `GCHostPay3-10-26/tphp3-10-26.py:174-185`
   - Payment amount determination logic:
   ```python
   if actual_eth_amount > 0:
       payment_amount = actual_eth_amount  # ❌ Uses 0.00149302
       print(f"✅ Using ACTUAL ETH for payment: {payment_amount}")
   elif estimated_eth_amount > 0:
       payment_amount = estimated_eth_amount  # ✅ Should use this (0.001269067)
       print(f"⚠️ Using ESTIMATED ETH: {payment_amount}")
   ```
   - **BUG**: GCHostPay3 prioritizes `actual_eth_amount` and sends `0.00149302 ETH` to ChangeNOW

6. **ChangeNOW Updates Transaction**
   - ChangeNOW's payin address receives: `0.00149302 ETH`
   - ChangeNOW updates transaction: `amountFrom: 0.00149302`
   - **Result**: Mismatch between expected (0.001269067) and actual (0.00149302)

## The Problem

**Incorrect Logic in GCHostPay3:**

The current logic in GCHostPay3 sends the UNADJUSTED amount (`actual_eth_amount = 0.00149302`) instead of the FEE-ADJUSTED amount (`estimated_eth_amount = 0.001269067`) to ChangeNOW.

**Why this is wrong:**

1. **ChangeNOW Swap Creation**: When creating the swap, we told ChangeNOW to expect `fromAmount: 0.001269067`
2. **ETH Payment**: We then send `0.00149302 ETH` to their payin address
3. **ChangeNOW Behavior**: ChangeNOW receives more than expected and updates `amountFrom` to reflect what they actually received
4. **Consequence**: The TP fee (difference between 0.00149302 and 0.001269067) is being sent to ChangeNOW instead of being retained by the platform

## Variable Naming Confusion

The root cause is also related to variable naming confusion:

| Variable | Current Meaning | Correct Usage |
|----------|----------------|---------------|
| `actual_eth_amount` | Full ETH from NowPayments (BEFORE TP fee) | Should be used for auditing/logging ONLY |
| `from_amount` / `estimated_eth_amount` | ChangeNOW swap amount (AFTER TP fee) | Should be used for PAYMENT to ChangeNOW |

In GCHostPay3, the variable `actual_eth_amount` is misleadingly named because it represents the UNADJUSTED amount, which should NOT be the "actual" amount sent to ChangeNOW.

## Impact Analysis

### Financial Impact
- **TP Fee Loss**: The platform is losing the TP fee on every instant payout
- **Example Transaction**:
  - TP fee collected: `0.00149302 - 0.001269067 = 0.000223953 ETH` (~15%)
  - But this fee is being sent to ChangeNOW instead of retained
  - Platform revenue loss: 100% of TP fee per transaction

### User Impact
- Users might actually receive MORE tokens than expected (since ChangeNOW gets more ETH)
- Not a user-facing issue, but a platform revenue issue

### Threshold Payout Impact
- **Threshold payouts are NOT affected** by this bug
- Reason: For threshold payouts, the swap_currency is 'usdt' (not 'eth')
- The USDT amount is calculated correctly and doesn't involve `actual_eth_amount`

## Solution

### Fix in GCHostPay3 (tphp3-10-26.py)

**Current Logic (Lines 174-185):**
```python
if actual_eth_amount > 0:
    payment_amount = actual_eth_amount  # ❌ BUG: Sends unadjusted amount
    print(f"✅ Using ACTUAL ETH for payment: {payment_amount}")
elif estimated_eth_amount > 0:
    payment_amount = estimated_eth_amount
    print(f"⚠️ Using ESTIMATED ETH: {payment_amount}")
else:
    payment_amount = from_amount
    print(f"⚠️ Using legacy from_amount: {payment_amount}")
```

**Proposed Fix:**
```python
# ✅ CRITICAL FIX: For instant payouts, always use the ChangeNOW swap amount
# The actual_eth_amount is for auditing only - it includes the TP fee
# which should NOT be sent to ChangeNOW

if from_currency.lower() == 'eth':
    # Instant payout: Use ChangeNOW estimate (fee-adjusted amount)
    if estimated_eth_amount > 0:
        payment_amount = estimated_eth_amount  # ✅ Fee-adjusted (0.001269067)
        print(f"✅ [INSTANT] Using ChangeNOW swap amount: {payment_amount} ETH")
    elif from_amount > 0:
        payment_amount = from_amount  # Fallback to from_amount
        print(f"⚠️ [INSTANT] Using from_amount fallback: {payment_amount} ETH")
    else:
        print(f"❌ [INSTANT] No valid payment amount found!")
        abort(400, "Invalid payment amount")

    # Log actual_eth_amount for auditing purposes
    if actual_eth_amount > 0:
        tp_fee_collected = actual_eth_amount - payment_amount
        print(f"💰 [AUDIT] ACTUAL ETH from NowPayments: {actual_eth_amount}")
        print(f"💸 [AUDIT] TP Fee collected: {tp_fee_collected} ETH")
        print(f"💎 [AUDIT] Amount sent to ChangeNOW: {payment_amount} ETH")

elif from_currency.lower() in TOKEN_CONFIGS:
    # ERC-20 token (USDT, etc.): Use from_amount or estimated_eth_amount
    if estimated_eth_amount > 0:
        payment_amount = estimated_eth_amount
        print(f"✅ [ERC20] Using estimated amount: {payment_amount}")
    elif from_amount > 0:
        payment_amount = from_amount
        print(f"✅ [ERC20] Using from_amount: {payment_amount}")
    else:
        print(f"❌ [ERC20] No valid payment amount found!")
        abort(400, "Invalid payment amount")
else:
    abort(400, f"Unsupported currency: {from_currency}")
```

### Additional Changes

**1. Update Database Schema (Optional - for better auditing)**
- Add column to track TP fee collected per transaction:
  ```sql
  ALTER TABLE hostpay_transaction
  ADD COLUMN tp_fee_collected DECIMAL(18, 8);
  ```

**2. Update GCHostPay3 Database Logging (tphp3-10-26.py:314-328)**
```python
# Calculate TP fee collected (for instant payouts only)
tp_fee_collected = 0.0
if from_currency.lower() == 'eth' and actual_eth_amount > 0:
    tp_fee_collected = actual_eth_amount - from_amount

db_success = db_manager.insert_hostpay_transaction(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,
    from_network=from_network,
    from_amount=from_amount,  # ✅ ChangeNOW swap amount
    payin_address=payin_address,
    is_complete=True,
    tx_hash=tx_result['tx_hash'],
    tx_status=tx_result['status'],
    gas_used=tx_result['gas_used'],
    block_number=tx_result['block_number'],
    actual_eth_amount=actual_eth_amount,  # ✅ For auditing
    tp_fee_collected=tp_fee_collected  # ✅ NEW: Track TP fee
)
```

## Testing Plan

### 1. Pre-Deployment Testing (Testnet)
- Deploy fixed GCHostPay3 to testnet
- Create test instant payout with known amounts
- Verify:
  - ChangeNOW receives fee-adjusted amount
  - `amountFrom` matches swap creation `fromAmount`
  - TP fee is NOT sent to ChangeNOW

### 2. Post-Deployment Monitoring
- Monitor first 10 instant payouts after deployment
- Check ChangeNOW API responses for `amountFrom` accuracy
- Verify platform revenue is being retained

### 3. Comparison Testing
- Compare pre-fix vs post-fix transactions
- Calculate TP fee retention rate improvement

## Deployment Checklist

- [ ] Review and approve fix in GCHostPay3-10-26/tphp3-10-26.py
- [ ] Test fix on staging/testnet environment
- [ ] Verify threshold payouts still work correctly (should be unaffected)
- [ ] Deploy to production
- [ ] Monitor logs for first 10 transactions
- [ ] Verify ChangeNOW API responses show correct `amountFrom`
- [ ] Update PROGRESS.md with deployment status

## Critical Notes

1. **DO NOT** change threshold payout logic - it works correctly
2. **ONLY** instant payouts are affected by this bug
3. The fix ensures TP fee is RETAINED by platform, not sent to ChangeNOW
4. Variable `actual_eth_amount` should be used for AUDITING ONLY, not for payment execution
5. Always send `estimated_eth_amount` (or `from_amount`) to ChangeNOW - this is the amount specified in the swap creation

## Conclusion

The bug is caused by incorrect prioritization of `actual_eth_amount` over `estimated_eth_amount` in GCHostPay3's payment execution logic. The fix is straightforward: use `estimated_eth_amount` (the ChangeNOW swap amount) for instant payouts, and reserve `actual_eth_amount` for auditing purposes only.

This ensures:
1. ChangeNOW receives the exact amount specified in swap creation
2. Platform retains the TP fee as intended
3. No impact on threshold payout functionality
