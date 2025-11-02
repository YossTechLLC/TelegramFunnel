#!/usr/bin/env python
"""
Database Manager for GCWebhook2-10-26 (Telegram Invite Sender Service).
Validates payment status before sending Telegram invitation links.
Queries private_channel_users_database to verify payment completion via IPN.
"""
from typing import Optional
from google.cloud.sql.connector import Connector


class DatabaseManager:
    """
    Manages database connections and payment validation for GCWebhook2-10-26.
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

        print(f"🗄️ [DATABASE] DatabaseManager initialized for payment validation")
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

    def get_nowpayments_data(self, user_id: int, closed_channel_id: int) -> Optional[dict]:
        """
        Get NowPayments payment_id and related data for a user/channel subscription.

        This data is populated by the np-webhook service when it receives IPN callbacks
        from NowPayments. If the IPN hasn't arrived yet, this will return None.

        Args:
            user_id: User's Telegram ID
            closed_channel_id: The closed (private) channel ID

        Returns:
            Dict with NowPayments fields or None if not available:
            {
                'nowpayments_payment_id': str,
                'nowpayments_payment_status': str,
                'nowpayments_pay_address': str,
                'nowpayments_outcome_amount': Decimal
            }
        """
        conn = None
        cur = None
        try:
            print(f"🔍 [VALIDATION] Looking up NowPayments payment data for user {user_id}, channel {closed_channel_id}")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [VALIDATION] Could not establish connection")
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
                    print(f"✅ [VALIDATION] Found NowPayments payment_id: {payment_id}")
                    print(f"📊 [VALIDATION] Payment status: {payment_status}")
                    print(f"💰 [VALIDATION] Price amount: {price_amount} {price_currency}")
                    print(f"💰 [VALIDATION] Outcome amount: {outcome_amount} {outcome_currency}")
                    print(f"📬 [VALIDATION] Pay address: {pay_address}")

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
                    print(f"⚠️ [VALIDATION] Subscription found but payment_id not yet available (IPN pending)")
                    return None
            else:
                print(f"⚠️ [VALIDATION] No subscription record found in database")
                return None

        except Exception as e:
            print(f"❌ [VALIDATION] Error fetching NowPayments data: {e}")
            return None

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [VALIDATION] Connection closed")

    def validate_payment_complete(self, user_id: int, closed_channel_id: int, expected_price: str) -> tuple[bool, str]:
        """
        Validate that payment has been completed and confirmed via IPN callback.
        Uses price_amount (USD) for validation when available.
        Falls back to crypto conversion if needed.

        Args:
            user_id: User's Telegram ID
            closed_channel_id: The closed (private) channel ID
            expected_price: Expected subscription price (USD)

        Returns:
            Tuple of (is_valid: bool, error_message: str)
            - (True, "") if payment is valid
            - (False, "error message") if payment is invalid
        """
        print(f"🔐 [VALIDATION] Starting payment validation for user {user_id}, channel {closed_channel_id}")

        # Get payment data
        payment_data = self.get_nowpayments_data(user_id, closed_channel_id)

        if not payment_data:
            error_msg = "Payment not confirmed - IPN callback not yet processed. Please wait."
            print(f"❌ [VALIDATION] {error_msg}")
            return False, error_msg

        payment_id = payment_data.get('nowpayments_payment_id')
        payment_status = payment_data.get('nowpayments_payment_status')
        price_amount = payment_data.get('nowpayments_price_amount')
        price_currency = payment_data.get('nowpayments_price_currency')
        outcome_amount = payment_data.get('nowpayments_outcome_amount')
        outcome_currency = payment_data.get('nowpayments_outcome_currency')

        # Validate payment_id exists
        if not payment_id:
            error_msg = "Payment ID not available - IPN callback pending"
            print(f"❌ [VALIDATION] {error_msg}")
            return False, error_msg

        # Validate payment status is 'finished'
        if payment_status != 'finished':
            error_msg = f"Payment not completed - status: {payment_status}"
            print(f"❌ [VALIDATION] {error_msg}")
            return False, error_msg

        # Validate payment amount
        try:
            expected_amount = float(expected_price)

            # Strategy 1: Use price_amount if available (preferred - USD to USD comparison)
            if price_amount and price_currency:
                actual_usd = float(price_amount)
                print(f"💰 [VALIDATION] Using price_amount for validation: ${actual_usd:.2f} {price_currency}")

                # Allow 5% tolerance for rounding/fees
                minimum_amount = expected_amount * 0.95

                if actual_usd < minimum_amount:
                    error_msg = f"Insufficient payment: received ${actual_usd:.2f} {price_currency}, expected at least ${minimum_amount:.2f}"
                    print(f"❌ [VALIDATION] {error_msg}")
                    return False, error_msg

                print(f"✅ [VALIDATION] Payment amount OK: ${actual_usd:.2f} >= ${minimum_amount:.2f}")
                print(f"✅ [VALIDATION] Payment validation successful - payment_id: {payment_id}")
                return True, ""

            # Strategy 2: Fallback - Convert crypto to USD (for old records or missing price_amount)
            else:
                print(f"⚠️ [VALIDATION] price_amount not available, falling back to crypto conversion")

                # Check if outcome is already in USD-based stablecoin
                if outcome_currency and outcome_currency.lower() in ['usd', 'usdt', 'usdc', 'busd']:
                    actual_usd = float(outcome_amount) if outcome_amount else 0.0
                    print(f"💰 [VALIDATION] Outcome is in stablecoin: ${actual_usd:.2f} {outcome_currency}")

                    # NowPayments takes ~15% fee, so outcome should be ~85% of price
                    # Allow 20% tolerance (80% minimum)
                    minimum_amount = expected_amount * 0.80

                    if actual_usd < minimum_amount:
                        error_msg = f"Insufficient payment: received ${actual_usd:.2f} {outcome_currency}, expected at least ${minimum_amount:.2f}"
                        print(f"❌ [VALIDATION] {error_msg}")
                        return False, error_msg

                    print(f"✅ [VALIDATION] Payment amount OK: ${actual_usd:.2f} >= ${minimum_amount:.2f}")
                    print(f"✅ [VALIDATION] Payment validation successful - payment_id: {payment_id}")
                    return True, ""

                # Strategy 3: Crypto amount - needs conversion (NOT RECOMMENDED - requires price feed)
                else:
                    error_msg = f"Cannot validate crypto payment: outcome_amount is in {outcome_currency}, price_amount not available"
                    print(f"❌ [VALIDATION] {error_msg}")
                    print(f"💡 [VALIDATION] This payment requires manual verification or NowPayments API call")
                    print(f"💡 [VALIDATION] Payment ID: {payment_id}")
                    print(f"💡 [VALIDATION] Outcome: {outcome_amount} {outcome_currency}")

                    # For now, fail validation and require manual intervention
                    # TODO: Implement crypto-to-USD conversion using price feed or NowPayments API
                    return False, error_msg

        except (ValueError, TypeError) as e:
            error_msg = f"Invalid payment amount data: {e}"
            print(f"❌ [VALIDATION] {error_msg}")
            return False, error_msg
