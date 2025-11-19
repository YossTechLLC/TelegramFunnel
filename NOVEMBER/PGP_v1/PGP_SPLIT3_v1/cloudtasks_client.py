#!/usr/bin/env python
"""
Cloud Tasks Client for PGP_SPLIT3_v1
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
        # PGP_SPLIT3 doesn't use signed tasks, so pass empty signing_key
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key="",
            service_name="PGP_SPLIT3_v1"
        )

    def enqueue_pgp_split1_swap_response(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str
    ) -> Optional[str]:
        """
        Enqueue an ETH→ClientCurrency swap response back to PGP_SPLIT1_v1.

        Args:
            queue_name: Queue name (e.g., "pgp-split-eth-client-response-queue")
            target_url: PGP_SPLIT1_v1 /eth-client-swap endpoint URL
            encrypted_token: Encrypted token with swap transaction data

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"📨 [CLOUD_TASKS] Enqueueing swap response to PGP_SPLIT1_v1")

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
