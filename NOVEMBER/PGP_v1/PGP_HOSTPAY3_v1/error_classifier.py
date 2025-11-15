#!/usr/bin/env python
"""
Error Classification Module for PGP_HOSTPAY3_v1.
Classifies ETH payment exceptions into actionable error codes for targeted resolution.
"""
from typing import Tuple
import re


class ErrorClassifier:
    """
    Classifies payment execution exceptions into error codes.
    Returns error code and retryability flag for automated retry decision-making.
    """

    # Critical Errors - Permanent failures that cannot be automatically retried
    CRITICAL_ERRORS = {
        'INSUFFICIENT_FUNDS': {
            'description': 'Host wallet has insufficient ETH for payment + gas fees',
            'patterns': [
                r'insufficient funds',
                r'insufficient.*balance',
                r'exceeds balance',
                r'not enough.*funds',
                r"doesn't have enough",
                r"doesn't have.*funds"
            ],
            'retryable': False
        },
        'INVALID_ADDRESS': {
            'description': 'Payin address is malformed or invalid',
            'patterns': [
                r'invalid.*address',
                r'bad.*address',
                r'malformed.*address',
                r'checksum.*failed'
            ],
            'retryable': False
        },
        'INVALID_AMOUNT': {
            'description': 'Payment amount is invalid (zero, negative, or too large)',
            'patterns': [
                r'invalid.*amount',
                r'amount.*invalid',
                r'negative.*amount',
                r'amount.*negative',
                r'amount is negative',
                r'zero.*amount'
            ],
            'retryable': False
        },
        'TRANSACTION_REVERTED_PERMANENT': {
            'description': 'Transaction reverted on-chain (non-gas related)',
            'patterns': [
                r'transaction.*reverted',
                r'reverted.*permanent',
                r'execution.*reverted'
            ],
            'retryable': False
        }
    }

    # Transient Errors - Temporary failures that can be automatically retried
    TRANSIENT_ERRORS = {
        'CONFIRMATION_TIMEOUT': {
            'description': 'Transaction not confirmed within 300s (mempool congestion)',
            'patterns': [
                r'confirmation.*timeout',
                r'not.*confirmed',
                r'pending.*too.*long'
            ],
            'retryable': True
        },
        'NETWORK_TIMEOUT': {
            'description': 'RPC connection timeout (Alchemy API slow/unavailable)',
            'patterns': [
                r'timeout',
                r'timed.*out',
                r'connection.*timeout',
                r'read.*timeout'
            ],
            'retryable': True
        },
        'RATE_LIMIT_EXCEEDED': {
            'description': 'Alchemy 429 rate limit hit (too many requests)',
            'patterns': [
                r'429',
                r'too many requests',
                r'rate.*limit',
                r'quota.*exceeded'
            ],
            'retryable': True
        },
        'NONCE_CONFLICT': {
            'description': 'Nonce already used or too low (race condition)',
            'patterns': [
                r'nonce.*too low',
                r'nonce.*already',
                r'replacement.*underpriced'
            ],
            'retryable': True
        },
        'GAS_PRICE_SPIKE': {
            'description': 'Gas price exceeds safety threshold (network congestion)',
            'patterns': [
                r'gas.*price.*high',
                r'max.*fee.*exceeded',
                r'gas.*too.*expensive'
            ],
            'retryable': True
        }
    }

    # Configuration Errors - System issues requiring admin intervention
    CONFIG_ERRORS = {
        'RPC_CONNECTION_FAILED': {
            'description': 'Cannot connect to Ethereum RPC (Alchemy API down)',
            'patterns': [
                r'connection.*failed',
                r'failed.*to.*connect',
                r'rpc.*error',
                r'connection.*refused'
            ],
            'retryable': False
        },
        'WALLET_UNLOCKED_FAILED': {
            'description': 'Cannot access wallet private key (Secret Manager error)',
            'patterns': [
                r'wallet.*unlock',
                r'private.*key.*failed',
                r'secret.*manager.*error'
            ],
            'retryable': False
        },
        'WEB3_INITIALIZATION_FAILED': {
            'description': 'Web3 provider initialization failed (library/network issue)',
            'patterns': [
                r'web3.*init',
                r'provider.*init',
                r'initialization.*failed'
            ],
            'retryable': False
        }
    }

    # Unknown Errors - Catch-all for unexpected exceptions
    UNKNOWN_ERROR = {
        'code': 'UNKNOWN_ERROR',
        'description': 'Unexpected exception (unhandled edge case)',
        'retryable': False
    }

    @classmethod
    def classify_error(cls, exception: Exception) -> Tuple[str, bool]:
        """
        Classify an exception into an error code and determine retryability.

        Args:
            exception: The exception raised during ETH payment execution

        Returns:
            Tuple of (error_code: str, is_retryable: bool)

        Example:
            >>> e = ValueError("insufficient funds for gas * price + value")
            >>> code, retryable = ErrorClassifier.classify_error(e)
            >>> print(code, retryable)
            'INSUFFICIENT_FUNDS' False
        """
        error_message = str(exception).lower()

        print(f"🔍 [ERROR_CLASSIFIER] Classifying error: {error_message[:100]}")

        # Check Critical Errors first (highest priority)
        for error_code, error_info in cls.CRITICAL_ERRORS.items():
            for pattern in error_info['patterns']:
                if re.search(pattern, error_message, re.IGNORECASE):
                    print(f"✅ [ERROR_CLASSIFIER] Matched: {error_code} (Critical)")
                    print(f"📝 [ERROR_CLASSIFIER] Description: {error_info['description']}")
                    print(f"🔄 [ERROR_CLASSIFIER] Retryable: {error_info['retryable']}")
                    return error_code, error_info['retryable']

        # Check Transient Errors (medium priority)
        for error_code, error_info in cls.TRANSIENT_ERRORS.items():
            for pattern in error_info['patterns']:
                if re.search(pattern, error_message, re.IGNORECASE):
                    print(f"✅ [ERROR_CLASSIFIER] Matched: {error_code} (Transient)")
                    print(f"📝 [ERROR_CLASSIFIER] Description: {error_info['description']}")
                    print(f"🔄 [ERROR_CLASSIFIER] Retryable: {error_info['retryable']}")
                    return error_code, error_info['retryable']

        # Check Configuration Errors (low priority)
        for error_code, error_info in cls.CONFIG_ERRORS.items():
            for pattern in error_info['patterns']:
                if re.search(pattern, error_message, re.IGNORECASE):
                    print(f"✅ [ERROR_CLASSIFIER] Matched: {error_code} (Config)")
                    print(f"📝 [ERROR_CLASSIFIER] Description: {error_info['description']}")
                    print(f"🔄 [ERROR_CLASSIFIER] Retryable: {error_info['retryable']}")
                    return error_code, error_info['retryable']

        # Default to Unknown Error
        print(f"⚠️ [ERROR_CLASSIFIER] No pattern match found - classifying as UNKNOWN_ERROR")
        print(f"📝 [ERROR_CLASSIFIER] Description: {cls.UNKNOWN_ERROR['description']}")
        print(f"🔄 [ERROR_CLASSIFIER] Retryable: {cls.UNKNOWN_ERROR['retryable']}")
        return cls.UNKNOWN_ERROR['code'], cls.UNKNOWN_ERROR['retryable']

    @classmethod
    def get_error_description(cls, error_code: str) -> str:
        """
        Get human-readable description for an error code.

        Args:
            error_code: The error code to describe

        Returns:
            Description string or "Unknown error code" if not found

        Example:
            >>> desc = ErrorClassifier.get_error_description('INSUFFICIENT_FUNDS')
            >>> print(desc)
            'Host wallet has insufficient ETH for payment + gas fees'
        """
        # Search in all error dictionaries
        for error_dict in [cls.CRITICAL_ERRORS, cls.TRANSIENT_ERRORS, cls.CONFIG_ERRORS]:
            if error_code in error_dict:
                return error_dict[error_code]['description']

        # Check unknown error
        if error_code == cls.UNKNOWN_ERROR['code']:
            return cls.UNKNOWN_ERROR['description']

        return f"Unknown error code: {error_code}"

    @classmethod
    def is_retryable(cls, error_code: str) -> bool:
        """
        Check if an error code is retryable.

        Args:
            error_code: The error code to check

        Returns:
            True if error is retryable, False otherwise

        Example:
            >>> ErrorClassifier.is_retryable('RATE_LIMIT_EXCEEDED')
            True
            >>> ErrorClassifier.is_retryable('INSUFFICIENT_FUNDS')
            False
        """
        # Search in all error dictionaries
        for error_dict in [cls.CRITICAL_ERRORS, cls.TRANSIENT_ERRORS, cls.CONFIG_ERRORS]:
            if error_code in error_dict:
                return error_dict[error_code]['retryable']

        # Unknown errors are not retryable by default
        return False
