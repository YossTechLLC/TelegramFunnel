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


class HMACAuth:
    """
    HMAC signature verification for webhook requests.

    Security Features:
    - SHA256 HMAC signature
    - Timing-safe comparison
    - Configurable secret per endpoint
    - Detailed logging for audit trail
    """

    def __init__(self, secret_key: str):
        """
        Initialize HMAC authenticator.

        Args:
            secret_key: Shared secret for HMAC signing (from Secret Manager)
        """
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key
        logger.info("🔒 [HMAC] Authenticator initialized")

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

    def require_signature(self, f):
        """
        Decorator to require HMAC signature and timestamp on Flask route.

        Security:
        - Requires both X-Signature and X-Request-Timestamp headers
        - Validates timestamp is within acceptable window (prevents replay attacks)
        - Verifies signature matches payload + timestamp

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

            # Check for missing headers
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
                logger.error("❌ [HMAC] Invalid signature or expired timestamp from {}".format(
                    request.remote_addr
                ))
                abort(403, "Invalid signature or expired timestamp")

            logger.info("✅ [HMAC] Valid signature and timestamp from {}".format(
                request.remote_addr
            ))
            return f(*args, **kwargs)

        return decorated_function


def init_hmac_auth(secret_key: str) -> HMACAuth:
    """
    Factory function to initialize HMAC authenticator.

    Args:
        secret_key: Shared secret (fetch from Secret Manager)

    Returns:
        HMACAuth instance
    """
    return HMACAuth(secret_key)
