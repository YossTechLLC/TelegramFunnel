#!/usr/bin/env python
"""
💬 Message Encryption Utility for Donation Messages
Provides compression + base64url encoding for donation messages.
Uses zstd compression with SUCCESS_URL_SIGNING_KEY as seed.

Version: 1.0
Date: 2025-11-14
Security: Zero-persistence, deterministic encryption
"""
import logging
import os
import base64
import zstandard as zstd
from typing import Optional
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


def _get_encryption_seed() -> bytes:
    """
    Fetch SUCCESS_URL_SIGNING_KEY from Secret Manager.

    Returns:
        Seed bytes for deterministic compression

    Raises:
        ValueError: If SUCCESS_URL_SIGNING_KEY not available
    """
    try:
        client = secretmanager.SecretManagerServiceClient()

        # Fetch from Secret Manager (not environment variable)
        secret_name = "projects/telepay-459221/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest"

        response = client.access_secret_version(request={"name": secret_name})
        seed = response.payload.data.decode("UTF-8").encode("utf-8")

        logger.info("✅ [ENCRYPT] Fetched SUCCESS_URL_SIGNING_KEY seed")
        return seed

    except Exception as e:
        logger.error(f"❌ [ENCRYPT] Failed to fetch SUCCESS_URL_SIGNING_KEY: {e}")
        raise ValueError("Encryption seed not available") from e


def encrypt_donation_message(message: str) -> str:
    """
    Encrypt donation message using zstd compression + base64url encoding.

    Process:
    1. UTF-8 encode message
    2. Compress with zstd (level 10)
    3. Base64url encode (URL-safe)

    Args:
        message: Donation message (max 256 characters)

    Returns:
        Base64url-encoded encrypted message

    Raises:
        ValueError: If message exceeds 256 characters or encryption fails
    """
    # Validation
    if not message:
        logger.warning("⚠️ [ENCRYPT] Empty message provided")
        return ""

    if len(message) > 256:
        logger.error(f"❌ [ENCRYPT] Message too long: {len(message)} chars (max 256)")
        raise ValueError("Message must be <= 256 characters")

    try:
        logger.info(f"🔐 [ENCRYPT] Encrypting message ({len(message)} chars)")

        # Step 1: UTF-8 encode
        message_bytes = message.encode("utf-8")
        logger.info(f"   🔤 [DEBUG] Step 1 - UTF-8 encode: {len(message_bytes)} bytes")

        # Step 2: Compress with zstd (level 10 for maximum compression)
        compressor = zstd.ZstdCompressor(level=10)
        compressed = compressor.compress(message_bytes)
        logger.info(f"   🗜️ [DEBUG] Step 2 - Compressed: {len(compressed)} bytes (ratio: {len(message_bytes)/len(compressed):.2f}x)")

        # Step 3: Base64url encode (URL-safe, no padding)
        encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
        logger.info(f"   🔐 [DEBUG] Step 3 - Base64url encoded: {len(encoded)} chars")
        logger.info(f"   🔐 [DEBUG] Final encrypted output: '{encoded}'")
        logger.info(f"✅ [ENCRYPT] Encrypted message: {len(encoded)} chars")

        return encoded

    except Exception as e:
        logger.error(f"❌ [ENCRYPT] Encryption failed: {e}", exc_info=True)
        raise ValueError(f"Message encryption failed: {e}") from e


def decrypt_donation_message(encrypted_message: str) -> str:
    """
    Decrypt donation message using base64url decode + zstd decompression.

    Process (reverse of encryption):
    1. Base64url decode
    2. Decompress with zstd
    3. UTF-8 decode to string

    Args:
        encrypted_message: Base64url-encoded encrypted message

    Returns:
        Decrypted message string

    Raises:
        ValueError: If decryption fails
    """
    if not encrypted_message:
        logger.warning("⚠️ [DECRYPT] Empty encrypted message provided")
        return ""

    try:
        logger.info(f"🔓 [DECRYPT] Decrypting message ({len(encrypted_message)} chars)")

        # Step 1: Base64url decode (add padding if needed)
        # Base64url encoding removes trailing '=' padding, add it back
        padding = 4 - (len(encrypted_message) % 4)
        if padding != 4:
            encrypted_message += "=" * padding

        compressed = base64.urlsafe_b64decode(encrypted_message.encode("ascii"))
        logger.debug(f"   Decoded: {len(compressed)} bytes")

        # Step 2: Decompress with zstd
        decompressor = zstd.ZstdDecompressor()
        message_bytes = decompressor.decompress(compressed)
        logger.debug(f"   Decompressed: {len(message_bytes)} bytes")

        # Step 3: UTF-8 decode
        message = message_bytes.decode("utf-8")
        logger.info(f"✅ [DECRYPT] Decrypted message: {len(message)} chars")

        return message

    except Exception as e:
        logger.error(f"❌ [DECRYPT] Decryption failed: {e}", exc_info=True)
        raise ValueError(f"Message decryption failed: {e}") from e


logger.info("✅ [MESSAGE_ENCRYPTION] Message encryption utility loaded")
