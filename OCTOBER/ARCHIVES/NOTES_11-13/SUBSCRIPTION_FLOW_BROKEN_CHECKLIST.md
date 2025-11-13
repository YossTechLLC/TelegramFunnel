# Subscription Flow Broken - Verification Checklist

**Issue:** "❌ No payment context found. Please start from a subscription link."
**Date:** 2025-11-13 Session 142

---

## Quick Verification Steps

### ☐ Step 1: Check Database Table Exists (2 minutes)

**Run:**
```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'user_conversation_state'
ORDER BY ordinal_position;
```

**Expected:**
```
table_name              | column_name        | data_type
-----------------------|-------------------|------------------
user_conversation_state | user_id           | bigint
user_conversation_state | conversation_type | character varying
user_conversation_state | state_data        | jsonb
user_conversation_state | updated_at        | timestamp
```

**If table missing:**
- Execute: `GCBotCommand-10-26/migrations/001_conversation_state_table.sql`
- STOP and fix this before testing flow

---

### ☐ Step 2: Test Complete Subscription Flow (5 minutes)

**Test Actions:**
1. ☐ Navigate to open channel with subscription broadcast
2. ☐ Click subscription button (e.g., "$45.0 for 13 days")
3. ☐ Bot PM opens automatically
4. ☐ Wait for bot message with "Launch Payment Gateway" button
5. ☐ Click "Launch Payment Gateway" button
6. ☐ Check if payment invoice appears

**Monitor GCBotCommand logs during test:**
```bash
# Real-time log monitoring
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=gcbotcommand-10-26" --format=json
```

**Expected Log Sequence:**
```
[Timestamp] 📍 /start command from user {user_id}, args: {token}
[Timestamp] 💰 Subscription: channel={channel_id}, price=${price}, time={time}days
[Timestamp] ✅ Message sent to chat_id {user_id}
[Timestamp] 🔘 Callback: TRIGGER_PAYMENT from user {user_id}
[Timestamp] 🌐 Calling GCPaymentGateway: /create-invoice
[Timestamp] ✅ Message sent to chat_id {user_id}
```

**Results:**
- ✅ SUCCESS: Payment invoice created, "💳 Pay Now" button appears
- ❌ FAILURE: Document which step failed

---

### ☐ Step 3: If Flow Still Fails - Check Conversation State (3 minutes)

**After clicking subscription button, immediately run:**
```sql
SELECT user_id, conversation_type, state_data, updated_at
FROM user_conversation_state
WHERE user_id = {YOUR_USER_ID}
ORDER BY updated_at DESC
LIMIT 5;
```

**Expected:**
```
user_id      | conversation_type | state_data                                    | updated_at
-------------|-------------------|-----------------------------------------------|---------------------------
6271402111   | payment           | {"channel_id": "-100...", "price": 45.0, ...} | 2025-11-13 22:XX:XX
```

**If row exists but payment still fails:**
- Conversation state is being saved correctly
- Issue is in retrieval logic (`get_conversation_state`)
- Check database connection/permissions

**If row missing:**
- `save_conversation_state()` is failing
- Check logs for database errors during `/start` command
- Check database permissions for INSERT operations

---

### ☐ Step 4: Manual `/start` Command Test (1 minute)

**Send to bot:**
```
/start test123
```

**Expected:**
- Log appears: `📍 /start command from user {user_id}, args: test123`
- Bot responds with: "Invalid token format" or main menu

**If no log appears:**
- Webhook not routing `/start` commands correctly
- Telegram webhook misconfigured
- Wrong bot instance receiving messages

---

### ☐ Step 5: Check Webhook Configuration (2 minutes)

**Run:**
```bash
TOKEN="8139434770:AAGc7zRahRJksnhp3_HOvOLERRXdgaYo6Co"
curl -s "https://api.telegram.org/bot$TOKEN/getWebhookInfo" | python3 -m json.tool
```

**Expected:**
```json
{
    "ok": true,
    "result": {
        "url": "https://gcbotcommand-10-26-291176869049.us-central1.run.app/webhook",
        "has_custom_certificate": false,
        "pending_update_count": 0,
        "max_connections": 40
    }
}
```

**If URL wrong or missing:**
```bash
# Set webhook
curl -X POST "https://api.telegram.org/bot$TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://gcbotcommand-10-26-291176869049.us-central1.run.app/webhook"}'
```

---

## Decision Tree

```
Start: User clicks "Launch Payment Gateway"
  ↓
  Is error "No payment context found"?
  ├─ NO → Different issue, investigate separately
  └─ YES ↓
      ↓
      Does user_conversation_state table exist?
      ├─ NO → Execute migration, retest
      └─ YES ↓
          ↓
          Did user click subscription button in channel first?
          ├─ NO → User clicked old PM button, instruct to start fresh
          └─ YES ↓
              ↓
              Was /start command logged?
              ├─ NO → Webhook issue, check Step 4-5
              └─ YES ↓
                  ↓
                  Was conversation state saved to database?
                  ├─ NO → Database permission/connection issue
                  └─ YES ↓
                      ↓
                      Is state being retrieved correctly?
                      ├─ NO → Bug in get_conversation_state()
                      └─ YES → Edge case, investigate further
```

---

## Quick Fixes by Root Cause

### Cause: Missing Database Table
**Fix:**
```bash
# Execute migration
cd GCBotCommand-10-26
psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
     -U postgres -d telepaydb \
     -f migrations/001_conversation_state_table.sql

# Verify
psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
     -U postgres -d telepaydb \
     -c "\d user_conversation_state"
```

**Time:** 2 minutes
**Deploy:** Not needed

---

### Cause: User Clicking Old Message
**Fix:**
- Instruct user to click subscription button in open channel (fresh flow)
- OR send `/start` command to reset conversation
- Old "Launch Payment Gateway" buttons won't work with new system

**Time:** 0 minutes (user action)
**Deploy:** Not needed

---

### Cause: Webhook Misconfigured
**Fix:**
```bash
TOKEN="8139434770:AAGc7zRahRJksnhp3_HOvOLERRXdgaYo6Co"
WEBHOOK_URL="https://gcbotcommand-10-26-291176869049.us-central1.run.app/webhook"

curl -X POST "https://api.telegram.org/bot$TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"$WEBHOOK_URL\"}"
```

**Time:** 1 minute
**Deploy:** Not needed

---

### Cause: Database Connection Issue (Unix Socket)
**Fix:**
```bash
# GCBotCommand needs same fix as GCDonationHandler
# Check if CLOUD_SQL_CONNECTION_NAME is set
gcloud run services describe gcbotcommand-10-26 \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env[?name=='CLOUD_SQL_CONNECTION_NAME'].value)"

# If missing or wrong:
gcloud run services update gcbotcommand-10-26 \
  --region=us-central1 \
  --set-env-vars="CLOUD_SQL_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql" \
  --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql
```

**Time:** 3 minutes
**Deploy:** YES

---

## Most Likely Scenario (Based on Evidence)

**Hypothesis:** User clicked old "Launch Payment Gateway" button from a previous conversation that occurred BEFORE the microservice refactoring.

**Why:**
- Log only shows TRIGGER_PAYMENT callback (Step 2), not /start command (Step 1)
- Old system (TelePay10-26) used in-memory state, new system uses database
- Old button still works (callback sent), but no state exists for it

**Test:** User must click subscription button in open channel to start fresh flow

**Confidence:** 80%

---

## Status Tracking

**Current Status:** ⏳ Awaiting user testing

**Completed:**
- ✅ Code review (logic correct)
- ✅ Database connection verified (working)
- ✅ Webhook routing verified (correct)
- ✅ Root cause analysis completed

**Pending:**
- ☐ Verify database table exists
- ☐ Test complete subscription flow
- ☐ Identify which step fails
- ☐ Apply appropriate fix
- ☐ Verify fix works end-to-end

---

## User Action Required

**Please complete these 2 steps:**

1. **Check if table exists:**
   ```sql
   \c telepaydb
   \d user_conversation_state
   ```

2. **Test complete flow:**
   - Go to open channel
   - Click subscription button ("$45.0 for 13 days")
   - Wait for bot message
   - Click "Launch Payment Gateway"
   - Report what happens at each step

**Report back:**
- Did table exist? (yes/no)
- Which step failed? (if any)
- What error message appeared? (if any)
- Full logs from the test

---

## References

- Full Analysis: `SUBSCRIPTION_FLOW_BROKEN_ANALYSIS.md`
- Code: `GCBotCommand-10-26/handlers/`
- Migration: `GCBotCommand-10-26/migrations/001_conversation_state_table.sql`
