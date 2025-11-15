# ENDPOINT_WEBHOOK_ANALYSIS.md

**Comprehensive Analysis of All Webhook Endpoints in the /10-26 Deployment**

**Date:** 2025-11-08
**Architecture:** Distributed Microservices on Google Cloud Run
**Project:** TelePay Payment Processing Platform

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Webhook Services & Endpoints](#webhook-services--endpoints)
4. [Flow Chart: Payment Processing Flow](#flow-chart-payment-processing-flow)
5. [Flow Chart: Instant vs Threshold Decision Tree](#flow-chart-instant-vs-threshold-decision-tree)
6. [Flow Chart: Batch Processing Flow](#flow-chart-batch-processing-flow)
7. [Endpoint Interaction Matrix](#endpoint-interaction-matrix)
8. [Cloud Tasks Queue Mapping](#cloud-tasks-queue-mapping)
9. [Database Operations by Service](#database-operations-by-service)
10. [External API Integrations](#external-api-integrations)

---

## Executive Summary

The TelePay platform consists of **13 microservices** deployed on Google Cloud Run, orchestrating **crypto payment processing, conversion, and distribution**. The system handles:

- **NowPayments IPN webhook processing** (np-webhook-10-26)
- **Telegram user payment requests** (GCWebhook1-10-26, GCWebhook2-10-26)
- **Instant vs Threshold routing** (GCSplit1-10-26)
- **ChangeNow crypto exchanges** (GCSplit2-10-26, GCSplit3-10-26)
- **Payment accumulation and batching** (GCAccumulator-10-26, GCBatchProcessor-10-26, GCMicroBatchProcessor-10-26)
- **Final ETH/ERC-20 payment execution** (GCHostPay1-10-26, GCHostPay2-10-26, GCHostPay3-10-26)
- **Channel registration and management** (GCRegisterAPI-10-26)

The system processes **two payment flows**:
1. **Instant Payouts** (< $100 USD) → Immediate conversion and payment
2. **Threshold Payouts** (≥ $100 USD) → Batch accumulation and scheduled processing

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TelePay Payment Platform                            │
│                         Google Cloud Architecture                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  External APIs   │     │  Cloud Services  │     │   User Access    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
│                        │                        │
│ • NowPayments          │ • Cloud Run            │ • Telegram Bot
│ • ChangeNow            │ • Cloud Tasks          │ • Web Dashboard
│ • CoinGecko            │ • Cloud SQL            │   (paygateprime.com)
│ • Alchemy RPC          │ • Secret Manager       │
│                        │ • Cloud Scheduler      │
└────────────────────────┴────────────────────────┴──────────────────┘
                                  ↓
        ┌─────────────────────────────────────────────────┐
        │         13 Microservices (Cloud Run)            │
        └─────────────────────────────────────────────────┘
                                  ↓
┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│  Entry      │  Routing    │ Conversion  │  Batching   │  Execution  │
│  Points     │  Layer      │  Layer      │  Layer      │  Layer      │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ np-webhook  │ GCSplit1    │ GCSplit2    │ GCBatch     │ GCHostPay1  │
│ GCWebhook1  │             │ GCSplit3    │ GCMicroBatch│ GCHostPay2  │
│ GCRegister  │             │ GCAccum     │             │ GCHostPay3  │
│ GCWebhook2  │             │             │             │             │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

---

## Webhook Services & Endpoints

### 1. **np-webhook-10-26** (NowPayments IPN Handler)

**Service Purpose:** Receives and validates IPN callbacks from NowPayments after users complete crypto payments.

**File:** `np-webhook-10-26/app.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Handle NowPayments IPN callbacks | NowPayments API |
| GET | `/api/payment-status` | Poll payment confirmation status | Frontend (payment-processing.html) |
| GET | `/payment-processing` | Serve payment processing page | Browser (user redirect) |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- Verify HMAC-SHA512 signature from NowPayments
- Parse order_id (format: `PGP-{user_id}|{open_channel_id}`)
- UPSERT payment data into `private_channel_users_database`
- Calculate outcome amount in USD using CoinGecko API
- Enqueue validated payment to **GCWebhook1** `/process-validated-payment`
- Implement idempotency check using `processed_payments` table

**Database Tables:**
- `private_channel_users_database` (UPSERT)
- `main_clients_database` (SELECT)
- `processed_payments` (INSERT for idempotency)

**External APIs:**
- CoinGecko (price fetching)

**Cloud Tasks:**
- Enqueues to: `GCWEBHOOK1_QUEUE` → `GCWebhook1/process-validated-payment`

---

### 2. **GCWebhook1-10-26** (Primary Payment Orchestrator)

**Service Purpose:** Central orchestrator for all payment processing flows.

**File:** `GCWebhook1-10-26/tph1-10-26.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Initial payment request from Telegram bot | Telegram Bot |
| POST | `/process-validated-payment` | Process NowPayments-validated payments | np-webhook (via Cloud Tasks) |
| POST | `/payment-completed` | Receive payment completion notification | GCHostPay3 (instant flow) |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- **POST /** (Telegram flow):
  - Validate JWT token from Telegram bot
  - Extract user_id, channel_id, subscription details
  - Generate unique_id and order_id
  - Create NowPayments invoice
  - Store initial record in `private_channel_users_database`
  - Return payment URL to bot

- **POST /process-validated-payment** (NowPayments flow):
  - Decrypt token from np-webhook
  - Verify payment amount matches subscription price
  - Route to **GCSplit1** for instant/threshold decision
  - Mark payment as `gcwebhook1_processed` in `processed_payments` table

- **POST /payment-completed** (Instant completion):
  - Decrypt token from GCHostPay3
  - Update `main_clients_database` with conversion data
  - Send Telegram invite link to user
  - Update `processed_payments` table

**Database Tables:**
- `private_channel_users_database` (INSERT, SELECT)
- `main_clients_database` (UPDATE)
- `processed_payments` (UPDATE)

**External APIs:**
- NowPayments (create invoice)
- Telegram Bot API (send invite link)

**Cloud Tasks:**
- Enqueues to: `GCSPLIT1_QUEUE` → `GCSplit1/`

---

### 3. **GCWebhook2-10-26** (Instant Payment Handler)

**Service Purpose:** Handles instant payment flow (< $100 USD threshold).

**File:** `GCWebhook2-10-26/tph2-10-26.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Process instant payment request | GCSplit1 (via Cloud Tasks) |
| POST | `/status-verified` | Receive ChangeNow status verification | GCHostPay2 |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- **POST /**:
  - Decrypt token from GCSplit1
  - Route to **GCSplit2** to create ChangeNow exchange
  - Wait for status verification

- **POST /status-verified**:
  - Decrypt status from GCHostPay2
  - Check if status is `finished`
  - Route to **GCHostPay1** for final payment execution

**Database Tables:**
- None (stateless orchestrator)

**Cloud Tasks:**
- Enqueues to:
  - `GCSPLIT2_QUEUE` → `GCSplit2/`
  - `GCHOSTPAY1_QUEUE` → `GCHostPay1/`

---

### 4. **GCSplit1-10-26** (Instant vs Threshold Router)

**Service Purpose:** Decides whether payment goes through instant or threshold flow based on USD amount.

**File:** `GCSplit1-10-26/tps1-10-26.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Route payment to instant or threshold flow | GCWebhook1 (via Cloud Tasks) |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- Decrypt token from GCWebhook1
- Calculate `outcome_amount_usd` (payment amount in USD)
- **If < $100 USD** → Route to **GCWebhook2** (instant flow)
- **If ≥ $100 USD** → Route to **GCAccumulator** (threshold flow)

**Database Tables:**
- `batch_conversions` (INSERT for threshold payments)

**Cloud Tasks:**
- Enqueues to:
  - **Instant**: `GCWEBHOOK2_QUEUE` → `GCWebhook2/`
  - **Threshold**: `GCACCUMULATOR_QUEUE` → `GCAccumulator/`

**Decision Logic:**
```python
if outcome_amount_usd < 100.0:
    # INSTANT FLOW
    enqueue_to_gcwebhook2()
else:
    # THRESHOLD FLOW
    enqueue_to_gcaccumulator()
```

---

### 5. **GCSplit2-10-26** (ChangeNow Exchange Creator - Instant)

**Service Purpose:** Creates ChangeNow exchanges for instant payments.

**File:** `GCSplit2-10-26/tps2-10-26.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Create ChangeNow exchange | GCWebhook2 (via Cloud Tasks) |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- Decrypt token from GCWebhook2
- Call ChangeNow API to create exchange
- Extract `cn_api_id` (ChangeNow exchange ID)
- Route to **GCHostPay1** with exchange details

**External APIs:**
- ChangeNow (create exchange)

**Cloud Tasks:**
- Enqueues to: `GCHOSTPAY1_QUEUE` → `GCHostPay1/`

---

### 6. **GCSplit3-10-26** (ChangeNow Exchange Creator - Threshold)

**Service Purpose:** Creates ChangeNow exchanges for threshold/batch payments.

**File:** `GCSplit3-10-26/tps3-10-26.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Create ChangeNow exchange for batch | GCAccumulator (via Cloud Tasks) |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- Decrypt token from GCAccumulator
- Call ChangeNow API to create exchange
- Extract `cn_api_id`
- Route to **GCHostPay1** with `context='threshold'`

**External APIs:**
- ChangeNow (create exchange)

**Cloud Tasks:**
- Enqueues to: `GCHOSTPAY1_QUEUE` → `GCHostPay1/`

---

### 7. **GCAccumulator-10-26** (Threshold Payment Accumulator)

**Service Purpose:** Accumulates threshold payments (≥ $100) and processes them in batches.

**File:** `GCAccumulator-10-26/acc10-26.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Accept threshold payment for accumulation | GCSplit1 (via Cloud Tasks) |
| POST | `/swap-executed` | Receive swap completion notification | GCHostPay3 (threshold flow) |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- **POST /**:
  - Decrypt token from GCSplit1
  - Store payment in `batch_conversions` table with `status='pending'`
  - Batch processor will pick it up later

- **POST /swap-executed**:
  - Decrypt token from GCHostPay3
  - Update `main_clients_database` with conversion data
  - Send Telegram invite link to user
  - Update `batch_conversions` status to `completed`

**Database Tables:**
- `batch_conversions` (INSERT, UPDATE)
- `main_clients_database` (UPDATE)

**External APIs:**
- Telegram Bot API (send invite link)

**Cloud Tasks:**
- None (terminal endpoint for accumulation)

---

### 8. **GCBatchProcessor-10-26** (Scheduled Batch Processor)

**Service Purpose:** Scheduled job (Cloud Scheduler) that processes accumulated threshold payments.

**File:** `GCBatchProcessor-10-26/batch10-26.py`

**Trigger:** Cloud Scheduler (e.g., every 1 hour)

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Process pending batch conversions | Cloud Scheduler |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- Query `batch_conversions` for `status='pending'`
- Group by `client_wallet_address` and `client_payout_currency`
- Calculate total USD amount per group
- If total ≥ threshold → Route to **GCSplit3** for processing
- Update status to `processing`

**Database Tables:**
- `batch_conversions` (SELECT, UPDATE)

**Cloud Tasks:**
- Enqueues to: `GCSPLIT3_QUEUE` → `GCSplit3/`

---

### 9. **GCMicroBatchProcessor-10-26** (Micro Batch Processor)

**Service Purpose:** Similar to GCBatchProcessor but processes smaller batches more frequently.

**File:** `GCMicroBatchProcessor-10-26/microbatch10-26.py`

**Trigger:** Cloud Scheduler (e.g., every 15 minutes)

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Process micro-batches | Cloud Scheduler |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- Same as GCBatchProcessor but with lower threshold
- More frequent execution
- Handles time-sensitive threshold payments

**Database Tables:**
- `batch_conversions` (SELECT, UPDATE)

**Cloud Tasks:**
- Enqueues to: `GCSPLIT3_QUEUE` → `GCSplit3/`

---

### 10. **GCHostPay1-10-26** (Payment Orchestrator)

**Service Purpose:** Orchestrates ChangeNow status checking and ETH payment execution.

**File:** `GCHostPay1-10-26/tphp1-10-26.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Receive ChangeNow exchange details | GCSplit2, GCSplit3 (via Cloud Tasks) |
| POST | `/status-verified` | Receive ChangeNow status from GCHostPay2 | GCHostPay2 |
| POST | `/payment-completed` | Receive payment completion from GCHostPay3 | GCHostPay3 |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- **POST /**:
  - Decrypt token from GCSplit2/GCSplit3
  - Route to **GCHostPay2** to check ChangeNow status

- **POST /status-verified**:
  - Decrypt status from GCHostPay2
  - If status is `finished` → Route to **GCHostPay3** for payment execution
  - If status is `waiting` → Retry status check

- **POST /payment-completed**:
  - Decrypt payment result from GCHostPay3
  - Route back to **GCWebhook2** (instant) or **GCAccumulator** (threshold)

**Database Tables:**
- None (stateless orchestrator)

**Cloud Tasks:**
- Enqueues to:
  - `GCHOSTPAY2_QUEUE` → `GCHostPay2/`
  - `GCHOSTPAY3_QUEUE` → `GCHostPay3/`
  - `GCWEBHOOK2_RESPONSE_QUEUE` → `GCWebhook2/status-verified`
  - `GCACCUMULATOR_RESPONSE_QUEUE` → `GCAccumulator/swap-executed`

---

### 11. **GCHostPay2-10-26** (ChangeNow Status Checker)

**Service Purpose:** Checks ChangeNow transaction status with infinite retry logic.

**File:** `GCHostPay2-10-26/tphp2-10-26.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Check ChangeNow transaction status | GCHostPay1 (via Cloud Tasks) |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- Decrypt token from GCHostPay1
- Call ChangeNow API to check transaction status
- **Infinite retry** with 60s backoff (up to 24 hours)
- Return status to **GCHostPay1** `/status-verified`

**External APIs:**
- ChangeNow (check transaction status)

**Cloud Tasks:**
- Enqueues to: `GCHOSTPAY1_RESPONSE_QUEUE` → `GCHostPay1/status-verified`

**Retry Logic:**
```python
# Infinite retry via Cloud Tasks
max_duration = 24 hours
retry_backoff = 60 seconds (fixed)
```

---

### 12. **GCHostPay3-10-26** (ETH Payment Executor)

**Service Purpose:** Executes final ETH/ERC-20 token payments to client wallets.

**File:** `GCHostPay3-10-26/tphp3-10-26.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| POST | `/` | Execute ETH/ERC-20 payment | GCHostPay1 (via Cloud Tasks) |
| GET | `/health` | Health check | Cloud Run monitoring |

**Key Operations:**
- Decrypt token from GCHostPay1
- Determine currency type (native ETH vs ERC-20 token)
- Check wallet balance (ETH or ERC-20)
- Execute blockchain transaction using WalletManager
- **3-attempt retry limit** with error classification
- On success → Log to `hostpay_transactions`, enqueue response
- On failure after 3 attempts → Store in `failed_transactions`, send alert

**Database Tables:**
- `hostpay_transactions` (INSERT on success)
- `failed_transactions` (INSERT after 3 failures)

**External APIs:**
- Alchemy RPC (Ethereum blockchain)

**Cloud Tasks:**
- Enqueues to:
  - **Instant**: `GCHOSTPAY1_RESPONSE_QUEUE` → `GCHostPay1/payment-completed`
  - **Threshold**: `GCACCUMULATOR_RESPONSE_QUEUE` → `GCAccumulator/swap-executed`
  - **Retry**: `GCHOSTPAY3_RETRY_QUEUE` → `GCHostPay3/` (self-retry)

**Supported Currencies:**
- Native ETH
- ERC-20 tokens: USDT, USDC, DAI, etc. (via TOKEN_CONFIGS)

**Retry Logic:**
```python
# 3-attempt retry limit
if attempt < 3:
    enqueue_retry(delay=60s)
else:
    store_in_failed_transactions()
    send_alert()
```

---

### 13. **GCRegisterAPI-10-26** (Channel Registration API)

**Service Purpose:** REST API for channel registration and user management (separate from payment flow).

**File:** `GCRegisterAPI-10-26/app.py`

**Endpoints:**

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| **Authentication** | | | |
| POST | `/api/auth/signup` | User registration | Frontend (www.paygateprime.com) |
| POST | `/api/auth/login` | User login | Frontend |
| POST | `/api/auth/refresh` | JWT token refresh | Frontend |
| GET | `/api/auth/me` | Get current user | Frontend |
| **Channels** | | | |
| POST | `/api/channels/register` | Register new channel | Frontend (authenticated) |
| GET | `/api/channels` | Get user's channels | Frontend (authenticated) |
| GET | `/api/channels/<id>` | Get channel details | Frontend (authenticated) |
| PUT | `/api/channels/<id>` | Update channel | Frontend (authenticated) |
| DELETE | `/api/channels/<id>` | Delete channel | Frontend (authenticated) |
| **Mappings** | | | |
| GET | `/api/mappings/currency-network` | Get currency/network mappings | Frontend |
| **Utility** | | | |
| GET | `/api/health` | Health check | Cloud Run monitoring |
| GET | `/` | API info | Browser |

**Key Operations:**
- JWT-based authentication (stateless)
- CRUD operations for `main_clients_database`
- CORS-enabled for SPA frontend
- Rate limiting: 200/day, 50/hour

**Database Tables:**
- `users` (authentication)
- `main_clients_database` (channel management)

**External APIs:**
- None (internal only)

**Frontend:**
- GCRegisterWeb-10-26 (TypeScript + React SPA)
- Served from Google Cloud Storage
- URL: https://www.paygateprime.com

---

## Flow Chart: Payment Processing Flow

### **Full End-to-End Payment Flow**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PAYMENT PROCESSING FLOW                             │
│                    (Instant & Threshold Unified View)                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ Telegram     │
│ User         │
│ Initiates    │
│ Payment      │
└──────┬───────┘
       │
       ↓
┌──────────────────────────────────────────────────────────────┐
│ GCWebhook1 POST /                                            │
│ • Generate unique_id                                         │
│ • Create NowPayments invoice                                 │
│ • Store in private_channel_users_database                    │
│ • Return payment URL to Telegram bot                         │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ↓
       ┌───────────────────────────────┐
       │ User pays via NowPayments     │
       │ (External crypto payment)     │
       └───────────────┬───────────────┘
                       │
                       ↓ IPN Callback
┌──────────────────────────────────────────────────────────────┐
│ np-webhook POST /                                            │
│ • Verify HMAC-SHA512 signature                               │
│ • Parse order_id → (user_id, channel_id)                     │
│ • UPSERT payment data in database                            │
│ • Calculate outcome_amount_usd via CoinGecko                 │
│ • Idempotency check via processed_payments                   │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ↓ Cloud Tasks
┌──────────────────────────────────────────────────────────────┐
│ GCWebhook1 POST /process-validated-payment                   │
│ • Decrypt token from np-webhook                              │
│ • Verify payment amount matches subscription                 │
│ • Mark gcwebhook1_processed = TRUE                           │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ↓ Cloud Tasks
┌──────────────────────────────────────────────────────────────┐
│ GCSplit1 POST /                                              │
│ • Calculate outcome_amount_usd                               │
│ • DECISION POINT: Instant vs Threshold                       │
└──────────────────────┬───────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ↓ < $100                    ↓ ≥ $100
    INSTANT FLOW               THRESHOLD FLOW
         │                           │
         ↓                           ↓
┌─────────────────────┐    ┌─────────────────────┐
│ GCWebhook2 POST /   │    │ GCAccumulator       │
│                     │    │ POST /              │
└────────┬────────────┘    │ • Store in          │
         │                 │   batch_conversions │
         ↓ Cloud Tasks     └──────┬──────────────┘
┌─────────────────────┐           │
│ GCSplit2 POST /     │           ↓ Wait for batch trigger
│ • Create ChangeNow  │    ┌─────────────────────┐
│   exchange          │    │ GCBatchProcessor /  │
└────────┬────────────┘    │ GCMicroBatchProcessor
         │                 │ (Cloud Scheduler)   │
         │                 │ • Query pending     │
         │                 │ • Group by wallet   │
         │                 │ • Sum USD amounts   │
         │                 └──────┬──────────────┘
         │                        │
         │                        ↓ Cloud Tasks
         │                 ┌─────────────────────┐
         │                 │ GCSplit3 POST /     │
         │                 │ • Create ChangeNow  │
         │                 │   exchange          │
         │                 └──────┬──────────────┘
         │                        │
         └────────────────────────┴─────────────────┐
                                                     │
                       ↓ Cloud Tasks                │
         ┌──────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────────┐
│ GCHostPay1 POST /                                           │
│ • Receive cn_api_id from GCSplit2 or GCSplit3               │
│ • Context: 'instant' or 'threshold'                         │
└────────┬────────────────────────────────────────────────────┘
         │
         ↓ Cloud Tasks
┌─────────────────────────────────────────────────────────────┐
│ GCHostPay2 POST /                                           │
│ • Check ChangeNow transaction status                        │
│ • Infinite retry (60s backoff, 24h max)                     │
└────────┬────────────────────────────────────────────────────┘
         │
         ↓ Cloud Tasks
┌─────────────────────────────────────────────────────────────┐
│ GCHostPay1 POST /status-verified                            │
│ • Receive status from GCHostPay2                            │
│ • Check if status = 'finished'                              │
└────────┬────────────────────────────────────────────────────┘
         │
         ↓ status = 'finished' → Cloud Tasks
┌─────────────────────────────────────────────────────────────┐
│ GCHostPay3 POST /                                           │
│ • Determine currency type (ETH vs ERC-20)                   │
│ • Check wallet balance                                      │
│ • Execute blockchain transaction                            │
│ • 3-attempt retry on failure                                │
│ • Log to hostpay_transactions or failed_transactions        │
└────────┬────────────────────────────────────────────────────┘
         │
         ↓ Cloud Tasks
┌─────────────────────────────────────────────────────────────┐
│ GCHostPay1 POST /payment-completed                          │
│ • Receive tx_hash from GCHostPay3                           │
│ • Route based on context                                    │
└────────┬────────────────────────────────────────────────────┘
         │
         ├───────────────┬──────────────────────┐
         │               │                      │
         ↓ Instant       ↓ Threshold            │
┌─────────────────┐  ┌────────────────────┐    │
│ GCWebhook2      │  │ GCAccumulator      │    │
│ POST /payment-  │  │ POST /swap-executed│    │
│ completed       │  │ • Update database  │    │
│ (deprecated?)   │  │ • Send Telegram    │    │
└────────┬────────┘  │   invite           │    │
         │           └────────┬───────────┘    │
         │                    │                │
         ↓                    ↓                ↓
┌────────────────────────────────────────────────┐
│ GCWebhook1 POST /payment-completed             │
│ • Update main_clients_database                 │
│ • Send Telegram invite link to user            │
│ • Mark telegram_invite_sent = TRUE             │
└────────────────────────────────────────────────┘
         │
         ↓
   ┌─────────────┐
   │ User joins  │
   │ Telegram    │
   │ channel     │
   └─────────────┘
```

---

## Flow Chart: Instant vs Threshold Decision Tree

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GCSPLIT1: INSTANT VS THRESHOLD ROUTING                   │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌──────────────────────┐
                        │ GCSplit1 POST /      │
                        │ Receives payment     │
                        │ from GCWebhook1      │
                        └──────────┬───────────┘
                                   │
                                   ↓
                        ┌──────────────────────┐
                        │ Calculate            │
                        │ outcome_amount_usd   │
                        │ (from np-webhook)    │
                        └──────────┬───────────┘
                                   │
                                   ↓
                   ┌───────────────────────────────┐
                   │ Is outcome_amount_usd < $100? │
                   └───────────┬───────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ↓ YES (< $100)                ↓ NO (≥ $100)
    ┌───────────────────────┐     ┌───────────────────────┐
    │  INSTANT PAYOUT FLOW  │     │ THRESHOLD PAYOUT FLOW │
    └───────────┬───────────┘     └───────────┬───────────┘
                │                             │
                │                             │
                ↓                             ↓
    ┌───────────────────────┐     ┌───────────────────────┐
    │ Enqueue to            │     │ Enqueue to            │
    │ GCWEBHOOK2_QUEUE      │     │ GCACCUMULATOR_QUEUE   │
    │                       │     │                       │
    │ Target:               │     │ Target:               │
    │ GCWebhook2/           │     │ GCAccumulator/        │
    └───────────┬───────────┘     └───────────┬───────────┘
                │                             │
                │                             │
                ↓                             ↓
    ┌───────────────────────┐     ┌───────────────────────┐
    │ IMMEDIATE PROCESSING  │     │ BATCH ACCUMULATION    │
    │                       │     │                       │
    │ • Create ChangeNow    │     │ • Store in            │
    │   exchange NOW        │     │   batch_conversions   │
    │ • Check status        │     │   table               │
    │ • Execute payment     │     │ • Wait for batch      │
    │ • Send invite         │     │   trigger             │
    │                       │     │ • Process in group    │
    │ Latency: ~5-10 min    │     │ Latency: 1-24 hours   │
    └───────────────────────┘     └───────────────────────┘
```

**Decision Logic:**
```python
# In GCSplit1
INSTANT_THRESHOLD_USD = 100.0

if outcome_amount_usd < INSTANT_THRESHOLD_USD:
    # Route to instant flow
    target_queue = GCWEBHOOK2_QUEUE
    target_url = GCWEBHOOK2_URL
    flow_type = "instant"
else:
    # Route to threshold flow
    target_queue = GCACCUMULATOR_QUEUE
    target_url = GCACCUMULATOR_URL
    flow_type = "threshold"
```

---

## Flow Chart: Batch Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BATCH PROCESSING ARCHITECTURE                        │
│                      (Threshold Payments ≥ $100 USD)                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│ batch_conversions    │
│ Table                │
│                      │
│ • user_id            │
│ • channel_id         │
│ • wallet_address     │
│ • payout_currency    │
│ • outcome_amount_usd │
│ • status             │  ← 'pending'
│ • created_at         │
└──────────┬───────────┘
           │
           │ Multiple payments accumulate
           │ from different users
           │
           ↓
┌──────────────────────────────────────────────────────────────┐
│ Cloud Scheduler Triggers                                     │
├──────────────────────────────────────────────────────────────┤
│ • GCBatchProcessor    → Every 1 hour   (larger batches)     │
│ • GCMicroBatchProcessor → Every 15 min (smaller batches)    │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ↓ HTTP POST /
┌──────────────────────────────────────────────────────────────┐
│ GCBatchProcessor / GCMicroBatchProcessor                     │
│                                                              │
│ STEP 1: Query pending conversions                           │
│   SELECT * FROM batch_conversions                            │
│   WHERE status = 'pending'                                   │
│   ORDER BY created_at ASC                                    │
│                                                              │
│ STEP 2: Group by wallet + currency                          │
│   GROUP BY client_wallet_address, client_payout_currency    │
│                                                              │
│ STEP 3: Calculate totals                                    │
│   SUM(outcome_amount_usd) AS total_usd                       │
│                                                              │
│ STEP 4: Filter by threshold                                 │
│   WHERE total_usd >= 100.0 (or lower for micro-batch)       │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ↓
         ┌─────────────────────────────────┐
         │ Batch Processing Decision       │
         │                                 │
         │ For each qualifying batch:      │
         │ • wallet: 0xABC...              │
         │ • currency: USDT                │
         │ • total: $150.23 USD            │
         │ • num_payments: 3               │
         └─────────────┬───────────────────┘
                       │
                       ↓ Enqueue to Cloud Tasks
┌──────────────────────────────────────────────────────────────┐
│ GCSPLIT3_QUEUE → GCSplit3 POST /                            │
│                                                              │
│ Payload:                                                     │
│ • batch_id: [list of conversion IDs]                        │
│ • wallet_address: 0xABC...                                   │
│ • payout_currency: USDT                                      │
│ • total_usd: 150.23                                          │
│ • context: 'threshold'                                       │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│ GCSplit3 POST /                                              │
│ • Create ChangeNow exchange for $150.23                      │
│ • Extract cn_api_id                                          │
│ • Update batch_conversions status = 'processing'             │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ↓ Route to GCHostPay1 → GCHostPay2 → GCHostPay3
┌──────────────────────────────────────────────────────────────┐
│ Payment Execution Flow (same as instant)                     │
│ • Check ChangeNow status                                     │
│ • Execute single ETH payment for $150.23                     │
│ • Send to client wallet                                      │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ↓ Success
┌──────────────────────────────────────────────────────────────┐
│ GCAccumulator POST /swap-executed                            │
│ • Receive tx_hash from GCHostPay3                            │
│ • Update batch_conversions status = 'completed'              │
│ • Send Telegram invites to ALL users in batch                │
│   (3 users in this example)                                  │
└──────────────────────────────────────────────────────────────┘
           │
           ↓
┌──────────────────────┐
│ batch_conversions    │
│ status = 'completed' │
│ tx_hash stored       │
└──────────────────────┘
```

**Batch Aggregation Example:**

```sql
-- GCBatchProcessor query
SELECT
    client_wallet_address,
    client_payout_currency,
    SUM(outcome_amount_usd) AS total_usd,
    COUNT(*) AS num_payments,
    ARRAY_AGG(id) AS batch_ids
FROM batch_conversions
WHERE status = 'pending'
GROUP BY client_wallet_address, client_payout_currency
HAVING SUM(outcome_amount_usd) >= 100.0
ORDER BY total_usd DESC;
```

**Result:**
```
wallet_address          | currency | total_usd | num_payments | batch_ids
------------------------+----------+-----------+--------------+-----------
0xABC123...             | USDT     | 150.23    | 3            | [45,46,51]
0xDEF456...             | ETH      | 225.50    | 5            | [47,48,49,50,52]
```

Each row becomes a **single ChangeNow exchange** and **single ETH payment**.

---

## Endpoint Interaction Matrix

**Visual representation of which services call which endpoints:**

```
CALLER ↓     ENDPOINT TARGET →

┌──────────────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│              │ np  │ GCW1│ GCW2│ GCS1│ GCS2│ GCS3│ GCAC│ GCBP│GCMBP│ HP1 │ HP2 │ HP3 │ REG │
├──────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
│ NowPayments  │  ✓  │     │     │     │     │     │     │     │     │     │     │     │     │
│ Telegram Bot │     │  ✓  │     │     │     │     │     │     │     │     │     │     │     │
│ Frontend     │     │     │     │     │     │     │     │     │     │     │     │     │  ✓  │
│ Scheduler    │     │     │     │     │     │     │     │  ✓  │  ✓  │     │     │     │     │
├──────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
│ np-webhook   │     │  ✓  │     │     │     │     │     │     │     │     │     │     │     │
│ GCWebhook1   │     │     │     │  ✓  │     │     │     │     │     │     │     │     │     │
│ GCWebhook2   │     │     │     │     │  ✓  │     │     │     │     │  ✓  │     │     │     │
│ GCSplit1     │     │     │  ✓  │     │     │     │  ✓  │     │     │     │     │     │     │
│ GCSplit2     │     │     │     │     │     │     │     │     │     │  ✓  │     │     │     │
│ GCSplit3     │     │     │     │     │     │     │     │     │     │  ✓  │     │     │     │
│ GCAccumulator│     │  ✓  │     │     │     │     │     │     │     │     │     │     │     │
│ GCBatchProc  │     │     │     │     │     │  ✓  │     │     │     │     │     │     │     │
│ GCMicroBatch │     │     │     │     │     │  ✓  │     │     │     │     │     │     │     │
│ GCHostPay1   │     │     │  ✓  │     │     │     │  ✓  │     │     │     │  ✓  │  ✓  │     │
│ GCHostPay2   │     │     │     │     │     │     │     │     │     │  ✓  │     │     │     │
│ GCHostPay3   │     │  ✓  │     │     │     │     │  ✓  │     │     │  ✓  │     │     │     │
└──────────────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘

Legend:
✓ = Service makes HTTP requests to this service
```

**Detailed Call Graph:**

```
External → np-webhook → GCWebhook1 → GCSplit1 ┬→ GCWebhook2 → GCSplit2 → GCHostPay1 → ...
                                              └→ GCAccumulator (stores)
                                                        ↑
                                                        │
                                                 GCBatchProcessor (scheduler)
                                                        │
                                                        ↓
                                                    GCSplit3 → GCHostPay1 → ...

GCHostPay1 → GCHostPay2 → GCHostPay1 → GCHostPay3 → GCHostPay1 ┬→ GCWebhook2 (deprecated?)
                                                                └→ GCAccumulator
                                                                └→ GCWebhook1 (for invite)
```

---

## Cloud Tasks Queue Mapping

**All Cloud Tasks queues used in the system:**

| Queue Name | Source Service | Target Service | Target Endpoint | Purpose |
|------------|---------------|----------------|-----------------|---------|
| `GCWEBHOOK1_QUEUE` | np-webhook | GCWebhook1 | `/process-validated-payment` | Trigger payment processing after NowPayments validation |
| `GCSPLIT1_QUEUE` | GCWebhook1 | GCSplit1 | `/` | Route to instant/threshold decision |
| `GCWEBHOOK2_QUEUE` | GCSplit1 | GCWebhook2 | `/` | Trigger instant payment flow |
| `GCSPLIT2_QUEUE` | GCWebhook2 | GCSplit2 | `/` | Create ChangeNow exchange (instant) |
| `GCACCUMULATOR_QUEUE` | GCSplit1 | GCAccumulator | `/` | Store threshold payment for batching |
| `GCSPLIT3_QUEUE` | GCBatchProcessor<br>GCMicroBatchProcessor | GCSplit3 | `/` | Create ChangeNow exchange (batch) |
| `GCHOSTPAY1_QUEUE` | GCSplit2<br>GCSplit3 | GCHostPay1 | `/` | Initiate payment orchestration |
| `GCHOSTPAY2_QUEUE` | GCHostPay1 | GCHostPay2 | `/` | Check ChangeNow status |
| `GCHOSTPAY1_RESPONSE_QUEUE` | GCHostPay2 | GCHostPay1 | `/status-verified` | Return ChangeNow status to orchestrator |
| `GCHOSTPAY3_QUEUE` | GCHostPay1 | GCHostPay3 | `/` | Execute ETH payment |
| `GCHOSTPAY3_RETRY_QUEUE` | GCHostPay3 | GCHostPay3 | `/` | Retry failed payment (self-retry) |
| `GCACCUMULATOR_RESPONSE_QUEUE` | GCHostPay3 | GCAccumulator | `/swap-executed` | Notify batch payment completion |

**Queue Configuration Notes:**
- All queues use Cloud Tasks HTTP targets
- Retry configuration: Exponential backoff (default)
- Max attempts: Varies by queue (3 for payments, infinite for status checks)
- Authentication: OIDC token-based (service account)

---

## Database Operations by Service

### **PostgreSQL Database Schema (telepaydb)**

**Main Tables:**

| Table Name | Purpose | Primary Services |
|------------|---------|------------------|
| `private_channel_users_database` | User subscriptions + payment data | np-webhook, GCWebhook1 |
| `main_clients_database` | Channel configuration + wallet info | GCWebhook1, GCAccumulator, GCRegisterAPI |
| `batch_conversions` | Threshold payment accumulation | GCSplit1, GCBatchProcessor, GCAccumulator |
| `hostpay_transactions` | Successful ETH payments log | GCHostPay3 |
| `failed_transactions` | Failed payment records | GCHostPay3 |
| `processed_payments` | Idempotency tracking | np-webhook, GCWebhook1 |
| `users` | User authentication | GCRegisterAPI |

**Database Operations by Service:**

| Service | Tables | Operations |
|---------|--------|------------|
| **np-webhook** | `private_channel_users_database`<br>`main_clients_database`<br>`processed_payments` | UPSERT payment data<br>SELECT channel mapping<br>INSERT/SELECT idempotency |
| **GCWebhook1** | `private_channel_users_database`<br>`main_clients_database`<br>`processed_payments` | INSERT initial record<br>UPDATE conversion data<br>UPDATE telegram invite status |
| **GCSplit1** | `batch_conversions` | INSERT threshold payments |
| **GCBatchProcessor<br>GCMicroBatchProcessor** | `batch_conversions` | SELECT pending<br>UPDATE to processing |
| **GCAccumulator** | `batch_conversions`<br>`main_clients_database` | UPDATE to completed<br>UPDATE conversion data |
| **GCHostPay3** | `hostpay_transactions`<br>`failed_transactions` | INSERT successful tx<br>INSERT failed tx |
| **GCRegisterAPI** | `main_clients_database`<br>`users` | Full CRUD operations<br>User authentication |

---

## External API Integrations

### **1. NowPayments API**

**Used by:** GCWebhook1

**Endpoints:**
- `POST /v1/invoice` - Create payment invoice

**Authentication:** API key in `x-api-key` header

**Flow:**
```
GCWebhook1 → NowPayments API
   Request: Create invoice
   Response: invoice_id, invoice_url, order_id

User → NowPayments checkout page → Crypto payment

NowPayments → np-webhook (IPN callback)
   Request: Payment confirmation with HMAC signature
   Response: 200 OK
```

---

### **2. ChangeNow API**

**Used by:** GCSplit2, GCSplit3, GCHostPay2

**Endpoints:**
- `POST /v2/exchange` - Create exchange transaction (GCSplit2, GCSplit3)
- `GET /v2/exchange/by-id/{id}` - Check exchange status (GCHostPay2)

**Authentication:** API key in `x-changenow-api-key` header

**Flow:**
```
GCSplit2/3 → ChangeNow API
   Request: Create exchange (ETH → USDT)
   Response: id (cn_api_id), payinAddress, status

Platform → ChangeNow payinAddress (ETH payment)

GCHostPay2 → ChangeNow API (polling)
   Request: GET /v2/exchange/by-id/{cn_api_id}
   Response: status (waiting → confirming → finished)
```

**Status Values:**
- `waiting` - Awaiting payment
- `confirming` - Payment received, confirming
- `exchanging` - Exchange in progress
- `finished` - Exchange complete
- `failed` - Exchange failed

---

### **3. CoinGecko API**

**Used by:** np-webhook

**Endpoints:**
- `GET /v3/simple/price` - Get cryptocurrency prices in USD

**Authentication:** None (public API)

**Purpose:** Convert crypto amounts to USD for threshold decision

**Example:**
```
GET /v3/simple/price?ids=ethereum&vs_currencies=usd
Response: {"ethereum": {"usd": 2500.42}}

Calculation:
0.05 ETH × $2500.42 = $125.02 USD → Threshold flow
```

---

### **4. Alchemy RPC (Ethereum)**

**Used by:** GCHostPay3 (WalletManager)

**Endpoints:**
- JSON-RPC 2.0 methods (via web3.py)
  - `eth_getBalance` - Check ETH balance
  - `eth_call` - Check ERC-20 token balance
  - `eth_sendRawTransaction` - Broadcast signed transaction
  - `eth_getTransactionReceipt` - Get transaction result

**Authentication:** API key in URL

**Flow:**
```
GCHostPay3 → Alchemy RPC
   1. Check balance: eth_getBalance(wallet_address)
   2. Build transaction: web3.eth.account.sign_transaction()
   3. Send transaction: eth_sendRawTransaction(signed_tx)
   4. Wait for receipt: eth_getTransactionReceipt(tx_hash)
```

---

### **5. Telegram Bot API**

**Used by:** GCWebhook1, GCAccumulator

**Endpoints:**
- `POST /bot{token}/sendMessage` - Send invite link to user

**Authentication:** Bot token in URL

**Flow:**
```
GCWebhook1/GCAccumulator → Telegram Bot API
   Request: Send message with invite link
   Response: message_id, chat_id
```

**Message Format:**
```python
{
    "chat_id": user_id,
    "text": "✅ Payment confirmed! Join your channel: {invite_link}",
    "parse_mode": "Markdown"
}
```

---

## Summary

This analysis covers **13 microservices** with **44 HTTP endpoints** processing **2 distinct payment flows** (instant and threshold). The system orchestrates:

- **6 external API integrations** (NowPayments, ChangeNow, CoinGecko, Alchemy, Telegram)
- **12 Cloud Tasks queues** for asynchronous processing
- **7 database tables** for state management
- **2 scheduled jobs** for batch processing (GCBatchProcessor, GCMicroBatchProcessor)

The architecture demonstrates a **fully event-driven, fault-tolerant microservices design** using:
- ✅ Encrypted token-based communication
- ✅ Idempotency protection
- ✅ Retry mechanisms (3-attempt for payments, infinite for status checks)
- ✅ Error classification and alerting
- ✅ Database-backed state tracking
- ✅ Cloud-native deployment (Cloud Run, Cloud Tasks, Cloud SQL)

---

**End of Analysis**
