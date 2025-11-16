# HMAC Timestamp Validation Security Documentation

**Version:** 1.0
**Last Updated:** 2025-11-16
**Status:** ✅ IMPLEMENTED

---

## Executive Summary

This document describes the HMAC timestamp validation implementation that prevents replay attacks in PGP_v1 inter-service communication. The implementation adds Unix timestamp validation to HMAC-SHA256 signatures, ensuring requests cannot be captured and replayed beyond a 5-minute window.

**Security Benefit:**
- **Before:** Captured webhook requests could be replayed indefinitely
- **After:** Requests expire after 5 minutes (300 seconds)

---

## Architecture Overview

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SENDER (PGP_ORCHESTRATOR_v1)                                           │
│  ────────────────────────────────                                       │
│  1. Generate Unix timestamp: timestamp = int(time.time())               │
│  2. Create message: message = f"{timestamp}:{payload_json}"             │
│  3. Calculate HMAC: signature = HMAC-SHA256(message, secret_key)        │
│  4. Send request with headers:                                          │
│     - X-Signature: <signature>                                          │
│     - X-Request-Timestamp: <timestamp>                                  │
│     - Content-Type: application/json                                    │
│     - Body: <payload_json>                                              │
└─────────────────────────────────────────────────────────────────────────┘
                                |
                                | HTTP POST
                                v
┌─────────────────────────────────────────────────────────────────────────┐
│  RECEIVER (PGP_SERVER_v1)                                               │
│  ─────────────────────────                                              │
│  1. Extract headers: signature, timestamp                               │
│  2. Validate timestamp within window (now ± 5 minutes)                  │
│     - If expired: REJECT (403 Forbidden)                                │
│  3. Calculate expected signature: HMAC-SHA256(timestamp:payload)        │
│  4. Compare signatures (timing-safe comparison)                         │
│     - If mismatch: REJECT (403 Forbidden)                               │
│  5. Accept request (200 OK)                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### 1. Timestamp Tolerance Window

```python
# PGP_SERVER_v1/security/hmac_auth.py
TIMESTAMP_TOLERANCE_SECONDS = 300  # 5 minutes
```

**Rationale:**
- **5 minutes** is industry standard for timestamp-based replay protection
- Balances security (shorter window) vs reliability (longer window)
- Accounts for:
  - Clock drift between Cloud Run instances
  - Network latency
  - Cloud Tasks queue delays
  - GCP internal routing time

**Security Trade-offs:**
- **Shorter window (e.g., 60s):** More secure but may reject legitimate delayed requests
- **Longer window (e.g., 15min):** More reliable but larger replay attack window
- **5 minutes:** Optimal balance for Cloud Run → Cloud Run communication

---

### 2. Signature Generation (Sender Side)

**Location:** `PGP_COMMON/cloudtasks/base_client.py:115-181`

**Implementation:**
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
        "X-Signature": signature,
        "X-Request-Timestamp": timestamp
    }

    return self.create_task(
        queue_name=queue_name,
        target_url=target_url,
        payload=payload,
        schedule_delay_seconds=schedule_delay_seconds,
        custom_headers=custom_headers
    )
```

**Key Security Features:**
- ✅ Timestamp prefix in message (`timestamp:payload`) prevents reordering attacks
- ✅ Unix timestamp format (seconds since epoch) - simple and unambiguous
- ✅ Timestamp generated at request creation time (not task execution time)
- ✅ HMAC-SHA256 provides cryptographic integrity

**Message Format:**
```
message = "{unix_timestamp}:{json_payload}"
Example: "1700000000:{'user_id':123,'amount':100}"
```

---

### 3. Signature Verification (Receiver Side)

**Location:** `PGP_SERVER_v1/security/hmac_auth.py:99-132`

**Implementation:**
```python
def verify_signature(self, payload: bytes, provided_signature: str, timestamp: str) -> bool:
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

**Order of Validation (FAIL-FAST):**
1. **First:** Check timestamp (cheap operation, fails quickly)
2. **Second:** Calculate signature (expensive operation, only if timestamp valid)

**Why this order matters:**
- Timestamp validation is O(1) - simple integer comparison
- Signature calculation is O(n) - cryptographic hash operation
- Rejecting expired requests BEFORE signature calculation prevents:
  - CPU exhaustion attacks (flooding with expired requests)
  - Timing attacks (observing signature calculation time)

---

### 4. Timestamp Validation Method

**Location:** `PGP_SERVER_v1/security/hmac_auth.py:63-97`

**Implementation:**
```python
def validate_timestamp(self, timestamp: str) -> bool:
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

**Security Features:**
- ✅ Uses absolute time difference - prevents both past and future-dated requests
- ✅ Handles invalid timestamp formats gracefully (ValueError, TypeError)
- ✅ Logs timestamp violations for security monitoring
- ✅ Returns False on any error (fail-secure)

**Validation Logic:**
```
Request VALID if: |current_time - request_time| ≤ 300 seconds

Examples:
- Request from 4 minutes ago: VALID (240s < 300s)
- Request from 6 minutes ago: INVALID (360s > 300s)
- Request from 4 minutes in future: VALID (handles clock drift)
- Request from 6 minutes in future: INVALID (prevents future-dated attacks)
```

---

### 5. Flask Decorator Integration

**Location:** `PGP_SERVER_v1/security/hmac_auth.py:134-185`

**Implementation:**
```python
def require_signature(self, f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get signature from header
        signature = request.headers.get('X-Signature')

        # Get timestamp from header
        timestamp = request.headers.get('X-Request-Timestamp')

        # Check for missing headers
        if not signature:
            logger.warning("⚠️ [HMAC] Missing X-Signature header")
            abort(401, "Missing signature header")

        if not timestamp:
            logger.warning("⚠️ [HMAC] Missing X-Request-Timestamp header")
            abort(401, "Missing timestamp header")

        # Get request payload
        payload = request.get_data()

        # Verify signature with timestamp
        if not self.verify_signature(payload, signature, timestamp):
            logger.error("❌ [HMAC] Invalid signature or expired timestamp")
            abort(403, "Invalid signature or expired timestamp")

        logger.info("✅ [HMAC] Valid signature and timestamp")
        return f(*args, **kwargs)

    return decorated_function
```

**Usage:**
```python
@app.route('/webhook', methods=['POST'])
@hmac_auth.require_signature
def handle_notification():
    return jsonify({'status': 'ok'})
```

**HTTP Response Codes:**
- **401 Unauthorized:** Missing X-Signature or X-Request-Timestamp header
- **403 Forbidden:** Invalid signature or expired timestamp
- **200 OK:** Valid signature and timestamp

---

## Attack Scenarios & Mitigations

### 1. Replay Attack (PRIMARY THREAT)

**Attack Scenario:**
```
1. Attacker intercepts legitimate request at 10:00:00 AM
   Headers:
   - X-Signature: abc123...
   - X-Request-Timestamp: 1700000000
   - Body: {"action":"transfer","amount":1000}

2. Attacker replays request at 10:10:00 AM (10 minutes later)
   Same headers and body
```

**Mitigation:**
```
✅ BLOCKED - Timestamp expired

Request time:  10:00:00 AM (1700000000)
Current time:  10:10:00 AM (1700000600)
Time diff:     600 seconds > 300 seconds (TOLERANCE)

Result: 403 Forbidden
```

---

### 2. Payload Tampering Attack

**Attack Scenario:**
```
1. Attacker intercepts legitimate request
   Timestamp: 1700000000
   Payload: {"amount": 100}
   Signature: abc123...

2. Attacker modifies payload
   Timestamp: 1700000000 (unchanged)
   Payload: {"amount": 999} (MODIFIED)
   Signature: abc123... (unchanged)
```

**Mitigation:**
```
✅ BLOCKED - Signature mismatch

Expected signature (server calculates):
  message = "1700000000:{'amount':999}"
  expected = HMAC-SHA256(message, secret)
  expected = "xyz789..."

Provided signature: "abc123..."

Result: abc123... != xyz789... → 403 Forbidden
```

---

### 3. Timing Attack on Signature Comparison

**Attack Scenario:**
```
Attacker tries to guess signature by measuring response times:
- Signature "a000..." → Response in 10ms
- Signature "b000..." → Response in 11ms (possibly correct first byte?)
```

**Mitigation:**
```
✅ BLOCKED - Timing-safe comparison

Uses hmac.compare_digest():
- Compares ALL bytes regardless of first mismatch
- Constant-time comparison (timing independent of input)
- Python 3.3+ standard library function

Result: All invalid signatures take same time to reject
```

**Code:**
```python
return hmac.compare_digest(expected_signature, provided_signature)
```

---

### 4. Clock Drift Attack

**Attack Scenario:**
```
Sender and receiver have misaligned clocks:
- Sender clock: 10:00:00 AM
- Receiver clock: 10:06:00 AM (6 minutes ahead)

Legitimate request sent at sender 10:00:00 AM
Received at receiver 10:06:00 AM
Time diff: 6 minutes > 5 minutes tolerance
```

**Mitigation:**
```
✅ HANDLED - Google Cloud NTP synchronization

Google Cloud Run instances use synchronized NTP:
- Clock drift typically < 1 second
- 5-minute tolerance window accounts for worst-case drift
- Monitoring alerts if clock drift exceeds threshold

Recommendation: Monitor timestamp rejection rates
```

---

### 5. Future-Dated Request Attack

**Attack Scenario:**
```
Attacker sends request with future timestamp:
- Current time: 10:00:00 AM
- Request timestamp: 10:10:00 AM (10 minutes in future)
- Goal: Request valid for 15 minutes total (5 min past + 10 min future)
```

**Mitigation:**
```
✅ BLOCKED - Absolute time difference check

abs(current_time - request_time) = abs(1700000000 - 1700000600)
                                  = 600 seconds > 300 seconds

Result: 403 Forbidden
```

**Code:**
```python
time_diff = abs(current_time - request_time)  # Absolute value catches future timestamps
```

---

## Security Best Practices Applied

### OWASP Recommendations

✅ **A02:2021 - Cryptographic Failures**
- Uses HMAC-SHA256 (industry standard)
- Timing-safe signature comparison
- No custom cryptography

✅ **A07:2021 - Identification and Authentication Failures**
- Multi-factor authentication (signature + timestamp)
- Timestamp prevents session replay
- Detailed logging for audit trail

✅ **A09:2021 - Security Logging and Monitoring Failures**
- Logs all authentication failures
- Logs timestamp violations with time difference
- Monitoring-ready log format

### Google Cloud Best Practices

✅ **Cloud Run Security**
- Uses Cloud Secret Manager for signing keys
- Minimal trust between services (every request verified)
- Defense in depth (HMAC + IP whitelist + rate limiting)

✅ **Cloud Tasks Security**
- Custom headers for authentication
- HTTPS-only communication
- Task queues isolated per service

---

## Monitoring & Alerting

### Key Metrics to Monitor

**1. Timestamp Rejection Rate**
```
Query:
  resource.type="cloud_run_revision"
  "⏰ [HMAC] Timestamp outside acceptable window"

Alert Threshold: > 5% of requests
Indicates: Possible clock drift or replay attack
```

**2. Signature Mismatch Rate**
```
Query:
  resource.type="cloud_run_revision"
  "❌ [HMAC] Signature mismatch"

Alert Threshold: > 1% of requests
Indicates: Possible tampering or key mismatch
```

**3. Missing Header Rate**
```
Query:
  resource.type="cloud_run_revision"
  "⚠️ [HMAC] Missing signature or timestamp"

Alert Threshold: > 0.1% of requests
Indicates: Service misconfiguration or API client error
```

### Sample Cloud Logging Query

```
resource.type="cloud_run_revision"
resource.labels.service_name="pgp-server-v1"
(
  "⏰ [HMAC] Timestamp outside acceptable window" OR
  "❌ [HMAC] Signature mismatch" OR
  "⚠️ [HMAC] Missing signature or timestamp"
)
```

---

## Testing

### Unit Tests

**Location:** `PGP_SERVER_v1/tests/test_hmac_timestamp_validation.py`

**Test Coverage:**
- ✅ Timestamp validation (valid, expired, future, invalid format)
- ✅ Signature generation with timestamp
- ✅ Signature verification with timestamp
- ✅ Flask decorator integration
- ✅ Replay attack scenario
- ✅ Payload tampering scenario
- ✅ End-to-end integration

**Run Tests:**
```bash
cd PGP_SERVER_v1
pytest tests/test_hmac_timestamp_validation.py -v
```

**Location:** `PGP_COMMON/tests/test_cloudtasks_timestamp_signature.py`

**Test Coverage:**
- ✅ Timestamp header generation
- ✅ Signature format validation
- ✅ Different payloads produce different signatures
- ✅ Different timestamps produce different signatures
- ✅ End-to-end sender → receiver flow

**Run Tests:**
```bash
cd PGP_COMMON
pytest tests/test_cloudtasks_timestamp_signature.py -v
```

---

## Deployment Considerations

### Breaking Change

⚠️ **WARNING:** This is a BREAKING CHANGE

**Before:**
- Header: `X-Webhook-Signature`
- Signature: `HMAC-SHA256(payload)`

**After:**
- Headers: `X-Signature` + `X-Request-Timestamp`
- Signature: `HMAC-SHA256(timestamp:payload)`

### Atomic Deployment Required

**Services to Deploy Simultaneously:**
1. `PGP_COMMON` (shared library)
2. `PGP_ORCHESTRATOR_v1` (sender - uses create_signed_task)
3. `PGP_SERVER_v1` (receiver - uses require_signature decorator)

**Deployment Window:** < 5 minutes

**Rollback Plan:**
```bash
# If deployment fails, rollback ALL services
gcloud run services update pgp-orchestrator-v1 --revision=<previous-revision>
gcloud run services update pgp-server-v1 --revision=<previous-revision>
```

### Production Checklist

- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Deployed to staging environment
- [ ] Manual testing completed (valid request, expired timestamp, invalid signature)
- [ ] Cloud Logging queries configured
- [ ] Monitoring alerts configured
- [ ] Rollback plan documented
- [ ] On-call engineer notified

---

## FAQ

**Q: Why 5 minutes instead of 1 minute?**
A: 5 minutes accounts for Cloud Tasks queue delays, network latency, and clock drift while still providing strong replay protection.

**Q: What if Cloud Run instances have clock drift?**
A: Google Cloud Run uses NTP synchronization with typically < 1 second drift. The 5-minute window provides ample buffer.

**Q: Can I use a different tolerance window?**
A: Yes, modify `TIMESTAMP_TOLERANCE_SECONDS` in `hmac_auth.py`, but 300 seconds (5 minutes) is recommended.

**Q: What about scheduled tasks with delays?**
A: Timestamp is generated at task CREATION time, not execution time. A task scheduled 10 minutes in the future will have a current timestamp, so it will be valid when executed.

**Q: How do I debug timestamp rejections?**
A: Check Cloud Logging for "⏰ [HMAC] Timestamp outside acceptable window" with time difference. Compare sender and receiver clocks.

---

## References

- [OWASP Authentication Cheat Sheet](https://cheats.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [RFC 2104: HMAC (Keyed-Hashing for Message Authentication)](https://www.ietf.org/rfc/rfc2104.txt)
- [Google Cloud Tasks Best Practices](https://cloud.google.com/tasks/docs/creating-http-target-tasks)
- [Python hmac.compare_digest() Documentation](https://docs.python.org/3/library/hmac.html#hmac.compare_digest)

---

**Document Owner:** PGP_v1 Security Team
**Review Cycle:** Quarterly
**Next Review:** 2025-02-16
