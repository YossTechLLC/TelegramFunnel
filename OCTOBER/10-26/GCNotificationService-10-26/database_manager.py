#!/usr/bin/env python
"""
🗄️ Database Manager for GCNotificationService
Handles PostgreSQL connections and notification queries
"""
import psycopg2
import os
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and notification queries"""

    def __init__(self, host: str, port: int, dbname: str, user: str, password: str):
        """
        Initialize database manager

        Args:
            host: Database host (Cloud SQL Unix socket or IP)
            port: Database port (default 5432)
            dbname: Database name
            user: Database user
            password: Database password
        """
        # Check if running in Cloud Run (use Unix socket) or locally (use TCP)
        cloud_sql_connection = os.getenv("CLOUD_SQL_CONNECTION_NAME")

        if cloud_sql_connection:
            # Cloud Run mode - use Unix socket
            self.host = f"/cloudsql/{cloud_sql_connection}"
            logger.info(f"🔌 [DATABASE] Using Cloud SQL Unix socket: {self.host}")
        else:
            # Local/VM mode - use TCP connection
            self.host = host
            logger.info(f"🔌 [DATABASE] Using TCP connection to: {self.host}")

        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password

        # Validate credentials
        if not self.password:
            raise RuntimeError("Database password not available. Cannot initialize DatabaseManager.")
        if not all([self.host, self.dbname, self.user]):
            raise RuntimeError("Critical database configuration missing.")

        logger.info(f"🗄️ [DATABASE] Initialized (host={self.host}, dbname={dbname})")

    def get_connection(self):
        """
        Create and return a database connection

        Returns:
            psycopg2 connection object
        """
        try:
            conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            return conn
        except Exception as e:
            logger.error(f"❌ [DATABASE] Connection error: {e}")
            raise

    def get_notification_settings(self, open_channel_id: str) -> Optional[Tuple[bool, Optional[int]]]:
        """
        Get notification settings for a channel

        Args:
            open_channel_id: The open channel ID to look up

        Returns:
            Tuple of (notification_status, notification_id) if found, None otherwise

        Example:
            >>> db.get_notification_settings("-1003268562225")
            (True, 123456789)
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT notification_status, notification_id
                FROM main_clients_database
                WHERE open_channel_id = %s
            """, (str(open_channel_id),))

            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                notification_status, notification_id = result
                logger.info(
                    f"✅ [DATABASE] Settings for {open_channel_id}: "
                    f"enabled={notification_status}, id={notification_id}"
                )
                return notification_status, notification_id
            else:
                logger.warning(f"⚠️ [DATABASE] No settings found for {open_channel_id}")
                return None

        except Exception as e:
            logger.error(f"❌ [DATABASE] Error fetching notification settings: {e}")
            return None

    def get_channel_details_by_open_id(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch channel details by open_channel_id for notification message formatting

        Args:
            open_channel_id: The open channel ID to fetch details for

        Returns:
            Dict containing channel details or None if not found:
            {
                "closed_channel_title": str,
                "closed_channel_description": str
            }

        Example:
            >>> db.get_channel_details_by_open_id("-1003268562225")
            {
                "closed_channel_title": "Premium SHIBA Channel",
                "closed_channel_description": "Exclusive content"
            }
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT
                    closed_channel_title,
                    closed_channel_description
                FROM main_clients_database
                WHERE open_channel_id = %s
                LIMIT 1
            """, (str(open_channel_id),))

            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                channel_details = {
                    "closed_channel_title": result[0] if result[0] else "Premium Channel",
                    "closed_channel_description": result[1] if result[1] else "Exclusive content"
                }
                logger.info(f"✅ [DATABASE] Fetched channel details for {open_channel_id}")
                return channel_details
            else:
                logger.warning(f"⚠️ [DATABASE] No channel details found for {open_channel_id}")
                return None

        except Exception as e:
            logger.error(f"❌ [DATABASE] Error fetching channel details: {e}")
            return None
