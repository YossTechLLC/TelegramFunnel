#!/usr/bin/env python
"""
Cloud Tasks Client for PGP_BATCHPROCESSOR_v1 (Batch Payout Processor Service).
Handles creation and dispatch of Cloud Tasks to PGP Split1 for batch payouts.
"""
from PGP_COMMON.cloudtasks import BaseCloudTasksClient


class CloudTasksClient(BaseCloudTasksClient):
    """
    Manages Cloud Tasks operations for PGP_BATCHPROCESSOR_v1.
    Inherits common methods from BaseCloudTasksClient.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., "us-central1")
        """
        # PGP_BATCHPROCESSOR doesn't use signed tasks, so pass empty signing_key
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key="",
            service_name="PGP_BATCHPROCESSOR_v1"
        )
