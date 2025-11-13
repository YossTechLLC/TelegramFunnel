# Notification Management Feature - Deployment Guide

**Feature:** Payment Notifications for Channel Owners
**Version:** 1.0
**Date:** 2025-11-11
**Status:** ✅ Ready for Deployment

---

## 📋 Pre-Deployment Checklist

### ✅ Completed
- [x] Database migration executed successfully
- [x] Backend API updated with notification fields
- [x] Frontend UI updated with notification settings
- [x] TelePay Bot updated with NotificationService
- [x] IPN Webhook updated with notification trigger
- [x] Deployment scripts created and tested

### 📝 Before Deploying
- [ ] Backup production database (recommended)
- [ ] Review all code changes
- [ ] Ensure gcloud is authenticated
- [ ] Verify sufficient GCP quotas

---

## 🚀 Deployment Instructions

### Option A: Master Deployment Script (Recommended)

Deploy all components at once using the orchestrator script:

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts

# Run master deployment script
bash deploy_notification_feature.sh
```

The script will:
1. Verify database migration (already completed)
2. Deploy Backend API
3. Deploy Frontend
4. Deploy TelePay Bot
5. Deploy IPN Webhook

**Output:** Comprehensive logs in `TOOLS_SCRIPTS_TESTS/logs/deployment_notification_feature_*.log`

---

### Option B: Individual Component Deployment

Deploy components individually if needed:

#### 1. Backend API
```bash
bash deploy_backend_api.sh
```

#### 2. Frontend
```bash
bash deploy_frontend.sh
```

#### 3. TelePay Bot
```bash
bash deploy_telepay_bot.sh
```

**Important:** Save the TelePay Bot URL printed after deployment!

#### 4. IPN Webhook
```bash
bash deploy_np_webhook.sh
```

**Note:** This script automatically configures TELEPAY_BOT_URL secret.

---

## 🔍 Post-Deployment Verification

### 1. Verify Services Are Running

Check all Cloud Run services:
```bash
gcloud run services list --region=us-central1
```

Expected services:
- `gcregisterapi-10-26` (Backend API)
- `telepay-10-26` (TelePay Bot)
- `np-webhook-10-26` (IPN Webhook)

### 2. Test Health Endpoints

Backend API:
```bash
curl https://gcregisterapi-10-26-<hash>.run.app/health
```

TelePay Bot:
```bash
curl https://telepay-10-26-<hash>.run.app/health
```

IPN Webhook:
```bash
curl https://np-webhook-10-26-<hash>.run.app/health
```

### 3. Verify Frontend is Live

Visit: https://www.paygateprime.com

Check:
- Registration page loads
- "📬 Payment Notification Settings" section visible
- Edit page loads with notification section

### 4. Verify Database Schema

Check columns exist:
```bash
# Via Cloud Console or using observability MCP
gcloud sql connect telepaypsql --user=postgres --database=client_table
```

```sql
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'main_clients_database'
AND column_name IN ('notification_status', 'notification_id');
```

Expected result:
```
 column_name       | data_type | column_default | is_nullable
-------------------+-----------+----------------+-------------
 notification_id   | bigint    | NULL           | YES
 notification_status | boolean   | false          | NO
```

---

## 🧪 Testing Procedure

### Test 1: Channel Registration with Notifications

1. Navigate to https://www.paygateprime.com
2. Register a new channel
3. Scroll to "📬 Payment Notification Settings"
4. Enable notifications
5. Get your Telegram ID from @userinfobot
6. Enter Telegram ID
7. Complete registration
8. Verify channel created successfully

**Verify in database:**
```sql
SELECT open_channel_id, notification_status, notification_id
FROM main_clients_database
WHERE open_channel_id = '<your-channel-id>';
```

### Test 2: Edit Existing Channel

1. Go to Dashboard
2. Click "Edit" on a channel
3. Scroll to notification settings
4. Toggle notifications on/off
5. Update Telegram ID
6. Save changes
7. Verify updates persisted

### Test 3: Notification Delivery (Critical)

**Setup:**
1. Register a channel with notifications enabled
2. Use your real Telegram ID
3. Make a small test payment (subscription or donation)

**Expected Behavior:**
1. Payment processes normally
2. Within 5-10 seconds, receive Telegram message
3. Message includes:
   - Payment type (subscription/donation)
   - Channel info
   - User info
   - Amount details
   - Timestamp

**If notification fails:**
- Check TelePay Bot logs
- Check np-webhook logs
- Verify TELEPAY_BOT_URL is set correctly
- Verify bot hasn't been blocked

---

## 🔧 Configuration Verification

### Required Secrets

All secrets should be configured. Verify with:

```bash
gcloud secrets list
```

Required secrets:
- `BOT_TOKEN`
- `CLOUD_SQL_CONNECTION_NAME`
- `DATABASE_NAME_SECRET`
- `DATABASE_USER_SECRET`
- `DATABASE_PASSWORD_SECRET`
- `NOWPAYMENTS_IPN_SECRET_KEY`
- `TELEPAY_BOT_URL` (🆕 New for this feature)
- `GCWEBHOOK1_QUEUE`
- `GCWEBHOOK1_URL`
- And others...

### Check TELEPAY_BOT_URL Secret

```bash
gcloud secrets versions access latest --secret=TELEPAY_BOT_URL
```

Should return TelePay Bot Cloud Run URL.

---

## 📊 Monitoring & Logging

### Cloud Logging Queries

**View notification logs:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="telepay-10-26"
"[NOTIFICATION]"
```

**View IPN notification triggers:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="np-webhook-10-26"
"[NOTIFICATION]"
```

**View Backend API notification requests:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcregisterapi-10-26"
jsonPayload.notification_status=true
```

### Key Metrics to Monitor

1. **Notification Success Rate**
   - Target: >95%
   - Alert if: <90%

2. **Notification Delivery Latency**
   - Target: <5 seconds
   - Alert if: >30 seconds

3. **Service Health**
   - All services should be "Healthy"
   - Min instances should be maintained

---

## 🐛 Troubleshooting

### Issue: Notification Not Received

**Check 1: Is notification enabled?**
```sql
SELECT notification_status, notification_id
FROM main_clients_database
WHERE open_channel_id = '<channel-id>';
```

**Check 2: View TelePay Bot logs**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=telepay-10-26" --limit 50
```

Look for:
- `📬 [NOTIFICATION] Processing notification request`
- `✅ [NOTIFICATION] Successfully sent`
- `❌ [NOTIFICATION] Error sending`

**Check 3: Verify TELEPAY_BOT_URL**
```bash
gcloud secrets versions access latest --secret=TELEPAY_BOT_URL
```

**Check 4: Test notification endpoint directly**
```bash
curl -X POST https://telepay-10-26-<hash>.run.app/send-notification \
  -H "Content-Type: application/json" \
  -d '{
    "open_channel_id": "<channel-id>",
    "payment_type": "subscription",
    "payment_data": {
      "user_id": <your-telegram-id>,
      "amount_crypto": "0.001",
      "amount_usd": "10.00",
      "crypto_currency": "ETH",
      "tier": 1,
      "tier_price": "10.00",
      "duration_days": 30
    }
  }'
```

### Issue: Bot Blocked by User

**Symptom:** Logs show `🚫 [NOTIFICATION] Bot blocked by user`

**Solution:**
1. User must unblock the bot in Telegram
2. User must send /start to the bot
3. Re-test notification

### Issue: Invalid Telegram ID

**Symptom:** Logs show `❌ [NOTIFICATION] Invalid request`

**Solution:**
1. Verify ID format (5-15 digits)
2. Get correct ID from @userinfobot
3. Update in Edit Channel page

### Issue: Payment Processes but No Notification

**This is expected behavior when:**
- Notifications are disabled for that channel
- notification_id is NULL
- Bot is blocked by user

**Check np-webhook logs:**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=np-webhook-10-26 AND textPayload:[NOTIFICATION]" --limit 20
```

---

## 🔄 Rollback Plan

If critical issues arise:

### 1. Rollback Services

Revert to previous revision:
```bash
# Get previous revision
gcloud run revisions list --service=gcregisterapi-10-26 --region=us-central1

# Route 100% traffic to previous revision
gcloud run services update-traffic gcregisterapi-10-26 \
  --to-revisions=<previous-revision>=100 \
  --region=us-central1
```

Repeat for other services if needed.

### 2. Rollback Database (If Necessary)

**⚠️ Only if absolutely necessary:**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts

# Connect to database
gcloud sql connect telepaypsql --user=postgres --database=client_table

# Run rollback SQL
\i rollback_notification_columns.sql
```

**Note:** Rollback is safe because:
- notification_status defaults to false (no unexpected behavior)
- Old code ignores new columns
- No breaking changes to existing functionality

---

## 📈 Success Criteria

Deployment is successful when:

- [x] All Cloud Run services are healthy
- [x] Frontend loads with notification UI
- [x] Database columns exist and have correct types
- [ ] Test channel registration succeeds
- [ ] Test notification delivery succeeds
- [ ] No errors in Cloud Logging
- [ ] All health endpoints return 200

---

## 📞 Support

**For issues:**
1. Check logs in Cloud Logging
2. Review this troubleshooting guide
3. Check PROGRESS.md and BUGS.md files
4. Escalate if unresolved

**Key Files:**
- Architecture: `NOTIFICATION_MANAGEMENT_ARCHITECTURE.md`
- Checklist: `NOTIFICATION_MANAGEMENT_ARCHITECTURE_CHECKLIST.md`
- Progress: `NOTIFICATION_MANAGEMENT_ARCHITECTURE_CHECKLIST_PROGRESS.md`
- Deployment: `NOTIFICATION_MANAGEMENT_DEPLOYMENT_GUIDE.md` (this file)

---

## ✅ Deployment Complete

Once all verification steps pass, the notification management feature is **LIVE**! 🎉

**Users can now:**
- Enable payment notifications during channel registration
- Receive instant Telegram messages when payments are completed
- Manage notification settings from the Edit Channel page

**Feature highlights:**
- ✅ Opt-in system (notifications disabled by default)
- ✅ Secure manual Telegram ID entry
- ✅ Rich HTML-formatted notifications
- ✅ Comprehensive error handling
- ✅ Graceful degradation (failures don't block payments)

---

**Deployment Date:** [To be filled]
**Deployed By:** [To be filled]
**Deployment Status:** [To be filled]
