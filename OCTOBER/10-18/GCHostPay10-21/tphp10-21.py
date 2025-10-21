#!/usr/bin/env python
"""
GCHostPay10-21: Host Wallet Payment Service
Google Cloud Run webhook service for automated ETH payments from host wallet to ChangeNow.
Receives encrypted tokens from TPS10-21 and executes ETH transfers.
"""
import os
import time
import struct
import base64
import hmac
import hashlib
from typing import Tuple, Optional
from flask import Flask, request, abort, jsonify
from google.cloud import secretmanager

# LIST OF ENVIRONMENT VARIABLES
# TPS_HOSTPAY_SIGNING_KEY: Path to signing key in Secret Manager (shared with GCSplit10-21)
# HOST_WALLET_ETH_ADDRESS: Path to host wallet ETH address in Secret Manager
# HOST_WALLET_PRIVATE_KEY: Path to host wallet private key in Secret Manager

app = Flask(__name__)

def fetch_secret(env_var_name: str, description: str = "") -> Optional[str]:
    """
    Fetch a secret from Google Cloud Secret Manager.

    Args:
        env_var_name: Environment variable containing the secret path
        description: Description for logging purposes

    Returns:
        Secret value or None if failed
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = os.getenv(env_var_name)
        if not secret_path:
            print(f"❌ [CONFIG] Environment variable {env_var_name} is not set")
            return None

        print(f"🔐 [CONFIG] Fetching {description or env_var_name}")
        response = client.access_secret_version(request={"name": secret_path})
        secret_value = response.payload.data.decode("UTF-8")

        print(f"✅ [CONFIG] Successfully fetched {description or env_var_name}")
        return secret_value

    except Exception as e:
        print(f"❌ [CONFIG] Error fetching {description or env_var_name}: {e}")
        return None

def fetch_tps_hostpay_signing_key() -> Optional[str]:
    """
    Fetch the TPS HostPay signing key from Secret Manager.

    Returns:
        TPS HostPay signing key or None if failed
    """
    return fetch_secret("TPS_HOSTPAY_SIGNING_KEY", "TPS HostPay signing key")

def fetch_host_wallet_address() -> Optional[str]:
    """
    Fetch the host wallet ETH address from Secret Manager.

    Returns:
        Host wallet ETH address or None if failed
    """
    return fetch_secret("HOST_WALLET_ETH_ADDRESS", "Host wallet ETH address")

def fetch_host_wallet_private_key() -> Optional[str]:
    """
    Fetch the host wallet private key from Secret Manager.

    Returns:
        Host wallet private key or None if failed
    """
    return fetch_secret("HOST_WALLET_PRIVATE_KEY", "Host wallet private key")

def decode_and_verify_hostpay_token(token: str, signing_key: str) -> Tuple[str, str, str, str, float, str]:
    """
    Decode and verify the HostPay token from TPS10-21.
    Token is valid for 1 minute from creation.

    Token Format (binary packed):
    - 16 bytes: unique_id (UTF-8, fixed length, padded with nulls)
    - 1 byte: cn_api_id length + variable bytes for cn_api_id
    - 1 byte: from_currency length + variable bytes for from_currency
    - 1 byte: from_network length + variable bytes for from_network
    - 8 bytes: from_amount (double precision float)
    - 1 byte: payin_address length + variable bytes for payin_address
    - 4 bytes: timestamp (unix timestamp as uint32)
    - 16 bytes: HMAC-SHA256 signature (truncated)

    Args:
        token: Base64 URL-safe encoded token
        signing_key: HMAC signing key

    Returns:
        Tuple of (unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address)

    Raises:
        ValueError: If token is invalid, expired, or signature verification fails
    """
    # Pad the token if base64 length is not a multiple of 4
    padding = '=' * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
    except Exception:
        raise ValueError("Invalid token: cannot decode base64")

    # Minimum size check: 16 (unique_id) + 1+1 (cn_api_id min) + 1+1 (currency min) + 1+1 (network min)
    #                     + 8 (amount) + 1+1 (address min) + 4 (timestamp) + 16 (signature) = 52 bytes minimum
    if len(raw) < 52:
        raise ValueError(f"Invalid token: too small (got {len(raw)}, minimum 52)")

    offset = 0

    # Parse fixed 16-byte unique_id
    unique_id_bytes = raw[offset:offset+16]
    unique_id = unique_id_bytes.rstrip(b'\x00').decode('utf-8')
    offset += 16

    # Parse variable-length cn_api_id
    if offset + 1 > len(raw):
        raise ValueError("Invalid token: missing cn_api_id length field")
    cn_api_id_len = raw[offset]
    offset += 1

    if offset + cn_api_id_len > len(raw):
        raise ValueError("Invalid token: incomplete cn_api_id")
    cn_api_id = raw[offset:offset+cn_api_id_len].decode('utf-8')
    offset += cn_api_id_len

    # Parse variable-length from_currency
    if offset + 1 > len(raw):
        raise ValueError("Invalid token: missing from_currency length field")
    from_currency_len = raw[offset]
    offset += 1

    if offset + from_currency_len > len(raw):
        raise ValueError("Invalid token: incomplete from_currency")
    from_currency = raw[offset:offset+from_currency_len].decode('utf-8')
    offset += from_currency_len

    # Parse variable-length from_network
    if offset + 1 > len(raw):
        raise ValueError("Invalid token: missing from_network length field")
    from_network_len = raw[offset]
    offset += 1

    if offset + from_network_len > len(raw):
        raise ValueError("Invalid token: incomplete from_network")
    from_network = raw[offset:offset+from_network_len].decode('utf-8')
    offset += from_network_len

    # Parse 8-byte double for amount
    if offset + 8 > len(raw):
        raise ValueError("Invalid token: incomplete from_amount")
    from_amount = struct.unpack(">d", raw[offset:offset+8])[0]
    offset += 8

    # Parse variable-length payin_address
    if offset + 1 > len(raw):
        raise ValueError("Invalid token: missing payin_address length field")
    payin_address_len = raw[offset]
    offset += 1

    if offset + payin_address_len > len(raw):
        raise ValueError("Invalid token: incomplete payin_address")
    payin_address = raw[offset:offset+payin_address_len].decode('utf-8')
    offset += payin_address_len

    # Parse 4-byte timestamp
    if offset + 4 > len(raw):
        raise ValueError("Invalid token: incomplete timestamp")
    timestamp = struct.unpack(">I", raw[offset:offset+4])[0]
    offset += 4

    # The remaining bytes should be the 16-byte truncated signature
    if len(raw) - offset != 16:
        raise ValueError(f"Invalid token: wrong signature size (got {len(raw) - offset}, expected 16)")

    data = raw[:offset]  # All data except signature
    sig = raw[offset:]   # The signature

    # Debug logs
    print(f"🔍 [TOKEN_DEBUG] Raw data size: {len(raw)} bytes")
    print(f"🔍 [TOKEN_DEBUG] Data size: {len(data)} bytes")
    print(f"🔍 [TOKEN_DEBUG] Signature size: {len(sig)} bytes")

    # Verify truncated signature
    expected_full_sig = hmac.new(signing_key.encode(), data, hashlib.sha256).digest()
    expected_sig = expected_full_sig[:16]  # Compare only first 16 bytes
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Signature mismatch - token may be tampered or invalid signing key")

    # Validate timestamp (1-minute window: current_time - 60 to current_time + 5)
    current_time = int(time.time())
    if not (current_time - 60 <= timestamp <= current_time + 5):
        time_diff = current_time - timestamp
        raise ValueError(f"Token expired (created {abs(time_diff)} seconds ago, max 60 seconds)")

    print(f"🔓 [TOKEN_VALIDATION] Token validated successfully")
    print(f"⏰ [TOKEN_VALIDATION] Token age: {current_time - timestamp} seconds")

    return unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address

@app.route("/", methods=["POST"])
def hostpay_webhook():
    """
    Main webhook endpoint for receiving HostPay requests from TPS10-21.
    """
    try:
        print(f"🎯 [HOSTPAY_WEBHOOK] Webhook called")

        # Parse JSON payload
        try:
            payload = request.get_json()
            if not payload:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [HOSTPAY_WEBHOOK] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        # Extract token
        token = payload.get('token')
        if not token:
            print(f"❌ [HOSTPAY_WEBHOOK] Missing token in payload")
            abort(400, "Missing token parameter")

        print(f"📦 [HOSTPAY_WEBHOOK] Received token (length: {len(token)} chars)")

        # Fetch signing key
        signing_key = fetch_tps_hostpay_signing_key()
        if not signing_key:
            print(f"❌ [HOSTPAY_WEBHOOK] Failed to fetch signing key")
            abort(500, "Configuration error: signing key not available")

        # Decode and verify token
        try:
            unique_id, cn_api_id, from_currency, from_network, from_amount, payin_address = decode_and_verify_hostpay_token(
                token, signing_key
            )
        except ValueError as e:
            print(f"❌ [HOSTPAY_WEBHOOK] Token validation failed: {e}")
            abort(400, f"Invalid token: {str(e)}")
        except Exception as e:
            print(f"❌ [HOSTPAY_WEBHOOK] Token decoding error: {e}")
            abort(500, f"Token processing error: {str(e)}")

        # Log extracted values
        print(f"✅ [HOSTPAY_WEBHOOK] Token validated and decoded successfully")
        print(f"")
        print(f"📦 [HOSTPAY_WEBHOOK] Extracted values:")
        print(f"   🆔 unique_id: {unique_id}")
        print(f"   🆔 cn_api_id: {cn_api_id}")
        print(f"   💰 from_currency: {from_currency}")
        print(f"   🌐 from_network: {from_network}")
        print(f"   💸 from_amount: {from_amount}")
        print(f"   🏦 payin_address: {payin_address}")
        print(f"")

        # TODO: Implement Web3 ETH transfer logic here
        print(f"⚠️ [HOSTPAY_WEBHOOK] ETH transfer not yet implemented")
        print(f"💡 [HOSTPAY_WEBHOOK] Next step: Send {from_amount} {from_currency.upper()} to {payin_address}")

        # Return success response
        return jsonify({
            "status": "success",
            "message": "Token validated and payload extracted successfully",
            "data": {
                "unique_id": unique_id,
                "cn_api_id": cn_api_id,
                "from_currency": from_currency,
                "from_network": from_network,
                "from_amount": from_amount,
                "payin_address": payin_address
            },
            "note": "ETH transfer functionality to be implemented"
        }), 200

    except Exception as e:
        print(f"❌ [HOSTPAY_WEBHOOK] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Webhook processing error: {str(e)}"
        }), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Test signing key availability
        signing_key = fetch_tps_hostpay_signing_key()
        signing_key_available = signing_key is not None

        return jsonify({
            "status": "healthy",
            "service": "GCHostPay10-21 Host Wallet Payment Service",
            "timestamp": int(time.time()),
            "configuration": {
                "signing_key": "✅" if signing_key_available else "❌"
            }
        }), 200
    except Exception as e:
        print(f"❌ [HEALTH_CHECK] Error: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "GCHostPay10-21 Host Wallet Payment Service",
            "error": str(e)
        }), 503

# --- Flask entrypoint for deployment ---
if __name__ == "__main__":
    print("🚀 [HOSTPAY] Starting GCHostPay10-21 Host Wallet Payment Service")
    print("📡 [HOSTPAY] Listening on port 8080")
    app.run(host="0.0.0.0", port=8080)
