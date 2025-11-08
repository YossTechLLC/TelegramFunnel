# GCMicroBatchProcessor and GCAccumulator Synchronization Issue

**Date**: 2025-11-03
**Analysis Period**: 11:05 AM EST - 11:40 AM EST (16:05 UTC - 16:40 UTC)
**Services Analyzed**: GCMicroBatchProcessor, GCBatchProcessor, GCAccumulator
**Status**: 🔴 **CRITICAL ISSUE IDENTIFIED**

---

## 🎯 Executive Summary

**GCMicroBatchProcessor has stopped executing** while other services continue to function normally. The last successful threshold check occurred at **11:05 AM EST (16:05 UTC)**, but the service should be checking every **5 minutes** via Cloud Scheduler. Meanwhile, GCBatchProcessor continues to run every 5 minutes and is correctly seeing updated accumulation totals.

**Impact**: New threshold payments are being accumulated but **NOT being processed into batch conversions** because the micro-batch threshold checker has stopped running.

---

## 📊 Timeline Analysis

### GCAccumulator-10-26 Activity
**Status**: ✅ **WORKING CORRECTLY**

| Timestamp (UTC) | Timestamp (EST) | Event | Amount |
|-----------------|-----------------|-------|--------|
| 16:16:43 | 11:16:43 | New payment received | $0.3921064960 |

**Log Evidence**:
```
2025-11-03 11:16:43.480 EST
💰 [DATABASE] Accumulated USD: $0.3921064960 (pending conversion)
💳 [DATABASE] NowPayments Payment ID: 6066278802
👤 [DATABASE] User ID: 6271402111, Client ID: -1003296084379
✅ [DATABASE] Accumulation record inserted successfully (pending conversion)
```

**Result**: Payment successfully stored in `payout_accumulation` table with `is_paid_out = FALSE`.

---

### GCBatchProcessor-10-26 Activity
**Status**: ✅ **WORKING CORRECTLY**

| Timestamp (UTC) | Timestamp (EST) | Client Total | Threshold | Over Threshold? |
|-----------------|-----------------|--------------|-----------|-----------------|
| 16:05:01 | 11:05:01 | $0.89554043 | $2.00 | ❌ FALSE |
| 16:10:01 | 11:10:01 | $0.89554043 | $2.00 | ❌ FALSE |
| 16:15:01 | 11:15:01 | $0.89554043 | $2.00 | ❌ FALSE |
| 16:20:01 | 11:20:01 | $1.28764693 | $2.00 | ❌ FALSE |
| 16:25:01 | 11:25:01 | $1.28764693 | $2.00 | ❌ FALSE |
| 16:30:01 | 11:30:01 | $1.28764693 | $2.00 | ❌ FALSE |
| 16:35:01 | 11:35:01 | $1.28764693 | $2.00 | ❌ FALSE |
| 16:40:01 | 11:40:01 | $1.28764693 | $2.00 | ❌ FALSE |

**Log Evidence**:
```
2025-11-03 11:20:01.720 EST
🔍 [DATABASE DEBUG] Client -1003296084379: $1.28764693 / $2.00 (over: False)
🔍 [DATABASE DEBUG] Aggregated clients (before HAVING): 1
🔍 [DATABASE DEBUG] Records after JOIN: 2
🔍 [DATABASE DEBUG] Total unpaid accumulation records: 2
```

**Calculation Verification**:
- Previous total: $0.89554043
- New payment: $0.3921064960
- **Expected new total**: $0.89554043 + $0.3921064960 = **$1.28764693** ✅ CORRECT

**Result**: GCBatchProcessor is correctly querying the database and seeing the updated totals.

---

### GCMicroBatchProcessor-10-26 Activity
**Status**: 🔴 **STOPPED EXECUTION**

| Timestamp (UTC) | Timestamp (EST) | Event | Pending USD |
|-----------------|-----------------|-------|-------------|
| 16:05:05 | 11:05:05 | ✅ Last successful check | $0.89554043 |
| 16:10:XX | 11:10:XX | ❌ **NO RUN** | N/A |
| 16:15:XX | 11:15:XX | ❌ **NO RUN** | N/A |
| 16:20:XX | 11:20:XX | ❌ **NO RUN** | N/A |
| 16:25:XX | 11:25:XX | ❌ **NO RUN** | N/A |
| 16:30:XX | 11:30:XX | ❌ **NO RUN** | N/A |
| 16:35:XX | 11:35:XX | ❌ **NO RUN** | N/A |
| 16:40:XX | 11:40:XX | ❌ **NO RUN** | N/A |

**Last Successful Log** (16:05:05 UTC / 11:05:05 EST):
```
2025-11-03 11:05:05.544 EST
🎯 [ENDPOINT] Threshold check triggered
⏰ [ENDPOINT] Timestamp: 1762185905
🔐 [ENDPOINT] Fetching micro-batch threshold from Secret Manager
💰 [ENDPOINT] Current threshold: $2.00
🔍 [ENDPOINT] Querying total pending USD
💰 [DATABASE] Total pending USD: $0.89554043
📊 [ENDPOINT] Total pending: $0.89554043
🔍 [ENDPOINT] Querying total pending ACTUAL ETH
💰 [DATABASE] Total pending ACTUAL ETH: 0.0002734 ETH
💎 [ENDPOINT] Total ACTUAL ETH: 0.0002734 ETH
⏳ [ENDPOINT] Total pending ($0.89554043) < Threshold ($2.00) - no action
```

**Expected Behavior**: Service should run every 5 minutes via Cloud Scheduler
**Actual Behavior**: Service has not executed since 16:05 UTC

---

## 🔍 Root Cause Analysis

### Primary Hypothesis: Cloud Scheduler Job Failure/Suspension

The GCMicroBatchProcessor service is triggered by a **Cloud Scheduler job** that should invoke the `/check-threshold` endpoint every 5 minutes. The complete absence of log entries after 16:05 UTC indicates one of the following:

#### Possible Causes:

1. **Cloud Scheduler Job Disabled/Paused**
   - The scheduler job may have been manually disabled
   - The job may have been paused due to repeated failures
   - The job configuration may have been changed

2. **Cloud Scheduler Job Deleted**
   - The scheduler job may have been accidentally deleted
   - A deployment may have removed the scheduler configuration

3. **Cloud Scheduler Quota Exhausted**
   - Project may have hit Cloud Scheduler API quota limits
   - Service account permissions may have been revoked

4. **Service Target URL Changed**
   - The scheduler may be targeting an incorrect/old service URL
   - The service may have been redeployed to a different URL

5. **Authentication/Authorization Failure**
   - Service account credentials may have expired
   - IAM permissions may have changed
   - OIDC token generation may be failing

6. **Scheduler Job Schedule Modified**
   - The cron schedule may have been changed to a longer interval
   - The timezone configuration may have been altered

---

## 🔬 Comparative Analysis: Why GCBatchProcessor Works But GCMicroBatchProcessor Doesn't

| Aspect | GCBatchProcessor | GCMicroBatchProcessor |
|--------|------------------|------------------------|
| **Last Run** | 16:40:01 UTC ✅ | 16:05:05 UTC ❌ |
| **Schedule** | Every 5 minutes | Every 5 minutes |
| **Endpoint** | `/process` | `/check-threshold` |
| **Service Status** | Running normally | Stopped after 16:05 |
| **Scheduler Job** | Working ✅ | **Not triggering** ❌ |

**Key Insight**: Both services have similar configurations and should run every 5 minutes. The fact that GCBatchProcessor continues to run successfully while GCMicroBatchProcessor stopped suggests a **scheduler-specific issue** rather than a database or network problem.

---

## 📋 Database State Verification

### Query Results from GCBatchProcessor

**Records in payout_accumulation** (unpaid):
- **Total records**: 2
- **Client -1003296084379**: $1.28764693 (2 accumulation records)

**Accumulation Breakdown**:
1. **Record 1**: $0.89554043 (from earlier payment)
2. **Record 2**: $0.3921064960 (from 11:16 AM EST payment)
3. **Total**: $1.28764693

This confirms:
- ✅ GCAccumulator successfully inserted the new record
- ✅ GCBatchProcessor correctly sums both records
- ❌ GCMicroBatchProcessor is NOT seeing the new total (last saw $0.89554043)

---

## 🚨 Impact Assessment

### Current System State

1. **Payments ARE Being Accumulated**: ✅ Working
   - Users pay via NOWPayments
   - GCWebhook1 routes to GCAccumulator
   - GCAccumulator stores in `payout_accumulation` table

2. **Regular Threshold Processing IS Working**: ✅ Working
   - GCBatchProcessor runs every 5 minutes
   - Checks for clients >= $2.00 threshold
   - Would trigger GCSplit1 batch payouts if threshold reached

3. **Micro-Batch Threshold Processing IS STOPPED**: ❌ **NOT WORKING**
   - GCMicroBatchProcessor has stopped running
   - No checks for micro-batch threshold ($2.00 default)
   - **No ETH→USDT conversions will trigger**
   - Payments will accumulate indefinitely without conversion

### User Impact

- **Short-term**: Low (payments still accumulating)
- **Medium-term**: High (no USDT distributions happening)
- **Long-term**: Critical (users will never receive payouts)

**Affected Users**:
- Client -1003296084379 has $1.28764693 pending
- Need $0.71235307 more to reach $2.00 threshold
- When threshold reached, GCMicroBatchProcessor should trigger ETH→USDT swap
- **Currently**: No swaps will occur even if threshold reached

---

## 🔧 Required Actions (Priority Order)

### IMMEDIATE (P0) - Restore Service

1. **Verify Cloud Scheduler Job Status**
   ```bash
   gcloud scheduler jobs list \
     --location=us-central1 \
     --filter="name:microbatch" \
     --format="table(name,state,schedule,lastAttemptTime,httpTarget.uri)"
   ```

2. **Check for Paused/Disabled Jobs**
   ```bash
   gcloud scheduler jobs describe [JOB_NAME] \
     --location=us-central1
   ```

3. **If Job Exists But Paused - Resume**
   ```bash
   gcloud scheduler jobs resume [JOB_NAME] \
     --location=us-central1
   ```

4. **If Job Missing - Recreate**
   - Check deployment scripts in `/10-26/scripts/`
   - Redeploy scheduler job with correct configuration
   - Verify target URL points to current GCMicroBatchProcessor revision

5. **Manual Trigger Test**
   ```bash
   gcloud scheduler jobs run [JOB_NAME] \
     --location=us-central1
   ```

6. **Check Logs After Manual Trigger**
   - Verify `/check-threshold` endpoint receives request
   - Confirm it queries database and sees $1.28764693
   - Ensure no errors in execution

---

### HIGH PRIORITY (P1) - Verification

7. **Review Cloud Scheduler Logs**
   ```bash
   gcloud logging read "resource.type=cloud_scheduler_job \
     AND resource.labels.job_id:[JOB_NAME] \
     AND timestamp>=2025-11-03T16:05:00Z" \
     --limit=50 \
     --format=json
   ```

8. **Check Service Account Permissions**
   - Verify service account has `run.routes.invoke` permission
   - Confirm OIDC token generation is working
   - Check for any IAM policy changes

9. **Compare Working vs. Broken Configurations**
   - Export GCBatchProcessor scheduler config
   - Export GCMicroBatchProcessor scheduler config
   - Identify differences

10. **Test Endpoint Manually**
    ```bash
    curl -X POST \
      -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
      https://gcmicrobatchprocessor-10-26-291176869049.us-central1.run.app/check-threshold
    ```

---

### MEDIUM PRIORITY (P2) - Monitoring

11. **Set Up Scheduler Failure Alerts**
    - Create Cloud Monitoring alert for missed scheduler runs
    - Alert if no `/check-threshold` requests in 10 minutes
    - Send notifications to operations channel

12. **Add Heartbeat Monitoring**
    - Log a heartbeat message on every successful run
    - Monitor for absence of heartbeat
    - Alert if heartbeat missing for 15 minutes

13. **Create Scheduler Job Health Dashboard**
    - Track success rate of all scheduler jobs
    - Show last execution time for each job
    - Display error counts and types

---

## 📊 Diagnostic Commands

### Check Current Scheduler Jobs
```bash
# List all scheduler jobs in project
gcloud scheduler jobs list --location=us-central1

# Check specific job details
gcloud scheduler jobs describe gcmicrobatchprocessor-job \
  --location=us-central1

# View recent attempts
gcloud logging read "resource.type=cloud_scheduler_job \
  AND timestamp>=2025-11-03T15:00:00Z" \
  --limit=100 \
  --format=json
```

### Check Service Health
```bash
# Test GCMicroBatchProcessor health endpoint
curl https://gcmicrobatchprocessor-10-26-291176869049.us-central1.run.app/health

# Check service logs for errors
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=gcmicrobatchprocessor-10-26 \
  AND timestamp>=2025-11-03T16:00:00Z \
  AND severity>=ERROR" \
  --limit=50
```

### Check Service Account
```bash
# Verify service account exists
gcloud iam service-accounts describe \
  [SERVICE_ACCOUNT_EMAIL]

# Check IAM bindings on Cloud Run service
gcloud run services get-iam-policy \
  gcmicrobatchprocessor-10-26 \
  --region=us-central1
```

---

## 🎓 Lessons Learned

1. **Single Point of Failure**: Critical threshold processing depends on a single Cloud Scheduler job
2. **Silent Failures**: Scheduler job stopped without triggering alerts or notifications
3. **Insufficient Monitoring**: No automated detection of missing scheduler executions
4. **Lack of Redundancy**: No fallback mechanism if scheduler fails
5. **Delayed Detection**: Issue went unnoticed until manual log review

---

## 🔮 Recommended Architecture Improvements

### Immediate Improvements
1. **Add scheduler execution monitoring** with alerts
2. **Implement heartbeat logging** for health checks
3. **Create fallback mechanism** (e.g., Cloud Functions with Pub/Sub)

### Long-term Improvements
1. **Dual scheduler jobs** for redundancy
2. **Self-healing mechanism** that detects missed runs and triggers manual execution
3. **Service-level SLIs/SLOs** for scheduler reliability
4. **Automated recovery** scripts that resume paused jobs

---

## 📝 Investigation Checklist

- [ ] Check Cloud Scheduler job status
- [ ] Review scheduler job configuration
- [ ] Verify service account permissions
- [ ] Test endpoint manually with authenticated request
- [ ] Check Cloud Scheduler quota limits
- [ ] Review recent deployments for configuration changes
- [ ] Verify service URL hasn't changed
- [ ] Check for Cloud Scheduler API outages
- [ ] Review IAM policy changes in audit logs
- [ ] Test OIDC token generation
- [ ] Compare with working GCBatchProcessor config
- [ ] Create monitoring alerts for future failures

---

**Analysis Completed**: 2025-11-03
**Analyzed By**: Claude Code
**Next Action**: Verify Cloud Scheduler job status and configuration
**Estimated Time to Resolution**: 15-30 minutes (if scheduler job exists and just needs to be resumed)
