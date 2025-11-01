# GCHOSTPAY3 ERROR HANDLING & FAILED TRANSACTION ARCHITECTURE

**Created**: 2025-11-01
**Status**: 🟡 Design Document (Not Yet Implemented)
**Version**: 1.0

---

## EXECUTIVE SUMMARY

**Current Problem:**
GCHostPay3 implements **infinite retry logic** (60s backoff, 24h Cloud Tasks max duration) for ETH payment execution. This causes:
- Endless retry loops for transactions that will never succeed (e.g., incorrect swap amounts from upstream bugs)
- Wasted compute resources and API rate limits (Alchemy 429 errors)
- No visibility into persistently failing transactions
- No mechanism for manual intervention or automated recovery

**Proposed Solution:**
Implement **3-attempt limit** on GCHostPay3 payment execution with comprehensive failed transaction storage, error classification, and recovery mechanisms.

**Key Benefits:**
- ✅ Stop endless retry loops after 3 legitimate attempts
- ✅ Capture failed transactions with full context for recovery
- ✅ Classify failures by error type for targeted resolution
- ✅ Enable manual and automated retry workflows
- ✅ Provide observability into payment failures
- ✅ Integrate seamlessly with existing Cloud Tasks/token architecture

---

## PROBLEM ANALYSIS

### Current Infinite Retry Behavior

**Code Location:** `wallet_manager.py:127-283`

**Current Flow:**
```
Attempt 1 → Failure → Wait 60s → Attempt 2 → Failure → Wait 60s → ...
(Continues for up to 24 hours via Cloud Tasks max-retry-duration)
```

**Real-World Failure Example:**
```
Transaction: 2.295 ETH → USDT (incorrect amount from GCMicroBatchProcessor bug)
Error: 429 Too Many Requests (Alchemy rate limit)
Behavior: Retries endlessly for 24 hours, hits rate limits repeatedly
Result: Wastes resources, never succeeds, no failure handling
```

**Issues with Current Design:**
1. **No Attempt Limit** - Will retry identical failures forever
2. **No Error Classification** - Can't distinguish between transient vs permanent failures
3. **No Failure Storage** - Failed transactions disappear after 24h timeout
4. **No Manual Recovery** - No way to fix and retry after investigation
5. **Resource Waste** - Cloud Run instances running for 24h on unrecoverable errors
6. **Rate Limit Abuse** - Repeatedly hits Alchemy API causing 429 errors

---

## PROPOSED ARCHITECTURE

### High-Level Design

**Core Principle:** Fail fast, fail smart, fail with context.

**3-Attempt Retry Strategy:**
```
Attempt 1 → Failure → Wait 60s →
Attempt 2 → Failure → Wait 60s →
Attempt 3 → Failure → STORE IN FAILED_TRANSACTIONS TABLE → Return 200 (stop Cloud Tasks retry)
```

**Key Architectural Components:**

1. **Attempt Counter Mechanism** - Track attempts via encrypted token
2. **Failed Transactions Table** - Store all failed transaction data
3. **Error Classification System** - Categorize failures with actionable error codes
4. **Recovery Endpoints** - Manual/automated retry mechanisms
5. **Alerting System** - Notify on failures requiring human intervention
6. **Dashboard Integration** - View and manage failed transactions

---

## DATABASE SCHEMA

### New Table: `failed_transactions`

**Purpose:** Store ETH payment transactions that failed after 3 attempts with full context for recovery.

```sql
CREATE TABLE failed_transactions (
    -- Primary Key
    id SERIAL PRIMARY KEY,

    -- Original Transaction Data (from token)
    unique_id VARCHAR(16) NOT NULL,
    cn_api_id VARCHAR(16) NOT NULL,
    from_currency VARCHAR(10) NOT NULL,
    from_network VARCHAR(10) NOT NULL,
    from_amount NUMERIC(18, 8) NOT NULL,  -- High precision for crypto amounts
    payin_address VARCHAR(100) NOT NULL,

    -- Context (instant/threshold/batch)
    context VARCHAR(20) NOT NULL DEFAULT 'instant',

    -- Failure Metadata
    error_code VARCHAR(50) NOT NULL,
    error_message TEXT,
    last_error_details JSONB,  -- Store full error context

    -- Retry Tracking
    attempt_count INTEGER NOT NULL DEFAULT 3,
    last_attempt_timestamp TIMESTAMP NOT NULL,

    -- Status Tracking
    status VARCHAR(30) NOT NULL DEFAULT 'failed_pending_review',
    -- Status values:
    --   'failed_pending_review' - Awaiting investigation
    --   'failed_retryable' - Can be retried (manual or auto)
    --   'failed_cancelled' - Permanently cancelled (won't retry)
    --   'retry_scheduled' - Queued for automated retry
    --   'retry_in_progress' - Currently retrying
    --   'recovered' - Successfully recovered via retry

    -- Recovery Metadata
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_attempt TIMESTAMP,
    recovery_tx_hash VARCHAR(100),  -- If recovered, store successful tx_hash
    recovered_at TIMESTAMP,
    recovered_by VARCHAR(50),  -- 'manual', 'automated', 'admin_user_id'

    -- Notes (for manual investigation)
    admin_notes TEXT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_failed_transactions_unique_id ON failed_transactions(unique_id);
CREATE INDEX idx_failed_transactions_cn_api_id ON failed_transactions(cn_api_id);
CREATE INDEX idx_failed_transactions_status ON failed_transactions(status);
CREATE INDEX idx_failed_transactions_error_code ON failed_transactions(error_code);
CREATE INDEX idx_failed_transactions_created_at ON failed_transactions(created_at DESC);

-- Composite index for retry queries
CREATE INDEX idx_failed_transactions_retry ON failed_transactions(status, error_code, created_at)
WHERE status IN ('failed_retryable', 'retry_scheduled');
```

**Design Decisions:**

1. **JSONB for error_details** - Flexible storage for varied error contexts
2. **High precision NUMERIC** - Match GCHostPay3's existing precision requirements
3. **Status-driven workflow** - Enable state machine for recovery process
4. **Retry metadata** - Track recovery attempts separately from original attempts
5. **Admin notes** - Support manual investigation and resolution notes

---

## ERROR CLASSIFICATION SYSTEM

### Error Code Taxonomy

**Purpose:** Classify failures into actionable categories for targeted resolution.

**Error Code Format:** `CATEGORY_SPECIFIC_REASON`

### Critical Errors (Permanent Failures - Cannot Auto-Retry)

| Error Code | Description | Cause | Resolution |
|------------|-------------|-------|------------|
| `INSUFFICIENT_FUNDS` | Host wallet has insufficient ETH | Balance too low for payment + gas | Add ETH to host wallet, manual retry |
| `INVALID_ADDRESS` | Payin address malformed/invalid | Bad ChangeNow response or data corruption | Investigate upstream service, cancel transaction |
| `INVALID_AMOUNT` | Payment amount invalid (0, negative, too large) | Upstream calculation bug | Fix upstream service, recalculate, manual retry |
| `TRANSACTION_REVERTED_PERMANENT` | Transaction reverted on-chain (non-gas) | Contract execution failure | Investigate blockchain state, likely cancel |

### Transient Errors (Temporary Failures - Can Auto-Retry)

| Error Code | Description | Cause | Resolution |
|------------|-------------|-------|------------|
| `NETWORK_TIMEOUT` | RPC connection timeout | Alchemy API slow/unavailable | Auto-retry after cooldown period |
| `RATE_LIMIT_EXCEEDED` | Alchemy 429 rate limit hit | Too many requests | Auto-retry after extended backoff (5-10 min) |
| `NONCE_CONFLICT` | Nonce already used or too low | Race condition or stuck transaction | Auto-retry with nonce refresh |
| `GAS_PRICE_SPIKE` | Gas price exceeds safety threshold | Network congestion | Auto-retry when gas normalizes |
| `CONFIRMATION_TIMEOUT` | Transaction not confirmed within 300s | Mempool congestion | Check on-chain status, may be mined |

### Configuration Errors (System Issues - Require Admin Intervention)

| Error Code | Description | Cause | Resolution |
|------------|-------------|-------|------------|
| `RPC_CONNECTION_FAILED` | Cannot connect to Ethereum RPC | Alchemy API down or config error | Check credentials, service status |
| `WALLET_UNLOCKED_FAILED` | Cannot access wallet private key | Secret Manager error | Verify wallet configuration |
| `WEB3_INITIALIZATION_FAILED` | Web3 provider initialization failed | Library error or network issue | Review logs, check dependencies |

### Unknown Errors (Catch-All)

| Error Code | Description | Cause | Resolution |
|------------|-------------|-------|------------|
| `UNKNOWN_ERROR` | Unexpected exception | Unhandled edge case | Manual investigation required |

---

## UPDATED GCHOSTPAY3 FLOW

### Modified Payment Execution Flow

**File:** `tphp3-10-26.py`

```
┌─────────────────────────────────────────────────────────────┐
│ GCHostPay3 POST / (from GCHostPay1 via Cloud Task)         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. Decrypt Token from GCHostPay1                            │
│    - Extract: unique_id, cn_api_id, amount, payin_address   │
│    - Extract: attempt_count (NEW - default to 1)            │
│    - Extract: context (instant/threshold/batch)             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Check Attempt Count                                      │
│    - If attempt_count > 3 → SKIP (Cloud Tasks retry bug)    │
│    - If attempt_count <= 3 → PROCEED                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Execute ETH Payment (wallet_manager.py)                  │
│    - Attempt transaction with current retry logic           │
│    - Capture error details if failure occurs                │
└─────────────────────────────────────────────────────────────┘
                          ↓
                ┌─────────┴─────────┐
                │                   │
            SUCCESS              FAILURE
                │                   │
                ↓                   ↓
┌──────────────────────┐  ┌──────────────────────────────────┐
│ 4a. Success Path     │  │ 4b. Failure Path                 │
│ - Log to DB          │  │ - Classify error → error_code    │
│ - Encrypt response   │  │ - Increment attempt_count        │
│ - Send to GCHostPay1 │  │ - Check: attempt_count < 3?      │
└──────────────────────┘  └──────────────────────────────────┘
                                      ↓
                          ┌───────────┴───────────┐
                          │                       │
                   attempt < 3              attempt >= 3
                          │                       │
                          ↓                       ↓
          ┌───────────────────────────┐  ┌────────────────────────┐
          │ 5a. Retry Path            │  │ 5b. Failed Path        │
          │ - Re-encrypt token        │  │ - Store in             │
          │   with incremented count  │  │   failed_transactions  │
          │ - Re-enqueue to self      │  │ - Classify error_code  │
          │   via Cloud Task (60s)    │  │ - Send failure alert   │
          │ - Return 200 (success)    │  │ - Return 200 (success) │
          └───────────────────────────┘  └────────────────────────┘
                          ↓                       ↓
                  (Retry Loop)           (Stop - No More Retries)
```

**Key Changes from Current Implementation:**

1. **Token carries attempt_count** - Incremented on each retry
2. **Error classification on failure** - Map exception → error_code
3. **Conditional retry vs storage** - <= 2 attempts: retry, >= 3: store
4. **Self-enqueue for retry** - GCHostPay3 re-queues itself (not via GCHostPay1)
5. **Always return 200** - Prevent Cloud Tasks' built-in retry (we control retry logic now)

---

## ATTEMPT TRACKING MECHANISM

### Token Schema Update

**Current Token (GCHostPay1 → GCHostPay3):**
```python
{
    'unique_id': 'abc123...',
    'cn_api_id': 'xyz789...',
    'from_currency': 'eth',
    'from_network': 'eth',
    'from_amount': 0.001234,
    'payin_address': '0x...',
    'context': 'instant'
}
```

**Updated Token (with attempt tracking):**
```python
{
    'unique_id': 'abc123...',
    'cn_api_id': 'xyz789...',
    'from_currency': 'eth',
    'from_network': 'eth',
    'from_amount': 0.001234,
    'payin_address': '0x...',
    'context': 'instant',
    'attempt_count': 1,           # NEW - Default to 1 on first attempt
    'first_attempt_at': 1730419200,  # NEW - Timestamp of first attempt
    'last_error_code': None       # NEW - Error from previous attempt (if retry)
}
```

**Encryption/Decryption Update:**

**File:** `token_manager.py` (GCHostPay3)

```python
def decrypt_gchostpay1_to_gchostpay3_token(self, encrypted_token: str) -> dict:
    """
    Decrypt token from GCHostPay1 (or self-retry).
    NEW: Handles attempt_count for retry tracking.
    """
    decrypted = self._decrypt_internal_token(encrypted_token)

    # Ensure attempt_count exists (backward compatibility)
    if 'attempt_count' not in decrypted:
        decrypted['attempt_count'] = 1

    if 'first_attempt_at' not in decrypted:
        decrypted['first_attempt_at'] = int(time.time())

    return decrypted

def encrypt_gchostpay3_retry_token(self, token_data: dict, error_code: str = None) -> str:
    """
    NEW METHOD: Encrypt token for self-retry after failure.
    Increments attempt_count and adds error context.
    """
    retry_token = token_data.copy()
    retry_token['attempt_count'] += 1
    retry_token['last_error_code'] = error_code

    return self._encrypt_internal_token(retry_token)
```

---

## IMPLEMENTATION COMPONENTS

### 1. Database Layer Updates

**File:** `database_manager.py` (GCHostPay3)

**New Methods:**

```python
def insert_failed_transaction(
    self,
    unique_id: str,
    cn_api_id: str,
    from_currency: str,
    from_network: str,
    from_amount: float,
    payin_address: str,
    context: str,
    error_code: str,
    error_message: str,
    error_details: dict,
    attempt_count: int
) -> bool:
    """
    Insert failed transaction into failed_transactions table.

    Returns:
        True if successful, False otherwise
    """
    # Implementation with INSERT query
    pass

def get_failed_transaction_by_unique_id(self, unique_id: str) -> dict:
    """
    Check if failed transaction already exists (prevent duplicates).

    Returns:
        Failed transaction record or None
    """
    # Implementation with SELECT query
    pass

def update_failed_transaction_status(
    self,
    unique_id: str,
    status: str,
    admin_notes: str = None
) -> bool:
    """
    Update status of failed transaction (for manual triage).

    Returns:
        True if successful, False otherwise
    """
    # Implementation with UPDATE query
    pass

def get_retryable_failed_transactions(self, limit: int = 10) -> list:
    """
    Fetch failed transactions marked as 'failed_retryable' for automated retry.

    Returns:
        List of failed transaction records
    """
    # Implementation with SELECT WHERE status='failed_retryable'
    pass

def mark_failed_transaction_recovered(
    self,
    unique_id: str,
    recovery_tx_hash: str,
    recovered_by: str
) -> bool:
    """
    Mark failed transaction as recovered after successful retry.

    Returns:
        True if successful, False otherwise
    """
    # Implementation with UPDATE query
    pass
```

---

### 2. Error Classifier Module

**File:** `error_classifier.py` (NEW)

**Purpose:** Map exceptions to error codes for consistent classification.

```python
class ErrorClassifier:
    """
    Classifies payment execution errors into actionable error codes.
    """

    # Critical Errors (permanent failures)
    CRITICAL_ERRORS = {
        'INSUFFICIENT_FUNDS': ['insufficient funds', 'balance too low'],
        'INVALID_ADDRESS': ['invalid address', 'checksum', 'malformed'],
        'INVALID_AMOUNT': ['invalid amount', 'amount must be positive'],
        'TRANSACTION_REVERTED_PERMANENT': ['execution reverted', 'contract error']
    }

    # Transient Errors (can auto-retry)
    TRANSIENT_ERRORS = {
        'NETWORK_TIMEOUT': ['timeout', 'connection timeout', 'read timeout'],
        'RATE_LIMIT_EXCEEDED': ['429', 'too many requests', 'rate limit'],
        'NONCE_CONFLICT': ['nonce too low', 'nonce already used'],
        'GAS_PRICE_SPIKE': ['gas price too high', 'max fee exceeded'],
        'CONFIRMATION_TIMEOUT': ['transaction not in chain', 'confirmation timeout']
    }

    # Configuration Errors (system issues)
    CONFIG_ERRORS = {
        'RPC_CONNECTION_FAILED': ['could not connect', 'rpc unavailable'],
        'WALLET_UNLOCKED_FAILED': ['private key', 'wallet unlock'],
        'WEB3_INITIALIZATION_FAILED': ['web3 initialization']
    }

    @staticmethod
    def classify_error(exception: Exception) -> tuple[str, bool]:
        """
        Classify exception into error_code and retryable status.

        Args:
            exception: Exception raised during payment execution

        Returns:
            Tuple of (error_code, is_retryable)

        Example:
            ('RATE_LIMIT_EXCEEDED', True)
            ('INSUFFICIENT_FUNDS', False)
        """
        error_msg = str(exception).lower()

        # Check critical errors (not retryable)
        for error_code, patterns in ErrorClassifier.CRITICAL_ERRORS.items():
            if any(pattern in error_msg for pattern in patterns):
                return (error_code, False)

        # Check transient errors (retryable)
        for error_code, patterns in ErrorClassifier.TRANSIENT_ERRORS.items():
            if any(pattern in error_msg for pattern in patterns):
                return (error_code, True)

        # Check config errors (not auto-retryable, needs admin)
        for error_code, patterns in ErrorClassifier.CONFIG_ERRORS.items():
            if any(pattern in error_msg for pattern in patterns):
                return (error_code, False)

        # Default to unknown error (not retryable - requires investigation)
        return ('UNKNOWN_ERROR', False)

    @staticmethod
    def get_error_description(error_code: str) -> str:
        """
        Get human-readable description of error code.

        Returns:
            Error description string
        """
        descriptions = {
            'INSUFFICIENT_FUNDS': 'Host wallet has insufficient ETH balance',
            'INVALID_ADDRESS': 'Payment address is invalid or malformed',
            'INVALID_AMOUNT': 'Payment amount is invalid (zero, negative, or too large)',
            'NETWORK_TIMEOUT': 'RPC connection timeout (Alchemy API slow/unavailable)',
            'RATE_LIMIT_EXCEEDED': 'Alchemy API rate limit exceeded (429)',
            'NONCE_CONFLICT': 'Transaction nonce conflict (already used or too low)',
            'CONFIRMATION_TIMEOUT': 'Transaction not confirmed within 300 seconds',
            # ... add all error codes
        }
        return descriptions.get(error_code, 'Unknown error occurred')
```

---

### 3. Updated Payment Execution Endpoint

**File:** `tphp3-10-26.py`

**Modified `execute_eth_payment()` endpoint:**

```python
@app.route("/", methods=["POST"])
def execute_eth_payment():
    """
    Main endpoint with 3-attempt retry logic.

    Flow:
    1. Decrypt token (extract attempt_count)
    2. Check attempt limit (>3 = skip duplicate Cloud Tasks retry)
    3. Execute payment
    4. On success: Log and callback to GCHostPay1
    5. On failure:
       a. If attempt < 3: Classify error, re-enqueue self with incremented count
       b. If attempt >= 3: Store in failed_transactions, send alert, stop
    """
    try:
        # ... existing token decryption ...

        # EXTRACT ATTEMPT COUNT
        attempt_count = decrypted_data.get('attempt_count', 1)
        first_attempt_at = decrypted_data.get('first_attempt_at', int(time.time()))

        print(f"🔢 [ENDPOINT] Attempt #{attempt_count}/3")

        # CHECK ATTEMPT LIMIT (prevent Cloud Tasks duplicate retry)
        if attempt_count > 3:
            print(f"⚠️ [ENDPOINT] Attempt count exceeds limit - skipping (Cloud Tasks retry bug)")
            return jsonify({"status": "skipped", "reason": "attempt_limit_exceeded"}), 200

        # EXECUTE PAYMENT
        try:
            tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
                to_address=payin_address,
                amount=from_amount,
                unique_id=unique_id
            )

            if tx_result and tx_result['status'] == 'success':
                # SUCCESS PATH (existing code)
                print(f"✅ [ENDPOINT] Payment successful after {attempt_count} attempt(s)")
                # ... existing success handling (log DB, encrypt response, send to GCHostPay1) ...
                return jsonify({...}), 200

            else:
                # This should never happen with current retry logic, but handle it
                raise Exception("Payment returned None or failed status")

        except Exception as payment_error:
            # FAILURE PATH
            print(f"❌ [ENDPOINT] Payment execution failed: {payment_error}")

            # CLASSIFY ERROR
            from error_classifier import ErrorClassifier
            error_code, is_retryable = ErrorClassifier.classify_error(payment_error)
            error_message = str(payment_error)

            print(f"📊 [ENDPOINT] Error classified: {error_code} (retryable: {is_retryable})")

            # DECIDE: RETRY OR STORE?
            if attempt_count < 3:
                # RETRY PATH (attempt 1 or 2)
                print(f"🔄 [ENDPOINT] Retrying (attempt {attempt_count}/3)")

                # Re-encrypt token with incremented attempt count
                retry_token_data = decrypted_data.copy()
                retry_token_data['attempt_count'] = attempt_count + 1
                retry_token_data['last_error_code'] = error_code

                encrypted_retry_token = token_manager.encrypt_gchostpay3_retry_token(
                    retry_token_data,
                    error_code=error_code
                )

                # Re-enqueue to self via Cloud Tasks with 60s delay
                retry_task = cloudtasks_client.enqueue_gchostpay3_retry(
                    queue_name=config.get('gchostpay3_retry_queue'),
                    target_url=f"{config.get('gchostpay3_url')}/",
                    encrypted_token=encrypted_retry_token,
                    schedule_delay_seconds=60
                )

                print(f"✅ [ENDPOINT] Retry task enqueued: {retry_task}")

                return jsonify({
                    "status": "retry_scheduled",
                    "attempt": attempt_count,
                    "next_attempt": attempt_count + 1,
                    "error_code": error_code,
                    "retry_task": retry_task
                }), 200

            else:
                # FAILED PATH (attempt 3 - final failure)
                print(f"💀 [ENDPOINT] FINAL FAILURE after 3 attempts")
                print(f"📊 [ENDPOINT] Storing in failed_transactions table")

                # Store in failed_transactions
                error_details = {
                    'exception_type': type(payment_error).__name__,
                    'exception_message': str(payment_error),
                    'first_attempt_at': first_attempt_at,
                    'last_attempt_at': int(time.time()),
                    'is_retryable': is_retryable
                }

                db_success = db_manager.insert_failed_transaction(
                    unique_id=unique_id,
                    cn_api_id=cn_api_id,
                    from_currency=from_currency,
                    from_network=from_network,
                    from_amount=from_amount,
                    payin_address=payin_address,
                    context=context,
                    error_code=error_code,
                    error_message=error_message,
                    error_details=error_details,
                    attempt_count=3
                )

                if db_success:
                    print(f"✅ [ENDPOINT] Failed transaction stored successfully")
                else:
                    print(f"❌ [ENDPOINT] Failed to store failed transaction (non-fatal)")

                # SEND FAILURE ALERT
                alert_sent = send_failure_alert(
                    unique_id=unique_id,
                    cn_api_id=cn_api_id,
                    error_code=error_code,
                    error_message=error_message,
                    context=context,
                    amount=from_amount
                )

                if alert_sent:
                    print(f"✅ [ENDPOINT] Failure alert sent")

                # NOTIFY UPSTREAM SERVICE (GCHostPay1, GCMicroBatchProcessor, etc.)
                # This allows upstream to mark batch/accumulation as failed
                notify_upstream_failure(
                    context=context,
                    unique_id=unique_id,
                    cn_api_id=cn_api_id,
                    error_code=error_code
                )

                # Return 200 to prevent Cloud Tasks retry
                return jsonify({
                    "status": "failed_permanently",
                    "attempts": 3,
                    "error_code": error_code,
                    "error_message": error_message,
                    "stored_in_db": db_success
                }), 200

    except Exception as e:
        # Top-level error handler
        print(f"❌ [ENDPOINT] Unexpected top-level error: {e}")
        # Return 500 to trigger Cloud Tasks retry (for infrastructure errors)
        return jsonify({"status": "error", "message": str(e)}), 500
```

---

### 4. Alerting System

**File:** `alerting.py` (NEW)

**Purpose:** Send notifications when transactions fail permanently.

```python
import requests
from typing import Optional

class AlertingService:
    """
    Handles failure notifications via multiple channels.
    """

    def __init__(self, config: dict):
        self.slack_webhook_url = config.get('slack_alert_webhook')
        self.admin_email = config.get('admin_alert_email')
        self.enabled = config.get('alerting_enabled', True)

    def send_payment_failure_alert(
        self,
        unique_id: str,
        cn_api_id: str,
        error_code: str,
        error_message: str,
        context: str,
        amount: float,
        attempt_count: int = 3
    ) -> bool:
        """
        Send multi-channel alert for payment failure.

        Channels:
        - Slack webhook
        - Email (future)
        - Cloud Logging structured log (always)

        Returns:
            True if alert sent successfully
        """
        if not self.enabled:
            print(f"⚠️ [ALERT] Alerting disabled - skipping")
            return False

        # Build alert message
        alert_title = f"🚨 ETH Payment Failed After {attempt_count} Attempts"
        alert_body = f"""
**Transaction Details:**
- Unique ID: `{unique_id}`
- ChangeNow ID: `{cn_api_id}`
- Context: `{context}`
- Amount: `{amount} ETH`

**Failure Details:**
- Error Code: `{error_code}`
- Error Message: `{error_message}`
- Attempts: `{attempt_count}`

**Next Steps:**
1. Review failed transaction in database: `SELECT * FROM failed_transactions WHERE unique_id='{unique_id}'`
2. Investigate error code: `{error_code}`
3. Decide on recovery action (manual retry, cancel, fix upstream)

**Dashboard:** [View Failed Transactions](https://console.cloud.google.com/...)
        """

        # Log structured alert to Cloud Logging
        print(f"🚨 [ALERT] {alert_title}")
        print(alert_body)

        # Send Slack notification
        if self.slack_webhook_url:
            try:
                slack_payload = {
                    "text": alert_title,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": alert_body}
                        }
                    ]
                }
                response = requests.post(self.slack_webhook_url, json=slack_payload, timeout=10)

                if response.status_code == 200:
                    print(f"✅ [ALERT] Slack notification sent")
                    return True
                else:
                    print(f"❌ [ALERT] Slack notification failed: {response.status_code}")
                    return False

            except Exception as e:
                print(f"❌ [ALERT] Slack notification error: {e}")
                return False

        return True
```

---

### 5. Recovery Endpoints

**File:** `tphp3-10-26.py`

**New Endpoints for Manual/Automated Recovery:**

#### 5a. Manual Retry Endpoint

```python
@app.route("/retry-failed-transaction", methods=["POST"])
def retry_failed_transaction():
    """
    Manual retry endpoint for failed transactions.

    Auth: Requires admin authentication (TODO: implement auth)

    Request Body:
    {
        "unique_id": "abc123...",
        "force": false  // Skip error code check (force retry even if not retryable)
    }

    Flow:
    1. Fetch failed transaction from DB
    2. Validate status (must be 'failed_pending_review' or 'failed_retryable')
    3. Re-create payment task with fresh attempt_count=1
    4. Mark as 'retry_in_progress'
    """
    try:
        # Parse request
        request_data = request.get_json()
        unique_id = request_data.get('unique_id')
        force = request_data.get('force', False)

        if not unique_id:
            abort(400, "Missing unique_id")

        print(f"🔄 [RETRY] Manual retry requested for: {unique_id}")

        # Fetch failed transaction
        failed_tx = db_manager.get_failed_transaction_by_unique_id(unique_id)

        if not failed_tx:
            abort(404, f"Failed transaction not found: {unique_id}")

        # Validate status
        if failed_tx['status'] not in ['failed_pending_review', 'failed_retryable']:
            abort(400, f"Cannot retry transaction with status: {failed_tx['status']}")

        # Check if error is retryable (unless forced)
        if not force:
            from error_classifier import ErrorClassifier
            error_code = failed_tx['error_code']

            # Check if error code is in transient errors
            is_transient = error_code in ErrorClassifier.TRANSIENT_ERRORS

            if not is_transient:
                return jsonify({
                    "status": "error",
                    "message": f"Error code {error_code} is not auto-retryable. Use force=true to override."
                }), 400

        # Re-create payment token with fresh attempt_count
        retry_token_data = {
            'unique_id': failed_tx['unique_id'],
            'cn_api_id': failed_tx['cn_api_id'],
            'from_currency': failed_tx['from_currency'],
            'from_network': failed_tx['from_network'],
            'from_amount': float(failed_tx['from_amount']),
            'payin_address': failed_tx['payin_address'],
            'context': failed_tx['context'],
            'attempt_count': 1,  # Reset to 1
            'first_attempt_at': int(time.time()),
            'last_error_code': None
        }

        encrypted_retry_token = token_manager.encrypt_gchostpay1_to_gchostpay3_token(
            **retry_token_data
        )

        # Enqueue retry task
        retry_task = cloudtasks_client.enqueue_gchostpay3_retry(
            queue_name=config.get('gchostpay3_retry_queue'),
            target_url=f"{config.get('gchostpay3_url')}/",
            encrypted_token=encrypted_retry_token,
            schedule_delay_seconds=5  # Immediate retry (5s delay for safety)
        )

        # Update failed transaction status
        db_manager.update_failed_transaction_status(
            unique_id=unique_id,
            status='retry_in_progress',
            retry_count=failed_tx['retry_count'] + 1
        )

        print(f"✅ [RETRY] Manual retry enqueued: {retry_task}")

        return jsonify({
            "status": "success",
            "message": "Retry task enqueued",
            "unique_id": unique_id,
            "retry_task": retry_task,
            "retry_count": failed_tx['retry_count'] + 1
        }), 200

    except Exception as e:
        print(f"❌ [RETRY] Error: {e}")
        abort(500, f"Retry failed: {str(e)}")
```

#### 5b. List Failed Transactions Endpoint

```python
@app.route("/failed-transactions", methods=["GET"])
def list_failed_transactions():
    """
    List failed transactions with filtering.

    Query Parameters:
    - status: Filter by status (optional)
    - error_code: Filter by error code (optional)
    - limit: Max results (default 50)
    - offset: Pagination offset (default 0)

    Returns:
    {
        "failed_transactions": [...],
        "total_count": 123,
        "limit": 50,
        "offset": 0
    }
    """
    # TODO: Implement query and pagination
    pass
```

#### 5c. Update Failed Transaction Status Endpoint

```python
@app.route("/failed-transactions/<unique_id>/status", methods=["PUT"])
def update_failed_transaction_status_endpoint(unique_id: str):
    """
    Update status of failed transaction (for manual triage).

    Request Body:
    {
        "status": "failed_cancelled",
        "admin_notes": "Upstream bug fixed, will retry after redeployment"
    }

    Valid status transitions:
    - failed_pending_review → failed_retryable (mark as safe to retry)
    - failed_pending_review → failed_cancelled (permanently cancel)
    - retry_in_progress → failed_retryable (retry failed, mark for re-retry)
    - retry_in_progress → recovered (retry succeeded)
    """
    # TODO: Implement status update with validation
    pass
```

---

### 6. Automated Recovery Service (Optional Future Enhancement)

**File:** `gc_failed_transaction_retry/ftretry10-26.py` (NEW SERVICE)

**Purpose:** Periodically check `failed_transactions` for auto-retryable failures and retry them.

**Trigger:** Cloud Scheduler (every 30 minutes)

**Flow:**
```
1. Query failed_transactions WHERE status='failed_retryable' AND error_code IN (TRANSIENT_ERRORS)
2. For each record:
   a. Check cooldown period (e.g., retry only if created_at > 1 hour ago)
   b. Check retry limit (e.g., max 5 automated retries per transaction)
   c. Re-enqueue to GCHostPay3 with fresh attempt_count
   d. Mark as 'retry_scheduled'
3. Log results
```

**Benefits:**
- Automatic recovery from transient failures (network issues, rate limits)
- No manual intervention needed for common failures
- Configurable retry policies per error code

**Risk Mitigation:**
- Cooldown periods prevent rapid retry loops
- Retry limits prevent infinite automated retries
- Only retries TRANSIENT_ERRORS (not critical/config errors)

---

## UPSTREAM INTEGRATION

### GCHostPay1 Updates

**File:** `tphp1-10-26.py`

**New Endpoint:** `POST /payment-failed` (callback from GCHostPay3)

**Purpose:** Receive failure notifications from GCHostPay3 for final (3-attempt) failures.

**Flow:**
```python
@app.route("/payment-failed", methods=["POST"])
def payment_failed():
    """
    Callback from GCHostPay3 when payment fails after 3 attempts.

    Request Body (encrypted token):
    {
        'unique_id': '...',
        'cn_api_id': '...',
        'error_code': 'RATE_LIMIT_EXCEEDED',
        'error_message': '...',
        'attempt_count': 3,
        'context': 'batch'
    }

    Flow:
    1. Decrypt token
    2. Route based on context:
       - batch → Notify GCMicroBatchProcessor to mark batch as failed
       - threshold → Notify GCAccumulator to rollback accumulation
       - instant → Mark split_payout_que as failed
    3. Log failure
    4. Return 200
    """
    # TODO: Implement failure routing logic
    pass
```

**Integration Points:**

| Context | Upstream Service | Action on Failure |
|---------|------------------|-------------------|
| `batch` | GCMicroBatchProcessor | Mark `batch_conversions.conversion_status = 'failed'`, rollback `payout_accumulation` to `pending` |
| `threshold` | GCAccumulator | Mark `payout_accumulation.conversion_status = 'failed_payment'` |
| `instant` | GCSplit1 | Mark `split_payout_que.status = 'failed'`, alert channel owner |

---

### GCMicroBatchProcessor Updates

**File:** `microbatch10-26.py`

**New Endpoint:** `POST /batch-payment-failed` (callback from GCHostPay1)

**Purpose:** Handle batch ETH→USDT payment failures.

**Flow:**
```python
@app.route("/batch-payment-failed", methods=["POST"])
def batch_payment_failed():
    """
    Callback when batch conversion payment fails.

    Flow:
    1. Decrypt token (extract batch_conversion_id, error_code)
    2. Mark batch_conversions record as 'failed'
    3. Rollback all payout_accumulation records to 'pending'
       (so they'll be picked up in next threshold check)
    4. Send alert to admin
    5. Return 200
    """
    # TODO: Implement batch failure rollback
    pass
```

**Database Updates:**
```sql
-- Mark batch as failed
UPDATE batch_conversions
SET conversion_status = 'failed',
    failed_reason = 'ETH payment failed after 3 attempts',
    failed_at = NOW()
WHERE batch_conversion_id = %s;

-- Rollback payout accumulations to pending
UPDATE payout_accumulation
SET conversion_status = 'pending',
    batch_conversion_id = NULL
WHERE batch_conversion_id = %s;
```

---

## CLOUD TASKS CONFIGURATION

### New Queue: `gchostpay3-retry-queue`

**Purpose:** Dedicated queue for GCHostPay3 self-retries (separate from main execution queue).

**Configuration:**
```bash
gcloud tasks queues create gchostpay3-retry-queue \
  --location=us-central1 \
  --max-dispatches-per-second=10 \
  --max-concurrent-dispatches=5 \
  --max-attempts=1 \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-retry-duration=0s
```

**Why separate queue?**
- Isolate retries from new payment requests (prevent retry backlog blocking new payments)
- Different rate limits (lower for retries)
- `max-attempts=1` - We control retry logic, don't want Cloud Tasks to retry
- `max-retry-duration=0s` - No automatic retries

**Queue Architecture:**
```
GCHostPay1 → gchostpay1-execution-queue → GCHostPay3 (attempt 1)
                                              ↓ (failure)
                                              ↓ (self-enqueue)
              gchostpay3-retry-queue → GCHostPay3 (attempt 2)
                                              ↓ (failure)
                                              ↓ (self-enqueue)
              gchostpay3-retry-queue → GCHostPay3 (attempt 3)
                                              ↓ (failure)
                                              ↓ (store in failed_transactions)
```

---

## MONITORING & OBSERVABILITY

### Cloud Logging Structured Logs

**Log Error Events with Structured Data:**

```python
import json
from google.cloud import logging as cloud_logging

def log_failed_transaction_structured(
    unique_id: str,
    cn_api_id: str,
    error_code: str,
    error_message: str,
    attempt_count: int,
    context: str
):
    """
    Log failed transaction as structured JSON for Cloud Logging queries.
    """
    log_entry = {
        'severity': 'ERROR',
        'event_type': 'eth_payment_failed_permanently',
        'unique_id': unique_id,
        'cn_api_id': cn_api_id,
        'error_code': error_code,
        'error_message': error_message,
        'attempt_count': attempt_count,
        'context': context,
        'timestamp': int(time.time())
    }

    # Print as JSON for Cloud Logging ingestion
    print(json.dumps(log_entry))
```

**Cloud Logging Query Examples:**

```sql
-- All failed transactions in last 24 hours
resource.type="cloud_run_revision"
jsonPayload.event_type="eth_payment_failed_permanently"
timestamp >= "2025-11-01T00:00:00Z"

-- Failed transactions by error code
resource.type="cloud_run_revision"
jsonPayload.event_type="eth_payment_failed_permanently"
jsonPayload.error_code="RATE_LIMIT_EXCEEDED"

-- Failed batch conversions
resource.type="cloud_run_revision"
jsonPayload.event_type="eth_payment_failed_permanently"
jsonPayload.context="batch"
```

---

### Cloud Monitoring Metrics

**Custom Metrics to Track:**

1. **Failed Transaction Count** (by error_code)
   - Metric: `custom.googleapis.com/gchostpay3/failed_transactions_count`
   - Labels: `error_code`, `context`

2. **Payment Attempt Distribution**
   - Metric: `custom.googleapis.com/gchostpay3/payment_attempts`
   - Values: 1, 2, 3 (histogram)

3. **Failed Transaction Recovery Rate**
   - Metric: `custom.googleapis.com/gchostpay3/recovery_success_rate`
   - Labels: `recovery_type` (manual, automated)

**Alert Policies:**

```yaml
# Alert when >5 failed transactions in 1 hour
condition:
  displayName: "High Failed Transaction Rate"
  conditionThreshold:
    filter: "metric.type=\"custom.googleapis.com/gchostpay3/failed_transactions_count\""
    comparison: COMPARISON_GT
    thresholdValue: 5
    duration: 3600s

# Alert on INSUFFICIENT_FUNDS error (requires immediate action)
condition:
  displayName: "Host Wallet Low Balance"
  conditionThreshold:
    filter: "metric.type=\"custom.googleapis.com/gchostpay3/failed_transactions_count\" AND metric.label.error_code=\"INSUFFICIENT_FUNDS\""
    comparison: COMPARISON_GT
    thresholdValue: 0
    duration: 60s
```

---

## SCALABILITY CONSIDERATIONS

### Database Performance

**Query Patterns:**
- **High frequency:** INSERT failed transactions (on every 3rd attempt failure)
- **Medium frequency:** SELECT retryable failed transactions (every 30 min by automated retry service)
- **Low frequency:** Manual queries for triage

**Optimization:**
- Indexes on `status`, `error_code`, `created_at` ensure fast queries
- Composite index on `(status, error_code, created_at)` for retry queries
- JSONB `error_details` field allows flexible error context without schema changes

**Growth Estimates:**
- **Worst case:** 10 failed transactions/hour = 240/day = ~7,200/month
- **Realistic:** 1-2 failed transactions/day = ~60/month
- **Table size:** ~10KB/row × 7,200 rows = ~70MB/month (negligible)

**Archival Strategy:**
- After 90 days, move recovered/cancelled transactions to `failed_transactions_archive`
- Keep active failures indefinitely until resolved

---

### Cloud Tasks Quota

**Current Quotas (us-central1):**
- Max dispatch rate: 500/sec per queue
- Max concurrent: 1000 per queue

**Retry Queue Impact:**
- Max retry rate: ~3 attempts × 60s = 1 retry/min per transaction
- Worst case: 10 concurrent failures = 10 retries/min = 0.17/sec
- **Quota usage:** <1% (negligible impact)

---

### Cost Analysis

**Additional Costs:**

1. **Cloud Run Invocations:**
   - Retry attempts: 2 extra invocations per failed transaction
   - Cost: $0.40/million × 2 × 60/month = $0.000048/month (negligible)

2. **Cloud Tasks:**
   - Retry enqueue: 2 tasks per failed transaction
   - Cost: $0.40/million × 2 × 60/month = $0.000048/month (negligible)

3. **Database Storage:**
   - ~70MB/month growth
   - Cost: $0.17/GB × 0.07GB = $0.012/month (negligible)

4. **Alerting:**
   - Slack webhooks: Free
   - Cloud Logging: Included in quota

**Total Additional Cost:** <$0.02/month (negligible)

---

## MIGRATION PATH

### Phase 1: Database Setup (No Code Changes)

**Steps:**
1. Create `failed_transactions` table via migration script
2. Verify table creation and indexes
3. Test INSERT/SELECT queries manually

**Risk:** None (read-only addition)

---

### Phase 2: Code Deployment (GCHostPay3 Only)

**Steps:**
1. Add `error_classifier.py` module
2. Add `alerting.py` module (optional - can start disabled)
3. Update `database_manager.py` with failed transaction methods
4. Update `token_manager.py` with attempt tracking
5. Update `tphp3-10-26.py` with 3-attempt logic
6. Deploy GCHostPay3 with new code

**Testing:**
1. Test with broken transaction (e.g., invalid amount)
2. Verify 3 retry attempts occur
3. Verify failed transaction stored in DB
4. Verify alert sent (if enabled)

**Risk:** Medium
- If retry logic fails, Cloud Tasks will retry (current behavior)
- Failed transaction storage is non-blocking (won't break payment flow)

**Rollback Plan:**
- Redeploy previous GCHostPay3 revision
- Failed transactions table remains (no data loss)

---

### Phase 3: Upstream Integration (GCHostPay1, GCMicroBatchProcessor)

**Steps:**
1. Add `/payment-failed` endpoint to GCHostPay1
2. Add `/batch-payment-failed` endpoint to GCMicroBatchProcessor
3. Update GCHostPay3 to notify upstream on final failure
4. Deploy all services

**Testing:**
1. Simulate batch payment failure
2. Verify batch rollback logic
3. Verify accumulations return to pending

**Risk:** Low
- Failure notifications are optional (won't break if missing)
- Rollback: Just remove notification calls

---

### Phase 4: Recovery Endpoints & Automation (Optional)

**Steps:**
1. Add manual retry endpoint to GCHostPay3
2. Add failed transactions list endpoint
3. Add update status endpoint
4. (Optional) Deploy automated retry service

**Testing:**
1. Manually retry a failed transaction
2. Verify recovery path works
3. Test automated retry service (if deployed)

**Risk:** Low (recovery is separate from critical path)

---

## APPENDIX: SQL MIGRATION SCRIPT

**File:** `create_failed_transactions_table.sql`

```sql
-- Migration: Create failed_transactions table for GCHostPay3 error handling
-- Date: 2025-11-01
-- Author: TelePay Architecture
-- Jira: N/A

BEGIN;

-- Create failed_transactions table
CREATE TABLE IF NOT EXISTS failed_transactions (
    -- Primary Key
    id SERIAL PRIMARY KEY,

    -- Original Transaction Data
    unique_id VARCHAR(16) NOT NULL,
    cn_api_id VARCHAR(16) NOT NULL,
    from_currency VARCHAR(10) NOT NULL,
    from_network VARCHAR(10) NOT NULL,
    from_amount NUMERIC(18, 8) NOT NULL,
    payin_address VARCHAR(100) NOT NULL,

    -- Context
    context VARCHAR(20) NOT NULL DEFAULT 'instant',

    -- Failure Metadata
    error_code VARCHAR(50) NOT NULL,
    error_message TEXT,
    last_error_details JSONB,

    -- Retry Tracking
    attempt_count INTEGER NOT NULL DEFAULT 3,
    last_attempt_timestamp TIMESTAMP NOT NULL,

    -- Status Tracking
    status VARCHAR(30) NOT NULL DEFAULT 'failed_pending_review',

    -- Recovery Metadata
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_attempt TIMESTAMP,
    recovery_tx_hash VARCHAR(100),
    recovered_at TIMESTAMP,
    recovered_by VARCHAR(50),

    -- Notes
    admin_notes TEXT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_failed_transactions_unique_id ON failed_transactions(unique_id);
CREATE INDEX idx_failed_transactions_cn_api_id ON failed_transactions(cn_api_id);
CREATE INDEX idx_failed_transactions_status ON failed_transactions(status);
CREATE INDEX idx_failed_transactions_error_code ON failed_transactions(error_code);
CREATE INDEX idx_failed_transactions_created_at ON failed_transactions(created_at DESC);

-- Composite index for retry queries
CREATE INDEX idx_failed_transactions_retry ON failed_transactions(status, error_code, created_at)
WHERE status IN ('failed_retryable', 'retry_scheduled');

-- Add comment
COMMENT ON TABLE failed_transactions IS 'Stores ETH payment transactions that failed after 3 retry attempts for recovery and analysis';

COMMIT;

-- Verify table creation
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'failed_transactions'
ORDER BY ordinal_position;
```

---

## SUMMARY

This architecture provides a **robust, scalable, and maintainable** error handling system for GCHostPay3 that:

✅ **Solves the immediate problem** - Stops endless retry loops after 3 attempts
✅ **Provides visibility** - All failures captured in database with full context
✅ **Enables recovery** - Manual and automated retry mechanisms
✅ **Scales gracefully** - Minimal cost and performance impact
✅ **Integrates seamlessly** - Works with existing Cloud Tasks/token architecture
✅ **Supports operations** - Alerting, monitoring, and dashboard integration

**Next Steps:**
1. Review this architecture document
2. Create implementation checklist
3. Execute phased deployment (Phase 1 → Phase 2 → Phase 3 → Phase 4)
4. Monitor production behavior and iterate

---

**END OF DOCUMENT**
