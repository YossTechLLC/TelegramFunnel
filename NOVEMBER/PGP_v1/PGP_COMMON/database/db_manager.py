#!/usr/bin/env python
"""
Base Database Manager for PGP_v1 Services.
Provides common database connection and utility methods shared across all PGP_v1 microservices.
"""
from datetime import datetime
from typing import Optional
from google.cloud.sql.connector import Connector


class BaseDatabaseManager:
    """
    Base class for database operations across all PGP_v1 services.

    This class provides common methods for:
    - Creating database connections using Cloud SQL Connector
    - Getting current timestamps and datestamps
    - Connection pooling and management

    Service-specific query methods remain in subclasses.
    """

    def __init__(self, instance_connection_name: str, db_name: str, db_user: str, db_password: str, service_name: str):
        """
        Initialize the BaseDatabaseManager.

        Args:
            instance_connection_name: Cloud SQL instance connection name
            db_name: Database name
            db_user: Database user
            db_password: Database password
            service_name: Name of the service (for logging)
        """
        self.instance_connection_name = instance_connection_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.service_name = service_name
        self.connector = Connector()

        print(f"🗄️ [DATABASE] DatabaseManager initialized for {service_name}")
        print(f"📊 [DATABASE] Instance: {instance_connection_name}")
        print(f"📊 [DATABASE] Database: {db_name}")

    def get_connection(self):
        """
        Create and return a database connection using Cloud SQL Connector.

        This method is 100% identical across all PGP_v1 services.

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

    def get_current_timestamp(self) -> str:
        """
        Get current time in PostgreSQL time format.

        This method is 100% identical across all services.

        Returns:
            String representation of current time (e.g., '22:55:30')
        """
        now = datetime.now()
        return now.strftime('%H:%M:%S')

    def get_current_datestamp(self) -> str:
        """
        Get current date in PostgreSQL date format.

        This method is 100% identical across all services.

        Returns:
            String representation of current date (e.g., '2025-06-20')
        """
        now = datetime.now()
        return now.strftime('%Y-%m-%d')

    def execute_query(self, query: str, params: tuple, fetch_one: bool = False, fetch_all: bool = False) -> Optional[any]:
        """
        Execute a database query with automatic connection management.

        Args:
            query: SQL query string
            params: Query parameters tuple
            fetch_one: If True, return single row
            fetch_all: If True, return all rows

        Returns:
            Query result or None if failed
        """
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return None

            cur = conn.cursor()
            cur.execute(query, params)

            if fetch_one:
                result = cur.fetchone()
                return result
            elif fetch_all:
                result = cur.fetchall()
                return result
            else:
                # For INSERT/UPDATE/DELETE operations
                conn.commit()
                rows_affected = cur.rowcount
                print(f"✅ [DATABASE] Query executed, {rows_affected} row(s) affected")
                return rows_affected

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                    print(f"🔄 [DATABASE] Transaction rolled back")
                except Exception:
                    pass
            print(f"❌ [DATABASE] Error executing query: {e}")
            return None

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def close_connector(self):
        """
        Close the Cloud SQL Connector.

        Call this when shutting down the service.
        """
        try:
            self.connector.close()
            print(f"🔌 [DATABASE] Connector closed")
        except Exception as e:
            print(f"❌ [DATABASE] Error closing connector: {e}")

    # =========================================================================
    # SHARED DATABASE METHODS (Consolidated from services)
    # =========================================================================
    # The following methods were identical across multiple PGP_v1 services
    # and have been consolidated here to eliminate code duplication.
    #
    # Used by: PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1, PGP_INVITE_v1
    # =========================================================================

    def record_private_channel_user(
        self,
        user_id: int,
        private_channel_id: int,
        sub_time: int,
        sub_price: str,
        expire_time: str,
        expire_date: str,
        is_active: bool = True
    ) -> bool:
        """
        Record a user's subscription in the private_channel_users_database table.

        This method is shared across: PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1

        Args:
            user_id: The user's Telegram ID
            private_channel_id: The private channel ID (closed channel ID)
            sub_time: Subscription time in days
            sub_price: Subscription price as string (e.g., "15.00")
            expire_time: Expiration time in HH:MM:SS format
            expire_date: Expiration date in YYYY-MM-DD format
            is_active: Whether the subscription is active (default: True)

        Returns:
            True if successful, False otherwise
        """
        # Get current timestamp and datestamp for PostgreSQL (inherited methods)
        current_timestamp = self.get_current_timestamp()
        current_datestamp = self.get_current_datestamp()

        print(f"📝 [DATABASE] Recording subscription")
        print(f"👤 [DATABASE] User: {user_id}, Channel: {private_channel_id}")
        print(f"💰 [DATABASE] Price: ${sub_price}, Duration: {sub_time} days")
        print(f"⏰ [DATABASE] Expires: {expire_time} on {expire_date}")

        conn = None
        cur = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return False

            cur = conn.cursor()

            # Update existing record or insert new record for user/channel combination
            update_query = """
                UPDATE private_channel_users_database
                SET sub_time = %s, sub_price = %s, timestamp = %s, datestamp = %s, is_active = %s,
                    expire_time = %s, expire_date = %s
                WHERE user_id = %s AND private_channel_id = %s
            """
            update_params = (
                sub_time, sub_price, current_timestamp, current_datestamp, is_active,
                expire_time, expire_date, user_id, private_channel_id
            )
            cur.execute(update_query, update_params)
            rows_affected = cur.rowcount

            if rows_affected == 0:
                # No existing record found, insert new record
                print(f"📝 [DATABASE] No existing record found, inserting new")
                insert_query = """
                    INSERT INTO private_channel_users_database
                    (private_channel_id, user_id, sub_time, sub_price, timestamp, datestamp,
                     expire_time, expire_date, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                insert_params = (
                    private_channel_id, user_id, sub_time, sub_price, current_timestamp,
                    current_datestamp, expire_time, expire_date, is_active
                )
                cur.execute(insert_query, insert_params)
                operation = "inserted"
            else:
                operation = "updated"
                print(f"✅ [DATABASE] Updated {rows_affected} existing record(s)")

            # Commit the transaction
            conn.commit()
            print(f"✅ [DATABASE] Successfully {operation} subscription record")
            print(f"🎉 [DATABASE] User {user_id} recorded for channel {private_channel_id}")
            return True

        except Exception as e:
            # Rollback transaction on error
            if conn:
                try:
                    conn.rollback()
                    print(f"🔄 [DATABASE] Transaction rolled back")
                except Exception:
                    pass

            print(f"❌ [DATABASE] Error recording subscription: {e}")
            return False

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def get_payout_strategy(self, closed_channel_id: int) -> tuple:
        """
        Get payout strategy and threshold for a client channel.

        This method is shared across: PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1

        Args:
            closed_channel_id: The closed (private) channel ID

        Returns:
            Tuple of (payout_strategy, payout_threshold_usd) or ('instant', 0) if not found
        """
        conn = None
        cur = None
        try:
            print(f"🔍 [DATABASE] Fetching payout strategy for closed channel {closed_channel_id}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return ('instant', 0)  # Default to instant

            cur = conn.cursor()

            # Query for payout strategy and threshold by closed_channel_id
            query = """
                SELECT payout_strategy, payout_threshold_usd
                FROM main_clients_database
                WHERE closed_channel_id = %s
            """
            cur.execute(query, (str(closed_channel_id),))
            result = cur.fetchone()

            if result:
                strategy = result[0] or 'instant'
                threshold = float(result[1]) if result[1] else 0
                print(f"✅ [DATABASE] Found client by closed_channel_id: strategy={strategy}, threshold=${threshold}")
                return (strategy, threshold)
            else:
                print(f"⚠️ [DATABASE] No client found for closed_channel_id {closed_channel_id}, defaulting to instant")
                return ('instant', 0)

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching payout strategy: {e}")
            return ('instant', 0)  # Default to instant on error

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def get_subscription_id(self, user_id: int, closed_channel_id: int) -> int:
        """
        Get subscription ID for a user/channel combination.

        This method is shared across: PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1

        Args:
            user_id: User's Telegram ID
            closed_channel_id: The closed (private) channel ID

        Returns:
            Subscription ID or 0 if not found
        """
        conn = None
        cur = None
        try:
            print(f"🔍 [DATABASE] Fetching subscription ID for user {user_id}, channel {closed_channel_id}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return 0

            cur = conn.cursor()

            # Query for subscription ID
            query = """
                SELECT id
                FROM private_channel_users_database
                WHERE user_id = %s AND private_channel_id = %s
                ORDER BY id DESC
                LIMIT 1
            """
            cur.execute(query, (user_id, closed_channel_id))
            result = cur.fetchone()

            if result:
                subscription_id = result[0]
                print(f"✅ [DATABASE] Found subscription ID: {subscription_id}")
                return subscription_id
            else:
                print(f"⚠️ [DATABASE] No subscription found")
                return 0

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching subscription ID: {e}")
            return 0

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def get_nowpayments_data(self, user_id: int, closed_channel_id: int) -> Optional[dict]:
        """
        Get NowPayments payment_id and related data for a user/channel subscription.

        This data is populated by the np-webhook service when it receives IPN callbacks
        from NowPayments. If the IPN hasn't arrived yet, this will return None.

        This method is shared across: PGP_ORCHESTRATOR_v1, PGP_NP_IPN_v1, PGP_INVITE_v1

        Args:
            user_id: User's Telegram ID
            closed_channel_id: The closed (private) channel ID

        Returns:
            Dict with NowPayments fields or None if not available:
            {
                'nowpayments_payment_id': str,
                'nowpayments_payment_status': str,
                'nowpayments_pay_address': str,
                'nowpayments_outcome_amount': str,
                'nowpayments_price_amount': str,
                'nowpayments_price_currency': str,
                'nowpayments_outcome_currency': str,
                'nowpayments_pay_currency': str
            }
        """
        conn = None
        cur = None
        try:
            print(f"🔍 [DATABASE] Looking up NowPayments payment data for user {user_id}, channel {closed_channel_id}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return None

            cur = conn.cursor()

            # Query for NowPayments data from most recent subscription
            query = """
                SELECT
                    nowpayments_payment_id,
                    nowpayments_payment_status,
                    nowpayments_pay_address,
                    nowpayments_outcome_amount,
                    nowpayments_price_amount,
                    nowpayments_price_currency,
                    nowpayments_outcome_currency,
                    nowpayments_pay_currency
                FROM private_channel_users_database
                WHERE user_id = %s AND private_channel_id = %s
                ORDER BY id DESC
                LIMIT 1
            """
            cur.execute(query, (user_id, closed_channel_id))
            result = cur.fetchone()

            if result:
                (payment_id, payment_status, pay_address, outcome_amount,
                 price_amount, price_currency, outcome_currency, pay_currency) = result

                if payment_id:
                    print(f"✅ [DATABASE] Found NowPayments payment_id: {payment_id}")
                    print(f"📊 [DATABASE] Payment status: {payment_status}")
                    print(f"💰 [DATABASE] Price amount: {price_amount} {price_currency}")
                    print(f"💰 [DATABASE] Outcome amount: {outcome_amount} {outcome_currency}")
                    print(f"📬 [DATABASE] Pay address: {pay_address}")

                    return {
                        'nowpayments_payment_id': payment_id,
                        'nowpayments_payment_status': payment_status,
                        'nowpayments_pay_address': pay_address,
                        'nowpayments_outcome_amount': str(outcome_amount) if outcome_amount else None,
                        'nowpayments_price_amount': str(price_amount) if price_amount else None,
                        'nowpayments_price_currency': price_currency,
                        'nowpayments_outcome_currency': outcome_currency,
                        'nowpayments_pay_currency': pay_currency
                    }
                else:
                    print(f"⚠️ [DATABASE] Subscription found but payment_id not yet available (IPN may arrive later)")
                    return None
            else:
                print(f"⚠️ [DATABASE] No subscription found")
                return None

        except Exception as e:
            print(f"❌ [DATABASE] Error fetching NowPayments data: {e}")
            return None

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")
