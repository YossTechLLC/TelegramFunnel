#!/usr/bin/env python
"""
Cloud Tasks Client for PGP_MICROBATCHPROCESSOR_v1 (Micro-Batch Conversion Service).
Handles enqueueing tasks to PGP HostPay1 batch execution queue.
"""
from typing import Optional
from PGP_COMMON.cloudtasks import BaseCloudTasksClient


class CloudTasksClient(BaseCloudTasksClient):
    """
    Manages Cloud Tasks operations for PGP_MICROBATCHPROCESSOR_v1.
    Inherits common methods from BaseCloudTasksClient.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., "us-central1")
        """
        # PGP_MICROBATCHPROCESSOR doesn't use signed tasks, so pass empty signing_key
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key="",
            service_name="PGP_MICROBATCHPROCESSOR_v1"
        )

    # ========================================================================
    # PGP_MICROBATCHPROCESSOR → PGP_HOSTPAY1_v1 (Batch Execution)
    # ========================================================================

    def enqueue_pgp_hostpay1_batch_execution(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue batch execution task to PGP_HOSTPAY1_v1.

        Args:
            queue_name: PGP_HOSTPAY1_v1 batch queue name
            target_url: PGP_HOSTPAY1_v1 service URL
            encrypted_token: Encrypted token with batch details

        Returns:
            Task name if successful, None if failed
        """
        print(f"📤 [CLOUDTASKS] Enqueueing batch execution task to PGP_HOSTPAY1_v1")
        print(f"🎯 [CLOUDTASKS] Queue: {queue_name}")
        print(f"🌐 [CLOUDTASKS] Target: {target_url}")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )
