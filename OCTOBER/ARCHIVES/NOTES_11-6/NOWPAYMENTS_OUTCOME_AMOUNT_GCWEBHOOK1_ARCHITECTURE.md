# NowPayments Outcome Amount - GCWebhook1 Orchestrator Architecture

## Executive Summary

This document proposes an alternative architecture to `NOWPAYMENTS_OUTCOME_AMOUNT_WORKFLOW_REFACTOR.md`, where **GCWebhook1 remains the central orchestrator** for all payment processing decisions. Instead of NP-Webhook directly queuing to GCSplit1/GCAccumulator, it triggers GCWebhook1 with validated payment data, allowing GCWebhook1 to make routing decisions.

### Key Principle
**"Single Responsibility with Central Orchestration"**
- NP-Webhook: Validates IPN, calculates outcome USD amount
- GCWebhook1: Orchestrates ALL payment routing decisions
- GCSplit1/GCAccumulator: Process payments with actual amounts

---

## Problem Analysis

### Current Timing Issue

```
Timeline of Events:
T+0s:   User pays, NowPayments creates invoice
T+30s:  Payment confirmed
        ↓
        ├─→ success_url redirects → GCWebhook1 (may happen first)
        └─→ IPN callback → NP-Webhook (may happen first)

Current Race Condition:
- GCWebhook1 tries to lookup nowpayments_outcome_amount_usd
- But NP-Webhook may not have calculated it yet!
- Result: GCWebhook1 queues with subscription_price (wrong amount)
```

**Root Cause:**
- GCWebhook1 (lines 176-189) attempts to lookup NowPayments data
- This data only exists AFTER NP-Webhook processes IPN
- The two webhooks arrive in non-deterministic order
- No coordination between them

---

## Proposed Architecture: Event-Driven Orchestration

### Flow Overview

```
User Pays → NowPayments
    ↓
NP-Webhook: Receive IPN Callback
    ↓
NP-Webhook: Validate Signature ✓
    ↓
NP-Webhook: Fetch CoinGecko ETH Price
    ↓
NP-Webhook: Calculate nowpayments_outcome_amount_usd
    ↓
NP-Webhook: Update Database
    ↓
NP-Webhook: Queue Task to GCWebhook1 ✅
    ↓ (with validated outcome amount)
GCWebhook1: Receive Payment Processing Request
    ↓
GCWebhook1: Determine Payout Mode (instant vs threshold)
    ↓
GCWebhook1: Queue to GCSplit1 OR GCAccumulator
    ↓ (with actual outcome USD amount)
Payment Processor: Execute with REAL amount
```

### Advantages Over Direct Queuing

1. **Separation of Concerns**
   - NP-Webhook: Validation & pricing ONLY
   - GCWebhook1: Business logic & routing ONLY
   - Clean separation of responsibilities

2. **Centralized Orchestration**
   - All payment routing logic lives in ONE place
   - Easier to debug and modify
   - Single source of truth for payout decisions

3. **Flexibility**
   - Easy to add new payout modes in GCWebhook1
   - No need to update NP-Webhook for business logic changes
   - Maintains existing orchestration patterns

4. **Testability**
   - Can test NP-Webhook validation independently
   - Can test GCWebhook1 routing independently
   - Clearer unit test boundaries

---

## Detailed Implementation

### Phase 1: Create New GCWebhook1 Endpoint

**New endpoint: `/process-validated-payment`**

This endpoint receives validated payment data from NP-Webhook and handles all orchestration.

```python
# GCWebhook1-10-26/tph1-10-26.py

@app.route("/process-validated-payment", methods=["POST"])
def process_validated_payment():
    """
    Process a payment that has been validated by np-webhook.

    This endpoint is called by np-webhook AFTER:
    - IPN signature validation
    - CoinGecko price fetch
    - Outcome USD amount calculation

    Flow:
    1. Receive validated payment data
    2. Lookup payout configuration
    3. Route to GCSplit1 (instant) or GCAccumulator (threshold)
    4. Queue Telegram invite to GCWebhook2
    """
    try:
        print(f"🎯 [VALIDATED] Received validated payment from NP-Webhook")

        # Get validated payment data from NP-Webhook
        payment_data = request.get_json()

        user_id = payment_data.get('user_id')
        closed_channel_id = payment_data.get('closed_channel_id')
        wallet_address = payment_data.get('wallet_address')
        payout_currency = payment_data.get('payout_currency')
        payout_network = payment_data.get('payout_network')
        subscription_time_days = payment_data.get('subscription_time_days')
        subscription_price = payment_data.get('subscription_price')

        # CRITICAL: This is the ACTUAL outcome amount in USD from CoinGecko
        outcome_amount_usd = payment_data.get('outcome_amount_usd')

        # NowPayments metadata
        nowpayments_payment_id = payment_data.get('nowpayments_payment_id')
        nowpayments_pay_address = payment_data.get('nowpayments_pay_address')
        nowpayments_outcome_amount = payment_data.get('nowpayments_outcome_amount')

        print(f"✅ [VALIDATED] Payment Data:")
        print(f"   User ID: {user_id}")
        print(f"   Channel ID: {closed_channel_id}")
        print(f"   Declared Price: ${subscription_price}")
        print(f"   💰 ACTUAL Outcome (USD): ${outcome_amount_usd}")
        print(f"   Payment ID: {nowpayments_payment_id}")

        # Validate required fields
        if not all([user_id, closed_channel_id, outcome_amount_usd]):
            print(f"❌ [VALIDATED] Missing required fields")
            abort(400, "Missing required payment data")

        # Lookup payout strategy
        print(f"🔍 [VALIDATED] Checking payout strategy for channel {closed_channel_id}")
        payout_mode, payout_threshold = db_manager.get_payout_strategy(closed_channel_id)

        print(f"💰 [VALIDATED] Payout mode: {payout_mode}")

        # Route to appropriate payment processor
        if payout_mode == "threshold":
            print(f"🎯 [VALIDATED] Threshold payout - routing to GCAccumulator")

            # Get subscription ID for accumulation record
            subscription_id = db_manager.get_subscription_id(user_id, closed_channel_id)

            gcaccumulator_queue = config.get('gcaccumulator_queue')
            gcaccumulator_url = config.get('gcaccumulator_url')

            if not gcaccumulator_queue or not gcaccumulator_url:
                print(f"⚠️ [VALIDATED] GCAccumulator config missing")
                abort(500, "GCAccumulator configuration error")

            # Queue to GCAccumulator with ACTUAL outcome amount
            task_name = cloudtasks_client.enqueue_gcaccumulator_payment(
                queue_name=gcaccumulator_queue,
                target_url=gcaccumulator_url,
                user_id=user_id,
                client_id=closed_channel_id,
                wallet_address=wallet_address,
                payout_currency=payout_currency,
                payout_network=payout_network,
                subscription_price=outcome_amount_usd,  # ✅ ACTUAL USD amount
                subscription_id=subscription_id,
                nowpayments_payment_id=nowpayments_payment_id,
                nowpayments_pay_address=nowpayments_pay_address,
                nowpayments_outcome_amount=nowpayments_outcome_amount
            )

            if task_name:
                print(f"✅ [VALIDATED] Enqueued to GCAccumulator")
                print(f"🆔 [VALIDATED] Task: {task_name}")
            else:
                print(f"❌ [VALIDATED] Failed to enqueue to GCAccumulator")
                abort(500, "Failed to enqueue to GCAccumulator")

        else:  # instant payout
            print(f"⚡ [VALIDATED] Instant payout - routing to GCSplit1")

            gcsplit1_queue = config.get('gcsplit1_queue')
            gcsplit1_url = config.get('gcsplit1_url')

            if not gcsplit1_queue or not gcsplit1_url:
                print(f"⚠️ [VALIDATED] GCSplit1 config missing")
                abort(500, "GCSplit1 configuration error")

            # Queue to GCSplit1 with ACTUAL outcome amount
            task_name = cloudtasks_client.enqueue_gcsplit1_payment_split(
                queue_name=gcsplit1_queue,
                target_url=gcsplit1_url,
                user_id=user_id,
                closed_channel_id=closed_channel_id,
                wallet_address=wallet_address,
                payout_currency=payout_currency,
                payout_network=payout_network,
                subscription_price=outcome_amount_usd  # ✅ ACTUAL USD amount
            )

            if task_name:
                print(f"✅ [VALIDATED] Enqueued to GCSplit1")
                print(f"🆔 [VALIDATED] Task: {task_name}")
            else:
                print(f"❌ [VALIDATED] Failed to enqueue to GCSplit1")
                abort(500, "Failed to enqueue to GCSplit1")

        # Queue Telegram invite to GCWebhook2
        print(f"📱 [VALIDATED] Queuing Telegram invite")

        encrypted_token = token_manager.encrypt_token_for_gcwebhook2(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            subscription_time_days=subscription_time_days,
            subscription_price=subscription_price
        )

        if not encrypted_token:
            print(f"❌ [VALIDATED] Failed to encrypt token for GCWebhook2")
            abort(500, "Token encryption failed")

        gcwebhook2_queue = config.get('gcwebhook2_queue')
        gcwebhook2_url = config.get('gcwebhook2_url')

        task_name_gcwebhook2 = cloudtasks_client.enqueue_gcwebhook2_telegram_invite(
            queue_name=gcwebhook2_queue,
            target_url=gcwebhook2_url,
            encrypted_token=encrypted_token
        )

        if task_name_gcwebhook2:
            print(f"✅ [VALIDATED] Enqueued Telegram invite to GCWebhook2")
            print(f"🆔 [VALIDATED] Task: {task_name_gcwebhook2}")
        else:
            print(f"⚠️ [VALIDATED] Failed to enqueue Telegram invite")

        print(f"🎉 [VALIDATED] Payment processing completed successfully")
        return jsonify({
            "status": "success",
            "message": "Payment processed",
            "outcome_amount_usd": outcome_amount_usd
        }), 200

    except Exception as e:
        print(f"❌ [VALIDATED] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

---

### Phase 2: NP-Webhook Enhancement

**Add CoinGecko Integration and GCWebhook1 Triggering**

```python
# np-webhook-10-26/app.py

import requests
from cloudtasks_client import CloudTasksClient

# Initialize Cloud Tasks client
cloudtasks_client = CloudTasksClient(
    project_id=os.getenv('CLOUD_TASKS_PROJECT_ID'),
    location=os.getenv('CLOUD_TASKS_LOCATION')
)

GCWEBHOOK1_QUEUE = os.getenv('GCWEBHOOK1_QUEUE')
GCWEBHOOK1_URL = os.getenv('GCWEBHOOK1_URL')


def get_crypto_usd_price(crypto_symbol: str) -> Optional[float]:
    """
    Fetch current USD price for a cryptocurrency from CoinGecko API.

    Args:
        crypto_symbol: Cryptocurrency symbol (e.g., 'ETH', 'BTC')

    Returns:
        Current USD price or None if fetch fails
    """
    # Map common symbols to CoinGecko IDs
    coin_id_map = {
        'ETH': 'ethereum',
        'BTC': 'bitcoin',
        'USDT': 'tether',
        'USDC': 'usd-coin',
        'LTC': 'litecoin',
        'TRX': 'tron'
    }

    coin_id = coin_id_map.get(crypto_symbol.upper())
    if not coin_id:
        print(f"❌ [PRICE] Unsupported crypto symbol: {crypto_symbol}")
        return None

    try:
        print(f"🔍 [PRICE] Fetching {crypto_symbol} price from CoinGecko...")

        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd'
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        usd_price = data.get(coin_id, {}).get('usd')

        if usd_price:
            print(f"💰 [PRICE] {crypto_symbol}/USD = ${usd_price:,.2f}")
            return float(usd_price)
        else:
            print(f"❌ [PRICE] Price not found in response")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ [PRICE] Failed to fetch price: {e}")
        return None
    except Exception as e:
        print(f"❌ [PRICE] Unexpected error: {e}")
        return None


@app.route('/', methods=['POST'])
def handle_ipn():
    """
    Enhanced IPN handler that:
    1. Validates signature
    2. Calculates outcome USD amount via CoinGecko
    3. Updates database
    4. Triggers GCWebhook1 for orchestration
    """
    print(f"")
    print(f"=" * 80)
    print(f"📬 [IPN] Received callback from NowPayments")

    # ... existing signature verification code ...

    # Parse JSON payload
    ipn_data = request.get_json()

    # Extract payment data
    payment_id = ipn_data.get('payment_id')
    order_id = ipn_data.get('order_id')
    outcome_amount = ipn_data.get('outcome_amount')  # Amount in crypto
    outcome_currency = ipn_data.get('outcome_currency', ipn_data.get('pay_currency'))
    payment_status = ipn_data.get('payment_status')

    print(f"📋 [IPN] Payment Data:")
    print(f"   Payment ID: {payment_id}")
    print(f"   Order ID: {order_id}")
    print(f"   Outcome: {outcome_amount} {outcome_currency}")
    print(f"   Status: {payment_status}")

    # Parse order_id to get user_id and channel_id
    user_id, open_channel_id = parse_order_id(order_id)
    if not user_id or not open_channel_id:
        print(f"❌ [IPN] Invalid order_id format")
        abort(400, "Invalid order_id")

    # Lookup closed_channel_id
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s",
        (str(open_channel_id),)
    )
    result = cur.fetchone()

    if not result:
        print(f"❌ [IPN] Channel mapping not found")
        cur.close()
        conn.close()
        abort(400, "Channel not registered")

    closed_channel_id = result[0]

    # Fetch subscription configuration
    cur.execute("""
        SELECT wallet_address, payout_currency, payout_network,
               subscription_time, subscription_price
        FROM private_channel_users_database
        WHERE user_id = %s AND private_channel_id = %s
        ORDER BY id DESC LIMIT 1
    """, (user_id, closed_channel_id))

    sub_data = cur.fetchone()

    if not sub_data:
        print(f"❌ [IPN] Subscription not found")
        cur.close()
        conn.close()
        abort(400, "Subscription not found")

    wallet_address = sub_data[0]
    payout_currency = sub_data[1]
    payout_network = sub_data[2]
    subscription_time_days = sub_data[3]
    subscription_price = sub_data[4]

    # Calculate outcome amount in USD using CoinGecko
    print(f"")
    print(f"💱 [CONVERSION] Calculating USD value...")

    outcome_amount_usd = None

    if outcome_currency.upper() in ['USDT', 'USDC', 'USD']:
        # Already in USD equivalent
        outcome_amount_usd = float(outcome_amount)
        print(f"✅ [CONVERSION] Already in USD: ${outcome_amount_usd:.2f}")
    else:
        # Fetch current price from CoinGecko
        crypto_usd_price = get_crypto_usd_price(outcome_currency)

        if crypto_usd_price:
            outcome_amount_usd = float(outcome_amount) * crypto_usd_price
            print(f"💰 [CONVERT] {outcome_amount} {outcome_currency} = ${outcome_amount_usd:.2f} USD")
        else:
            print(f"❌ [CONVERT] Failed to fetch {outcome_currency} price")
            print(f"⚠️ [CONVERT] Falling back to declared subscription price")
            outcome_amount_usd = float(subscription_price)

    print(f"💰 [VALIDATION] Outcome in USD: ${outcome_amount_usd:.2f}")

    # Update database with all payment data including USD outcome
    payment_data = {
        'payment_id': payment_id,
        'invoice_id': ipn_data.get('invoice_id'),
        'order_id': order_id,
        'pay_address': ipn_data.get('pay_address'),
        'payment_status': payment_status,
        'pay_amount': ipn_data.get('pay_amount'),
        'pay_currency': ipn_data.get('pay_currency'),
        'outcome_amount': outcome_amount,
        'price_amount': ipn_data.get('price_amount'),
        'price_currency': ipn_data.get('price_currency'),
        'outcome_currency': outcome_currency,
        'outcome_amount_usd': outcome_amount_usd  # NEW: USD value
    }

    # Update database (enhanced query with outcome_amount_usd)
    cur.execute("""
        UPDATE private_channel_users_database
        SET
            nowpayments_payment_id = %s,
            nowpayments_invoice_id = %s,
            nowpayments_order_id = %s,
            nowpayments_pay_address = %s,
            nowpayments_payment_status = %s,
            nowpayments_pay_amount = %s,
            nowpayments_pay_currency = %s,
            nowpayments_outcome_amount = %s,
            nowpayments_price_amount = %s,
            nowpayments_price_currency = %s,
            nowpayments_outcome_currency = %s,
            nowpayments_outcome_amount_usd = %s,
            nowpayments_updated_at = CURRENT_TIMESTAMP
        WHERE user_id = %s AND private_channel_id = %s
        AND id = (
            SELECT id FROM private_channel_users_database
            WHERE user_id = %s AND private_channel_id = %s
            ORDER BY id DESC LIMIT 1
        )
    """, (
        payment_id,
        ipn_data.get('invoice_id'),
        order_id,
        ipn_data.get('pay_address'),
        payment_status,
        ipn_data.get('pay_amount'),
        ipn_data.get('pay_currency'),
        outcome_amount,
        ipn_data.get('price_amount'),
        ipn_data.get('price_currency'),
        outcome_currency,
        outcome_amount_usd,  # NEW
        user_id,
        closed_channel_id,
        user_id,
        closed_channel_id
    ))

    conn.commit()
    cur.close()
    conn.close()

    print(f"✅ [DATABASE] Updated with outcome_amount_usd: ${outcome_amount_usd:.2f}")

    # Trigger GCWebhook1 for orchestration
    print(f"")
    print(f"🚀 [ORCHESTRATION] Triggering GCWebhook1 for payment processing...")

    try:
        task_name = cloudtasks_client.enqueue_gcwebhook1_validated_payment(
            queue_name=GCWEBHOOK1_QUEUE,
            target_url=f"{GCWEBHOOK1_URL}/process-validated-payment",
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            subscription_time_days=subscription_time_days,
            subscription_price=subscription_price,
            outcome_amount_usd=outcome_amount_usd,
            nowpayments_payment_id=payment_id,
            nowpayments_pay_address=ipn_data.get('pay_address'),
            nowpayments_outcome_amount=outcome_amount
        )

        if task_name:
            print(f"✅ [ORCHESTRATION] Enqueued to GCWebhook1")
            print(f"🆔 [ORCHESTRATION] Task: {task_name}")
        else:
            print(f"❌ [ORCHESTRATION] Failed to enqueue to GCWebhook1")

    except Exception as e:
        print(f"❌ [ORCHESTRATION] Error queuing to GCWebhook1: {e}")

    print(f"")
    print(f"✅ [IPN] IPN processed successfully")
    print(f"=" * 80)

    return jsonify({"status": "success"}), 200
```

---

### Phase 3: CloudTasks Client Enhancement

**Add new method for triggering GCWebhook1**

```python
# np-webhook-10-26/cloudtasks_client.py

class CloudTasksClient:
    def __init__(self, project_id: str, location: str):
        self.project_id = project_id
        self.location = location
        self.client = tasks_v2.CloudTasksClient()

    def enqueue_gcwebhook1_validated_payment(
        self,
        queue_name: str,
        target_url: str,
        user_id: int,
        closed_channel_id: int,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        subscription_time_days: int,
        subscription_price: float,
        outcome_amount_usd: float,
        nowpayments_payment_id: str,
        nowpayments_pay_address: str,
        nowpayments_outcome_amount: float
    ) -> Optional[str]:
        """
        Enqueue validated payment to GCWebhook1 for orchestration.

        Args:
            All payment and payout configuration data
            outcome_amount_usd: ACTUAL USD value from CoinGecko

        Returns:
            Task name if successful, None otherwise
        """
        try:
            payload = {
                "user_id": user_id,
                "closed_channel_id": closed_channel_id,
                "wallet_address": wallet_address,
                "payout_currency": payout_currency,
                "payout_network": payout_network,
                "subscription_time_days": subscription_time_days,
                "subscription_price": subscription_price,
                "outcome_amount_usd": outcome_amount_usd,  # CRITICAL
                "nowpayments_payment_id": nowpayments_payment_id,
                "nowpayments_pay_address": nowpayments_pay_address,
                "nowpayments_outcome_amount": nowpayments_outcome_amount
            }

            parent = self.client.queue_path(self.project_id, self.location, queue_name)

            task = {
                'http_request': {
                    'http_method': tasks_v2.HttpMethod.POST,
                    'url': target_url,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(payload).encode()
                }
            }

            response = self.client.create_task(request={"parent": parent, "task": task})

            print(f"✅ [CLOUDTASKS] Task created: {response.name}")
            return response.name

        except Exception as e:
            print(f"❌ [CLOUDTASKS] Failed to create task: {e}")
            return None
```

---

### Phase 4: Database Schema Enhancement

**Add `nowpayments_outcome_amount_usd` column**

```sql
-- Add outcome USD amount column
ALTER TABLE private_channel_users_database
ADD COLUMN IF NOT EXISTS nowpayments_outcome_amount_usd DECIMAL(20, 8);

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_nowpayments_payment_id
ON private_channel_users_database(nowpayments_payment_id);

-- Add comment for documentation
COMMENT ON COLUMN private_channel_users_database.nowpayments_outcome_amount_usd IS
'Actual USD value of outcome_amount calculated via CoinGecko API at time of IPN callback';
```

---

### Phase 5: Remove Old success_url Logic from GCWebhook1

**Deprecate the GET / endpoint that processes success_url**

The old flow where GCWebhook1 receives success_url and immediately queues payments is no longer needed. We have two options:

**Option A: Complete Removal**
- Remove GET / endpoint entirely
- All processing goes through `/process-validated-payment`

**Option B: Gradual Migration**
- Keep GET / endpoint but only for database writes
- Remove all queuing logic from GET /
- Log warning that it's deprecated

**Recommended: Option B for safety**

```python
# GCWebhook1-10-26/tph1-10-26.py

@app.route("/", methods=["GET"])
def process_payment():
    """
    DEPRECATED: Legacy success_url endpoint.

    This endpoint is maintained only for backward compatibility during migration.
    It now ONLY writes to database and does NOT queue any payments.

    All payment processing is handled by /process-validated-payment endpoint
    triggered by np-webhook after IPN validation.
    """
    try:
        print(f"⚠️ [DEPRECATED] Legacy success_url endpoint called")
        print(f"ℹ️ [DEPRECATED] This endpoint no longer queues payments")

        # Extract and decode token
        token = request.args.get("token")
        if not token:
            abort(400, "Missing token")

        user_id, closed_channel_id, wallet_address, payout_currency, \
        payout_network, subscription_time_days, subscription_price = \
            token_manager.decode_and_verify_token(token)

        # Calculate expiration
        expire_time, expire_date = calculate_expiration_time(subscription_time_days)

        # ONLY write to database - NO queuing
        success = db_manager.record_private_channel_user(
            user_id=user_id,
            private_channel_id=closed_channel_id,
            sub_time=subscription_time_days,
            sub_price=subscription_price,
            expire_time=expire_time,
            expire_date=expire_date,
            is_active=True
        )

        if success:
            print(f"✅ [DEPRECATED] Database record created")
            print(f"ℹ️ [DEPRECATED] Waiting for IPN validation to trigger payment processing")

        return jsonify({
            "status": "ok",
            "message": "Record created, awaiting IPN validation"
        }), 200

    except Exception as e:
        print(f"❌ [DEPRECATED] Error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

---

## Configuration Requirements

### NP-Webhook Environment Variables

**New secrets required in Secret Manager:**

```bash
# Cloud Tasks Configuration
CLOUD_TASKS_PROJECT_ID=telepay-459221
CLOUD_TASKS_LOCATION=us-central1

# GCWebhook1 Queue Configuration
GCWEBHOOK1_QUEUE=gcwebhook1-queue
GCWEBHOOK1_URL=https://gcwebhook1-10-26-291176869049.us-central1.run.app
```

**Update np-webhook deployment:**

```bash
# Create secrets
gcloud secrets create GCWEBHOOK1_QUEUE --data-file=- <<< "gcwebhook1-queue"
gcloud secrets create GCWEBHOOK1_URL --data-file=- <<< "https://gcwebhook1-10-26-291176869049.us-central1.run.app"

# Update Cloud Run service
gcloud run services update np-webhook-10-26 \
  --region=us-central1 \
  --update-secrets=GCWEBHOOK1_QUEUE=GCWEBHOOK1_QUEUE:latest \
  --update-secrets=GCWEBHOOK1_URL=GCWEBHOOK1_URL:latest
```

---

## Implementation Checklist

### Phase 1: Database Preparation
- [ ] Add `nowpayments_outcome_amount_usd` column
- [ ] Add index on `nowpayments_payment_id`
- [ ] Verify column can store decimal values with 8 decimal places
- [ ] Test database update query with new column

### Phase 2: NP-Webhook Enhancement
- [ ] Add `requests` library to requirements.txt
- [ ] Implement `get_crypto_usd_price()` function
- [ ] Copy `cloudtasks_client.py` to `np-webhook-10-26/`
- [ ] Implement `enqueue_gcwebhook1_validated_payment()` method
- [ ] Update IPN handler to calculate outcome USD amount
- [ ] Update IPN handler to trigger GCWebhook1
- [ ] Test CoinGecko API integration
- [ ] Test Cloud Tasks queueing

### Phase 3: GCWebhook1 New Endpoint
- [ ] Create `/process-validated-payment` endpoint
- [ ] Implement payout mode routing logic
- [ ] Implement GCSplit1 queuing with outcome USD
- [ ] Implement GCAccumulator queuing with outcome USD
- [ ] Implement Telegram invite queuing
- [ ] Add comprehensive logging
- [ ] Test endpoint with mock data

### Phase 4: Secret Manager Configuration
- [ ] Create GCWEBHOOK1_QUEUE secret
- [ ] Create GCWEBHOOK1_URL secret
- [ ] Grant np-webhook access to new secrets
- [ ] Update np-webhook deployment with new secrets
- [ ] Verify secrets are accessible

### Phase 5: Deprecate Old Flow
- [ ] Update GCWebhook1 GET / endpoint
- [ ] Remove payment queuing logic
- [ ] Add deprecation warnings
- [ ] Update documentation
- [ ] Test backward compatibility

### Phase 6: Deployment
- [ ] Deploy updated np-webhook-10-26
- [ ] Deploy updated gcwebhook1-10-26
- [ ] Monitor logs for first payment
- [ ] Verify IPN → CoinGecko → GCWebhook1 flow
- [ ] Verify outcome USD amount calculation
- [ ] Verify payment queuing with correct amounts

### Phase 7: Testing & Validation
- [ ] Create test payment
- [ ] Verify IPN callback received
- [ ] Verify CoinGecko price fetch
- [ ] Verify outcome USD calculation
- [ ] Verify GCWebhook1 triggered
- [ ] Verify payout mode determination
- [ ] Verify GCSplit1/GCAccumulator queued with correct amount
- [ ] Compare outcome amount vs subscription price

---

## Comparison with Direct Queuing Approach

| Aspect | Direct Queuing (Alt 1) | GCWebhook1 Orchestration (This Doc) |
|--------|------------------------|-------------------------------------|
| **Orchestration Logic** | Split across NP-Webhook | Centralized in GCWebhook1 |
| **Code Changes** | NP-Webhook gets complex | NP-Webhook stays focused |
| **Future Extensibility** | Must update NP-Webhook | Only update GCWebhook1 |
| **Debugging** | Check multiple services | Single orchestrator to debug |
| **Testing** | Test business logic in webhook | Test routing independently |
| **Separation of Concerns** | Mixed validation & routing | Clean separation |
| **Pattern Consistency** | New pattern | Existing pattern (GCWebhook1 as orchestrator) |

**Recommendation:** GCWebhook1 Orchestration approach is superior for long-term maintainability and architectural clarity.

---

## Flow Timeline Example

```
T+0s:   User completes payment on NowPayments
T+10s:  NowPayments confirms payment
T+15s:  NowPayments sends IPN to np-webhook
T+16s:  np-webhook validates signature ✓
T+17s:  np-webhook fetches CoinGecko price: ETH = $3,902.76
T+18s:  np-webhook calculates: 0.00026932 ETH = $1.05 USD
T+19s:  np-webhook updates DB: nowpayments_outcome_amount_usd = 1.05
T+20s:  np-webhook queues task to GCWebhook1
T+21s:  GCWebhook1 receives validated payment data
T+22s:  GCWebhook1 looks up payout mode: "instant"
T+23s:  GCWebhook1 queues GCSplit1 with sub_price=1.05 ✅
T+24s:  GCWebhook1 queues Telegram invite to GCWebhook2
T+25s:  GCSplit1 processes payment with ACTUAL amount
```

---

## Error Handling & Recovery

### Scenario 1: CoinGecko API Failure

**Problem:** CoinGecko API is down or rate-limited

**Solution:**
```python
if not crypto_usd_price:
    print(f"⚠️ [FALLBACK] CoinGecko unavailable, using subscription price")
    outcome_amount_usd = subscription_price
    # Log warning for manual review
```

### Scenario 2: GCWebhook1 Queue Failure

**Problem:** Cloud Tasks fails to enqueue to GCWebhook1

**Solution:**
- NP-Webhook stores outcome_amount_usd in database
- Manual retry script can lookup and reprocess
- Alert monitoring on consecutive failures

### Scenario 3: IPN Never Arrives

**Problem:** NowPayments IPN is delayed or lost

**Solution:**
- Implement payment status polling
- After 30 minutes, query NowPayments API for payment status
- If confirmed, manually trigger IPN processing

---

## Success Metrics

### Accuracy
- 100% of payments have nowpayments_outcome_amount_usd populated
- < 1% difference between outcome USD and CoinGecko calculation
- 0 payments processed with subscription_price instead of outcome

### Performance
- < 5 seconds from IPN to GCWebhook1 queuing
- < 30 seconds end-to-end from IPN to GCSplit1/GCAccumulator
- 99.9% uptime for CoinGecko fetching

### Reliability
- 100% of validated IPNs trigger GCWebhook1
- 0 race conditions between success_url and IPN
- 0 duplicate payment processing

---

## Migration Strategy

### Week 1: Preparation
- Add database column
- Deploy NP-Webhook with CoinGecko integration (passive mode)
- Monitor outcome USD calculations without triggering

### Week 2: Soft Launch
- Deploy GCWebhook1 new endpoint
- Enable NP-Webhook → GCWebhook1 queuing for 10% of traffic
- Compare outcomes between old and new flows

### Week 3: Full Migration
- Enable for 100% of traffic
- Deprecate old success_url processing
- Monitor for issues

### Week 4: Cleanup
- Remove deprecated code
- Update documentation
- Archive old flow documentation

---

## Conclusion

This architecture maintains **GCWebhook1 as the central orchestrator** while leveraging NP-Webhook for validation and pricing. This approach:

1. **Preserves architectural patterns** - GCWebhook1 remains the decision-maker
2. **Separates concerns** - Each service has a clear, focused responsibility
3. **Enables extensibility** - Easy to add new payout modes or business logic
4. **Improves accuracy** - All payments use actual received amounts
5. **Simplifies debugging** - Clear flow with single orchestration point

The event-driven design ensures payments are processed with **real outcome amounts** while keeping the codebase clean, testable, and maintainable.
