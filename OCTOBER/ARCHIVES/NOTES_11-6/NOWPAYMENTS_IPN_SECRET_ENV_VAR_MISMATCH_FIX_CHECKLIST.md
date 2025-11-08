# NowPayments IPN Secret Environment Variable Mismatch Fix Checklist

**Date:** 2025-11-02
**Issue:** IPN signature verification failing due to environment variable name mismatch
**Status:** 🟢 IN PROGRESS

---

## Root Cause Analysis

### The Problem
NP-Webhook service is rejecting all IPN callbacks from NowPayments with:
```
❌ [IPN] Cannot verify signature - NOWPAYMENTS_IPN_SECRET not configured
❌ [IPN] Signature verification failed - rejecting request
```

### Root Cause
**Environment Variable Name Mismatch:**
- **Deployment Configuration:** Sets env var `NOWPAYMENTS_IPN_SECRET_KEY` (with `_KEY` suffix)
- **Code Expectation:** Reads env var `NOWPAYMENTS_IPN_SECRET` (without `_KEY` suffix)
- **Result:** Code cannot find the secret, signature verification fails

### Evidence
```yaml
# Current deployment config (WRONG):
- name: NOWPAYMENTS_IPN_SECRET_KEY  # ← Has _KEY suffix
  valueFrom:
    secretKeyRef:
      key: latest
      name: NOWPAYMENTS_IPN_SECRET  # ← Secret name is correct
```

```python
# Code in app.py line 31 (CORRECT):
NOWPAYMENTS_IPN_SECRET = (os.getenv('NOWPAYMENTS_IPN_SECRET') or '').strip() or None
#                                    ^^^^^^^^^^^^^^^^^^^^^^^^ Looking for env var WITHOUT _KEY
```

---

## Fix Strategy

**Option 1: Fix the deployment config** (RECOMMENDED)
- Change env var name from `NOWPAYMENTS_IPN_SECRET_KEY` → `NOWPAYMENTS_IPN_SECRET`
- Keeps code consistent with logical naming (secret name = env var name)
- Single deployment fix, no code changes needed

**Option 2: Fix the code**
- Change code to read `NOWPAYMENTS_IPN_SECRET_KEY` instead of `NOWPAYMENTS_IPN_SECRET`
- Requires code change + rebuild + redeploy
- Less clean (env var name differs from secret name)

**Decision: Use Option 1** - Fix the deployment configuration

---

## Implementation Checklist

### Phase 1: Verify Current State ✅

#### Task 1.1: Check np-webhook deployment config ✅
- **Status:** COMPLETED
- **Result:** Confirmed env var `NOWPAYMENTS_IPN_SECRET_KEY` (with `_KEY`)

#### Task 1.2: Verify secret exists in Secret Manager ✅
- **Status:** COMPLETED
- **Result:** Secret `NOWPAYMENTS_IPN_SECRET` exists (no `_KEY`)

#### Task 1.3: Confirm code expectation ✅
- **Status:** COMPLETED
- **Result:** Code expects `NOWPAYMENTS_IPN_SECRET` (line 31 of app.py)

### Phase 2: Search for Similar Issues Across All Services ⏳

#### Task 2.1: Check ALL services for NOWPAYMENTS_IPN_SECRET_KEY usage
- **Status:** PENDING
- **Action:** Search all Cloud Run services for this environment variable
- **Services to check:**
  - np-webhook-10-26 (confirmed WRONG)
  - GCWebhook1-10-26
  - GCWebhook2-10-26
  - GCSplit1-10-26, GCSplit2-10-26, GCSplit3-10-26
  - GCAccumulator-10-26
  - GCBatchProcessor-10-26
  - GCMicroBatchProcessor-10-26
  - GCHostPay1-10-26, GCHostPay2-10-26, GCHostPay3-10-26
  - GCRegister10-26
  - GCRegisterAPI-10-26
  - TelePay10-26 (if deployed to Cloud Run)

#### Task 2.2: Check for environment variable naming patterns
- **Status:** PENDING
- **Action:** Verify no other secrets have `_KEY` suffix mismatch
- **Pattern to check:** Any env var with `_KEY` suffix where secret doesn't have `_KEY`

#### Task 2.3: Document all mismatches found
- **Status:** PENDING
- **Action:** Create list of all services with similar issues

### Phase 3: Fix NP-Webhook Service ⏳

#### Task 3.1: Update np-webhook-10-26 deployment
- **Status:** PENDING
- **Command:**
  ```bash
  gcloud run services update np-webhook-10-26 \
    --region=us-central1 \
    --update-env-vars=NOWPAYMENTS_API_KEY=NOWPAYMENTS_API_KEY:latest \
    --update-env-vars=NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest \
    --update-env-vars=CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest \
    --update-env-vars=CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest \
    --update-env-vars=GCWEBHOOK1_QUEUE=GCWEBHOOK1_QUEUE:latest \
    --update-env-vars=GCWEBHOOK1_URL=GCWEBHOOK1_URL:latest \
    --update-env-vars=CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest \
    --update-env-vars=DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest \
    --update-env-vars=DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest \
    --update-env-vars=DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest
  ```
- **Expected Result:** Environment variable `NOWPAYMENTS_IPN_SECRET` available in container

#### Task 3.2: Verify deployment
- **Status:** PENDING
- **Action:** Check service status after update
  ```bash
  gcloud run services describe np-webhook-10-26 --region=us-central1 \
    --format="yaml(spec.template.spec.containers[0].env)"
  ```

#### Task 3.3: Check startup logs
- **Status:** PENDING
- **Action:** Verify `✅ [CONFIG] NOWPAYMENTS_IPN_SECRET loaded` in logs

### Phase 4: Fix Other Affected Services (If Any) ⏳

#### Task 4.1: Apply fixes to other services with same issue
- **Status:** PENDING
- **Dependencies:** Complete Phase 2 first

#### Task 4.2: Verify all fixes deployed
- **Status:** PENDING

### Phase 5: Functional Testing ⏳

#### Task 5.1: Trigger test IPN callback
- **Status:** PENDING
- **Action:** Create test payment to trigger IPN
- **Expected Log:**
  ```
  🔐 [IPN] Signature header present: ...
  ✅ [IPN] Signature verification successful
  ```

#### Task 5.2: Verify payment processing works end-to-end
- **Status:** PENDING
- **Action:** Confirm payment → database update → GCWebhook1 enqueue

#### Task 5.3: Monitor for signature verification errors
- **Status:** PENDING
- **Action:** Check logs for 24 hours for any signature failures

### Phase 6: Documentation ⏳

#### Task 6.1: Update PROGRESS.md
- **Status:** PENDING
- **Content:** Log the fix and lessons learned

#### Task 6.2: Update DECISIONS.md
- **Status:** PENDING
- **Content:** Document decision to use consistent env var naming

#### Task 6.3: Create naming convention guide
- **Status:** PENDING
- **Content:** Document standard: env var name should match secret name unless aliasing is intentional and documented

---

## Key Insights

### Why This Happened
The previous session noted fixing "secret name" from `NOWPAYMENTS_IPN_SECRET_KEY` → `NOWPAYMENTS_IPN_SECRET`, but the fix was incomplete:
- **Fixed:** The secret reference (which Secret Manager secret to use)
- **NOT Fixed:** The environment variable name (what name the code sees)

### The Correct Pattern
```yaml
# CORRECT:
- name: MY_SECRET              # ← Env var name
  valueFrom:
    secretKeyRef:
      name: MY_SECRET          # ← Secret Manager secret name
      key: latest

# WRONG (what we had):
- name: MY_SECRET_KEY          # ← Different from secret name
  valueFrom:
    secretKeyRef:
      name: MY_SECRET          # ← Code can't find it!
      key: latest
```

### Prevention
1. **Naming Convention:** Environment variable name = Secret Manager secret name (unless intentional aliasing)
2. **Verification:** Always check startup logs for `✅ Loaded` vs `❌ Missing` messages
3. **Testing:** Test with real IPN callback before marking deployment as complete

---

## Progress Summary

| Phase | Tasks | Completed | Status |
|-------|-------|-----------|--------|
| Phase 1: Verify Current State | 3 | 3/3 | ✅ COMPLETE |
| Phase 2: Search Similar Issues | 3 | 0/3 | ⏳ PENDING |
| Phase 3: Fix NP-Webhook | 3 | 0/3 | ⏳ PENDING |
| Phase 4: Fix Other Services | 2 | 0/2 | ⏳ PENDING |
| Phase 5: Functional Testing | 3 | 0/3 | ⏳ PENDING |
| Phase 6: Documentation | 3 | 0/3 | ⏳ PENDING |

**Total:** 17 tasks, 3 completed, 14 pending

---

## Next Steps

1. **Search all services** for similar environment variable mismatches (Phase 2)
2. **Fix np-webhook** deployment configuration (Phase 3)
3. **Fix any other affected services** found in Phase 2 (Phase 4)
4. **Test with real IPN** callback (Phase 5)
5. **Update documentation** (Phase 6)
