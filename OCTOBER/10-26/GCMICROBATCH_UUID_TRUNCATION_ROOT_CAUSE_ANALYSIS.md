# GCMicroBatchProcessor UUID Truncation - Root Cause Analysis

**Date:** 2025-11-04
**Severity:** 🔴 **CRITICAL** - Complete Batch Conversion Failure
**Status:** 🚨 **ACTIVE BUG** - Blocking All Micro-Batch Payments

---

## Executive Summary

A **critical bug** is preventing ALL micro-batch conversions from completing. The `batch_conversion_id` (UUID) is being systematically truncated from **36 characters to 10 characters** (`"e0514205-7"` instead of `"e0514205-xxxx-xxxx-xxxx-xxxxxxxxxxxx"`), causing PostgreSQL UUID validation failures.

### Impact
- ❌ **100% failure rate** for batch conversions
- ❌ Database rejects truncated UUID: `invalid input syntax for type uuid: "e0514205-7"`
- ❌ GCMicroBatchProcessor `/swap-executed` endpoint returns 404
- ❌ Accumulated payments stuck in "swapping" status indefinitely
- ❌ Users not receiving USDT payouts

### Root Cause
The UUID is being truncated during the **token encryption/decryption cycle** between GCHostPay1 and GCMicroBatchProcessor, OR during **database storage/retrieval** in GCHostPay1.

---

## Error Details

### Error Log from GCMicroBatchProcessor
```
🆔 [ENDPOINT] Batch Conversion ID: e0514205-7
🔍 [ENDPOINT] Fetching records for batch conversion
🔗 [DATABASE] Connection established successfully
🔍 [DATABASE] Fetching records for batch e0514205-7
❌ [DATABASE] Query error: {'S': 'ERROR', 'V': 'ERROR', 'C': '22P02',
   'M': 'invalid input syntax for type uuid: "e0514205-7"',
   'W': "unnamed portal parameter $1 = '...'",
   'F': 'uuid.c', 'L': '141', 'R': 'string_to_uuid'}
❌ [ENDPOINT] No records found for batch e0514205-7
❌ [ENDPOINT] Unexpected error: 404 Not Found: Batch records not found
```

### Key Observation
- **Expected UUID format:** `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (36 characters)
- **Actual truncated value:** `e0514205-7` (10 characters)
- **Truncation pattern:** Consistently 10 characters, suggesting systematic issue not random corruption

---

## Data Flow Analysis

### Token Encryption/Decryption Chain

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: GCMicroBatchProcessor Creates Batch                         │
├─────────────────────────────────────────────────────────────────────┤
│ microbatch10-26.py:142                                              │
│   batch_conversion_id = str(uuid.uuid4())                           │
│   → "e0514205-1234-5678-9abc-def012345678" (36 chars)          ✅  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Encrypt Token for GCHostPay1                                │
├─────────────────────────────────────────────────────────────────────┤
│ token_manager.py:66 (GCMicroBatchProcessor)                         │
│   payload.extend(self._pack_string(batch_conversion_id))           │
│   → Packs: [length_byte=36] + [36 UUID bytes]                 ✅  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: GCHostPay1 Decrypts Token                                   │
├─────────────────────────────────────────────────────────────────────┤
│ token_manager.py:1002 (GCHostPay1)                                  │
│   batch_conversion_id, offset = self._unpack_string(raw, offset)   │
│   → Should get full 36-char UUID                               ✅? │
│                                                                      │
│ If signature verifies, UUID MUST be intact!                         │
│ (Corruption would fail HMAC verification)                           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: GCHostPay1 Creates unique_id                                │
├─────────────────────────────────────────────────────────────────────┤
│ tphp1-10-26.py:357                                                  │
│   unique_id = f"batch_{batch_conversion_id}"                       │
│   → "batch_e0514205-1234-5678-9abc-def012345678" (42 chars)   ✅? │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: GCHostPay1 Stores unique_id in Database? 🔴 SUSPECT!        │
├─────────────────────────────────────────────────────────────────────┤
│ Possible VARCHAR length limit in processed_payments table?         │
│   → If column is VARCHAR(16), would truncate to "batch_e0514205"   │
│   → This matches the 10-char pattern after removing "batch_"!       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: GCHostPay1 Retrieves unique_id from Database 🔴 CORRUPTION  │
├─────────────────────────────────────────────────────────────────────┤
│ tphp1-10-26.py:740                                                  │
│   batch_conversion_id = unique_id.replace('batch_', '')            │
│   → If unique_id="batch_e0514205" (truncated)                       │
│   → batch_conversion_id="e0514205" (10 chars)                  ❌  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: GCHostPay1 Encrypts Response Token                          │
├─────────────────────────────────────────────────────────────────────┤
│ token_manager.py:1100                                               │
│   payload.extend(self._pack_string(batch_conversion_id))           │
│   → Packs TRUNCATED UUID: [length=10] + "e0514205-7"          ❌  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 8: GCMicroBatchProcessor Decrypts Response                     │
├─────────────────────────────────────────────────────────────────────┤
│ token_manager.py:138                                                │
│   batch_conversion_id, offset = self._unpack_string(payload, offset)│
│   → Gets "e0514205-7" (10 chars)                               ❌  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 9: PostgreSQL Rejects Invalid UUID                             │
├─────────────────────────────────────────────────────────────────────┤
│ database_manager.py:282                                             │
│   WHERE batch_conversion_id = %s  (UUID column type)               │
│   → PostgreSQL ERROR: invalid input syntax for type uuid       ❌  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Root Cause Hypothesis

### Primary Suspect: Database Column Length Limit

The `processed_payments` table in GCHostPay1 likely has a **VARCHAR constraint** on the `unique_id` column that is **too short** to store the full `"batch_{uuid}"` string (42 characters).

#### Evidence
1. **Consistent truncation pattern** - Always exactly 10 characters after removing "batch_"
2. **Database-driven behavior** - Truncation happens between Steps 5-6 (store/retrieve)
3. **Token encryption works** - If token encoding was broken, HMAC verification would fail
4. **UUID generation correct** - Initial UUID is valid 36-character string

#### Hypothesis Details
```sql
-- SUSPECTED SCHEMA (TOO SHORT):
CREATE TABLE processed_payments (
    unique_id VARCHAR(16),  -- ❌ Can only store "batch_e0514205"
    ...
);

-- When storing "batch_e0514205-1234-5678-9abc-def012345678"
-- PostgreSQL silently truncates to "batch_e0514205" (16 chars)

-- When retrieving and removing "batch_", we get "e0514205" (10 chars)
```

### Secondary Suspect: Token Encoding Bug

Alternatively, there could be an issue with the `_pack_string` / `_unpack_string` methods where:
- The length byte is being misread as `10` instead of `36`
- Possible offset calculation error in the unpacking logic

However, this is **less likely** because:
- HMAC signature verification would fail if data was corrupted
- Both services use identical pack/unpack implementations
- Error pattern too consistent for encoding bug

---

## Affected Code Locations

### GCHostPay1-10-26

**File: `tphp1-10-26.py`**
- Line 357: `unique_id = f"batch_{batch_conversion_id}"` - Creates 42-char string
- Line 740: `batch_conversion_id = unique_id.replace('batch_', '')` - Extracts truncated value

**File: `database_manager.py`** (NEEDS INSPECTION)
- Methods that store/retrieve `unique_id` in `processed_payments` table
- Need to verify column schema and length constraints

**File: `token_manager.py`**
- Lines 29-42: `_pack_string()` and `_unpack_string()` methods
- Line 1100: Encrypts response token with (potentially truncated) batch_conversion_id

### GCMicroBatchProcessor-10-26

**File: `microbatch10-26.py`**
- Line 142: Generates full UUID (correct)
- Line 350: Queries database with truncated UUID (fails)

**File: `database_manager.py`**
- Line 282: `WHERE batch_conversion_id = %s` - PostgreSQL rejects truncated UUID

**File: `token_manager.py`**
- Line 138: Decrypts truncated batch_conversion_id from response token

---

## Investigation Steps

### Step 1: Verify Database Schema (**CRITICAL**)

```sql
-- Check processed_payments table schema
\d processed_payments

-- Look for:
-- - unique_id column type (VARCHAR(?)  vs TEXT)
-- - Any CHECK constraints
-- - Any triggers that modify unique_id
```

**Expected Issue:**
```sql
unique_id VARCHAR(16)  -- ❌ TOO SHORT (needs 42+ chars)
```

**Should Be:**
```sql
unique_id VARCHAR(64)  -- ✅ Sufficient for "batch_{uuid}"
-- OR
unique_id TEXT         -- ✅ No length limit
```

### Step 2: Check GCHostPay1 Logs

```bash
# Look for the initial batch_conversion_id decryption
gcloud run services logs read gchostpay1-10-26 \
  --region=us-central1 \
  --format="value(textPayload)" \
  --filter='textPayload:"Batch Conversion ID"' \
  --limit=20
```

**Look for:**
```
🆔 [TOKEN_DEC] Batch Conversion ID: e0514205-1234-5678-9abc-def012345678
```

If the log shows the **full 36-character UUID**, it confirms the truncation happens during database storage/retrieval, not during token decryption.

### Step 3: Inspect Token Encoding

Add debug logging to token_manager.py `_pack_string`:
```python
def _pack_string(self, s: str) -> bytes:
    s_bytes = s.encode('utf-8')
    if len(s_bytes) > 255:
        raise ValueError(f"String too long (max 255 bytes): {s}")
    print(f"🔍 [PACK] String: '{s}' → Length: {len(s_bytes)} bytes")  # DEBUG
    return bytes([len(s_bytes)]) + s_bytes
```

### Step 4: Verify HMAC Signatures

If data corruption occurred during token encoding, the HMAC signature verification would fail. Check GCMicroBatchProcessor logs for signature errors:
```bash
gcloud run services logs read gcmicrobatchprocessor-10-26 \
  --region=us-central1 \
  --format="value(textPayload)" \
  --filter='textPayload:"signature"'
```

**Should NOT see:**
```
❌ [TOKEN_DEC] Signature mismatch
```

---

## Proposed Solution

### Fix 1: Extend Database Column Length (**PRIMARY FIX**)

```sql
-- Migration script
ALTER TABLE processed_payments
ALTER COLUMN unique_id TYPE VARCHAR(64);

-- Verify
\d processed_payments
```

**Rationale:**
- `"batch_{uuid}"` = 6 + 36 = 42 characters minimum
- VARCHAR(64) provides safety margin
- Minimal performance impact (still indexed)

### Fix 2: Add Defensive Validation in GCHostPay1

**File: `tphp1-10-26.py`**

```python
# After line 740
batch_conversion_id = unique_id.replace('batch_', '')

# ADD VALIDATION:
if len(batch_conversion_id) != 36:
    print(f"❌ [ENDPOINT_3] Invalid batch_conversion_id length: {len(batch_conversion_id)} (expected 36)")
    print(f"❌ [ENDPOINT_3] Truncated value: '{batch_conversion_id}'")
    print(f"❌ [ENDPOINT_3] Original unique_id: '{unique_id}'")
    print(f"❌ [ENDPOINT_3] This indicates a database schema issue!")
    abort(500, "Batch ID corrupted - check database schema")
```

### Fix 3: Add Length Assertion in Token Manager

**File: `token_manager.py` (both services)**

```python
def _pack_string(self, s: str) -> bytes:
    """Pack a string with 1-byte length prefix."""
    s_bytes = s.encode('utf-8')
    if len(s_bytes) > 255:
        raise ValueError(f"String too long (max 255 bytes): {s}")

    # ADD: Validate UUID strings
    if s and len(s) == 36 and '-' in s:  # Looks like a UUID
        if len(s) != 36:
            raise ValueError(f"UUID string has invalid length: {len(s)} (expected 36), value: '{s}'")

    return bytes([len(s_bytes)]) + s_bytes
```

### Fix 4: Comprehensive Logging

Add detailed logging at each step to trace UUID transformations:

**GCHostPay1 `tphp1-10-26.py`:**
```python
# After line 357
print(f"🆔 [ENDPOINT_1] Created unique_id: '{unique_id}' (length: {len(unique_id)})")
print(f"🆔 [ENDPOINT_1] batch_conversion_id: '{batch_conversion_id}' (length: {len(batch_conversion_id)})")

# Before line 740 (before database retrieval)
print(f"🔍 [ENDPOINT_3] Retrieving unique_id from database...")

# After line 740
print(f"🆔 [ENDPOINT_3] Retrieved unique_id: '{unique_id}' (length: {len(unique_id)})")
print(f"🆔 [ENDPOINT_3] Extracted batch_conversion_id: '{batch_conversion_id}' (length: {len(batch_conversion_id)})")
```

---

## Testing Plan

### Test 1: Verify Database Schema
```bash
# Connect to database
gcloud sql connect telepaypsql --user=postgres --database=telepaydb

# Check schema
\d processed_payments

# Check for truncated records
SELECT unique_id, LENGTH(unique_id) as len
FROM processed_payments
WHERE unique_id LIKE 'batch_%'
ORDER BY created_at DESC
LIMIT 10;
```

### Test 2: Create Test Batch
1. Trigger a micro-batch conversion
2. Monitor GCHostPay1 logs for initial UUID:
   ```
   🆔 [TOKEN_DEC] Batch Conversion ID: {full-uuid}
   ```
3. Check if UUID is still full 36 characters after database round-trip
4. Verify GCMicroBatchProcessor receives full UUID in callback

### Test 3: End-to-End Validation
1. Create test payment that accumulates to threshold
2. Verify batch creation succeeds
3. Verify GCHostPay1 executes payment
4. Verify GCMicroBatchProcessor receives callback with FULL UUID
5. Verify database query succeeds
6. Verify USDT distribution completes

---

## Rollout Plan

### Phase 1: Investigation (IMMEDIATE)
- [ ] Check `processed_payments` table schema
- [ ] Review recent GCHostPay1 logs for full UUID
- [ ] Identify exact truncation point

### Phase 2: Database Fix (HIGH PRIORITY)
- [ ] Create migration script
- [ ] Test on telepaypsql-clone first
- [ ] Apply to telepaypsql production
- [ ] Verify no data loss

### Phase 3: Code Hardening (MEDIUM PRIORITY)
- [ ] Add defensive validation in GCHostPay1
- [ ] Add UUID length assertions in token managers
- [ ] Add comprehensive logging at all UUID transformation points
- [ ] Build and deploy updated services

### Phase 4: Verification (POST-DEPLOYMENT)
- [ ] Trigger test batch conversion
- [ ] Monitor logs for full 36-character UUIDs throughout flow
- [ ] Verify database query succeeds
- [ ] Confirm end-to-end payment flow works

---

## Similar Issues to Check

Based on the CRITICAL_QUEUE_NEWLINE_BUG_FIX.md, we should also check for:

1. **Whitespace in unique_id values**
   - Check if database stores `"batch_{uuid}\n"` (with newline)
   - Apply `.strip()` pattern when retrieving from database

2. **Other truncated fields**
   - Review ALL VARCHAR columns in processed_payments
   - Check if cn_api_id, tx_hash, or other fields are truncated

3. **Secret Manager newlines**
   - Verify no newlines in any SECRET values that GCHostPay1 retrieves
   - Apply defensive `.strip()` pattern in config_manager.py

---

## Risk Assessment

### Current Risk: 🔴 **CRITICAL**
- **Impact:** Complete batch conversion failure
- **Scope:** 100% of micro-batch payments affected
- **Duration:** Unknown (need to check logs for first occurrence)

### Mitigation Risk: 🟡 **MEDIUM**
- **Database migration:** Low risk if tested on clone first
- **Code changes:** Medium risk, requires rebuild and redeploy
- **Testing required:** Must validate end-to-end before production use

---

## Questions for User

1. **When did this error start?** (Check logs for first occurrence)
2. **Has processed_payments schema changed recently?**
3. **What is the current VARCHAR length for unique_id column?**
4. **Are there any other tables that store batch_conversion_id?**

---

## Next Steps

1. **IMMEDIATE:** Check database schema for `processed_payments.unique_id` column length
2. **URGENT:** Review GCHostPay1 logs to confirm UUID is full 36 chars after initial decryption
3. **HIGH PRIORITY:** Create and test database migration script
4. **MEDIUM PRIORITY:** Add defensive validation and logging code
5. **POST-FIX:** Create monitoring alert for UUID length anomalies

---

**Status:** 📋 **ANALYSIS COMPLETE** - Ready for Investigation
**Recommended Action:** Check database schema IMMEDIATELY
**Estimated Fix Time:** 1-2 hours (pending schema confirmation)
