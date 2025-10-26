#!/usr/bin/env python
"""
ChangeNow API Client with Infinite Retry Logic for GCSplit2-10-26.
Handles USDT→ETH estimate requests with automatic retry on failures.
"""
import requests
import time
from typing import Dict, Any, Optional


class ChangeNowClient:
    """
    Client for interacting with ChangeNow API v2 with built-in retry logic.
    Retries infinitely (up to Cloud Tasks 24-hour limit) on rate limiting or errors.
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

                        to_amount = result.get('toAmount', 0)
                        deposit_fee = result.get('depositFee', 0)
                        withdrawal_fee = result.get('withdrawalFee', 0)

                        print(f"✅ [CHANGENOW_ESTIMATE_V2] Success after {attempt} attempt(s)")
                        print(f"💰 [CHANGENOW_ESTIMATE_V2] Estimated receive: {to_amount} {to_currency.upper()}")
                        print(f"📊 [CHANGENOW_ESTIMATE_V2] Deposit fee: {deposit_fee}")
                        print(f"📊 [CHANGENOW_ESTIMATE_V2] Withdrawal fee: {withdrawal_fee}")

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
