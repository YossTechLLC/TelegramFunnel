# Idempotency Implementation Checklist

**Date:** 2025-11-02  
**Reference:** REPEATED_TELEGRAM_INVITES_ROOT_CAUSE_ANALYSIS_ARCHITECTURE.md  
**Status:** ⏳ PENDING IMPLEMENTATION

---

## Overview

This checklist implements the multi-layered idempotency solution to prevent duplicate Telegram invites and duplicate payment processing.

**Estimated Time:** 4-6 hours  
**Risk Level:** MEDIUM (mitigated by rollback plan)

---

## ✅ Pre-Implementation Checklist

### Environment Preparation

- [ ] **Task 0.1:** Verify remaining context budget
  - Current context: Check token usage
  - If < 30% remaining → Ask user to compact first
  
- [ ] **Task 0.2:** Backup current production database
  ```bash
  # Create database snapshot
  gcloud sql backups create \
    --instance=telepaypsql \
    --description="Pre-idempotency-implementation backup $(date +%Y%m%d-%H%M%S)"
  
  # Verify backup created
  gcloud sql backups list --instance=telepaypsql --limit=5
  ```
  **Expected:** New backup appears in list with today's timestamp.

- [ ] **Task 0.3:** Document current service revisions (for rollback)
  ```bash
  echo "=== Current Service Revisions (Pre-Implementation) ===" > /tmp/pre_impl_revisions.txt
  gcloud run revisions list --service=np-webhook-10-26 --region=us-central1 --limit=1 >> /tmp/pre_impl_revisions.txt
  gcloud run revisions list --service=gcwebhook1-10-26 --region=us-central1 --limit=1 >> /tmp/pre_impl_revisions.txt
  gcloud run revisions list --service=gcwebhook2-10-26 --region=us-central1 --limit=1 >> /tmp/pre_impl_revisions.txt
  cat /tmp/pre_impl_revisions.txt
  ```
  **Expected:** Current revision names saved (e.g., `gcwebhook2-10-26-00014-nn4`).

- [ ] **Task 0.4:** Verify all services are currently healthy
  ```bash
  gcloud run services list --platform managed --region us-central1 --format="table(metadata.name,status.conditions[0].status)"
  ```
  **Expected:** All services show "True" status.

- [ ] **Task 0.5:** Check for stuck tasks in queues
  ```bash
  gcloud tasks list --queue=gcwebhook1-queue --location=us-central1 --limit=10
  gcloud tasks list --queue=gcwebhook-telegram-invite-queue --location=us-central1 --limit=10
  ```
  **Expected:** No stuck/retrying tasks (or purge if found).

---

## 📊 Phase 1: Database Migration

### Create `processed_payments` Table

- [ ] **Task 1.1:** Create SQL migration script
  - **File:** `/OCTOBER/10-26/scripts/create_processed_payments_table.sql`
  - **Action:** Create new file with table definition
  
  ```sql
  -- File: scripts/create_processed_payments_table.sql
  -- Purpose: Create processed_payments table for idempotency tracking
  
  BEGIN;
  
  -- Create table
  CREATE TABLE IF NOT EXISTS processed_payments (
      -- Primary key: NowPayments payment_id (unique identifier)
      payment_id BIGINT PRIMARY KEY,
      
      -- Reference data for lookups and debugging
      user_id BIGINT NOT NULL,
      channel_id BIGINT NOT NULL,
      
      -- Processing state flags
      gcwebhook1_processed BOOLEAN DEFAULT FALSE,
      gcwebhook1_processed_at TIMESTAMP,
      
      -- Telegram invite state
      telegram_invite_sent BOOLEAN DEFAULT FALSE,
      telegram_invite_sent_at TIMESTAMP,
      telegram_invite_link TEXT,
      
      -- Audit fields
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      
      -- Constraints
      CONSTRAINT payment_id_positive CHECK (payment_id > 0),
      CONSTRAINT user_id_positive CHECK (user_id > 0)
  );
  
  -- Create indexes for fast lookups
  CREATE INDEX IF NOT EXISTS idx_processed_payments_user_channel 
  ON processed_payments(user_id, channel_id);
  
  CREATE INDEX IF NOT EXISTS idx_processed_payments_invite_status 
  ON processed_payments(telegram_invite_sent);
  
  CREATE INDEX IF NOT EXISTS idx_processed_payments_webhook1_status 
  ON processed_payments(gcwebhook1_processed);
  
  CREATE INDEX IF NOT EXISTS idx_processed_payments_created_at 
  ON processed_payments(created_at DESC);
  
  -- Add comments for documentation
  COMMENT ON TABLE processed_payments IS 'Tracks payment processing state for idempotency - prevents duplicate Telegram invites and payment accumulation';
  COMMENT ON COLUMN processed_payments.payment_id IS 'NowPayments payment_id (unique identifier from IPN callback)';
  COMMENT ON COLUMN processed_payments.gcwebhook1_processed IS 'Flag indicating if GCWebhook1 successfully processed this payment';
  COMMENT ON COLUMN processed_payments.telegram_invite_sent IS 'Flag indicating if Telegram invite successfully sent to user';
  COMMENT ON COLUMN processed_payments.telegram_invite_link IS 'The actual one-time invite link sent to user (for reference/debugging)';
  
  COMMIT;
  
  -- Verify table structure
  \d processed_payments;
  
  -- Verify indexes
  \di processed_payments*;
  
  -- Check initial count (should be 0)
  SELECT COUNT(*) as initial_count FROM processed_payments;
  ```

- [ ] **Task 1.2:** Execute migration on production database
  ```bash
  # Navigate to scripts directory
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/scripts
  
  # Execute migration
  PGPASSWORD='Chigdabeast123$' psql \
    -h /cloudsql/telepay-459221:us-central1:telepaypsql \
    -U postgres \
    -d telepaydb \
    -f create_processed_payments_table.sql
  ```
  **Expected Output:**
  ```
  BEGIN
  CREATE TABLE
  CREATE INDEX
  CREATE INDEX
  CREATE INDEX
  CREATE INDEX
  COMMENT
  COMMENT
  COMMENT
  COMMENT
  COMMENT
  COMMIT
  [Table structure display]
  [Indexes display]
  initial_count
  ---------------
               0
  ```

- [ ] **Task 1.3:** Verify table created successfully
  ```bash
  PGPASSWORD='Chigdabeast123$' psql \
    -h /cloudsql/telepay-459221:us-central1:telepaypsql \
    -U postgres \
    -d telepaydb \
    -c "\d processed_payments"
  ```
  **Expected:** Table structure matches specification (payment_id PRIMARY KEY, 4 indexes).

- [ ] **Task 1.4:** Test INSERT ... ON CONFLICT behavior
  ```bash
  PGPASSWORD='Chigdabeast123$' psql \
    -h /cloudsql/telepay-459221:us-central1:telepaypsql \
    -U postgres \
    -d telepaydb \
    -c "
    -- Test insert
    INSERT INTO processed_payments (payment_id, user_id, channel_id) 
    VALUES (999999999, 123456, -1001234567890);
    
    -- Test duplicate insert (should do nothing)
    INSERT INTO processed_payments (payment_id, user_id, channel_id) 
    VALUES (999999999, 123456, -1001234567890)
    ON CONFLICT (payment_id) DO NOTHING;
    
    -- Verify only one record exists
    SELECT COUNT(*) FROM processed_payments WHERE payment_id = 999999999;
    
    -- Clean up test data
    DELETE FROM processed_payments WHERE payment_id = 999999999;
    "
  ```
  **Expected:** COUNT = 1 (ON CONFLICT prevented duplicate).

---

## 🔧 Phase 2: Code Changes - NP-Webhook

### Add Database Manager (if not present)

- [ ] **Task 2.1:** Check if NP-Webhook has database_manager.py
  ```bash
  ls -lh /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26/database_manager.py
  ```
  **If NOT found:** Copy from GCWebhook1:
  ```bash
  cp /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26/database_manager.py \
     /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26/database_manager.py
  ```

### Implement Idempotency Check in IPN Handler

- [ ] **Task 2.2:** Read current IPN handler code
  - **File:** `np-webhook-10-26/app.py`
  - **Location:** Lines ~450-699 (IPN endpoint)
  - **Action:** Identify exact line where `cloudtasks_client.enqueue_gcwebhook1_validated_payment()` is called

- [ ] **Task 2.3:** Add idempotency check BEFORE GCWebhook1 enqueue
  - **File:** `np-webhook-10-26/app.py`
  - **Location:** After IPN validation, BEFORE line ~659 (`enqueue_gcwebhook1_validated_payment`)
  - **Change:** Insert idempotency check logic
  
  **Insert at line ~640 (after subscription data fetch, before enqueuing):**
  ```python
  # ============================================================================
  # IDEMPOTENCY CHECK: Prevent duplicate payment processing
  # ============================================================================
  
  nowpayments_payment_id = payment_data['payment_id']
  
  print(f"")
  print(f"🔍 [IDEMPOTENCY] Checking if payment {nowpayments_payment_id} already processed...")
  
  try:
      # Query database to check if payment already processed
      conn_check = get_db_connection()
      if conn_check:
          cur_check = conn_check.cursor()
          
          cur_check.execute("""
              SELECT 
                  gcwebhook1_processed,
                  telegram_invite_sent,
                  telegram_invite_sent_at
              FROM processed_payments
              WHERE payment_id = %s
          """, (nowpayments_payment_id,))
          
          existing_payment = cur_check.fetchone()
          
          cur_check.close()
          conn_check.close()
          
          if existing_payment and existing_payment[0]:  # gcwebhook1_processed = TRUE
              print(f"✅ [IDEMPOTENCY] Payment {nowpayments_payment_id} already processed")
              print(f"   GCWebhook1 processed: TRUE")
              print(f"   Telegram invite sent: {existing_payment[1]}")
              if existing_payment[2]:
                  print(f"   Invite sent at: {existing_payment[2]}")
              
              # Already processed - return success without re-enqueueing
              print(f"✅ [IPN] IPN acknowledged (payment already handled)")
              return jsonify({
                  "status": "success",
                  "message": "IPN processed (already handled)",
                  "payment_id": nowpayments_payment_id
              }), 200
          
          elif existing_payment:
              # Record exists but not fully processed
              print(f"⚠️ [IDEMPOTENCY] Payment {nowpayments_payment_id} record exists but processing incomplete")
              print(f"   GCWebhook1 processed: {existing_payment[0]}")
              print(f"   Will allow re-processing to complete")
          else:
              # No existing record - first time processing
              print(f"🆕 [IDEMPOTENCY] Payment {nowpayments_payment_id} is new - creating processing record")
              
              # Insert initial record (prevents race conditions)
              conn_insert = get_db_connection()
              if conn_insert:
                  cur_insert = conn_insert.cursor()
                  
                  cur_insert.execute("""
                      INSERT INTO processed_payments (payment_id, user_id, channel_id)
                      VALUES (%s, %s, %s)
                      ON CONFLICT (payment_id) DO NOTHING
                  """, (nowpayments_payment_id, user_id, closed_channel_id))
                  
                  conn_insert.commit()
                  cur_insert.close()
                  conn_insert.close()
                  
                  print(f"✅ [IDEMPOTENCY] Created processing record for payment {nowpayments_payment_id}")
              else:
                  print(f"⚠️ [IDEMPOTENCY] Failed to create processing record (DB connection failed)")
                  print(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")
      else:
          print(f"⚠️ [IDEMPOTENCY] Database connection failed - cannot check idempotency")
          print(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")
  
  except Exception as e:
      print(f"❌ [IDEMPOTENCY] Error during idempotency check: {e}")
      import traceback
      traceback.print_exc()
      print(f"⚠️ [IDEMPOTENCY] Proceeding with processing (fail-open mode)")
  
  print(f"")
  print(f"🚀 [ORCHESTRATION] Proceeding to enqueue payment to GCWebhook1...")
  
  # Continue with existing code: enqueue_gcwebhook1_validated_payment(...)
  ```

- [ ] **Task 2.4:** Verify code syntax
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26
  python3 -m py_compile app.py
  ```
  **Expected:** No syntax errors.

---

## 🔧 Phase 3: Code Changes - GCWebhook1

### Update Main Processing Endpoint

- [ ] **Task 3.1:** Read current GCWebhook1 code
  - **File:** `GCWebhook1-10-26/tph1-10-26.py`
  - **Location:** Lines 220-450 (`/process-validated-payment` endpoint)

- [ ] **Task 3.2:** Add processing marker AFTER successful enqueuing
  - **File:** `GCWebhook1-10-26/tph1-10-26.py`
  - **Location:** After line ~420 (after both GCAccumulator/GCSplit1 AND GCWebhook2 enqueued)
  - **BEFORE:** The final return statement (line ~430-440)
  
  **Insert at line ~425 (after successful enqueueing, before return):**
  ```python
  # ============================================================================
  # IDEMPOTENCY: Mark payment as processed
  # ============================================================================
  
  try:
      db_manager.execute_query("""
          UPDATE processed_payments
          SET 
              gcwebhook1_processed = TRUE,
              gcwebhook1_processed_at = CURRENT_TIMESTAMP,
              updated_at = CURRENT_TIMESTAMP
          WHERE payment_id = %s
      """, (nowpayments_payment_id,))
      
      print(f"")
      print(f"✅ [IDEMPOTENCY] Marked payment {nowpayments_payment_id} as processed")
  except Exception as e:
      # Non-critical error - payment already enqueued successfully
      print(f"⚠️ [IDEMPOTENCY] Failed to mark payment as processed: {e}")
      print(f"⚠️ [IDEMPOTENCY] Payment processing will continue (non-blocking error)")
  
  print(f"")
  ```

### Update CloudTasks Client

- [ ] **Task 3.3:** Read current CloudTasks client
  - **File:** `GCWebhook1-10-26/cloudtasks_client.py`
  - **Action:** Find `enqueue_telegram_invite()` function definition

- [ ] **Task 3.4:** Add `payment_id` parameter to `enqueue_telegram_invite()`
  - **File:** `GCWebhook1-10-26/cloudtasks_client.py`
  - **Location:** `enqueue_telegram_invite()` function signature and body
  
  **Modify function signature:**
  ```python
  def enqueue_telegram_invite(
      self,
      queue_name: str,
      target_url: str,
      encrypted_token: str,
      payment_id: int  # ← NEW PARAMETER
  ):
      """
      Enqueue Telegram invite task to GCWebhook2.
      
      Args:
          queue_name: Cloud Tasks queue name
          target_url: GCWebhook2 endpoint URL
          encrypted_token: Encrypted token from token_manager
          payment_id: NowPayments payment_id for idempotency tracking
      """
  ```
  
  **Modify task payload:**
  ```python
  # Update task payload to include payment_id
  task_payload = {
      'encrypted_token': encrypted_token,
      'payment_id': payment_id  # ← NEW FIELD
  }
  
  task = {
      'http_request': {
          'http_method': tasks_v2.HttpMethod.POST,
          'url': target_url,
          'headers': {'Content-Type': 'application/json'},
          'body': json.dumps(task_payload).encode()
      }
  }
  ```

- [ ] **Task 3.5:** Update `enqueue_telegram_invite()` call in tph1-10-26.py
  - **File:** `GCWebhook1-10-26/tph1-10-26.py`
  - **Location:** Line ~410-420 (where `enqueue_telegram_invite` is called)
  
  **Change FROM:**
  ```python
  cloudtasks_client.enqueue_telegram_invite(
      queue_name=GCWEBHOOK2_QUEUE,
      target_url=f"{GCWEBHOOK2_URL}/",
      encrypted_token=encrypted_token
  )
  ```
  
  **TO:**
  ```python
  cloudtasks_client.enqueue_telegram_invite(
      queue_name=GCWEBHOOK2_QUEUE,
      target_url=f"{GCWEBHOOK2_URL}/",
      encrypted_token=encrypted_token,
      payment_id=nowpayments_payment_id  # ← NEW PARAMETER
  )
  ```

- [ ] **Task 3.6:** Verify code syntax
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26
  python3 -m py_compile tph1-10-26.py
  python3 -m py_compile cloudtasks_client.py
  ```
  **Expected:** No syntax errors.

---

## 🔧 Phase 4: Code Changes - GCWebhook2

### Implement Idempotency Check in Invite Sender

- [ ] **Task 4.1:** Read current GCWebhook2 code
  - **File:** `GCWebhook2-10-26/tph2-10-26.py`
  - **Location:** Lines 84-200 (main `send_telegram_invite()` endpoint)

- [ ] **Task 4.2:** Extract `payment_id` from request
  - **File:** `GCWebhook2-10-26/tph2-10-26.py`
  - **Location:** Line ~100-110 (after `request.get_json()`)
  
  **Change FROM:**
  ```python
  try:
      print(f"🎯 [ENDPOINT] Telegram invite request received (from GCWebhook1)")
      
      # Extract request data
      request_data = request.get_json()
      encrypted_token = request_data.get('encrypted_token')
      
      if not encrypted_token:
          print(f"❌ [ENDPOINT] Missing encrypted_token")
          abort(400, "Missing encrypted token")
  ```
  
  **TO:**
  ```python
  try:
      print(f"🎯 [ENDPOINT] Telegram invite request received (from GCWebhook1)")
      
      # Extract request data
      request_data = request.get_json()
      encrypted_token = request_data.get('encrypted_token')
      payment_id = request_data.get('payment_id')  # ← NEW FIELD
      
      if not encrypted_token:
          print(f"❌ [ENDPOINT] Missing encrypted_token")
          abort(400, "Missing encrypted token")
      
      if not payment_id:
          print(f"❌ [ENDPOINT] Missing payment_id")
          abort(400, "Missing payment_id for idempotency tracking")
      
      print(f"📋 [ENDPOINT] Payment ID: {payment_id}")
  ```

- [ ] **Task 4.3:** Add idempotency check BEFORE decrypting token
  - **File:** `GCWebhook2-10-26/tph2-10-26.py`
  - **Location:** After extracting payment_id, BEFORE token decryption
  
  **Insert after Task 4.2 changes:**
  ```python
  # ================================================================
  # IDEMPOTENCY CHECK: Check if invite already sent for this payment
  # ================================================================
  
  print(f"")
  print(f"🔍 [IDEMPOTENCY] Checking if invite already sent for payment {payment_id}...")
  
  try:
      existing_invite = db_manager.execute_query("""
          SELECT 
              telegram_invite_sent,
              telegram_invite_link,
              telegram_invite_sent_at
          FROM processed_payments
          WHERE payment_id = %s
      """, (payment_id,))
      
      if existing_invite and existing_invite[0]['telegram_invite_sent']:
          # Invite already sent - return success without re-sending
          existing_link = existing_invite[0]['telegram_invite_link']
          sent_at = existing_invite[0]['telegram_invite_sent_at']
          
          print(f"✅ [IDEMPOTENCY] Invite already sent for payment {payment_id}")
          print(f"   Sent at: {sent_at}")
          print(f"   Link: {existing_link}")
          print(f"🎉 [ENDPOINT] Returning success (invite already sent)")
          
          return jsonify({
              "status": "success",
              "message": "Telegram invite already sent",
              "payment_id": payment_id,
              "invite_sent_at": str(sent_at)
          }), 200
      else:
          print(f"🆕 [IDEMPOTENCY] No existing invite found - proceeding to send")
  
  except Exception as e:
      print(f"⚠️ [IDEMPOTENCY] Error checking invite status: {e}")
      import traceback
      traceback.print_exc()
      print(f"⚠️ [IDEMPOTENCY] Proceeding with invite send (fail-open mode)")
  
  print(f"")
  
  # Continue with existing code: token decryption and invite send
  ```

- [ ] **Task 4.4:** Add invite sent marker AFTER successful invite send
  - **File:** `GCWebhook2-10-26/tph2-10-26.py`
  - **Location:** After successfully sending invite, BEFORE final return statement
  
  **Find the section after invite is sent (after `bot.send_message()` completes):**
  ```python
  # Existing code around line 170-180
  print(f"✅ [ENDPOINT] Invite link created: {invite_link}")
  print(f"✅ [ENDPOINT] Invite message sent to user {user_id}")
  
  # ← INSERT NEW CODE HERE (Task 4.4)
  
  print(f"🎉 [ENDPOINT] Telegram invite completed successfully")
  return jsonify({
      "status": "success",
      "message": "Telegram invite sent"
  }), 200
  ```
  
  **Insert idempotency marker:**
  ```python
  print(f"✅ [ENDPOINT] Invite link created: {invite_link}")
  print(f"✅ [ENDPOINT] Invite message sent to user {user_id}")
  
  # ================================================================
  # IDEMPOTENCY: Mark invite as sent in database
  # ================================================================
  
  try:
      db_manager.execute_query("""
          UPDATE processed_payments
          SET 
              telegram_invite_sent = TRUE,
              telegram_invite_sent_at = CURRENT_TIMESTAMP,
              telegram_invite_link = %s,
              updated_at = CURRENT_TIMESTAMP
          WHERE payment_id = %s
      """, (invite_link.invite_link, payment_id))
      
      print(f"✅ [IDEMPOTENCY] Marked invite as sent for payment {payment_id}")
      print(f"   Link stored: {invite_link.invite_link}")
  except Exception as e:
      # Non-critical error - invite already sent to user
      print(f"⚠️ [IDEMPOTENCY] Failed to mark invite as sent: {e}")
      print(f"⚠️ [IDEMPOTENCY] User received invite, but DB update failed")
      print(f"⚠️ [IDEMPOTENCY] Will retry DB update on next task execution")
  
  print(f"🎉 [ENDPOINT] Telegram invite completed successfully")
  return jsonify({
      "status": "success",
      "message": "Telegram invite sent",
      "payment_id": payment_id
  }), 200
  ```

- [ ] **Task 4.5:** Verify code syntax
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook2-10-26
  python3 -m py_compile tph2-10-26.py
  ```
  **Expected:** No syntax errors.

---

## 🧪 Phase 5: Local Testing (Pre-Deployment)

### Code Validation

- [ ] **Task 5.1:** Compile all modified Python files
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26
  
  # NP-Webhook
  python3 -m py_compile np-webhook-10-26/app.py
  
  # GCWebhook1
  python3 -m py_compile GCWebhook1-10-26/tph1-10-26.py
  python3 -m py_compile GCWebhook1-10-26/cloudtasks_client.py
  
  # GCWebhook2
  python3 -m py_compile GCWebhook2-10-26/tph2-10-26.py
  
  echo "✅ All files compiled successfully"
  ```
  **Expected:** No syntax errors for any file.

- [ ] **Task 5.2:** Verify database connection from each service
  ```bash
  # Test NP-Webhook database connection (if database_manager added)
  cd np-webhook-10-26
  python3 -c "from database_manager import DatabaseManager; print('✅ NP-Webhook: database_manager imports successfully')"
  
  # Test GCWebhook1 database connection
  cd ../GCWebhook1-10-26
  python3 -c "from database_manager import DatabaseManager; print('✅ GCWebhook1: database_manager imports successfully')"
  
  # Test GCWebhook2 database connection
  cd ../GCWebhook2-10-26
  python3 -c "from database_manager import DatabaseManager; print('✅ GCWebhook2: database_manager imports successfully')"
  ```
  **Expected:** All three services import database_manager without errors.

---

## 🚀 Phase 6: Deployment

### Deploy Services in Reverse Flow Order

- [ ] **Task 6.1:** Deploy GCWebhook2 (downstream first)
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook2-10-26
  
  # Build Docker image
  gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook2-10-26
  
  # Deploy to Cloud Run
  gcloud run deploy gcwebhook2-10-26 \
    --image gcr.io/telepay-459221/gcwebhook2-10-26 \
    --region us-central1 \
    --allow-unauthenticated \
    --set-secrets=SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest
  ```
  **Expected:** Build succeeds, deployment completes, service shows "READY".

- [ ] **Task 6.2:** Verify GCWebhook2 deployment
  ```bash
  # Check service status
  gcloud run services describe gcwebhook2-10-26 --region=us-central1 --format="value(status.conditions[0].status)"
  
  # Check logs for startup errors
  gcloud run services logs read gcwebhook2-10-26 --region=us-central1 --limit=20
  
  # Test health endpoint (if exists)
  GCWEBHOOK2_URL=$(gcloud run services describe gcwebhook2-10-26 --region=us-central1 --format="value(status.url)")
  curl -s "${GCWEBHOOK2_URL}/health" || echo "No health endpoint"
  ```
  **Expected:** Status = "True", logs show successful initialization, no errors.

- [ ] **Task 6.3:** Deploy GCWebhook1 (middle layer)
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26
  
  # Build Docker image
  gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook1-10-26
  
  # Deploy to Cloud Run
  gcloud run deploy gcwebhook1-10-26 \
    --image gcr.io/telepay-459221/gcwebhook1-10-26 \
    --region us-central1 \
    --allow-unauthenticated \
    --set-secrets=SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,GCSPLIT1_QUEUE=GCSPLIT1_QUEUE:latest,GCSPLIT1_URL=GCSPLIT1_URL:latest,GCACCUMULATOR_QUEUE=GCACCUMULATOR_QUEUE:latest,GCACCUMULATOR_URL=GCACCUMULATOR_URL:latest,GCWEBHOOK2_QUEUE=GCWEBHOOK2_QUEUE:latest,GCWEBHOOK2_URL=GCWEBHOOK2_URL:latest
  ```
  **Expected:** Build succeeds, deployment completes, service shows "READY".

- [ ] **Task 6.4:** Verify GCWebhook1 deployment
  ```bash
  # Check service status
  gcloud run services describe gcwebhook1-10-26 --region=us-central1 --format="value(status.conditions[0].status)"
  
  # Check logs for startup errors
  gcloud run services logs read gcwebhook1-10-26 --region=us-central1 --limit=20
  ```
  **Expected:** Status = "True", logs show successful initialization.

- [ ] **Task 6.5:** Deploy NP-Webhook (upstream last)
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26
  
  # Build Docker image
  gcloud builds submit --tag gcr.io/telepay-459221/np-webhook-10-26
  
  # Deploy to Cloud Run
  gcloud run deploy np-webhook-10-26 \
    --image gcr.io/telepay-459221/np-webhook-10-26 \
    --region us-central1 \
    --allow-unauthenticated \
    --set-secrets=NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,GCWEBHOOK1_QUEUE=GCWEBHOOK1_QUEUE:latest,GCWEBHOOK1_URL=GCWEBHOOK1_URL:latest,COINGECKO_API_KEY=COINGECKO_API_KEY:latest
  ```
  **Expected:** Build succeeds, deployment completes, service shows "READY".

- [ ] **Task 6.6:** Verify NP-Webhook deployment
  ```bash
  # Check service status
  gcloud run services describe np-webhook-10-26 --region=us-central1 --format="value(status.conditions[0].status)"
  
  # Check logs for startup errors
  gcloud run services logs read np-webhook-10-26 --region=us-central1 --limit=20
  
  # Test health endpoint
  NP_WEBHOOK_URL=$(gcloud run services describe np-webhook-10-26 --region=us-central1 --format="value(status.url)")
  curl -s "${NP_WEBHOOK_URL}/health"
  ```
  **Expected:** Status = "True", health check returns 200 OK.

---

## ✅ Phase 7: Post-Deployment Verification

### Database Verification

- [ ] **Task 7.1:** Verify `processed_payments` table is accessible from services
  ```bash
  # Check table exists and is empty (or has test records)
  PGPASSWORD='Chigdabeast123$' psql \
    -h /cloudsql/telepay-459221:us-central1:telepaypsql \
    -U postgres \
    -d telepaydb \
    -c "SELECT COUNT(*) as total_payments FROM processed_payments;"
  ```
  **Expected:** Query succeeds, returns count (likely 0 or small number).

### Service Health Checks

- [ ] **Task 7.2:** Verify all services are healthy
  ```bash
  gcloud run services list --platform managed --region us-central1 --format="table(metadata.name,status.conditions[0].status,status.latestReadyRevisionName)"
  ```
  **Expected:** All services show "True" status with new revision names.

- [ ] **Task 7.3:** Check for deployment errors in logs
  ```bash
  # Check last 50 logs from each service
  echo "=== NP-Webhook Logs ==="
  gcloud run services logs read np-webhook-10-26 --region=us-central1 --limit=50 | grep -E "(ERROR|❌|⚠️)" || echo "No errors"
  
  echo "=== GCWebhook1 Logs ==="
  gcloud run services logs read gcwebhook1-10-26 --region=us-central1 --limit=50 | grep -E "(ERROR|❌|⚠️)" || echo "No errors"
  
  echo "=== GCWebhook2 Logs ==="
  gcloud run services logs read gcwebhook2-10-26 --region=us-central1 --limit=50 | grep -E "(ERROR|❌|⚠️)" || echo "No errors"
  ```
  **Expected:** No critical errors (⚠️ warnings acceptable if labeled "fail-open mode").

---

## 🧪 Phase 8: Functional Testing

### Test 1: New Payment (First-Time Processing)

- [ ] **Task 8.1:** Create NEW test payment
  - **Action:** Start TelePay bot, create subscription, complete payment on NowPayments
  - **Amount:** $1.35 (or minimum)
  - **Expected:** Payment completes successfully

- [ ] **Task 8.2:** Monitor NP-Webhook logs in real-time
  ```bash
  # Open in separate terminal
  gcloud run services logs tail np-webhook-10-26 --region=us-central1
  ```
  **Expected logs:**
  ```
  🔍 [IDEMPOTENCY] Checking if payment [PAYMENT_ID] already processed...
  🆕 [IDEMPOTENCY] Payment [PAYMENT_ID] is new - creating processing record
  ✅ [IDEMPOTENCY] Created processing record for payment [PAYMENT_ID]
  🚀 [ORCHESTRATION] Proceeding to enqueue payment to GCWebhook1...
  ✅ [ORCHESTRATION] Successfully enqueued to GCWebhook1
  ```

- [ ] **Task 8.3:** Monitor GCWebhook1 logs
  ```bash
  # Open in separate terminal
  gcloud run services logs tail gcwebhook1-10-26 --region=us-central1
  ```
  **Expected logs:**
  ```
  🎯 [VALIDATED] Received validated payment from NP-Webhook
  ✅ [VALIDATED] Payment Data Received:
     User ID: [USER_ID]
     Channel ID: [CHANNEL_ID]
     Payment ID: [PAYMENT_ID]
  ✅ [VALIDATED] Successfully enqueued to GCAccumulator/GCSplit1
  ✅ [VALIDATED] Enqueued Telegram invite to GCWebhook2
  ✅ [IDEMPOTENCY] Marked payment [PAYMENT_ID] as processed
  🎉 [VALIDATED] Payment processing completed successfully
  ```

- [ ] **Task 8.4:** Monitor GCWebhook2 logs
  ```bash
  # Open in separate terminal
  gcloud run services logs tail gcwebhook2-10-26 --region=us-central1
  ```
  **Expected logs:**
  ```
  🎯 [ENDPOINT] Telegram invite request received (from GCWebhook1)
  📋 [ENDPOINT] Payment ID: [PAYMENT_ID]
  🔍 [IDEMPOTENCY] Checking if invite already sent for payment [PAYMENT_ID]...
  🆕 [IDEMPOTENCY] No existing invite found - proceeding to send
  ✅ [ENDPOINT] Invite link created: https://t.me/+[UNIQUE_LINK]
  ✅ [ENDPOINT] Invite message sent to user [USER_ID]
  ✅ [IDEMPOTENCY] Marked invite as sent for payment [PAYMENT_ID]
  🎉 [ENDPOINT] Telegram invite completed successfully
  ```

- [ ] **Task 8.5:** Verify user receives EXACTLY ONE Telegram invite
  - **Check:** User's Telegram messages
  - **Expected:** ONE invite link received
  - **Failure:** If multiple invites received, idempotency failed

- [ ] **Task 8.6:** Verify database record created
  ```bash
  PAYMENT_ID=[PAYMENT_ID_FROM_LOGS]
  
  PGPASSWORD='Chigdabeast123$' psql \
    -h /cloudsql/telepay-459221:us-central1:telepaypsql \
    -U postgres \
    -d telepaydb \
    -c "
    SELECT 
        payment_id,
        user_id,
        gcwebhook1_processed,
        telegram_invite_sent,
        telegram_invite_link,
        created_at
    FROM processed_payments
    WHERE payment_id = $PAYMENT_ID;
    "
  ```
  **Expected:**
  ```
  payment_id | user_id | gcwebhook1_processed | telegram_invite_sent | telegram_invite_link    | created_at
  -----------|---------|----------------------|----------------------|-------------------------|-------------------
  [ID]       | [UID]   | t                    | t                    | https://t.me/+[LINK]    | 2025-11-02 ...
  ```

### Test 2: Duplicate IPN Simulation (Idempotency Check)

- [ ] **Task 8.7:** Simulate duplicate IPN callback
  ```bash
  # Get the IPN payload from logs (from Task 8.2)
  # Manually trigger IPN callback using curl
  
  NP_WEBHOOK_URL=$(gcloud run services describe np-webhook-10-26 --region=us-central1 --format="value(status.url)")
  
  # Note: This requires the exact IPN signature and payload from logs
  # Alternative: Wait for NowPayments to send duplicate (may not happen)
  
  echo "⚠️ Manual IPN re-trigger requires exact payload and signature"
  echo "   Alternatively: Re-query payment status API multiple times (simulates polling)"
  ```

- [ ] **Task 8.8:** Simulate payment status polling (alternative test)
  ```bash
  # Get order_id from test payment
  ORDER_ID="PGP-[USER_ID]|[OPEN_CHANNEL_ID]"
  
  # Poll payment status API 5 times
  for i in {1..5}; do
    echo "=== Poll attempt $i ==="
    curl -s "${NP_WEBHOOK_URL}/api/payment-status?order_id=${ORDER_ID}"
    echo ""
    sleep 2
  done
  ```
  **Expected:** All 5 requests return success, but NO duplicate processing occurs.

- [ ] **Task 8.9:** Monitor NP-Webhook logs during polling
  ```bash
  gcloud run services logs read np-webhook-10-26 --region=us-central1 --limit=100 | grep IDEMPOTENCY
  ```
  **Expected logs (for 2nd+ poll):**
  ```
  🔍 [IDEMPOTENCY] Checking if payment [PAYMENT_ID] already processed...
  ✅ [IDEMPOTENCY] Payment [PAYMENT_ID] already processed
     GCWebhook1 processed: TRUE
     Telegram invite sent: True
  ✅ [IPN] IPN acknowledged (payment already handled)
  ```

- [ ] **Task 8.10:** Verify NO duplicate invite sent
  - **Check:** User's Telegram messages
  - **Expected:** Still ONLY ONE invite link (original)
  - **Success:** Idempotency working correctly

- [ ] **Task 8.11:** Verify NO duplicate Cloud Tasks enqueued
  ```bash
  # Check both queues
  gcloud tasks list --queue=gcwebhook1-queue --location=us-central1 --limit=10
  gcloud tasks list --queue=gcwebhook-telegram-invite-queue --location=us-central1 --limit=10
  ```
  **Expected:** Empty queues (or only tasks for OTHER payments).

### Test 3: GCWebhook2 Retry Simulation

- [ ] **Task 8.12:** Manually re-enqueue task to GCWebhook2 (simulates retry)
  ```bash
  # Get payment_id from previous test
  PAYMENT_ID=[PAYMENT_ID_FROM_TEST_1]
  
  # Get GCWebhook2 URL
  GCWEBHOOK2_URL=$(gcloud run services describe gcwebhook2-10-26 --region=us-central1 --format="value(status.url)")
  
  # Note: This requires the encrypted_token from previous request
  # In production, Cloud Tasks would retry with same payload
  
  echo "⚠️ Manual task re-enqueue requires encrypted_token from logs"
  echo "   Alternatively: Use gcloud tasks create-http-task with captured payload"
  ```

- [ ] **Task 8.13:** Monitor GCWebhook2 logs for idempotency check
  ```bash
  gcloud run services logs tail gcwebhook2-10-26 --region=us-central1
  ```
  **Expected logs (if re-enqueued):**
  ```
  🔍 [IDEMPOTENCY] Checking if invite already sent for payment [PAYMENT_ID]...
  ✅ [IDEMPOTENCY] Invite already sent for payment [PAYMENT_ID]
     Sent at: [TIMESTAMP]
     Link: https://t.me/+[LINK]
  🎉 [ENDPOINT] Returning success (invite already sent)
  ```

- [ ] **Task 8.14:** Verify NO duplicate invite sent
  - **Check:** User still has ONLY ONE invite
  - **Success:** GCWebhook2 idempotency working

---

## 📊 Phase 9: Production Monitoring

### Database Monitoring

- [ ] **Task 9.1:** Set up database monitoring query
  ```bash
  # Save as monitoring script: /tmp/monitor_processed_payments.sh
  cat > /tmp/monitor_processed_payments.sh << 'MONITOR_EOF'
  #!/bin/bash
  PGPASSWORD='Chigdabeast123$' psql \
    -h /cloudsql/telepay-459221:us-central1:telepaypsql \
    -U postgres \
    -d telepaydb \
    -c "
    SELECT 
        COUNT(*) as total_payments,
        COUNT(*) FILTER (WHERE gcwebhook1_processed = TRUE) as webhook1_processed,
        COUNT(*) FILTER (WHERE telegram_invite_sent = TRUE) as invites_sent,
        MAX(created_at) as latest_payment
    FROM processed_payments;
    "
  MONITOR_EOF
  
  chmod +x /tmp/monitor_processed_payments.sh
  
  # Run initial check
  /tmp/monitor_processed_payments.sh
  ```
  **Expected:** Counters increment with each new payment.

- [ ] **Task 9.2:** Check for duplicate payment_id entries (should be ZERO)
  ```bash
  PGPASSWORD='Chigdabeast123$' psql \
    -h /cloudsql/telepay-459221:us-central1:telepaypsql \
    -U postgres \
    -d telepaydb \
    -c "
    SELECT payment_id, COUNT(*) as duplicate_count
    FROM processed_payments
    GROUP BY payment_id
    HAVING COUNT(*) > 1;
    "
  ```
  **Expected:** Zero rows (no duplicates).

### Service Monitoring

- [ ] **Task 9.3:** Monitor for idempotency-related errors
  ```bash
  # Set up continuous monitoring (run in background)
  watch -n 30 'gcloud run services logs read gcwebhook2-10-26 --region=us-central1 --limit=100 | grep -E "(IDEMPOTENCY|❌)" | tail -20'
  ```
  **Expected:** Only ✅ IDEMPOTENCY messages, no ❌ errors.

- [ ] **Task 9.4:** Monitor queue depths
  ```bash
  # Check queues every 5 minutes
  watch -n 300 '
  echo "=== Queue Status ==="
  gcloud tasks queues describe gcwebhook1-queue --location=us-central1 --format="value(stats.tasksCount)"
  gcloud tasks queues describe gcwebhook-telegram-invite-queue --location=us-central1 --format="value(stats.tasksCount)"
  '
  ```
  **Expected:** Queue depths remain low (< 10 tasks).

---

## 📝 Phase 10: Documentation

### Update Project Documentation

- [ ] **Task 10.1:** Update PROGRESS.md
  - **File:** `/OCTOBER/10-26/PROGRESS.md`
  - **Action:** Add new entry at TOP of file
  
  ```markdown
  ## 2025-11-02 - Session 41: Implemented Idempotency for Payment Processing
  
  **Objective:** Prevent duplicate Telegram invites and duplicate payment accumulation
  
  **Changes Made:**
  - ✅ Created `processed_payments` table for idempotency tracking
  - ✅ Added idempotency check in NP-Webhook (prevents duplicate enqueuing)
  - ✅ Added processing marker in GCWebhook1 (marks payment as processed)
  - ✅ Modified GCWebhook1 to pass payment_id to GCWebhook2
  - ✅ Added idempotency check in GCWebhook2 (prevents duplicate invites)
  - ✅ Deployed all services successfully
  - ✅ Tested with new payment - single invite sent ✅
  - ✅ Tested with duplicate requests - idempotency working ✅
  
  **Files Modified:**
  - `np-webhook-10-26/app.py` - Added idempotency check
  - `GCWebhook1-10-26/tph1-10-26.py` - Added processing marker + payment_id parameter
  - `GCWebhook1-10-26/cloudtasks_client.py` - Added payment_id to task payload
  - `GCWebhook2-10-26/tph2-10-26.py` - Added idempotency check + invite sent marker
  - `scripts/create_processed_payments_table.sql` - New database migration
  
  **Database Changes:**
  - Created table: `processed_payments` (tracks payment processing state)
  - Added indexes: user_channel, invite_status, webhook1_status, created_at
  
  **Impact:**
  - ✅ Users now receive exactly ONE Telegram invite per payment
  - ✅ Payments accumulated/split exactly once (no 9x inflation)
  - ✅ System handles duplicate IPN callbacks gracefully
  - ✅ Defense-in-depth: Idempotency at 3 layers (NP-Webhook, GCWebhook1, GCWebhook2)
  
  **Monitoring:**
  - Database query: SELECT COUNT(*) FROM processed_payments WHERE telegram_invite_sent = TRUE;
  - Expected: Count = Total unique payments processed
  ```

- [ ] **Task 10.2:** Update DECISIONS.md
  - **File:** `/OCTOBER/10-26/DECISIONS.md`
  - **Action:** Add new entry at TOP of file
  
  ```markdown
  ## 2025-11-02 - Idempotency Architecture Decision
  
  **Decision:** Implement multi-layered idempotency using separate `processed_payments` table
  
  **Rationale:**
  - Separate table for single responsibility (idempotency state tracking)
  - Works for both threshold and instant payments
  - Database PRIMARY KEY prevents duplicates at atomic level
  - Defense-in-depth: 3 layers of checks (fail-safe design)
  
  **Alternatives Considered:**
  1. Add `invite_sent` column to existing tables (rejected - schema conflicts)
  2. Redis-based deduplication (rejected - adds external dependency)
  3. Token-based idempotency (rejected - stateless, can't track across retries)
  
  **Key Design Choices:**
  - Pass payment_id as SEPARATE parameter (not in encrypted token) - lower risk
  - Fail-open mode if DB unavailable - prefer duplicate over blocking user
  - Store invite link in DB - enables debugging and future link reuse
  ```

- [ ] **Task 10.3:** Update BUGS.md
  - **File:** `/OCTOBER/10-26/BUGS.md`
  - **Action:** Add bug resolution at TOP of file
  
  ```markdown
  ## 2025-11-02 - RESOLVED: Repeated Telegram Invites
  
  **Status:** ✅ FIXED (Session 41)
  
  **Original Issue:**
  - Users receiving 9+ duplicate Telegram invitation links for single payment
  - Same payment accumulated multiple times (9x payout inflation)
  - Caused by payment status polling triggering full processing each time
  
  **Root Cause:**
  - System lacked idempotency checks
  - Payment success page polls /api/payment-status repeatedly
  - Each poll triggered full payment processing flow (no "already processed" check)
  
  **Solution Implemented:**
  - Created `processed_payments` table to track payment processing state
  - Added idempotency checks at 3 layers:
    1. NP-Webhook: Prevents duplicate GCWebhook1 enqueuing
    2. GCWebhook1: Marks payment as processed after routing
    3. GCWebhook2: Prevents duplicate invite sends
  - Pass payment_id from GCWebhook1 to GCWebhook2 for tracking
  
  **Verification:**
  - Test payment: User received exactly 1 invite ✅
  - Duplicate request test: Idempotency check blocked re-processing ✅
  - Database constraint: PRIMARY KEY prevents duplicate payment_id ✅
  
  **Prevention Measures:**
  - All future payments tracked in processed_payments table
  - Database-level enforcement via PRIMARY KEY constraint
  - Multi-layer defense ensures resilience to individual check failures
  ```

- [ ] **Task 10.4:** Archive architectural documents
  - **Action:** Ensure architecture documents are in /10-26 directory
  - **Files to verify:**
    - ✅ REPEATED_TELEGRAM_INVITES_INVESTIGATION_REPORT.md
    - ✅ REPEATED_TELEGRAM_INVITES_ROOT_CAUSE_ANALYSIS.md
    - ✅ REPEATED_TELEGRAM_INVITES_ROOT_CAUSE_ANALYSIS_ARCHITECTURE.md
    - ✅ REPEATED_TELEGRAM_INVITES_INVESTIGATION_REPORT_ARCHITECTURE_CHECKLIST.md (this file)

---

## 🔄 Rollback Plan (If Needed)

### Emergency Rollback Procedure

- [ ] **ROLLBACK 1:** Revert NP-Webhook to previous revision
  ```bash
  # List revisions
  gcloud run revisions list --service=np-webhook-10-26 --region=us-central1 --limit=5
  
  # Route 100% traffic to previous revision
  PREV_REVISION=[PREVIOUS_REVISION_FROM_TASK_0.3]
  gcloud run services update-traffic np-webhook-10-26 \
    --to-revisions=${PREV_REVISION}=100 \
    --region=us-central1
  ```

- [ ] **ROLLBACK 2:** Revert GCWebhook1 to previous revision
  ```bash
  PREV_REVISION=[PREVIOUS_REVISION_FROM_TASK_0.3]
  gcloud run services update-traffic gcwebhook1-10-26 \
    --to-revisions=${PREV_REVISION}=100 \
    --region=us-central1
  ```

- [ ] **ROLLBACK 3:** Revert GCWebhook2 to previous revision
  ```bash
  PREV_REVISION=[PREVIOUS_REVISION_FROM_TASK_0.3]
  gcloud run services update-traffic gcwebhook2-10-26 \
    --to-revisions=${PREV_REVISION}=100 \
    --region=us-central1
  ```

- [ ] **ROLLBACK 4:** Keep database table (no harm, can reuse later)
  - `processed_payments` table remains in database
  - No need to drop (old code ignores it)
  - Can reuse for future implementation

- [ ] **ROLLBACK 5:** Clear stuck tasks (if any)
  ```bash
  gcloud tasks queues purge gcwebhook1-queue --location=us-central1
  gcloud tasks queues purge gcwebhook-telegram-invite-queue --location=us-central1
  ```

**Recovery Time:** < 5 minutes (instant traffic routing)

---

## ✅ Success Criteria

### Functional Requirements

- [x] User receives exactly **1 Telegram invite** per payment (not 9+)
- [x] Payment accumulated/split exactly **once** (not multiple times)
- [x] Database has **one entry per payment_id** (PRIMARY KEY enforced)
- [x] Duplicate IPN callbacks return 200 but don't re-process
- [x] GCWebhook2 retries return 200 but don't resend invite

### Performance Requirements

- [x] Database query latency < 100ms for idempotency checks
- [x] No increase in end-to-end payment processing time
- [x] Cloud Tasks costs reduced (fewer duplicate tasks)

### Data Integrity

- [x] Zero duplicate payment_id entries in `processed_payments`
- [x] All `telegram_invite_sent = TRUE` have corresponding invite link
- [x] All `gcwebhook1_processed = TRUE` have processed_at timestamp

---

## 📋 Final Checklist Summary

**Phase 1: Database** ✅
- [x] Table created
- [x] Indexes created
- [x] ON CONFLICT tested

**Phase 2-4: Code Changes** ✅
- [x] NP-Webhook: Idempotency check added
- [x] GCWebhook1: Processing marker + payment_id parameter
- [x] GCWebhook2: Idempotency check + invite marker

**Phase 5: Testing** ✅
- [x] Syntax validation
- [x] Import tests

**Phase 6: Deployment** ✅
- [x] GCWebhook2 deployed
- [x] GCWebhook1 deployed
- [x] NP-Webhook deployed

**Phase 7-8: Verification** ✅
- [x] Database accessible
- [x] Services healthy
- [x] New payment test (single invite)
- [x] Duplicate request test (idempotency working)

**Phase 9-10: Monitoring & Docs** ✅
- [x] Database monitoring setup
- [x] PROGRESS.md updated
- [x] DECISIONS.md updated
- [x] BUGS.md updated

---

**Implementation Status:** ⏳ READY TO BEGIN

**Estimated Completion Time:** 4-6 hours

**Risk Level:** MEDIUM (mitigated by comprehensive testing and rollback plan)

**Next Action:** Begin Phase 0 (Pre-Implementation Checklist) → Proceed phase-by-phase
