#!/usr/bin/env python
"""
TPS10-21: ChangeNow Payment Splitting Service
Google Cloud Function for automated cryptocurrency payment splitting using ChangeNow API.
Converts ETH payments to client payout currencies after successful subscription payments.
"""
import os
import json
import time
import hmac
import hashlib
import asyncio
import struct
import base64
import requests
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from flask import Flask, request, abort, jsonify
from config_manager import ConfigManager
from changenow_client import ChangeNowClient
from database_manager import DatabaseManager

app = Flask(__name__)

# Initialize managers
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize ChangeNow client
changenow_client = ChangeNowClient(config.get('changenow_api_key'))

# Initialize Database manager
database_manager = DatabaseManager()

def verify_webhook_signature(payload: bytes, signature: str, signing_key: str) -> bool:
    """
    Verify webhook signature from tph10-16.py to ensure authentic requests.
    Uses SUCCESS_URL_SIGNING_KEY (shared with tph10-16) for signature verification.

    Args:
        payload: Raw request payload
        signature: Provided signature (HMAC-SHA256 hexdigest)
        signing_key: Secret signing key (SUCCESS_URL_SIGNING_KEY)

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

def build_hostpay_token(unique_id: str, cn_api_id: str, from_currency: str,
                       from_network: str, from_amount: float, payin_address: str,
                       signing_key: str) -> Optional[str]:
    """
    Build a cryptographically signed token for GCHostPay10-21 webhook.
    Token is valid for 1 minute from creation.

    Token Format (binary packed):
    - 16 bytes: unique_id (UTF-8, fixed length, padded with nulls if shorter)
    - 1 byte: cn_api_id length + variable bytes for cn_api_id
    - 1 byte: from_currency length + variable bytes for from_currency
    - 1 byte: from_network length + variable bytes for from_network
    - 8 bytes: from_amount (double precision float)
    - 1 byte: payin_address length + variable bytes for payin_address
    - 4 bytes: timestamp (unix timestamp as uint32)
    - 16 bytes: HMAC-SHA256 signature (truncated)

    Args:
        unique_id: Database unique ID (16 chars max)
        cn_api_id: ChangeNow transaction ID
        from_currency: Source currency (e.g., "eth")
        from_network: Source network (e.g., "eth")
        from_amount: Amount to send
        payin_address: ChangeNow deposit address
        signing_key: HMAC signing key

    Returns:
        Base64 URL-safe encoded token or None if failed
    """
    try:
        print(f"🔐 [HOSTPAY_TOKEN] Building HostPay webhook token")

        # Prepare unique_id (fixed 16 bytes, padded with nulls if shorter)
        unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')

        # Encode string fields to UTF-8
        cn_api_id_bytes = cn_api_id.encode('utf-8')
        from_currency_bytes = from_currency.lower().encode('utf-8')
        from_network_bytes = from_network.lower().encode('utf-8')
        payin_address_bytes = payin_address.encode('utf-8')

        # Get current timestamp
        current_timestamp = int(time.time())

        # Build packed data
        packed_data = bytearray()

        # Fixed 16-byte unique_id
        packed_data.extend(unique_id_bytes)

        # Variable length fields with 1-byte length prefix
        packed_data.append(len(cn_api_id_bytes))
        packed_data.extend(cn_api_id_bytes)

        packed_data.append(len(from_currency_bytes))
        packed_data.extend(from_currency_bytes)

        packed_data.append(len(from_network_bytes))
        packed_data.extend(from_network_bytes)

        # 8-byte double for amount
        packed_data.extend(struct.pack(">d", from_amount))

        # Payin address
        packed_data.append(len(payin_address_bytes))
        packed_data.extend(payin_address_bytes)

        # 4-byte timestamp
        packed_data.extend(struct.pack(">I", current_timestamp))

        # Generate HMAC signature
        full_signature = hmac.new(signing_key.encode(), bytes(packed_data), hashlib.sha256).digest()
        truncated_signature = full_signature[:16]  # First 16 bytes

        # Combine data + signature
        final_data = bytes(packed_data) + truncated_signature

        # Base64 URL-safe encode
        token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

        print(f"✅ [HOSTPAY_TOKEN] Token generated successfully")
        print(f"🆔 [HOSTPAY_TOKEN] Unique ID: {unique_id}")
        print(f"🆔 [HOSTPAY_TOKEN] CN API ID: {cn_api_id}")
        print(f"💰 [HOSTPAY_TOKEN] Amount: {from_amount} {from_currency.upper()}")
        print(f"🌐 [HOSTPAY_TOKEN] Network: {from_network}")
        print(f"🏦 [HOSTPAY_TOKEN] Payin Address: {payin_address}")
        print(f"⏰ [HOSTPAY_TOKEN] Timestamp: {current_timestamp}")
        print(f"🔐 [HOSTPAY_TOKEN] Token size: {len(token)} chars")

        return token

    except Exception as e:
        print(f"❌ [HOSTPAY_TOKEN] Error building token: {e}")
        return None

def trigger_hostpay_webhook(unique_id: str, cn_api_id: str, from_currency: str,
                           from_network: str, from_amount: float, payin_address: str) -> bool:
    """
    Trigger the GCHostPay10-21 webhook with encrypted token.

    Args:
        unique_id: Database unique ID
        cn_api_id: ChangeNow transaction ID
        from_currency: Source currency
        from_network: Source network
        from_amount: Amount to send
        payin_address: ChangeNow deposit address

    Returns:
        True if webhook triggered successfully, False otherwise
    """
    try:
        # Get configuration
        hostpay_webhook_url = config.get('hostpay_webhook_url')
        signing_key = config.get('tps_hostpay_signing_key')

        if not hostpay_webhook_url:
            print(f"⚠️ [HOSTPAY_WEBHOOK] HostPay webhook URL not configured, skipping")
            return False

        if not signing_key:
            print(f"❌ [HOSTPAY_WEBHOOK] TPS HostPay signing key not available")
            return False

        # Build token
        token = build_hostpay_token(
            unique_id=unique_id,
            cn_api_id=cn_api_id,
            from_currency=from_currency,
            from_network=from_network,
            from_amount=from_amount,
            payin_address=payin_address,
            signing_key=signing_key
        )

        if not token:
            print(f"❌ [HOSTPAY_WEBHOOK] Failed to build token")
            return False

        print(f"🚀 [HOSTPAY_WEBHOOK] Triggering GCHostPay10-21 webhook")
        print(f"🌐 [HOSTPAY_WEBHOOK] URL: {hostpay_webhook_url}")

        # Prepare request payload
        payload = {
            "token": token
        }

        # Send webhook request
        response = requests.post(
            hostpay_webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        if response.status_code == 200:
            print(f"✅ [HOSTPAY_WEBHOOK] Webhook triggered successfully")
            try:
                response_data = response.json()
                print(f"📦 [HOSTPAY_WEBHOOK] Response: {response_data}")
            except:
                pass
            return True
        else:
            print(f"❌ [HOSTPAY_WEBHOOK] Webhook failed with status {response.status_code}: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print(f"❌ [HOSTPAY_WEBHOOK] Request timeout")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ [HOSTPAY_WEBHOOK] Connection error")
        return False
    except Exception as e:
        print(f"❌ [HOSTPAY_WEBHOOK] Error triggering webhook: {e}")
        return False

def create_fixed_rate_transaction(to_amount: float, from_currency: str, to_currency: str,
                                wallet_address: str, user_id: int, unique_id: str = None,
                                closed_channel_id: str = None, from_network: str = "eth",
                                to_network: str = "eth") -> Optional[Dict]:
    """
    Create a fixed-rate transaction with ChangeNow and save to split_payout_que table.

    Args:
        to_amount: Expected amount to receive (from ChangeNow estimate)
        from_currency: Source currency
        to_currency: Target currency
        wallet_address: Recipient wallet address
        user_id: User ID for tracking
        unique_id: Unique ID from split_payout_request (for linking tables)
        closed_channel_id: Channel ID from webhook
        from_network: Source network (default "eth")
        to_network: Target network (default "eth")

    Returns:
        Transaction data or None if failed
    """
    try:
        print(f"🚀 [CHANGENOW_SWAP] Starting fixed-rate transaction")
        print(f"💰 [CHANGENOW_SWAP] Expected to receive: {to_amount} {to_currency.upper()}")
        print(f"🏦 [CHANGENOW_SWAP] Target wallet: {wallet_address}")
        if unique_id:
            print(f"🆔 [CHANGENOW_SWAP] Unique ID (for linking): {unique_id}")

        # Create the fixed-rate transaction using to_amount from estimate
        transaction = changenow_client.create_fixed_rate_transaction(
            from_currency=from_currency,
            to_currency=to_currency,
            from_amount=to_amount,
            address=wallet_address,
            user_id=str(user_id)
        )

        if transaction:
            transaction_id = transaction.get('id', 'Unknown')
            payin_address = transaction.get('payinAddress', 'Unknown')
            payin_extra_id = transaction.get('payinExtraId', '')
            expected_amount = transaction.get('fromAmount', '')

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
            print(f"💰 You will receive approximately {to_amount} {to_currency.upper()}")
            print(f"⏰ Transaction ID: {transaction_id}")
            print(f"="*60 + "\n")

            # Save to split_payout_que table if unique_id is provided
            if unique_id and user_id and closed_channel_id:
                print(f"💾 [CHANGENOW_SWAP] Saving transaction to split_payout_que table")

                try:
                    # Extract data from API response
                    cn_api_id = transaction.get('id', '')
                    api_from_amount = float(transaction.get('fromAmount', 0))
                    api_to_amount = float(transaction.get('toAmount', 0))
                    api_from_currency = transaction.get('fromCurrency', from_currency)
                    api_to_currency = transaction.get('toCurrency', to_currency)
                    api_from_network = transaction.get('fromNetwork', from_network)
                    api_to_network = transaction.get('toNetwork', to_network)
                    api_payin_address = transaction.get('payinAddress', '')
                    api_payout_address = transaction.get('payoutAddress', wallet_address)
                    api_refund_address = transaction.get('refundAddress', '')
                    api_flow = transaction.get('flow', 'standard')
                    api_type = transaction.get('type', 'direct')

                    print(f"🆔 [CHANGENOW_SWAP] Extracted ChangeNow API ID: {cn_api_id}")

                    # Insert into split_payout_que table
                    que_success = database_manager.insert_split_payout_que(
                        unique_id=unique_id,
                        cn_api_id=cn_api_id,
                        user_id=user_id,
                        closed_channel_id=closed_channel_id,
                        from_currency=api_from_currency,
                        to_currency=api_to_currency,
                        from_network=api_from_network,
                        to_network=api_to_network,
                        from_amount=api_from_amount,
                        to_amount=api_to_amount,
                        payin_address=api_payin_address,
                        payout_address=api_payout_address,
                        refund_address=api_refund_address,
                        flow=api_flow,
                        type_=api_type
                    )

                    if que_success:
                        print(f"✅ [CHANGENOW_SWAP] Successfully saved to split_payout_que")
                        print(f"🔗 [CHANGENOW_SWAP] Both tables linked with unique_id: {unique_id}")

                        # Trigger HostPay webhook for automated payment
                        print(f"🚀 [CHANGENOW_SWAP] Triggering HostPay webhook for automated ETH transfer")
                        try:
                            hostpay_triggered = trigger_hostpay_webhook(
                                unique_id=unique_id,
                                cn_api_id=cn_api_id,
                                from_currency=api_from_currency,
                                from_network=api_from_network,
                                from_amount=api_from_amount,
                                payin_address=api_payin_address
                            )
                            if hostpay_triggered:
                                print(f"✅ [CHANGENOW_SWAP] HostPay webhook triggered successfully")
                            else:
                                print(f"⚠️ [CHANGENOW_SWAP] HostPay webhook trigger failed (non-fatal)")
                        except Exception as webhook_error:
                            print(f"❌ [CHANGENOW_SWAP] Error triggering HostPay webhook: {webhook_error}")
                    else:
                        print(f"⚠️ [CHANGENOW_SWAP] Failed to save to split_payout_que (non-fatal)")

                except Exception as db_error:
                    print(f"❌ [CHANGENOW_SWAP] Database error saving to split_payout_que: {db_error}")
                    print(f"⚠️ [CHANGENOW_SWAP] Transaction created but not saved to que table (non-fatal)")
            else:
                print(f"⚠️ [CHANGENOW_SWAP] Skipping split_payout_que insertion - missing unique_id or user_id or closed_channel_id")

            return transaction
        else:
            print(f"❌ [CHANGENOW_SWAP] Failed to create transaction")
            return None

    except Exception as e:
        print(f"❌ [CHANGENOW_SWAP] Error creating transaction: {e}")
        return None

def calculate_adjusted_amount(subscription_price: str, tp_flat_fee: str) -> Tuple[float, float]:
    """
    Calculate the adjusted amount after removing TP flat fee.

    Args:
        subscription_price: Original subscription price as string (e.g., "15.00")
        tp_flat_fee: TP flat fee percentage as string (e.g., "3" for 3%)

    Returns:
        Tuple of (original_amount, adjusted_amount)
    """
    try:
        # Convert to Decimal for precise calculation
        original_amount = Decimal(subscription_price)
        fee_percentage = Decimal(tp_flat_fee if tp_flat_fee else "3")  # Default to 3%

        # Calculate fee amount
        fee_amount = original_amount * (fee_percentage / Decimal("100"))

        # Calculate adjusted amount
        adjusted_amount = original_amount - fee_amount

        print(f"💰 [FEE_CALCULATION] Original amount: ${original_amount}")
        print(f"📊 [FEE_CALCULATION] TP flat fee: {fee_percentage}%")
        print(f"💸 [FEE_CALCULATION] Fee amount: ${fee_amount}")
        print(f"✅ [FEE_CALCULATION] Adjusted amount: ${adjusted_amount}")

        return (float(original_amount), float(adjusted_amount))

    except Exception as e:
        print(f"❌ [FEE_CALCULATION] Error calculating adjusted amount: {e}")
        # Return original amount if calculation fails
        return (float(subscription_price), float(subscription_price))

def get_estimated_conversion_and_save(user_id: int, closed_channel_id: str,
                                     wallet_address: str, payout_currency: str,
                                     subscription_price: str) -> Optional[Dict[str, Any]]:
    """
    Get estimated conversion from ChangeNow API and save to database.

    Flow:
    1. Calculate adjusted amount (subscription_price - TP_FLAT_FEE)
    2. Call ChangeNow API v2 estimated-amount endpoint
    3. Extract toAmount from response
    4. Insert record into split_payout_request table

    Args:
        user_id: User ID from webhook
        closed_channel_id: Channel ID from webhook
        wallet_address: Client wallet address from webhook
        payout_currency: Client payout currency from webhook
        subscription_price: Subscription price from webhook

    Returns:
        Dictionary with estimate data and unique_id, or None if failed
    """
    try:
        print(f"🔄 [ESTIMATE_AND_SAVE] Starting conversion estimate workflow")

        # Step 1: Calculate adjusted amount after TP flat fee
        tp_flat_fee = config.get('tp_flat_fee')
        original_amount, adjusted_amount = calculate_adjusted_amount(subscription_price, tp_flat_fee)

        # Step 1.5: Look up the network for the target currency from database
        to_network = database_manager.get_network_for_currency(payout_currency.upper())
        if not to_network:
            print(f"❌ [ESTIMATE_AND_SAVE] Failed to lookup network for currency {payout_currency}")
            print(f"💡 [ESTIMATE_AND_SAVE] Ensure to_currency_to_network table has entry for '{payout_currency.upper()}'")
            return None

        print(f"🌐 [ESTIMATE_AND_SAVE] Using network '{to_network}' for currency '{payout_currency.upper()}'")

        # Step 2: Call ChangeNow API v2 for estimated amount
        print(f"🌐 [ESTIMATE_AND_SAVE] Calling ChangeNow API for estimate")

        estimate_response = changenow_client.get_estimated_amount_v2(
            from_currency="usdt",
            ### to_currency=payout_currency.lower(),
            to_currency="eth",
            from_network="eth",
            ### to_network=to_network.lower(),  # Dynamic from database
            to_network="eth",
            from_amount=str(adjusted_amount),
            flow="standard",
            type_="direct"
        )

        if not estimate_response:
            print(f"❌ [ESTIMATE_AND_SAVE] Failed to get estimate from ChangeNow API")
            return None

        # Step 3: Extract data from response
        to_amount = estimate_response.get('toAmount')
        from_amount = estimate_response.get('fromAmount')
        deposit_fee = estimate_response.get('depositFee', 0)
        withdrawal_fee = estimate_response.get('withdrawalFee', 0)

        print(f"📊 [ESTIMATE_AND_SAVE] Estimate details:")
        print(f"   From Amount: {from_amount} USDT")
        print(f"   To Amount: {to_amount} {payout_currency.upper()}")
        print(f"   Deposit Fee: {deposit_fee}")
        print(f"   Withdrawal Fee: {withdrawal_fee}")

        # Step 4: Insert into split_payout_request table
        print(f"💾 [ESTIMATE_AND_SAVE] Inserting into database")

        unique_id = database_manager.insert_split_payout_request(
            user_id=user_id,
            closed_channel_id=str(closed_channel_id),
            from_currency="usdt",
            to_currency=payout_currency.lower(),
            from_network="eth",
            to_network=to_network.lower(),  # Dynamic from database lookup
            from_amount=float(from_amount),
            to_amount=float(to_amount),
            client_wallet_address=wallet_address,
            refund_address="",  # Empty for now as specified
            flow="standard",
            type_="direct"
        )

        if not unique_id:
            print(f"❌ [ESTIMATE_AND_SAVE] Failed to insert into database")
            return None

        print(f"✅ [ESTIMATE_AND_SAVE] Successfully completed workflow")
        print(f"🆔 [ESTIMATE_AND_SAVE] Unique ID: {unique_id}")

        return {
            "unique_id": unique_id,
            "original_subscription_price": original_amount,
            "adjusted_amount": adjusted_amount,
            "tp_flat_fee_percentage": tp_flat_fee,
            "from_amount": from_amount,
            "to_amount": to_amount,
            "from_currency": "usdt",
            "to_currency": payout_currency.lower(),
            "deposit_fee": deposit_fee,
            "withdrawal_fee": withdrawal_fee,
            "wallet_address": wallet_address
        }

    except Exception as e:
        print(f"❌ [ESTIMATE_AND_SAVE] Error in workflow: {e}")
        return None

def process_payment_split(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main processing function for payment splitting workflow.

    Args:
        webhook_data: Data received from tph10-16.py webhook
        
    Returns:
        Processing result dictionary
    """
    try:
        # Extract required data
        user_id = webhook_data.get('user_id')
        closed_channel_id = webhook_data.get('closed_channel_id')
        wallet_address = webhook_data.get('wallet_address', '').strip()
        payout_currency = webhook_data.get('payout_currency', '').strip().lower()
        sub_price = webhook_data.get('subscription_price') or webhook_data.get('sub_price')

        print(f"🔄 [PAYMENT_SPLITTING] Starting Client Payout")
        print(f"👤 [PAYMENT_SPLITTING] User ID: {user_id}")
        print(f"🏢 [PAYMENT_SPLITTING] Channel ID: {closed_channel_id}")
        print(f"💰 [PAYMENT_SPLITTING] Subscription Price: ${sub_price}")
        print(f"🏦 [PAYMENT_SPLITTING] Target: {wallet_address} ({payout_currency.upper()})")
        
        # Validate required fields
        if not all([user_id, closed_channel_id, wallet_address, payout_currency, sub_price]):
            return {
                "success": False,
                "error": "Missing required fields",
                "details": {
                    "user_id": bool(user_id),
                    "closed_channel_id": bool(closed_channel_id),
                    "wallet_address": bool(wallet_address),
                    "payout_currency": bool(payout_currency),
                    "sub_price": bool(sub_price)
                }
            }
        
        try:
            sub_price_float = float(sub_price)
        except (ValueError, TypeError):
            return {
                "success": False,
                "error": "Invalid subscription price format"
            }

        # Step 1: Get estimated conversion and save to database
        print(f"📊 [PAYMENT_SPLITTING] Step 1: Getting estimate and saving to database")
        estimate_data = get_estimated_conversion_and_save(
            user_id=user_id,
            closed_channel_id=closed_channel_id,
            wallet_address=wallet_address,
            payout_currency=payout_currency,
            subscription_price=str(sub_price)
        )

        if not estimate_data:
            return {
                "success": False,
                "error": "Failed to get conversion estimate or save to database"
            }

        print(f"✅ [PAYMENT_SPLITTING] Estimate saved with unique_id: {estimate_data['unique_id']}")
        print(f"💰 [PAYMENT_SPLITTING] Will convert {estimate_data['from_amount']} USDT → {estimate_data['to_amount']} {payout_currency.upper()}")

        # Step 2: Validate currency pair
        if not validate_changenow_pair("eth", payout_currency):
            return {
                "success": False,
                "error": f"Currency pair ETH → {payout_currency.upper()} not supported by ChangeNow",
                "estimate_data": estimate_data
            }

        # Step 3: Check amount limits
        amount_valid, limits_info = check_amount_limits("eth", payout_currency, sub_price_float)
        if not amount_valid:
            return {
                "success": False,
                "error": "Amount outside acceptable limits",
                "limits": limits_info,
                "estimate_data": estimate_data
            }

        # Step 4: Create fixed-rate transaction using to_amount from estimate and pass unique_id for linking
        print(f"🔗 [PAYMENT_SPLITTING] Passing unique_id '{estimate_data['unique_id']}' to transaction creation")
        transaction = create_fixed_rate_transaction(
            to_amount=float(estimate_data['to_amount']),
            from_currency="eth",
            to_currency=payout_currency,
            wallet_address=wallet_address,
            user_id=user_id,
            unique_id=estimate_data['unique_id'],  # Pass unique_id for linking tables
            closed_channel_id=str(closed_channel_id),  # Pass closed_channel_id for database
            from_network="eth",
            to_network="eth"
        )

        if transaction:
            print(f"✅ [PAYMENT_SPLITTING] Completed successfully")

            # Step 5: Send Telegram notification
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
                "currency": "ETH",
                "estimate_data": estimate_data  # Include estimate data in response
            }
        else:
            return {
                "success": False,
                "error": "Failed to create ChangeNow transaction",
                "estimate_data": estimate_data  # Include estimate data even if transaction failed
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
    Main webhook endpoint for receiving payment split requests from tph10-16.py.
    """
    try:
        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get('X-Webhook-Signature', '')

        print(f"🎯 [WEBHOOK] TPS10-21 Webhook Called")
        print(f"📦 [WEBHOOK] Payload size: {len(payload)} bytes")
        
        # Verify webhook signature if signing key is available
        signing_key = config.get('success_url_signing_key')
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
        "service": "TPS10-21 Payment Splitting",
        "timestamp": int(time.time())
    }), 200

# --- Flask entrypoint for deployment ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)