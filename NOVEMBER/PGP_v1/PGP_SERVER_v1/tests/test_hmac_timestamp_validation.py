#!/usr/bin/env python
"""
Unit tests for HMAC timestamp validation (replay attack protection).

Tests the new timestamp-based signature verification that prevents replay attacks
by including Unix timestamps in HMAC signature calculation and validation.

Test Coverage:
- Timestamp validation (valid, expired, future-dated, invalid format)
- Signature generation with timestamp
- Signature verification with timestamp
- Integration tests with Flask decorator
"""
import pytest
import time
import hmac
import hashlib
from unittest.mock import Mock, patch
from flask import Flask, request
from PGP_SERVER_v1.security.hmac_auth import HMACAuth, TIMESTAMP_TOLERANCE_SECONDS


class TestTimestampValidation:
    """Test suite for timestamp validation logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.secret_key = "test_secret_key_12345"
        self.hmac_auth = HMACAuth(self.secret_key)

    def test_valid_current_timestamp(self):
        """Test that current timestamp is valid."""
        current_timestamp = str(int(time.time()))
        assert self.hmac_auth.validate_timestamp(current_timestamp) is True

    def test_valid_timestamp_within_window_past(self):
        """Test that timestamp 4 minutes in the past is valid."""
        # 4 minutes ago (within 5-minute window)
        past_timestamp = str(int(time.time()) - 240)
        assert self.hmac_auth.validate_timestamp(past_timestamp) is True

    def test_valid_timestamp_within_window_future(self):
        """Test that timestamp 4 minutes in the future is valid."""
        # 4 minutes in the future (within 5-minute window)
        future_timestamp = str(int(time.time()) + 240)
        assert self.hmac_auth.validate_timestamp(future_timestamp) is True

    def test_expired_timestamp_too_old(self):
        """Test that timestamp older than 5 minutes is rejected."""
        # 6 minutes ago (outside 5-minute window)
        expired_timestamp = str(int(time.time()) - 360)
        assert self.hmac_auth.validate_timestamp(expired_timestamp) is False

    def test_expired_timestamp_too_far_future(self):
        """Test that timestamp more than 5 minutes in future is rejected."""
        # 6 minutes in the future (outside 5-minute window)
        future_timestamp = str(int(time.time()) + 360)
        assert self.hmac_auth.validate_timestamp(future_timestamp) is False

    def test_invalid_timestamp_format_string(self):
        """Test that non-numeric timestamp is rejected."""
        invalid_timestamp = "not_a_timestamp"
        assert self.hmac_auth.validate_timestamp(invalid_timestamp) is False

    def test_invalid_timestamp_format_empty(self):
        """Test that empty timestamp is rejected."""
        assert self.hmac_auth.validate_timestamp("") is False

    def test_invalid_timestamp_format_none(self):
        """Test that None timestamp is rejected."""
        # This will raise TypeError which is caught
        assert self.hmac_auth.validate_timestamp(None) is False

    def test_boundary_timestamp_exactly_300_seconds_past(self):
        """Test timestamp exactly at the boundary (300 seconds ago)."""
        boundary_timestamp = str(int(time.time()) - TIMESTAMP_TOLERANCE_SECONDS)
        # Should be valid (tolerance is inclusive: abs(diff) > 300)
        assert self.hmac_auth.validate_timestamp(boundary_timestamp) is True

    def test_boundary_timestamp_exactly_301_seconds_past(self):
        """Test timestamp just outside the boundary (301 seconds ago)."""
        outside_timestamp = str(int(time.time()) - (TIMESTAMP_TOLERANCE_SECONDS + 1))
        assert self.hmac_auth.validate_timestamp(outside_timestamp) is False


class TestSignatureGenerationWithTimestamp:
    """Test suite for signature generation with timestamp."""

    def setup_method(self):
        """Set up test fixtures."""
        self.secret_key = "test_secret_key_12345"
        self.hmac_auth = HMACAuth(self.secret_key)

    def test_signature_includes_timestamp(self):
        """Test that signature changes when timestamp changes."""
        payload = b'{"user_id": 123, "amount": 100}'
        timestamp1 = "1700000000"
        timestamp2 = "1700000001"

        sig1 = self.hmac_auth.generate_signature(payload, timestamp1)
        sig2 = self.hmac_auth.generate_signature(payload, timestamp2)

        # Different timestamps should produce different signatures
        assert sig1 != sig2

    def test_signature_format_consistency(self):
        """Test that signature format is consistent (hex string)."""
        payload = b'{"user_id": 123}'
        timestamp = str(int(time.time()))

        signature = self.hmac_auth.generate_signature(payload, timestamp)

        # HMAC-SHA256 produces 64-character hex string
        assert len(signature) == 64
        assert all(c in '0123456789abcdef' for c in signature)

    def test_signature_reproducibility(self):
        """Test that same payload + timestamp produces same signature."""
        payload = b'{"user_id": 123}'
        timestamp = "1700000000"

        sig1 = self.hmac_auth.generate_signature(payload, timestamp)
        sig2 = self.hmac_auth.generate_signature(payload, timestamp)

        assert sig1 == sig2

    def test_signature_manual_calculation(self):
        """Test signature against manually calculated expected value."""
        payload = b'{"test": "data"}'
        timestamp = "1700000000"
        secret = self.secret_key.encode()

        # Manual calculation
        message = f"{timestamp}:".encode() + payload
        expected_sig = hmac.new(secret, message, hashlib.sha256).hexdigest()

        actual_sig = self.hmac_auth.generate_signature(payload, timestamp)

        assert actual_sig == expected_sig


class TestSignatureVerificationWithTimestamp:
    """Test suite for signature verification with timestamp."""

    def setup_method(self):
        """Set up test fixtures."""
        self.secret_key = "test_secret_key_12345"
        self.hmac_auth = HMACAuth(self.secret_key)

    def test_verify_valid_signature_and_timestamp(self):
        """Test that valid signature with current timestamp is accepted."""
        payload = b'{"user_id": 123}'
        timestamp = str(int(time.time()))
        signature = self.hmac_auth.generate_signature(payload, timestamp)

        assert self.hmac_auth.verify_signature(payload, signature, timestamp) is True

    def test_verify_invalid_signature(self):
        """Test that invalid signature is rejected even with valid timestamp."""
        payload = b'{"user_id": 123}'
        timestamp = str(int(time.time()))
        invalid_signature = "0" * 64  # Wrong signature

        assert self.hmac_auth.verify_signature(payload, invalid_signature, timestamp) is False

    def test_verify_expired_timestamp_valid_signature(self):
        """Test that valid signature with expired timestamp is rejected."""
        payload = b'{"user_id": 123}'
        # Timestamp from 10 minutes ago (expired)
        old_timestamp = str(int(time.time()) - 600)
        # Generate signature with old timestamp
        signature = self.hmac_auth.generate_signature(payload, old_timestamp)

        # Should reject due to expired timestamp
        assert self.hmac_auth.verify_signature(payload, signature, old_timestamp) is False

    def test_verify_missing_signature(self):
        """Test that missing signature is rejected."""
        payload = b'{"user_id": 123}'
        timestamp = str(int(time.time()))

        assert self.hmac_auth.verify_signature(payload, "", timestamp) is False
        assert self.hmac_auth.verify_signature(payload, None, timestamp) is False

    def test_verify_missing_timestamp(self):
        """Test that missing timestamp is rejected."""
        payload = b'{"user_id": 123}'
        signature = "a" * 64

        assert self.hmac_auth.verify_signature(payload, signature, "") is False
        assert self.hmac_auth.verify_signature(payload, signature, None) is False

    def test_verify_tampered_payload(self):
        """Test that tampered payload fails verification."""
        original_payload = b'{"user_id": 123, "amount": 100}'
        tampered_payload = b'{"user_id": 123, "amount": 999}'  # Changed amount
        timestamp = str(int(time.time()))

        # Generate signature for original payload
        signature = self.hmac_auth.generate_signature(original_payload, timestamp)

        # Verify with tampered payload should fail
        assert self.hmac_auth.verify_signature(tampered_payload, signature, timestamp) is False

    def test_verify_replay_attack_scenario(self):
        """Test that replayed request with old timestamp is rejected."""
        # Simulate legitimate request from 10 minutes ago
        payload = b'{"action": "transfer", "amount": 1000}'
        old_timestamp = str(int(time.time()) - 600)
        valid_signature = self.hmac_auth.generate_signature(payload, old_timestamp)

        # Attacker captures and replays the request now
        # Should be rejected due to timestamp expiration
        assert self.hmac_auth.verify_signature(payload, valid_signature, old_timestamp) is False


class TestHMACDecoratorIntegration:
    """Integration tests for HMAC decorator with Flask routes."""

    def setup_method(self):
        """Set up Flask app with HMAC-protected route."""
        self.app = Flask(__name__)
        self.secret_key = "test_secret_key_12345"
        self.hmac_auth = HMACAuth(self.secret_key)

        @self.app.route('/webhook', methods=['POST'])
        @self.hmac_auth.require_signature
        def test_webhook():
            return {'status': 'ok'}, 200

        self.client = self.app.test_client()

    def test_decorator_accepts_valid_signature_and_timestamp(self):
        """Test that decorator accepts request with valid signature and timestamp."""
        payload = {'user_id': 123, 'amount': 100}
        payload_bytes = str(payload).replace("'", '"').encode()  # JSON-like format
        timestamp = str(int(time.time()))

        # Generate valid signature
        signature = self.hmac_auth.generate_signature(payload_bytes, timestamp)

        # Make request with valid headers
        response = self.client.post(
            '/webhook',
            data=payload_bytes,
            headers={
                'X-Signature': signature,
                'X-Request-Timestamp': timestamp
            }
        )

        assert response.status_code == 200

    def test_decorator_rejects_missing_signature_header(self):
        """Test that decorator rejects request without X-Signature header."""
        payload = {'user_id': 123}
        timestamp = str(int(time.time()))

        response = self.client.post(
            '/webhook',
            json=payload,
            headers={'X-Request-Timestamp': timestamp}
        )

        assert response.status_code == 401

    def test_decorator_rejects_missing_timestamp_header(self):
        """Test that decorator rejects request without X-Request-Timestamp header."""
        payload = {'user_id': 123}
        signature = "a" * 64

        response = self.client.post(
            '/webhook',
            json=payload,
            headers={'X-Signature': signature}
        )

        assert response.status_code == 401

    def test_decorator_rejects_expired_timestamp(self):
        """Test that decorator rejects request with expired timestamp."""
        payload = {'user_id': 123}
        payload_bytes = str(payload).replace("'", '"').encode()
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago

        # Generate signature with old timestamp
        signature = self.hmac_auth.generate_signature(payload_bytes, old_timestamp)

        response = self.client.post(
            '/webhook',
            data=payload_bytes,
            headers={
                'X-Signature': signature,
                'X-Request-Timestamp': old_timestamp
            }
        )

        assert response.status_code == 403

    def test_decorator_rejects_invalid_signature(self):
        """Test that decorator rejects request with invalid signature."""
        payload = {'user_id': 123}
        timestamp = str(int(time.time()))
        invalid_signature = "0" * 64

        response = self.client.post(
            '/webhook',
            json=payload,
            headers={
                'X-Signature': invalid_signature,
                'X-Request-Timestamp': timestamp
            }
        )

        assert response.status_code == 403


class TestEndToEndSignatureFlow:
    """End-to-end tests simulating Cloud Tasks → PGP_SERVER flow."""

    def setup_method(self):
        """Set up sender and receiver."""
        self.signing_key = "shared_secret_key_12345"
        self.hmac_auth = HMACAuth(self.signing_key)

    def test_end_to_end_valid_request(self):
        """Test complete flow: generate signature → verify signature."""
        # Sender side (simulating Cloud Tasks)
        payload = {'payment_id': 12345, 'user_id': 67890}
        payload_json = str(payload).replace("'", '"')
        timestamp = str(int(time.time()))

        # Generate signature (simulating BaseCloudTasksClient.create_signed_task)
        message = f"{timestamp}:{payload_json}"
        signature = hmac.new(
            self.signing_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        # Receiver side (simulating PGP_SERVER)
        payload_bytes = payload_json.encode()
        is_valid = self.hmac_auth.verify_signature(payload_bytes, signature, timestamp)

        assert is_valid is True

    def test_end_to_end_replay_attack_blocked(self):
        """Test that replayed request from 10 minutes ago is blocked."""
        # Original request from 10 minutes ago
        payload = {'payment_id': 12345, 'user_id': 67890}
        payload_json = str(payload).replace("'", '"')
        old_timestamp = str(int(time.time()) - 600)

        # Generate signature with old timestamp
        message = f"{old_timestamp}:{payload_json}"
        signature = hmac.new(
            self.signing_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        # Attacker replays the request now
        payload_bytes = payload_json.encode()
        is_valid = self.hmac_auth.verify_signature(payload_bytes, signature, old_timestamp)

        # Should be rejected
        assert is_valid is False

    def test_end_to_end_tampered_payload_blocked(self):
        """Test that tampered payload is rejected."""
        # Original payload
        original_payload = {'payment_id': 12345, 'amount': 100}
        original_json = str(original_payload).replace("'", '"')
        timestamp = str(int(time.time()))

        # Generate signature for original
        message = f"{timestamp}:{original_json}"
        signature = hmac.new(
            self.signing_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        # Attacker tampers with amount
        tampered_payload = {'payment_id': 12345, 'amount': 999}
        tampered_json = str(tampered_payload).replace("'", '"')

        # Try to verify with tampered payload
        tampered_bytes = tampered_json.encode()
        is_valid = self.hmac_auth.verify_signature(tampered_bytes, signature, timestamp)

        # Should be rejected
        assert is_valid is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
