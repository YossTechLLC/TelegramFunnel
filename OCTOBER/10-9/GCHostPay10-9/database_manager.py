#!/usr/bin/env python
"""
Database Manager for HPW10-9 Host Payment Wallet Service.
Handles all PostgreSQL database operations for payment queue management.
"""
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from google.cloud import secretmanager
from google.cloud.sql.connector import Connector


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
        print(f"❌ [DATABASE] Error fetching DATABASE_NAME_SECRET: {e}")
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
        print(f"❌ [DATABASE] Error fetching DATABASE_USER_SECRET: {e}")
        raise


def fetch_database_password() -> str:
    """Fetch database password from Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv("DATABASE_PASSWORD_SECRET")
        if not secret_path:
            return None
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ [DATABASE] Error fetching DATABASE_PASSWORD_SECRET: {e}")
        return None


def fetch_cloud_sql_connection_name() -> str:
    """Fetch Cloud SQL connection name from environment variable."""
    try:
        connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME")
        if not connection_name:
            raise ValueError("Environment variable CLOUD_SQL_CONNECTION_NAME is not set.")
        return connection_name
    except Exception as e:
        print(f"❌ [DATABASE] Error fetching CLOUD_SQL_CONNECTION_NAME: {e}")
        raise


# Database configuration - using Secret Manager and environment variables
DB_CONNECTION_NAME = fetch_cloud_sql_connection_name()
DB_NAME = fetch_database_name()
DB_USER = fetch_database_user()
DB_PASSWORD = fetch_database_password()


class DatabaseManager:
    """
    Manages database operations for the host payment queue.
    Uses Cloud SQL Connector for secure database connections.
    """

    def __init__(self):
        self.connection_name = DB_CONNECTION_NAME
        self.dbname = DB_NAME
        self.user = DB_USER
        self.password = DB_PASSWORD

        # Validate critical credentials
        if not self.password:
            raise RuntimeError("Database password not available from Secret Manager.")
        if not self.connection_name or not self.dbname or not self.user:
            raise RuntimeError("Critical database configuration missing from Secret Manager or environment.")

    def get_connection(self):
        """Create and return a database connection using Cloud SQL Connector."""
        connector = Connector()
        connection = connector.connect(
            self.connection_name,
            "pg8000",
            user=self.user,
            password=self.password,
            db=self.dbname
        )
        return connection

    def insert_payment(self, payment_data: Dict[str, Any]) -> bool:
        """
        Insert a new payment into the queue.

        Args:
            payment_data: Dictionary containing payment information

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            insert_query = """
                INSERT INTO host_payment_queue
                (payment_id, order_id, changenow_tx_id, payin_address, expected_amount_eth, user_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (payment_id) DO NOTHING
            """

            values = (
                payment_data.get('payment_id'),
                payment_data.get('order_id'),
                payment_data.get('changenow_tx_id'),
                payment_data.get('payin_address'),
                payment_data.get('expected_amount_eth'),
                payment_data.get('user_id'),
                payment_data.get('status', 'pending')
            )

            cur.execute(insert_query, values)
            conn.commit()

            rows_affected = cur.rowcount
            cur.close()
            conn.close()

            if rows_affected > 0:
                print(f"✅ [DATABASE] Inserted payment: {payment_data.get('payment_id')}")
                return True
            else:
                print(f"⚠️ [DATABASE] Payment already exists: {payment_data.get('payment_id')}")
                return False

        except Exception as e:
            print(f"❌ [DATABASE] Error inserting payment: {e}")
            return False

    def get_pending_payments(self) -> List[Dict[str, Any]]:
        """
        Retrieve all pending or waiting_funds payments from the queue.

        Returns:
            List of payment dictionaries
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            select_query = """
                SELECT id, payment_id, order_id, changenow_tx_id, payin_address,
                       expected_amount_eth, actual_amount_received, status, tx_hash,
                       gas_price_gwei, gas_used, created_at, updated_at, error_message,
                       retry_count, user_id
                FROM host_payment_queue
                WHERE status IN ('pending', 'waiting_funds')
                ORDER BY created_at ASC
            """

            cur.execute(select_query)
            rows = cur.fetchall()

            payments = []
            for row in rows:
                payments.append({
                    'id': row[0],
                    'payment_id': row[1],
                    'order_id': row[2],
                    'changenow_tx_id': row[3],
                    'payin_address': row[4],
                    'expected_amount_eth': float(row[5]) if row[5] else 0.0,
                    'actual_amount_received': float(row[6]) if row[6] else None,
                    'status': row[7],
                    'tx_hash': row[8],
                    'gas_price_gwei': float(row[9]) if row[9] else None,
                    'gas_used': row[10],
                    'created_at': row[11],
                    'updated_at': row[12],
                    'error_message': row[13],
                    'retry_count': row[14],
                    'user_id': row[15]
                })

            cur.close()
            conn.close()

            print(f"📊 [DATABASE] Retrieved {len(payments)} pending payments")
            return payments

        except Exception as e:
            print(f"❌ [DATABASE] Error retrieving pending payments: {e}")
            return []

    def update_payment_status(self, payment_id: str, status: str,
                             tx_hash: Optional[str] = None,
                             gas_price_gwei: Optional[float] = None,
                             actual_amount: Optional[float] = None,
                             error_message: Optional[str] = None) -> bool:
        """
        Update the status of a payment in the queue.

        Args:
            payment_id: Payment identifier
            status: New status
            tx_hash: Ethereum transaction hash (optional)
            gas_price_gwei: Gas price in Gwei (optional)
            actual_amount: Actual amount received (optional)
            error_message: Error message if failed (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            update_query = """
                UPDATE host_payment_queue
                SET status = %s, updated_at = NOW(), tx_hash = %s,
                    gas_price_gwei = %s, actual_amount_received = %s, error_message = %s
                WHERE payment_id = %s
            """

            values = (status, tx_hash, gas_price_gwei, actual_amount, error_message, payment_id)
            cur.execute(update_query, values)
            conn.commit()

            rows_affected = cur.rowcount
            cur.close()
            conn.close()

            if rows_affected > 0:
                print(f"✅ [DATABASE] Updated payment {payment_id} status to {status}")
                return True
            else:
                print(f"⚠️ [DATABASE] No payment found with ID {payment_id}")
                return False

        except Exception as e:
            print(f"❌ [DATABASE] Error updating payment status: {e}")
            return False

    def increment_retry_count(self, payment_id: str) -> bool:
        """
        Increment the retry count for a payment.

        Args:
            payment_id: Payment identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            update_query = """
                UPDATE host_payment_queue
                SET retry_count = retry_count + 1, updated_at = NOW()
                WHERE payment_id = %s
            """

            cur.execute(update_query, (payment_id,))
            conn.commit()
            cur.close()
            conn.close()

            print(f"🔄 [DATABASE] Incremented retry count for payment {payment_id}")
            return True

        except Exception as e:
            print(f"❌ [DATABASE] Error incrementing retry count: {e}")
            return False

    def mark_as_sent(self, payment_id: str, tx_hash: str, gas_price_gwei: float, gas_used: int) -> bool:
        """
        Mark a payment as sent with transaction details.

        Args:
            payment_id: Payment identifier
            tx_hash: Ethereum transaction hash
            gas_price_gwei: Gas price in Gwei
            gas_used: Gas units consumed

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            update_query = """
                UPDATE host_payment_queue
                SET status = 'sent', tx_hash = %s, gas_price_gwei = %s,
                    gas_used = %s, updated_at = NOW()
                WHERE payment_id = %s
            """

            values = (tx_hash, gas_price_gwei, gas_used, payment_id)
            cur.execute(update_query, values)
            conn.commit()
            cur.close()
            conn.close()

            print(f"✅ [DATABASE] Marked payment {payment_id} as sent (tx: {tx_hash})")
            return True

        except Exception as e:
            print(f"❌ [DATABASE] Error marking payment as sent: {e}")
            return False

    def get_sent_payments(self) -> List[Dict[str, Any]]:
        """
        Retrieve all sent payments pending confirmation.

        Returns:
            List of payment dictionaries
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            select_query = """
                SELECT id, payment_id, order_id, changenow_tx_id, payin_address,
                       expected_amount_eth, tx_hash, gas_price_gwei, gas_used,
                       created_at, updated_at, user_id
                FROM host_payment_queue
                WHERE status = 'sent' AND tx_hash IS NOT NULL
                ORDER BY updated_at ASC
            """

            cur.execute(select_query)
            rows = cur.fetchall()

            payments = []
            for row in rows:
                payments.append({
                    'id': row[0],
                    'payment_id': row[1],
                    'order_id': row[2],
                    'changenow_tx_id': row[3],
                    'payin_address': row[4],
                    'expected_amount_eth': float(row[5]) if row[5] else 0.0,
                    'tx_hash': row[6],
                    'gas_price_gwei': float(row[7]) if row[7] else None,
                    'gas_used': row[8],
                    'created_at': row[9],
                    'updated_at': row[10],
                    'user_id': row[11]
                })

            cur.close()
            conn.close()

            print(f"📊 [DATABASE] Retrieved {len(payments)} sent payments")
            return payments

        except Exception as e:
            print(f"❌ [DATABASE] Error retrieving sent payments: {e}")
            return []

    def expire_old_payments(self, timeout_minutes: int = 120) -> int:
        """
        Mark payments as expired if they exceed the timeout.

        Args:
            timeout_minutes: Timeout in minutes (default: 120)

        Returns:
            Number of payments expired
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            expiration_time = datetime.now() - timedelta(minutes=timeout_minutes)

            update_query = """
                UPDATE host_payment_queue
                SET status = 'expired', updated_at = NOW(),
                    error_message = 'Payment timed out after ' || %s || ' minutes'
                WHERE status IN ('pending', 'waiting_funds')
                AND created_at < %s
            """

            cur.execute(update_query, (timeout_minutes, expiration_time))
            conn.commit()

            rows_affected = cur.rowcount
            cur.close()
            conn.close()

            if rows_affected > 0:
                print(f"⏰ [DATABASE] Expired {rows_affected} old payments")
            return rows_affected

        except Exception as e:
            print(f"❌ [DATABASE] Error expiring old payments: {e}")
            return 0

    def get_payment_by_id(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific payment by payment_id.

        Args:
            payment_id: Payment identifier

        Returns:
            Payment dictionary or None if not found
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            select_query = """
                SELECT id, payment_id, order_id, changenow_tx_id, payin_address,
                       expected_amount_eth, actual_amount_received, status, tx_hash,
                       gas_price_gwei, gas_used, created_at, updated_at, error_message,
                       retry_count, user_id
                FROM host_payment_queue
                WHERE payment_id = %s
            """

            cur.execute(select_query, (payment_id,))
            row = cur.fetchone()

            if row:
                payment = {
                    'id': row[0],
                    'payment_id': row[1],
                    'order_id': row[2],
                    'changenow_tx_id': row[3],
                    'payin_address': row[4],
                    'expected_amount_eth': float(row[5]) if row[5] else 0.0,
                    'actual_amount_received': float(row[6]) if row[6] else None,
                    'status': row[7],
                    'tx_hash': row[8],
                    'gas_price_gwei': float(row[9]) if row[9] else None,
                    'gas_used': row[10],
                    'created_at': row[11],
                    'updated_at': row[12],
                    'error_message': row[13],
                    'retry_count': row[14],
                    'user_id': row[15]
                }

                cur.close()
                conn.close()
                return payment
            else:
                cur.close()
                conn.close()
                return None

        except Exception as e:
            print(f"❌ [DATABASE] Error retrieving payment by ID: {e}")
            return None
