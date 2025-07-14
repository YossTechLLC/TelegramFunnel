#!/usr/bin/env python
"""
ChangeNOW API Manager for TelegramFunnel
Handles cryptocurrency swaps via ChangeNOW API v2
"""
import os
import httpx
import asyncio
import time
from typing import Dict, Any, Optional, Tuple
from google.cloud import secretmanager


class ChangeNOWManager:
    def __init__(self, api_key: str = None):
        """
        Initialize the ChangeNOW API Manager.
        
        Args:
            api_key: ChangeNOW API key. If None, will fetch from Secret Manager
        """
        self.api_key = api_key or self.fetch_changenow_api_key()
        self.base_url = "https://api.changenow.io"
        self.timeout = 30
        
        if not self.api_key:
            raise ValueError("ChangeNOW API key is required")
    
    def fetch_changenow_api_key(self) -> Optional[str]:
        """Fetch ChangeNOW API key from Google Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv("CHANGENOW_API_KEY")
            if not secret_path:
                raise ValueError("Environment variable CHANGENOW_API_KEY is not set")
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"❌ [ERROR] Failed to fetch ChangeNOW API key: {e}")
            return None
    
    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for ChangeNOW API requests."""
        return {
            "x-changenow-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def validate_address(self, currency: str, address: str) -> Tuple[bool, str]:
        """
        Validate a cryptocurrency address format.
        
        Args:
            currency: Currency ticker (e.g., 'usdt', 'trx')
            address: Address to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        print(f"🔍 [DEBUG] ChangeNOW API: Starting address validation")
        print(f"📋 [DEBUG] Request params: currency='{currency}', address='{address}'")
        
        try:
            params = {
                "currency": currency.lower(),
                "address": address
            }
            
            print(f"🌐 [DEBUG] Making GET request to: {self.base_url}/v2/validate/address")
            print(f"📤 [DEBUG] Request headers: {self.get_headers()}")
            print(f"📤 [DEBUG] Request params: {params}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/v2/validate/address",
                    headers=self.get_headers(),
                    params=params
                )
                
                print(f"📥 [DEBUG] Response status: {response.status_code}")
                print(f"📥 [DEBUG] Response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"📥 [DEBUG] Response body: {data}")
                        
                        is_valid = data.get("result", False)
                        message = "Valid address" if is_valid else "Invalid address format"
                        
                        if is_valid:
                            print(f"✅ [SUCCESS] Address validation passed for {currency.upper()}: {address}")
                        else:
                            print(f"❌ [VALIDATION] Address validation failed for {currency.upper()}: {address}")
                            
                        return is_valid, message
                        
                    except Exception as json_error:
                        error_msg = f"Failed to parse JSON response: {str(json_error)}"
                        print(f"❌ [ERROR] JSON parsing error: {error_msg}")
                        print(f"📥 [DEBUG] Raw response text: {response.text}")
                        return False, error_msg
                        
                else:
                    error_msg = f"HTTP {response.status_code} - {response.text}"
                    print(f"❌ [ERROR] Address validation API error: {error_msg}")
                    
                    # Log specific error codes
                    if response.status_code == 400:
                        print(f"⚠️ [WARNING] Bad request - check currency ticker and address format")
                    elif response.status_code == 401:
                        print(f"🔑 [ERROR] Unauthorized - check ChangeNOW API key")
                    elif response.status_code == 403:
                        print(f"🚫 [ERROR] Forbidden - API key may lack permissions")
                    elif response.status_code == 429:
                        print(f"⏰ [ERROR] Rate limit exceeded - too many API requests")
                    elif response.status_code >= 500:
                        print(f"🔧 [ERROR] ChangeNOW server error - service may be down")
                    
                    return False, error_msg
                    
        except httpx.TimeoutException:
            error_msg = f"Request timeout after {self.timeout} seconds"
            print(f"⏰ [ERROR] ChangeNOW API timeout: {error_msg}")
            return False, error_msg
        except httpx.ConnectError:
            error_msg = "Connection failed - check internet connectivity"
            print(f"🔌 [ERROR] ChangeNOW API connection error: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ [ERROR] Address validation exception: {error_msg}")
            print(f"🔍 [DEBUG] Exception type: {type(e).__name__}")
            return False, error_msg
    
    async def estimate_exchange(self, from_currency: str, to_currency: str, 
                               from_amount: float) -> Dict[str, Any]:
        """
        Get exchange rate estimation.
        
        Args:
            from_currency: Source currency ticker (e.g., 'eth')
            to_currency: Target currency ticker (e.g., 'usdt')
            from_amount: Amount to exchange
            
        Returns:
            Dictionary with estimation data or error info
        """
        print(f"📊 [DEBUG] ChangeNOW API: Starting exchange estimation")
        print(f"💱 [DEBUG] Exchange pair: {from_amount} {from_currency.upper()} → {to_currency.upper()}")
        
        try:
            params = {
                "fromCurrency": from_currency.lower(),
                "toCurrency": to_currency.lower(),
                "fromAmount": str(from_amount),
                "type": "direct"
            }
            
            print(f"🌐 [DEBUG] Making GET request to: {self.base_url}/v2/exchange/estimated-amount")
            print(f"📤 [DEBUG] Request headers: {self.get_headers()}")
            print(f"📤 [DEBUG] Request params: {params}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/v2/exchange/estimated-amount",
                    headers=self.get_headers(),
                    params=params
                )
                
                print(f"📥 [DEBUG] Response status: {response.status_code}")
                print(f"📥 [DEBUG] Response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"📥 [DEBUG] Response body: {data}")
                        
                        estimated_amount = data.get('estimatedAmount', 'unknown')
                        min_amount = data.get('minAmount', 'unknown')
                        max_amount = data.get('maxAmount', 'unknown')
                        
                        print(f"✅ [SUCCESS] Exchange estimation completed")
                        print(f"📈 [RESULT] {from_amount} {from_currency.upper()} → {estimated_amount} {to_currency.upper()}")
                        print(f"📊 [LIMITS] Min: {min_amount}, Max: {max_amount}")
                        
                        return {
                            "success": True,
                            "data": data
                        }
                        
                    except Exception as json_error:
                        error_msg = f"Failed to parse JSON response: {str(json_error)}"
                        print(f"❌ [ERROR] JSON parsing error: {error_msg}")
                        print(f"📥 [DEBUG] Raw response text: {response.text}")
                        return {
                            "success": False,
                            "error": error_msg
                        }
                        
                else:
                    error_msg = f"HTTP {response.status_code} - {response.text}"
                    print(f"❌ [ERROR] Exchange estimation API error: {error_msg}")
                    
                    # Log specific error scenarios
                    if response.status_code == 400:
                        print(f"⚠️ [WARNING] Bad request - check currency pair or amount")
                    elif response.status_code == 422:
                        print(f"⚠️ [WARNING] Unprocessable entity - currency pair may not be supported")
                    elif response.status_code == 429:
                        print(f"⏰ [ERROR] Rate limit exceeded")
                    
                    return {
                        "success": False,
                        "error": error_msg
                    }
                    
        except httpx.TimeoutException:
            error_msg = f"Request timeout after {self.timeout} seconds"
            print(f"⏰ [ERROR] ChangeNOW API timeout: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except httpx.ConnectError:
            error_msg = "Connection failed - check internet connectivity"
            print(f"🔌 [ERROR] ChangeNOW API connection error: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ [ERROR] Exchange estimation exception: {error_msg}")
            print(f"🔍 [DEBUG] Exception type: {type(e).__name__}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def create_exchange(self, from_currency: str, to_currency: str, 
                             from_amount: float, recipient_address: str,
                             refund_address: str = "", order_id: str = "") -> Dict[str, Any]:
        """
        Create a new exchange transaction.
        
        Args:
            from_currency: Source currency ticker (e.g., 'eth')
            to_currency: Target currency ticker (e.g., 'usdt')
            from_amount: Amount to exchange
            recipient_address: Address to receive the exchanged currency
            refund_address: Optional refund address
            order_id: Optional order identifier
            
        Returns:
            Dictionary with exchange transaction data or error info
        """
        print(f"🔄 [DEBUG] ChangeNOW API: Starting exchange creation")
        print(f"💱 [DEBUG] Exchange: {from_amount} {from_currency.upper()} → {to_currency.upper()}")
        print(f"📍 [DEBUG] Recipient address: {recipient_address}")
        print(f"🔄 [DEBUG] Refund address: {refund_address or 'Not provided'}")
        print(f"🔖 [DEBUG] Order ID: {order_id or 'Auto-generated'}")
        
        try:
            # Generate user ID if not provided
            user_id = order_id or f"tf30_{int(time.time())}"
            
            payload = {
                "from": from_currency.lower(),
                "to": to_currency.lower(),
                "amount": str(from_amount),
                "address": recipient_address,
                "extraId": "",
                "userId": user_id,
                "contactEmail": "",
                "refundAddress": refund_address,
                "refundExtraId": ""
            }
            
            print(f"🌐 [DEBUG] Making POST request to: {self.base_url}/v2/exchange")
            print(f"📤 [DEBUG] Request headers: {self.get_headers()}")
            print(f"📤 [DEBUG] Request payload: {payload}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v2/exchange",
                    headers=self.get_headers(),
                    json=payload
                )
                
                print(f"📥 [DEBUG] Response status: {response.status_code}")
                print(f"📥 [DEBUG] Response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"📥 [DEBUG] Response body: {data}")
                        
                        # Extract key information
                        payin_address = data.get("payinAddress")
                        exchange_id = data.get("id")
                        expected_amount = data.get("expectedReceiveAmount")
                        deposit_required = data.get("depositRequired", "unknown")
                        deposit_received = data.get("depositReceived", "0")
                        
                        print(f"✅ [SUCCESS] ChangeNOW exchange created successfully")
                        print(f"🔗 [EXCHANGE] Exchange ID: {exchange_id}")
                        print(f"💰 [PAYIN] Send {from_amount} {from_currency.upper()} to: {payin_address}")
                        print(f"📈 [EXPECTED] Will receive: {expected_amount} {to_currency.upper()}")
                        print(f"📊 [DEPOSIT] Required: {deposit_required}, Received: {deposit_received}")
                        
                        # Additional response fields for debugging
                        if "status" in data:
                            print(f"📊 [STATUS] Exchange status: {data['status']}")
                        if "actualReceiveAmount" in data:
                            print(f"💰 [ACTUAL] Actual receive amount: {data['actualReceiveAmount']}")
                        if "validUntil" in data:
                            print(f"⏰ [EXPIRY] Valid until: {data['validUntil']}")
                        
                        return {
                            "success": True,
                            "data": data,
                            "payin_address": payin_address,
                            "exchange_id": exchange_id,
                            "expected_amount": expected_amount
                        }
                        
                    except Exception as json_error:
                        error_msg = f"Failed to parse JSON response: {str(json_error)}"
                        print(f"❌ [ERROR] JSON parsing error: {error_msg}")
                        print(f"📥 [DEBUG] Raw response text: {response.text}")
                        return {
                            "success": False,
                            "error": error_msg
                        }
                        
                else:
                    error_msg = f"HTTP {response.status_code} - {response.text}"
                    print(f"❌ [ERROR] Exchange creation API error: {error_msg}")
                    
                    # Log specific error scenarios with detailed explanations
                    if response.status_code == 400:
                        print(f"⚠️ [BAD_REQUEST] Possible issues:")
                        print(f"   • Invalid currency pair ({from_currency} → {to_currency})")
                        print(f"   • Amount too small/large ({from_amount})")
                        print(f"   • Invalid recipient address format")
                        print(f"   • Missing required fields")
                    elif response.status_code == 422:
                        print(f"⚠️ [UNPROCESSABLE] Possible issues:")
                        print(f"   • Currency pair not supported")
                        print(f"   • Amount outside min/max limits")
                        print(f"   • Recipient address validation failed")
                    elif response.status_code == 401:
                        print(f"🔑 [UNAUTHORIZED] API key issues:")
                        print(f"   • Invalid API key")
                        print(f"   • API key not active")
                        print(f"   • Check CHANGENOW_API_KEY in Secret Manager")
                    elif response.status_code == 403:
                        print(f"🚫 [FORBIDDEN] Permission issues:")
                        print(f"   • API key lacks exchange permissions")
                        print(f"   • Account restrictions")
                    elif response.status_code == 429:
                        print(f"⏰ [RATE_LIMIT] Too many requests:")
                        print(f"   • API rate limit exceeded")
                        print(f"   • Wait before retrying")
                    elif response.status_code >= 500:
                        print(f"🔧 [SERVER_ERROR] ChangeNOW service issues:")
                        print(f"   • Temporary service outage")
                        print(f"   • Exchange service maintenance")
                        print(f"   • Try again later")
                    
                    return {
                        "success": False,
                        "error": error_msg
                    }
                    
        except httpx.TimeoutException:
            error_msg = f"Request timeout after {self.timeout} seconds"
            print(f"⏰ [TIMEOUT] ChangeNOW API timeout: {error_msg}")
            print(f"💡 [SUGGESTION] Try increasing timeout or retry later")
            return {
                "success": False,
                "error": error_msg
            }
        except httpx.ConnectError:
            error_msg = "Connection failed - check internet connectivity"
            print(f"🔌 [CONNECTION] ChangeNOW API connection error: {error_msg}")
            print(f"💡 [SUGGESTION] Check network connectivity and DNS resolution")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ [EXCEPTION] Exchange creation exception: {error_msg}")
            print(f"🔍 [DEBUG] Exception type: {type(e).__name__}")
            print(f"🔍 [DEBUG] Exception args: {e.args}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def get_exchange_status(self, exchange_id: str) -> Dict[str, Any]:
        """
        Get the status of an exchange transaction.
        
        Args:
            exchange_id: The exchange transaction ID
            
        Returns:
            Dictionary with exchange status data or error info
        """
        print(f"📈 [DEBUG] ChangeNOW API: Checking exchange status")
        print(f"🔗 [DEBUG] Exchange ID: {exchange_id}")
        
        try:
            params = {"id": exchange_id}
            
            print(f"🌐 [DEBUG] Making GET request to: {self.base_url}/v2/exchange/by-id")
            print(f"📤 [DEBUG] Request headers: {self.get_headers()}")
            print(f"📤 [DEBUG] Request params: {params}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/v2/exchange/by-id",
                    headers=self.get_headers(),
                    params=params
                )
                
                print(f"📥 [DEBUG] Response status: {response.status_code}")
                print(f"📥 [DEBUG] Response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"📥 [DEBUG] Response body: {data}")
                        
                        # Extract and log key status information
                        status = data.get("status", "unknown")
                        from_currency = data.get("fromCurrency", "unknown")
                        to_currency = data.get("toCurrency", "unknown")
                        from_amount = data.get("fromAmount", "unknown")
                        expected_amount = data.get("expectedReceiveAmount", "unknown")
                        actual_amount = data.get("actualReceiveAmount", "0")
                        deposit_received = data.get("depositReceived", "0")
                        
                        print(f"📊 [STATUS] Exchange status: {status}")
                        print(f"💱 [PAIR] {from_amount} {from_currency.upper()} → {to_currency.upper()}")
                        print(f"📈 [AMOUNTS] Expected: {expected_amount}, Actual: {actual_amount}")
                        print(f"💰 [DEPOSIT] Received: {deposit_received}")
                        
                        # Log status-specific information
                        if status == "new":
                            print(f"🆕 [NEW] Exchange created, waiting for deposit")
                        elif status == "waiting":
                            print(f"⏳ [WAITING] Waiting for deposit confirmation")
                        elif status == "confirming":
                            print(f"🔄 [CONFIRMING] Deposit confirmed, processing exchange")
                        elif status == "exchanging":
                            print(f"🔄 [EXCHANGING] Exchange in progress")
                        elif status == "sending":
                            print(f"📤 [SENDING] Sending to recipient address")
                        elif status == "finished":
                            print(f"✅ [FINISHED] Exchange completed successfully")
                            if "payoutHash" in data:
                                print(f"🔗 [PAYOUT] Transaction hash: {data['payoutHash']}")
                        elif status == "failed":
                            print(f"❌ [FAILED] Exchange failed")
                            if "error" in data:
                                print(f"❌ [ERROR] Failure reason: {data['error']}")
                        elif status == "refunded":
                            print(f"🔄 [REFUNDED] Exchange refunded")
                            if "refundHash" in data:
                                print(f"🔗 [REFUND] Refund hash: {data['refundHash']}")
                        elif status == "expired":
                            print(f"⏰ [EXPIRED] Exchange expired")
                        
                        # Log additional useful fields
                        if "payinAddress" in data:
                            print(f"📍 [PAYIN] Deposit address: {data['payinAddress']}")
                        if "payoutAddress" in data:
                            print(f"📍 [PAYOUT] Recipient address: {data['payoutAddress']}")
                        if "validUntil" in data:
                            print(f"⏰ [EXPIRY] Valid until: {data['validUntil']}")
                        if "updatedAt" in data:
                            print(f"🕐 [UPDATED] Last updated: {data['updatedAt']}")
                        
                        return {
                            "success": True,
                            "data": data,
                            "status": status
                        }
                        
                    except Exception as json_error:
                        error_msg = f"Failed to parse JSON response: {str(json_error)}"
                        print(f"❌ [ERROR] JSON parsing error: {error_msg}")
                        print(f"📥 [DEBUG] Raw response text: {response.text}")
                        return {
                            "success": False,
                            "error": error_msg
                        }
                        
                else:
                    error_msg = f"HTTP {response.status_code} - {response.text}"
                    print(f"❌ [ERROR] Status check API error: {error_msg}")
                    
                    # Log specific error scenarios
                    if response.status_code == 400:
                        print(f"⚠️ [BAD_REQUEST] Invalid exchange ID format")
                    elif response.status_code == 404:
                        print(f"🔍 [NOT_FOUND] Exchange ID not found: {exchange_id}")
                        print(f"💡 [SUGGESTION] Check if exchange ID is correct")
                    elif response.status_code == 401:
                        print(f"🔑 [UNAUTHORIZED] Invalid API key")
                    elif response.status_code == 429:
                        print(f"⏰ [RATE_LIMIT] Too many status check requests")
                    
                    return {
                        "success": False,
                        "error": error_msg
                    }
                    
        except httpx.TimeoutException:
            error_msg = f"Request timeout after {self.timeout} seconds"
            print(f"⏰ [TIMEOUT] ChangeNOW API timeout: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except httpx.ConnectError:
            error_msg = "Connection failed - check internet connectivity"
            print(f"🔌 [CONNECTION] ChangeNOW API connection error: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ [EXCEPTION] Status check exception: {error_msg}")
            print(f"🔍 [DEBUG] Exception type: {type(e).__name__}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def get_supported_currencies(self) -> Dict[str, Any]:
        """
        Get list of supported currencies.
        
        Returns:
            Dictionary with supported currencies or error info
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/v2/exchange/currencies",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"📋 [DEBUG] Retrieved {len(data)} supported currencies")
                    return {
                        "success": True,
                        "data": data
                    }
                else:
                    error_msg = f"API error: {response.status_code} - {response.text}"
                    print(f"❌ [ERROR] Failed to get supported currencies: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg
                    }
                    
        except Exception as e:
            error_msg = f"Currencies request failed: {str(e)}"
            print(f"❌ [ERROR] Currencies request exception: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def is_currency_supported(self, currency: str) -> Tuple[bool, str]:
        """
        Check if a currency is supported by ChangeNOW.
        
        Args:
            currency: Currency ticker to check
            
        Returns:
            Tuple of (is_supported, message)
        """
        print(f"🔍 [DEBUG] ChangeNOW API: Checking currency support")
        print(f"💰 [DEBUG] Currency: {currency.upper()}")
        
        try:
            currencies_result = await self.get_supported_currencies()
            if not currencies_result["success"]:
                error_msg = f"Failed to fetch supported currencies: {currencies_result['error']}"
                print(f"❌ [ERROR] {error_msg}")
                return False, error_msg
            
            currencies = currencies_result["data"]
            currency_lower = currency.lower()
            
            print(f"📋 [DEBUG] Searching through {len(currencies)} supported currencies...")
            
            for curr in currencies:
                ticker = curr.get("ticker", "").lower()
                if ticker == currency_lower:
                    is_available = curr.get("isAvailable", False)
                    network = curr.get("network", "unknown")
                    name = curr.get("name", "unknown")
                    
                    print(f"🔍 [FOUND] Currency found: {name} ({ticker.upper()}) on {network}")
                    print(f"📊 [AVAILABILITY] Available: {is_available}")
                    
                    if "minAmount" in curr:
                        print(f"📊 [LIMITS] Min amount: {curr['minAmount']}")
                    if "maxAmount" in curr:
                        print(f"📊 [LIMITS] Max amount: {curr['maxAmount']}")
                    
                    if is_available:
                        message = f"Currency {currency.upper()} is supported and available"
                        print(f"✅ [SUCCESS] {message}")
                        return True, message
                    else:
                        message = f"Currency {currency.upper()} is supported but temporarily unavailable"
                        print(f"⚠️ [WARNING] {message}")
                        return False, message
            
            message = f"Currency {currency.upper()} is not supported by ChangeNOW"
            print(f"❌ [NOT_FOUND] {message}")
            print(f"💡 [SUGGESTION] Check supported currencies list or verify ticker symbol")
            return False, message
            
        except Exception as e:
            error_msg = f"Currency support check failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            print(f"🔍 [DEBUG] Exception type: {type(e).__name__}")
            return False, error_msg
    
    async def log_api_status_summary(self) -> None:
        """
        Log a comprehensive summary of ChangeNOW API status and capabilities.
        Useful for debugging and monitoring API health.
        """
        print(f"📊 [SUMMARY] ================== ChangeNOW API Status Summary ==================")
        print(f"🌐 [CONFIG] API Base URL: {self.base_url}")
        print(f"⏰ [CONFIG] Request Timeout: {self.timeout}s")
        print(f"🔑 [CONFIG] API Key: {'✅ Set' if self.api_key else '❌ Missing'}")
        
        try:
            # Test basic connectivity with supported currencies endpoint
            print(f"🔍 [TEST] Testing API connectivity...")
            currencies_result = await self.get_supported_currencies()
            
            if currencies_result["success"]:
                currencies = currencies_result["data"]
                print(f"✅ [CONNECTIVITY] API is reachable and responsive")
                print(f"📋 [CURRENCIES] {len(currencies)} currencies supported")
                
                # Count available vs unavailable currencies
                available_count = sum(1 for c in currencies if c.get("isAvailable", False))
                unavailable_count = len(currencies) - available_count
                
                print(f"📊 [AVAILABILITY] Available: {available_count}, Unavailable: {unavailable_count}")
                
                # Show some popular currencies status
                popular_currencies = ["eth", "btc", "usdt", "usdc", "trx", "bnb", "ada", "dot"]
                print(f"🔍 [POPULAR] Popular currencies status:")
                
                for currency in popular_currencies:
                    is_supported, message = await self.is_currency_supported(currency)
                    status_icon = "✅" if is_supported else "❌"
                    print(f"   {status_icon} {currency.upper()}: {'Available' if is_supported else 'Not available'}")
                
            else:
                print(f"❌ [CONNECTIVITY] API connection failed: {currencies_result['error']}")
                print(f"💡 [SUGGESTION] Check API key and network connectivity")
            
        except Exception as e:
            print(f"❌ [ERROR] Status summary failed: {str(e)}")
        
        print(f"📊 [SUMMARY] ================================================================")