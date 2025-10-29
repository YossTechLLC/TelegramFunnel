#!/usr/bin/env python
"""
Database Manager for GCHostPay10-26 Host Wallet Payment Service.
Handles database operations for the split_payout_hostpay table.
Uses Google Cloud SQL Connector (mirroring GCSplit10-26 pattern).
"""
from typing import Optional

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
    Manages database connections and operations for GCHostPay10-26 service.
    Uses the same database as the main TelePay application.
    Uses Google Cloud SQL Connector (no connection pooling).
    """

    def __init__(self, instance_connection_name: str, db_name: str, db_user: str, db_password: str):
        """
        Initialize the DatabaseManager.

        Args:
            instance_connection_name: Cloud SQL instance connection name
            db_name: Database name
            db_user: Database user
            db_password: Database password
        """
        self.connection_name = instance_connection_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password

        print(f"🗄️ [DATABASE] DatabaseManager initialized")
        print(f"📊 [DATABASE] Instance: {instance_connection_name}")
        print(f"📊 [DATABASE] Database: {db_name}")
        print(f"📊 [DATABASE] User: {db_user}")

    def get_database_connection(self):
        """
        Create and return a database connection using Cloud SQL Connector.
        This mirrors the pattern from GCSplit10-26.

        Returns:
            Database connection object or None if failed
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [DATABASE] Cloud SQL Connector not available")
            return None

        if not all([self.db_name, self.db_user, self.db_password, self.connection_name]):
            print("❌ [DATABASE] Missing database credentials")
            return None

        try:
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
            print(f"❌ [DATABASE] Database connection failed: {e}")
            return None

    def insert_hostpay_transaction(self, unique_id: str, cn_api_id: str, from_currency: str,
                                   from_network: str, from_amount: float, payin_address: str,
                                   is_complete: bool = True, tx_hash: str = None, tx_status: str = None,
                                   gas_used: int = None, block_number: int = None) -> bool:
        """
        Insert a completed host payment transaction into split_payout_hostpay table.

        Args:
            unique_id: Database linking ID (16 chars)
            cn_api_id: ChangeNow transaction ID
            from_currency: Source currency (e.g., "eth")
            from_network: Source network (e.g., "eth")
            from_amount: Amount sent
            payin_address: ChangeNow deposit address
            is_complete: Payment completion status (default: True)
            tx_hash: Ethereum transaction hash (optional)
            tx_status: Transaction status ("success" or "failed") (optional)
            gas_used: Gas used by the transaction (optional)
            block_number: Block number where transaction was mined (optional)

        Returns:
            True if successful, False otherwise
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [HOSTPAY_DB] Cloud SQL Connector not available - cannot insert record")
            return False

        conn = None
        cur = None
        try:
            print(f"📝 [HOSTPAY_DB] Starting database insert for unique_id: {unique_id}")

            conn = self.get_database_connection()
            if not conn:
                print("❌ [HOSTPAY_DB] Could not establish database connection")
                return False

            cur = conn.cursor()

            # Insert into split_payout_hostpay table
            # NOTE: Database uses currency_type ENUM which expects UPPERCASE values
            # NOTE: from_amount is NUMERIC(12,8) - round to 8 decimal places to avoid precision errors

            # Round from_amount to 8 decimal places to match NUMERIC(12,8) constraint
            from_amount_rounded = round(float(from_amount), 8)

            # Validate cn_api_id length (table expects varchar(16))
            if len(cn_api_id) > 16:
                print(f"⚠️ [HOSTPAY_DB] cn_api_id too long ({len(cn_api_id)} chars), truncating to 16")
                cn_api_id = cn_api_id[:16]

            insert_query = """
                INSERT INTO split_payout_hostpay
                (unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address, is_complete, tx_hash, tx_status, gas_used, block_number)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            insert_params = (unique_id, cn_api_id, from_currency.upper(), from_network.upper(), from_amount_rounded, payin_address, is_complete, tx_hash, tx_status, gas_used, block_number)

            # Log exact values being inserted for debugging
            print(f"📋 [HOSTPAY_DB] Insert parameters:")
            print(f"   unique_id: {unique_id} (len: {len(unique_id)})")
            print(f"   cn_api_id: {cn_api_id} (len: {len(cn_api_id)})")
            print(f"   from_currency: {from_currency.upper()}")
            print(f"   from_network: {from_network.upper()}")
            print(f"   from_amount: {from_amount_rounded} (original: {from_amount})")
            print(f"   payin_address: {payin_address} (len: {len(payin_address)})")
            print(f"   is_complete: {is_complete}")
            print(f"   tx_hash: {tx_hash}")
            print(f"   tx_status: {tx_status}")
            print(f"   gas_used: {gas_used}")
            print(f"   block_number: {block_number}")

            print(f"🔄 [HOSTPAY_DB] Executing INSERT query")
            cur.execute(insert_query, insert_params)

            # Commit the transaction
            conn.commit()
            print(f"✅ [HOSTPAY_DB] Transaction committed successfully")

            print(f"🎉 [HOSTPAY_DB] Successfully inserted record for unique_id: {unique_id}")
            print(f"   🆔 CN API ID: {cn_api_id}")
            print(f"   💰 Currency: {from_currency.upper()}")
            print(f"   🌐 Network: {from_network.upper()}")
            print(f"   💰 Amount: {from_amount_rounded} {from_currency.upper()}")
            print(f"   🏦 Payin Address: {payin_address}")
            print(f"   ✔️ Is Complete: {is_complete}")
            print(f"   🔗 TX Hash: {tx_hash}")
            print(f"   📊 TX Status: {tx_status}")
            print(f"   ⛽ Gas Used: {gas_used}")
            print(f"   📦 Block Number: {block_number}")

            return True

        except Exception as e:
            # Rollback transaction on error
            if conn:
                try:
                    conn.rollback()
                    print(f"🔄 [HOSTPAY_DB] Transaction rolled back due to error")
                except Exception:
                    pass

            print(f"❌ [HOSTPAY_DB] Database error inserting hostpay transaction: {e}")
            return False

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [HOSTPAY_DB] Database connection closed")

    def check_transaction_exists(self, unique_id: str) -> bool:
        """
        Check if a transaction with the given unique_id already exists in split_payout_hostpay.

        Args:
            unique_id: Database linking ID to check

        Returns:
            True if exists, False otherwise
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [HOSTPAY_DB] Cloud SQL Connector not available - cannot check existence")
            return False

        conn = None
        cur = None
        try:
            conn = self.get_database_connection()
            if not conn:
                print("❌ [HOSTPAY_DB] Could not establish database connection")
                return False

            cur = conn.cursor()

            # Check if record exists
            check_query = """
                SELECT COUNT(*) FROM split_payout_hostpay WHERE unique_id = %s
            """
            cur.execute(check_query, (unique_id,))
            result = cur.fetchone()

            exists = result[0] > 0 if result else False

            if exists:
                print(f"⚠️ [HOSTPAY_DB] Transaction {unique_id} already exists in database")
            else:
                print(f"✅ [HOSTPAY_DB] Transaction {unique_id} does not exist - safe to insert")

            return exists

        except Exception as e:
            print(f"❌ [HOSTPAY_DB] Database error checking transaction existence: {e}")
            return False

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def update_transaction_status(self, tx_hash: str, status: str, block_number: int = None, gas_used: int = None) -> bool:
        """
        Update transaction status in split_payout_hostpay table using tx_hash.
        Used by Alchemy webhook handler to update confirmed transactions.

        Args:
            tx_hash: Transaction hash to look up
            status: Transaction status ("confirmed", "failed", "dropped")
            block_number: Block number where transaction was mined (optional)
            gas_used: Gas used by the transaction (optional)

        Returns:
            True if successful, False otherwise
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [HOSTPAY_DB] Cloud SQL Connector not available - cannot update status")
            return False

        conn = None
        cur = None
        try:
            print(f"📝 [HOSTPAY_DB] Updating transaction status for tx_hash: {tx_hash[:16]}...")

            conn = self.get_database_connection()
            if not conn:
                print("❌ [HOSTPAY_DB] Could not establish database connection")
                return False

            cur = conn.cursor()

            # Note: This assumes tx_hash column exists in split_payout_hostpay table
            # If the table doesn't have tx_hash column, this will need adjustment

            # Build update query dynamically based on provided fields
            update_fields = ["updated_at = NOW()"]
            params = []

            # Always update status if provided
            if status:
                update_fields.append("tx_status = %s")
                params.append(status)

            if block_number is not None:
                update_fields.append("block_number = %s")
                params.append(block_number)

            if gas_used is not None:
                update_fields.append("gas_used = %s")
                params.append(gas_used)

            # Add tx_hash as WHERE condition
            params.append(tx_hash)

            update_query = f"""
                UPDATE split_payout_hostpay
                SET {', '.join(update_fields)}
                WHERE tx_hash = %s
            """

            print("🔄 [HOSTPAY_DB] Executing UPDATE query")
            cur.execute(update_query, tuple(params))

            # Check how many rows were affected
            rows_affected = cur.rowcount

            # Commit the transaction
            conn.commit()
            print("✅ [HOSTPAY_DB] Transaction committed successfully")

            if rows_affected > 0:
                print("🎉 [HOSTPAY_DB] Successfully updated transaction status")
                print(f"   TX Hash: {tx_hash[:16]}...")
                print(f"   Status: {status}")
                if block_number:
                    print(f"   Block Number: {block_number}")
                if gas_used:
                    print(f"   Gas Used: {gas_used}")
                return True
            else:
                print(f"⚠️ [HOSTPAY_DB] No rows updated - tx_hash not found: {tx_hash[:16]}...")
                return False

        except Exception as e:
            # Rollback transaction on error
            if conn:
                try:
                    conn.rollback()
                    print("🔄 [HOSTPAY_DB] Transaction rolled back due to error")
                except Exception:
                    pass

            print(f"❌ [HOSTPAY_DB] Database error updating transaction status: {e}")
            return False

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print("🔌 [HOSTPAY_DB] Database connection closed")

    def get_unique_id_by_tx_hash(self, tx_hash: str) -> Optional[str]:
        """
        Look up unique_id by transaction hash.
        Used by Alchemy webhook handler to find the corresponding transaction.

        Args:
            tx_hash: Transaction hash to look up

        Returns:
            unique_id if found, None otherwise
        """
        if not CLOUD_SQL_AVAILABLE:
            print("❌ [HOSTPAY_DB] Cloud SQL Connector not available - cannot lookup unique_id")
            return None

        conn = None
        cur = None
        try:
            conn = self.get_database_connection()
            if not conn:
                print("❌ [HOSTPAY_DB] Could not establish database connection")
                return None

            cur = conn.cursor()

            # Query for unique_id by tx_hash
            lookup_query = """
                SELECT unique_id FROM split_payout_hostpay WHERE tx_hash = %s
            """
            cur.execute(lookup_query, (tx_hash,))
            result = cur.fetchone()

            if result:
                unique_id = result[0]
                print(f"✅ [HOSTPAY_DB] Found unique_id for tx_hash {tx_hash[:16]}...: {unique_id}")
                return unique_id
            else:
                print(f"⚠️ [HOSTPAY_DB] No record found for tx_hash: {tx_hash[:16]}...")
                return None

        except Exception as e:
            print(f"❌ [HOSTPAY_DB] Database error looking up unique_id: {e}")
            return None

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
