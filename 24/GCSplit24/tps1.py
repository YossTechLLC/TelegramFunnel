#!/usr/bin/env python
"""
TPS1 - ETH Payment Splitting Webhook Service
Receives payment data from tph4.py, converts USD to ETH, and sends 85% to client wallets.
"""
import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from flask import Flask, request, abort, jsonify

# Import our custom modules
from config_manager import ConfigManager
from eth_converter import EthConverter
from wallet_manager import WalletManager

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
eth_converter = None
wallet_manager = None

def initialize_components():
    """Initialize all system components."""
    global config_manager, eth_converter, wallet_manager
    
    try:
        print("🚀 [INFO] Initializing ETH Payment Splitting Service...")
        
        # Initialize configuration manager
        config_manager = ConfigManager()
        config = config_manager.load_configuration()
        
        if not config_manager.validate_configuration():
            raise RuntimeError("Configuration validation failed")
        
        # Initialize ETH converter
        eth_converter = EthConverter(config['oneinch_api_key'])
        
        # Initialize wallet manager
        wallet_manager = WalletManager(
            private_key=config['host_wallet_private_key'],
            host_address=config['host_wallet_eth_address'],
            rpc_url=config['ethereum_rpc_url']
        )
        
        print("✅ [INFO] All components initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ [ERROR] Component initialization failed: {e}")
        return False

def validate_request_payload(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate incoming webhook payload.
    
    Args:
        data: Request payload
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['client_wallet_address', 'sub_price', 'user_id']
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Validate client wallet address
    wallet_address = data['client_wallet_address']
    if not isinstance(wallet_address, str) or not wallet_address.startswith('0x') or len(wallet_address) != 42:
        return False, "Invalid client wallet address format"
    
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
    
    return True, ""

def log_transaction_request(data: Dict[str, Any]) -> str:
    """
    Log incoming transaction request and return request ID.
    
    Args:
        data: Request payload
        
    Returns:
        Unique request ID for tracking
    """
    request_id = f"TPS1_{int(time.time())}_{data.get('user_id', 'unknown')}"
    
    print(f"📝 [INFO] Transaction request received - ID: {request_id}")
    print(f"💰 [INFO] Amount: ${data.get('sub_price', 'unknown')} USD")
    print(f"🏦 [INFO] Destination: {data.get('client_wallet_address', 'unknown')}")
    print(f"👤 [INFO] User ID: {data.get('user_id', 'unknown')}")
    
    return request_id

@app.route("/", methods=["POST"])
def process_payment():
    """
    Main webhook endpoint for processing ETH payments.
    
    Expected payload:
    {
        "client_wallet_address": "0x...",
        "sub_price": "15.00",
        "user_id": 12345
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
        
        print(f"🔄 [INFO] {request_id}: Starting ETH conversion and transfer process")
        
        # Step 1: Convert USD to ETH
        print(f"💱 [INFO] {request_id}: Converting ${sub_price_usd:.2f} USD to ETH")
        eth_rate_result = eth_converter.get_usd_to_eth_rate()
        
        if not eth_rate_result['success']:
            error_msg = f"Failed to get ETH conversion rate: {eth_rate_result.get('error', 'Unknown error')}"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            abort(500, error_msg)
        
        eth_rate = eth_rate_result['eth_per_usd']
        total_eth_amount = sub_price_usd * eth_rate
        client_eth_amount = total_eth_amount * 0.85  # 85% to client
        
        print(f"📊 [INFO] {request_id}: ETH Rate: {eth_rate:.8f} ETH/USD")
        print(f"💰 [INFO] {request_id}: Total ETH: {total_eth_amount:.8f}")
        print(f"🎯 [INFO] {request_id}: Client gets: {client_eth_amount:.8f} ETH (85%)")
        
        # Step 2: Check wallet balance
        balance_result = wallet_manager.get_wallet_balance()
        if not balance_result['success']:
            error_msg = f"Failed to check wallet balance: {balance_result.get('error', 'Unknown error')}"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            abort(500, error_msg)
        
        wallet_balance = balance_result['balance_eth']
        print(f"🏦 [INFO] {request_id}: Wallet balance: {wallet_balance:.8f} ETH")
        
        if wallet_balance < client_eth_amount:
            error_msg = f"Insufficient wallet balance. Need: {client_eth_amount:.8f} ETH, Have: {wallet_balance:.8f} ETH"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            abort(500, error_msg)
        
        # Step 3: Send ETH to client wallet
        print(f"📤 [INFO] {request_id}: Sending {client_eth_amount:.8f} ETH to {client_wallet_address}")
        transaction_result = wallet_manager.send_eth_to_address(
            recipient_address=client_wallet_address,
            amount_eth=client_eth_amount,
            request_id=request_id
        )
        
        if not transaction_result['success']:
            error_msg = f"Transaction failed: {transaction_result.get('error', 'Unknown error')}"
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            abort(500, error_msg)
        
        transaction_hash = transaction_result['transaction_hash']
        gas_used = transaction_result.get('gas_used', 'unknown')
        gas_price = transaction_result.get('gas_price', 'unknown')
        
        # Calculate processing time
        processing_time = time.time() - request_start_time
        
        # Log success
        print(f"✅ [SUCCESS] {request_id}: Transaction completed successfully!")
        print(f"🔗 [INFO] {request_id}: TX Hash: {transaction_hash}")
        print(f"⛽ [INFO] {request_id}: Gas used: {gas_used}, Gas price: {gas_price}")
        print(f"⏱️ [INFO] {request_id}: Processing time: {processing_time:.2f}s")
        
        # Return success response
        response_data = {
            "status": "success",
            "request_id": request_id,
            "transaction_hash": transaction_hash,
            "amount_usd": sub_price_usd,
            "amount_eth": client_eth_amount,
            "eth_rate": eth_rate,
            "recipient": client_wallet_address,
            "user_id": user_id,
            "processing_time_seconds": round(processing_time, 2)
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        processing_time = time.time() - request_start_time
        error_msg = f"Unexpected error processing payment: {str(e)}"
        
        if request_id:
            print(f"❌ [ERROR] {request_id}: {error_msg}")
            print(f"⏱️ [INFO] {request_id}: Failed after {processing_time:.2f}s")
        else:
            print(f"❌ [ERROR] {error_msg}")
        
        logger.exception("Payment processing error")
        abort(500, error_msg)

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check component status
        components_status = {
            "config_manager": config_manager is not None and config_manager.config_loaded,
            "eth_converter": eth_converter is not None,
            "wallet_manager": wallet_manager is not None
        }
        
        all_healthy = all(components_status.values())
        
        # Get wallet balance if available
        wallet_info = {}
        if wallet_manager:
            balance_result = wallet_manager.get_wallet_balance()
            if balance_result['success']:
                wallet_info = {
                    "balance_eth": balance_result['balance_eth'],
                    "balance_usd": balance_result.get('balance_usd', 'unknown')
                }
        
        # Get config summary
        config_summary = {}
        if config_manager:
            config_summary = config_manager.get_safe_config_summary()
        
        health_data = {
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": components_status,
            "wallet": wallet_info,
            "config": config_summary
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
            "service": "TPS1 - ETH Payment Splitting Service",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": "Service running"
        }
        
        # Add component details if available
        if config_manager:
            status_data["config"] = config_manager.get_safe_config_summary()
        
        if wallet_manager:
            balance_result = wallet_manager.get_wallet_balance()
            if balance_result['success']:
                status_data["wallet"] = {
                    "address": config_manager.host_wallet_eth_address if config_manager else "unknown",
                    "balance_eth": balance_result['balance_eth'],
                    "balance_usd": balance_result.get('balance_usd', 'unknown')
                }
        
        if eth_converter:
            rate_result = eth_converter.get_usd_to_eth_rate()
            if rate_result['success']:
                status_data["current_eth_rate"] = {
                    "eth_per_usd": rate_result['eth_per_usd'],
                    "usd_per_eth": rate_result.get('usd_per_eth', 'unknown'),
                    "source": rate_result.get('source', 'unknown'),
                    "timestamp": rate_result.get('timestamp', 'unknown')
                }
        
        return jsonify(status_data), 200
        
    except Exception as e:
        error_data = {
            "service": "TPS1 - ETH Payment Splitting Service",
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
        return jsonify(error_data), 500

# Initialize components on startup
if __name__ == "__main__":
    print("🚀 [STARTUP] TPS1 ETH Payment Splitting Service starting...")
    
    if initialize_components():
        print("✅ [STARTUP] Initialization successful, starting Flask server...")
        app.run(host="0.0.0.0", port=8080, debug=False)
    else:
        print("❌ [STARTUP] Initialization failed, exiting...")
        exit(1)