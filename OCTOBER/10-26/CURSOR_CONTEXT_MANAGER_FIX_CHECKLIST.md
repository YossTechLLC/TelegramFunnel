# Cursor Context Manager Fix Checklist

## 🔍 Issue Overview

**CRITICAL BUG IDENTIFIED**: Multiple services are using an incorrect pattern for database cursor management that can lead to resource leaks and connection pool exhaustion.

### The Problem

The pattern `with self.get_connection() as conn, conn.cursor() as cur:` fails because:

1. `self.get_connection()` calls `self.pool.engine.raw_connection()`
2. This returns a `_ConnectionFairy` object (SQLAlchemy's connection wrapper from the connection pool)
3. `_ConnectionFairy` DOES support being used as a context manager: `with conn:`
4. BUT `conn.cursor()` returns a **pg8000/psycopg2 cursor object** that is NOT context-manager-compatible when chained
5. The nested context manager pattern `conn.cursor() as cur:` FAILS ❌

### Current Issue Location

**TelePay10-26/database.py**:
- Line 661: `fetch_expired_subscriptions()` method
- Line 719: `deactivate_subscription()` method

**TelePay10-26/subscription_manager.py**:
- Line 96: `fetch_expired_subscriptions()` method
- Line 197: `deactivate_subscription()` method

---

## 📊 Services Audit Results

### ✅ Services Using CORRECT Pattern (No Changes Needed)

These services properly manage connections and cursors:

1. **GCAccumulator-10-26/database_manager.py**
   - Pattern: Manual try/finally with explicit cursor close
   - Status: ✅ GOOD

2. **GCSplit2-10-26/database_manager.py**
   - Pattern: Manual try/finally with explicit cursor close
   - Status: ✅ GOOD

3. **GCNotificationService-10-26/database_manager.py**
   - Pattern: Manual connection + cursor with explicit close
   - Status: ✅ GOOD

4. **GCSubscriptionMonitor-10-26/database_manager.py**
   - Pattern: SQLAlchemy with text() queries (no raw cursors)
   - Status: ✅ GOOD

5. **GCBroadcastScheduler-10-26/database_manager.py**
   - Pattern: SQLAlchemy with text() queries (no raw cursors)
   - Status: ✅ GOOD

---

### ⚠️ Services Requiring Fixes

The following services use the PROBLEMATIC pattern and need to be fixed:

---

## 🔧 Fixing Instructions

For each service, we need to change from:

```python
# ❌ BROKEN PATTERN
with self.get_connection() as conn, conn.cursor() as cur:
    cur.execute("...")
    result = cur.fetchone()
```

To:

```python
# ✅ CORRECT PATTERN (Option A - Nested Context Managers)
with self.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("...")
        result = cur.fetchone()
```

OR:

```python
# ✅ CORRECT PATTERN (Option B - Manual Management - Recommended)
conn = None
try:
    conn = self.get_connection()
    if not conn:
        return None
    cur = conn.cursor()
    cur.execute("...")
    result = cur.fetchone()
    cur.close()
    return result
except Exception as e:
    print(f"❌ Database error: {e}")
    return None
finally:
    if conn:
        conn.close()
```

**Recommendation**: Use **Option B (Manual Management)** as it matches the pattern already used successfully in GCAccumulator-10-26 and GCSplit2-10-26.

---

## 📋 Service-by-Service Fix Checklist

### 1. TelePay10-26/database.py ⚠️ CRITICAL

**Priority**: CRITICAL (Blocking subscription expiration workflow)

**Methods to Fix**:

- [ ] **Line 661**: `fetch_expired_subscriptions()`
  - Change: `with self.get_connection() as conn, conn.cursor() as cur:`
  - To: Manual try/finally pattern
  - Impact: Subscription monitoring broken

- [ ] **Line 719**: `deactivate_subscription()`
  - Change: `with self.get_connection() as conn, conn.cursor() as cur:`
  - To: Manual try/finally pattern
  - Impact: Cannot mark subscriptions as inactive

**Files Impacted**: 1
**Methods to Fix**: 2

---

### 2. TelePay10-26/subscription_manager.py ⚠️ CRITICAL

**Priority**: CRITICAL (Blocking subscription expiration workflow)

**Methods to Fix**:

- [ ] **Line 96**: `fetch_expired_subscriptions()`
  - Change: `with self.db_manager.get_connection() as conn, conn.cursor() as cur:`
  - To: Manual try/finally pattern
  - Impact: SubscriptionManager cannot fetch expired subscriptions

- [ ] **Line 197**: `deactivate_subscription()`
  - Change: `with self.db_manager.get_connection() as conn, conn.cursor() as cur:`
  - To: Manual try/finally pattern
  - Impact: SubscriptionManager cannot deactivate subscriptions

**Files Impacted**: 1
**Methods to Fix**: 2

---

### 3. GCWebhook1-10-26/database_manager.py ⚠️ HIGH

**Priority**: HIGH (Payment processing webhook)

**Methods to Fix**:

- [ ] **Line 120**: `update_subscription_record()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 200**: `get_payout_info()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 252**: `get_subscription_id()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 313**: `get_nowpayments_data()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

**Files Impacted**: 1
**Methods to Fix**: 4

---

### 4. GCWebhook2-10-26/database_manager.py ⚠️ HIGH

**Priority**: HIGH (Payment processing webhook)

**Methods to Fix**:

- [ ] **Line 103**: `get_nowpayments_data()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

**Files Impacted**: 1
**Methods to Fix**: 1

---

### 5. np-webhook-10-26/database_manager.py ⚠️ HIGH

**Priority**: HIGH (NowPayments webhook handler)

**Methods to Fix**:

- [ ] **Line 120**: `update_subscription_record()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 200**: `get_payout_info()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 252**: `get_subscription_id()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 313**: `get_nowpayments_data()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

**Files Impacted**: 1
**Methods to Fix**: 4

---

### 6. GCSplit1-10-26/database_manager.py ⚠️ HIGH

**Priority**: HIGH (Payout splitting service)

**Methods to Fix**:

- [ ] **Line 160**: `insert_split_payout_que_record()`
  - Pattern: `conn = self.get_database_connection()` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios
  - Note: Uses different method name `get_database_connection()`

- [ ] **Line 305**: `insert_split_payout_hostpay_record()`
  - Pattern: `conn = self.get_database_connection()` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 355**: `get_payment_by_tx_hash()`
  - Pattern: `conn = self.get_database_connection()` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

**Files Impacted**: 1
**Methods to Fix**: 3

---

### 7. GCHostPay1-10-26/database_manager.py ⚠️ HIGH

**Priority**: HIGH (Payout execution service)

**Methods to Fix**:

- [ ] **Line 118**: `insert_hostpay_record()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 216**: `update_hostpay_tx_hash()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 272**: `mark_hostpay_completed()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 368**: `get_unique_id_by_tx_hash()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

**Files Impacted**: 1
**Methods to Fix**: 4

---

### 8. GCHostPay3-10-26/database_manager.py ⚠️ HIGH

**Priority**: HIGH (Payout execution service)

**Methods to Fix**:

- [ ] Review all methods using cursor pattern (similar to GCHostPay1-10-26)
- [ ] Implement manual try/finally pattern for all cursor usage

**Files Impacted**: 1
**Methods to Fix**: ~4 (needs detailed review)

---

### 9. GCMicroBatchProcessor-10-26/database_manager.py ⚠️ HIGH

**Priority**: HIGH (Batch conversion processor)

**Methods to Fix**:

- [ ] **Line 76**: `get_total_pending_usd()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 117**: `get_all_pending_payments()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 184**: `create_batch_conversion()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 228**: `update_payments_to_swapping()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 273**: `get_payments_for_batch()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 395**: `update_swap_details()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 444**: `finalize_batch_conversion()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 488**: `get_total_pending_actual_eth()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

**Files Impacted**: 1
**Methods to Fix**: 8

---

### 10. GCBatchProcessor-10-26/database_manager.py ⚠️ HIGH

**Priority**: HIGH (Threshold batch processor)

**Methods to Fix**:

- [ ] **Line 72**: `get_clients_over_threshold()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 186**: `create_batch_record()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 238**: `update_batch_status()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 282**: `mark_accumulations_as_paid()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 330**: `get_accumulated_actual_eth()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

**Files Impacted**: 1
**Methods to Fix**: 5

---

### 11. GCBroadcastService-10-26/clients/database_client.py ⚠️ MEDIUM

**Priority**: MEDIUM (Broadcast service)

**Methods to Fix**:

- [ ] **Line 117, 120**: `fetch_due_broadcasts()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 195, 196**: `get_broadcast_by_id()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 243, 244**: `mark_broadcast_sent()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 284, 285**: `mark_broadcast_failed()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 328, 329**: `mark_broadcast_canceled()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 377, 378**: `get_all_manual_trigger_times()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 405, 406**: `update_manual_trigger_time()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

- [ ] **Line 443, 444**: `get_all_broadcasts()`
  - Pattern: `with self.get_connection() as conn:` + `cur = conn.cursor()`
  - Issue: Cursor not closed in exception scenarios

**Files Impacted**: 1
**Methods to Fix**: 8

---

## 📈 Summary Statistics

| Priority | Services | Files | Total Methods | Status |
|----------|----------|-------|---------------|--------|
| **CRITICAL** | 2 | 2 | 4 | ⚠️ NOT FIXED |
| **HIGH** | 8 | 8 | 37 | ⚠️ NOT FIXED |
| **MEDIUM** | 1 | 1 | 8 | ⚠️ NOT FIXED |
| **GOOD** | 5 | 5 | N/A | ✅ NO ISSUES |
| **TOTAL** | 16 | 16 | 49 | - |

**Services Requiring Fixes**: 11 (69%)
**Total Methods to Fix**: 49
**Services Already Correct**: 5 (31%)

---

## 🔄 Implementation Strategy

### Phase 1: CRITICAL (Immediate - Subscription Flow Broken)
1. Fix TelePay10-26/database.py (2 methods)
2. Fix TelePay10-26/subscription_manager.py (2 methods)
3. Deploy and test subscription expiration workflow

### Phase 2: HIGH Priority (Payment Processing)
1. Fix GCWebhook1-10-26/database_manager.py (4 methods)
2. Fix GCWebhook2-10-26/database_manager.py (1 method)
3. Fix np-webhook-10-26/database_manager.py (4 methods)
4. Deploy and test payment webhooks

### Phase 3: HIGH Priority (Payout Processing)
1. Fix GCSplit1-10-26/database_manager.py (3 methods)
2. Fix GCHostPay1-10-26/database_manager.py (4 methods)
3. Fix GCHostPay3-10-26/database_manager.py (~4 methods)
4. Deploy and test payout splitting and execution

### Phase 4: HIGH Priority (Batch Processing)
1. Fix GCMicroBatchProcessor-10-26/database_manager.py (8 methods)
2. Fix GCBatchProcessor-10-26/database_manager.py (5 methods)
3. Deploy and test batch conversion and threshold batching

### Phase 5: MEDIUM Priority (Broadcast Service)
1. Fix GCBroadcastService-10-26/clients/database_client.py (8 methods)
2. Deploy and test broadcast functionality

---

## 🧪 Testing Requirements

For each service after fixing:

1. **Unit Testing**:
   - Test each method with successful execution
   - Test each method with database exception (to verify cleanup)
   - Verify cursor is closed in all scenarios

2. **Integration Testing**:
   - Test the full workflow for each service
   - Monitor connection pool metrics during testing
   - Verify no connection/cursor leaks

3. **Load Testing** (for payment services):
   - Simulate high volume of concurrent requests
   - Monitor connection pool exhaustion
   - Verify proper resource cleanup under load

---

## 📝 Deployment Checklist

- [ ] Phase 1 - Fix TelePay10-26 (CRITICAL)
  - [ ] Update database.py
  - [ ] Update subscription_manager.py
  - [ ] Deploy TelePay10-26
  - [ ] Test subscription expiration workflow
  - [ ] Update PROGRESS.md
  - [ ] Update BUGS.md

- [ ] Phase 2 - Fix Webhook Services (HIGH)
  - [ ] Update GCWebhook1-10-26
  - [ ] Update GCWebhook2-10-26
  - [ ] Update np-webhook-10-26
  - [ ] Deploy webhook services
  - [ ] Test payment processing
  - [ ] Update PROGRESS.md

- [ ] Phase 3 - Fix Payout Services (HIGH)
  - [ ] Update GCSplit1-10-26
  - [ ] Update GCHostPay1-10-26
  - [ ] Update GCHostPay3-10-26
  - [ ] Deploy payout services
  - [ ] Test payout splitting and execution
  - [ ] Update PROGRESS.md

- [ ] Phase 4 - Fix Batch Processors (HIGH)
  - [ ] Update GCMicroBatchProcessor-10-26
  - [ ] Update GCBatchProcessor-10-26
  - [ ] Deploy batch processors
  - [ ] Test batch conversion and threshold batching
  - [ ] Update PROGRESS.md

- [ ] Phase 5 - Fix Broadcast Service (MEDIUM)
  - [ ] Update GCBroadcastService-10-26
  - [ ] Deploy broadcast service
  - [ ] Test broadcast functionality
  - [ ] Update PROGRESS.md

- [ ] Final Steps
  - [ ] Update DECISIONS.md with architectural decision
  - [ ] Mark all items in BUGS.md as resolved
  - [ ] Create comprehensive testing report

---

## 🎯 Success Criteria

- [ ] All 49 methods updated to use correct cursor management pattern
- [ ] All services deployed successfully
- [ ] All integration tests passing
- [ ] No connection pool exhaustion under normal load
- [ ] No cursor leaks detected during testing
- [ ] Subscription expiration workflow working correctly
- [ ] Payment processing working correctly
- [ ] Payout processing working correctly
- [ ] Batch processing working correctly
- [ ] Broadcast functionality working correctly

---

## ⚠️ Risk Assessment

### High Risk Areas

1. **Payment Processing** (GCWebhook1, GCWebhook2, np-webhook)
   - Impact: Users cannot complete subscriptions
   - Mitigation: Fix and test in development first

2. **Payout Processing** (GCSplit1, GCHostPay1, GCHostPay3)
   - Impact: Content creators cannot receive payouts
   - Mitigation: Monitor payout queue closely during deployment

3. **Subscription Expiration** (TelePay10-26)
   - Impact: Users retain access after subscription expires
   - Mitigation: CRITICAL FIX - Deploy immediately

### Medium Risk Areas

1. **Batch Processing** (GCMicroBatchProcessor, GCBatchProcessor)
   - Impact: Payouts may be delayed
   - Mitigation: Monitor batch queues during deployment

2. **Broadcast Service** (GCBroadcastService)
   - Impact: Broadcast messages may fail
   - Mitigation: Test thoroughly before deployment

---

## 📚 Reference Implementation

Use **GCAccumulator-10-26/database_manager.py** as the reference implementation for the correct pattern:

```python
def get_total_accumulated_usd(self, open_channel_id: str) -> float:
    """Get total accumulated USD for a client."""
    conn = None
    try:
        conn = self.get_connection()
        if not conn:
            print("❌ [ACCUMULATOR] Failed to get database connection")
            return 0.0

        cur = conn.cursor()
        query = """
            SELECT COALESCE(SUM(nowpayments_outcome_usd), 0.0)
            FROM payout_accumulation_database
            WHERE open_channel_id = %s
            AND status = 'pending'
        """
        cur.execute(query, (open_channel_id,))
        result = cur.fetchone()
        cur.close()  # ✅ Explicitly close cursor

        total = float(result[0]) if result and result[0] else 0.0
        return total

    except Exception as e:
        print(f"❌ [ACCUMULATOR] Error getting total accumulated USD: {e}")
        return 0.0
    finally:
        if conn:
            conn.close()  # ✅ Always close connection in finally block
```

---

## 🚀 Next Steps

1. **Confirm approach**: User approval of fixing strategy
2. **Start with Phase 1**: Fix CRITICAL TelePay10-26 issues first
3. **Progressive deployment**: Fix and deploy in phases
4. **Continuous monitoring**: Watch for connection pool issues
5. **Documentation**: Update all relevant documentation

---

**Created**: 2025-11-14
**Status**: AWAITING USER APPROVAL TO PROCEED
**Total Estimated Time**: 6-8 hours for all fixes and testing
