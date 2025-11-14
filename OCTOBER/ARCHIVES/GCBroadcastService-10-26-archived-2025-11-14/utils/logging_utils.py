#!/usr/bin/env python3
"""
Logging Utilities
Structured logging setup for GCBroadcastService
"""

import logging
import sys


def setup_logging(level=logging.INFO):
    """
    Set up structured logging for the service.

    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=level,
        stream=sys.stdout
    )

    # Set specific loggers to WARNING to reduce noise
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
