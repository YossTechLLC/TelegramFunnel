# Micro-Batch Conversion Architecture - Implementation Checklist
**Architecture Reference:** `MICRO_BATCH_CONVERSION_ARCHITECTURE.md`

**Goal:** Convert from per-payment ETH→USDT swaps to micro-batch conversions with dynamic Google Cloud Secret threshold ($20 → $1000+)

---

## 📋 Quick Overview

### What We're Changing
- ✅ **GCAccumulator**: Remove immediate swap queuing (lines 146-191, 211-417)
- ✅ **GCMicroBatchProcessor**: NEW service for batch conversion logic
- ✅ **GCHostPay1**: Add batch context handling
- ✅ **Database**: Add `batch_conversions` table + `batch_conversion_id` column
- ✅ **Secret Manager**: Store dynamic threshold ($20 → $1000+)
- ✅ **Cloud Scheduler**: Cron job to trigger batch checks every 15 minutes

### What Stays the Same
- ✅ GCBatchProcessor (USDT→ClientCurrency batching) - **NO CHANGES**
- ✅ GCWebhook1/GCWebhook2 - **NO CHANGES**
- ✅ GCSplit1/GCSplit2/GCSplit3 - **NO CHANGES**
- ✅ GCHostPay2/GCHostPay3 - **NO CHANGES**
- ✅ Overall token encryption patterns (HMAC-SHA256)
- ✅ Cloud Tasks queue architecture

---

## 🗂️ Implementation Checklist

### ✅ Phase 1: Database Migrations (telepaypsql)

- [ ] **1.1** Connect to telepaypsql database
  ```bash
  gcloud sql connect telepaypsql --user=postgres --database=telepaydb
  ```

- [ ] **1.2** Create `batch_conversions` table
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
  CREATE INDEX idx_batch_conversions_created ON batch_conversions(created_at);
  ```

- [ ] **1.3** Add `batch_conversion_id` column to `payout_accumulation`
  ```sql
  ALTER TABLE payout_accumulation
  ADD COLUMN batch_conversion_id UUID REFERENCES batch_conversions(batch_conversion_id);

  CREATE INDEX idx_payout_accumulation_batch_conversion ON payout_accumulation(batch_conversion_id);
  ```

- [ ] **1.4** Verify schema changes
  ```bash
  # Check batch_conversions table
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "\d batch_conversions"

  # Check payout_accumulation column added
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "\d payout_accumulation" | grep batch_conversion_id
  ```

---

### ✅ Phase 2: Google Cloud Secret Manager Setup

- [ ] **2.1** Create `MICRO_BATCH_THRESHOLD_USD` secret
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

- [ ] **2.3** Verify secret created
  ```bash
  gcloud secrets versions access latest --secret=MICRO_BATCH_THRESHOLD_USD \
      --project=telepay-459221

  # Expected output: 20.00
  ```

- [ ] **2.4** Grant access to service accounts (after Phase 3.1 creates service)
  ```bash
  # For GCMicroBatchProcessor
  gcloud secrets add-iam-policy-binding MICRO_BATCH_THRESHOLD_USD \
      --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor" \
      --project=telepay-459221

  # Note: Update service account email after service deployment
  ```

---

### ✅ Phase 3: Create GCMicroBatchProcessor-10-26 Service

#### 3.1 - Service Directory Setup

- [ ] **3.1.1** Create service directory
  ```bash
  mkdir -p /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCMicroBatchProcessor-10-26
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCMicroBatchProcessor-10-26
  ```

#### 3.2 - Core Service File: `microbatch10-26.py`

**Reference Pattern:** `GCBatchProcessor-10-26/batch10-26.py` (lines 60-227)

- [ ] **3.2.1** Create `microbatch10-26.py` with Flask app initialization
  - Import Flask, time, Decimal, uuid
  - Initialize ConfigManager, DatabaseManager, TokenManager, CloudTasksClient
  - Pattern: Copy from `GCAccumulator-10-26/acc10-26.py` (lines 1-59)

- [ ] **3.2.2** Implement `/check-threshold` endpoint (Cron-triggered)
  ```python
  @app.route("/check-threshold", methods=["POST"])
  def check_threshold():
      """
      Triggered by Cloud Scheduler every 15 minutes.

      Flow:
      1. Fetch threshold from Google Cloud Secret
      2. Query total pending USD
      3. If total >= threshold:
         a. Create ChangeNow ETH→USDT swap
         b. Update all pending records to 'swapping'
         c. Enqueue to GCHostPay1
      """
  ```

  **Key Logic:**
  - Fetch threshold: `threshold = config_manager.get_micro_batch_threshold()`
  - Query total: `total_pending = db_manager.get_total_pending_usd()`
  - Check: `if total_pending >= threshold:`
  - Create batch: `batch_id = str(uuid.uuid4())`
  - Call ChangeNow API: Use pattern from `GCSplit3-10-26/tps3-10-26.py` (lines 231-375)
  - Update records: `db_manager.update_records_to_swapping(batch_id)`
  - Enqueue to GCHostPay1: Create encrypted token with context='batch'

- [ ] **3.2.3** Implement `/swap-executed` endpoint (Callback from GCHostPay1)
  ```python
  @app.route("/swap-executed", methods=["POST"])
  def swap_executed():
      """
      Receives callback from GCHostPay1 after ETH payment executed.

      Flow:
      1. Decrypt token from GCHostPay1
      2. Fetch all pending records for batch_conversion_id
      3. Calculate proportional USDT distribution
      4. Update each record with usdt_share
      5. Mark batch as completed
      """
  ```

  **Key Logic:**
  - Decrypt token: `decrypted_data = token_manager.decrypt_gchostpay1_to_microbatch_token()`
  - Fetch records: `records = db_manager.get_records_by_batch(batch_conversion_id)`
  - Distribute: `distributions = distribute_usdt_proportionally(records, actual_usdt_received)`
  - Update records: Loop through distributions and update each
  - Finalize: `db_manager.finalize_batch_conversion(batch_conversion_id)`

- [ ] **3.2.4** Implement `/health` endpoint
  ```python
  @app.route("/health", methods=["GET"])
  def health_check():
      """Health check endpoint for monitoring."""
      return jsonify({
          "status": "healthy",
          "service": "GCMicroBatchProcessor-10-26",
          "timestamp": int(time.time())
      }), 200
  ```

#### 3.3 - Database Manager: `database_manager.py`

**Reference Pattern:** `GCBatchProcessor-10-26/database_manager.py`

- [ ] **3.3.1** Create `database_manager.py` with DatabaseManager class
  - Copy initialization pattern from `GCAccumulator-10-26/database_manager.py` (lines 1-58)

- [ ] **3.3.2** Implement `get_total_pending_usd()` method
  ```python
  def get_total_pending_usd(self) -> Decimal:
      """
      Get total USD accumulated across all pending payments.

      Returns:
          Decimal total pending USD
      """
      cur.execute(
          """SELECT COALESCE(SUM(accumulated_eth), 0) as total_pending
             FROM payout_accumulation
             WHERE conversion_status = 'pending'"""
      )
  ```

- [ ] **3.3.3** Implement `get_all_pending_records()` method
  ```python
  def get_all_pending_records(self) -> List[Dict]:
      """
      Fetch all pending payment records for batch processing.

      Returns:
          List of dicts with id, accumulated_eth, client_id, user_id
      """
      cur.execute(
          """SELECT id, accumulated_eth, client_id, user_id,
                    client_wallet_address, client_payout_currency, client_payout_network
             FROM payout_accumulation
             WHERE conversion_status = 'pending'
             ORDER BY created_at ASC"""
      )
  ```

- [ ] **3.3.4** Implement `create_batch_conversion()` method
  ```python
  def create_batch_conversion(
      self,
      batch_conversion_id: str,
      total_eth_usd: Decimal,
      threshold: Decimal,
      cn_api_id: str,
      payin_address: str
  ) -> bool:
      """
      Create batch_conversions record.

      Returns:
          True if successful, False if failed
      """
      cur.execute(
          """INSERT INTO batch_conversions (
              batch_conversion_id, total_eth_usd, threshold_at_creation,
              cn_api_id, payin_address, conversion_status, processing_started_at
          ) VALUES (%s, %s, %s, %s, %s, 'swapping', NOW())""",
          (batch_conversion_id, total_eth_usd, threshold, cn_api_id, payin_address)
      )
  ```

- [ ] **3.3.5** Implement `update_records_to_swapping()` method
  ```python
  def update_records_to_swapping(
      self,
      batch_conversion_id: str
  ) -> bool:
      """
      Update all pending records to 'swapping' status with batch_conversion_id.

      Returns:
          True if successful, False if failed
      """
      cur.execute(
          """UPDATE payout_accumulation
             SET conversion_status = 'swapping',
                 batch_conversion_id = %s,
                 updated_at = NOW()
             WHERE conversion_status = 'pending'""",
          (batch_conversion_id,)
      )
  ```

- [ ] **3.3.6** Implement `get_records_by_batch()` method
  ```python
  def get_records_by_batch(
      self,
      batch_conversion_id: str
  ) -> List[Dict]:
      """
      Fetch all records for a batch_conversion_id.

      Returns:
          List of dicts with id, accumulated_eth, client_id, user_id
      """
      cur.execute(
          """SELECT id, accumulated_eth
             FROM payout_accumulation
             WHERE batch_conversion_id = %s""",
          (batch_conversion_id,)
      )
  ```

- [ ] **3.3.7** Implement `distribute_usdt_proportionally()` method
  ```python
  def distribute_usdt_proportionally(
      self,
      pending_records: List[Dict],
      actual_usdt_received: Decimal
  ) -> List[Dict]:
      """
      Distribute actual USDT received proportionally across pending records.

      Formula: usdt_share_i = (payment_i / total_pending) × actual_usdt_received

      Returns:
          List of dicts with 'id' and 'usdt_share'
      """
      from decimal import getcontext
      getcontext().prec = 28

      total_pending = sum(Decimal(str(r['accumulated_eth'])) for r in pending_records)

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
              'usdt_share': usdt_share
          })

      return distributions
  ```

- [ ] **3.3.8** Implement `update_record_usdt_share()` method
  ```python
  def update_record_usdt_share(
      self,
      record_id: int,
      usdt_share: Decimal,
      tx_hash: str
  ) -> bool:
      """
      Update individual record with USDT share and mark completed.

      Returns:
          True if successful, False if failed
      """
      cur.execute(
          """UPDATE payout_accumulation
             SET accumulated_amount_usdt = %s,
                 conversion_status = 'completed',
                 conversion_tx_hash = %s,
                 updated_at = NOW()
             WHERE id = %s""",
          (usdt_share, tx_hash, record_id)
      )
  ```

- [ ] **3.3.9** Implement `finalize_batch_conversion()` method
  ```python
  def finalize_batch_conversion(
      self,
      batch_conversion_id: str,
      actual_usdt_received: Decimal,
      tx_hash: str
  ) -> bool:
      """
      Mark batch_conversion as completed.

      Returns:
          True if successful, False if failed
      """
      cur.execute(
          """UPDATE batch_conversions
             SET actual_usdt_received = %s,
                 conversion_tx_hash = %s,
                 conversion_status = 'completed',
                 completed_at = NOW()
             WHERE batch_conversion_id = %s""",
          (actual_usdt_received, tx_hash, batch_conversion_id)
      )
  ```

#### 3.4 - Config Manager: `config_manager.py`

**Reference Pattern:** `GCAccumulator-10-26/config_manager.py`

- [ ] **3.4.1** Create `config_manager.py` with ConfigManager class
  - Copy base class from `GCAccumulator-10-26/config_manager.py`
  - Keep all existing secret fetching methods

- [ ] **3.4.2** Add `get_micro_batch_threshold()` method
  ```python
  from google.cloud import secretmanager
  from decimal import Decimal

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
          print(f"⚠️ [CONFIG] Using fallback threshold: $20.00")
          return Decimal('20.00')
  ```

#### 3.5 - Token Manager: `token_manager.py`

**Reference Pattern:** `GCAccumulator-10-26/token_manager.py`

- [ ] **3.5.1** Create `token_manager.py` with TokenManager class
  - Copy base class from `GCAccumulator-10-26/token_manager.py` (lines 1-127)
  - Include `_pack_string()` and `_unpack_string()` helper methods

- [ ] **3.5.2** Implement `encrypt_microbatch_to_gchostpay1_token()` method
  ```python
  def encrypt_microbatch_to_gchostpay1_token(
      self,
      batch_conversion_id: str,
      cn_api_id: str,
      from_currency: str,
      from_network: str,
      from_amount: float,
      payin_address: str
  ) -> Optional[str]:
      """
      Encrypt token for GCHostPay1 batch execution request.

      Token Structure:
      - 1 byte: context ('batch')
      - 1 byte: batch_conversion_id length + variable bytes
      - 1 byte: cn_api_id length + variable bytes
      - ... (rest similar to GCAccumulator pattern)

      Returns:
          Base64 URL-safe encoded token or None if failed
      """
      try:
          payload = bytearray()

          # Pack context
          payload.extend(self._pack_string('batch'))

          # Pack batch_conversion_id (UUID as string)
          payload.extend(self._pack_string(batch_conversion_id))

          # Pack cn_api_id
          payload.extend(self._pack_string(cn_api_id))

          # Pack from_currency
          payload.extend(self._pack_string(from_currency))

          # Pack from_network
          payload.extend(self._pack_string(from_network))

          # Pack from_amount (8 bytes, double)
          payload.extend(struct.pack(">d", from_amount))

          # Pack payin_address
          payload.extend(self._pack_string(payin_address))

          # Pack timestamp (8 bytes, uint64)
          timestamp = int(time.time())
          payload.extend(struct.pack(">Q", timestamp))

          # Generate HMAC signature
          signature = hmac.new(
              self.signing_key.encode(),
              bytes(payload),
              hashlib.sha256
          ).digest()[:16]

          # Combine payload + signature
          full_data = bytes(payload) + signature

          # Base64 encode
          token = base64.urlsafe_b64encode(full_data).decode('utf-8').rstrip('=')

          return token

      except Exception as e:
          print(f"❌ [TOKEN_ENC] Encryption error: {e}")
          return None
  ```

- [ ] **3.5.3** Implement `decrypt_gchostpay1_to_microbatch_token()` method
  ```python
  def decrypt_gchostpay1_to_microbatch_token(self, token: str) -> Optional[Dict[str, Any]]:
      """
      Decrypt token from GCHostPay1 with batch execution completion details.

      Expected fields:
      - batch_conversion_id (str)
      - cn_api_id (str)
      - tx_hash (str)
      - actual_usdt_received (float)
      - timestamp (int)

      Returns:
          Dictionary with decrypted data or None if failed
      """
      try:
          # Decode base64
          padding = 4 - (len(token) % 4) if len(token) % 4 != 0 else 0
          token_padded = token + ('=' * padding)
          data = base64.urlsafe_b64decode(token_padded)

          if len(data) < 16:
              raise ValueError("Token too short")

          payload = data[:-16]
          provided_signature = data[-16:]

          # Verify signature
          expected_signature = hmac.new(
              self.signing_key.encode(),
              payload,
              hashlib.sha256
          ).digest()[:16]

          if not hmac.compare_digest(provided_signature, expected_signature):
              raise ValueError("Invalid signature")

          offset = 0

          # Unpack batch_conversion_id (variable length string)
          batch_conversion_id, offset = self._unpack_string(payload, offset)

          # Unpack cn_api_id (variable length string)
          cn_api_id, offset = self._unpack_string(payload, offset)

          # Unpack tx_hash (variable length string)
          tx_hash, offset = self._unpack_string(payload, offset)

          # Unpack actual_usdt_received (8 bytes, double)
          actual_usdt_received = struct.unpack(">d", payload[offset:offset + 8])[0]
          offset += 8

          # Unpack timestamp (8 bytes, uint64)
          timestamp = struct.unpack(">Q", payload[offset:offset + 8])[0]
          offset += 8

          # Validate timestamp (5 minutes = 300 seconds)
          current_time = int(time.time())
          if not (current_time - 300 <= timestamp <= current_time + 5):
              raise ValueError("Token expired")

          return {
              "batch_conversion_id": batch_conversion_id,
              "cn_api_id": cn_api_id,
              "tx_hash": tx_hash,
              "actual_usdt_received": actual_usdt_received,
              "timestamp": timestamp
          }

      except Exception as e:
          print(f"❌ [TOKEN_DEC] Decryption error: {e}")
          return None
  ```

#### 3.6 - Cloud Tasks Client: `cloudtasks_client.py`

**Reference Pattern:** `GCAccumulator-10-26/cloudtasks_client.py`

- [ ] **3.6.1** Create `cloudtasks_client.py` with CloudTasksClient class
  - Copy base class from `GCAccumulator-10-26/cloudtasks_client.py`

- [ ] **3.6.2** Implement `enqueue_gchostpay1_batch_execution()` method
  ```python
  def enqueue_gchostpay1_batch_execution(
      self,
      queue_name: str,
      target_url: str,
      encrypted_token: str
  ) -> Optional[str]:
      """
      Enqueue batch execution task to GCHostPay1.

      Args:
          queue_name: GCHostPay1 batch queue name
          target_url: GCHostPay1 service URL
          encrypted_token: Encrypted token with batch details

      Returns:
          Task name if successful, None if failed
      """
      # Copy pattern from existing enqueue methods
  ```

#### 3.7 - ChangeNow Client: `changenow_client.py`

- [ ] **3.7.1** Copy `changenow_client.py` from GCSplit3-10-26
  ```bash
  cp /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit3-10-26/changenow_client.py \
     /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCMicroBatchProcessor-10-26/
  ```

  - No modifications needed - reuse existing infinite retry logic

#### 3.8 - Docker Configuration

- [ ] **3.8.1** Create `Dockerfile`
  ```dockerfile
  FROM python:3.11-slim

  WORKDIR /app

  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  COPY . .

  CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 microbatch10-26:app
  ```

- [ ] **3.8.2** Create `requirements.txt`
  ```
  Flask==3.0.0
  gunicorn==21.2.0
  google-cloud-secret-manager==2.16.4
  cloud-sql-python-connector[pg8000]==1.5.0
  pg8000==1.30.3
  google-cloud-tasks==2.14.2
  requests==2.31.0
  ```

- [ ] **3.8.3** Create `.dockerignore`
  ```
  __pycache__
  *.pyc
  .env
  .git
  .gitignore
  README.md
  *.md
  ```

#### 3.9 - Local Testing

- [ ] **3.9.1** Test service locally with mock data
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCMicroBatchProcessor-10-26

  # Set environment variables
  export PORT=8080
  export GOOGLE_CLOUD_PROJECT=telepay-459221

  # Run service
  python microbatch10-26.py
  ```

- [ ] **3.9.2** Test `/health` endpoint
  ```bash
  curl http://localhost:8080/health
  ```

- [ ] **3.9.3** Test `/check-threshold` endpoint with mock data
  ```bash
  curl -X POST http://localhost:8080/check-threshold
  ```

---

### ✅ Phase 4: Modify GCAccumulator-10-26

#### 4.1 - Backup Current Service

- [ ] **4.1.1** Create backup of GCAccumulator
  ```bash
  cp -r /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCAccumulator-10-26 \
        /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/ARCHIVES/GCAccumulator-10-26-BACKUP-$(date +%Y%m%d)
  ```

#### 4.2 - Modify `acc10-26.py`

- [ ] **4.2.1** Remove lines 146-191 (GCSplit3 swap queuing logic)
  **REMOVE THIS CODE BLOCK:**
  ```python
  # Queue task to GCSplit3 for ACTUAL ETH→USDT swap creation
  if not cloudtasks_client:
      print(f"❌ [ENDPOINT] Cloud Tasks client not available")
      abort(500, "Cloud Tasks unavailable")

  if not token_manager:
      print(f"❌ [ENDPOINT] Token manager not available")
      abort(500, "Token manager unavailable")

  gcsplit3_queue = config.get('gcsplit3_queue')
  gcsplit3_url = config.get('gcsplit3_url')
  host_wallet_usdt = config.get('host_wallet_usdt_address')

  # ... rest of GCSplit3 queuing code ...
  ```

- [ ] **4.2.2** Update response message at lines 194-201
  **CHANGE FROM:**
  ```python
  return jsonify({
      "status": "success",
      "message": "Payment accumulated successfully, ETH→USDT swap pending",
      "accumulation_id": accumulation_id,
      "accumulated_eth": str(accumulated_eth),
      "swap_task": task_name,
      "conversion_status": "pending"
  }), 200
  ```

  **CHANGE TO:**
  ```python
  print(f"✅ [ENDPOINT] Payment accumulated (awaiting micro-batch conversion)")
  print(f"⏳ [ENDPOINT] Conversion will occur when batch threshold reached")

  return jsonify({
      "status": "success",
      "message": "Payment accumulated successfully (micro-batch pending)",
      "accumulation_id": accumulation_id,
      "accumulated_eth": str(accumulated_eth),
      "conversion_status": "pending"
  }), 200
  ```

- [ ] **4.2.3** Remove `/swap-created` endpoint (lines 211-333)
  - Delete entire endpoint function
  - This callback is no longer needed

- [ ] **4.2.4** Remove `/swap-executed` endpoint (lines 336-417)
  - Delete entire endpoint function
  - This logic moves to GCMicroBatchProcessor

- [ ] **4.2.5** Keep `/health` endpoint unchanged (lines 420-441)

#### 4.3 - Test Modified GCAccumulator Locally

- [ ] **4.3.1** Run modified service locally
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCAccumulator-10-26
  python acc10-26.py
  ```

- [ ] **4.3.2** Test POST / endpoint with mock payment data
  ```bash
  curl -X POST http://localhost:8080/ \
      -H "Content-Type: application/json" \
      -d '{
          "user_id": 12345,
          "client_id": "test_client",
          "wallet_address": "0xtest",
          "payout_currency": "xmr",
          "payout_network": "xmr",
          "payment_amount_usd": 10.00,
          "subscription_id": 1,
          "payment_timestamp": "2025-10-31T12:00:00Z"
      }'
  ```

  - Expected: 200 response with "micro-batch pending" message
  - Expected: NO task queued to GCSplit3
  - Expected: Database record created with conversion_status='pending'

---

### ✅ Phase 5: Modify GCHostPay1-10-26

#### 5.1 - Update `tphp1-10-26.py`

- [ ] **5.1.1** Update token decryption to handle context
  **ADD CONTEXT HANDLING:**
  ```python
  # After decrypting token
  decrypted_data = token_manager.decrypt_token(encrypted_token)
  context = decrypted_data.get('context', 'individual')  # 'individual' or 'batch'

  print(f"📋 [ENDPOINT] Payment context: {context}")

  if context == 'batch':
      batch_conversion_id = decrypted_data['batch_conversion_id']
      print(f"🆔 [ENDPOINT] Batch Conversion ID: {batch_conversion_id}")

      # Use batch callback configuration
      callback_queue = config.get('microbatch_response_queue')
      callback_url = config.get('microbatch_url')
      callback_endpoint = '/swap-executed'
  else:
      accumulation_id = decrypted_data['accumulation_id']
      print(f"🆔 [ENDPOINT] Accumulation ID: {accumulation_id}")

      # Use individual callback configuration (for debugging/fallback)
      callback_queue = config.get('accumulator_response_queue')
      callback_url = config.get('accumulator_url')
      callback_endpoint = '/swap-executed'
  ```

- [ ] **5.1.2** Update callback token encryption for batch context
  ```python
  if context == 'batch':
      # Encrypt response for MicroBatchProcessor
      response_token = token_manager.encrypt_gchostpay1_to_microbatch_response_token(
          batch_conversion_id=batch_conversion_id,
          cn_api_id=cn_api_id,
          tx_hash=tx_hash,
          actual_usdt_received=actual_usdt_received
      )
  else:
      # Encrypt response for GCAccumulator (existing logic)
      response_token = token_manager.encrypt_gchostpay1_to_accumulator_token(...)
  ```

#### 5.2 - Update `token_manager.py`

- [ ] **5.2.1** Add `decrypt_token()` method to extract context
  ```python
  def decrypt_token(self, token: str) -> Optional[Dict[str, Any]]:
      """
      Generic token decryption that extracts context first.
      Routes to appropriate specific decryption method.
      """
      # Decode base64
      padding = 4 - (len(token) % 4) if len(token) % 4 != 0 else 0
      token_padded = token + ('=' * padding)
      data = base64.urlsafe_b64decode(token_padded)

      payload = data[:-16]

      # Extract context (first field)
      context, offset = self._unpack_string(payload, 0)

      # Route to specific decryption
      if context == 'batch':
          return self.decrypt_accumulator_to_gchostpay1_batch_token(token)
      else:
          return self.decrypt_accumulator_to_gchostpay1_token(token)
  ```

- [ ] **5.2.2** Add `decrypt_accumulator_to_gchostpay1_batch_token()` method
  ```python
  def decrypt_accumulator_to_gchostpay1_batch_token(self, token: str) -> Optional[Dict[str, Any]]:
      """
      Decrypt batch execution token from MicroBatchProcessor.

      Expected fields:
      - context = 'batch'
      - batch_conversion_id (str)
      - cn_api_id (str)
      - from_currency (str)
      - from_network (str)
      - from_amount (float)
      - payin_address (str)
      - timestamp (int)
      """
      # Implementation similar to existing decryption pattern
  ```

- [ ] **5.2.3** Add `encrypt_gchostpay1_to_microbatch_response_token()` method
  ```python
  def encrypt_gchostpay1_to_microbatch_response_token(
      self,
      batch_conversion_id: str,
      cn_api_id: str,
      tx_hash: str,
      actual_usdt_received: float
  ) -> Optional[str]:
      """
      Encrypt response token for MicroBatchProcessor after execution.
      """
      # Implementation following existing encryption pattern
  ```

#### 5.3 - Test GCHostPay1 Modifications

- [ ] **5.3.1** Test locally with mock batch token
- [ ] **5.3.2** Verify context handling works correctly
- [ ] **5.3.3** Verify callback routing to correct service

---

### ✅ Phase 6: Cloud Tasks Queues Setup

- [ ] **6.1** Create `GCHOSTPAY1_BATCH_QUEUE` queue
  ```bash
  gcloud tasks queues create gchostpay1-batch-queue \
      --location=us-central1 \
      --max-concurrent-dispatches=10 \
      --max-attempts=10 \
      --max-retry-duration=24h \
      --project=telepay-459221
  ```

- [ ] **6.2** Create `MICROBATCH_RESPONSE_QUEUE` queue
  ```bash
  gcloud tasks queues create microbatch-response-queue \
      --location=us-central1 \
      --max-concurrent-dispatches=10 \
      --max-attempts=10 \
      --max-retry-duration=24h \
      --project=telepay-459221
  ```

- [ ] **6.3** Store queue names in Secret Manager
  ```bash
  # GCHOSTPAY1_BATCH_QUEUE
  echo -n "gchostpay1-batch-queue" | \
      gcloud secrets create GCHOSTPAY1_BATCH_QUEUE \
      --data-file=- \
      --replication-policy="automatic" \
      --project=telepay-459221

  # MICROBATCH_RESPONSE_QUEUE
  echo -n "microbatch-response-queue" | \
      gcloud secrets create MICROBATCH_RESPONSE_QUEUE \
      --data-file=- \
      --replication-policy="automatic" \
      --project=telepay-459221
  ```

- [ ] **6.4** Verify queues created
  ```bash
  gcloud tasks queues list --location=us-central1 --project=telepay-459221 | grep batch
  ```

---

### ✅ Phase 7: Deploy GCMicroBatchProcessor-10-26

- [ ] **7.1** Build Docker image
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCMicroBatchProcessor-10-26

  gcloud builds submit --tag gcr.io/telepay-459221/gcmicrobatchprocessor-10-26 \
      --project=telepay-459221
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
      --add-cloudsql-instances telepay-459221:us-central1:telepaypsql \
      --project=telepay-459221
  ```

- [ ] **7.3** Get service URL and store in Secret Manager
  ```bash
  # Get URL
  SERVICE_URL=$(gcloud run services describe gcmicrobatchprocessor-10-26 \
      --region us-central1 \
      --format='value(status.url)' \
      --project=telepay-459221)

  echo "Service URL: $SERVICE_URL"

  # Store in Secret Manager
  echo -n "$SERVICE_URL" | \
      gcloud secrets create MICROBATCH_URL \
      --data-file=- \
      --replication-policy="automatic" \
      --project=telepay-459221
  ```

- [ ] **7.4** Grant Secret Manager access to service account
  ```bash
  # Get service account email
  SERVICE_ACCOUNT=$(gcloud run services describe gcmicrobatchprocessor-10-26 \
      --region us-central1 \
      --format='value(spec.template.spec.serviceAccountName)' \
      --project=telepay-459221)

  echo "Service Account: $SERVICE_ACCOUNT"

  # Grant access to MICRO_BATCH_THRESHOLD_USD
  gcloud secrets add-iam-policy-binding MICRO_BATCH_THRESHOLD_USD \
      --member="serviceAccount:${SERVICE_ACCOUNT}" \
      --role="roles/secretmanager.secretAccessor" \
      --project=telepay-459221

  # Grant access to other required secrets
  for SECRET in CLOUD_SQL_CONNECTION_NAME DATABASE_NAME_SECRET DATABASE_USER_SECRET \
                DATABASE_PASSWORD_SECRET SUCCESS_URL_SIGNING_KEY CHANGENOW_API_KEY \
                GCHOSTPAY1_BATCH_QUEUE MICROBATCH_RESPONSE_QUEUE \
                GCHOSTPAY1_URL HOST_WALLET_USDT_ADDRESS; do
      echo "Granting access to $SECRET"
      gcloud secrets add-iam-policy-binding $SECRET \
          --member="serviceAccount:${SERVICE_ACCOUNT}" \
          --role="roles/secretmanager.secretAccessor" \
          --project=telepay-459221
  done
  ```

- [ ] **7.5** Test health endpoint
  ```bash
  SERVICE_URL=$(gcloud run services describe gcmicrobatchprocessor-10-26 \
      --region us-central1 \
      --format='value(status.url)' \
      --project=telepay-459221)

  curl $SERVICE_URL/health
  ```

  Expected output:
  ```json
  {
    "status": "healthy",
    "service": "GCMicroBatchProcessor-10-26",
    "timestamp": 1698758400
  }
  ```

---

### ✅ Phase 8: Cloud Scheduler Setup

- [ ] **8.1** Create Cloud Scheduler job (15-minute interval)
  ```bash
  # Get service URL
  SERVICE_URL=$(gcloud run services describe gcmicrobatchprocessor-10-26 \
      --region us-central1 \
      --format='value(status.url)' \
      --project=telepay-459221)

  # Get service account
  SERVICE_ACCOUNT=$(gcloud run services describe gcmicrobatchprocessor-10-26 \
      --region us-central1 \
      --format='value(spec.template.spec.serviceAccountName)' \
      --project=telepay-459221)

  # Create scheduler job
  gcloud scheduler jobs create http micro-batch-conversion-job \
      --location=us-central1 \
      --schedule="*/15 * * * *" \
      --uri="${SERVICE_URL}/check-threshold" \
      --http-method=POST \
      --oidc-service-account-email="${SERVICE_ACCOUNT}" \
      --oidc-token-audience="${SERVICE_URL}" \
      --project=telepay-459221
  ```

- [ ] **8.2** Test manual trigger
  ```bash
  gcloud scheduler jobs run micro-batch-conversion-job \
      --location=us-central1 \
      --project=telepay-459221
  ```

- [ ] **8.3** Verify job created and running
  ```bash
  gcloud scheduler jobs describe micro-batch-conversion-job \
      --location=us-central1 \
      --project=telepay-459221
  ```

---

### ✅ Phase 9: Redeploy Modified Services

#### 9.1 - Redeploy GCAccumulator-10-26

- [ ] **9.1.1** Build modified image
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCAccumulator-10-26

  gcloud builds submit --tag gcr.io/telepay-459221/gcaccumulator-10-26 \
      --project=telepay-459221
  ```

- [ ] **9.1.2** Deploy to Cloud Run
  ```bash
  gcloud run deploy gcaccumulator-10-26 \
      --image gcr.io/telepay-459221/gcaccumulator-10-26 \
      --platform managed \
      --region us-central1 \
      --project=telepay-459221
  ```

- [ ] **9.1.3** Verify deployment
  ```bash
  SERVICE_URL=$(gcloud run services describe gcaccumulator-10-26 \
      --region us-central1 \
      --format='value(status.url)' \
      --project=telepay-459221)

  curl $SERVICE_URL/health
  ```

#### 9.2 - Redeploy GCHostPay1-10-26

- [ ] **9.2.1** Build modified image
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay1-10-26

  gcloud builds submit --tag gcr.io/telepay-459221/gchostpay1-10-26 \
      --project=telepay-459221
  ```

- [ ] **9.2.2** Deploy to Cloud Run
  ```bash
  gcloud run deploy gchostpay1-10-26 \
      --image gcr.io/telepay-459221/gchostpay1-10-26 \
      --platform managed \
      --region us-central1 \
      --project=telepay-459221
  ```

- [ ] **9.2.3** Verify deployment
  ```bash
  SERVICE_URL=$(gcloud run services describe gchostpay1-10-26 \
      --region us-central1 \
      --format='value(status.url)' \
      --project=telepay-459221)

  curl $SERVICE_URL/health
  ```

---

### ✅ Phase 10: Testing and Verification

#### 10.1 - Test Payment Accumulation (No Immediate Swap)

- [ ] **10.1.1** Send test payment via GCWebhook1
  ```bash
  # Test payment will trigger GCWebhook1 → GCAccumulator flow
  # Use test Telegram payment or mock webhook call
  ```

- [ ] **10.1.2** Verify database record created
  ```bash
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT id, accumulated_eth, conversion_status
           FROM payout_accumulation
           ORDER BY created_at DESC LIMIT 5;"
  ```

  Expected: conversion_status = 'pending'

- [ ] **10.1.3** Verify NO task queued to GCSplit3
  ```bash
  # Check GCSplit3 logs - should be empty for this payment
  gcloud logging read 'resource.type="cloud_run_revision"
      resource.labels.service_name="gcsplit3-10-26"' \
      --limit 10 \
      --format json \
      --project=telepay-459221
  ```

- [ ] **10.1.4** Verify NO ChangeNow swap created
  - Check ChangeNow dashboard - no new transactions

#### 10.2 - Test Threshold Check (Below Threshold)

- [ ] **10.2.1** Ensure total pending < $20
  ```bash
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT COALESCE(SUM(accumulated_eth), 0) as total_pending
           FROM payout_accumulation
           WHERE conversion_status = 'pending';"
  ```

- [ ] **10.2.2** Manual trigger Cloud Scheduler
  ```bash
  gcloud scheduler jobs run micro-batch-conversion-job \
      --location=us-central1 \
      --project=telepay-459221
  ```

- [ ] **10.2.3** Verify logs show "below threshold - no action"
  ```bash
  gcloud logging read 'resource.type="cloud_run_revision"
      resource.labels.service_name="gcmicrobatchprocessor-10-26"' \
      --limit 20 \
      --format json \
      --project=telepay-459221 | grep "below threshold"
  ```

#### 10.3 - Test Threshold Check (Above Threshold)

- [ ] **10.3.1** Accumulate multiple payments until total >= $20
  ```bash
  # Send additional test payments via GCWebhook1
  # Verify total pending:
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT COALESCE(SUM(accumulated_eth), 0) as total_pending
           FROM payout_accumulation
           WHERE conversion_status = 'pending';"
  ```

- [ ] **10.3.2** Manual trigger Cloud Scheduler
  ```bash
  gcloud scheduler jobs run micro-batch-conversion-job \
      --location=us-central1 \
      --project=telepay-459221
  ```

- [ ] **10.3.3** Verify logs show batch creation
  ```bash
  gcloud logging read 'resource.type="cloud_run_revision"
      resource.labels.service_name="gcmicrobatchprocessor-10-26"
      jsonPayload.message=~"creating batch"' \
      --limit 50 \
      --format json \
      --project=telepay-459221
  ```

- [ ] **10.3.4** Verify batch_conversions record created
  ```bash
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT * FROM batch_conversions ORDER BY created_at DESC LIMIT 1;"
  ```

  Expected: conversion_status = 'swapping'

- [ ] **10.3.5** Verify all pending records updated to 'swapping'
  ```bash
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT id, conversion_status, batch_conversion_id
           FROM payout_accumulation
           WHERE batch_conversion_id IS NOT NULL
           ORDER BY created_at DESC;"
  ```

- [ ] **10.3.6** Verify task queued to GCHostPay1
  ```bash
  gcloud logging read 'resource.type="cloud_run_revision"
      resource.labels.service_name="gchostpay1-10-26"' \
      --limit 20 \
      --format json \
      --project=telepay-459221
  ```

- [ ] **10.3.7** Verify ChangeNow swap created
  - Check ChangeNow dashboard for new transaction
  - Verify transaction amount matches total_eth_usd

#### 10.4 - Test Swap Execution and Proportional Distribution

- [ ] **10.4.1** Wait for GCHostPay1 to execute swap
  - Monitor GCHostPay1 logs for execution
  - Monitor Alchemy webhook for payment confirmation

- [ ] **10.4.2** Verify callback to MicroBatchProcessor /swap-executed
  ```bash
  gcloud logging read 'resource.type="cloud_run_revision"
      resource.labels.service_name="gcmicrobatchprocessor-10-26"
      jsonPayload.message=~"swap executed"' \
      --limit 50 \
      --format json \
      --project=telepay-459221
  ```

- [ ] **10.4.3** Verify proportional distribution calculations in logs
  ```bash
  gcloud logging read 'resource.type="cloud_run_revision"
      resource.labels.service_name="gcmicrobatchprocessor-10-26"
      jsonPayload.message=~"DISTRIBUTION"' \
      --limit 100 \
      --format json \
      --project=telepay-459221
  ```

- [ ] **10.4.4** Verify all records updated with USDT shares
  ```bash
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT id, accumulated_eth, accumulated_amount_usdt, conversion_status
           FROM payout_accumulation
           WHERE batch_conversion_id IS NOT NULL
           ORDER BY created_at DESC;"
  ```

  Expected:
  - accumulated_amount_usdt populated (proportional shares)
  - conversion_status = 'completed'
  - conversion_tx_hash populated

- [ ] **10.4.5** Verify batch_conversions marked completed
  ```bash
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT batch_conversion_id, total_eth_usd, actual_usdt_received,
                  conversion_status, completed_at
           FROM batch_conversions
           ORDER BY created_at DESC LIMIT 1;"
  ```

  Expected: conversion_status = 'completed', completed_at populated

- [ ] **10.4.6** Verify proportional distribution math accuracy
  ```bash
  # Calculate: SUM(accumulated_amount_usdt) should equal actual_usdt_received
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT
              bc.actual_usdt_received as batch_total,
              SUM(pa.accumulated_amount_usdt) as distributed_total,
              bc.actual_usdt_received - SUM(pa.accumulated_amount_usdt) as difference
           FROM batch_conversions bc
           JOIN payout_accumulation pa ON bc.batch_conversion_id = pa.batch_conversion_id
           GROUP BY bc.batch_conversion_id, bc.actual_usdt_received
           ORDER BY bc.created_at DESC LIMIT 1;"
  ```

  Expected: difference = 0 (or < 0.01 due to rounding)

#### 10.5 - Test Threshold Scaling

- [ ] **10.5.1** Update threshold to $100
  ```bash
  echo -n "100.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD \
      --data-file=- \
      --project=telepay-459221
  ```

- [ ] **10.5.2** Verify MicroBatchProcessor fetches new threshold
  ```bash
  # Trigger scheduler
  gcloud scheduler jobs run micro-batch-conversion-job \
      --location=us-central1 \
      --project=telepay-459221

  # Check logs for threshold value
  gcloud logging read 'resource.type="cloud_run_revision"
      resource.labels.service_name="gcmicrobatchprocessor-10-26"
      jsonPayload.message=~"Threshold fetched"' \
      --limit 10 \
      --format json \
      --project=telepay-459221
  ```

  Expected: Logs show "Threshold fetched: $100"

- [ ] **10.5.3** Verify batches only created when total_pending >= $100
  - Accumulate payments below $100
  - Trigger scheduler - verify no batch created
  - Accumulate more payments to reach $100+
  - Trigger scheduler - verify batch created

---

### ✅ Phase 11: Monitoring and Observability

- [ ] **11.1** Set up log-based metrics
  ```bash
  # Metric: Batch conversions created
  gcloud logging metrics create micro_batch_conversions_created \
      --description="Count of micro-batch conversions created" \
      --log-filter='resource.type="cloud_run_revision"
      resource.labels.service_name="gcmicrobatchprocessor-10-26"
      jsonPayload.message=~"Batch conversion created"' \
      --project=telepay-459221

  # Metric: Batch conversions completed
  gcloud logging metrics create micro_batch_conversions_completed \
      --description="Count of micro-batch conversions completed" \
      --log-filter='resource.type="cloud_run_revision"
      resource.labels.service_name="gcmicrobatchprocessor-10-26"
      jsonPayload.message=~"Batch conversion finalized"' \
      --project=telepay-459221

  # Metric: Pending USD total
  gcloud logging metrics create micro_batch_pending_usd \
      --description="Total USD pending conversion" \
      --log-filter='resource.type="cloud_run_revision"
      resource.labels.service_name="gcmicrobatchprocessor-10-26"
      jsonPayload.message=~"Total pending"' \
      --value-extractor='EXTRACT(jsonPayload.pending_usd)' \
      --project=telepay-459221
  ```

- [ ] **11.2** Create dashboard queries
  ```bash
  # Query: Total pending payments
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT
              COUNT(*) as pending_count,
              COALESCE(SUM(accumulated_eth), 0) as total_pending_usd
           FROM payout_accumulation
           WHERE conversion_status = 'pending';"

  # Query: Batch conversion stats (last 7 days)
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT
              DATE(created_at) as date,
              COUNT(*) as batch_count,
              AVG(total_eth_usd) as avg_batch_size,
              SUM(total_eth_usd) as total_converted
           FROM batch_conversions
           WHERE created_at >= NOW() - INTERVAL '7 days'
           GROUP BY DATE(created_at)
           ORDER BY date DESC;"

  # Query: Distribution accuracy check
  psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
       -U postgres -d telepaydb \
       -c "SELECT
              bc.batch_conversion_id,
              bc.actual_usdt_received,
              SUM(pa.accumulated_amount_usdt) as distributed_total,
              ABS(bc.actual_usdt_received - SUM(pa.accumulated_amount_usdt)) as rounding_error
           FROM batch_conversions bc
           JOIN payout_accumulation pa ON bc.batch_conversion_id = pa.batch_conversion_id
           WHERE bc.conversion_status = 'completed'
           GROUP BY bc.batch_conversion_id, bc.actual_usdt_received
           ORDER BY bc.created_at DESC
           LIMIT 10;"
  ```

- [ ] **11.3** Set up alerting (optional)
  - Alert if no batches created in 48 hours (may indicate traffic drop or service issue)
  - Alert if batch failure rate > 5%
  - Alert if rounding error > $0.10 (distribution math issue)

---

## 📊 Post-Deployment Monitoring

### Week 1: Launch Phase ($20 Threshold)

- [ ] **Daily:** Check total pending USD
  ```bash
  psql -c "SELECT COUNT(*), SUM(accumulated_eth)
           FROM payout_accumulation
           WHERE conversion_status='pending';"
  ```

- [ ] **Daily:** Review batch conversion logs
  ```bash
  gcloud logging read 'resource.labels.service_name="gcmicrobatchprocessor-10-26"' \
      --limit 100 \
      --format json \
      --project=telepay-459221
  ```

- [ ] **Daily:** Verify distribution accuracy
  ```bash
  psql -c "SELECT batch_conversion_id,
              ABS(actual_usdt_received - SUM(accumulated_amount_usdt)) as error
           FROM batch_conversions bc
           JOIN payout_accumulation pa USING(batch_conversion_id)
           GROUP BY batch_conversion_id, actual_usdt_received;"
  ```

### Month 1: Growth Phase ($50 Threshold)

- [ ] **Trigger:** When batches consistently include 8-10 payments
- [ ] **Action:** Update threshold
  ```bash
  echo -n "50.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=-
  ```
- [ ] **Monitor:** Batch frequency and gas fee savings

### Month 3: Scale Phase ($100 Threshold)

- [ ] **Trigger:** When batches consistently include 15-20 payments
- [ ] **Action:** Update threshold
  ```bash
  echo -n "100.00" | gcloud secrets versions add MICRO_BATCH_THRESHOLD_USD --data-file=-
  ```
- [ ] **Monitor:** Cost efficiency metrics

---

## 🚨 Rollback Plan

If critical issues occur during deployment:

### Emergency Rollback Steps

- [ ] **1. Pause Cloud Scheduler**
  ```bash
  gcloud scheduler jobs pause micro-batch-conversion-job \
      --location=us-central1 \
      --project=telepay-459221
  ```

- [ ] **2. Restore GCAccumulator (previous version)**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/ARCHIVES/GCAccumulator-10-26-BACKUP-YYYYMMDD

  gcloud builds submit --tag gcr.io/telepay-459221/gcaccumulator-10-26 \
      --project=telepay-459221

  gcloud run deploy gcaccumulator-10-26 \
      --image gcr.io/telepay-459221/gcaccumulator-10-26 \
      --platform managed \
      --region us-central1 \
      --project=telepay-459221
  ```

- [ ] **3. Process pending records manually**
  ```bash
  # Query pending records
  psql -c "SELECT id, accumulated_eth FROM payout_accumulation
           WHERE conversion_status='pending';"

  # Create individual swaps via GCSplit3 (manual intervention)
  # Contact users if necessary
  ```

---

## ✅ Final Verification Checklist

Before marking implementation complete:

- [ ] Database tables created and verified (batch_conversions, payout_accumulation.batch_conversion_id)
- [ ] Google Cloud Secret MICRO_BATCH_THRESHOLD_USD created and accessible
- [ ] GCMicroBatchProcessor service deployed and health check passing
- [ ] GCAccumulator modified (no immediate swap queuing)
- [ ] GCHostPay1 modified (batch context handling)
- [ ] Cloud Tasks queues created (gchostpay1-batch-queue, microbatch-response-queue)
- [ ] Cloud Scheduler job created and running every 15 minutes
- [ ] All services redeployed successfully
- [ ] End-to-end test completed (payment → accumulation → batch → distribution)
- [ ] Proportional distribution math verified accurate
- [ ] Threshold scaling tested ($20 → $100)
- [ ] Monitoring and alerting configured
- [ ] Documentation updated in PROGRESS.md
- [ ] Backup of original services created

---

## 📝 Summary

### Services Created/Modified

| Service | Status | Changes |
|---------|--------|---------|
| GCMicroBatchProcessor-10-26 | ✅ NEW | Batch conversion logic, threshold checking |
| GCAccumulator-10-26 | ✅ MODIFIED | Removed swap queuing (lines 146-417) |
| GCHostPay1-10-26 | ✅ MODIFIED | Added batch context handling |
| GCBatchProcessor-10-26 | ⚫ NO CHANGE | USDT→ClientCurrency batching unchanged |
| GCWebhook1/2 | ⚫ NO CHANGE | Webhook handling unchanged |
| GCSplit1/2/3 | ⚫ NO CHANGE | Split logic unchanged |
| GCHostPay2/3 | ⚫ NO CHANGE | Payout logic unchanged |

### Database Changes

- ✅ New table: `batch_conversions`
- ✅ New column: `payout_accumulation.batch_conversion_id`

### Infrastructure Changes

- ✅ New secret: `MICRO_BATCH_THRESHOLD_USD`
- ✅ New queue: `gchostpay1-batch-queue`
- ✅ New queue: `microbatch-response-queue`
- ✅ New scheduler: `micro-batch-conversion-job` (every 15 minutes)

### Key Benefits Achieved

- ✅ **50-90% gas fee reduction** (one swap for multiple payments)
- ✅ **Dynamic threshold scaling** ($20 → $1000+ without code changes)
- ✅ **Proportional USDT distribution** (fair allocation across payments)
- ✅ **Volatility protection** (15-minute conversion window acceptable)
- ✅ **Proven architecture patterns** (CRON + QUEUES + TOKENS)

---

**Document Version:** 1.0
**Created:** 2025-10-31
**Architecture Reference:** `MICRO_BATCH_CONVERSION_ARCHITECTURE.md`
**Implementation Status:** Ready for execution
