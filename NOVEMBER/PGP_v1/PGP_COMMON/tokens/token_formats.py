#!/usr/bin/env python
"""
Token Format Registry for PGP_v1 Services.

This module documents all token formats used across the PGP_v1 architecture.
Each token format is defined by its communication flow and field structure.

This serves as centralized documentation for all inter-service token formats,
making it easier to maintain consistency and debug token-related issues.
"""
from typing import Dict, List, Tuple, Any


# Token format registry: documents all token structures used in PGP_v1
TOKEN_FORMATS: Dict[str, Dict[str, Any]] = {

    # ========================================================================
    # NOWPayments Integration Tokens
    # ========================================================================

    "nowpayments_to_orchestrator": {
        "description": "NOWPayments success_url token format (entry point to PGP system)",
        "flow": "NOWPayments → PGP_ORCHESTRATOR_v1",
        "fields": [
            ("user_id", "6 bytes", "48-bit unsigned, converted to signed Telegram ID"),
            ("closed_channel_id", "6 bytes", "48-bit unsigned, converted to signed channel ID"),
            ("timestamp_minutes", "2 bytes", "uint16 (wrap-around at 65536 ≈ 45 days)"),
            ("subscription_time_days", "2 bytes", "uint16"),
            ("subscription_price", "variable", "1-byte length + UTF-8 string"),
            ("wallet_address", "variable", "1-byte length + UTF-8 string"),
            ("payout_currency", "variable", "1-byte length + UTF-8 string (e.g., 'btc', 'eth')"),
            ("payout_network", "variable", "1-byte length + UTF-8 string (e.g., 'btc', 'eth')"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated to 16 bytes"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "2 hours (7200 seconds)",
        "notes": [
            "Entry point from external payment processor",
            "Uses 48-bit IDs to minimize token size",
            "Timestamp in minutes allows 16-bit encoding (reduces by 4 bytes)",
            "All variable strings are network-optimized (e.g., 'btc' not 'Bitcoin')"
        ],
    },

    "orchestrator_to_invite": {
        "description": "Re-encrypted token for Telegram invite sender",
        "flow": "PGP_ORCHESTRATOR_v1 → PGP_INVITE_v1",
        "fields": [
            # Same structure as nowpayments_to_orchestrator but with fresh timestamp
            ("user_id", "6 bytes", "48-bit unsigned, converted to signed"),
            ("closed_channel_id", "6 bytes", "48-bit unsigned, converted to signed"),
            ("timestamp_minutes", "2 bytes", "uint16 (freshly generated)"),
            ("subscription_time_days", "2 bytes", "uint16"),
            ("subscription_price", "variable", "1-byte length + UTF-8 string"),
            ("wallet_address", "variable", "1-byte length + UTF-8 string"),
            ("payout_currency", "variable", "1-byte length + UTF-8 string"),
            ("payout_network", "variable", "1-byte length + UTF-8 string"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "24 hours (86400 seconds)",
        "notes": [
            "Orchestrator re-encrypts NOWPayments token with fresh timestamp",
            "Longer expiration (24hr) to accommodate Telegram invite delays",
            "Same format ensures consistency across the payment flow"
        ],
    },

    # ========================================================================
    # SPLIT Service Tokens (ETH Swap Flow)
    # ========================================================================

    "split1_to_split2_estimate_request": {
        "description": "Token for swap estimate request (ETH or USDT → Client Currency)",
        "flow": "PGP_SPLIT1_v1 → PGP_SPLIT2_v1",
        "fields": [
            ("user_id", "8 bytes", "uint64"),
            ("closed_channel_id", "16 bytes", "fixed-length padded string"),
            ("wallet_address", "variable", "1-byte length + UTF-8 string"),
            ("payout_currency", "variable", "1-byte length + UTF-8 string"),
            ("payout_network", "variable", "1-byte length + UTF-8 string"),
            ("adjusted_amount", "8 bytes", "double (ETH or USDT depending on payout_mode)"),
            ("swap_currency", "variable", "1-byte length + UTF-8 ('eth' or 'usdt')"),
            ("payout_mode", "variable", "1-byte length + UTF-8 ('instant' or 'threshold')"),
            ("actual_eth_amount", "8 bytes", "double (actual ETH from NOWPayments)"),
            ("timestamp", "4 bytes", "uint32"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "24 hours (86400 seconds)",
        "notes": [
            "Supports two payout modes: instant (direct ETH swap) and threshold (accumulated USDT swap)",
            "swap_currency indicates what's being swapped: 'eth' for instant, 'usdt' for threshold",
            "actual_eth_amount preserves the real amount received from NOWPayments",
            "adjusted_amount may differ from actual_eth_amount due to fee deductions"
        ],
    },

    "split2_to_split1_estimate_response": {
        "description": "Token with swap estimate details (ChangeNOW fees and amounts)",
        "flow": "PGP_SPLIT2_v1 → PGP_SPLIT1_v1",
        "fields": [
            ("user_id", "8 bytes", "uint64"),
            ("closed_channel_id", "16 bytes", "fixed-length"),
            ("wallet_address", "variable", "1-byte length + UTF-8"),
            ("payout_currency", "variable", "1-byte length + UTF-8"),
            ("payout_network", "variable", "1-byte length + UTF-8"),
            ("from_amount", "8 bytes", "double (ETH or USDT)"),
            ("to_amount_post_fee", "8 bytes", "double (client currency after fees)"),
            ("deposit_fee", "8 bytes", "double"),
            ("withdrawal_fee", "8 bytes", "double"),
            ("swap_currency", "variable", "1-byte length + UTF-8"),
            ("payout_mode", "variable", "1-byte length + UTF-8"),
            ("actual_eth_amount", "8 bytes", "double"),
            ("timestamp", "4 bytes", "uint32"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "24 hours",
        "notes": [
            "Contains ChangeNOW estimate with detailed fee breakdown",
            "to_amount_post_fee is the final amount client will receive",
            "Fees are explicitly tracked for transparency and debugging"
        ],
    },

    "split1_to_split3_swap_request": {
        "description": "Token to initiate actual swap on ChangeNOW",
        "flow": "PGP_SPLIT1_v1 → PGP_SPLIT3_v1",
        "fields": [
            ("unique_id", "16 bytes", "fixed-length unique identifier"),
            ("user_id", "8 bytes", "uint64"),
            ("closed_channel_id", "16 bytes", "fixed-length"),
            ("wallet_address", "variable", "1-byte length + UTF-8"),
            ("payout_currency", "variable", "1-byte length + UTF-8"),
            ("payout_network", "variable", "1-byte length + UTF-8"),
            ("eth_amount", "8 bytes", "double (estimated ETH amount)"),
            ("swap_currency", "variable", "1-byte length + UTF-8"),
            ("payout_mode", "variable", "1-byte length + UTF-8"),
            ("actual_eth_amount", "8 bytes", "double (ACTUAL from NOWPayments)"),
            ("timestamp", "4 bytes", "uint32"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "24 hours",
        "notes": [
            "unique_id ensures idempotency for ChangeNOW API calls",
            "eth_amount is the estimate, actual_eth_amount is what NOWPayments actually sent",
            "SPLIT3 uses actual_eth_amount for the real swap transaction"
        ],
    },

    "split3_to_split1_swap_response": {
        "description": "Token with ChangeNOW swap transaction details",
        "flow": "PGP_SPLIT3_v1 → PGP_SPLIT1_v1",
        "fields": [
            ("unique_id", "16 bytes", "fixed-length"),
            ("user_id", "8 bytes", "uint64"),
            ("closed_channel_id", "16 bytes", "fixed-length"),
            ("cn_api_id", "variable", "1-byte length + UTF-8 (ChangeNOW transaction ID)"),
            ("from_currency", "variable", "1-byte length + UTF-8"),
            ("to_currency", "variable", "1-byte length + UTF-8"),
            ("from_network", "variable", "1-byte length + UTF-8"),
            ("to_network", "variable", "1-byte length + UTF-8"),
            ("from_amount", "8 bytes", "double"),
            ("to_amount", "8 bytes", "double"),
            ("payin_address", "variable", "1-byte length + UTF-8 (ChangeNOW deposit address)"),
            ("payout_address", "variable", "1-byte length + UTF-8 (client wallet)"),
            ("refund_address", "variable", "1-byte length + UTF-8"),
            ("flow", "variable", "1-byte length + UTF-8 ('standard' or 'fixed-rate')"),
            ("type_", "variable", "1-byte length + UTF-8 ('direct' or 'reverse')"),
            ("actual_eth_amount", "8 bytes", "double"),
            ("timestamp", "4 bytes", "uint32"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "24 hours",
        "notes": [
            "Contains complete ChangeNOW transaction details",
            "cn_api_id is critical for tracking swap status",
            "payin_address is where SPLIT1 will send ETH",
            "payout_address is where client will receive their currency"
        ],
    },

    # ========================================================================
    # Batch Processing Tokens
    # ========================================================================

    "batch_to_split1": {
        "description": "Batch token for accumulated USDT payouts",
        "flow": "PGP_BATCHPROCESSOR_v1 → PGP_SPLIT1_v1",
        "fields": [
            # JSON payload structure:
            ("batch_id", "variable", "UUID string"),
            ("client_id", "variable", "string"),
            ("wallet_address", "variable", "string"),
            ("payout_currency", "variable", "string"),
            ("payout_network", "variable", "string"),
            ("amount_usdt", "variable", "decimal string"),
            ("timestamp", "variable", "integer"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated (after JSON payload)"),
        ],
        "signing_key": "TPS_HOSTPAY_SIGNING_KEY",
        "expiration": "24 hours",
        "notes": [
            "Uses JSON payload instead of binary packing for flexibility",
            "Different signing key (TPS_HOSTPAY_SIGNING_KEY) from other flows",
            "amount_usdt is accumulated from multiple threshold-mode payouts"
        ],
    },

    "microbatch_to_hostpay1_request": {
        "description": "Micro-batch conversion request token",
        "flow": "PGP_MICROBATCHPROCESSOR_v1 → PGP_HOSTPAY1_v1",
        "fields": [
            ("context", "variable", "1-byte length + UTF-8 ('batch')"),
            ("batch_conversion_id", "variable", "1-byte length + UUID string"),
            ("cn_api_id", "variable", "1-byte length + UTF-8"),
            ("from_currency", "variable", "1-byte length + UTF-8"),
            ("from_network", "variable", "1-byte length + UTF-8"),
            ("from_amount", "8 bytes", "double"),
            ("payin_address", "variable", "1-byte length + UTF-8"),
            ("timestamp", "8 bytes", "uint64"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "30 minutes (1800 seconds)",
        "notes": [
            "Shorter expiration (30min) due to crypto volatility",
            "Context field allows future extensibility",
            "Extended window accommodates ChangeNOW retry delays (up to 15 min)"
        ],
    },

    "hostpay1_to_microbatch_response": {
        "description": "Batch execution completion token",
        "flow": "PGP_HOSTPAY1_v1 → PGP_MICROBATCHPROCESSOR_v1",
        "fields": [
            ("batch_conversion_id", "variable", "1-byte length + UUID string"),
            ("cn_api_id", "variable", "1-byte length + UTF-8"),
            ("tx_hash", "variable", "1-byte length + UTF-8 (blockchain transaction hash)"),
            ("actual_usdt_received", "8 bytes", "double"),
            ("timestamp", "8 bytes", "uint64"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "30 minutes",
        "notes": [
            "tx_hash is blockchain confirmation",
            "actual_usdt_received may differ from estimate due to slippage"
        ],
    },

    # ========================================================================
    # Accumulator Tokens
    # ========================================================================

    "accumulator_to_split3": {
        "description": "Accumulated ETH to USDT swap request",
        "flow": "PGP_ACCUMULATOR_v1 → PGP_SPLIT3_v1",
        "fields": [
            ("accumulation_id", "8 bytes", "int64"),
            ("client_id", "variable", "1-byte length + string"),
            ("eth_amount", "8 bytes", "double"),
            ("usdt_wallet_address", "variable", "1-byte length + UTF-8"),
            ("timestamp", "8 bytes", "uint64"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "5 minutes (300 seconds)",
        "notes": [
            "Very short expiration due to ETH volatility",
            "Accumulation happens when client reaches threshold",
            "SPLIT3 handles swap to USDT for fiat off-ramp"
        ],
    },

    "split3_to_accumulator": {
        "description": "ETH→USDT swap completion details",
        "flow": "PGP_SPLIT3_v1 → PGP_ACCUMULATOR_v1",
        "fields": [
            ("accumulation_id", "8 bytes", "int64"),
            ("client_id", "variable", "1-byte length + string"),
            ("cn_api_id", "variable", "1-byte length + UTF-8"),
            ("from_amount", "8 bytes", "double (ETH)"),
            ("to_amount", "8 bytes", "double (USDT)"),
            ("payin_address", "variable", "1-byte length + UTF-8"),
            ("payout_address", "variable", "1-byte length + UTF-8"),
            ("timestamp", "8 bytes", "uint64"),
            ("signature", "16 bytes", "HMAC-SHA256 truncated"),
        ],
        "signing_key": "SUCCESS_URL_SIGNING_KEY",
        "expiration": "5 minutes",
        "notes": [
            "Completes accumulation cycle",
            "to_amount (USDT) is what gets added to batch queue"
        ],
    },

    # ========================================================================
    # HostPay Internal Tokens
    # ========================================================================

    "hostpay1_to_hostpay2": {
        "description": "Internal HostPay token (HostPay1 → HostPay2)",
        "flow": "PGP_HOSTPAY1_v1 → PGP_HOSTPAY2_v1",
        "fields": [
            # Structure varies by implementation
            # Uses PGP_INTERNAL_SIGNING_KEY for internal communication
        ],
        "signing_key": "PGP_INTERNAL_SIGNING_KEY",
        "expiration": "Varies by implementation",
        "notes": [
            "Internal HostPay communication uses separate key",
            "Format customized for HostPay-specific needs",
            "Not exposed to external systems"
        ],
    },

    "hostpay2_to_hostpay3": {
        "description": "Internal HostPay token (HostPay2 → HostPay3)",
        "flow": "PGP_HOSTPAY2_v1 → PGP_HOSTPAY3_v1",
        "fields": [
            # Structure varies by implementation
        ],
        "signing_key": "PGP_INTERNAL_SIGNING_KEY",
        "expiration": "Varies by implementation",
        "notes": [
            "Internal HostPay communication",
            "Format customized for HostPay-specific needs"
        ],
    },
}


def get_token_format(format_name: str) -> Dict[str, Any]:
    """
    Retrieve token format documentation by name.

    Args:
        format_name: Name of the token format (e.g., 'nowpayments_to_orchestrator')

    Returns:
        Dictionary with token format specification

    Raises:
        KeyError: If format_name not found in registry
    """
    if format_name not in TOKEN_FORMATS:
        raise KeyError(f"Token format '{format_name}' not found in registry")
    return TOKEN_FORMATS[format_name]


def list_token_formats() -> List[str]:
    """
    List all available token format names.

    Returns:
        List of token format names
    """
    return list(TOKEN_FORMATS.keys())


def get_formats_by_signing_key(signing_key_name: str) -> List[str]:
    """
    Get all token formats that use a specific signing key.

    Args:
        signing_key_name: Name of signing key (e.g., 'SUCCESS_URL_SIGNING_KEY')

    Returns:
        List of token format names using that key
    """
    return [
        name for name, fmt in TOKEN_FORMATS.items()
        if fmt.get("signing_key") == signing_key_name
    ]


def get_formats_by_service(service_name: str) -> List[Tuple[str, str]]:
    """
    Get all token formats involving a specific service.

    Args:
        service_name: Service name (e.g., 'PGP_SPLIT1_v1')

    Returns:
        List of (format_name, flow) tuples
    """
    results = []
    for name, fmt in TOKEN_FORMATS.items():
        flow = fmt.get("flow", "")
        if service_name in flow:
            results.append((name, flow))
    return results


# Export all public functions and constants
__all__ = [
    "TOKEN_FORMATS",
    "get_token_format",
    "list_token_formats",
    "get_formats_by_signing_key",
    "get_formats_by_service",
]
