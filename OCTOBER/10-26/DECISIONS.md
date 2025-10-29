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

### Decision: Flask-Login for User Account Management
- **Date:** October 28, 2025
- **Status:** ✅ Designed, Documentation Complete
- **Context:** Need user authentication and session management for multi-channel dashboard
- **Decision:** Use Flask-Login library for authentication
- **Rationale:**
  - **Industry Standard:** Most popular Flask authentication library
  - **Built-In Features:** @login_required decorator, current_user proxy, remember-me
  - **Simple Integration:** Minimal configuration, works with existing Flask setup
  - **Session-Based:** Stateful authentication suitable for web app
  - **Easy Migration:** Can later migrate to JWT for SPA when modernizing
- **Implementation:**
  - LoginManager initialization in tpr10-26.py
  - User class implementing UserMixin
  - @login_manager.user_loader function
  - Session cookies for authentication state
- **Trade-offs:**
  - Session-based (not stateless like JWT)
  - Requires SECRET_KEY in Secret Manager
  - Server-side session storage
- **Alternative Considered:**
  - JWT authentication (better for SPA, but GCRegister not yet SPA)
  - Custom authentication (too much reinvention)
  - Flask-Security (overkill for current needs)
- **Outcome:** Perfect fit for current Flask template architecture
- **Documentation:** `GCREGISTER_USER_MANAGEMENT_GUIDE.md`, `DEPLOYMENT_GUIDE_USER_ACCOUNTS.md`

### Decision: UUID for User IDs (Not Sequential Integers)
- **Date:** October 28, 2025
- **Status:** ✅ Designed, Documentation Complete
- **Context:** Need primary key for registered_users table
- **Decision:** Use UUID (gen_random_uuid()) instead of SERIAL
- **Rationale:**
  - **Security:** Prevents user enumeration attacks (can't guess user IDs)
  - **Opaque Identifiers:** UUIDs don't leak information (unlike sequential IDs)
  - **Distributed System Ready:** UUIDs can be generated independently without coordination
  - **Best Practice:** Industry standard for user identifiers
  - **URL Safety:** UUIDs work well in URLs without exposing system internals
- **Implementation:**
  ```sql
  CREATE TABLE registered_users (
      user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      ...
  );
  ```
- **Trade-offs:**
  - Larger storage (16 bytes vs 4 bytes for INTEGER)
  - Slightly slower joins (but negligible with proper indexes)
  - Less human-readable in logs
- **Alternative Considered:**
  - SERIAL/BIGSERIAL (sequential integers - bad for security)
  - Custom hash-based IDs (unnecessary complexity)
- **Outcome:** Secure, scalable user identification
- **Documentation:** `DB_MIGRATION_USER_ACCOUNTS.md`

### Decision: Legacy User for Backward Compatibility
- **Date:** October 28, 2025
- **Status:** ✅ Designed, Documentation Complete
- **Context:** Existing channels have no user owner when user accounts are first introduced
- **Decision:** Create special "legacy_system" user (UUID all zeros) for existing channels
- **Rationale:**
  - **Backward Compatibility:** All existing channels remain functional
  - **No Data Loss:** Channels not deleted when user accounts introduced
  - **Clean Migration:** All existing channels assigned to known UUID
  - **Future Reassignment:** Admin can later reassign channels to real users
  - **Atomic Migration:** No manual channel-by-channel assignment during migration
- **Implementation:**
  ```sql
  INSERT INTO registered_users (
      user_id,
      username,
      email,
      password_hash,
      is_active,
      email_verified
  ) VALUES (
      '00000000-0000-0000-0000-000000000000',  -- Reserved UUID
      'legacy_system',
      'legacy@paygateprime.com',
      '$2b$12$...',  -- Random bcrypt hash (login disabled)
      FALSE,  -- Account disabled
      FALSE
  );

  -- All existing channels
  UPDATE main_clients_database
  SET client_id = '00000000-0000-0000-0000-000000000000'
  WHERE client_id IS NULL;
  ```
- **Trade-offs:**
  - Special-case UUID (all zeros) requires documentation
  - Legacy user account takes up one user slot (minimal impact)
- **Alternative Considered:**
  - Nullable client_id (bad for data integrity)
  - Delete existing channels (data loss)
  - Manual reassignment during migration (too risky)
- **Outcome:** Smooth migration path, zero downtime
- **Documentation:** `DB_MIGRATION_USER_ACCOUNTS.md`

### Decision: 10-Channel Limit per Account
- **Date:** October 28, 2025
- **Status:** ✅ Designed, Documentation Complete
- **Context:** Need to prevent abuse and manage resource allocation
- **Decision:** Enforce maximum 10 channels per user account
- **Rationale:**
  - **Prevent Abuse:** Stops users from creating unlimited channels
  - **Resource Management:** Bounds per-user resource consumption
  - **Business Model:** Encourages premium accounts in future (if >10 needed)
  - **Reasonable Limit:** 10 is generous for most legitimate use cases
  - **Performance:** Ensures dashboard queries remain fast
- **Implementation:**
  ```python
  # In tpr10-26.py /channels/add route
  channel_count = db_manager.count_channels_by_client(current_user.id)
  if channel_count >= 10:
      flash('Maximum 10 channels per account', 'error')
      return redirect('/channels')
  ```
- **Trade-offs:**
  - May frustrate power users (can create multiple accounts)
  - Requires enforcement in application code
- **Alternative Considered:**
  - No limit (open to abuse)
  - Database constraint (CHECK constraint, but harder to update)
  - Higher limit (15, 20) - 10 is good starting point
- **Outcome:** Balanced limit for resource management
- **Documentation:** `GCREGISTER_USER_MANAGEMENT_GUIDE.md`, `DEPLOYMENT_GUIDE_USER_ACCOUNTS.md`

### Decision: Owner-Only Channel Editing (Authorization)
- **Date:** October 28, 2025
- **Status:** ✅ Designed, Documentation Complete
- **Context:** Users should only edit their own channels, not others'
- **Decision:** Implement authorization checks in /channels/<id>/edit route
- **Rationale:**
  - **Security:** Prevents unauthorized channel modifications
  - **Data Integrity:** Only owner can modify channel configuration
  - **User Trust:** Users confident their channels are private
  - **Compliance:** Meets basic security requirements
- **Implementation:**
  ```python
  @app.route('/channels/<channel_id>/edit', methods=['GET', 'POST'])
  @login_required
  def edit_channel(channel_id):
      channel = db_manager.get_channel_by_id(channel_id)

      # Authorization check
      if str(channel['client_id']) != str(current_user.id):
          abort(403)  # Forbidden

      # ... rest of edit logic
  ```
- **Trade-offs:**
  - Requires UUID comparison (client_id == current_user.id)
  - Need to handle 403 errors gracefully in templates
- **Alternative Considered:**
  - Trust frontend to only show user's channels (insecure)
  - Database-level row security policies (overkill for this use case)
- **Outcome:** Secure channel editing with clear authorization
- **Documentation:** `GCREGISTER_USER_MANAGEMENT_GUIDE.md`, `DEPLOYMENT_GUIDE_USER_ACCOUNTS.md`

### Decision: ON DELETE CASCADE for Client-to-Channel Relationship
- **Date:** October 28, 2025
- **Status:** ✅ Designed, Documentation Complete
- **Context:** What happens to channels when user account is deleted?
- **Decision:** Use ON DELETE CASCADE to automatically delete channels
- **Rationale:**
  - **Data Cleanup:** No orphaned channels when user deleted
  - **GDPR Compliance:** User data fully removed when account deleted
  - **Automatic:** No manual cleanup required
  - **Database-Enforced:** Cannot forget to delete channels
- **Implementation:**
  ```sql
  ALTER TABLE main_clients_database
  ADD CONSTRAINT fk_client_id
      FOREIGN KEY (client_id)
      REFERENCES registered_users(user_id)
      ON DELETE CASCADE;
  ```
- **Trade-offs:**
  - Permanent data loss (can't undo user deletion)
  - Channels deleted immediately without confirmation
- **Alternative Considered:**
  - ON DELETE SET NULL (orphaned channels)
  - ON DELETE RESTRICT (prevent user deletion if channels exist)
  - Soft delete (mark user inactive, keep channels)
- **Outcome:** Clean data model, automatic cleanup
- **Documentation:** `DB_MIGRATION_USER_ACCOUNTS.md`

---

## Recent Deployment Decisions (2025-10-29)

### Decision: Deploy Threshold Payout and User Accounts in Single Session
- **Date:** October 29, 2025
- **Status:** ✅ Executed
- **Context:** Both database migrations were ready and independent
- **Decision:** Execute both migrations together to minimize database downtime
- **Rationale:**
  - Both migrations modify `main_clients_database` (different columns, no conflicts)
  - Simpler deployment story (one migration session vs two)
  - User accounts database ready even if UI implementation delayed
  - Reduces risk of forgetting second migration
- **Implementation:**
  - Created single Python script (`execute_migrations.py`) handling both migrations
  - Executed migrations in sequence with verification steps
  - All 13 existing channels successfully migrated
- **Trade-offs:**
  - Slightly longer migration time (~15 minutes vs ~8 minutes each)
  - More complex rollback if issues (but provided separate rollback procedures)
- **Alternative Considered:** Deploy threshold payout first, user accounts later
- **Outcome:** ✅ Success - Both migrations completed, all data verified

### Decision: Use Cloud Scheduler Instead of Cron Job for Batch Processing
- **Date:** October 29, 2025
- **Status:** ✅ Implemented
- **Context:** Need to trigger GCBatchProcessor every 5 minutes to check for clients over threshold
- **Decision:** Use Google Cloud Scheduler with HTTP target
- **Rationale:**
  - **Serverless:** No VM maintenance required
  - **Reliable:** Google-managed, guaranteed execution
  - **Observable:** Built-in execution history and logging
  - **Scalable:** No capacity planning needed
  - **Cost-effective:** Free tier covers 3 jobs (we use 1)
  - **Cloud Run Integration:** Direct HTTP POST to service endpoint
- **Configuration:**
  - Schedule: `*/5 * * * *` (every 5 minutes)
  - Target: https://gcbatchprocessor-10-26.../process
  - Timezone: America/Los_Angeles
  - State: ENABLED
- **Trade-offs:**
  - Requires Cloud Scheduler API (easily enabled)
  - 5-minute granularity (good enough for batch processing)
- **Alternative Considered:** Cron job in VM, Cloud Functions with pub/sub trigger
- **Outcome:** ✅ Job created and enabled, runs every 5 minutes

### Decision: Enable Cloud Scheduler API During Deployment
- **Date:** October 29, 2025
- **Status:** ✅ Executed
- **Context:** Cloud Scheduler API was not previously enabled in telepay-459221 project
- **Decision:** Enable API when needed rather than asking user
- **Rationale:**
  - User gave explicit permission to enable any API needed
  - Cloud Scheduler is core infrastructure for batch processing
  - No cost impact (free tier sufficient)
  - API enablement is non-destructive and reversible
- **Command:** `gcloud services enable cloudscheduler.googleapis.com`
- **Trade-offs:**
  - Adds API to project (minimal impact)
  - Requires waiting ~2 minutes for API to propagate
- **Alternative Considered:** Ask user before enabling (unnecessary delay)
- **Outcome:** ✅ API enabled successfully, scheduler job created immediately after

### Decision: Deploy Services Before Creating URL Secrets
- **Date:** October 29, 2025
- **Status:** ✅ Executed
- **Context:** GCACCUMULATOR_URL secret needs actual Cloud Run URL
- **Decision:** Deploy service first, then create URL secret, then re-deploy dependent services
- **Rationale:**
  - Cloud Run URLs unknown until first deployment
  - GCWebhook1 needs GCACCUMULATOR_URL to route threshold payments
  - Two-step deployment acceptable (deploy accumulator → create secret → re-deploy webhook)
- **Implementation Order:**
  1. Deploy GCAccumulator-10-26 (get URL)
  2. Create GCACCUMULATOR_URL secret with actual URL
  3. Deploy GCBatchProcessor-10-26 (get URL)
  4. Re-deploy GCWebhook1-10-26 (can now fetch GCACCUMULATOR_URL secret)
- **Trade-offs:**
  - Requires re-deployment of dependent services
  - Slight complexity in deployment order
- **Alternative Considered:** Hardcode URLs (bad practice), deploy all at once with placeholder URLs
- **Outcome:** ✅ All services deployed correctly with proper URL secrets

### Decision: Mock ETH→USDT Conversion in GCAccumulator
- **Date:** October 29, 2025
- **Status:** ✅ Implemented
- **Context:** GCAccumulator needs to convert ETH to USDT for accumulation
- **Decision:** Use mock conversion rate initially, design for ChangeNow integration later
- **Rationale:**
  - Mock allows end-to-end testing without ChangeNow API costs
  - Architecture supports swapping in real ChangeNow calls later
  - Can verify database writes and batch processing independently
  - Reduces deployment complexity (fewer API dependencies)
- **Implementation:**
  - Mock rate: 1 ETH = 3000 USDT (hardcoded for now)
  - `eth_to_usdt_rate` stored in database for audit
  - Ready to replace with ChangeNow API v2 estimate call
- **Trade-offs:**
  - Not production-ready for real money (mock conversion)
  - Requires future work to integrate ChangeNow
- **Alternative Considered:** Integrate ChangeNow immediately (more complex, delays testing)
- **Outcome:** ✅ System deployed and testable, ChangeNow integration deferred

### Decision: Use Python Script for Database Migrations Instead of Manual SQL
- **Date:** October 29, 2025
- **Status:** ✅ Executed
- **Context:** Need to execute SQL migrations from WSL environment without psql client
- **Decision:** Create Python script using Cloud SQL Connector
- **Rationale:**
  - **No psql Required:** Cloud SQL Connector handles authentication and connection
  - **Programmatic:** Can add verification queries and error handling
  - **Idempotent:** Script checks if migration already applied before executing
  - **Audit Trail:** Prints detailed progress with emojis matching project style
  - **Reusable:** Can be run again safely (won't re-apply migrations)
- **Implementation:**
  - Created `execute_migrations.py` with Cloud SQL Connector + pg8000
  - Used Google Secret Manager for database credentials
  - Added verification steps after each migration
  - Included rollback SQL in comments
- **Trade-offs:**
  - Requires Python dependencies (cloud-sql-python-connector, google-cloud-secret-manager)
  - More code than manual SQL execution
- **Alternative Considered:** Manual SQL via gcloud sql connect (psql not available), Cloud Shell
- **Outcome:** ✅ Migrations executed successfully, full verification completed

### Decision: RegisterChannelPage with Complete Form UI
- **Date:** October 29, 2025
- **Status:** ✅ Implemented
- **Context:** Users could signup and login but couldn't register channels - buttons existed but did nothing
- **Decision:** Implement complete RegisterChannelPage.tsx with all form fields from API model
- **Rationale:**
  - **Complete User Flow:** Users can now: signup → login → register channel → view dashboard
  - **Form Complexity:** 20+ fields organized into logical sections (Open Channel, Closed Channel, Tiers, Payment Config, Payout Strategy)
  - **Dynamic UI:** Tier count dropdown shows/hides Tier 2 and 3 fields based on selection
  - **Network-Currency Mapping:** Currency dropdown updates based on selected network
  - **Validation:** Client-side validation before API call (channel ID format, required fields)
  - **Visual Design:** Color-coded tier sections (Gold=yellow, Silver=gray, Bronze=rose)
  - **Strategy Toggle:** Instant vs Threshold with conditional threshold amount field
- **Implementation:**
  - Created RegisterChannelPage.tsx (470 lines)
  - Added tier_count field to ChannelRegistrationRequest TypeScript type
  - Wired dashboard buttons: `onClick={() => navigate('/register')}`
  - Added /register route to App.tsx with ProtectedRoute wrapper
  - Fetches currency/network mappings from API on mount
  - Auto-selects default network (BSC) and currency (SHIB) from database
- **Form Sections:**
  1. Open Channel (Public): ID, Title, Description
  2. Closed Channel (Private/Paid): ID, Title, Description
  3. Subscription Tiers: Count selector + dynamic tier fields (Price USD, Duration days)
  4. Payment Configuration: Wallet address, Network dropdown, Currency dropdown
  5. Payout Strategy: Instant or Threshold + conditional threshold amount
- **Trade-offs:**
  - Large component (470 lines) - could be split into smaller components
  - Inline styles instead of CSS modules - easier to maintain in single file
  - Network/currency mapping from database - requires API call on page load
- **Alternative Considered:**
  - Multi-step wizard (better UX but more complex state management)
  - Separate pages for each section (worse UX - too many nav steps)
  - Form library like React Hook Form (overkill for single form)
- **Testing Results:**
  - ✅ Form loads correctly with all fields
  - ✅ Currency dropdown updates when network changes
  - ✅ Tier 2/3 fields show/hide based on tier count
  - ✅ Threshold field shows/hides based on strategy
  - ✅ Channel registered successfully (API logs show 201 Created)
  - ✅ Dashboard shows registered channel with correct data
  - ✅ 1/10 channels counter updates correctly
- **User Flow Verified:**
  ```
  Landing Page → Signup → Login → Dashboard (0 channels)
  → Click "Register Channel" → Fill form → Submit
  → Redirect to Dashboard → Channel appears (1/10 channels)
  ```
- **Outcome:** ✅ Complete user registration flow working end-to-end
- **Files Modified:**
  - Created: `GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
  - Modified: `GCRegisterWeb-10-26/src/App.tsx` (added route)
  - Modified: `GCRegisterWeb-10-26/src/pages/DashboardPage.tsx` (added onClick handlers)
  - Modified: `GCRegisterWeb-10-26/src/types/channel.ts` (added tier_count field)
- **Deployment:** ✅ Deployed to gs://www-paygateprime-com via Cloud CDN

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
