# Bug Tracker - TelegramFunnel NOVEMBER/PGP_v1

**Last Updated:** 2025-11-16 - OWASP Security Analysis

---

## Active Security Vulnerabilities

## 2025-11-16: 🔴 CRITICAL - 73 Security Vulnerabilities Identified (OWASP Top 10 2021)

**Severity:** 🔴 CRITICAL (Payment System Security)
**Status:** 🔴 ACTIVE - Requires immediate remediation
**Source:** OWASP Top 10 2021 Security Analysis
**Report:** `SECURITY_VULNERABILITY_ANALYSIS_OWASP_VERIFICATION.md`

**Vulnerability Summary:**
- **Total:** 73 vulnerabilities across 7 OWASP categories
- **Critical:** 15 vulnerabilities requiring 0-7 day remediation (P1)
- **High:** 18 vulnerabilities requiring 30-day remediation (P2)
- **Medium:** 25 vulnerabilities requiring 90-day remediation (P3)
- **Low:** 15 vulnerabilities requiring 180-day remediation (P4)

**Top 8 NEW Critical Vulnerabilities (Not Previously Identified):**

### 1. 🔴 Missing Wallet Address Validation (FUND THEFT RISK)
**OWASP:** A03:2021 - Injection
**Severity:** CRITICAL
**Impact:** Payments sent to invalid addresses = permanent fund loss
**Location:** Payment processing across all services
**Fix:** Implement EIP-55 checksum validation for Ethereum addresses
**Priority:** P1 (0-7 days)
```python
# REQUIRED: Validate wallet addresses with EIP-55 checksum
from web3 import Web3
if not Web3.is_checksum_address(wallet_address):
    raise ValueError("Invalid wallet address")
```

### 2. 🔴 No Transaction Amount Limits (FRAUD/MONEY LAUNDERING RISK)
**OWASP:** A04:2021 - Insecure Design
**Severity:** CRITICAL
**Impact:** Unlimited transaction amounts enable fraud and money laundering
**Compliance:** PCI DSS 11.3, SOC 2 CC6.1, FINRA 3310 violation
**Location:** Payment processing layer
**Fix:** Implement configurable transaction limits (daily, per-transaction)
**Priority:** P1 (0-7 days)

### 3. 🔴 IP Spoofing via X-Forwarded-For (ACCESS CONTROL BYPASS)
**OWASP:** A01:2021 - Broken Access Control
**Severity:** CRITICAL
**Impact:** Attackers can bypass IP whitelist by spoofing X-Forwarded-For header
**Location:** `PGP_SERVER_v1/security/ip_whitelist.py`
**Current Code:**
```python
client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
if ',' in client_ip:
    client_ip = client_ip.split(',')[0].strip()  # ❌ VULNERABLE
```
**Fix:** Trust only Cloud Run's rightmost X-Forwarded-For IP or use static IPs with Cloud NAT
**Priority:** P1 (0-7 days)

### 4. 🔴 Replay Attacks - No Nonce Tracking (DUPLICATE PAYMENT PROCESSING)
**OWASP:** A07:2021 - Authentication Failures
**Severity:** CRITICAL
**Impact:** 5-minute timestamp window allows replay attacks
**Location:** `PGP_SERVER_v1/security/hmac_auth.py`
**Current:** Only timestamp validation (300-second window)
**Fix:** Implement Redis-based nonce tracking with 5-minute TTL
**Priority:** P1 (0-7 days)

### 5. 🔴 Race Conditions in Payment Processing (DUPLICATE SUBSCRIPTIONS)
**OWASP:** A04:2021 - Insecure Design
**Severity:** CRITICAL
**Impact:** Concurrent requests can create duplicate subscription records
**Location:** `PGP_ORCHESTRATOR_v1/database_manager.py` - `record_private_channel_user()`
**Current:** UPDATE then INSERT pattern without locking
**Fix:** Use `SELECT FOR UPDATE` or PostgreSQL UPSERT
**Priority:** P1 (0-7 days)

### 6. 🔴 Missing Fraud Detection System (COMPLIANCE VIOLATION)
**OWASP:** A04:2021 - Insecure Design
**Severity:** CRITICAL
**Impact:** No fraud detection = PCI DSS, SOC 2, FINRA non-compliance
**Compliance:** PCI DSS 11.4, SOC 2 CC7.2, FINRA 3310 required
**Location:** All payment processing services
**Fix:** Implement fraud detection with anomaly detection, velocity checks
**Priority:** P1 (0-7 days)

### 7. 🔴 No Webhook Signature Expiration (EXTENDED REPLAY WINDOW)
**OWASP:** A07:2021 - Authentication Failures
**Severity:** HIGH (escalates to CRITICAL without nonce tracking)
**Impact:** Valid signatures can be replayed within 5-minute window
**Location:** `PGP_SERVER_v1/security/hmac_auth.py`
**Current:** Timestamp validation only, no signature expiration
**Fix:** Add signature expiration + nonce tracking
**Priority:** P1 (0-7 days)

### 8. 🟡 Missing Database Connection Pooling Limits (DOS RISK)
**OWASP:** A04:2021 - Insecure Design
**Severity:** MEDIUM
**Impact:** Unbounded connection pools can exhaust database resources
**Location:** `PGP_COMMON/database/db_manager.py`
**Fix:** Configure max_overflow and pool_size limits in SQLAlchemy
**Priority:** P3 (90 days)

**Additional Critical Findings:**
- Missing mTLS for service-to-service communication (P2)
- No RBAC implementation (P2)
- Missing SIEM integration (P2)
- No security headers (CSP, HSTS, X-Frame-Options) (P2)
- HTTPS not enforced (P2)
- Password hashing using bcrypt instead of Argon2id (P3)
- Missing idempotency keys (P3)
- No input validation framework (P3)
- No automated vulnerability scanning (P4)
- Incomplete log sanitization (P4)

**Compliance Impact:**
- **PCI DSS 3.2.1:** NON-COMPLIANT (6 violations)
- **SOC 2 Type II:** NON-COMPLIANT (8 control gaps)
- **OWASP ASVS Level 2:** 60% compliant (40% gap)

**Remediation Timeline:**
- **P1 (0-7 days):** 5 critical fixes started
- **P2 (30 days):** 5 high-priority fixes planned
- **P3 (90 days):** 5 medium-priority fixes scheduled
- **P4 (180 days):** 3 low-priority fixes queued

**Next Steps:**
1. Review full analysis: `SECURITY_VULNERABILITY_ANALYSIS_OWASP_VERIFICATION.md`
2. Prioritize P1 fixes (IP spoofing, nonce tracking, wallet validation, race conditions, limits)
3. Create implementation plan for each remediation
4. Schedule penetration testing after P1/P2 fixes
5. Begin PCI DSS compliance certification process

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

