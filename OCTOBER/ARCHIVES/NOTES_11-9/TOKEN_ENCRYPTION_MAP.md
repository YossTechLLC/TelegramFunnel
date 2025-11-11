# Token Encryption/Decryption Architecture Map

## Overview
This document provides a comprehensive mapping of which services use encryption/decryption tokens in the TelegramFunnel payout architecture, along with the complete token flow between services.

---

## Service Summary Table

| Service | Main File | Token Manager | DECRYPT | ENCRYPT | Token Data | Role |
|---------|-----------|---------------|---------|---------|-----------|------|
| **GCWebhook1-10-26** | tph1-10-26.py | ✅ Yes | ✅ FROM NP | ✅ TO GCWebhook2, GCSplit1 | Payment data + pricing | Payment Processor |
| **GCWebhook2-10-26** | tph2-10-26.py | ✅ Yes | ✅ FROM GCWebhook1 | ❌ No | Subscription data | Telegram Invite Sender |
| **GCSplit1-10-26** | tps1-10-26.py | ✅ Yes (dual key) | ❌ No | ✅ TO GCSplit2, GCSplit3, GCHostPay1 | Payment split data | Orchestrator |
| **GCSplit2-10-26** | tps2-10-26.py | ✅ Yes | ✅ FROM GCSplit1 | ✅ TO GCSplit1 | USDT amount + estimate | USDT→ETH Estimator |
| **GCSplit3-10-26** | tps3-10-26.py | ✅ Yes | ✅ FROM GCSplit1 | ✅ TO GCSplit1 | ETH amount + swap data | ETH→Client Swapper |
| **GCHostPay1-10-26** | tphp1-10-26.py | ✅ Yes (dual key) | ✅ FROM GCSplit1 | ✅ TO GCHostPay2, GCHostPay3, GCMicroBatch | Payment metadata | Validator/Orchestrator |
| **GCHostPay2-10-26** | tphp2-10-26.py | ✅ Yes | ✅ FROM GCHostPay1 | ✅ TO GCHostPay1 | Status check response | Status Checker |
| **GCHostPay3-10-26** | tphp3-10-26.py | ✅ Yes | ✅ FROM GCHostPay1 | ✅ TO GCHostPay1 | ETH transfer response | Payment Executor |
| **GCAccumulator-10-26** | acc10-26.py | ✅ Yes | ❌ No | ❌ No | Payment data (NO crypto) | Accumulator |
| **GCBatchProcessor-10-26** | batch10-26.py | ✅ Yes | ❌ No | ✅ TO GCSplit1 | Batch payment data | Batch Processor |
| **GCMicroBatchProcessor-10-26** | microbatch10-26.py | ✅ Yes | ✅ FROM GCHostPay1 | ✅ TO GCHostPay1 | Batch conversion response | Micro-Batch Handler |
| **np-webhook-10-26** | app.py | ❌ No | ❌ No | ❌ No | IPN validation only | NowPayments Handler |
| **TelePay10-26** | telepay10-26.py | ❌ No | ❌ No | ❌ No | User data / Telegram API | Telegram Bot |

---

## Detailed Service Analysis

### 1. GCWebhook1-10-26 (Payment Processor Service)

**Main File:** `/tph1-10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py`

**Endpoints & Token Usage:**

#### Endpoint: GET / (Legacy - Deprecated)
- **Purpose:** Receives success_url from NOWPayments
- **Token Usage:** 
  - **DECRYPT** ✅ - Token from URL parameter
  - **ENCRYPT** ✅ - Creates encrypted token for GCWebhook2
  - **Data:** user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price

#### Endpoint: POST /process-validated-payment (Current)
- **Purpose:** Receives validated payment from np-webhook IPN
- **Token Usage:**
  - **DECRYPT** ❌ - Receives plain JSON (not encrypted)
  - **ENCRYPT** ✅ - Creates encrypted token for GCWebhook2
  - **Data:** Same as above
  
#### Endpoint: GET /health
- **Purpose:** Health check
- **Token Usage:** ❌ None

**Token Flow:**
```
NOWPayments (success_url)
    ↓ Contains encrypted token
GCWebhook1
    ├─→ DECRYPT: Extract payment details
    ├─→ Determine route: instant vs threshold
    ├─→ Route to GCSplit1 (instant) or GCAccumulator (threshold)
    └─→ ENCRYPT: New token for GCWebhook2
        ├─→ GCWebhook2: Telegram invite
        └─→ Data: subscription_time_days, subscription_price, wallet_address
```

**Signing Keys Used:**
- `SUCCESS_URL_SIGNING_KEY` - For both decrypt (NOWPayments) and encrypt (GCWebhook2)

---

### 2. GCWebhook2-10-26 (Telegram Invite Sender Service)

**Main File:** `/tph2-10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py`

**Endpoints & Token Usage:**

#### Endpoint: POST / (Main Webhook)
- **Purpose:** Receives encrypted token from GCWebhook1 via Cloud Tasks
- **Token Usage:**
  - **DECRYPT** ✅ - Token from request.get_json()
  - **ENCRYPT** ❌ - No encryption output
  - **Data:** user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price

#### Endpoint: GET /health
- **Purpose:** Health check
- **Token Usage:** ❌ None

**Token Flow:**
```
GCWebhook1 (Cloud Tasks)
    ↓ Encrypted token + payment_id
GCWebhook2
    ├─→ IDEMPOTENCY: Check if invite already sent
    ├─→ DECRYPT: Extract subscription data
    ├─→ VALIDATE: Payment completion check
    ├─→ CREATE: Telegram one-time invite link
    └─→ RETURN: Success (200)
```

**Signing Keys Used:**
- `SUCCESS_URL_SIGNING_KEY` - For decrypt (GCWebhook1 token)

**Critical Features:**
- Idempotency check to prevent duplicate invites
- Payment validation before sending invite
- Token expiration window: 24 hours (accommodates retry delays)

---

### 3. GCSplit1-10-26 (Payment Splitting Orchestrator Service)

**Main File:** `/tps1-10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py` (dual-key system)

**Endpoints & Token Usage:**

#### Endpoint: POST / (Main Webhook from GCWebhook1)
- **Purpose:** Orchestrates payment splitting workflow
- **Token Usage:**
  - **DECRYPT** ❌ - Receives plain JSON from GCWebhook1
  - **ENCRYPT** ✅ - Creates tokens for GCSplit2, GCSplit3, GCHostPay1
  - **Data Encrypted:** user_id, closed_channel_id, wallet_address, payout_currency, payout_network, adjusted_amount, swap_currency, payout_mode, actual_eth_amount

#### Endpoint: POST /estimate-response (Response from GCSplit2)
- **Purpose:** Receives USDT→ETH estimate from GCSplit2
- **Token Usage:**
  - **DECRYPT** ✅ - Token from GCSplit2
  - **ENCRYPT** ✅ - Re-encrypts for GCSplit3
  - **Data:** Estimate response with from_amount, to_amount, fees

#### Endpoint: POST /swap-response (Response from GCSplit3)
- **Purpose:** Receives ETH→Client currency swap details
- **Token Usage:**
  - **DECRYPT** ✅ - Token from GCSplit3
  - **ENCRYPT** ✅ - Creates token for GCHostPay1
  - **Data:** Swap transaction details

**Token Flow:**
```
GCWebhook1 (Plain JSON with outcome_amount_usd)
    ↓
GCSplit1 (Orchestrator)
    ├─→ Calculate adjusted amount (remove TP fee)
    ├─→ ENCRYPT: Token for GCSplit2 (USDT→ETH estimate)
    │   │ Data: adjusted_amount, swap_currency='usdt', payout_mode, actual_eth_amount
    │   └─→ GCSplit2: Returns estimate
    │       ├─→ Back to GCSplit1 (/estimate-response)
    │       ├─→ DECRYPT: GCSplit2 response
    │       ├─→ ENCRYPT: Token for GCSplit3
    │       │   Data: eth_amount, swap_currency, payout_mode, actual_eth_amount
    │       └─→ GCSplit3: Creates fixed-rate transaction
    │           └─→ Back to GCSplit1 (/swap-response)
    │               ├─→ DECRYPT: GCSplit3 response
    │               ├─→ ENCRYPT: Token for GCHostPay1
    │               │   Data: Payment metadata, CN API ID, payin_address
    │               └─→ GCHostPay1: Validates & orchestrates payment
    │
    └─→ Parallel: QUEUE to GCSplit1 (instant routes to GCSplit1, threshold to GCAccumulator)
```

**Signing Keys Used:**
- `SUCCESS_URL_SIGNING_KEY` - For internal GCSplit1→GCSplit2→GCSplit3 communication
- `TPS_HOSTPAY_SIGNING_KEY` - For GCSplit1→GCHostPay1 communication (external boundary)

**Critical Functions:**
- `build_hostpay_token()` - Encrypts payment data for GCHostPay1
- `calculate_adjusted_amount()` - Removes TP flat fee
- Token includes both `actual_eth_amount` and `estimated_eth_amount` for comparison

---

### 4. GCSplit2-10-26 (USDT→ETH Estimator Service)

**Main File:** `/tps2-10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py`

**Endpoints & Token Usage:**

#### Endpoint: POST / (Main Webhook from GCSplit1)
- **Purpose:** Calls ChangeNow API for USDT→ETH estimate
- **Token Usage:**
  - **DECRYPT** ✅ - Token from GCSplit1
  - **ENCRYPT** ✅ - Response token to GCSplit1
  - **Data:** USDT amount, swap_currency, payout_mode, actual_eth_amount

**Token Flow:**
```
GCSplit1 (Cloud Tasks)
    ↓ Encrypted token with adjusted_amount
GCSplit2
    ├─→ DECRYPT: Extract amount, swap_currency, payout_mode
    ├─→ API CALL: ChangeNow get_estimated_amount_v2_with_retry()
    │   Input: from_amount (USDT), to_currency (client's currency)
    │   Output: Estimated amount post-fees
    ├─→ ENCRYPT: Response token with estimates
    └─→ QUEUE: Task back to GCSplit1 (/estimate-response)
```

**Signing Keys Used:**
- `SUCCESS_URL_SIGNING_KEY` - For both decrypt (GCSplit1) and encrypt (response)

**Critical Features:**
- Infinite retry logic for ChangeNow API failures
- Extracts swap_currency from token to determine if ETH or USDT
- Passes actual_eth_amount through for later validation

---

### 5. GCSplit3-10-26 (ETH→Client Currency Swapper Service)

**Main File:** `/tps3-10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py`

**Endpoints & Token Usage:**

#### Endpoint: POST / (Main Webhook from GCSplit1)
- **Purpose:** Creates ChangeNow fixed-rate transaction (ETH→Client Currency)
- **Token Usage:**
  - **DECRYPT** ✅ - Token from GCSplit1
  - **ENCRYPT** ✅ - Response token to GCSplit1
  - **Data:** ETH amount, client currency, payout network, actual_eth_amount

**Token Flow:**
```
GCSplit1 (Cloud Tasks with estimated amount from GCSplit2)
    ↓ Encrypted token with eth_amount
GCSplit3
    ├─→ DECRYPT: Extract amount, payout_currency, payout_network
    ├─→ API CALL: ChangeNow create_fixed_rate_transaction_with_retry()
    │   Input: eth_amount, from_currency='eth', to_currency (client), address
    │   Output: Transaction ID, payin_address, rate, payee_address
    ├─→ ENCRYPT: Response token with transaction details
    └─→ QUEUE: Task back to GCSplit1 (/swap-response)
```

**Signing Keys Used:**
- `SUCCESS_URL_SIGNING_KEY` - For both decrypt and encrypt

**Critical Features:**
- Creates FIXED-RATE transaction (locked rate)
- Includes client wallet address for receiving swapped currency
- Infinite retry logic for API failures

---

### 6. GCHostPay1-10-26 (Validator & Orchestrator Service)

**Main File:** `/tphp1-10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py` (dual-key system)

**Endpoints & Token Usage:**

#### Endpoint: POST / (Main Webhook from GCSplit1)
- **Purpose:** Validates and orchestrates payment execution flow
- **Token Usage:**
  - **DECRYPT** ✅ - Token from GCSplit1 (built by build_hostpay_token)
  - **ENCRYPT** ✅ - Tokens for GCHostPay2 (status check) and GCHostPay3 (payment)
  - **Data:** CN API ID, payin_address, payment amount, actual vs estimated ETH

#### Endpoint: POST /status-verified (Response from GCHostPay2)
- **Purpose:** Receives ChangeNow status verification
- **Token Usage:**
  - **DECRYPT** ✅ - Token from GCHostPay2
  - **ENCRYPT** ✅ - Token for GCHostPay3 (if status good)

#### Endpoint: POST /payment-completed (Response from GCHostPay3)
- **Purpose:** Receives ETH payment execution confirmation
- **Token Usage:**
  - **DECRYPT** ✅ - Token from GCHostPay3
  - **ENCRYPT** ✅ - Callback token for GCMicroBatchProcessor (batch mode only)

**Token Flow:**
```
GCSplit1 (Cloud Tasks)
    ↓ Token with CN API ID + payin_address
GCHostPay1 (/main)
    ├─→ DECRYPT: Extract payment metadata
    ├─→ DB CHECK: Verify ChangeNow transaction exists
    ├─→ ENCRYPT: Token for GCHostPay2 (status check)
    │   └─→ QUEUE: Status verification task
    │
    ├─→ GCHostPay2 receives token
    │   ├─→ DECRYPT: Extract CN API ID
    │   ├─→ API CALL: ChangeNow get_transaction_status()
    │   ├─→ ENCRYPT: Response token with status
    │   └─→ QUEUE: Response back to GCHostPay1 (/status-verified)
    │
    ├─→ GCHostPay1 (/status-verified)
    │   ├─→ DECRYPT: GCHostPay2 response
    │   ├─→ IF status=='waiting':
    │   │   ├─→ ENCRYPT: Token for GCHostPay3 (execute payment)
    │   │   └─→ QUEUE: Payment execution task
    │   │
    │   └─→ GCHostPay3 receives token
    │       ├─→ DECRYPT: Extract payment details
    │       ├─→ EXECUTE: Send ETH from HostPay wallet to payin_address
    │       ├─→ ENCRYPT: Response token with tx_hash
    │       └─→ QUEUE: Response back to GCHostPay1 (/payment-completed)
    │
    └─→ GCHostPay1 (/payment-completed)
        ├─→ DECRYPT: GCHostPay3 response
        ├─→ IF batch conversion:
        │   ├─→ ENCRYPT: Callback token for GCMicroBatchProcessor
        │   └─→ QUEUE: Callback task with batch results
        └─→ Update DB with payment status
```

**Signing Keys Used:**
- `TPS_HOSTPAY_SIGNING_KEY` - For decrypt (GCSplit1 token)
- `SUCCESS_URL_SIGNING_KEY` - For encrypt/decrypt internal communication (GCHostPay2, GCHostPay3)

**Critical Features:**
- Dual-key system for security boundary
- Orchestrates multi-step validation flow
- Handles both instant and batch conversions

---

### 7. GCHostPay2-10-26 (Status Checker Service)

**Main File:** `/tphp2-10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py`

**Endpoints & Token Usage:**

#### Endpoint: POST / (Status Check Request from GCHostPay1)
- **Purpose:** Verifies ChangeNow transaction is ready
- **Token Usage:**
  - **DECRYPT** ✅ - Token from GCHostPay1
  - **ENCRYPT** ✅ - Response token to GCHostPay1
  - **Data:** CN API ID, transaction status response

**Token Flow:**
```
GCHostPay1 (Cloud Tasks)
    ↓ Encrypted token with CN API ID
GCHostPay2
    ├─→ DECRYPT: Extract CN API ID
    ├─→ API CALL: ChangeNow get_transaction_status()
    ├─→ ENCRYPT: Response with status
    └─→ QUEUE: Task back to GCHostPay1 (/status-verified)
```

**Signing Keys Used:**
- `SUCCESS_URL_SIGNING_KEY` - For both decrypt and encrypt (internal communication)

---

### 8. GCHostPay3-10-26 (Payment Executor Service)

**Main File:** `/tphp3-10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py`

**Endpoints & Token Usage:**

#### Endpoint: POST / (Payment Execution Request from GCHostPay1)
- **Purpose:** Executes ETH transfer from HostPay wallet
- **Token Usage:**
  - **DECRYPT** ✅ - Token from GCHostPay1
  - **ENCRYPT** ✅ - Response token to GCHostPay1
  - **Data:** Payment amount (ETH), payin_address, transaction hash

**Token Flow:**
```
GCHostPay1 (Cloud Tasks)
    ↓ Encrypted token with payment amount + address
GCHostPay3
    ├─→ DECRYPT: Extract payment details
    ├─→ WALLET_MANAGER: Execute ETH transfer
    │   Input: payin_address, amount_eth
    │   Output: tx_hash
    ├─→ ENCRYPT: Response with tx_hash
    └─→ QUEUE: Task back to GCHostPay1 (/payment-completed)
```

**Signing Keys Used:**
- `SUCCESS_URL_SIGNING_KEY` - For both decrypt and encrypt (internal communication)

---

### 9. GCAccumulator-10-26 (Payment Accumulation Service)

**Main File:** `/acc10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py` **BUT UNUSED**

**Endpoints & Token Usage:**

#### Endpoint: POST / (Accumulation Request from GCWebhook1)
- **Purpose:** Accumulates payments for threshold-based payout
- **Token Usage:**
  - **DECRYPT** ❌ - Receives plain JSON (NOT encrypted)
  - **ENCRYPT** ❌ - No encryption output
  - **Data Received:** Plain JSON with user_id, client_id, payment_amount_usd, wallet_address, etc.

**Token Flow:**
```
GCWebhook1 (Cloud Tasks - Plain JSON)
    ↓
GCAccumulator
    ├─→ NO DECRYPTION
    ├─→ Calculate adjusted amount (remove TP fee)
    ├─→ Store in payout_accumulation table (PENDING conversion status)
    ├─→ QUEUE: Task to GCSplit2 for async conversion (ETH→USDT)
    └─→ Return success immediately
```

**Key Points:**
- Token manager exists but is **NOT USED**
- Plain JSON communication (no encryption overhead)
- Conversions happen asynchronously via GCSplit2

---

### 10. GCBatchProcessor-10-26 (Batch Payout Processor Service)

**Main File:** `/batch10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py`

**Endpoints & Token Usage:**

#### Endpoint: POST /process (Triggered by Cloud Scheduler)
- **Purpose:** Detects accumulated payments over threshold, creates batch payouts
- **Token Usage:**
  - **DECRYPT** ❌ - Scheduler trigger only
  - **ENCRYPT** ✅ - Creates tokens for GCSplit1 (batch payouts)
  - **Data:** Batch ID, total accumulated USDT, client wallet address

**Token Flow:**
```
Cloud Scheduler (Every 5 minutes)
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

**Signing Keys Used:**
- `TPS_HOSTPAY_SIGNING_KEY` - For encrypt (token to GCSplit1)

---

### 11. GCMicroBatchProcessor-10-26 (Micro-Batch Conversion Service)

**Main File:** `/microbatch10-26.py`
**Token Manager:** ✅ Yes - `token_manager.py`

**Endpoints & Token Usage:**

#### Endpoint: POST /check-threshold (Triggered by Cloud Scheduler)
- **Purpose:** Checks if total pending USD >= threshold, creates micro-batch swap
- **Token Usage:**
  - **DECRYPT** ✅ - Receives callback token from GCHostPay1
  - **ENCRYPT** ✅ - Callback response token
  - **Data:** Batch conversion results, actual USDT received

**Token Flow:**
```
Cloud Scheduler (Every 15 minutes)
    ↓
GCMicroBatchProcessor (/check-threshold)
    ├─→ NO DECRYPTION (initial trigger)
    ├─→ Query: Total pending USD in payout_accumulation (PENDING status)
    ├─→ IF total >= micro_batch_threshold:
    │   ├─→ Create ChangeNow ETH→USDT swap
    │   ├─→ Update all pending records to 'swapping'
    │   └─→ QUEUE: Task to GCHostPay1 (payment execution)
    │
    └─→ GCHostPay1 (Payment execution path)
        └─→ After ETH payment completes:
            └─→ Back to GCMicroBatchProcessor (/callback)
                ├─→ DECRYPT: Callback token from GCHostPay1
                │   Data: batch_conversion_id, cn_api_id, tx_hash, actual_usdt_received
                └─→ Update batch_conversions with actual amount received
```

**Signing Keys Used:**
- `SUCCESS_URL_SIGNING_KEY` - For decrypt (GCHostPay1 callback)

---

### 12. np-webhook-10-26 (NowPayments IPN Handler)

**Main File:** `/app.py`
**Token Manager:** ❌ No

**Endpoints & Token Usage:**

#### Endpoint: POST / (IPN Callback from NowPayments)
- **Purpose:** Handles IPN signature verification and database updates
- **Token Usage:**
  - **DECRYPT** ❌ - No token decryption
  - **ENCRYPT** ❌ - No token encryption
  - **Data:** Plain JSON from NowPayments with IPN signature verification

#### Endpoint: GET /payment-processing (Landing Page)
- **Purpose:** Serves payment processing UI
- **Token Usage:** ❌ None

**Key Points:**
- NO encryption/decryption
- Uses HMAC-SHA256 for **signature verification** (not encryption)
- Verifies IPN signature against `NOWPAYMENTS_IPN_SECRET`
- Updates `processed_payments` table with payment_id and metadata
- Triggers GCWebhook1 via Cloud Tasks after IPN validation

**Token Flow:**
```
NowPayments (IPN Callback)
    ↓ POST /, HMAC-SHA256 signature in header
np-webhook
    ├─→ NO DECRYPTION
    ├─→ VERIFY: HMAC-SHA256 signature check (defense-in-depth)
    ├─→ UPDATE: DB with payment_id, outcome_amount (actual crypto value)
    ├─→ FETCH: CoinGecko price for outcome amount → USD conversion
    ├─→ QUEUE: Task to GCWebhook1 (/process-validated-payment)
    │   Data: Plain JSON with payment_status='finished', outcome_amount_usd
    └─→ Return 200 OK
```

**Signing Keys Used:**
- `NOWPAYMENTS_IPN_SECRET` - For signature verification only

---

### 13. TelePay10-26 (Telegram Bot)

**Main File:** `/telepay10-26.py`
**Token Manager:** ❌ No

**Role:** Telegram bot user interaction, command handling, subscription management

**Token Usage:**
- **DECRYPT** ❌ - No token decryption
- **ENCRYPT** ❌ - No token encryption
- **Data:** Direct Telegram API calls, user commands, subscription data

**Key Points:**
- Pure Telegram bot implementation
- No token encryption/decryption
- Interacts with database directly for user/subscription management
- No inter-service communication via encrypted tokens

---

## Token Encryption Architecture Summary

### Two-Key System Architecture

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

### Key Distribution

| Key Name | Used By | Services |
|----------|---------|----------|
| `SUCCESS_URL_SIGNING_KEY` | Internal boundaries | GCWebhook1, GCWebhook2, GCSplit1-3, GCHostPay1-3, GCAccumulator, GCMicroBatchProcessor |
| `TPS_HOSTPAY_SIGNING_KEY` | External boundary (GCSplit1→GCHostPay1) | GCSplit1, GCHostPay1, GCBatchProcessor |
| `NOWPAYMENTS_IPN_SECRET` | Signature verification (NOT encryption) | np-webhook |

---

## Token Data Payloads

### Payment Data Token (NOWPayments → GCWebhook1)

```
Binary Format:
- 6 bytes: user_id (48-bit)
- 6 bytes: closed_channel_id (48-bit)
- 2 bytes: timestamp_minutes (16-bit)
- 2 bytes: subscription_time_days (16-bit)
- 1 byte: price_length + variable bytes
- 1 byte: wallet_address_length + variable bytes
- 1 byte: currency_length + variable bytes
- 1 byte: network_length + variable bytes
- 16 bytes: HMAC-SHA256 signature (truncated)

Total: ~38+ bytes (variable length)
Encoded: Base64 URL-safe without padding
```

### Payment Split Token (GCSplit1 → GCSplit2/GCSplit3)

```
Binary Format:
- 8 bytes: user_id (64-bit)
- 16 bytes: closed_channel_id (fixed, padded)
- Variable: wallet_address (length-prefixed)
- Variable: payout_currency (length-prefixed)
- Variable: payout_network (length-prefixed)
- 8 bytes: adjusted_amount (double precision float)
- Variable: swap_currency (length-prefixed) ['eth' or 'usdt']
- Variable: payout_mode (length-prefixed) ['instant' or 'threshold']
- 8 bytes: actual_eth_amount (double precision float)
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC-SHA256 signature (truncated)

Encoded: Base64 URL-safe without padding
```

### HostPay Token (GCSplit1 → GCHostPay1)

```
Binary Format:
- 16 bytes: unique_id (fixed, padded with nulls)
- Variable: cn_api_id (length-prefixed)
- Variable: from_currency (length-prefixed)
- Variable: from_network (length-prefixed)
- 8 bytes: actual_eth_amount (double) [actual from NowPayments]
- 8 bytes: estimated_eth_amount (double) [ChangeNow estimate]
- Variable: payin_address (length-prefixed)
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC-SHA256 signature (truncated)

Encoded: Base64 URL-safe without padding
```

---

## Service Dependency Graph

```
NOWPayments (IPN)
    │
    └─→ np-webhook (verify signature, fetch price)
        │
        └─→ GCWebhook1 (decrypt token, route payment)
            │
            ├─→ INSTANT ROUTE:
            │   │
            │   └─→ GCSplit1 (orchestrate payment)
            │       ├─→ GCSplit2 (estimate USDT→ETH)
            │       │   └─→ back to GCSplit1
            │       │
            │       ├─→ GCSplit3 (create ETH→Client swap)
            │       │   └─→ back to GCSplit1
            │       │
            │       └─→ GCHostPay1 (validate & orchestrate)
            │           ├─→ GCHostPay2 (check status)
            │           │   └─→ back to GCHostPay1
            │           │
            │           └─→ GCHostPay3 (execute payment)
            │               └─→ back to GCHostPay1
            │
            ├─→ THRESHOLD ROUTE:
            │   │
            │   └─→ GCAccumulator (store pending)
            │       │
            │       └─→ GCSplit2 (async ETH→USDT)
            │
            ├─→ PARALLEL:
            │
            └─→ GCWebhook2 (send Telegram invite)

Cloud Scheduler (Every 5 min)
    │
    └─→ GCBatchProcessor
        │
        └─→ GCSplit1 (batch USDT→Client swap)

Cloud Scheduler (Every 15 min)
    │
    └─→ GCMicroBatchProcessor
        │
        └─→ GCHostPay1 (batch payment execution)
```

---

## Encryption/Decryption Summary Statistics

| Category | Count |
|----------|-------|
| Services with token_manager.py | 11 |
| Services that DECRYPT | 8 |
| Services that ENCRYPT | 9 |
| Services with BOTH | 6 |
| Services with DECRYPT ONLY | 2 |
| Services with ENCRYPT ONLY | 2 |
| Services with NEITHER | 3 |
| Signing keys in use | 3 |
| Token types | 4 |

---

## Critical Security Notes

1. **Key Rotation:** All signing keys should be rotated regularly
2. **Token Expiration:** 
   - Payment tokens: 2-hour window
   - Telegram invite tokens: 24-hour window
   - HostPay tokens: 60-second window
3. **Truncated Signatures:** All HMAC signatures are truncated to 16 bytes
4. **Base64 Encoding:** URL-safe encoding without padding
5. **Timestamp Validation:** All tokens validate timestamp to prevent replay attacks
6. **ID Handling:** 48-bit Telegram IDs converted to handle negative values

---

## Testing Tokens

To test token encryption/decryption:

```bash
# GCWebhook1 token flow
curl https://gcwebhook1/process-validated-payment \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "closed_channel_id": -456, ...}'

# GCWebhook2 token validation
curl https://gcwebhook2/ \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"token": "base64_encoded_token", "payment_id": "np_payment_id"}'
```

---

## Maintenance Checklist

- [ ] Verify all signing keys are loaded in services
- [ ] Monitor token expiration handling in logs
- [ ] Check idempotency markers in database
- [ ] Validate signature verification failures
- [ ] Audit token flow for any missing encryption points
- [ ] Review timeout windows for each service pair
- [ ] Test key rotation process
- [ ] Verify backup signing keys are available

