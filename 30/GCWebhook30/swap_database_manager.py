#!/usr/bin/env python
"""
Swap Database Manager for TelegramFunnel
Handles database operations for ChangeNOW swap tracking
"""
import os
import psycopg2
from typing import Dict, Any, Optional, List, Tuple
from google.cloud import secretmanager
from datetime import datetime


class SwapDatabaseManager:
    def __init__(self):
        """Initialize the Swap Database Manager with database credentials."""
        self.host = self.fetch_database_host()
        self.port = 5432
        self.dbname = self.fetch_database_name()
        self.user = self.fetch_database_user()
        self.password = self.fetch_database_password()
        
        # Validate that critical credentials are available
        if not self.password:
            raise RuntimeError("Database password not available from Secret Manager. Cannot initialize SwapDatabaseManager.")
        if not self.host or not self.dbname or not self.user:
            raise RuntimeError("Critical database configuration missing from Secret Manager.")
    
    def fetch_database_host(self) -> str:
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
    
    def fetch_database_name(self) -> str:
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
    
    def fetch_database_user(self) -> str:
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
    
    def fetch_database_password(self) -> str:
        """Fetch database password from Secret Manager."""
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
    
    def get_connection(self):
        """Create and return a database connection."""
        return psycopg2.connect(
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port
        )
    
    def create_swap_tracking_table(self) -> bool:
        """
        Create the changenow_swaps table for tracking swap transactions.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                create_table_sql = """
                    CREATE TABLE IF NOT EXISTS changenow_swaps (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        order_id VARCHAR(255),
                        exchange_id VARCHAR(255) UNIQUE,
                        subscription_price_usd DECIMAL(10,2),
                        swap_amount_usd DECIMAL(10,2),
                        eth_amount_sent DECIMAL(18,8),
                        target_currency VARCHAR(10),
                        client_wallet_address VARCHAR(255),
                        expected_output VARCHAR(50),
                        eth_tx_hash VARCHAR(66),
                        payin_address VARCHAR(255),
                        swap_status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        error_message TEXT
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_changenow_swaps_user_id ON changenow_swaps(user_id);
                    CREATE INDEX IF NOT EXISTS idx_changenow_swaps_exchange_id ON changenow_swaps(exchange_id);
                    CREATE INDEX IF NOT EXISTS idx_changenow_swaps_status ON changenow_swaps(swap_status);
                    CREATE INDEX IF NOT EXISTS idx_changenow_swaps_created_at ON changenow_swaps(created_at);
                """
                
                cur.execute(create_table_sql)
                print("✅ [INFO] ChangeNOW swaps table created/verified successfully")
                return True
                
        except Exception as e:
            print(f"❌ [ERROR] Failed to create changenow_swaps table: {e}")
            return False
    
    def record_swap_transaction(self, swap_data: Dict[str, Any]) -> Optional[int]:
        """
        Record a new swap transaction in the database.
        
        Args:
            swap_data: Dictionary containing swap transaction data
            
        Returns:
            The ID of the created record, or None if failed
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                insert_sql = """
                    INSERT INTO changenow_swaps 
                    (user_id, order_id, exchange_id, subscription_price_usd, swap_amount_usd,
                     eth_amount_sent, target_currency, client_wallet_address, expected_output,
                     eth_tx_hash, payin_address, swap_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                
                values = (
                    swap_data.get("user_id"),
                    swap_data.get("order_id"),
                    swap_data.get("exchange_id"),
                    swap_data.get("subscription_price_usd"),
                    swap_data.get("swap_amount_usd"),
                    swap_data.get("eth_amount_sent"),
                    swap_data.get("target_currency"),
                    swap_data.get("client_wallet_address"),
                    swap_data.get("expected_output"),
                    swap_data.get("eth_tx_hash"),
                    swap_data.get("payin_address"),
                    swap_data.get("swap_status", "pending")
                )
                
                cur.execute(insert_sql, values)
                record_id = cur.fetchone()[0]
                
                print(f"✅ [INFO] Swap transaction recorded with ID: {record_id}")
                print(f"📊 [INFO] Exchange ID: {swap_data.get('exchange_id')}")
                print(f"💰 [INFO] User: {swap_data.get('user_id')}, Amount: {swap_data.get('eth_amount_sent')} ETH → {swap_data.get('expected_output')} {swap_data.get('target_currency')}")
                
                return record_id
                
        except Exception as e:
            print(f"❌ [ERROR] Failed to record swap transaction: {e}")
            return None
    
    def update_swap_status(self, exchange_id: str, status: str, 
                          error_message: str = None, completed_at: datetime = None) -> bool:
        """
        Update the status of a swap transaction.
        
        Args:
            exchange_id: ChangeNOW exchange ID
            status: New status (pending, processing, finished, failed, refunded, etc.)
            error_message: Optional error message if status is failed
            completed_at: Optional completion timestamp
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                update_sql = """
                    UPDATE changenow_swaps 
                    SET swap_status = %s, updated_at = CURRENT_TIMESTAMP
                """
                values = [status]
                
                if error_message:
                    update_sql += ", error_message = %s"
                    values.append(error_message)
                
                if completed_at:
                    update_sql += ", completed_at = %s"
                    values.append(completed_at)
                elif status in ['finished', 'failed', 'refunded']:
                    update_sql += ", completed_at = CURRENT_TIMESTAMP"
                
                update_sql += " WHERE exchange_id = %s"
                values.append(exchange_id)
                
                cur.execute(update_sql, values)
                rows_affected = cur.rowcount
                
                if rows_affected > 0:
                    print(f"✅ [INFO] Swap status updated: {exchange_id} → {status}")
                    if error_message:
                        print(f"❌ [INFO] Error: {error_message}")
                    return True
                else:
                    print(f"⚠️ [WARNING] No swap found with exchange_id: {exchange_id}")
                    return False
                    
        except Exception as e:
            print(f"❌ [ERROR] Failed to update swap status: {e}")
            return False
    
    def get_swap_by_exchange_id(self, exchange_id: str) -> Optional[Dict[str, Any]]:
        """
        Get swap transaction details by exchange ID.
        
        Args:
            exchange_id: ChangeNOW exchange ID
            
        Returns:
            Dictionary with swap details or None if not found
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                select_sql = """
                    SELECT id, user_id, order_id, exchange_id, subscription_price_usd,
                           swap_amount_usd, eth_amount_sent, target_currency, 
                           client_wallet_address, expected_output, eth_tx_hash,
                           payin_address, swap_status, created_at, updated_at,
                           completed_at, error_message
                    FROM changenow_swaps 
                    WHERE exchange_id = %s
                """
                
                cur.execute(select_sql, (exchange_id,))
                row = cur.fetchone()
                
                if row:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
                else:
                    return None
                    
        except Exception as e:
            print(f"❌ [ERROR] Failed to get swap by exchange_id: {e}")
            return None
    
    def get_user_swaps(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get swap transactions for a specific user.
        
        Args:
            user_id: User's Telegram ID
            limit: Maximum number of records to return
            
        Returns:
            List of swap transaction dictionaries
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                select_sql = """
                    SELECT id, user_id, order_id, exchange_id, subscription_price_usd,
                           swap_amount_usd, eth_amount_sent, target_currency, 
                           client_wallet_address, expected_output, eth_tx_hash,
                           payin_address, swap_status, created_at, updated_at,
                           completed_at, error_message
                    FROM changenow_swaps 
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """
                
                cur.execute(select_sql, (user_id, limit))
                rows = cur.fetchall()
                
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            print(f"❌ [ERROR] Failed to get user swaps: {e}")
            return []
    
    def get_pending_swaps(self, older_than_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Get pending swap transactions that are older than specified minutes.
        
        Args:
            older_than_minutes: Consider swaps older than this many minutes
            
        Returns:
            List of pending swap transaction dictionaries
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                select_sql = """
                    SELECT id, user_id, order_id, exchange_id, subscription_price_usd,
                           swap_amount_usd, eth_amount_sent, target_currency, 
                           client_wallet_address, expected_output, eth_tx_hash,
                           payin_address, swap_status, created_at, updated_at,
                           completed_at, error_message
                    FROM changenow_swaps 
                    WHERE swap_status IN ('pending', 'processing')
                    AND created_at < NOW() - INTERVAL '%s minutes'
                    ORDER BY created_at ASC
                """
                
                cur.execute(select_sql, (older_than_minutes,))
                rows = cur.fetchall()
                
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            print(f"❌ [ERROR] Failed to get pending swaps: {e}")
            return []
    
    def get_swap_statistics(self) -> Dict[str, Any]:
        """
        Get swap transaction statistics.
        
        Returns:
            Dictionary with swap statistics
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                stats_sql = """
                    SELECT 
                        COUNT(*) as total_swaps,
                        COUNT(CASE WHEN swap_status = 'finished' THEN 1 END) as successful_swaps,
                        COUNT(CASE WHEN swap_status = 'failed' THEN 1 END) as failed_swaps,
                        COUNT(CASE WHEN swap_status IN ('pending', 'processing') THEN 1 END) as pending_swaps,
                        SUM(CASE WHEN swap_status = 'finished' THEN eth_amount_sent ELSE 0 END) as total_eth_swapped,
                        SUM(CASE WHEN swap_status = 'finished' THEN swap_amount_usd ELSE 0 END) as total_usd_swapped,
                        COUNT(DISTINCT target_currency) as unique_currencies,
                        COUNT(DISTINCT user_id) as unique_users
                    FROM changenow_swaps
                """
                
                cur.execute(stats_sql)
                row = cur.fetchone()
                
                if row:
                    columns = [desc[0] for desc in cur.description]
                    stats = dict(zip(columns, row))
                    
                    # Calculate success rate
                    if stats['total_swaps'] > 0:
                        stats['success_rate'] = (stats['successful_swaps'] / stats['total_swaps']) * 100
                    else:
                        stats['success_rate'] = 0.0
                    
                    return stats
                else:
                    return {}
                    
        except Exception as e:
            print(f"❌ [ERROR] Failed to get swap statistics: {e}")
            return {}