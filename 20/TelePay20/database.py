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
        print(f"Error fetching DATABASE_HOST_SECRET: {e}")
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
        print(f"Error fetching DATABASE_NAME_SECRET: {e}")
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
        print(f"Error fetching DATABASE_USER_SECRET: {e}")
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
        print(f"Error fetching DATABASE_PASSWORD_SECRET: {e}")
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
    
    def fetch_tele_open_list(self) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """
        Fetch all tele_open channels and their subscription info from database.
        Returns: (tele_open_list, tele_info_open_map)
        """
        tele_open_list = []
        tele_info_open_map = {}
        
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT tele_open, sub_1, sub_1_time, sub_2, sub_2_time, sub_3, sub_3_time FROM tele_channel")
                for (tele_open, s1, s1_time, s2, s2_time, s3, s3_time,) in cur.fetchall():
                    tele_open_list.append(tele_open)
                    tele_info_open_map[tele_open] = {
                        "sub_1": s1,
                        "sub_1_time": s1_time,
                        "sub_2": s2,
                        "sub_2_time": s2_time,
                        "sub_3": s3,
                        "sub_3_time": s3_time,
                    }
        except Exception as e:
            print("db tele_open error:", e)
        
        return tele_open_list, tele_info_open_map
    
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
            print(f"[DEBUG] Looking up closed_channel_id for tele_open: {str(open_channel_id)}")
            cur.execute("SELECT tele_closed FROM tele_channel WHERE tele_open = %s", (str(open_channel_id),))
            result = cur.fetchone()
            print(f"[DEBUG] fetch_closed_channel_id result: {result}")
            cur.close()
            conn.close()
            if result and result[0]:
                return result[0]
            else:
                print("❌ No matching record found for tele_open =", open_channel_id)
                return None
        except Exception as e:
            print(f"❌ Error fetching tele_closed: {e}")
            return None
    
    def fetch_client_wallet_info(self, tele_open_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the client wallet address and payout currency for a given tele_open ID.
        
        Args:
            tele_open_id: The tele_open ID to look up
            
        Returns:
            Tuple of (client_wallet_address, client_payout_currency) if found, (None, None) otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            print(f"[DEBUG] Looking up wallet info for tele_open: {str(tele_open_id)}")
            cur.execute(
                "SELECT client_wallet_address, client_payout_currency FROM tele_channel WHERE tele_open = %s", 
                (str(tele_open_id),)
            )
            result = cur.fetchone()
            print(f"[DEBUG] fetch_client_wallet_info result: {result}")
            cur.close()
            conn.close()
            
            if result:
                wallet_address, payout_currency = result
                return wallet_address, payout_currency
            else:
                print("❌ No wallet info found for tele_open =", tele_open_id)
                return None, None
                
        except Exception as e:
            print(f"❌ Error fetching wallet info: {e}")
            return None, None
    
    def get_default_donation_channel(self) -> Optional[str]:
        """
        Get the first available channel for donations.
        This can be used as a fallback when no specific channel is provided.
        
        Returns:
            The first available tele_open channel ID, or None if no channels exist
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT tele_open FROM tele_channel LIMIT 1")
                result = cur.fetchone()
                if result:
                    print(f"[DEBUG] Found default donation channel: {result[0]}")
                    return result[0]
                else:
                    print("[DEBUG] No channels found in database for default donation")
                    return None
        except Exception as e:
            print(f"[DEBUG] Error getting default donation channel: {e}")
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
            channel_data["tele_open"],
            channel_data["tele_closed"],
            channel_data["sub_1"],
            channel_data["sub_1_time"],
            channel_data["sub_2"],
            channel_data["sub_2_time"],
            channel_data["sub_3"],
            channel_data["sub_3_time"],
        )
        
        try:
            conn = self.get_connection()
            with conn, conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO tele_channel
                       (tele_open, tele_closed,
                        sub_1, sub_1_time,
                        sub_2, sub_2_time,
                        sub_3, sub_3_time)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    vals,
                )
            return True
        except Exception as e:
            print(f"❌ DB error: {e}")
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
                    FROM private_channel_users 
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
                        print(f"Error parsing expiration data for user {user_id}: {e}")
                        continue
                        
        except Exception as e:
            print(f"Database error fetching expired subscriptions: {e}")
            
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
                    UPDATE private_channel_users 
                    SET is_active = false 
                    WHERE user_id = %s AND private_channel_id = %s AND is_active = true
                """
                
                cur.execute(update_query, (user_id, private_channel_id))
                rows_affected = cur.rowcount
                
                if rows_affected > 0:
                    print(f"[DEBUG] Marked subscription as inactive: user {user_id}, channel {private_channel_id}")
                    return True
                else:
                    print(f"[WARNING] No active subscription found to deactivate: user {user_id}, channel {private_channel_id}")
                    return False
                    
        except Exception as e:
            print(f"[ERROR] Database error deactivating subscription for user {user_id}, channel {private_channel_id}: {e}")
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
        "tele_open": ctx.user_data["tele_open"],
        "tele_closed": ctx.user_data["tele_closed"],
        "sub_1": ctx.user_data["sub_1"],
        "sub_1_time": ctx.user_data["sub_1_time"],
        "sub_2": ctx.user_data["sub_2"],
        "sub_2_time": ctx.user_data["sub_2_time"],
        "sub_3": ctx.user_data["sub_3"],
        "sub_3_time": ctx.user_data["sub_3_time"],
    }
    
    if db_manager.insert_channel_config(channel_data):
        vals = (
            channel_data["tele_open"], channel_data["tele_closed"],
            channel_data["sub_1"], channel_data["sub_1_time"],
            channel_data["sub_2"], channel_data["sub_2_time"],
            channel_data["sub_3"], channel_data["sub_3_time"],
        )
        await update.message.reply_text(
            "✅ Saved:\n"
            f"tele_open={vals[0]}, tele_closed={vals[1]},\n"
            f"sub_1={vals[2]} ({vals[3]}), sub_2={vals[4]} ({vals[5]}), sub_3={vals[6]} ({vals[7]})"
        )
    else:
        await update.message.reply_text("❌ Failed to save to database.")
    
    ctx.user_data.clear()
    return ConversationHandler.END