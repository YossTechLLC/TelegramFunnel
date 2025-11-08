# GCHOSTPAY3 ERROR HANDLING IMPLEMENTATION CHECKLIST

**Created**: 2025-11-01
**Status**: 🟡 Ready for Execution
**Version**: 1.0
**Architecture Doc**: See `MAIN_GCHOSTPAY_ERROR_ARCHITECTURE.md`

---

## OVERVIEW

This checklist implements the 3-attempt retry logic and failed transaction handling architecture for GCHostPay3. Execute phases sequentially to minimize risk.

**Total Estimated Time**: 6-8 hours
**Phases**: 4 (Database → Core Logic → Integration → Recovery)
**Risk Level**: Medium (Phase 2), Low (all others)

---

## PHASE 1: DATABASE SETUP
**Estimated Time**: 30 minutes
**Risk Level**: None (read-only addition)
**Dependencies**: PostgreSQL access to telepaydb

### ✅ Tasks

- [ ] **1.1 Create SQL Migration Script**
  - [ ] Create file: `create_failed_transactions_table.sql`
  - [ ] Copy SQL from architecture doc (Appendix section)
  - [ ] Review schema definition
  - [ ] Verify all indexes are included
  - [ ] Add rollback script at bottom (DROP TABLE IF EXISTS)

- [ ] **1.2 Test Migration Locally (Optional)**
  - [ ] Connect to telepaypsql-clone-preclaude (test instance)
  - [ ] Run migration script
  - [ ] Verify table created: `\d failed_transactions`
  - [ ] Verify indexes: `\di failed_transactions*`
  - [ ] Test sample INSERT query
  - [ ] Test sample SELECT query
  - [ ] Rollback: `DROP TABLE failed_transactions CASCADE;`

- [ ] **1.3 Execute Migration on Production**
  - [ ] Connect to telepaypsql database instance
  - [ ] Run migration script:
    ```bash
    psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
         -U postgres -d telepaydb \
         -f create_failed_transactions_table.sql
    ```
  - [ ] Verify table creation:
    ```sql
    SELECT table_name, column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'failed_transactions'
    ORDER BY ordinal_position;
    ```
  - [ ] Verify row count (should be 0):
    ```sql
    SELECT COUNT(*) FROM failed_transactions;
    ```
  - [ ] Verify indexes exist:
    ```sql
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE tablename = 'failed_transactions';
    ```

- [ ] **1.4 Document Migration**
  - [ ] Update PROGRESS.md with Phase 1 completion
  - [ ] Note migration timestamp
  - [ ] Commit migration script to git (future reference)

### ✅ Verification Checklist

- [ ] Table `failed_transactions` exists in telepaydb
- [ ] All 6 indexes created successfully
- [ ] No errors in migration log
- [ ] Table has 0 rows (fresh start)

### 🔄 Rollback Procedure (if needed)

```sql
BEGIN;
DROP TABLE IF EXISTS failed_transactions CASCADE;
COMMIT;
```

---

## PHASE 2: CORE LOGIC IMPLEMENTATION (GCHOSTPAY3)
**Estimated Time**: 3-4 hours
**Risk Level**: Medium
**Dependencies**: Phase 1 complete

### ✅ Tasks

#### 2.1 Create Error Classification Module

- [ ] **2.1.1 Create error_classifier.py**
  - [ ] Create file: `GCHostPay3-10-26/error_classifier.py`
  - [ ] Implement `ErrorClassifier` class
  - [ ] Define CRITICAL_ERRORS dictionary (INSUFFICIENT_FUNDS, INVALID_ADDRESS, etc.)
  - [ ] Define TRANSIENT_ERRORS dictionary (NETWORK_TIMEOUT, RATE_LIMIT_EXCEEDED, etc.)
  - [ ] Define CONFIG_ERRORS dictionary (RPC_CONNECTION_FAILED, etc.)
  - [ ] Implement `classify_error(exception)` method
  - [ ] Implement `get_error_description(error_code)` method
  - [ ] Add docstrings and comments

- [ ] **2.1.2 Test Error Classifier Locally**
  - [ ] Create test script: `test_error_classifier.py`
  - [ ] Test classification of various exception types:
    ```python
    # Test insufficient funds
    e = ValueError("insufficient funds for gas * price + value")
    code, retryable = ErrorClassifier.classify_error(e)
    assert code == "INSUFFICIENT_FUNDS"
    assert retryable == False

    # Test rate limit
    e = requests.exceptions.HTTPError("429 Too Many Requests")
    code, retryable = ErrorClassifier.classify_error(e)
    assert code == "RATE_LIMIT_EXCEEDED"
    assert retryable == True

    # Test unknown error
    e = Exception("Something completely unexpected")
    code, retryable = ErrorClassifier.classify_error(e)
    assert code == "UNKNOWN_ERROR"
    assert retryable == False
    ```
  - [ ] Verify all error patterns match correctly
  - [ ] Test `get_error_description()` for all error codes

#### 2.2 Create Alerting Module

- [ ] **2.2.1 Create alerting.py**
  - [ ] Create file: `GCHostPay3-10-26/alerting.py`
  - [ ] Implement `AlertingService` class
  - [ ] Add Slack webhook configuration support
  - [ ] Implement `send_payment_failure_alert()` method
  - [ ] Add structured Cloud Logging output (JSON format)
  - [ ] Add error handling (alerting failure should not break payment flow)
  - [ ] Add configuration toggle (ALERTING_ENABLED secret)

- [ ] **2.2.2 Configure Slack Webhook (Optional)**
  - [ ] Create Slack incoming webhook URL
  - [ ] Store in Secret Manager: `SLACK_ALERT_WEBHOOK`
  - [ ] Test webhook with curl:
    ```bash
    curl -X POST $SLACK_WEBHOOK_URL \
      -H 'Content-Type: application/json' \
      -d '{"text": "Test alert from GCHostPay3"}'
    ```
  - [ ] Verify message appears in Slack channel

- [ ] **2.2.3 Create ALERTING_ENABLED Secret**
  - [ ] Create secret in Secret Manager:
    ```bash
    echo -n "true" | gcloud secrets create ALERTING_ENABLED \
      --data-file=- \
      --replication-policy=automatic
    ```
  - [ ] Grant GCHostPay3 service account access:
    ```bash
    gcloud secrets add-iam-policy-binding ALERTING_ENABLED \
      --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
    ```

#### 2.3 Update Database Manager

- [ ] **2.3.1 Add Failed Transaction Methods**
  - [ ] Edit: `GCHostPay3-10-26/database_manager.py`
  - [ ] Add import: `import json` (for JSONB handling)
  - [ ] Implement `insert_failed_transaction()` method
    - [ ] Parameters: unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address, context, error_code, error_message, error_details, attempt_count
    - [ ] Convert error_details dict to JSON string
    - [ ] Handle NUMERIC precision for from_amount
    - [ ] Return bool (success/failure)
  - [ ] Implement `get_failed_transaction_by_unique_id()` method
    - [ ] Return dict with all fields or None
    - [ ] Parse JSONB error_details back to dict
  - [ ] Implement `update_failed_transaction_status()` method
    - [ ] Parameters: unique_id, status, admin_notes
    - [ ] Update updated_at timestamp
  - [ ] Implement `get_retryable_failed_transactions()` method
    - [ ] Query WHERE status='failed_retryable'
    - [ ] LIMIT and OFFSET support for pagination
  - [ ] Implement `mark_failed_transaction_recovered()` method
    - [ ] Parameters: unique_id, recovery_tx_hash, recovered_by
    - [ ] Set status='recovered', recovered_at=NOW()

- [ ] **2.3.2 Test Database Methods Locally**
  - [ ] Create test script: `test_database_manager.py`
  - [ ] Test insert_failed_transaction():
    ```python
    success = db_manager.insert_failed_transaction(
        unique_id="TEST123456789012",
        cn_api_id="test_cn_id",
        from_currency="eth",
        from_network="eth",
        from_amount=0.001234,
        payin_address="0x1234567890abcdef",
        context="instant",
        error_code="RATE_LIMIT_EXCEEDED",
        error_message="429 Too Many Requests",
        error_details={"status_code": 429, "attempt": 3},
        attempt_count=3
    )
    assert success == True
    ```
  - [ ] Test get_failed_transaction_by_unique_id()
  - [ ] Test update_failed_transaction_status()
  - [ ] Test mark_failed_transaction_recovered()
  - [ ] Clean up test data:
    ```sql
    DELETE FROM failed_transactions WHERE unique_id LIKE 'TEST%';
    ```

#### 2.4 Update Token Manager

- [ ] **2.4.1 Add Attempt Tracking to Tokens**
  - [ ] Edit: `GCHostPay3-10-26/token_manager.py`
  - [ ] Update `decrypt_gchostpay1_to_gchostpay3_token()`:
    - [ ] Add backward compatibility for attempt_count (default to 1)
    - [ ] Add backward compatibility for first_attempt_at
    - [ ] Add backward compatibility for last_error_code
  - [ ] Create new method: `encrypt_gchostpay3_retry_token()`:
    - [ ] Accept token_data dict and error_code
    - [ ] Increment attempt_count by 1
    - [ ] Set last_error_code
    - [ ] Return encrypted token string
  - [ ] Update `encrypt_gchostpay1_to_gchostpay3_token()`:
    - [ ] Add attempt_count=1 to new tokens (from GCHostPay1)
    - [ ] Add first_attempt_at=current_timestamp
    - [ ] Add last_error_code=None

- [ ] **2.4.2 Test Token Encryption/Decryption**
  - [ ] Create test script: `test_token_manager.py`
  - [ ] Test new token creation (from GCHostPay1):
    ```python
    token = token_manager.encrypt_gchostpay1_to_gchostpay3_token(
        unique_id="test123",
        cn_api_id="cn123",
        from_currency="eth",
        from_network="eth",
        from_amount=0.001,
        payin_address="0xabc",
        context="instant"
    )
    decrypted = token_manager.decrypt_gchostpay1_to_gchostpay3_token(token)
    assert decrypted['attempt_count'] == 1
    assert 'first_attempt_at' in decrypted
    ```
  - [ ] Test retry token creation:
    ```python
    retry_token = token_manager.encrypt_gchostpay3_retry_token(
        decrypted,
        error_code="NETWORK_TIMEOUT"
    )
    retry_decrypted = token_manager.decrypt_gchostpay1_to_gchostpay3_token(retry_token)
    assert retry_decrypted['attempt_count'] == 2
    assert retry_decrypted['last_error_code'] == "NETWORK_TIMEOUT"
    ```

#### 2.5 Update Cloud Tasks Client

- [ ] **2.5.1 Add Retry Enqueue Method**
  - [ ] Edit: `GCHostPay3-10-26/cloudtasks_client.py`
  - [ ] Create new method: `enqueue_gchostpay3_retry()`:
    - [ ] Parameters: queue_name, target_url, encrypted_token, schedule_delay_seconds
    - [ ] Create Cloud Task with delay (in_seconds parameter)
    - [ ] Return task name
  - [ ] Add error handling and logging

- [ ] **2.5.2 Create Retry Queue**
  - [ ] Create Cloud Tasks queue:
    ```bash
    gcloud tasks queues create gchostpay3-retry-queue \
      --location=us-central1 \
      --max-dispatches-per-second=10 \
      --max-concurrent-dispatches=5 \
      --max-attempts=1 \
      --min-backoff=60s \
      --max-backoff=60s \
      --max-retry-duration=0s
    ```
  - [ ] Verify queue created:
    ```bash
    gcloud tasks queues describe gchostpay3-retry-queue \
      --location=us-central1
    ```

- [ ] **2.5.3 Create Secret for Retry Queue**
  - [ ] Create secret:
    ```bash
    echo -n "gchostpay3-retry-queue" | gcloud secrets create GCHOSTPAY3_RETRY_QUEUE \
      --data-file=- \
      --replication-policy=automatic
    ```
  - [ ] Grant access to GCHostPay3:
    ```bash
    gcloud secrets add-iam-policy-binding GCHOSTPAY3_RETRY_QUEUE \
      --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
    ```

#### 2.6 Update Config Manager

- [ ] **2.6.1 Add New Secret Getters**
  - [ ] Edit: `GCHostPay3-10-26/config_manager.py`
  - [ ] Add `get_gchostpay3_retry_queue()` method
  - [ ] Add `get_gchostpay3_url()` method (for self URL)
  - [ ] Add `get_alerting_enabled()` method
  - [ ] Add `get_slack_alert_webhook()` method (optional)

- [ ] **2.6.2 Create GCHOSTPAY3_URL Secret**
  - [ ] Create secret:
    ```bash
    echo -n "https://gchostpay3-10-26-291176869049.us-central1.run.app" | \
      gcloud secrets create GCHOSTPAY3_URL \
      --data-file=- \
      --replication-policy=automatic
    ```
  - [ ] Grant access:
    ```bash
    gcloud secrets add-iam-policy-binding GCHOSTPAY3_URL \
      --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
    ```

#### 2.7 Update Main Service File

- [ ] **2.7.1 Modify execute_eth_payment() Endpoint**
  - [ ] Edit: `GCHostPay3-10-26/tphp3-10-26.py`
  - [ ] Import new modules:
    ```python
    from error_classifier import ErrorClassifier
    from alerting import AlertingService
    ```
  - [ ] Initialize AlertingService in app startup
  - [ ] Extract attempt_count from decrypted token
  - [ ] Add attempt limit check (>3 = skip)
  - [ ] Wrap wallet_manager.send_eth_payment_with_infinite_retry() in try/except
  - [ ] On success: Keep existing flow (log DB, callback GCHostPay1)
  - [ ] On failure:
    - [ ] Classify error using ErrorClassifier
    - [ ] If attempt_count < 3:
      - [ ] Re-encrypt token with incremented count
      - [ ] Enqueue retry task to self (60s delay)
      - [ ] Return 200 with retry_scheduled status
    - [ ] If attempt_count >= 3:
      - [ ] Store in failed_transactions via db_manager
      - [ ] Send alert via AlertingService
      - [ ] Return 200 with failed_permanently status
  - [ ] Add structured logging for all paths

- [ ] **2.7.2 Remove Infinite Retry from Wallet Manager**
  - [ ] Edit: `GCHostPay3-10-26/wallet_manager.py`
  - [ ] Modify `send_eth_payment_with_infinite_retry()` method:
    - [ ] Remove outer while True loop
    - [ ] Keep single attempt logic
    - [ ] Return result or raise exception (don't retry internally)
    - [ ] Rename method to `send_eth_payment()` (no longer infinite retry)
  - [ ] Update method docstring

#### 2.8 Code Review & Testing

- [ ] **2.8.1 Code Review**
  - [ ] Review all modified files for consistency
  - [ ] Check error handling in all new methods
  - [ ] Verify logging uses existing emoji patterns
  - [ ] Ensure all secrets are fetched from Secret Manager
  - [ ] Check for SQL injection vulnerabilities (use parameterized queries)

- [ ] **2.8.2 Local Testing (if possible)**
  - [ ] Run service locally with test configuration
  - [ ] Mock payment failure (invalid address)
  - [ ] Verify 3 retry attempts occur
  - [ ] Verify failed transaction stored in DB
  - [ ] Verify alert sent (if enabled)

### ✅ Verification Checklist

- [ ] All new files created and committed
- [ ] All existing files updated with new logic
- [ ] No syntax errors in Python code
- [ ] All imports resolved
- [ ] Secrets created and accessible
- [ ] Cloud Tasks retry queue created

### 🔄 Rollback Procedure (if needed)

**Before deployment:**
1. Git commit all changes: `git add . && git commit -m "Phase 2: GCHostPay3 3-attempt retry logic"`
2. Note current revision: `gcloud run services describe gchostpay3-10-26 --region=us-central1 --format="value(status.latestCreatedRevisionName)"`

**If issues occur after deployment:**
```bash
# Rollback to previous revision
PREVIOUS_REVISION="gchostpay3-10-26-00009-xyz"  # Replace with actual
gcloud run services update-traffic gchostpay3-10-26 \
  --to-revisions=$PREVIOUS_REVISION=100 \
  --region=us-central1
```

---

## PHASE 3: DEPLOYMENT & PRODUCTION TESTING
**Estimated Time**: 1 hour
**Risk Level**: Medium
**Dependencies**: Phase 2 complete

### ✅ Tasks

#### 3.1 Pre-Deployment Checks

- [ ] **3.1.1 Environment Verification**
  - [ ] Verify all secrets exist:
    ```bash
    gcloud secrets list | grep -E "(GCHOSTPAY3_RETRY_QUEUE|GCHOSTPAY3_URL|ALERTING_ENABLED)"
    ```
  - [ ] Verify failed_transactions table exists:
    ```sql
    SELECT COUNT(*) FROM failed_transactions;
    ```
  - [ ] Verify retry queue exists:
    ```bash
    gcloud tasks queues describe gchostpay3-retry-queue --location=us-central1
    ```

- [ ] **3.1.2 Create Deployment Backup**
  - [ ] Note current revision:
    ```bash
    gcloud run services describe gchostpay3-10-26 \
      --region=us-central1 \
      --format="value(status.latestCreatedRevisionName)" \
      > GCHOSTPAY3_PREVIOUS_REVISION.txt
    ```
  - [ ] Export current environment variables:
    ```bash
    gcloud run services describe gchostpay3-10-26 \
      --region=us-central1 \
      --format="yaml(spec.template.spec.containers[0].env)" \
      > GCHOSTPAY3_ENV_BACKUP.yaml
    ```

#### 3.2 Deploy GCHostPay3

- [ ] **3.2.1 Build and Deploy**
  - [ ] Navigate to service directory:
    ```bash
    cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay3-10-26
    ```
  - [ ] Deploy service:
    ```bash
    gcloud run deploy gchostpay3-10-26 \
      --source . \
      --region=us-central1 \
      --allow-unauthenticated \
      --timeout=3600 \
      --memory=512Mi \
      --cpu=1 \
      --max-instances=10 \
      --min-instances=0
    ```
  - [ ] Wait for deployment to complete
  - [ ] Note new revision number

- [ ] **3.2.2 Verify Deployment**
  - [ ] Check service health:
    ```bash
    curl https://gchostpay3-10-26-291176869049.us-central1.run.app/health
    ```
  - [ ] Verify response shows all components healthy:
    ```json
    {
      "status": "healthy",
      "service": "GCHostPay3-10-26 ETH Payment Executor",
      "components": {
        "token_manager": "healthy",
        "wallet": "healthy",
        "database": "healthy",
        "cloudtasks": "healthy"
      }
    }
    ```
  - [ ] Check Cloud Run logs for initialization errors:
    ```bash
    gcloud run services logs read gchostpay3-10-26 \
      --region=us-central1 \
      --limit=50
    ```

#### 3.3 Production Testing

- [ ] **3.3.1 Test with Simulated Failure (Manual)**
  - [ ] Create test payment with invalid amount (to trigger failure)
  - [ ] Monitor logs for 3 retry attempts:
    ```bash
    gcloud run services logs read gchostpay3-10-26 \
      --region=us-central1 \
      --limit=100 \
      --format="table(timestamp, textPayload)"
    ```
  - [ ] Verify retry schedule:
    - [ ] Attempt 1 → Failure → 60s wait
    - [ ] Attempt 2 → Failure → 60s wait
    - [ ] Attempt 3 → Failure → Store in DB
  - [ ] Query failed_transactions table:
    ```sql
    SELECT unique_id, cn_api_id, error_code, error_message, attempt_count, status
    FROM failed_transactions
    ORDER BY created_at DESC
    LIMIT 1;
    ```
  - [ ] Verify record stored correctly
  - [ ] Verify alert sent (check Slack if configured)

- [ ] **3.3.2 Test with Real Transaction (if available)**
  - [ ] Trigger normal payment flow (via GCHostPay1)
  - [ ] Monitor for successful completion
  - [ ] Verify no errors in logs
  - [ ] Verify attempt_count=1 in logs
  - [ ] Verify successful callback to GCHostPay1

- [ ] **3.3.3 Monitor Retry Queue**
  - [ ] Check retry queue for tasks:
    ```bash
    gcloud tasks list --queue=gchostpay3-retry-queue \
      --location=us-central1
    ```
  - [ ] Verify tasks execute on schedule
  - [ ] Verify no stuck tasks

#### 3.4 Post-Deployment Verification

- [ ] **3.4.1 Check Error Logs**
  - [ ] Review Cloud Run logs for errors:
    ```bash
    gcloud logging read "resource.type=cloud_run_revision AND \
      resource.labels.service_name=gchostpay3-10-26 AND \
      severity>=ERROR" \
      --limit=50 \
      --format=json
    ```
  - [ ] Investigate any unexpected errors
  - [ ] Verify no critical failures

- [ ] **3.4.2 Database Validation**
  - [ ] Check failed_transactions table has expected data:
    ```sql
    SELECT
      COUNT(*) as total_failures,
      error_code,
      status
    FROM failed_transactions
    GROUP BY error_code, status;
    ```
  - [ ] Verify no duplicate entries (same unique_id)
  - [ ] Verify JSONB error_details are valid

- [ ] **3.4.3 Alert Validation**
  - [ ] If Slack configured: Verify alert received
  - [ ] Check Cloud Logging for structured alert events:
    ```bash
    gcloud logging read "jsonPayload.event_type=\"eth_payment_failed_permanently\"" \
      --limit=10 \
      --format=json
    ```

### ✅ Verification Checklist

- [ ] GCHostPay3 deployed successfully (new revision)
- [ ] Health check returns healthy status
- [ ] 3-attempt retry logic working correctly
- [ ] Failed transactions stored in database
- [ ] Alerts sent on permanent failures
- [ ] No critical errors in logs
- [ ] Retry queue processing tasks correctly

### 🔄 Rollback Procedure (if critical issues)

```bash
# Read previous revision from backup
PREVIOUS_REVISION=$(cat GCHOSTPAY3_PREVIOUS_REVISION.txt)

# Rollback traffic to previous revision
gcloud run services update-traffic gchostpay3-10-26 \
  --to-revisions=$PREVIOUS_REVISION=100 \
  --region=us-central1

# Verify rollback
gcloud run services describe gchostpay3-10-26 \
  --region=us-central1 \
  --format="value(status.traffic[0].revisionName)"
```

---

## PHASE 4: UPSTREAM INTEGRATION (OPTIONAL)
**Estimated Time**: 2-3 hours
**Risk Level**: Low
**Dependencies**: Phase 3 complete and stable

### ✅ Tasks

#### 4.1 Update GCHostPay1

- [ ] **4.1.1 Add Payment Failed Endpoint**
  - [ ] Edit: `GCHostPay1-10-26/tphp1-10-26.py`
  - [ ] Create new endpoint: `POST /payment-failed`
  - [ ] Decrypt token from GCHostPay3
  - [ ] Extract context (instant/threshold/batch)
  - [ ] Route based on context:
    - [ ] batch → Enqueue to GCMicroBatchProcessor /batch-payment-failed
    - [ ] threshold → Enqueue to GCAccumulator /payment-failed (future)
    - [ ] instant → Mark split_payout_que as failed
  - [ ] Log failure details
  - [ ] Return 200

- [ ] **4.1.2 Update Token Manager**
  - [ ] Edit: `GCHostPay1-10-26/token_manager.py`
  - [ ] Create method: `decrypt_gchostpay3_failure_token()`
  - [ ] Create method: `encrypt_gchostpay1_to_microbatch_failure_token()`

- [ ] **4.1.3 Test Locally**
  - [ ] Create test script
  - [ ] Mock failure notification from GCHostPay3
  - [ ] Verify routing logic works
  - [ ] Verify token encryption/decryption

#### 4.2 Update GCHostPay3 Failure Notification

- [ ] **4.2.1 Add Upstream Notification**
  - [ ] Edit: `GCHostPay3-10-26/tphp3-10-26.py`
  - [ ] In 3rd attempt failure path (after storing failed transaction)
  - [ ] Encrypt failure token with context
  - [ ] Enqueue to GCHostPay1 /payment-failed
  - [ ] Add error handling (notification failure should not break flow)

- [ ] **4.2.2 Create Notification Method**
  - [ ] Add method: `notify_upstream_failure()`
  - [ ] Parameters: context, unique_id, cn_api_id, error_code
  - [ ] Encrypt token using token_manager
  - [ ] Enqueue to GCHostPay1 via cloudtasks_client

#### 4.3 Update GCMicroBatchProcessor

- [ ] **4.3.1 Add Batch Payment Failed Endpoint**
  - [ ] Edit: `GCMicroBatchProcessor-10-26/microbatch10-26.py`
  - [ ] Create new endpoint: `POST /batch-payment-failed`
  - [ ] Decrypt token from GCHostPay1
  - [ ] Extract batch_conversion_id and error_code
  - [ ] Mark batch_conversions as failed:
    ```sql
    UPDATE batch_conversions
    SET conversion_status = 'failed',
        failed_reason = 'ETH payment failed: {error_code}',
        failed_at = NOW()
    WHERE batch_conversion_id = %s;
    ```
  - [ ] Rollback payout_accumulation records to pending:
    ```sql
    UPDATE payout_accumulation
    SET conversion_status = 'pending',
        batch_conversion_id = NULL
    WHERE batch_conversion_id = %s;
    ```
  - [ ] Send admin alert
  - [ ] Return 200

- [ ] **4.3.2 Update Database Manager**
  - [ ] Edit: `GCMicroBatchProcessor-10-26/database_manager.py`
  - [ ] Add method: `mark_batch_failed(batch_conversion_id, error_code)`
  - [ ] Add method: `rollback_batch_accumulations(batch_conversion_id)`

- [ ] **4.3.3 Test Locally**
  - [ ] Create test batch conversion record
  - [ ] Create test payout accumulation records
  - [ ] Simulate failure callback
  - [ ] Verify batch marked as failed
  - [ ] Verify accumulations rolled back to pending

#### 4.4 Deploy Upstream Services

- [ ] **4.4.1 Deploy GCHostPay1**
  - [ ] Navigate to service directory
  - [ ] Deploy:
    ```bash
    cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay1-10-26
    gcloud run deploy gchostpay1-10-26 \
      --source . \
      --region=us-central1 \
      --allow-unauthenticated \
      --timeout=3600 \
      --memory=512Mi
    ```
  - [ ] Verify health check

- [ ] **4.4.2 Deploy GCMicroBatchProcessor**
  - [ ] Navigate to service directory
  - [ ] Deploy:
    ```bash
    cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCMicroBatchProcessor-10-26
    gcloud run deploy gcmicrobatchprocessor-10-26 \
      --source . \
      --region=us-central1 \
      --allow-unauthenticated \
      --timeout=3600 \
      --memory=512Mi
    ```
  - [ ] Verify health check

- [ ] **4.4.3 Redeploy GCHostPay3 (with upstream notification)**
  - [ ] Navigate to service directory
  - [ ] Deploy:
    ```bash
    cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay3-10-26
    gcloud run deploy gchostpay3-10-26 \
      --source . \
      --region=us-central1 \
      --allow-unauthenticated \
      --timeout=3600 \
      --memory=512Mi
    ```
  - [ ] Verify health check

#### 4.5 End-to-End Testing

- [ ] **4.5.1 Test Batch Failure Flow**
  - [ ] Trigger micro-batch conversion with invalid amount
  - [ ] Monitor GCHostPay3 logs for 3 attempts
  - [ ] Verify failure notification sent to GCHostPay1
  - [ ] Verify GCHostPay1 routes to GCMicroBatchProcessor
  - [ ] Verify batch marked as failed
  - [ ] Verify accumulations rolled back to pending
  - [ ] Verify alert sent

- [ ] **4.5.2 Test Recovery Flow**
  - [ ] Fix upstream bug (if applicable)
  - [ ] Wait for next micro-batch threshold check (15 min)
  - [ ] Verify rolled-back accumulations picked up again
  - [ ] Verify new batch created successfully

### ✅ Verification Checklist

- [ ] GCHostPay1 has /payment-failed endpoint
- [ ] GCMicroBatchProcessor has /batch-payment-failed endpoint
- [ ] GCHostPay3 sends failure notifications
- [ ] End-to-end failure flow working
- [ ] Rollback logic working correctly
- [ ] No errors in any service logs

### 🔄 Rollback Procedure (if needed)

Same as Phase 3 - rollback each service individually to previous revision.

---

## PHASE 5: RECOVERY ENDPOINTS (OPTIONAL - FUTURE)
**Estimated Time**: 2 hours
**Risk Level**: Low
**Dependencies**: Phase 3 complete

**Note**: These are manual intervention endpoints. Not critical for initial deployment.

### ✅ Tasks

- [ ] **5.1 Add Manual Retry Endpoint**
  - [ ] Edit: `GCHostPay3-10-26/tphp3-10-26.py`
  - [ ] Create endpoint: `POST /retry-failed-transaction`
  - [ ] Add authentication (admin token)
  - [ ] Implement retry logic (see architecture doc)
  - [ ] Test with failed transaction

- [ ] **5.2 Add List Failed Transactions Endpoint**
  - [ ] Create endpoint: `GET /failed-transactions`
  - [ ] Add query parameter filtering (status, error_code)
  - [ ] Add pagination support (limit, offset)
  - [ ] Test with multiple failed transactions

- [ ] **5.3 Add Update Status Endpoint**
  - [ ] Create endpoint: `PUT /failed-transactions/{unique_id}/status`
  - [ ] Add authentication
  - [ ] Implement status update logic
  - [ ] Test status transitions

- [ ] **5.4 Deploy Recovery Endpoints**
  - [ ] Deploy GCHostPay3 with new endpoints
  - [ ] Test all endpoints with Postman/curl
  - [ ] Document API usage

### ✅ Verification Checklist

- [ ] Manual retry endpoint working
- [ ] List endpoint returning correct data
- [ ] Update status endpoint working
- [ ] All endpoints authenticated (if required)

---

## POST-IMPLEMENTATION TASKS

### Documentation

- [ ] **Update PROGRESS.md**
  - [ ] Document Phase 1 completion (database)
  - [ ] Document Phase 2 completion (core logic)
  - [ ] Document Phase 3 completion (deployment)
  - [ ] Document Phase 4 completion (upstream integration)
  - [ ] Note all new revisions deployed

- [ ] **Update BUGS.md**
  - [ ] Mark infinite retry bug as RESOLVED
  - [ ] Document 3-attempt solution
  - [ ] Add transaction ID examples

- [ ] **Update DECISIONS.md**
  - [ ] Document decision to use 3-attempt limit
  - [ ] Document decision to use self-retry pattern
  - [ ] Document error classification approach
  - [ ] Document failed transaction storage schema

- [ ] **Create Operations Guide**
  - [ ] How to view failed transactions
  - [ ] How to manually retry failed transactions
  - [ ] How to investigate error codes
  - [ ] How to update failed transaction status

### Monitoring Setup

- [ ] **Create Cloud Monitoring Dashboards**
  - [ ] Failed transactions count (by error_code)
  - [ ] Payment attempt distribution (1, 2, 3)
  - [ ] Recovery success rate

- [ ] **Create Alert Policies**
  - [ ] Alert on >5 failed transactions in 1 hour
  - [ ] Alert on INSUFFICIENT_FUNDS error (immediate)
  - [ ] Alert on >10 RATE_LIMIT_EXCEEDED in 1 hour

- [ ] **Set up Log-Based Metrics**
  - [ ] Metric: failed_transactions_count
  - [ ] Metric: payment_retry_attempts
  - [ ] Metric: recovery_attempts

### Cleanup

- [ ] **Remove Test Data**
  - [ ] Delete test failed transactions:
    ```sql
    DELETE FROM failed_transactions WHERE unique_id LIKE 'TEST%';
    ```
  - [ ] Verify production data only

- [ ] **Commit All Changes**
  - [ ] Git add all modified files
  - [ ] Commit with message: "Implement GCHostPay3 3-attempt retry and failed transaction handling"
  - [ ] Note: User will commit manually after review

---

## FINAL VERIFICATION

### System Health Check

- [ ] **All Services Running**
  - [ ] GCHostPay1: Health check passing
  - [ ] GCHostPay2: Health check passing
  - [ ] GCHostPay3: Health check passing
  - [ ] GCMicroBatchProcessor: Health check passing
  - [ ] GCBatchProcessor: Health check passing

- [ ] **Database Integrity**
  - [ ] failed_transactions table has data
  - [ ] No orphaned records
  - [ ] All indexes working

- [ ] **Queue Health**
  - [ ] gchostpay3-retry-queue processing tasks
  - [ ] No stuck tasks in any queue
  - [ ] No excessive backlog

- [ ] **Monitoring Active**
  - [ ] Cloud Logging capturing events
  - [ ] Alerts configured and active
  - [ ] Dashboards showing data

### Success Criteria

- [ ] ✅ 3-attempt retry logic working correctly
- [ ] ✅ Failed transactions stored in database
- [ ] ✅ Error classification accurate
- [ ] ✅ Alerts sent on permanent failures
- [ ] ✅ Upstream services notified on failures
- [ ] ✅ Rollback logic working (batch conversions)
- [ ] ✅ No infinite retry loops
- [ ] ✅ No critical errors in logs
- [ ] ✅ Manual retry capability available

---

## RISK MITIGATION

### Known Risks

1. **Risk**: Code bugs in retry logic cause payment failures
   - **Mitigation**: Extensive testing in Phase 3
   - **Fallback**: Rollback to previous revision

2. **Risk**: Database insert failures block payment flow
   - **Mitigation**: Insert is non-blocking (error logged but payment continues)
   - **Fallback**: Monitor logs for insert failures

3. **Risk**: Alerting failures cause silent failures
   - **Mitigation**: Structured logging always happens (Slack is optional)
   - **Fallback**: Monitor Cloud Logging for failures

4. **Risk**: Token encryption changes break backward compatibility
   - **Mitigation**: Backward compatibility built into decrypt methods
   - **Fallback**: Old tokens still work (default attempt_count=1)

5. **Risk**: Upstream rollback logic has bugs
   - **Mitigation**: Test rollback in Phase 4.5
   - **Fallback**: Manual database updates if needed

---

## APPENDIX

### Quick Reference Commands

**Check failed transactions:**
```sql
SELECT unique_id, cn_api_id, error_code, status, created_at
FROM failed_transactions
ORDER BY created_at DESC
LIMIT 10;
```

**View service logs:**
```bash
gcloud run services logs read gchostpay3-10-26 \
  --region=us-central1 \
  --limit=100
```

**Check retry queue:**
```bash
gcloud tasks list --queue=gchostpay3-retry-queue \
  --location=us-central1
```

**Rollback service:**
```bash
gcloud run services update-traffic gchostpay3-10-26 \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=us-central1
```

**Check current revision:**
```bash
gcloud run services describe gchostpay3-10-26 \
  --region=us-central1 \
  --format="value(status.latestCreatedRevisionName)"
```

---

## COMPLETION SIGN-OFF

**Phase 1 (Database Setup)**
- [ ] Completed by: _____________
- [ ] Date: _____________
- [ ] Sign-off: _____________

**Phase 2 (Core Logic)**
- [ ] Completed by: _____________
- [ ] Date: _____________
- [ ] Sign-off: _____________

**Phase 3 (Deployment)**
- [ ] Completed by: _____________
- [ ] Date: _____________
- [ ] Sign-off: _____________

**Phase 4 (Upstream Integration)**
- [ ] Completed by: _____________
- [ ] Date: _____________
- [ ] Sign-off: _____________

**Phase 5 (Recovery Endpoints)**
- [ ] Completed by: _____________
- [ ] Date: _____________
- [ ] Sign-off: _____________

---

**END OF CHECKLIST**

**Next Steps After Completion:**
1. Monitor production for 48 hours
2. Review failed_transactions table for patterns
3. Adjust error classifications if needed
4. Fine-tune alert thresholds
5. Create operational runbooks
