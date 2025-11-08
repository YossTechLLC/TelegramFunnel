# ChangeNow API Request Troubleshooting - Diagnostic Checklist

**Date:** 2025-10-13
**Issue:** Payment succeeds but ChangeNow API POST request never appears in logs or on ChangeNow backend

---

## Phase 1: tph10-13.py Webhook Trigger Verification

### 1.1 Check TPS_WEBHOOK_URL Environment Variable

**Action:** Go to Google Cloud Console → Cloud Run → Select `tph10-13` service → Variables & Secrets tab

**Look for:**
```
TPS_WEBHOOK_URL=https://tps10-9-291176869049.us-central1.run.app
```

**Result:**
- [ ] ✅ Variable exists with correct URL
- [ ] ❌ Variable missing → **ROOT CAUSE FOUND**
- [ ] ❌ Variable has wrong URL → **ROOT CAUSE FOUND**

**If missing/wrong, run:**
```bash
gcloud run services update tph10-13 \
    --region us-central1 \
    --set-env-vars TPS_WEBHOOK_URL=https://tps10-9-291176869049.us-central1.run.app
```

---

### 1.2 Check tph10-13 Logs for Webhook Trigger Attempt

**Action:** Go to Google Cloud Console → Cloud Run → tph10-13 → Logs

**Search for these log patterns (in order):**

```
1. "✅ You've been granted access!"
   → Confirms user received Telegram invite

2. "🚀 [PAYMENT_SPLITTING] Starting Client Payout"
   → Confirms payment split flow initiated

3. "🔄 [PAYMENT_SPLITTING] Triggering TPS10-9 webhook"
   → Confirms webhook function called

4. "📦 [PAYMENT_SPLITTING] Payload: user_id="
   → Confirms payload constructed

5. "🔐 [PAYMENT_SPLITTING] Added webhook signature"
   → Confirms HMAC signature added

6. "✅ [PAYMENT_SPLITTING] Webhook triggered successfully"
   → Confirms HTTP 200 response from tps10-9
```

**Possible failure patterns:**

```
❌ "⚠️ [PAYMENT_SPLITTING] TPS_WEBHOOK_URL not configured"
   → ROOT CAUSE: TPS_WEBHOOK_URL environment variable missing

❌ "❌ [PAYMENT_SPLITTING] Webhook failed with status 401"
   → Signature verification failure in tps10-9

❌ "❌ [PAYMENT_SPLITTING] Webhook failed with status 404"
   → tps10-9 service not accessible or wrong URL

❌ "❌ [PAYMENT_SPLITTING] Webhook request timeout"
   → tps10-9 service not responding (deployment issue)

❌ "❌ [PAYMENT_SPLITTING] Webhook connection error"
   → Network issue or tps10-9 not running
```

**Results:**
- [ ] Log pattern 1-6 all found → Proceed to Phase 2
- [ ] Stops at pattern ____ → Note where it stops:_________________
- [ ] Error pattern found:_________________

---

### 1.3 Verify Webhook Response Status

**Search logs for:**
```
"[PAYMENT_SPLITTING] Webhook responded but split failed"
```

**If found, check what error message follows**

**Result:**
- [ ] Webhook succeeded (status 200)
- [ ] Webhook failed with error:_________________

---

## Phase 2: tps10-9 Service Deployment Verification

### 2.1 Verify tps10-9 Service Exists

**Action:** Run in Cloud Shell:
```bash
gcloud run services list --region us-central1 | grep tps10-9
```

**Expected output:**
```
tps10-9  us-central1  https://tps10-9-291176869049.us-central1.run.app  Ready
```

**Result:**
- [ ] ✅ Service exists and shows "Ready"
- [ ] ❌ Service not found → **ROOT CAUSE: tps10-9 never deployed**
- [ ] ❌ Service shows error status → **ROOT CAUSE: Deployment failed**

**If service doesn't exist, deploy it:**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-9/GCSplit7-14

gcloud run deploy tps10-9 \
    --source . \
    --region us-central1 \
    --port 8080 \
    --allow-unauthenticated \
    --service-account=291176869049-compute@developer.gserviceaccount.com \
    --set-env-vars CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest \
    --set-env-vars WEBHOOK_SIGNING_KEY=projects/291176869049/secrets/WEBHOOK_SIGNING_KEY/versions/latest \
    --set-env-vars TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest \
    --set-env-vars HPW_WEBHOOK_URL=https://hpw10-9-291176869049.us-central1.run.app/gcsplit
```

---

### 2.2 Test tps10-9 Health Endpoint

**Action:** Run in Cloud Shell:
```bash
curl https://tps10-9-291176869049.us-central1.run.app/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "service": "TPS10-9 Payment Splitting",
  "timestamp": 1234567890
}
```

**Result:**
- [ ] ✅ Health endpoint returns 200 with expected JSON
- [ ] ❌ Connection refused → Service not running
- [ ] ❌ 404 Not Found → Service deployed but Flask routes not working
- [ ] ❌ Other error:_________________

---

### 2.3 Check tps10-9 Logs for Incoming Requests

**Action:** Go to Cloud Console → Cloud Run → tps10-9 → Logs

**Search for:**
```
"🎯 [WEBHOOK] TPS10-9 Webhook Called"
```

**Result:**
- [ ] ✅ Log entry found → Webhook request reached tps10-9
- [ ] ❌ No log entry → Webhook requests never reaching tps10-9
- [ ] ❌ Found but followed by error:_________________

---

### 2.4 Check for Signature Verification Failures

**Search tps10-9 logs for:**
```
"❌ [WEBHOOK] Invalid signature"
"❌ [WEBHOOK_VERIFY] Signature verification error"
```

**Result:**
- [ ] No signature errors found
- [ ] ✅ Signature error found → **ROOT CAUSE: Key mismatch**

**If signature error found, check:**
1. Both tph10-13 and tps10-9 use same SECRET_KEY for signing
2. Environment variables: SUCCESS_URL_SIGNING_KEY (tph10-13) and WEBHOOK_SIGNING_KEY (tps10-9)

---

## Phase 3: ChangeNow API Key Configuration

### 3.1 Check CHANGENOW_API_KEY Environment Variable

**Action:** Cloud Console → Cloud Run → tps10-9 → Variables & Secrets

**Look for:**
```
CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest
```

**Result:**
- [ ] ✅ Variable exists
- [ ] ❌ Variable missing → **ROOT CAUSE FOUND**

---

### 3.2 Verify Secret Manager Contains API Key

**Action:** Run in Cloud Shell:
```bash
gcloud secrets versions access latest --secret="CHANGENOW_API_KEY"
```

**Expected value:**
```
0e7ab0b9cfd8dd81479e811eb583b01a2b5c7f3aac00d5075225a4241e0a5bde
```

**Result:**
- [ ] ✅ Secret exists with correct value
- [ ] ❌ Secret missing → Create it
- [ ] ❌ Secret has different value → Update it

**If secret needs updating:**
```bash
echo -n "0e7ab0b9cfd8dd81479e811eb583b01a2b5c7f3aac00d5075225a4241e0a5bde" | \
    gcloud secrets create CHANGENOW_API_KEY --data-file=-
```

---

### 3.3 Check tps10-9 Logs for Client Initialization

**Search tps10-9 logs for:**
```
"🔗 [CHANGENOW_CLIENT] Initialized with API key: 0e7ab0b9..."
```

**Result:**
- [ ] ✅ Initialization log found
- [ ] ❌ Not found → Client never initialized
- [ ] ❌ Error during init:_________________

---

## Phase 4: ChangeNow API Call Execution Path

### 4.1 Check Payment Split Processing Start

**Search tps10-9 logs for:**
```
"🔄 [PAYMENT_SPLITTING] Starting Client Payout"
"👤 [PAYMENT_SPLITTING] User ID:"
"💰 [PAYMENT_SPLITTING] Amount:"
"🏦 [PAYMENT_SPLITTING] Target:"
```

**Result:**
- [ ] ✅ All logs found → Processing started
- [ ] ❌ Not found → Payment split never triggered
- [ ] ❌ Partial logs → Stopped at:_________________

---

### 4.2 Check Currency Pair Validation

**Search tps10-9 logs for:**
```
"🔍 [CHANGENOW_PAIR_CHECK] Validating ETH → "
```

**Look for result:**
```
✅ "Pair ETH → [CURRENCY] is supported"
OR
❌ "Pair ETH → [CURRENCY] not supported"
```

**Result:**
- [ ] ✅ Validation passed
- [ ] ❌ Validation failed → **ROOT CAUSE: Currency pair not supported**
- [ ] ❌ Not reached → Failed before validation

---

### 4.3 Check Amount Limits Validation

**Search tps10-9 logs for:**
```
"💰 [CHANGENOW_LIMITS] Checking limits for"
```

**Look for result:**
```
✅ "Amount ... within valid range"
OR
❌ "Amount ... below minimum"
OR
❌ "Amount ... above maximum"
```

**Result:**
- [ ] ✅ Amount validation passed
- [ ] ❌ Amount too small/large → **ROOT CAUSE: Amount outside limits**
- [ ] ❌ Not reached → Failed before this step

---

### 4.4 Check Transaction Creation Attempt

**Search tps10-9 logs for:**
```
"🚀 [CHANGENOW_SWAP] Starting fixed-rate transaction"
"💰 [CHANGENOW_SWAP] ... ETH → ..."
"🏦 [CHANGENOW_SWAP] Target wallet:"
```

**Result:**
- [ ] ✅ All logs found → Function called
- [ ] ❌ Not found → Never reached this function
- [ ] ❌ Partial → Stopped at:_________________

---

### 4.5 Check ChangeNow API Request Initiation

**Search tps10-9 logs for:**
```
"🚀 [CHANGENOW_TRANSACTION] Creating transaction via API v2"
"📦 [CHANGENOW_TRANSACTION] Payload:"
```

**Result:**
- [ ] ✅ Payload logged → Request prepared
- [ ] ❌ Not found → Request never prepared

**If payload logged, copy the entire payload here:**
```json
[PASTE PAYLOAD FROM LOGS]
```

---

### 4.6 Check HTTP Request to ChangeNow

**Search tps10-9 logs for:**
```
"🌐 [CHANGENOW_API] POST /exchange"
```

**Result:**
- [ ] ✅ Log found → HTTP request attempted
- [ ] ❌ Not found → **ROOT CAUSE: Request blocked before _make_request**

---

### 4.7 Check ChangeNow API Response

**Search tps10-9 logs for:**
```
"📊 [CHANGENOW_API] Response status: "
```

**Possible statuses:**
```
✅ 200 → Success
❌ 400 → Bad request (payload issue)
❌ 401 → Unauthorized (API key issue)
❌ 403 → Forbidden (API key permissions)
❌ 429 → Rate limited
❌ 500 → ChangeNow server error
```

**Result:**
- [ ] Status code:_________________
- [ ] ❌ No status logged → **ROOT CAUSE: Request never sent or exception occurred**

---

### 4.8 Check for API Errors

**Search tps10-9 logs for:**
```
"❌ [CHANGENOW_API] API error"
"❌ [CHANGENOW_API] Request timeout"
"❌ [CHANGENOW_API] Connection error"
"❌ [CHANGENOW_API] Unexpected error"
"❌ [CHANGENOW_TRANSACTION] Error creating transaction"
"❌ [CHANGENOW_TRANSACTION] Failed to create transaction"
```

**If error found, copy full error message:**
```
[PASTE ERROR MESSAGE]
```

---

### 4.9 Check for Successful Transaction Creation

**Search tps10-9 logs for:**
```
"✅ [CHANGENOW_TRANSACTION] Transaction created successfully"
"🆔 [CHANGENOW_TRANSACTION] ID:"
"🏦 [CHANGENOW_TRANSACTION] Deposit address:"
```

**Result:**
- [ ] ✅ Transaction created → **ChangeNow API IS working!**
- [ ] ❌ Not found → Transaction creation failed

---

## Phase 5: Enhanced Logging (If Needed)

If the above phases don't reveal the issue, I will add enhanced logging to:

1. Log every function entry/exit
2. Log full exception stack traces
3. Log raw HTTP request/response bodies
4. Add checkpoint markers throughout code

---

## Summary of Findings

**After completing all phases above, fill in this summary:**

### Where Did the Flow Stop?

- [ ] Phase 1: tph10-13 webhook trigger
- [ ] Phase 2: tps10-9 service receiving webhook
- [ ] Phase 3: ChangeNow client initialization
- [ ] Phase 4: ChangeNow API call execution

### Last Successful Log Entry Found:
```
[PASTE LAST SUCCESSFUL LOG]
```

### First Error/Missing Log:
```
[DESCRIBE WHAT LOG WAS EXPECTED BUT NOT FOUND]
```

### Root Cause Identified:
```
[DESCRIBE ROOT CAUSE]
```

---

## Next Steps

Based on findings, I will:
1. Fix identified configuration issues
2. Add enhanced logging if needed
3. Redeploy affected services
4. Trigger test payment to verify fix
5. Monitor logs to confirm ChangeNow API call succeeds
