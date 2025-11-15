#!/usr/bin/env python
"""
Database Manager for PGP_MICROBATCHPROCESSOR_v1 (Micro-Batch Conversion Service).
Handles database connections and operations for batch_conversions and payout_accumulation tables.
"""
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Optional, List, Dict
from PGP_COMMON.database import BaseDatabaseManager


class DatabaseManager(BaseDatabaseManager):
    """
    Manages database connections and operations for PGP_MICROBATCHPROCESSOR_v1.
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
        super().__init__(
            instance_connection_name=instance_connection_name,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            service_name="PGP_MICROBATCHPROCESSOR_v1"
        )

        # Set high precision for Decimal calculations
        getcontext().prec = 28

    def get_database_connection(self):
        """Alias for backward compatibility"""
        return self.get_connection()


    def get_total_pending_usd(self) -> Decimal:
        """
        Get total USD accumulated across all pending payments.

        Returns:
            Decimal total pending USD
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return Decimal('0')

            cur = conn.cursor()
            print(f"🔍 [DATABASE] Querying total pending USD")

            # Query accumulated_amount_usdt (stores pending USD value for unconverted payments)
            # For pending records, this stores the adjusted USD amount awaiting batch conversion
            # After batch completes, it stores the final USDT share
            cur.execute(
                """SELECT COALESCE(SUM(accumulated_amount_usdt), 0) as total_pending
                   FROM payout_accumulation
                   WHERE conversion_status = 'pending'"""
            )

            result = cur.fetchone()
            total_pending = Decimal(str(result[0])) if result else Decimal('0')

            print(f"💰 [DATABASE] Total pending USD: ${total_pending}")

            cur.close()
            conn.close()
            return total_pending

        except Exception as e:
            print(f"❌ [DATABASE] Query error: {e}")
            if conn:
                conn.close()
            return Decimal('0')

    def get_all_pending_records(self) -> List[Dict]:
        """
        Fetch all pending payment records for batch processing.

        Returns:
            List of dicts with id, accumulated_amount_usdt, client_id, user_id, etc.
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return []

            cur = conn.cursor()
            print(f"🔍 [DATABASE] Fetching all pending payment records")

            # Query accumulated_amount_usdt (stores pending USD value for unconverted payments)
            # For pending records, this stores the adjusted USD amount awaiting batch conversion
            cur.execute(
                """SELECT id, accumulated_amount_usdt, client_id, user_id,
                          client_wallet_address, client_payout_currency, client_payout_network
                   FROM payout_accumulation
                   WHERE conversion_status = 'pending'
                   ORDER BY created_at ASC"""
            )

            rows = cur.fetchall()
            records = []

            for row in rows:
                records.append({
                    'id': row[0],
                    'accumulated_amount_usdt': Decimal(str(row[1])),  # Pending USD value
                    'client_id': row[2],
                    'user_id': row[3],
                    'client_wallet_address': row[4],
                    'client_payout_currency': row[5],
                    'client_payout_network': row[6]
                })

            print(f"📊 [DATABASE] Found {len(records)} pending record(s)")

            cur.close()
            conn.close()
            return records

        except Exception as e:
            print(f"❌ [DATABASE] Query error: {e}")
            if conn:
                conn.close()
            return []

    def create_batch_conversion(
        self,
        batch_conversion_id: str,
        total_eth_usd: Decimal,
        threshold: Decimal,
        cn_api_id: str,
        payin_address: str
    ) -> bool:
        """
        Create batch_conversions record.

        Args:
            batch_conversion_id: UUID for this batch
            total_eth_usd: Total USD being converted
            threshold: Threshold value at creation time
            cn_api_id: ChangeNow API ID
            payin_address: ChangeNow payin address

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
            print(f"💾 [DATABASE] Creating batch_conversions record")
            print(f"🆔 [DATABASE] Batch ID: {batch_conversion_id}")
            print(f"💰 [DATABASE] Total: ${total_eth_usd}")

            cur.execute(
                """INSERT INTO batch_conversions (
                    batch_conversion_id, total_eth_usd, threshold_at_creation,
                    cn_api_id, payin_address, conversion_status, processing_started_at
                ) VALUES (%s, %s, %s, %s, %s, 'swapping', NOW())""",
                (batch_conversion_id, str(total_eth_usd), str(threshold), cn_api_id, payin_address)
            )

            conn.commit()
            print(f"✅ [DATABASE] Batch conversion record created")

            cur.close()
            conn.close()
            return True

        except Exception as e:
            print(f"❌ [DATABASE] Insert error: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False

    def update_records_to_swapping(self, batch_conversion_id: str) -> bool:
        """
        Update all pending records to 'swapping' status with batch_conversion_id.

        Args:
            batch_conversion_id: UUID of the batch

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
            print(f"💾 [DATABASE] Updating pending records to 'swapping'")

            cur.execute(
                """UPDATE payout_accumulation
                   SET conversion_status = 'swapping',
                       batch_conversion_id = %s,
                       updated_at = NOW()
                   WHERE conversion_status = 'pending'""",
                (batch_conversion_id,)
            )

            rows_updated = cur.rowcount
            conn.commit()

            print(f"✅ [DATABASE] Updated {rows_updated} record(s) to 'swapping'")

            cur.close()
            conn.close()
            return True

        except Exception as e:
            print(f"❌ [DATABASE] Update error: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False

    def get_records_by_batch(self, batch_conversion_id: str) -> List[Dict]:
        """
        Fetch all records for a batch_conversion_id.

        Args:
            batch_conversion_id: UUID of the batch

        Returns:
            List of dicts with id, accumulated_eth
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return []

            cur = conn.cursor()
            print(f"🔍 [DATABASE] Fetching records for batch {batch_conversion_id}")

            # Query accumulated_amount_usdt (stores pending USD value for unconverted payments)
            # For records in a batch, this will still have the original USD amount
            cur.execute(
                """SELECT id, accumulated_amount_usdt
                   FROM payout_accumulation
                   WHERE batch_conversion_id = %s""",
                (batch_conversion_id,)
            )

            rows = cur.fetchall()
            records = []

            for row in rows:
                records.append({
                    'id': row[0],
                    'accumulated_amount_usdt': Decimal(str(row[1]))
                })

            print(f"📊 [DATABASE] Found {len(records)} record(s) in batch")

            cur.close()
            conn.close()
            return records

        except Exception as e:
            print(f"❌ [DATABASE] Query error: {e}")
            if conn:
                conn.close()
            return []

    def distribute_usdt_proportionally(
        self,
        pending_records: List[Dict],
        actual_usdt_received: Decimal
    ) -> List[Dict]:
        """
        Distribute actual USDT received proportionally across pending records.

        Formula: usdt_share_i = (payment_i / total_pending) × actual_usdt_received

        Args:
            pending_records: List of dicts with 'id' and 'accumulated_amount_usdt'
            actual_usdt_received: Total USDT received from ChangeNow

        Returns:
            List of dicts with 'id' and 'usdt_share'
        """
        try:
            if not pending_records:
                print(f"⚠️ [DISTRIBUTION] No pending records to distribute")
                return []

            # Calculate total pending
            total_pending = sum(Decimal(str(r['accumulated_amount_usdt'])) for r in pending_records)

            print(f"💰 [DISTRIBUTION] Total pending: ${total_pending}")
            print(f"💰 [DISTRIBUTION] Actual USDT received: ${actual_usdt_received}")

            distributions = []
            running_total = Decimal('0')

            for i, record in enumerate(pending_records):
                record_usd = Decimal(str(record['accumulated_amount_usdt']))

                # Last record gets remainder to avoid rounding errors
                if i == len(pending_records) - 1:
                    usdt_share = actual_usdt_received - running_total
                else:
                    usdt_share = (record_usd / total_pending) * actual_usdt_received
                    running_total += usdt_share

                percentage = (record_usd / total_pending) * 100

                distributions.append({
                    'id': record['id'],
                    'usdt_share': usdt_share,
                    'percentage': percentage
                })

                print(f"📊 [DISTRIBUTION] Record {record['id']}: "
                      f"${record_usd} ({percentage:.2f}%) → ${usdt_share} USDT")

            # Verification
            total_distributed = sum(d['usdt_share'] for d in distributions)
            print(f"✅ [DISTRIBUTION] Verification: ${total_distributed} = ${actual_usdt_received}")

            if abs(total_distributed - actual_usdt_received) > Decimal('0.01'):
                print(f"⚠️ [DISTRIBUTION] Rounding error detected: ${abs(total_distributed - actual_usdt_received)}")

            return distributions

        except Exception as e:
            print(f"❌ [DISTRIBUTION] Calculation error: {e}")
            return []

    def update_record_usdt_share(
        self,
        record_id: int,
        usdt_share: Decimal,
        tx_hash: str
    ) -> bool:
        """
        Update individual record with USDT share and mark completed.

        Args:
            record_id: Payout accumulation record ID
            usdt_share: Proportional USDT share
            tx_hash: Transaction hash

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

            cur.execute(
                """UPDATE payout_accumulation
                   SET accumulated_amount_usdt = %s,
                       conversion_status = 'completed',
                       conversion_tx_hash = %s,
                       updated_at = NOW()
                   WHERE id = %s""",
                (str(usdt_share), tx_hash, record_id)
            )

            conn.commit()

            cur.close()
            conn.close()
            return True

        except Exception as e:
            print(f"❌ [DATABASE] Update error for record {record_id}: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False

    def finalize_batch_conversion(
        self,
        batch_conversion_id: str,
        actual_usdt_received: Decimal,
        tx_hash: str
    ) -> bool:
        """
        Mark batch_conversion as completed.

        Args:
            batch_conversion_id: UUID of the batch
            actual_usdt_received: Actual USDT received from swap
            tx_hash: Transaction hash

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
            print(f"💾 [DATABASE] Finalizing batch conversion {batch_conversion_id}")

            cur.execute(
                """UPDATE batch_conversions
                   SET actual_usdt_received = %s,
                       conversion_tx_hash = %s,
                       conversion_status = 'completed',
                       completed_at = NOW()
                   WHERE batch_conversion_id = %s""",
                (str(actual_usdt_received), tx_hash, batch_conversion_id)
            )

            conn.commit()
            print(f"✅ [DATABASE] Batch conversion finalized")

            cur.close()
            conn.close()
            return True

        except Exception as e:
            print(f"❌ [DATABASE] Update error: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False

    def get_total_pending_actual_eth(self) -> float:
        """
        Get total ACTUAL ETH from nowpayments_outcome_amount for pending conversions.

        This sums all actual ETH received from NowPayments for payments
        awaiting micro-batch conversion.

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
            print(f"🔍 [DATABASE] Querying total pending ACTUAL ETH")

            cur.execute(
                """SELECT COALESCE(SUM(CAST(nowpayments_outcome_amount AS NUMERIC)), 0)
                   FROM payout_accumulation
                   WHERE conversion_status = 'pending'
                     AND nowpayments_outcome_amount IS NOT NULL"""
            )

            result = cur.fetchone()
            total_eth = float(result[0]) if result and result[0] else 0.0

            print(f"💰 [DATABASE] Total pending ACTUAL ETH: {total_eth} ETH")

            cur.close()
            conn.close()
            return total_eth

        except Exception as e:
            print(f"❌ [DATABASE] Query error: {e}")
            if conn:
                conn.close()
            return 0.0
