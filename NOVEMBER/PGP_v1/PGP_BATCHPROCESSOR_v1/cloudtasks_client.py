#!/usr/bin/env python
"""
Cloud Tasks Client for GCBatchProcessor-10-26 (Batch Payout Processor Service).
Handles creation and dispatch of Cloud Tasks to GCSplit1 for batch payouts.
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
