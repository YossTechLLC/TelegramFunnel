# Logging Best Practices - PGP_v1

## Overview

This document defines logging standards and best practices for all PGP_v1 services to ensure consistent, production-ready logging.

**Security Issue**: Issue 3 - Debug Logging in Production (MEDIUM Priority)
**Status**: IN PROGRESS
**Date**: 2025-11-16

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Logging Standards](#logging-standards)
3. [Implementation Guide](#implementation-guide)
4. [Log Levels](#log-levels)
5. [Production Configuration](#production-configuration)
6. [Migration Guide](#migration-guide)
7. [Examples](#examples)
8. [Monitoring](#monitoring)

---

## Problem Statement

### Security Risk: Debug Logging in Production

**Issue**: Many PGP_v1 services use `print()` statements for debugging, which:
- Cannot be disabled in production (always outputs to stdout)
- Lacks log level control (DEBUG, INFO, WARNING, ERROR)
- May leak sensitive information in production logs
- Creates noise in Cloud Logging
- No structured logging for analysis

**Example - BEFORE (Insecure)**:
```python
# PGP_WEBAPI_v1/pgp_webapi_v1.py:93-94
print(f"🔍 CORS Debug - Origin: {origin}, Allowed origins: {cors_origins}")
print(f"🔍 Response headers: {dict(response.headers)}")
```

**Problems**:
- Always logs, even in production
- Exposes CORS configuration details
- Exposes response headers for every request
- Creates log spam (millions of log entries)
- **Risk**: Information disclosure

**Example - AFTER (Secure)**:
```python
logger.debug(f"🔍 [CORS] Origin: {origin}, Allowed origins: {cors_origins}")
logger.debug(f"🔍 [CORS] Response headers: {dict(response.headers)}")
```

**Benefits**:
- Controlled by `LOG_LEVEL` environment variable
- Production: `LOG_LEVEL=INFO` (debug logs suppressed)
- Development: `LOG_LEVEL=DEBUG` (full verbosity)
- Structured logging with timestamps, log levels, module names

---

## Logging Standards

### Rule 1: NEVER use `print()` in production code

**BAD**:
```python
print(f"🔍 Debug info: {variable}")
print("Processing payment...")
```

**GOOD**:
```python
logger.debug(f"🔍 Debug info: {variable}")
logger.info("Processing payment...")
```

**Exception**: `print()` is acceptable ONLY in:
- Local development scripts (`TOOLS_SCRIPTS_TESTS/tools/`)
- Unit tests (`tests/`)
- Interactive CLI tools

### Rule 2: Always configure logging at module level

**Required Setup** (at top of every service file):
```python
import logging
import os

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress noisy third-party loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
```

### Rule 3: Use appropriate log levels

| Level | When to Use | Production Visibility |
|-------|-------------|---------------------|
| `DEBUG` | Detailed diagnostic info, variable dumps, CORS debugging | ❌ Hidden (LOG_LEVEL=INFO) |
| `INFO` | General informational messages, service startup, major operations | ✅ Visible |
| `WARNING` | Unexpected behavior that doesn't prevent operation | ✅ Visible + Alerts |
| `ERROR` | Error that prevents specific operation | ✅ Visible + Alerts |
| `CRITICAL` | Fatal error requiring immediate attention | ✅ Visible + Pager Alerts |

### Rule 4: Use structured logging tags

**Always prefix logs with context tags** for easy filtering:

```python
logger.debug(f"🔍 [CORS] Origin: {origin}")
logger.info(f"💰 [PAYMENT] Processing payment ID: {payment_id}")
logger.warning(f"⚠️ [RATE_LIMIT] User {user_id} exceeded limit")
logger.error(f"❌ [DATABASE] Failed to connect: {error}")
```

**Standard Tags**:
- `[CORS]` - CORS-related operations
- `[AUTH]` - Authentication/authorization
- `[PAYMENT]` - Payment processing
- `[DATABASE]` - Database operations
- `[API]` - API requests/responses
- `[WEBHOOK]` - Webhook handling
- `[RATE_LIMIT]` - Rate limiting events
- `[SECURITY]` - Security events (HMAC, IP whitelist)
- `[CLOUDTASKS]` - Cloud Tasks operations
- `[CHANGENOW]` - ChangeNOW API calls

### Rule 5: NEVER log sensitive data

**Sensitive Data** (NEVER log):
- Passwords or password hashes
- API keys or secrets
- Credit card numbers
- Private keys
- JWT tokens (full token)
- User email addresses (use user_id instead)
- Telegram bot tokens
- Database connection strings

**ACCEPTABLE** (OK to log):
```python
logger.info(f"💰 [PAYMENT] Payment created: ID={payment_id}, Amount={amount}")
logger.info(f"🔐 [AUTH] User logged in: user_id={user_id}")
logger.debug(f"🔍 [JWT] Token expires in {expires_in} seconds")
```

**FORBIDDEN** (NEVER log):
```python
logger.debug(f"Password: {password}")  # ❌ NEVER
logger.debug(f"API Key: {api_key}")  # ❌ NEVER
logger.debug(f"JWT Token: {token}")  # ❌ NEVER (log token_id only)
logger.debug(f"Email: {email}")  # ❌ Avoid (use user_id)
```

---

## Implementation Guide

### Step 1: Add Logging Configuration

At the **top of every service file** (after imports):

```python
import logging
import os

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

### Step 2: Convert print() Statements

**Find all print() statements**:
```bash
grep -rn "print(" PGP_WEBAPI_v1/*.py
```

**Convert based on purpose**:

| Purpose | BEFORE | AFTER |
|---------|--------|-------|
| **Debug info** | `print(f"🔍 Debug: {var}")` | `logger.debug(f"🔍 [TAG] Debug: {var}")` |
| **Startup info** | `print("🚀 Service starting")` | `logger.info("🚀 Service starting")` |
| **Success message** | `print("✅ Operation complete")` | `logger.info("✅ [TAG] Operation complete")` |
| **Warning** | `print("⚠️ Retry attempt")` | `logger.warning("⚠️ [TAG] Retry attempt")` |
| **Error** | `print(f"❌ Error: {e}")` | `logger.error(f"❌ [TAG] Error: {e}")` |

### Step 3: Test Logging Levels

**Development** (verbose logging):
```bash
export LOG_LEVEL=DEBUG
python pgp_webapi_v1.py
# Output: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Production** (minimal logging):
```bash
export LOG_LEVEL=INFO
python pgp_webapi_v1.py
# Output: INFO, WARNING, ERROR, CRITICAL (DEBUG suppressed)
```

**Verify**:
```bash
# Should NOT see debug logs in production
curl http://localhost:8080/api/health
# Logs should only show INFO level or higher
```

### Step 4: Update Deployment Configuration

**Cloud Run Deployment** (`app.yaml` or `gcloud run deploy`):
```yaml
env_variables:
  LOG_LEVEL: "INFO"  # Production: INFO, Staging: DEBUG
```

**Docker Compose** (local development):
```yaml
environment:
  LOG_LEVEL: "DEBUG"  # Development: full verbosity
```

---

## Log Levels

### DEBUG

**Purpose**: Detailed diagnostic information for troubleshooting

**When to Use**:
- CORS request/response details
- HTTP header inspection
- Variable dumps for debugging
- Function entry/exit tracing
- State transitions

**Examples**:
```python
logger.debug(f"🔍 [CORS] Origin: {origin}, Allowed: {cors_origins}")
logger.debug(f"🔍 [API] Request headers: {dict(request.headers)}")
logger.debug(f"🔍 [DATABASE] Query: {query}")
logger.debug(f"🔍 [WEBHOOK] Payload: {json.dumps(payload)}")
```

**Production**: ❌ **SUPPRESSED** (LOG_LEVEL=INFO)

### INFO

**Purpose**: General informational messages about normal operations

**When to Use**:
- Service startup
- Major operations (payment creation, user signup)
- Successful completions
- Configuration loading
- Cron job execution

**Examples**:
```python
logger.info("🚀 PGP_WEBAPI_v1 Starting")
logger.info(f"💰 [PAYMENT] Payment created: ID={payment_id}")
logger.info(f"🔐 [AUTH] User logged in: user_id={user_id}")
logger.info(f"✅ [DATABASE] Connection pool initialized")
```

**Production**: ✅ **VISIBLE**

### WARNING

**Purpose**: Unexpected behavior that doesn't prevent operation

**When to Use**:
- Retry attempts
- Fallback to defaults
- Deprecated API usage
- Rate limit approaching
- Temporary failures

**Examples**:
```python
logger.warning(f"⚠️ [API] Retry attempt {retry} for request")
logger.warning(f"⚠️ [CONFIG] Using fallback value for {key}")
logger.warning(f"⚠️ [RATE_LIMIT] User {user_id} at 80% of limit")
logger.warning(f"⚠️ [CLOUDTASKS] Task queue backlog: {count}")
```

**Production**: ✅ **VISIBLE** + Monitoring Alerts

### ERROR

**Purpose**: Error that prevents specific operation

**When to Use**:
- Database connection failures
- API call failures
- Validation errors
- Payment processing errors
- Webhook delivery failures

**Examples**:
```python
logger.error(f"❌ [DATABASE] Failed to connect: {error}")
logger.error(f"❌ [API] NowPayments API error: {response.status_code}")
logger.error(f"❌ [PAYMENT] Payment verification failed: {payment_id}")
logger.error(f"❌ [WEBHOOK] Failed to deliver notification: {error}")
```

**Production**: ✅ **VISIBLE** + Monitoring Alerts + Incident Tracking

### CRITICAL

**Purpose**: Fatal error requiring immediate attention

**When to Use**:
- Service cannot start
- Complete database failure
- Critical security breach
- Data corruption
- Payment system down

**Examples**:
```python
logger.critical(f"🚨 [STARTUP] Failed to load secret: {error}")
logger.critical(f"🚨 [DATABASE] Connection pool exhausted")
logger.critical(f"🚨 [SECURITY] HMAC validation bypass detected")
logger.critical(f"🚨 [PAYMENT] Payment gateway unreachable")
```

**Production**: ✅ **VISIBLE** + **PAGER ALERTS** + Immediate Escalation

---

## Production Configuration

### Environment Variables

**Required** for all services:
```bash
# Set in Cloud Run environment
LOG_LEVEL=INFO  # Production default
```

**Optional** (for debugging):
```bash
LOG_LEVEL=DEBUG  # Temporary for troubleshooting
```

### Cloud Run Deployment

```bash
gcloud run deploy pgp-webapi-v1 \
  --set-env-vars LOG_LEVEL=INFO \
  --region us-central1 \
  --project pgp-live
```

### Dockerfile

```dockerfile
# Production default
ENV LOG_LEVEL=INFO

# Can be overridden at runtime
# docker run -e LOG_LEVEL=DEBUG ...
```

### app.yaml (App Engine)

```yaml
env_variables:
  LOG_LEVEL: "INFO"
```

---

## Migration Guide

### Phase 1: Identify print() Statements

**Find all print() in production code**:
```bash
# Search for print statements
grep -rn "print(" PGP_*/[!tests]*.py > print_statements.txt

# Count by service
for service in PGP_*_v1; do
  count=$(grep -r "print(" "$service/*.py" 2>/dev/null | wc -l)
  echo "$service: $count print() calls"
done
```

### Phase 2: Service-by-Service Conversion

**Priority Order**:
1. ✅ **PGP_WEBAPI_v1** (COMPLETE - Issue 3 reference)
2. ⏳ **PGP_SERVER_v1** (Telegram bot service)
3. ⏳ **PGP_ORCHESTRATOR_v1** (Orchestration service)
4. ⏳ **PGP_NP_IPN_v1** (NowPayments webhook)
5. ⏳ **PGP_SPLIT*_v1** (Payment splitting services)
6. ⏳ **PGP_HOSTPAY*_v1** (Payment hosting services)
7. ⏳ **PGP_ACCUMULATOR_v1** (Payment accumulation)
8. ⏳ **PGP_BATCHPROCESSOR_v1** (Batch processing)

**Conversion Checklist (per service)**:
- [ ] Add logging configuration at module level
- [ ] Convert all `print()` to `logger.debug/info/warning/error()`
- [ ] Add structured tags `[TAG]` to all log messages
- [ ] Test with `LOG_LEVEL=DEBUG` (development)
- [ ] Test with `LOG_LEVEL=INFO` (production simulation)
- [ ] Update deployment config with `LOG_LEVEL=INFO`
- [ ] Deploy to staging
- [ ] Verify Cloud Logging output
- [ ] Deploy to production

### Phase 3: Cleanup

**Remove print() from test files**:
```bash
# Tests can keep print() for local output
# But should also support logging for CI/CD
```

**Update tools/scripts**:
```bash
# Tools can keep print() for CLI output
# Add --quiet flag for production scripts
```

---

## Examples

### Example 1: PGP_WEBAPI_v1 (COMPLETE)

**File**: `PGP_WEBAPI_v1/pgp_webapi_v1.py`

**BEFORE**:
```python
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    print(f"🔍 CORS Debug - Origin: {origin}, Allowed origins: {cors_origins}")
    print(f"🔍 CORS Debug - Origin in list: {origin in cors_origins}")

    if origin in cors_origins:
        print(f"✅ Adding CORS headers for origin: {origin}")
        # ... set headers ...
    else:
        print(f"❌ Origin not in allowed list or missing")

    print(f"🔍 Response headers: {dict(response.headers)}")
    return response
```

**AFTER**:
```python
import logging
import os

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    logger.debug(f"🔍 [CORS] Origin: {origin}, Allowed origins: {cors_origins}")
    logger.debug(f"🔍 [CORS] Origin in list: {origin in cors_origins}")

    if origin in cors_origins:
        logger.debug(f"✅ [CORS] Adding CORS headers for origin: {origin}")
        # ... set headers ...
    else:
        logger.debug(f"❌ [CORS] Origin not in allowed list or missing")

    logger.debug(f"🔍 [CORS] Response headers: {dict(response.headers)}")
    return response
```

**Result**:
- **Production** (`LOG_LEVEL=INFO`): No CORS debug logs ✅
- **Development** (`LOG_LEVEL=DEBUG`): Full CORS debugging ✅
- **Secure**: No information disclosure in production ✅

### Example 2: Payment Processing

**BEFORE**:
```python
def process_payment(payment_id):
    print(f"Processing payment: {payment_id}")
    try:
        result = payment_api.create(payment_id)
        print(f"Payment created: {result}")
    except Exception as e:
        print(f"Error processing payment: {e}")
```

**AFTER**:
```python
def process_payment(payment_id):
    logger.info(f"💰 [PAYMENT] Processing payment: {payment_id}")
    try:
        result = payment_api.create(payment_id)
        logger.info(f"💰 [PAYMENT] Payment created: ID={payment_id}, Status={result.status}")
        logger.debug(f"🔍 [PAYMENT] Full response: {result}")
    except Exception as e:
        logger.error(f"❌ [PAYMENT] Failed to process payment {payment_id}: {e}", exc_info=True)
```

**Benefits**:
- Info logs: High-level operation status
- Debug logs: Detailed response data (production: suppressed)
- Error logs: Full exception with stack trace

### Example 3: Startup Logging

**BEFORE**:
```python
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("=" * 80)
    print("🚀 Service Starting")
    print(f"Port: {port}")
    print("=" * 80)
    app.run(host='0.0.0.0', port=port)
```

**AFTER**:
```python
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info("=" * 80)
    logger.info("🚀 PGP_WEBAPI_v1 Starting")
    logger.info(f"📍 Port: {port}")
    logger.info(f"📝 Log Level: {LOG_LEVEL}")
    logger.info("=" * 80)
    app.run(host='0.0.0.0', port=port)
```

---

## Monitoring

### Cloud Logging Queries

**Filter by log level**:
```
resource.type="cloud_run_revision"
AND severity>=WARNING
```

**Filter by tag**:
```
resource.type="cloud_run_revision"
AND jsonPayload.message=~"\[PAYMENT\]"
```

**Find debug logs (should be empty in production)**:
```
resource.type="cloud_run_revision"
AND severity=DEBUG
AND timestamp>"2025-11-16T00:00:00Z"
```

**Error rate monitoring**:
```
resource.type="cloud_run_revision"
AND severity>=ERROR
AND timestamp>"2025-11-16T00:00:00Z"
```

### Alerts

**Create alerts for**:
- ERROR rate > 10/minute
- CRITICAL log detected (immediate)
- WARNING rate > 100/minute

---

## Related Documentation

- [HMAC Timestamp Security](PGP_SERVER_v1/security/HMAC_TIMESTAMP_SECURITY.md) - Issue 1
- [IP Whitelist Security](PGP_SERVER_v1/security/IP_WHITELIST_SECURITY.md) - Issue 2

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-16 | 1.0.0 | Initial logging best practices (Issue 3) |

---

**Security Issue**: Issue 3 - Debug Logging in Production
**Status**: ✅ PGP_WEBAPI_v1 COMPLETE, ⏳ Other services IN PROGRESS
**Next Steps**: Apply to remaining 14 production services
