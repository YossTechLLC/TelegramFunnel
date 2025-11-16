#!/usr/bin/env python
"""
Cloud Tasks Client for PGP_HOSTPAY1_v1.
Handles creating and enqueueing Cloud Tasks for inter-service communication.

Supports:
- PGP_HOSTPAY1_v1 → PGP_HOSTPAY2_v1 (status check request)
- PGP_HOSTPAY1_v1 → PGP_HOSTPAY3_v1 (payment execution request)
- PGP_HOSTPAY2_v1 → PGP_HOSTPAY1_v1 (status check response)
- PGP_HOSTPAY3_v1 → PGP_HOSTPAY1_v1 (payment execution response)
"""
from typing import Optional
from PGP_COMMON.cloudtasks import BaseCloudTasksClient


class CloudTasksClient(BaseCloudTasksClient):
    """
    Manages Cloud Tasks operations for PGP_HOSTPAY1_v1.
    Inherits common methods from BaseCloudTasksClient.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., "us-central1")
        """
        # PGP_HOSTPAY1 doesn't use signed tasks, so pass empty signing_key
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key="",
            service_name="PGP_HOSTPAY1_v1"
        )

    # ========================================================================
    # PGP_HOSTPAY1_v1 → PGP_HOSTPAY2_v1 (Status Check Request)
    # ========================================================================

    def enqueue_pgp_hostpay2_status_check(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue status check request to PGP_HOSTPAY2_v1.

        Args:
            queue_name: PGP_HOSTPAY2_v1 queue name
            target_url: PGP_HOSTPAY2_v1 service URL
            encrypted_token: Encrypted token with unique_id and cn_api_id

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing status check to PGP_HOSTPAY2_v1")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # PGP_HOSTPAY1_v1 → PGP_HOSTPAY3_v1 (Payment Execution Request)
    # ========================================================================

    def enqueue_pgp_hostpay3_payment_execution(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue payment execution request to PGP_HOSTPAY3_v1.

        Args:
            queue_name: PGP_HOSTPAY3_v1 queue name
            target_url: PGP_HOSTPAY3_v1 service URL
            encrypted_token: Encrypted token with payment details

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing payment execution to PGP_HOSTPAY3_v1")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # PGP_HOSTPAY2_v1 → PGP_HOSTPAY1_v1 (Status Check Response)
    # ========================================================================

    def enqueue_pgp_hostpay1_status_response(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue status check response back to PGP_HOSTPAY1_v1.

        Args:
            queue_name: PGP_HOSTPAY1_v1 response queue name
            target_url: PGP_HOSTPAY1_v1 /status-verified endpoint URL
            encrypted_token: Encrypted token with status result

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing status response to PGP_HOSTPAY1_v1")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # PGP_HOSTPAY3_v1 → PGP_HOSTPAY1_v1 (Payment Execution Response)
    # ========================================================================

    def enqueue_pgp_hostpay1_payment_response(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue payment execution response back to PGP_HOSTPAY1_v1.

        Args:
            queue_name: PGP_HOSTPAY1_v1 response queue name
            target_url: PGP_HOSTPAY1_v1 /payment-completed endpoint URL
            encrypted_token: Encrypted token with payment result

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing payment response to PGP_HOSTPAY1_v1")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # PGP_HOSTPAY1_v1 Retry (Delayed ChangeNow Query)
    # ========================================================================

    def enqueue_pgp_hostpay1_retry_callback(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str,
        delay_seconds: int = 300
    ) -> Optional[str]:
        """
        Enqueue delayed retry callback check to PGP_HOSTPAY1_v1.

        This handles the timing issue where ETH payment completes before ChangeNow
        swap finishes. We retry after a delay to check if amountTo is available.

        Args:
            queue_name: PGP_HOSTPAY1_v1 response queue name
            target_url: PGP_HOSTPAY1_v1 /retry-callback-check endpoint URL
            encrypted_token: Encrypted retry token with unique_id, cn_api_id, etc.
            delay_seconds: Delay before retry (default: 300 = 5 minutes)

        Returns:
            Task name if successful, None if failed
        """
        print(f"🔄 [CLOUDTASKS] Enqueueing delayed retry callback to PGP_HOSTPAY1_v1")
        print(f"⏱️ [CLOUDTASKS] Retry will execute in {delay_seconds}s")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload,
            schedule_delay_seconds=delay_seconds
        )
