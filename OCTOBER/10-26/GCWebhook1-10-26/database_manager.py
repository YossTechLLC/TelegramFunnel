#!/usr/bin/env python
"""
Database Manager for GCWebhook1-10-26 (Payment Processor Service).
Handles database connections and operations for private_channel_users_database table.
Extends shared BaseDatabaseManager with service-specific database operations.

Migration Date: 2025-11-15
Extends: _shared/database_manager_base.BaseDatabaseManager
"""
import sys
from datetime import datetime
from typing import Optional

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.database_manager_base import BaseDatabaseManager


class DatabaseManager(BaseDatabaseManager):
    """
    GCWebhook1-specific database manager.
    Extends BaseDatabaseManager with subscription recording and payout strategy operations.
    """

    def get_connection(self):
        """Alias for parent's get_database_connection()."""
        return self.get_database_connection()

    def get_current_timestamp(self) -> str:
        """Get current time in PostgreSQL time format."""
        now = datetime.now()
        return now.strftime('%H:%M:%S')

    def get_current_datestamp(self) -> str:
        """Get current date in PostgreSQL date format."""
        now = datetime.now()
        return now.strftime('%Y-%m-%d')

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
        """Record a user's subscription in the private_channel_users_database table."""
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

            conn.commit()
            print(f"✅ [DATABASE] Successfully {operation} subscription record")
            print(f"🎉 [DATABASE] User {user_id} recorded for channel {private_channel_id}")
            return True

        except Exception as e:
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
        """Get payout strategy and threshold for a client channel."""
        conn = None
        cur = None
        try:
            print(f"🔍 [DATABASE] Fetching payout strategy for closed channel {closed_channel_id}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return ('instant', 0)

            cur = conn.cursor()

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
            return ('instant', 0)

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def get_subscription_id(self, user_id: int, closed_channel_id: int) -> int:
        """Get subscription ID for a user/channel combination."""
        conn = None
        cur = None
        try:
            print(f"🔍 [DATABASE] Fetching subscription ID for user {user_id}, channel {closed_channel_id}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return 0

            cur = conn.cursor()

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
        """Get NowPayments payment_id and related data for a user/channel subscription."""
        conn = None
        cur = None
        try:
            print(f"🔍 [DATABASE] Looking up NowPayments payment_id for user {user_id}, channel {closed_channel_id}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return None

            cur = conn.cursor()

            query = """
                SELECT
                    nowpayments_payment_id,
                    nowpayments_pay_address,
                    nowpayments_outcome_amount
                FROM private_channel_users_database
                WHERE user_id = %s AND private_channel_id = %s
                ORDER BY id DESC
                LIMIT 1
            """
            cur.execute(query, (user_id, closed_channel_id))
            result = cur.fetchone()

            if result:
                payment_id, pay_address, outcome_amount = result

                if payment_id:
                    print(f"✅ [DATABASE] Found NowPayments payment_id: {payment_id}")
                    print(f"💰 [DATABASE] Outcome amount: {outcome_amount}")
                    print(f"📬 [DATABASE] Pay address: {pay_address}")

                    return {
                        'nowpayments_payment_id': payment_id,
                        'nowpayments_pay_address': pay_address,
                        'nowpayments_outcome_amount': str(outcome_amount) if outcome_amount else None
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
