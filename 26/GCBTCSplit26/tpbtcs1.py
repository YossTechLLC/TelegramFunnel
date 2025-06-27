#!/usr/bin/env python
"""
TPBTCS1 - Bitcoin (WBTC) Payment Splitting Webhook Service
Receives payment data from tph6.py, converts USD to WBTC, and sends 30% to client wallets.
Handles Bitcoin address validation and WBTC (Wrapped Bitcoin) transfers on Ethereum/Polygon.
"""
import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from flask import Flask, request, abort, jsonify

# Import our custom modules
from btc_converter import BTCConverter
from btc_wallet_manager import BTCWalletManager

# Import config manager from parent directory
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'GCSplit26'))
from config_manager import ConfigManager

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global components
config_manager = None
btc_converter = None
btc_wallet_manager = None


def initialize_components():
    """Initialize all system components."""
    global config_manager, btc_converter, btc_wallet_manager
    
    try:
        print("₿ [INFO] Initializing Bitcoin (WBTC) Payment Splitting Service...")
        
        # Initialize configuration manager
        config_manager = ConfigManager()
        config = config_manager.load_configuration()
        
        if not config_manager.validate_configuration():
            raise RuntimeError("Configuration validation failed")
        
        # Initialize BTC converter
        print("💱 [INFO] Initializing BTC converter with market data...")
        btc_converter = BTCConverter(config_manager=config_manager)
        
        # Initialize BTC wallet manager (WBTC on Ethereum)
        print("₿ [INFO] Initializing BTC wallet manager...")
        btc_wallet_manager = BTCWalletManager(
            private_key=config['host_wallet_private_key'],
            host_address=config['host_wallet_eth_address'],
            rpc_url=config['ethereum_rpc_url'],
            chain_id=1  # Ethereum mainnet for WBTC
        )
        
        print("✅ [INFO] All Bitcoin components initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ [ERROR] Bitcoin component initialization failed: {e}")
        return False


def validate_request_payload(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate incoming webhook payload for Bitcoin payments.
    
    Args:
        data: Request payload
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['client_wallet_address', 'sub_price', 'user_id', 'client_payout_currency']
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Validate subscription price
    try:
        sub_price = float(data['sub_price'])
        if sub_price <= 0 or sub_price > 1000:  # Max $1000 for security
            return False, "Subscription price out of valid range (0-1000 USD)"
    except (ValueError, TypeError):
        return False, "Invalid subscription price format"
    
    # Validate user ID
    try:
        user_id = int(data['user_id'])
        if user_id <= 0:
            return False, "Invalid user ID"
    except (ValueError, TypeError):
        return False, "Invalid user ID format"
    
    # Validate payout currency is Bitcoin-related
    payout_currency = data['client_payout_currency'].strip().upper()
    if payout_currency not in ['BTC', 'WBTC']:
        return False, f"Invalid Bitcoin currency: {payout_currency}. Expected BTC or WBTC"
    
    # Validate wallet address
    client_wallet_address = data['client_wallet_address']
    if not client_wallet_address:
        return False, "Client wallet address cannot be empty"
    
    # For WBTC, we need Ethereum address; for BTC we accept Bitcoin address but convert to ETH
    if payout_currency == 'WBTC':
        if not client_wallet_address.startswith('0x') or len(client_wallet_address) != 42:
            return False, "WBTC requires Ethereum address format (0x...)"
    else:  # BTC
        # Accept both Bitcoin and Ethereum addresses
        if client_wallet_address.startswith('0x'):
            if len(client_wallet_address) != 42:
                return False, "Invalid Ethereum address format"
        else:
            # Validate Bitcoin address format
            btc_validation = btc_wallet_manager.validate_bitcoin_address(client_wallet_address)
            if not btc_validation['valid']:
                return False, f"Invalid Bitcoin address: {btc_validation['error']}"
    
    return True, ""


def log_transaction_request(data: Dict[str, Any]) -> str:
    """
    Log incoming transaction request and return request ID.
    
    Args:
        data: Request payload
        
    Returns:
        Unique request ID for tracking
    """
    request_id = f"TPBTCS1_{int(time.time())}_{data.get('user_id', 'unknown')}"
    
    print(f"📝 [INFO] Bitcoin transaction request received - ID: {request_id}")
    print(f"💰 [INFO] Amount: ${data.get('sub_price', 'unknown')} USD")
    print(f"🏦 [INFO] Destination: {data.get('client_wallet_address', 'unknown')}")
    print(f"₿ [INFO] Payout Currency: {data.get('client_payout_currency', 'unknown')}")
    print(f"👤 [INFO] User ID: {data.get('user_id', 'unknown')}")
    
    return request_id


@app.route("/", methods=["POST"])
def process_bitcoin_payment():
    """
    Main webhook endpoint for processing Bitcoin (WBTC) payments.
    
    Expected payload:
    {
        "client_wallet_address": "bc1..." or "0x...",
        "sub_price": "15.00",
        "user_id": 12345,
        "client_payout_currency": "BTC" | "WBTC"
    }
    """
    request_start_time = time.time()
    request_id = None
    
    try:
        # Parse request data
        if not request.is_json:
            print("❌ [ERROR] Request is not JSON")
            abort(400, "Request must be JSON")
        
        data = request.get_json()
        request_id = log_transaction_request(data)
        
        # Validate payload
        is_valid, error_msg = validate_request_payload(data)
        if not is_valid:
            print(f"❌ [ERROR] {request_id}: Payload validation failed - {error_msg}")
            abort(400, f"Invalid payload: {error_msg}")
        
        client_wallet_address = data['client_wallet_address']
        sub_price_usd = float(data['sub_price'])
        user_id = int(data['user_id'])
        client_payout_currency = data['client_payout_currency'].strip().upper()
        
        print(f"₿ [INFO] {request_id}: Starting {client_payout_currency} conversion and transfer process")
        
        # Calculate client amount (30% of subscription)
        client_usd_amount = sub_price_usd * 0.30
        print(f"💰 [INFO] {request_id}: Client USD amount (30%): ${client_usd_amount:.2f}")
        
        # Convert USD to WBTC
        print(f"💱 [INFO] {request_id}: Converting ${client_usd_amount:.2f} USD to WBTC")
        
        conversion_result = btc_converter.convert_usd_to_wbtc(client_usd_amount)
        
        if not conversion_result['success']:
            error_msg = f"Failed to convert USD to WBTC: {conversion_result.get('error', 'Unknown error')}"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            abort(500, error_msg)
        
        client_wbtc_amount = conversion_result['wbtc_amount']
        wbtc_per_usd = conversion_result['wbtc_per_usd']
        usd_per_btc = conversion_result['usd_per_btc']
        
        print(f"📊 [INFO] {request_id}: BTC Rate: ${usd_per_btc:.2f} USD/BTC")
        print(f"📊 [INFO] {request_id}: Conversion Rate: {wbtc_per_usd:.8f} WBTC/USD")
        print(f"🎯 [INFO] {request_id}: Client gets: {client_wbtc_amount:.8f} WBTC (30% of ${sub_price_usd:.2f})")
        
        # Validate WBTC amount
        if not btc_converter.validate_btc_amount(client_wbtc_amount):
            error_msg = f"WBTC amount {client_wbtc_amount:.8f} is invalid or too small"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            abort(500, error_msg)
        
        # Check wallet balances
        wbtc_balance_result = btc_wallet_manager.get_wbtc_balance()
        if not wbtc_balance_result['success']:
            error_msg = f"Failed to check WBTC balance: {wbtc_balance_result.get('error', 'Unknown error')}"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            abort(500, error_msg)
        
        wbtc_balance = wbtc_balance_result['balance_wbtc']
        print(f"₿ [INFO] {request_id}: WBTC balance: {wbtc_balance:.8f} WBTC")
        
        # Also check ETH balance for gas
        eth_balance_result = btc_wallet_manager.get_wallet_balance()
        if not eth_balance_result['success']:
            error_msg = f"Failed to check ETH balance for gas: {eth_balance_result.get('error', 'Unknown error')}"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            abort(500, error_msg)
        
        eth_balance = eth_balance_result['balance_eth']
        print(f"⛽ [INFO] {request_id}: ETH balance for gas: {eth_balance:.6f} ETH")
        
        # Check sufficient WBTC balance
        if wbtc_balance < client_wbtc_amount:
            error_msg = f"Insufficient WBTC balance. Need: {client_wbtc_amount:.8f} WBTC, Have: {wbtc_balance:.8f} WBTC"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            print(f"💡 [SUGGESTION] {request_id}: Add more WBTC to host wallet or implement ETH→WBTC swapping")
            abort(500, error_msg)
        
        # Handle Bitcoin vs Ethereum address for WBTC transfer
        recipient_address = client_wallet_address
        
        if not client_wallet_address.startswith('0x'):
            # Bitcoin address provided - need to inform user about WBTC limitation
            print(f"⚠️ [WARNING] {request_id}: Bitcoin address provided but WBTC requires Ethereum address")
            print(f"💡 [INFO] {request_id}: WBTC is an ERC20 token on Ethereum - cannot send to Bitcoin address")
            
            error_msg = ("WBTC cannot be sent to Bitcoin addresses. "
                        "WBTC is an Ethereum ERC20 token. "
                        "Please provide an Ethereum address (0x...) to receive WBTC.")
            abort(400, error_msg)
        
        # Send WBTC to Ethereum address
        print(f"₿ [INFO] {request_id}: Sending {client_wbtc_amount:.8f} WBTC to {recipient_address}")
        
        transaction_result = btc_wallet_manager.send_wbtc_to_address(
            recipient_address=recipient_address,
            amount_wbtc=client_wbtc_amount,
            request_id=request_id
        )
        
        if not transaction_result['success']:
            error_msg = f"WBTC transaction failed: {transaction_result.get('error', 'Unknown error')}"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            abort(500, error_msg)
        
        transaction_hash = transaction_result['transaction_hash']
        gas_used = transaction_result.get('gas_used', 'unknown')
        gas_price = transaction_result.get('gas_price', 'unknown')
        
        # Calculate processing time
        processing_time = time.time() - request_start_time
        
        # Log success
        print(f"✅ [SUCCESS] {request_id}: WBTC transaction completed successfully!")
        print(f"🔗 [INFO] {request_id}: TX Hash: {transaction_hash}")
        print(f"⛽ [INFO] {request_id}: Gas used: {gas_used}, Gas price: {gas_price}")
        print(f"⏱️ [INFO] {request_id}: Processing time: {processing_time:.2f}s")
        
        # Return success response
        response_data = {
            "status": "success",
            "request_id": request_id,
            "transaction_hash": transaction_hash,
            "amount_usd": sub_price_usd,
            "amount_sent": client_wbtc_amount,
            "payout_currency": "WBTC",
            "wbtc_per_usd": wbtc_per_usd,
            "usd_per_btc": usd_per_btc,
            "recipient": recipient_address,
            "user_id": user_id,
            "processing_time_seconds": round(processing_time, 2),
            "chain_id": transaction_result.get('chain_id', 1),
            "token_contract": btc_wallet_manager.wbtc_contract.address if btc_wallet_manager.wbtc_contract else None
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        processing_time = time.time() - request_start_time
        error_msg = f"Unexpected error processing Bitcoin payment: {str(e)}"
        
        if request_id:
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            print(f"⏱️ [INFO] {request_id}: Failed after {processing_time:.2f}s")
        else:
            print(f"❌ [ERROR] {error_msg}")
        
        logger.exception("Bitcoin payment processing error")
        abort(500, error_msg)


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check component status
        components_status = {
            "config_manager": config_manager is not None and config_manager.config_loaded,
            "btc_converter": btc_converter is not None,
            "btc_wallet_manager": btc_wallet_manager is not None,
            "wbtc_contract": btc_wallet_manager is not None and btc_wallet_manager.wbtc_contract is not None
        }
        
        all_healthy = all(components_status.values())
        
        # Get wallet balance if available
        wallet_info = {}
        if btc_wallet_manager:
            wbtc_result = btc_wallet_manager.get_wbtc_balance()
            eth_result = btc_wallet_manager.get_wallet_balance()
            
            if wbtc_result['success'] and eth_result['success']:
                wallet_info = {
                    "balance_wbtc": wbtc_result['balance_wbtc'],
                    "balance_eth": eth_result['balance_eth'],
                    "balance_usd": wbtc_result.get('balance_usd', 'unknown')
                }
        
        # Get market data if available
        market_info = {}
        if btc_converter:
            try:
                market_info = btc_converter.get_market_summary()
            except Exception:
                pass
        
        health_data = {
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": components_status,
            "wallet": wallet_info,
            "market": market_info
        }
        
        status_code = 200 if all_healthy else 503
        return jsonify(health_data), status_code
        
    except Exception as e:
        error_data = {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
        return jsonify(error_data), 500


@app.route("/status", methods=["GET"])
def get_status():
    """Get detailed system status."""
    try:
        status_data = {
            "service": "TPBTCS1 - Bitcoin (WBTC) Payment Splitting Service",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": "Service running"
        }
        
        # Add component details if available
        if config_manager:
            status_data["config"] = config_manager.get_safe_config_summary()
        
        if btc_wallet_manager:
            wbtc_result = btc_wallet_manager.get_wbtc_balance()
            eth_result = btc_wallet_manager.get_wallet_balance()
            
            if wbtc_result['success'] and eth_result['success']:
                status_data["wallet"] = {
                    "address": config_manager.host_wallet_eth_address if config_manager else "unknown",
                    "balance_wbtc": wbtc_result['balance_wbtc'],
                    "balance_eth": eth_result['balance_eth'],
                    "balance_usd": wbtc_result.get('balance_usd', 'unknown')
                }
        
        if btc_converter:
            try:
                market_data = btc_converter.get_market_summary()
                status_data["current_btc_rate"] = {
                    "usd_per_btc": market_data.get('btc_price_usd', 0),
                    "wbtc_per_usd": market_data.get('wbtc_per_usd', 0),
                    "source": market_data.get('data_source', 'unknown'),
                    "cache_status": market_data.get('cache_status', 'unknown')
                }
            except Exception:
                pass
        
        return jsonify(status_data), 200
        
    except Exception as e:
        error_data = {
            "service": "TPBTCS1 - Bitcoin (WBTC) Payment Splitting Service",
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
        return jsonify(error_data), 500


# Initialize components on startup
if __name__ == "__main__":
    print("₿ [STARTUP] TPBTCS1 Bitcoin (WBTC) Payment Splitting Service starting...")
    
    if initialize_components():
        print("✅ [STARTUP] Initialization successful, starting Flask server...")
        app.run(host="0.0.0.0", port=8080, debug=False)
    else:
        print("❌ [STARTUP] Initialization failed, exiting...")
        exit(1)