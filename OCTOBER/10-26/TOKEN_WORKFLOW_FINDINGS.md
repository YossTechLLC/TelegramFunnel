# TOKEN WORKFLOW FINDINGS

**Date:** 2025-11-07
**Scope:** Complete token encryption/decryption workflow analysis across TelePay payment system
**Key Focus:** SUCCESS_URL_SIGNING_KEY usage and inter-service communication security

---

## Executive Summary

The TelePay system uses **SUCCESS_URL_SIGNING_KEY** as the primary cryptographic seed for securing inter-service communication via encrypted tokens. This key is fetched from **Google Cloud Secret Manager** and used across **13 microservices** to encrypt/decrypt **25+ different token types** that facilitate secure payment processing, user verification, and cryptocurrency conversions.

**Key Security Mechanisms:**
- HMAC-SHA256 signature validation (16-byte truncated)
- Binary struct packing for space efficiency
- Base64 URL-safe encoding
- Timestamp-based token expiration (ranges from 60 seconds to 24 hours)
- Length-prefixed string encoding (max 255 bytes per field)

---

## 1. SUCCESS_URL_SIGNING_KEY Architecture

### 1.1 Storage and Retrieval

**Location:** Google Cloud Secret Manager
**Secret Name:** `SUCCESS_URL_SIGNING_KEY`
**Access Pattern:** Environment variable injection via Cloud Run `--set-secrets` flag

**Fetch Pattern (Consistent Across All Services):**

```python
# File: config_manager.py (in every service)
def fetch_secret(self, secret_name_env: str) -> Optional[str]:
    """
    Fetch secret from environment variable.
    Cloud Run automatically injects secret values.
    """
    secret_value = (os.getenv(secret_name_env) or '').strip() or None
    return secret_value

# Usage in each service's initialization:
success_url_signing_key = config_manager.fetch_secret(
    "SUCCESS_URL_SIGNING_KEY",
    "Success URL signing key for token encryption"
)
```

**Services Using SUCCESS_URL_SIGNING_KEY:**
1. GCWebhook1-10-26 (Payment processor)
2. GCWebhook2-10-26 (Telegram invite sender)
3. GCSplit1-10-26 (Payment orchestrator)
4. GCSplit2-10-26 (USDT→ETH estimator)
5. GCSplit3-10-26 (ETH→Client swap executor)
6. GCHostPay1-10-26 (Internal signing key)
7. GCHostPay2-10-26 (Internal signing key)
8. GCHostPay3-10-26 (Internal signing key)
9. GCAccumulator-10-26 (Threshold payout aggregator)
10. GCBatchProcessor-10-26 (Batch payout processor)
11. GCMicroBatchProcessor-10-26 (Micro-batch converter)

### 1.2 Secondary Signing Key: TPS_HOSTPAY_SIGNING_KEY

**Purpose:** Separate key for **external → internal** service boundaries
**Used For:** GCSplit1 → GCHostPay1 communication (crossing payment flow boundary)

**Key Separation Strategy:**
- `SUCCESS_URL_SIGNING_KEY`: Internal service-to-service communication (same trust domain)
- `TPS_HOSTPAY_SIGNING_KEY`: External payment flow → internal ETH execution boundary

```python
# GCHostPay1 TokenManager uses BOTH keys:
def __init__(self, tps_hostpay_signing_key: str, internal_signing_key: str):
    self.tps_hostpay_key = tps_hostpay_signing_key     # For GCSplit1 → GCHostPay1
    self.internal_key = internal_signing_key            # For GCHostPay1 ↔ GCHostPay2/3
```

---

## 2. Token Encryption/Decryption Patterns

### 2.1 Common TokenManager Pattern

**All services implement this base pattern:**

```python
class TokenManager:
    def __init__(self, signing_key: str):
        self.signing_key = signing_key

    def _pack_string(self, s: str) -> bytes:
        """Length-prefixed string: 1 byte length + UTF-8 bytes"""
        s_bytes = s.encode('utf-8')
        return bytes([len(s_bytes)]) + s_bytes

    def _unpack_string(self, data: bytes, offset: int) -> Tuple[str, int]:
        """Extract length-prefixed string"""
        length = data[offset]
        offset += 1
        s_bytes = data[offset:offset + length]
        offset += length
        return s_bytes.decode('utf-8'), offset

    def encrypt_xxx_token(self, **fields) -> Optional[str]:
        """
        Standard encryption flow:
        1. Pack fields into binary bytearray using struct.pack
        2. Generate HMAC-SHA256 signature
        3. Truncate signature to 16 bytes
        4. Combine data + signature
        5. Base64 URL-safe encode
        6. Strip trailing '=' padding
        """
        packed_data = bytearray()
        # Pack fields...

        signature = hmac.new(
            self.signing_key.encode(),
            bytes(packed_data),
            hashlib.sha256
        ).digest()[:16]  # Truncate to 16 bytes

        final_data = bytes(packed_data) + signature
        token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')
        return token

    def decrypt_xxx_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Standard decryption flow:
        1. Re-add base64 padding
        2. Decode base64
        3. Split data and signature (last 16 bytes)
        4. Verify HMAC signature
        5. Unpack fields from binary data
        6. Validate timestamp
        7. Return dictionary
        """
        padding = 4 - (len(token) % 4) if len(token) % 4 != 0 else 0
        data = base64.urlsafe_b64decode(token + ('=' * padding))

        payload = data[:-16]
        provided_signature = data[-16:]

        expected_signature = hmac.new(
            self.signing_key.encode(),
            payload,
            hashlib.sha256
        ).digest()[:16]

        if not hmac.compare_digest(provided_signature, expected_signature):
            raise ValueError("Invalid signature")

        # Unpack fields and validate timestamp...
        return decrypted_data
```

### 2.2 Binary Struct Packing Formats

**Primitive Types:**
- `">Q"` - Unsigned 64-bit integer (big-endian)
- `">I"` - Unsigned 32-bit integer (big-endian)
- `">H"` - Unsigned 16-bit integer (big-endian)
- `">d"` - Double precision float (big-endian, 8 bytes)

**Fixed-Length Strings:**
```python
# Fixed 16-byte fields (padded with null bytes)
closed_channel_id_bytes = closed_channel_id.encode('utf-8')[:16].ljust(16, b'\x00')
packed_data.extend(closed_channel_id_bytes)
```

**Variable-Length Strings:**
```python
# 1-byte length prefix (max 255 bytes)
def _pack_string(self, s: str) -> bytes:
    s_bytes = s.encode('utf-8')
    if len(s_bytes) > 255:
        raise ValueError("String too long")
    return bytes([len(s_bytes)]) + s_bytes
```

### 2.3 Timestamp Validation Strategies

**Different services use different expiration windows:**

| Service | Token Type | Validity Window | Reason |
|---------|-----------|-----------------|--------|
| GCWebhook1 | NOWPayments token | 2 hours (7200s) | Handles delayed payment confirmations |
| GCWebhook2 | Telegram invite | 24 hours (86400s) | Accommodates retry delays |
| GCSplit1-3 | Payment flow | 24 hours (86400s) | ETH transaction confirmations (10-20 min) |
| GCHostPay1-3 | ETH execution | 2 hours (7200s) | ChangeNow processing + retries |
| GCAccumulator | Threshold payout | 5 minutes (300s) | Fast internal processing |
| GCMicroBatch | Batch conversion | 30 minutes (1800s) | Extended for ChangeNow retry delays |

**Standard Validation Pattern:**
```python
now = int(time.time())
if not (now - MAX_AGE <= timestamp <= now + 300):
    raise ValueError("Token expired")
```

---

## 3. Complete Token Flow Mapping

### 3.1 INSTANT PAYOUT MODE (ETH → Client Currency)

**Flow:** `NOWPayments → GCWebhook1 → GCWebhook2 (parallel) + GCSplit1 → GCSplit2 → GCSplit1 → GCSplit3 → GCSplit1`

#### Token 1: NOWPayments → GCWebhook1 (Success URL Token)
**Purpose:** Payment confirmation callback
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCWebhook1-10-26/token_manager.py:29-172`

**Structure:**
```
- 6 bytes: user_id (48-bit, handles negative Telegram IDs)
- 6 bytes: closed_channel_id (48-bit)
- 2 bytes: timestamp_minutes (16-bit, wraps every 45 days)
- 2 bytes: subscription_time_days (16-bit)
- 1 byte: subscription_price length + UTF-8 bytes
- 1 byte: wallet_address length + UTF-8 bytes
- 1 byte: payout_currency length + UTF-8 bytes
- 1 byte: payout_network length + UTF-8 bytes
- 16 bytes: HMAC-SHA256 signature (truncated)
```

**Decryption Method:** `decode_and_verify_token()`
**Expiration:** 2 hours (accommodates delayed confirmations)

---

#### Token 2: GCWebhook1 → GCWebhook2 (Telegram Invite)
**Purpose:** Send Telegram channel invite link
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCWebhook1-10-26/token_manager.py:174-272`

**Structure:** Same as Token 1 (re-encrypted with fresh timestamp)

**Encryption Method:** `encrypt_token_for_gcwebhook2()`
**Queue:** `gcwebhook-telegram-invite-queue`
**Parallel Processing:** This happens in parallel with GCSplit1 enqueue

---

#### Token 3: GCWebhook1 → GCSplit1 (Payment Split Request)
**Purpose:** Initiate payment split and conversion
**Signing Key:** SUCCESS_URL_SIGNING_KEY (via Cloud Tasks payload)
**File:** `GCWebhook1-10-26/cloudtasks_client.py:138-186`

**Structure (Cloud Tasks JSON Payload):**
```json
{
  "user_id": int,
  "closed_channel_id": int,
  "wallet_address": str,
  "payout_currency": str,
  "payout_network": str,
  "subscription_price": str,
  "actual_eth_amount": float,  // NEW: From nowpayments_outcome_amount
  "payout_mode": str  // NEW: 'instant' or 'threshold'
}
```

**Enqueue Method:** `enqueue_gcsplit1_payment_split()`
**Queue:** `gcwebhook-payment-split-queue`

---

#### Token 4: GCSplit1 → GCSplit2 (USDT→ETH Estimate Request)
**Purpose:** Get ChangeNow estimate for currency swap
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCSplit1-10-26/token_manager.py:70-169`

**Structure:**
```
- 8 bytes: user_id (uint64)
- 16 bytes: closed_channel_id (fixed, padded)
- 1 byte: wallet_address length + UTF-8 bytes
- 1 byte: payout_currency length + UTF-8 bytes
- 1 byte: payout_network length + UTF-8 bytes
- 8 bytes: adjusted_amount (double) [ETH or USDT based on payout_mode]
- 1 byte: swap_currency length + UTF-8 bytes [NEW: 'eth' or 'usdt']
- 1 byte: payout_mode length + UTF-8 bytes [NEW: 'instant' or 'threshold']
- 8 bytes: actual_eth_amount (double)
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC signature
```

**Key Fields for Dual-Currency Support:**
- `swap_currency`: 'eth' for instant payouts, 'usdt' for threshold payouts
- `payout_mode`: 'instant' or 'threshold' (determines fee structure)
- `actual_eth_amount`: Actual ETH received from NowPayments (for instant payouts)

**Encryption Method:** `encrypt_gcsplit1_to_gcsplit2_token()`
**Decryption Method:** `decrypt_gcsplit1_to_gcsplit2_token()` (GCSplit2 side)

---

#### Token 5: GCSplit2 → GCSplit1 (USDT→ETH Estimate Response)
**Purpose:** Return ChangeNow estimate back to orchestrator
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCSplit2-10-26/token_manager.py:266-338`

**Structure:**
```
- 8 bytes: user_id (uint64)
- 16 bytes: closed_channel_id (fixed)
- 1 byte: wallet_address length + UTF-8 bytes
- 1 byte: payout_currency length + UTF-8 bytes
- 1 byte: payout_network length + UTF-8 bytes
- 8 bytes: from_amount (double) [ETH or USDT]
- 8 bytes: to_amount_eth_post_fee (double)
- 8 bytes: deposit_fee (double)
- 8 bytes: withdrawal_fee (double)
- 1 byte: swap_currency length + UTF-8 bytes [NEW]
- 1 byte: payout_mode length + UTF-8 bytes [NEW]
- 8 bytes: actual_eth_amount (double)
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC signature
```

**⚠️ CRITICAL BUG FIXED (Session 66):**
Field ordering in GCSplit1 decryption was incorrect. Now fixed to match GCSplit2 encryption order.

**Encryption Method:** `encrypt_gcsplit2_to_gcsplit1_token()`
**Decryption Method:** `decrypt_gcsplit2_to_gcsplit1_token()` (GCSplit1 side)

---

#### Token 6: GCSplit1 → GCSplit3 (ETH→Client Swap Request)
**Purpose:** Create final ChangeNow transaction
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCSplit1-10-26/token_manager.py:477-549`

**Structure:**
```
- 16 bytes: unique_id (fixed, UUID for database tracking)
- 8 bytes: user_id (uint64)
- 16 bytes: closed_channel_id (fixed)
- 1 byte: wallet_address length + UTF-8 bytes
- 1 byte: payout_currency length + UTF-8 bytes
- 1 byte: payout_network length + UTF-8 bytes
- 8 bytes: eth_amount (double, estimated from GCSplit2)
- 1 byte: swap_currency length + UTF-8 bytes [NEW]
- 1 byte: payout_mode length + UTF-8 bytes [NEW]
- 8 bytes: actual_eth_amount (double, ACTUAL from NowPayments)
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC signature
```

**Key Design Decision:**
Token includes BOTH estimated_eth_amount (from GCSplit2) and actual_eth_amount (from NowPayments) to enable comparison and use the correct amount for payment.

**Encryption Method:** `encrypt_gcsplit1_to_gcsplit3_token()`
**Decryption Method:** `decrypt_gcsplit1_to_gcsplit3_token()` (GCSplit3 side)

---

#### Token 7: GCSplit3 → GCSplit1 (Swap Response)
**Purpose:** Return ChangeNow transaction details
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCSplit1-10-26/token_manager.py:658-738`

**Structure:**
```
- 16 bytes: unique_id (fixed)
- 8 bytes: user_id (uint64)
- 16 bytes: closed_channel_id (fixed)
- 1 byte: cn_api_id length + UTF-8 bytes (ChangeNow transaction ID)
- 1 byte: from_currency length + UTF-8 bytes
- 1 byte: to_currency length + UTF-8 bytes
- 1 byte: from_network length + UTF-8 bytes
- 1 byte: to_network length + UTF-8 bytes
- 8 bytes: from_amount (double)
- 8 bytes: to_amount (double)
- 1 byte: payin_address length + UTF-8 bytes (ChangeNow deposit address)
- 1 byte: payout_address length + UTF-8 bytes (Client wallet)
- 1 byte: refund_address length + UTF-8 bytes
- 1 byte: flow length + UTF-8 bytes
- 1 byte: type_ length + UTF-8 bytes
- 8 bytes: actual_eth_amount (double)
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC signature
```

**Encryption Method:** `encrypt_gcsplit3_to_gcsplit1_token()`
**Decryption Method:** `decrypt_gcsplit3_to_gcsplit1_token()` (GCSplit1 side)

---

### 3.2 THRESHOLD PAYOUT MODE (USDT Accumulation → Batch Conversion)

**Flow:** `NOWPayments → GCWebhook1 → GCAccumulator → GCSplit3 → GCAccumulator → GCHostPay1 → GCHostPay2 → GCHostPay1 → GCHostPay3 → GCHostPay1 → GCMicroBatchProcessor → GCHostPay1 → GCMicroBatchProcessor → GCBatchProcessor → GCSplit1`

#### Token 8: GCAccumulator → GCSplit3 (ETH→USDT Swap Request)
**Purpose:** Convert accumulated ETH to USDT
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCAccumulator-10-26/token_manager.py:131-194`

**Structure:**
```
- 8 bytes: accumulation_id (uint64)
- 1 byte: client_id length + UTF-8 bytes
- 8 bytes: eth_amount (double)
- 1 byte: usdt_wallet_address length + UTF-8 bytes (platform wallet)
- 8 bytes: timestamp (uint64)
- 16 bytes: HMAC signature
```

**Encryption Method:** `encrypt_accumulator_to_gcsplit3_token()`

---

#### Token 9: GCSplit3 → GCAccumulator (ETH→USDT Swap Response)
**Purpose:** Return ChangeNow transaction details
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCAccumulator-10-26/token_manager.py:196-290`

**Structure:**
```
- 8 bytes: accumulation_id (uint64)
- 1 byte: client_id length + UTF-8 bytes
- 1 byte: cn_api_id length + UTF-8 bytes
- 8 bytes: from_amount (double, ETH)
- 8 bytes: to_amount (double, USDT)
- 1 byte: payin_address length + UTF-8 bytes
- 1 byte: payout_address length + UTF-8 bytes
- 8 bytes: timestamp (uint64)
- 16 bytes: HMAC signature
```

**Decryption Method:** `decrypt_gcsplit3_to_accumulator_token()`

---

#### Token 10: GCAccumulator → GCHostPay1 (Swap Execution Request)
**Purpose:** Execute ETH payment to ChangeNow
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCAccumulator-10-26/token_manager.py:296-378`

**Structure:**
```
- 8 bytes: accumulation_id (uint64)
- 1 byte: cn_api_id length + UTF-8 bytes
- 1 byte: from_currency length + UTF-8 bytes
- 1 byte: from_network length + UTF-8 bytes
- 8 bytes: from_amount (double)
- 1 byte: payin_address length + UTF-8 bytes
- 1 byte: context length + UTF-8 bytes [NEW: 'threshold']
- 8 bytes: timestamp (uint64)
- 16 bytes: HMAC signature
```

**Encryption Method:** `encrypt_accumulator_to_gchostpay1_token()`
**Decryption Method:** `decrypt_accumulator_to_gchostpay1_token()` (GCHostPay1 side)

---

#### Token 11-15: GCHostPay Internal Flow

**GCHostPay services use 5 internal tokens:**

1. **GCSplit1 → GCHostPay1** (Instant payout path)
   - Uses TPS_HOSTPAY_SIGNING_KEY (external boundary)
   - Includes actual_eth_amount + estimated_eth_amount

2. **GCHostPay1 → GCHostPay2** (Status check request)
   - Uses SUCCESS_URL_SIGNING_KEY (internal)
   - Includes full payment details for passthrough

3. **GCHostPay2 → GCHostPay1** (Status check response)
   - Uses SUCCESS_URL_SIGNING_KEY (internal)
   - Returns ChangeNow status + payment details

4. **GCHostPay1 → GCHostPay3** (Payment execution)
   - Uses SUCCESS_URL_SIGNING_KEY (internal)
   - Includes context field ('instant' or 'threshold')

5. **GCHostPay3 → GCHostPay1** (Payment response)
   - Uses SUCCESS_URL_SIGNING_KEY (internal)
   - Returns Ethereum transaction hash + gas details

**Files:**
- `GCHostPay1-10-26/token_manager.py:74-1264` (All 5 token types)
- `GCHostPay2-10-26/token_manager.py` (Uses GCHostPay1's patterns)
- `GCHostPay3-10-26/token_manager.py` (Uses GCHostPay1's patterns)

---

#### Token 16: GCMicroBatchProcessor → GCHostPay1 (Batch Execution)
**Purpose:** Execute micro-batch ETH payment
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCMicroBatchProcessor-10-26/token_manager.py:44-104`

**Structure:**
```
- 1 byte: context length + UTF-8 bytes ('batch')
- 1 byte: batch_conversion_id length + UTF-8 bytes (UUID)
- 1 byte: cn_api_id length + UTF-8 bytes
- 1 byte: from_currency length + UTF-8 bytes
- 1 byte: from_network length + UTF-8 bytes
- 8 bytes: from_amount (double)
- 1 byte: payin_address length + UTF-8 bytes
- 8 bytes: timestamp (uint64)
- 16 bytes: HMAC signature
```

**Encryption Method:** `encrypt_microbatch_to_gchostpay1_token()`

---

#### Token 17: GCHostPay1 → GCMicroBatchProcessor (Batch Response)
**Purpose:** Return USDT conversion results
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCHostPay1-10-26/token_manager.py:1056-1122`

**Structure:**
```
- 1 byte: batch_conversion_id length + UTF-8 bytes
- 1 byte: cn_api_id length + UTF-8 bytes
- 1 byte: tx_hash length + UTF-8 bytes
- 8 bytes: actual_usdt_received (double)
- 8 bytes: timestamp (uint64)
- 16 bytes: HMAC signature
```

**Encryption Method:** `encrypt_gchostpay1_to_microbatch_response_token()`
**Decryption Method:** `decrypt_gchostpay1_to_microbatch_token()` (GCMicroBatch side)

---

#### Token 18: GCBatchProcessor → GCSplit1 (Batch Payout Request)
**Purpose:** Final batch payout to client
**Signing Key:** TPS_HOSTPAY_SIGNING_KEY (crossing boundary)
**File:** `GCBatchProcessor-10-26/token_manager.py:28-93`

**Structure (JSON-based token):**
```json
{
  "batch_id": str,
  "client_id": str,
  "wallet_address": str,
  "payout_currency": str,
  "payout_network": str,
  "amount_usdt": str,
  "actual_eth_amount": float
}
```

**Note:** This is the ONLY JSON-based token in the system (not binary packed)

**Encryption Method:** `encrypt_batch_token()`
**Decryption Method:** `decrypt_batch_token()` (GCSplit1 side)

---

#### Token 19: GCHostPay1 Retry Token (Internal Delayed Callback)
**Purpose:** Self-callback for ChangeNow status recheck
**Signing Key:** SUCCESS_URL_SIGNING_KEY
**File:** `GCHostPay1-10-26/token_manager.py:1128-1263`

**Structure:**
```
- 1 byte: unique_id length + UTF-8 bytes
- 1 byte: cn_api_id length + UTF-8 bytes
- 1 byte: tx_hash length + UTF-8 bytes
- 1 byte: context length + UTF-8 bytes ('batch' or 'threshold')
- 4 bytes: retry_count (uint32)
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC signature
```

**Expiration:** 24 hours (longest window in system, accommodates full retry cycle)

**Encryption Method:** `encrypt_gchostpay1_retry_token()`
**Decryption Method:** `decrypt_gchostpay1_retry_token()`

---

## 4. Security Analysis

### 4.1 Strengths

✅ **HMAC-SHA256 Signature Validation**
- Prevents token tampering
- 16-byte truncation provides 128-bit security
- Constant-time comparison prevents timing attacks

✅ **Timestamp-Based Expiration**
- Tokens have limited validity windows
- Prevents replay attacks beyond expiration
- Different windows for different use cases (60s to 24h)

✅ **Base64 URL-Safe Encoding**
- Tokens can be safely transmitted in URLs and JSON
- No special character escaping needed

✅ **Binary Struct Packing**
- Space-efficient (vs JSON)
- Type-safe unpacking with validation
- Fixed-width fields for predictable parsing

✅ **Length-Prefixed Strings**
- Prevents buffer overflow attacks
- Max 255 bytes per field enforced

✅ **Key Separation (TPS_HOSTPAY vs SUCCESS_URL)**
- Different keys for external vs internal boundaries
- Limits blast radius if one key compromised

### 4.2 Potential Vulnerabilities

⚠️ **Single Point of Failure**
- If SUCCESS_URL_SIGNING_KEY is compromised, entire system vulnerable
- **Mitigation:** Store in Secret Manager with strict IAM policies

⚠️ **No Token Revocation Mechanism**
- Tokens remain valid until expiration
- Cannot invalidate a leaked token before expiry
- **Mitigation:** Short expiration windows (most are <5 minutes)

⚠️ **Timestamp Skew Sensitivity**
- Services must have synchronized clocks
- Large time drift could cause false expirations
- **Mitigation:** Cloud Run uses Google's NTP infrastructure

⚠️ **No Version Field in Tokens**
- Backward compatibility relies on optional field checking
- Token format changes require careful ordering
- **Mitigation:** Current system uses safe defaults for missing fields

⚠️ **HMAC Truncation to 16 Bytes**
- Reduces security from 256-bit to 128-bit
- Still cryptographically secure but lower margin
- **Trade-off:** Saves 16 bytes per token for space efficiency

### 4.3 Field Ordering Bug (Session 66)

**Issue:** GCSplit2→GCSplit1 token decryption had incorrect field ordering
**Impact:** Complete data corruption, token decryption failures
**Root Cause:** Binary struct unpacking order didn't match packing order
**Fix:** Reordered field extraction in `decrypt_gcsplit2_to_gcsplit1_token()`

**Lesson Learned:**
- Binary token formats require exact packing/unpacking symmetry
- No automated validation caught this during deployment
- Recommendation: Add unit tests for encrypt/decrypt roundtrips

---

## 5. Token Flow Diagrams

### 5.1 Instant Payout Flow

```
NOWPayments (Webhook)
    │
    │ [Token 1: Success URL Token]
    ↓
GCWebhook1 (Payment Processor)
    │
    ├─────────────────────────────┬────────────────────────────┐
    │                             │                            │
    │ [Token 2: Telegram Invite]  │ [Token 3: Payment Split]  │
    ↓                             ↓                            │
GCWebhook2                    GCSplit1 (Orchestrator)         │
    │                             │                            │
    │ [Telegram API]              │ [Token 4: Estimate Req]    │
    ↓                             ↓                            │
  User Invited                GCSplit2 (Estimator)            │
                                  │                            │
                                  │ [Token 5: Estimate Resp]   │
                                  ↓                            │
                              GCSplit1 (Orchestrator)          │
                                  │                            │
                                  │ [Token 6: Swap Request]    │
                                  ↓                            │
                              GCSplit3 (Swap Executor)         │
                                  │                            │
                                  │ [ChangeNow API]            │
                                  │ [Token 7: Swap Response]   │
                                  ↓                            │
                              GCSplit1 (Orchestrator)          │
                                  │                            │
                                  │ [Token: HostPay Request]   │
                                  ↓                            │
                              GCHostPay1/2/3 ──────────────────┘
                                  │
                                  │ [Ethereum Blockchain]
                                  ↓
                              Payment Complete
```

### 5.2 Threshold Payout Flow

```
NOWPayments (Webhook)
    │
    │ [Token 1: Success URL Token]
    ↓
GCWebhook1 (Payment Processor)
    │
    │ [Accumulation Logic]
    ↓
GCAccumulator (Threshold Aggregator)
    │
    │ [Token 8: ETH→USDT Swap Request]
    ↓
GCSplit3 (Swap Executor)
    │
    │ [ChangeNow API: ETH→USDT]
    │ [Token 9: Swap Response]
    ↓
GCAccumulator (Threshold Aggregator)
    │
    │ [Token 10: Execution Request]
    ↓
GCHostPay1 (ETH Payment Orchestrator)
    │
    ├─────────────────────┬─────────────────────┐
    │ [Token 11]          │ [Token 13]          │
    ↓                     ↓                     │
GCHostPay2          GCHostPay3                 │
    │ [Status Check]      │ [ETH Payment]       │
    │ [Token 12]          │ [Token 14]          │
    └─────────────────────┴─────────────────────┘
                          │
                          ↓
                    GCMicroBatchProcessor
                          │
                          │ [Token 16: Batch Execution]
                          ↓
                      GCHostPay1
                          │
                          │ [Token 17: Batch Response]
                          ↓
                    GCMicroBatchProcessor
                          │
                          │ [USDT Accumulation]
                          ↓
                    GCBatchProcessor
                          │
                          │ [Token 18: Final Payout]
                          ↓
                      GCSplit1 → GCSplit2 → GCSplit3
                          │
                          │ [Final Client Payout]
                          ↓
                    Client Wallet
```

---

## 6. Service-to-Service Token Usage Matrix

| Source Service | Target Service | Token Type | Signing Key | File Location |
|---------------|---------------|-----------|-------------|---------------|
| NOWPayments | GCWebhook1 | Success URL | SUCCESS_URL_SIGNING_KEY | GCWebhook1/token_manager.py:29 |
| GCWebhook1 | GCWebhook2 | Telegram Invite | SUCCESS_URL_SIGNING_KEY | GCWebhook1/token_manager.py:174 |
| GCWebhook1 | GCSplit1 | Payment Split | Cloud Tasks JSON | GCWebhook1/cloudtasks_client.py:138 |
| GCSplit1 | GCSplit2 | Estimate Request | SUCCESS_URL_SIGNING_KEY | GCSplit1/token_manager.py:70 |
| GCSplit2 | GCSplit1 | Estimate Response | SUCCESS_URL_SIGNING_KEY | GCSplit2/token_manager.py:266 |
| GCSplit1 | GCSplit3 | Swap Request | SUCCESS_URL_SIGNING_KEY | GCSplit1/token_manager.py:477 |
| GCSplit3 | GCSplit1 | Swap Response | SUCCESS_URL_SIGNING_KEY | GCSplit1/token_manager.py:658 |
| GCSplit1 | GCHostPay1 | Instant Payout | TPS_HOSTPAY_SIGNING_KEY | GCHostPay1/token_manager.py:74 |
| GCAccumulator | GCSplit3 | ETH→USDT Swap | SUCCESS_URL_SIGNING_KEY | GCAccumulator/token_manager.py:131 |
| GCSplit3 | GCAccumulator | Swap Response | SUCCESS_URL_SIGNING_KEY | GCAccumulator/token_manager.py:196 |
| GCAccumulator | GCHostPay1 | Execution Request | SUCCESS_URL_SIGNING_KEY | GCAccumulator/token_manager.py:296 |
| GCHostPay1 | GCHostPay2 | Status Check | SUCCESS_URL_SIGNING_KEY | GCHostPay1/token_manager.py:356 |
| GCHostPay2 | GCHostPay1 | Status Response | SUCCESS_URL_SIGNING_KEY | GCHostPay1/token_manager.py:504 |
| GCHostPay1 | GCHostPay3 | Payment Execution | SUCCESS_URL_SIGNING_KEY | GCHostPay1/token_manager.py:660 |
| GCHostPay3 | GCHostPay1 | Payment Response | SUCCESS_URL_SIGNING_KEY | GCHostPay1/token_manager.py:804 |
| GCMicroBatch | GCHostPay1 | Batch Execution | SUCCESS_URL_SIGNING_KEY | GCMicroBatch/token_manager.py:44 |
| GCHostPay1 | GCMicroBatch | Batch Response | SUCCESS_URL_SIGNING_KEY | GCHostPay1/token_manager.py:1056 |
| GCBatchProcessor | GCSplit1 | Final Payout | TPS_HOSTPAY_SIGNING_KEY | GCBatchProcessor/token_manager.py:28 |
| GCHostPay1 | GCHostPay1 | Retry Callback | SUCCESS_URL_SIGNING_KEY | GCHostPay1/token_manager.py:1128 |

**Total Token Types:** 19
**Total Services:** 13
**Total Service-to-Service Connections:** 19

---

## 7. Key Findings and Recommendations

### 7.1 Current State Assessment

✅ **Well-Architected Security**
- HMAC signatures prevent tampering
- Timestamp expiration limits replay attacks
- Key separation for different trust domains

✅ **Consistent Implementation Pattern**
- All services follow same TokenManager pattern
- Binary packing for efficiency
- Base64 URL-safe encoding

✅ **Comprehensive Coverage**
- 19 distinct token types
- Covers all service-to-service communication
- Both instant and threshold payout modes supported

⚠️ **Recent Critical Fix Applied**
- Session 66 fixed field ordering bug in GCSplit1→GCSplit2 token
- Bug caused complete data corruption
- Fix verified and deployed

### 7.2 Recommendations

**1. Add Token Versioning**
```python
# Add version byte to all tokens
packed_data.extend(bytes([TOKEN_VERSION]))  # 0x01, 0x02, etc.
```
**Benefit:** Enables format changes without breaking backward compatibility

**2. Implement Unit Tests for Token Roundtrips**
```python
def test_token_encrypt_decrypt_roundtrip():
    token_manager = TokenManager(signing_key)
    encrypted = token_manager.encrypt_xxx_token(...)
    decrypted = token_manager.decrypt_xxx_token(encrypted)
    assert decrypted == original_data
```
**Benefit:** Catches field ordering bugs before deployment

**3. Add Structured Logging for Token Events**
```python
logger.info("token_created", token_type="gcsplit1_to_gcsplit2",
            service="gcsplit1", user_id=user_id, token_length=len(token))
```
**Benefit:** Better observability for debugging token issues

**4. Consider Key Rotation Strategy**
- Store key version in Secret Manager metadata
- Support multiple active keys during rotation period
- Update services to try both old and new keys during transition

**5. Add Token Introspection Tool**
```python
def introspect_token(token: str, signing_key: str) -> dict:
    """Decode token and show structure without validating timestamp"""
    # Useful for debugging expired tokens
```
**Benefit:** Faster debugging of token-related issues

---

## 8. Appendix: Complete File Reference

### 8.1 Token Manager Files

```
/OCTOBER/10-26/GCWebhook1-10-26/token_manager.py
/OCTOBER/10-26/GCWebhook2-10-26/token_manager.py
/OCTOBER/10-26/GCSplit1-10-26/token_manager.py
/OCTOBER/10-26/GCSplit2-10-26/token_manager.py
/OCTOBER/10-26/GCSplit3-10-26/token_manager.py
/OCTOBER/10-26/GCHostPay1-10-26/token_manager.py
/OCTOBER/10-26/GCHostPay2-10-26/token_manager.py
/OCTOBER/10-26/GCHostPay3-10-26/token_manager.py
/OCTOBER/10-26/GCAccumulator-10-26/token_manager.py
/OCTOBER/10-26/GCBatchProcessor-10-26/token_manager.py
/OCTOBER/10-26/GCMicroBatchProcessor-10-26/token_manager.py
```

### 8.2 Config Manager Files (Secret Fetching)

```
/OCTOBER/10-26/GCWebhook1-10-26/config_manager.py
/OCTOBER/10-26/GCWebhook2-10-26/config_manager.py
/OCTOBER/10-26/GCSplit1-10-26/config_manager.py
/OCTOBER/10-26/GCSplit2-10-26/config_manager.py
/OCTOBER/10-26/GCSplit3-10-26/config_manager.py
/OCTOBER/10-26/GCHostPay1-10-26/config_manager.py
/OCTOBER/10-26/GCHostPay2-10-26/config_manager.py
/OCTOBER/10-26/GCHostPay3-10-26/config_manager.py
/OCTOBER/10-26/GCAccumulator-10-26/config_manager.py
/OCTOBER/10-26/GCBatchProcessor-10-26/config_manager.py
/OCTOBER/10-26/GCMicroBatchProcessor-10-26/config_manager.py
```

### 8.3 Cloud Tasks Clients (Token Enqueuing)

```
/OCTOBER/10-26/GCWebhook1-10-26/cloudtasks_client.py
/OCTOBER/10-26/GCSplit1-10-26/cloudtasks_client.py
/OCTOBER/10-26/GCSplit2-10-26/cloudtasks_client.py
/OCTOBER/10-26/GCSplit3-10-26/cloudtasks_client.py
/OCTOBER/10-26/GCHostPay1-10-26/cloudtasks_client.py
/OCTOBER/10-26/GCHostPay3-10-26/cloudtasks_client.py
/OCTOBER/10-26/GCAccumulator-10-26/cloudtasks_client.py
/OCTOBER/10-26/GCMicroBatchProcessor-10-26/cloudtasks_client.py
```

---

**Document Version:** 1.0
**Last Updated:** 2025-11-07
**Total Services Analyzed:** 13
**Total Token Types Documented:** 19
**Critical Bugs Identified:** 1 (Session 66 field ordering, now fixed)
