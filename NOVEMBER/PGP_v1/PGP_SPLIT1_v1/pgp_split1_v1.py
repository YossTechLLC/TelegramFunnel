#!/usr/bin/env python
"""
PGP_SPLIT1_v1: Payment Splitting Orchestrator Service
Coordinates payment splitting workflow across PGP_SPLIT2_v1 and PGP_SPLIT3_v1 using Cloud Tasks.
Handles database operations and integrates with GCHostPay for final ETH transfers.
"""
import os
import json
import time
import struct
import base64
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from flask import Flask, request, abort, jsonify

# Import service modules
from config_manager import ConfigManager
from database_manager import DatabaseManager
from token_manager import TokenManager
from cloudtasks_client import CloudTasksClient
from PGP_COMMON.utils import verify_sha256_signature

from PGP_COMMON.logging import setup_logger
logger = setup_logger(__name__)
# Initialize logger

app = Flask(__name__)

# Initialize managers
logger.info(f"🚀 [APP] Initializing PGP_SPLIT1_v1 Orchestrator Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize database manager
try:
    database_manager = DatabaseManager(config)
    logger.info(f"✅ [APP] Database manager initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize database manager: {e}", exc_info=True)
    database_manager = None

# Initialize token manager
try:
    signing_key = config.get('success_url_signing_key')
    batch_signing_key = config.get('tps_hostpay_signing_key')
    if not signing_key:
        raise ValueError("SUCCESS_URL_SIGNING_KEY not available")
    if not batch_signing_key:
        logger.warning(f"⚠️ [APP] TPS_HOSTPAY_SIGNING_KEY not available - batch token decryption may fail")
    token_manager = TokenManager(signing_key, batch_signing_key)
    logger.info(f"✅ [APP] Token manager initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize token manager: {e}", exc_info=True)
    token_manager = None

# Initialize Cloud Tasks client
try:
    project_id = config.get('cloud_tasks_project_id')
    location = config.get('cloud_tasks_location')
    if not project_id or not location:
        raise ValueError("Cloud Tasks configuration incomplete")
    cloudtasks_client = CloudTasksClient(project_id, location)
    logger.info(f"✅ [APP] Cloud Tasks client initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize Cloud Tasks client: {e}", exc_info=True)
    cloudtasks_client = None


# ============================================================================
# WEBHOOK SIGNATURE VERIFICATION - Moved to PGP_COMMON/utils/webhook_auth.py
# ============================================================================
# The verify_webhook_signature() function has been replaced with:
#   verify_sha256_signature() from PGP_COMMON.utils
#
# This consolidates duplicate signature verification logic across services.
# (~27 lines moved to shared utility)
# ============================================================================


def calculate_adjusted_amount(subscription_price: str, tp_flat_fee: str) -> Tuple[float, float]:
    """
    Calculate the adjusted amount after removing TP flat fee.

    Args:
        subscription_price: Original subscription price as string
        tp_flat_fee: TP flat fee percentage as string (e.g., "3" for 3%)

    Returns:
        Tuple of (original_amount, adjusted_amount)
    """
    try:
        original_amount = Decimal(subscription_price)
        fee_percentage = Decimal(tp_flat_fee if tp_flat_fee else "3")

        fee_amount = original_amount * (fee_percentage / Decimal("100"))
        adjusted_amount = original_amount - fee_amount

        logger.info(f"💰 [FEE_CALC] Original: ${original_amount}")
        logger.debug(f"📊 [FEE_CALC] TP fee: {fee_percentage}%")
        logger.info(f"💸 [FEE_CALC] Fee amount: ${fee_amount}")
        logger.info(f"✅ [FEE_CALC] Adjusted: ${adjusted_amount}")

        return (float(original_amount), float(adjusted_amount))

    except Exception as e:
        logger.error(f"❌ [FEE_CALC] Error: {e}", exc_info=True)
        return (float(subscription_price), float(subscription_price))


def build_hostpay_token(
    unique_id: str,
    cn_api_id: str,
    from_currency: str,
    from_network: str,
    actual_eth_amount: float,      # ✅ RENAMED from from_amount
    estimated_eth_amount: float,   # ✅ ADDED
    payin_address: str,
    signing_key: str
) -> Optional[str]:
    """
    Build a cryptographically signed token for PGP_HOSTPAY1_v10-26 webhook.

    Token Format (binary packed):
    - 16 bytes: unique_id (fixed, padded)
    - 1 byte: cn_api_id length + variable bytes
    - 1 byte: from_currency length + variable bytes
    - 1 byte: from_network length + variable bytes
    - 8 bytes: actual_eth_amount (double) - ACTUAL from NowPayments
    - 8 bytes: estimated_eth_amount (double) - ChangeNow estimate
    - 1 byte: payin_address length + variable bytes
    - 4 bytes: timestamp (uint32)
    - 16 bytes: HMAC-SHA256 signature (truncated)

    Returns:
        Base64 URL-safe encoded token or None if failed
    """
    try:
        logger.info(f"🔐 [HOSTPAY_TOKEN] Building GCHostPay token")

        unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
        cn_api_id_bytes = cn_api_id.encode('utf-8')
        from_currency_bytes = from_currency.lower().encode('utf-8')
        from_network_bytes = from_network.lower().encode('utf-8')
        payin_address_bytes = payin_address.encode('utf-8')

        current_timestamp = int(time.time())

        # Build packed data
        packed_data = bytearray()
        packed_data.extend(unique_id_bytes)
        packed_data.append(len(cn_api_id_bytes))
        packed_data.extend(cn_api_id_bytes)
        packed_data.append(len(from_currency_bytes))
        packed_data.extend(from_currency_bytes)
        packed_data.append(len(from_network_bytes))
        packed_data.extend(from_network_bytes)
        packed_data.extend(struct.pack(">d", actual_eth_amount))      # ✅ ACTUAL (for payment)
        packed_data.extend(struct.pack(">d", estimated_eth_amount))   # ✅ ESTIMATED (for comparison)
        packed_data.append(len(payin_address_bytes))
        packed_data.extend(payin_address_bytes)
        packed_data.extend(struct.pack(">I", current_timestamp))

        # Generate HMAC signature
        full_signature = hmac.new(signing_key.encode(), bytes(packed_data), hashlib.sha256).digest()
        truncated_signature = full_signature[:16]

        # Combine data + signature
        final_data = bytes(packed_data) + truncated_signature
        token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

        logger.info(f"✅ [HOSTPAY_TOKEN] Token generated successfully ({len(token)} chars)")
        logger.debug(f"🆔 [HOSTPAY_TOKEN] Unique ID: {unique_id}")
        logger.debug(f"🆔 [HOSTPAY_TOKEN] CN API ID: {cn_api_id}")
        print(f"💰 [HOSTPAY_TOKEN] ACTUAL amount: {actual_eth_amount} {from_currency.upper()}")       # ✅ LOG ACTUAL
        print(f"💰 [HOSTPAY_TOKEN] ESTIMATED amount: {estimated_eth_amount} {from_currency.upper()}") # ✅ LOG ESTIMATED

        return token

    except Exception as e:
        logger.error(f"❌ [HOSTPAY_TOKEN] Error building token: {e}", exc_info=True)
        return None


def calculate_pure_market_conversion(
    from_amount: float,  # ✅ Generic name (ETH or USDT)
    to_amount_post_fee: float,  # ✅ Generic name (ClientCurrency)
    deposit_fee: float,
    withdrawal_fee: float
) -> float:
    """
    Calculate pure market rate conversion from ChangeNow estimate data.

    ChangeNow's toAmount includes fees deducted. This function back-calculates
    the pure market rate to get the true USDT→ETH conversion value.

    Purpose: split_payout_request should store the MARKET VALUE in ETH
             (how much ETH is this dollar amount worth at current rates)
             NOT the post-fee swap amount.

    Formula:
        1. Actual USDT swapped = fromAmount - depositFee
        2. ETH before withdrawal = toAmount + withdrawalFee
        3. Market Rate = ETH_before / USDT_swapped
        4. Pure Conversion = original_fromAmount * Market_Rate

    Returns:
        Pure market conversion amount (ETH) without fees
    """
    try:
        logger.info(f"🧮 [MARKET_CALC] Calculating pure market conversion")
        logger.info(f"   From Amount: {from_amount}")
        logger.info(f"   To Amount (post-fee): {to_amount_post_fee}")
        logger.info(f"   Deposit Fee: {deposit_fee}")
        logger.info(f"   Withdrawal Fee: {withdrawal_fee}")

        amount_swapped = from_amount - deposit_fee
        amount_before_withdrawal = to_amount_post_fee + withdrawal_fee

        logger.info(f"   Amount swapped: {amount_swapped}")
        logger.info(f"   Amount before withdrawal: {amount_before_withdrawal}")

        if amount_swapped <= 0:
            logger.error(f"❌ [MARKET_CALC] Invalid amount_swapped: {amount_swapped}")
            return to_amount_post_fee  # Fallback

        market_rate = amount_before_withdrawal / amount_swapped
        logger.info(f"   Market Rate: {market_rate}")

        pure_market_value = from_amount * market_rate

        logger.info(f"✅ [MARKET_CALC] Pure market value: {pure_market_value}")
        logger.info(f"   (True market value of {from_amount})")
        logger.info(f"   Difference from post-fee: +{pure_market_value - to_amount_post_fee}")

        return pure_market_value

    except Exception as e:
        logger.error(f"❌ [MARKET_CALC] Error: {e}", exc_info=True)
        logger.warning(f"⚠️ [MARKET_CALC] Falling back to post-fee amount")
        return to_amount_post_fee


# ============================================================================
# ENDPOINT 1: POST / - Initial webhook from PGP_ORCHESTRATOR_v1
# ============================================================================

@app.route("/", methods=["POST"])
def initial_webhook():
    """
    Main webhook endpoint for receiving payment split requests from PGP_ORCHESTRATOR_v10-26.

    Flow:
    1. Verify HMAC signature
    2. Extract data from webhook
    3. Calculate adjusted amount (remove TP fee)
    4. Encrypt token for PGP_SPLIT2_v1
    5. Enqueue Cloud Task to PGP_SPLIT2_v1

    Returns:
        JSON response with status
    """
    try:
        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get('X-Webhook-Signature', '')

        logger.info(f"🎯 [ENDPOINT_1] Initial webhook called (from GCWebhook)")
        logger.info(f"📦 [ENDPOINT_1] Payload size: {len(payload)} bytes")

        # Verify signature using shared utility
        signing_key = config.get('success_url_signing_key')
        if signing_key and not verify_sha256_signature(payload, signature, signing_key):
            logger.error(f"❌ [ENDPOINT_1] Invalid signature")
            abort(401, "Invalid webhook signature")

        # Parse JSON payload
        try:
            webhook_data = request.get_json()
            if not webhook_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT_1] JSON parsing error: {e}", exc_info=True)
            abort(400, "Malformed JSON payload")

        # Extract required data with null-safe handling
        # Note: webhook_data.get('key', '') doesn't protect against None values
        # (None is truthy in dict.get context). Use (value or '') pattern instead.
        user_id = webhook_data.get('user_id')
        closed_channel_id = webhook_data.get('closed_channel_id')
        wallet_address = (webhook_data.get('wallet_address') or '').strip()
        payout_currency = (webhook_data.get('payout_currency') or '').strip().lower()
        payout_network = (webhook_data.get('payout_network') or '').strip().lower()
        subscription_price = webhook_data.get('subscription_price') or webhook_data.get('sub_price') or '0'
        actual_eth_amount = float(webhook_data.get('actual_eth_amount', 0.0))  # ✅ ADDED: Extract ACTUAL ETH from NowPayments
        payout_mode = webhook_data.get('payout_mode', 'instant').strip().lower()  # ✅ NEW: Extract payout_mode (default: instant)

        # ✅ NEW: Determine swap_currency based on payout_mode
        # Instant: ETH→ClientCurrency (use actual ETH from NowPayments)
        # Threshold: USDT→ClientCurrency (use accumulated USDT)
        swap_currency = 'eth' if payout_mode == 'instant' else 'usdt'

        logger.info(f"👤 [ENDPOINT_1] User ID: {user_id}")
        logger.info(f"🏢 [ENDPOINT_1] Channel ID: {closed_channel_id}")
        logger.info(f"💰 [ENDPOINT_1] Subscription Price: ${subscription_price}")
        logger.info(f"💎 [ENDPOINT_1] ACTUAL ETH Amount (NowPayments): {actual_eth_amount}")
        print(f"🎯 [ENDPOINT_1] Payout Mode: {payout_mode}")  # ✅ NEW LOG
        print(f"💱 [ENDPOINT_1] Swap Currency: {swap_currency}")  # ✅ NEW LOG
        logger.info(f"🏦 [ENDPOINT_1] Target: {wallet_address} ({payout_currency.upper()} on {payout_network.upper()})")

        # ✅ ADDED: Validation warning if actual_eth_amount is missing/zero
        if actual_eth_amount == 0.0:
            logger.warning(f"⚠️ [ENDPOINT_1] WARNING: actual_eth_amount is zero (backward compat mode - using estimates)")

        # Validate required fields
        if not all([user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_price]):
            logger.error(f"❌ [ENDPOINT_1] Missing required fields")
            return jsonify({
                "status": "error",
                "message": "Missing required fields",
                "details": {
                    "user_id": bool(user_id),
                    "closed_channel_id": bool(closed_channel_id),
                    "wallet_address": bool(wallet_address),
                    "payout_currency": bool(payout_currency),
                    "payout_network": bool(payout_network),
                    "subscription_price": bool(subscription_price)
                }
            }), 400

        # ✅ UPDATED: Calculate adjusted amount based on swap_currency
        # Instant (ETH): Use actual_eth_amount from NowPayments (already net of network fees)
        # Threshold (USDT): Calculate adjusted_amount_usdt by removing TP fee from subscription_price
        tp_flat_fee = config.get('tp_flat_fee')

        if swap_currency == 'eth':
            # Instant payout: Use ACTUAL ETH received from NowPayments MINUS TP fee
            tp_fee_decimal = float(tp_flat_fee if tp_flat_fee else "3") / 100
            adjusted_amount = actual_eth_amount * (1 - tp_fee_decimal)
            logger.info(f"⚡ [ENDPOINT_1] Instant payout mode detected")
            logger.info(f"   💎 ACTUAL ETH from NowPayments: {actual_eth_amount}")
            logger.debug(f"   📊 TP Fee: {tp_flat_fee}%")
            logger.info(f"   ✅ Adjusted amount (post-TP-fee): {adjusted_amount} ETH")
        else:
            # Threshold payout: Calculate USDT amount (USD - TP fee)
            original_amount, adjusted_amount = calculate_adjusted_amount(subscription_price, tp_flat_fee)
            logger.info(f"🎯 [ENDPOINT_1] Threshold payout - calculated adjusted USDT: ${adjusted_amount}")

        # Encrypt token for PGP_SPLIT2_v1
        if not token_manager:
            logger.error(f"❌ [ENDPOINT_1] Token manager not available")
            abort(500, "Service configuration error")

        encrypted_token = token_manager.encrypt_pgp_split1_to_pgp_split2_token(
            user_id=user_id,
            closed_channel_id=str(closed_channel_id),
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            adjusted_amount=adjusted_amount,  # ✅ UPDATED: Now handles both ETH and USDT
            swap_currency=swap_currency,  # ✅ NEW: Pass swap_currency
            payout_mode=payout_mode,  # ✅ NEW: Pass payout_mode
            actual_eth_amount=actual_eth_amount  # ✅ PASS: Pass ACTUAL ETH to PGP_SPLIT2_v1
        )

        if not encrypted_token:
            logger.error(f"❌ [ENDPOINT_1] Failed to encrypt token")
            abort(500, "Token encryption failed")

        # Enqueue Cloud Task to PGP_SPLIT2_v1
        if not cloudtasks_client:
            logger.error(f"❌ [ENDPOINT_1] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gcsplit2_queue = config.get('gcsplit2_queue')
        pgp_split2_url = config.get('pgp_split2_url')

        if not gcsplit2_queue or not pgp_split2_url:
            logger.error(f"❌ [ENDPOINT_1] PGP_SPLIT2_v1 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_pgp_split2_estimate_request(
            queue_name=gcsplit2_queue,
            target_url=pgp_split2_url,
            encrypted_token=encrypted_token
        )

        if not task_name:
            logger.error(f"❌ [ENDPOINT_1] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        logger.info(f"✅ [ENDPOINT_1] Successfully enqueued to PGP_SPLIT2_v1")
        logger.debug(f"🆔 [ENDPOINT_1] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "Payment split request accepted",
            "task_id": task_name
        }), 200

    except Exception as e:
        logger.error(f"❌ [ENDPOINT_1] Unexpected error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Webhook error: {str(e)}"
        }), 500


# ============================================================================
# ENDPOINT 2: POST /usdt-eth-estimate - Receives estimate from PGP_SPLIT2_v1
# ============================================================================

@app.route("/usdt-eth-estimate", methods=["POST"])
def receive_usdt_eth_estimate():
    """
    Endpoint for receiving USDT→ETH estimate response from PGP_SPLIT2_v1.

    Flow:
    1. Decrypt token from PGP_SPLIT2_v1
    2. Calculate pure market conversion value
    3. Insert into split_payout_request table
    4. Encrypt token for PGP_SPLIT3_v1
    5. Enqueue Cloud Task to PGP_SPLIT3_v1

    Returns:
        JSON response with status
    """
    try:
        logger.info(f"🎯 [ENDPOINT_2] USDT→ETH estimate received (from PGP_SPLIT2_v1)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT_2] JSON parsing error: {e}", exc_info=True)
            abort(400, "Malformed JSON payload")

        encrypted_token = request_data.get('token')
        if not encrypted_token:
            logger.error(f"❌ [ENDPOINT_2] Missing token", exc_info=True)
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            logger.error(f"❌ [ENDPOINT_2] Token manager not available")
            abort(500, "Service configuration error")

        decrypted_data = token_manager.decrypt_pgp_split2_to_pgp_split1_token(encrypted_token)
        if not decrypted_data:
            logger.error(f"❌ [ENDPOINT_2] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract data
        user_id = decrypted_data['user_id']
        closed_channel_id = decrypted_data['closed_channel_id']
        wallet_address = decrypted_data['wallet_address']
        payout_currency = decrypted_data['payout_currency']
        payout_network = decrypted_data['payout_network']
        from_amount = decrypted_data['from_amount']  # ✅ UPDATED: Generic name (ETH or USDT)
        to_amount_post_fee = decrypted_data['to_amount_post_fee']  # ✅ FIXED: Correct key name
        deposit_fee = decrypted_data['deposit_fee']
        withdrawal_fee = decrypted_data['withdrawal_fee']
        actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)
        swap_currency = decrypted_data.get('swap_currency', 'usdt')  # ✅ NEW: Extract swap_currency
        payout_mode = decrypted_data.get('payout_mode', 'instant')  # ✅ NEW: Extract payout_mode

        logger.info(f"👤 [ENDPOINT_2] User ID: {user_id}")
        print(f"💱 [ENDPOINT_2] Swap Currency: {swap_currency}")  # ✅ NEW LOG
        print(f"🎯 [ENDPOINT_2] Payout Mode: {payout_mode}")  # ✅ NEW LOG
        print(f"💰 [ENDPOINT_2] From: {from_amount} {swap_currency.upper()}")  # ✅ UPDATED: Dynamic currency
        print(f"💰 [ENDPOINT_2] To (post-fee): {to_amount_post_fee} {payout_currency.upper()}")  # ✅ FIXED
        logger.info(f"💎 [ENDPOINT_2] ACTUAL ETH (from NowPayments): {actual_eth_amount}")

        # Calculate pure market conversion
        pure_market_value = calculate_pure_market_conversion(
            from_amount, to_amount_post_fee, deposit_fee, withdrawal_fee  # ✅ FIXED
        )

        # Insert into split_payout_request table
        if not database_manager:
            logger.error(f"❌ [ENDPOINT_2] Database manager not available")
            abort(500, "Database unavailable")

        logger.info(f"💾 [ENDPOINT_2] Inserting into split_payout_request")
        logger.info(f"   NOTE: to_amount = PURE MARKET VALUE ({pure_market_value} {payout_currency.upper()})")
        logger.info(f"   💎 ACTUAL ETH: {actual_eth_amount}")

        unique_id = database_manager.insert_split_payout_request(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            from_currency=swap_currency,  # ✅ UPDATED: Dynamic (eth or usdt)
            to_currency=payout_currency,
            from_network="eth",  # Both ETH and USDT use ETH network
            to_network=payout_network,
            from_amount=from_amount,  # ✅ UPDATED: Dynamic amount
            to_amount=pure_market_value,  # Pure market value
            client_wallet_address=wallet_address,
            refund_address="",
            flow="standard",
            type_="direct",
            actual_eth_amount=actual_eth_amount
        )

        if not unique_id:
            logger.error(f"❌ [ENDPOINT_2] Failed to insert into database")
            abort(500, "Database insertion failed")

        logger.info(f"✅ [ENDPOINT_2] Database insertion successful")
        logger.debug(f"🆔 [ENDPOINT_2] Unique ID: {unique_id}")

        # Encrypt token for PGP_SPLIT3_v1
        encrypted_token_for_split3 = token_manager.encrypt_pgp_split1_to_pgp_split3_token(
            unique_id=unique_id,
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            eth_amount=from_amount,  # ✅ UPDATED: Pass swap currency amount (ETH or USDT)
            swap_currency=swap_currency,  # ✅ NEW: Pass swap_currency
            payout_mode=payout_mode,  # ✅ NEW: Pass payout_mode
            actual_eth_amount=actual_eth_amount
        )

        if not encrypted_token_for_split3:
            logger.error(f"❌ [ENDPOINT_2] Failed to encrypt token for PGP_SPLIT3_v1")
            abort(500, "Token encryption failed")

        # Enqueue Cloud Task to PGP_SPLIT3_v1
        if not cloudtasks_client:
            logger.error(f"❌ [ENDPOINT_2] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gcsplit3_queue = config.get('gcsplit3_queue')
        pgp_split3_url = config.get('pgp_split3_url')

        if not gcsplit3_queue or not pgp_split3_url:
            logger.error(f"❌ [ENDPOINT_2] PGP_SPLIT3_v1 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_pgp_split3_swap_request(
            queue_name=gcsplit3_queue,
            target_url=pgp_split3_url,
            encrypted_token=encrypted_token_for_split3
        )

        if not task_name:
            logger.error(f"❌ [ENDPOINT_2] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        logger.info(f"✅ [ENDPOINT_2] Successfully enqueued to PGP_SPLIT3_v1")
        logger.debug(f"🆔 [ENDPOINT_2] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "Estimate processed and swap request enqueued",
            "unique_id": unique_id,
            "task_id": task_name
        }), 200

    except Exception as e:
        logger.error(f"❌ [ENDPOINT_2] Unexpected error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


# ============================================================================
# ENDPOINT 3: POST /eth-client-swap - Receives swap result from PGP_SPLIT3_v1
# ============================================================================

@app.route("/eth-client-swap", methods=["POST"])
def receive_eth_client_swap():
    """
    Endpoint for receiving ETH→ClientCurrency swap response from PGP_SPLIT3_v1.

    Flow:
    1. Decrypt token from PGP_SPLIT3_v1
    2. Insert into split_payout_que table
    3. Build GCHostPay token
    4. Enqueue Cloud Task to GCHostPay

    Returns:
        JSON response with status
    """
    try:
        logger.info(f"🎯 [ENDPOINT_3] ETH→Client swap received (from PGP_SPLIT3_v1)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT_3] JSON parsing error: {e}", exc_info=True)
            abort(400, "Malformed JSON payload")

        encrypted_token = request_data.get('token')
        if not encrypted_token:
            logger.error(f"❌ [ENDPOINT_3] Missing token", exc_info=True)
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            logger.error(f"❌ [ENDPOINT_3] Token manager not available")
            abort(500, "Service configuration error")

        decrypted_data = token_manager.decrypt_pgp_split3_to_pgp_split1_token(encrypted_token)
        if not decrypted_data:
            logger.error(f"❌ [ENDPOINT_3] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract data
        unique_id = decrypted_data['unique_id']
        user_id = decrypted_data['user_id']
        closed_channel_id = decrypted_data['closed_channel_id']
        cn_api_id = decrypted_data['cn_api_id']
        from_currency = decrypted_data['from_currency']
        to_currency = decrypted_data['to_currency']
        from_network = decrypted_data['from_network']
        to_network = decrypted_data['to_network']
        from_amount = decrypted_data['from_amount']  # ChangeNow estimate
        to_amount = decrypted_data['to_amount']
        payin_address = decrypted_data['payin_address']
        payout_address = decrypted_data['payout_address']
        refund_address = decrypted_data['refund_address']
        flow = decrypted_data['flow']
        type_ = decrypted_data['type']
        actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)  # ✅ ADDED: ACTUAL ETH from NowPayments

        logger.debug(f"🆔 [ENDPOINT_3] Unique ID: {unique_id}")
        logger.debug(f"🆔 [ENDPOINT_3] ChangeNow API ID: {cn_api_id}")
        logger.info(f"👤 [ENDPOINT_3] User ID: {user_id}")
        logger.info(f"💰 [ENDPOINT_3] ChangeNow from_amount: {from_amount} {from_currency.upper()}")
        logger.info(f"💰 [ENDPOINT_3] To: {to_amount} {to_currency.upper()}")

        # ✅ UPDATED: Currency-aware payment amount logic
        # For instant (ETH): Compare ChangeNow estimate vs ACTUAL ETH from NowPayments
        # For threshold (USDT): Use from_amount directly (no comparison needed)
        if from_currency.lower() == 'eth':
            logger.info(f"⚡ [ENDPOINT_3] Instant payout mode - ETH swap")
            logger.info(f"💎 [ENDPOINT_3] ACTUAL ETH (from NowPayments): {actual_eth_amount} ETH")

            # Validation - Compare actual vs estimate
            if actual_eth_amount > 0 and from_amount > 0:
                discrepancy = abs(from_amount - actual_eth_amount)
                discrepancy_pct = (discrepancy / actual_eth_amount) * 100

                logger.debug(f"📊 [ENDPOINT_3] Amount comparison:")
                logger.info(f"   ChangeNow estimate: {from_amount} ETH")
                logger.info(f"   ACTUAL from NowPayments: {actual_eth_amount} ETH")
                logger.info(f"   Discrepancy: {discrepancy} ETH ({discrepancy_pct:.2f}%)")

                if discrepancy_pct > 10:
                    logger.warning(f"⚠️ [ENDPOINT_3] WARNING: Large discrepancy (>10%)!")
                elif discrepancy_pct > 5:
                    logger.warning(f"⚠️ [ENDPOINT_3] Moderate discrepancy (>5%)")
                else:
                    logger.info(f"✅ [ENDPOINT_3] Amounts match within tolerance (<5%)")

            # Use ACTUAL ETH for payment
            if actual_eth_amount > 0:
                payment_amount_eth = actual_eth_amount
                estimated_amount_eth = from_amount
                logger.info(f"✅ [ENDPOINT_3] Using ACTUAL ETH for payment: {payment_amount_eth}")
            else:
                payment_amount_eth = from_amount
                estimated_amount_eth = from_amount
                logger.warning(f"⚠️ [ENDPOINT_3] ACTUAL ETH not available, using ChangeNow estimate: {payment_amount_eth}")

        else:  # from_currency == 'usdt'
            logger.info(f"🎯 [ENDPOINT_3] Threshold payout mode - USDT swap")
            # For USDT swaps, use the from_amount directly (this is accumulated USDT)
            payment_amount_eth = from_amount  # Actually USDT, but variable name maintained for compatibility
            estimated_amount_eth = from_amount
            logger.info(f"✅ [ENDPOINT_3] Using USDT amount for swap: {payment_amount_eth} USDT")

        # ============================================================================
        # CRITICAL: Idempotency Check - Prevent Duplicate Insertions
        # ============================================================================
        if not database_manager:
            logger.error(f"❌ [ENDPOINT_3] Database manager not available")
            abort(500, "Database unavailable")

        # Check if this ChangeNow transaction already exists
        logger.debug(f"🔍 [ENDPOINT_3] Checking for existing ChangeNow transaction")
        existing_record = database_manager.check_split_payout_que_by_cn_api_id(cn_api_id)

        if existing_record:
            print(f"=" * 80)
            logger.info(f"🛡️ [ENDPOINT_3] IDEMPOTENT REQUEST DETECTED")
            print(f"=" * 80)
            logger.info(f"✅ [ENDPOINT_3] ChangeNow transaction already processed: {cn_api_id}")
            logger.debug(f"🆔 [ENDPOINT_3] Linked unique_id: {existing_record['unique_id']}")
            logger.info(f"🕒 [ENDPOINT_3] Original insertion: {existing_record['created_at']}")
            logger.info(f"🔄 [ENDPOINT_3] This is likely a Cloud Tasks retry")
            logger.info(f"✅ [ENDPOINT_3] Returning success to prevent retry loop")
            print(f"=" * 80)

            # Return 200 OK to prevent Cloud Tasks from retrying
            return jsonify({
                "status": "success",
                "message": "ChangeNow transaction already processed (idempotent)",
                "unique_id": existing_record['unique_id'],
                "cn_api_id": cn_api_id,
                "from_currency": existing_record['from_currency'],
                "to_currency": existing_record['to_currency'],
                "idempotent": True,
                "original_processing_time": str(existing_record['created_at'])
            }), 200

        # If we reach here, this is a NEW transaction - proceed with insertion
        logger.info(f"💾 [ENDPOINT_3] Inserting into split_payout_que")

        que_success = database_manager.insert_split_payout_que(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            from_currency=from_currency,
            to_currency=to_currency,
            from_network=from_network,
            to_network=to_network,
            from_amount=from_amount,
            to_amount=to_amount,
            payin_address=payin_address,
            payout_address=payout_address,
            refund_address=refund_address,
            flow=flow,
            type_=type_,
            actual_eth_amount=actual_eth_amount  # ✅ NEW: Pass ACTUAL ETH from NowPayments
        )

        if not que_success:
            logger.error(f"❌ [ENDPOINT_3] Failed to insert into split_payout_que")

            # Double-check if failure is due to race condition (concurrent insertion)
            logger.debug(f"🔍 [ENDPOINT_3] Checking for concurrent insertion (race condition)")
            existing_record = database_manager.check_split_payout_que_by_cn_api_id(cn_api_id)

            if existing_record:
                logger.info(f"✅ [ENDPOINT_3] Record inserted by concurrent request")
                logger.info(f"✅ [ENDPOINT_3] Treating as idempotent success")

                return jsonify({
                    "status": "success",
                    "message": "Concurrent insertion handled (idempotent)",
                    "unique_id": existing_record['unique_id'],
                    "cn_api_id": cn_api_id,
                    "idempotent": True,
                    "race_condition_handled": True
                }), 200
            else:
                # Genuine insertion failure (not duplicate)
                abort(500, "Database insertion failed")

        logger.info(f"✅ [ENDPOINT_3] Database insertion successful")
        logger.info(f"🔗 [ENDPOINT_3] Linked to split_payout_request via unique_id: {unique_id}")

        # Build PGP_HOSTPAY1_v1 token
        tps_hostpay_signing_key = config.get('tps_hostpay_signing_key')
        if not tps_hostpay_signing_key:
            logger.error(f"❌ [ENDPOINT_3] HostPay signing key not available")
            abort(500, "HostPay configuration missing")

        hostpay_token = build_hostpay_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            from_currency=from_currency,
            from_network=from_network,
            actual_eth_amount=payment_amount_eth,  # ✅ UPDATED: Use ACTUAL ETH for payment
            estimated_eth_amount=estimated_amount_eth,  # ✅ UPDATED: Pass estimate for comparison
            payin_address=payin_address,
            signing_key=tps_hostpay_signing_key
        )

        if not hostpay_token:
            logger.error(f"❌ [ENDPOINT_3] Failed to build HostPay token")
            abort(500, "HostPay token generation failed")

        # Enqueue Cloud Task to PGP_HOSTPAY1_v1
        if not cloudtasks_client:
            logger.error(f"❌ [ENDPOINT_3] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        hostpay_queue = config.get('hostpay_queue')
        hostpay_webhook_url = config.get('hostpay_webhook_url')

        if not hostpay_queue or not hostpay_webhook_url:
            logger.error(f"❌ [ENDPOINT_3] HostPay configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_hostpay_trigger(
            queue_name=hostpay_queue,
            target_url=hostpay_webhook_url,
            encrypted_token=hostpay_token
        )

        if not task_name:
            logger.error(f"❌ [ENDPOINT_3] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        logger.info(f"✅ [ENDPOINT_3] Successfully enqueued to GCHostPay")
        logger.debug(f"🆔 [ENDPOINT_3] Task: {task_name}")
        logger.info(f"🎉 [ENDPOINT_3] Complete payment split workflow finished!")

        return jsonify({
            "status": "success",
            "message": "Swap processed and HostPay trigger enqueued",
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "task_id": task_name
        }), 200

    except Exception as e:
        logger.error(f"❌ [ENDPOINT_3] Unexpected error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


# ============================================================================
# ENDPOINT 4: POST /batch-payout - Batch payout from PGP_BATCHPROCESSOR
# ============================================================================

@app.route("/batch-payout", methods=["POST"])
def batch_payout():
    """
    Endpoint for receiving batch payout requests from PGP_BATCHPROCESSOR.

    Flow:
    1. Decrypt batch token
    2. Extract batch data (batch_id, client_id, amount, etc.)
    3. Encrypt token for PGP_SPLIT2_v1 (USDT estimate request)
    4. Enqueue Cloud Task to PGP_SPLIT2_v1
    5. Note: Use user_id=0 for batch payouts (not tied to single user)

    Returns:
        JSON response with status
    """
    try:
        logger.info(f"🎯 [ENDPOINT_4] Batch payout request received (from PGP_BATCHPROCESSOR)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT_4] JSON parsing error: {e}", exc_info=True)
            abort(400, "Malformed JSON payload")

        encrypted_token = request_data.get('token')
        batch_mode = request_data.get('batch_mode', False)

        if not encrypted_token:
            logger.error(f"❌ [ENDPOINT_4] Missing token", exc_info=True)
            abort(400, "Missing token")

        if not batch_mode:
            logger.warning(f"⚠️ [ENDPOINT_4] batch_mode flag not set, proceeding anyway")

        # Decrypt batch token
        if not token_manager:
            logger.error(f"❌ [ENDPOINT_4] Token manager not available")
            abort(500, "Service configuration error")

        decrypted_data = token_manager.decrypt_batch_token(encrypted_token)
        if not decrypted_data:
            logger.error(f"❌ [ENDPOINT_4] Failed to decrypt batch token")
            abort(401, "Invalid token")

        # Extract data
        batch_id = decrypted_data.get('batch_id')
        client_id = decrypted_data.get('client_id')
        wallet_address = decrypted_data.get('wallet_address')
        payout_currency = decrypted_data.get('payout_currency')
        payout_network = decrypted_data.get('payout_network')
        amount_usdt = decrypted_data.get('amount_usdt')

        logger.debug(f"🆔 [ENDPOINT_4] Batch ID: {batch_id}")
        logger.info(f"🏢 [ENDPOINT_4] Client ID: {client_id}")
        logger.info(f"💰 [ENDPOINT_4] Total Amount: ${amount_usdt} USDT")
        logger.info(f"🎯 [ENDPOINT_4] Target: {payout_currency.upper()} on {payout_network.upper()}")

        # Validate required fields
        if not all([batch_id, client_id, wallet_address, payout_currency, payout_network, amount_usdt]):
            logger.error(f"❌ [ENDPOINT_4] Missing required fields in decrypted token")
            return jsonify({
                "status": "error",
                "message": "Missing required fields in token",
                "details": {
                    "batch_id": bool(batch_id),
                    "client_id": bool(client_id),
                    "wallet_address": bool(wallet_address),
                    "payout_currency": bool(payout_currency),
                    "payout_network": bool(payout_network),
                    "amount_usdt": bool(amount_usdt)
                }
            }), 400

        # Note: For batch payouts, we use user_id=0 since it's not tied to a single user
        # The batch aggregates multiple user payments for the same client
        batch_user_id = 0

        logger.info(f"📝 [ENDPOINT_4] Using user_id={batch_user_id} for batch payout")

        # Encrypt token for PGP_SPLIT2_v1 (USDT estimate request)
        encrypted_token_for_split2 = token_manager.encrypt_pgp_split1_to_pgp_split2_token(
            user_id=batch_user_id,
            closed_channel_id=str(client_id),
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            adjusted_amount=amount_usdt,       # ✅ FIXED: Use new parameter name
            swap_currency='usdt',              # ✅ NEW: Threshold always uses USDT
            payout_mode='threshold',           # ✅ NEW: Mark as threshold payout
            actual_eth_amount=0.0              # ✅ NEW: No ETH in threshold flow
        )

        if not encrypted_token_for_split2:
            logger.error(f"❌ [ENDPOINT_4] Failed to encrypt token for PGP_SPLIT2_v1")
            abort(500, "Token encryption failed")

        # Enqueue Cloud Task to PGP_SPLIT2_v1
        if not cloudtasks_client:
            logger.error(f"❌ [ENDPOINT_4] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gcsplit2_queue = config.get('gcsplit2_queue')
        pgp_split2_url = config.get('pgp_split2_url')

        if not gcsplit2_queue or not pgp_split2_url:
            logger.error(f"❌ [ENDPOINT_4] PGP_SPLIT2_v1 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_pgp_split2_estimate_request(
            queue_name=gcsplit2_queue,
            target_url=pgp_split2_url,
            encrypted_token=encrypted_token_for_split2
        )

        if not task_name:
            logger.error(f"❌ [ENDPOINT_4] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        logger.info(f"✅ [ENDPOINT_4] Successfully enqueued batch payout to PGP_SPLIT2_v1")
        logger.debug(f"🆔 [ENDPOINT_4] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "Batch payout request accepted",
            "batch_id": batch_id,
            "task_id": task_name
        }), 200

    except Exception as e:
        logger.error(f"❌ [ENDPOINT_4] Unexpected error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Batch payout error: {str(e)}"
        }), 500


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Test database connection
        db_healthy = False
        if database_manager:
            try:
                conn = database_manager.get_database_connection()
                if conn:
                    conn.close()
                    db_healthy = True
            except Exception:
                pass

        return jsonify({
            "status": "healthy" if db_healthy else "degraded",
            "service": "PGP_SPLIT1_v1 Orchestrator",
            "timestamp": int(time.time()),
            "components": {
                "database": "healthy" if db_healthy else "unhealthy",
                "token_manager": "healthy" if token_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200 if db_healthy else 503

    except Exception as e:
        logger.error(f"❌ [HEALTH] Health check failed: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "service": "PGP_SPLIT1_v1 Orchestrator",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    logger.info(f"🚀 [APP] Starting PGP_SPLIT1_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
