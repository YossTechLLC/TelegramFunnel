#!/usr/bin/env python
"""
Database Manager for GCSubscriptionMonitor
Handles PostgreSQL operations using Cloud SQL Connector
"""
from google.cloud.sql.connector import Connector
import sqlalchemy
from datetime import datetime
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations"""

    def __init__(self, instance_connection_name: str, db_name: str,
                 db_user: str, db_password: str):
        """
        Initialize database manager with Cloud SQL Connector.

        Args:
            instance_connection_name: Format "project:region:instance"
            db_name: Database name
            db_user: Database user
            db_password: Database password
        """
        self.instance_connection_name = instance_connection_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password

        logger.info("🔌 Initializing Cloud SQL Connector...")

        self.connector = Connector()
        self.pool = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=self._getconn
        )

        logger.info("✅ Database connection pool initialized")

    def _getconn(self):
        """Create database connection via Cloud SQL Connector"""
        return self.connector.connect(
            self.instance_connection_name,
            "pg8000",
            user=self.db_user,
            password=self.db_password,
            db=self.db_name
        )

    def get_connection(self):
        """Get a database connection from the pool"""
        return self.pool.connect()

    def fetch_expired_subscriptions(self) -> List[Tuple[int, int, str, str]]:
        """
        Fetch all expired subscriptions from database.

        Returns:
            List of tuples: (user_id, private_channel_id, expire_time, expire_date)
        """
        expired_subscriptions = []

        try:
            with self.get_connection() as conn:
                query = sqlalchemy.text("""
                    SELECT user_id, private_channel_id, expire_time, expire_date
                    FROM private_channel_users_database
                    WHERE is_active = true
                        AND expire_time IS NOT NULL
                        AND expire_date IS NOT NULL
                """)

                result = conn.execute(query)
                rows = result.fetchall()

                current_datetime = datetime.now()

                for row in rows:
                    user_id = row[0]
                    private_channel_id = row[1]
                    expire_time_str = row[2]
                    expire_date_str = row[3]

                    try:
                        # Parse expiration time and date
                        if isinstance(expire_date_str, str):
                            expire_date_obj = datetime.strptime(expire_date_str, '%Y-%m-%d').date()
                        else:
                            expire_date_obj = expire_date_str

                        if isinstance(expire_time_str, str):
                            expire_time_obj = datetime.strptime(expire_time_str, '%H:%M:%S').time()
                        else:
                            expire_time_obj = expire_time_str

                        # Combine date and time
                        expire_datetime = datetime.combine(expire_date_obj, expire_time_obj)

                        # Check if subscription has expired
                        if current_datetime > expire_datetime:
                            expired_subscriptions.append((
                                user_id,
                                private_channel_id,
                                str(expire_time_str),
                                str(expire_date_str)
                            ))
                            logger.debug(
                                f"🔍 Found expired subscription: "
                                f"user {user_id}, channel {private_channel_id}, "
                                f"expired at {expire_datetime}"
                            )

                    except Exception as e:
                        logger.error(f"❌ Error parsing expiration data for user {user_id}: {e}")
                        continue

                logger.info(f"📊 Found {len(expired_subscriptions)} expired subscriptions")

        except Exception as e:
            logger.error(f"❌ Database error fetching expired subscriptions: {e}", exc_info=True)

        return expired_subscriptions

    def deactivate_subscription(self, user_id: int, private_channel_id: int) -> bool:
        """
        Mark subscription as inactive in database.

        Args:
            user_id: User's Telegram ID
            private_channel_id: Private channel ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                query = sqlalchemy.text("""
                    UPDATE private_channel_users_database
                    SET is_active = false
                    WHERE user_id = :user_id
                        AND private_channel_id = :private_channel_id
                        AND is_active = true
                """)

                result = conn.execute(
                    query,
                    {"user_id": user_id, "private_channel_id": private_channel_id}
                )
                conn.commit()

                rows_affected = result.rowcount

                if rows_affected > 0:
                    logger.info(
                        f"📝 Marked subscription as inactive: "
                        f"user {user_id}, channel {private_channel_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"⚠️ No active subscription found to deactivate: "
                        f"user {user_id}, channel {private_channel_id}"
                    )
                    return False

        except Exception as e:
            logger.error(
                f"❌ Database error deactivating subscription "
                f"for user {user_id}, channel {private_channel_id}: {e}",
                exc_info=True
            )
            return False

    def close(self):
        """Close database connections"""
        self.connector.close()
        logger.info("🔌 Database connections closed")
