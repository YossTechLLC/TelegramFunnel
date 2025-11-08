# RESOLVING GCSPLIT TOKEN ENCRYPTION/DECRYPTION ISSUE

**Status:** CRITICAL BUG IDENTIFIED - TOKEN FIELD ORDERING MISMATCH
**Date:** 2025-11-07
**Issue:** GCSplit1 cannot decrypt tokens from GCSplit2 due to field ordering mismatch

---

## Executive Summary

### Root Cause
**Token field ordering mismatch** between GCSplit2's encryption and GCSplit1's decryption:

- **GCSplit2 packs:** `from_amount → to_amount → deposit_fee → withdrawal_fee → swap_currency → payout_mode → actual_eth_amount`
- **GCSplit1 unpacks:** `from_amount → swap_currency → payout_mode → to_amount → deposit_fee → withdrawal_fee → actual_eth_amount`

This causes struct unpacking to read from wrong byte offsets, producing:
- Missing swap_currency/payout_mode (reads fee fields as strings)
- Corrupted actual_eth_amount: `2.6874284797920923e-292` (reads random bytes as double)
- Token expiry errors (invalid signature verification)

### Impact
- ✅ **Instant payout mode:** BLOCKED - Cannot process payments
- ✅ **Threshold payout mode:** BLOCKED - Same token flow affected
- ❌ **Data corruption:** Critical - Wrong amounts could cause financial loss

---

## Error Log Evidence

```
2025-11-07 10:40:46.084 EST
🔓 [TOKEN_DEC] GCSplit2→GCSplit1: Decrypting estimate response
⚠️ [TOKEN_DEC] No swap_currency in token (backward compat - defaulting to 'usdt')
⚠️ [TOKEN_DEC] No payout_mode in token (backward compat - defaulting to 'instant')
💰 [TOKEN_DEC] ACTUAL ETH extracted: 2.6874284797920923e-292  ❌ CORRUPTED
❌ [TOKEN_DEC] Decryption error: Token expired
❌ [ENDPOINT_2] Failed to decrypt token
❌ [ENDPOINT_2] Unexpected error: 401 Unauthorized: Invalid token
```

**Analysis:**
- GCSplit2 successfully encrypted token with new fields
- GCSplit1 failed to decrypt because it's reading from wrong byte positions
- Backward compatibility checks triggered (shouldn't happen with new tokens)
- Corrupted double value confirms struct misalignment

---

## Technical Analysis

### GCSplit2 Encryption (CORRECT ORDER)

**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py`
**Method:** `encrypt_gcsplit2_to_gcsplit1_token()` (Lines 266-338)

**Packing Order:**
```python
# Line 305-309: Fixed fields
packed_data.extend(struct.pack(">Q", user_id))                    # 8 bytes
packed_data.extend(closed_channel_id_bytes)                        # 16 bytes
packed_data.extend(self._pack_string(wallet_address))             # 1+N bytes
packed_data.extend(self._pack_string(payout_currency))            # 1+N bytes
packed_data.extend(self._pack_string(payout_network))             # 1+N bytes

# Line 310-313: Amount fields
packed_data.extend(struct.pack(">d", from_amount))                # 8 bytes
packed_data.extend(struct.pack(">d", to_amount_eth_post_fee))     # 8 bytes
packed_data.extend(struct.pack(">d", deposit_fee))                # 8 bytes
packed_data.extend(struct.pack(">d", withdrawal_fee))             # 8 bytes

# Line 316-318: NEW FIELDS ✅ CORRECT POSITION
packed_data.extend(self._pack_string(swap_currency))              # 1+N bytes
packed_data.extend(self._pack_string(payout_mode))                # 1+N bytes
packed_data.extend(struct.pack(">d", actual_eth_amount))          # 8 bytes

# Line 320: Timestamp
packed_data.extend(struct.pack(">I", current_timestamp))          # 4 bytes
```

### GCSplit1 Decryption (INCORRECT ORDER)

**File:** `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py`
**Method:** `decrypt_gcsplit2_to_gcsplit1_token()` (Lines 363-472)

**Unpacking Order (WRONG):**
```python
# Line 388-397: Fixed fields (CORRECT)
user_id = struct.unpack(">Q", payload[offset:offset + 8])[0]
offset += 8
closed_channel_id = ...
offset += 16
wallet_address, offset = self._unpack_string(payload, offset)
payout_currency, offset = self._unpack_string(payload, offset)
payout_network, offset = self._unpack_string(payload, offset)

# Line 399-400: First amount (CORRECT)
from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8

# Line 402-422: NEW FIELDS ❌ WRONG POSITION - Should be AFTER withdrawal_fee!
swap_currency = 'usdt'
if offset + 1 <= len(payload):
    swap_currency, offset = self._unpack_string(payload, offset)  # ❌ Reading to_amount as string!

payout_mode = 'instant'
if offset + 1 <= len(payload):
    payout_mode, offset = self._unpack_string(payload, offset)    # ❌ Reading deposit_fee as string!

# Line 424-429: Remaining amounts (WRONG - should be before new fields)
to_amount_post_fee = struct.unpack(">d", payload[offset:offset + 8])[0]  # ❌ Reading garbage
offset += 8
deposit_fee = struct.unpack(">d", payload[offset:offset + 8])[0]          # ❌ Reading garbage
offset += 8
withdrawal_fee = struct.unpack(">d", payload[offset:offset + 8])[0]       # ❌ Reading garbage
offset += 8
```

**Result:** Complete data corruption from offset misalignment.

---

## Solution: Fix GCSplit1 Decryption Order

### Required Change

**File:** `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py`
**Method:** `decrypt_gcsplit2_to_gcsplit1_token()`
**Lines to modify:** 399-445

**BEFORE (WRONG):**
```python
from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8

# ❌ WRONG POSITION
swap_currency, offset = self._unpack_string(payload, offset)
payout_mode, offset = self._unpack_string(payload, offset)

to_amount_post_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8
deposit_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8
withdrawal_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8

actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8
```

**AFTER (CORRECT):**
```python
from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8

# ✅ CORRECT: Read all amount fields FIRST
to_amount_post_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8
deposit_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8
withdrawal_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
offset += 8

# ✅ CORRECT: Read new fields AFTER amount fields
swap_currency = 'usdt'  # Default for old tokens
if offset + 1 <= len(payload):
    try:
        swap_currency, offset = self._unpack_string(payload, offset)
    except Exception:
        print(f"⚠️ [TOKEN_DEC] No swap_currency in token (backward compat - defaulting to 'usdt')")
        swap_currency = 'usdt'
else:
    print(f"⚠️ [TOKEN_DEC] Old token format - no swap_currency (backward compat)")

payout_mode = 'instant'  # Default for old tokens
if offset + 1 <= len(payload):
    try:
        payout_mode, offset = self._unpack_string(payload, offset)
    except Exception:
        print(f"⚠️ [TOKEN_DEC] No payout_mode in token (backward compat - defaulting to 'instant')")
        payout_mode = 'instant'
else:
    print(f"⚠️ [TOKEN_DEC] Old token format - no payout_mode (backward compat)")

# ✅ CORRECT: Read actual_eth_amount LAST
actual_eth_amount = 0.0
if offset + 8 <= len(payload):
    try:
        actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
        offset += 8
        print(f"💰 [TOKEN_DEC] ACTUAL ETH extracted: {actual_eth_amount}")
    except Exception:
        print(f"⚠️ [TOKEN_DEC] No actual_eth_amount in token (backward compat)")
        actual_eth_amount = 0.0
else:
    print(f"⚠️ [TOKEN_DEC] Old token format - no actual_eth_amount (backward compat)")
```

---

## Implementation Checklist

### Phase 1: Code Fix ✅

- [ ] **1.1** Read current GCSplit1 token_manager.py
  - File: `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py`
  - Method: `decrypt_gcsplit2_to_gcsplit1_token()`
  - Lines: 363-472

- [ ] **1.2** Apply ordering fix
  - Move `swap_currency` extraction AFTER `withdrawal_fee` (line ~402 → ~430)
  - Move `payout_mode` extraction AFTER `swap_currency` (line ~413 → ~440)
  - Keep `actual_eth_amount` in current position (already correct)
  - Verify all backward compatibility checks remain intact

- [ ] **1.3** Verify token structure matches GCSplit2
  - Compare packing order in GCSplit2 (lines 305-320)
  - Compare unpacking order in GCSplit1 (lines 387-445)
  - Ensure byte-perfect alignment

### Phase 2: Testing ✅

- [ ] **2.1** Create test token locally
  - Use GCSplit2's encrypt method
  - Pack sample data with new fields
  - Verify token length and structure

- [ ] **2.2** Test decryption locally
  - Use fixed GCSplit1 decrypt method
  - Verify all fields extract correctly
  - Verify no data corruption

- [ ] **2.3** Test backward compatibility
  - Create old-format token (without new fields)
  - Verify defaults apply correctly
  - Verify no errors on old tokens

### Phase 3: Deployment ✅

- [ ] **3.1** Build Docker image
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit1-10-26
  docker build -t gcr.io/telepay-459221/gcsplit1-10-26:latest .
  ```

- [ ] **3.2** Push to GCR
  ```bash
  docker push gcr.io/telepay-459221/gcsplit1-10-26:latest
  ```

- [ ] **3.3** Deploy to Cloud Run
  ```bash
  gcloud run deploy gcsplit1-10-26 \
    --image gcr.io/telepay-459221/gcsplit1-10-26:latest \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated
  ```

- [ ] **3.4** Verify deployment
  ```bash
  # Check service status
  gcloud run services describe gcsplit1-10-26 --region=us-central1

  # Check logs for startup
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26" --limit=20 --format=json
  ```

### Phase 4: Production Validation ✅

- [ ] **4.1** Trigger instant payout test
  - Use test NowPayments webhook
  - Monitor GCWebhook1 → GCSplit1 → GCSplit2 flow
  - Verify token decryption succeeds

- [ ] **4.2** Check logs for success
  ```bash
  # GCSplit2 encryption
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit2-10-26 AND textPayload:\"TOKEN_ENC\"" --limit=5

  # GCSplit1 decryption
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26 AND textPayload:\"TOKEN_DEC\"" --limit=5
  ```

- [ ] **4.3** Verify data integrity
  - Swap currency extracted correctly
  - Payout mode extracted correctly
  - Actual ETH amount matches NowPayments value
  - No corrupted float values

- [ ] **4.4** Test threshold payout mode
  - Trigger threshold payout test
  - Verify same token flow works
  - Confirm swap_currency='usdt' for threshold

---

## Verification Criteria

### Success Indicators ✅

1. **Token Decryption:** GCSplit1 logs show `✅ [TOKEN_DEC] Estimate response decrypted successfully`
2. **Field Extraction:** No "backward compat" warnings for new fields
3. **Swap Currency:** Logs show correct currency (`eth` for instant, `usdt` for threshold)
4. **Payout Mode:** Logs show correct mode (`instant` or `threshold`)
5. **Actual ETH:** Logs show realistic value (e.g., `0.0009853`, NOT `2.687e-292`)
6. **Payment Flow:** Transaction completes successfully through GCSplit3

### Failure Indicators ❌

1. **Decryption Error:** `❌ [TOKEN_DEC] Decryption error: Token expired`
2. **Missing Fields:** `⚠️ [TOKEN_DEC] No swap_currency in token`
3. **Corrupted Values:** `💰 [TOKEN_DEC] ACTUAL ETH extracted: 2.687e-292`
4. **401 Unauthorized:** `❌ [ENDPOINT_2] Unexpected error: 401 Unauthorized`

---

## Rollback Plan

If deployment causes issues:

```bash
# Revert to previous revision
gcloud run services update-traffic gcsplit1-10-26 \
  --to-revisions=gcsplit1-10-26-00017-xyz=100 \
  --region=us-central1

# OR delete latest revision
gcloud run revisions delete gcsplit1-10-26-00018-qjj \
  --region=us-central1
```

**Note:** Rollback will re-introduce the bug but restore service availability.

---

## Additional Notes

### Why This Bug Occurred

1. **Implementation rushed:** New fields added without careful ordering review
2. **No local testing:** Token serialization never tested end-to-end locally
3. **Separate file updates:** GCSplit1 and GCSplit2 token managers updated independently
4. **No unit tests:** Missing struct packing/unpacking test suite

### Prevention for Future

1. **Token versioning:** Add version byte to detect format changes
2. **Unit tests:** Test encrypt/decrypt roundtrip for each token type
3. **Integration tests:** Test full GCSplit1→GCSplit2→GCSplit1 flow locally
4. **Code review:** Compare packing/unpacking orders before deployment

### Impact on Threshold Payouts

**This bug affects BOTH instant AND threshold payouts** because:
- Same token flow: GCWebhook1 → GCSplit1 → GCSplit2 → GCSplit1
- Same token manager methods used
- Only difference is `swap_currency` value ('eth' vs 'usdt')

**Therefore, fixing this resolves the entire dual-currency implementation.**

---

## Estimated Time

- **Code Fix:** 10 minutes
- **Local Testing:** 15 minutes (optional but recommended)
- **Deployment:** 5 minutes
- **Validation:** 10 minutes
- **Total:** ~40 minutes

---

**Last Updated:** 2025-11-07
**Priority:** CRITICAL - BLOCKING PRODUCTION
**Status:** Ready for implementation
