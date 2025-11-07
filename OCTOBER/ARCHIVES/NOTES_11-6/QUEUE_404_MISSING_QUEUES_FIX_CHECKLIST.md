# Cloud Tasks Queue 404 Error - Missing Queues Fix Checklist

**Date:** 2025-11-02
**Issue:** NP-Webhook failing to enqueue payments to GCWebhook1 (404 Queue not found)
**Status:** 🔄 IN PROGRESS

---

## Executive Summary

After fixing the trailing newline bug (Session 39), payments are now hitting a **404 error** because the `gcwebhook1-queue` Cloud Tasks queue was never created.

### Error Message
```
❌ [CLOUDTASKS] Failed to create task: 404 Queue does not exist.
   If you just created the queue, wait at least a minute for the queue to initialize.
```

### Impact
- ✅ NP-Webhook receiving IPN callbacks successfully
- ✅ Payment validation and outcome_amount_usd calculation working
- ❌ **Unable to enqueue to GCWebhook1** (404 queue not found)
- ❌ Payments validated but NOT processed (no invites sent)

---

## Root Cause Analysis

### Problem 1: Missing Entry Point Queue (CRITICAL)

**Expected:** `gcwebhook1-queue` for NP-Webhook → GCWebhook1 flow
**Reality:** Queue never created

**Why This Happened:**
- Deployment scripts created internal service queues (GCWebhook1 → GCWebhook2, GCWebhook1 → GCSplit1)
- **Forgot to create the entry point queue** for NP-Webhook → GCWebhook1
- Secret Manager has `GCWEBHOOK1_QUEUE=gcwebhook1-queue` but queue doesn't exist

### Problem 2: Inconsistent Queue Naming

**Existing Queues:**
```
✅ gcwebhook-telegram-invite-queue   (GCWebhook1 → GCWebhook2)
✅ gcsplit-webhook-queue              (GCWebhook1 → GCSplit1)
✅ accumulator-payment-queue          (payments to accumulator)
✅ gcsplit-usdt-eth-estimate-queue    (internal split processing)
✅ gchostpay1-batch-queue             (batch payments)
```

**Missing Queues:**
```
❌ gcwebhook1-queue                   (NP-Webhook → GCWebhook1) ← CRITICAL!
❌ gcbatchprocessor-10-26-queue       (if batch processor is active)
```

---

## Fix Checklist

### Phase 1: Create Missing Queues ✅

- [ ] **Task 1.1:** Create `gcwebhook1-queue` (NP-Webhook → GCWebhook1)
  - **Purpose:** Entry point for validated payments from NP-Webhook
  - **Rate Limit:** High (100 dispatches/sec) - fast payment processing
  - **Concurrency:** 150 concurrent tasks
  - **Retry:** Infinite retries for 24 hours
  - **Command:**
    ```bash
    gcloud tasks queues create gcwebhook1-queue \
      --location=us-central1 \
      --max-dispatches-per-second=100 \
      --max-concurrent-dispatches=150 \
      --max-attempts=-1 \
      --max-retry-duration=86400s \
      --min-backoff=10s \
      --max-backoff=300s \
      --max-doublings=5
    ```

- [ ] **Task 1.2:** Verify queue creation
  - **Command:**
    ```bash
    gcloud tasks queues describe gcwebhook1-queue --location=us-central1
    ```

- [ ] **Task 1.3:** Create `gcbatchprocessor-10-26-queue` (if needed)
  - **Check if GCBatchProcessor is active**
  - **Create queue only if service is deployed and used**

### Phase 2: Verify Queue Architecture ✅

- [ ] **Task 2.1:** List all existing queues
  - **Command:**
    ```bash
    gcloud tasks queues list --location=us-central1
    ```

- [ ] **Task 2.2:** Map queues to services
  - **Create architecture diagram of queue flow**
  - **Verify each service has required queues**

- [ ] **Task 2.3:** Check Secret Manager queue mappings
  - **Verify all queue name secrets match actual queues**
  - **List:**
    - GCWEBHOOK1_QUEUE → gcwebhook1-queue ✅
    - GCWEBHOOK2_QUEUE → gcwebhook-telegram-invite-queue ✅
    - GCSPLIT1_QUEUE → gcsplit-webhook-queue ✅
    - GCSPLIT2_QUEUE → gcsplit-usdt-eth-estimate-queue ✅
    - GCSPLIT3_QUEUE → gcsplit-eth-client-swap-queue ✅
    - GCACCUMULATOR_QUEUE → accumulator-payment-queue ✅
    - GCBATCHPROCESSOR_QUEUE → gcbatchprocessor-10-26-queue (if exists)
    - GCHOSTPAY1_QUEUE → gchostpay1-batch-queue ✅
    - GCHOSTPAY2_QUEUE → gchostpay2-status-check-queue ✅
    - GCHOSTPAY3_QUEUE → gchostpay3-payment-exec-queue ✅

### Phase 3: Test Payment Flow ✅

- [ ] **Task 3.1:** Create new test payment
  - **Start TelePay bot** (if not running)
  - **Generate test payment via Telegram**
  - **Complete payment using NowPayments**

- [ ] **Task 3.2:** Monitor np-webhook-10-26 logs
  - **Command:**
    ```bash
    gcloud run services logs read np-webhook-10-26 \
      --region=us-central1 \
      --limit=50 \
      --format="value(textPayload)"
    ```
  - **Expected:**
    ```
    ✅ [CLOUDTASKS] Task created successfully
    🎯 [ORCHESTRATION] Successfully enqueued to GCWebhook1
    ```
  - **Should NOT see:**
    ```
    ❌ [CLOUDTASKS] Failed to create task: 404 Queue does not exist
    ```

- [ ] **Task 3.3:** Monitor GCWebhook1-10-26 logs
  - **Command:**
    ```bash
    gcloud run services logs read gcwebhook1-10-26 \
      --region=us-central1 \
      --limit=50
    ```
  - **Expected:**
    ```
    ✅ [PAYMENT] Processing validated payment from NP-Webhook
    🎯 [PAYMENT] Routing to GCSplit1 or GCAccumulator
    ```

- [ ] **Task 3.4:** Verify end-to-end flow
  - **User receives Telegram invite link** ✅
  - **Payment record updated in database** ✅
  - **No errors in any service logs** ✅

### Phase 4: Documentation & Prevention ✅

- [ ] **Task 4.1:** Update PROGRESS.md
  - **Add Session 40 entry documenting queue fix**

- [ ] **Task 4.2:** Update DECISIONS.md
  - **Document queue naming conventions**
  - **Document queue creation checklist for new services**

- [ ] **Task 4.3:** Create queue deployment verification script
  - **Script to check all required queues exist**
  - **Run before each deployment**

- [ ] **Task 4.4:** Update deployment documentation
  - **Add "Verify queues exist" step to deployment guides**
  - **Document queue creation for each service**

---

## Queue Architecture Reference

### Payment Processing Flow

```
1. NowPayments IPN
   ↓
2. NP-Webhook (receives IPN, validates, stores payment_id)
   ↓ [gcwebhook1-queue] ← MISSING! (404 ERROR)
   ↓
3. GCWebhook1 (orchestrates payment routing)
   ├─ [gcwebhook-telegram-invite-queue] → GCWebhook2 (send invite)
   └─ [gcsplit-webhook-queue] → GCSplit1 (process payment)
      ↓
4. GCSplit1 (splits payment or accumulates)
   ├─ Instant: [gcsplit-usdt-eth-estimate-queue] → GCSplit2
   └─ Threshold: [accumulator-payment-queue] → GCAccumulator
```

### Required Queue Configurations

#### High-Priority Queues (Payments)
- **gcwebhook1-queue:** 100 dispatches/sec, 150 concurrent
- **gcsplit-webhook-queue:** 100 dispatches/sec, 150 concurrent
- **accumulator-payment-queue:** 50 dispatches/sec, 100 concurrent

#### Medium-Priority Queues (Internal)
- **gcwebhook-telegram-invite-queue:** 8 dispatches/sec, 24 concurrent (Telegram rate limit)
- **gcsplit-usdt-eth-estimate-queue:** 50 dispatches/sec, 100 concurrent
- **gcsplit-eth-client-swap-queue:** 50 dispatches/sec, 100 concurrent

#### Low-Priority Queues (Batch Processing)
- **gchostpay1-batch-queue:** 20 dispatches/sec, 50 concurrent
- **gchostpay2-status-check-queue:** 10 dispatches/sec, 20 concurrent
- **gchostpay3-payment-exec-queue:** 20 dispatches/sec, 50 concurrent
- **gchostpay3-retry-queue:** 5 dispatches/sec, 10 concurrent

---

## Risk Assessment

### Risks Mitigated ✅
1. **Queue naming validated** - No more newline characters
2. **Code defensive** - All services strip whitespace
3. **Architecture documented** - Queue flow clearly mapped

### Remaining Risks ⚠️
1. **Queue doesn't exist** - Currently blocking payments
   - **Mitigation:** Create queue immediately
   - **Severity:** CRITICAL
   - **Likelihood:** 100% (confirmed missing)

2. **Other queues might be missing**
   - **Mitigation:** Audit all queue dependencies
   - **Severity:** Medium
   - **Likelihood:** Low (most queues exist)

3. **Queue configuration suboptimal**
   - **Mitigation:** Review rate limits and retry policies
   - **Severity:** Low
   - **Likelihood:** Medium

---

## Verification Commands

### Check Queue Exists
```bash
gcloud tasks queues describe gcwebhook1-queue --location=us-central1
```

### List All Queues
```bash
gcloud tasks queues list --location=us-central1 --format="table(name,rateLimits.maxConcurrentDispatches,rateLimits.maxDispatchesPerSecond)"
```

### Check Queue Task Count
```bash
gcloud tasks list --queue=gcwebhook1-queue --location=us-central1
```

### Monitor Queue Activity
```bash
gcloud tasks list --queue=gcwebhook1-queue --location=us-central1 --limit=10
```

---

## Rollback Plan

If issues occur after creating the queue:

### Option 1: Delete New Queue
```bash
gcloud tasks queues delete gcwebhook1-queue --location=us-central1
```

### Option 2: Pause Queue (Keep for Testing)
```bash
gcloud tasks queues pause gcwebhook1-queue --location=us-central1
```

### Option 3: Resume Queue
```bash
gcloud tasks queues resume gcwebhook1-queue --location=us-central1
```

---

## Success Criteria

- [x] `gcwebhook1-queue` created and operational
- [ ] NP-Webhook successfully enqueues to GCWebhook1 (no 404 errors)
- [ ] GCWebhook1 receives and processes tasks
- [ ] Test payment completes end-to-end successfully
- [ ] All queue dependencies verified and documented

---

**Next Action:** Create `gcwebhook1-queue` and test payment flow

**Status:** ⏳ READY TO EXECUTE
