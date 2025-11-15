#!/usr/bin/env python
"""
Database Manager for GCBatchProcessor-10-26 (Batch Payout Processor Service).
Handles database connections and operations for payout_batches and payout_accumulation tables.
"""
from decimal import Decimal
from typing import List, Dict, Optional
from google.cloud.sql.connector import Connector


class DatabaseManager:
    """
    Manages database connections and operations for GCBatchProcessor-10-26.
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
        self.instance_connection_name = instance_connection_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.connector = Connector()

        print(f"🗄️ [DATABASE] DatabaseManager initialized")
        print(f"📊 [DATABASE] Instance: {instance_connection_name}")
        print(f"📊 [DATABASE] Database: {db_name}")

    def get_connection(self):
        """
        Create and return a database connection using Cloud SQL Connector.

        Returns:
            Database connection object or None if failed
        """
        try:
            connection = self.connector.connect(
                self.instance_connection_name,
                "pg8000",
                user=self.db_user,
                password=self.db_password,
                db=self.db_name
            )
            print(f"🔗 [DATABASE] Connection established successfully")
            return connection

        except Exception as e:
            print(f"❌ [DATABASE] Connection failed: {e}")
            return None

    def find_clients_over_threshold(self) -> List[Dict]:
        """
        Find clients with accumulated USDT >= threshold.

        Returns:
            List of client data dictionaries
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return []

            cur = conn.cursor()
            print(f"🔍 [DATABASE] Searching for clients over threshold")

            # Debug: Check total unpaid records
            cur.execute("SELECT COUNT(*) FROM payout_accumulation WHERE is_paid_out = FALSE")
            unpaid_count = cur.fetchone()[0]
            print(f"🔍 [DATABASE DEBUG] Total unpaid accumulation records: {unpaid_count}")

            # Debug: Check if JOIN works
            cur.execute("""
                SELECT COUNT(*)
                FROM payout_accumulation pa
                JOIN main_clients_database mc ON pa.client_id = mc.closed_channel_id
                WHERE pa.is_paid_out = FALSE
            """)
            join_count = cur.fetchone()[0]
            print(f"🔍 [DATABASE DEBUG] Records after JOIN: {join_count}")

            # Debug: Show aggregated values before HAVING
            cur.execute("""
                SELECT
                    pa.client_id,
                    SUM(pa.accumulated_amount_usdt) as total_usdt,
                    COUNT(*) as payment_count,
                    mc.payout_threshold_usd as threshold
                FROM payout_accumulation pa
                JOIN main_clients_database mc ON pa.client_id = mc.closed_channel_id
                WHERE pa.is_paid_out = FALSE
                GROUP BY pa.client_id, mc.payout_threshold_usd
            """)
            agg_results = cur.fetchall()
            print(f"🔍 [DATABASE DEBUG] Aggregated clients (before HAVING): {len(agg_results)}")
            for row in agg_results:
                is_over = row[1] >= row[3] if row[3] is not None else False
                print(f"🔍 [DATABASE DEBUG]   Client {row[0]}: ${row[1]} / ${row[3]} (over: {is_over})")

            # Main query with HAVING clause
            cur.execute(
                """SELECT
                    pa.client_id,
                    pa.client_wallet_address,
                    pa.client_payout_currency,
                    pa.client_payout_network,
                    SUM(pa.accumulated_amount_usdt) as total_usdt,
                    COUNT(*) as payment_count,
                    mc.payout_threshold_usd as threshold
                FROM payout_accumulation pa
                JOIN main_clients_database mc ON pa.client_id = mc.closed_channel_id
                WHERE pa.is_paid_out = FALSE
                GROUP BY
                    pa.client_id,
                    pa.client_wallet_address,
                    pa.client_payout_currency,
                    pa.client_payout_network,
                    mc.payout_threshold_usd
                HAVING SUM(pa.accumulated_amount_usdt) >= mc.payout_threshold_usd"""
            )

            results = []
            for row in cur.fetchall():
                results.append({
                    'client_id': row[0],
                    'wallet_address': row[1],
                    'payout_currency': row[2],
                    'payout_network': row[3],
                    'total_usdt': Decimal(str(row[4])),
                    'payment_count': row[5],
                    'threshold': Decimal(str(row[6]))
                })

            cur.close()
            print(f"✅ [DATABASE] Found {len(results)} client(s) over threshold")

            return results

        except Exception as e:
            print(f"❌ [DATABASE] Failed to find clients over threshold: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def create_payout_batch(
        self,
        batch_id: str,
        client_id: str,
        total_amount_usdt: Decimal,
        total_payments_count: int,
        client_wallet_address: str,
        client_payout_currency: str,
        client_payout_network: str
    ) -> bool:
        """
        Create a batch payout record.

        Args:
            batch_id: UUID for batch
            client_id: Client's open_channel_id
            total_amount_usdt: Total USDT accumulated
            total_payments_count: Number of payments batched
            client_wallet_address: Client's payout wallet
            client_payout_currency: Target currency
            client_payout_network: Payout network

        Returns:
            True if successful, False if failed
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return False

            cur = conn.cursor()
            print(f"💾 [DATABASE] Creating batch record")
            print(f"🆔 [DATABASE] Batch ID: {batch_id}")
            print(f"🏢 [DATABASE] Client ID: {client_id}")
            print(f"💰 [DATABASE] Total USDT: ${total_amount_usdt}")
            print(f"📊 [DATABASE] Payment Count: {total_payments_count}")

            cur.execute(
                """INSERT INTO payout_batches (
                    batch_id, client_id,
                    total_amount_usdt, total_payments_count,
                    client_wallet_address, client_payout_currency, client_payout_network,
                    status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')""",
                (
                    batch_id, client_id,
                    total_amount_usdt, total_payments_count,
                    client_wallet_address, client_payout_currency, client_payout_network
                )
            )
            conn.commit()
            cur.close()

            print(f"✅ [DATABASE] Batch record created successfully")

            return True

        except Exception as e:
            print(f"❌ [DATABASE] Failed to create batch record: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def update_batch_status(self, batch_id: str, status: str) -> bool:
        """
        Update batch status.

        Args:
            batch_id: Batch ID
            status: New status (pending/processing/completed/failed)

        Returns:
            True if successful, False if failed
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return False

            cur = conn.cursor()
            print(f"🔄 [DATABASE] Updating batch {batch_id} status to: {status}")

            cur.execute(
                """UPDATE payout_batches
                   SET status = %s,
                       processing_started_at = CASE WHEN %s = 'processing' THEN NOW() ELSE processing_started_at END,
                       completed_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE completed_at END
                   WHERE batch_id = %s""",
                (status, status, status, batch_id)
            )
            conn.commit()
            rowcount = cur.rowcount
            cur.close()

            print(f"✅ [DATABASE] Batch status updated successfully")

            return rowcount > 0

        except Exception as e:
            print(f"❌ [DATABASE] Failed to update batch status: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def mark_accumulations_paid(self, client_id: str, batch_id: str) -> int:
        """
        Mark all unpaid accumulations for client as paid.

        Args:
            client_id: Client's open_channel_id
            batch_id: Batch ID to link

        Returns:
            Number of records updated
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return 0

            cur = conn.cursor()
            print(f"💾 [DATABASE] Marking accumulations as paid")
            print(f"🏢 [DATABASE] Client ID: {client_id}")
            print(f"🆔 [DATABASE] Batch ID: {batch_id}")

            cur.execute(
                """UPDATE payout_accumulation
                   SET is_paid_out = TRUE,
                       payout_batch_id = %s,
                       paid_out_at = NOW()
                   WHERE client_id = %s AND is_paid_out = FALSE""",
                (batch_id, client_id)
            )
            conn.commit()
            count = cur.rowcount
            cur.close()

            print(f"✅ [DATABASE] Marked {count} accumulation(s) as paid")

            return count

        except Exception as e:
            print(f"❌ [DATABASE] Failed to mark accumulations as paid: {e}")
            return 0
        finally:
            if conn:
                conn.close()

    def get_accumulated_actual_eth(self, client_id: str) -> float:
        """
        Get total ACTUAL ETH accumulated for a client (for threshold payouts).

        Sums all nowpayments_outcome_amount values from payout_accumulation
        for unpaid records.

        Args:
            client_id: Channel/client ID (closed_channel_id)

        Returns:
            Total actual ETH amount
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return 0.0

            cur = conn.cursor()
            print(f"💰 [DATABASE] Fetching accumulated ACTUAL ETH for client: {client_id}")

            cur.execute(
                """SELECT COALESCE(SUM(CAST(nowpayments_outcome_amount AS NUMERIC)), 0)
                   FROM payout_accumulation
                   WHERE client_id = %s
                     AND is_paid_out = FALSE
                     AND nowpayments_outcome_amount IS NOT NULL""",
                (client_id,)
            )

            result = cur.fetchone()
            total_eth = float(result[0]) if result and result[0] else 0.0

            cur.close()

            print(f"💰 [DATABASE] Total ACTUAL ETH for client {client_id}: {total_eth} ETH")

            return total_eth

        except Exception as e:
            print(f"❌ [DATABASE] Failed to get accumulated ACTUAL ETH: {e}")
            return 0.0
        finally:
            if conn:
                conn.close()
