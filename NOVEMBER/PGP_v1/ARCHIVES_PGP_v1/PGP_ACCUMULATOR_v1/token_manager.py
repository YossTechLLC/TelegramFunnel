#!/usr/bin/env python
"""
Token Manager for PGP_ACCUMULATOR_v1 (Payment Accumulation Service).

NOTE: Architecture changed - PGP_ACCUMULATOR is now passive storage only.
All token encryption/decryption for downstream services (SPLIT/HOSTPAY) removed.
Orchestration handled by PGP_MICROBATCHPROCESSOR_v1.
"""
from PGP_COMMON.tokens import BaseTokenManager


class TokenManager(BaseTokenManager):
    """
    Manages token operations for PGP_ACCUMULATOR_v1.
    Inherits common methods from BaseTokenManager.

    NOTE: This service no longer encrypts/decrypts tokens for downstream services.
    It only stores accumulation data. Kept for future use if needed.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: SUCCESS_URL_SIGNING_KEY for token operations
        """
        super().__init__(signing_key=signing_key, service_name="PGP_ACCUMULATOR_v1")

    # All downstream token methods removed (encrypt_token_for_pgp_split2,
    # encrypt/decrypt_accumulator_to_pgp_split3, encrypt/decrypt_accumulator_to_pgp_hostpay1, etc.)
    # Architecture changed to micro-batch processing model - ACCUMULATOR is passive storage only.
