#!/usr/bin/env python3
"""
ChangeNow API Precision Test Script
Tests whether ChangeNow returns high-value token amounts as strings or numbers.
This determines if the system can handle tokens like SHIB/PEPE without precision loss.

Usage:
    python3 test_changenow_precision.py

Requirements:
    - requests library (pip install requests)
    - ChangeNow API key (set as environment variable or edit script)
"""
import os
import sys
import json
import requests
from decimal import Decimal
from typing import Dict, Any, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

# ChangeNow API Key - Set via environment variable or edit here
CHANGENOW_API_KEY = os.getenv('CHANGENOW_API_KEY', 'YOUR_API_KEY_HERE')

# Test cases for various high-value tokens
TEST_CASES = [
    {
        "name": "SHIB (Shiba Inu) - 100K per USD",
        "from_currency": "usdt",
        "to_currency": "shib",
        "from_network": "eth",
        "to_network": "eth",
        "from_amount": "100",  # $100 USD
        "expected_quantity": "~10,000,000 SHIB"
    },
    {
        "name": "PEPE - Very High Quantity",
        "from_currency": "usdt",
        "to_currency": "pepe",
        "from_network": "eth",
        "to_network": "eth",
        "from_amount": "100",
        "expected_quantity": "~Billions of PEPE"
    },
    {
        "name": "XRP - Lower Quantity (Control)",
        "from_currency": "usdt",
        "to_currency": "xrp",
        "from_network": "eth",
        "to_network": "xrp",
        "from_amount": "100",
        "expected_quantity": "~100 XRP"
    }
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def test_changenow_response(test_case: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Test ChangeNow API for a specific token pair.

    Args:
        test_case: Dictionary with test parameters

    Returns:
        Analysis results or None if request failed
    """
    print(f"\n{'='*80}")
    print(f"TEST: {test_case['name']}")
    print(f"{'='*80}")

    # Build API request
    url = "https://api.changenow.io/v2/exchange/estimated-amount"
    headers = {"x-changenow-api-key": CHANGENOW_API_KEY}
    params = {
        "fromCurrency": test_case["from_currency"],
        "toCurrency": test_case["to_currency"],
        "fromNetwork": test_case["from_network"],
        "toNetwork": test_case["to_network"],
        "fromAmount": test_case["from_amount"],
        "toAmount": "",
        "flow": "standard",
        "type": "direct"
    }

    print(f"\n📤 Request:")
    print(f"   URL: {url}")
    print(f"   From: {params['fromAmount']} {params['fromCurrency'].upper()}")
    print(f"   To: {params['toCurrency'].upper()}")
    print(f"   Expected: {test_case['expected_quantity']}")

    try:
        # Send request
        response = requests.get(url, headers=headers, params=params, timeout=30)

        print(f"\n📥 Response:")
        print(f"   Status: {response.status_code}")

        if response.status_code != 200:
            print(f"   ❌ Error: {response.text}")
            return None

        # Get raw JSON text
        raw_json = response.text
        print(f"\n📄 Raw JSON Response:")
        print(f"   {raw_json[:500]}{'...' if len(raw_json) > 500 else ''}")

        # Parse JSON
        data = response.json()

        # Extract critical fields
        to_amount = data.get('toAmount')
        deposit_fee = data.get('depositFee')
        withdrawal_fee = data.get('withdrawalFee')

        # Analyze toAmount type
        to_amount_type = type(to_amount).__name__

        print(f"\n🔍 Analysis:")
        print(f"   toAmount value: {to_amount}")
        print(f"   toAmount type: {to_amount_type}")
        print(f"   toAmount repr: {repr(to_amount)}")

        # Check if it's a string or number in raw JSON
        if f'"toAmount":"{to_amount}"' in raw_json or f'"toAmount": "{to_amount}"' in raw_json:
            json_format = "STRING"
        elif f'"toAmount":{to_amount}' in raw_json or f'"toAmount": {to_amount}' in raw_json:
            json_format = "NUMBER"
        else:
            json_format = "UNKNOWN"

        print(f"   JSON format: {json_format}")

        # Test precision preservation
        print(f"\n🧪 Precision Test:")

        # Convert to float and back to string
        if isinstance(to_amount, str):
            float_value = float(to_amount)
            decimal_value = Decimal(to_amount)
        else:
            float_value = float(to_amount)
            decimal_value = Decimal(str(to_amount))

        float_roundtrip = str(float_value)

        print(f"   Original: {to_amount}")
        print(f"   As float: {float_value}")
        print(f"   Float→str: {float_roundtrip}")
        print(f"   As Decimal: {decimal_value}")

        # Check for precision loss
        original_str = str(to_amount)
        if original_str == float_roundtrip:
            precision_status = "✅ NO PRECISION LOSS"
        else:
            precision_status = f"⚠️ PRECISION LOSS DETECTED"
            print(f"   Difference: {original_str} != {float_roundtrip}")

        print(f"   Status: {precision_status}")

        # Additional info
        print(f"\n💰 Exchange Details:")
        print(f"   From Amount: {params['fromAmount']} {params['fromCurrency'].upper()}")
        print(f"   To Amount: {to_amount} {params['toCurrency'].upper()}")
        print(f"   Deposit Fee: {deposit_fee}")
        print(f"   Withdrawal Fee: {withdrawal_fee}")

        # Calculate number of digits
        if isinstance(to_amount, str):
            num_digits = len(to_amount.replace('.', '').replace('-', ''))
        else:
            num_digits = len(str(to_amount).replace('.', '').replace('-', ''))

        print(f"\n📊 Digit Analysis:")
        print(f"   Total digits: {num_digits}")
        if num_digits <= 15:
            print(f"   Float safety: ✅ SAFE (≤15 digits)")
        elif num_digits <= 17:
            print(f"   Float safety: 🟡 BORDERLINE (15-17 digits)")
        else:
            print(f"   Float safety: ❌ UNSAFE (>17 digits)")

        return {
            "test_name": test_case["name"],
            "to_amount": to_amount,
            "to_amount_type": to_amount_type,
            "json_format": json_format,
            "precision_safe": original_str == float_roundtrip,
            "num_digits": num_digits,
            "deposit_fee": deposit_fee,
            "withdrawal_fee": withdrawal_fee
        }

    except requests.exceptions.Timeout:
        print(f"   ❌ Request timeout")
        return None
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection error")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def print_summary(results: list):
    """Print summary of all test results."""
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}\n")

    if not results:
        print("❌ No successful tests")
        return

    all_safe = all(r['precision_safe'] for r in results if r)
    all_strings = all(r['json_format'] == 'STRING' for r in results if r)

    print(f"Tests completed: {len([r for r in results if r])}/{len(results)}")
    print(f"\n🔍 JSON Format Analysis:")

    for result in results:
        if result:
            status = "✅" if result['precision_safe'] else "⚠️"
            print(f"   {status} {result['test_name']}")
            print(f"      - JSON format: {result['json_format']}")
            print(f"      - Python type: {result['to_amount_type']}")
            print(f"      - Precision safe: {result['precision_safe']}")
            print(f"      - Total digits: {result['num_digits']}")

    print(f"\n🎯 Conclusion:")

    if all_strings:
        print(f"   ✅ ChangeNow returns amounts as STRINGS")
        print(f"   ✅ System CAN safely handle high-value tokens")
        print(f"   📝 Recommendation: Use Decimal parsing to preserve precision")
    elif all_safe:
        print(f"   🟡 ChangeNow returns amounts as NUMBERS")
        print(f"   🟡 System MAY work but precision is at risk")
        print(f"   📝 Recommendation: Implement Decimal conversion fixes")
    else:
        print(f"   ❌ Precision loss detected in some test cases")
        print(f"   ❌ System NEEDS fixes before handling high-value tokens")
        print(f"   📝 Recommendation: Implement all precision fixes immediately")

    print(f"\n📚 Next Steps:")
    if all_strings and all_safe:
        print(f"   1. ✅ System is ready for high-value tokens")
        print(f"   2. Optional: Implement Decimal parsing for extra safety")
        print(f"   3. Monitor first SHIB payout closely")
    else:
        print(f"   1. Implement Fix #2: Replace float parsing with Decimal")
        print(f"   2. Implement Fix #1: Replace float() conversion with str()")
        print(f"   3. Re-test after fixes")
        print(f"   4. See LARGE_TOKEN_QUANTITY_ANALYSIS.md for details")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution function."""
    print("="*80)
    print("ChangeNow API Precision Test")
    print("="*80)
    print(f"\nPurpose: Test if ChangeNow can handle high-value tokens (SHIB/PEPE)")
    print(f"Question: Does ChangeNow return amounts as strings or numbers?")

    # Check API key
    if CHANGENOW_API_KEY == 'YOUR_API_KEY_HERE':
        print(f"\n❌ ERROR: ChangeNow API key not configured!")
        print(f"\nPlease either:")
        print(f"   1. Set environment variable: export CHANGENOW_API_KEY='your_key'")
        print(f"   2. Edit this script and replace 'YOUR_API_KEY_HERE'")
        print(f"\nGet API key from: https://changenow.io/api/")
        sys.exit(1)

    print(f"\n✅ API key configured: {CHANGENOW_API_KEY[:8]}...")
    print(f"\nRunning {len(TEST_CASES)} test(s)...\n")

    # Run tests
    results = []
    for test_case in TEST_CASES:
        result = test_changenow_response(test_case)
        results.append(result)

    # Print summary
    print_summary(results)

    print(f"\n{'='*80}")
    print(f"Test complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
