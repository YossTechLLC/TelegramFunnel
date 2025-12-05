# PGP_v1 Critical Security Fixes Implementation Checklist

**Version:** 1.0
**Created:** 2025-11-16
**Status:** 🔴 NOT STARTED
**Estimated Effort:** 3-4 days
**Priority:** CRITICAL - Must complete before ANY deployment to pgp-live

---

## Executive Summary

This checklist addresses **three critical security vulnerabilities** identified in the PGP_v1 codebase security audit:

1. 🔴 **CRITICAL:** Replay Attack Vulnerability (HMAC lacks timestamp validation)
2. 🔴 **HIGH:** IP Whitelist Incomplete (Cloud Run egress IPs not documented)
3. 🟡 **MEDIUM:** Debug Logging in Production (Information disclosure risk)

**⚠️ WARNING:** Do NOT deploy to production until ALL items marked as CRITICAL are complete and tested.

---

## Table of Contents

1. [Issue 1: HMAC Timestamp Validation (Replay Attack Protection)](#issue-1-hmac-timestamp-validation)
2. [Issue 2: IP Whitelist Configuration](#issue-2-ip-whitelist-configuration)
3. [Issue 3: Debug Logging Removal](#issue-3-debug-logging-removal)
4. [Integration Testing](#integration-testing)
5. [Deployment & Rollback](#deployment--rollback)

---

## Issue 1: HMAC Timestamp Validation (Replay Attack Protection)

### Overview
**Severity:** 🔴 CRITICAL
**Risk:** Attackers can capture valid webhook requests and replay them indefinitely
**Impact:** Financial loss, duplicate payments, unauthorized access
**Effort:** 1-2 days development + testing

### Affected Components
- **Receiver Side:** `PGP_SERVER_v1/security/hmac_auth.py` (signature verification)
- **Sender Side:** `PGP_COMMON/cloudtasks/base_client.py` (signature generation)
- **All Services Using Signed Tasks:** 12 services use `create_signed_task()`

### Architecture Decision

**Pattern:** HTTP Header-Based Timestamp + HMAC Signature

**Best Practice (OWASP):**
- Include timestamp in signature calculation
- Reject requests with timestamps outside acceptable window (5 minutes recommended)
- Use Unix timestamp (seconds since epoch) for simplicity
- Send timestamp in dedicated header (`X-Request-Timestamp`)

**Flow:**
```
Client (Cloud Tasks)                    Server (PGP_SERVER_v1)
     |                                           |
     |  1. Generate Unix timestamp               |
     |  2. Create payload: JSON body             |
     |  3. Calculate HMAC(payload + timestamp)   |
     |  4. Send request with headers:            |
     |     - X-Request-Timestamp: 1700000000     |
     |     - X-Signature: abc123...              |
     |     - Content-Type: application/json      |
     |     - Body: {...}                         |
     |                                           |
     | ----------------------------------------> |
     |                                           |
     |                          5. Receive request
     |                          6. Extract timestamp from header
     |                          7. Verify timestamp within window (now ± 5min)
     |                          8. Calculate HMAC(payload + timestamp)
     |                          9. Compare signatures (timing-safe)
     |                          10. Accept/Reject request
```

---

### Phase 1.1: Update HMAC Signature Generation (Sender Side)

**Location:** `PGP_COMMON/cloudtasks/base_client.py`

- [ ] **Step 1.1.1:** Add timestamp generation to `create_signed_task()` method

**Current Code (Lines 115-167):**
```python
def create_signed_task(
    self,
    queue_name: str,
    target_url: str,
    payload: dict,
    schedule_delay_seconds: int = 0
) -> Optional[str]:
    import hmac
    import hashlib

    try:
        # Create HMAC signature
        payload_json = json.dumps(payload)
        signature = hmac.new(
            self.signing_key.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()

        # Add signature to custom headers
        custom_headers = {
            "X-Webhook-Signature": signature
        }
```

**New Code:**
```python
def create_signed_task(
    self,
    queue_name: str,
    target_url: str,
    payload: dict,
    schedule_delay_seconds: int = 0
) -> Optional[str]:
    import hmac
    import hashlib
    import time

    try:
        # Generate Unix timestamp (seconds since epoch)
        timestamp = str(int(time.time()))

        # Create HMAC signature including timestamp
        payload_json = json.dumps(payload)
        message = f"{timestamp}:{payload_json}"  # Timestamp prefix prevents reordering attacks

        signature = hmac.new(
            self.signing_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        # Add signature AND timestamp to custom headers
        custom_headers = {
            "X-Signature": signature,  # Renamed from X-Webhook-Signature for consistency
            "X-Request-Timestamp": timestamp
        }

        print(f"🔐 [CLOUD_TASKS] Added webhook signature with timestamp: {timestamp}")
```

**Changes Required:**
1. Add `import time` at top of method
2. Generate Unix timestamp: `timestamp = str(int(time.time()))`
3. Include timestamp in signature calculation: `message = f"{timestamp}:{payload_json}"`
4. Add `X-Request-Timestamp` header
5. Rename `X-Webhook-Signature` to `X-Signature` (consistency)
6. Update debug logging

**⚠️ Breaking Change:** This changes the signature format. All services must be updated simultaneously.

---

- [ ] **Step 1.1.2:** Update logging to include timestamp information

Add debug logging:
```python
print(f"🔐 [CLOUD_TASKS] Generated signature at timestamp: {timestamp}")
print(f"🔐 [CLOUD_TASKS] Signature format: HMAC-SHA256(timestamp:payload)")
```

---

- [ ] **Step 1.1.3:** Add backward compatibility check (OPTIONAL - for gradual rollout)

If gradual rollout is needed, add feature flag:
```python
def create_signed_task(
    self,
    queue_name: str,
    target_url: str,
    payload: dict,
    schedule_delay_seconds: int = 0,
    use_timestamp: bool = True  # Feature flag
) -> Optional[str]:
```

**Decision:** ✅ **Recommended to skip** - All services under our control, atomic deployment preferred

---

### Phase 1.2: Update HMAC Signature Verification (Receiver Side)

**Location:** `PGP_SERVER_v1/security/hmac_auth.py`

- [ ] **Step 1.2.1:** Add timestamp window constant at top of file

```python
#!/usr/bin/env python
"""
HMAC-based request authentication for webhook endpoints.
Verifies requests from Cloud Run services using shared secret.
Includes timestamp validation for replay attack protection.
"""
import hmac
import hashlib
import logging
import time
from functools import wraps
from flask import request, abort

logger = logging.getLogger(__name__)

# Security Configuration
TIMESTAMP_TOLERANCE_SECONDS = 300  # 5 minutes (300 seconds)
```

**Rationale:**
- 5 minutes = 300 seconds is industry standard
- Accounts for clock drift between services
- Balances security (shorter window) vs reliability (longer window)

---

- [ ] **Step 1.2.2:** Update `generate_signature()` method to accept timestamp

**Current Code (Lines 36-52):**
```python
def generate_signature(self, payload: bytes) -> str:
    """
    Generate HMAC-SHA256 signature for payload.

    Args:
        payload: Request body as bytes

    Returns:
        Hex-encoded HMAC signature
    """
    signature = hmac.new(
        self.secret_key,
        payload,
        hashlib.sha256
    ).hexdigest()

    return signature
```

**New Code:**
```python
def generate_signature(self, payload: bytes, timestamp: str) -> str:
    """
    Generate HMAC-SHA256 signature for payload with timestamp.

    Args:
        payload: Request body as bytes
        timestamp: Unix timestamp as string (e.g., "1700000000")

    Returns:
        Hex-encoded HMAC signature
    """
    # Create message: timestamp:payload
    message = f"{timestamp}:".encode() + payload

    signature = hmac.new(
        self.secret_key,
        message,
        hashlib.sha256
    ).hexdigest()

    return signature
```

---

- [ ] **Step 1.2.3:** Add timestamp validation method

**New Method (add after `generate_signature()`):**
```python
def validate_timestamp(self, timestamp: str) -> bool:
    """
    Validate request timestamp is within acceptable window.

    Prevents replay attacks by rejecting requests with timestamps
    outside the acceptable time window (±5 minutes).

    Args:
        timestamp: Unix timestamp as string (e.g., "1700000000")

    Returns:
        True if timestamp is valid, False otherwise
    """
    try:
        # Parse timestamp
        request_time = int(timestamp)
        current_time = int(time.time())

        # Calculate time difference (absolute value)
        time_diff = abs(current_time - request_time)

        # Check if within tolerance window
        if time_diff > TIMESTAMP_TOLERANCE_SECONDS:
            logger.warning(
                f"⏰ [HMAC] Timestamp outside acceptable window: "
                f"diff={time_diff}s (max={TIMESTAMP_TOLERANCE_SECONDS}s)"
            )
            return False

        logger.debug(f"✅ [HMAC] Timestamp valid: diff={time_diff}s")
        return True

    except (ValueError, TypeError) as e:
        logger.error(f"❌ [HMAC] Invalid timestamp format: {timestamp} - {e}")
        return False
```

**Security Considerations:**
- Uses absolute time difference to prevent future-dated requests
- Logs timestamp violations for security monitoring
- Handles invalid timestamp formats gracefully

---

- [ ] **Step 1.2.4:** Update `verify_signature()` method to accept and validate timestamp

**Current Code (Lines 54-69):**
```python
def verify_signature(self, payload: bytes, provided_signature: str) -> bool:
    """
    Verify HMAC signature using timing-safe comparison.

    Args:
        payload: Request body as bytes
        provided_signature: Signature from X-Signature header

    Returns:
        True if signature is valid, False otherwise
    """
    if not provided_signature:
        return False

    expected_signature = self.generate_signature(payload)
    return hmac.compare_digest(expected_signature, provided_signature)
```

**New Code:**
```python
def verify_signature(self, payload: bytes, provided_signature: str, timestamp: str) -> bool:
    """
    Verify HMAC signature and timestamp using timing-safe comparison.

    Security:
    - Validates timestamp within acceptable window (±5 minutes)
    - Uses timing-safe signature comparison
    - Prevents replay attacks

    Args:
        payload: Request body as bytes
        provided_signature: Signature from X-Signature header
        timestamp: Timestamp from X-Request-Timestamp header

    Returns:
        True if signature and timestamp are valid, False otherwise
    """
    if not provided_signature or not timestamp:
        logger.warning("⚠️ [HMAC] Missing signature or timestamp")
        return False

    # Step 1: Validate timestamp (CRITICAL - check before signature)
    if not self.validate_timestamp(timestamp):
        logger.error("❌ [HMAC] Timestamp validation failed")
        return False

    # Step 2: Verify signature with timestamp
    expected_signature = self.generate_signature(payload, timestamp)
    is_valid = hmac.compare_digest(expected_signature, provided_signature)

    if not is_valid:
        logger.error("❌ [HMAC] Signature mismatch")

    return is_valid
```

**Critical Security Pattern:**
1. Validate timestamp FIRST (cheap operation, fails fast)
2. Only calculate signature if timestamp is valid (expensive operation)
3. Use timing-safe comparison for signature

---

- [ ] **Step 1.2.5:** Update `require_signature` decorator to extract timestamp header

**Current Code (Lines 71-107):**
```python
def require_signature(self, f):
    """
    Decorator to require HMAC signature on Flask route.

    Usage:
        @app.route('/webhook', methods=['POST'])
        @hmac_auth.require_signature
        def webhook():
            return jsonify({'status': 'ok'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get signature from header
        signature = request.headers.get('X-Signature')

        if not signature:
            logger.warning("⚠️ [HMAC] Missing X-Signature header from {}".format(
                request.remote_addr
            ))
            abort(401, "Missing signature header")

        # Get request payload
        payload = request.get_data()

        # Verify signature
        if not self.verify_signature(payload, signature):
            logger.error("❌ [HMAC] Invalid signature from {}".format(
                request.remote_addr
            ))
            abort(403, "Invalid signature")

        logger.info("✅ [HMAC] Valid signature from {}".format(
            request.remote_addr
        ))
        return f(*args, **kwargs)

    return decorated_function
```

**New Code:**
```python
def require_signature(self, f):
    """
    Decorator to require HMAC signature and timestamp on Flask route.

    Security Features:
    - Validates timestamp within acceptable window (±5 minutes)
    - Verifies HMAC-SHA256 signature with timing-safe comparison
    - Prevents replay attacks

    Usage:
        @app.route('/webhook', methods=['POST'])
        @hmac_auth.require_signature
        def webhook():
            return jsonify({'status': 'ok'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get signature from header
        signature = request.headers.get('X-Signature')

        # Get timestamp from header
        timestamp = request.headers.get('X-Request-Timestamp')

        # Validate headers present
        if not signature:
            logger.warning("⚠️ [HMAC] Missing X-Signature header from {}".format(
                request.remote_addr
            ))
            abort(401, "Missing signature header")

        if not timestamp:
            logger.warning("⚠️ [HMAC] Missing X-Request-Timestamp header from {}".format(
                request.remote_addr
            ))
            abort(401, "Missing timestamp header")

        # Get request payload
        payload = request.get_data()

        # Verify signature with timestamp
        if not self.verify_signature(payload, signature, timestamp):
            logger.error("❌ [HMAC] Authentication failed from {} (invalid signature or expired timestamp)".format(
                request.remote_addr
            ))
            abort(403, "Authentication failed")

        logger.info("✅ [HMAC] Valid signature and timestamp from {} (age: {}s)".format(
            request.remote_addr,
            abs(int(time.time()) - int(timestamp))
        ))
        return f(*args, **kwargs)

    return decorated_function
```

**Key Changes:**
1. Extract `X-Request-Timestamp` header
2. Validate both signature and timestamp present
3. Pass timestamp to `verify_signature()`
4. Enhanced error logging (signature vs timestamp failure)
5. Log request age for monitoring

---

### Phase 1.3: Update Service-Specific CloudTasks Clients

**Affected Services:** 12 services use `create_signed_task()`

- [ ] **Step 1.3.1:** Verify all services inherit from `BaseCloudTasksClient`

Services to check:
1. ✅ PGP_ORCHESTRATOR_v1 (uses `create_signed_task` at line 125)
2. ✅ PGP_SPLIT1_v1
3. ✅ PGP_SPLIT2_v1
4. ✅ PGP_SPLIT3_v1
5. ✅ PGP_HOSTPAY1_v1
6. ✅ PGP_HOSTPAY2_v1
7. ✅ PGP_HOSTPAY3_v1
8. ✅ PGP_ACCUMULATOR_v1
9. ✅ PGP_BATCHPROCESSOR_v1
10. ✅ PGP_MICROBATCHPROCESSOR_v1
11. ✅ PGP_NP_IPN_v1
12. ✅ PGP_INVITE_v1

**Verification Command:**
```bash
grep -r "create_signed_task" --include="*.py" PGP_*/cloudtasks_client.py
```

**Expected Result:** All services use inherited method, NO custom implementations

**✅ If all services inherit:** No changes needed to service-specific code
**❌ If any service overrides:** Must update override to match new signature format

---

- [ ] **Step 1.3.2:** Check for any custom signature generation code

**Search Command:**
```bash
grep -r "X-Webhook-Signature\|X-Signature" --include="*.py" PGP_*/ | grep -v THINKING | grep -v ".md"
```

**Action:** Update any custom implementations to use timestamp

---

### Phase 1.4: Testing HMAC Timestamp Validation

- [ ] **Step 1.4.1:** Create unit tests for timestamp validation

**Location:** Create `PGP_SERVER_v1/tests/test_hmac_timestamp.py`

```python
#!/usr/bin/env python
"""
Unit tests for HMAC timestamp validation (replay attack protection).
"""
import pytest
import time
import hmac
import hashlib
from security.hmac_auth import HMACAuth, TIMESTAMP_TOLERANCE_SECONDS


class TestHMACTimestampValidation:
    """Test HMAC signature and timestamp validation."""

    @pytest.fixture
    def hmac_auth(self):
        """Create HMACAuth instance with test secret."""
        return HMACAuth("test-secret-key-12345")

    def test_valid_current_timestamp(self, hmac_auth):
        """Test signature with current timestamp is accepted."""
        timestamp = str(int(time.time()))
        payload = b'{"user_id": 123, "amount": "10.00"}'

        # Generate signature
        signature = hmac_auth.generate_signature(payload, timestamp)

        # Verify signature
        assert hmac_auth.verify_signature(payload, signature, timestamp) is True

    def test_old_timestamp_rejected(self, hmac_auth):
        """Test signature with old timestamp is rejected (replay attack)."""
        # Timestamp from 10 minutes ago (outside 5-minute window)
        old_timestamp = str(int(time.time()) - 600)
        payload = b'{"user_id": 123, "amount": "10.00"}'

        # Generate signature with old timestamp
        signature = hmac_auth.generate_signature(payload, old_timestamp)

        # Should reject due to expired timestamp
        assert hmac_auth.verify_signature(payload, signature, old_timestamp) is False

    def test_future_timestamp_rejected(self, hmac_auth):
        """Test signature with future timestamp is rejected."""
        # Timestamp from 10 minutes in future
        future_timestamp = str(int(time.time()) + 600)
        payload = b'{"user_id": 123, "amount": "10.00"}'

        # Generate signature with future timestamp
        signature = hmac_auth.generate_signature(payload, future_timestamp)

        # Should reject due to future timestamp
        assert hmac_auth.verify_signature(payload, signature, future_timestamp) is False

    def test_timestamp_within_tolerance(self, hmac_auth):
        """Test timestamp within tolerance window is accepted."""
        # Timestamp from 4 minutes ago (within 5-minute window)
        timestamp = str(int(time.time()) - 240)
        payload = b'{"user_id": 123, "amount": "10.00"}'

        signature = hmac_auth.generate_signature(payload, timestamp)

        # Should accept - within tolerance
        assert hmac_auth.verify_signature(payload, signature, timestamp) is True

    def test_invalid_timestamp_format(self, hmac_auth):
        """Test invalid timestamp format is rejected."""
        payload = b'{"user_id": 123}'
        signature = "dummy-signature"

        # Invalid formats
        assert hmac_auth.verify_signature(payload, signature, "not-a-number") is False
        assert hmac_auth.verify_signature(payload, signature, "") is False
        assert hmac_auth.verify_signature(payload, signature, "12.34") is False

    def test_modified_payload_rejected(self, hmac_auth):
        """Test signature verification fails if payload is modified."""
        timestamp = str(int(time.time()))
        original_payload = b'{"user_id": 123, "amount": "10.00"}'
        modified_payload = b'{"user_id": 123, "amount": "99.00"}'

        # Generate signature for original
        signature = hmac_auth.generate_signature(original_payload, timestamp)

        # Verify with modified payload should fail
        assert hmac_auth.verify_signature(modified_payload, signature, timestamp) is False

    def test_modified_timestamp_rejected(self, hmac_auth):
        """Test signature verification fails if timestamp is modified."""
        original_timestamp = str(int(time.time()))
        modified_timestamp = str(int(time.time()) - 10)
        payload = b'{"user_id": 123}'

        # Generate signature with original timestamp
        signature = hmac_auth.generate_signature(payload, original_timestamp)

        # Verify with different timestamp should fail
        assert hmac_auth.verify_signature(payload, signature, modified_timestamp) is False

    def test_missing_timestamp(self, hmac_auth):
        """Test missing timestamp is rejected."""
        payload = b'{"user_id": 123}'
        signature = "dummy-signature"

        assert hmac_auth.verify_signature(payload, signature, None) is False
        assert hmac_auth.verify_signature(payload, signature, "") is False


class TestCloudTasksSignedTask:
    """Test Cloud Tasks signature generation with timestamp."""

    def test_signature_includes_timestamp(self):
        """Test create_signed_task includes timestamp in signature."""
        # This requires BaseCloudTasksClient to be imported
        # Test that X-Request-Timestamp header is set
        # Test that signature is calculated with timestamp:payload format
        pass  # Implement after code changes
```

**Run Tests:**
```bash
cd PGP_SERVER_v1
pytest tests/test_hmac_timestamp.py -v
```

---

- [ ] **Step 1.4.2:** Create integration test for end-to-end validation

**Location:** Create `TOOLS_SCRIPTS_TESTS/tests/test_hmac_integration.py`

```python
#!/usr/bin/env python
"""
Integration test for HMAC signature with timestamp (replay attack protection).
Tests complete flow from Cloud Tasks client to PGP_SERVER_v1 webhook endpoint.
"""
import requests
import time
import hmac
import hashlib
import json


def test_webhook_with_valid_timestamp():
    """Test webhook accepts request with valid timestamp."""
    # Configuration
    webhook_url = "http://localhost:8080/webhook/notification"  # Update with actual endpoint
    secret_key = "test-secret-key"  # Must match server configuration

    # Create payload
    payload = {
        "user_id": 123,
        "message": "Test notification",
        "timestamp": int(time.time())
    }

    # Generate timestamp and signature (simulating Cloud Tasks)
    request_timestamp = str(int(time.time()))
    payload_json = json.dumps(payload)
    message = f"{request_timestamp}:{payload_json}"

    signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    # Send request
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "X-Request-Timestamp": request_timestamp
    }

    response = requests.post(webhook_url, json=payload, headers=headers)

    # Should succeed
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    print("✅ Test passed: Valid timestamp accepted")


def test_webhook_rejects_old_timestamp():
    """Test webhook rejects request with old timestamp (replay attack simulation)."""
    webhook_url = "http://localhost:8080/webhook/notification"
    secret_key = "test-secret-key"

    payload = {"user_id": 123, "message": "Replayed request"}

    # Use old timestamp (10 minutes ago)
    old_timestamp = str(int(time.time()) - 600)
    payload_json = json.dumps(payload)
    message = f"{old_timestamp}:{payload_json}"

    signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "X-Request-Timestamp": old_timestamp
    }

    response = requests.post(webhook_url, json=payload, headers=headers)

    # Should reject with 403
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    print("✅ Test passed: Old timestamp rejected (replay attack prevented)")


def test_webhook_rejects_missing_timestamp():
    """Test webhook rejects request without timestamp header."""
    webhook_url = "http://localhost:8080/webhook/notification"
    secret_key = "test-secret-key"

    payload = {"user_id": 123}
    payload_json = json.dumps(payload)

    # Generate signature WITHOUT timestamp (old behavior)
    signature = hmac.new(
        secret_key.encode(),
        payload_json.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature
        # Missing X-Request-Timestamp
    }

    response = requests.post(webhook_url, json=payload, headers=headers)

    # Should reject with 401 (missing header)
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    print("✅ Test passed: Missing timestamp header rejected")


if __name__ == "__main__":
    print("🧪 Running HMAC integration tests...")
    print("\n" + "="*60)

    try:
        test_webhook_with_valid_timestamp()
        test_webhook_rejects_old_timestamp()
        test_webhook_rejects_missing_timestamp()

        print("\n" + "="*60)
        print("✅ All integration tests passed!")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except requests.exceptions.ConnectionError:
        print("\n⚠️  Error: Cannot connect to webhook endpoint")
        print("   Make sure PGP_SERVER_v1 is running at http://localhost:8080")
```

**Run Integration Test:**
```bash
# Start PGP_SERVER_v1 locally first
cd TOOLS_SCRIPTS_TESTS/tests
python test_hmac_integration.py
```

---

- [ ] **Step 1.4.3:** Test with actual Cloud Tasks (staging environment)

**Prerequisites:**
- Staging environment deployed
- Cloud Tasks queues configured
- Test webhook endpoint available

**Test Procedure:**
1. Deploy updated code to staging
2. Trigger real Cloud Task from PGP_NP_IPN_v1
3. Verify webhook receives request with timestamp
4. Check logs for signature validation success
5. Attempt replay attack (resend captured request after 10 minutes)
6. Verify replay is rejected with 403

**Expected Logs:**
```
✅ [HMAC] Valid signature and timestamp from 10.128.0.x (age: 2s)
```

**Replay Attack Log (Expected):**
```
⏰ [HMAC] Timestamp outside acceptable window: diff=605s (max=300s)
❌ [HMAC] Authentication failed from 10.128.0.x (invalid signature or expired timestamp)
```

---

### Phase 1.5: Documentation Updates

- [ ] **Step 1.5.1:** Update security documentation

**File:** `PGP_SERVER_v1/SECURITY.md` (create if not exists)

```markdown
# Security Architecture - PGP_v1

## HMAC Authentication with Timestamp Validation

### Overview
All inter-service webhook requests use HMAC-SHA256 signatures with timestamp validation to prevent replay attacks.

### Request Format

**Headers:**
- `Content-Type: application/json`
- `X-Signature: <hex-encoded-hmac-sha256>`
- `X-Request-Timestamp: <unix-timestamp>`

**Signature Calculation:**
```
message = "{timestamp}:{json_payload}"
signature = HMAC-SHA256(secret_key, message)
```

**Example:**
```bash
timestamp="1700000000"
payload='{"user_id":123}'
message="${timestamp}:${payload}"
signature=$(echo -n "$message" | openssl dgst -sha256 -hmac "secret-key" | cut -d' ' -f2)

curl -X POST https://service.run.app/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $signature" \
  -H "X-Request-Timestamp: $timestamp" \
  -d "$payload"
```

### Timestamp Validation

- **Tolerance Window:** ±5 minutes (300 seconds)
- **Clock Synchronization:** All services use NTP-synchronized Cloud Run instances
- **Replay Protection:** Requests with timestamps outside window are rejected with HTTP 403

### Security Guarantees

✅ **Replay Attack Protection:** Old requests cannot be replayed
✅ **Integrity:** Payload tampering detected via signature
✅ **Authenticity:** Only services with shared secret can sign requests
✅ **Timing Safety:** Constant-time signature comparison prevents timing attacks
```

---

- [ ] **Step 1.5.2:** Update API documentation

**File:** `PGP_SERVER_v1/API.md`

Add webhook authentication section with timestamp requirements.

---

- [ ] **Step 1.5.3:** Update DECISIONS.md

Document the architectural decision to add timestamp validation (already done in this checklist).

---

### Phase 1.6: Deployment Coordination

**⚠️ CRITICAL:** All services must be updated simultaneously due to breaking change

- [ ] **Step 1.6.1:** Create deployment plan

**Atomic Deployment Strategy:**
1. Build all Docker images with updated code
2. Push all images to Container Registry
3. Deploy ALL services within 5-minute window
4. Verify health checks pass
5. Monitor logs for signature errors

**Services to Deploy (12):**
- PGP_ORCHESTRATOR_v1
- PGP_INVITE_v1
- PGP_SPLIT1_v1, PGP_SPLIT2_v1, PGP_SPLIT3_v1
- PGP_HOSTPAY1_v1, PGP_HOSTPAY2_v1, PGP_HOSTPAY3_v1
- PGP_ACCUMULATOR_v1
- PGP_BATCHPROCESSOR_v1
- PGP_MICROBATCHPROCESSOR_v1
- PGP_NP_IPN_v1
- **PGP_SERVER_v1** (HMAC verification)

**Deployment Order:**
1. Deploy PGP_COMMON update (all services will rebuild)
2. Deploy PGP_SERVER_v1 (receiver) FIRST
3. Deploy all sender services (ORCHESTRATOR, SPLIT, HOSTPAY, etc.)
4. Reason: New receiver accepts both old and new formats temporarily (optional)

---

- [ ] **Step 1.6.2:** Create rollback procedure

**Rollback Steps:**
```bash
# Revert to previous image tags
gcloud run services update pgp-server-v1 --image=gcr.io/pgp-live/pgp-server-v1:previous
gcloud run services update pgp-orchestrator-v1 --image=gcr.io/pgp-live/pgp-orchestrator-v1:previous
# ... repeat for all services
```

**Rollback Decision Criteria:**
- Signature validation errors > 5% of requests
- Any service health check failures
- Payment processing failures

---

## Issue 2: IP Whitelist Configuration

### Overview
**Severity:** 🔴 HIGH
**Risk:** Inter-service communication may fail OR whitelist may be too permissive
**Impact:** Service outages, potential unauthorized access
**Effort:** 1 day (research + configuration)

### Affected Components
- **Configuration:** `PGP_SERVER_v1/security/ip_whitelist.py`
- **Initialization:** `PGP_SERVER_v1/server_manager.py` OR `app_initializer.py`

---

### Phase 2.1: Research Cloud Run Egress IPs

- [ ] **Step 2.1.1:** Document Cloud Run egress IP ranges for us-central1

**Google Cloud Documentation:**
Cloud Run services in a specific region share egress IP ranges. These are NOT static IPs but come from documented CIDR blocks.

**Research Steps:**
1. Check Google Cloud documentation: https://cloud.google.com/run/docs/securing/static-outbound-ip
2. Note: Cloud Run uses **VPC egress** for outbound connections
3. For us-central1, egress IPs come from GCP IP ranges

**GCP IP Ranges Discovery:**
```bash
# Download GCP IP ranges (JSON format)
curl -s https://www.gstatic.com/ipranges/cloud.json > gcp_ip_ranges.json

# Extract us-central1 ranges
cat gcp_ip_ranges.json | jq '.prefixes[] | select(.scope=="us-central1") | .ipv4Prefix' | sort -u
```

**Expected Ranges (verify before using):**
```
10.128.0.0/9       # GCP internal (if using VPC connector)
35.184.0.0/13      # us-central1 range 1
35.192.0.0/14      # us-central1 range 2
35.196.0.0/15      # us-central1 range 3
```

**⚠️ IMPORTANT:** Verify these ranges against current GCP documentation before deployment!

---

- [ ] **Step 2.1.2:** Document internal GCP network ranges

If services use VPC connector (private networking):
```
10.128.0.0/9       # GCP internal VPC
172.16.0.0/12      # Private network (if configured)
```

---

- [ ] **Step 2.1.3:** Create IP whitelist configuration file

**File:** Create `PGP_SERVER_v1/config/allowed_ips.py`

```python
#!/usr/bin/env python
"""
Cloud Run egress IP whitelist configuration.
Updated: 2025-11-16
Source: https://cloud.google.com/run/docs/securing/static-outbound-ip
"""

# Cloud Run egress IPs for us-central1
# IMPORTANT: Verify these ranges before production deployment
# Source: curl https://www.gstatic.com/ipranges/cloud.json | jq '.prefixes[] | select(.scope=="us-central1")'
CLOUD_RUN_US_CENTRAL1 = [
    "35.184.0.0/13",   # us-central1 range 1
    "35.192.0.0/14",   # us-central1 range 2
    "35.196.0.0/15",   # us-central1 range 3
    "35.202.0.0/16",   # us-central1 range 4 (verify)
]

# GCP Internal Network (if using VPC connector)
GCP_INTERNAL = [
    "10.128.0.0/9",    # GCP internal VPC
]

# Local development IPs
LOCAL_DEVELOPMENT = [
    "127.0.0.1",       # Localhost
    "::1",             # IPv6 localhost
]

# Combined whitelist for production
PRODUCTION_WHITELIST = CLOUD_RUN_US_CENTRAL1 + GCP_INTERNAL

# Development whitelist (includes localhost)
DEVELOPMENT_WHITELIST = PRODUCTION_WHITELIST + LOCAL_DEVELOPMENT

# Export based on environment
def get_allowed_ips(environment='production'):
    """
    Get allowed IP list for environment.

    Args:
        environment: 'production' or 'development'

    Returns:
        List of allowed IP ranges (CIDR notation)
    """
    if environment == 'development':
        return DEVELOPMENT_WHITELIST
    return PRODUCTION_WHITELIST
```

---

### Phase 2.2: Update IP Whitelist Implementation

- [ ] **Step 2.2.1:** Update IP whitelist initialization in server_manager.py

**Current Code:** `PGP_SERVER_v1/server_manager.py` (assumed initialization)

**Find Current Initialization:**
```bash
grep -n "init_ip_whitelist\|IPWhitelist" PGP_SERVER_v1/server_manager.py
```

**Update Initialization:**
```python
from security.ip_whitelist import init_ip_whitelist
from config.allowed_ips import get_allowed_ips
import os

# In create_app() or __init__():
environment = os.getenv('ENVIRONMENT', 'production')
allowed_ips = get_allowed_ips(environment)

ip_whitelist = init_ip_whitelist(allowed_ips)
app.config['ip_whitelist'] = ip_whitelist

logger.info(f"🔒 [IP_WHITELIST] Initialized with {len(allowed_ips)} IP ranges")
logger.info(f"🔒 [IP_WHITELIST] Environment: {environment}")
```

---

- [ ] **Step 2.2.2:** Add IP whitelist logging (debug mode only)

**Update** `PGP_SERVER_v1/security/ip_whitelist.py`:

```python
def __init__(self, allowed_ips: List[str]):
    """
    Initialize IP whitelist.

    Args:
        allowed_ips: List of allowed IPs/CIDR ranges
            Example: ['10.0.0.0/8', '35.123.45.67']
    """
    self.allowed_networks = [ip_network(ip) for ip in allowed_ips]
    logger.info("🔒 [IP_WHITELIST] Initialized with {} networks".format(
        len(self.allowed_networks)
    ))

    # Debug logging (only in development)
    if os.getenv('ENVIRONMENT') == 'development':
        for network in self.allowed_networks:
            logger.debug(f"   - {network}")
```

**Security Note:** Do NOT log allowed IPs in production (information disclosure)

---

### Phase 2.3: Testing IP Whitelist

- [ ] **Step 2.3.1:** Create IP whitelist unit tests

**File:** Create `PGP_SERVER_v1/tests/test_ip_whitelist.py`

```python
#!/usr/bin/env python
"""
Unit tests for IP whitelist configuration.
"""
import pytest
from security.ip_whitelist import IPWhitelist


class TestIPWhitelist:
    """Test IP whitelist validation."""

    def test_cloud_run_ips_allowed(self):
        """Test Cloud Run egress IPs are allowed."""
        whitelist = IPWhitelist([
            "35.184.0.0/13",
            "35.192.0.0/14",
        ])

        # Test IPs within Cloud Run ranges
        assert whitelist.is_allowed("35.184.0.1") is True
        assert whitelist.is_allowed("35.185.0.1") is True
        assert whitelist.is_allowed("35.192.0.1") is True

    def test_external_ips_blocked(self):
        """Test external IPs are blocked."""
        whitelist = IPWhitelist([
            "35.184.0.0/13",
        ])

        # Test external IPs
        assert whitelist.is_allowed("1.2.3.4") is False
        assert whitelist.is_allowed("8.8.8.8") is False
        assert whitelist.is_allowed("203.0.113.1") is False

    def test_localhost_allowed_in_dev(self):
        """Test localhost is allowed in development."""
        whitelist = IPWhitelist([
            "127.0.0.1",
            "::1",
        ])

        assert whitelist.is_allowed("127.0.0.1") is True

    def test_invalid_ip_format(self):
        """Test invalid IP format is rejected."""
        whitelist = IPWhitelist(["35.184.0.0/13"])

        assert whitelist.is_allowed("not-an-ip") is False
        assert whitelist.is_allowed("") is False
```

**Run Tests:**
```bash
cd PGP_SERVER_v1
pytest tests/test_ip_whitelist.py -v
```

---

- [ ] **Step 2.3.2:** Test with actual Cloud Run egress IPs

**Test Procedure:**
1. Deploy to staging
2. Make request from another Cloud Run service
3. Check logs for client IP
4. Verify IP is within configured ranges

**Log Check:**
```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=pgp-server-v1" --limit=50 --format=json | jq '.[] | select(.textPayload | contains("IP_WHITELIST"))'
```

**Expected Log:**
```
✅ [IP_WHITELIST] Allowed request from 35.184.x.x
```

---

- [ ] **Step 2.3.3:** Test IP whitelist bypass attempts

**Manual Test:**
```bash
# Attempt to access webhook from unauthorized IP (should fail)
curl -X POST https://pgp-server-v1-xxx.run.app/webhook/notification \
  -H "Content-Type: application/json" \
  -d '{"test": "unauthorized"}' \
  -v
```

**Expected Response:**
```
HTTP/1.1 403 Forbidden
{"error": "Unauthorized IP address"}
```

---

### Phase 2.4: Documentation

- [ ] **Step 2.4.1:** Document IP whitelist configuration

**File:** `PGP_SERVER_v1/SECURITY.md` (append to existing)

```markdown
## IP Whitelist Configuration

### Cloud Run Egress IPs

PGP_SERVER_v1 restricts webhook access to known Cloud Run egress IPs.

**Allowed Ranges (us-central1):**
- `35.184.0.0/13` - Cloud Run range 1
- `35.192.0.0/14` - Cloud Run range 2
- `35.196.0.0/15` - Cloud Run range 3
- `10.128.0.0/9` - GCP internal VPC

**Configuration File:** `config/allowed_ips.py`

**Environment Variable:** `ENVIRONMENT=production|development`
- Production: Cloud Run IPs only
- Development: Cloud Run IPs + localhost

### Updating IP Ranges

IP ranges may change. Verify current ranges before deployment:

```bash
curl -s https://www.gstatic.com/ipranges/cloud.json | \
  jq '.prefixes[] | select(.scope=="us-central1") | .ipv4Prefix'
```

Update `config/allowed_ips.py` if ranges have changed.

### Monitoring

Monitor blocked requests:
```bash
gcloud logging read "resource.type=cloud_run_revision \
  AND textPayload:\"Blocked request from\"" --limit=20
```
```

---

- [ ] **Step 2.4.2:** Update deployment documentation

Add IP whitelist configuration to deployment checklist.

---

## Issue 3: Debug Logging Removal

### Overview
**Severity:** 🟡 MEDIUM
**Risk:** Information disclosure via logs
**Impact:** Sensitive data exposure, verbose logs increase costs
**Effort:** <1 day

### Affected Components

**Debug Logging Found:**
1. `PGP_WEBAPI_v1/pgp_webapi_v1.py:93-94` - CORS debug
2. `PGP_SERVER_v1/database.py` - Database debug (8 locations)
3. `PGP_SERVER_v1/bot_manager.py` - Bot debug (5 locations)
4. `PGP_SERVER_v1/menu_handlers.py` - Menu debug (11 locations)
5. `PGP_SERVER_v1/app_initializer.py` - Payment gateway debug (2 locations)

---

### Phase 3.1: Remove CORS Debug Logging

- [ ] **Step 3.1.1:** Remove CORS debug from PGP_WEBAPI_v1

**Location:** `PGP_WEBAPI_v1/pgp_webapi_v1.py:93-106`

**Current Code (Lines 90-107):**
```python
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    print(f"🔍 CORS Debug - Origin: {origin}, Allowed origins: {cors_origins}")
    print(f"🔍 CORS Debug - Origin in list: {origin in cors_origins}")

    if origin in cors_origins:
        print(f"✅ Adding CORS headers for origin: {origin}")
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Authorization'
    else:
        print(f"❌ Origin not in allowed list or missing")

    print(f"🔍 Response headers: {dict(response.headers)}")
    return response
```

**New Code:**
```python
@app.after_request
def after_request(response):
    """Add CORS headers to response if origin is whitelisted."""
    origin = request.headers.get('Origin')

    if origin in cors_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Authorization'

        # Structured logging (INFO level, not DEBUG)
        logger.info(f"✅ [CORS] Added headers for origin: {origin}")
    elif origin:
        # Log rejected origins for security monitoring
        logger.warning(f"⚠️ [CORS] Rejected origin: {origin}")

    return response
```

**Changes:**
1. Remove 4 debug print statements
2. Add structured logging with logger.info/warning
3. Only log origin (not full headers - sensitive data)
4. Keep security logging (rejected origins)

---

- [ ] **Step 3.1.2:** Remove preflight debug logging

**Location:** `PGP_WEBAPI_v1/pgp_webapi_v1.py:86`

**Current Code:**
```python
print(f"✅ Preflight handled for origin: {origin}")
```

**New Code:**
```python
logger.debug(f"✅ [CORS] Preflight handled for origin: {origin}")
```

**Change:** Use logger.debug instead of print (disabled by default in production)

---

### Phase 3.2: Convert Database Debug to Structured Logging

**Location:** `PGP_SERVER_v1/database.py`

**Strategy:** Replace `print(f"🔍 [DEBUG] ...")` with `logger.debug(...)`

- [ ] **Step 3.2.1:** Add logger import at top of file

```python
import logging

logger = logging.getLogger(__name__)
```

---

- [ ] **Step 3.2.2:** Replace debug print statements (8 locations)

**Lines to Update:** 178, 181, 206, 212, 242, 245, 248, 664

**Pattern:**
```python
# BEFORE
print(f"🔍 [DEBUG] Looking up closed_channel_id...")

# AFTER
logger.debug(f"🔍 [DEBUG] Looking up closed_channel_id...")
```

**Automated Replacement:**
```bash
cd PGP_SERVER_v1
sed -i 's/print(f"🔍 \[DEBUG\]/logger.debug(f"🔍 [DEBUG]/g' database.py
sed -i 's/print(f"📋 \[DEBUG\]/logger.debug(f"📋 [DEBUG]/g' database.py
sed -i 's/print(f"💰 \[DEBUG\]/logger.debug(f"💰 [DEBUG]/g' database.py
sed -i 's/print(f"🎯 \[DEBUG\]/logger.debug(f"🎯 [DEBUG]/g' database.py
sed -i 's/print(f"ℹ️ \[DEBUG\]/logger.debug(f"ℹ️ [DEBUG]/g' database.py
sed -i 's/print(f"❌ \[DEBUG\]/logger.debug(f"❌ [DEBUG]/g' database.py
sed -i 's/print(f"📝 \[DEBUG\]/logger.debug(f"📝 [DEBUG]/g' database.py
```

**Verify Changes:**
```bash
grep -n "print.*DEBUG" database.py  # Should return NO results
```

---

### Phase 3.3: Convert Bot Manager Debug to Structured Logging

**Location:** `PGP_SERVER_v1/bot_manager.py`

- [ ] **Step 3.3.1:** Add logger import (if not present)

- [ ] **Step 3.3.2:** Replace debug print statements (5 locations)

**Lines:** 121, 131, 139, 142, 150, 158, 161

**Automated Replacement:**
```bash
cd PGP_SERVER_v1
sed -i 's/print(f"⚙️ \[DEBUG\]/logger.debug(f"⚙️ [DEBUG]/g' bot_manager.py
sed -i 's/print(f"💳 \[DEBUG\]/logger.debug(f"💳 [DEBUG]/g' bot_manager.py
sed -i 's/print(f"✅ \[DEBUG\]/logger.debug(f"✅ [DEBUG]/g' bot_manager.py
sed -i 's/print(f"❌ \[DEBUG\]/logger.debug(f"❌ [DEBUG]/g' bot_manager.py
```

---

### Phase 3.4: Convert Menu Handlers Debug to Structured Logging

**Location:** `PGP_SERVER_v1/menu_handlers.py`

- [ ] **Step 3.4.1:** Add logger import (if not present)

- [ ] **Step 3.4.2:** Replace debug print statements (11 locations)

**Lines:** 68, 135, 140, 144, 173, 175, 179, 188, 191, 227, 248

**Automated Replacement:**
```bash
cd PGP_SERVER_v1
sed -i 's/print(f"⚠️ \[DEBUG\]/logger.debug(f"⚠️ [DEBUG]/g' menu_handlers.py
sed -i 's/print(f"🎯 \[DEBUG\]/logger.debug(f"🎯 [DEBUG]/g' menu_handlers.py
sed -i 's/print(f"⚙️ \[DEBUG\]/logger.debug(f"⚙️ [DEBUG]/g' menu_handlers.py
sed -i 's/print(f"🚀 \[DEBUG\]/logger.debug(f"🚀 [DEBUG]/g' menu_handlers.py
sed -i 's/print(f"📅 \[DEBUG\]/logger.debug(f"📅 [DEBUG]/g' menu_handlers.py
sed -i 's/print(f"ℹ️ \[DEBUG\]/logger.debug(f"ℹ️ [DEBUG]/g' menu_handlers.py
sed -i 's/print(f"💰 \[DEBUG\]/logger.debug(f"💰 [DEBUG]/g' menu_handlers.py
sed -i 's/print(f"✅ \[DEBUG\]/logger.debug(f"✅ [DEBUG]/g' menu_handlers.py
```

---

### Phase 3.5: Convert App Initializer Debug to Structured Logging

**Location:** `PGP_SERVER_v1/app_initializer.py`

- [ ] **Step 3.5.1:** Replace debug print statements (2 locations)

**Lines:** 120, 126

---

### Phase 3.6: Set Production Logging Level

- [ ] **Step 3.6.1:** Configure logging level via environment variable

**File:** `PGP_SERVER_v1/server_manager.py` OR `app_initializer.py`

**Add Logging Configuration:**
```python
import logging
import os

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()  # Default INFO in production
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info(f"🔧 [CONFIG] Logging level set to: {LOG_LEVEL}")
```

**Environment Variables:**
- Production: `LOG_LEVEL=INFO` (DEBUG logs suppressed)
- Development: `LOG_LEVEL=DEBUG` (All logs visible)
- Troubleshooting: `LOG_LEVEL=DEBUG` (Temporarily enable debug)

---

### Phase 3.7: Verify Debug Logging Removal

- [ ] **Step 3.7.1:** Search for remaining debug print statements

**Search Commands:**
```bash
# Find all print statements with DEBUG
grep -r "print.*DEBUG" --include="*.py" PGP_SERVER_v1/ PGP_WEBAPI_v1/

# Find all print statements with debug emojis
grep -r "print(f\"🔍" --include="*.py" PGP_SERVER_v1/ PGP_WEBAPI_v1/
```

**Expected:** NO results (all converted to logger.debug)

---

- [ ] **Step 3.7.2:** Verify logging configuration

**Test:**
```bash
# Start service with INFO level (default)
LOG_LEVEL=INFO python pgp_webapi_v1.py

# Should NOT see debug logs

# Start with DEBUG level
LOG_LEVEL=DEBUG python pgp_webapi_v1.py

# Should see debug logs
```

---

### Phase 3.8: Production Logging Best Practices

- [ ] **Step 3.8.1:** Document sensitive data redaction policy

**File:** Create `LOGGING_POLICY.md`

```markdown
# Logging Policy - PGP_v1

## Sensitive Data - DO NOT LOG

**NEVER log these values:**
- Private keys (HOST_WALLET_PRIVATE_KEY)
- API keys (NOWPAYMENTS_API_KEY, SENDGRID_API_KEY)
- Passwords (DATABASE_PASSWORD)
- Full JWT tokens
- User wallet addresses (log truncated: 0x1234...5678)
- Email addresses (log hashed or truncated)
- Payment amounts (aggregate only, not individual)

## Logging Levels

### CRITICAL
System failures requiring immediate attention

### ERROR
Failed operations that need investigation

### WARNING
Recoverable issues (rejected CORS origins, invalid timestamps)

### INFO
Normal operations (successful payments, signature validation)

### DEBUG
Detailed troubleshooting info (NEVER in production)

## Production Configuration

```bash
LOG_LEVEL=INFO  # Default for production
LOG_LEVEL=DEBUG # Only for troubleshooting (time-limited)
```

## Structured Logging Format

```python
logger.info(f"✅ [COMPONENT] Action completed: param1={value1}, param2={value2}")
```

## Monitoring & Alerts

- ERROR logs trigger alerts
- WARNING logs reviewed daily
- DEBUG logs disabled by default
```

---

- [ ] **Step 3.8.2:** Audit logs for sensitive data exposure

**Review Checklist:**
- [ ] Private keys NOT logged
- [ ] API keys NOT logged
- [ ] Database passwords NOT logged
- [ ] Full wallet addresses NOT logged (use truncation)
- [ ] Email addresses handled carefully
- [ ] JWT tokens NOT logged in full

**Search for Potential Leaks:**
```bash
grep -r "private.*key\|api.*key\|password" --include="*.py" PGP_*/ | grep -i "print\|logger"
```

---

## Integration Testing

### Test Plan

- [ ] **Test 1:** HMAC timestamp validation end-to-end
  - [ ] Valid timestamp accepted
  - [ ] Old timestamp rejected (replay attack prevented)
  - [ ] Future timestamp rejected
  - [ ] Modified timestamp rejected
  - [ ] Missing timestamp rejected

- [ ] **Test 2:** IP whitelist validation
  - [ ] Cloud Run egress IPs allowed
  - [ ] External IPs blocked
  - [ ] Localhost allowed in development
  - [ ] Invalid IP format handled

- [ ] **Test 3:** Logging configuration
  - [ ] Debug logs suppressed in production (LOG_LEVEL=INFO)
  - [ ] Debug logs visible in development (LOG_LEVEL=DEBUG)
  - [ ] No sensitive data in logs
  - [ ] Structured logging format consistent

- [ ] **Test 4:** Complete payment flow
  - [ ] NowPayments IPN → PGP_NP_IPN_v1
  - [ ] PGP_NP_IPN_v1 → PGP_ORCHESTRATOR_v1 (with timestamp)
  - [ ] PGP_ORCHESTRATOR_v1 → PGP_INVITE_v1 (invitation sent)
  - [ ] PGP_ORCHESTRATOR_v1 → PGP_SPLIT1_v1 (payment splitting)
  - [ ] All signatures validated with timestamp
  - [ ] No debug logs in production

---

## Deployment & Rollback

### Pre-Deployment Checklist

- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Code review completed
- [ ] Documentation updated (SECURITY.md, API.md, LOGGING_POLICY.md)
- [ ] Deployment plan created
- [ ] Rollback procedure documented

### Deployment Steps (Staging)

1. [ ] Deploy PGP_COMMON updates (timestamp signature)
2. [ ] Deploy PGP_SERVER_v1 (HMAC verification, IP whitelist, logging)
3. [ ] Deploy all sender services (ORCHESTRATOR, SPLIT, HOSTPAY, etc.)
4. [ ] Verify health checks pass
5. [ ] Run integration tests
6. [ ] Monitor logs for errors
7. [ ] Test replay attack prevention manually

### Deployment Steps (Production)

**Prerequisites:**
- [ ] Staging tests passed for 48+ hours
- [ ] No critical issues found
- [ ] Security audit approved

**Deployment:**
1. [ ] Schedule maintenance window (low traffic period)
2. [ ] Deploy all services within 5-minute window
3. [ ] Monitor for 1 hour post-deployment
4. [ ] Verify payment processing working
5. [ ] Check signature validation logs
6. [ ] Confirm no debug logs in production

### Rollback Procedure

**Trigger Conditions:**
- Signature validation failures > 5%
- Payment processing errors > 1%
- Service health check failures
- Any CRITICAL errors in logs

**Rollback Steps:**
```bash
# Revert all services to previous version
./deploy/rollback_all_services.sh

# Or manual rollback:
gcloud run services update pgp-server-v1 --image=gcr.io/pgp-live/pgp-server-v1:previous
gcloud run services update pgp-orchestrator-v1 --image=gcr.io/pgp-live/pgp-orchestrator-v1:previous
# ... repeat for all 12 services
```

**Post-Rollback:**
1. Verify services healthy
2. Review logs for root cause
3. Fix issues in development
4. Re-test before re-deployment

---

## Monitoring & Alerts

### Metrics to Monitor

- [ ] **HMAC Timestamp Failures**
  - Query: `textPayload:"Timestamp outside acceptable window"`
  - Threshold: > 5 failures/hour
  - Action: Investigate clock drift or replay attack

- [ ] **IP Whitelist Blocks**
  - Query: `textPayload:"Blocked request from"`
  - Threshold: > 10 blocks/hour
  - Action: Verify Cloud Run IP ranges are current

- [ ] **Debug Logs in Production**
  - Query: `textPayload:"[DEBUG]"`
  - Threshold: > 0 (should be ZERO)
  - Action: Check LOG_LEVEL environment variable

- [ ] **Signature Validation Errors**
  - Query: `textPayload:"Invalid signature"`
  - Threshold: > 1% of requests
  - Action: Check secret key configuration

### Alert Configuration

**Cloud Monitoring Alerts:**
```yaml
# HMAC timestamp failures
- name: hmac-timestamp-failures
  condition: rate(timestamp_failures) > 5/hour
  severity: WARNING
  notification: security-team

# IP whitelist blocks
- name: ip-whitelist-blocks
  condition: rate(ip_blocks) > 10/hour
  severity: WARNING
  notification: security-team

# Debug logs in production
- name: debug-logs-production
  condition: count(debug_logs) > 0
  severity: ERROR
  notification: dev-team
```

---

## Success Criteria

### Issue 1: HMAC Timestamp Validation ✅

- [ ] Timestamp validation implemented in HMACAuth
- [ ] Signature generation includes timestamp
- [ ] All 12 services use updated signature format
- [ ] Unit tests passing (10+ test cases)
- [ ] Integration tests passing
- [ ] Replay attack prevention verified
- [ ] Documentation updated

### Issue 2: IP Whitelist Configuration ✅

- [ ] Cloud Run egress IPs documented
- [ ] IP whitelist configured with verified ranges
- [ ] Unit tests passing
- [ ] Integration tests confirm Cloud Run IPs allowed
- [ ] External IPs blocked
- [ ] Documentation updated

### Issue 3: Debug Logging Removal ✅

- [ ] CORS debug logging removed
- [ ] Database debug converted to logger.debug
- [ ] Bot manager debug converted to logger.debug
- [ ] Menu handlers debug converted to logger.debug
- [ ] Production logging level set to INFO
- [ ] No debug logs visible in production
- [ ] Logging policy documented
- [ ] No sensitive data in logs

### Overall Security Posture

- [ ] Replay attack vulnerability: 🔴 CRITICAL → ✅ FIXED
- [ ] IP whitelist incomplete: 🔴 HIGH → ✅ FIXED
- [ ] Debug logging in production: 🟡 MEDIUM → ✅ FIXED
- [ ] All tests passing
- [ ] Security documentation complete
- [ ] Deployment successful
- [ ] No regressions

---

## Timeline

### Week 1: Development & Unit Testing
- Days 1-2: HMAC timestamp validation (Issue 1)
- Day 3: IP whitelist configuration (Issue 2)
- Day 4: Debug logging removal (Issue 3)

### Week 2: Integration Testing & Deployment
- Days 1-2: Integration testing
- Day 3: Staging deployment
- Day 4: Production deployment
- Day 5: Monitoring & validation

**Total Effort:** 8-10 days (including testing and deployment)

---

## References

### OWASP Best Practices
- **Replay Attack Prevention:** https://cheatsheetseries.owasp.org/cheatsheets/Web_Service_Security_Cheat_Sheet.html#message-replay-protection
- **HMAC Signatures:** https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html#hmac-based-message-authentication
- **Logging Guidance:** https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

### Google Cloud Documentation
- **Cloud Run Networking:** https://cloud.google.com/run/docs/securing/static-outbound-ip
- **GCP IP Ranges:** https://www.gstatic.com/ipranges/cloud.json
- **Cloud Logging:** https://cloud.google.com/logging/docs

### Flask Security
- **Security Headers:** https://flask-talisman.readthedocs.io/
- **CORS Configuration:** https://flask-cors.readthedocs.io/

---

**END OF CHECKLIST**

Last Updated: 2025-11-16
Version: 1.0
Status: Ready for implementation
