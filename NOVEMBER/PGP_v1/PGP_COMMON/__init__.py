"""
PGP_COMMON - Shared library for PGP_v1 microservices.

This package provides common base classes for:
- Configuration management (BaseConfigManager)
- Cloud Tasks operations (BaseCloudTasksClient)
- Database operations (BaseDatabaseManager)
- Token management (BaseTokenManager)
- Logging utilities (setup_logger, get_logger)
"""

__version__ = "1.0.0"

from PGP_COMMON.config.base_config import BaseConfigManager
from PGP_COMMON.cloudtasks.base_client import BaseCloudTasksClient
from PGP_COMMON.database.db_manager import BaseDatabaseManager
from PGP_COMMON.tokens.base_token import BaseTokenManager
from PGP_COMMON.logging import setup_logger, get_logger

__all__ = [
    "BaseConfigManager",
    "BaseCloudTasksClient",
    "BaseDatabaseManager",
    "BaseTokenManager",
    "setup_logger",
    "get_logger",
]
