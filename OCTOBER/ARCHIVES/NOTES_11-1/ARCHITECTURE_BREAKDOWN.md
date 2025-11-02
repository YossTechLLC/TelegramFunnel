# TELEPAY PAYMENT SYSTEM ARCHITECTURE BREAKDOWN (10-26)
**Created**: 2025-11-01
**Status**: ✅ Production Operational

---

## PAYMENT FLOW OVERVIEW

The system implements **TWO DISTINCT PAYOUT STRATEGIES**:

### **INSTANT PAYOUT**
- User pays → Immediate conversion → Instant payout to channel owner
- Flow: GCWebhook1 → GCSplit1-2-3 → GCHostPay1-2-3

### **THRESHOLD PAYOUT**
- User pays → Accumulated → Batched when threshold reached → Proportional distribution
- Flow: GCWebhook1 → GCAccumulator → (wait) → GCMicroBatchProcessor → GCHostPay1-2-3
- Scheduler: Every 15 minutes checks if accumulated USD >= $20

---

## SERVICE BREAKDOWN

### **GCWebhook1-10-26** (Payment Entry Point)
**INPUT**:
- NOWPayments success_url webhook with encrypted token
- Contains: user_id, channel_id, payment_amount_usd, subscription details

**FUNCTION**:
- Decrypts payment token
- Writes subscriber to `private_channel_users_database`
- **DECISION POINT**: Queries `payout_strategy` from `private_channels` table
  - If `payout_strategy = 'instant'` → Routes to GCSplit1
  - If `payout_strategy = 'threshold'` → Routes to GCAccumulator
- Always queues Telegram invite task

**OUTPUT**:
- Cloud Task → GCWebhook2 (Telegram invite - always)
- Cloud Task → GCSplit1 (instant) OR GCAccumulator (threshold)

---

### **GCWebhook2-10-26** (Telegram Invite Handler)
**INPUT**:
- Cloud Task from GCWebhook1 with encrypted token
- Contains: user_id, channel_id

**FUNCTION**:
- Generates Telegram invite link for private channel
- Sends invite via Telegram Bot API

**OUTPUT**:
- Telegram invite link sent to user
- No further Cloud Tasks

---

### **GCSplit1-10-26** (Payment Splitting Orchestrator)
**INPUT**:
1. POST / - From GCWebhook1 (instant payouts)
2. POST /batch-payout - From GCBatchProcessor (threshold → client payouts)
3. POST /usdt-eth-estimate - Callback from GCSplit2
4. POST /eth-client-swap - Callback from GCSplit3

**FUNCTION**:
- **Main Orchestrator** for all currency conversions
- Calculates adjusted amount (removes 3% TP fee)
- Coordinates 3-step conversion: **Payment → USDT → ETH → ClientCurrency**
- Stores conversion progress in `split_payout_request` and `split_payout_que`
- Calculates **pure market value** (not post-fee amount)

**OUTPUT**:
- Cloud Task → GCSplit2 (USDT→ETH estimate request)
- Cloud Task → GCSplit3 (ETH→ClientCurrency swap request)
- Cloud Task → GCHostPay1 (payment execution request)

---

### **GCSplit2-10-26** (USDT→ETH Estimator)
**INPUT**:
- Cloud Task from GCSplit1 with encrypted token
- Contains: USDT amount for conversion

**FUNCTION**:
- Calls ChangeNow estimate API: USDT → ETH
- Returns conversion rate with fees (depositFee, withdrawalFee)
- Enables pure market value calculation

**OUTPUT**:
- Callback → GCSplit1 /usdt-eth-estimate endpoint
- Returns: toAmount (ETH post-fee), depositFee, withdrawalFee

---

### **GCSplit3-10-26** (ETH→ClientCurrency Swapper)
**INPUT**:
- Cloud Task from GCSplit1 with encrypted token
- Contains: ETH amount, client currency/network, wallet address

**FUNCTION**:
- Creates ChangeNow fixed-rate transaction: ETH → ClientCurrency
- Returns transaction ID and payment address

**OUTPUT**:
- Callback → GCSplit1 /eth-client-swap endpoint
- Returns: cn_api_id, payin_address for payment execution

---

### **GCAccumulator-10-26** (Payment Accumulation Service)
**INPUT**:
- Cloud Task from GCWebhook1 (threshold payouts only)
- Contains: payment_amount_usd, user_id, channel_id, client details

**FUNCTION**:
- Calculates adjusted amount (removes 3% TP fee)
- Stores payment record in `payout_accumulation` table
- Sets `conversion_status = 'pending'`
- **DOES NOT** trigger immediate conversion
- **CRITICAL**: Field `accumulated_eth` stores USD value (not ETH - legacy naming!)

**OUTPUT**:
- Database insert only
- Returns HTTP 200 (NO Cloud Tasks queued)
- Awaits GCMicroBatchProcessor to process batch

---

### **GCMicroBatchProcessor-10-26** (Micro-Batch Conversion Service)
**Trigger**: Cloud Scheduler every 15 minutes

**ENDPOINTS**:
1. **POST /check-threshold** (cron-triggered)
2. **POST /swap-executed** (callback from GCHostPay1)

#### Endpoint 1: /check-threshold
**INPUT**:
- Cron trigger (no payload)

**FUNCTION**:
1. Fetches threshold from Secret Manager (`MICRO_BATCH_THRESHOLD_USD` = $20.00)
2. Queries total pending: `SUM(accumulated_eth) WHERE conversion_status='pending'`
3. **IF total_pending >= threshold**:
   - Calls ChangeNow estimate API: USD → ETH conversion rate
   - Creates ChangeNow swap: ETH → USDT (with calculated ETH amount)
   - Creates `batch_conversions` record
   - Updates ALL pending records to `conversion_status = 'swapping'`
   - Enqueues to GCHostPay1 with `context='batch'`
4. **ELSE**: No action, waits for more payments

**OUTPUT**:
- Database: `batch_conversions` insert, `payout_accumulation` updates
- Cloud Task → GCHostPay1 (if threshold met)

#### Endpoint 2: /swap-executed
**INPUT**:
- Callback from GCHostPay1 with encrypted token
- Contains: batch_conversion_id, cn_api_id, tx_hash, actual_usdt_received

**FUNCTION**:
1. Fetches all `payout_accumulation` records for this batch
2. **Proportional USDT Distribution**:
   ```
   usdt_share_i = (accumulated_eth_i / total_pending) × actual_usdt_received
   ```
3. Updates each record:
   - `accumulated_amount_usdt = usdt_share`
   - `conversion_status = 'completed'`
   - `conversion_tx_hash = tx_hash`
4. Finalizes `batch_conversions` record

**OUTPUT**:
- Database updates: Proportional USDT distribution to all batch participants
- Returns HTTP 200 (no further Cloud Tasks)

---

### **GCBatchProcessor-10-26** (Batch Payout Processor)
**Trigger**: Cloud Scheduler every 5 minutes

**INPUT**:
- Cron trigger (no payload)

**FUNCTION**:
1. Queries `payout_accumulation` for clients over threshold:
   ```sql
   SELECT client_id, SUM(accumulated_amount_usdt)
   WHERE conversion_status='completed' AND paid_out=FALSE
   GROUP BY client_id
   HAVING SUM >= payout_threshold
   ```
2. For each client:
   - Generates batch_id (UUID)
   - Creates `payout_batches` record
   - Encrypts batch token with client wallet/currency/network
   - Enqueues to GCSplit1 /batch-payout
   - Marks accumulations as `paid_out = TRUE`

**OUTPUT**:
- Database: `payout_batches` insert, `payout_accumulation` updates
- Cloud Task → GCSplit1 /batch-payout (for each client)

**NOTE**: This is DIFFERENT from GCMicroBatchProcessor:
- **GCBatchProcessor**: Aggregates **USDT** (already converted) for client payouts
- **GCMicroBatchProcessor**: Batches **USD pending conversion** to save on ETH→USDT swap fees

---

### **GCHostPay1-10-26** (Validator & Orchestrator)
**INPUTS**:
1. POST / - From GCSplit1 (instant), GCAccumulator (deprecated), GCMicroBatchProcessor (batch)
2. POST /status-verified - Callback from GCHostPay2
3. POST /payment-completed - Callback from GCHostPay3

**FUNCTION**:
- **Multi-context token decryption** (instant, threshold, batch)
- Orchestrates payment workflow: validation → execution → completion
- **Context Detection** via unique_id prefix:
  - `batch_*` → Micro-batch conversion
  - `acc_*` → Threshold payout (not currently used)
  - Regular → Instant payout
- **Callback Routing** (in /payment-completed):
  - Queries ChangeNow for actual USDT received
  - Routes batch callbacks to GCMicroBatchProcessor /swap-executed
  - Routes threshold callbacks to GCAccumulator (TODO - not implemented)

**OUTPUT**:
- Cloud Task → GCHostPay2 (status check)
- Cloud Task → GCHostPay3 (payment execution)
- Callback → GCMicroBatchProcessor /swap-executed (for batch conversions)

---

### **GCHostPay2-10-26** (ChangeNow Status Checker)
**INPUT**:
- Cloud Task from GCHostPay1 with encrypted token
- Contains: cn_api_id for ChangeNow transaction

**FUNCTION**:
- Queries ChangeNow transaction status via API
- Validates status == "waiting" before allowing payment execution
- Prevents payment to invalid/expired transactions

**OUTPUT**:
- Callback → GCHostPay1 /status-verified endpoint
- Returns: transaction status details

---

### **GCHostPay3-10-26** (ETH Payment Executor)
**INPUT**:
- Cloud Task from GCHostPay1 (via GCHostPay2 status verification)
- Contains: payin_address, ETH amount

**FUNCTION**:
- Executes ETH payment to ChangeNow payin_address
- Uses Web3.py for Ethereum blockchain interaction
- Waits for transaction confirmation

**OUTPUT**:
- Callback → GCHostPay1 /payment-completed endpoint
- Returns: tx_hash, gas_used, block_number

---

### **GCRegister10-26** (Channel Registration - Web Form)
**INPUT**:
- HTTP GET/POST requests from channel owners
- Form data: channel_id, wallet_address, payout_strategy, payout_threshold, payout_currency, payout_network

**FUNCTION**:
- Validates Telegram channel ownership
- Stores channel configuration in `private_channels` table
- Sets payout strategy (instant vs threshold)

**OUTPUT**:
- Database insert into `private_channels`
- Success/error page rendered

---

### **GCRegisterAPI-10-26** (Channel Management REST API)
**ENDPOINTS**:
- POST /auth/signup - Create user account
- POST /auth/login - Authenticate user (JWT tokens)
- POST /auth/refresh - Refresh access token
- GET /channels - List user's channels
- POST /channels - Register new channel
- PUT /channels/{id} - Update channel config
- DELETE /channels/{id} - Delete channel
- GET /mappings - Get channel-wallet mappings

**INPUT**:
- REST API requests with JWT authentication
- JSON payloads for channel/user management

**FUNCTION**:
- User authentication and authorization
- CRUD operations for channels
- Secure API access for GCRegisterWeb frontend

**OUTPUT**:
- JSON responses with data/errors
- JWT tokens for authentication

---

### **GCRegisterWeb-10-26** (React Frontend)
**INPUT**:
- User interactions (clicks, form submissions)
- API responses from GCRegisterAPI

**FUNCTION**:
- Modern React/TypeScript SPA
- Pages: Landing, Login, Signup, Dashboard, RegisterChannel, EditChannel
- Secure authentication flow (JWT tokens)
- Channel CRUD interface

**OUTPUT**:
- REST API calls to GCRegisterAPI
- Dynamic UI updates based on user state

---

### **TelePay10-26** (Telegram Bot)
**Not analyzed in this document - separate architecture**

---

## CRITICAL DATA FLOWS

### **INSTANT PAYOUT FLOW**
```
User Payment (NOWPayments)
    ↓
GCWebhook1 (detects instant strategy)
    ↓ Cloud Task
GCSplit1 (orchestrator)
    ↓ Cloud Task
GCSplit2 (USDT→ETH estimate)
    ↓ callback
GCSplit1 (stores pure market value)
    ↓ Cloud Task
GCSplit3 (ETH→ClientCurrency swap)
    ↓ callback
GCSplit1 (queues payment)
    ↓ Cloud Task
GCHostPay1 (validator)
    ↓ Cloud Task
GCHostPay2 (status check)
    ↓ callback
GCHostPay1 (routes to payment)
    ↓ Cloud Task
GCHostPay3 (ETH payment execution)
    ↓ callback
GCHostPay1 (completes workflow)
```

### **THRESHOLD PAYOUT FLOW**
```
User Payment (NOWPayments)
    ↓
GCWebhook1 (detects threshold strategy)
    ↓ Cloud Task
GCAccumulator (stores pending)
    ↓ (no action - awaits batch)
    ⏰ Cloud Scheduler (every 15 min)
    ↓
GCMicroBatchProcessor /check-threshold
    ↓ (if total_pending >= $20)
    ↓ (Creates ChangeNow ETH→USDT swap)
    ↓ Cloud Task
GCHostPay1 (batch context)
    ↓ Cloud Task
GCHostPay2 (status check)
    ↓ callback
GCHostPay1 (routes to payment)
    ↓ Cloud Task
GCHostPay3 (ETH payment execution)
    ↓ callback
GCHostPay1 (queries ChangeNow for actual USDT)
    ↓ callback
GCMicroBatchProcessor /swap-executed
    ↓ (Proportional USDT distribution)
    ↓ Database updates
(Payments now have accumulated_amount_usdt set)
    ⏰ Cloud Scheduler (every 5 min)
    ↓
GCBatchProcessor /process
    ↓ (if client total_usdt >= threshold)
    ↓ Cloud Task
GCSplit1 /batch-payout
    ↓ (Same flow as instant payout)
    ↓ GCSplit2 → GCSplit3 → GCHostPay1-2-3
```

---

## EXTERNAL DEPENDENCIES

### **ChangeNow API**
- **POST /v2/exchange/estimated-amount** - Conversion rate estimates
- **POST /v2/exchange** - Create fixed-rate transactions
- **GET /v2/exchange/by-id** - Transaction status queries

### **Ethereum Blockchain**
- **Web3.py** - ETH payment execution via GCHostPay3

### **NOWPayments**
- **success_url callback** - Payment notifications to GCWebhook1

### **Telegram Bot API**
- **Invite link generation** - Via GCWebhook2

---

## DATABASE TABLES

### **private_channel_users_database**
- Stores subscriber records (user_id, channel_id, subscription details)

### **private_channels**
- Stores channel config (payout_strategy, payout_threshold, wallet_address, etc.)

### **payout_accumulation**
- Stores pending/completed threshold payments
- **CRITICAL FIELDS**:
  - `accumulated_eth` - Stores USD value (legacy naming!)
  - `accumulated_amount_usdt` - Stores USDT after conversion
  - `conversion_status` - 'pending' | 'swapping' | 'completed'
  - `batch_conversion_id` - Links to batch_conversions
  - `paid_out` - TRUE after batch payout

### **batch_conversions**
- Stores micro-batch conversion records
- Tracks total_eth_usd, actual_usdt_received, conversion_tx_hash

### **payout_batches**
- Stores client payout batch records
- Tracks total_amount_usdt per client, batch_status

### **split_payout_request**
- Stores instant payout requests with pure market value

### **split_payout_que**
- Stores instant payout execution details (cn_api_id, payin_address)

---

## CLOUD SCHEDULER JOBS

### **micro-batch-conversion-job**
- **Schedule**: Every 15 minutes (`*/15 * * * *`)
- **Target**: GCMicroBatchProcessor /check-threshold
- **Purpose**: Check if pending USD >= $20, create batch ETH→USDT swaps

### **batch-payout-processor-job**
- **Schedule**: Every 5 minutes (`*/5 * * * *`)
- **Target**: GCBatchProcessor /process
- **Purpose**: Check if clients have USDT >= threshold, trigger client payouts

---

## KEY ARCHITECTURAL DECISIONS

1. **Asynchronous Queue-Based Communication** - All inter-service via Cloud Tasks
2. **Token-Based Security** - HMAC-SHA256 signed tokens for service-to-service auth
3. **Callback Pattern** - Services don't wait for responses, use callbacks
4. **Multi-Context Service Design** - GCHostPay1 handles instant/threshold/batch contexts
5. **Cron-Triggered Batch Processing** - Scheduled jobs for cost-efficient batching
6. **Decimal Precision** - All financial calculations use Python Decimal (precision=28)
7. **Proportional Distribution** - Fair USDT allocation based on USD contribution ratio

---

## CURRENT STATUS

✅ **PRODUCTION OPERATIONAL**
- All services deployed and functional
- Instant payout flow working
- Threshold payout (micro-batch) working
- Batch payout (client aggregation) working
- Cloud Scheduler jobs running
- ChangeNow integration working
- Ethereum payment execution working

⚠️ **KNOWN ISSUES**
- `accumulated_eth` field stores USD (not ETH) - legacy naming
- Threshold callback routing in GCHostPay1 has TODO marker (may not be needed)

🟢 **SCALABILITY**
- Threshold adjustable via Secret Manager ($20 → $100 → $500 → $1000+)
- No code changes or redeployment needed for threshold updates

---

**END OF DOCUMENT**
