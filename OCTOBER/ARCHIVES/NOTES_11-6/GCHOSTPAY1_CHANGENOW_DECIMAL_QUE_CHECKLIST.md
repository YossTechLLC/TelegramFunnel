# GCHostPay1 ChangeNow Decimal Conversion Fix - Implementation Checklist

**Issue**: `decimal.ConversionSyntax` error when ChangeNow API returns null/empty amounts
**Root Cause**: ChangeNow swap not finished when GCHostPay1 queries for actual USDT received
**Impact**: Batch conversion callbacks fail, users don't receive payouts
**Priority**: P1 - HIGH

---

## Phase 1: Immediate Fix - Defensive Decimal Conversion

### ✅ Task 1: Update changenow_client.py with Safe Decimal Helper

**File**: `/10-26/GCHostPay1-10-26/changenow_client.py`

**Action**: Add `safe_decimal()` helper function and update `get_transaction_status()` method

**Changes**:

#### 1.1: Add Safe Decimal Helper Function
**Location**: After line 10, before class definition
```python
def _safe_decimal(value, default='0') -> Decimal:
    """
    Safely convert value to Decimal, return default if invalid.

    Handles:
    - None values
    - Empty strings
    - 'null'/'none' strings
    - Invalid numeric strings

    Args:
        value: Value to convert (can be None, str, int, float)
        default: Default Decimal string if conversion fails

    Returns:
        Decimal instance
    """
    # Handle None
    if value is None:
        return Decimal(default)

    # Convert to string and strip whitespace
    str_value = str(value).strip()

    # Handle empty or null strings
    if not str_value or str_value.lower() in ('null', 'none', ''):
        return Decimal(default)

    # Attempt conversion
    try:
        return Decimal(str_value)
    except (ValueError, decimal.InvalidOperation):
        print(f"⚠️ [SAFE_DECIMAL] Could not convert '{value}' to Decimal, using default: {default}")
        return Decimal(default)
```

**Import Required**: Add `import decimal` at top of file (line 7)

#### 1.2: Update get_transaction_status() Method
**Location**: Replace lines 69-79 in `get_transaction_status()` method

**BEFORE** (lines 69-79):
```python
data = response.json()

status = data.get('status', 'unknown')
amount_from = Decimal(str(data.get('amountFrom', 0)))  # ❌ CRASHES HERE
amount_to = Decimal(str(data.get('amountTo', 0)))      # ❌ OR HERE
payin_hash = data.get('payinHash', '')
payout_hash = data.get('payoutHash', '')

print(f"✅ [CHANGENOW_STATUS] Transaction status: {status}")
print(f"💰 [CHANGENOW_STATUS] Amount from: {amount_from}")
print(f"💰 [CHANGENOW_STATUS] Amount to: {amount_to} (ACTUAL USDT RECEIVED)")
```

**AFTER**:
```python
data = response.json()

status = data.get('status', 'unknown')

# ✅ DEFENSIVE CONVERSION: Handle null/empty/invalid values
amount_from = _safe_decimal(data.get('amountFrom'), '0')
amount_to = _safe_decimal(data.get('amountTo'), '0')

payin_hash = data.get('payinHash', '')
payout_hash = data.get('payoutHash', '')

print(f"✅ [CHANGENOW_STATUS] Transaction status: {status}")
print(f"💰 [CHANGENOW_STATUS] Amount from: {amount_from}")
print(f"💰 [CHANGENOW_STATUS] Amount to: {amount_to} (ACTUAL USDT RECEIVED)")

# ⚠️ WARN if amounts are zero (not available yet)
if amount_to == Decimal('0'):
    print(f"⚠️ [CHANGENOW_STATUS] amountTo is zero/null - swap may not be finished yet (status={status})")
if amount_from == Decimal('0') and status not in ['new', 'waiting']:
    print(f"⚠️ [CHANGENOW_STATUS] amountFrom is zero/null - unexpected for status={status}")
```

**Checklist**:
- [ ] Add `import decimal` to imports (line 7)
- [ ] Add `_safe_decimal()` helper function after imports
- [ ] Replace `Decimal(str(data.get('amountFrom', 0)))` with `_safe_decimal(data.get('amountFrom'), '0')`
- [ ] Replace `Decimal(str(data.get('amountTo', 0)))` with `_safe_decimal(data.get('amountTo'), '0')`
- [ ] Add warning log when `amount_to == Decimal('0')`
- [ ] Add warning log when `amount_from == Decimal('0')` (unexpected states)
- [ ] Verify changes using `Read` tool

---

### ✅ Task 2: Update tphp1-10-26.py to Handle Zero amountTo

**File**: `/10-26/GCHostPay1-10-26/tphp1-10-26.py`

**Action**: Update ENDPOINT_3 `/payment-completed` to detect when ChangeNow swap isn't finished

**Changes**:

#### 2.1: Improve ChangeNow Query Logic
**Location**: Replace lines 596-608 in `payment_completed()` endpoint

**BEFORE** (lines 596-608):
```python
if not changenow_client:
    print(f"❌ [ENDPOINT_3] ChangeNow client not available, cannot query transaction status")
else:
    try:
        print(f"🔍 [ENDPOINT_3] Querying ChangeNow for actual USDT received...")
        cn_status = changenow_client.get_transaction_status(cn_api_id)

        if cn_status and cn_status.get('status') == 'finished':
            actual_usdt_received = float(cn_status.get('amountTo', 0))
            print(f"✅ [ENDPOINT_3] Actual USDT received: ${actual_usdt_received}")
        else:
            print(f"⚠️ [ENDPOINT_3] ChangeNow transaction not finished yet: {cn_status.get('status') if cn_status else 'unknown'}")

    except Exception as e:
        print(f"❌ [ENDPOINT_3] ChangeNow query error: {e}")
```

**AFTER**:
```python
if not changenow_client:
    print(f"❌ [ENDPOINT_3] ChangeNow client not available, cannot query transaction status")
else:
    try:
        print(f"🔍 [ENDPOINT_3] Querying ChangeNow for actual USDT received...")
        cn_status = changenow_client.get_transaction_status(cn_api_id)

        if cn_status:
            status = cn_status.get('status')
            amount_to_decimal = cn_status.get('amountTo')  # This is a Decimal now

            print(f"📊 [ENDPOINT_3] ChangeNow status: {status}")

            # Check if swap is finished AND has actual amounts
            if status == 'finished' and amount_to_decimal and float(amount_to_decimal) > 0:
                actual_usdt_received = float(amount_to_decimal)
                print(f"✅ [ENDPOINT_3] Actual USDT received: ${actual_usdt_received}")

            elif status in ['waiting', 'confirming', 'exchanging', 'sending']:
                # Swap still in progress
                print(f"⏳ [ENDPOINT_3] ChangeNow swap not finished yet: {status}")
                print(f"⚠️ [ENDPOINT_3] amountTo not available yet (will be 0 in database)")
                print(f"💡 [ENDPOINT_3] Consider implementing retry logic (Phase 2) to query again later")

            elif status == 'finished' and float(amount_to_decimal) == 0:
                # Finished but zero amount - unexpected
                print(f"⚠️ [ENDPOINT_3] ChangeNow status=finished but amountTo=0 (UNEXPECTED)")
                print(f"⚠️ [ENDPOINT_3] This may indicate a ChangeNow API issue")

            else:
                # Failed, refunded, or unknown status
                print(f"❌ [ENDPOINT_3] ChangeNow transaction in unexpected state: {status}")

        else:
            print(f"❌ [ENDPOINT_3] ChangeNow query returned no data")

    except Exception as e:
        print(f"❌ [ENDPOINT_3] ChangeNow query error: {e}")
        import traceback
        print(f"❌ [ENDPOINT_3] Traceback: {traceback.format_exc()}")
```

**Checklist**:
- [ ] Update ENDPOINT_3 ChangeNow query logic (lines 596-608)
- [ ] Add status detection for in-progress swaps
- [ ] Add warning for finished swaps with zero amounts
- [ ] Add better error logging with traceback
- [ ] Verify changes using `Read` tool

---

### ✅ Task 3: Build and Deploy GCHostPay1-10-26

#### 3.1: Build Docker Image
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay1-10-26

gcloud builds submit \
  --tag gcr.io/telepay-459221/gchostpay1-10-26:latest \
  --timeout=600s
```

**Checklist**:
- [ ] Navigate to GCHostPay1-10-26 directory
- [ ] Run `gcloud builds submit` command
- [ ] Verify build success (check logs for "SUCCESS")
- [ ] Note build ID and image digest

#### 3.2: Deploy to Cloud Run
```bash
gcloud run deploy gchostpay1-10-26 \
  --image gcr.io/telepay-459221/gchostpay1-10-26:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

**Checklist**:
- [ ] Run `gcloud run deploy` command
- [ ] Verify deployment success
- [ ] Note new revision number (e.g., gchostpay1-10-26-00XXX-abc)
- [ ] Verify revision is serving 100% traffic
- [ ] Check service URL is responding

---

### ✅ Task 4: Test Phase 1 Fix

#### 4.1: Monitor Logs for Defensive Behavior

**Watch for these log patterns**:

✅ **Success Pattern** (swap finished):
```
🔍 [CHANGENOW_STATUS] Querying transaction status for: [id]
✅ [CHANGENOW_STATUS] Transaction status: finished
💰 [CHANGENOW_STATUS] Amount from: [amount]
💰 [CHANGENOW_STATUS] Amount to: [amount] (ACTUAL USDT RECEIVED)
✅ [ENDPOINT_3] Actual USDT received: $[amount]
```

⚠️ **Expected Pattern** (swap not finished):
```
🔍 [CHANGENOW_STATUS] Querying transaction status for: [id]
✅ [CHANGENOW_STATUS] Transaction status: waiting
💰 [CHANGENOW_STATUS] Amount from: 0
💰 [CHANGENOW_STATUS] Amount to: 0 (ACTUAL USDT RECEIVED)
⚠️ [CHANGENOW_STATUS] amountTo is zero/null - swap may not be finished yet (status=waiting)
📊 [ENDPOINT_3] ChangeNow status: waiting
⏳ [ENDPOINT_3] ChangeNow swap not finished yet: waiting
```

❌ **NO MORE** (crash eliminated):
```
❌ [CHANGENOW_STATUS] Unexpected error: [<class 'decimal.ConversionSyntax'>]
```

**Checklist**:
- [ ] Trigger new batch conversion (initiate payment flow)
- [ ] Monitor GCHostPay1 logs at https://gchostpay1-10-26-291176869049.us-central1.run.app
- [ ] Verify NO `ConversionSyntax` errors
- [ ] Verify defensive logs appear when swap not finished
- [ ] Verify successful callback sent when swap IS finished

---

### ✅ Task 5: Update Documentation

#### 5.1: Update PROGRESS.md
Add entry at TOP of file:
```markdown
## 2025-11-03 Session 52: GCHostPay1 ChangeNow Decimal Conversion Fix (Phase 1) 🛡️

**DEFENSIVE FIX**: Added safe Decimal conversion to prevent crashes when ChangeNow amounts unavailable

**Root Cause:**
- GCHostPay1 queries ChangeNow API immediately after ETH payment confirmation
- ChangeNow swap takes 5-10 minutes to complete
- API returns `null` or empty values for `amountFrom`/`amountTo` during swap
- Code attempted: `Decimal(str(None))` → `Decimal("None")` → ConversionSyntax error

**Fix Implemented:**
- ✅ Added `_safe_decimal()` helper function to changenow_client.py
- ✅ Replaced unsafe Decimal conversions with defensive version
- ✅ Added warning logs when amounts are zero/null
- ✅ Updated ENDPOINT_3 to detect in-progress swaps
- ✅ Deployed revision: gchostpay1-10-26-[NEW_REVISION]

**Impact:**
- ✅ No more crashes on missing amounts
- ✅ Code continues execution gracefully
- ⚠️ Callback still not sent if swap not finished (Phase 2 will add retry logic)

**Files Modified:**
- `/10-26/GCHostPay1-10-26/changenow_client.py` - Added safe_decimal helper
- `/10-26/GCHostPay1-10-26/tphp1-10-26.py` - Enhanced ChangeNow query logic

**Testing:**
- ✅ No ConversionSyntax errors in logs
- ✅ Defensive warnings appear for in-progress swaps
- ⏳ Phase 2 needed: Add retry logic to query again when swap completes
```

**Checklist**:
- [ ] Add Session 52 entry to TOP of PROGRESS.md
- [ ] Include root cause summary
- [ ] List all changes made
- [ ] Note new revision number
- [ ] Mark as Phase 1 complete, Phase 2 pending

#### 5.2: Update DECISIONS.md
Add entry at TOP of file:
```markdown
### 2025-11-03 Session 52: Defensive Decimal Conversion Over Fail-Fast ✅

**Decision:** Implement defensive Decimal conversion to return `0` for invalid values instead of crashing

**Context:**
- ChangeNow API returns `null`/empty values when swap not finished
- Original code: `Decimal(str(None))` → ConversionSyntax error
- Need to handle this gracefully without breaking payment workflow

**Options Considered:**

**Option A: Fail-Fast (REJECTED)**
- Let exception crash and propagate up
- ❌ Breaks entire payment workflow
- ❌ No callback sent to MicroBatchProcessor
- ❌ Poor user experience

**Option B: Defensive Conversion (CHOSEN)**
- Return `Decimal('0')` for invalid values
- ✅ Prevents crashes
- ✅ Allows code to continue
- ✅ Clear warning logs when amounts missing
- ⚠️ Requires Phase 2 retry logic to get actual amounts

**Rationale:**
- Better to log a warning and continue than to crash the entire flow
- Phase 2 will add retry logic to query ChangeNow again after swap completes
- Defensive programming principle: handle external API variability gracefully

**Next Steps:**
- Phase 2: Add Cloud Tasks retry logic to check ChangeNow again after 5-10 minutes
- Phase 3: Consider ChangeNow webhook integration for event-driven approach
```

**Checklist**:
- [ ] Add Session 52 decision to TOP of DECISIONS.md
- [ ] Document why defensive approach was chosen
- [ ] Note that Phase 2 retry logic is still needed

#### 5.3: Update BUGS.md
Add entry at TOP of file:
```markdown
### 2025-11-03 Session 52: GCHostPay1 decimal.ConversionSyntax on Null ChangeNow Amounts ✅

**Bug**: `decimal.ConversionSyntax` exception when ChangeNow API returns null/empty amounts

**Symptom:**
```
❌ [CHANGENOW_STATUS] Unexpected error: [<class 'decimal.ConversionSyntax'>]
❌ [ENDPOINT_3] ChangeNow query error: [<class 'decimal.ConversionSyntax'>]
⚠️ [ENDPOINT_3] No callback sent (context=batch, actual_usdt_received=None)
```

**Root Cause:**
1. GCHostPay3 completes ETH payment and sends callback to GCHostPay1
2. GCHostPay1 queries ChangeNow API immediately (TOO EARLY)
3. ChangeNow swap still in progress (takes 5-10 minutes)
4. ChangeNow returns `amountTo=null` (not available yet)
5. Code attempts: `Decimal(str(None))` → `Decimal("None")` → ❌ ConversionSyntax

**Impact:**
- ❌ Batch conversion callbacks fail
- ❌ GCMicroBatchProcessor never notified
- ❌ Users don't receive payouts
- ⚠️ ETH payments succeed but feedback loop breaks

**Fix:**
- ✅ Added `_safe_decimal()` helper to handle None/null/empty values
- ✅ Returns `Decimal('0')` for invalid values instead of crashing
- ✅ Added warning logs when amounts are zero/unavailable
- ✅ Updated ENDPOINT_3 to detect in-progress swaps

**Files Fixed:**
- `/10-26/GCHostPay1-10-26/changenow_client.py` (added safe_decimal)
- `/10-26/GCHostPay1-10-26/tphp1-10-26.py` (enhanced query logic)

**Deployed:** Revision gchostpay1-10-26-[NEW_REVISION]

**Status:** ✅ Phase 1 complete (crash prevention)
**Next:** ⏳ Phase 2 needed (retry logic to query when swap finishes)

**Lessons Learned:**
1. Never trust external API fields to exist
2. Always validate before type conversion
3. Handle asynchronous processes with appropriate timing
4. Defensive programming > fail-fast for critical workflows
5. Add clear warning logs when data is incomplete
```

**Checklist**:
- [ ] Add Session 52 bug entry to TOP of BUGS.md
- [ ] Document complete timeline of the bug
- [ ] List fix details and files changed
- [ ] Note that Phase 2 is still needed

---

## Phase 2: Retry Logic for Unfinished Swaps

> **NOTE**: Phase 2 implementation is OPTIONAL but HIGHLY RECOMMENDED
> - Phase 1 prevents crashes but callbacks still fail if swap not finished
> - Phase 2 adds automatic retry to query ChangeNow again after swap completes
> - Without Phase 2: Manual intervention needed to re-trigger callbacks

### ✅ Task 6: Add Retry Endpoint to tphp1-10-26.py

**File**: `/10-26/GCHostPay1-10-26/tphp1-10-26.py`

**Action**: Create new endpoint `/retry-callback-check` to re-query ChangeNow

#### 6.1: Add Helper Function for Enqueueing Retry
**Location**: After `_route_batch_callback()` function (after line 175)

```python
def _enqueue_delayed_callback_check(
    unique_id: str,
    cn_api_id: str,
    tx_hash: str,
    context: str,
    retry_count: int = 0,
    retry_after_seconds: int = 300
) -> bool:
    """
    Enqueue delayed callback check to retry ChangeNow query after swap completes.

    This handles the timing issue where ETH payment completes before ChangeNow
    swap finishes. We retry after 5 minutes to check if amountTo is available.

    Args:
        unique_id: Unique transaction ID (e.g., batch_xxx)
        cn_api_id: ChangeNow API transaction ID
        tx_hash: Ethereum transaction hash
        context: 'batch' or 'threshold'
        retry_count: Current retry attempt (max 3)
        retry_after_seconds: Delay before retry (default 300 = 5 minutes)

    Returns:
        True if retry enqueued successfully, False otherwise
    """
    try:
        # Check max retries
        if retry_count >= 3:
            print(f"❌ [RETRY_ENQUEUE] Max retries reached ({retry_count}/3) for {unique_id}")
            print(f"⚠️ [RETRY_ENQUEUE] Manual intervention required - ChangeNow swap not finishing")
            return False

        print(f"🔄 [RETRY_ENQUEUE] Scheduling retry #{retry_count + 1} in {retry_after_seconds}s")
        print(f"🆔 [RETRY_ENQUEUE] Unique ID: {unique_id}")
        print(f"🆔 [RETRY_ENQUEUE] CN API ID: {cn_api_id}")

        # Validate Cloud Tasks client
        if not cloudtasks_client:
            print(f"❌ [RETRY_ENQUEUE] Cloud Tasks client not available")
            return False

        # Get queue configuration
        gchostpay1_response_queue = config.get('gchostpay1_response_queue')
        gchostpay1_url = config.get('gchostpay1_url')

        if not gchostpay1_response_queue or not gchostpay1_url:
            print(f"❌ [RETRY_ENQUEUE] GCHostPay1 response queue config missing")
            return False

        # Encrypt retry token
        if not token_manager:
            print(f"❌ [RETRY_ENQUEUE] Token manager not available")
            return False

        retry_token = token_manager.encrypt_gchostpay1_retry_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            tx_hash=tx_hash,
            context=context,
            retry_count=retry_count + 1
        )

        if not retry_token:
            print(f"❌ [RETRY_ENQUEUE] Failed to encrypt retry token")
            return False

        # Prepare retry payload
        payload = {
            'token': retry_token
        }

        # Enqueue retry task with delay
        retry_url = f"{gchostpay1_url}/retry-callback-check"
        print(f"📡 [RETRY_ENQUEUE] Enqueueing retry to: {retry_url}")

        task_success = cloudtasks_client.enqueue_task(
            queue_name=gchostpay1_response_queue,
            url=retry_url,
            payload=payload,
            schedule_time=retry_after_seconds  # Delay execution
        )

        if task_success:
            print(f"✅ [RETRY_ENQUEUE] Retry task enqueued (will execute in {retry_after_seconds}s)")
            return True
        else:
            print(f"❌ [RETRY_ENQUEUE] Failed to enqueue retry task")
            return False

    except Exception as e:
        print(f"❌ [RETRY_ENQUEUE] Unexpected error: {e}")
        import traceback
        print(f"❌ [RETRY_ENQUEUE] Traceback: {traceback.format_exc()}")
        return False
```

**Checklist**:
- [ ] Add `_enqueue_delayed_callback_check()` helper function
- [ ] Validate token_manager and cloudtasks_client availability
- [ ] Implement max retry limit (3 retries)
- [ ] Add schedule_time parameter for delayed execution

#### 6.2: Add Retry Endpoint
**Location**: After `/payment-completed` endpoint (after line 650)

```python
# ============================================================================
# ENDPOINT 4: POST /retry-callback-check - Retry ChangeNow query (internal)
# ============================================================================

@app.route("/retry-callback-check", methods=["POST"])
def retry_callback_check():
    """
    Retry endpoint to re-query ChangeNow for actual USDT received.

    This endpoint is called by Cloud Tasks after a delay (5 minutes) to check
    if the ChangeNow swap has completed and amountTo is now available.

    Flow:
    1. Decrypt retry token
    2. Extract: unique_id, cn_api_id, tx_hash, context, retry_count
    3. Query ChangeNow API again
    4. If finished: Send callback to MicroBatchProcessor
    5. If still in progress: Enqueue another retry (max 3 total)

    Returns:
        JSON response with status
    """
    try:
        print(f"🔄 [ENDPOINT_4] Retry callback check received")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT_4] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        token = request_data.get('token')
        if not token:
            print(f"❌ [ENDPOINT_4] Missing token")
            abort(400, "Missing token")

        # Decrypt retry token
        if not token_manager:
            print(f"❌ [ENDPOINT_4] Token manager not available")
            abort(500, "Service configuration error")

        try:
            decrypted_data = token_manager.decrypt_gchostpay1_retry_token(token)
            if not decrypted_data:
                print(f"❌ [ENDPOINT_4] Failed to decrypt retry token")
                abort(401, "Invalid token")

            unique_id = decrypted_data['unique_id']
            cn_api_id = decrypted_data['cn_api_id']
            tx_hash = decrypted_data['tx_hash']
            context = decrypted_data['context']
            retry_count = decrypted_data['retry_count']

            print(f"✅ [ENDPOINT_4] Retry token decoded successfully")
            print(f"🆔 [ENDPOINT_4] Unique ID: {unique_id}")
            print(f"🆔 [ENDPOINT_4] CN API ID: {cn_api_id}")
            print(f"🔁 [ENDPOINT_4] Retry attempt: {retry_count}/3")

        except Exception as e:
            print(f"❌ [ENDPOINT_4] Token validation error: {e}")
            abort(400, f"Token error: {e}")

        # Query ChangeNow API again
        actual_usdt_received = None
        if not changenow_client:
            print(f"❌ [ENDPOINT_4] ChangeNow client not available")
            abort(500, "ChangeNow client unavailable")

        try:
            print(f"🔍 [ENDPOINT_4] Re-querying ChangeNow for actual USDT received...")
            cn_status = changenow_client.get_transaction_status(cn_api_id)

            if cn_status:
                status = cn_status.get('status')
                amount_to_decimal = cn_status.get('amountTo')

                print(f"📊 [ENDPOINT_4] ChangeNow status: {status}")

                if status == 'finished' and amount_to_decimal and float(amount_to_decimal) > 0:
                    # ✅ Swap finally complete!
                    actual_usdt_received = float(amount_to_decimal)
                    print(f"✅ [ENDPOINT_4] Actual USDT received: ${actual_usdt_received}")
                    print(f"🎉 [ENDPOINT_4] ChangeNow swap completed after retry!")

                elif status in ['waiting', 'confirming', 'exchanging', 'sending']:
                    # ⏳ Still in progress - retry again if under limit
                    print(f"⏳ [ENDPOINT_4] ChangeNow swap still in progress: {status}")

                    if retry_count < 3:
                        print(f"🔄 [ENDPOINT_4] Enqueueing another retry (attempt {retry_count + 1})")
                        _enqueue_delayed_callback_check(
                            unique_id=unique_id,
                            cn_api_id=cn_api_id,
                            tx_hash=tx_hash,
                            context=context,
                            retry_count=retry_count,
                            retry_after_seconds=300  # 5 minutes
                        )

                        return jsonify({
                            "status": "retry_scheduled",
                            "message": f"Swap still in progress, retry #{retry_count + 1} scheduled",
                            "unique_id": unique_id,
                            "cn_api_id": cn_api_id,
                            "changenow_status": status
                        }), 200
                    else:
                        print(f"❌ [ENDPOINT_4] Max retries exceeded - swap still not finished")
                        print(f"⚠️ [ENDPOINT_4] Manual intervention required")

                        return jsonify({
                            "status": "max_retries_exceeded",
                            "message": "ChangeNow swap not finished after 3 retries",
                            "unique_id": unique_id,
                            "cn_api_id": cn_api_id,
                            "changenow_status": status
                        }), 500

                else:
                    # ❌ Failed or unexpected status
                    print(f"❌ [ENDPOINT_4] ChangeNow transaction in unexpected state: {status}")

                    return jsonify({
                        "status": "failed",
                        "message": f"ChangeNow transaction failed: {status}",
                        "unique_id": unique_id,
                        "cn_api_id": cn_api_id,
                        "changenow_status": status
                    }), 500

        except Exception as e:
            print(f"❌ [ENDPOINT_4] ChangeNow query error: {e}")
            import traceback
            print(f"❌ [ENDPOINT_4] Traceback: {traceback.format_exc()}")
            abort(500, f"ChangeNow query failed: {e}")

        # If we have actual_usdt_received, send callback
        if actual_usdt_received is not None and actual_usdt_received > 0:
            if context == 'batch':
                # Extract batch_conversion_id from unique_id
                batch_conversion_id = unique_id.replace('batch_', '')
                print(f"🎯 [ENDPOINT_4] Routing batch callback to GCMicroBatchProcessor")

                callback_success = _route_batch_callback(
                    batch_conversion_id=batch_conversion_id,
                    cn_api_id=cn_api_id,
                    tx_hash=tx_hash,
                    actual_usdt_received=actual_usdt_received
                )

                if callback_success:
                    print(f"✅ [ENDPOINT_4] Batch callback sent successfully")
                    return jsonify({
                        "status": "success",
                        "message": "Callback sent to MicroBatchProcessor",
                        "unique_id": unique_id,
                        "actual_usdt_received": actual_usdt_received
                    }), 200
                else:
                    print(f"❌ [ENDPOINT_4] Failed to send batch callback")
                    return jsonify({
                        "status": "callback_failed",
                        "message": "Could not send callback to MicroBatchProcessor"
                    }), 500

            elif context == 'threshold':
                print(f"🎯 [ENDPOINT_4] Routing threshold callback to GCAccumulator")
                # TODO: Implement threshold callback
                print(f"⚠️ [ENDPOINT_4] Threshold callback not yet implemented")
                return jsonify({
                    "status": "not_implemented",
                    "message": "Threshold callback not yet implemented"
                }), 501
        else:
            print(f"⚠️ [ENDPOINT_4] No callback sent - actual_usdt_received unavailable")
            return jsonify({
                "status": "no_callback",
                "message": "Actual USDT received not available"
            }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT_4] Unexpected error: {e}")
        import traceback
        print(f"❌ [ENDPOINT_4] Traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500
```

**Checklist**:
- [ ] Add `/retry-callback-check` endpoint after `/payment-completed`
- [ ] Decrypt retry token with unique_id, cn_api_id, tx_hash, context, retry_count
- [ ] Re-query ChangeNow API
- [ ] If finished: Send callback to MicroBatchProcessor
- [ ] If still in progress: Enqueue another retry (max 3)
- [ ] Add comprehensive error handling and logging

#### 6.3: Update ENDPOINT_3 to Enqueue Retry
**Location**: In `payment_completed()` endpoint, after line 607

**Add this after detecting in-progress swap:**
```python
elif status in ['waiting', 'confirming', 'exchanging', 'sending']:
    # Swap still in progress
    print(f"⏳ [ENDPOINT_3] ChangeNow swap not finished yet: {status}")
    print(f"⚠️ [ENDPOINT_3] amountTo not available yet")

    # ✅ ENQUEUE RETRY: Check again after 5 minutes
    print(f"🔄 [ENDPOINT_3] Enqueueing delayed retry to check when swap completes")
    _enqueue_delayed_callback_check(
        unique_id=unique_id,
        cn_api_id=cn_api_id,
        tx_hash=tx_hash,
        context=context,
        retry_count=0,  # First retry
        retry_after_seconds=300  # 5 minutes
    )
```

**Checklist**:
- [ ] Update ENDPOINT_3 to detect in-progress swaps
- [ ] Call `_enqueue_delayed_callback_check()` when swap not finished
- [ ] Set initial retry_count=0
- [ ] Set retry delay to 300 seconds (5 minutes)

---

### ✅ Task 7: Add Retry Token Methods to token_manager.py

**File**: `/10-26/GCHostPay1-10-26/token_manager.py`

**Action**: Add encryption/decryption methods for retry tokens

#### 7.1: Add Encryption Method
**Location**: Add to TokenManager class

```python
def encrypt_gchostpay1_retry_token(
    self,
    unique_id: str,
    cn_api_id: str,
    tx_hash: str,
    context: str,
    retry_count: int
) -> Optional[str]:
    """
    Encrypt retry token for delayed ChangeNow query.

    Token Structure:
    - 16 bytes: unique_id (UUID format)
    - String: cn_api_id
    - String: tx_hash
    - String: context ('batch' or 'threshold')
    - 4 bytes: retry_count
    - 4 bytes: timestamp
    - 16 bytes: HMAC signature

    Args:
        unique_id: Unique transaction ID (e.g., batch_xxx)
        cn_api_id: ChangeNow API transaction ID
        tx_hash: Ethereum transaction hash
        context: 'batch' or 'threshold'
        retry_count: Current retry attempt number

    Returns:
        Base64-encoded encrypted token, or None if encryption fails
    """
    try:
        print(f"🔐 [TOKEN_ENC] GCHostPay1 Retry: Encrypting retry token")

        packed_data = bytearray()

        # Pack unique_id (16 bytes)
        unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
        packed_data.extend(unique_id_bytes)

        # Pack strings
        packed_data.extend(self._pack_string(cn_api_id))
        packed_data.extend(self._pack_string(tx_hash))
        packed_data.extend(self._pack_string(context))

        # Pack retry_count (4 bytes)
        packed_data.extend(struct.pack(">I", retry_count))

        # Pack timestamp (4 bytes)
        current_timestamp = int(time.time())
        packed_data.extend(struct.pack(">I", current_timestamp))

        # Generate HMAC signature
        signature = hmac.new(
            self.internal_signing_key,
            packed_data,
            hashlib.sha256
        ).digest()[:16]

        packed_data.extend(signature)

        # Encrypt
        encrypted = self.internal_cipher.encrypt(bytes(packed_data))
        token = base64.urlsafe_b64encode(encrypted).decode('utf-8')

        print(f"✅ [TOKEN_ENC] Retry token encrypted successfully")
        return token

    except Exception as e:
        print(f"❌ [TOKEN_ENC] Retry token encryption failed: {e}")
        return None
```

#### 7.2: Add Decryption Method
**Location**: Add to TokenManager class

```python
def decrypt_gchostpay1_retry_token(self, token: str) -> Optional[Dict[str, Any]]:
    """Decrypt retry token from delayed ChangeNow query."""
    try:
        print(f"🔓 [TOKEN_DEC] GCHostPay1 Retry: Decrypting retry token")

        # Decode and decrypt
        encrypted = base64.urlsafe_b64decode(token.encode('utf-8'))
        decrypted = self.internal_cipher.decrypt(encrypted)

        payload = decrypted
        offset = 0

        # Extract unique_id (16 bytes)
        unique_id = payload[offset:offset + 16].rstrip(b'\x00').decode('utf-8')
        offset += 16

        # Extract strings
        cn_api_id, offset = self._unpack_string(payload, offset)
        tx_hash, offset = self._unpack_string(payload, offset)
        context, offset = self._unpack_string(payload, offset)

        # Extract retry_count (4 bytes)
        retry_count = struct.unpack(">I", payload[offset:offset + 4])[0]
        offset += 4

        # Extract timestamp (4 bytes)
        timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]
        offset += 4

        # Verify signature
        signature = payload[offset:offset + 16]
        expected_signature = hmac.new(
            self.internal_signing_key,
            payload[:offset],
            hashlib.sha256
        ).digest()[:16]

        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Invalid signature")

        # Validate timestamp (retry tokens valid for 24 hours)
        now = int(time.time())
        if not (now - 86400 <= timestamp <= now + 300):
            raise ValueError("Token expired")

        print(f"✅ [TOKEN_DEC] Retry token decrypted successfully")

        return {
            'unique_id': unique_id,
            'cn_api_id': cn_api_id,
            'tx_hash': tx_hash,
            'context': context,
            'retry_count': retry_count
        }

    except Exception as e:
        print(f"❌ [TOKEN_DEC] Retry token decryption failed: {e}")
        return None
```

**Checklist**:
- [ ] Add `encrypt_gchostpay1_retry_token()` method to TokenManager
- [ ] Add `decrypt_gchostpay1_retry_token()` method to TokenManager
- [ ] Use internal_signing_key for HMAC (not tps_hostpay_key)
- [ ] Set token expiry to 24 hours (86400 seconds backward)
- [ ] Verify changes using `Read` tool

---

### ✅ Task 8: Update CloudTasks Client for Delayed Execution

**File**: `/10-26/GCHostPay1-10-26/cloudtasks_client.py`

**Action**: Add `schedule_time` parameter to `enqueue_task()` method

#### 8.1: Update enqueue_task() Method
**Location**: Modify existing `enqueue_task()` method

**Add `schedule_time` parameter:**
```python
def enqueue_task(
    self,
    queue_name: str,
    url: str,
    payload: dict,
    schedule_time: int = None  # ✅ ADD THIS PARAMETER (seconds from now)
) -> bool:
    """
    Enqueue a task to Cloud Tasks.

    Args:
        queue_name: Name of the Cloud Tasks queue
        url: Target URL for the task
        payload: JSON payload to send
        schedule_time: Optional delay in seconds before task execution

    Returns:
        True if task enqueued successfully, False otherwise
    """
    try:
        # ... existing code ...

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload).encode(),
            },
        }

        # ✅ ADD SCHEDULE TIME IF PROVIDED
        if schedule_time:
            import datetime
            d = datetime.datetime.utcnow() + datetime.timedelta(seconds=schedule_time)
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(d)
            task["schedule_time"] = timestamp
            print(f"⏰ [CLOUDTASKS] Task scheduled for {schedule_time}s from now")

        # ... rest of existing code ...
```

**Required Import:**
```python
from google.protobuf import timestamp_pb2
import datetime
```

**Checklist**:
- [ ] Add `schedule_time` parameter to `enqueue_task()` method
- [ ] Import `timestamp_pb2` and `datetime`
- [ ] Calculate future timestamp when schedule_time provided
- [ ] Add schedule_time to task definition
- [ ] Verify changes using `Read` tool

---

### ✅ Task 9: Deploy Phase 2 Changes

#### 9.1: Build and Deploy
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay1-10-26

gcloud builds submit \
  --tag gcr.io/telepay-459221/gchostpay1-10-26:latest \
  --timeout=600s

gcloud run deploy gchostpay1-10-26 \
  --image gcr.io/telepay-459221/gchostpay1-10-26:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

**Checklist**:
- [ ] Build Docker image with Phase 2 changes
- [ ] Deploy to Cloud Run
- [ ] Verify new revision deployed
- [ ] Check /health endpoint responding

#### 9.2: Test Phase 2 Retry Logic
**Test Scenario**: Trigger batch conversion and monitor retry behavior

**Expected Flow:**
```
T+0s:  Payment initiated
T+30s: ETH payment confirmed, GCHostPay3 → GCHostPay1 callback
T+30s: GCHostPay1 queries ChangeNow (status=waiting, amountTo=null)
T+30s: Phase 1 prevents crash, returns Decimal('0')
T+30s: Phase 2 detects in-progress swap, enqueues retry #1 (5 min delay)
T+5m:  Retry #1 executes, queries ChangeNow (status=exchanging, amountTo=null)
T+5m:  Enqueues retry #2 (5 min delay)
T+10m: Retry #2 executes, queries ChangeNow (status=finished, amountTo=45.67)
T+10m: Callback sent to GCMicroBatchProcessor with actual_usdt_received=45.67
```

**Monitor Logs For:**
```
🔄 [ENDPOINT_3] Enqueueing delayed retry to check when swap completes
✅ [RETRY_ENQUEUE] Retry task enqueued (will execute in 300s)
🔄 [ENDPOINT_4] Retry callback check received
🔍 [ENDPOINT_4] Re-querying ChangeNow for actual USDT received...
✅ [ENDPOINT_4] Actual USDT received: $45.67
🎉 [ENDPOINT_4] ChangeNow swap completed after retry!
✅ [ENDPOINT_4] Batch callback sent successfully
```

**Checklist**:
- [ ] Initiate new batch conversion
- [ ] Verify initial query detects in-progress swap
- [ ] Verify retry task enqueued with 5-minute delay
- [ ] Wait 5 minutes, verify retry executes
- [ ] Verify retry eventually succeeds when swap finishes
- [ ] Verify callback sent to GCMicroBatchProcessor
- [ ] Check MicroBatchProcessor receives callback with actual_usdt_received

---

### ✅ Task 10: Update Documentation for Phase 2

#### 10.1: Update PROGRESS.md
Add Phase 2 entry:
```markdown
## 2025-11-03 Session 52: GCHostPay1 ChangeNow Retry Logic (Phase 2) 🔄

**RETRY LOGIC**: Added automatic retry to query ChangeNow after swap completes

**Problem:**
- Phase 1 prevented crashes but callbacks still failed if swap not finished
- ChangeNow swaps take 5-10 minutes to complete
- Need to re-query ChangeNow after delay to get actual USDT received

**Phase 2 Implementation:**
- ✅ Added `_enqueue_delayed_callback_check()` helper to enqueue retry tasks
- ✅ Created `/retry-callback-check` endpoint to handle retries
- ✅ Added retry token encryption/decryption methods to TokenManager
- ✅ Updated CloudTasks client to support delayed task execution
- ✅ Implemented max 3 retries (5 minutes apart)
- ✅ Deployed revision: gchostpay1-10-26-[PHASE2_REVISION]

**Retry Flow:**
1. ENDPOINT_3 detects ChangeNow swap not finished (status=waiting/exchanging)
2. Enqueues retry task to execute after 5 minutes
3. Retry endpoint `/retry-callback-check` executes after delay
4. Re-queries ChangeNow API for actual_usdt_received
5. If finished: Sends callback to GCMicroBatchProcessor
6. If still in progress: Enqueues another retry (max 3 total)

**Impact:**
- ✅ Automatic callback when ChangeNow swap completes
- ✅ No manual intervention needed
- ✅ Micro-batch conversions complete end-to-end
- ✅ Users receive payouts automatically

**Files Modified:**
- `/10-26/GCHostPay1-10-26/tphp1-10-26.py` - Added retry endpoint and enqueue logic
- `/10-26/GCHostPay1-10-26/token_manager.py` - Added retry token methods
- `/10-26/GCHostPay1-10-26/cloudtasks_client.py` - Added schedule_time support

**Testing:**
- ✅ Retry tasks enqueue with 5-minute delay
- ✅ Retry endpoint executes and re-queries ChangeNow
- ✅ Callback sent once swap finishes
- ✅ Max retry limit prevents infinite loops
```

**Checklist**:
- [ ] Add Phase 2 entry to PROGRESS.md
- [ ] Document retry flow and implementation
- [ ] List all files modified
- [ ] Note new revision number

#### 10.2: Update DECISIONS.md
Add Phase 2 decision:
```markdown
### 2025-11-03 Session 52: Cloud Tasks Retry vs Polling Loop ✅

**Decision:** Use Cloud Tasks delayed execution for retries instead of in-process polling

**Options Considered:**

**Option A: In-Process Sleep/Polling (REJECTED)**
- Use asyncio or threading to sleep and retry in same request
- ❌ Blocks Cloud Run instance for 5-10 minutes
- ❌ Wastes compute resources
- ❌ Request timeout issues (max 60 minutes)
- ❌ No retry persistence if service restarts

**Option B: Cloud Tasks Delayed Execution (CHOSEN)**
- Enqueue retry task with schedule_time delay
- ✅ No blocking - Cloud Run scales to zero
- ✅ Cost-efficient (only pay for retry execution)
- ✅ Persistent (survives service restarts)
- ✅ Automatic retry on transient failures
- ✅ Distributed tracing and monitoring

**Rationale:**
- Cloud Tasks is designed for delayed/scheduled execution
- Follows serverless best practices (don't block, use queues)
- More reliable and cost-effective than in-process polling

**Implementation:**
- Initial callback detects in-progress swap
- Enqueues Cloud Tasks job with 300s (5 min) delay
- Task executes `/retry-callback-check` endpoint after delay
- Maximum 3 retries to prevent infinite loops
```

**Checklist**:
- [ ] Add Cloud Tasks retry decision to DECISIONS.md
- [ ] Document why Cloud Tasks chosen over polling

---

## Phase 1 + Phase 2 Complete Summary

### What Was Fixed

**Phase 1 (Defensive Fix):**
- ✅ Added `_safe_decimal()` helper to handle null/empty ChangeNow amounts
- ✅ Prevents `decimal.ConversionSyntax` crashes
- ✅ Returns `Decimal('0')` for invalid values
- ✅ Added warning logs when amounts unavailable

**Phase 2 (Retry Logic):**
- ✅ Added automatic retry when ChangeNow swap not finished
- ✅ Re-queries ChangeNow after 5-minute delay
- ✅ Maximum 3 retries (5 min, 10 min, 15 min)
- ✅ Sends callback once swap completes
- ✅ Fully automated - no manual intervention needed

### Files Modified

1. `/10-26/GCHostPay1-10-26/changenow_client.py`
   - Added `_safe_decimal()` helper function
   - Updated Decimal conversions to use defensive version
   - Added warning logs for zero amounts

2. `/10-26/GCHostPay1-10-26/tphp1-10-26.py`
   - Enhanced ENDPOINT_3 ChangeNow query logic
   - Added `_enqueue_delayed_callback_check()` helper
   - Created ENDPOINT_4 `/retry-callback-check` endpoint
   - Integrated retry enqueue on in-progress swaps

3. `/10-26/GCHostPay1-10-26/token_manager.py`
   - Added `encrypt_gchostpay1_retry_token()` method
   - Added `decrypt_gchostpay1_retry_token()` method

4. `/10-26/GCHostPay1-10-26/cloudtasks_client.py`
   - Added `schedule_time` parameter to `enqueue_task()`
   - Supports delayed task execution

5. `/10-26/PROGRESS.md`
   - Session 52 Phase 1 entry
   - Session 52 Phase 2 entry

6. `/10-26/DECISIONS.md`
   - Defensive conversion decision
   - Cloud Tasks retry decision

7. `/10-26/BUGS.md`
   - Session 52 decimal.ConversionSyntax bug entry

### Testing Checklist

**Phase 1 Testing:**
- [ ] No `ConversionSyntax` errors in logs
- [ ] Defensive warnings appear for in-progress swaps
- [ ] Service continues execution without crashing

**Phase 2 Testing:**
- [ ] Retry tasks enqueue with 5-minute delay
- [ ] Retry endpoint executes after delay
- [ ] ChangeNow re-queried successfully
- [ ] Callback sent when swap finishes
- [ ] Max retry limit prevents infinite loops
- [ ] GCMicroBatchProcessor receives callback with actual_usdt_received

**End-to-End Testing:**
- [ ] Initiate batch conversion
- [ ] ETH payment completes successfully
- [ ] Initial ChangeNow query detects in-progress swap
- [ ] Retry automatically enqueued
- [ ] Retry executes after 5 minutes
- [ ] Actual USDT amount retrieved
- [ ] Callback sent to GCMicroBatchProcessor
- [ ] Micro-batch conversion completes
- [ ] Users receive payouts

---

**STATUS**: Ready for Implementation
**PRIORITY**: P1 - HIGH
**ESTIMATED TIME**:
- Phase 1: 1-2 hours
- Phase 2: 2-3 hours
- Total: 3-5 hours

**NEXT STEPS**:
1. Start with Phase 1 (defensive fix) - Deploy immediately
2. Test Phase 1 with real transaction
3. Implement Phase 2 (retry logic) - Deploy when ready
4. Test Phase 2 end-to-end
5. Monitor production for 24 hours
6. Consider Phase 3 (ChangeNow webhooks) as future enhancement
