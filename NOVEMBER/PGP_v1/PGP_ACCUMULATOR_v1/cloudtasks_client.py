#!/usr/bin/env python
"""
Cloud Tasks Client for PGP_ACCUMULATOR_v1 (Payment Accumulation Service).
Handles creation and dispatch of Cloud Tasks to PGP Split and HostPay services.
"""
from typing import Optional
from PGP_COMMON.cloudtasks import BaseCloudTasksClient


class CloudTasksClient(BaseCloudTasksClient):
    """
    Manages Cloud Tasks operations for PGP_ACCUMULATOR_v1.
    Inherits common methods from BaseCloudTasksClient.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., "us-central1")
        """
        # PGP_ACCUMULATOR doesn't use signed tasks, so pass empty signing_key
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key="",
            service_name="PGP_ACCUMULATOR_v1"
        )

    # ========================================================================
    # GCAccumulator → GCSplit2 (ETH→USDT Conversion Estimate)
    # ========================================================================

    def enqueue_pgp_split2_conversion(
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
        print(f"📤 [CLOUDTASKS] Enqueueing GCSplit2 conversion task")
        print(f"🆔 [CLOUDTASKS] Accumulation ID: {accumulation_id}")
        print(f"💰 [CLOUDTASKS] Accumulated ETH: ${accumulated_eth}")

        payload = {
            "accumulation_id": accumulation_id,
            "client_id": client_id,
            "accumulated_eth": accumulated_eth
        }

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # GCAccumulator → GCSplit3 (ETH→USDT Swap Creation)
    # ========================================================================

    def enqueue_pgp_split3_eth_to_usdt_swap(
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
        print(f"💱 [CLOUDTASKS] Enqueueing GCSplit3 ETH→USDT swap task")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    # ========================================================================
    # GCAccumulator → GCHostPay1 (Swap Execution)
    # ========================================================================

    def enqueue_pgp_hostpay1_execution(
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
        print(f"🚀 [CLOUDTASKS] Enqueueing GCHostPay1 execution task")

        payload = {"token": encrypted_token}

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )
