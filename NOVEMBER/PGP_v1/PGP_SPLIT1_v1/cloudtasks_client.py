#!/usr/bin/env python
"""
Cloud Tasks Client for PGP_SPLIT1_v1
Handles creation and dispatch of Cloud Tasks for inter-service communication.
"""
from typing import Optional
from PGP_COMMON.cloudtasks import BaseCloudTasksClient


class CloudTasksClient(BaseCloudTasksClient):
    """
    Client for creating and dispatching Google Cloud Tasks.
    Inherits common methods from BaseCloudTasksClient.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: GCP project ID
            location: Cloud region (e.g., "us-central1")
        """
        # PGP_SPLIT1 doesn't use signed tasks, so pass empty signing_key
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key="",
            service_name="PGP_SPLIT1_v1"
        )

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
