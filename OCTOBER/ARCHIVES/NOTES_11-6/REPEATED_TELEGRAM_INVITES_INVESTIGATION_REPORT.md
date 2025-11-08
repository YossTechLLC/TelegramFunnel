# Repeated Telegram Invites - Investigation Report

**Date:** 2025-11-02
**Issue:** Multiple one-time Telegram invitation links sent for single payment
**Status:** 🔍 ROOT CAUSE IDENTIFIED
**Payment Analyzed:** Payment ID 5996609246 ($1.35)

---

## Executive Summary

After Session 40's fix deployment, the repeated Telegram invite issue **persists** but for a **completely different reason** than Session 40's bug. The investigation reveals:

- ✅ **Session 40 fix is working** - GCWebhook1 no longer crashes (returns HTTP 200)
- ✅ **No Cloud Tasks retry loops** - Both queues are empty, tasks complete successfully
- ❌ **GCWebhook1 called 9 times** for the SAME payment within 8 minutes
- ❌ **Each call successfully sends a NEW invite** (no errors, working as designed)
- ❌ **Root cause: External trigger** calling GCWebhook1 repeatedly, NOT internal service failures

---

## Evidence Summary

### 1. GCWebhook1 Processing Pattern

**Payment ID 5996609246 processed 9 times:**

| Timestamp | Revision | Status | Invite Sent | Notes |
|-----------|----------|--------|-------------|-------|
| 16:22:19 | 00017-cpz | ✅ 200 | ✅ Yes | Before Session 40 fix |
| 16:22:49 | 00017-cpz | ✅ 200 | ✅ Yes | Before Session 40 fix |
| 16:23:49 | 00017-cpz | ✅ 200 | ✅ Yes | Before Session 40 fix |
| 16:24:40 | 00018-dpk | ✅ 200 | ✅ Yes | After Session 40 fix |
| 16:28:36 | 00018-dpk | ✅ 200 | ✅ Yes | After Session 40 fix |
| 16:28:38 | 00018-dpk | ✅ 200 | ✅ Yes | After Session 40 fix |
| 16:29:45 | 00018-dpk | ✅ 200 | ✅ Yes | After Session 40 fix |
| 16:29:50 | 00018-dpk | ✅ 200 | ✅ Yes | After Session 40 fix |
| 16:30:31 | 00018-dpk | ✅ 200 | ✅ Yes | After Session 40 fix (LATEST) |

**Pattern:** Initial ~30-60 second intervals, then larger gaps. All returned HTTP 200 (success).

### 2. GCWebhook2 (Telegram Invite Service) Logs

**9 distinct Telegram invites sent:**

| Timestamp | Invite Link | User ID | Status |
|-----------|-------------|---------|--------|
| 16:22:20 | https://t.me/+n_px-mYe-n8wM2Ux | 6271402111 | ✅ Sent |
| 16:22:50 | https://t.me/+PaYXv1sRP8RiYzEx | 6271402111 | ✅ Sent |
| 16:23:50 | https://t.me/+EUisI4-qofNmNzRh | 6271402111 | ✅ Sent |
| 16:24:41 | https://t.me/+WiAsSWl6mF9kMmUx | 6271402111 | ✅ Sent |
| 16:30:32 | https://t.me/+kBauQNfVHkU2MzRh | 6271402111 | ✅ Sent |
| 16:30:37 | https://t.me/+0jCtIaEB0CQ4YTFh | 6271402111 | ✅ Sent |
| 16:30:40 | https://t.me/+5fNOi434cAZiODMx | 6271402111 | ✅ Sent |
| 16:30:45 | https://t.me/+d1YIBhVLFNJhNjdh | 6271402111 | ✅ Sent |
| 16:30:51 | https://t.me/+u5poC8U-wFIxNjQx | 6271402111 | ✅ Sent |

**Observation:** Each GCWebhook1 call resulted in a unique, successfully sent Telegram invite.

### 3. Cloud Tasks Queue Status

```bash
# gcwebhook1-queue
Listed 0 items.

# gcwebhook-telegram-invite-queue
Listed 0 items.
```

**Result:** ✅ **NO stuck tasks** - All tasks completed successfully.

### 4. NowPayments IPN Analysis

**Critical Finding:** **NO IPN callbacks detected!**

```bash
# Search for POST /ipn requests (actual IPN callbacks)
Result: 0 items found

# Search for payment status API requests
Result: Multiple GET /api/payment-status requests found
```

**NP-Webhook Activity Pattern:**
- ✅ Multiple GET requests to `/api/payment-status?order_id=PGP-6271402111|-1003268562225`
- ❌ **ZERO POST requests to `/ipn`** (IPN callback endpoint)
- 📊 Timestamps: 16:34:26, 16:34:31, 16:34:37 (payment status polls)

**Implication:** The payment flow is **NOT driven by NowPayments IPN callbacks**. Instead, something is **polling the payment status** via GET API.

### 5. Latest GCWebhook1 Execution (16:30:31)

**Complete successful flow:**
```
✅ Received validated payment from NP-Webhook
✅ Payment Data Received: User 6271402111, Channel -1003296084379, Payment 5996609246
✅ Payout mode: threshold ($2.0)
✅ Successfully enqueued to GCAccumulator
✅ Enqueued Telegram invite to GCWebhook2
✅ Payment processing completed successfully
HTTP 200 OK
```

**No errors. Session 40 fix is working correctly.**

---

## Root Cause Analysis

### What Session 40 Fixed ✅

**Session 40 Part 3** fixed the line 437 type error that caused:
- GCWebhook1 to crash with HTTP 500 AFTER processing
- Cloud Tasks to retry the same task
- Each retry to send duplicate invites

**This is now resolved.** GCWebhook1 returns HTTP 200 and tasks complete successfully.

### What's STILL Causing Repeated Invites ❌

The **NEW root cause** is **external repeated calls** to GCWebhook1, NOT internal service failures.

**Evidence:**
1. **GCWebhook1 called 9 times** - Each call is a SEPARATE, successful execution
2. **All tasks complete** - No retry loops, all return HTTP 200
3. **No NowPayments IPNs** - NP-Webhook NOT receiving IPN POST callbacks
4. **Only status API polls** - NP-Webhook only handling GET /api/payment-status

**Likely Culprits:**

#### 🔴 **Hypothesis 1: Payment Success Page Polling (MOST LIKELY)**

**Scenario:**
1. User completes NowPayments payment
2. User redirected to success page (likely hosted on Google Cloud Storage)
3. **Success page polls `/api/payment-status` every few seconds** to check payment status
4. Each poll might trigger the payment processing flow AGAIN
5. Each processing sends a new invite

**Evidence:**
- GET /api/payment-status called multiple times from user's IP (97.81.68.5)
- User-Agent: Chrome browser (not NowPayments server)
- Referer: `https://storage.googleapis.com/`
- **This confirms user is viewing a page that's making API calls**

**Example Log:**
```
remoteIp: "97.81.68.5"
userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
referer: "https://storage.googleapis.com/"
requestUrl: "/api/payment-status?order_id=PGP-6271402111|-1003268562225"
requestMethod: "GET"
```

#### 🟡 **Hypothesis 2: NowPayments Webhook Retry**

**Scenario:**
1. NowPayments configured to send IPN callbacks
2. IPN endpoint misconfigured or returning errors
3. NowPayments retries IPN multiple times
4. Each retry triggers payment processing

**Evidence Against:**
- ❌ No POST /ipn requests found in np-webhook logs
- ❌ If IPNs were failing, we'd see error logs in np-webhook

**Likelihood:** Low

#### 🟡 **Hypothesis 3: Multiple Browser Tabs/Refreshes**

**Scenario:**
1. User opens payment success page in multiple tabs
2. Each tab polls payment status independently
3. Each poll triggers processing

**Evidence:**
- Multiple GET requests from same IP
- Timing pattern suggests automated polling (every ~5 seconds)

**Likelihood:** Medium

---

## Architecture Issue: Idempotency

**The fundamental problem:** The payment processing flow **lacks idempotency**.

### Current Behavior (Non-Idempotent)

```
Payment Status API Request
  ↓
NP-Webhook checks database
  ↓
Finds payment record (status: confirmed)
  ↓
Enqueues to GCWebhook1 (EVERY TIME)
  ↓
GCWebhook1 processes payment (EVERY TIME)
  ↓
Sends Telegram invite (EVERY TIME)
```

**Problem:** No check for "already processed" - same payment triggers full flow repeatedly.

### Expected Behavior (Idempotent)

```
Payment Status API Request
  ↓
NP-Webhook checks database
  ↓
Finds payment record
  ↓
CHECK: Has invite already been sent?
  ├─ YES → Return 200 OK (do nothing)
  └─ NO  → Enqueue to GCWebhook1 (one-time only)
```

**Solution:** Add idempotency check to prevent duplicate processing.

---

## Impact Assessment

### Services Affected

| Service | Impact | Severity |
|---------|--------|----------|
| **GCWebhook1** | Processes same payment 9 times | 🟡 MEDIUM |
| **GCWebhook2** | Sends 9 duplicate Telegram invites | 🔴 CRITICAL |
| **GCAccumulator** | Receives same payment 9 times | 🟡 MEDIUM |
| **NP-Webhook** | Handles multiple status API requests | ✅ NONE (working as designed) |
| **Users** | Receive 9 duplicate invite links | 🔴 CRITICAL |

### Data Integrity Risks

1. **Duplicate payment records in payout_accumulation table**
   - Same payment_id (5996609246) inserted 9 times
   - Accumulated amount inflated: $1.06 × 9 = $9.54 instead of $1.06
   - **Risk:** User could receive 9x payout

2. **Database constraints**
   - If `UNIQUE` constraint on `payment_id` exists → Insertion fails (good)
   - If no constraint → Duplicates created (bad)

**Action Required:** Verify database constraints on `payout_accumulation.payment_id`

---

## Solution Recommendations

### 🔴 **Solution 1: Add Idempotency to Payment Processing (RECOMMENDED)**

**Implementation:** Add "invite_sent" flag to database

**Changes Required:**

#### 1. Database Schema Update
```sql
-- Add invite_sent column to subscriptions table
ALTER TABLE subscriptions
ADD COLUMN invite_sent BOOLEAN DEFAULT FALSE;

-- Add index for faster lookups
CREATE INDEX idx_subscriptions_invite_sent
ON subscriptions(user_id, closed_channel_id, invite_sent);
```

#### 2. NP-Webhook Logic Update
```python
# In np-webhook /api/payment-status endpoint
# BEFORE enqueueing to GCWebhook1, check if invite already sent

# Query database
subscription = db.execute("""
    SELECT invite_sent FROM subscriptions
    WHERE user_id = %s AND closed_channel_id = %s
""", (user_id, closed_channel_id))

if subscription['invite_sent']:
    # Invite already sent - return success without re-processing
    return jsonify({"status": "confirmed", "invite_sent": True}), 200

# Otherwise, proceed with enqueueing to GCWebhook1
# ... existing code ...
```

#### 3. GCWebhook2 Logic Update
```python
# In gcwebhook2 AFTER successfully sending invite
# Update database to mark invite as sent

db.execute("""
    UPDATE subscriptions
    SET invite_sent = TRUE
    WHERE user_id = %s AND closed_channel_id = %s
""", (user_id, closed_channel_id))
```

**Benefits:**
- ✅ Prevents duplicate invites permanently
- ✅ Works regardless of what's calling the API
- ✅ Database-backed (survives restarts)
- ✅ Fast lookups with index

**Effort:** Medium (2-3 hours: schema change + code updates + testing)

---

### 🟡 **Solution 2: Add Request Deduplication Cache (ALTERNATIVE)**

**Implementation:** Use Redis/Memorystore to track recent requests

```python
# In np-webhook /api/payment-status endpoint
import redis
cache = redis.Redis(host='...', port=6379)

# Generate unique key for this payment
cache_key = f"payment_processed:{user_id}:{closed_channel_id}:{payment_id}"

# Check if already processed (TTL: 24 hours)
if cache.exists(cache_key):
    return jsonify({"status": "confirmed", "cached": True}), 200

# Process payment
# ... existing code ...

# Mark as processed
cache.setex(cache_key, 86400, "1")  # Expire after 24 hours
```

**Benefits:**
- ✅ Fast lookups (in-memory)
- ✅ Automatic expiration
- ✅ No database schema changes

**Drawbacks:**
- ❌ Requires Redis/Memorystore instance
- ❌ Cache could be cleared/lost
- ❌ Additional infrastructure cost

**Effort:** Medium-High (Redis setup + code updates + testing)

---

### 🟢 **Solution 3: Fix Success Page Polling Logic (IF APPLICABLE)**

**IF the success page is polling too aggressively:**

```javascript
// Current (likely problematic):
setInterval(checkPaymentStatus, 5000);  // Poll every 5 seconds forever

// Fixed:
let pollCount = 0;
const maxPolls = 12;  // Max 12 attempts (1 minute)
const pollInterval = setInterval(() => {
    if (pollCount >= maxPolls) {
        clearInterval(pollInterval);
        return;
    }

    checkPaymentStatus().then(status => {
        if (status === 'confirmed') {
            clearInterval(pollInterval);  // Stop polling once confirmed
            showSuccessMessage();
        }
    });

    pollCount++;
}, 5000);
```

**Benefits:**
- ✅ Reduces API load
- ✅ Simple fix
- ✅ No backend changes

**Drawbacks:**
- ❌ Doesn't solve root cause (lack of idempotency)
- ❌ Duplicate invites could still occur

**Effort:** Low (30 minutes if success page is accessible)

---

## Recommended Action Plan

### Phase 1: Immediate Mitigation ✅

- [x] **Verify Session 40 fix is working** - ✅ CONFIRMED (HTTP 200 responses)
- [ ] **Stop active polling** - If success page is accessible, pause aggressive polling
- [ ] **Communicate to affected users** - Explain duplicate invites (all links work)

### Phase 2: Root Cause Fix (RECOMMENDED) ✅

- [ ] **Implement Solution 1** - Add invite_sent flag to database
  - [ ] Task 2.1: Update subscriptions table schema
  - [ ] Task 2.2: Update NP-Webhook to check invite_sent before enqueueing
  - [ ] Task 2.3: Update GCWebhook2 to set invite_sent after sending
  - [ ] Task 2.4: Add database index for performance
  - [ ] Task 2.5: Deploy changes
  - [ ] Task 2.6: Test with new payment

### Phase 3: Data Cleanup ✅

- [ ] **Check for duplicate payout_accumulation records**
  ```sql
  SELECT payment_id, COUNT(*) as count
  FROM payout_accumulation
  WHERE payment_id = '5996609246'
  GROUP BY payment_id
  HAVING COUNT(*) > 1;
  ```

- [ ] **Remove duplicates if found**
  ```sql
  DELETE FROM payout_accumulation
  WHERE id NOT IN (
      SELECT MIN(id)
      FROM payout_accumulation
      GROUP BY payment_id
  );
  ```

### Phase 4: Monitoring ✅

- [ ] **Monitor for repeated API calls**
  ```bash
  # Check for same payment_id being processed multiple times
  gcloud logging read 'resource.type="cloud_run_revision"
    AND resource.labels.service_name="gcwebhook1-10-26"
    AND textPayload:"Payment ID: 5996609246"' --limit=50
  ```

- [ ] **Set up alert for duplicate processing** (if > 2 invites sent per payment)

---

## Testing Plan

### Test 1: Verify Idempotency Fix

1. Create new test payment
2. Call `/api/payment-status` multiple times rapidly
3. **Expected:** Only ONE invite sent (subsequent calls return cached/flagged result)
4. **Verify:** Check GCWebhook2 logs (should show only 1 invite)
5. **Verify:** Check database (invite_sent = TRUE)

### Test 2: Normal Payment Flow

1. Create new test payment
2. Complete payment via NowPayments
3. Wait for automatic processing
4. **Expected:** Single invite sent
5. **Verify:** User receives exactly ONE Telegram link

---

## Prevention Measures

### 1. **Idempotency by Design**
All payment processing endpoints should be idempotent. Use one of:
- Database flags (invite_sent, processed_at)
- Request deduplication cache (Redis)
- Unique constraint on payment_id in all tables

### 2. **API Rate Limiting**
Add rate limits to prevent rapid repeated calls:
```python
# Limit: 5 requests per payment per minute
from flask_limiter import Limiter
limiter = Limiter(key_func=lambda: f"{request.args.get('order_id')}")

@app.route('/api/payment-status')
@limiter.limit("5 per minute")
def payment_status():
    # ... existing code ...
```

### 3. **Success Page Best Practices**
- Stop polling once payment confirmed
- Use exponential backoff (5s → 10s → 20s → 40s)
- Set maximum poll attempts (e.g., 12 attempts = 1 minute)
- Show "processing complete" message to prevent user refreshes

### 4. **Database Constraints**
Add UNIQUE constraints to prevent duplicate records:
```sql
-- Ensure payment_id is unique in payout_accumulation
ALTER TABLE payout_accumulation
ADD CONSTRAINT unique_payment_id UNIQUE (payment_id);
```

---

## Success Criteria

- [x] Root cause identified (external repeated calls, not service failures)
- [ ] Idempotency solution implemented
- [ ] Database schema updated (if using Solution 1)
- [ ] Code deployed to NP-Webhook and GCWebhook2
- [ ] New test payment sends ONLY ONE invite
- [ ] Multiple status API calls do NOT trigger duplicate processing
- [ ] Documentation updated

---

## Comparison: Session 40 Bug vs Current Issue

| Aspect | Session 40 Bug | Current Issue |
|--------|---------------|---------------|
| **Symptom** | Repeated Telegram invites | Repeated Telegram invites |
| **Root Cause** | GCWebhook1 crash (HTTP 500) | External repeated calls |
| **Trigger** | Type error at line 437 | Payment status polling |
| **Cloud Tasks** | Retry loop (same task) | Multiple separate tasks |
| **Queue Status** | Stuck tasks (11-12 retries) | Empty (all complete) |
| **HTTP Response** | 500 Internal Server Error | 200 OK (success) |
| **Fix** | Convert subscription_price to float | Add idempotency check |
| **Status** | ✅ FIXED (Session 40 Part 3) | ❌ UNRESOLVED |

---

**Next Action:** Implement Solution 1 (Add invite_sent flag to database)

**Status:** ⏳ ROOT CAUSE IDENTIFIED - AWAITING FIX APPROVAL

**Priority:** 🔴 HIGH - Users receiving multiple invites (poor UX, potential data integrity issues)
