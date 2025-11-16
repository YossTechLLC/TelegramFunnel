#!/usr/bin/env python
"""
💳 Payment Service for PGP_SERVER_v1
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

    def __init__(self, api_key: Optional[str] = None, ipn_callback_url: Optional[str] = None, database_manager=None):
        """
        Initialize payment service.

        Args:
            api_key: NowPayments API key (if None, fetches from Secret Manager)
            ipn_callback_url: IPN callback URL (if None, fetches from Secret Manager)
            database_manager: DatabaseManager instance for fetching channel details (optional)
        """
        self.api_key = api_key or self._fetch_api_key()
        self.ipn_callback_url = ipn_callback_url or self._fetch_ipn_callback_url()
        self.database_manager = database_manager
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

        if self.database_manager:
            logger.info("✅ [PAYMENT] Database manager configured for channel details")
        else:
            logger.warning("⚠️ [PAYMENT] No database manager - channel details won't be available")

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

    @staticmethod
    def get_telegram_user_id(update) -> Optional[int]:
        """
        Extract the user ID from a Telegram update.

        Args:
            update: The Telegram update object

        Returns:
            The user ID if found, None otherwise

        Example:
            user_id = PaymentService.get_telegram_user_id(update)
        """
        if hasattr(update, "effective_user") and update.effective_user:
            return update.effective_user.id
        if hasattr(update, "callback_query") and update.callback_query and update.callback_query.from_user:
            return update.callback_query.from_user.id
        return None

    async def start_payment_flow(self, update, context, sub_value: float,
                                 open_channel_id: str, secure_success_url: str,
                                 closed_channel_title: str = "Premium Channel",
                                 closed_channel_description: str = "exclusive content",
                                 sub_time: int = 30, order_id: str = None) -> None:
        """
        Start the complete payment flow for a user with Telegram WebApp integration.

        This method implements the FULL OLD functionality including:
        - ReplyKeyboardMarkup with WebAppInfo button (Telegram Mini App)
        - HTML formatted message with channel details
        - Order ID generation with validation
        - Comprehensive error handling

        Args:
            update: Telegram Update object
            context: Telegram Context object
            sub_value: Subscription amount in USD
            open_channel_id: Open channel ID
            secure_success_url: Success URL for post-payment redirect
            closed_channel_title: Title of the closed channel (default: "Premium Channel")
            closed_channel_description: Description of the closed channel (default: "exclusive content")
            sub_time: Subscription duration in days (default: 30)
            order_id: Optional pre-created order_id (to avoid duplication)

        Returns:
            None (sends message to user via Telegram)

        Example:
            await payment_service.start_payment_flow(
                update=update,
                context=context,
                sub_value=29.99,
                open_channel_id="-1001234567890",
                secure_success_url="https://storage.googleapis.com/...",
                closed_channel_title="VIP Channel",
                closed_channel_description="exclusive trading signals",
                sub_time=30
            )
        """
        from telegram import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

        logger.info(f"💳 [PAYMENT] Starting payment flow: amount=${sub_value:.2f}, channel_id={open_channel_id}")

        user_id = self.get_telegram_user_id(update)
        if not user_id:
            chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
            if chat_id:
                await context.bot.send_message(chat_id, "❌ Could not determine user ID.")
            logger.error("❌ [PAYMENT] Could not extract user ID from update")
            return

        # Create unique order ID if not provided
        if not order_id:
            # Validate that open_channel_id is negative (Telegram requirement)
            if not str(open_channel_id).startswith('-') and open_channel_id != "donation_default":
                logger.warning(f"⚠️ [PAYMENT] open_channel_id should be negative: {open_channel_id}")
                logger.warning(f"⚠️ [PAYMENT] Telegram channel IDs are always negative for supergroups/channels")
                # Add negative sign to fix misconfiguration
                open_channel_id = f"-{open_channel_id}"
                logger.info(f"✅ [PAYMENT] Corrected to: {open_channel_id}")

            order_id = self.generate_order_id(user_id, open_channel_id)
            logger.info(f"📋 [PAYMENT] Created order_id: {order_id}")
        else:
            logger.info(f"📋 [PAYMENT] Using provided order_id: {order_id}")

        # Create payment invoice
        invoice_result = await self.create_invoice(
            user_id=user_id,
            amount=sub_value,
            success_url=secure_success_url,
            order_id=order_id,
            description=f"Subscription - {sub_time} days"
        )

        # Determine chat ID for response
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
        bot = context.bot

        if invoice_result.get("success"):
            invoice_url = invoice_result.get("invoice_url", "<no url>")
            logger.info(f"✅ [PAYMENT] Payment gateway created successfully for ${sub_value:.2f}")
            logger.info(f"🔗 [PAYMENT] Invoice URL: {invoice_url}")

            # CRITICAL: Use ReplyKeyboardMarkup with WebAppInfo (Telegram Mini App)
            # This is the key difference from the compatibility wrapper
            reply_markup = ReplyKeyboardMarkup.from_button(
                KeyboardButton(
                    text="💰 Start Payment Gateway",
                    web_app=WebAppInfo(url=invoice_url),
                )
            )

            # Enhanced HTML message with channel details
            text = (
                f"💳 <b>Click the button below to start the Payment Gateway</b> 🚀\n\n"
                f"🔒 <b>Private Channel:</b> {closed_channel_title}\n"
                f"📝 <b>Channel Description:</b> {closed_channel_description}\n"
                f"💰 <b>Price:</b> ${sub_value:.2f}\n"
                f"⏰ <b>Duration:</b> {sub_time} days"
            )

            await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
            logger.info(f"✅ [PAYMENT] Payment message sent to user {user_id}")
        else:
            error_msg = invoice_result.get("error", "Unknown error")
            status_code = invoice_result.get("status_code", "N/A")
            await bot.send_message(
                chat_id,
                f"❌ NowPayments error — status {status_code}\n{error_msg}",
            )
            logger.error(f"❌ [PAYMENT] Invoice creation failed for user {user_id}: {error_msg}")

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
        🆕 FULL-FEATURED COMPATIBILITY WRAPPER with database integration.

        This provides COMPLETE backward compatibility with OLD PaymentGatewayManager.start_np_gateway_new()
        including database integration, WebApp button, static landing page, and channel details.

        ✅ Phase 2 Migration: Now includes ALL features from OLD implementation

        Args:
            update: Telegram Update object
            context: Telegram Context object
            amount: Payment amount in USD (global_sub_value)
            channel_id: Channel/group ID (global_open_channel_id)
            duration: Subscription duration in days (global_sub_time)
            webhook_manager: Legacy parameter (not used - replaced by static landing page)
            db_manager: DatabaseManager instance for fetching channel details

        Returns:
            None (sends message to user directly via Telegram)

        Features:
            - Database integration for closed_channel_id, wallet_info, channel_details
            - ReplyKeyboardMarkup with WebAppInfo (Telegram Mini App)
            - Static landing page URL construction
            - Enhanced message formatting with channel details
            - Donation default handling
        """
        from urllib.parse import quote

        logger.info(f"💳 [PAYMENT] start_np_gateway_new called: amount=${amount:.2f}, channel={channel_id}, duration={duration}d")

        user_id = self.get_telegram_user_id(update)
        if not user_id:
            chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
            if chat_id:
                await context.bot.send_message(chat_id, "❌ Could not determine user ID.")
            return

        # Ensure channel_id is string (can be int from legacy code)
        channel_id = str(channel_id)

        # Use database_manager from instance if available, fallback to parameter
        db_mgr = self.database_manager or db_manager

        # Handle special donation default case
        if channel_id == "donation_default":
            logger.info("🎯 [PAYMENT] Handling donation_default case - using placeholder values")
            closed_channel_id = "donation_default_closed"
            closed_channel_title = "Donation Channel"
            closed_channel_description = "supporting our community"
        else:
            if not db_mgr:
                logger.error("❌ [PAYMENT] No database manager available for channel details")
                chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
                if chat_id:
                    await context.bot.send_message(chat_id, "❌ Database not available. Please contact support.")
                return

            # Get closed channel ID from database
            closed_channel_id = db_mgr.fetch_closed_channel_id(channel_id)
            if not closed_channel_id:
                chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
                await context.bot.send_message(chat_id, "❌ Could not find a closed_channel_id for this open_channel_id. Please check your database!")
                logger.error(f"❌ [PAYMENT] No closed_channel_id found for {channel_id}")
                return

            # Get wallet info from database (now includes network)
            wallet_address, payout_currency, payout_network = db_mgr.fetch_client_wallet_info(channel_id)
            logger.info(f"💰 [PAYMENT] Retrieved wallet info for {channel_id}: wallet='{wallet_address}', currency='{payout_currency}', network='{payout_network}'")

            # Get channel title and description info for personalized message
            _, channel_info_map = db_mgr.fetch_open_channel_list()
            channel_data = channel_info_map.get(channel_id, {})
            closed_channel_title = channel_data.get("closed_channel_title", "Premium Channel")
            closed_channel_description = channel_data.get("closed_channel_description", "exclusive content")
            logger.info(f"🏷️ [PAYMENT] Retrieved channel info: title='{closed_channel_title}', description='{closed_channel_description}'")

        # Validate that channel_id is negative (Telegram requirement)
        if not str(channel_id).startswith('-') and channel_id != "donation_default":
            logger.warning(f"⚠️ [PAYMENT] channel_id should be negative: {channel_id}")
            # Add negative sign to fix misconfiguration
            channel_id = f"-{channel_id}"
            logger.info(f"✅ [PAYMENT] Corrected to: {channel_id}")

        # Create order_id for NowPayments tracking
        order_id = self.generate_order_id(user_id, channel_id)

        # Build success URL pointing to static landing page
        # The landing page will poll payment status via API
        landing_page_base_url = "https://storage.googleapis.com/paygateprime-static/payment-processing.html"
        secure_success_url = f"{landing_page_base_url}?order_id={quote(order_id, safe='')}"

        logger.info(f"🔗 [PAYMENT] Using static landing page URL: {secure_success_url}")

        # Use the new start_payment_flow method with ALL channel info
        await self.start_payment_flow(
            update=update,
            context=context,
            sub_value=amount,
            open_channel_id=channel_id,
            secure_success_url=secure_success_url,
            closed_channel_title=closed_channel_title,
            closed_channel_description=closed_channel_description,
            sub_time=duration,
            order_id=order_id  # Pass order_id to avoid duplicate creation
        )


def init_payment_service(
    api_key: Optional[str] = None,
    ipn_callback_url: Optional[str] = None,
    database_manager=None
) -> PaymentService:
    """
    Factory function to initialize payment service.

    Args:
        api_key: NowPayments API key (if None, fetches from Secret Manager)
        ipn_callback_url: IPN callback URL (if None, fetches from Secret Manager)
        database_manager: DatabaseManager instance for fetching channel details (optional)

    Returns:
        PaymentService instance

    Usage:
        # Auto-fetch from Secret Manager without database
        payment_service = init_payment_service()

        # With database manager for full features
        payment_service = init_payment_service(database_manager=db_manager)

        # Or provide all parameters directly
        payment_service = init_payment_service(
            api_key="your_api_key",
            ipn_callback_url="https://your-domain.com/ipn",
            database_manager=db_manager
        )
    """
    return PaymentService(api_key=api_key, ipn_callback_url=ipn_callback_url, database_manager=database_manager)


logger.info("✅ [PAYMENT] Payment service module loaded")
