# Repeated Telegram Invites - Architectural Solution Design

**Date:** 2025-11-02  
**Issue:** Idempotency failure causing duplicate payment processing and Telegram invites  
**Status:** 📐 ARCHITECTURAL DESIGN

---

## Executive Summary

This document outlines the architectural changes required to implement idempotency in the payment processing system, preventing duplicate Telegram invitations and duplicate payment accumulation.

### Core Problem

**Current Behavior:** Same payment can be processed multiple times, resulting in:
- Multiple Telegram invite links sent to users (9 duplicate invites observed)
- Same payment accumulated multiple times (potential 9x payout inflation)
- Unnecessary Cloud Tasks usage and costs

**Root Cause:** System lacks idempotency checks - no mechanism to prevent re-processing of already-handled payments.

**Solution Approach:** Multi-layered idempotency tracking using database state management.

---

## Current Architecture Analysis

### Payment Processing Flow (As-Is)

```
┌─────────────────┐
│  NowPayments    │
│  IPN Callback   │
└────────┬────────┘
         │ POST /ipn
         ▼
┌──────────────────────────────────────────────────────────┐
│  NP-Webhook (np-webhook-10-26)                          │
│  1. Validates IPN signature                              │
│  2. Updates DB: payment_status = 'confirmed'            │
│  3. Enqueues to GCWebhook1 ◄──── NO IDEMPOTENCY CHECK  │
└────────┬─────────────────────────────────────────────────┘
         │ Cloud Tasks: gcwebhook1-queue
         ▼
┌──────────────────────────────────────────────────────────┐
│  GCWebhook1 (gcwebhook1-10-26)                          │
│  1. Receives payment data (includes payment_id)          │
│  2. Routes to GCAccumulator or GCSplit1                  │
│  3. Encrypts token for GCWebhook2 (NO payment_id)       │
│  4. Enqueues to GCWebhook2 ◄──── NO IDEMPOTENCY CHECK  │
└────────┬─────────────────────────────────────────────────┘
         │ Cloud Tasks: gcwebhook-telegram-invite-queue
         ▼
┌──────────────────────────────────────────────────────────┐
│  GCWebhook2 (gcwebhook2-10-26)                          │
│  1. Decrypts token                                       │
│  2. Creates Telegram invite link                         │
│  3. Sends invite to user ◄──── NO IDEMPOTENCY CHECK    │
│  4. Returns 200 OK                                       │
└──────────────────────────────────────────────────────────┘
```

### Critical Gap Analysis

| Service | Receives payment_id? | Has Idempotency Check? | Impact |
|---------|---------------------|----------------------|--------|
| **NP-Webhook IPN** | ✅ YES (`payment_data['payment_id']`) | ❌ NO | Can enqueue same payment multiple times |
| **GCWebhook1** | ✅ YES (`nowpayments_payment_id`) | ❌ NO | Processes payment multiple times |
| **GCWebhook2** | ❌ NO (not in token) | ❌ NO | Sends invite every time called |

**Key Finding:** `nowpayments_payment_id` is available in NP-Webhook and GCWebhook1, but **NOT passed to GCWebhook2**.

---

## Proposed Architecture (To-Be)

### Design Principles

1. **Defense in Depth:** Multiple layers of idempotency checks
2. **Single Source of Truth:** Database-tracked payment processing state
3. **Atomic Operations:** Use database constraints to prevent race conditions
4. **Minimal Changes:** Preserve existing functionality where possible
5. **Backward Compatible:** Existing payments grandfathered in

### Core Data Model: Payment Processing State Tracking

**New Table: `processed_payments`**

```sql
CREATE TABLE IF NOT EXISTS processed_payments (
    -- Primary key: NowPayments payment_id (unique identifier)
    payment_id BIGINT PRIMARY KEY,
    
    -- Reference data for lookups and debugging
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    
    -- Processing state flags
    gcwebhook1_processed BOOLEAN DEFAULT FALSE,
    gcwebhook1_processed_at TIMESTAMP,
    
    telegram_invite_sent BOOLEAN DEFAULT FALSE,
    telegram_invite_sent_at TIMESTAMP,
    telegram_invite_link TEXT,
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookups
CREATE INDEX idx_processed_payments_user_channel ON processed_payments(user_id, channel_id);
CREATE INDEX idx_processed_payments_invite_status ON processed_payments(telegram_invite_sent);
CREATE INDEX idx_processed_payments_webhook1_status ON processed_payments(gcwebhook1_processed);
```

**Why This Design:**
- ✅ **Unique payment_id** prevents duplicate entries (database-level enforcement)
- ✅ **Separate state flags** allow tracking each processing stage independently
- ✅ **Timestamps** provide audit trail for debugging
- ✅ **Stored invite link** enables returning same link if re-requested
- ✅ **User/channel index** supports alternative lookup patterns

---

## Architectural Changes by Service

### 1. NP-Webhook: Add Idempotency Check

**Location:** `/ipn` endpoint (line ~659 in app.py)  
**Change:** Add check BEFORE enqueueing to GCWebhook1

#### Implementation Pseudocode

```python
# In np-webhook app.py, AFTER validating IPN signature
# BEFORE calling cloudtasks_client.enqueue_gcwebhook1_validated_payment()

nowpayments_payment_id = payment_data['payment_id']

# Check if payment already processed
existing_payment = db_execute_query("""
    SELECT gcwebhook1_processed, telegram_invite_sent
    FROM processed_payments
    WHERE payment_id = %s
""", (nowpayments_payment_id,))

if existing_payment and existing_payment[0]['gcwebhook1_processed']:
    # Already processed - skip enqueueing
    print(f"✅ [IDEMPOTENCY] Payment {nowpayments_payment_id} already processed")
    return jsonify({"status": "success", "message": "Already handled"}), 200

# If not processed, insert initial record (prevents race conditions)
db_execute_query("""
    INSERT INTO processed_payments (payment_id, user_id, channel_id)
    VALUES (%s, %s, %s)
    ON CONFLICT (payment_id) DO NOTHING
""", (nowpayments_payment_id, user_id, closed_channel_id))

# Now safe to enqueue to GCWebhook1
task_name = cloudtasks_client.enqueue_gcwebhook1_validated_payment(...)
```

**Impact:**
- ✅ Stops duplicate processing at earliest point
- ✅ Handles concurrent IPN callbacks safely (ON CONFLICT)
- ⚠️ Requires database manager in NP-Webhook

---

### 2. GCWebhook1: Mark Payment as Processed

**Location:** `/process-validated-payment` endpoint (line ~430 in tph1-10-26.py)  
**Change:** Update database AFTER successful processing

#### Implementation Pseudocode

```python
# In gcwebhook1 tph1-10-26.py
# AFTER successfully enqueueing to GCAccumulator/GCSplit1 AND GCWebhook2

db_manager.execute_query("""
    UPDATE processed_payments
    SET 
        gcwebhook1_processed = TRUE,
        gcwebhook1_processed_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE payment_id = %s
""", (nowpayments_payment_id,))

print(f"✅ [IDEMPOTENCY] Marked payment {nowpayments_payment_id} as processed")
```

---

### 3. GCWebhook1 to GCWebhook2: Pass payment_id

**Location:** Cloud Tasks enqueue call (line ~410-420 in tph1-10-26.py)  
**Change:** Add payment_id as separate parameter in task payload

#### Current State
```python
# Token does NOT include payment_id
encrypted_token = token_manager.encrypt_token_for_gcwebhook2(
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    # ... other fields ...
    # ❌ payment_id NOT included
)
```

#### Proposed Change

**Recommendation:** Pass payment_id as SEPARATE parameter (not in token)

```python
# In cloudtasks_client.py enqueue_telegram_invite()
task_payload = {
    'encrypted_token': encrypted_token,
    'payment_id': nowpayments_payment_id  # ← NEW FIELD
}
```

**Why separate parameter:**
- ✅ No token schema changes (lower risk)
- ✅ payment_id is not sensitive (no encryption needed)
- ✅ Easier to implement and test

---

### 4. GCWebhook2: Idempotency Check + Mark Invite Sent

**Location:** `/` endpoint (line ~84 in tph2-10-26.py)  
**Changes:** Extract payment_id, check if invite sent, mark as sent

#### Implementation Pseudocode

```python
@app.route("/", methods=["POST"])
def send_telegram_invite():
    # Extract request data
    request_data = request.get_json()
    encrypted_token = request_data.get('encrypted_token')
    payment_id = request_data.get('payment_id')  # ← NEW FIELD
    
    # Idempotency check
    existing_invite = db_manager.execute_query("""
        SELECT telegram_invite_sent, telegram_invite_link
        FROM processed_payments
        WHERE payment_id = %s
    """, (payment_id,))
    
    if existing_invite and existing_invite[0]['telegram_invite_sent']:
        # Already sent - return success without re-sending
        print(f"✅ [IDEMPOTENCY] Invite already sent for payment {payment_id}")
        return jsonify({"status": "success", "message": "Already sent"}), 200
    
    # Decrypt token and send invite (existing logic)
    token_data = token_manager.decrypt_token_from_gcwebhook1(encrypted_token)
    # ... create invite link ...
    # ... send to user ...
    
    # Mark invite as sent
    db_manager.execute_query("""
        UPDATE processed_payments
        SET 
            telegram_invite_sent = TRUE,
            telegram_invite_sent_at = CURRENT_TIMESTAMP,
            telegram_invite_link = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE payment_id = %s
    """, (invite_link, payment_id))
    
    print(f"✅ [IDEMPOTENCY] Marked invite as sent for payment {payment_id}")
    return jsonify({"status": "success"}), 200
```

---

## Database Migration Strategy

### Phase 1: Create Table

```sql
-- File: scripts/create_processed_payments_table.sql

BEGIN;

CREATE TABLE IF NOT EXISTS processed_payments (
    payment_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    gcwebhook1_processed BOOLEAN DEFAULT FALSE,
    gcwebhook1_processed_at TIMESTAMP,
    telegram_invite_sent BOOLEAN DEFAULT FALSE,
    telegram_invite_sent_at TIMESTAMP,
    telegram_invite_link TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processed_payments_user_channel 
ON processed_payments(user_id, channel_id);

CREATE INDEX IF NOT EXISTS idx_processed_payments_invite_status 
ON processed_payments(telegram_invite_sent);

CREATE INDEX IF NOT EXISTS idx_processed_payments_webhook1_status 
ON processed_payments(gcwebhook1_processed);

COMMIT;
```

### Phase 2: Backward Compatibility

**Existing Payments:** Will NOT have entries in `processed_payments`.
- First-time processing: Allowed (no record exists)
- After processing: Record created → Prevents future duplicates
- **No data migration needed**

---

## Risk Analysis & Mitigation

### Risk 1: Database Connection Failures

**Severity:** HIGH  
**Mitigation:** Graceful fallback - log error but continue processing (fail-open)

### Risk 2: Race Conditions

**Severity:** MEDIUM  
**Mitigation:** Use `INSERT ... ON CONFLICT DO NOTHING` (atomic operation)

### Risk 3: GCWebhook2 Fails to Update After Sending

**Severity:** MEDIUM  
**Mitigation:** Cloud Tasks retry will mark as sent on retry

### Risk 4: Token Schema Changes

**Severity:** LOW (using separate parameter, not changing token)  
**Mitigation:** No token changes required

---

## Testing Strategy

### Test 1: NP-Webhook Idempotency
1. Trigger IPN for NEW payment → Verify processing
2. Trigger SAME IPN again → Verify "already processed" log
3. Check database: One entry in `processed_payments`

### Test 2: GCWebhook2 Idempotency
1. Enqueue to GCWebhook2 with NEW payment_id → Verify invite sent
2. Enqueue SAME task again → Verify "already sent" log
3. User receives exactly ONE invite

### Test 3: End-to-End
1. Complete NEW payment → Monitor all services
2. Verify: One invite sent, one accumulation, one database entry

---

## Deployment Plan

### Order of Deployment

1. **Database migration** (create `processed_payments` table)
2. **GCWebhook2** (downstream first)
3. **GCWebhook1** (middle)
4. **NP-Webhook** (upstream last)

**Why this order:** Downstream services ready before upstream starts using new features.

### Commands

```bash
# 1. Database
psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
     -U postgres -d telepaydb \
     -f scripts/create_processed_payments_table.sql

# 2. Deploy services (GCWebhook2, GCWebhook1, NP-Webhook)
cd GCWebhook2-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook2-10-26
gcloud run deploy gcwebhook2-10-26 --image gcr.io/telepay-459221/gcwebhook2-10-26 ...
# (repeat for other services)
```

---

## Rollback Plan

### If Critical Issues Detected

```bash
# Revert to previous revision
gcloud run services update-traffic gcwebhook2-10-26 \
  --to-revisions=gcwebhook2-10-26-00014-nn4=100 \
  --region=us-central1
```

**Recovery Time:** < 5 minutes  
**Database:** Keep table (no harm, can reuse for future deployment)

---

## Success Metrics

- ✅ **Zero duplicate invites** - User receives exactly 1 invite per payment
- ✅ **Zero duplicate accumulation** - Payment accumulated exactly once
- ✅ **All invites delivered** - No failures due to idempotency checks
- ⏱️ **Database query latency** - < 50ms for idempotency checks

### Monitoring Queries

```sql
-- Total payments processed
SELECT COUNT(*) FROM processed_payments;

-- Payments with invites sent
SELECT COUNT(*) FROM processed_payments WHERE telegram_invite_sent = TRUE;

-- Check for duplicates (should be zero)
SELECT payment_id, COUNT(*) 
FROM processed_payments 
GROUP BY payment_id 
HAVING COUNT(*) > 1;
```

---

## Code Changes Summary

### Files to Modify

1. **np-webhook-10-26/app.py**
   - Add idempotency check in `/ipn` endpoint (line ~659)
   - Add database_manager import (if not present)

2. **GCWebhook1-10-26/tph1-10-26.py**
   - Mark payment as processed after enqueueing (line ~430)

3. **GCWebhook1-10-26/cloudtasks_client.py**
   - Add `payment_id` parameter to `enqueue_telegram_invite()`

4. **GCWebhook2-10-26/tph2-10-26.py**
   - Extract `payment_id` from request
   - Add idempotency check
   - Mark invite as sent after sending

5. **New File: scripts/create_processed_payments_table.sql**
   - Database migration script

---

## Future Enhancements

### Phase 2 Considerations

1. **Invite Link Reuse**
   - Return existing invite if still valid
   - Reduces Telegram API calls

2. **Payment Status Dashboard**
   - Admin UI to view `processed_payments`
   - Resend invite functionality

3. **Automated Cleanup**
   - Archive old records (> 90 days)

4. **Monitoring Dashboard**
   - Grafana metrics for payment processing
   - Alerts on duplicate detection spike

---

## References

### Related Documents

- [REPEATED_TELEGRAM_INVITES_INVESTIGATION_REPORT.md](./REPEATED_TELEGRAM_INVITES_INVESTIGATION_REPORT.md)
- [REPEATED_TELEGRAM_INVITES_ROOT_CAUSE_ANALYSIS.md](./REPEATED_TELEGRAM_INVITES_ROOT_CAUSE_ANALYSIS.md)
- [QUEUE_VERIFICATION_REPORT.md](./QUEUE_VERIFICATION_REPORT.md)

### Code References

- **NP-Webhook IPN:** `np-webhook-10-26/app.py` line ~450-699
- **GCWebhook1:** `GCWebhook1-10-26/tph1-10-26.py` line 220-450
- **GCWebhook2:** `GCWebhook2-10-26/tph2-10-26.py` line 84-200

---

**Status:** 📐 **ARCHITECTURAL DESIGN COMPLETE**

**Next Action:** Review with user, get approval to proceed with implementation

**Estimated Implementation Time:** 4-6 hours

**Risk Level:** MEDIUM (mitigated by rollback plan and phased deployment)
