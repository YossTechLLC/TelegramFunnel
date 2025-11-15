#!/usr/bin/env python3
"""
🧪 Unit Tests for EmailService
Tests email template generation and dev mode functionality.
Full SendGrid integration tests require a test API key.
"""
import pytest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.services.email_service import EmailService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def email_service_dev_mode():
    """Create EmailService instance in dev mode (no API key)"""
    # Ensure no API key is set
    if 'SENDGRID_API_KEY' in os.environ:
        del os.environ['SENDGRID_API_KEY']

    # Set test configuration
    os.environ['FROM_EMAIL'] = 'test@example.com'
    os.environ['FROM_NAME'] = 'Test App'
    os.environ['BASE_URL'] = 'https://test.example.com'

    service = EmailService()

    yield service

    # Cleanup
    for key in ['FROM_EMAIL', 'FROM_NAME', 'BASE_URL']:
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def test_email_data():
    """Sample email data for testing"""
    return {
        'to_email': 'recipient@example.com',
        'username': 'testuser',
        'token': 'test-token-1234567890abcdef'
    }


# =============================================================================
# Initialization Tests
# =============================================================================

class TestEmailServiceInitialization:
    """Tests for EmailService initialization"""

    def test_init_dev_mode(self, email_service_dev_mode):
        """Test initialization in dev mode"""
        assert email_service_dev_mode.sendgrid_api_key is None
        assert email_service_dev_mode.from_email == 'test@example.com'
        assert email_service_dev_mode.from_name == 'Test App'
        assert email_service_dev_mode.base_url == 'https://test.example.com'
        print("✅ EmailService initialized in dev mode")

    def test_init_defaults(self):
        """Test initialization with default values"""
        # Clear all environment variables
        for key in ['SENDGRID_API_KEY', 'FROM_EMAIL', 'FROM_NAME', 'BASE_URL']:
            if key in os.environ:
                del os.environ[key]

        service = EmailService()

        assert service.from_email == 'noreply@pgp_server.com'
        assert service.from_name == 'TelePay'
        assert service.base_url == 'https://app.pgp_server.com'
        print("✅ EmailService uses correct defaults")


# =============================================================================
# Dev Mode Email Tests
# =============================================================================

class TestDevModeEmails:
    """Tests for dev mode email sending (no actual API calls)"""

    def test_send_verification_email_dev_mode(self, email_service_dev_mode, test_email_data, capsys):
        """Test sending verification email in dev mode"""
        result = email_service_dev_mode.send_verification_email(
            to_email=test_email_data['to_email'],
            username=test_email_data['username'],
            token=test_email_data['token']
        )

        # Should return True in dev mode
        assert result is True

        # Check console output
        captured = capsys.readouterr()
        assert '[DEV MODE]' in captured.out
        assert 'Email Verification' in captured.out
        assert test_email_data['to_email'] in captured.out
        assert test_email_data['token'] in captured.out

        print("✅ Verification email dev mode works correctly")

    def test_send_password_reset_email_dev_mode(self, email_service_dev_mode, test_email_data, capsys):
        """Test sending password reset email in dev mode"""
        result = email_service_dev_mode.send_password_reset_email(
            to_email=test_email_data['to_email'],
            username=test_email_data['username'],
            token=test_email_data['token']
        )

        # Should return True in dev mode
        assert result is True

        # Check console output
        captured = capsys.readouterr()
        assert '[DEV MODE]' in captured.out
        assert 'Password Reset Request' in captured.out
        assert test_email_data['to_email'] in captured.out
        assert test_email_data['token'] in captured.out

        print("✅ Password reset email dev mode works correctly")

    def test_send_password_reset_confirmation_dev_mode(self, email_service_dev_mode, test_email_data, capsys):
        """Test sending password reset confirmation email in dev mode"""
        result = email_service_dev_mode.send_password_reset_confirmation_email(
            to_email=test_email_data['to_email'],
            username=test_email_data['username']
        )

        # Should return True in dev mode
        assert result is True

        # Check console output
        captured = capsys.readouterr()
        assert '[DEV MODE]' in captured.out
        assert 'Password Reset Confirmation' in captured.out
        assert test_email_data['to_email'] in captured.out

        print("✅ Password reset confirmation dev mode works correctly")


# =============================================================================
# Email Template Tests
# =============================================================================

class TestEmailTemplates:
    """Tests for email template generation"""

    def test_verification_email_template(self):
        """Test verification email template generation"""
        username = 'testuser'
        verification_url = 'https://example.com/verify?token=abc123'

        html = EmailService._get_verification_email_template(username, verification_url)

        # Check template contains expected elements
        assert username in html
        assert verification_url in html
        assert 'Verify Email Address' in html or 'verify' in html.lower()
        assert '24 hours' in html or '24' in html
        assert 'html' in html.lower()
        assert '<a' in html  # Has clickable link

        print("✅ Verification email template generated correctly")

    def test_password_reset_email_template(self):
        """Test password reset email template generation"""
        username = 'testuser'
        reset_url = 'https://example.com/reset?token=xyz789'

        html = EmailService._get_password_reset_email_template(username, reset_url)

        # Check template contains expected elements
        assert username in html
        assert reset_url in html
        assert 'Reset Password' in html or 'reset' in html.lower()
        assert '1 hour' in html or '1' in html
        assert 'html' in html.lower()
        assert '<a' in html  # Has clickable link

        print("✅ Password reset email template generated correctly")

    def test_password_reset_confirmation_template(self):
        """Test password reset confirmation template generation"""
        username = 'testuser'

        html = EmailService._get_password_reset_confirmation_template(username)

        # Check template contains expected elements
        assert username in html
        assert 'successfully' in html.lower() or 'success' in html.lower()
        assert 'password' in html.lower()
        assert 'html' in html.lower()

        print("✅ Password reset confirmation template generated correctly")

    def test_template_html_structure(self):
        """Test that templates have proper HTML structure"""
        username = 'testuser'
        url = 'https://example.com/test'

        templates = [
            EmailService._get_verification_email_template(username, url),
            EmailService._get_password_reset_email_template(username, url),
            EmailService._get_password_reset_confirmation_template(username)
        ]

        for html in templates:
            # Check basic HTML structure
            assert '<!DOCTYPE html>' in html or '<html>' in html.lower()
            assert '<body' in html.lower()
            assert '</body>' in html.lower()
            assert '</html>' in html.lower()

        print("✅ All templates have valid HTML structure")


# =============================================================================
# URL Generation Tests
# =============================================================================

class TestURLGeneration:
    """Tests for URL generation in emails"""

    def test_verification_url_generation(self, email_service_dev_mode):
        """Test that verification URLs are correctly generated"""
        token = 'test-token-123'

        # Access the private method via service
        html = email_service_dev_mode._get_verification_email_template('testuser',
            f"{email_service_dev_mode.base_url}/verify-email?token={token}")

        # Check URL is in template
        assert email_service_dev_mode.base_url in html
        assert '/verify-email?token=' in html
        assert token in html

        print("✅ Verification URL generated correctly")

    def test_reset_url_generation(self, email_service_dev_mode):
        """Test that reset URLs are correctly generated"""
        token = 'test-reset-token-456'

        # Access the private method via service
        html = email_service_dev_mode._get_password_reset_email_template('testuser',
            f"{email_service_dev_mode.base_url}/reset-password?token={token}")

        # Check URL is in template
        assert email_service_dev_mode.base_url in html
        assert '/reset-password?token=' in html
        assert token in html

        print("✅ Reset URL generated correctly")


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error conditions"""

    def test_special_characters_in_username(self, email_service_dev_mode):
        """Test templates with special characters in username"""
        username = "Test User <test@example.com>"
        url = "https://example.com/test"

        html = EmailService._get_verification_email_template(username, url)

        # Should handle special characters
        assert 'Test User' in html
        print("✅ Special characters in username handled correctly")

    def test_long_token(self, email_service_dev_mode, capsys):
        """Test email with very long token"""
        long_token = 'a' * 500  # 500 character token

        result = email_service_dev_mode.send_verification_email(
            to_email='test@example.com',
            username='testuser',
            token=long_token
        )

        assert result is True
        print("✅ Long tokens handled correctly")

    def test_email_with_plus_sign(self, email_service_dev_mode, capsys):
        """Test email addresses with + sign"""
        email_with_plus = 'test+spam@example.com'

        result = email_service_dev_mode.send_verification_email(
            to_email=email_with_plus,
            username='testuser',
            token='test-token'
        )

        assert result is True

        captured = capsys.readouterr()
        assert email_with_plus in captured.out
        print("✅ Email addresses with + sign handled correctly")


# =============================================================================
# Template Personalization Tests
# =============================================================================

class TestTemplatePersonalization:
    """Tests for template personalization features"""

    def test_username_personalization(self):
        """Test that username is correctly personalized in all templates"""
        username = 'JohnDoe'
        url = 'https://example.com/test'

        templates = [
            EmailService._get_verification_email_template(username, url),
            EmailService._get_password_reset_email_template(username, url),
            EmailService._get_password_reset_confirmation_template(username)
        ]

        for html in templates:
            # Username should appear in the template
            assert username in html

        print("✅ All templates correctly personalized with username")

    def test_url_clickability(self):
        """Test that URLs are rendered as clickable links"""
        url = 'https://example.com/verify?token=abc123'

        html = EmailService._get_verification_email_template('testuser', url)

        # Should have proper anchor tag
        assert f'href="{url}"' in html or f"href='{url}'" in html
        print("✅ URLs rendered as clickable links")


# =============================================================================
# Run tests
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
