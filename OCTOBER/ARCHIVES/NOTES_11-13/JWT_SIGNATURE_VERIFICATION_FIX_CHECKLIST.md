# JWT Signature Verification Fix Checklist
**Date:** 2025-11-12
**Issue:** JWT Signature Verification Failed in GCBroadcastScheduler
**Error:** "Signature verification failed" when users try to trigger manual broadcasts

---

## Root Cause Analysis

### Error Observed
```
2025-11-12 01:58:13,485 - broadcast_web_api - WARNING - ⚠️ Invalid token: Signature verification failed
```

**User Impact:**
- Users clicking "Resend Messages" see: "Session expired. Please log in again."
- Users are automatically logged out
- Manual broadcast trigger feature is non-functional

### What's Happening

1. **User logs in** → GCRegisterAPI creates JWT token using `flask-jwt-extended`
2. **Token stored** in browser localStorage
3. **User clicks "Resend Messages"** → Frontend sends token to GCBroadcastScheduler
4. **GCBroadcastScheduler** tries to verify token using raw `PyJWT` library
5. **Signature verification fails** → "Invalid token: Signature verification failed"
6. **User sees** "Session expired" and gets logged out

### Root Cause

**LIBRARY MISMATCH: Token issuer and token verifier use incompatible JWT libraries**

#### GCRegisterAPI (Token Issuer) ✅
**File:** `/GCRegisterAPI-10-26/app.py` (lines 21, 37, 52)
```python
from flask_jwt_extended import JWTManager
app.config['JWT_SECRET_KEY'] = config['jwt_secret_key']
jwt = JWTManager(app)
```

**Token Creation:** `/GCRegisterAPI-10-26/api/services/auth_service.py` (lines 9, 212-216)
```python
from flask_jwt_extended import create_access_token, create_refresh_token

access_token = create_access_token(
    identity=user_id,
    additional_claims={'username': username},
    expires_delta=timedelta(minutes=15)
)
```

**Library:** `flask-jwt-extended` (Flask extension with special token structure)

---

#### GCBroadcastScheduler (Token Verifier) ❌
**File:** `/GCBroadcastScheduler-10-26/broadcast_web_api.py` (lines 11, 65)
```python
import jwt  # This is raw PyJWT, NOT flask-jwt-extended

payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])
```

**Library:** `PyJWT` (basic JWT library, incompatible with flask-jwt-extended tokens)

---

### Why They're Incompatible

**Flask-JWT-Extended tokens have:**
- Special claim structure (uses 'sub' for identity by default, but configurable)
- Additional claims: 'fresh', 'type' ('access' or 'refresh'), 'jti', 'iat', 'nbf', 'exp', 'csrf'
- Specific token format that PyJWT alone cannot decode without matching configuration

**Raw PyJWT expects:**
- Standard JWT structure
- No special flask-jwt-extended claims
- Different signature verification approach

**Result:** Signature verification fails because the token structure doesn't match expectations

---

### Evidence

**GCBroadcastScheduler Config:**
```bash
$ gcloud run services describe gcbroadcastscheduler-10-26 --format="yaml(spec.template.spec.containers[0].env)"

- name: JWT_SECRET_KEY_SECRET
  value: projects/telepay-459221/secrets/JWT_SECRET_KEY/versions/latest
```

**GCRegisterAPI Config:**
```bash
$ gcloud run services describe gcregisterapi-10-26 --format="yaml(spec.template.spec.containers[0].env)"

- name: JWT_SECRET_KEY
  valueFrom:
    secretKeyRef:
      key: latest
      name: JWT_SECRET_KEY
```

**Both services point to the SAME secret (`JWT_SECRET_KEY`), but:**
- ❌ GCBroadcastScheduler loads it as 65 characters (logs show "JWT secret key loaded (length: 65)")
- ❌ Token signature still fails despite using same secret
- ✅ This confirms it's a LIBRARY incompatibility, not a secret mismatch

---

## Fix Strategy

### Option A: Use Flask-JWT-Extended in GCBroadcastScheduler (RECOMMENDED) ✅

**Pros:**
- Industry-standard solution for Flask applications
- Automatic handling of flask-jwt-extended token structure
- Built-in decorators for authentication
- Consistent JWT implementation across all services
- Supports token refresh, blacklisting, and advanced features

**Cons:**
- Requires adding flask-jwt-extended dependency
- Requires Flask app context for JWT operations
- Slightly more setup than raw PyJWT

**Rationale:**
- GCBroadcastScheduler is already a Flask application
- GCRegisterAPI uses flask-jwt-extended
- Using the same library ensures compatibility
- Future-proof: all services use same JWT standard

---

### Option B: Use Raw PyJWT in Both Services ❌ REJECTED

**Pros:**
- Minimal dependencies
- Direct control over JWT encoding/decoding

**Cons:**
- **BREAKING CHANGE**: Would require rewriting GCRegisterAPI authentication
- **USER IMPACT**: All existing user sessions would be invalidated
- **HIGH RISK**: Could break other services using GCRegisterAPI tokens
- **NOT RECOMMENDED**: GCRegisterAPI is production-stable

---

### Option C: Manual Token Decoding with PyJWT ❌ REJECTED

**Pros:**
- No new dependencies

**Cons:**
- **ERROR-PRONE**: Must manually replicate flask-jwt-extended's token structure
- **MAINTENANCE BURDEN**: Must keep in sync with flask-jwt-extended updates
- **FRAGILE**: Easy to break with configuration changes
- **NOT RECOMMENDED**: Violates DRY principle

---

**DECISION:** Use Option A (Flask-JWT-Extended)

---

## Implementation Checklist

### Phase 1: Code Changes ⬜

#### Task 1.1: Update requirements.txt ⬜
**File:** `GCBroadcastScheduler-10-26/requirements.txt`

**Action:** Add flask-jwt-extended dependency

**Before:**
```txt
# Web Framework
flask>=2.3.0,<3.0.0
flask-cors>=4.0.0,<5.0.0
gunicorn>=21.0.0,<22.0.0
```

**After:**
```diff
# Web Framework
flask>=2.3.0,<3.0.0
flask-cors>=4.0.0,<5.0.0
+flask-jwt-extended>=4.5.0,<5.0.0
gunicorn>=21.0.0,<22.0.0
```

**Estimated Time:** 1 minute

---

#### Task 1.2: Update main.py - Initialize JWT ⬜
**File:** `GCBroadcastScheduler-10-26/main.py`

**Action:** Initialize JWTManager after creating Flask app

**Current Code** (lines 29-42):
```python
# Create Flask app
app = Flask(__name__)

# Configure CORS
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://www.paygateprime.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 3600
    }
})
```

**Add After CORS Configuration:**
```diff
# Create Flask app
app = Flask(__name__)

# Configure CORS
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://www.paygateprime.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

+# Configure JWT (MUST be before initializing components that use JWT)
+from flask_jwt_extended import JWTManager
+
+logger.info("🔐 Initializing JWT authentication...")
+jwt_secret_key = ConfigManager().get_jwt_secret_key()
+app.config['JWT_SECRET_KEY'] = jwt_secret_key
+app.config['JWT_ALGORITHM'] = 'HS256'
+app.config['JWT_DECODE_LEEWAY'] = 10  # 10 seconds leeway for clock skew
+jwt = JWTManager(app)
+logger.info("✅ JWT authentication initialized")

# Initialize components
logger.info("🚀 Initializing GCBroadcastScheduler-10-26...")
```

**Configuration Explained:**
- `JWT_SECRET_KEY`: Same secret used by GCRegisterAPI
- `JWT_ALGORITHM`: HS256 (same as GCRegisterAPI)
- `JWT_DECODE_LEEWAY`: 10 seconds to handle clock skew between services

**Estimated Time:** 3 minutes

---

#### Task 1.3: Update broadcast_web_api.py - Use Flask-JWT-Extended ⬜
**File:** `GCBroadcastScheduler-10-26/broadcast_web_api.py`

**Action:** Replace raw PyJWT with flask-jwt-extended decorators

**Current Import** (line 11):
```python
import jwt
```

**New Import:**
```diff
-import jwt
+from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
```

---

**Current Authentication Decorator** (lines 39-90):
```python
def authenticate_request(f):
    """
    Decorator to authenticate JWT tokens from requests.

    Expects Authorization header: "Bearer <token>"
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            logger.warning("⚠️ Missing Authorization header")
            return jsonify({'error': 'Missing Authorization header'}), 401

        try:
            # Extract token from "Bearer <token>"
            parts = auth_header.split(' ')
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                logger.warning("⚠️ Invalid Authorization header format")
                return jsonify({'error': 'Invalid Authorization header format'}), 401

            token = parts[1]

            # Decode JWT (secret key from config)
            jwt_secret = config_manager.get_jwt_secret_key()

            payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])

            # Attach client_id to request context
            # Note: The JWT should contain 'sub' or 'client_id' claim
            request.client_id = payload.get('sub') or payload.get('client_id')

            if not request.client_id:
                logger.warning("⚠️ Invalid token payload - missing client_id")
                return jsonify({'error': 'Invalid token payload'}), 401

            logger.debug(f"✅ Authenticated client: {request.client_id[:8]}...")
            return f(*args, **kwargs)

        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ Token expired")
            return jsonify({'error': 'Token expired'}), 401

        except jwt.InvalidTokenError as e:
            logger.warning(f"⚠️ Invalid token: {e}")
            return jsonify({'error': 'Invalid token'}), 401

        except Exception as e:
            logger.error(f"❌ Authentication error: {e}", exc_info=True)
            return jsonify({'error': 'Authentication failed'}), 401

    return decorated
```

**REMOVE ENTIRE FUNCTION** and replace with:

```python
def get_client_id_from_jwt():
    """
    Extract client_id from JWT token.

    Returns:
        str: User ID from JWT 'sub' claim
    """
    try:
        # Flask-JWT-Extended automatically validates and decodes the token
        client_id = get_jwt_identity()

        if not client_id:
            logger.warning("⚠️ Invalid token payload - missing identity")
            return None

        logger.debug(f"✅ Authenticated client: {client_id[:8]}...")
        return client_id

    except Exception as e:
        logger.error(f"❌ Error extracting client ID: {e}", exc_info=True)
        return None
```

---

**Update Route Decorators:**

**Current** (lines 92-94):
```python
@broadcast_api.route('/api/broadcast/trigger', methods=['POST'])
@authenticate_request
def trigger_broadcast():
```

**New:**
```diff
@broadcast_api.route('/api/broadcast/trigger', methods=['POST'])
-@authenticate_request
+@jwt_required()
def trigger_broadcast():
```

**Update Route Body** (line 125):
```diff
broadcast_id = data['broadcast_id']
-client_id = request.client_id
+client_id = get_client_id_from_jwt()
+
+if not client_id:
+    return jsonify({'error': 'Invalid token payload'}), 401
```

---

**Update Second Route** (lines 165-167):
```python
@broadcast_api.route('/api/broadcast/status/<broadcast_id>', methods=['GET'])
@authenticate_request
def get_broadcast_status(broadcast_id):
```

**New:**
```diff
@broadcast_api.route('/api/broadcast/status/<broadcast_id>', methods=['GET'])
-@authenticate_request
+@jwt_required()
def get_broadcast_status(broadcast_id):
```

**Update Route Body** (line 186):
```diff
-client_id = request.client_id
+client_id = get_client_id_from_jwt()
+
+if not client_id:
+    return jsonify({'error': 'Invalid token payload'}), 401
```

**Estimated Time:** 10 minutes

---

#### Task 1.4: Add JWT Error Handlers to main.py ⬜
**File:** `GCBroadcastScheduler-10-26/main.py`

**Action:** Add custom error handlers for JWT errors

**Add Before** `if __name__ == "__main__":` (before line 213):

```python
# JWT error handlers
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """Handle expired JWT tokens"""
    logger.warning("⚠️ JWT token expired")
    return jsonify({
        'error': 'Token expired',
        'message': 'Session expired. Please log in again.'
    }), 401


@jwt.invalid_token_loader
def invalid_token_callback(error):
    """Handle invalid JWT tokens"""
    logger.warning(f"⚠️ Invalid JWT token: {error}")
    return jsonify({
        'error': 'Invalid token',
        'message': 'Session expired. Please log in again.'
    }), 401


@jwt.unauthorized_loader
def unauthorized_callback(error):
    """Handle missing JWT tokens"""
    logger.warning("⚠️ Missing JWT token")
    return jsonify({
        'error': 'Missing Authorization header',
        'message': 'Authentication required'
    }), 401
```

**Estimated Time:** 3 minutes

---

### Phase 2: Testing Locally (Optional) ⬜

#### Task 2.1: Test JWT Token Decoding Locally ⬜

**Create test script:** `GCBroadcastScheduler-10-26/test_jwt.py`

```python
#!/usr/bin/env python3
"""
Test JWT token decoding with flask-jwt-extended
"""
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token, decode_token
import os

# Create test app
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'test-secret')

jwt = JWTManager(app)

# Test token creation and decoding
with app.app_context():
    # Create token (simulating GCRegisterAPI)
    test_user_id = "12345678-1234-1234-1234-123456789012"
    token = create_access_token(
        identity=test_user_id,
        additional_claims={'username': 'testuser'}
    )

    print(f"✅ Token created: {token[:50]}...")

    # Decode token (simulating GCBroadcastScheduler)
    try:
        payload = decode_token(token)
        print(f"✅ Token decoded successfully")
        print(f"   Identity: {payload['sub']}")
        print(f"   Username: {payload.get('username')}")
        print(f"   Type: {payload.get('type')}")
        print(f"   Fresh: {payload.get('fresh')}")
    except Exception as e:
        print(f"❌ Token decode failed: {e}")
```

**Run:**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCBroadcastScheduler-10-26
python3 test_jwt.py
```

**Expected Output:**
```
✅ Token created: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
✅ Token decoded successfully
   Identity: 12345678-1234-1234-1234-123456789012
   Username: testuser
   Type: access
   Fresh: False
```

**Estimated Time:** 5 minutes

---

### Phase 3: Build & Deploy ⬜

#### Task 3.1: Build New Docker Image ⬜

**Command:**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCBroadcastScheduler-10-26

gcloud builds submit \
  --tag gcr.io/telepay-459221/gcbroadcastscheduler-10-26:latest \
  --timeout=600s
```

**Expected Outcome:**
- Docker image built with flask-jwt-extended installed
- Image pushed to Google Container Registry

**Estimated Time:** 3-5 minutes

---

#### Task 3.2: Deploy to Cloud Run ⬜

**Command:**
```bash
gcloud run deploy gcbroadcastscheduler-10-26 \
  --image gcr.io/telepay-459221/gcbroadcastscheduler-10-26:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated
```

**Expected Outcome:**
- Service updated with new revision
- JWT tokens now properly verified using flask-jwt-extended

**Estimated Time:** 2-3 minutes

---

### Phase 4: Verification ⬜

#### Task 4.1: Check Logs for JWT Initialization ⬜

**Command:**
```bash
gcloud logging read \
  "resource.type=cloud_run_revision
   AND resource.labels.service_name=gcbroadcastscheduler-10-26
   AND textPayload=~'JWT authentication initialized'
   AND timestamp>='" + $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ) + "'" \
  --limit=5 \
  --format=json
```

**Expected Log:**
```
✅ JWT authentication initialized
🔑 JWT secret key loaded (length: 65)
```

**Success Criteria:**
- ✅ JWT initialization log present
- ✅ No errors during startup

**Estimated Time:** 2 minutes

---

#### Task 4.2: Test from Website (Real User Flow) ⬜

**Steps:**
1. Navigate to https://www.paygateprime.com/dashboard
2. **Clear browser cache and localStorage** (to ensure fresh login)
3. Login with credentials: `user1user1` / `user1TEST$`
4. Click "Resend Messages" on "11-11 SHIBA OPEN INSTANT" channel
5. Confirm dialog

**Expected Outcome:**
- ✅ No "Session expired. Please log in again." error
- ✅ Either:
  - Success: "Broadcast queued for sending"
  - Rate Limit: "Please wait X minutes before resending messages again." (with countdown)

**Success Criteria:**
- ✅ NO "Signature verification failed" in logs
- ✅ NO automatic logout
- ✅ Request reaches backend successfully
- ✅ Proper authentication (200 or 429 status, NOT 401)

**Estimated Time:** 3 minutes

---

#### Task 4.3: Check Logs for Successful Authentication ⬜

**Command:**
```bash
gcloud logging read \
  "resource.type=cloud_run_revision
   AND resource.labels.service_name=gcbroadcastscheduler-10-26
   AND (textPayload=~'Authenticated client' OR textPayload=~'Manual trigger request')
   AND timestamp>='" + $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ) + "'" \
  --limit=10 \
  --format=json
```

**Expected Logs:**
```
✅ Authenticated client: 6632bec9...
📨 Manual trigger request: broadcast=a1b2c3d4..., client=6632bec9...
```

**Success Criteria:**
- ✅ "Authenticated client" log present (NOT "Invalid token")
- ✅ "Manual trigger request" log present
- ✅ NO "Signature verification failed" errors

**Estimated Time:** 2 minutes

---

#### Task 4.4: Test Token Expiration Handling ⬜

**Wait for token to expire** (15 minutes after login), then:

1. Navigate to https://www.paygateprime.com/dashboard
2. Try to click "Resend Messages"

**Expected Outcome:**
- ✅ Error message: "Session expired. Please log in again."
- ✅ User redirected to login page after 2 seconds
- ✅ This is CORRECT behavior (token expired, user must re-authenticate)

**Logs Should Show:**
```
⚠️ JWT token expired
```

**Success Criteria:**
- ✅ Token expiration handled gracefully
- ✅ User sees clear "Session expired" message (NOT "Network Error")
- ✅ Logs show "JWT token expired" (NOT "Signature verification failed")

**Estimated Time:** 17 minutes (15 min wait + 2 min test)

---

### Phase 5: Documentation ⬜

#### Task 5.1: Update PROGRESS.md ⬜

**Action:** Add Session 121 entry at the beginning

**Entry:**
```markdown
## 2025-11-12 Session 121: JWT Signature Verification Fix ✅

**JWT FIX:** Resolved JWT signature verification failures in GCBroadcastScheduler

**Problem:**
- ❌ Users clicking "Resend Messages" saw "Session expired. Please log in again."
- ❌ Logs showed "Signature verification failed"
- ❌ Manual broadcast trigger feature non-functional
- ❌ Users automatically logged out on every trigger attempt

**Root Cause:**
- GCRegisterAPI creates JWT tokens using `flask-jwt-extended`
- GCBroadcastScheduler tried to verify tokens using raw `PyJWT` library
- **LIBRARY MISMATCH**: flask-jwt-extended tokens incompatible with PyJWT decoder
- Both services pointed to same JWT_SECRET_KEY, but token structure differed

**Solution:**
- ✅ Added `flask-jwt-extended>=4.5.0,<5.0.0` to requirements.txt
- ✅ Initialized JWTManager in main.py with same configuration as GCRegisterAPI
- ✅ Replaced custom PyJWT authentication decorator with `@jwt_required()`
- ✅ Added JWT error handlers for expired/invalid tokens
- ✅ Rebuilt and redeployed service

**Technical Details:**
- Flask-JWT-Extended Config:
  - JWT_SECRET_KEY: Same secret as GCRegisterAPI
  - JWT_ALGORITHM: HS256
  - JWT_DECODE_LEEWAY: 10 seconds (clock skew tolerance)
- Token Claims: Uses 'sub' for user identity (consistent with GCRegisterAPI)

**Verification:**
- ✅ JWT initialization logs present
- ✅ "Authenticated client" logs present (NO "Signature verification failed")
- ✅ Manual broadcast triggers work from website
- ✅ Token expiration handled gracefully (401 with clear message)
- ✅ Users no longer automatically logged out

**Files Modified:**
- GCBroadcastScheduler-10-26/requirements.txt
- GCBroadcastScheduler-10-26/main.py
- GCBroadcastScheduler-10-26/broadcast_web_api.py
```

**Estimated Time:** 3 minutes

---

#### Task 5.2: Update DECISIONS.md ⬜

**Action:** Add architectural decision entry

**Entry:**
```markdown
### 2025-11-12 Session 121: JWT Library Standardization Across Services 🔐

**Decision:** Standardize on flask-jwt-extended for JWT authentication across all Flask services

**Context:**
- GCRegisterAPI uses flask-jwt-extended to issue JWT tokens
- GCBroadcastScheduler initially used raw PyJWT to verify tokens
- Library mismatch caused signature verification failures
- Users unable to trigger manual broadcasts

**Problem Analysis:**

**Token Issuer (GCRegisterAPI):**
```python
from flask_jwt_extended import JWTManager, create_access_token
access_token = create_access_token(
    identity=user_id,
    additional_claims={'username': username}
)
```

**Token Verifier (GCBroadcastScheduler - BEFORE FIX):**
```python
import jwt  # Raw PyJWT
payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])
```

**Why This Failed:**
- Flask-JWT-Extended adds special claims: 'fresh', 'type', 'jti', 'csrf'
- Token structure differs from standard PyJWT tokens
- Signature verification fails despite using same secret

**Options Considered:**

**Option A: Use Flask-JWT-Extended in GCBroadcastScheduler** ✅ SELECTED
- Consistent JWT implementation across services
- Automatic handling of flask-jwt-extended token structure
- Built-in decorators (@jwt_required)
- Industry-standard Flask authentication

**Option B: Rewrite GCRegisterAPI to use Raw PyJWT** ❌ REJECTED
- BREAKING CHANGE for production service
- Would invalidate all existing user sessions
- High risk to stable authentication system
- NOT RECOMMENDED

**Option C: Manual Token Decoding** ❌ REJECTED
- Error-prone
- Must manually replicate flask-jwt-extended structure
- Maintenance burden
- NOT RECOMMENDED

**Implementation:**
```python
# main.py - Initialize JWT
from flask_jwt_extended import JWTManager
app.config['JWT_SECRET_KEY'] = jwt_secret_key
app.config['JWT_ALGORITHM'] = 'HS256'
app.config['JWT_DECODE_LEEWAY'] = 10
jwt = JWTManager(app)

# broadcast_web_api.py - Use decorators
from flask_jwt_extended import jwt_required, get_jwt_identity

@broadcast_api.route('/api/broadcast/trigger', methods=['POST'])
@jwt_required()
def trigger_broadcast():
    client_id = get_jwt_identity()
    # ... route logic
```

**JWT Configuration (Standardized):**
- Secret: Same JWT_SECRET_KEY across all services
- Algorithm: HS256
- Access Token Expiry: 15 minutes
- Refresh Token Expiry: 30 days
- Clock Skew Tolerance: 10 seconds

**Security Considerations:**
- ✅ All services use same secret (JWT_SECRET_KEY from Secret Manager)
- ✅ Tokens expire after 15 minutes (security best practice)
- ✅ Clock skew tolerance prevents timing issues between services
- ✅ Refresh tokens allow seamless re-authentication

**Impact:**
- ✅ Manual broadcast triggers now functional
- ✅ JWT authentication consistent across all services
- ✅ Token verification errors eliminated
- ✅ User experience improved (no unexpected logouts)

**Future Considerations:**
- Consider implementing JWT blacklisting for logout functionality
- Monitor token expiration UX (15 minutes may be too short)
- Add refresh token endpoint to GCBroadcastScheduler if needed
```

**Estimated Time:** 5 minutes

---

## Risk Assessment

### Risks Identified

#### Risk 1: JWT Configuration Mismatch
**Likelihood:** LOW
**Impact:** HIGH (authentication broken)
**Mitigation:**
- Use exact same JWT_SECRET_KEY as GCRegisterAPI
- Use same algorithm (HS256)
- Test with real tokens before deploying

#### Risk 2: Token Claims Mismatch
**Likelihood:** LOW
**Impact:** MEDIUM (client_id extraction fails)
**Mitigation:**
- Flask-jwt-extended automatically handles 'sub' claim for identity
- Test token payload extraction before deploying

#### Risk 3: Deployment Failure
**Likelihood:** LOW
**Impact:** MEDIUM (service unavailable during rollback)
**Mitigation:**
- Cloud Run automatically rolls back on failure
- Previous revision remains available

#### Risk 4: Existing Sessions Break
**Likelihood:** VERY LOW
**Impact:** LOW (users just re-login)
**Mitigation:**
- Token structure remains same (issued by GCRegisterAPI)
- Only verification method changes
- Existing tokens should work immediately

---

## Rollback Plan

**If deployment fails or JWT still doesn't work:**

### Step 1: Check Deployment Status
```bash
gcloud run services describe gcbroadcastscheduler-10-26 \
  --region=us-central1 \
  --format="value(status.latestReadyRevisionName)"
```

### Step 2: Check JWT Initialization Logs
```bash
gcloud logging read \
  "resource.type=cloud_run_revision
   AND resource.labels.service_name=gcbroadcastscheduler-10-26
   AND textPayload=~'JWT'
   AND timestamp>='" + $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ) + "'" \
  --limit=20
```

### Step 3: Rollback to Previous Revision (if needed)
```bash
# List revisions
gcloud run revisions list \
  --service=gcbroadcastscheduler-10-26 \
  --region=us-central1

# Rollback to previous revision (replace with actual revision name)
gcloud run services update-traffic gcbroadcastscheduler-10-26 \
  --region=us-central1 \
  --to-revisions=<previous-revision>=100
```

### Step 4: Debug JWT Configuration
```bash
# Check JWT secret length
gcloud secrets versions access latest --secret=JWT_SECRET_KEY | wc -c

# Should output: 65 (64 characters + newline)
```

---

## Total Estimated Time

- **Phase 1 (Code Changes):** 17 minutes
- **Phase 2 (Local Testing):** 5 minutes (optional)
- **Phase 3 (Build & Deploy):** 5-8 minutes
- **Phase 4 (Verification):** 24 minutes (includes 15 min wait for token expiry test)
- **Phase 5 (Documentation):** 8 minutes

**TOTAL:** ~60 minutes (including token expiry test)
**TOTAL (without expiry test):** ~35-45 minutes

---

## Success Criteria

### Technical Success
- ✅ flask-jwt-extended installed in requirements.txt
- ✅ JWTManager initialized in main.py
- ✅ Custom PyJWT decoder replaced with @jwt_required()
- ✅ JWT error handlers configured
- ✅ Service deployed with new revision
- ✅ Logs show "JWT authentication initialized"
- ✅ Logs show "Authenticated client" (NO "Signature verification failed")

### User Success
- ✅ "Resend Messages" button works from website
- ✅ NO "Session expired" error when token is valid
- ✅ NO automatic logout on manual broadcast trigger
- ✅ Success or rate limit message appears
- ✅ Token expiration handled gracefully (clear error message)

---

## Approval Required

**Please review this checklist and confirm:**
1. ✅ The root cause analysis is correct (library mismatch)
2. ✅ The fix strategy is correct (use flask-jwt-extended)
3. ✅ The JWT configuration matches GCRegisterAPI
4. ✅ The deployment plan is acceptable
5. ✅ You approve proceeding with the implementation

**Once approved, I will:**
1. Make all code changes (requirements.txt, main.py, broadcast_web_api.py)
2. Build and deploy the service
3. Verify JWT authentication works
4. Test from website
5. Update documentation (PROGRESS.md, DECISIONS.md)
6. Provide final verification report

---

**Status:** ⏳ AWAITING APPROVAL
