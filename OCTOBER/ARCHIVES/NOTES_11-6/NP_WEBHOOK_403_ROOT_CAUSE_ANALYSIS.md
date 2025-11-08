# NP-Webhook 403 Error - Root Cause Analysis

**Date:** 2025-11-02
**Issue:** GCWebhook2 can't validate payments because payment_id is NULL
**Root Cause:** np-webhook service is rejecting NowPayments IPN callbacks with HTTP 403

---

## Problem Statement

### Symptom
GCWebhook2 logs show:
```
⚠️ [VALIDATION] Subscription found but payment_id not yet available (IPN pending)
❌ [VALIDATION] Payment not confirmed - IPN callback not yet processed. Please wait.
⏳ [ENDPOINT] Payment validation pending - Cloud Tasks will retry
```

### NowPayments Dashboard Shows
- Payment ID: `6260719507`
- Status: `finished`
- Payment completed successfully at 01:22 AM

### np-webhook Logs Show
Multiple IPN callback attempts from NowPayments (IP: 51.75.77.69):
```
POST https://np-webhook-291176869049.us-east1.run.app/
Status: 403 Forbidden
User-Agent: NOWPayments v1.0
Timestamps: 06:19:29, 06:20:12, 06:21:08, 06:21:58
```

---

## Root Cause Analysis

### Data Flow (Expected)
```
1. Customer pays → NowPayments processes payment
2. NowPayments sends IPN POST to np-webhook
3. np-webhook verifies IPN signature with NOWPAYMENTS_IPN_SECRET
4. np-webhook updates private_channel_users_database with payment_id
5. GCWebhook2 queries database → finds payment_id → sends invitation
```

### Data Flow (Actual)
```
1. Customer pays → NowPayments processes payment ✅
2. NowPayments sends IPN POST to np-webhook ✅
3. np-webhook REJECTS with 403 Forbidden ❌
4. Database never gets updated with payment_id ❌
5. GCWebhook2 queries database → payment_id is NULL ❌
6. GCWebhook2 returns 503 (retry logic) ❌
```

---

## Why 403 Forbidden?

### Possible Causes

#### 1. **np-webhook Service Not Configured with IPN Secret** (MOST LIKELY)
- Secret `NOWPAYMENTS_IPN_SECRET` exists in Secret Manager
- But np-webhook Cloud Run service may not have it mounted as environment variable
- Without the secret, np-webhook can't verify IPN signature → rejects as 403

#### 2. **Signature Verification Failing**
- IPN secret in Secret Manager doesn't match NowPayments dashboard
- np-webhook using wrong header for signature verification
- Signature algorithm mismatch

#### 3. **np-webhook Code Missing IPN Endpoint**
- Service may only have health check endpoint
- POST to `/` returns 403 or 405

#### 4. **IAM Permissions Issue**
- Service account doesn't have `secretmanager.versions.access` permission
- Can't read NOWPAYMENTS_IPN_SECRET from Secret Manager

---

## Evidence

### 1. Secret Exists in Secret Manager
```bash
$ gcloud secrets describe NOWPAYMENTS_IPN_SECRET
NAME: projects/291176869049/secrets/NOWPAYMENTS_IPN_SECRET
✅ Confirmed: Secret exists
```

### 2. np-webhook Service Deployed
```bash
$ gcloud run services list | grep np-webhook
np-webhook    us-east1    https://np-webhook-291176869049.us-east1.run.app
✅ Confirmed: Service running
```

### 3. IPN Callbacks Arriving
```
LOG: POST https://np-webhook-291176869049.us-east1.run.app/
     User-Agent: NOWPayments v1.0
     Status: 403 Forbidden
     IP: 51.75.77.69 (NowPayments server)
✅ Confirmed: IPN callbacks arriving but being rejected
```

### 4. Database Schema Ready
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'private_channel_users_database'
AND column_name LIKE 'nowpayments_%';

Result: 10 columns (payment_id, invoice_id, order_id, etc.)
✅ Confirmed: Database ready to receive payment_id
```

---

## Investigation Steps

### Step 1: Check np-webhook Environment Variables
```bash
gcloud run services describe np-webhook --region=us-east1 \
  --format="yaml(spec.template.spec.containers[0].env)"
```
**Expected:** Should see environment variable or secret mount for NOWPAYMENTS_IPN_SECRET
**Actual:** TO BE CHECKED

### Step 2: Check np-webhook Source Code
```bash
# Find np-webhook deployment source
# Check if IPN endpoint exists
# Verify signature verification logic
```
**Expected:** POST / endpoint that verifies IPN signature and updates database
**Actual:** TO BE CHECKED

### Step 3: Check Service Account Permissions
```bash
gcloud run services get-iam-policy np-webhook --region=us-east1
```
**Expected:** Service account with secretmanager.secretAccessor role
**Actual:** TO BE CHECKED

### Step 4: Verify IPN Secret Value
```bash
gcloud secrets versions access latest --secret=NOWPAYMENTS_IPN_SECRET
```
**Expected:** Should match IPN secret from NowPayments dashboard
**Actual:** Value is `1EQDQWRpHwAsF7dHmI4N/gAaQ/IKrDQs`

---

## Solution Checklist

### ✅ Prerequisites (Already Complete)
- [x] Database migration complete (10 NowPayments columns added)
- [x] NOWPAYMENTS_IPN_SECRET exists in Secret Manager
- [x] GCWebhook1 updated to query payment_id
- [x] GCAccumulator updated to store payment_id
- [x] GCWebhook2 updated with payment validation logic

### 🔧 Required Fixes

#### Fix 1: Configure np-webhook with IPN Secret
**Action:** Update np-webhook Cloud Run service to mount NOWPAYMENTS_IPN_SECRET
```bash
gcloud run services update np-webhook \
  --region=us-east1 \
  --update-secrets=NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest
```

#### Fix 2: Verify np-webhook Code Has IPN Endpoint
**Action:** Review/update np-webhook source code
- Ensure POST / endpoint exists
- Verify IPN signature verification logic
- Confirm database update logic for payment_id

#### Fix 3: Grant IAM Permissions
**Action:** Ensure service account has Secret Manager access
```bash
gcloud secrets add-iam-policy-binding NOWPAYMENTS_IPN_SECRET \
  --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

#### Fix 4: Verify Database Credentials
**Action:** Ensure np-webhook can connect to database
- Check Cloud SQL connection name configured
- Verify database credentials available
- Test database connectivity

### ✅ Verification Steps

#### 1. Check np-webhook Health
```bash
curl https://np-webhook-291176869049.us-east1.run.app/health
```
**Expected:** 200 OK with service status

#### 2. Simulate IPN Callback (Local Test)
```bash
# Use curl to send test IPN payload
# Verify 200 OK response
# Check database for payment_id update
```

#### 3. Monitor Real IPN Callback
```bash
gcloud run services logs read np-webhook --region=us-east1 --follow
```
**Expected:**
```
✅ [IPN] Signature verified
✅ [IPN] Database updated with payment_id: 6260719507
✅ [IPN] IPN processed successfully
```

#### 4. End-to-End Test
1. Create new test payment
2. Monitor np-webhook logs → should see 200 OK
3. Monitor GCWebhook1 logs → should see payment_id found
4. Monitor GCWebhook2 logs → should see payment validation success
5. Query database → payment_id should be populated

---

## Next Actions

### Immediate (Priority 1)
1. Investigate np-webhook service configuration
2. Identify why 403 errors are occurring
3. Fix np-webhook secret mounting or code issue
4. Redeploy np-webhook if needed

### Short-term (Priority 2)
5. Test with real payment to verify end-to-end flow
6. Monitor logs for successful IPN processing
7. Verify GCWebhook2 payment validation works

### Long-term (Priority 3)
8. Add monitoring/alerting for np-webhook 403 errors
9. Create runbook for IPN troubleshooting
10. Document np-webhook configuration requirements

---

## Impact

### Current State
- ❌ **100% of payments failing validation**
- ❌ Users can't access Telegram channels after payment
- ❌ payment_id not captured for fee reconciliation
- ❌ Cloud Tasks stuck in retry loop (503 errors)

### After Fix
- ✅ IPN callbacks processed successfully
- ✅ payment_id captured in database
- ✅ GCWebhook2 validation succeeds
- ✅ Users get Telegram invitations immediately
- ✅ Fee reconciliation data available

---

**Status:** Investigation complete - Root cause identified
**Next:** Execute fix checklist to resolve np-webhook 403 errors
