#!/usr/bin/env python
"""
Comprehensive Logging Utility for ChangeNOW Integration
Provides structured logging for all swap operations with detailed error tracking
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional


class SwapLogger:
    """Centralized logger for ChangeNOW swap operations."""
    
    def __init__(self, user_id: int = None, exchange_id: str = None):
        """
        Initialize swap logger with context information.
        
        Args:
            user_id: User's Telegram ID for context
            exchange_id: ChangeNOW exchange ID for tracking
        """
        self.user_id = user_id
        self.exchange_id = exchange_id
        self.start_time = time.time()
        
    def _get_timestamp(self) -> str:
        """Get formatted timestamp for logging."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _get_elapsed(self) -> str:
        """Get elapsed time since logger initialization."""
        elapsed = time.time() - self.start_time
        return f"{elapsed:.2f}s"
    
    def _format_context(self) -> str:
        """Format context information for logging."""
        context_parts = []
        if self.user_id:
            context_parts.append(f"User:{self.user_id}")
        if self.exchange_id:
            context_parts.append(f"Exchange:{self.exchange_id}")
        
        if context_parts:
            return f"[{' | '.join(context_parts)}]"
        return ""
    
    def log_swap_start(self, from_currency: str, to_currency: str, amount: float, 
                      client_wallet: str) -> None:
        """Log the start of a swap operation."""
        context = self._format_context()
        print(f"🚀 [SWAP_START] {context} {self._get_timestamp()}")
        print(f"💱 [SWAP_DETAILS] {amount} {from_currency.upper()} → {to_currency.upper()}")
        print(f"📍 [CLIENT_WALLET] {client_wallet}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
        print(f"{'='*80}")
    
    def log_validation_start(self, currency: str, address: str) -> None:
        """Log validation process start."""
        context = self._format_context()
        print(f"🔍 [VALIDATION_START] {context} Validating {currency.upper()} address")
        print(f"📍 [ADDRESS] {address}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
    
    def log_validation_result(self, currency: str, address: str, is_valid: bool, 
                            message: str) -> None:
        """Log validation result."""
        context = self._format_context()
        status_icon = "✅" if is_valid else "❌"
        status_text = "VALID" if is_valid else "INVALID"
        
        print(f"{status_icon} [VALIDATION_{status_text}] {context} {currency.upper()} address validation")
        print(f"📍 [ADDRESS] {address}")
        print(f"💬 [MESSAGE] {message}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
    
    def log_estimation_start(self, from_currency: str, to_currency: str, amount: float) -> None:
        """Log exchange estimation start."""
        context = self._format_context()
        print(f"📊 [ESTIMATION_START] {context} Getting exchange rate")
        print(f"💱 [PAIR] {amount} {from_currency.upper()} → {to_currency.upper()}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
    
    def log_estimation_result(self, from_currency: str, to_currency: str, from_amount: float,
                            estimated_amount: str, min_amount: str, max_amount: str) -> None:
        """Log exchange estimation result."""
        context = self._format_context()
        print(f"✅ [ESTIMATION_SUCCESS] {context} Exchange rate retrieved")
        print(f"💱 [CONVERSION] {from_amount} {from_currency.upper()} → {estimated_amount} {to_currency.upper()}")
        print(f"📊 [LIMITS] Min: {min_amount}, Max: {max_amount}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
    
    def log_exchange_creation_start(self, payload: Dict[str, Any]) -> None:
        """Log ChangeNOW exchange creation start."""
        context = self._format_context()
        print(f"🔄 [EXCHANGE_CREATE_START] {context} Creating ChangeNOW exchange")
        print(f"📤 [PAYLOAD] From: {payload.get('from', 'unknown').upper()}")
        print(f"📤 [PAYLOAD] To: {payload.get('to', 'unknown').upper()}")
        print(f"📤 [PAYLOAD] Amount: {payload.get('amount', 'unknown')}")
        print(f"📤 [PAYLOAD] Address: {payload.get('address', 'unknown')}")
        print(f"📤 [PAYLOAD] Refund: {payload.get('refundAddress', 'none')}")
        print(f"📤 [PAYLOAD] User ID: {payload.get('userId', 'unknown')}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
    
    def log_exchange_creation_success(self, exchange_data: Dict[str, Any]) -> None:
        """Log successful ChangeNOW exchange creation."""
        context = self._format_context()
        exchange_id = exchange_data.get("id", "unknown")
        payin_address = exchange_data.get("payinAddress", "unknown")
        expected_amount = exchange_data.get("expectedReceiveAmount", "unknown")
        
        # Update context with exchange ID if not already set
        if not self.exchange_id and exchange_id != "unknown":
            self.exchange_id = exchange_id
        
        print(f"✅ [EXCHANGE_CREATE_SUCCESS] {context} ChangeNOW exchange created")
        print(f"🔗 [EXCHANGE_ID] {exchange_id}")
        print(f"📍 [PAYIN_ADDRESS] {payin_address}")
        print(f"📈 [EXPECTED_OUTPUT] {expected_amount}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
        
        # Log additional fields if present
        if "status" in exchange_data:
            print(f"📊 [INITIAL_STATUS] {exchange_data['status']}")
        if "validUntil" in exchange_data:
            print(f"⏰ [VALID_UNTIL] {exchange_data['validUntil']}")
    
    def log_eth_transaction_start(self, to_address: str, amount_eth: float, gas_info: Dict[str, Any]) -> None:
        """Log ETH transaction start."""
        context = self._format_context()
        print(f"💸 [ETH_TX_START] {context} Sending ETH to ChangeNOW")
        print(f"📍 [TO_ADDRESS] {to_address}")
        print(f"💰 [AMOUNT] {amount_eth} ETH")
        print(f"⛽ [GAS_LIMIT] {gas_info.get('gas_limit', 'unknown')}")
        print(f"⛽ [GAS_PRICE] {gas_info.get('gas_price', 'unknown')} wei")
        print(f"⛽ [GAS_COST] {gas_info.get('gas_cost_eth', 'unknown')} ETH")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
    
    def log_eth_transaction_success(self, tx_result: Dict[str, Any]) -> None:
        """Log successful ETH transaction."""
        context = self._format_context()
        tx_hash = tx_result.get("tx_hash", "unknown")
        amount_eth = tx_result.get("amount_eth", "unknown")
        
        print(f"✅ [ETH_TX_SUCCESS] {context} ETH transaction sent successfully")
        print(f"🔗 [TX_HASH] {tx_hash}")
        print(f"💰 [AMOUNT_SENT] {amount_eth} ETH")
        print(f"📍 [TO_ADDRESS] {tx_result.get('to_address', 'unknown')}")
        print(f"🔢 [NONCE] {tx_result.get('nonce', 'unknown')}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
    
    def log_database_operation(self, operation: str, data: Dict[str, Any], success: bool, 
                              record_id: Optional[int] = None) -> None:
        """Log database operation."""
        context = self._format_context()
        status_icon = "✅" if success else "❌"
        status_text = "SUCCESS" if success else "FAILED"
        
        print(f"{status_icon} [DB_{operation.upper()}_{status_text}] {context} Database operation")
        if record_id:
            print(f"🔢 [RECORD_ID] {record_id}")
        print(f"📊 [DATA] Exchange: {data.get('exchange_id', 'unknown')}")
        print(f"📊 [DATA] Status: {data.get('swap_status', 'unknown')}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
    
    def log_swap_completion(self, success: bool, result: Dict[str, Any]) -> None:
        """Log final swap completion."""
        context = self._format_context()
        status_icon = "✅" if success else "❌"
        status_text = "SUCCESS" if success else "FAILED"
        
        print(f"{'='*80}")
        print(f"{status_icon} [SWAP_{status_text}] {context} Swap process completed")
        print(f"⏱️ [TOTAL_TIME] {self._get_elapsed()}")
        
        if success:
            print(f"🔗 [EXCHANGE_ID] {result.get('exchange_id', 'unknown')}")
            print(f"💰 [ETH_SENT] {result.get('eth_amount_sent', 'unknown')} ETH")
            print(f"📈 [EXPECTED_OUTPUT] {result.get('expected_output', 'unknown')} {result.get('target_currency', 'unknown')}")
            print(f"🔐 [ETH_TX_HASH] {result.get('eth_tx_hash', 'unknown')}")
        else:
            print(f"❌ [ERROR] {result.get('error', 'Unknown error')}")
        
        print(f"⏱️ [FINAL_ELAPSED] {self._get_elapsed()}")
        print(f"🏁 [TIMESTAMP] {self._get_timestamp()}")
        print(f"{'='*80}")
    
    def log_error(self, operation: str, error: Exception, additional_context: Dict[str, Any] = None) -> None:
        """Log detailed error information."""
        context = self._format_context()
        print(f"❌ [ERROR_{operation.upper()}] {context} Operation failed")
        print(f"🔍 [ERROR_TYPE] {type(error).__name__}")
        print(f"💬 [ERROR_MESSAGE] {str(error)}")
        print(f"📊 [ERROR_ARGS] {error.args}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
        
        if additional_context:
            for key, value in additional_context.items():
                print(f"📝 [CONTEXT_{key.upper()}] {value}")
    
    def log_api_response(self, endpoint: str, method: str, status_code: int, 
                        response_data: Any, request_data: Any = None) -> None:
        """Log detailed API response information."""
        context = self._format_context()
        status_icon = "✅" if 200 <= status_code < 300 else "❌"
        
        print(f"{status_icon} [API_RESPONSE] {context} {method} {endpoint}")
        print(f"📊 [STATUS_CODE] {status_code}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
        
        if request_data:
            print(f"📤 [REQUEST_DATA] {request_data}")
        
        if isinstance(response_data, dict):
            # Log key response fields
            for key, value in response_data.items():
                if key in ["id", "status", "payinAddress", "expectedReceiveAmount", "error", "message"]:
                    print(f"📥 [RESPONSE_{key.upper()}] {value}")
        else:
            print(f"📥 [RESPONSE_DATA] {response_data}")
    
    def log_status_check(self, exchange_id: str, status: str, status_data: Dict[str, Any]) -> None:
        """Log ChangeNOW status check results."""
        context = self._format_context()
        
        # Status-specific icons
        status_icons = {
            "new": "🆕",
            "waiting": "⏳", 
            "confirming": "🔄",
            "exchanging": "🔄",
            "sending": "📤",
            "finished": "✅",
            "failed": "❌",
            "refunded": "🔄",
            "expired": "⏰"
        }
        
        icon = status_icons.get(status.lower(), "📊")
        
        print(f"{icon} [STATUS_CHECK] {context} Exchange status update")
        print(f"🔗 [EXCHANGE_ID] {exchange_id}")
        print(f"📊 [STATUS] {status}")
        print(f"💰 [DEPOSIT_RECEIVED] {status_data.get('depositReceived', '0')}")
        print(f"📈 [EXPECTED_AMOUNT] {status_data.get('expectedReceiveAmount', 'unknown')}")
        print(f"💰 [ACTUAL_AMOUNT] {status_data.get('actualReceiveAmount', '0')}")
        print(f"⏱️ [ELAPSED] {self._get_elapsed()}")
        
        # Log transaction hashes if available
        if "payoutHash" in status_data:
            print(f"🔗 [PAYOUT_HASH] {status_data['payoutHash']}")
        if "refundHash" in status_data:
            print(f"🔗 [REFUND_HASH] {status_data['refundHash']}")
        if "error" in status_data:
            print(f"❌ [ERROR_REASON] {status_data['error']}")