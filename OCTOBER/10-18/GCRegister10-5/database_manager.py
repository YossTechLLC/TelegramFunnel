#!/usr/bin/env python
"""
Database Manager for GCRegister10-5 Channel Registration Service.
Handles PostgreSQL connections and data operations using Cloud SQL Connector.
"""
from google.cloud.sql.connector import Connector
from typing import Optional, Dict, Any
from contextlib import contextmanager

class DatabaseManager:
    """
    Manages PostgreSQL database connections and operations for channel registration.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the DatabaseManager with Cloud SQL Connector.

        Args:
            config: Configuration dictionary containing database credentials
        """
        self.instance_connection_name = config.get('instance_connection_name')
        self.dbname = config.get('db_name')
        self.user = config.get('db_user')
        self.password = config.get('db_password')
        self.connector = Connector()

        # Validate that critical credentials are available
        if not self.password:
            print(f"❌ [DATABASE] Database password is missing")
            raise RuntimeError("Database password not available. Cannot initialize DatabaseManager.")
        if not self.instance_connection_name:
            print(f"❌ [DATABASE] Cloud SQL instance connection name is missing")
            print(f"🔍 [DATABASE] Expected key: 'instance_connection_name', got: {config.get('instance_connection_name')}")
            raise RuntimeError("Critical database configuration missing: instance_connection_name")
        if not self.dbname:
            print(f"❌ [DATABASE] Database name is missing")
            raise RuntimeError("Critical database configuration missing: db_name")
        if not self.user:
            print(f"❌ [DATABASE] Database user is missing")
            raise RuntimeError("Critical database configuration missing: db_user")

        print(f"🔗 [DATABASE] DatabaseManager initialized with Cloud SQL Connector")
        print(f"🔗 [DATABASE] Instance: {self.instance_connection_name}")
        print(f"🔗 [DATABASE] Database: {self.dbname}")

    @contextmanager
    def get_connection(self):
        """
        Create and return a database connection using Cloud SQL Connector.

        Yields:
            pg8000 connection object
        """
        conn = None
        try:
            conn = self.connector.connect(
                self.instance_connection_name,
                "pg8000",
                user=self.user,
                password=self.password,
                db=self.dbname
            )
            print(f"✅ [DATABASE] Connection established")
            yield conn
        except Exception as e:
            print(f"❌ [DATABASE] Connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def test_connection(self) -> bool:
        """
        Test the database connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    if result and result[0] == 1:
                        print(f"✅ [DATABASE] Connection test successful")
                        return True
                    return False
                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Connection test failed: {e}")
            return False

    def validate_channel_id_unique(self, open_channel_id: str) -> bool:
        """
        Check if the open_channel_id already exists in the database.

        Args:
            open_channel_id: The channel ID to check

        Returns:
            True if channel ID is unique (does not exist), False if it already exists
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    print(f"🔍 [DATABASE] Checking uniqueness for open_channel_id: {open_channel_id}")
                    cur.execute(
                        "SELECT COUNT(*) FROM main_clients_database WHERE open_channel_id = %s",
                        (open_channel_id,)
                    )
                    count = cur.fetchone()[0]

                    if count > 0:
                        print(f"❌ [DATABASE] Channel ID {open_channel_id} already exists")
                        return False
                    else:
                        print(f"✅ [DATABASE] Channel ID {open_channel_id} is unique")
                        return True
                finally:
                    cur.close()

        except Exception as e:
            print(f"❌ [DATABASE] Error checking channel ID uniqueness: {e}")
            return False

    def insert_channel_registration(self, data: Dict[str, Any]) -> bool:
        """
        Insert a new channel registration into the main_clients_database table.

        Args:
            data: Dictionary containing all registration data

        Returns:
            True if insertion successful, False otherwise
        """
        conn = None
        try:
            # First check if channel ID is unique
            if not self.validate_channel_id_unique(data['open_channel_id']):
                print(f"❌ [DATABASE] Cannot insert - channel ID already exists")
                return False

            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    print(f"📝 [DATABASE] Inserting new registration for channel: {data['open_channel_id']}")

                    # Prepare the insertion query (now includes client_payout_network)
                    insert_query = """
                        INSERT INTO main_clients_database
                        (open_channel_id, open_channel_title, open_channel_description,
                         closed_channel_id, closed_channel_title, closed_channel_description,
                         sub_1_price, sub_1_time, sub_2_price, sub_2_time, sub_3_price, sub_3_time,
                         client_wallet_address, client_payout_currency, client_payout_network)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    values = (
                        data['open_channel_id'],
                        data['open_channel_title'],
                        data['open_channel_description'],
                        data['closed_channel_id'],
                        data['closed_channel_title'],
                        data['closed_channel_description'],
                        data['sub_1_price'],
                        data['sub_1_time'],
                        data['sub_2_price'],
                        data['sub_2_time'],
                        data['sub_3_price'],
                        data['sub_3_time'],
                        data['client_wallet_address'],
                        data['client_payout_currency'],
                        data['client_payout_network']
                    )

                    # Execute the insertion
                    cur.execute(insert_query, values)
                    conn.commit()

                    print(f"✅ [DATABASE] Successfully inserted registration for channel: {data['open_channel_id']}")
                    print(f"📊 [DATABASE] Details: {data['open_channel_title']} -> {data['closed_channel_title']}")

                    # Log tier configuration (handle NULL values)
                    tier_info = []
                    if data['sub_1_price'] is not None and data['sub_1_time'] is not None:
                        tier_info.append(f"Tier 1 (Gold): ${data['sub_1_price']}/{data['sub_1_time']}d")
                    if data['sub_2_price'] is not None and data['sub_2_time'] is not None:
                        tier_info.append(f"Tier 2 (Silver): ${data['sub_2_price']}/{data['sub_2_time']}d")
                    if data['sub_3_price'] is not None and data['sub_3_time'] is not None:
                        tier_info.append(f"Tier 3 (Bronze): ${data['sub_3_price']}/{data['sub_3_time']}d")

                    tier_count = len(tier_info)
                    print(f"💰 [DATABASE] {tier_count} tier(s) configured: {', '.join(tier_info)}")

                    print(f"🏦 [DATABASE] Wallet: {data['client_wallet_address'][:20]}...")
                    print(f"🌐 [DATABASE] Payout: {data['client_payout_currency']} on {data['client_payout_network']} network")

                    return True
                finally:
                    cur.close()

        except Exception as e:
            if conn:
                conn.rollback()
            # Check if it's an integrity error (duplicate key, constraint violation)
            if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                print(f"❌ [DATABASE] Integrity error (duplicate or constraint violation): {e}")
            else:
                print(f"❌ [DATABASE] Error inserting registration: {e}")
            return False

    def get_registration_count(self) -> int:
        """
        Get the total number of registered channels.

        Returns:
            Count of registered channels
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT COUNT(*) FROM main_clients_database")
                    count = cur.fetchone()[0]
                    print(f"📊 [DATABASE] Total registered channels: {count}")
                    return count
                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Error getting registration count: {e}")
            return 0

    def get_currency_to_network_mappings(self) -> Dict[str, Any]:
        """
        Fetch all currency-to-network mappings from the currency_to_network table.
        Returns data structured for bidirectional filtering with friendly names.

        Returns:
            Dictionary with:
            - 'mappings': List of {currency, network, currency_name, network_name} pairs
            - 'network_to_currencies': Dict mapping network -> list of currency objects with names
            - 'currency_to_networks': Dict mapping currency -> list of network objects with names
            - 'networks_with_names': Dict mapping network code -> network_name
            - 'currencies_with_names': Dict mapping currency code -> currency_name
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    print(f"🔍 [DATABASE] Fetching currency-to-network mappings with friendly names")
                    cur.execute(
                        "SELECT currency, network, currency_name, network_name FROM currency_to_network ORDER BY network, currency"
                    )
                    rows = cur.fetchall()

                    # Build data structures for bidirectional filtering
                    mappings = []
                    network_to_currencies = {}
                    currency_to_networks = {}
                    networks_with_names = {}
                    currencies_with_names = {}

                    for currency, network, currency_name, network_name in rows:
                        # Add to mappings list
                        mappings.append({
                            'currency': currency,
                            'network': network,
                            'currency_name': currency_name or currency,  # Fallback to code if name is NULL
                            'network_name': network_name or network      # Fallback to code if name is NULL
                        })

                        # Build network -> currencies mapping
                        if network not in network_to_currencies:
                            network_to_currencies[network] = []
                        network_to_currencies[network].append({
                            'currency': currency,
                            'currency_name': currency_name or currency
                        })

                        # Build currency -> networks mapping
                        if currency not in currency_to_networks:
                            currency_to_networks[currency] = []
                        currency_to_networks[currency].append({
                            'network': network,
                            'network_name': network_name or network
                        })

                        # Build lookup tables for names
                        if network not in networks_with_names:
                            networks_with_names[network] = network_name or network
                        if currency not in currencies_with_names:
                            currencies_with_names[currency] = currency_name or currency

                    print(f"✅ [DATABASE] Fetched {len(mappings)} currency-network mappings with friendly names")
                    print(f"📊 [DATABASE] {len(network_to_currencies)} unique networks")
                    print(f"📊 [DATABASE] {len(currency_to_networks)} unique currencies")

                    return {
                        'mappings': mappings,
                        'network_to_currencies': network_to_currencies,
                        'currency_to_networks': currency_to_networks,
                        'networks_with_names': networks_with_names,
                        'currencies_with_names': currencies_with_names
                    }
                finally:
                    cur.close()

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching currency-network mappings: {e}")
            return {
                'mappings': [],
                'network_to_currencies': {},
                'currency_to_networks': {},
                'networks_with_names': {},
                'currencies_with_names': {}
            }
