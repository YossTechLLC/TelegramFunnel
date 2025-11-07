# NowPayments IPN "No Payment Record Found" Issue Analysis

**Date:** 2025-11-07
**Service:** np-webhook-10-26 (NowPayments IPN Handler)
**Issue:** IPN callback successfully received and validated, but database update fails causing payment processing to hang

---

## Executive Summary

The payment system is receiving IPN callbacks from NowPayments successfully, including signature verification, but is failing to process them due to a **missing pre-existing database record**. This causes a cascading failure where:
1. IPN callback returns HTTP 500
2. NowPayments retries indefinitely
3. `/api/payment-status` endpoint returns "No payment record found"
4. User is stuck on payment processing page
5. Payment confirmation never completes

**Root Cause:** The `np-webhook` service attempts to UPDATE an existing record in `private_channel_users_database`, but no record exists for this user/channel combination, likely because the payment was initiated via direct payment link without prior Telegram bot interaction.

---

## Payment Details

### From User's NowPayments API Response:
```json
{
  "payment_id": 4479119533,
  "invoice_id": 4910826526,
  "payment_status": "finished",
  "price_amount": 2.5,
  "price_currency": "usd",
  "pay_amount": 0.00076967,
  "actually_paid": 0.00076967,
  "pay_currency": "eth",
  "order_id": "PGP-6271402111|-1003253338212",
  "outcome_amount": 0.00061819,
  "outcome_currency": "eth",
  "payout_hash": "0x2b37662ad40a9db2b730e3a9ea02641cf1ae04d7c62e7fd9df89ca0aad1b2a70",
  "payin_hash": "0x00819d027e85c90208e6438522a67112030f8d949708bcd0d214015f248f795a",
  "created_at": "2025-11-07T11:48:27.355Z",
  "updated_at": "2025-11-07T11:51:20.364Z"
}
```

### Parsed Identifiers:
- **User ID:** 6271402111
- **Open Channel ID:** -1003253338212
- **Closed Channel ID:** -1003016667267 (successfully mapped)
- **Payment Status:** ✅ `finished` (at NowPayments)
- **Payment Status in DB:** ❌ No record found

---

## Technical Flow Analysis

### What's Working ✅

1. **IPN Callback Reception**
   - Timestamp: 2025-11-07 11:51:15 UTC (and multiple retry attempts)
   - Source IP: 169.254.169.126
   - Payload Size: 629 bytes

2. **Signature Verification**
   ```
   ✅ [IPN] Signature verified successfully
   ```
   - HMAC-SHA512 signature validation passes
   - Proves authenticity of NowPayments callback

3. **Order ID Parsing**
   ```
   ✅ [PARSE] New format detected
   User ID: 6271402111
   Open Channel ID: -1003253338212
   ```
   - New pipe-delimited format (`PGP-{user_id}|{open_channel_id}`) parsed correctly
   - Negative channel ID preserved

4. **Channel Mapping Lookup**
   ```
   ✅ [DATABASE] Found channel mapping:
   Open Channel ID (public): -1003253338212
   Closed Channel ID (private): -1003016667267
   ```
   - Mapping from `main_clients_database` retrieved successfully
   - Service correctly translates open → closed channel ID

### What's Failing ❌

5. **Database Record Update**
   ```
   ⚠️ [DATABASE] No records found to update
   User ID: 6271402111
   Private Channel ID: -1003016667267
   💡 [HINT] User may not have an active subscription record
   ```

6. **IPN Response**
   ```
   ⚠️ [IPN] Database update failed
   🔄 [IPN] Returning 500 - NowPayments will retry
   ```
   - Returns HTTP 500 to NowPayments
   - Triggers infinite retry loop (observed at 11:50:29, 11:51:15, 11:53:05)

7. **Landing Page API Status Check**
   ```
   🔍 [API] Looking up payment status for order_id: PGP-6271402111|-1003253338212
   ⚠️ [API] No payment record found
   ```
   - `/api/payment-status` endpoint cannot find record
   - Returns `"status": "pending"` indefinitely
   - User stuck on "Processing payment..." page

---

## Root Cause Analysis

### The UPDATE Query Problem

**Location:** `np-webhook-10-26/app.py` lines 359-401

```python
update_query = """
    UPDATE private_channel_users_database
    SET
        nowpayments_payment_id = %s,
        nowpayments_invoice_id = %s,
        ...
        payment_status = 'confirmed',
        ...
    WHERE user_id = %s AND private_channel_id = %s
    AND id = (
        SELECT id FROM private_channel_users_database
        WHERE user_id = %s AND private_channel_id = %s
        ORDER BY id DESC LIMIT 1
    )
"""
```

**Critical Issue:** This query requires a **pre-existing record** in `private_channel_users_database` to update. If no record exists, the UPDATE affects **0 rows** and returns `False`.

### Why No Record Exists

#### Scenario 1: Direct Payment Link (Most Likely)
User accessed payment URL directly without first initiating subscription via Telegram bot:

**Normal Flow:**
1. User interacts with Telegram bot → `/subscribe` command
2. Bot creates initial record in `private_channel_users_database` with `payment_status='pending'`
3. Bot generates NowPayments invoice and returns payment link
4. User pays
5. IPN callback updates existing record with payment details

**Broken Flow (What Happened):**
1. User accesses payment URL directly (e.g., via saved link, shared link, or bookmark)
2. No initial record created ❌
3. User completes payment
4. IPN callback attempts to update non-existent record → FAILS ❌

#### Scenario 2: Race Condition
Payment completed faster than database record creation:
- User initiated payment via bot
- Payment completed in <30 seconds (very fast blockchain confirmation)
- Initial DB record creation lagged or failed
- IPN arrived before record existed

#### Scenario 3: Channel Registration Issue
The channel `-1003253338212` (open) maps to `-1003016667267` (closed), but:
- Initial record may have been created with wrong channel ID
- OR record was created but for different user_id
- OR record exists in different table/schema

---

## Database Query to Verify

To confirm the issue, run these queries:

### 1. Check if ANY record exists for this user
```sql
SELECT id, user_id, private_channel_id, payment_status,
       nowpayments_payment_id, created_at
FROM private_channel_users_database
WHERE user_id = 6271402111
ORDER BY id DESC
LIMIT 10;
```

### 2. Check if record exists with OPEN channel ID (incorrect)
```sql
SELECT id, user_id, private_channel_id, payment_status
FROM private_channel_users_database
WHERE user_id = 6271402111
  AND private_channel_id = '-1003253338212'  -- OPEN channel ID
ORDER BY id DESC;
```

### 3. Check if record exists with CLOSED channel ID (correct)
```sql
SELECT id, user_id, private_channel_id, payment_status
FROM private_channel_users_database
WHERE user_id = 6271402111
  AND private_channel_id = '-1003016667267'  -- CLOSED channel ID
ORDER BY id DESC;
```

### 4. Verify channel mapping
```sql
SELECT open_channel_id, closed_channel_id,
       client_wallet_address, client_payout_currency
FROM main_clients_database
WHERE open_channel_id = '-1003253338212';
```

### Expected Results:
- **Query 1:** Should return 0 rows (no record for this user)
- **Query 2:** Might return 1 row if record was created with open_channel_id (BUG)
- **Query 3:** Should return 0 rows (confirms missing record)
- **Query 4:** Should return 1 row with `closed_channel_id = '-1003016667267'` ✅

---

## Architectural Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     NOWPAYMENTS IPN FLOW                             │
└─────────────────────────────────────────────────────────────────────┘

1. NowPayments Sends IPN Callback
   ↓
   POST https://np-webhook-10-26.../
   {
     "payment_id": 4479119533,
     "order_id": "PGP-6271402111|-1003253338212",
     "payment_status": "finished",
     ...
   }

2. np-webhook Validates Signature
   ↓
   HMAC-SHA512 verification
   ✅ SUCCESS

3. Parse order_id
   ↓
   user_id = 6271402111
   open_channel_id = -1003253338212

4. Look up closed_channel_id
   ↓
   Query: main_clients_database
   WHERE open_channel_id = '-1003253338212'
   ✅ Returns: closed_channel_id = '-1003016667267'

5. UPDATE private_channel_users_database
   ↓
   Query:
   UPDATE private_channel_users_database
   SET payment_status='confirmed', nowpayments_payment_id=4479119533, ...
   WHERE user_id=6271402111 AND private_channel_id='-1003016667267'
   ❌ FAILS: 0 rows updated (no existing record)

6. Return HTTP 500 to NowPayments
   ↓
   NowPayments retries indefinitely (11:50, 11:51, 11:53...)

┌─────────────────────────────────────────────────────────────────────┐
│                  LANDING PAGE STATUS CHECK                           │
└─────────────────────────────────────────────────────────────────────┘

1. User's Browser Polls Status Every 5 Seconds
   ↓
   GET /api/payment-status?order_id=PGP-6271402111|-1003253338212

2. np-webhook Looks Up Payment Record
   ↓
   Query: private_channel_users_database
   WHERE user_id=6271402111 AND private_channel_id='-1003016667267'
   ❌ Returns: 0 rows

3. Return "pending" Status
   ↓
   Response: {"status": "pending", "message": "Payment record not found"}

4. User Stuck on "Processing..." Page
   ↓
   Infinite polling, never progresses
```

---

## Why This Causes Complete Failure

### 1. Payment Confirmed at NowPayments ✅
- Payment successfully completed
- Funds transferred
- Transaction hashes recorded
- `payment_status = "finished"`

### 2. But Internal System Stuck ❌
- `private_channel_users_database` has NO record
- `payment_status` never set to `'confirmed'`
- Landing page never receives confirmation
- User never receives Telegram invite
- Payment split to client wallet never triggered

### 3. Infinite Retry Loop
```
11:50:29 → IPN callback → 500 error → NowPayments retries
11:51:15 → IPN callback → 500 error → NowPayments retries
11:53:05 → IPN callback → 500 error → NowPayments retries
...continues indefinitely...
```

### 4. User Experience
```
[User Browser]
11:48:27 → User completes payment
11:48:30 → Redirected to payment-processing.html
11:48:35 → Polling starts: "Processing your payment..."
11:49:00 → Still processing...
11:50:00 → Still processing...
11:51:00 → Still processing...
12:01:00 → Still processing... ❌ User frustrated
```

---

## Proposed Solutions

### Solution 1: INSERT or UPDATE (UPSERT) Strategy ⭐ **RECOMMENDED**

**Modify:** `np-webhook-10-26/app.py` lines 359-401

**Change from UPDATE to UPSERT:**
```python
upsert_query = """
    INSERT INTO private_channel_users_database (
        user_id,
        private_channel_id,
        nowpayments_payment_id,
        nowpayments_invoice_id,
        nowpayments_order_id,
        nowpayments_pay_address,
        nowpayments_payment_status,
        nowpayments_pay_amount,
        nowpayments_pay_currency,
        nowpayments_outcome_amount,
        nowpayments_price_amount,
        nowpayments_price_currency,
        nowpayments_outcome_currency,
        payment_status,
        nowpayments_created_at,
        nowpayments_updated_at
    )
    VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'confirmed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )
    ON CONFLICT (user_id, private_channel_id)
    DO UPDATE SET
        nowpayments_payment_id = EXCLUDED.nowpayments_payment_id,
        nowpayments_invoice_id = EXCLUDED.nowpayments_invoice_id,
        nowpayments_order_id = EXCLUDED.nowpayments_order_id,
        nowpayments_pay_address = EXCLUDED.nowpayments_pay_address,
        nowpayments_payment_status = EXCLUDED.nowpayments_payment_status,
        nowpayments_pay_amount = EXCLUDED.nowpayments_pay_amount,
        nowpayments_pay_currency = EXCLUDED.nowpayments_pay_currency,
        nowpayments_outcome_amount = EXCLUDED.nowpayments_outcome_amount,
        nowpayments_price_amount = EXCLUDED.nowpayments_price_amount,
        nowpayments_price_currency = EXCLUDED.nowpayments_price_currency,
        nowpayments_outcome_currency = EXCLUDED.nowpayments_outcome_currency,
        payment_status = 'confirmed',
        nowpayments_updated_at = CURRENT_TIMESTAMP
"""
```

**Benefits:**
- ✅ Works for both first-time payments AND updates to existing records
- ✅ Handles direct payment links
- ✅ Handles race conditions
- ✅ Idempotent (safe to retry)
- ✅ Minimal code changes

**Requirements:**
- Must have UNIQUE constraint on `(user_id, private_channel_id)` in `private_channel_users_database`
- OR use `ON CONFLICT (id)` if updating specific row

---

### Solution 2: Pre-populate Required Fields from main_clients_database

**Problem with Solution 1:** UPSERT may not populate all required fields (e.g., `sub_time`, `sub_price`, `wallet_address`, etc.)

**Enhanced UPSERT:**
```python
# Step 1: Get subscription details from main_clients_database
cur.execute("""
    SELECT
        client_wallet_address,
        client_payout_currency::text,
        client_payout_network::text
    FROM main_clients_database
    WHERE closed_channel_id = %s
""", (closed_channel_id,))

client_data = cur.fetchone()
if not client_data:
    print(f"❌ [DATABASE] No client configuration found for channel {closed_channel_id}")
    return False

wallet_address, payout_currency, payout_network = client_data

# Step 2: UPSERT with all required fields
upsert_query = """
    INSERT INTO private_channel_users_database (
        user_id,
        private_channel_id,
        client_wallet_address,
        client_payout_currency,
        client_payout_network,
        sub_time,
        sub_price,
        nowpayments_payment_id,
        nowpayments_invoice_id,
        ...
        payment_status
    )
    VALUES (
        %s, %s, %s, %s, %s,
        30,  -- Default subscription time (30 days)
        %s,  -- price_amount from IPN
        %s, %s, ...,
        'confirmed'
    )
    ON CONFLICT (user_id, private_channel_id)
    DO UPDATE SET
        nowpayments_payment_id = EXCLUDED.nowpayments_payment_id,
        ...
"""
```

**Benefits:**
- ✅ Populates ALL required fields even for direct payments
- ✅ Subscription can proceed to GCWebhook1 → GCSplit1 flow
- ✅ User receives Telegram invite
- ✅ Payment split to client wallet occurs

---

### Solution 3: Two-Pass Strategy (CHECK then INSERT/UPDATE)

**Modify:** `np-webhook-10-26/app.py`

```python
# Step 1: Check if record exists
cur.execute("""
    SELECT id FROM private_channel_users_database
    WHERE user_id = %s AND private_channel_id = %s
""", (user_id, closed_channel_id))

existing_record = cur.fetchone()

if existing_record:
    # Record exists → UPDATE
    cur.execute("""
        UPDATE private_channel_users_database
        SET nowpayments_payment_id = %s, ...
        WHERE user_id = %s AND private_channel_id = %s
    """, (..., user_id, closed_channel_id))
else:
    # No record → INSERT with defaults
    cur.execute("""
        INSERT INTO private_channel_users_database (
            user_id, private_channel_id, payment_status, ...
        ) VALUES (%s, %s, 'confirmed', ...)
    """, (user_id, closed_channel_id, ...))
```

**Benefits:**
- ✅ Clear logic flow (easier to debug)
- ✅ Handles both scenarios explicitly

**Drawbacks:**
- ❌ Two queries (potential race condition)
- ❌ More code to maintain

---

### Solution 4: Enforce Bot-First Flow (Prevention)

**Change:** Require all payments to originate from Telegram bot

**Implementation:**
1. Make payment links single-use with expiration
2. Generate unique tokens for each payment link
3. Validate token in `np-webhook` before processing IPN
4. Reject direct/replayed payment links

**Benefits:**
- ✅ Ensures proper flow initialization
- ✅ Better security (prevents link sharing)

**Drawbacks:**
- ❌ Complex to implement
- ❌ Breaks user convenience (can't bookmark/share links)
- ❌ Doesn't solve underlying architectural issue

---

## Immediate Workaround (Manual Fix for This Payment)

To unblock the current user's payment:

### Step 1: Manually Insert Record
```sql
INSERT INTO private_channel_users_database (
    user_id,
    private_channel_id,
    client_wallet_address,
    client_payout_currency,
    client_payout_network,
    sub_time,
    sub_price,
    nowpayments_payment_id,
    nowpayments_invoice_id,
    nowpayments_order_id,
    nowpayments_pay_address,
    nowpayments_payment_status,
    nowpayments_pay_amount,
    nowpayments_pay_currency,
    nowpayments_outcome_amount,
    nowpayments_price_amount,
    nowpayments_price_currency,
    nowpayments_outcome_currency,
    payment_status,
    nowpayments_created_at,
    nowpayments_updated_at
)
SELECT
    6271402111,  -- user_id
    closed_channel_id,  -- from main_clients_database
    client_wallet_address,
    client_payout_currency,
    client_payout_network,
    30,  -- Default 30 days subscription
    2.50,  -- From NowPayments response
    4479119533,  -- payment_id
    4910826526,  -- invoice_id
    'PGP-6271402111|-1003253338212',  -- order_id
    '0xD031Cb94c419A5D7AA4BA5FDBc9Cc82138651083',  -- pay_address
    'finished',  -- payment_status (from NowPayments)
    0.00076967,  -- pay_amount
    'eth',  -- pay_currency
    0.00061819,  -- outcome_amount
    2.50,  -- price_amount
    'usd',  -- price_currency
    'eth',  -- outcome_currency
    'confirmed',  -- payment_status (internal)
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM main_clients_database
WHERE closed_channel_id = '-1003016667267';
```

### Step 2: Verify Record Created
```sql
SELECT * FROM private_channel_users_database
WHERE user_id = 6271402111 AND private_channel_id = '-1003016667267';
```

### Step 3: Trigger Processing Manually
Once record exists, next IPN retry from NowPayments will:
1. Find existing record ✅
2. Update it successfully ✅
3. Return HTTP 200 to NowPayments ✅
4. Enqueue to GCWebhook1 for payment orchestration ✅
5. User receives Telegram invite ✅

OR manually trigger GCWebhook1:
```bash
curl -X POST "https://gcwebhook1-10-26-.../process-validated-payment" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 6271402111,
    "closed_channel_id": "-1003016667267",
    "wallet_address": "<from main_clients_database>",
    "payout_currency": "<from main_clients_database>",
    "payout_network": "<from main_clients_database>",
    "subscription_time_days": 30,
    "subscription_price": "2.50",
    "outcome_amount_usd": 2.50,
    "nowpayments_payment_id": 4479119533,
    "nowpayments_pay_address": "0xD031Cb94c419A5D7AA4BA5FDBc9Cc82138651083",
    "nowpayments_outcome_amount": 0.00061819
  }'
```

---

## Long-Term Recommendations

### 1. **Implement UPSERT in np-webhook** ⭐
- **Priority:** HIGH
- **Effort:** Low (1-2 hours)
- **Impact:** Fixes root cause for all future occurrences

### 2. **Add Logging for Missing Records**
- Log user_id + closed_channel_id when no record found
- Alert on repeated missing records (indicates systemic issue)

### 3. **Add Database Constraints**
```sql
-- Ensure idempotency for UPSERT
ALTER TABLE private_channel_users_database
ADD CONSTRAINT unique_user_channel UNIQUE (user_id, private_channel_id);
```

### 4. **Implement Retry Logic in Landing Page**
- If payment status remains "pending" for >5 minutes
- Show user-friendly message: "Payment confirmed but processing delayed"
- Provide support contact option

### 5. **Add Monitoring & Alerts**
- Alert when IPN returns 500 more than 3 times for same payment_id
- Alert when `/api/payment-status` called >50 times for same order_id
- Dashboard showing "stuck payments" (pending >10 minutes)

### 6. **Create Payment Reconciliation Script**
- Cron job queries NowPayments API for `"payment_status": "finished"`
- Compares against `private_channel_users_database`
- Auto-creates missing records
- Triggers manual processing

---

## Testing Plan

After implementing UPSERT solution:

### Test Case 1: Direct Payment Link (No Pre-existing Record)
1. Delete any records for test user in `private_channel_users_database`
2. Generate payment link via NowPayments dashboard
3. Complete payment
4. Verify IPN creates new record ✅
5. Verify status API returns `"confirmed"` ✅
6. Verify GCWebhook1 processing triggered ✅

### Test Case 2: Normal Bot Flow (Pre-existing Record)
1. Initiate payment via Telegram bot
2. Verify initial record created with `payment_status='pending'`
3. Complete payment
4. Verify IPN updates existing record ✅
5. Verify no duplicate records created ✅

### Test Case 3: Retry Idempotency
1. Complete payment
2. Manually trigger IPN callback 5 times
3. Verify no duplicate records ✅
4. Verify payment_id remains correct ✅

### Test Case 4: Race Condition
1. Create payment link
2. Initiate payment
3. Immediately delete initial record (simulate race)
4. Complete payment
5. Verify IPN creates record successfully ✅

---

## Conclusion

The issue is **100% caused by missing pre-existing database records** when IPN callbacks arrive. The system architecture assumes records always exist before payment, but this assumption breaks for:
- Direct payment links
- Very fast payments (race conditions)
- Link sharing/bookmarking

**Recommended Solution:** Implement UPSERT strategy in `np-webhook-10-26/app.py` to handle both INSERT (new records) and UPDATE (existing records) scenarios gracefully.

**Immediate Action:** Manually insert the record for payment_id=4479119533 to unblock the current user, then implement UPSERT to prevent future occurrences.

---

## Files Requiring Changes

1. **`/OCTOBER/10-26/np-webhook-10-26/app.py`**
   - Lines 290-441: `update_payment_data()` function
   - Change UPDATE to UPSERT

2. **Database Migration**
   - Add UNIQUE constraint: `(user_id, private_channel_id)`

3. **`/OCTOBER/10-26/PROGRESS.md` & `/OCTOBER/10-26/DECISIONS.md`**
   - Document UPSERT strategy decision
   - Record fix for production issue

---

## Related Architecture Documents

- `MAIN_ARCHITECTURE_INSTANT_PAYOUT.md` - Documents full instant payout flow including np-webhook role
- `MAIN_ARCHITECTURE_THRESHOLD_PAYOUT.md` - Documents threshold payout flow
- `NOWPAYMENTS_INTEGRATION_GUIDE.md` (if exists) - NowPayments integration details
- `DATABASE_SCHEMA.md` (if exists) - Database schema documentation

---

**Document Version:** 1.0
**Last Updated:** 2025-11-07 12:15 UTC
**Status:** Investigation Complete - Awaiting Fix Implementation
