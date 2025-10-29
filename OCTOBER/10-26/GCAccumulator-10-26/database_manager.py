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

    def insert_payout_accumulation(
        self,
        client_id: str,
        user_id: int,
        subscription_id: int,
        payment_amount_usd: Decimal,
        payment_currency: str,
        payment_timestamp: str,
        accumulated_amount_usdt: Decimal,
        eth_to_usdt_rate: Decimal,
        conversion_timestamp: str,
        conversion_tx_hash: str,
        client_wallet_address: str,
        client_payout_currency: str,
        client_payout_network: str
    ) -> Optional[int]:
        """
        Insert a payment accumulation record.

        Args:
            client_id: open_channel_id from main_clients_database
            user_id: Telegram user who made payment
            subscription_id: FK to private_channel_users_database
            payment_amount_usd: What user originally paid
            payment_currency: Original payment currency
            payment_timestamp: When user paid
            accumulated_amount_usdt: Locked USDT value (eliminates volatility)
            eth_to_usdt_rate: Rate at conversion time
            conversion_timestamp: When ETH→USDT executed
            conversion_tx_hash: ChangeNow tx ID
            client_wallet_address: Client's payout wallet address
            client_payout_currency: Target currency (e.g., XMR)
            client_payout_network: Payout network

        Returns:
            Accumulation ID if successful, None if failed
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                print(f"💾 [DATABASE] Inserting payout accumulation record")
                print(f"👤 [DATABASE] User ID: {user_id}, Client ID: {client_id}")
                print(f"💰 [DATABASE] Payment Amount: ${payment_amount_usd}")
                print(f"💰 [DATABASE] USDT Accumulated: {accumulated_amount_usdt} USDT")

                cur.execute(
                    """INSERT INTO payout_accumulation (
                        client_id, user_id, subscription_id,
                        payment_amount_usd, payment_currency, payment_timestamp,
                        accumulated_amount_usdt, eth_to_usdt_rate,
                        conversion_timestamp, conversion_tx_hash,
                        client_wallet_address, client_payout_currency, client_payout_network
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id""",
                    (
                        client_id, user_id, subscription_id,
                        payment_amount_usd, payment_currency, payment_timestamp,
                        accumulated_amount_usdt, eth_to_usdt_rate,
                        conversion_timestamp, conversion_tx_hash,
                        client_wallet_address, client_payout_currency, client_payout_network
                    )
                )

                accumulation_id = cur.fetchone()[0]
                conn.commit()

                print(f"✅ [DATABASE] Accumulation record inserted successfully")
                print(f"🆔 [DATABASE] Accumulation ID: {accumulation_id}")

                return accumulation_id

        except Exception as e:
            print(f"❌ [DATABASE] Failed to insert accumulation record: {e}")
            return None

    def get_client_accumulation_total(self, client_id: str) -> Decimal:
        """
        Get total USDT accumulated for client (not yet paid out).

        Args:
            client_id: Client's open_channel_id

        Returns:
            Total USDT accumulated
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                print(f"📊 [DATABASE] Fetching accumulation total for client: {client_id}")

                cur.execute(
                    """SELECT COALESCE(SUM(accumulated_amount_usdt), 0)
                       FROM payout_accumulation
                       WHERE client_id = %s AND is_paid_out = FALSE""",
                    (client_id,)
                )

                total = cur.fetchone()[0]
                print(f"💰 [DATABASE] Client total accumulated: ${total} USDT")

                return Decimal(str(total))

        except Exception as e:
            print(f"❌ [DATABASE] Failed to fetch accumulation total: {e}")
            return Decimal('0')

    def get_client_threshold(self, client_id: str) -> Decimal:
        """
        Get payout threshold for client.

        Args:
            client_id: Client's open_channel_id

        Returns:
            Payout threshold in USD
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cur:
                print(f"🎯 [DATABASE] Fetching threshold for client: {client_id}")

                cur.execute(
                    """SELECT payout_threshold_usd
                       FROM main_clients_database
                       WHERE open_channel_id = %s""",
                    (client_id,)
                )

                result = cur.fetchone()
                threshold = Decimal(str(result[0])) if result else Decimal('0')

                print(f"🎯 [DATABASE] Client threshold: ${threshold}")

                return threshold

        except Exception as e:
            print(f"❌ [DATABASE] Failed to fetch client threshold: {e}")
            return Decimal('0')
