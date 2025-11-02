# Micro-Batch Conversion Architecture
**Micro-Batch ETH→USDT Conversion with Dynamic Google Cloud Secret Threshold**

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Current System Flow (Per-Payment Conversion)](#current-system-flow-per-payment-conversion)
3. [Proposed System Flow (Micro-Batch Conversion)](#proposed-system-flow-micro-batch-conversion)
4. [Key Architectural Changes](#key-architectural-changes)
5. [Google Cloud Secret Integration](#google-cloud-secret-integration)
6. [Proportional Distribution Mathematics](#proportional-distribution-mathematics)
7. [Detailed Implementation Checklist](#detailed-implementation-checklist)
8. [Scalability Strategy](#scalability-strategy)
9. [Testing Plan](#testing-plan)
10. [Deployment Guide](#deployment-guide)

---

## Architecture Overview

### Current Problem
The existing system creates **ONE ChangeNow ETH→USDT swap per payment** immediately upon payment receipt. This results in:
- High gas fees (multiple small transactions)
- Poor cost efficiency at scale
- Unnecessary API call volume

### Micro-Batch Solution
Accumulate **multiple pending payments** and create **ONE ChangeNow swap** when the total pending amount reaches a dynamic threshold stored in **Google Cloud Secret Manager**.

**Key Benefits:**
- ✅ Reduces gas fees (one swap for multiple payments)
- ✅ Cost-efficient at scale ($20 → $100 → $1000+ threshold growth)
- ✅ Still provides volatility protection (15-minute window acceptable)
- ✅ Dynamic threshold without code changes

---

## Current System Flow (Per-Payment Conversion)

```
1. User pays $50 → GCWebhook1
                    ↓
2. GCWebhook1 → GCAccumulator (queues task)
                    ↓
3. GCAccumulator.accumulate_payment():
   - Calculates adjusted amount (after TP fee)
   - Stores in payout_accumulation (conversion_status='pending')
   - **IMMEDIATELY** queues task to GCSplit3 for ETH→USDT swap
                    ↓
4. GCSplit3 creates ChangeNow swap
   - Callbacks to GCAccumulator /swap-created
                    ↓
5. GCAccumulator queues task to GCHostPay1 for execution
                    ↓
6. GCHostPay1 executes ETH payment
   - Callbacks to GCAccumulator /swap-executed
                    ↓
7. GCAccumulator finalizes conversion with actual USDT amount
```

**Problem:** Steps 3-7 happen **ONCE per payment** (inefficient)

---

## Proposed System Flow (Micro-Batch Conversion)

```
1. User pays $50 → GCWebhook1
                    ↓
2. GCWebhook1 → GCAccumulator (queues task)
                    ↓
3. GCAccumulator.accumulate_payment():
   - Calculates adjusted amount (after TP fee)
   - Stores in payout_accumulation (conversion_status='pending')
   - **DOES NOT queue swap immediately** ✅ CHANGE
   - Returns success
                    ↓
4. [15 minutes pass... more payments accumulate]
                    ↓
5. Cloud Scheduler triggers MicroBatchProcessor.check_threshold() every 15 mins
                    ↓
6. MicroBatchProcessor:
   - Queries total pending USD: SUM(accumulated_eth) WHERE conversion_status='pending'
   - Fetches threshold from Google Cloud Secret (e.g., $50)
   - If total_pending >= threshold:
       a. Create ONE ChangeNow ETH→USDT swap for TOTAL amount
       b. Store swap details (cn_api_id, payin_address)
       c. Update ALL pending records: conversion_status='swapping'
       d. Enqueue to GCHostPay1 for execution
                    ↓
7. GCHostPay1 executes swap
   - Callbacks to MicroBatchProcessor with actual USDT received
                    ↓
8. MicroBatchProcessor distributes USDT proportionally:
   - For each pending record:
       usdt_share = (record.accumulated_eth / total_pending) * actual_usdt_received
   - Updates each record: accumulated_amount_usdt = usdt_share
   - Updates each record: conversion_status='completed'
```

**Efficiency:** Steps 6-8 happen **ONCE per batch** (many payments), not once per payment

---

## Key Architectural Changes

### 1. **GCAccumulator Modifications**
**Current Behavior (Lines 63-208):**
```python
# REMOVE THIS LOGIC:
# Immediately queue task to GCSplit3 for ETH→USDT swap
encrypted_token = token_manager.encrypt_accumulator_to_gcsplit3_token(...)
task_name = cloudtasks_client.enqueue_gcsplit3_eth_to_usdt_swap(...)
```

**New Behavior:**
```python
# Store payment with conversion_status='pending'
accumulation_id = db_manager.insert_payout_accumulation_pending(...)

# Return success immediately (NO swap queuing)
return jsonify({
    "status": "success",
    "message": "Payment accumulated (pending batch conversion)",
    "accumulation_id": accumulation_id,
    "conversion_status": "pending"
}), 200
```

**Endpoints to Keep:**
- `/swap-executed` endpoint - Still needed for GCHostPay1 callbacks (but rename/repurpose)
- Remove `/swap-created` endpoint - No longer needed (GCSplit3 won't callback per payment)

---

### 2. **New Service: GCMicroBatchProcessor-10-26**

**Purpose:** Cron-triggered service that checks pending threshold and creates batch swaps

**Endpoints:**

#### `POST /check-threshold` (Cron-triggered)
```python
@app.route("/check-threshold", methods=["POST"])
def check_threshold():
    """
    Triggered by Cloud Scheduler every 15 minutes.

    Flow:
    1. Fetch threshold from Google Cloud Secret
    2. Query total pending: SUM(accumulated_eth) WHERE conversion_status='pending'
    3. If total >= threshold:
       a. Fetch all pending records with their details
       b. Create ONE ChangeNow ETH→USDT swap for total amount
       c. Store batch_conversion record with cn_api_id
       d. Update ALL pending records: conversion_status='swapping', batch_conversion_id
       e. Enqueue to GCHostPay1 for execution
    4. Return summary
    """
```

#### `POST /swap-executed` (Callback from GCHostPay1)
```python
@app.route("/swap-executed", methods=["POST"])
def swap_executed():
    """
    Receives callback from GCHostPay1 after ETH payment executed.

    Flow:
    1. Decrypt token from GCHostPay1
    2. Extract: batch_conversion_id, cn_api_id, actual_usdt_received
    3. Fetch all pending records for this batch_conversion_id
    4. Calculate total_pending_usd = SUM(accumulated_eth)
    5. For each record:
       usdt_share = (record.accumulated_eth / total_pending_usd) * actual_usdt_received
       UPDATE payout_accumulation SET:
           accumulated_amount_usdt = usdt_share,
           conversion_status = 'completed',
           conversion_tx_hash = tx_hash
       WHERE id = record.id
    6. Mark batch_conversion as completed
    7. Return success
    """
```

**Pattern Reference:** This mirrors `GCBatchProcessor-10-26/batch10-26.py` structure:
- Cron-triggered endpoint (lines 60-227)
- Database aggregation queries (GCBatchProcessor database_manager.py lines 58-152)
- Cloud Tasks integration
- Token encryption/decryption

---

### 3. **New Database Table: batch_conversions**

```sql
CREATE TABLE batch_conversions (
    id SERIAL PRIMARY KEY,
    batch_conversion_id UUID NOT NULL UNIQUE,
    total_eth_usd NUMERIC(20, 8) NOT NULL,
    threshold_at_creation NUMERIC(20, 2) NOT NULL,
    cn_api_id VARCHAR(255),
    payin_address VARCHAR(255),
    conversion_status VARCHAR(20) DEFAULT 'pending',
    actual_usdt_received NUMERIC(20, 8),
    conversion_tx_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    processing_started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_batch_conversions_status ON batch_conversions(conversion_status);
CREATE INDEX idx_batch_conversions_cn_api_id ON batch_conversions(cn_api_id);
```

---

### 4. **Modified Database Table: payout_accumulation**

**Add New Column:**
```sql
ALTER TABLE payout_accumulation
ADD COLUMN batch_conversion_id UUID REFERENCES batch_conversions(batch_conversion_id);

CREATE INDEX idx_payout_accumulation_batch_conversion ON payout_accumulation(batch_conversion_id);
```

**Purpose:** Links individual payments to their batch conversion

---

### 5. **New Database Queries**

#### Get Total Pending USD
```sql
SELECT COALESCE(SUM(accumulated_eth), 0) as total_pending
FROM payout_accumulation
WHERE conversion_status = 'pending';
```

#### Get All Pending Records for Batch
```sql
SELECT id, accumulated_eth, client_id, user_id
FROM payout_accumulation
WHERE conversion_status = 'pending'
ORDER BY created_at ASC;
```

#### Update Records to Swapping Status
```sql
UPDATE payout_accumulation
SET conversion_status = 'swapping',
    batch_conversion_id = %s,
    updated_at = NOW()
WHERE conversion_status = 'pending';
```

#### Proportionally Distribute USDT
```python
# For each record in batch:
usdt_share = (record.accumulated_eth / total_pending_usd) * actual_usdt_received

# SQL:
UPDATE payout_accumulation
SET accumulated_amount_usdt = %s,
    conversion_status = 'completed',
    conversion_tx_hash = %s,
    updated_at = NOW()
WHERE id = %s;
```

---

## Google Cloud Secret Integration

### Secret Name: `MICRO_BATCH_THRESHOLD_USD`

**Initial Value:** `20.00`

**Scaling Path:**
- Launch: `$20` (accumulate 2-4 payments before swap)
- Month 1: `$50` (5-10 payments)
- Month 3: `$100` (10-20 payments)
- Year 1: `$500` (50+ payments)
- Year 2: `$1000+` (100+ payments)

### Secret Manager Operations

#### Create Secret (One-time setup)
```bash
gcloud secrets create MICRO_BATCH_THRESHOLD_USD \
    --replication-policy="automatic" \
    --project=telepay-459221

# Set initial value
echo -n "20.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD \
    --data-file=- \
    --project=telepay-459221
```

#### Grant Access to Service Account
```bash
# Get service account for GCMicroBatchProcessor
SERVICE_ACCOUNT="gcmicrobatchprocessor-10-26@telepay-459221.iam.gserviceaccount.com"

gcloud secrets add-iam-policy-binding MICRO_BATCH_THRESHOLD_USD \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=telepay-459221
```

#### Update Threshold (No code changes)
```bash
# Scale up to $100
echo -n "100.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD \
    --data-file=- \
    --project=telepay-459221

# Scale up to $1000
echo -n "1000.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD \
    --data-file=- \
    --project=telepay-459221
```

### Fetching Secret in Code

**config_manager.py:**
```python
from google.cloud import secretmanager

def get_micro_batch_threshold(self) -> Decimal:
    """
    Fetch micro-batch threshold from Google Cloud Secret Manager.

    Returns:
        Decimal threshold value (e.g., Decimal('20.00'))
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        project_id = self.config.get('cloud_tasks_project_id', 'telepay-459221')

        secret_name = f"projects/{project_id}/secrets/MICRO_BATCH_THRESHOLD_USD/versions/latest"

        print(f"🔐 [CONFIG] Fetching threshold from Secret Manager")
        response = client.access_secret_version(request={"name": secret_name})
        threshold_str = response.payload.data.decode('UTF-8')
        threshold = Decimal(threshold_str)

        print(f"✅ [CONFIG] Threshold fetched: ${threshold}")
        return threshold

    except Exception as e:
        print(f"❌ [CONFIG] Failed to fetch threshold: {e}")
        # Fallback to default
        print(f"⚠️ [CONFIG] Using fallback threshold: $20.00")
        return Decimal('20.00')
```

**Usage in MicroBatchProcessor:**
```python
threshold = config_manager.get_micro_batch_threshold()
total_pending = db_manager.get_total_pending_usd()

if total_pending >= threshold:
    # Create batch swap
    create_batch_conversion(total_pending, threshold)
```

---

## Proportional Distribution Mathematics

### Problem
- Multiple payments accumulated: `[p1=$10, p2=$15, p3=$25]` = `$50 total`
- Create ONE ChangeNow swap: `$50 ETH → ? USDT`
- ChangeNow returns: `$48.50 USDT` (after fees/slippage)
- **How to distribute $48.50 across p1, p2, p3?**

### Solution: Proportional Distribution

**Formula:**
```
usdt_share_i = (payment_i / total_pending) × actual_usdt_received
```

**Example:**
```python
# Payments
p1 = Decimal('10.00')  # 20% of total
p2 = Decimal('15.00')  # 30% of total
p3 = Decimal('25.00')  # 50% of total
total_pending = Decimal('50.00')

# ChangeNow swap result
actual_usdt_received = Decimal('48.50')

# Distribution
usdt_p1 = (p1 / total_pending) * actual_usdt_received
        = (10 / 50) * 48.50
        = 0.20 * 48.50
        = 9.70 USDT ✅

usdt_p2 = (15 / 50) * 48.50
        = 0.30 * 48.50
        = 14.55 USDT ✅

usdt_p3 = (25 / 50) * 48.50
        = 0.50 * 48.50
        = 24.25 USDT ✅

# Verify: 9.70 + 14.55 + 24.25 = 48.50 ✅
```

### Python Implementation

```python
from decimal import Decimal, getcontext

def distribute_usdt_proportionally(
    pending_records: List[Dict],
    actual_usdt_received: Decimal
) -> List[Dict]:
    """
    Distribute actual USDT received proportionally across pending records.

    Args:
        pending_records: List of dicts with 'id' and 'accumulated_eth'
        actual_usdt_received: Total USDT received from ChangeNow

    Returns:
        List of dicts with 'id' and 'usdt_share'
    """
    # Set precision for Decimal calculations
    getcontext().prec = 28

    # Calculate total pending
    total_pending = sum(Decimal(str(r['accumulated_eth'])) for r in pending_records)

    print(f"💰 [DISTRIBUTION] Total pending: ${total_pending}")
    print(f"💰 [DISTRIBUTION] Actual USDT received: ${actual_usdt_received}")

    distributions = []
    running_total = Decimal('0')

    for i, record in enumerate(pending_records):
        record_eth = Decimal(str(record['accumulated_eth']))

        # Last record gets remainder to avoid rounding errors
        if i == len(pending_records) - 1:
            usdt_share = actual_usdt_received - running_total
        else:
            usdt_share = (record_eth / total_pending) * actual_usdt_received
            running_total += usdt_share

        distributions.append({
            'id': record['id'],
            'usdt_share': usdt_share,
            'percentage': (record_eth / total_pending) * 100
        })

        print(f"📊 [DISTRIBUTION] Record {record['id']}: "
              f"${record_eth} ({(record_eth/total_pending)*100:.2f}%) → "
              f"${usdt_share} USDT")

    # Verification
    total_distributed = sum(d['usdt_share'] for d in distributions)
    print(f"✅ [DISTRIBUTION] Verification: ${total_distributed} = ${actual_usdt_received}")

    return distributions
```

### Handling Edge Cases

**Case 1: Zero Pending Records**
```python
if not pending_records:
    print(f"⚠️ [DISTRIBUTION] No pending records to distribute")
    return []
```

**Case 2: Single Record**
```python
if len(pending_records) == 1:
    # All USDT goes to single record
    return [{
        'id': pending_records[0]['id'],
        'usdt_share': actual_usdt_received,
        'percentage': Decimal('100')
    }]
```

**Case 3: Rounding Precision**
- Use `Decimal` for all calculations (never `float`)
- Last record gets remainder to ensure exact total
- Verify distribution sums to actual USDT received

---

## Detailed Implementation Checklist

### Phase 1: Database Setup

- [ ] **1.1** Create `batch_conversions` table
  ```sql
  -- Execute in PostgreSQL
  CREATE TABLE batch_conversions (
      id SERIAL PRIMARY KEY,
      batch_conversion_id UUID NOT NULL UNIQUE,
      total_eth_usd NUMERIC(20, 8) NOT NULL,
      threshold_at_creation NUMERIC(20, 2) NOT NULL,
      cn_api_id VARCHAR(255),
      payin_address VARCHAR(255),
      conversion_status VARCHAR(20) DEFAULT 'pending',
      actual_usdt_received NUMERIC(20, 8),
      conversion_tx_hash VARCHAR(255),
      created_at TIMESTAMP DEFAULT NOW(),
      processing_started_at TIMESTAMP,
      completed_at TIMESTAMP
  );

  CREATE INDEX idx_batch_conversions_status ON batch_conversions(conversion_status);
  CREATE INDEX idx_batch_conversions_cn_api_id ON batch_conversions(cn_api_id);
  ```

- [ ] **1.2** Add `batch_conversion_id` column to `payout_accumulation`
  ```sql
  ALTER TABLE payout_accumulation
  ADD COLUMN batch_conversion_id UUID REFERENCES batch_conversions(batch_conversion_id);

  CREATE INDEX idx_payout_accumulation_batch_conversion ON payout_accumulation(batch_conversion_id);
  ```

- [ ] **1.3** Verify schema changes
  ```bash
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "\d batch_conversions"

  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "\d payout_accumulation"
  ```

---

### Phase 2: Google Cloud Secret Setup

- [ ] **2.1** Create secret in Secret Manager
  ```bash
  gcloud secrets create MICRO_BATCH_THRESHOLD_USD \
      --replication-policy="automatic" \
      --project=telepay-459221
  ```

- [ ] **2.2** Set initial threshold value ($20)
  ```bash
  echo -n "20.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD \
      --data-file=- \
      --project=telepay-459221
  ```

- [ ] **2.3** Grant access to service accounts
  ```bash
  # For GCMicroBatchProcessor (create service account first in Phase 3)
  gcloud secrets add-iam-policy-binding MICRO_BATCH_THRESHOLD_USD \
      --member="serviceAccount:gcmicrobatchprocessor-10-26@telepay-459221.iam.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor" \
      --project=telepay-459221
  ```

- [ ] **2.4** Verify secret access
  ```bash
  gcloud secrets versions access latest --secret=MICRO_BATCH_THRESHOLD_USD \
      --project=telepay-459221
  ```

---

### Phase 3: Create GCMicroBatchProcessor Service

- [ ] **3.1** Create service directory
  ```bash
  mkdir -p /OCTOBER/10-26/GCMicroBatchProcessor-10-26
  cd /OCTOBER/10-26/GCMicroBatchProcessor-10-26
  ```

- [ ] **3.2** Create `microbatch10-26.py` (main service file)
  - Implement `/check-threshold` endpoint (cron-triggered)
  - Implement `/swap-executed` endpoint (callback from GCHostPay1)
  - Pattern: Copy structure from `GCBatchProcessor-10-26/batch10-26.py`

- [ ] **3.3** Create `database_manager.py`
  - Implement `get_total_pending_usd()` - global SUM query
  - Implement `get_all_pending_records()` - fetch all pending for batch
  - Implement `create_batch_conversion()` - insert batch record
  - Implement `update_records_to_swapping()` - mark pending → swapping
  - Implement `distribute_usdt_proportionally()` - final USDT distribution
  - Implement `finalize_batch_conversion()` - mark batch complete
  - Pattern: Reference `GCBatchProcessor-10-26/database_manager.py`

- [ ] **3.4** Create `config_manager.py`
  - Add `get_micro_batch_threshold()` method (fetch from Secret Manager)
  - Pattern: Copy from `GCAccumulator-10-26/config_manager.py`

- [ ] **3.5** Create `token_manager.py`
  - Implement `encrypt_microbatch_to_gchostpay1_token()` - batch execution token
  - Implement `decrypt_gchostpay1_to_microbatch_token()` - execution response
  - Pattern: Reference `GCAccumulator-10-26/token_manager.py`

- [ ] **3.6** Create `cloudtasks_client.py`
  - Implement `enqueue_gchostpay1_batch_execution()` - queue batch swap
  - Pattern: Copy from `GCAccumulator-10-26/cloudtasks_client.py`

- [ ] **3.7** Create `Dockerfile`
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 microbatch10-26:app
  ```

- [ ] **3.8** Create `requirements.txt`
  ```
  Flask==3.0.0
  gunicorn==21.2.0
  google-cloud-secret-manager==2.16.4
  cloud-sql-python-connector[pg8000]==1.5.0
  pg8000==1.30.3
  google-cloud-tasks==2.14.2
  ```

- [ ] **3.9** Create `.dockerignore`
  ```
  __pycache__
  *.pyc
  .env
  .git
  ```

---

### Phase 4: Modify GCAccumulator Service

- [ ] **4.1** Backup current GCAccumulator
  ```bash
  cp -r /OCTOBER/10-26/GCAccumulator-10-26 \
        /OCTOBER/ARCHIVES/GCAccumulator-10-26-BACKUP-$(date +%Y%m%d)
  ```

- [ ] **4.2** Modify `acc10-26.py` - Remove immediate swap queuing
  - **REMOVE** lines 146-191 (GCSplit3 task queuing logic)
  - **KEEP** lines 63-145 (payment accumulation logic)
  - **UPDATE** response at lines 194-201 to indicate "pending batch conversion"

  **Before:**
  ```python
  # Queue task to GCSplit3 for ACTUAL ETH→USDT swap creation
  if not cloudtasks_client:
      print(f"❌ [ENDPOINT] Cloud Tasks client not available")
      abort(500, "Cloud Tasks unavailable")

  # ... GCSplit3 queuing code ...

  return jsonify({
      "status": "success",
      "message": "Payment accumulated successfully, ETH→USDT swap pending",
      "conversion_status": "pending"
  }), 200
  ```

  **After:**
  ```python
  print(f"✅ [ENDPOINT] Payment accumulated (awaiting micro-batch conversion)")
  print(f"⏳ [ENDPOINT] Conversion will occur when batch threshold reached")

  return jsonify({
      "status": "success",
      "message": "Payment accumulated successfully (micro-batch pending)",
      "accumulation_id": accumulation_id,
      "conversion_status": "pending"
  }), 200
  ```

- [ ] **4.3** Remove `/swap-created` endpoint (lines 211-333)
  - This endpoint is no longer needed (was callback from GCSplit3)

- [ ] **4.4** Remove `/swap-executed` endpoint (lines 336-417)
  - This logic moves to GCMicroBatchProcessor

- [ ] **4.5** Keep `/health` endpoint unchanged

- [ ] **4.6** Test modified GCAccumulator locally
  ```bash
  cd /OCTOBER/10-26/GCAccumulator-10-26
  python acc10-26.py
  # Test POST / endpoint with mock payment data
  ```

---

### Phase 5: Modify GCHostPay1 Service

- [ ] **5.1** Update `tphp1-10-26.py` - Add context handling
  - Currently expects tokens from GCAccumulator (individual payments)
  - Need to handle tokens from GCMicroBatchProcessor (batch conversions)

  **Token decryption should extract context:**
  ```python
  decrypted_data = token_manager.decrypt_token(encrypted_token)
  context = decrypted_data.get('context', 'individual')  # 'individual' or 'batch'

  if context == 'batch':
      batch_conversion_id = decrypted_data['batch_conversion_id']
      # Use batch callback URL
      callback_queue = config.get('microbatch_response_queue')
      callback_url = config.get('microbatch_url')
  else:
      accumulation_id = decrypted_data['accumulation_id']
      # Use individual callback URL (if keeping old flow for debugging)
      callback_queue = config.get('accumulator_response_queue')
      callback_url = config.get('accumulator_url')
  ```

- [ ] **5.2** Update token_manager.py encryption/decryption
  - Add `context` field to tokens
  - Add `batch_conversion_id` field for batch context

- [ ] **5.3** Test GCHostPay1 modifications locally

---

### Phase 6: Create Cloud Tasks Queues

- [ ] **6.1** Create queue for MicroBatchProcessor execution requests
  ```bash
  gcloud tasks queues create gchostpay1-batch-queue \
      --location=us-central1 \
      --max-concurrent-dispatches=10 \
      --max-attempts=10 \
      --max-retry-duration=24h
  ```

- [ ] **6.2** Create queue for GCHostPay1 → MicroBatchProcessor responses
  ```bash
  gcloud tasks queues create microbatch-response-queue \
      --location=us-central1 \
      --max-concurrent-dispatches=10 \
      --max-attempts=10 \
      --max-retry-duration=24h
  ```

- [ ] **6.3** Store queue names in Secret Manager
  ```bash
  echo -n "gchostpay1-batch-queue" | \
      gcloud secrets versions add GCHOSTPAY1_BATCH_QUEUE --data-file=-

  echo -n "microbatch-response-queue" | \
      gcloud secrets versions add MICROBATCH_RESPONSE_QUEUE --data-file=-
  ```

- [ ] **6.4** Verify queues created
  ```bash
  gcloud tasks queues list --location=us-central1
  ```

---

### Phase 7: Deploy GCMicroBatchProcessor

- [ ] **7.1** Build Docker image
  ```bash
  cd /OCTOBER/10-26/GCMicroBatchProcessor-10-26

  gcloud builds submit --tag gcr.io/telepay-459221/gcmicrobatchprocessor-10-26
  ```

- [ ] **7.2** Deploy to Cloud Run
  ```bash
  gcloud run deploy gcmicrobatchprocessor-10-26 \
      --image gcr.io/telepay-459221/gcmicrobatchprocessor-10-26 \
      --platform managed \
      --region us-central1 \
      --allow-unauthenticated \
      --memory 512Mi \
      --cpu 1 \
      --timeout 900 \
      --min-instances 0 \
      --max-instances 10 \
      --add-cloudsql-instances telepay-459221:us-central1:telepaypsql
  ```

- [ ] **7.3** Get service URL
  ```bash
  gcloud run services describe gcmicrobatchprocessor-10-26 \
      --region us-central1 \
      --format='value(status.url)'
  ```

- [ ] **7.4** Store service URL in Secret Manager
  ```bash
  # Example: https://gcmicrobatchprocessor-10-26-abc123-uc.a.run.app
  SERVICE_URL=$(gcloud run services describe gcmicrobatchprocessor-10-26 \
      --region us-central1 --format='value(status.url)')

  echo -n "$SERVICE_URL" | \
      gcloud secrets versions add MICROBATCH_URL --data-file=-
  ```

- [ ] **7.5** Test health endpoint
  ```bash
  curl https://gcmicrobatchprocessor-10-26-abc123-uc.a.run.app/health
  ```

---

### Phase 8: Create Cloud Scheduler Job

- [ ] **8.1** Create cron job to trigger threshold check every 15 minutes
  ```bash
  gcloud scheduler jobs create http micro-batch-conversion-job \
      --location=us-central1 \
      --schedule="*/15 * * * *" \
      --uri="https://gcmicrobatchprocessor-10-26-abc123-uc.a.run.app/check-threshold" \
      --http-method=POST \
      --oidc-service-account-email=gcmicrobatchprocessor-10-26@telepay-459221.iam.gserviceaccount.com \
      --oidc-token-audience="https://gcmicrobatchprocessor-10-26-abc123-uc.a.run.app"
  ```

- [ ] **8.2** Test manual trigger
  ```bash
  gcloud scheduler jobs run micro-batch-conversion-job \
      --location=us-central1
  ```

- [ ] **8.3** Monitor job executions
  ```bash
  gcloud scheduler jobs describe micro-batch-conversion-job \
      --location=us-central1
  ```

---

### Phase 9: Redeploy Modified Services

- [ ] **9.1** Redeploy GCAccumulator (with removed swap queuing)
  ```bash
  cd /OCTOBER/10-26/GCAccumulator-10-26

  gcloud builds submit --tag gcr.io/telepay-459221/gcaccumulator-10-26

  gcloud run deploy gcaccumulator-10-26 \
      --image gcr.io/telepay-459221/gcaccumulator-10-26 \
      --platform managed \
      --region us-central1
  ```

- [ ] **9.2** Redeploy GCHostPay1 (with batch context handling)
  ```bash
  cd /OCTOBER/10-26/GCHostPay1-10-26

  gcloud builds submit --tag gcr.io/telepay-459221/gchostpay1-10-26

  gcloud run deploy gchostpay1-10-26 \
      --image gcr.io/telepay-459221/gchostpay1-10-26 \
      --platform managed \
      --region us-central1
  ```

---

### Phase 10: Testing

- [ ] **10.1** Test payment accumulation (no immediate swap)
  ```bash
  # Send test payment via GCWebhook1
  # Verify: payout_accumulation record created with conversion_status='pending'
  # Verify: NO task queued to GCSplit3
  # Verify: NO ChangeNow swap created
  ```

- [ ] **10.2** Test threshold check (below threshold)
  ```bash
  # Manual trigger scheduler
  gcloud scheduler jobs run micro-batch-conversion-job --location=us-central1

  # Verify logs show: "Total pending ($15) < Threshold ($20) - no action"
  ```

- [ ] **10.3** Test threshold check (above threshold)
  ```bash
  # Accumulate multiple payments until total >= $20
  # Manual trigger scheduler
  gcloud scheduler jobs run micro-batch-conversion-job --location=us-central1

  # Verify logs show:
  # - "Total pending ($25) >= Threshold ($20) - creating batch"
  # - batch_conversions record created
  # - All pending records updated: conversion_status='swapping'
  # - Task queued to GCHostPay1
  # - ChangeNow swap created
  ```

- [ ] **10.4** Test swap execution and proportional distribution
  ```bash
  # Wait for GCHostPay1 to execute swap
  # Verify callback to MicroBatchProcessor /swap-executed
  # Verify logs show proportional distribution calculations
  # Verify all records updated with:
  #   - accumulated_amount_usdt (proportional share)
  #   - conversion_status='completed'
  #   - conversion_tx_hash
  ```

- [ ] **10.5** Test threshold scaling
  ```bash
  # Update threshold to $100
  echo -n "100.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=-

  # Verify MicroBatchProcessor fetches new threshold
  # Verify batches only created when total_pending >= $100
  ```

---

### Phase 11: Monitoring and Observability

- [ ] **11.1** Set up log-based metrics
  ```bash
  # Track batch conversions
  gcloud logging metrics create micro_batch_conversions \
      --description="Count of micro-batch conversions" \
      --log-filter='resource.type="cloud_run_revision"
      resource.labels.service_name="gcmicrobatchprocessor-10-26"
      jsonPayload.message=~"Batch conversion created"'
  ```

- [ ] **11.2** Create alerting policy
  ```bash
  # Alert if no batches created in 24 hours (may indicate issue)
  # Alert if batch failure rate > 5%
  ```

- [ ] **11.3** Set up dashboard for monitoring
  - Total pending USD (real-time)
  - Current threshold value
  - Batch conversion frequency
  - Average batch size
  - Distribution accuracy (verify proportional math)

---

## Scalability Strategy

### Launch Phase: $20 Threshold
**Metrics:**
- 2-4 payments per batch
- Batch frequency: ~2 hours (assuming moderate traffic)
- Gas fee savings: ~50% vs per-payment swaps

**Monitoring:**
```bash
# Check pending accumulation every hour
psql -c "SELECT COUNT(*), SUM(accumulated_eth)
         FROM payout_accumulation
         WHERE conversion_status='pending';"
```

---

### Growth Phase 1: $50 Threshold (Month 1)
**Trigger:** When batches consistently include 8-10 payments

**Update:**
```bash
echo -n "50.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=-
```

**Expected Results:**
- 5-10 payments per batch
- Batch frequency: ~3-4 hours
- Gas fee savings: ~70% vs per-payment swaps

---

### Growth Phase 2: $100 Threshold (Month 3)
**Trigger:** When batches consistently include 15-20 payments

**Update:**
```bash
echo -n "100.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=-
```

**Expected Results:**
- 10-20 payments per batch
- Batch frequency: ~6-8 hours
- Gas fee savings: ~80% vs per-payment swaps

---

### Maturity Phase: $500-$1000+ Threshold (Year 1+)
**Trigger:** High traffic (50+ payments per day)

**Update:**
```bash
echo -n "500.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=-
# Or even higher:
echo -n "1000.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=-
```

**Expected Results:**
- 50-100+ payments per batch
- Batch frequency: ~12-24 hours
- Gas fee savings: ~90% vs per-payment swaps

---

### Dynamic Threshold Algorithm (Future Enhancement)

**Auto-scaling based on metrics:**
```python
def calculate_optimal_threshold(
    avg_daily_volume: Decimal,
    avg_payment_size: Decimal,
    target_batch_frequency_hours: int = 6
) -> Decimal:
    """
    Dynamically calculate optimal threshold.

    Example:
    - avg_daily_volume = $500
    - target_batch_frequency = 6 hours (4 batches/day)
    - optimal_threshold = $500 / 4 = $125
    """
    batches_per_day = 24 / target_batch_frequency_hours
    optimal_threshold = avg_daily_volume / Decimal(str(batches_per_day))

    # Round to nearest $10
    return (optimal_threshold / 10).quantize(1) * 10
```

---

## Testing Plan

### Unit Tests

#### Test: Proportional Distribution Math
```python
def test_proportional_distribution():
    """Test USDT distribution across 3 payments."""
    pending_records = [
        {'id': 1, 'accumulated_eth': Decimal('10.00')},  # 20%
        {'id': 2, 'accumulated_eth': Decimal('15.00')},  # 30%
        {'id': 3, 'accumulated_eth': Decimal('25.00')}   # 50%
    ]
    actual_usdt = Decimal('48.50')

    distributions = distribute_usdt_proportionally(pending_records, actual_usdt)

    assert distributions[0]['usdt_share'] == Decimal('9.70')
    assert distributions[1]['usdt_share'] == Decimal('14.55')
    assert distributions[2]['usdt_share'] == Decimal('24.25')

    # Verify sum
    total = sum(d['usdt_share'] for d in distributions)
    assert total == actual_usdt
```

#### Test: Secret Manager Fetch
```python
def test_secret_manager_threshold():
    """Test fetching threshold from Secret Manager."""
    config_manager = ConfigManager()
    threshold = config_manager.get_micro_batch_threshold()

    assert isinstance(threshold, Decimal)
    assert threshold > Decimal('0')
    print(f"Current threshold: ${threshold}")
```

#### Test: Threshold Logic
```python
def test_threshold_check():
    """Test batch creation logic."""
    total_pending = Decimal('25.00')
    threshold = Decimal('20.00')

    should_create_batch = total_pending >= threshold
    assert should_create_batch == True

    total_pending = Decimal('15.00')
    should_create_batch = total_pending >= threshold
    assert should_create_batch == False
```

---

### Integration Tests

#### Test: End-to-End Batch Conversion
```python
def test_e2e_batch_conversion():
    """
    Test complete micro-batch flow:
    1. Create 3 pending payments
    2. Trigger threshold check
    3. Verify batch conversion created
    4. Mock GCHostPay1 execution
    5. Verify proportional distribution
    """
    # Setup: Insert 3 test payments
    db_manager.insert_payout_accumulation_pending(...)  # $10
    db_manager.insert_payout_accumulation_pending(...)  # $15
    db_manager.insert_payout_accumulation_pending(...)  # $25

    # Trigger batch check
    response = requests.post(f"{MICROBATCH_URL}/check-threshold")
    assert response.status_code == 200

    # Verify batch created
    batch = db_manager.get_latest_batch_conversion()
    assert batch['total_eth_usd'] == Decimal('50.00')
    assert batch['conversion_status'] == 'swapping'

    # Mock GCHostPay1 callback with actual USDT
    mock_callback_data = {
        'batch_conversion_id': batch['batch_conversion_id'],
        'actual_usdt_received': Decimal('48.50'),
        'tx_hash': '0xabc123...'
    }

    token = token_manager.encrypt_gchostpay1_to_microbatch_token(mock_callback_data)
    response = requests.post(
        f"{MICROBATCH_URL}/swap-executed",
        json={'token': token}
    )
    assert response.status_code == 200

    # Verify distribution
    records = db_manager.get_records_by_batch(batch['batch_conversion_id'])
    assert records[0]['accumulated_amount_usdt'] == Decimal('9.70')
    assert records[1]['accumulated_amount_usdt'] == Decimal('14.55')
    assert records[2]['accumulated_amount_usdt'] == Decimal('24.25')

    # Verify all completed
    for record in records:
        assert record['conversion_status'] == 'completed'
```

---

### Load Testing

```bash
# Simulate high payment volume
for i in {1..100}; do
    curl -X POST https://gcaccumulator-10-26.../  \
        -H "Content-Type: application/json" \
        -d '{
            "user_id": '$i',
            "client_id": "test_client",
            "payment_amount_usd": 5.00,
            ...
        }'
done

# Monitor batch creation
gcloud logging read 'resource.type="cloud_run_revision"
    resource.labels.service_name="gcmicrobatchprocessor-10-26"
    jsonPayload.message=~"Batch conversion created"' \
    --limit 50 \
    --format json
```

---

## Deployment Guide

### Pre-Deployment Checklist

- [ ] All database migrations completed (Phase 1)
- [ ] Google Cloud Secret created and accessible (Phase 2)
- [ ] GCMicroBatchProcessor service built and tested (Phase 3)
- [ ] GCAccumulator modifications tested (Phase 4)
- [ ] GCHostPay1 modifications tested (Phase 5)
- [ ] Cloud Tasks queues created (Phase 6)
- [ ] Cloud Scheduler job configured (Phase 8)
- [ ] All unit tests passing
- [ ] Integration tests passing

---

### Deployment Steps

#### 1. Deploy GCMicroBatchProcessor (New Service)
```bash
cd /OCTOBER/10-26/GCMicroBatchProcessor-10-26

# Build and deploy
gcloud builds submit --tag gcr.io/telepay-459221/gcmicrobatchprocessor-10-26

gcloud run deploy gcmicrobatchprocessor-10-26 \
    --image gcr.io/telepay-459221/gcmicrobatchprocessor-10-26 \
    --platform managed \
    --region us-central1 \
    --memory 512Mi \
    --timeout 900
```

#### 2. Deploy Modified GCAccumulator
```bash
cd /OCTOBER/10-26/GCAccumulator-10-26

gcloud builds submit --tag gcr.io/telepay-459221/gcaccumulator-10-26

gcloud run deploy gcaccumulator-10-26 \
    --image gcr.io/telepay-459221/gcaccumulator-10-26
```

#### 3. Deploy Modified GCHostPay1
```bash
cd /OCTOBER/10-26/GCHostPay1-10-26

gcloud builds submit --tag gcr.io/telepay-459221/gchostpay1-10-26

gcloud run deploy gchostpay1-10-26 \
    --image gcr.io/telepay-459221/gchostpay1-10-26
```

#### 4. Enable Cloud Scheduler Job
```bash
gcloud scheduler jobs resume micro-batch-conversion-job \
    --location=us-central1
```

#### 5. Monitor First Batch
```bash
# Watch logs
gcloud logging tail "resource.type=cloud_run_revision AND \
    resource.labels.service_name=gcmicrobatchprocessor-10-26" \
    --format=json

# Check database
psql -c "SELECT * FROM batch_conversions ORDER BY created_at DESC LIMIT 5;"
```

---

### Rollback Plan

If issues occur, rollback to per-payment conversion:

#### 1. Pause Cloud Scheduler
```bash
gcloud scheduler jobs pause micro-batch-conversion-job \
    --location=us-central1
```

#### 2. Restore GCAccumulator (Previous Version)
```bash
cd /OCTOBER/ARCHIVES/GCAccumulator-10-26-BACKUP-YYYYMMDD

gcloud builds submit --tag gcr.io/telepay-459221/gcaccumulator-10-26

gcloud run deploy gcaccumulator-10-26 \
    --image gcr.io/telepay-459221/gcaccumulator-10-26
```

#### 3. Process Pending Records Manually
```bash
# Query pending records
psql -c "SELECT id, accumulated_eth FROM payout_accumulation
         WHERE conversion_status='pending';"

# Create individual swaps via GCSplit3 (manual intervention)
```

---

## Summary

### What Changes
- **GCAccumulator**: No longer queues individual swaps (store pending only)
- **GCMicroBatchProcessor**: New service - cron-triggered batch conversion
- **GCHostPay1**: Handles both individual and batch execution contexts
- **Database**: New `batch_conversions` table + `batch_conversion_id` column
- **Threshold**: Stored in Google Cloud Secret (dynamic, no code changes)

### What Stays the Same
- CRON JOBS pattern (Cloud Scheduler)
- QUEUES & TASKS pattern (Cloud Tasks)
- ENCRYPT/DECRYPT TOKEN pattern (HMAC-SHA256)
- GCBatchProcessor (USDT→ClientCurrency batching - unchanged)
- Overall payment flow (GCWebhook1 → GCAccumulator → ... → Client)

### Key Benefits
- ✅ **Cost Efficiency**: 50-90% gas fee reduction
- ✅ **Scalability**: $20 → $1000+ threshold growth
- ✅ **Flexibility**: Update threshold without redeployment
- ✅ **Volatility Protection**: 15-minute window acceptable
- ✅ **Proven Patterns**: Uses existing codebase architecture

### Risks Mitigated
- **Proportional Distribution Errors**: Decimal precision, last-record remainder
- **Secret Fetch Failures**: Fallback to $20 default
- **Batch Conversion Failures**: Individual records remain in 'swapping' state (retry logic)
- **Threshold Too High**: Monitor pending USD, manually trigger if needed

---

## Next Steps

1. Review this document with team
2. Execute Phase 1 (Database Setup)
3. Execute Phase 2 (Secret Manager Setup)
4. Build GCMicroBatchProcessor (Phase 3)
5. Test locally with mock data
6. Deploy to staging environment
7. Run integration tests
8. Deploy to production with $20 threshold
9. Monitor for 1 week
10. Scale threshold based on metrics

---

**Document Version:** 1.0
**Created:** 2025-10-31
**Architecture:** Micro-Batch Conversion (Option 3)
**Pattern:** CRON JOBS + QUEUES & TASKS + ENCRYPT/DECRYPT TOKENS
