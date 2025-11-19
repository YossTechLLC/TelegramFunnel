#!/usr/bin/env python
"""
Base Database Manager for PGP_v1 Services.
Provides common database connection and utility methods shared across all PGP_v1 microservices.
"""
import logging
from datetime import datetime
from typing import Optional
from google.cloud.sql.connector import Connector
from PGP_COMMON.utils import (
    generate_error_id,
    log_error_with_context,
    sanitize_sql_error
)

logger = logging.getLogger(__name__)


class BaseDatabaseManager:
    """
    Base class for database operations across all PGP_v1 services.

    This class provides common methods for:
    - Creating database connections using Cloud SQL Connector
    - Getting current timestamps and datestamps
    - Connection pooling and management
    - SQL injection protection via query validation

    Service-specific query methods remain in subclasses.

    Security Features:
    - Query validation before execution (C-06)
    - Parameterized queries enforcement
    - Column name whitelisting
    - Operation type validation
    """

    # SQL Injection Protection: Allowed operations
    ALLOWED_SQL_OPERATIONS = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH'}

    # SQL Injection Protection: Updateable columns per table
    # Add all tables used by your application
    UPDATEABLE_COLUMNS = {
        'main_clients_database': {
            'open_channel_title', 'closed_channel_title',
            'sub_1_price', 'sub_2_price', 'sub_3_price',
            'client_wallet_address', 'payout_strategy',
            'payout_network', 'customer_id'
        },
        'processed_payments': {
            'pgp_orchestrator_processed', 'outcome_amount_usd',
            'subscription_price', 'payout_network',
            'wallet_address', 'processed_at'
        },
        'subscription_tracking_table': {
            'subscription_status', 'subscription_end_date',
            'cancelled_at', 'payment_id'
        },
        'payout_accumulation_table': {
            'accumulated_amount', 'last_updated',
            'payout_status', 'payout_date'
        },
        'split_payout_que': {
            'processed', 'processed_at', 'error_message'
        },
        'batch_conversions': {
            'conversion_status', 'changenow_exchange_id',
            'completed_at', 'error_message'
        }
    }

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
            # Log full error details internally (not exposed to user)
            error_id = generate_error_id()
            log_error_with_context(e, error_id, {
                'service': self.service_name,
                'instance': self.instance_connection_name,
                'operation': 'get_connection'
            })
            print(f"❌ [DATABASE] Connection failed (Error ID: {error_id})")
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

    def execute_query(self, query: str, params: tuple, fetch_one: bool = False, fetch_all: bool = False, skip_validation: bool = False) -> Optional[any]:
        """
        Execute a database query with automatic connection management.

        Args:
            query: SQL query string
            params: Query parameters tuple
            fetch_one: If True, return single row
            fetch_all: If True, return all rows
            skip_validation: If True, skip SQL injection validation (use with caution!)

        Returns:
            Query result or None if failed

        Security:
            Validates all queries by default to prevent SQL injection (C-06).
            Use skip_validation=True ONLY for trusted internal queries.
        """
        # VALIDATE QUERY FIRST (SQL Injection Protection)
        if not skip_validation:
            try:
                self.validate_query(query)
            except ValueError as e:
                error_id = generate_error_id()
                logger.error(f"❌ [SECURITY] Query validation failed (Error ID: {error_id}): {e}")
                print(f"❌ [DATABASE] Query validation failed (Error ID: {error_id})")
                return None

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

            # Log full error details internally (SQL details NOT exposed to user)
            error_id = generate_error_id()
            log_error_with_context(e, error_id, {
                'service': self.service_name,
                'operation': 'execute_query',
                'fetch_one': fetch_one,
                'fetch_all': fetch_all
            })
            print(f"❌ [DATABASE] Query execution failed (Error ID: {error_id})")
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
            # Log full error details internally
            error_id = generate_error_id()
            log_error_with_context(e, error_id, {
                'service': self.service_name,
                'operation': 'close_connector'
            })
            print(f"❌ [DATABASE] Error closing connector (Error ID: {error_id})")

    # =========================================================================
    # SQL INJECTION PROTECTION METHODS (C-06)
    # =========================================================================

    def validate_query(self, query: str) -> bool:
        """
        Validate SQL query for security (SQL Injection Protection).

        Checks:
        1. Query starts with allowed operation (SELECT, INSERT, UPDATE, DELETE, WITH)
        2. No dangerous SQL comments (-- or /* */)
        3. No multiple statements (;)
        4. No EXECUTE, DROP, ALTER, TRUNCATE, GRANT, REVOKE

        Args:
            query: SQL query string to validate

        Returns:
            True if valid

        Raises:
            ValueError: If query fails validation

        Example:
            >>> db_manager.validate_query("SELECT * FROM users WHERE id = %s")
            True
            >>> db_manager.validate_query("DROP TABLE users")
            ValueError: Invalid SQL operation: DROP
        """
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")

        # Remove leading/trailing whitespace and convert to uppercase for checking
        query_upper = query.strip().upper()

        # Check for allowed operations
        operation = query_upper.split()[0] if query_upper.split() else ""

        if operation not in self.ALLOWED_SQL_OPERATIONS:
            error_id = generate_error_id()
            logger.error(f"❌ [SECURITY] Invalid SQL operation blocked: {operation} (Error ID: {error_id})")
            raise ValueError(f"Invalid SQL operation: {operation}")

        # Check for dangerous keywords
        dangerous_keywords = {
            'DROP', 'ALTER', 'TRUNCATE', 'GRANT', 'REVOKE',
            'EXECUTE', 'EXEC', 'CREATE TABLE', 'CREATE INDEX'
        }

        for keyword in dangerous_keywords:
            if keyword in query_upper:
                error_id = generate_error_id()
                logger.error(f"❌ [SECURITY] Dangerous SQL keyword blocked: {keyword} (Error ID: {error_id})")
                raise ValueError(f"Dangerous SQL keyword not allowed: {keyword}")

        # Check for SQL comments (can be used for injection)
        if '--' in query or '/*' in query or '*/' in query:
            error_id = generate_error_id()
            logger.error(f"❌ [SECURITY] SQL comments blocked (Error ID: {error_id})")
            raise ValueError("SQL comments are not allowed")

        # Check for multiple statements (semicolon injection)
        # Allow semicolon only at the very end
        semicolon_count = query.count(';')
        if semicolon_count > 1 or (semicolon_count == 1 and not query.strip().endswith(';')):
            error_id = generate_error_id()
            logger.error(f"❌ [SECURITY] Multiple SQL statements blocked (Error ID: {error_id})")
            raise ValueError("Multiple SQL statements are not allowed")

        return True

    def validate_column_name(self, table: str, column: str) -> bool:
        """
        Validate that a column name is in the whitelist for the given table.

        This prevents SQL injection via dynamic column names.

        Args:
            table: Table name
            column: Column name to validate

        Returns:
            True if valid

        Raises:
            ValueError: If column not in whitelist

        Example:
            >>> db_manager.validate_column_name('processed_payments', 'outcome_amount_usd')
            True
            >>> db_manager.validate_column_name('processed_payments', 'malicious_column')
            ValueError: Column 'malicious_column' not allowed for table 'processed_payments'
        """
        if table not in self.UPDATEABLE_COLUMNS:
            error_id = generate_error_id()
            logger.error(f"❌ [SECURITY] Unknown table in column validation: {table} (Error ID: {error_id})")
            raise ValueError(f"Table '{table}' not in whitelist")

        if column not in self.UPDATEABLE_COLUMNS[table]:
            error_id = generate_error_id()
            logger.error(f"❌ [SECURITY] Invalid column blocked: {table}.{column} (Error ID: {error_id})")
            raise ValueError(f"Column '{column}' not allowed for table '{table}'")

        return True

    def sanitize_query_comments(self, query: str) -> str:
        """
        Remove SQL comments from query string.

        Args:
            query: SQL query string

        Returns:
            Query with comments removed

        Example:
            >>> db_manager.sanitize_query_comments("SELECT * -- comment")
            'SELECT * '
        """
        # Remove single-line comments
        lines = query.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove everything after --
            if '--' in line:
                line = line.split('--')[0]
            cleaned_lines.append(line)

        query = '\n'.join(cleaned_lines)

        # Remove multi-line comments /* ... */
        while '/*' in query and '*/' in query:
            start = query.index('/*')
            end = query.index('*/') + 2
            query = query[:start] + query[end:]

        return query

    # =========================================================================
    # RACE CONDITION PROTECTION METHODS (C-04)
    # =========================================================================

    def mark_payment_processed_atomic(
        self,
        payment_id: str,
        service_name: str,
        additional_data: Optional[dict] = None
    ) -> bool:
        """
        Atomically mark a payment as processed using PostgreSQL UPSERT.

        This prevents race conditions where multiple concurrent requests
        try to process the same payment simultaneously.

        Uses PostgreSQL INSERT...ON CONFLICT to ensure atomicity:
        - If payment_id doesn't exist: INSERT succeeds → return True (process payment)
        - If payment_id exists: INSERT skipped → return False (already processed)

        Args:
            payment_id: Unique payment identifier (from NowPayments or similar)
            service_name: Name of service processing the payment
            additional_data: Optional dict of additional columns to store

        Returns:
            True if this is the FIRST time processing (safe to proceed)
            False if already processed (duplicate request, skip processing)

        Example:
            >>> # First request
            >>> is_new = db_manager.mark_payment_processed_atomic("pay_123", "pgp_orchestrator")
            >>> is_new
            True  # Safe to process payment

            >>> # Concurrent duplicate request
            >>> is_new = db_manager.mark_payment_processed_atomic("pay_123", "pgp_orchestrator")
            >>> is_new
            False  # Already processed, skip

        Security:
            Requires unique constraint on payment_id column in processed_payments table.
            See migration: 004_add_payment_unique_constraint.sql
        """
        conn = None
        cur = None

        try:
            conn = self.get_connection()
            if not conn:
                logger.error("❌ [DATABASE] Could not establish connection for atomic payment")
                return False

            cur = conn.cursor()

            # Build column names and values dynamically (but safely)
            base_columns = ['payment_id', 'service_name', 'processed_at']
            base_values = [payment_id, service_name, self.get_current_timestamp()]

            # Add additional data if provided
            extra_columns = []
            extra_values = []
            if additional_data:
                for col, val in additional_data.items():
                    # Validate column name against whitelist
                    try:
                        self.validate_column_name('processed_payments', col)
                        extra_columns.append(col)
                        extra_values.append(val)
                    except ValueError as e:
                        logger.warning(f"⚠️ [DATABASE] Skipping invalid column in atomic payment: {col}")

            all_columns = base_columns + extra_columns
            all_values = base_values + extra_values

            # Build UPSERT query
            columns_str = ', '.join(all_columns)
            placeholders = ', '.join(['%s'] * len(all_values))

            query = f"""
                INSERT INTO processed_payments ({columns_str})
                VALUES ({placeholders})
                ON CONFLICT (payment_id) DO NOTHING
                RETURNING payment_id
            """

            # Execute atomic UPSERT
            cur.execute(query, tuple(all_values))
            result = cur.fetchone()
            conn.commit()

            if result:
                # INSERT succeeded → this is the first time processing
                logger.info(f"✅ [DATABASE] Payment {payment_id} marked as processed by {service_name}")
                return True
            else:
                # INSERT skipped due to conflict → already processed
                logger.warning(f"⚠️ [DATABASE] Payment {payment_id} already processed (duplicate request)")
                return False

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass

            # Log error details
            error_id = generate_error_id()
            log_error_with_context(e, error_id, {
                'service': service_name,
                'payment_id': payment_id,
                'operation': 'mark_payment_processed_atomic'
            })
            logger.error(f"❌ [DATABASE] Atomic payment processing failed (Error ID: {error_id})")
            return False

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

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

    def insert_payout_accumulation_pending(
        self,
        client_id: str,
        user_id: int,
        subscription_id: int,
        payment_amount_usd,
        payment_currency: str,
        payment_timestamp: str,
        accumulated_eth,
        client_wallet_address: str,
        client_payout_currency: str,
        client_payout_network: str,
        nowpayments_payment_id: str = None,
        nowpayments_pay_address: str = None,
        nowpayments_outcome_amount: str = None
    ) -> Optional[int]:
        """
        Insert a payment accumulation record with pending conversion status.

        This method is used by PGP_ORCHESTRATOR_v1 for threshold-based payouts.
        Stores payment data in payout_accumulation table awaiting ETH→USDT conversion
        by PGP_MICROBATCHPROCESSOR_v1.

        Args:
            client_id: closed_channel_id from main_clients_database (private channel ID)
            user_id: Telegram user who made payment
            subscription_id: FK to private_channel_users_database
            payment_amount_usd: What user originally paid (Decimal or float)
            payment_currency: Original payment currency
            payment_timestamp: When user paid
            accumulated_eth: USD value pending conversion (Decimal or float, parameter name kept for compatibility)
            client_wallet_address: Client's payout wallet address
            client_payout_currency: Target currency (e.g., XMR)
            client_payout_network: Payout network
            nowpayments_payment_id: NowPayments payment ID (optional, from IPN)
            nowpayments_pay_address: Customer's payment address (optional, from IPN)
            nowpayments_outcome_amount: Actual received amount (optional, from IPN)

        Returns:
            Accumulation ID if successful, None if failed
        """
        from decimal import Decimal

        conn = None
        cur = None

        try:
            conn = self.get_connection()
            if not conn:
                logger.error(f"❌ [{self.service_name}] Failed to establish connection for accumulation insert")
                return None

            cur = conn.cursor()
            logger.info(f"💾 [{self.service_name}] Inserting payout accumulation record (pending conversion)")
            logger.info(f"👤 [{self.service_name}] User ID: {user_id}, Client ID: {client_id}")
            logger.info(f"💰 [{self.service_name}] Payment Amount: ${payment_amount_usd}")
            logger.info(f"💰 [{self.service_name}] Accumulated USD: ${accumulated_eth} (pending conversion)")

            if nowpayments_payment_id:
                logger.info(f"💳 [{self.service_name}] NowPayments Payment ID: {nowpayments_payment_id}")
                logger.info(f"📬 [{self.service_name}] Pay Address: {nowpayments_pay_address}")
                logger.info(f"💰 [{self.service_name}] Outcome Amount: {nowpayments_outcome_amount}")

            cur.execute(
                """INSERT INTO payout_accumulation (
                    client_id, user_id, subscription_id,
                    payment_amount_usd, payment_currency, payment_timestamp,
                    accumulated_eth, is_conversion_complete, is_paid_out,
                    client_wallet_address, client_payout_currency, client_payout_network,
                    nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id""",
                (
                    client_id, user_id, subscription_id,
                    payment_amount_usd, payment_currency, payment_timestamp,
                    accumulated_eth, False, False,  # is_conversion_complete=FALSE, is_paid_out=FALSE
                    client_wallet_address, client_payout_currency, client_payout_network,
                    nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount
                )
            )

            accumulation_id = cur.fetchone()[0]
            conn.commit()

            logger.info(f"✅ [{self.service_name}] Accumulation record inserted successfully (pending conversion)")
            logger.info(f"🆔 [{self.service_name}] Accumulation ID: {accumulation_id}")

            if nowpayments_payment_id:
                logger.info(f"🔗 [{self.service_name}] Linked to NowPayments payment_id: {nowpayments_payment_id}")

            return accumulation_id

        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Failed to insert accumulation record: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return None

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # =========================================================================
    # HOSTPAY TRANSACTION METHODS (Shared by HOSTPAY1 and HOSTPAY3)
    # =========================================================================
    # These methods were duplicated in PGP_HOSTPAY1_v1 and PGP_HOSTPAY3_v1
    # and have been consolidated here to eliminate code duplication.
    #
    # Moved from: PGP_HOSTPAY1_v1/database_manager.py, PGP_HOSTPAY3_v1/database_manager.py
    # Used by: PGP_HOSTPAY1_v1, PGP_HOSTPAY3_v1
    # =========================================================================

    def insert_hostpay_transaction(
        self,
        unique_id: str,
        cn_api_id: str,
        from_currency: str,
        from_network: str,
        from_amount: float,
        payin_address: str,
        is_complete: bool = True,
        tx_hash: str = None,
        tx_status: str = None,
        gas_used: int = None,
        block_number: int = None,
        actual_eth_amount: float = 0.0
    ) -> bool:
        """
        Insert a completed host payment transaction into split_payout_hostpay table.

        Shared across HOSTPAY1 and HOSTPAY3 services.

        Args:
            unique_id: Database linking ID (16 chars)
            cn_api_id: ChangeNow transaction ID
            from_currency: Source currency (e.g., "eth")
            from_network: Source network (e.g., "eth")
            from_amount: Amount sent (from ChangeNow estimate or actual payment)
            payin_address: ChangeNow deposit address
            is_complete: Payment completion status (default: True)
            tx_hash: Ethereum transaction hash (optional)
            tx_status: Transaction status ("success" or "failed") (optional)
            gas_used: Gas used by the transaction (optional)
            block_number: Block number where transaction was mined (optional)
            actual_eth_amount: ACTUAL ETH from NowPayments (default 0 for backward compat)

        Returns:
            True if successful, False otherwise
        """
        conn = None
        cur = None
        try:
            print(f"📝 [HOSTPAY_DB] Starting database insert for unique_id: {unique_id}")

            conn = self.get_connection()
            if not conn:
                print("❌ [HOSTPAY_DB] Could not establish database connection")
                return False

            cur = conn.cursor()

            # Insert into split_payout_hostpay table
            # NOTE: Database uses currency_type ENUM which expects UPPERCASE values
            # NOTE: from_amount is NUMERIC(12,8) - round to 8 decimal places to avoid precision errors

            # Round from_amount to 8 decimal places to match NUMERIC(12,8) constraint
            from_amount_rounded = round(float(from_amount), 8)

            # Validate cn_api_id length (table expects varchar(16))
            if len(cn_api_id) > 16:
                print(f"⚠️ [HOSTPAY_DB] cn_api_id too long ({len(cn_api_id)} chars), truncating to 16")
                cn_api_id = cn_api_id[:16]

            insert_query = """
                INSERT INTO split_payout_hostpay
                (unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address, is_complete, tx_hash, tx_status, gas_used, block_number, actual_eth_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            insert_params = (unique_id, cn_api_id, from_currency.upper(), from_network.upper(), from_amount_rounded, payin_address, is_complete, tx_hash, tx_status, gas_used, block_number, actual_eth_amount)

            # Log exact values being inserted for debugging
            print(f"📋 [HOSTPAY_DB] Insert parameters:")
            print(f"   unique_id: {unique_id} (len: {len(unique_id)})")
            print(f"   cn_api_id: {cn_api_id} (len: {len(cn_api_id)})")
            print(f"   from_currency: {from_currency.upper()}")
            print(f"   from_network: {from_network.upper()}")
            print(f"   from_amount: {from_amount_rounded} (original: {from_amount})")
            print(f"   actual_eth_amount: {actual_eth_amount}")
            print(f"   payin_address: {payin_address} (len: {len(payin_address)})")
            print(f"   is_complete: {is_complete}")
            print(f"   tx_hash: {tx_hash}")
            print(f"   tx_status: {tx_status}")
            print(f"   gas_used: {gas_used}")
            print(f"   block_number: {block_number}")

            print(f"🔄 [HOSTPAY_DB] Executing INSERT query")
            cur.execute(insert_query, insert_params)

            # Commit the transaction
            conn.commit()
            print(f"✅ [HOSTPAY_DB] Transaction committed successfully")

            print(f"🎉 [HOSTPAY_DB] Successfully inserted record for unique_id: {unique_id}")
            print(f"   🆔 CN API ID: {cn_api_id}")
            print(f"   💰 Currency: {from_currency.upper()}")
            print(f"   🌐 Network: {from_network.upper()}")
            print(f"   💰 Amount: {from_amount_rounded} {from_currency.upper()}")
            print(f"   🏦 Payin Address: {payin_address}")
            print(f"   ✔️ Is Complete: {is_complete}")
            print(f"   🔗 TX Hash: {tx_hash}")
            print(f"   📊 TX Status: {tx_status}")
            print(f"   ⛽ Gas Used: {gas_used}")
            print(f"   📦 Block Number: {block_number}")

            return True

        except Exception as e:
            # Rollback transaction on error
            if conn:
                try:
                    conn.rollback()
                    print(f"🔄 [HOSTPAY_DB] Transaction rolled back due to error")
                except Exception:
                    pass

            print(f"❌ [HOSTPAY_DB] Database error inserting hostpay transaction: {e}")
            return False

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [HOSTPAY_DB] Database connection closed")

    def insert_failed_transaction(
        self,
        unique_id: str,
        cn_api_id: str,
        from_currency: str,
        from_network: str,
        from_amount: float,
        payin_address: str,
        context: str,
        error_code: str,
        error_message: str,
        error_details: dict,
        attempt_count: int = 3
    ) -> bool:
        """
        Insert a failed transaction into failed_transactions table.

        Used by HOSTPAY3 for final failure after 3 payment attempts.

        Args:
            unique_id: Unique identifier for the transaction
            cn_api_id: ChangeNow API transaction ID
            from_currency: Source currency
            from_network: Network
            from_amount: Amount attempted
            payin_address: Destination address
            context: Context of failure (e.g., 'payment_execution')
            error_code: Error classification code
            error_message: Human-readable error message
            error_details: Additional error details (dict, will be converted to JSON)
            attempt_count: Number of attempts made

        Returns:
            True if insert successful, False otherwise
        """
        import json

        conn = None
        cur = None

        try:
            print(f"💾 [FAILED_TX] Storing failed transaction: {unique_id}")
            print(f"📊 [FAILED_TX] Error code: {error_code}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [FAILED_TX] Database connection failed")
                return False

            cur = conn.cursor()

            # Convert error_details dict to JSON string
            error_details_json = json.dumps(error_details)

            query = """
                INSERT INTO failed_transactions (
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
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, NOW(), 'failed_pending_review', NOW(), NOW()
                )
            """

            cur.execute(query, (
                unique_id,
                cn_api_id,
                from_currency,
                from_network,
                from_amount,
                payin_address,
                context,
                error_code,
                error_message,
                error_details_json,
                attempt_count
            ))

            conn.commit()
            print(f"✅ [FAILED_TX] Failed transaction stored successfully")
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
