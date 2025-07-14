#!/usr/bin/env python
"""
Swap Processor for TelegramFunnel
Orchestrates cryptocurrency swaps via ChangeNOW and ETH transactions
"""
import asyncio
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from changenow_manager import ChangeNOWManager
from eth_wallet_manager import ETHWalletManager
from swap_database_manager import SwapDatabaseManager


class SwapProcessor:
    def __init__(self):
        """Initialize the Swap Processor with required managers."""
        self.changenow_manager = None
        self.eth_wallet_manager = None
        self.swap_db_manager = None
        self.swap_percentage = 0.30  # 30% of payment goes to client
        
    async def initialize_managers(self) -> Tuple[bool, str]:
        """
        Initialize ChangeNOW and ETH wallet managers.
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            print("🔧 [INFO] Initializing swap processor managers...")
            
            # Initialize ChangeNOW manager
            self.changenow_manager = ChangeNOWManager()
            print("✅ [INFO] ChangeNOW manager initialized")
            
            # Log API status summary for debugging
            await self.changenow_manager.log_api_status_summary()
            
            # Initialize ETH wallet manager
            self.eth_wallet_manager = ETHWalletManager()
            print("✅ [INFO] ETH wallet manager initialized")
            
            # Initialize database manager
            self.swap_db_manager = SwapDatabaseManager()
            print("✅ [INFO] Swap database manager initialized")
            
            # Ensure swap tracking table exists
            self.swap_db_manager.create_swap_tracking_table()
            
            return True, ""
            
        except Exception as e:
            error_msg = f"Failed to initialize swap processor managers: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return False, error_msg
    
    def calculate_swap_amount_usd(self, subscription_price_usd: str) -> float:
        """
        Calculate the USD amount to be swapped (30% of subscription price).
        
        Args:
            subscription_price_usd: Subscription price in USD as string
            
        Returns:
            Amount in USD to be swapped
        """
        try:
            price_usd = float(subscription_price_usd)
            swap_amount_usd = price_usd * self.swap_percentage
            print(f"💰 [DEBUG] Subscription: ${price_usd:.2f}, Swap amount (30%): ${swap_amount_usd:.2f}")
            return swap_amount_usd
        except (ValueError, TypeError) as e:
            print(f"❌ [ERROR] Invalid subscription price: {subscription_price_usd} - {e}")
            return 0.0
    
    def estimate_eth_amount_from_usd(self, usd_amount: float, eth_price_usd: float = 3000.0) -> float:
        """
        Estimate ETH amount from USD value.
        
        Args:
            usd_amount: Amount in USD
            eth_price_usd: Current ETH price in USD (fallback value)
            
        Returns:
            Estimated ETH amount
        """
        if eth_price_usd <= 0:
            eth_price_usd = 3000.0  # Fallback ETH price
            
        eth_amount = usd_amount / eth_price_usd
        print(f"📊 [DEBUG] ${usd_amount:.2f} ≈ {eth_amount:.6f} ETH (@ ${eth_price_usd:.2f}/ETH)")
        return eth_amount
    
    async def validate_swap_parameters(self, client_wallet_address: str, 
                                      client_payout_currency: str) -> Tuple[bool, str]:
        """
        Validate swap parameters before proceeding.
        
        Args:
            client_wallet_address: Client's wallet address
            client_payout_currency: Target currency for swap
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if managers are initialized
            if not self.changenow_manager or not self.eth_wallet_manager:
                return False, "Swap managers not initialized"
            
            # Skip validation for ETH (no swap needed)
            if client_payout_currency.upper() == "ETH":
                print("ℹ️ [DEBUG] Target currency is ETH - no swap validation needed")
                return True, ""
            
            # Validate client wallet address is not empty
            if not client_wallet_address or client_wallet_address.strip() == "":
                return False, "Client wallet address is empty"
            
            # Check if currency is supported by ChangeNOW
            is_supported, support_msg = await self.changenow_manager.is_currency_supported(client_payout_currency)
            if not is_supported:
                return False, f"Currency not supported: {support_msg}"
            
            # Validate client wallet address format
            is_valid_addr, addr_msg = await self.changenow_manager.validate_address(
                client_payout_currency, client_wallet_address
            )
            if not is_valid_addr:
                return False, f"Invalid wallet address: {addr_msg}"
            
            print(f"✅ [DEBUG] Swap parameters validated for {client_payout_currency} to {client_wallet_address}")
            return True, ""
            
        except Exception as e:
            error_msg = f"Parameter validation failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return False, error_msg
    
    async def process_changenow_swap(self, user_id: int, subscription_price_usd: str,
                                    client_wallet_address: str, client_payout_currency: str,
                                    order_id: str = "") -> Dict[str, Any]:
        """
        Process the complete ChangeNOW swap workflow.
        
        Args:
            user_id: User's Telegram ID
            subscription_price_usd: Subscription price in USD
            client_wallet_address: Client's wallet address for receiving swapped crypto
            client_payout_currency: Target currency for swap
            order_id: Optional order identifier
            
        Returns:
            Dictionary with swap result
        """
        try:
            print(f"🔄 [INFO] Starting ChangeNOW swap process for user {user_id}")
            print(f"💰 [INFO] Subscription: ${subscription_price_usd}, Target: {client_payout_currency}")
            print(f"📍 [INFO] Client wallet: {client_wallet_address}")
            
            # Initialize managers if needed
            if not self.changenow_manager or not self.eth_wallet_manager or not self.swap_db_manager:
                success, error = await self.initialize_managers()
                if not success:
                    return {"success": False, "error": error}
            
            # Skip swap if target currency is ETH
            if client_payout_currency.upper() == "ETH":
                print("ℹ️ [INFO] Target currency is ETH - no swap needed")
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "Target currency is ETH - no swap required"
                }
            
            # Validate parameters
            is_valid, validation_error = await self.validate_swap_parameters(
                client_wallet_address, client_payout_currency
            )
            if not is_valid:
                return {"success": False, "error": f"Validation failed: {validation_error}"}
            
            # Calculate swap amount in USD (30% of subscription)
            swap_amount_usd = self.calculate_swap_amount_usd(subscription_price_usd)
            if swap_amount_usd <= 0:
                return {"success": False, "error": "Invalid swap amount calculated"}
            
            # Estimate ETH amount needed for swap
            estimated_eth_amount = self.estimate_eth_amount_from_usd(swap_amount_usd)
            
            # Check ETH wallet balance
            balance_eth, _ = self.eth_wallet_manager.get_balance()
            if balance_eth < estimated_eth_amount:
                return {
                    "success": False,
                    "error": f"Insufficient ETH balance: {balance_eth:.6f} < {estimated_eth_amount:.6f}"
                }
            
            # Get exchange estimate from ChangeNOW
            estimate_result = await self.changenow_manager.estimate_exchange(
                "eth", client_payout_currency, estimated_eth_amount
            )
            
            if not estimate_result["success"]:
                return {
                    "success": False,
                    "error": f"Exchange estimation failed: {estimate_result['error']}"
                }
            
            estimated_output = estimate_result["data"].get("estimatedAmount", "0")
            print(f"📊 [INFO] Estimated output: {estimated_output} {client_payout_currency.upper()}")
            
            # Create ChangeNOW exchange transaction
            exchange_order_id = order_id or f"tf30_swap_{user_id}_{int(asyncio.get_event_loop().time())}"
            
            exchange_result = await self.changenow_manager.create_exchange(
                from_currency="eth",
                to_currency=client_payout_currency,
                from_amount=estimated_eth_amount,
                recipient_address=client_wallet_address,
                refund_address=self.eth_wallet_manager.wallet_address,
                order_id=exchange_order_id
            )
            
            if not exchange_result["success"]:
                return {
                    "success": False,
                    "error": f"Exchange creation failed: {exchange_result['error']}"
                }
            
            payin_address = exchange_result["payin_address"]
            exchange_id = exchange_result["exchange_id"]
            expected_amount = exchange_result["expected_amount"]
            
            print(f"✅ [SUCCESS] ChangeNOW exchange created: {exchange_id}")
            print(f"💸 [INFO] Now sending {estimated_eth_amount:.6f} ETH to ChangeNOW...")
            
            # Send ETH to ChangeNOW payin address
            send_result = await self.eth_wallet_manager.send_eth(
                to_address=payin_address,
                amount_eth=estimated_eth_amount
            )
            
            if not send_result["success"]:
                return {
                    "success": False,
                    "error": f"ETH transfer failed: {send_result['error']}",
                    "exchange_id": exchange_id  # Include for potential refund
                }
            
            tx_hash = send_result["tx_hash"]
            print(f"🚀 [SUCCESS] ETH sent successfully: {tx_hash}")
            
            # Record swap transaction in database
            swap_data = {
                "user_id": user_id,
                "order_id": exchange_order_id,
                "exchange_id": exchange_id,
                "subscription_price_usd": float(subscription_price_usd),
                "swap_amount_usd": swap_amount_usd,
                "eth_amount_sent": estimated_eth_amount,
                "target_currency": client_payout_currency.upper(),
                "client_wallet_address": client_wallet_address,
                "expected_output": expected_amount,
                "eth_tx_hash": tx_hash,
                "payin_address": payin_address,
                "swap_status": "processing"
            }
            
            if self.swap_db_manager:
                record_id = self.swap_db_manager.record_swap_transaction(swap_data)
                if record_id:
                    print(f"📊 [INFO] Swap recorded in database with ID: {record_id}")
                else:
                    print(f"⚠️ [WARNING] Failed to record swap in database")
            
            # Return successful swap result
            result = {
                "success": True,
                "user_id": user_id,
                "subscription_price_usd": subscription_price_usd,
                "swap_amount_usd": swap_amount_usd,
                "eth_amount_sent": estimated_eth_amount,
                "target_currency": client_payout_currency.upper(),
                "client_wallet": client_wallet_address,
                "expected_output": expected_amount,
                "exchange_id": exchange_id,
                "eth_tx_hash": tx_hash,
                "payin_address": payin_address,
                "order_id": exchange_order_id
            }
            
            print(f"🎉 [SUCCESS] ChangeNOW swap completed for user {user_id}")
            print(f"🔗 [INFO] Exchange ID: {exchange_id}")
            print(f"💰 [INFO] Expected output: {expected_amount} {client_payout_currency.upper()}")
            
            return result
            
        except Exception as e:
            error_msg = f"ChangeNOW swap process failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {"success": False, "error": error_msg}
    
    async def check_swap_status(self, exchange_id: str) -> Dict[str, Any]:
        """
        Check the status of a ChangeNOW swap.
        
        Args:
            exchange_id: ChangeNOW exchange ID
            
        Returns:
            Dictionary with swap status
        """
        try:
            if not self.changenow_manager:
                success, error = await self.initialize_managers()
                if not success:
                    return {"success": False, "error": error}
            
            status_result = await self.changenow_manager.get_exchange_status(exchange_id)
            return status_result
            
        except Exception as e:
            error_msg = f"Swap status check failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {"success": False, "error": error_msg}