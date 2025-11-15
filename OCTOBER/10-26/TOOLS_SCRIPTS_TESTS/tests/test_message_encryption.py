#!/usr/bin/env python3
"""
Unit tests for message encryption utility
"""
import sys
sys.path.append('/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26')

from shared_utils.message_encryption import encrypt_donation_message, decrypt_donation_message


def test_basic_encryption_decryption():
    """Test basic encryption and decryption"""
    original = "Thank you for the amazing content! Keep up the great work!"

    print(f"🧪 Testing encryption/decryption")
    print(f"   Original: {original} ({len(original)} chars)")

    # Encrypt
    encrypted = encrypt_donation_message(original)
    print(f"   Encrypted: {encrypted} ({len(encrypted)} chars)")

    # Decrypt
    decrypted = decrypt_donation_message(encrypted)
    print(f"   Decrypted: {decrypted} ({len(decrypted)} chars)")

    # Verify
    assert original == decrypted, "Decrypted message doesn't match original!"
    print(f"✅ Test passed: Encryption/decryption successful")


def test_max_length_message():
    """Test 256 character message"""
    original = "A" * 256

    print(f"\n🧪 Testing max length (256 chars)")
    print(f"   Original length: {len(original)}")

    encrypted = encrypt_donation_message(original)
    print(f"   Encrypted length: {len(encrypted)} chars")

    decrypted = decrypt_donation_message(encrypted)
    assert original == decrypted
    print(f"✅ Test passed: Max length message handled correctly")


def test_empty_message():
    """Test empty message"""
    print(f"\n🧪 Testing empty message")

    encrypted = encrypt_donation_message("")
    print(f"   Encrypted: '{encrypted}'")
    assert encrypted == ""

    decrypted = decrypt_donation_message("")
    print(f"   Decrypted: '{decrypted}'")
    assert decrypted == ""
    print(f"✅ Test passed: Empty message handled correctly")


def test_special_characters():
    """Test message with emojis and special characters"""
    original = "Thanks! 💝🎉 Here's $50 for you & your team! 你好 🌟"

    print(f"\n🧪 Testing special characters and emojis")
    print(f"   Original: {original}")

    encrypted = encrypt_donation_message(original)
    decrypted = decrypt_donation_message(encrypted)

    assert original == decrypted
    print(f"✅ Test passed: Special characters preserved")


def test_compression_ratio():
    """Test compression effectiveness"""
    original = "Thank you " * 20  # Repetitive text compresses well

    print(f"\n🧪 Testing compression ratio")
    print(f"   Original: {len(original)} chars")

    encrypted = encrypt_donation_message(original)
    print(f"   Encrypted: {len(encrypted)} chars")

    ratio = len(original) / len(encrypted)
    print(f"   Compression ratio: {ratio:.2f}x")

    decrypted = decrypt_donation_message(encrypted)
    assert original == decrypted
    print(f"✅ Test passed: Compression working effectively")


def test_message_too_long():
    """Test that messages >256 chars are rejected"""
    original = "A" * 257

    print(f"\n🧪 Testing message too long (257 chars)")
    print(f"   Original length: {len(original)}")

    try:
        encrypted = encrypt_donation_message(original)
        print(f"❌ Test failed: Should have raised ValueError")
        assert False, "Should have raised ValueError for message >256 chars"
    except ValueError as e:
        print(f"   Error: {e}")
        print(f"✅ Test passed: Correctly rejected message >256 chars")


if __name__ == "__main__":
    print("=" * 60)
    print("MESSAGE ENCRYPTION UNIT TESTS")
    print("=" * 60)

    test_basic_encryption_decryption()
    test_max_length_message()
    test_empty_message()
    test_special_characters()
    test_compression_ratio()
    test_message_too_long()

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)
