#!/usr/bin/env python
"""
Database Manager for GCRegister10-5 Channel Registration Service.
Handles PostgreSQL connections and data operations.
"""
import psycopg2
from typing import Optional, Dict, Any
from contextlib import contextmanager

class DatabaseManager:
    """
    Manages PostgreSQL database connections and operations for channel registration.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the DatabaseManager.

        Args:
            config: Configuration dictionary containing database credentials
        """
        self.host = config.get('db_host')
        self.port = config.get('db_port', 5432)
        self.dbname = config.get('db_name')
        self.user = config.get('db_user')
        self.password = config.get('db_password')

        # Validate that critical credentials are available
        if not self.password:
            raise RuntimeError("Database password not available. Cannot initialize DatabaseManager.")
        if not self.host or not self.dbname or not self.user:
            raise RuntimeError("Critical database configuration missing.")

        print(f"🔗 [DATABASE] DatabaseManager initialized for {self.dbname}@{self.host}")

    @contextmanager
    def get_connection(self):
        """
        Create and return a database connection using context manager.

        Yields:
            psycopg2 connection object
        """
        conn = None
        try:
            conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            print(f"✅ [DATABASE] Connection established")
            yield conn
        except Exception as e:
            print(f"❌ [DATABASE] Connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def test_connection(self) -> bool:
        """
        Test the database connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    if result and result[0] == 1:
                        print(f"✅ [DATABASE] Connection test successful")
                        return True
            return False
        except Exception as e:
            print(f"❌ [DATABASE] Connection test failed: {e}")
            return False

    def validate_channel_id_unique(self, open_channel_id: str) -> bool:
        """
        Check if the open_channel_id already exists in the database.

        Args:
            open_channel_id: The channel ID to check

        Returns:
            True if channel ID is unique (does not exist), False if it already exists
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    print(f"🔍 [DATABASE] Checking uniqueness for open_channel_id: {open_channel_id}")
                    cur.execute(
                        "SELECT COUNT(*) FROM main_clients_database WHERE open_channel_id = %s",
                        (open_channel_id,)
                    )
                    count = cur.fetchone()[0]

                    if count > 0:
                        print(f"❌ [DATABASE] Channel ID {open_channel_id} already exists")
                        return False
                    else:
                        print(f"✅ [DATABASE] Channel ID {open_channel_id} is unique")
                        return True

        except Exception as e:
            print(f"❌ [DATABASE] Error checking channel ID uniqueness: {e}")
            return False

    def insert_channel_registration(self, data: Dict[str, Any]) -> bool:
        """
        Insert a new channel registration into the main_clients_database table.

        Args:
            data: Dictionary containing all registration data

        Returns:
            True if insertion successful, False otherwise
        """
        conn = None
        try:
            # First check if channel ID is unique
            if not self.validate_channel_id_unique(data['open_channel_id']):
                print(f"❌ [DATABASE] Cannot insert - channel ID already exists")
                return False

            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    print(f"📝 [DATABASE] Inserting new registration for channel: {data['open_channel_id']}")

                    # Prepare the insertion query
                    insert_query = """
                        INSERT INTO main_clients_database
                        (open_channel_id, open_channel_title, open_channel_description,
                         closed_channel_id, closed_channel_title, closed_channel_description,
                         sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                         client_wallet_address, client_payout_currency)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    values = (
                        data['open_channel_id'],
                        data['open_channel_title'],
                        data['open_channel_description'],
                        data['closed_channel_id'],
                        data['closed_channel_title'],
                        data['closed_channel_description'],
                        data['sub_1_price'],
                        data['sub_1_time'],
                        data['sub_2_price'],
                        data['sub_2_time'],
                        data['sub_3_price'],
                        data['sub_3_time'],
                        data['client_wallet_address'],
                        data['client_payout_currency']
                    )

                    # Execute the insertion
                    cur.execute(insert_query, values)
                    conn.commit()

                    print(f"✅ [DATABASE] Successfully inserted registration for channel: {data['open_channel_id']}")
                    print(f"📊 [DATABASE] Details: {data['open_channel_title']} -> {data['closed_channel_title']}")
                    print(f"💰 [DATABASE] Tiers: ${data['sub_1_price']}/{data['sub_1_time']}d, ${data['sub_2_price']}/{data['sub_2_time']}d, ${data['sub_3_price']}/{data['sub_3_time']}d")
                    print(f"🏦 [DATABASE] Wallet: {data['client_wallet_address'][:20]}... ({data['client_payout_currency']})")

                    return True

        except psycopg2.IntegrityError as e:
            if conn:
                conn.rollback()
            print(f"❌ [DATABASE] Integrity error (duplicate or constraint violation): {e}")
            return False
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"❌ [DATABASE] Error inserting registration: {e}")
            return False

    def get_registration_count(self) -> int:
        """
        Get the total number of registered channels.

        Returns:
            Count of registered channels
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM main_clients_database")
                    count = cur.fetchone()[0]
                    print(f"📊 [DATABASE] Total registered channels: {count}")
                    return count
        except Exception as e:
            print(f"❌ [DATABASE] Error getting registration count: {e}")
            return 0
