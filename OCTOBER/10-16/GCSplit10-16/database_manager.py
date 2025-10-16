#!/usr/bin/env python
"""
Database Manager for TPS10-16 Payment Splitting Service.
Handles database operations for the split_payout_request table.
"""
import os
import random
import string
import psycopg2
from psycopg2 import pool
from google.cloud import secretmanager
from typing import Optional, Dict, Any
from contextlib import contextmanager

class DatabaseManager:
    """
    Manages database connections and operations for TPS10-16 service.
    Uses the same database as the main TelePay application.
    """

    def __init__(self):
        """Initialize the DatabaseManager with connection pooling."""
        self.connection_pool = None
        self.db_host = None
        self.db_name = None
        self.db_user = None
        self.db_password = None

        # Initialize database connection
        self._initialize_database()

    def _fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
        """
        Fetch a secret from Google Cloud Secret Manager.

        Args:
            secret_name_env: Environment variable containing the secret path
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv(secret_name_env)
            if not secret_path:
                print(f"❌ [DB_CONFIG] Environment variable {secret_name_env} is not set")
                return None

            print(f"🔐 [DB_CONFIG] Fetching {description or secret_name_env}")
            response = client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")

            print(f"✅ [DB_CONFIG] Successfully fetched {description or secret_name_env}")
            return secret_value

        except Exception as e:
            print(f"❌ [DB_CONFIG] Error fetching {description or secret_name_env}: {e}")
            return None

    def _initialize_database(self):
        """Initialize database connection pool."""
        try:
            print(f"🔄 [DATABASE] Initializing database connection")

            # Fetch database credentials from Secret Manager
            # Using the same credentials as main TelePay application
            self.db_host = self._fetch_secret("DATABASE_HOST_SECRET", "database host") or "127.0.0.1"
            self.db_name = self._fetch_secret("DATABASE_NAME_SECRET", "database name")
            self.db_user = self._fetch_secret("DATABASE_USER_SECRET", "database user")
            self.db_password = self._fetch_secret("DATABASE_PASSWORD_SECRET", "database password")

            if not all([self.db_name, self.db_user, self.db_password]):
                print(f"❌ [DATABASE] Missing required database credentials")
                return

            # Create connection pool
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,  # min and max connections
                host=self.db_host,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
                port=5432
            )

            print(f"✅ [DATABASE] Database connection pool initialized")
            print(f"📊 [DATABASE] Host: {self.db_host}")
            print(f"📊 [DATABASE] Database: {self.db_name}")

        except Exception as e:
            print(f"❌ [DATABASE] Error initializing database: {e}")
            self.connection_pool = None

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.

        Yields:
            Database connection from pool
        """
        connection = None
        try:
            if not self.connection_pool:
                raise Exception("Database connection pool not initialized")

            connection = self.connection_pool.getconn()
            yield connection
            connection.commit()
        except Exception as e:
            if connection:
                connection.rollback()
            print(f"❌ [DATABASE] Connection error: {e}")
            raise
        finally:
            if connection:
                self.connection_pool.putconn(connection)

    def generate_unique_id(self) -> str:
        """
        Generate a unique 16-digit alphanumeric ID for split_payout_request.

        Returns:
            16-character unique ID string
        """
        # Generate a 16-digit random string using uppercase letters and digits
        # This provides high entropy: 36^16 = 7.9 x 10^24 possible combinations
        characters = string.ascii_uppercase + string.digits
        unique_id = ''.join(random.choices(characters, k=16))

        print(f"🔑 [UNIQUE_ID] Generated: {unique_id}")
        return unique_id

    def insert_split_payout_request(self, user_id: int, closed_channel_id: str,
                                   from_currency: str, to_currency: str,
                                   from_network: str, to_network: str,
                                   from_amount: float, client_wallet_address: str,
                                   refund_address: str = "", flow: str = "standard",
                                   type_: str = "direct") -> Optional[str]:
        """
        Insert a new record into the split_payout_request table.

        Args:
            user_id: User ID from webhook
            closed_channel_id: Channel ID from webhook
            from_currency: Source currency (e.g., "usdt")
            to_currency: Target currency (e.g., "eth")
            from_network: Source network (e.g., "eth")
            to_network: Target network (e.g., "eth")
            from_amount: Amount from ChangeNow estimate response (fromAmount field)
            client_wallet_address: Client's wallet address
            refund_address: Refund address (optional, empty string if not provided)
            flow: Exchange flow type (default "standard")
            type_: Exchange type (default "direct")

        Returns:
            Generated unique_id if successful, None otherwise
        """
        try:
            print(f"📝 [DB_INSERT] Preparing split payout request insertion")
            print(f"👤 [DB_INSERT] User ID: {user_id}")
            print(f"🏦 [DB_INSERT] Wallet: {client_wallet_address}")
            print(f"💰 [DB_INSERT] Amount: {from_amount} {from_currency.upper()}")

            # Generate unique ID
            unique_id = self.generate_unique_id()

            # SQL INSERT statement
            insert_query = """
                INSERT INTO split_payout_request (
                    unique_id, user_id, closed_channel_id,
                    from_currency, to_currency, from_network, to_network,
                    from_amount, client_wallet_address, refund_address,
                    flow, type
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
            """

            params = (
                unique_id, user_id, closed_channel_id,
                from_currency.lower(), to_currency.lower(), from_network.lower(), to_network.lower(),
                from_amount, client_wallet_address, refund_address,
                flow, type_
            )

            # Execute insertion
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(insert_query, params)
                    rows_affected = cursor.rowcount

                    if rows_affected > 0:
                        print(f"✅ [DB_INSERT] Successfully inserted split payout request")
                        print(f"🆔 [DB_INSERT] Unique ID: {unique_id}")
                        return unique_id
                    else:
                        print(f"❌ [DB_INSERT] No rows affected")
                        return None

        except psycopg2.IntegrityError as e:
            print(f"❌ [DB_INSERT] Integrity error (possible duplicate unique_id): {e}")
            # Retry with new unique ID
            print(f"🔄 [DB_INSERT] Retrying with new unique ID...")
            return self.insert_split_payout_request(
                user_id, closed_channel_id, from_currency, to_currency,
                from_network, to_network, from_amount, client_wallet_address,
                refund_address, flow, type_
            )
        except Exception as e:
            print(f"❌ [DB_INSERT] Error inserting split payout request: {e}")
            return None

    def get_split_payout_request(self, unique_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a split payout request by unique_id.

        Args:
            unique_id: Unique ID of the request

        Returns:
            Dictionary containing request data or None if not found
        """
        try:
            print(f"🔍 [DB_QUERY] Fetching split payout request: {unique_id}")

            select_query = """
                SELECT
                    unique_id, user_id, closed_channel_id,
                    from_currency, to_currency, from_network, to_network,
                    from_amount, client_wallet_address, refund_address,
                    flow, type, created_at, updated_at
                FROM split_payout_request
                WHERE unique_id = %s
            """

            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(select_query, (unique_id,))
                    row = cursor.fetchone()

                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        result = dict(zip(columns, row))
                        print(f"✅ [DB_QUERY] Found request: {unique_id}")
                        return result
                    else:
                        print(f"❌ [DB_QUERY] Request not found: {unique_id}")
                        return None

        except Exception as e:
            print(f"❌ [DB_QUERY] Error fetching split payout request: {e}")
            return None

    def close(self):
        """Close all database connections in the pool."""
        if self.connection_pool:
            self.connection_pool.closeall()
            print(f"✅ [DATABASE] Connection pool closed")
