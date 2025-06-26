#!/usr/bin/env python
"""
TPS3 - Multi-Token Payment Splitting Webhook Service
Receives payment data from tph6.py, converts USD to tokens (ETH/ERC20), and sends 30% to client wallets.
Supports ETH and major ERC20 tokens including USDT, USDC, DAI, LINK, UNI, AAVE, etc.
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
from multi_token_converter import MultiTokenConverter
from wallet_manager import WalletManager
from dex_swapper import SwapConfig

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
multi_token_converter = None
wallet_manager = None
swap_config = None

def initialize_components():
    """Initialize all system components."""
    global config_manager, eth_converter, multi_token_converter, wallet_manager, swap_config
    
    try:
        print("🚀 [INFO] Initializing Multi-Token Payment Splitting Service...")
        
        # Initialize configuration manager
        config_manager = ConfigManager()
        config = config_manager.load_configuration()
        
        if not config_manager.validate_configuration():
            raise RuntimeError("Configuration validation failed")
        
        # Initialize ETH converter (legacy compatibility)
        eth_converter = EthConverter(config['oneinch_api_key'])
        
        # Initialize multi-token converter with robust market data provider
        print("🪙 [INFO] Initializing multi-token converter with robust pricing...")
        multi_token_converter = MultiTokenConverter(
            oneinch_api_key=config['oneinch_api_key'],  # Legacy fallback
            chain_id=1,  # Default to Ethereum Mainnet
            config_manager=config_manager  # Pass config manager for API key access
        )
        
        # Initialize wallet manager
        print("🔄 [INFO] Initializing wallet manager with Web3 connection...")
        wallet_manager = WalletManager(
            private_key=config['host_wallet_private_key'],
            host_address=config['host_wallet_eth_address'],
            rpc_url=config['ethereum_rpc_url']
        )
        
        # Initialize DEX swapper for automatic token conversion
        print("🔄 [INFO] Initializing DEX swapper for automatic token conversion...")
        
        # Configure swap parameters (can be overridden via environment variables)
        swap_config = SwapConfig(
            max_slippage_percent=float(os.getenv("SWAP_MAX_SLIPPAGE", "1.0")),  # 1% default slippage
            max_eth_per_swap=float(os.getenv("SWAP_MAX_ETH", "0.1")),           # 0.1 ETH maximum per swap
            min_eth_reserve=float(os.getenv("SWAP_MIN_ETH_RESERVE", "0.001")),  # Keep 0.001 ETH minimum for gas
            swap_timeout_seconds=int(os.getenv("SWAP_TIMEOUT", "30")),          # 30 second timeout
            enable_swapping=os.getenv("ENABLE_AUTO_SWAPPING", "true").lower() == "true"  # Enable by default
        )
        
        print(f"⚙️ [INFO] Swap configuration: slippage={swap_config.max_slippage_percent}%, max_eth={swap_config.max_eth_per_swap}, reserve={swap_config.min_eth_reserve}")
        
        dex_init_success = wallet_manager.initialize_dex_swapper(
            oneinch_api_key=config['oneinch_api_key'],
            swap_config=swap_config,
            config_manager=config_manager  # Pass config manager for market data validation
        )
        
        if dex_init_success:
            print("✅ [INFO] DEX swapper initialized - automatic token conversion enabled")
        else:
            print("⚠️ [WARNING] DEX swapper initialization failed - manual token management required")
        
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
    required_fields = ['client_wallet_address', 'sub_price', 'user_id', 'client_payout_currency']
    
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
    
    # Validate payout currency
    payout_currency = data['client_payout_currency'].strip().upper()
    if not payout_currency:
        return False, "Client payout currency cannot be empty"
    
    # Allow basic validation - detailed validation happens in converter
    if len(payout_currency) > 10:  # Reasonable token symbol length
        return False, "Invalid payout currency format"
    
    return True, ""

def log_transaction_request(data: Dict[str, Any]) -> str:
    """
    Log incoming transaction request and return request ID.
    
    Args:
        data: Request payload
        
    Returns:
        Unique request ID for tracking
    """
    request_id = f"TPS3_{int(time.time())}_{data.get('user_id', 'unknown')}"
    
    print(f"📝 [INFO] Transaction request received - ID: {request_id}")
    print(f"💰 [INFO] Amount: ${data.get('sub_price', 'unknown')} USD")
    print(f"🏦 [INFO] Destination: {data.get('client_wallet_address', 'unknown')}")
    print(f"🪙 [INFO] Payout Currency: {data.get('client_payout_currency', 'unknown')}")
    print(f"👤 [INFO] User ID: {data.get('user_id', 'unknown')}")
    
    return request_id

@app.route("/", methods=["POST"])
def process_payment():
    """
    Main webhook endpoint for processing token payments.
    
    Expected payload:
    {
        "client_wallet_address": "0x...",
        "sub_price": "15.00",
        "user_id": 12345,
        "client_payout_currency": "ETH" | "USDT" | "USDC" | etc.
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
        
        print(f"🔄 [INFO] {request_id}: Starting {client_payout_currency} conversion and transfer process")
        
        # Step 1: Determine payment flow based on currency
        if client_payout_currency == "ETH":
            # Legacy ETH flow for backward compatibility
            print(f"💱 [INFO] {request_id}: Converting ${sub_price_usd:.2f} USD to ETH (legacy flow)")
            rate_result = eth_converter.get_usd_to_eth_rate()
            
            if not rate_result['success']:
                error_msg = f"Failed to get ETH conversion rate: {rate_result.get('error', 'Unknown error')}"
                print(f"❌ [ERROR] {request_id}: {error_msg}")
                abort(500, error_msg)
            
            tokens_per_usd = rate_result['eth_per_usd']
            total_token_amount = sub_price_usd * tokens_per_usd
            client_token_amount = total_token_amount * 0.30  # 30% to client
            
            print(f"📊 [INFO] {request_id}: ETH Rate: {tokens_per_usd:.8f} ETH/USD")
            print(f"💰 [INFO] {request_id}: Total ETH: {total_token_amount:.8f}")
            print(f"🎯 [INFO] {request_id}: Client gets: {client_token_amount:.8f} ETH (30%)")
            
        else:
            # Multi-token flow for ERC20 tokens
            print(f"🪙 [INFO] {request_id}: Converting ${sub_price_usd:.2f} USD to {client_payout_currency} (multi-token flow)")
            
            # First, get ETH equivalent (30% of USD amount)
            client_usd_amount = sub_price_usd * 0.30  # 30% to client
            print(f"💰 [INFO] {request_id}: Client USD amount (30%): ${client_usd_amount:.2f}")
            
            # Convert client's USD amount to target token
            conversion_result = multi_token_converter.convert_usd_to_token(client_usd_amount, client_payout_currency)
            
            if not conversion_result['success']:
                error_msg = f"Failed to convert USD to {client_payout_currency}: {conversion_result.get('error', 'Unknown error')}"
                print(f"❌ [ERROR] {request_id}: {error_msg}")
                abort(500, error_msg)
            
            client_token_amount = conversion_result['token_amount']
            tokens_per_usd = conversion_result['tokens_per_usd']
            
            print(f"📊 [INFO] {request_id}: {client_payout_currency} Rate: {tokens_per_usd:.8f} {client_payout_currency}/USD")
            print(f"🎯 [INFO] {request_id}: Client gets: {client_token_amount:.8f} {client_payout_currency} (30% of ${sub_price_usd:.2f})")
        
        # Step 2: Check wallet balances and send transaction
        if client_payout_currency == "ETH":
            # ETH balance check and transfer
            balance_result = wallet_manager.get_wallet_balance()
            if not balance_result['success']:
                error_msg = f"Failed to check ETH wallet balance: {balance_result.get('error', 'Unknown error')}"
                print(f"❌ [ERROR] {request_id}: {error_msg}")
                abort(500, error_msg)
            
            wallet_balance = balance_result['balance_eth']
            print(f"🏦 [INFO] {request_id}: ETH wallet balance: {wallet_balance:.8f} ETH")
            
            if wallet_balance < client_token_amount:
                error_msg = f"Insufficient ETH balance. Need: {client_token_amount:.8f} ETH, Have: {wallet_balance:.8f} ETH"
                print(f"❌ [ERROR] {request_id}: {error_msg}")
                abort(500, error_msg)
            
            # Send ETH to client wallet
            print(f"📤 [INFO] {request_id}: Sending {client_token_amount:.8f} ETH to {client_wallet_address}")
            transaction_result = wallet_manager.send_eth_to_address(
                recipient_address=client_wallet_address,
                amount_eth=client_token_amount,
                request_id=request_id
            )
            
        else:
            # ERC20 token balance check and transfer
            token_balance_result = wallet_manager.get_erc20_balance(client_payout_currency)
            if not token_balance_result['success']:
                error_msg = f"Failed to check {client_payout_currency} balance: {token_balance_result.get('error', 'Unknown error')}"
                print(f"❌ [ERROR] {request_id}: {error_msg}")
                abort(500, error_msg)
            
            token_balance = token_balance_result['balance_tokens']
            print(f"🪙 [INFO] {request_id}: {client_payout_currency} balance: {token_balance:.8f} {client_payout_currency}")
            
            # Also check ETH balance for gas
            eth_balance_result = wallet_manager.get_wallet_balance()
            if not eth_balance_result['success']:
                error_msg = f"Failed to check ETH balance for gas: {eth_balance_result.get('error', 'Unknown error')}"
                print(f"❌ [ERROR] {request_id}: {error_msg}")
                abort(500, error_msg)
            
            eth_balance = eth_balance_result['balance_eth']
            print(f"⛽ [INFO] {request_id}: ETH balance for gas: {eth_balance:.8f} ETH")
            
            # Ensure sufficient token balance (automatic conversion if needed)
            if token_balance < client_token_amount:
                print(f"📉 [INFO] {request_id}: Insufficient {client_payout_currency} balance - attempting automatic conversion")
                print(f"💰 [INFO] {request_id}: Need: {client_token_amount:.8f} {client_payout_currency}, Have: {token_balance:.8f} {client_payout_currency}")
                
                # Attempt to acquire tokens via ETH swap
                ensure_result = wallet_manager.ensure_token_balance(
                    token_symbol=client_payout_currency,
                    required_amount=client_token_amount,
                    request_id=request_id
                )
                
                if not ensure_result['success']:
                    error_details = ensure_result.get('error', 'Unknown error')
                    action_attempted = ensure_result.get('action_taken', 'unknown')
                    
                    error_msg = f"Failed to acquire sufficient {client_payout_currency}: {error_details}"
                    print(f"❌ [ERROR] {request_id}: {error_msg}")
                    print(f"🔍 [DEBUG] {request_id}: Action attempted: {action_attempted}")
                    
                    # Provide specific troubleshooting suggestions based on error type
                    if "insufficient eth" in error_details.lower():
                        print(f"💡 [SUGGESTION] {request_id}: Add more ETH to host wallet for automatic swapping")
                        # Access swap config through wallet manager if available
                        min_reserve = "unknown"
                        if wallet_manager and wallet_manager.dex_swapper and wallet_manager.dex_swapper.config:
                            min_reserve = f"{wallet_manager.dex_swapper.config.min_eth_reserve:.6f}"
                            required_total = wallet_manager.dex_swapper.config.min_eth_reserve + 0.003  # Estimate for swap + gas
                            print(f"⛽ [SUGGESTION] {request_id}: Current ETH: {eth_balance:.6f}, Min reserve: {min_reserve}")
                            print(f"📊 [SUGGESTION] {request_id}: Recommended total ETH: >{required_total:.6f} (reserve + swap + gas)")
                        else:
                            print(f"⛽ [SUGGESTION] {request_id}: Current ETH: {eth_balance:.6f}, Min reserve: {min_reserve}")
                        print(f"🔧 [ALTERNATIVE] {request_id}: Lower reserve with env var SWAP_MIN_ETH_RESERVE=0.001")
                    elif "dex swapper not initialized" in error_details.lower():
                        print(f"💡 [SUGGESTION] {request_id}: Check 1INCH API key configuration or manually add {client_payout_currency} tokens")
                        print(f"🔍 [DEBUG] {request_id}: Verify 1INCH_API_KEY points to valid Secret Manager path")
                    elif "swapping is disabled" in error_details.lower():
                        print(f"💡 [SUGGESTION] {request_id}: Enable auto-swapping or manually add {client_payout_currency} tokens")
                        print(f"🔧 [FIX] {request_id}: Set environment variable ENABLE_AUTO_SWAPPING=true")
                    elif "quote returned zero tokens" in error_details.lower() or "all progressive quote attempts" in error_details.lower():
                        print(f"🔄 [SUGGESTION] {request_id}: 1INCH quote issues - try these solutions:")
                        print(f"    💰 Increase ETH balance above 0.01 ETH for better liquidity")
                        print(f"    🔄 Retry the payment in a few minutes (temporary API/liquidity issue)")
                        print(f"    💱 Consider switching to a more liquid token (USDT/USDC)")
                        print(f"    🔧 Check 1INCH API key configuration and rate limits")
                        
                        # Check if we have error analysis from DEX swapper
                        swap_result = ensure_result.get('swap_result', {})
                        if 'error_analysis' in swap_result:
                            error_analysis = swap_result['error_analysis']
                            print(f"🔍 [ANALYSIS] {request_id}: Detailed failure analysis:")
                            print(f"    📋 Issue type: {error_analysis.get('failure_type', 'unknown')}")
                            print(f"    ⚠️ Severity: {error_analysis.get('severity', 'unknown')}")
                            print(f"    💡 Recommended actions:")
                            for action in error_analysis.get('suggested_actions', []):
                                print(f"      {action}")
                        
                    else:
                        print(f"💡 [SUGGESTION] {request_id}: Ensure host wallet has sufficient ETH for swapping or manually add {client_payout_currency} tokens")
                        print(f"🔧 [ALTERNATIVES] {request_id}: 1) Add ETH to wallet, 2) Add {client_payout_currency} tokens directly, 3) Adjust SWAP_MIN_ETH_RESERVE")
                    
                    # Log additional context for debugging
                    print(f"🔍 [DEBUG] {request_id}: Required tokens: {client_token_amount:.8f} {client_payout_currency}")
                    print(f"🔍 [DEBUG] {request_id}: Current token balance: {token_balance:.8f} {client_payout_currency}")
                    print(f"🔍 [DEBUG] {request_id}: ETH balance: {eth_balance:.8f} ETH")
                    
                    abort(500, error_msg)
                
                action_taken = ensure_result.get('action_taken', 'unknown')
                if action_taken == 'eth_to_token_swap':
                    swap_result = ensure_result.get('swap_result', {})
                    tx_hash = swap_result.get('transaction_hash', 'unknown')
                    print(f"✅ [SUCCESS] {request_id}: Automatically swapped ETH for {client_payout_currency}")
                    print(f"🔗 [INFO] {request_id}: Swap TX Hash: {tx_hash}")
                    
                    # Update balance info for logging
                    new_balance = ensure_result.get('new_balance', client_token_amount)
                    print(f"🪙 [INFO] {request_id}: Updated {client_payout_currency} balance: {new_balance:.8f} {client_payout_currency}")
                else:
                    print(f"✅ [INFO] {request_id}: Token balance ensured (action: {action_taken})")
            
            # Send ERC20 tokens to client wallet
            print(f"🪙 [INFO] {request_id}: Sending {client_token_amount:.8f} {client_payout_currency} to {client_wallet_address}")
            transaction_result = wallet_manager.send_erc20_token(
                recipient_address=client_wallet_address,
                amount_tokens=client_token_amount,
                token_symbol=client_payout_currency,
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
        print(f"✅ [SUCCESS] {request_id}: {client_payout_currency} transaction completed successfully!")
        print(f"🔗 [INFO] {request_id}: TX Hash: {transaction_hash}")
        print(f"⛽ [INFO] {request_id}: Gas used: {gas_used}, Gas price: {gas_price}")
        print(f"⏱️ [INFO] {request_id}: Processing time: {processing_time:.2f}s")
        
        # Return success response
        response_data = {
            "status": "success",
            "request_id": request_id,
            "transaction_hash": transaction_hash,
            "amount_usd": sub_price_usd,
            "amount_sent": client_token_amount,
            "payout_currency": client_payout_currency,
            "tokens_per_usd": tokens_per_usd,
            "recipient": client_wallet_address,
            "user_id": user_id,
            "processing_time_seconds": round(processing_time, 2)
        }
        
        # Add legacy fields for backward compatibility
        if client_payout_currency == "ETH":
            response_data["amount_eth"] = client_token_amount
            response_data["eth_rate"] = tokens_per_usd
        
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
            "wallet_manager": wallet_manager is not None,
            "dex_swapper": wallet_manager is not None and wallet_manager.dex_swapper is not None,
            "auto_swapping": wallet_manager is not None and wallet_manager.dex_swapper is not None and wallet_manager.dex_swapper.config.enable_swapping
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
            "service": "TPS3 - Multi-Token Payment Splitting Service",
            "version": "3.0.0",
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
            "service": "TPS3 - Multi-Token Payment Splitting Service",
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
        return jsonify(error_data), 500

# Initialize components on startup
if __name__ == "__main__":
    print("🚀 [STARTUP] TPS3 Multi-Token Payment Splitting Service starting...")
    
    if initialize_components():
        print("✅ [STARTUP] Initialization successful, starting Flask server...")
        app.run(host="0.0.0.0", port=8080, debug=False)
    else:
        print("❌ [STARTUP] Initialization failed, exiting...")
        exit(1)