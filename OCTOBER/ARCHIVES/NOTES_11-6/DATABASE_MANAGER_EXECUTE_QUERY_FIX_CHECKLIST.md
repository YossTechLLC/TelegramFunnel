# DatabaseManager execute_query() Method Missing Fix Checklist

**Date:** 2025-11-02
**Issue:** Idempotency code calling non-existent `execute_query()` method on DatabaseManager
**Status:** 🟢 IN PROGRESS

---

## Root Cause Analysis

### The Problem
GCWebhook1 and GCWebhook2 services are failing with:
```
⚠️ [IDEMPOTENCY] Failed to mark payment as processed: 'DatabaseManager' object has no attribute 'execute_query'
```

### Root Cause
During the idempotency implementation (previous session), we added code that calls:
```python
db_manager.execute_query(query, params)
```

**BUT:** The DatabaseManager class does NOT have an `execute_query()` method.

**Available Methods:**
- `get_connection()` - Returns a database connection
- `record_private_channel_user()` - Specific method for user records
- `get_payout_strategy()` - Specific method for payout data
- `get_subscription_id()` - Specific method for subscription ID
- `get_nowpayments_data()` - Specific method for NowPayments data

### Evidence

**GCWebhook1-10-26/tph1-10-26.py line 434:**
```python
db_manager.execute_query("""
    UPDATE processed_payments
    SET gcwebhook1_processed = TRUE, ...
    WHERE payment_id = %s
""", (nowpayments_payment_id,))
```

**GCWebhook2-10-26/tph2-10-26.py line 137:**
```python
existing_invite = db_manager.execute_query("""
    SELECT telegram_invite_sent, telegram_invite_link, ...
    FROM processed_payments
    WHERE payment_id = %s
""", (payment_id,))
```

**GCWebhook2-10-26/tph2-10-26.py line 281:**
```python
db_manager.execute_query("""
    UPDATE processed_payments
    SET telegram_invite_sent = TRUE, ...
    WHERE payment_id = %s
""", (invite_link, payment_id))
```

**NP-Webhook CORRECT pattern (app.py lines 654-666):**
```python
conn_check = db_manager.get_connection()
cur_check = conn_check.cursor()
cur_check.execute("""
    SELECT gcwebhook1_processed
    FROM processed_payments
    WHERE payment_id = %s
""", (nowpayments_payment_id,))
existing_payment = cur_check.fetchone()
cur_check.close()
conn_check.close()
```

---

## Fix Strategy

**Replace all `db_manager.execute_query()` calls with proper connection pattern:**

### For SELECT queries:
```python
conn = db_manager.get_connection()
if not conn:
    # Handle error
    return
cur = conn.cursor()
cur.execute(query, params)
result = cur.fetchone()  # or fetchall()
cur.close()
conn.close()
```

### For UPDATE/INSERT queries:
```python
conn = db_manager.get_connection()
if not conn:
    # Handle error
    return
cur = conn.cursor()
cur.execute(query, params)
conn.commit()
cur.close()
conn.close()
```

---

## Implementation Checklist

### Phase 1: Verify Scope ✅

#### Task 1.1: Identify all execute_query() calls ✅
- **Status:** COMPLETED
- **Findings:**
  - GCWebhook1: 1 occurrence (line 434 - UPDATE query)
  - GCWebhook2: 2 occurrences (line 137 - SELECT, line 281 - UPDATE)
  - NP-Webhook: 0 occurrences (uses correct pattern)

#### Task 1.2: Check DatabaseManager class structure ✅
- **Status:** COMPLETED
- **Result:** Confirmed no `execute_query()` method exists

#### Task 1.3: Document correct pattern from NP-Webhook ✅
- **Status:** COMPLETED
- **Pattern:** get_connection() + cursor() + execute() + close()

### Phase 2: Fix GCWebhook1 ⏳

#### Task 2.1: Fix UPDATE query at line 434
- **Status:** PENDING
- **Location:** tph1-10-26.py line 434
- **Current Code:**
  ```python
  db_manager.execute_query("""
      UPDATE processed_payments
      SET gcwebhook1_processed = TRUE, ...
      WHERE payment_id = %s
  """, (nowpayments_payment_id,))
  ```
- **Fixed Code:**
  ```python
  conn = db_manager.get_connection()
  if conn:
      cur = conn.cursor()
      cur.execute("""
          UPDATE processed_payments
          SET gcwebhook1_processed = TRUE,
              gcwebhook1_processed_at = CURRENT_TIMESTAMP,
              updated_at = CURRENT_TIMESTAMP
          WHERE payment_id = %s
      """, (nowpayments_payment_id,))
      conn.commit()
      cur.close()
      conn.close()
  ```

#### Task 2.2: Verify GCWebhook1 code syntax
- **Status:** PENDING
- **Action:** Python compile check

### Phase 3: Fix GCWebhook2 ⏳

#### Task 3.1: Fix SELECT query at line 137
- **Status:** PENDING
- **Location:** tph2-10-26.py line 137
- **Current Code:**
  ```python
  existing_invite = db_manager.execute_query("""
      SELECT telegram_invite_sent, telegram_invite_link, telegram_invite_sent_at
      FROM processed_payments
      WHERE payment_id = %s
  """, (payment_id,))

  if existing_invite and existing_invite[0]['telegram_invite_sent']:
      # Uses dict-style access
  ```
- **Fixed Code:**
  ```python
  conn = db_manager.get_connection()
  if conn:
      cur = conn.cursor()
      cur.execute("""
          SELECT telegram_invite_sent, telegram_invite_link, telegram_invite_sent_at
          FROM processed_payments
          WHERE payment_id = %s
      """, (payment_id,))
      existing_invite = cur.fetchone()
      cur.close()
      conn.close()
  else:
      existing_invite = None

  if existing_invite and existing_invite[0]:  # Now tuple access [0], [1], [2]
      # Must update code to use tuple indexes instead of dict keys
  ```

#### Task 3.2: Fix UPDATE query at line 281
- **Status:** PENDING
- **Location:** tph2-10-26.py line 281
- **Current Code:**
  ```python
  db_manager.execute_query("""
      UPDATE processed_payments
      SET telegram_invite_sent = TRUE, ...
      WHERE payment_id = %s
  """, (invite_link, payment_id))
  ```
- **Fixed Code:**
  ```python
  conn = db_manager.get_connection()
  if conn:
      cur = conn.cursor()
      cur.execute("""
          UPDATE processed_payments
          SET telegram_invite_sent = TRUE,
              telegram_invite_sent_at = CURRENT_TIMESTAMP,
              telegram_invite_link = %s,
              updated_at = CURRENT_TIMESTAMP
          WHERE payment_id = %s
      """, (invite_link, payment_id))
      conn.commit()
      cur.close()
      conn.close()
  ```

#### Task 3.3: Update result access from dict to tuple
- **Status:** PENDING
- **Location:** tph2-10-26.py lines 146-149
- **Current Code:**
  ```python
  if existing_invite and existing_invite[0]['telegram_invite_sent']:
      existing_link = existing_invite[0]['telegram_invite_link']
      sent_at = existing_invite[0]['telegram_invite_sent_at']
  ```
- **Fixed Code:**
  ```python
  if existing_invite and existing_invite[0]:  # telegram_invite_sent is index 0
      telegram_invite_sent = existing_invite[0]  # boolean
      existing_link = existing_invite[1]  # telegram_invite_link
      sent_at = existing_invite[2]  # telegram_invite_sent_at
  ```

#### Task 3.4: Verify GCWebhook2 code syntax
- **Status:** PENDING
- **Action:** Python compile check

### Phase 4: Deployment ⏳

#### Task 4.1: Deploy GCWebhook2 (downstream first)
- **Status:** PENDING
- **Command:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook2-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook2-10-26
  gcloud run deploy gcwebhook2-10-26 --image gcr.io/telepay-459221/gcwebhook2-10-26 --region us-central1
  ```

#### Task 4.2: Deploy GCWebhook1 (upstream second)
- **Status:** PENDING
- **Command:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook1-10-26
  gcloud run deploy gcwebhook1-10-26 --image gcr.io/telepay-459221/gcwebhook1-10-26 --region us-central1
  ```

### Phase 5: Verification ⏳

#### Task 5.1: Check deployment logs for startup errors
- **Status:** PENDING
- **Action:** Verify no import or configuration errors

#### Task 5.2: Test idempotency with new payment
- **Status:** PENDING
- **Expected Logs:**
  - GCWebhook1: `✅ [IDEMPOTENCY] Marked payment {id} as processed`
  - GCWebhook2: `🆕 [IDEMPOTENCY] No existing invite found - proceeding to send`
  - GCWebhook2: `✅ [IDEMPOTENCY] Marked invite as sent for payment {id}`

#### Task 5.3: Test idempotency with duplicate IPN
- **Status:** PENDING
- **Expected Behavior:**
  - NP-Webhook: Returns 200 without re-enqueuing
  - GCWebhook1: Not triggered (blocked at NP-Webhook)
  - GCWebhook2: Not triggered

#### Task 5.4: Monitor for database connection errors
- **Status:** PENDING
- **Action:** Check logs for 1 hour after deployment

### Phase 6: Documentation ⏳

#### Task 6.1: Update PROGRESS.md
- **Status:** PENDING
- **Content:** Log the bug fix and lessons learned

#### Task 6.2: Update BUGS.md
- **Status:** PENDING
- **Content:** Document the execute_query bug and resolution

#### Task 6.3: Update DECISIONS.md
- **Status:** PENDING
- **Content:** Establish pattern for database operations

---

## Key Insights

### Why This Happened
During the idempotency implementation, we assumed the DatabaseManager class had a generic `execute_query()` method like other database wrappers. However:
- The DatabaseManager was designed with **specific, purpose-built methods**
- For custom queries, the correct pattern is **get_connection() + cursor operations**
- NP-Webhook correctly used this pattern, but GCWebhook1/2 did not

### The Difference: pg8000 Returns Tuples, Not Dicts
- **pg8000 cursor.fetchone()** returns a tuple: `(value1, value2, value3)`
- **NOT a dict:** Code expecting `result[0]['column_name']` will fail
- **Correct access:** Use tuple indexes `result[0]`, `result[1]`, `result[2]`

### Prevention
1. **Always check the class interface** before calling methods
2. **Follow existing patterns** in the codebase (NP-Webhook had the right pattern)
3. **Test locally** with syntax checks before deployment
4. **Document the database access pattern** for future development

---

## Progress Summary

| Phase | Tasks | Completed | Status |
|-------|-------|-----------|--------|
| Phase 1: Verify Scope | 3 | 3/3 | ✅ COMPLETE |
| Phase 2: Fix GCWebhook1 | 2 | 0/2 | ⏳ PENDING |
| Phase 3: Fix GCWebhook2 | 4 | 0/4 | ⏳ PENDING |
| Phase 4: Deployment | 2 | 0/2 | ⏳ PENDING |
| Phase 5: Verification | 4 | 0/4 | ⏳ PENDING |
| Phase 6: Documentation | 3 | 0/3 | ⏳ PENDING |

**Total:** 18 tasks, 3 completed, 15 pending

---

## Next Steps

1. **Fix GCWebhook1** tph1-10-26.py line 434 (Phase 2)
2. **Fix GCWebhook2** tph2-10-26.py lines 137, 146-149, 281 (Phase 3)
3. **Deploy services** in correct order (Phase 4)
4. **Verify with testing** (Phase 5)
5. **Update documentation** (Phase 6)
