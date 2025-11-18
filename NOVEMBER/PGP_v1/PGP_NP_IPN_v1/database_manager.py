#!/usr/bin/env python
"""
Database Manager for PGP_NP_IPN_v1 (NowPayments IPN Handler).
Handles database connections and operations for private_channel_users_database table.
"""
from datetime import datetime
from typing import Optional
from PGP_COMMON.database import BaseDatabaseManager


class DatabaseManager(BaseDatabaseManager):
    """
    Manages database connections and operations for PGP_NP_IPN_v1.
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
            service_name="PGP_NP_IPN_v1"
        )

    # =========================================================================
    # SERVICE-SPECIFIC DATABASE METHODS
    # =========================================================================
    # All shared database methods have been consolidated into
    # PGP_COMMON/database/db_manager.py:
    #   - get_current_timestamp() (was duplicate, already in base)
    #   - get_current_datestamp() (was duplicate, already in base)
    #   - record_private_channel_user()
    #   - get_payout_strategy()
    #   - get_subscription_id()
    #   - get_nowpayments_data()
    #
    # The get_database_connection() alias has been removed (use get_connection()).
    #
    # NP_IPN-specific database methods below (moved from pgp_np_ipn_v1.py):
    # =========================================================================

    def parse_order_id(self, order_id: str) -> tuple:
        """
        Parse NowPayments order_id to extract user_id and open_channel_id.

        Format: PGP-{user_id}|{open_channel_id}
        Example: PGP-6271402111|-1003268562225

        Also supports old format for backward compatibility:
        Old Format: PGP-{user_id}-{channel_id} (loses negative sign)
        Example: PGP-6271402111-1003268562225

        Args:
            order_id: NowPayments order_id string

        Returns:
            Tuple of (user_id, open_channel_id) or (None, None) if invalid
        """
        try:
            # Check for new format first (with | separator)
            if '|' in order_id:
                # New format: PGP-{user_id}|{open_channel_id}
                prefix_and_user, channel_id_str = order_id.split('|')
                if not prefix_and_user.startswith('PGP-'):
                    print(f"❌ [PARSE] order_id does not start with 'PGP-': {order_id}")
                    return None, None
                user_id_str = prefix_and_user[4:]  # Remove 'PGP-' prefix
                user_id = int(user_id_str)
                open_channel_id = int(channel_id_str)  # Preserves negative sign
                print(f"✅ [PARSE] New format detected")
                print(f"   User ID: {user_id}")
                print(f"   Open Channel ID: {open_channel_id}")
                return user_id, open_channel_id

            # Fallback to old format for backward compatibility (during transition)
            else:
                # Old format: PGP-{user_id}-{channel_id} (loses negative sign)
                parts = order_id.split('-')
                if len(parts) < 3 or parts[0] != 'PGP':
                    print(f"❌ [PARSE] Invalid order_id format: {order_id}")
                    return None, None
                user_id = int(parts[1])
                channel_id = int(parts[2])
                # FIX: Add negative sign back (all Telegram channels are negative)
                open_channel_id = -abs(channel_id)
                print(f"⚠️ [PARSE] Old format detected - added negative sign")
                print(f"   User ID: {user_id}")
                print(f"   Open Channel ID: {open_channel_id} (corrected from {channel_id})")
                return user_id, open_channel_id

        except (ValueError, IndexError) as e:
            print(f"❌ [PARSE] Failed to parse order_id '{order_id}': {e}")
            return None, None

    def update_payment_data(self, order_id: str, payment_data: dict) -> bool:
        """
        UPSERT payment data into private_channel_users_database.

        This function handles both scenarios:
        1. UPDATE: Existing record (normal bot flow)
        2. INSERT: No existing record (direct payment link, race condition)

        Three-step process:
        1. Parse order_id to get user_id and open_channel_id
        2. Look up closed_channel_id + client config from main_clients_database
        3. UPSERT into private_channel_users_database with full client configuration

        Args:
            order_id: NowPayments order_id (format: PGP-{user_id}|{open_channel_id})
            payment_data: Dictionary with payment metadata from IPN

        Returns:
            True if operation successful, False otherwise
        """
        conn = None
        cur = None

        try:
            # Step 1: Parse order_id
            user_id, open_channel_id = self.parse_order_id(order_id)
            if user_id is None or open_channel_id is None:
                print(f"❌ [DATABASE] Invalid order_id format: {order_id}")
                return False

            print(f"")
            print(f"📝 [DATABASE] Parsed order_id successfully:")
            print(f"   User ID: {user_id}")
            print(f"   Open Channel ID: {open_channel_id}")

            conn = self.get_connection()
            if not conn:
                return False

            cur = conn.cursor()

            # Step 2: Look up closed_channel_id + client configuration from main_clients_database
            print(f"")
            print(f"🔍 [DATABASE] Looking up channel mapping and client config...")
            print(f"   Searching for open_channel_id: {open_channel_id}")

            cur.execute("""
                SELECT
                    closed_channel_id,
                    client_wallet_address,
                    client_payout_currency::text,
                    client_payout_network::text
                FROM main_clients_database
                WHERE open_channel_id = %s
            """, (str(open_channel_id),))

            result = cur.fetchone()

            if not result or not result[0]:
                print(f"")
                print(f"❌ [DATABASE] No closed_channel_id found for open_channel_id: {open_channel_id}")
                print(f"⚠️ [DATABASE] This channel may not be registered in main_clients_database")
                print(f"💡 [HINT] Register this channel first:")
                print(f"   INSERT INTO main_clients_database (open_channel_id, closed_channel_id, ...)")
                print(f"   VALUES ('{open_channel_id}', '<closed_channel_id>', ...)")
                return False

            closed_channel_id = result[0]
            client_wallet_address = result[1]
            client_payout_currency = result[2]
            client_payout_network = result[3]

            print(f"✅ [DATABASE] Found channel mapping:")
            print(f"   Open Channel ID (public): {open_channel_id}")
            print(f"   Closed Channel ID (private): {closed_channel_id}")
            print(f"   Client Wallet: {client_wallet_address}")
            print(f"   Payout Currency: {client_payout_currency}")
            print(f"   Payout Network: {client_payout_network}")

            # Step 3: UPSERT into private_channel_users_database
            # This handles both new records (INSERT) and existing records (UPDATE)
            print(f"")
            print(f"🗄️ [DATABASE] Upserting payment record (INSERT or UPDATE)...")
            print(f"   Target table: private_channel_users_database")
            print(f"   Key: user_id = {user_id} AND private_channel_id = {closed_channel_id}")

            # Calculate expiration (30 days from now as default)
            from datetime import datetime, timedelta
            now = datetime.now()
            expiration = now + timedelta(days=30)
            expire_time = expiration.strftime('%H:%M:%S')
            expire_date = expiration.strftime('%Y-%m-%d')
            current_timestamp = now.strftime('%H:%M:%S')
            current_datestamp = now.strftime('%Y-%m-%d')

            # First, check if record exists to determine operation type
            cur.execute("""
                SELECT id FROM private_channel_users_database
                WHERE user_id = %s AND private_channel_id = %s
                ORDER BY id DESC LIMIT 1
            """, (user_id, closed_channel_id))

            existing_record = cur.fetchone()

            if existing_record:
                # Record exists - UPDATE
                print(f"📝 [DATABASE] Existing record found (id={existing_record[0]}) - will UPDATE")

                update_query = """
                    UPDATE private_channel_users_database
                    SET
                        nowpayments_payment_id = %s,
                        nowpayments_invoice_id = %s,
                        nowpayments_order_id = %s,
                        nowpayments_pay_address = %s,
                        nowpayments_payment_status = %s,
                        nowpayments_pay_amount = %s,
                        nowpayments_pay_currency = %s,
                        nowpayments_outcome_amount = %s,
                        nowpayments_price_amount = %s,
                        nowpayments_price_currency = %s,
                        nowpayments_outcome_currency = %s,
                        payment_status = 'confirmed',
                        nowpayments_created_at = CURRENT_TIMESTAMP,
                        nowpayments_updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND private_channel_id = %s
                    AND id = %s
                """

                cur.execute(update_query, (
                    payment_data.get('payment_id'),
                    payment_data.get('invoice_id'),
                    payment_data.get('order_id'),
                    payment_data.get('pay_address'),
                    payment_data.get('payment_status'),
                    payment_data.get('pay_amount'),
                    payment_data.get('pay_currency'),
                    payment_data.get('outcome_amount'),
                    payment_data.get('price_amount'),
                    payment_data.get('price_currency'),
                    payment_data.get('outcome_currency'),
                    user_id,
                    closed_channel_id,
                    existing_record[0]
                ))

                operation = "UPDATED"

            else:
                # No record exists - INSERT with full client configuration
                print(f"📝 [DATABASE] No existing record - will INSERT new record")
                print(f"💡 [DATABASE] Populating default subscription data (30 days)")

                insert_query = """
                    INSERT INTO private_channel_users_database (
                        user_id,
                        private_channel_id,
                        sub_time,
                        sub_price,
                        timestamp,
                        datestamp,
                        expire_time,
                        expire_date,
                        is_active,
                        payment_status,
                        nowpayments_payment_id,
                        nowpayments_invoice_id,
                        nowpayments_order_id,
                        nowpayments_pay_address,
                        nowpayments_payment_status,
                        nowpayments_pay_amount,
                        nowpayments_pay_currency,
                        nowpayments_outcome_amount,
                        nowpayments_price_amount,
                        nowpayments_price_currency,
                        nowpayments_outcome_currency,
                        nowpayments_created_at,
                        nowpayments_updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                """

                cur.execute(insert_query, (
                    user_id,
                    closed_channel_id,
                    30,  # Default subscription time: 30 days
                    str(payment_data.get('price_amount')),  # Use price_amount as sub_price
                    current_timestamp,
                    current_datestamp,
                    expire_time,
                    expire_date,
                    True,  # is_active
                    'confirmed',  # payment_status
                    payment_data.get('payment_id'),
                    payment_data.get('invoice_id'),
                    payment_data.get('order_id'),
                    payment_data.get('pay_address'),
                    payment_data.get('payment_status'),
                    payment_data.get('pay_amount'),
                    payment_data.get('pay_currency'),
                    payment_data.get('outcome_amount'),
                    payment_data.get('price_amount'),
                    payment_data.get('price_currency'),
                    payment_data.get('outcome_currency')
                ))

                operation = "INSERTED"

            conn.commit()
            rows_affected = cur.rowcount

            print(f"")
            print(f"✅ [DATABASE] Successfully {operation} {rows_affected} record(s)")
            print(f"   User ID: {user_id}")
            print(f"   Private Channel ID: {closed_channel_id}")
            print(f"   Payment ID: {payment_data.get('payment_id')}")
            print(f"   Invoice ID: {payment_data.get('invoice_id')}")
            print(f"   NowPayments Status: {payment_data.get('payment_status')}")
            print(f"   Payment Status: confirmed ✅")
            print(f"   Amount: {payment_data.get('outcome_amount')} {payment_data.get('pay_currency')}")

            if operation == "INSERTED":
                print(f"   Subscription: 30 days")
                print(f"   Expires: {expire_date} {expire_time}")

            return True

        except Exception as e:
            print(f"")
            print(f"❌ [DATABASE] Operation failed with exception: {e}")
            print(f"🔄 [DATABASE] Rolling back transaction...")
            if conn:
                conn.rollback()
            import traceback
            traceback.print_exc()
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")
