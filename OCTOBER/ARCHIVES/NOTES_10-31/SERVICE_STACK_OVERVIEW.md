# Service Stack Overview - OCTOBER/10-26

**Date:** October 31, 2025
**Purpose:** Comprehensive overview of all services in the 10-26 stack
**Format:** Intake → Function → Output

---

## Payment Processing Flow Services

### GCWebhook1-10-26

**Intake:**
- POST requests from NOWPayments API via `success_url` webhook
- Contains encrypted payment confirmation data (user_id, subscription_id, payment details)

**Function:**
- Receives and validates payment success webhooks from NOWPayments
- Decrypts and verifies payment data using SUCCESS_URL_SIGNING_KEY
- Writes payment record to database (user_subscriptions table)
- Calculates subscription expiration time
- Routes payment based on client's payout strategy:
  - If `payout_strategy = 'instant'`: Queues to GCSplit1 (instant payout)
  - If `payout_strategy = 'threshold'`: Queues to GCAccumulator (batch payout)
- Queues Telegram invite task to GCWebhook2 (happens regardless of strategy)

**Output:**
- Database: New record in `user_subscriptions` table
- Cloud Tasks: Encrypted token to GCWebhook2 `/` (Telegram invite)
- Cloud Tasks: Encrypted token to GCSplit1 `/` OR GCAccumulator `/accumulate` (payment split)
- HTTP: 200 OK response to NOWPayments

---

### GCWebhook2-10-26

**Intake:**
- POST requests from GCWebhook1 via Cloud Tasks queue
- Encrypted token containing: user_telegram_id, channel_id, expire_time, expire_date

**Function:**
- Receives invitation task from GCWebhook1
- Decrypts token using SUCCESS_URL_SIGNING_KEY
- Creates fresh Telegram Bot instance per request
- Uses asyncio.run() to execute async Telegram operations in isolated event loop
- Generates one-time Telegram invite link for user to join private channel
- Sends invite link via Telegram DM to user
- Implements infinite retry (60s backoff, 24h max) via Cloud Tasks

**Output:**
- Telegram: DM sent to user with invite link to private channel
- HTTP: 200 OK to Cloud Tasks (marks task complete)
- HTTP: 500 to Cloud Tasks (triggers retry after 60s)

---

## Payment Splitting Services (Instant Payout)

### GCSplit1-10-26

**Intake:**
- POST `/` requests from GCWebhook1 via Cloud Tasks queue
- Encrypted token containing: client_id, adjusted_amount_usdt, wallet_address, payout_currency, payout_network
- POST `/gcsplit2-response` requests from GCSplit2 via Cloud Tasks
- POST `/gcsplit3-response` requests from GCSplit3 via Cloud Tasks
- POST `/batch-payout` requests from GCBatchProcessor via Cloud Tasks

**Function:**
- **Main Flow:** Orchestrates payment splitting workflow across GCSplit2 and GCSplit3
- Stores payment split record in database
- Queues USDT→ETH estimate request to GCSplit2
- Receives ETH estimate from GCSplit2
- Queues ETH→ClientCurrency swap request to GCSplit3
- Receives ChangeNow transaction from GCSplit3
- Queues ETH payment execution to GCHostPay1
- Updates database with split completion status
- **Batch Flow:** Handles batch payouts from GCBatchProcessor (multiple payments aggregated)

**Output:**
- Database: Records in `payment_splits` table
- Cloud Tasks: Token to GCSplit2 `/` (USDT→ETH estimate)
- Cloud Tasks: Token to GCSplit3 `/` (ETH→ClientCurrency swap)
- Cloud Tasks: Token to GCHostPay1 `/` (ETH payment execution)
- HTTP: 200 OK to calling service

---

### GCSplit2-10-26

**Intake:**
- POST `/` requests from GCSplit1 via Cloud Tasks queue
- Encrypted token containing: unique_id, adjusted_amount_usdt, payout_currency, payout_network
- POST `/estimate-and-update` requests from GCAccumulator via Cloud Tasks queue
- JSON payload containing: accumulation_id, client_id, accumulated_eth

**Function:**
- **Main Endpoint (/):** USDT→ETH Estimator
  - Receives USDT amount from GCSplit1
  - Calls ChangeNow API for USDT→ETH conversion estimate (infinite retry)
  - Calculates pure market rate (removes ChangeNow fees from calculation)
  - Encrypts response with ETH amount
  - Queues response back to GCSplit1
- **Estimate-and-Update Endpoint:** ETH→USDT Converter (for GCAccumulator)
  - Receives ETH amount from GCAccumulator
  - Calls ChangeNow API for ETH→USDT conversion estimate (infinite retry)
  - **NOTE: Currently only gets QUOTE, does NOT create actual blockchain swap**
  - Updates database with conversion data
  - Checks if client threshold is met (REDUNDANT - see GCSPLIT2_ESTIMATE_VS_GCBATCHPROCESSOR_ARCHITECTURE_ANALYSIS.md)
  - If threshold met, queues GCBatchProcessor (REDUNDANT)

**Output:**
- Cloud Tasks: Encrypted token to GCSplit1 `/gcsplit2-response` (ETH estimate)
- Database: Updated `payout_accumulation` records with conversion data
- Cloud Tasks: Task to GCBatchProcessor `/process` (if threshold met - REDUNDANT)
- HTTP: 200 OK to calling service

---

### GCSplit3-10-26

**Intake:**
- POST `/` requests from GCSplit1 via Cloud Tasks queue
- Encrypted token containing: unique_id, eth_amount, wallet_address, payout_currency, payout_network

**Function:**
- Receives ETH amount from GCSplit1
- Creates ChangeNow fixed-rate transaction (infinite retry):
  - FROM: ETH
  - TO: Client's payout currency (e.g., XMR, BTC, LTC)
  - Creates ACTUAL blockchain transaction (not just estimate)
- Extracts ChangeNow transaction details (payin address, payout address, tx ID)
- Encrypts response with transaction data
- Queues response back to GCSplit1

**Output:**
- Cloud Tasks: Encrypted token to GCSplit1 `/gcsplit3-response` (ChangeNow transaction)
- HTTP: 200 OK to Cloud Tasks

---

## Payment Execution Services

### GCHostPay1-10-26

**Intake:**
- POST `/` requests from GCSplit1 via Cloud Tasks queue
- Encrypted token containing: unique_id, cn_api_id, eth_amount, eth_address
- POST `/status-verified` requests from GCHostPay2 via Cloud Tasks
- POST `/payment-completed` requests from GCHostPay3 via Cloud Tasks

**Function:**
- **Main Endpoint (/):** Validator & Orchestrator
  - Receives payment execution request from GCSplit1
  - Validates and decrypts token
  - Stores in-progress payment in database
  - Queues ChangeNow status check to GCHostPay2
- **Status-Verified Endpoint:** Receives status from GCHostPay2
  - If status = 'finished': Queues ETH payment execution to GCHostPay3
  - If status != 'finished': Returns 500 to trigger Cloud Tasks retry
- **Payment-Completed Endpoint:** Receives confirmation from GCHostPay3
  - Updates database with payment completion status

**Output:**
- Database: Records in `host_payments` table
- Cloud Tasks: Token to GCHostPay2 `/` (ChangeNow status check)
- Cloud Tasks: Token to GCHostPay3 `/` (ETH payment execution)
- HTTP: 200 OK to calling service

---

### GCHostPay2-10-26

**Intake:**
- POST `/` requests from GCHostPay1 via Cloud Tasks queue
- Encrypted token containing: unique_id, cn_api_id

**Function:**
- Receives status check request from GCHostPay1
- Calls ChangeNow API to check transaction status (infinite retry, 60s backoff, 24h max):
  - Endpoint: `/exchange/by-id`
  - Returns status: "waiting", "confirming", "exchanging", "sending", "finished", "failed", "refunded", "expired"
- Encrypts response with status
- Queues response back to GCHostPay1

**Output:**
- Cloud Tasks: Encrypted token to GCHostPay1 `/status-verified` (status response)
- HTTP: 200 OK to Cloud Tasks (success)
- HTTP: 500 to Cloud Tasks (triggers retry if API error)

---

### GCHostPay3-10-26

**Intake:**
- POST `/` requests from GCHostPay1 via Cloud Tasks queue
- Encrypted token containing: unique_id, eth_amount, eth_address

**Function:**
- Receives ETH payment execution request from GCHostPay1
- Uses WalletManager to send ETH from host_wallet to destination address (infinite retry):
  - Builds Ethereum transaction
  - Signs with host wallet private key
  - Broadcasts to Ethereum network via Alchemy RPC
  - Waits for transaction confirmation
- Updates database with transaction hash and status
- Encrypts response with payment confirmation
- Queues response back to GCHostPay1

**Output:**
- Blockchain: ETH transaction from host_wallet to destination address
- Database: Updated `host_payments` record with tx_hash
- Cloud Tasks: Encrypted token to GCHostPay1 `/payment-completed` (confirmation)
- HTTP: 200 OK to Cloud Tasks

---

## Threshold Payout Services

### GCAccumulator-10-26

**Intake:**
- POST `/accumulate` requests from GCWebhook1 via Cloud Tasks queue
- JSON payload containing: client_id, user_id, subscription_id, payment_amount_usd, payment_currency, payment_timestamp, wallet_address, payout_currency, payout_network

**Function:**
- Receives payment data from GCWebhook1 (for clients with `payout_strategy='threshold'`)
- Calculates adjusted amount (removes TelePay platform fee)
- Stores payment record in `payout_accumulation` table with `conversion_status='pending'`
- Stores `accumulated_eth` field (USD equivalent of payment, pending conversion)
- Queues task to GCSplit2 for ETH→USDT conversion
- Returns 200 OK immediately (non-blocking)

**Output:**
- Database: New record in `payout_accumulation` table (conversion_status='pending')
- Cloud Tasks: Task to GCSplit2 `/estimate-and-update` (ETH→USDT conversion)
- HTTP: 200 OK to Cloud Tasks

---

### GCBatchProcessor-10-26

**Intake:**
- POST `/process` requests from Cloud Scheduler (every 5 minutes)
- Optional: POST `/process` requests from GCSplit2 (REDUNDANT - see analysis doc)

**Function:**
- Triggered by Cloud Scheduler every 5 minutes
- Queries database for clients with `SUM(accumulated_amount_usdt) >= payout_threshold_usd`
- For each client over threshold:
  - Generates unique batch_id (UUID)
  - Creates batch record in `payout_batches` table
  - Encrypts token with batch details
  - Queues to GCSplit1 for USDT→ClientCurrency swap
  - Marks individual payments as `is_paid_out = true`
- Processes each client independently (one failure doesn't stop others)

**Output:**
- Database: New records in `payout_batches` table
- Database: Updated `payout_accumulation` records (is_paid_out=true)
- Cloud Tasks: Encrypted token to GCSplit1 `/batch-payout` (for each client over threshold)
- HTTP: 200 OK with summary (number of batches created)

---

## Channel Registration Services

### GCRegister10-26

**Intake:**
- GET `/` requests - Display registration form
- POST `/` requests - Form submission with channel registration data
- GET `/success` - Success confirmation page
- GET `/api/currency-network-mappings` - Currency dropdown data
- GET `/health` - Health check

**Function:**
- Flask web application with Jinja2 templates
- Displays HTML form for channel owners to register their channels
- Form includes: channel_name, channel_username, channel_id, payout_currency, payout_network, wallet_address, subscription_price, subscription_time, payout_strategy (instant/threshold), payout_threshold_usd
- Validates form inputs (WTForms + custom validators)
- Checks for duplicate channels in database
- Inserts new channel record into `main_clients_database` table
- Generates random channel_id if not provided
- CAPTCHA validation (math-based)
- Rate limiting disabled (for testing)

**Output:**
- Database: New record in `main_clients_database` table
- HTTP: Redirect to `/success` page (on success)
- HTTP: Form re-render with error messages (on validation failure)

---

### GCRegisterAPI-10-26

**Intake:**
- POST `/api/auth/signup` - User registration
- POST `/api/auth/login` - User login
- POST `/api/auth/refresh` - Refresh JWT token
- GET `/api/channels` - List user's channels
- POST `/api/channels` - Create new channel
- GET `/api/channels/<id>` - Get channel details
- PUT `/api/channels/<id>` - Update channel
- DELETE `/api/channels/<id>` - Delete channel
- GET `/api/mappings/currency-network` - Get currency/network mappings

**Function:**
- Flask REST API (JSON-only, no templates)
- JWT authentication (stateless, 15-minute access tokens, 30-day refresh tokens)
- CORS-enabled for React SPA frontend
- User account management (signup, login, logout)
- Multi-channel dashboard (users can register multiple channels)
- CRUD operations for channels
- Associates channels with user accounts via `user_id` foreign key
- Password hashing with bcrypt
- Rate limiting per endpoint

**Output:**
- HTTP: JSON responses with data or error messages
- Database: Records in `user_accounts` and `main_clients_database` tables
- JWT: Access and refresh tokens (in JSON response)

---

### GCRegisterWeb-10-26

**Intake:**
- User interactions in browser (clicks, form submissions)
- API responses from GCRegisterAPI-10-26

**Function:**
- TypeScript + React Single-Page Application (SPA)
- Provides modern UI for channel registration system
- Pages:
  - Landing page (public)
  - Login page
  - Signup page
  - Dashboard (protected - lists user's channels)
  - Register channel page (protected)
  - Edit channel page (protected)
- Protected routes (requires JWT authentication)
- React Query for API state management
- Form validation with React Hook Form
- Responsive design with Tailwind CSS
- Connects to GCRegisterAPI-10-26 backend

**Output:**
- HTTP: API requests to GCRegisterAPI-10-26 (JSON payloads)
- Browser: Rendered HTML/CSS/JavaScript (interactive UI)
- LocalStorage: JWT tokens for authentication persistence

---

## Support Files (Not Services)

The following files/scripts are not deployed services but support deployment and development:

### Configuration/Deployment Scripts

- **`deploy_accumulator_tasks_queues.sh`** - Creates Cloud Tasks queues for GCAccumulator and GCBatchProcessor
- **`deploy_gcsplit_tasks_queues.sh`** - Creates Cloud Tasks queues for GCSplit services
- **`deploy_gcwebhook_tasks_queues.sh`** - Creates Cloud Tasks queues for GCWebhook services
- **`deploy_hostpay_tasks_queues.sh`** - Creates Cloud Tasks queues for GCHostPay services
- **`deploy_config_fixes.sh`** - Utility script for fixing configuration issues

### Database Utilities

- **`check_client_table_db.py`** - Verifies `main_clients_database` table structure
- **`check_payout_details.py`** - Inspects `payout_accumulation` records
- **`check_schema.py`** - Validates database schema
- **`check_schema_details.py`** - Detailed schema inspection
- **`check_payment_amounts.py`** - Audits payment calculations
- **`execute_migrations.py`** - Runs database migrations
- **`test_batch_query.py`** - Tests GCBatchProcessor queries
- **`verify_batch_success.py`** - Validates batch payout completion

### SQL Migration Files

- **`add_conversion_status_fields.sql`** - Adds conversion tracking fields to `payout_accumulation` table

---

## Service Dependency Map

### Instant Payout Flow

```
GCWebhook1
    ├─> GCWebhook2 (Telegram invite)
    └─> GCSplit1
           ├─> GCSplit2 (USDT→ETH estimate)
           └─> GCSplit3 (ETH→ClientCurrency swap)
                  └─> GCHostPay1
                         ├─> GCHostPay2 (ChangeNow status check)
                         └─> GCHostPay3 (ETH payment execution)
```

### Threshold Payout Flow

```
GCWebhook1
    ├─> GCWebhook2 (Telegram invite)
    └─> GCAccumulator
           └─> GCSplit2 /estimate-and-update (ETH→USDT conversion)

Cloud Scheduler (every 5 minutes)
    └─> GCBatchProcessor
           └─> GCSplit1 /batch-payout
                  └─> (same flow as instant payout)
```

### Registration Flow (Legacy)

```
User Browser
    └─> GCRegister10-26 (Flask + Jinja2)
           └─> PostgreSQL database
```

### Registration Flow (Modern)

```
User Browser
    └─> GCRegisterWeb-10-26 (React SPA)
           └─> GCRegisterAPI-10-26 (Flask REST API)
                  └─> PostgreSQL database
```

---

## Key Architectural Patterns

### 1. Cloud Tasks Queue Pattern
- **All external API calls happen in Cloud Tasks queue handlers, never in webhook receivers**
- Webhooks return 200 OK immediately (non-blocking)
- External API failures isolated to specific queues
- Automatic retry (60s fixed backoff, 24h max duration)

### 2. Token Encryption Pattern
- All service-to-service communication uses encrypted tokens
- SUCCESS_URL_SIGNING_KEY for GCWebhook/GCSplit services
- TPS_HOSTPAY_SIGNING_KEY for GCHostPay services
- Prevents token tampering and replay attacks

### 3. Infinite Retry Pattern
- ChangeNow API calls use infinite retry loops
- Cloud Tasks enforces 24-hour max retry duration
- Fixed 60-second backoff between retries
- Handles rate limiting (HTTP 429), server errors (5xx), timeouts, connection errors

### 4. Database Connection Pattern
- Cloud SQL connector with automatic IAM authentication
- Connection pooling per service instance
- Automatic reconnection on failure

### 5. Stateless Service Pattern
- All services are stateless (no in-memory session state)
- Cloud Run can scale to zero or scale up dynamically
- Each request is independent and self-contained

---

## Service Count Summary

**Total Services:** 13

**Payment Processing:** 2
- GCWebhook1-10-26
- GCWebhook2-10-26

**Payment Splitting:** 3
- GCSplit1-10-26
- GCSplit2-10-26
- GCSplit3-10-26

**Payment Execution:** 3
- GCHostPay1-10-26
- GCHostPay2-10-26
- GCHostPay3-10-26

**Threshold Payout:** 2
- GCAccumulator-10-26
- GCBatchProcessor-10-26

**Channel Registration:** 3
- GCRegister10-26 (Legacy)
- GCRegisterAPI-10-26 (Modern Backend)
- GCRegisterWeb-10-26 (Modern Frontend)

**Excluded:** TelePay10-26 (Telegram Bot - not covered per request)

---

**Last Updated:** October 31, 2025
**Architecture Version:** 10-26
**Status:** Production
