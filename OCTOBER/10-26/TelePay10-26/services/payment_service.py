#!/usr/bin/env python
"""
💳 Payment Service for TelePay10-26
Handles NowPayments integration for invoice creation and payment tracking.
Extracted from start_np_gateway.py for better modularity.

Version: 2.0
Date: 2025-11-13
Architecture: NEW_ARCHITECTURE Phase 3.1
"""
import logging
import httpx
from typing import Dict, Any, Optional
from google.cloud import secretmanager
import os
import sys
from urllib.parse import quote  # For URL encoding query parameters

# Add shared_utils to path for message encryption
sys.path.append('/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26')
from shared_utils.message_encryption import encrypt_donation_message

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Payment gateway service for NowPayments integration.

    Features:
    - Invoice creation with NowPayments API
    - Order ID generation and management
    - IPN callback URL configuration
    - Comprehensive error handling
    - Secret Manager integration

    Usage:
        payment_service = PaymentService(api_key, ipn_callback_url)
        result = await payment_service.create_invoice(
            user_id=123,
            amount=29.99,
            order_id="PGP-123|-1001234567890",
            description="Premium Subscription"
        )
    """

    def __init__(self, api_key: Optional[str] = None, ipn_callback_url: Optional[str] = None):
        """
        Initialize payment service.

        Args:
            api_key: NowPayments API key (if None, fetches from Secret Manager)
            ipn_callback_url: IPN callback URL (if None, fetches from Secret Manager)
        """
        self.api_key = api_key or self._fetch_api_key()
        self.ipn_callback_url = ipn_callback_url or self._fetch_ipn_callback_url()
        self.api_url = "https://api.nowpayments.io/v1/invoice"

        # Log initialization status
        if self.api_key:
            logger.info("✅ [PAYMENT] Service initialized with API key")
        else:
            logger.error("❌ [PAYMENT] Service initialized WITHOUT API key")

        if self.ipn_callback_url:
            logger.info(f"✅ [PAYMENT] IPN callback URL configured")
        else:
            logger.warning("⚠️ [PAYMENT] IPN callback URL not configured - payment_id won't be captured")

    def _fetch_api_key(self) -> Optional[str]:
        """
        Fetch NowPayments API key from Google Secret Manager.

        Returns:
            API key string or None if not found

        Environment Variables Required:
            PAYMENT_PROVIDER_SECRET_NAME: Secret path in format projects/*/secrets/*/versions/*
        """
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("PAYMENT_PROVIDER_SECRET_NAME")

            if not secret_path:
                logger.error("❌ [PAYMENT] PAYMENT_PROVIDER_SECRET_NAME environment variable not set")
                return None

            response = client.access_secret_version(request={"name": secret_path})
            api_key = response.payload.data.decode("UTF-8")

            logger.info("✅ [PAYMENT] Successfully fetched API key from Secret Manager")
            return api_key

        except Exception as e:
            logger.error(f"❌ [PAYMENT] Error fetching API key from Secret Manager: {e}", exc_info=True)
            return None

    def _fetch_ipn_callback_url(self) -> Optional[str]:
        """
        Fetch IPN callback URL from Google Secret Manager.

        Returns:
            IPN callback URL string or None if not found

        Environment Variables Required:
            NOWPAYMENTS_IPN_CALLBACK_URL: Secret path in format projects/*/secrets/*/versions/*
        """
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("NOWPAYMENTS_IPN_CALLBACK_URL")

            if not secret_path:
                logger.warning("⚠️ [PAYMENT] NOWPAYMENTS_IPN_CALLBACK_URL environment variable not set")
                logger.warning("⚠️ [PAYMENT] Payment ID capture will not work without IPN callback URL")
                return None

            response = client.access_secret_version(request={"name": secret_path})
            ipn_url = response.payload.data.decode("UTF-8")

            logger.info("✅ [PAYMENT] Successfully fetched IPN callback URL from Secret Manager")
            return ipn_url

        except Exception as e:
            logger.error(f"❌ [PAYMENT] Error fetching IPN callback URL from Secret Manager: {e}", exc_info=True)
            logger.warning("⚠️ [PAYMENT] Payment ID capture will not work - falling back to None")
            return None

    async def create_invoice(
        self,
        user_id: int,
        amount: float,
        success_url: str,
        order_id: str,
        description: str = "Payment"
    ) -> Dict[str, Any]:
        """
        Create payment invoice with NowPayments API.

        Args:
            user_id: Telegram user ID
            amount: Payment amount in USD
            success_url: URL to redirect to after successful payment
            order_id: Unique order identifier (format: PGP-{user_id}|{channel_id})
            description: Payment description (default: "Payment")

        Returns:
            Dictionary with invoice creation result:
            {
                'success': True/False,
                'invoice_id': 'xxx' (if success),
                'invoice_url': 'https://...' (if success),
                'data': {...} (full API response if success),
                'error': 'error message' (if failed),
                'status_code': xxx (HTTP status code)
            }

        Example:
            result = await payment_service.create_invoice(
                user_id=123456789,
                amount=29.99,
                success_url="https://example.com/success",
                order_id="PGP-123456789|-1001234567890",
                description="Premium Subscription - Tier 1"
            )

            if result['success']:
                invoice_url = result['invoice_url']
                # Send invoice_url to user
        """
        # Validate API key
        if not self.api_key:
            logger.error("❌ [PAYMENT] Cannot create invoice - API key not available")
            return {
                'success': False,
                'error': 'Payment provider API key not configured'
            }

        # Log IPN status
        if not self.ipn_callback_url:
            logger.warning(f"⚠️ [PAYMENT] Creating invoice without IPN callback - payment_id won't be captured")

        # Build invoice payload
        invoice_payload = {
            'price_amount': amount,
            'price_currency': 'USD',
            'order_id': order_id,
            'order_description': description,
            'success_url': success_url,
            'ipn_callback_url': self.ipn_callback_url,  # IPN endpoint for payment_id capture
            'is_fixed_rate': False,  # Allow price to fluctuate with crypto market
            'is_fee_paid_by_user': False  # We absorb the fees
        }

        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }

        try:
            logger.info(f"📋 [PAYMENT] Creating invoice: user={user_id}, amount=${amount:.2f}, order={order_id}")

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=invoice_payload
                )

                if response.status_code == 200:
                    data = response.json()
                    invoice_id = data.get('id')
                    invoice_url = data.get('invoice_url')

                    logger.info(f"✅ [PAYMENT] Invoice created successfully")
                    logger.info(f"   Invoice ID: {invoice_id}")
                    logger.info(f"   Order ID: {order_id}")
                    logger.info(f"   Amount: ${amount:.2f} USD")

                    if self.ipn_callback_url:
                        logger.info(f"   IPN will be sent to: {self.ipn_callback_url}")
                    else:
                        logger.warning(f"   ⚠️ No IPN callback configured")

                    return {
                        'success': True,
                        'invoice_id': invoice_id,
                        'invoice_url': invoice_url,
                        'status_code': response.status_code,
                        'data': data
                    }
                else:
                    logger.error(f"❌ [PAYMENT] Invoice creation failed")
                    logger.error(f"   Status Code: {response.status_code}")
                    logger.error(f"   Error: {response.text}")

                    return {
                        'success': False,
                        'status_code': response.status_code,
                        'error': response.text
                    }

        except httpx.TimeoutException as e:
            logger.error(f"❌ [PAYMENT] Request timeout: {e}")
            return {
                'success': False,
                'error': f'Request timeout: {str(e)}'
            }

        except httpx.RequestError as e:
            logger.error(f"❌ [PAYMENT] Request error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Request failed: {str(e)}'
            }

        except Exception as e:
            logger.error(f"❌ [PAYMENT] Unexpected error creating invoice: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

    async def create_donation_invoice(
        self,
        user_id: int,
        amount: float,
        order_id: str,
        description: str,
        donation_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create payment invoice for donation with optional encrypted message.

        Args:
            user_id: Telegram user ID
            amount: Donation amount in USD
            order_id: Unique order identifier
            description: Payment description
            donation_message: Optional donation message (max 256 chars)

        Returns:
            Dictionary with invoice creation result
        """
        # Validate API key
        if not self.api_key:
            logger.error("❌ [PAYMENT] Cannot create invoice - API key not available")
            return {
                'success': False,
                'error': 'Payment provider API key not configured'
            }

        try:
            # Build base success URL with properly encoded order_id
            # URL encode the pipe character (|) in order_id format: PGP-{user_id}|{channel_id}
            base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')
            success_url = f"{base_url}/payment-processing?order_id={quote(order_id)}"

            # Encrypt and append message if provided (with URL encoding)
            if donation_message:
                logger.info(f"💬 [PAYMENT] Including donation message in invoice")
                encrypted_msg = encrypt_donation_message(donation_message)
                success_url += f"&msg={quote(encrypted_msg)}"  # URL encode encrypted message
                logger.info(f"   Encrypted message length: {len(encrypted_msg)} chars")

            # Call parent create_invoice method with constructed success_url
            result = await self.create_invoice(
                user_id=user_id,
                amount=amount,
                success_url=success_url,
                order_id=order_id,
                description=description
            )

            return result

        except Exception as e:
            logger.error(f"❌ [PAYMENT] Donation invoice creation failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Invoice creation failed: {str(e)}'
            }

    def generate_order_id(self, user_id: int, channel_id: str) -> str:
        """
        Generate unique order ID for payment tracking.

        Format: PGP-{user_id}|{channel_id}
        Example: PGP-123456789|-1001234567890

        The pipe (|) separator is used to preserve negative sign in channel_id.
        Telegram channel IDs are always negative for supergroups/channels.

        Args:
            user_id: Telegram user ID (positive integer)
            channel_id: Open channel ID (negative for channels, or "donation_default")

        Returns:
            Order ID string

        Example:
            order_id = payment_service.generate_order_id(123456789, "-1001234567890")
            # Returns: "PGP-123456789|-1001234567890"
        """
        # Validate channel_id format
        if channel_id != "donation_default" and not str(channel_id).startswith('-'):
            logger.warning(f"⚠️ [PAYMENT] Channel ID should be negative: {channel_id}")
            logger.warning(f"⚠️ [PAYMENT] Telegram channel IDs are always negative for supergroups/channels")
            # Auto-correct by adding negative sign
            channel_id = f"-{channel_id}"
            logger.info(f"✅ [PAYMENT] Auto-corrected to: {channel_id}")

        order_id = f"PGP-{user_id}|{channel_id}"

        logger.debug(f"📋 [PAYMENT] Generated order_id: {order_id}")
        logger.debug(f"   User ID: {user_id}")
        logger.debug(f"   Channel ID: {channel_id}")

        return order_id

    def parse_order_id(self, order_id: str) -> Optional[Dict[str, str]]:
        """
        Parse order ID back into components.

        Args:
            order_id: Order ID string (format: PGP-{user_id}|{channel_id})

        Returns:
            Dictionary with parsed components or None if invalid:
            {
                'user_id': 'xxx',
                'channel_id': 'yyy'
            }

        Example:
            components = payment_service.parse_order_id("PGP-123456789|-1001234567890")
            # Returns: {'user_id': '123456789', 'channel_id': '-1001234567890'}
        """
        try:
            # Remove PGP- prefix
            if not order_id.startswith('PGP-'):
                logger.error(f"❌ [PAYMENT] Invalid order_id format: {order_id}")
                return None

            # Split by pipe separator
            parts = order_id[4:].split('|')
            if len(parts) != 2:
                logger.error(f"❌ [PAYMENT] Invalid order_id format: {order_id}")
                return None

            user_id, channel_id = parts

            logger.debug(f"✅ [PAYMENT] Parsed order_id: user={user_id}, channel={channel_id}")

            return {
                'user_id': user_id,
                'channel_id': channel_id
            }

        except Exception as e:
            logger.error(f"❌ [PAYMENT] Error parsing order_id '{order_id}': {e}")
            return None

    def is_configured(self) -> bool:
        """
        Check if payment service is properly configured.

        Returns:
            True if API key is available, False otherwise
        """
        return self.api_key is not None

    def get_status(self) -> Dict[str, Any]:
        """
        Get payment service status.

        Returns:
            Dictionary with service status:
            {
                'configured': True/False,
                'api_key_available': True/False,
                'ipn_callback_configured': True/False,
                'api_url': 'https://...'
            }
        """
        return {
            'configured': self.is_configured(),
            'api_key_available': self.api_key is not None,
            'ipn_callback_configured': self.ipn_callback_url is not None,
            'api_url': self.api_url
        }

    async def start_np_gateway_new(self, update, context, amount, channel_id, duration, webhook_manager, db_manager):
        """
        🆕 COMPATIBILITY WRAPPER for old PaymentGatewayManager.start_np_gateway_new()

        This allows gradual migration from old to new payment service.
        Provides backward compatibility while the codebase transitions.

        ⚠️ DEPRECATED: This method exists only for backward compatibility.
        New code should use create_invoice() directly.

        Args:
            update: Telegram Update object
            context: Telegram Context object
            amount: Payment amount in USD
            channel_id: Channel/group ID (can be string or int)
            duration: Subscription duration in days (for description)
            webhook_manager: Legacy parameter (not used)
            db_manager: Legacy parameter (not used)

        Returns:
            None (sends message to user directly via Telegram)

        Migration Path:
            Old code:
                await payment_manager.start_np_gateway_new(update, context, amount, channel_id, duration, webhook_manager, db_manager)

            New code:
                result = await payment_service.create_invoice(user_id, amount, success_url, order_id, description)
                if result['success']:
                    # Send invoice_url to user
        """
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        logger.warning("⚠️ [PAYMENT] Using compatibility wrapper - migrate to create_invoice()")
        logger.warning("⚠️ [PAYMENT] This wrapper will be removed in future versions")

        user_id = update.effective_user.id

        # Ensure channel_id is string (can be int from legacy code)
        channel_id = str(channel_id)

        # Generate order ID (format: PGP-{user_id}|{channel_id})
        order_id = self.generate_order_id(user_id, channel_id)

        # Build success URL (use Telegram deep link)
        bot_username = context.bot.username
        success_url = f"https://t.me/{bot_username}?start=payment_success"

        # Create invoice
        result = await self.create_invoice(
            user_id=user_id,
            amount=amount,
            success_url=success_url,
            order_id=order_id,
            description=f"Subscription - {duration} days"
        )

        if result['success']:
            # Send payment link to user
            invoice_url = result['invoice_url']
            invoice_id = result['invoice_id']

            # Format payment message (same as legacy)
            message_text = (
                f"💳 <b>Payment Gateway</b>\n\n"
                f"Amount: <b>${amount:.2f} USD</b>\n"
                f"Duration: <b>{duration} days</b>\n\n"
                f"Click the button below to complete your payment:"
            )

            # Create payment button keyboard
            keyboard = [[
                InlineKeyboardButton("💰 Pay Now", url=invoice_url)
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send message to user
            await update.effective_message.reply_text(
                text=message_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )

            logger.info(f"✅ [PAYMENT] Payment link sent to user {user_id}")
            logger.info(f"   Invoice ID: {invoice_id}")
            logger.info(f"   Amount: ${amount:.2f}")
            logger.info(f"   Duration: {duration} days")

        else:
            # Error creating invoice - inform user
            error_message = "❌ <b>Payment Error</b>\n\nCould not create payment invoice. Please try again later or contact support."
            await update.effective_message.reply_text(
                text=error_message,
                parse_mode='HTML'
            )

            logger.error(f"❌ [PAYMENT] Invoice creation failed for user {user_id}")
            logger.error(f"   Error: {result.get('error', 'Unknown error')}")


def init_payment_service(
    api_key: Optional[str] = None,
    ipn_callback_url: Optional[str] = None
) -> PaymentService:
    """
    Factory function to initialize payment service.

    Args:
        api_key: NowPayments API key (if None, fetches from Secret Manager)
        ipn_callback_url: IPN callback URL (if None, fetches from Secret Manager)

    Returns:
        PaymentService instance

    Usage:
        # Auto-fetch from Secret Manager
        payment_service = init_payment_service()

        # Or provide directly
        payment_service = init_payment_service(
            api_key="your_api_key",
            ipn_callback_url="https://your-domain.com/ipn"
        )
    """
    return PaymentService(api_key=api_key, ipn_callback_url=ipn_callback_url)


logger.info("✅ [PAYMENT] Payment service module loaded")
