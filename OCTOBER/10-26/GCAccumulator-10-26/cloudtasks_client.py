#!/usr/bin/env python
"""
Cloud Tasks Client for GCAccumulator-10-26 (Payment Accumulation Service).
Handles creation and dispatch of Cloud Tasks to GCSplit2 for USDT conversion.
"""
import json
from typing import Optional
from google.cloud import tasks_v2


class CloudTasksClient:
    """
    Client for creating and dispatching Google Cloud Tasks.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: GCP project ID
            location: Cloud region (e.g., "us-central1")
        """
        if not project_id or not location:
            raise ValueError("Project ID and location are required")

        self.project_id = project_id
        self.location = location
        self.client = tasks_v2.CloudTasksClient()

        print(f"☁️ [CLOUD_TASKS] Initialized client")
        print(f"📍 [CLOUD_TASKS] Project: {project_id}, Location: {location}")

    def create_task(
        self,
        queue_name: str,
        target_url: str,
        payload: dict
    ) -> Optional[str]:
        """
        Create and enqueue a Cloud Task.

        Args:
            queue_name: Name of the Cloud Tasks queue
            target_url: Target service URL (full https:// URL)
            payload: JSON payload to send (will be converted to bytes)

        Returns:
            Task name if successful, None if failed
        """
        try:
            # Construct the fully qualified queue name
            parent = self.client.queue_path(self.project_id, self.location, queue_name)

            print(f"🚀 [CLOUD_TASKS] Creating task for queue: {queue_name}")
            print(f"🎯 [CLOUD_TASKS] Target URL: {target_url}")
            print(f"📦 [CLOUD_TASKS] Payload size: {len(json.dumps(payload))} bytes")

            # Construct the task
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": target_url,
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "body": json.dumps(payload).encode()
                }
            }

            # Create the task
            response = self.client.create_task(request={"parent": parent, "task": task})

            task_name = response.name
            print(f"✅ [CLOUD_TASKS] Task created successfully")
            print(f"🆔 [CLOUD_TASKS] Task name: {task_name}")

            return task_name

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error creating task: {e}")
            return None

    def enqueue_gcsplit2_conversion(
        self,
        queue_name: str,
        target_url: str,
        accumulation_id: int,
        client_id: str,
        accumulated_eth: float
    ) -> Optional[str]:
        """
        Enqueue ETH→USDT conversion task to GCSplit2.

        Args:
            queue_name: GCSplit2 queue name
            target_url: GCSplit2 /estimate-and-update endpoint URL
            accumulation_id: Database accumulation record ID
            client_id: Client's closed_channel_id
            accumulated_eth: ETH value to convert (USD equivalent)

        Returns:
            Task name if successful, None if failed
        """
        payload = {
            "accumulation_id": accumulation_id,
            "client_id": client_id,
            "accumulated_eth": accumulated_eth
        }

        print(f"📤 [CLOUD_TASKS] Enqueueing GCSplit2 conversion task")
        print(f"🆔 [CLOUD_TASKS] Accumulation ID: {accumulation_id}")
        print(f"💰 [CLOUD_TASKS] Accumulated ETH: ${accumulated_eth}")

        return self.create_task(queue_name, target_url, payload)

    def enqueue_gcsplit3_eth_to_usdt_swap(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue ETH→USDT swap creation task to GCSplit3.

        Args:
            queue_name: GCSplit3 queue name
            target_url: GCSplit3 /eth-to-usdt endpoint URL
            encrypted_token: Encrypted token with swap request data

        Returns:
            Task name if successful, None if failed
        """
        payload = {
            "token": encrypted_token
        }

        print(f"💱 [CLOUD_TASKS] Enqueueing GCSplit3 ETH→USDT swap task")

        return self.create_task(queue_name, target_url, payload)

    def enqueue_gchostpay1_execution(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue swap execution task to GCHostPay1.

        Args:
            queue_name: GCHostPay1 queue name
            target_url: GCHostPay1 endpoint URL
            encrypted_token: Encrypted token with execution request data

        Returns:
            Task name if successful, None if failed
        """
        payload = {
            "token": encrypted_token
        }

        print(f"🚀 [CLOUD_TASKS] Enqueueing GCHostPay1 execution task")

        return self.create_task(queue_name, target_url, payload)
