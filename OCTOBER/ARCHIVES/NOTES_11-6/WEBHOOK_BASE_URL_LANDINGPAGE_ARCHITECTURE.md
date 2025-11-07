# WEBHOOK_BASE_URL Static Landing Page Architecture

**Date:** 2025-11-02
**Status:** 🎯 ARCHITECTURAL DESIGN
**Context:** Replace WEBHOOK_BASE_URL with static landing page to eliminate RACE condition
**Related:** WEBHOOK_BASE_URL_REDUNDANCY_ANALYSIS.md

---

## Executive Summary

This document outlines the architectural changes required to replace the current token-based `WEBHOOK_BASE_URL` redirect with a **static landing page** that provides real-time payment confirmation feedback to users while eliminating the RACE condition between browser redirects and IPN callbacks.

### Core Problem

**Current Issue:** RACE condition with dual payment triggers
```
Path 1: Browser → success_url → GCWebhook1 (with token, may use wrong amount)
Path 2: IPN → np-webhook → Cloud Tasks → GCWebhook1 (with validated amount)
Result: Non-deterministic, potential duplicate processing
```

**Solution:** Single IPN-triggered path with user-friendly landing page
```
Path 1: Browser → success_url → Static Landing Page (loading...)
Path 2: IPN → np-webhook → Cloud Tasks → GCWebhook1 → Process payment
Result: Deterministic, single source of truth, better UX
```

---

## Architecture Goals

### Primary Objectives
1. ✅ **Eliminate RACE condition** - Only IPN callback triggers payment processing
2. ✅ **Maintain user feedback** - User sees clear status updates in browser
3. ✅ **Real-time updates** - Landing page updates from loading → success
4. ✅ **Simplify architecture** - Remove token encryption/decryption complexity
5. ✅ **Reduce attack surface** - No sensitive data in URL parameters

### Non-Functional Requirements
- **Performance:** Landing page loads in < 500ms
- **Reliability:** Works even if JavaScript disabled (graceful degradation)
- **Mobile-friendly:** Responsive design for all devices
- **Accessibility:** WCAG 2.1 AA compliant
- **Cost-effective:** Use Cloud Storage (cheapest option)

---

## Proposed Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STATIC LANDING PAGE ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────────┘

1. User Completes Payment
   ┌──────────┐
   │   User   │
   │ Pays ETH │
   └────┬─────┘
        │
        ▼
   ┌────────────────┐
   │  NowPayments   │
   └────┬───────┬───┘
        │       │
        │       └───────────────────────────────────────┐
        │                                               │
        ▼ (Browser Redirect)                           ▼ (Server IPN)
   ┌─────────────────────────────┐           ┌──────────────────┐
   │  Static Landing Page        │           │  np-webhook      │
   │  (Cloud Storage/CDN)        │           │  (10-26)         │
   │                             │           └────────┬─────────┘
   │  URL: success_url?order_id= │                    │
   │                             │                    │
   │  Initial State:             │                    ▼
   │  ┌─────────────────────┐   │           Store payment_id
   │  │ 🔄 Loading...       │   │           Validate signature
   │  │                     │   │           Calculate outcome_amount_usd
   │  │ "Processing your   │   │           Update database:
   │  │  payment..."        │   │           - payment_status = "confirmed"
   │  └─────────────────────┘   │           - nowpayments_payment_id = xyz
   │                             │           - outcome_amount_usd = X.XX
   │  JavaScript Polling:        │                    │
   │  GET /api/payment-status    │                    ▼
   │      ?order_id=xxx          │           Queue to GCWebhook1
   │                             │           (Cloud Tasks)
   │  Every 2 seconds            │                    │
   │         │                   │                    ▼
   │         ▼                   │           ┌──────────────────┐
   │  ┌─────────────────────┐   │           │  GCWebhook1      │
   │  │ Payment Status      │◄──┼───────────┤  (10-26)         │
   │  │ Endpoint            │   │           └────────┬─────────┘
   │  │                     │   │                    │
   │  │ Returns:            │   │                    ▼
   │  │ {                   │   │           Process payment
   │  │   status: "pending" │   │           Route to:
   │  │   OR "confirmed"    │   │           - GCSplit1 (instant)
   │  │ }                   │   │           - GCAccumulator (threshold)
   │  └─────────────────────┘   │                    │
   │                             │                    ▼
   │  When status="confirmed":   │           ┌──────────────────┐
   │  ┌─────────────────────┐   │           │  GCWebhook2      │
   │  │ ✅ Success!         │   │           │  (Telegram)      │
   │  │                     │   │           └────────┬─────────┘
   │  │ "Check your        │   │                    │
   │  │  Telegram chat     │   │                    ▼
   │  │  with              │   │           Send invitation link
   │  │  @PayGatePrime_bot"│   │           to user via Telegram
   │  │                     │   │
   │  │ [Open Telegram] ──────►│──────► https://t.me/PayGatePrime_bot
   │  └─────────────────────┘   │
   │                             │
   │  Fallback (no JS):          │
   │  Shows static message       │
   │  "Check Telegram in 30s"    │
   └─────────────────────────────┘
```

---

## Component Breakdown

### 1. Static Landing Page (HTML + CSS + JS)

**Location:** Cloud Storage bucket `gs://paygateprime-static/`
**URL:** `https://storage.googleapis.com/paygateprime-static/payment-success.html`
**Alternative:** Custom domain via Cloud Load Balancer (optional)

#### Features

**A. Initial Loading State**
- Animated spinner or pulse effect
- Text: "Processing your payment..."
- Subtle gradient background
- PayGate Prime branding

**B. Success State (after confirmation)**
- Large green checkmark animation (fade in + scale)
- Text: "Payment Confirmed! ✅"
- Instruction: "Check your Telegram chat with @PayGatePrime_bot for your invitation link"
- Call-to-action button: "Open Telegram"
- Auto-redirect to Telegram after 5 seconds (optional)

**C. Error/Timeout State (fallback)**
- If polling fails after 60 seconds
- Text: "Payment processing is taking longer than expected"
- Instruction: "You'll receive your invitation via Telegram within 2 minutes"
- Support link: "Contact Support" → redirects to support channel

**D. Accessibility Features**
- ARIA labels for screen readers
- High contrast mode support
- Keyboard navigation
- Works without JavaScript (shows static "check Telegram" message)

---

### 2. Payment Status API Endpoint

**Purpose:** Lightweight endpoint for polling payment confirmation status

**Location:** New endpoint in existing service (options):
- **Option A:** Add to `np-webhook-10-26` (co-located with payment processing)
- **Option B:** Add to `GCWebhook1-10-26` (co-located with routing logic)
- **Option C:** New micro-service `gcpaymentstatus-10-26` (cleaner separation)

**Recommended:** **Option A** (np-webhook-10-26) - minimal infrastructure, co-located with status updates

#### Endpoint Specification

**Route:** `GET /api/payment-status`

**Query Parameters:**
- `order_id` (required) - The NowPayments order_id from invoice creation

**Response Format:**
```json
{
  "order_id": "tpay_abc123",
  "status": "pending" | "confirmed" | "failed",
  "timestamp": "2025-11-02T15:30:45Z"
}
```

**Status Definitions:**
- `pending` - Payment initiated but not yet confirmed by NowPayments IPN
- `confirmed` - IPN received, payment validated, GCWebhook1 queued
- `failed` - Payment failed or expired (if needed)

**Security Considerations:**
- **Rate limiting:** Max 30 requests/minute per IP (prevent abuse)
- **No sensitive data:** Only returns status, no user/wallet/amount info
- **CORS:** Allow `storage.googleapis.com` origin for landing page
- **No authentication required:** order_id is public (already in NowPayments URLs)

**Implementation Details:**
```python
# File: np-webhook-10-26/app.py

@app.route("/api/payment-status", methods=["GET", "OPTIONS"])
def payment_status():
    """
    Lightweight endpoint for landing page to poll payment confirmation status.
    Returns payment status based on order_id.
    """

    # Handle CORS preflight
    if request.method == "OPTIONS":
        response = make_response("", 204)
        response.headers["Access-Control-Allow-Origin"] = "https://storage.googleapis.com"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Max-Age"] = "3600"
        return response

    order_id = request.args.get("order_id")

    if not order_id:
        response = jsonify({"error": "Missing order_id parameter"}), 400
        response[0].headers["Access-Control-Allow-Origin"] = "https://storage.googleapis.com"
        return response

    # Check rate limit (simple in-memory cache or Cloud Memorystore)
    # ... rate limiting logic ...

    try:
        # Query database for payment status
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
            SELECT payment_status, updated_at
            FROM private_channel_subscriptions
            WHERE order_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """

        cur.execute(query, (order_id,))
        result = cur.fetchone()

        cur.close()
        conn.close()

        if result:
            payment_status = result[0]  # "pending", "confirmed", "failed"
            timestamp = result[1].isoformat() if result[1] else None

            response_data = {
                "order_id": order_id,
                "status": payment_status,
                "timestamp": timestamp
            }
        else:
            # Order not found (payment not yet initiated or invalid order_id)
            response_data = {
                "order_id": order_id,
                "status": "pending",
                "timestamp": None
            }

        response = jsonify(response_data), 200
        response[0].headers["Access-Control-Allow-Origin"] = "https://storage.googleapis.com"
        return response

    except Exception as e:
        print(f"❌ [STATUS_API] Error querying payment status: {e}")
        response = jsonify({"error": "Internal server error"}), 500
        response[0].headers["Access-Control-Allow-Origin"] = "https://storage.googleapis.com"
        return response
```

**Database Schema Update Required:**
```sql
-- Add payment_status column to private_channel_subscriptions if not exists
ALTER TABLE private_channel_subscriptions
ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'pending';

-- Create index for faster order_id lookups
CREATE INDEX IF NOT EXISTS idx_order_id_status
ON private_channel_subscriptions(order_id, payment_status);
```

**Performance Optimization:**
- Index on `order_id` column (if not already exists)
- Connection pooling (already implemented in database_manager)
- Consider caching recent results (Cloud Memorystore Redis) for high traffic

---

### 3. Landing Page HTML/CSS/JS

**File:** `payment-success.html`

**Key Features:**
- Self-contained (all CSS/JS inline, no external dependencies)
- Vanilla JavaScript (no frameworks, minimal payload)
- Progressive enhancement (works without JS)
- Mobile-first responsive design

**HTML Structure Outline:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Payment Processing - PayGate Prime</title>

    <!-- SEO & Social Meta Tags -->
    <meta name="description" content="Your payment is being processed. Check Telegram for your invitation.">
    <meta property="og:title" content="Payment Processing - PayGate Prime">
    <meta property="og:description" content="Your payment is being processed">

    <!-- Favicon -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,...">

    <style>
        /* Inline CSS for performance */
        /* Modern gradient background */
        /* Loading spinner animation */
        /* Success checkmark animation */
        /* Responsive design */
    </style>
</head>
<body>
    <!-- Loading State (initial) -->
    <div id="loading-state" class="container">
        <div class="logo">💳 PayGate Prime</div>
        <div class="spinner"></div>
        <h1>Processing Your Payment</h1>
        <p>Please wait while we confirm your transaction...</p>
        <div class="progress-bar">
            <div class="progress-fill"></div>
        </div>
    </div>

    <!-- Success State (hidden initially) -->
    <div id="success-state" class="container hidden">
        <div class="logo">💳 PayGate Prime</div>
        <div class="checkmark-circle">
            <svg class="checkmark" viewBox="0 0 52 52">
                <!-- Animated SVG checkmark -->
            </svg>
        </div>
        <h1>Payment Confirmed!</h1>
        <p class="main-message">
            Check your Telegram chat with
            <strong>@PayGatePrime_bot</strong>
            for your invitation link.
        </p>
        <a href="https://t.me/PayGatePrime_bot" class="telegram-button">
            Open Telegram Bot
        </a>
        <p class="small-text">Invitation sent • Check your messages</p>
    </div>

    <!-- Error/Timeout State (hidden initially) -->
    <div id="error-state" class="container hidden">
        <div class="logo">💳 PayGate Prime</div>
        <div class="warning-icon">⏳</div>
        <h1>Payment Processing</h1>
        <p class="main-message">
            Your payment is taking longer than expected.<br>
            You'll receive your Telegram invitation within 2 minutes.
        </p>
        <a href="https://t.me/PayGatePrime_bot" class="telegram-button">
            Open Telegram Bot
        </a>
        <a href="https://t.me/PayGatePrimeSupport" class="support-link">
            Contact Support
        </a>
    </div>

    <!-- Fallback for no JavaScript -->
    <noscript>
        <div class="container">
            <div class="logo">💳 PayGate Prime</div>
            <h1>Payment Received</h1>
            <p>Your payment has been received. Check your Telegram chat with <strong>@PayGatePrime_bot</strong> for your invitation link within 30 seconds.</p>
            <a href="https://t.me/PayGatePrime_bot" class="telegram-button">
                Open Telegram Bot
            </a>
        </div>
    </noscript>

    <script>
        // JavaScript for polling and state management
        (function() {
            // Parse order_id from URL
            const urlParams = new URLSearchParams(window.location.search);
            const orderId = urlParams.get('order_id');

            if (!orderId) {
                // No order_id - show error
                showError();
                return;
            }

            // Configuration
            const API_ENDPOINT = 'https://np-webhook-10-26-291176869049.us-east1.run.app/api/payment-status';
            const POLL_INTERVAL = 2000; // 2 seconds
            const MAX_ATTEMPTS = 30; // 60 seconds total (30 * 2s)

            let pollCount = 0;
            let pollInterval;

            // State management
            function showLoading() {
                document.getElementById('loading-state').classList.remove('hidden');
                document.getElementById('success-state').classList.add('hidden');
                document.getElementById('error-state').classList.add('hidden');
            }

            function showSuccess() {
                document.getElementById('loading-state').classList.add('hidden');
                document.getElementById('success-state').classList.remove('hidden');
                document.getElementById('error-state').classList.add('hidden');

                // Stop polling
                if (pollInterval) clearInterval(pollInterval);

                // Trigger checkmark animation
                animateCheckmark();
            }

            function showError() {
                document.getElementById('loading-state').classList.add('hidden');
                document.getElementById('success-state').classList.add('hidden');
                document.getElementById('error-state').classList.remove('hidden');

                // Stop polling
                if (pollInterval) clearInterval(pollInterval);
            }

            // Poll payment status
            function checkPaymentStatus() {
                pollCount++;

                fetch(`${API_ENDPOINT}?order_id=${encodeURIComponent(orderId)}`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log(`[Poll ${pollCount}] Status:`, data.status);

                        if (data.status === 'confirmed') {
                            showSuccess();
                        } else if (pollCount >= MAX_ATTEMPTS) {
                            // Timeout after 60 seconds
                            showError();
                        }
                        // Else: keep polling (status = 'pending')
                    })
                    .catch(error => {
                        console.error(`[Poll ${pollCount}] Error:`, error);

                        if (pollCount >= MAX_ATTEMPTS) {
                            showError();
                        }
                        // Else: keep polling (network error, retry)
                    });
            }

            // Checkmark animation
            function animateCheckmark() {
                const checkmark = document.querySelector('.checkmark');
                if (checkmark) {
                    checkmark.style.animation = 'checkmark-draw 1s ease-in-out forwards';
                }
            }

            // Start polling immediately
            showLoading();
            checkPaymentStatus(); // First check immediately
            pollInterval = setInterval(checkPaymentStatus, POLL_INTERVAL);
        })();
    </script>
</body>
</html>
```

**CSS Highlights:**
- Gradient background: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- Loading spinner: CSS-only animation (no images)
- Checkmark: SVG with stroke-dasharray animation
- Responsive breakpoints: Mobile (< 768px), Tablet, Desktop
- Dark mode support: `@media (prefers-color-scheme: dark)`

**JavaScript Features:**
- URL parameter parsing (order_id)
- Fetch API for polling
- State management (loading/success/error)
- Progressive timeout (60 seconds max)
- Error handling with fallback

---

## Implementation Roadmap

### Phase 1: Infrastructure Setup

**Tasks:**
1. ✅ Create Cloud Storage bucket for static hosting
2. ✅ Enable public access to bucket
3. ✅ Configure CORS on bucket
4. ✅ (Optional) Set up Cloud CDN for faster global delivery
5. ✅ (Optional) Configure custom domain via Cloud Load Balancer

**Commands:**
```bash
# Create bucket
gsutil mb -p telepay-459221 -l us-central1 gs://paygateprime-static

# Enable public access
gsutil iam ch allUsers:objectViewer gs://paygateprime-static

# Configure CORS
cat > cors.json <<EOF
[
  {
    "origin": ["*"],
    "method": ["GET"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF
gsutil cors set cors.json gs://paygateprime-static

# Set cache control for HTML
gsutil -h "Cache-Control:public, max-age=60" cp payment-success.html gs://paygateprime-static/

# Verify URL
echo "Landing page: https://storage.googleapis.com/paygateprime-static/payment-success.html"
```

---

### Phase 2: Database Schema Updates

**Tasks:**
1. ✅ Add `payment_status` column to `private_channel_subscriptions`
2. ✅ Add index on `order_id` for fast lookups
3. ✅ Update `np-webhook` to set `payment_status = 'confirmed'` on IPN

**Migration SQL:**
```sql
-- Execute on telepaydb database

-- 1. Add payment_status column
ALTER TABLE private_channel_subscriptions
ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'pending';

-- 2. Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_order_id_status
ON private_channel_subscriptions(order_id, payment_status);

-- 3. Update existing records (backfill)
UPDATE private_channel_subscriptions
SET payment_status = 'confirmed'
WHERE nowpayments_payment_id IS NOT NULL
  AND payment_status IS NULL;

-- 4. Verify migration
SELECT
    COUNT(*) as total_records,
    COUNT(CASE WHEN payment_status = 'confirmed' THEN 1 END) as confirmed,
    COUNT(CASE WHEN payment_status = 'pending' THEN 1 END) as pending
FROM private_channel_subscriptions;
```

**Update np-webhook IPN handler:**
```python
# File: np-webhook-10-26/app.py (around line 580-610)

# After successful payment validation, update payment_status
update_query = """
    UPDATE private_channel_subscriptions
    SET nowpayments_payment_id = %s,
        nowpayments_outcome_amount = %s,
        nowpayments_outcome_amount_usd = %s,
        payment_status = 'confirmed',  -- ← ADD THIS
        updated_at = NOW()
    WHERE order_id = %s
"""

cur.execute(update_query, (
    payment_id,
    outcome_amount,
    outcome_amount_usd,
    order_id
))
conn.commit()

print(f"✅ [DATABASE] Payment status updated to 'confirmed' for order_id: {order_id}")
```

---

### Phase 3: Payment Status API Endpoint

**Tasks:**
1. ✅ Add `/api/payment-status` endpoint to `np-webhook-10-26`
2. ✅ Implement rate limiting (basic)
3. ✅ Add CORS headers
4. ✅ Test endpoint with curl/Postman
5. ✅ Deploy updated `np-webhook-10-26`

**Testing:**
```bash
# Test payment status API
curl "https://np-webhook-10-26-291176869049.us-east1.run.app/api/payment-status?order_id=tpay_test123"

# Expected response:
# {"order_id": "tpay_test123", "status": "pending", "timestamp": null}
# OR
# {"order_id": "tpay_test123", "status": "confirmed", "timestamp": "2025-11-02T15:30:45"}
```

---

### Phase 4: Static Landing Page Development

**Tasks:**
1. ✅ Create `payment-success.html` with all states (loading/success/error)
2. ✅ Add CSS animations (spinner, checkmark)
3. ✅ Implement JavaScript polling logic
4. ✅ Test locally (use `python3 -m http.server`)
5. ✅ Test with mock API endpoint
6. ✅ Add accessibility features (ARIA labels, keyboard nav)
7. ✅ Test on mobile devices
8. ✅ Deploy to Cloud Storage

**Local Testing:**
```bash
# Test locally
cd /path/to/landing-page
python3 -m http.server 8080

# Open in browser
# http://localhost:8080/payment-success.html?order_id=tpay_test123

# Verify:
# - Loading spinner appears
# - Polling starts (check browser console)
# - Success state appears when API returns "confirmed"
# - Error state appears after 60 seconds if status stays "pending"
```

---

### Phase 5: TelePay Bot Integration

**Tasks:**
1. ✅ Update `TelePay10-26/start_np_gateway.py` to use new landing page URL
2. ✅ Include `order_id` in success_url parameter
3. ✅ Remove dependency on `WEBHOOK_BASE_URL` secret
4. ✅ Remove token encryption logic (no longer needed)
5. ✅ Deploy updated TelePay bot

**Code Changes:**

**File: `TelePay10-26/start_np_gateway.py`**

```python
# BEFORE (Old token-based approach):
async def create_payment_invoice(self, user_id: int, amount: float, success_url: str, order_id: str):
    """Create payment invoice with encrypted token in success_url"""
    # ... token encryption logic ...
    success_url_with_token = f"{WEBHOOK_BASE_URL}?token={encrypted_token}"

    invoice_payload = {
        "price_amount": amount,
        "price_currency": "USD",
        "order_id": order_id,
        "success_url": success_url_with_token,  # ← Token-based
        "ipn_callback_url": self.ipn_callback_url,
        # ...
    }

# AFTER (New static landing page approach):
async def create_payment_invoice(self, user_id: int, amount: float, order_id: str):
    """Create payment invoice with static landing page"""

    # Static landing page URL (no token, just order_id)
    LANDING_PAGE_URL = "https://storage.googleapis.com/paygateprime-static/payment-success.html"
    success_url = f"{LANDING_PAGE_URL}?order_id={order_id}"

    print(f"🔗 [INVOICE] success_url: {success_url}")
    print(f"ℹ️ [INVOICE] Payment processing triggered by IPN only")

    invoice_payload = {
        "price_amount": amount,
        "price_currency": "USD",
        "order_id": order_id,
        "success_url": success_url,  # ← Static landing page
        "ipn_callback_url": self.ipn_callback_url,
        "is_fixed_rate": False,
        "is_fee_paid_by_user": False
    }

    # ... rest of invoice creation ...
```

**Remove imports:**
```python
# DELETE these imports (no longer needed):
from secure_webhook import WebhookManager  # ← Remove
```

**Update method signature:**
```python
# OLD:
async def start_np_invoice(self, user_id, amount, webhook_manager, order_id):
    secure_success_url = webhook_manager.build_signed_success_url(...)  # ← Remove

# NEW:
async def start_np_invoice(self, user_id, amount, order_id):
    # No webhook_manager needed, using static landing page
```

---

### Phase 6: GCWebhook1 Deprecation (Optional)

**Tasks:**
1. ✅ Deprecate `GET /?token=...` endpoint in GCWebhook1
2. ✅ Keep `POST /process-validated-payment` endpoint (used by np-webhook)
3. ✅ Add logging to track if old endpoint is still called
4. ✅ Deploy updated GCWebhook1

**Code Changes:**

**File: `GCWebhook1-10-26/tph1-10-26.py`**

```python
@app.route("/", methods=["GET"])
def handle_legacy_success_redirect():
    """
    DEPRECATED: Legacy success_url endpoint.

    This endpoint is no longer in use as of 2025-11-02.
    All payment processing is now triggered by IPN → np-webhook → Cloud Tasks.

    If you're seeing this, the TelePay bot may not be updated yet.
    """
    print(f"⚠️ [DEPRECATED] Legacy GET /?token= endpoint called")
    print(f"⚠️ [DEPRECATED] This should not happen - check TelePay bot deployment")

    token = request.args.get("token")
    if token:
        print(f"⚠️ [DEPRECATED] Token received: {token[:20]}...")

    # Return user-friendly message
    return """
    <html>
    <head><title>Payment Processing</title></head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>⚠️ Deprecated Endpoint</h1>
        <p>This payment endpoint is no longer in use.</p>
        <p>Please check your Telegram chat with <strong>@PayGatePrime_bot</strong> for your invitation.</p>
        <a href="https://t.me/PayGatePrime_bot">Open Telegram Bot</a>
    </body>
    </html>
    """, 410  # HTTP 410 Gone

# KEEP this endpoint (used by np-webhook):
@app.route("/process-validated-payment", methods=["POST"])
def handle_validated_payment():
    """
    Process payment after IPN validation by np-webhook.

    This is the PRIMARY payment processing endpoint.
    Triggered by Cloud Tasks after np-webhook validates IPN.
    """
    # ... existing Cloud Tasks handling logic ...
```

---

### Phase 7: Testing & Validation

**End-to-End Test Checklist:**

1. ✅ **Create test payment**
   - Start TelePay bot
   - Select subscription plan
   - Generate payment invoice
   - Verify `success_url` points to landing page with `order_id`

2. ✅ **Verify redirect**
   - Complete payment on NowPayments
   - Verify browser redirected to landing page
   - Verify loading state appears
   - Verify `order_id` in URL

3. ✅ **Verify polling**
   - Open browser DevTools → Network tab
   - Verify GET requests to `/api/payment-status` every 2 seconds
   - Verify correct `order_id` in query string

4. ✅ **Verify IPN callback**
   - Check `np-webhook-10-26` logs
   - Verify IPN received and validated
   - Verify `payment_status = 'confirmed'` updated in database
   - Verify GCWebhook1 queued via Cloud Tasks

5. ✅ **Verify success state**
   - Landing page should change from loading → success
   - Green checkmark should animate
   - Message should display: "Check Telegram"
   - "Open Telegram" button should work

6. ✅ **Verify payment processing**
   - Check GCWebhook1 logs
   - Verify payment routed to GCSplit1 or GCAccumulator
   - Verify Telegram invitation sent via GCWebhook2
   - Verify user receives invitation in Telegram

7. ✅ **Verify no duplicate processing**
   - Check logs for only ONE payment processing workflow
   - Verify GCWebhook1 `GET /?token=` endpoint NOT called
   - Verify GCWebhook1 `POST /process-validated-payment` called ONCE

8. ✅ **Test error handling**
   - Test with invalid `order_id`
   - Test with network failure (block API endpoint)
   - Verify timeout after 60 seconds
   - Verify error state displayed correctly

9. ✅ **Test mobile devices**
   - Test on iPhone Safari
   - Test on Android Chrome
   - Verify responsive design
   - Verify animations work smoothly

10. ✅ **Test accessibility**
    - Test with screen reader (NVDA/JAWS)
    - Test keyboard navigation
    - Test without JavaScript (noscript fallback)
    - Verify ARIA labels present

---

### Phase 8: Cleanup (Post-Deployment)

**Tasks:**
1. ✅ Monitor production for 48 hours
2. ✅ Verify no errors in logs
3. ✅ Verify zero calls to deprecated GCWebhook1 `GET /?token=` endpoint
4. ✅ Delete `WEBHOOK_BASE_URL` secret from Secret Manager
5. ✅ Delete `SUCCESS_URL_SIGNING_KEY` secret (if no longer used)
6. ✅ Archive `secure_webhook.py` file
7. ✅ Update documentation

**Cleanup Commands:**
```bash
# After 48 hours of stable production operation:

# 1. Verify zero usage of old endpoint
gcloud logging read 'resource.type="cloud_run_revision"
    resource.labels.service_name="gcwebhook1-10-26"
    textPayload=~"DEPRECATED"'
    --limit 50 --format json

# If zero results → safe to delete secrets

# 2. Delete WEBHOOK_BASE_URL secret
gcloud secrets delete WEBHOOK_BASE_URL --project=telepay-459221

# 3. (Optional) Delete SUCCESS_URL_SIGNING_KEY if not used elsewhere
# IMPORTANT: Check if any other services still use this key
gcloud secrets delete SUCCESS_URL_SIGNING_KEY --project=telepay-459221

# 4. Archive secure_webhook.py
mkdir -p /OCTOBER/ARCHIVES/DEPRECATED-2025-11-02/
mv TelePay10-26/secure_webhook.py /OCTOBER/ARCHIVES/DEPRECATED-2025-11-02/

# 5. Update deployment docs
# (Manual step - update DEPLOYMENT_GUIDE.md, README.md, etc.)
```

---

## Architecture Comparison: Before vs After

| Aspect | Before (Token-Based) | After (Static Landing Page) |
|--------|----------------------|----------------------------|
| **success_url Points To** | GCWebhook1 with encrypted token | Static HTML page with order_id |
| **Payment Trigger** | Browser redirect OR IPN (RACE) | IPN only (deterministic) |
| **Amount Used** | May use `subscription_price` (wrong) | Always uses `outcome_amount_usd` (correct) |
| **Duplicate Processing Risk** | High (two paths to GCWebhook1) | None (single IPN-triggered path) |
| **User Feedback** | Immediate (browser redirect) | Real-time (polling + state updates) |
| **Token Encryption** | Required (HMAC signing) | Not needed (order_id is public) |
| **Secrets Required** | WEBHOOK_BASE_URL, SUCCESS_URL_SIGNING_KEY | None |
| **Infrastructure** | Cloud Run service (GCWebhook1) | Cloud Storage (static hosting) |
| **Cost** | ~$0.40/month (Cloud Run always-on) | ~$0.02/month (Cloud Storage) |
| **Latency** | ~200-500ms (token decryption + DB) | ~50-100ms (static file) |
| **Scalability** | Limited by Cloud Run instances | Unlimited (Cloud CDN) |
| **Security** | Token in URL (potential logging leak) | No sensitive data in URL |
| **Debugging** | Hard (which path was used?) | Easy (only one path) |
| **Financial Accuracy** | Low (may use wrong amount) | High (always validated amount) |

---

## Security Considerations

### Eliminated Security Risks

**1. Token Leakage**
- **Before:** Encrypted tokens in URL → risk of logging in browser history, reverse proxies, analytics
- **After:** Only public `order_id` in URL → no sensitive data exposure

**2. Token Replay Attacks**
- **Before:** Stolen token could be replayed to trigger duplicate processing
- **After:** No tokens → no replay risk

**3. Signature Verification Complexity**
- **Before:** HMAC signing logic spread across services
- **After:** No token signing/verification needed

### New Security Considerations

**1. Payment Status API Rate Limiting**
- **Risk:** Abuse of `/api/payment-status` endpoint
- **Mitigation:** Rate limit to 30 requests/min per IP
- **Implementation:** Use Cloud Armor or application-level rate limiting

**2. order_id Enumeration**
- **Risk:** Attackers could enumerate order_ids to check payment statuses
- **Mitigation:**
  - Use UUIDs for order_ids (already implemented: `tpay_<uuid>`)
  - No sensitive data returned (only status: pending/confirmed)
  - Rate limiting prevents mass enumeration

**3. CORS Configuration**
- **Risk:** Unauthorized domains calling API endpoint
- **Mitigation:**
  - Allow only `storage.googleapis.com` origin
  - Consider custom domain if using Cloud Load Balancer

**4. DDoS Protection**
- **Risk:** Mass requests to landing page or API endpoint
- **Mitigation:**
  - Cloud Storage has built-in DDoS protection
  - Consider Cloud CDN for global caching
  - Cloud Armor for API endpoint protection

---

## Performance & Cost Analysis

### Performance Improvements

**Landing Page Load Time:**
- **Target:** < 500ms to first contentful paint (FCP)
- **Optimization:**
  - Inline CSS/JS (no external requests)
  - Minified HTML (gzip compression)
  - Cloud CDN caching (optional)
  - HTTP/2 support

**Payment Status API Response Time:**
- **Target:** < 100ms per request
- **Optimization:**
  - Database index on `order_id`
  - Connection pooling
  - Optional: Redis caching for recent payments

**Polling Overhead:**
- **Frequency:** 2 seconds × 30 attempts = 60 seconds max
- **Total requests per payment:** ~15-30 (depending on IPN speed)
- **Bandwidth:** ~100 bytes per request × 30 = ~3 KB per payment
- **Cost impact:** Negligible (~$0.0001 per payment)

### Cost Comparison

| Component | Before (Token-Based) | After (Static Landing Page) | Savings |
|-----------|----------------------|----------------------------|---------|
| **Hosting** | Cloud Run (GCWebhook1) | Cloud Storage | ~90% |
| **Compute** | ~0.1 vCPU per request | Static file serving | ~95% |
| **Bandwidth** | ~1 KB per request | ~10 KB initial + 3 KB polling | -$0.0001 |
| **Total per 1000 payments** | ~$0.50 | ~$0.05 | **$0.45 savings** |

**Annual Savings (assuming 10,000 payments/year):**
- ~$4.50/year in direct hosting costs
- Additional savings: reduced Cloud Run instance hours, fewer cold starts

---

## Rollback Plan

### If Issues Arise

**Symptoms requiring rollback:**
- Payment success rate drops > 5%
- Users report not receiving invitations
- Landing page unavailable (> 1% error rate)
- Database connection issues on status API

**Rollback Procedure:**

1. **Immediate (< 5 minutes):**
   ```bash
   # Revert TelePay bot to previous revision
   gcloud run services update-traffic telepay-10-26 \
     --to-revisions=PREVIOUS_REVISION=100 \
     --region=us-central1

   # Verify old revision uses WEBHOOK_BASE_URL
   gcloud run revisions describe PREVIOUS_REVISION \
     --region=us-central1 \
     --format="value(spec.template.spec.containers[0].env)"
   ```

2. **Post-rollback (within 1 hour):**
   - Verify payment flow working with old approach
   - Investigate root cause (check logs, metrics)
   - Fix issue in staging environment
   - Re-deploy after validation

3. **Keep secrets:**
   - Do NOT delete `WEBHOOK_BASE_URL` or `SUCCESS_URL_SIGNING_KEY` until 7 days post-deployment
   - Allows instant rollback without secret recreation

---

## Monitoring & Alerting

### Key Metrics to Monitor

**1. Landing Page Performance**
- **Metric:** Page load time (FCP, LCP)
- **Target:** < 500ms for 95th percentile
- **Alert:** If > 1 second for 5 minutes
- **Dashboard:** Cloud Monitoring → Storage → Bucket metrics

**2. Payment Status API**
- **Metric:** Request latency, error rate
- **Target:** < 100ms latency, < 1% error rate
- **Alert:** If latency > 500ms or errors > 5%
- **Dashboard:** Cloud Monitoring → Cloud Run → np-webhook-10-26

**3. Payment Confirmation Rate**
- **Metric:** % of payments reaching "confirmed" status within 60 seconds
- **Target:** > 95%
- **Alert:** If < 90% for 10 minutes
- **Query:**
  ```sql
  SELECT
    COUNT(*) as total_payments,
    COUNT(CASE WHEN payment_status = 'confirmed' THEN 1 END) as confirmed,
    ROUND(COUNT(CASE WHEN payment_status = 'confirmed' THEN 1 END)::NUMERIC / COUNT(*) * 100, 2) as confirmation_rate
  FROM private_channel_subscriptions
  WHERE created_at > NOW() - INTERVAL '1 hour'
  ```

**4. Polling API Request Volume**
- **Metric:** Requests/second to `/api/payment-status`
- **Target:** ~0.5-2 RPS per concurrent payment
- **Alert:** If > 100 RPS (potential abuse)

**5. Error State Frequency**
- **Metric:** % of landing page visits reaching error/timeout state
- **Target:** < 5%
- **Alert:** If > 10% for 10 minutes
- **Implementation:** Add client-side analytics (Google Analytics or custom)

### Alerting Rules

**Create Cloud Monitoring Alert Policies:**

```bash
# Alert: Payment Status API High Error Rate
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Payment Status API - High Error Rate" \
  --condition-display-name="Error rate > 5%" \
  --condition-threshold-value=0.05 \
  --condition-threshold-duration=300s \
  --condition-filter='
    resource.type="cloud_run_revision"
    AND resource.labels.service_name="np-webhook-10-26"
    AND metric.type="run.googleapis.com/request_count"
    AND metric.labels.response_code_class="5xx"
  '

# Alert: Payment Confirmation Rate Drop
# (Requires custom metric - implement via Cloud Function querying database)
```

---

## Future Enhancements (Optional)

### Phase 2 Improvements (Post-Launch)

**1. Custom Domain**
- **Current:** `https://storage.googleapis.com/paygateprime-static/payment-success.html`
- **Future:** `https://pay.paygateprime.com/success` (branded domain)
- **Implementation:** Cloud Load Balancer → Cloud Storage backend
- **Cost:** +$18/month (Load Balancer)

**2. Real-Time WebSocket Updates**
- **Current:** Polling every 2 seconds
- **Future:** WebSocket or Server-Sent Events (SSE) for instant updates
- **Benefits:** Faster confirmation (no polling delay), less API requests
- **Implementation:** Cloud Run service with WebSocket support
- **Cost:** +$5-10/month (Cloud Run always-on instance)

**3. Analytics & Tracking**
- **Add:** Google Analytics or Plausible for landing page metrics
- **Track:** User behavior, time-to-confirmation, error rates
- **Privacy:** No sensitive payment data, only aggregated metrics

**4. Multi-Language Support**
- **Current:** English only
- **Future:** Auto-detect browser language, show localized messages
- **Languages:** English, Russian, Spanish, Chinese
- **Implementation:** JavaScript i18n library (minimal)

**5. Payment Receipt Download**
- **Feature:** Generate PDF receipt on success state
- **Implementation:** Cloud Function to generate PDF, signed Cloud Storage URL
- **Benefit:** Professional invoicing for users

**6. Progressive Web App (PWA)**
- **Feature:** Add service worker for offline support
- **Benefit:** Landing page works even without internet (cached)
- **Implementation:** Workbox.js for service worker generation

---

## Documentation Updates Required

### Files to Update

1. **DEPLOYMENT_INSTRUCTIONS.md**
   - Remove token-based success_url instructions
   - Add static landing page deployment steps
   - Update environment variables list

2. **MAIN_ARCHITECTURE_WORKFLOW.md**
   - Update payment flow diagram
   - Show IPN-only trigger path
   - Remove token encryption steps

3. **TELEPAY10-26_ENVIRONMENT_VARIABLES_COMPLETE.md**
   - Remove `WEBHOOK_BASE_URL` from required variables
   - Remove `SUCCESS_URL_SIGNING_KEY` from TelePay bot requirements
   - Mark as deprecated

4. **README.md** (if exists)
   - Update "Payment Flow" section
   - Add "Landing Page" section
   - Update troubleshooting guides

---

## Summary & Recommendations

### Final Architecture

**✅ Recommended Implementation:**

1. **Landing Page:** Cloud Storage static HTML with JavaScript polling
2. **Status API:** Lightweight endpoint in `np-webhook-10-26`
3. **Database:** Add `payment_status` column with index
4. **TelePay Bot:** Update to use static landing page URL
5. **GCWebhook1:** Deprecate `GET /?token=` endpoint (keep for 7 days)

**Timeline:** 1-2 days for complete implementation + testing

**Risk Level:** **Low** - Minimal breaking changes, easy rollback

**Effort:** **Medium** - HTML/CSS/JS development + API endpoint + deployment

### Key Benefits

1. ✅ **Eliminates RACE condition** - Single payment processing path
2. ✅ **Better UX** - Real-time loading → success feedback
3. ✅ **Financial accuracy** - Always uses validated `outcome_amount_usd`
4. ✅ **Simpler architecture** - Removes token encryption complexity
5. ✅ **Better security** - No sensitive data in URLs
6. ✅ **Lower cost** - Cloud Storage ($0.02/month) vs Cloud Run ($0.40/month)
7. ✅ **Higher performance** - Static file serving (< 100ms) vs Cloud Run (200-500ms)
8. ✅ **Easier debugging** - Single deterministic payment path

### Success Criteria

**Deployment is successful if:**
- ✅ 95%+ payment confirmation rate (same as before)
- ✅ Zero duplicate payment processing
- ✅ Landing page loads in < 500ms (95th percentile)
- ✅ Payment status API responds in < 100ms
- ✅ 100% of users see success state within 60 seconds
- ✅ Zero errors related to token decryption (removed)
- ✅ Zero calls to deprecated GCWebhook1 `GET /?token=` endpoint

---

## Next Steps

### Immediate Actions

1. **Review & Approve Architecture** - Get stakeholder sign-off on this design
2. **Create Implementation Checklist** - Break down into actionable tasks
3. **Set Up Development Environment** - Local testing for landing page
4. **Schedule Deployment Window** - Low-traffic period (2-4 AM UTC)
5. **Prepare Rollback Plan** - Document procedure, keep old secrets available

### Implementation Order

**Week 1: Development**
- Day 1-2: Create landing page HTML/CSS/JS
- Day 3: Implement payment status API endpoint
- Day 4: Database migration
- Day 5: TelePay bot integration

**Week 2: Testing & Deployment**
- Day 1-2: End-to-end testing in staging
- Day 3: Deploy to production
- Day 4-5: Monitor production, fix issues
- Day 6-7: Cleanup (delete old secrets, update docs)

---

**Document Version:** 1.0
**Created:** 2025-11-02
**Status:** 🎯 READY FOR IMPLEMENTATION
**Estimated Effort:** 8-12 hours development + testing
**Risk Assessment:** **LOW** ✅
**Recommended:** **YES** ✅
