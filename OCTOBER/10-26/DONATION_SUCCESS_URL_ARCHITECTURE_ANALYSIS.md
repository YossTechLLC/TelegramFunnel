# Donation success_url Architecture Analysis

**Date:** 2025-11-15
**Status:** 🔴 **CRITICAL ISSUE IDENTIFIED - REQUIRES IMMEDIATE FIX**

---

## PROBLEM IDENTIFIED

### Current Donation Flow (BROKEN)

**File:** `TelePay10-26/services/payment_service.py` (Line 295)

```python
base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')
success_url = f"{base_url}/payment-processing?order_id={quote(order_id)}"
```

**Current success_url:**
```
https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_SAXuQAASGV5IHRoaXMgaXMgYSBTdHJhdCAhISE
```

**Issues:**
1. ❌ Points to `www.paygateprime.com/payment-processing` (domain doesn't exist)
2. ❌ Not using the proper landing page architecture
3. ❌ Inconsistent with subscription flow
4. ❌ No payment status polling mechanism

---

### Correct Subscription Flow (WORKING)

**File:** `TelePay10-26/start_np_gateway.py` (Lines 297-298)

```python
landing_page_base_url = "https://storage.googleapis.com/paygateprime-static/payment-processing.html"
secure_success_url = f"{landing_page_base_url}?order_id={quote(order_id, safe='')}"
```

**Correct success_url:**
```
https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003377958897
```

**Why This Works:**
1. ✅ Points to actual static HTML page in Cloud Storage
2. ✅ Landing page polls `np-webhook-10-26` for payment status
3. ✅ Uses same-origin architecture (np-webhook serves HTML via `/payment-processing` route)
4. ✅ Proper CORS configuration

---

## ARCHITECTURAL CONTEXT

### Payment Processing Flow (Subscription - CORRECT)

```
User pays on NowPayments
         ↓
NowPayments redirects to: storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-xxx
         ↓
payment-processing.html loads in browser
         ↓
JavaScript polls: np-webhook-10-26.run.app/api/payment-status?order_id=PGP-xxx
         ↓
np-webhook checks database for payment confirmation
         ↓
Once confirmed: Redirect to success page OR show confirmation
```

### np-webhook Architecture (Same-Origin Alternative)

**From DECISIONS_ARCH.md (2025-11-02):**

**Decision:** Serve `payment-processing.html` from np-webhook service itself instead of Cloud Storage

**Rationale:**
- Eliminates CORS issues (same-origin policy)
- No hardcoded URLs (uses `window.location.origin`)
- Simpler deployment (no Cloud Storage dependency)

**Implementation:**

**File:** `np-webhook-10-26/app.py` (Lines 1295-1311)

```python
@app.route('/payment-processing', methods=['GET'])
def serve_payment_processing_page():
    """
    Serve the payment-processing.html landing page.

    This page is where NowPayments redirects users after payment.
    By serving it from the same origin as the API, we eliminate CORS complexity
    and avoid hardcoding URLs (uses window.location.origin).
    """
    try:
        # Read the HTML file
        with open('payment-processing.html', 'r') as f:
            html_content = f.read()

        return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        print(f"❌ [PAGE] Failed to serve payment-processing.html: {e}")
        return jsonify({"error": "Failed to load payment processing page"}), 500
```

**Deployment:**
- `np-webhook-10-26/payment-processing.html` exists (17648 bytes, Nov 8 08:45)
- `np-webhook-10-26/Dockerfile` copies HTML file: `COPY payment-processing.html .`

---

## ROOT CAUSE: BASE_URL Environment Variable

**File:** `TelePay10-26/services/payment_service.py` (Line 295)

```python
base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')
```

**Problem:**
- `BASE_URL` environment variable is set to `https://www.paygateprime.com`
- This domain does NOT have a `/payment-processing` endpoint
- Should point to `np-webhook-10-26` service URL OR Cloud Storage bucket

---

## SOLUTION OPTIONS

### Option 1: Use Cloud Storage (Same as Subscription Flow) ✅ RECOMMENDED

**Approach:** Match subscription flow exactly

**Changes Required:**

**File:** `TelePay10-26/services/payment_service.py`

**Before (Lines 293-303):**
```python
# Build base success URL with properly encoded order_id
# URL encode the pipe character (|) in order_id format: PGP-{user_id}|{channel_id}
base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')

# DEBUG: Log order_id before and after URL encoding
logger.info(f"🔑 [DEBUG] Order ID encoding:")
logger.info(f"   Original order_id: '{order_id}'")
logger.info(f"   URL-encoded order_id: '{quote(order_id)}'")

success_url = f"{base_url}/payment-processing?order_id={quote(order_id)}"
logger.info(f"🔗 [DEBUG] Base success_url (before message): {success_url}")

# Encrypt and append message if provided (with URL encoding)
if donation_message:
    logger.info(f"💬 [PAYMENT] Including donation message in invoice")

    # DEBUG: Log encryption and URL encoding process
    logger.info(f"🔐 [DEBUG] Message encryption process:")
    logger.info(f"   Step 1 - Original message: '{donation_message}'")

    encrypted_msg = encrypt_donation_message(donation_message)

    logger.info(f"   Step 2 - After encryption (base64url): '{encrypted_msg}'")
    logger.info(f"   Step 3 - URL-encoded encrypted msg: '{quote(encrypted_msg)}'")

    success_url += f"&msg={quote(encrypted_msg)}"  # URL encode encrypted message

    logger.info(f"   Encrypted message length: {len(encrypted_msg)} chars")
    logger.info(f"🔗 [DEBUG] Final success_url (with message): {success_url}")
```

**After:**
```python
# Build success URL pointing to static landing page in Cloud Storage
# This matches the subscription flow architecture from start_np_gateway.py
# The landing page polls np-webhook for payment status and handles message decryption
landing_page_base_url = "https://storage.googleapis.com/paygateprime-static/payment-processing.html"

# DEBUG: Log order_id before and after URL encoding
logger.info(f"🔑 [DEBUG] Order ID encoding:")
logger.info(f"   Original order_id: '{order_id}'")
logger.info(f"   URL-encoded order_id: '{quote(order_id, safe='')}'")

success_url = f"{landing_page_base_url}?order_id={quote(order_id, safe='')}"
logger.info(f"🔗 [DEBUG] Base success_url (before message): {success_url}")

# Encrypt and append message if provided (with URL encoding)
if donation_message:
    logger.info(f"💬 [PAYMENT] Including donation message in invoice")

    # DEBUG: Log encryption and URL encoding process
    logger.info(f"🔐 [DEBUG] Message encryption process:")
    logger.info(f"   Step 1 - Original message: '{donation_message}'")

    encrypted_msg = encrypt_donation_message(donation_message)

    logger.info(f"   Step 2 - After encryption (base64url): '{encrypted_msg}'")
    logger.info(f"   Step 3 - URL-encoded encrypted msg: '{quote(encrypted_msg, safe='')}'")

    success_url += f"&msg={quote(encrypted_msg, safe='')}"  # URL encode encrypted message

    logger.info(f"   Encrypted message length: {len(encrypted_msg)} chars")
    logger.info(f"🔗 [DEBUG] Final success_url (with message): {success_url}")
```

**Key Changes:**
1. Replace `base_url = os.getenv('BASE_URL', ...)` with hardcoded Cloud Storage URL
2. Change `quote(order_id)` to `quote(order_id, safe='')` (matches subscription flow)
3. Change `quote(encrypted_msg)` to `quote(encrypted_msg, safe='')` (matches subscription flow)

**Benefits:**
- ✅ Matches subscription flow exactly
- ✅ Uses proven, working architecture
- ✅ No environment variable dependency
- ✅ Consistent user experience

---

### Option 2: Use np-webhook Same-Origin Architecture ⚠️ ALTERNATIVE

**Approach:** Point to np-webhook service endpoint

**Changes Required:**

**File:** `TelePay10-26/services/payment_service.py`

```python
# Build success URL pointing to np-webhook service (same-origin architecture)
# The np-webhook service serves payment-processing.html at /payment-processing
# This eliminates CORS issues and uses window.location.origin for API calls
np_webhook_url = os.getenv('NOWPAYMENTS_IPN_CALLBACK_URL', 'https://np-webhook-10-26-291176869049.us-central1.run.app')
# Extract base URL (remove /api/nowpayments-ipn if present)
base_url = np_webhook_url.replace('/api/nowpayments-ipn', '')
landing_page_url = f"{base_url}/payment-processing"

# DEBUG: Log order_id before and after URL encoding
logger.info(f"🔑 [DEBUG] Order ID encoding:")
logger.info(f"   Original order_id: '{order_id}'")
logger.info(f"   URL-encoded order_id: '{quote(order_id, safe='')}'")

success_url = f"{landing_page_url}?order_id={quote(order_id, safe='')}"
# ... rest of code
```

**Benefits:**
- ✅ Same-origin architecture (no CORS)
- ✅ Uses window.location.origin (no hardcoded API URLs)
- ✅ Single deployment (np-webhook serves both HTML and API)

**Drawbacks:**
- ⚠️ Requires parsing NOWPAYMENTS_IPN_CALLBACK_URL environment variable
- ⚠️ Different from subscription flow (inconsistent)

---

## RECOMMENDED APPROACH: Option 1 (Cloud Storage)

**Why:**
1. **Proven working architecture** - Subscription flow uses this
2. **Simple** - No environment variable parsing
3. **Consistent** - Both subscription and donation flows use same landing page
4. **Reliable** - Cloud Storage is highly available

**Why NOT Option 2:**
- Inconsistent with subscription flow
- Requires environment variable parsing
- More complex

---

## IMPLEMENTATION PLAN

### Step 1: Update payment_service.py

**File:** `TelePay10-26/services/payment_service.py` (Lines 293-321)

Replace entire success_url construction block with Cloud Storage URL approach.

---

### Step 2: Handle Donation Message in Landing Page

**Current Issue:** The `payment-processing.html` landing page doesn't know about donation messages.

**Solution:** Landing page needs to:
1. Extract `msg` parameter from URL
2. Display message to channel owner via notification (already handled by np-webhook IPN)

**No changes needed** - The IPN callback already handles message extraction and decryption:

**File:** `np-webhook-10-26/app.py` (Lines 585-615)

```python
def extract_message_from_success_url(success_url: str) -> Optional[str]:
    """Extract encrypted message from success_url query parameter."""
    try:
        if not success_url:
            return None

        # Parse URL and extract query parameters
        parsed = urlparse(success_url)
        query_params = parse_qs(parsed.query)

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

**Flow:**
1. User pays → NowPayments stores `success_url` with `msg` parameter
2. Payment confirmed → NowPayments sends IPN to np-webhook
3. np-webhook extracts `msg` from `success_url` in IPN payload
4. np-webhook decrypts message
5. np-webhook sends notification to channel owner with decrypted message

---

### Step 3: Test Flow

**Test Case 1: Donation WITHOUT Message**
1. Start donation flow
2. Amount: $5.00
3. Click "Skip Message"
4. **Expected success_url:** `https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003377958897`
5. Pay invoice
6. **Expected:** Landing page loads, polls for payment status, shows success

**Test Case 2: Donation WITH Message**
1. Start donation flow
2. Amount: $5.00
3. Click "Add Message"
4. Type: "Test message 123"
5. **Expected success_url:** `https://storage.googleapis.com/paygateprime-static/payment-processing.html?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_SAXuQAA...`
6. Pay invoice
7. **Expected:** Landing page loads, polls for payment status, shows success
8. **Expected IPN:** np-webhook extracts message from success_url, decrypts, sends notification to channel owner

---

## FILES TO MODIFY

### ✅ `TelePay10-26/services/payment_service.py`
- Lines 293-321: Replace BASE_URL logic with Cloud Storage URL

---

## DEPENDENCIES

- ✅ `payment-processing.html` already exists in Cloud Storage bucket
- ✅ `np-webhook-10-26` already handles message extraction from success_url
- ✅ CORS already configured for `storage.googleapis.com`
- ✅ No new environment variables needed

---

## ROLLBACK PLAN

If issues occur:

1. Revert `payment_service.py` to use BASE_URL environment variable
2. No database changes (safe rollback)
3. No deployment changes needed (pure logic change)

---

## QUESTIONS FOR USER

1. ✅ **Approve Option 1** (Cloud Storage URL)?
   - Recommended: Yes (matches subscription flow)

2. ✅ **Confirm Cloud Storage URL:**
   - `https://storage.googleapis.com/paygateprime-static/payment-processing.html`
   - Is this the correct URL? (verified from subscription flow)

3. ✅ **Verify payment-processing.html handles donations:**
   - Does landing page need any updates to handle donation flow?
   - Or is it generic enough to work for both subscription and donation?

4. ✅ **Ready to proceed with implementation?**

---

## SUMMARY

**Current Problem:**
- Donation flow uses `https://www.paygateprime.com/payment-processing` (doesn't exist)
- Subscription flow uses `https://storage.googleapis.com/paygateprime-static/payment-processing.html` (works)

**Root Cause:**
- `BASE_URL` environment variable points to wrong domain
- Not using proven landing page architecture

**Solution:**
- Replace BASE_URL logic with hardcoded Cloud Storage URL
- Match subscription flow exactly
- 3 lines changed in `payment_service.py`

**Impact:**
- ✅ Donation payments will redirect to proper landing page
- ✅ Payment status polling will work
- ✅ Message encryption/decryption unaffected
- ✅ Consistent user experience across donation and subscription flows

---

**Status:** 🔴 **AWAITING USER APPROVAL TO PROCEED**
