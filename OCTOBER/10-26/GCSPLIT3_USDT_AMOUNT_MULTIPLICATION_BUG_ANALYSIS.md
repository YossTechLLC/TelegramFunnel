# GCSplit3 USDT Amount Multiplication Bug - Critical Analysis

**Date:** 2025-11-04
**Session:** 58
**Service:** GCSplit3-10-26 (triggered by GCSplit1-10-26)
**Severity:** CRITICAL - Payment workflow sending wrong amounts to ChangeNOW
**Status:** ❌ NOT FIXED - Analysis Complete, Awaiting Implementation

---

## Executive Summary

**Critical data flow error** where the calculated **token quantity** (596,726 SHIB) is being sent to ChangeNOW as the **USDT input amount** instead of the actual USDT payment amount (5.48949167 USDT).

**Impact:** ChangeNOW receives requests to swap 596,726 USDT → SHIB instead of 5.48 USDT → SHIB, resulting in massively incorrect transaction amounts (100,000x multiplier).

**Root Cause:** GCSplit1 passes `pure_market_eth_value` (target token quantity) to GCSplit3, which then uses it as the USDT input amount for ChangeNOW API calls.

---

## Problem Description

### Error Observed in Logs

```
2025-11-04 03:29:24.041 EST
💰 [ENDPOINT_2] From: 5.48949167 USDT
💰 [ENDPOINT_2] To (post-fee): 504442.0194895 ETH
✅ [MARKET_CALC] Pure market value: 596726.7004304786 ETH
(True market value of 5.48949167 USDT)
💾 [ENDPOINT_2] Inserting into split_payout_request
NOTE: to_amount = PURE MARKET VALUE (596726.7004304786 ETH)
```

### ChangeNOW API Response

```json
{
    "id": "108737820c2f05",
    "fromCurrency": "usdt",
    "toCurrency": "shib",
    "expectedAmountFrom": 596726.70043,  // ❌ WRONG - Should be 5.48949167
    "expectedAmountTo": 61942343929.62906,  // ❌ WRONG - Calculated from wrong input
    "payinAddress": "0x8cB4aaDDcF98b75261DF9119FDBD6e9422a0c270",
    "payoutAddress": "0x249A83b498acE1177920566CE83CADA0A56F69D8",
    ...
}
```

**Expected ChangeNOW Request:**
- `expectedAmountFrom`: **5.48949167 USDT** ✅
- `expectedAmountTo`: ~500,000 SHIB (estimated based on market rate)

**Actual ChangeNOW Request:**
- `expectedAmountFrom`: **596726.70043 USDT** ❌
- `expectedAmountTo`: ~62 billion SHIB (calculated from wrong input)

**Multiplier:** 108,703x error (596,726 / 5.48 ≈ 108,703)

---

## Root Cause Analysis

### Data Flow Trace

#### 1. **GCWebhook → GCSplit1** (Initial Payment)
```
Original Amount: 5.48949167 USDT
After TP Fee (3%): 4.92873267 USDT (for swapping)
```

#### 2. **GCSplit1 → GCSplit2** (USDT→ETH Estimate Request)
```python
# GCSplit1 encrypts token for GCSplit2
encrypted_token = token_manager.encrypt_gcsplit1_to_gcsplit2_token(
    adjusted_amount_usdt=adjusted_amount_usdt  # ✅ CORRECT: 5.48949167 USDT
)
```

#### 3. **GCSplit2 → GCSplit1** (Estimate Response)
```
From: 5.48949167 USDT
To (post-fee): 504,442.0194895 ETH (actually SHIB, mislabeled)
Deposit Fee: 0.560759 USDT
Withdrawal Fee: 31,328.24127 ETH
```

#### 4. **GCSplit1 Calculates Pure Market Value**
```python
# tps1-10-26.py:463-465
pure_market_eth_value = calculate_pure_market_conversion(
    from_amount_usdt=5.48949167,
    to_amount_eth_post_fee=504442.0194895,
    deposit_fee=0.560759,
    withdrawal_fee=31328.24127
)
# Result: 596726.7004304786 (SHIB quantity)
```

**Purpose of pure_market_eth_value:**
- This is the **token quantity** the client should receive
- It's the "true market value" calculation for database storage
- It's **NOT** a USDT amount!

#### 5. **GCSplit1 → GCSplit3** ❌ **BUG IS HERE!**
```python
# tps1-10-26.py:500-508
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    eth_amount=pure_market_eth_value,  # ❌ BUG: Passing 596726.7004304786 (SHIB quantity)
    actual_eth_amount=actual_eth_amount
)
```

**The Problem:**
- `eth_amount` parameter is set to `pure_market_eth_value` (596,726 SHIB)
- This should be the **ORIGINAL USDT AMOUNT** (5.48949167 USDT)
- GCSplit3 receives this as `usdt_amount` and passes it to ChangeNOW

#### 6. **GCSplit3 Receives Token**
```python
# tps3-10-26.py:112
usdt_amount = decrypted_data['eth_amount']  # ✅ RENAMED: Actually contains USDT amount
# BUT ACTUALLY CONTAINS: 596726.7004304786 (SHIB quantity, not USDT!)
```

**Comment says "Actually contains USDT amount" but it DOESN'T!**
- It contains `pure_market_eth_value` from GCSplit1
- Which is the calculated SHIB quantity (596,726)
- NOT the USDT amount (5.48)

#### 7. **GCSplit3 → ChangeNOW** ❌ **WRONG AMOUNT SENT!**
```python
# tps3-10-26.py:129-136
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="usdt",
    to_currency=payout_currency,
    from_amount=usdt_amount,  # ❌ BUG: Sending 596726.7004304786 instead of 5.48949167
    address=wallet_address,
    from_network="eth",
    to_network=payout_network,
    user_id=str(user_id)
)
```

**ChangeNow API receives:**
```json
{
    "fromCurrency": "usdt",
    "toCurrency": "shib",
    "fromAmount": "596726.70043",  // ❌ WRONG: Should be "5.48949167"
    ...
}
```

---

## Why This Bug Exists

### Misunderstanding of `pure_market_eth_value`

The `pure_market_eth_value` calculation was added to store the **client's token quantity** in the database for accounting purposes. However, this value was **incorrectly reused** as the input amount for the next ChangeNOW swap.

**What `pure_market_eth_value` represents:**
- **Output token quantity** that the client should receive
- Calculated by back-engineering ChangeNOW's fees
- Used for database storage in `split_payout_request.to_amount`

**What GCSplit3 needs:**
- **Input USDT amount** for the USDT→ClientCurrency swap
- Should be the **original subscription price** after TP fee
- Example: 5.48949167 USDT

### Variable Naming Confusion

The token field is called `eth_amount` but:
1. In GCSplit1, it's set to `pure_market_eth_value` (which is SHIB quantity)
2. In GCSplit3, it's renamed to `usdt_amount` (but still contains SHIB quantity)
3. Comment says "Actually contains USDT amount" but this is FALSE

---

## Impact Analysis

### Current Behavior (❌ BROKEN)

1. User pays **$5.48** subscription
2. GCSplit1 calculates token quantity: **596,726 SHIB**
3. GCSplit1 sends **596,726** to GCSplit3 (thinking it's USDT)
4. GCSplit3 asks ChangeNOW to swap **596,726 USDT → SHIB**
5. ChangeNOW expects ~**62 billion SHIB** output
6. Platform wallet receives deposit request for **596,726 USDT** (which we don't have!)

**Financial Impact:**
- Attempting to swap 100,000x more than available
- ChangeNOW transaction will **fail** (insufficient funds at payin address)
- Client never receives their SHIB payout
- Platform never receives the ETH we thought we'd swap

### Expected Behavior (✅ CORRECT)

1. User pays **$5.48** subscription
2. GCSplit1 calculates token quantity: **596,726 SHIB** (for database only)
3. GCSplit1 sends **5.48 USDT** to GCSplit3
4. GCSplit3 asks ChangeNOW to swap **5.48 USDT → SHIB**
5. ChangeNOW calculates output: ~**596,726 SHIB**
6. Platform wallet deposits **5.48 USDT** to ChangeNOW
7. Client receives **~596,726 SHIB** at their wallet

---

## Solution Design

### Fix Required in GCSplit1

**File:** `GCSplit1-10-26/tps1-10-26.py`
**Location:** Line 500-508 (encrypt_gcsplit1_to_gcsplit3_token call)

**Current Code (WRONG):**
```python
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    eth_amount=pure_market_eth_value,  # ❌ WRONG: Token quantity (596726 SHIB)
    actual_eth_amount=actual_eth_amount
)
```

**Fixed Code (CORRECT):**
```python
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    eth_amount=from_amount_usdt,  # ✅ CORRECT: Original USDT amount (5.48949167)
    actual_eth_amount=actual_eth_amount
)
```

### Why This Fix Works

1. **GCSplit1** extracts `from_amount_usdt` from the GCSplit2 response (line 451)
2. This value is the **original USDT payment amount** (5.48949167 USDT)
3. By passing `from_amount_usdt` instead of `pure_market_eth_value`:
   - GCSplit3 receives the correct USDT amount
   - ChangeNOW creates a swap with correct input (5.48 USDT → ~596,726 SHIB)
   - Platform deposits the correct amount to ChangeNOW
   - Client receives the correct SHIB quantity

### Variable Available in Scope

Looking at line 451 in GCSplit1:
```python
from_amount_usdt = decrypted_data['from_amount_usdt']
```

This variable is **in scope** at line 500, so we can use it directly.

---

## Verification of Other Potential Issues

### Does This Bug Affect Other Services?

**Checked:**
1. ✅ **GCSplit2-10-26**: Only handles USDT→ETH estimates, doesn't create ChangeNOW transactions
2. ✅ **GCHostPay**: Receives ETH amounts (not affected by USDT conversion)
3. ✅ **GCBatchProcessor → GCSplit1**: Uses `amount_usdt` directly (line 804), not affected
4. ✅ **GCMicroBatchProcessor → GCSplit3**: Creates ChangeNOW directly, not using GCSplit1 flow

**Conclusion:** This bug is **isolated to the standard payment flow** (GCWebhook → GCSplit1 → GCSplit3).

### Does This Affect ETH→USDT Swaps (Threshold Payouts)?

**Checked:** GCSplit3 `/eth-to-usdt` endpoint (line 234-378)

```python
# Line 299
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="eth",
    to_currency="usdt",
    from_amount=str(eth_amount),  # ✅ CORRECT: Uses eth_amount directly
    ...
)
```

**Conclusion:** Threshold payout flow is **NOT AFFECTED** by this bug.

---

## Testing Strategy

### Pre-Fix Test (Reproduce Bug)

1. **Trigger a payment** with low-value token (SHIB, DOGE, PEPE)
2. **Check GCSplit3 logs** for ChangeNOW API request
3. **Verify bug:** `expectedAmountFrom` is large token quantity instead of USDT amount
4. **Check ChangeNOW transaction status:** Should fail due to insufficient USDT deposit

### Post-Fix Test (Verify Correctness)

1. **Deploy fixed GCSplit1-10-26**
2. **Trigger same payment** with low-value token
3. **Check GCSplit3 logs** for ChangeNOW API request
4. **Verify fix:** `expectedAmountFrom` is correct USDT amount (5.48)
5. **Check ChangeNOW transaction status:** Should succeed with correct amounts

### Test Case Matrix

| Test Case | Input USDT | Target Token | Expected `expectedAmountFrom` | Expected Token Quantity |
|-----------|------------|--------------|-------------------------------|-------------------------|
| Small BTC | 10 USDT | BTC | 10 USDT ✅ | ~0.00016 BTC |
| Small ETH | 10 USDT | ETH | 10 USDT ✅ | ~0.0033 ETH |
| Large DOGE | 10 USDT | DOGE | 10 USDT ✅ | ~100 DOGE |
| Large SHIB | 10 USDT | SHIB | 10 USDT ✅ | ~1,000,000 SHIB |
| Large PEPE | 10 USDT | PEPE | 10 USDT ✅ | ~10,000,000 PEPE |

---

## Implementation Checklist

### 1. Code Changes

- [ ] **GCSplit1-10-26/tps1-10-26.py**
  - [ ] Line 507: Change `eth_amount=pure_market_eth_value` to `eth_amount=from_amount_usdt`
  - [ ] Verify `from_amount_usdt` is in scope (extracted at line 451)
  - [ ] Add comment explaining the fix

### 2. Variable Naming Cleanup (Optional but Recommended)

- [ ] **TokenManager** (if feasible)
  - [ ] Rename `eth_amount` parameter to `usdt_amount` in `encrypt_gcsplit1_to_gcsplit3_token()`
  - [ ] Update token structure to use clearer naming
  - [ ] Update decryption in `decrypt_gcsplit1_to_gcsplit3_token()`

- [ ] **GCSplit3-10-26/tps3-10-26.py**
  - [ ] Update comment on line 112 to reflect correct data type
  - [ ] Consider renaming variable for clarity

### 3. Database Impact

- [ ] **No database changes required** ✅
  - `split_payout_request.to_amount` still stores `pure_market_eth_value` (correct)
  - `split_payout_request.from_amount` still stores `from_amount_usdt` (correct)
  - No migration needed

### 4. Deployment

- [ ] Build new GCSplit1-10-26 Docker image
- [ ] Deploy to Cloud Run: `gcsplit1-10-26`
- [ ] Monitor logs for first few transactions
- [ ] Verify ChangeNOW API requests have correct amounts

### 5. Testing

- [ ] Test with SHIB payout (low-value token)
- [ ] Test with BTC payout (high-value token)
- [ ] Test with DOGE payout (medium-value token)
- [ ] Verify all ChangeNOW transactions succeed
- [ ] Verify clients receive correct token quantities

### 6. Documentation

- [ ] Update PROGRESS.md (Session 58)
- [ ] Update DECISIONS.md (Data flow correction)
- [ ] Update BUGS.md (Bug fix logged)
- [ ] Update this document with "FIXED" status

---

## Prevention Strategy

### Code Review Guidelines

1. **Variable Naming Convention:**
   - Use semantic names that reflect data type (e.g., `usdt_amount`, `token_quantity`)
   - Avoid generic names like `eth_amount` when the value isn't ETH

2. **Token Field Validation:**
   - When encrypting tokens, add assertions to verify data types
   - Example: `assert from_amount_usdt < 1000000, "USDT amount too large, possible confusion with token quantity"`

3. **Logging Best Practices:**
   - Always log both USDT input and token output in the same log statement
   - Example: `print(f"Creating swap: {usdt_in} USDT → {token_out} {currency}")`

4. **Unit Tests:**
   - Test edge cases with low-value tokens (SHIB, PEPE)
   - Assert that ChangeNOW `from_amount` < reasonable threshold (e.g., < $100,000)

### Monitoring Alerts

- [ ] Alert on ChangeNOW API `expectedAmountFrom` > $10,000
- [ ] Alert on ChangeNOW transaction failures due to insufficient funds
- [ ] Alert on large discrepancy between database `from_amount` and ChangeNOW `fromAmount`

---

## Related Issues

### Previous Similar Issues

1. **NUMERIC Precision Overflow (Session 57)**
   - Also involved SHIB token quantities
   - Also caused by confusion between USDT amounts and token quantities
   - Fixed by increasing database precision

2. **GCWebhook1 `outcome_amount` Confusion**
   - Similar issue where multiple currencies were passed through single field
   - Fixed by adding explicit amount tracking for each currency type

### Root Cause Pattern

**Common Thread:** Reusing calculated values for purposes they weren't designed for.

**Solution Pattern:**
- Keep intermediate calculations (like `pure_market_eth_value`) separate
- Always pass **original input amounts** to downstream services
- Let each service perform its own calculations

---

## Conclusion

**Severity:** CRITICAL - Payment workflow completely broken for low-value tokens

**Impact:** 100% of USDT→ClientCurrency swaps fail due to incorrect ChangeNOW API requests

**Fix Complexity:** LOW - Single line change in GCSplit1

**Risk:** NONE - Fix is straightforward, well-understood, and isolated

**Timeline:**
- Analysis: ✅ Complete (Session 58)
- Implementation: ⏳ Pending user approval
- Testing: ⏳ Pending deployment
- Deployment: ⏳ Pending testing

**Status:** Ready for implementation. Awaiting user confirmation to proceed with fix.

---

## Appendix: Variable Trace Table

| Service | Variable Name | Value Example | Semantic Meaning | Correct Usage |
|---------|---------------|---------------|------------------|---------------|
| GCWebhook | `subscription_price` | 5.48949167 | Original USDT payment | ✅ Pass to GCSplit1 |
| GCSplit1 | `adjusted_amount_usdt` | 5.32560472 | USDT after TP fee | ✅ Pass to GCSplit2 |
| GCSplit2 | `from_amount_usdt` | 5.48949167 | Original USDT (restored) | ✅ Return to GCSplit1 |
| GCSplit1 | `from_amount_usdt` | 5.48949167 | Original USDT amount | ✅ Pass to GCSplit3 |
| GCSplit1 | `pure_market_eth_value` | 596726.70043 | **Token quantity (SHIB)** | ❌ **DO NOT** pass to GCSplit3 |
| GCSplit3 | `usdt_amount` | ❌ 596726.70043 | Should be USDT, but receives SHIB | ❌ BUG |
| GCSplit3 | `usdt_amount` | ✅ 5.48949167 | **AFTER FIX:** Correct USDT | ✅ Pass to ChangeNOW |

---

**Author:** Claude Code (Session 58)
**Last Updated:** 2025-11-04
**Next Action:** Implement fix in GCSplit1-10-26
