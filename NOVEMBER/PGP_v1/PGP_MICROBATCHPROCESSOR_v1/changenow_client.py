#!/usr/bin/env python
"""
ChangeNow API Client with Infinite Retry Logic for PGP_SPLIT3_v1.
Handles ETH→ClientCurrency fixed-rate transaction creation with automatic retry on failures.
"""
import requests
import time
from typing import Dict, Any, Optional


class ChangeNowClient:
    """
    Client for interacting with ChangeNow API v2 with built-in retry logic.
    Creates fixed-rate transactions with infinite retry on failures.
    """

    def __init__(self, api_key: str):
        """
        Initialize ChangeNow client.

        Args:
            api_key: ChangeNow API key for authentication
        """
        self.api_key = api_key
        self.base_url_v2 = "https://api.changenow.io/v2"
        self.session = requests.Session()

        # Set default headers
        self.session.headers.update({
            'x-changenow-api-key': self.api_key,
            'Content-Type': 'application/json'
        })

        print(f"🔗 [CHANGENOW_CLIENT] Initialized with API key: {api_key[:8]}...")

    def create_fixed_rate_transaction_with_retry(
        self,
        from_currency: str,
        to_currency: str,
        from_amount: float,
        address: str,
        from_network: str = None,
        to_network: str = None,
        user_id: str = None,
        rate_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a fixed-rate transaction with ChangeNow API v2 with INFINITE RETRY.

        This method will retry indefinitely (up to Cloud Tasks timeout of 24 hours)
        on ANY error condition including:
        - HTTP 429 (Rate Limit)
        - HTTP 5xx (Server Error)
        - Timeout
        - Connection Error

        Backoff: Fixed 60 seconds between retries (no exponential backoff)

        Args:
            from_currency: Source currency (e.g., "eth")
            to_currency: Target currency (e.g., "link", "btc")
            from_amount: Amount to exchange
            address: Recipient wallet address
            from_network: Source network (defaults to from_currency if not provided)
            to_network: Target network (defaults to to_currency if not provided)
            user_id: Optional user ID for tracking
            rate_id: Optional rate ID for guaranteed pricing

        Returns:
            Transaction data (will eventually succeed or timeout after 24h)
        """
        attempt = 0

        while True:  # Infinite retry loop
            attempt += 1
            print(f"🔄 [CHANGENOW_RETRY] Attempt #{attempt}")
            print(f"🚀 [CHANGENOW_TRANSACTION] Creating: {from_amount} {from_currency.upper()} → {to_currency.upper()}")

            try:
                # Use provided networks or fall back to currency defaults
                actual_from_network = from_network.lower() if from_network else from_currency.lower()
                actual_to_network = to_network.lower() if to_network else to_currency.lower()

                print(f"🌐 [CHANGENOW_TRANSACTION] Networks: {actual_from_network} → {actual_to_network}")

                # Build transaction data
                transaction_data = {
                    "fromCurrency": from_currency.lower(),
                    "toCurrency": to_currency.lower(),
                    "fromNetwork": actual_from_network,
                    "toNetwork": actual_to_network,
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

                # Make API request
                url = f"{self.base_url_v2}/exchange"
                response = self.session.post(url, json=transaction_data, timeout=30)

                print(f"📊 [CHANGENOW_TRANSACTION] Response status: {response.status_code}")

                # Handle rate limiting (429) - retry after 60s
                if response.status_code == 429:
                    print(f"⏰ [CHANGENOW_RETRY] Rate limited (429), waiting 60 seconds...")
                    time.sleep(60)
                    continue  # Retry

                # Handle server errors (5xx) - retry after 60s
                if 500 <= response.status_code < 600:
                    print(f"❌ [CHANGENOW_RETRY] Server error ({response.status_code}), waiting 60 seconds...")
                    time.sleep(60)
                    continue  # Retry

                # Handle successful response (200)
                if response.status_code == 200:
                    try:
                        result = response.json()

                        transaction_id = result.get('id', 'Unknown')
                        payin_address = result.get('payinAddress', 'Unknown')
                        to_amount = result.get('toAmount', 'Unknown')
                        from_curr = result.get('fromCurrency', from_currency).upper()
                        to_curr = result.get('toCurrency', to_currency).upper()

                        print(f"✅ [CHANGENOW_TRANSACTION] Success after {attempt} attempt(s)")
                        print(f"🆔 [CHANGENOW_TRANSACTION] Transaction ID: {transaction_id}")
                        print(f"🏦 [CHANGENOW_TRANSACTION] Deposit address: {payin_address}")
                        print(f"💰 [CHANGENOW_TRANSACTION] Will receive: {to_amount} {to_curr}")

                        return result

                    except ValueError as json_error:
                        print(f"❌ [CHANGENOW_RETRY] JSON decode error: {json_error}, waiting 60 seconds...")
                        time.sleep(60)
                        continue  # Retry

                # Handle other HTTP errors (4xx except 429) - retry after 60s
                else:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('message', 'Unknown error')
                        print(f"❌ [CHANGENOW_RETRY] API error {response.status_code}: {error_message}")
                    except ValueError:
                        print(f"❌ [CHANGENOW_RETRY] HTTP error {response.status_code}: {response.text}")

                    print(f"⏰ [CHANGENOW_RETRY] Waiting 60 seconds before retry...")
                    time.sleep(60)
                    continue  # Retry

            except requests.exceptions.Timeout:
                print(f"❌ [CHANGENOW_RETRY] Request timeout, waiting 60 seconds...")
                time.sleep(60)
                continue  # Retry

            except requests.exceptions.ConnectionError:
                print(f"❌ [CHANGENOW_RETRY] Connection error, waiting 60 seconds...")
                time.sleep(60)
                continue  # Retry

            except Exception as e:
                print(f"❌ [CHANGENOW_RETRY] Unexpected error: {e}, waiting 60 seconds...")
                time.sleep(60)
                continue  # Retry

        # This line should never be reached due to infinite loop
        # Cloud Tasks will terminate the task after 24 hours (max-retry-duration)

    def get_estimated_amount_v2_with_retry(
        self,
        from_currency: str,
        to_currency: str,
        from_network: str,
        to_network: str,
        from_amount: str,
        flow: str = "standard",
        type_: str = "direct"
    ) -> Optional[Dict[str, Any]]:
        """
        Get estimated exchange amount using ChangeNow API v2 with INFINITE RETRY.

        This method will retry indefinitely (up to Cloud Tasks timeout of 24 hours)
        on ANY error condition including:
        - HTTP 429 (Rate Limit)
        - HTTP 5xx (Server Error)
        - Timeout
        - Connection Error

        Backoff: Fixed 60 seconds between retries (no exponential backoff)

        Args:
            from_currency: Source currency (e.g., "usdt")
            to_currency: Target currency (e.g., "eth")
            from_network: Source network (e.g., "eth")
            to_network: Target network (e.g., "eth")
            from_amount: Amount to exchange as string
            flow: Exchange flow type (default "standard")
            type_: Exchange type (default "direct")

        Returns:
            Estimate response data (will eventually succeed or timeout after 24h)
        """
        from decimal import Decimal

        attempt = 0

        while True:  # Infinite retry loop
            attempt += 1
            print(f"🔄 [CHANGENOW_RETRY] Attempt #{attempt}")
            print(f"📈 [CHANGENOW_ESTIMATE_V2] Getting estimate: {from_amount} {from_currency.upper()} → {to_currency.upper()}")

            try:
                # Build request parameters
                params = {
                    "fromCurrency": from_currency.lower(),
                    "toCurrency": to_currency.lower(),
                    "fromNetwork": from_network.lower(),
                    "toNetwork": to_network.lower(),
                    "fromAmount": from_amount,
                    "toAmount": "",  # Empty for fromAmount-based estimates
                    "flow": flow,
                    "type": type_
                }

                print(f"📦 [CHANGENOW_ESTIMATE_V2] Request params: {params}")

                # Make API request
                url = f"{self.base_url_v2}/exchange/estimated-amount"
                response = self.session.get(url, params=params, timeout=30)

                print(f"📊 [CHANGENOW_ESTIMATE_V2] Response status: {response.status_code}")

                # Handle rate limiting (429) - retry after 60s
                if response.status_code == 429:
                    print(f"⏰ [CHANGENOW_RETRY] Rate limited (429), waiting 60 seconds...")
                    time.sleep(60)
                    continue  # Retry

                # Handle server errors (5xx) - retry after 60s
                if 500 <= response.status_code < 600:
                    print(f"❌ [CHANGENOW_RETRY] Server error ({response.status_code}), waiting 60 seconds...")
                    time.sleep(60)
                    continue  # Retry

                # Handle successful response (200)
                if response.status_code == 200:
                    try:
                        result = response.json()

                        # ✅ Parse amounts as Decimal to preserve precision
                        to_amount = Decimal(str(result.get('toAmount', 0)))
                        deposit_fee = Decimal(str(result.get('depositFee', 0)))
                        withdrawal_fee = Decimal(str(result.get('withdrawalFee', 0)))

                        print(f"✅ [CHANGENOW_ESTIMATE_V2] Success after {attempt} attempt(s)")
                        print(f"💰 [CHANGENOW_ESTIMATE_V2] Estimated receive: {to_amount} {to_currency.upper()}")
                        print(f"📊 [CHANGENOW_ESTIMATE_V2] Deposit fee: {deposit_fee}")
                        print(f"📊 [CHANGENOW_ESTIMATE_V2] Withdrawal fee: {withdrawal_fee}")

                        # Store Decimal values back in result dict
                        result['toAmount'] = to_amount
                        result['depositFee'] = deposit_fee
                        result['withdrawalFee'] = withdrawal_fee

                        return result

                    except ValueError as json_error:
                        print(f"❌ [CHANGENOW_RETRY] JSON decode error: {json_error}, waiting 60 seconds...")
                        time.sleep(60)
                        continue  # Retry

                # Handle other HTTP errors (4xx except 429) - retry after 60s
                else:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('message', 'Unknown error')
                        print(f"❌ [CHANGENOW_RETRY] API error {response.status_code}: {error_message}")
                    except ValueError:
                        print(f"❌ [CHANGENOW_RETRY] HTTP error {response.status_code}: {response.text}")

                    print(f"⏰ [CHANGENOW_RETRY] Waiting 60 seconds before retry...")
                    time.sleep(60)
                    continue  # Retry

            except requests.exceptions.Timeout:
                print(f"❌ [CHANGENOW_RETRY] Request timeout, waiting 60 seconds...")
                time.sleep(60)
                continue  # Retry

            except requests.exceptions.ConnectionError:
                print(f"❌ [CHANGENOW_RETRY] Connection error, waiting 60 seconds...")
                time.sleep(60)
                continue  # Retry

            except Exception as e:
                print(f"❌ [CHANGENOW_RETRY] Unexpected error: {e}, waiting 60 seconds...")
                time.sleep(60)
                continue  # Retry

        # This line should never be reached due to infinite loop
        # Cloud Tasks will terminate the task after 24 hours (max-retry-duration)
