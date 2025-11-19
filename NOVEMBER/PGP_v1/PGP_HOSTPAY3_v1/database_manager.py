#!/usr/bin/env python
"""
Database Manager for PGP_HOSTPAY3_v1 Host Wallet Payment Service.
Handles database operations for the split_payout_hostpay table.
"""
from typing import Optional, List, Dict, Any
import json
import time
from PGP_COMMON.database import BaseDatabaseManager

class DatabaseManager(BaseDatabaseManager):
    """
    Manages database connections and operations for PGP_HOSTPAY3_v1 service.
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
        super().__init__(instance_connection_name, db_name, db_user, db_password, service_name="PGP_HOSTPAY3_v1")

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

    # =====================================================================
    # FAILED TRANSACTIONS METHODS (NEW - Phase 2)
    # =====================================================================

    # insert_failed_transaction() now inherited from BaseDatabaseManager ✅
    # Removed duplicate method - now using shared implementation from PGP_COMMON

    def get_failed_transaction_by_unique_id(self, unique_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a failed transaction by unique_id.

        Args:
            unique_id: Unique payment identifier

        Returns:
            Dict with transaction details or None if not found
        """
        conn = None
        cur = None

        try:
            print(f"🔍 [FAILED_TX] Looking up failed transaction: {unique_id}")

            conn = self.get_database_connection()
            if not conn:
                print(f"❌ [FAILED_TX] Database connection failed")
                return None

            cur = conn.cursor()

            query = """
                SELECT
                    id,
                    unique_id,
                    cn_api_id,
                    from_currency,
                    from_network,
                    from_amount,
                    payin_address,
                    context,
                    error_code,
                    error_message,
                    last_error_details,
                    attempt_count,
                    last_attempt_timestamp,
                    status,
                    retry_count,
                    last_retry_attempt,
                    recovery_tx_hash,
                    recovered_at,
                    recovered_by,
                    admin_notes,
                    created_at,
                    updated_at
                FROM failed_transactions
                WHERE unique_id = %s
            """

            cur.execute(query, (unique_id,))
            row = cur.fetchone()

            if not row:
                print(f"⚠️ [FAILED_TX] Failed transaction not found: {unique_id}")
                return None

            # Parse JSONB error_details back to dict
            error_details = json.loads(row[10]) if row[10] else {}

            result = {
                'id': row[0],
                'unique_id': row[1],
                'cn_api_id': row[2],
                'from_currency': row[3],
                'from_network': row[4],
                'from_amount': float(row[5]),
                'payin_address': row[6],
                'context': row[7],
                'error_code': row[8],
                'error_message': row[9],
                'last_error_details': error_details,
                'attempt_count': row[11],
                'last_attempt_timestamp': row[12],
                'status': row[13],
                'retry_count': row[14],
                'last_retry_attempt': row[15],
                'recovery_tx_hash': row[16],
                'recovered_at': row[17],
                'recovered_by': row[18],
                'admin_notes': row[19],
                'created_at': row[20],
                'updated_at': row[21]
            }

            print(f"✅ [FAILED_TX] Failed transaction found: {result['error_code']} ({result['status']})")
            return result

        except Exception as e:
            print(f"❌ [FAILED_TX] Database error: {e}")
            return None

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def update_failed_transaction_status(
        self,
        unique_id: str,
        status: str,
        admin_notes: Optional[str] = None
    ) -> bool:
        """
        Update status of a failed transaction.

        Args:
            unique_id: Unique payment identifier
            status: New status value
            admin_notes: Optional admin notes

        Returns:
            True if successful, False otherwise
        """
        conn = None
        cur = None

        try:
            print(f"💾 [FAILED_TX] Updating status for {unique_id}: {status}")

            conn = self.get_database_connection()
            if not conn:
                print(f"❌ [FAILED_TX] Database connection failed")
                return False

            cur = conn.cursor()

            if admin_notes:
                query = """
                    UPDATE failed_transactions
                    SET status = %s, admin_notes = %s, updated_at = NOW()
                    WHERE unique_id = %s
                """
                cur.execute(query, (status, admin_notes, unique_id))
            else:
                query = """
                    UPDATE failed_transactions
                    SET status = %s, updated_at = NOW()
                    WHERE unique_id = %s
                """
                cur.execute(query, (status, unique_id))

            conn.commit()
            print(f"✅ [FAILED_TX] Status updated successfully")
            return True

        except Exception as e:
            print(f"❌ [FAILED_TX] Database error: {e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def get_retryable_failed_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get failed transactions with retryable status.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of dicts with transaction details
        """
        conn = None
        cur = None

        try:
            print(f"🔍 [FAILED_TX] Fetching retryable failed transactions (limit: {limit})")

            conn = self.get_database_connection()
            if not conn:
                print(f"❌ [FAILED_TX] Database connection failed")
                return []

            cur = conn.cursor()

            query = """
                SELECT
                    unique_id,
                    cn_api_id,
                    from_currency,
                    from_network,
                    from_amount,
                    payin_address,
                    context,
                    error_code,
                    status,
                    retry_count
                FROM failed_transactions
                WHERE status = 'failed_retryable'
                ORDER BY created_at ASC
                LIMIT %s
            """

            cur.execute(query, (limit,))
            rows = cur.fetchall()

            results = []
            for row in rows:
                results.append({
                    'unique_id': row[0],
                    'cn_api_id': row[1],
                    'from_currency': row[2],
                    'from_network': row[3],
                    'from_amount': float(row[4]),
                    'payin_address': row[5],
                    'context': row[6],
                    'error_code': row[7],
                    'status': row[8],
                    'retry_count': row[9]
                })

            print(f"✅ [FAILED_TX] Found {len(results)} retryable transaction(s)")
            return results

        except Exception as e:
            print(f"❌ [FAILED_TX] Database error: {e}")
            return []

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def mark_failed_transaction_recovered(
        self,
        unique_id: str,
        recovery_tx_hash: str,
        recovered_by: str = "manual"
    ) -> bool:
        """
        Mark a failed transaction as recovered after successful retry.

        Args:
            unique_id: Unique payment identifier
            recovery_tx_hash: Ethereum transaction hash of successful retry
            recovered_by: Who/what recovered it (default: "manual")

        Returns:
            True if successful, False otherwise
        """
        conn = None
        cur = None

        try:
            print(f"💾 [FAILED_TX] Marking transaction as recovered: {unique_id}")
            print(f"🔗 [FAILED_TX] Recovery TX: {recovery_tx_hash}")

            conn = self.get_database_connection()
            if not conn:
                print(f"❌ [FAILED_TX] Database connection failed")
                return False

            cur = conn.cursor()

            query = """
                UPDATE failed_transactions
                SET
                    status = 'recovered',
                    recovery_tx_hash = %s,
                    recovered_at = NOW(),
                    recovered_by = %s,
                    updated_at = NOW()
                WHERE unique_id = %s
            """

            cur.execute(query, (recovery_tx_hash, recovered_by, unique_id))
            conn.commit()
            print(f"✅ [FAILED_TX] Transaction marked as recovered")
            return True

        except Exception as e:
            print(f"❌ [FAILED_TX] Database error: {e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
