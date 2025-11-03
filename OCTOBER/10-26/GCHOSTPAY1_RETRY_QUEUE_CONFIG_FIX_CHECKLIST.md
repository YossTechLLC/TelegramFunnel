# GCHostPay1 Retry Queue Config Fix - Implementation Checklist

**Started**: 2025-11-03
**Issue**: Config manager missing GCHOSTPAY1_URL and GCHOSTPAY1_RESPONSE_QUEUE
**Priority**: P1 - CRITICAL
**Root Cause**: Session 52 Phase 2 implementation forgot to update config_manager.py

---

## Phase 1: Immediate Fix (Reuse Existing Response Queue)

### ✅ Task 1: Update config_manager.py

**Status**: ⏳ PENDING

#### Checklist:
- [ ] Add GCHOSTPAY1_URL fetch after line 98
- [ ] Add GCHOSTPAY1_RESPONSE_QUEUE fetch
- [ ] Add both to config dictionary (lines 144-167)
- [ ] Add both to status logging (lines 170-185)
- [ ] Verify changes using Read tool

**Expected Changes**:
```python
# After line 98 (after GCHostPay3 config)
gchostpay1_url = self.fetch_secret(
    "GCHOSTPAY1_URL",
    "GCHostPay1 service URL (for self-callbacks)"
)

gchostpay1_response_queue = self.fetch_secret(
    "GCHOSTPAY1_RESPONSE_QUEUE",
    "GCHostPay1 response queue name (for retry callbacks)"
)

# In config dictionary (line 159 area)
'gchostpay1_url': gchostpay1_url,
'gchostpay1_response_queue': gchostpay1_response_queue,

# In status logging (line 182 area)
print(f"   GCHostPay1 URL: {'✅' if config['gchostpay1_url'] else '❌'}")
print(f"   GCHostPay1 Response Queue: {'✅' if config['gchostpay1_response_queue'] else '❌'}")
```

---

### ✅ Task 2: Build Docker Image

**Status**: ⏳ PENDING

#### Checklist:
- [ ] Navigate to GCHostPay1-10-26 directory
- [ ] Run `gcloud builds submit` command
- [ ] Verify build success (check logs for "SUCCESS")
- [ ] Note build ID and image digest

**Command**:
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay1-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gchostpay1-10-26:latest
```

**Expected**: Build ID and "SUCCESS" status

---

### ✅ Task 3: Deploy to Cloud Run with Secrets

**Status**: ⏳ PENDING

#### Checklist:
- [ ] Deploy with GCHOSTPAY1_URL secret injection
- [ ] Deploy with GCHOSTPAY1_RESPONSE_QUEUE secret injection
- [ ] Verify deployment success
- [ ] Note new revision number
- [ ] Verify revision is serving 100% traffic
- [ ] Check service URL is responding

**Command**:
```bash
gcloud run deploy gchostpay1-10-26 \
  --image gcr.io/telepay-459221/gchostpay1-10-26:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets=TPS_HOSTPAY_SIGNING_KEY=TPS_HOSTPAY_SIGNING_KEY:latest,\
SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,\
GCHOSTPAY2_QUEUE=GCHOSTPAY2_QUEUE:latest,\
GCHOSTPAY2_URL=GCHOSTPAY2_URL:latest,\
GCHOSTPAY3_QUEUE=GCHOSTPAY3_QUEUE:latest,\
GCHOSTPAY3_URL=GCHOSTPAY3_URL:latest,\
GCHOSTPAY1_URL=GCHOSTPAY1_URL:latest,\
GCHOSTPAY1_RESPONSE_QUEUE=GCHOSTPAY1_RESPONSE_QUEUE:latest,\
CHANGENOW_API_KEY=CHANGENOW_API_KEY:latest,\
MICROBATCH_RESPONSE_QUEUE=MICROBATCH_RESPONSE_QUEUE:latest,\
MICROBATCH_URL=MICROBATCH_URL:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest \
  --add-cloudsql-instances telepay-459221:us-central1:telepaypsql
```

**Expected**:
- New revision: `gchostpay1-10-26-00017-xxx`
- Service URL: `https://gchostpay1-10-26-291176869049.us-central1.run.app`
- Traffic: 100%

---

### ✅ Task 4: Test Retry Logic

**Status**: ⏳ PENDING

#### 4.1: Monitor Service Logs
- [ ] Access https://gchostpay1-10-26-291176869049.us-central1.run.app logs
- [ ] Check for config loading success:
  ```
  ✅ [CONFIG] Successfully loaded GCHostPay1 service URL
  ✅ [CONFIG] Successfully loaded GCHostPay1 response queue name
  ```
- [ ] Verify no "config missing" errors

#### 4.2: Trigger Batch Conversion (If Available)
- [ ] Initiate new batch conversion payment
- [ ] Monitor GCHostPay1 logs for:
  ```
  🔍 [ENDPOINT_3] Querying ChangeNow for actual USDT received...
  ⏳ [ENDPOINT_3] ChangeNow swap not finished yet: waiting
  🔄 [RETRY_ENQUEUE] Scheduling retry #1 in 300s
  ✅ [RETRY_ENQUEUE] Retry task enqueued (will execute in 300s)
  ```
- [ ] NO MORE "❌ [RETRY_ENQUEUE] GCHostPay1 response queue config missing"

#### 4.3: Wait for Retry Execution (5 minutes)
- [ ] Monitor Cloud Tasks queue: `gchostpay1-response-queue`
- [ ] Verify retry task appears in queue
- [ ] Wait 5 minutes for execution
- [ ] Monitor GCHostPay1 logs for:
  ```
  🔍 [ENDPOINT_4] Retry callback check triggered
  🔍 [ENDPOINT_4] Re-querying ChangeNow API...
  ✅ [ENDPOINT_4] ChangeNow swap finished: amountTo = X.XX
  ✅ [ENDPOINT_4] Sending callback to GCMicroBatchProcessor
  ```

---

### ✅ Task 5: Verify Other Services Don't Have Same Issue

**Status**: ⏳ PENDING

#### Check GCHostPay2-10-26
- [ ] Read config_manager.py
- [ ] Verify all config values used in main code are loaded
- [ ] Note any missing config

#### Check GCHostPay3-10-26
- [ ] Read config_manager.py
- [ ] Verify GCHOSTPAY3_RETRY_QUEUE is properly loaded
- [ ] Verify all config values used in main code are loaded

#### Check GCAccumulator-10-26
- [ ] Read config_manager.py
- [ ] Verify completeness

#### Check GCBatchProcessor-10-26
- [ ] Read config_manager.py
- [ ] Verify completeness

#### Check GCMicroBatchProcessor-10-26
- [ ] Read config_manager.py
- [ ] Verify completeness

**Method**: For each service:
1. Read main Python file to see what config values are accessed
2. Read config_manager.py to see what's loaded
3. Compare and note any missing values

---

### ✅ Task 6: Update Documentation

**Status**: ⏳ PENDING

#### 6.1: Update PROGRESS.md
- [ ] Add Session 53 entry to TOP of PROGRESS.md
- [ ] Include root cause summary (config loading missing)
- [ ] List all changes made (config_manager.py lines)
- [ ] Note new revision number
- [ ] Mark Phase 1 complete

#### 6.2: Update BUGS.md
- [ ] Add Session 53 bug entry to TOP of BUGS.md
- [ ] Document complete timeline of the bug
- [ ] List fix details and files changed
- [ ] Note that Phase 2 (dedicated retry queue) is optional enhancement

#### 6.3: Update DECISIONS.md
- [ ] Add Session 53 decision to TOP of DECISIONS.md
- [ ] Document why we reused response queue for Phase 1 (speed)
- [ ] Note that dedicated retry queue is recommended for Phase 2

---

## Phase 2: Clean Architecture (Dedicated Retry Queue) - OPTIONAL

**Status**: ⏳ PENDING
**Priority**: P3 - ENHANCEMENT (Phase 1 fixes critical issue)

### ✅ Task 7: Create Retry Queue Infrastructure

#### 7.1: Create Cloud Tasks Queue
- [ ] Create `gchostpay1-retry-queue`
- [ ] Set location: us-central1
- [ ] Set max retry: 3
- [ ] Set retry interval: 300s

**Command**:
```bash
gcloud tasks queues create gchostpay1-retry-queue \
  --location=us-central1 \
  --max-retry=3 \
  --min-backoff=300s
```

#### 7.2: Create Secret Manager Secret
- [ ] Create GCHOSTPAY1_RETRY_QUEUE secret
- [ ] Set value to `gchostpay1-retry-queue`

**Command**:
```bash
echo -n "gchostpay1-retry-queue" | gcloud secrets create GCHOSTPAY1_RETRY_QUEUE \
  --data-file=- \
  --replication-policy=automatic
```

---

### ✅ Task 8: Update config_manager.py for Retry Queue

**Status**: ⏳ PENDING

#### Checklist:
- [ ] Add GCHOSTPAY1_RETRY_QUEUE fetch
- [ ] Add to config dictionary
- [ ] Add to status logging
- [ ] Verify changes

---

### ✅ Task 9: Update Helper Function to Use Retry Queue

**Status**: ⏳ PENDING

#### Checklist:
- [ ] Update `_enqueue_delayed_callback_check()` line 220-225
- [ ] Change to use `gchostpay1_retry_queue` instead of `gchostpay1_response_queue`
- [ ] Update comments/docstrings
- [ ] Verify changes

**Expected Change**:
```python
# Get queue configuration for RETRY (not response)
gchostpay1_retry_queue = config.get('gchostpay1_retry_queue')
gchostpay1_url = config.get('gchostpay1_url')

if not gchostpay1_retry_queue or not gchostpay1_url:
    print(f"❌ [RETRY_ENQUEUE] GCHostPay1 retry queue config missing")
    return False
```

---

### ✅ Task 10: Build and Deploy Phase 2

**Status**: ⏳ PENDING

#### Checklist:
- [ ] Build Docker image
- [ ] Deploy with GCHOSTPAY1_RETRY_QUEUE secret
- [ ] Verify deployment
- [ ] Test retry tasks go to dedicated queue

---

### ✅ Task 11: Update Documentation for Phase 2

**Status**: ⏳ PENDING

#### Checklist:
- [ ] Update PROGRESS.md with Phase 2 completion
- [ ] Update DECISIONS.md with dedicated queue decision
- [ ] Update checklist status

---

## Summary

**Phase 1 Status**: ⏳ READY TO START
**Phase 2 Status**: ⏳ OPTIONAL ENHANCEMENT
**Current Stage**: About to fix critical config loading bug
**Blockers**: None

**What's Next**:
1. Execute Task 1: Update config_manager.py
2. Execute Task 2: Build Docker image
3. Execute Task 3: Deploy with secrets
4. Execute Task 4: Test retry logic
5. Execute Task 5: Verify other services
6. Execute Task 6: Update documentation
7. (Optional) Execute Phase 2 for clean architecture
