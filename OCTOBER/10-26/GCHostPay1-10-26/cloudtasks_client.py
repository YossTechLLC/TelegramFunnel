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
import datetime
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
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
                d = datetime.datetime.utcnow() + datetime.timedelta(seconds=schedule_delay_seconds)
                timestamp = timestamp_pb2.Timestamp()
                timestamp.FromDatetime(d)
                task["schedule_time"] = timestamp
                print(f"⏰ [CLOUDTASKS] Task scheduled for {schedule_delay_seconds}s from now")

            print(f"📤 [CLOUDTASKS] Creating task to {target_url}")
            print(f"📦 [CLOUDTASKS] Queue: {queue_name}")

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
    # GCHostPay1 Retry (Delayed ChangeNow Query)
    # ========================================================================

    def enqueue_gchostpay1_retry_callback(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str,
        delay_seconds: int = 300
    ) -> Optional[str]:
        """
        Enqueue delayed retry callback check to GCHostPay1.

        This handles the timing issue where ETH payment completes before ChangeNow
        swap finishes. We retry after a delay to check if amountTo is available.

        Args:
            queue_name: GCHostPay1 response queue name
            target_url: GCHostPay1 /retry-callback-check endpoint URL
            encrypted_token: Encrypted retry token with unique_id, cn_api_id, etc.
            delay_seconds: Delay before retry (default: 300 = 5 minutes)

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing delayed retry callback to GCHostPay1")
        print(f"⏱️ [CLOUDTASKS] Retry will execute in {delay_seconds}s")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload,
            schedule_delay_seconds=delay_seconds
        )
