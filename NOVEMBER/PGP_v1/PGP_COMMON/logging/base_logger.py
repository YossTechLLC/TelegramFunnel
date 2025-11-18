#!/usr/bin/env python
"""
Base Logging Configuration for PGP_v1 Services.
Provides standardized logging setup with LOG_LEVEL control and structured output.

Usage:
    from PGP_COMMON.logging import setup_logger

    logger = setup_logger(__name__)
    logger.info("🚀 [APP] Service started")
    logger.debug("🔍 [DEBUG] Detailed debugging info")  # Only visible when LOG_LEVEL=DEBUG
"""
import os
import logging
import sys
from typing import Optional


def setup_logger(
    name: str,
    default_level: str = "INFO",
    format_string: Optional[str] = None,
    suppress_libraries: bool = True
) -> logging.Logger:
    """
    Setup standardized logger for PGP_v1 services.

    Args:
        name: Logger name (typically __name__ from calling module)
        default_level: Default log level if LOG_LEVEL env var not set
        format_string: Custom log format (uses default if None)
        suppress_libraries: Suppress verbose library logs (httpx, urllib3, etc.)

    Returns:
        Configured logger instance

    Environment Variables:
        LOG_LEVEL: Production log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                  Default: INFO (hides debug logs in production)

    Examples:
        # Production (LOG_LEVEL=INFO)
        logger.debug("Not visible")  ❌ Hidden
        logger.info("Visible")       ✅ Shown

        # Staging (LOG_LEVEL=DEBUG)
        logger.debug("Visible")      ✅ Shown
        logger.info("Visible")       ✅ Shown
    """
    # Get log level from environment (production control)
    log_level = os.getenv('LOG_LEVEL', default_level).upper()

    # Validate log level
    valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    if log_level not in valid_levels:
        print(f"⚠️  [LOGGING] Invalid LOG_LEVEL '{log_level}', defaulting to {default_level}")
        log_level = default_level

    # Configure logging format (matches existing PGP_v1 pattern)
    if format_string is None:
        # Structured format for Cloud Logging (consistent with existing services)
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Setup root logger (affects all loggers)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=format_string,
        stream=sys.stdout,  # Cloud Run captures stdout
        force=True  # Override any previous configuration
    )

    # Suppress verbose library logs (consistent with PGP_SERVER_v1 pattern)
    if suppress_libraries:
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('google.auth').setLevel(logging.WARNING)
        logging.getLogger('google.cloud').setLevel(logging.INFO)

    # Create and return logger for calling module
    logger = logging.getLogger(name)
    logger.info(f"📋 [LOGGING] Logger '{name}' initialized (level={log_level})")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get existing logger (assumes setup_logger was called earlier).

    This is useful for library modules (like PGP_COMMON modules) that don't need
    to configure logging themselves but just need a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Existing logger instance

    Usage:
        # In PGP_COMMON library modules (don't configure, just get logger)
        from PGP_COMMON.logging import get_logger
        logger = get_logger(__name__)

        # In main service files (configure logging first)
        from PGP_COMMON.logging import setup_logger
        logger = setup_logger(__name__)
    """
    return logging.getLogger(name)
