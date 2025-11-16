# Bug Tracker - TelegramFunnel NOVEMBER/PGP_v1

**Last Updated:** 2025-11-14 Session 157

---

## Recently Resolved

## 2025-11-14 Session 157: ✅ RESOLVED - Flask JSON Parsing Errors (415 & 400)

**Severity:** 🔴 CRITICAL - Production service errors blocking Cloud Scheduler
**Status:** ✅ RESOLVED (Deployed in pgp_broadcastscheduler-10-26-00020-j6n)
**Service:** PGP_BROADCAST_v1
**Endpoint:** `POST /api/broadcast/execute`

**Error 1: 415 Unsupported Media Type**
```
2025-11-14 23:46:36,016 - main - ERROR - ❌ Error executing broadcasts: 415 Unsupported Media Type: Did not attempt to load JSON data because the request Content-Type was not 'application/json'.

Traceback (most recent call last):
  File "/app/pgp_broadcast_v1.py", line 143, in execute_broadcasts
    data = request.get_json() or {}
  File "/usr/local/lib/python3.11/site-packages/werkzeug/wrappers/request.py", line 604, in get_json
    return self.on_json_loading_failed(None)
  File "/usr/local/lib/python3.11/site-packages/flask/wrappers.py", line 130, in on_json_loading_failed
    return super().on_json_loading_failed(e)
  File "/usr/local/lib/python3.11/site-packages/werkzeug/wrappers/request.py", line 647, in on_json_loading_failed
    raise UnsupportedMediaType(
werkzeug.exceptions.UnsupportedMediaType: 415 Unsupported Media Type
```

**Error 2: 400 Bad Request - JSON Decode Error**
```
2025-11-14 23:46:40,515 - main - ERROR - ❌ Error executing broadcasts: 400 Bad Request: The browser (or proxy) sent a request that this server could not understand.

Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/werkzeug/wrappers/request.py", line 611, in get_json
    rv = self.json_module.loads(data)
  File "/usr/local/lib/python3.11/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
  File "/usr/local/lib/python3.11/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
  File "/usr/local/lib/python3.11/json/decoder.py", line 355, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Root Cause:**
- Flask's default `request.get_json()` raises exceptions instead of returning `None`
- **Error 1 Trigger**: Missing or incorrect `Content-Type` header (manual tests, proxy issues)
- **Error 2 Trigger**: Empty request body or malformed JSON with correct `Content-Type` header
- Cloud Scheduler was configured correctly, but endpoint couldn't handle edge cases

**Affected Code:**
- File: `PGP_BROADCAST_v1/pgp_broadcast_v1.py`
- Location: Line 143 in `execute_broadcasts()` function

**Before (Problematic):**
```python
try:
    # Get optional source from request body
    data = request.get_json() or {}  # ❌ Raises exceptions
    source = data.get('source', 'unknown')
```

**After (Fixed):**
```python
try:
    # Get optional source from request body
    # Use force=True to handle Content-Type issues (proxies/gateways)
    # Use silent=True to return None instead of raising exceptions on parse errors
    data = request.get_json(force=True, silent=True) or {}  # ✅ Returns None on errors
    source = data.get('source', 'unknown')

    logger.info(f"🎯 Broadcast execution triggered by: {source}")
    logger.debug(f"📦 Request data: {data}")
```

**Fix Explanation:**
1. `force=True`: Parse JSON regardless of Content-Type header
   - Solves Error 1 (415 Unsupported Media Type)
   - Handles missing/incorrect Content-Type headers gracefully

2. `silent=True`: Return `None` instead of raising exceptions on parse errors
   - Solves Error 2 (400 Bad Request)
   - Handles empty body and malformed JSON gracefully

3. `or {}`: Fallback to empty dictionary for safe access
   - Ensures `data.get('source', 'unknown')` never fails

**Testing Performed:**
1. ✅ **Test 1**: Request without Content-Type header
   - Before: 415 Unsupported Media Type ❌
   - After: HTTP 200 ✅

2. ✅ **Test 2**: Request with Content-Type but empty body
   - Before: 400 Bad Request ❌
   - After: HTTP 200 ✅

3. ✅ **Test 3**: Request with proper JSON payload
   - Before: HTTP 200 ✅
   - After: HTTP 200 ✅

4. ✅ **Test 4**: Cloud Scheduler manual trigger
   - Before: Intermittent failures ❌
   - After: HTTP 200 with "cloud_scheduler" source logged ✅

**Verification Logs:**
```
2025-11-14 23:56:39,000 - main - INFO - 🎯 Broadcast execution triggered by: cloud_scheduler
2025-11-14 23:56:39,000 - main - INFO - 📋 Fetching due broadcasts...
2025-11-14 23:56:39,060 - main - INFO - ✅ No broadcasts due at this time
2025-11-14 23:56:39,060 - main - INFO - 📮 POST /api/broadcast/execute -> 200
```

**Impact:**
- ✅ Cloud Scheduler executing successfully every 5 minutes
- ✅ Manual API testing now works regardless of headers
- ✅ Production errors eliminated
- ✅ Endpoint robust to proxy/gateway header modifications

**Prevention for Future:**
- Apply `request.get_json(force=True, silent=True)` pattern to ALL API endpoints
- Document pattern in DECISIONS.md for team reference
- Review other services: PGP_NOTIFICATIONS, GCHostPay, TelePay webhooks

**Related Documentation:**
- ✅ `DECISIONS.md`: Added Flask JSON handling best practice decision
- ✅ `PROGRESS.md`: Added implementation details and testing results
- ✅ Flask Documentation: Verified pattern via Context7 MCP research

---

## 2025-11-14 Session 156: ✅ RESOLVED - Missing Environment Variables (3 Total)

**Severity:** 🟡 HIGH - Service initialization errors and warnings
**Status:** ✅ RESOLVED (Deployed in pgp_broadcastscheduler-10-26-00019-nzk)
**Service:** PGP_BROADCAST_v1
**Errors:**
1. `Environment variable BOT_USERNAME_SECRET not set and no default provided`
2. `Environment variable BROADCAST_MANUAL_INTERVAL_SECRET not set, using default`
3. `Environment variable BROADCAST_AUTO_INTERVAL_SECRET not set, using default`

**Symptom:**
```
config_manager - ERROR - ❌ Error fetching secret BOT_USERNAME_SECRET: Environment variable BOT_USERNAME_SECRET not set
config_manager - WARNING - ⚠️ Environment variable BROADCAST_MANUAL_INTERVAL_SECRET not set, using default
config_manager - WARNING - ⚠️ Environment variable BROADCAST_AUTO_INTERVAL_SECRET not set, using default
```

**Root Cause:**
- Incomplete review of `config_manager.py` - only identified 8 of 10 required environment variables
- `BOT_USERNAME_SECRET` was missing entirely (initially pointed to wrong secret: `BOT_USERNAME` instead of `TELEGRAM_BOT_USERNAME`)
- `BROADCAST_AUTO_INTERVAL_SECRET` and `BROADCAST_MANUAL_INTERVAL_SECRET` were not included in deployment

**Fix Applied:**
```bash
# Missing variables (3):
BOT_USERNAME_SECRET=projects/telepay-459221/secrets/TELEGRAM_BOT_USERNAME/versions/latest
BROADCAST_AUTO_INTERVAL_SECRET=projects/telepay-459221/secrets/BROADCAST_AUTO_INTERVAL/versions/latest
BROADCAST_MANUAL_INTERVAL_SECRET=projects/telepay-459221/secrets/BROADCAST_MANUAL_INTERVAL/versions/latest
```

**Solution:**
1. ✅ Read ENTIRE `config_manager.py` file to identify ALL 10 environment variable calls
2. ✅ Referenced `SECRET_CONFIG.md` for correct secret name mappings
3. ✅ Deployed service with complete set of 10 environment variables
4. ✅ Verified no errors or warnings in logs

**Verification:**
```
2025-11-14 23:46:02 - config_manager - INFO - 🤖 Bot username: @PayGatePrime_bot
2025-11-14 23:46:02 - telegram_client - INFO - 🤖 TelegramClient initialized for @PayGatePrime_bot
2025-11-14 23:46:02 - main - INFO - ✅ All components initialized successfully
```
(No warnings about BROADCAST intervals)

**Documentation Updated:**
- ✅ `DECISIONS.md`: Added complete 10-variable secret mapping reference table
- ✅ `CON_CURSOR_CLEANUP_PROGRESS.md`: Updated deployment section with all 10 variables
- ✅ `PROGRESS.md`: Updated with complete environment variable fix details

---

