# PGP_MAP_UPDATED.md - PayGatePrime Complete Architecture & Deployment Guide

**Project:** PayGatePrime (PGP) - Telegram Cryptocurrency Payment Gateway
**Version:** 2.0
**Last Updated:** 2025-11-18
**Target Project:** pgp-live (GCP Project ID: pgp-live)
**Database:** pgp-live-psql (PostgreSQL instance)
**Active Services:** 15 microservices + 1 shared library

---

## 📋 EXECUTIVE SUMMARY

**PayGatePrime** is a production-ready Telegram-based cryptocurrency payment gateway that enables channel owners to monetize their Telegram channels through subscriptions and donations. The system processes payments via NOWPayments API, manages user subscriptions, handles automated payouts through multi-stage conversion pipelines, and provides comprehensive channel management tools.

### Architecture Overview

- **15 Active Microservices** deployed on Google Cloud Run
- **1 Shared Library (PGP_COMMON)** reducing code duplication by 60%
- **PostgreSQL Database** (Cloud SQL) with 15 tables
- **17 Cloud Tasks Queues** for async processing
- **2 Cloud Scheduler Jobs** for batch processing
- **Event-Driven Architecture** with retry resilience
- **Hot-Reload Configuration** via Secret Manager (75+ secrets)

### Key Capabilities

✅ **Subscription Management** - Automated tier-based subscriptions with expiration tracking
✅ **Donation Processing** - Direct cryptocurrency donations to channel owners
✅ **Multi-Currency Support** - ETH, USDT, BTC, and 150+ cryptocurrencies
✅ **Automated Payouts** - Batch and micro-batch processing with threshold detection
✅ **Broadcast System** - Scheduled and manual broadcasts to subscribers
✅ **Security Hardened** - HMAC authentication, IP whitelisting, rate limiting, Redis nonce tracking
✅ **High Availability** - Serverless Cloud Run with auto-scaling (0-100 instances)
✅ **Cost Optimized** - Scales to zero, pay-per-use pricing model

---

## 🗺️ QUICK REFERENCE MAP

### Service Categories at a Glance

```
┌──────────────────────────────────────────────────────────────────┐
│                  PAYGATEPRIME ARCHITECTURE                       │
│                     15 Active Services                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🤖 USER INTERFACE LAYER (2 services)                            │
│  ├─ PGP_SERVER_v1         → Telegram bot & webhook server       │
│  └─ PGP_WEBAPI_v1         → REST API for channel registration   │
│                                                                  │
│  💳 PAYMENT PROCESSING (3 services)                              │
│  ├─ PGP_NP_IPN_v1         → NOWPayments IPN webhook handler     │
│  ├─ PGP_ORCHESTRATOR_v1   → Payment processor & orchestrator    │
│  └─ PGP_INVITE_v1         → Telegram invite link sender         │
│                                                                  │
│  💰 PAYOUT PIPELINE (6 services)                                 │
│  ├─ PGP_SPLIT1_v1         → Split orchestrator                  │
│  ├─ PGP_SPLIT2_v1         → USDT→ETH estimator                  │
│  ├─ PGP_SPLIT3_v1         → ETH→Client currency swapper         │
│  ├─ PGP_HOSTPAY1_v1       → Payment validator & orchestrator    │
│  ├─ PGP_HOSTPAY2_v1       → ChangeNow status checker            │
│  └─ PGP_HOSTPAY3_v1       → ETH payment executor                │
│                                                                  │
│  ⏰ SCHEDULED PROCESSORS (2 services)                            │
│  ├─ PGP_BATCHPROCESSOR_v1      → Batch payout (every 5min)     │
│  └─ PGP_MICROBATCHPROCESSOR_v1 → Micro-batch (every 15min)     │
│                                                                  │
│  📢 COMMUNICATIONS (2 services)                                  │
│  ├─ PGP_NOTIFICATIONS_v1  → Payment notifications               │
│  └─ PGP_BROADCAST_v1      → Broadcast scheduler/executor        │
│                                                                  │
│  📚 SHARED INFRASTRUCTURE                                        │
│  └─ PGP_COMMON            → Base classes & utilities            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Critical Path Data Flow

```
User Payment Flow:
──────────────────
User → Telegram Bot (PGP_SERVER_v1)
    ↓
NOWPayments Payment Gateway
    ↓
IPN Webhook (PGP_NP_IPN_v1) → Updates payment_id
    ↓
Success Callback → PGP_ORCHESTRATOR_v1
    ├→ PGP_INVITE_v1 (send Telegram invite)
    ├→ PGP_NOTIFICATIONS_v1 (notify channel owner)
    └→ Inline Accumulation (threshold detection)

Scheduled Payout Flow:
─────────────────────
Cloud Scheduler (every 15min) → PGP_MICROBATCHPROCESSOR_v1
    ↓
ETH→USDT Conversion (if threshold ≥ $5 USD)
    ↓
Cloud Scheduler (every 5min) → PGP_BATCHPROCESSOR_v1
    ↓
Threshold Detection (if balance ≥ $50 USD)
    ↓
Payout Pipeline: SPLIT1 → SPLIT2 → SPLIT3 → HOSTPAY1 → HOSTPAY2 → HOSTPAY3
    ↓
Final Payment to Channel Owner's Wallet
```

---

## 📖 DETAILED SERVICE DESCRIPTIONS

### 🤖 USER INTERFACE LAYER

---

#### PGP_SERVER_v1
**Telegram Bot & Application Server**

**Location:** `/PGP_SERVER_v1/`
**Entry Point:** `pgp_server_v1.py`
**Port:** 5000 (Flask)
**Deployment:** Cloud Run (1Gi RAM, 1-20 instances)

**Purpose:**
The central user-facing service that runs the Telegram bot and coordinates all bot interactions. This is the primary interface through which users interact with PayGatePrime to purchase subscriptions, make donations, and manage their accounts.

**Why It Exists:**
Users need a conversational interface to interact with the payment system. Telegram bots provide this interface while maintaining security, ease of use, and wide accessibility across mobile and desktop platforms.

**Critical Unique Functions:**
1. **Telegram Bot Management** - Handles all bot commands (`/start`, `/donate`, `/help`, etc.)
2. **Subscription Expiration Monitoring** - Runs background task every 5 minutes to detect and remove expired users from channels
3. **Donation Conversation Flow** - Manages multi-step donation input workflows with keypad state tracking
4. **Payment Link Generation** - Creates NOWPayments payment links with encrypted tokens
5. **Invite Link Distribution** - Generates and sends one-time Telegram invite links after payment
6. **Flask Webhook Server** - Receives callbacks from PGP_ORCHESTRATOR_v1 and external services
7. **Security Services** - HMAC authentication, IP whitelisting, rate limiting for all webhook endpoints

**Key Components:**
- `app_initializer.py` - Application initialization and dependency injection
- `server_manager.py` - Flask server and webhook endpoint management
- `bot/` - Telegram bot handlers, conversations, and command processing
- `models/connection_pool.py` - Database connection pooling with Cloud SQL Connector
- `services/payment_service.py` - Payment link creation and validation
- `services/notification_service.py` - Notification delivery coordination
- `security/` - HMAC signature verification, IP whitelisting, rate limiting middleware

**Dependencies:**
- Extends PGP_COMMON base classes (BaseConfigManager, BaseDatabaseManager)
- Receives webhooks from PGP_ORCHESTRATOR_v1 (payment confirmations)
- Sends requests to PGP_NOTIFICATIONS_v1 (manual notifications)
- Connects to PostgreSQL via Cloud SQL Connector
- python-telegram-bot library for Telegram Bot API
- Flask for webhook server

**Scalability:** Handles concurrent users via asyncio event loop, horizontal scaling via Cloud Run

---

#### PGP_WEBAPI_v1
**REST API Backend for Channel Registration**

**Location:** `/PGP_WEBAPI_v1/`
**Entry Point:** `pgp_webapi_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (4 CPU, 8Gi RAM, 0-10 instances) - **Customer-facing service**

**Purpose:**
Provides a stateless REST API backend for channel registration, authentication, channel management, and account operations. This is the primary interface for channel owners to register and configure their channels. Currently operates as a **standalone API service** (no frontend exists - PGP_WEB_v1 was removed as ghost service).

**Why It Exists:**
Channel owners need a programmatic interface to register channels, configure subscription tiers, set payout wallets, and manage their accounts. This service provides that interface with JWT-based authentication, CORS support for future frontend integration, and comprehensive API endpoints. Can be called directly via API clients (Postman, curl, etc.) or integrated with a future frontend.

**Critical Unique Functions:**
1. **JWT Authentication** - Stateless token-based auth (15min access tokens, 30-day refresh tokens)
2. **User Registration** - Email-based account creation with SendGrid email verification
3. **Channel Registration** - Telegram channel validation and registration (verifies bot admin status)
4. **Subscription Tier Management** - CRUD operations for pricing tiers (monthly, quarterly, yearly)
5. **Payout Configuration** - Wallet address validation and storage (ETH, USDT, BTC)
6. **Email Services** - SendGrid integration for welcome emails, password resets, notifications
7. **Rate Limiting** - Token bucket algorithm to prevent API abuse

**Key Components:**
- `api/routes/auth.py` - Registration, login, token refresh endpoints
- `api/routes/account.py` - Account management, password reset, email verification
- `api/routes/channels.py` - Channel CRUD operations, validation, status management
- `api/routes/mappings.py` - Subscription tier and payout wallet mapping operations
- `api/middleware/rate_limiter.py` - Rate limiting middleware (100 requests/15min per IP)
- `api/services/email_service.py` - SendGrid email delivery service
- `config_manager.py` - Secret Manager integration for API keys

**Dependencies:**
- Extends PGP_COMMON base classes (BaseConfigManager, BaseDatabaseManager)
- Connects to PostgreSQL database for user and channel data
- SendGrid for email delivery (welcome, verification, password reset)
- Flask-JWT-Extended for JWT token management
- Flask-CORS for cross-origin request handling

**Resource Allocation:**
**🔴 CRITICAL:** This service handles customer-facing API traffic and requires **4 CPU, 8GB RAM** to handle up to **1000 requests/minute** during peak load. Memory-intensive operations include JWT token generation, database queries, and email template rendering.

**Scalability:** Auto-scales 0-10 instances based on traffic, supports 1000+ concurrent API requests

---

### 💳 PAYMENT PROCESSING LAYER

---

#### PGP_NP_IPN_v1
**NOWPayments IPN Webhook Handler**

**Location:** `/PGP_NP_IPN_v1/`
**Entry Point:** `pgp_np_ipn_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-20 instances)

**Purpose:**
Receives Instant Payment Notification (IPN) callbacks from NOWPayments API when payment status changes occur. Updates the database with critical payment metadata including payment_id, outcome_amount, actual_price_usd, and payment status.

**Why It Exists:**
NOWPayments sends two separate callbacks: (1) IPN with payment_id and metadata, and (2) success_url redirect with user info. These IPNs arrive asynchronously and contain critical payment tracking information needed to reconcile payments in NOWPayments' system. This service handles the IPN callback, while PGP_ORCHESTRATOR_v1 handles the success_url callback.

**Critical Unique Functions:**
1. **IPN Signature Verification** - Validates HMAC-SHA512 signatures from NOWPayments using IPN secret key
2. **Payment ID Storage** - Updates `processed_payments` table with NOWPayments payment_id
3. **Payment Status Tracking** - Records payment status changes (waiting, confirming, confirmed, finished, failed)
4. **Payment Metadata Storage** - Stores outcome_amount, actual_price_usd, price_amount, price_currency
5. **Payment Processing Page** - Serves payment-processing.html page shown during payment flow
6. **Payment Status API** - Provides GET endpoint for frontend to check payment status by unique_id
7. **Fallback Pricing** - Uses CryptoPricingClient to calculate USD values when missing from IPN

**Key Components:**
- **POST /** - Main IPN webhook endpoint (receives NOWPayments IPNs)
- **GET /payment-processing** - Serves payment processing HTML page
- **GET /api/payment-status/:unique_id** - Payment status query API
- `database_manager.py` - Database operations for payment updates
- SHA-512 signature verification (PGP_COMMON.utils.webhook_auth)
- CryptoPricingClient for fallback pricing (PGP_COMMON.utils.crypto_pricing)

**Dependencies:**
- Uses PGP_COMMON utilities (verify_sha512_signature, CryptoPricingClient)
- Connects to PostgreSQL database (updates processed_payments table)
- Receives IPNs from NOWPayments external webhook
- Must be publicly accessible via Load Balancer + Cloud Armor

**Security:**
HMAC-SHA512 signature verification ensures IPNs are authentic. Cloud Armor rate limiting prevents DDoS. Service runs in authenticated mode with Load Balancer handling external access.

---

#### PGP_ORCHESTRATOR_v1
**Payment Success Processor & Task Orchestrator**

**Location:** `/PGP_ORCHESTRATOR_v1/`
**Entry Point:** `pgp_orchestrator_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-20 instances)

**Purpose:**
Receives success_url callbacks from NOWPayments after successful payment, decrypts payment data, writes to database, calculates subscription expiration, and orchestrates downstream tasks via Cloud Tasks. This is the **central orchestrator** for all post-payment workflows.

**Why It Exists:**
After successful payment, multiple coordinated actions must occur: (1) record payment in database, (2) send Telegram invite to user, (3) notify channel owner, (4) accumulate funds for payout. This service orchestrates all these workflows while maintaining transaction integrity and retry resilience through Cloud Tasks.

**Critical Unique Functions:**
1. **Success URL Token Decryption** - Decrypts and validates success_url tokens from NOWPayments
2. **Payment Recording** - Writes payment records to `processed_payments` table with full metadata
3. **Subscription Expiration Calculation** - Calculates expire_time (Unix timestamp) and expire_date (ISO 8601)
4. **Inline Accumulation** - Calculates TelePay 3% fee and writes to `payout_accumulation` table (replaces old PGP_ACCUMULATOR_v1 service)
5. **Task Orchestration** - Enqueues Cloud Tasks to downstream services:
   - `pgp-invite-v1-queue` → PGP_INVITE_v1 (send Telegram invite)
   - `pgp-notifications-v1-queue` → PGP_NOTIFICATIONS_v1 (notify channel owner)
6. **Token Encryption** - Creates encrypted HMAC-signed tokens for secure inter-service communication
7. **Idempotency Handling** - Prevents duplicate payment processing via unique_id tracking

**Key Components:**
- **POST /** - Main success_url webhook endpoint (receives NOWPayments success callbacks)
- **GET /health** - Health check endpoint for monitoring
- `database_manager.py` - Database operations (payment insertion, accumulation)
- `cloudtasks_client.py` - Cloud Tasks queue management (extends BaseCloudTasksClient)
- `token_manager.py` - Token encryption/decryption (extends BaseTokenManager)
- Inline accumulation logic (52 lines, replaces entire PGP_ACCUMULATOR_v1 service)

**Dependencies:**
- Uses PGP_COMMON for base classes and utilities
- Connects to PostgreSQL database (processed_payments, payout_accumulation tables)
- Creates tasks in Cloud Tasks queues:
  - `pgp-invite-v1-queue` (Cloud Tasks → PGP_INVITE_v1)
  - `pgp-notifications-v1-queue` (Cloud Tasks → PGP_NOTIFICATIONS_v1)
- Receives success_url callbacks from NOWPayments (must be publicly accessible)

**Architecture Note:**
🔴 **IMPORTANT:** PGP_ACCUMULATOR_v1 service was **REMOVED** on 2025-11-18. Accumulation logic moved inline to this service (lines 388-440) for performance. This eliminates ~200-300ms Cloud Task overhead and saves ~$20/month. Database method centralized to `BaseDatabaseManager.insert_payout_accumulation_pending()` in PGP_COMMON.

**See:** `THINK/AUTO/PGP_THRESHOLD_REVIEW.md`, `PROGRESS.md` (2025-11-18), `DECISIONS.md` (Decision 13.1)

---

#### PGP_INVITE_v1
**Telegram Invite Link Sender**

**Location:** `/PGP_INVITE_v1/`
**Entry Point:** `pgp_invite_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-10 instances)

**Purpose:**
Receives encrypted tokens from PGP_ORCHESTRATOR_v1 via Cloud Tasks, generates one-time Telegram invite links using Telegram Bot API, validates payment amounts, and sends invite links to users via direct message.

**Why It Exists:**
After payment confirmation, users need to be added to the private Telegram channel they subscribed to. This service handles the invitation process with retry logic, payment validation, and error handling to ensure users receive access after successful payment.

**Critical Unique Functions:**
1. **Token Decryption** - Decrypts HMAC-signed payment tokens from PGP_ORCHESTRATOR_v1
2. **Invite Link Generation** - Creates one-time Telegram invite links using `create_chat_invite_link()` API
3. **Payment Validation** - Verifies payment amounts against subscription tier prices before sending invite
4. **Direct Message Sending** - Sends invite links to users via Telegram direct message
5. **Event Loop Management** - Uses `asyncio.run()` for isolated event loops optimized for Cloud Run serverless
6. **Infinite Retry** - Cloud Tasks retry with 60s exponential backoff for Telegram API failures

**Key Components:**
- **POST /** - Main webhook endpoint (receives Cloud Tasks from PGP_ORCHESTRATOR_v1)
- **GET /health** - Health check endpoint
- `config_manager.py` - Secret Manager integration for Telegram bot token
- `database_manager.py` - Payment validation queries
- Telegram Bot instance (created per-request, destroyed after completion)
- Token decryption (PGP_COMMON.tokens.BaseTokenManager)

**Dependencies:**
- Uses PGP_COMMON for base classes (BaseConfigManager, BaseDatabaseManager, BaseTokenManager)
- Connects to PostgreSQL database for payment validation
- python-telegram-bot library (Telegram Bot API client)
- Triggered by Cloud Tasks from PGP_ORCHESTRATOR_v1
- Requires Telegram bot to be admin in target channel

**Architecture Note:**
Uses **SYNCHRONOUS Flask route** with `asyncio.run()` to create isolated event loops for each request. This prevents "Event loop is closed" errors in serverless Cloud Run environments where event loops cannot be shared across requests.

**Error Handling:**
Cloud Tasks infinite retry ensures invites are sent even if Telegram API is temporarily unavailable. Logs all failures for manual investigation.

---

### 💰 PAYOUT PIPELINE (6-Service Multi-Stage Pipeline)

---

#### PGP_SPLIT1_v1
**Payment Splitting Orchestrator**

**Location:** `/PGP_SPLIT1_v1/`
**Entry Point:** `pgp_split1_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-15 instances)

**Purpose:**
Orchestrates the multi-stage payment splitting workflow across PGP_SPLIT2_v1 (USDT→ETH estimation) and PGP_SPLIT3_v1 (ETH→ClientCurrency swap creation). Manages database state transitions through the `split_payout_que` table and coordinates final payment execution via PGP_HOSTPAY1_v1.

**Why It Exists:**
The payout pipeline requires coordination between multiple services with complex dependencies: (1) estimate USDT→ETH conversion, (2) create ETH→ClientCurrency swap, (3) validate ChangeNow status, (4) execute ETH payment. This orchestrator manages the workflow, handles callbacks, and maintains state consistency across the multi-step process.

**Critical Unique Functions:**
1. **Workflow Orchestration** - Coordinates 3-stage USDT→ETH→ClientCurrency conversion pipeline
2. **State Management** - Updates `split_payout_que` table through workflow stages (pending → estimating → swapping → executing → completed)
3. **Token Encryption** - Creates HMAC-signed encrypted tokens for inter-service communication
4. **Callback Handling** - Receives and processes callbacks from PGP_SPLIT2_v1 (estimate) and PGP_SPLIT3_v1 (swap)
5. **Batch Data Retrieval** - Queries `batch_conversions` table for ChangeNow exchange_id and swap details
6. **Error Recovery** - Handles retry logic and failure states with Cloud Tasks exponential backoff
7. **Final Execution Queue** - Enqueues tasks to PGP_HOSTPAY1_v1 after swap creation success

**Endpoints:**
- **POST /** - Initial payment split request (triggered by PGP_BATCHPROCESSOR_v1)
- **POST /pgp-split2-callback** - ETH estimate callback (from PGP_SPLIT2_v1)
- **POST /pgp-split3-callback** - Swap creation callback (from PGP_SPLIT3_v1)
- **GET /health** - Health check endpoint

**Workflow Stages:**
```
1. Receive batch from PGP_BATCHPROCESSOR_v1
2. Query batch_conversions for ChangeNow exchange_id
3. Enqueue PGP_SPLIT2_v1 for USDT→ETH estimate
4. [CALLBACK] Receive estimate from PGP_SPLIT2_v1
5. Update split_payout_que with estimated_eth_amount
6. Enqueue PGP_SPLIT3_v1 for ETH→ClientCurrency swap
7. [CALLBACK] Receive swap details from PGP_SPLIT3_v1
8. Update split_payout_que with swap_id, payin_address
9. Enqueue PGP_HOSTPAY1_v1 for final payment execution
```

**Dependencies:**
- Uses PGP_COMMON for base classes (BaseConfigManager, BaseDatabaseManager, BaseCloudTasksClient, BaseTokenManager)
- Connects to PostgreSQL database (split_payout_que, batch_conversions tables)
- Creates tasks in Cloud Tasks queues:
  - `pgp-split2-v1-queue` → PGP_SPLIT2_v1 (estimate)
  - `pgp-split3-v1-queue` → PGP_SPLIT3_v1 (swap)
  - `pgp-hostpay1-v1-queue` → PGP_HOSTPAY1_v1 (payment)
- Receives callbacks from PGP_SPLIT2_v1 and PGP_SPLIT3_v1

**State Diagram:**
```
pending → estimating → swapping → executing → completed
                ↓           ↓           ↓
              failed     failed     failed
```

---

#### PGP_SPLIT2_v1
**USDT→ETH Estimator Service**

**Location:** `/PGP_SPLIT2_v1/`
**Entry Point:** `pgp_split2_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-15 instances)

**Purpose:**
Receives encrypted tokens from PGP_SPLIT1_v1 via Cloud Tasks, calls ChangeNow API v2 for USDT→ETH exchange rate estimates, validates responses, encrypts results, and returns them via callback Cloud Task to PGP_SPLIT1_v1.

**Why It Exists:**
Before creating a ChangeNow swap transaction, we need to estimate how much ETH we'll receive for our USDT balance. This service isolates the estimation logic with infinite retry resilience for ChangeNow API failures, preventing the entire payout pipeline from failing due to temporary API issues.

**Critical Unique Functions:**
1. **Token Decryption** - Decrypts HMAC-signed request tokens from PGP_SPLIT1_v1
2. **ChangeNow Estimate API** - Calls `/v2/exchange/estimated-amount` endpoint with from_currency=USDT, to_currency=ETH
3. **Estimate Validation** - Validates API response structure and estimated_amount field
4. **Hot-Reload API Key** - Fetches ChangeNow API key from Secret Manager on-demand (config hot-reload)
5. **Token Encryption** - Creates encrypted response tokens with estimated_eth_amount
6. **Callback Queue** - Enqueues Cloud Task back to PGP_SPLIT1_v1 callback endpoint
7. **Infinite Retry** - Cloud Tasks retry with 60s exponential backoff for API failures

**Key Components:**
- **POST /** - Main estimate endpoint (receives Cloud Tasks from PGP_SPLIT1_v1)
- **GET /health** - Health check endpoint
- `cloudtasks_client.py` - Cloud Tasks client for callbacks (extends BaseCloudTasksClient)
- `token_manager.py` - Token encryption/decryption (extends BaseTokenManager)
- ChangeNowClient integration (PGP_COMMON.utils.changenow_client) - hot-reload enabled
- Estimate validation logic

**Dependencies:**
- Uses PGP_COMMON for base classes and ChangeNowClient
- ChangeNow API v2 (external REST API)
- Creates tasks in `pgp-split1-v1-callback-queue` (callbacks to PGP_SPLIT1_v1)
- Triggered by Cloud Tasks from PGP_SPLIT1_v1

**API Integration:**
```python
# ChangeNow API v2 Estimate Request
GET https://api.changenow.io/v2/exchange/estimated-amount
    ?fromCurrency=usdt
    &toCurrency=eth
    &fromAmount={usdt_amount}
    &fromNetwork=eth
    &toNetwork=eth
    &type=fixed

# Response: { "estimatedAmount": "0.025", "toAmount": "0.025", ... }
```

**Error Handling:**
All ChangeNow API errors trigger Cloud Tasks retry. Service logs errors but does not mark transactions as failed - retry continues until success or manual intervention.

---

#### PGP_SPLIT3_v1
**ETH→ClientCurrency Swap Creator**

**Location:** `/PGP_SPLIT3_v1/`
**Entry Point:** `pgp_split3_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-15 instances)

**Purpose:**
Receives encrypted tokens from PGP_SPLIT1_v1 via Cloud Tasks, creates ChangeNow fixed-rate swap transactions for ETH→ClientCurrency conversions (e.g., ETH→BTC, ETH→USDT), captures transaction details (swap_id, payin_address, payinExtraId), and returns encrypted responses with full transaction metadata.

**Why It Exists:**
After estimating ETH amount from SPLIT2, we need to create the actual swap transaction with the client's payout address and desired currency. This service handles swap creation with infinite retry resilience, ensuring swaps are created even if ChangeNow API is temporarily unavailable.

**Critical Unique Functions:**
1. **Token Decryption** - Decrypts HMAC-signed swap request tokens from PGP_SPLIT1_v1
2. **ChangeNow Fixed-Rate Swap** - Creates swap transaction via `/v2/exchange` endpoint with fixed-rate pricing
3. **Transaction Recording** - Returns swap_id, payin_address, payinExtraId, payoutAddress to orchestrator
4. **Hot-Reload API Key** - Fetches ChangeNow API key from Secret Manager on-demand (config hot-reload)
5. **Token Encryption** - Creates encrypted response with full transaction details
6. **Callback Queue** - Enqueues Cloud Task back to PGP_SPLIT1_v1 callback endpoint
7. **Infinite Retry** - Cloud Tasks retry with 60s exponential backoff for API failures

**Key Components:**
- **POST /** - Main swap creation endpoint (receives Cloud Tasks from PGP_SPLIT1_v1)
- **GET /health** - Health check endpoint
- `cloudtasks_client.py` - Cloud Tasks client for callbacks (extends BaseCloudTasksClient)
- `token_manager.py` - Token encryption/decryption (extends BaseTokenManager)
- ChangeNowClient integration (PGP_COMMON.utils.changenow_client) - hot-reload enabled
- Swap validation logic

**Dependencies:**
- Uses PGP_COMMON for base classes and ChangeNowClient
- ChangeNow API v2 (external REST API)
- Creates tasks in `pgp-split1-v1-callback-queue` (callbacks to PGP_SPLIT1_v1)
- Triggered by Cloud Tasks from PGP_SPLIT1_v1

**API Integration:**
```python
# ChangeNow API v2 Swap Request
POST https://api.changenow.io/v2/exchange
{
  "fromCurrency": "eth",
  "toCurrency": "btc",  # Client's desired payout currency
  "fromAmount": "0.025",  # Estimated amount from SPLIT2
  "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Client's wallet
  "fromNetwork": "eth",
  "toNetwork": "btc",
  "flow": "fixed-rate",
  "type": "direct"
}

# Response: {
#   "id": "swap_abc123",  # swap_id
#   "payinAddress": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
#   "payinExtraId": null,
#   "payoutAddress": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
#   ...
# }
```

**Error Handling:**
All ChangeNow API errors trigger Cloud Tasks retry. Service logs errors but does not mark transactions as failed - retry continues until success or manual intervention.

---

#### PGP_HOSTPAY1_v1
**Payment Validator & Orchestrator**

**Location:** `/PGP_HOSTPAY1_v1/`
**Entry Point:** `pgp_hostpay1_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-15 instances)

**Purpose:**
Validates payment split requests from PGP_SPLIT1_v1 and orchestrates the final payment execution workflow across PGP_HOSTPAY2_v1 (ChangeNow status verification) and PGP_HOSTPAY3_v1 (ETH payment execution). Acts as the orchestrator for the final payment stage.

**Why It Exists:**
Before executing final ETH payment to client's address, we must verify that the ChangeNow swap has completed successfully and received USDT. This orchestrator coordinates the validation and payment execution steps, ensuring we only send ETH after confirming the swap succeeded.

**Critical Unique Functions:**
1. **Token Decryption** - Decrypts HMAC-signed payment request tokens from PGP_SPLIT1_v1
2. **ChangeNow Validation Orchestration** - Enqueues PGP_HOSTPAY2_v1 for swap status verification
3. **Status Callback Handling** - Receives status verification from PGP_HOSTPAY2_v1
4. **Payment Orchestration** - Enqueues PGP_HOSTPAY3_v1 for ETH payment execution after verification
5. **Completion Callback Handling** - Receives payment confirmation from PGP_HOSTPAY3_v1
6. **Database Updates** - Updates `split_payout_que` with transaction details, status, tx_hash
7. **State Management** - Coordinates state transitions (executing → verifying → paying → completed)

**Endpoints:**
- **POST /** - Initial payment request (triggered by PGP_SPLIT1_v1)
- **POST /status-verified** - Status check callback (from PGP_HOSTPAY2_v1)
- **POST /payment-completed** - Payment execution callback (from PGP_HOSTPAY3_v1)
- **GET /health** - Health check endpoint

**Workflow Stages:**
```
1. Receive payment request from PGP_SPLIT1_v1
2. Enqueue PGP_HOSTPAY2_v1 for ChangeNow status check
3. [CALLBACK] Receive status verification (swap finished, USDT received)
4. Enqueue PGP_HOSTPAY3_v1 for ETH payment execution
5. [CALLBACK] Receive payment completion (tx_hash, gas_used)
6. Update database with final transaction details
7. Mark payout as completed
```

**Dependencies:**
- Uses PGP_COMMON for base classes (BaseConfigManager, BaseDatabaseManager, BaseCloudTasksClient, BaseTokenManager)
- Connects to PostgreSQL database (split_payout_que table)
- Creates tasks in Cloud Tasks queues:
  - `pgp-hostpay2-v1-queue` → PGP_HOSTPAY2_v1 (status check)
  - `pgp-hostpay3-v1-queue` → PGP_HOSTPAY3_v1 (payment execution)
- Receives callbacks from PGP_HOSTPAY2_v1 and PGP_HOSTPAY3_v1

**State Transitions:**
```
executing → verifying → paying → completed
     ↓          ↓          ↓
  failed    failed    failed
```

---

#### PGP_HOSTPAY2_v1
**ChangeNow Status Checker**

**Location:** `/PGP_HOSTPAY2_v1/`
**Entry Point:** `pgp_hostpay2_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-15 instances)

**Purpose:**
Receives encrypted tokens from PGP_HOSTPAY1_v1 via Cloud Tasks, checks ChangeNow transaction status via API, validates swap completion, captures actual_usdt_received amount, and returns encrypted verification responses.

**Why It Exists:**
Before sending ETH payment to client's wallet, we must verify that the ChangeNow swap has completed successfully and we received the expected USDT amount. This service isolates status checking with infinite retry, ensuring we never send payments for unfinished swaps.

**Critical Unique Functions:**
1. **Token Decryption** - Decrypts HMAC-signed status check request tokens from PGP_HOSTPAY1_v1
2. **ChangeNow Status API** - Calls `/v2/exchange/by-id/{exchange_id}` endpoint for transaction status
3. **Status Validation** - Verifies swap is in 'finished' state (or acceptable intermediate states)
4. **Actual Amount Recording** - Captures actual_usdt_received from ChangeNow (may differ from estimate)
5. **Hot-Reload API Key** - Fetches ChangeNow API key from Secret Manager on-demand
6. **Token Encryption** - Creates encrypted verification response with status and amounts
7. **Callback Queue** - Enqueues Cloud Task back to PGP_HOSTPAY1_v1 callback endpoint
8. **Infinite Retry** - Cloud Tasks retry until swap reaches 'finished' state

**Key Components:**
- **POST /** - Main status check endpoint (receives Cloud Tasks from PGP_HOSTPAY1_v1)
- **GET /health** - Health check endpoint
- `database_manager.py` - Database operations (optional logging)
- ChangeNowClient integration (PGP_COMMON.utils.changenow_client) - hot-reload enabled
- Status validation logic (checks for 'finished', 'sending', 'exchanging' states)

**Dependencies:**
- Uses PGP_COMMON for base classes and ChangeNowClient
- ChangeNow API v2 (external REST API)
- Creates tasks in `pgp-hostpay1-v1-callback-queue` (callbacks to PGP_HOSTPAY1_v1)
- Triggered by Cloud Tasks from PGP_HOSTPAY1_v1

**API Integration:**
```python
# ChangeNow API v2 Status Request
GET https://api.changenow.io/v2/exchange/by-id/{exchange_id}

# Response:
{
  "status": "finished",  # or "waiting", "confirming", "exchanging", "sending"
  "amountFrom": "100.00",  # USDT sent
  "amountTo": "0.025",  # ETH received
  "actualAmountTo": "0.0248",  # Actual ETH received (may differ)
  ...
}
```

**Status States:**
- **finished** - Swap completed successfully, proceed with payment
- **sending** - ChangeNow sending payout, wait and retry
- **exchanging** - ChangeNow processing swap, wait and retry
- **failed** - Swap failed, mark transaction as failed
- **refunded** - Swap refunded, mark transaction as failed

**Error Handling:**
Service retries indefinitely until swap reaches terminal state ('finished', 'failed', 'refunded'). Intermediate states trigger retry with exponential backoff.

---

#### PGP_HOSTPAY3_v1
**ETH Payment Executor**

**Location:** `/PGP_HOSTPAY3_v1/`
**Entry Point:** `pgp_hostpay3_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-15 instances)

**Purpose:**
Receives encrypted tokens from PGP_HOSTPAY1_v1 via Cloud Tasks, executes final ETH payment to client's wallet address using Web3.py and Ethereum mainnet, captures transaction hash and gas costs, and returns encrypted completion responses.

**Why It Exists:**
After ChangeNow swap verification, we must send the ETH to the client's payout address. This service handles the actual blockchain transaction execution using Web3.py, managing gas estimation, transaction signing with private key, and transaction submission to Ethereum mainnet.

**Critical Unique Functions:**
1. **Token Decryption** - Decrypts HMAC-signed payment execution request tokens from PGP_HOSTPAY1_v1
2. **ETH Payment Execution** - Sends ETH to client's wallet using Web3.py and Alchemy RPC
3. **Transaction Hash Recording** - Captures blockchain transaction hash for tracking
4. **Gas Estimation** - Estimates gas costs before transaction submission
5. **Private Key Management** - Loads HOT_WALLET_PRIVATE_KEY from Secret Manager securely
6. **Transaction Verification** - Confirms transaction success via receipt
7. **Token Encryption** - Creates encrypted completion response with tx_hash and gas_used
8. **Callback Queue** - Enqueues Cloud Task back to PGP_HOSTPAY1_v1 callback endpoint

**Key Components:**
- **POST /** - Main payment execution endpoint (receives Cloud Tasks from PGP_HOSTPAY1_v1)
- **GET /health** - Health check endpoint
- `config_manager.py` - Secret Manager integration for private key and RPC URL
- `database_manager.py` - Database operations (optional logging)
- Web3.py integration for Ethereum transactions
- Wallet management (hot wallet with private key)
- Token encryption/decryption (PGP_COMMON.tokens.BaseTokenManager)

**Dependencies:**
- Uses PGP_COMMON for base classes (BaseConfigManager, BaseDatabaseManager, BaseCloudTasksClient, BaseTokenManager)
- Web3.py library for Ethereum transactions
- Alchemy RPC endpoint (ETHEREUM_RPC_URL from Secret Manager)
- Creates tasks in `pgp-hostpay1-v1-callback-queue` (callbacks to PGP_HOSTPAY1_v1)
- Triggered by Cloud Tasks from PGP_HOSTPAY1_v1

**Transaction Flow:**
```python
# 1. Load private key from Secret Manager
private_key = config['HOST_WALLET_PRIVATE_KEY']

# 2. Build transaction
tx = {
    'to': client_wallet_address,
    'value': Web3.to_wei(eth_amount, 'ether'),
    'gas': estimated_gas,
    'gasPrice': w3.eth.gas_price,
    'nonce': w3.eth.get_transaction_count(hot_wallet_address),
    'chainId': 1  # Ethereum mainnet
}

# 3. Sign transaction
signed_tx = w3.eth.account.sign_transaction(tx, private_key)

# 4. Send transaction
tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

# 5. Wait for receipt
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

# 6. Return tx_hash to orchestrator
```

**Security:**
🔴 **CRITICAL:** Private key stored in Secret Manager with strict IAM permissions. Only PGP_HOSTPAY3_v1 service account has access. Key never logged or exposed in responses.

**Error Handling:**
All blockchain errors trigger Cloud Tasks retry with exponential backoff. Service logs errors for manual investigation but retries indefinitely until success.

---

### ⏰ SCHEDULED PROCESSORS

---

#### PGP_BATCHPROCESSOR_v1
**Scheduled Batch Payout Processor**

**Location:** `/PGP_BATCHPROCESSOR_v1/`
**Entry Point:** `pgp_batchprocessor_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-10 instances)
**Trigger:** Cloud Scheduler (every 5 minutes)

**Purpose:**
Triggered by Cloud Scheduler every 5 minutes. Queries `payout_accumulation` table for clients whose accumulated balance >= threshold ($50 USD default), creates batch records in `batch_conversions` table, and initiates USDT→ClientCurrency swap pipeline via PGP_SPLIT1_v1.

**Why It Exists:**
Payouts must be batched to minimize transaction costs, API calls, and blockchain fees. This scheduler detects when accumulated subscription revenue reaches the payout threshold and triggers the conversion pipeline. Runs every 5 minutes to ensure timely payouts while avoiding excessive API calls.

**Critical Unique Functions:**
1. **Threshold Detection** - Queries database for clients with `SUM(pending_payout_usd) >= 50` (configurable)
2. **Batch Record Creation** - Creates records in `batch_conversions` table with batch_id (UUID)
3. **Batch ID Generation** - Generates unique UUID identifiers for batch tracking
4. **Task Orchestration** - Enqueues Cloud Tasks to PGP_SPLIT1_v1 for swap execution
5. **Accumulation Marking** - Marks accumulated payments as `paid_out` to prevent double-processing
6. **Scheduler Trigger** - Receives POST requests from Cloud Scheduler every 5 minutes
7. **Idempotency** - Prevents duplicate batch creation via status checking

**Key Components:**
- **POST /process** - Main batch processing endpoint (triggered by Cloud Scheduler)
- **GET /health** - Health check endpoint for monitoring
- `database_manager.py` - Database operations (threshold queries, batch creation)
- `cloudtasks_client.py` - Cloud Tasks client for SPLIT1 queue (extends BaseCloudTasksClient)
- Threshold calculation logic
- Batch creation logic

**Dependencies:**
- Uses PGP_COMMON for base classes (BaseConfigManager, BaseDatabaseManager, BaseCloudTasksClient)
- Connects to PostgreSQL database (payout_accumulation, batch_conversions tables)
- Creates tasks in `pgp-split1-v1-queue` (Cloud Tasks → PGP_SPLIT1_v1)
- Triggered by Cloud Scheduler job (every 5 minutes)

**Threshold Query:**
```sql
SELECT
    client_id,
    SUM(pending_payout_usd) as total_pending_usd
FROM payout_accumulation
WHERE status = 'pending'
GROUP BY client_id
HAVING SUM(pending_payout_usd) >= 50.00
ORDER BY total_pending_usd DESC;
```

**Cloud Scheduler Configuration:**
```bash
gcloud scheduler jobs create http pgp-batchprocessor-v1-job \
  --schedule="*/5 * * * *" \
  --uri="https://pgp-batchprocessor-v1-[hash].run.app/process" \
  --http-method=POST \
  --oidc-service-account-email="pgp-batchprocessor-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --location=us-central1
```

---

#### PGP_MICROBATCHPROCESSOR_v1
**Scheduled Micro-Batch ETH→USDT Conversion**

**Location:** `/PGP_MICROBATCHPROCESSOR_v1/`
**Entry Point:** `pgp_microbatchprocessor_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-10 instances)
**Trigger:** Cloud Scheduler (every 15 minutes)

**Purpose:**
Triggered by Cloud Scheduler every 15 minutes. Checks total pending USD in `payout_accumulation` table, and if >= threshold ($5 USD default), creates a single ETH→USDT swap via ChangeNow to eliminate cryptocurrency volatility risk. Protects channel owner revenue from ETH price fluctuations.

**Why It Exists:**
Accumulated ETH payments from subscriptions are subject to price volatility. If ETH price drops, channel owners lose revenue. This service periodically converts accumulated ETH to stablecoin USDT at fixed rates, locking in USD value and eliminating volatility risk. Runs more frequently than batch processor (every 15min vs 5min) to minimize exposure.

**Critical Unique Functions:**
1. **Threshold Checking** - Sums total pending USD from `payout_accumulation` table across all clients
2. **Batch ETH→USDT Swap** - Creates ChangeNow fixed-rate swap (ETH → USDT) for accumulated balances
3. **Batch Conversion Recording** - Records swap in `batch_conversions` table with exchange_id
4. **Accumulation Status Update** - Marks all pending payments as `swapping` status
5. **Task Queuing** - Enqueues Cloud Task to PGP_HOSTPAY1_v1 for swap status monitoring
6. **Scheduler Trigger** - Receives POST requests from Cloud Scheduler every 15 minutes
7. **Hot-Reload API Key** - Fetches ChangeNow API key from Secret Manager on-demand

**Key Components:**
- **POST /check-threshold** - Main threshold check endpoint (triggered by Cloud Scheduler)
- **GET /health** - Health check endpoint for monitoring
- `database_manager.py` - Database operations (threshold queries, status updates)
- `cloudtasks_client.py` - Cloud Tasks client for HOSTPAY1 queue
- ChangeNowClient integration (PGP_COMMON.utils.changenow_client) - hot-reload enabled
- Threshold calculation logic

**Dependencies:**
- Uses PGP_COMMON for base classes and ChangeNowClient
- Connects to PostgreSQL database (payout_accumulation, batch_conversions tables)
- ChangeNow API v2 (external REST API for ETH→USDT swaps)
- Creates tasks in `pgp-hostpay1-v1-queue` (Cloud Tasks → PGP_HOSTPAY1_v1)
- Triggered by Cloud Scheduler job (every 15 minutes)

**Threshold Query:**
```sql
SELECT
    SUM(pending_payout_usd) as total_pending_usd,
    SUM(pending_payout_eth) as total_pending_eth
FROM payout_accumulation
WHERE status = 'pending';
```

**ChangeNow Swap Creation:**
```python
# If total_pending_usd >= 5.00:
swap_response = changenow_client.create_fixed_swap(
    from_currency='eth',
    to_currency='usdt',
    from_amount=total_pending_eth,
    from_network='eth',
    to_network='eth',
    payout_address=HOST_WALLET_USDT_ADDRESS  # Our USDT wallet
)
# Returns: { "id": "exchange_abc123", "payinAddress": "0x...", ... }
```

**Cloud Scheduler Configuration:**
```bash
gcloud scheduler jobs create http pgp-microbatchprocessor-v1-job \
  --schedule="*/15 * * * *" \
  --uri="https://pgp-microbatchprocessor-v1-[hash].run.app/check-threshold" \
  --http-method=POST \
  --oidc-service-account-email="pgp-microbatchprocessor-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --location=us-central1
```

**Volatility Protection Example:**
- User pays $10 subscription (receives ~0.003 ETH at $3000/ETH)
- ETH drops to $2500/ETH before payout (now worth $7.50)
- Micro-batch converts ETH→USDT at $3000/ETH (locks in $10 value)
- Channel owner receives $10 USD equivalent regardless of ETH price

---

### 📢 COMMUNICATIONS LAYER

---

#### PGP_NOTIFICATIONS_v1
**Payment Notification Service**

**Location:** `/PGP_NOTIFICATIONS_v1/`
**Entry Point:** `pgp_notifications_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 0-10 instances)

**Purpose:**
Sends payment notifications to channel owners via Telegram direct message when users purchase subscriptions or make donations. Provides real-time revenue alerts with formatted payment details including amount, currency, subscriber username, and subscription tier.

**Why It Exists:**
Channel owners need to be notified immediately when they receive payments. This service formats and delivers professional notification messages via Telegram Bot API, providing real-time revenue tracking and payment confirmations. Enhances trust and transparency in the payment system.

**Critical Unique Functions:**
1. **Notification Formatting** - Creates formatted payment notification messages with emoji indicators
2. **Channel Owner Lookup** - Retrieves channel owner's Telegram user_id from `client_table` database
3. **Telegram Message Sending** - Delivers notifications via Telegram Bot API direct message
4. **Payment Type Handling** - Different message formats for subscriptions vs donations
5. **Error Handling** - Graceful handling of notification failures (user blocked bot, chat not found)
6. **Event Loop Management** - Uses `asyncio.run()` for isolated event loops (Cloud Run optimized)
7. **Retry Logic** - Cloud Tasks infinite retry for temporary Telegram API failures

**Key Components:**
- **POST /send-notification** - Main notification endpoint (receives Cloud Tasks)
- **GET /health** - Health check endpoint
- `notification_handler.py` - Notification formatting and delivery logic
- `telegram_client.py` - Telegram Bot API wrapper with retry logic
- Message templates for subscriptions and donations
- Error handling for blocked users and chat not found

**Dependencies:**
- Uses PGP_COMMON for logging (setup_logger)
- Connects to PostgreSQL database (client_table for owner lookup)
- python-telegram-bot library (Telegram Bot API client)
- Triggered by Cloud Tasks from PGP_ORCHESTRATOR_v1

**Notification Message Format (Subscription):**
```
💰 New Subscription Payment Received!

Amount: $10.00 USD (0.003 ETH)
Subscriber: @johndoe
Tier: Monthly Premium
Payment ID: abc123xyz
Status: Confirmed ✅

Your payout will be processed automatically when threshold is reached.
```

**Notification Message Format (Donation):**
```
🎁 New Donation Received!

Amount: $25.00 USD (0.0075 ETH)
From: @janedoe
Message: "Love your content! Keep it up!"
Payment ID: def456uvw
Status: Confirmed ✅

Thank you for creating amazing content!
```

**Architecture Note:**
Uses SYNCHRONOUS Flask route with `asyncio.run()` to create isolated event loops for each request. Prevents "Event loop is closed" errors in Cloud Run.

---

#### PGP_BROADCAST_v1
**Broadcast Scheduler & Executor**

**Location:** `/PGP_BROADCAST_v1/`
**Entry Point:** `pgp_broadcast_v1.py`
**Port:** 8080 (Flask)
**Deployment:** Cloud Run (512Mi RAM, 1-5 instances)
**Trigger:** Cloud Scheduler (configurable intervals)

**Purpose:**
Provides automated scheduled broadcasts and manual broadcast messaging to Telegram channels. Includes scheduling logic, execution tracking via `broadcast_manager` table, message delivery with rate limiting, and REST API for frontend control. Enables channel owners to communicate with subscribers.

**Why It Exists:**
Channel owners need to send announcements, updates, and broadcasts to their subscribers. This service provides reliable scheduled and manual broadcasting with delivery tracking, rate limiting to comply with Telegram API limits, and comprehensive logging for audit trails.

**Critical Unique Functions:**
1. **Broadcast Scheduling** - Cloud Scheduler triggers for automated recurring broadcasts
2. **Broadcast Execution** - Sends messages to Telegram channels with rate limiting
3. **Message Tracking** - Tracks broadcast status, delivery count, and failures in `broadcast_manager` table
4. **Web API** - REST endpoints for broadcast management (create, list, history)
5. **JWT Authentication** - Secures API endpoints with token-based auth
6. **CORS Support** - Enables future frontend integration
7. **Rate Limiting** - Complies with Telegram API limits (20 messages/second)

**Key Components:**
- `broadcast_scheduler.py` - Scheduling logic (queries database for due broadcasts)
- `broadcast_executor.py` - Message sending with Telegram Bot API
- `broadcast_tracker.py` - Delivery tracking and status updates
- `broadcast_web_api.py` - REST API endpoints with JWT authentication
- `telegram_client.py` - Telegram Bot API wrapper with rate limiting
- `database_manager.py` - Database operations for broadcast records

**Endpoints:**
- **POST /execute** - Execute scheduled broadcasts (triggered by Cloud Scheduler)
- **POST /api/broadcasts/manual** - Manual broadcast endpoint (requires JWT)
- **GET /api/broadcasts/history** - Broadcast history (requires JWT)
- **GET /health** - Health check endpoint

**Dependencies:**
- Uses PGP_COMMON for logging (setup_logger)
- Connects to PostgreSQL database (broadcast_manager, client_table tables)
- python-telegram-bot library (Telegram Bot API client)
- Flask-JWT-Extended for JWT authentication
- Flask-CORS for cross-origin support
- Triggered by Cloud Scheduler job (configurable intervals)

**Broadcast Types:**
1. **Scheduled Broadcasts** - Recurring automated messages (daily, weekly, monthly)
2. **Manual Broadcasts** - One-time messages via API endpoint

**Cloud Scheduler Configuration (Example - Daily Broadcast):**
```bash
gcloud scheduler jobs create http pgp-broadcast-v1-daily-job \
  --schedule="0 9 * * *"  # Daily at 9:00 AM
  --uri="https://pgp-broadcast-v1-[hash].run.app/execute" \
  --http-method=POST \
  --oidc-service-account-email="pgp-broadcast-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --location=us-central1
```

**Rate Limiting:**
Telegram API limits: 20 messages/second per bot. Service implements token bucket rate limiter with 50ms delays between messages to stay within limits.

---

### 📚 SHARED INFRASTRUCTURE

---

#### PGP_COMMON
**Shared Library for All PGP_v1 Services**

**Location:** `/PGP_COMMON/`
**Package Type:** Installable Python package (pip install -e ../PGP_COMMON)
**Installation:** Required in all service Dockerfiles

**Purpose:**
Eliminates code duplication by providing base classes, utilities, and common functionality shared across all 15 PGP_v1 microservices. Serves as a single source of truth for configuration management, database operations, Cloud Tasks integration, token encryption, and utility functions.

**Why It Exists:**
Without shared libraries, each of the 15 services would duplicate configuration, database, token, and Cloud Tasks logic. This would lead to ~7,250 lines of duplicate code, inconsistent behavior, maintenance nightmares, and bug propagation across services. PGP_COMMON achieves **60% code reduction** and ensures consistent patterns across all services.

**Critical Unique Functions:**

**Base Classes (Inheritance):**
1. **BaseConfigManager** - Secret Manager integration, hot-reload configuration, secret fetching
2. **BaseCloudTasksClient** - Cloud Tasks operations, HMAC-signed token generation, queue management
3. **BaseDatabaseManager** - Database connection pooling, SQL query execution, Cloud SQL Connector
4. **BaseTokenManager** - Token encryption/decryption, HMAC signature generation/verification

**Utilities (Import):**
5. **ChangeNowClient** - ChangeNow API v2 integration (estimate, swap creation, status check) - hot-reload enabled
6. **CryptoPricingClient** - Multi-source cryptocurrency pricing (CoinGecko, CryptoCompare, 1inch fallback)
7. **RedisClient** - Redis operations for nonce tracking (HMAC timestamp replay prevention)
8. **Error Sanitization** - Security utilities for error responses (removes stack traces, sanitizes messages)
9. **Webhook Authentication** - SHA-256 and SHA-512 signature verification for webhooks
10. **Wallet Validation** - Cryptocurrency wallet address validation (ETH, BTC, USDT, 150+ currencies)
11. **IP Extraction** - Extract real client IP from Cloud Run headers (X-Forwarded-For, X-Real-IP)
12. **Centralized Logging** - Standardized logging with emoji support and LOG_LEVEL environment variable

**Package Structure:**
```
PGP_COMMON/
├── __init__.py                    # Package initialization
├── setup.py                       # pip install configuration
├── README.md                      # Usage documentation
├── config/
│   └── base_config.py             # BaseConfigManager
├── cloudtasks/
│   └── base_client.py             # BaseCloudTasksClient
├── database/
│   └── db_manager.py              # BaseDatabaseManager
├── tokens/
│   ├── base_token.py              # BaseTokenManager
│   └── token_formats.py           # Token format definitions
├── logging/
│   └── base_logger.py             # Centralized logging
├── auth/
│   └── service_auth.py            # Service authentication
└── utils/
    ├── changenow_client.py        # ChangeNow API client
    ├── crypto_pricing.py          # Crypto pricing fallback
    ├── redis_client.py            # Redis client
    ├── error_sanitizer.py         # Error sanitization
    ├── webhook_auth.py            # Webhook signature verification
    ├── wallet_validation.py       # Wallet address validation
    ├── ip_extraction.py           # IP extraction utilities
    ├── validation.py              # Input validation
    └── idempotency.py             # Idempotency helpers
```

**Benefits:**
- **60% Code Reduction** - Eliminates ~7,250 lines of duplicate code across 15 services
- **Single Source of Truth** - Update common methods in one place, propagates to all services
- **Consistent Behavior** - All services use identical patterns for config, database, tasks, tokens
- **Easier Maintenance** - Bug fixes in base classes automatically fix all services
- **Better Testing** - Test base classes once instead of 15 times in each service
- **Hot-Reload Support** - Configuration changes without redeployment (Secret Manager integration)
- **Security Hardening** - Centralized security utilities ensure consistent protection

**Usage Example:**
```python
# Every PGP_X_v1 service extends base classes:
from PGP_COMMON.config import BaseConfigManager
from PGP_COMMON.database import BaseDatabaseManager
from PGP_COMMON.cloudtasks import BaseCloudTasksClient
from PGP_COMMON.tokens import BaseTokenManager
from PGP_COMMON.logging import setup_logger

class ConfigManager(BaseConfigManager):
    def __init__(self):
        super().__init__(service_name="PGP_ORCHESTRATOR_v1")

class DatabaseManager(BaseDatabaseManager):
    def __init__(self):
        super().__init__(service_name="PGP_ORCHESTRATOR_v1")

# Initialize logger
logger = setup_logger(__name__)
```

**Installation in Dockerfiles:**
```dockerfile
# Copy PGP_COMMON and install
COPY PGP_COMMON /app/PGP_COMMON
RUN pip install -e /app/PGP_COMMON

# Copy service-specific code
COPY PGP_ORCHESTRATOR_v1 /app
```

**Dependencies (PGP_COMMON requirements):**
- google-cloud-secret-manager
- google-cloud-tasks
- cloud-sql-python-connector
- pg8000
- redis
- requests
- web3
- cryptography
- sqlalchemy

---

## 🚀 DEPLOYMENT CHECKLIST - pgp-live Project

### Pre-Deployment Overview

**Target Environment:** pgp-live (GCP Project)
**Database:** pgp-live-psql (Cloud SQL PostgreSQL instance)
**Region:** us-central1
**Budget Target:** $200/month
**Scale Target:** 1000 requests/minute
**Timeline:** 3-4 weeks (accelerated) or 5-8 weeks (standard)

---

### PHASE 1: GCP Project Setup & Permissions

**⏱️ Duration:** 1-2 days
**Budget Impact:** $0 (no resource costs)

#### 1.1 Project Configuration
- [ ] Verify pgp-live project exists
- [ ] Enable required APIs:
  ```bash
  gcloud services enable compute.googleapis.com \
    sqladmin.googleapis.com \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudtasks.googleapis.com \
    secretmanager.googleapis.com \
    redis.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com \
    --project=pgp-live
  ```

#### 1.2 Service Accounts (15 services)
- [ ] Create service accounts for each PGP_X_v1 service:
  ```bash
  # Create service accounts
  for service in server webapi np-ipn orchestrator invite \
                 split1 split2 split3 \
                 hostpay1 hostpay2 hostpay3 \
                 batchprocessor microbatchprocessor \
                 notifications broadcast; do
    gcloud iam service-accounts create pgp-${service}-v1-sa \
      --display-name="PGP ${service} v1 Service Account" \
      --project=pgp-live
  done
  ```

#### 1.3 IAM Permissions
- [ ] Grant Secret Manager access to all service accounts
- [ ] Grant Cloud SQL Client role to database services
- [ ] Grant Cloud Tasks Admin to orchestrator services
- [ ] Grant Logs Writer to all services
- [ ] Grant Monitoring Metric Writer to all services

---

### PHASE 2: Secret Manager (75+ Secrets)

**⏱️ Duration:** 2-3 days
**Budget Impact:** ~$0.36/month (75 secrets × $0.06/10K access operations)

#### 2.1 Database Credentials (5 secrets)
- [ ] `DATABASE_HOST_SECRET` - pgp-live-psql instance IP
- [ ] `DATABASE_NAME_SECRET` - pgp-live-db
- [ ] `DATABASE_USER_SECRET` - postgres
- [ ] `DATABASE_PASSWORD_SECRET` - Generate strong password (15+ chars)
- [ ] `CLOUD_SQL_CONNECTION_NAME` - pgp-live:us-central1:pgp-live-psql

#### 2.2 Payment & Exchange APIs (8 secrets)
- [ ] `NOWPAYMENTS_API_KEY` - Copy from telepay-459221
- [ ] `NOWPAYMENTS_IPN_SECRET` - Copy from telepay-459221
- [ ] `NOWPAYMENT_WEBHOOK_KEY` - Copy from telepay-459221
- [ ] `PAYMENT_PROVIDER_TOKEN` - Copy from telepay-459221
- [ ] `CHANGENOW_API_KEY` - Copy from telepay-459221
- [ ] `COINGECKO_API_KEY` - Copy from telepay-459221
- [ ] `CRYPTOCOMPARE_API_KEY` - Copy from telepay-459221
- [ ] `1INCH_API_KEY` - Copy from telepay-459221

#### 2.3 Blockchain & Wallet (6 secrets) 🔴 CRITICAL
- [ ] `HOST_WALLET_PRIVATE_KEY` - Copy from telepay-459221 (NEVER REGENERATE)
- [ ] `HOST_WALLET_ETH_ADDRESS` - Copy from telepay-459221
- [ ] `HOST_WALLET_USDT_ADDRESS` - Copy from telepay-459221
- [ ] `ETHEREUM_RPC_URL` - Alchemy mainnet RPC URL
- [ ] `ETHEREUM_RPC_URL_API` - Alchemy API key
- [ ] `ETHEREUM_RPC_WEBHOOK_SECRET` - Copy from telepay-459221

#### 2.4 Signing & Security Keys (6 secrets)
- [ ] `WEBHOOK_SIGNING_KEY` - Generate new 64-char hex key
- [ ] `TPS_HOSTPAY_SIGNING_KEY` - Generate new 64-char hex key
- [ ] `SUCCESS_URL_SIGNING_KEY` - Copy from telepay-459221
- [ ] `JWT_SECRET_KEY` - Generate new 64-char hex key
- [ ] `SIGNUP_SECRET_KEY` - Generate new 64-char hex key
- [ ] `FLASK_SECRET_KEY` - Generate new 64-char hex key

#### 2.5 Telegram Bot (2 secrets)
- [ ] `TELEGRAM_BOT_SECRET_NAME` - Copy from telepay-459221 (or create new bot)
- [ ] `TELEGRAM_BOT_USERNAME` - PayGatePrime_bot (or new bot username)

#### 2.6 Email Configuration (3 secrets)
- [ ] `SENDGRID_API_KEY` - Copy from telepay-459221 (or generate new)
- [ ] `FROM_EMAIL` - noreply@paygateprime.com
- [ ] `FROM_NAME` - PayGatePrime

#### 2.7 Service URLs (15 secrets) - UPDATE AFTER DEPLOYMENT
- [ ] `PGP_SERVER_URL` - https://pgp-server-v1-[hash].run.app
- [ ] `PGP_WEBAPI_URL` - https://pgp-webapi-v1-[hash].run.app
- [ ] `PGP_NP_IPN_URL` - https://pgp-np-ipn-v1-[hash].run.app
- [ ] `PGP_ORCHESTRATOR_URL` - https://pgp-orchestrator-v1-[hash].run.app
- [ ] `PGP_INVITE_URL` - https://pgp-invite-v1-[hash].run.app
- [ ] `PGP_SPLIT1_URL` - https://pgp-split1-v1-[hash].run.app
- [ ] `PGP_SPLIT2_URL` - https://pgp-split2-v1-[hash].run.app
- [ ] `PGP_SPLIT3_URL` - https://pgp-split3-v1-[hash].run.app
- [ ] `PGP_HOSTPAY1_URL` - https://pgp-hostpay1-v1-[hash].run.app
- [ ] `PGP_HOSTPAY2_URL` - https://pgp-hostpay2-v1-[hash].run.app
- [ ] `PGP_HOSTPAY3_URL` - https://pgp-hostpay3-v1-[hash].run.app
- [ ] `PGP_BATCHPROCESSOR_URL` - https://pgp-batchprocessor-v1-[hash].run.app
- [ ] `PGP_MICROBATCHPROCESSOR_URL` - https://pgp-microbatchprocessor-v1-[hash].run.app
- [ ] `PGP_NOTIFICATIONS_URL` - https://pgp-notifications-v1-[hash].run.app
- [ ] `PGP_BROADCAST_URL` - https://pgp-broadcast-v1-[hash].run.app

#### 2.8 Cloud Tasks Queue Names (17 secrets)
- [ ] `PGP_ORCHESTRATOR_QUEUE` - pgp-orchestrator-v1-queue
- [ ] `PGP_INVITE_QUEUE` - pgp-invite-v1-queue
- [ ] `PGP_NOTIFICATIONS_QUEUE` - pgp-notifications-v1-queue
- [ ] `PGP_SPLIT1_QUEUE` - pgp-split1-v1-queue
- [ ] `PGP_SPLIT1_CALLBACK_QUEUE` - pgp-split1-v1-callback-queue
- [ ] `PGP_SPLIT2_QUEUE` - pgp-split2-v1-queue
- [ ] `PGP_SPLIT2_RESPONSE_QUEUE` - pgp-split2-v1-response-queue
- [ ] `PGP_SPLIT3_QUEUE` - pgp-split3-v1-queue
- [ ] `PGP_SPLIT3_RESPONSE_QUEUE` - pgp-split3-v1-response-queue
- [ ] `PGP_HOSTPAY1_QUEUE` - pgp-hostpay1-v1-queue
- [ ] `PGP_HOSTPAY1_CALLBACK_QUEUE` - pgp-hostpay1-v1-callback-queue
- [ ] `PGP_HOSTPAY2_QUEUE` - pgp-hostpay2-v1-queue
- [ ] `PGP_HOSTPAY3_QUEUE` - pgp-hostpay3-v1-queue
- [ ] `PGP_BATCHPROCESSOR_QUEUE` - pgp-batchprocessor-v1-queue
- [ ] `PGP_MICROBATCHPROCESSOR_QUEUE` - pgp-microbatchprocessor-v1-queue

#### 2.9 Application Configuration (10 secrets)
- [ ] `BASE_URL` - https://www.paygateprime.com
- [ ] `CORS_ORIGIN` - https://www.paygateprime.com
- [ ] `CLOUD_TASKS_LOCATION` - us-central1
- [ ] `CLOUD_TASKS_PROJECT_ID` - pgp-live
- [ ] `BROADCAST_AUTO_INTERVAL` - 24 (hours)
- [ ] `BROADCAST_MANUAL_INTERVAL` - 0.0833 (hours, 5 minutes)
- [ ] `ALERTING_ENABLED` - true
- [ ] `MICRO_BATCH_THRESHOLD_USD` - 5.00
- [ ] `PAYMENT_FALLBACK_TOLERANCE` - 0.75
- [ ] `PAYMENT_MIN_TOLERANCE` - 0.50
- [ ] `TP_FLAT_FEE` - 15 (TelePay 3% fee in basis points)

#### 2.10 Grant IAM Access to Secrets
```bash
# Grant access to all service accounts
for service in server webapi np-ipn orchestrator invite \
               split1 split2 split3 \
               hostpay1 hostpay2 hostpay3 \
               batchprocessor microbatchprocessor \
               notifications broadcast; do

  # Grant access to all secrets
  for secret in $(gcloud secrets list --project=pgp-live --format="value(name)"); do
    gcloud secrets add-iam-policy-binding $secret \
      --member="serviceAccount:pgp-${service}-v1-sa@pgp-live.iam.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor" \
      --project=pgp-live
  done
done
```

---

### PHASE 3: Cloud SQL PostgreSQL Database

**⏱️ Duration:** 2-3 days
**Budget Impact:** ~$60-80/month (shared-core-1 with 10GB storage)

#### 3.1 Create Cloud SQL Instance
```bash
gcloud sql instances create pgp-live-psql \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-7680 \
  --region=us-central1 \
  --storage-type=SSD \
  --storage-size=10GB \
  --storage-auto-increase \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=3 \
  --availability-type=ZONAL \
  --backup-start-time=02:00 \
  --enable-bin-log \
  --retained-backups-count=7 \
  --project=pgp-live

# Cost: ~$60-80/month
# Custom tier (2 vCPU, 7.5GB RAM) chosen to handle 1000 req/min
# Auto-increase storage ensures no downtime
# Daily backups with 7-day retention
```

#### 3.2 Create Database
```bash
gcloud sql databases create pgp-live-db \
  --instance=pgp-live-psql \
  --project=pgp-live
```

#### 3.3 Set Root Password
```bash
# Generate strong password
PG_PASSWORD=$(openssl rand -base64 32)

# Set postgres user password
gcloud sql users set-password postgres \
  --instance=pgp-live-psql \
  --password="$PG_PASSWORD" \
  --project=pgp-live

# Save to Secret Manager
echo -n "$PG_PASSWORD" | gcloud secrets create DATABASE_PASSWORD_SECRET \
  --data-file=- \
  --replication-policy="automatic" \
  --project=pgp-live
```

#### 3.4 Deploy Database Schema
```bash
# Run schema deployment script
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/scripts
./deploy_pgp_live_schema.sh

# This creates:
# - 15 database tables
# - 4 ENUM types
# - Indexes and constraints
# - UNIQUE constraints for idempotency
```

#### 3.5 Verify Schema Deployment
```bash
# Run verification script
./verify_pgp_live_schema.sh

# Expected output:
# ✅ All 15 tables created
# ✅ All ENUM types created
# ✅ All indexes created
# ✅ All constraints created
```

#### 3.6 Enable Connection from Cloud Run
```bash
# Cloud Run services connect via private IP (no public IP needed)
# Connection string: pgp-live:us-central1:pgp-live-psql
```

#### 3.7 Database Tables (15 total)
- `client_table` - Channel owner registration
- `subscription_tier_map` - Subscription pricing tiers
- `payout_details` - Payout wallet configuration
- `processed_payments` - Payment records
- `payout_accumulation` - Pending payouts
- `batch_conversions` - Batch swap records
- `split_payout_que` - Payment split workflow
- `broadcast_manager` - Broadcast scheduling
- `donation_keypad_state` - Donation workflow state
- `conversation_state` - Bot conversation state
- `currency_to_network` - Currency network mapping
- `failed_transactions` - Failed payment tracking
- `landing_page` - Landing page analytics
- `transaction_limits` - Rate limiting
- Additional supporting tables

---

### PHASE 4: Redis Instance (Nonce Tracking)

**⏱️ Duration:** 1 day
**Budget Impact:** ~$15-20/month (Basic tier, 1GB)

#### 4.1 Create Redis Instance
```bash
# Run Redis deployment script
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/scripts
./deploy_redis_nonce_tracker.sh

# Creates:
# - Redis instance: pgp-nonce-tracker
# - Tier: Basic (1GB)
# - Region: us-central1
# - VPC: default
```

#### 4.2 Create Redis Secret
```bash
# Get Redis host
REDIS_HOST=$(gcloud redis instances describe pgp-nonce-tracker \
  --region=us-central1 \
  --format="value(host)" \
  --project=pgp-live)

# Create secret
echo -n "$REDIS_HOST" | gcloud secrets create REDIS_HOST \
  --data-file=- \
  --replication-policy="automatic" \
  --project=pgp-live

# Create port secret (default: 6379)
echo -n "6379" | gcloud secrets create REDIS_PORT \
  --data-file=- \
  --replication-policy="automatic" \
  --project=pgp-live
```

---

### PHASE 5: Cloud Tasks Queues (17 queues)

**⏱️ Duration:** 1 day
**Budget Impact:** $0 (pay-per-use, ~$0.40/million operations)

#### 5.1 Create All Cloud Tasks Queues
```bash
# Create queues for all services
for queue in pgp-orchestrator-v1-queue \
             pgp-invite-v1-queue \
             pgp-notifications-v1-queue \
             pgp-split1-v1-queue \
             pgp-split1-v1-callback-queue \
             pgp-split2-v1-queue \
             pgp-split2-v1-response-queue \
             pgp-split3-v1-queue \
             pgp-split3-v1-response-queue \
             pgp-hostpay1-v1-queue \
             pgp-hostpay1-v1-callback-queue \
             pgp-hostpay2-v1-queue \
             pgp-hostpay3-v1-queue \
             pgp-batchprocessor-v1-queue \
             pgp-microbatchprocessor-v1-queue; do

  gcloud tasks queues create $queue \
    --location=us-central1 \
    --max-concurrent-dispatches=100 \
    --max-attempts=0 \
    --max-retry-duration=0 \
    --min-backoff=1s \
    --max-backoff=60s \
    --max-doublings=16 \
    --project=pgp-live
done
```

#### 5.2 Queue Configuration Details
- **Max Concurrent Dispatches:** 100 (handles high throughput)
- **Max Attempts:** 0 (infinite retry for resilience)
- **Max Retry Duration:** 0 (never give up)
- **Min Backoff:** 1s (fast initial retry)
- **Max Backoff:** 60s (reasonable max delay)
- **Max Doublings:** 16 (exponential backoff)

---

### PHASE 6: Cloud Run Services Deployment (15 services)

**⏱️ Duration:** 3-5 days
**Budget Impact:** ~$80-120/month (depends on traffic and instance scaling)

#### 6.1 Deploy All Services
```bash
# Run master deployment script
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/scripts
./deploy_all_pgp_services.sh

# This deploys all 15 services:
# Phase 1: Core Infrastructure (PGP_SERVER_v1, PGP_WEBAPI_v1)
# Phase 2: Payment Processing (PGP_NP_IPN_v1, PGP_ORCHESTRATOR_v1, PGP_INVITE_v1)
# Phase 3: Payout Pipeline (SPLIT1-3, HOSTPAY1-3)
# Phase 4: Batch Processors (BATCHPROCESSOR, MICROBATCHPROCESSOR)
# Phase 5: Communications (NOTIFICATIONS, BROADCAST)
```

#### 6.2 Resource Allocation Per Service

**🔴 CRITICAL - Customer-Facing Service:**
- **PGP_WEBAPI_v1:** 4 CPU, 8GB RAM, 0-10 instances, 300s timeout
  - Handles customer registration and API traffic
  - **Must support 1000 requests/minute during peak load**
  - Memory-intensive: JWT generation, database queries, email rendering
  - **Budget Impact:** ~$60-80/month (most expensive service)

**High-Traffic Services:**
- **PGP_SERVER_v1:** 1 CPU, 1GB RAM, 1-20 instances, 300s timeout (~$25-30/month)
- **PGP_NP_IPN_v1:** 1 CPU, 512MB RAM, 0-20 instances, 300s timeout (~$15-20/month)
- **PGP_ORCHESTRATOR_v1:** 1 CPU, 512MB RAM, 0-20 instances, 300s timeout (~$15-20/month)

**Medium-Traffic Services:**
- **PGP_SPLIT1_v1:** 1 CPU, 512MB RAM, 0-15 instances, 300s timeout (~$10-15/month)
- **PGP_SPLIT2_v1:** 1 CPU, 512MB RAM, 0-15 instances, 300s timeout (~$10-15/month)
- **PGP_SPLIT3_v1:** 1 CPU, 512MB RAM, 0-15 instances, 300s timeout (~$10-15/month)
- **PGP_HOSTPAY1_v1:** 1 CPU, 512MB RAM, 0-15 instances, 300s timeout (~$10-15/month)
- **PGP_HOSTPAY2_v1:** 1 CPU, 512MB RAM, 0-15 instances, 300s timeout (~$10-15/month)
- **PGP_HOSTPAY3_v1:** 1 CPU, 512MB RAM, 0-15 instances, 300s timeout (~$10-15/month)

**Low-Traffic Services:**
- **PGP_INVITE_v1:** 1 CPU, 512MB RAM, 0-10 instances, 300s timeout (~$5-10/month)
- **PGP_BATCHPROCESSOR_v1:** 1 CPU, 512MB RAM, 0-10 instances, 300s timeout (~$5-10/month)
- **PGP_MICROBATCHPROCESSOR_v1:** 1 CPU, 512MB RAM, 0-10 instances, 300s timeout (~$5-10/month)
- **PGP_NOTIFICATIONS_v1:** 1 CPU, 512MB RAM, 0-10 instances, 300s timeout (~$5-10/month)
- **PGP_BROADCAST_v1:** 1 CPU, 512MB RAM, 1-5 instances, 300s timeout (~$5-10/month)

#### 6.3 Service URLs Collection
After deployment, collect all service URLs and update Secret Manager:
```bash
# Get service URLs
for service in server webapi np-ipn orchestrator invite \
               split1 split2 split3 \
               hostpay1 hostpay2 hostpay3 \
               batchprocessor microbatchprocessor \
               notifications broadcast; do

  URL=$(gcloud run services describe pgp-${service}-v1 \
    --region=us-central1 \
    --format="value(status.url)" \
    --project=pgp-live)

  echo "pgp-${service}-v1: $URL"

  # Update Secret Manager
  SECRET_NAME="PGP_$(echo $service | tr '[:lower:]' '[:upper:]' | tr '-' '_')_URL"
  echo -n "$URL" | gcloud secrets versions add $SECRET_NAME \
    --data-file=- \
    --project=pgp-live
done
```

---

### PHASE 7: Cloud Scheduler (CRON Jobs)

**⏱️ Duration:** 1 day
**Budget Impact:** $0.10/month (3 jobs × $0.10/job)

#### 7.1 Create Batch Processor Job (Every 5 minutes)
```bash
gcloud scheduler jobs create http pgp-batchprocessor-v1-job \
  --schedule="*/5 * * * *" \
  --uri="https://pgp-batchprocessor-v1-[hash].run.app/process" \
  --http-method=POST \
  --oidc-service-account-email="pgp-batchprocessor-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --location=us-central1 \
  --project=pgp-live

# Runs every 5 minutes: 288 times/day
# Checks for clients with balance >= $50 USD
# Triggers payout pipeline via PGP_SPLIT1_v1
```

#### 7.2 Create Micro-Batch Processor Job (Every 15 minutes)
```bash
gcloud scheduler jobs create http pgp-microbatchprocessor-v1-job \
  --schedule="*/15 * * * *" \
  --uri="https://pgp-microbatchprocessor-v1-[hash].run.app/check-threshold" \
  --http-method=POST \
  --oidc-service-account-email="pgp-microbatchprocessor-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --location=us-central1 \
  --project=pgp-live

# Runs every 15 minutes: 96 times/day
# Checks for total pending >= $5 USD
# Triggers ETH→USDT conversion via ChangeNow
```

#### 7.3 Create Broadcast Scheduler Job (Daily at 9:00 AM)
```bash
gcloud scheduler jobs create http pgp-broadcast-v1-daily-job \
  --schedule="0 9 * * *" \
  --uri="https://pgp-broadcast-v1-[hash].run.app/execute" \
  --http-method=POST \
  --oidc-service-account-email="pgp-broadcast-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --location=us-central1 \
  --project=pgp-live

# Runs daily at 9:00 AM UTC
# Executes scheduled broadcasts to channels
```

---

### PHASE 8: External Configuration & Webhooks

**⏱️ Duration:** 1-2 days
**Budget Impact:** $0 (configuration only)

#### 8.1 Update NOWPayments Dashboard
1. Login to https://nowpayments.io/dashboard
2. Navigate to Settings → API → IPN Settings
3. Update IPN Callback URL:
   - **Production:** `https://[load-balancer-ip]/webhooks/nowpayments-ipn`
   - **Direct:** `https://pgp-np-ipn-v1-[hash].run.app/`
4. Update Success URL:
   - **Production:** `https://[load-balancer-ip]/webhooks/success`
   - **Direct:** `https://pgp-orchestrator-v1-[hash].run.app/`
5. Verify IPN Secret matches Secret Manager value
6. Test IPN signature verification

#### 8.2 Configure Telegram Bot Webhook (Optional)
```bash
# Option 1: Polling (default, no webhook needed)
# PGP_SERVER_v1 uses polling by default - no configuration needed

# Option 2: Webhook (recommended for production)
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://pgp-server-v1-[hash].run.app/telegram-webhook",
    "max_connections": 40,
    "allowed_updates": ["message", "callback_query"]
  }'
```

#### 8.3 Update DNS Records (Cloudflare)
⚠️ **DO NOT DEPLOY TO CLOUDFLARE** - Local changes only

**Documentation Only:**
- Point `www.paygateprime.com` to Load Balancer IP (after Phase 9)
- Configure SSL/TLS certificate (Full or Full Strict mode)
- Enable Cloudflare proxy (orange cloud)
- Configure WAF rules for DDoS protection

#### 8.4 Configure ChangeNow API Webhooks (Optional)
1. Login to https://changenow.io/
2. Navigate to API Settings
3. Configure status webhooks (optional - we poll instead):
   - Not required - our services poll ChangeNow API for status updates
   - Reduces webhook complexity and improves resilience

---

### PHASE 9: Load Balancer & Cloud Armor (Security Layer)

**⏱️ Duration:** 2-3 days
**Budget Impact:** ~$18-25/month (Load Balancer + Cloud Armor)

#### 9.1 Create Serverless Network Endpoint Groups (NEGs)
```bash
# Create NEG for each public-facing service
for service in server webapi np-ipn orchestrator; do
  gcloud compute network-endpoint-groups create pgp-${service}-v1-neg \
    --region=us-central1 \
    --network-endpoint-type=SERVERLESS \
    --cloud-run-service=pgp-${service}-v1 \
    --project=pgp-live
done
```

#### 9.2 Create Cloud Armor Security Policy
```bash
# Create security policy
gcloud compute security-policies create pgp-security-policy \
  --description="PayGatePrime DDoS protection and rate limiting" \
  --project=pgp-live

# Add rate limiting rule (1000 requests/minute per IP)
gcloud compute security-policies rules create 1000 \
  --security-policy=pgp-security-policy \
  --expression="true" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=1000 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=600 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --project=pgp-live

# Add NOWPayments IP whitelist for IPN endpoint
gcloud compute security-policies rules create 2000 \
  --security-policy=pgp-security-policy \
  --src-ip-ranges="<nowpayments-ip-range>" \
  --action=allow \
  --description="Allow NOWPayments IPN webhooks" \
  --project=pgp-live
```

#### 9.3 Deploy Load Balancer
```bash
# Run load balancer deployment script
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/TOOLS_SCRIPTS_TESTS/scripts/security
./deploy_load_balancer.sh

# Creates:
# - Backend services for each NEG
# - URL map with path routing
# - Target HTTPS proxy
# - SSL certificate (managed)
# - Global forwarding rule
# - Attaches Cloud Armor policy
```

#### 9.4 Path Routing Configuration
```yaml
# URL Map Configuration
/webhooks/nowpayments-ipn → pgp-np-ipn-v1
/webhooks/success → pgp-orchestrator-v1
/api/* → pgp-webapi-v1
/* → pgp-server-v1 (default)
```

---

### PHASE 10: Monitoring & Alerting

**⏱️ Duration:** 2-3 days
**Budget Impact:** ~$10-15/month (Cloud Monitoring + Logs)

#### 10.1 Enable Cloud Monitoring
- [ ] Create monitoring workspace for pgp-live
- [ ] Enable Cloud Logging API
- [ ] Configure log retention (30 days default)

#### 10.2 Create Alerting Policies
- [ ] **Database Connection Errors** - Alert if >10 errors in 5 minutes
- [ ] **Cloud Run 5xx Errors** - Alert if >50 errors in 5 minutes
- [ ] **Cloud Tasks Queue Backlog** - Alert if queue depth >1000
- [ ] **Payment Processing Failures** - Alert if payment failure rate >5%
- [ ] **ChangeNow API Failures** - Alert if API error rate >10%
- [ ] **Telegram Bot Errors** - Alert if bot error rate >5%
- [ ] **Cloud SQL CPU Usage** - Alert if CPU >80% for 10 minutes
- [ ] **Cloud SQL Memory Usage** - Alert if memory >90% for 10 minutes
- [ ] **Cloud Run Memory Usage** - Alert if any service >90% memory

#### 10.3 Create Dashboards
- [ ] **Payment Dashboard** - Payments/hour, revenue, success rate
- [ ] **Service Health Dashboard** - Latency, errors, request rate
- [ ] **Database Dashboard** - Connections, queries/sec, slow queries
- [ ] **Payout Dashboard** - Pending payouts, batch status, swap success

#### 10.4 Configure Log Sinks (Optional)
```bash
# Export error logs to BigQuery for analysis
gcloud logging sinks create pgp-error-logs \
  bigquery.googleapis.com/projects/pgp-live/datasets/error_logs \
  --log-filter='severity>=ERROR' \
  --project=pgp-live
```

---

### PHASE 11: Testing & Validation

**⏱️ Duration:** 3-5 days
**Budget Impact:** $0 (testing only, uses existing resources)

#### 11.1 Unit Testing
- [ ] Test all base classes in PGP_COMMON
- [ ] Test database connection pooling
- [ ] Test token encryption/decryption
- [ ] Test HMAC signature verification
- [ ] Test wallet validation

#### 11.2 Integration Testing
- [ ] **Payment Flow (End-to-End):**
  - User initiates payment via Telegram bot
  - NOWPayments processes payment
  - IPN webhook received and processed
  - Success callback triggers invite sending
  - User receives Telegram invite
  - Channel owner receives notification
  - Payment accumulated for payout
- [ ] **Payout Flow (End-to-End):**
  - Batch processor detects threshold
  - SPLIT pipeline executes (SPLIT1→SPLIT2→SPLIT3)
  - HOSTPAY pipeline validates and executes (HOSTPAY1→HOSTPAY2→HOSTPAY3)
  - ETH payment sent to client wallet
  - Transaction hash recorded in database
- [ ] **Micro-Batch Flow:**
  - Micro-batch processor detects threshold
  - ETH→USDT conversion via ChangeNow
  - USDT received in hot wallet

#### 11.3 Load Testing (1000 requests/minute)
```bash
# Test PGP_WEBAPI_v1 (customer-facing API)
# Target: 1000 requests/minute sustained for 10 minutes
hey -z 10m -q 17 -c 50 \
  -H "Authorization: Bearer <jwt_token>" \
  https://pgp-webapi-v1-[hash].run.app/api/channels

# Expected results:
# - No 5xx errors
# - Latency p95 < 500ms
# - Latency p99 < 1000ms
# - All requests successful
```

#### 11.4 Security Testing
- [ ] Test HMAC signature verification (invalid signatures rejected)
- [ ] Test IP whitelisting (unauthorized IPs blocked)
- [ ] Test rate limiting (>1000 req/min blocked with 429)
- [ ] Test JWT token expiration (expired tokens rejected)
- [ ] Test SQL injection prevention (parameterized queries)
- [ ] Test XSS prevention (sanitized error responses)
- [ ] Test Redis nonce tracking (replay attacks prevented)

#### 11.5 Failover Testing
- [ ] Kill database connection (services reconnect automatically)
- [ ] Kill Redis connection (services gracefully degrade)
- [ ] Simulate ChangeNow API failure (Cloud Tasks retry)
- [ ] Simulate Telegram API failure (Cloud Tasks retry)
- [ ] Simulate blockchain RPC failure (Cloud Tasks retry)

---

### PHASE 12: Production Hardening & Go-Live

**⏱️ Duration:** 2-3 days
**Budget Impact:** $0 (configuration only)

#### 12.1 Final Security Checklist
- [ ] All secrets stored in Secret Manager (never in code)
- [ ] All service accounts follow principle of least privilege
- [ ] All Cloud Run services require authentication
- [ ] Load Balancer handles all external traffic
- [ ] Cloud Armor rate limiting enabled
- [ ] IP whitelisting configured for webhooks
- [ ] HMAC signatures verified on all webhooks
- [ ] Redis nonce tracking enabled (replay attack prevention)
- [ ] Database uses private IP only (no public access)
- [ ] SSL/TLS certificates configured (HTTPS only)

#### 12.2 Performance Optimization
- [ ] Enable Cloud CDN for static assets (if applicable)
- [ ] Configure connection pooling (Cloud SQL Connector)
- [ ] Enable query caching (PostgreSQL)
- [ ] Optimize database indexes (slow query analysis)
- [ ] Enable Cloud Run request compression

#### 12.3 Backup & Disaster Recovery
- [ ] Verify daily database backups enabled (7-day retention)
- [ ] Test database restore from backup
- [ ] Document disaster recovery runbook
- [ ] Configure Cloud SQL Point-in-Time Recovery (PITR)
- [ ] Export critical secrets to secure offline storage

#### 12.4 Documentation
- [ ] Update all service URLs in documentation
- [ ] Update API documentation (Postman collection)
- [ ] Create operations runbook
- [ ] Create incident response plan
- [ ] Document rollback procedures

#### 12.5 Go-Live Checklist
- [ ] ✅ All 15 services deployed and healthy
- [ ] ✅ All 17 Cloud Tasks queues created
- [ ] ✅ All 2 Cloud Scheduler jobs created
- [ ] ✅ Database schema deployed and verified
- [ ] ✅ All 75+ secrets configured
- [ ] ✅ Load Balancer configured with Cloud Armor
- [ ] ✅ Monitoring and alerting configured
- [ ] ✅ DNS records updated (Cloudflare)
- [ ] ✅ NOWPayments webhook URLs updated
- [ ] ✅ Telegram bot configured (polling or webhook)
- [ ] ✅ End-to-end payment flow tested
- [ ] ✅ End-to-end payout flow tested
- [ ] ✅ Load testing passed (1000 req/min)
- [ ] ✅ Security testing passed
- [ ] ✅ Failover testing passed
- [ ] ✅ Backup and restore tested

---

## 💰 COST BREAKDOWN & BUDGET ANALYSIS

### Monthly Cost Estimate (Target: $200/month)

| Component | Configuration | Monthly Cost |
|-----------|---------------|--------------|
| **Cloud SQL (PostgreSQL)** | db-custom-2-7680 (2 vCPU, 7.5GB RAM, 10GB SSD) | ~$70-80 |
| **Redis (Memorystore)** | Basic tier, 1GB | ~$15-20 |
| **Cloud Run Services (15)** | Total across all services | ~$80-100 |
| ├─ PGP_WEBAPI_v1 | 4 CPU, 8GB RAM, 0-10 instances | ~$50-60 |
| ├─ PGP_SERVER_v1 | 1 CPU, 1GB RAM, 1-20 instances | ~$20-25 |
| ├─ Other 13 services | 512MB RAM each | ~$10-15 |
| **Cloud Tasks** | 17 queues, ~100K operations/month | ~$0.40 |
| **Cloud Scheduler** | 3 jobs | ~$0.30 |
| **Cloud Logging** | 10GB/month | ~$5 |
| **Cloud Monitoring** | Standard metrics | ~$5 |
| **Load Balancer** | Global HTTPS LB | ~$18 |
| **Cloud Armor** | Security policy + rules | ~$7 |
| **Secret Manager** | 75 secrets, 100K accesses/month | ~$0.36 |
| **Networking** | Egress traffic (10GB/month) | ~$1.20 |
| **TOTAL (Standard)** | | **~$202-237/month** |

### Cost Optimization Strategies (Target: $200/month)

**🎯 Optimized Configuration ($195-205/month):**

1. **Cloud SQL Optimization** - Reduce to shared-core-1 during low traffic
   - **Savings:** ~$20-30/month
   - **Trade-off:** Lower performance, suitable for <500 req/min

2. **Cloud Run Optimization** - Reduce min instances to 0 for all services
   - **Savings:** ~$15-20/month
   - **Trade-off:** Cold start latency (1-3 seconds)

3. **Redis Optimization** - Use Redis 5.0 instead of 6.x
   - **Savings:** ~$5/month
   - **Trade-off:** Fewer features

4. **Logging Optimization** - Reduce retention to 7 days, exclude debug logs
   - **Savings:** ~$3-5/month
   - **Trade-off:** Less audit trail

**🔴 Critical: Do NOT Reduce:**
- PGP_WEBAPI_v1 resources (4CPU, 8GB RAM) - Customer-facing
- Database backups (7-day retention) - Disaster recovery
- Cloud Armor (DDoS protection) - Security
- HMAC authentication (replay attack prevention) - Security

### Scaling Projections (1000 requests/minute)

**Current Configuration (1000 req/min):**
- PGP_WEBAPI_v1: Can handle 1000 req/min with 4 CPU, 8GB RAM
- Cloud SQL: 2 vCPU, 7.5GB RAM supports ~500 concurrent connections
- Redis: 1GB supports ~10K operations/sec
- Load Balancer: Auto-scales infinitely
- Cloud Run: Auto-scales to 100 instances per service

**If Traffic Increases to 5000 req/min:**
- Upgrade Cloud SQL to db-custom-4-15360 (4 vCPU, 15GB RAM) → +$80/month
- Increase PGP_WEBAPI_v1 max instances to 20 → +$100/month
- Upgrade Redis to Standard tier, 5GB → +$100/month
- **New Total:** ~$480-520/month

---

## 🔒 SECURITY BEST PRACTICES

### Implemented Security Measures

1. **HMAC-SHA256 Signature Verification** (All Cloud Tasks)
2. **SHA-512 Signature Verification** (NOWPayments IPN)
3. **JWT Authentication** (PGP_WEBAPI_v1)
4. **IP Whitelisting** (PGP_SERVER_v1 webhooks)
5. **Cloud Armor Rate Limiting** (1000 req/min per IP)
6. **Redis Nonce Tracking** (Replay attack prevention)
7. **Parameterized SQL Queries** (SQL injection prevention)
8. **Error Sanitization** (No stack traces in responses)
9. **Secret Manager** (All credentials encrypted at rest)
10. **Private Key Security** (Hot wallet key in Secret Manager only)
11. **TLS Encryption** (All traffic HTTPS only)
12. **Service Account Isolation** (Least privilege IAM)

### Recommended Additional Security (Optional)

- **Cloud KMS** - Encrypt database at rest with customer-managed keys (+$10/month)
- **VPC Service Controls** - Restrict API access to VPC perimeter (+$0)
- **Binary Authorization** - Enforce signed container images (+$0)
- **Cloud Audit Logs** - Enhanced audit trail (+$5-10/month)
- **WAF Custom Rules** - Advanced DDoS protection (+$20-30/month)

---

## 📞 SUPPORT & MAINTENANCE

### Daily Operations
- Monitor Cloud Monitoring dashboards for anomalies
- Review Cloud Logging for errors and warnings
- Check Cloud Tasks queue depths (should be <100)
- Verify Cloud Scheduler jobs executed successfully
- Monitor payment success rate (should be >95%)

### Weekly Operations
- Review database performance (slow queries, connection pools)
- Analyze Cloud Run instance scaling patterns
- Check ChangeNow API success rate
- Verify backup restoration works
- Update dependencies (security patches)

### Monthly Operations
- Review and optimize Cloud SQL indexes
- Analyze cost trends and optimize resources
- Update Secret Manager secrets (rotate API keys)
- Test disaster recovery procedures
- Review and update documentation

---

## 🎉 DEPLOYMENT TIMELINE SUMMARY

### Accelerated Timeline (3-4 weeks)
- **Week 1:** GCP setup, Secret Manager, Cloud SQL, Redis
- **Week 2:** Cloud Tasks, Cloud Run deployment, Cloud Scheduler
- **Week 3:** Load Balancer, monitoring, testing
- **Week 4:** Final hardening, go-live

### Standard Timeline (5-8 weeks)
- **Week 1-2:** GCP setup, Secret Manager, Cloud SQL, Redis
- **Week 3-4:** Cloud Tasks, Cloud Run deployment
- **Week 5:** Cloud Scheduler, Load Balancer, monitoring
- **Week 6-7:** Comprehensive testing, security audits
- **Week 8:** Final hardening, documentation, go-live

---

## 📚 APPENDICES

### A. Secret Manager Quick Reference
All secrets follow naming pattern: `UPPERCASE_SNAKE_CASE`
- Database: `DATABASE_*_SECRET`
- APIs: `*_API_KEY`
- Wallets: `HOST_WALLET_*`
- Signing: `*_SIGNING_KEY`
- URLs: `PGP_*_URL`
- Queues: `PGP_*_QUEUE`

### B. Service Account Email Format
All service accounts follow pattern: `pgp-{service}-v1-sa@pgp-live.iam.gserviceaccount.com`

Example: `pgp-orchestrator-v1-sa@pgp-live.iam.gserviceaccount.com`

### C. Cloud Tasks Queue Naming
All queues follow pattern: `pgp-{service}-v1-{purpose}-queue`

Example: `pgp-split1-v1-callback-queue`

### D. Cloud Run Service Naming
All services follow pattern: `pgp-{service}-v1`

Example: `pgp-orchestrator-v1`

### E. Database Connection String
```
Project: pgp-live
Region: us-central1
Instance: pgp-live-psql
Database: pgp-live-db
Connection: pgp-live:us-central1:pgp-live-psql
```

### F. Critical File Locations
- Deployment scripts: `/TOOLS_SCRIPTS_TESTS/scripts/`
- Database migrations: `/TOOLS_SCRIPTS_TESTS/migrations/pgp-live/`
- Documentation: `/THINK/` and `/ARCHIVES_PGP_v1/11-18_PGP_v1/`
- Service code: `/PGP_X_v1/` (15 service folders)
- Shared library: `/PGP_COMMON/`

### G. External Dependencies
- **NOWPayments API:** https://documenter.getpostman.com/view/7907941/S1a32n38
- **ChangeNow API:** https://documenter.getpostman.com/view/8180765/SVfTPo8f
- **Telegram Bot API:** https://core.telegram.org/bots/api
- **Ethereum RPC:** Alchemy (https://www.alchemy.com/)
- **SendGrid API:** https://docs.sendgrid.com/api-reference

---

**END OF PGP_MAP_UPDATED.md**

**Document Version:** 2.0
**Last Updated:** 2025-11-18
**Prepared For:** pgp-live project deployment
**Maintained By:** PayGatePrime Development Team

For questions or issues, refer to:
- `PROGRESS.md` - Implementation progress tracking
- `DECISIONS.md` - Architectural decision log
- `BUGS.md` - Known issues and bug tracking
- `THINK/AUTO/` - Detailed analysis and planning documents
