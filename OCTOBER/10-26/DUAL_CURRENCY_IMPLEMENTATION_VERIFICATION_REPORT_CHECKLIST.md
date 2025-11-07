# DUAL-CURRENCY IMPLEMENTATION FIX CHECKLIST

**Date Created:** 2025-11-07
**Status:** 🚨 CRITICAL FIXES REQUIRED
**Related Document:** `DUAL_CURRENCY_IMPLEMENTATION_VERIFICATION_REPORT.md`

---

## OVERVIEW

This checklist addresses **3 CRITICAL BUGS** in GCSplit2's token manager that will cause 100% failure for instant payouts. All items must be completed before deployment.

---

## PHASE 1: PRE-WORK & PREPARATION

### 1.1 Code Backup & State Verification

- [ ] **Create backup** of current GCSplit2-10-26 directory
  - Path: `/OCTOBER/10-26/GCSplit2-10-26/`
  - Backup location: `/OCTOBER/ARCHIVES/GCSplit2-10-26-BACKUP-DUAL-CURRENCY-FIX/`

- [ ] **Verify current deployment status**
  ```bash
  gcloud run services describe gcsplit2-10-26 --region=us-central1 --format="value(status.url)"
  ```

- [ ] **Check for any running background builds**
  - Verify no conflicting Docker builds in progress
  - Verify no conflicting Cloud Build submissions

### 1.2 Confirm Scope of Changes

- [ ] **Read current GCSplit2 token_manager.py**
  - File: `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py`
  - Confirm lines that need modification:
    - Lines 136-212: `decrypt_gcsplit1_to_gcsplit2_token()`
    - Lines 214-274: `encrypt_gcsplit2_to_gcsplit1_token()`
    - Lines 276-345: `decrypt_gcsplit2_to_gcsplit1_token()`

- [ ] **Verify GCSplit1 token_manager.py is correct**
  - File: `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py`
  - Confirm it has the correct implementation (reference for patterns)

- [ ] **Verify GCSplit3 token_manager.py is correct**
  - File: `/OCTOBER/10-26/GCSplit3-10-26/token_manager.py`
  - Confirm backward compatibility pattern to replicate

---

## PHASE 2: CODE FIXES

### 2.1 FIX #1: Update `decrypt_gcsplit1_to_gcsplit2_token()` Method

**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:136-212`

#### 2.1.1 Variable Renaming

- [ ] **Line ~186:** Change `adjusted_amount_usdt` → `adjusted_amount`
  - Old: `adjusted_amount_usdt = struct.unpack(">d", payload[offset:offset + 8])[0]`
  - New: `adjusted_amount = struct.unpack(">d", payload[offset:offset + 8])[0]`

#### 2.1.2 Extract New Fields (with backward compatibility)

- [ ] **After line ~188:** Add `swap_currency` extraction
  ```python
  # NEW: Extract swap_currency with backward compatibility
  swap_currency = 'usdt'  # Default for old tokens
  if offset + 1 <= len(payload):
      try:
          swap_currency, offset = self._unpack_string(payload, offset)
          print(f"💱 [TOKEN_DEC] Swap currency extracted: {swap_currency}")
      except Exception:
          print(f"⚠️ [TOKEN_DEC] No swap_currency (backward compat)")
          swap_currency = 'usdt'
  ```

- [ ] **After swap_currency:** Add `payout_mode` extraction
  ```python
  # NEW: Extract payout_mode with backward compatibility
  payout_mode = 'instant'  # Default for old tokens
  if offset + 1 <= len(payload):
      try:
          payout_mode, offset = self._unpack_string(payload, offset)
          print(f"🎯 [TOKEN_DEC] Payout mode extracted: {payout_mode}")
      except Exception:
          print(f"⚠️ [TOKEN_DEC] No payout_mode (backward compat)")
          payout_mode = 'instant'
  ```

- [ ] **After payout_mode:** Add `actual_eth_amount` extraction
  ```python
  # NEW: Extract actual_eth_amount with backward compatibility
  actual_eth_amount = 0.0
  if offset + 8 <= len(payload):
      try:
          actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
          offset += 8
          print(f"💰 [TOKEN_DEC] ACTUAL ETH extracted: {actual_eth_amount}")
      except Exception:
          print(f"⚠️ [TOKEN_DEC] No actual_eth_amount (backward compat)")
          actual_eth_amount = 0.0
  ```

#### 2.1.3 Update Return Dictionary

- [ ] **Line ~200:** Update return statement to include new fields
  ```python
  return {
      "user_id": user_id,
      "closed_channel_id": closed_channel_id,
      "wallet_address": wallet_address,
      "payout_currency": payout_currency,
      "payout_network": payout_network,
      "adjusted_amount": adjusted_amount,        # RENAMED from adjusted_amount_usdt
      "swap_currency": swap_currency,            # NEW
      "payout_mode": payout_mode,                # NEW
      "actual_eth_amount": actual_eth_amount,    # NEW
      "timestamp": timestamp
  }
  ```

---

### 2.2 FIX #2: Update `encrypt_gcsplit2_to_gcsplit1_token()` Method

**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:214-274`

#### 2.2.1 Update Method Signature

- [ ] **Line ~214:** Add new parameters to method signature
  ```python
  def encrypt_gcsplit2_to_gcsplit1_token(
      self,
      user_id: int,
      closed_channel_id: str,
      wallet_address: str,
      payout_currency: str,
      payout_network: str,
      from_amount: float,              # RENAMED from from_amount_usdt
      to_amount_eth_post_fee: float,
      deposit_fee: float,
      withdrawal_fee: float,
      swap_currency: str,              # NEW
      payout_mode: str,                # NEW
      actual_eth_amount: float = 0.0  # NEW
  ) -> Optional[str]:
  ```

#### 2.2.2 Update Variable References

- [ ] **Line ~217:** Update print statement
  ```python
  print(f"🔐 [TOKEN_ENC] GCSplit2→GCSplit1: Encrypting estimate response")
  print(f"💱 [TOKEN_ENC] Swap Currency: {swap_currency}, Payout Mode: {payout_mode}")
  ```

- [ ] **Line ~250:** Change variable name in struct.pack
  - Old: `packed_data.extend(struct.pack(">d", from_amount_usdt))`
  - New: `packed_data.extend(struct.pack(">d", from_amount))`

#### 2.2.3 Pack New Fields

- [ ] **After line ~258 (after withdrawal_fee packing):** Add new field packing
  ```python
  # NEW: Pack swap_currency, payout_mode, actual_eth_amount
  packed_data.extend(self._pack_string(swap_currency))
  packed_data.extend(self._pack_string(payout_mode))
  packed_data.extend(struct.pack(">d", actual_eth_amount))
  ```

---

### 2.3 FIX #3: Update `decrypt_gcsplit2_to_gcsplit1_token()` Method

**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:276-345`

#### 2.3.1 Variable Renaming

- [ ] **Line ~310:** Change `from_amount_usdt` → `from_amount`
  - Old: `from_amount_usdt = struct.unpack(">d", payload[offset:offset + 8])[0]`
  - New: `from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]`

#### 2.3.2 Extract New Fields (with backward compatibility)

- [ ] **After line ~322 (after withdrawal_fee extraction):** Add `swap_currency` extraction
  ```python
  # NEW: Extract swap_currency with backward compatibility
  swap_currency = 'usdt'
  if offset + 1 <= len(payload):
      try:
          swap_currency, offset = self._unpack_string(payload, offset)
          print(f"💱 [TOKEN_DEC] Swap currency extracted: {swap_currency}")
      except Exception:
          swap_currency = 'usdt'
  ```

- [ ] **After swap_currency:** Add `payout_mode` extraction
  ```python
  # NEW: Extract payout_mode with backward compatibility
  payout_mode = 'instant'
  if offset + 1 <= len(payload):
      try:
          payout_mode, offset = self._unpack_string(payload, offset)
          print(f"🎯 [TOKEN_DEC] Payout mode extracted: {payout_mode}")
      except Exception:
          payout_mode = 'instant'
  ```

- [ ] **After payout_mode:** Add `actual_eth_amount` extraction
  ```python
  # NEW: Extract actual_eth_amount with backward compatibility
  actual_eth_amount = 0.0
  if offset + 8 <= len(payload):
      try:
          actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
          offset += 8
          print(f"💰 [TOKEN_DEC] ACTUAL ETH extracted: {actual_eth_amount}")
      except Exception:
          actual_eth_amount = 0.0
  ```

#### 2.3.3 Update Return Dictionary

- [ ] **Line ~335:** Update return statement to include new fields
  ```python
  return {
      "user_id": user_id,
      "closed_channel_id": closed_channel_id,
      "wallet_address": wallet_address,
      "payout_currency": payout_currency,
      "payout_network": payout_network,
      "from_amount": from_amount,              # RENAMED from from_amount_usdt
      "swap_currency": swap_currency,          # NEW
      "payout_mode": payout_mode,              # NEW
      "to_amount_eth_post_fee": to_amount_eth_post_fee,
      "deposit_fee": deposit_fee,
      "withdrawal_fee": withdrawal_fee,
      "actual_eth_amount": actual_eth_amount,  # NEW
      "timestamp": timestamp
  }
  ```

---

### 2.4 Verify No Other References Need Updating

- [ ] **Search for `adjusted_amount_usdt` in GCSplit2 codebase**
  ```bash
  grep -r "adjusted_amount_usdt" /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit2-10-26/
  ```
  - Should return NO results after fixes

- [ ] **Search for `from_amount_usdt` in GCSplit2 codebase**
  ```bash
  grep -r "from_amount_usdt" /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit2-10-26/
  ```
  - Should return NO results after fixes

---

## PHASE 3: TESTING

### 3.1 Static Code Review

- [ ] **Review all changes made to token_manager.py**
  - Verify all variable name changes are consistent
  - Verify all new fields are packed/unpacked in correct order
  - Verify backward compatibility logic is present for all new fields

- [ ] **Check for syntax errors**
  ```bash
  python3 -m py_compile /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit2-10-26/token_manager.py
  ```

### 3.2 Unit Tests (Optional but Recommended)

- [ ] **Create test file:** `test_token_roundtrip.py`
  - Test GCSplit1 → GCSplit2 token round-trip with new fields
  - Test GCSplit2 → GCSplit1 token round-trip with new fields
  - Test backward compatibility (old tokens without new fields)

- [ ] **Run unit tests**
  ```bash
  python3 test_token_roundtrip.py
  ```

### 3.3 Integration Test Preparation

- [ ] **Verify GCSplit2 main service (tps2-10-26.py) is compatible**
  - Line 113: Uses `adjusted_amount` ✅ (generic name)
  - Line 115-116: Extracts `swap_currency`, `payout_mode` ✅
  - Line 163-176: Passes all new fields to encrypt method ✅
  - **NO CHANGES NEEDED** to tps2-10-26.py

---

## PHASE 4: DEPLOYMENT

### 4.1 Pre-Deployment Checks

- [ ] **Ensure all code changes are saved**
  - `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py`

- [ ] **Verify no other services are being deployed simultaneously**

- [ ] **Check current GCSplit2 service health**
  ```bash
  curl https://gcsplit2-10-26-291176869049.us-central1.run.app/health
  ```

### 4.2 Build Docker Image

- [ ] **Build new Docker image with updated code**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit2-10-26
  docker build -t gcr.io/telepay-459221/gcsplit2-10-26:dual-currency-fixed .
  ```

- [ ] **Verify Docker build success** (no errors)

### 4.3 Push to Google Container Registry

- [ ] **Submit build to Google Cloud Build**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit2-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gcsplit2-10-26:dual-currency-fixed
  ```

- [ ] **Verify build success** in Cloud Build console

### 4.4 Deploy to Cloud Run

- [ ] **Deploy updated GCSplit2 service**
  ```bash
  gcloud run deploy gcsplit2-10-26 \
    --image gcr.io/telepay-459221/gcsplit2-10-26:dual-currency-fixed \
    --region us-central1 \
    --platform managed
  ```

- [ ] **Verify deployment success**
  ```bash
  gcloud run services describe gcsplit2-10-26 --region=us-central1
  ```

### 4.5 Service Health Check

- [ ] **Test health endpoint**
  ```bash
  curl https://gcsplit2-10-26-291176869049.us-central1.run.app/health
  ```
  - Should return: `"status": "healthy"`
  - Should show: `"token_manager": "healthy"`
  - Should show: `"changenow": "healthy"`
  - Should show: `"cloudtasks": "healthy"`

---

## PHASE 5: POST-DEPLOYMENT VALIDATION

### 5.1 Token Flow Integration Test

- [ ] **Trigger a test instant payout** (if test environment available)
  - Use test payment with `payout_mode='instant'`
  - Monitor logs for successful token decryption in GCSplit2
  - Verify no "Token expired" or `struct.error` errors

- [ ] **Monitor GCSplit2 logs during test**
  ```bash
  gcloud run services logs read gcsplit2-10-26 --region=us-central1 --limit=50
  ```
  - Look for: `"💱 [TOKEN_DEC] Swap currency extracted: eth"`
  - Look for: `"🎯 [TOKEN_DEC] Payout mode extracted: instant"`
  - Look for: `"💰 [TOKEN_DEC] ACTUAL ETH extracted: 0.000XXX"`

### 5.2 Backward Compatibility Test

- [ ] **Trigger a test threshold payout** (old-style token)
  - Use test payment with `payout_mode='threshold'`
  - Verify GCSplit2 can still process old tokens
  - Verify defaults are applied: `swap_currency='usdt'`

### 5.3 Error Monitoring

- [ ] **Monitor for any runtime errors** (24 hour period)
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit2-10-26 AND severity>=ERROR" --limit=50 --format=json
  ```

- [ ] **Check Cloud Tasks queue health**
  ```bash
  gcloud tasks queues describe GCSPLIT1_RESPONSE_QUEUE --location=us-central1
  ```
  - Verify no stuck tasks
  - Verify task execution rate is normal

### 5.4 End-to-End Flow Validation

- [ ] **Verify complete instant payout flow**
  - GCWebhook1 → GCSplit1 → GCSplit2 → GCSplit1 → GCSplit3 → GCHostPay
  - Monitor each service's logs for successful token passing
  - Verify final payout completion

- [ ] **Verify complete threshold payout flow**
  - Same flow but with `payout_mode='threshold'`
  - Verify backward compatibility throughout chain

---

## PHASE 6: DOCUMENTATION & CLEANUP

### 6.1 Update Documentation

- [ ] **Update PROGRESS.md**
  - Add entry: "Fixed GCSplit2 token manager for dual-currency support"
  - Note: "All 3 token methods updated with swap_currency, payout_mode, actual_eth_amount"

- [ ] **Update DECISIONS.md**
  - Add entry: "GCSplit2 token manager now supports both ETH and USDT swaps"
  - Note: "Implemented backward compatibility for old tokens"

- [ ] **Add to BUGS.md** (if not already present)
  - "FIXED: GCSplit2 token manager missing dual-currency fields"

### 6.2 Archive Old Code

- [ ] **Move backup to archives**
  - From: `/OCTOBER/ARCHIVES/GCSplit2-10-26-BACKUP-DUAL-CURRENCY-FIX/`
  - To: Keep for 30 days, then delete if no issues

### 6.3 Verification Confirmation

- [ ] **Create deployment summary document**
  - File: `DUAL_CURRENCY_FIX_DEPLOYMENT_SUMMARY.md`
  - Include: Date, time, issues fixed, test results, deployment status

- [ ] **Update checklist completion status**
  - This document: Mark all items as complete
  - Archive to: `/OCTOBER/ARCHIVES/NOTES_11-7/`

---

## ROLLBACK PLAN (If Issues Occur)

### Emergency Rollback Steps

1. **Identify the issue**
   - Check error logs
   - Determine if rollback is necessary

2. **Redeploy previous version**
   ```bash
   gcloud run deploy gcsplit2-10-26 \
     --image gcr.io/telepay-459221/gcsplit2-10-26:PREVIOUS_TAG \
     --region us-central1
   ```

3. **Verify rollback success**
   ```bash
   curl https://gcsplit2-10-26-291176869049.us-central1.run.app/health
   ```

4. **Document issue in BUGS.md**

5. **Re-review fixes and retry**

---

## CHECKLIST SUMMARY

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1: Pre-Work | 7 tasks | ⬜ Not Started |
| Phase 2: Code Fixes | 19 tasks | ⬜ Not Started |
| Phase 3: Testing | 7 tasks | ⬜ Not Started |
| Phase 4: Deployment | 9 tasks | ⬜ Not Started |
| Phase 5: Validation | 10 tasks | ⬜ Not Started |
| Phase 6: Documentation | 6 tasks | ⬜ Not Started |
| **TOTAL** | **58 tasks** | **⬜ 0% Complete** |

---

## CRITICAL SUCCESS CRITERIA

Before marking this checklist as complete, verify:

- ✅ All 3 methods in GCSplit2 token_manager.py are updated
- ✅ All variable names changed from `*_usdt` to generic names
- ✅ All new fields (swap_currency, payout_mode, actual_eth_amount) are packed/unpacked
- ✅ Backward compatibility is implemented for all new fields
- ✅ GCSplit2 service deployed successfully
- ✅ Health check passes
- ✅ At least one successful instant payout test completed
- ✅ No errors in logs for 24 hours post-deployment

---

**Checklist Created:** 2025-11-07
**Estimated Time to Complete:** 2-4 hours
**Priority:** 🚨 CRITICAL - Required before any instant payouts can function
