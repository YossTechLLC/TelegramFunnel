# DUAL-CURRENCY IMPLEMENTATION VERIFICATION REPORT

**Date:** 2025-11-07
**Review Type:** Code Review - Token Flow & Data Type Analysis
**Status:** 🚨 CRITICAL ISSUES FOUND

---

## Executive Summary

A thorough review of the dual-mode payout currency implementation has revealed **CRITICAL MISMATCHES** between service implementations that will cause **RUNTIME FAILURES**. The system cannot function as deployed.

### Critical Findings:
- ❌ **GCSplit2 token manager NOT updated** - Missing all new fields
- ❌ **Token encryption/decryption mismatch** between services
- ❌ **Type conversion issues** in multiple locations
- ⚠️ **Variable naming inconsistencies** across token chains

---

## CRITICAL ISSUE #1: GCSplit2 Token Manager Not Updated 🚨

### Problem Description

**GCSplit1 encrypts tokens with new fields** (swap_currency, payout_mode, actual_eth_amount), but **GCSplit2 cannot decrypt them** because its token_manager.py was never updated.

### Evidence

#### GCSplit1 Token Manager (encrypt_gcsplit1_to_gcsplit2_token)
**File:** `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py:70-169`

```python
def encrypt_gcsplit1_to_gcsplit2_token(
    self,
    user_id: int,
    closed_channel_id: str,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    adjusted_amount: Union[str, float, Decimal],  # ✅ RENAMED
    swap_currency: str = 'usdt',  # ✅ NEW
    payout_mode: str = 'instant',  # ✅ NEW
    actual_eth_amount: float = 0.0  # ✅ NEW
) -> Optional[str]:
    # ... encryption logic includes all new fields
    packed_data.extend(self._pack_string(swap_currency))  # Line 139
    packed_data.extend(self._pack_string(payout_mode))    # Line 142
    packed_data.extend(struct.pack(">d", actual_eth_amount))  # Line 145
```

#### GCSplit2 Token Manager (decrypt_gcsplit1_to_gcsplit2_token)
**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:136-212`

```python
def decrypt_gcsplit1_to_gcsplit2_token(self, token: str) -> Optional[Dict[str, Any]]:
    # ... decryption logic

    # ❌ WRONG: Uses old field name
    adjusted_amount_usdt = struct.unpack(">d", payload[offset:offset + 8])[0]
    offset += 8

    # ❌ MISSING: No code to extract swap_currency, payout_mode, actual_eth_amount!

    timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]  # Line 190

    return {
        "user_id": user_id,
        "closed_channel_id": closed_channel_id,
        "wallet_address": wallet_address,
        "payout_currency": payout_currency,
        "payout_network": payout_network,
        "adjusted_amount_usdt": adjusted_amount_usdt,  # ❌ OLD NAME
        "timestamp": timestamp
        # ❌ MISSING: swap_currency, payout_mode, actual_eth_amount
    }
```

#### GCSplit2 Main Service (Tries to use missing fields)
**File:** `/OCTOBER/10-26/GCSplit2-10-26/tps2-10-26.py:115-116`

```python
swap_currency = decrypted_data.get('swap_currency', 'usdt')  # ❌ WILL ALWAYS DEFAULT
payout_mode = decrypted_data.get('payout_mode', 'instant')    # ❌ WILL ALWAYS DEFAULT
```

### Impact

**RUNTIME BEHAVIOR:**
1. GCSplit1 sends token with: `adjusted_amount`, `swap_currency='eth'`, `payout_mode='instant'`, `actual_eth_amount=0.0005668`
2. GCSplit2 receives token and tries to decrypt
3. GCSplit2's decrypt method reaches `adjusted_amount_usdt` (line 186) and successfully unpacks 8 bytes
4. GCSplit2 then immediately tries to unpack timestamp (line 190)
5. **BUT** the next bytes in the token are actually `swap_currency` length prefix, not timestamp!
6. **Result:** `struct.unpack(">I", ...)` reads garbage data as timestamp
7. **Outcome:** Token validation fails with "Token expired" or struct.error

**CONSEQUENCE:** All instant payouts will FAIL at GCSplit2 level.

---

## CRITICAL ISSUE #2: GCSplit2 Encrypt Method Not Updated 🚨

### Problem Description

GCSplit2's response token encryption method **does not include the new fields**, so GCSplit1 cannot extract them from the response.

### Evidence

#### GCSplit2 Token Manager (encrypt_gcsplit2_to_gcsplit1_token)
**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:214-274`

```python
def encrypt_gcsplit2_to_gcsplit1_token(
    self,
    user_id: int,
    closed_channel_id: str,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    from_amount_usdt: float,  # ❌ OLD NAME - should be 'from_amount'
    to_amount_eth_post_fee: float,
    deposit_fee: float,
    withdrawal_fee: float
    # ❌ MISSING: swap_currency, payout_mode, actual_eth_amount parameters!
) -> Optional[str]:
    # ... encryption logic
    packed_data.extend(struct.pack(">d", from_amount_usdt))  # ❌ Uses old name
    # ❌ MISSING: No code to pack swap_currency, payout_mode, actual_eth_amount!
```

#### GCSplit2 Main Service (Calls with wrong parameters)
**File:** `/OCTOBER/10-26/GCSplit2-10-26/tps2-10-26.py:163-176`

```python
encrypted_response_token = token_manager.encrypt_gcsplit2_to_gcsplit1_token(
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    from_amount=float(from_amount),  # ✅ Uses new name
    to_amount_eth_post_fee=float(to_amount),
    deposit_fee=float(deposit_fee),
    withdrawal_fee=float(withdrawal_fee),
    swap_currency=swap_currency,  # ✅ Tries to pass
    payout_mode=payout_mode,      # ✅ Tries to pass
    actual_eth_amount=actual_eth_amount  # ✅ Tries to pass
)
```

### Impact

**This will cause a Python TypeError:**
```
TypeError: encrypt_gcsplit2_to_gcsplit1_token() got unexpected keyword arguments:
'swap_currency', 'payout_mode', 'actual_eth_amount'
```

**CONSEQUENCE:** All instant payouts will FAIL at GCSplit2 response encryption.

---

## CRITICAL ISSUE #3: GCSplit3 Token Manager Issues

### Problem: Backward Compatibility Code for Non-Existent Fields

GCSplit3's token manager has backward compatibility code for `swap_currency` and `payout_mode` in the `decrypt_gcsplit1_to_gcsplit3_token` method, but these fields were never added to GCSplit1's `encrypt_gcsplit1_to_gcsplit3_token` method!

### Evidence

#### GCSplit1 Token Manager (encrypt_gcsplit1_to_gcsplit3_token)
**File:** `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py:474-546`

```python
def encrypt_gcsplit1_to_gcsplit3_token(
    self,
    unique_id: str,
    user_id: int,
    closed_channel_id: str,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    eth_amount: float,
    swap_currency: str = 'usdt',  # ✅ HAS PARAMETER
    payout_mode: str = 'instant',  # ✅ HAS PARAMETER
    actual_eth_amount: float = 0.0  # ✅ HAS PARAMETER
) -> Optional[str]:
    # ... packing logic
    packed_data.extend(struct.pack(">d", eth_amount))  # Line 523
    packed_data.extend(self._pack_string(swap_currency))  # ✅ Line 524
    packed_data.extend(self._pack_string(payout_mode))  # ✅ Line 525
    packed_data.extend(struct.pack(">d", actual_eth_amount))  # ✅ Line 526
```

**STATUS:** ✅ GCSplit1 DOES pack these fields correctly!

#### GCSplit3 Token Manager (decrypt_gcsplit1_to_gcsplit3_token)
**File:** `/OCTOBER/10-26/GCSplit3-10-26/token_manager.py:407-516`

```python
def decrypt_gcsplit1_to_gcsplit3_token(self, token: str) -> Optional[Dict[str, Any]]:
    # ... unpacking logic
    eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
    offset += 8

    # ✅ NEW: swap_currency with backward compatibility (Lines 451-462)
    swap_currency = 'usdt'
    if offset + 1 <= len(payload) - 4:
        try:
            swap_currency, offset = self._unpack_string(payload, offset)
            print(f"💱 [TOKEN_DEC] Swap currency extracted: {swap_currency}")
        except Exception:
            swap_currency = 'usdt'

    # ✅ NEW: payout_mode with backward compatibility (Lines 464-473)
    payout_mode = 'instant'
    if offset + 1 <= len(payload) - 4:
        try:
            payout_mode, offset = self._unpack_string(payload, offset)
            print(f"🎯 [TOKEN_DEC] Payout mode extracted: {payout_mode}")
        except Exception:
            payout_mode = 'instant'
```

**STATUS:** ✅ GCSplit3 CAN decode these fields correctly with backward compatibility!

### Issue: GCSplit3 Main Service Does NOT Extract These Fields

**File:** `/OCTOBER/10-26/GCSplit3-10-26/tps3-10-26.py:105-167`

Looking at the main service file (already read in previous conversation summary):
- Line 114-115: Extracts `swap_currency` and `payout_mode` from decrypted token ✅
- Line 134: Uses `from_currency=swap_currency` in ChangeNow API call ✅

**STATUS:** ✅ CORRECTLY IMPLEMENTED

---

## Variable Naming Analysis

### Issue: Inconsistent Variable Names Across Token Chain

#### Adjusted Amount Variable Names

**GCSplit1 → GCSplit2:**
- GCSplit1 encrypts as: `adjusted_amount` (generic, supports ETH or USDT)
- GCSplit2 decrypts as: `adjusted_amount_usdt` ❌ (hardcoded to USDT)

**GCSplit2 → GCSplit1:**
- GCSplit2 encrypts as: `from_amount_usdt` ❌ (hardcoded to USDT)
- GCSplit1 decrypts as: `from_amount` ✅ (generic)

### Recommendation

All variable names should be **currency-agnostic**:
- ❌ `adjusted_amount_usdt`
- ❌ `from_amount_usdt`
- ✅ `adjusted_amount`
- ✅ `from_amount`

---

## Data Type Consistency Analysis

### Float vs Decimal Handling

#### GCSplit1 Token Manager (encrypt_gcsplit1_to_gcsplit2_token)
**File:** `/OCTOBER/10-26/GCSplit1-10-26/token_manager.py:110-116`

```python
if isinstance(adjusted_amount, str):
    amount = float(Decimal(adjusted_amount))  # ✅ Decimal → float
elif isinstance(adjusted_amount, Decimal):
    amount = float(adjusted_amount)  # ✅ Decimal → float
else:
    amount = float(adjusted_amount)  # ✅ Direct float
```

**Analysis:** ✅ Properly converts all numeric types to float for struct.pack

#### GCSplit2 Main Service
**File:** `/OCTOBER/10-26/GCSplit2-10-26/tps2-10-26.py:169-170`

```python
from_amount=float(from_amount),  # ✅ Explicit float conversion
```

**Analysis:** ✅ Properly converts to float before encryption

### Integer Type Consistency

All services use consistent types:
- `user_id`: `int` → packed as `struct.pack(">Q", user_id)` (uint64) ✅
- `closed_channel_id`: `str` → packed as fixed 16-byte string ✅
- Amounts: `float` → packed as `struct.pack(">d", amount)` (double) ✅

---

## Token Encryption/Decryption Flow Analysis

### Expected Flow (Architecture):

```
GCWebhook1 (payout_mode='instant')
    ↓ [token: payout_mode, actual_eth_amount]
GCSplit1 (swap_currency='eth', adjusted_amount=ETH)
    ↓ [token: adjusted_amount, swap_currency, payout_mode, actual_eth_amount]
GCSplit2 (from_currency=swap_currency)
    ↓ [token: from_amount, swap_currency, payout_mode, actual_eth_amount]
GCSplit1 (extracts from_amount, swap_currency, payout_mode)
    ↓ [token: swap_currency, payout_mode, actual_eth_amount]
GCSplit3 (from_currency=swap_currency, uses actual_eth_amount)
    ↓ [token: from_currency, actual_eth_amount]
GCHostPay (from_currency determines payment method)
```

### Actual Implementation (Current Code):

```
GCWebhook1 (payout_mode='instant') ✅
    ↓ [token: payout_mode, actual_eth_amount] ✅
GCSplit1 (swap_currency='eth', adjusted_amount=ETH) ✅
    ↓ [token: adjusted_amount, swap_currency, payout_mode, actual_eth_amount] ✅
GCSplit2 ❌ CANNOT DECRYPT TOKEN!
    ↓ ❌ RUNTIME ERROR: struct.error or "Token expired"
[FLOW STOPS HERE]
```

---

## Summary of Issues by Severity

### 🚨 CRITICAL (System Breaking):

1. **GCSplit2 token manager decrypt method** - Missing code to extract new fields
   - **Impact:** All instant payouts fail with decryption error
   - **Files:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:136-212`

2. **GCSplit2 token manager encrypt method** - Missing parameters for new fields
   - **Impact:** Python TypeError when GCSplit2 tries to send response
   - **Files:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:214-274`

### ⚠️ HIGH (Functional Issues):

3. **Variable naming inconsistency** - `adjusted_amount_usdt` vs `adjusted_amount`
   - **Impact:** Confusion, potential bugs if code assumes USDT
   - **Files:** All token managers

### ✅ CORRECT (No Issues):

- GCWebhook1 implementation ✅
- GCSplit1 token manager ✅
- GCSplit1 main service ✅
- GCSplit3 token manager ✅
- GCSplit3 main service ✅
- Data type conversions ✅
- Backward compatibility defaults ✅

---

## Required Fixes

### Fix #1: Update GCSplit2 Token Manager - decrypt_gcsplit1_to_gcsplit2_token

**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:136-212`

**Changes Required:**

1. Rename `adjusted_amount_usdt` → `adjusted_amount`
2. Add backward-compatible extraction of `swap_currency`, `payout_mode`, `actual_eth_amount`
3. Return all new fields in dict

**Example Implementation (based on GCSplit1's pattern):**

```python
def decrypt_gcsplit1_to_gcsplit2_token(self, token: str) -> Optional[Dict[str, Any]]:
    try:
        # ... existing decryption logic up to adjusted_amount

        # CHANGE: Rename variable
        adjusted_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
        offset += 8

        # NEW: Extract swap_currency with backward compatibility
        swap_currency = 'usdt'  # Default for old tokens
        if offset + 1 <= len(payload):
            try:
                swap_currency, offset = self._unpack_string(payload, offset)
                print(f"💱 [TOKEN_DEC] Swap currency extracted: {swap_currency}")
            except Exception:
                print(f"⚠️ [TOKEN_DEC] No swap_currency (backward compat)")
                swap_currency = 'usdt'

        # NEW: Extract payout_mode with backward compatibility
        payout_mode = 'instant'  # Default for old tokens
        if offset + 1 <= len(payload):
            try:
                payout_mode, offset = self._unpack_string(payload, offset)
                print(f"🎯 [TOKEN_DEC] Payout mode extracted: {payout_mode}")
            except Exception:
                print(f"⚠️ [TOKEN_DEC] No payout_mode (backward compat)")
                payout_mode = 'instant'

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

        # THEN extract timestamp
        timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]
        offset += 4

        # ... existing timestamp validation

        return {
            "user_id": user_id,
            "closed_channel_id": closed_channel_id,
            "wallet_address": wallet_address,
            "payout_currency": payout_currency,
            "payout_network": payout_network,
            "adjusted_amount": adjusted_amount,  # RENAMED
            "swap_currency": swap_currency,      # NEW
            "payout_mode": payout_mode,          # NEW
            "actual_eth_amount": actual_eth_amount,  # NEW
            "timestamp": timestamp
        }
```

### Fix #2: Update GCSplit2 Token Manager - encrypt_gcsplit2_to_gcsplit1_token

**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:214-274`

**Changes Required:**

1. Add parameters: `swap_currency`, `payout_mode`, `actual_eth_amount`
2. Rename `from_amount_usdt` → `from_amount`
3. Pack new fields into token

**Example Implementation:**

```python
def encrypt_gcsplit2_to_gcsplit1_token(
    self,
    user_id: int,
    closed_channel_id: str,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    from_amount: float,  # RENAMED from from_amount_usdt
    to_amount_eth_post_fee: float,
    deposit_fee: float,
    withdrawal_fee: float,
    swap_currency: str,  # NEW
    payout_mode: str,    # NEW
    actual_eth_amount: float = 0.0  # NEW
) -> Optional[str]:
    try:
        print(f"🔐 [TOKEN_ENC] GCSplit2→GCSplit1: Encrypting estimate response")
        print(f"💱 [TOKEN_ENC] Swap Currency: {swap_currency}, Payout Mode: {payout_mode}")

        # ... existing packing logic for user_id, closed_channel_id, strings

        packed_data.extend(struct.pack(">d", from_amount))  # RENAMED
        packed_data.extend(struct.pack(">d", to_amount_eth_post_fee))
        packed_data.extend(struct.pack(">d", deposit_fee))
        packed_data.extend(struct.pack(">d", withdrawal_fee))

        # NEW: Pack swap_currency, payout_mode, actual_eth_amount
        packed_data.extend(self._pack_string(swap_currency))
        packed_data.extend(self._pack_string(payout_mode))
        packed_data.extend(struct.pack(">d", actual_eth_amount))

        # ... rest of encryption logic
```

### Fix #3: Update GCSplit2 Token Manager - decrypt_gcsplit2_to_gcsplit1_token

**File:** `/OCTOBER/10-26/GCSplit2-10-26/token_manager.py:276-345`

**Changes Required:**

1. Rename `from_amount_usdt` → `from_amount`
2. Add backward-compatible extraction of `swap_currency`, `payout_mode`, `actual_eth_amount`
3. Return all new fields in dict

**Example Implementation:**

```python
def decrypt_gcsplit2_to_gcsplit1_token(self, token: str) -> Optional[Dict[str, Any]]:
    try:
        # ... existing decryption logic up to from_amount

        from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]  # RENAMED
        offset += 8
        to_amount_eth_post_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
        offset += 8
        deposit_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
        offset += 8
        withdrawal_fee = struct.unpack(">d", payload[offset:offset + 8])[0]
        offset += 8

        # NEW: Extract swap_currency with backward compatibility
        swap_currency = 'usdt'
        if offset + 1 <= len(payload):
            try:
                swap_currency, offset = self._unpack_string(payload, offset)
            except Exception:
                swap_currency = 'usdt'

        # NEW: Extract payout_mode with backward compatibility
        payout_mode = 'instant'
        if offset + 1 <= len(payload):
            try:
                payout_mode, offset = self._unpack_string(payload, offset)
            except Exception:
                payout_mode = 'instant'

        # NEW: Extract actual_eth_amount with backward compatibility
        actual_eth_amount = 0.0
        if offset + 8 <= len(payload):
            try:
                actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
                offset += 8
            except Exception:
                actual_eth_amount = 0.0

        timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]

        # ... timestamp validation

        return {
            "user_id": user_id,
            "closed_channel_id": closed_channel_id,
            "wallet_address": wallet_address,
            "payout_currency": payout_currency,
            "payout_network": payout_network,
            "from_amount": from_amount,  # RENAMED
            "swap_currency": swap_currency,  # NEW
            "payout_mode": payout_mode,  # NEW
            "to_amount_eth_post_fee": to_amount_eth_post_fee,
            "deposit_fee": deposit_fee,
            "withdrawal_fee": withdrawal_fee,
            "actual_eth_amount": actual_eth_amount,  # NEW
            "timestamp": timestamp
        }
```

---

## Testing Recommendations

### Unit Tests Required:

1. **Token Round-Trip Test (GCSplit1 ↔ GCSplit2)**
   ```python
   def test_gcsplit1_to_gcsplit2_token_roundtrip():
       # Encrypt with new fields
       token = gcsplit1_token_manager.encrypt_gcsplit1_to_gcsplit2_token(
           user_id=123,
           closed_channel_id="456",
           wallet_address="0xabc",
           payout_currency="shib",
           payout_network="eth",
           adjusted_amount=0.00048178,  # ETH amount
           swap_currency='eth',
           payout_mode='instant',
           actual_eth_amount=0.0005668
       )

       # Decrypt with GCSplit2
       data = gcsplit2_token_manager.decrypt_gcsplit1_to_gcsplit2_token(token)

       assert data['adjusted_amount'] == 0.00048178
       assert data['swap_currency'] == 'eth'
       assert data['payout_mode'] == 'instant'
       assert data['actual_eth_amount'] == 0.0005668
   ```

2. **Token Round-Trip Test (GCSplit2 ↔ GCSplit1)**
   ```python
   def test_gcsplit2_to_gcsplit1_token_roundtrip():
       # Encrypt with new fields
       token = gcsplit2_token_manager.encrypt_gcsplit2_to_gcsplit1_token(
           user_id=123,
           closed_channel_id="456",
           wallet_address="0xabc",
           payout_currency="shib",
           payout_network="eth",
           from_amount=0.00048178,
           to_amount_eth_post_fee=586726.70,
           deposit_fee=0.0,
           withdrawal_fee=0.0,
           swap_currency='eth',
           payout_mode='instant',
           actual_eth_amount=0.0005668
       )

       # Decrypt with GCSplit1
       data = gcsplit1_token_manager.decrypt_gcsplit2_to_gcsplit1_token(token)

       assert data['from_amount'] == 0.00048178
       assert data['swap_currency'] == 'eth'
       assert data['payout_mode'] == 'instant'
       assert data['actual_eth_amount'] == 0.0005668
   ```

3. **Backward Compatibility Test**
   ```python
   def test_old_token_still_works():
       # Create old-style token (no new fields)
       old_token = create_old_style_token()

       # Should decrypt with defaults
       data = gcsplit2_token_manager.decrypt_gcsplit1_to_gcsplit2_token(old_token)

       assert data['swap_currency'] == 'usdt'  # Default
       assert data['payout_mode'] == 'instant'  # Default
       assert data['actual_eth_amount'] == 0.0  # Default
   ```

---

## Deployment Recommendations

### DO NOT DEPLOY until:

1. ✅ GCSplit2 token manager updated with all 3 fixes
2. ✅ All unit tests passing
3. ✅ Integration test with full payment flow (GCWebhook1 → GCSplit1 → GCSplit2 → GCSplit1 → GCSplit3)
4. ✅ Verified that all services can decrypt both old and new tokens

### Deployment Order (After Fixes):

1. Deploy GCSplit2 first (with backward compatibility)
2. Deploy GCSplit1 (already correct)
3. Deploy GCSplit3 (already correct)
4. Deploy GCWebhook1 (already correct)

This order ensures backward compatibility - old tokens can still be processed while new tokens are being generated.

---

## Conclusion

The dual-currency implementation is **architecturally sound** but has **critical implementation gaps** in GCSplit2's token manager. These issues will cause **100% failure rate** for instant payouts.

**All fixes must be applied before deployment.**

---

**Report Generated:** 2025-11-07
**Reviewed By:** Claude Code Analysis
**Next Steps:** Apply fixes to GCSplit2 token manager, run tests, re-deploy
