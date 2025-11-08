# NowPayments Payment ID Storage - Implementation Checklist

**Created:** 2025-11-02
**Status:** READY FOR IMPLEMENTATION
**Priority:** P0 - Critical for Fee Discrepancy Resolution
**Related Documents:**
- `NOWPAYMENTS_PAYMENT_ID_STORAGE_ANALYSIS.md` - Problem analysis
- `NOWPAYMENTS_PAYMENT_ID_STORAGE_ANALYSIS_ARCHITECTURE.md` - Architectural design

---

## Quick Reference

### Critical Files to Modify
- `/OCTOBER/10-26/TelePay10-26/start_np_gateway.py` - Add ipn_callback_url
- `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py` - Add IPN endpoint + enhance main endpoint
- `/OCTOBER/10-26/GCWebhook1-10-26/database_manager.py` - Add IPN database methods
- `/OCTOBER/10-26/GCWebhook1-10-26/token_manager.py` - Extend token format
- `/OCTOBER/10-26/GCWebhook1-10-26/cloudtasks_client.py` - Enhance payloads
- `/OCTOBER/10-26/GCAccumulator-10-26/acc10-26.py` - Accept payment_id
- `/OCTOBER/10-26/GCAccumulator-10-26/database_manager.py` - Store payment_id

### Success Criteria
- ✅ **>95% payment_id capture rate** (target: 100%)
- ✅ **Zero IPN signature failures**
- ✅ **<500ms IPN processing latency**
- ✅ Backward compatibility maintained
- ✅ Zero downtime deployment

---

## Phase 1: Database Migration (Week 1, Days 1-2)

### 1.1 Preparation
- [ ] Review current database schema for `private_channel_users_database`
- [ ] Review current database schema for `payout_accumulation`
- [ ] Verify database connection credentials in Secret Manager
- [ ] Create backup of production database (precautionary)
- [ ] Test database connection from local environment

### 1.2 Migration Script Creation
- [ ] Create migration script: `/tools/execute_payment_id_migration.py`
- [ ] Add database columns for `private_channel_users_database`:
  - [ ] `nowpayments_payment_id VARCHAR(50)`
  - [ ] `nowpayments_invoice_id VARCHAR(50)`
  - [ ] `nowpayments_order_id VARCHAR(100)`
  - [ ] `nowpayments_pay_address VARCHAR(255)`
  - [ ] `nowpayments_payment_status VARCHAR(50)`
  - [ ] `nowpayments_pay_amount DECIMAL(30, 18)`
  - [ ] `nowpayments_pay_currency VARCHAR(20)`
  - [ ] `nowpayments_outcome_amount DECIMAL(30, 18)`
  - [ ] `nowpayments_created_at TIMESTAMP`
  - [ ] `nowpayments_updated_at TIMESTAMP`
- [ ] Add indexes for `private_channel_users_database`:
  - [ ] `idx_nowpayments_payment_id` on `nowpayments_payment_id`
  - [ ] `idx_nowpayments_order_id` on `nowpayments_order_id`
- [ ] Add database columns for `payout_accumulation`:
  - [ ] `nowpayments_payment_id VARCHAR(50)`
  - [ ] `nowpayments_pay_address VARCHAR(255)`
  - [ ] `nowpayments_outcome_amount DECIMAL(30, 18)`
  - [ ] `nowpayments_network_fee DECIMAL(30, 18)`
  - [ ] `payment_fee_usd DECIMAL(20, 8)`
- [ ] Add indexes for `payout_accumulation`:
  - [ ] `idx_payout_nowpayments_payment_id` on `nowpayments_payment_id`
  - [ ] `idx_payout_pay_address` on `nowpayments_pay_address`
- [ ] Use `IF NOT EXISTS` clause to ensure idempotent migrations

### 1.3 Migration Testing
- [ ] Test migration script locally (dry run)
- [ ] Verify migration script error handling
- [ ] Test rollback procedure (if needed)
- [ ] Document migration execution steps

### 1.4 Migration Execution
- [ ] Execute migration in production database
- [ ] Verify all columns created successfully
- [ ] Verify all indexes created successfully
- [ ] Check migration logs for errors
- [ ] Validate database performance (index efficiency)

### 1.5 Migration Verification
- [ ] Run verification query: Check columns exist
  ```sql
  SELECT column_name, data_type
  FROM information_schema.columns
  WHERE table_name = 'private_channel_users_database'
  AND column_name LIKE 'nowpayments_%';
  ```
- [ ] Run verification query: Check indexes exist
  ```sql
  SELECT indexname, indexdef
  FROM pg_indexes
  WHERE tablename = 'private_channel_users_database'
  AND indexname LIKE 'idx_nowpayments_%';
  ```
- [ ] Verify column count: 10 new columns in `private_channel_users_database`
- [ ] Verify column count: 5 new columns in `payout_accumulation`
- [ ] Document migration completion in `PROGRESS.md`

---

## Phase 2: IPN Endpoint Implementation (Week 1, Days 3-5)

### 2.1 Secret Manager Configuration
- [ ] Add `NOWPAYMENTS_IPN_SECRET` to Google Cloud Secret Manager
  - [ ] Get IPN secret from NowPayments dashboard
  - [ ] Create secret: `gcloud secrets create NOWPAYMENTS_IPN_SECRET`
  - [ ] Add secret version with IPN secret value
  - [ ] Grant `gcwebhook1-10-26` service account access to secret
- [ ] Add `NOWPAYMENTS_IPN_CALLBACK_URL` to Secret Manager
  - [ ] Value: `https://gcwebhook1-10-26-291176869049.us-central1.run.app/ipn`
  - [ ] Create secret: `gcloud secrets create NOWPAYMENTS_IPN_CALLBACK_URL`
  - [ ] Grant necessary service accounts access

### 2.2 GCWebhook1 - IPN Signature Verification
- [ ] Open `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`
- [ ] Add imports:
  - [ ] `import hmac`
  - [ ] `import hashlib`
- [ ] Implement `verify_ipn_signature()` function
  - [ ] Use HMAC-SHA512 (NowPayments standard)
  - [ ] Compare with `hmac.compare_digest()` for timing-safe comparison
  - [ ] Handle edge cases (missing secret, missing signature)
  - [ ] Add error logging with emoji prefixes
- [ ] Test signature verification with mock data

### 2.3 GCWebhook1 - IPN Endpoint
- [ ] Open `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`
- [ ] Add `/ipn` endpoint route (`@app.route("/ipn", methods=["POST"])`)
- [ ] Implement IPN endpoint logic:
  - [ ] Get raw payload (`request.get_data()`)
  - [ ] Get signature from header (`x-nowpayments-sig`)
  - [ ] Fetch IPN secret from config
  - [ ] Verify signature (reject if invalid with 401)
  - [ ] Parse JSON payload
  - [ ] Extract fields: `payment_id`, `invoice_id`, `order_id`, `payment_status`
  - [ ] Extract amounts: `pay_address`, `pay_amount`, `actually_paid`, `outcome_amount`
  - [ ] Extract metadata: `pay_currency`, `created_at`, `updated_at`
  - [ ] Validate required fields (return 400 if missing)
  - [ ] Idempotency check: lookup existing record by `order_id`
  - [ ] If payment_id already stored, return 200 OK (duplicate IPN)
  - [ ] Update database with NowPayments data
  - [ ] Return 200 OK to NowPayments
  - [ ] Add comprehensive logging with emoji prefixes
  - [ ] Add error handling (return 500 on failure)

### 2.4 GCWebhook1 - Database Manager Methods
- [ ] Open `/OCTOBER/10-26/GCWebhook1-10-26/database_manager.py`
- [ ] Implement `update_nowpayments_data_by_order_id()` method
  - [ ] Parameters: `order_id`, `payment_id`, `invoice_id`, `payment_status`, `pay_address`, `pay_amount`, `outcome_amount`, `pay_currency`, `created_at`, `updated_at`
  - [ ] SQL: `UPDATE private_channel_users_database SET ... WHERE nowpayments_order_id = %s`
  - [ ] Return `True` if rows updated, `False` otherwise
  - [ ] Add logging with emoji prefixes
  - [ ] Add error handling
- [ ] Implement `get_record_by_order_id()` method
  - [ ] Parameters: `order_id`
  - [ ] SQL: `SELECT ... FROM private_channel_users_database WHERE nowpayments_order_id = %s`
  - [ ] Return dict with fields or `None` if not found
  - [ ] Add error handling
- [ ] Implement `get_subscription_record()` method
  - [ ] Parameters: `user_id`, `channel_id`
  - [ ] SQL: `SELECT nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount FROM private_channel_users_database WHERE user_id = %s AND private_channel_id = %s ORDER BY subscription_time DESC LIMIT 1`
  - [ ] Return dict with NowPayments fields or `None`
  - [ ] Add error handling

### 2.5 GCWebhook1 - Config Manager Updates
- [ ] Open `/OCTOBER/10-26/GCWebhook1-10-26/config_manager.py`
- [ ] Add method to fetch `NOWPAYMENTS_IPN_SECRET` from Secret Manager
  - [ ] Method: `get_nowpayments_ipn_secret()`
  - [ ] Return secret value or raise error if not available
- [ ] Update `initialize_config()` to include IPN secret
  - [ ] Add `'nowpayments_ipn_secret'` to config dict

### 2.6 GCWebhook1 - Main Endpoint Enhancement
- [ ] Open `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`
- [ ] Locate `@app.route("/", methods=["GET"])` endpoint
- [ ] After decoding token and writing to database:
  - [ ] Add lookup for payment_id: `subscription_record = db_manager.get_subscription_record(user_id, closed_channel_id)`
  - [ ] Extract NowPayments fields from record (if available):
    - [ ] `nowpayments_payment_id = subscription_record.get('nowpayments_payment_id')`
    - [ ] `nowpayments_pay_address = subscription_record.get('nowpayments_pay_address')`
    - [ ] `nowpayments_outcome_amount = subscription_record.get('nowpayments_outcome_amount')`
  - [ ] Add logging: "Found payment_id" or "payment_id not yet available"
- [ ] Update GCAccumulator enqueue call to include payment_id fields:
  - [ ] Add parameters: `nowpayments_payment_id`, `nowpayments_pay_address`, `nowpayments_outcome_amount`

### 2.7 GCWebhook1 - Deployment
- [ ] Update `requirements.txt` if needed (hmac/hashlib are standard library)
- [ ] Build Docker image: `cd OCTOBER/10-26/GCWebhook1-10-26 && docker build -t gcwebhook1-10-26 .`
- [ ] Test locally with Docker
- [ ] Deploy to Google Cloud Run:
  ```bash
  gcloud run deploy gcwebhook1-10-26 \
    --source . \
    --region us-central1 \
    --allow-unauthenticated
  ```
- [ ] Verify deployment: `curl https://gcwebhook1-10-26-.../health`
- [ ] Test IPN endpoint with mock request
- [ ] Monitor logs for errors

### 2.8 TelePay Bot - IPN Callback URL Configuration
- [ ] Open `/OCTOBER/10-26/TelePay10-26/start_np_gateway.py`
- [ ] Locate `create_payment_invoice()` method
- [ ] Add ipn_callback_url to invoice payload:
  - [ ] Fetch from environment: `ipn_callback_url = os.getenv('NOWPAYMENTS_IPN_CALLBACK_URL')`
  - [ ] Add to payload: `"ipn_callback_url": ipn_callback_url`
  - [ ] Add logging: "IPN will be sent to: {ipn_callback_url}"
  - [ ] Add warning if not configured
- [ ] Add `NOWPAYMENTS_IPN_CALLBACK_URL` to bot environment variables
- [ ] Restart bot
- [ ] Test invoice creation (verify ipn_callback_url in invoice)

---

## Phase 3: Token Enhancement (Week 2, Days 1-3)

### 3.1 Token Manager - Encryption Enhancement
- [ ] Open `/OCTOBER/10-26/GCWebhook1-10-26/token_manager.py`
- [ ] Locate `encrypt_token_for_gcwebhook2()` method
- [ ] Add optional parameters:
  - [ ] `nowpayments_payment_id: str = None`
  - [ ] `nowpayments_pay_address: str = None`
  - [ ] `nowpayments_outcome_amount: str = None`
- [ ] After existing field packing, add NowPayments fields:
  - [ ] If `nowpayments_payment_id` exists:
    - [ ] Encode to bytes: `payment_id_bytes = nowpayments_payment_id.encode('utf-8')`
    - [ ] Pack length: `packed_data.append(len(payment_id_bytes))`
    - [ ] Pack data: `packed_data.extend(payment_id_bytes)`
  - [ ] Else: `packed_data.append(0)` (0-length indicates absent)
  - [ ] Repeat for `nowpayments_pay_address`
  - [ ] Repeat for `nowpayments_outcome_amount`
- [ ] Update HMAC signature calculation (includes new fields)
- [ ] Add logging: "Encrypted token with payment_id: {bool(nowpayments_payment_id)}"

### 3.2 Token Manager - Decryption Enhancement
- [ ] Open `/OCTOBER/10-26/GCWebhook1-10-26/token_manager.py`
- [ ] Locate `decode_and_verify_token()` method
- [ ] After parsing existing fields, add NowPayments field parsing:
  - [ ] Check if more data available: `if offset + 1 <= len(raw):`
  - [ ] Read payment_id length: `payment_id_len = struct.unpack(">B", raw[offset:offset+1])[0]`
  - [ ] If `payment_id_len > 0`:
    - [ ] Decode: `nowpayments_payment_id = raw[offset:offset+payment_id_len].decode('utf-8')`
    - [ ] Increment offset
  - [ ] Else: `nowpayments_payment_id = None`
  - [ ] Repeat for `nowpayments_pay_address`
  - [ ] Repeat for `nowpayments_outcome_amount`
- [ ] Handle backward compatibility:
  - [ ] If no more data after existing fields, return `None` for NowPayments fields
  - [ ] Old tokens should decode without errors
- [ ] Update return tuple to include 3 new fields:
  - [ ] `(user_id, closed_channel_id, ..., nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount)`

### 3.3 Token Manager - Testing
- [ ] Create unit test: `/OCTOBER/10-26/GCWebhook1-10-26/test_token_payment_id.py`
- [ ] Test encoding WITH payment_id:
  - [ ] Encrypt token with all 3 NowPayments fields
  - [ ] Decrypt token
  - [ ] Verify payment_id matches
  - [ ] Verify pay_address matches
  - [ ] Verify outcome_amount matches
- [ ] Test encoding WITHOUT payment_id (backward compatibility):
  - [ ] Encrypt token with no NowPayments fields
  - [ ] Decrypt token
  - [ ] Verify NowPayments fields are `None`
  - [ ] Verify existing fields still work
- [ ] Test decoding old tokens (pre-payment_id):
  - [ ] Use old token format (without NowPayments fields)
  - [ ] Decrypt token
  - [ ] Verify no errors
  - [ ] Verify NowPayments fields return `None`

### 3.4 Cloud Tasks Client - Payload Enhancement
- [ ] Open `/OCTOBER/10-26/GCWebhook1-10-26/cloudtasks_client.py`
- [ ] Locate `enqueue_gcaccumulator_payment()` method
- [ ] Add optional parameters:
  - [ ] `nowpayments_payment_id: str = None`
  - [ ] `nowpayments_pay_address: str = None`
  - [ ] `nowpayments_outcome_amount: str = None`
- [ ] Add to payload dict:
  - [ ] `"nowpayments_payment_id": nowpayments_payment_id`
  - [ ] `"nowpayments_pay_address": nowpayments_pay_address`
  - [ ] `"nowpayments_outcome_amount": nowpayments_outcome_amount`
- [ ] Add logging: "Enqueueing with payment_id: {bool(nowpayments_payment_id)}"

### 3.5 GCWebhook1 - Update Enqueue Calls
- [ ] Open `/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`
- [ ] Locate threshold payout routing (GCAccumulator enqueue)
- [ ] Update `cloudtasks_client.enqueue_gcaccumulator_payment()` call:
  - [ ] Add parameters from lookup (Section 2.6):
    - [ ] `nowpayments_payment_id=nowpayments_payment_id`
    - [ ] `nowpayments_pay_address=nowpayments_pay_address`
    - [ ] `nowpayments_outcome_amount=nowpayments_outcome_amount`

### 3.6 GCWebhook1 - Deployment (Token Changes)
- [ ] Build Docker image with updated token_manager
- [ ] Test token encoding/decoding locally
- [ ] Deploy to Google Cloud Run
- [ ] Monitor logs for token-related errors
- [ ] Test backward compatibility with old tokens

---

## Phase 4: GCAccumulator Integration (Week 2, Days 4-5)

### 4.1 GCAccumulator - Main Endpoint Enhancement
- [ ] Open `/OCTOBER/10-26/GCAccumulator-10-26/acc10-26.py`
- [ ] Locate `@app.route("/", methods=["POST"])` endpoint
- [ ] After extracting existing fields from `request_data`:
  - [ ] Extract NowPayments fields:
    - [ ] `nowpayments_payment_id = request_data.get('nowpayments_payment_id')`
    - [ ] `nowpayments_pay_address = request_data.get('nowpayments_pay_address')`
    - [ ] `nowpayments_outcome_amount = request_data.get('nowpayments_outcome_amount')`
  - [ ] Add logging:
    - [ ] If payment_id exists: "NowPayments Payment ID: {payment_id}"
    - [ ] If not: "payment_id not available (may arrive via IPN later)"
- [ ] Update `db_manager.insert_payout_accumulation_pending()` call:
  - [ ] Add parameters: `nowpayments_payment_id`, `nowpayments_pay_address`, `nowpayments_outcome_amount`

### 4.2 GCAccumulator - Database Manager Enhancement
- [ ] Open `/OCTOBER/10-26/GCAccumulator-10-26/database_manager.py`
- [ ] Locate `insert_payout_accumulation_pending()` method
- [ ] Add optional parameters:
  - [ ] `nowpayments_payment_id: str = None`
  - [ ] `nowpayments_pay_address: str = None`
  - [ ] `nowpayments_outcome_amount: str = None`
- [ ] Update SQL INSERT statement:
  - [ ] Add columns: `nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount`
  - [ ] Add values: `%s, %s, %s`
  - [ ] Add to parameter tuple
- [ ] Add logging:
  - [ ] After insert: "Inserted accumulation record ID: {accumulation_id}"
  - [ ] If payment_id: "Linked to payment_id: {payment_id}"

### 4.3 GCAccumulator - Testing
- [ ] Create test payload with payment_id
- [ ] Send test request to GCAccumulator endpoint
- [ ] Verify database insertion
- [ ] Query `payout_accumulation` table:
  ```sql
  SELECT nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount
  FROM payout_accumulation
  ORDER BY id DESC LIMIT 1;
  ```
- [ ] Verify payment_id stored correctly

### 4.4 GCAccumulator - Deployment
- [ ] Build Docker image: `cd OCTOBER/10-26/GCAccumulator-10-26 && docker build -t gcaccumulator-10-26 .`
- [ ] Test locally with Docker
- [ ] Deploy to Google Cloud Run:
  ```bash
  gcloud run deploy gcaccumulator-10-26 \
    --source . \
    --region us-central1 \
    --allow-unauthenticated
  ```
- [ ] Verify deployment: `curl https://gcaccumulator-10-26-.../health`
- [ ] Monitor logs for errors

---

## Phase 5: Production Validation (Week 3)

### 5.1 End-to-End Testing
- [ ] Create test payment through TelePay bot
  - [ ] Verify invoice creation includes ipn_callback_url
  - [ ] Log invoice_id and order_id
- [ ] Complete test payment (use real crypto or testnet)
- [ ] Monitor IPN callback:
  - [ ] Check GCWebhook1 logs for IPN received
  - [ ] Verify signature verification success
  - [ ] Verify database update success
  - [ ] Check payment_id stored in `private_channel_users_database`
- [ ] Monitor success_url redirect:
  - [ ] Check GCWebhook1 main endpoint logs
  - [ ] Verify payment_id lookup from database
  - [ ] Verify payment_id included in Cloud Tasks payload
- [ ] Monitor GCAccumulator:
  - [ ] Check logs for payment_id received
  - [ ] Verify payment_id stored in `payout_accumulation`
- [ ] Verify complete flow with logging

### 5.2 Production Monitoring Setup
- [ ] Create monitoring queries in Google Cloud Logging:
  - [ ] IPN callbacks received (last 24h)
  - [ ] IPN signature failures (alert if >0)
  - [ ] payment_id capture rate (alert if <95%)
  - [ ] IPN processing latency (alert if >500ms)
- [ ] Create validation script: `/tools/validate_payment_id_capture.sh`
  - [ ] Query payment_id capture rate
  - [ ] Query accumulation records with payment_id
  - [ ] Test NowPayments API with captured payment_id
  - [ ] Generate summary report
- [ ] Set up Cloud Monitoring alerts:
  - [ ] Alert: IPN signature failures > 10 in 5 minutes (CRITICAL)
  - [ ] Alert: payment_id capture rate < 90% over 1 hour (WARNING)
  - [ ] Alert: IPN processing latency > 5 seconds (WARNING)

### 5.3 Data Validation
- [ ] Run validation queries on production database:
  - [ ] Check payment_id capture rate (last 24 hours)
    ```sql
    SELECT
        COUNT(*) as total_payments,
        COUNT(nowpayments_payment_id) as with_payment_id,
        ROUND(100.0 * COUNT(nowpayments_payment_id) / COUNT(*), 2) as capture_rate
    FROM private_channel_users_database
    WHERE subscription_time > NOW() - INTERVAL '24 hours';
    ```
  - [ ] Target: >95% capture rate
- [ ] Check accumulation records:
  ```sql
  SELECT
      COUNT(*) as total_accumulations,
      COUNT(nowpayments_payment_id) as with_payment_id
  FROM payout_accumulation
  WHERE created_at > NOW() - INTERVAL '24 hours';
  ```
- [ ] Verify no NULL values where payment_id should exist

### 5.4 NowPayments API Integration Testing
- [ ] Get payment_id from recent payment
- [ ] Query NowPayments API:
  ```bash
  curl -X GET "https://api.nowpayments.io/v1/payment/{PAYMENT_ID}" \
    -H "x-api-key: $NOWPAYMENTS_API_KEY"
  ```
- [ ] Verify API returns payment details
- [ ] Compare API response with stored data
- [ ] Document any discrepancies

### 5.5 Performance Testing
- [ ] Test IPN endpoint under load (simulate multiple concurrent callbacks)
- [ ] Measure IPN processing latency
  - [ ] Target: <500ms average
  - [ ] Maximum acceptable: <2 seconds
- [ ] Verify database performance with new indexes
- [ ] Check Cloud Run instance scaling (no cold starts causing delays)

### 5.6 Edge Case Testing
- [ ] Test race condition: IPN arrives BEFORE success_url
  - [ ] Verify payment_id stored via IPN
  - [ ] Verify success_url lookup finds payment_id
  - [ ] Verify no duplicate entries
- [ ] Test race condition: success_url arrives BEFORE IPN
  - [ ] Verify flow continues without payment_id
  - [ ] Verify IPN updates record retroactively
  - [ ] Verify eventual consistency
- [ ] Test duplicate IPN callbacks (idempotency)
  - [ ] Send same IPN twice
  - [ ] Verify second call returns 200 OK (no error)
  - [ ] Verify no duplicate database updates
- [ ] Test invalid IPN signature
  - [ ] Send IPN with wrong signature
  - [ ] Verify rejection with 401 Unauthorized
  - [ ] Verify no database update
- [ ] Test missing required fields in IPN
  - [ ] Send IPN without payment_id
  - [ ] Verify rejection with 400 Bad Request
- [ ] Test old tokens (pre-payment_id format)
  - [ ] Use old token without payment_id fields
  - [ ] Verify decoding works
  - [ ] Verify NowPayments fields return None
  - [ ] Verify flow continues normally

### 5.7 Backward Compatibility Verification
- [ ] Verify existing instant payout flow works
- [ ] Verify existing threshold payout flow works
- [ ] Verify services handle missing payment_id gracefully
- [ ] Verify no errors in logs for old payments

### 5.8 Documentation Updates
- [ ] Update `PROGRESS.md`:
  - [ ] Add session entry for Phase 1 completion
  - [ ] Add session entry for Phase 2 completion
  - [ ] Add session entry for Phase 3 completion
  - [ ] Add session entry for Phase 4 completion
  - [ ] Add session entry for Phase 5 completion
- [ ] Update `DECISIONS.md`:
  - [ ] Document IPN callback architecture decision
  - [ ] Document token format extension decision
  - [ ] Document backward compatibility approach
- [ ] Update `BUGS.md` (if any issues found during implementation)
- [ ] Create operational runbook: `/OCTOBER/10-26/NOWPAYMENTS_PAYMENT_ID_RUNBOOK.md`
  - [ ] How to monitor payment_id capture rate
  - [ ] How to troubleshoot IPN failures
  - [ ] How to query NowPayments API
  - [ ] How to resolve missing payment_id issues

---

## Rollback Procedures

### Rollback Checklist (if issues arise)

#### Rollback GCWebhook1
- [ ] List available revisions:
  ```bash
  gcloud run revisions list --service=gcwebhook1-10-26 --region=us-central1
  ```
- [ ] Rollback to previous revision:
  ```bash
  gcloud run services update-traffic gcwebhook1-10-26 \
    --to-revisions [PREVIOUS_REVISION]=100 \
    --region=us-central1
  ```
- [ ] Verify rollback: `curl https://gcwebhook1-10-26-.../health`

#### Rollback GCAccumulator
- [ ] List available revisions:
  ```bash
  gcloud run revisions list --service=gcaccumulator-10-26 --region=us-central1
  ```
- [ ] Rollback to previous revision:
  ```bash
  gcloud run services update-traffic gcaccumulator-10-26 \
    --to-revisions [PREVIOUS_REVISION]=100 \
    --region=us-central1
  ```
- [ ] Verify rollback: `curl https://gcaccumulator-10-26-.../health`

#### Database Rollback (if needed)
- [ ] **NOTE**: Database schema changes are additive (new columns are NULL-allowed)
- [ ] **SAFE**: Old code continues to work with new schema (ignores new columns)
- [ ] **ONLY IF CRITICAL**: Drop columns (not recommended):
  ```sql
  -- ONLY if absolutely necessary
  ALTER TABLE private_channel_users_database
  DROP COLUMN nowpayments_payment_id,
  DROP COLUMN nowpayments_invoice_id,
  -- ... (drop all added columns)
  ```

---

## Success Validation Checklist

### Technical Success Criteria
- [ ] **Database Migration**: All columns and indexes created successfully
- [ ] **IPN Endpoint**: Deployed and accessible at `/ipn`
- [ ] **Signature Verification**: 100% IPN signature verification success rate
- [ ] **Database Updates**: No failed database updates from IPN
- [ ] **Idempotency**: Duplicate IPN callbacks handled correctly
- [ ] **Token Enhancement**: Tokens include payment_id when available
- [ ] **Backward Compatibility**: Old tokens still decode successfully
- [ ] **GCAccumulator**: payment_id stored in payout_accumulation
- [ ] **End-to-End Flow**: Complete flow working from invoice creation to accumulation

### Performance Success Criteria
- [ ] **Payment ID Capture Rate**: >95% (target: 100%)
- [ ] **IPN Processing Latency**: <500ms average (max: <2 seconds)
- [ ] **Zero Errors**: No signature verification failures
- [ ] **Zero Downtime**: All deployments completed without service interruption

### Business Success Criteria
- [ ] **NowPayments API Queries**: Can query payment details with payment_id
- [ ] **Fee Discrepancy Resolution**: Can calculate actual fees from NowPayments data
- [ ] **Blockchain Matching**: Can match payments to blockchain transactions via pay_address
- [ ] **Customer Support**: Can lookup payments quickly by payment_id

---

## Next Steps After Completion

### Integration with Fee Discrepancy Solution
- [ ] Review `FEE_DISCREPANCY_ARCHITECTURAL_SOLUTION.md`
- [ ] Use payment_id to query NowPayments API for actual amounts
- [ ] Implement fee discrepancy calculation logic
- [ ] Implement two-phase confirmation workflow

### Customer Support Tools
- [ ] Build admin dashboard to query by payment_id
- [ ] Create payment lookup tool for support team
- [ ] Document support procedures

### Financial Reporting
- [ ] Calculate actual fees paid to NowPayments
- [ ] Generate revenue reports with accurate amounts
- [ ] Build analytics dashboard

---

## Notes

- **Backward Compatibility**: Critical requirement - old code must continue working
- **Zero Downtime**: All deployments must be zero-downtime (Cloud Run handles this)
- **Idempotency**: IPN endpoint must handle duplicate callbacks gracefully
- **Race Conditions**: IPN can arrive before or after success_url - both scenarios must work
- **Optional Fields**: payment_id is optional in all services (may not be available immediately)
- **Database Performance**: New indexes ensure fast lookups by payment_id and order_id

---

**Document Owner:** Claude
**Last Updated:** 2025-11-02
**Version:** 1.0
**Status:** READY FOR IMPLEMENTATION
