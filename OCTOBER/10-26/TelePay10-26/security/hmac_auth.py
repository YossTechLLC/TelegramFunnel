#!/usr/bin/env python
"""
HMAC-based request authentication for webhook endpoints.
Verifies requests from Cloud Run services using shared secret.
"""
import hmac
import hashlib
import logging
from functools import wraps
from flask import request, abort

logger = logging.getLogger(__name__)


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


def init_hmac_auth(secret_key: str) -> HMACAuth:
    """
    Factory function to initialize HMAC authenticator.

    Args:
        secret_key: Shared secret (fetch from Secret Manager)

    Returns:
        HMACAuth instance
    """
    return HMACAuth(secret_key)
