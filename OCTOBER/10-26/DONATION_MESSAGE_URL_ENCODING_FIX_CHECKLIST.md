# Donation Message URL Encoding Fix - Implementation Checklist

**Date:** 2025-11-15
**Status:** 🔴 **AWAITING APPROVAL**

---

## EXECUTIVE SUMMARY

**Root Cause:** NowPayments API rejecting invoice creation with `"success_url must be a valid uri"` because:
1. The pipe character `|` in `order_id` (format: `PGP-{user_id}|{channel_id}`) is **not URL-encoded**
2. The encrypted donation message in the `msg` parameter is **not URL-encoded**

**Impact:** Both donation flows (with and without message) are failing at invoice creation.

**Solution:** Add `urllib.parse.quote()` to properly URL-encode ALL query parameters in `success_url`.

**Scope:** Single file change in `TelePay10-26/services/payment_service.py`

**Risk Level:** ⚠️ **LOW** - This fix was already applied once before for the same issue (see BUGS_ARCH.md entry from 2025-11-02). We're simply re-applying the correct pattern.

---

## ANALYSIS SUMMARY

### Current Code (BROKEN)

**File:** `TelePay10-26/services/payment_service.py` (Lines 292-301)

```python
# Build base success URL
base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')
success_url = f"{base_url}/payment-processing?order_id={order_id}"  # ❌ NO ENCODING

# Encrypt and append message if provided
if donation_message:
    logger.info(f"💬 [PAYMENT] Including donation message in invoice")
    encrypted_msg = encrypt_donation_message(donation_message)
    success_url += f"&msg={encrypted_msg}"  # ❌ NO ENCODING
    logger.info(f"   Encrypted message length: {len(encrypted_msg)} chars")
```

**Example Broken URLs:**

1. **With message:**
   ```
   https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111|-1003377958897&msg=KLUv_QBYwQEA...
                                                                          ↑ INVALID PIPE (needs %7C)
   ```

2. **Without message:**
   ```
   https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111|-1003377958897
                                                                          ↑ INVALID PIPE (needs %7C)
   ```

**NowPayments Error:**
```json
{
  "status": false,
  "statusCode": 400,
  "code": "INVALID_REQUEST_PARAMS",
  "message": "success_url must be a valid uri"
}
```

---

### Why This Happens

1. **Pipe Character `|` in order_id**
   - Format: `PGP-{user_id}|{channel_id}` (e.g., `PGP-6271402111|-1003377958897`)
   - The pipe `|` is **NOT a valid URI character** per RFC 3986
   - Must be percent-encoded as `%7C`

2. **Base64URL ≠ URL Encoding for Query Parameters**
   - `message_encryption.py` uses `base64.urlsafe_b64encode()` which produces `-` and `_` instead of `+` and `/`
   - This makes the string URL-safe for **path segments**
   - But it's **NOT sufficient** for **query parameters** without additional encoding
   - NowPayments has strict URI validation that requires proper query parameter encoding

3. **Historical Precedent**
   - This exact issue was fixed on 2025-11-02 (see BUGS_ARCH.md)
   - The donation message feature re-introduced the same pattern without URL encoding
   - The fix is well-tested and proven to work

---

### Fixed Code (PROPOSED)

**Option 1: Using `urllib.parse.quote()` (Recommended)**

```python
from urllib.parse import quote  # Add to imports at top of file

# Build base success URL with encoded order_id
base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')
success_url = f"{base_url}/payment-processing?order_id={quote(order_id)}"  # ✅ ENCODED

# Encrypt and append message if provided (with encoding)
if donation_message:
    logger.info(f"💬 [PAYMENT] Including donation message in invoice")
    encrypted_msg = encrypt_donation_message(donation_message)
    success_url += f"&msg={quote(encrypted_msg)}"  # ✅ ENCODED
    logger.info(f"   Encrypted message length: {len(encrypted_msg)} chars")
```

**Option 2: Using `urllib.parse.urlencode()` (More Robust, Alternative)**

```python
from urllib.parse import urlencode  # Add to imports at top of file

# Build base success URL
base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')

# Build query parameters dictionary
params = {'order_id': order_id}

# Add encrypted message if provided
if donation_message:
    logger.info(f"💬 [PAYMENT] Including donation message in invoice")
    encrypted_msg = encrypt_donation_message(donation_message)
    params['msg'] = encrypted_msg
    logger.info(f"   Encrypted message length: {len(encrypted_msg)} chars")

# Construct success_url with properly encoded query string
success_url = f"{base_url}/payment-processing?{urlencode(params)}"  # ✅ ENCODED
```

**Example Fixed URLs:**

1. **With message:**
   ```
   https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_QBYwQEA...
                                                                          ↑ ENCODED PIPE
   ```

2. **Without message:**
   ```
   https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897
                                                                          ↑ ENCODED PIPE
   ```

---

## DECRYPTION FLOW VERIFICATION

**Critical Question:** Will URL encoding break decryption?

**Answer:** ✅ **NO** - Decryption will work correctly.

### How Decryption Works (np-webhook-10-26/app.py)

**Lines 585-615: Message Extraction**
```python
def extract_message_from_success_url(success_url: str) -> Optional[str]:
    """Extract encrypted message from success_url query parameter."""
    try:
        if not success_url:
            return None

        # Parse URL and extract query parameters
        parsed = urlparse(success_url)
        query_params = parse_qs(parsed.query)  # ✅ AUTOMATICALLY URL-DECODES

        # Get 'msg' parameter (returns list, take first value)
        encrypted_msg = query_params.get('msg', [None])[0]  # ✅ ALREADY DECODED

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

**Key Points:**

1. **`urllib.parse.parse_qs()` automatically URL-decodes all query parameters**
   - Receives: `msg=KLUv_QBYwQEA...` (may or may not be URL-encoded)
   - Returns: `{'msg': ['KLUv_QBYwQEA...']}`
   - The value is **automatically decoded** if it was encoded

2. **The decryption function receives the original base64url string**
   ```python
   # np-webhook-10-26/app.py line 986
   encrypted_message = extract_message_from_success_url(success_url)

   # Then passed to GCNotificationService which decrypts it:
   # GCNotificationService-10-26/service.py
   from shared_utils.message_encryption import decrypt_donation_message
   decrypted_msg = decrypt_donation_message(encrypted_message)
   ```

3. **Round-trip example:**
   ```
   Original message: "Hello this is a test!"
                     ↓
   encrypt_donation_message()
                     ↓
   Base64url: "KLUv_QBYwQEArJxN5OhbVaPpzQ"
                     ↓
   quote() for URL: "KLUv_QBYwQEArJxN5OhbVaPpzQ" (no change needed, already URL-safe)
                     ↓
   NowPayments stores: success_url with encoded params
                     ↓
   IPN callback provides: success_url
                     ↓
   parse_qs() extracts: "KLUv_QBYwQEArJxN5OhbVaPpzQ" (auto-decoded)
                     ↓
   decrypt_donation_message()
                     ↓
   Result: "Hello this is a test!" ✅
   ```

**Conclusion:** URL encoding is **transparent** to the decryption flow. The `parse_qs()` function handles all decoding automatically.

---

## IMPLEMENTATION PLAN

### Changes Required

**File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TelePay10-26/services/payment_service.py`

#### Change 1: Add Import (Line 5-10 area)

**Current imports:**
```python
import logging
import os
from typing import Dict, Optional
```

**Add:**
```python
from urllib.parse import quote  # For URL encoding query parameters
```

#### Change 2: Fix success_url Construction (Lines 292-301)

**Before:**
```python
# Build base success URL
base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')
success_url = f"{base_url}/payment-processing?order_id={order_id}"

# Encrypt and append message if provided
if donation_message:
    logger.info(f"💬 [PAYMENT] Including donation message in invoice")
    encrypted_msg = encrypt_donation_message(donation_message)
    success_url += f"&msg={encrypted_msg}"
    logger.info(f"   Encrypted message length: {len(encrypted_msg)} chars")
```

**After:**
```python
# Build base success URL with properly encoded order_id
base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')
success_url = f"{base_url}/payment-processing?order_id={quote(order_id)}"  # URL encode pipe character

# Encrypt and append message if provided (with URL encoding)
if donation_message:
    logger.info(f"💬 [PAYMENT] Including donation message in invoice")
    encrypted_msg = encrypt_donation_message(donation_message)
    success_url += f"&msg={quote(encrypted_msg)}"  # URL encode encrypted message
    logger.info(f"   Encrypted message length: {len(encrypted_msg)} chars")
```

---

## TESTING PLAN

### Pre-Deployment Testing

**Environment:** Local machine or VM

1. **Test URL Encoding Manually:**
   ```python
   from urllib.parse import quote

   # Test order_id encoding
   order_id = "PGP-6271402111|-1003377958897"
   encoded = quote(order_id)
   print(f"Original: {order_id}")
   print(f"Encoded:  {encoded}")
   # Expected: PGP-6271402111%7C-1003377958897

   # Test message encoding
   msg = "KLUv_QBYwQEArJxN5OhbVaPpzQ"
   encoded_msg = quote(msg)
   print(f"Original: {msg}")
   print(f"Encoded:  {encoded_msg}")
   # Expected: KLUv_QBYwQEArJxN5OhbVaPpzQ (no change, already URL-safe)
   ```

2. **Test Round-Trip Decoding:**
   ```python
   from urllib.parse import quote, parse_qs, urlparse

   # Build URL
   url = f"https://www.paygateprime.com/payment-processing?order_id={quote('PGP-123|456')}&msg={quote('KLUv_QBYwQEA')}"
   print(f"Built URL: {url}")

   # Extract params (simulate IPN callback)
   parsed = urlparse(url)
   params = parse_qs(parsed.query)
   print(f"Extracted order_id: {params.get('order_id', [None])[0]}")
   print(f"Extracted msg: {params.get('msg', [None])[0]}")
   # Expected: Original values (auto-decoded)
   ```

### Post-Deployment Testing

1. **Test Donation WITHOUT Message:**
   - Open Telegram bot
   - Click "Donate to Support This Channel"
   - Enter amount: $5.00
   - Click "Confirm"
   - Click "💰 Skip Message - Donate Now"
   - **Expected:** Payment link created successfully ✅
   - **Check logs for:** `✅ [PAYMENT] Invoice created successfully`

2. **Test Donation WITH Message:**
   - Open Telegram bot
   - Click "Donate to Support This Channel"
   - Enter amount: $5.00
   - Click "Confirm"
   - Click "💬 Add Message"
   - Type message: "Hello this is a test!"
   - **Expected:** Payment link created successfully ✅
   - **Check logs for:** `✅ [PAYMENT] Invoice created successfully`

3. **Test Decryption Flow (Full End-to-End):**
   - Complete donation with message
   - Complete payment on NowPayments
   - **Check np-webhook logs for:**
     ```
     💬 [IPN] Found encrypted message in success_url
     ```
   - **Check GCNotificationService logs for:**
     ```
     🔓 [DECRYPT] Decrypting message
     ✅ [DECRYPT] Decrypted message: <original message>
     ```
   - **Check channel owner receives:**
     - Notification with correct amount
     - Decrypted donation message

---

## VERIFICATION STEPS

After deployment, verify the fix with these checks:

### 1. Invoice Creation Success
```
Expected log output:
📋 [PAYMENT] Creating invoice: user=6271402111, amount=$5.00, order=PGP-6271402111|-1003377958897
✅ [PAYMENT] Invoice created successfully
   Invoice URL: https://nowpayments.io/payment/...
```

### 2. URL Format Validation
```
Expected success_url format:
https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897
                                                                        ↑ Pipe encoded as %7C

With message:
https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_QBYwQEA...
```

### 3. Decryption Success (For Donations With Message)
```
Expected np-webhook log output:
💬 [IPN] Found encrypted message in success_url (44 chars)
📤 [NOTIFICATION] Calling GCNotificationService...
   Encrypted message included in notification payload

Expected GCNotificationService log output:
🔓 [DECRYPT] Decrypting message (44 chars)
✅ [DECRYPT] Decrypted message: 23 chars
💬 [NOTIFICATION] Including donation message in notification
```

---

## ROLLBACK PLAN

If the fix causes issues:

1. **Immediate Rollback:**
   ```bash
   # SSH into VM
   gcloud compute ssh pgp-final --zone us-central1-c --project telepay-459221

   # Restore previous version
   cd /home/kingslavxxx/TelegramFunnel/OCTOBER/10-26/TelePay10-26/services/
   cp payment_service.py payment_service.py.backup-url-encoding
   # (restore from git or previous backup)

   # Restart service
   pkill -f telepay10-26.py
   cd /home/kingslavxxx/TelegramFunnel/OCTOBER/10-26/TelePay10-26/
   source ~/TF1/venv/bin/activate
   source 11-14.env
   python telepay10-26.py &
   ```

2. **Expected Rollback State:**
   - Invoices will fail again with "success_url must be a valid uri"
   - But system is stable and unchanged

---

## DEPENDENCIES & SIDE EFFECTS

### Dependencies
- ✅ `urllib.parse` is Python standard library (no new dependencies)
- ✅ No database schema changes required
- ✅ No environment variable changes required

### Side Effects
- ✅ **None** - This is a pure URL construction fix
- ✅ Decryption flow is unaffected (parse_qs auto-decodes)
- ✅ No changes to webhook processing logic
- ✅ No changes to database operations

---

## RISK ASSESSMENT

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| URL encoding breaks decryption | ❌ None | N/A | parse_qs() auto-decodes, verified in code analysis |
| NowPayments rejects encoded URLs | ❌ None | N/A | This is the correct RFC 3986 format |
| Other query params break | ❌ None | N/A | Only encoding order_id and msg params |
| Rollback needed | 🟡 Low | Low | Simple file replacement, documented above |

**Overall Risk:** 🟢 **VERY LOW**

This fix:
1. Follows RFC 3986 URI specification
2. Was already applied successfully before (2025-11-02)
3. Matches NowPayments API requirements
4. Doesn't affect decryption (auto-decoded by parse_qs)

---

## IMPLEMENTATION CHECKLIST

### Pre-Implementation
- [ ] Review this checklist with user
- [ ] Get user approval to proceed
- [ ] Verify current working directory: `TelegramFunnel/OCTOBER/10-26`
- [ ] Verify local file exists: `TelePay10-26/services/payment_service.py`

### Implementation Steps
- [ ] Read current `payment_service.py` to verify line numbers
- [ ] Add `from urllib.parse import quote` to imports section
- [ ] Update `success_url` construction (line ~294) with `quote(order_id)`
- [ ] Update `msg` parameter (line ~300) with `quote(encrypted_msg)`
- [ ] Add inline comments explaining URL encoding

### VM Deployment
- [ ] Copy fixed file to VM: `/home/kingslavxxx/TelegramFunnel/OCTOBER/10-26/TelePay10-26/services/payment_service.py`
- [ ] Verify file on VM (check for merge conflicts)
- [ ] Restart telepay10-26.py service

### Testing
- [ ] Test donation WITHOUT message (expect success)
- [ ] Test donation WITH message (expect success)
- [ ] Verify invoice created in logs
- [ ] Complete full payment flow
- [ ] Verify decryption works (for donations with message)

### Documentation
- [ ] Update PROGRESS.md with fix summary
- [ ] Update DECISIONS.md with URL encoding decision
- [ ] Update BUGS.md if this was tracked as a bug
- [ ] Mark this checklist as complete

---

## QUESTIONS FOR USER

Before proceeding, please confirm:

1. ✅ **Approve Option 1 (urllib.parse.quote) or Option 2 (urllib.parse.urlencode)?**
   - Recommendation: **Option 1** (simpler, matches previous fix pattern)

2. ✅ **Any concerns about the decryption flow?**
   - Analysis shows it will work correctly (parse_qs auto-decodes)

3. ✅ **Ready to proceed with implementation?**
   - Once approved, I'll implement and deploy immediately

---

## HISTORICAL CONTEXT

**From BUGS_ARCH.md (2025-11-02):**

```
**BUG:** NowPayments Invoice Creation Failure - Invalid URI
**Date:** 2025-11-02
**Severity:** CRITICAL - Blocks all payment creation
**Status:** FIXED ✅

**Description:**
- NowPayments API rejecting payment invoice creation with 400 error
- Error message: `{"status":false,"statusCode":400,"code":"INVALID_REQUEST_PARAMS","message":"success_url must be a valid uri"}`

**Root Cause:**
URL encoding violation - pipe character `|` in order_id not percent-encoded

**Fix Applied:**
```python
from urllib.parse import quote

# Fixed URL construction (line 300):
success_url = f"{base_url}?order_id={quote(order_id)}"
```

**Result:** ✅ All payment invoice creation working correctly
```

**Current Issue:** The donation message feature added `&msg={encrypted_msg}` without URL encoding, re-introducing the same pattern.

**Solution:** Apply the same fix (URL encoding) to BOTH `order_id` and `msg` parameters.

---

**Status:** 🔴 **AWAITING YOUR APPROVAL TO PROCEED**
