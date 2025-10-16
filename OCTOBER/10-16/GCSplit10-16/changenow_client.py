#!/usr/bin/env python
"""
ChangeNow API Client for TPS10-16 Payment Splitting Service.
Handles all interactions with the ChangeNow cryptocurrency exchange API.
"""
import requests
import time
from typing import Dict, Any, Optional, List
from telegram import Bot
from telegram.error import TelegramError

class ChangeNowClient:
    """
    Client for interacting with ChangeNow API v1.
    Handles authentication, rate limiting, and error handling.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize ChangeNow client.

        Args:
            api_key: ChangeNow API key for authentication
        """
        self.api_key = api_key
        self.base_url_v1 = "https://api.changenow.io/v1"
        self.base_url_v2 = "https://api.changenow.io/v2"
        self.session = requests.Session()

        # Set default headers
        self.session.headers.update({
            'x-changenow-api-key': self.api_key,
            'Content-Type': 'application/json'
        })

        print(f"🔗 [CHANGENOW_CLIENT] Initialized with API key: {api_key[:8]}...")
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                     params: Optional[Dict] = None, use_v2: bool = False) -> Optional[Dict]:
        """
        Make authenticated request to ChangeNow API with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: JSON data for POST requests
            params: URL parameters for GET requests
            use_v2: Use v2 API endpoint if True, v1 otherwise

        Returns:
            API response data or None if failed
        """
        base_url = self.base_url_v2 if use_v2 else self.base_url_v1
        url = f"{base_url}{endpoint}"
        
        try:
            print(f"🌐 [CHANGENOW_API] {method} {endpoint}")
            
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=30
            )
            
            print(f"📊 [CHANGENOW_API] Response status: {response.status_code}")
            
            # Handle rate limiting
            if response.status_code == 429:
                print(f"⏰ [CHANGENOW_API] Rate limited, waiting 60 seconds...")
                time.sleep(60)
                return self._make_request(method, endpoint, data, params)
            
            # Handle successful responses
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"✅ [CHANGENOW_API] Request successful")
                    return result
                except ValueError as e:
                    print(f"❌ [CHANGENOW_API] JSON decode error: {e}")
                    return None
            
            # Handle API errors
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', 'Unknown error')
                    print(f"❌ [CHANGENOW_API] API error {response.status_code}: {error_message}")
                except ValueError:
                    print(f"❌ [CHANGENOW_API] HTTP error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"❌ [CHANGENOW_API] Request timeout")
            return None
        except requests.exceptions.ConnectionError:
            print(f"❌ [CHANGENOW_API] Connection error")
            return None
        except Exception as e:
            print(f"❌ [CHANGENOW_API] Unexpected error: {e}")
            return None
    
    def get_available_pairs(self) -> Optional[List[str]]:
        """
        Get list of available currency pairs from ChangeNow.
        
        Returns:
            List of available pairs or None if failed
        """
        try:
            print(f"🔍 [CHANGENOW_PAIRS] Fetching available currency pairs")
            
            # Use market-info endpoint for available pairs
            response = self._make_request('GET', '/market-info/available-pairs/')
            
            if response and isinstance(response, list):
                print(f"📋 [CHANGENOW_PAIRS] Found {len(response)} available pairs")
                return response
            else:
                print(f"❌ [CHANGENOW_PAIRS] Invalid response format")
                return None
                
        except Exception as e:
            print(f"❌ [CHANGENOW_PAIRS] Error fetching pairs: {e}")
            return None
    
    def get_exchange_limits(self, from_currency: str, to_currency: str) -> Optional[Dict]:
        """
        Get minimum exchange amount for a currency pair.
        
        Args:
            from_currency: Source currency
            to_currency: Target currency
            
        Returns:
            Limits information or None if failed
        """
        try:
            print(f"💰 [CHANGENOW_LIMITS] Getting limits for {from_currency.upper()} → {to_currency.upper()}")
            
            # Get minimum amount
            min_response = self._make_request(
                'GET', 
                f'/min-amount/{from_currency.lower()}_{to_currency.lower()}'
            )
            
            if min_response:
                min_amount = min_response.get('minAmount', 0)
                print(f"📊 [CHANGENOW_LIMITS] Minimum amount: {min_amount} {from_currency.upper()}")
                
                # For now, we'll use a reasonable max limit since ChangeNow doesn't always provide this
                # In production, you might want to call a separate endpoint for max limits
                return {
                    'minAmount': float(min_amount),
                    'maxAmount': 1000.0,  # Conservative max limit
                    'currency': from_currency.upper()
                }
            else:
                print(f"❌ [CHANGENOW_LIMITS] Failed to get limits")
                return None
                
        except Exception as e:
            print(f"❌ [CHANGENOW_LIMITS] Error getting limits: {e}")
            return None
    
    def get_estimated_exchange_amount(self, amount: float, from_currency: str, 
                                    to_currency: str) -> Optional[Dict]:
        """
        Get estimated exchange amount for a transaction.
        
        Args:
            amount: Amount to exchange
            from_currency: Source currency
            to_currency: Target currency
            
        Returns:
            Estimated exchange data or None if failed
        """
        try:
            print(f"📈 [CHANGENOW_ESTIMATE] Getting estimate for {amount} {from_currency.upper()}")
            
            response = self._make_request(
                'GET', 
                f'/exchange-amount/{amount}/{from_currency.lower()}_{to_currency.lower()}'
            )
            
            if response:
                estimated_amount = response.get('toAmount', 0)
                print(f"📊 [CHANGENOW_ESTIMATE] Estimated receive: {estimated_amount} {to_currency.upper()}")
                return response
            else:
                print(f"❌ [CHANGENOW_ESTIMATE] Failed to get estimate")
                return None
                
        except Exception as e:
            print(f"❌ [CHANGENOW_ESTIMATE] Error getting estimate: {e}")
            return None
    
    def create_fixed_rate_transaction(self, from_currency: str, to_currency: str,
                                    from_amount: float, address: str,
                                    user_id: str = None, rate_id: str = None) -> Optional[Dict]:
        """
        Create a transaction with ChangeNow API v2.

        Args:
            from_currency: Source currency
            to_currency: Target currency
            from_amount: Amount to exchange
            address: Recipient wallet address
            user_id: Optional user ID for tracking
            rate_id: Optional rate ID for guaranteed pricing

        Returns:
            Transaction data or None if failed
        """
        try:
            print(f"🚀 [CHANGENOW_TRANSACTION] Creating transaction via API v2")
            print(f"💱 [CHANGENOW_TRANSACTION] {from_amount} {from_currency.upper()} → {to_currency.upper()}")

            # Prepare transaction data for v2 API
            transaction_data = {
                "fromCurrency": from_currency.lower(),
                "toCurrency": to_currency.lower(),
                "fromNetwork": from_currency.lower(),
                "toNetwork": to_currency.lower(),
                "fromAmount": str(from_amount),
                "toAmount": "",
                "address": address,
                "extraId": "",
                "refundAddress": "",
                "refundExtraId": "",
                "userId": user_id if user_id else "",
                "payload": "",
                "contactEmail": "",
                "source": "",
                "flow": "standard",
                "type": "direct",
                "rateId": rate_id if rate_id else ""
            }

            print(f"📦 [CHANGENOW_TRANSACTION] Payload: {transaction_data}")

            # Create the transaction using v2 API
            response = self._make_request('POST', '/exchange', data=transaction_data, use_v2=True)

            if response:
                transaction_id = response.get('id', 'Unknown')
                payin_address = response.get('payinAddress', 'Unknown')
                to_amount = response.get('toAmount', 'Unknown')
                from_curr = response.get('fromCurrency', from_currency).upper()
                to_curr = response.get('toCurrency', to_currency).upper()

                print(f"✅ [CHANGENOW_TRANSACTION] Transaction created successfully")
                print(f"🆔 [CHANGENOW_TRANSACTION] ID: {transaction_id}")
                print(f"🏦 [CHANGENOW_TRANSACTION] Deposit address: {payin_address}")
                print(f"💰 [CHANGENOW_TRANSACTION] Will receive: {to_amount} {to_curr}")

                return response
            else:
                print(f"❌ [CHANGENOW_TRANSACTION] Failed to create transaction")
                return None

        except Exception as e:
            print(f"❌ [CHANGENOW_TRANSACTION] Error creating transaction: {e}")
            return None
    
    def get_transaction_status(self, transaction_id: str) -> Optional[Dict]:
        """
        Get status of an existing transaction.
        
        Args:
            transaction_id: ChangeNow transaction ID
            
        Returns:
            Transaction status data or None if failed
        """
        try:
            print(f"🔍 [CHANGENOW_STATUS] Checking transaction {transaction_id}")
            
            response = self._make_request('GET', f'/transactions/{transaction_id}')
            
            if response:
                status = response.get('status', 'Unknown')
                print(f"📊 [CHANGENOW_STATUS] Transaction status: {status}")
                return response
            else:
                print(f"❌ [CHANGENOW_STATUS] Failed to get transaction status")
                return None
                
        except Exception as e:
            print(f"❌ [CHANGENOW_STATUS] Error getting transaction status: {e}")
            return None
    
    def validate_address(self, currency: str, address: str) -> bool:
        """
        Validate a wallet address for a specific currency.

        Args:
            currency: Currency symbol
            address: Wallet address to validate

        Returns:
            True if address is valid, False otherwise
        """
        try:
            print(f"🔍 [CHANGENOW_VALIDATE] Validating {currency.upper()} address")

            response = self._make_request(
                'GET',
                f'/validate/address',
                params={
                    'currency': currency.lower(),
                    'address': address
                }
            )

            if response:
                is_valid = response.get('result', False)
                print(f"✅ [CHANGENOW_VALIDATE] Address validation: {is_valid}")
                return is_valid
            else:
                print(f"❌ [CHANGENOW_VALIDATE] Failed to validate address")
                return False

        except Exception as e:
            print(f"❌ [CHANGENOW_VALIDATE] Error validating address: {e}")
            return False

    async def send_telegram_notification(self, bot_token: str, transaction_data: Dict[str, Any]) -> bool:
        """
        Send transaction details to @PayGatePrime_bot on Telegram.

        Args:
            bot_token: Telegram bot token
            transaction_data: Transaction response from ChangeNow

        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            # Extract required fields
            transaction_id = transaction_data.get('id', 'N/A')
            from_currency = transaction_data.get('fromCurrency', 'N/A').upper()
            to_currency = transaction_data.get('toCurrency', 'N/A').upper()
            to_amount = transaction_data.get('toAmount', 'N/A')
            payin_address = transaction_data.get('payinAddress', 'N/A')

            # Create formatted message
            message = (
                f"🎯 <b>ChangeNow Transaction Created</b>\n\n"
                f"🆔 <b>Transaction ID:</b> <code>{transaction_id}</code>\n"
                f"💱 <b>From Currency:</b> {from_currency}\n"
                f"💰 <b>To Currency:</b> {to_currency}\n"
                f"📊 <b>Amount to Receive:</b> {to_amount} {to_currency}\n"
                f"🏦 <b>Deposit Address:</b>\n<code>{payin_address}</code>"
            )

            # Initialize bot and send message
            bot = Bot(token=bot_token)

            # Send to @PayGatePrime_bot (you need to get the chat_id)
            # For now, we'll use a method to get updates or you can hardcode the chat_id
            # This is a placeholder - you'll need to provide the actual chat_id or username
            chat_id = "@PayGatePrime_bot"

            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='HTML'
            )

            print(f"✅ [TELEGRAM] Successfully sent notification to @PayGatePrime_bot")
            print(f"📝 [TELEGRAM] Transaction ID: {transaction_id}")
            return True

        except TelegramError as e:
            print(f"❌ [TELEGRAM] Telegram API error: {e}")
            return False
        except Exception as e:
            print(f"❌ [TELEGRAM] Error sending Telegram notification: {e}")
            return False