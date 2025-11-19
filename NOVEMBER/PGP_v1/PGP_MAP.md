# PGP_MAP.md - PayGatePrime Architecture Map

**Last Updated:** 2025-11-18
**Version:** 1.2 (Updated: PGP_WEB_v1 removed - ghost service)
**Purpose:** Comprehensive mapping of all PGP_X_v1 services in the PayGatePrime Telegram payment gateway system

**⚠️ UPDATE (2025-11-18):**
- **PGP_ACCUMULATOR_v1** has been **REMOVED** - accumulation logic moved inline to PGP_ORCHESTRATOR_v1
- **PGP_WEB_v1** has been **REMOVED** - ghost service with no source code (empty directory)
- The service count is now **15 active services** (down from 18). See PROGRESS.md and DECISIONS.md for details.

---

## 📋 QUICK REFERENCE MAP

**PayGatePrime** is a Telegram-based cryptocurrency payment gateway system that enables channel owners to monetize their Telegram channels through subscriptions and donations.

### Service Categories

```
┌─────────────────────────────────────────────────────────────────┐
│                    PAYGATEPRIME SERVICES                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🤖 USER INTERFACE                                              │
│  ├── PGP_SERVER_v1         → Main Telegram bot & server        │
│  └── PGP_WEBAPI_v1         → REST API backend (no frontend)    │
│                                                                 │
│  💳 PAYMENT PROCESSING                                          │
│  ├── PGP_NP_IPN_v1         → NOWPayments webhook handler       │
│  ├── PGP_ORCHESTRATOR_v1   → Payment processor & orchestrator  │
│  └── PGP_INVITE_v1         → Telegram invite sender            │
│                                                                 │
│  💰 PAYOUT PIPELINE (Subscription Revenue Split)                │
│  ├── PGP_SPLIT1_v1         → Split orchestrator                │
│  ├── PGP_SPLIT2_v1         → USDT→ETH estimator                │
│  ├── PGP_SPLIT3_v1         → ETH→Client currency swapper       │
│  ├── PGP_HOSTPAY1_v1       → Validator & orchestrator          │
│  ├── PGP_HOSTPAY2_v1       → ChangeNow status checker          │
│  └── PGP_HOSTPAY3_v1       → ETH payment executor              │
│                                                                 │
│  ⏰ SCHEDULED PROCESSORS                                        │
│  ├── PGP_BATCHPROCESSOR_v1      → Batch payout (every 5min)   │
│  └── PGP_MICROBATCHPROCESSOR_v1 → Micro-batch (every 15min)   │
│                                                                 │
│  📢 COMMUNICATIONS                                              │
│  ├── PGP_NOTIFICATIONS_v1  → Payment notifications             │
│  └── PGP_BROADCAST_v1      → Broadcast scheduler/executor      │
│                                                                 │
│  📚 SHARED LIBRARY                                              │
│  └── PGP_COMMON            → Base classes & utilities          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow Overview

```
User → Telegram Bot (PGP_SERVER_v1) → Payment Page
    ↓
NOWPayments Payment Processing
    ↓
IPN Webhook (PGP_NP_IPN_v1) → Updates Database
    ↓
Success Callback → PGP_ORCHESTRATOR_v1
    ├→ PGP_INVITE_v1 (sends Telegram invite)
    ├→ PGP_NOTIFICATIONS_v1 (notifies channel owner)
    └→ Inline Accumulation (threshold payouts only)
        ↓
Scheduled Batch Processing:
    ├→ PGP_MICROBATCHPROCESSOR_v1 (ETH→USDT conversion, every 15min)
    └→ PGP_BATCHPROCESSOR_v1 (threshold payout dispatch, every 5min)
        ↓
Payout Pipeline: PGP_SPLIT1_v1 → SPLIT2 → SPLIT3 → HOSTPAY1 → HOSTPAY2 → HOSTPAY3
    ↓
Final Payment to Channel Owner's Wallet
```

---

## 📖 DETAILED SERVICE DESCRIPTIONS

---

### 🤖 PGP_SERVER_v1
**Primary Telegram Bot & Application Server**

**Location:** `/PGP_SERVER_v1/`
**Entry Point:** `pgp_server_v1.py`
**Port:** 5000 (Flask)

#### Purpose
The central user-facing service that runs the Telegram bot and coordinates all bot interactions. This is the primary interface through which users interact with PayGatePrime.

#### Why It Exists
Users need a conversational interface to purchase subscriptions, make donations, and manage their account. Telegram bots provide this interface while maintaining security and ease of use.

#### Critical Unique Functions
1. **Telegram Bot Management**: Handles all Telegram bot commands (`/start`, `/donate`, etc.)
2. **Subscription Management**: Monitors subscription expirations and removes expired users
3. **Conversation Flow**: Manages donation input workflows and keypad states
4. **Payment Link Generation**: Creates NOWPayments payment links
5. **Invite Link Management**: Generates and sends one-time Telegram invite links
6. **Flask Webhook Server**: Receives callbacks from PGP_ORCHESTRATOR_v1 and other services
7. **Security Services**: HMAC authentication, IP whitelisting, rate limiting

#### Key Components
- `app_initializer.py` - Application initialization
- `server_manager.py` - Flask server management
- `bot/` - Telegram bot handlers and conversations
- `models/connection_pool.py` - Database connection management
- `services/payment_service.py` - Payment processing logic
- `services/notification_service.py` - Notification handling
- `security/` - HMAC, IP whitelisting, rate limiting

#### Dependencies
- Uses PGP_COMMON for base classes
- Receives webhooks from PGP_ORCHESTRATOR_v1
- Sends requests to PGP_NOTIFICATIONS_v1
- Connects to PostgreSQL database

---

### ~~🌐 PGP_WEB_v1~~ (REMOVED 2025-11-18)
**⚠️ Ghost Service - Empty Directory with No Source Code**

**Status:** REMOVED (archived to `ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/PGP_WEB_v1_REMOVED_20251118/`)

**Removal Rationale:**
- Service was an **empty directory** containing only:
  - 1 HTML file referencing non-existent `/src/main.tsx`
  - 1 `.env.example` with stale reference to old `GCRegisterAPI`
  - Empty `dist/` directory (no build output)
  - `node_modules/` with dependencies but **zero source code**
- **No React/TypeScript files existed** - documentation described planned features that were never implemented
- Cannot be deployed (no Dockerfile, no source code)
- No service references or depends on PGP_WEB_v1

**Current State:**
- PGP_WEBAPI_v1 remains as a **standalone REST API** that can be called directly
- If frontend is needed in future, build new React app and deploy to Cloud Storage/CDN
- PGP_WEBAPI_v1 already has CORS enabled and JWT authentication for frontend integration

**Cost Savings:** Minimal (eliminated service account overhead, reduced confusion)

**See:** `THINK/AUTO/PGP_WEB_v1_CLEANUP_CHECKLIST.md`, `PROGRESS.md` (2025-11-18), `DECISIONS.md` (Decision 14.1)

---

### 🔌 PGP_WEBAPI_v1
**REST API Backend for Channel Registration**

**Location:** `/PGP_WEBAPI_v1/`
**Entry Point:** `pgp_webapi_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Provides a stateless REST API backend for channel registration, handling authentication, channel management, and account operations. Currently operates as a **standalone API service** (no frontend exists - PGP_WEB_v1 was removed as ghost service).

#### Why It Exists
Provides programmatic access to channel registration and management functionality. Can be called directly via API clients (Postman, curl) or integrated with a future frontend if needed. CORS is already enabled for frontend integration.

#### Critical Unique Functions
1. **JWT Authentication**: Stateless token-based auth
2. **User Registration**: Email-based account creation
3. **Channel Registration**: Telegram channel validation and registration
4. **Subscription Tier Management**: CRUD operations for pricing tiers
5. **Payout Configuration**: Wallet address validation and storage
6. **Email Services**: SendGrid integration for emails

#### Key Components
- `api/routes/auth.py` - Authentication endpoints
- `api/routes/account.py` - Account management
- `api/routes/channels.py` - Channel operations
- `api/routes/mappings.py` - Tier and payout mappings
- `api/middleware/rate_limiter.py` - Rate limiting

#### Dependencies
- Uses PGP_COMMON for base classes
- Connects to PostgreSQL database
- SendGrid for email delivery
- JWT for authentication

---

### 💳 PGP_NP_IPN_v1
**NOWPayments IPN Webhook Handler**

**Location:** `/PGP_NP_IPN_v1/`
**Entry Point:** `pgp_np_ipn_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Receives Instant Payment Notification (IPN) callbacks from NOWPayments API when payment status changes occur. Updates the database with payment_id and metadata.

#### Why It Exists
NOWPayments sends IPNs separately from the success callback. These IPNs contain critical payment_id information needed to track payments in NOWPayments' system.

#### Critical Unique Functions
1. **IPN Signature Verification**: Validates HMAC-SHA512 signatures from NOWPayments
2. **Payment ID Storage**: Updates database with NOWPayments payment_id
3. **Payment Status Tracking**: Records payment status changes
4. **Payment Metadata Storage**: Stores outcome_amount, actual_price_usd, etc.
5. **Payment Processing Page**: Serves the payment-processing.html page

#### Key Components
- **POST /** - Main IPN webhook endpoint
- **GET /payment-processing** - Serves payment processing page
- **GET /api/payment-status/:unique_id** - Payment status API
- SHA-512 signature verification
- CryptoPricingClient for fallback pricing

#### Dependencies
- Uses PGP_COMMON utilities (verify_sha512_signature, CryptoPricingClient)
- Connects to PostgreSQL database
- Receives IPNs from NOWPayments

---

### 💼 PGP_ORCHESTRATOR_v1
**Payment Success Processor & Task Orchestrator**

**Location:** `/PGP_ORCHESTRATOR_v1/`
**Entry Point:** `pgp_orchestrator_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Receives success_url callbacks from NOWPayments, processes payment confirmations, writes to database, and orchestrates downstream tasks via Cloud Tasks.

#### Why It Exists
After successful payment, multiple actions must be coordinated: sending Telegram invites, notifying channel owners, and accumulating funds for payout. This service orchestrates all post-payment workflows.

#### Critical Unique Functions
1. **Success URL Processing**: Decrypts and validates success_url tokens from NOWPayments
2. **Payment Recording**: Writes payment records to `processed_payments` table
3. **Subscription Expiration Calculation**: Calculates expire_time and expire_date
4. **Task Orchestration**: Enqueues Cloud Tasks to:
   - PGP_INVITE_v1 (send Telegram invite)
   - PGP_NOTIFICATIONS_v1 (notify channel owner)
   - PGP_ACCUMULATOR_v1 (accumulate for payout)
5. **Token Encryption**: Creates encrypted tokens for secure inter-service communication

#### Key Components
- **POST /** - Main success_url webhook endpoint
- **GET /health** - Health check endpoint
- Token decryption and validation
- Database operations for payment recording
- Cloud Tasks client for task creation

#### Dependencies
- Uses PGP_COMMON for base classes
- Connects to PostgreSQL database
- Creates tasks in Cloud Tasks queues:
  - `pgp-invite-v1-queue`
  - `pgp-notifications-v1-queue`
  - `pgp-accumulator-v1-queue`

---

### 📨 PGP_INVITE_v1
**Telegram Invite Link Sender**

**Location:** `/PGP_INVITE_v1/`
**Entry Point:** `pgp_invite_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Receives encrypted tokens from PGP_ORCHESTRATOR_v1 via Cloud Tasks, generates one-time Telegram invite links, and sends them to users who have paid for subscriptions.

#### Why It Exists
After payment confirmation, users need to be added to the private Telegram channel. This service handles the invitation process with retry logic for resilience.

#### Critical Unique Functions
1. **Token Decryption**: Decrypts payment tokens from PGP_ORCHESTRATOR_v1
2. **Invite Link Generation**: Creates one-time Telegram invite links using Bot API
3. **Payment Validation**: Verifies payment amounts before sending invites
4. **Direct Message Sending**: Sends invite links via Telegram DM
5. **Event Loop Management**: Uses asyncio.run() for isolated event loops (Cloud Run optimized)

#### Key Components
- **POST /** - Main webhook endpoint
- **GET /health** - Health check endpoint
- Telegram Bot instance (created per-request)
- Payment validation logic
- Cloud Tasks retry handling (infinite retry with 60s backoff)

#### Architecture Note
Uses SYNCHRONOUS Flask route with `asyncio.run()` to create isolated event loops for each request. This prevents "Event loop is closed" errors in serverless Cloud Run environments.

#### Dependencies
- Uses PGP_COMMON for base classes
- Connects to PostgreSQL database for payment validation
- python-telegram-bot library
- Triggered by Cloud Tasks from PGP_ORCHESTRATOR_v1

---

### 📬 PGP_NOTIFICATIONS_v1
**Payment Notification Service**

**Location:** `/PGP_NOTIFICATIONS_v1/`
**Entry Point:** `pgp_notifications_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Sends payment notifications to channel owners via Telegram when users purchase subscriptions or make donations. Provides real-time revenue alerts.

#### Why It Exists
Channel owners need to be notified when they receive payments. This service formats and delivers professional notification messages via Telegram.

#### Critical Unique Functions
1. **Notification Formatting**: Creates formatted payment notification messages
2. **Channel Owner Lookup**: Retrieves channel owner's Telegram user_id from database
3. **Telegram Message Sending**: Delivers notifications via Telegram Bot API
4. **Payment Type Handling**: Different message formats for subscriptions vs donations
5. **Error Handling**: Graceful handling of notification failures

#### Key Components
- **POST /send-notification** - Main notification endpoint
- **GET /health** - Health check endpoint
- `notification_handler.py` - Notification logic
- `telegram_client.py` - Telegram Bot API wrapper
- Message templates for subscriptions and donations

#### Dependencies
- Uses PGP_COMMON for logging
- Connects to PostgreSQL database
- python-telegram-bot library
- Triggered by Cloud Tasks from PGP_ORCHESTRATOR_v1

---

### ~~💰 PGP_ACCUMULATOR_v1~~ (REMOVED 2025-11-18)
**⚠️ Service Deprecated - Logic Moved Inline to PGP_ORCHESTRATOR_v1**

**Status:** REMOVED (archived to `ARCHIVES_PGP_v1/REMOVED_DEAD_CODE/PGP_ACCUMULATOR_v1_REMOVED_20251118/`)

**Removal Rationale:**
- Service performed only simple fee calculation (3% TelePay fee) and database write
- No orchestration logic or complex business rules
- Added ~200-300ms latency overhead from Cloud Task invocation
- Moved inline to PGP_ORCHESTRATOR_v1 for performance (52 lines of code)
- Database method centralized to `PGP_COMMON.insert_payout_accumulation_pending()`

**Migration:**
- Fee calculation logic moved inline to PGP_ORCHESTRATOR_v1 (lines 388-440)
- Database write uses `BaseDatabaseManager.insert_payout_accumulation_pending()` in PGP_COMMON
- Cloud Task to PGP_SPLIT2_v1 removed (no longer needed - MICROBATCH handles conversion)

**Cost Savings:** ~$20/month (~$241/year)

**See:** `THINK/AUTO/PGP_THRESHOLD_REVIEW.md`, `PROGRESS.md` (2025-11-18), `DECISIONS.md` (Decision 13.1)

---

### ⏰ PGP_BATCHPROCESSOR_v1
**Scheduled Batch Payout Processor**

**Location:** `/PGP_BATCHPROCESSOR_v1/`
**Entry Point:** `pgp_batchprocessor_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Triggered by Cloud Scheduler every 5 minutes. Queries `payout_accumulation` table for clients over threshold ($50 default), creates batch records, and initiates USDT→ClientCurrency swaps.

#### Why It Exists
Payouts must be batched to minimize transaction costs and API calls. This scheduler detects when accumulated amounts reach threshold and triggers the payout pipeline.

#### Critical Unique Functions
1. **Threshold Detection**: Queries database for clients >= $50 (configurable)
2. **Batch Record Creation**: Creates records in `batch_conversions` table
3. **Batch ID Generation**: Generates UUID batch identifiers
4. **Task Orchestration**: Enqueues Cloud Tasks to PGP_SPLIT1_v1 for swap execution
5. **Accumulation Marking**: Marks accumulated payments as `paid_out`

#### Key Components
- **POST /process** - Main batch processing endpoint
- **GET /health** - Health check endpoint
- Threshold query logic
- Batch creation logic
- Cloud Tasks client

#### Dependencies
- Uses PGP_COMMON for base classes
- Connects to PostgreSQL database
- Creates tasks in `pgp-split1-v1-queue`
- Triggered by Cloud Scheduler (every 5 minutes)

---

### 🔄 PGP_MICROBATCHPROCESSOR_v1
**Scheduled Micro-Batch ETH→USDT Conversion**

**Location:** `/PGP_MICROBATCHPROCESSOR_v1/`
**Entry Point:** `pgp_microbatchprocessor_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Triggered by Cloud Scheduler every 15 minutes. Checks total pending USD in `payout_accumulation`, and if >= threshold, creates a single ETH→USDT swap to eliminate volatility risk.

#### Why It Exists
Accumulated ETH payments are subject to price volatility. This service periodically converts ETH to stablecoin USDT to protect channel owner revenue from price fluctuations.

#### Critical Unique Functions
1. **Threshold Checking**: Sums total pending USD from `payout_accumulation`
2. **Batch ETH→USDT Swap**: Creates ChangeNow fixed-rate swap
3. **Batch Conversion Recording**: Records swap in `batch_conversions` table
4. **Accumulation Status Update**: Marks payments as `swapping`
5. **Task Queuing**: Enqueues Cloud Task to PGP_HOSTPAY1_v1 for execution

#### Key Components
- **POST /check-threshold** - Main threshold check endpoint
- **GET /health** - Health check endpoint
- ChangeNow API client
- Threshold calculation logic
- Cloud Tasks client

#### Dependencies
- Uses PGP_COMMON for base classes and ChangeNowClient
- Connects to PostgreSQL database
- Creates tasks in `pgp-hostpay1-v1-queue`
- Triggered by Cloud Scheduler (every 15 minutes)

---

### 🎯 PGP_SPLIT1_v1
**Payment Splitting Orchestrator**

**Location:** `/PGP_SPLIT1_v1/`
**Entry Point:** `pgp_split1_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Orchestrates the payment splitting workflow across PGP_SPLIT2_v1 (estimation) and PGP_SPLIT3_v1 (swap creation). Manages database state transitions and integrates final payment execution.

#### Why It Exists
The payout pipeline requires coordination between multiple services (estimation, swap creation, payment execution). This orchestrator manages the complex multi-step workflow.

#### Critical Unique Functions
1. **Workflow Orchestration**: Coordinates USDT→ETH→ClientCurrency conversion pipeline
2. **State Management**: Updates `split_payout_que` table through workflow stages
3. **Token Encryption**: Creates encrypted tokens for inter-service communication
4. **Callback Handling**: Receives callbacks from PGP_SPLIT2_v1 and PGP_SPLIT3_v1
5. **Error Handling**: Manages retry logic and failure states
6. **Final Execution**: Enqueues tasks to PGP_HOSTPAY1_v1 for payment

#### Endpoints
- **POST /** - Initial payment split request (from PGP_BATCHPROCESSOR_v1)
- **POST /pgp-split2-callback** - ETH estimate callback (from PGP_SPLIT2_v1)
- **POST /pgp-split3-callback** - Swap creation callback (from PGP_SPLIT3_v1)
- **GET /health** - Health check endpoint

#### Workflow
1. Receives batch from PGP_BATCHPROCESSOR_v1
2. Queries `batch_conversions` for ChangeNow details
3. Enqueues PGP_SPLIT2_v1 for USDT→ETH estimate
4. Receives callback from PGP_SPLIT2_v1
5. Enqueues PGP_SPLIT3_v1 for ETH→ClientCurrency swap
6. Receives callback from PGP_SPLIT3_v1
7. Enqueues PGP_HOSTPAY1_v1 for final payment execution

#### Dependencies
- Uses PGP_COMMON for base classes
- Connects to PostgreSQL database
- Creates tasks in:
  - `pgp-split2-v1-queue`
  - `pgp-split3-v1-queue`
  - `pgp-hostpay1-v1-queue`

---

### 📊 PGP_SPLIT2_v1
**USDT→ETH Estimator Service**

**Location:** `/PGP_SPLIT2_v1/`
**Entry Point:** `pgp_split2_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Receives encrypted tokens from PGP_SPLIT1_v1, calls ChangeNow API v2 for USDT→ETH estimates, and returns encrypted responses back via Cloud Tasks.

#### Why It Exists
Before creating a swap, we need to estimate how much ETH we'll receive for our USDT. This service isolates the estimation logic with infinite retry for API resilience.

#### Critical Unique Functions
1. **Token Decryption**: Decrypts request tokens from PGP_SPLIT1_v1
2. **ChangeNow Estimate API**: Calls `/v2/exchange/estimated-amount` endpoint
3. **Estimate Validation**: Validates API response and estimated amounts
4. **Token Encryption**: Creates encrypted response tokens
5. **Callback Queue**: Enqueues Cloud Task back to PGP_SPLIT1_v1
6. **Infinite Retry**: Cloud Tasks retry for API failures

#### Key Components
- **POST /** - Main estimate endpoint
- **GET /health** - Health check endpoint
- ChangeNowClient integration (hot-reload enabled)
- Token encryption/decryption
- Cloud Tasks client

#### Dependencies
- Uses PGP_COMMON for base classes and ChangeNowClient
- Creates tasks in `pgp-split1-v1-callback-queue`
- Triggered by Cloud Tasks from PGP_SPLIT1_v1

---

### 🔄 PGP_SPLIT3_v1
**ETH→ClientCurrency Swap Creator**

**Location:** `/PGP_SPLIT3_v1/`
**Entry Point:** `pgp_split3_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Receives encrypted tokens from PGP_SPLIT1_v1, creates ChangeNow fixed-rate transactions for ETH→ClientCurrency swaps, and returns encrypted responses with full transaction details.

#### Why It Exists
After estimating ETH amount, we need to create the actual swap transaction with the client's payout address. This service handles swap creation with infinite retry resilience.

#### Critical Unique Functions
1. **Token Decryption**: Decrypts swap request tokens from PGP_SPLIT1_v1
2. **ChangeNow Fixed-Rate Swap**: Creates swap transaction via `/v2/exchange` endpoint
3. **Transaction Recording**: Returns swap_id, payin_address, payinExtraId
4. **Token Encryption**: Creates encrypted response with transaction details
5. **Callback Queue**: Enqueues Cloud Task back to PGP_SPLIT1_v1
6. **Infinite Retry**: Cloud Tasks retry for API failures

#### Key Components
- **POST /** - Main swap creation endpoint
- **GET /health** - Health check endpoint
- ChangeNowClient integration (hot-reload enabled)
- Token encryption/decryption
- Cloud Tasks client

#### Dependencies
- Uses PGP_COMMON for base classes and ChangeNowClient
- Creates tasks in `pgp-split1-v1-callback-queue`
- Triggered by Cloud Tasks from PGP_SPLIT1_v1

---

### 🎯 PGP_HOSTPAY1_v1
**Payment Validator & Orchestrator**

**Location:** `/PGP_HOSTPAY1_v1/`
**Entry Point:** `pgp_hostpay1_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Validates payment split requests from PGP_SPLIT1_v1 and orchestrates the final payment execution workflow across PGP_HOSTPAY2_v1 (status check) and PGP_HOSTPAY3_v1 (ETH payment).

#### Why It Exists
Before executing final ETH payment to client's address, we must verify ChangeNow swap status. This orchestrator coordinates the validation and payment execution steps.

#### Critical Unique Functions
1. **Token Decryption**: Decrypts payment request tokens
2. **ChangeNow Validation**: Enqueues PGP_HOSTPAY2_v1 for status check
3. **Callback Handling**: Receives status verification from PGP_HOSTPAY2_v1
4. **Payment Orchestration**: Enqueues PGP_HOSTPAY3_v1 for ETH payment
5. **Completion Callback**: Receives payment confirmation from PGP_HOSTPAY3_v1
6. **Database Updates**: Updates `split_payout_que` with transaction details

#### Endpoints
- **POST /** - Initial payment request (from PGP_SPLIT1_v1)
- **POST /status-verified** - Status check callback (from PGP_HOSTPAY2_v1)
- **POST /payment-completed** - Payment execution callback (from PGP_HOSTPAY3_v1)
- **GET /health** - Health check endpoint

#### Workflow
1. Receives payment request from PGP_SPLIT1_v1
2. Enqueues PGP_HOSTPAY2_v1 for ChangeNow status check
3. Receives status verification callback
4. Enqueues PGP_HOSTPAY3_v1 for ETH payment execution
5. Receives payment completion callback
6. Updates database with final transaction details

#### Dependencies
- Uses PGP_COMMON for base classes
- Connects to PostgreSQL database
- Creates tasks in:
  - `pgp-hostpay2-v1-queue`
  - `pgp-hostpay3-v1-queue`

---

### ✅ PGP_HOSTPAY2_v1
**ChangeNow Status Checker**

**Location:** `/PGP_HOSTPAY2_v1/`
**Entry Point:** `pgp_hostpay2_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Receives encrypted tokens from PGP_HOSTPAY1_v1, checks ChangeNow transaction status, and returns encrypted verification responses.

#### Why It Exists
Before sending ETH payment, we must verify that the ChangeNow swap has completed successfully. This service isolates status checking with infinite retry.

#### Critical Unique Functions
1. **Token Decryption**: Decrypts status check request tokens
2. **ChangeNow Status API**: Calls `/v2/exchange/by-id` endpoint
3. **Status Validation**: Verifies swap is in 'finished' or acceptable state
4. **Actual Amount Recording**: Captures actual_usdt_received from ChangeNow
5. **Token Encryption**: Creates encrypted verification response
6. **Callback Queue**: Enqueues Cloud Task back to PGP_HOSTPAY1_v1

#### Key Components
- **POST /** - Main status check endpoint
- **GET /health** - Health check endpoint
- ChangeNow status API integration
- Token encryption/decryption
- Cloud Tasks client

#### Dependencies
- Uses PGP_COMMON for base classes and ChangeNowClient
- Creates tasks in `pgp-hostpay1-v1-callback-queue`
- Triggered by Cloud Tasks from PGP_HOSTPAY1_v1

---

### 💸 PGP_HOSTPAY3_v1
**ETH Payment Executor**

**Location:** `/PGP_HOSTPAY3_v1/`
**Entry Point:** `pgp_hostpay3_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Receives encrypted tokens from PGP_HOSTPAY1_v1, executes final ETH payment to client's wallet address, and returns encrypted completion responses with transaction hash.

#### Why It Exists
After ChangeNow swap verification, we must send the ETH to the client's payout address. This service handles the actual blockchain transaction execution.

#### Critical Unique Functions
1. **Token Decryption**: Decrypts payment execution request tokens
2. **ETH Payment Execution**: Sends ETH to client's wallet using Web3
3. **Transaction Hash Recording**: Captures blockchain transaction hash
4. **Payment Verification**: Confirms transaction success
5. **Token Encryption**: Creates encrypted completion response with tx_hash
6. **Callback Queue**: Enqueues Cloud Task back to PGP_HOSTPAY1_v1

#### Key Components
- **POST /** - Main payment execution endpoint
- **GET /health** - Health check endpoint
- Web3 integration for ETH transactions
- Wallet management (hot wallet)
- Token encryption/decryption
- Cloud Tasks client

#### Dependencies
- Uses PGP_COMMON for base classes
- Web3.py library for Ethereum transactions
- Creates tasks in `pgp-hostpay1-v1-callback-queue`
- Triggered by Cloud Tasks from PGP_HOSTPAY1_v1

---

### 📢 PGP_BROADCAST_v1
**Broadcast Scheduler & Executor**

**Location:** `/PGP_BROADCAST_v1/`
**Entry Point:** `pgp_broadcast_v1.py`
**Port:** 8080 (Flask)

#### Purpose
Provides automated and manual broadcast messaging to Telegram channels. Includes scheduling, execution tracking, and web API for frontend control.

#### Why It Exists
Channel owners need to send announcements and broadcasts to their subscribers. This service provides reliable scheduled and manual broadcasting with tracking.

#### Critical Unique Functions
1. **Broadcast Scheduling**: Cloud Scheduler triggers for automated broadcasts
2. **Broadcast Execution**: Sends messages to Telegram channels
3. **Message Tracking**: Tracks broadcast status and delivery
4. **Web API**: REST endpoints for broadcast management
5. **JWT Authentication**: Secures API endpoints
6. **CORS Support**: Enables potential future frontend integration

#### Key Components
- `broadcast_scheduler.py` - Scheduling logic
- `broadcast_executor.py` - Message sending
- `broadcast_tracker.py` - Delivery tracking
- `broadcast_web_api.py` - REST API endpoints
- `telegram_client.py` - Telegram Bot API wrapper

#### Endpoints
- **POST /execute** - Execute scheduled broadcasts
- **POST /api/broadcasts/manual** - Manual broadcast
- **GET /api/broadcasts/history** - Broadcast history
- **GET /health** - Health check

#### Dependencies
- Uses PGP_COMMON for logging
- Connects to PostgreSQL database
- python-telegram-bot library
- Flask-JWT-Extended for authentication
- Triggered by Cloud Scheduler (configurable intervals)

---

### 📚 PGP_COMMON
**Shared Library for All PGP_v1 Services**

**Location:** `/PGP_COMMON/`
**Package Type:** Installable Python package
**Installation:** `pip install -e ../PGP_COMMON`

#### Purpose
Eliminates code duplication by providing base classes and utilities shared across all PGP_v1 microservices. Single source of truth for common functionality.

#### Why It Exists
Without shared libraries, each service would duplicate configuration, database, token, and Cloud Tasks logic. This would lead to ~7,250 lines of duplicate code and maintenance nightmares.

#### Critical Unique Functions

**Base Classes:**
1. **BaseConfigManager** - Secret Manager and configuration management
2. **BaseCloudTasksClient** - Cloud Tasks operations and HMAC signing
3. **BaseDatabaseManager** - Database connection and query execution
4. **BaseTokenManager** - Token encryption, decryption, and signature generation

**Utilities:**
5. **ChangeNowClient** - ChangeNow API integration (hot-reload enabled)
6. **CryptoPricingClient** - Cryptocurrency pricing fallback
7. **RedisClient** - Redis operations for nonce tracking
8. **Error Sanitization** - Security utilities for error responses
9. **Webhook Authentication** - SHA-256 and SHA-512 signature verification
10. **Wallet Validation** - Cryptocurrency wallet address validation
11. **IP Extraction** - Extract real IP from Cloud Run headers
12. **Centralized Logging** - Standardized logging with emoji support

#### Package Structure
```
PGP_COMMON/
├── __init__.py
├── setup.py
├── README.md
├── config/
│   └── base_config.py         # BaseConfigManager
├── cloudtasks/
│   └── base_client.py         # BaseCloudTasksClient
├── database/
│   └── db_manager.py          # BaseDatabaseManager
├── tokens/
│   ├── base_token.py          # BaseTokenManager
│   └── token_formats.py       # Token format definitions
├── logging/
│   └── base_logger.py         # Centralized logging
├── auth/
│   └── service_auth.py        # Service authentication
└── utils/
    ├── changenow_client.py    # ChangeNow API client
    ├── crypto_pricing.py      # Crypto pricing fallback
    ├── redis_client.py        # Redis client
    ├── error_sanitizer.py     # Error sanitization
    ├── webhook_auth.py        # Webhook signature verification
    ├── wallet_validation.py   # Wallet address validation
    └── ip_extraction.py       # IP extraction utilities
```

#### Benefits
- **60% Code Reduction**: Eliminates ~7,250 lines of duplicate code
- **Single Source of Truth**: Update common methods in one place
- **Consistent Behavior**: All services use the same patterns
- **Easier Maintenance**: Bug fixes propagate to all services
- **Better Testing**: Test base classes once instead of 17 times

#### Usage Example
```python
from PGP_COMMON.config import BaseConfigManager
from PGP_COMMON.database import BaseDatabaseManager
from PGP_COMMON.cloudtasks import BaseCloudTasksClient
from PGP_COMMON.tokens import BaseTokenManager

# All services extend these base classes
class ConfigManager(BaseConfigManager):
    def __init__(self):
        super().__init__(service_name="PGP_ORCHESTRATOR_v1")
```

#### Dependencies
- google-cloud-secret-manager
- google-cloud-tasks
- cloud-sql-python-connector
- pg8000
- redis
- requests
- web3

---

## 🔐 SECURITY ARCHITECTURE

### Authentication Methods

1. **HMAC-SHA256 Signature** (Cloud Tasks)
   - All inter-service Cloud Tasks requests
   - Signed with `SUCCESS_URL_SIGNING_KEY`
   - Timestamp validation (nonce tracking via Redis)

2. **SHA-512 Signature** (NOWPayments IPN)
   - IPN webhooks from NOWPayments
   - Signed with `NOWPAYMENTS_IPN_SECRET`

3. **JWT Authentication** (Web API)
   - PGP_WEBAPI_v1 endpoints
   - Stateless token-based auth
   - 15-minute access tokens, 30-day refresh tokens

4. **IP Whitelisting**
   - PGP_SERVER_v1 webhook endpoints
   - Cloud Run internal IPs only

### Secret Management

All secrets stored in Google Cloud Secret Manager:
- Database credentials (hot-reload enabled)
- API keys (NOWPayments, ChangeNow, SendGrid)
- Signing keys (HMAC, JWT)
- Bot tokens (Telegram)

---

## 📊 DATABASE ARCHITECTURE

### Primary Database
**Cloud SQL PostgreSQL** (`pgp-live:us-central1:pgp-telepaypsql`)

### Key Tables

1. **client_table** - Channel owner registration
2. **subscription_tier_map** - Subscription pricing tiers
3. **payout_details** - Payout wallet configuration
4. **processed_payments** - Payment records
5. **payout_accumulation** - Pending payouts
6. **batch_conversions** - Batch swap records
7. **split_payout_que** - Payment split workflow
8. **broadcast_manager** - Broadcast scheduling
9. **donation_keypad_state** - Donation workflow state
10. **conversation_state** - Bot conversation state

---

## 🚀 DEPLOYMENT ARCHITECTURE

### Cloud Run Services (Serverless)
All PGP_X_v1 services deployed to Google Cloud Run:
- **Region:** us-central1
- **Concurrency:** 80 (default)
- **Min Instances:** 0 (scales to zero)
- **Max Instances:** 100 (default)
- **Memory:** 512Mi - 1Gi (varies by service)
- **CPU:** 1 (default)

### Cloud Scheduler
- **PGP_BATCHPROCESSOR_v1:** Every 5 minutes
- **PGP_MICROBATCHPROCESSOR_v1:** Every 15 minutes
- **PGP_BROADCAST_v1:** Configurable (default: daily)

### Cloud Tasks Queues
1. `pgp-orchestrator-v1-queue`
2. `pgp-invite-v1-queue`
3. `pgp-notifications-v1-queue`
4. `pgp-accumulator-v1-queue`
5. `pgp-split1-v1-queue`
6. `pgp-split2-v1-queue`
7. `pgp-split3-v1-queue`
8. `pgp-hostpay1-v1-queue`
9. `pgp-hostpay2-v1-queue`
10. `pgp-hostpay3-v1-queue`
11. Callback queues for each service

---

## 💡 KEY DESIGN PATTERNS

### 1. Microservices Architecture
Each service has a single, well-defined responsibility. Services communicate via Cloud Tasks with encrypted tokens.

### 2. Event-Driven Processing
Cloud Tasks and Cloud Scheduler trigger asynchronous workflows. Services are stateless and scale independently.

### 3. Retry Resilience
Cloud Tasks provides infinite retry with exponential backoff. Services handle transient failures gracefully.

### 4. Token-Based Security
Encrypted tokens carry payment data between services. HMAC signatures prevent tampering.

### 5. Hot-Reload Configuration
Services fetch secrets on-demand from Secret Manager. Configuration changes don't require redeployment.

### 6. Database Connection Pooling
Cloud SQL Connector provides automatic connection management. Services use SQLAlchemy for safe queries.

### 7. Centralized Logging
PGP_COMMON provides standardized logging with emoji indicators. All services use consistent log formats.

---

## 🎯 PAYMENT FLOW SUMMARY

### Subscription Flow
```
1. User → PGP_SERVER_v1 (Telegram bot)
2. PGP_SERVER_v1 → NOWPayments (payment link)
3. User → NOWPayments (payment)
4. NOWPayments → PGP_NP_IPN_v1 (IPN webhook)
5. NOWPayments → PGP_ORCHESTRATOR_v1 (success_url)
6. PGP_ORCHESTRATOR_v1 → PGP_INVITE_v1 (send invite)
7. PGP_ORCHESTRATOR_v1 → PGP_NOTIFICATIONS_v1 (notify owner)
8. PGP_ORCHESTRATOR_v1 → PGP_ACCUMULATOR_v1 (accumulate)
9. Cloud Scheduler → PGP_BATCHPROCESSOR_v1 (every 5min)
10. PGP_BATCHPROCESSOR_v1 → PGP_SPLIT1_v1 (batch payout)
11. PGP_SPLIT1_v1 → PGP_SPLIT2_v1 (estimate)
12. PGP_SPLIT1_v1 → PGP_SPLIT3_v1 (swap)
13. PGP_SPLIT1_v1 → PGP_HOSTPAY1_v1 (orchestrate)
14. PGP_HOSTPAY1_v1 → PGP_HOSTPAY2_v1 (verify)
15. PGP_HOSTPAY1_v1 → PGP_HOSTPAY3_v1 (execute)
16. PGP_HOSTPAY3_v1 → Blockchain (ETH payment)
```

### Donation Flow
```
1. User → PGP_SERVER_v1 (Telegram bot)
2. PGP_SERVER_v1 → NOWPayments (payment link)
3. User → NOWPayments (payment)
4. NOWPayments → PGP_NP_IPN_v1 (IPN webhook)
5. NOWPayments → PGP_ORCHESTRATOR_v1 (success_url)
6. PGP_ORCHESTRATOR_v1 → PGP_NOTIFICATIONS_v1 (notify owner)
7. (Donations bypass accumulation and go directly to channel owner)
```

---

## 📞 SUPPORT & DOCUMENTATION

**Project:** PayGatePrime - Telegram Payment Gateway
**Architecture Version:** 1.0
**Last Updated:** 2025-11-18

For detailed service implementation, refer to individual service README files and architecture documents in `/ARCHIVES_PGP_v1/11-18_PGP_v1/`.

---

**END OF PGP_MAP.md**
