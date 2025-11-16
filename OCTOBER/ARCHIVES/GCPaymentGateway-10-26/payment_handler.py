#!/usr/bin/env python
"""
Payment Handler for GCPaymentGateway-10-26
Handles NowPayments API integration and invoice creation
"""

import httpx
import asyncio
from typing import Dict, Any, Optional, Tuple
from urllib.parse import quote
from validators import (
    validate_user_id,
    validate_amount,
    validate_channel_id,
    validate_subscription_time,
    validate_payment_type,
    sanitize_channel_id
)


class PaymentHandler:
    """
    Handles payment invoice creation with NowPayments API.
    """

    def __init__(self, config: Dict[str, Any], db_manager):
        """
        Initialize the PaymentHandler.

        Args:
            config: Configuration dictionary with API credentials
            db_manager: DatabaseManager instance for channel lookups
        """
        self.payment_token = config.get("payment_provider_token")
        self.ipn_callback_url = config.get("ipn_callback_url")
        self.api_url = config.get("nowpayments_api_url")
        self.landing_page_base_url = config.get("landing_page_base_url")
        self.db_manager = db_manager

        if not self.payment_token:
            raise ValueError("Payment provider token is required")

        if not self.ipn_callback_url:
            print("⚠️ [PAYMENT] IPN callback URL not configured - payment_id capture may not work")

        print("✅ [PAYMENT] Payment handler initialized with NowPayments API")

    def validate_request(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate incoming invoice creation request.

        Args:
            data: Request data dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        required_fields = ["user_id", "amount", "open_channel_id", "subscription_time_days", "payment_type"]
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"

        # Validate user_id
        if not validate_user_id(data["user_id"]):
            return False, "Invalid user_id (must be positive integer)"

        # Validate amount
        if not validate_amount(data["amount"]):
            return False, "Invalid amount (must be between $1.00 and $9999.99)"

        # Validate channel_id
        if not validate_channel_id(data["open_channel_id"]):
            return False, "Invalid channel ID format"

        # Validate subscription time
        if not validate_subscription_time(data["subscription_time_days"]):
            return False, "Invalid subscription time (must be between 1 and 999 days)"

        # Validate payment type
        if not validate_payment_type(data["payment_type"]):
            return False, "Invalid payment type (must be 'subscription' or 'donation')"

        print("✅ [PAYMENT] Request validation passed")
        return True, None

    def build_order_id(self, user_id: int, open_channel_id: str) -> str:
        """
        Build unique order ID in PayGatePrime format.

        Format: PGP-{user_id}|{open_channel_id}
        Example: PGP-6271402111|-1003268562225

        Args:
            user_id: Telegram user ID
            open_channel_id: Open channel ID (sanitized)

        Returns:
            Order ID string
        """
        # Sanitize channel ID (ensure negative for Telegram channels)
        sanitized_channel_id = sanitize_channel_id(open_channel_id)

        order_id = f"PGP-{user_id}|{sanitized_channel_id}"

        print(f"📋 [ORDER] Created order_id: {order_id}")
        print(f"   👤 User ID: {user_id}")
        print(f"   📺 Open Channel ID: {sanitized_channel_id}")

        return order_id

    def build_success_url(self, order_id: str) -> str:
        """
        Build success URL pointing to static landing page.

        Args:
            order_id: Order ID to include in URL

        Returns:
            Success URL string
        """
        # URL-encode order_id to handle special characters (| and -)
        encoded_order_id = quote(order_id, safe='')
        success_url = f"{self.landing_page_base_url}?order_id={encoded_order_id}"

        print(f"🔗 [SUCCESS_URL] Built success URL")
        print(f"   📝 URL: {success_url}")

        return success_url

    def create_invoice_payload(self, data: Dict[str, Any], order_id: str, success_url: str) -> Dict[str, Any]:
        """
        Create NowPayments invoice payload.

        Args:
            data: Request data
            order_id: Generated order ID
            success_url: Success redirect URL

        Returns:
            Invoice payload dictionary
        """
        payload = {
            "price_amount": float(data["amount"]),
            "price_currency": "USD",
            "order_id": order_id,
            "order_description": "Payment-Test-1",
            "success_url": success_url,
            "ipn_callback_url": self.ipn_callback_url,
            "is_fixed_rate": False,
            "is_fee_paid_by_user": False
        }

        print(f"📋 [INVOICE] Created invoice payload:")
        print(f"   💵 Amount: ${payload['price_amount']}")
        print(f"   📄 Order ID: {payload['order_id']}")
        print(f"   🔔 IPN Callback: {'Configured' if self.ipn_callback_url else 'Not configured'}")

        return payload

    async def call_nowpayments_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API call to NowPayments to create invoice.

        Args:
            payload: Invoice payload dictionary

        Returns:
            API response dictionary
        """
        headers = {
            "x-api-key": self.payment_token,
            "Content-Type": "application/json",
        }

        try:
            print(f"🌐 [API] Calling NowPayments API: {self.api_url}")

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                )

                if resp.status_code == 200:
                    response_data = resp.json()
                    invoice_id = response_data.get('id')
                    invoice_url = response_data.get('invoice_url')

                    print(f"✅ [API] Invoice created successfully")
                    print(f"   🆔 Invoice ID: {invoice_id}")
                    print(f"   🔗 Invoice URL: {invoice_url}")

                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "data": response_data
                    }
                else:
                    print(f"❌ [API] NowPayments error: {resp.status_code}")
                    print(f"   📄 Response: {resp.text}")

                    return {
                        "success": False,
                        "status_code": resp.status_code,
                        "error": resp.text
                    }

        except httpx.TimeoutException:
            print(f"❌ [API] Request timeout (30s)")
            return {
                "success": False,
                "error": "Request timeout - NowPayments API did not respond"
            }
        except Exception as e:
            print(f"❌ [API] Request failed: {e}")
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }

    def create_invoice(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method to create a payment invoice.
        This is the entry point called by the Flask route.

        Args:
            request_data: Request data from Flask route

        Returns:
            Response dictionary with invoice details or error
        """
        print(f"💳 [PAYMENT] Creating invoice for user {request_data.get('user_id')}")

        # 1. Validate request
        is_valid, error_message = self.validate_request(request_data)
        if not is_valid:
            print(f"❌ [PAYMENT] Validation failed: {error_message}")
            return {
                "success": False,
                "error": error_message,
                "status_code": 400
            }

        # 2. Extract and sanitize data
        user_id = request_data["user_id"]
        amount = request_data["amount"]
        open_channel_id = request_data["open_channel_id"]
        subscription_time_days = request_data["subscription_time_days"]
        payment_type = request_data["payment_type"]

        # 3. Check if order_id provided (optional)
        if "order_id" in request_data and request_data["order_id"]:
            order_id = request_data["order_id"]
            print(f"📋 [ORDER] Using provided order_id: {order_id}")
        else:
            # Generate order_id
            order_id = self.build_order_id(user_id, open_channel_id)

        # 4. Validate channel exists in database (unless donation_default)
        if open_channel_id != "donation_default":
            sanitized_channel_id = sanitize_channel_id(open_channel_id)
            if not self.db_manager.channel_exists(sanitized_channel_id):
                print(f"❌ [PAYMENT] Channel {sanitized_channel_id} does not exist in database")
                return {
                    "success": False,
                    "error": f"Channel {sanitized_channel_id} not found",
                    "status_code": 404
                }

            # Fetch channel details for logging
            channel_details = self.db_manager.fetch_channel_details(sanitized_channel_id)
            if channel_details:
                print(f"🏷️ [PAYMENT] Channel: {channel_details.get('closed_channel_title')}")

        # 5. Build success URL
        success_url = self.build_success_url(order_id)

        # 6. Create invoice payload
        payload = self.create_invoice_payload(request_data, order_id, success_url)

        # 7. Call NowPayments API (async)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        api_response = loop.run_until_complete(self.call_nowpayments_api(payload))
        loop.close()

        # 8. Return response
        if api_response.get("success"):
            return {
                "success": True,
                "invoice_id": api_response["data"].get("id"),
                "invoice_url": api_response["data"].get("invoice_url"),
                "order_id": order_id,
                "status_code": 200
            }
        else:
            return {
                "success": False,
                "error": api_response.get("error", "Unknown error"),
                "status_code": api_response.get("status_code", 500)
            }
