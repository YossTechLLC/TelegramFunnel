#!/usr/bin/env python
"""
Database Manager for GCPaymentGateway-10-26
Handles all database operations using psycopg2
"""

import psycopg2
from typing import Optional, Dict, Any, Tuple


class DatabaseManager:
    """
    Manages database connections and operations for the payment gateway.
    Uses direct psycopg2 connections (not Cloud SQL Connector).
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the DatabaseManager with configuration.

        Args:
            config: Configuration dictionary containing database credentials
        """
        self.host = config.get("database_host")
        self.port = config.get("database_port", 5432)
        self.dbname = config.get("database_name")
        self.user = config.get("database_user")
        self.password = config.get("database_password")

        # Validate configuration
        if not all([self.host, self.dbname, self.user, self.password]):
            raise ValueError("Incomplete database configuration")

        print(f"✅ [DATABASE] Initialized with host={self.host}, db={self.dbname}")

    def get_connection(self):
        """
        Create and return a database connection.

        Returns:
            psycopg2 connection object

        Raises:
            Exception: If connection fails
        """
        try:
            conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            return conn
        except Exception as e:
            print(f"❌ [DATABASE] Connection failed: {e}")
            raise

    def channel_exists(self, open_channel_id: str) -> bool:
        """
        Validate if a channel exists in the database.

        Args:
            open_channel_id: The open channel ID to validate

        Returns:
            True if channel exists, False otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM main_clients_database WHERE open_channel_id = %s LIMIT 1",
                (str(open_channel_id),)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()

            exists = result is not None
            if exists:
                print(f"✅ [DATABASE] Channel {open_channel_id} exists")
            else:
                print(f"⚠️ [DATABASE] Channel {open_channel_id} does not exist")

            return exists

        except Exception as e:
            print(f"❌ [DATABASE] Error validating channel: {e}")
            return False

    def fetch_channel_details(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch complete channel details for invoice message personalization.

        Args:
            open_channel_id: The open channel ID to fetch details for

        Returns:
            Dictionary with channel details or None if not found:
            {
                "open_channel_id": str,
                "open_channel_title": str,
                "open_channel_description": str,
                "closed_channel_id": str,
                "closed_channel_title": str,
                "closed_channel_description": str,
                "sub_1_price": Decimal,
                "sub_1_time": int,
                "sub_2_price": Decimal,
                "sub_2_time": int,
                "sub_3_price": Decimal,
                "sub_3_time": int,
                "client_wallet_address": str,
                "client_payout_currency": str,
                "client_payout_network": str
            }
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            print(f"🔍 [DATABASE] Fetching channel details for {open_channel_id}")

            cur.execute("""
                SELECT
                    open_channel_id,
                    open_channel_title,
                    open_channel_description,
                    closed_channel_id,
                    closed_channel_title,
                    closed_channel_description,
                    sub_1_price,
                    sub_1_time,
                    sub_2_price,
                    sub_2_time,
                    sub_3_price,
                    sub_3_time,
                    client_wallet_address,
                    client_payout_currency,
                    client_payout_network
                FROM main_clients_database
                WHERE open_channel_id = %s
                LIMIT 1
            """, (str(open_channel_id),))

            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                channel_details = {
                    "open_channel_id": result[0],
                    "open_channel_title": result[1] if result[1] else "Premium Channel",
                    "open_channel_description": result[2] if result[2] else "exclusive content",
                    "closed_channel_id": result[3],
                    "closed_channel_title": result[4] if result[4] else "Premium Channel",
                    "closed_channel_description": result[5] if result[5] else "exclusive content",
                    "sub_1_price": result[6],
                    "sub_1_time": result[7],
                    "sub_2_price": result[8],
                    "sub_2_time": result[9],
                    "sub_3_price": result[10],
                    "sub_3_time": result[11],
                    "client_wallet_address": result[12] if result[12] else "",
                    "client_payout_currency": result[13] if result[13] else "USD",
                    "client_payout_network": result[14] if result[14] else ""
                }
                print(f"✅ [DATABASE] Channel details found: {channel_details['closed_channel_title']}")
                return channel_details
            else:
                print(f"⚠️ [DATABASE] No channel details found for {open_channel_id}")
                return None

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching channel details: {e}")
            return None

    def fetch_closed_channel_id(self, open_channel_id: str) -> Optional[str]:
        """
        Get the closed channel ID for a given open channel ID.

        Args:
            open_channel_id: The open channel ID to look up

        Returns:
            The closed channel ID if found, None otherwise
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            print(f"🔍 [DATABASE] Looking up closed_channel_id for {open_channel_id}")

            cur.execute(
                "SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s",
                (str(open_channel_id),)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result and result[0]:
                print(f"✅ [DATABASE] Closed channel ID: {result[0]}")
                return result[0]
            else:
                print(f"⚠️ [DATABASE] No closed_channel_id found for {open_channel_id}")
                return None

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching closed_channel_id: {e}")
            return None

    def fetch_client_wallet_info(self, open_channel_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get the client wallet address, payout currency, and payout network.

        Args:
            open_channel_id: The open_channel_id to look up

        Returns:
            Tuple of (wallet_address, payout_currency, payout_network) or (None, None, None)
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            print(f"🔍 [DATABASE] Looking up wallet info for {open_channel_id}")

            cur.execute(
                """SELECT client_wallet_address, client_payout_currency, client_payout_network
                   FROM main_clients_database
                   WHERE open_channel_id = %s""",
                (str(open_channel_id),)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                wallet_address, payout_currency, payout_network = result
                print(f"💰 [DATABASE] Wallet: {wallet_address}, Currency: {payout_currency}, Network: {payout_network}")
                return wallet_address, payout_currency, payout_network
            else:
                print(f"⚠️ [DATABASE] No wallet info found for {open_channel_id}")
                return None, None, None

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching wallet info: {e}")
            return None, None, None

    def close(self):
        """
        Close database connections.
        Called during application shutdown.
        """
        print("🔒 [DATABASE] Closing database connections")
        # Note: Currently using direct connections (no pooling)
        # Future: Implement connection pool cleanup here if needed
