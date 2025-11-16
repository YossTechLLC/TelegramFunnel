# External Webhooks Configuration Guide

**⚠️ CRITICAL:** These webhooks must be configured for the payment system to work

---

## 📋 Overview

PayGatePrime receives payment notifications from external services. After deploying Cloud Run services, you MUST update these webhook URLs in the respective dashboards.

---

## 🔴 PRIORITY 1: NowPayments IPN Webhook

### Service Information
- **Service:** pgp-npwebhook-v1
- **Purpose:** Receives Instant Payment Notifications (IPN) from NowPayments
- **Security:** HMAC signature verification using NOWPAYMENTS_IPN_SECRET

### Get Service URL
```bash
gcloud run services describe pgp-npwebhook-v1 \
  --region=us-central1 \
  --format="value(status.url)"
```

**Example URL:**
```
https://pgp-npwebhook-v1-291176869049.us-central1.run.app
```

### Configure in NowPayments Dashboard

1. **Log into NowPayments:**
   - https://account.nowpayments.io/

2. **Navigate to Settings → API Keys**

3. **Update IPN Callback URL:**
   - Find your API key settings
   - Set IPN Callback URL to: `https://pgp-npwebhook-v1-XXXXXX.us-central1.run.app/`
   - ⚠️ **Important:** Use the **root path** (`/`) for IPN callbacks

4. **Verify IPN Secret:**
   - Ensure the IPN secret matches the `NOWPAYMENTS_IPN_SECRET` in Secret Manager
   - If different, update the secret in GCP

5. **Test IPN:**
   - NowPayments dashboard usually has a "Test IPN" button
   - Click it to send a test notification
   - Check Cloud Run logs:
     ```bash
     gcloud run services logs read pgp-npwebhook-v1 --region=us-central1
     ```

### Expected Flow
```
Customer Payment
    ↓
NowPayments processes payment
    ↓
NowPayments sends IPN → https://pgp-npwebhook-v1-XXX.run.app/
    ↓
np-webhook verifies HMAC signature
    ↓
np-webhook enqueues task → GCWebhook1-PGP (via Cloud Tasks)
    ↓
Payment processing begins
```

### Troubleshooting
- **IPN not received:** Check service is deployed and public (`--allow-unauthenticated`)
- **Signature verification fails:** Verify `NOWPAYMENTS_IPN_SECRET` matches dashboard
- **Task not enqueued:** Check `GCWEBHOOK1_QUEUE` and `GCWEBHOOK1_URL` secrets exist

---

## 🟡 PRIORITY 2: Payment Status Page

### Public Endpoint
The np-webhook service also serves a payment status tracking page:

**URL:** `https://pgp-npwebhook-v1-XXXXXX.us-central1.run.app/payment-processing`

### Usage
- Customers are redirected here after initiating payment
- Page polls `/api/check-payment-status?payment_id=XXX`
- Shows real-time payment status updates

### Configure in Frontend
Update `GCRegisterWeb-PGP` to redirect users to this URL after payment initiation.

---

## 🟢 PRIORITY 3: ChangeNOW Webhooks (If Used)

### Service Information
- **Services:** GCHostPay1-PGP, GCHostPay2-PGP, GCHostPay3-PGP
- **Purpose:** Execute crypto conversions via ChangeNOW API

### Check if Webhooks Required
ChangeNOW may support webhook notifications for transaction status updates.

**Current Implementation:** Polling-based (no webhook required)

### If Implementing Webhooks
1. Check ChangeNOW API documentation for webhook support
2. Add webhook endpoint to GCHostPay services
3. Configure callback URL in ChangeNOW dashboard
4. Implement signature verification

---

## 🔵 PRIORITY 4: Telegram Bot Webhooks (Optional)

### Service Information
- **Service:** pgp-bot-v1
- **Purpose:** Telegram bot for legacy payment notifications

### Webhook Mode (Recommended)
If using webhook mode instead of polling:

1. **Get Service URL:**
   ```bash
   gcloud run services describe pgp-bot-v1 \
     --region=us-central1 \
     --format="value(status.url)"
   ```

2. **Set Telegram Webhook:**
   ```bash
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
     -d "url=https://pgp-bot-v1-XXXXXX.us-central1.run.app/webhook"
   ```

3. **Verify Webhook:**
   ```bash
   curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
   ```

### Polling Mode (Alternative)
If not using webhooks, the bot will use long polling (default behavior).

---

## ✅ Verification Checklist

### NowPayments IPN
- [ ] Service deployed and accessible
- [ ] IPN URL configured in NowPayments dashboard
- [ ] IPN secret matches Secret Manager value
- [ ] Test IPN sent successfully
- [ ] Logs show successful signature verification
- [ ] Task enqueued to GCWebhook1-PGP

### Payment Status Page
- [ ] Page accessible at `/payment-processing`
- [ ] API endpoint `/api/check-payment-status` working
- [ ] Frontend redirects to correct URL

### ChangeNOW (If Applicable)
- [ ] API key valid
- [ ] Conversions executing successfully
- [ ] Webhook configured (if implemented)

### Telegram Bot (If Used)
- [ ] Webhook set or polling enabled
- [ ] Bot responding to commands
- [ ] Payment notifications working

---

## 🔧 Testing Webhooks

### Test NowPayments IPN Manually
```bash
# Get your service URL
SERVICE_URL=$(gcloud run services describe pgp-npwebhook-v1 --region=us-central1 --format="value(status.url)")

# Generate test IPN payload (simplified)
# Real IPN includes HMAC signature - use NowPayments dashboard for real test

curl -X POST "$SERVICE_URL/" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "test-123",
    "payment_status": "finished",
    "pay_amount": "100",
    "pay_currency": "usdttrc20"
  }'

# Check logs
gcloud run services logs read pgp-npwebhook-v1 --region=us-central1 --limit=50
```

⚠️ **Note:** Real IPN includes HMAC signature. Use NowPayments dashboard "Test IPN" feature for authentic testing.

---

## 📊 Monitoring Webhooks

### Cloud Logging Queries

**View all IPN callbacks:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="pgp-npwebhook-v1"
jsonPayload.message=~"IPN"
```

**View signature verification failures:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="pgp-npwebhook-v1"
severity="ERROR"
jsonPayload.message=~"signature"
```

**View successful task enqueues:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="pgp-npwebhook-v1"
jsonPayload.message=~"enqueued"
```

---

## 🆘 Troubleshooting

### IPN Not Received
1. Check service is deployed: `gcloud run services list --region=us-central1`
2. Check service is public: `gcloud run services describe pgp-npwebhook-v1 --region=us-central1 --format="value(spec.template.spec.containers[0].env)"`
3. Test URL directly: `curl https://pgp-npwebhook-v1-XXX.run.app/health` (if health endpoint exists)
4. Check NowPayments dashboard for IPN delivery logs

### Signature Verification Fails
1. Verify secret: `gcloud secrets versions access latest --secret=NOWPAYMENTS_IPN_SECRET`
2. Check it matches NowPayments dashboard
3. Check logs for exact error: `gcloud run services logs read pgp-npwebhook-v1 --region=us-central1`

### Tasks Not Enqueued
1. Verify queue exists: `gcloud tasks queues list --location=us-central1`
2. Verify queue name secret: `gcloud secrets versions access latest --secret=GCWEBHOOK1_QUEUE`
3. Check IAM permissions: Service account has `cloudtasks.enqueuer` role
4. Check service URL secret: `gcloud secrets versions access latest --secret=GCWEBHOOK1_URL`

---

## 📝 Configuration Summary

| Service | Webhook URL | External System | Configuration Location |
|---------|-------------|-----------------|------------------------|
| pgp-npwebhook-v1 | `https://pgp-npwebhook-v1-XXX.run.app/` | NowPayments | account.nowpayments.io → Settings → API Keys |
| pgp-npwebhook-v1 | `https://pgp-npwebhook-v1-XXX.run.app/payment-processing` | Frontend Redirect | Update in React app |
| pgp-bot-v1 | `https://pgp-bot-v1-XXX.run.app/webhook` | Telegram | Bot API setWebhook |

---

**Status:** Configuration guide complete
**Next:** Run verification script (10_verify_deployment.sh)
