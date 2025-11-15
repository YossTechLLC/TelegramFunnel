#!/usr/bin/env python
"""
Database Manager for GCSplit2-10-26 (ETH→USDT Conversion Service).
Handles database connections and operations for updating payout_accumulation records.
Extends shared BaseDatabaseManager with service-specific operations.

Migration Date: 2025-11-15
Extends: _shared/database_manager_base.BaseDatabaseManager
"""
import sys
from datetime import datetime
from decimal import Decimal
from typing import Optional

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.database_manager_base import BaseDatabaseManager


class DatabaseManager(BaseDatabaseManager):
    """
    GCSplit2-specific database manager.
    Extends BaseDatabaseManager with payout_accumulation update operations.
    """

    def get_connection(self):
        """Alias for parent's get_database_connection()."""
        return self.get_database_connection()

    def update_accumulation_with_conversion(
        self,
        accumulation_id: int,
        accumulated_usdt: Decimal,
        eth_to_usdt_rate: Decimal,
        conversion_tx_hash: str
    ) -> bool:
        """
        Update payout_accumulation record with ETH→USDT conversion data.

        Args:
            accumulation_id: Database accumulation record ID
            accumulated_usdt: Converted USDT amount
            eth_to_usdt_rate: ETH to USDT conversion rate
            conversion_tx_hash: ChangeNow transaction ID

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
            print(f"💾 [DATABASE] Updating accumulation record with conversion data")
            print(f"🆔 [DATABASE] Accumulation ID: {accumulation_id}")
            print(f"💰 [DATABASE] USDT: {accumulated_usdt}")
            print(f"📊 [DATABASE] Rate: {eth_to_usdt_rate}")

            cur.execute(
                """UPDATE payout_accumulation SET
                    accumulated_amount_usdt = %s,
                    eth_to_usdt_rate = %s,
                    conversion_tx_hash = %s,
                    conversion_timestamp = %s,
                    conversion_status = %s,
                    conversion_attempts = conversion_attempts + 1,
                    last_conversion_attempt = %s
                WHERE id = %s""",
                (
                    accumulated_usdt,
                    eth_to_usdt_rate,
                    conversion_tx_hash,
                    datetime.now().isoformat(),
                    'completed',
                    datetime.now().isoformat(),
                    accumulation_id
                )
            )

            conn.commit()
            cur.close()

            print(f"✅ [DATABASE] Accumulation record updated successfully")
            return True

        except Exception as e:
            print(f"❌ [DATABASE] Failed to update accumulation record: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_client_accumulation_total(self, client_id: str) -> Decimal:
        """
        Get total USDT accumulated for client (not yet paid out).

        Args:
            client_id: Client's closed_channel_id

        Returns:
            Total USDT accumulated
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return Decimal('0')

            cur = conn.cursor()
            print(f"📊 [DATABASE] Fetching accumulation total for client: {client_id}")

            cur.execute(
                """SELECT COALESCE(SUM(accumulated_amount_usdt), 0)
                   FROM payout_accumulation
                   WHERE client_id = %s
                     AND is_paid_out = FALSE
                     AND conversion_status = 'completed'""",
                (client_id,)
            )

            total = cur.fetchone()[0]
            cur.close()
            print(f"💰 [DATABASE] Client total accumulated: ${total} USDT")

            return Decimal(str(total))

        except Exception as e:
            print(f"❌ [DATABASE] Failed to fetch accumulation total: {e}")
            return Decimal('0')
        finally:
            if conn:
                conn.close()

    def get_client_threshold(self, client_id: str) -> Decimal:
        """
        Get payout threshold for client.

        Args:
            client_id: Client's closed_channel_id

        Returns:
            Payout threshold in USD
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return Decimal('0')

            cur = conn.cursor()
            print(f"🎯 [DATABASE] Fetching threshold for client: {client_id}")

            cur.execute(
                """SELECT payout_threshold_usd
                   FROM main_clients_database
                   WHERE closed_channel_id = %s""",
                (client_id,)
            )

            result = cur.fetchone()
            threshold = Decimal(str(result[0])) if result else Decimal('0')
            cur.close()

            print(f"🎯 [DATABASE] Client threshold: ${threshold}")

            return threshold

        except Exception as e:
            print(f"❌ [DATABASE] Failed to fetch client threshold: {e}")
            return Decimal('0')
        finally:
            if conn:
                conn.close()
