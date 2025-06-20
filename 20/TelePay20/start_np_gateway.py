#!/usr/bin/env python
import os
import httpx
from typing import Dict, Any, Optional
from google.cloud import secretmanager
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

class PaymentGatewayManager:
    def __init__(self, payment_token: str = None):
        """
        Initialize the PaymentGatewayManager.
        
        Args:
            payment_token: The NowPayments API token. If None, will fetch from secrets
        """
        self.payment_token = payment_token or self.fetch_payment_provider_token()
        self.api_url = "https://api.nowpayments.io/v1/invoice"
    
    def fetch_payment_provider_token(self) -> Optional[str]:
        """Fetch the payment provider token from Google Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_name = os.getenv("PAYMENT_PROVIDER_SECRET_NAME")
            if not secret_name:
                raise ValueError("Environment variable PAYMENT_PROVIDER_SECRET_NAME is not set.")
            secret_path = f"{secret_name}"
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"Error fetching the PAYMENT_PROVIDER_TOKEN: {e}")
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
        
        invoice_payload = {
            "price_amount": amount,
            "price_currency": "USD",
            "order_id": order_id,
            "order_description": "Payment-Test-1",
            "success_url": success_url,
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
                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "data": resp.json()
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
                                secure_success_url: str) -> None:
        """
        Start the complete payment flow for a user.
        
        Args:
            update: The Telegram update object
            context: The bot context
            sub_value: The subscription amount
            open_channel_id: The open channel ID
            secure_success_url: The signed success URL for post-payment redirect
        """
        print(f"[DEBUG] Starting payment flow: amount=${sub_value:.2f}, channel_id={open_channel_id}")
        user_id = self.get_telegram_user_id(update)
        if not user_id:
            chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
            if chat_id:
                await context.bot.send_message(chat_id, "❌ Could not determine user ID.")
            return
        
        # Create unique order ID
        order_id = f"PGP-{user_id}{open_channel_id}"
        
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
            print(f"[DEBUG] Payment gateway created successfully for ${sub_value:.2f}")
            print(f"[DEBUG] Invoice URL: {invoice_url}")
            reply_markup = ReplyKeyboardMarkup.from_button(
                KeyboardButton(
                    text="Open Payment Gateway",
                    web_app=WebAppInfo(url=invoice_url),
                )
            )
            text = (
                f"💳 *Payment Gateway Ready*\n\n"
                f"Amount: ${sub_value:.2f}\n\n"
                "Please click 'Open Payment Gateway' below. "
                "You have 20 minutes to complete the payment."
            )
            await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="Markdown")
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
            print("[DEBUG] Handling donation_default case - using placeholder values")
            closed_channel_id = "donation_default_closed"
            wallet_address = ""
            payout_currency = ""
        else:
            # Get closed channel ID from database
            closed_channel_id = db_manager.fetch_closed_channel_id(global_open_channel_id)
            if not closed_channel_id:
                chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else update.callback_query.message.chat.id
                await context.bot.send_message(chat_id, "❌ Could not find a closed_channel_id for this open_channel_id. Please check your database!")
                return
            
            # Get wallet info from database
            wallet_address, payout_currency = db_manager.fetch_client_wallet_info(global_open_channel_id)
            print(f"[DEBUG] Retrieved wallet info for {global_open_channel_id}: wallet='{wallet_address}', currency='{payout_currency}'")


        if not webhook_manager.signing_key:
            chat_id = update.effective_chat.id if hasattr(update, "effective_chat") else None
            if chat_id:
                await context.bot.send_message(chat_id, "❌ Signing key missing, cannot generate secure URL.")
            return

        # Build secure success URL with wallet info and subscription time
        secure_success_url = webhook_manager.build_signed_success_url(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            client_wallet_address=wallet_address or "",
            client_payout_currency=payout_currency or "",
            subscription_time=global_sub_time
        )
        
        # Use the new payment flow method
        await self.start_payment_flow(
            update=update,
            context=context,
            sub_value=global_sub_value,
            open_channel_id=global_open_channel_id,
            secure_success_url=secure_success_url
        )