#!/usr/bin/env python3
"""
DatabaseManager - Handles all database operations for broadcast_manager table
Provides queries for fetching, updating, and tracking broadcasts
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool  # ✅ H-06 FIX: Use QueuePool for connection reuse
from config_manager import ConfigManager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and operations for broadcast management.

    Responsibilities:
    - Create and manage database connections
    - Fetch broadcasts due for sending
    - Update broadcast status and statistics
    - Query broadcast information for API responses
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the DatabaseManager.

        Args:
            config_manager: ConfigManager instance for fetching credentials
        """
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        self.connector = Connector()
        self._engine = None

    def _get_engine(self):
        """
        Get or create SQLAlchemy engine with Cloud SQL Connector.

        Returns:
            SQLAlchemy Engine instance
        """
        if self._engine is None:
            connection_name = self.config.get_cloud_sql_connection_name()
            db_name = self.config.get_database_name()
            db_user = self.config.get_database_user()
            db_password = self.config.get_database_password()

            def getconn():
                conn = self.connector.connect(
                    connection_name,
                    "pg8000",
                    user=db_user,
                    password=db_password,
                    db=db_name
                )
                return conn

            # ✅ H-06 FIX: Use QueuePool for connection pooling (prevents connection exhaustion)
            self._engine = create_engine(
                "postgresql+pg8000://",
                creator=getconn,

                # ✅ CONNECTION POOLING CONFIGURATION
                poolclass=QueuePool,        # Maintains pool of reusable connections
                pool_size=5,                # Keep 5 persistent connections
                max_overflow=10,            # Allow up to 15 total (5 + 10 burst)
                pool_timeout=30,            # Wait max 30s for connection
                pool_recycle=1800,          # Recycle connections every 30 min (Cloud SQL timeout)
                pool_pre_ping=True,         # Test connection before use (detect stale)

                # Disable SQL echo in production
                echo=False
            )

            self.logger.info(f"🔌 [H-06 FIX] Database engine configured: {connection_name}/{db_name}")
            self.logger.info(f"   ✅ Connection pool: size=5, max_overflow=10, timeout=30s")
            self.logger.info(f"   ✅ Pool settings: recycle=1800s, pre_ping=True")

        return self._engine

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.

        Yields:
            Database connection object (pg8000 via SQLAlchemy)

        Example:
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT ...")
        """
        engine = self._get_engine()
        conn = engine.raw_connection()
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            self.logger.error(f"❌ Database error: {e}")
            raise
        finally:
            conn.close()

    def fetch_due_broadcasts(self) -> List[Dict[str, Any]]:
        """
        Fetch all broadcast entries that are due to be sent.

        A broadcast is "due" if:
        - is_active = true
        - broadcast_status = 'pending'
        - next_send_time <= NOW()
        - consecutive_failures < 5

        Also joins with main_clients_database to get channel details.

        🆕 NEW_ARCHITECTURE: Uses SQLAlchemy text() for safe query execution.

        Returns:
            List of broadcast entries with full channel details
        """
        try:
            self.logger.info("🔍 [DEBUG] fetch_due_broadcasts() called")

            engine = self._get_engine()
            with engine.connect() as conn:
                self.logger.info("🔍 [DEBUG] Database connection obtained")

                query = text("""
                    SELECT
                        bm.id,
                        bm.client_id,
                        bm.open_channel_id,
                        bm.closed_channel_id,
                        bm.last_sent_time,
                        bm.next_send_time,
                        bm.broadcast_status,
                        bm.consecutive_failures,
                        bm.last_open_message_id,
                        bm.last_closed_message_id,
                        mc.open_channel_title,
                        mc.open_channel_description,
                        mc.closed_channel_title,
                        mc.closed_channel_description,
                        mc.closed_channel_donation_message,
                        mc.sub_1_price,
                        mc.sub_1_time,
                        mc.sub_2_price,
                        mc.sub_2_time,
                        mc.sub_3_price,
                        mc.sub_3_time
                    FROM broadcast_manager bm
                    INNER JOIN main_clients_database mc
                        ON bm.open_channel_id = mc.open_channel_id
                    WHERE bm.is_active = true
                        AND bm.broadcast_status = 'pending'
                        AND bm.next_send_time <= NOW()
                        AND bm.consecutive_failures < 5
                    ORDER BY bm.next_send_time ASC
                """)

                self.logger.info("🔍 [DEBUG] Executing query...")
                result = conn.execute(query)

                self.logger.info("🔍 [DEBUG] Fetching all rows...")
                rows = result.fetchall()

                self.logger.info(f"🔍 [DEBUG] Fetched {len(rows)} rows from database")

                # Convert rows to dictionaries
                columns = result.keys()
                self.logger.info(f"🔍 [DEBUG] Column names: {list(columns)}")

                broadcasts = [dict(row._mapping) for row in rows]

                self.logger.info(f"📋 Found {len(broadcasts)} broadcasts due for sending")

                if broadcasts:
                    for i, b in enumerate(broadcasts[:3], 1):  # Log first 3
                        self.logger.info(
                            f"   Broadcast {i}: id={b['id']}, "
                            f"open_channel={b['open_channel_id']}, "
                            f"closed_channel={b['closed_channel_id']}"
                        )

                return broadcasts

        except Exception as e:
            self.logger.error(f"❌ Error fetching due broadcasts: {e}", exc_info=True)
            return []

    def fetch_broadcast_by_id(self, broadcast_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single broadcast entry by ID.

        🆕 NEW_ARCHITECTURE: Uses SQLAlchemy text() with named parameters.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            Broadcast entry dict or None if not found
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT
                        bm.*,
                        mc.open_channel_title,
                        mc.open_channel_description,
                        mc.closed_channel_title,
                        mc.closed_channel_description,
                        mc.closed_channel_donation_message,
                        mc.sub_1_price,
                        mc.sub_1_time,
                        mc.sub_2_price,
                        mc.sub_2_time,
                        mc.sub_3_price,
                        mc.sub_3_time
                    FROM broadcast_manager bm
                    LEFT JOIN main_clients_database mc
                        ON bm.open_channel_id = mc.open_channel_id
                    WHERE bm.id = :broadcast_id
                """)

                result = conn.execute(query, {"broadcast_id": broadcast_id})
                row = result.fetchone()

                if row:
                    return dict(row._mapping)
                else:
                    self.logger.warning(f"⚠️ Broadcast not found: {broadcast_id}")
                    return None

        except Exception as e:
            self.logger.error(f"❌ Error fetching broadcast {broadcast_id}: {e}")
            return None

    def update_broadcast_status(self, broadcast_id: str, status: str) -> bool:
        """
        Update broadcast status.

        🆕 NEW_ARCHITECTURE: Uses SQLAlchemy text() with named parameters.

        Args:
            broadcast_id: UUID of the broadcast entry
            status: New status ('pending', 'in_progress', 'completed', 'failed', 'skipped')

        Returns:
            True if successful, False otherwise
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    UPDATE broadcast_manager
                    SET broadcast_status = :status
                    WHERE id = :broadcast_id
                """)

                conn.execute(query, {"status": status, "broadcast_id": broadcast_id})
                conn.commit()

                self.logger.debug(f"📝 Updated status: {broadcast_id} → {status}")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error updating status: {e}")
            return False

    def update_broadcast_success(
        self,
        broadcast_id: str,
        next_send_time: datetime
    ) -> bool:
        """
        Mark broadcast as successfully completed.

        Updates:
        - broadcast_status = 'completed'
        - last_sent_time = NOW()
        - next_send_time = provided value
        - total_broadcasts += 1
        - successful_broadcasts += 1
        - consecutive_failures = 0
        - last_error_message = NULL

        🆕 NEW_ARCHITECTURE: Uses SQLAlchemy text() with named parameters.

        Args:
            broadcast_id: UUID of the broadcast entry
            next_send_time: When to send next broadcast

        Returns:
            True if successful, False otherwise
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    UPDATE broadcast_manager
                    SET
                        broadcast_status = 'completed',
                        last_sent_time = NOW(),
                        next_send_time = :next_send_time,
                        total_broadcasts = total_broadcasts + 1,
                        successful_broadcasts = successful_broadcasts + 1,
                        consecutive_failures = 0,
                        last_error_message = NULL,
                        last_error_time = NULL
                    WHERE id = :broadcast_id
                """)

                conn.execute(query, {
                    "next_send_time": next_send_time,
                    "broadcast_id": broadcast_id
                })
                conn.commit()

                self.logger.info(f"✅ Marked success: {broadcast_id}")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error marking success: {e}")
            return False

    def update_broadcast_failure(self, broadcast_id: str, error_message: str) -> bool:
        """
        Mark broadcast as failed.

        Updates:
        - broadcast_status = 'failed'
        - failed_broadcasts += 1
        - consecutive_failures += 1
        - last_error_message = error_message
        - last_error_time = NOW()
        - is_active = false (if consecutive_failures >= 5)

        🆕 NEW_ARCHITECTURE: Uses SQLAlchemy text() with named parameters.

        Args:
            broadcast_id: UUID of the broadcast entry
            error_message: Error description

        Returns:
            True if successful, False otherwise
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    UPDATE broadcast_manager
                    SET
                        broadcast_status = 'failed',
                        failed_broadcasts = failed_broadcasts + 1,
                        consecutive_failures = consecutive_failures + 1,
                        last_error_message = :error_message,
                        last_error_time = NOW(),
                        is_active = CASE
                            WHEN consecutive_failures + 1 >= 5 THEN false
                            ELSE is_active
                        END
                    WHERE id = :broadcast_id
                    RETURNING consecutive_failures, is_active
                """)

                result = conn.execute(query, {
                    "error_message": error_message,
                    "broadcast_id": broadcast_id
                })
                row = result.fetchone()
                conn.commit()

                if row:
                    failures, is_active = row
                    if not is_active:
                        self.logger.warning(
                            f"⚠️ Broadcast {broadcast_id} deactivated after {failures} consecutive failures"
                        )
                    else:
                        self.logger.error(
                            f"❌ Marked failure: {broadcast_id} (consecutive: {failures})"
                        )

                return True

        except Exception as e:
            self.logger.error(f"❌ Error marking failure: {e}")
            return False

    def get_manual_trigger_info(self, broadcast_id: str) -> Optional[Tuple[str, Optional[datetime]]]:
        """
        Get last manual trigger time for rate limiting.

        🆕 NEW_ARCHITECTURE: Uses SQLAlchemy text() with named parameters.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            Tuple of (client_id, last_manual_trigger_time) or None
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT client_id, last_manual_trigger_time
                    FROM broadcast_manager
                    WHERE id = :broadcast_id
                """)

                result = conn.execute(query, {"broadcast_id": broadcast_id})
                row = result.fetchone()

                return tuple(row) if row else None

        except Exception as e:
            self.logger.error(f"❌ Error fetching manual trigger info: {e}")
            return None

    def queue_manual_broadcast(self, broadcast_id: str) -> bool:
        """
        Queue a broadcast for immediate execution (manual trigger).

        Sets next_send_time = NOW() to trigger on next cron run.

        🆕 NEW_ARCHITECTURE: Uses SQLAlchemy text() with named parameters.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successfully queued, False otherwise
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    UPDATE broadcast_manager
                    SET
                        next_send_time = NOW(),
                        broadcast_status = 'pending',
                        last_manual_trigger_time = NOW(),
                        manual_trigger_count = manual_trigger_count + 1
                    WHERE id = :broadcast_id
                    RETURNING id
                """)

                result = conn.execute(query, {"broadcast_id": broadcast_id})
                row = result.fetchone()
                conn.commit()

                if row:
                    self.logger.info(f"✅ Queued manual broadcast: {broadcast_id}")
                    return True
                else:
                    self.logger.warning(f"⚠️ Broadcast not found: {broadcast_id}")
                    return False

        except Exception as e:
            self.logger.error(f"❌ Error queuing manual broadcast: {e}")
            return False

    def get_broadcast_statistics(self, broadcast_id: str) -> Optional[Dict[str, Any]]:
        """
        Get broadcast statistics for API responses.

        🆕 NEW_ARCHITECTURE: Uses SQLAlchemy text() with named parameters.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            Dictionary with statistics or None
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                query = text("""
                    SELECT
                        id,
                        broadcast_status,
                        last_sent_time,
                        next_send_time,
                        total_broadcasts,
                        successful_broadcasts,
                        failed_broadcasts,
                        consecutive_failures,
                        last_error_message,
                        last_error_time,
                        is_active,
                        manual_trigger_count
                    FROM broadcast_manager
                    WHERE id = :broadcast_id
                """)

                result = conn.execute(query, {"broadcast_id": broadcast_id})
                row = result.fetchone()

                if row:
                    return dict(row._mapping)
                else:
                    return None

        except Exception as e:
            self.logger.error(f"❌ Error fetching statistics: {e}")
            return None

    def close(self):
        """Close the Cloud SQL connector (for cleanup)."""
        if self.connector:
            self.connector.close()
            self.logger.info("🔌 Database connector closed")
