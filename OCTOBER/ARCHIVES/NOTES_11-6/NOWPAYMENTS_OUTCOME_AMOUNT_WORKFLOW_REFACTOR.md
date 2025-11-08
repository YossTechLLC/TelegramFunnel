# NowPayments Outcome Amount Workflow Refactoring

## Problem Statement

### Current Incorrect Flow
```
GCWebhook2 receives payment
    ↓
IMMEDIATELY queues GCSplit1/GCAccumulator with subscription_price
    ↓
Later... NP-webhook validates IPN
    ↓
NP-webhook calls CoinGecko API
    ↓
nowpayments_outcome_amount_usd is calculated and stored
```

### Critical Issue
- **GCSplit1/GCAccumulator are triggered with `subscription_price` (declared value)**
- **They SHOULD use `nowpayments_outcome_amount_usd` (actual USD value of crypto received)**
- **But this value doesn't exist until AFTER IPN validation and CoinGecko price fetch**

### Why This Matters
The system currently processes payouts based on what the user DECLARED they would pay, not what they ACTUALLY paid in crypto. This creates:
- **Financial discrepancies**: Payout amounts don't match actual received funds
- **Loss of revenue**: If ETH price drops between subscription creation and payment, we pay out more than we received
- **Accounting errors**: Database shows incorrect payment flows

---

## Current Architecture Analysis

### GCWebhook2 Flow (tph2-10-26.py)

```python
# Line 214-227: Threshold Payout - WRONG
if payout_mode == "threshold":
    task_name = cloudtasks_client.enqueue_gcaccumulator_payment(
        subscription_price=subscription_price,  # ❌ Uses declared price
        # Missing: nowpayments_outcome_amount_usd
    )

# Line 292-301: Instant Payout - WRONG
if payout_mode == "instant":
    task_name = cloudtasks_client.enqueue_gcsplit1_payment_split(
        subscription_price=subscription_price  # ❌ Uses declared price
        # Missing: nowpayments_outcome_amount_usd
    )
```

### NP-Webhook Flow (np-webhook-10-26/app.py)

```python
# This is where the ACTUAL outcome amount is calculated:
1. Validates IPN callback from NowPayments
2. Calls get_crypto_usd_price() to fetch ETH price from CoinGecko
3. Calculates: outcome_amount_usd = outcome_amount * eth_usd_price
4. Updates database with nowpayments_outcome_amount_usd
```

**Example from logs:**
```
🔍 [PRICE] Fetching ETH price from CoinGecko...
💰 [PRICE] ETH/USD = $3,902.76
💰 [CONVERT] 0.00026932 ETH = $1.05 USD
💰 [VALIDATION] Outcome in USD: $1.05
```

---

## Proposed Solution: Event-Driven Architecture

### Architecture Overview

```
User Pays → NowPayments
    ↓
GCWebhook2: Create Record + Wait for Validation
    ↓ (no queuing yet)
NP-Webhook: Validate IPN
    ↓
NP-Webhook: Fetch CoinGecko Price
    ↓
NP-Webhook: Calculate & Store nowpayments_outcome_amount_usd
    ↓
NP-Webhook: Queue GCSplit1/GCAccumulator ✅
    ↓ (with correct outcome amount)
GCSplit1/GCAccumulator: Process with ACTUAL amount
```

### Key Changes Required

#### 1. **GCWebhook2 Changes (tph2-10-26.py)**

**REMOVE:**
- All `cloudtasks_client.enqueue_gcsplit1_payment_split()` calls
- All `cloudtasks_client.enqueue_gcaccumulator_payment()` calls

**ADD:**
- Store payout configuration in database for later retrieval
- Set payment status to `pending_validation`

```python
# New flow - GCWebhook2 does NOT queue payments
def handle_telegram_success(user_id, payment_data):
    # 1. Store payment record
    conn.execute("""
        INSERT INTO private_channel_users_database
        (user_id, closed_channel_id, wallet_address, payout_currency,
         payout_network, payout_mode, subscription_price,
         payment_status, nowpayments_payment_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending_validation', %s)
    """, (...))

    # 2. Log and wait for NP webhook
    logger.info(f"💾 [PAYMENT] Stored payment record, awaiting IPN validation")
    logger.info(f"⏳ [QUEUE] Payment will be queued after validation")

    # 3. Return success to Telegram
    return jsonify({"status": "success"})
```

#### 2. **NP-Webhook Changes (np-webhook-10-26/app.py)**

**ADD:**
- CloudTasks client initialization
- Logic to determine payout_mode from database
- Queue GCSplit1 for instant payouts
- Queue GCAccumulator for threshold payouts

```python
from cloudtasks_client import CloudTasksClient

cloudtasks_client = CloudTasksClient(
    project_id=config.CLOUD_TASKS_PROJECT_ID,
    location=config.CLOUD_TASKS_LOCATION
)

@app.route('/webhook', methods=['POST'])
def handle_nowpayments_webhook():
    # ... existing validation logic ...

    # After successful validation and price calculation:
    outcome_amount_usd = outcome_amount * eth_usd_price

    # 1. Update database
    cursor.execute("""
        UPDATE private_channel_users_database
        SET nowpayments_outcome_amount_usd = %s,
            payment_status = 'validated'
        WHERE nowpayments_payment_id = %s
    """, (outcome_amount_usd, payment_id))

    # 2. Fetch payment configuration
    cursor.execute("""
        SELECT user_id, closed_channel_id, wallet_address,
               payout_currency, payout_network, payout_mode,
               subscription_id, nowpayments_pay_address,
               nowpayments_outcome_amount
        FROM private_channel_users_database
        WHERE nowpayments_payment_id = %s
    """, (payment_id,))

    payment_config = cursor.fetchone()

    # 3. Queue appropriate payment processor
    if payment_config['payout_mode'] == 'instant':
        logger.info(f"🚀 [QUEUE] Queuing GCSplit1 with outcome: ${outcome_amount_usd}")
        cloudtasks_client.enqueue_gcsplit1_payment_split(
            queue_name=config.GCSPLIT1_QUEUE,
            target_url=config.GCSPLIT1_URL,
            user_id=payment_config['user_id'],
            closed_channel_id=payment_config['closed_channel_id'],
            wallet_address=payment_config['wallet_address'],
            payout_currency=payment_config['payout_currency'],
            payout_network=payment_config['payout_network'],
            subscription_price=outcome_amount_usd  # ✅ ACTUAL amount
        )

    elif payment_config['payout_mode'] == 'threshold':
        logger.info(f"🚀 [QUEUE] Queuing GCAccumulator with outcome: ${outcome_amount_usd}")
        cloudtasks_client.enqueue_gcaccumulator_payment(
            queue_name=config.GCACCUMULATOR_QUEUE,
            target_url=config.GCACCUMULATOR_URL,
            user_id=payment_config['user_id'],
            client_id=payment_config['closed_channel_id'],
            wallet_address=payment_config['wallet_address'],
            payout_currency=payment_config['payout_currency'],
            payout_network=payment_config['payout_network'],
            subscription_price=outcome_amount_usd,  # ✅ ACTUAL amount
            subscription_id=payment_config['subscription_id'],
            nowpayments_payment_id=payment_id,
            nowpayments_pay_address=payment_config['nowpayments_pay_address'],
            nowpayments_outcome_amount=payment_config['nowpayments_outcome_amount']
        )

    return jsonify({"status": "success"})
```

#### 3. **Database Schema Enhancement**

Add `payment_status` column to track payment lifecycle:

```sql
ALTER TABLE private_channel_users_database
ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'pending_validation';

-- Possible values:
-- 'pending_validation' - Waiting for NP IPN callback
-- 'validated' - IPN validated, outcome amount calculated
-- 'queued' - Payment queued to GCSplit1/GCAccumulator
-- 'processing' - Currently being processed
-- 'completed' - Payment successfully processed
-- 'failed' - Payment processing failed
```

#### 4. **CloudTasks Client Addition to NP-Webhook**

**New file: `np-webhook-10-26/cloudtasks_client.py`**
- Copy from GCWebhook2-10-26/cloudtasks_client.py
- Include both `enqueue_gcsplit1_payment_split()` and `enqueue_gcaccumulator_payment()`

**Update: `np-webhook-10-26/config_manager.py`**
- Add Cloud Tasks configuration
- Add GCSplit1 and GCAccumulator queue/URL secrets

```python
# New secrets required:
CLOUD_TASKS_PROJECT_ID = get_secret("CLOUD_TASKS_PROJECT_ID")
CLOUD_TASKS_LOCATION = get_secret("CLOUD_TASKS_LOCATION")
GCSPLIT1_QUEUE = get_secret("GCSPLIT1_QUEUE")
GCSPLIT1_URL = get_secret("GCSPLIT1_URL")
GCACCUMULATOR_QUEUE = get_secret("GCACCUMULATOR_QUEUE")
GCACCUMULATOR_URL = get_secret("GCACCUMULATOR_URL")
```

**Update: `np-webhook-10-26/requirements.txt`**
```
google-cloud-tasks>=2.16.0
```

---

## Payload Changes

### Current Payload (WRONG)
```json
{
  "user_id": "123",
  "sub_price": 1.28,  // ❌ Declared subscription price
  "wallet_address": "0x..."
}
```

### New Payload (CORRECT)
```json
{
  "user_id": "123",
  "sub_price": 1.05,  // ✅ Actual outcome amount in USD from CoinGecko
  "wallet_address": "0x..."
}
```

---

## Implementation Checklist

### Phase 1: Database Preparation
- [ ] Add `payment_status` column to `private_channel_users_database`
- [ ] Verify all required columns exist (payout_mode, nowpayments_outcome_amount_usd, etc.)
- [ ] Add index on `nowpayments_payment_id` for faster lookups

### Phase 2: NP-Webhook Enhancement
- [ ] Copy `cloudtasks_client.py` to `np-webhook-10-26/`
- [ ] Update `config_manager.py` with Cloud Tasks secrets
- [ ] Create/verify secrets in Secret Manager:
  - GCSPLIT1_QUEUE
  - GCSPLIT1_URL
  - GCACCUMULATOR_QUEUE
  - GCACCUMULATOR_URL
- [ ] Update `requirements.txt` with `google-cloud-tasks`
- [ ] Implement payment queuing logic in `app.py`
- [ ] Add database lookup for payment configuration
- [ ] Add conditional logic for instant vs threshold payout
- [ ] Add comprehensive logging
- [ ] Test with sample IPN callback

### Phase 3: GCWebhook2 Simplification
- [ ] Remove all `enqueue_gcsplit1_payment_split()` calls
- [ ] Remove all `enqueue_gcaccumulator_payment()` calls
- [ ] Add `payment_status = 'pending_validation'` to database inserts
- [ ] Update logging to reflect new flow
- [ ] Add documentation comments explaining the change

### Phase 4: GCSplit1/GCAccumulator Verification
- [ ] Verify they correctly use `sub_price` parameter
- [ ] Confirm no hardcoded assumptions about subscription_price
- [ ] Test with outcome amounts (should work without changes)

### Phase 5: Deployment
- [ ] Deploy updated `np-webhook-10-26`
- [ ] Deploy updated `gcwebhook2-10-26`
- [ ] Monitor logs for first few payments
- [ ] Verify outcome amounts match expected values
- [ ] Confirm GCSplit1/GCAccumulator receive correct amounts

### Phase 6: Testing & Validation
- [ ] Create test payment with known ETH amount
- [ ] Verify GCWebhook2 creates pending_validation record
- [ ] Trigger IPN callback to np-webhook
- [ ] Verify CoinGecko price fetch
- [ ] Verify nowpayments_outcome_amount_usd calculation
- [ ] Verify GCSplit1/GCAccumulator queuing with correct amount
- [ ] Compare outcome amount to subscription price (should differ due to market fluctuations)

---

## Risk Mitigation

### Timing Concerns
**Risk:** IPN callback might be delayed or fail
**Mitigation:**
- Implement payment status tracking
- Add timeout monitoring (alert if payment stays in `pending_validation` > 30 minutes)
- Create manual retry endpoint for stuck payments

### Database Consistency
**Risk:** Race conditions if multiple IPN callbacks arrive
**Mitigation:**
- Use database transaction with row-level locking
- Check payment_status before processing
- Add unique constraint on nowpayments_payment_id

### Backward Compatibility
**Risk:** Payments in-flight during deployment
**Mitigation:**
- Deploy during low-traffic period
- Keep old code paths for 24 hours (if payment_status is NULL, use old flow)
- Monitor for any payments stuck in old flow

---

## Success Metrics

### Financial Accuracy
- Payout amounts match actual received crypto value in USD
- No more than 1% discrepancy between outcome and payout

### System Reliability
- 100% of validated IPNs successfully queue payments
- < 5 minute average time from IPN to queuing
- Zero stuck payments in `pending_validation` > 1 hour

### Operational
- All payments have `nowpayments_outcome_amount_usd` populated
- Payment status accurately reflects lifecycle stage
- Logs clearly show flow: webhook → validation → pricing → queuing

---

## Example Flow Timeline

```
T+0s:   User completes payment, NowPayments creates transaction
T+1s:   GCWebhook2 creates record, status='pending_validation'
        ⏳ WAITING for IPN callback...
T+30s:  NowPayments sends IPN to np-webhook
T+31s:  np-webhook validates signature ✓
T+32s:  np-webhook fetches CoinGecko price: ETH = $3,902.76
T+33s:  np-webhook calculates: 0.00026932 ETH = $1.05 USD
T+34s:  np-webhook updates DB: nowpayments_outcome_amount_usd = 1.05
T+35s:  np-webhook determines payout_mode = 'instant'
T+36s:  np-webhook queues GCSplit1 with sub_price=1.05 ✅
T+37s:  GCSplit1 processes payment with ACTUAL amount
```

---

## Alternative Considered: Synchronous Wait

**Idea:** Have GCWebhook2 wait synchronously for IPN validation before returning

**Rejected because:**
- Could timeout (Telegram expects fast response)
- Ties up Cloud Run instance
- NowPayments IPN can take 30-60 seconds
- Increases costs (longer execution time)
- Poor user experience (waiting on payment confirmation)

**Event-driven approach is superior:**
- Fast response to user
- Decoupled services
- Better error handling
- Scales independently
- Industry best practice

---

## Conclusion

This refactoring ensures that all payment processing uses the **actual USD value of received cryptocurrency**, not the declared subscription price. This is critical for:

1. **Financial accuracy** - Payouts match real revenue
2. **Market resilience** - System handles crypto price volatility
3. **Audit compliance** - Accurate accounting of all transactions
4. **Risk management** - Never pay out more than received

The event-driven architecture leverages our existing Cloud Tasks infrastructure while maintaining service independence and scalability.
