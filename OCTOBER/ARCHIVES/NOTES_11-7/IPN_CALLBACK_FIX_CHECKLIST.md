# IPN CALLBACK FIX CHECKLIST

**Status:** READY FOR IMPLEMENTATION
**Date:** 2025-11-07
**Priority:** CRITICAL - BLOCKING PRODUCTION
**Combines:** NowPayments status validation + split_payout_que idempotency

---

## Executive Summary

This checklist combines two critical fixes:

1. **NowPayments Status Validation** (Defense-in-depth)
   - Add 'finished' status check in np-webhook (first layer)
   - Add 'finished' status check in GCWebhook1 (second layer)
   - Prevent premature payouts before funds are confirmed

2. **Split_Payout_Que Idempotency Protection**
   - Add duplicate check before inserting into split_payout_que
   - Prevent duplicate key errors during Cloud Tasks retries
   - Return idempotent 200 OK responses

---

## Phase 1: np-webhook Status Check (First Layer) ✅

### File: `/OCTOBER/10-26/np-webhook-10-26/app.py`

---

#### Change 1.1: Add Status Validation After Parsing IPN Data

**Location:** After line 631 (after `ipn_data = request.get_json()`)

**Insert this code:**

```python
# ============================================================================
# CRITICAL: Validate payment_status before processing
# ============================================================================
payment_status = ipn_data.get('payment_status', '').lower()

# Define allowed statuses (only process finished payments)
ALLOWED_PAYMENT_STATUSES = ['finished']

print(f"🔍 [IPN] Payment status received: '{payment_status}'")
print(f"✅ [IPN] Allowed statuses: {ALLOWED_PAYMENT_STATUSES}")

if payment_status not in ALLOWED_PAYMENT_STATUSES:
    print(f"=" * 80)
    print(f"⏸️ [IPN] PAYMENT STATUS NOT READY FOR PROCESSING")
    print(f"=" * 80)
    print(f"📊 [IPN] Current status: '{payment_status}'")
    print(f"⏳ [IPN] Waiting for status: 'finished'")
    print(f"💳 [IPN] Payment ID: {ipn_data.get('payment_id')}")
    print(f"💰 [IPN] Amount: {ipn_data.get('price_amount')} {ipn_data.get('price_currency')}")
    print(f"📝 [IPN] Action: Acknowledged but not processed")
    print(f"🔄 [IPN] NowPayments will send another IPN when status becomes 'finished'")
    print(f"=" * 80)

    # Return 200 OK to acknowledge receipt to NowPayments
    # But DO NOT trigger GCWebhook1 or any downstream processing
    return jsonify({
        "status": "acknowledged",
        "message": f"IPN received but not processed. Waiting for status 'finished' (current: {payment_status})",
        "payment_id": ipn_data.get('payment_id'),
        "current_status": payment_status,
        "required_status": "finished"
    }), 200

# If we reach here, payment_status is 'finished' - proceed with processing
print(f"=" * 80)
print(f"✅ [IPN] PAYMENT STATUS VALIDATED: '{payment_status}'")
print(f"✅ [IPN] Proceeding with payment processing")
print(f"=" * 80)
```

**Why this location:**
- After signature verification (lines 596-613) ✅
- After JSON parsing (lines 615-631) ✅
- BEFORE database update (line 665) ✅
- BEFORE triggering GCWebhook1 (lines 855-901) ✅

---

#### Change 1.2: Update Database Status Field (Conditional)

**Location:** Line 412 (within database update)

**BEFORE:**
```python
payment_status = 'confirmed',  # ❌ Hardcoded for all IPNs
```

**AFTER:**
```python
payment_status = 'confirmed',  # Only reached if status='finished' due to check above
nowpayments_payment_status = payment_status,  # Store actual NowPayments status
```

**Note:** This change is OPTIONAL since we're already filtering by status='finished' before reaching this line. The database will only be updated for finished payments.

---

#### Change 1.3: Add payment_status to GCWebhook1 Payload

**Location:** Lines 855-901 (Cloud Tasks enqueue call)

**Find this code (around line 870-901):**
```python
task_name = cloudtasks_client.enqueue_gcwebhook1_validated_payment(
    queue_name=gcwebhook1_queue,
    target_url=gcwebhook1_url,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    subscription_price=sub_price,
    nowpayments_payment_id=nowpayments_payment_id,
    nowpayments_pay_address=nowpayments_pay_address,
    nowpayments_outcome_amount=nowpayments_outcome_amount
)
```

**AFTER:**
```python
task_name = cloudtasks_client.enqueue_gcwebhook1_validated_payment(
    queue_name=gcwebhook1_queue,
    target_url=gcwebhook1_url,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    subscription_price=sub_price,
    nowpayments_payment_id=nowpayments_payment_id,
    nowpayments_pay_address=nowpayments_pay_address,
    nowpayments_outcome_amount=nowpayments_outcome_amount,
    payment_status=payment_status  # ✅ NEW: Pass validated status to GCWebhook1
)
```

---

### File: `/OCTOBER/10-26/np-webhook-10-26/cloudtasks_client.py`

---

#### Change 1.4: Update CloudTasksClient Method Signature

**Location:** Line 16 (method definition for `enqueue_gcwebhook1_validated_payment`)

**Find the method signature:**
```python
def enqueue_gcwebhook1_validated_payment(
    self,
    queue_name: str,
    target_url: str,
    user_id: int,
    closed_channel_id: str,
    subscription_price: str,
    nowpayments_payment_id: str = None,
    nowpayments_pay_address: str = None,
    nowpayments_outcome_amount: str = None
) -> Optional[str]:
```

**AFTER (add payment_status parameter):**
```python
def enqueue_gcwebhook1_validated_payment(
    self,
    queue_name: str,
    target_url: str,
    user_id: int,
    closed_channel_id: str,
    subscription_price: str,
    nowpayments_payment_id: str = None,
    nowpayments_pay_address: str = None,
    nowpayments_outcome_amount: str = None,
    payment_status: str = 'finished'  # ✅ NEW: Default to 'finished' for safety
) -> Optional[str]:
```

---

#### Change 1.5: Add payment_status to Payload

**Location:** Within the `enqueue_gcwebhook1_validated_payment` method (around line 40-60)

**Find the payload dictionary:**
```python
payload = {
    "user_id": user_id,
    "closed_channel_id": closed_channel_id,
    "subscription_price": subscription_price,
    "nowpayments_payment_id": nowpayments_payment_id,
    "nowpayments_pay_address": nowpayments_pay_address,
    "nowpayments_outcome_amount": nowpayments_outcome_amount
}
```

**AFTER:**
```python
payload = {
    "user_id": user_id,
    "closed_channel_id": closed_channel_id,
    "subscription_price": subscription_price,
    "nowpayments_payment_id": nowpayments_payment_id,
    "nowpayments_pay_address": nowpayments_pay_address,
    "nowpayments_outcome_amount": nowpayments_outcome_amount,
    "payment_status": payment_status  # ✅ NEW: Include status in payload
}
```

**Add log statement:**
```python
print(f"✅ [CLOUD_TASKS] Payment status: {payment_status}")
```

---

## Phase 2: GCWebhook1 Status Check (Second Layer) ✅

### File: `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`

---

#### Change 2.1: Extract and Validate payment_status

**Location:** After line 208 (after parsing request JSON in `/process-validated-payment` endpoint)

**Find this code (around line 192-208):**
```python
@app.route("/process-validated-payment", methods=["POST"])
def process_validated_payment():
    try:
        print(f"🎯 [GCWEBHOOK1] Validated payment received from np-webhook")

        # Parse JSON payload
        request_data = request.get_json()
        if not request_data:
            abort(400, "Invalid JSON payload")
```

**Insert AFTER line 208 (after parsing JSON):**

```python
        # ============================================================================
        # CRITICAL: Defense-in-depth - Validate payment_status again
        # ============================================================================
        payment_status = request_data.get('payment_status', '').lower()

        ALLOWED_PAYMENT_STATUSES = ['finished']

        print(f"🔍 [GCWEBHOOK1] Payment status received: '{payment_status}'")
        print(f"✅ [GCWEBHOOK1] Allowed statuses: {ALLOWED_PAYMENT_STATUSES}")

        if payment_status not in ALLOWED_PAYMENT_STATUSES:
            print(f"=" * 80)
            print(f"⏸️ [GCWEBHOOK1] PAYMENT STATUS VALIDATION FAILED (Second Layer)")
            print(f"=" * 80)
            print(f"📊 [GCWEBHOOK1] Current status: '{payment_status}'")
            print(f"⏳ [GCWEBHOOK1] Required status: 'finished'")
            print(f"👤 [GCWEBHOOK1] User ID: {request_data.get('user_id')}")
            print(f"💰 [GCWEBHOOK1] Amount: {request_data.get('subscription_price')}")
            print(f"🛡️ [GCWEBHOOK1] Defense-in-depth check prevented processing")
            print(f"=" * 80)

            # Return 200 OK to prevent Cloud Tasks retry
            # This should never happen if np-webhook is working correctly
            return jsonify({
                "status": "rejected",
                "message": f"Payment status not ready for processing (current: {payment_status})",
                "payment_status": payment_status,
                "required_status": "finished",
                "defense_layer": "gcwebhook1_second_layer"
            }), 200

        # If we reach here, payment_status is 'finished' - proceed with routing
        print(f"=" * 80)
        print(f"✅ [GCWEBHOOK1] PAYMENT STATUS VALIDATED (Second Layer): '{payment_status}'")
        print(f"✅ [GCWEBHOOK1] Proceeding with instant/threshold routing")
        print(f"=" * 80)
```

**Why second layer:**
- Defense-in-depth security principle
- Protects against direct GCWebhook1 calls (bypassing np-webhook)
- Protects against configuration errors in np-webhook
- Provides audit trail of status at routing decision point

---

## Phase 3: GCSplit1 Idempotency Protection ✅

### File: `/OCTOBER/10-26/GCSplit1-10-26/database_manager.py`

---

#### Change 3.1: Add check_split_payout_que_by_cn_api_id() Method

**Location:** After line 332 (after `insert_split_payout_que` method)

**Insert this new method:**

```python
def check_split_payout_que_by_cn_api_id(self, cn_api_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if a ChangeNow transaction already exists in split_payout_que.
    Used for idempotency protection during Cloud Tasks retries.

    Args:
        cn_api_id: ChangeNow transaction ID to check

    Returns:
        Dictionary with record data if exists, None otherwise
    """
    conn = None
    cur = None
    try:
        print(f"🔍 [DB_CHECK] Checking for existing ChangeNow transaction: {cn_api_id}")

        conn = self.get_database_connection()
        cur = conn.cursor()

        # Query for existing record
        check_query = """
            SELECT unique_id, cn_api_id, from_currency, to_currency,
                   from_amount, to_amount, created_at
            FROM split_payout_que
            WHERE cn_api_id = %s
        """

        cur.execute(check_query, (cn_api_id,))
        row = cur.fetchone()

        if row:
            print(f"✅ [DB_CHECK] ChangeNow transaction EXISTS in split_payout_que")
            print(f"🆔 [DB_CHECK] Unique ID: {row[0]}")
            print(f"🆔 [DB_CHECK] CN API ID: {row[1]}")
            print(f"💰 [DB_CHECK] {row[2]}→{row[3]}: {row[4]}→{row[5]}")
            print(f"🕒 [DB_CHECK] Created: {row[6]}")
            print(f"🛡️ [DB_CHECK] IDEMPOTENCY: Duplicate insertion prevented")

            return {
                'unique_id': row[0],
                'cn_api_id': row[1],
                'from_currency': row[2],
                'to_currency': row[3],
                'from_amount': float(row[4]) if row[4] else 0.0,
                'to_amount': float(row[5]) if row[5] else 0.0,
                'created_at': row[6]
            }
        else:
            print(f"✅ [DB_CHECK] ChangeNow transaction NOT FOUND - safe to insert")
            return None

    except Exception as e:
        print(f"❌ [DB_CHECK] Error checking ChangeNow transaction: {e}")
        return None
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
```

---

### File: `/OCTOBER/10-26/GCSplit1-10-26/tps1-10-26.py`

---

#### Change 3.2: Add Idempotency Check in endpoint_3

**Location:** BEFORE line 702 (before `database_manager.insert_split_payout_que()` call)

**Find this code (around lines 695-723):**
```python
        # Insert into split_payout_que table
        if not database_manager:
            print(f"❌ [ENDPOINT_3] Database manager not available")
            abort(500, "Database unavailable")

        print(f"💾 [ENDPOINT_3] Inserting into split_payout_que")

        que_success = database_manager.insert_split_payout_que(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            # ... other params ...
        )

        if not que_success:
            print(f"❌ [ENDPOINT_3] Failed to insert into split_payout_que")
            abort(500, "Database insertion failed")
```

**REPLACE WITH:**
```python
        # ============================================================================
        # CRITICAL: Idempotency Check - Prevent Duplicate Insertions
        # ============================================================================
        if not database_manager:
            print(f"❌ [ENDPOINT_3] Database manager not available")
            abort(500, "Database unavailable")

        # Check if this ChangeNow transaction already exists
        print(f"🔍 [ENDPOINT_3] Checking for existing ChangeNow transaction")
        existing_record = database_manager.check_split_payout_que_by_cn_api_id(cn_api_id)

        if existing_record:
            print(f"=" * 80)
            print(f"🛡️ [ENDPOINT_3] IDEMPOTENT REQUEST DETECTED")
            print(f"=" * 80)
            print(f"✅ [ENDPOINT_3] ChangeNow transaction already processed: {cn_api_id}")
            print(f"🆔 [ENDPOINT_3] Linked unique_id: {existing_record['unique_id']}")
            print(f"🕒 [ENDPOINT_3] Original insertion: {existing_record['created_at']}")
            print(f"🔄 [ENDPOINT_3] This is likely a Cloud Tasks retry")
            print(f"✅ [ENDPOINT_3] Returning success to prevent retry loop")
            print(f"=" * 80)

            # Return 200 OK to prevent Cloud Tasks from retrying
            return jsonify({
                "status": "success",
                "message": "ChangeNow transaction already processed (idempotent)",
                "unique_id": existing_record['unique_id'],
                "cn_api_id": cn_api_id,
                "from_currency": existing_record['from_currency'],
                "to_currency": existing_record['to_currency'],
                "idempotent": True,
                "original_processing_time": str(existing_record['created_at'])
            }), 200

        # If we reach here, this is a NEW transaction - proceed with insertion
        print(f"💾 [ENDPOINT_3] Inserting into split_payout_que")

        que_success = database_manager.insert_split_payout_que(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            from_currency=from_currency,
            to_currency=to_currency,
            from_network=from_network,
            to_network=to_network,
            from_amount=from_amount,
            to_amount=to_amount,
            payin_address=payin_address,
            payout_address=payout_address,
            refund_address=refund_address,
            flow=flow,
            type_=type_
        )

        if not que_success:
            print(f"❌ [ENDPOINT_3] Failed to insert into split_payout_que")

            # Double-check if failure is due to race condition (concurrent insertion)
            print(f"🔍 [ENDPOINT_3] Checking for concurrent insertion (race condition)")
            existing_record = database_manager.check_split_payout_que_by_cn_api_id(cn_api_id)

            if existing_record:
                print(f"✅ [ENDPOINT_3] Record inserted by concurrent request")
                print(f"✅ [ENDPOINT_3] Treating as idempotent success")

                return jsonify({
                    "status": "success",
                    "message": "Concurrent insertion handled (idempotent)",
                    "unique_id": existing_record['unique_id'],
                    "cn_api_id": cn_api_id,
                    "idempotent": True,
                    "race_condition_handled": True
                }), 200
            else:
                # Genuine insertion failure (not duplicate)
                abort(500, "Database insertion failed")
```

**Why this approach:**
- **Prevents duplicate key errors** on `unique_id` primary key
- **Handles Cloud Tasks retries** gracefully (same `cn_api_id` = idempotent)
- **Handles race conditions** (concurrent requests with same `cn_api_id`)
- **Returns 200 OK** to stop Cloud Tasks retry loop
- **Preserves audit trail** of when original insertion occurred

---

## Phase 4: Testing Strategy ✅

### Test Case 1: Non-Finished IPN (First Layer Check)

**Setup:**
```bash
# Send test IPN with status='confirming' to np-webhook
curl -X POST https://np-webhook-10-26-XXXXXX.run.app/ \
  -H "Content-Type: application/json" \
  -H "x-nowpayments-sig: <valid_signature>" \
  -d '{
    "payment_id": 9999999999,
    "payment_status": "confirming",
    "pay_address": "0xTEST...",
    "price_amount": 3,
    "price_currency": "usd",
    "pay_amount": 0.001,
    "outcome_amount": 0.0009,
    "outcome_currency": "eth"
  }'
```

**Expected Results:**
- ✅ np-webhook returns 200 OK with `"status": "acknowledged"`
- ✅ Log shows: `⏸️ [IPN] PAYMENT STATUS NOT READY FOR PROCESSING`
- ✅ NO Cloud Task created to GCWebhook1
- ✅ NO database update
- ✅ NO downstream processing

**Verification:**
```bash
# Check Cloud Tasks queue (should be empty)
gcloud tasks list --queue=gcwebhook1-queue --location=us-central1

# Check logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=np-webhook-10-26 AND textPayload:\"PAYMENT STATUS NOT READY\"" --limit=5
```

---

### Test Case 2: Finished IPN - Instant Payout

**Setup:**
```bash
# Send test IPN with status='finished' to np-webhook
curl -X POST https://np-webhook-10-26-XXXXXX.run.app/ \
  -H "Content-Type: application/json" \
  -H "x-nowpayments-sig: <valid_signature>" \
  -d '{
    "payment_id": 8888888888,
    "payment_status": "finished",
    "pay_address": "0xTEST...",
    "price_amount": 3,
    "price_currency": "usd",
    "pay_amount": 0.001,
    "outcome_amount": 0.0009,
    "outcome_currency": "eth"
  }'
```

**Expected Results:**
- ✅ np-webhook returns 200 OK with `"status": "success"`
- ✅ Log shows: `✅ [IPN] PAYMENT STATUS VALIDATED: 'finished'`
- ✅ Cloud Task created to GCWebhook1
- ✅ GCWebhook1 validates status (second layer)
- ✅ GCWebhook1 routes to GCSplit1 (instant payout)
- ✅ Full flow completes: GCSplit1 → GCSplit2 → GCSplit1 → GCSplit3 → GCHostPay

**Verification:**
```bash
# Check np-webhook logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=np-webhook-10-26 AND textPayload:\"PAYMENT STATUS VALIDATED\"" --limit=5

# Check GCWebhook1 logs (second layer)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcwebhook1-10-26 AND textPayload:\"PAYMENT STATUS VALIDATED\"" --limit=5

# Check GCSplit1 logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26 AND textPayload:\"ENDPOINT_1\"" --limit=10
```

---

### Test Case 3: Finished IPN - Threshold Payout

**Setup:**
```bash
# Send test IPN with status='finished' for client with threshold payout
# Use closed_channel_id that has payout_mode='threshold' in main_clients_database
curl -X POST https://np-webhook-10-26-XXXXXX.run.app/ \
  -H "Content-Type: application/json" \
  -H "x-nowpayments-sig: <valid_signature>" \
  -d '{
    "payment_id": 7777777777,
    "payment_status": "finished",
    "pay_address": "0xTEST...",
    "price_amount": 3,
    "price_currency": "usd",
    "pay_amount": 0.001,
    "outcome_amount": 0.0009,
    "outcome_currency": "eth"
  }'
```

**Expected Results:**
- ✅ np-webhook validates status='finished'
- ✅ GCWebhook1 validates status='finished' (second layer)
- ✅ GCWebhook1 routes to GCAccumulator (threshold payout)
- ✅ GCAccumulator stores payment for accumulation
- ✅ NO immediate conversion to client currency

**Verification:**
```bash
# Check GCWebhook1 routing decision
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcwebhook1-10-26 AND textPayload:\"Threshold payout mode\"" --limit=5

# Check GCAccumulator logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcaccumulator-10-26" --limit=10
```

---

### Test Case 4: Idempotency - Duplicate cn_api_id

**Setup:**
```bash
# Step 1: Send normal request to GCSplit3
# GCSplit3 creates ChangeNow transaction with cn_api_id='test123abc'

# Step 2: Manually trigger GCSplit1 endpoint_3 with SAME cn_api_id
curl -X POST https://gcsplit1-10-26-XXXXXX.run.app/eth-client-swap \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<encrypted_token_with_cn_api_id_test123abc>"
  }'

# Expected: First call inserts successfully
# Expected: Second call returns 200 OK (idempotent - no insertion)
```

**Expected Results:**
- ✅ First call: Inserts into split_payout_que successfully
- ✅ Second call: Detects existing cn_api_id
- ✅ Second call: Returns 200 OK with `"idempotent": true`
- ✅ Second call: NO duplicate key error
- ✅ Second call: NO Cloud Tasks retry

**Verification:**
```bash
# Check GCSplit1 logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26 AND textPayload:\"IDEMPOTENT REQUEST DETECTED\"" --limit=5

# Check database (should have only ONE record)
gcloud sql connect telepaypsql --user=postgres --database=telepaydb
SELECT * FROM split_payout_que WHERE cn_api_id = 'test123abc';
# Should return 1 row only
```

---

### Test Case 5: Bypass Attempt (Direct GCWebhook1 Call)

**Setup:**
```bash
# Attempt to call GCWebhook1 directly with status='confirming' (bypassing np-webhook)
curl -X POST https://gcwebhook1-10-26-XXXXXX.run.app/process-validated-payment \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123456789,
    "closed_channel_id": "-1003296084379",
    "subscription_price": "3",
    "payment_status": "confirming"
  }'
```

**Expected Results:**
- ✅ GCWebhook1 second layer catches invalid status
- ✅ Returns 200 OK with `"status": "rejected"`
- ✅ Log shows: `⏸️ [GCWEBHOOK1] PAYMENT STATUS VALIDATION FAILED (Second Layer)`
- ✅ NO routing to GCSplit1 or GCAccumulator
- ✅ Defense-in-depth protection works

**Verification:**
```bash
# Check GCWebhook1 logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcwebhook1-10-26 AND textPayload:\"Defense-in-depth check prevented processing\"" --limit=5
```

---

## Phase 5: Deployment Strategy ✅

### Deployment Order (CRITICAL)

**Deploy in this exact order to maintain service availability:**

#### Step 1: Deploy np-webhook-10-26 (First Layer)

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26

# Build Docker image
docker build -t gcr.io/telepay-459221/np-webhook-10-26:latest .

# Push to Google Container Registry
docker push gcr.io/telepay-459221/np-webhook-10-26:latest

# Deploy to Cloud Run
gcloud run deploy np-webhook-10-26 \
  --image gcr.io/telepay-459221/np-webhook-10-26:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated

# Verify deployment
gcloud run services describe np-webhook-10-26 --region=us-central1
```

**Test after deployment:**
- Send test IPN with status='confirming' → Should be rejected
- Send test IPN with status='finished' → Should be processed
- Check logs for status validation messages

---

#### Step 2: Deploy GCWebhook1-10-26 (Second Layer)

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26

# Build Docker image
docker build -t gcr.io/telepay-459221/gcwebhook1-10-26:latest .

# Push to GCR
docker push gcr.io/telepay-459221/gcwebhook1-10-26:latest

# Deploy to Cloud Run
gcloud run deploy gcwebhook1-10-26 \
  --image gcr.io/telepay-459221/gcwebhook1-10-26:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated

# Verify deployment
gcloud run services describe gcwebhook1-10-26 --region=us-central1
```

**Test after deployment:**
- Trigger test payment through np-webhook
- Verify GCWebhook1 validates status (second layer)
- Check logs for defense-in-depth messages

---

#### Step 3: Deploy GCSplit1-10-26 (Idempotency Protection)

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit1-10-26

# Build Docker image
docker build -t gcr.io/telepay-459221/gcsplit1-10-26:latest .

# Push to GCR
docker push gcr.io/telepay-459221/gcsplit1-10-26:latest

# Deploy to Cloud Run
gcloud run deploy gcsplit1-10-26 \
  --image gcr.io/telepay-459221/gcsplit1-10-26:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated

# Verify deployment
gcloud run services describe gcsplit1-10-26 --region=us-central1
```

**Test after deployment:**
- Trigger Cloud Tasks retry scenario
- Verify idempotency check prevents duplicate key errors
- Check logs for "IDEMPOTENT REQUEST DETECTED" messages

---

### Post-Deployment Verification

#### Verify All Services Are Running

```bash
# Check service status
gcloud run services list --region=us-central1 | grep -E "np-webhook-10-26|gcwebhook1-10-26|gcsplit1-10-26"

# Check recent revisions
gcloud run revisions list --service=np-webhook-10-26 --region=us-central1 --limit=3
gcloud run revisions list --service=gcwebhook1-10-26 --region=us-central1 --limit=3
gcloud run revisions list --service=gcsplit1-10-26 --region=us-central1 --limit=3
```

#### Monitor Logs for First Real Payment

```bash
# Terminal 1: Watch np-webhook logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=np-webhook-10-26" --format=json

# Terminal 2: Watch GCWebhook1 logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=gcwebhook1-10-26" --format=json

# Terminal 3: Watch GCSplit1 logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26" --format=json
```

---

## Phase 6: Rollback Plan ✅

### If Issues Are Detected

#### Rollback np-webhook-10-26

```bash
# Find previous working revision
gcloud run revisions list --service=np-webhook-10-26 --region=us-central1 --limit=5

# Route 100% traffic to previous revision
gcloud run services update-traffic np-webhook-10-26 \
  --to-revisions=np-webhook-10-26-00XXX-xyz=100 \
  --region=us-central1

# Or delete latest revision entirely
gcloud run revisions delete np-webhook-10-26-00YYY-abc \
  --region=us-central1 \
  --quiet
```

#### Rollback GCWebhook1-10-26

```bash
# Route traffic to previous revision
gcloud run services update-traffic gcwebhook1-10-26 \
  --to-revisions=gcwebhook1-10-26-00XXX-xyz=100 \
  --region=us-central1
```

#### Rollback GCSplit1-10-26

```bash
# Route traffic to previous revision
gcloud run services update-traffic gcsplit1-10-26 \
  --to-revisions=gcsplit1-10-26-00XXX-xyz=100 \
  --region=us-central1
```

**Note:** Rollback will re-introduce the bugs but restore service availability. Fix the code issues and redeploy.

---

## Success Criteria ✅

### For np-webhook (First Layer):

- ✅ IPNs with status != 'finished' return 200 OK with `"status": "acknowledged"`
- ✅ IPNs with status = 'finished' trigger GCWebhook1 Cloud Task
- ✅ Logs show: `✅ [IPN] PAYMENT STATUS VALIDATED: 'finished'`
- ✅ No premature payouts before funds confirmed

### For GCWebhook1 (Second Layer):

- ✅ Requests with status != 'finished' return 200 OK with `"status": "rejected"`
- ✅ Requests with status = 'finished' route to GCSplit1/GCAccumulator
- ✅ Logs show: `✅ [GCWEBHOOK1] PAYMENT STATUS VALIDATED (Second Layer)`
- ✅ Defense-in-depth prevents bypass attempts

### For GCSplit1 (Idempotency):

- ✅ Duplicate cn_api_id insertions return 200 OK with `"idempotent": true`
- ✅ No duplicate key errors on split_payout_que
- ✅ Logs show: `🛡️ [ENDPOINT_3] IDEMPOTENT REQUEST DETECTED`
- ✅ Cloud Tasks retries don't cause infinite loops

---

## Monitoring & Alerts ✅

### Key Metrics to Watch

```bash
# Count non-finished IPNs received (should be non-zero if NowPayments sends status updates)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=np-webhook-10-26 AND textPayload:\"PAYMENT STATUS NOT READY\"" --limit=50 --format=json | jq length

# Count finished IPNs processed (should be steady rate)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=np-webhook-10-26 AND textPayload:\"PAYMENT STATUS VALIDATED\"" --limit=50 --format=json | jq length

# Count defense-in-depth rejections (should be zero in normal operation)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcwebhook1-10-26 AND textPayload:\"Defense-in-depth check prevented processing\"" --limit=50 --format=json | jq length

# Count idempotent requests (indicates Cloud Tasks retries - should be low)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26 AND textPayload:\"IDEMPOTENT REQUEST DETECTED\"" --limit=50 --format=json | jq length
```

### Alert Conditions

**Alert if:**
1. Defense-in-depth rejections > 0 (indicates bypass attempt or np-webhook failure)
2. Idempotent requests > 10% of total requests (indicates high retry rate)
3. Zero 'finished' IPNs processed for > 1 hour (indicates payment flow broken)

---

## Documentation Updates ✅

### Update PROGRESS.md

Add entry at TOP of file:

```markdown
## 2025-11-07 - IPN Callback Status Validation + Idempotency Fix

### Changes Implemented:
- ✅ Added NowPayments status='finished' check in np-webhook (first layer)
- ✅ Added NowPayments status='finished' check in GCWebhook1 (second layer - defense-in-depth)
- ✅ Added idempotency protection in GCSplit1 endpoint_3 (prevents duplicate key errors)
- ✅ Modified Cloud Tasks payload to include payment_status
- ✅ Added check_split_payout_que_by_cn_api_id() method to database_manager

### Files Modified:
- np-webhook-10-26/app.py (status validation)
- np-webhook-10-26/cloudtasks_client.py (payload update)
- GCWebhook1-10-26/tph1-10-26.py (second layer validation)
- GCSplit1-10-26/database_manager.py (idempotency check method)
- GCSplit1-10-26/tps1-10-26.py (idempotency protection)

### Impact:
- ✅ Prevents premature payouts before NowPayments confirms funds
- ✅ Eliminates duplicate key errors during Cloud Tasks retries
- ✅ Defense-in-depth security against bypass attempts
- ✅ Proper audit trail of payment status progression
```

---

### Update DECISIONS.md

Add entry at TOP of file:

```markdown
## 2025-11-07 - NowPayments Status Validation Strategy

### Decision: Defense-in-Depth Status Validation

**Context:**
- System was processing ALL NowPayments IPNs regardless of payment_status
- Risk of premature payouts before funds confirmed
- No validation at np-webhook or GCWebhook1 layers

**Decision:**
Implement two-layer status validation:
1. **First layer (np-webhook):** Validate status='finished' before triggering GCWebhook1
2. **Second layer (GCWebhook1):** Re-validate status='finished' before routing

**Rationale:**
- Defense-in-depth security principle
- Protects against configuration errors
- Protects against direct GCWebhook1 calls (bypass attempts)
- Provides audit trail at both layers

**Alternatives Considered:**
- ❌ Single layer validation (less secure)
- ❌ Database-level validation (too late in flow)
- ✅ Two-layer validation (chosen for robustness)

### Decision: Idempotency by cn_api_id

**Context:**
- Cloud Tasks retries cause duplicate insertions into split_payout_que
- Primary key on unique_id prevents multiple ChangeNow transactions per request
- Need to handle retries gracefully

**Decision:**
- Check for existing cn_api_id before inserting into split_payout_que
- Return 200 OK if record exists (idempotent operation)
- Prevent Cloud Tasks retry loops

**Rationale:**
- cn_api_id is unique per ChangeNow transaction (guaranteed by API)
- Idempotent operations prevent infinite retry loops
- Gracefully handles race conditions (concurrent requests)
```

---

## Summary of Changes ✅

### Files Modified: 5

1. **np-webhook-10-26/app.py**
   - Added status validation after line 631
   - Added payment_status to Cloud Tasks payload (line ~900)

2. **np-webhook-10-26/cloudtasks_client.py**
   - Updated enqueue_gcwebhook1_validated_payment() signature
   - Added payment_status to payload dictionary

3. **GCWebhook1-10-26/tph1-10-26.py**
   - Added second layer status validation after line 208
   - Added defense-in-depth rejection logic

4. **GCSplit1-10-26/database_manager.py**
   - Added check_split_payout_que_by_cn_api_id() method (after line 332)

5. **GCSplit1-10-26/tps1-10-26.py**
   - Added idempotency check before line 702
   - Added race condition handling

### Lines of Code Added: ~200
- np-webhook: ~50 lines
- GCWebhook1: ~40 lines
- GCSplit1 database_manager: ~60 lines
- GCSplit1 endpoint: ~50 lines

### Estimated Time: 2 hours
- Code changes: 1 hour
- Testing: 30 minutes
- Deployment: 30 minutes

---

## Final Checklist Before Deployment ✅

- [ ] **Phase 1 Complete:** np-webhook status validation added
- [ ] **Phase 2 Complete:** GCWebhook1 second layer validation added
- [ ] **Phase 3 Complete:** GCSplit1 idempotency protection added
- [ ] **Test Case 1 Passed:** Non-finished IPN rejected
- [ ] **Test Case 2 Passed:** Finished IPN (instant) processes correctly
- [ ] **Test Case 3 Passed:** Finished IPN (threshold) processes correctly
- [ ] **Test Case 4 Passed:** Duplicate cn_api_id handled idempotently
- [ ] **Test Case 5 Passed:** Defense-in-depth prevents bypass
- [ ] **Deployment Order:** np-webhook → GCWebhook1 → GCSplit1
- [ ] **Rollback Plan:** Documented and tested
- [ ] **Monitoring:** Log queries prepared
- [ ] **Documentation:** PROGRESS.md and DECISIONS.md updated

---

**Last Updated:** 2025-11-07
**Priority:** CRITICAL - DEPLOY ASAP
**Status:** Ready for implementation
