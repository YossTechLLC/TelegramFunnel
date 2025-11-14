#!/usr/bin/env python3
"""
DatabaseClient - Handles all database operations for broadcast_manager table
Provides queries for fetching, updating, and tracking broadcasts
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class DatabaseClient:
    """
    Manages database connections and operations for broadcast management.

    Responsibilities:
    - Create and manage database connections
    - Fetch broadcasts due for sending
    - Update broadcast status and statistics
    - Query broadcast information for API responses
    """

    def __init__(self, config):
        """
        Initialize the DatabaseClient.

        Args:
            config: Config instance for fetching credentials
        """
        self.config = config
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

            self._engine = create_engine(
                "postgresql+pg8000://",
                creator=getconn,
                poolclass=NullPool,
            )

            self.logger.info(f"🔌 Database engine configured: {connection_name}/{db_name}")

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

        Returns:
            List of broadcast entries with full channel details
        """
        try:
            self.logger.info("🔍 [DEBUG] fetch_due_broadcasts() called")

            with self.get_connection() as conn:
                self.logger.info("🔍 [DEBUG] Database connection obtained")

                cur = conn.cursor()
                self.logger.info("🔍 [DEBUG] Cursor created")

                query = """
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
                """

                self.logger.info("🔍 [DEBUG] Executing query...")
                cur.execute(query)

                self.logger.info("🔍 [DEBUG] Fetching all rows...")
                rows = cur.fetchall()

                self.logger.info(f"🔍 [DEBUG] Fetched {len(rows)} rows from database")

                # Convert rows to dictionaries
                columns = [desc[0] for desc in cur.description]
                self.logger.info(f"🔍 [DEBUG] Column names: {columns}")

                broadcasts = [dict(zip(columns, row)) for row in rows]

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

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            Broadcast entry dict or None if not found
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                query = """
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
                    WHERE bm.id = %s
                """

                cur.execute(query, (broadcast_id,))
                row = cur.fetchone()

                if row:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
                else:
                    self.logger.warning(f"⚠️ Broadcast not found: {broadcast_id}")
                    return None

        except Exception as e:
            self.logger.error(f"❌ Error fetching broadcast {broadcast_id}: {e}")
            return None

    def update_broadcast_status(self, broadcast_id: str, status: str) -> bool:
        """
        Update broadcast status.

        Args:
            broadcast_id: UUID of the broadcast entry
            status: New status ('pending', 'in_progress', 'completed', 'failed', 'skipped')

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE broadcast_manager
                    SET broadcast_status = %s
                    WHERE id = %s
                """, (status, broadcast_id))

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

        Args:
            broadcast_id: UUID of the broadcast entry
            next_send_time: When to send next broadcast

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE broadcast_manager
                    SET
                        broadcast_status = 'completed',
                        last_sent_time = NOW(),
                        next_send_time = %s,
                        total_broadcasts = total_broadcasts + 1,
                        successful_broadcasts = successful_broadcasts + 1,
                        consecutive_failures = 0,
                        last_error_message = NULL,
                        last_error_time = NULL
                    WHERE id = %s
                """, (next_send_time, broadcast_id))

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

        Args:
            broadcast_id: UUID of the broadcast entry
            error_message: Error description

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE broadcast_manager
                    SET
                        broadcast_status = 'failed',
                        failed_broadcasts = failed_broadcasts + 1,
                        consecutive_failures = consecutive_failures + 1,
                        last_error_message = %s,
                        last_error_time = NOW(),
                        is_active = CASE
                            WHEN consecutive_failures + 1 >= 5 THEN false
                            ELSE is_active
                        END
                    WHERE id = %s
                    RETURNING consecutive_failures, is_active
                """, (error_message, broadcast_id))

                result = cur.fetchone()
                conn.commit()

                if result:
                    failures, is_active = result
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

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            Tuple of (client_id, last_manual_trigger_time) or None
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT client_id, last_manual_trigger_time
                    FROM broadcast_manager
                    WHERE id = %s
                """, (broadcast_id,))

                result = cur.fetchone()
                return result if result else None

        except Exception as e:
            self.logger.error(f"❌ Error fetching manual trigger info: {e}")
            return None

    def queue_manual_broadcast(self, broadcast_id: str) -> bool:
        """
        Queue a broadcast for immediate execution (manual trigger).

        Sets next_send_time = NOW() to trigger on next cron run.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successfully queued, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE broadcast_manager
                    SET
                        next_send_time = NOW(),
                        broadcast_status = 'pending',
                        last_manual_trigger_time = NOW(),
                        manual_trigger_count = manual_trigger_count + 1
                    WHERE id = %s
                    RETURNING id
                """, (broadcast_id,))

                result = cur.fetchone()
                conn.commit()

                if result:
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

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            Dictionary with statistics or None
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
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
                    WHERE id = %s
                """, (broadcast_id,))

                row = cur.fetchone()

                if row:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
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
