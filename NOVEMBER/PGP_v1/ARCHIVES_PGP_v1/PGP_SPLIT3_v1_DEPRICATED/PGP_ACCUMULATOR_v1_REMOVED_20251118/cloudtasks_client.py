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

    # NOTE: Architecture changed from active orchestration to passive storage.
    # All downstream task enqueueing removed as PGP_MICROBATCHPROCESSOR_v1
    # now handles the orchestration. This service only stores accumulation data.
