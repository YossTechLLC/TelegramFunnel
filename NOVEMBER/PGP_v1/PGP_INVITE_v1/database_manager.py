#!/usr/bin/env python
"""
Database Manager for PGP_INVITE_v1 (Telegram Invite Sender Service).
Validates payment status before sending Telegram invitation links.
Queries private_channel_users_database to verify payment completion via IPN.
"""
from typing import Optional
from PGP_COMMON.database import BaseDatabaseManager
from PGP_COMMON.utils import CryptoPricingClient


class DatabaseManager(BaseDatabaseManager):
    """
    Manages database connections and payment validation for PGP_INVITE_v1.
    Inherits common methods from BaseDatabaseManager.
    """

    def __init__(
        self,
        instance_connection_name: str,
        db_name: str,
        db_user: str,
        db_password: str,
        payment_min_tolerance: float = 0.50,
        payment_fallback_tolerance: float = 0.75
    ):
        """
        Initialize the DatabaseManager.

        Args:
            instance_connection_name: Cloud SQL instance connection name
            db_name: Database name
            db_user: Database user
            db_password: Database password
            payment_min_tolerance: Minimum tolerance for outcome_amount validation (default: 0.50)
            payment_fallback_tolerance: Minimum tolerance for price_amount fallback (default: 0.75)
        """
        super().__init__(
            instance_connection_name=instance_connection_name,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            service_name="PGP_INVITE_v1"
        )
        self.payment_min_tolerance = payment_min_tolerance
        self.payment_fallback_tolerance = payment_fallback_tolerance

        # Initialize crypto pricing client (shared utility)
        self.pricing_client = CryptoPricingClient()

        print(f"🗄️ [DATABASE] DatabaseManager initialized for payment validation")
        print(f"📊 [DATABASE] Min tolerance: {payment_min_tolerance} ({payment_min_tolerance*100}%)")
        print(f"📊 [DATABASE] Fallback tolerance: {payment_fallback_tolerance} ({payment_fallback_tolerance*100}%)")

    # =========================================================================
    # SHARED METHOD CONSOLIDATION
    # =========================================================================
    # get_nowpayments_data() has been moved to PGP_COMMON/database/db_manager.py
    # It now returns 8 fields (enhanced version with all payment data).
    # =========================================================================

    # =========================================================================
    # CRYPTO PRICING METHODS - CONSOLIDATED TO PGP_COMMON
    # =========================================================================
    # get_crypto_usd_price() and convert_crypto_to_usd() have been moved to
    # PGP_COMMON/utils/crypto_pricing.py and are now accessed via
    # self.pricing_client (CryptoPricingClient instance)
    # =========================================================================

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

            # ============================================================================
            # STRATEGY 1 (PRIMARY): Validate outcome_amount converted to USD
            # ============================================================================
            if outcome_amount and outcome_currency:
                print(f"💰 [VALIDATION] Outcome: {outcome_amount} {outcome_currency}")

                # Convert outcome_amount to USD using shared pricing client
                outcome_usd = self.pricing_client.convert_crypto_to_usd(
                    amount=float(outcome_amount),
                    crypto_symbol=outcome_currency
                )

                if outcome_usd is not None:
                    print(f"💰 [VALIDATION] Outcome in USD: ${outcome_usd:.2f}")

                    # Calculate minimum acceptable amount using configurable tolerance
                    minimum_amount = expected_amount * self.payment_min_tolerance
                    print(f"📊 [VALIDATION] Using min tolerance: {self.payment_min_tolerance} ({self.payment_min_tolerance*100}%)")
                    print(f"📊 [VALIDATION] Minimum acceptable: ${minimum_amount:.2f} USD")

                    if outcome_usd < minimum_amount:
                        error_msg = (
                            f"Insufficient payment received: ${outcome_usd:.2f} USD "
                            f"(from {outcome_amount} {outcome_currency}), "
                            f"expected at least ${minimum_amount:.2f} USD"
                        )
                        print(f"❌ [VALIDATION] {error_msg}")
                        return False, error_msg

                    print(f"✅ [VALIDATION] Outcome amount OK: ${outcome_usd:.2f} >= ${minimum_amount:.2f}")

                    # Log fee information for reconciliation
                    if price_amount:
                        fee_lost = float(price_amount) - outcome_usd
                        fee_percentage = (fee_lost / float(price_amount)) * 100
                        print(f"📊 [VALIDATION] Invoice: ${price_amount}, Received: ${outcome_usd:.2f}, Fee: ${fee_lost:.2f} ({fee_percentage:.1f}%)")

                    print(f"✅ [VALIDATION] Payment validation successful - payment_id: {payment_id}")
                    return True, ""
                else:
                    print(f"⚠️ [VALIDATION] Could not convert outcome_amount to USD")
                    print(f"⚠️ [VALIDATION] Falling back to price_amount validation...")

            # ============================================================================
            # STRATEGY 2 (FALLBACK): Use price_amount if outcome conversion failed
            # ============================================================================
            if price_amount and price_currency:
                print(f"💰 [VALIDATION] Using price_amount fallback: ${float(price_amount):.2f} {price_currency}")
                print(f"⚠️ [VALIDATION] WARNING: Validating invoice price, not actual received amount")

                actual_usd = float(price_amount)
                minimum_amount = expected_amount * self.payment_fallback_tolerance
                print(f"📊 [VALIDATION] Using fallback tolerance: {self.payment_fallback_tolerance} ({self.payment_fallback_tolerance*100}%)")
                print(f"📊 [VALIDATION] Minimum acceptable: ${minimum_amount:.2f} USD")

                if actual_usd < minimum_amount:
                    error_msg = f"Insufficient invoice amount: ${actual_usd:.2f}, expected at least ${minimum_amount:.2f}"
                    print(f"❌ [VALIDATION] {error_msg}")
                    return False, error_msg

                print(f"✅ [VALIDATION] Invoice amount OK: ${actual_usd:.2f} >= ${minimum_amount:.2f}")
                print(f"⚠️ [VALIDATION] NOTE: Actual received amount not validated (outcome conversion unavailable)")
                return True, ""

            # ============================================================================
            # STRATEGY 3 (ERROR): No validation possible
            # ============================================================================
            error_msg = "Cannot validate payment: both outcome_amount and price_amount unavailable"
            print(f"❌ [VALIDATION] {error_msg}")
            return False, error_msg

        except (ValueError, TypeError) as e:
            error_msg = f"Invalid payment amount data: {e}"
            print(f"❌ [VALIDATION] {error_msg}")
            return False, error_msg

    def get_channel_subscription_details(
        self,
        closed_channel_id: int,
        subscription_price: str,
        subscription_time_days: int
    ) -> dict:
        """
        Fetch channel title and determine subscription tier number.

        Args:
            closed_channel_id: The closed (private) channel ID
            subscription_price: Subscription price from token (USD string)
            subscription_time_days: Subscription duration from token (days)

        Returns:
            Dict with channel details:
            {
                'channel_title': str,
                'tier_number': int | str  # 1, 2, 3, or "Unknown"
            }

            Fallback values if channel not found or tier not matched:
            {
                'channel_title': 'Premium Channel',
                'tier_number': 'Unknown'
            }
        """
        conn = None
        cur = None
        try:
            print(f"📺 [CHANNEL] Fetching details for channel {closed_channel_id}")
            print(f"📺 [CHANNEL] Looking for match: ${subscription_price} USD, {subscription_time_days} days")

            conn = self.get_connection()
            if not conn:
                print(f"❌ [CHANNEL] Could not establish connection - using fallback values")
                return {
                    'channel_title': 'Premium Channel',
                    'tier_number': 'Unknown'
                }

            cur = conn.cursor()

            # Query for channel and tier information
            query = """
                SELECT
                    closed_channel_title,
                    sub_1_price,
                    sub_1_time,
                    sub_2_price,
                    sub_2_time,
                    sub_3_price,
                    sub_3_time
                FROM main_clients_database
                WHERE closed_channel_id = %s
                LIMIT 1
            """
            cur.execute(query, (closed_channel_id,))
            result = cur.fetchone()

            if not result:
                print(f"⚠️ [CHANNEL] Channel {closed_channel_id} not found in database - using fallback")
                return {
                    'channel_title': 'Premium Channel',
                    'tier_number': 'Unknown'
                }

            # Unpack result
            (channel_title, sub_1_price, sub_1_time, sub_2_price, sub_2_time,
             sub_3_price, sub_3_time) = result

            # Use fallback if channel title is empty
            if not channel_title or channel_title.strip() == '':
                channel_title = 'Premium Channel'
                print(f"⚠️ [CHANNEL] Channel title empty - using fallback")

            # Determine tier by matching price and duration
            tier_number = 'Unknown'
            try:
                # Convert subscription_price to float for comparison
                price_float = float(subscription_price)

                # Check Tier 1
                if (sub_1_price is not None and sub_1_time is not None and
                    abs(float(sub_1_price) - price_float) < 0.01 and
                    sub_1_time == subscription_time_days):
                    tier_number = 1

                # Check Tier 2
                elif (sub_2_price is not None and sub_2_time is not None and
                      abs(float(sub_2_price) - price_float) < 0.01 and
                      sub_2_time == subscription_time_days):
                    tier_number = 2

                # Check Tier 3
                elif (sub_3_price is not None and sub_3_time is not None and
                      abs(float(sub_3_price) - price_float) < 0.01 and
                      sub_3_time == subscription_time_days):
                    tier_number = 3

                else:
                    print(f"⚠️ [CHANNEL] No tier match found for ${price_float}, {subscription_time_days} days")
                    tier_number = 'Unknown'

            except (ValueError, TypeError) as e:
                print(f"⚠️ [CHANNEL] Error matching tier: {e}")
                tier_number = 'Unknown'

            print(f"✅ [CHANNEL] Found: '{channel_title}', Tier {tier_number}")

            return {
                'channel_title': channel_title,
                'tier_number': tier_number
            }

        except Exception as e:
            print(f"❌ [CHANNEL] Error fetching channel details: {e}")
            import traceback
            traceback.print_exc()
            return {
                'channel_title': 'Premium Channel',
                'tier_number': 'Unknown'
            }

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [CHANNEL] Connection closed")
