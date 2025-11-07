# Instant Payout Issue Analysis

## Issue Summary

For the instant payout flow, ChangeNOW API shows `amountFrom: 0.00149302` (unadjusted amount) instead of the expected `amountFrom: 0.001269067` (fee-adjusted amount that was passed in the swap creation request).

**Transaction Details:**
- ChangeNOW Transaction ID: `36b4cdde6bde04`
- Expected `fromAmount` (swap creation): `0.001269067 ETH` (after TP_FEE deduction)
- Actual `amountFrom` (ChangeNOW response): `0.00149302 ETH` (before TP_FEE deduction)

## Root Cause Analysis

### The Problem

ChangeNOW is receiving **MORE ETH than we told them to expect** in the swap creation. This happens because we're sending the **UNADJUSTED** amount (0.00149302 ETH) instead of the **FEE-ADJUSTED** amount (0.001269067 ETH) to their payin address.

### Flow Breakdown

#### 1. NowPayments Payment Receipt
- User subscribes via NowPayments
- NowPayments reports: `actual_eth_amount = 0.00149302 ETH`
- This is the FULL amount received from the user (**BEFORE** TP fee deduction)

#### 2. TP Fee Calculation (GCSplit1)
**Location:** `GCSplit1-10-26/tps1-10-26.py:350-357`

For instant payouts (`swap_currency='eth'`):
```python
tp_fee_decimal = float(tp_flat_fee if tp_flat_fee else "3") / 100
adjusted_amount = actual_eth_amount * (1 - tp_fee_decimal)
# adjusted_amount = 0.00149302 * (1 - 0.15) = 0.001269067 ETH
```
- TP Fee: 15%
- Adjusted amount (post-TP-fee): `0.001269067 ETH`

#### 3. ChangeNOW Swap Creation (GCSplit3)
**Location:** `GCSplit3-10-26/tps3-10-26.py:133-141`

GCSplit3 correctly creates the swap with the **fee-adjusted amount**:
```python
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency='eth',
    to_currency='shib',
    from_amount='0.001269067',  # ✅ FEE-ADJUSTED AMOUNT
    address=wallet_address,
    ...
)
```

This tells ChangeNOW: **"Expect to receive 0.001269067 ETH"**

#### 4. Token Flow: GCSplit1 → GCHostPay1

**Location:** `GCSplit1-10-26/tps1-10-26.py:783-792`

GCSplit1 builds a token with BOTH amounts:
```python
hostpay_token = build_hostpay_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,
    from_network=from_network,
    actual_eth_amount=payment_amount_eth,      # 0.00149302 (UNADJUSTED)
    estimated_eth_amount=estimated_amount_eth, # 0.001269067 (ChangeNOW)
    payin_address=payin_address,
    signing_key=tps_hostpay_signing_key
)
```

**Location:** `GCSplit1-10-26/token_manager.py:172-173`

The token packing order:
```python
packed_data.extend(struct.pack(">d", actual_eth_amount))      # FIRST (0.00149302)
packed_data.extend(struct.pack(">d", estimated_eth_amount))   # SECOND (0.001269067)
```

#### 5. 🐛 **THE BUG** - GCHostPay1 Token Decryption

**Location:** `GCHostPay1-10-26/token_manager.py:233-243`

When GCHostPay1 decrypts the token from GCSplit1:
```python
# Line 155-156: Read first amount
first_amount = struct.unpack(">d", raw[offset:offset+8])[0]  # 0.00149302
offset += 8

# Lines 168-177: Read second amount (if present)
second_amount = struct.unpack(">d", raw[offset:offset+8])[0]  # 0.001269067
offset += 8

# Lines 173-174: Assign amounts
actual_eth_amount = first_amount      # 0.00149302
estimated_eth_amount = second_amount  # 0.001269067

# Line 238: ❌ BUG - Sets from_amount to UNADJUSTED amount
return {
    "unique_id": unique_id,
    "cn_api_id": cn_api_id,
    "from_currency": from_currency,
    "from_network": from_network,
    "from_amount": first_amount,  # ❌ BUG: Uses 0.00149302 (unadjusted)
    "actual_eth_amount": actual_eth_amount,      # 0.00149302
    "estimated_eth_amount": estimated_eth_amount, # 0.001269067
    "payin_address": payin_address,
    "timestamp": timestamp
}
```

**This is the bug**: Line 238 sets `from_amount` to `first_amount` (actual_eth_amount = 0.00149302) instead of `estimated_eth_amount` (0.001269067).

#### 6. GCHostPay1 Endpoint 1 Processing

**Location:** `GCHostPay1-10-26/tphp1-10-26.py:369-377`

```python
cn_api_id = decrypted_data['cn_api_id']
from_currency = decrypted_data['from_currency']
from_network = decrypted_data['from_network']
from_amount = decrypted_data['from_amount']  # ❌ Gets 0.00149302 (WRONG!)
payin_address = decrypted_data['payin_address']

# These fields are available but not used to override from_amount
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)      # 0.00149302
estimated_eth_amount = decrypted_data.get('estimated_eth_amount', 0.0) # 0.001269067
```

#### 7. GCHostPay1 → GCHostPay3 Token Creation

**Location:** `GCHostPay1-10-26/tphp1-10-26.py:544-551`

```python
encrypted_token_payment = token_manager.encrypt_gchostpay1_to_gchostpay3_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,
    from_network=from_network,
    from_amount=from_amount,  # ❌ Passes 0.00149302 (WRONG!)
    payin_address=payin_address,
    context=context
)
```

**CRITICAL:** This token does NOT include `actual_eth_amount` or `estimated_eth_amount` fields!

**Location:** `GCHostPay1-10-26/token_manager.py:660-702`

The encryption only packs:
```python
packed_data.extend(self._pack_string(unique_id))
packed_data.extend(self._pack_string(cn_api_id))
packed_data.extend(self._pack_string(from_currency.lower()))
packed_data.extend(self._pack_string(from_network.lower()))
packed_data.extend(struct.pack(">d", from_amount))  # Only this amount!
packed_data.extend(self._pack_string(payin_address))
packed_data.extend(self._pack_string(context.lower()))
```

#### 8. GCHostPay3 Payment Execution

**Location:** `GCHostPay3-10-26/tphp3-10-26.py:153-186`

GCHostPay3 decrypts the token and gets:
```python
from_amount = decrypted_data.get('from_amount', 0.0)  # 0.00149302
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)  # 0.0 (not in token!)
estimated_eth_amount = decrypted_data.get('estimated_eth_amount', 0.0)  # 0.0 (not in token!)
```

Then determines payment amount:
```python
if actual_eth_amount > 0:  # False (0.0)
    payment_amount = actual_eth_amount
elif estimated_eth_amount > 0:  # False (0.0)
    payment_amount = estimated_eth_amount
elif from_amount > 0:  # True (0.00149302)
    payment_amount = from_amount  # ❌ Uses WRONG amount (0.00149302)
else:
    abort(400, "Invalid payment amount")
```

**Result:** GCHostPay3 uses `payment_amount = 0.00149302 ETH`

#### 9. ETH Payment to ChangeNOW

GCHostPay3 sends `0.00149302 ETH` to ChangeNOW's payin address `0x233893A8bCF10C5E40C46Ba2A89942cc75e52BdB`

#### 10. ChangeNOW Updates Transaction

- ChangeNOW's payin address receives: `0.00149302 ETH`
- ChangeNOW updates their transaction record: `amountFrom: 0.00149302`
- **Result**: Mismatch between expected (0.001269067) and actual (0.00149302)

## The Bug Location

**File:** `GCHostPay1-10-26/token_manager.py`
**Line:** 238
**Current Code:**
```python
"from_amount": first_amount,  # Uses actual_eth_amount (unadjusted)
```

**Should Be:**
```python
"from_amount": estimated_eth_amount,  # Use fee-adjusted amount
```

## Impact Analysis

### Financial Impact
- **TP Fee Loss**: The platform is losing the TP fee on every instant payout
- **Example Transaction**:
  - TP fee collected: `0.00149302 - 0.001269067 = 0.000223953 ETH` (~15%)
  - But this fee is being sent to ChangeNOW instead of being retained
  - Platform revenue loss: **100% of TP fee per transaction**

### User Impact
- Users might actually receive **MORE** tokens than expected (since ChangeNOW gets more ETH)
- Not a user-facing issue, but a **platform revenue issue**

### Threshold Payout Impact
- **Threshold payouts are NOT affected** by this bug
- Reason: Threshold payouts follow a different flow through GCAccumulator/GCMicroBatchProcessor
- The threshold flow uses old token format with single amount
- The USDT calculation is correct in the accumulator flow

## Solution

### Single-Line Fix in GCHostPay1

**File:** `GCHostPay1-10-26/token_manager.py`
**Line:** 238

**Change From:**
```python
return {
    "unique_id": unique_id,
    "cn_api_id": cn_api_id,
    "from_currency": from_currency,
    "from_network": from_network,
    "from_amount": first_amount,  # ❌ BUG: Uses actual_eth_amount (unadjusted)
    "actual_eth_amount": actual_eth_amount,
    "estimated_eth_amount": estimated_eth_amount,
    "payin_address": payin_address,
    "timestamp": timestamp
}
```

**Change To:**
```python
return {
    "unique_id": unique_id,
    "cn_api_id": cn_api_id,
    "from_currency": from_currency,
    "from_network": from_network,
    "from_amount": estimated_eth_amount,  # ✅ FIX: Use fee-adjusted amount
    "actual_eth_amount": actual_eth_amount,
    "estimated_eth_amount": estimated_eth_amount,
    "payin_address": payin_address,
    "timestamp": timestamp
}
```

### Why This Fix Works

1. **For Instant Payouts (New Format)**:
   - Token has two amounts: actual_eth_amount (0.00149302) and estimated_eth_amount (0.001269067)
   - Fix sets `from_amount = estimated_eth_amount` (0.001269067)
   - This is the correct fee-adjusted amount that matches ChangeNOW swap creation
   - GCHostPay3 will receive `from_amount = 0.001269067` and send the correct amount to ChangeNOW

2. **For Threshold Payouts (Old Format - Backward Compatibility)**:
   - Token has single amount
   - Backward compatibility logic in lines 186-190:
     ```python
     else:
         # Old format - only one amount
         actual_eth_amount = first_amount
         estimated_eth_amount = first_amount
     ```
   - Both `actual_eth_amount` and `estimated_eth_amount` are set to the same value
   - Therefore: `from_amount = estimated_eth_amount = actual_eth_amount = single_amount`
   - **No impact on threshold payouts**

### Alternative Options (Not Recommended)

**Option 2:** Fix in GCSplit1 token packing (swap the order)
- **Location:** `GCSplit1-10-26/token_manager.py:172-173`
- **Issue:** Would break backward compatibility with existing threshold payouts
- **Not recommended**

**Option 3:** Fix in GCHostPay3 logic
- **Location:** `GCHostPay3-10-26/tphp3-10-26.py:174-185`
- **Issue:** GCHostPay3 doesn't receive `actual_eth_amount` or `estimated_eth_amount` in its token
- **Not possible without also modifying GCHostPay1→GCHostPay3 token format**

## Testing Plan

### Pre-Deployment Testing
1. Deploy fixed GCHostPay1 to staging/testnet
2. Create test instant payout with known amounts
3. Verify:
   - ChangeNOW receives fee-adjusted amount (0.001269067)
   - `amountFrom` matches swap creation `fromAmount`
   - TP fee is NOT sent to ChangeNOW
   - Platform retains the TP fee as intended

### Threshold Payout Verification
1. Test threshold payout flow after deploying fix
2. Verify accumulated USDT amounts are correct
3. Confirm no impact on batch conversion process

### Post-Deployment Monitoring
1. Monitor first 10 instant payouts after deployment
2. Check ChangeNOW API responses for `amountFrom` accuracy
3. Verify platform revenue is being retained
4. Compare pre-fix vs post-fix TP fee retention rate

## Deployment Checklist

- [ ] Review and approve fix in GCHostPay1-10-26/token_manager.py
- [ ] Test fix on staging/testnet environment
- [ ] Verify instant payouts work correctly
- [ ] Verify threshold payouts still work correctly (should be unaffected)
- [ ] Deploy to production
- [ ] Monitor logs for first 10 transactions
- [ ] Verify ChangeNOW API responses show correct `amountFrom`
- [ ] Confirm TP fee retention in platform wallet

## Critical Notes

1. **ONLY instant payouts are affected** - threshold payouts work correctly
2. The fix ensures TP fee is **RETAINED by platform**, not sent to ChangeNOW
3. Variable `actual_eth_amount` should be used for **AUDITING ONLY**, not for payment execution
4. Always send `estimated_eth_amount` to ChangeNOW - this is the amount specified in the swap creation
5. **Single-line fix** maintains backward compatibility with threshold payout flow
6. **No database changes required** for this fix
7. **No changes to GCHostPay3** required (the bug is upstream)

## Conclusion

The bug is caused by incorrect assignment of `from_amount` to `first_amount` (actual_eth_amount) instead of `estimated_eth_amount` in GCHostPay1's token decryption logic at line 238.

This single-line fix ensures:
1. ✅ ChangeNOW receives the exact amount specified in swap creation
2. ✅ Platform retains the TP fee as intended
3. ✅ No impact on threshold payout functionality
4. ✅ Backward compatibility maintained
5. ✅ Financial integrity restored

**Estimated Revenue Recovery:** 15% of all instant payout transaction volumes will now be retained as platform fees instead of being sent to ChangeNOW.
