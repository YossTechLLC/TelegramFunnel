# UUID Truncation Bug - Root Cause Analysis

**Date:** 2025-11-03
**Severity:** CRITICAL
**Status:** IDENTIFIED - FIX IN PROGRESS

---

## Executive Summary

GCMicroBatchProcessor is failing with "invalid input syntax for type uuid" errors because the `batch_conversion_id` is being truncated from a full 36-character UUID to only 10 characters.

**Root Cause:** Fixed 16-byte encoding in token encryption systematically truncates UUIDs across multiple services.

**Production Evidence:**
```
❌ [DATABASE] Query error: invalid input syntax for type uuid: "f577abaa-1"
🆔 [ENDPOINT] Batch Conversion ID: f577abaa-1  ← TRUNCATED (should be 36 chars)
```

---

## Detailed Root Cause

### The Bug Location

**GCHostPay3** `token_manager.py` Line 764:
```python
unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
```

This line TRUNCATES the `unique_id` to only **16 bytes**.

### Why This Breaks

**Full UUID Format:**
- Actual value: `"batch_f577abaa-1234-5678-9012-abcdef123456"` (43 characters)
- After encoding to UTF-8: 43 bytes
- After truncation `[:16]`: `"batch_f577abaa-1"` (16 bytes)
- After removing "batch_" prefix in GCHostPay1: `"f577abaa-1"` (10 characters)

**Result:** PostgreSQL receives `"f577abaa-1"` instead of `"f577abaa-1234-5678-9012-abcdef123456"` and rejects it as invalid UUID syntax.

### The Data Flow

```
GCMicroBatchProcessor
  └─> Creates batch with UUID: "f577abaa-1234-5678-9012-abcdef123456"
  └─> Sends to GCHostPay1 with unique_id: "batch_f577abaa-1234-5678-9012-abcdef123456"
      └─> GCHostPay1 forwards to GCHostPay2 (USDT→ETH conversion)
          └─> GCHostPay2 forwards to GCHostPay3 (ETH payout execution)
              └─> GCHostPay3 encrypts token
                  ❌ TRUNCATES unique_id to 16 bytes: "batch_f577abaa-1"
              └─> GCHostPay3 sends truncated token back to GCHostPay1
          └─> GCHostPay1 receives truncated unique_id: "batch_f577abaa-1"
          └─> GCHostPay1 strips "batch_" prefix: "f577abaa-1"
          └─> GCHostPay1 sends callback to GCMicroBatchProcessor
      └─> GCMicroBatchProcessor tries to query database
          ❌ PostgreSQL rejects "f577abaa-1" as invalid UUID
```

---

## Scope Analysis - How Widespread Is This?

Searching for the truncation pattern `[:16]`:

### **Services With 16-Byte Truncation:**

1. **GCHostPay1-10-26** (5 instances)
   - Lines: 395, 549, 700, 841, 1172

2. **GCHostPay2-10-26** (4 instances)
   - Lines: 247, 401, 546, 686

3. **GCHostPay3-10-26** (4 instances)
   - Lines: 248, 402, 562, 764 ← **THIS ONE CAUSED CURRENT BUG**

4. **GCSplit1-10-26** (6 instances)
   - Lines: 110, 262, 412, 413, 551, 552
   - Note: Some are for `closed_channel_id` which may be OK if it's a short integer

### **Impact Assessment:**

- ✅ **WORKS:** Instant payouts (no batch prefix, short unique_id)
- ❌ **BROKEN:** Batch conversions (unique_id = "batch_{uuid}")
- ⚠️ **UNKNOWN:** Threshold payouts (unique_id = "acc_{uuid}")

---

## The Fix Strategy

### Option A: Use Variable-Length String Packing (RECOMMENDED)

Replace fixed 16-byte encoding with the existing `_pack_string()` method that uses length-prefix encoding.

**Before (GCHostPay3 line 764):**
```python
unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
packed_data.extend(unique_id_bytes)
```

**After:**
```python
packed_data.extend(self._pack_string(unique_id))
```

**Decrypt Change (GCHostPay1 line 892):**

**Before:**
```python
unique_id = raw[offset:offset+16].rstrip(b'\x00').decode('utf-8')
offset += 16
```

**After:**
```python
unique_id, offset = self._unpack_string(raw, offset)
```

### Option B: Increase Fixed Length (NOT RECOMMENDED)

Increase from 16 bytes to 64 bytes to accommodate long UUIDs with prefixes.

**Why Not Recommended:**
- Wastes space for short IDs
- Doesn't scale if we add longer prefixes later
- Variable-length is cleaner and already implemented

---

## Fix Checklist

### Phase 1: Fix GCHostPay3 → GCHostPay1 Token (HIGHEST PRIORITY)

**This is the current production bug.**

- [ ] **GCHostPay3** `token_manager.py`
  - [ ] Line 764: Change `unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')` to `self._pack_string(unique_id)`
  - [ ] Line 767: Change `packed_data.extend(unique_id_bytes)` to `packed_data.extend(self._pack_string(unique_id))`
  - [ ] Update token structure comment (line 749) to reflect variable-length unique_id

- [ ] **GCHostPay1** `token_manager.py` (decrypt method)
  - [ ] Line 892-893: Change from fixed 16-byte read to `unique_id, offset = self._unpack_string(raw, offset)`
  - [ ] Update token structure comment to reflect variable-length unique_id

- [ ] **Build and Deploy**
  - [ ] Build GCHostPay3-10-26
  - [ ] Build GCHostPay1-10-26
  - [ ] Deploy GCHostPay3-10-26 (sender changes first)
  - [ ] Deploy GCHostPay1-10-26 (receiver changes second)

### Phase 2: Fix All Other unique_id Truncations (PREVENT FUTURE BUGS)

**Fix remaining instances to prevent issues with threshold payouts and other contexts.**

- [ ] **GCHostPay1** `token_manager.py` - Fix all unique_id encrypt/decrypt pairs
  - [ ] Lines 395, 549, 700, 841, 1172 (5 encrypt methods)
  - [ ] Corresponding decrypt methods

- [ ] **GCHostPay2** `token_manager.py` - Fix all unique_id encrypt/decrypt pairs
  - [ ] Lines 247, 401, 546, 686 (4 encrypt methods)
  - [ ] Corresponding decrypt methods

- [ ] **GCHostPay3** `token_manager.py` - Fix remaining unique_id encrypt/decrypt pairs
  - [ ] Lines 248, 402, 562 (3 remaining encrypt methods)
  - [ ] Corresponding decrypt methods

- [ ] **GCSplit1** `token_manager.py` - Fix unique_id (NOT closed_channel_id yet)
  - [ ] Lines 412, 551 (unique_id encrypt methods)
  - [ ] Corresponding decrypt methods

- [ ] **Build and Deploy All Services**
  - [ ] Build all modified services
  - [ ] Deploy in dependency order

### Phase 3: Investigate closed_channel_id (ASSESS RISK)

- [ ] Determine if `closed_channel_id` values are short enough for 16-byte truncation
- [ ] If not, fix using same pattern as unique_id
- [ ] Lines in GCSplit1: 110, 262, 412-413, 551-552

### Phase 4: Testing & Validation

- [ ] Test batch conversion end-to-end
- [ ] Verify GCMicroBatchProcessor receives full UUID
- [ ] Check database query succeeds
- [ ] Test threshold payouts (acc_{uuid})
- [ ] Monitor production logs for UUID errors

---

## Prevention Measures

1. **Code Review Rule:** Flag any `.encode('utf-8')[:N]` patterns for UUIDs
2. **Testing:** Add integration tests that verify full UUID round-trip
3. **Documentation:** Document token encoding standards
4. **Validation:** Add UUID format validation at token creation time

---

## Lessons Learned

1. **Fixed-length encoding is dangerous for variable-length data**
   - UUIDs are 36 characters (128 bits)
   - UUIDs with prefixes can be 40+ characters
   - Fixed 16-byte truncation silently corrupts data

2. **Length-prefixed encoding is safer**
   - Already implemented as `_pack_string()` method
   - Handles any string length up to 255 bytes
   - No silent truncation

3. **Test with realistic production data**
   - Batch conversion IDs like "batch_{uuid}" are longer than test data
   - Integration tests should use realistic ID formats

---

## Files Modified (Planned)

### Phase 1 (Current Bug Fix):
1. `GCHostPay3-10-26/token_manager.py`
2. `GCHostPay1-10-26/token_manager.py`

### Phase 2 (Complete Fix):
3. `GCHostPay2-10-26/token_manager.py`
4. `GCSplit1-10-26/token_manager.py`

---

## Next Steps

1. ✅ **ROOT CAUSE IDENTIFIED**
2. ⏳ **CREATE IMPLEMENTATION CHECKLIST**
3. ⏳ **EXECUTE PHASE 1 FIX (CRITICAL)**
4. ⏳ **EXECUTE PHASE 2 FIX (COMPREHENSIVE)**
5. ⏳ **VALIDATE IN PRODUCTION**
6. ⏳ **UPDATE DOCUMENTATION**

---

**Analysis Complete:** 2025-11-03
**Next Action:** Execute Phase 1 fix for GCHostPay3 and GCHostPay1
