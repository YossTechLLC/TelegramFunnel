#!/usr/bin/env python3
"""
🧪 Unit Tests for TokenService
Tests token generation, validation, and expiration for email verification
and password reset tokens.
"""
import pytest
import os
import time
from datetime import datetime, timedelta
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.services.token_service import TokenService
from itsdangerous import SignatureExpired, BadSignature


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def token_service():
    """Create TokenService instance with test secret"""
    # Set test secret key
    os.environ['SIGNUP_SECRET_KEY'] = 'test-secret-key-for-unit-tests-32-chars-long'
    service = TokenService()
    yield service
    # Cleanup
    if 'SIGNUP_SECRET_KEY' in os.environ:
        del os.environ['SIGNUP_SECRET_KEY']


@pytest.fixture
def test_user_data():
    """Sample user data for testing"""
    return {
        'user_id': '550e8400-e29b-41d4-a716-446655440000',
        'email': 'test@example.com'
    }


# =============================================================================
# Email Verification Token Tests
# =============================================================================

class TestEmailVerificationTokens:
    """Tests for email verification token generation and validation"""

    def test_generate_email_verification_token(self, token_service, test_user_data):
        """Test that email verification tokens are generated correctly"""
        token = token_service.generate_email_verification_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Assertions
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # Tokens should be reasonably long
        print(f"✅ Generated email verification token: {token[:30]}...")

    def test_verify_email_verification_token(self, token_service, test_user_data):
        """Test that email verification tokens can be validated correctly"""
        # Generate token
        token = token_service.generate_email_verification_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Verify token
        data = token_service.verify_email_verification_token(token)

        # Assertions
        assert data is not None
        assert data['user_id'] == test_user_data['user_id']
        assert data['email'] == test_user_data['email']
        print(f"✅ Verified email verification token for user: {data['user_id']}")

    def test_email_verification_token_expiration(self, token_service, test_user_data):
        """Test that expired email verification tokens are rejected"""
        # Temporarily set a short expiration (1 second)
        original_max_age = token_service.EMAIL_VERIFICATION_MAX_AGE
        token_service.EMAIL_VERIFICATION_MAX_AGE = 1

        # Generate token
        token = token_service.generate_email_verification_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Wait for expiration
        time.sleep(2)

        # Try to verify expired token
        with pytest.raises(SignatureExpired):
            token_service.verify_email_verification_token(token)

        print("✅ Expired email verification token correctly rejected")

        # Restore original max age
        token_service.EMAIL_VERIFICATION_MAX_AGE = original_max_age

    def test_tampered_email_verification_token(self, token_service, test_user_data):
        """Test that tampered email verification tokens are rejected"""
        # Generate valid token
        token = token_service.generate_email_verification_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Tamper with token (change last 5 characters)
        tampered_token = token[:-5] + 'XXXXX'

        # Try to verify tampered token
        with pytest.raises(BadSignature):
            token_service.verify_email_verification_token(tampered_token)

        print("✅ Tampered email verification token correctly rejected")

    def test_email_verification_token_uniqueness(self, token_service, test_user_data):
        """Test that each token generation produces a unique token"""
        token1 = token_service.generate_email_verification_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Wait to ensure timestamp difference (1+ second for guaranteed uniqueness)
        time.sleep(1.1)

        token2 = token_service.generate_email_verification_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Tokens should be different due to timestamp
        assert token1 != token2
        print("✅ Each token generation produces unique tokens")


# =============================================================================
# Password Reset Token Tests
# =============================================================================

class TestPasswordResetTokens:
    """Tests for password reset token generation and validation"""

    def test_generate_password_reset_token(self, token_service, test_user_data):
        """Test that password reset tokens are generated correctly"""
        token = token_service.generate_password_reset_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Assertions
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50
        print(f"✅ Generated password reset token: {token[:30]}...")

    def test_verify_password_reset_token(self, token_service, test_user_data):
        """Test that password reset tokens can be validated correctly"""
        # Generate token
        token = token_service.generate_password_reset_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Verify token
        data = token_service.verify_password_reset_token(token)

        # Assertions
        assert data is not None
        assert data['user_id'] == test_user_data['user_id']
        assert data['email'] == test_user_data['email']
        print(f"✅ Verified password reset token for user: {data['user_id']}")

    def test_password_reset_token_expiration(self, token_service, test_user_data):
        """Test that expired password reset tokens are rejected"""
        # Temporarily set a short expiration (1 second)
        original_max_age = token_service.PASSWORD_RESET_MAX_AGE
        token_service.PASSWORD_RESET_MAX_AGE = 1

        # Generate token
        token = token_service.generate_password_reset_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Wait for expiration
        time.sleep(2)

        # Try to verify expired token
        with pytest.raises(SignatureExpired):
            token_service.verify_password_reset_token(token)

        print("✅ Expired password reset token correctly rejected")

        # Restore original max age
        token_service.PASSWORD_RESET_MAX_AGE = original_max_age

    def test_tampered_password_reset_token(self, token_service, test_user_data):
        """Test that tampered password reset tokens are rejected"""
        # Generate valid token
        token = token_service.generate_password_reset_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Tamper with token
        tampered_token = token[:-5] + 'YYYYY'

        # Try to verify tampered token
        with pytest.raises(BadSignature):
            token_service.verify_password_reset_token(tampered_token)

        print("✅ Tampered password reset token correctly rejected")


# =============================================================================
# Token Type Separation Tests
# =============================================================================

class TestTokenTypeSeparation:
    """Tests to ensure different token types cannot be used interchangeably"""

    def test_email_token_cannot_be_used_for_password_reset(self, token_service, test_user_data):
        """Test that email verification tokens cannot be used for password reset"""
        # Generate email verification token
        email_token = token_service.generate_email_verification_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Try to verify as password reset token (should fail)
        with pytest.raises(BadSignature):
            token_service.verify_password_reset_token(email_token)

        print("✅ Email verification token cannot be used for password reset")

    def test_password_reset_token_cannot_be_used_for_email_verification(self, token_service, test_user_data):
        """Test that password reset tokens cannot be used for email verification"""
        # Generate password reset token
        reset_token = token_service.generate_password_reset_token(
            user_id=test_user_data['user_id'],
            email=test_user_data['email']
        )

        # Try to verify as email verification token (should fail)
        with pytest.raises(BadSignature):
            token_service.verify_email_verification_token(reset_token)

        print("✅ Password reset token cannot be used for email verification")


# =============================================================================
# Utility Method Tests
# =============================================================================

class TestUtilityMethods:
    """Tests for utility methods"""

    def test_get_expiration_datetime_email_verification(self):
        """Test expiration datetime for email verification"""
        exp_time = TokenService.get_expiration_datetime('email_verification')

        # Should be approximately 24 hours from now
        expected_time = datetime.utcnow() + timedelta(hours=24)
        time_diff = abs((exp_time - expected_time).total_seconds())

        assert time_diff < 2  # Allow 2 seconds difference
        print(f"✅ Email verification expiration: {exp_time.isoformat()}")

    def test_get_expiration_datetime_password_reset(self):
        """Test expiration datetime for password reset"""
        exp_time = TokenService.get_expiration_datetime('password_reset')

        # Should be approximately 1 hour from now
        expected_time = datetime.utcnow() + timedelta(hours=1)
        time_diff = abs((exp_time - expected_time).total_seconds())

        assert time_diff < 2  # Allow 2 seconds difference
        print(f"✅ Password reset expiration: {exp_time.isoformat()}")

    def test_get_expiration_datetime_invalid_type(self):
        """Test that invalid token type raises ValueError"""
        with pytest.raises(ValueError):
            TokenService.get_expiration_datetime('invalid_type')

        print("✅ Invalid token type correctly raises ValueError")


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error conditions"""

    def test_empty_user_id(self, token_service):
        """Test token generation with empty user_id"""
        token = token_service.generate_email_verification_token(
            user_id='',
            email='test@example.com'
        )

        # Should generate token but may contain empty user_id
        data = token_service.verify_email_verification_token(token)
        assert data['user_id'] == ''
        print("✅ Empty user_id handled correctly")

    def test_empty_email(self, token_service):
        """Test token generation with empty email"""
        token = token_service.generate_email_verification_token(
            user_id='550e8400-e29b-41d4-a716-446655440000',
            email=''
        )

        # Should generate token but may contain empty email
        data = token_service.verify_email_verification_token(token)
        assert data['email'] == ''
        print("✅ Empty email handled correctly")

    def test_special_characters_in_email(self, token_service):
        """Test token generation with special characters in email"""
        special_email = 'test+special@example.com'
        token = token_service.generate_email_verification_token(
            user_id='550e8400-e29b-41d4-a716-446655440000',
            email=special_email
        )

        data = token_service.verify_email_verification_token(token)
        assert data['email'] == special_email
        print("✅ Special characters in email handled correctly")


# =============================================================================
# Run tests
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
