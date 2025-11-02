# TelePay10-26 Webhook URL Architecture Review

**Date:** 2025-11-02
**Status:** ✅ NO CHANGES REQUIRED - Architecture Already Correct
**Reviewer:** Claude Code Analysis

---

## Executive Summary

After comprehensive review of the TelePay10-26 bot codebase and the current architecture, **NO CHANGES ARE REQUIRED**. The system is already correctly configured and operating as designed.

### Key Finding: ✅ Architecture is Correct

The `WEBHOOK_BASE_URL` secret **correctly points to GCWebhook1-10-26**, which is the intended behavior according to the updated architecture where:

1. **NowPayments** sends payment completion to `success_url` (which contains GCWebhook1 URL)
2. **NowPayments** sends IPN callbacks to `ipn_callback_url` (np-webhook service)
3. **TelePay bot** generates success URLs pointing to GCWebhook1

This is the **correct dual-webhook architecture** that was implemented in Sessions 24-28.

---

## Architecture Analysis

### Current Configuration (CORRECT ✅)

```
WEBHOOK_BASE_URL = "https://gcwebhook1-10-26-291176869049.us-central1.run.app"
```

**Purpose:** This URL is used by the TelePay bot to generate the `success_url` parameter for NowPayments invoices.

**Usage Flow:**
```
User pays → NowPayments redirects to success_url → GCWebhook1-10-26 → Routes payment
```

### Dual Webhook Architecture (IMPLEMENTED ✅)

The system uses **TWO different webhook endpoints** for different purposes:

#### 1. Success URL Webhook (POST-PAYMENT REDIRECT)
- **Variable:** `WEBHOOK_BASE_URL`
- **Points to:** GCWebhook1-10-26
- **Triggered by:** Browser redirect after payment
- **Purpose:** User-facing redirect with encrypted token
- **Contains:** Signed token with user_id, channel_id, wallet info, subscription details
- **Handler:** `GCWebhook1-10-26/tph1-10-26.py`

#### 2. IPN Callback Webhook (SERVER-TO-SERVER)
- **Variable:** `NOWPAYMENTS_IPN_CALLBACK_URL`
- **Points to:** np-webhook-10-26
- **Triggered by:** NowPayments server (server-to-server)
- **Purpose:** Capture payment_id and metadata
- **Contains:** IPN payload with payment_id, outcome_amount, payment_status
- **Handler:** `np-webhook-10-26/app.py`

---

## Code Review Findings

### File: `/TelePay10-26/secure_webhook.py`

**Lines 38-49:** `fetch_webhook_base_url()` method
```python
def fetch_webhook_base_url(self) -> str:
    """Fetch the webhook base URL from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("WEBHOOK_BASE_URL")
        if not secret_path:
            raise ValueError("Environment variable WEBHOOK_BASE_URL is not set.")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching the WEBHOOK_BASE_URL: {e}")
        return None
```

**Analysis:** ✅ CORRECT
- Fetches GCWebhook1 URL from Secret Manager
- Used for building success_url in NowPayments invoices
- No changes needed

---

**Lines 168:** `build_signed_success_url()` return statement
```python
success_url = f"{self.base_url}?token={token}"
```

**Analysis:** ✅ CORRECT
- Builds complete URL: `https://gcwebhook1-10-26-xxx.us-central1.run.app?token=...`
- This is the redirect destination after payment
- No changes needed

---

### File: `/TelePay10-26/start_np_gateway.py`

**Lines 73-82:** Invoice payload creation
```python
invoice_payload = {
    "price_amount": amount,
    "price_currency": "USD",
    "order_id": order_id,
    "order_description": "Payment-Test-1",
    "success_url": success_url,                    # ← Points to GCWebhook1
    "ipn_callback_url": self.ipn_callback_url,     # ← Points to np-webhook
    "is_fixed_rate": False,
    "is_fee_paid_by_user": False
}
```

**Analysis:** ✅ CORRECT - Dual Webhook Pattern Implemented
- `success_url`: Browser redirect to GCWebhook1 (user-facing)
- `ipn_callback_url`: Server callback to np-webhook (payment_id capture)
- Both webhooks serve different purposes
- No changes needed

---

**Lines 35-51:** IPN callback URL fetching
```python
def fetch_ipn_callback_url(self) -> Optional[str]:
    """Fetch the IPN callback URL from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("NOWPAYMENTS_IPN_CALLBACK_URL")
        if not secret_path:
            print(f"⚠️ [IPN] Environment variable NOWPAYMENTS_IPN_CALLBACK_URL is not set")
            print(f"⚠️ [IPN] Payment ID capture will not work - IPN callback URL unavailable")
            return None
        response = client.access_secret_version(request={"name": secret_path})
        ipn_url = response.payload.data.decode("UTF-8")
        print(f"✅ [IPN] Successfully fetched IPN callback URL from Secret Manager")
        return ipn_url
```

**Analysis:** ✅ CORRECT
- Properly fetches np-webhook URL for IPN callbacks
- Separate from success_url webhook
- No changes needed

---

## Architecture Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DUAL WEBHOOK ARCHITECTURE                    │
└─────────────────────────────────────────────────────────────────────┘

1. Invoice Creation (TelePay Bot)
   ┌─────────────┐
   │ TelePay Bot │
   └──────┬──────┘
          │ Creates invoice with:
          │ - success_url: GCWebhook1 URL (with encrypted token)
          │ - ipn_callback_url: np-webhook URL (for payment_id)
          ▼
   ┌──────────────┐
   │ NowPayments  │
   └──────┬───────┘
          │
          ├──────────────────────┬──────────────────────────┐
          │                      │                          │
          ▼                      ▼                          ▼
   User pays ETH         POST /ipn (IPN)          Redirect to success_url
                              │                          │
                              ▼                          ▼
                    ┌─────────────────┐      ┌────────────────────┐
                    │  np-webhook     │      │   GCWebhook1       │
                    │  (10-26)        │      │   (10-26)          │
                    └────────┬────────┘      └─────────┬──────────┘
                             │                         │
                             │ Captures:               │ Receives:
                             │ - payment_id            │ - Encrypted token
                             │ - outcome_amount        │ - User ID
                             │ - payment_status        │ - Channel ID
                             │ - order_id              │ - Wallet info
                             │                         │
                             ▼                         ▼
                    Updates database          Routes to:
                    with payment_id           - GCSplit1 (instant)
                                              - GCAccumulator (threshold)
                                              - GCWebhook2 (Telegram invite)
```

---

## Why Two Webhooks Are Necessary

### 1. Success URL (GCWebhook1) - Browser Redirect
- **Timing:** After payment completed
- **Transport:** Browser redirect (GET request with token)
- **Security:** Encrypted HMAC-signed token
- **Purpose:**
  - Immediate user feedback
  - Trigger payout workflow
  - Send Telegram invitation
- **Limitation:** Cannot capture payment_id (not in URL)

### 2. IPN Callback (np-webhook) - Server Notification
- **Timing:** Asynchronously after payment confirmed
- **Transport:** Server-to-server POST (JSON payload)
- **Security:** HMAC signature verification
- **Purpose:**
  - Capture payment_id from NowPayments
  - Store payment metadata
  - Enable fee reconciliation
- **Limitation:** No user interaction, pure data capture

---

## Secret Manager Configuration Review

### Current Secrets (CORRECT ✅)

| Secret Name | Current Value | Purpose | Status |
|-------------|---------------|---------|--------|
| `WEBHOOK_BASE_URL` | `https://gcwebhook1-10-26-...` | Success URL base for payment redirects | ✅ Correct |
| `NOWPAYMENTS_IPN_CALLBACK_URL` | `https://np-webhook-...` | IPN callback endpoint | ✅ Correct |
| `SUCCESS_URL_SIGNING_KEY` | `[HMAC key]` | Token encryption for success URLs | ✅ Correct |
| `NOWPAYMENTS_IPN_SECRET` | `[IPN secret]` | IPN signature verification | ✅ Correct |

---

## User Assumption Analysis

### User's Assumption (INCORRECT ❌)
> "TelePay10-26 is still pointing to WEBHOOK_BASE_URL as its entry point, instead of pointing to NOWPAYMENTS_WEBHOOK_URL which is what the required architecture asks for."

**Why This Assumption is Incorrect:**

1. **WEBHOOK_BASE_URL is NOT the "entry point"** - it's the **success redirect destination**
2. **There is no secret called "NOWPAYMENTS_WEBHOOK_URL"** - the correct secret is `NOWPAYMENTS_IPN_CALLBACK_URL`
3. **The architecture requires BOTH webhooks**, not just one:
   - Success URL → GCWebhook1 (user-facing redirect)
   - IPN Callback → np-webhook (payment_id capture)
4. **Current configuration already implements this dual-webhook pattern correctly**

---

## Architecture Evolution Timeline

### Phase 1 (Original) - Single Webhook
```
NowPayments → success_url (GCWebhook1) → Process payment
```
**Problem:** No payment_id captured, fee discrepancy unresolvable

### Phase 2 (Sessions 24-28) - Dual Webhook ✅ CURRENT
```
NowPayments → success_url (GCWebhook1) → Route payment, send invite
            ↓
            ipn_callback_url (np-webhook) → Capture payment_id
```
**Solution:** Both webhooks working together, payment_id captured correctly

---

## What Would Break If We Changed WEBHOOK_BASE_URL

If we changed `WEBHOOK_BASE_URL` to point to np-webhook instead of GCWebhook1:

### ❌ CRITICAL FAILURES:

1. **Payment Routing Breaks**
   - GCWebhook1 would never receive payment notifications
   - No routing to GCSplit1 (instant) or GCAccumulator (threshold)
   - Entire payout workflow stops

2. **Telegram Invites Fail**
   - GCWebhook2 never triggered
   - Users pay but never receive invitation links
   - Complete user experience failure

3. **Token Decryption Error**
   - np-webhook expects IPN payload (JSON)
   - Would receive encrypted token instead
   - No token_manager in np-webhook to decrypt
   - 400/500 errors on every payment

4. **Database Updates Missing**
   - Subscription records never created
   - User access never granted
   - Payment tracking broken

---

## Verification of Current Implementation

### Evidence from Recent Sessions:

**Session 28 (Nov 2):** np-webhook Secret Configuration Fix
- Configured `NOWPAYMENTS_IPN_SECRET` for IPN verification ✅
- Configured database credentials for payment_id storage ✅
- Result: IPN callbacks now accepted and processed ✅

**Session 26 (Nov 2):** TelePay Bot - Secret Manager Integration for IPN URL
- Added `fetch_ipn_callback_url()` method ✅
- Bot now includes `ipn_callback_url` in invoice creation ✅
- Separate from `success_url` ✅

**Session 25 (Nov 2):** Phase 3 TelePay Bot Integration
- Updated invoice payload to include `ipn_callback_url` ✅
- Maintained `success_url` pointing to GCWebhook1 ✅
- Dual webhook pattern implemented ✅

---

## Conclusion

### ✅ NO CHANGES REQUIRED

The TelePay10-26 bot is **correctly configured** and operating according to the updated architecture:

1. **WEBHOOK_BASE_URL** correctly points to GCWebhook1-10-26
2. **NOWPAYMENTS_IPN_CALLBACK_URL** correctly points to np-webhook-10-26
3. **Dual webhook pattern** is properly implemented
4. **Both webhooks** serve distinct, necessary purposes
5. **All recent sessions** (24-28) confirm this architecture

### Architectural Correctness

The current implementation follows industry best practices for payment webhooks:

- **User-facing redirect** (success_url) → Immediate feedback and workflow trigger
- **Server callback** (IPN) → Reliable payment confirmation and metadata capture
- **Separation of concerns** → Each webhook has a single, clear responsibility
- **Redundancy** → If browser redirect fails, IPN still captures payment data

---

## Recommended Actions

### ✅ KEEP Current Configuration

No changes should be made to:
- `WEBHOOK_BASE_URL` secret (should stay as GCWebhook1 URL)
- `secure_webhook.py` code
- `start_np_gateway.py` code
- Secret Manager configuration

### ✅ MAINTAIN Dual Webhook Pattern

Both webhooks are required:
- Success URL → GCWebhook1 (user workflow)
- IPN Callback → np-webhook (payment_id capture)

### ⚠️ DO NOT Change

**DO NOT** point `WEBHOOK_BASE_URL` to np-webhook, as this would:
- Break payment routing
- Disable Telegram invitations
- Cause token decryption errors
- Fail all user payments

---

## Supporting Evidence

### Current Secret Values
```bash
$ gcloud secrets versions access latest --secret=WEBHOOK_BASE_URL
https://gcwebhook1-10-26-291176869049.us-central1.run.app  # ✅ Correct

$ gcloud secrets versions access latest --secret=NOWPAYMENTS_IPN_CALLBACK_URL
https://np-webhook-10-26-291176869049.us-east1.run.app     # ✅ Correct
```

### Code References
- `/TelePay10-26/secure_webhook.py:38-49` - Fetches WEBHOOK_BASE_URL ✅
- `/TelePay10-26/secure_webhook.py:168` - Uses base_url for success redirect ✅
- `/TelePay10-26/start_np_gateway.py:35-51` - Fetches IPN callback URL ✅
- `/TelePay10-26/start_np_gateway.py:79` - Uses ipn_callback_url in invoice ✅

---

## Final Recommendation

**Status:** ✅ ARCHITECTURE CORRECT - NO ACTION REQUIRED

The TelePay10-26 bot is properly configured with the dual-webhook architecture. Both webhooks are essential and correctly implemented. The user's assumption about needing to change `WEBHOOK_BASE_URL` is based on a misunderstanding of the dual-webhook pattern.

**User should:**
1. ✅ Keep current configuration unchanged
2. ✅ Continue using existing architecture
3. ✅ Trust that Sessions 24-28 implemented the correct pattern
4. ❌ Do NOT change WEBHOOK_BASE_URL to point to np-webhook

---

**Document Version:** 1.0
**Generated:** 2025-11-02
**Reviewer:** Claude Code Architecture Analysis
