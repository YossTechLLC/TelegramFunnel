# Broadcast Messages Not Sending - Root Cause Analysis & Fix Checklist

**Date:** 2025-11-12
**Service:** GCBroadcastScheduler-10-26
**Issue:** Messages not being sent to open_channel_id or closed_channel_id
**Status:** ⏸️ AWAITING APPROVAL

---

## 🔍 Investigation Summary

### What I Found:

1. ✅ **Database Connection Works**
   - Service using Cloud SQL Connector correctly
   - Connects to `client_table` database successfully
   - Logs show: `🔌 Database engine configured: telepay-459221:us-central1:telepaypsql/client_table`

2. ✅ **Broadcasts Exist in Database**
   - **17 broadcasts** in `broadcast_manager` table
   - All meet criteria: `is_active=true`, `broadcast_status='pending'`, `next_send_time <= NOW()`, `consecutive_failures < 5`
   - Test script confirms query returns 17 rows when executed with same code pattern

3. ❌ **Service Returns "No broadcasts due"**
   - `/api/broadcast/execute` endpoint returns: `{"message": "No broadcasts due", "total_broadcasts": 0}`
   - `fetch_due_broadcasts()` is returning empty list []
   - No error logs showing "Error fetching due broadcasts"

4. ❌ **Silent Failure Detected**
   - Query executes without throwing exceptions
   - BUT returns 0 rows instead of 17 rows
   - Root cause: **fetch_due_broadcasts() implementation has a bug**

---

## 🐛 Root Cause Analysis

### The Problem

Looking at `database_manager.py` lines 100-161, I discovered the issue:

**Current Implementation (WRONG):**
```python
def fetch_due_broadcasts(self) -> List[Dict[str, Any]]:
    try:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = """..."""  # Query is correct

            cur.execute(query)
            rows = cur.fetchall()

            # Convert rows to dictionaries
            columns = [desc[0] for desc in cur.description]
            broadcasts = [dict(zip(columns, row)) for row in rows]

            self.logger.info(f"📋 Found {len(broadcasts)} broadcasts due for sending")
            return broadcasts

    except Exception as e:
        self.logger.error(f"❌ Error fetching due broadcasts: {e}")
        return []
```

### Why It Returns 0 Rows

**The issue is that `conn.cursor()` is being called on a raw pg8000 connection that comes from SQLAlchemy's `raw_connection()`.**

When using SQLAlchemy with pg8000, there's a subtle difference in how cursors work:
- pg8000 connections need to have transactions **explicitly committed** OR
- The cursor results might not be available immediately

However, based on my test showing the query DOES work with the same pattern, the actual issue is likely:

**The database_manager.py code we're looking at is NOT the same as what's actually deployed!**

The build from Session 122 added Cloud SQL Connector to requirements.txt but **THE CODE IN database_manager.py WAS ALREADY UPDATED** in that session.

Let me verify what's actually in the current deployed database_manager.py by checking if there are any error logs we missed.

---

## 🔧 Fix Strategy

Based on the investigation, here are the issues to fix:

### Issue 1: Missing Log Output
- `fetch_due_broadcasts()` line 156 logs: `"📋 Found X broadcasts due for sending"`
- This log is NOT appearing in service logs
- This suggests the function is either:
  1. Not being called at all, OR
  2. Throwing an exception before reaching the log statement, OR
  3. The connection is failing silently

### Issue 2: Telegram Bot Token Required
- Even if broadcasts are fetched, they need to be SENT via Telegram
- `TelegramClient` requires valid bot token (`BOT_TOKEN` secret)
- `telegram_client.py` must have correct implementation

### Issue 3: Missing Telegram Message Composer
- Broadcasts need to format donation messages
- Must pull data from `main_clients_database` (subscription prices, times, donation message template)
- Must send to both open_channel_id and closed_channel_id

---

## 📋 Fix Checklist

### Phase 1: Add Debug Logging to Isolate Issue

**File:** `database_manager.py` (line 100-161)

**Add extensive debug logging:**

```python
def fetch_due_broadcasts(self) -> List[Dict[str, Any]]:
    """
    Fetch all broadcast entries that are due to be sent.
    """
    try:
        self.logger.info("🔍 [DEBUG] fetch_due_broadcasts() called")

        with self.get_connection() as conn:
            self.logger.info("🔍 [DEBUG] Database connection obtained")

            cur = conn.cursor()
            self.logger.info("🔍 [DEBUG] Cursor created")

            query = """
                SELECT
                    bm.id,
                    bm.client_id,
                    bm.open_channel_id,
                    bm.closed_channel_id,
                    bm.last_sent_time,
                    bm.next_send_time,
                    bm.broadcast_status,
                    bm.consecutive_failures,
                    mc.open_channel_title,
                    mc.open_channel_description,
                    mc.closed_channel_title,
                    mc.closed_channel_description,
                    mc.closed_channel_donation_message,
                    mc.sub_1_price,
                    mc.sub_1_time,
                    mc.sub_2_price,
                    mc.sub_2_time,
                    mc.sub_3_price,
                    mc.sub_3_time
                FROM broadcast_manager bm
                INNER JOIN main_clients_database mc
                    ON bm.open_channel_id = mc.open_channel_id
                WHERE bm.is_active = true
                    AND bm.broadcast_status = 'pending'
                    AND bm.next_send_time <= NOW()
                    AND bm.consecutive_failures < 5
                ORDER BY bm.next_send_time ASC
            """

            self.logger.info("🔍 [DEBUG] Executing query...")
            cur.execute(query)

            self.logger.info("🔍 [DEBUG] Fetching all rows...")
            rows = cur.fetchall()

            self.logger.info(f"🔍 [DEBUG] Fetched {len(rows)} rows from database")

            # Convert rows to dictionaries
            columns = [desc[0] for desc in cur.description]
            self.logger.info(f"🔍 [DEBUG] Column names: {columns}")

            broadcasts = [dict(zip(columns, row)) for row in rows]

            self.logger.info(f"📋 Found {len(broadcasts)} broadcasts due for sending")

            if broadcasts:
                for i, b in enumerate(broadcasts[:3], 1):  # Log first 3
                    self.logger.info(
                        f"   Broadcast {i}: id={b['id']}, "
                        f"open_channel={b['open_channel_id']}, "
                        f"closed_channel={b['closed_channel_id']}"
                    )

            return broadcasts

    except Exception as e:
        self.logger.error(f"❌ Error fetching due broadcasts: {e}", exc_info=True)
        return []
```

**Why:** This will show us EXACTLY where the code is failing.

---

### Phase 2: Check if Telegram Client is Initialized

**Verify BOT_TOKEN secret exists:**
```bash
gcloud secrets versions access latest --secret=BOT_TOKEN
```

**Verify BOT_USERNAME secret exists:**
```bash
gcloud secrets versions access latest --secret=BOT_USERNAME
```

---

### Phase 3: Read Actual Telegram Implementation

**Files to review:**
- `telegram_client.py` - Verify it can send messages
- `broadcast_executor.py` - Verify it calls Telegram client correctly
- `broadcast_tracker.py` - Verify it updates database after sending

---

### Phase 4: Test End-to-End Flow

1. Deploy Phase 1 changes (debug logging)
2. Trigger `/api/broadcast/execute` endpoint
3. Review logs to see where it's failing
4. Fix the actual root cause based on logs

---

## 🚨 Critical Questions for User

Before I proceed with fixes, I need to confirm:

1. **Are the broadcasts SUPPOSED to send automatically every 24 hours?**
   - Current `next_send_time` values are in the past (from 2025-11-12 00:32 UTC)
   - They should have sent already

2. **Has the Telegram bot been created and configured?**
   - Do `BOT_TOKEN` and `BOT_USERNAME` secrets exist?
   - Is the bot added as admin to all channels?

3. **What should the broadcast messages contain?**
   - Should they include subscription pricing info?
   - Should they link to the closed/premium channel?
   - Is there a specific message template?

---

## 🎯 Expected Root Causes (In Order of Likelihood)

1. **fetch_due_broadcasts() is failing silently** (80% likely)
   - Exception being caught but not logged properly
   - Need debug logging to confirm

2. **Telegram client not initialized** (15% likely)
   - Missing BOT_TOKEN or BOT_USERNAME secrets
   - Would cause failure at broadcast execution stage

3. **broadcast_executor not calling telegram_client** (5% likely)
   - Logic error in execution flow
   - Would show in logs as broadcasts "executed" but nothing sent

---

## ✅ Success Criteria

- [ ] Debug logs show `fetch_due_broadcasts()` returning 17 broadcasts
- [ ] Broadcasts are sent to Telegram channels
- [ ] Database updated with `last_sent_time` and `next_send_time`
- [ ] Users see messages in both open and closed channels
- [ ] No errors in service logs

---

**Ready to proceed?** Please review this checklist and let me know:
1. Should I add debug logging (Phase 1)?
2. Do the Telegram bot secrets exist?
3. What should the broadcast messages say?
