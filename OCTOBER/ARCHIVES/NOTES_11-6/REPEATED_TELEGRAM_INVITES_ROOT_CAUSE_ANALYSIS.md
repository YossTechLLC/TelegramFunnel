# Repeated Telegram Invites - Root Cause Analysis

**Date:** 2025-11-02
**Issue:** Telegram bot sending repeated one-time invitation links in a cycle
**Status:** 🔍 ROOT CAUSE IDENTIFIED

---

## Executive Summary

After Session 40's type conversion fix, GCWebhook1 successfully processes payments and sends Telegram invites, **BUT crashes with HTTP 500 error** immediately after. Cloud Tasks interprets the 500 as a failure and retries the same payment, causing:

- ✅ Payment processed successfully to GCAccumulator/GCSplit1
- ✅ Telegram invite sent successfully to GCWebhook2
- ❌ **GCWebhook1 crashes with TypeError at line 437**
- ❌ **Cloud Tasks retries the SAME payment** (11-12 times per payment)
- ❌ **Each retry sends a NEW Telegram invite**

---

## Symptoms

### User Report
```
PayGatePrime, [11/2/2025 10:59 AM]
✅ You've been granted access!
Here is your one-time invite link:
https://t.me/+ANBtioyHy49jNDQx

PayGatePrime, [11/2/2025 11:02 AM]
✅ You've been granted access!
Here is your one-time invite link:
https://t.me/+l7pb9PEqSzdhN2Vh

[... 9 more invites in 13 minutes ...]
```

### Log Evidence

**GCWebhook1 Logs (16:02:18):**
```
🎯 [VALIDATED] Received validated payment from NP-Webhook
✅ [VALIDATED] Payment Data Received:
   User ID: 6271402111
   Channel ID: -1003296084379
   Payment ID: 4364424903
✅ [VALIDATED] Successfully enqueued to GCAccumulator
✅ [VALIDATED] Enqueued Telegram invite to GCWebhook2
❌ [VALIDATED] Unexpected error: unsupported operand type(s) for -: 'float' and 'str'
```

**HTTP Response:**
```
POST /process-validated-payment HTTP/1.1
Status: 500 Internal Server Error
```

**Cloud Tasks Queue Status:**
```
TASK_NAME             DISPATCH_ATTEMPTS  LAST_ATTEMPT_STATUS
9928316398378024711   11                 INTERNAL(13): HTTP status code 500
4849204958515981235   11                 INTERNAL(13): HTTP status code 500
00873497653357580501  12                 INTERNAL(13): HTTP status code 500
65569508316581070531  12                 INTERNAL(13): HTTP status code 500
```

**Pattern:** Same 4 payments retried 11-12 times each, every ~30-60 seconds.

---

## Root Cause Analysis

### The Error

**File:** `GCWebhook1-10-26/tph1-10-26.py`
**Line:** 437
**Error:** `TypeError: unsupported operand type(s) for -: 'float' and 'str'`

```python
# Lines 432-438
return jsonify({
    "status": "success",
    "message": "Payment processed with actual outcome amount",
    "outcome_amount_usd": outcome_amount_usd,     # float
    "declared_price": subscription_price,          # str (converted at line 390)
    "difference": outcome_amount_usd - subscription_price  # ← LINE 437: CRASH!
}), 200
```

### How This Happened

#### Session 40 Part 2 - Type Conversion Fix (PREVIOUS)
To fix token encryption failure, I added type conversion at lines 387-394:

```python
# Lines 387-394 (Session 40 fix)
# Ensure subscription_price is string for token encryption
try:
    subscription_price = str(subscription_price)
except (ValueError, TypeError) as e:
    print(f"❌ [VALIDATED] Invalid type for subscription_price: {e}")
    abort(400, "Invalid subscription_price type")
```

**Result:**
- ✅ Token encryption now works (requires string)
- ❌ **Broke the calculation at line 437** (requires float)

#### Original Code Behavior
Before Session 40:
- `subscription_price` was a number (float/int)
- Line 437 calculation worked: `float - float = float`

After Session 40:
- `subscription_price` is a string: `"1.35"`
- Line 437 calculation fails: `float - str = TypeError`

### Why It Causes Repeated Invites

**Execution Flow:**
```
1. GCWebhook1 receives task from Cloud Tasks
2. ✅ Processes payment successfully
3. ✅ Enqueues to GCAccumulator (payment processed)
4. ✅ Enqueues to GCWebhook2 (Telegram invite sent)
5. ❌ Crashes at line 437 (trying to return response)
6. ❌ Flask catches exception, returns HTTP 500
7. Cloud Tasks sees 500 error → Assumes task failed
8. Cloud Tasks retries task (exponential backoff: 10s, 20s, 40s, 80s, 160s, 300s...)
9. GOTO step 1 (repeat for SAME payment)
```

**Impact:**
- Each retry sends a NEW Telegram invite (step 4)
- Same payment processed to GCAccumulator multiple times (step 3)
- 11-12 retries per payment over 13+ minutes

---

## Technical Analysis

### Type Flow Through Code

```python
# Line 236: Extract from JSON (could be string or number)
subscription_price = payment_data.get('subscription_price')

# Lines 251-253: Early integer conversions (Session 40 fix)
user_id = int(user_id)
closed_channel_id = int(closed_channel_id)
subscription_time_days = int(subscription_time_days)
# NOTE: subscription_price NOT converted here

# Lines 387-394: Convert subscription_price to string (Session 40 fix)
subscription_price = str(subscription_price)

# Lines 396-404: Token encryption (requires string)
encrypted_token = token_manager.encrypt_token_for_gcwebhook2(
    # ... other params ...
    subscription_price=subscription_price  # ✅ String works here
)

# Line 437: Calculate difference (REQUIRES FLOAT)
"difference": outcome_amount_usd - subscription_price  # ❌ float - str = ERROR
```

### Why This Wasn't Caught Earlier

1. **No previous test payments** reached this code path after Session 40 fix
2. **Token encryption succeeded** (the primary bug we fixed)
3. **Payment routing succeeded** (logs showed successful enqueue)
4. **Error happens AFTER all critical operations** (payment already processed)
5. **User sees invites** (GCWebhook2 received tasks before crash)

---

## Impact Assessment

### Services Affected

| Service | Impact | Severity |
|---------|--------|----------|
| **GCWebhook1** | Crashes after processing each payment | 🔴 CRITICAL |
| **GCWebhook2** | Receives duplicate invite requests | 🟡 MEDIUM |
| **GCAccumulator** | Receives duplicate payment records | 🟡 MEDIUM |
| **GCSplit1** | Not affected (threshold payments only) | ✅ NONE |
| **Cloud Tasks** | Retries stuck tasks continuously | 🟡 MEDIUM |
| **Users** | Receive 11+ duplicate invite links | 🔴 CRITICAL |

### Data Integrity

**Potential Issues:**
1. **Duplicate payments in payout_accumulation table** (same payment_id processed multiple times)
2. **Accumulated amount may be inflated** (same $1.05 added 11 times = $11.55)
3. **Telegram invites sent multiple times** (user confusion)

**Mitigation:**
- Database should have `UNIQUE` constraint on `payment_id` (prevents duplicates)
- If no constraint, manual cleanup may be required

---

## Solution

### Fix Strategy

**Option 1: Keep subscription_price as float, convert only for token encryption (RECOMMENDED)**

```python
# Lines 387-394 (REPLACE)
# Keep subscription_price as float for calculations
# Convert to string only when needed for token encryption
try:
    subscription_price_float = float(subscription_price)
    subscription_price_str = str(subscription_price)
except (ValueError, TypeError) as e:
    print(f"❌ [VALIDATED] Invalid type for subscription_price: {e}")
    abort(400, "Invalid subscription_price type")

# Line 403: Use string for token encryption
encrypted_token = token_manager.encrypt_token_for_gcwebhook2(
    # ... other params ...
    subscription_price=subscription_price_str
)

# Line 437: Use float for calculation
"difference": outcome_amount_usd - subscription_price_float
```

**Option 2: Convert subscription_price to float at line 437 (SIMPLER)**

```python
# Line 437 (CHANGE)
"difference": outcome_amount_usd - float(subscription_price)
```

**Recommendation:** Option 2 is simpler and sufficient for this fix.

---

## Fix Checklist

### Phase 1: Code Fix ✅

- [ ] **Task 1.1:** Fix line 437 type error
  - **File:** `GCWebhook1-10-26/tph1-10-26.py`
  - **Line:** 437
  - **Change:** `outcome_amount_usd - subscription_price` → `outcome_amount_usd - float(subscription_price)`

### Phase 2: Deployment ✅

- [ ] **Task 2.1:** Rebuild GCWebhook1 Docker image
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook1-10-26
  ```

- [ ] **Task 2.2:** Deploy updated service
  ```bash
  gcloud run deploy gcwebhook1-10-26 \
    --image gcr.io/telepay-459221/gcwebhook1-10-26 \
    --region us-central1 \
    --allow-unauthenticated \
    --set-secrets=SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,GCSPLIT1_QUEUE=GCSPLIT1_QUEUE:latest,GCSPLIT1_URL=GCSPLIT1_URL:latest,GCACCUMULATOR_QUEUE=GCACCUMULATOR_QUEUE:latest,GCACCUMULATOR_URL=GCACCUMULATOR_URL:latest,GCWEBHOOK2_QUEUE=GCWEBHOOK2_QUEUE:latest,GCWEBHOOK2_URL=GCWEBHOOK2_URL:latest
  ```

### Phase 3: Queue Cleanup ✅

- [ ] **Task 3.1:** Purge stuck tasks from gcwebhook1-queue
  ```bash
  gcloud tasks queues purge gcwebhook1-queue --location=us-central1
  ```
  **Reason:** The 4 payments stuck in retry loop will continue failing until purged.

- [ ] **Task 3.2:** Verify queue is empty
  ```bash
  gcloud tasks list --queue=gcwebhook1-queue --location=us-central1 --limit=10
  ```

### Phase 4: Database Verification ✅

- [ ] **Task 4.1:** Check for duplicate payment records
  ```sql
  SELECT payment_id, COUNT(*) as count
  FROM payout_accumulation
  WHERE payment_id IN ('4364424903')  -- The payment IDs from logs
  GROUP BY payment_id
  HAVING COUNT(*) > 1;
  ```

- [ ] **Task 4.2:** If duplicates found, remove extras (keep earliest)
  ```sql
  -- ONLY run if duplicates found in Task 4.1
  DELETE FROM payout_accumulation
  WHERE id NOT IN (
      SELECT MIN(id)
      FROM payout_accumulation
      GROUP BY payment_id
  );
  ```

### Phase 5: Testing ✅

- [ ] **Task 5.1:** Create new test payment
  - Start TelePay bot
  - Generate test payment via Telegram
  - Complete payment using NowPayments

- [ ] **Task 5.2:** Monitor GCWebhook1 logs for success
  ```bash
  gcloud run services logs read gcwebhook1-10-26 --region=us-central1 --limit=50
  ```

  **Expected:**
  ```
  ✅ [VALIDATED] Enqueued Telegram invite to GCWebhook2
  🎉 [VALIDATED] Payment processing completed successfully
  ```

  **Should NOT see:**
  ```
  ❌ [VALIDATED] Unexpected error: unsupported operand type(s) for -: 'float' and 'str'
  ```

- [ ] **Task 5.3:** Verify HTTP 200 response (not 500)
  ```bash
  gcloud run services logs read gcwebhook1-10-26 --region=us-central1 --limit=10 | grep "POST /process-validated-payment"
  ```

  **Expected:** `status: 200`
  **Should NOT see:** `status: 500`

- [ ] **Task 5.4:** Verify single Telegram invite received
  - User should receive ONLY ONE invite link
  - No repeated invites

- [ ] **Task 5.5:** Verify task completes successfully (no retries)
  ```bash
  gcloud tasks list --queue=gcwebhook1-queue --location=us-central1 --limit=10
  ```
  **Expected:** Empty queue (task completed successfully)

### Phase 6: Documentation ✅

- [ ] **Task 6.1:** Update PROGRESS.md
  - Add Session 40 Part 3 entry
  - Document repeated invite bug and fix

- [ ] **Task 6.2:** Update BUGS.md
  - Document the bug
  - Add prevention measures

---

## Prevention Measures

### Coding Standards

1. **Type consistency:** If a variable is used in multiple contexts (string for API, float for math), use distinct variable names:
   ```python
   subscription_price_float = float(subscription_price)
   subscription_price_str = str(subscription_price)
   ```

2. **Test all code paths:** After type conversion changes, test the ENTIRE function flow, not just the fixed section.

3. **Add type hints:** Use Python type hints to catch type errors early:
   ```python
   def process_payment(subscription_price: float) -> dict:
       subscription_price_str: str = str(subscription_price)
       # ...
   ```

4. **Unit tests:** Add tests for the return value:
   ```python
   def test_process_payment_return_value():
       result = process_payment(...)
       assert "difference" in result
       assert isinstance(result["difference"], float)
   ```

### Testing Protocol

**After ANY type conversion changes:**
1. ✅ Test the specific functionality being fixed
2. ✅ Test the ENTIRE endpoint from start to finish
3. ✅ Verify HTTP response code is 200 (not 500)
4. ✅ Check logs for uncaught exceptions
5. ✅ Monitor for retry loops in Cloud Tasks

---

## Risk Assessment

### Risks Mitigated ✅
1. **Repeated Telegram invites** - Fixed with line 437 type conversion
2. **500 errors causing retries** - Fixed (will return 200 OK)
3. **Stuck tasks in queue** - Purged after fix

### Remaining Risks ⚠️
1. **Duplicate payment records in database** (Severity: Medium, Likelihood: High if no UNIQUE constraint)
   - Mitigation: Verify and clean up duplicates in Phase 4
2. **User confusion from past duplicate invites** (Severity: Low, Likelihood: Certain)
   - Mitigation: Users can ignore extra links (all work)

---

## Success Criteria

- [x] Root cause identified (line 437 type error)
- [ ] Code fix implemented
- [ ] GCWebhook1 rebuilt and deployed
- [ ] Stuck tasks purged from queue
- [ ] New test payment completes successfully
- [ ] HTTP 200 response received
- [ ] Single Telegram invite sent (no repeats)
- [ ] No task retries observed
- [ ] Documentation updated

---

**Next Action:** Implement fix at line 437 in tph1-10-26.py

**Status:** ⏳ READY TO FIX
