#!/usr/bin/env python
"""
Webhook signature verification utilities for PGP_v1 Services.
Provides HMAC-based signature verification for incoming webhook requests.
"""
import hmac
import hashlib
from typing import Optional


def verify_hmac_hex_signature(
    payload: bytes,
    signature: str,
    secret: str,
    algorithm: str = 'sha256'
) -> bool:
    """
    Verify HMAC signature for webhook requests (hex-encoded).

    This is a common pattern for webhook signature verification where:
    1. Provider calculates HMAC of request body using shared secret
    2. Provider sends signature as hex string in header
    3. Receiver verifies by recalculating and comparing signatures

    Used by:
    - PGP_SPLIT1_v1: Verify webhook callbacks (HMAC-SHA256)
    - PGP_NP_IPN_v1: Verify NowPayments IPN callbacks (HMAC-SHA512)

    Args:
        payload: Raw request body bytes (exactly as received)
        signature: Hex-encoded signature from webhook header
        secret: Shared secret key for HMAC calculation
        algorithm: Hash algorithm ('sha256', 'sha512', etc.)

    Returns:
        True if signature is valid, False otherwise

    Security:
    - Uses timing-safe comparison (hmac.compare_digest)
    - Supports multiple hash algorithms
    - Returns False on any error (fail-secure)

    Example:
        >>> payload = b'{"order_id": "PGP-123", "status": "finished"}'
        >>> signature = "abc123..."  # From X-Signature header
        >>> secret = "my_webhook_secret"
        >>> is_valid = verify_hmac_hex_signature(payload, signature, secret)
        >>> if is_valid:
        ...     process_webhook(payload)
    """
    if not secret or not signature:
        return False

    try:
        # Select hash algorithm
        if algorithm == 'sha256':
            hash_func = hashlib.sha256
        elif algorithm == 'sha512':
            hash_func = hashlib.sha512
        elif algorithm == 'sha1':
            hash_func = hashlib.sha1
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hash_func
        ).hexdigest()

        # Timing-safe comparison
        return hmac.compare_digest(signature, expected_signature)

    except Exception as e:
        print(f"❌ [WEBHOOK_AUTH] Signature verification error: {e}")
        return False


def verify_sha256_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify HMAC-SHA256 signature (convenience wrapper).

    Args:
        payload: Raw request body bytes
        signature: Hex-encoded HMAC-SHA256 signature
        secret: Shared secret key

    Returns:
        True if signature is valid, False otherwise

    Example:
        >>> verify_sha256_signature(b'{"data": "value"}', "abc123...", "secret")
        True
    """
    return verify_hmac_hex_signature(payload, signature, secret, algorithm='sha256')


def verify_sha512_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify HMAC-SHA512 signature (convenience wrapper).

    Commonly used by payment providers like NowPayments.

    Args:
        payload: Raw request body bytes
        signature: Hex-encoded HMAC-SHA512 signature
        secret: Shared secret key

    Returns:
        True if signature is valid, False otherwise

    Example:
        >>> # NowPayments IPN verification
        >>> verify_sha512_signature(ipn_payload, nowpayments_sig, ipn_secret)
        True
    """
    return verify_hmac_hex_signature(payload, signature, secret, algorithm='sha512')
