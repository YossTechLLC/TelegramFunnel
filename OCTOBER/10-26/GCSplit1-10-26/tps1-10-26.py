#!/usr/bin/env python
"""
GCSplit1-10-26: Payment Splitting Orchestrator Service
Coordinates payment splitting workflow across GCSplit2 and GCSplit3 using Cloud Tasks.
Handles database operations and integrates with GCHostPay for final ETH transfers.
"""
import os
import json
import time
import hmac
import hashlib
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

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing GCSplit1-10-26 Orchestrator Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize database manager
try:
    database_manager = DatabaseManager(config)
    print(f"✅ [APP] Database manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize database manager: {e}")
    database_manager = None

# Initialize token manager
try:
    signing_key = config.get('success_url_signing_key')
    if not signing_key:
        raise ValueError("SUCCESS_URL_SIGNING_KEY not available")
    token_manager = TokenManager(signing_key)
    print(f"✅ [APP] Token manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize token manager: {e}")
    token_manager = None

# Initialize Cloud Tasks client
try:
    project_id = config.get('cloud_tasks_project_id')
    location = config.get('cloud_tasks_location')
    if not project_id or not location:
        raise ValueError("Cloud Tasks configuration incomplete")
    cloudtasks_client = CloudTasksClient(project_id, location)
    print(f"✅ [APP] Cloud Tasks client initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize Cloud Tasks client: {e}")
    cloudtasks_client = None


def verify_webhook_signature(payload: bytes, signature: str, signing_key: str) -> bool:
    """
    Verify webhook signature to ensure authentic requests.
    Uses SUCCESS_URL_SIGNING_KEY for signature verification.

    Args:
        payload: Raw request payload
        signature: Provided signature (HMAC-SHA256 hexdigest)
        signing_key: Secret signing key

    Returns:
        True if signature is valid, False otherwise
    """
    if not signing_key or not signature:
        return False

    try:
        expected_signature = hmac.new(
            signing_key.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        print(f"❌ [WEBHOOK_VERIFY] Signature verification error: {e}")
        return False


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

        print(f"💰 [FEE_CALC] Original: ${original_amount}")
        print(f"📊 [FEE_CALC] TP fee: {fee_percentage}%")
        print(f"💸 [FEE_CALC] Fee amount: ${fee_amount}")
        print(f"✅ [FEE_CALC] Adjusted: ${adjusted_amount}")

        return (float(original_amount), float(adjusted_amount))

    except Exception as e:
        print(f"❌ [FEE_CALC] Error: {e}")
        return (float(subscription_price), float(subscription_price))


def build_hostpay_token(
    unique_id: str,
    cn_api_id: str,
    from_currency: str,
    from_network: str,
    from_amount: float,
    payin_address: str,
    signing_key: str
) -> Optional[str]:
    """
    Build a cryptographically signed token for GCHostPay10-26 webhook.

    Token Format (binary packed):
    - 16 bytes: unique_id (fixed, padded)
    - 1 byte: cn_api_id length + variable bytes
    - 1 byte: from_currency length + variable bytes
    - 1 byte: from_network length + variable bytes
    - 8 bytes: from_amount (double)
    - 1 byte: payin_address length + variable bytes
    - 4 bytes: timestamp (uint32)
    - 16 bytes: HMAC-SHA256 signature (truncated)

    Returns:
        Base64 URL-safe encoded token or None if failed
    """
    try:
        print(f"🔐 [HOSTPAY_TOKEN] Building GCHostPay token")

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
        packed_data.extend(struct.pack(">d", from_amount))
        packed_data.append(len(payin_address_bytes))
        packed_data.extend(payin_address_bytes)
        packed_data.extend(struct.pack(">I", current_timestamp))

        # Generate HMAC signature
        full_signature = hmac.new(signing_key.encode(), bytes(packed_data), hashlib.sha256).digest()
        truncated_signature = full_signature[:16]

        # Combine data + signature
        final_data = bytes(packed_data) + truncated_signature
        token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

        print(f"✅ [HOSTPAY_TOKEN] Token generated successfully ({len(token)} chars)")
        print(f"🆔 [HOSTPAY_TOKEN] Unique ID: {unique_id}")
        print(f"🆔 [HOSTPAY_TOKEN] CN API ID: {cn_api_id}")
        print(f"💰 [HOSTPAY_TOKEN] Amount: {from_amount} {from_currency.upper()}")

        return token

    except Exception as e:
        print(f"❌ [HOSTPAY_TOKEN] Error building token: {e}")
        return None


def calculate_pure_market_conversion(
    from_amount_usdt: float,
    to_amount_eth_post_fee: float,
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
        print(f"🧮 [MARKET_CALC] Calculating pure market conversion")
        print(f"   From Amount: {from_amount_usdt} USDT")
        print(f"   To Amount (post-fee): {to_amount_eth_post_fee} ETH")
        print(f"   Deposit Fee: {deposit_fee} USDT")
        print(f"   Withdrawal Fee: {withdrawal_fee} ETH")

        usdt_swapped = from_amount_usdt - deposit_fee
        eth_before_withdrawal = to_amount_eth_post_fee + withdrawal_fee

        print(f"   USDT swapped: {usdt_swapped}")
        print(f"   ETH before withdrawal: {eth_before_withdrawal}")

        if usdt_swapped <= 0:
            print(f"❌ [MARKET_CALC] Invalid usdt_swapped: {usdt_swapped}")
            return to_amount_eth_post_fee  # Fallback

        market_rate = eth_before_withdrawal / usdt_swapped
        print(f"   Market Rate: {market_rate} ETH per USDT")

        pure_market_value = from_amount_usdt * market_rate

        print(f"✅ [MARKET_CALC] Pure market value: {pure_market_value} ETH")
        print(f"   (True market value of {from_amount_usdt} USDT)")
        print(f"   Difference from post-fee: +{pure_market_value - to_amount_eth_post_fee} ETH")

        return pure_market_value

    except Exception as e:
        print(f"❌ [MARKET_CALC] Error: {e}")
        print(f"⚠️ [MARKET_CALC] Falling back to post-fee amount")
        return to_amount_eth_post_fee


# ============================================================================
# ENDPOINT 1: POST / - Initial webhook from GCWebhook
# ============================================================================

@app.route("/", methods=["POST"])
def initial_webhook():
    """
    Main webhook endpoint for receiving payment split requests from GCWebhook10-26.

    Flow:
    1. Verify HMAC signature
    2. Extract data from webhook
    3. Calculate adjusted amount (remove TP fee)
    4. Encrypt token for GCSplit2
    5. Enqueue Cloud Task to GCSplit2

    Returns:
        JSON response with status
    """
    try:
        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get('X-Webhook-Signature', '')

        print(f"🎯 [ENDPOINT_1] Initial webhook called (from GCWebhook)")
        print(f"📦 [ENDPOINT_1] Payload size: {len(payload)} bytes")

        # Verify signature
        signing_key = config.get('success_url_signing_key')
        if signing_key and not verify_webhook_signature(payload, signature, signing_key):
            print(f"❌ [ENDPOINT_1] Invalid signature")
            abort(401, "Invalid webhook signature")

        # Parse JSON payload
        try:
            webhook_data = request.get_json()
            if not webhook_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT_1] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        # Extract required data
        user_id = webhook_data.get('user_id')
        closed_channel_id = webhook_data.get('closed_channel_id')
        wallet_address = webhook_data.get('wallet_address', '').strip()
        payout_currency = webhook_data.get('payout_currency', '').strip().lower()
        payout_network = webhook_data.get('payout_network', '').strip().lower()
        subscription_price = webhook_data.get('subscription_price') or webhook_data.get('sub_price')

        print(f"👤 [ENDPOINT_1] User ID: {user_id}")
        print(f"🏢 [ENDPOINT_1] Channel ID: {closed_channel_id}")
        print(f"💰 [ENDPOINT_1] Subscription Price: ${subscription_price}")
        print(f"🏦 [ENDPOINT_1] Target: {wallet_address} ({payout_currency.upper()} on {payout_network.upper()})")

        # Validate required fields
        if not all([user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_price]):
            print(f"❌ [ENDPOINT_1] Missing required fields")
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

        # Calculate adjusted amount (remove TP fee)
        tp_flat_fee = config.get('tp_flat_fee')
        original_amount, adjusted_amount_usdt = calculate_adjusted_amount(subscription_price, tp_flat_fee)

        # Encrypt token for GCSplit2
        if not token_manager:
            print(f"❌ [ENDPOINT_1] Token manager not available")
            abort(500, "Service configuration error")

        encrypted_token = token_manager.encrypt_gcsplit1_to_gcsplit2_token(
            user_id=user_id,
            closed_channel_id=str(closed_channel_id),
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            adjusted_amount_usdt=adjusted_amount_usdt
        )

        if not encrypted_token:
            print(f"❌ [ENDPOINT_1] Failed to encrypt token")
            abort(500, "Token encryption failed")

        # Enqueue Cloud Task to GCSplit2
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT_1] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gcsplit2_queue = config.get('gcsplit2_queue')
        gcsplit2_url = config.get('gcsplit2_url')

        if not gcsplit2_queue or not gcsplit2_url:
            print(f"❌ [ENDPOINT_1] GCSplit2 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_gcsplit2_estimate_request(
            queue_name=gcsplit2_queue,
            target_url=gcsplit2_url,
            encrypted_token=encrypted_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT_1] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT_1] Successfully enqueued to GCSplit2")
        print(f"🆔 [ENDPOINT_1] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "Payment split request accepted",
            "task_id": task_name
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT_1] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Webhook error: {str(e)}"
        }), 500


# ============================================================================
# ENDPOINT 2: POST /usdt-eth-estimate - Receives estimate from GCSplit2
# ============================================================================

@app.route("/usdt-eth-estimate", methods=["POST"])
def receive_usdt_eth_estimate():
    """
    Endpoint for receiving USDT→ETH estimate response from GCSplit2.

    Flow:
    1. Decrypt token from GCSplit2
    2. Calculate pure market conversion value
    3. Insert into split_payout_request table
    4. Encrypt token for GCSplit3
    5. Enqueue Cloud Task to GCSplit3

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT_2] USDT→ETH estimate received (from GCSplit2)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT_2] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        encrypted_token = request_data.get('token')
        if not encrypted_token:
            print(f"❌ [ENDPOINT_2] Missing token")
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            print(f"❌ [ENDPOINT_2] Token manager not available")
            abort(500, "Service configuration error")

        decrypted_data = token_manager.decrypt_gcsplit2_to_gcsplit1_token(encrypted_token)
        if not decrypted_data:
            print(f"❌ [ENDPOINT_2] Failed to decrypt token")
            abort(401, "Invalid token")

        # Extract data
        user_id = decrypted_data['user_id']
        closed_channel_id = decrypted_data['closed_channel_id']
        wallet_address = decrypted_data['wallet_address']
        payout_currency = decrypted_data['payout_currency']
        payout_network = decrypted_data['payout_network']
        from_amount_usdt = decrypted_data['from_amount_usdt']
        to_amount_eth_post_fee = decrypted_data['to_amount_eth_post_fee']
        deposit_fee = decrypted_data['deposit_fee']
        withdrawal_fee = decrypted_data['withdrawal_fee']

        print(f"👤 [ENDPOINT_2] User ID: {user_id}")
        print(f"💰 [ENDPOINT_2] From: {from_amount_usdt} USDT")
        print(f"💰 [ENDPOINT_2] To (post-fee): {to_amount_eth_post_fee} ETH")

        # Calculate pure market conversion
        pure_market_eth_value = calculate_pure_market_conversion(
            from_amount_usdt, to_amount_eth_post_fee, deposit_fee, withdrawal_fee
        )

        # Insert into split_payout_request table
        if not database_manager:
            print(f"❌ [ENDPOINT_2] Database manager not available")
            abort(500, "Database unavailable")

        print(f"💾 [ENDPOINT_2] Inserting into split_payout_request")
        print(f"   NOTE: to_amount = PURE MARKET VALUE ({pure_market_eth_value} ETH)")

        unique_id = database_manager.insert_split_payout_request(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            from_currency="usdt",
            to_currency=payout_currency,
            from_network="eth",
            to_network=payout_network,
            from_amount=from_amount_usdt,
            to_amount=pure_market_eth_value,  # Pure market value
            client_wallet_address=wallet_address,
            refund_address="",
            flow="standard",
            type_="direct"
        )

        if not unique_id:
            print(f"❌ [ENDPOINT_2] Failed to insert into database")
            abort(500, "Database insertion failed")

        print(f"✅ [ENDPOINT_2] Database insertion successful")
        print(f"🆔 [ENDPOINT_2] Unique ID: {unique_id}")

        # Encrypt token for GCSplit3
        encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
            unique_id=unique_id,
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            payout_network=payout_network,
            eth_amount=pure_market_eth_value
        )

        if not encrypted_token_for_split3:
            print(f"❌ [ENDPOINT_2] Failed to encrypt token for GCSplit3")
            abort(500, "Token encryption failed")

        # Enqueue Cloud Task to GCSplit3
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT_2] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        gcsplit3_queue = config.get('gcsplit3_queue')
        gcsplit3_url = config.get('gcsplit3_url')

        if not gcsplit3_queue or not gcsplit3_url:
            print(f"❌ [ENDPOINT_2] GCSplit3 configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_gcsplit3_swap_request(
            queue_name=gcsplit3_queue,
            target_url=gcsplit3_url,
            encrypted_token=encrypted_token_for_split3
        )

        if not task_name:
            print(f"❌ [ENDPOINT_2] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT_2] Successfully enqueued to GCSplit3")
        print(f"🆔 [ENDPOINT_2] Task: {task_name}")

        return jsonify({
            "status": "success",
            "message": "Estimate processed and swap request enqueued",
            "unique_id": unique_id,
            "task_id": task_name
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT_2] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


# ============================================================================
# ENDPOINT 3: POST /eth-client-swap - Receives swap result from GCSplit3
# ============================================================================

@app.route("/eth-client-swap", methods=["POST"])
def receive_eth_client_swap():
    """
    Endpoint for receiving ETH→ClientCurrency swap response from GCSplit3.

    Flow:
    1. Decrypt token from GCSplit3
    2. Insert into split_payout_que table
    3. Build GCHostPay token
    4. Enqueue Cloud Task to GCHostPay

    Returns:
        JSON response with status
    """
    try:
        print(f"🎯 [ENDPOINT_3] ETH→Client swap received (from GCSplit3)")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [ENDPOINT_3] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        encrypted_token = request_data.get('token')
        if not encrypted_token:
            print(f"❌ [ENDPOINT_3] Missing token")
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            print(f"❌ [ENDPOINT_3] Token manager not available")
            abort(500, "Service configuration error")

        decrypted_data = token_manager.decrypt_gcsplit3_to_gcsplit1_token(encrypted_token)
        if not decrypted_data:
            print(f"❌ [ENDPOINT_3] Failed to decrypt token")
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
        from_amount = decrypted_data['from_amount']
        to_amount = decrypted_data['to_amount']
        payin_address = decrypted_data['payin_address']
        payout_address = decrypted_data['payout_address']
        refund_address = decrypted_data['refund_address']
        flow = decrypted_data['flow']
        type_ = decrypted_data['type']

        print(f"🆔 [ENDPOINT_3] Unique ID: {unique_id}")
        print(f"🆔 [ENDPOINT_3] ChangeNow API ID: {cn_api_id}")
        print(f"👤 [ENDPOINT_3] User ID: {user_id}")
        print(f"💰 [ENDPOINT_3] From: {from_amount} {from_currency.upper()}")
        print(f"💰 [ENDPOINT_3] To: {to_amount} {to_currency.upper()}")

        # Insert into split_payout_que table
        if not database_manager:
            print(f"❌ [ENDPOINT_3] Database manager not available")
            abort(500, "Database unavailable")

        print(f"💾 [ENDPOINT_3] Inserting into split_payout_que")

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
            type_=type_
        )

        if not que_success:
            print(f"❌ [ENDPOINT_3] Failed to insert into split_payout_que")
            abort(500, "Database insertion failed")

        print(f"✅ [ENDPOINT_3] Database insertion successful")
        print(f"🔗 [ENDPOINT_3] Linked to split_payout_request via unique_id: {unique_id}")

        # Build GCHostPay token
        tps_hostpay_signing_key = config.get('tps_hostpay_signing_key')
        if not tps_hostpay_signing_key:
            print(f"❌ [ENDPOINT_3] HostPay signing key not available")
            abort(500, "HostPay configuration missing")

        hostpay_token = build_hostpay_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            from_currency=from_currency,
            from_network=from_network,
            from_amount=from_amount,
            payin_address=payin_address,
            signing_key=tps_hostpay_signing_key
        )

        if not hostpay_token:
            print(f"❌ [ENDPOINT_3] Failed to build HostPay token")
            abort(500, "HostPay token generation failed")

        # Enqueue Cloud Task to GCHostPay
        if not cloudtasks_client:
            print(f"❌ [ENDPOINT_3] Cloud Tasks client not available")
            abort(500, "Cloud Tasks unavailable")

        hostpay_queue = config.get('hostpay_queue')
        hostpay_webhook_url = config.get('hostpay_webhook_url')

        if not hostpay_queue or not hostpay_webhook_url:
            print(f"❌ [ENDPOINT_3] HostPay configuration missing")
            abort(500, "Service configuration error")

        task_name = cloudtasks_client.enqueue_hostpay_trigger(
            queue_name=hostpay_queue,
            target_url=hostpay_webhook_url,
            encrypted_token=hostpay_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT_3] Failed to create Cloud Task")
            abort(500, "Failed to enqueue task")

        print(f"✅ [ENDPOINT_3] Successfully enqueued to GCHostPay")
        print(f"🆔 [ENDPOINT_3] Task: {task_name}")
        print(f"🎉 [ENDPOINT_3] Complete payment split workflow finished!")

        return jsonify({
            "status": "success",
            "message": "Swap processed and HostPay trigger enqueued",
            "unique_id": unique_id,
            "cn_api_id": cn_api_id,
            "task_id": task_name
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT_3] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
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
            "service": "GCSplit1-10-26 Orchestrator",
            "timestamp": int(time.time()),
            "components": {
                "database": "healthy" if db_healthy else "unhealthy",
                "token_manager": "healthy" if token_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200 if db_healthy else 503

    except Exception as e:
        print(f"❌ [HEALTH] Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCSplit1-10-26 Orchestrator",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    print(f"🚀 [APP] Starting GCSplit1-10-26 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
