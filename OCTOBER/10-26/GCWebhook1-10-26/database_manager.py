#!/usr/bin/env python
"""
Database Manager for GCWebhook1-10-26 (Payment Processor Service).
Handles database connections and operations for private_channel_users_database table.
"""
from datetime import datetime
from typing import Optional
from google.cloud.sql.connector import Connector


class DatabaseManager:
    """
    Manages database connections and operations for GCWebhook1-10-26.
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
        self.instance_connection_name = instance_connection_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.connector = Connector()

        print(f"🗄️ [DATABASE] DatabaseManager initialized")
        print(f"📊 [DATABASE] Instance: {instance_connection_name}")
        print(f"📊 [DATABASE] Database: {db_name}")

    def get_connection(self):
        """
        Create and return a database connection using Cloud SQL Connector.

        Returns:
            Database connection object or None if failed
        """
        try:
            connection = self.connector.connect(
                self.instance_connection_name,
                "pg8000",
                user=self.db_user,
                password=self.db_password,
                db=self.db_name
            )
            print(f"🔗 [DATABASE] Connection established successfully")
            return connection

        except Exception as e:
            print(f"❌ [DATABASE] Connection failed: {e}")
            return None

    def get_current_timestamp(self) -> str:
        """
        Get current time in PostgreSQL time format.

        Returns:
            String representation of current time (e.g., '22:55:30')
        """
        now = datetime.now()
        return now.strftime('%H:%M:%S')

    def get_current_datestamp(self) -> str:
        """
        Get current date in PostgreSQL date format.

        Returns:
            String representation of current date (e.g., '2025-06-20')
        """
        now = datetime.now()
        return now.strftime('%Y-%m-%d')

    def record_private_channel_user(
        self,
        user_id: int,
        private_channel_id: int,
        sub_time: int,
        sub_price: str,
        expire_time: str,
        expire_date: str,
        is_active: bool = True
    ) -> bool:
        """
        Record a user's subscription in the private_channel_users_database table.

        Args:
            user_id: The user's Telegram ID
            private_channel_id: The private channel ID (closed channel ID)
            sub_time: Subscription time in days
            sub_price: Subscription price as string (e.g., "15.00")
            expire_time: Expiration time in HH:MM:SS format
            expire_date: Expiration date in YYYY-MM-DD format
            is_active: Whether the subscription is active (default: True)

        Returns:
            True if successful, False otherwise
        """
        # Get current timestamp and datestamp for PostgreSQL
        current_timestamp = self.get_current_timestamp()
        current_datestamp = self.get_current_datestamp()

        print(f"📝 [DATABASE] Recording subscription")
        print(f"👤 [DATABASE] User: {user_id}, Channel: {private_channel_id}")
        print(f"💰 [DATABASE] Price: ${sub_price}, Duration: {sub_time} days")
        print(f"⏰ [DATABASE] Expires: {expire_time} on {expire_date}")

        conn = None
        cur = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return False

            cur = conn.cursor()

            # Update existing record or insert new record for user/channel combination
            update_query = """
                UPDATE private_channel_users_database
                SET sub_time = %s, sub_price = %s, timestamp = %s, datestamp = %s, is_active = %s,
                    expire_time = %s, expire_date = %s
                WHERE user_id = %s AND private_channel_id = %s
            """
            update_params = (
                sub_time, sub_price, current_timestamp, current_datestamp, is_active,
                expire_time, expire_date, user_id, private_channel_id
            )
            cur.execute(update_query, update_params)
            rows_affected = cur.rowcount

            if rows_affected == 0:
                # No existing record found, insert new record
                print(f"📝 [DATABASE] No existing record found, inserting new")
                insert_query = """
                    INSERT INTO private_channel_users_database
                    (private_channel_id, user_id, sub_time, sub_price, timestamp, datestamp,
                     expire_time, expire_date, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                insert_params = (
                    private_channel_id, user_id, sub_time, sub_price, current_timestamp,
                    current_datestamp, expire_time, expire_date, is_active
                )
                cur.execute(insert_query, insert_params)
                operation = "inserted"
            else:
                operation = "updated"
                print(f"✅ [DATABASE] Updated {rows_affected} existing record(s)")

            # Commit the transaction
            conn.commit()
            print(f"✅ [DATABASE] Successfully {operation} subscription record")
            print(f"🎉 [DATABASE] User {user_id} recorded for channel {private_channel_id}")
            return True

        except Exception as e:
            # Rollback transaction on error
            if conn:
                try:
                    conn.rollback()
                    print(f"🔄 [DATABASE] Transaction rolled back")
                except Exception:
                    pass

            print(f"❌ [DATABASE] Error recording subscription: {e}")
            return False

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def get_payout_strategy(self, closed_channel_id: int) -> tuple:
        """
        Get payout strategy and threshold for a client channel.

        Args:
            closed_channel_id: The closed (private) channel ID

        Returns:
            Tuple of (payout_strategy, payout_threshold_usd) or ('instant', 0) if not found
        """
        conn = None
        cur = None
        try:
            print(f"🔍 [DATABASE] Fetching payout strategy for closed channel {closed_channel_id}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return ('instant', 0)  # Default to instant

            cur = conn.cursor()

            # Query for payout strategy and threshold by closed_channel_id
            query = """
                SELECT payout_strategy, payout_threshold_usd
                FROM main_clients_database
                WHERE closed_channel_id = %s
            """
            cur.execute(query, (str(closed_channel_id),))
            result = cur.fetchone()

            if result:
                strategy = result[0] or 'instant'
                threshold = float(result[1]) if result[1] else 0
                print(f"✅ [DATABASE] Found client by closed_channel_id: strategy={strategy}, threshold=${threshold}")
                return (strategy, threshold)
            else:
                print(f"⚠️ [DATABASE] No client found for closed_channel_id {closed_channel_id}, defaulting to instant")
                return ('instant', 0)

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching payout strategy: {e}")
            return ('instant', 0)  # Default to instant on error

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def get_subscription_id(self, user_id: int, closed_channel_id: int) -> int:
        """
        Get subscription ID for a user/channel combination.

        Args:
            user_id: User's Telegram ID
            closed_channel_id: The closed (private) channel ID

        Returns:
            Subscription ID or 0 if not found
        """
        conn = None
        cur = None
        try:
            print(f"🔍 [DATABASE] Fetching subscription ID for user {user_id}, channel {closed_channel_id}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return 0

            cur = conn.cursor()

            # Query for subscription ID
            query = """
                SELECT id
                FROM private_channel_users_database
                WHERE user_id = %s AND private_channel_id = %s
                ORDER BY id DESC
                LIMIT 1
            """
            cur.execute(query, (user_id, closed_channel_id))
            result = cur.fetchone()

            if result:
                subscription_id = result[0]
                print(f"✅ [DATABASE] Found subscription ID: {subscription_id}")
                return subscription_id
            else:
                print(f"⚠️ [DATABASE] No subscription found")
                return 0

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching subscription ID: {e}")
            return 0

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")
