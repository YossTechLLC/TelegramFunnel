#!/usr/bin/env python
import psycopg2
import os
from typing import Optional, Tuple, List, Dict, Any
from google.cloud import secretmanager
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

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

# Database configuration - now using Secret Manager
DB_HOST = fetch_database_host()
DB_PORT = 5432  # This can remain hardcoded as it's not sensitive
DB_NAME = fetch_database_name()
DB_USER = fetch_database_user()
DB_PASSWORD = fetch_database_password()

class DatabaseManager:
    def __init__(self):
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
    
    def get_connection(self):
        """Create and return a database connection."""
        return psycopg2.connect(
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port
        )
    
    def fetch_open_channel_list(self) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """
        Fetch all open_channel_id channels and their subscription info from database.
        Returns: (open_channel_list, open_channel_info_map)
        """
        open_channel_list = []
        open_channel_info_map = {}

        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT open_channel_id, open_channel_title, open_channel_description, closed_channel_id, closed_channel_title, closed_channel_description, sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time, client_wallet_address, client_payout_currency, client_payout_network FROM main_clients_database")
                for (open_channel_id, open_channel_title, open_channel_desc, closed_channel_id, closed_channel_title, closed_channel_desc, s1_price, s1_time, s2_price, s2_time, s3_price, s3_time, wallet_addr, payout_currency, payout_network) in cur.fetchall():
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
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT open_channel_id FROM main_clients_database LIMIT 1")
                result = cur.fetchone()
                if result:
                    print(f"🎯 [DEBUG] Found default donation channel: {result[0]}")
                    return result[0]
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
            - payout_strategy: "instant" or "threshold"
            - payout_threshold_usd: Threshold amount for batch payouts

        Example:
            [
                {
                    "closed_channel_id": "-1002345678901",
                    "open_channel_id": "-1003268562225",
                    "closed_channel_title": "Premium Content",
                    "closed_channel_description": "Exclusive access",
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
                    "payout_strategy": row[4] if row[4] else "instant",
                    "payout_threshold_usd": row[5] if row[5] else 0.0
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

        Args:
            open_channel_id: The open channel ID to fetch details for

        Returns:
            Dict containing channel details or None if not found:
            {
                "closed_channel_title": str,
                "closed_channel_description": str,
                "sub_value": float
            }

        Example:
            >>> db.get_channel_details_by_open_id("-1003268562225")
            {
                "closed_channel_title": "11-7 #2 SHIBA CLOSED INSTANT",
                "closed_channel_description": "Another Test.",
                "sub_value": 6.00
            }
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    closed_channel_title,
                    closed_channel_description,
                    sub_value
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
                    "closed_channel_description": result[1] if result[1] else "Exclusive content",
                    "sub_value": result[2] if result[2] else 0.0
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
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                print(f"🔍 [DB] Fetching channel config for open_channel_id: {open_channel_id}")
                cur.execute(
                    """SELECT open_channel_id, open_channel_title, open_channel_description,
                              closed_channel_id, closed_channel_title, closed_channel_description,
                              sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                              client_wallet_address, client_payout_currency, client_payout_network
                       FROM main_clients_database
                       WHERE open_channel_id = %s""",
                    (str(open_channel_id),)
                )
                result = cur.fetchone()

                if result:
                    channel_data = {
                        "open_channel_id": result[0],
                        "open_channel_title": result[1],
                        "open_channel_description": result[2],
                        "closed_channel_id": result[3],
                        "closed_channel_title": result[4],
                        "closed_channel_description": result[5],
                        "sub_1_price": result[6],
                        "sub_1_time": result[7],
                        "sub_2_price": result[8],
                        "sub_2_time": result[9],
                        "sub_3_price": result[10],
                        "sub_3_time": result[11],
                        "client_wallet_address": result[12],
                        "client_payout_currency": result[13],
                        "client_payout_network": result[14],
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
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                print(f"💾 [DB] Updating channel config for {open_channel_id}")
                cur.execute(
                    """UPDATE main_clients_database
                       SET open_channel_title = %s,
                           open_channel_description = %s,
                           closed_channel_id = %s,
                           closed_channel_title = %s,
                           closed_channel_description = %s,
                           sub_1_price = %s,
                           sub_1_time = %s,
                           sub_2_price = %s,
                           sub_2_time = %s,
                           sub_3_price = %s,
                           sub_3_time = %s,
                           client_wallet_address = %s,
                           client_payout_currency = %s
                       WHERE open_channel_id = %s""",
                    (
                        channel_data.get("open_channel_title"),
                        channel_data.get("open_channel_description"),
                        channel_data.get("closed_channel_id"),
                        channel_data.get("closed_channel_title"),
                        channel_data.get("closed_channel_description"),
                        channel_data.get("sub_1_price"),
                        channel_data.get("sub_1_time"),
                        channel_data.get("sub_2_price"),
                        channel_data.get("sub_2_time"),
                        channel_data.get("sub_3_price"),
                        channel_data.get("sub_3_time"),
                        channel_data.get("client_wallet_address"),
                        channel_data.get("client_payout_currency"),
                        str(open_channel_id),
                    )
                )
                rows_affected = cur.rowcount

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
        
        expired_subscriptions = []
        
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                # Query active subscriptions with expiration data
                query = """
                    SELECT user_id, private_channel_id, expire_time, expire_date
                    FROM private_channel_users_database 
                    WHERE is_active = true 
                    AND expire_time IS NOT NULL 
                    AND expire_date IS NOT NULL
                """
                
                cur.execute(query)
                results = cur.fetchall()
                
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
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                update_query = """
                    UPDATE private_channel_users_database 
                    SET is_active = false 
                    WHERE user_id = %s AND private_channel_id = %s AND is_active = true
                """
                
                cur.execute(update_query, (user_id, private_channel_id))
                rows_affected = cur.rowcount
                
                if rows_affected > 0:
                    print(f"📝 [DEBUG] Marked subscription as inactive: user {user_id}, channel {private_channel_id}")
                    return True
                else:
                    print(f"⚠️ [WARNING] No active subscription found to deactivate: user {user_id}, channel {private_channel_id}")
                    return False
                    
        except Exception as e:
            print(f"❌ [ERROR] Database error deactivating subscription for user {user_id}, channel {private_channel_id}: {e}")
            return False

# Validation functions
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