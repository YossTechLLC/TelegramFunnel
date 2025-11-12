#!/usr/bin/env python
"""
Database Manager for GCBotCommand
Handles all PostgreSQL database operations
"""
import psycopg2
import os
import json
from typing import Optional, Tuple, List, Dict, Any
from google.cloud import secretmanager

def fetch_database_host() -> str:
    """Fetch database host from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_HOST_SECRET")
        if not secret_path:
            raise ValueError("DATABASE_HOST_SECRET not set")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_HOST_SECRET: {e}")
        raise

def fetch_database_name() -> str:
    """Fetch database name from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_NAME_SECRET")
        if not secret_path:
            raise ValueError("DATABASE_NAME_SECRET not set")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_NAME_SECRET: {e}")
        raise

def fetch_database_user() -> str:
    """Fetch database user from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_USER_SECRET")
        if not secret_path:
            raise ValueError("DATABASE_USER_SECRET not set")
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_USER_SECRET: {e}")
        raise

def fetch_database_password() -> str:
    """Fetch database password from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_PASSWORD_SECRET")
        if not secret_path:
            return None
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error fetching DATABASE_PASSWORD_SECRET: {e}")
        return None

class DatabaseManager:
    """Manages all database operations for GCBotCommand"""

    def __init__(self):
        # Check if running in Cloud Run (use Unix socket) or locally (use TCP)
        cloud_sql_connection = os.getenv("CLOUD_SQL_CONNECTION_NAME")

        if cloud_sql_connection:
            # Cloud Run mode - use Unix socket
            self.host = f"/cloudsql/{cloud_sql_connection}"
            print(f"🔌 Using Cloud SQL Unix socket: {self.host}")
        else:
            # Local/VM mode - use TCP connection
            self.host = fetch_database_host()
            print(f"🔌 Using TCP connection to: {self.host}")

        self.port = 5432
        self.dbname = fetch_database_name()
        self.user = fetch_database_user()
        self.password = fetch_database_password()

        if not all([self.host, self.dbname, self.user, self.password]):
            raise RuntimeError("Critical database configuration missing from Secret Manager")

        print("✅ Database configuration loaded")
        print(f"  🗄️  Database: {self.dbname}")
        print(f"  🌐 Host: {self.host}")
        print(f"  👤 User: {self.user}")

    def get_connection(self):
        """Create and return a database connection"""
        return psycopg2.connect(
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port
        )

    def fetch_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch channel configuration by open_channel_id

        Args:
            channel_id: The open_channel_id to look up

        Returns:
            Dictionary with channel configuration, or None if not found
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        open_channel_id, open_channel_title, open_channel_description,
                        closed_channel_id, closed_channel_title, closed_channel_description,
                        closed_channel_donation_message,
                        sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                        client_wallet_address, client_payout_currency, client_payout_network,
                        payout_strategy, payout_threshold_usd,
                        notification_status, notification_id
                    FROM main_clients_database
                    WHERE open_channel_id = %s
                """, (channel_id,))

                row = cur.fetchone()
                if not row:
                    return None

                return {
                    "open_channel_id": row[0],
                    "open_channel_title": row[1],
                    "open_channel_description": row[2],
                    "closed_channel_id": row[3],
                    "closed_channel_title": row[4],
                    "closed_channel_description": row[5],
                    "closed_channel_donation_message": row[6],
                    "sub_1_price": row[7],
                    "sub_1_time": row[8],
                    "sub_2_price": row[9],
                    "sub_2_time": row[10],
                    "sub_3_price": row[11],
                    "sub_3_time": row[12],
                    "client_wallet_address": row[13],
                    "client_payout_currency": row[14],
                    "client_payout_network": row[15],
                    "payout_strategy": row[16],
                    "payout_threshold_usd": row[17],
                    "notification_status": row[18],
                    "notification_id": row[19]
                }
        except Exception as e:
            print(f"❌ Error fetching channel by ID: {e}")
            return None

    def update_channel_config(self, channel_id: str, channel_data: Dict[str, Any]) -> bool:
        """
        Update or insert channel configuration

        Args:
            channel_id: The open_channel_id
            channel_data: Dictionary with channel configuration fields

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                # Use UPSERT (INSERT ... ON CONFLICT UPDATE)
                cur.execute("""
                    INSERT INTO main_clients_database (
                        open_channel_id, open_channel_title, open_channel_description,
                        closed_channel_id, closed_channel_title, closed_channel_description,
                        closed_channel_donation_message,
                        sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                        client_wallet_address, client_payout_currency, client_payout_network
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (open_channel_id) DO UPDATE SET
                        open_channel_title = EXCLUDED.open_channel_title,
                        open_channel_description = EXCLUDED.open_channel_description,
                        closed_channel_id = EXCLUDED.closed_channel_id,
                        closed_channel_title = EXCLUDED.closed_channel_title,
                        closed_channel_description = EXCLUDED.closed_channel_description,
                        closed_channel_donation_message = EXCLUDED.closed_channel_donation_message,
                        sub_1_price = EXCLUDED.sub_1_price,
                        sub_1_time = EXCLUDED.sub_1_time,
                        sub_2_price = EXCLUDED.sub_2_price,
                        sub_2_time = EXCLUDED.sub_2_time,
                        sub_3_price = EXCLUDED.sub_3_price,
                        sub_3_time = EXCLUDED.sub_3_time,
                        client_wallet_address = EXCLUDED.client_wallet_address,
                        client_payout_currency = EXCLUDED.client_payout_currency,
                        client_payout_network = EXCLUDED.client_payout_network
                """, (
                    channel_id,
                    channel_data.get("open_channel_title"),
                    channel_data.get("open_channel_description"),
                    channel_data.get("closed_channel_id"),
                    channel_data.get("closed_channel_title"),
                    channel_data.get("closed_channel_description"),
                    channel_data.get("closed_channel_donation_message"),
                    channel_data.get("sub_1_price"),
                    channel_data.get("sub_1_time"),
                    channel_data.get("sub_2_price"),
                    channel_data.get("sub_2_time"),
                    channel_data.get("sub_3_price"),
                    channel_data.get("sub_3_time"),
                    channel_data.get("client_wallet_address"),
                    channel_data.get("client_payout_currency"),
                    channel_data.get("client_payout_network")
                ))
                conn.commit()
                print(f"✅ Channel {channel_id} configuration saved")
                return True
        except Exception as e:
            print(f"❌ Error updating channel config: {e}")
            return False

    def fetch_open_channel_list(self) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """
        Fetch all open channels and their configuration

        Returns:
            Tuple of (list of channel IDs, dict mapping ID to config)
        """
        open_channel_list = []
        open_channel_info_map = {}

        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        open_channel_id, open_channel_title, open_channel_description,
                        closed_channel_id, closed_channel_title, closed_channel_description,
                        sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                        client_wallet_address, client_payout_currency, client_payout_network
                    FROM main_clients_database
                """)

                for row in cur.fetchall():
                    open_channel_id = row[0]
                    open_channel_list.append(open_channel_id)
                    open_channel_info_map[open_channel_id] = {
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
                        "client_payout_network": row[14]
                    }
        except Exception as e:
            print(f"❌ Error fetching open channel list: {e}")

        return open_channel_list, open_channel_info_map

    # ═══════════════════════════════════════════════════════════════
    #  CONVERSATION STATE MANAGEMENT (for stateless webhook operation)
    # ═══════════════════════════════════════════════════════════════

    def save_conversation_state(self, user_id: int, conversation_type: str, state_data: Dict[str, Any]) -> bool:
        """
        Save conversation state to database for stateless operation

        Args:
            user_id: Telegram user ID
            conversation_type: Type of conversation ('database', 'donation', 'payment', etc.)
            state_data: Dictionary with conversation state

        Returns:
            True if successful
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_conversation_state (user_id, conversation_type, state_data, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (user_id, conversation_type) DO UPDATE SET
                        state_data = EXCLUDED.state_data,
                        updated_at = NOW()
                """, (user_id, conversation_type, json.dumps(state_data)))
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error saving conversation state: {e}")
            return False

    def get_conversation_state(self, user_id: int, conversation_type: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve conversation state from database

        Args:
            user_id: Telegram user ID
            conversation_type: Type of conversation

        Returns:
            State data dictionary or None
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    SELECT state_data FROM user_conversation_state
                    WHERE user_id = %s AND conversation_type = %s
                """, (user_id, conversation_type))
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])
                return None
        except Exception as e:
            print(f"❌ Error getting conversation state: {e}")
            return None

    def clear_conversation_state(self, user_id: int, conversation_type: str) -> bool:
        """Clear conversation state for a user"""
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM user_conversation_state
                    WHERE user_id = %s AND conversation_type = %s
                """, (user_id, conversation_type))
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error clearing conversation state: {e}")
            return False
