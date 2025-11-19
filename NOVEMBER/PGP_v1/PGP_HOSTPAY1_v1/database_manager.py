#!/usr/bin/env python
"""
Database Manager for PGP_HOSTPAY1_v1 Host Wallet Payment Service.
Handles database operations for the split_payout_hostpay table.
"""
from typing import Optional
from PGP_COMMON.database import BaseDatabaseManager

class DatabaseManager(BaseDatabaseManager):
    """
    Manages database connections and operations for PGP_HOSTPAY1_v1 service.
    Inherits common methods from BaseDatabaseManager.
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
        super().__init__(instance_connection_name, db_name, db_user, db_password, service_name="PGP_HOSTPAY1_v1")

    def get_database_connection(self):
        """Alias for get_connection() for backward compatibility"""
        return self.get_connection()

    # insert_hostpay_transaction() now inherited from BaseDatabaseManager ✅
    # Removed duplicate method - now using shared implementation from PGP_COMMON

    def check_transaction_exists(self, unique_id: str) -> bool:
        """
        Check if a transaction with the given unique_id already exists in split_payout_hostpay.

        Args:
            unique_id: Database linking ID to check

        Returns:
            True if exists, False otherwise
        """
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
