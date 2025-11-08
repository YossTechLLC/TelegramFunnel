# Threshold Payout Method Fix Analysis

**Date:** 2025-11-07
**Status:** CRITICAL BUG - Blocking threshold payouts
**Severity:** HIGH

---

## Problem Summary

The threshold payout method is broken due to a parameter name mismatch after implementing the instant payout dual-currency architecture. The error occurs when GCBatchProcessor triggers GCSplit1's `/batch-payout` endpoint.

**Error:**
```
❌ [ENDPOINT_4] Unexpected error: TokenManager.encrypt_gcsplit1_to_gcsplit2_token() got an unexpected keyword argument 'adjusted_amount_usdt'
```

---

## Root Cause Analysis

### What Happened

When we implemented the instant payout method to support dual currencies (ETH and USDT), we refactored the token encryption methods to be currency-agnostic:

1. **Parameter Renaming:** Changed `adjusted_amount_usdt` → `adjusted_amount` (generic name)
2. **New Parameters:** Added `swap_currency` ('eth' or 'usdt') and `payout_mode` ('instant' or 'threshold')
3. **Unified Flow:** Both instant and threshold payouts now use the same token encryption methods

However, we **missed updating** the `/batch-payout` endpoint (ENDPOINT 4) in `GCSplit1-10-26/tps1-10-26.py` to use the new parameter names.

### Code Location

**File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

**Lines 926-934:**
```python
# ❌ BROKEN CODE
encrypted_token_for_split2 = token_manager.encrypt_gcsplit1_to_gcsplit2_token(
    user_id=batch_user_id,
    closed_channel_id=str(client_id),
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    adjusted_amount_usdt=amount_usdt  # ❌ OLD PARAMETER NAME
)
```

### Method Signature (Current)

**File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit1-10-26/token_manager.py`

**Lines 70-81:**
```python
def encrypt_gcsplit1_to_gcsplit2_token(
    self,
    user_id: int,
    closed_channel_id: str,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    adjusted_amount: Union[str, float, Decimal],  # ✅ NEW NAME (generic)
    swap_currency: str = 'usdt',  # ✅ NEW PARAM
    payout_mode: str = 'instant',  # ✅ NEW PARAM
    actual_eth_amount: float = 0.0
) -> Optional[str]:
```

---

## The Fix

### Required Changes

Update the `/batch-payout` endpoint to use the correct parameter names:

**File:** `GCSplit1-10-26/tps1-10-26.py`
**Lines 926-937:**

```python
# ✅ FIXED CODE
encrypted_token_for_split2 = token_manager.encrypt_gcsplit1_to_gcsplit2_token(
    user_id=batch_user_id,
    closed_channel_id=str(client_id),
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    adjusted_amount=amount_usdt,       # ✅ FIXED: Use new parameter name
    swap_currency='usdt',              # ✅ NEW: Threshold always uses USDT
    payout_mode='threshold',           # ✅ NEW: Mark as threshold payout
    actual_eth_amount=0.0              # ✅ NEW: No ETH in threshold flow
)
```

### Why This Fix Works

1. **Parameter Name:** `adjusted_amount=amount_usdt` matches the current method signature
2. **Swap Currency:** `swap_currency='usdt'` correctly identifies this as a USDT swap (threshold flow)
3. **Payout Mode:** `payout_mode='threshold'` marks this as threshold payout for downstream services
4. **No ETH:** `actual_eth_amount=0.0` since threshold payouts don't involve NowPayments ETH

---

## Impact Analysis

### ✅ Will NOT Break Instant Payout

The instant payout method remains completely unaffected because it uses **ENDPOINT 1** (`POST /`), not ENDPOINT 4.

**Instant Payout Flow:**
```
GCWebhook1 → GCSplit1 (ENDPOINT 1) → GCSplit2 → GCSplit1 (ENDPOINT 2) → GCSplit3 → GCHostPay
```

**Threshold Payout Flow:**
```
GCWebhook1 → queue → GCBatchProcessor → GCSplit1 (ENDPOINT 4) → GCSplit2 → GCSplit1 (ENDPOINT 2) → GCSplit3 → GCHostPay
```

### ✅ Maintains Consistency

After this fix, both flows use the **exact same token format** with:
- Generic `adjusted_amount` (ETH for instant, USDT for threshold)
- `swap_currency` field ('eth' or 'usdt')
- `payout_mode` field ('instant' or 'threshold')
- `actual_eth_amount` field (populated for instant, 0.0 for threshold)

This ensures downstream services (GCSplit2, GCSplit3, GCHostPay) can handle both flows correctly.

---

## Verification Steps

After deploying the fix:

1. **Trigger Threshold Payout:**
   - Make a test payment to a channel configured for threshold payouts
   - Verify GCBatchProcessor successfully creates a batch
   - Check GCSplit1 logs for successful token encryption

2. **Check Logs:**
   ```bash
   gcloud logging read 'resource.type="cloud_run_revision"
   resource.labels.service_name="gcsplit1-10-26"
   severity>=INFO' --limit 50 --format json
   ```

3. **Expected Success Logs:**
   ```
   🎯 [ENDPOINT_4] Batch payout request received (from GCBatchProcessor)
   🔓 [TOKEN_DEC] GCBatchProcessor→GCSplit1: Decrypting batch token
   ✅ [TOKEN_DEC] Batch token decrypted successfully
   🔐 [TOKEN_ENC] GCSplit1→GCSplit2: Encrypting token
   ✅ [TOKEN_ENC] Token encrypted successfully
   ✅ [ENDPOINT_4] Successfully enqueued batch payout to GCSplit2
   ```

4. **Verify Instant Payout Still Works:**
   - Make a test instant payout
   - Confirm no errors in GCSplit1 logs
   - Verify payment completes successfully

---

## Deployment Checklist

- [ ] Update `GCSplit1-10-26/tps1-10-26.py` lines 926-937
- [ ] Build new Docker image
- [ ] Deploy to Cloud Run (creates new revision)
- [ ] Test threshold payout flow
- [ ] Test instant payout flow (regression test)
- [ ] Monitor logs for 24 hours
- [ ] Update PROGRESS.md with Session 75 entry
- [ ] Update DECISIONS.md with fix rationale

---

## Technical Notes

### Why We Refactored to Generic Parameters

The dual-currency architecture requires a single, unified codebase that handles both ETH and USDT swaps. Instead of maintaining separate code paths, we:

1. Use generic parameter names (`adjusted_amount` instead of `adjusted_amount_usdt` or `adjusted_amount_eth`)
2. Add explicit type indicators (`swap_currency`, `payout_mode`)
3. Pass metadata fields (`actual_eth_amount`) even when not needed (set to 0.0)

This approach:
- ✅ Reduces code duplication
- ✅ Makes the codebase easier to maintain
- ✅ Allows downstream services to handle both flows with the same logic
- ✅ Provides backward compatibility through default parameter values

### Backward Compatibility

The token decryption methods include backward compatibility for old tokens:
- If `swap_currency` is missing → defaults to `'usdt'`
- If `payout_mode` is missing → defaults to `'instant'`
- If `actual_eth_amount` is missing → defaults to `0.0`

This ensures old tokens in flight during deployment won't cause errors.

---

## Related Files

- `GCSplit1-10-26/tps1-10-26.py` - Main service file (contains the bug)
- `GCSplit1-10-26/token_manager.py` - Token encryption/decryption methods
- `GCBatchProcessor-10-26/batch10-26.py` - Batch processor (triggers ENDPOINT 4)
- `GCSplit2-10-26/tps2-10-26.py` - Receives encrypted token from GCSplit1

---

## Conclusion

This is a **simple parameter name fix** that was overlooked during the instant payout refactoring. The fix:
- ✅ Restores threshold payout functionality
- ✅ Maintains instant payout functionality
- ✅ Ensures consistency across both payout flows
- ✅ Requires minimal code changes (3 lines)
- ✅ Has no risk to production systems

**Estimated Time to Fix:** 10 minutes
**Estimated Time to Deploy:** 5 minutes
**Risk Level:** LOW (isolated change, well-understood impact)
