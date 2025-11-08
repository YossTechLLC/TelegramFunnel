# GCSPLIT1 ENDPOINT_2 KEYERROR FIX CHECKLIST

**Status:** CRITICAL BUG - NAMING INCONSISTENCY
**Date:** 2025-11-07
**Issue:** KeyError on `'to_amount_eth_post_fee'` in GCSplit1 endpoint_2
**Error Location:** `https://gcsplit1-10-26-291176869049.us-central1.run.app/endpoint_2`

---

## Executive Summary

### Root Cause
**Dictionary key mismatch** between GCSplit1's decrypt method and endpoint code:

- **GCSplit1 decrypt returns:** `"to_amount_post_fee"` (generic name for dual-currency)
- **GCSplit1 endpoint expects:** `"to_amount_eth_post_fee"` (legacy name from ETH-only era)

### Error Flow
```
1. GCSplit2 encrypts token with field: to_amount_eth_post_fee ✅
2. GCSplit1 decrypts token successfully ✅
3. GCSplit1 decrypt returns dictionary with key: "to_amount_post_fee" ✅
4. GCSplit1 endpoint tries to access: decrypted_data['to_amount_eth_post_fee'] ❌ KeyError!
```

### Impact
- ✅ **Instant payout mode:** BLOCKED - Cannot process payments
- ✅ **Threshold payout mode:** BLOCKED - Same token flow affected
- ❌ **Critical:** Payment processing completely stopped at GCSplit1→GCSplit3 handoff

---

## Technical Analysis

### Evidence from Error Log
```
2025-11-07 11:18:36.849 EST
✅ [TOKEN_DEC] Estimate response decrypted successfully  ← Token decryption WORKS
🎯 [TOKEN_DEC] Payout Mode: instant, Swap Currency: eth  ← Fields extracted correctly
💰 [TOKEN_DEC] ACTUAL ETH extracted: 0.0010582  ← All data present
❌ [ENDPOINT_2] Unexpected error: 'to_amount_eth_post_fee'  ← KeyError accessing wrong key
```

**Conclusion:** Token decryption is successful. The bug is in the endpoint code accessing the decrypted data.

### File Analysis

#### GCSplit1 Decrypt Method
**File:** `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py`
**Method:** `decrypt_gcsplit2_to_gcsplit1_token()`
**Line 466:** Returns dictionary with key `"to_amount_post_fee"` ✅ CORRECT (generic name)

```python
return {
    "user_id": user_id,
    "closed_channel_id": closed_channel_id,
    "wallet_address": wallet_address,
    "payout_currency": payout_currency,
    "payout_network": payout_network,
    "from_amount": from_amount,
    "to_amount_post_fee": to_amount_post_fee,  # ✅ GENERIC NAME (not "eth")
    "deposit_fee": deposit_fee,
    "withdrawal_fee": withdrawal_fee,
    "swap_currency": swap_currency,
    "payout_mode": payout_mode,
    "actual_eth_amount": actual_eth_amount
}
```

#### GCSplit1 Endpoint Code
**File:** `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`
**Line 476:** Tries to access wrong key ❌ INCORRECT

```python
from_amount = decrypted_data['from_amount']  # ✅ Works
to_amount_eth_post_fee = decrypted_data['to_amount_eth_post_fee']  # ❌ KeyError!
```

### Why the Name "to_amount_post_fee" is More Accurate

**Legacy Name:** `to_amount_eth_post_fee`
- Implies value is always in ETH
- Misleading for threshold mode (USDT → ClientCurrency)

**New Generic Name:** `to_amount_post_fee`
- Accurate for both payout modes
- Represents output amount in target currency (post-fee)
- Instant mode: ETH → ClientCurrency → value is ClientCurrency amount
- Threshold mode: USDT → ClientCurrency → value is ClientCurrency amount

---

## Solution Strategy

### Option A: Update Endpoint Code (RECOMMENDED) ✅
- Change endpoint code to access `'to_amount_post_fee'`
- Matches decrypt method return value
- Maintains dual-currency naming consistency
- Minimal changes (only GCSplit1 endpoint)

### Option B: Update Decrypt Method (NOT RECOMMENDED) ❌
- Change decrypt method to return `'to_amount_eth_post_fee'`
- Restores legacy name
- Misleading for threshold mode
- Contradicts dual-currency architecture

**Selected Strategy:** Option A - Update endpoint code to use generic naming

---

## Implementation Checklist

### Phase 1: Identify All Affected Lines in GCSplit1 ✅

- [ ] **1.1** Map all occurrences of `to_amount_eth_post_fee` in GCSplit1
  - File: `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`
  - Lines to update:
    - Line 199: Function signature for `calculate_pure_market_conversion()`
    - Line 201: Function parameter
    - Line 227: Print statement
    - Line 232: Calculation
    - Line 239: Fallback return
    - Line 248: Print statement
    - Line 255: Fallback return
    - Line 476: **CRITICAL** - Dictionary key access (causes KeyError)
    - Line 487: Print statement
    - Line 492: Function call argument

- [ ] **1.2** Verify no impact on token encryption to GCSplit3
  - Line 535 passes `eth_amount=from_amount` (not affected by this change)
  - Token structure for GCSplit1→GCSplit3 remains unchanged ✅

### Phase 2: Code Changes in GCSplit1 ✅

#### File: `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

- [ ] **2.1** Update function signature (Lines 199-204)

**BEFORE:**
```python
def calculate_pure_market_conversion(
    from_amount_usdt: float,
    to_amount_eth_post_fee: float,
    deposit_fee: float,
    withdrawal_fee: float
) -> float:
```

**AFTER:**
```python
def calculate_pure_market_conversion(
    from_amount: float,  # ✅ Generic name (ETH or USDT)
    to_amount_post_fee: float,  # ✅ Generic name (ClientCurrency)
    deposit_fee: float,
    withdrawal_fee: float
) -> float:
```

- [ ] **2.2** Update function body (Lines 225-255)

Replace all occurrences of:
- `from_amount_usdt` → `from_amount`
- `to_amount_eth_post_fee` → `to_amount_post_fee`

**Example (Line 227):**
```python
# BEFORE
print(f"   To Amount (post-fee): {to_amount_eth_post_fee} ETH")

# AFTER
print(f"   To Amount (post-fee): {to_amount_post_fee}")  # Currency-agnostic
```

**Example (Lines 232-233):**
```python
# BEFORE
usdt_swapped = from_amount_usdt - deposit_fee
eth_before_withdrawal = to_amount_eth_post_fee + withdrawal_fee

# AFTER
amount_swapped = from_amount - deposit_fee
amount_before_withdrawal = to_amount_post_fee + withdrawal_fee
```

**Example (Line 237-240):**
```python
# BEFORE
if usdt_swapped <= 0:
    print(f"❌ [MARKET_CALC] Invalid usdt_swapped: {usdt_swapped}")
    return to_amount_eth_post_fee

# AFTER
if amount_swapped <= 0:
    print(f"❌ [MARKET_CALC] Invalid amount_swapped: {amount_swapped}")
    return to_amount_post_fee
```

**Example (Line 241-243):**
```python
# BEFORE
market_rate = eth_before_withdrawal / usdt_swapped
pure_market_value = from_amount_usdt * market_rate

# AFTER
market_rate = amount_before_withdrawal / amount_swapped
pure_market_value = from_amount * market_rate
```

**Example (Line 248):**
```python
# BEFORE
print(f"   Difference from post-fee: +{pure_market_value - to_amount_eth_post_fee} ETH")

# AFTER
print(f"   Difference from post-fee: +{pure_market_value - to_amount_post_fee}")
```

**Example (Line 255):**
```python
# BEFORE
return to_amount_eth_post_fee

# AFTER
return to_amount_post_fee
```

- [ ] **2.3** Update endpoint_2 data extraction (Line 476) **← CRITICAL FIX**

**BEFORE:**
```python
from_amount = decrypted_data['from_amount']
to_amount_eth_post_fee = decrypted_data['to_amount_eth_post_fee']  # ❌ KeyError
```

**AFTER:**
```python
from_amount = decrypted_data['from_amount']
to_amount_post_fee = decrypted_data['to_amount_post_fee']  # ✅ Correct key
```

- [ ] **2.4** Update endpoint_2 print statement (Line 487)

**BEFORE:**
```python
print(f"💰 [ENDPOINT_2] To (post-fee): {to_amount_eth_post_fee} {payout_currency.upper()}")
```

**AFTER:**
```python
print(f"💰 [ENDPOINT_2] To (post-fee): {to_amount_post_fee} {payout_currency.upper()}")
```

- [ ] **2.5** Update function call (Line 491-493)

**BEFORE:**
```python
pure_market_value = calculate_pure_market_conversion(
    from_amount, to_amount_eth_post_fee, deposit_fee, withdrawal_fee
)
```

**AFTER:**
```python
pure_market_value = calculate_pure_market_conversion(
    from_amount, to_amount_post_fee, deposit_fee, withdrawal_fee
)
```

### Phase 3: Verify No Impact on GCSplit2/GCSplit3 ✅

- [ ] **3.1** Verify GCSplit2 remains unchanged
  - GCSplit2's encrypt method uses parameter `to_amount_eth_post_fee` internally ✅
  - GCSplit2's decrypt method returns `"to_amount_eth_post_fee"` key ✅
  - NO CHANGES NEEDED in GCSplit2 (internal consistency maintained)

- [ ] **3.2** Verify GCSplit3 remains unchanged
  - GCSplit3's decrypt method uses `to_amount_eth_post_fee` internally ✅
  - GCSplit3 receives token from GCSplit1 with field `eth_amount` (not affected) ✅
  - NO CHANGES NEEDED in GCSplit3 (internal consistency maintained)

- [ ] **3.3** Verify GCSplit1→GCSplit3 token structure unchanged
  - Token sent to GCSplit3 uses `eth_amount=from_amount` (line 535)
  - This field is NOT affected by the `to_amount_post_fee` naming change ✅
  - Token encryption/decryption flow remains intact ✅

### Phase 4: Dual-Currency Compatibility Verification ✅

- [ ] **4.1** Verify instant payout mode (ETH → ClientCurrency)
  - Token flow: GCWebhook1 → GCSplit1 → GCSplit2 → GCSplit1 → GCSplit3
  - GCSplit2 returns token with `to_amount_post_fee` = ClientCurrency amount
  - GCSplit1 endpoint extracts and processes correctly ✅
  - GCSplit1 sends to GCSplit3 with `eth_amount=from_amount` (ETH) ✅

- [ ] **4.2** Verify threshold payout mode (USDT → ClientCurrency)
  - Token flow: GCAccumulator → GCSplit1 → GCSplit2 → GCSplit1 → GCSplit3
  - GCSplit2 returns token with `to_amount_post_fee` = ClientCurrency amount
  - GCSplit1 endpoint extracts and processes correctly ✅
  - GCSplit1 sends to GCSplit3 with `eth_amount=from_amount` (USDT) ✅

- [ ] **4.3** Verify `swap_currency` and `payout_mode` fields unaffected
  - These fields extracted correctly (lines 480-481) ✅
  - Logged correctly (lines 484-485) ✅
  - Passed to GCSplit3 correctly (lines 536-537) ✅

### Phase 5: Testing Strategy ✅

- [ ] **5.1** Code review before deployment
  - Verify all 10 occurrences of `to_amount_eth_post_fee` updated
  - Verify all variable references consistent
  - Verify no typos in dictionary key access

- [ ] **5.2** Local testing (optional but recommended)
  - Create mock decrypted token data with `to_amount_post_fee` key
  - Test endpoint_2 code path with mock data
  - Verify no KeyError exceptions
  - Verify function calculations correct

- [ ] **5.3** Deployment to Cloud Run
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit1-10-26
  docker build -t gcr.io/telepay-459221/gcsplit1-10-26:latest .
  docker push gcr.io/telepay-459221/gcsplit1-10-26:latest
  gcloud run deploy gcsplit1-10-26 \
    --image gcr.io/telepay-459221/gcsplit1-10-26:latest \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated
  ```

- [ ] **5.4** Verify deployment
  ```bash
  # Check service status
  gcloud run services describe gcsplit1-10-26 --region=us-central1

  # Check logs for startup
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26" --limit=20 --format=json
  ```

### Phase 6: Production Validation ✅

- [ ] **6.1** Trigger instant payout test
  - Use test NowPayments webhook
  - Monitor GCWebhook1 → GCSplit1 → GCSplit2 → GCSplit1 flow
  - Verify no KeyError on line 476

- [ ] **6.2** Check logs for success
  ```bash
  # GCSplit1 endpoint_2 processing
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26 AND textPayload:\"ENDPOINT_2\"" --limit=10

  # Look for successful extraction
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26 AND textPayload:\"To (post-fee)\"" --limit=5
  ```

- [ ] **6.3** Verify data integrity
  - `to_amount_post_fee` extracted correctly from token
  - Print statements show correct values
  - `calculate_pure_market_conversion()` executes without errors
  - Database insertion succeeds
  - Token sent to GCSplit3 successfully

- [ ] **6.4** Test threshold payout mode
  - Trigger threshold payout test (if possible)
  - Verify same fixes work for USDT → ClientCurrency
  - Confirm `swap_currency='usdt'` for threshold

---

## Verification Criteria

### Success Indicators ✅

1. **No KeyError:** GCSplit1 logs show no `'to_amount_eth_post_fee'` KeyError
2. **Field Extraction:** Logs show `💰 [ENDPOINT_2] To (post-fee): X.XXXXXX`
3. **Function Execution:** `calculate_pure_market_conversion()` completes successfully
4. **Database Insertion:** `✅ [ENDPOINT_2] Database insertion successful`
5. **Token to GCSplit3:** `✅ [CLOUD_TASKS] Payment split task created`
6. **Payment Completion:** Transaction completes successfully through GCSplit3

### Failure Indicators ❌

1. **KeyError persists:** `❌ [ENDPOINT_2] Unexpected error: 'to_amount_eth_post_fee'`
2. **New KeyError:** `❌ [ENDPOINT_2] Unexpected error: 'to_amount_post_fee'` (typo in fix)
3. **Function error:** `❌ [MARKET_CALC] Error: ...`
4. **Database error:** `❌ [ENDPOINT_2] Failed to insert into database`

---

## Impact Analysis on Other Services

### GCSplit2 - NO CHANGES NEEDED ✅
**Why:** GCSplit2 is internally consistent
- Encrypt method parameter: `to_amount_eth_post_fee`
- Decrypt method return key: `"to_amount_eth_post_fee"`
- Endpoint code: Uses consistent naming internally
- **Conclusion:** GCSplit2 does not call GCSplit1's decrypt method, so no impact

### GCSplit3 - NO CHANGES NEEDED ✅
**Why:** GCSplit3 receives different token structure
- Receives token from GCSplit1 with field `eth_amount` (not `to_amount_*`)
- GCSplit3's internal token methods unaffected by GCSplit1's changes
- **Conclusion:** Token structure from GCSplit1→GCSplit3 remains unchanged

### Token Flow Summary ✅

```
INSTANT MODE (ETH → ClientCurrency):
┌─────────────┐                ┌─────────────┐                ┌─────────────┐
│ GCWebhook1  │───payment──────→│  GCSplit1   │─────────────→ │  GCSplit2   │
└─────────────┘   data          └─────────────┘  estimate req  └─────────────┘
                                      ↓ ⬅︎ encrypted token
                                      │    to_amount_eth_post_fee (in token bytes)
                                      │    to_amount_post_fee (in dict key) ✅ FIX
                                      ↓
                                ┌─────────────┐
                                │  GCSplit3   │
                                └─────────────┘
                                 eth_amount=from_amount ✅ UNCHANGED

THRESHOLD MODE (USDT → ClientCurrency):
┌─────────────┐                ┌─────────────┐                ┌─────────────┐
│GCAccumulator│────payment────→│  GCSplit1   │─────────────→ │  GCSplit2   │
└─────────────┘                └─────────────┘  estimate req  └─────────────┘
                                      ↓ ⬅︎ encrypted token
                                      │    to_amount_eth_post_fee (in token bytes)
                                      │    to_amount_post_fee (in dict key) ✅ FIX
                                      ↓
                                ┌─────────────┐
                                │  GCSplit3   │
                                └─────────────┘
                                 eth_amount=from_amount ✅ UNCHANGED
```

**Key Insight:**
- GCSplit2 encrypts with parameter name `to_amount_eth_post_fee`
- GCSplit1 decrypts and returns dictionary with key `"to_amount_post_fee"`
- This fix updates GCSplit1's endpoint to access the correct key
- No changes needed in GCSplit2 or GCSplit3

---

## Rollback Plan

If deployment causes issues:

```bash
# Revert to previous revision
gcloud run services update-traffic gcsplit1-10-26 \
  --to-revisions=gcsplit1-10-26-00018-abc=100 \
  --region=us-central1

# OR delete latest revision
gcloud run revisions delete gcsplit1-10-26-00019-xyz \
  --region=us-central1
```

**Note:** Rollback will re-introduce the KeyError bug but restore service availability if new issues emerge.

---

## Prevention for Future

### 1. Naming Conventions
- Use currency-agnostic names when value can be in multiple currencies
- Avoid hardcoding currency names in variable names (e.g., `eth`, `usdt`)
- Use descriptive names that reflect the semantic meaning

### 2. Dictionary Key Consistency
- Decrypt methods should document the exact dictionary keys returned
- Endpoint code should access keys documented by decrypt methods
- Add unit tests for encrypt/decrypt roundtrips

### 3. Dual-Currency Architecture
- All services should support generic field names
- Use `swap_currency` field to determine actual currency
- Update legacy parameter names during refactoring

### 4. Code Review Checklist
- When updating decrypt methods, check all endpoint code that uses them
- When adding new fields, ensure encrypt/decrypt/endpoint all aligned
- Test both instant and threshold modes after changes

---

## Summary of Changes

### Files Modified: 1
- `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

### Lines Modified: 10
1. Line 199: Function signature parameter name
2. Line 201: Function parameter name (redundant with 199, combined change)
3. Line 227: Print statement variable
4. Line 232: Calculation variable
5. Line 239: Fallback return variable
6. Line 248: Print statement variable
7. Line 255: Fallback return variable
8. Line 476: **CRITICAL** - Dictionary key access (fixes KeyError)
9. Line 487: Print statement variable
10. Line 492: Function call argument

### Services Impacted: 1
- GCSplit1 (code fix)

### Services Unaffected: 2
- GCSplit2 (no changes needed)
- GCSplit3 (no changes needed)

### Payout Modes Fixed: 2
- Instant mode (ETH → ClientCurrency) ✅
- Threshold mode (USDT → ClientCurrency) ✅

---

## Estimated Time

- **Code Changes:** 15 minutes (10 lines across 1 file)
- **Code Review:** 10 minutes (verify all references updated)
- **Deployment:** 5 minutes (Docker build + push + deploy)
- **Validation:** 10 minutes (test both payout modes)
- **Total:** ~40 minutes

---

**Last Updated:** 2025-11-07
**Priority:** CRITICAL - BLOCKING PRODUCTION
**Status:** Ready for implementation
**Approval Required:** Yes - review changes before deployment
