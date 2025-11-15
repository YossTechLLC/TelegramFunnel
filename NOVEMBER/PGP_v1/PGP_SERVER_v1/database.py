#!/usr/bin/env python
import psycopg2
import os
from typing import Optional, Tuple, List, Dict, Any
from google.cloud import secretmanager
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# 🆕 NEW_ARCHITECTURE: Import ConnectionPool
from models import init_connection_pool

def fetch_database_host() -> str:
    """Fetch database host from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_HOST_SECRET")
        if not secret_path:
            raise ValueError("Environment variable DATABASE_HOST_SECRET is not set.")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_HOST_SECRET: {e}")
        raise

def fetch_database_name() -> str:
    """Fetch database name from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_NAME_SECRET")
        if not secret_path:
            raise ValueError("Environment variable DATABASE_NAME_SECRET is not set.")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_NAME_SECRET: {e}")
        raise

def fetch_database_user() -> str:
    """Fetch database user from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_USER_SECRET")
        if not secret_path:
            raise ValueError("Environment variable DATABASE_USER_SECRET is not set.")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_USER_SECRET: {e}")
        raise

def fetch_database_password() -> str:
    """Fetch database password from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_PASSWORD_SECRET")
        if not secret_path:
            return None  # No fallback for password - this should fail safely
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_PASSWORD_SECRET: {e}")
        return None  # No fallback for password - this should fail safely

def fetch_cloud_sql_connection_name() -> str:
    """Fetch Cloud SQL connection name from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("CLOUD_SQL_CONNECTION_NAME")
        if not secret_path:
            # Fallback to default if not set
            print("⚠️ CLOUD_SQL_CONNECTION_NAME not set, using default: telepay-459221:us-central1:telepaypsql")
            return "telepay-459221:us-central1:telepaypsql"

        # Check if it's already in correct format (PROJECT:REGION:INSTANCE)
        if ':' in secret_path and not secret_path.startswith('projects/'):
            print(f"✅ CLOUD_SQL_CONNECTION_NAME already in correct format: {secret_path}")
            return secret_path

        # Otherwise, fetch from Secret Manager
        response = client.access_secret_version(request={"name": secret_path})
        connection_name = response.payload.data.decode("UTF-8").strip()
        print(f"✅ Fetched Cloud SQL connection name from Secret Manager: {connection_name}")
        return connection_name
    except Exception as e:
        print(f"❌ Error fetching CLOUD_SQL_CONNECTION_NAME: {e}")
        print("⚠️ Falling back to default: telepay-459221:us-central1:telepaypsql")
        return "telepay-459221:us-central1:telepaypsql"

# Database configuration - now using Secret Manager
DB_HOST = fetch_database_host()
DB_PORT = 5432  # This can remain hardcoded as it's not sensitive
DB_NAME = fetch_database_name()
DB_USER = fetch_database_user()
DB_PASSWORD = fetch_database_password()
DB_CLOUD_SQL_CONNECTION_NAME = fetch_cloud_sql_connection_name()

class DatabaseManager:
    def __init__(self):
        """
        Initialize DatabaseManager with connection pooling.

        🆕 NEW_ARCHITECTURE: Now uses ConnectionPool for better performance and resource management.
        """
        self.host = DB_HOST
        self.port = DB_PORT
        self.dbname = DB_NAME
        self.user = DB_USER
        self.password = DB_PASSWORD

        # Validate that critical credentials are available
        if not self.password:
            raise RuntimeError("Database password not available from Secret Manager. Cannot initialize DatabaseManager.")
        if not self.host or not self.dbname or not self.user:
            raise RuntimeError("Critical database configuration missing from Secret Manager.")

        # 🆕 NEW_ARCHITECTURE: Initialize connection pool
        try:
            self.pool = init_connection_pool({
                'instance_connection_name': DB_CLOUD_SQL_CONNECTION_NAME,
                'database': self.dbname,
                'user': self.user,
                'password': self.password,
                'pool_size': int(os.getenv('DB_POOL_SIZE', '5')),
                'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '10')),
                'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
                'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '1800'))
            })
            print("✅ [DATABASE] Connection pool initialized")
        except Exception as e:
            print(f"❌ [DATABASE] Failed to initialize connection pool: {e}")
            raise

    def get_connection(self):
        """
        Get raw database connection from pool.

        🆕 NEW_ARCHITECTURE: Now returns connection from pool instead of creating new connection.

        ⚠️ DEPRECATED: Prefer using execute_query() or get_session() for better connection management.
        This method is kept for backward compatibility with legacy code.

        Returns:
            psycopg2 connection object
        """
        # For backward compatibility, return a raw connection from the pool
        # This will be managed by the pool but returned as raw connection
        return self.pool.engine.raw_connection()

    def execute_query(self, query: str, params: dict = None):
        """
        Execute SQL query using connection pool.

        🆕 NEW_ARCHITECTURE: New method for executing queries with connection pooling.

        Args:
            query: SQL query with :param_name placeholders
            params: Dictionary of parameters

        Returns:
            Query result
        """
        return self.pool.execute_query(query, params)

    def get_session(self):
        """
        Get SQLAlchemy ORM session from pool.

        🆕 NEW_ARCHITECTURE: New method for ORM operations.

        Usage:
            with db_manager.get_session() as session:
                result = session.query(...)

        Returns:
            SQLAlchemy session
        """
        return self.pool.get_session()

    def health_check(self) -> bool:
        """
        Check database connection health.

        🆕 NEW_ARCHITECTURE: New method for health monitoring.

        Returns:
            True if database is accessible, False otherwise
        """
        return self.pool.health_check()

    def close(self):
        """
        Close connection pool on shutdown.

        🆕 NEW_ARCHITECTURE: New method for clean shutdown.
        """
        if hasattr(self, 'pool'):
            self.pool.close()
            print("✅ [DATABASE] Connection pool closed")
    
    def fetch_open_channel_list(self) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """
        Fetch all open_channel_id channels and their subscription info from database.
        Returns: (open_channel_list, open_channel_info_map)
        """
        from sqlalchemy import text

        open_channel_list = []
        open_channel_info_map = {}

        try:
            with self.pool.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT open_channel_id, open_channel_title, open_channel_description, closed_channel_id, closed_channel_title, closed_channel_description, sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time, client_wallet_address, client_payout_currency, client_payout_network FROM main_clients_database"
                ))
                for (open_channel_id, open_channel_title, open_channel_desc, closed_channel_id, closed_channel_title, closed_channel_desc, s1_price, s1_time, s2_price, s2_time, s3_price, s3_time, wallet_addr, payout_currency, payout_network) in result.fetchall():
                    open_channel_list.append(open_channel_id)
                    open_channel_info_map[open_channel_id] = {
                        "open_channel_title": open_channel_title,
                        "open_channel_description": open_channel_desc,
                        "closed_channel_id": closed_channel_id,
                        "closed_channel_title": closed_channel_title,
                        "closed_channel_description": closed_channel_desc,
                        "sub_1_price": s1_price,
                        "sub_1_time": s1_time,
                        "sub_2_price": s2_price,
                        "sub_2_time": s2_time,
                        "sub_3_price": s3_price,
                        "sub_3_time": s3_time,
                        "client_wallet_address": wallet_addr,
                        "client_payout_currency": payout_currency,
                        "client_payout_network": payout_network,
                    }
        except Exception as e:
            print("❌ db open_channel error:", e)

        return open_channel_list, open_channel_info_map
    
    def fetch_closed_channel_id(self, open_channel_id: str) -> Optional[str]:
        """
        Get the closed channel ID for a given open channel ID.
        
        Args:
            open_channel_id: The open channel ID to look up
            
        Returns:
            The closed channel ID if found, None otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            print(f"🔍 [DEBUG] Looking up closed_channel_id for open_channel_id: {str(open_channel_id)}")
            cur.execute("SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s", (str(open_channel_id),))
            result = cur.fetchone()
            print(f"📋 [DEBUG] fetch_closed_channel_id result: {result}")
            cur.close()
            conn.close()
            if result and result[0]:
                return result[0]
            else:
                print("❌ No matching record found for open_channel_id =", open_channel_id)
                return None
        except Exception as e:
            print(f"❌ Error fetching closed_channel_id: {e}")
            return None
    
    def fetch_client_wallet_info(self, open_channel_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get the client wallet address, payout currency, and payout network for a given open_channel_id.

        Args:
            open_channel_id: The open_channel_id to look up

        Returns:
            Tuple of (client_wallet_address, client_payout_currency, client_payout_network) if found, (None, None, None) otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            print(f"🔍 [DEBUG] Looking up wallet info for open_channel_id: {str(open_channel_id)}")
            cur.execute(
                "SELECT client_wallet_address, client_payout_currency, client_payout_network FROM main_clients_database WHERE open_channel_id = %s",
                (str(open_channel_id),)
            )
            result = cur.fetchone()
            print(f"💰 [DEBUG] fetch_client_wallet_info result: {result}")
            cur.close()
            conn.close()

            if result:
                wallet_address, payout_currency, payout_network = result
                return wallet_address, payout_currency, payout_network
            else:
                print("❌ No wallet info found for open_channel_id =", open_channel_id)
                return None, None, None

        except Exception as e:
            print(f"❌ Error fetching wallet info: {e}")
            return None, None, None
    
    def get_default_donation_channel(self) -> Optional[str]:
        """
        Get the first available channel for donations.
        This can be used as a fallback when no specific channel is provided.

        Returns:
            The first available open_channel_id, or None if no channels exist
        """
        from sqlalchemy import text

        try:
            with self.pool.engine.connect() as conn:
                result = conn.execute(text("SELECT open_channel_id FROM main_clients_database LIMIT 1"))
                row = result.fetchone()
                if row:
                    print(f"🎯 [DEBUG] Found default donation channel: {row[0]}")
                    return row[0]
                else:
                    print("ℹ️ [DEBUG] No channels found in database for default donation")
                    return None
        except Exception as e:
            print(f"❌ [DEBUG] Error getting default donation channel: {e}")
            return None

    def fetch_all_closed_channels(self) -> List[Dict[str, Any]]:
        """
        Fetch all closed channels with their associated metadata for donation messages.

        Returns:
            List of dicts containing:
            - closed_channel_id: The closed channel ID
            - open_channel_id: The associated open channel ID
            - closed_channel_title: Title of the closed channel
            - closed_channel_description: Description of the closed channel
            - closed_channel_donation_message: Custom donation message for the channel
            - payout_strategy: "instant" or "threshold"
            - payout_threshold_usd: Threshold amount for batch payouts

        Example:
            [
                {
                    "closed_channel_id": "-1002345678901",
                    "open_channel_id": "-1003268562225",
                    "closed_channel_title": "Premium Content",
                    "closed_channel_description": "Exclusive access",
                    "closed_channel_donation_message": "Your support helps us...",
                    "payout_strategy": "threshold",
                    "payout_threshold_usd": 100.00
                },
                ...
            ]
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    closed_channel_id,
                    open_channel_id,
                    closed_channel_title,
                    closed_channel_description,
                    closed_channel_donation_message,
                    payout_strategy,
                    payout_threshold_usd
                FROM main_clients_database
                WHERE closed_channel_id IS NOT NULL
                    AND closed_channel_id != ''
                ORDER BY closed_channel_id
            """)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            result = []
            for row in rows:
                result.append({
                    "closed_channel_id": row[0],
                    "open_channel_id": row[1],
                    "closed_channel_title": row[2] if row[2] else "Premium Channel",
                    "closed_channel_description": row[3] if row[3] else "exclusive content",
                    "closed_channel_donation_message": row[4] if row[4] else "Consider supporting our channel!",
                    "payout_strategy": row[5] if row[5] else "instant",
                    "payout_threshold_usd": row[6] if row[6] else 0.0
                })

            print(f"📋 Fetched {len(result)} closed channels for donation messages")
            return result

        except Exception as e:
            print(f"❌ Error fetching closed channels: {e}")
            return []

    def channel_exists(self, open_channel_id: str) -> bool:
        """
        Validate if a channel exists in the database.
        Used for security validation of callback data.

        Args:
            open_channel_id: The open channel ID to validate

        Returns:
            True if channel exists, False otherwise

        Example:
            >>> db.channel_exists("-1003268562225")
            True
            >>> db.channel_exists("-1009999999999")
            False
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM main_clients_database WHERE open_channel_id = %s LIMIT 1",
                (str(open_channel_id),)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()

            exists = result is not None
            if exists:
                print(f"✅ Channel validation: {open_channel_id} exists")
            else:
                print(f"⚠️ Channel validation: {open_channel_id} does not exist")

            return exists

        except Exception as e:
            print(f"❌ Error validating channel: {e}")
            return False

    def get_channel_details_by_open_id(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch channel details by open_channel_id for donation message formatting.

        This method is used exclusively by the donation workflow to display
        channel information to users. It does NOT fetch subscription pricing
        (sub_value) since donations use user-entered amounts.

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
                "closed_channel_title": "11-7 #2 SHIBA CLOSED INSTANT",
                "closed_channel_description": "Another Test."
            }
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    closed_channel_title,
                    closed_channel_description
                FROM main_clients_database
                WHERE open_channel_id = %s
                LIMIT 1
            """, (str(open_channel_id),))
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                channel_details = {
                    "closed_channel_title": result[0] if result[0] else "Premium Channel",
                    "closed_channel_description": result[1] if result[1] else "Exclusive content"
                }
                print(f"✅ Fetched channel details for {open_channel_id}")
                return channel_details
            else:
                print(f"⚠️ No channel details found for {open_channel_id}")
                return None

        except Exception as e:
            print(f"❌ Error fetching channel details: {e}")
            return None

    def insert_channel_config(self, channel_data: Dict[str, Any]) -> bool:
        """
        Insert a new channel configuration into the database.

        Args:
            channel_data: Dictionary containing channel configuration data

        Returns:
            True if successful, False otherwise
        """
        vals = (
            channel_data["open_channel_id"],
            channel_data.get("open_channel_title", "Default Title"),
            channel_data.get("open_channel_description", "Default Description"),
            channel_data["closed_channel_id"],
            channel_data.get("closed_channel_title", "Default Title"),
            channel_data.get("closed_channel_description", "Default Description"),
            channel_data["sub_1_price"],
            channel_data["sub_1_time"],
            channel_data["sub_2_price"],
            channel_data["sub_2_time"],
            channel_data["sub_3_price"],
            channel_data["sub_3_time"],
            channel_data.get("client_wallet_address", ""),
            channel_data.get("client_payout_currency", "USD"),
        )

        try:
            conn = self.get_connection()
            with conn, conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO main_clients_database
                       (open_channel_id, open_channel_title, open_channel_description, closed_channel_id, closed_channel_title, closed_channel_description,
                        sub_1_price, sub_1_time,
                        sub_2_price, sub_2_time,
                        sub_3_price, sub_3_time,
                        client_wallet_address, client_payout_currency)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    vals,
                )
            return True
        except Exception as e:
            print(f"❌ DB error: {e}")
            return False

    def fetch_channel_by_id(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a complete channel configuration by open_channel_id.

        Args:
            open_channel_id: The open channel ID to look up

        Returns:
            Dictionary with all channel data if found, None otherwise
        """
        from sqlalchemy import text

        try:
            with self.pool.engine.connect() as conn:
                print(f"🔍 [DB] Fetching channel config for open_channel_id: {open_channel_id}")
                result = conn.execute(
                    text("""SELECT open_channel_id, open_channel_title, open_channel_description,
                              closed_channel_id, closed_channel_title, closed_channel_description,
                              sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                              client_wallet_address, client_payout_currency, client_payout_network
                       FROM main_clients_database
                       WHERE open_channel_id = :open_channel_id"""),
                    {"open_channel_id": str(open_channel_id)}
                )
                row = result.fetchone()

                if row:
                    channel_data = {
                        "open_channel_id": row[0],
                        "open_channel_title": row[1],
                        "open_channel_description": row[2],
                        "closed_channel_id": row[3],
                        "closed_channel_title": row[4],
                        "closed_channel_description": row[5],
                        "sub_1_price": row[6],
                        "sub_1_time": row[7],
                        "sub_2_price": row[8],
                        "sub_2_time": row[9],
                        "sub_3_price": row[10],
                        "sub_3_time": row[11],
                        "client_wallet_address": row[12],
                        "client_payout_currency": row[13],
                        "client_payout_network": row[14],
                    }
                    print(f"✅ [DB] Channel config found for {open_channel_id}")
                    return channel_data
                else:
                    print(f"❌ [DB] No channel config found for {open_channel_id}")
                    return None

        except Exception as e:
            print(f"❌ [DB] Error fetching channel config: {e}")
            return None

    def update_channel_config(self, open_channel_id: str, channel_data: Dict[str, Any]) -> bool:
        """
        Update an existing channel configuration in the database.

        Args:
            open_channel_id: The open channel ID to update
            channel_data: Dictionary containing updated channel data

        Returns:
            True if successful, False otherwise
        """
        from sqlalchemy import text

        try:
            with self.pool.engine.connect() as conn:
                print(f"💾 [DB] Updating channel config for {open_channel_id}")
                result = conn.execute(
                    text("""UPDATE main_clients_database
                       SET open_channel_title = :open_channel_title,
                           open_channel_description = :open_channel_description,
                           closed_channel_id = :closed_channel_id,
                           closed_channel_title = :closed_channel_title,
                           closed_channel_description = :closed_channel_description,
                           sub_1_price = :sub_1_price,
                           sub_1_time = :sub_1_time,
                           sub_2_price = :sub_2_price,
                           sub_2_time = :sub_2_time,
                           sub_3_price = :sub_3_price,
                           sub_3_time = :sub_3_time,
                           client_wallet_address = :client_wallet_address,
                           client_payout_currency = :client_payout_currency
                       WHERE open_channel_id = :open_channel_id"""),
                    {
                        "open_channel_title": channel_data.get("open_channel_title"),
                        "open_channel_description": channel_data.get("open_channel_description"),
                        "closed_channel_id": channel_data.get("closed_channel_id"),
                        "closed_channel_title": channel_data.get("closed_channel_title"),
                        "closed_channel_description": channel_data.get("closed_channel_description"),
                        "sub_1_price": channel_data.get("sub_1_price"),
                        "sub_1_time": channel_data.get("sub_1_time"),
                        "sub_2_price": channel_data.get("sub_2_price"),
                        "sub_2_time": channel_data.get("sub_2_time"),
                        "sub_3_price": channel_data.get("sub_3_price"),
                        "sub_3_time": channel_data.get("sub_3_time"),
                        "client_wallet_address": channel_data.get("client_wallet_address"),
                        "client_payout_currency": channel_data.get("client_payout_currency"),
                        "open_channel_id": str(open_channel_id),
                    }
                )
                conn.commit()
                rows_affected = result.rowcount

                if rows_affected > 0:
                    print(f"✅ [DB] Channel config updated successfully for {open_channel_id}")
                    return True
                else:
                    print(f"⚠️ [DB] No rows updated for {open_channel_id}")
                    return False

        except Exception as e:
            print(f"❌ [DB] Error updating channel config: {e}")
            return False
    
    def fetch_expired_subscriptions(self) -> List[Tuple[int, int, str, str]]:
        """
        Fetch all expired subscriptions from database.

        Returns:
            List of tuples: (user_id, private_channel_id, expire_time, expire_date)
        """
        from datetime import datetime
        from sqlalchemy import text

        expired_subscriptions = []

        try:
            with self.pool.engine.connect() as conn:
                # Query active subscriptions with expiration data
                query = """
                    SELECT user_id, private_channel_id, expire_time, expire_date
                    FROM private_channel_users_database
                    WHERE is_active = true
                    AND expire_time IS NOT NULL
                    AND expire_date IS NOT NULL
                """

                result = conn.execute(text(query))
                results = result.fetchall()

                current_datetime = datetime.now()

                for row in results:
                    user_id, private_channel_id, expire_time_str, expire_date_str = row

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
                            expired_subscriptions.append((user_id, private_channel_id, expire_time_str, expire_date_str))

                    except Exception as e:
                        print(f"❌ Error parsing expiration data for user {user_id}: {e}")
                        continue

        except Exception as e:
            print(f"❌ Database error fetching expired subscriptions: {e}")

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
        from sqlalchemy import text

        try:
            with self.pool.engine.connect() as conn:
                update_query = """
                    UPDATE private_channel_users_database
                    SET is_active = false
                    WHERE user_id = :user_id AND private_channel_id = :private_channel_id AND is_active = true
                """

                result = conn.execute(text(update_query), {
                    "user_id": user_id,
                    "private_channel_id": private_channel_id
                })
                conn.commit()
                rows_affected = result.rowcount

                if rows_affected > 0:
                    print(f"📝 [DEBUG] Marked subscription as inactive: user {user_id}, channel {private_channel_id}")
                    return True
                else:
                    print(f"⚠️ [WARNING] No active subscription found to deactivate: user {user_id}, channel {private_channel_id}")
                    return False

        except Exception as e:
            print(f"❌ [ERROR] Database error deactivating subscription for user {user_id}, channel {private_channel_id}: {e}")
            return False

    def get_notification_settings(self, open_channel_id: str) -> Optional[Tuple[bool, Optional[int]]]:
        """
        Get notification settings for a channel.
        🆕 Added for NOTIFICATION_MANAGEMENT_ARCHITECTURE

        Args:
            open_channel_id: The open channel ID to look up

        Returns:
            Tuple of (notification_status, notification_id) if found, None otherwise

        Example:
            >>> db.get_notification_settings("-1003268562225")
            (True, 123456789)
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT notification_status, notification_id
                FROM main_clients_database
                WHERE open_channel_id = %s
            """, (str(open_channel_id),))
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                notification_status, notification_id = result
                print(f"✅ [NOTIFICATION] Settings for {open_channel_id}: enabled={notification_status}, id={notification_id}")
                return notification_status, notification_id
            else:
                print(f"⚠️ [NOTIFICATION] No settings found for {open_channel_id}")
                return None

        except Exception as e:
            print(f"❌ [NOTIFICATION] Error fetching settings: {e}")
            return None

    def get_last_broadcast_message_ids(
        self,
        open_channel_id: str
    ) -> Dict[str, Optional[int]]:
        """
        Get the last sent message IDs for a channel pair.

        Args:
            open_channel_id: The open channel ID to query

        Returns:
            {
                'last_open_message_id': int or None,
                'last_closed_message_id': int or None
            }
        """
        try:
            from sqlalchemy import text

            with self.pool.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT
                            last_open_message_id,
                            last_closed_message_id
                        FROM broadcast_manager
                        WHERE open_channel_id = :open_channel_id
                        LIMIT 1
                    """),
                    {'open_channel_id': open_channel_id}
                ).fetchone()

                if result:
                    return {
                        'last_open_message_id': result[0],
                        'last_closed_message_id': result[1]
                    }
                else:
                    return {
                        'last_open_message_id': None,
                        'last_closed_message_id': None
                    }

        except Exception as e:
            print(f"❌ Error fetching message IDs for {open_channel_id}: {e}")
            return {
                'last_open_message_id': None,
                'last_closed_message_id': None
            }

    def update_broadcast_message_ids(
        self,
        open_channel_id: str,
        open_message_id: Optional[int] = None,
        closed_message_id: Optional[int] = None
    ) -> bool:
        """
        Update the last sent message IDs for a channel pair.

        Args:
            open_channel_id: The open channel ID
            open_message_id: Telegram message ID sent to open channel
            closed_message_id: Telegram message ID sent to closed channel

        Returns:
            True if successful, False otherwise
        """
        try:
            from sqlalchemy import text

            # Build dynamic update query
            update_fields = []
            params = {'open_channel_id': open_channel_id}

            if open_message_id is not None:
                update_fields.append("last_open_message_id = :open_msg_id")
                update_fields.append("last_open_message_sent_at = NOW()")
                params['open_msg_id'] = open_message_id

            if closed_message_id is not None:
                update_fields.append("last_closed_message_id = :closed_msg_id")
                update_fields.append("last_closed_message_sent_at = NOW()")
                params['closed_msg_id'] = closed_message_id

            if not update_fields:
                print("⚠️ No message IDs provided to update")
                return False

            query = f"""
                UPDATE broadcast_manager
                SET {', '.join(update_fields)}
                WHERE open_channel_id = :open_channel_id
            """

            with self.pool.engine.connect() as conn:
                conn.execute(text(query), params)
                conn.commit()

                print(
                    f"📝 Updated message IDs for {open_channel_id} "
                    f"(open={open_message_id}, closed={closed_message_id})"
                )

                return True

        except Exception as e:
            print(f"❌ Error updating message IDs for {open_channel_id}: {e}")
            return False


def _valid_channel_id(text: str) -> bool:
    """Validate that a channel ID is properly formatted."""
    if text.lstrip("-").isdigit():
        return len(text) <= 14
    return False

def _valid_sub(text: str) -> bool:
    """Validate that a subscription value is properly formatted."""
    try:
        val = float(text)
    except ValueError:
        return False
    if not (0 <= val <= 9999.99):
        return False
    parts = text.split(".")
    return len(parts) == 1 or len(parts[1]) <= 2

def _valid_time(text: str) -> bool:
    """Validate that a time value is properly formatted."""
    return text.isdigit() and 1 <= int(text) <= 999

# Database conversation handler for receiving final subscription data
async def receive_sub3_time_db(update: Update, ctx: ContextTypes.DEFAULT_TYPE, db_manager: DatabaseManager):
    """Handle the final step of database entry conversation."""
    if not _valid_time(update.message.text):
        await update.message.reply_text("❌ Invalid time. Try sub_3_time again:")
        from input_handlers import SUB3_TIME_INPUT  # Import conversation state
        return SUB3_TIME_INPUT
    
    ctx.user_data["sub_3_time"] = int(update.message.text)
    
    channel_data = {
        "open_channel_id": ctx.user_data["open_channel_id"],
        "closed_channel_id": ctx.user_data["closed_channel_id"],
        "sub_1_price": ctx.user_data["sub_1_price"],
        "sub_1_time": ctx.user_data["sub_1_time"],
        "sub_2_price": ctx.user_data["sub_2_price"],
        "sub_2_time": ctx.user_data["sub_2_time"],
        "sub_3_price": ctx.user_data["sub_3_price"],
        "sub_3_time": ctx.user_data["sub_3_time"],
    }
    
    if db_manager.insert_channel_config(channel_data):
        vals = (
            channel_data["open_channel_id"], channel_data["closed_channel_id"],
            channel_data["sub_1_price"], channel_data["sub_1_time"],
            channel_data["sub_2_price"], channel_data["sub_2_time"],
            channel_data["sub_3_price"], channel_data["sub_3_time"],
        )
        await update.message.reply_text(
            "✅ Saved:\n"
            f"open_channel_id={vals[0]}, closed_channel_id={vals[1]},\n"
            f"sub_1_price={vals[2]} ({vals[3]}), sub_2_price={vals[4]} ({vals[5]}), sub_3_price={vals[6]} ({vals[7]})"
        )
    else:
        await update.message.reply_text("❌ Failed to save to database.")
    
    ctx.user_data.clear()
    return ConversationHandler.END