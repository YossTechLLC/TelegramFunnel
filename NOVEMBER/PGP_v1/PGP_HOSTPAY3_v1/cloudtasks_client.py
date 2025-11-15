#!/usr/bin/env python
"""
Cloud Tasks Client for GCHostPay Services.
Handles creating and enqueueing Cloud Tasks for inter-service communication.

Supports:
- GCHostPay1 → GCHostPay2 (status check request)
- GCHostPay1 → GCHostPay3 (payment execution request)
- GCHostPay2 → GCHostPay1 (status check response)
- GCHostPay3 → GCHostPay1 (payment execution response)
"""
import json
from google.cloud import tasks_v2
from typing import Optional


class CloudTasksClient:
    """
    Manages Cloud Tasks operations for GCHostPay services.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., "us-central1")
        """
        self.client = tasks_v2.CloudTasksClient()
        self.project_id = project_id
        self.location = location
        print(f"✅ [CLOUDTASKS] CloudTasksClient initialized")
        print(f"📊 [CLOUDTASKS] Project: {project_id}, Location: {location}")

    def create_task(
        self,
        queue_name: str,
        target_url: str,
        payload: dict,
        schedule_delay_seconds: int = 0
    ) -> Optional[str]:
        """
        Create and enqueue a Cloud Task.

        Args:
            queue_name: Name of the Cloud Tasks queue
            target_url: Target service URL
            payload: JSON payload to send
            schedule_delay_seconds: Optional delay before execution (default: 0)

        Returns:
            Task name if successful, None if failed
        """
        try:
            # Construct the queue path
            parent = self.client.queue_path(self.project_id, self.location, queue_name)

            # Construct the task
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": target_url,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(payload).encode()
                }
            }

            # Add schedule time if delay is specified
            if schedule_delay_seconds > 0:
                import datetime
                schedule_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=schedule_delay_seconds)
                task["schedule_time"] = schedule_time

            print(f"📤 [CLOUDTASKS] Creating task to {target_url}")
            print(f"📦 [CLOUDTASKS] Queue: {queue_name}")
            if schedule_delay_seconds > 0:
                print(f"⏰ [CLOUDTASKS] Scheduled delay: {schedule_delay_seconds}s")

            # Create the task
            response = self.client.create_task(request={"parent": parent, "task": task})

            print(f"✅ [CLOUDTASKS] Task created successfully")
            print(f"🆔 [CLOUDTASKS] Task name: {response.name}")

            return response.name

        except Exception as e:
            print(f"❌ [CLOUDTASKS] Error creating task: {e}")
            return None

    # ========================================================================
    # GCHostPay1 → GCHostPay2 (Status Check Request)
    # ========================================================================

    def enqueue_gchostpay2_status_check(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue status check request to GCHostPay2.

        Args:
            queue_name: GCHostPay2 queue name
            target_url: GCHostPay2 service URL
            encrypted_token: Encrypted token with unique_id and cn_api_id

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing status check to GCHostPay2")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # GCHostPay1 → GCHostPay3 (Payment Execution Request)
    # ========================================================================

    def enqueue_gchostpay3_payment_execution(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue payment execution request to GCHostPay3.

        Args:
            queue_name: GCHostPay3 queue name
            target_url: GCHostPay3 service URL
            encrypted_token: Encrypted token with payment details

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing payment execution to GCHostPay3")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # GCHostPay2 → GCHostPay1 (Status Check Response)
    # ========================================================================

    def enqueue_gchostpay1_status_response(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue status check response back to GCHostPay1.

        Args:
            queue_name: GCHostPay1 response queue name
            target_url: GCHostPay1 /status-verified endpoint URL
            encrypted_token: Encrypted token with status result

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing status response to GCHostPay1")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # GCHostPay3 → GCHostPay1 (Payment Execution Response)
    # ========================================================================

    def enqueue_gchostpay1_payment_response(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue payment execution response back to GCHostPay1.

        Args:
            queue_name: GCHostPay1 response queue name
            target_url: GCHostPay1 /payment-completed endpoint URL
            encrypted_token: Encrypted token with payment result

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing payment response to GCHostPay1")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # GCHostPay3 → GCHostPay3 (Self-Retry After Failure) [NEW]
    # ========================================================================

    def enqueue_gchostpay3_retry(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str,
        retry_delay_seconds: int = 60
    ) -> Optional[str]:
        """
        NEW METHOD: Enqueue retry task to GCHostPay3 itself after transient failure.

        This method is called when a payment fails with a retryable error (e.g., RATE_LIMIT_EXCEEDED).
        The retry is delayed by retry_delay_seconds to allow transient issues to resolve.

        Args:
            queue_name: GCHostPay3 retry queue name (e.g., "gchostpay3-retry-queue")
            target_url: GCHostPay3 service URL (same as original endpoint)
            encrypted_token: Retry token with incremented attempt_count
            retry_delay_seconds: Delay before retry execution (default: 60s)

        Returns:
            Task name if successful, None if failed

        Example:
            >>> tasks_client.enqueue_gchostpay3_retry(
            ...     queue_name="gchostpay3-retry-queue",
            ...     target_url="https://gchostpay3-10-26.run.app/",
            ...     encrypted_token=retry_token,
            ...     retry_delay_seconds=60
            ... )
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing self-retry to GCHostPay3")
        print(f"⏰ [CLOUDTASKS] Retry delay: {retry_delay_seconds}s")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload,
            schedule_delay_seconds=retry_delay_seconds
        )
