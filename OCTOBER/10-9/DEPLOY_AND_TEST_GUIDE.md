# Deploy and Test Guide - Enhanced Logging for ChangeNow API Debugging

**Date:** 2025-10-13
**Purpose:** Deploy enhanced logging versions of tps10-9 to identify why ChangeNow API requests are not visible

---

## Summary of Changes

I've added comprehensive enhanced logging to the following files:

### 1. `GCSplit7-14/changenow_client.py`
- **Added:** Detailed logging in `_make_request()` method
- **Logs:** Full HTTP request details (URL, headers, body)
- **Logs:** Full HTTP response details (status, headers, body)
- **Logs:** Complete stack traces for all exceptions
- **Logs:** Entry/exit markers for all API calls

### 2. `GCSplit7-14/tps10-9.py`
- **Added:** Step-by-step logging in `process_payment_split()`
- **Added:** Detailed logging in `create_fixed_rate_transaction()`
- **Logs:** Each validation step with success/failure status
- **Logs:** Function entry/exit markers
- **Logs:** Complete stack traces for exceptions

---

## Deployment Steps

### Step 1: Deploy tps10-9 with Enhanced Logging

```bash
# Navigate to GCSplit7-14 directory
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-9/GCSplit7-14

# Deploy to Cloud Run
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

**Expected output:**
```
Deploying from source. To deploy a container use [--image]. See https://cloud.google.com/run/docs/deploying-source-code for more details.
Building using Buildpacks and deploying container to Cloud Run service [tps10-9] in project [telepay-459221] region [us-central1]
✓ Building and deploying... Done.
  ✓ Uploading sources...
  ✓ Building Container... Logs are available at [...]
  ✓ Creating Revision...
  ✓ Routing traffic...
Done.
Service [tps10-9] revision [tps10-9-00001-xxx] has been deployed and is serving 100 percent of traffic.
Service URL: https://tps10-9-291176869049.us-central1.run.app
```

---

### Step 2: Verify Deployment

```bash
# Check service status
gcloud run services describe tps10-9 --region us-central1 --format="value(status.url,status.conditions)"

# Test health endpoint
curl https://tps10-9-291176869049.us-central1.run.app/health
```

**Expected health response:**
```json
{
  "status": "healthy",
  "service": "TPS10-9 Payment Splitting",
  "timestamp": 1234567890
}
```

---

### Step 3: Verify tph10-13 Has TPS_WEBHOOK_URL Configured

```bash
# Check tph10-13 environment variables
gcloud run services describe tph10-13 --region us-central1 --format="value(spec.template.spec.containers[0].env)"
```

**Look for:**
```
TPS_WEBHOOK_URL=https://tps10-9-291176869049.us-central1.run.app
```

**If missing, add it:**
```bash
gcloud run services update tph10-13 \
    --region us-central1 \
    --set-env-vars TPS_WEBHOOK_URL=https://tps10-9-291176869049.us-central1.run.app
```

---

## Testing Procedure

### Step 1: Trigger a Test Payment

1. Generate a payment URL with your token generator
2. Open the URL in a browser
3. User should receive Telegram invite link
4. Payment should complete successfully

---

### Step 2: Monitor tph10-13 Logs

**Open Cloud Console:**
```
Cloud Run → tph10-13 → Logs
```

**Search for these log patterns in order:**

#### 2.1 Invite Link Sent
```
Search: "✅ You've been granted access!"
```
✅ **If found:** User received invite, payment completed

#### 2.2 Payment Split Initiated
```
Search: "🚀 [PAYMENT_SPLITTING] Starting Client Payout"
```
✅ **If found:** Payment split flow started
❌ **If NOT found:** Payment split never triggered → Check code flow

#### 2.3 Webhook Trigger Attempt
```
Search: "🔄 [PAYMENT_SPLITTING] Triggering TPS10-9 webhook"
```
✅ **If found:** Webhook function called
❌ **If NOT found:** Function never reached

#### 2.4 TPS_WEBHOOK_URL Check
```
Search: "⚠️ [PAYMENT_SPLITTING] TPS_WEBHOOK_URL not configured"
```
❌ **If found:** **ROOT CAUSE IDENTIFIED** → TPS_WEBHOOK_URL missing

#### 2.5 Webhook Success
```
Search: "✅ [PAYMENT_SPLITTING] Webhook triggered successfully"
```
✅ **If found:** tps10-9 received webhook
❌ **If NOT found:** Check error logs below

#### 2.6 Webhook Errors
```
Search: "❌ [PAYMENT_SPLITTING] Webhook failed"
Search: "❌ [PAYMENT_SPLITTING] Webhook request timeout"
Search: "❌ [PAYMENT_SPLITTING] Webhook connection error"
```
❌ **If found:** tps10-9 not accessible or rejecting webhook

---

### Step 3: Monitor tps10-9 Logs

**Open Cloud Console:**
```
Cloud Run → tps10-9 → Logs
```

**Search for these patterns (these are the NEW enhanced logs):**

#### 3.1 Webhook Received
```
Search: "🎯 [WEBHOOK] TPS10-9 Webhook Called"
```
✅ **If found:** Webhook reached tps10-9
❌ **If NOT found:** **ROOT CAUSE:** Webhook never reached service

#### 3.2 Processing Started
```
Search: ">>> ENTERING process_payment_split <<<"
```
✅ **If found:** Payment processing initiated
❌ **If NOT found:** Webhook rejected before processing

#### 3.3 Field Validation
```
Search: "Step 1: Validating required fields"
```
✅ **If found with "All required fields present":** Validation passed
❌ **If found with "VALIDATION FAILED":** Missing fields in webhook payload

#### 3.4 Currency Pair Validation
```
Search: "Step 3: Validating currency pair"
```
✅ **If found with "Currency pair validated":** Pair supported
❌ **If found with "VALIDATION FAILED":** **ROOT CAUSE:** Currency not supported

#### 3.5 Amount Validation
```
Search: "Step 4: Checking amount limits"
```
✅ **If found with "Amount within valid limits":** Amount OK
❌ **If found with "VALIDATION FAILED":** **ROOT CAUSE:** Amount too small/large

#### 3.6 Transaction Creation Call
```
Search: ">>> ENTERING create_fixed_rate_transaction <<<"
```
✅ **If found:** Function called
❌ **If NOT found:** **ROOT CAUSE:** Never reached this step

#### 3.7 ChangeNow API Request Preparation
```
Search: ">>> STARTING ChangeNow API Transaction <<<"
```
✅ **If found:** API call preparation started
❌ **If NOT found:** Function exited before API call

#### 3.8 Payload Logging
```
Search: "Complete payload:"
```
✅ **If found:** Check if payload structure matches your working curl command
❌ **If NOT found:** Payload never created

#### 3.9 API Request Sent
```
Search: ">>> ENTERING _make_request <<<"
```
✅ **If found:** HTTP request being sent
❌ **If NOT found:** **ROOT CAUSE:** Request blocked before _make_request

#### 3.10 HTTP Request Details
```
Search: "POST https://api.changenow.io/v2/exchange"
Search: "Request body:"
```
✅ **If found:** Actual HTTP request being made
❌ **If NOT found:** Request preparation failed

#### 3.11 API Response Received
```
Search: "Response received!"
Search: "Response status:"
```
✅ **If found:** ChangeNow server responded
❌ **If NOT found:** **ROOT CAUSE:** Request never sent or timeout

#### 3.12 Response Status Code
```
Search: "Response status: 200"
```
✅ **200:** Success!
❌ **400:** Bad request (payload issue)
❌ **401:** Unauthorized (API key issue)
❌ **403:** Forbidden (API key permissions)
❌ **429:** Rate limited
❌ **500:** ChangeNow server error

#### 3.13 Success Confirmation
```
Search: "✅ [CHANGENOW_TRANSACTION] Transaction created successfully!"
Search: "Transaction ID:"
```
✅ **If found:** **ChangeNow API IS WORKING!**
❌ **If NOT found:** Transaction creation failed

---

## Interpreting Results

### Scenario 1: TPS_WEBHOOK_URL Not Configured

**Symptoms:**
- tph10-13 logs show: `"⚠️ [PAYMENT_SPLITTING] TPS_WEBHOOK_URL not configured"`
- tps10-9 logs show: No webhook received

**Root Cause:** TPS_WEBHOOK_URL environment variable missing in tph10-13

**Fix:**
```bash
gcloud run services update tph10-13 \
    --region us-central1 \
    --set-env-vars TPS_WEBHOOK_URL=https://tps10-9-291176869049.us-central1.run.app
```

---

### Scenario 2: tps10-9 Not Deployed

**Symptoms:**
- tph10-13 logs show: `"❌ [PAYMENT_SPLITTING] Webhook connection error"`
- tps10-9 logs show: Nothing (service doesn't exist)

**Root Cause:** tps10-9 service was never deployed

**Fix:** Run deployment command from Step 1 above

---

### Scenario 3: Webhook Signature Verification Failure

**Symptoms:**
- tph10-13 logs show: `"❌ [PAYMENT_SPLITTING] Webhook failed with status 401"`
- tps10-9 logs show: `"❌ [WEBHOOK] Invalid signature"`

**Root Cause:** SUCCESS_URL_SIGNING_KEY (tph10-13) ≠ WEBHOOK_SIGNING_KEY (tps10-9)

**Fix:** Ensure both services use the same signing key secret

---

### Scenario 4: CHANGENOW_API_KEY Not Configured

**Symptoms:**
- tps10-9 logs show: No `"🔗 [CHANGENOW_CLIENT] Initialized with API key"`
- tps10-9 logs show: Config manager errors

**Root Cause:** CHANGENOW_API_KEY environment variable missing or secret not accessible

**Fix:**
```bash
# Verify secret exists
gcloud secrets versions access latest --secret="CHANGENOW_API_KEY"

# If missing, create it
echo -n "0e7ab0b9cfd8dd81479e811eb583b01a2b5c7f3aac00d5075225a4241e0a5bde" | \
    gcloud secrets create CHANGENOW_API_KEY --data-file=-

# Ensure tps10-9 has access
gcloud run services update tps10-9 \
    --region us-central1 \
    --set-env-vars CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest
```

---

### Scenario 5: Currency Pair Not Supported

**Symptoms:**
- tps10-9 logs show: `"❌ [PAYMENT_SPLITTING] VALIDATION FAILED! Currency pair not supported"`
- No API call made

**Root Cause:** User requested payout currency not available on ChangeNow

**Fix:** Check available pairs with `get_available_pairs()` or use different currency

---

### Scenario 6: Amount Outside Limits

**Symptoms:**
- tps10-9 logs show: `"❌ [PAYMENT_SPLITTING] VALIDATION FAILED! Amount outside limits"`
- No API call made

**Root Cause:** Payment amount below ChangeNow minimum or above maximum

**Fix:** Adjust subscription price or check ChangeNow limits for the currency pair

---

### Scenario 7: API Request Timeout

**Symptoms:**
- tps10-9 logs show: `"❌ [CHANGENOW_API] Request timeout after 30s"`
- No response received

**Root Cause:** ChangeNow server not responding or network issue

**Fix:** Retry payment, check ChangeNow status page

---

### Scenario 8: API Key Invalid/Unauthorized

**Symptoms:**
- tps10-9 logs show: `"Response status: 401"`
- API request sent but rejected

**Root Cause:** API key incorrect or expired

**Fix:** Update CHANGENOW_API_KEY secret with valid key

---

### Scenario 9: Malformed Request Payload

**Symptoms:**
- tps10-9 logs show: `"Response status: 400"`
- Response body shows validation errors

**Root Cause:** Payload structure incorrect

**Fix:** Compare logged payload with working curl command, fix differences

---

## Next Steps After Testing

Once you've completed the test payment and reviewed the logs:

1. **Identify which scenario matches your logs**
2. **Apply the corresponding fix**
3. **Redeploy if needed**
4. **Test again to verify fix**
5. **Report findings**

---

## Log Analysis Checklist

Use this checklist while reviewing logs:

### tph10-13 Logs:
- [ ] User received Telegram invite
- [ ] Payment split flow initiated
- [ ] Webhook trigger function called
- [ ] TPS_WEBHOOK_URL configured
- [ ] Webhook sent successfully (200 response)
- [ ] No webhook errors logged

### tps10-9 Logs:
- [ ] Webhook received
- [ ] process_payment_split() entered
- [ ] All required fields present
- [ ] Currency pair validated
- [ ] Amount within limits
- [ ] create_fixed_rate_transaction() called
- [ ] changenow_client.create_fixed_rate_transaction() called
- [ ] _make_request() entered
- [ ] HTTP POST request sent to ChangeNow
- [ ] Response received from ChangeNow
- [ ] Response status code: ________
- [ ] Transaction created successfully
- [ ] Transaction ID logged: ________

---

## Expected Complete Log Flow (Success Case)

```
[tph10-13]
✅ You've been granted access!
🚀 [PAYMENT_SPLITTING] Starting Client Payout
🔄 [PAYMENT_SPLITTING] Triggering TPS10-9 webhook
📦 [PAYMENT_SPLITTING] Payload: user_id=...
🔐 [PAYMENT_SPLITTING] Added webhook signature
✅ [PAYMENT_SPLITTING] Webhook triggered successfully

[tps10-9]
🎯 [WEBHOOK] TPS10-9 Webhook Called
===============================================================================
🔄 [PAYMENT_SPLITTING] >>> ENTERING process_payment_split <<<
📦 [PAYMENT_SPLITTING] Extracting data from webhook payload...
🔍 [PAYMENT_SPLITTING] Step 1: Validating required fields...
✅ [PAYMENT_SPLITTING] All required fields present
🔍 [PAYMENT_SPLITTING] Step 2: Converting sub_price to float...
✅ [PAYMENT_SPLITTING] Price converted: 0.05 ETH
🔍 [PAYMENT_SPLITTING] Step 3: Validating currency pair...
✅ [PAYMENT_SPLITTING] Currency pair validated
🔍 [PAYMENT_SPLITTING] Step 4: Checking amount limits...
✅ [PAYMENT_SPLITTING] Amount within valid limits
🚀 [PAYMENT_SPLITTING] Step 5: Creating ChangeNow transaction...
===============================================================================
🚀 [CHANGENOW_SWAP] >>> ENTERING create_fixed_rate_transaction <<<
📈 [CHANGENOW_SWAP] Step 1: Getting exchange estimate...
✅ [CHANGENOW_SWAP] ✅ Estimate received: 120.5 USDT
🔄 [CHANGENOW_SWAP] Step 2: Creating ChangeNow transaction...
===============================================================================
🚀 [CHANGENOW_TRANSACTION] >>> STARTING ChangeNow API Transaction <<<
📦 [CHANGENOW_TRANSACTION] Complete payload: {...}
🔄 [CHANGENOW_TRANSACTION] Calling _make_request with POST /exchange...
🌐 [CHANGENOW_API] >>> ENTERING _make_request <<<
🌐 [CHANGENOW_API] POST https://api.changenow.io/v2/exchange
🌐 [CHANGENOW_API] API Key (first 8 chars): 0e7ab0b9
📦 [CHANGENOW_API] Request body: {...}
🔄 [CHANGENOW_API] Sending HTTP request...
📊 [CHANGENOW_API] Response received!
📊 [CHANGENOW_API] Response status: 200
✅ [CHANGENOW_API] Request successful
🔄 [CHANGENOW_TRANSACTION] _make_request returned, analyzing response...
✅ [CHANGENOW_TRANSACTION] SUCCESS! Response received from ChangeNow
✅ [CHANGENOW_TRANSACTION] Transaction created successfully!
🆔 [CHANGENOW_TRANSACTION] Transaction ID: abc123...
🏦 [CHANGENOW_TRANSACTION] Deposit address: 0x742d35...
===============================================================================
✅ [CHANGENOW_SWAP] SUCCESS! Transaction object received
✅ [PAYMENT_SPLITTING] Completed successfully
```

---

## Contact

If logs show unexpected behavior not covered in this guide, please:

1. Copy the relevant log sections
2. Note which scenario best matches the symptoms
3. Share findings for further analysis

**End of Guide**
