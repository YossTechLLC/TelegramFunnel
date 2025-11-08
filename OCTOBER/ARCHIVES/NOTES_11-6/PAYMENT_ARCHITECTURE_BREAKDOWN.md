# TelePay10-26 Payment Architecture Breakdown

## Overview
This document provides a condensed breakdown of the INSTANT and THRESHOLD payout architecture present in the /10-26 microservices system.

---

## INSTANT PAYOUT WORKFLOW (NowPayments → Direct Client Payout)

### 1. **NP-Webhook-10-26** (IPN Handler)
**Function:** Receives and validates NowPayments IPN callbacks

**INPUT:**
- NowPayments IPN callback (POST /)
- Contains: payment_id, order_id, payment_status, outcome_amount, pay_currency, etc.

**FUNCTION:**
- Verifies HMAC signature (x-nowpayments-sig header)
- Parses order_id to extract user_id and open_channel_id
- Looks up closed_channel_id from main_clients_database
- Updates private_channel_users_database with NowPayments metadata
- Fetches crypto price from CoinGecko API
- Calculates outcome_amount_usd (ACTUAL market value)
- Fetches subscription details via JOIN query

**OUTPUT:**
- Enqueues to **GCWebhook1-10-26** via Cloud Tasks (GCWEBHOOK1_QUEUE)
- Target: `/process-validated-payment`
- Payload: user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price, outcome_amount_usd, nowpayments_payment_id

---

### 2. **GCWebhook1-10-26** (Payment Orchestrator)
**Function:** Routes payments to instant or threshold processing, triggers Telegram invites

**INPUT:**
- POST /process-validated-payment (from NP-Webhook via Cloud Tasks)
- Contains: user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price, outcome_amount_usd, nowpayments metadata

**FUNCTION:**
- Queries payout_accumulation table for payout_mode (instant vs threshold)
- For INSTANT mode:
  - Routes to **GCSplit1-10-26** with ACTUAL outcome_amount_usd
  - Encrypts token for **GCWebhook2-10-26** (Telegram invite)
- For THRESHOLD mode:
  - Routes to **GCAccumulator-10-26** with ACTUAL outcome_amount_usd
  - Also encrypts token for **GCWebhook2-10-26** (Telegram invite)

**OUTPUT:**
- INSTANT: Enqueues to **GCSplit1-10-26** (GCSPLIT1_QUEUE)
- THRESHOLD: Enqueues to **GCAccumulator-10-26** (GCACCUMULATOR_QUEUE)
- BOTH: Enqueues to **GCWebhook2-10-26** (GCWEBHOOK2_QUEUE) for Telegram invite

---

### 3. **GCWebhook2-10-26** (Telegram Invite Sender)
**Function:** Sends one-time Telegram invite links to users

**INPUT:**
- POST / (from GCWebhook1 via Cloud Tasks)
- Encrypted token containing: user_id, closed_channel_id, wallet_address, subscription_time_days, subscription_price

**FUNCTION:**
- Decrypts token
- Validates payment completion in database
- Creates fresh Bot instance per request
- Uses asyncio.run() to execute async telegram operations
- Creates one-time invite link (expires 1hr, 1 use)
- Sends invite message to user

**OUTPUT:**
- TERMINATES workflow (sends invite to user)
- Returns 200 on success (Cloud Tasks marks complete)
- Returns 503 on IPN pending (Cloud Tasks retries)

---

### 4. **GCSplit1-10-26** (Payment Split Orchestrator)
**Function:** Coordinates multi-step currency conversion workflow

**INPUT:**
- POST / (from GCWebhook1 via Cloud Tasks)
- Contains: user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_price (ACTUAL outcome_amount_usd)

**FUNCTION:**
- Removes TP flat fee (default 3%)
- Encrypts token for **GCSplit2-10-26** (USDT→ETH estimate)
- Enqueues Cloud Task to GCSplit2

**OUTPUT:**
- Enqueues to **GCSplit2-10-26** (GCSPLIT2_QUEUE)
- Workflow continues asynchronously

**ADDITIONAL ENDPOINTS:**
- POST /usdt-eth-estimate: Receives estimate from GCSplit2
  - Calculates pure market ETH value
  - Inserts into split_payout_request table
  - Enqueues to **GCSplit3-10-26** (GCSPLIT3_QUEUE)

- POST /eth-client-swap: Receives swap result from GCSplit3
  - Inserts into split_payout_que table
  - Builds GCHostPay token
  - Enqueues to **GCHostPay1-10-26** (GCHOSTPAY1_QUEUE)

- POST /batch-payout: Receives batch payout from GCBatchProcessor
  - Handles threshold payout batches
  - Routes to GCSplit2 for conversion

---

### 5. **GCSplit2-10-26** (USDT→ETH Estimator)
**Function:** Fetches ChangeNow estimates for USDT→ETH conversion

**INPUT:**
- POST / (from GCSplit1 via Cloud Tasks)
- Encrypted token containing: user_id, closed_channel_id, wallet_address, payout_currency, payout_network, adjusted_amount_usdt

**FUNCTION:**
- Decrypts token
- Calls ChangeNow API v2 for USDT→ETH estimate (with infinite retry)
- Extracts: fromAmount, toAmount, depositFee, withdrawalFee
- Encrypts response token

**OUTPUT:**
- Enqueues response to **GCSplit1-10-26** (GCSPLIT1_RESPONSE_QUEUE)
- Target: `/usdt-eth-estimate`
- Payload: from_amount_usdt, to_amount_eth_post_fee, deposit_fee, withdrawal_fee

---

### 6. **GCSplit3-10-26** (ETH→Client Currency Swapper)
**Function:** Creates ChangeNow fixed-rate transactions for ETH→ClientCurrency

**INPUT:**
- POST / (from GCSplit1 via Cloud Tasks)
- Encrypted token containing: unique_id, user_id, closed_channel_id, wallet_address, payout_currency, payout_network, eth_amount

**FUNCTION:**
- Decrypts token
- Creates ChangeNow fixed-rate transaction (ETH→ClientCurrency) with infinite retry
- Extracts full transaction details (id, payin_address, fromAmount, toAmount, etc.)
- Encrypts response token

**OUTPUT:**
- Enqueues response to **GCSplit1-10-26** (GCSPLIT1_RESPONSE_QUEUE)
- Target: `/eth-client-swap`
- Payload: cn_api_id, from_currency, to_currency, from_amount, to_amount, payin_address, payout_address, etc.

**ADDITIONAL ENDPOINT:**
- POST /eth-to-usdt: Creates ETH→USDT swaps for threshold payouts
  - Called by GCAccumulator for batch conversions
  - Returns to GCAccumulator with swap details

---

### 7. **GCHostPay1-10-26** (Validator & Orchestrator)
**Function:** Validates and orchestrates ETH payment execution

**INPUT:**
- POST / (from GCSplit1 via Cloud Tasks)
- Encrypted token containing: unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address

**FUNCTION:**
- Decrypts token (supports 3 token types: GCSplit1, GCAccumulator, GCMicroBatchProcessor)
- Checks database for duplicates
- Encrypts token for **GCHostPay2-10-26** (status check)
- Enqueues to GCHostPay2

**OUTPUT:**
- Enqueues to **GCHostPay2-10-26** (GCHOSTPAY2_QUEUE)
- Workflow continues asynchronously

**ADDITIONAL ENDPOINTS:**
- POST /status-verified: Receives status from GCHostPay2
  - Validates status == "waiting"
  - Detects context (instant, threshold, or batch)
  - Enqueues to **GCHostPay3-10-26** (GCHOSTPAY3_QUEUE)

- POST /payment-completed: Receives payment result from GCHostPay3
  - Queries ChangeNow for actual USDT received (for batch/threshold)
  - Routes callback based on context:
    - BATCH: Routes to **GCMicroBatchProcessor-10-26** (/swap-executed)
    - THRESHOLD: Routes to **GCAccumulator-10-26** (not yet implemented)
    - INSTANT: TERMINATES workflow (no callback needed)

---

### 8. **GCHostPay2-10-26** (ChangeNow Status Checker)
**Function:** Checks ChangeNow transaction status

**INPUT:**
- POST / (from GCHostPay1 via Cloud Tasks)
- Encrypted token containing: unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address

**FUNCTION:**
- Decrypts token
- Queries ChangeNow API for transaction status (with infinite retry)
- Validates status == "waiting"
- Encrypts response token

**OUTPUT:**
- Enqueues response to **GCHostPay1-10-26** (GCHOSTPAY1_RESPONSE_QUEUE)
- Target: `/status-verified`
- Payload: unique_id, cn_api_id, status, from_currency, from_network, from_amount, payin_address

---

### 9. **GCHostPay3-10-26** (ETH Payment Executor)
**Function:** Executes ETH payments with 3-attempt retry logic

**INPUT:**
- POST / (from GCHostPay1 via Cloud Tasks)
- Encrypted token containing: unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address, context, attempt_count

**FUNCTION:**
- Decrypts token
- Checks attempt limit (max 3)
- Executes ETH payment via WalletManager (single attempt - no infinite retry)
- ON SUCCESS:
  - Logs to hostpay_transactions table
  - Encrypts response token
  - Routes based on context:
    - INSTANT: Routes to **GCHostPay1-10-26** (/payment-completed)
    - THRESHOLD: Routes to **GCAccumulator-10-26** (/swap-executed)
  - TERMINATES workflow on instant context
- ON FAILURE:
  - Classifies error (retryable vs permanent)
  - If attempt < 3: Re-encrypts with incremented count, self-retries after 60s
  - If attempt >= 3: Stores in failed_transactions table, sends alert, TERMINATES

**OUTPUT:**
- SUCCESS: Enqueues to GCHostPay1 or GCAccumulator based on context
- RETRY: Enqueues self-retry to **GCHostPay3-10-26** (GCHOSTPAY3_RETRY_QUEUE)
- FAILURE: TERMINATES workflow (stored in failed_transactions)

---

## THRESHOLD PAYOUT WORKFLOW (Accumulation → Batch Conversion)

### 10. **GCAccumulator-10-26** (Payment Accumulator)
**Function:** Accumulates payments for clients using threshold payout mode

**INPUT:**
- POST / (from GCWebhook1 via Cloud Tasks)
- Contains: user_id, client_id, wallet_address, payout_currency, payout_network, payment_amount_usd (ACTUAL outcome_amount_usd), subscription_id, nowpayments metadata

**FUNCTION:**
- Calculates adjusted amount (removes TP fee like GCSplit1)
- Stores in payout_accumulation table with status='pending'
- Sets accumulated_eth to adjusted USD value (pending conversion)
- NOTE: Conversion happens later via GCMicroBatchProcessor when threshold reached

**OUTPUT:**
- TERMINATES workflow (stores payment for future batch processing)
- Returns success immediately
- No immediate conversion - waits for batch threshold

**ADDITIONAL ENDPOINT:**
- POST /swap-executed: Receives callback from GCHostPay3 after ETH→USDT swap
  - Updates batch records with actual USDT received
  - Calculates proportional distribution
  - Updates conversion status
  - (Not yet fully implemented)

---

### 11. **GCMicroBatchProcessor-10-26** (Micro-Batch Converter)
**Function:** Triggered by Cloud Scheduler every 15 minutes to check and execute batch conversions

**INPUT:**
- POST /check-threshold (from Cloud Scheduler every 15 min)
- No payload - scheduler trigger

**FUNCTION:**
- Fetches micro_batch_threshold from Secret Manager
- Queries total pending USD from payout_accumulation table
- If total >= threshold:
  - Generates batch_conversion_id
  - Calls ChangeNow estimate API: USDT→ETH (to get ETH equivalent of USD value)
  - Creates ChangeNow swap: ETH→USDT (with calculated ETH amount)
  - Creates batch_conversions record
  - Updates all pending records to status='swapping'
  - Encrypts token for **GCHostPay1-10-26**
  - Enqueues to GCHostPay1 for ETH payment execution

**OUTPUT:**
- If threshold reached: Enqueues to **GCHostPay1-10-26** (GCHOSTPAY1_BATCH_QUEUE)
- Context: 'batch'
- Workflow continues through GCHostPay1 → GCHostPay2 → GCHostPay3
- GCHostPay3 calls back to **GCMicroBatchProcessor-10-26** (/swap-executed)

**ADDITIONAL ENDPOINT:**
- POST /swap-executed: Receives callback from GCHostPay1 after ETH payment executed
  - Fetches all records for batch_conversion_id
  - Calculates proportional USDT distribution based on actual_usdt_received
  - Updates each record with usdt_share
  - Finalizes batch conversion
  - TERMINATES workflow

---

### 12. **GCBatchProcessor-10-26** (Threshold Payout Processor)
**Function:** Triggered by Cloud Scheduler every 5 minutes to process client threshold payouts

**INPUT:**
- POST /process (from Cloud Scheduler every 5 min)
- No payload - scheduler trigger

**FUNCTION:**
- Queries payout_accumulation for clients >= payout_threshold
- For each client over threshold:
  - Generates batch_id
  - Creates payout_batch record
  - Encrypts batch token for **GCSplit1-10-26**
  - Enqueues to GCSplit1 for batch payout processing
  - Marks accumulations as paid_out

**OUTPUT:**
- Enqueues to **GCSplit1-10-26** (GCSPLIT1_BATCH_QUEUE)
- Target: `/batch-payout`
- Payload: batch_id, client_id, wallet_address, payout_currency, payout_network, total_amount_usdt
- Workflow continues through GCSplit1 → GCSplit2 → GCSplit3 → GCHostPay1/2/3
- TERMINATES after GCHostPay3 executes payment

---

## SUPPORTING SERVICES (Not in payment flow)

### **GCRegister10-26** (Legacy Form-Based Registration)
**Function:** HTML form for channel registration
- Simple Flask web form
- Validates channel ID, subscription details
- Stores in main_clients_database

### **GCRegisterAPI-10-26** (RESTful API for Registration)
**Function:** RESTful API for channel management
- JWT authentication
- CRUD operations for channels
- User account management
- Endpoints: /auth/login, /auth/signup, /channels, /mappings

### **GCRegisterWeb-10-26** (React Frontend)
**Function:** Modern React SPA for channel registration
- Built with Vite + TypeScript
- Connects to GCRegisterAPI-10-26
- Features: login, signup, channel registration, channel editing

### **TelePay10-26** (Telegram Bot)
**Function:** User-facing Telegram bot
- Handles user interactions
- Creates NowPayments invoices with success_url tokens
- Manages subscriptions and broadcasts
- Not part of payment processing workflow

---

## KEY ARCHITECTURAL PATTERNS

### **Encryption & Token Flow**
- All inter-service communication uses encrypted tokens with HMAC signatures
- TokenManager handles encryption/decryption with service-specific methods
- Tokens expire after 2 hours (timestamp validation)
- Supports negative Telegram IDs (48-bit encoding)

### **Cloud Tasks Orchestration**
- All service-to-service communication via Cloud Tasks queues
- Enables retry logic with controlled backoff
- Prevents tight coupling between services
- Each service has dedicated queues for different workflows

### **Database Architecture**
- **private_channel_users_database**: Subscription records
- **main_clients_database**: Channel configuration
- **payout_accumulation**: Threshold payout accumulation
- **batch_conversions**: Micro-batch conversion records
- **split_payout_request**: Instant payout requests
- **split_payout_que**: ChangeNow swap queue
- **hostpay_transactions**: ETH payment logs
- **failed_transactions**: Failed payment records

### **Retry & Error Handling**
- ChangeNow API calls: Infinite retry with exponential backoff
- ETH payments: 3-attempt limit with error classification
- Cloud Tasks: Automatic retry on 503 responses
- Failed transactions stored with error details and alerting

### **Two-Phase Payment Processing**
1. **Validation Phase**: np-webhook validates IPN, calculates outcome_amount_usd
2. **Execution Phase**: GCWebhook1 routes based on payout mode (instant vs threshold)

### **Market Value vs Declared Price**
- System uses ACTUAL outcome_amount_usd from CoinGecko (not declared subscription_price)
- Ensures accurate fee calculations and payout amounts
- Handles crypto volatility during payment processing

---

## WORKFLOW SUMMARY

### INSTANT PAYOUT (User pays → Gets invite + Client gets paid)
```
User Payment
    ↓
NowPayments IPN → np-webhook-10-26
    ↓ (validates, calculates outcome_amount_usd)
GCWebhook1-10-26
    ↓ (routes based on payout_mode)
    ├─→ GCWebhook2-10-26 (sends Telegram invite) [TERMINATES]
    └─→ GCSplit1-10-26
            ↓ (removes TP fee)
        GCSplit2-10-26 (USDT→ETH estimate)
            ↓
        GCSplit1-10-26 (/usdt-eth-estimate)
            ↓ (calculates pure market ETH)
        GCSplit3-10-26 (creates ETH→Client swap)
            ↓
        GCSplit1-10-26 (/eth-client-swap)
            ↓ (builds GCHostPay token)
        GCHostPay1-10-26
            ↓ (validates)
        GCHostPay2-10-26 (checks ChangeNow status)
            ↓
        GCHostPay1-10-26 (/status-verified)
            ↓
        GCHostPay3-10-26 (executes ETH payment)
            ↓
        GCHostPay1-10-26 (/payment-completed) [TERMINATES]
```

### THRESHOLD PAYOUT (User pays → Gets invite, Payment accumulates until threshold)
```
User Payment
    ↓
NowPayments IPN → np-webhook-10-26
    ↓ (validates, calculates outcome_amount_usd)
GCWebhook1-10-26
    ↓ (routes based on payout_mode)
    ├─→ GCWebhook2-10-26 (sends Telegram invite) [TERMINATES]
    └─→ GCAccumulator-10-26 (stores with status='pending') [TERMINATES]

[Later: Cloud Scheduler triggers every 15 minutes]
GCMicroBatchProcessor-10-26 (/check-threshold)
    ↓ (if total >= threshold)
    ├─→ Creates ChangeNow ETH→USDT swap
    ├─→ Updates records to status='swapping'
    └─→ GCHostPay1-10-26 (context='batch')
            ↓
        GCHostPay2-10-26 (checks ChangeNow status)
            ↓
        GCHostPay1-10-26 (/status-verified)
            ↓
        GCHostPay3-10-26 (executes ETH payment)
            ↓
        GCHostPay1-10-26 (/payment-completed)
            ↓ (queries ChangeNow for actual USDT)
        GCMicroBatchProcessor-10-26 (/swap-executed)
            ↓ (distributes USDT proportionally) [TERMINATES]

[Later: Cloud Scheduler triggers every 5 minutes]
GCBatchProcessor-10-26 (/process)
    ↓ (finds clients >= payout_threshold)
    └─→ GCSplit1-10-26 (/batch-payout)
            ↓ (continues through standard conversion flow)
        GCSplit2-10-26 → GCSplit3-10-26 → GCHostPay1/2/3 [TERMINATES]
```

---

## TERMINATION POINTS

1. **GCWebhook2-10-26** - After sending Telegram invite
2. **GCHostPay1-10-26** (/payment-completed) - After instant payout execution
3. **GCAccumulator-10-26** - After storing threshold payment
4. **GCMicroBatchProcessor-10-26** (/swap-executed) - After distributing batch USDT
5. **GCHostPay3-10-26** - After 3 failed attempts (stores in failed_transactions)

---

## CRITICAL DEPENDENCIES

- **Cloud SQL PostgreSQL**: All database operations
- **Cloud Tasks**: All inter-service communication
- **ChangeNow API**: All currency conversions
- **CoinGecko API**: Crypto price fetching for outcome_amount_usd
- **NowPayments API**: Payment processing and IPN callbacks
- **Telegram Bot API**: User invite link generation
- **Google Secret Manager**: Configuration and API keys
- **Ethereum RPC (Alchemy)**: ETH payment execution
