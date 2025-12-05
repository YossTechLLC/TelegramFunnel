#!/usr/bin/env python
"""
Payment Gateway Manager for GCDonationHandler
Handles NowPayments API integration for donation invoices

This module provides a self-contained interface to the NowPayments API
for creating payment invoices. It uses synchronous HTTP requests for
Flask compatibility.
"""

import logging
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)


class PaymentGatewayManager:
    """
    Manages NowPayments API operations for donation invoices.

    This class handles creating payment invoices through the NowPayments
    gateway. It uses synchronous HTTP requests to ensure compatibility
    with Flask synchronous handlers.

    Attributes:
        payment_token: NowPayments API key
        ipn_callback_url: IPN callback URL for payment notifications
        api_url: NowPayments API endpoint for invoice creation
    """

    def __init__(self, payment_token: str, ipn_callback_url: str):
        """
        Initialize the PaymentGatewayManager.

        Args:
            payment_token: NowPayments API key
            ipn_callback_url: URL for IPN callbacks (payment_id capture)

        Raises:
            ValueError: If payment_token is empty or None
        """
        if not payment_token:
            raise ValueError("Payment token is required")

        self.payment_token = payment_token
        self.ipn_callback_url = ipn_callback_url
        self.api_url = "https://api.nowpayments.io/v1/invoice"

        logger.info("💳 PaymentGatewayManager initialized")
        if not ipn_callback_url:
            logger.warning("⚠️ IPN callback URL not configured - payment_id won't be captured")

    def create_payment_invoice(
        self,
        user_id: int,
        amount: float,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Create a payment invoice with NowPayments.

        Generates a unique invoice URL for the user to complete their donation.
        The order_id format should be: PGP-{user_id}|{open_channel_id}

        Args:
            user_id: Telegram user ID
            amount: Donation amount in USD
            order_id: Unique order identifier (e.g., "PGP-123456|channel_id")

        Returns:
            Dictionary with result:
            {
                'success': True,
                'data': {
                    'invoice_url': str,
                    'invoice_id': str
                }
            } on success

            {
                'success': False,
                'error': str
            } on failure

        Example:
            >>> manager = PaymentGatewayManager(token, ipn_url)
            >>> result = manager.create_payment_invoice(
            ...     user_id=123456789,
            ...     amount=25.50,
            ...     order_id="PGP-123456789|-1003268562225"
            ... )
            >>> if result['success']:
            ...     print(f"Invoice URL: {result['data']['invoice_url']}")
        """
        # Construct invoice payload
        payload = {
            "price_amount": amount,
            "price_currency": "USD",
            "order_id": order_id,
            "order_description": f"Donation for channel",
            "ipn_callback_url": self.ipn_callback_url,
            "success_url": "https://paygateprime.com/success",
            "cancel_url": "https://paygateprime.com/cancel",
            "is_fixed_rate": False,
            "is_fee_paid_by_user": False
        }

        # Set request headers
        headers = {
            "x-api-key": self.payment_token,
            "Content-Type": "application/json"
        }

        logger.info(f"💳 Creating invoice for user {user_id}, amount ${amount:.2f}, order_id: {order_id}")

        try:
            # Use synchronous httpx.Client for Flask compatibility
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.api_url,
                    json=payload,
                    headers=headers
                )

                # Check HTTP status
                if response.status_code == 200:
                    response_data = response.json()
                    invoice_id = response_data.get('id')
                    invoice_url = response_data.get('invoice_url')

                    if not invoice_url:
                        logger.error(f"❌ Invoice created but no URL in response: {response_data}")
                        return {
                            'success': False,
                            'error': 'No invoice URL in API response'
                        }

                    logger.info(f"✅ Invoice created successfully: {invoice_url}")
                    logger.info(f"💳 Invoice ID: {invoice_id}, Order ID: {order_id}")

                    return {
                        'success': True,
                        'data': {
                            'invoice_url': invoice_url,
                            'invoice_id': invoice_id
                        }
                    }

                elif response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get('message', 'Bad request')
                    logger.error(f"❌ NowPayments API error (400): {error_msg}")
                    return {
                        'success': False,
                        'error': f'API validation error: {error_msg}'
                    }

                elif response.status_code == 401:
                    logger.error("❌ NowPayments authentication failed - invalid API key")
                    return {
                        'success': False,
                        'error': 'Payment gateway authentication failed'
                    }

                elif response.status_code == 500:
                    logger.error("❌ NowPayments server error (500)")
                    return {
                        'success': False,
                        'error': 'Payment gateway server error'
                    }

                else:
                    logger.error(f"❌ Unexpected NowPayments response: {response.status_code}")
                    return {
                        'success': False,
                        'error': f'Unexpected API response: {response.status_code}'
                    }

        except httpx.TimeoutException:
            logger.error("❌ NowPayments API timeout (>30s)")
            return {
                'success': False,
                'error': 'Payment gateway timeout - please try again'
            }

        except httpx.ConnectError as e:
            logger.error(f"❌ Failed to connect to NowPayments API: {e}")
            return {
                'success': False,
                'error': 'Cannot reach payment gateway'
            }

        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error during invoice creation: {e}")
            return {
                'success': False,
                'error': 'Payment gateway communication error'
            }

        except Exception as e:
            logger.error(f"❌ Unexpected error during invoice creation: {e}")
            return {
                'success': False,
                'error': 'Internal error creating invoice'
            }
