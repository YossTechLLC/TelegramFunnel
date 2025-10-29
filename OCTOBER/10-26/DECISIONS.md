# Architectural Decisions - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-10-28

This document records all significant architectural decisions made during the development of the TelegramFunnel payment system.

---

## Table of Contents
1. [Service Architecture](#service-architecture)
2. [Cloud Infrastructure](#cloud-infrastructure)
3. [Data Flow & Orchestration](#data-flow--orchestration)
4. [Security & Authentication](#security--authentication)
5. [Database Design](#database-design)
6. [Error Handling & Resilience](#error-handling--resilience)
7. [User Interface](#user-interface)

---

## Service Architecture

### Decision: Microservices Over Monolith
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Initial system was monolithic, leading to scaling and deployment issues
- **Decision:** Split into 10 independent microservices
- **Rationale:**
  - Independent scaling of compute-intensive services (payment execution, crypto swaps)
  - Isolated failure domains (one service failure doesn't bring down entire system)
  - Easier deployment and rollback
  - Different services have different retry requirements
- **Trade-offs:**
  - Increased complexity in orchestration
  - More services to monitor and maintain
  - Inter-service communication overhead
- **Alternative Considered:** Modular monolith with separate worker processes
- **Outcome:** Successfully deployed, improved resilience and scalability

### Decision: Flask for All HTTP Services
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Needed consistent framework across all microservices
- **Decision:** Use Flask for all webhook/HTTP services (GCWebhook, GCSplit, GCHostPay, GCRegister)
- **Rationale:**
  - Lightweight and simple for webhook endpoints
  - Well-established ecosystem
  - Easy integration with Google Cloud Run
  - Consistent development patterns across services
- **Trade-offs:**
  - Not as feature-rich as Django for web apps
  - Manual setup required for many features
- **Alternative Considered:** FastAPI (async-first), Django (full-featured)
- **Outcome:** Works well, consistent patterns, easy maintenance

### Decision: python-telegram-bot for Telegram Bot
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Needed robust Telegram bot framework
- **Decision:** Use python-telegram-bot library v20+
- **Rationale:**
  - Official Python wrapper for Telegram Bot API
  - Native async/await support
  - Built-in conversation handlers
  - Active development and community
- **Trade-offs:**
  - Async event loop management can be tricky in serverless environments
  - Required careful handling of Bot instance lifecycle
- **Alternative Considered:** aiogram, pyrogram
- **Outcome:** Successful with proper event loop isolation pattern

---

## Cloud Infrastructure

### Decision: Google Cloud Run for All Services
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Needed serverless compute platform
- **Decision:** Deploy all services on Google Cloud Run
- **Rationale:**
  - Auto-scaling (scale to zero during low traffic)
  - Pay-per-use pricing model
  - Built-in HTTPS endpoints
  - Easy integration with other GCP services
  - No server management overhead
- **Trade-offs:**
  - Cold start latency for infrequent requests
  - Stateless execution model (requires careful design)
  - Request timeout limits (9 minutes max)
- **Alternative Considered:** Google Kubernetes Engine, AWS Lambda, VPS
- **Outcome:** Cost-effective, reliable, easy to manage

### Decision: Google Cloud Tasks for Asynchronous Orchestration
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Needed reliable async task queue with retry capabilities
- **Decision:** Use Google Cloud Tasks for all inter-service communication
- **Rationale:**
  - Native integration with Cloud Run
  - Configurable retry policies (including infinite retry)
  - Task deduplication
  - Guaranteed delivery
  - HTTP-based task creation (simple to use)
- **Trade-offs:**
  - Limited to HTTP tasks (no custom workers)
  - Queue configuration requires separate deployment
  - Fixed backoff strategies (no custom retry logic in queue)
- **Alternative Considered:** Cloud Pub/Sub, RabbitMQ, Redis Queue
- **Outcome:** Perfect fit for our orchestration needs

### Decision: Google Secret Manager for Configuration
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Needed secure storage for API keys, tokens, credentials
- **Decision:** Store ALL sensitive configuration in Google Secret Manager
- **Rationale:**
  - Centralized secret management
  - Automatic rotation support
  - IAM-based access control
  - Versioning and audit logging
  - Native GCP integration
- **Trade-offs:**
  - API call latency on service startup
  - Costs for secret access operations
  - Requires proper IAM configuration
- **Alternative Considered:** Environment variables, encrypted files in Cloud Storage
- **Outcome:** Secure, auditable, easy to rotate secrets

### Decision: PostgreSQL on Cloud SQL
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Needed managed relational database
- **Decision:** Use PostgreSQL on Google Cloud SQL
- **Rationale:**
  - Fully managed (backups, updates, patches)
  - Strong consistency and ACID compliance
  - Rich data types (NUMERIC for precise financial calculations)
  - Connection pooling via Cloud SQL connector
  - High availability options
- **Trade-offs:**
  - Higher cost than self-hosted
  - Connection limits require management
  - Potential latency for database-heavy operations
- **Alternative Considered:** Firestore, MongoDB, self-hosted PostgreSQL
- **Outcome:** Reliable, consistent, easy to maintain

---

## Data Flow & Orchestration

### Decision: 3-Stage Split Architecture (GCSplit1/2/3)
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Payment splitting requires multiple ChangeNow API calls with retry logic
- **Decision:** Split into 3 services: Orchestrator (Split1), USDT→ETH Estimator (Split2), ETH→Client Swapper (Split3)
- **Rationale:**
  - **Split1 (Orchestrator):** Manages overall workflow, database operations, state
  - **Split2 (USDT→ETH):** Isolated ChangeNow estimate calls with retry
  - **Split3 (ETH→Client):** Isolated ChangeNow swap creation with retry
  - Each service can retry infinitely without affecting others
  - Clear separation of concerns
  - Database writes only in Split1 (single source of truth)
- **Trade-offs:**
  - More complex than single service
  - More Cloud Tasks overhead
  - Debugging requires tracing across services
- **Alternative Considered:** Single Split service with internal retry
- **Outcome:** Excellent resilience, clear boundaries

### Decision: 3-Stage HostPay Architecture (GCHostPay1/2/3)
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** ETH payment execution requires ChangeNow status check before transfer
- **Decision:** Split into 3 services: Orchestrator (HostPay1), Status Checker (HostPay2), Payment Executor (HostPay3)
- **Rationale:**
  - **HostPay1 (Orchestrator):** Validates, checks duplicates, coordinates workflow
  - **HostPay2 (Status Checker):** Verifies ChangeNow status with retry
  - **HostPay3 (Payment Executor):** Executes ETH transfers with retry
  - Status check can retry infinitely without triggering duplicate payments
  - Payment execution isolated from coordination logic
  - Clear audit trail of validation → verification → execution
- **Trade-offs:**
  - More services to monitor
  - Increased Cloud Tasks usage
  - More complex deployment
- **Alternative Considered:** Single HostPay service with internal stages
- **Outcome:** High reliability, no duplicate payments, clear workflow

### Decision: 2-Stage Webhook Architecture (GCWebhook1/2)
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Payment confirmation requires database write AND Telegram invite
- **Decision:** Split into 2 services: Payment Processor (Webhook1), Invite Sender (Webhook2)
- **Rationale:**
  - **Webhook1:** Fast response to NOWPayments, database write, task enqueuing
  - **Webhook2:** Async Telegram invite sending with retry (can be slow)
  - Telegram API rate limits don't block payment confirmation
  - Webhook1 can return 200 quickly to NOWPayments
  - Webhook2 can retry invite sending without re-processing payment
- **Trade-offs:**
  - Two services instead of one
  - Slight delay in invite delivery
- **Alternative Considered:** Single webhook service with background threads
- **Outcome:** Fast payment confirmation, reliable invite delivery

### Decision: Pure Market Value Calculation in Split1
- **Date:** October 20, 2025
- **Status:** ✅ Implemented
- **Context:** `split_payout_request` table needs to store true market value, not post-fee amount
- **Decision:** Calculate pure market conversion value in Split1 before database insert
- **Rationale:**
  - ChangeNow's `toAmount` includes fees deducted
  - We need the MARKET VALUE (what the dollar amount is worth in ETH)
  - Back-calculate from fee data: `(toAmount + withdrawalFee) / (fromAmount - depositFee)`
  - Store this pure market rate in `split_payout_request.to_amount`
- **Trade-offs:**
  - Slightly more complex calculation
  - Requires understanding ChangeNow fee structure
- **Alternative Considered:** Store post-fee amount (simpler but incorrect)
- **Outcome:** Accurate market value tracking for accounting

---

## Security & Authentication

### Decision: Token-Based Inter-Service Authentication
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Services need to authenticate each other's requests
- **Decision:** Use encrypted, signed tokens with HMAC-SHA256
- **Rationale:**
  - Stateless authentication (no session management)
  - Self-contained (includes all necessary data)
  - Tamper-proof (HMAC signature verification)
  - Time-limited (timestamp validation)
  - No external auth service required
- **Implementation:**
  - `TokenManager` class in each service
  - Binary packed data with HMAC signature
  - Base64 URL-safe encoding
  - Different signing keys for different service pairs
- **Trade-offs:**
  - Token size overhead in payloads
  - Requires synchronized signing keys across services
  - No centralized token revocation
- **Alternative Considered:** JWT, API keys, mutual TLS
- **Outcome:** Simple, secure, performant

### Decision: HMAC Webhook Signature Verification
- **Date:** October 2025
- **Status:** 🔄 Partially Implemented
- **Context:** Webhook endpoints need to verify request authenticity
- **Decision:** Use HMAC-SHA256 signature verification for webhooks
- **Rationale:**
  - Prevents unauthorized webhook calls
  - Verifies request hasn't been tampered with
  - Standard practice for webhook security
- **Current Status:** Implemented in GCSplit1, planned for others
- **Trade-offs:**
  - Adds verification overhead
  - Requires signature header in all requests
- **Alternative Considered:** Rely on Cloud Tasks internal network security
- **Outcome:** Partial implementation, full rollout planned

---

## Database Design

### Decision: Separate Tables for Split Workflow (split_payout_request, split_payout_que)
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Payment split workflow has two distinct phases
- **Decision:** Use two tables linked by `unique_id`
- **Rationale:**
  - **split_payout_request:** Initial request data, pure market value
  - **split_payout_que:** ChangeNow swap transaction data
  - Separates "what we want to do" from "how ChangeNow is doing it"
  - Clean data model for two-phase workflow
  - Enables separate querying/analytics
- **Schema:**
  ```sql
  split_payout_request (
    unique_id, user_id, closed_channel_id,
    from_currency, to_currency, from_network, to_network,
    from_amount, to_amount (PURE MARKET VALUE), ...
  )

  split_payout_que (
    unique_id, cn_api_id, user_id, closed_channel_id,
    from_currency, to_currency, from_network, to_network,
    from_amount, to_amount, payin_address, payout_address, ...
  )
  ```
- **Trade-offs:**
  - Two tables instead of one
  - JOIN required for full transaction view
- **Alternative Considered:** Single table with nullable ChangeNow fields
- **Outcome:** Clean separation, good data model

### Decision: NUMERIC Type for All Financial Values
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Need precise decimal arithmetic for money
- **Decision:** Use PostgreSQL NUMERIC type for all prices, amounts, fees
- **Rationale:**
  - Exact decimal representation (no floating-point errors)
  - Arbitrary precision
  - Standard for financial applications
  - PostgreSQL optimized for NUMERIC operations
- **Trade-offs:**
  - Slightly slower than floating-point
  - Requires conversion in application code
- **Alternative Considered:** FLOAT, REAL (both have precision issues)
- **Outcome:** Accurate financial calculations, no rounding errors

---

## Error Handling & Resilience

### Decision: Infinite Retry with Fixed 60s Backoff
- **Date:** October 21, 2025
- **Status:** ✅ Implemented
- **Context:** External APIs (ChangeNow, Ethereum RPC) can be temporarily unavailable
- **Decision:** Configure all Cloud Tasks queues with infinite retry, 60s fixed backoff, 24h max duration
- **Configuration:**
  ```
  Max Attempts: -1 (infinite)
  Max Retry Duration: 86400s (24 hours)
  Min Backoff: 60s
  Max Backoff: 60s
  Max Doublings: 0 (no exponential backoff)
  ```
- **Rationale:**
  - **Fixed Backoff:** Consistent retry interval, easier to reason about
  - **60s Interval:** Balance between responsiveness and API politeness
  - **24h Max:** Reasonable timeout for even extended outages
  - **Infinite Attempts:** Will eventually succeed unless task expires
  - **No Exponential:** Avoids extremely long waits, maintains consistent throughput
- **Trade-offs:**
  - Can accumulate many tasks during extended outages
  - 60s may be too slow for time-sensitive operations
  - 24h cutoff may lose some tasks during catastrophic failures
- **Alternative Considered:** Exponential backoff, shorter retry windows
- **Outcome:** Excellent resilience, consistent behavior

### Decision: Sync Route with asyncio.run() for GCWebhook2
- **Date:** October 26, 2025
- **Status:** ✅ Implemented
- **Context:** GCWebhook2 was experiencing "Event loop is closed" errors
- **Decision:** Change from async Flask route to sync route with `asyncio.run()`
- **Rationale:**
  - **Cloud Run Stateless Model:** Event loops don't persist between requests
  - **Fresh Event Loop per Request:** Each `asyncio.run()` creates isolated loop
  - **Fresh Bot Instance:** New httpx connection pool per request
  - **Clean Lifecycle:** Event loop and connections cleaned up after request
  - **Prevents Errors:** No shared state between requests
- **Implementation:**
  ```python
  @app.route("/", methods=["POST"])
  def send_telegram_invite():  # Sync route
      async def send_invite_async():
          bot = Bot(bot_token)  # Fresh instance
          # ... async telegram operations

      result = asyncio.run(send_invite_async())  # Isolated loop
      return jsonify(result), 200
  ```
- **Trade-offs:**
  - Cannot share Bot instance across requests (slightly more overhead)
  - Event loop created/destroyed each request
- **Alternative Considered:** Async route with loop management, background worker
- **Outcome:** ✅ Fixed event loop errors, stable in production

### Decision: Database Write Only After Success in HostPay3
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Need to log ETH payments but avoid logging failed attempts
- **Decision:** Write to `hostpay_transactions` table ONLY after successful ETH transfer
- **Rationale:**
  - Prevents database pollution with failed attempts
  - Clean audit trail of actual transfers
  - Retry logic can continue without cleanup
  - Database reflects actual blockchain state
- **Trade-offs:**
  - No record of failed attempts (only in logs)
  - Can't analyze retry patterns from database
- **Alternative Considered:** Log all attempts with status field
- **Outcome:** Clean transaction log, accurate state

---

## User Interface

### Decision: Inline Keyboards Over Text Input for Telegram Bot
- **Date:** October 26, 2025
- **Status:** ✅ Implemented
- **Context:** Original DATABASE command used text-based conversation flow
- **Decision:** Rebuild with inline keyboard forms (web-like UX)
- **Rationale:**
  - **Better UX:** Button clicks instead of typing
  - **Less Error-Prone:** Validation before submission
  - **Clearer Workflow:** Visual navigation with back buttons
  - **Modern Feel:** More app-like than chat-like
  - **Session-Based Editing:** Changes stored until "Save All"
- **Implementation:**
  - Nested inline keyboard menus
  - Toggle buttons for tier enable/disable
  - Edit buttons for each field
  - Submit buttons at each level
  - "Save All Changes" / "Cancel Edit" at top level
- **Trade-offs:**
  - More complex conversation handler logic
  - Requires careful state management (context.user_data)
  - More code than simple text prompts
- **Alternative Considered:** Keep text-based input with better prompts
- **Outcome:** Much better user experience, positive feedback expected

### Decision: Color-Coded Tier Status (✅ / ❌)
- **Date:** October 26, 2025
- **Status:** ✅ Implemented
- **Context:** Need visual feedback for tier enable/disable state
- **Decision:** Use ✅ (enabled) and ❌ (disabled) emojis
- **Rationale:**
  - Instant visual feedback
  - No need to read text to understand state
  - Consistent with modern UI patterns
  - Works in Telegram's limited UI
- **Trade-offs:**
  - Relies on emoji support
  - Color meaning must be learned (but intuitive)
- **Alternative Considered:** Text labels ("Enabled" / "Disabled")
- **Outcome:** Clear, intuitive visual design

### Decision: CAPTCHA for Registration Form
- **Date:** October 2025
- **Status:** ✅ Implemented
- **Context:** Registration form needs bot protection
- **Decision:** Implement simple math-based CAPTCHA
- **Rationale:**
  - Low friction (simple addition)
  - Effective against basic bots
  - No external service required
  - Works without JavaScript
- **Trade-offs:**
  - Can be bypassed by advanced bots
  - Minor user friction
- **Alternative Considered:** reCAPTCHA, hCaptcha
- **Outcome:** Good balance of security and usability

---

---

## Recent Architectural Decisions (2025-10-28)

### Decision: USDT Accumulation for Threshold Payouts
- **Date:** October 28, 2025
- **Status:** ✅ Designed, Awaiting Implementation
- **Context:** Need to support high-fee cryptocurrencies like Monero without exposing clients to market volatility
- **Decision:** Implement dual-strategy payout system (instant + threshold) with USDT stablecoin accumulation
- **Rationale:**
  - **Problem:** Holding volatile crypto (ETH) during accumulation could lose client 25%+ value
  - **Solution:** Immediately convert ETH→USDT, accumulate stablecoins
  - **Benefit:** Zero volatility risk, client receives exact USD value earned
  - **Fee Savings:** Batching Monero payouts reduces fees from 5-20% to <1%
- **Architecture:**
  - GCAccumulator-10-26: Converts payments to USDT immediately
  - GCBatchProcessor-10-26: Detects threshold, triggers batch payouts
  - Two new tables: `payout_accumulation`, `payout_batches`
  - Modified services: GCWebhook1 (routing), GCRegister (UI)
- **Trade-offs:**
  - Adds complexity (2 new services, 2 new tables)
  - USDT depeg risk (very low probability)
  - Extra swap step ETH→USDT (0.3-0.5% fee, but eliminates 25%+ volatility risk)
- **Alternative Considered:**
  - Platform absorbs volatility risk (unsustainable)
  - Client accepts volatility risk (bad UX)
  - Immediate conversion to final currency (high fees per transaction)
- **Outcome:** Awaiting implementation - Architecture doc complete
- **Documentation:** `THRESHOLD_PAYOUT_ARCHITECTURE.md`

### Decision: 3-Stage Split for Threshold Payout
- **Date:** October 28, 2025
- **Status:** ✅ Designed
- **Context:** Batch payouts require USDT→ClientCurrency conversion
- **Decision:** Reuse existing GCSplit1/2/3 infrastructure with new `/batch-payout` endpoint
- **Rationale:**
  - No need to duplicate swap logic
  - Same ChangeNow API integration
  - Consistent retry patterns
  - Just needs batch_id tracking instead of user_id
- **Trade-offs:**
  - Adds endpoint to existing service (minor complexity)
  - Shares rate limits with instant payouts
- **Alternative Considered:** Separate batch swap service (unnecessary duplication)
- **Outcome:** Clean reuse of existing infrastructure

### Decision: Separate USER_ACCOUNT_MANAGEMENT from THRESHOLD_PAYOUT
- **Date:** October 28, 2025
- **Status:** ✅ Designed
- **Context:** Both architectures are large, independent features
- **Decision:** Implement as separate phases
- **Rationale:**
  - Threshold payout has no dependencies (can ship first)
  - User accounts require authentication layer (larger change)
  - Easier testing and rollback if separated
  - Clearer git history and deployment tracking
- **Implementation Order:**
  1. THRESHOLD_PAYOUT (Phase 1 - foundational)
  2. USER_ACCOUNT_MANAGEMENT (Phase 2 - builds on threshold fields)
  3. GCREGISTER_MODERNIZATION (Phase 3 - UI layer for both)
- **Trade-offs:**
  - Longer total timeline (but safer)
  - Multiple database migrations (but atomic)
- **Alternative Considered:** Big-bang implementation of all three (too risky)
- **Outcome:** Phased approach reduces risk

### Decision: TypeScript/React SPA for GCRegister Modernization
- **Date:** October 28, 2025
- **Status:** ✅ Designed
- **Context:** Current GCRegister is Flask monolith with server-rendered templates
- **Decision:** Split into Flask REST API + TypeScript/React SPA
- **Rationale:**
  - **Zero Cold Starts:** Static assets served from Cloud Storage + CDN
  - **Modern UX:** Instant interactions, real-time validation
  - **Type Safety:** TypeScript (frontend) + Pydantic (backend)
  - **Better DX:** Hot module replacement, component reusability
  - **Scalability:** Frontend scales infinitely (static), backend scales independently
- **Architecture:**
  - GCRegisterAPI-10-26: Flask REST API (JSON only, no templates)
  - GCRegisterWeb-10-26: React SPA (TypeScript, Vite, Tailwind)
  - Hosted separately: API on Cloud Run, SPA on Cloud Storage
- **Trade-offs:**
  - More complex deployment (two services instead of one)
  - Requires frontend build pipeline
  - CORS configuration needed
  - More initial development time
- **Alternative Considered:** Keep Flask with templates, use HTMX for interactivity
- **Outcome:** Modern architecture, ready for future growth
- **Documentation:** `GCREGISTER_MODERNIZATION_ARCHITECTURE.md`

---

## Future Considerations

### Under Evaluation

1. **Metrics Collection**
   - Cloud Monitoring integration
   - Custom dashboards
   - Alerting on failures

2. **Admin Dashboard**
   - Transaction monitoring
   - User management
   - Analytics and reporting

3. **Rate Limiting Strategy**
   - Re-enable in GCRegister
   - Implement in other services
   - Configure based on actual load

4. **Threshold Payout Enhancements** (Post-Launch)
   - Time-based trigger (auto-payout after 90 days)
   - Manual override for early payout
   - Client dashboard showing accumulation progress
   - SMS/Email notifications when threshold reached

---

## Notes

- All decisions documented with date, context, rationale
- Trade-offs explicitly stated for informed decision-making
- Alternatives considered show exploration of options
- Outcomes track success/failure of decisions
- Update this file when making significant architectural changes
- **NEW (2025-10-28):** Four major architectural decisions added for threshold payout and modernization initiatives
