# GCSplit USDT→Client Currency Fix - Implementation Checklist

**Date**: 2025-11-03
**Issue**: Second ChangeNow swap uses ETH instead of USDT as source currency
**Priority**: P0 - CRITICAL
**Estimated Time**: 60 minutes

---

## Root Cause Summary

**Two bugs causing ETH→ClientCurrency swap instead of USDT→ClientCurrency:**

1. **GCSplit2** (line 131): Hardcoded `to_currency="eth"` instead of using `payout_currency`
2. **GCSplit3** (line 130): Hardcoded `from_currency="eth"` instead of `"usdt"`

---

## Phase 1: Critical Fixes

### ✅ Task 1: Fix GCSplit2 Estimate Logic

**File**: `/10-26/GCSplit2-10-26/tps2-10-26.py`

#### Subtasks:
- [ ] Read current file to verify line numbers
- [ ] Update line 131: Change `to_currency="eth"` → `to_currency=payout_currency`
- [ ] Update line 132: Change `to_network="eth"` → `to_network=payout_network`
- [ ] Update line 154: Add `{payout_currency.upper()}` to log message
- [ ] Verify changes using Read tool

**Expected Changes**:
```python
# Line 129-137: BEFORE
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency="usdt",
    to_currency="eth",      # ❌ BUG
    from_network="eth",
    to_network="eth",       # ❌ BUG
    from_amount=str(adjusted_amount_usdt),
    flow="standard",
    type_="direct"
)

# Line 129-137: AFTER
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency="usdt",
    to_currency=payout_currency,  # ✅ FIXED
    from_network="eth",
    to_network=payout_network,    # ✅ FIXED
    from_amount=str(adjusted_amount_usdt),
    flow="standard",
    type_="direct"
)
```

---

### ✅ Task 2: Fix GCSplit3 Swap Creation

**File**: `/10-26/GCSplit3-10-26/tps3-10-26.py`

#### Subtasks:
- [ ] Read current file to verify line numbers
- [ ] Update line 112: Rename `eth_amount` → `usdt_amount` (for clarity)
- [ ] Update line 118: Change log to show "USDT Amount"
- [ ] Update line 130: Change `from_currency="eth"` → `from_currency="usdt"`
- [ ] Update line 132: Change `from_amount=eth_amount` → `from_amount=usdt_amount`
- [ ] Update line 162: Add "USDT" to log message
- [ ] Verify changes using Read tool

**Expected Changes**:
```python
# Line 112: BEFORE
eth_amount = decrypted_data['eth_amount']  # Estimated

# Line 112: AFTER
usdt_amount = decrypted_data['eth_amount']  # ✅ RENAMED for clarity

# Line 129-137: BEFORE
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="eth",  # ❌ BUG
    to_currency=payout_currency,
    from_amount=eth_amount,
    address=wallet_address,
    from_network="eth",
    to_network=payout_network,
    user_id=str(user_id)
)

# Line 129-137: AFTER
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="usdt",  # ✅ FIXED
    to_currency=payout_currency,
    from_amount=usdt_amount,  # ✅ RENAMED
    address=wallet_address,
    from_network="eth",
    to_network=payout_network,
    user_id=str(user_id)
)
```

---

### ✅ Task 3: Build and Deploy GCSplit2

**Service**: GCSplit2-10-26

#### Subtasks:
- [ ] Navigate to `/10-26/GCSplit2-10-26/` directory
- [ ] Run `gcloud builds submit --tag gcr.io/telepay-459221/gcsplit2-10-26:latest`
- [ ] Verify build success (check for "SUCCESS" in logs)
- [ ] Note build ID and image digest
- [ ] Run `gcloud run deploy gcsplit2-10-26 --image gcr.io/telepay-459221/gcsplit2-10-26:latest --region us-central1`
- [ ] Verify deployment success
- [ ] Note new revision number
- [ ] Verify revision serving 100% traffic
- [ ] Check health endpoint: `https://gcsplit2-10-26-291176869049.us-central1.run.app/health`

**Build ID**: _______________
**Revision**: _______________
**Status**: _______________

---

### ✅ Task 4: Build and Deploy GCSplit3

**Service**: GCSplit3-10-26

#### Subtasks:
- [ ] Navigate to `/10-26/GCSplit3-10-26/` directory
- [ ] Run `gcloud builds submit --tag gcr.io/telepay-459221/gcsplit3-10-26:latest`
- [ ] Verify build success (check for "SUCCESS" in logs)
- [ ] Note build ID and image digest
- [ ] Run `gcloud run deploy gcsplit3-10-26 --image gcr.io/telepay-459221/gcsplit3-10-26:latest --region us-central1`
- [ ] Verify deployment success
- [ ] Note new revision number
- [ ] Verify revision serving 100% traffic
- [ ] Check health endpoint: `https://gcsplit3-10-26-291176869049.us-central1.run.app/health`

**Build ID**: _______________
**Revision**: _______________
**Status**: _______________

---

### ✅ Task 5: Test Batch Payout Flow

**Objective**: Verify second swap uses USDT→ClientCurrency

#### Subtasks:
- [ ] Initiate test payment to trigger batch payout
- [ ] Monitor GCSplit2 logs for estimate request
- [ ] Verify log shows: `To: X.XX SHIB (post-fee)` (not ETH)
- [ ] Monitor GCSplit3 logs for swap creation
- [ ] Verify log shows: `From: X.XX USDT` (not ETH)
- [ ] Check ChangeNow transaction data
- [ ] Verify `fromCurrency: "usdt"` and `toCurrency: "shib"`
- [ ] Confirm swap status changes to "finished"
- [ ] Verify client receives payout in correct currency

**Test Results**:
- GCSplit2 estimate currency: _______________
- GCSplit3 swap from_currency: _______________
- ChangeNow transaction ID: _______________
- Swap status: _______________

---

### ✅ Task 6: Update Documentation

#### 6.1: Update PROGRESS.md
- [ ] Add Session 53 entry to TOP of PROGRESS.md
- [ ] Include root cause summary
- [ ] List all changes made with file names and line numbers
- [ ] Note build IDs and revision numbers
- [ ] Document test results

#### 6.2: Update DECISIONS.md
- [ ] Add Session 53 decision to TOP of DECISIONS.md
- [ ] Document why two-swap architecture was maintained
- [ ] Note alternatives considered (single swap ETH→ClientCurrency)
- [ ] Explain rationale for fix approach

#### 6.3: Update BUGS.md
- [ ] Add Session 53 bug entry to TOP of BUGS.md
- [ ] Document complete timeline and discovery process
- [ ] List fix details with before/after code snippets
- [ ] Note testing results and validation

**Notes**:
- _______________________________________________
- _______________________________________________
- _______________________________________________

---

## Validation Checklist

### Service Health:
- [ ] GCSplit2 health check returns 200 OK
- [ ] GCSplit3 health check returns 200 OK
- [ ] All components show "healthy" status

### Log Verification:
- [ ] GCSplit2 logs show correct `payout_currency` in estimate
- [ ] GCSplit3 logs show `from_currency="usdt"` in swap creation
- [ ] No errors in service logs during batch payout

### ChangeNow Verification:
- [ ] Second swap transaction shows `fromCurrency: "usdt"`
- [ ] Second swap transaction shows correct `toCurrency` (e.g., "shib")
- [ ] Swap completes successfully with status "finished"

### End-to-End Verification:
- [ ] User payment triggers batch payout correctly
- [ ] First swap (ETH→USDT) completes successfully
- [ ] Second swap (USDT→ClientCurrency) completes successfully
- [ ] Client receives payout in correct currency and amount

---

## Rollback Plan (If Needed)

### If Issues Occur:
1. Note error messages and logs
2. Rollback to previous revisions:
   - GCSplit2: `gcloud run services update-traffic gcsplit2-10-26 --to-revisions=PREVIOUS_REVISION=100 --region=us-central1`
   - GCSplit3: `gcloud run services update-traffic gcsplit3-10-26 --to-revisions=PREVIOUS_REVISION=100 --region=us-central1`
3. Document issues in BUGS.md
4. Investigate root cause before re-attempting fix

---

## Success Criteria

### Fix is Successful When:
1. ✅ GCSplit2 logs show estimate for USDT→ClientCurrency (not USDT→ETH)
2. ✅ GCSplit3 logs show swap creation with from_currency="usdt"
3. ✅ ChangeNow transaction JSON shows correct currencies
4. ✅ Second swap completes successfully
5. ✅ Client receives payout in correct currency and amount

---

## Time Tracking

| Task | Estimated | Actual | Status |
|------|-----------|--------|--------|
| Task 1: Fix GCSplit2 | 10 min | _____ | ☐ |
| Task 2: Fix GCSplit3 | 10 min | _____ | ☐ |
| Task 3: Build/Deploy GCSplit2 | 10 min | _____ | ☐ |
| Task 4: Build/Deploy GCSplit3 | 10 min | _____ | ☐ |
| Task 5: Test Batch Payout | 10 min | _____ | ☐ |
| Task 6: Update Documentation | 10 min | _____ | ☐ |
| **Total** | **60 min** | **_____** | ☐ |

---

## Notes & Observations

### Implementation Notes:
- _______________________________________________
- _______________________________________________

### Issues Encountered:
- _______________________________________________
- _______________________________________________

### Lessons Learned:
- _______________________________________________
- _______________________________________________

---

**Checklist Version**: 1.0
**Last Updated**: 2025-11-03
**Session**: 53
