# Event Loop Closure Bug - Fix Checklist

**Issue:** `RuntimeError('Event loop is closed')` on second notification request
**Service:** GCNotificationService-10-26
**Root Cause:** Event loop is created, used, and closed for each request, causing failure on subsequent requests
**Date:** 2025-11-14

---

## Problem Analysis

### Logs Evidence:
```
2025-11-14 14:13:24 - ✅ [REQUEST] Notification sent successfully (FIRST REQUEST - SUCCESS)
2025-11-14 14:25:43 - ❌ [TELEGRAM] Telegram API error: RuntimeError('Event loop is closed') (SECOND REQUEST - FAILURE)
```

### Root Cause:
**File:** `telegram_client.py`
**Lines:** 53-65

```python
# PROBLEMATIC CODE:
loop = asyncio.new_event_loop()     # Creates NEW loop
asyncio.set_event_loop(loop)         # Sets as current
loop.run_until_complete(...)         # Runs async operation
loop.close()                         # CLOSES loop (BUG!)
```

**Why This Fails:**
1. **First request (14:13:24):** Creates loop → Uses it → Closes it ✅
2. **Second request (14:25:43):** Tries to create new loop, but asyncio internals may still reference the closed loop ❌
3. Python's asyncio module can have stale references to closed loops in WSGI/Flask contexts

---

## Solution Options

### ⭐ Option 1: Reuse Single Event Loop (RECOMMENDED)
**Approach:** Create one event loop during TelegramClient initialization, reuse for all requests
**Pros:** Clean, efficient, follows asyncio best practices
**Cons:** Need to ensure loop stays open for service lifetime

### Option 2: Use nest_asyncio (ALTERNATIVE)
**Approach:** Allow nested event loops using `nest_asyncio.apply()`
**Pros:** Quick fix, no major refactoring
**Cons:** Adds dependency, doesn't address root issue

### Option 3: Use synchronous telegram library (NOT RECOMMENDED)
**Approach:** Switch to `python-telegram-bot` < 20.x or requests-based approach
**Cons:** Outdated library, loses async benefits

**DECISION:** Use Option 1 (Reuse Single Event Loop)

---

## Implementation Checklist

### Phase 1: Backup Current Implementation ✅

- [ ] Create backup of `telegram_client.py`
  ```bash
  cp /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCNotificationService-10-26/telegram_client.py \
     /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCNotificationService-10-26/telegram_client.py.backup-$(date +%Y%m%d-%H%M%S)
  ```

### Phase 2: Fix TelegramClient Class ✅

- [ ] **Update `__init__` method** to create persistent event loop
  - Create event loop during initialization
  - Store as instance variable `self.loop`
  - Keep loop open for service lifetime

- [ ] **Update `send_message` method** to reuse existing loop
  - Remove `asyncio.new_event_loop()` creation
  - Remove `asyncio.set_event_loop()` call
  - Remove `loop.close()` call
  - Use `self.loop.run_until_complete()` instead

- [ ] **Add cleanup method** for graceful shutdown
  - Add `close()` method to close loop on shutdown
  - Document when to call (app teardown)

### Phase 3: Update Service Initialization ✅

- [ ] **No changes needed to `service.py`**
  - TelegramClient interface remains the same
  - Flask app will automatically handle lifecycle

### Phase 4: Add Error Handling ✅

- [ ] **Add loop status checks**
  - Check if loop is running before use
  - Handle edge case if loop gets closed unexpectedly
  - Re-create loop if needed (defensive programming)

### Phase 5: Testing ✅

- [ ] **Local testing**
  - Test first notification
  - Test second notification (verify no "Event loop is closed")
  - Test rapid successive notifications

- [ ] **Deploy to Cloud Run**
  - Deploy updated service
  - Monitor logs for event loop errors
  - Verify consecutive notifications work

### Phase 6: Verification ✅

- [ ] **Monitor production logs**
  - Watch for `Event loop is closed` errors
  - Verify multiple notifications to same channel work
  - Check performance (loop reuse should be faster)

- [ ] **Load testing**
  - Send 10 consecutive notifications
  - Verify all succeed without event loop errors

---

## Code Changes Required

### File: `telegram_client.py`

**BEFORE (BROKEN):**
```python
def send_message(self, chat_id: int, text: str, ...) -> bool:
    try:
        logger.info(f"📤 [TELEGRAM] Sending message to chat_id {chat_id}")

        # Use synchronous wrapper for python-telegram-bot >= 20.x
        loop = asyncio.new_event_loop()     # ❌ Creates new loop every time
        asyncio.set_event_loop(loop)         # ❌ Sets as current

        loop.run_until_complete(
            self.bot.send_message(...)
        )

        loop.close()                         # ❌ CLOSES LOOP (BUG!)

        logger.info(f"✅ [TELEGRAM] Message delivered to {chat_id}")
        return True
    except Exception as e:
        ...
```

**AFTER (FIXED):**
```python
class TelegramClient:
    def __init__(self, bot_token: str):
        if not bot_token:
            raise ValueError("Bot token is required")

        self.bot = Bot(token=bot_token)

        # ✅ Create persistent event loop (reused for all requests)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        logger.info("🤖 [TELEGRAM] Client initialized with persistent event loop")

    def send_message(self, chat_id: int, text: str, ...) -> bool:
        try:
            logger.info(f"📤 [TELEGRAM] Sending message to chat_id {chat_id}")

            # ✅ Reuse persistent event loop (no create/close)
            self.loop.run_until_complete(
                self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
            )

            # ✅ DO NOT CLOSE LOOP - keep for next request

            logger.info(f"✅ [TELEGRAM] Message delivered to {chat_id}")
            return True
        except Exception as e:
            ...

    def close(self):
        """Close event loop on service shutdown (call in teardown)"""
        if self.loop and not self.loop.is_closed():
            self.loop.close()
            logger.info("🔒 [TELEGRAM] Event loop closed")
```

---

## Deployment Steps

### 1. Update Code
```bash
# Navigate to service directory
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCNotificationService-10-26

# Apply fix to telegram_client.py
# (Claude Code will do this in next step)
```

### 2. Deploy to Cloud Run
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/telepay-459221/gcnotificationservice-10-26 && \
gcloud run deploy gcnotificationservice-10-26 \
  --image gcr.io/telepay-459221/gcnotificationservice-10-26 \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars="TELEGRAM_BOT_SECRET_NAME=projects/291176869049/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest,TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest,DATABASE_HOST_SECRET=projects/291176869049/secrets/DATABASE_HOST_SECRET/versions/latest,DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest,DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest,DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest,CLOUD_SQL_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql" \
  --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql
```

### 3. Verify Deployment
```bash
# Check service health
curl https://gcnotificationservice-10-26-291176869049.us-central1.run.app/health

# Expected: {"status":"healthy","service":"GCNotificationService","version":"1.0"}
```

### 4. Test Consecutive Notifications
```bash
# Send first notification
curl -X POST https://gcnotificationservice-10-26-291176869049.us-central1.run.app/send-notification \
  -H "Content-Type: application/json" \
  -d '{
    "open_channel_id": "-1003202734748",
    "payment_type": "subscription",
    "payment_data": {
      "user_id": 6271402111,
      "amount_crypto": "0.001",
      "amount_usd": "2.50",
      "crypto_currency": "ETH",
      "tier": 1,
      "tier_price": "2.50",
      "duration_days": 30,
      "timestamp": "2025-11-14 14:30:00 UTC"
    }
  }'

# Expected: {"status":"success","message":"Notification sent successfully"}

# Send second notification (THIS SHOULD NOW WORK)
curl -X POST https://gcnotificationservice-10-26-291176869049.us-central1.run.app/send-notification \
  -H "Content-Type: application/json" \
  -d '{
    "open_channel_id": "-1003202734748",
    "payment_type": "donation",
    "payment_data": {
      "user_id": 6271402111,
      "amount_crypto": "0.0005",
      "amount_usd": "1.25",
      "crypto_currency": "ETH",
      "timestamp": "2025-11-14 14:31:00 UTC"
    }
  }'

# Expected: {"status":"success","message":"Notification sent successfully"}
# NOT: Event loop is closed error
```

### 5. Monitor Logs
```bash
# Watch Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcnotificationservice-10-26" \
  --limit 50 \
  --format "table(timestamp, textPayload)" \
  --freshness=10m

# Look for:
# ✅ "Message delivered to 6271402111"
# ❌ NO "Event loop is closed" errors
```

---

## Success Criteria

- ✅ First notification sends successfully
- ✅ Second notification sends successfully (NO event loop error)
- ✅ Third, fourth, fifth notifications all succeed
- ✅ Logs show "Message delivered" for all requests
- ✅ No "RuntimeError: Event loop is closed" in logs
- ✅ Service remains stable under load

---

## Rollback Plan

If fix causes issues:

```bash
# Restore backup
cp /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCNotificationService-10-26/telegram_client.py.backup-* \
   /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCNotificationService-10-26/telegram_client.py

# Redeploy old version
gcloud builds submit --tag gcr.io/telepay-459221/gcnotificationservice-10-26 && \
gcloud run deploy gcnotificationservice-10-26 \
  --image gcr.io/telepay-459221/gcnotificationservice-10-26 \
  --region us-central1
```

---

## Post-Deployment Monitoring

### Week 1: Intensive Monitoring
- Check logs daily for event loop errors
- Monitor notification success rate
- Verify no performance degradation

### Week 2-4: Standard Monitoring
- Weekly log review
- Alert on any event loop errors
- Track notification delivery metrics

---

**Status:** ⏳ PENDING IMPLEMENTATION
**Priority:** 🔴 HIGH (Production Bug)
**Estimated Time:** 30 minutes (implementation + deployment)
**Risk Level:** 🟢 LOW (Simple fix, backward compatible)

---

**END OF CHECKLIST**
