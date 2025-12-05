# GCDonationHandler Deployment Error Analysis
**Date:** 2025-11-13
**Status:** 🔴 CRITICAL - Service Deployed But Non-Functional
**Revision:** gcdonationhandler-10-26-00005-fvk

---

## 🚨 Executive Summary

The GCDonationHandler service was successfully deployed after stateless keypad refactoring, but is **completely broken** in production. Two critical implementation errors prevent all donation functionality:

1. **Database Error:** `'DatabaseManager' object has no attribute 'execute_query'`
2. **Async Error:** `RuntimeError('Event loop is closed')`

**Impact:** 100% of donation attempts fail. Users cannot start donation flow or interact with keypad.

---

## 🐛 Error 1: DatabaseManager Missing Method

### Error Message
```
2025-11-13 21:54:52,466 - keypad_state_manager - ERROR - ❌ Failed to get state for user 6271402111: 'DatabaseManager' object has no attribute 'execute_query'
```

### Root Cause Analysis

**What I Did Wrong:**
1. Created `KeypadStateManager` class that calls `self.db_manager.execute_query(query, params)`
2. **NEVER verified that DatabaseManager has an `execute_query()` method**
3. Assumed the method existed without reading `database_manager.py`
4. Deployed to production without testing

**The Truth:**
DatabaseManager (`GCDonationHandler-10-26/database_manager.py`) has ONLY these methods:
- `__init__()`
- `_get_connection()` (private)
- `channel_exists()`
- `get_channel_details_by_open_id()`
- `fetch_all_closed_channels()`
- `close()`

**NO `execute_query()` method exists!**

### Existing Pattern in DatabaseManager

All methods follow this pattern:

```python
def some_method(self, param):
    try:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...", (param,))
                result = cur.fetchone()
                return result
    except psycopg2.Error as e:
        logger.error(f"❌ Error: {e}")
        return None
```

### What KeypadStateManager Does (WRONG)

```python
def get_state(self, user_id: int):
    query = "SELECT * FROM donation_keypad_state WHERE user_id = %s"
    result = self.db_manager.execute_query(query, (user_id,))  # ← METHOD DOESN'T EXIST!
    return result
```

### Impact

- ❌ `create_state()` - Cannot create state → Donation flow blocked at start
- ❌ `get_state()` - Cannot read state → "Session expired" errors
- ❌ `update_amount()` - Cannot update state → Keypad buttons don't work
- ❌ `delete_state()` - Cannot delete state → Stale states accumulate
- ❌ `cleanup_stale_states()` - Cannot cleanup → Memory leak in database

**Result:** Entire KeypadStateManager is non-functional.

---

## 🐛 Error 2: Telegram Client Event Loop

### Error Message
```
2025-11-13 21:54:45,503 - telegram_client - ERROR - ❌ Failed to send message to chat -1003016667267: Unknown error in HTTP implementation: RuntimeError('Event loop is closed')
```

### Root Cause Analysis

**What Happens:**
1. Flask request arrives → synchronous context
2. `telegram_client.send_message()` called
3. Method creates async function: `async def _send(): ...`
4. Method calls: `asyncio.run(_send())`
5. `asyncio.run()` creates event loop, runs coroutine, **closes loop**
6. Second Telegram call in same request tries to use closed loop → **CRASH**

**The Problem with `asyncio.run()`:**

```python
# telegram_client.py line 80-90
def send_message(self, chat_id, text, reply_markup=None):
    async def _send():
        message = await self.bot.send_message(...)
        return message

    message = asyncio.run(_send())  # ← CLOSES LOOP AFTER EXECUTION
    return {'success': True, 'message_id': message.message_id}
```

`asyncio.run()` is designed to be called **ONCE** as the main entry point of an async program. It:
1. Creates new event loop
2. Runs the coroutine
3. **Closes the loop** (this is the problem)
4. Returns result

When called multiple times in same request:
- First call: Creates loop → sends message → **closes loop** ✅
- Second call: Tries to use closed loop → **CRASH** ❌

### When This Fails

**Scenario 1: Start Donation Flow**
```python
# service.py /start-donation-input endpoint
keypad_handler.start_donation_input(user_id, chat_id, ...)
  └─> telegram_client.send_message(...)  # 1st call - creates & closes loop
      └─> telegram_client.answer_callback_query(...)  # 2nd call - CRASH
```

**Scenario 2: Keypad Interaction**
```python
# keypad_handler.py handle_keypad_input()
telegram_client.edit_message_reply_markup(...)  # 1st call - creates & closes loop
telegram_client.answer_callback_query(...)  # 2nd call - CRASH
```

### Impact

- ❌ Cannot send keypad to user
- ❌ Cannot update keypad display
- ❌ Cannot answer callback queries (Telegram shows loading spinner forever)
- ❌ Cannot send payment gateway link
- ❌ Cannot delete messages

**Result:** All Telegram operations fail after first call in request.

---

## 📋 Fix Strategy

### Fix 1: Refactor KeypadStateManager (Database Operations)

**Approach:** Match DatabaseManager's existing pattern

**Changes Required:**
- Remove ALL calls to `execute_query()`
- Use `self.db_manager._get_connection()` directly
- Implement proper connection and cursor handling in EACH method
- Follow existing pattern from `channel_exists()`, `get_channel_details_by_open_id()`, etc.

**Methods to Refactor:** 6 methods
1. `create_state()` - Lines 21-42
2. `get_state()` - Lines 44-74
3. `update_amount()` - Lines 76-96
4. `delete_state()` - Lines 98-113
5. `state_exists()` - Lines 115-122 (just calls get_state, no changes needed)
6. `cleanup_stale_states()` - Lines 124-139

**Estimated Time:** 45 minutes

**Example Refactor:**

```python
# BEFORE (broken):
def get_state(self, user_id: int) -> Optional[Dict[str, Any]]:
    try:
        query = """
            SELECT user_id, channel_id, current_amount, decimal_entered,
                   state_type, created_at, updated_at
            FROM donation_keypad_state
            WHERE user_id = %s
        """
        result = self.db_manager.execute_query(query, (user_id,))  # DOESN'T EXIST

        if result and len(result) > 0:
            row = result[0]
            return {
                'user_id': row[0],
                'amount_building': row[2],
                'open_channel_id': row[1],
                'decimal_entered': row[3],
                'state_type': row[4],
                'created_at': row[5],
                'updated_at': row[6]
            }
        return None
    except Exception as e:
        logger.error(f"❌ Failed to get state for user {user_id}: {e}")
        return None

# AFTER (fixed):
def get_state(self, user_id: int) -> Optional[Dict[str, Any]]:
    try:
        with self.db_manager._get_connection() as conn:  # ← USE _get_connection()
            with conn.cursor() as cur:                   # ← PROPER CURSOR HANDLING
                cur.execute(
                    """
                    SELECT user_id, channel_id, current_amount, decimal_entered,
                           state_type, created_at, updated_at
                    FROM donation_keypad_state
                    WHERE user_id = %s
                    """,
                    (user_id,)
                )
                result = cur.fetchone()

                if result:
                    return {
                        'user_id': result[0],
                        'amount_building': result[2],
                        'open_channel_id': result[1],
                        'decimal_entered': result[3],
                        'state_type': result[4],
                        'created_at': result[5],
                        'updated_at': result[6]
                    }
                return None
    except Exception as e:
        logger.error(f"❌ Failed to get state for user {user_id}: {e}")
        return None
```

---

### Fix 2: Refactor TelegramClient (Event Loop Handling)

**Approach:** Replace `asyncio.run()` with persistent event loop

**Changes Required:**
- Add `_run_async()` helper method
- Replace ALL `asyncio.run()` calls with `self._run_async()`
- Proper event loop detection and reuse

**Methods to Refactor:** 5 methods
1. `send_message()` - Line 90
2. `edit_message_reply_markup()` - Line 183
3. `delete_message()` - Line 227
4. `answer_callback_query()` - Line 280
5. `send_message_with_webapp_button()` - Already calls send_message(), no changes needed

**Estimated Time:** 30 minutes

**Implementation:**

```python
# ADD NEW METHOD to TelegramClient class:
def _run_async(self, coro):
    """
    Safely run async coroutine in Flask synchronous context.

    Handles event loop creation and reuse to avoid "Event loop is closed" errors.

    Args:
        coro: Async coroutine to execute

    Returns:
        Result of coroutine execution

    Raises:
        Exception: Any exception raised by the coroutine
    """
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            # Loop exists but is closed, create new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # No event loop in current thread, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run coroutine in the loop (doesn't close it)
    return loop.run_until_complete(coro)


# BEFORE (broken):
def send_message(self, chat_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        async def _send():
            message = await self.bot.send_message(...)
            return message

        message = asyncio.run(_send())  # ← CLOSES LOOP
        return {'success': True, 'message_id': message.message_id}
    except TelegramError as e:
        return {'success': False, 'error': str(e)}


# AFTER (fixed):
def send_message(self, chat_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        async def _send():
            message = await self.bot.send_message(...)
            return message

        message = self._run_async(_send())  # ← USES PERSISTENT LOOP
        return {'success': True, 'message_id': message.message_id}
    except TelegramError as e:
        return {'success': False, 'error': str(e)}
```

---

## 📝 Detailed Fix Checklist

### Phase 1: Code Fixes - KeypadStateManager

#### Task 1.1: Refactor `create_state()` Method
- [ ] Open `GCDonationHandler-10-26/keypad_state_manager.py`
- [ ] Locate `create_state()` method (lines 21-42)
- [ ] Replace `execute_query()` call with proper connection handling
- [ ] Test UPSERT logic (`INSERT ... ON CONFLICT DO UPDATE`)
- [ ] Save file

**New Implementation:**
```python
def create_state(self, user_id: int, channel_id: str, chat_id: int,
                 keypad_message_id: Optional[int] = None,
                 state_type: str = 'keypad_input') -> bool:
    try:
        with self.db_manager._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO donation_keypad_state
                    (user_id, channel_id, current_amount, decimal_entered, state_type, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        channel_id = EXCLUDED.channel_id,
                        current_amount = '0',
                        decimal_entered = false,
                        state_type = EXCLUDED.state_type,
                        updated_at = NOW()
                    """,
                    (user_id, channel_id, '0', False, state_type)
                )
                conn.commit()
                logger.debug(f"💾 Created state for user {user_id} (channel: {channel_id})")
                return True
    except Exception as e:
        logger.error(f"❌ Failed to create state for user {user_id}: {e}")
        return False
```

#### Task 1.2: Refactor `get_state()` Method
- [ ] Locate `get_state()` method (lines 44-74)
- [ ] Replace `execute_query()` with connection handling
- [ ] Verify column mapping to dictionary
- [ ] Save file

**(Implementation shown above in Fix 1 example)**

#### Task 1.3: Refactor `update_amount()` Method
- [ ] Locate `update_amount()` method (lines 76-96)
- [ ] Replace `execute_query()` with connection handling
- [ ] Ensure both `current_amount` and `decimal_entered` are updated
- [ ] Save file

```python
def update_amount(self, user_id: int, new_amount: str) -> bool:
    try:
        has_decimal = '.' in new_amount
        with self.db_manager._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE donation_keypad_state
                    SET current_amount = %s, decimal_entered = %s, updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (new_amount, has_decimal, user_id)
                )
                conn.commit()
                logger.debug(f"💾 Updated amount for user {user_id}: {new_amount}")
                return True
    except Exception as e:
        logger.error(f"❌ Failed to update amount for user {user_id}: {e}")
        return False
```

#### Task 1.4: Refactor `delete_state()` Method
- [ ] Locate `delete_state()` method (lines 98-113)
- [ ] Replace `execute_query()` with connection handling
- [ ] Save file

```python
def delete_state(self, user_id: int) -> bool:
    try:
        with self.db_manager._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM donation_keypad_state WHERE user_id = %s",
                    (user_id,)
                )
                conn.commit()
                logger.debug(f"🗑️ Deleted state for user {user_id}")
                return True
    except Exception as e:
        logger.error(f"❌ Failed to delete state for user {user_id}: {e}")
        return False
```

#### Task 1.5: Refactor `cleanup_stale_states()` Method
- [ ] Locate `cleanup_stale_states()` method (lines 124-139)
- [ ] Replace `execute_query()` with connection handling
- [ ] Call database function `cleanup_stale_donation_states()`
- [ ] Return count of deleted states
- [ ] Save file

```python
def cleanup_stale_states(self, max_age_hours: int = 1) -> int:
    try:
        with self.db_manager._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT cleanup_stale_donation_states()")
                deleted_count = cur.fetchone()[0]
                conn.commit()
                logger.info(f"🧹 Cleaned up {deleted_count} stale donation states (older than {max_age_hours}h)")
                return deleted_count
    except Exception as e:
        logger.error(f"❌ Failed to cleanup stale states: {e}")
        return 0
```

#### Task 1.6: Verify Syntax
- [ ] Run syntax check:
  ```bash
  cd GCDonationHandler-10-26
  python3 -m py_compile keypad_state_manager.py
  ```
- [ ] Verify no errors

---

### Phase 2: Code Fixes - TelegramClient

#### Task 2.1: Add `_run_async()` Helper Method
- [ ] Open `GCDonationHandler-10-26/telegram_client.py`
- [ ] Add new method after `__init__()` (around line 48)
- [ ] Save file

**(Implementation shown above in Fix 2)**

#### Task 2.2: Refactor `send_message()` Method
- [ ] Locate `send_message()` method (line 49-96)
- [ ] Find `asyncio.run(_send())` call (line 90)
- [ ] Replace with `self._run_async(_send())`
- [ ] Save file

#### Task 2.3: Refactor `edit_message_reply_markup()` Method
- [ ] Locate method (line 147-197)
- [ ] Find `asyncio.run(_edit())` call (line 183)
- [ ] Replace with `self._run_async(_edit())`
- [ ] Save file

#### Task 2.4: Refactor `delete_message()` Method
- [ ] Locate method (line 199-241)
- [ ] Find `asyncio.run(_delete())` call (line 227)
- [ ] Replace with `self._run_async(_delete())`
- [ ] Save file

#### Task 2.5: Refactor `answer_callback_query()` Method
- [ ] Locate method (line 243-286)
- [ ] Find `asyncio.run(_answer())` call (line 280)
- [ ] Replace with `self._run_async(_answer())`
- [ ] Save file

#### Task 2.6: Verify Syntax
- [ ] Run syntax check:
  ```bash
  python3 -m py_compile telegram_client.py
  ```
- [ ] Verify no errors

---

### Phase 3: Testing & Deployment

#### Task 3.1: Build Docker Image
- [ ] Navigate to directory:
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCDonationHandler-10-26
  ```
- [ ] Build and submit:
  ```bash
  gcloud builds submit --tag gcr.io/telepay-459221/gcdonationhandler-10-26
  ```
- [ ] Wait for build to complete (~3 minutes)
- [ ] Verify build SUCCESS

#### Task 3.2: Deploy to Cloud Run
- [ ] Deploy service:
  ```bash
  gcloud run deploy gcdonationhandler-10-26 \
    --image gcr.io/telepay-459221/gcdonationhandler-10-26 \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql
  ```
- [ ] Wait for deployment (~2 minutes)
- [ ] Note revision name
- [ ] Verify 100% traffic

#### Task 3.3: Verify Health Check
- [ ] Test health endpoint:
  ```bash
  curl https://gcdonationhandler-10-26-291176869049.us-central1.run.app/health
  ```
- [ ] Expected: `{"status": "healthy", "service": "GCDonationHandler", "version": "1.0"}`

#### Task 3.4: Check Startup Logs
- [ ] Query logs:
  ```bash
  gcloud logging read \
    'resource.type="cloud_run_revision"
     resource.labels.service_name="gcdonationhandler-10-26"
     "KeypadStateManager initialized"' \
    --limit=5
  ```
- [ ] Verify: "🗄️ KeypadStateManager initialized (database-backed)"
- [ ] Verify: NO "execute_query" errors
- [ ] Verify: Service started successfully

#### Task 3.5: End-to-End Donation Flow Test
- [ ] User clicks "💝 Donate" button in closed channel
- [ ] **EXPECTED:** Keypad appears in DM within 2 seconds
- [ ] **EXPECTED:** Keypad shows "$0.00"
- [ ] User presses digit "5"
- [ ] **EXPECTED:** Display updates to "$5.00"
- [ ] User presses "." (decimal)
- [ ] **EXPECTED:** Display updates to "$5."
- [ ] User presses "0", "0"
- [ ] **EXPECTED:** Display updates to "$5.00"
- [ ] User presses "Confirm"
- [ ] **EXPECTED:** Payment gateway link appears
- [ ] **EXPECTED:** NO "session expired" errors
- [ ] **EXPECTED:** NO "event loop" errors in logs

#### Task 3.6: Verify No Errors in Logs
- [ ] Query for errors:
  ```bash
  gcloud logging read \
    'resource.type="cloud_run_revision"
     resource.labels.service_name="gcdonationhandler-10-26"
     severity>=ERROR
     timestamp>="2025-11-13T22:00:00Z"' \
    --limit=50
  ```
- [ ] Verify: NO "execute_query" errors
- [ ] Verify: NO "Event loop is closed" errors
- [ ] Verify: NO "Failed to get state" errors
- [ ] Verify: NO "Failed to send message" errors

---

## ✅ Success Criteria

### Must Pass (CRITICAL)
- [ ] Keypad appears when user clicks "Donate" button
- [ ] Keypad display updates as user presses digits
- [ ] Confirm button creates payment invoice
- [ ] NO "execute_query" errors in logs
- [ ] NO "Event loop is closed" errors in logs
- [ ] NO "Session expired" errors during keypad use
- [ ] All Telegram operations succeed (send, edit, answer callback)

### Should Pass (IMPORTANT)
- [ ] Response time < 3 seconds for keypad appearance
- [ ] State persists across multiple button presses
- [ ] Database connections are properly closed (no leaks)
- [ ] Logs are clean and informative

### Nice to Have
- [ ] Cleanup function runs and removes stale states
- [ ] Service handles 10+ concurrent users without issues

---

## 🔍 Why These Errors Happened

### Lessons Learned

**1. Assumed API without verification**
- I created `KeypadStateManager` calling `db_manager.execute_query()`
- **Never read `database_manager.py` to verify method exists**
- Deployed to production without local testing
- **Prevention:** ALWAYS read existing modules BEFORE creating dependencies

**2. Copied async pattern without understanding**
- Used `asyncio.run()` because it "looked right"
- **Did not understand that it closes the event loop**
- Did not test multiple Telegram calls in same request
- **Prevention:** Test critical paths before deploying

**3. No functional testing before deployment**
- Deployed based on health check only
- **Health check doesn't test actual functionality**
- Should have tested donation flow end-to-end
- **Prevention:** Add functional tests to deployment checklist

**4. Pattern mismatched**
- DatabaseManager uses `_get_connection()` context manager pattern
- KeypadStateManager assumed `execute_query()` exists
- **Should have matched existing pattern from the start**
- **Prevention:** Follow existing codebase patterns (pattern matching > innovation)

---

## 🎯 Estimated Fix Time

- **Phase 1 (KeypadStateManager):** 45 minutes
  - 6 methods to refactor
  - Straightforward pattern replacement
- **Phase 2 (TelegramClient):** 30 minutes
  - 1 new method + 4 method updates
  - Simple replacement of `asyncio.run()`
- **Phase 3 (Build & Deploy):** 20 minutes
  - Docker build: ~3 minutes
  - Cloud Run deploy: ~2 minutes
  - Testing & verification: ~15 minutes

**Total: ~95 minutes (~1.5 hours)**

---

## 📄 Files to Modify

1. `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCDonationHandler-10-26/keypad_state_manager.py`
   - Refactor 5 methods (create_state, get_state, update_amount, delete_state, cleanup_stale_states)

2. `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCDonationHandler-10-26/telegram_client.py`
   - Add 1 new method (_run_async)
   - Modify 4 existing methods (send_message, edit_message_reply_markup, delete_message, answer_callback_query)

3. **NO** changes needed to:
   - `service.py` (already correct)
   - `keypad_handler.py` (already correct)
   - `database_manager.py` (already correct)
   - `Dockerfile` (already includes keypad_state_manager.py)

---

## 📊 Risk Assessment

**Risk Level:** 🟡 LOW-MEDIUM

**Why Low Risk:**
- Changes are isolated to 2 files
- No database schema changes
- No API contract changes
- No changes to other services
- Easy to verify with functional tests
- Easy to rollback if needed

**Rollback Plan:**
```bash
# Get previous working revision (before stateless keypad)
PREVIOUS_REVISION="gcdonationhandler-10-26-00004-xxx"  # Update with actual

# Rollback
gcloud run services update-traffic gcdonationhandler-10-26 \
  --region=us-central1 \
  --to-revisions=$PREVIOUS_REVISION=100
```

---

## 🚀 Next Steps

**AWAITING USER APPROVAL**

Please review this analysis and approve the fix strategy before I proceed with implementation.

**Questions to Confirm:**
1. Do you agree with the root cause analysis?
2. Do you approve the proposed fix approach?
3. Should I proceed with implementation immediately?
4. Any concerns about the estimated time or risk level?

**Once approved, I will:**
1. Execute Phase 1 (KeypadStateManager fixes)
2. Execute Phase 2 (TelegramClient fixes)
3. Execute Phase 3 (Build, deploy, test)
4. Update PROGRESS.md, DECISIONS.md, BUGS.md
5. Report results with full test validation

---

**Document Prepared By:** Claude Code
**Status:** ✅ READY FOR USER APPROVAL
**Last Updated:** 2025-11-13
