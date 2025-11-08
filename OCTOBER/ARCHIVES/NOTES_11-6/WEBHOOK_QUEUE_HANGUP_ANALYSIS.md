# Webhook and Cloud Tasks Queue Hangup Analysis
**Date**: 2025-11-03
**Analysis Period**: Past 24 hours (2025-11-02 to 2025-11-03)
**Services Analyzed**: GCWebhook1, GCWebhook2, NP-Webhook, Cloud Tasks Queues

---

## 🎯 Executive Summary

The payment processing pipeline has been experiencing **3 critical failure points** that are causing Cloud Tasks to retry repeatedly, creating a hangup scenario where payments cannot complete processing:

1. **GCWebhook1-10-26**: Type conversion error (FIXED in latest revision)
2. **GCWebhook2-10-26**: Missing database method causing 500 errors (ACTIVE)
3. **np-webhook-10-26**: Multiple configuration and validation issues (ACTIVE)

---

## 🔴 CRITICAL ISSUE #1: GCWebhook1 Type Conversion Error

### Error Pattern
```python
TypeError: unsupported operand type(s) for -: 'float' and 'str'
Location: /app/tph1-10-26.py:437 (in deployed revision 00017-cpz)
Line: "difference": outcome_amount_usd - subscription_price
```

### Root Cause
The `subscription_price` field was being received as a **string** from the JSON payload but was not being converted to a float before arithmetic operations.

### Impact Timeline
- **First Error**: 2025-11-02 12:49:49 UTC
- **Last Error**: 2025-11-02 16:23:49 UTC
- **Affected Revision**: gcwebhook1-10-26-00017-cpz
- **Error Count**: 20+ repeated failures (causing task retries)
- **HTTP Status**: 500 (Internal Server Error)

### Resolution Status
✅ **RESOLVED** - Fixed in revision `gcwebhook1-10-26-00021-2pp` (deployed 2025-11-02 20:23:05 UTC)

The current code properly converts the type:
```python
"difference": outcome_amount_usd - float(subscription_price)
```

### Queue Hangup Effect
- Cloud Tasks queue `gcwebhook1-queue` was retrying failed tasks repeatedly
- Queue configuration: **Unlimited retries** (`maxAttempts: -1`) with 24-hour retry duration
- Tasks were stuck in retry loop for ~4 hours before fix deployment
- No tasks purged - queue shows last purge at 2025-11-02 16:24:36 UTC

---

## 🔴 CRITICAL ISSUE #2: GCWebhook2 Missing Database Method

### Error Pattern
```python
AttributeError: 'DatabaseManager' object has no attribute 'execute_query'
Location: /app/tph2-10-26.py:137 (in send_telegram_invite)
Revision: gcwebhook2-10-26-00016-p7q and gcwebhook2-10-26-00017-hfq
```

### Root Cause
The deployed version of `tph2-10-26.py` is calling `db_manager.execute_query()` which **does not exist** in the deployed `database_manager.py`. This indicates:
1. Code was updated to use a new API that wasn't deployed
2. OR the database_manager.py is an older version

### Impact Timeline
- **Errors in Revision 00016**: 2025-11-02 17:49:32 - 17:50:52 UTC
- **Errors in Revision 00017**: 2025-11-02 18:12:51 - 20:48:51 UTC (ONGOING)
- **Error Count**: 20+ failures across 2+ hours
- **HTTP Status**: 500 (Internal Server Error)
- **User Agent**: Google-Cloud-Tasks (automated retries)

### Current Status
❌ **ACTIVE ISSUE** - Still failing in latest revision (00017-hfq)

### Queue Hangup Effect
- Tasks from `gcwebhook-telegram-invite-queue` are **continuously failing**
- Telegram invitations are **not being sent** to users
- Tasks retry every ~60 seconds based on 500 status
- Users complete payment but **never receive channel access**

---

## 🔴 CRITICAL ISSUE #3: NP-Webhook Multiple Configuration Issues

### Issue 3A: Missing Secret - NOWPAYMENTS_IPN_SECRET_KEY

**Error Pattern**:
```
SecretsAccessCheckFailed
Secret projects/291176869049/secrets/NOWPAYMENTS_IPN_SECRET_KEY/versions/latest was not found
Revision: np-webhook-10-26-00005-68w
Timestamp: 2025-11-02 17:17:32 UTC
```

**Root Cause**: The environment variable name mismatch - service expects `NOWPAYMENTS_IPN_SECRET_KEY` but the secret may be named differently in Secret Manager.

**Impact**: Revision 00005-68w failed to deploy, service rolled back to 00004-q9b

---

### Issue 3B: Queue Name Validation Error

**Error Pattern**:
```python
google.api_core.exceptions.InvalidArgument: 400 Queue ID "gcwebhook1-queue
Location: /app/cloudtasks_client.py:104
Timestamp: 2025-11-02 14:30:02 - 14:31:05 UTC
```

**Root Cause**: Queue name contains a **trailing newline character** (`\n`), causing Cloud Tasks API to reject the queue ID. This error message is truncated mid-string, suggesting the actual value is:
```
"gcwebhook1-queue\n"
```

**Source**: Secret Manager value for `GCWEBHOOK1_QUEUE` has trailing whitespace

**Impact**:
- Cannot enqueue validated payments to GCWebhook1
- Payments stuck at np-webhook stage
- Database updated but no downstream processing

---

### Issue 3C: Queue Does Not Exist (404)

**Error Pattern**:
```python
google.api_core.exceptions.NotFound: 404 Queue does not exist.
If you just created the queue, wait at least a minute for the queue to initialize.
Timestamps: 2025-11-02 15:26:16 - 15:28:14 UTC
```

**Root Cause**: Attempting to enqueue to a queue that either:
1. Doesn't exist yet (recently created)
2. Has incorrect name due to configuration error
3. Was deleted and recreated

**Impact**: Temporary - appears to have resolved after queue initialization

---

### Issue 3D: NOWPayments IPN Signature Validation Failure

**Error Pattern**:
```
HTTP 403 Forbidden
User-Agent: NOWPayments v1.0
Remote IP: 51.75.77.69
Timestamps: 2025-11-02 17:33:44, 17:35:55 UTC
```

**Root Cause**: IPN signature validation failing - either:
1. Incorrect IPN secret key
2. Signature calculation mismatch
3. Request body modification in transit

**Impact**:
- Legitimate payment webhooks from NOWPayments are being **rejected**
- Payments cannot enter the processing pipeline
- **CRITICAL**: Users pay but system doesn't know about it

---

### Issue 3E: Database Connection Management Error

**Error Pattern**:
```python
pg8000.exceptions.InterfaceError: connection is closed
Location: /app/app.py:688 (in handle_ipn conn.close())
Timestamps: 2025-11-02 14:30:02, 14:31:05 UTC
```

**Root Cause**: Attempting to close a database connection that's already closed - defensive error handling issue

**Impact**: Non-critical but indicates sloppy connection management

---

## 📊 Cloud Tasks Queue Status

All queues are currently in **RUNNING** state:

| Queue Name | State | Purpose |
|------------|-------|---------|
| `gcwebhook1-queue` | RUNNING | Process validated payments |
| `gcwebhook-telegram-invite-queue` | RUNNING | Send Telegram invites |
| `accumulator-payment-queue` | RUNNING | Accumulate threshold payments |
| `gcsplit1-batch-queue` | RUNNING | Instant payment splitting |
| `gchostpay1-batch-queue` | RUNNING | Batch crypto conversions |

**Queue Configuration - gcwebhook1-queue**:
```json
{
  "maxAttempts": -1,           // ⚠️ UNLIMITED RETRIES
  "maxBackoff": "300s",         // 5 minutes
  "maxRetryDuration": "86400s", // 24 hours
  "minBackoff": "10s"
}
```

### Queue Hangup Mechanism

When a service returns HTTP 500:
1. Cloud Tasks marks the task as failed
2. Task is scheduled for retry with exponential backoff (10s → 20s → 40s... up to 300s)
3. Retries continue for **24 hours** because `maxAttempts: -1` (unlimited)
4. Failed tasks accumulate in the queue
5. New tasks for the same payment create duplicates
6. Queue becomes backlogged with permanently failing tasks

**Current Backlog**: Unknown - need to query task count per queue

---

## 🔧 Required Actions (Priority Order)

### IMMEDIATE (P0) - User Impact

1. **Fix GCWebhook2 Database Method Error**
   - Deploy correct version of `database_manager.py` with `execute_query()` method
   - OR update `tph2-10-26.py` to use the correct database method calls
   - **Impact**: Users aren't receiving Telegram invites after payment

2. **Fix NP-Webhook IPN Secret**
   - Verify Secret Manager secret name: `NOWPAYMENTS_IPN_SECRET_KEY` vs actual name
   - Update service configuration or create missing secret
   - **Impact**: Payment webhooks being rejected - users pay but system doesn't register it

3. **Clean Trailing Newlines from Secrets**
   - Strip whitespace from all queue/URL secrets in Secret Manager
   - Redeploy np-webhook and any other affected services
   - Specifically check: `GCWEBHOOK1_QUEUE`, `GCWEBHOOK1_URL`
   - **Impact**: Cannot route payments to downstream services

### HIGH PRIORITY (P1) - System Health

4. **Purge Failed Tasks from gcwebhook1-queue**
   ```bash
   gcloud tasks queues purge gcwebhook1-queue --location=us-central1
   ```
   - Clear backlog of failed tasks from the 4-hour failure window
   - Prevents duplicate processing when users retry

5. **Verify Latest Revisions Deployed**
   - Ensure all services are using latest revision with fixes
   - Check traffic routing isn't split between old/new revisions

### MEDIUM PRIORITY (P2) - Operational Improvement

6. **Adjust Queue Retry Configuration**
   - Change `maxAttempts: -1` to reasonable limit (e.g., `maxAttempts: 10`)
   - Prevents infinite retry loops
   - Add dead-letter queue for permanently failed tasks

7. **Add Defensive Type Conversion**
   - Audit all services for string→float/int conversions from JSON
   - Add type validation at payload entry points
   - Use Pydantic models for request validation

8. **Implement Better Error Alerting**
   - Set up Cloud Monitoring alerts for:
     - Error rate > 10% in any service
     - Queue depth > 100 tasks
     - Task age > 10 minutes
   - Send to Slack/Email for immediate response

---

## 📈 Metrics & Timeline

### Error Volume by Service (Past 24h)

| Service | Error Count | Time Window | Status |
|---------|-------------|-------------|--------|
| GCWebhook1 | ~20 errors | 12:49 - 16:23 UTC | ✅ Fixed |
| GCWebhook2 | ~20 errors | 17:49 - 20:48 UTC | ❌ Active |
| NP-Webhook | ~15 errors | 14:30 - 17:35 UTC | ❌ Active |

### Deployment Timeline

```
12:30 UTC - np-webhook-10-26-00003 errors start (queue name issue)
14:30 UTC - np-webhook-10-26-00003 database connection errors
15:57 UTC - gcwebhook1-10-26-00017 deployed (has type error)
16:24 UTC - gcwebhook1-queue purged
17:17 UTC - np-webhook-10-26-00005 failed deployment (secret missing)
17:20 UTC - gcwebhook1-10-26-00019 deployed (still has error)
17:50 UTC - gcwebhook2-10-26-00016 execute_query errors start
18:05 UTC - gcwebhook1-10-26-00020 deployed
18:12 UTC - gcwebhook2-10-26-00017 deployed (still has error)
20:23 UTC - gcwebhook1-10-26-00021 deployed (✅ FIXES type error)
```

---

## 🎓 Lessons Learned

1. **Type Safety**: JSON payloads don't preserve types - always validate and convert
2. **API Contracts**: Database method changes must be deployed atomically across services
3. **Secret Management**: Trailing whitespace in secrets causes silent failures
4. **Queue Configuration**: Unlimited retries can create permanent backlog
5. **Deployment Coordination**: Services have dependencies - deploy in order
6. **Monitoring Gaps**: These errors went unnoticed for hours

---

## 🔍 Next Steps for Investigation

1. Check processed_payments table for stuck payments during error window
2. Query Cloud Tasks API for current queue depths
3. Verify which database_manager.py version is deployed to each service
4. Review all Secret Manager values for trailing whitespace
5. Check if any payments were double-processed due to retries

---

## 📝 Architecture Notes

### Payment Flow (When Working)
```
NOWPayments IPN
    ↓
np-webhook-10-26 (validate, fetch price, calculate USD)
    ↓
gcwebhook1-10-26 (route to accumulator/split)
    ↓
gcwebhook2-10-26 (send Telegram invite)
```

### Failure Points Identified
```
NOWPayments IPN → [403 Forbidden] ← Invalid signature
    ↓
np-webhook → [400 Invalid Queue ID] ← Trailing newline
    ↓
gcwebhook1 → [500 Type Error] ← String vs Float (FIXED)
    ↓
gcwebhook2 → [500 Missing Method] ← execute_query not found (ACTIVE)
```

---

**Analysis Completed**: 2025-11-03
**Analyzed By**: Claude Code
**Files Examined**:
- Cloud Run logs for gcwebhook1-10-26, gcwebhook2-10-26, np-webhook-10-26
- Cloud Tasks queue configurations
- Deployed code: tph1-10-26.py, tph2-10-26.py
- Revision history and deployment timestamps
