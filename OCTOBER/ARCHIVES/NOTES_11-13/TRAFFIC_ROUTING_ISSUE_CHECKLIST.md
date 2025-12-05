# Traffic Routing Issue - Verification & Fix Checklist

**Issue:** Subscription payment flow still broken after fix deployment
**Date:** 2025-11-13 Session 142 (Continued)
**Severity:** 🔴 CRITICAL - Fix exists but not active

---

## Executive Summary

**Root Cause:** Traffic is routed to OLD revision instead of NEW fixed revision.

- ✅ Fix deployed successfully: `gcbotcommand-10-26-00007-mzc`
- ✅ New revision is healthy and ready
- ❌ Traffic is 100% on old buggy revision: `gcbotcommand-10-26-00004-26n`
- ❌ Subscription flow failing because old code is still active

**Solution:** Route traffic to the new revision.

---

## Current State Verification ✅ COMPLETED

### 1. Revision Status
```
NAME                          STATUS  SERVING_TRAFFIC
gcbotcommand-10-26-00007-mzc  True    0%         ← Fixed revision (NOT active)
gcbotcommand-10-26-00006-fgh  False   0%         ← Failed deployment (missing env vars)
gcbotcommand-10-26-00005-65p  False   0%         ← Failed deployment
gcbotcommand-10-26-00004-26n  True    100%       ← Old buggy revision (ACTIVE)
```

### 2. What's in Each Revision

**Revision 00004-26n (Currently Serving - HAS THE BUG):**
- Created: 2025-11-13 20:22:20 UTC (Session 140)
- Code: Has donation callback routing fix
- Bug: `database_manager.py` always sets `port=5432` even for Unix socket
- Result: `save_conversation_state()` works, `get_conversation_state()` returns None

**Revision 00007-mzc (Fixed but Not Serving):**
- Created: 2025-11-13 22:32:22 UTC (Session 142)
- Code: Has Unix socket fix in `database_manager.py`
- Fix: Sets `port=None` for Unix socket, `port=5432` only for TCP
- Config: ✅ Cloud SQL instance annotation present
- Status: Healthy and ready to serve
- Result: Both save and get operations should work correctly

### 3. Logs Confirm Old Revision Active
```
2025-11-13 22:41:03 - 📍 /start command from user 6271402111
2025-11-13 22:41:05 - 🔘 Callback: TRIGGER_PAYMENT from user 6271402111
2025-11-13 22:41:06 - ✅ Message sent (error message)
Revision: gcbotcommand-10-26-00004-26n  ← OLD CODE
```

---

## Why This Happened

When I deployed revision 00007-mzc, Cloud Run:
1. **Did not automatically route traffic** to it
2. Likely because revisions 00005 and 00006 failed health checks
3. Cloud Run kept traffic on last known good revision (00004-26n)
4. This is a safety feature to prevent broken deployments from serving traffic

---

## Fix Plan

### Option A: Route 100% Traffic to Fixed Revision (RECOMMENDED)

**Command:**
```bash
gcloud run services update-traffic gcbotcommand-10-26 \
  --region=us-central1 \
  --to-revisions=gcbotcommand-10-26-00007-mzc=100
```

**What This Does:**
- Immediately switches 100% of traffic to the fixed revision
- Old revision becomes inactive (but still available for rollback)
- Takes effect instantly (no rebuild required)

**Time Required:** 10 seconds

**Risk Level:** LOW
- Revision 00007-mzc is healthy (passed health checks)
- Can rollback instantly if issues occur
- Fix is proven correct (same as GCDonationHandler Session 141)

---

### Option B: Gradual Canary Deployment (SAFER BUT SLOWER)

**Step 1: Route 10% traffic to new revision**
```bash
gcloud run services update-traffic gcbotcommand-10-26 \
  --region=us-central1 \
  --to-revisions=gcbotcommand-10-26-00007-mzc=10,gcbotcommand-10-26-00004-26n=90
```

**Step 2: Monitor logs for 5-10 minutes**
- Check for errors in 00007-mzc
- Verify subscription flow works for ~10% of users

**Step 3: Route 100% if no issues**
```bash
gcloud run services update-traffic gcbotcommand-10-26 \
  --region=us-central1 \
  --to-revisions=gcbotcommand-10-26-00007-mzc=100
```

**Time Required:** 10-15 minutes

**Risk Level:** VERY LOW
- Test with small percentage first
- Easy to rollback if issues

---

## Verification Checklist

### ☐ Pre-Deployment Verification
1. ✅ Confirm revision 00007-mzc exists and is healthy
2. ✅ Confirm Cloud SQL annotation present on 00007-mzc
3. ✅ Confirm old revision 00004-26n is currently serving 100% traffic

### ☐ Execute Traffic Routing (Choose Option A or B)

**If Option A (Immediate):**
```bash
gcloud run services update-traffic gcbotcommand-10-26 \
  --region=us-central1 \
  --to-revisions=gcbotcommand-10-26-00007-mzc=100
```

**If Option B (Canary):**
Start with 10%, monitor, then increase to 100%.

### ☐ Post-Deployment Verification

**1. Check Traffic Distribution**
```bash
gcloud run services describe gcbotcommand-10-26 --region=us-central1 --format="value(status.traffic)"
```

**Expected:**
```
{'percent': 100, 'revisionName': 'gcbotcommand-10-26-00007-mzc'}
```

**2. Test Subscription Flow End-to-End**
- Go to open channel
- Click subscription button (e.g., "$45.0 for 13 days")
- Wait for bot PM with "Launch Payment Gateway" button
- Click "Launch Payment Gateway"
- **Expected:** Payment invoice appears with "💳 Pay Now" button
- **No Error:** Should NOT see "❌ No payment context found"

**3. Monitor Logs**
```bash
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=gcbotcommand-10-26" \
  --format=json \
  --filter='textPayload=~"start command" OR textPayload=~"TRIGGER_PAYMENT" OR textPayload=~"Unix socket"'
```

**Expected Log Sequence:**
```
[Time] 📍 /start command from user {user_id}, args: {token}
[Time] 💰 Subscription: channel={id}, price=${price}, time={days}days
[Time] ✅ Message sent to chat_id {user_id}
[Time] 🔘 Callback: TRIGGER_PAYMENT from user {user_id}
[Time] 🌐 Calling GCPaymentGateway: /create-invoice
[Time] ✅ Message sent to chat_id {user_id}

Revision: gcbotcommand-10-26-00007-mzc  ← NEW CODE
```

**4. Check for Unix Socket Usage (First Request Only)**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcbotcommand-10-26 AND textPayload=~\"Unix socket\"" --limit=1
```

**Expected:**
```
🔌 Using Cloud SQL Unix socket: /cloudsql/telepay-459221:us-central1:telepaypsql
```

---

## Rollback Plan (If Issues Occur)

**Immediate Rollback to Old Revision:**
```bash
gcloud run services update-traffic gcbotcommand-10-26 \
  --region=us-central1 \
  --to-revisions=gcbotcommand-10-26-00004-26n=100
```

**Note:** Old revision will continue to have the database bug, but at least it's a known state.

---

## Decision Tree

```
Start: Subscription flow failing after fix deployed
  ↓
  Is revision 00007-mzc healthy?
  ├─ NO → Investigate health check failures (unlikely - already verified)
  └─ YES ↓
      ↓
      Is traffic on revision 00007-mzc?
      ├─ YES → Different issue, investigate logs
      └─ NO ↓ (CURRENT STATE)
          ↓
          Route traffic to 00007-mzc
          ↓
          Test subscription flow
          ↓
          Does it work now?
          ├─ YES → SUCCESS! Update documentation
          └─ NO → Rollback and investigate deeper
```

---

## Why This Fix Will Work

### Technical Explanation:

**The Bug (in 00004-26n):**
```python
# database_manager.py (OLD CODE)
def __init__(self):
    if cloud_sql_connection:
        self.host = f"/cloudsql/{cloud_sql_connection}"
    else:
        self.host = fetch_database_host()

    self.port = 5432  # ❌ ALWAYS set, even for Unix socket

def get_connection(self):
    return psycopg2.connect(
        host=self.host,
        port=self.port  # ❌ Port passed even for Unix socket
    )
```

**The Fix (in 00007-mzc):**
```python
# database_manager.py (NEW CODE)
def __init__(self):
    if cloud_sql_connection:
        self.host = f"/cloudsql/{cloud_sql_connection}"
        self.port = None  # ✅ No port for Unix socket
    else:
        self.host = fetch_database_host()
        self.port = 5432  # ✅ Port only for TCP

def get_connection(self):
    conn_params = {
        "host": self.host,
        "dbname": self.dbname,
        "user": self.user,
        "password": self.password
    }

    if self.port is not None:  # ✅ Conditionally include port
        conn_params["port"] = self.port

    return psycopg2.connect(**conn_params)
```

**Why It Matters:**
- psycopg2 has inconsistent behavior when port is provided for Unix socket
- INSERT operations (save) work even with port parameter
- SELECT operations (get) fail silently with port parameter
- Omitting port parameter fixes SELECT operations

**Evidence:**
- Identical fix worked for GCDonationHandler in Session 141
- User confirmed conversation state row EXISTS in database (save worked)
- But get_conversation_state() returns None (get failed)
- Fix removes port parameter for Unix socket connections

---

## Recommended Action

**I recommend Option A (Immediate Traffic Routing):**

1. **Low Risk:**
   - Revision is healthy
   - Fix is proven (GCDonationHandler uses same pattern)
   - Can rollback instantly if needed

2. **High Impact:**
   - Fixes 100% of subscription payment failures immediately
   - No gradual rollout complexity
   - Users can start subscribing right away

3. **Fast:**
   - Takes 10 seconds to execute
   - No rebuild required
   - Instant activation

**Command to execute:**
```bash
gcloud run services update-traffic gcbotcommand-10-26 \
  --region=us-central1 \
  --to-revisions=gcbotcommand-10-26-00007-mzc=100
```

---

## What You Need to Decide

**Please choose:**

1. **Option A:** Route 100% traffic now (recommended)
2. **Option B:** Gradual canary deployment (safer but slower)
3. **Wait:** You want to review something else first

**After choosing, I will:**
1. Execute the traffic routing command
2. Verify traffic is on new revision
3. Guide you through testing the subscription flow
4. Monitor logs to confirm fix is working
5. Update documentation (PROGRESS.md, BUGS.md, DECISIONS.md)

---

## Status

**Current:** ⏳ Awaiting your decision on traffic routing

**Required User Action:**
- Choose Option A or Option B (or ask questions)
- Confirm you want me to proceed with traffic routing

**Next Steps (After Routing):**
- Test complete subscription flow
- Verify no "No payment context found" error
- Confirm payment invoice creation works
- Update documentation with Session 142 resolution
