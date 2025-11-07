# TelePay Bot Deployment Instructions - NowPayments Payment ID Integration

**Date:** 2025-11-02
**Priority:** ⚠️ REQUIRED BEFORE NEXT PAYMENT TEST
**Estimated Time:** 2 minutes

---

## Quick Summary

The TelePay bot code has been updated to include IPN (Instant Payment Notification) callback URLs in payment invoices. This enables automatic capture of NowPayments `payment_id` for fee reconciliation.

**Status:**
- ✅ Code updated: `start_np_gateway.py`
- ✅ Database ready: Migration complete
- ✅ Services deployed: GCWebhook1 + GCAccumulator
- ⚠️ **ACTION REQUIRED:** Set environment variable and restart bot

---

## Step-by-Step Deployment

### Step 1: Set Environment Variable

Before starting the TelePay bot, set the IPN callback URL environment variable:

```bash
export NOWPAYMENTS_IPN_CALLBACK_URL="https://np-webhook-291176869049.us-east1.run.app"
```

**Verification:**
```bash
echo $NOWPAYMENTS_IPN_CALLBACK_URL
# Should output: https://np-webhook-291176869049.us-east1.run.app
```

### Step 2: Restart TelePay Bot

Restart your TelePay bot to apply the updated code and environment variable.

**Example (if running in terminal):**
```bash
# Stop existing bot (Ctrl+C or kill process)
# Then start bot again
python3 telepay10-26.py
```

**Example (if running as systemd service):**
```bash
sudo systemctl restart telepay-bot
```

### Step 3: Verify Configuration

After bot starts, check the logs when creating a test invoice. You should see:

```
📋 [INVOICE] Created invoice_id: <ID>
📋 [INVOICE] Order ID: <ORDER_ID>
📋 [INVOICE] IPN will be sent to: https://np-webhook-291176869049.us-east1.run.app
```

**If you see this warning instead:**
```
⚠️ [INVOICE] IPN callback URL not configured - payment_id won't be captured
```
→ Environment variable was not loaded. Go back to Step 1.

---

## Verification Test (Optional but Recommended)

### Test 1: Create Invoice Through Bot

1. Send `/start` to your TelePay bot
2. Follow prompts to create a payment
3. Check bot logs for the IPN URL message
4. ✅ If you see `IPN will be sent to: https://np-webhook...`, configuration is correct

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

### Issue: Warning about IPN URL not configured

**Solution:**
1. Verify environment variable is set:
   ```bash
   echo $NOWPAYMENTS_IPN_CALLBACK_URL
   ```
2. If empty, set it again and restart bot
3. Make sure you restart the bot AFTER setting the variable

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

### Issue: Cannot find payment_id in payout_accumulation

**Solution:**
1. First check if it's in `private_channel_users_database` (primary source)
2. Check GCWebhook1 logs to see if payment_id was found and passed
3. Check GCAccumulator logs to see if payment_id was received and stored

---

## Success Criteria

After deployment, you should have:
- ✅ Environment variable set and persisted
- ✅ Bot restarted successfully
- ✅ Bot logs show IPN URL when creating invoices
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
- **Progress Tracking:** `PROGRESS.md` (Session 25)
- **Architecture Details:** `NOWPAYMENTS_PAYMENT_ID_STORAGE_ANALYSIS_ARCHITECTURE.md`
- **Progress Checklist:** `NOWPAYMENTS_PAYMENT_ID_STORAGE_ANALYSIS_ARCHITECTURE_CHECKLIST_PROGRESS.md`

---

**Questions or Issues?**
- Check bot logs for error messages
- Check np-webhook service logs
- Verify Secret Manager contains correct IPN secret
- Review implementation summary for architecture details

---

**Deployment Owner:** User
**Date Required:** Before next payment test
**Estimated Time:** 2 minutes
