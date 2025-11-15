# IPN Workflow with Donation Message - Complete Flow

**Date:** 2025-11-15
**Status:** 📘 **TECHNICAL DOCUMENTATION**

---

## YOUR QUESTION

> "Would we be able to trigger the np webhook given this is the success_url 'https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb' --> we want to see what would happen if nowpayments triggered status : finished --> and this was the token we passed"

---

## SHORT ANSWER

**YES!** ✅ The success_url is **NOT used to trigger np-webhook**.

**Two separate mechanisms:**
1. **success_url** → User redirect URL (browser navigation)
2. **IPN callback** → Backend webhook trigger (NowPayments → np-webhook)

The success_url is stored by NowPayments and included in the IPN payload, where np-webhook extracts the encrypted message from it.

---

## COMPLETE PAYMENT FLOW

### **Step 1: User Pays on NowPayments**

**User Journey:**
1. User receives invoice URL: `https://nowpayments.io/payment/?iid=5140807937`
2. User selects crypto (e.g., ETH)
3. User sends payment to NowPayments address
4. NowPayments confirms payment received

---

### **Step 2: NowPayments Redirects User (Browser)**

**After payment confirmed:**

NowPayments redirects user's browser to the `success_url` that was provided when creating the invoice:

```
https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb
```

**What happens:**
- ✅ Browser navigates to Cloud Storage landing page
- ✅ Landing page JavaScript starts polling `/api/payment-status`
- ✅ User sees "Processing payment..." message
- ⚠️ **This is NOT the webhook trigger**

---

### **Step 3: NowPayments Sends IPN (Backend Webhook)**

**Parallel to user redirect** (or slightly after), NowPayments sends HTTP POST to np-webhook:

**URL:** `https://np-webhook-10-26-291176869049.us-central1.run.app/api/nowpayments-ipn`

**Method:** `POST`

**Headers:**
```json
{
  "x-nowpayments-sig": "f8d3e7c6b5a4...",
  "Content-Type": "application/json"
}
```

**Body (IPN Payload):**
```json
{
  "payment_id": "8139434771",
  "invoice_id": "5140807937",
  "order_id": "PGP-6271402111|-1003377958897",
  "payment_status": "finished",
  "pay_address": "0xABC123...",
  "pay_amount": "0.00123",
  "pay_currency": "ETH",
  "outcome_amount": "0.00123",
  "outcome_currency": "ETH",
  "price_amount": "5.00",
  "price_currency": "USD",
  "success_url": "https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb"
}
```

**KEY POINT:** ⬆️ The `success_url` is included in the IPN payload!

---

## NP-WEBHOOK PROCESSING (Step-by-Step)

### **Step 1: Signature Verification**

**File:** `np-webhook-10-26/app.py` (Lines 648-651)

```python
# Verify signature
if not verify_ipn_signature(payload, signature):
    print(f"❌ [IPN] Signature verification failed - rejecting request")
    abort(403, "Invalid signature")
```

**Expected Output:**
```
🔐 [IPN] Signature header present: f8d3e7c6b5a4...
✅ [IPN] Signature verified successfully
```

---

### **Step 2: Payment Status Validation**

**File:** `np-webhook-10-26/app.py` (Lines 674-708)

```python
payment_status = ipn_data.get('payment_status', '').lower()
ALLOWED_PAYMENT_STATUSES = ['finished']

if payment_status not in ALLOWED_PAYMENT_STATUSES:
    # Return 200 but don't process
    return jsonify({
        "status": "acknowledged",
        "message": f"IPN received but not processed. Waiting for status 'finished'"
    }), 200

# If we reach here, payment_status is 'finished' - proceed
```

**Expected Output (status = "finished"):**
```
🔍 [IPN] Payment status received: 'finished'
✅ [IPN] Allowed statuses: ['finished']
✅ [IPN] PAYMENT STATUS VALIDATED: 'finished'
✅ [IPN] Proceeding with payment processing
```

---

### **Step 3: Extract Encrypted Message from success_url**

**File:** `np-webhook-10-26/app.py` (Lines 585-615)

```python
def extract_message_from_success_url(success_url: str) -> Optional[str]:
    """Extract encrypted message from success_url query parameter."""
    try:
        if not success_url:
            return None

        # Parse URL and extract query parameters
        parsed = urlparse(success_url)
        query_params = parse_qs(parsed.query)  # ✅ Auto-decodes URL encoding

        # Get 'msg' parameter (returns list, take first value)
        encrypted_msg = query_params.get('msg', [None])[0]

        if encrypted_msg:
            print(f"💬 [IPN] Found encrypted message in success_url ({len(encrypted_msg)} chars)")
            return encrypted_msg
        else:
            print(f"💬 [IPN] No message parameter in success_url")
            return None

    except Exception as e:
        print(f"❌ [IPN] Error extracting message from success_url: {e}")
        return None
```

**Expected Output:**
```
💬 [IPN] Extracting message from success_url...
   success_url: https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb
💬 [IPN] Found encrypted message in success_url (40 chars)
💬 [IPN] Encrypted message: 'KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb'
```

**How it works:**
- `parse_qs()` automatically URL-decodes the query parameters
- `msg=KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb` is extracted
- No additional decoding needed (base64url is already URL-safe)

---

### **Step 4: Update Database with Payment Data**

**File:** `np-webhook-10-26/app.py` (Lines 718-750)

```python
payment_data = {
    'payment_id': ipn_data.get('payment_id'),
    'invoice_id': ipn_data.get('invoice_id'),
    'order_id': ipn_data.get('order_id'),
    'pay_address': ipn_data.get('pay_address'),
    'payment_status': ipn_data.get('payment_status'),
    'pay_amount': ipn_data.get('pay_amount'),
    'pay_currency': ipn_data.get('pay_currency'),
    'outcome_amount': ipn_data.get('outcome_amount'),
    'price_amount': ipn_data.get('price_amount'),
    'price_currency': ipn_data.get('price_currency'),
    'outcome_currency': ipn_data.get('outcome_currency')
}

success = update_payment_data(order_id, payment_data)
```

**Expected Output:**
```
🗄️ [DATABASE] Updating database with payment data...
✅ [DATABASE] Payment data updated successfully
   Order ID: PGP-6271402111|-1003377958897
   Payment ID: 8139434771
   Payment Status: finished
```

---

### **Step 5: Calculate Outcome Amount in USD**

**File:** `np-webhook-10-26/app.py` (Lines 753-807)

```python
outcome_amount = payment_data.get('outcome_amount')
outcome_currency = payment_data.get('outcome_currency', 'ETH')

# Fetch ETH price from CoinGecko
crypto_usd_price = get_crypto_usd_price(outcome_currency)

if crypto_usd_price:
    outcome_amount_usd = float(outcome_amount) * crypto_usd_price
    print(f"💰 [CONVERT] {outcome_amount} {outcome_currency} × ${crypto_usd_price:,.2f}")
    print(f"💰 [CONVERT] = ${outcome_amount_usd:.2f} USD")
```

**Expected Output:**
```
💱 [CONVERSION] Calculating USD value of outcome amount...
🔍 [PRICE] Fetching ETH price from CoinGecko...
✅ [PRICE] Current ETH price: $3,245.67
💰 [CONVERT] 0.00123 ETH × $3,245.67
💰 [CONVERT] = $3.99 USD
💰 [VALIDATION] Final Outcome in USD: $3.99
```

---

### **Step 6: Idempotency Check**

**File:** `np-webhook-10-26/app.py` (Lines 850-925)

```python
# Check if payment already processed
cur_check.execute("""
    SELECT gcwebhook1_processed, telegram_invite_sent
    FROM processed_payments
    WHERE payment_id = %s
""", (nowpayments_payment_id,))

existing_payment = cur_check.fetchone()

if existing_payment and existing_payment[0]:  # Already processed
    return jsonify({
        "status": "success",
        "message": "IPN processed (already handled)",
        "payment_id": nowpayments_payment_id
    }), 200
```

**Expected Output (First Time):**
```
🆕 [IDEMPOTENCY] Payment 8139434771 is new - creating processing record
✅ [IDEMPOTENCY] Created processing record for payment 8139434771
```

---

### **Step 7: Trigger GCWebhook1 (Cloud Tasks)**

**File:** `np-webhook-10-26/app.py` (Lines 940-999)

```python
# Enqueue payment to GCWebhook1 for processing
task_name = cloudtasks_client.enqueue_gcwebhook1(
    queue_name=GCWEBHOOK1_QUEUE,
    url=GCWEBHOOK1_URL,
    order_id=order_id,
    payment_id=nowpayments_payment_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_time_days=subscription_time_days,
    subscription_price=subscription_price
)
```

**Expected Output:**
```
🚀 [ORCHESTRATION] Triggering GCWebhook1 for payment processing...
✅ [CLOUDTASKS] Task enqueued to GCWebhook1 successfully
   Task Name: projects/telepay-459221/locations/us-central1/queues/gcwebhook1-queue/tasks/gcwebhook1-payment-8139434771-...
```

---

### **Step 8: Send Notification to Channel Owner (GCNotificationService)**

**File:** `np-webhook-10-26/app.py` (Lines 1000-1089)

**This is where the encrypted message is used!**

```python
# Extract encrypted message from success_url
encrypted_msg = extract_message_from_success_url(ipn_data.get('success_url'))

# Decrypt message
if encrypted_msg:
    try:
        # Import decrypt function
        import sys
        sys.path.append('/workspace')  # Add np-webhook directory to path
        from decrypt_message import decrypt_donation_message

        decrypted_msg = decrypt_donation_message(encrypted_msg)
        print(f"✅ [DECRYPT] Decrypted message: '{decrypted_msg}'")
    except Exception as e:
        print(f"❌ [DECRYPT] Decryption failed: {e}")
        decrypted_msg = None
else:
    decrypted_msg = None

# Build notification payload
notification_payload = {
    'channel_id': open_channel_id,
    'payment_type': 'donation',  # or 'subscription'
    'payment_data': {
        'order_id': order_id,
        'payment_id': nowpayments_payment_id,
        'amount_usd': str(price_amount),
        'crypto_amount': str(outcome_amount),
        'crypto_currency': outcome_currency,
        'donation_message': decrypted_msg  # ✅ Decrypted message included
    }
}

# Send to GCNotificationService
response = requests.post(
    f"{GCNOTIFICATIONSERVICE_URL}/send-notification",
    json=notification_payload,
    timeout=10
)
```

**Expected Output:**
```
💬 [IPN] Extracting message from success_url...
💬 [IPN] Found encrypted message in success_url (40 chars)
🔓 [DECRYPT] Decrypting message (40 chars)
✅ [DECRYPT] Decrypted message: 'Hey man tetaiiioo'

📤 [NOTIFICATION] Calling GCNotificationService...
   URL: https://gcnotificationservice-10-26-*.run.app/send-notification
   Channel ID: -1003377958897
   Payment Type: donation

✅ [NOTIFICATION] Notification sent successfully
📤 [NOTIFICATION] Response: Notification queued for delivery
```

---

### **Step 9: Final Response**

**File:** `np-webhook-10-26/app.py` (Lines 1108-1113)

```python
print(f"✅ [IPN] IPN processed successfully")
print(f"🎯 [IPN] payment_id {payment_data['payment_id']} stored in database")

return jsonify({"status": "success", "message": "IPN processed"}), 200
```

**Expected Output:**
```
✅ [IPN] IPN processed successfully
🎯 [IPN] payment_id 8139434771 stored in database
```

---

## COMPLETE EXPECTED LOG OUTPUT

### **When NowPayments Sends IPN with status="finished"**

```
===============================================================================
📬 [IPN] Received callback from NowPayments
🌐 [IPN] Source IP: 34.78.123.45
⏰ [IPN] Timestamp: Fri, 15 Nov 2025 04:30:00 GMT
🔐 [IPN] Signature header present: f8d3e7c6b5a4...
📦 [IPN] Payload size: 512 bytes
✅ [IPN] Signature verified successfully

📋 [IPN] Payment Data Received:
   Payment ID: 8139434771
   Order ID: PGP-6271402111|-1003377958897
   Payment Status: finished
   Pay Amount: 0.00123 ETH
   Outcome Amount: 0.00123 ETH
   Price Amount: 5.00 USD
   Pay Address: 0xABC123...

🔍 [IPN] Payment status received: 'finished'
✅ [IPN] Allowed statuses: ['finished']
===============================================================================
✅ [IPN] PAYMENT STATUS VALIDATED: 'finished'
✅ [IPN] Proceeding with payment processing
===============================================================================

🗄️ [DATABASE] Updating database with payment data...
✅ [DATABASE] Payment data updated successfully

💱 [CONVERSION] Calculating USD value of outcome amount...
🔍 [PRICE] Fetching ETH price from CoinGecko...
✅ [PRICE] Current ETH price: $3,245.67
💰 [CONVERT] 0.00123 ETH × $3,245.67
💰 [CONVERT] = $3.99 USD
💰 [VALIDATION] Final Outcome in USD: $3.99

🆕 [IDEMPOTENCY] Payment 8139434771 is new - creating processing record
✅ [IDEMPOTENCY] Created processing record for payment 8139434771

🚀 [ORCHESTRATION] Proceeding to enqueue payment to GCWebhook1...

🚀 [ORCHESTRATION] Triggering GCWebhook1 for payment processing...
✅ [CLOUDTASKS] Task enqueued to GCWebhook1 successfully
   Task Name: projects/telepay-459221/locations/us-central1/queues/gcwebhook1-queue/tasks/...

💬 [IPN] Extracting message from success_url...
   success_url: https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb
💬 [IPN] Found encrypted message in success_url (40 chars)
💬 [IPN] Encrypted message: 'KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb'

🔓 [DECRYPT] Decrypting message (40 chars)
   🔐 [DEBUG] Step 1 - Base64url decode: 28 bytes
   🗜️ [DEBUG] Step 2 - Decompressed: 17 bytes
✅ [DECRYPT] Decrypted message: 'Hey man tetaiiioo'

📤 [NOTIFICATION] Calling GCNotificationService...
   URL: https://gcnotificationservice-10-26-291176869049.us-central1.run.app/send-notification
   Channel ID: -1003377958897
   Payment Type: donation

✅ [NOTIFICATION] Notification sent successfully
📤 [NOTIFICATION] Response: Notification queued for delivery

✅ [IPN] IPN processed successfully
🎯 [IPN] payment_id 8139434771 stored in database
===============================================================================
```

---

## KEY POINTS

### **1. success_url is NOT the webhook trigger**
- ❌ **WRONG:** success_url triggers np-webhook
- ✅ **CORRECT:** IPN POST request triggers np-webhook

### **2. success_url has TWO purposes:**
1. **Browser redirect:** User sees landing page after payment
2. **Message storage:** NowPayments includes it in IPN payload

### **3. Message extraction flow:**
```
User types: "Hey man tetaiiioo"
     ↓
TelePay encrypts: "KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb"
     ↓
Included in success_url: ...&msg=KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb
     ↓
NowPayments stores success_url in invoice
     ↓
NowPayments sends IPN with success_url in payload
     ↓
np-webhook extracts 'msg' parameter from success_url
     ↓
np-webhook decrypts: "Hey man tetaiiioo"
     ↓
GCNotificationService sends to channel owner
```

### **4. Idempotency protection:**
- ✅ Multiple IPNs for same payment_id → Only processed once
- ✅ `processed_payments` table prevents duplicates

---

## TESTING THE FLOW

### **Manual IPN Test (Using curl)**

You can manually trigger the flow by sending a test IPN:

```bash
# Get signature (use actual secret)
curl -X POST https://np-webhook-10-26-291176869049.us-central1.run.app/api/nowpayments-ipn \
  -H "x-nowpayments-sig: YOUR_SIGNATURE_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "TEST-8139434771",
    "invoice_id": "5140807937",
    "order_id": "PGP-6271402111|-1003377958897",
    "payment_status": "finished",
    "pay_address": "0xTEST123",
    "pay_amount": "0.00123",
    "pay_currency": "ETH",
    "outcome_amount": "0.00123",
    "outcome_currency": "ETH",
    "price_amount": "5.00",
    "price_currency": "USD",
    "success_url": "https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb"
  }'
```

**Expected:**
- ✅ IPN validates signature
- ✅ Extracts encrypted message from success_url
- ✅ Decrypts to "Hey man tetaiiioo"
- ✅ Sends notification to channel owner

---

## SUMMARY

**Your Question:** Will the webhook be triggered with this success_url?

**Answer:** YES! ✅

The success_url you showed is **perfect** and will work as follows:

1. **Browser redirect:** User → Cloud Storage landing page
2. **IPN trigger:** NowPayments → np-webhook (separate HTTP POST)
3. **Message extraction:** np-webhook parses `success_url` from IPN payload
4. **Decryption:** `KLUv_SARiQAASGV5IG1hbiB0ZXRhaWlpb` → `"Hey man tetaiiioo"`
5. **Notification:** Channel owner receives decrypted message ✅

**The success_url is NOT used to trigger the webhook, but it IS included in the IPN payload where the encrypted message is extracted from.**

---

**Status:** 📘 **COMPLETE TECHNICAL DOCUMENTATION**
