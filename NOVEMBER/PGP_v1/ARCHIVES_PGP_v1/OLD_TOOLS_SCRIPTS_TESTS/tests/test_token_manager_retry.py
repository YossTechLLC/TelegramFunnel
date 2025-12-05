#!/usr/bin/env python3
"""
Test script for token_manager.py retry tracking features.
Verifies encryption/decryption of retry tokens with attempt_count tracking.
"""
from token_manager import TokenManager
import time


def test_first_attempt_token():
    """Test encrypting and decrypting a first-attempt token (from PGP_HOSTPAY1_v1)."""
    print("=" * 60)
    print("TEST 1: First Attempt Token (PGP_HOSTPAY1_v1 → PGP_HOSTPAY3_v1)")
    print("=" * 60)

    # Initialize token manager
    token_mgr = TokenManager(
        tps_hostpay_signing_key="test_tps_key_12345",
        internal_signing_key="test_internal_key_67890"
    )

    # Encrypt first attempt token
    token = token_mgr.encrypt_gchostpay1_to_gchostpay3_token(
        unique_id="TEST123456789012",
        cn_api_id="cn_test_12345",
        from_currency="eth",
        from_network="eth",
        from_amount=0.001234,
        payin_address="0x1234567890abcdef",
        context="instant"
        # Note: attempt_count defaults to 1, first_attempt_at defaults to now
    )

    print(f"\n✅ Token encrypted: {token[:50]}...")

    # Decrypt token
    decrypted = token_mgr.decrypt_gchostpay1_to_gchostpay3_token(token)

    print(f"\n📋 Decrypted token:")
    print(f"  - unique_id: {decrypted['unique_id']}")
    print(f"  - cn_api_id: {decrypted['cn_api_id']}")
    print(f"  - from_currency: {decrypted['from_currency']}")
    print(f"  - from_amount: {decrypted['from_amount']}")
    print(f"  - payin_address: {decrypted['payin_address']}")
    print(f"  - context: {decrypted['context']}")
    print(f"  - attempt_count: {decrypted['attempt_count']}")
    print(f"  - first_attempt_at: {decrypted['first_attempt_at']}")
    print(f"  - last_error_code: {decrypted['last_error_code']}")

    # Verify defaults
    assert decrypted['attempt_count'] == 1, f"Expected attempt_count=1, got {decrypted['attempt_count']}"
    assert decrypted['last_error_code'] is None, f"Expected last_error_code=None, got {decrypted['last_error_code']}"
    assert decrypted['first_attempt_at'] is not None, "first_attempt_at should not be None"

    print("\n✅ TEST 1 PASSED")
    return token_mgr, decrypted


def test_retry_token():
    """Test creating a retry token after first failure."""
    print("\n" + "=" * 60)
    print("TEST 2: Retry Token (PGP_HOSTPAY3_v1 → PGP_HOSTPAY3_v1)")
    print("=" * 60)

    token_mgr, first_token_data = test_first_attempt_token()

    # Simulate failure and create retry token
    retry_token = token_mgr.encrypt_gchostpay3_retry_token(
        token_data=first_token_data,
        error_code="RATE_LIMIT_EXCEEDED"
    )

    print(f"\n✅ Retry token encrypted: {retry_token[:50]}...")

    # Decrypt retry token
    retry_decrypted = token_mgr.decrypt_gchostpay1_to_gchostpay3_token(retry_token)

    print(f"\n📋 Decrypted retry token:")
    print(f"  - unique_id: {retry_decrypted['unique_id']}")
    print(f"  - attempt_count: {retry_decrypted['attempt_count']}")
    print(f"  - first_attempt_at: {retry_decrypted['first_attempt_at']}")
    print(f"  - last_error_code: {retry_decrypted['last_error_code']}")

    # Verify retry fields
    assert retry_decrypted['attempt_count'] == 2, f"Expected attempt_count=2, got {retry_decrypted['attempt_count']}"
    assert retry_decrypted['last_error_code'] == "RATE_LIMIT_EXCEEDED", f"Expected last_error_code='RATE_LIMIT_EXCEEDED', got {retry_decrypted['last_error_code']}"
    assert retry_decrypted['first_attempt_at'] == first_token_data['first_attempt_at'], "first_attempt_at should remain unchanged"

    print("\n✅ TEST 2 PASSED")
    return token_mgr, retry_decrypted


def test_third_attempt_token():
    """Test creating third (final) attempt token."""
    print("\n" + "=" * 60)
    print("TEST 3: Third Attempt Token (Final Retry)")
    print("=" * 60)

    token_mgr, second_token_data = test_retry_token()

    # Create third attempt token
    third_token = token_mgr.encrypt_gchostpay3_retry_token(
        token_data=second_token_data,
        error_code="NETWORK_TIMEOUT"
    )

    print(f"\n✅ Third attempt token encrypted: {third_token[:50]}...")

    # Decrypt third attempt token
    third_decrypted = token_mgr.decrypt_gchostpay1_to_gchostpay3_token(third_token)

    print(f"\n📋 Decrypted third attempt token:")
    print(f"  - attempt_count: {third_decrypted['attempt_count']}")
    print(f"  - last_error_code: {third_decrypted['last_error_code']}")

    # Verify third attempt fields
    assert third_decrypted['attempt_count'] == 3, f"Expected attempt_count=3, got {third_decrypted['attempt_count']}"
    assert third_decrypted['last_error_code'] == "NETWORK_TIMEOUT", f"Expected last_error_code='NETWORK_TIMEOUT', got {third_decrypted['last_error_code']}"

    print("\n✅ TEST 3 PASSED")
    print("\n⚠️ NOTE: After attempt 3, payment should be stored in failed_transactions (not retried)")


def test_backward_compatibility():
    """Test that old tokens without retry fields still work."""
    print("\n" + "=" * 60)
    print("TEST 4: Backward Compatibility (Legacy Token)")
    print("=" * 60)

    token_mgr = TokenManager(
        tps_hostpay_signing_key="test_tps_key_12345",
        internal_signing_key="test_internal_key_67890"
    )

    # Create a legacy token by manually building it (simulating old version)
    # We'll use the internal method but exclude retry fields
    import struct
    import base64
    import hmac
    import hashlib

    unique_id_bytes = "LEGACY123456789".encode('utf-8')[:16].ljust(16, b'\x00')

    packed_data = bytearray()
    packed_data.extend(unique_id_bytes)
    packed_data.extend(token_mgr._pack_string("cn_legacy_123"))
    packed_data.extend(token_mgr._pack_string("eth"))
    packed_data.extend(token_mgr._pack_string("eth"))
    packed_data.extend(struct.pack(">d", 0.005678))
    packed_data.extend(token_mgr._pack_string("0xlegacy_address"))
    packed_data.extend(token_mgr._pack_string("instant"))
    # STOP HERE - no retry fields (legacy token)

    current_timestamp = int(time.time())
    packed_data.extend(struct.pack(">I", current_timestamp))

    # Sign with internal key
    full_signature = hmac.new(
        token_mgr.internal_key.encode(),
        bytes(packed_data),
        hashlib.sha256
    ).digest()
    truncated_signature = full_signature[:16]

    final_data = bytes(packed_data) + truncated_signature
    legacy_token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

    print(f"\n✅ Legacy token created: {legacy_token[:50]}...")

    # Decrypt legacy token
    legacy_decrypted = token_mgr.decrypt_gchostpay1_to_gchostpay3_token(legacy_token)

    print(f"\n📋 Decrypted legacy token:")
    print(f"  - unique_id: {legacy_decrypted['unique_id']}")
    print(f"  - attempt_count: {legacy_decrypted['attempt_count']}")
    print(f"  - first_attempt_at: {legacy_decrypted['first_attempt_at']}")
    print(f"  - last_error_code: {legacy_decrypted['last_error_code']}")

    # Verify backward compatibility defaults
    assert legacy_decrypted['attempt_count'] == 1, f"Legacy token should default to attempt_count=1"
    assert legacy_decrypted['last_error_code'] is None, f"Legacy token should default to last_error_code=None"
    assert legacy_decrypted['first_attempt_at'] is not None, "Legacy token should get current time for first_attempt_at"

    print("\n✅ TEST 4 PASSED - Backward compatibility working!")


def test_all_fields_preserved():
    """Test that all payment fields are preserved through retry cycles."""
    print("\n" + "=" * 60)
    print("TEST 5: Field Preservation Through Retry Cycles")
    print("=" * 60)

    token_mgr = TokenManager(
        tps_hostpay_signing_key="test_tps_key_12345",
        internal_signing_key="test_internal_key_67890"
    )

    # Create first token
    original_token = token_mgr.encrypt_gchostpay1_to_gchostpay3_token(
        unique_id="PRESERVE12345678",
        cn_api_id="cn_preserve_999",
        from_currency="eth",
        from_network="eth",
        from_amount=0.987654,
        payin_address="0xpreserve_address",
        context="threshold"  # Test non-default context
    )

    decrypted_1 = token_mgr.decrypt_gchostpay1_to_gchostpay3_token(original_token)

    # Create retry token
    retry_token = token_mgr.encrypt_gchostpay3_retry_token(decrypted_1, "INSUFFICIENT_FUNDS")
    decrypted_2 = token_mgr.decrypt_gchostpay1_to_gchostpay3_token(retry_token)

    # Verify all original fields preserved
    fields_to_check = ['unique_id', 'cn_api_id', 'from_currency', 'from_network', 'from_amount', 'payin_address', 'context']
    for field in fields_to_check:
        assert decrypted_1[field] == decrypted_2[field], f"Field '{field}' not preserved through retry!"
        print(f"  ✅ {field}: {decrypted_2[field]}")

    print("\n✅ TEST 5 PASSED - All fields preserved!")


if __name__ == "__main__":
    print("\n🚀 Starting Token Manager Retry Feature Tests\n")

    try:
        test_first_attempt_token()
        test_retry_token()
        test_third_attempt_token()
        test_backward_compatibility()
        test_all_fields_preserved()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        raise
