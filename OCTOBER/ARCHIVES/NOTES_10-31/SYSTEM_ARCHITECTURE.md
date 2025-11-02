# TelegramFunnel System Architecture

**Version:** 10-26
**Last Updated:** 2025-10-28
**Status:** Production

---

## Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Service Directory](#service-directory)
4. [Data Flow Diagrams](#data-flow-diagrams)
5. [Database Schema](#database-schema)
6. [Security & Authentication](#security--authentication)
7. [Emoji Patterns Reference](#emoji-patterns-reference)
8. [Deployment Architecture](#deployment-architecture)
9. [Monitoring & Operations](#monitoring--operations)

---

## System Overview

### Purpose
TelegramFunnel is a cryptocurrency payment gateway system that enables Telegram channel owners to monetize their private channels through automated subscription management. Users pay in various cryptocurrencies, and payments are split between the platform and channel owners.

### Core Capabilities
- 💬 **Telegram Bot Interface** - User registration, payment, channel access
- 🌐 **Web Registration** - www.paygateprime.com for channel owner registration
- 💰 **Payment Processing** - Multi-currency support via NOWPayments
- 🔄 **Payment Splitting** - Automated profit sharing via ChangeNow
- 🏦 **ETH Distribution** - Direct ETH transfers to channel owners
- 📅 **Subscription Management** - Automated expiration and access revocation

### Technology Stack
- **Language:** Python 3.11+
- **Web Framework:** Flask
- **Telegram Bot:** python-telegram-bot v20+
- **Database:** PostgreSQL 14 (Cloud SQL)
- **Cloud Platform:** Google Cloud Platform (GCP)
- **Compute:** Google Cloud Run (serverless containers)
- **Orchestration:** Google Cloud Tasks
- **Configuration:** Google Secret Manager
- **External APIs:** NOWPayments, ChangeNow, Ethereum RPC (Alchemy)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION LAYER                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐              ┌────────────────────────┐           │
│  │   Telegram   │              │   Web Browser          │           │
│  │   Users      │              │   (Channel Owners)     │           │
│  └──────┬───────┘              └────────┬───────────────┘           │
│         │                               │                            │
└─────────┼───────────────────────────────┼────────────────────────────┘
          │                               │
          ▼                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      APPLICATION SERVICES LAYER                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────┐                ┌──────────────────┐           │
│  │  TelePay10-26    │                │ GCRegister10-26  │           │
│  │  Telegram Bot    │                │ Registration Web │           │
│  │  (polling)       │                │ (Flask App)      │           │
│  └────────┬─────────┘                └────────┬─────────┘           │
│           │                                   │                      │
│           │ Receives payment                  │ Registers            │
│           │ confirmation                      │ channels             │
│           ▼                                   ▼                      │
│  ┌──────────────────┐                ┌──────────────────┐           │
│  │ GCWebhook1-10-26 │                │   PostgreSQL     │           │
│  │ Payment Processor│◄───────────────┤   Cloud SQL      │           │
│  └────────┬─────────┘                └──────────────────┘           │
│           │                                                          │
│           ├─────────► GCWebhook2-10-26 (Telegram Invites)           │
│           └─────────► GCSplit1-10-26 (Payment Splitting)            │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
          │                               │
          ▼                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PAYMENT PROCESSING LAYER                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │              GCSplit Orchestration (3-Stage)             │        │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │        │
│  │  │  GCSplit1  │─►│  GCSplit2  │─►│  GCSplit3  │        │        │
│  │  │Orchestrator│  │USDT→ETH Est│  │ETH→Client  │        │        │
│  │  └────────────┘  └────────────┘  └──────┬─────┘        │        │
│  │                                          │               │        │
│  └──────────────────────────────────────────┼──────────────┘        │
│                                             │                        │
│  ┌──────────────────────────────────────────┼──────────────┐        │
│  │           GCHostPay Orchestration (3-Stage)             │        │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │        │
│  │  │ GCHostPay1 │◄─┤ GCHostPay2 │  │ GCHostPay3 │        │        │
│  │  │Orchestrator│  │Status Check│  │ETH Payment │        │        │
│  │  │            │─►│ ChangeNow  │─►│  Executor  │        │        │
│  │  └────────────┘  └────────────┘  └────────────┘        │        │
│  └─────────────────────────────────────────────────────────┘        │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
          │                               │                    │
          ▼                               ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       EXTERNAL SERVICES LAYER                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │
│  │  NOWPayments  │  │   ChangeNow   │  │  Ethereum RPC │           │
│  │  (Payments)   │  │ (Crypto Swap) │  │   (Alchemy)   │           │
│  └───────────────┘  └───────────────┘  └───────────────┘           │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Service Directory

### 1. TelePay10-26 - Telegram Bot Service
**Type:** Long-running service (polling mode)
**Entry Point:** `telepay10-26.py`
**Port:** N/A (polling, not HTTP)

#### Purpose
Main Telegram bot interface for end users. Handles:
- User registration via subscription links
- Payment gateway integration
- Channel configuration for owners
- Subscription monitoring and expiration
- Broadcasting messages

#### Key Components
- **`telepay10-26.py`** - Main orchestrator
- **`app_initializer.py`** - Bootstrap application
- **`bot_manager.py`** - Conversation handlers and bot setup
- **`menu_handlers.py`** - Inline keyboard menu system
- **`input_handlers.py`** - User input processing and validation
- **`subscription_manager.py`** - Background subscription monitoring (60s loop)
- **`database.py`** - Database operations
- **`config_manager.py`** - Secret Manager integration
- **`server_manager.py`** - Flask webhook server (runs in background thread)
- **`start_np_gateway.py`** - Payment gateway handler
- **`broadcast_manager.py`** - Message broadcasting
- **`message_utils.py`** - Message formatting helpers

#### Key Features
- **New Database UI** (Oct 26): Inline form-based configuration with nested menus
- **Subscription Monitoring**: Checks for expired subscriptions every 60 seconds
- **Payment Gateway**: Integrates with NOWPayments
- **Conversation Handlers**: DATABASE_V2, donation flow, menu navigation

#### Configuration
- `TELEGRAM_BOT_SECRET_NAME` - Bot token
- `NOWPAYMENT_WEBHOOK_KEY` - NOWPayments webhook key
- `TELEGRAM_BOT_USERNAME` - Bot username
- `TELEGRAM_BOT_WEBHOOK_URL` - Webhook URL (if using webhooks)

#### Emoji Patterns
🚀 ✅ ❌ 💾 👤 📨 🕐 💰 🔐 🎯

---

### 2. GCRegister10-26 - Channel Registration Web App
**Type:** HTTP service (Flask)
**Entry Point:** `tpr10-26.py`
**Port:** 8080
**Public URL:** www.paygateprime.com

#### Purpose
Web application for channel owners to register their channels into the payment system.

#### Key Components
- **`tpr10-26.py`** - Flask application
- **`forms.py`** - WTForms validation
- **`validators.py`** - Custom field validators
- **`database_manager.py`** - Database operations
- **`config_manager.py`** - Configuration management
- **`templates/`** - Jinja2 HTML templates
  - `register.html` - Main registration form
  - `success.html` - Success confirmation
  - `error.html` - Error page
- **`static/css/style.css`** - Styling

#### Endpoints
- `GET/POST /` - Registration form
- `GET /success` - Success page
- `GET /api/currency-network-mappings` - API for currency/network data
- `GET /health` - Health check

#### Key Features
- Math-based CAPTCHA (random addition)
- Tier selection (1-3 subscription tiers)
- Dynamic currency/network filtering
- Form validation with WTForms
- Rate limiting (currently disabled for testing)

#### Configuration
- `SECRET_KEY` - Flask session secret
- Database connection via Secret Manager

#### Emoji Patterns
🚀 ✅ ❌ 📝 💰 🔐 🔍 ⚠️

---

### 3. GCWebhook1-10-26 - Payment Processor Service
**Type:** HTTP service (Flask)
**Entry Point:** `tph1-10-26.py`
**Port:** 8080

#### Purpose
Receives payment confirmations from NOWPayments success_url, processes them, and triggers downstream workflows.

#### Key Components
- **`tph1-10-26.py`** - Flask application
- **`token_manager.py`** - Token encryption/decryption
- **`database_manager.py`** - Database operations
- **`cloudtasks_client.py`** - Cloud Tasks integration
- **`config_manager.py`** - Configuration management

#### Endpoints
- `GET /` - Main endpoint (receives success_url with token)
- `GET /health` - Health check

#### Data Flow
1. Receives success_url from NOWPayments with encrypted token
2. Decrypts token to extract:
   - user_id, closed_channel_id
   - subscription_price, subscription_time_days
   - wallet_address, payout_currency, payout_network
3. Calculates expiration date/time
4. Writes to `private_channel_users_database`
5. Encrypts token for GCWebhook2 → Enqueues Telegram invite task
6. Enqueues task to GCSplit1 for payment splitting
7. Returns 200 to NOWPayments

#### Configuration
- `SUCCESS_URL_SIGNING_KEY` - Token signing key
- Database connection
- Cloud Tasks queues: `gcwebhook2_queue`, `gcsplit1_queue`

#### Emoji Patterns
🎯 ✅ ❌ 💾 👤 💰 🏦 🌐 📅 🕒

---

### 4. GCWebhook2-10-26 - Telegram Invite Sender
**Type:** HTTP service (Flask)
**Entry Point:** `tph2-10-26.py`
**Port:** 8080

#### Purpose
Sends one-time Telegram invite links to users after successful payment.

#### Key Components
- **`tph2-10-26.py`** - Flask application (sync route with asyncio.run())
- **`token_manager.py`** - Token decryption
- **`config_manager.py`** - Configuration management

#### Endpoints
- `POST /` - Main endpoint (receives task from GCWebhook1)
- `GET /health` - Health check

#### Architecture Pattern: Sync + asyncio.run()
```python
@app.route("/", methods=["POST"])
def send_telegram_invite():  # Sync route
    async def send_invite_async():
        bot = Bot(bot_token)  # Fresh Bot instance
        invite = await bot.create_chat_invite_link(...)
        await bot.send_message(...)
        return {"success": True, "invite_link": invite.invite_link}

    result = asyncio.run(send_invite_async())  # Isolated event loop
    return jsonify(result), 200
```

**Why this pattern?**
- Cloud Run is stateless; event loops don't persist between requests
- Fresh event loop per request prevents "Event loop is closed" errors
- Fresh Bot instance ensures clean httpx connection pool
- Event loop lifecycle contained within request scope

#### Data Flow
1. Receives encrypted token from Cloud Tasks
2. Decrypts to extract user_id, closed_channel_id
3. Creates fresh Bot instance
4. Generates one-time invite link (expires in 1 hour, 1 use)
5. Sends invite message to user
6. Returns 200 (or 500 to trigger retry)

#### Retry Logic
- Infinite retry via Cloud Tasks (60s backoff, 24h max)
- Handles Telegram API errors gracefully

#### Configuration
- `TELEGRAM_BOT_TOKEN` - Bot token
- `SUCCESS_URL_SIGNING_KEY` - Token signing key

#### Emoji Patterns
🎯 ✅ ❌ 📨 👤 🔄

---

### 5. GCSplit1-10-26 - Payment Split Orchestrator
**Type:** HTTP service (Flask)
**Entry Point:** `tps1-10-26.py`
**Port:** 8080

#### Purpose
Orchestrates the 3-stage payment splitting workflow. Coordinates USDT→ETH conversion and ETH→ClientCurrency swap.

#### Key Components
- **`tps1-10-26.py`** - Flask application
- **`token_manager.py`** - Token encryption/decryption
- **`database_manager.py`** - Database operations
- **`cloudtasks_client.py`** - Cloud Tasks integration
- **`config_manager.py`** - Configuration management

#### Endpoints
1. `POST /` - Initial webhook from GCWebhook
2. `POST /usdt-eth-estimate` - Receives estimate from GCSplit2
3. `POST /eth-client-swap` - Receives swap result from GCSplit3

#### Data Flow

**Stage 1: Initial Request**
1. Receives webhook from GCWebhook1 with payment data
2. Verifies HMAC signature
3. Calculates adjusted amount (removes TP flat fee, default 3%)
4. Encrypts token for GCSplit2
5. Enqueues to GCSplit2

**Stage 2: USDT→ETH Estimate Response**
1. Receives encrypted token from GCSplit2 with estimate data
2. Calculates **pure market conversion value**:
   ```python
   # ChangeNow's toAmount is post-fee
   # We need MARKET VALUE (what the dollar amount is worth in ETH)
   usdt_swapped = from_amount - deposit_fee
   eth_before_withdrawal = to_amount + withdrawal_fee
   market_rate = eth_before_withdrawal / usdt_swapped
   pure_market_value = from_amount * market_rate
   ```
3. Inserts into `split_payout_request` with pure market value
4. Encrypts token for GCSplit3
5. Enqueues to GCSplit3

**Stage 3: ETH→Client Swap Response**
1. Receives encrypted token from GCSplit3 with swap transaction data
2. Inserts into `split_payout_que` (linked via unique_id)
3. Builds GCHostPay token
4. Enqueues to GCHostPay1

#### Database Tables
- **split_payout_request**: Initial split request with pure market value
- **split_payout_que**: ChangeNow transaction data

#### Configuration
- `SUCCESS_URL_SIGNING_KEY` - Token signing key
- `TP_FLAT_FEE` - Platform fee percentage (default 3%)
- `TPS_HOSTPAY_SIGNING_KEY` - HostPay token signing key
- Cloud Tasks queues: `gcsplit2_queue`, `gcsplit3_queue`, `hostpay_queue`

#### Emoji Patterns
🎯 ✅ ❌ 💰 🏦 🌐 💾 🆔 👤 🧮 💸 📊

---

### 6. GCSplit2-10-26 - USDT→ETH Estimator
**Type:** HTTP service (Flask)
**Entry Point:** `tps2-10-26.py`
**Port:** 8080

#### Purpose
Calls ChangeNow API to get USDT→ETH conversion estimates.

#### Key Components
- **`tps2-10-26.py`** - Flask application
- **`changenow_client.py`** - ChangeNow API client with retry
- **`token_manager.py`** - Token encryption/decryption
- **`cloudtasks_client.py`** - Cloud Tasks integration
- **`config_manager.py`** - Configuration management

#### Endpoints
- `POST /` - Main endpoint (receives task from GCSplit1)
- `GET /health` - Health check

#### Data Flow
1. Receives encrypted token from GCSplit1
2. Decrypts to extract: user_id, wallet_address, adjusted_amount_usdt
3. Calls ChangeNow API v2 estimate endpoint (USDT→ETH)
4. Extracts: fromAmount, toAmount, depositFee, withdrawalFee
5. Encrypts response token
6. Enqueues back to GCSplit1 /usdt-eth-estimate

#### Retry Logic
- Infinite retry in `changenow_client.get_estimated_amount_v2_with_retry()`
- 60s sleep between retries
- Logs each attempt with 🔄 emoji

#### Configuration
- `CHANGENOW_API_KEY` - ChangeNow API key
- `SUCCESS_URL_SIGNING_KEY` - Token signing key
- Cloud Tasks queue: `gcsplit1_response_queue`

#### Emoji Patterns
🎯 ✅ ❌ 👤 💰 🌐 🏦 🔄

---

### 7. GCSplit3-10-26 - ETH→ClientCurrency Swapper
**Type:** HTTP service (Flask)
**Entry Point:** `tps3-10-26.py`
**Port:** 8080

#### Purpose
Creates ChangeNow fixed-rate transactions to swap ETH to client's desired currency.

#### Key Components
- **`tps3-10-26.py`** - Flask application
- **`changenow_client.py`** - ChangeNow API client with retry
- **`token_manager.py`** - Token encryption/decryption
- **`cloudtasks_client.py`** - Cloud Tasks integration
- **`config_manager.py`** - Configuration management

#### Endpoints
- `POST /` - Main endpoint (receives task from GCSplit1)
- `GET /health` - Health check

#### Data Flow
1. Receives encrypted token from GCSplit1
2. Decrypts to extract: unique_id, eth_amount, wallet_address, payout_currency/network
3. Calls ChangeNow API v2 create fixed-rate transaction (ETH→ClientCurrency)
4. Extracts full transaction data:
   - cn_api_id (ChangeNow transaction ID)
   - payin_address (where to send ETH)
   - payout_address (where client receives)
   - from_amount, to_amount
   - flow, type
5. Encrypts response token with ALL transaction data
6. Enqueues back to GCSplit1 /eth-client-swap

#### Retry Logic
- Infinite retry in `changenow_client.create_fixed_rate_transaction_with_retry()`
- 60s sleep between retries
- Logs each attempt

#### Configuration
- `CHANGENOW_API_KEY` - ChangeNow API key
- `SUCCESS_URL_SIGNING_KEY` - Token signing key
- Cloud Tasks queue: `gcsplit1_response_queue`

#### Emoji Patterns
🎯 ✅ ❌ 🆔 👤 💰 🌐 🏦 🔄

---

### 8. GCHostPay1-10-26 - Validator & Orchestrator
**Type:** HTTP service (Flask)
**Entry Point:** `tphp1-10-26.py`
**Port:** 8080

#### Purpose
Orchestrates the 3-stage ETH payment workflow. Validates requests, checks ChangeNow status, executes ETH transfers.

#### Key Components
- **`tphp1-10-26.py`** - Flask application
- **`token_manager.py`** - Token encryption/decryption (dual keys)
- **`database_manager.py`** - Database operations
- **`cloudtasks_client.py`** - Cloud Tasks integration
- **`config_manager.py`** - Configuration management

#### Endpoints
1. `POST /` - Main webhook from GCSplit1
2. `POST /status-verified` - Status check response from GCHostPay2
3. `POST /payment-completed` - Payment execution response from GCHostPay3

#### Data Flow

**Stage 1: Initial Request**
1. Receives token from GCSplit1 (encrypted with TPS_HOSTPAY_SIGNING_KEY)
2. Decrypts to extract: unique_id, cn_api_id, from_currency, from_amount, payin_address
3. Checks database for duplicate transaction
4. Encrypts token for GCHostPay2 (with SUCCESS_URL_SIGNING_KEY)
5. Enqueues to GCHostPay2

**Stage 2: Status Check Response**
1. Receives token from GCHostPay2 with ChangeNow status
2. Validates status == "waiting"
3. Encrypts token for GCHostPay3
4. Enqueues to GCHostPay3

**Stage 3: Payment Completion Response**
1. Receives token from GCHostPay3 with tx details
2. Logs final status (tx_hash, gas_used, block_number)
3. Returns success

#### Database Tables
- Checks `hostpay_transactions` for duplicates

#### Configuration
- `TPS_HOSTPAY_SIGNING_KEY` - Token signing key from GCSplit
- `SUCCESS_URL_SIGNING_KEY` - Internal signing key
- Cloud Tasks queues: `gchostpay2_queue`, `gchostpay3_queue`

#### Emoji Patterns
🎯 ✅ ❌ 🆔 💰 🏦 📊 ⚠️

---

### 9. GCHostPay2-10-26 - ChangeNow Status Checker
**Type:** HTTP service (Flask)
**Entry Point:** `tphp2-10-26.py`
**Port:** 8080

#### Purpose
Checks ChangeNow transaction status with infinite retry before proceeding to payment execution.

#### Key Components
- **`tphp2-10-26.py`** - Flask application
- **`changenow_client.py`** - ChangeNow API client with retry
- **`token_manager.py`** - Token encryption/decryption
- **`cloudtasks_client.py`** - Cloud Tasks integration
- **`config_manager.py`** - Configuration management

#### Endpoints
- `POST /` - Main endpoint (receives task from GCHostPay1)
- `GET /health` - Health check

#### Data Flow
1. Receives encrypted token from GCHostPay1
2. Decrypts to extract: unique_id, cn_api_id, payment details
3. Calls ChangeNow status API with **infinite retry**
4. Extracts status field (expected: "waiting")
5. Encrypts response token with status + payment details
6. Enqueues back to GCHostPay1 /status-verified

#### Retry Logic
- `changenow_client.check_transaction_status_with_retry(cn_api_id)`
- Infinite retry with 60s sleep
- Will eventually succeed or timeout after 24h

#### Why Check Status?
- Ensures ChangeNow transaction is in "waiting" state before sending ETH
- Prevents sending ETH to invalid/expired transactions
- Safety check before irreversible blockchain operation

#### Configuration
- `CHANGENOW_API_KEY` - ChangeNow API key
- `SUCCESS_URL_SIGNING_KEY` - Token signing key
- Cloud Tasks queue: `gchostpay1_response_queue`

#### Emoji Patterns
🎯 ✅ ❌ 🆔 📊 🌐 💰 🔄

---

### 10. GCHostPay3-10-26 - ETH Payment Executor
**Type:** HTTP service (Flask)
**Entry Point:** `tphp3-10-26.py`
**Port:** 8080

#### Purpose
Executes ETH transfers to ChangeNow payin addresses with infinite retry.

#### Key Components
- **`tphp3-10-26.py`** - Flask application
- **`wallet_manager.py`** - Ethereum wallet operations (web3py)
- **`token_manager.py`** - Token encryption/decryption
- **`database_manager.py`** - Database operations
- **`cloudtasks_client.py`** - Cloud Tasks integration
- **`config_manager.py`** - Configuration management

#### Endpoints
- `POST /` - Main endpoint (receives task from GCHostPay1)
- `GET /health` - Health check

#### Data Flow
1. Receives encrypted token from GCHostPay1
2. Decrypts to extract: unique_id, payin_address, from_amount, cn_api_id
3. Executes ETH payment with **infinite retry**:
   ```python
   wallet_manager.send_eth_payment_with_infinite_retry(
       to_address=payin_address,
       amount=from_amount,
       unique_id=unique_id
   )
   ```
4. Receives tx result (tx_hash, status, gas_used, block_number)
5. **ONLY AFTER SUCCESS**: Writes to `hostpay_transactions` database
6. Encrypts response token with tx details
7. Enqueues back to GCHostPay1 /payment-completed

#### Retry Logic
- Infinite retry in `wallet_manager.send_eth_payment_with_infinite_retry()`
- Handles:
  - RPC connection failures
  - Insufficient gas
  - Nonce conflicts
  - Network congestion
- 60s sleep between retries
- Will eventually succeed or timeout after 24h

#### Database Write Strategy
**Critical:** Database write happens ONLY after successful ETH transfer
- Prevents logging failed attempts
- Clean audit trail
- Database reflects actual blockchain state

#### Configuration
- `HOST_WALLET_ADDRESS` - ETH wallet address
- `HOST_WALLET_PRIVATE_KEY` - Private key
- `ETHEREUM_RPC_URL` - Alchemy RPC endpoint
- `ETHEREUM_RPC_URL_API` - Alchemy API key
- `SUCCESS_URL_SIGNING_KEY` - Token signing key
- Cloud Tasks queue: `gchostpay1_response_queue`

#### Emoji Patterns
🎯 ✅ ❌ 🆔 💰 🔗 ⛽ 📦 🔄

---

## Data Flow Diagrams

### Complete Payment Flow (User → Channel Access)

```
┌──────────┐
│   User   │
└────┬─────┘
     │
     │ 1. /start {subscription_token}
     ▼
┌──────────────────┐
│  TelePay10-26    │
│  Telegram Bot    │
└────┬─────────────┘
     │
     │ 2. Generate payment link (NOWPayments)
     │    with success_url pointing to GCWebhook1
     ▼
┌──────────────────┐
│   User pays via  │
│   NOWPayments    │
└────┬─────────────┘
     │
     │ 3. Payment confirmed → success_url callback
     ▼
┌──────────────────────┐
│  GCWebhook1-10-26    │──► 4. Write to private_channel_users_database
│  Payment Processor   │       (user_id, channel_id, expire_date, etc.)
└────┬─────────┬───────┘
     │         │
     │         │ 5. Enqueue to GCWebhook2
     │         ▼
     │    ┌─────────────────┐
     │    │ GCWebhook2-10-26│
     │    │ Invite Sender   │
     │    └────┬────────────┘
     │         │
     │         │ 6. Create Telegram invite link
     │         │    Send to user
     │         ▼
     │    ┌──────────┐
     │    │   User   │──► 7. Joins private channel
     │    └──────────┘
     │
     │ 8. Enqueue to GCSplit1 (Payment Splitting)
     ▼
┌──────────────────────┐
│   GCSplit1-10-26     │
│   Orchestrator       │
└────┬─────────┬───────┘
     │         │
     │ 9. Enqueue to GCSplit2
     │         ▼
     │    ┌─────────────────┐
     │    │  GCSplit2-10-26 │
     │    │  USDT→ETH Est.  │──► 10. Call ChangeNow API
     │    └────┬────────────┘       Get estimate
     │         │
     │         │ 11. Return estimate
     │         ▼
     │    ┌──────────────────┐
     │    │  GCSplit1-10-26  │──► 12. Insert split_payout_request
     │    │  Orchestrator    │        (with pure market value)
     │    └────┬─────────────┘
     │         │
     │         │ 13. Enqueue to GCSplit3
     │         ▼
     │    ┌─────────────────┐
     │    │  GCSplit3-10-26 │
     │    │  ETH→Client     │──► 14. Create ChangeNow transaction
     │    └────┬────────────┘       Get payin_address
     │         │
     │         │ 15. Return transaction data
     │         ▼
     │    ┌──────────────────┐
     │    │  GCSplit1-10-26  │──► 16. Insert split_payout_que
     │    │  Orchestrator    │        (ChangeNow tx data)
     │    └────┬─────────────┘
     │         │
     │         │ 17. Enqueue to GCHostPay1
     │         ▼
     │    ┌──────────────────┐
     │    │ GCHostPay1-10-26 │
     │    │ Orchestrator     │──► 18. Check duplicates
     │    └────┬─────────────┘
     │         │
     │         │ 19. Enqueue to GCHostPay2
     │         ▼
     │    ┌──────────────────┐
     │    │ GCHostPay2-10-26 │
     │    │ Status Checker   │──► 20. Check ChangeNow status
     │    └────┬─────────────┘       (infinite retry)
     │         │
     │         │ 21. Return status="waiting"
     │         ▼
     │    ┌──────────────────┐
     │    │ GCHostPay1-10-26 │
     │    │ Orchestrator     │
     │    └────┬─────────────┘
     │         │
     │         │ 22. Enqueue to GCHostPay3
     │         ▼
     │    ┌──────────────────┐
     │    │ GCHostPay3-10-26 │
     │    │ ETH Executor     │──► 23. Send ETH to payin_address
     │    └────┬─────────────┘       (infinite retry)
     │         │
     │         │ 24. Write hostpay_transactions
     │         │     Return tx_hash
     │         ▼
     │    ┌──────────────────┐
     │    │ GCHostPay1-10-26 │
     │    │ Orchestrator     │──► 25. Log completion
     │    └──────────────────┘
     │
     │ 26. ChangeNow executes swap
     │     ETH → Client's desired currency
     │     Sends to client's wallet
     ▼
┌─────────────────┐
│ Channel Owner   │──► 27. Receives payment in their wallet
└─────────────────┘
```

### Subscription Expiration Flow

```
┌──────────────────────┐
│  TelePay10-26        │
│  Subscription Manager│
│  (60s monitoring)    │
└────┬─────────────────┘
     │
     │ Every 60 seconds
     ▼
┌─────────────────────────────────────────┐
│  Query private_channel_users_database   │
│  WHERE is_active = true                 │
│  AND expire_date/expire_time <= NOW     │
└────┬────────────────────────────────────┘
     │
     │ Found expired subscriptions
     ▼
┌─────────────────────────────────────────┐
│  For each expired subscription:         │
│  1. bot.ban_chat_member(user, channel)  │
│  2. bot.unban_chat_member(user)         │
│     (allows re-joining if they pay)     │
│  3. UPDATE is_active = false            │
└─────────────────────────────────────────┘
```

### Channel Registration Flow

```
┌──────────────┐
│ Channel Owner│
└────┬─────────┘
     │
     │ 1. Visit www.paygateprime.com
     ▼
┌──────────────────┐
│ GCRegister10-26  │
│ Registration Form│
└────┬─────────────┘
     │
     │ 2. Fill form:
     │    - open_channel_id, title, description
     │    - closed_channel_id, title, description
     │    - sub_1/2/3_price, sub_1/2/3_time
     │    - client_wallet_address
     │    - client_payout_currency, network
     │    - CAPTCHA answer
     │    - Tier count (1-3)
     ▼
┌─────────────────────────────────────────┐
│  Validate all fields                    │
│  - Channel IDs (≤14 chars)              │
│  - Titles (1-100 chars)                 │
│  - Descriptions (1-500 chars)           │
│  - Prices (positive decimals)           │
│  - Times (positive integers)            │
│  - Wallet address (10-200 chars)        │
│  - Currency (supported currency)        │
│  - Network (matches currency)           │
│  - CAPTCHA (correct answer)             │
└────┬────────────────────────────────────┘
     │
     │ 3. All valid
     ▼
┌─────────────────────────────────────────┐
│  INSERT INTO main_clients_database      │
│  (open_channel_id, titles, prices...)   │
└────┬────────────────────────────────────┘
     │
     │ 4. Success or duplicate error
     ▼
┌──────────────────┐
│  Success Page    │──► Channel registered!
│  or Error Page   │    Bot can now accept payments
└──────────────────┘
```

---

## Database Schema

### PostgreSQL Cloud SQL Database

#### Table: `main_clients_database`
**Purpose:** Channel configurations for all registered channels

```sql
CREATE TABLE main_clients_database (
    open_channel_id VARCHAR(14) PRIMARY KEY,  -- Public channel ID
    open_channel_title VARCHAR(100) NOT NULL,
    open_channel_description VARCHAR(500),
    closed_channel_id VARCHAR(14) NOT NULL,   -- Private channel ID
    closed_channel_title VARCHAR(100) NOT NULL,
    closed_channel_description VARCHAR(500),

    -- Subscription Tiers (nullable if not enabled)
    sub_1_price NUMERIC(10, 2),  -- Gold tier
    sub_1_time INTEGER,           -- Days
    sub_2_price NUMERIC(10, 2),  -- Silver tier
    sub_2_time INTEGER,
    sub_3_price NUMERIC(10, 2),  -- Bronze tier
    sub_3_time INTEGER,

    -- Payout Configuration
    client_wallet_address VARCHAR(200) NOT NULL,
    client_payout_currency VARCHAR(10) NOT NULL,
    client_payout_network VARCHAR(50) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Table: `private_channel_users_database`
**Purpose:** Active subscriptions (written by GCWebhook1)

```sql
CREATE TABLE private_channel_users_database (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,              -- Telegram user ID
    private_channel_id VARCHAR(14) NOT NULL,
    sub_price NUMERIC(10, 2) NOT NULL,    -- What they paid
    sub_time INTEGER NOT NULL,             -- Subscription duration (days)
    expire_time TIME NOT NULL,             -- Expiration time
    expire_date DATE NOT NULL,             -- Expiration date
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Composite index for expiration queries
    INDEX idx_active_expiration (is_active, expire_date, expire_time)
);
```

#### Table: `split_payout_request`
**Purpose:** Payment split requests (written by GCSplit1 after USDT→ETH estimate)

```sql
CREATE TABLE split_payout_request (
    unique_id VARCHAR(50) PRIMARY KEY,  -- UUID
    user_id BIGINT NOT NULL,
    closed_channel_id VARCHAR(14) NOT NULL,

    -- Conversion details
    from_currency VARCHAR(10) NOT NULL,  -- "usdt"
    to_currency VARCHAR(10) NOT NULL,    -- Client's desired currency
    from_network VARCHAR(50) NOT NULL,   -- "eth"
    to_network VARCHAR(50) NOT NULL,     -- Client's network

    from_amount NUMERIC(18, 8) NOT NULL,  -- USDT amount
    to_amount NUMERIC(18, 8) NOT NULL,    -- PURE MARKET VALUE in ETH

    client_wallet_address VARCHAR(200) NOT NULL,
    refund_address VARCHAR(200),
    flow VARCHAR(20) DEFAULT 'standard',
    type_ VARCHAR(20) DEFAULT 'direct',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Table: `split_payout_que`
**Purpose:** ChangeNow swap transactions (written by GCSplit1 after ETH→Client swap)

```sql
CREATE TABLE split_payout_que (
    id SERIAL PRIMARY KEY,
    unique_id VARCHAR(50) REFERENCES split_payout_request(unique_id),
    cn_api_id VARCHAR(100) NOT NULL,  -- ChangeNow transaction ID

    user_id BIGINT NOT NULL,
    closed_channel_id VARCHAR(14) NOT NULL,

    -- Swap details (from ChangeNow response)
    from_currency VARCHAR(10) NOT NULL,  -- "eth"
    to_currency VARCHAR(10) NOT NULL,    -- Client's currency
    from_network VARCHAR(50) NOT NULL,   -- "eth"
    to_network VARCHAR(50) NOT NULL,

    from_amount NUMERIC(18, 8) NOT NULL,  -- ETH to send
    to_amount NUMERIC(18, 8) NOT NULL,    -- Client receives

    payin_address VARCHAR(200) NOT NULL,  -- Where we send ETH
    payout_address VARCHAR(200) NOT NULL, -- Client's wallet
    refund_address VARCHAR(200),

    flow VARCHAR(20),
    type_ VARCHAR(20),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_unique_id (unique_id),
    INDEX idx_cn_api_id (cn_api_id)
);
```

#### Table: `hostpay_transactions`
**Purpose:** ETH payment execution logs (written by GCHostPay3 after successful transfer)

```sql
CREATE TABLE hostpay_transactions (
    id SERIAL PRIMARY KEY,
    unique_id VARCHAR(50) NOT NULL,
    cn_api_id VARCHAR(100) NOT NULL,

    from_currency VARCHAR(10) NOT NULL,
    from_network VARCHAR(50) NOT NULL,
    from_amount NUMERIC(18, 8) NOT NULL,
    payin_address VARCHAR(200) NOT NULL,

    is_complete BOOLEAN DEFAULT FALSE,

    -- Ethereum transaction details
    tx_hash VARCHAR(66),            -- 0x + 64 hex chars
    tx_status VARCHAR(20),          -- "success" / "failed"
    gas_used INTEGER,
    block_number INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_unique_id (unique_id),
    INDEX idx_tx_hash (tx_hash)
);
```

#### Table: `currency_to_network_supported_mappings`
**Purpose:** Supported currency/network combinations for registration form

```sql
CREATE TABLE currency_to_network_supported_mappings (
    id SERIAL PRIMARY KEY,
    currency VARCHAR(10) NOT NULL,
    network VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,

    UNIQUE(currency, network)
);
```

---

## Security & Authentication

### Token-Based Authentication

All inter-service communication uses encrypted, signed tokens.

#### Token Structure
```
┌─────────────────────────────────────────────────┐
│           Binary Packed Data                    │
├─────────────────────────────────────────────────┤
│  - Field 1 (fixed or length-prefixed)          │
│  - Field 2 (fixed or length-prefixed)          │
│  - ...                                          │
│  - Timestamp (4 bytes, uint32)                  │
├─────────────────────────────────────────────────┤
│  HMAC-SHA256 Signature (16 bytes, truncated)   │
└─────────────────────────────────────────────────┘
        ↓ Base64 URL-safe encoding
    Final Token String
```

#### Signing Keys

- **SUCCESS_URL_SIGNING_KEY**: Used for internal services (GCWebhook, GCSplit)
- **TPS_HOSTPAY_SIGNING_KEY**: Used for GCSplit → GCHostPay communication

#### Token Flows

1. **GCWebhook1 → GCWebhook2**
   - Key: SUCCESS_URL_SIGNING_KEY
   - Data: user_id, closed_channel_id, subscription details

2. **GCWebhook1 → GCSplit1**
   - Key: SUCCESS_URL_SIGNING_KEY (HMAC signature in header)
   - Data: user_id, wallet_address, payment details

3. **GCSplit1 ↔ GCSplit2/3**
   - Key: SUCCESS_URL_SIGNING_KEY
   - Data: user_id, amounts, addresses

4. **GCSplit1 → GCHostPay1**
   - Key: TPS_HOSTPAY_SIGNING_KEY
   - Data: unique_id, cn_api_id, payin_address, amounts

5. **GCHostPay1 ↔ GCHostPay2/3**
   - Key: SUCCESS_URL_SIGNING_KEY
   - Data: unique_id, payment details, status

### Secret Manager Configuration

All sensitive data stored in Google Secret Manager:

```
projects/{PROJECT_ID}/secrets/{SECRET_NAME}/versions/latest
```

**Secrets:**
- `TELEGRAM_BOT_SECRET_NAME` - Telegram bot token
- `TELEGRAM_BOT_USERNAME` - Bot username
- `NOWPAYMENT_WEBHOOK_KEY` - NOWPayments webhook key
- `SUCCESS_URL_SIGNING_KEY` - Internal token signing
- `TPS_HOSTPAY_SIGNING_KEY` - HostPay token signing
- `CHANGENOW_API_KEY` - ChangeNow API key
- `HOST_WALLET_ADDRESS` - ETH wallet address
- `HOST_WALLET_PRIVATE_KEY` - ETH wallet private key
- `ETHEREUM_RPC_URL` - Alchemy RPC endpoint
- `ETHEREUM_RPC_URL_API` - Alchemy API key
- Database credentials (instance, name, user, password)

---

## Emoji Patterns Reference

All services use consistent emoji patterns for logging:

| Emoji | Meaning | Usage |
|-------|---------|-------|
| 🚀 | Startup/Launch | Service initialization |
| ✅ | Success | Operation completed successfully |
| ❌ | Error/Failure | Operation failed |
| 💾 | Database | Database operations |
| 👤 | User | User-related operations |
| 💰 | Money/Payment | Payment amounts, transactions |
| 🏦 | Wallet/Banking | Wallet addresses, bank operations |
| 🌐 | Network/API | API calls, network operations |
| 🎯 | Endpoint | Endpoint receiving request |
| 📦 | Data/Payload | Data payloads, packages |
| 🆔 | IDs | Unique identifiers |
| 📨 | Messaging | Sending messages, invites |
| 🔐 | Security/Encryption | Token encryption, signatures |
| 🕐 | Time | Time-related operations |
| 🔍 | Search/Finding | Database queries, searches |
| 📝 | Writing/Logging | Writing to logs, database |
| ⚠️ | Warning | Non-critical issues |
| 🎉 | Completion | Workflow completion |
| 🔄 | Retry | Retry attempts |
| 📊 | Status/Statistics | Status checks, metrics |
| 🔗 | Links/Connections | Hyperlinks, connections |
| ⛽ | Gas | Ethereum gas fees |
| 📅 | Date/Time | Date/time calculations |
| 💸 | Fee | Fee calculations |
| 🧮 | Calculation | Mathematical operations |
| 🏢 | Channel | Telegram channels |

### Example Log Output

```
🚀 [APP] Initializing GCHostPay3-10-26 ETH Payment Executor Service
✅ [APP] Token manager initialized
✅ [APP] Wallet manager initialized
✅ [APP] Database manager initialized
🎯 [ENDPOINT] Payment execution request received (from GCHostPay1)
✅ [ENDPOINT] Token decoded successfully
🆔 [ENDPOINT] Unique ID: abc123-def456
🆔 [ENDPOINT] CN API ID: cn_xyz789
💰 [ENDPOINT] Amount: 0.05 ETH
🏦 [ENDPOINT] Payin Address: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
💰 [ENDPOINT] Executing ETH payment with infinite retry
✅ [ENDPOINT] ETH payment executed successfully
🔗 [ENDPOINT] TX Hash: 0xabc...123
📊 [ENDPOINT] TX Status: success
⛽ [ENDPOINT] Gas Used: 21000
📦 [ENDPOINT] Block Number: 12345678
✅ [ENDPOINT] Database: Successfully logged payment
```

---

## Deployment Architecture

### Google Cloud Platform Services

```
┌─────────────────────────────────────────────────────────────────┐
│                      Google Cloud Platform                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │               Cloud Run (10 Services)                      │  │
│  │                                                             │  │
│  │  TelePay10-26 (polling)                                    │  │
│  │  GCRegister10-26 (HTTP:8080)                               │  │
│  │  GCWebhook1-10-26 (HTTP:8080)                              │  │
│  │  GCWebhook2-10-26 (HTTP:8080)                              │  │
│  │  GCSplit1-10-26 (HTTP:8080)                                │  │
│  │  GCSplit2-10-26 (HTTP:8080)                                │  │
│  │  GCSplit3-10-26 (HTTP:8080)                                │  │
│  │  GCHostPay1-10-26 (HTTP:8080)                              │  │
│  │  GCHostPay2-10-26 (HTTP:8080)                              │  │
│  │  GCHostPay3-10-26 (HTTP:8080)                              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Cloud Tasks (10+ Queues)                      │  │
│  │                                                             │  │
│  │  gcwebhook-telegram-invite-queue                           │  │
│  │  gcsplit-usdt-eth-estimate-queue                           │  │
│  │  gcsplit-usdt-eth-response-queue                           │  │
│  │  gcsplit-eth-client-swap-queue                             │  │
│  │  gcsplit-eth-client-response-queue                         │  │
│  │  gcsplit-hostpay-trigger-queue                             │  │
│  │  gchostpay-status-check-queue                              │  │
│  │  gchostpay-payment-exec-queue                              │  │
│  │  gchostpay1-response-queue                                 │  │
│  │  ...                                                        │  │
│  │                                                             │  │
│  │  Config: 60s fixed backoff, infinite retry, 24h max        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Cloud SQL (PostgreSQL 14)                     │  │
│  │                                                             │  │
│  │  main_clients_database                                     │  │
│  │  private_channel_users_database                            │  │
│  │  split_payout_request                                      │  │
│  │  split_payout_que                                          │  │
│  │  hostpay_transactions                                      │  │
│  │  currency_to_network_supported_mappings                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Secret Manager                                │  │
│  │                                                             │  │
│  │  20+ secrets for API keys, tokens, credentials            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Cloud DNS                                     │  │
│  │                                                             │  │
│  │  www.paygateprime.com → GCRegister10-26                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Deployment Scripts

Located in `/OCTOBER/10-26/`:

- **`deploy_gcsplit_tasks_queues.sh`** - Deploys GCSplit queues
- **`deploy_gcwebhook_tasks_queues.sh`** - Deploys GCWebhook queues
- **`deploy_hostpay_tasks_queues.sh`** - Deploys GCHostPay queues

### Docker Deployment

Each service has a `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "service_name.py"]
```

---

## Monitoring & Operations

### Health Checks

All HTTP services expose `GET /health` endpoint:

```json
{
  "status": "healthy",
  "service": "ServiceName",
  "timestamp": 1234567890,
  "components": {
    "token_manager": "healthy",
    "database": "healthy",
    "cloudtasks": "healthy"
  }
}
```

### Logging Strategy

All logs use emoji-prefixed format for easy filtering:

```
🚀 [COMPONENT] Log message
✅ [COMPONENT] Success message
❌ [COMPONENT] Error message
```

Filter by component:
```bash
gcloud logging read "resource.type=cloud_run_revision AND textPayload:\"[ENDPOINT]\""
```

Filter by emoji:
```bash
gcloud logging read "resource.type=cloud_run_revision AND textPayload:\"❌\""
```

### Retry Monitoring

Monitor Cloud Tasks retry behavior:

```bash
gcloud tasks queues describe QUEUE_NAME --location=LOCATION
```

Check task backlog:
```bash
gcloud tasks queues list --location=LOCATION
```

### Database Connection Pooling

All services use context managers for connection management:

```python
with db_manager.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT ...")
        # Connection automatically closed on exit
```

---

## Notes

- All monetary values use NUMERIC type for precision
- All tokens are encrypted with HMAC-SHA256 signatures
- All services retry infinitely (60s backoff, 24h max)
- All database writes use transactions
- All event loops are isolated per-request (Cloud Run compatibility)
- All sensitive data stored in Secret Manager
- All services log with emoji patterns for consistency

---

**Document Version:** 1.0
**Last Review:** 2025-10-28
**Next Review:** 2025-11-28
