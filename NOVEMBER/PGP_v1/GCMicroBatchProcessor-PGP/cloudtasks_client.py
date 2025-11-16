#!/usr/bin/env python
"""
Cloud Tasks Client for GCMicroBatchProcessor-10-26.
Handles enqueueing tasks to GCHostPay1 batch execution queue.
"""
from google.cloud import tasks_v2
from typing import Optional


class CloudTasksClient:
    """
    Manages Cloud Tasks operations for GCMicroBatchProcessor-10-26.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initialize the CloudTasksClient.

        Args:
            project_id: Google Cloud project ID
            location: Cloud Tasks location (e.g., us-central1)
        """
        self.project_id = project_id
        self.location = location
        self.client = tasks_v2.CloudTasksClient()
        print(f"☁️ [CLOUDTASKS] CloudTasksClient initialized")
        print(f"📊 [CLOUDTASKS] Project: {project_id}, Location: {location}")

    def enqueue_gchostpay1_batch_execution(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue batch execution task to GCHostPay1.

        Args:
            queue_name: GCHostPay1 batch queue name
            target_url: GCHostPay1 service URL
            encrypted_token: Encrypted token with batch details

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"📤 [CLOUDTASKS] Enqueueing batch execution task to GCHostPay1")
            print(f"🎯 [CLOUDTASKS] Queue: {queue_name}")
            print(f"🌐 [CLOUDTASKS] Target: {target_url}")

            # Construct the fully qualified queue name
            parent = self.client.queue_path(self.project_id, self.location, queue_name)

            # Construct the request body
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": target_url,
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "body": f'{{"token": "{encrypted_token}"}}'.encode()
                }
            }

            # Create the task
            response = self.client.create_task(request={"parent": parent, "task": task})

            print(f"✅ [CLOUDTASKS] Task created successfully")
            print(f"🆔 [CLOUDTASKS] Task name: {response.name}")

            return response.name

        except Exception as e:
            print(f"❌ [CLOUDTASKS] Failed to create task: {e}")
            return None
