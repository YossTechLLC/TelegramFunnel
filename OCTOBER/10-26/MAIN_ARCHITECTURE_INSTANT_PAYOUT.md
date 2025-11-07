# MAIN ARCHITECTURE - INSTANT PAYOUT FLOW

**Document Purpose:** Comprehensive outline of all services involved in the **INSTANT PAYOUT** flow, detailing their input, function, and output.

**Last Updated:** 2025-11-07

---

## Overview

When a client configures their payout strategy as "instant" (default), payments are processed immediately without accumulation. As soon as NowPayments confirms payment, the system converts the crypto to the client's chosen payout currency and sends it to their wallet.

**Key Difference from Threshold Payouts:**
- **Instant:** Payment → Immediate conversion → Immediate payout (within minutes)
- **Threshold:** Payment → Accumulate → Wait for threshold → Batch conversion → Batch payout (hours to days)

**Advantages of Instant Payouts:**
- ✅ Lower latency (5-10 minutes total)
- ✅ Simpler architecture (fewer services)
- ✅ Predictable user experience (immediate gratification)
- ✅ Lower volatility exposure (immediate conversion)

**Trade-offs:**
- ⚠️ Higher gas costs per payment (no batching optimization)
- ⚠️ More ChangeNow API calls (one per payment vs batched)

---

## Service Flow Diagram

```
┌─────────────────┐
│  User Payment   │
│  (BTC/ETH/LTC)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  NowPayments    │ Converts to outcome currency
│  (External API) │ (typically ETH or USDT)
└────────┬────────┘
         │
    ┌────┴─────────────────┐
    │                      │
    ▼                      ▼
┌─────────────────┐  ┌─────────────────┐
│  success_url    │  │  IPN callback   │ (Optional)
│  GCWebhook1     │  │  np-webhook     │
└────────┬────────┘  └────────┬────────┘
         │                     │
         │                     └──────► Validates IPN
         │                              Updates processed_payments
         │                              Enqueues to GCWebhook1
         │                                      │
         └──────────────────────────────────────┘
                               │
         ┌─────────────────────┴──────────────────────┐
         │                                             │
         ▼                                             ▼
┌─────────────────────────────┐        ┌─────────────────────────────┐
│  GCWebhook1                 │        │  GCWebhook2                 │
│  Entry Point & Router       │───────▶│  Telegram Invite Sender     │
│  (Validates & Routes)       │        │  (Parallel Process)         │
└─────────────┬───────────────┘        └─────────────────────────────┘
              │                                      │
              │ Routes to GCSplit1                   │
              │ (instant detected)                   ▼
              │                              Sends invite to user
              ▼                              ✅ TERMINAL
┌─────────────────────────────┐
│  GCSplit1                   │
│  Payment Split Orchestrator │
└─────────────┬───────────────┘
              │
         ┌────┴────┐
         │         │
         ▼         ▼
┌─────────────┐   ┌─────────────┐
│  GCSplit2   │   │  GCSplit3   │
│  Estimator  │──▶│  Swapper    │
└─────────────┘   └──────┬──────┘
                         │
                         ▼
                  ┌─────────────┐
                  │  GCSplit1   │
                  │  Callback   │
                  └──────┬──────┘
                         │
                         ▼
                  ┌─────────────────┐
                  │  GCHostPay1     │
                  │  Orchestrator   │
                  └────────┬────────┘
                           │
                      ┌────┴────┐
                      │         │
                      ▼         ▼
                ┌─────────┐   ┌─────────┐
                │GCHostPay2│  │GCHostPay3│
                │ Status  │──▶│ Payment │
                └─────────┘   └────┬────┘
                                   │
                                   ▼
                            Sends crypto to
                            ChangeNow deposit
                                   │
                                   ▼
                            ChangeNow converts
                            and sends to client
                                   │
                                   ▼
                            Client receives payout
                            ✅ PAYMENT COMPLETE
```

---

## Phase 1: Payment Reception & Routing

### 🔹 np-webhook-10-26 - NowPayments IPN Handler (Optional Entry Point)

**PURPOSE:** Receives Instant Payment Notification (IPN) callbacks from NowPayments. Validates IPN signature, updates database with payment metadata, and triggers GCWebhook1 for payment processing.

**NOTE:** This service is an OPTIONAL alternative entry point. Payments can also be triggered via direct `success_url` callback to GCWebhook1.

**INPUT:**
- **Source:** NowPayments IPN API (HTTP POST)
- **Endpoint:** `POST /`
- **Headers:**
  - `x-nowpayments-sig`: HMAC-SHA512 signature
- **Payload (JSON):**
  ```json
  {
    "payment_id": 1234567890,
    "payment_status": "finished",
    "pay_address": "0xabc123...",
    "price_amount": 1.35,
    "price_currency": "usd",
    "pay_amount": 0.000573,
    "pay_currency": "eth",
    "order_id": "user123_channel456_sub789",
    "outcome_amount": 0.000573,
    "outcome_currency": "eth"
  }
  ```

**FUNCTION:**
1. **Receives IPN callback** from NowPayments
2. **Validates HMAC-SHA512 signature:**
   ```python
   expected_sig = hmac.new(
       IPN_SECRET.encode(),
       request.data,
       hashlib.sha512
   ).hexdigest()
   ```
3. **Parses order_id** to extract:
   - `user_id` (Telegram user ID)
   - `closed_channel_id` (Telegram channel ID)
   - `subscription_id` (database ID)
4. **Queries database** for payment details:
   ```sql
   SELECT wallet_address, payout_currency, payout_network, subscription_price
   FROM private_channel_users_database
   WHERE subscription_id = :subscription_id
   ```
5. **Fetches crypto-to-USD conversion rate** from CoinGecko API
6. **Calculates outcome_amount_usd:**
   ```python
   outcome_amount_usd = outcome_amount * crypto_usd_rate
   ```
7. **Updates `processed_payments` table:**
   ```sql
   INSERT INTO processed_payments (
       payment_id,
       order_id,
       payment_status,
       outcome_amount,
       outcome_currency,
       outcome_amount_usd
   ) VALUES (...)
   ON CONFLICT (payment_id) DO UPDATE ...
   ```
8. **Encrypts token for GCWebhook1** with payment data
9. **Enqueues Cloud Task to GCWebhook1:**
   - Queue: `gcwebhook1-queue`
   - Contains all payment details for processing

**OUTPUT:**
- **To GCWebhook1 (via Cloud Tasks):**
  - Queue: `gcwebhook1-queue`
  - URL: GCWebhook1 service URL
  - Payload: Encrypted token with:
    - `user_id`
    - `closed_channel_id`
    - `wallet_address`
    - `payout_currency`
    - `payout_network`
    - `subscription_price`
    - `nowpayments_payment_id`
    - `nowpayments_pay_address`
    - `nowpayments_outcome_amount`
    - `outcome_amount_usd`
- **Database Write:**
  - `processed_payments` table updated with IPN data
- **To NowPayments:** HTTP 200 OK (acknowledges IPN)

**TERMINATION:** Does NOT terminate - Triggers GCWebhook1 for processing

**PARALLEL PATH:** This service is optional. Payments can bypass np-webhook entirely if NowPayments sends `success_url` directly to GCWebhook1.

---

### 🔹 GCWebhook1 - Payment Entry Point & Router

**PURPOSE:** Primary entry point for payment confirmations. Validates payment, writes to database, and routes to appropriate handler based on payout strategy (instant → GCSplit1, threshold → GCAccumulator).

**INPUT:**
- **Source:** NowPayments `success_url` callback (HTTP GET) OR np-webhook-10-26 (HTTP POST via Cloud Tasks)
- **Method 1 - Direct from NowPayments:**
  - `GET /?token={encrypted_token}`
  - Token contains:
    - `user_id`
    - `closed_channel_id`
    - `wallet_address`
    - `payout_currency`
    - `payout_network`
    - `subscription_time_days`
    - `subscription_price`
- **Method 2 - From np-webhook-10-26:**
  - `POST /` (via Cloud Tasks)
  - Encrypted token from np-webhook with additional IPN data

**FUNCTION:**
1. **Decrypts and validates token** (HMAC signature verification)
2. **Calculates subscription expiration:**
   ```python
   expiration_datetime = now + timedelta(days=subscription_time_days)
   expire_time = expiration_datetime.strftime('%H:%M:%S')
   expire_date = expiration_datetime.strftime('%Y-%m-%d')
   ```
3. **Writes to `private_channel_users_database` table:**
   ```sql
   INSERT INTO private_channel_users_database (
       user_id,
       closed_channel_id,
       wallet_address,
       payout_currency,
       payout_network,
       expire_time,
       expire_date,
       subscription_price
   ) VALUES (...)
   ```
4. **Encrypts token for GCWebhook2** (Telegram invite)
5. **Enqueues Cloud Task to GCWebhook2** (parallel process):
   - Queue: `gcwebhook2-queue`
   - Contains: user_id, channel_id, subscription data, payment_id
6. **Queries NowPayments IPN data** for actual outcome amount:
   ```sql
   SELECT payment_id, outcome_amount, outcome_currency, outcome_amount_usd
   FROM processed_payments
   WHERE order_id LIKE '%user_id%closed_channel_id%'
   ORDER BY created_at DESC LIMIT 1
   ```
7. **Queries payout strategy** from client configuration:
   ```sql
   SELECT payout_strategy, payout_threshold_usd
   FROM client_table
   WHERE closed_channel_id = :closed_channel_id
   ```
8. **ROUTING DECISION - INSTANT PAYOUT PATH:**
   - If `payout_strategy == "instant"` (or default):
     - Logs: "⚡ Instant payout mode - processing immediately"
     - Encrypts token for GCSplit1
     - Enqueues Cloud Task to GCSplit1 with ACTUAL outcome amount
9. **ROUTING DECISION - THRESHOLD PAYOUT PATH:** *(Not covered in this doc)*
   - If `payout_strategy == "threshold"`:
     - Routes to GCAccumulator (see THRESHOLD document)

**OUTPUT:**

**For INSTANT Payouts:**
- **To GCWebhook2 (via Cloud Tasks):**
  - Queue: `gcwebhook2-queue`
  - Encrypted token with user/channel/subscription data
  - Includes `payment_id` for idempotency
- **To GCSplit1 (via Cloud Tasks):**
  - Queue: `gcsplit1-queue`
  - JSON payload:
    ```json
    {
      "user_id": "123456",
      "closed_channel_id": "789012",
      "wallet_address": "0xabc...",
      "payout_currency": "shib",
      "payout_network": "eth",
      "subscription_price": "1.35",
      "actual_eth_amount": 0.000573
    }
    ```
- **Database Write:**
  - `private_channel_users_database` table (new subscription record)
- **To NowPayments:** HTTP 200 OK

**TERMINATION:** Does NOT terminate - Triggers GCWebhook2 (parallel) and GCSplit1 (instant flow)

---

### 🔹 GCWebhook2 - Telegram Invitation Sender (Parallel Process)

**PURPOSE:** Sends Telegram one-time invitation link to user. Runs in PARALLEL to payment flow, does not block payout processing.

**INPUT:**
- **Source:** GCWebhook1 via Cloud Tasks (HTTP POST)
- **Queue:** `gcwebhook2-queue`
- **Payload:**
  - `token` (encrypted): Contains user_id, closed_channel_id, subscription data
  - `payment_id`: NowPayments payment ID for idempotency

**FUNCTION:**
1. **Checks idempotency:** Queries `processed_payments` table:
   ```sql
   SELECT telegram_invite_sent, telegram_invite_link, telegram_invite_sent_at
   FROM processed_payments
   WHERE payment_id = :payment_id
   ```
2. **If invite already sent:** Returns HTTP 200 immediately (Cloud Tasks marks success)
3. **Validates payment:** Confirms payment status = "finished" in database
4. **Validates minimum payment amount:**
   - Queries expected amount vs actual amount
   - Checks tolerance thresholds (50% minimum, 75% fallback)
   - If validation fails: Returns HTTP 500 (Cloud Tasks retries after 60s)
5. **Creates fresh Bot instance** (per-request to avoid event loop issues):
   ```python
   bot = Bot(token=bot_token)
   ```
6. **Uses asyncio.run()** to execute async Telegram operations in isolated event loop:
   ```python
   async def send_invite():
       invite_link = await bot.create_chat_invite_link(
           chat_id=closed_channel_id,
           member_limit=1,
           expire_date=int(time.time()) + 86400
       )
       await bot.send_message(
           chat_id=user_id,
           text=f"Welcome! Your invite: {invite_link.invite_link}"
       )
       return invite_link.invite_link

   invite_link = asyncio.run(send_invite())
   ```
7. **Updates `processed_payments` table:**
   ```sql
   UPDATE processed_payments
   SET telegram_invite_sent = true,
       telegram_invite_link = :invite_link,
       telegram_invite_sent_at = NOW()
   WHERE payment_id = :payment_id
   ```

**OUTPUT:**
- **To User:** Telegram direct message with one-time invitation link
- **Database Write:** `processed_payments` table (telegram_invite_sent = true)
- **To Cloud Tasks:** HTTP 200 (success) or HTTP 500 (retry after 60s with 24h max duration)

**TERMINATION:** ✅ YES - This is a TERMINAL service (completes after sending invite)

**RETRY STRATEGY:**
- Infinite retry via Cloud Tasks (60s fixed backoff)
- Max retry duration: 24 hours
- Idempotency ensures no duplicate invites

---

## Phase 2: Payment Split & Conversion

### 🔹 GCSplit1 - Payment Split Orchestrator

**PURPOSE:** Central orchestrator for instant payment conversions. Coordinates with GCSplit2 (estimator) and GCSplit3 (swap creator) to convert incoming crypto to client's chosen payout currency, then routes to GCHostPay for execution.

**ENDPOINTS:**
- `POST /` - Main webhook (receives from GCWebhook1)
- `POST /eth-estimate-response` - Receives estimate from GCSplit2
- `POST /eth-client-swap-response` - Receives swap details from GCSplit3

**INPUT (Main Endpoint `/`):**
- **Source:** GCWebhook1 via Cloud Tasks (HTTP POST) OR np-webhook via Cloud Tasks
- **Queue:** `gcsplit1-queue`
- **Payload (JSON):**
  ```json
  {
    "user_id": "123456",
    "closed_channel_id": "789012",
    "wallet_address": "0xabc123...",
    "payout_currency": "shib",
    "payout_network": "eth",
    "subscription_price": "1.35",
    "actual_eth_amount": 0.000573
  }
  ```
- **Signature:** HMAC-SHA256 in `X-Webhook-Signature` header

**FUNCTION:**

**Step 1: Initial Webhook Processing**
1. **Verifies HMAC signature** using `SUCCESS_URL_SIGNING_KEY`
2. **Parses JSON payload** and extracts payment details
3. **Validates required fields:**
   - user_id, closed_channel_id, wallet_address
   - payout_currency, payout_network, subscription_price
4. **Calculates adjusted amount** after platform fee:
   ```python
   tp_flat_fee = 3.0  # Default 3%
   fee_amount = subscription_price * (tp_flat_fee / 100)
   adjusted_amount_usdt = subscription_price - fee_amount
   # Example: $1.35 - $0.04 = $1.31 adjusted
   ```
5. **Encrypts token for GCSplit2** (USDT→ClientCurrency estimate request)
6. **Enqueues Cloud Task to GCSplit2:**
   - Queue: `gcsplit2-queue`
   - Token contains: user_id, wallet, currency, adjusted_amount_usdt, actual_eth_amount

**Step 2: Estimate Response Processing (Endpoint `/eth-estimate-response`)**
1. **Receives callback from GCSplit2** with estimated client token quantity
2. **Decrypts token** from GCSplit2
3. **Calculates pure market ETH value** (for database accounting):
   ```python
   # ChangeNow provides: expectedAmountFrom, expectedAmountTo, fees
   from_amount_usdt = adjusted_amount_usdt
   to_amount_post_fee = estimated_amount  # Client tokens after fees
   deposit_fee = 0.01  # Example ChangeNow deposit fee
   withdrawal_fee = 10000  # Example ChangeNow withdrawal fee (SHIB)

   # Back-calculate market rate
   usdt_swapped = from_amount_usdt - deposit_fee
   tokens_before_withdrawal = to_amount_post_fee + withdrawal_fee
   market_rate = tokens_before_withdrawal / usdt_swapped
   pure_market_value = from_amount_usdt * market_rate

   # Example: 1.31 USDT → 596,726 SHIB (pure market)
   ```
4. **Writes to database:**
   - **Table:** `split_payout_request`
   - **Purpose:** Initial payment record
   - **Data:**
     - user_id, closed_channel_id, wallet_address
     - from_amount = adjusted_amount_usdt ($1.31)
     - from_currency = "usdt"
     - to_amount = 0 (placeholder)
     - to_currency = payout_currency ("shib")
   - **Table:** `split_payout_que`
   - **Purpose:** Conversion queue record
   - **Data:**
     - from_amount = adjusted_amount_usdt ($1.31)
     - to_amount = pure_market_value (596,726 SHIB)
     - estimated_to_amount = estimated_amount (586,726 SHIB post-fee)
5. **Encrypts token for GCSplit3** (swap creation request)
6. **Enqueues Cloud Task to GCSplit3:**
   - Queue: `gcsplit3-queue`
   - Token contains: unique_id, user_id, wallet, currency, adjusted_amount_usdt, estimated_amount, actual_eth_amount

**Step 3: Swap Response Processing (Endpoint `/eth-client-swap-response`)**
1. **Receives callback from GCSplit3** with ChangeNow transaction details
2. **Decrypts token** from GCSplit3
3. **Extracts ChangeNow transaction data:**
   - `cn_api_id` (ChangeNow transaction ID, e.g., "613c822e844358")
   - `payin_address` (ChangeNow deposit address for USDT)
   - `expected_from` (USDT required, e.g., 1.31)
   - `expected_to` (SHIB expected, e.g., 586,726)
4. **Writes to database:**
   - **Table:** `split_payout_hostpay`
   - **Purpose:** Payment execution record for GCHostPay
   - **Data:**
     - unique_id = user_id (instant payment identifier)
     - cn_api_id = "613c822e844358"
     - from_currency = "usdt" ✅ CRITICAL
     - from_network = "eth"
     - from_amount = adjusted_amount_usdt (1.31)
     - payin_address = ChangeNow deposit address
     - to_address = wallet_address (client wallet)
     - to_currency = "shib"
     - to_network = "eth"
5. **Encrypts token for GCHostPay1** (payment execution request)
6. **Enqueues Cloud Task to GCHostPay1:**
   - Queue: `gchostpay1-queue`
   - Token contains: unique_id, cn_api_id, from_currency="usdt", from_amount, payin_address, actual_eth_amount

**OUTPUT:**

**To GCSplit2 (via Cloud Tasks):**
- Queue: `gcsplit2-queue`
- Encrypted token:
  - `user_id`
  - `closed_channel_id`
  - `wallet_address`
  - `payout_currency` (e.g., "shib")
  - `payout_network` (e.g., "eth")
  - `adjusted_amount_usdt` (e.g., 1.31)
  - `actual_eth_amount` (e.g., 0.000573)

**To GCSplit3 (via Cloud Tasks):**
- Queue: `gcsplit3-queue`
- Encrypted token:
  - `unique_id` (user_id for instant payments)
  - `user_id`
  - `closed_channel_id`
  - `wallet_address`
  - `payout_currency` (e.g., "shib")
  - `payout_network` (e.g., "eth")
  - `eth_amount` = adjusted_amount_usdt (1.31) ✅ CRITICAL: USDT not tokens
  - `estimated_amount` (586,726 SHIB)
  - `actual_eth_amount` (0.000573 ETH)

**To GCHostPay1 (via Cloud Tasks):**
- Queue: `gchostpay1-queue`
- Encrypted token:
  - `unique_id` = user_id (e.g., "user123")
  - `cn_api_id` (ChangeNow transaction ID)
  - `from_currency` = "usdt" ✅ CRITICAL
  - `from_network` = "eth"
  - `actual_eth_amount` = adjusted_amount_usdt (1.31 USDT to send)
  - `estimated_eth_amount` = expected_from (1.31 USDT)
  - `payin_address` (ChangeNow deposit address)

**Database Writes:**
- `split_payout_request` table (initial record)
- `split_payout_que` table (conversion queue)
- `split_payout_hostpay` table (payment execution record)

**TERMINATION:** Does NOT terminate - Routes to GCHostPay1 for payment execution

---

### 🔹 GCSplit2 - USDT→ClientCurrency Estimator

**PURPOSE:** Calls ChangeNow API to get estimated exchange rate for USDT→ClientCurrency conversion. Returns estimate to GCSplit1 for validation and database storage.

**INPUT:**
- **Source:** GCSplit1 via Cloud Tasks (HTTP POST)
- **Queue:** `gcsplit2-queue`
- **Payload:** Encrypted token with:
  - `user_id`
  - `closed_channel_id`
  - `wallet_address`
  - `payout_currency` (e.g., "shib")
  - `payout_network` (e.g., "eth")
  - `adjusted_amount_usdt` (e.g., 1.31)
  - `actual_eth_amount` (e.g., 0.000573)

**FUNCTION:**
1. **Decrypts token** from GCSplit1
2. **Logs payment details:**
   ```
   👤 User ID: 123456
   🏦 Wallet: 0xabc123...
   💰 Amount: 1.31 USDT
   💎 ACTUAL ETH (from NowPayments): 0.000573
   🎯 Target: SHIB on ETH network
   ```
3. **Calls ChangeNow API v2:** `GET /v2/exchange/estimated-amount`
   - **Request:**
     ```
     from_currency = "usdt"
     to_currency = "shib"
     to_network = "eth"
     from_amount = 1.31
     ```
   - **Implements INFINITE RETRY via Cloud Tasks:**
     - On API failure: Returns HTTP 500
     - Cloud Tasks automatically retries after 60s
     - Max retry duration: 24 hours
4. **Extracts estimate from response:**
   ```json
   {
     "estimatedAmount": 586726.7004304786,
     "transactionSpeedForecast": "10-60",
     "warningMessage": null
   }
   ```
5. **Logs estimate:**
   ```
   💱 ChangeNow estimate: 1.31 USDT → 586,726.70 SHIB
   ⏱️ Estimated time: 10-60 minutes
   ```
6. **Encrypts response token** with original data + estimated_amount
7. **Enqueues Cloud Task back to GCSplit1:**
   - Queue: `gcsplit1-response-queue`
   - URL: `/eth-estimate-response`

**OUTPUT:**
- **To GCSplit1 (via Cloud Tasks):**
  - Queue: `gcsplit1-response-queue`
  - URL: `/eth-estimate-response`
  - Encrypted token:
    - All original fields from input
    - `estimated_amount` = 586726.7004304786 (SHIB)
- **To Cloud Tasks:** HTTP 200 (success) or HTTP 500 (retry)

**TERMINATION:** Does NOT terminate - Returns control to GCSplit1

**RETRY STRATEGY:**
- Infinite retry via Cloud Tasks (60s fixed backoff)
- Max retry duration: 24 hours
- Handles ChangeNow API rate limits and downtime gracefully

---

### 🔹 GCSplit3 - USDT→ClientCurrency Swap Creator

**PURPOSE:** Creates fixed-rate ChangeNow transaction for USDT→ClientCurrency conversion. Returns transaction details (payin address, expected amounts) to GCSplit1.

**INPUT:**
- **Source:** GCSplit1 via Cloud Tasks (HTTP POST)
- **Queue:** `gcsplit3-queue`
- **Payload:** Encrypted token with:
  - `unique_id` (user_id for instant payments)
  - `user_id`
  - `closed_channel_id`
  - `wallet_address` (client's payout wallet)
  - `payout_currency` (e.g., "shib")
  - `payout_network` (e.g., "eth")
  - `eth_amount` = adjusted_amount_usdt (e.g., 1.31) ✅ USDT not tokens
  - `estimated_amount` (e.g., 586726.70 SHIB)
  - `actual_eth_amount` (e.g., 0.000573 ETH)

**FUNCTION:**
1. **Decrypts token** from GCSplit1
2. **Renames variable for clarity:**
   ```python
   usdt_amount = eth_amount  # Input is actually USDT, not ETH
   ```
3. **Logs payment details:**
   ```
   🆔 Unique ID: user123
   👤 User ID: 123456
   🏦 Wallet: 0xabc123...
   💰 USDT Amount: 1.31
   💎 ACTUAL ETH (from NowPayments): 0.000573
   🎯 Target: SHIB on ETH network
   ```
4. **Creates ChangeNow fixed-rate transaction:** `POST /v2/exchange`
   - **Request Body:**
     ```json
     {
       "from_currency": "usdt",
       "to_currency": "shib",
       "from_amount": 1.31,
       "to_address": "0xabc123...",
       "to_network": "eth",
       "flow": "fixed-rate"
     }
     ```
   - **Implements INFINITE RETRY via Cloud Tasks:**
     - On API failure: Returns HTTP 500
     - Cloud Tasks automatically retries after 60s
     - Max retry duration: 24 hours
5. **Extracts transaction details from response:**
   ```json
   {
     "id": "613c822e844358",
     "payinAddress": "0xChangeNowDepositAddress...",
     "payoutAddress": "0xabc123...",
     "fromCurrency": "usdt",
     "toCurrency": "shib",
     "fromNetwork": "eth",
     "toNetwork": "eth",
     "expectedAmountFrom": 1.31,
     "expectedAmountTo": 586726.70,
     "transactionSpeedForecast": "10-60"
   }
   ```
6. **Logs transaction creation:**
   ```
   ✅ ChangeNow transaction created
   🆔 Transaction ID: 613c822e844358
   📬 Deposit address: 0xChangeNowDepositAddress...
   💰 Expected input: 1.31 USDT
   💰 Expected output: 586,726.70 SHIB
   ⏱️ Estimated time: 10-60 minutes
   ```
7. **Encrypts response token** with transaction data
8. **Enqueues Cloud Task back to GCSplit1:**
   - Queue: `gcsplit1-response-queue`
   - URL: `/eth-client-swap-response`

**OUTPUT:**
- **To GCSplit1 (via Cloud Tasks):**
  - Queue: `gcsplit1-response-queue`
  - URL: `/eth-client-swap-response`
  - Encrypted token:
    - All original fields from input
    - `cn_api_id` = "613c822e844358"
    - `payin_address` = "0xChangeNowDepositAddress..."
    - `expected_from` = 1.31 (USDT)
    - `expected_to` = 586726.70 (SHIB)
    - `actual_eth_amount` = 0.000573
- **To Cloud Tasks:** HTTP 200 (success) or HTTP 500 (retry)

**TERMINATION:** Does NOT terminate - Returns control to GCSplit1

**RETRY STRATEGY:**
- Infinite retry via Cloud Tasks (60s fixed backoff)
- Max retry duration: 24 hours
- Handles ChangeNow API rate limits and downtime gracefully

---

## Phase 3: Payment Execution

### 🔹 GCHostPay1 - Payment Orchestrator & Validator

**PURPOSE:** Central orchestrator for payment execution. Validates payment requests, checks ChangeNow transaction status via GCHostPay2, and executes crypto payments via GCHostPay3. Handles both instant and batch (threshold) payouts.

**ENDPOINTS:**
- `POST /` - Main webhook (receives from GCSplit1 or GCMicroBatchProcessor)
- `POST /status-verified` - Receives status check response from GCHostPay2
- `POST /payment-completed` - Receives payment execution response from GCHostPay3
- `POST /retry-callback-check` - Delayed retry for ChangeNow status check

**INPUT (Main Endpoint `/` - INSTANT PAYOUTS):**
- **Source:** GCSplit1 via Cloud Tasks (HTTP POST)
- **Queue:** `gchostpay1-queue`
- **Payload:** Encrypted token with:
  - `unique_id` = user_id (e.g., "user123")
  - `cn_api_id` (ChangeNow transaction ID, e.g., "613c822e844358")
  - `from_currency` = "usdt" ✅ CRITICAL
  - `from_network` = "eth"
  - `actual_eth_amount` = USDT amount to send (e.g., 1.31)
  - `estimated_eth_amount` = expected USDT (e.g., 1.31)
  - `payin_address` (ChangeNow deposit address)

**FUNCTION:**

**Step 1: Initial Payment Request Processing**
1. **Decrypts token** from GCSplit1 using `TPS_HOSTPAY_SIGNING_KEY`
2. **Validates payment request:**
   - Checks required fields: unique_id, cn_api_id, from_currency, payin_address
   - Verifies from_currency is supported ("eth" or "usdt")
3. **Detects payment context:**
   ```python
   if unique_id.startswith("batch_"):
       context = "batch"  # Threshold payout
   else:
       context = "instant"  # Instant payout
   ```
4. **Writes to database:**
   - **For instant:** `split_payout_hostpay` table
   - **For batch:** `batch_conversions` table
   ```sql
   INSERT INTO split_payout_hostpay (
       unique_id,
       cn_api_id,
       from_currency,
       from_network,
       from_amount,
       payin_address,
       status
   ) VALUES (:unique_id, :cn_api_id, 'usdt', 'eth', 1.31, :payin_address, 'pending')
   ```
5. **Logs payment details:**
   ```
   🆔 Unique ID: user123
   🔗 ChangeNow ID: 613c822e844358
   💰 Amount: 1.31 USDT
   📬 Deposit address: 0xChangeNowDepositAddress...
   🎯 Context: instant
   ```
6. **Encrypts token for GCHostPay2** (status check request)
7. **Enqueues Cloud Task to GCHostPay2:**
   - Queue: `gchostpay2-queue`
   - Token contains: unique_id, cn_api_id

**Step 2: Status Verified Processing (Endpoint `/status-verified`)**
1. **Receives callback from GCHostPay2** with ChangeNow status
2. **Decrypts token** from GCHostPay2
3. **Extracts ChangeNow status:**
   - "waiting" - Transaction created, waiting for payment
   - "confirming" - Payment received, confirming on blockchain
   - "exchanging" - Exchange in progress
   - "sending" - Sending to recipient
   - "finished" - Transaction completed
   - "failed" - Transaction failed
4. **Decision logic:**
   - **If status in ["waiting", "confirming", "exchanging", "sending"]:**
     - Too early to proceed, swap not finished
     - Enqueues delayed retry (5 minutes) to `/retry-callback-check`
     - Up to 3 retries (total 15 minutes)
     - Logs: "⏳ Swap not finished, scheduling retry #1 in 300s"
   - **If status = "finished":**
     - Proceeds to payment execution
     - Logs: "✅ ChangeNow status verified: finished"
   - **If status = "failed":**
     - Logs error and sends alert
     - Does NOT proceed to payment execution
5. **Encrypts token for GCHostPay3** (payment execution request)
6. **Enqueues Cloud Task to GCHostPay3:**
   - Queue: `gchostpay3-queue`
   - Token contains: unique_id, from_currency, from_amount, payin_address, cn_api_id, attempt_count=1, context

**Step 3: Payment Completed Processing (Endpoint `/payment-completed`)**
1. **Receives callback from GCHostPay3** with payment execution result
2. **Decrypts token** from GCHostPay3
3. **Extracts payment result:**
   - `tx_hash` (Ethereum transaction hash)
   - `cn_api_id` (ChangeNow transaction ID)
   - `from_currency` (e.g., "usdt")
   - `from_amount` (e.g., 1.31)
   - `context` ("instant" or "batch")
4. **Queries ChangeNow API** for final transaction status:
   - Calls: `GET /v2/exchange/by-id/{cn_api_id}`
   - Extracts: `amountFrom`, `amountTo`, `status`
5. **Defensive amount parsing** (handles null/missing amounts):
   ```python
   def _safe_decimal(value):
       if value is None or value == "":
           return Decimal("0")
       try:
           return Decimal(str(value))
       except:
           return Decimal("0")

   actual_usdt_received = _safe_decimal(amountFrom)
   ```
6. **Updates database:**
   ```sql
   UPDATE split_payout_hostpay
   SET status = 'completed',
       tx_hash = :tx_hash,
       completed_at = NOW()
   WHERE unique_id = :unique_id
   ```
7. **Context-based routing:**
   - **For instant payouts (context="instant"):**
     - Logs: "✅ Instant payout completed"
     - Returns success to GCSplit1
     - Flow terminates here
   - **For batch payouts (context="batch"):**
     - Routes callback to GCMicroBatchProcessor
     - (See THRESHOLD document for details)

**OUTPUT:**

**To GCHostPay2 (via Cloud Tasks):**
- Queue: `gchostpay2-queue`
- Encrypted token:
  - `unique_id` (e.g., "user123")
  - `cn_api_id` (e.g., "613c822e844358")

**To GCHostPay3 (via Cloud Tasks):**
- Queue: `gchostpay3-queue`
- Encrypted token:
  - `unique_id`
  - `from_currency` = "usdt"
  - `from_network` = "eth"
  - `from_amount` = 1.31
  - `payin_address` (ChangeNow deposit address)
  - `cn_api_id`
  - `attempt_count` = 1
  - `context` = "instant"

**To Self (retry, via Cloud Tasks):**
- Queue: `gchostpay1-response-queue`
- URL: `/retry-callback-check`
- Encrypted token with retry_count incremented

**Database Updates:**
- `split_payout_hostpay` table (status: pending → completed)

**TERMINATION:** Does NOT terminate - Orchestrates GCHostPay2 and GCHostPay3, then completes flow for instant payouts

---

### 🔹 GCHostPay2 - ChangeNow Status Checker

**PURPOSE:** Checks ChangeNow transaction status with infinite retry logic (60s backoff, 24h max duration). Returns status to GCHostPay1 for validation before proceeding with payment execution.

**INPUT:**
- **Source:** GCHostPay1 via Cloud Tasks (HTTP POST)
- **Queue:** `gchostpay2-queue`
- **Payload:** Encrypted token with:
  - `unique_id` (e.g., "user123" for instant)
  - `cn_api_id` (ChangeNow transaction ID)

**FUNCTION:**
1. **Decrypts token** from GCHostPay1
2. **Logs status check:**
   ```
   🎯 Status check request received (from GCHostPay1)
   🆔 Unique ID: user123
   🔗 ChangeNow ID: 613c822e844358
   ```
3. **Calls ChangeNow API:** `GET /v2/exchange/by-id/{cn_api_id}`
   - **Implements INFINITE RETRY via Cloud Tasks:**
     - On API failure: Returns HTTP 500
     - Cloud Tasks automatically retries after 60s
     - Max retry duration: 24 hours
   - **Example Response:**
     ```json
     {
       "id": "613c822e844358",
       "status": "waiting",
       "fromCurrency": "usdt",
       "toCurrency": "shib",
       "fromNetwork": "eth",
       "toNetwork": "eth",
       "payinAddress": "0xChangeNowDepositAddress...",
       "payoutAddress": "0xabc123...",
       "amountFrom": null,
       "amountTo": null
     }
     ```
4. **Extracts status field:**
   - Possible values: "waiting", "confirming", "exchanging", "sending", "finished", "failed"
5. **Logs status result:**
   ```
   ✅ ChangeNow API response received
   📊 Status: waiting
   🔗 Transaction ID: 613c822e844358
   ```
6. **Encrypts response token** with status
7. **Enqueues Cloud Task back to GCHostPay1:**
   - Queue: `gchostpay1-response-queue`
   - URL: `/status-verified`

**OUTPUT:**
- **To GCHostPay1 (via Cloud Tasks):**
  - Queue: `gchostpay1-response-queue`
  - URL: `/status-verified`
  - Encrypted token:
    - `unique_id` (e.g., "user123")
    - `cn_api_id` (e.g., "613c822e844358")
    - `status` (e.g., "waiting")
- **To Cloud Tasks:** HTTP 200 (success) or HTTP 500 (retry)

**TERMINATION:** Does NOT terminate - Returns control to GCHostPay1

**RETRY STRATEGY:**
- Infinite retry via Cloud Tasks (60s fixed backoff)
- Max retry duration: 24 hours
- Handles ChangeNow API rate limits and downtime

---

### 🔹 GCHostPay3 - Crypto Payment Executor

**PURPOSE:** Executes ETH or ERC-20 token payments to ChangeNow deposit address with 3-attempt retry limit. Supports native ETH and ERC-20 tokens (USDT, USDC, DAI).

**INPUT:**
- **Source:** GCHostPay1 via Cloud Tasks (HTTP POST)
- **Queue:** `gchostpay3-queue`
- **Payload:** Encrypted token with:
  - `unique_id` (e.g., "user123")
  - `from_currency` (e.g., "usdt")
  - `from_network` (e.g., "eth")
  - `from_amount` (e.g., 1.31)
  - `payin_address` (ChangeNow deposit address)
  - `cn_api_id` (e.g., "613c822e844358")
  - `attempt_count` (default: 1)
  - `context` (e.g., "instant")

**FUNCTION:**
1. **Decrypts token** from GCHostPay1
2. **Validates attempt count:**
   ```python
   if attempt_count > 3:
       # Prevent duplicate Cloud Tasks retries
       return jsonify({"status": "skipped"}), 200
   ```
3. **Logs payment details:**
   ```
   🎯 Payment execution request received
   🆔 Unique ID: user123
   💰 Amount: 1.31 USDT
   📬 Destination: 0xChangeNowDepositAddress...
   🔗 ChangeNow ID: 613c822e844358
   🔄 Attempt: 1 of 3
   🎯 Context: instant
   ```
4. **Currency type detection:**
   ```python
   if from_currency == 'eth':
       currency_type = "NATIVE ETH"
   elif from_currency in ['usdt', 'usdc', 'dai']:
       currency_type = f"ERC-20 TOKEN ({TOKEN_CONFIGS[from_currency]['name']})"
   else:
       # Unsupported currency
       return error(400, f"Unsupported currency: {from_currency}")
   ```
5. **Checks wallet balance:**
   - **For native ETH:**
     ```python
     balance_eth = wallet_manager.get_balance()
     if balance_eth < from_amount:
         raise InsufficientFundsError
     ```
   - **For ERC-20 tokens:**
     ```python
     token_contract = TOKEN_CONFIGS[from_currency]['address']
     token_decimals = TOKEN_CONFIGS[from_currency]['decimals']
     balance_tokens = wallet_manager.get_erc20_balance(token_contract, token_decimals)
     if balance_tokens < from_amount:
         raise InsufficientFundsError
     ```
6. **Executes payment (single attempt, no infinite retry):**
   - **For native ETH:**
     ```python
     tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
         to_address=payin_address,
         amount=from_amount,
         unique_id=unique_id
     )
     ```
   - **For ERC-20 tokens (e.g., USDT):**
     ```python
     tx_result = wallet_manager.send_erc20_token(
         token_contract_address=TOKEN_CONFIGS['usdt']['address'],
         to_address=payin_address,
         amount=from_amount,
         token_decimals=6,  # USDT has 6 decimals
         unique_id=unique_id
     )
     ```
7. **On SUCCESS:**
   - Extracts transaction hash from result
   - Logs: "✅ Payment sent successfully, Tx: 0xabc123..."
   - Encrypts response token with tx_hash
   - Enqueues callback to GCHostPay1 `/payment-completed`
8. **On FAILURE:**
   - Classifies error (retryable vs non-retryable)
   - **If attempt_count < 3:**
     - Increments attempt_count
     - Re-encrypts token with new attempt_count
     - Enqueues retry task to self (60s delay)
     - Logs: "🔄 Retrying payment (attempt 2 of 3) in 60s"
   - **If attempt_count >= 3:**
     - Stores in `failed_transactions` table
     - Sends alert via Slack webhook
     - Returns failure to GCHostPay1
     - Logs: "❌ Max retries exceeded, storing in failed_transactions"

**OUTPUT:**

**On Success - To GCHostPay1 (via Cloud Tasks):**
- Queue: `gchostpay1-response-queue`
- URL: `/payment-completed`
- Encrypted token:
  - `unique_id` (e.g., "user123")
  - `tx_hash` (e.g., "0xabc123...")
  - `cn_api_id` (e.g., "613c822e844358")
  - `from_currency` (e.g., "usdt")
  - `from_amount` (e.g., 1.31)
  - `context` (e.g., "instant")

**On Retry - To Self (via Cloud Tasks):**
- Queue: `gchostpay3-retry-queue`
- Encrypted token with:
  - All original fields
  - `attempt_count` incremented (e.g., 2)

**On Max Retries - Database Write:**
- Table: `failed_transactions`
- Data:
  - unique_id, cn_api_id, from_currency, from_amount
  - payin_address, error_message, attempt_count
  - error_category (e.g., "INSUFFICIENT_BALANCE")
  - created_at

**On Max Retries - Alert:**
- Slack webhook notification with failure details

**TERMINATION:** Does NOT terminate - Returns control to GCHostPay1 on success

**RETRY STRATEGY:**
- 3-attempt retry limit (manual retry via Cloud Tasks)
- 60s delay between retries
- Prevents infinite retries on non-retryable errors (e.g., insufficient balance)
- Failed transactions stored in database after max retries

**ERC-20 SUPPORT:**
- Native ETH: 21,000 gas, 18 decimals
- USDT: 60,000-100,000 gas, 6 decimals, contract 0xdac17f958d2ee523a2206206994597c13d831ec7
- USDC: 60,000-100,000 gas, 6 decimals, contract 0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
- DAI: 60,000-100,000 gas, 18 decimals, contract 0x6b175474e89094c44da98b954eedeac495271d0f

---

## Payment Completion & Termination

After GCHostPay3 successfully sends crypto to ChangeNow deposit address:

1. **ChangeNow receives payment** (USDT deposit confirmed)
2. **ChangeNow converts USDT→ClientCurrency** (e.g., USDT→SHIB)
3. **ChangeNow sends client currency to client wallet** (e.g., 586,726 SHIB)
4. **Client receives payout** in their wallet
5. **GCHostPay1 receives callback** from GCHostPay3
6. **GCHostPay1 queries ChangeNow** for final transaction status
7. **GCHostPay1 updates database** with completion status
8. **Flow terminates** ✅ PAYMENT COMPLETE

**Total Flow Duration (Instant Payout):**
- User payment to NowPayments: ~30 seconds (blockchain confirmation)
- GCWebhook1 processing: ~2 seconds
- GCSplit1 orchestration: ~5 seconds (estimate + swap creation)
- GCHostPay1 status check: ~3 seconds
- GCHostPay3 payment execution: ~30 seconds (blockchain transaction)
- ChangeNow conversion: 10-60 minutes (advertised)
- **Total: ~11-61 minutes** from payment to payout

---

## Database Tables (Instant Payouts)

### `private_channel_users_database`
**Purpose:** Stores subscription records for users who paid.

**Key Columns:**
- `user_id` (Telegram user ID)
- `closed_channel_id` (Telegram channel ID)
- `wallet_address` (client's payout wallet)
- `payout_currency` (e.g., "shib")
- `payout_network` (e.g., "eth")
- `expire_time` (subscription expiration time)
- `expire_date` (subscription expiration date)
- `subscription_price` (USD amount paid)

### `processed_payments`
**Purpose:** Tracks NowPayments IPN data and Telegram invite status.

**Key Columns:**
- `payment_id` (NowPayments payment ID, PRIMARY KEY)
- `order_id` (subscription ID)
- `payment_status` (e.g., "finished")
- `outcome_amount` (ETH received from NowPayments)
- `outcome_currency` (e.g., "eth")
- `outcome_amount_usd` (USD equivalent)
- `telegram_invite_sent` (boolean)
- `telegram_invite_link` (one-time link)
- `telegram_invite_sent_at` (timestamp)

### `split_payout_request`
**Purpose:** Initial payment split request record.

**Key Columns:**
- `user_id`
- `closed_channel_id`
- `wallet_address`
- `from_amount` (adjusted USDT after fee)
- `from_currency` ("usdt")
- `to_amount` (placeholder, 0)
- `to_currency` (e.g., "shib")
- `created_at`

### `split_payout_que`
**Purpose:** Payment conversion queue record.

**Key Columns:**
- `user_id`
- `closed_channel_id`
- `from_amount` (adjusted USDT)
- `to_amount` (pure market token quantity, e.g., 596,726 SHIB)
- `estimated_to_amount` (post-fee token quantity, e.g., 586,726 SHIB)
- `created_at`

### `split_payout_hostpay`
**Purpose:** Payment execution record for GCHostPay.

**Key Columns:**
- `unique_id` (user_id for instant payments)
- `cn_api_id` (ChangeNow transaction ID)
- `from_currency` (e.g., "usdt")
- `from_network` (e.g., "eth")
- `from_amount` (USDT to send, e.g., 1.31)
- `payin_address` (ChangeNow deposit address)
- `to_address` (client wallet address)
- `to_currency` (e.g., "shib")
- `to_network` (e.g., "eth")
- `status` ('pending' → 'completed')
- `tx_hash` (Ethereum transaction hash)
- `completed_at`

### `failed_transactions`
**Purpose:** Stores payment attempts that failed after max retries.

**Key Columns:**
- `unique_id`
- `cn_api_id`
- `from_currency`
- `from_amount`
- `payin_address`
- `error_message`
- `error_category` (e.g., "INSUFFICIENT_BALANCE")
- `attempt_count` (always 3)
- `created_at`

---

## Environment Variables / Secret Manager

**Instant-Specific Configuration:**
- `TP_FLAT_FEE` - Platform fee percentage (default: "3" for 3%)
- `SUCCESS_URL_SIGNING_KEY` - HMAC signing key for token encryption
- `TPS_HOSTPAY_SIGNING_KEY` - Signing key for GCSplit1 ↔ GCHostPay tokens

**Service URLs (used for Cloud Tasks routing):**
- `GCWEBHOOK1_URL`
- `GCWEBHOOK2_URL`
- `GCSPLIT1_URL`
- `GCSPLIT2_URL`
- `GCSPLIT3_URL`
- `GCHOSTPAY1_URL`
- `GCHOSTPAY2_URL`
- `GCHOSTPAY3_URL`

**Queue Names (used for Cloud Tasks):**
- `GCWEBHOOK1_QUEUE`
- `GCWEBHOOK2_QUEUE`
- `GCSPLIT1_QUEUE`
- `GCSPLIT2_QUEUE`
- `GCSPLIT3_QUEUE`
- `GCHOSTPAY1_QUEUE`
- `GCHOSTPAY2_QUEUE`
- `GCHOSTPAY3_QUEUE`
- `GCHOSTPAY3_RETRY_QUEUE`

**ChangeNow Configuration:**
- `CHANGENOW_API_KEY` - ChangeNow API authentication key

**Ethereum Configuration:**
- `HOST_WALLET_ADDRESS` - Platform's ETH wallet address
- `HOST_WALLET_PRIVATE_KEY` - Platform's ETH wallet private key
- `ETHEREUM_RPC_URL` - Ethereum node RPC URL (Alchemy)
- `ETHEREUM_RPC_URL_API` - Alchemy API key

**Database Configuration:**
- `CLOUD_SQL_CONNECTION_NAME`
- `DATABASE_NAME_SECRET`
- `DATABASE_USER_SECRET`
- `DATABASE_PASSWORD_SECRET`

**NowPayments Configuration:**
- `NOWPAYMENTS_IPN_SECRET` - IPN signature verification key

**Telegram Configuration:**
- `TELEGRAM_BOT_TOKEN` - Telegram bot authentication token

**Alerting Configuration:**
- `SLACK_ALERT_WEBHOOK` - Slack webhook URL for failure alerts
- `ALERTING_ENABLED` - Enable/disable alerting (default: "true")

---

## Key Architectural Decisions

### 1. Single-Swap vs Two-Swap Architecture

**Instant Payouts:** Single swap (NowPayments outcome → Client currency)
**Threshold Payouts:** Two swaps (ETH→USDT, USDT→Client currency)

**Rationale for Instant:**
- Minimize latency (fewer ChangeNow API calls)
- Lower fees (one swap instead of two)
- Simpler architecture (6 services vs 11)
- Immediate conversion reduces volatility exposure

### 2. Parallel Telegram Invite Processing

**Decision:** GCWebhook2 runs in PARALLEL to payment flow, does not block GCSplit1.

**Rationale:**
- Telegram invite delivery is separate concern from payment processing
- If Telegram API is slow/down, payment should not be affected
- User receives invite slightly later, but payment completes faster
- Idempotency ensures no duplicate invites

### 3. USDT as Intermediate Currency (for swaps)

**Decision:** ChangeNow swaps use USDT as source currency (not ETH directly).

**Rationale:**
- NowPayments converts incoming crypto to outcome currency (typically ETH or USDT)
- ChangeNow has better liquidity for USDT→ClientCurrency pairs
- USDT is more stable than ETH for pending conversions
- Lower slippage on USDT pairs vs ETH pairs

### 4. Variable-Length Token Encoding

**Decision:** Replace fixed 16-byte encoding with variable-length string packing for unique_id fields.

**Rationale:**
- Fixed 16-byte encoding truncated long IDs (e.g., "user123456789" → "user12345678")
- Variable-length supports any ID format up to 255 bytes
- Prevents silent data corruption
- Backward compatible with short IDs

### 5. Token Expiration Windows

**Decision:** Different expiration windows based on workflow type.

**Instant Payout Tokens:**
- GCWebhook1 → GCWebhook2: 5 minutes (synchronous)
- GCSplit1 → GCSplit2/3: 5 minutes (synchronous)
- GCHostPay1 → GCHostPay2: 5 minutes (synchronous)
- GCHostPay1 → GCHostPay3: 2 hours (accounts for ChangeNow delays)

**Rationale:**
- Synchronous calls complete quickly (5 minutes sufficient)
- ChangeNow conversions may take 10-60 minutes (2 hours allows buffer)
- Security maintained via HMAC signature + timestamp validation

### 6. 3-Attempt Retry Limit (GCHostPay3)

**Decision:** Payment execution limited to 3 attempts (vs infinite retry).

**Rationale:**
- Infinite retry dangerous for non-retryable errors (e.g., insufficient balance)
- 3 attempts with 60s delay handles transient failures (network issues, gas price spikes)
- Failed transactions stored in database for manual investigation
- Alerting service notifies team immediately

### 7. Cloud Tasks for Orchestration

**Decision:** Use Cloud Tasks for all inter-service communication (not direct HTTP calls).

**Rationale:**
- Automatic retry on failure (60s backoff, 24h max duration)
- Decouples services (no tight dependencies)
- Built-in rate limiting and queue management
- Service failures don't cause cascading failures
- Idempotency ensured via task name deduplication

---

## End-to-End Flow Summary (Instant Payout)

**Example: User pays $1.35 subscription in BTC**

```
User sends BTC payment ($1.35) to NowPayments
    ↓
NowPayments confirms payment, converts to ETH (0.000573 ETH)
    ↓
NowPayments sends success_url to GCWebhook1 with encrypted token
    ↓
GCWebhook1 validates token, writes to database
    ↓
GCWebhook1 queries payout_strategy: "instant"
    ↓
GCWebhook1 enqueues to GCWebhook2 (parallel) and GCSplit1 (main flow)
    ↓
GCWebhook2 sends Telegram invite to user (completes)
    ↓
GCSplit1 calculates adjusted amount: $1.35 - 3% fee = $1.31 USDT
    ↓
GCSplit1 enqueues to GCSplit2 for estimate
    ↓
GCSplit2 calls ChangeNow: "1.31 USDT → SHIB?" → Estimate: 586,726 SHIB
    ↓
GCSplit2 returns estimate to GCSplit1
    ↓
GCSplit1 calculates pure market value: 596,726 SHIB (accounting)
    ↓
GCSplit1 writes to database: split_payout_request, split_payout_que
    ↓
GCSplit1 enqueues to GCSplit3 for swap creation
    ↓
GCSplit3 creates ChangeNow transaction: USDT→SHIB
    ↓
ChangeNow response:
    - Transaction ID: 613c822e844358
    - Deposit address: 0xChangeNowDepositAddress...
    - Expected input: 1.31 USDT
    - Expected output: 586,726 SHIB
    ↓
GCSplit3 returns transaction details to GCSplit1
    ↓
GCSplit1 writes to database: split_payout_hostpay
    ↓
GCSplit1 enqueues to GCHostPay1 for payment execution
    ↓
GCHostPay1 validates payment request, writes to database
    ↓
GCHostPay1 enqueues to GCHostPay2 for status check
    ↓
GCHostPay2 checks ChangeNow status: "waiting"
    ↓
GCHostPay2 returns status to GCHostPay1
    ↓
GCHostPay1 verifies status, proceeds to payment execution
    ↓
GCHostPay1 enqueues to GCHostPay3 for payment
    ↓
GCHostPay3 validates: from_currency="usdt", amount=1.31
    ↓
GCHostPay3 checks wallet balance: Platform has 50.00 USDT ✅
    ↓
GCHostPay3 executes ERC-20 transfer:
    - Token contract: 0xdac17f958d2ee523a2206206994597c13d831ec7 (USDT)
    - To address: 0xChangeNowDepositAddress...
    - Amount: 1.31 USDT (1,310,000 units with 6 decimals)
    - Gas: 100,000 units
    ↓
Ethereum transaction confirmed:
    - Tx hash: 0xabc123...
    - 1.31 USDT sent to ChangeNow
    ↓
GCHostPay3 returns tx_hash to GCHostPay1
    ↓
GCHostPay1 queries ChangeNow for final status
    ↓
GCHostPay1 updates database: split_payout_hostpay (status='completed')
    ↓
ChangeNow receives 1.31 USDT, starts conversion
    ↓
ChangeNow converts 1.31 USDT → 586,726 SHIB
    ↓
ChangeNow sends 586,726 SHIB to client wallet (0xabc123...)
    ↓
Client receives 586,726 SHIB in their wallet
    ↓
✅ PAYMENT COMPLETE
```

**Total Services Involved in Instant Payout:** 8 services
- GCWebhook1, GCWebhook2, GCSplit1, GCSplit2, GCSplit3, GCHostPay1, GCHostPay2, GCHostPay3

**Optional Services:** 1 service
- np-webhook-10-26 (IPN handler, alternative entry point)

---

## Comparison: Instant vs Threshold Payouts

| Aspect | Instant Payout | Threshold Payout |
|--------|----------------|------------------|
| **Trigger** | Immediate on payment | Accumulate until threshold |
| **Services** | 8 (GCWebhook1 → GCSplit → GCHostPay) | 11 (+ GCAccumulator, GCMicroBatchProcessor, GCBatchProcessor) |
| **Conversion** | Single swap (USDT→Client currency) | Two swaps (ETH→USDT, USDT→Client) |
| **Database** | `split_payout_*` tables | `payout_accumulation` + `batch_*` tables |
| **Orchestration** | Cloud Tasks (immediate) | Cloud Scheduler + Cloud Tasks |
| **Latency** | 5-60 minutes | Hours to days (depends on threshold) |
| **Gas Efficiency** | Lower (one transaction per payment) | Higher (batch multiple payments) |
| **Volatility Risk** | Lower (immediate conversion) | Mitigated (USDT intermediate) |
| **ChangeNow Fees** | One swap fee (~1.5%) | Two swap fees (~3% total) |
| **Use Case** | High-value subscriptions ($10+) | Low-value subscriptions ($1-5) |
| **Default** | ✅ Yes (if not specified) | No (must configure threshold) |

---

## Monitoring & Observability

### Key Metrics (Instant Payouts)

**Payment Processing:**
- Total payments received (per day/hour)
- Average payment amount (USD)
- Payment success rate (%)
- Average processing time (minutes)

**ChangeNow Integration:**
- ChangeNow API success rate (%)
- Average ChangeNow conversion time (minutes)
- ChangeNow fee percentage (actual vs expected)

**Blockchain Transactions:**
- Ethereum transaction success rate (%)
- Average gas cost (USD)
- Failed transactions count
- Transaction retry count

**Telegram Invites:**
- Telegram invite success rate (%)
- Average invite delivery time (seconds)
- Duplicate invite prevention hits

### Alerts

**Critical:**
- GCHostPay3 payment failed after max retries
- Insufficient wallet balance (USDT or ETH)
- ChangeNow API down for >5 minutes
- Database connection failure

**Warning:**
- Payment processing time >10 minutes
- ChangeNow conversion time >60 minutes
- Gas price spike (>100 Gwei)
- Token expiration rate >1%

**Info:**
- New instant payment received
- ChangeNow transaction completed
- Ethereum transaction confirmed
- Telegram invite sent

---

**Document Version:** 1.0
**Last Updated:** 2025-11-07
**Author:** Claude Code Analysis
