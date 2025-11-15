# Debug Logging Implementation Summary

**Date:** 2025-11-15
**Status:** ✅ **IMPLEMENTATION COMPLETE - READY FOR TESTING**

---

## PURPOSE

Added comprehensive debug logging to track the complete donation message encryption and URL encoding workflow for troubleshooting invoice creation issues.

---

## IMPLEMENTATION OVERVIEW

### Files Modified

1. **`TelePay10-26/bot/conversations/donation_conversation.py`**
   - Lines 371-377: Log original donation message before passing to payment service
   - Lines 390-393: Log final invoice URL returned from payment service

2. **`TelePay10-26/services/payment_service.py`**
   - Lines 297-321: Log order_id encoding and complete message encryption workflow

3. **`TelePay10-26/shared_utils/message_encryption.py`**
   - Lines 80, 85, 89-90: Log each step of encryption process

---

## COMPLETE DEBUG FLOW

### Test Case 1: Donation WITH Message

**User Input:** "Test message 123"

**Expected Terminal Output:**

```
2025-11-15 04:20:16,663 - bot.conversations.donation_conversation - INFO - 💝 [DONATION] Finalizing payment for user 6271402111
2025-11-15 04:20:16,663 - bot.conversations.donation_conversation - INFO -    Amount: $5.00
2025-11-15 04:20:16,663 - bot.conversations.donation_conversation - INFO -    Channel: -1003377958897
2025-11-15 04:20:16,663 - bot.conversations.donation_conversation - INFO -    Message: Yes

📝 [DEBUG] Original donation message received:
   Input text: 'Test message 123'
   Length: 16 chars
   Type: str

🔑 [DEBUG] Order ID encoding:
   Original order_id: 'PGP-6271402111|-1003377958897'
   URL-encoded order_id: 'PGP-6271402111%7C-1003377958897'

🔗 [DEBUG] Base success_url (before message): https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897

2025-11-15 04:20:17,165 - services.payment_service - INFO - 💬 [PAYMENT] Including donation message in invoice

🔐 [DEBUG] Message encryption process:
   Step 1 - Original message: 'Test message 123'

2025-11-15 04:20:17,165 - shared_utils.message_encryption - INFO - 🔐 [ENCRYPT] Encrypting message (16 chars)
   🔤 [DEBUG] Step 1 - UTF-8 encode: 16 bytes
   🗜️ [DEBUG] Step 2 - Compressed: 22 bytes (ratio: 0.73x)
   🔐 [DEBUG] Step 3 - Base64url encoded: 30 chars
   🔐 [DEBUG] Final encrypted output: 'KLUv_QBYwQEAVGVzdCBtZXNzYWdl'

2025-11-15 04:20:17,172 - shared_utils.message_encryption - INFO - ✅ [ENCRYPT] Encrypted message: 30 chars

   Step 2 - After encryption (base64url): 'KLUv_QBYwQEAVGVzdCBtZXNzYWdl'
   Step 3 - URL-encoded encrypted msg: 'KLUv_QBYwQEAVGVzdCBtZXNzYWdl'

2025-11-15 04:20:17,173 - services.payment_service - INFO -    Encrypted message length: 30 chars

🔗 [DEBUG] Final success_url (with message): https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_QBYwQEAVGVzdCBtZXNzYWdl

2025-11-15 04:20:17,173 - services.payment_service - WARNING - ⚠️ [PAYMENT] Creating invoice without IPN callback - payment_id won't be captured
2025-11-15 04:20:17,173 - services.payment_service - INFO - 📋 [PAYMENT] Creating invoice: user=6271402111, amount=$5.00, order=PGP-6271402111|-1003377958897
2025-11-15 04:20:17,514 - services.payment_service - INFO - ✅ [PAYMENT] Invoice created successfully
2025-11-15 04:20:17,514 - services.payment_service - INFO -    Invoice ID: 5140807937
2025-11-15 04:20:17,514 - services.payment_service - INFO -    Order ID: PGP-6271402111|-1003377958897
2025-11-15 04:20:17,514 - services.payment_service - INFO -    Amount: $5.00 USD
2025-11-15 04:20:17,514 - services.payment_service - WARNING -    ⚠️ No IPN callback configured

🔗 [DEBUG] Final invoice URL returned from payment_service:
   URL: https://nowpayments.io/payment/?iid=5140807937
   URL length: 58 chars

2025-11-15 04:20:17,777 - bot.conversations.donation_conversation - INFO - ✅ [DONATION] Invoice created: https://nowpayments.io/payment/?iid=5140807937
```

---

### Test Case 2: Donation WITHOUT Message

**User Action:** Click "💰 Skip Message - Donate Now"

**Expected Terminal Output:**

```
2025-11-15 04:25:10,123 - bot.conversations.donation_conversation - INFO - 💝 [DONATION] Finalizing payment for user 6271402111
2025-11-15 04:25:10,123 - bot.conversations.donation_conversation - INFO -    Amount: $10.00
2025-11-15 04:25:10,123 - bot.conversations.donation_conversation - INFO -    Channel: -1003377958897
2025-11-15 04:25:10,123 - bot.conversations.donation_conversation - INFO -    Message: No

📝 [DEBUG] No donation message provided (Skip Message clicked)

🔑 [DEBUG] Order ID encoding:
   Original order_id: 'PGP-6271402111|-1003377958897'
   URL-encoded order_id: 'PGP-6271402111%7C-1003377958897'

🔗 [DEBUG] Base success_url (before message): https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897

2025-11-15 04:25:10,456 - services.payment_service - WARNING - ⚠️ [PAYMENT] Creating invoice without IPN callback - payment_id won't be captured
2025-11-15 04:25:10,456 - services.payment_service - INFO - 📋 [PAYMENT] Creating invoice: user=6271402111, amount=$10.00, order=PGP-6271402111|-1003377958897
2025-11-15 04:25:10,789 - services.payment_service - INFO - ✅ [PAYMENT] Invoice created successfully
2025-11-15 04:25:10,789 - services.payment_service - INFO -    Invoice ID: 5140807938
2025-11-15 04:25:10,789 - services.payment_service - INFO -    Order ID: PGP-6271402111|-1003377958897
2025-11-15 04:25:10,789 - services.payment_service - INFO -    Amount: $10.00 USD
2025-11-15 04:25:10,789 - services.payment_service - WARNING -    ⚠️ No IPN callback configured

🔗 [DEBUG] Final invoice URL returned from payment_service:
   URL: https://nowpayments.io/payment/?iid=5140807938
   URL length: 58 chars

2025-11-15 04:25:11,012 - bot.conversations.donation_conversation - INFO - ✅ [DONATION] Invoice created: https://nowpayments.io/payment/?iid=5140807938
```

---

## KEY DEBUG POINTS TO VERIFY

### ✅ **1. Original Message Capture**
```
📝 [DEBUG] Original donation message received:
   Input text: 'Test message 123'
   Length: 16 chars
   Type: str
```
**Verify:** Message text matches what user typed

---

### ✅ **2. Order ID URL Encoding**
```
🔑 [DEBUG] Order ID encoding:
   Original order_id: 'PGP-6271402111|-1003377958897'
   URL-encoded order_id: 'PGP-6271402111%7C-1003377958897'
```
**Verify:** Pipe `|` character converted to `%7C`

---

### ✅ **3. Base success_url Construction**
```
🔗 [DEBUG] Base success_url (before message): https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897
```
**Verify:** URL contains encoded order_id parameter

---

### ✅ **4. Encryption Process**
```
🔐 [DEBUG] Message encryption process:
   Step 1 - Original message: 'Test message 123'

🔐 [ENCRYPT] Encrypting message (16 chars)
   🔤 [DEBUG] Step 1 - UTF-8 encode: 16 bytes
   🗜️ [DEBUG] Step 2 - Compressed: 22 bytes (ratio: 0.73x)
   🔐 [DEBUG] Step 3 - Base64url encoded: 30 chars
   🔐 [DEBUG] Final encrypted output: 'KLUv_QBYwQEAVGVzdCBtZXNzYWdl'
```
**Verify:**
- UTF-8 byte count matches character count
- Compression shows compression ratio
- Base64url output is URL-safe (no `+`, `/`, or `=`)
- Final encrypted string logged

---

### ✅ **5. URL Encoding of Encrypted Message**
```
   Step 2 - After encryption (base64url): 'KLUv_QBYwQEAVGVzdCBtZXNzYWdl'
   Step 3 - URL-encoded encrypted msg: 'KLUv_QBYwQEAVGVzdCBtZXNzYWdl'
```
**Verify:** Base64url and URL-encoded versions match (base64url already URL-safe)

---

### ✅ **6. Final success_url with Message**
```
🔗 [DEBUG] Final success_url (with message): https://www.paygateprime.com/payment-processing?order_id=PGP-6271402111%7C-1003377958897&msg=KLUv_QBYwQEAVGVzdCBtZXNzYWdl
```
**Verify:**
- Contains both `order_id` and `msg` parameters
- Pipe character encoded as `%7C`
- Message parameter is base64url string

---

### ✅ **7. Invoice Creation Success**
```
✅ [PAYMENT] Invoice created successfully
   Invoice ID: 5140807937
   Order ID: PGP-6271402111|-1003377958897
   Amount: $5.00 USD
```
**Verify:** NowPayments accepted the success_url (no 400 error)

---

### ✅ **8. Final Invoice URL**
```
🔗 [DEBUG] Final invoice URL returned from payment_service:
   URL: https://nowpayments.io/payment/?iid=5140807937
   URL length: 58 chars
```
**Verify:** Invoice URL ready to send to user

---

## TROUBLESHOOTING GUIDE

### If Invoice Creation Fails (HTTP 400)

**Check Debug Output:**

1. **Order ID Encoding:**
   - ❌ BAD: `Original order_id: 'PGP-123|-456'` → `URL-encoded: 'PGP-123|-456'` (no encoding)
   - ✅ GOOD: `Original order_id: 'PGP-123|-456'` → `URL-encoded: 'PGP-123%7C-456'` (pipe encoded)

2. **Encrypted Message Encoding:**
   - ✅ GOOD: Base64url output has no `+`, `/`, or `=` characters
   - ❌ BAD: If you see those characters, encryption is using regular base64 (not base64url)

3. **Final success_url:**
   - ✅ GOOD: Contains `%7C` instead of `|`
   - ✅ GOOD: Message parameter is base64url string
   - ❌ BAD: Contains unencoded special characters

---

### If Decryption Fails on IPN Callback

**Check Debug Output:**

1. **Encrypted Output:**
   ```
   🔐 [DEBUG] Final encrypted output: 'KLUv_QBYwQEAVGVzdCBtZXNzYWdl'
   ```
   - Copy this string
   - Manually test decryption in Python console

2. **Round-Trip Test:**
   ```python
   from shared_utils.message_encryption import encrypt_donation_message, decrypt_donation_message

   original = "Test message 123"
   encrypted = encrypt_donation_message(original)
   decrypted = decrypt_donation_message(encrypted)

   print(f"Original:  '{original}'")
   print(f"Encrypted: '{encrypted}'")
   print(f"Decrypted: '{decrypted}'")
   print(f"Match: {original == decrypted}")
   ```

---

## DEPLOYMENT CHECKLIST

- [x] Debug logging added to donation_conversation.py
- [x] Debug logging added to payment_service.py
- [x] Debug logging added to message_encryption.py
- [x] PROGRESS.md updated
- [ ] **GitHub sync (USER ACTION)**
- [ ] **VM deployment (USER ACTION)**
- [ ] **Test donation with message (USER ACTION)**
- [ ] **Test donation without message (USER ACTION)**
- [ ] **Verify debug output matches expected format (USER ACTION)**

---

## WHAT TO LOOK FOR IN LOGS

### ✅ **SUCCESS INDICATORS:**

1. **Order ID encoding shows `%7C`**
2. **Encrypted message is base64url format**
3. **Final success_url has both `order_id` and `msg` parameters**
4. **Invoice created successfully (no 400 error)**
5. **Invoice URL returned from NowPayments**

### ❌ **FAILURE INDICATORS:**

1. **Order ID not encoded (still shows `|`)**
2. **Encrypted message has `+`, `/`, or `=` characters**
3. **success_url missing parameters**
4. **HTTP 400 error: "success_url must be a valid uri"**
5. **No invoice URL returned**

---

## SUMMARY

**What was added:**
- Comprehensive debug logging at 8 key points in the donation message workflow
- Visibility into encryption → URL encoding → success_url construction
- Easy verification of URL encoding correctness

**Why it matters:**
- Troubleshoot invoice creation failures quickly
- Verify encryption/decryption round-trip
- Validate NowPayments API submissions

**Ready for deployment:** ✅ YES

---

**Status:** 🟢 **IMPLEMENTATION COMPLETE - AWAITING USER TESTING**
