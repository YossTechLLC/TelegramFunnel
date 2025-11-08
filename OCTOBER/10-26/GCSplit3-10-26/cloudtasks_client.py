#!/usr/bin/env python
"""
Cloud Tasks Client for GCSplit Services
Handles creation and dispatch of Cloud Tasks for inter-service communication.
"""
import json
from typing import Optional
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import datetime


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
        payload: dict,
        schedule_delay_seconds: int = 0
    ) -> Optional[str]:
        """
        Create and enqueue a Cloud Task.

        Args:
            queue_name: Name of the Cloud Tasks queue
            target_url: Target service URL (full https:// URL)
            payload: JSON payload to send (will be converted to bytes)
            schedule_delay_seconds: Optional delay before task execution (default 0)

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

            # Add schedule time if delay is specified
            if schedule_delay_seconds > 0:
                d = datetime.datetime.utcnow() + datetime.timedelta(seconds=schedule_delay_seconds)
                timestamp = timestamp_pb2.Timestamp()
                timestamp.FromDatetime(d)
                task["schedule_time"] = timestamp
                print(f"⏰ [CLOUD_TASKS] Scheduled delay: {schedule_delay_seconds}s")

            # Create the task
            response = self.client.create_task(request={"parent": parent, "task": task})

            task_name = response.name
            print(f"✅ [CLOUD_TASKS] Task created successfully")
            print(f"🆔 [CLOUD_TASKS] Task name: {task_name}")

            return task_name

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error creating task: {e}")
            return None

    def enqueue_gcsplit2_estimate_request(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue a USDT→ETH estimate request to GCSplit2.

        Args:
            queue_name: Queue name (e.g., "gcsplit-usdt-eth-estimate-queue")
            target_url: GCSplit2 service URL
            encrypted_token: Encrypted token with request data

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"💰 [CLOUD_TASKS] Enqueueing USDT→ETH estimate request")

            payload = {
                "token": encrypted_token
            }

            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing estimate request: {e}")
            return None

    def enqueue_gcsplit1_estimate_response(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue a USDT→ETH estimate response back to GCSplit1.

        Args:
            queue_name: Queue name (e.g., "gcsplit-usdt-eth-response-queue")
            target_url: GCSplit1 /usdt-eth-estimate endpoint URL
            encrypted_token: Encrypted token with estimate data

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"📨 [CLOUD_TASKS] Enqueueing estimate response to GCSplit1")

            payload = {
                "token": encrypted_token
            }

            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing estimate response: {e}")
            return None

    def enqueue_gcsplit3_swap_request(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue an ETH→ClientCurrency swap request to GCSplit3.

        Args:
            queue_name: Queue name (e.g., "gcsplit-eth-client-swap-queue")
            target_url: GCSplit3 service URL
            encrypted_token: Encrypted token with swap request data

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"💱 [CLOUD_TASKS] Enqueueing ETH→Client swap request")

            payload = {
                "token": encrypted_token
            }

            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing swap request: {e}")
            return None

    def enqueue_gcsplit1_swap_response(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue an ETH→ClientCurrency swap response back to GCSplit1.

        Args:
            queue_name: Queue name (e.g., "gcsplit-eth-client-response-queue")
            target_url: GCSplit1 /eth-client-swap endpoint URL
            encrypted_token: Encrypted token with swap transaction data

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"📨 [CLOUD_TASKS] Enqueueing swap response to GCSplit1")

            payload = {
                "token": encrypted_token
            }

            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing swap response: {e}")
            return None

    def enqueue_hostpay_trigger(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue a GCHostPay trigger request.

        Args:
            queue_name: Queue name (e.g., "gcsplit-hostpay-trigger-queue")
            target_url: GCHostPay webhook URL
            encrypted_token: Encrypted token with HostPay data

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"🚀 [CLOUD_TASKS] Enqueueing HostPay trigger")

            payload = {
                "token": encrypted_token
            }

            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing HostPay trigger: {e}")
            return None

    def enqueue_accumulator_swap_response(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue swap response to GCAccumulator.

        Args:
            queue_name: Queue name (e.g., "gcaccumulator-swap-response-queue")
            target_url: GCAccumulator webhook URL
            encrypted_token: Encrypted token with swap details

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"🚀 [CLOUD_TASKS] Enqueueing response to GCAccumulator")

            payload = {
                "token": encrypted_token
            }

            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing GCAccumulator response: {e}")
            return None
