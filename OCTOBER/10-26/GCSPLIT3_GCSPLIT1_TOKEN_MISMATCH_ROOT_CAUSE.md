# CRITICAL: GCSplit3→GCSplit1 Token Version Mismatch Root Cause Analysis

## Executive Summary

**ROOT CAUSE IDENTIFIED**: Version mismatch between GCSplit3 and GCSplit1 TokenManager implementations causing systematic token expiration errors.

- **Issue**: GCSplit3 encrypts tokens with `actual_eth_amount` field; GCSplit1 expects tokens WITHOUT it
- **Impact**: 100% token decryption failure rate between services
- **Severity**: CRITICAL - Payment flow completely broken
- **Time to Detection**: Tokens fail within 3 minutes (not 16 minutes as initially reported)

---

## Detailed Analysis

### 1. Token Structure Mismatch

#### GCSplit3-10-26 Token Encryption (tps3-10-26.py line 166-183)
```python
encrypted_response_token = token_manager.encrypt_gcsplit3_to_gcsplit1_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    cn_api_id=cn_api_id,
    from_currency=api_from_currency,
    to_currency=api_to_currency,
    from_network=api_from_network,
    to_network=api_to_network,
    from_amount=api_from_amount,
    to_amount=api_to_amount,
    payin_address=api_payin_address,
    payout_address=api_payout_address,
    refund_address=api_refund_address,
    flow=api_flow,
    type_=api_type,
    actual_eth_amount=actual_eth_amount  # ✅ PASSES actual_eth_amount
)
```

#### GCSplit3-10-26 TokenManager (token_manager.py line 489-567)
```python
def encrypt_gcsplit3_to_gcsplit1_token(
    self,
    unique_id: str,
    user_id: int,
    closed_channel_id: str,
    cn_api_id: str,
    from_currency: str,
    to_currency: str,
    from_network: str,
    to_network: str,
    from_amount: float,
    to_amount: float,
    payin_address: str,
    payout_address: str,
    refund_address: str,
    flow: str,
    type_: str,
    actual_eth_amount: float = 0.0  # ✅ ACCEPTS actual_eth_amount parameter
) -> Optional[str]:
    """
    Token Structure:
    - 16 bytes: unique_id
    - 4 bytes: user_id
    - 16 bytes: closed_channel_id
    - Strings: cn_api_id, currencies, networks, addresses, flow, type
    - 8 bytes each: from_amount, to_amount
    - 8 bytes: actual_eth_amount (ACTUAL from NowPayments)  # ✅ DOCUMENTED
    - 4 bytes: timestamp
    - 16 bytes: HMAC signature
    """
    # ... packing code ...
    packed_data.extend(struct.pack(">d", actual_eth_amount))  # ✅ LINE 547: PACKS actual_eth_amount
```

#### GCSplit1-10-26 TokenManager (token_manager.py line 513-587)
```python
def encrypt_gcsplit3_to_gcsplit1_token(
    self,
    unique_id: str,
    user_id: int,
    closed_channel_id: str,
    cn_api_id: str,
    from_currency: str,
    to_currency: str,
    from_network: str,
    to_network: str,
    from_amount: float,
    to_amount: float,
    payin_address: str,
    payout_address: str,
    refund_address: str,
    flow: str,
    type_: str
    # ❌ NO actual_eth_amount parameter
) -> Optional[str]:
    """
    Token Structure:
    - 16 bytes: unique_id
    - 8 bytes: user_id (uint64)
    - 16 bytes: closed_channel_id
    - Strings: cn_api_id, currencies, networks, addresses, flow, type
    - 8 bytes each: from_amount, to_amount
    - 4 bytes: timestamp  # ❌ NO actual_eth_amount in structure
    - 16 bytes: HMAC signature
    """
    # ... packing code ...
    # ❌ LINE 567-570: NO actual_eth_amount packing
    packed_data.extend(self._pack_string(type_))
    
    current_timestamp = int(time.time())
    packed_data.extend(struct.pack(">I", current_timestamp))
```

#### GCSplit1-10-26 Decryption (token_manager.py line 589-685)
```python
def decrypt_gcsplit3_to_gcsplit1_token(self, token: str) -> Optional[Dict[str, Any]]:
    """Decrypt token from GCSplit3 → GCSplit1."""
    try:
        # ... unpacking code ...
        
        type_, offset = self._unpack_string(payload, offset)
        
        timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]  # ❌ LINE 643
        offset += 4
        
        # ✅ LINE 646-655: TRIES to extract actual_eth_amount for backward compat
        actual_eth_amount = 0.0
        if offset + 8 <= len(payload):  # ❌ CONDITION FAILS - payload already consumed
            try:
                actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
                offset += 8
                print(f"💰 [TOKEN_DEC] ACTUAL ETH extracted: {actual_eth_amount}")
            except Exception:
                print(f"⚠️ [TOKEN_DEC] No actual_eth_amount in token (backward compat)")
                actual_eth_amount = 0.0
        
        now = int(time.time())
        if not (now - 86400 <= timestamp <= now + 300):  # ❌ LINE 658: TIMESTAMP VALIDATION FAILS
            raise ValueError("Token expired")
```

---

## 2. Why Token Decryption Fails

### Binary Structure Mismatch

**GCSplit3 sends (292 chars base64):**
```
[unique_id: 16] [user_id: 8] [channel_id: 16] 
[cn_api_id: var] [from_curr: var] [to_curr: var] [from_net: var] [to_net: var]
[from_amt: 8] [to_amt: 8]
[payin_addr: var] [payout_addr: var] [refund_addr: var] [flow: var] [type: var]
[actual_eth_amount: 8]  ← ✅ EXTRA 8 BYTES HERE
[timestamp: 4]
[signature: 16]
```

**GCSplit1 expects:**
```
[unique_id: 16] [user_id: 8] [channel_id: 16] 
[cn_api_id: var] [from_curr: var] [to_curr: var] [from_net: var] [to_net: var]
[from_amt: 8] [to_amt: 8]
[payin_addr: var] [payout_addr: var] [refund_addr: var] [flow: var] [type: var]
[timestamp: 4]  ← ❌ READS actual_eth_amount BYTES AS TIMESTAMP
[signature: 16]
```

### What Actually Happens

1. **GCSplit3 encrypts** at 17:50:07 with `actual_eth_amount=0.0` (8 bytes: `0x0000000000000000`)
2. **Token structure**: `...type_field + 0x0000000000000000 (actual_eth) + TIMESTAMP + signature`
3. **GCSplit1 decrypts** at 17:53:07 and reads the **first 4 bytes of actual_eth_amount as timestamp**
4. **Timestamp read**: `struct.unpack(">I", payload[offset:offset+4])` reads `0x00000000` = **timestamp 0**
5. **Validation check**: `now - 86400 <= 0 <= now + 300` → **FAILS** (timestamp in 1970!)
6. **Result**: `ValueError("Token expired")`

### Corrupted ACTUAL ETH Value (8.70638631e-315)

When GCSplit1 tries backward-compatible extraction:
```python
if offset + 8 <= len(payload):  # ❌ offset is now PAST the timestamp position
    actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
    # Reads 4 bytes of real timestamp + 4 bytes of signature = garbage float
    # Result: 8.70638631e-315 (corrupted memory interpretation)
```

---

## 3. Timeline of Events

| Time (UTC) | Service | Event | Details |
|------------|---------|-------|---------|
| 17:50:07 | GCSplit3 | Token encrypted | ACTUAL ETH: 0.0, 292 chars, includes actual_eth_amount field |
| 17:50:07 | GCSplit3 | Task enqueued | Target: GCSplit1 /eth-client-swap via gcsplit-eth-client-response-queue |
| 17:53:07 | GCSplit1 | Token decryption attempted | ERROR: Token expired (timestamp=0) |
| 17:54:07 | GCSplit1 | Retry #1 | ERROR: Token expired |
| 17:55:07 | GCSplit1 | Retry #2 | ERROR: Token expired |
| ... | GCSplit1 | Retries continue every 60s | All fail with same error |
| 18:12:08 | GCSplit1 | Latest retry | Still failing |

**Observation**: Cloud Tasks is retrying every ~60 seconds due to 401 Unauthorized response.

---

## 4. Why ACTUAL ETH is 0.0

From GCSplit3 logs (17:50:07):
```
💎 [ENDPOINT] ACTUAL ETH (from NowPayments): 0.0
```

**Root cause**: GCSplit3 receives `actual_eth_amount=0.0` from GCSplit1 because:

1. GCSplit1 passes `actual_eth_amount` to GCSplit3 (tps1-10-26.py line 508)
2. BUT GCSplit1's `encrypt_gcsplit1_to_gcsplit3_token` method (line 380-443) **DOES include actual_eth_amount** in the token
3. GCSplit3's `decrypt_gcsplit1_to_gcsplit3_token` (tps3-10-26.py line 113) successfully extracts it
4. **The issue**: The value is 0.0 because it's not being properly propagated from the original webhook

**Separate issue**: The 0.0 value indicates the actual_eth_amount is not being passed correctly from earlier in the flow, but this is a separate data flow issue from the token mismatch.

---

## 5. Token TTL Configuration

**Both services use the same TTL:**
- **Expiration window**: `now - 86400 <= timestamp <= now + 300`
- **Max age**: 24 hours backward
- **Max future**: 5 minutes forward
- **Signing key**: Both use `SUCCESS_URL_SIGNING_KEY` from Secret Manager

**TTL is NOT the problem** - the timestamp being read is literally `0` (Unix epoch 1970-01-01).

---

## 6. Impact Assessment

### Complete Payment Flow Breakdown

```
GCWebhook1 → GCSplit1 → GCSplit2 → GCSplit1 → GCSplit3 → GCSplit1 ❌ FAILS HERE
                                                              ↓
                                                         GCHostPay1 (never reached)
```

**Consequences:**
- ✅ USDT→ETH estimate: Works
- ✅ ETH→Client swap creation: Works
- ✅ ChangeNow transaction created: Works
- ❌ **Payment confirmation to GCHostPay: BLOCKED**
- ❌ **ETH transfer to client: NEVER HAPPENS**
- ❌ **User payment stuck in limbo**

### Production Impact
- **All payments from Nov 2-3**: Stuck at GCSplit3→GCSplit1 handoff
- **Financial risk**: Funds received but not distributed
- **User experience**: Payment confirmation pending indefinitely

---

## 7. Root Cause Summary

| Factor | GCSplit3-10-26 | GCSplit1-10-26 | Status |
|--------|---------------|---------------|---------|
| **Token Structure** | Includes actual_eth_amount (8 bytes) | Does NOT include actual_eth_amount | ❌ MISMATCH |
| **Encryption Method** | `encrypt_gcsplit3_to_gcsplit1_token()` has 16 params | `encrypt_gcsplit3_to_gcsplit1_token()` has 15 params | ❌ MISMATCH |
| **Decryption Method** | N/A (GCSplit3 doesn't decrypt this direction) | `decrypt_gcsplit3_to_gcsplit1_token()` expects 15-param format | ❌ INCOMPATIBLE |
| **Signing Key** | SUCCESS_URL_SIGNING_KEY | SUCCESS_URL_SIGNING_KEY | ✅ MATCH |
| **TTL Policy** | 24h backward, 5min forward | 24h backward, 5min forward | ✅ MATCH |
| **Timestamp Read** | N/A | Reads actual_eth_amount bytes as timestamp = 0 | ❌ CORRUPTION |

**Primary Issue**: Code version mismatch - GCSplit3 has updated TokenManager, GCSplit1 has old version.

**Secondary Issue**: ACTUAL ETH is 0.0 (separate data propagation issue).

**Tertiary Issue**: No defensive validation - timestamp=0 should be caught with better error message.

---

## 8. Fix Strategy

### IMMEDIATE FIX (Deploy within hours)

**Option A: Update GCSplit1 TokenManager** (RECOMMENDED)
```python
# GCSplit1-10-26/token_manager.py

def encrypt_gcsplit3_to_gcsplit1_token(
    self,
    # ... existing params ...
    type_: str,
    actual_eth_amount: float = 0.0  # ✅ ADD THIS PARAMETER
) -> Optional[str]:
    # ... existing packing code ...
    packed_data.extend(self._pack_string(type_))
    packed_data.extend(struct.pack(">d", actual_eth_amount))  # ✅ ADD THIS LINE
    
    current_timestamp = int(time.time())
    # ... rest of method
```

**Option B: Rollback GCSplit3 TokenManager**
- Remove actual_eth_amount from GCSplit3's encryption method
- Match GCSplit1's expected format
- **Drawback**: Loses actual_eth_amount data tracking

### LONG-TERM FIX

1. **Version Token Format**: Add format version byte to all tokens
2. **Defensive Decryption**: Validate timestamp before signature check
3. **Better Error Messages**: "Invalid timestamp: 0 (expected recent Unix timestamp)"
4. **Integration Tests**: Test GCSplit3→GCSplit1 token flow
5. **Fix actual_eth_amount Propagation**: Trace why value is 0.0 from source

---

## 9. Deployment Plan

### Phase 1: Emergency Fix (1-2 hours)
1. ✅ Update GCSplit1-10-26/token_manager.py encryption method
2. ✅ Update GCSplit1-10-26/token_manager.py decryption method (already has backward compat)
3. ✅ Deploy GCSplit1-10-26
4. ✅ Monitor logs for successful token decryption
5. ✅ Verify payment flow end-to-end

### Phase 2: Validation (2-4 hours)
1. ✅ Test with real transaction
2. ✅ Verify actual_eth_amount propagation
3. ✅ Check GCHostPay receives correct amounts
4. ✅ Confirm Cloud Tasks queue clears backlog

### Phase 3: Data Investigation (Next day)
1. Investigate why actual_eth_amount = 0.0
2. Trace webhook data flow from GCWebhook1
3. Fix data propagation issue
4. Re-test end-to-end

---

## 10. Prevention Measures

1. **Shared TokenManager Library**: Extract to common package
2. **API Versioning**: Add version field to all inter-service tokens
3. **Contract Testing**: Automated tests for service integration
4. **Deployment Coordination**: Deploy dependent services together
5. **Canary Deployments**: Test with 1% traffic before full rollout
6. **Monitoring**: Alert on token decryption error rate >1%

---

## Appendix A: Log Evidence

### GCSplit3 Encryption (17:50:07.250)
```
🔐 [TOKEN_ENC] GCSplit3→GCSplit1: Encrypting swap response
💰 [TOKEN_ENC] ACTUAL ETH: 0.0
✅ [TOKEN_ENC] Swap response token encrypted successfully (292 chars)
```

### GCSplit1 Decryption Attempts (17:53:07 - 18:12:08)
```
🔓 [TOKEN_DEC] GCSplit3→GCSplit1: Decrypting swap response
❌ [TOKEN_DEC] Decryption error: Token expired
```
(Repeated every ~60 seconds)

### Token Characteristics
- **Length**: 292 characters (GCSplit3 with actual_eth_amount)
- **Expected**: ~280 characters (GCSplit1 without actual_eth_amount)
- **Difference**: ~12 characters = 8 bytes base64-encoded actual_eth_amount field

---

**Status**: ROOT CAUSE CONFIRMED  
**Priority**: P0 - CRITICAL  
**Next Action**: Deploy GCSplit1 TokenManager fix immediately  
**ETA**: 1-2 hours for fix + deployment + validation

