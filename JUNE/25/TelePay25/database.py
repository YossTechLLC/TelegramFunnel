#!/usr/bin/env python
import psycopg2
import os
from typing import Optional, Tuple, List, Dict, Any
from google.cloud import secretmanager
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# Import token registry for validation
try:
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'GCSplit25'))
    from token_registry import TokenRegistry
    TOKEN_REGISTRY_AVAILABLE = True
    print("✅ [INFO] Token Registry imported successfully for database validation")
except ImportError as e:
    print(f"⚠️ [WARNING] Token Registry import failed: {e}")
    TOKEN_REGISTRY_AVAILABLE = False
    TokenRegistry = None

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
        
        # Initialize token registry for validation
        self.token_registry = None
        if TOKEN_REGISTRY_AVAILABLE:
            try:
                self.token_registry = TokenRegistry()
                print("✅ [INFO] DatabaseManager: Token Registry initialized for validation")
            except Exception as e:
                print(f"⚠️ [WARNING] DatabaseManager: Failed to initialize Token Registry: {e}")
        
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
                cur.execute("SELECT open_channel_id, open_channel_title, open_channel_description, closed_channel_id, closed_channel_title, closed_channel_description, sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time, client_wallet_address, client_payout_currency FROM main_clients_database")
                for (open_channel_id, open_channel_title, open_channel_desc, closed_channel_id, closed_channel_title, closed_channel_desc, s1_price, s1_time, s2_price, s2_time, s3_price, s3_time, wallet_addr, payout_currency) in cur.fetchall():
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
    
    def fetch_client_wallet_info(self, open_channel_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the client wallet address and payout currency for a given open_channel_id.
        
        Args:
            open_channel_id: The open_channel_id to look up
            
        Returns:
            Tuple of (client_wallet_address, client_payout_currency) if found, (None, None) otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            print(f"🔍 [DEBUG] Looking up wallet info for open_channel_id: {str(open_channel_id)}")
            cur.execute(
                "SELECT client_wallet_address, client_payout_currency FROM main_clients_database WHERE open_channel_id = %s", 
                (str(open_channel_id),)
            )
            result = cur.fetchone()
            print(f"💰 [DEBUG] fetch_client_wallet_info raw result: {result}")
            cur.close()
            conn.close()
            
            if result:
                wallet_address, payout_currency = result
                
                # Enhanced logging for currency validation
                print(f"🏦 [DEBUG] Retrieved wallet_address: '{wallet_address}'")
                print(f"💱 [DEBUG] Retrieved payout_currency: '{payout_currency}'")
                
                # Validate the retrieved payout currency
                if payout_currency:
                    is_valid, error_msg = self.validate_client_payout_currency(payout_currency)
                    if is_valid:
                        print(f"✅ [DEBUG] Payout currency '{payout_currency}' is valid")
                    else:
                        print(f"❌ [WARNING] Payout currency '{payout_currency}' is INVALID: {error_msg}")
                        print(f"⚠️ [WARNING] This will likely cause payment flow issues!")
                else:
                    print(f"⚠️ [WARNING] Payout currency is NULL/empty for channel {open_channel_id}")
                
                return wallet_address, payout_currency
            else:
                print(f"❌ [ERROR] No wallet info found for open_channel_id = {open_channel_id}")
                print(f"🔍 [DEBUG] This suggests the channel is not configured in main_clients_database")
                return None, None
                
        except Exception as e:
            print(f"❌ [ERROR] Database error fetching wallet info for channel {open_channel_id}: {e}")
            return None, None
    
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
    
    def validate_client_payout_currency(self, payout_currency: str) -> Tuple[bool, str]:
        """
        Validate that the payout currency is a supported token symbol.
        
        Args:
            payout_currency: The currency symbol to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not payout_currency:
            return False, "Payout currency cannot be empty"
        
        # Clean and standardize the currency symbol
        payout_currency = payout_currency.strip().upper()
        
        # If token registry is not available, allow ETH as fallback
        if not self.token_registry:
            if payout_currency == "ETH":
                return True, ""
            else:
                return False, f"Token registry not available - only ETH is supported as fallback"
        
        # Check if token is supported on Ethereum Mainnet (Chain ID 1)
        if payout_currency == "ETH" or self.token_registry.is_token_supported(1, payout_currency):
            return True, ""
        
        # Get list of supported tokens for error message
        supported_tokens = ["ETH"] + self.token_registry.get_supported_tokens(1)
        supported_tokens_str = ", ".join(supported_tokens)
        
        return False, f"Unsupported token '{payout_currency}'. Supported tokens: {supported_tokens_str}"
    
    def insert_channel_config(self, channel_data: Dict[str, Any]) -> bool:
        """
        Insert a new channel configuration into the database.
        
        Args:
            channel_data: Dictionary containing channel configuration data
            
        Returns:
            True if successful, False otherwise
        """
        # Validate client_payout_currency before inserting
        payout_currency = channel_data.get("client_payout_currency", "ETH")
        is_valid, error_msg = self.validate_client_payout_currency(payout_currency)
        
        if not is_valid:
            print(f"❌ [ERROR] Invalid client_payout_currency '{payout_currency}': {error_msg}")
            print(f"❌ [ERROR] Channel configuration insert failed for open_channel_id: {channel_data.get('open_channel_id', 'unknown')}")
            return False
        
        # Standardize the currency symbol (uppercase)
        payout_currency = payout_currency.strip().upper()
        print(f"✅ [INFO] Validated client_payout_currency: '{payout_currency}' for channel {channel_data.get('open_channel_id', 'unknown')}")
        
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
            payout_currency,
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
    
    def migrate_usd_to_token_currency(self, target_currency: str = "ETH", dry_run: bool = True) -> Dict[str, Any]:
        """
        Migrate existing USD values in client_payout_currency to a valid token symbol.
        
        Args:
            target_currency: The token symbol to replace USD with (default: ETH)
            dry_run: If True, only report what would be changed without making changes
            
        Returns:
            Dictionary with migration results
        """
        # Validate target currency
        is_valid, error_msg = self.validate_client_payout_currency(target_currency)
        if not is_valid:
            return {
                "success": False,
                "error": f"Invalid target currency '{target_currency}': {error_msg}",
                "records_found": 0,
                "records_updated": 0
            }
        
        target_currency = target_currency.strip().upper()
        
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                # First, find all records with USD as client_payout_currency
                query_find = """
                    SELECT open_channel_id, client_payout_currency 
                    FROM main_clients_database 
                    WHERE client_payout_currency = %s
                """
                cur.execute(query_find, ("USD",))
                usd_records = cur.fetchall()
                
                records_found = len(usd_records)
                print(f"🔍 [INFO] Found {records_found} records with client_payout_currency = 'USD'")
                
                if records_found == 0:
                    return {
                        "success": True,
                        "message": "No USD records found - no migration needed",
                        "records_found": 0,
                        "records_updated": 0
                    }
                
                # Log the records that would be updated
                for open_channel_id, current_currency in usd_records:
                    action = "WOULD UPDATE" if dry_run else "UPDATING"
                    print(f"📝 [INFO] {action}: Channel {open_channel_id} from '{current_currency}' to '{target_currency}'")
                
                records_updated = 0
                if not dry_run:
                    # Perform the actual update
                    update_query = """
                        UPDATE main_clients_database 
                        SET client_payout_currency = %s 
                        WHERE client_payout_currency = %s
                    """
                    cur.execute(update_query, (target_currency, "USD"))
                    records_updated = cur.rowcount
                    
                    print(f"✅ [INFO] Successfully updated {records_updated} records from 'USD' to '{target_currency}'")
                else:
                    records_updated = records_found
                    print(f"🔄 [INFO] DRY RUN: Would update {records_updated} records from 'USD' to '{target_currency}'")
                
                return {
                    "success": True,
                    "message": f"Migration {'completed' if not dry_run else 'simulated'} successfully",
                    "records_found": records_found,
                    "records_updated": records_updated,
                    "dry_run": dry_run,
                    "target_currency": target_currency
                }
                
        except Exception as e:
            error_msg = f"Migration failed: {e}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "records_found": 0,
                "records_updated": 0
            }
    
    def get_currency_distribution(self) -> Dict[str, Any]:
        """
        Get distribution of client_payout_currency values in the database.
        
        Returns:
            Dictionary with currency distribution statistics
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                query = """
                    SELECT client_payout_currency, COUNT(*) as count
                    FROM main_clients_database 
                    GROUP BY client_payout_currency
                    ORDER BY count DESC
                """
                cur.execute(query)
                results = cur.fetchall()
                
                distribution = {}
                total_records = 0
                
                for currency, count in results:
                    distribution[currency or "NULL"] = count
                    total_records += count
                    
                    # Validate each currency
                    if currency:
                        is_valid, _ = self.validate_client_payout_currency(currency)
                        status = "✅ VALID" if is_valid else "❌ INVALID"
                        print(f"💰 [INFO] Currency '{currency}': {count} records - {status}")
                    else:
                        print(f"⚠️ [WARNING] NULL currency: {count} records - ❌ INVALID")
                
                return {
                    "success": True,
                    "total_records": total_records,
                    "distribution": distribution,
                    "currencies": list(distribution.keys())
                }
                
        except Exception as e:
            error_msg = f"Failed to get currency distribution: {e}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
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