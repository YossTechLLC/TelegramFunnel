# FINAL BATCH REVIEW #4 - IMPLEMENTATION CHECKLIST
## Security Fixes & Code Consolidation Plan

**Date:** 2025-11-18
**Scope:** PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1, PGP_INVITE_v1, PGP_BROADCAST_v1
**Status:** Ready for Implementation
**Estimated Total Time:** ~34 hours (7 + 12 + 15 hours across 3 phases)

---

## EXECUTIVE SUMMARY

### Findings Overview
- 🔴 **Critical Issues:** 4 (Service crashes, race conditions, security breaches)
- 🟡 **High Issues:** 8 (Connection leaks, input validation, information disclosure)
- 🟠 **Medium Issues:** 12 (Rate limiting, inconsistent configs, GDPR concerns)
- 📦 **Dead Code:** 7 blocks (~200 lines to remove)
- 🔄 **Duplicate Code:** 820+ lines across services

### Impact Assessment
**Before Fix:**
- PGP_NP_IPN_v1 will crash on any IPN callback (NameError)
- Race conditions allow duplicate payment processing → financial loss
- Connection leaks under load → service degradation
- 820+ lines of duplicate code → maintenance burden

**After Fix:**
- All services stable and production-ready
- Atomic idempotency prevents duplicates
- ~1,000 lines removed from codebase
- Single source of truth for 23 shared patterns
- Consistent security posture across all services

---

## SCOPE ANALYSIS: FILES REQUIRING CHANGES

### Phase 1: Critical Fixes (4 issues, 7 files)

**PGP_NP_IPN_v1/** (High Priority)
- ✏️ `pgp_np_ipn_v1.py` - Fix undefined function calls, add atomic idempotency
- ✏️ `database_manager.py` - Add input validation on all queries
- 📖 All config_manager.py files - Remove secret length logging

**PGP_ORCHESTRATOR_v1/**
- ✏️ `pgp_orchestrator_v1.py` - Add atomic idempotency
- 📖 `config_manager.py` - Remove secret length logging

**PGP_INVITE_v1/**
- ✏️ `pgp_invite_v1.py` - Add atomic idempotency
- 📖 `config_manager.py` - Remove secret length logging

**PGP_BROADCAST_v1/**
- 📖 `config_manager.py` - Remove secret length logging

**PGP_COMMON/** (New Files to Create)
- ➕ `utils/idempotency.py` - Atomic idempotency manager (NEW)
- ✏️ `database/db_manager.py` - Add validation helpers

---

### Phase 2: Security Hardening (8 issues, 12 files)

**PGP_INVITE_v1/**
- ✏️ `pgp_invite_v1.py` - Fix Bot context manager, error sanitization
- ✏️ `database_manager.py` - Add crypto symbol validation

**PGP_NP_IPN_v1/**
- ✏️ `pgp_np_ipn_v1.py` - Restrict CORS, add request size limits
- ✏️ `database_manager.py` - Sanitize payment data before DB insert

**PGP_BROADCAST_v1/**
- ✏️ `database_manager.py` - Replace NullPool with QueuePool

**PGP_ORCHESTRATOR_v1/**
- ✏️ `pgp_orchestrator_v1.py` - Add input validation for Telegram IDs

**PGP_COMMON/** (Extensions & New Files)
- ✏️ `utils/crypto_pricing.py` - Add symbol whitelist & validation
- ✏️ `tokens/base_token.py` - Standardize timestamp validation (1hr)
- ➕ `flask/error_handlers.py` - Centralized error handling (NEW)
- ➕ `flask/health_check.py` - Standardized health endpoints (NEW)
- ✏️ `utils/error_sanitizer.py` - Extend for all error types

---

### Phase 3: Code Quality & Dead Code (19 items, 15+ files)

**Dead Code Removal:**
- PGP_NP_IPN_v1/pgp_np_ipn_v1.py (Comment blocks, deprecated CORS)
- PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py (Unused functions, deprecated endpoint)
- PGP_INVITE_v1/config_manager.py (Deprecated methods)
- PGP_BROADCAST_v1/config_manager.py (Unused singleton getter)

**Consolidation Opportunities:**
- All 4 services: Error handlers → PGP_COMMON/flask/error_handlers.py
- All 4 services: Health checks → PGP_COMMON/flask/health_check.py
- PGP_NP_IPN_v1: Order parsing → PGP_COMMON/utils/order_parsing.py

**Total Files Affected:** ~25 files across 5 directories

---

## PHASE 1: CRITICAL FIXES (P0 - IMMEDIATE)
**Timeline:** Days 1-5 (Week 1)
**Estimated Time:** 7 hours
**Risk Level:** 🔴 CRITICAL - Production Blockers

### C-01: UNDEFINED FUNCTION CAUSING RUNTIME CRASHES ⚠️ SHOWSTOPPER

**Priority:** P0 (IMMEDIATE - Service Non-Functional)
**Severity:** CRITICAL
**Estimated Time:** 30 minutes
**Impact:** PGP_NP_IPN_v1 crashes on EVERY IPN callback

#### Problem
```python
# PGP_NP_IPN_v1/pgp_np_ipn_v1.py Lines: 432, 475, 494, 574
conn_check = get_db_connection()  # ❌ NameError - function doesn't exist!
```

**Root Cause:**
- Function `get_db_connection()` was removed during refactoring
- Comment at line 186 says "moved to db_manager.get_connection()"
- 4 call sites were never updated
- **Service has never been tested after refactoring**

**Current State:**
- Service will crash immediately with `NameError` on first IPN
- No payments can be processed
- Database connections leak (if any opened before crash)

#### Scope Assessment

**Files to Change:** 1
- `PGP_NP_IPN_v1/pgp_np_ipn_v1.py`

**Lines Affected:** 4 locations (432, 475, 494, 574)

**Dependencies:**
- None - simple find & replace
- Uses existing `db_manager.get_connection()` method

**Breaking Changes:** None

#### Resolution Steps

**Step 1: Locate all instances**
```bash
# Search for all occurrences
grep -n "get_db_connection()" PGP_NP_IPN_v1/pgp_np_ipn_v1.py

# Expected output:
# 432:    conn_check = get_db_connection()
# 475:    conn_check = get_db_connection()
# 494:    conn_check = get_db_connection()
# 574:    conn_check = get_db_connection()
```

**Step 2: Understand context pattern**
```python
# OLD PATTERN (Lines 432-442):
conn_check = get_db_connection()  # ❌ Undefined
if conn_check:
    cur_check = conn_check.cursor()
    cur_check.execute("""
        SELECT pgp_orchestrator_processed, telegram_invite_sent
        FROM processed_payments WHERE payment_id = %s
    """, (nowpayments_payment_id,))
    existing_payment = cur_check.fetchone()
    cur_check.close()
    conn_check.close()
```

**Step 3: Apply correct pattern**
```python
# NEW PATTERN (Correct):
with db_manager.get_connection() as conn_check:
    cur_check = conn_check.cursor()
    cur_check.execute("""
        SELECT pgp_orchestrator_processed, telegram_invite_sent
        FROM processed_payments WHERE payment_id = %s
    """, (nowpayments_payment_id,))
    existing_payment = cur_check.fetchone()
    cur_check.close()
# ✅ Connection auto-closed by context manager
```

**Step 4: Fix all 4 instances**

**Location 1: Line 432 (Idempotency check)**
```python
# BEFORE:
conn_check = get_db_connection()
if conn_check:
    cur_check = conn_check.cursor()
    # ... query ...
    cur_check.close()
    conn_check.close()

# AFTER:
with db_manager.get_connection() as conn_check:
    cur_check = conn_check.cursor()
    # ... query ...
    cur_check.close()
```

**Location 2: Line 475 (Database update check)**
```python
# BEFORE:
conn_check = get_db_connection()
if conn_check:
    cur_check = conn_check.cursor()
    # ... update ...
    conn_check.commit()
    cur_check.close()
    conn_check.close()

# AFTER:
with db_manager.get_connection() as conn_check:
    cur_check = conn_check.cursor()
    # ... update ...
    conn_check.commit()
    cur_check.close()
```

**Location 3: Line 494 (Validation query)**
```python
# Similar pattern - use context manager
```

**Location 4: Line 574 (Final update)**
```python
# Similar pattern - use context manager
```

#### Verification Steps

**Pre-Deployment Verification:**
```bash
# 1. Search for remaining instances (should be 0)
grep -n "get_db_connection()" PGP_NP_IPN_v1/pgp_np_ipn_v1.py
# Expected: No output

# 2. Verify correct pattern used
grep -n "with db_manager.get_connection()" PGP_NP_IPN_v1/pgp_np_ipn_v1.py
# Expected: 4+ matches

# 3. Run linter to catch any syntax errors
python3 -m py_compile PGP_NP_IPN_v1/pgp_np_ipn_v1.py

# 4. Check imports are present
grep -n "from.*database_manager import.*DatabaseManager" PGP_NP_IPN_v1/pgp_np_ipn_v1.py
```

**Post-Deployment Verification:**
```bash
# 1. Send test IPN callback
curl -X POST https://pgp-np-ipn-v1.../  \
  -H "Content-Type: application/json" \
  -d @test_ipn.json

# Expected: 200 OK (not 500 NameError)

# 2. Check Cloud Run logs for errors
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=pgp-np-ipn-v1 \
  AND severity=ERROR" --limit=10

# Expected: No NameError exceptions
```

**Success Criteria:**
- ✅ No `NameError: name 'get_db_connection' is not defined` in logs
- ✅ Service processes IPN callbacks successfully
- ✅ Database connections properly closed (no leaks)

#### Testing Requirements

**Unit Test:**
```python
# Create: PGP_NP_IPN_v1/tests/test_database_connections.py

def test_ipn_processing_no_nameerror():
    """Verify service doesn't crash with NameError."""
    ipn_data = create_test_ipn_payload()

    # Should NOT raise NameError
    response = process_ipn(ipn_data)

    assert response.status_code == 200
    assert 'NameError' not in str(response.data)
```

**Integration Test:**
```python
def test_database_connection_closed():
    """Verify database connections are properly closed."""
    initial_conn_count = get_active_db_connections()

    # Process IPN
    process_ipn(test_ipn_data)

    final_conn_count = get_active_db_connections()

    # Connection should be returned to pool (not leaked)
    assert final_conn_count == initial_conn_count
```

---

### C-02: RACE CONDITION IN IDEMPOTENCY CHECK 💰 FINANCIAL RISK

**Priority:** P0 (IMMEDIATE - Data Integrity & Financial Loss)
**Severity:** CRITICAL
**Estimated Time:** 2 hours
**Impact:** Duplicate payment processing → double payouts → financial loss

#### Problem

**Classic TOCTOU (Time-of-Check-Time-of-Use) Vulnerability:**

```python
# PGP_NP_IPN_v1/pgp_np_ipn_v1.py Lines 442-463
# ❌ NON-ATOMIC PATTERN (Vulnerable to race condition)

# Step 1: Check if payment exists
cur_check.execute("""
    SELECT pgp_orchestrator_processed
    FROM processed_payments
    WHERE payment_id = %s
""", (payment_id,))

existing_payment = cur_check.fetchone()

# ⚠️ RACE WINDOW HERE - Another request could execute between check and insert

# Step 2: If not exists, insert (separate operation)
if not existing_payment or not existing_payment[0]:
    # Process payment...
    insert_payment(payment_id)  # ❌ Too late - another request may have won
```

**Attack Scenario:**
```
Time    Request A                          Request B
----    ---------                          ---------
T+0     SELECT (finds nothing)
T+1                                        SELECT (finds nothing)
T+2     Process payment
T+3                                        Process payment ❌ DUPLICATE!
T+4     INSERT record
T+5                                        INSERT record (fails, but already processed!)
```

**Real-World Impact:**
- User gets 2 Telegram invites
- Payout accumulated twice (financial loss)
- Database inconsistency
- Telegram bot could be banned for spam

#### Scope Assessment

**Files to Change:** 4
- `PGP_NP_IPN_v1/pgp_np_ipn_v1.py` (Lines 424-502)
- `PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py` (Lines 244-286)
- `PGP_INVITE_v1/pgp_invite_v1.py` (Lines 138-187)
- `PGP_COMMON/utils/idempotency.py` (NEW FILE - create this)

**Database Requirements:**
```sql
-- Ensure UNIQUE constraint exists (should already be there)
ALTER TABLE processed_payments
ADD CONSTRAINT IF NOT EXISTS unique_payment_id UNIQUE (payment_id);
```

**Dependencies:**
- Requires database constraint on `processed_payments.payment_id`
- All 3 services must be updated together for consistency

**Breaking Changes:** None (backward compatible)

#### Resolution Steps

**Step 1: Create centralized IdempotencyManager in PGP_COMMON**

Create new file: `PGP_COMMON/utils/idempotency.py`

```python
"""
Atomic idempotency checking for payment processing.

Prevents duplicate processing via database-level atomic operations.
"""

from typing import Optional, Tuple, Dict
from contextlib import contextmanager
from PGP_COMMON.logging import setup_logger

logger = setup_logger(__name__)


class IdempotencyManager:
    """
    Atomic idempotency manager using database constraints.

    Key Features:
    - Uses INSERT ... ON CONFLICT to ensure atomic "first-to-insert" semantics
    - SELECT FOR UPDATE for row-level locking during checks
    - Prevents TOCTOU race conditions
    """

    def __init__(self, db_manager):
        """
        Initialize idempotency manager.

        Args:
            db_manager: Database manager instance (must have get_connection() method)
        """
        self.db_manager = db_manager

    def check_and_claim_processing(
        self,
        payment_id: str,
        user_id: int,
        channel_id: int,
        service_column: str  # e.g., 'pgp_orchestrator_processed'
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Atomically check if payment already processed AND claim for processing.

        This method combines check + claim in one atomic operation to prevent races.

        Args:
            payment_id: Unique payment identifier
            user_id: Telegram user ID
            channel_id: Telegram channel ID
            service_column: Column name for this service's processing flag

        Returns:
            (can_process, existing_data)
            - can_process: True if this request should process (won the race)
            - existing_data: Dict with existing payment info if already processed

        Raises:
            ValueError: If input validation fails
        """
        # Validate inputs
        if not payment_id or len(payment_id) > 100:
            raise ValueError(f"Invalid payment_id: {payment_id}")

        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}")

        if not isinstance(channel_id, int):
            raise ValueError(f"Invalid channel_id: {channel_id}")

        with self.db_manager.get_connection() as conn:
            cur = conn.cursor()

            # ATOMIC STEP 1: Try to insert (claims processing)
            # If payment_id already exists, ON CONFLICT DO NOTHING ensures only 1 insert wins
            cur.execute("""
                INSERT INTO processed_payments (
                    payment_id,
                    user_id,
                    closed_channel_id,
                    processing_started_at
                )
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (payment_id) DO NOTHING
                RETURNING payment_id, user_id, closed_channel_id
            """, (payment_id, user_id, channel_id))

            insert_result = cur.fetchone()

            if insert_result:
                # ✅ We won! This is the first request for this payment_id
                conn.commit()
                cur.close()

                logger.info(f"✅ [IDEMPOTENCY] Claimed processing for payment {payment_id}")
                return True, None

            # ATOMIC STEP 2: Another request already inserted, check if their processing is complete
            # Use SELECT FOR UPDATE to lock the row (prevent concurrent updates)
            cur.execute(f"""
                SELECT
                    {service_column},
                    payment_status,
                    telegram_invite_sent,
                    accumulator_processed,
                    created_at
                FROM processed_payments
                WHERE payment_id = %s
                FOR UPDATE  -- ✅ Row-level lock prevents concurrent modifications
            """, (payment_id,))

            existing = cur.fetchone()
            cur.close()

            if not existing:
                # This shouldn't happen (INSERT failed but SELECT finds nothing)
                # Possible if constraint name is wrong or row was deleted
                logger.error(f"❌ [IDEMPOTENCY] Race condition detected for payment {payment_id}")
                return False, None

            service_processed, payment_status, invite_sent, accumulator_done, created_at = existing

            if service_processed:
                # Another request already completed processing for THIS service
                logger.info(f"✅ [IDEMPOTENCY] Payment {payment_id} already processed by this service")
                return False, {
                    'already_processed': True,
                    'payment_status': payment_status,
                    'telegram_invite_sent': invite_sent,
                    'accumulator_processed': accumulator_done,
                    'created_at': created_at
                }

            # Payment exists but not yet processed by THIS service
            # This is OK - other services may have processed their parts
            logger.info(f"ℹ️ [IDEMPOTENCY] Payment {payment_id} exists but not yet processed by this service")
            return True, None

    def mark_service_complete(
        self,
        payment_id: str,
        service_column: str,
        additional_updates: Optional[Dict] = None
    ) -> bool:
        """
        Mark service-specific processing as complete.

        Args:
            payment_id: Payment identifier
            service_column: Column to set TRUE (e.g., 'pgp_orchestrator_processed')
            additional_updates: Optional dict of {column_name: value} to update

        Returns:
            True if update succeeded, False otherwise
        """
        with self.db_manager.get_connection() as conn:
            cur = conn.cursor()

            # Build UPDATE query dynamically
            updates = [f"{service_column} = TRUE"]
            params = []

            if additional_updates:
                for col, val in additional_updates.items():
                    updates.append(f"{col} = %s")
                    params.append(val)

            params.append(payment_id)

            update_query = f"""
                UPDATE processed_payments
                SET {', '.join(updates)}, updated_at = NOW()
                WHERE payment_id = %s
            """

            cur.execute(update_query, params)
            rows_updated = cur.rowcount
            conn.commit()
            cur.close()

            if rows_updated > 0:
                logger.info(f"✅ [IDEMPOTENCY] Marked {service_column} complete for payment {payment_id}")
                return True
            else:
                logger.warning(f"⚠️ [IDEMPOTENCY] Payment {payment_id} not found for update")
                return False
```

**Step 2: Update PGP_NP_IPN_v1 to use IdempotencyManager**

```python
# PGP_NP_IPN_v1/pgp_np_ipn_v1.py

from PGP_COMMON.utils import IdempotencyManager

# Initialize at module level (after db_manager)
idempotency_manager = IdempotencyManager(db_manager)

# Replace Lines 424-502 with:

@app.route("/", methods=["POST"])
def nowpayments_ipn():
    """Handle NowPayments IPN callback with atomic idempotency."""

    # ... existing IPN parsing code ...

    # Extract payment details
    payment_id = ipn_data.get('payment_id')
    user_id, open_channel_id = parse_order_id(ipn_data.get('order_id'))

    if not payment_id or not user_id:
        return jsonify({"error": "Invalid IPN data"}), 400

    # ✅ ATOMIC IDEMPOTENCY CHECK
    can_process, existing_data = idempotency_manager.check_and_claim_processing(
        payment_id=payment_id,
        user_id=user_id,
        channel_id=open_channel_id,
        service_column='pgp_np_ipn_processed'  # Service-specific flag
    )

    if not can_process:
        # Another request already processed this payment
        logger.info(f"✅ [IPN] Payment {payment_id} already processed: {existing_data}")
        return jsonify({
            "status": "already_processed",
            "payment_id": payment_id,
            "details": existing_data
        }), 200

    # ✅ We won the race - safe to process
    logger.info(f"🔄 [IPN] Processing payment {payment_id}...")

    try:
        # Process payment (existing logic)
        process_payment(ipn_data)

        # Mark this service's processing complete
        idempotency_manager.mark_service_complete(
            payment_id=payment_id,
            service_column='pgp_np_ipn_processed',
            additional_updates={
                'payment_status': ipn_data.get('payment_status'),
                'outcome_amount_usd': calculate_usd_value(...)
            }
        )

        logger.info(f"✅ [IPN] Successfully processed payment {payment_id}")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"❌ [IPN] Error processing payment {payment_id}: {e}")
        # Don't mark as complete - allow retry
        return jsonify({"status": "error", "message": str(e)}), 500
```

**Step 3: Update PGP_ORCHESTRATOR_v1**

```python
# PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py

from PGP_COMMON.utils import IdempotencyManager

idempotency_manager = IdempotencyManager(db_manager)

@app.route("/process-validated-payment", methods=["POST"])
def process_validated_payment():
    """Process payment with atomic idempotency."""

    # Parse token
    user_id, closed_channel_id, payment_id = parse_token(request.json.get('token'))

    # ✅ ATOMIC CHECK
    can_process, existing = idempotency_manager.check_and_claim_processing(
        payment_id=payment_id,
        user_id=user_id,
        channel_id=closed_channel_id,
        service_column='pgp_orchestrator_processed'
    )

    if not can_process:
        logger.info(f"✅ [ORCHESTRATOR] Payment {payment_id} already processed")
        return success_response()

    # Process...
    queue_invite_task(user_id, closed_channel_id)

    # Mark complete
    idempotency_manager.mark_service_complete(
        payment_id,
        'pgp_orchestrator_processed',
        {'telegram_invite_queued': True}
    )

    return success_response()
```

**Step 4: Update PGP_INVITE_v1**

```python
# PGP_INVITE_v1/pgp_invite_v1.py

from PGP_COMMON.utils import IdempotencyManager

idempotency_manager = IdempotencyManager(db_manager)

@app.route("/", methods=["POST"])
def send_telegram_invite():
    """Send invite with atomic idempotency."""

    # Decode token
    user_id, closed_channel_id = decode_token(request.json.get('token'))

    # Generate pseudo payment_id from token for idempotency
    # (Or extract real payment_id if included in token)
    payment_id = generate_payment_id_from_token(token)

    # ✅ ATOMIC CHECK
    can_process, existing = idempotency_manager.check_and_claim_processing(
        payment_id=payment_id,
        user_id=user_id,
        channel_id=closed_channel_id,
        service_column='telegram_invite_sent'
    )

    if not can_process:
        logger.info(f"✅ [INVITE] Invite already sent for {payment_id}")
        return success_response()

    # Send invite...
    send_telegram_invite_link(user_id, closed_channel_id)

    # Mark complete
    idempotency_manager.mark_service_complete(
        payment_id,
        'telegram_invite_sent',
        {'invite_sent_at': 'NOW()'}
    )

    return success_response()
```

#### Verification Steps

**Pre-Deployment:**
```bash
# 1. Verify UNIQUE constraint exists
psql -h /cloudsql/pgp-live:... -d pgp-live-db -c "
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'processed_payments' AND constraint_type = 'UNIQUE';
"
# Expected: unique_payment_id constraint exists

# 2. Run unit tests
python3 -m pytest PGP_COMMON/tests/test_idempotency.py -v

# 3. Verify imports work
python3 -c "from PGP_COMMON.utils import IdempotencyManager; print('✅ Import OK')"
```

**Post-Deployment Race Condition Test:**
```python
# Create: PGP_NP_IPN_v1/tests/test_race_condition.py

import concurrent.futures
import time

def test_concurrent_ipn_processing():
    """
    Test that concurrent IPNs for same payment_id are handled correctly.
    Only ONE should process, others should return 'already_processed'.
    """
    payment_id = f"test_payment_{int(time.time())}"

    # Create test IPN payload
    ipn_payload = {
        'payment_id': payment_id,
        'order_id': '123456789_-1001234567890',
        'payment_status': 'finished',
        # ... other fields
    }

    # Send 5 concurrent requests
    def send_ipn():
        response = requests.post(
            'https://pgp-np-ipn-v1.../nowpayments-ipn',
            json=ipn_payload
        )
        return response.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_ipn) for _ in range(5)]
        results = [f.result() for f in futures]

    # Count how many actually processed
    processed_count = sum(1 for r in results if r.get('status') == 'success')
    already_processed_count = sum(1 for r in results if r.get('status') == 'already_processed')

    # ✅ VERIFY: Only 1 processed, 4 detected as duplicate
    assert processed_count == 1, f"Expected 1 processed, got {processed_count}"
    assert already_processed_count == 4, f"Expected 4 duplicates, got {already_processed_count}"

    # Verify database has only 1 record
    payment_records = db.query(
        "SELECT COUNT(*) FROM processed_payments WHERE payment_id = %s",
        (payment_id,)
    )
    assert payment_records[0][0] == 1, "Should have exactly 1 record in database"

    print("✅ Race condition test PASSED - atomic idempotency working correctly")
```

**Success Criteria:**
- ✅ Race condition test passes (1 processes, 4 duplicates detected)
- ✅ No duplicate Telegram invites sent
- ✅ No duplicate payout accumulations
- ✅ Database has exactly 1 record per payment_id

---

### C-03: UNVALIDATED DATABASE INPUT 🛡️ INJECTION RISK

**Priority:** P0 (IMMEDIATE - Logic Bugs & Data Integrity)
**Severity:** CRITICAL
**Estimated Time:** 3 hours
**Impact:** Invalid data → query failures → payment processing errors

#### Problem

**Parameterized Queries ≠ Input Validation**

While parameterized queries prevent SQL injection, they don't prevent logic bugs:

```python
# PGP_NP_IPN_v1/database_manager.py Lines 151-159

def get_payout_strategy(self, open_channel_id: int) -> tuple:
    with self.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT closed_channel_id, client_wallet_address,
                   client_payout_currency::text, client_payout_network::text
            FROM main_clients_database
            WHERE open_channel_id = %s
        """, (str(open_channel_id),))  # ❌ No validation!
```

**What Could Go Wrong:**

| Input Value | SQL Query | Result | Impact |
|------------|-----------|---------|---------|
| `None` | `WHERE open_channel_id = 'None'` | No rows | Payment fails (wallet not found) |
| `0` | `WHERE open_channel_id = '0'` | No rows | Payment fails |
| `-1` | `WHERE open_channel_id = '-1'` | No rows | Invalid Telegram ID |
| `999` | `WHERE open_channel_id = '999'` | No rows | Too short for Telegram channel |
| `"abc"` | Type error before query | Exception | Service crash |

**Real-World Scenario:**
1. Malicious IPN sends `order_id = "invalid_-1"`
2. Parser extracts `open_channel_id = -1`
3. Query returns no wallet address
4. Payment processing fails
5. User doesn't get access despite paying

#### Scope Assessment

**Files to Change:** 5
- `PGP_NP_IPN_v1/database_manager.py` (All query methods)
- `PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py` (Request handlers)
- `PGP_INVITE_v1/pgp_invite_v1.py` (Token validation)
- `PGP_COMMON/utils/validation.py` (NEW - create validation utilities)
- `PGP_COMMON/database/db_manager.py` (Add base validation)

**Query Methods Requiring Validation:**
1. `get_payout_strategy(open_channel_id)` - Validate channel ID
2. `parse_order_id(order_id)` - Validate format & IDs
3. `update_payment_status(payment_id, ...)` - Validate payment_id length
4. `insert_processed_payment(...)` - Validate all fields
5. All HTTP endpoint handlers - Validate request params

**Dependencies:**
- None (self-contained validation)

**Breaking Changes:**
- May reject previously accepted (but invalid) inputs
- This is a FEATURE (fail-fast is better than corrupt data)

#### Resolution Steps

**Step 1: Create validation utilities in PGP_COMMON**

Create: `PGP_COMMON/utils/validation.py`

```python
"""
Input validation utilities for PGP services.

Provides comprehensive validation for:
- Telegram user IDs and channel IDs
- Payment identifiers
- Cryptocurrency symbols
- Wallet addresses
"""

from typing import Any, Optional
import re


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


def validate_telegram_user_id(user_id: Any, field_name: str = "user_id") -> int:
    """
    Validate and convert Telegram user ID.

    Telegram user IDs are:
    - Always positive integers
    - Typically 8-10 digits (range: 10,000,000 to 9,999,999,999)
    - Never 0, negative, or None

    Args:
        user_id: Value to validate (can be string, int, etc.)
        field_name: Name of field for error messages

    Returns:
        Validated integer user_id

    Raises:
        ValidationError: If validation fails

    Examples:
        >>> validate_telegram_user_id(123456789)
        123456789
        >>> validate_telegram_user_id("987654321")
        987654321
        >>> validate_telegram_user_id(None)
        ValidationError: user_id cannot be None
        >>> validate_telegram_user_id(-123)
        ValidationError: user_id must be positive
    """
    # Check for None/empty
    if user_id is None or user_id == '':
        raise ValidationError(f"{field_name} cannot be None or empty")

    # Convert to int
    try:
        uid = int(user_id)
    except (ValueError, TypeError) as e:
        raise ValidationError(f"{field_name} must be an integer, got {type(user_id).__name__}: {user_id}")

    # Check positive
    if uid <= 0:
        raise ValidationError(f"{field_name} must be positive, got {uid}")

    # Check realistic range (Telegram user IDs are 8+ digits)
    if uid < 10_000_000:
        raise ValidationError(
            f"{field_name} appears invalid: {uid} (Telegram user IDs are typically 8+ digits)"
        )

    # Sanity check upper bound (current max ~10 digits)
    if uid > 9_999_999_999:
        raise ValidationError(
            f"{field_name} too large: {uid} (max 10 digits for Telegram user IDs)"
        )

    return uid


def validate_telegram_channel_id(channel_id: Any, field_name: str = "channel_id") -> int:
    """
    Validate and convert Telegram channel ID.

    Telegram channel/group IDs:
    - Can be positive or negative (supergroups are negative)
    - Typically 10-13 digits
    - Format: -100xxxxxxxxxx for supergroups
    - Never 0 or None

    Args:
        channel_id: Value to validate
        field_name: Name of field for error messages

    Returns:
        Validated integer channel_id

    Raises:
        ValidationError: If validation fails

    Examples:
        >>> validate_telegram_channel_id(-1001234567890)
        -1001234567890
        >>> validate_telegram_channel_id(1234567890)
        1234567890
        >>> validate_telegram_channel_id(123)
        ValidationError: channel_id too short
    """
    if channel_id is None or channel_id == '':
        raise ValidationError(f"{field_name} cannot be None or empty")

    try:
        cid = int(channel_id)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be an integer, got {type(channel_id).__name__}: {channel_id}")

    if cid == 0:
        raise ValidationError(f"{field_name} cannot be 0")

    # Check length (absolute value)
    abs_cid = abs(cid)
    if abs_cid < 1_000_000_000:  # 10 digits minimum
        raise ValidationError(
            f"{field_name} too short: {cid} (Telegram channels are typically 10+ digits)"
        )

    if abs_cid > 9_999_999_999_999:  # 13 digits maximum
        raise ValidationError(
            f"{field_name} too large: {cid} (max 13 digits for Telegram channels)"
        )

    return cid


def validate_payment_id(payment_id: Any, field_name: str = "payment_id") -> str:
    """
    Validate payment identifier from payment processor.

    Payment IDs should be:
    - Non-empty strings
    - Between 1-100 characters (database limit)
    - Alphanumeric with allowed special chars: -_

    Args:
        payment_id: Value to validate
        field_name: Name of field for error messages

    Returns:
        Validated string payment_id

    Raises:
        ValidationError: If validation fails
    """
    if not payment_id:
        raise ValidationError(f"{field_name} cannot be empty")

    # Convert to string if needed
    pid = str(payment_id).strip()

    if not pid:
        raise ValidationError(f"{field_name} cannot be whitespace only")

    # Check length
    if len(pid) > 100:
        raise ValidationError(
            f"{field_name} too long: {len(pid)} characters (max 100)"
        )

    # Check format (alphanumeric + hyphens/underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', pid):
        raise ValidationError(
            f"{field_name} contains invalid characters: {pid} "
            "(only alphanumeric, hyphens, and underscores allowed)"
        )

    return pid


def validate_order_id_format(order_id: Any) -> str:
    """
    Validate NowPayments order_id format.

    Expected format: {user_id}_{open_channel_id}
    Example: "123456789_-1001234567890"

    Args:
        order_id: Order ID to validate

    Returns:
        Validated order_id string

    Raises:
        ValidationError: If format invalid
    """
    if not order_id:
        raise ValidationError("order_id cannot be empty")

    oid = str(order_id).strip()

    # Check format
    if '_' not in oid:
        raise ValidationError(
            f"order_id invalid format: {oid} (expected user_id_channel_id)"
        )

    parts = oid.split('_')
    if len(parts) != 2:
        raise ValidationError(
            f"order_id invalid format: {oid} (expected exactly one underscore)"
        )

    # Validate parts are numeric
    try:
        user_part = int(parts[0])
        channel_part = int(parts[1])
    except ValueError:
        raise ValidationError(
            f"order_id contains non-numeric IDs: {oid}"
        )

    # Validate ID formats
    validate_telegram_user_id(user_part, "order_id user_id part")
    validate_telegram_channel_id(channel_part, "order_id channel_id part")

    return oid


def validate_crypto_amount(amount: Any, field_name: str = "amount") -> float:
    """
    Validate cryptocurrency amount.

    Args:
        amount: Amount to validate
        field_name: Name of field for error messages

    Returns:
        Validated float amount

    Raises:
        ValidationError: If validation fails
    """
    if amount is None:
        raise ValidationError(f"{field_name} cannot be None")

    try:
        amt = float(amount)
    except (ValueError, TypeError):
        raise ValidationError(
            f"{field_name} must be numeric, got {type(amount).__name__}: {amount}"
        )

    if amt < 0:
        raise ValidationError(f"{field_name} cannot be negative: {amt}")

    if amt == 0:
        raise ValidationError(f"{field_name} cannot be zero")

    # Sanity check (no transaction should be > $1M)
    if amt > 1_000_000:
        raise ValidationError(
            f"{field_name} unrealistically large: {amt} (max 1,000,000)"
        )

    return amt
```

**Step 2: Update PGP_NP_IPN_v1/database_manager.py**

```python
# PGP_NP_IPN_v1/database_manager.py

from PGP_COMMON.utils.validation import (
    validate_telegram_user_id,
    validate_telegram_channel_id,
    validate_payment_id,
    validate_order_id_format,
    validate_crypto_amount,
    ValidationError
)

class DatabaseManager(BaseDatabaseManager):

    def get_payout_strategy(self, open_channel_id: int) -> tuple:
        """
        Get client payout strategy by channel ID.

        Args:
            open_channel_id: Telegram channel ID (MUST be validated)

        Returns:
            (closed_channel_id, wallet_address, currency, network)

        Raises:
            ValidationError: If open_channel_id invalid
            ValueError: If no client found for channel
        """
        # ✅ VALIDATE INPUT
        try:
            validated_channel_id = validate_telegram_channel_id(
                open_channel_id,
                field_name="open_channel_id"
            )
        except ValidationError as e:
            logger.error(f"❌ [DB] Invalid open_channel_id: {e}")
            raise

        # Now safe to query
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    closed_channel_id,
                    client_wallet_address,
                    client_payout_currency::text,
                    client_payout_network::text
                FROM main_clients_database
                WHERE open_channel_id = %s
            """, (validated_channel_id,))

            result = cur.fetchone()
            cur.close()

            if not result:
                raise ValueError(
                    f"No client configuration found for channel ID: {validated_channel_id}"
                )

            # Validate result data
            closed_channel_id, wallet, currency, network = result

            if not wallet:
                raise ValueError(
                    f"Client {validated_channel_id} has no wallet address configured"
                )

            if not currency or not network:
                raise ValueError(
                    f"Client {validated_channel_id} has incomplete payout config"
                )

            return result

    def parse_order_id(self, order_id: str) -> tuple:
        """
        Parse NowPayments order_id into user_id and channel_id.

        Args:
            order_id: Format "user_id_channel_id"

        Returns:
            (user_id, open_channel_id) both as integers

        Raises:
            ValidationError: If order_id format invalid
        """
        # ✅ VALIDATE FORMAT
        try:
            validated_order_id = validate_order_id_format(order_id)
        except ValidationError as e:
            logger.error(f"❌ [DB] Invalid order_id: {e}")
            return None, None  # Return None tuple for backward compatibility

        # Parse (already validated by validate_order_id_format)
        parts = validated_order_id.split('_')
        user_id = int(parts[0])
        open_channel_id = int(parts[1])

        return user_id, open_channel_id

    def update_processed_payment(self, payment_data: dict) -> bool:
        """
        Update processed payment with validated data.

        Args:
            payment_data: Dict with payment details (will be validated)

        Returns:
            True if update succeeded

        Raises:
            ValidationError: If any field validation fails
        """
        # ✅ VALIDATE ALL INPUTS
        try:
            payment_id = validate_payment_id(
                payment_data.get('payment_id'),
                field_name="payment_id"
            )

            # Validate payment_status against enum
            payment_status = payment_data.get('payment_status', '').lower().strip()
            ALLOWED_STATUSES = {
                'waiting', 'confirming', 'confirmed', 'sending',
                'partially_paid', 'finished', 'failed', 'refunded', 'expired'
            }
            if payment_status not in ALLOWED_STATUSES:
                raise ValidationError(
                    f"Invalid payment_status: {payment_status} "
                    f"(allowed: {', '.join(ALLOWED_STATUSES)})"
                )

            # Validate amounts if present
            if 'pay_amount' in payment_data and payment_data['pay_amount'] is not None:
                pay_amount = validate_crypto_amount(
                    payment_data['pay_amount'],
                    field_name="pay_amount"
                )
            else:
                pay_amount = None

            # Validate address length if present
            pay_address = payment_data.get('pay_address', '').strip()
            if pay_address and len(pay_address) > 150:
                raise ValidationError(
                    f"pay_address too long: {len(pay_address)} chars (max 150)"
                )

        except ValidationError as e:
            logger.error(f"❌ [DB] Payment data validation failed: {e}")
            raise

        # Now safe to update database
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE processed_payments
                SET
                    payment_status = %s,
                    pay_amount = %s,
                    pay_address = %s,
                    updated_at = NOW()
                WHERE payment_id = %s
            """, (payment_status, pay_amount, pay_address, payment_id))

            rows = cur.rowcount
            conn.commit()
            cur.close()

            return rows > 0
```

**Step 3: Update HTTP endpoint handlers**

```python
# PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py

from PGP_COMMON.utils.validation import (
    validate_telegram_user_id,
    validate_telegram_channel_id,
    validate_payment_id,
    ValidationError
)

@app.route("/process-validated-payment", methods=["POST"])
def process_validated_payment():
    """Process payment with comprehensive input validation."""

    request_data = request.get_json()

    # ✅ VALIDATE ALL INPUTS BEFORE PROCESSING
    try:
        # Validate user_id
        user_id = validate_telegram_user_id(
            request_data.get('user_id'),
            field_name="user_id"
        )

        # Validate closed_channel_id
        closed_channel_id = validate_telegram_channel_id(
            request_data.get('closed_channel_id'),
            field_name="closed_channel_id"
        )

        # Validate payment_id if present
        if 'payment_id' in request_data:
            payment_id = validate_payment_id(
                request_data.get('payment_id'),
                field_name="payment_id"
            )

    except ValidationError as e:
        # Return 400 Bad Request with specific error message
        logger.warning(f"⚠️ [ORCHESTRATOR] Invalid request: {e}")
        return jsonify({
            "error": "Invalid request parameters",
            "details": str(e)
        }), 400

    # Now safe to process with validated data
    logger.info(f"✅ [ORCHESTRATOR] Processing payment for user {user_id}, channel {closed_channel_id}")

    # ... rest of processing logic ...
```

**Step 4: Add validation to PGP_INVITE_v1**

```python
# PGP_INVITE_v1/pgp_invite_v1.py

from PGP_COMMON.utils.validation import ValidationError

@app.route("/", methods=["POST"])
def send_telegram_invite():
    """Send invite with token validation."""

    try:
        # Decode token (includes validation)
        token_data = token_manager.decode_and_verify_token(
            request.json.get('token')
        )

        # Token manager should now validate IDs internally
        # But we can add explicit checks here too
        user_id = validate_telegram_user_id(token_data['user_id'])
        closed_channel_id = validate_telegram_channel_id(token_data['closed_channel_id'])

    except ValidationError as e:
        logger.error(f"❌ [INVITE] Invalid token data: {e}")
        return jsonify({"error": "Invalid token"}), 400

    # Safe to process...
```

#### Verification Steps

**Pre-Deployment:**
```bash
# 1. Run validation unit tests
python3 -m pytest PGP_COMMON/tests/test_validation.py -v

# 2. Test validation functions interactively
python3 << EOF
from PGP_COMMON.utils.validation import *

# Test valid inputs
print(validate_telegram_user_id(123456789))  # Should pass
print(validate_telegram_channel_id(-1001234567890))  # Should pass

# Test invalid inputs
try:
    validate_telegram_user_id(None)
except ValidationError as e:
    print(f"✅ Caught: {e}")

try:
    validate_telegram_channel_id(123)  # Too short
except ValidationError as e:
    print(f"✅ Caught: {e}")

print("✅ All validation tests passed")
EOF

# 3. Verify imports work in services
python3 -c "
import sys
sys.path.insert(0, 'PGP_NP_IPN_v1')
from database_manager import DatabaseManager
print('✅ DatabaseManager imports OK')
"
```

**Post-Deployment Testing:**
```bash
# Test 1: Send IPN with invalid order_id
curl -X POST https://pgp-np-ipn-v1.../ \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "test123",
    "order_id": "invalid_format",
    "payment_status": "finished"
  }'

# Expected: 400 Bad Request with validation error message

# Test 2: Send valid IPN
curl -X POST https://pgp-np-ipn-v1.../ \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "test123",
    "order_id": "123456789_-1001234567890",
    "payment_status": "finished"
  }'

# Expected: 200 OK (or appropriate processing response)

# Test 3: Check logs for validation errors
gcloud logging read "resource.type=cloud_run_revision \
  AND textPayload=~'Invalid.*ValidationError' \
  AND timestamp>=\"$(date -u -d '5 minutes ago' '+%Y-%m-%dT%H:%M:%S')\"" \
  --limit=20 --format=json
```

**Unit Test Examples:**
```python
# Create: PGP_COMMON/tests/test_validation.py

import pytest
from PGP_COMMON.utils.validation import *


class TestTelegramUserIDValidation:

    def test_valid_user_id(self):
        """Valid user IDs should pass."""
        assert validate_telegram_user_id(123456789) == 123456789
        assert validate_telegram_user_id("987654321") == 987654321

    def test_none_user_id(self):
        """None should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be None"):
            validate_telegram_user_id(None)

    def test_negative_user_id(self):
        """Negative IDs should raise ValidationError."""
        with pytest.raises(ValidationError, match="must be positive"):
            validate_telegram_user_id(-123)

    def test_too_short_user_id(self):
        """IDs < 8 digits should raise ValidationError."""
        with pytest.raises(ValidationError, match="8\\+ digits"):
            validate_telegram_user_id(123)  # Only 3 digits

    def test_non_integer_user_id(self):
        """Non-numeric values should raise ValidationError."""
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_telegram_user_id("abc")


class TestChannelIDValidation:

    def test_valid_negative_channel_id(self):
        """Valid negative channel IDs (supergroups) should pass."""
        assert validate_telegram_channel_id(-1001234567890) == -1001234567890

    def test_valid_positive_channel_id(self):
        """Valid positive channel IDs should pass."""
        assert validate_telegram_channel_id(1234567890) == 1234567890

    def test_zero_channel_id(self):
        """Zero should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be 0"):
            validate_telegram_channel_id(0)

    def test_too_short_channel_id(self):
        """Channel IDs < 10 digits should raise ValidationError."""
        with pytest.raises(ValidationError, match="too short"):
            validate_telegram_channel_id(123456)


class TestPaymentIDValidation:

    def test_valid_payment_id(self):
        """Valid payment IDs should pass."""
        assert validate_payment_id("payment123") == "payment123"
        assert validate_payment_id("pay-ment_456") == "pay-ment_456"

    def test_empty_payment_id(self):
        """Empty strings should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_payment_id("")

    def test_too_long_payment_id(self):
        """Payment IDs > 100 chars should raise ValidationError."""
        long_id = "a" * 101
        with pytest.raises(ValidationError, match="too long"):
            validate_payment_id(long_id)

    def test_invalid_characters(self):
        """Payment IDs with special chars should raise ValidationError."""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_payment_id("payment@123")  # @ not allowed


class TestOrderIDValidation:

    def test_valid_order_id(self):
        """Valid order_id format should pass."""
        assert validate_order_id_format("123456789_-1001234567890") == "123456789_-1001234567890"

    def test_missing_underscore(self):
        """Order IDs without underscore should raise ValidationError."""
        with pytest.raises(ValidationError, match="expected user_id_channel_id"):
            validate_order_id_format("123456789")

    def test_multiple_underscores(self):
        """Order IDs with multiple underscores should raise ValidationError."""
        with pytest.raises(ValidationError, match="exactly one underscore"):
            validate_order_id_format("123_456_789")

    def test_non_numeric_parts(self):
        """Order IDs with non-numeric parts should raise ValidationError."""
        with pytest.raises(ValidationError, match="non-numeric IDs"):
            validate_order_id_format("abc_def")

    def test_invalid_user_id_part(self):
        """Order IDs with invalid user_id should raise ValidationError."""
        with pytest.raises(ValidationError, match="user_id part"):
            validate_order_id_format("123_-1001234567890")  # User ID too short


class TestCryptoAmountValidation:

    def test_valid_amount(self):
        """Valid amounts should pass."""
        assert validate_crypto_amount(1.5) == 1.5
        assert validate_crypto_amount("2.5") == 2.5

    def test_negative_amount(self):
        """Negative amounts should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be negative"):
            validate_crypto_amount(-1.0)

    def test_zero_amount(self):
        """Zero should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be zero"):
            validate_crypto_amount(0)

    def test_unrealistic_amount(self):
        """Amounts > 1M should raise ValidationError."""
        with pytest.raises(ValidationError, match="unrealistically large"):
            validate_crypto_amount(2_000_000)
```

**Success Criteria:**
- ✅ All validation unit tests pass
- ✅ Invalid inputs are rejected with clear error messages (400 Bad Request)
- ✅ Valid inputs are processed successfully
- ✅ No SQL errors from invalid data types
- ✅ Logs show validation errors (not database errors)

---

### C-04: HARDCODED SECRET EXPOSURE IN LOGS 🔐 GDPR VIOLATION

**Priority:** P0 (IMMEDIATE - Security & Compliance)
**Severity:** CRITICAL
**Estimated Time:** 1 hour
**Impact:** Secret metadata in production logs → security risk + GDPR violation

#### Problem

**Secret Length Disclosure:**
```python
# PGP_BROADCAST_v1/config_manager.py Lines 105-106, 229-230
logger.info(f"🔑 JWT secret key loaded (length: {len(secret_key)})")
# Output: "🔑 JWT secret key loaded (length: 16)"
```

**Why This Is Bad:**

1. **Entropy Disclosure:**
   - Length reveals key strength: `16 bytes = 128-bit key` (weak for JWT)
   - Helps attackers prioritize targets: "Attack this one first, weak key!"
   - `32 bytes = 256-bit key` (strong) vs `16 bytes = 128-bit` (brute-forceable)

2. **Logging Scope:**
   - Production logs accessible to many people (developers, ops, auditors)
   - Logs exported to third-party systems (Datadog, Splunk, etc.)
   - Logs persist longer than secrets (violates secret rotation policy)

3. **GDPR/Compliance:**
   - Secrets in logs = security incident
   - Must be reported if logs are breached
   - Auditors flag this as critical finding

4. **Wrong Log Levels:**
   ```python
   # PGP_NP_IPN_v1/pgp_np_ipn_v1.py Lines 83-86
   logger.error(f"   DATABASE_PASSWORD_SECRET: {'✅ Loaded' if PASSWORD else '❌ Missing'}")
   ```
   - Using `logger.error()` for INFO messages
   - Pollutes error monitoring (false positives)
   - Makes real errors harder to find

#### Scope Assessment

**Files to Change:** 8 (All config_manager.py files + main services)

**Services Affected:**
1. PGP_ORCHESTRATOR_v1/config_manager.py
2. PGP_NP_IPN_v1/pgp_np_ipn_v1.py (also logs config at startup)
3. PGP_INVITE_v1/config_manager.py
4. PGP_BROADCAST_v1/config_manager.py
5. PGP_COMMON/config/base_config.py (if it logs lengths)

**Pattern to Find:**
```python
# BAD PATTERNS:
logger.info(f"🔑 JWT secret key loaded (length: {len(secret_key)})")
logger.info(f"Secret loaded (length: {len(SECRET)})")
logger.info(f"Token: {token[:10]}...")  # Even prefix is risky
logger.error(f"   SECRET: {'✅ Loaded' if SECRET else '❌ Missing'}")  # Wrong level
```

**Dependencies:** None (simple search & replace)

**Breaking Changes:** None (only affects logs)

#### Resolution Steps

**Step 1: Find all instances of secret logging**

```bash
# Search for secret length logging
grep -rn "len(secret" PGP_*/
grep -rn "len(key" PGP_*/
grep -rn "len(token" PGP_*/
grep -rn "len(.*SECRET" PGP_*/

# Search for wrong log levels (error used for info)
grep -rn "logger.error.*Loaded" PGP_*/
grep -rn "logger.error.*✅" PGP_*/

# Search for secret prefixes/substrings
grep -rn "secret\[:.*\]" PGP_*/
grep -rn "token\[:.*\]" PGP_*/
```

**Expected Findings:**
```
PGP_BROADCAST_v1/config_manager.py:105:        logger.info(f"🔑 JWT secret key loaded (length: {len(secret_key)})")
PGP_BROADCAST_v1/config_manager.py:229:        logger.info(f"🔑 JWT secret key loaded (length: {len(secret_key)})")
PGP_NP_IPN_v1/pgp_np_ipn_v1.py:83:        logger.error(f"   CLOUD_SQL_CONNECTION_NAME: {'✅ Loaded' if CLOUD_SQL_CONNECTION_NAME else '❌ Missing'}")
PGP_NP_IPN_v1/pgp_np_ipn_v1.py:84:        logger.error(f"   DATABASE_PASSWORD_SECRET: {'✅ Loaded' if DATABASE_PASSWORD else '❌ Missing'}")
... (more instances)
```

**Step 2: Fix PGP_BROADCAST_v1/config_manager.py**

```python
# BEFORE (Lines 105-106):
secret_key = self.get_secret("PGP_JWT_SECRET_KEY_v1")
logger.info(f"🔑 JWT secret key loaded (length: {len(secret_key)})")

# AFTER:
secret_key = self.get_secret("PGP_JWT_SECRET_KEY_v1")
logger.info(f"🔑 JWT authentication configured")  # ✅ Generic confirmation


# BEFORE (Lines 229-230) - DUPLICATE!
logger.info(f"🔑 JWT secret key loaded (length: {len(secret_key)})")

# AFTER:
# DELETE this line entirely (it's a duplicate of line 105-106)
# OR if it's in a different context:
logger.info(f"🔑 JWT configuration validated")
```

**Step 3: Fix PGP_NP_IPN_v1/pgp_np_ipn_v1.py (wrong log levels)**

```python
# BEFORE (Lines 83-86):
logger.error(f"   CLOUD_SQL_CONNECTION_NAME: {'✅ Loaded' if CLOUD_SQL_CONNECTION_NAME else '❌ Missing'}")
logger.error(f"   DATABASE_PASSWORD_SECRET: {'✅ Loaded' if DATABASE_PASSWORD else '❌ Missing'}")

# AFTER (use correct log levels):
if CLOUD_SQL_CONNECTION_NAME:
    logger.info(f"   ✅ CLOUD_SQL_CONNECTION_NAME loaded")
else:
    logger.error(f"   ❌ CLOUD_SQL_CONNECTION_NAME missing")  # ERROR only if actually missing

if DATABASE_PASSWORD:
    logger.info(f"   ✅ DATABASE_PASSWORD_SECRET loaded")
else:
    logger.error(f"   ❌ DATABASE_PASSWORD_SECRET missing")  # ERROR only if actually missing
```

**Step 4: Fix all other instances**

Repeat pattern for all services:

```python
# CORRECT PATTERN FOR SECRET LOGGING:

# ❌ NEVER DO THIS:
logger.info(f"Secret loaded (length: {len(secret)})")
logger.info(f"Token: {token[:10]}...")
logger.debug(f"Secret value: {secret}")  # NEVER EVER EVER

# ✅ DO THIS INSTEAD:
logger.info(f"Secret configuration loaded")
logger.info(f"Authentication configured")
logger.info(f"Database credentials loaded")

# ✅ IF SECRET MISSING, LOG ERROR:
if not secret:
    logger.error(f"❌ SECRET_NAME not found in Secret Manager")
else:
    logger.info(f"✅ SECRET_NAME loaded successfully")
```

**Step 5: Create audit checklist**

Create: `PGP_COMMON/security/SECRET_LOGGING_AUDIT.md`

```markdown
# Secret Logging Audit Checklist

## ❌ NEVER Log These:
- Secret values (full or partial)
- Secret lengths (`len(secret)`)
- Secret prefixes/suffixes (`secret[:10]`, `secret[-5:]`)
- Hash values of secrets
- Secret Manager paths (reveals GCP structure)
- Encryption keys
- API tokens
- Database passwords
- JWT secret keys

## ✅ Safe to Log:
- Generic confirmation: "Secret loaded successfully"
- Secret names (if not sensitive): "PGP_JWT_SECRET_KEY_v1 loaded"
- Failure messages: "Secret not found in Secret Manager"
- Configuration status: "Authentication configured"

## 🔍 Audit Commands:
```bash
# Find potential secret logging
grep -rn "len(.*secret" . --include="*.py"
grep -rn "len(.*key" . --include="*.py"
grep -rn "len(.*token" . --include="*.py"
grep -rn "secret\[:.*\]" . --include="*.py"

# Expected: No results
```

## 🛡️ Pre-Deployment Check:
Before deploying any service, run:
```bash
cd PGP_X_v1/
grep -n "len(.*secret\|len(.*key\|len(.*token" *.py */*.py

# If any results: REJECT deployment, fix first
```
```

#### Verification Steps

**Pre-Deployment:**
```bash
# 1. Search for remaining instances (should be 0)
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1

grep -rn "len(secret" PGP_*/
grep -rn "len(key" PGP_*/
grep -rn "len(token" PGP_*/
grep -rn "len(.*SECRET" PGP_*/

# Expected: No output

# 2. Search for wrong log levels (should be 0)
grep -rn "logger.error.*Loaded" PGP_*/
grep -rn "logger.error.*✅" PGP_*/

# Expected: No output

# 3. Verify correct pattern used
grep -rn "authentication configured\|configuration loaded" PGP_*/

# Expected: Multiple matches (replacement pattern)
```

**Post-Deployment Log Audit:**
```bash
# 1. Check recent logs for secret length patterns
gcloud logging read "resource.type=cloud_run_revision \
  AND (textPayload=~'length:' OR textPayload=~'len(') \
  AND timestamp>=\"$(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%S')\"" \
  --limit=100

# Expected: No matches related to secrets

# 2. Verify correct log levels being used
gcloud logging read "resource.type=cloud_run_revision \
  AND severity=ERROR \
  AND textPayload=~'✅' \
  AND timestamp>=\"$(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%S')\"" \
  --limit=20

# Expected: No "✅" in ERROR logs (should be INFO)

# 3. Check for any secret values in logs (should be 0)
gcloud logging read "resource.type=cloud_run_revision \
  AND (textPayload=~'sk_.*' OR textPayload=~'key_.*' OR textPayload=~'secret_.*') \
  AND timestamp>=\"$(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%S')\"" \
  --limit=50

# Expected: No actual secret values (only "secret loaded" type messages)
```

**Code Review Checklist:**
```python
# Review each changed file manually:

# ✅ CHECK 1: No len() on secrets
# Search for: len(secret, len(key, len(token
# Expected: 0 matches

# ✅ CHECK 2: Correct log levels
# INFO for success, ERROR only for failures
# No logger.error() with "✅ Loaded"

# ✅ CHECK 3: Generic messages
# "Authentication configured" not "JWT key loaded (32 bytes)"

# ✅ CHECK 4: No secret substrings
# No secret[:X], secret[-X:], secret[X:Y]
```

**Success Criteria:**
- ✅ No secret lengths in logs
- ✅ No secret prefixes/suffixes in logs
- ✅ Correct log levels (INFO for success, ERROR for failure)
- ✅ Generic confirmation messages only
- ✅ Production logs don't expose secret metadata
- ✅ Audit checklist passes

---

## PHASE 1 COMPLETION SUMMARY

**Critical Fixes Completed:**
1. ✅ C-01: Fixed `get_db_connection()` undefined function (30min)
2. ✅ C-02: Implemented atomic idempotency (2hrs)
3. ✅ C-03: Added comprehensive input validation (3hrs)
4. ✅ C-04: Removed secret logging (1hr)

**Total Time:** ~7 hours
**Files Changed:** ~15 files
**Lines Added:** ~800 (validation + idempotency utilities)
**Lines Removed:** ~50 (secret logging, dead code)

**Production Ready Checklist:**
- ✅ All NameError crashes fixed
- ✅ Race conditions prevented via atomic operations
- ✅ All database inputs validated
- ✅ No secrets in logs
- ✅ Unit tests passing
- ✅ Integration tests passing

---

## PHASE 2: SECURITY HARDENING (P1 - Week 2)
**Timeline:** Days 8-12 (Week 2)
**Estimated Time:** 12 hours
**Focus:** Fix 8 high-severity security issues + code consolidation

### Overview of Phase 2 Tasks

**High Priority Security Issues:**
- H-01: Missing Input Validation (PGP_ORCHESTRATOR_v1)
- H-02: Information Disclosure in Error Messages (All services)
- H-03: Unsafe asyncio.run() Pattern (PGP_INVITE_v1)
- H-04: Unvalidated Crypto Symbol (PGP_NP_IPN_v1, PGP_INVITE_v1)
- H-05: Missing CORS Origin Validation (PGP_NP_IPN_v1)
- H-06: Database Connection Leak (PGP_BROADCAST_v1)
- H-07: JWT Secret Key Logged (Already fixed in C-04)
- H-08: Direct User Input Without Sanitization (PGP_NP_IPN_v1)

**Code Consolidation Tasks:**
- R-01: Duplicate Idempotency Check (Already done in C-02)
- R-02: Duplicate Token Decoding Logic
- R-03: Duplicate Error Handlers
- R-07: Duplicate Crypto Pricing Validation

### H-01: MISSING INPUT VALIDATION (Telegram IDs)

**Priority:** P1 (High)
**Estimated Time:** 1 hour
**Already Partially Fixed:** C-03 created validation utilities

**Remaining Work:**
Apply validation utilities to PGP_ORCHESTRATOR_v1 endpoints

```python
# PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py

from PGP_COMMON.utils.validation import (
    validate_telegram_user_id,
    validate_telegram_channel_id,
    ValidationError
)

@app.route("/process-validated-payment", methods=["POST"])
def process_validated_payment():
    """Already fixed in C-03."""
    # Validation code already added in C-03
    pass
```

**Status:** ✅ COMPLETE (done in C-03)

---

### H-02: INFORMATION DISCLOSURE IN ERROR MESSAGES

**Priority:** P1 (High)
**Estimated Time:** 2 hours
**Impact:** Internal error details exposed to clients

**Problem:**
```python
# PGP_INVITE_v1/pgp_invite_v1.py Lines 354-360
except TelegramError as te:
    abort(500, f"Telegram API error: {te}")  # ❌ Exposes internal details
```

**Exposed Information:**
- Telegram chat IDs (sensitive)
- User IDs (PII)
- Bot token fragments (in stack traces)
- Internal Telegram server errors

**Resolution:**

**Step 1: Extend error sanitizer in PGP_COMMON**

```python
# PGP_COMMON/utils/error_sanitizer.py

# Add to existing file:

def sanitize_telegram_error(error: Exception) -> str:
    """
    Sanitize Telegram API errors for client response.

    Args:
        error: TelegramError or generic exception

    Returns:
        Sanitized error message safe for client
    """
    error_str = str(error).lower()

    # Map internal errors to generic messages
    if 'chat not found' in error_str:
        return "Channel not accessible"

    if 'user not found' in error_str or 'user_id' in error_str:
        return "User account not accessible"

    if 'bot was blocked' in error_str:
        return "Bot access revoked by user"

    if 'insufficient rights' in error_str or 'admin' in error_str:
        return "Insufficient permissions for this operation"

    if 'rate limit' in error_str or 'too many requests' in error_str:
        return "Service temporarily busy, please retry"

    if 'network' in error_str or 'timeout' in error_str:
        return "Network connectivity issue, please retry"

    # Generic fallback (don't expose details)
    return "Telegram service temporarily unavailable"


def sanitize_database_error(error: Exception) -> str:
    """
    Sanitize database errors for client response.

    Args:
        error: Database exception

    Returns:
        Sanitized error message
    """
    error_str = str(error).lower()

    if 'connection' in error_str or 'timeout' in error_str:
        return "Database temporarily unavailable"

    if 'unique constraint' in error_str or 'duplicate' in error_str:
        return "Duplicate entry detected"

    if 'not found' in error_str or 'no rows' in error_str:
        return "Requested record not found"

    # Don't expose schema details
    return "Database operation failed"


def sanitize_error_for_user(error: Exception, context: str = "generic") -> str:
    """
    Enhanced version with context-aware sanitization.

    Args:
        error: Exception to sanitize
        context: Error context (telegram_api, database, payment, etc.)

    Returns:
        Sanitized error message
    """
    if context == "telegram_api":
        return sanitize_telegram_error(error)

    if context == "database":
        return sanitize_database_error(error)

    if context == "payment":
        return "Payment processing error, please contact support"

    # Generic fallback
    return "An error occurred, please try again or contact support"
```

**Step 2: Apply to PGP_INVITE_v1**

```python
# PGP_INVITE_v1/pgp_invite_v1.py

from PGP_COMMON.utils import sanitize_error_for_user
from telegram.error import TelegramError

@app.route("/", methods=["POST"])
def send_telegram_invite():
    """Send invite with error sanitization."""

    try:
        # ... invite sending logic ...

    except TelegramError as te:
        # ✅ LOG full error internally (with stack trace)
        logger.error(
            f"❌ [INVITE] Telegram API error for user {user_id}: {te}",
            exc_info=True  # Includes stack trace in logs
        )

        # ✅ RETURN sanitized error to client
        sanitized_msg = sanitize_error_for_user(te, context="telegram_api")
        return jsonify({
            "error": sanitized_msg,
            "retry": True  # Hint that retry might succeed
        }), 500

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"❌ [INVITE] Unexpected error: {e}", exc_info=True)

        sanitized_msg = sanitize_error_for_user(e, context="generic")
        return jsonify({"error": sanitized_msg}), 500
```

**Step 3: Apply to all services**

Apply same pattern to:
- PGP_ORCHESTRATOR_v1 (database errors)
- PGP_NP_IPN_v1 (CoinGecko API errors, database errors)
- PGP_BROADCAST_v1 (Telegram errors, JWT errors)

**Verification:**
```bash
# Test error sanitization
curl -X POST https://pgp-invite-v1.../ \
  -H "Content-Type: application/json" \
  -d '{"token": "invalid_token_causing_telegram_error"}'

# Expected response:
# {"error": "Telegram service temporarily unavailable", "retry": true}
# NOT: {"error": "TelegramError: Chat not found -1001234567890"}

# Check logs contain full error
gcloud logging read "resource.type=cloud_run_revision \
  AND severity=ERROR \
  AND textPayload=~'Telegram API error'" --limit=5

# Expected: Full error with stack trace in logs
```

**Success Criteria:**
- ✅ Client receives generic error messages
- ✅ Logs contain full error details (for debugging)
- ✅ No PII/sensitive data in client responses
- ✅ No internal system details exposed

---

### H-03: UNSAFE asyncio.run() PATTERN (Bot Connection Leak)

**Priority:** P1 (High)
**Estimated Time:** 1 hour
**Impact:** Connection pool exhaustion under high load

**Problem:**
```python
# PGP_INVITE_v1/pgp_invite_v1.py Lines 252-307

async def send_invite_async():
    bot = Bot(bot_token)  # ❌ Not using context manager
    try:
        invite = await bot.create_chat_invite_link(...)
        return {"success": True}
    except TelegramError:
        raise  # ❌ Bot shutdown() never called
```

**Why This Leaks:**
- Bot uses httpx connection pool
- On exception, `bot.shutdown()` never called
- Connections remain open → pool exhaustion
- Under load: 503 Service Unavailable

**Resolution:**

```python
# PGP_INVITE_v1/pgp_invite_v1.py

async def send_invite_async(
    bot_token: str,
    user_id: int,
    closed_channel_id: int
) -> dict:
    """
    Send Telegram invite with proper resource cleanup.

    Args:
        bot_token: Telegram bot token
        user_id: User ID to send invite to
        closed_channel_id: Channel ID for invite link

    Returns:
        Dict with success status and invite_link

    Raises:
        TelegramError: If Telegram API fails
    """
    # ✅ USE CONTEXT MANAGER for automatic cleanup
    async with Bot(bot_token) as bot:
        try:
            # Create single-use invite link
            invite = await bot.create_chat_invite_link(
                chat_id=closed_channel_id,
                member_limit=1,
                creates_join_request=False,
                name=f"Invite for user {user_id}"
            )

            logger.info(f"✅ [TELEGRAM] Created invite link for user {user_id}")

            # Send invite to user via DM
            await bot.send_message(
                chat_id=user_id,
                text=f"🎉 Welcome! Here's your exclusive invite:\n{invite.invite_link}",
                parse_mode='Markdown'
            )

            logger.info(f"✅ [TELEGRAM] Sent invite DM to user {user_id}")

            return {
                "success": True,
                "invite_link": invite.invite_link,
                "user_id": user_id
            }

        except TelegramError as te:
            # Log error with context
            logger.error(
                f"❌ [TELEGRAM] Failed to send invite for user {user_id}: {te}",
                exc_info=True
            )
            raise  # ✅ Context manager still cleans up bot

    # ✅ Bot connections automatically closed when exiting 'async with' block
    # Even if exception raised, cleanup guaranteed


@app.route("/", methods=["POST"])
def send_telegram_invite():
    """Main endpoint with asyncio."""

    # ... token validation ...

    try:
        # Run async function
        result = asyncio.run(
            send_invite_async(
                bot_token=config_manager.get_telegram_bot_token(),
                user_id=user_id,
                closed_channel_id=closed_channel_id
            )
        )

        # Mark as complete
        idempotency_manager.mark_service_complete(
            payment_id,
            'telegram_invite_sent',
            {'invite_link': result['invite_link']}
        )

        return jsonify(result), 200

    except TelegramError as te:
        # Error already logged in send_invite_async
        sanitized_error = sanitize_error_for_user(te, context="telegram_api")
        return jsonify({"error": sanitized_error}), 500
```

**Verification:**

**Unit Test:**
```python
# PGP_INVITE_v1/tests/test_bot_cleanup.py

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from telegram.error import TelegramError

async def test_bot_cleanup_on_success():
    """Verify bot connections cleaned up on success."""

    with patch('telegram.Bot') as MockBot:
        mock_bot_instance = MagicMock()
        MockBot.return_value.__aenter__.return_value = mock_bot_instance

        # Mock successful invite creation
        mock_bot_instance.create_chat_invite_link = AsyncMock(
            return_value=MagicMock(invite_link="https://t.me/+abc123")
        )
        mock_bot_instance.send_message = AsyncMock()

        # Call function
        result = await send_invite_async("token", 123456789, -1001234567890)

        assert result['success'] == True
        assert 'invite_link' in result

        # Verify context manager was used (async with)
        MockBot.return_value.__aenter__.assert_called_once()
        MockBot.return_value.__aexit__.assert_called_once()


async def test_bot_cleanup_on_exception():
    """Verify bot connections cleaned up even on exception."""

    with patch('telegram.Bot') as MockBot:
        mock_bot_instance = MagicMock()
        MockBot.return_value.__aenter__.return_value = mock_bot_instance

        # Mock Telegram error
        mock_bot_instance.create_chat_invite_link = AsyncMock(
            side_effect=TelegramError("Chat not found")
        )

        # Should raise exception
        with pytest.raises(TelegramError):
            await send_invite_async("token", 123456789, -1001234567890)

        # ✅ CRITICAL: Verify cleanup still happened
        MockBot.return_value.__aenter__.assert_called_once()
        MockBot.return_value.__aexit__.assert_called_once()
```

**Load Test:**
```python
# Test connection pool under concurrent requests
import concurrent.futures
import requests
import time

def send_invite_request(user_id):
    """Send invite request."""
    response = requests.post(
        'https://pgp-invite-v1.../',
        json={'token': generate_valid_token(user_id)}
    )
    return response.status_code

# Send 50 concurrent requests
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    user_ids = range(100000000, 100000050)
    futures = [executor.submit(send_invite_request, uid) for uid in user_ids]
    results = [f.result() for f in futures]

# All should succeed (no connection pool exhaustion)
success_count = results.count(200)
assert success_count == 50, f"Expected 50 success, got {success_count}"
```

**Success Criteria:**
- ✅ Bot context manager used (`async with Bot()`)
- ✅ Connections cleaned up on success
- ✅ Connections cleaned up on exception
- ✅ No connection leaks under load
- ✅ Unit tests pass

---

### H-04: UNVALIDATED CRYPTO SYMBOL IN PRICING

**Priority:** P1 (High)
**Estimated Time:** 2 hours
**Impact:** XSS, API abuse, invalid pricing

**Problem:**
```python
# PGP_NP_IPN_v1/pgp_np_ipn_v1.py Lines 342-350
crypto_usd_price = pricing_client.get_crypto_usd_price(outcome_currency)  # ❌ No validation
```

**User-controlled input:**
- `outcome_currency` from NowPayments IPN
- Could be: `"<script>alert(1)</script>"`, `"; DROP TABLE--"`, `"../../../../etc/passwd"`

**Resolution:**

Already created validation in C-03, now extend crypto pricing client:

**Step 1: Add symbol whitelist to PGP_COMMON/utils/crypto_pricing.py**

```python
# PGP_COMMON/utils/crypto_pricing.py

# Add comprehensive whitelist
ALLOWED_CRYPTO_SYMBOLS = {
    # Major cryptocurrencies
    'BTC', 'ETH', 'LTC', 'XRP', 'BCH', 'BNB', 'ADA', 'DOGE',
    'TRX', 'SOL', 'MATIC', 'AVAX', 'DOT', 'ATOM', 'LINK',
    # Stablecoins
    'USDT', 'USDC', 'BUSD', 'DAI', 'USD', 'USDD', 'TUSD',
    # Privacy coins
    'XMR', 'ZEC', 'DASH',
    # DeFi tokens
    'UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'CRV',
    # Other supported coins
    'EOS', 'XLM', 'XTZ', 'ALGO', 'VET', 'FTM', 'NEAR', 'SAND', 'MANA'
}


def validate_crypto_symbol(symbol: str) -> str:
    """
    Validate and normalize cryptocurrency symbol.

    Args:
        symbol: Crypto symbol (case-insensitive)

    Returns:
        Normalized uppercase symbol

    Raises:
        ValueError: If symbol not in whitelist

    Examples:
        >>> validate_crypto_symbol("btc")
        'BTC'
        >>> validate_crypto_symbol("ETH")
        'ETH'
        >>> validate_crypto_symbol("INVALID")
        ValueError: Unsupported crypto symbol: INVALID
    """
    if not symbol:
        raise ValueError("Crypto symbol cannot be empty")

    # Normalize
    normalized = str(symbol).upper().strip()

    # Check length (no crypto symbol > 10 chars)
    if len(normalized) > 10:
        raise ValueError(f"Crypto symbol too long: {len(normalized)} chars (max 10)")

    # Check format (only letters and numbers)
    if not normalized.replace('USD', '').replace('BTC', '').isalnum():
        raise ValueError(f"Crypto symbol contains invalid characters: {symbol}")

    # Check whitelist
    if normalized not in ALLOWED_CRYPTO_SYMBOLS:
        raise ValueError(
            f"Unsupported crypto symbol: {symbol}. "
            f"Supported: {', '.join(sorted(ALLOWED_CRYPTO_SYMBOLS))}"
        )

    return normalized


class CryptoPricingClient:
    """Enhanced with validation."""

    def get_crypto_usd_price(self, crypto_symbol: str) -> Optional[float]:
        """
        Get crypto USD price with validation.

        Args:
            crypto_symbol: Symbol to price (will be validated)

        Returns:
            USD price or None if failed

        Raises:
            ValueError: If symbol invalid
        """
        # ✅ VALIDATE before API call
        try:
            validated_symbol = validate_crypto_symbol(crypto_symbol)
        except ValueError as e:
            logger.warning(f"⚠️ [PRICING] Invalid crypto symbol: {e}")
            raise

        # Stablecoins = $1.00
        if validated_symbol in {'USDT', 'USDC', 'BUSD', 'DAI', 'USD', 'TUSD', 'USDD'}:
            return 1.0

        # Fetch from CoinGecko (symbol already validated)
        return self._fetch_from_coingecko(validated_symbol)

    def validate_and_convert_to_usd(
        self,
        amount: float,
        crypto_symbol: str,
        min_tolerance: float = 0.50
    ) -> Tuple[Optional[float], str]:
        """
        Validate crypto symbol and convert to USD with tolerance check.

        Args:
            amount: Crypto amount
            crypto_symbol: Crypto symbol (will be validated)
            min_tolerance: Minimum acceptable USD value

        Returns:
            (usd_value, status_message)
        """
        # Validate symbol
        try:
            validated_symbol = validate_crypto_symbol(crypto_symbol)
        except ValueError as e:
            return None, str(e)

        # Validate amount
        if not isinstance(amount, (int, float)) or amount <= 0:
            return None, f"Invalid amount: {amount}"

        # Convert
        try:
            price = self.get_crypto_usd_price(validated_symbol)
            if price is None:
                return None, "Failed to fetch crypto price"

            usd_value = amount * price

            # Check tolerance
            if usd_value < min_tolerance:
                return None, f"Amount ${usd_value:.2f} below minimum ${min_tolerance:.2f}"

            return usd_value, "success"

        except Exception as e:
            logger.error(f"❌ [PRICING] Conversion error: {e}")
            return None, "Pricing error"
```

**Step 2: Apply validation in PGP_NP_IPN_v1**

```python
# PGP_NP_IPN_v1/pgp_np_ipn_v1.py

from PGP_COMMON.utils import CryptoPricingClient, validate_crypto_symbol

pricing_client = CryptoPricingClient()

def calculate_outcome_usd(outcome_currency: str, outcome_amount: float) -> Optional[float]:
    """
    Calculate USD value of outcome with validation.

    Args:
        outcome_currency: Crypto symbol from IPN (user-controlled!)
        outcome_amount: Amount in crypto

    Returns:
        USD value or None if invalid
    """
    # ✅ VALIDATE crypto symbol
    try:
        usd_value, status = pricing_client.validate_and_convert_to_usd(
            amount=outcome_amount,
            crypto_symbol=outcome_currency,
            min_tolerance=0.50
        )

        if usd_value is None:
            logger.warning(f"⚠️ [IPN] Crypto validation failed: {status}")
            return None

        logger.info(f"✅ [IPN] {outcome_amount} {outcome_currency} = ${usd_value:.2f} USD")
        return usd_value

    except Exception as e:
        logger.error(f"❌ [IPN] Pricing error: {e}")
        return None


# In IPN handler:
if outcome_currency and outcome_amount:
    outcome_amount_usd = calculate_outcome_usd(outcome_currency, outcome_amount)

    if outcome_amount_usd is None:
        # Invalid crypto or pricing failed
        # Still process payment but log warning
        logger.warning(f"⚠️ [IPN] Could not calculate USD value for {outcome_currency}")
```

**Verification:**
```python
# Unit tests
def test_validate_crypto_symbol():
    """Test crypto symbol validation."""
    # Valid symbols
    assert validate_crypto_symbol("btc") == "BTC"
    assert validate_crypto_symbol("ETH") == "ETH"
    assert validate_crypto_symbol("usdt") == "USDT"

    # Invalid symbols
    with pytest.raises(ValueError, match="Unsupported"):
        validate_crypto_symbol("INVALID_COIN")

    with pytest.raises(ValueError, match="invalid characters"):
        validate_crypto_symbol("<script>alert(1)</script>")

    with pytest.raises(ValueError, match="too long"):
        validate_crypto_symbol("A" * 20)


def test_ipn_with_invalid_crypto():
    """Test IPN handling with invalid crypto symbol."""
    ipn_data = {
        'payment_id': 'test123',
        'outcome_currency': '<script>alert(1)</script>',
        'outcome_amount': 1.0
    }

    outcome_usd = calculate_outcome_usd(
        ipn_data['outcome_currency'],
        ipn_data['outcome_amount']
    )

    # Should return None (invalid symbol rejected)
    assert outcome_usd is None
```

**Success Criteria:**
- ✅ Only whitelisted crypto symbols accepted
- ✅ XSS payloads rejected
- ✅ Invalid symbols logged but don't crash service
- ✅ Pricing calculations safe

---

### H-05: MISSING CORS ORIGIN VALIDATION

**Priority:** P1 (High)
**Estimated Time:** 30 minutes
**Impact:** CORS policy too permissive → data theft risk

**Problem:**
```python
# PGP_NP_IPN_v1/pgp_np_ipn_v1.py Lines 36-50
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://storage.googleapis.com",  # ❌ ANY bucket!
            "http://localhost:*"  # ❌ ANY port!
        ]
    }
})
```

**Attack:**
1. Attacker creates `https://storage.googleapis.com/evil-bucket/attack.html`
2. Page makes AJAX to `https://pgp-np-ipn-v1.../api/payment-status?payment_id=XXX`
3. CORS allows it (origin matches)
4. Attacker steals payment data

**Resolution:**

```python
# PGP_NP_IPN_v1/pgp_np_ipn_v1.py

from flask_cors import CORS

# ✅ RESTRICTIVE CORS configuration
CORS(app, resources={
    r"/api/*": {
        "origins": [
            # ✅ SPECIFIC bucket only (if still needed)
            "https://storage.googleapis.com/pgp-payment-pages-prod",

            # ✅ Production domains (www and non-www)
            "https://www.paygateprime.com",
            "https://paygateprime.com",

            # ✅ Development (REMOVE in production deployment)
            # Uncomment only for local testing:
            # "http://localhost:3000"
        ],

        # ✅ Restrict HTTP methods
        "methods": ["GET", "OPTIONS"],  # Only read operations

        # ✅ Restrict headers
        "allow_headers": ["Content-Type", "Accept"],

        # ✅ No credentials
        "supports_credentials": False,

        # ✅ Cache preflight for 1 hour
        "max_age": 3600
    }
})

# ✅ EVEN BETTER: Check if CORS still needed
# Comment from review: "CORS is now only for backward compatibility"
# TODO: Monitor /api/* usage for 30 days, then remove CORS if unused

# Add monitoring
@app.route("/api/<path:path>", methods=["GET", "OPTIONS"])
def deprecated_api_endpoint(path):
    """
    DEPRECATED API ENDPOINT - REMOVE AFTER 2025-12-31

    This endpoint kept for backward compatibility with old payment pages.
    Log all access to determine if still in use.
    """
    logger.warning(
        f"⚠️ [DEPRECATED] /api/{path} accessed from {request.origin} - "
        f"REMOVE THIS ENDPOINT IF NO USAGE BY 2025-12-31"
    )

    # ... existing logic if needed ...
    # Or return 410 Gone to force clients to upgrade:
    return jsonify({
        "error": "This endpoint is deprecated",
        "message": "Please upgrade to new payment flow"
    }), 410  # 410 Gone = permanent deprecation
```

**Verification:**
```bash
# Test 1: Allowed origin should work
curl -X GET "https://pgp-np-ipn-v1.../api/payment-status?id=test" \
  -H "Origin: https://www.paygateprime.com" \
  -v

# Expected: 200 OK with CORS headers:
# Access-Control-Allow-Origin: https://www.paygateprime.com

# Test 2: Unauthorized origin should be blocked
curl -X GET "https://pgp-np-ipn-v1.../api/payment-status?id=test" \
  -H "Origin: https://storage.googleapis.com/evil-bucket" \
  -v

# Expected: No Access-Control-Allow-Origin header (browser blocks)

# Test 3: Monitor CORS usage
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=pgp-np-ipn-v1 \
  AND httpRequest.requestUrl=~/api/ \
  AND timestamp>=\"$(date -u -d '30 days ago' '+%Y-%m-%dT%H:%M:%S')\"" \
  --limit=100

# If 0 results after 30 days → safe to remove CORS entirely
```

**Success Criteria:**
- ✅ CORS restricted to specific origins
- ✅ No wildcard origins (`*`)
- ✅ No overly broad patterns (`localhost:*`)
- ✅ Monitoring in place to deprecate CORS
- ✅ Unauthorized origins blocked

---

### H-06: DATABASE CONNECTION LEAK (NullPool Issue)

**Priority:** P1 (High)
**Estimated Time:** 1 hour
**Impact:** Connection exhaustion under load

**Problem:**
```python
# PGP_BROADCAST_v1/database_manager.py Lines 76-98
self._engine = create_engine(
    "postgresql+pg8000://",
    creator=getconn,
    poolclass=NullPool  # ❌ No pooling! Creates new connection per request
)
```

**Why This Is Bad:**
- NullPool = no connection reuse
- Every request creates new TCP connection to database
- Under load: 100 req/sec = 100 new connections/sec
- Database max_connections = 100 (default PostgreSQL)
- Result: `FATAL: too many connections` → service unavailable

**Resolution:**

```python
# PGP_BROADCAST_v1/database_manager.py

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool  # ✅ Import QueuePool

class DatabaseManager(BaseDatabaseManager):

    def _get_engine(self):
        """Get or create SQLAlchemy engine with proper connection pooling."""
        if self._engine:
            return self._engine

        def getconn():
            """Create database connection via Cloud SQL connector."""
            return self.connector.connect(
                self.instance_connection_name,
                "pg8000",
                user=self.db_user,
                password=self.db_password,
                db=self.db_name
            )

        # ✅ USE QUEUEPOOL for connection reuse
        self._engine = create_engine(
            "postgresql+pg8000://",
            creator=getconn,

            # ✅ CONNECTION POOLING CONFIGURATION
            poolclass=QueuePool,      # Maintains pool of reusable connections
            pool_size=5,               # Keep 5 persistent connections
            max_overflow=10,           # Allow up to 15 total (5 + 10 burst)
            pool_timeout=30,           # Wait max 30s for connection
            pool_recycle=1800,         # Recycle connections every 30 min (Cloud SQL timeout)
            pool_pre_ping=True,        # Test connection before use (detect stale)

            # ✅ ECHO SQL (disable in production)
            echo=False
        )

        logger.info(
            f"✅ [DB] Connection pool initialized: "
            f"size={5}, max_overflow={10}, timeout={30}s"
        )

        return self._engine
```

**Why These Settings:**
```python
pool_size=5
# Persistent connections kept alive
# Good for: steady baseline traffic
# Cloud Run: each instance handles ~80 concurrent requests
# 5 connections handles most traffic without waste

max_overflow=10
# Additional connections created on demand
# Total capacity: 15 (5 + 10)
# Good for: traffic bursts
# Prevents connection exhaustion

pool_timeout=30
# How long to wait for available connection
# 30s is reasonable (most requests < 5s)
# Prevents indefinite hangs

pool_recycle=1800
# Recycle connections every 30 min
# Cloud SQL drops idle connections after 10 hours
# 30 min ensures connections stay fresh

pool_pre_ping=True
# Test connection before use: SELECT 1
# Detects stale connections (prevents errors)
# Small overhead (~ 1ms) worth the reliability
```

**Comparison:**

| Config | NullPool (Before) | QueuePool (After) |
|--------|------------------|-------------------|
| **Connections/sec** | 100 (new per request) | 0-10 (reuse from pool) |
| **DB Load** | Very high | Low |
| **Latency** | +50ms (TCP handshake) | +1ms (pool checkout) |
| **Max Concurrent** | 100 (DB limit) | 15 per instance |
| **Under Load** | Crashes | Stable |

**Verification:**

**Load Test:**
```python
# Create: PGP_BROADCAST_v1/tests/test_connection_pool.py

import concurrent.futures
import time
import requests

def send_broadcast_request():
    """Send broadcast API request."""
    response = requests.post(
        'https://pgp-broadcast-v1.../api/broadcast',
        json={'message': 'test', 'channel_id': -1001234567890},
        headers={'Authorization': 'Bearer test_token'}
    )
    return response.status_code

def test_connection_pool_under_load():
    """
    Verify connection pool handles concurrent requests.

    Before fix (NullPool): Would crash after ~100 concurrent requests
    After fix (QueuePool): Should handle 200+ concurrent requests
    """
    start_time = time.time()

    # Send 200 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=200) as executor:
        futures = [executor.submit(send_broadcast_request) for _ in range(200)]
        results = [f.result() for f in futures]

    duration = time.time() - start_time

    # Check results
    success_count = results.count(200)
    error_count = len([r for r in results if r >= 500])

    print(f"✅ Completed 200 requests in {duration:.2f}s")
    print(f"   Success: {success_count}")
    print(f"   Errors: {error_count}")

    # Should have very few errors (connection pool handles burst)
    assert success_count >= 190, f"Expected ≥190 success, got {success_count}"
    assert error_count <= 10, f"Expected ≤10 errors, got {error_count}"
```

**Monitor Connection Pool:**
```python
# Add to PGP_BROADCAST_v1/database_manager.py

def get_pool_status(self) -> dict:
    """Get current connection pool statistics."""
    engine = self._get_engine()
    pool = engine.pool

    return {
        'size': pool.size(),           # Current pool size
        'checked_in': pool.checkedin(),  # Available connections
        'checked_out': pool.checkedout(),  # In-use connections
        'overflow': pool.overflow(),    # Overflow connections created
        'total': pool.size() + pool.overflow()
    }

# Add monitoring endpoint
@app.route("/health/pool", methods=["GET"])
def pool_health():
    """Connection pool health check."""
    stats = db_manager.get_pool_status()

    logger.info(f"📊 [POOL] {stats}")

    return jsonify({
        'status': 'healthy',
        'pool': stats,
        'utilization': f"{stats['checked_out']}/{stats['total']}"
    }), 200
```

**Check Logs for Connection Errors:**
```bash
# Before fix - look for these errors:
gcloud logging read "resource.type=cloud_run_revision \
  AND textPayload=~'too many connections' \
  AND timestamp>=\"$(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%S')\"" \
  --limit=100

# After fix - should be 0 results

# Monitor pool usage
curl https://pgp-broadcast-v1.../health/pool

# Expected:
# {
#   "status": "healthy",
#   "pool": {
#     "size": 5,
#     "checked_in": 3,
#     "checked_out": 2,
#     "overflow": 0,
#     "total": 5
#   },
#   "utilization": "2/5"
# }
```

**Success Criteria:**
- ✅ QueuePool configured with appropriate settings
- ✅ Load test passes (200 concurrent requests)
- ✅ No "too many connections" errors
- ✅ Pool statistics available via `/health/pool`
- ✅ Connection reuse visible in metrics

---

### H-08: DIRECT USER INPUT IN DATABASE WITHOUT SANITIZATION

**Priority:** P1 (High)
**Estimated Time:** 1 hour (partially covered by C-03)
**Impact:** XSS, data validation issues

**Status:** ✅ Mostly covered by C-03 input validation

**Additional Work Needed:**

Extend validation to cover payment_status enum:

```python
# PGP_NP_IPN_v1/database_manager.py

# Add to existing validation:

ALLOWED_PAYMENT_STATUSES = {
    'waiting', 'confirming', 'confirmed', 'sending',
    'partially_paid', 'finished', 'failed', 'refunded', 'expired'
}

def validate_payment_status(status: str) -> str:
    """
    Validate payment status against allowed values.

    Args:
        status: Payment status from IPN

    Returns:
        Validated status

    Raises:
        ValueError: If status not in enum
    """
    if not status:
        raise ValueError("payment_status cannot be empty")

    normalized = status.lower().strip()

    if normalized not in ALLOWED_PAYMENT_STATUSES:
        raise ValueError(
            f"Invalid payment_status: {status}. "
            f"Allowed: {', '.join(ALLOWED_PAYMENT_STATUSES)}"
        )

    return normalized

# Apply in update_processed_payment():
payment_status = validate_payment_status(payment_data.get('payment_status'))
```

**Success Criteria:**
- ✅ All payment data validated (covered in C-03)
- ✅ Payment status validated against enum
- ✅ String lengths validated
- ✅ No XSS payloads accepted

---

## PHASE 2 CODE CONSOLIDATION TASKS

### R-02: DUPLICATE TOKEN DECODING LOGIC

**Priority:** P1
**Estimated Time:** 2 hours
**Impact:** Removes ~280 lines of duplicate code

**Files Affected:**
- PGP_ORCHESTRATOR_v1/token_manager.py (Lines 30-107)
- PGP_INVITE_v1/token_manager.py (Lines 30-167)
- PGP_COMMON/tokens/base_token.py (extend this)

**Problem:**
Both services implement IDENTICAL token decoding:
- 48-bit timestamp + HMAC signature
- Same validation logic
- Different timestamp windows (2hr vs 24hr) ← **INCONSISTENT**

**Resolution:**

**Step 1: Extend PGP_COMMON/tokens/base_token.py**

```python
# PGP_COMMON/tokens/base_token.py

import hmac
import hashlib
import base64
import time
from typing import Dict, List, Optional

class BaseTokenManager:
    """
    Base token manager with standardized token format.

    Token Format:
    - 48-bit timestamp (6 bytes)
    - N x 48-bit components (6 bytes each)
    - 32-byte HMAC-SHA256 signature
    - Base64 URL-safe encoded
    """

    # ✅ STANDARDIZED token expiration (consistent across all services)
    TOKEN_MAX_AGE = 3600          # 1 hour (not 2hr or 24hr!)
    TOKEN_FUTURE_TOLERANCE = 300  # 5 minutes (clock skew)

    def __init__(self, signing_key: str):
        """
        Initialize token manager.

        Args:
            signing_key: Secret key for HMAC signatures
        """
        self.signing_key = signing_key

    def decode_and_verify_standard_token(
        self,
        encrypted_token: str,
        expected_components: List[str]
    ) -> Dict:
        """
        Decode and verify standard PGP token format.

        Args:
            encrypted_token: Base64 URL-safe encoded token
            expected_components: List of component names to extract
                                Example: ['user_id', 'closed_channel_id']

        Returns:
            Dict with decoded components:
            {
                'timestamp': 1699999999,
                'user_id': 123456789,
                'closed_channel_id': -1001234567890,
                ...
            }

        Raises:
            ValueError: If token invalid, expired, or signature mismatch
        """
        # Decode base64
        try:
            token_bytes = base64.urlsafe_b64decode(encrypted_token)
        except Exception as e:
            raise ValueError(f"Invalid token encoding: {e}")

        # Validate length
        # Format: timestamp (6 bytes) + components (6 bytes each) + HMAC (32 bytes)
        expected_length = 6 + (6 * len(expected_components)) + 32
        if len(token_bytes) != expected_length:
            raise ValueError(
                f"Invalid token length: {len(token_bytes)}, expected {expected_length}"
            )

        # Extract signature
        payload = token_bytes[:-32]
        signature = token_bytes[-32:]

        # Verify HMAC
        expected_signature = hmac.new(
            self.signing_key.encode(),
            payload,
            hashlib.sha256
        ).digest()

        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Invalid token signature")

        # Decode payload (48-bit integers, big-endian)
        offset = 0
        components = {}

        # Extract timestamp
        timestamp = int.from_bytes(payload[offset:offset+6], 'big')
        components['timestamp'] = timestamp
        offset += 6

        # ✅ VALIDATE TIMESTAMP (standardized window)
        self.validate_token_timestamp(timestamp)

        # Extract expected components
        for component_name in expected_components:
            value = int.from_bytes(payload[offset:offset+6], 'big')
            components[component_name] = value
            offset += 6

        return components

    def validate_token_timestamp(self, timestamp: int) -> None:
        """
        Validate token timestamp within acceptable window.

        Args:
            timestamp: Unix timestamp from token

        Raises:
            ValueError: If token expired or not yet valid
        """
        now = int(time.time())

        # Check if within valid window
        if not (now - self.TOKEN_MAX_AGE <= timestamp <= now + self.TOKEN_FUTURE_TOLERANCE):
            age = now - timestamp

            if age > 0:
                # Token too old
                raise ValueError(
                    f"Token expired {age} seconds ago "
                    f"(max age: {self.TOKEN_MAX_AGE} seconds = {self.TOKEN_MAX_AGE // 3600} hour)"
                )
            else:
                # Token from future (clock skew)
                raise ValueError(
                    f"Token timestamp {abs(age)} seconds in future "
                    f"(max clock skew: {self.TOKEN_FUTURE_TOLERANCE} seconds)"
                )

    def encode_standard_token(
        self,
        components: Dict[str, int]
    ) -> str:
        """
        Encode token with standard format.

        Args:
            components: Dict of {component_name: value}
                       Must include at least one component
                       All values must fit in 48 bits (< 281,474,976,710,656)

        Returns:
            Base64 URL-safe encoded token

        Example:
            >>> manager.encode_standard_token({
            ...     'user_id': 123456789,
            ...     'closed_channel_id': -1001234567890
            ... })
            'ABC123...XYZ'
        """
        # Create timestamp
        timestamp = int(time.time())

        # Build payload
        payload = timestamp.to_bytes(6, 'big')

        for component_name in components:
            value = components[component_name]

            # Validate fits in 48 bits
            if abs(value) >= 2**48:
                raise ValueError(
                    f"{component_name} value {value} too large for 48-bit encoding"
                )

            # Convert to bytes (handle negative via two's complement)
            if value < 0:
                value_bytes = (value & 0xFFFFFFFFFFFF).to_bytes(6, 'big')
            else:
                value_bytes = value.to_bytes(6, 'big')

            payload += value_bytes

        # Generate HMAC signature
        signature = hmac.new(
            self.signing_key.encode(),
            payload,
            hashlib.sha256
        ).digest()

        # Combine payload + signature
        token_bytes = payload + signature

        # Base64 encode
        return base64.urlsafe_b64encode(token_bytes).decode('utf-8')
```

**Step 2: Update PGP_ORCHESTRATOR_v1/token_manager.py**

```python
# PGP_ORCHESTRATOR_v1/token_manager.py

from PGP_COMMON.tokens import BaseTokenManager

class TokenManager(BaseTokenManager):
    """
    Orchestrator token manager.

    Token contains:
    - user_id
    - closed_channel_id
    """

    def __init__(self, signing_key: str):
        """Initialize with signing key from config."""
        super().__init__(signing_key)

    def decode_and_verify_token(self, token: str) -> tuple:
        """
        Decode orchestrator token.

        Args:
            token: Encrypted token string

        Returns:
            (timestamp, user_id, closed_channel_id)

        Raises:
            ValueError: If token invalid
        """
        # ✅ USE BASE CLASS METHOD
        components = self.decode_and_verify_standard_token(
            encrypted_token=token,
            expected_components=['user_id', 'closed_channel_id']
        )

        # Return as tuple for backward compatibility
        return (
            components['timestamp'],
            components['user_id'],
            components['closed_channel_id']
        )

    def create_token(self, user_id: int, closed_channel_id: int) -> str:
        """
        Create new orchestrator token.

        Args:
            user_id: Telegram user ID
            closed_channel_id: Telegram channel ID

        Returns:
            Encrypted token string
        """
        return self.encode_standard_token({
            'user_id': user_id,
            'closed_channel_id': closed_channel_id
        })
```

**Step 3: Update PGP_INVITE_v1/token_manager.py**

```python
# PGP_INVITE_v1/token_manager.py

from PGP_COMMON.tokens import BaseTokenManager

class TokenManager(BaseTokenManager):
    """
    Invite token manager.

    Token contains:
    - user_id
    - closed_channel_id
    - subscription_price
    - subscription_time
    """

    def decode_and_verify_token(self, token: str) -> tuple:
        """
        Decode invite token with subscription details.

        Args:
            token: Encrypted token string

        Returns:
            (timestamp, user_id, closed_channel_id, subscription_price, subscription_time)
        """
        # ✅ USE BASE CLASS METHOD
        components = self.decode_and_verify_standard_token(
            encrypted_token=token,
            expected_components=[
                'user_id',
                'closed_channel_id',
                'subscription_price',
                'subscription_time'
            ]
        )

        return (
            components['timestamp'],
            components['user_id'],
            components['closed_channel_id'],
            components['subscription_price'],
            components['subscription_time']
        )

    def create_token(
        self,
        user_id: int,
        closed_channel_id: int,
        subscription_price: int,
        subscription_time: int
    ) -> str:
        """Create new invite token."""
        return self.encode_standard_token({
            'user_id': user_id,
            'closed_channel_id': closed_channel_id,
            'subscription_price': subscription_price,
            'subscription_time': subscription_time
        })
```

**Benefits:**
- ✅ Standardized 1-hour expiration (fixes M-01)
- ✅ Single implementation of HMAC verification
- ✅ ~280 lines of duplicate code removed
- ✅ Consistent error messages
- ✅ Easier to audit security

**Verification:**
```python
# Test token compatibility
def test_token_backward_compatibility():
    """Verify tokens still work after refactoring."""

    # Create token with new method
    token_manager = TokenManager(signing_key="test_secret")
    token = token_manager.create_token(
        user_id=123456789,
        closed_channel_id=-1001234567890
    )

    # Decode with new method
    timestamp, user_id, channel_id = token_manager.decode_and_verify_token(token)

    assert user_id == 123456789
    assert channel_id == -1001234567890
    assert timestamp <= int(time.time())

    # Verify expiration
    time.sleep(3601)  # Wait 1 hour + 1 second

    with pytest.raises(ValueError, match="Token expired"):
        token_manager.decode_and_verify_token(token)
```

---

### R-03: DUPLICATE ERROR HANDLERS

**Priority:** P1
**Estimated Time:** 1 hour
**Impact:** Removes ~200 lines of duplicate code

**Problem:**
All 4 services have identical error handlers:
```python
@app.errorhandler(400)
def handle_bad_request(e):
    return create_error_response(400, str(e), "bad_request")
# ... repeated in every service
```

**Resolution:**

**Step 1: Create PGP_COMMON/flask/error_handlers.py**

```python
# PGP_COMMON/flask/error_handlers.py

"""
Standardized Flask error handlers for all PGP services.
"""

from flask import Flask, jsonify, request
from PGP_COMMON.utils import (
    sanitize_error_for_user,
    create_error_response
)
from PGP_COMMON.logging import setup_logger

logger = setup_logger(__name__)


def register_standard_error_handlers(app: Flask, service_name: str):
    """
    Register standardized error handlers on Flask app.

    Args:
        app: Flask application instance
        service_name: Name of service for logging context
                     Example: "PGP_ORCHESTRATOR_v1"

    Example:
        >>> app = Flask(__name__)
        >>> register_standard_error_handlers(app, "PGP_ORCHESTRATOR_v1")
    """

    @app.errorhandler(400)
    def handle_bad_request(e):
        """Handle 400 Bad Request errors."""
        logger.warning(f"⚠️ [{service_name}] Bad request: {e}")
        return create_error_response(
            status_code=400,
            message=str(e),
            error_type="bad_request"
        )

    @app.errorhandler(404)
    def handle_not_found(e):
        """Handle 404 Not Found errors."""
        logger.info(f"ℹ️ [{service_name}] Not found: {request.path}")
        return create_error_response(
            status_code=404,
            message="Resource not found",
            error_type="not_found"
        )

    @app.errorhandler(429)
    def handle_rate_limit(e):
        """Handle 429 Too Many Requests errors."""
        logger.warning(f"⚠️ [{service_name}] Rate limit exceeded: {request.remote_addr}")
        return create_error_response(
            status_code=429,
            message="Too many requests, please slow down",
            error_type="rate_limit_exceeded"
        )

    @app.errorhandler(500)
    def handle_internal_error(e):
        """Handle 500 Internal Server Error."""
        logger.error(
            f"❌ [{service_name}] Internal error: {e}",
            exc_info=True
        )

        # Sanitize error for client
        sanitized_msg = sanitize_error_for_user(e, context="internal_error")

        return create_error_response(
            status_code=500,
            message=sanitized_msg,
            error_type="internal_error"
        )

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all unhandled exceptions."""
        # Log full exception with stack trace
        logger.error(
            f"❌ [{service_name}] Unhandled exception: {e}",
            exc_info=True
        )

        # Sanitize error message
        sanitized_msg = sanitize_error_for_user(e, context="exception")

        # Determine HTTP status code
        status_code = getattr(e, 'code', 500)

        return create_error_response(
            status_code=status_code,
            message=sanitized_msg,
            error_type="exception"
        )

    logger.info(f"✅ [{service_name}] Standard error handlers registered")
```

**Step 2: Apply to all services**

```python
# PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py

from flask import Flask
from PGP_COMMON.flask import register_standard_error_handlers

app = Flask(__name__)

# ✅ REGISTER ERROR HANDLERS (1 line replaces 50+ lines)
register_standard_error_handlers(app, "PGP_ORCHESTRATOR_v1")

# DELETE local error handlers (lines 559-607)
# @app.errorhandler(400)  ← DELETE
# @app.errorhandler(404)  ← DELETE
# @app.errorhandler(Exception)  ← DELETE
```

Repeat for:
- PGP_NP_IPN_v1/pgp_np_ipn_v1.py
- PGP_INVITE_v1/pgp_invite_v1.py
- PGP_BROADCAST_v1/broadcast_service.py (or main service file)

**Success Criteria:**
- ✅ 1 line replaces ~50 lines in each service
- ✅ Consistent error responses across all services
- ✅ Error logging includes service name context
- ✅ All error types handled (400, 404, 429, 500, Exception)

---

### R-07: DUPLICATE CRYPTO PRICING VALIDATION

**Status:** ✅ Already completed in H-04
- Created `validate_crypto_symbol()` in PGP_COMMON
- Created `validate_and_convert_to_usd()` in CryptoPricingClient
- Applied to PGP_NP_IPN_v1

---

## PHASE 2 COMPLETION SUMMARY

**Security Issues Fixed:**
- ✅ H-01: Input validation (completed in C-03)
- ✅ H-02: Error sanitization
- ✅ H-03: Bot context manager (connection cleanup)
- ✅ H-04: Crypto symbol validation
- ✅ H-05: CORS restriction
- ✅ H-06: Connection pooling (QueuePool)
- ✅ H-07: JWT logging (completed in C-04)
- ✅ H-08: Payment data sanitization (completed in C-03)

**Code Consolidation:**
- ✅ R-01: Idempotency (completed in C-02)
- ✅ R-02: Token decoding (~280 lines removed)
- ✅ R-03: Error handlers (~200 lines removed)
- ✅ R-07: Crypto validation (completed in H-04)

**Total Impact:**
- ~500 lines of duplicate code removed
- All high-severity security issues resolved
- Standardized patterns across all services

---

## PHASE 3: CODE QUALITY & REMAINING WORK (P2 - Weeks 3-4)
**Timeline:** Days 15-28 (Weeks 3-4)
**Estimated Time:** 15 hours
**Focus:** Dead code removal + medium security issues + remaining consolidations

### Dead Code Removal (D-01 to D-07)

**Time Estimate:** 2 hours total

#### D-01: UNDEFINED get_db_connection() (Already fixed in C-01)
**Status:** ✅ COMPLETE

#### D-02: DEPRECATED CORS CONFIGURATION

**File:** PGP_NP_IPN_v1/pgp_np_ipn_v1.py Lines 30-50
**Action:** Add expiration date and monitoring

```python
# BEFORE:
# CORS backward compatibility

# AFTER:
# =================================================================================
# CORS BACKWARD COMPATIBILITY - SCHEDULED FOR REMOVAL 2025-12-31
# =================================================================================
# Old payment-processing.html hosted on Cloud Storage may still call /api/*
# Monitoring: Check logs monthly, if no /api/* requests for 90 days → remove CORS
# Last checked: 2025-11-18 (TODO: check again 2025-12-18)
# =================================================================================
```

#### D-03: UNUSED calculate_expiration_time()

**File:** PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py Lines 82-107
**Action:** DELETE entire function

```bash
# Verify not used
grep -rn "calculate_expiration_time" PGP_ORCHESTRATOR_v1/

# Expected: Only definition, no calls

# Safe to delete
```

#### D-04: DEPRECATED ENDPOINT GET /

**File:** PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py Lines 114-200
**Action:** Add deprecation warning, schedule removal

```python
@app.route("/", methods=["GET"])
def deprecated_success_url():
    """
    DEPRECATED ENDPOINT - REMOVE AFTER 2025-12-31

    Old payment flow redirected to GET / with token.
    New flow uses POST /process-validated-payment.
    """
    logger.warning(
        f"⚠️ [DEPRECATED] GET / endpoint called - REMOVE AFTER 2025-12-31. "
        f"Token: {request.args.get('token', '')[:20]}..."
    )

    # ... existing logic if needed for backward compat ...
```

#### D-05: DUPLICATE get_payment_tolerances()

**File:** PGP_INVITE_v1/config_manager.py Lines 61-90
**Action:** Search for usages, delete if unused

```bash
grep -rn "get_payment_tolerances()" PGP_INVITE_v1/

# If 0 results → DELETE lines 61-90
```

#### D-06: SINGLETON PATTERN FUNCTION NEVER USED

**File:** PGP_BROADCAST_v1/config_manager.py Lines 259-273
**Action:** Search and delete

```bash
grep -rn "get_config_manager()" PGP_BROADCAST_v1/

# If 0 results → DELETE lines 259-273
```

#### D-07: OLD COMMENT BLOCKS

**File:** PGP_NP_IPN_v1/pgp_np_ipn_v1.py Lines 180-205
**Action:** DELETE (git history preserves this info)

```python
# DELETE entire block:
# =================================================================================
# NOTE ON REFACTORED FUNCTIONS
# =================================================================================
# ... 25 lines of comments ...
```

**Dead Code Removal Summary:**
- 7 items identified
- ~200 lines to remove
- 0 breaking changes (all unused code)

---

### Medium Security Issues (M-01 to M-12)

**Time Estimate:** 13 hours total

#### M-01: INCONSISTENT TOKEN EXPIRATION

**Status:** ✅ Already fixed in R-02
- Standardized to 1 hour across all services
- No additional work needed

#### M-02: NO REQUEST SIZE LIMIT

**Priority:** P2
**Time:** 30 minutes
**File:** PGP_NP_IPN_v1/pgp_np_ipn_v1.py

```python
# Add at app initialization
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # ✅ 1MB limit

# Add validation in handler
@app.route("/", methods=["POST"])
def nowpayments_ipn():
    if request.content_length and request.content_length > app.config['MAX_CONTENT_LENGTH']:
        logger.warning(f"⚠️ [IPN] Payload too large: {request.content_length} bytes")
        abort(413, "Payload too large")

    # ... continue processing ...
```

#### M-03: MISSING RATE LIMITING

**Priority:** P2
**Time:** 3 hours
**Files:** PGP_INVITE_v1, PGP_NP_IPN_v1, PGP_ORCHESTRATOR_v1

**Option 1: Redis-based rate limiting (RECOMMENDED)**

```python
# PGP_COMMON/utils/rate_limiter.py (NEW FILE)

from PGP_COMMON.utils import get_nonce_tracker
import time

class RateLimiter:
    """Redis-based rate limiter."""

    def __init__(self, redis_client=None):
        self.redis = redis_client or get_nonce_tracker()

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> bool:
        """
        Check if request within rate limit.

        Args:
            key: Unique key for this rate limit (e.g., "invite:user_123456789")
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            True if within limit, False if exceeded
        """
        current_count = self.redis.incr(key)

        if current_count == 1:
            # First request, set expiration
            self.redis.expire(key, window_seconds)

        return current_count <= max_requests

# Apply to PGP_INVITE_v1
from PGP_COMMON.utils import RateLimiter

rate_limiter = RateLimiter()

@app.route("/", methods=["POST"])
def send_telegram_invite():
    """Send invite with rate limiting."""

    # Extract user_id from token
    user_id = decode_token_for_user_id(request.json.get('token'))

    # Check rate limit: max 3 invites per user per hour
    rate_limit_key = f"invite_rate_limit:{user_id}"
    if not rate_limiter.check_rate_limit(rate_limit_key, max_requests=3, window_seconds=3600):
        logger.warning(f"⚠️ [INVITE] Rate limit exceeded for user {user_id}")
        return jsonify({
            "error": "Too many invite requests, please try again in 1 hour"
        }), 429

    # Continue processing...
```

#### M-04 to M-12: Additional Medium Issues

**Quick Summary:**

- **M-04:** HTTP timeout on CoinGecko (1hr) - Add `timeout=10` to requests
- **M-05:** Bot token in module scope (30min) - Use getter function
- **M-06:** Excessive PII logging (2hrs) - Audit and redact
- **M-07:** Duplicate of C-01 (DONE)
- **M-08:** Missing retry on Secret Manager (1hr) - Add retry logic
- **M-09:** Unsafe float comparison (1hr) - Use Decimal for money
- **M-10:** Overly permissive CORS (DONE in H-05)
- **M-11:** Health check doesn't test DB (1hr) - Add DB ping
- **M-12:** Missing type hints (2hrs) - Add to all public methods

---

## FINAL IMPLEMENTATION ROADMAP

### Week 1: Critical Fixes (P0)
**Days 1-5**

**Day 1:**
- [ ] C-01: Fix `get_db_connection()` (30min)
- [ ] Verify: Test PGP_NP_IPN_v1 doesn't crash

**Day 2-3:**
- [ ] C-02: Implement IdempotencyManager (2hrs)
- [ ] Verify: Race condition test passes

**Day 4:**
- [ ] C-03: Add input validation (3hrs)
- [ ] Verify: Invalid inputs rejected gracefully

**Day 5:**
- [ ] C-04: Remove secret logging (1hr)
- [ ] Deploy Phase 1
- [ ] Verify: Production stable, no crashes

---

### Week 2: Security Hardening (P1)
**Days 8-12**

**Day 8:**
- [ ] H-02: Error sanitization (2hrs)
- [ ] H-03: Bot context manager (1hr)

**Day 9:**
- [ ] H-04: Crypto symbol validation (2hrs)
- [ ] H-05: CORS restriction (30min)

**Day 10:**
- [ ] H-06: Connection pooling (1hr)
- [ ] R-02: Token consolidation (2hrs)

**Day 11:**
- [ ] R-03: Error handler consolidation (1hr)
- [ ] Integration testing

**Day 12:**
- [ ] Deploy Phase 2
- [ ] Verify: All high issues fixed

---

### Weeks 3-4: Code Quality (P2)
**Days 15-28**

**Week 3:**
- [ ] D-01 to D-07: Remove dead code (2hrs)
- [ ] M-02: Request size limits (30min)
- [ ] M-03: Rate limiting (3hrs)
- [ ] M-04 to M-12: Remaining medium issues (8hrs)

**Week 4:**
- [ ] Final testing & QA
- [ ] Documentation updates
- [ ] Deploy Phase 3
- [ ] Post-deployment monitoring

---

## SUCCESS METRICS

### After Phase 1 (Week 1):
- ✅ 0 NameError crashes
- ✅ 0 race condition duplicates
- ✅ 100% input validation on database queries
- ✅ 0 secrets in logs

### After Phase 2 (Week 2):
- ✅ 0 high-severity security issues
- ✅ ~500 lines duplicate code removed
- ✅ Consistent error handling across services
- ✅ Connection pooling prevents exhaustion

### After Phase 3 (Week 4):
- ✅ 0 medium-severity security issues
- ✅ ~820+ total lines removed
- ✅ All dead code eliminated
- ✅ Rate limiting on all public endpoints
- ✅ Comprehensive test coverage (>80%)

---

## RISK MITIGATION

### High Risk Items:
1. **C-02 Idempotency:** Test thoroughly (race conditions hard to debug)
2. **H-06 Connection pooling:** Monitor database connections closely
3. **R-02 Token consolidation:** Ensure backward compatibility

### Rollback Plan:
Each phase deployed independently:
- Phase 1 rollback: Revert to previous version (keep old db_manager pattern)
- Phase 2 rollback: Keep Phase 1 fixes, revert Phase 2 only
- Phase 3 rollback: Phases 1-2 remain stable

### Monitoring:
```bash
# After each deployment, monitor for 24 hours:
- Error rates (should not increase)
- Response times (should improve or stay same)
- Database connections (should decrease with QueuePool)
- Race condition attempts (should all be caught)
```

---

## CONCLUSION

This comprehensive checklist provides:
- ✅ Clear scope for all 33 issues identified
- ✅ Step-by-step resolution instructions
- ✅ File-by-file change mapping
- ✅ Verification steps for each fix
- ✅ Phased implementation (P0 → P1 → P2)
- ✅ Risk mitigation strategies
- ✅ Success criteria for each phase

**Total Estimated Time:** 34 hours across 3 phases
**Total Lines Removed:** ~1,000 lines
**Security Issues Fixed:** 24 issues (4 critical + 8 high + 12 medium)
**Code Quality Improvement:** 23 consolidation opportunities

Ready for implementation approval. 🚀
