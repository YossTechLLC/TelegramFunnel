# TelePay Bot Deployment Instructions - NowPayments Payment ID Integration (Updated)

**Date:** 2025-11-02
**Version:** 2.0 (Secret Manager Integration)
**Priority:** ⚠️ REQUIRED BEFORE NEXT PAYMENT TEST
**Estimated Time:** 2 minutes

---

## Quick Summary

The TelePay bot code has been updated to:
1. Include IPN (Instant Payment Notification) callback URLs in payment invoices
2. **Fetch IPN callback URL from Google Cloud Secret Manager** (more secure)

This enables automatic capture of NowPayments `payment_id` for fee reconciliation.

**Status:**
- ✅ Code updated: `start_np_gateway.py`
- ✅ Database ready: Migration complete
- ✅ Services deployed: GCWebhook1 + GCAccumulator
- ✅ Secret Manager configured: `NOWPAYMENTS_IPN_CALLBACK_URL` secret exists
- ⚠️ **ACTION REQUIRED:** Set secret path environment variable and restart bot

---

## What Changed from Previous Version

**Previous approach (v1.0):** Direct environment variable
```bash
export NOWPAYMENTS_IPN_CALLBACK_URL="https://np-webhook-291176869049.us-east1.run.app"
```

**New approach (v2.0):** Secret Manager path in environment variable
```bash
export NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest"
```

**Why the change?**
- 🔐 More secure: Secret stored in Secret Manager with IAM controls
- 🎯 Consistent: Matches pattern used for `PAYMENT_PROVIDER_TOKEN`
- 📋 Better logging: Clear success/error messages
- ✅ Easier management: Update secret without restarting bot (after initial setup)

---

## Step-by-Step Deployment

### Step 1: Set Environment Variable

Before starting the TelePay bot, set the Secret Manager path environment variable:

```bash
export NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest"
```

**Verification:**
```bash
echo $NOWPAYMENTS_IPN_CALLBACK_URL
# Should output: projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest
```

### Step 2: Restart TelePay Bot

Restart your TelePay bot to apply the updated code and environment variable.

**Example (if running in terminal):**
```bash
# Stop existing bot (Ctrl+C or kill process)
# Then start bot again
python3 /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TelePay10-26/telepay10-26.py
```

**Example (if running as systemd service):**
```bash
sudo systemctl restart telepay-bot
```

### Step 3: Verify Configuration

After bot starts, check the startup logs:

**Expected output on startup:**
```
✅ [IPN] Successfully fetched IPN callback URL from Secret Manager
```

**If you see this warning instead:**
```
⚠️ [IPN] Environment variable NOWPAYMENTS_IPN_CALLBACK_URL is not set
⚠️ [IPN] Payment ID capture will not work - IPN callback URL unavailable
```
→ Go back to Step 1 (environment variable not set correctly)

**If you see this error:**
```
❌ [IPN] Error fetching IPN callback URL from Secret Manager: <error message>
```
→ Check IAM permissions for the service account running the bot

---

### Step 4: Test Invoice Creation

Create a test invoice through the bot and check logs:

**Expected output when creating invoice:**
```
📋 [INVOICE] Created invoice_id: <ID>
📋 [INVOICE] Order ID: <ORDER_ID>
📋 [INVOICE] IPN will be sent to: https://np-webhook-291176869049.us-east1.run.app
```

**If you see this warning:**
```
⚠️ [INVOICE] IPN callback URL not set - payment_id won't be captured
```
→ Secret Manager fetch failed during initialization (check Step 3 logs)

---

## Verification Test (Optional but Recommended)

### Test 1: Verify Secret Manager Access

Manually verify the bot can access the secret:

```bash
# Test with gcloud CLI (if authenticated)
gcloud secrets versions access latest \
  --secret=NOWPAYMENTS_IPN_CALLBACK_URL \
  --project=telepay-459221

# Should output: https://np-webhook-291176869049.us-east1.run.app
```

### Test 2: Complete Small Payment ($1.35)

1. Create payment through bot
2. Complete payment (use testnet or small amount)
3. After payment completes, verify payment_id was captured:

```bash
# Query database to check payment_id
# (This assumes you have database access via gcloud)
gcloud sql connect telepaypsql --user=postgres --database=telepaydb
```

```sql
-- Check if payment_id was captured
SELECT
    user_id,
    private_channel_id,
    nowpayments_payment_id,
    nowpayments_outcome_amount,
    subscription_time
FROM private_channel_users_database
ORDER BY subscription_time DESC
LIMIT 1;
```

**Expected Result:**
- `nowpayments_payment_id` should NOT be NULL
- Should contain a value like `'4971340333'`

---

## Troubleshooting

### Issue: Bot won't start - Secret Manager error

**Error Message:**
```
❌ [IPN] Error fetching IPN callback URL from Secret Manager: 403 Permission denied
```

**Solution:**
1. Check which service account is running the bot
2. Grant Secret Manager access:
   ```bash
   # Replace <SERVICE_ACCOUNT_EMAIL> with actual service account
   gcloud secrets add-iam-policy-binding NOWPAYMENTS_IPN_CALLBACK_URL \
     --member="serviceAccount:<SERVICE_ACCOUNT_EMAIL>" \
     --role="roles/secretmanager.secretAccessor" \
     --project=telepay-459221
   ```

### Issue: Environment variable not persisting

**Solution:**
Add to bot startup script or systemd service file:

**For systemd:**
```ini
# /etc/systemd/system/telepay-bot.service
[Service]
Environment="NOWPAYMENTS_IPN_CALLBACK_URL=projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest"
```

**For shell script:**
```bash
#!/bin/bash
# start_telepay_bot.sh
export NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest"
python3 /path/to/telepay10-26.py
```

### Issue: payment_id is NULL in database

**Possible Causes:**
1. np-webhook service not receiving IPN (check service logs)
2. IPN signature verification failing (check Secret Manager for correct secret)
3. Race condition (IPN slower than success_url - should self-heal)

**Check np-webhook logs:**
```bash
gcloud run services logs read np-webhook --region=us-east1 --limit=50
```

Look for:
- `📨 [IPN] Received IPN notification from NowPayments`
- `✅ [IPN] Signature verified successfully`
- `💾 [IPN] Updated private_channel_users_database with payment_id`

### Issue: Want to update IPN callback URL

**Solution:**
Update the secret in Secret Manager (no bot restart needed after initial setup):

```bash
# Update secret value
echo -n "https://new-webhook-url.run.app" | \
  gcloud secrets versions add NOWPAYMENTS_IPN_CALLBACK_URL \
    --data-file=- \
    --project=telepay-459221

# Bot will use new URL on next restart
```

---

## Success Criteria

After deployment, you should have:
- ✅ Environment variable `NOWPAYMENTS_IPN_CALLBACK_URL` set and persisted
- ✅ Bot restarted successfully
- ✅ Startup logs show: `✅ [IPN] Successfully fetched IPN callback URL from Secret Manager`
- ✅ Invoice logs show IPN URL when creating invoices
- ✅ Test payment shows payment_id captured in database
- ✅ payment_id appears in both `private_channel_users_database` AND `payout_accumulation`

---

## What Happens Next?

Once deployed and verified:
1. All new payments will include `ipn_callback_url` in invoice
2. NowPayments will send IPN callbacks to np-webhook
3. payment_id will be automatically captured and stored
4. payment_id will propagate through GCWebhook1 → GCAccumulator → payout_accumulation
5. You'll be able to query NowPayments API by payment_id for fee reconciliation

---

## Additional Resources

- **Implementation Summary:** `NOWPAYMENTS_IMPLEMENTATION_SUMMARY.md`
- **Progress Tracking:** `PROGRESS.md` (Sessions 25 & 26)
- **Architecture Details:** `NOWPAYMENTS_PAYMENT_ID_STORAGE_ANALYSIS_ARCHITECTURE.md`
- **Architectural Decision:** `DECISIONS.md` (Secret Manager Integration)

---

## Quick Reference

**Environment Variable (Required):**
```bash
NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest"
```

**Expected Startup Log:**
```
✅ [IPN] Successfully fetched IPN callback URL from Secret Manager
```

**Expected Invoice Log:**
```
📋 [INVOICE] IPN will be sent to: https://np-webhook-291176869049.us-east1.run.app
```

---

**Deployment Owner:** User
**Date Required:** Before next payment test
**Estimated Time:** 2 minutes
**Version:** 2.0 (Secret Manager Integration)
