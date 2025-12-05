# Duplicate Telegram Invite Investigation Report

**Date:** 2025-11-14
**Incident:** User received 3 separate one-time invitation links for 1 payment
**Severity:** HIGH - Security/UX issue (users can invite multiple people with one payment)

---

## Executive Summary

User completed 1 payment and received **3 different one-time Telegram invitation links**. Investigation revealed that **GCWebhook1 lacks idempotency protection**, allowing it to process the same payment multiple times if called repeatedly by np-webhook.

---

## Evidence from Logs

### GCWebhook2 Logs (21:45-21:46 UTC)

**3 Separate Requests Received:**

1. **Request 1** (21:45:24):
   - Payment ID: `1763148537`
   - User: `6271402111`
   - Channel: `-1003111266231`
   - Invite Link: `https://t.me/+qIYW7Qsh295iY2Ex`
   - Status: ✅ Sent

2. **Request 2** (21:46:00):
   - Payment ID: `1763147598` ← **Different payment_id!**
   - User: `6271402111` (same user)
   - Channel: `-1003111266231` (same channel)
   - Invite Link: `https://t.me/+Qx-u-VYJ1qlmZjhh`
   - Status: ✅ Sent

3. **Request 3** (21:46:13):
   - Payment ID: `1763148344` ← **Different payment_id!**
   - User: `6271402111` (same user)
   - Channel: `-1003111266231` (same channel)
   - Invite Link: `https://t.me/+NhOtlsDgkRcwN2Vh`
   - Status: ✅ Sent

**Observation:**
- All 3 requests had **different payment_ids** but the **same user and channel**
- Each request passed idempotency checks in GCWebhook2 (because different payment_ids)
- Each created a unique one-time invite link

---

## Root Cause Analysis

###  1. **GCWebhook1 Missing Idempotency Check**

**Current Flow:**
```
np-webhook calls /process-validated-payment
  ↓
GCWebhook1 receives request
  ↓
NO CHECK if payment already processed ❌
  ↓
Creates Cloud Task for GCSplit1
  ↓
Creates Cloud Task for GCWebhook2
  ↓
Marks payment as processed (too late!)
```

**Problem:**
- GCWebhook1 only MARKS payment as processed at the end (line 490)
- GCWebhook1 does NOT CHECK if payment was already processed at the beginning
- If np-webhook retries or sends duplicate requests, GCWebhook1 processes each one

### 2. **Why Are There 3 Different Payment IDs?**

**Hypothesis 1:** np-webhook is generating timestamp-based payment_ids instead of using NowPayments payment_id
- Need to verify np-webhook code

**Hypothesis 2:** np-webhook is being called 3 times by NowPayments IPN
- Need to check NowPayments IPN logs

**Hypothesis 3:** There are actually 3 separate payments in the database
- Need to query database

---

## Impact Assessment

### Security Impact: **HIGH**
- Users can potentially invite multiple people with one payment
- Each one-time link grants access to the premium channel
- Violates subscription model (1 payment = 1 access)

### UX Impact: **MEDIUM**
- Users confused by receiving multiple links
- Users don't know which link to use
- Creates support burden

### Financial Impact: **MEDIUM**
- Channel owner loses revenue (3 people get access for 1 payment)
- Devalues subscription offering

---

## Solution

### Fix 1: Add Idempotency Check to GCWebhook1 (CRITICAL)

**Implementation:**
Add idempotency check at the BEGINNING of `/process-validated-payment`:

```python
@app.route("/process-validated-payment", methods=["POST"])
def process_validated_payment():
    try:
        print(f"🎯 [VALIDATED] Received validated payment from NP-Webhook")

        payment_data = request.get_json()
        nowpayments_payment_id = payment_data.get('nowpayments_payment_id')

        # ================================================================
        # IDEMPOTENCY CHECK: Verify payment not already processed
        # ================================================================
        print(f"🔍 [IDEMPOTENCY] Checking if payment {nowpayments_payment_id} already processed...")

        conn = db_manager.get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT gcwebhook1_processed, gcwebhook1_processed_at
                FROM processed_payments
                WHERE payment_id = %s
            """, (nowpayments_payment_id,))
            existing = cur.fetchone()
            cur.close()
            conn.close()

            if existing and existing[0]:  # gcwebhook1_processed is True
                processed_at = existing[1]
                print(f"✅ [IDEMPOTENCY] Payment already processed at {processed_at}")
                print(f"🎉 [IDEMPOTENCY] Returning success (no duplicate processing)")
                return jsonify({
                    "status": "success",
                    "message": "Payment already processed",
                    "payment_id": nowpayments_payment_id,
                    "processed_at": str(processed_at)
                }), 200

        print(f"🆕 [IDEMPOTENCY] Payment not yet processed - proceeding...")

        # ... rest of processing logic ...
```

**Benefits:**
- Prevents duplicate processing
- Returns success immediately if already processed
- Compatible with np-webhook retries
- No side effects on subsequent calls

### Fix 2: Investigate np-webhook Payment ID Generation

**Action Items:**
1. Review np-webhook code to verify it's using NowPayments payment_id
2. Check if np-webhook is generating timestamp-based IDs
3. Verify database has correct payment_id values

---

## Testing Plan

### Test 1: Idempotency Protection
1. Complete a test payment
2. Manually call `/process-validated-payment` 3 times with same payment_id
3. Verify only 1 Cloud Task created
4. Verify only 1 Telegram invite sent
5. Verify subsequent calls return "already processed"

### Test 2: np-webhook Retry Behavior
1. Trigger np-webhook IPN callback
2. Monitor if np-webhook retries on failure
3. Verify GCWebhook1 handles retries gracefully

### Test 3: End-to-End Payment Flow
1. Complete real payment
2. Verify user receives exactly 1 invitation link
3. Verify database shows correct processing state

---

## Deployment Checklist

- [ ] Add idempotency check to GCWebhook1 `/process-validated-payment`
- [ ] Test locally with multiple calls to same payment_id
- [ ] Build and deploy GCWebhook1
- [ ] Monitor logs for idempotency messages
- [ ] Verify no duplicate invites in production
- [ ] Update PROGRESS.md and DECISIONS.md

---

## Related Files

- `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py` (needs idempotency check)
- `/OCTOBER/10-26/GCWebhook2-10-26/tph2-10-26.py` (already has idempotency)
- `/OCTOBER/10-26/np-webhook-10-26/app.py` (may need review)

---

## Conclusion

The duplicate invite issue is caused by **missing idempotency protection in GCWebhook1**. The fix is straightforward: add a check at the beginning of `/process-validated-payment` to return early if the payment was already processed. This will prevent duplicate Cloud Tasks and duplicate invitations.

**Priority:** HIGH
**Fix Complexity:** LOW (< 30 lines of code)
**Risk:** LOW (graceful early return, no breaking changes)
