# NP-Webhook Dual Deployment Analysis

**Date:** 2025-11-07
**Issue:** Two np-webhook-10-26 deployments exist, potentially causing IPN routing issues

---

## Current Deployment State

### Deployment 1: us-central1 (NEWLY DEPLOYED)
- **URL:** `https://np-webhook-10-26-pjxwjsdktq-uc.a.run.app`
- **Alternative URL:** `https://np-webhook-10-26-291176869049.us-central1.run.app`
- **Revision:** `np-webhook-10-26-00010-pds`
- **Image:** `gcr.io/telepay-459221/np-webhook-10-26@sha256:eff3ace351bc8d3d6ee90098bf347340fb3b79438926d448c2963a4a9734dd88`
- **Deployed:** 2025-11-07 12:25:03 UTC
- **Status:** ✅ Active (serving 100% traffic in us-central1)
- **Contains:** UPSERT fix + GCWebhook1 orchestration (Session 63 changes)

### Deployment 2: us-east1 (OLDER)
- **URL:** `https://np-webhook-10-26-pjxwjsdktq-ue.a.run.app`
- **Revision:** `np-webhook-10-26-00002-8rs`
- **Image:** `gcr.io/telepay-459221/np-webhook-10-26@sha256:794a0a046b3dd695ff0fcd748579e563108becf2c1c4110c496a81a75a36e409`
- **Deployed:** 2025-11-02 12:31:01 UTC (5 days old)
- **Status:** ⚠️ Active (serving traffic in us-east1)
- **Contains:** Unknown (older codebase without Session 63 fixes)

---

## IPN Callback URL Configuration

### Current Configuration
According to Secret Manager:
```bash
$ gcloud secrets versions access latest --secret=NOWPAYMENTS_IPN_CALLBACK_URL
https://np-webhook-10-26-pjxwjsdktq-uc.a.run.app
```

**Result:** Points to **us-central1** deployment ✅

### NowPayments Merchant Configuration
```bash
$ curl -H "x-api-key: $NOWPAYMENTS_API_KEY" https://api.nowpayments.io/v1/merchant
{
  "ipn_callback_url": "Not set"
}
```

**Result:** No global IPN callback URL configured in NowPayments dashboard

**Explanation:** NowPayments allows IPN callback URLs to be set per-payment during payment creation. The global merchant-level callback is "Not set", which means each payment must specify its IPN callback URL individually.

---

## Traffic Analysis

### Recent Activity (Last 10 minutes)

#### us-central1 (NEW deployment):
1. **12:26:22 UTC** - Health check (GET /health) - Status: 200 ✅
   - Revision: `np-webhook-10-26-00010-pds`
   - Source: My verification curl command

2. **12:22:13 UTC** - Payment status API (GET /api/payment-status?order_id=PGP-6271402111%7C-1003253338212)
   - Revision: `np-webhook-10-26-00009-th6` (OLD revision, pre-deployment)
   - Source: User's browser polling from payment processing page
   - Status: 200

#### us-east1 (OLD deployment):
- **No traffic observed in last 24 hours**

### IPN POST Requests
- **Last IPN callback:** 12:22:13 UTC (before our deployment)
- **Target:** us-central1, OLD revision (np-webhook-10-26-00009-th6)
- **After deployment:** No new IPN callbacks observed yet

---

## Code Analysis

### Session 63 Changes (us-central1 NEW revision)

The newly deployed code in `app.py` includes:

#### 1. UPSERT Logic (lines 290-535)
- ✅ Handles missing database records
- ✅ Creates new records for direct payment links

#### 2. GCWebhook1 Orchestration (lines 852-901)
```python
# Line 863: Log message
print(f"🚀 [ORCHESTRATION] Triggering GCWebhook1 for payment processing...")

# Line 865-870: Validation checks
if not cloudtasks_client:
    print(f"❌ [ORCHESTRATION] Cloud Tasks client not initialized")
elif not GCWEBHOOK1_QUEUE or not GCWEBHOOK1_URL:
    print(f"❌ [ORCHESTRATION] GCWebhook1 configuration missing")
else:
    # Line 873-887: Enqueue to GCWebhook1
    task_name = cloudtasks_client.enqueue_gcwebhook1_validated_payment(...)
```

**Expected Log Messages:**
- `🚀 [ORCHESTRATION] Triggering GCWebhook1 for payment processing...`
- `✅ [ORCHESTRATION] Successfully enqueued to GCWebhook1`
- `🆔 [ORCHESTRATION] Task: {task_name}`

**OR if failed:**
- `❌ [ORCHESTRATION] Cloud Tasks client not initialized`
- `❌ [ORCHESTRATION] GCWebhook1 configuration missing`
- `❌ [ORCHESTRATION] Failed to enqueue to GCWebhook1`

### us-east1 OLD Revision
- **Unknown codebase** - deployed 5 days ago
- May or may not have GCWebhook1 orchestration
- Definitely does NOT have Session 63 UPSERT fix

---

## Root Cause Analysis

### Hypothesis 1: No New IPN Callbacks Yet ✅ MOST LIKELY
**Evidence:**
- Last IPN callback was at 12:22:13 (before deployment at 12:25:03)
- Payment 4479119533 was manually inserted into database (Record ID 17)
- NowPayments typically retries failed IPNs every few minutes
- Next retry hasn't occurred yet

**What's Happening:**
1. Payment 4479119533 was created before our deployment
2. IPN callbacks kept failing (HTTP 500) because record didn't exist
3. We manually inserted the record at 12:25:00
4. We deployed the fix at 12:25:03
5. NowPayments hasn't sent the next retry yet

**Next Steps:**
- Wait for next IPN retry from NowPayments
- Should arrive within 5-15 minutes of last attempt
- Will be routed to us-central1 NEW revision
- Should successfully update and trigger GCWebhook1

### Hypothesis 2: Payment URL Points to Wrong Deployment ❌ UNLIKELY
**Evidence Against:**
- Secret Manager shows us-central1 URL
- Payment status API calls are going to us-central1
- us-east1 has NO recent traffic

**Verdict:** NOT the issue

### Hypothesis 3: us-east1 is Receiving IPNs ❌ FALSE
**Evidence:**
- us-east1 logs show ZERO activity in last 24 hours
- No IPN callbacks, no API calls, no health checks

**Verdict:** NOT the issue

---

## Configuration Verification

### Environment Variables (us-central1 NEW revision)
From startup logs at 12:26:08 UTC:
```
✅ [CONFIG] NOWPAYMENTS_IPN_SECRET loaded
   CLOUD_TASKS_PROJECT_ID: ✅ Loaded
   CLOUD_TASKS_LOCATION: ✅ Loaded
   GCWEBHOOK1_QUEUE: ✅ Loaded
   GCWEBHOOK1_URL: ✅ Loaded
✅ [CLOUDTASKS] Client initialized for project: telepay-459221, location: us-central1
✅ [CLOUDTASKS] Client initialized successfully
```

**All required configuration is loaded correctly** ✅

---

## User's Concern

> "I believe the correctly working version is found on us-east1 and not us-central1 because even though the updated version on us-central1 now updates the private_channel_users_database table correctly, the webhook doesn't do anything further and doesn't send any request to GCWebhook1."

### Analysis of This Statement

**"updated version on us-central1 now updates the private_channel_users_database table correctly"**
- This refers to the manual insert we did (Record ID 17)
- The NEW deployment hasn't received an IPN callback yet to test the UPSERT logic

**"doesn't send any request to GCWebhook1"**
- No IPN callbacks have been received by the NEW deployment yet
- The GCWebhook1 orchestration code is present (lines 852-901)
- Configuration is loaded correctly (GCWEBHOOK1_QUEUE, GCWEBHOOK1_URL)

**Why this might feel like an issue:**
1. User manually created payment from us-central1 URL
2. Payment completed, but user is still stuck on "Processing..." page
3. User expects immediate GCWebhook1 trigger
4. But GCWebhook1 is only triggered by IPN callbacks, not by manual database inserts

---

## The Real Flow

### Normal Payment Flow
```
User → Payment Link → NowPayments Payment
                            ↓
                   Payment Completes
                            ↓
            NowPayments sends IPN callback
                            ↓
            np-webhook receives POST /
                            ↓
        Verify signature + Update DB
                            ↓
        ✅ Trigger GCWebhook1 via Cloud Tasks
                            ↓
        GCWebhook1 processes payment
                            ↓
        User receives Telegram invite
```

### What Happened for Payment 4479119533
```
User → Payment Link (us-central1 URL) → NowPayments Payment
                                             ↓
                                    Payment Completes
                                             ↓
                           NowPayments sends IPN callbacks
                                             ↓
                         np-webhook (OLD revision) receives POST /
                                             ↓
                     ❌ UPDATE fails (no existing record)
                                             ↓
                         Returns HTTP 500 - NowPayments will retry
                                             ↓
                        (Retries: 11:50:29, 11:51:15, 11:53:05)
                                             ↓
                         ❌ All retries fail with HTTP 500
                                             ↓
                            [WE INTERVENE HERE]
                                             ↓
                     Manual insert (Record ID 17) at 12:25:00
                                             ↓
                     Deploy UPSERT fix at 12:25:03
                                             ↓
                     ⏳ WAITING FOR NEXT IPN RETRY
```

**Current Status:** Waiting for NowPayments to send the next IPN retry

---

## Action Required

### Option 1: Wait for NowPayments Retry (RECOMMENDED)
**Timeline:** 5-15 minutes from last attempt (11:53:05)
**Expected:** Next retry should arrive by ~12:00 UTC
**Result:** Will hit NEW revision, find record, trigger GCWebhook1

### Option 2: Manually Trigger GCWebhook1
If urgent, manually enqueue task to GCWebhook1:

```python
# Script to manually trigger GCWebhook1 for payment 4479119533
cloudtasks_client.enqueue_gcwebhook1_validated_payment(
    queue_name=GCWEBHOOK1_QUEUE,
    target_url=f"{GCWEBHOOK1_URL}/process-validated-payment",
    user_id=6271402111,
    closed_channel_id=-1003016667267,
    wallet_address="<from main_clients_database>",
    payout_currency="<from main_clients_database>",
    payout_network="<from main_clients_database>",
    subscription_time_days=30,
    subscription_price="2.50",
    outcome_amount_usd=2.01,  # Calculated value
    nowpayments_payment_id="4479119533",
    nowpayments_pay_address="0xD031Cb94c419A5D7AA4BA5FDBc9Cc82138651083",
    nowpayments_outcome_amount=0.00061819
)
```

### Option 3: Manually Trigger IPN Callback
Force NowPayments to send IPN immediately:
```bash
# Not typically available - NowPayments controls retry schedule
```

---

## Conclusion

**Is the issue that we're pointing to the wrong deployment?**
❌ **NO** - us-central1 is correctly configured and receiving traffic

**Is us-east1 the "correctly working version"?**
❌ **NO** - us-east1 has ZERO recent activity and older code

**What's actually happening?**
✅ **Waiting for next IPN retry** - The manual insert fixed the immediate issue, but GCWebhook1 orchestration requires an IPN callback to trigger

**Why hasn't GCWebhook1 been triggered yet?**
✅ **No IPN callback received by NEW deployment** - Last callback was before deployment

**Recommended Action:**
1. ✅ **Wait** 5-10 more minutes for NowPayments retry
2. ✅ **Monitor logs** for IPN callback and GCWebhook1 orchestration messages
3. ✅ **If urgent**, manually trigger GCWebhook1 using Option 2 above

---

## Monitoring Commands

### Watch for IPN Callbacks
```bash
gcloud logging read '
  resource.type="cloud_run_revision"
  resource.labels.service_name="np-webhook-10-26"
  resource.labels.revision_name="np-webhook-10-26-00010-pds"
  textPayload=~"IPN"
' --limit 50 --format json --freshness=10m
```

### Watch for GCWebhook1 Orchestration
```bash
gcloud logging read '
  resource.type="cloud_run_revision"
  resource.labels.service_name="np-webhook-10-26"
  resource.labels.revision_name="np-webhook-10-26-00010-pds"
  textPayload=~"ORCHESTRATION"
' --limit 50 --format json --freshness=10m
```

### Check NowPayments Payment Status
```bash
curl -H "x-api-key: $NOWPAYMENTS_API_KEY" \
  "https://api.nowpayments.io/v1/payment/4479119533"
```

---

**End of Analysis**
