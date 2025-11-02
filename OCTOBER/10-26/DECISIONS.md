# Architectural Decisions - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-01 (Archived previous entries to DECISIONS_ARCH.md)

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

## Recent Decisions

### 2025-11-02: GCWebhook2 Payment Validation Security Fix

**Decision:** Added payment validation to GCWebhook2 service to verify payment completion before sending Telegram invitations

**Context:**
- Security review revealed GCWebhook2 was sending Telegram invitations without payment verification
- Service blindly trusted encrypted tokens from GCWebhook1
- No check for NowPayments IPN callback or payment_id existence
- Race condition could allow unauthorized access if payment failed after token generation
- Critical security vulnerability in payment flow

**Problem:**
1. GCWebhook1 creates encrypted token and enqueues GCWebhook2 task immediately after creating subscription record
2. GCWebhook2 receives token and sends Telegram invitation without checking payment status
3. If NowPayments IPN callback is delayed or payment fails, user gets invitation without paying
4. No validation of payment_id, payment_status, or payment amount

**Implementation:**
1. **New Database Manager:**
   - Created `database_manager.py` with Cloud SQL Connector integration
   - `get_nowpayments_data()`: Queries payment_id, status, address, outcome_amount
   - `validate_payment_complete()`: Validates payment against business rules
   - Returns tuple of (is_valid: bool, error_message: str)

2. **Payment Validation Rules:**
   - Check payment_id exists (populated by np-webhook IPN callback)
   - Verify payment_status = 'finished'
   - Validate outcome_amount >= 80% of expected price (accounts for 15% NowPayments fee + 5% tolerance)

3. **Cloud Tasks Retry Logic:**
   - Return 503 if IPN callback not yet processed → Cloud Tasks retries after 60s
   - Return 400 if payment invalid (wrong amount, failed status) → Cloud Tasks stops retrying
   - Return 200 only after payment validation succeeds

4. **Configuration Updates:**
   - Added database credential fetching to `config_manager.py`
   - Fetches CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME_SECRET, DATABASE_USER_SECRET, DATABASE_PASSWORD_SECRET
   - Updated `requirements.txt` with cloud-sql-python-connector and pg8000
   - Fixed Dockerfile to include database_manager.py

**Rationale:**
- **Security:** Prevents unauthorized Telegram access without payment confirmation
- **Trust Model:** Zero-trust approach - validate payment even with signed tokens
- **Race Condition Fix:** Handles IPN delays gracefully with retry logic
- **Business Logic:** Validates payment amount to prevent underpayment fraud
- **Reliability:** Cloud Tasks retry ensures eventual consistency when IPN delayed

**Alternatives Considered:**
1. **Skip validation, trust GCWebhook1 token:** Rejected - security vulnerability
2. **Validate in GCWebhook1 before enqueueing:** Rejected - still has race condition
3. **Poll NowPayments API directly:** Rejected - inefficient, rate limits, already have IPN data
4. **Add payment_id to token payload:** Rejected - token created before payment_id available

**Trade-offs:**
- **Performance:** Additional database query per invitation (~50ms latency)
- **Complexity:** Requires database credentials in GCWebhook2 service
- **Dependencies:** Adds Cloud SQL Connector dependency to service
- **Benefit:** Eliminates critical security vulnerability, worth the cost

**Impact:**
- GCWebhook2 now validates payment before sending invitations
- Service health check includes database_manager status
- Payment validation logs provide audit trail
- Cloud Tasks retry logic handles IPN delays automatically

**Files Modified:**
- `/GCWebhook2-10-26/database_manager.py` (NEW)
- `/GCWebhook2-10-26/tph2-10-26.py` (payment validation added)
- `/GCWebhook2-10-26/config_manager.py` (database credentials)
- `/GCWebhook2-10-26/requirements.txt` (dependencies)
- `/GCWebhook2-10-26/Dockerfile` (copy database_manager.py)

**Status:** ✅ Implemented and deployed (gcwebhook2-10-26-00011-w2t)

---

### 2025-11-02: TelePay Bot - Secret Manager Integration for IPN Callback URL

**Decision:** Modified TelePay bot to fetch IPN callback URL from Google Cloud Secret Manager instead of directly from environment variables

**Context:**
- Phase 3 of payment_id implementation originally used direct environment variable lookup
- Inconsistent with existing secret management pattern for `PAYMENT_PROVIDER_TOKEN`
- Environment variables storing sensitive URLs less secure than Secret Manager
- Needed centralized secret management across all services

**Implementation:**
1. **New Method Added:**
   - `fetch_ipn_callback_url()` method follows same pattern as `fetch_payment_provider_token()`
   - Fetches from Secret Manager using path from `NOWPAYMENTS_IPN_CALLBACK_URL` env var
   - Returns IPN URL or None if not configured

2. **Initialization Pattern:**
   - `__init__()` now calls `fetch_ipn_callback_url()` on startup
   - Stores IPN URL in `self.ipn_callback_url` instance variable
   - Can be overridden via constructor parameter for testing

3. **Invoice Creation:**
   - `create_payment_invoice()` uses `self.ipn_callback_url` instead of `os.getenv()`
   - Single fetch on initialization, not on every invoice creation
   - Better performance and consistent behavior

**Rationale:**
- **Security:** Secrets stored in Secret Manager with IAM controls, audit logging, versioning
- **Consistency:** Matches existing pattern for all other secrets in codebase
- **Maintainability:** Single source of truth for IPN URL configuration
- **Flexibility:** Environment variable only needs secret path, not the actual URL
- **Observability:** Better logging at fetch time vs. usage time

**Trade-offs:**
- Environment variable now stores secret path instead of actual URL
- Secret Manager API call on bot startup (minimal latency ~50-100ms)
- Must restart bot to pick up secret changes (acceptable for infrequent changes)

**Impact:**
- ✅ More secure secret management
- ✅ Consistent with codebase patterns
- ✅ Better error handling and logging
- ✅ Zero impact on invoice creation performance

**Configuration Required:**
```bash
# Old way (Phase 3 - Direct URL):
export NOWPAYMENTS_IPN_CALLBACK_URL="https://np-webhook-291176869049.us-east1.run.app"

# New way (Session 26 - Secret Manager path):
export NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest"
```

---

### 2025-11-02: NowPayments Payment ID Storage Architecture

**Decision:** Implemented payment_id storage and propagation through the payment flow to enable fee discrepancy resolution

**Context:**
- Fee discrepancies discovered between NowPayments charges and actual blockchain transactions
- Cannot reconcile fees without linking NowPayments payment_id to our database records
- Need to track actual fees paid vs. estimated fees for accurate accounting

**Implementation:**
1. **Database Layer:**
   - Added 10 NowPayments columns to `private_channel_users_database` (payment_id, invoice_id, order_id, pay_address, payment_status, pay_amount, pay_currency, outcome_amount, created_at, updated_at)
   - Added 5 NowPayments columns to `payout_accumulation` (payment_id, pay_address, outcome_amount, network_fee, payment_fee_usd)
   - Created indexes on payment_id and order_id for fast lookups

2. **Service Integration:**
   - Leveraged existing `np-webhook` service for IPN handling
   - Updated GCWebhook1 to query payment_id after database write and pass to GCAccumulator
   - Updated GCAccumulator to store payment_id in payout_accumulation records
   - Added NOWPAYMENTS_IPN_SECRET and NOWPAYMENTS_IPN_CALLBACK_URL to Secret Manager

3. **TelePay Bot Updates (Phase 3):**
   - Updated `start_np_gateway.py` to include `ipn_callback_url` in NowPayments invoice creation
   - Bot now passes IPN endpoint to NowPayments: `https://np-webhook-291176869049.us-east1.run.app`
   - Added logging to track invoice_id, order_id, and IPN callback URL for debugging
   - Environment variable `NOWPAYMENTS_IPN_CALLBACK_URL` must be set before bot starts

4. **Data Flow:**
   - TelePay bot creates invoice with `ipn_callback_url` specified
   - Customer pays → NowPayments sends IPN to np-webhook
   - NowPayments IPN → np-webhook → updates `private_channel_users_database` with payment_id
   - NowPayments success_url → GCWebhook1 → queries payment_id → passes to GCAccumulator
   - GCAccumulator → stores payment_id in `payout_accumulation`

**Rationale:**
- Minimal changes to existing architecture (reused np-webhook service)
- payment_id propagates through entire payment flow automatically
- Enables future fee reconciliation tools via NowPayments API queries
- Database indexes ensure fast lookups even with large datasets

**Trade-offs:**
- Relies on np-webhook IPN arriving before success_url (usually true, but not guaranteed)
- If IPN delayed, payment_id will be NULL initially but can be backfilled
- Additional database storage for NowPayments metadata (~300 bytes per payment)

**Impact:**
- Zero downtime migration (additive schema changes)
- Backward compatible (payment_id fields are optional)
- Foundation for accurate fee tracking and discrepancy resolution

---

### 2025-11-02: Micro-Batch Processor Schedule Optimization

**Decision:** Reduced micro-batch-conversion-job scheduler interval from 15 minutes to 5 minutes

**Rationale:**
- Faster threshold detection for accumulated payments
- Improved payout latency for users (3x faster threshold checks)
- Aligns with batch-processor-job interval (also 5 minutes)
- No functional changes to service logic - only scheduling frequency

**Impact:**
- Threshold checks now occur every 5 minutes instead of 15 minutes
- Maximum wait time for threshold detection reduced from 15 min to 5 min
- Expected payout completion time reduced by up to 10 minutes
- Minimal increase in Cloud Scheduler API calls (cost negligible)

**Configuration:**
```
Schedule: */5 * * * * (Etc/UTC)
Target: https://gcmicrobatchprocessor-10-26-291176869049.us-central1.run.app/check-threshold
State: ENABLED
```

---

## Notes
- All previous architectural decisions have been archived to DECISIONS_ARCH.md
- This file tracks only the most recent architectural decisions
- Add new decisions at the TOP of the document
