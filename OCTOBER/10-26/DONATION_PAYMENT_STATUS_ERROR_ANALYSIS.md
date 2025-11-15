# Donation "No Payment Record Found" Error - Root Cause Analysis

**Date:** 2025-11-15
**Status:** 🔍 **ROOT CAUSE IDENTIFIED - NO CODE CHANGES YET**

---

## ERROR SYMPTOMS

### **User-Reported Error:**

```
2025-11-15 00:44:19.866 EST
🔍 [API] Looking up payment status for order_id: PGP-8361239852|-1003377958897

2025-11-15 00:44:19.866 EST
✅ [PARSE] New format detected
User ID: 8361239852
Open Channel ID: -1003377958897

2025-11-15 00:44:19.920 EST
🔗 [DATABASE] Connection established

2025-11-15 00:44:19.926 EST
✅ [API] Found closed_channel_id: -1003185255259

2025-11-15 00:44:19.931 EST
⚠️ [API] No payment record found
```

---

## ROOT CAUSE ANALYSIS

### **The Problem:**

**Donations DO NOT create database records when invoice is created.**

Unlike subscriptions, the donation flow ONLY creates a NowPayments invoice but does NOT insert a pending record into `private_channel_users_database`.

### **What Happens:**

```
SUBSCRIPTION FLOW (Works correctly):
1. User clicks subscription tier
2. Bot creates invoice via NowPayments
3. ✅ Bot ALSO creates pending database record in private_channel_users_database
4. User pays
5. IPN callback arrives
6. np-webhook UPDATES existing record (changes payment_status from 'pending' to 'confirmed')
7. Landing page polls /api/payment-status
8. ✅ Record found with payment_status='confirmed'
9. User sees "Payment Confirmed!"

DONATION FLOW (Broken):
1. User clicks "Donate to Support This Channel"
2. Bot creates invoice via NowPayments
3. ❌ Bot DOES NOT create database record
4. User pays
5. IPN callback arrives
6. np-webhook tries to UPDATE record (lines 391-422 in app.py)
7. ❌ No existing record found (lines 391-397)
8. np-webhook creates NEW record with payment_status='confirmed' (lines 443-505)
9. Landing page polls /api/payment-status DURING payment (before IPN)
10. ❌ Record not found yet (IPN hasn't arrived)
11. Landing page shows "Payment pending..." forever
12. Eventually IPN arrives and creates record
13. But user has already left the page
```

---

## CODE EVIDENCE

### **Donation Flow - No Database Insert:**

**File:** `TelePay10-26/services/payment_service.py` (Lines 263-340)

```python
async def create_donation_invoice(
    self,
    user_id: int,
    amount: float,
    order_id: str,
    description: str,
    donation_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create payment invoice for donation with optional encrypted message.
    """
    # Build success URL
    landing_page_base_url = "https://storage.googleapis.com/paygateprime-static/payment-processing.html"
    success_url = f"{landing_page_base_url}?order_id={quote(order_id, safe='')}"

    # Add encrypted message if provided
    if donation_message:
        encrypted_msg = encrypt_donation_message(donation_message)
        success_url += f"&msg={quote(encrypted_msg, safe='')}"

    # Call NowPayments API to create invoice
    result = await self.create_invoice(
        user_id=user_id,
        amount=amount,
        success_url=success_url,
        order_id=order_id,
        description=description
    )

    return result
    # ❌ NO DATABASE INSERT - Only creates invoice at NowPayments
```

**What's missing:**
- No `INSERT INTO private_channel_users_database` with `payment_status='pending'`
- No placeholder record for the donation
- Landing page has nothing to poll until IPN arrives

---

### **Subscription Flow - Creates Pending Record:**

**File:** `TelePay10-26/start_np_gateway.py` (Reference - working code)

```python
# After creating invoice, ALSO create database record:
async with get_db_connection() as conn:
    async with conn.cursor() as cur:
        await cur.execute("""
            INSERT INTO private_channel_users_database (
                user_id,
                private_channel_id,
                sub_time,
                sub_price,
                payment_status,  # ✅ Set to 'pending'
                nowpayments_order_id,
                is_active,
                timestamp,
                datestamp,
                expire_time,
                expire_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            closed_channel_id,
            sub_time,
            sub_price,
            'pending',  # ✅ Pending status allows landing page to poll
            order_id,
            False,  # Not active until payment confirmed
            timestamp,
            datestamp,
            expire_time,
            expire_date
        ))
        await conn.commit()

# ✅ Record exists immediately
# Landing page can poll and see payment_status='pending'
# When IPN arrives, status updates to 'confirmed'
```

---

### **np-webhook Payment Status API - Expects Record to Exist:**

**File:** `np-webhook-10-26/app.py` (Lines 1207-1232)

```python
# Query payment_status from private_channel_users_database
cur.execute("""
    SELECT payment_status, nowpayments_payment_id, nowpayments_payment_status
    FROM private_channel_users_database
    WHERE user_id = %s AND private_channel_id = %s
    ORDER BY id DESC LIMIT 1
""", (user_id, closed_channel_id))

payment_record = cur.fetchone()

if not payment_record:
    # ❌ THIS IS THE ERROR WE'RE SEEING
    print(f"⚠️ [API] No payment record found")
    print(f"   User ID: {user_id}")
    print(f"   Private Channel ID: {closed_channel_id}")
    return jsonify({
        "status": "pending",
        "message": "Payment record not found - still pending",
        "data": {
            "order_id": order_id,
            "payment_status": "pending",
            "confirmed": False
        }
    }), 200
```

**Why this fails for donations:**
- Donation invoice created but NO database record
- Landing page polls immediately after user pays
- Record doesn't exist yet (IPN hasn't arrived)
- User sees "pending" forever
- Eventually IPN creates record, but user has left

---

## TIMING DIAGRAM

### **Subscription Flow (Correct):**

```
Time 0s:  User clicks tier → Invoice created + DB record inserted (payment_status='pending')
         ↓
Time 5s:  User redirected to NowPayments
         ↓
Time 30s: User completes payment
         ↓
Time 31s: NowPayments redirects to landing page
         ↓
Time 31s: Landing page starts polling /api/payment-status
         ↓
Time 32s: Poll #1 → Record found (payment_status='pending')
         ↓
Time 33s: Poll #2 → Record found (payment_status='pending')
         ↓
Time 34s: IPN arrives at np-webhook
         ↓
Time 35s: np-webhook UPDATES record (payment_status='confirmed')
         ↓
Time 36s: Poll #3 → Record found (payment_status='confirmed') ✅
         ↓
Time 36s: Landing page shows "Payment Confirmed!" ✅
```

---

### **Donation Flow (Broken):**

```
Time 0s:  User clicks donate → Invoice created (❌ NO DB record)
         ↓
Time 5s:  User redirected to NowPayments
         ↓
Time 30s: User completes payment
         ↓
Time 31s: NowPayments redirects to landing page
         ↓
Time 31s: Landing page starts polling /api/payment-status
         ↓
Time 32s: Poll #1 → ❌ No record found (returns "pending")
         ↓
Time 33s: Poll #2 → ❌ No record found (returns "pending")
         ↓
Time 34s: IPN arrives at np-webhook
         ↓
Time 35s: np-webhook INSERTS new record (payment_status='confirmed')
         ↓
Time 36s: Poll #3 → ✅ Record found (payment_status='confirmed')
         ↓
Time 36s: Landing page shows "Payment Confirmed!" ✅

BUT: User likely sees "pending" for 5+ seconds and may leave before confirmation
```

---

## WHY THIS IS A PROBLEM

### **1. Poor User Experience**

- User pays successfully
- Landing page shows "Processing..." for 5-10+ seconds
- User thinks payment failed
- User leaves before seeing confirmation

### **2. Race Condition**

- Landing page polls immediately
- IPN callback may take 5-30 seconds to arrive
- During this window, landing page sees "No record found"
- Unreliable confirmation flow

### **3. Inconsistent Architecture**

- Subscription flow: Creates pending record immediately ✅
- Donation flow: Waits for IPN to create record ❌
- Different behavior for similar payment flows

---

## THE FIX (NOT IMPLEMENTED YET)

### **Solution: Create Pending Database Record for Donations**

We need to modify the donation flow to match the subscription flow:

**Step 1:** After creating invoice, INSERT pending record into database
**Step 2:** When IPN arrives, UPDATE existing record (same as subscriptions)

### **Where to Add Database Insert:**

**File:** `TelePay10-26/bot/conversations/donation_conversation.py`

**Function:** `finalize_payment()` (around line 490-520)

**After invoice creation:**

```python
# Create invoice with encrypted message in success_url
result = await payment_service.create_donation_invoice(...)

if result['success']:
    invoice_url = result['invoice_url']

    # ✅ NEW: Insert pending record into database
    # This allows landing page to poll immediately
    try:
        # Get database connection from application
        db_manager = context.application.bot_data.get('db_manager')

        if db_manager:
            # Insert pending donation record
            await db_manager.insert_pending_donation(
                user_id=user.id,
                open_channel_id=open_channel_id,
                closed_channel_id=closed_channel_id,  # Need to look this up first
                amount=amount_float,
                order_id=order_id,
                donation_message=donation_message
            )
            logger.info(f"✅ [DONATION] Pending record created in database")
        else:
            logger.warning(f"⚠️ [DONATION] Database manager not available - record not created")
            logger.warning(f"   Landing page will show 'pending' until IPN arrives")

    except Exception as e:
        logger.error(f"❌ [DONATION] Failed to create pending record: {e}")
        # Continue anyway - IPN will create record later

    # Send WebApp button...
```

---

### **What Needs to Be Added:**

**1. Lookup `closed_channel_id`:**
```python
# Query main_clients_database to get closed_channel_id from open_channel_id
SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s
```

**2. Insert Pending Record:**
```python
INSERT INTO private_channel_users_database (
    user_id,
    private_channel_id,
    sub_time,
    sub_price,
    payment_status,  # 'pending'
    nowpayments_order_id,
    is_active,
    timestamp,
    datestamp
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
```

**3. When IPN Arrives:**
- np-webhook finds existing record (lines 391-397)
- Updates it with payment_id and payment_status='confirmed' (lines 403-422)
- Same as subscription flow ✅

---

## BENEFITS OF THE FIX

### **1. Consistent User Experience**

- Donation and subscription flows behave identically
- Landing page always finds a record to poll
- User sees status update in real-time

### **2. No Race Condition**

- Record exists immediately (payment_status='pending')
- Landing page can poll and show "Processing payment..."
- When IPN arrives, status updates to 'confirmed'
- User sees smooth transition

### **3. Better Debugging**

- Can track donation attempts even if payment fails
- All donations have database records
- Easier to troubleshoot payment issues

---

## ALTERNATIVE SOLUTIONS CONSIDERED

### **Option 1: Delay Landing Page Polling**

❌ **Rejected:** Still creates race condition, just delays it

### **Option 2: Poll NowPayments API Directly**

❌ **Rejected:**
- Rate limiting concerns
- Additional API calls cost money
- IPN is the source of truth

### **Option 3: Create Pending Record (RECOMMENDED)**

✅ **Accepted:**
- Matches proven subscription flow pattern
- Consistent architecture
- Best user experience
- No race conditions

---

## IMPLEMENTATION PLAN (NOT STARTED)

### **Step 1: Create Database Manager Method**

**File:** `TelePay10-26/models/connection_pool.py` or new `donation_database_manager.py`

```python
async def insert_pending_donation(
    self,
    user_id: int,
    open_channel_id: str,
    closed_channel_id: str,
    amount: float,
    order_id: str,
    donation_message: Optional[str] = None
):
    """
    Insert pending donation record into private_channel_users_database.

    This allows landing page to poll for payment status immediately,
    matching the subscription flow architecture.
    """
    pass  # Implementation needed
```

---

### **Step 2: Lookup closed_channel_id in finalize_payment()**

Before inserting pending record, need to look up closed_channel_id:

```python
# Query main_clients_database
SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s
```

---

### **Step 3: Insert Pending Record After Invoice Creation**

In `finalize_payment()` after `result = await payment_service.create_donation_invoice(...)`:

```python
if result['success']:
    # Look up closed_channel_id
    # Insert pending record
    # Then send WebApp button
```

---

### **Step 4: Test Both Flows**

1. Test donation WITHOUT message - verify pending record created
2. Test donation WITH message - verify pending record created
3. Verify IPN updates existing record (not creates new one)
4. Verify landing page finds record immediately

---

## RISKS

### **Implementation Risk:** 🟡 **MEDIUM**

**Concerns:**
- Need database connection in bot conversation handler
- Database schema must support donations (it does - same table as subscriptions)
- Need to handle closed_channel_id lookup failure

**Mitigation:**
- Add try/except around database insert
- If insert fails, continue anyway (IPN will create record later)
- Log warnings so we can monitor failures

---

### **Rollback Risk:** 🟢 **LOW**

**If issues occur:**
- Remove database insert code
- Behavior reverts to current (IPN creates record)
- No database schema changes needed

---

## QUESTIONS TO ANSWER BEFORE IMPLEMENTATION

### **1. How is closed_channel_id determined?**

For subscriptions, the closed_channel_id is known from the button callback.

For donations:
- order_id format: `PGP-{user_id}|{open_channel_id}`
- We have open_channel_id
- Need to query `main_clients_database` to get closed_channel_id
- What if mapping doesn't exist? (Should exist if donation button was shown)

---

### **2. What should sub_time and sub_price be for donations?**

Donations are NOT subscriptions, but they use the same table.

**Option A:** Use dummy values
- `sub_time = 0` (not a subscription)
- `sub_price = amount` (donation amount)

**Option B:** Leave NULL
- `sub_time = NULL`
- `sub_price = NULL`

**Recommendation:** Use Option A (matches current IPN behavior - see line 484)

---

### **3. Should donations grant channel access?**

Current IPN handler sets:
- `is_active = True`
- `expire_date = 30 days from now`

This means donations GRANT 30-day access to private channel.

**Is this intentional?**
- If YES: Keep current behavior
- If NO: Need to change IPN handler to NOT grant access for donations

**Need user clarification on intended behavior.**

---

## SUMMARY

**Root Cause:**
- Donation flow does NOT create pending database record
- Landing page polls for record that doesn't exist yet
- Record only created when IPN arrives (5-30 seconds later)
- User sees "No payment record found" error

**Solution:**
- Create pending database record IMMEDIATELY after invoice creation
- Matches subscription flow architecture
- Eliminates race condition
- Better user experience

**Status:**
- 🔍 **ROOT CAUSE IDENTIFIED**
- ⏸️ **AWAITING USER CONFIRMATION BEFORE IMPLEMENTATION**
- ❓ **QUESTIONS NEED ANSWERS** (see above)

---

## NEXT STEPS

**Before implementing, need user to confirm:**

1. Should donations grant channel access? (Currently they do - 30 days)
2. Should we match subscription flow architecture? (Create pending record immediately)
3. Any other business logic differences between donations and subscriptions?

**After confirmation:**
1. Implement database insert in `finalize_payment()`
2. Test both donation flows (with/without message)
3. Verify IPN still works correctly
4. Deploy to VM

---

**Status:** 🟡 **ANALYSIS COMPLETE - AWAITING USER DECISION**
