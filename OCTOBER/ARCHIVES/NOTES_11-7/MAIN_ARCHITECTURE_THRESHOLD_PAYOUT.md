# MAIN ARCHITECTURE - THRESHOLD PAYOUT FLOW

**Document Purpose:** Comprehensive outline of all services involved in the **THRESHOLD PAYOUT** flow, detailing their input, function, and output.

**Last Updated:** 2025-11-07

---

## Overview

When a client configures their payout strategy as "threshold" (instead of "instant"), payments accumulate until reaching a minimum threshold amount (e.g., $10 USD). Once the threshold is met, a batch conversion is triggered to convert accumulated funds and pay out to the client.

**Key Difference from Instant Payouts:**
- **Instant:** Payment → Immediate conversion → Immediate payout
- **Threshold:** Payment → Accumulate → Wait for threshold → Batch conversion → Batch payout

---

## Service Flow Diagram

```
┌─────────────────┐
│  NowPayments    │
│  (External API) │
└────────┬────────┘
         │ success_url callback
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: PAYMENT RECEPTION & ROUTING                            │
└─────────────────────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────────────┐           ┌─────────────────┐
│  GCWebhook1     │──────────▶│  GCWebhook2     │ (Parallel)
│  Entry Point    │           │  Telegram Invite│
└────────┬────────┘           └─────────────────┘
         │ Routes based on payout_strategy
         │ (threshold detected)
         ▼
┌─────────────────┐
│  GCAccumulator  │
│  Store Payment  │
└────────┬────────┘
         │ Stores in payout_accumulation (status='pending')
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: MICRO-BATCH CONVERSION (ETH→USDT)                      │
│ Triggered by Cloud Scheduler every 15 minutes                   │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│  GCMicroBatchProcessor  │◄──── Cloud Scheduler (Every 15 min)
│  Check Threshold        │
└────────┬────────────────┘
         │ If total pending >= threshold
         │ Creates batch ETH→USDT swap
         ▼
┌─────────────────┐
│  GCHostPay1     │
│  Orchestrator   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ GCHostPay2  │   │ GCHostPay3  │   │ GCHostPay1  │
│ Status Check│──▶│ Execute Pay │──▶│ Callback    │
└─────────────┘   └─────────────┘   └──────┬──────┘
                                            │
                                            ▼
                                  ┌─────────────────────────┐
                                  │  GCMicroBatchProcessor  │
                                  │  /swap-executed         │
                                  └──────────┬──────────────┘
                                            │ Updates payout_accumulation
                                            │ (status='confirmed', accumulated_usdt set)
                                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: BATCH CLIENT PAYOUT (USDT→ClientCurrency)              │
│ Triggered by Cloud Scheduler every 5 minutes                    │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│  GCBatchProcessor   │◄──── Cloud Scheduler (Every 5 min)
│  Find Clients       │
│  Over Threshold     │
└────────┬────────────┘
         │ If client's total_usdt >= client_threshold
         │ Creates batch record
         ▼
┌─────────────────┐
│  GCSplit1       │
│  Orchestrator   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  GCSplit2   │   │  GCSplit3   │   │  GCSplit1   │
│  Estimator  │──▶│  Swapper    │──▶│  Callback   │
└─────────────┘   └─────────────┘   └──────┬──────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │  GCHostPay1     │
                                   │  Final ETH Pay  │
                                   └─────────────────┘
                                            │
                                            ▼
                                      Client receives
                                      payout in their
                                      chosen currency
```

---

## PHASE 1: PAYMENT RECEPTION & ROUTING

### 🔹 GCWebhook1 - Payment Reception & Routing Orchestrator

**PURPOSE:** Entry point for all NowPayments callbacks. Validates payment, writes to database, and routes to either instant (GCSplit1) or threshold (GCAccumulator) based on client configuration.

**INPUT:**
- **Source:** NowPayments API `success_url` callback (HTTP GET)
- **Parameters:**
  - `token` (URL parameter): Encrypted token containing:
    - `user_id` (Telegram user ID)
    - `closed_channel_id` (Telegram channel ID)
    - `wallet_address` (Client's payout wallet)
    - `payout_currency` (e.g., "shib", "xmr", "doge")
    - `payout_network` (e.g., "eth", "xmr")
    - `subscription_time_days` (Subscription duration)
    - `subscription_price` (USD amount)

**FUNCTION:**
1. Decrypts and validates token from NowPayments
2. Calculates subscription expiration date (current_time + subscription_time_days)
3. Writes to `private_channel_users_database` table
4. Encrypts token for GCWebhook2 (Telegram invite)
5. Enqueues Cloud Task to GCWebhook2 (parallel process)
6. **Queries database for payout_strategy** (`instant` or `threshold`)
7. **If threshold:**
   - Queries subscription_id from database
   - Enqueues Cloud Task to **GCAccumulator** with payment data
8. **If instant:**
   - Enqueues Cloud Task to **GCSplit1** for immediate conversion

**OUTPUT:**
- **To GCWebhook2 (via Cloud Tasks):**
  - Queue: `gcwebhook2-queue`
  - Encrypted token with user/channel/subscription data
- **To GCAccumulator (via Cloud Tasks):** *(THRESHOLD ONLY)*
  - Queue: `gcaccumulator-queue`
  - JSON payload:
    - `user_id`
    - `client_id` (closed_channel_id)
    - `wallet_address`
    - `payout_currency`
    - `payout_network`
    - `payment_amount_usd` (subscription_price)
    - `subscription_id`
    - `payment_timestamp`
    - `nowpayments_payment_id` (optional)
    - `nowpayments_pay_address` (optional)
    - `nowpayments_outcome_amount` (actual ETH received, optional)
- **To NowPayments:** HTTP 200 OK (acknowledges callback)
- **Database Write:** `private_channel_users_database` table

**TERMINATION:** Does NOT terminate - triggers downstream services via Cloud Tasks

---

### 🔹 GCWebhook2 - Telegram Invitation Sender

**PURPOSE:** Sends Telegram one-time invitation link to user (runs in PARALLEL to payment flow, not blocking).

**INPUT:**
- **Source:** GCWebhook1 via Cloud Tasks (HTTP POST)
- **Queue:** `gcwebhook2-queue`
- **Payload:**
  - `token` (encrypted): Contains user_id, closed_channel_id, subscription data
  - `payment_id`: NowPayments payment ID for idempotency

**FUNCTION:**
1. Checks idempotency: Has invite already been sent for this payment_id?
2. If already sent, returns success immediately (Cloud Tasks marks as complete)
3. Validates payment: Queries NowPayments IPN data to confirm payment received
4. Creates fresh Bot instance (per-request to avoid event loop issues)
5. Uses asyncio.run() to execute async Telegram API calls in isolated event loop
6. Creates Telegram invite link via `bot.create_chat_invite_link()`
7. Sends invite message to user via `bot.send_message()`
8. Updates `processed_payments` table with invite link and timestamp

**OUTPUT:**
- **To User:** Telegram message with one-time invitation link
- **To Cloud Tasks:** HTTP 200 (success) or HTTP 500 (retry after 60s)
- **Database Write:** `processed_payments.telegram_invite_sent = true`

**TERMINATION:** YES - This is a terminal service (sends invite and completes)

---

## PHASE 2: ACCUMULATION & MICRO-BATCH CONVERSION

### 🔹 GCAccumulator - Payment Accumulation Service

**PURPOSE:** Receives threshold payout payments, stores in accumulation table with "pending" status, and queues ETH→USDT conversion request to GCSplit2.

**INPUT:**
- **Source:** GCWebhook1 via Cloud Tasks (HTTP POST)
- **Queue:** `gcaccumulator-queue`
- **Payload:**
  - `user_id`
  - `client_id`
  - `wallet_address`
  - `payout_currency`
  - `payout_network`
  - `payment_amount_usd` (subscription price)
  - `subscription_id`
  - `payment_timestamp`
  - `nowpayments_payment_id` (optional)
  - `nowpayments_pay_address` (optional)
  - `nowpayments_outcome_amount` (actual ETH received, optional)

**FUNCTION:**
1. Calculates adjusted amount after TP fee (default 3%):
   - `fee_amount = payment_amount_usd * (tp_flat_fee / 100)`
   - `adjusted_amount_usd = payment_amount_usd - fee_amount`
2. Stores payment in `payout_accumulation` table:
   - `status = 'pending'` (awaiting conversion)
   - `accumulated_eth = adjusted_amount_usd` (USD value, not yet converted)
   - `accumulated_usdt = NULL` (will be set after conversion)
   - `nowpayments_outcome_amount` (actual ETH from NowPayments)
3. Encrypts token for GCSplit2 (ETH→USDT estimate request)
4. Enqueues Cloud Task to GCSplit2

**OUTPUT:**
- **To GCSplit2 (via Cloud Tasks):**
  - Queue: `gcsplit2-queue`
  - Encrypted token with:
    - `accumulation_id` (database row ID)
    - `adjusted_amount_usd`
    - `actual_eth_amount` (from NowPayments)
- **Database Write:** New row in `payout_accumulation` table (status='pending')
- **To Client (response):** HTTP 200 (acknowledged)

**TERMINATION:** Does NOT terminate - Triggers GCSplit2 for conversion

---

### 🔹 GCMicroBatchProcessor - Micro-Batch Threshold Checker & Swap Creator

**PURPOSE:** Triggered by Cloud Scheduler every 15 minutes. Checks if total pending USD >= micro-batch threshold. If yes, creates a batch ETH→USDT swap via ChangeNow and enqueues to GCHostPay1 for execution.

**INPUT:**
- **Source:** Cloud Scheduler (HTTP POST every 15 minutes)
- **Endpoint:** `/check-threshold`
- **Trigger:** `gcmicrobatchprocessor-scheduler` (Cloud Scheduler job)

**FUNCTION:**
1. Fetches `MICRO_BATCH_THRESHOLD_USD` from Secret Manager (e.g., $5.00)
2. Queries `payout_accumulation` for total pending USD:
   ```sql
   SELECT SUM(accumulated_eth) as total_pending
   FROM payout_accumulation
   WHERE status = 'pending'
   ```
3. Queries total pending ACTUAL ETH from NowPayments:
   ```sql
   SELECT SUM(nowpayments_outcome_amount) as total_actual_eth
   FROM payout_accumulation
   WHERE status = 'pending' AND nowpayments_outcome_amount IS NOT NULL
   ```
4. **If total_pending < threshold:** Returns early (no action)
5. **If total_pending >= threshold:**
   - Generates batch conversion ID (UUID)
   - Fetches all pending records from `payout_accumulation`
   - Creates ChangeNow ETH→USDT swap:
     - Calls `changenow_client.create_fixed_rate_transaction()`
     - `from_currency = "eth"`
     - `to_currency = "usdt"`
     - `from_amount = total_actual_eth`
     - `to_address = host_wallet_usdt_address`
   - Creates batch record in `batch_conversions` table:
     - `batch_conversion_id = UUID`
     - `status = 'processing'`
     - `changenow_id = cn_api_id`
     - `eth_amount = total_actual_eth`
     - `expected_usdt = estimated_amount`
   - Updates ALL pending records to status='swapping'
   - Encrypts token for GCHostPay1
   - Enqueues Cloud Task to GCHostPay1 for payment execution

6. Stores batch in `batch_conversions` table for tracking

**OUTPUT:**
- **To GCHostPay1 (via Cloud Tasks):**
  - Queue: `gchostpay1-queue`
  - Encrypted token:
    - `unique_id = "batch_{batch_conversion_id}"` (42 chars)
    - `cn_api_id` (ChangeNow transaction ID)
    - `from_currency = "eth"`
    - `from_network = "eth"`
    - `actual_eth_amount` (total ETH to send)
    - `estimated_eth_amount` (ChangeNow estimate)
    - `payin_address` (ChangeNow deposit address)
- **Database Write:**
  - New row in `batch_conversions` table (status='processing')
  - Updates `payout_accumulation` rows (status='swapping')
- **To Scheduler:** HTTP 200 (summary JSON)

**TERMINATION:** Does NOT terminate - Triggers GCHostPay1 for payment execution

---

### 🔹 GCHostPay1 - Validator & Payment Orchestrator

**PURPOSE:** Central orchestrator for payment execution. Validates payment requests, checks ChangeNow status via GCHostPay2, and executes ETH payments via GCHostPay3. Handles both instant and batch (threshold) payouts.

**ENDPOINTS:**
- `POST /` - Main webhook (receives from GCSplit1 or GCMicroBatchProcessor)
- `POST /status-verified` - Receives status check response from GCHostPay2
- `POST /payment-completed` - Receives payment execution response from GCHostPay3
- `POST /retry-callback-check` - Delayed retry for ChangeNow status check

**INPUT (Main Endpoint `/`):**
- **Source:** GCMicroBatchProcessor (batch) or GCSplit1 (instant) via Cloud Tasks
- **Payload:** Encrypted token with:
  - `unique_id` (e.g., "batch_fc3f8f55-c123-4567-..." or "instant123")
  - `cn_api_id` (ChangeNow transaction ID)
  - `from_currency` ("eth" or "usdt")
  - `from_network` ("eth")
  - `actual_eth_amount` (amount to send)
  - `estimated_eth_amount` (ChangeNow estimate)
  - `payin_address` (ChangeNow deposit address)

**FUNCTION:**
1. **Decrypts and validates token**
2. **Writes to database:**
   - For instant: `split_payout_hostpay` table
   - For batch: `batch_conversions` table (status='processing')
3. **Encrypts token for GCHostPay2** (status check request)
4. **Enqueues Cloud Task to GCHostPay2:**
   - Queue: `gchostpay2-queue`
   - Token contains: `unique_id`, `cn_api_id`
5. **Waits for GCHostPay2 callback** (receives at `/status-verified`)
6. **On status verified:**
   - If status = "waiting"/"confirming"/"exchanging"/"sending":
     - Enqueues delayed retry (5 min) to `/retry-callback-check`
     - Up to 3 retries (total 15 minutes)
   - If status = "finished"/"failed":
     - Proceeds to payment execution
7. **Encrypts token for GCHostPay3** (payment execution request)
8. **Enqueues Cloud Task to GCHostPay3:**
   - Queue: `gchostpay3-queue`
   - Token contains: full payment details
9. **Waits for GCHostPay3 callback** (receives at `/payment-completed`)
10. **On payment completed:**
    - Queries ChangeNow API for final transaction status
    - Extracts actual amounts received
    - **Routes callback based on context:**
      - **Batch (threshold):** Sends to GCMicroBatchProcessor `/swap-executed`
      - **Instant:** Sends to GCSplit1 `/swap-executed` (not part of threshold flow)

**OUTPUT:**
- **To GCHostPay2 (via Cloud Tasks):**
  - Queue: `gchostpay2-queue`
  - Encrypted token with `unique_id`, `cn_api_id`
- **To GCHostPay3 (via Cloud Tasks):**
  - Queue: `gchostpay3-queue`
  - Encrypted token with full payment details
- **To GCMicroBatchProcessor (via Cloud Tasks):** *(BATCH/THRESHOLD ONLY)*
  - Queue: `gcmicrobatchprocessor-response-queue`
  - Encrypted token:
    - `batch_conversion_id` (UUID)
    - `cn_api_id`
    - `tx_hash` (Ethereum transaction hash)
    - `actual_usdt_received` (from ChangeNow)
- **Database Updates:**
  - `split_payout_hostpay` or `batch_conversions` status updates

**TERMINATION:** Does NOT terminate - Orchestrates multiple services, routes final callback to GCMicroBatchProcessor

---

### 🔹 GCHostPay2 - ChangeNow Status Checker

**PURPOSE:** Checks ChangeNow transaction status with infinite retry logic (60s backoff, 24h max duration). Returns status to GCHostPay1.

**INPUT:**
- **Source:** GCHostPay1 via Cloud Tasks (HTTP POST)
- **Queue:** `gchostpay2-queue`
- **Payload:** Encrypted token with:
  - `unique_id`
  - `cn_api_id` (ChangeNow transaction ID)

**FUNCTION:**
1. Decrypts token from GCHostPay1
2. Calls ChangeNow API: `GET /v2/exchange/by-id/{cn_api_id}`
3. **Implements INFINITE RETRY via Cloud Tasks:**
   - On API failure: Returns HTTP 500
   - Cloud Tasks automatically retries after 60s
   - Max retry duration: 24 hours
4. Extracts status field from response (e.g., "waiting", "confirming", "finished")
5. Encrypts response token with status
6. Enqueues Cloud Task back to GCHostPay1 `/status-verified`

**OUTPUT:**
- **To GCHostPay1 (via Cloud Tasks):**
  - Queue: `gchostpay1-response-queue`
  - URL: `/status-verified`
  - Encrypted token:
    - `unique_id`
    - `cn_api_id`
    - `status` (ChangeNow transaction status)
- **To Cloud Tasks:** HTTP 200 (success) or HTTP 500 (retry)

**TERMINATION:** Does NOT terminate - Returns control to GCHostPay1

---

### 🔹 GCHostPay3 - ETH Payment Executor

**PURPOSE:** Executes ETH or ERC-20 token payments to ChangeNow deposit address with 3-attempt retry limit. Supports native ETH and ERC-20 tokens (USDT, USDC, DAI).

**INPUT:**
- **Source:** GCHostPay1 via Cloud Tasks (HTTP POST)
- **Queue:** `gchostpay3-queue`
- **Payload:** Encrypted token with:
  - `unique_id`
  - `from_currency` ("eth" or "usdt")
  - `from_network` ("eth")
  - `from_amount` (amount to send)
  - `payin_address` (ChangeNow deposit address)
  - `cn_api_id`
  - `attempt_count` (current retry attempt, default=1)
  - `context` ("instant" or "threshold")

**FUNCTION:**
1. Decrypts token from GCHostPay1
2. Extracts payment details and attempt count
3. **Checks attempt limit:** If attempt_count > 3, skips payment (prevents duplicate retries)
4. **Currency type detection:**
   - If `from_currency == "eth"`: Routes to native ETH transfer
   - If `from_currency in ["usdt", "usdc", "dai"]`: Routes to ERC-20 token transfer
   - Else: Returns 400 error (unsupported currency)
5. **Checks wallet balance:**
   - Native ETH: `wallet_manager.get_balance()`
   - ERC-20: `wallet_manager.get_erc20_balance(token_contract, decimals)`
6. **Executes payment (single attempt, no infinite retry):**
   - Native ETH: `wallet_manager.send_eth_payment_with_infinite_retry()`
   - ERC-20: `wallet_manager.send_erc20_token(token_contract, amount, decimals)`
7. **On SUCCESS:**
   - Extracts transaction hash
   - Encrypts response token
   - Enqueues callback to GCHostPay1 `/payment-completed`
8. **On FAILURE:**
   - Classifies error (retryable vs non-retryable)
   - **If attempt_count < 3:**
     - Increments attempt_count
     - Re-encrypts token with new attempt_count
     - Enqueues retry task to self (60s delay)
   - **If attempt_count >= 3:**
     - Stores in `failed_transactions` table
     - Sends alert via alerting service (Slack)
     - Returns failure to GCHostPay1

**OUTPUT:**
- **To GCHostPay1 (via Cloud Tasks):**
  - Queue: `gchostpay1-response-queue`
  - URL: `/payment-completed`
  - Encrypted token:
    - `unique_id`
    - `tx_hash` (Ethereum transaction hash)
    - `cn_api_id`
    - `from_currency`
    - `from_amount`
    - `context` ("instant" or "threshold")
- **To Self (retry, via Cloud Tasks):**
  - Queue: `gchostpay3-retry-queue`
  - Encrypted token with incremented `attempt_count`
- **Database Write (on failure):**
  - `failed_transactions` table
- **Alert (on max retries):**
  - Slack webhook notification

**TERMINATION:** Does NOT terminate - Returns control to GCHostPay1

---

### 🔹 GCMicroBatchProcessor - Swap Completion Handler (Callback Endpoint)

**PURPOSE:** Receives swap completion callback from GCHostPay1 after ETH→USDT conversion completes. Updates payout_accumulation records with actual USDT received.

**ENDPOINT:** `POST /swap-executed`

**INPUT:**
- **Source:** GCHostPay1 via Cloud Tasks (HTTP POST)
- **Queue:** `gcmicrobatchprocessor-response-queue`
- **Payload:** Encrypted token with:
  - `batch_conversion_id` (UUID)
  - `cn_api_id` (ChangeNow transaction ID)
  - `tx_hash` (Ethereum transaction hash)
  - `actual_usdt_received` (USDT received from ChangeNow)

**FUNCTION:**
1. Decrypts token from GCHostPay1 (30-minute expiration window to handle delays)
2. Validates token timestamp (allows up to 30 minutes for async workflow)
3. Extracts batch_conversion_id (full UUID, not truncated)
4. Queries `batch_conversions` table for batch details
5. Fetches all `payout_accumulation` records with status='swapping'
6. **Distributes USDT proportionally:**
   ```python
   for record in pending_records:
       proportion = record.accumulated_eth / total_pending_usd
       usdt_share = actual_usdt_received * proportion
       UPDATE payout_accumulation
       SET accumulated_usdt = usdt_share,
           status = 'confirmed',
           conversion_completed_at = NOW()
       WHERE id = record.id
   ```
7. Updates `batch_conversions` table:
   - `status = 'completed'`
   - `actual_usdt_received = actual_usdt_received`
   - `completed_at = NOW()`

**OUTPUT:**
- **Database Updates:**
  - `payout_accumulation` rows: status='confirmed', accumulated_usdt set
  - `batch_conversions` row: status='completed', actual_usdt_received set
- **To Client (response):** HTTP 200 (success)

**TERMINATION:** YES - This completes Phase 2 (micro-batch conversion). Records are now ready for Phase 3 (client payout).

---

## PHASE 3: CLIENT BATCH PAYOUT

### 🔹 GCBatchProcessor - Client Threshold Checker & Batch Creator

**PURPOSE:** Triggered by Cloud Scheduler every 5 minutes. Finds clients whose accumulated USDT >= client-specific threshold, creates batch payout records, and enqueues to GCSplit1 for USDT→ClientCurrency conversion.

**INPUT:**
- **Source:** Cloud Scheduler (HTTP POST every 5 minutes)
- **Endpoint:** `/process`
- **Trigger:** `gcbatchprocessor-scheduler` (Cloud Scheduler job)

**FUNCTION:**
1. Queries `payout_accumulation` grouped by `client_id`:
   ```sql
   SELECT
       client_id,
       SUM(accumulated_usdt) as total_usdt,
       COUNT(*) as payment_count,
       client_wallet_address,
       client_payout_currency,
       client_payout_network
   FROM payout_accumulation
   WHERE status = 'confirmed' AND accumulated_usdt IS NOT NULL
   GROUP BY client_id, client_wallet_address, client_payout_currency, client_payout_network
   HAVING SUM(accumulated_usdt) >= (
       SELECT payout_threshold_usd FROM client_table WHERE closed_channel_id = client_id
   )
   ```
2. For each client over threshold:
   - Generates batch ID (UUID)
   - Queries summed ACTUAL ETH for this client:
     ```sql
     SELECT SUM(nowpayments_outcome_amount) as total_actual_eth
     FROM payout_accumulation
     WHERE client_id = :client_id AND status = 'confirmed'
     ```
   - Creates batch record in `payout_batches` table:
     - `batch_id = UUID`
     - `client_id`
     - `total_amount_usdt`
     - `total_payments_count`
     - `client_wallet_address`
     - `client_payout_currency`
     - `client_payout_network`
     - `status = 'processing'`
   - Encrypts token for GCSplit1
   - Enqueues Cloud Task to GCSplit1 for batch payout
   - Updates `payout_accumulation` rows: status='paid_out', batch_id set

**OUTPUT:**
- **To GCSplit1 (via Cloud Tasks):**
  - Queue: `gcsplit1-queue`
  - Encrypted token:
    - `batch_id` (UUID)
    - `client_id`
    - `total_usdt`
    - `wallet_address`
    - `payout_currency`
    - `payout_network`
    - `actual_eth_total` (summed from accumulation records)
- **Database Writes:**
  - New row in `payout_batches` table (status='processing')
  - Updates `payout_accumulation` rows (status='paid_out', batch_id set)
- **To Scheduler:** HTTP 200 (summary JSON with batches_created count)

**TERMINATION:** Does NOT terminate - Triggers GCSplit1 for USDT→ClientCurrency conversion

---

### 🔹 GCSplit1 - Batch Payout Orchestrator

**PURPOSE:** Orchestrates USDT→ClientCurrency batch payout. Coordinates with GCSplit2 (estimator) and GCSplit3 (swapper) to create ChangeNow swap, then routes to GCHostPay for final payment execution.

**ENDPOINTS:**
- `POST /` - Main endpoint (receives batch from GCBatchProcessor)
- `POST /eth-estimate-response` - Receives estimate from GCSplit2
- `POST /eth-client-swap-response` - Receives swap details from GCSplit3

**INPUT (Main Endpoint `/`):**
- **Source:** GCBatchProcessor via Cloud Tasks (HTTP POST)
- **Queue:** `gcsplit1-queue`
- **Payload:** Encrypted token with:
  - `batch_id` (UUID)
  - `client_id`
  - `total_usdt`
  - `wallet_address`
  - `payout_currency` (e.g., "shib", "xmr")
  - `payout_network` (e.g., "eth", "xmr")
  - `actual_eth_total`

**FUNCTION:**
1. **Decrypts token** from GCBatchProcessor
2. **Calculates adjusted USDT** (after TP fee):
   - `fee_amount = total_usdt * (tp_flat_fee / 100)`
   - `adjusted_amount_usdt = total_usdt - fee_amount`
3. **Writes to database:**
   - Inserts row in `split_payout_request` table
4. **Encrypts token for GCSplit2** (USDT→ClientCurrency estimate)
5. **Enqueues Cloud Task to GCSplit2**
6. **Waits for GCSplit2 response** (receives at `/eth-estimate-response`)
7. **On estimate received:**
   - Extracts estimated client token quantity
   - Calculates `pure_market_eth_value` (for database accounting):
     ```python
     pure_market_eth_value = estimated_to_amount * (1 + changenow_fee_multiplier)
     ```
   - Writes to `split_payout_que` table
   - Encrypts token for GCSplit3
   - Enqueues Cloud Task to GCSplit3
8. **Waits for GCSplit3 response** (receives at `/eth-client-swap-response`)
9. **On swap created:**
   - Extracts ChangeNow transaction details
   - Writes to `split_payout_hostpay` table
   - **Routes to GCHostPay1** for ETH payment execution:
     - Encrypts token with `from_currency="usdt"` (NOT "eth")
     - Enqueues Cloud Task to GCHostPay1

**OUTPUT:**
- **To GCSplit2 (via Cloud Tasks):**
  - Queue: `gcsplit2-queue`
  - Encrypted token:
    - `user_id`
    - `closed_channel_id`
    - `wallet_address`
    - `payout_currency`
    - `payout_network`
    - `adjusted_amount_usdt`
    - `actual_eth_amount`
- **To GCSplit3 (via Cloud Tasks):**
  - Queue: `gcsplit3-queue`
  - Encrypted token:
    - `unique_id` (batch_id or user_id)
    - `user_id`
    - `closed_channel_id`
    - `wallet_address`
    - `payout_currency`
    - `payout_network`
    - `eth_amount` (adjusted_amount_usdt, NOT pure_market_eth_value)
    - `estimated_amount` (from GCSplit2)
    - `actual_eth_amount`
- **To GCHostPay1 (via Cloud Tasks):**
  - Queue: `gchostpay1-queue`
  - Encrypted token:
    - `unique_id = batch_id`
    - `cn_api_id` (ChangeNow transaction ID)
    - `from_currency = "usdt"` ✅ CRITICAL (not "eth")
    - `from_network = "eth"`
    - `actual_eth_amount` (USDT amount to send)
    - `estimated_eth_amount` (ChangeNow estimate)
    - `payin_address` (ChangeNow deposit address)
- **Database Writes:**
  - `split_payout_request` table
  - `split_payout_que` table
  - `split_payout_hostpay` table

**TERMINATION:** Does NOT terminate - Routes to GCHostPay1 for payment execution

---

### 🔹 GCSplit2 - USDT→ClientCurrency Estimator

**PURPOSE:** Calls ChangeNow API to get estimated exchange rate for USDT→ClientCurrency. Returns estimate to GCSplit1.

**INPUT:**
- **Source:** GCSplit1 via Cloud Tasks (HTTP POST)
- **Queue:** `gcsplit2-queue`
- **Payload:** Encrypted token with:
  - `user_id`
  - `closed_channel_id`
  - `wallet_address`
  - `payout_currency` (e.g., "shib")
  - `payout_network` (e.g., "eth")
  - `adjusted_amount_usdt`
  - `actual_eth_amount`

**FUNCTION:**
1. Decrypts token from GCSplit1
2. Calls ChangeNow API v2: `GET /v2/exchange/estimated-amount`
   - `from_currency = "usdt"` ✅ CRITICAL
   - `to_currency = payout_currency` (e.g., "shib")
   - `to_network = payout_network` (e.g., "eth")
   - `from_amount = adjusted_amount_usdt`
3. **Implements INFINITE RETRY via Cloud Tasks:**
   - On API failure: Returns HTTP 500
   - Cloud Tasks automatically retries after 60s
   - Max retry duration: 24 hours
4. Extracts estimated client token quantity (e.g., 596,726 SHIB)
5. Encrypts response token
6. Enqueues Cloud Task back to GCSplit1 `/eth-estimate-response`

**OUTPUT:**
- **To GCSplit1 (via Cloud Tasks):**
  - Queue: `gcsplit1-response-queue`
  - URL: `/eth-estimate-response`
  - Encrypted token:
    - Original fields from input token
    - `estimated_amount` (client token quantity from ChangeNow)
- **To Cloud Tasks:** HTTP 200 (success) or HTTP 500 (retry)

**TERMINATION:** Does NOT terminate - Returns control to GCSplit1

---

### 🔹 GCSplit3 - USDT→ClientCurrency Swap Creator

**PURPOSE:** Creates fixed-rate ChangeNow transaction for USDT→ClientCurrency conversion. Returns transaction details to GCSplit1.

**INPUT:**
- **Source:** GCSplit1 via Cloud Tasks (HTTP POST)
- **Queue:** `gcsplit3-queue`
- **Payload:** Encrypted token with:
  - `unique_id` (batch_id or user_id)
  - `user_id`
  - `closed_channel_id`
  - `wallet_address`
  - `payout_currency` (e.g., "shib")
  - `payout_network` (e.g., "eth")
  - `eth_amount` (USDT amount, NOT token quantity)
  - `estimated_amount` (client token quantity estimate)
  - `actual_eth_amount`

**FUNCTION:**
1. Decrypts token from GCSplit1
2. Creates ChangeNow fixed-rate transaction: `POST /v2/exchange`
   - `from_currency = "usdt"` ✅ CRITICAL (not "eth")
   - `to_currency = payout_currency` (e.g., "shib")
   - `from_amount = eth_amount` (USDT, e.g., 5.48)
   - `to_address = wallet_address` (client's wallet)
   - `to_network = payout_network`
3. **Implements INFINITE RETRY via Cloud Tasks:**
   - On API failure: Returns HTTP 500
   - Cloud Tasks automatically retries after 60s
   - Max retry duration: 24 hours
4. Extracts transaction details:
   - `id` (ChangeNow transaction ID)
   - `payinAddress` (deposit address)
   - `expectedAmountFrom` (USDT required)
   - `expectedAmountTo` (client token quantity)
5. Encrypts response token with full transaction data
6. Enqueues Cloud Task back to GCSplit1 `/eth-client-swap-response`

**OUTPUT:**
- **To GCSplit1 (via Cloud Tasks):**
  - Queue: `gcsplit1-response-queue`
  - URL: `/eth-client-swap-response`
  - Encrypted token:
    - Original fields from input token
    - `cn_api_id` (ChangeNow transaction ID)
    - `payin_address` (ChangeNow deposit address)
    - `expected_from` (USDT required)
    - `expected_to` (client token quantity)
    - `actual_eth_amount`
- **To Cloud Tasks:** HTTP 200 (success) or HTTP 500 (retry)

**TERMINATION:** Does NOT terminate - Returns control to GCSplit1

---

## FINAL STAGES: GCHostPay Payment Execution (Same as Phase 2)

After GCSplit3 creates the USDT→ClientCurrency swap, GCSplit1 routes the payment request to **GCHostPay1**, which orchestrates:

1. **GCHostPay1** → **GCHostPay2** (status check)
2. **GCHostPay1** → **GCHostPay3** (USDT payment execution to ChangeNow)
3. ChangeNow receives USDT, converts to client currency (e.g., SHIB), sends to client wallet

**Final Output:**
- Client receives their accumulated payout in their chosen currency (e.g., SHIB)
- Database records updated: `payout_batches` status='completed'

---

## Key Architectural Decisions

### 1. Two-Swap Architecture (ETH→USDT→ClientCurrency)

**Rationale:** USDT provides stable intermediate currency during accumulation period.

**Benefits:**
- Price stability: Accumulated funds maintain predictable USD value
- Reduced volatility risk: ETH price fluctuations don't affect accumulation value
- Simpler fee calculations: Known USDT value for all conversions
- Easier tracking: USD-denominated accumulation records

**Trade-offs:**
- Two ChangeNow swaps instead of one (higher fees)
- More complex orchestration (6 services for batch payouts vs 3 for instant)

### 2. Micro-Batch vs Individual Conversions

**Micro-Batch (ETH→USDT):**
- Triggered every 15 minutes by Cloud Scheduler
- Checks if total pending >= threshold (e.g., $5 USD)
- Converts ALL pending payments in single batch swap
- **Benefit:** Reduces ChangeNow API calls and gas costs

**Individual Client Batches (USDT→ClientCurrency):**
- Triggered every 5 minutes by Cloud Scheduler
- Checks if each client >= their threshold (e.g., $10 USD)
- One swap per client (each client may have different payout currency)
- **Benefit:** Respects individual client payout preferences

### 3. Idempotency & Retry Strategy

**GCWebhook2 (Telegram Invites):**
- Idempotency key: `payment_id`
- Checks `processed_payments.telegram_invite_sent` before sending
- Prevents duplicate invites if Cloud Tasks retries

**GCHostPay3 (Payment Execution):**
- 3-attempt retry limit with 60s delays
- Prevents infinite retries on non-retryable errors (e.g., insufficient balance)
- Failed transactions stored in `failed_transactions` table after max retries
- Alerting service sends Slack notification on max retries

**Token Expiration Windows:**
- GCWebhook1 → GCWebhook2: 5 minutes (sync)
- GCHostPay1 → GCHostPay2: 5 minutes (sync)
- GCHostPay1 → GCHostPay3: 2 hours (accounts for ChangeNow delays)
- GCHostPay1 → GCMicroBatchProcessor: 30 minutes (async callback with retry delays)

---

## Database Tables (Threshold Payouts)

### `payout_accumulation`
**Purpose:** Stores individual threshold payout payments pending batch conversion.

**Key Columns:**
- `id` (PRIMARY KEY)
- `client_id` (closed_channel_id)
- `user_id` (Telegram user ID)
- `subscription_id`
- `payment_amount_usd` (original subscription price)
- `payment_currency` ('usd')
- `payment_timestamp`
- `accumulated_eth` (USD value after TP fee, pending conversion)
- `accumulated_usdt` (USDT after conversion, initially NULL)
- `status` ('pending' → 'swapping' → 'confirmed' → 'paid_out')
- `client_wallet_address`
- `client_payout_currency` (e.g., 'shib')
- `client_payout_network` (e.g., 'eth')
- `batch_conversion_id` (FK to batch_conversions, set after micro-batch)
- `batch_id` (FK to payout_batches, set after client batch)
- `nowpayments_payment_id`
- `nowpayments_pay_address`
- `nowpayments_outcome_amount` (actual ETH from NowPayments)

### `batch_conversions`
**Purpose:** Tracks micro-batch ETH→USDT conversions.

**Key Columns:**
- `batch_conversion_id` (UUID, PRIMARY KEY)
- `status` ('processing' → 'completed')
- `changenow_id` (ChangeNow transaction ID)
- `eth_amount` (total ETH being converted)
- `expected_usdt` (estimated USDT from ChangeNow)
- `actual_usdt_received` (actual USDT after swap)
- `created_at`
- `completed_at`

### `payout_batches`
**Purpose:** Tracks client batch USDT→ClientCurrency payouts.

**Key Columns:**
- `batch_id` (UUID, PRIMARY KEY)
- `client_id` (closed_channel_id)
- `total_amount_usdt` (total USDT being paid out)
- `total_payments_count` (number of payments in batch)
- `client_wallet_address`
- `client_payout_currency`
- `client_payout_network`
- `status` ('processing' → 'completed')
- `created_at`
- `completed_at`

---

## Environment Variables / Secret Manager

**Threshold-Specific Configuration:**
- `MICRO_BATCH_THRESHOLD_USD` - Minimum USD to trigger ETH→USDT conversion (e.g., "5.00")
- `TP_FLAT_FEE` - Platform fee percentage (e.g., "3" for 3%)

**Service URLs (used for Cloud Tasks routing):**
- `GCACCUMULATOR_URL`
- `GCMICROBATCHPROCESSOR_URL`
- `GCBATCHPROCESSOR_URL`

**Queue Names (used for Cloud Tasks):**
- `GCACCUMULATOR_QUEUE`
- `GCMICROBATCHPROCESSOR_RESPONSE_QUEUE`
- `GCBATCHPROCESSOR_QUEUE`

---

## Cloud Scheduler Jobs

### `gcmicrobatchprocessor-scheduler`
- **Schedule:** Every 15 minutes
- **Target:** `GCMicroBatchProcessor /check-threshold`
- **Purpose:** Check if total pending USD >= micro-batch threshold

### `gcbatchprocessor-scheduler`
- **Schedule:** Every 5 minutes
- **Target:** `GCBatchProcessor /process`
- **Purpose:** Find clients over threshold and create batch payouts

---

## Summary: Threshold vs Instant Payout

| Aspect | Instant Payout | Threshold Payout |
|--------|----------------|------------------|
| **Trigger** | Immediate on payment | Accumulate until threshold |
| **Services** | 3 (GCWebhook1 → GCSplit1 → GCHostPay1) | 11 (full flow) |
| **Conversion** | Single swap (NowPayments currency → Client currency) | Two swaps (ETH→USDT, USDT→Client) |
| **Database** | `split_payout_*` tables | `payout_accumulation` + `batch_*` tables |
| **Orchestration** | Cloud Tasks (immediate) | Cloud Scheduler + Cloud Tasks |
| **Latency** | ~5-10 minutes | Hours to days (depends on threshold) |
| **Gas Efficiency** | Lower (one transaction per payment) | Higher (batch multiple payments) |
| **Volatility Risk** | Lower (immediate conversion) | Mitigated (USDT intermediate) |
| **Use Case** | High-value subscriptions | Low-value subscriptions |

---

## End-to-End Flow Summary (Threshold Payout)

```
User pays for subscription ($1.35 in BTC)
    ↓
NowPayments converts to ETH (receives 0.000573 ETH, outcome_amount)
    ↓
GCWebhook1 receives success_url, routes to GCAccumulator (threshold detected)
    ↓
GCAccumulator stores payment (status='pending', accumulated_eth=$1.35 after fee)
    ↓
... User pays again ($1.35) and again ($1.35) ...
    ↓
Total pending = $4.05 (still below $5 threshold)
    ↓
... User pays again ($1.35) ...
    ↓
Total pending = $5.40 (>= $5 threshold!)
    ↓
GCMicroBatchProcessor creates batch ETH→USDT swap (0.00186 ETH → $5.40 USDT)
    ↓
GCHostPay1 orchestrates payment execution
    ↓
GCHostPay3 sends 0.00186 ETH to ChangeNow deposit address
    ↓
ChangeNow converts ETH to USDT, sends to platform wallet
    ↓
GCHostPay1 queries ChangeNow, gets actual USDT received ($5.31 after ChangeNow fees)
    ↓
GCHostPay1 sends callback to GCMicroBatchProcessor
    ↓
GCMicroBatchProcessor distributes USDT proportionally:
    - Payment 1: $1.33 USDT
    - Payment 2: $1.33 USDT
    - Payment 3: $1.33 USDT
    - Payment 4: $1.32 USDT
    ↓
All records updated: status='confirmed', accumulated_usdt set
    ↓
... 5 minutes later (Cloud Scheduler) ...
    ↓
GCBatchProcessor checks client thresholds
    ↓
Client A: $5.31 USDT accumulated (>= $10 client threshold? NO)
    ↓
... User continues paying ... eventually reaches $10.50 USDT
    ↓
GCBatchProcessor creates batch payout (USDT→SHIB swap)
    ↓
GCSplit1 orchestrates USDT→SHIB conversion
    ↓
GCSplit2 estimates: $10.50 USDT → 596,726 SHIB
    ↓
GCSplit3 creates ChangeNow swap: USDT→SHIB
    ↓
GCHostPay3 sends 10.50 USDT to ChangeNow deposit address
    ↓
ChangeNow converts USDT to SHIB, sends to client wallet
    ↓
Client receives 596,726 SHIB in their wallet
    ↓
END - Payment complete
```

**Total Services Involved in Threshold Payout:** 11 services + Cloud Scheduler
- GCWebhook1, GCWebhook2, GCAccumulator, GCMicroBatchProcessor, GCBatchProcessor, GCSplit1, GCSplit2, GCSplit3, GCHostPay1, GCHostPay2, GCHostPay3

---

**Document Version:** 1.0
**Last Updated:** 2025-11-07
**Author:** Claude Code Analysis
