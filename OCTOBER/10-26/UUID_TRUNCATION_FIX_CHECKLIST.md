# UUID Truncation Bug - Implementation Checklist

**Date:** 2025-11-03
**Bug:** Batch conversion IDs truncated to 10 characters instead of full 36-character UUID
**Root Cause:** Fixed 16-byte encoding in GCHostPay3 token encryption

---

## ✅ PHASE 1: Fix Current Production Bug (CRITICAL)

**Target:** GCHostPay3 → GCHostPay1 token flow
**Impact:** Fixes batch conversion failures in GCMicroBatchProcessor

### Task 1.1: Fix GCHostPay3 Encryption

**File:** `GCHostPay3-10-26/token_manager.py`
**Method:** `encrypt_gchostpay3_to_gchostpay1_token`

- [ ] **Line 764** - Change unique_id encoding
  - **Before:**
    ```python
    unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
    ```
  - **After:**
    ```python
    # REMOVED - using _pack_string instead
    ```

- [ ] **Line 767** - Change payload packing
  - **Before:**
    ```python
    packed_data.extend(unique_id_bytes)
    ```
  - **After:**
    ```python
    packed_data.extend(self._pack_string(unique_id))
    ```

- [ ] **Line 749** - Update token structure comment
  - **Before:**
    ```
    - 16 bytes: unique_id (fixed)
    ```
  - **After:**
    ```
    - 1 byte: unique_id length + variable bytes (length-prefixed string)
    ```

### Task 1.2: Fix GCHostPay1 Decryption

**File:** `GCHostPay1-10-26/token_manager.py`
**Method:** `decrypt_gchostpay3_to_gchostpay1_token`

- [ ] **Lines 891-893** - Change unique_id parsing
  - **Before:**
    ```python
    # Parse unique_id
    unique_id = raw[offset:offset+16].rstrip(b'\x00').decode('utf-8')
    offset += 16
    ```
  - **After:**
    ```python
    # Parse unique_id (variable-length string)
    unique_id, offset = self._unpack_string(raw, offset)
    ```

- [ ] **Line 886** - Update minimum token size check
  - **Before:**
    ```python
    if len(raw) < 52:
    ```
  - **After:**
    ```python
    # Minimum: 1 (unique_id len) + 1 (min str) + 1 (cn_api_id len) + 1 (min str) +
    #          1 (tx_hash len) + 1 (min str) + 1 (tx_status len) + 1 (min str) +
    #          8 (gas_used) + 8 (block_number) + 4 (timestamp) + 16 (signature) = 43
    if len(raw) < 43:
    ```

- [ ] Update token structure comment in decrypt method docstring

### Task 1.3: Build and Deploy Phase 1

- [ ] **Build GCHostPay3-10-26**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay3-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gchostpay3-10-26:latest
  ```

- [ ] **Build GCHostPay1-10-26**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay1-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gchostpay1-10-26:latest
  ```

- [ ] **Deploy GCHostPay3-10-26 FIRST** (sender sends new format)
  ```bash
  gcloud run deploy gchostpay3-10-26 \
    --image gcr.io/telepay-459221/gchostpay3-10-26:latest \
    --region us-central1
  ```

- [ ] **Deploy GCHostPay1-10-26 SECOND** (receiver can read new format)
  ```bash
  gcloud run deploy gchostpay1-10-26 \
    --image gcr.io/telepay-459221/gchostpay1-10-26:latest \
    --region us-central1
  ```

- [ ] **Record build IDs and revision numbers**

### Task 1.4: Validate Phase 1 Fix

- [ ] Check GCHostPay3 logs for token encryption
  - Look for log: "✅ [TOKEN_ENC] Payment response token encrypted"
  - Verify no encoding errors

- [ ] Check GCHostPay1 logs for token decryption
  - Look for log: "✅ [ENDPOINT_3] Token decoded successfully"
  - Look for log: "🆔 [ENDPOINT_3] Unique ID: batch_..." (should show full UUID)

- [ ] Check GCMicroBatchProcessor logs for database query
  - Look for log: "🆔 [ENDPOINT] Batch Conversion ID: ..." (should show full UUID)
  - Verify NO error: "invalid input syntax for type uuid"

- [ ] Trigger test batch conversion to verify end-to-end

---

## ⏳ PHASE 2: Fix All Other unique_id Truncations (COMPREHENSIVE)

**Target:** All remaining unique_id token encoding/decoding
**Impact:** Prevents future bugs with threshold payouts and other contexts

### Task 2.1: Fix GCHostPay1 Remaining Instances

**File:** `GCHostPay1-10-26/token_manager.py`

- [ ] **Instance 1** - Line 395 (method: `encrypt_gcsplit1_to_gchostpay1_token`)
  - [ ] Change `unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')`
  - [ ] Change `packed_data.extend(unique_id_bytes)` → `packed_data.extend(self._pack_string(unique_id))`
  - [ ] Update corresponding decrypt method `decrypt_gcsplit1_to_gchostpay1_token`

- [ ] **Instance 2** - Line 549 (method: TBD)
  - [ ] Apply same fix pattern
  - [ ] Update corresponding decrypt method

- [ ] **Instance 3** - Line 700 (method: TBD)
  - [ ] Apply same fix pattern
  - [ ] Update corresponding decrypt method

- [ ] **Instance 4** - Line 841 (method: TBD)
  - [ ] Apply same fix pattern
  - [ ] Update corresponding decrypt method

- [ ] **Instance 5** - Line 1172 (method: TBD)
  - [ ] Apply same fix pattern
  - [ ] Update corresponding decrypt method

### Task 2.2: Fix GCHostPay2 All Instances

**File:** `GCHostPay2-10-26/token_manager.py`

- [ ] **Instance 1** - Line 247
  - [ ] Apply variable-length fix
  - [ ] Update corresponding decrypt

- [ ] **Instance 2** - Line 401
  - [ ] Apply variable-length fix
  - [ ] Update corresponding decrypt

- [ ] **Instance 3** - Line 546
  - [ ] Apply variable-length fix
  - [ ] Update corresponding decrypt

- [ ] **Instance 4** - Line 686
  - [ ] Apply variable-length fix
  - [ ] Update corresponding decrypt

### Task 2.3: Fix GCHostPay3 Remaining Instances

**File:** `GCHostPay3-10-26/token_manager.py`

- [ ] **Instance 1** - Line 248
  - [ ] Apply variable-length fix
  - [ ] Update corresponding decrypt

- [ ] **Instance 2** - Line 402
  - [ ] Apply variable-length fix
  - [ ] Update corresponding decrypt

- [ ] **Instance 3** - Line 562
  - [ ] Apply variable-length fix
  - [ ] Update corresponding decrypt

### Task 2.4: Fix GCSplit1 unique_id Instances

**File:** `GCSplit1-10-26/token_manager.py`

- [ ] **Instance 1** - Line 412 (unique_id only)
  - [ ] Apply variable-length fix
  - [ ] Update corresponding decrypt

- [ ] **Instance 2** - Line 551 (unique_id only)
  - [ ] Apply variable-length fix
  - [ ] Update corresponding decrypt

**NOTE:** Lines 110, 262, 413, 552 are for `closed_channel_id` - handle separately in Phase 3

### Task 2.5: Build and Deploy Phase 2

- [ ] Build all modified services
  - [ ] GCHostPay1-10-26
  - [ ] GCHostPay2-10-26
  - [ ] GCHostPay3-10-26
  - [ ] GCSplit1-10-26

- [ ] Deploy in dependency order (senders first, receivers second)

- [ ] Record all build IDs and revision numbers

---

## ⏳ PHASE 3: Assess closed_channel_id Risk

**Target:** GCSplit1 closed_channel_id encoding
**Impact:** TBD - depends on actual closed_channel_id values

### Task 3.1: Investigate closed_channel_id Values

- [ ] Check production logs for closed_channel_id examples
- [ ] Determine max length of closed_channel_id values
- [ ] Assess if 16-byte truncation is safe or needs fix

### Task 3.2: Fix if Needed

**If closed_channel_id can exceed 16 bytes:**

- [ ] Apply same variable-length fix to all closed_channel_id instances
  - [ ] Lines: 110, 262, 412-413, 551-552 in GCSplit1
- [ ] Update corresponding decrypt methods
- [ ] Build and deploy GCSplit1

**If closed_channel_id is always ≤ 16 bytes:**

- [ ] Document why 16-byte encoding is safe for this field
- [ ] Add validation to ensure closed_channel_id never exceeds 16 bytes
- [ ] No code changes needed

---

## ✅ PHASE 4: Testing & Validation

### Task 4.1: Integration Testing

- [ ] **Test Batch Conversions** (batch_{uuid})
  - [ ] Trigger batch conversion with multiple small amounts
  - [ ] Verify GCMicroBatchProcessor receives full UUID
  - [ ] Verify database query succeeds
  - [ ] Verify proportional distribution completes

- [ ] **Test Threshold Payouts** (acc_{uuid})
  - [ ] Accumulate payments until threshold
  - [ ] Verify GCAccumulator receives full UUID
  - [ ] Verify payout completes successfully

- [ ] **Test Instant Payouts** (no prefix)
  - [ ] Trigger single large payment
  - [ ] Verify works as before (regression test)

### Task 4.2: Production Monitoring

- [ ] Monitor GCMicroBatchProcessor logs for 24 hours
  - [ ] No "invalid input syntax for type uuid" errors
  - [ ] All batch_conversion_id values show full UUIDs

- [ ] Monitor GCAccumulator logs for 24 hours
  - [ ] No UUID-related errors
  - [ ] All accumulation_id values show full UUIDs

- [ ] Monitor all HostPay services
  - [ ] No token encryption/decryption errors
  - [ ] All unique_id values preserved correctly

---

## 📝 PHASE 5: Documentation

### Task 5.1: Update Code Documentation

- [ ] Add comments explaining variable-length encoding choice
- [ ] Update all token structure comments to reflect new format
- [ ] Document token version if backward compatibility becomes issue

### Task 5.2: Update PROGRESS.md

- [ ] Add Session entry with:
  - [ ] Root cause summary
  - [ ] Production evidence
  - [ ] Fix details (all files modified with line numbers)
  - [ ] Deployment information (build IDs, revisions)
  - [ ] Impact assessment
  - [ ] Testing results

### Task 5.3: Update DECISIONS.md

- [ ] Add architectural decision entry:
  - [ ] Why variable-length encoding chosen
  - [ ] Why NOT fixed-length increase
  - [ ] Future considerations
  - [ ] Trade-offs

### Task 5.4: Update BUGS.md

- [ ] Add bug report with:
  - [ ] Symptom and production evidence
  - [ ] Root cause analysis
  - [ ] Fix implementation details
  - [ ] Deployment details
  - [ ] Lessons learned
  - [ ] Prevention measures

---

## Summary

- **Phase 1:** CRITICAL - Fix production bug (2 files, ~6 line changes)
- **Phase 2:** COMPREHENSIVE - Fix all unique_id instances (4 files, ~40 line changes)
- **Phase 3:** ASSESSMENT - Investigate closed_channel_id (1 file, TBD changes)
- **Phase 4:** VALIDATION - Test all payout flows
- **Phase 5:** DOCUMENTATION - Update all tracking documents

**Estimated Impact:**
- Files Modified: 4-5 services
- Total Line Changes: ~50-60 lines
- Services to Redeploy: 4 services
- Expected Downtime: None (rolling deployment)

---

**Checklist Created:** 2025-11-03
**Status:** READY FOR EXECUTION
**Next:** Execute Phase 1 (CRITICAL FIX)
