"""
Logging utilities for PGP_v1 services.

Provides centralized logging configuration with LOG_LEVEL control.

Usage:
    # In main service files (initialize logging)
    from PGP_COMMON.logging import setup_logger
    logger = setup_logger(__name__)

    # In library modules (just get logger)
    from PGP_COMMON.logging import get_logger
    logger = get_logger(__name__)
"""
from .base_logger import setup_logger, get_logger

__all__ = [
    'setup_logger',
    'get_logger'
]
