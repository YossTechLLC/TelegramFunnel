#!/usr/bin/env python
"""
Database Manager for PGP_ORCHESTRATOR_v1 (Payment Processor Service).
Handles database connections and operations for private_channel_users_database table.
"""
from typing import Optional
from PGP_COMMON.database import BaseDatabaseManager


class DatabaseManager(BaseDatabaseManager):
    """
    Manages database connections and operations for PGP_ORCHESTRATOR_v1.
    Inherits common methods from BaseDatabaseManager.
    """

    def __init__(self, instance_connection_name: str, db_name: str, db_user: str, db_password: str):
        """
        Initialize the DatabaseManager.

        Args:
            instance_connection_name: Cloud SQL instance connection name
            db_name: Database name
            db_user: Database user
            db_password: Database password
        """
        super().__init__(
            instance_connection_name=instance_connection_name,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            service_name="PGP_ORCHESTRATOR_v1"
        )

    # =========================================================================
    # SERVICE-SPECIFIC DATABASE METHODS
    # =========================================================================
    # All shared database methods (record_private_channel_user,
    # get_payout_strategy, get_subscription_id, get_nowpayments_data)
    # have been consolidated into PGP_COMMON/database/db_manager.py
    #
    # Add any ORCHESTRATOR-specific database methods here.
    # =========================================================================
