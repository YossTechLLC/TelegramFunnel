#!/usr/bin/env python
"""
Unit tests for BaseCloudTasksClient timestamp-based signature generation.

Tests the new timestamp-based signature generation in create_signed_task()
that prevents replay attacks.

Test Coverage:
- Timestamp generation and inclusion in signature
- Header generation (X-Signature, X-Request-Timestamp)
- Signature format validation
- Integration with Cloud Tasks API
"""
import pytest
import time
import hmac
import hashlib
import json
from unittest.mock import Mock, patch, MagicMock
from PGP_COMMON.cloudtasks import BaseCloudTasksClient


class TestTimestampSignatureGeneration:
    """Test suite for timestamp-based signature generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.location = "us-central1"
        self.signing_key = "test_signing_key_12345"
        self.service_name = "TEST_SERVICE"

        # Mock the CloudTasksClient to avoid actual GCP calls
        with patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient'):
            self.client = BaseCloudTasksClient(
                project_id=self.project_id,
                location=self.location,
                signing_key=self.signing_key,
                service_name=self.service_name
            )

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_create_signed_task_includes_timestamp_header(self, mock_tasks_client):
        """Test that create_signed_task includes X-Request-Timestamp header."""
        # Mock the create_task response
        mock_response = Mock()
        mock_response.name = "test-task-123"
        mock_tasks_client.return_value.create_task.return_value = mock_response

        # Patch the client's client attribute
        self.client.client = mock_tasks_client.return_value

        # Create signed task
        queue_name = "test-queue"
        target_url = "https://test-service.com/webhook"
        payload = {"user_id": 123, "amount": 100}

        task_name = self.client.create_signed_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

        # Verify create_task was called
        assert mock_tasks_client.return_value.create_task.called

        # Get the task argument passed to create_task
        call_args = mock_tasks_client.return_value.create_task.call_args
        task_request = call_args.kwargs['request']
        task = task_request['task']

        # Verify headers include both X-Signature and X-Request-Timestamp
        headers = task['http_request']['headers']
        assert 'X-Signature' in headers
        assert 'X-Request-Timestamp' in headers

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_create_signed_task_timestamp_is_valid_unix_time(self, mock_tasks_client):
        """Test that timestamp is valid Unix timestamp (seconds since epoch)."""
        mock_response = Mock()
        mock_response.name = "test-task-123"
        mock_tasks_client.return_value.create_task.return_value = mock_response
        self.client.client = mock_tasks_client.return_value

        before_time = int(time.time())

        task_name = self.client.create_signed_task(
            queue_name="test-queue",
            target_url="https://test-service.com/webhook",
            payload={"test": "data"}
        )

        after_time = int(time.time())

        # Get timestamp from headers
        call_args = mock_tasks_client.return_value.create_task.call_args
        task = call_args.kwargs['request']['task']
        timestamp_str = task['http_request']['headers']['X-Request-Timestamp']

        # Parse timestamp
        timestamp = int(timestamp_str)

        # Verify timestamp is within expected range (should be very close to current time)
        assert before_time <= timestamp <= after_time

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_create_signed_task_signature_includes_timestamp(self, mock_tasks_client):
        """Test that signature is calculated as HMAC(timestamp:payload)."""
        mock_response = Mock()
        mock_response.name = "test-task-123"
        mock_tasks_client.return_value.create_task.return_value = mock_response
        self.client.client = mock_tasks_client.return_value

        payload = {"user_id": 123, "amount": 100}

        # Create signed task
        with patch('time.time', return_value=1700000000.0):  # Fix timestamp for testing
            task_name = self.client.create_signed_task(
                queue_name="test-queue",
                target_url="https://test-service.com/webhook",
                payload=payload
            )

        # Get headers from the created task
        call_args = mock_tasks_client.return_value.create_task.call_args
        task = call_args.kwargs['request']['task']
        headers = task['http_request']['headers']
        actual_signature = headers['X-Signature']
        timestamp = headers['X-Request-Timestamp']

        # Manually calculate expected signature
        payload_json = json.dumps(payload)
        message = f"{timestamp}:{payload_json}"
        expected_signature = hmac.new(
            self.signing_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        # Verify signature matches
        assert actual_signature == expected_signature

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_create_signed_task_signature_format(self, mock_tasks_client):
        """Test that signature is 64-character hex string (SHA256)."""
        mock_response = Mock()
        mock_response.name = "test-task-123"
        mock_tasks_client.return_value.create_task.return_value = mock_response
        self.client.client = mock_tasks_client.return_value

        task_name = self.client.create_signed_task(
            queue_name="test-queue",
            target_url="https://test-service.com/webhook",
            payload={"test": "data"}
        )

        # Get signature from headers
        call_args = mock_tasks_client.return_value.create_task.call_args
        task = call_args.kwargs['request']['task']
        signature = task['http_request']['headers']['X-Signature']

        # Verify signature format
        assert len(signature) == 64  # SHA256 hex digest is 64 characters
        assert all(c in '0123456789abcdef' for c in signature)

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_create_signed_task_different_payloads_different_signatures(self, mock_tasks_client):
        """Test that different payloads produce different signatures."""
        mock_response = Mock()
        mock_response.name = "test-task-123"
        mock_tasks_client.return_value.create_task.return_value = mock_response
        self.client.client = mock_tasks_client.return_value

        # Create two tasks with different payloads
        with patch('time.time', return_value=1700000000.0):  # Same timestamp
            self.client.create_signed_task(
                queue_name="test-queue",
                target_url="https://test-service.com/webhook",
                payload={"amount": 100}
            )
            call1 = mock_tasks_client.return_value.create_task.call_args
            sig1 = call1.kwargs['request']['task']['http_request']['headers']['X-Signature']

            self.client.create_signed_task(
                queue_name="test-queue",
                target_url="https://test-service.com/webhook",
                payload={"amount": 200}
            )
            call2 = mock_tasks_client.return_value.create_task.call_args
            sig2 = call2.kwargs['request']['task']['http_request']['headers']['X-Signature']

        # Signatures should be different
        assert sig1 != sig2

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_create_signed_task_different_timestamps_different_signatures(self, mock_tasks_client):
        """Test that different timestamps produce different signatures."""
        mock_response = Mock()
        mock_response.name = "test-task-123"
        mock_tasks_client.return_value.create_task.return_value = mock_response
        self.client.client = mock_tasks_client.return_value

        payload = {"amount": 100}

        # Create two tasks with same payload but different timestamps
        with patch('time.time', return_value=1700000000.0):
            self.client.create_signed_task(
                queue_name="test-queue",
                target_url="https://test-service.com/webhook",
                payload=payload
            )
            call1 = mock_tasks_client.return_value.create_task.call_args
            sig1 = call1.kwargs['request']['task']['http_request']['headers']['X-Signature']

        with patch('time.time', return_value=1700000001.0):  # 1 second later
            self.client.create_signed_task(
                queue_name="test-queue",
                target_url="https://test-service.com/webhook",
                payload=payload
            )
            call2 = mock_tasks_client.return_value.create_task.call_args
            sig2 = call2.kwargs['request']['task']['http_request']['headers']['X-Signature']

        # Signatures should be different
        assert sig1 != sig2

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_create_signed_task_backward_compatibility(self, mock_tasks_client):
        """Test that create_signed_task still returns task name on success."""
        mock_response = Mock()
        mock_response.name = "projects/test/locations/us-central1/queues/test/tasks/12345"
        mock_tasks_client.return_value.create_task.return_value = mock_response
        self.client.client = mock_tasks_client.return_value

        task_name = self.client.create_signed_task(
            queue_name="test-queue",
            target_url="https://test-service.com/webhook",
            payload={"test": "data"}
        )

        # Should return task name
        assert task_name == mock_response.name

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_create_signed_task_error_handling(self, mock_tasks_client):
        """Test that create_signed_task handles errors gracefully."""
        mock_tasks_client.return_value.create_task.side_effect = Exception("Cloud Tasks API error")
        self.client.client = mock_tasks_client.return_value

        task_name = self.client.create_signed_task(
            queue_name="test-queue",
            target_url="https://test-service.com/webhook",
            payload={"test": "data"}
        )

        # Should return None on error
        assert task_name is None


class TestEndToEndCloudTasksToServer:
    """Integration tests simulating Cloud Tasks signature → Server verification."""

    def setup_method(self):
        """Set up sender and receiver with shared secret."""
        self.shared_secret = "shared_secret_key_12345"

        # Sender side (BaseCloudTasksClient)
        with patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient'):
            self.sender = BaseCloudTasksClient(
                project_id="test-project",
                location="us-central1",
                signing_key=self.shared_secret,
                service_name="TEST_SENDER"
            )

        # Receiver side (HMACAuth)
        from PGP_SERVER_v1.security.hmac_auth import HMACAuth
        self.receiver = HMACAuth(self.shared_secret)

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_end_to_end_signature_verification(self, mock_tasks_client):
        """Test that signature generated by sender can be verified by receiver."""
        mock_response = Mock()
        mock_response.name = "test-task-123"
        mock_tasks_client.return_value.create_task.return_value = mock_response
        self.sender.client = mock_tasks_client.return_value

        # Sender creates signed task
        payload = {"user_id": 123, "amount": 100}
        task_name = self.sender.create_signed_task(
            queue_name="test-queue",
            target_url="https://receiver.com/webhook",
            payload=payload
        )

        # Extract headers from created task
        call_args = mock_tasks_client.return_value.create_task.call_args
        task = call_args.kwargs['request']['task']
        headers = task['http_request']['headers']
        signature = headers['X-Signature']
        timestamp = headers['X-Request-Timestamp']
        payload_bytes = task['http_request']['body']

        # Receiver verifies signature
        is_valid = self.receiver.verify_signature(payload_bytes, signature, timestamp)

        # Should be valid
        assert is_valid is True

    @patch('PGP_COMMON.cloudtasks.base_client.tasks_v2.CloudTasksClient')
    def test_end_to_end_replay_attack_blocked(self, mock_tasks_client):
        """Test that old request cannot be replayed."""
        mock_response = Mock()
        mock_response.name = "test-task-123"
        mock_tasks_client.return_value.create_task.return_value = mock_response
        self.sender.client = mock_tasks_client.return_value

        # Sender creates signed task 10 minutes ago
        with patch('time.time', return_value=time.time() - 600):
            payload = {"user_id": 123, "amount": 100}
            task_name = self.sender.create_signed_task(
                queue_name="test-queue",
                target_url="https://receiver.com/webhook",
                payload=payload
            )

            # Extract headers
            call_args = mock_tasks_client.return_value.create_task.call_args
            task = call_args.kwargs['request']['task']
            headers = task['http_request']['headers']
            signature = headers['X-Signature']
            timestamp = headers['X-Request-Timestamp']
            payload_bytes = task['http_request']['body']

        # Now (10 minutes later), receiver tries to verify
        is_valid = self.receiver.verify_signature(payload_bytes, signature, timestamp)

        # Should be rejected (timestamp expired)
        assert is_valid is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
