#!/usr/bin/env python
"""
ChangeNow Transaction Tracker for HPW10-9 Host Payment Wallet Service.
Links NowPayments payment_id to ChangeNow transaction details and
retrieves deposit information for automated payments.
"""
import requests
from typing import Optional, Dict, Any


class ChangeNowTracker:
    """
    Tracks and retrieves ChangeNow transaction information.
    """

    def __init__(self, database_manager):
        """
        Initialize the ChangeNow tracker.

        Args:
            database_manager: Database manager instance for lookups
        """
        self.db_manager = database_manager
        print(f"🔗 [CHANGENOW_TRACKER] Initialized")

    def link_payment_to_changenow(self, payment_id: str, changenow_tx_id: str) -> bool:
        """
        Link a NowPayments payment_id to a ChangeNow transaction_id.

        Args:
            payment_id: NowPayments payment identifier
            changenow_tx_id: ChangeNow transaction identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update database record with ChangeNow transaction ID
            conn = self.db_manager.get_connection()
            cur = conn.cursor()

            update_query = """
                UPDATE host_payment_queue
                SET changenow_tx_id = %s, updated_at = NOW()
                WHERE payment_id = %s
            """

            cur.execute(update_query, (changenow_tx_id, payment_id))
            conn.commit()

            rows_affected = cur.rowcount
            cur.close()
            conn.close()

            if rows_affected > 0:
                print(f"✅ [CHANGENOW_TRACKER] Linked payment {payment_id} to ChangeNow TX {changenow_tx_id}")
                return True
            else:
                print(f"⚠️ [CHANGENOW_TRACKER] Payment {payment_id} not found in database")
                return False

        except Exception as e:
            print(f"❌ [CHANGENOW_TRACKER] Error linking payment to ChangeNow: {e}")
            return False

    def get_deposit_info_from_database(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve ChangeNow deposit information from database.

        Args:
            payment_id: NowPayments payment identifier

        Returns:
            Deposit info dict or None if not found
        """
        try:
            payment = self.db_manager.get_payment_by_id(payment_id)

            if payment:
                deposit_info = {
                    'payin_address': payment.get('payin_address'),
                    'expected_amount_eth': payment.get('expected_amount_eth'),
                    'changenow_tx_id': payment.get('changenow_tx_id'),
                    'order_id': payment.get('order_id')
                }

                print(f"✅ [CHANGENOW_TRACKER] Retrieved deposit info for payment {payment_id}")
                print(f"   Payin address: {deposit_info['payin_address']}")
                print(f"   Expected amount: {deposit_info['expected_amount_eth']} ETH")

                return deposit_info
            else:
                print(f"❌ [CHANGENOW_TRACKER] Payment {payment_id} not found in database")
                return None

        except Exception as e:
            print(f"❌ [CHANGENOW_TRACKER] Error retrieving deposit info: {e}")
            return None

    def parse_changenow_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse ChangeNow transaction data from GCSplit7-14 webhook.

        Args:
            webhook_data: Webhook payload from GCSplit7-14

        Returns:
            Parsed transaction data
        """
        try:
            transaction_data = {
                'changenow_tx_id': webhook_data.get('transaction_id'),
                'payin_address': webhook_data.get('payin_address'),
                'expected_amount_eth': float(webhook_data.get('expected_amount', 0)),
                'order_id': webhook_data.get('order_id'),
                'user_id': webhook_data.get('user_id'),
                'payout_address': webhook_data.get('payout_address'),
                'payout_currency': webhook_data.get('payout_currency')
            }

            print(f"📊 [CHANGENOW_TRACKER] Parsed ChangeNow transaction data:")
            print(f"   TX ID: {transaction_data['changenow_tx_id']}")
            print(f"   Payin address: {transaction_data['payin_address']}")
            print(f"   Amount: {transaction_data['expected_amount_eth']} ETH")
            print(f"   Order ID: {transaction_data['order_id']}")

            return transaction_data

        except Exception as e:
            print(f"❌ [CHANGENOW_TRACKER] Error parsing webhook data: {e}")
            return {}

    def validate_deposit_address(self, address: str) -> bool:
        """
        Validate that a ChangeNow deposit address is properly formatted.

        Args:
            address: Ethereum address to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Basic Ethereum address validation
            if not address or len(address) != 42:
                print(f"❌ [CHANGENOW_TRACKER] Invalid address length: {address}")
                return False

            if not address.startswith('0x'):
                print(f"❌ [CHANGENOW_TRACKER] Address missing 0x prefix: {address}")
                return False

            # Check if hex string
            int(address, 16)

            print(f"✅ [CHANGENOW_TRACKER] Valid deposit address: {address}")
            return True

        except ValueError:
            print(f"❌ [CHANGENOW_TRACKER] Invalid hex address: {address}")
            return False
        except Exception as e:
            print(f"❌ [CHANGENOW_TRACKER] Address validation error: {e}")
            return False
