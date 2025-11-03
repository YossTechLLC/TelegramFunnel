#!/usr/bin/env python
"""
ChangeNow API Client for GCHostPay1-10-26.
Handles ChangeNow transaction status queries to get actual USDT received.
"""
import requests
import decimal
from decimal import Decimal
from typing import Dict, Any, Optional


def _safe_decimal(value, default='0') -> Decimal:
    """
    Safely convert value to Decimal, return default if invalid.

    Handles:
    - None values
    - Empty strings
    - 'null'/'none' strings
    - Invalid numeric strings

    Args:
        value: Value to convert (can be None, str, int, float)
        default: Default Decimal string if conversion fails

    Returns:
        Decimal instance
    """
    # Handle None
    if value is None:
        return Decimal(default)

    # Convert to string and strip whitespace
    str_value = str(value).strip()

    # Handle empty or null strings
    if not str_value or str_value.lower() in ('null', 'none', ''):
        return Decimal(default)

    # Attempt conversion
    try:
        return Decimal(str_value)
    except (ValueError, decimal.InvalidOperation):
        print(f"⚠️ [SAFE_DECIMAL] Could not convert '{value}' to Decimal, using default: {default}")
        return Decimal(default)


class ChangeNowClient:
    """
    Client for querying ChangeNow API v2 transaction status.
    Used to get actual USDT received after ETH→USDT swap completes.
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

    def get_transaction_status(self, cn_api_id: str) -> Optional[Dict[str, Any]]:
        """
        Query ChangeNow API for transaction status and actual amounts.

        This is CRITICAL for micro-batch conversion flow to determine:
        - actual_usdt_received: The FINAL USDT amount after conversion (may differ from estimate)

        Args:
            cn_api_id: ChangeNow API transaction ID

        Returns:
            dict with:
                - status: 'finished' | 'waiting' | 'confirming' | 'exchanging' | 'sending' | 'failed'
                - amountFrom: Actual ETH sent (Decimal)
                - amountTo: Actual USDT received (Decimal) ← THIS IS CRITICAL
                - payinHash: Ethereum tx hash
                - payoutHash: USDT tx hash (if applicable)

        Raises:
            requests.exceptions.RequestException: If API request fails
            ValueError: If response parsing fails

        API Endpoint: GET https://api.changenow.io/v2/exchange/by-id?id={cn_api_id}
        """
        try:
            print(f"🔍 [CHANGENOW_STATUS] Querying transaction status for: {cn_api_id}")

            url = f"{self.base_url_v2}/exchange/by-id"
            params = {"id": cn_api_id}

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            status = data.get('status', 'unknown')

            # ✅ DEFENSIVE CONVERSION: Handle null/empty/invalid values
            amount_from = _safe_decimal(data.get('amountFrom'), '0')
            amount_to = _safe_decimal(data.get('amountTo'), '0')

            payin_hash = data.get('payinHash', '')
            payout_hash = data.get('payoutHash', '')

            print(f"✅ [CHANGENOW_STATUS] Transaction status: {status}")
            print(f"💰 [CHANGENOW_STATUS] Amount from: {amount_from}")
            print(f"💰 [CHANGENOW_STATUS] Amount to: {amount_to} (ACTUAL USDT RECEIVED)")
            print(f"🔗 [CHANGENOW_STATUS] Payin hash: {payin_hash}")
            print(f"🔗 [CHANGENOW_STATUS] Payout hash: {payout_hash}")

            # ⚠️ WARN if amounts are zero (not available yet)
            if amount_to == Decimal('0'):
                print(f"⚠️ [CHANGENOW_STATUS] amountTo is zero/null - swap may not be finished yet (status={status})")
            if amount_from == Decimal('0') and status not in ['new', 'waiting']:
                print(f"⚠️ [CHANGENOW_STATUS] amountFrom is zero/null - unexpected for status={status}")

            return {
                'status': status,
                'amountFrom': amount_from,
                'amountTo': amount_to,  # CRITICAL: actual USDT received
                'payinHash': payin_hash,
                'payoutHash': payout_hash
            }

        except requests.exceptions.HTTPError as e:
            print(f"❌ [CHANGENOW_STATUS] HTTP error: {e}")
            print(f"❌ [CHANGENOW_STATUS] Response: {e.response.text if e.response else 'No response'}")
            raise

        except requests.exceptions.RequestException as e:
            print(f"❌ [CHANGENOW_STATUS] Request error: {e}")
            raise

        except (ValueError, KeyError) as e:
            print(f"❌ [CHANGENOW_STATUS] Response parsing error: {e}")
            raise ValueError(f"Failed to parse ChangeNow response: {e}")

        except Exception as e:
            print(f"❌ [CHANGENOW_STATUS] Unexpected error: {e}")
            raise
