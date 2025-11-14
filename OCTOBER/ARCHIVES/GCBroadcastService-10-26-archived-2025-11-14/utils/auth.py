#!/usr/bin/env python3
"""
Authentication Utilities
JWT authentication helpers for GCBroadcastService
"""

import logging
from flask_jwt_extended import get_jwt_identity

logger = logging.getLogger(__name__)


def extract_client_id() -> str:
    """
    Extract client_id from JWT token.

    Returns:
        str: User ID from JWT 'sub' claim
        None: If token is invalid or missing
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
