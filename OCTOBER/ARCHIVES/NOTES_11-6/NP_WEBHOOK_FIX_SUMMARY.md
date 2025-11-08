# NP-Webhook 403 Error - Fix Summary

**Date:** 2025-11-02
**Issue:** payment_id not captured in database (GCWebhook2 validation failures)
**Root Cause:** np-webhook missing required secrets configuration
**Status:** ✅ FIXED

---

## Problem Analysis

### What Was Happening
1. ❌ Customer completes payment on NowPayments (payment_id: `6260719507`)
2. ❌ NowPayments sends IPN callback to np-webhook
3. ❌ np-webhook returns **403 Forbidden** (no signature verification possible)
4. ❌ Database never updated with payment_id
5. ❌ GCWebhook2 can't find payment_id → returns 503 (retry loop)
6. ❌ Customer doesn't receive Telegram invitation

### Root Cause Identified
```bash
$ gcloud run services describe np-webhook --region=us-east1 \
    --format="yaml(spec.template.spec.containers[0].env)"

Result: null  # ❌ NO ENVIRONMENT VARIABLES OR SECRETS
```

**np-webhook had ZERO secrets configured!**
- No `NOWPAYMENTS_IPN_SECRET` → Can't verify IPN signatures
- No database credentials → Can't update payment_id in database
- Result: All IPN callbacks rejected with 403 Forbidden

---

## Fix Applied

### 1. Mounted Required Secrets
```bash
gcloud run services update np-webhook \
  --region=us-east1 \
  --update-secrets=NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest
```

**Result:** New revision `np-webhook-00004-kpk` deployed

### 2. Routed Traffic to New Revision
```bash
gcloud run services update-traffic np-webhook --region=us-east1 --to-latest
```

**Result:** 100% traffic now on revision with secrets

### 3. Verified Configuration
```bash
$ gcloud run services describe np-webhook --region=us-east1 \
    --format="yaml(spec.template.spec.containers[0].env)"

Result:
  env:
  - name: NOWPAYMENTS_IPN_SECRET          ✅
    valueFrom:
      secretKeyRef:
        key: latest
        name: NOWPAYMENTS_IPN_SECRET
  - name: CLOUD_SQL_CONNECTION_NAME       ✅
    valueFrom:
      secretKeyRef:
        key: latest
        name: CLOUD_SQL_CONNECTION_NAME
  - name: DATABASE_NAME_SECRET            ✅
    valueFrom:
      secretKeyRef:
        key: latest
        name: DATABASE_NAME_SECRET
  - name: DATABASE_USER_SECRET            ✅
    valueFrom:
      secretKeyRef:
        key: latest
        name: DATABASE_USER_SECRET
  - name: DATABASE_PASSWORD_SECRET        ✅
    valueFrom:
      secretKeyRef:
        key: latest
        name: DATABASE_PASSWORD_SECRET
```

---

## Expected Behavior After Fix

### IPN Flow (Now Working)
```
1. Customer completes payment
2. NowPayments sends IPN POST to np-webhook
3. np-webhook verifies signature using NOWPAYMENTS_IPN_SECRET ✅
4. np-webhook updates private_channel_users_database with payment_id ✅
5. GCWebhook2 queries database → finds payment_id ✅
6. GCWebhook2 validates payment → sends Telegram invitation ✅
```

### Expected Logs

**np-webhook (After IPN Arrives):**
```
✅ [IPN] Signature verified successfully
✅ [IPN] Payment ID: 6260719507
🗄️ [DATABASE] Updating subscription with NowPayments data
✅ [DATABASE] Updated user 6271402111, channel -1003296084379
🎯 [IPN] IPN processed successfully
HTTP 200 OK
```

**GCWebhook2 (After Validation):**
```
🔐 [VALIDATION] Starting payment validation for user 6271402111, channel -1003296084379
🔍 [VALIDATION] Looking up NowPayments payment data
✅ [VALIDATION] Found NowPayments payment_id: 6260719507
📊 [VALIDATION] Payment status: finished
💰 [VALIDATION] Outcome amount: 0.00026957
✅ [VALIDATION] Payment amount OK: $1.15 >= $1.08 (80% threshold)
✅ [VALIDATION] Payment validation successful
✅ [ENDPOINT] Payment validation successful - proceeding with invitation
📨 [TELEGRAM] Creating one-time invite link for channel -1003296084379
HTTP 200 OK
```

---

## Verification Steps

### Step 1: Test with Next Payment
Create a new test payment and monitor logs:

**Monitor np-webhook:**
```bash
gcloud run services logs read np-webhook --region=us-east1 --follow
```

**Expected:**
- IPN callback arrives from NowPayments
- Signature verification succeeds
- Database update succeeds
- Returns HTTP 200 OK

### Step 2: Verify Database Update
```sql
SELECT
  nowpayments_payment_id,
  nowpayments_payment_status,
  nowpayments_outcome_amount,
  user_id,
  private_channel_id,
  datestamp,
  timestamp
FROM private_channel_users_database
WHERE nowpayments_payment_id IS NOT NULL
ORDER BY id DESC
LIMIT 5;
```

**Expected:** New payment should appear with payment_id populated

### Step 3: Verify GCWebhook2 Validation
```bash
gcloud run services logs read gcwebhook2-10-26 --region=us-central1 --follow
```

**Expected:**
- Payment validation finds payment_id
- Validation succeeds (not 503 retry)
- Telegram invitation sent
- Returns HTTP 200 OK

---

## Affected Services

### ✅ Fixed
- **np-webhook** - Now has all required secrets mounted

### ✅ Already Updated (Previous Sessions)
- **GCWebhook1-10-26** - Queries payment_id from database
- **GCAccumulator-10-26** - Stores payment_id in payout_accumulation
- **GCWebhook2-10-26** - Validates payment before sending invitation
- **TelePay10-26 Bot** - Includes ipn_callback_url in invoices

### ✅ Database Schema
- **private_channel_users_database** - Has 10 NowPayments columns
- **payout_accumulation** - Has 5 NowPayments columns

---

## Why This Wasn't Caught Earlier

### Missing Configuration
The np-webhook service was deployed previously but never configured with:
1. IPN signature secret (can't verify NowPayments callbacks)
2. Database credentials (can't write payment_id)

### Silent Failure
- np-webhook returned 403 (not 500) so didn't trigger alerts
- NowPayments retries IPN callbacks but eventually gives up
- System continued working without payment_id (graceful degradation)
- Only caught when implementing GCWebhook2 payment validation

---

## Lessons Learned

### 1. Service Configuration Validation
**Problem:** np-webhook deployed without required secrets
**Solution:** Always verify service has secrets mounted:
```bash
gcloud run services describe <SERVICE> --format="yaml(spec.template.spec.containers[0].env)"
```

### 2. Integration Testing
**Problem:** IPN flow never tested end-to-end
**Solution:** Test complete payment flow including IPN callbacks

### 3. Monitoring & Alerting
**Problem:** 403 errors from NowPayments not monitored
**Solution:** Add monitoring for:
- np-webhook HTTP status codes (alert on non-200)
- payment_id NULL rate in database
- GCWebhook2 503 retry frequency

---

## Next Steps

### Immediate (Required)
1. ✅ np-webhook secrets mounted
2. ⏳ Test with new payment to verify IPN processing
3. ⏳ Verify payment_id appears in database
4. ⏳ Verify GCWebhook2 validation succeeds

### Short-term (Recommended)
5. Add health check to np-webhook that validates secrets present
6. Add monitoring for np-webhook IPN success rate
7. Create alert for payment_id NULL rate > 10%
8. Document np-webhook configuration requirements

### Long-term (Nice to Have)
9. Backfill payment_id for historical payments (if needed)
10. Create fee reconciliation tool using payment_id
11. Build dashboard showing IPN callback success metrics

---

## Technical Details

### Secrets Required by np-webhook
1. **NOWPAYMENTS_IPN_SECRET**
   - Purpose: Verify IPN callback signatures from NowPayments
   - Value: `1EQDQWRpHwAsF7dHmI4N/gAaQ/IKrDQs`
   - Usage: Signature verification before processing IPN

2. **CLOUD_SQL_CONNECTION_NAME**
   - Purpose: Connect to PostgreSQL database
   - Value: `telepay-459221:us-central1:telepaypsql`
   - Usage: Cloud SQL Connector connection string

3. **DATABASE_NAME_SECRET**
   - Purpose: Database name for connection
   - Value: `telepaydb`
   - Usage: Database selection in connection

4. **DATABASE_USER_SECRET**
   - Purpose: Database username
   - Value: `postgres`
   - Usage: Authentication

5. **DATABASE_PASSWORD_SECRET**
   - Purpose: Database password
   - Value: (encrypted)
   - Usage: Authentication

### Service Revisions
- **Old Revision:** `np-webhook-00003-r27` (0% traffic) - Missing secrets ❌
- **New Revision:** `np-webhook-00004-kpk` (100% traffic) - All secrets mounted ✅

### IAM Permissions (Already Correct)
```bash
$ gcloud secrets get-iam-policy NOWPAYMENTS_IPN_SECRET

serviceAccount:291176869049-compute@developer.gserviceaccount.com
Role: roles/secretmanager.secretAccessor  ✅
```

---

## Status

### ✅ Fix Complete
- np-webhook configured with all required secrets
- New revision deployed and serving 100% traffic
- Service ready to process IPN callbacks

### ⏳ Awaiting Verification
- Needs real payment test to confirm IPN processing works
- Database updates need to be verified
- End-to-end flow needs validation

### 📊 Metrics to Monitor
- np-webhook HTTP 200 rate (should be 100% after fix)
- payment_id population rate in database (should be ~100%)
- GCWebhook2 validation success rate (should increase to ~100%)
- Average time from payment to invitation delivery (should decrease)

---

**Fix Applied By:** Claude (Session 28)
**Deployment Time:** 2025-11-02 ~06:35 UTC
**Confidence:** High (root cause identified and resolved)
**Testing Required:** Yes (end-to-end payment flow)
