# NowPayments Outcome Amount - GCWebhook1 Architecture Implementation Checklist

## Overview

This checklist implements the architecture defined in `NOWPAYMENTS_OUTCOME_AMOUNT_GCWEBHOOK1_ARCHITECTURE.md` to ensure payment processing uses **actual outcome amounts** from CoinGecko instead of declared subscription prices.

**Critical Goal:** Replace `subscription_price` with `outcome_amount_usd` (actual crypto value in USD) throughout the payment processing pipeline.

---

## Pre-Implementation Verification

### ☑️ Phase 0: Environment Readiness
- [ ] Verify database access to `telepaypsql` instance
- [ ] Verify current GCWebhook1 service URL: `https://gcwebhook1-10-26-291176869049.us-central1.run.app`
- [ ] Verify current np-webhook service URL
- [ ] Confirm Cloud Tasks API is enabled
- [ ] Confirm Secret Manager API is enabled
- [ ] Backup current production database
- [ ] Document current service versions

---

## Phase 1: Database Schema Changes

### ☑️ Step 1.1: Add New Column to Database

**File:** N/A (Direct database modification)

**Action:** Add `nowpayments_outcome_amount_usd` column to store actual USD value

```sql
-- Connect to database
-- psql -h /cloudsql/telepay-459221:us-central1:telepaypsql -U postgres -d telepaydb

-- Add new column for outcome USD amount
ALTER TABLE private_channel_users_database
ADD COLUMN IF NOT EXISTS nowpayments_outcome_amount_usd DECIMAL(20, 8);

-- Verify column was added
\d private_channel_users_database

-- Should see: nowpayments_outcome_amount_usd | numeric(20,8) |
```

**Verification:**
- [ ] Column `nowpayments_outcome_amount_usd` exists
- [ ] Column type is `DECIMAL(20, 8)` (supports 8 decimal places)
- [ ] Column allows NULL values (for backward compatibility)

---

### ☑️ Step 1.2: Add Database Index for Performance

**Action:** Add index on `nowpayments_payment_id` for faster lookups

```sql
-- Add index for faster payment_id lookups
CREATE INDEX IF NOT EXISTS idx_nowpayments_payment_id
ON private_channel_users_database(nowpayments_payment_id);

-- Verify index was created
\di idx_nowpayments_payment_id

-- Should show the index on nowpayments_payment_id column
```

**Verification:**
- [ ] Index `idx_nowpayments_payment_id` exists
- [ ] Index is on column `nowpayments_payment_id`

---

### ☑️ Step 1.3: Add Column Documentation

**Action:** Add comment explaining the new column

```sql
-- Add documentation comment
COMMENT ON COLUMN private_channel_users_database.nowpayments_outcome_amount_usd IS
'Actual USD value of outcome_amount calculated via CoinGecko API at time of IPN callback. This is the REAL amount received, not the declared subscription price.';

-- Verify comment was added
SELECT
    column_name,
    data_type,
    col_description('private_channel_users_database'::regclass, ordinal_position) as column_comment
FROM information_schema.columns
WHERE table_name = 'private_channel_users_database'
AND column_name = 'nowpayments_outcome_amount_usd';
```

**Verification:**
- [ ] Column comment exists
- [ ] Comment accurately describes the column purpose

---

## Phase 2: NP-Webhook Enhancements

### ☑️ Step 2.1: Update requirements.txt

**File:** `/OCTOBER/10-26/np-webhook-10-26/requirements.txt`

**Action:** Add required libraries

**Current Content:**
```
Flask==3.0.3
google-cloud-secret-manager==2.20.0
cloud-sql-python-connector[pg8000]==1.14.0
pg8000==1.31.2
```

**Add:**
```
requests==2.31.0
google-cloud-tasks==2.16.3
```

**New Content:**
```
Flask==3.0.3
google-cloud-secret-manager==2.20.0
cloud-sql-python-connector[pg8000]==1.14.0
pg8000==1.31.2
requests==2.31.0
google-cloud-tasks==2.16.3
```

**Verification:**
- [ ] `requests` library added for CoinGecko API calls
- [ ] `google-cloud-tasks` library added for Cloud Tasks integration
- [ ] Version numbers specified for reproducibility

---

### ☑️ Step 2.2: Create CloudTasks Client for NP-Webhook

**File:** `/OCTOBER/10-26/np-webhook-10-26/cloudtasks_client.py` (NEW FILE)

**Action:** Create new file with Cloud Tasks client

**Content:**
```python
#!/usr/bin/env python
"""
CloudTasks Client for NP-Webhook
Handles queuing validated payments to GCWebhook1 for orchestration.
"""
import json
from typing import Optional
from google.cloud import tasks_v2

class CloudTasksClient:
    """Client for creating Cloud Tasks to GCWebhook1."""

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: GCP project ID
            location: GCP location (e.g., 'us-central1')
        """
        self.project_id = project_id
        self.location = location
        self.client = tasks_v2.CloudTasksClient()
        print(f"✅ [CLOUDTASKS] Client initialized for project: {project_id}, location: {location}")

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

        This method sends ALL payment configuration data plus the CRITICAL
        outcome_amount_usd field to GCWebhook1 for payout routing decisions.

        Args:
            queue_name: Cloud Tasks queue name
            target_url: GCWebhook1 endpoint URL (should include /process-validated-payment)
            user_id: Telegram user ID
            closed_channel_id: Private channel ID
            wallet_address: User's payout wallet address
            payout_currency: Currency for payout (e.g., 'USDT')
            payout_network: Network for payout (e.g., 'trc20')
            subscription_time_days: Subscription duration in days
            subscription_price: Original declared subscription price
            outcome_amount_usd: ACTUAL USD value from CoinGecko (CRITICAL)
            nowpayments_payment_id: NowPayments payment ID
            nowpayments_pay_address: NowPayments payment address
            nowpayments_outcome_amount: Outcome amount in crypto

        Returns:
            Task name if successful, None otherwise
        """
        try:
            print(f"")
            print(f"🚀 [CLOUDTASKS] Creating task to GCWebhook1...")
            print(f"   Queue: {queue_name}")
            print(f"   Target: {target_url}")
            print(f"   User ID: {user_id}")
            print(f"   Channel ID: {closed_channel_id}")
            print(f"   💰 Outcome USD: ${outcome_amount_usd:.2f}")

            # Build payload with ALL required data
            payload = {
                "user_id": user_id,
                "closed_channel_id": closed_channel_id,
                "wallet_address": wallet_address,
                "payout_currency": payout_currency,
                "payout_network": payout_network,
                "subscription_time_days": subscription_time_days,
                "subscription_price": subscription_price,
                "outcome_amount_usd": outcome_amount_usd,  # CRITICAL FIELD
                "nowpayments_payment_id": nowpayments_payment_id,
                "nowpayments_pay_address": nowpayments_pay_address,
                "nowpayments_outcome_amount": nowpayments_outcome_amount
            }

            # Get queue path
            parent = self.client.queue_path(self.project_id, self.location, queue_name)

            # Create task
            task = {
                'http_request': {
                    'http_method': tasks_v2.HttpMethod.POST,
                    'url': target_url,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(payload).encode()
                }
            }

            # Submit task
            response = self.client.create_task(request={"parent": parent, "task": task})

            print(f"✅ [CLOUDTASKS] Task created successfully")
            print(f"🆔 [CLOUDTASKS] Task name: {response.name}")
            return response.name

        except Exception as e:
            print(f"❌ [CLOUDTASKS] Failed to create task: {e}")
            import traceback
            traceback.print_exc()
            return None
```

**Verification:**
- [ ] File created at `/OCTOBER/10-26/np-webhook-10-26/cloudtasks_client.py`
- [ ] `CloudTasksClient` class defined
- [ ] `enqueue_gcwebhook1_validated_payment` method implemented
- [ ] Method includes all required parameters
- [ ] `outcome_amount_usd` parameter is prominently marked as CRITICAL

---

### ☑️ Step 2.3: Add CoinGecko Price Fetching Function

**File:** `/OCTOBER/10-26/np-webhook-10-26/app.py`

**Action:** Add function to fetch crypto prices from CoinGecko

**Location:** Add after imports, before `handle_ipn()` function

**Code to Add:**
```python
def get_crypto_usd_price(crypto_symbol: str) -> Optional[float]:
    """
    Fetch current USD price for a cryptocurrency from CoinGecko API.

    Args:
        crypto_symbol: Cryptocurrency symbol (e.g., 'ETH', 'BTC')

    Returns:
        Current USD price or None if fetch fails
    """
    import requests

    # Map common symbols to CoinGecko IDs
    coin_id_map = {
        'ETH': 'ethereum',
        'BTC': 'bitcoin',
        'USDT': 'tether',
        'USDC': 'usd-coin',
        'LTC': 'litecoin',
        'TRX': 'tron',
        'BNB': 'binancecoin',
        'SOL': 'solana',
        'MATIC': 'matic-network'
    }

    coin_id = coin_id_map.get(crypto_symbol.upper())
    if not coin_id:
        print(f"❌ [PRICE] Unsupported crypto symbol: {crypto_symbol}")
        print(f"💡 [PRICE] Supported symbols: {', '.join(coin_id_map.keys())}")
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
            print(f"❌ [PRICE] Price not found in CoinGecko response")
            return None

    except requests.exceptions.Timeout:
        print(f"❌ [PRICE] CoinGecko API timeout after 10 seconds")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ [PRICE] Failed to fetch price from CoinGecko: {e}")
        return None
    except Exception as e:
        print(f"❌ [PRICE] Unexpected error fetching price: {e}")
        return None
```

**Verification:**
- [ ] Function `get_crypto_usd_price()` added to `app.py`
- [ ] Function is placed before `handle_ipn()` function
- [ ] Supports common cryptocurrencies (ETH, BTC, USDT, etc.)
- [ ] Includes proper error handling
- [ ] Has 10-second timeout for API calls

---

### ☑️ Step 2.4: Initialize Cloud Tasks Client in NP-Webhook

**File:** `/OCTOBER/10-26/np-webhook-10-26/app.py`

**Action:** Import and initialize Cloud Tasks client

**Location:** Add after database configuration section (around line 65)

**Code to Add:**
```python
# ============================================================================
# CLOUD TASKS INITIALIZATION
# ============================================================================

print(f"")
print(f"⚙️ [CONFIG] Loading Cloud Tasks configuration...")

# Cloud Tasks configuration for triggering GCWebhook1
CLOUD_TASKS_PROJECT_ID = os.getenv('CLOUD_TASKS_PROJECT_ID')
CLOUD_TASKS_LOCATION = os.getenv('CLOUD_TASKS_LOCATION')
GCWEBHOOK1_QUEUE = os.getenv('GCWEBHOOK1_QUEUE')
GCWEBHOOK1_URL = os.getenv('GCWEBHOOK1_URL')

print(f"   CLOUD_TASKS_PROJECT_ID: {'✅ Loaded' if CLOUD_TASKS_PROJECT_ID else '❌ Missing'}")
print(f"   CLOUD_TASKS_LOCATION: {'✅ Loaded' if CLOUD_TASKS_LOCATION else '❌ Missing'}")
print(f"   GCWEBHOOK1_QUEUE: {'✅ Loaded' if GCWEBHOOK1_QUEUE else '❌ Missing'}")
print(f"   GCWEBHOOK1_URL: {'✅ Loaded' if GCWEBHOOK1_URL else '❌ Missing'}")

# Initialize Cloud Tasks client
cloudtasks_client = None
if all([CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION]):
    try:
        from cloudtasks_client import CloudTasksClient
        cloudtasks_client = CloudTasksClient(CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION)
        print(f"✅ [CLOUDTASKS] Client initialized successfully")
    except Exception as e:
        print(f"❌ [CLOUDTASKS] Failed to initialize client: {e}")
        print(f"⚠️ [CLOUDTASKS] GCWebhook1 triggering will not work!")
else:
    print(f"⚠️ [CLOUDTASKS] Skipping initialization - missing configuration")
    print(f"⚠️ [CLOUDTASKS] GCWebhook1 will NOT be triggered after IPN validation!")

print(f"")
```

**Verification:**
- [ ] Cloud Tasks client initialization code added
- [ ] Environment variables loaded and logged
- [ ] Client initialized conditionally (only if config present)
- [ ] Errors are logged but don't crash the service

---

### ☑️ Step 2.5: Enhance IPN Handler with Outcome USD Calculation

**File:** `/OCTOBER/10-26/np-webhook-10-26/app.py`

**Function:** `handle_ipn()` (existing function)

**Action:** Add outcome USD calculation and GCWebhook1 triggering

**Location:** After database update (around line 435), BEFORE the final return statement

**Code to Add:**
```python
    # ============================================================================
    # NEW: Calculate Outcome Amount in USD using CoinGecko
    # ============================================================================
    print(f"")
    print(f"💱 [CONVERSION] Calculating USD value of outcome amount...")

    outcome_amount_usd = None

    # Check if outcome is already in USD/stablecoin
    if outcome_currency.upper() in ['USDT', 'USDC', 'USD', 'BUSD', 'DAI']:
        # Already in USD equivalent - no conversion needed
        outcome_amount_usd = float(outcome_amount)
        print(f"✅ [CONVERSION] Already in USD equivalent: ${outcome_amount_usd:.2f}")
    else:
        # Fetch current market price from CoinGecko
        crypto_usd_price = get_crypto_usd_price(outcome_currency)

        if crypto_usd_price:
            # Calculate USD value
            outcome_amount_usd = float(outcome_amount) * crypto_usd_price
            print(f"💰 [CONVERT] {outcome_amount} {outcome_currency} × ${crypto_usd_price:,.2f}")
            print(f"💰 [CONVERT] = ${outcome_amount_usd:.2f} USD")
        else:
            # Fallback: Use declared subscription price if CoinGecko fails
            print(f"❌ [CONVERT] Failed to fetch {outcome_currency} price from CoinGecko")
            print(f"⚠️ [CONVERT] FALLBACK: Using declared subscription price")
            outcome_amount_usd = float(subscription_price)

    print(f"💰 [VALIDATION] Final Outcome in USD: ${outcome_amount_usd:.2f}")

    # Update database with outcome_amount_usd
    cur.execute("""
        UPDATE private_channel_users_database
        SET nowpayments_outcome_amount_usd = %s
        WHERE user_id = %s AND private_channel_id = %s
        AND id = (
            SELECT id FROM private_channel_users_database
            WHERE user_id = %s AND private_channel_id = %s
            ORDER BY id DESC LIMIT 1
        )
    """, (outcome_amount_usd, user_id, closed_channel_id, user_id, closed_channel_id))

    conn.commit()
    print(f"✅ [DATABASE] Updated nowpayments_outcome_amount_usd: ${outcome_amount_usd:.2f}")

    # ============================================================================
    # NEW: Trigger GCWebhook1 for Payment Orchestration
    # ============================================================================
    print(f"")
    print(f"🚀 [ORCHESTRATION] Triggering GCWebhook1 for payment processing...")

    if not cloudtasks_client:
        print(f"❌ [ORCHESTRATION] Cloud Tasks client not initialized")
        print(f"⚠️ [ORCHESTRATION] Cannot trigger GCWebhook1 - payment will not be processed!")
    elif not GCWEBHOOK1_QUEUE or not GCWEBHOOK1_URL:
        print(f"❌ [ORCHESTRATION] GCWebhook1 configuration missing")
        print(f"⚠️ [ORCHESTRATION] Cannot trigger GCWebhook1 - payment will not be processed!")
    else:
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
                outcome_amount_usd=outcome_amount_usd,  # CRITICAL: Real amount
                nowpayments_payment_id=payment_id,
                nowpayments_pay_address=ipn_data.get('pay_address'),
                nowpayments_outcome_amount=outcome_amount
            )

            if task_name:
                print(f"✅ [ORCHESTRATION] Successfully enqueued to GCWebhook1")
                print(f"🆔 [ORCHESTRATION] Task: {task_name}")
            else:
                print(f"❌ [ORCHESTRATION] Failed to enqueue to GCWebhook1")
                print(f"⚠️ [ORCHESTRATION] Payment validated but not queued for processing!")

        except Exception as e:
            print(f"❌ [ORCHESTRATION] Error queuing to GCWebhook1: {e}")
            import traceback
            traceback.print_exc()

    print(f"")
```

**Verification:**
- [ ] Code added to `handle_ipn()` function
- [ ] Placed BEFORE the final `return jsonify()` statement
- [ ] Calculates `outcome_amount_usd` using CoinGecko
- [ ] Updates database with USD outcome
- [ ] Triggers GCWebhook1 via Cloud Tasks
- [ ] Includes comprehensive error handling

---

### ☑️ Step 2.6: Update Database UPDATE Query

**File:** `/OCTOBER/10-26/np-webhook-10-26/app.py`

**Function:** `update_payment_data()` or inline UPDATE in `handle_ipn()`

**Action:** Ensure the UPDATE query includes `nowpayments_outcome_amount_usd`

**Find the existing UPDATE query (around line 226-248):**
```python
update_query = """
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
        nowpayments_created_at = CURRENT_TIMESTAMP,
        nowpayments_updated_at = CURRENT_TIMESTAMP
    WHERE user_id = %s AND private_channel_id = %s
    AND id = (
        SELECT id FROM private_channel_users_database
        WHERE user_id = %s AND private_channel_id = %s
        ORDER BY id DESC LIMIT 1
    )
"""
```

**NOTE:** The outcome_amount_usd update is handled in Step 2.5 as a separate UPDATE.
This is intentional to keep the logic clear. No changes needed here.

**Verification:**
- [ ] Existing UPDATE query verified
- [ ] Separate UPDATE for `nowpayments_outcome_amount_usd` added in Step 2.5
- [ ] Both updates use the same WHERE clause

---

## Phase 3: GCWebhook1 Enhancements

### ☑️ Step 3.1: Create New Endpoint for Validated Payments

**File:** `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`

**Action:** Add new `/process-validated-payment` endpoint

**Location:** Add AFTER the existing `@app.route("/", methods=["GET"])` endpoint, BEFORE the health check endpoint

**Code to Add:**
```python
# ============================================================================
# NEW ENDPOINT: POST /process-validated-payment
# Receives validated payment data from NP-Webhook and orchestrates processing
# ============================================================================

@app.route("/process-validated-payment", methods=["POST"])
def process_validated_payment():
    """
    Process a payment that has been validated by np-webhook.

    This endpoint is called by np-webhook AFTER:
    - IPN signature validation
    - CoinGecko price fetch
    - Outcome USD amount calculation
    - Database update with outcome_amount_usd

    Flow:
    1. Receive validated payment data from np-webhook
    2. Extract outcome_amount_usd (ACTUAL USD value)
    3. Lookup payout strategy (instant vs threshold)
    4. Route to GCSplit1 (instant) or GCAccumulator (threshold) with REAL amount
    5. Queue Telegram invite to GCWebhook2

    CRITICAL: This endpoint ensures all payments are processed with
    the ACTUAL crypto outcome value in USD, not the declared subscription price.
    """
    try:
        print(f"")
        print(f"=" * 80)
        print(f"🎯 [VALIDATED] Received validated payment from NP-Webhook")

        # Get validated payment data from NP-Webhook
        payment_data = request.get_json()

        if not payment_data:
            print(f"❌ [VALIDATED] No JSON payload received")
            abort(400, "Missing payment data")

        # Extract all required fields
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

        print(f"")
        print(f"✅ [VALIDATED] Payment Data Received:")
        print(f"   User ID: {user_id}")
        print(f"   Channel ID: {closed_channel_id}")
        print(f"   Wallet: {wallet_address}")
        print(f"   Payout: {payout_currency} on {payout_network}")
        print(f"   Subscription Days: {subscription_time_days}")
        print(f"   Declared Price: ${subscription_price}")
        print(f"   💰 ACTUAL Outcome (USD): ${outcome_amount_usd}")
        print(f"   Payment ID: {nowpayments_payment_id}")

        # Validate required fields
        if not all([user_id, closed_channel_id, outcome_amount_usd]):
            print(f"❌ [VALIDATED] Missing required fields")
            print(f"   user_id: {user_id}")
            print(f"   closed_channel_id: {closed_channel_id}")
            print(f"   outcome_amount_usd: {outcome_amount_usd}")
            abort(400, "Missing required payment data")

        # ========================================================================
        # PAYOUT ROUTING DECISION
        # ========================================================================
        print(f"")
        print(f"🔍 [VALIDATED] Checking payout strategy for channel {closed_channel_id}")

        if not db_manager:
            print(f"❌ [VALIDATED] Database manager not available")
            abort(500, "Database unavailable")

        payout_mode, payout_threshold = db_manager.get_payout_strategy(closed_channel_id)
        print(f"💰 [VALIDATED] Payout mode: {payout_mode}")

        if payout_mode == "threshold":
            print(f"🎯 [VALIDATED] Threshold payout mode - ${payout_threshold} threshold")
            print(f"📊 [VALIDATED] Routing to GCAccumulator for accumulation")

            # Get subscription ID for accumulation record
            subscription_id = db_manager.get_subscription_id(user_id, closed_channel_id)

            # Get GCAccumulator configuration
            gcaccumulator_queue = config.get('gcaccumulator_queue')
            gcaccumulator_url = config.get('gcaccumulator_url')

            if not gcaccumulator_queue or not gcaccumulator_url:
                print(f"❌ [VALIDATED] GCAccumulator configuration missing")
                abort(500, "GCAccumulator configuration error")

            # Queue to GCAccumulator with ACTUAL outcome amount
            print(f"")
            print(f"🚀 [VALIDATED] Queuing to GCAccumulator...")
            print(f"   💰 Using ACTUAL outcome: ${outcome_amount_usd} (not ${subscription_price})")

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
                print(f"✅ [VALIDATED] Successfully enqueued to GCAccumulator")
                print(f"🆔 [VALIDATED] Task: {task_name}")
            else:
                print(f"❌ [VALIDATED] Failed to enqueue to GCAccumulator")
                abort(500, "Failed to enqueue to GCAccumulator")

        else:  # instant payout
            print(f"⚡ [VALIDATED] Instant payout mode - processing immediately")
            print(f"📊 [VALIDATED] Routing to GCSplit1 for payment split")

            # Get GCSplit1 configuration
            gcsplit1_queue = config.get('gcsplit1_queue')
            gcsplit1_url = config.get('gcsplit1_url')

            if not gcsplit1_queue or not gcsplit1_url:
                print(f"❌ [VALIDATED] GCSplit1 configuration missing")
                abort(500, "GCSplit1 configuration error")

            # Queue to GCSplit1 with ACTUAL outcome amount
            print(f"")
            print(f"🚀 [VALIDATED] Queuing to GCSplit1...")
            print(f"   💰 Using ACTUAL outcome: ${outcome_amount_usd} (not ${subscription_price})")

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
                print(f"✅ [VALIDATED] Successfully enqueued to GCSplit1")
                print(f"🆔 [VALIDATED] Task: {task_name}")
            else:
                print(f"❌ [VALIDATED] Failed to enqueue to GCSplit1")
                abort(500, "Failed to enqueue to GCSplit1")

        # ========================================================================
        # TELEGRAM INVITE
        # ========================================================================
        print(f"")
        print(f"📱 [VALIDATED] Queuing Telegram invite to GCWebhook2")

        if not token_manager:
            print(f"❌ [VALIDATED] Token manager not available")
            abort(500, "Token manager unavailable")

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

        if not gcwebhook2_queue or not gcwebhook2_url:
            print(f"⚠️ [VALIDATED] GCWebhook2 configuration missing - skipping invite")
        else:
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

        print(f"")
        print(f"🎉 [VALIDATED] Payment processing completed successfully")
        print(f"=" * 80)

        return jsonify({
            "status": "success",
            "message": "Payment processed with actual outcome amount",
            "outcome_amount_usd": outcome_amount_usd,
            "declared_price": subscription_price,
            "difference": outcome_amount_usd - subscription_price
        }), 200

    except Exception as e:
        print(f"❌ [VALIDATED] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

**Verification:**
- [ ] New endpoint `/process-validated-payment` added
- [ ] Accepts POST requests
- [ ] Extracts `outcome_amount_usd` from payload
- [ ] Routes to GCSplit1 OR GCAccumulator based on payout mode
- [ ] Uses `outcome_amount_usd` instead of `subscription_price` for payments
- [ ] Queues Telegram invite to GCWebhook2
- [ ] Includes comprehensive logging

---

### ☑️ Step 3.2: Deprecate Old GET / Endpoint

**File:** `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`

**Function:** `@app.route("/", methods=["GET"])` - `process_payment()`

**Action:** Remove payment queuing logic, keep database write only

**Find these sections in the existing `process_payment()` function and COMMENT THEM OUT or REMOVE:**

**Section 1: Lines 173-190 - Remove NowPayments lookup (no longer needed)**
```python
# REMOVE OR COMMENT OUT:
        # ============================================================================
        # NEW: Lookup NowPayments payment_id (populated by np-webhook IPN)
        # ============================================================================
        print(f"🔍 [ENDPOINT] Looking up NowPayments payment_id from database")
        nowpayments_data = db_manager.get_nowpayments_data(user_id, closed_channel_id)

        nowpayments_payment_id = None
        nowpayments_pay_address = None
        nowpayments_outcome_amount = None

        if nowpayments_data:
            nowpayments_payment_id = nowpayments_data.get('nowpayments_payment_id')
            nowpayments_pay_address = nowpayments_data.get('nowpayments_pay_address')
            nowpayments_outcome_amount = nowpayments_data.get('nowpayments_outcome_amount')
            print(f"✅ [ENDPOINT] NowPayments payment_id found: {nowpayments_payment_id}")
        else:
            print(f"⚠️ [ENDPOINT] NowPayments payment_id not yet available (IPN may arrive later)")
```

**Section 2: Lines 192-235 - Remove payout strategy routing to GCAccumulator**
```python
# REMOVE OR COMMENT OUT:
        # ============================================================================
        # NEW: Check payout strategy and route accordingly
        # ============================================================================
        print(f"🔍 [ENDPOINT] Checking payout strategy for channel {closed_channel_id}")
        payout_strategy, payout_threshold = db_manager.get_payout_strategy(closed_channel_id)

        print(f"💰 [ENDPOINT] Payout strategy: {payout_strategy}")
        if payout_strategy == 'threshold':
            # ... entire threshold block ...
        else:
            print(f"⚡ [ENDPOINT] Instant payout mode - processing immediately")
```

**Section 3: Lines 282-310 - Remove GCSplit1 queuing**
```python
# REMOVE OR COMMENT OUT:
        # Enqueue payment split to GCSplit1 (ONLY for instant payout)
        if payout_strategy == 'instant':
            print(f"⚡ [ENDPOINT] Routing to GCSplit1 for instant payout")
            # ... entire GCSplit1 queuing block ...
        else:
            print(f"📊 [ENDPOINT] Skipping GCSplit1 - using threshold accumulation instead")
```

**Replace with deprecation notice:**
```python
        # ============================================================================
        # DEPRECATED: Payment queuing removed
        # ============================================================================
        print(f"")
        print(f"⚠️ [DEPRECATED] This endpoint no longer queues payments")
        print(f"ℹ️ [DEPRECATED] Payment processing happens via /process-validated-payment")
        print(f"ℹ️ [DEPRECATED] Triggered by np-webhook after IPN validation")
        print(f"")
```

**Keep these sections:**
- Token decoding
- Expiration calculation
- Database write (`db_manager.record_private_channel_user()`)
- GCWebhook2 Telegram invite queuing (keep this temporarily for testing)

**Verification:**
- [ ] NowPayments lookup section removed
- [ ] Payout strategy routing removed
- [ ] GCSplit1 queuing removed
- [ ] GCAccumulator queuing removed
- [ ] Deprecation notice added
- [ ] Database write still works
- [ ] GCWebhook2 invite still queued (optional - can remove later)

---

## Phase 4: Secret Manager Configuration

### ☑️ Step 4.1: Create GCWEBHOOK1_QUEUE Secret

**Action:** Create Cloud Tasks queue name secret for np-webhook

```bash
# Create secret for GCWebhook1 queue name
gcloud secrets create GCWEBHOOK1_QUEUE \
  --data-file=- <<< "gcwebhook1-queue" \
  --replication-policy="automatic"

# Verify secret created
gcloud secrets versions access latest --secret=GCWEBHOOK1_QUEUE
# Should output: gcwebhook1-queue
```

**Verification:**
- [ ] Secret `GCWEBHOOK1_QUEUE` created
- [ ] Value is `gcwebhook1-queue`
- [ ] Secret is accessible

---

### ☑️ Step 4.2: Create GCWEBHOOK1_URL Secret

**Action:** Create GCWebhook1 service URL secret for np-webhook

```bash
# Create secret for GCWebhook1 URL
gcloud secrets create GCWEBHOOK1_URL \
  --data-file=- <<< "https://gcwebhook1-10-26-291176869049.us-central1.run.app" \
  --replication-policy="automatic"

# Verify secret created
gcloud secrets versions access latest --secret=GCWEBHOOK1_URL
# Should output: https://gcwebhook1-10-26-291176869049.us-central1.run.app
```

**Verification:**
- [ ] Secret `GCWEBHOOK1_URL` created
- [ ] Value is correct GCWebhook1 service URL
- [ ] URL format is valid (https://)

---

### ☑️ Step 4.3: Create CLOUD_TASKS_PROJECT_ID Secret

**Action:** Create Cloud Tasks project ID secret for np-webhook

```bash
# Create secret for Cloud Tasks project ID
gcloud secrets create CLOUD_TASKS_PROJECT_ID \
  --data-file=- <<< "telepay-459221" \
  --replication-policy="automatic"

# Verify secret created
gcloud secrets versions access latest --secret=CLOUD_TASKS_PROJECT_ID
# Should output: telepay-459221
```

**Verification:**
- [ ] Secret `CLOUD_TASKS_PROJECT_ID` created
- [ ] Value is `telepay-459221`

---

### ☑️ Step 4.4: Create CLOUD_TASKS_LOCATION Secret

**Action:** Create Cloud Tasks location secret for np-webhook

```bash
# Create secret for Cloud Tasks location
gcloud secrets create CLOUD_TASKS_LOCATION \
  --data-file=- <<< "us-central1" \
  --replication-policy="automatic"

# Verify secret created
gcloud secrets versions access latest --secret=CLOUD_TASKS_LOCATION
# Should output: us-central1
```

**Verification:**
- [ ] Secret `CLOUD_TASKS_LOCATION` created
- [ ] Value is `us-central1`

---

### ☑️ Step 4.5: Grant NP-Webhook Access to Secrets

**Action:** Grant np-webhook service account access to new secrets

```bash
# Get the service account email for np-webhook
SERVICE_ACCOUNT=$(gcloud run services describe np-webhook-10-26 \
  --region=us-central1 \
  --format='value(spec.template.spec.serviceAccountName)')

echo "Service Account: $SERVICE_ACCOUNT"

# Grant access to all new secrets
for SECRET in GCWEBHOOK1_QUEUE GCWEBHOOK1_URL CLOUD_TASKS_PROJECT_ID CLOUD_TASKS_LOCATION
do
  echo "Granting access to $SECRET..."
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"
done
```

**Verification:**
- [ ] Service account identified
- [ ] IAM bindings added for all 4 secrets
- [ ] No permission errors

---

## Phase 5: Deployment

### ☑️ Step 5.1: Build and Deploy NP-Webhook

**Action:** Deploy updated np-webhook with CoinGecko and Cloud Tasks support

```bash
# Navigate to np-webhook directory
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26

# Build and deploy
gcloud run deploy np-webhook-10-26 \
  --source . \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars=PORT=8080 \
  --set-secrets=NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,\
GCWEBHOOK1_QUEUE=GCWEBHOOK1_QUEUE:latest,\
GCWEBHOOK1_URL=GCWEBHOOK1_URL:latest

# Wait for deployment to complete
echo "Waiting for deployment..."
sleep 10

# Test health endpoint
curl https://$(gcloud run services describe np-webhook-10-26 \
  --region=us-central1 \
  --format='value(status.url)' | sed 's|https://||')/health
```

**Verification:**
- [ ] Build completed successfully
- [ ] Deployment completed successfully
- [ ] Service is running
- [ ] Health check returns 200
- [ ] All secrets are mounted correctly
- [ ] Logs show Cloud Tasks client initialized

---

### ☑️ Step 5.2: Build and Deploy GCWebhook1

**Action:** Deploy updated gcwebhook1 with new endpoint

```bash
# Navigate to gcwebhook1 directory
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26

# Build and deploy
gcloud run deploy gcwebhook1-10-26 \
  --source . \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars=PORT=8080 \
  --set-secrets=SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,\
GCWEBHOOK2_QUEUE=GCWEBHOOK2_QUEUE:latest,\
GCWEBHOOK2_URL=GCWEBHOOK2_URL:latest,\
GCSPLIT1_QUEUE=GCSPLIT1_QUEUE:latest,\
GCSPLIT1_URL=GCSPLIT1_URL:latest,\
GCACCUMULATOR_QUEUE=GCACCUMULATOR_QUEUE:latest,\
GCACCUMULATOR_URL=GCACCUMULATOR_URL:latest

# Wait for deployment
echo "Waiting for deployment..."
sleep 10

# Test health endpoint
curl https://$(gcloud run services describe gcwebhook1-10-26 \
  --region=us-central1 \
  --format='value(status.url)' | sed 's|https://||')/health
```

**Verification:**
- [ ] Build completed successfully
- [ ] Deployment completed successfully
- [ ] Service is running
- [ ] Health check returns 200
- [ ] New endpoint `/process-validated-payment` is accessible

---

### ☑️ Step 5.3: Verify Service Communication

**Action:** Test that np-webhook can reach gcwebhook1

```bash
# Get service URLs
NP_WEBHOOK_URL=$(gcloud run services describe np-webhook-10-26 \
  --region=us-central1 \
  --format='value(status.url)')

GCWEBHOOK1_URL=$(gcloud run services describe gcwebhook1-10-26 \
  --region=us-central1 \
  --format='value(status.url)')

echo "NP-Webhook URL: $NP_WEBHOOK_URL"
echo "GCWebhook1 URL: $GCWEBHOOK1_URL"

# Test new endpoint exists
curl -X POST $GCWEBHOOK1_URL/process-validated-payment \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "closed_channel_id": 456, "outcome_amount_usd": 1.05}'

# Should return error about missing fields, but endpoint should exist
```

**Verification:**
- [ ] Both services are accessible
- [ ] `/process-validated-payment` endpoint exists
- [ ] Endpoint returns 400 for test data (expected)
- [ ] No 404 or 500 errors

---

## Phase 6: Testing & Validation

### ☑️ Step 6.1: Monitor Logs During Test Payment

**Action:** Set up log streaming before test

```bash
# Open 3 terminal windows/tabs:

# Terminal 1: NP-Webhook logs
gcloud run services logs tail np-webhook-10-26 --region=us-central1

# Terminal 2: GCWebhook1 logs
gcloud run services logs tail gcwebhook1-10-26 --region=us-central1

# Terminal 3: GCSplit1 logs (for instant payout test)
gcloud run services logs tail gcsplit1-10-26 --region=us-central1
```

**Verification:**
- [ ] All log streams active
- [ ] Ready to monitor test payment

---

### ☑️ Step 6.2: Create Test Payment

**Action:** Create a real test payment via Telegram bot

1. Open Telegram bot
2. Subscribe to a test channel
3. Complete payment with NowPayments (use small amount)
4. Monitor all log streams

**Verification:**
- [ ] NP-Webhook receives IPN callback
- [ ] IPN signature validated
- [ ] CoinGecko price fetched (check for "💰 [PRICE] ETH/USD = $...")
- [ ] Outcome USD calculated (check for "💰 [CONVERT] X ETH = $Y USD")
- [ ] Database updated with `nowpayments_outcome_amount_usd`
- [ ] GCWebhook1 triggered (check for "🚀 [ORCHESTRATION]")
- [ ] GCWebhook1 receives validated payment
- [ ] Payout mode determined
- [ ] GCSplit1/GCAccumulator queued with correct amount
- [ ] Telegram invite sent

---

### ☑️ Step 6.3: Verify Database Record

**Action:** Check database for complete payment record

```bash
# Query the payment record
gcloud sql connect telepaypsql --user=postgres --database=telepaydb

# In psql:
SELECT
    id,
    user_id,
    private_channel_id,
    subscription_price as declared_price,
    nowpayments_outcome_amount as outcome_crypto,
    nowpayments_outcome_currency as crypto_currency,
    nowpayments_outcome_amount_usd as outcome_usd,
    (nowpayments_outcome_amount_usd - subscription_price) as difference
FROM private_channel_users_database
WHERE nowpayments_payment_id IS NOT NULL
ORDER BY id DESC
LIMIT 5;
```

**Verification:**
- [ ] `nowpayments_outcome_amount_usd` is populated
- [ ] Value is different from `subscription_price` (due to market rate)
- [ ] Value is reasonable (within expected range)
- [ ] All NowPayments fields populated

---

### ☑️ Step 6.4: Compare Amounts

**Action:** Verify outcome USD is being used for payouts

**Check logs for this pattern:**
```
NP-Webhook:
💰 [CONVERT] 0.00026932 ETH = $1.05 USD

GCWebhook1:
💰 Using ACTUAL outcome: $1.05 (not $1.28)

GCSplit1:
📊 [SPLIT] Total amount: $1.05
```

**Verification:**
- [ ] Outcome USD calculated correctly
- [ ] GCWebhook1 uses outcome USD (not subscription price)
- [ ] GCSplit1 receives outcome USD
- [ ] Amounts match throughout pipeline

---

### ☑️ Step 6.5: Test Error Handling

**Action:** Test fallback scenarios

**Scenario 1: CoinGecko API Failure**
- Temporarily block CoinGecko API (firewall rule or wait for rate limit)
- Create test payment
- Verify fallback to subscription_price
- Check for warning logs

**Scenario 2: Cloud Tasks Failure**
- Verify error logging if Cloud Tasks fails
- Verify payment data still stored in database
- Verify manual retry is possible

**Verification:**
- [ ] Fallback to subscription_price works when CoinGecko fails
- [ ] Errors are logged clearly
- [ ] System doesn't crash on API failures
- [ ] Database always updated

---

## Phase 7: Monitoring & Alerts

### ☑️ Step 7.1: Create Log-Based Metrics

**Action:** Create metrics to monitor the new flow

```bash
# Metric 1: CoinGecko price fetch success rate
gcloud logging metrics create coingecko_price_fetch_success \
  --description="Successful CoinGecko price fetches" \
  --log-filter='resource.type="cloud_run_revision"
resource.labels.service_name="np-webhook-10-26"
textPayload=~"PRICE.*USD ="'

# Metric 2: GCWebhook1 validated payment processing
gcloud logging metrics create gcwebhook1_validated_payments \
  --description="Payments processed via validated endpoint" \
  --log-filter='resource.type="cloud_run_revision"
resource.labels.service_name="gcwebhook1-10-26"
textPayload=~"VALIDATED.*Received validated payment"'

# Metric 3: Outcome USD vs Declared Price difference
gcloud logging metrics create payment_amount_discrepancy \
  --description="Difference between outcome and declared price" \
  --log-filter='resource.type="cloud_run_revision"
textPayload=~"difference"'
```

**Verification:**
- [ ] Metrics created successfully
- [ ] Metrics appear in Cloud Monitoring
- [ ] Metrics start collecting data

---

### ☑️ Step 7.2: Verify Old Flow is Deprecated

**Action:** Ensure old GET / endpoint no longer processes payments

**Check logs for:**
```
⚠️ [DEPRECATED] Legacy success_url endpoint called
ℹ️ [DEPRECATED] This endpoint no longer queues payments
```

**Verification:**
- [ ] Old endpoint still creates database records
- [ ] Old endpoint no longer queues to GCSplit1/GCAccumulator
- [ ] Deprecation warnings logged
- [ ] No errors from removed code

---

## Phase 8: Documentation & Rollback Plan

### ☑️ Step 8.1: Update PROGRESS.md

**File:** `/OCTOBER/10-26/PROGRESS.md`

**Action:** Add entry at the TOP of the file

```markdown
## [2025-11-02] NowPayments Outcome Amount - GCWebhook1 Architecture Implementation

### Changes Implemented
- ✅ Added `nowpayments_outcome_amount_usd` column to database
- ✅ Integrated CoinGecko API in np-webhook for real-time crypto pricing
- ✅ Created new `/process-validated-payment` endpoint in GCWebhook1
- ✅ Refactored payment flow: NP-Webhook → GCWebhook1 → GCSplit1/GCAccumulator
- ✅ All payments now use ACTUAL outcome amounts instead of declared prices
- ✅ Deprecated old GET / endpoint in GCWebhook1
- ✅ Added Cloud Tasks integration to np-webhook

### Critical Fix
**Problem:** Payment processing was using `subscription_price` (declared value) instead of actual crypto outcome value in USD.

**Solution:** NP-Webhook now calculates outcome USD via CoinGecko, triggers GCWebhook1, which routes payments with real amounts.

**Impact:** Financial accuracy improved - payouts match actual received crypto value.

### Files Modified
- `/np-webhook-10-26/app.py` - Added CoinGecko integration and GCWebhook1 triggering
- `/np-webhook-10-26/cloudtasks_client.py` - NEW: Cloud Tasks client
- `/np-webhook-10-26/requirements.txt` - Added requests and google-cloud-tasks
- `/GCWebhook1-10-26/tph1-10-26.py` - Added /process-validated-payment endpoint
- Database: Added `nowpayments_outcome_amount_usd` column

### Testing
- ✅ Test payment processed successfully
- ✅ Outcome USD calculated correctly via CoinGecko
- ✅ GCWebhook1 triggered with validated data
- ✅ Payments queued with actual amounts
- ✅ Database records complete

---
```

**Verification:**
- [ ] Entry added to PROGRESS.md
- [ ] Entry is at the TOP of the file
- [ ] Concise and accurate

---

### ☑️ Step 8.2: Update DECISIONS.md

**File:** `/OCTOBER/10-26/DECISIONS.md`

**Action:** Add architectural decision at the TOP

```markdown
## [2025-11-02] Architecture: GCWebhook1 as Central Orchestrator for Validated Payments

### Decision
Use GCWebhook1 as the central orchestrator for payment routing instead of having NP-Webhook directly queue to GCSplit1/GCAccumulator.

### Rationale
1. **Separation of Concerns:** NP-Webhook handles validation/pricing, GCWebhook1 handles routing
2. **Architectural Consistency:** Maintains GCWebhook1's role as orchestrator
3. **Extensibility:** Easy to add new payout modes in GCWebhook1 without touching NP-Webhook
4. **Maintainability:** Clear boundaries between services

### Alternatives Considered
- **Direct Queuing:** NP-Webhook directly queues to GCSplit1/GCAccumulator
  - Rejected: Mixes validation and business logic in one service
  - Would require updating NP-Webhook for any routing changes

### Implementation
- NP-Webhook: IPN validation → CoinGecko pricing → Database update → Trigger GCWebhook1
- GCWebhook1: Receive validated data → Route based on payout mode → Queue to processor
- Clean event-driven architecture with clear responsibilities

---
```

**Verification:**
- [ ] Entry added to DECISIONS.md
- [ ] Entry is at the TOP of the file
- [ ] Rationale clearly stated

---

### ☑️ Step 8.3: Create Rollback Plan

**File:** `/OCTOBER/10-26/NOWPAYMENTS_OUTCOME_ROLLBACK_PLAN.md` (NEW)

**Action:** Create rollback procedure

```markdown
# Rollback Plan: NowPayments Outcome Amount Architecture

## When to Rollback
- CoinGecko API consistently failing (>10% of requests)
- GCWebhook1 validated endpoint errors (>5% error rate)
- Incorrect payment amounts being processed
- Database performance issues

## Rollback Steps

### Step 1: Revert GCWebhook1
```bash
# Redeploy previous version
gcloud run services update gcwebhook1-10-26 \
  --region=us-central1 \
  --image=<previous-image-sha>
```

### Step 2: Revert NP-Webhook
```bash
# Redeploy previous version
gcloud run services update np-webhook-10-26 \
  --region=us-central1 \
  --image=<previous-image-sha>
```

### Step 3: Verify Old Flow Works
- Create test payment
- Verify old GET / endpoint processes payments
- Verify GCSplit1/GCAccumulator queuing works

### Step 4: Database Cleanup (Optional)
```sql
-- Column can stay, just won't be populated
-- Optional: Remove if causing issues
ALTER TABLE private_channel_users_database
DROP COLUMN IF EXISTS nowpayments_outcome_amount_usd;
```

## Post-Rollback
- Document what went wrong
- Plan fixes
- Schedule re-deployment

## Recovery Time Objective (RTO)
Target: < 15 minutes from decision to rollback completion
```

**Verification:**
- [ ] Rollback plan created
- [ ] Steps are clear and actionable
- [ ] Previous image SHAs documented

---

## Final Verification Checklist

### ☑️ Database
- [ ] Column `nowpayments_outcome_amount_usd` exists with correct type
- [ ] Index `idx_nowpayments_payment_id` created
- [ ] Column comment added
- [ ] Test payment has outcome USD populated

### ☑️ NP-Webhook
- [ ] `requirements.txt` updated with requests and google-cloud-tasks
- [ ] `cloudtasks_client.py` created
- [ ] `get_crypto_usd_price()` function added
- [ ] Cloud Tasks client initialized
- [ ] IPN handler calculates outcome USD
- [ ] IPN handler triggers GCWebhook1
- [ ] Deployed successfully
- [ ] Logs show CoinGecko API calls working

### ☑️ GCWebhook1
- [ ] `/process-validated-payment` endpoint created
- [ ] Endpoint receives validated payment data
- [ ] Payout mode routing works (instant vs threshold)
- [ ] Uses outcome USD for payment amounts
- [ ] Queues to GCSplit1/GCAccumulator correctly
- [ ] Old GET / endpoint deprecated
- [ ] Deployed successfully

### ☑️ Secret Manager
- [ ] `GCWEBHOOK1_QUEUE` secret created
- [ ] `GCWEBHOOK1_URL` secret created
- [ ] `CLOUD_TASKS_PROJECT_ID` secret created
- [ ] `CLOUD_TASKS_LOCATION` secret created
- [ ] NP-Webhook has access to all secrets

### ☑️ Testing
- [ ] Test payment completed successfully
- [ ] CoinGecko price fetched
- [ ] Outcome USD calculated correctly
- [ ] Database updated with outcome USD
- [ ] GCWebhook1 triggered
- [ ] Payment queued with actual amount
- [ ] Amounts match throughout pipeline

### ☑️ Monitoring
- [ ] Log-based metrics created
- [ ] Logs show new flow working
- [ ] No errors in production logs
- [ ] Deprecation warnings visible for old endpoint

### ☑️ Documentation
- [ ] PROGRESS.md updated
- [ ] DECISIONS.md updated
- [ ] Rollback plan created
- [ ] Architecture document reviewed

---

## Success Criteria

### ✅ Functional
- [ ] 100% of payments have `nowpayments_outcome_amount_usd` populated
- [ ] Outcome USD differs from subscription price (proves it's working)
- [ ] GCSplit1/GCAccumulator receive correct amounts
- [ ] No payment processing failures

### ✅ Performance
- [ ] CoinGecko API response time < 2 seconds
- [ ] Total flow time (IPN → GCWebhook1 → GCSplit1) < 10 seconds
- [ ] No timeout errors

### ✅ Reliability
- [ ] Zero payment processing errors
- [ ] Fallback to subscription price works when CoinGecko fails
- [ ] All payments processed correctly

---

## Post-Implementation

### Next Steps
1. Monitor for 72 hours
2. Review logs daily for first week
3. Compare outcome amounts vs declared prices
4. Gather statistics on discrepancies
5. Consider removing deprecated GET / endpoint after 30 days

### Metrics to Track
- Average difference between outcome USD and declared price
- CoinGecko API success rate
- Payment processing success rate
- Time from IPN to payment queuing

---

**Implementation Date:** 2025-11-02
**Implemented By:** Claude Code
**Architecture Document:** NOWPAYMENTS_OUTCOME_AMOUNT_GCWEBHOOK1_ARCHITECTURE.md
**Status:** Ready for Implementation
