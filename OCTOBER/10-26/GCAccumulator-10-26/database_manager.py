#!/usr/bin/env python
"""
Database Manager for GCAccumulator-10-26 (Payment Accumulation Service).
Handles database connections and operations for payout_accumulation table.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple
from google.cloud.sql.connector import Connector


class DatabaseManager:
    """
    Manages database connections and operations for GCAccumulator-10-26.
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

    def insert_payout_accumulation_pending(
        self,
        client_id: str,
        user_id: int,
        subscription_id: int,
        payment_amount_usd: Decimal,
        payment_currency: str,
        payment_timestamp: str,
        accumulated_eth: Decimal,
        client_wallet_address: str,
        client_payout_currency: str,
        client_payout_network: str,
        nowpayments_payment_id: str = None,
        nowpayments_pay_address: str = None,
        nowpayments_outcome_amount: str = None
    ) -> Optional[int]:
        """
        Insert a payment accumulation record with pending conversion status.

        Args:
            client_id: closed_channel_id from main_clients_database (private channel ID)
            user_id: Telegram user who made payment
            subscription_id: FK to private_channel_users_database
            payment_amount_usd: What user originally paid
            payment_currency: Original payment currency
            payment_timestamp: When user paid
            accumulated_eth: USD value pending conversion (parameter name kept for compatibility)
            client_wallet_address: Client's payout wallet address
            client_payout_currency: Target currency (e.g., XMR)
            client_payout_network: Payout network
            nowpayments_payment_id: NowPayments payment ID (optional, from IPN)
            nowpayments_pay_address: Customer's payment address (optional, from IPN)
            nowpayments_outcome_amount: Actual received amount (optional, from IPN)

        Returns:
            Accumulation ID if successful, None if failed
        """
        conn = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Failed to establish connection")
                return None

            cur = conn.cursor()
            print(f"💾 [DATABASE] Inserting payout accumulation record (pending conversion)")
            print(f"👤 [DATABASE] User ID: {user_id}, Client ID: {client_id}")
            print(f"💰 [DATABASE] Payment Amount: ${payment_amount_usd}")
            print(f"💰 [DATABASE] Accumulated USD: ${accumulated_eth} (pending conversion)")

            if nowpayments_payment_id:
                print(f"💳 [DATABASE] NowPayments Payment ID: {nowpayments_payment_id}")
                print(f"📬 [DATABASE] Pay Address: {nowpayments_pay_address}")
                print(f"💰 [DATABASE] Outcome Amount: {nowpayments_outcome_amount}")

            cur.execute(
                """INSERT INTO payout_accumulation (
                    client_id, user_id, subscription_id,
                    payment_amount_usd, payment_currency, payment_timestamp,
                    accumulated_amount_usdt, conversion_status,
                    client_wallet_address, client_payout_currency, client_payout_network,
                    nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id""",
                (
                    client_id, user_id, subscription_id,
                    payment_amount_usd, payment_currency, payment_timestamp,
                    accumulated_eth, 'pending',
                    client_wallet_address, client_payout_currency, client_payout_network,
                    nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount
                )
            )

            accumulation_id = cur.fetchone()[0]
            conn.commit()
            cur.close()

            print(f"✅ [DATABASE] Accumulation record inserted successfully (pending conversion)")
            print(f"🆔 [DATABASE] Accumulation ID: {accumulation_id}")

            if nowpayments_payment_id:
                print(f"🔗 [DATABASE] Linked to NowPayments payment_id: {nowpayments_payment_id}")

            return accumulation_id

        except Exception as e:
            print(f"❌ [DATABASE] Failed to insert accumulation record: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_client_accumulation_total(self, client_id: str) -> Decimal:
        """
        Get total USDT accumulated for client (not yet paid out).

        Args:
            client_id: Client's open_channel_id

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
                   WHERE client_id = %s AND is_paid_out = FALSE""",
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
            client_id: Client's closed_channel_id (stored in payout_accumulation.client_id)

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

    def update_accumulation_conversion_status(
        self,
        accumulation_id: int,
        conversion_status: str,
        cn_api_id: str,
        payin_address: str
    ) -> bool:
        """
        Update accumulation record with conversion status and swap details.

        Args:
            accumulation_id: Accumulation record ID
            conversion_status: Status ('swapping', 'completed', 'failed')
            cn_api_id: ChangeNow API transaction ID
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
            print(f"💾 [DATABASE] Updating accumulation conversion status")
            print(f"🆔 [DATABASE] Accumulation ID: {accumulation_id}")
            print(f"📊 [DATABASE] Status: {conversion_status}")
            print(f"🔗 [DATABASE] CN API ID: {cn_api_id}")

            cur.execute(
                """UPDATE payout_accumulation
                   SET conversion_status = %s,
                       cn_api_id = %s,
                       payin_address = %s,
                       updated_at = NOW()
                   WHERE id = %s""",
                (conversion_status, cn_api_id, payin_address, accumulation_id)
            )

            conn.commit()
            cur.close()

            print(f"✅ [DATABASE] Accumulation status updated")

            return True

        except Exception as e:
            print(f"❌ [DATABASE] Failed to update accumulation status: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def finalize_accumulation_conversion(
        self,
        accumulation_id: int,
        accumulated_amount_usdt: Decimal,
        conversion_tx_hash: str,
        conversion_status: str
    ) -> bool:
        """
        Finalize accumulation conversion with final USDT amount and tx hash.

        Args:
            accumulation_id: Accumulation record ID
            accumulated_amount_usdt: Final USDT amount received
            conversion_tx_hash: Blockchain transaction hash
            conversion_status: Final status ('completed' or 'failed')

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
            print(f"💾 [DATABASE] Finalizing accumulation conversion")
            print(f"🆔 [DATABASE] Accumulation ID: {accumulation_id}")
            print(f"💰 [DATABASE] Final USDT: ${accumulated_amount_usdt}")
            print(f"🔗 [DATABASE] TX Hash: {conversion_tx_hash}")
            print(f"📊 [DATABASE] Status: {conversion_status}")

            cur.execute(
                """UPDATE payout_accumulation
                   SET accumulated_amount_usdt = %s,
                       conversion_tx_hash = %s,
                       conversion_status = %s,
                       updated_at = NOW()
                   WHERE id = %s""",
                (accumulated_amount_usdt, conversion_tx_hash, conversion_status, accumulation_id)
            )

            conn.commit()
            cur.close()

            print(f"✅ [DATABASE] Accumulation conversion finalized")
            print(f"💰 [DATABASE] ${accumulated_amount_usdt} USDT locked in value - volatility protection active!")

            return True

        except Exception as e:
            print(f"❌ [DATABASE] Failed to finalize accumulation conversion: {e}")
            return False
        finally:
            if conn:
                conn.close()
