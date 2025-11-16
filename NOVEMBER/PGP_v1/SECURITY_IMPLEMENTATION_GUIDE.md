# Security Implementation Guide - Fix Critical Issues

**Purpose:** Step-by-step guide to fix the 3 critical security gaps
**Estimated Time:** 8-12 hours total
**Priority:** Complete before production deployment

---

## 📋 Overview of Fixes

| Issue | Severity | Files Affected | Time Estimate |
|-------|----------|----------------|---------------|
| **Service-to-Service Auth** | 🔴 CRITICAL | 11 services | 4-5 hours |
| **HTTP Security Headers** | 🔴 CRITICAL | 15 services | 2-3 hours |
| **Input Validation** | 🟡 HIGH | 5 files | 2-4 hours |

---

# PART 1: Service-to-Service Authentication (OIDC)

## 🎯 Goal
Add OIDC token verification to all internal Cloud Run services to prevent unauthorized service-to-service calls.

## 📊 Affected Services (11 total)
- pgp-webhook1-v1 (GCWebhook1-PGP)
- pgp-webhook2-v1 (GCWebhook2-PGP)
- pgp-split1-v1 (GCSplit1-PGP)
- pgp-split2-v1 (GCSplit2-PGP)
- pgp-split3-v1 (GCSplit3-PGP)
- pgp-hostpay1-v1 (GCHostPay1-PGP)
- pgp-hostpay2-v1 (GCHostPay2-PGP)
- pgp-hostpay3-v1 (GCHostPay3-PGP)
- pgp-accumulator-v1 (GCAccumulator-PGP)
- pgp-batchprocessor-v1 (GCBatchProcessor-PGP)
- pgp-microbatchprocessor-v1 (GCMicroBatchProcessor-PGP)

---

## Step 1: Create OIDC Middleware (Common Module)

### 1.1 Create the middleware file

**File:** Create `NOVEMBER/PGP_v1/common/oidc_auth.py`

```bash
# Create common directory
mkdir -p /home/user/TelegramFunnel/NOVEMBER/PGP_v1/common
touch /home/user/TelegramFunnel/NOVEMBER/PGP_v1/common/__init__.py
```

### 1.2 Write the OIDC middleware

**File:** `common/oidc_auth.py`

```python
#!/usr/bin/env python
"""
OIDC Authentication Middleware for PayGatePrime v1
Verifies Google Cloud OIDC tokens for service-to-service authentication.

This middleware protects Cloud Run services from unauthorized access by
verifying that incoming requests contain valid OIDC tokens issued by Google.

Usage:
    from common.oidc_auth import require_oidc_token

    @app.route('/internal-endpoint', methods=['POST'])
    @require_oidc_token
    def internal_endpoint():
        # Only accessible with valid OIDC token
        pass
"""
import os
from functools import wraps
from flask import request, jsonify, abort
import google.auth.transport.requests
import google.oauth2.id_token


# Configuration
OIDC_ENFORCEMENT = os.getenv('OIDC_ENFORCEMENT', 'true').lower() == 'true'
ALLOWED_SERVICE_ACCOUNTS = os.getenv('ALLOWED_SERVICE_ACCOUNTS', '').split(',')


def require_oidc_token(f):
    """
    Decorator to verify Google Cloud OIDC tokens on internal service endpoints.

    Security Features:
    - Verifies token signature using Google's public keys
    - Validates token issuer (must be Google)
    - Checks token expiration
    - Optionally restricts to specific service accounts

    Args:
        f: The Flask route function to protect

    Returns:
        Wrapped function that requires valid OIDC token

    Raises:
        401: If token is missing, invalid, or expired

    Example:
        @app.route('/process-task', methods=['POST'])
        @require_oidc_token
        def process_task():
            # This endpoint now requires valid OIDC token
            claims = request.oidc_claims
            print(f"Called by: {claims.get('email')}")
            return jsonify({"status": "success"})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip OIDC check if explicitly disabled (for local testing only)
        if not OIDC_ENFORCEMENT:
            print("⚠️ [OIDC] Token verification DISABLED (testing mode)")
            request.oidc_claims = {"email": "local-testing@test.local"}
            return f(*args, **kwargs)

        # Get Authorization header
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            print("❌ [OIDC] Missing or invalid Authorization header")
            print(f"   Received: {auth_header[:50] if auth_header else '(empty)'}")
            abort(401, description="Unauthorized - Missing or invalid Authorization header")

        # Extract token
        token = auth_header.split(' ', 1)[1]

        try:
            # Verify the OIDC token
            # This automatically:
            # - Validates token signature using Google's public keys
            # - Checks token expiration
            # - Verifies token hasn't been tampered with
            auth_req = google.auth.transport.requests.Request()

            # Get the service URL to use as audience
            # Cloud Run sets this in X-Forwarded-Proto and X-Forwarded-Host headers
            scheme = request.headers.get('X-Forwarded-Proto', 'https')
            host = request.headers.get('X-Forwarded-Host', request.host)
            audience = f"{scheme}://{host}"

            print(f"🔐 [OIDC] Verifying token for audience: {audience}")

            id_info = google.oauth2.id_token.verify_oauth2_token(
                token,
                auth_req,
                audience=audience
            )

            # Verify issuer (must be Google)
            issuer = id_info.get('iss', '')
            valid_issuers = [
                'https://accounts.google.com',
                'accounts.google.com'
            ]

            if issuer not in valid_issuers:
                print(f"❌ [OIDC] Invalid token issuer: {issuer}")
                print(f"   Valid issuers: {valid_issuers}")
                abort(401, description="Unauthorized - Invalid token issuer")

            # Optional: Check if token is from allowed service account
            email = id_info.get('email', '')
            if ALLOWED_SERVICE_ACCOUNTS and ALLOWED_SERVICE_ACCOUNTS[0]:
                if email not in ALLOWED_SERVICE_ACCOUNTS:
                    print(f"❌ [OIDC] Service account not allowed: {email}")
                    print(f"   Allowed accounts: {ALLOWED_SERVICE_ACCOUNTS}")
                    abort(403, description="Forbidden - Service account not authorized")

            # Token is valid - attach claims to request for use in handler
            request.oidc_claims = id_info

            print(f"✅ [OIDC] Valid token verified")
            print(f"   Email: {email}")
            print(f"   Subject: {id_info.get('sub', 'N/A')}")
            print(f"   Issued at: {id_info.get('iat', 'N/A')}")
            print(f"   Expires at: {id_info.get('exp', 'N/A')}")

        except ValueError as e:
            # Token verification failed
            print(f"❌ [OIDC] Token verification failed: {e}")
            abort(401, description="Unauthorized - Invalid or expired token")

        except Exception as e:
            # Unexpected error during verification
            print(f"❌ [OIDC] Unexpected error during token verification: {e}")
            abort(500, description="Internal server error during authentication")

        return f(*args, **kwargs)

    return decorated_function


def verify_oidc_token_manual(token: str, audience: str) -> dict:
    """
    Manually verify an OIDC token (for non-decorator use cases).

    Args:
        token: The OIDC token to verify
        audience: Expected audience (usually the service URL)

    Returns:
        dict: Token claims if valid

    Raises:
        ValueError: If token is invalid

    Example:
        try:
            claims = verify_oidc_token_manual(token, "https://my-service.run.app")
            print(f"Token valid for: {claims['email']}")
        except ValueError as e:
            print(f"Invalid token: {e}")
    """
    auth_req = google.auth.transport.requests.Request()
    id_info = google.oauth2.id_token.verify_oauth2_token(
        token,
        auth_req,
        audience=audience
    )

    # Verify issuer
    issuer = id_info.get('iss', '')
    valid_issuers = ['https://accounts.google.com', 'accounts.google.com']

    if issuer not in valid_issuers:
        raise ValueError(f"Invalid issuer: {issuer}")

    return id_info
```

---

## Step 2: Update requirements.txt

Add the required dependency to **ALL 11 services**:

**Files to update:**
```
GCWebhook1-PGP/requirements.txt
GCWebhook2-PGP/requirements.txt
GCSplit1-PGP/requirements.txt
GCSplit2-PGP/requirements.txt
GCSplit3-PGP/requirements.txt
GCHostPay1-PGP/requirements.txt
GCHostPay2-PGP/requirements.txt
GCHostPay3-PGP/requirements.txt
GCAccumulator-PGP/requirements.txt
GCBatchProcessor-PGP/requirements.txt
GCMicroBatchProcessor-PGP/requirements.txt
```

**Add this line to each:**
```text
google-auth==2.23.4
```

---

## Step 3: Apply OIDC Decorator to Service Endpoints

### 3.1 Example: GCWebhook1-PGP (pgp-webhook1-v1)

**File:** `GCWebhook1-PGP/tph1-10-26.py`

**Current code (around line 108):**
```python
@app.route('/', methods=['POST'])
def handle_payment_task():
    """
    Receive task from GCTriggerService (np-webhook).
    """
```

**Updated code:**
```python
import sys
sys.path.append('/workspace')  # Add parent directory to path for common imports
from common.oidc_auth import require_oidc_token

@app.route('/', methods=['POST'])
@require_oidc_token  # ✅ ADD THIS LINE
def handle_payment_task():
    """
    Receive task from GCTriggerService (np-webhook).
    SECURITY: Protected by OIDC token verification.
    """
    # Get authenticated caller info
    caller_email = request.oidc_claims.get('email', 'unknown')
    print(f"🔐 [AUTH] Request from authenticated service: {caller_email}")
```

### 3.2 Apply to ALL Internal Endpoints

**Services & Files to Update:**

| Service | File | Endpoint | Line # (approx) |
|---------|------|----------|-----------------|
| **GCWebhook1-PGP** | tph1-10-26.py | `@app.route('/', methods=['POST'])` | ~108 |
| **GCWebhook2-PGP** | tph2-10-26.py | `@app.route('/', methods=['POST'])` | ~185 |
| **GCSplit1-PGP** | tps1-10-26.py | `@app.route('/process', methods=['POST'])` | ~95 |
| **GCSplit2-PGP** | tps2-10-26.py | `@app.route('/estimate', methods=['POST'])` | ~90 |
| **GCSplit3-PGP** | tps3-10-26.py | `@app.route('/convert', methods=['POST'])` | ~85 |
| **GCHostPay1-PGP** | tphp1-10-26.py | `@app.route('/query', methods=['POST'])` | ~280 |
| **GCHostPay2-PGP** | tphp2-10-26.py | `@app.route('/monitor', methods=['POST'])` | ~75 |
| **GCHostPay3-PGP** | tphp3-10-26.py | `@app.route('/validate', methods=['POST'])` | ~140 |
| **GCAccumulator-PGP** | acc10-26.py | `@app.route('/accumulate', methods=['POST'])` | ~90 |
| **GCBatchProcessor-PGP** | bp10-26.py | `@app.route('/process-batch', methods=['POST'])` | ~70 |
| **GCMicroBatchProcessor-PGP** | mbp10-26.py | `@app.route('/process-micro', methods=['POST'])` | ~75 |

**Pattern to apply to each:**
```python
# Add to top of file
import sys
sys.path.append('/workspace')
from common.oidc_auth import require_oidc_token

# Add decorator to endpoint
@app.route('/your-endpoint', methods=['POST'])
@require_oidc_token  # ✅ ADD THIS
def your_handler():
    # Get caller info if needed
    caller = request.oidc_claims.get('email', 'unknown')
    print(f"🔐 [AUTH] Authenticated call from: {caller}")
    # ... rest of handler code
```

---

## Step 4: Update Dockerfiles (if using custom images)

If any services use custom Dockerfiles, ensure the common directory is copied:

**File:** `GCWebhook1-PGP/Dockerfile` (if exists)

```dockerfile
FROM python:3.11-slim

WORKDIR /workspace

# Copy common directory
COPY ../common ./common

# Copy service files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run service
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 tph1-10-26:app
```

---

## Step 5: Testing OIDC Implementation

### 5.1 Local Testing (Disable OIDC)

For local development, disable OIDC enforcement:

```bash
export OIDC_ENFORCEMENT=false
python tph1-10-26.py
```

### 5.2 Test Invalid Token (Should Fail)

```bash
# Deploy service first
gcloud run deploy pgp-webhook1-v1 --source . --region us-central1

# Get service URL
SERVICE_URL=$(gcloud run services describe pgp-webhook1-v1 --region us-central1 --format='value(status.url)')

# Test without token (should fail with 401)
curl -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Expected output: 401 Unauthorized
```

### 5.3 Test Valid Token (Should Succeed)

```bash
# Get valid OIDC token for your user
TOKEN=$(gcloud auth print-identity-token)

# Test with valid token (should succeed)
curl -X POST $SERVICE_URL/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Expected output: Endpoint response (not 401)
```

### 5.4 Test Cloud Tasks Integration

Cloud Tasks automatically sends OIDC tokens. Trigger a task and check logs:

```bash
# Trigger a payment flow that uses Cloud Tasks
# Check service logs for OIDC verification messages

gcloud run services logs read pgp-webhook1-v1 --region us-central1 --limit 50

# Look for:
# ✅ [OIDC] Valid token verified
# Email: PROJECT_NUMBER-compute@developer.gserviceaccount.com
```

---

## Step 6: Verification Checklist

- [ ] Created `common/oidc_auth.py` with OIDC middleware
- [ ] Added `google-auth==2.23.4` to all 11 services' requirements.txt
- [ ] Applied `@require_oidc_token` decorator to all internal endpoints (11 services)
- [ ] Updated Dockerfiles to copy common directory (if applicable)
- [ ] Tested locally with OIDC_ENFORCEMENT=false
- [ ] Tested deployed service rejects requests without token (401)
- [ ] Tested deployed service accepts valid OIDC token
- [ ] Verified Cloud Tasks calls work (check logs for ✅ OIDC messages)
- [ ] Removed any test/debug endpoints that bypass OIDC

---

# PART 2: HTTP Security Headers (Flask-Talisman)

## 🎯 Goal
Add security headers to prevent XSS, clickjacking, and other HTTP-based attacks.

## 📊 Affected Services (15 total - ALL services)

---

## Step 1: Install Flask-Talisman

### 1.1 Update requirements.txt for ALL services

**Files to update (15 total):**
```
GCRegisterAPI-PGP/requirements.txt
np-webhook-PGP/requirements.txt
GCWebhook1-PGP/requirements.txt
GCWebhook2-PGP/requirements.txt
GCSplit1-PGP/requirements.txt
GCSplit2-PGP/requirements.txt
GCSplit3-PGP/requirements.txt
GCHostPay1-PGP/requirements.txt
GCHostPay2-PGP/requirements.txt
GCHostPay3-PGP/requirements.txt
GCAccumulator-PGP/requirements.txt
GCBatchProcessor-PGP/requirements.txt
GCMicroBatchProcessor-PGP/requirements.txt
TelePay-PGP/requirements.txt
GCRegisterWeb-PGP/requirements.txt (if applicable)
```

**Add this line:**
```text
flask-talisman==1.1.0
```

---

## Step 2: Create Talisman Configuration Module

**File:** Create `common/security_headers.py`

```python
#!/usr/bin/env python
"""
Security Headers Configuration for PayGatePrime v1
Provides Flask-Talisman configurations for different service types.

Usage:
    from common.security_headers import apply_security_headers

    app = Flask(__name__)
    apply_security_headers(app, service_type='internal')
"""
from flask_talisman import Talisman


# Strict CSP for internal services (API-only, no frontend)
INTERNAL_SERVICE_CSP = {
    'default-src': "'none'",
    'script-src': "'none'",
    'style-src': "'none'",
    'img-src': "'none'",
    'font-src': "'none'",
    'connect-src': "'none'",
    'frame-ancestors': "'none'"
}

# Moderate CSP for public API (may serve JSON, needs connect-src)
PUBLIC_API_CSP = {
    'default-src': "'self'",
    'script-src': ["'self'"],
    'style-src': ["'self'", "'unsafe-inline'"],  # For error pages
    'img-src': ["'self'", "data:"],
    'connect-src': ["'self'"],
    'frame-ancestors': "'none'"
}

# Permissive CSP for frontend (React app needs more access)
FRONTEND_CSP = {
    'default-src': "'self'",
    'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'"],  # React needs eval
    'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    'img-src': ["'self'", "data:", "https:"],
    'font-src': ["'self'", "data:", "https://fonts.gstatic.com"],
    'connect-src': ["'self'", "https://www.paygateprime.com"],
    'frame-ancestors': "'none'"
}


def apply_security_headers(app, service_type='internal'):
    """
    Apply Flask-Talisman security headers to Flask app.

    Args:
        app: Flask application instance
        service_type: Type of service ('internal', 'public_api', 'frontend')

    Returns:
        Talisman instance

    Example:
        app = Flask(__name__)
        talisman = apply_security_headers(app, service_type='internal')
    """
    # Select CSP based on service type
    if service_type == 'internal':
        csp = INTERNAL_SERVICE_CSP
        frame_options = 'DENY'
    elif service_type == 'public_api':
        csp = PUBLIC_API_CSP
        frame_options = 'DENY'
    elif service_type == 'frontend':
        csp = FRONTEND_CSP
        frame_options = 'DENY'
    else:
        raise ValueError(f"Unknown service_type: {service_type}")

    # Apply Talisman with strict security headers
    talisman = Talisman(
        app,

        # Force HTTPS (Cloud Run already does this, but double-check)
        force_https=True,
        force_https_permanent=False,  # Use 302 redirects

        # HSTS - Tell browsers to always use HTTPS
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,  # 1 year
        strict_transport_security_include_subdomains=True,
        strict_transport_security_preload=False,  # Don't preload by default

        # Content Security Policy
        content_security_policy=csp,
        content_security_policy_report_only=False,  # Enforce (not just report)

        # X-Frame-Options - Prevent clickjacking
        frame_options=frame_options,

        # X-Content-Type-Options - Prevent MIME sniffing
        content_type_options=True,
        content_type_options_value='nosniff',

        # Referrer-Policy - Control referrer information
        referrer_policy='strict-origin-when-cross-origin',

        # Feature-Policy / Permissions-Policy
        feature_policy={
            'geolocation': "'none'",
            'camera': "'none'",
            'microphone': "'none'",
            'payment': "'none'"  # Disable browser payment API
        }
    )

    print(f"🔐 [SECURITY] Flask-Talisman enabled (service_type={service_type})")
    print(f"   ✅ HTTPS enforcement: ON")
    print(f"   ✅ HSTS: ON (max-age=1 year)")
    print(f"   ✅ CSP: {csp}")
    print(f"   ✅ X-Frame-Options: {frame_options}")
    print(f"   ✅ X-Content-Type-Options: nosniff")

    return talisman
```

---

## Step 3: Apply Security Headers to Each Service

### 3.1 Internal Services (11 services)

**Example: GCWebhook1-PGP/tph1-10-26.py**

**Add near top of file (after Flask import):**
```python
from flask import Flask, request, jsonify
import sys
sys.path.append('/workspace')
from common.security_headers import apply_security_headers

app = Flask(__name__)

# Apply security headers for internal service
apply_security_headers(app, service_type='internal')

# ... rest of code
```

**Apply to these files:**
- GCWebhook1-PGP/tph1-10-26.py
- GCWebhook2-PGP/tph2-10-26.py
- GCSplit1-PGP/tps1-10-26.py
- GCSplit2-PGP/tps2-10-26.py
- GCSplit3-PGP/tps3-10-26.py
- GCHostPay1-PGP/tphp1-10-26.py
- GCHostPay2-PGP/tphp2-10-26.py
- GCHostPay3-PGP/tphp3-10-26.py
- GCAccumulator-PGP/acc10-26.py
- GCBatchProcessor-PGP/bp10-26.py
- GCMicroBatchProcessor-PGP/mbp10-26.py

### 3.2 Public API Service (1 service)

**File: GCRegisterAPI-PGP/app.py** (or wherever Flask app is created)

```python
from flask import Flask
import sys
sys.path.append('/workspace')
from common.security_headers import apply_security_headers

app = Flask(__name__)

# Apply security headers for public API
apply_security_headers(app, service_type='public_api')

# ... rest of code
```

### 3.3 Webhook Service with CORS (1 service)

**File: np-webhook-PGP/app.py**

**Current code (around line 17-42):**
```python
app = Flask(__name__)

# Configure CORS
CORS(app, resources={...})
```

**Updated code:**
```python
app = Flask(__name__)

# Apply security headers FIRST
import sys
sys.path.append('/workspace')
from common.security_headers import apply_security_headers
talisman = apply_security_headers(app, service_type='public_api')

# Configure CORS AFTER Talisman
CORS(app, resources={...})
```

### 3.4 Telegram Bot (1 service)

**File: TelePay-PGP/telepay10-26.py** (or main file)

If the bot has a Flask web interface:
```python
app = Flask(__name__)

import sys
sys.path.append('/workspace')
from common.security_headers import apply_security_headers
apply_security_headers(app, service_type='internal')
```

### 3.5 Frontend Service (1 service - if applicable)

**File: GCRegisterWeb-PGP** (React frontend)

If serving React through Flask:
```python
app = Flask(__name__)

import sys
sys.path.append('/workspace')
from common.security_headers import apply_security_headers
apply_security_headers(app, service_type='frontend')
```

---

## Step 4: Testing Security Headers

### 4.1 Test Headers are Present

```bash
# Deploy a service
gcloud run deploy pgp-webhook1-v1 --source . --region us-central1

# Get service URL
SERVICE_URL=$(gcloud run services describe pgp-webhook1-v1 --region us-central1 --format='value(status.url)')

# Check headers
curl -I $SERVICE_URL

# Expected headers:
# Strict-Transport-Security: max-age=31536000; includeSubDomains
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Content-Security-Policy: default-src 'none'; ...
# Referrer-Policy: strict-origin-when-cross-origin
```

### 4.2 Test CSP Blocks Unwanted Content

If service has any HTML response:
```bash
# Try to load external script (should be blocked by CSP)
curl $SERVICE_URL | grep -i "content-security-policy"
```

### 4.3 Automated Testing Script

Create a test script:

**File:** `deployment_scripts/test_security_headers.sh`

```bash
#!/bin/bash
# Test security headers on all services

SERVICES=(
  "pgp-server-v1"
  "pgp-npwebhook-v1"
  "pgp-webhook1-v1"
  "pgp-webhook2-v1"
  "pgp-split1-v1"
  # ... add all 15 services
)

REGION="us-central1"

echo "🔐 Testing Security Headers"
echo "=============================="

for service in "${SERVICES[@]}"; do
  echo ""
  echo "Testing: $service"

  URL=$(gcloud run services describe $service --region=$REGION --format='value(status.url)' 2>/dev/null)

  if [ -z "$URL" ]; then
    echo "⚠️  Service not deployed"
    continue
  fi

  # Check for HSTS
  HSTS=$(curl -sI $URL | grep -i "strict-transport-security")
  if [ -z "$HSTS" ]; then
    echo "❌ HSTS header missing"
  else
    echo "✅ HSTS: $HSTS"
  fi

  # Check for X-Frame-Options
  XFO=$(curl -sI $URL | grep -i "x-frame-options")
  if [ -z "$XFO" ]; then
    echo "❌ X-Frame-Options missing"
  else
    echo "✅ X-Frame-Options: $XFO"
  fi

  # Check for CSP
  CSP=$(curl -sI $URL | grep -i "content-security-policy")
  if [ -z "$CSP" ]; then
    echo "❌ CSP header missing"
  else
    echo "✅ CSP: ${CSP:0:80}..."
  fi
done
```

---

## Step 5: Verification Checklist

- [ ] Added `flask-talisman==1.1.0` to all 15 services' requirements.txt
- [ ] Created `common/security_headers.py` with Talisman configs
- [ ] Applied security headers to all internal services (11 services)
- [ ] Applied security headers to public API (1 service)
- [ ] Applied security headers to webhook service (1 service)
- [ ] Applied security headers to bot/frontend (2 services)
- [ ] Tested deployed service has HSTS header
- [ ] Tested deployed service has X-Frame-Options header
- [ ] Tested deployed service has CSP header
- [ ] Tested deployed service has X-Content-Type-Options header
- [ ] Verified CORS still works (for np-webhook-PGP)
- [ ] Ran automated header test script on all services

---

# PART 3: Input Validation (Payment Data)

## 🎯 Goal
Add comprehensive validation for payment amounts, wallet addresses, and transaction data.

## 📊 Affected Files (5 main entry points)
- np-webhook-PGP/app.py (NowPayments IPN)
- GCWebhook1-PGP/tph1-10-26.py (Payment processing)
- GCRegisterAPI-PGP/api/routes/payments.py (API endpoint - if exists)
- GCSplit1-PGP/tps1-10-26.py (Split processing)
- GCAccumulator-PGP/acc10-26.py (Accumulator)

---

## Step 1: Create Validation Module

**File:** Create `common/validators.py`

```python
#!/usr/bin/env python
"""
Input Validation for PayGatePrime v1
Comprehensive validation for payment amounts, wallet addresses, and transaction data.

Usage:
    from common.validators import PaymentValidator, WalletValidator

    # Validate payment amount
    is_valid, amount, error = PaymentValidator.validate_amount("100.50", "USD")
    if not is_valid:
        return jsonify({"error": error}), 400

    # Validate wallet address
    is_valid, error = WalletValidator.validate_ethereum_address("0x...")
    if not is_valid:
        return jsonify({"error": error}), 400
"""
import re
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Tuple, Optional


class PaymentValidator:
    """Validates payment amounts with comprehensive checks"""

    # Payment limits
    MIN_AMOUNT_USD = Decimal("1.00")  # $1 minimum
    MAX_AMOUNT_USD = Decimal("50000.00")  # $50k maximum per transaction
    MAX_DECIMAL_PLACES = 8  # Maximum precision for crypto

    # Supported currencies
    SUPPORTED_CURRENCIES = {'USD', 'USDT', 'ETH', 'BTC', 'MATIC'}

    @staticmethod
    def validate_amount(
        amount: str,
        currency: str = "USD",
        min_override: Optional[Decimal] = None,
        max_override: Optional[Decimal] = None
    ) -> Tuple[bool, Optional[Decimal], str]:
        """
        Validate payment amount with comprehensive checks.

        Args:
            amount: Amount as string
            currency: Currency code (USD, USDT, etc.)
            min_override: Optional minimum amount override
            max_override: Optional maximum amount override

        Returns:
            (is_valid, decimal_amount, error_message)

        Example:
            is_valid, amt, err = PaymentValidator.validate_amount("100.50", "USD")
            if not is_valid:
                return jsonify({"error": err}), 400
        """
        # Validate currency
        if currency.upper() not in PaymentValidator.SUPPORTED_CURRENCIES:
            return False, None, f"Unsupported currency: {currency}"

        # Check for None or empty
        if amount is None or str(amount).strip() == '':
            return False, None, "Amount is required"

        # Convert to string and clean
        amount_str = str(amount).strip()

        # Check for scientific notation (not allowed)
        if 'e' in amount_str.lower():
            return False, None, "Scientific notation not allowed"

        # Try to convert to Decimal
        try:
            decimal_amount = Decimal(amount_str)
        except (InvalidOperation, ValueError, TypeError) as e:
            return False, None, f"Invalid amount format: {amount_str}"

        # Check for NaN or Infinity
        if decimal_amount.is_nan() or decimal_amount.is_infinite():
            return False, None, "Invalid amount value"

        # Check for negative or zero
        if decimal_amount <= 0:
            return False, None, "Amount must be positive"

        # Check minimum
        min_amount = min_override if min_override is not None else PaymentValidator.MIN_AMOUNT_USD
        if decimal_amount < min_amount:
            return False, None, f"Amount below minimum (${min_amount})"

        # Check maximum (anti-money laundering)
        max_amount = max_override if max_override is not None else PaymentValidator.MAX_AMOUNT_USD
        if decimal_amount > max_amount:
            return False, None, f"Amount exceeds maximum (${max_amount})"

        # Check decimal places
        decimal_tuple = decimal_amount.as_tuple()
        if decimal_tuple.exponent < 0:  # Has decimal places
            decimal_places = abs(decimal_tuple.exponent)
            if decimal_places > PaymentValidator.MAX_DECIMAL_PLACES:
                return False, None, f"Too many decimal places (max {PaymentValidator.MAX_DECIMAL_PLACES})"

        # All checks passed
        return True, decimal_amount, ""

    @staticmethod
    def validate_transaction_id(tx_id: str) -> Tuple[bool, str]:
        """
        Validate transaction/payment ID format.

        Args:
            tx_id: Transaction ID to validate

        Returns:
            (is_valid, error_message)
        """
        if not tx_id or not isinstance(tx_id, str):
            return False, "Transaction ID is required"

        tx_id = tx_id.strip()

        # Check length (reasonable limits)
        if len(tx_id) < 5:
            return False, "Transaction ID too short"

        if len(tx_id) > 200:
            return False, "Transaction ID too long"

        # Check for dangerous characters
        if any(char in tx_id for char in ['<', '>', '"', "'", '\\', '\0']):
            return False, "Transaction ID contains invalid characters"

        return True, ""


class WalletValidator:
    """Validates cryptocurrency wallet addresses"""

    # Ethereum/Polygon address: 0x followed by 40 hex characters
    ETH_ADDRESS_PATTERN = re.compile(r'^0x[a-fA-F0-9]{40}$')

    # Bitcoin Legacy: starts with 1 or 3
    BTC_LEGACY_PATTERN = re.compile(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$')

    # Bitcoin SegWit: starts with bc1
    BTC_SEGWIT_PATTERN = re.compile(r'^bc1[a-z0-9]{39,59}$')

    @staticmethod
    def validate_ethereum_address(address: str) -> Tuple[bool, str]:
        """
        Validate Ethereum/Polygon wallet address.

        Args:
            address: Wallet address to validate

        Returns:
            (is_valid, error_message)

        Example:
            is_valid, err = WalletValidator.validate_ethereum_address("0x...")
            if not is_valid:
                return jsonify({"error": err}), 400
        """
        if not address or not isinstance(address, str):
            return False, "Wallet address is required"

        address = address.strip()

        # Check format
        if not WalletValidator.ETH_ADDRESS_PATTERN.match(address):
            return False, "Invalid Ethereum address format (must be 0x + 40 hex chars)"

        # Optional: Add EIP-55 checksum validation
        # For now, format check is sufficient

        return True, ""

    @staticmethod
    def validate_bitcoin_address(address: str) -> Tuple[bool, str]:
        """
        Validate Bitcoin wallet address (Legacy or SegWit).

        Args:
            address: Bitcoin address to validate

        Returns:
            (is_valid, error_message)
        """
        if not address or not isinstance(address, str):
            return False, "Bitcoin address is required"

        address = address.strip()

        # Check Legacy format
        if WalletValidator.BTC_LEGACY_PATTERN.match(address):
            return True, ""

        # Check SegWit format
        if WalletValidator.BTC_SEGWIT_PATTERN.match(address):
            return True, ""

        return False, "Invalid Bitcoin address format"

    @staticmethod
    def validate_address(address: str, currency: str) -> Tuple[bool, str]:
        """
        Validate wallet address based on currency.

        Args:
            address: Wallet address
            currency: Currency type (ETH, BTC, MATIC, etc.)

        Returns:
            (is_valid, error_message)
        """
        currency = currency.upper()

        if currency in ['ETH', 'MATIC', 'USDT']:  # USDT on Polygon
            return WalletValidator.validate_ethereum_address(address)
        elif currency == 'BTC':
            return WalletValidator.validate_bitcoin_address(address)
        else:
            # Unknown currency - basic check
            if not address or len(address) < 10:
                return False, f"Invalid {currency} address"
            return True, ""


class OrderValidator:
    """Validates order/request data"""

    @staticmethod
    def validate_order_id(order_id: str) -> Tuple[bool, str]:
        """
        Validate order ID format.

        Args:
            order_id: Order ID from payment request

        Returns:
            (is_valid, error_message)
        """
        if not order_id or not isinstance(order_id, str):
            return False, "Order ID is required"

        order_id = order_id.strip()

        # Check length
        if len(order_id) < 1:
            return False, "Order ID cannot be empty"

        if len(order_id) > 100:
            return False, "Order ID too long (max 100 characters)"

        # Check for SQL injection patterns
        dangerous_patterns = ['--', ';', '/*', '*/', 'xp_', 'sp_', 'DROP', 'DELETE', 'INSERT', 'UPDATE']
        order_id_upper = order_id.upper()
        if any(pattern in order_id_upper for pattern in dangerous_patterns):
            return False, "Order ID contains invalid characters"

        return True, ""

    @staticmethod
    def validate_payment_status(status: str) -> Tuple[bool, str]:
        """
        Validate payment status value.

        Args:
            status: Payment status from webhook

        Returns:
            (is_valid, error_message)
        """
        if not status or not isinstance(status, str):
            return False, "Payment status is required"

        # Valid statuses from NowPayments
        valid_statuses = [
            'waiting', 'confirming', 'confirmed', 'sending',
            'partially_paid', 'finished', 'failed', 'refunded', 'expired'
        ]

        if status.lower() not in valid_statuses:
            return False, f"Invalid payment status: {status}"

        return True, ""
```

---

## Step 2: Apply Validation to Payment Entry Points

### 2.1 NowPayments IPN Webhook

**File:** `np-webhook-PGP/app.py`

**Find the IPN handler (around line 615):**

```python
# Current code (after signature verification)
try:
    ipn_data = request.get_json()
    # ... process ipn_data
```

**Add validation:**

```python
import sys
sys.path.append('/workspace')
from common.validators import PaymentValidator, OrderValidator

# After signature verification and JSON parsing:
try:
    ipn_data = request.get_json()

    # ============================================================================
    # STEP 1: Validate payment status
    # ============================================================================
    payment_status = ipn_data.get('payment_status', '')
    is_valid, error = OrderValidator.validate_payment_status(payment_status)
    if not is_valid:
        print(f"❌ [VALIDATION] Invalid payment status: {error}")
        abort(400, description=error)

    # ============================================================================
    # STEP 2: Validate order ID
    # ============================================================================
    order_id = ipn_data.get('order_id', '')
    is_valid, error = OrderValidator.validate_order_id(order_id)
    if not is_valid:
        print(f"❌ [VALIDATION] Invalid order ID: {error}")
        abort(400, description=error)

    # ============================================================================
    # STEP 3: Validate payment amount
    # ============================================================================
    price_amount = ipn_data.get('price_amount')
    price_currency = ipn_data.get('price_currency', 'USD')

    if price_amount:
        is_valid, validated_amount, error = PaymentValidator.validate_amount(
            price_amount,
            price_currency
        )
        if not is_valid:
            print(f"❌ [VALIDATION] Invalid payment amount: {error}")
            print(f"   Received: {price_amount} {price_currency}")
            abort(400, description=f"Invalid payment amount: {error}")

        print(f"✅ [VALIDATION] Payment amount validated: ${validated_amount} {price_currency}")

    # ============================================================================
    # STEP 4: Validate pay address (if present)
    # ============================================================================
    pay_address = ipn_data.get('pay_address')
    pay_currency = ipn_data.get('pay_currency', '')

    if pay_address and pay_currency:
        from common.validators import WalletValidator
        is_valid, error = WalletValidator.validate_address(pay_address, pay_currency)
        if not is_valid:
            print(f"⚠️ [VALIDATION] Invalid pay address: {error}")
            # Don't abort - this is provided by NowPayments, log warning only
        else:
            print(f"✅ [VALIDATION] Pay address validated: {pay_address[:10]}...")

    # Continue with normal IPN processing...
```

### 2.2 GCWebhook1 (Payment Processor)

**File:** `GCWebhook1-PGP/tph1-10-26.py`

**Find where request data is received (around line 130):**

```python
import sys
sys.path.append('/workspace')
from common.validators import PaymentValidator, OrderValidator

@app.route('/', methods=['POST'])
@require_oidc_token
def handle_payment_task():
    request_data = request.get_json()

    # Validate order_id
    order_id = request_data.get('order_id')
    is_valid, error = OrderValidator.validate_order_id(order_id)
    if not is_valid:
        print(f"❌ [VALIDATION] {error}")
        return jsonify({"error": error, "status": "failed"}), 400

    # Validate payment amount (if in request)
    if 'price_amount' in request_data:
        is_valid, amount, error = PaymentValidator.validate_amount(
            request_data['price_amount'],
            request_data.get('price_currency', 'USD')
        )
        if not is_valid:
            print(f"❌ [VALIDATION] {error}")
            return jsonify({"error": error, "status": "failed"}), 400

    # Validate wallet address
    if 'wallet_address' in request_data:
        from common.validators import WalletValidator
        is_valid, error = WalletValidator.validate_address(
            request_data['wallet_address'],
            request_data.get('payout_currency', 'ETH')
        )
        if not is_valid:
            print(f"❌ [VALIDATION] {error}")
            return jsonify({"error": error, "status": "failed"}), 400

    # Continue with processing...
```

### 2.3 API Endpoint (if exists)

**File:** `GCRegisterAPI-PGP/api/routes/payments.py` (if it exists)

```python
from common.validators import PaymentValidator, WalletValidator, OrderValidator

@app.route('/api/payments', methods=['POST'])
@jwt_required()  # User must be authenticated
def create_payment():
    data = request.get_json()

    # Validate amount
    is_valid, amount, error = PaymentValidator.validate_amount(
        data.get('amount'),
        data.get('currency', 'USD')
    )
    if not is_valid:
        return jsonify({"error": error}), 400

    # Validate wallet address
    is_valid, error = WalletValidator.validate_address(
        data.get('wallet_address'),
        data.get('currency')
    )
    if not is_valid:
        return jsonify({"error": error}), 400

    # Process payment...
```

---

## Step 3: Testing Input Validation

### 3.1 Test Amount Validation

```bash
# Test negative amount (should fail)
curl -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{
    "price_amount": "-100",
    "price_currency": "USD",
    "order_id": "test-123"
  }'

# Expected: 400 Bad Request
# Error: "Amount must be positive"

# Test excessive decimal places (should fail)
curl -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{
    "price_amount": "10.123456789",
    "price_currency": "USD",
    "order_id": "test-123"
  }'

# Expected: 400 Bad Request
# Error: "Too many decimal places (max 8)"

# Test amount exceeding maximum (should fail)
curl -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{
    "price_amount": "99999999",
    "price_currency": "USD",
    "order_id": "test-123"
  }'

# Expected: 400 Bad Request
# Error: "Amount exceeds maximum ($50000.00)"

# Test valid amount (should succeed)
curl -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{
    "price_amount": "100.50",
    "price_currency": "USD",
    "order_id": "test-123"
  }'

# Expected: Proceeds to next validation step
```

### 3.2 Test Wallet Address Validation

```bash
# Test invalid Ethereum address (should fail)
curl -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_address": "invalid-address",
    "currency": "ETH"
  }'

# Expected: 400 Bad Request
# Error: "Invalid Ethereum address format"

# Test valid Ethereum address (should succeed)
curl -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
    "currency": "ETH"
  }'

# Expected: Validation passes
```

### 3.3 Automated Validation Tests

Create test script:

**File:** `deployment_scripts/test_input_validation.sh`

```bash
#!/bin/bash
# Test input validation

SERVICE_URL="https://pgp-npwebhook-v1.run.app"

echo "🧪 Testing Input Validation"
echo "==========================="

# Test 1: Negative amount
echo -e "\n Test 1: Negative amount (should fail)"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{"price_amount": "-100", "price_currency": "USD"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "400" ]; then
  echo "✅ PASS - Rejected negative amount"
else
  echo "❌ FAIL - Should reject negative amount (got $HTTP_CODE)"
fi

# Test 2: Excessive decimals
echo -e "\nTest 2: Excessive decimals (should fail)"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{"price_amount": "10.123456789", "price_currency": "USD"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "400" ]; then
  echo "✅ PASS - Rejected excessive decimals"
else
  echo "❌ FAIL - Should reject excessive decimals (got $HTTP_CODE)"
fi

# Test 3: Valid amount
echo -e "\nTest 3: Valid amount (should pass validation)"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST $SERVICE_URL/ \
  -H "Content-Type: application/json" \
  -d '{"price_amount": "100.50", "price_currency": "USD"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
# Note: May still fail due to missing other required fields, but shouldn't fail on amount
echo "HTTP Code: $HTTP_CODE (validation passed if not 400 with amount error)"
```

---

## Step 4: Verification Checklist

- [ ] Created `common/validators.py` with all validator classes
- [ ] Added validation to np-webhook-PGP IPN handler
- [ ] Added validation to GCWebhook1-PGP payment processor
- [ ] Added validation to API payment endpoints (if exist)
- [ ] Added validation to other payment entry points
- [ ] Tested negative amount is rejected (400)
- [ ] Tested excessive decimal places rejected (400)
- [ ] Tested amount exceeding max rejected (400)
- [ ] Tested valid amount passes validation
- [ ] Tested invalid wallet address rejected (400)
- [ ] Tested valid wallet address passes validation
- [ ] Tested invalid order ID rejected (400)
- [ ] Ran automated validation test script
- [ ] Checked logs show validation messages

---

# FINAL VERIFICATION

## Complete Security Implementation Checklist

### Part 1: Service-to-Service Auth ✅
- [ ] Created common/oidc_auth.py
- [ ] Added google-auth to requirements.txt (11 services)
- [ ] Applied @require_oidc_token to all internal endpoints
- [ ] Tested token verification works
- [ ] Verified Cloud Tasks calls succeed

### Part 2: HTTP Security Headers ✅
- [ ] Created common/security_headers.py
- [ ] Added flask-talisman to requirements.txt (15 services)
- [ ] Applied headers to all services
- [ ] Tested HSTS header present
- [ ] Tested CSP header present
- [ ] Tested X-Frame-Options present

### Part 3: Input Validation ✅
- [ ] Created common/validators.py
- [ ] Applied amount validation to all entry points
- [ ] Applied wallet validation to all entry points
- [ ] Applied order ID validation
- [ ] Tested all validation rules work

### Deployment
- [ ] All 3 parts implemented
- [ ] All tests passing
- [ ] Services deployed with fixes
- [ ] Monitored logs for errors
- [ ] Security score improved from 73/100 to 90+/100

---

## Estimated Timeline

| Task | Time | Complexity |
|------|------|------------|
| **Part 1: OIDC Auth** | 4-5 hours | Medium |
| **Part 2: Security Headers** | 2-3 hours | Low |
| **Part 3: Input Validation** | 2-4 hours | Medium |
| **Testing & Verification** | 2 hours | Low |
| **TOTAL** | **10-14 hours** | **Medium** |

---

## Support & Troubleshooting

### Common Issues

**Issue 1: OIDC verification fails with "Invalid audience"**
```
Solution: Ensure audience matches service URL exactly
- Check X-Forwarded-Host header
- Verify service URL in Cloud Run console
```

**Issue 2: Talisman blocks legitimate requests**
```
Solution: Adjust CSP for specific needs
- Add domain to connect-src for API calls
- Add 'unsafe-inline' if absolutely necessary (not recommended)
```

**Issue 3: Validation too strict/too lenient**
```
Solution: Adjust limits in validators.py
- Change MIN_AMOUNT_USD / MAX_AMOUNT_USD
- Change MAX_DECIMAL_PLACES
```

---

**Implementation Guide Complete**
**Next Step:** Begin with Part 1 (OIDC), then Part 2 (Headers), then Part 3 (Validation)
