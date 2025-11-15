#!/usr/bin/env python
"""
Base Cloud Tasks Client for PGP_v1 Services.
Provides common Cloud Tasks operations shared across all PGP_v1 microservices.
"""
import json
import datetime
from typing import Optional
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2


class BaseCloudTasksClient:
    """
    Base class for Cloud Tasks operations across all PGP_v1 services.

    This class provides the common create_task() method that is 70-80% identical
    across all services. Service-specific enqueue methods remain in subclasses.
    """

    def __init__(self, project_id: str, location: str, signing_key: str, service_name: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: GCP project ID
            location: Cloud region (e.g., "us-central1")
            signing_key: SUCCESS_URL_SIGNING_KEY for webhook signature
            service_name: Name of the service (for logging)
        """
        if not project_id or not location:
            raise ValueError("Project ID and location are required")

        self.project_id = project_id
        self.location = location
        self.signing_key = signing_key
        self.service_name = service_name
        self.client = tasks_v2.CloudTasksClient()

        print(f"☁️ [CLOUD_TASKS] Initialized client for {service_name}")
        print(f"📍 [CLOUD_TASKS] Project: {project_id}, Location: {location}")

    def create_task(
        self,
        queue_name: str,
        target_url: str,
        payload: dict,
        schedule_delay_seconds: int = 0,
        custom_headers: Optional[dict] = None
    ) -> Optional[str]:
        """
        Create and enqueue a Cloud Task.

        This method is 70-80% identical across all PGP_v1 services.

        Args:
            queue_name: Name of the Cloud Tasks queue
            target_url: Target service URL (full https:// URL)
            payload: JSON payload to send (will be converted to bytes)
            schedule_delay_seconds: Optional delay before task execution (default 0)
            custom_headers: Optional custom headers to add (e.g., X-Webhook-Signature)

        Returns:
            Task name if successful, None if failed
        """
        try:
            # Construct the fully qualified queue name
            parent = self.client.queue_path(self.project_id, self.location, queue_name)

            print(f"🚀 [CLOUD_TASKS] Creating task for queue: {queue_name}")
            print(f"🎯 [CLOUD_TASKS] Target URL: {target_url}")
            print(f"📦 [CLOUD_TASKS] Payload size: {len(json.dumps(payload))} bytes")

            # Construct headers
            headers = {
                "Content-Type": "application/json"
            }

            # Add custom headers if provided
            if custom_headers:
                headers.update(custom_headers)
                print(f"🔐 [CLOUD_TASKS] Added {len(custom_headers)} custom header(s)")

            # Construct the task
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": target_url,
                    "headers": headers,
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

    def create_signed_task(
        self,
        queue_name: str,
        target_url: str,
        payload: dict,
        schedule_delay_seconds: int = 0
    ) -> Optional[str]:
        """
        Create a Cloud Task with webhook signature.

        This is a convenience method that automatically adds X-Webhook-Signature
        header using the signing_key.

        Args:
            queue_name: Name of the Cloud Tasks queue
            target_url: Target service URL (full https:// URL)
            payload: JSON payload to send (will be converted to bytes)
            schedule_delay_seconds: Optional delay before task execution (default 0)

        Returns:
            Task name if successful, None if failed
        """
        import hmac
        import hashlib

        try:
            # Create HMAC signature
            payload_json = json.dumps(payload)
            signature = hmac.new(
                self.signing_key.encode(),
                payload_json.encode(),
                hashlib.sha256
            ).hexdigest()

            # Add signature to custom headers
            custom_headers = {
                "X-Webhook-Signature": signature
            }

            print(f"🔐 [CLOUD_TASKS] Added webhook signature")

            # Use create_task with custom headers
            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload,
                schedule_delay_seconds=schedule_delay_seconds,
                custom_headers=custom_headers
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error creating signed task: {e}")
            return None
