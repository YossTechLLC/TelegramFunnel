# GCDonationHandler Deployment Error Fix - Quick Checklist
**Parent Document:** DEPLOYMENT_ERROR_ANALYSIS.md
**Status:** AWAITING APPROVAL
**Estimated Time:** 95 minutes

---

## Quick Summary

**Two Critical Errors:**
1. ❌ `'DatabaseManager' object has no attribute 'execute_query'` - KeypadStateManager broken
2. ❌ `RuntimeError('Event loop is closed')` - TelegramClient broken

**Fix Strategy:**
1. Refactor KeypadStateManager to use `_get_connection()` pattern (match DatabaseManager)
2. Add `_run_async()` helper to TelegramClient (replace `asyncio.run()`)

---

## Phase 1: KeypadStateManager Fixes (45 min)

### File: `keypad_state_manager.py`

- [ ] **Task 1.1:** Refactor `create_state()` (lines 21-42)
  - Replace `execute_query()` with `_get_connection()` pattern
  - Verify UPSERT works (INSERT ... ON CONFLICT)

- [ ] **Task 1.2:** Refactor `get_state()` (lines 44-74)
  - Replace `execute_query()` with `_get_connection()` pattern
  - Return dict with proper column mapping

- [ ] **Task 1.3:** Refactor `update_amount()` (lines 76-96)
  - Replace `execute_query()` with `_get_connection()` pattern
  - Update both `current_amount` and `decimal_entered`

- [ ] **Task 1.4:** Refactor `delete_state()` (lines 98-113)
  - Replace `execute_query()` with `_get_connection()` pattern

- [ ] **Task 1.5:** Refactor `cleanup_stale_states()` (lines 124-139)
  - Replace `execute_query()` with `_get_connection()` pattern
  - Call `cleanup_stale_donation_states()` function

- [ ] **Task 1.6:** Verify syntax
  ```bash
  python3 -m py_compile keypad_state_manager.py
  ```

---

## Phase 2: TelegramClient Fixes (30 min)

### File: `telegram_client.py`

- [ ] **Task 2.1:** Add `_run_async()` helper method (after line 47)
  - Detect existing event loop
  - Create loop if needed
  - Use `loop.run_until_complete(coro)` instead of `asyncio.run()`

- [ ] **Task 2.2:** Update `send_message()` (line 90)
  - Replace: `asyncio.run(_send())` → `self._run_async(_send())`

- [ ] **Task 2.3:** Update `edit_message_reply_markup()` (line 183)
  - Replace: `asyncio.run(_edit())` → `self._run_async(_edit())`

- [ ] **Task 2.4:** Update `delete_message()` (line 227)
  - Replace: `asyncio.run(_delete())` → `self._run_async(_delete())`

- [ ] **Task 2.5:** Update `answer_callback_query()` (line 280)
  - Replace: `asyncio.run(_answer())` → `self._run_async(_answer())`

- [ ] **Task 2.6:** Verify syntax
  ```bash
  python3 -m py_compile telegram_client.py
  ```

---

## Phase 3: Deploy & Test (20 min)

### Build & Deploy

- [ ] **Task 3.1:** Build Docker image
  ```bash
  cd GCDonationHandler-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gcdonationhandler-10-26
  ```

- [ ] **Task 3.2:** Deploy to Cloud Run
  ```bash
  gcloud run deploy gcdonationhandler-10-26 \
    --image gcr.io/telepay-459221/gcdonationhandler-10-26 \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql
  ```

- [ ] **Task 3.3:** Verify health check
  ```bash
  curl https://gcdonationhandler-10-26-291176869049.us-central1.run.app/health
  ```

### Functional Testing

- [ ] **Task 3.4:** Test donation flow end-to-end
  1. Click "💝 Donate" in closed channel
  2. Keypad appears
  3. Press digits (e.g., 5, 0, ., 0, 0)
  4. Display updates correctly
  5. Press "Confirm"
  6. Payment gateway link appears
  7. NO errors

- [ ] **Task 3.5:** Check logs for errors
  ```bash
  gcloud logging read \
    'resource.type="cloud_run_revision"
     resource.labels.service_name="gcdonationhandler-10-26"
     severity>=ERROR
     timestamp>="2025-11-13T22:00:00Z"' \
    --limit=50
  ```
  - Verify: NO "execute_query" errors
  - Verify: NO "Event loop is closed" errors

---

## Success Criteria

### Must Pass ✅
- [ ] Keypad appears when user clicks "Donate"
- [ ] Keypad display updates as user presses buttons
- [ ] Confirm button creates payment invoice
- [ ] NO "execute_query" errors
- [ ] NO "Event loop is closed" errors
- [ ] NO "Session expired" errors

### Should Pass ✅
- [ ] Response time < 3 seconds
- [ ] State persists across button presses
- [ ] Clean logs (no warnings/errors)

---

## Rollback Plan (If Needed)

```bash
# Get previous revision
gcloud run revisions list \
  --service=gcdonationhandler-10-26 \
  --region=us-central1 \
  --format='value(metadata.name)' \
  --limit=2

# Rollback to previous revision
gcloud run services update-traffic gcdonationhandler-10-26 \
  --region=us-central1 \
  --to-revisions=<PREVIOUS_REVISION>=100
```

---

## Quick Reference: Code Patterns

### DatabaseManager Pattern (USE THIS)
```python
with self.db_manager._get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT ...", (params,))
        result = cur.fetchone()
        conn.commit()  # For INSERT/UPDATE/DELETE
```

### TelegramClient Pattern (USE THIS)
```python
async def _operation():
    result = await self.bot.some_method(...)
    return result

result = self._run_async(_operation())  # NOT asyncio.run()
```

---

**Status:** AWAITING USER APPROVAL
**Once approved, execute phases 1-3 in sequence**
