#!/usr/bin/env python
"""
ChangeNow API Client for PGP_HOSTPAY2_v1 (ChangeNow Status Checker Service).
Handles ChangeNow API status check requests with infinite retry logic.

Implements resilience against:
- Rate limiting (HTTP 429)
- Server errors (5xx)
- Network timeouts
- Connection errors

Retry Strategy:
- Fixed 60-second backoff between retries
- Infinite retries (-1 max_attempts)
- 24-hour max retry duration (handled by Cloud Tasks)
"""
import time
import requests
from typing import Optional
from requests.exceptions import Timeout, ConnectionError


class ChangeNowClient:
    """
    ChangeNow API client with infinite retry logic for status checks.
    """

    def __init__(self, api_key: str):
        """
        Initialize ChangeNow client.

        Args:
            api_key: ChangeNow API key
        """
        self.api_key = api_key
        self.base_url = "https://api.changenow.io/v2"
        self.session = requests.Session()
        self.session.headers.update({"x-changenow-api-key": self.api_key})
        print(f"✅ [CHANGENOW] ChangeNow client initialized")

    def check_transaction_status_with_retry(self, cn_api_id: str) -> Optional[str]:
        """
        Check ChangeNow transaction status with infinite retry.

        Implements infinite retry with 60-second fixed backoff.
        Cloud Tasks will enforce 24-hour max retry duration.

        Args:
            cn_api_id: ChangeNow transaction ID

        Returns:
            Status string ("waiting", "confirming", "exchanging", "sending", "finished",
                          "failed", "refunded", "expired") or None after 24h timeout
        """
        attempt = 0
        start_time = time.time()

        print(f"🔍 [CHANGENOW] Starting status check with infinite retry")
        print(f"🆔 [CHANGENOW] CN API ID: {cn_api_id}")

        while True:
            attempt += 1
            elapsed_time = int(time.time() - start_time)

            print(f"🔄 [CHANGENOW_RETRY] Attempt #{attempt} (elapsed: {elapsed_time}s)")

            try:
                # Build API request
                url = f"{self.base_url}/exchange/by-id"
                params = {"id": cn_api_id}

                print(f"🌐 [CHANGENOW_RETRY] GET {url}?id={cn_api_id}")

                # Send GET request with 30s timeout
                response = self.session.get(url, params=params, timeout=30)

                # Handle rate limiting (HTTP 429)
                if response.status_code == 429:
                    print(f"⏰ [CHANGENOW_RETRY] Rate limited (HTTP 429)")
                    print(f"⏳ [CHANGENOW_RETRY] Waiting 60s before retry...")
                    time.sleep(60)
                    continue

                # Handle server errors (5xx)
                elif 500 <= response.status_code < 600:
                    print(f"❌ [CHANGENOW_RETRY] Server error (HTTP {response.status_code})")
                    print(f"⏳ [CHANGENOW_RETRY] Waiting 60s before retry...")
                    time.sleep(60)
                    continue

                # Handle client errors (4xx) - likely invalid transaction ID
                elif 400 <= response.status_code < 500:
                    print(f"❌ [CHANGENOW_RETRY] Client error (HTTP {response.status_code})")
                    print(f"📄 [CHANGENOW_RETRY] Response: {response.text}")
                    # Don't retry on client errors - transaction ID likely invalid
                    return None

                # Handle success (HTTP 200)
                elif response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "")

                    print(f"✅ [CHANGENOW_RETRY] Status check successful!")
                    print(f"📊 [CHANGENOW_RETRY] Status: {status}")
                    print(f"🕒 [CHANGENOW_RETRY] Total attempts: {attempt}")
                    print(f"⏱️  [CHANGENOW_RETRY] Total time: {elapsed_time}s")

                    return status

                # Handle unexpected status codes
                else:
                    print(f"⚠️ [CHANGENOW_RETRY] Unexpected status code: {response.status_code}")
                    print(f"⏳ [CHANGENOW_RETRY] Waiting 60s before retry...")
                    time.sleep(60)
                    continue

            except Timeout:
                print(f"⏰ [CHANGENOW_RETRY] Request timeout (30s)")
                print(f"⏳ [CHANGENOW_RETRY] Waiting 60s before retry...")
                time.sleep(60)
                continue

            except ConnectionError as ce:
                print(f"❌ [CHANGENOW_RETRY] Connection error: {ce}")
                print(f"⏳ [CHANGENOW_RETRY] Waiting 60s before retry...")
                time.sleep(60)
                continue

            except requests.exceptions.RequestException as re:
                print(f"❌ [CHANGENOW_RETRY] Request exception: {re}")
                print(f"⏳ [CHANGENOW_RETRY] Waiting 60s before retry...")
                time.sleep(60)
                continue

            except Exception as e:
                print(f"❌ [CHANGENOW_RETRY] Unexpected error: {e}")
                print(f"⏳ [CHANGENOW_RETRY] Waiting 60s before retry...")
                time.sleep(60)
                continue

    def check_transaction_status_single_attempt(self, cn_api_id: str) -> Optional[str]:
        """
        Check ChangeNow transaction status (single attempt, no retry).
        Useful for testing or debugging.

        Args:
            cn_api_id: ChangeNow transaction ID

        Returns:
            Status string or None if request failed
        """
        try:
            url = f"{self.base_url}/exchange/by-id"
            params = {"id": cn_api_id}

            print(f"🔍 [CHANGENOW] Checking status for transaction: {cn_api_id}")
            print(f"🌐 [CHANGENOW] Request URL: {url}?id={cn_api_id}")

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "")

                print(f"✅ [CHANGENOW] API response received")
                print(f"📊 [CHANGENOW] Transaction status: {status}")

                return status
            else:
                print(f"❌ [CHANGENOW] API request failed with status {response.status_code}")
                print(f"📄 [CHANGENOW] Response: {response.text}")
                return None

        except Exception as e:
            print(f"❌ [CHANGENOW] Error checking status: {e}")
            return None
