#!/usr/bin/env python3
"""
Test script for error_classifier.py
Verifies error classification patterns and retryability logic.
"""
from error_classifier import ErrorClassifier


def test_critical_errors():
    """Test critical error classification."""
    print("=" * 60)
    print("TESTING CRITICAL ERRORS (Non-Retryable)")
    print("=" * 60)

    test_cases = [
        (ValueError("insufficient funds for gas * price + value"), "INSUFFICIENT_FUNDS", False),
        (ValueError("sender doesn't have enough funds"), "INSUFFICIENT_FUNDS", False),
        (ValueError("invalid address checksum"), "INVALID_ADDRESS", False),
        (ValueError("malformed address format"), "INVALID_ADDRESS", False),
        (ValueError("invalid amount: zero"), "INVALID_AMOUNT", False),
        (ValueError("amount is negative"), "INVALID_AMOUNT", False),
        (ValueError("transaction reverted during execution"), "TRANSACTION_REVERTED_PERMANENT", False),
    ]

    for exception, expected_code, expected_retryable in test_cases:
        code, retryable = ErrorClassifier.classify_error(exception)
        status = "✅ PASS" if code == expected_code and retryable == expected_retryable else "❌ FAIL"
        print(f"\n{status}")
        print(f"  Exception: {str(exception)}")
        print(f"  Expected: {expected_code}, retryable={expected_retryable}")
        print(f"  Got: {code}, retryable={retryable}")


def test_transient_errors():
    """Test transient error classification."""
    print("\n" + "=" * 60)
    print("TESTING TRANSIENT ERRORS (Retryable)")
    print("=" * 60)

    test_cases = [
        (TimeoutError("connection timeout"), "NETWORK_TIMEOUT", True),
        (Exception("request timed out after 30s"), "NETWORK_TIMEOUT", True),
        (Exception("429 Too Many Requests"), "RATE_LIMIT_EXCEEDED", True),
        (Exception("rate limit exceeded"), "RATE_LIMIT_EXCEEDED", True),
        (ValueError("nonce too low"), "NONCE_CONFLICT", True),
        (ValueError("replacement transaction underpriced"), "NONCE_CONFLICT", True),
        (ValueError("gas price is too high"), "GAS_PRICE_SPIKE", True),
        (TimeoutError("confirmation timeout exceeded"), "CONFIRMATION_TIMEOUT", True),
    ]

    for exception, expected_code, expected_retryable in test_cases:
        code, retryable = ErrorClassifier.classify_error(exception)
        status = "✅ PASS" if code == expected_code and retryable == expected_retryable else "❌ FAIL"
        print(f"\n{status}")
        print(f"  Exception: {str(exception)}")
        print(f"  Expected: {expected_code}, retryable={expected_retryable}")
        print(f"  Got: {code}, retryable={retryable}")


def test_config_errors():
    """Test configuration error classification."""
    print("\n" + "=" * 60)
    print("TESTING CONFIGURATION ERRORS (Non-Retryable)")
    print("=" * 60)

    test_cases = [
        (ConnectionError("connection refused by RPC endpoint"), "RPC_CONNECTION_FAILED", False),
        (ConnectionError("failed to connect to Alchemy"), "RPC_CONNECTION_FAILED", False),
        (ValueError("wallet unlock failed"), "WALLET_UNLOCKED_FAILED", False),
        (ValueError("private key access failed"), "WALLET_UNLOCKED_FAILED", False),
        (RuntimeError("web3 initialization failed"), "WEB3_INITIALIZATION_FAILED", False),
    ]

    for exception, expected_code, expected_retryable in test_cases:
        code, retryable = ErrorClassifier.classify_error(exception)
        status = "✅ PASS" if code == expected_code and retryable == expected_retryable else "❌ FAIL"
        print(f"\n{status}")
        print(f"  Exception: {str(exception)}")
        print(f"  Expected: {expected_code}, retryable={expected_retryable}")
        print(f"  Got: {code}, retryable={retryable}")


def test_unknown_errors():
    """Test unknown error classification."""
    print("\n" + "=" * 60)
    print("TESTING UNKNOWN ERRORS (Non-Retryable)")
    print("=" * 60)

    test_cases = [
        (Exception("Something completely unexpected happened"), "UNKNOWN_ERROR", False),
        (RuntimeError("Unhandled edge case"), "UNKNOWN_ERROR", False),
        (ValueError("This error doesn't match any pattern"), "UNKNOWN_ERROR", False),
    ]

    for exception, expected_code, expected_retryable in test_cases:
        code, retryable = ErrorClassifier.classify_error(exception)
        status = "✅ PASS" if code == expected_code and retryable == expected_retryable else "❌ FAIL"
        print(f"\n{status}")
        print(f"  Exception: {str(exception)}")
        print(f"  Expected: {expected_code}, retryable={expected_retryable}")
        print(f"  Got: {code}, retryable={retryable}")


def test_error_descriptions():
    """Test error description retrieval."""
    print("\n" + "=" * 60)
    print("TESTING ERROR DESCRIPTIONS")
    print("=" * 60)

    error_codes = [
        "INSUFFICIENT_FUNDS",
        "RATE_LIMIT_EXCEEDED",
        "RPC_CONNECTION_FAILED",
        "UNKNOWN_ERROR",
        "NONEXISTENT_CODE"
    ]

    for code in error_codes:
        description = ErrorClassifier.get_error_description(code)
        print(f"\n{code}:")
        print(f"  {description}")


def test_retryability_check():
    """Test retryability check method."""
    print("\n" + "=" * 60)
    print("TESTING RETRYABILITY CHECK")
    print("=" * 60)

    test_cases = [
        ("INSUFFICIENT_FUNDS", False),
        ("RATE_LIMIT_EXCEEDED", True),
        ("NETWORK_TIMEOUT", True),
        ("INVALID_ADDRESS", False),
        ("UNKNOWN_ERROR", False),
    ]

    for code, expected in test_cases:
        result = ErrorClassifier.is_retryable(code)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"\n{status} {code}: {result} (expected {expected})")


if __name__ == "__main__":
    print("\n🚀 Starting Error Classifier Tests\n")

    test_critical_errors()
    test_transient_errors()
    test_config_errors()
    test_unknown_errors()
    test_error_descriptions()
    test_retryability_check()

    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 60)
