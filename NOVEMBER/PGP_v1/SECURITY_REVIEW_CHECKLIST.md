# PayGatePrime v1 - Pre-Deployment Security & Best Practices Checklist

**Project:** pgp-live
**Services to Review:** 15
**Review Date:** _____________
**Reviewed By:** _____________

---

## 📋 Overview

This checklist ensures all services meet security best practices and industry standards before deployment to production. Each service must pass ALL checks before deployment.

**Priority Levels:**
- 🔴 **CRITICAL** - Must fix before deployment (security risk)
- 🟡 **HIGH** - Should fix before deployment (best practice)
- 🟢 **MEDIUM** - Nice to have (optimization)

---

## 🎯 Services to Review (15 Total)

### Public-Facing Services (HIGH RISK) 🔴
- [ ] **pgp-server-v1** (Main API) - Directory: `GCRegisterAPI-PGP/`
- [ ] **pgp-npwebhook-v1** (NowPayments IPN) - Directory: `np-webhook-PGP/`
- [ ] **pgp-bot-v1** (Telegram Bot) - Directory: `TelePay-PGP/`

### Internal Payment Services (CRITICAL) 🔴
- [ ] **pgp-webhook1-v1** (Payment Processor) - Directory: `GCWebhook1-PGP/`
- [ ] **pgp-webhook2-v1** (Telegram Invites) - Directory: `GCWebhook2-PGP/`
- [ ] **pgp-split1-v1** (Payment Splitter) - Directory: `GCSplit1-PGP/`
- [ ] **pgp-split2-v1** (Payment Router) - Directory: `GCSplit2-PGP/`
- [ ] **pgp-split3-v1** (Accumulator Enqueuer) - Directory: `GCSplit3-PGP/`

### Crypto Payment Services (CRITICAL) 🔴
- [ ] **pgp-hostpay1-v1** (Crypto Executor) - Directory: `GCHostPay1-PGP/`
- [ ] **pgp-hostpay2-v1** (Conversion Monitor) - Directory: `GCHostPay2-PGP/`
- [ ] **pgp-hostpay3-v1** (Blockchain Validator) - Directory: `GCHostPay3-PGP/`

### Batch Processing Services (HIGH) 🟡
- [ ] **pgp-accumulator-v1** (Accumulator) - Directory: `GCAccumulator-PGP/`
- [ ] **pgp-batchprocessor-v1** (Batch Processor) - Directory: `GCBatchProcessor-PGP/`
- [ ] **pgp-microbatchprocessor-v1** (Micro Batch) - Directory: `GCMicroBatchProcessor-PGP/`

---

## 🔐 SECTION 1: Secrets Management & Configuration (CRITICAL)

**Review For:** ALL 15 services

### 1.1 Secret Manager Integration 🔴
- [ ] Uses Google Cloud Secret Manager (NOT environment variables or .env files)
- [ ] No hardcoded secrets in source code
- [ ] No secrets in config files committed to git
- [ ] All secrets loaded at runtime from Secret Manager
- [ ] Proper error handling when secrets cannot be retrieved
- [ ] Secrets are NOT logged or printed to console

**Check Files:**
- `config_manager.py` or equivalent
- `app.py` main application file
- Any configuration modules

**Validation Command:**
```bash
# Search for potential hardcoded secrets
grep -r "API_KEY\|api_key\|password\|secret\|token" --include="*.py" [SERVICE_DIR]/ | grep -v "SECRET_NAME\|get_secret\|access_secret"
```

### 1.2 Secret Names Updated to PGP v1 🔴
- [ ] All queue secret names use `PGP_*_QUEUE` format (not `GC*_QUEUE`)
- [ ] All URL secret names use `PGP_*_URL` format (not `GC*_URL`)
- [ ] Secret names match those in `04_create_queue_secrets.sh`
- [ ] Secret names match those in `05_create_service_url_secrets.sh`
- [ ] No references to old GC* secret names remain

**Check Files:**
- All Python files with secret references

**Validation Command:**
```bash
# Search for old secret naming scheme
grep -r "GCWEBHOOK\|GCSPLIT\|GCHOSTPAY\|GCACCUMULATOR\|GCBATCHPROCESSOR" --include="*.py" [SERVICE_DIR]/
```

### 1.3 Configuration Security 🔴
- [ ] Database credentials NOT in code (retrieved from Secret Manager)
- [ ] API keys NOT in code (retrieved from Secret Manager)
- [ ] JWT secrets use cryptographically secure random values (256-bit minimum)
- [ ] Database connection uses Cloud SQL Auth Proxy (not direct IP)
- [ ] Project ID and region loaded from environment or Secret Manager

---

## 🔒 SECTION 2: Payment Data Security (CRITICAL)

**Review For:** pgp-server-v1, pgp-npwebhook-v1, pgp-webhook1-v1, pgp-webhook2-v1, all split and hostpay services

### 2.1 Data Encryption 🔴
- [ ] Payment amounts encrypted at rest in database (if stored long-term)
- [ ] Sensitive user data encrypted in transit (HTTPS only)
- [ ] Database uses encryption at rest (Cloud SQL default)
- [ ] Wallet addresses validated before use
- [ ] Credit card numbers NEVER stored (if applicable)
- [ ] PII (Personally Identifiable Information) minimized

**Best Practice Reference:**
```python
# Example: Encrypt sensitive data before storage
from cryptography.fernet import Fernet
from google.cloud import kms

# Use Google Cloud KMS for encryption keys
# Never hardcode encryption keys
```

### 2.2 Payment Processing Security 🔴
- [ ] Payment amounts validated (positive, within limits)
- [ ] Transaction IDs validated as unique
- [ ] Duplicate payment detection implemented
- [ ] Idempotency keys used for payment operations
- [ ] Payment status transitions validated (state machine)
- [ ] Refund capabilities secured with proper authorization
- [ ] Fee calculations validated (prevent manipulation)

**Check:**
```python
# Ensure payment validation like:
def validate_payment(amount, currency):
    if amount <= 0:
        raise ValueError("Invalid amount")
    if amount > MAX_PAYMENT_AMOUNT:
        raise ValueError("Amount exceeds limit")
    # Additional validation...
```

### 2.3 Webhook Security (NowPayments IPN) 🔴
**Service:** pgp-npwebhook-v1

- [ ] HMAC signature verification implemented
- [ ] IPN secret stored in Secret Manager
- [ ] Signature verification happens BEFORE processing
- [ ] Replay attack prevention (nonce/timestamp validation)
- [ ] IP allowlist for NowPayments (if available)
- [ ] Invalid signatures logged and rejected
- [ ] Rate limiting implemented

**Validation:**
```python
# Must have signature verification like:
import hmac
import hashlib

def verify_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## 🛡️ SECTION 3: API Security (CRITICAL)

**Review For:** pgp-server-v1, pgp-npwebhook-v1, pgp-bot-v1

### 3.1 Authentication & Authorization 🔴
- [ ] JWT tokens used for authentication
- [ ] JWT secrets are 256-bit minimum
- [ ] JWT expiration implemented (not infinite tokens)
- [ ] Token refresh mechanism implemented
- [ ] Role-based access control (if applicable)
- [ ] API endpoints protected (not all public)
- [ ] Service-to-service auth uses Cloud Run service accounts

**Check:**
```python
# JWT implementation should include:
import jwt
from datetime import datetime, timedelta

def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')
```

### 3.2 Input Validation & Sanitization 🔴
- [ ] All user inputs validated (type, length, format)
- [ ] SQL injection prevention (parameterized queries ONLY)
- [ ] XSS prevention (input sanitization)
- [ ] Command injection prevention (no shell commands with user input)
- [ ] Path traversal prevention (validate file paths)
- [ ] Email validation (proper regex)
- [ ] URL validation (prevent SSRF)

**Anti-Pattern (DO NOT USE):**
```python
# NEVER DO THIS:
query = f"SELECT * FROM users WHERE email = '{user_email}'"  # SQL INJECTION!

# ALWAYS DO THIS:
query = "SELECT * FROM users WHERE email = %s"
cursor.execute(query, (user_email,))
```

### 3.3 Rate Limiting & DDoS Protection 🟡
- [ ] Rate limiting on API endpoints
- [ ] Rate limiting on authentication endpoints (prevent brute force)
- [ ] Rate limiting on payment endpoints
- [ ] Cloud Run concurrency limits configured
- [ ] Cloud Armor enabled (if needed)
- [ ] Request size limits enforced

---

## 🗄️ SECTION 4: Database Security (CRITICAL)

**Review For:** ALL services with database access

### 4.1 Connection Security 🔴
- [ ] Uses Cloud SQL Auth Proxy (unix socket connection)
- [ ] Connection string format: `/cloudsql/[CONNECTION_NAME]`
- [ ] Database password stored in Secret Manager
- [ ] Connection pooling implemented
- [ ] Connections properly closed (using context managers)
- [ ] Connection timeout configured
- [ ] SSL/TLS enforced (if not using unix socket)

**Check:**
```python
# Proper Cloud SQL connection:
import pg8000
from google.cloud.sql.connector import Connector

connector = Connector()

def get_conn():
    conn = connector.connect(
        "pgp-live:us-central1:pgp-live-psql",
        "pg8000",
        user=db_user,
        password=db_password,
        db=db_name
    )
    return conn
```

### 4.2 Query Security 🔴
- [ ] ALL queries use parameterized statements
- [ ] NO string formatting in SQL queries
- [ ] NO dynamic table/column names from user input
- [ ] Prepared statements used where possible
- [ ] ORM used correctly (if applicable)
- [ ] Least privilege database user (not postgres superuser for app)

**Anti-Pattern:**
```python
# NEVER:
cursor.execute(f"INSERT INTO payments VALUES ('{amount}', '{user_id}')")

# ALWAYS:
cursor.execute("INSERT INTO payments VALUES (%s, %s)", (amount, user_id))
```

### 4.3 Data Protection 🔴
- [ ] Sensitive columns identified and protected
- [ ] PII access logged (audit trail)
- [ ] Database backups enabled
- [ ] Point-in-time recovery enabled
- [ ] Database access restricted (firewall rules)
- [ ] No database credentials in logs

---

## 🔑 SECTION 5: Cryptography & Hashing (CRITICAL)

**Review For:** pgp-server-v1, all services handling sensitive data

### 5.1 Password Hashing 🔴
- [ ] Uses bcrypt, argon2, or scrypt (NOT MD5, SHA1, plain SHA256)
- [ ] Sufficient cost factor (bcrypt: 12+, argon2: recommended params)
- [ ] Passwords NEVER logged or stored in plain text
- [ ] Password reset uses secure tokens (not predictable)

**Best Practice:**
```python
# Use bcrypt or argon2
import bcrypt

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)
```

### 5.2 Encryption Standards 🔴
- [ ] AES-256 used for data encryption (if encrypting data)
- [ ] No custom/homebrew encryption algorithms
- [ ] Uses well-established libraries (cryptography, google-cloud-kms)
- [ ] Encryption keys managed by Cloud KMS (not in code)
- [ ] Proper IV/nonce generation for each encryption

### 5.3 Random Number Generation 🔴
- [ ] Uses `secrets` module for security-sensitive operations
- [ ] Does NOT use `random` module for tokens/keys
- [ ] Session tokens cryptographically random
- [ ] API keys cryptographically random

**Best Practice:**
```python
import secrets

# For security-sensitive operations:
token = secrets.token_urlsafe(32)  # Good
# NOT: token = ''.join(random.choice(string.ascii_letters) for _ in range(32))  # Bad
```

---

## 📝 SECTION 6: Logging & Monitoring (CRITICAL)

**Review For:** ALL 15 services

### 6.1 Secure Logging 🔴
- [ ] NO sensitive data in logs (passwords, API keys, tokens, credit cards)
- [ ] NO PII in logs unless necessary (and redacted)
- [ ] Payment amounts logged (for audit), but NOT card details
- [ ] User IDs logged (for debugging), but NOT passwords
- [ ] Error messages don't reveal system internals
- [ ] Stack traces don't contain secrets
- [ ] Structured logging used (JSON format)

**Anti-Pattern:**
```python
# NEVER LOG:
logger.info(f"User login: {email} with password {password}")  # BAD!
logger.info(f"API Key: {api_key}")  # BAD!

# ALWAYS LOG:
logger.info(f"User login attempt: {email}")  # Good
logger.info(f"Payment processed: amount={amount}, user_id={user_id}")  # Good
```

### 6.2 Audit Trail 🟡
- [ ] All payment operations logged
- [ ] Authentication attempts logged (success and failure)
- [ ] Authorization failures logged
- [ ] Configuration changes logged
- [ ] Logs include timestamp, user_id, action, result
- [ ] Logs sent to Cloud Logging (Stackdriver)

### 6.3 Error Handling 🔴
- [ ] Generic error messages to users (don't reveal internals)
- [ ] Detailed errors logged server-side only
- [ ] No stack traces exposed to users in production
- [ ] All exceptions caught and handled
- [ ] Database errors don't leak schema information
- [ ] 500 errors logged with context

**Best Practice:**
```python
try:
    result = process_payment(data)
except PaymentError as e:
    logger.error(f"Payment failed: {e}", extra={'user_id': user_id})
    return {"error": "Payment processing failed"}, 400  # Generic to user
except Exception as e:
    logger.exception(f"Unexpected error: {e}")  # Detailed to logs
    return {"error": "Internal server error"}, 500  # Generic to user
```

---

## 🌐 SECTION 7: Network & Transport Security (CRITICAL)

**Review For:** ALL 15 services

### 7.1 HTTPS/TLS 🔴
- [ ] HTTPS enforced (Cloud Run default)
- [ ] HTTP redirects to HTTPS (if applicable)
- [ ] TLS 1.2 minimum (TLS 1.3 preferred)
- [ ] No mixed content (all resources over HTTPS)
- [ ] HSTS headers enabled
- [ ] Secure cookies (Secure, HttpOnly, SameSite flags)

### 7.2 CORS Configuration 🔴
**Service:** pgp-server-v1

- [ ] CORS origin restricted to frontend domain only
- [ ] NOT set to `*` (allow all)
- [ ] Credentials allowed only for trusted origins
- [ ] Preflight requests handled correctly
- [ ] CORS headers validated

**Check:**
```python
# CORS should be:
CORS_ORIGIN = "https://www.paygateprime.com"  # Specific domain
# NOT: CORS_ORIGIN = "*"  # Too permissive!
```

### 7.3 Service-to-Service Communication 🔴
- [ ] Internal services NOT publicly accessible
- [ ] Cloud Tasks uses OIDC tokens for authentication
- [ ] Service accounts have least privilege
- [ ] No service account keys in code (use Workload Identity)

---

## 🔧 SECTION 8: Dependencies & Vulnerabilities (HIGH)

**Review For:** ALL 15 services

### 8.1 Dependency Management 🟡
- [ ] requirements.txt exists and is up to date
- [ ] All dependencies pinned to specific versions
- [ ] No wildcard version specifiers (`package==*`)
- [ ] No known vulnerabilities in dependencies
- [ ] Dependencies regularly updated (security patches)

**Check:**
```bash
# Scan for vulnerabilities
pip install safety
safety check -r requirements.txt

# Or use Google Cloud artifact scanning
```

### 8.2 Python Version 🟡
- [ ] Python 3.9+ used (security updates)
- [ ] Not using EOL Python versions
- [ ] Dockerfile specifies exact Python version

### 8.3 Docker Security 🟡
- [ ] Base image from trusted source (official Python)
- [ ] No root user in container (if possible)
- [ ] Minimal base image (python:3.10-slim preferred over python:3.10)
- [ ] No unnecessary packages installed
- [ ] .dockerignore configured (excludes .git, .env, etc.)

---

## 🏗️ SECTION 9: Code Quality & Architecture (MEDIUM)

**Review For:** ALL 15 services

### 9.1 Code Structure 🟢
- [ ] Separation of concerns (routes, business logic, data access)
- [ ] Config separate from code (config_manager.py)
- [ ] No business logic in route handlers
- [ ] Database access abstracted (database_manager.py)
- [ ] Error handling consistent
- [ ] Code follows Python PEP 8 style guide

### 9.2 Cloud Run Best Practices 🟡
- [ ] Starts quickly (under 10 seconds)
- [ ] Listens on PORT environment variable
- [ ] Handles SIGTERM gracefully (graceful shutdown)
- [ ] Stateless design (no local file storage)
- [ ] Concurrency configured appropriately
- [ ] Health check endpoint implemented

**Check:**
```python
import os
import signal

PORT = int(os.environ.get('PORT', 8080))

# Graceful shutdown
def shutdown_handler(signum, frame):
    logger.info("Shutting down gracefully...")
    # Close connections, cleanup
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
```

### 9.3 Cloud Tasks Integration 🟡
- [ ] Task creation includes proper authentication
- [ ] Task payloads validated
- [ ] Task failures handled (retries configured)
- [ ] Task idempotency implemented
- [ ] Dead letter queue configured

---

## 💰 SECTION 10: Payment Gateway Integration (CRITICAL)

### 10.1 NowPayments Integration 🔴
**Services:** pgp-server-v1, pgp-npwebhook-v1

- [ ] API key stored in Secret Manager
- [ ] IPN secret stored in Secret Manager
- [ ] HMAC signature verification on all IPNs
- [ ] Payment status updates idempotent
- [ ] Webhook replay attack prevention
- [ ] Error handling for API failures
- [ ] Retry logic with exponential backoff

### 10.2 ChangeNOW Integration 🔴
**Services:** pgp-hostpay1-v1, pgp-hostpay2-v1

- [ ] API key stored in Secret Manager
- [ ] Wallet addresses validated before use
- [ ] Transaction monitoring implemented
- [ ] Conversion rate limits enforced
- [ ] Error handling for API failures
- [ ] Transaction IDs validated as unique

### 10.3 Blockchain Validation 🔴
**Service:** pgp-hostpay3-v1

- [ ] Alchemy API key in Secret Manager
- [ ] RPC endpoints use HTTPS
- [ ] Transaction hash validation
- [ ] Block confirmation requirements met
- [ ] Smart contract calls validated
- [ ] Gas price validation (prevent manipulation)
- [ ] Wallet ownership verified

---

## 🧪 SECTION 11: Testing & Validation (HIGH)

**Review For:** ALL 15 services

### 11.1 Testing Coverage 🟡
- [ ] Unit tests exist for critical functions
- [ ] Payment processing has test coverage
- [ ] Authentication/authorization tested
- [ ] Input validation tested
- [ ] Error handling tested
- [ ] Integration tests for external APIs

### 11.2 Manual Testing Checklist 🟡
- [ ] Test with valid inputs
- [ ] Test with invalid inputs (negative testing)
- [ ] Test with boundary values
- [ ] Test error scenarios
- [ ] Test concurrent requests
- [ ] Test with production-like data volumes

---

## 📊 SECTION 12: Compliance & Legal (MEDIUM)

### 12.1 Data Privacy 🟡
- [ ] GDPR compliance considered (if EU users)
- [ ] PII minimization principle followed
- [ ] User data deletion capability exists
- [ ] Privacy policy references correct practices
- [ ] Data retention policies defined
- [ ] User consent mechanisms (if needed)

### 12.2 Financial Compliance 🟡
- [ ] PCI DSS compliance (if handling cards - should NOT be)
- [ ] AML (Anti-Money Laundering) considerations
- [ ] Transaction limits enforced
- [ ] Audit logs for financial transactions
- [ ] Terms of service references payment processing

---

## ✅ SECTION 13: Pre-Deployment Verification

### 13.1 Final Checklist 🔴
Before deploying ANY service, verify:

- [ ] All CRITICAL (🔴) items pass
- [ ] All HIGH (🟡) items reviewed and addressed or documented
- [ ] Secrets exist in Secret Manager
- [ ] Service account permissions configured
- [ ] Cloud SQL database exists and accessible
- [ ] Cloud Tasks queues created
- [ ] Deployment script tested in staging (if available)
- [ ] Rollback plan documented
- [ ] Monitoring and alerts configured

### 13.2 Security Sign-Off 🔴
- [ ] Security review completed
- [ ] Penetration testing conducted (if applicable)
- [ ] Vulnerability scan completed
- [ ] Code review by second developer completed
- [ ] Security exceptions documented and approved

### 13.3 Documentation 🟢
- [ ] README.md exists for service
- [ ] API documentation complete
- [ ] Environment variables documented
- [ ] Secrets list documented
- [ ] Deployment instructions complete
- [ ] Troubleshooting guide exists

---

## 📋 Service-by-Service Review Template

Use this template for each of the 15 services:

```
SERVICE: ___________________________
DIRECTORY: _________________________
REVIEWER: __________________________
DATE: ______________________________

CRITICAL CHECKS (ALL MUST PASS):
[ ] Secrets in Secret Manager (not hardcoded)
[ ] Input validation on all endpoints
[ ] SQL injection prevention (parameterized queries)
[ ] Authentication/authorization implemented
[ ] Payment data secured (if applicable)
[ ] Webhook signature verification (if applicable)
[ ] HTTPS enforced
[ ] No sensitive data in logs
[ ] Error handling doesn't leak information
[ ] Dependencies scanned for vulnerabilities

HIGH PRIORITY CHECKS:
[ ] Rate limiting implemented
[ ] Audit logging configured
[ ] Graceful shutdown handling
[ ] Database connection security
[ ] Cloud Run best practices followed

NOTES:
_________________________________________________
_________________________________________________
_________________________________________________

SECURITY EXCEPTIONS (if any):
_________________________________________________
_________________________________________________

APPROVAL:
[ ] Approved for deployment
[ ] Requires fixes (see notes)
[ ] Rejected (critical issues)

Signature: _________________ Date: _____________
```

---

## 🚀 Quick Reference Commands

### Security Scanning
```bash
# Check for hardcoded secrets
cd [SERVICE_DIR]
grep -r "api_key\|password\|secret\|token" --include="*.py" . | grep -v "get_secret\|SECRET_NAME"

# Check for SQL injection vulnerabilities
grep -r "execute.*f\"\|execute.*%\|execute.*format" --include="*.py" .

# Check for old naming scheme
grep -r "GCWEBHOOK\|GCSPLIT\|GCHOSTPAY" --include="*.py" .

# Scan dependencies
pip install safety
safety check -r requirements.txt

# Check for common security issues
bandit -r . -f json -o security-report.json
```

### Testing Commands
```bash
# Run tests
pytest tests/

# Test with coverage
pytest --cov=. --cov-report=html tests/

# Static type checking
mypy *.py
```

---

## 📚 Best Practices References

### Security Resources:
- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **PCI DSS:** https://www.pcisecuritystandards.org/
- **Google Cloud Security Best Practices:** https://cloud.google.com/security/best-practices
- **Cloud Run Security:** https://cloud.google.com/run/docs/securing/
- **Secret Manager Best Practices:** https://cloud.google.com/secret-manager/docs/best-practices

### Python Security:
- **Python Security Best Practices:** https://python.readthedocs.io/en/stable/library/security.html
- **Bandit Security Linter:** https://bandit.readthedocs.io/
- **Safety Vulnerability Scanner:** https://pyup.io/safety/

---

**REMEMBER:**
- ✅ Security first - never deploy with known vulnerabilities
- ✅ Fail secure - default to denying access
- ✅ Defense in depth - multiple layers of security
- ✅ Least privilege - minimal permissions necessary
- ✅ Assume breach - plan for compromises

**Last Updated:** 2025-11-16
**Version:** 1.0
**Status:** READY FOR REVIEW
