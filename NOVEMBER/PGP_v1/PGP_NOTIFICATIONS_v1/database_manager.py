#!/usr/bin/env python
"""
🗄️ Database Manager for PGP_NOTIFICATIONS_v1
Handles PostgreSQL connections and notification queries using NEW_ARCHITECTURE pattern
Inherits from BaseDatabaseManager for common connection pooling
"""
import os
from typing import Optional, Tuple, Dict, Any
from decimal import Decimal
import logging
from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, pool, text
from PGP_COMMON.database import BaseDatabaseManager

logger = logging.getLogger(__name__)


class DatabaseManager(BaseDatabaseManager):
    """
    Manages database connections and notification queries using SQLAlchemy.
    Inherits common connection pooling from BaseDatabaseManager.
    """

    def __init__(self, instance_connection_name: str, dbname: str, user: str, password: str):
        """
        Initialize database manager with SQLAlchemy connection pool.

        Args:
            instance_connection_name: Cloud SQL instance connection name (project:region:instance)
            dbname: Database name
            user: Database user
            password: Database password
        """
        # Call base class constructor
        super().__init__(
            instance_connection_name=instance_connection_name,
            dbname=dbname,
            user=user,
            password=password,
            service_name="PGP_NOTIFICATIONS_v1"
        )

        # Validate credentials
        if not password:
            raise RuntimeError("Database password not available. Cannot initialize DatabaseManager.")
        if not all([instance_connection_name, dbname, user]):
            raise RuntimeError("Critical database configuration missing.")

        # Initialize connection pool with notification service settings
        self.connector = None
        self.engine = None
        self._initialize_pool()

        logger.info(f"🗄️ [DATABASE] Initialized with connection pool")
        logger.info(f"   Instance: {instance_connection_name}")
        logger.info(f"   Database: {dbname}")

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
        Initialize SQLAlchemy engine with connection pool (NEW_ARCHITECTURE pattern).

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

    # ========================================================================
    # Service-Specific Methods
    # ========================================================================

    def get_notification_settings(self, open_channel_id: str) -> Optional[Tuple[bool, Optional[int]]]:
        """
        Get notification settings for a channel (NEW_ARCHITECTURE pattern).

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
        Fetch channel details by open_channel_id for notification message formatting (NEW_ARCHITECTURE pattern).

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

    def get_payout_configuration(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get payout configuration for notification message (NEW_ARCHITECTURE pattern).

        Args:
            open_channel_id: The open channel ID to fetch payout configuration for

        Returns:
            Dict containing payout configuration or None if not found:
            {
                "payout_strategy": str,        # "instant" or "threshold"
                "wallet_address": str,         # e.g., "0x249A83b498acE1177920566CE83CADA0A56F69D8"
                "payout_currency": str,        # e.g., "SHIB", "USDT", "ETH"
                "payout_network": str,         # e.g., "ETH", "TRX", "BSC"
                "threshold_usd": Decimal       # e.g., 100.00 (NULL for instant mode)
            }

        Example:
            >>> db.get_payout_configuration("-1003202734748")
            {
                "payout_strategy": "instant",
                "wallet_address": "0x249A83b498acE1177920566CE83CADA0A56F69D8",
                "payout_currency": "SHIB",
                "payout_network": "ETH",
                "threshold_usd": None
            }
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT
                            payout_strategy,
                            client_wallet_address,
                            client_payout_currency::text,
                            client_payout_network::text,
                            payout_threshold_usd
                        FROM main_clients_database
                        WHERE open_channel_id = :open_channel_id
                    """),
                    {"open_channel_id": str(open_channel_id)}
                )

                row = result.fetchone()

                if row:
                    payout_config = {
                        "payout_strategy": row[0] if row[0] else "instant",
                        "wallet_address": row[1],
                        "payout_currency": row[2],
                        "payout_network": row[3],
                        "threshold_usd": row[4]  # Can be None for instant mode
                    }
                    logger.info(
                        f"✅ [DATABASE] Payout config for {open_channel_id}: "
                        f"strategy={payout_config['payout_strategy']}, "
                        f"currency={payout_config['payout_currency']}, "
                        f"network={payout_config['payout_network']}"
                    )
                    return payout_config
                else:
                    logger.warning(f"⚠️ [DATABASE] No payout configuration found for {open_channel_id}")
                    return None

        except Exception as e:
            logger.error(f"❌ [DATABASE] Error fetching payout configuration: {e}")
            return None

    def get_threshold_progress(self, open_channel_id: str) -> Optional[Decimal]:
        """
        Get current accumulated amount for threshold payout mode (NEW_ARCHITECTURE pattern).

        Calculates the sum of all unpaid payment amounts for a client channel.
        Used to display live progress towards payout threshold.

        Args:
            open_channel_id: The open channel ID (client_id in payout_accumulation)

        Returns:
            Decimal: Total accumulated USD not yet paid out, or None if query fails
            Returns Decimal('0.00') if no unpaid payments exist

        Example:
            >>> db.get_threshold_progress("-1003202734748")
            Decimal('47.50')
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT COALESCE(SUM(payment_amount_usd), 0) as current_accumulated
                        FROM payout_accumulation
                        WHERE client_id = :open_channel_id
                          AND is_paid_out = FALSE
                    """),
                    {"open_channel_id": str(open_channel_id)}
                )

                row = result.fetchone()

                if row:
                    accumulated = row[0] if row[0] is not None else Decimal('0.00')
                    logger.info(
                        f"✅ [DATABASE] Threshold progress for {open_channel_id}: "
                        f"${accumulated} accumulated"
                    )
                    return accumulated
                else:
                    # Should not happen due to COALESCE, but handle defensively
                    logger.info(f"✅ [DATABASE] No accumulated payments for {open_channel_id}")
                    return Decimal('0.00')

        except Exception as e:
            logger.error(f"❌ [DATABASE] Error fetching threshold progress: {e}")
            return None
