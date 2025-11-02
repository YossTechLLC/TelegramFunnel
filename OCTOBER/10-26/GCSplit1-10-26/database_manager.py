#!/usr/bin/env python
"""
Database Manager for GCSplit1-10-26 (Orchestrator Service).
Handles database operations for split_payout_request and split_payout_que tables.
Uses Google Cloud SQL Connector.
"""
import random
import string
from google.cloud.sql.connector import Connector
from typing import Optional, Dict, Any
from contextlib import contextmanager


class DatabaseManager:
    """
    Manages database connections and operations for GCSplit1-10-26.
    Handles split_payout_request and split_payout_que tables.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize DatabaseManager with configuration.

        Args:
            config: Configuration dictionary from ConfigManager
        """
        self.instance_connection_name = config.get('instance_connection_name')
        self.db_name = config.get('db_name')
        self.db_user = config.get('db_user')
        self.db_password = config.get('db_password')
        self.connector = Connector()

        # Validate credentials
        if not all([self.instance_connection_name, self.db_name, self.db_user, self.db_password]):
            print(f"❌ [DATABASE] Missing required credentials")
            print(f"   Instance: {'✅' if self.instance_connection_name else '❌'}")
            print(f"   DB Name: {'✅' if self.db_name else '❌'}")
            print(f"   DB User: {'✅' if self.db_user else '❌'}")
            print(f"   DB Password: {'✅' if self.db_password else '❌'}")
            raise RuntimeError("Database credentials incomplete")

        print(f"🔗 [DATABASE] DatabaseManager initialized")
        print(f"☁️ [DATABASE] Instance: {self.instance_connection_name}")
        print(f"📊 [DATABASE] Database: {self.db_name}")

    def get_database_connection(self):
        """
        Create and return a database connection using Cloud SQL Connector.

        Returns:
            pg8000 connection object
        """
        try:
            connection = self.connector.connect(
                self.instance_connection_name,
                "pg8000",
                user=self.db_user,
                password=self.db_password,
                db=self.db_name
            )
            print(f"✅ [DATABASE] Connection established")
            return connection

        except Exception as e:
            print(f"❌ [DATABASE] Connection error: {e}")
            raise

    def generate_unique_id(self) -> str:
        """
        Generate a unique 16-digit alphanumeric ID for split_payout_request.

        Returns:
            16-character unique ID string (uppercase letters and digits)
        """
        characters = string.ascii_uppercase + string.digits
        unique_id = ''.join(random.choices(characters, k=16))
        print(f"🔑 [UNIQUE_ID] Generated: {unique_id}")
        return unique_id

    def insert_split_payout_request(
        self,
        user_id: int,
        closed_channel_id: str,
        from_currency: str,
        to_currency: str,
        from_network: str,
        to_network: str,
        from_amount: float,
        to_amount: float,
        client_wallet_address: str,
        refund_address: str = "",
        flow: str = "standard",
        type_: str = "direct",
        actual_eth_amount: float = 0.0  # ✅ ADD THIS
    ) -> Optional[str]:
        """
        Insert a new record into the split_payout_request table.

        This table stores the MARKET VALUE of the USDT→ETH conversion
        (pure market rate, not post-fee amount).

        Args:
            user_id: User ID from webhook
            closed_channel_id: Channel ID from webhook
            from_currency: Source currency (e.g., "usdt")
            to_currency: Target currency (e.g., "eth" or client's payout currency)
            from_network: Source network (e.g., "eth")
            to_network: Target network (e.g., "eth")
            from_amount: USDT amount (after TP fee deduction)
            to_amount: Pure market ETH value (NOT post-fee amount)
            client_wallet_address: Client's wallet address
            refund_address: Refund address (optional)
            flow: Exchange flow type (default "standard")
            type_: Exchange type (default "direct")
            actual_eth_amount: ACTUAL ETH from NowPayments (default 0 for backward compat)

        Returns:
            Generated unique_id if successful, None otherwise
        """
        conn = None
        cur = None
        try:
            print(f"📝 [DB_INSERT] Preparing split_payout_request insertion")
            print(f"👤 [DB_INSERT] User ID: {user_id}")
            print(f"🏦 [DB_INSERT] Wallet: {client_wallet_address}")
            print(f"💰 [DB_INSERT] From: {from_amount} {from_currency.upper()}")
            print(f"💰 [DB_INSERT] To: {to_amount} {to_currency.upper()} (PURE MARKET VALUE)")
            print(f"💰 [DB_INSERT] ACTUAL ETH: {actual_eth_amount}")  # ✅ ADD LOG

            # Generate unique ID
            unique_id = self.generate_unique_id()

            # SQL INSERT statement
            insert_query = """
                INSERT INTO split_payout_request (
                    unique_id, user_id, closed_channel_id,
                    from_currency, to_currency, from_network, to_network,
                    from_amount, to_amount, client_wallet_address, refund_address,
                    flow, type, actual_eth_amount
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
            """

            params = (
                unique_id, user_id, closed_channel_id,
                from_currency.upper(), to_currency.upper(),
                from_network.upper(), to_network.upper(),
                from_amount, to_amount,
                client_wallet_address, refund_address,
                flow, type_,
                actual_eth_amount  # ✅ ADD VALUE
            )

            # Execute insertion
            conn = self.get_database_connection()
            cur = conn.cursor()
            cur.execute(insert_query, params)
            rows_affected = cur.rowcount

            if rows_affected > 0:
                conn.commit()
                print(f"✅ [DB_INSERT] Successfully inserted split_payout_request")
                print(f"🆔 [DB_INSERT] Unique ID: {unique_id}")
                return unique_id
            else:
                print(f"❌ [DB_INSERT] No rows affected")
                return None

        except Exception as e:
            # Handle duplicate unique_id (retry with new ID)
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"⚠️ [DB_INSERT] Duplicate unique_id, retrying...")
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                if cur:
                    try:
                        cur.close()
                    except Exception:
                        pass
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                # Retry with new unique ID
                return self.insert_split_payout_request(
                    user_id, closed_channel_id, from_currency, to_currency,
                    from_network, to_network, from_amount, to_amount,
                    client_wallet_address, refund_address, flow, type_,
                    actual_eth_amount  # ✅ ADD PARAMETER
                )
            else:
                print(f"❌ [DB_INSERT] Error: {e}")
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                return None
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def insert_split_payout_que(
        self,
        unique_id: str,
        cn_api_id: str,
        user_id: int,
        closed_channel_id: str,
        from_currency: str,
        to_currency: str,
        from_network: str,
        to_network: str,
        from_amount: float,
        to_amount: float,
        payin_address: str,
        payout_address: str,
        refund_address: str = "",
        flow: str = "standard",
        type_: str = "direct"
    ) -> bool:
        """
        Insert a new record into the split_payout_que table.

        This table stores the ACTUAL CHANGENOW TRANSACTION details
        (actual swap amounts including all fees).

        Args:
            unique_id: The SAME unique_id from split_payout_request (for linking)
            cn_api_id: ChangeNow transaction ID (from API response)
            user_id: User ID
            closed_channel_id: Channel ID
            from_currency: Source currency (e.g., "eth")
            to_currency: Target currency (e.g., "link", "btc")
            from_network: Source network
            to_network: Target network
            from_amount: Actual from amount (from ChangeNow response)
            to_amount: Actual to amount (from ChangeNow response)
            payin_address: ChangeNow deposit address
            payout_address: Client's wallet address
            refund_address: Refund address (optional)
            flow: Exchange flow type
            type_: Exchange type

        Returns:
            True if successful, False otherwise
        """
        conn = None
        cur = None
        try:
            print(f"📝 [DB_INSERT_QUE] Preparing split_payout_que insertion")
            print(f"🆔 [DB_INSERT_QUE] Unique ID: {unique_id} (linking to request)")
            print(f"🆔 [DB_INSERT_QUE] ChangeNow API ID: {cn_api_id}")
            print(f"👤 [DB_INSERT_QUE] User ID: {user_id}")
            print(f"🏦 [DB_INSERT_QUE] Payin: {payin_address}")
            print(f"🏦 [DB_INSERT_QUE] Payout: {payout_address}")
            print(f"💰 [DB_INSERT_QUE] From: {from_amount} {from_currency.upper()}")
            print(f"💰 [DB_INSERT_QUE] To: {to_amount} {to_currency.upper()}")

            # SQL INSERT statement
            insert_query = """
                INSERT INTO split_payout_que (
                    unique_id, cn_api_id, user_id, closed_channel_id,
                    from_currency, to_currency, from_network, to_network,
                    from_amount, to_amount, payin_address, payout_address, refund_address,
                    flow, type
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s
                )
            """

            params = (
                unique_id, cn_api_id, user_id, closed_channel_id,
                from_currency.upper(), to_currency.upper(),
                from_network.upper(), to_network.upper(),
                from_amount, to_amount,
                payin_address, payout_address, refund_address,
                flow, type_
            )

            # Execute insertion
            conn = self.get_database_connection()
            cur = conn.cursor()
            cur.execute(insert_query, params)
            rows_affected = cur.rowcount

            if rows_affected > 0:
                conn.commit()
                print(f"✅ [DB_INSERT_QUE] Successfully inserted into split_payout_que")
                print(f"🔗 [DB_INSERT_QUE] Linked to split_payout_request via unique_id: {unique_id}")
                return True
            else:
                print(f"❌ [DB_INSERT_QUE] No rows affected")
                return False

        except Exception as e:
            print(f"❌ [DB_INSERT_QUE] Error: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return False
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
