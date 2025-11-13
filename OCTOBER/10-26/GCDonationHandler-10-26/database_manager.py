#!/usr/bin/env python
"""
Database Manager for GCDonationHandler
Handles all PostgreSQL database operations

This module provides a self-contained interface for database operations
required by the donation handler service. It has no internal dependencies.
"""

import logging
import os
from typing import Optional, List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages PostgreSQL database operations for donation handler.

    This class provides methods for channel validation, metadata fetching,
    and broadcast list retrieval. All database operations use parameterized
    queries to prevent SQL injection.

    Attributes:
        db_host: Database host (Cloud SQL connection name or IP)
        db_port: Database port (default: 5432)
        db_name: Database name
        db_user: Database user
        db_password: Database password
    """

    def __init__(self, db_host: str, db_port: int, db_name: str, db_user: str, db_password: str):
        """
        Initialize the DatabaseManager with connection parameters.

        Automatically detects Cloud Run environment and uses Unix socket
        for Cloud SQL connections when CLOUD_SQL_CONNECTION_NAME is set.

        Args:
            db_host: Database host connection string (or IP for local/fallback)
            db_port: Database port number (ignored for Unix socket)
            db_name: Name of the database
            db_user: Database username
            db_password: Database password

        Raises:
            ValueError: If any required parameter is missing
        """
        if not all([db_host, db_name, db_user, db_password]):
            raise ValueError("All database connection parameters are required")

        # Check if running in Cloud Run (use Unix socket) or locally (use TCP)
        cloud_sql_connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME")

        if cloud_sql_connection_name:
            # Cloud Run mode - use Unix socket
            self.db_host = f"/cloudsql/{cloud_sql_connection_name}"
            self.db_port = None  # Port is not used for Unix socket
            logger.info(f"🔌 Using Cloud SQL Unix socket: {self.db_host}")
        else:
            # Local/VM mode - use TCP connection
            self.db_host = db_host
            self.db_port = db_port
            logger.info(f"🔌 Using TCP connection to: {self.db_host}:{self.db_port}")

        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password

        logger.info(f"🗄️ DatabaseManager initialized for {db_user}@{self.db_host}/{db_name}")

    def _get_connection(self):
        """
        Create and return a database connection.

        Uses Unix socket when CLOUD_SQL_CONNECTION_NAME is set (Cloud Run),
        otherwise uses TCP connection (local development).

        Returns:
            psycopg2 connection object, or None if connection fails

        Raises:
            psycopg2.Error: If database connection fails
        """
        try:
            # Build connection parameters
            conn_params = {
                "host": self.db_host,
                "dbname": self.db_name,
                "user": self.db_user,
                "password": self.db_password
            }

            # Only include port for TCP connections (not Unix socket)
            if self.db_port is not None:
                conn_params["port"] = self.db_port

            conn = psycopg2.connect(**conn_params)
            return conn
        except psycopg2.Error as e:
            logger.error(f"❌ Database connection error: {e}")
            raise

    def channel_exists(self, open_channel_id: str) -> bool:
        """
        Check if a channel exists in the database.

        This method validates channel IDs received in callback data to prevent
        unauthorized donation requests.

        Args:
            open_channel_id: The open channel ID to validate (e.g., "-1003268562225")

        Returns:
            True if channel exists, False otherwise

        Example:
            >>> db = DatabaseManager(...)
            >>> if db.channel_exists("-1003268562225"):
            ...     print("Channel is valid")
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM main_clients_database WHERE open_channel_id = %s",
                        (open_channel_id,)
                    )
                    result = cur.fetchone()
                    exists = result is not None

                    if exists:
                        logger.info(f"✅ Channel validated: {open_channel_id}")
                    else:
                        logger.warning(f"⚠️ Channel not found: {open_channel_id}")

                    return exists

        except psycopg2.Error as e:
            logger.error(f"❌ Error checking channel existence for {open_channel_id}: {e}")
            return False

    def get_channel_details_by_open_id(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch channel details by open channel ID.

        Retrieves all metadata for a channel, including closed channel information,
        donation message, and payout configuration.

        Args:
            open_channel_id: The open channel ID to look up

        Returns:
            Dictionary with channel details, or None if not found:
            {
                'open_channel_id': str,
                'open_channel_title': str,
                'open_channel_description': str,
                'closed_channel_id': str,
                'closed_channel_title': str,
                'closed_channel_description': str,
                'closed_channel_donation_message': str,
                'payout_strategy': str,
                'payout_threshold_usd': float,
                'client_wallet_address': str,
                'client_payout_currency': str,
                'client_payout_network': str
            }

        Example:
            >>> details = db.get_channel_details_by_open_id("-1003268562225")
            >>> print(f"Donation message: {details['closed_channel_donation_message']}")
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT
                            open_channel_id,
                            open_channel_title,
                            open_channel_description,
                            closed_channel_id,
                            closed_channel_title,
                            closed_channel_description,
                            closed_channel_donation_message,
                            payout_strategy,
                            payout_threshold_usd,
                            client_wallet_address,
                            client_payout_currency,
                            client_payout_network
                        FROM main_clients_database
                        WHERE open_channel_id = %s
                        """,
                        (open_channel_id,)
                    )
                    result = cur.fetchone()

                    if result:
                        logger.info(f"✅ Fetched channel details for: {open_channel_id}")
                        return dict(result)
                    else:
                        logger.warning(f"⚠️ No channel details found for: {open_channel_id}")
                        return None

        except psycopg2.Error as e:
            logger.error(f"❌ Error fetching channel details for {open_channel_id}: {e}")
            return None

    def fetch_all_closed_channels(self) -> List[Dict[str, Any]]:
        """
        Fetch all closed channels for broadcast operations.

        Retrieves all channels that have a closed channel configured. This is
        used by the broadcast manager to send donation buttons to all closed
        channels.

        Returns:
            List of dictionaries containing channel information:
            [
                {
                    'open_channel_id': str,
                    'closed_channel_id': str,
                    'closed_channel_donation_message': str
                },
                ...
            ]

        Example:
            >>> channels = db.fetch_all_closed_channels()
            >>> print(f"Found {len(channels)} closed channels")
            >>> for channel in channels:
            ...     print(f"  - {channel['closed_channel_id']}")
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT
                            open_channel_id,
                            closed_channel_id,
                            closed_channel_donation_message
                        FROM main_clients_database
                        WHERE closed_channel_id IS NOT NULL
                        AND closed_channel_id != ''
                        """
                    )
                    results = cur.fetchall()

                    channels = [dict(row) for row in results]
                    logger.info(f"✅ Fetched {len(channels)} closed channels for broadcast")
                    return channels

        except psycopg2.Error as e:
            logger.error(f"❌ Error fetching closed channels: {e}")
            return []

    def close(self):
        """
        Cleanup method for database connections.

        This method is provided for compatibility but connection cleanup
        is handled automatically via context managers in all operations.
        """
        logger.info("🗄️ DatabaseManager cleanup completed")
