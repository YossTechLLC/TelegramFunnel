#!/usr/bin/env python
"""
Request signing utility for outbound requests to TelePay10-26.
Uses HMAC-SHA256 for cryptographic signing of webhook requests.
"""
import hmac
import hashlib
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RequestSigner:
    """Signs outbound HTTP requests with HMAC-SHA256."""

    def __init__(self, secret_key: str):
        """
        Initialize request signer.

        Args:
            secret_key: Shared secret key for HMAC signing
        """
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key
        logger.info("🔐 [REQUEST_SIGNER] Initialized with secret key")

    def sign_request(self, payload: Dict[str, Any]) -> str:
        """
        Generate HMAC signature for JSON payload.

        Args:
            payload: Request body as dictionary

        Returns:
            Hex-encoded HMAC signature
        """
        # Convert to JSON string (deterministic ordering)
        json_payload = json.dumps(payload, sort_keys=True).encode()

        signature = hmac.new(
            self.secret_key,
            json_payload,
            hashlib.sha256
        ).hexdigest()

        logger.debug("🔐 [REQUEST_SIGNER] Generated signature for payload")
        return signature
