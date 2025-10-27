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
