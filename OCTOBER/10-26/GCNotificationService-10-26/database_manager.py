#!/usr/bin/env python
"""
🗄️ Database Manager for GCNotificationService
Handles PostgreSQL connections and notification queries using NEW_ARCHITECTURE pattern
"""
import os
from typing import Optional, Tuple, Dict, Any
import logging
from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, pool, text

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and notification queries using SQLAlchemy"""

    def __init__(self, instance_connection_name: str, dbname: str, user: str, password: str):
        """
        Initialize database manager with SQLAlchemy connection pool

        Args:
            instance_connection_name: Cloud SQL instance connection name (project:region:instance)
            dbname: Database name
            user: Database user
            password: Database password
        """
        self.instance_connection_name = instance_connection_name
        self.dbname = dbname
        self.user = user
        self.password = password

        # Validate credentials
        if not self.password:
            raise RuntimeError("Database password not available. Cannot initialize DatabaseManager.")
        if not all([self.instance_connection_name, self.dbname, self.user]):
            raise RuntimeError("Critical database configuration missing.")

        # Initialize connection pool
        self.connector = None
        self.engine = None
        self._initialize_pool()

        logger.info(f"🗄️ [DATABASE] Initialized with connection pool")
        logger.info(f"   Instance: {self.instance_connection_name}")
        logger.info(f"   Database: {self.dbname}")

    def _get_conn(self):
        """
        Get database connection using Cloud SQL Connector.
        Called by SQLAlchemy when it needs a new connection.

        Returns:
            Database connection object (pg8000 connection)
        """
        conn = self.connector.connect(
            self.instance_connection_name,
            "pg8000",
            user=self.user,
            password=self.password,
            db=self.dbname
        )
        return conn

    def _initialize_pool(self):
        """
        Initialize SQLAlchemy engine with connection pool (NEW_ARCHITECTURE pattern)

        Creates:
        - Cloud SQL Connector instance
        - SQLAlchemy engine with QueuePool
        - Automatic connection health checks and recycling
        """
        try:
            # Initialize Cloud SQL connector
            self.connector = Connector()

            logger.info("🔌 [DATABASE] Initializing Cloud SQL connector with SQLAlchemy...")

            # Create SQLAlchemy engine with connection pool
            self.engine = create_engine(
                "postgresql+pg8000://",
                creator=self._get_conn,
                poolclass=pool.QueuePool,
                pool_size=3,           # Smaller pool for notification service
                max_overflow=2,        # Limited overflow
                pool_timeout=30,       # 30 seconds
                pool_recycle=1800,     # 30 minutes
                pool_pre_ping=True,    # Health check before using connection
                echo=False
            )

            logger.info("✅ [DATABASE] Connection pool initialized (NEW_ARCHITECTURE)")

        except Exception as e:
            logger.error(f"❌ [DATABASE] Failed to initialize pool: {e}", exc_info=True)
            raise

    def get_notification_settings(self, open_channel_id: str) -> Optional[Tuple[bool, Optional[int]]]:
        """
        Get notification settings for a channel (NEW_ARCHITECTURE pattern)

        Args:
            open_channel_id: The open channel ID to look up

        Returns:
            Tuple of (notification_status, notification_id) if found, None otherwise

        Example:
            >>> db.get_notification_settings("-1003268562225")
            (True, 123456789)
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT notification_status, notification_id
                        FROM main_clients_database
                        WHERE open_channel_id = :open_channel_id
                    """),
                    {"open_channel_id": str(open_channel_id)}
                )

                row = result.fetchone()

                if row:
                    notification_status, notification_id = row
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
        Fetch channel details by open_channel_id for notification message formatting (NEW_ARCHITECTURE pattern)

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
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT
                            closed_channel_title,
                            closed_channel_description
                        FROM main_clients_database
                        WHERE open_channel_id = :open_channel_id
                        LIMIT 1
                    """),
                    {"open_channel_id": str(open_channel_id)}
                )

                row = result.fetchone()

                if row:
                    channel_details = {
                        "closed_channel_title": row[0] if row[0] else "Premium Channel",
                        "closed_channel_description": row[1] if row[1] else "Exclusive content"
                    }
                    logger.info(f"✅ [DATABASE] Fetched channel details for {open_channel_id}")
                    return channel_details
                else:
                    logger.warning(f"⚠️ [DATABASE] No channel details found for {open_channel_id}")
                    return None

        except Exception as e:
            logger.error(f"❌ [DATABASE] Error fetching channel details: {e}")
            return None
