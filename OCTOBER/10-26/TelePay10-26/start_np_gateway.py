#!/usr/bin/env python
import os
import httpx
from typing import Dict, Any, Optional
from google.cloud import secretmanager
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

class PaymentGatewayManager:
    def __init__(self, payment_token: str = None, ipn_callback_url: str = None):
        """
        Initialize the PaymentGatewayManager.

        Args:
            payment_token: The NowPayments API token. If None, will fetch from secrets
            ipn_callback_url: The IPN callback URL. If None, will fetch from secrets
        """
        self.payment_token = payment_token or self.fetch_payment_provider_token()
        self.ipn_callback_url = ipn_callback_url or self.fetch_ipn_callback_url()
        self.api_url = "https://api.nowpayments.io/v1/invoice"
    
    def fetch_payment_provider_token(self) -> Optional[str]:
        """Fetch the payment provider token from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("PAYMENT_PROVIDER_SECRET_NAME")
            if not secret_path:
                raise ValueError("Environment variable PAYMENT_PROVIDER_SECRET_NAME is not set.")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ Error fetching the PAYMENT_PROVIDER_TOKEN: {e}")
            return None

    def fetch_ipn_callback_url(self) -> Optional[str]:
        """Fetch the IPN callback URL from Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("NOWPAYMENTS_IPN_CALLBACK_URL")
            if not secret_path:
                print(f"⚠️ [IPN] Environment variable NOWPAYMENTS_IPN_CALLBACK_URL is not set")
                print(f"⚠️ [IPN] Payment ID capture will not work - IPN callback URL unavailable")
                return None
            response = client.access_secret_version(request={"name": secret_path})
            ipn_url = response.payload.data.decode("UTF-8")
            print(f"✅ [IPN] Successfully fetched IPN callback URL from Secret Manager")
            return ipn_url
        except Exception as e:
            print(f"❌ [IPN] Error fetching IPN callback URL from Secret Manager: {e}")
            print(f"⚠️ [IPN] Payment ID capture will not work - falling back to None")
            return None
    
    async def create_payment_invoice(self, user_id: int, amount: float, success_url: str, order_id: str) -> Dict[str, Any]:
        """
        Create a payment invoice with NowPayments.

        Args:
            user_id: The user's Telegram ID
            amount: The payment amount in USD
            success_url: The URL to redirect to after successful payment
            order_id: Unique order identifier

        Returns:
            Dictionary containing the API response
        """
        if not self.payment_token:
            return {"error": "Payment provider token not available"}

        # Use IPN callback URL from instance (fetched from Secret Manager in __init__)
        if not self.ipn_callback_url:
            print(f"⚠️ [INVOICE] IPN callback URL not configured - payment_id won't be captured")

        invoice_payload = {
            "price_amount": amount,
            "price_currency": "USD",
            "order_id": order_id,
            "order_description": "Payment-Test-1",
            "success_url": success_url,
            "ipn_callback_url": self.ipn_callback_url,  # IPN endpoint for payment_id capture
            "is_fixed_rate": False,
            "is_fee_paid_by_user": False
        }
        
        headers = {
            "x-api-key": self.payment_token,
            "Content-Type": "application/json",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.api_url,
                    headers=headers,
                    json=invoice_payload,
                )
                
                if resp.status_code == 200:
                    response_data = resp.json()
                    invoice_id = response_data.get('id')

                    # Log invoice creation with IPN callback URL
                    print(f"📋 [INVOICE] Created invoice_id: {invoice_id}")
                    print(f"📋 [INVOICE] Order ID: {order_id}")
                    if self.ipn_callback_url:
                        print(f"📋 [INVOICE] IPN will be sent to: {self.ipn_callback_url}")
                    else:
                        print(f"⚠️ [INVOICE] IPN callback URL not set - payment_id won't be captured")

                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "data": response_data
                    }
                else:
                    return {
                        "success": False,
                        "status_code": resp.status_code,
                        "error": resp.text
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }
    
    def get_telegram_user_id(self, update: Update) -> Optional[int]:
        """
        Extract the user ID from a Telegram update.
        
        Args:
            update: The Telegram update object
            
        Returns:
            The user ID if found, None otherwise
        """
        if hasattr(update, "effective_user") and update.effective_user:
            return update.effective_user.id
        if hasattr(update, "callback_query") and update.callback_query and update.callback_query.from_user:
            return update.callback_query.from_user.id
        return None
    
    async def start_payment_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                sub_value: float, open_channel_id: str,
                                secure_success_url: str, closed_channel_title: str = "Premium Channel",
                                closed_channel_description: str = "exclusive content", sub_time: int = 30,
                                order_id: str = None) -> None:
        """
        Start the complete payment flow for a user.

        Args:
            update: The Telegram update object
            context: The bot context
            sub_value: The subscription amount
            open_channel_id: The open channel ID
            secure_success_url: The success URL for post-payment redirect (now points to landing page)
            closed_channel_title: The title of the closed channel
            closed_channel_description: The description of the closed channel
            sub_time: The subscription duration in days
            order_id: Optional pre-created order_id (to avoid duplication)
        """
        print(f"💳 [DEBUG] Starting payment flow: amount=${sub_value:.2f}, channel_id={open_channel_id}")
        user_id = self.get_telegram_user_id(update)
        if not user_id:
            chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
            if chat_id:
                await context.bot.send_message(chat_id, "❌ Could not determine user ID.")
            return

        # Create unique order ID if not provided
        if not order_id:
            # FIXED: Use | separator to preserve negative sign in channel_id
            # Format: PGP-{user_id}|{open_channel_id}
            # Example: PGP-6271402111|-1003268562225

            # Validate that open_channel_id is negative (Telegram requirement)
            if not str(open_channel_id).startswith('-'):
                print(f"⚠️ [VALIDATION] open_channel_id should be negative: {open_channel_id}")
                print(f"⚠️ [VALIDATION] Telegram channel IDs are always negative for supergroups/channels")
                # Add negative sign to fix misconfiguration
                open_channel_id = f"-{open_channel_id}" if open_channel_id != "donation_default" else open_channel_id
                print(f"✅ [VALIDATION] Corrected to: {open_channel_id}")

            order_id = f"PGP-{user_id}|{open_channel_id}"

            # Debug logging
            print(f"📋 [ORDER] Created order_id: {order_id}")
            print(f"   User ID: {user_id}")
            print(f"   Open Channel ID: {open_channel_id}")
            print(f"   Channel ID is negative: {str(open_channel_id).startswith('-')}")
        else:
            print(f"📋 [ORDER] Using provided order_id: {order_id}")

        # Create payment invoice
        invoice_result = await self.create_payment_invoice(
            user_id=user_id,
            amount=sub_value,
            success_url=secure_success_url,
            order_id=order_id
        )
        
        # Determine chat ID for response
        chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
        bot = context.bot
        
        if invoice_result.get("success"):
            invoice_url = invoice_result["data"].get("invoice_url", "<no url>")
            print(f"✅ [DEBUG] Payment gateway created successfully for ${sub_value:.2f}")
            print(f"🔗 [DEBUG] Invoice URL: {invoice_url}")
            
            reply_markup = ReplyKeyboardMarkup.from_button(
                KeyboardButton(
                    text="💰 Start Payment Gateway",
                    web_app=WebAppInfo(url=invoice_url),
                )
            )
            text = (
                f"💳 <b>Click the button below to start the Payment Gateway</b> 🚀\n\n"
                f"🔒 <b>Private Channel:</b> {closed_channel_title}\n"
                f"📝 <b>Channel Description:</b> {closed_channel_description}\n"
                f"💰 <b>Price:</b> ${sub_value:.2f}\n"
                f"⏰ <b>Duration:</b> {sub_time} days\n\n"
                f"🧪 <b>For testing purposes, here is the Success URL</b> 🔗\n"
                f"<code>{secure_success_url}</code>"
            )
            await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            error_msg = invoice_result.get("error", "Unknown error")
            status_code = invoice_result.get("status_code", "N/A")
            await bot.send_message(
                chat_id,
                f"nowpayments error ❌ — status {status_code}\n{error_msg}",
            )

    async def start_np_gateway_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  global_sub_value: float, global_open_channel_id: str,
                                  global_sub_time: int, webhook_manager, db_manager) -> None:
        """
        Legacy function for backward compatibility with existing code.
        This wraps the new start_payment_flow method.
        """
        user_id = self.get_telegram_user_id(update)
        if not user_id:
            chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
            if chat_id:
                await context.bot.send_message(chat_id, "❌ Could not determine user ID.")
            return

        # Handle special donation default case
        if global_open_channel_id == "donation_default":
            print("🎯 [DEBUG] Handling donation_default case - using placeholder values")
            closed_channel_id = "donation_default_closed"
            wallet_address = ""
            payout_currency = ""
            payout_network = ""
            closed_channel_title = "Donation Channel"
            closed_channel_description = "supporting our community"
        else:
            # Get closed channel ID from database
            closed_channel_id = db_manager.fetch_closed_channel_id(global_open_channel_id)
            if not closed_channel_id:
                chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
                await context.bot.send_message(chat_id, "❌ Could not find a closed_channel_id for this open_channel_id. Please check your database!")
                return

            # Get wallet info from database (now includes network)
            wallet_address, payout_currency, payout_network = db_manager.fetch_client_wallet_info(global_open_channel_id)
            print(f"💰 [DEBUG] Retrieved wallet info for {global_open_channel_id}: wallet='{wallet_address}', currency='{payout_currency}', network='{payout_network}'")

            # Get channel title and description info for personalized message
            _, channel_info_map = db_manager.fetch_open_channel_list()
            channel_data = channel_info_map.get(global_open_channel_id, {})
            closed_channel_title = channel_data.get("closed_channel_title", "Premium Channel")
            closed_channel_description = channel_data.get("closed_channel_description", "exclusive content")
            print(f"🏷️ [DEBUG] Retrieved channel info: title='{closed_channel_title}', description='{closed_channel_description}'")


        # Create order_id for NowPayments tracking
        # Format: PGP-{user_id}|{open_channel_id}
        # Example: PGP-6271402111|-1003268562225

        # Validate that open_channel_id is negative (Telegram requirement)
        if not str(global_open_channel_id).startswith('-') and global_open_channel_id != "donation_default":
            print(f"⚠️ [VALIDATION] open_channel_id should be negative: {global_open_channel_id}")
            # Add negative sign to fix misconfiguration
            global_open_channel_id = f"-{global_open_channel_id}"
            print(f"✅ [VALIDATION] Corrected to: {global_open_channel_id}")

        order_id = f"PGP-{user_id}|{global_open_channel_id}"

        print(f"📋 [ORDER] Created order_id: {order_id}")
        print(f"   User ID: {user_id}")
        print(f"   Open Channel ID: {global_open_channel_id}")

        # Build success URL pointing to static landing page
        # The landing page will poll payment status via API
        # OLD: Used signed webhook URL with token (deprecated)
        # NEW: Static landing page with order_id parameter
        landing_page_base_url = "https://storage.googleapis.com/paygateprime-static/payment-processing.html"
        secure_success_url = f"{landing_page_base_url}?order_id={order_id}"

        print(f"🔗 [SUCCESS_URL] Using static landing page")
        print(f"   URL: {secure_success_url}")
        
        # Use the new payment flow method with channel info
        await self.start_payment_flow(
            update=update,
            context=context,
            sub_value=global_sub_value,
            open_channel_id=global_open_channel_id,
            secure_success_url=secure_success_url,
            closed_channel_title=closed_channel_title,
            closed_channel_description=closed_channel_description,
            sub_time=global_sub_time,
            order_id=order_id  # Pass order_id to avoid duplicate creation
        )