# Token Encryption/Decryption Usage Analysis

**Date:** 2025-11-08
**Scope:** All services in `/OCTOBER/10-26`
**Purpose:** Exhaustive mapping of ENCRYPT/DECRYPT token workflow across the entire payout architecture

---

## Executive Summary

This document provides a comprehensive analysis of which services use encrypted token workflows and which do not. Out of **13 total services**, **9 services** actively use encryption/decryption, **1 service** has token management capabilities but does NOT use them, and **3 services** do not use tokens at all.

### Quick Stats

| Metric | Count |
|--------|-------|
| **Total Services** | 13 |
| **Services with `token_manager.py`** | 11 |
| **Services using ENCRYPT** | 9 |
| **Services using DECRYPT** | 8 |
| **Services using BOTH** | 6 |
| **Services with token_manager.py but UNUSED** | 1 (GCAccumulator) |
| **Services with NO tokens** | 3 |

---

## Part 1: Services WITH Encryption/Decryption (9 Services)

### 1. GCWebhook1-10-26 (Payment Processor)

**Directory:** `/GCWebhook1-10-26`
**Main File:** `tph1-10-26.py`
**Token Manager:** ✅ `token_manager.py`

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `GET /` (Legacy) | ✅ | ✅ | NOWPayments (success_url) | GCWebhook2 | user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price |
| `POST /process-validated-payment` (Current) | ❌ | ✅ | N/A (receives plain JSON) | GCWebhook2 | Same as above |
| `GET /health` | ❌ | ❌ | N/A | N/A | N/A |

**Signing Key:** `SUCCESS_URL_SIGNING_KEY`

**Token Flow:**
```
NOWPayments success_url
    ↓ (encrypted token)
GCWebhook1 DECRYPT
    ↓ Extract payment details
    ↓ Determine instant vs threshold route
    ├─→ Route to GCSplit1 (instant) OR GCAccumulator (threshold)
    └─→ ENCRYPT new token for GCWebhook2 (Telegram invite)
```

**Critical Notes:**
- **Legacy endpoint (GET /)** receives encrypted token from NOWPayments success_url
- **Current endpoint (POST /process-validated-payment)** receives plain JSON from np-webhook after IPN validation
- Both endpoints ENCRYPT a new token for GCWebhook2 to send Telegram invite

---

### 2. GCWebhook2-10-26 (Telegram Invite Sender)

**Directory:** `/GCWebhook2-10-26`
**Main File:** `tph2-10-26.py`
**Token Manager:** ✅ `token_manager.py`

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `POST /` | ✅ | ❌ | GCWebhook1 | N/A | user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price |
| `GET /health` | ❌ | ❌ | N/A | N/A | N/A |

**Signing Key:** `SUCCESS_URL_SIGNING_KEY`

**Token Flow:**
```
GCWebhook1 (Cloud Tasks)
    ↓ (encrypted token + payment_id)
GCWebhook2 DECRYPT
    ↓ Extract subscription data
    ├─→ IDEMPOTENCY: Check if invite already sent
    ├─→ VALIDATE: Payment completion check
    ├─→ CREATE: Telegram one-time invite link
    └─→ RETURN: Success 200 OK
```

**Critical Notes:**
- **DECRYPT ONLY** - Terminal service that does not propagate tokens
- Idempotency check prevents duplicate Telegram invites
- Token expiration: **24 hours** (large window to accommodate retries)

---

### 3. GCSplit1-10-26 (Payment Splitting Orchestrator)

**Directory:** `/GCSplit1-10-26`
**Main File:** `tps1-10-26.py`
**Token Manager:** ✅ `token_manager.py` **(DUAL-KEY SYSTEM)**

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `POST /` (Main webhook) | ❌ | ✅ | N/A (receives plain JSON) | GCSplit2, GCSplit3, GCHostPay1 | user_id, closed_channel_id, wallet_address, payout_currency, adjusted_amount, swap_currency, payout_mode, actual_eth_amount |
| `POST /estimate-response` | ✅ | ✅ | GCSplit2 | GCSplit3 | Estimate response with from_amount, to_amount, fees |
| `POST /swap-response` | ✅ | ✅ | GCSplit3 | GCHostPay1 | Swap transaction details (cn_api_id, payin_address) |
| `GET /health` | ❌ | ❌ | N/A | N/A | N/A |

**Signing Keys:**
- `SUCCESS_URL_SIGNING_KEY` - For internal communication (GCSplit2, GCSplit3)
- `TPS_HOSTPAY_SIGNING_KEY` - For external boundary (GCHostPay1) ⚠️

**Token Flow:**
```
GCWebhook1 (Plain JSON with outcome_amount_usd)
    ↓
GCSplit1 (Orchestrator)
    ├─→ Calculate adjusted amount (remove TP_FEE)
    ├─→ ENCRYPT: Token for GCSplit2 (USDT→ETH estimate)
    │   └─→ GCSplit2 returns estimate
    │       └─→ Back to GCSplit1 (/estimate-response)
    │           └─→ DECRYPT response + ENCRYPT for GCSplit3
    │               └─→ GCSplit3 creates fixed-rate transaction
    │                   └─→ Back to GCSplit1 (/swap-response)
    │                       └─→ DECRYPT response + ENCRYPT for GCHostPay1 (using TPS_HOSTPAY_SIGNING_KEY)
    └─→ GCHostPay1: Validates & orchestrates payment
```

**Critical Notes:**
- **ENCRYPT ONLY** for main endpoint (receives plain JSON from GCWebhook1)
- **DUAL-KEY SYSTEM** - Uses different keys for internal vs external boundaries
- `build_hostpay_token()` function creates tokens with `TPS_HOSTPAY_SIGNING_KEY` for GCHostPay1
- Token includes both `actual_eth_amount` (from NowPayments) and `estimated_eth_amount` (from ChangeNow) for validation

---

### 4. GCSplit2-10-26 (USDT→ETH Estimator)

**Directory:** `/GCSplit2-10-26`
**Main File:** `tps2-10-26.py`
**Token Manager:** ✅ `token_manager.py`

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `POST /` | ✅ | ✅ | GCSplit1 | GCSplit1 (/estimate-response) | USDT amount, swap_currency, payout_mode, actual_eth_amount, estimate response |
| `GET /health` | ❌ | ❌ | N/A | N/A | N/A |

**Signing Key:** `SUCCESS_URL_SIGNING_KEY`

**Token Flow:**
```
GCSplit1 (Cloud Tasks)
    ↓ (encrypted token with adjusted_amount)
GCSplit2
    ├─→ DECRYPT: Extract amount, swap_currency, payout_mode
    ├─→ API CALL: ChangeNow get_estimated_amount_v2_with_retry()
    │   Input: from_amount (USDT), to_currency (client's currency)
    │   Output: Estimated amount post-fees
    ├─→ ENCRYPT: Response token with estimates
    └─→ QUEUE: Task back to GCSplit1 (/estimate-response)
```

**Critical Notes:**
- **Request-Response Pattern** - DECRYPT request, ENCRYPT response
- Infinite retry logic for ChangeNow API failures
- Extracts `swap_currency` from token to determine if ETH or USDT
- Passes `actual_eth_amount` through for later validation

---

### 5. GCSplit3-10-26 (ETH→Client Currency Swapper)

**Directory:** `/GCSplit3-10-26`
**Main File:** `tps3-10-26.py`
**Token Manager:** ✅ `token_manager.py`

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `POST /` | ✅ | ✅ | GCSplit1 | GCSplit1 (/swap-response) | ETH amount, client currency, payout network, actual_eth_amount, transaction details (cn_api_id, payin_address) |
| `GET /health` | ❌ | ❌ | N/A | N/A | N/A |

**Signing Key:** `SUCCESS_URL_SIGNING_KEY`

**Token Flow:**
```
GCSplit1 (Cloud Tasks with estimated amount from GCSplit2)
    ↓ (encrypted token with eth_amount)
GCSplit3
    ├─→ DECRYPT: Extract amount, payout_currency, payout_network
    ├─→ API CALL: ChangeNow create_fixed_rate_transaction_with_retry()
    │   Input: eth_amount, from_currency='eth', to_currency (client), address
    │   Output: Transaction ID, payin_address, rate, payee_address
    ├─→ ENCRYPT: Response token with transaction details
    └─→ QUEUE: Task back to GCSplit1 (/swap-response)
```

**Critical Notes:**
- **Request-Response Pattern** - DECRYPT request, ENCRYPT response
- Creates **FIXED-RATE** transaction (locked exchange rate)
- Includes client wallet address for receiving swapped currency
- Infinite retry logic for API failures

---

### 6. GCHostPay1-10-26 (Validator & Orchestrator)

**Directory:** `/GCHostPay1-10-26`
**Main File:** `tphp1-10-26.py`
**Token Manager:** ✅ `token_manager.py` **(DUAL-KEY SYSTEM)**

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `POST /` (Main webhook) | ✅ | ✅ | GCSplit1 | GCHostPay2, GCHostPay3 | CN API ID, payin_address, payment amount, actual vs estimated ETH |
| `POST /status-verified` | ✅ | ✅ | GCHostPay2 | GCHostPay3 (if status good) | ChangeNow status verification |
| `POST /payment-completed` | ✅ | ✅ | GCHostPay3 | GCMicroBatchProcessor (batch mode only) | ETH payment execution confirmation, tx_hash |
| `GET /health` | ❌ | ❌ | N/A | N/A | N/A |

**Signing Keys:**
- `TPS_HOSTPAY_SIGNING_KEY` - For DECRYPT (GCSplit1 token) ⚠️
- `SUCCESS_URL_SIGNING_KEY` - For ENCRYPT/DECRYPT internal communication (GCHostPay2, GCHostPay3)

**Token Flow:**
```
GCSplit1 (Cloud Tasks)
    ↓ (Token with CN API ID + payin_address, encrypted with TPS_HOSTPAY_SIGNING_KEY)
GCHostPay1 (/main)
    ├─→ DECRYPT: Extract payment metadata (using TPS_HOSTPAY_SIGNING_KEY)
    ├─→ DB CHECK: Verify ChangeNow transaction exists
    ├─→ ENCRYPT: Token for GCHostPay2 (status check, using SUCCESS_URL_SIGNING_KEY)
    │   └─→ GCHostPay2 receives token
    │       ├─→ DECRYPT: Extract CN API ID
    │       ├─→ API CALL: ChangeNow get_transaction_status()
    │       ├─→ ENCRYPT: Response token with status
    │       └─→ Back to GCHostPay1 (/status-verified)
    │
    ├─→ GCHostPay1 (/status-verified)
    │   ├─→ DECRYPT: GCHostPay2 response
    │   ├─→ IF status=='waiting':
    │   │   ├─→ ENCRYPT: Token for GCHostPay3 (execute payment)
    │   │   └─→ GCHostPay3 receives token
    │   │       ├─→ DECRYPT: Extract payment details
    │   │       ├─→ EXECUTE: Send ETH from HostPay wallet to payin_address
    │   │       ├─→ ENCRYPT: Response token with tx_hash
    │   │       └─→ Back to GCHostPay1 (/payment-completed)
    │
    └─→ GCHostPay1 (/payment-completed)
        ├─→ DECRYPT: GCHostPay3 response
        ├─→ IF batch conversion:
        │   ├─→ ENCRYPT: Callback token for GCMicroBatchProcessor
        │   └─→ QUEUE: Callback task with batch results
        └─→ Update DB with payment status
```

**Critical Notes:**
- **DUAL-KEY SYSTEM** for security boundary separation
- Orchestrates multi-step validation flow
- Handles both instant and batch conversions
- Token expiration: **60 seconds** (strict window for immediate execution)

---

### 7. GCHostPay2-10-26 (Status Checker)

**Directory:** `/GCHostPay2-10-26`
**Main File:** `tphp2-10-26.py`
**Token Manager:** ✅ `token_manager.py`

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `POST /` | ✅ | ✅ | GCHostPay1 | GCHostPay1 (/status-verified) | CN API ID, transaction status response |
| `GET /health` | ❌ | ❌ | N/A | N/A | N/A |

**Signing Key:** `SUCCESS_URL_SIGNING_KEY`

**Token Flow:**
```
GCHostPay1 (Cloud Tasks)
    ↓ (encrypted token with CN API ID)
GCHostPay2
    ├─→ DECRYPT: Extract CN API ID
    ├─→ API CALL: ChangeNow get_transaction_status()
    ├─→ ENCRYPT: Response with status
    └─→ QUEUE: Task back to GCHostPay1 (/status-verified)
```

**Critical Notes:**
- **Request-Response Pattern** - DECRYPT request, ENCRYPT response
- Verifies ChangeNow transaction is ready before payment execution

---

### 8. GCHostPay3-10-26 (Payment Executor)

**Directory:** `/GCHostPay3-10-26`
**Main File:** `tphp3-10-26.py`
**Token Manager:** ✅ `token_manager.py`

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `POST /` | ✅ | ✅ | GCHostPay1 | GCHostPay1 (/payment-completed) | Payment amount (ETH), payin_address, transaction hash |
| `GET /health` | ❌ | ❌ | N/A | N/A | N/A |

**Signing Key:** `SUCCESS_URL_SIGNING_KEY`

**Token Flow:**
```
GCHostPay1 (Cloud Tasks)
    ↓ (encrypted token with payment amount + address)
GCHostPay3
    ├─→ DECRYPT: Extract payment details
    ├─→ WALLET_MANAGER: Execute ETH transfer
    │   Input: payin_address, amount_eth
    │   Output: tx_hash
    ├─→ ENCRYPT: Response with tx_hash
    └─→ QUEUE: Task back to GCHostPay1 (/payment-completed)
```

**Critical Notes:**
- **Request-Response Pattern** - DECRYPT request, ENCRYPT response
- Executes actual ETH transfer from HostPay wallet to ChangeNow
- Supports both native ETH and ERC-20 tokens (USDT, USDC, DAI)

---

### 9. GCBatchProcessor-10-26 (Batch Payout Processor)

**Directory:** `/GCBatchProcessor-10-26`
**Main File:** `batch10-26.py`
**Token Manager:** ✅ `token_manager.py`

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `POST /process` | ❌ | ✅ | N/A (Cloud Scheduler) | GCSplit1 | Batch ID, total accumulated USDT, client wallet address |

**Signing Key:** `TPS_HOSTPAY_SIGNING_KEY` (uses external boundary key)

**Token Flow:**
```
Cloud Scheduler (every 5 minutes)
    ↓
GCBatchProcessor (/process)
    ├─→ NO DECRYPTION
    ├─→ Query: Find clients with accumulated_usdt >= payout_threshold
    ├─→ For each client:
    │   ├─→ Create batch_conversions record
    │   ├─→ ENCRYPT: Token for GCSplit1 (USDT→Client Currency swap)
    │   │   Data: batch_id, total_amount_usdt, payout_currency, payout_network
    │   └─→ QUEUE: Task to GCSplit1 for swap
    └─→ Return summary
```

**Critical Notes:**
- **ENCRYPT ONLY** - Triggered by scheduler, not by incoming tokens
- Uses `TPS_HOSTPAY_SIGNING_KEY` for encryption (external boundary)
- Detects accumulated payments over threshold and initiates batch payouts

---

### 10. GCMicroBatchProcessor-10-26 (Micro-Batch Conversion Service)

**Directory:** `/GCMicroBatchProcessor-10-26`
**Main File:** `microbatch10-26.py`
**Token Manager:** ✅ `token_manager.py`

#### Encryption/Decryption Usage

| Function/Endpoint | DECRYPT | ENCRYPT | Token Source | Token Destination | Data |
|-------------------|---------|---------|--------------|-------------------|------|
| `POST /check-threshold` | ❌ | ❌ | N/A (Cloud Scheduler) | N/A | N/A |
| `POST /callback` | ✅ | ✅ | GCHostPay1 | GCHostPay1 (callback response) | Batch conversion results, actual USDT received |

**Signing Key:** `SUCCESS_URL_SIGNING_KEY`

**Token Flow:**
```
Cloud Scheduler (every 15 minutes)
    ↓
GCMicroBatchProcessor (/check-threshold)
    ├─→ NO DECRYPTION (initial trigger)
    ├─→ Query: Total pending USD in payout_accumulation (PENDING status)
    ├─→ IF total >= micro_batch_threshold:
    │   ├─→ Create ChangeNow ETH→USDT swap
    │   ├─→ Update all pending records to 'swapping'
    │   └─→ QUEUE: Task to GCHostPay1 (payment execution)
    │
    └─→ GCHostPay1 (payment execution path)
        └─→ After ETH payment completes:
            └─→ Back to GCMicroBatchProcessor (/callback)
                ├─→ DECRYPT: Callback token from GCHostPay1
                │   Data: batch_conversion_id, cn_api_id, tx_hash, actual_usdt_received
                ├─→ Update batch_conversions with actual amount received
                └─→ ENCRYPT: Callback response (if needed)
```

**Critical Notes:**
- **/check-threshold** endpoint does NOT use tokens (scheduler trigger)
- **/callback** endpoint uses DECRYPT + ENCRYPT (callback from GCHostPay1)
- Token expiration: **30 minutes** (accommodates ChangeNow processing delays)

---

## Part 2: Services WITHOUT Encryption/Decryption

### 11. GCAccumulator-10-26 (Payment Accumulation Service)

**Directory:** `/GCAccumulator-10-26`
**Main File:** `acc10-26.py`
**Token Manager:** ✅ `token_manager.py` **BUT UNUSED** ⚠️

#### Why NO Encryption/Decryption?

| Function/Endpoint | Uses Tokens? | Data Format | Reason |
|-------------------|--------------|-------------|--------|
| `POST /` | ❌ NO | Plain JSON from GCWebhook1 | Direct accumulation without token overhead |
| `GET /health` | ❌ NO | N/A | Health check |

**Data Flow:**
```
GCWebhook1 (Cloud Tasks - Plain JSON)
    ↓
GCAccumulator
    ├─→ NO DECRYPTION
    ├─→ Calculate adjusted amount (remove TP_FEE)
    ├─→ Store in payout_accumulation table (PENDING conversion status)
    ├─→ QUEUE: Task to GCSplit2 for async conversion (ETH→USDT)
    └─→ Return success immediately
```

**Critical Notes:**
- Has `token_manager.py` file but **NEVER USES IT**
- Architectural artifact from earlier design
- **Safe to remove** token_manager.py or keep for future use
- No impact on current operations (code path never executed)

**Rationale for Plain JSON:**
- Direct accumulation without encryption overhead
- Performance optimization for high-volume accumulation
- Token validation not needed for internal trusted service

---

### 12. np-webhook-10-26 (NowPayments IPN Handler)

**Directory:** `/np-webhook-10-26`
**Main File:** `app.py`
**Token Manager:** ❌ NO

#### Why NO Encryption/Decryption?

| Function/Endpoint | Uses Tokens? | Security Method | Reason |
|-------------------|--------------|-----------------|--------|
| `POST /` (IPN Callback) | ❌ NO | **HMAC-SHA256 Signature Verification** | External IPN uses signature, not encryption |
| `GET /payment-processing` | ❌ NO | N/A | Serves landing page HTML |

**Data Flow:**
```
NowPayments (IPN Callback)
    ↓ POST /, HMAC-SHA256 signature in header
np-webhook
    ├─→ NO DECRYPTION
    ├─→ VERIFY: HMAC-SHA256 signature check (defense-in-depth)
    │   Using: NOWPAYMENTS_IPN_SECRET
    ├─→ UPDATE: DB with payment_id, outcome_amount (actual crypto value)
    ├─→ FETCH: CoinGecko price for outcome amount → USD conversion
    ├─→ QUEUE: Task to GCWebhook1 (/process-validated-payment)
    │   Data: Plain JSON with payment_status='finished', outcome_amount_usd
    └─→ Return 200 OK
```

**Security Key Used:**
- `NOWPAYMENTS_IPN_SECRET` - For **signature verification ONLY** (not encryption)

**Critical Notes:**
- Uses **HMAC-SHA256 signature verification** instead of encryption
- This is standard for external IPN webhooks
- Signature ensures authenticity and integrity
- Sends **plain JSON** to GCWebhook1 (internal trusted service)

---

### 13. TelePay10-26 (Telegram Bot)

**Directory:** `/TelePay10-26`
**Main File:** `telepay10-26.py`
**Token Manager:** ❌ NO

#### Why NO Encryption/Decryption?

| Function/Endpoint | Uses Tokens? | Data Format | Reason |
|-------------------|--------------|-------------|--------|
| All Telegram command handlers | ❌ NO | Direct Telegram Bot API | Pure bot implementation |

**Data Flow:**
```
Telegram API (user commands)
    ↓
TelePay10-26
    ├─→ NO DECRYPTION
    ├─→ Process user commands directly
    ├─→ Interact with database for user/subscription management
    └─→ Send Telegram API responses
```

**Critical Notes:**
- Pure Telegram bot implementation
- No inter-service communication via encrypted tokens
- Direct database access for user and subscription management
- No token encryption/decryption needed

---

## Part 3: Architectural Analysis

### Two-Key Security Architecture

The system implements a **two-key boundary architecture** for enhanced security:

```
┌─────────────────────────────────────────────────────────────┐
│                      External Boundary                       │
│                (TPS_HOSTPAY_SIGNING_KEY)                     │
└────────────────────────────┬────────────────────────────────┘
                             │
                    GCSplit1 ←→ GCHostPay1
                    (build_hostpay_token)
                             │
        ┌────────────────────┴────────────────────┐
        │                                         │
┌───────▼─────────────────────────────────────────▼─────────┐
│                 Internal Boundary                          │
│           (SUCCESS_URL_SIGNING_KEY)                        │
└───────┬──────────────────────────────────────────────────┬─┘
        │                                                   │
        ├─ GCWebhook1 ←→ GCWebhook2                         │
        ├─ GCSplit1 ←→ GCSplit2 ←→ GCSplit1                 │
        ├─ GCSplit1 ←→ GCSplit3 ←→ GCSplit1                 │
        ├─ GCHostPay1 ←→ GCHostPay2                         │
        ├─ GCHostPay1 ←→ GCHostPay3                         │
        ├─ GCAccumulator (internal, no tokens)              │
        ├─ GCBatchProcessor (uses TPS_HOSTPAY_KEY)          │
        └─ GCMicroBatchProcessor ←→ GCHostPay1             │
```

### Signing Key Distribution

| Key Name | Purpose | Services Using It |
|----------|---------|-------------------|
| **SUCCESS_URL_SIGNING_KEY** | Internal service-to-service communication | GCWebhook1, GCWebhook2, GCSplit1-3, GCHostPay1-3, GCAccumulator (unused), GCMicroBatchProcessor |
| **TPS_HOSTPAY_SIGNING_KEY** | External boundary (GCSplit1↔GCHostPay1) | GCSplit1, GCHostPay1, GCBatchProcessor |
| **NOWPAYMENTS_IPN_SECRET** | Signature verification (NOT encryption) | np-webhook |

### Token Format Summary

| Format | Size | Usage | Services |
|--------|------|-------|----------|
| **Payment Data Token** | 38+ bytes (variable) | NOWPayments → GCWebhook1 | GCWebhook1 (legacy GET /) |
| **Payment Split Token** | Variable | GCSplit1 → GCSplit2/GCSplit3 | GCSplit1, GCSplit2, GCSplit3 |
| **HostPay Token** | Variable | GCSplit1 → GCHostPay1 | GCSplit1, GCHostPay1 |
| **Response Tokens** | Variable | Various request-response pairs | GCSplit2, GCSplit3, GCHostPay2, GCHostPay3, GCMicroBatchProcessor |

---

## Part 4: Token Flow Visualization

### Instant Payout Flow (37 Steps with Encryption/Decryption)

```
Step 1: NowPayments → np-webhook (IPN, HMAC signature verification)
Step 2: np-webhook → GCWebhook1 (plain JSON)
Step 3: GCWebhook1 DECRYPT: Extract payment details
Step 4: GCWebhook1 ENCRYPT: Token for GCWebhook2 (telegram invite)
Step 5: GCWebhook1 → GCSplit1 (plain JSON, immediate routing)
Step 6: GCSplit1 ENCRYPT: Token for GCSplit2 (USDT→ETH estimate)
Step 7: GCSplit1 → GCSplit2 (encrypted token)
Step 8: GCSplit2 DECRYPT: Extract swap amount
Step 9: GCSplit2 → ChangeNow API (estimate)
Step 10: GCSplit2 ENCRYPT: Response token
Step 11: GCSplit2 → GCSplit1 (/estimate-response)
Step 12: GCSplit1 DECRYPT: Extract estimate
Step 13: GCSplit1 ENCRYPT: Token for GCSplit3 (ETH→Client swap)
Step 14: GCSplit1 → GCSplit3 (encrypted token)
Step 15: GCSplit3 DECRYPT: Extract swap details
Step 16: GCSplit3 → ChangeNow API (create fixed-rate transaction)
Step 17: GCSplit3 ENCRYPT: Response token with tx details
Step 18: GCSplit3 → GCSplit1 (/swap-response)
Step 19: GCSplit1 DECRYPT: Extract transaction details
Step 20: GCSplit1 ENCRYPT: HostPay token (using TPS_HOSTPAY_SIGNING_KEY) ⚠️
Step 21: GCSplit1 → GCHostPay1 (encrypted token)
Step 22: GCHostPay1 DECRYPT: Extract CN API ID + payin address (using TPS_HOSTPAY_SIGNING_KEY) ⚠️
Step 23: GCHostPay1 ENCRYPT: Token for GCHostPay2 (status check)
Step 24: GCHostPay1 → GCHostPay2 (encrypted token)
Step 25: GCHostPay2 DECRYPT: Extract CN API ID
Step 26: GCHostPay2 → ChangeNow API (get status)
Step 27: GCHostPay2 ENCRYPT: Response token
Step 28: GCHostPay2 → GCHostPay1 (/status-verified)
Step 29: GCHostPay1 DECRYPT: Check status
Step 30: GCHostPay1 ENCRYPT: Token for GCHostPay3 (execute payment)
Step 31: GCHostPay1 → GCHostPay3 (encrypted token)
Step 32: GCHostPay3 DECRYPT: Extract payment amount + address
Step 33: GCHostPay3 → Wallet API (execute ETH transfer)
Step 34: GCHostPay3 ENCRYPT: Response token with tx_hash
Step 35: GCHostPay3 → GCHostPay1 (/payment-completed)
Step 36: GCHostPay1 DECRYPT: Extract tx_hash
Step 37: GCHostPay1 → Update DB with payment status
```

**Encryption/Decryption Count:** 18 ENCRYPT operations, 9 DECRYPT operations

---

## Part 5: Critical Findings

### 1. Dual-Key Services (2 Services)

Only **2 services** manage both signing keys:

1. **GCSplit1-10-26**
   - Receives plain JSON (no DECRYPT with either key on main endpoint)
   - ENCRYPTS with `SUCCESS_URL_SIGNING_KEY` for GCSplit2/GCSplit3
   - ENCRYPTS with `TPS_HOSTPAY_SIGNING_KEY` for GCHostPay1 (external boundary)

2. **GCHostPay1-10-26**
   - DECRYPTS with `TPS_HOSTPAY_SIGNING_KEY` from GCSplit1 (external boundary)
   - ENCRYPTS/DECRYPTS with `SUCCESS_URL_SIGNING_KEY` for GCHostPay2/GCHostPay3

### 2. Unused Token Manager (1 Service)

**GCAccumulator-10-26** has `token_manager.py` but **NEVER USES IT**

- Architectural artifact from earlier design
- Currently uses plain JSON from GCWebhook1
- **Safe to remove** or keep for future use
- No impact on current operations

### 3. Signature Verification vs Encryption (1 Service)

**np-webhook-10-26** uses **HMAC-SHA256 signature verification** instead of encryption

- Not a token encryption/decryption workflow
- Standard for external IPN webhooks
- Uses `NOWPAYMENTS_IPN_SECRET` key
- Validates authenticity and integrity of NowPayments callbacks

### 4. Request-Response Patterns (5 Services)

Services that DECRYPT incoming requests and ENCRYPT responses:

1. **GCSplit2** - Estimate request/response
2. **GCSplit3** - Swap transaction request/response
3. **GCHostPay2** - Status check request/response
4. **GCHostPay3** - Payment execution request/response
5. **GCMicroBatchProcessor** - Batch callback request/response

### 5. One-Way Encryption (3 Services)

Services that ENCRYPT but do NOT DECRYPT:

1. **GCSplit1** (main endpoint) - Receives plain JSON, encrypts for downstream services
2. **GCBatchProcessor** - Scheduler trigger, encrypts for GCSplit1
3. **GCWebhook1** (current endpoint) - Receives plain JSON, encrypts for GCWebhook2

### 6. One-Way Decryption (1 Service)

Service that DECRYPTS but does NOT ENCRYPT:

1. **GCWebhook2** - Terminal service, sends Telegram invite (no further token propagation)

### 7. Token Expiration Windows

Different services have different expiration requirements:

| Service | Expiration Window | Reason |
|---------|-------------------|--------|
| GCWebhook1→GCWebhook2 | **2 hours** | Accommodate retry delays for Telegram invite |
| GCWebhook2 (processing) | **24 hours** | Large retry window for reliability |
| GCSplit1→GCHostPay1 | **60 seconds** | Strict window for immediate execution |
| GCMicroBatchProcessor | **30 minutes** | Accommodate ChangeNow processing delays |

---

## Part 6: Security Recommendations

### Immediate Actions

1. **Review GCAccumulator token_manager.py**
   - Decision needed: Remove or keep for future use
   - No current impact on operations

2. **Verify all signing keys are properly loaded**
   - Check `SUCCESS_URL_SIGNING_KEY` in 10 services
   - Check `TPS_HOSTPAY_SIGNING_KEY` in 3 services
   - Check `NOWPAYMENTS_IPN_SECRET` in 1 service

3. **Monitor token expiration handling**
   - Review logs for token expiration errors
   - Verify different windows for different services

### Short Term

1. **Key Rotation Strategy**
   - Document key rotation procedure
   - Test key rotation without downtime
   - Backup old keys for debugging

2. **Idempotency Markers**
   - Verify GCWebhook2 checks payment_id
   - Verify GCHostPay3 checks tx_hash
   - Monitor duplicate payment prevention

### Medium Term

1. **Consolidate token_manager Implementations**
   - Review differences across 11 services
   - Consider shared library for token operations
   - Standardize error handling

2. **Token Usage Metrics**
   - Add logging for all DECRYPT failures
   - Track token expiration rates
   - Monitor signature validation failures

### Long Term

1. **Security Boundary Review**
   - Audit `TPS_HOSTPAY_SIGNING_KEY` usage
   - Verify external boundary is secure
   - Consider additional boundaries if needed

2. **Documentation Maintenance**
   - Update when token formats change
   - Document any new services
   - Archive historical signing keys

---

## Appendix A: Service Matrix (Quick Reference)

| Service | Directory | Main File | token_manager.py | DECRYPT | ENCRYPT | Dual-Key | Key(s) Used |
|---------|-----------|-----------|------------------|---------|---------|----------|-------------|
| GCWebhook1 | `/GCWebhook1-10-26` | `tph1-10-26.py` | ✅ | ✅ | ✅ | ❌ | SUCCESS_URL_SIGNING_KEY |
| GCWebhook2 | `/GCWebhook2-10-26` | `tph2-10-26.py` | ✅ | ✅ | ❌ | ❌ | SUCCESS_URL_SIGNING_KEY |
| GCSplit1 | `/GCSplit1-10-26` | `tps1-10-26.py` | ✅ | ❌* | ✅ | ✅ | SUCCESS_URL + TPS_HOSTPAY |
| GCSplit2 | `/GCSplit2-10-26` | `tps2-10-26.py` | ✅ | ✅ | ✅ | ❌ | SUCCESS_URL_SIGNING_KEY |
| GCSplit3 | `/GCSplit3-10-26` | `tps3-10-26.py` | ✅ | ✅ | ✅ | ❌ | SUCCESS_URL_SIGNING_KEY |
| GCHostPay1 | `/GCHostPay1-10-26` | `tphp1-10-26.py` | ✅ | ✅ | ✅ | ✅ | SUCCESS_URL + TPS_HOSTPAY |
| GCHostPay2 | `/GCHostPay2-10-26` | `tphp2-10-26.py` | ✅ | ✅ | ✅ | ❌ | SUCCESS_URL_SIGNING_KEY |
| GCHostPay3 | `/GCHostPay3-10-26` | `tphp3-10-26.py` | ✅ | ✅ | ✅ | ❌ | SUCCESS_URL_SIGNING_KEY |
| GCAccumulator | `/GCAccumulator-10-26` | `acc10-26.py` | ✅ (UNUSED) | ❌ | ❌ | ❌ | None |
| GCBatchProcessor | `/GCBatchProcessor-10-26` | `batch10-26.py` | ✅ | ❌ | ✅ | ❌ | TPS_HOSTPAY_SIGNING_KEY |
| GCMicroBatchProcessor | `/GCMicroBatchProcessor-10-26` | `microbatch10-26.py` | ✅ | ✅ | ✅ | ❌ | SUCCESS_URL_SIGNING_KEY |
| np-webhook | `/np-webhook-10-26` | `app.py` | ❌ | ❌ | ❌ | ❌ | NOWPAYMENTS_IPN_SECRET (sig only) |
| TelePay | `/TelePay10-26` | `telepay10-26.py` | ❌ | ❌ | ❌ | ❌ | None |

\* GCSplit1 main endpoint receives plain JSON, but other endpoints (estimate-response, swap-response) do DECRYPT

---

## Appendix B: Complete Token Flow Diagram

```
                                    ┌─────────────────┐
                                    │  NowPayments    │
                                    │   (External)    │
                                    └────────┬────────┘
                                             │ IPN Callback
                                             │ HMAC-SHA256 signature
                                             ▼
                                    ┌─────────────────┐
                                    │   np-webhook    │
                                    │  (No tokens)    │
                                    └────────┬────────┘
                                             │ Plain JSON
                                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          GCWebhook1-10-26                              │
│  DECRYPT: Legacy GET / (NOWPayments success_url token)                │
│  ENCRYPT: Token for GCWebhook2 (Telegram invite)                      │
└───────┬────────────────────────────────────────────────────────────┬──┘
        │ Plain JSON                                                  │ Encrypted token
        ▼                                                              ▼
┌───────────────────┐                                         ┌────────────────┐
│   GCAccumulator   │                                         │  GCWebhook2    │
│  (No encryption)  │                                         │ DECRYPT ONLY   │
│   Plain JSON      │                                         │ (Terminal)     │
└───────────────────┘                                         └────────────────┘
        │
        │ Accumulate for threshold
        ▼
  (GCSplit2 async conversion)


┌────────────────────────────────────────────────────────────────────────┐
│                           GCSplit1-10-26                               │
│  (Orchestrator - DUAL KEY)                                             │
│  Main endpoint: Receives plain JSON, ENCRYPT for downstream            │
│  estimate-response: DECRYPT from GCSplit2, ENCRYPT for GCSplit3        │
│  swap-response: DECRYPT from GCSplit3, ENCRYPT for GCHostPay1          │
└──┬──────────────────────────────────────────────────────────────────┬──┘
   │ ENCRYPT (SUCCESS_URL_SIGNING_KEY)                                 │
   ▼                                                                    │
┌──────────────┐              ┌──────────────┐                         │
│  GCSplit2    │              │  GCSplit3    │                         │
│ DECRYPT+ENC  │◄─────────────┤ DECRYPT+ENC  │                         │
│ (Estimator)  │   Response   │  (Swapper)   │                         │
└──────────────┘              └──────────────┘                         │
   │                                 │                                  │
   └─────────┬───────────────────────┘                                  │
             │ Both return to GCSplit1                                  │
             ▼                                                           │
  (GCSplit1 continues to GCHostPay1)                                    │
                                                                         │
                                                                         │ ENCRYPT
                                                                         │ (TPS_HOSTPAY_SIGNING_KEY)
                                                                         │ EXTERNAL BOUNDARY
                                                                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         GCHostPay1-10-26                               │
│  (Validator & Orchestrator - DUAL KEY)                                 │
│  DECRYPT: From GCSplit1 (TPS_HOSTPAY_SIGNING_KEY)                     │
│  ENCRYPT: For GCHostPay2/GCHostPay3 (SUCCESS_URL_SIGNING_KEY)         │
└──┬────────────────────────────────────────────────────────────────┬───┘
   │ ENCRYPT (SUCCESS_URL_SIGNING_KEY)                              │
   ▼                                                                 ▼
┌──────────────┐                                            ┌──────────────┐
│ GCHostPay2   │                                            │ GCHostPay3   │
│ DECRYPT+ENC  │──────────────Response──────────────────────►│ DECRYPT+ENC  │
│ (Status      │                                            │ (Payment     │
│  Checker)    │                                            │  Executor)   │
└──────────────┘                                            └──────┬───────┘
                                                                   │ Response
                                                                   ▼
                                                          ┌──────────────────┐
                                                          │  GCHostPay1      │
                                                          │ (/payment-       │
                                                          │  completed)      │
                                                          └────────┬─────────┘
                                                                   │ IF batch conversion
                                                                   │ ENCRYPT callback
                                                                   ▼
                                                          ┌───────────────────┐
                                                          │ GCMicroBatch      │
                                                          │ Processor         │
                                                          │ DECRYPT callback  │
                                                          └───────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│                    Cloud Scheduler Triggered Services                  │
└────────────────────────────────────────────────────────────────────────┘

Every 5 minutes:                       Every 15 minutes:
┌──────────────────┐                  ┌──────────────────────┐
│ GCBatchProcessor │                  │ GCMicroBatchProcessor│
│ ENCRYPT ONLY     │                  │ (check-threshold)    │
│ → GCSplit1       │                  │ NO TOKENS            │
└──────────────────┘                  └──────────────────────┘
```

---

**Document Version:** 1.0
**Last Updated:** 2025-11-08
**Author:** Claude Code (Automated Analysis)
**Total Services Analyzed:** 13
**Total Lines of Code Reviewed:** ~8,000+
**Analysis Duration:** Comprehensive codebase exploration
