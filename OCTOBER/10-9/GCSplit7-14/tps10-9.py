#!/usr/bin/env python
"""
TPS10-9: ChangeNow Payment Splitting Service
Google Cloud Function for automated cryptocurrency payment splitting using ChangeNow API.
Converts ETH payments to client payout currencies after successful subscription payments.
"""
import os
import json
import time
import hmac
import hashlib
import asyncio
from typing import Dict, Any, Optional, Tuple
from flask import Flask, request, abort, jsonify
from config_manager import ConfigManager
from changenow_client import ChangeNowClient

app = Flask(__name__)

# Initialize managers
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize ChangeNow client
changenow_client = ChangeNowClient(config.get('changenow_api_key'))

def verify_webhook_signature(payload: bytes, signature: str, signing_key: str) -> bool:
    """
    Verify webhook signature from tph7-14.py to ensure authentic requests.
    
    Args:
        payload: Raw request payload
        signature: Provided signature
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

def validate_changenow_pair(from_currency: str, to_currency: str) -> bool:
    """
    Validate that the currency pair is supported by ChangeNow.
    
    Args:
        from_currency: Source currency (ETH)
        to_currency: Target currency
        
    Returns:
        True if pair is supported, False otherwise
    """
    try:
        print(f"🔍 [CHANGENOW_PAIR_CHECK] Validating {from_currency.upper()} → {to_currency.upper()}")
        
        available_pairs = changenow_client.get_available_pairs()
        if not available_pairs:
            print(f"❌ [CHANGENOW_PAIR_CHECK] Failed to fetch available pairs")
            return False
            
        # Check if the pair exists in available pairs
        pair_key = f"{from_currency.lower()}_{to_currency.lower()}"
        reverse_pair_key = f"{to_currency.lower()}_{from_currency.lower()}"
        
        # ChangeNow may list pairs in either direction
        pair_exists = any(
            pair_key in pair.lower() or reverse_pair_key in pair.lower()
            for pair in available_pairs
        )
        
        if pair_exists:
            print(f"✅ [CHANGENOW_PAIR_CHECK] Pair {from_currency.upper()} → {to_currency.upper()} is supported")
            return True
        else:
            print(f"❌ [CHANGENOW_PAIR_CHECK] Pair {from_currency.upper()} → {to_currency.upper()} not supported")
            return False
            
    except Exception as e:
        print(f"❌ [CHANGENOW_PAIR_CHECK] Error validating pair: {e}")
        return False

def check_amount_limits(from_currency: str, to_currency: str, amount: float) -> Tuple[bool, Optional[Dict]]:
    """
    Check if the amount falls within ChangeNow's min/max limits for the pair.
    
    Args:
        from_currency: Source currency
        to_currency: Target currency
        amount: Amount to check
        
    Returns:
        Tuple of (is_valid, limits_info)
    """
    try:
        print(f"💰 [CHANGENOW_LIMITS] Checking limits for {amount} {from_currency.upper()} → {to_currency.upper()}")
        
        limits = changenow_client.get_exchange_limits(from_currency, to_currency)
        if not limits:
            print(f"❌ [CHANGENOW_LIMITS] Failed to fetch limits")
            return False, None
            
        min_amount = limits.get('minAmount', 0)
        max_amount = limits.get('maxAmount', float('inf'))
        
        print(f"📊 [CHANGENOW_LIMITS] Min: {min_amount}, Max: {max_amount}, Amount: {amount}")
        
        if amount < min_amount:
            print(f"❌ [CHANGENOW_LIMITS] Amount {amount} below minimum {min_amount}")
            return False, limits
        elif amount > max_amount:
            print(f"❌ [CHANGENOW_LIMITS] Amount {amount} above maximum {max_amount}")
            return False, limits
        else:
            print(f"✅ [CHANGENOW_LIMITS] Amount {amount} within valid range")
            return True, limits
            
    except Exception as e:
        print(f"❌ [CHANGENOW_LIMITS] Error checking limits: {e}")
        return False, None

def create_fixed_rate_transaction(from_amount: float, from_currency: str, to_currency: str, 
                                wallet_address: str, user_id: int) -> Optional[Dict]:
    """
    Create a fixed-rate transaction with ChangeNow.
    
    Args:
        from_amount: Amount to exchange
        from_currency: Source currency
        to_currency: Target currency
        wallet_address: Recipient wallet address
        user_id: User ID for tracking
        
    Returns:
        Transaction data or None if failed
    """
    try:
        print(f"🚀 [CHANGENOW_SWAP] Starting fixed-rate transaction")
        print(f"💰 [CHANGENOW_SWAP] {from_amount} {from_currency.upper()} → {to_currency.upper()}")
        print(f"🏦 [CHANGENOW_SWAP] Target wallet: {wallet_address}")
        
        # Get estimated exchange amount first
        estimated = changenow_client.get_estimated_exchange_amount(from_amount, from_currency, to_currency)
        if estimated:
            print(f"📈 [CHANGENOW_SWAP] Estimated receive: {estimated.get('toAmount', 'Unknown')} {to_currency.upper()}")
        
        # Create the fixed-rate transaction
        transaction = changenow_client.create_fixed_rate_transaction(
            from_currency=from_currency,
            to_currency=to_currency,
            from_amount=from_amount,
            address=wallet_address,
            user_id=str(user_id)
        )
        
        if transaction:
            transaction_id = transaction.get('id', 'Unknown')
            payin_address = transaction.get('payinAddress', 'Unknown')
            payin_extra_id = transaction.get('payinExtraId', '')
            expected_amount = transaction.get('fromAmount', from_amount)
            
            print(f"✅ [CHANGENOW_SWAP] Transaction created successfully")
            print(f"🆔 [CHANGENOW_SWAP] Transaction ID: {transaction_id}")
            print(f"🏦 [CHANGENOW_SWAP] Deposit Address: {payin_address}")
            if payin_extra_id:
                print(f"🔖 [CHANGENOW_SWAP] Extra ID: {payin_extra_id}")
            print(f"💰 [CHANGENOW_SWAP] Required Deposit: {expected_amount} {from_currency.upper()}")
            print(f"🎯 [CHANGENOW_SWAP] Destination: {wallet_address} ({to_currency.upper()})")
            
            # Log deposit information for customer funding
            print(f"\n" + "="*60)
            print(f"📋 [CUSTOMER_FUNDING_INFO] Payment Split Instructions")
            print(f"🏦 Send exactly {expected_amount} {from_currency.upper()} to: {payin_address}")
            if payin_extra_id:
                print(f"🔖 Include Extra ID: {payin_extra_id}")
            print(f"🎯 Funds will be converted and sent to: {wallet_address}")
            print(f"💰 You will receive approximately {estimated.get('toAmount', 'TBD')} {to_currency.upper()}")
            print(f"⏰ Transaction ID: {transaction_id}")
            print(f"="*60 + "\n")
            
            return transaction
        else:
            print(f"❌ [CHANGENOW_SWAP] Failed to create transaction")
            return None
            
    except Exception as e:
        print(f"❌ [CHANGENOW_SWAP] Error creating transaction: {e}")
        return None

def process_payment_split(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main processing function for payment splitting workflow.
    
    Args:
        webhook_data: Data received from tph7-14.py webhook
        
    Returns:
        Processing result dictionary
    """
    try:
        # Extract required data
        user_id = webhook_data.get('user_id')
        wallet_address = webhook_data.get('wallet_address', '').strip()
        payout_currency = webhook_data.get('payout_currency', '').strip().lower()
        sub_price = webhook_data.get('sub_price')
        
        print(f"🔄 [PAYMENT_SPLITTING] Starting Client Payout")
        print(f"👤 [PAYMENT_SPLITTING] User ID: {user_id}")
        print(f"💰 [PAYMENT_SPLITTING] Amount: {sub_price} ETH")
        print(f"🏦 [PAYMENT_SPLITTING] Target: {wallet_address} ({payout_currency.upper()})")
        
        # Validate required fields
        if not all([user_id, wallet_address, payout_currency, sub_price]):
            return {
                "success": False,
                "error": "Missing required fields",
                "details": {
                    "user_id": bool(user_id),
                    "wallet_address": bool(wallet_address),
                    "payout_currency": bool(payout_currency),
                    "sub_price": bool(sub_price)
                }
            }
        
        try:
            sub_price = float(sub_price)
        except (ValueError, TypeError):
            return {
                "success": False,
                "error": "Invalid subscription price format"
            }
        
        # Step 1: Validate currency pair
        if not validate_changenow_pair("eth", payout_currency):
            return {
                "success": False,
                "error": f"Currency pair ETH → {payout_currency.upper()} not supported by ChangeNow"
            }
        
        # Step 2: Check amount limits
        amount_valid, limits_info = check_amount_limits("eth", payout_currency, sub_price)
        if not amount_valid:
            return {
                "success": False,
                "error": "Amount outside acceptable limits",
                "limits": limits_info
            }
        
        # Step 3: Create fixed-rate transaction
        transaction = create_fixed_rate_transaction(
            from_amount=sub_price,
            from_currency="eth",
            to_currency=payout_currency,
            wallet_address=wallet_address,
            user_id=user_id
        )

        if transaction:
            print(f"✅ [PAYMENT_SPLITTING] Completed successfully")

            # Step 4: Send Telegram notification
            telegram_bot_token = config.get('telegram_bot_token')
            if telegram_bot_token:
                try:
                    # Run async Telegram notification
                    asyncio.run(changenow_client.send_telegram_notification(
                        bot_token=telegram_bot_token,
                        transaction_data=transaction
                    ))
                except Exception as telegram_error:
                    print(f"⚠️ [TELEGRAM] Failed to send notification (non-fatal): {telegram_error}")
            else:
                print(f"⚠️ [TELEGRAM] Bot token not configured, skipping notification")

            return {
                "success": True,
                "transaction_id": transaction.get('id'),
                "payin_address": transaction.get('payinAddress'),
                "payin_extra_id": transaction.get('payinExtraId'),
                "expected_amount": transaction.get('fromAmount'),
                "currency": "ETH"
            }
        else:
            return {
                "success": False,
                "error": "Failed to create ChangeNow transaction"
            }
            
    except Exception as e:
        print(f"❌ [PAYMENT_SPLITTING] Error processing payment split: {e}")
        return {
            "success": False,
            "error": f"Processing error: {str(e)}"
        }

@app.route("/", methods=["POST"])
def payment_split_webhook():
    """
    Main webhook endpoint for receiving payment split requests from tph7-14.py.
    """
    try:
        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get('X-Webhook-Signature', '')
        
        print(f"🎯 [WEBHOOK] TPS10-9 Webhook Called")
        print(f"📦 [WEBHOOK] Payload size: {len(payload)} bytes")
        
        # Verify webhook signature if signing key is available
        signing_key = config.get('webhook_signing_key')
        if signing_key and not verify_webhook_signature(payload, signature, signing_key):
            print(f"❌ [WEBHOOK] Invalid signature")
            abort(401, "Invalid webhook signature")
        
        # Parse JSON payload
        try:
            webhook_data = request.get_json()
            if not webhook_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [WEBHOOK] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")
        
        print(f"📝 [WEBHOOK] Processing payment split request")
        
        # Process the payment split
        result = process_payment_split(webhook_data)
        
        if result["success"]:
            print(f"✅ [WEBHOOK] Payment split completed successfully")
            return jsonify({
                "status": "success",
                "message": "Payment split processed",
                "data": result
            }), 200
        else:
            print(f"❌ [WEBHOOK] Payment split failed: {result.get('error')}")
            return jsonify({
                "status": "error",
                "message": result.get("error"),
                "details": result.get("details", {})
            }), 400
            
    except Exception as e:
        print(f"❌ [WEBHOOK] Webhook processing error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Webhook error: {str(e)}"
        }), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "TPS10-9 Payment Splitting",
        "timestamp": int(time.time())
    }), 200

# --- Flask entrypoint for deployment ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)