# GCSplit USDT→Client Currency Bug Analysis

**Date**: 2025-11-03
**Priority**: P0 - CRITICAL
**Status**: Analysis Complete, Fix Pending

---

## Problem Summary

The second ChangeNow swap in batch payouts is being created with **ETH→ClientCurrency** instead of **USDT→ClientCurrency**, causing the wrong currency to be used for the client payout.

### Expected Behavior:
1. **First swap**: ETH → USDT (accumulator threshold conversion) ✅
2. **Second swap**: USDT → ClientCurrency (e.g., SHIB) ❌

### Actual Behavior:
1. **First swap**: ETH → USDT ✅ Successfully completed
2. **Second swap**: ETH → ClientCurrency ❌ Wrong input currency!

### Evidence from User Transaction Data:

**First Swap (ETH → USDT)** - ✅ SUCCESS:
```json
{
    "id": "613c822e844358",
    "status": "finished",
    "fromCurrency": "eth",
    "toCurrency": "usdt",
    "amountFrom": 0.0007573,
    "amountTo": 1.832669,
    "payinAddress": "0xa41cAf600B932D9290bF2BC9dc30476C97F107F3",
    "payoutAddress": "0x16bf79087671ff98c0b63a0b1970dbd5c4231bc4"
}
```

**Second Swap (ETH → SHIB)** - ❌ WRONG:
```json
{
    "id": "0bd9c09b68484c",
    "status": "waiting",
    "fromCurrency": "eth",        // ❌ Should be "usdt"
    "toCurrency": "shib",         // ✅ Correct
    "expectedAmountFrom": 0.00063941,  // ❌ ETH amount
    "expectedAmountTo": 188663.9497643,
    "payinAddress": "0x349254B0043502EA03cFAD88f708166ea42d3BBD",
    "payoutAddress": "0x249A83b498acE1177920566CE83CADA0A56F69D8"
}
```

**Issue**: The second swap is expecting ETH as input instead of USDT!

---

## Root Cause Analysis

### Bug Location 1: GCSplit2-10-26 (USDT Estimate Service)

**File**: `/10-26/GCSplit2-10-26/tps2-10-26.py`
**Line**: 131
**Function**: `process_usdt_eth_estimate()`

**Incorrect Code**:
```python
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency="usdt",
    to_currency="eth",      # ❌ BUG: Hardcoded to "eth"
    from_network="eth",
    to_network="eth",       # ❌ BUG: Hardcoded to "eth"
    from_amount=str(adjusted_amount_usdt),
    flow="standard",
    type_="direct"
)
```

**Problem**:
- GCSplit2 is hardcoded to convert USDT→ETH
- It receives `payout_currency` and `payout_network` from GCSplit1 (line 111-112)
- But it IGNORES these and uses "eth" instead

**Expected Code**:
```python
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency="usdt",
    to_currency=payout_currency,  # ✅ Use actual target currency
    from_network="eth",
    to_network=payout_network,    # ✅ Use actual target network
    from_amount=str(adjusted_amount_usdt),
    flow="standard",
    type_="direct"
)
```

---

### Bug Location 2: GCSplit3-10-26 (Swap Creation Service)

**File**: `/10-26/GCSplit3-10-26/tps3-10-26.py`
**Line**: 129-137
**Function**: `process_eth_client_swap()`

**Incorrect Code**:
```python
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="eth",  # ❌ BUG: Hardcoded to "eth"
    to_currency=payout_currency,
    from_amount=eth_amount,  # ❌ Misleading variable name
    address=wallet_address,
    from_network="eth",
    to_network=payout_network,
    user_id=str(user_id)
)
```

**Problem**:
- GCSplit3 is hardcoded to create swaps with `from_currency="eth"`
- The variable `eth_amount` is misleading - it actually contains the USDT amount
- This causes ChangeNow to create an ETH→ClientCurrency swap instead of USDT→ClientCurrency

**Expected Code**:
```python
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="usdt",  # ✅ Correct source currency
    to_currency=payout_currency,
    from_amount=eth_amount,  # ✅ Actually contains USDT amount (rename variable!)
    address=wallet_address,
    from_network="eth",
    to_network=payout_network,
    user_id=str(user_id)
)
```

---

## Impact Assessment

### Systems Affected:
1. ✅ **Instant Conversion Flow** (GCWebhook1 → GCSplit1 → GCSplit2 → GCSplit3) - NOT AFFECTED
   - This flow uses NowPayments which provides ETH directly
   - GCSplit services convert ETH→ClientCurrency correctly in this case

2. ❌ **Batch Payout Flow** (GCBatchProcessor → GCSplit1 → GCSplit2 → GCSplit3) - AFFECTED
   - First swap (ETH→USDT) completes successfully
   - Second swap fails because it expects ETH input instead of USDT

3. ❌ **Threshold Payout Flow** (if using similar logic) - LIKELY AFFECTED

### User Impact:
- **Critical**: Batch payouts are completely broken
- Users accumulating payments will never receive payouts
- USDT sits in host wallet but cannot be converted to client currencies

---

## Data Flow Analysis

### Correct Flow (Expected):

```
GCBatchProcessor
    ↓ (batch payout trigger)
GCSplit1 /batch-payout
    ↓ (token with: amount_usdt, payout_currency, payout_network)
GCSplit2 /
    ↓ (should estimate: USDT → payout_currency)
    ✅ Returns: from_amount_usdt, to_amount_client_currency
GCSplit1 /usdt-eth-estimate
    ↓ (token with: from_amount_usdt, to_amount, payout_currency)
GCSplit3 /
    ↓ (should create swap: USDT → payout_currency)
    ✅ Creates ChangeNow swap with correct currencies
GCHostPay (via GCSplit1)
    ✅ Executes USDT payment to ChangeNow
```

### Actual Flow (Current Bug):

```
GCBatchProcessor
    ↓ (batch payout trigger)
GCSplit1 /batch-payout
    ↓ (token with: amount_usdt, payout_currency, payout_network)
GCSplit2 /
    ↓ (WRONG: estimates USDT → ETH instead of USDT → payout_currency)
    ❌ Returns: from_amount_usdt, to_amount_eth
GCSplit1 /usdt-eth-estimate
    ↓ (token with: from_amount_usdt=1.832669, eth_amount=X, payout_currency=shib)
GCSplit3 /
    ↓ (WRONG: creates swap ETH → payout_currency instead of USDT → payout_currency)
    ❌ Creates ChangeNow swap with from_currency="eth"
GCHostPay (via GCSplit1)
    ❌ Would execute ETH payment (but no ETH available!)
```

---

## Variable Naming Issues

### Misleading Variable Names:

1. **GCSplit2 Service Name**: "USDT→ETH Estimator"
   - ❌ Misleading: Should be "USDT→ClientCurrency Estimator"
   - Service is supposed to estimate conversion to ANY currency, not just ETH

2. **GCSplit3 Variable**: `eth_amount` (line 112)
   - ❌ Misleading: Actually contains USDT amount
   - Should be renamed to `usdt_amount` or `from_amount_usdt`

3. **GCSplit1 Function**: `receive_usdt_eth_estimate()` (line 403)
   - ❌ Misleading: Should be `receive_usdt_client_currency_estimate()`

---

## Fix Implementation Plan

### Phase 1: Critical Fixes (P0)

#### 1.1. Fix GCSplit2 Estimate Logic
**File**: `GCSplit2-10-26/tps2-10-26.py`

**Changes Required**:
```python
# Line 129-137: Update ChangeNow API call
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency="usdt",
    to_currency=payout_currency,  # ✅ FIXED: Use actual target currency
    from_network="eth",
    to_network=payout_network,    # ✅ FIXED: Use actual target network
    from_amount=str(adjusted_amount_usdt),
    flow="standard",
    type_="direct"
)

# Line 152-156: Update logging
print(f"✅ [ENDPOINT] ChangeNow estimate received")
print(f"💰 [ENDPOINT] From: {from_amount} USDT")
print(f"💰 [ENDPOINT] To: {to_amount} {payout_currency.upper()} (post-fee)")  # ✅ FIXED
print(f"📊 [ENDPOINT] Deposit fee: {deposit_fee}")
print(f"📊 [ENDPOINT] Withdrawal fee: {withdrawal_fee}")
```

**Impact**: Fixes estimate calculations to use correct target currency

---

#### 1.2. Fix GCSplit3 Swap Creation
**File**: `GCSplit3-10-26/tps3-10-26.py`

**Changes Required**:
```python
# Line 112: Rename misleading variable
usdt_amount = decrypted_data['eth_amount']  # ✅ RENAMED for clarity
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)

# Line 118-120: Update logging
print(f"💰 [ENDPOINT] USDT Amount: {usdt_amount}")  # ✅ FIXED
print(f"💎 [ENDPOINT] ACTUAL ETH (from NowPayments): {actual_eth_amount}")
print(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")

# Line 129-137: Fix swap creation
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="usdt",  # ✅ FIXED: Correct source currency
    to_currency=payout_currency,
    from_amount=usdt_amount,  # ✅ FIXED: Renamed variable
    address=wallet_address,
    from_network="eth",
    to_network=payout_network,
    user_id=str(user_id)
)

# Line 162-163: Update logging
print(f"💰 [ENDPOINT] From: {api_from_amount} USDT")  # ✅ FIXED
print(f"💰 [ENDPOINT] To: {api_to_amount} {api_to_currency.upper()}")
```

**Impact**: Fixes swap creation to use USDT as source currency

---

### Phase 2: Code Quality Improvements (P1)

#### 2.1. Rename GCSplit2 Service
**Files**:
- `GCSplit2-10-26/tps2-10-26.py` (line 23)
- Documentation files

**Changes**:
```python
# Line 23: Update service description
print(f"🚀 [APP] Initializing GCSplit2-10-26 USDT→ClientCurrency Estimator Service")

# Line 224: Update health check
"service": "GCSplit2-10-26 USDT→ClientCurrency Estimator",
```

---

#### 2.2. Rename GCSplit1 Function and Variables
**File**: `GCSplit1-10-26/tps1-10-26.py`

**Changes**:
```python
# Line 403: Rename function
@app.route("/usdt-client-estimate", methods=["POST"])  # ✅ RENAMED endpoint
def receive_usdt_client_currency_estimate():  # ✅ RENAMED function
    """
    Endpoint for receiving USDT→ClientCurrency estimate response from GCSplit2.

    Flow:
    1. Decrypt token from GCSplit2
    2. Calculate pure market conversion value
    3. Insert into split_payout_request table
    4. Encrypt token for GCSplit3
    5. Enqueue Cloud Task to GCSplit3

    Returns:
        JSON response with status
    """
    # ... implementation
```

**Note**: Endpoint rename requires updating GCSplit2 callback URL

---

### Phase 3: Testing & Validation (P0)

#### 3.1. Unit Testing
- [ ] Test GCSplit2 with various payout currencies (SHIB, XMR, BTC)
- [ ] Test GCSplit3 swap creation with USDT source
- [ ] Verify token encryption/decryption maintains correct currency info

#### 3.2. Integration Testing
- [ ] Test complete batch payout flow end-to-end
- [ ] Verify ChangeNow API accepts USDT→SHIB swaps
- [ ] Confirm correct amounts calculated at each step

#### 3.3. Production Validation
- [ ] Monitor logs for correct currency in swap creation
- [ ] Verify actual ChangeNow transactions use USDT source
- [ ] Confirm client payouts execute successfully

---

## Deployment Checklist

### Pre-Deployment:
- [ ] Read and verify all affected files
- [ ] Create backup of current code
- [ ] Update PROGRESS.md with session summary
- [ ] Update DECISIONS.md with architecture decision
- [ ] Update BUGS.md with bug details

### Deployment Order:
1. [ ] Deploy GCSplit2-10-26 (estimate fix)
2. [ ] Deploy GCSplit3-10-26 (swap creation fix)
3. [ ] Verify health checks pass
4. [ ] Monitor logs for correct behavior

### Post-Deployment:
- [ ] Trigger test batch payout
- [ ] Monitor ChangeNow transaction creation
- [ ] Verify swap uses USDT→ClientCurrency
- [ ] Confirm client receives payout

---

## Potential Edge Cases

### 1. Instant Conversion Flow
**Question**: Does this fix break instant conversions?
**Answer**: NO - Instant conversions use NowPayments with ETH input
**Reason**: GCSplit2/3 are only called for batch payouts where USDT is the input

### 2. Threshold Payouts
**Question**: Are threshold payouts affected?
**Answer**: POSSIBLY - Need to verify if threshold payouts use GCSplit2/3
**Action**: Check GCAccumulator flow and confirm currency handling

### 3. Multiple Payout Currencies
**Question**: Will this work for all client payout currencies?
**Answer**: YES - As long as ChangeNow supports USDT→ClientCurrency pairs
**Action**: Verify ChangeNow API supports USDT→SHIB, USDT→XMR, etc.

### 4. Fee Calculations
**Question**: Do fee calculations change with USDT source?
**Answer**: NO - ChangeNow fee structure is the same
**Action**: Monitor actual fees in production to confirm

---

## Related Issues

### Issue 1: Variable Naming Consistency
**Description**: Many variables named `eth_amount` actually contain USDT amounts
**Priority**: P1
**Fix**: Rename variables systematically across all services

### Issue 2: Service Name Accuracy
**Description**: GCSplit2 is named "USDT→ETH Estimator" but should handle any currency
**Priority**: P2
**Fix**: Update service descriptions and documentation

### Issue 3: Endpoint Naming
**Description**: Endpoint `/usdt-eth-estimate` is misleading
**Priority**: P2
**Fix**: Consider renaming to `/usdt-client-estimate` (requires callback URL update)

---

## Architecture Decision

### Decision: Keep Two-Swap Architecture
**Rationale**:
- ✅ Separates accumulation (ETH→USDT) from payout (USDT→ClientCurrency)
- ✅ USDT is stable intermediate currency
- ✅ Reduces volatility risk for accumulated funds

**Alternative Considered**: Single swap (ETH→ClientCurrency directly)
- ❌ Higher volatility exposure during accumulation
- ❌ More complex fee calculations
- ❌ Harder to track accumulated value

**Chosen Solution**: Fix existing two-swap architecture
- ✅ Maintains stability of USDT intermediate
- ✅ Simple fix (2 services, ~10 lines changed)
- ✅ No database schema changes needed

---

## Success Criteria

### Fix is Successful When:
1. ✅ GCSplit2 estimates USDT→ClientCurrency correctly
2. ✅ GCSplit3 creates ChangeNow swap with fromCurrency="usdt"
3. ✅ ChangeNow swap shows correct currencies in transaction data
4. ✅ Client receives correct amount in payout currency
5. ✅ No errors in logs during batch payout execution

### Monitoring Metrics:
- **GCSplit2 Logs**: Check `to_currency` matches `payout_currency`
- **GCSplit3 Logs**: Check `from_currency="usdt"` in swap creation
- **ChangeNow API**: Verify transaction JSON shows correct currencies
- **Database**: Check `split_payout_request.from_currency="usdt"`
- **User Wallets**: Verify client receives payout in correct currency

---

## Timeline Estimate

### Development: ~30 minutes
- 10 min: Update GCSplit2 (lines 131, 132, 154)
- 10 min: Update GCSplit3 (lines 112, 118, 130, 162)
- 10 min: Code review and verification

### Testing: ~20 minutes
- 10 min: Build and deploy both services
- 10 min: Monitor test batch payout execution

### Validation: ~10 minutes
- 5 min: Verify ChangeNow transaction data
- 5 min: Check logs for correct behavior

**Total Time**: ~60 minutes

---

## Next Steps

1. User approval of fix plan
2. Implement Phase 1 fixes (GCSplit2 + GCSplit3)
3. Build and deploy updated services
4. Monitor production batch payout
5. Document results in PROGRESS.md

---

**Document Version**: 1.0
**Last Updated**: 2025-11-03
**Author**: Claude Code Session 53
