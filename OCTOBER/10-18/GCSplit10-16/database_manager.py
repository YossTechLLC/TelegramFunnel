#!/usr/bin/env python
"""
Database Manager for TPS10-16 Payment Splitting Service.
Handles database operations for the split_payout_request table.
Uses Google Cloud SQL Connector (mirroring tph10-16.py pattern).
"""
import os
import random
import string
from google.cloud import secretmanager
from typing import Optional, Dict, Any
from contextlib import contextmanager

# Import Cloud SQL Connector for database functionality
try:
    from google.cloud.sql.connector import Connector
    CLOUD_SQL_AVAILABLE = True
    print("✅ [INFO] Cloud SQL Connector imported successfully")
except ImportError as e:
    print(f"❌ [ERROR] Cloud SQL Connector import failed: {e}")
    CLOUD_SQL_AVAILABLE = False
    Connector = None

class DatabaseManager:
    """
    Manages database connections and operations for TPS10-16 service.
    Uses the same database as the main TelePay application.
    Uses Google Cloud SQL Connector (no connection pooling).
    """

    def __init__(self):
        """Initialize the DatabaseManager."""
        self.db_name = None
        self.db_user = None
        self.db_password = None
        self.connection_name = None

        # Fetch database credentials
        self._initialize_credentials()

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

    def _initialize_credentials(self):
        """Initialize database credentials from Secret Manager."""
        try:
            print(f"🔄 [DATABASE] Initializing database credentials")

            # Fetch database credentials from Secret Manager
            self.db_name = self._fetch_secret("DATABASE_NAME_SECRET", "database name")
            self.db_user = self._fetch_secret("DATABASE_USER_SECRET", "database user")
            self.db_password = self._fetch_secret("DATABASE_PASSWORD_SECRET", "database password")
            self.connection_name = self._fetch_secret("CLOUD_SQL_CONNECTION_NAME", "Cloud SQL connection name")

            if not all([self.db_name, self.db_user, self.db_password, self.connection_name]):
                print(f"❌ [DATABASE] Missing required database credentials")
                print(f"   Database Name: {'✅' if self.db_name else '❌'}")
                print(f"   Database User: {'✅' if self.db_user else '❌'}")
                print(f"   Database Password: {'✅' if self.db_password else '❌'}")
                print(f"   Cloud SQL Connection Name: {'✅' if self.connection_name else '❌'}")
                return

            print(f"✅ [DATABASE] Database credentials initialized")
            print(f"📊 [DATABASE] Database: {self.db_name}")
            print(f"📊 [DATABASE] User: {self.db_user}")
            print(f"☁️ [DATABASE] Connection: {self.connection_name}")

        except Exception as e:
            print(f"❌ [DATABASE] Error initializing credentials: {e}")

    def get_database_connection(self):
        """
        Create and return a database connection using Cloud SQL Connector.
        This mirrors the pattern from tph10-16.py.

        Returns:
            Database connection or None if failed
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [ERROR] Cloud SQL Connector not available")
            return None

        try:
            if not all([self.db_name, self.db_user, self.db_password, self.connection_name]):
                print("❌ [ERROR] Missing database credentials")
                return None

            # Create connection using Cloud SQL Connector
            connector = Connector()
            connection = connector.connect(
                self.connection_name,
                "pg8000",
                user=self.db_user,
                password=self.db_password,
                db=self.db_name
            )
            print("🔗 [DATABASE] ✅ Cloud SQL Connector connection successful!")
            return connection

        except Exception as e:
            print(f"❌ [ERROR] Database connection failed: {e}")
            print(f"💡 [DATABASE] Troubleshooting tips:")
            print(f"   - Verify all DATABASE_*_SECRET environment variables are set")
            print(f"   - Check Secret Manager permissions for the service account")
            print(f"   - Verify CLOUD_SQL_CONNECTION_NAME is correct")
            print(f"   - Ensure Cloud SQL instance is running")
            print(f"   - Grant roles/cloudsql.client to service account")
            return None

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Creates a new connection for each operation and closes it when done.

        Yields:
            Database connection
        """
        connection = None
        try:
            connection = self.get_database_connection()
            if not connection:
                raise Exception("Failed to create database connection")

            yield connection
            connection.commit()
        except Exception as e:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            print(f"❌ [DATABASE] Connection error: {e}")
            raise
        finally:
            if connection:
                try:
                    connection.close()
                except Exception:
                    pass

    def get_network_for_currency(self, to_currency: str) -> Optional[str]:
        """
        Get the network for a given currency from to_currency_to_network table.

        Args:
            to_currency: Target currency (e.g., "LINK", "ETH", "USDT")

        Returns:
            Network name (e.g., "eth", "bsc", "polygon") or None if not found
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [ERROR] Cloud SQL Connector not available - cannot lookup network")
            return None

        conn = None
        cur = None
        try:
            print(f"🔍 [NETWORK_LOOKUP] Looking up network for currency: {to_currency}")

            select_query = """
                SELECT to_network
                FROM to_currency_to_network
                WHERE to_currency = %s
            """

            conn = self.get_database_connection()
            if not conn:
                print(f"❌ [NETWORK_LOOKUP] Could not establish database connection")
                return None

            cur = conn.cursor()
            cur.execute(select_query, (to_currency.upper(),))
            row = cur.fetchone()

            if row:
                network = row[0]
                print(f"✅ [NETWORK_LOOKUP] Found network '{network}' for currency '{to_currency}'")
                return network
            else:
                print(f"❌ [NETWORK_LOOKUP] No network found for currency '{to_currency}'")
                return None

        except Exception as e:
            print(f"❌ [NETWORK_LOOKUP] Error looking up network: {e}")
            return None
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

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
                                   from_amount: float, to_amount: float,
                                   client_wallet_address: str,
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
            to_amount: Amount from ChangeNow estimate response (toAmount field)
            client_wallet_address: Client's wallet address
            refund_address: Refund address (optional, empty string if not provided)
            flow: Exchange flow type (default "standard")
            type_: Exchange type (default "direct")

        Returns:
            Generated unique_id if successful, None otherwise
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [ERROR] Cloud SQL Connector not available - cannot insert record")
            return None

        conn = None
        cur = None
        try:
            print(f"📝 [DB_INSERT] Preparing split payout request insertion")
            print(f"👤 [DB_INSERT] User ID: {user_id}")
            print(f"🏦 [DB_INSERT] Wallet: {client_wallet_address}")
            print(f"💰 [DB_INSERT] From Amount: {from_amount} {from_currency.upper()}")
            print(f"💰 [DB_INSERT] To Amount: {to_amount} {to_currency.upper()}")

            # Generate unique ID
            unique_id = self.generate_unique_id()

            # SQL INSERT statement
            insert_query = """
                INSERT INTO split_payout_request (
                    unique_id, user_id, closed_channel_id,
                    from_currency, to_currency, from_network, to_network,
                    from_amount, to_amount, client_wallet_address, refund_address,
                    flow, type
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
            """

            params = (
                unique_id, user_id, closed_channel_id,
                from_currency.upper(), to_currency.upper(), from_network.upper(), to_network.upper(),
                from_amount, to_amount, client_wallet_address, refund_address,
                flow, type_
            )

            # Execute insertion
            conn = self.get_database_connection()
            if not conn:
                print(f"❌ [DB_INSERT] Could not establish database connection")
                return None

            cur = conn.cursor()
            cur.execute(insert_query, params)
            rows_affected = cur.rowcount

            if rows_affected > 0:
                conn.commit()
                print(f"✅ [DB_INSERT] Successfully inserted split payout request")
                print(f"🆔 [DB_INSERT] Unique ID: {unique_id}")
                return unique_id
            else:
                print(f"❌ [DB_INSERT] No rows affected")
                return None

        except Exception as e:
            # Check if it's an integrity error (duplicate unique_id)
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"❌ [DB_INSERT] Integrity error (possible duplicate unique_id): {e}")
                # Retry with new unique ID
                print(f"🔄 [DB_INSERT] Retrying with new unique ID...")
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                if cur:
                    try:
                        cur.close()
                    except Exception:
                        pass
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                return self.insert_split_payout_request(
                    user_id, closed_channel_id, from_currency, to_currency,
                    from_network, to_network, from_amount, to_amount,
                    client_wallet_address, refund_address, flow, type_
                )
            else:
                print(f"❌ [DB_INSERT] Error inserting split payout request: {e}")
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                return None
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_split_payout_request(self, unique_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a split payout request by unique_id.

        Args:
            unique_id: Unique ID of the request

        Returns:
            Dictionary containing request data or None if not found
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [ERROR] Cloud SQL Connector not available - cannot query record")
            return None

        conn = None
        cur = None
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

            conn = self.get_database_connection()
            if not conn:
                print(f"❌ [DB_QUERY] Could not establish database connection")
                return None

            cur = conn.cursor()
            cur.execute(select_query, (unique_id,))
            row = cur.fetchone()

            if row:
                columns = [desc[0] for desc in cur.description]
                result = dict(zip(columns, row))
                print(f"✅ [DB_QUERY] Found request: {unique_id}")
                return result
            else:
                print(f"❌ [DB_QUERY] Request not found: {unique_id}")
                return None

        except Exception as e:
            print(f"❌ [DB_QUERY] Error fetching split payout request: {e}")
            return None
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def insert_split_payout_que(self, unique_id: str, cn_api_id: str, user_id: int, closed_channel_id: str,
                                from_currency: str, to_currency: str,
                                from_network: str, to_network: str,
                                from_amount: float, to_amount: float,
                                payin_address: str, payout_address: str,
                                refund_address: str = "", flow: str = "standard",
                                type_: str = "direct") -> bool:
        """
        Insert a new record into the split_payout_que table after ChangeNow transaction creation.

        This method is called after create_fixed_rate_transaction API call succeeds.
        It uses the SAME unique_id as the split_payout_request table to maintain consistency.

        Args:
            unique_id: The SAME unique_id from split_payout_request table
            cn_api_id: ChangeNow transaction ID from API response (id field)
            user_id: User ID from webhook
            closed_channel_id: Channel ID from webhook
            from_currency: Source currency (e.g., "eth")
            to_currency: Target currency (e.g., "link")
            from_network: Source network (e.g., "eth")
            to_network: Target network (e.g., "eth")
            from_amount: Amount from ChangeNow API response (fromAmount field)
            to_amount: Amount from ChangeNow API response (toAmount field)
            payin_address: ChangeNow deposit address (payinAddress field)
            payout_address: Client's wallet address (payoutAddress field)
            refund_address: Refund address (refundAddress field, optional)
            flow: Exchange flow type (default "standard")
            type_: Exchange type (default "direct")

        Returns:
            True if successful, False otherwise
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [ERROR] Cloud SQL Connector not available - cannot insert into split_payout_que")
            return False

        conn = None
        cur = None
        try:
            print(f"📝 [DB_INSERT_QUE] Preparing split payout que insertion")
            print(f"🆔 [DB_INSERT_QUE] Unique ID: {unique_id}")
            print(f"🆔 [DB_INSERT_QUE] ChangeNow API ID: {cn_api_id}")
            print(f"👤 [DB_INSERT_QUE] User ID: {user_id}")
            print(f"🏦 [DB_INSERT_QUE] Payin Address: {payin_address}")
            print(f"🏦 [DB_INSERT_QUE] Payout Address: {payout_address}")
            print(f"💰 [DB_INSERT_QUE] From Amount: {from_amount} {from_currency.upper()}")
            print(f"💰 [DB_INSERT_QUE] To Amount: {to_amount} {to_currency.upper()}")

            # SQL INSERT statement for split_payout_que table
            insert_query = """
                INSERT INTO split_payout_que (
                    unique_id, cn_api_id, user_id, closed_channel_id,
                    from_currency, to_currency, from_network, to_network,
                    from_amount, to_amount, payin_address, payout_address, refund_address,
                    flow, type
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s
                )
            """

            params = (
                unique_id, cn_api_id, user_id, closed_channel_id,
                from_currency.upper(), to_currency.upper(), from_network.upper(), to_network.upper(),
                from_amount, to_amount, payin_address, payout_address, refund_address,
                flow, type_
            )

            # Execute insertion
            conn = self.get_database_connection()
            if not conn:
                print(f"❌ [DB_INSERT_QUE] Could not establish database connection")
                return False

            cur = conn.cursor()
            cur.execute(insert_query, params)
            rows_affected = cur.rowcount

            if rows_affected > 0:
                conn.commit()
                print(f"✅ [DB_INSERT_QUE] Successfully inserted into split_payout_que")
                print(f"🆔 [DB_INSERT_QUE] Unique ID: {unique_id}")
                print(f"🔗 [DB_INSERT_QUE] Linked to split_payout_request with same unique_id")
                return True
            else:
                print(f"❌ [DB_INSERT_QUE] No rows affected")
                return False

        except Exception as e:
            print(f"❌ [DB_INSERT_QUE] Error inserting into split_payout_que: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return False
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
