#!/usr/bin/env python
"""
DEX Swapper - Automated ETH to ERC20 token swapping using 1INCH DEX aggregator.
Handles automatic token acquisition for the payment splitting system.
"""
import time
import requests
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from web3 import Web3
from token_registry import TokenRegistry, TokenInfo
from market_data_provider import RealTimeMarketDataProvider

@dataclass
class SwapConfig:
    """Configuration for DEX swap parameters."""
    max_slippage_percent: float = 1.0  # 1% maximum slippage
    max_eth_per_swap: float = 0.1  # Maximum 0.1 ETH per swap
    min_eth_reserve: float = 0.001  # Keep 0.001 ETH minimum for gas
    swap_timeout_seconds: int = 30  # API timeout
    enable_swapping: bool = True  # Global swap enable/disable

class DEXSwapper:
    """Handles ETH to ERC20 token swaps using 1INCH DEX aggregator."""
    
    def __init__(self, w3: Web3, oneinch_api_key: str, host_address: str, private_key: str, 
                 swap_config: SwapConfig = None, config_manager=None):
        """
        Initialize the DEX swapper with rate validation.
        
        Args:
            w3: Web3 instance
            oneinch_api_key: 1INCH API key for DEX access
            host_address: Host wallet address
            private_key: Host wallet private key
            swap_config: Swap configuration parameters
            config_manager: Optional ConfigManager for market data API keys
        """
        self.w3 = w3
        self.oneinch_api_key = oneinch_api_key
        self.host_address = Web3.to_checksum_address(host_address)
        self.private_key = private_key
        self.config = swap_config or SwapConfig()
        self.token_registry = TokenRegistry()
        self.chain_id = w3.eth.chain_id
        
        # Initialize market data provider for rate validation
        self.market_data_provider = RealTimeMarketDataProvider(config_manager=config_manager)
        
        # 1INCH API endpoints
        self.swap_api_base = f"https://api.1inch.dev/swap/v6.0/{self.chain_id}"
        self.quote_endpoint = f"{self.swap_api_base}/quote"
        self.swap_endpoint = f"{self.swap_api_base}/swap"
        
        # Strict rate limiting for 1INCH API (1 RPS limit)
        self.last_api_call_time = 0
        self.last_api_response_time = 0  # Track when API response was received
        self.min_request_interval = 1.2  # 1200ms buffer above 1s limit (50 req/min max)
        self.rate_limit_delay = 2.0  # 2 second base delay after 429 errors
        self.consecutive_429_count = 0  # Track consecutive 429 errors for exponential backoff
        
        print(f"🔄 [INFO] DEX Swapper initialized for chain {self.chain_id} with rate validation")
        print(f"⚙️ [INFO] Swap config: max_slippage={self.config.max_slippage_percent}%, max_eth={self.config.max_eth_per_swap} ETH")
        print(f"📊 [INFO] Market data validation: {len([s for s in self.market_data_provider.price_sources.values() if s['enabled']])} sources enabled")
        print(f"🚦 [INFO] Rate limiting: {self.min_request_interval}s between API calls, {self.rate_limit_delay}s after 429 errors")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for 1INCH API requests."""
        return {
            'Authorization': f'Bearer {self.oneinch_api_key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def _get_token_address(self, token_symbol: str) -> Optional[str]:
        """
        Get token contract address for a given symbol.
        
        Args:
            token_symbol: Token symbol (e.g., "LINK", "USDT")
            
        Returns:
            Token contract address or None if not found
        """
        if token_symbol.upper() == "ETH":
            return "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"  # ETH address in 1INCH
        
        token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
        return token_info.address if token_info else None
    
    def _validate_swap_rate(self, from_token: str, to_token: str, eth_amount: float, expected_token_amount: float) -> Dict[str, Any]:
        """
        Validate swap rate against market data to prevent rate calculation errors.
        
        Args:
            from_token: Source token (typically "ETH")
            to_token: Target token (e.g., "LINK")
            eth_amount: Amount of ETH being swapped
            expected_token_amount: Expected amount of tokens to receive
            
        Returns:
            Validation result dictionary
        """
        try:
            print(f"🔍 [INFO] Validating swap rate: {eth_amount:.6f} {from_token} → {expected_token_amount:.6f} {to_token}")
            
            # Get market rates for both tokens
            if from_token.upper() == "ETH":
                eth_price_result = self.market_data_provider.get_token_price("ETH")
            else:
                eth_price_result = {'success': False, 'error': 'Only ETH swaps supported for validation'}
            
            to_token_price_result = self.market_data_provider.get_token_price(to_token)
            
            if not eth_price_result['success'] or not to_token_price_result['success']:
                # If we can't validate, allow the swap but log warning
                print(f"⚠️ [WARNING] Cannot validate swap rate - market data unavailable")
                print(f"🔍 [DEBUG] ETH price: {eth_price_result.get('error', 'unknown')}")
                print(f"🔍 [DEBUG] {to_token} price: {to_token_price_result.get('error', 'unknown')}")
                return {
                    'valid': True,  # Allow swap to proceed
                    'validated': False,
                    'reason': 'Market data unavailable for validation',
                    'warning': True
                }
            
            # Calculate expected conversion based on market rates
            eth_usd_value = eth_amount * eth_price_result['usd_per_token']
            expected_tokens_from_market = eth_usd_value * to_token_price_result['tokens_per_usd']
            
            # Calculate deviation
            deviation = abs(expected_token_amount - expected_tokens_from_market) / expected_tokens_from_market
            
            print(f"📊 [INFO] Rate validation:")
            print(f"  💱 ETH price: ${eth_price_result['usd_per_token']:.2f} (sources: {', '.join(eth_price_result['sources_used'])})")
            print(f"  💱 {to_token} price: ${to_token_price_result['usd_per_token']:.6f} (sources: {', '.join(to_token_price_result['sources_used'])})")
            print(f"  💰 ETH USD value: ${eth_usd_value:.2f}")
            print(f"  🎯 Expected {to_token} from market: {expected_tokens_from_market:.6f}")
            print(f"  🔄 1INCH quote amount: {expected_token_amount:.6f}")
            print(f"  📈 Deviation: {deviation:.1%}")
            
            # Set deviation threshold (10% for now, can be made configurable)
            max_deviation = 0.10  # 10%
            
            if deviation > max_deviation:
                return {
                    'valid': False,
                    'validated': True,
                    'reason': f'Swap rate deviates {deviation:.1%} from market rate (max: {max_deviation:.1%})',
                    'market_data': {
                        'eth_price': eth_price_result['usd_per_token'],
                        'token_price': to_token_price_result['usd_per_token'],
                        'expected_from_market': expected_tokens_from_market,
                        'quote_amount': expected_token_amount,
                        'deviation': deviation
                    },
                    'severity': 'high' if deviation > 0.25 else 'medium'
                }
            else:
                return {
                    'valid': True,
                    'validated': True,
                    'reason': f'Swap rate within acceptable range (deviation: {deviation:.1%})',
                    'market_data': {
                        'eth_price': eth_price_result['usd_per_token'],
                        'token_price': to_token_price_result['usd_per_token'],
                        'expected_from_market': expected_tokens_from_market,
                        'quote_amount': expected_token_amount,
                        'deviation': deviation
                    }
                }
                
        except Exception as e:
            print(f"❌ [ERROR] Rate validation failed: {e}")
            return {
                'valid': True,  # Allow swap to proceed if validation fails
                'validated': False,
                'reason': f'Validation error: {str(e)}',
                'error': True
            }
    
    def get_swap_quote(self, from_token: str, to_token: str, amount_wei: int) -> Dict[str, Any]:
        """
        Get a swap quote from 1INCH without executing the swap.
        
        Args:
            from_token: Source token symbol (typically "ETH")
            to_token: Target token symbol (e.g., "LINK", "USDT")
            amount_wei: Amount to swap in Wei
            
        Returns:
            Dictionary with quote information
        """
        try:
            from_address = self._get_token_address(from_token)
            to_address = self._get_token_address(to_token)
            
            if not from_address or not to_address:
                return {
                    'success': False,
                    'error': f'Token address not found: from={from_token}, to={to_token}'
                }
            
            params = {
                'src': from_address,
                'dst': to_address,
                'amount': str(amount_wei),
                'includeTokensInfo': 'true',
                'includeProtocols': 'true',
                'includeGas': 'true'
            }
            
            amount_eth = float(self.w3.from_wei(amount_wei, 'ether'))
            print(f"🔍 [INFO] Getting 1INCH quote: {amount_eth:.6f} ETH ({amount_wei} Wei) {from_token} → {to_token}")
            print(f"🔗 [DEBUG] Quote endpoint: {self.quote_endpoint}")
            print(f"📝 [DEBUG] Quote params: src={from_address[:10]}..., dst={to_address[:10]}..., amount={amount_wei}")
            
            # Strict rate limiting to avoid 429 errors (1 RPS limit)
            current_time = time.time()
            
            # Calculate time since last API call AND response to ensure proper spacing
            time_since_last_call = current_time - self.last_api_call_time
            time_since_last_response = current_time - self.last_api_response_time
            
            # Use the more restrictive of call time or response time
            time_since_last_activity = min(time_since_last_call, time_since_last_response)
            
            if time_since_last_activity < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_activity
                print(f"🚦 [INFO] Rate limiting: waiting {sleep_time:.2f}s before API call (1 RPS limit)")
                time.sleep(sleep_time)
            
            # Record when we start the API call
            self.last_api_call_time = time.time()
            
            response = requests.get(
                self.quote_endpoint,
                params=params,
                headers=self._get_headers(),
                timeout=self.config.swap_timeout_seconds
            )
            
            # Record when we received the API response for rate limiting
            self.last_api_response_time = time.time()
            
            print(f"📡 [DEBUG] 1INCH API response status: {response.status_code}")
            
            if response.status_code == 200:
                quote_data = response.json()
                
                # Validate quote response structure
                validation_result = self._validate_quote_response(quote_data, from_token, to_token, amount_wei)
                if not validation_result['valid']:
                    print(f"❌ [ERROR] Quote response validation failed: {validation_result['error']}")
                    return {
                        'success': False,
                        'error': f"Invalid quote response: {validation_result['error']}",
                        'validation_details': validation_result
                    }
                
                # Extract key information - CRITICAL FIX for parsing bug
                # 1INCH API v6 uses different field names than expected
                from_amount = int(quote_data.get('fromTokenAmount', amount_wei))  # Use input amount as fallback
                to_amount = int(quote_data.get('dstAmount', 0))  # FIXED: Use 'dstAmount' not 'toTokenAmount'
                gas_estimate = int(quote_data.get('gas', 0))  # FIXED: Use 'gas' not 'estimatedGas'
                
                # Log the actual field names for debugging
                print(f"🔍 [DEBUG] API response fields: {list(quote_data.keys())}")
                print(f"🔍 [DEBUG] fromTokenAmount: {quote_data.get('fromTokenAmount', 'MISSING')}")
                print(f"🔍 [DEBUG] dstAmount: {quote_data.get('dstAmount', 'MISSING')}")
                print(f"🔍 [DEBUG] gas: {quote_data.get('gas', 'MISSING')}")
                
                # Enhanced logging for debugging
                to_amount_readable = to_amount / (10 ** 18) if to_token != 'ETH' else to_amount  # Assume 18 decimals for debugging
                print(f"📊 [DEBUG] Quote result: {from_amount} Wei in → {to_amount} Wei out (~{to_amount_readable:.6f} {to_token})")
                print(f"⛽ [DEBUG] Estimated gas: {gas_estimate}")
                
                # Check for zero token output and log additional details
                if to_amount == 0:
                    print(f"⚠️ [WARNING] Quote returned ZERO tokens for {amount_eth:.6f} ETH → {to_token}")
                    print(f"🔍 [DEBUG] Raw quote response: {quote_data}")
                    # Log specific fields that might indicate why
                    if 'protocols' in quote_data:
                        protocols = quote_data.get('protocols', [])
                        print(f"🔗 [DEBUG] Available protocols: {len(protocols)} protocols found")
                    if 'error' in quote_data:
                        print(f"❌ [DEBUG] API error in response: {quote_data['error']}")
                
                # Reset consecutive 429 count on successful response
                self.consecutive_429_count = 0
                
                return {
                    'success': True,
                    'from_token': from_token,
                    'to_token': to_token,
                    'from_amount_wei': from_amount,
                    'to_amount_wei': to_amount,
                    'from_amount_eth': float(self.w3.from_wei(from_amount, 'ether')),
                    'gas_estimate': gas_estimate,
                    'quote_data': quote_data,
                    'validation': validation_result
                }
            else:
                error_msg = f"1INCH quote failed: {response.status_code} - {response.text}"
                print(f"❌ [ERROR] {error_msg}")
                print(f"🔗 [DEBUG] Failed request URL: {self.quote_endpoint}")
                print(f"📝 [DEBUG] Request params: {params}")
                
                # Enhanced handling for rate limit errors with exponential backoff
                if response.status_code == 429:
                    self.consecutive_429_count += 1
                    # Exponential backoff: 3s, 6s, 12s, max 30s
                    adaptive_delay = min(self.rate_limit_delay * (2 ** (self.consecutive_429_count - 1)), 30.0)
                    print(f"🚦 [WARNING] Rate limit hit (429) - attempt #{self.consecutive_429_count}")
                    print(f"⏳ [INFO] Implementing exponential backoff: {adaptive_delay:.1f}s delay")
                    # Update the last call time to include the extra delay
                    self.last_api_call_time = time.time() + adaptive_delay
                else:
                    # Reset consecutive 429 count on any successful or non-429 response
                    self.consecutive_429_count = 0
                
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code,
                    'is_rate_limit': response.status_code == 429
                }
                
        except Exception as e:
            error_msg = f"Quote request failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def _get_quote_with_429_retry(self, from_token: str, to_token: str, amount_wei: int, max_retries: int = 3) -> Dict[str, Any]:
        """
        Get a quote with specific retry logic for 429 rate limit errors.
        
        Args:
            from_token: Source token symbol
            to_token: Target token symbol  
            amount_wei: Amount in Wei
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary with quote result
        """
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # For 429 retries, use escalating delays
                    base_delay = self.rate_limit_delay  # 2.0s base
                    wait_time = base_delay * (2 ** (attempt - 1))  # 2s, 4s, 8s
                    print(f"🔄 [INFO] 429 retry attempt {attempt + 1}/{max_retries} after {wait_time:.1f}s delay")
                    time.sleep(wait_time)
                
                quote_result = self.get_swap_quote(from_token, to_token, amount_wei)
                
                if quote_result['success']:
                    if attempt > 0:
                        print(f"✅ [SUCCESS] Quote succeeded on 429 retry attempt {attempt + 1}")
                    return quote_result
                else:
                    # Check if this is a 429 error specifically
                    is_rate_limit = quote_result.get('is_rate_limit', False)
                    error_msg = quote_result.get('error', 'Unknown error')
                    
                    if is_rate_limit and attempt < max_retries - 1:
                        print(f"🚦 [WARNING] 429 rate limit on attempt {attempt + 1}, will retry...")
                        continue
                    else:
                        # Non-429 error or final attempt - return the error
                        print(f"❌ [ERROR] Quote failed on attempt {attempt + 1}: {error_msg}")
                        return quote_result
                        
            except Exception as e:
                print(f"❌ [ERROR] Quote attempt {attempt + 1} exception: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1.0)  # Brief delay before retry
                    continue
                else:
                    return {
                        'success': False,
                        'error': f'All quote attempts failed: {str(e)}'
                    }
        
        # If we get here, all retries failed
        return {
            'success': False,
            'error': f'Quote failed after {max_retries} attempts due to persistent 429 rate limits'
        }
    
    def _get_quote_with_retry(self, from_token: str, to_token: str, amount_wei: int, max_retries: int = 3) -> Dict[str, Any]:
        """
        Get a quote with retry logic and intelligent rate limit handling.
        
        Args:
            from_token: Source token symbol
            to_token: Target token symbol
            amount_wei: Amount in Wei
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary with quote result
        """
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # For 429 errors, use longer delay; otherwise exponential backoff
                    wait_time = 2 ** (attempt - 1)
                    print(f"⏳ [INFO] Retry attempt {attempt + 1}/{max_retries} after {wait_time}s delay")
                    time.sleep(wait_time)
                
                quote_result = self.get_swap_quote(from_token, to_token, amount_wei)
                
                if quote_result['success']:
                    if attempt > 0:
                        print(f"✅ [SUCCESS] Quote succeeded on retry attempt {attempt + 1}")
                    return quote_result
                else:
                    error_msg = quote_result.get('error', 'Unknown error')
                    is_rate_limit = quote_result.get('is_rate_limit', False)
                    
                    print(f"⚠️ [WARNING] Quote attempt {attempt + 1} failed: {error_msg}")
                    
                    # For rate limit errors, add extra delay before next retry
                    if is_rate_limit and attempt < max_retries - 1:
                        extra_delay = self.rate_limit_delay
                        print(f"🚦 [INFO] Rate limit detected - adding extra {extra_delay}s delay")
                        time.sleep(extra_delay)
                    
            except Exception as e:
                print(f"❌ [ERROR] Quote attempt {attempt + 1} exception: {e}")
                
        print(f"❌ [ERROR] All {max_retries} quote attempts failed")
        return {
            'success': False,
            'error': f'Quote failed after {max_retries} attempts with intelligent retries'
        }
    
    def _analyze_quote_failures(self, from_token: str, to_token: str, attempted_amounts: list) -> Dict[str, Any]:
        """
        Analyze quote failures and provide specific diagnostics and suggestions.
        
        Args:
            from_token: Source token that failed
            to_token: Target token that failed
            attempted_amounts: List of ETH amounts that were attempted
            
        Returns:
            Dictionary with failure analysis and suggestions
        """
        analysis = {
            'failure_type': 'unknown',
            'suggested_actions': [],
            'diagnostics': {},
            'severity': 'medium'
        }
        
        try:
            # Check if it's a common token pair issue
            if to_token.upper() in ['LINK', 'UNI', 'AAVE']:
                analysis['failure_type'] = 'low_liquidity_token'
                analysis['suggested_actions'] = [
                    f"🔄 Try increasing ETH amount above {max(attempted_amounts):.3f} ETH",
                    f"📊 Check {to_token} market conditions and liquidity",
                    f"💱 Consider using a more liquid token (USDT, USDC, DAI)",
                    f"⏰ Try again during different market hours for better liquidity"
                ]
                analysis['severity'] = 'high'
                
            elif to_token.upper() in ['USDT', 'USDC', 'DAI']:
                analysis['failure_type'] = 'stablecoin_issue'
                analysis['suggested_actions'] = [
                    f"🔧 Check 1INCH API key configuration and permissions",
                    f"🌐 Verify network connectivity to 1INCH API",
                    f"💰 Ensure ETH amount is sufficient (try 0.01+ ETH)",
                    f"🔄 Try alternative DEX or manual token acquisition"
                ]
                analysis['severity'] = 'critical'
                
            else:
                analysis['failure_type'] = 'general_quote_failure'
                analysis['suggested_actions'] = [
                    f"📊 Verify {to_token} is actively traded on DEXs",
                    f"🔍 Check token contract address in registry",
                    f"💰 Increase ETH amount for better liquidity",
                    f"🔧 Verify 1INCH API configuration"
                ]
                
            # Add general diagnostics
            analysis['diagnostics'] = {
                'attempted_amounts_eth': attempted_amounts,
                'min_attempted': min(attempted_amounts),
                'max_attempted': max(attempted_amounts),
                'token_pair': f"{from_token} → {to_token}",
                'chain_id': self.chain_id,
                'api_endpoint': self.quote_endpoint
            }
            
            # Log the analysis
            print(f"🔍 [ANALYSIS] Quote failure analysis:")
            print(f"  📋 Failure type: {analysis['failure_type']}")
            print(f"  ⚠️ Severity: {analysis['severity']}")
            print(f"  💡 Suggestions:")
            for action in analysis['suggested_actions']:
                print(f"    {action}")
                
        except Exception as e:
            print(f"❌ [ERROR] Error analysis failed: {e}")
            analysis['failure_type'] = 'analysis_error'
            analysis['suggested_actions'] = [
                "🔧 Check system configuration and try again",
                "💰 Ensure sufficient ETH balance for swapping",
                "📞 Contact support if issues persist"
            ]
            
        return analysis
    
    def _validate_quote_response(self, quote_data: dict, from_token: str, to_token: str, amount_wei: int) -> Dict[str, Any]:
        """
        Validate 1INCH quote response to catch parsing issues early.
        
        Args:
            quote_data: Raw API response data
            from_token: Expected source token
            to_token: Expected destination token
            amount_wei: Expected input amount
            
        Returns:
            Dictionary with validation result and details
        """
        validation = {
            'valid': True,
            'error': None,
            'warnings': [],
            'fields_found': list(quote_data.keys()) if isinstance(quote_data, dict) else []
        }
        
        try:
            # Check basic structure
            if not isinstance(quote_data, dict):
                validation['valid'] = False
                validation['error'] = f"Response is not a dictionary: {type(quote_data)}"
                return validation
            
            # Check for essential fields
            required_fields = ['dstAmount']  # Critical field that was being missed
            optional_fields = ['fromTokenAmount', 'gas', 'srcToken', 'dstToken', 'protocols']
            
            missing_required = [field for field in required_fields if field not in quote_data]
            if missing_required:
                validation['valid'] = False
                validation['error'] = f"Missing required fields: {missing_required}"
                return validation
            
            missing_optional = [field for field in optional_fields if field not in quote_data]
            if missing_optional:
                validation['warnings'].append(f"Missing optional fields: {missing_optional}")
            
            # Validate dstAmount is a valid number
            dst_amount = quote_data.get('dstAmount')
            if dst_amount is None:
                validation['valid'] = False
                validation['error'] = "dstAmount is None"
                return validation
                
            try:
                dst_amount_int = int(dst_amount)
                if dst_amount_int < 0:
                    validation['warnings'].append("dstAmount is negative")
            except (ValueError, TypeError):
                validation['valid'] = False
                validation['error'] = f"dstAmount is not a valid number: {dst_amount} ({type(dst_amount)})"
                return validation
            
            # Check token information if present
            if 'srcToken' in quote_data:
                src_token_data = quote_data['srcToken']
                if isinstance(src_token_data, dict):
                    src_symbol = src_token_data.get('symbol', '').upper()
                    if src_symbol and src_symbol != from_token.upper():
                        validation['warnings'].append(f"Source token mismatch: expected {from_token}, got {src_symbol}")
            
            if 'dstToken' in quote_data:
                dst_token_data = quote_data['dstToken']
                if isinstance(dst_token_data, dict):
                    dst_symbol = dst_token_data.get('symbol', '').upper()
                    if dst_symbol and dst_symbol != to_token.upper():
                        validation['warnings'].append(f"Destination token mismatch: expected {to_token}, got {dst_symbol}")
            
            # Check for error field in response
            if 'error' in quote_data:
                validation['warnings'].append(f"API response contains error field: {quote_data['error']}")
            
            # Log validation results
            if validation['warnings']:
                print(f"⚠️ [VALIDATION] Quote response warnings: {', '.join(validation['warnings'])}")
            
            print(f"✅ [VALIDATION] Quote response structure validated successfully")
            
        except Exception as e:
            validation['valid'] = False
            validation['error'] = f"Validation exception: {str(e)}"
            print(f"❌ [ERROR] Quote validation failed: {e}")
        
        return validation

    def _try_progressive_quotes(self, from_token: str, to_token: str, quote_amounts_eth: list) -> Dict[str, Any]:
        """
        Try multiple quote amounts progressively with retry logic until we get a valid quote.
        
        Args:
            from_token: Source token symbol
            to_token: Target token symbol  
            quote_amounts_eth: List of ETH amounts to try (in descending order)
            
        Returns:
            Dictionary with quote result or failure
        """
        print(f"🔄 [INFO] Attempting progressive quotes for {from_token} → {to_token}")
        
        for i, eth_amount in enumerate(quote_amounts_eth):
            try:
                eth_wei = self.w3.to_wei(eth_amount, 'ether')
                print(f"🔍 [INFO] Quote attempt {i+1}/{len(quote_amounts_eth)}: {eth_amount:.6f} ETH")
                
                # Use retry logic for each amount
                quote_result = self._get_quote_with_retry(from_token, to_token, eth_wei, max_retries=2)
                
                if quote_result['success'] and quote_result['to_amount_wei'] > 0:
                    print(f"✅ [SUCCESS] Quote successful with {eth_amount:.6f} ETH")
                    return quote_result
                else:
                    print(f"⚠️ [WARNING] Quote attempt {i+1} failed or returned zero tokens")
                    if quote_result.get('error'):
                        print(f"🔍 [DEBUG] Error: {quote_result['error']}")
                        
            except Exception as e:
                print(f"❌ [ERROR] Quote attempt {i+1} exception: {e}")
                continue
        
        # Provide comprehensive error analysis and suggestions
        error_analysis = self._analyze_quote_failures(from_token, to_token, quote_amounts_eth)
        
        return {
            'success': False,
            'error': f'All progressive quote attempts with retries failed for {from_token} → {to_token}',
            'error_analysis': error_analysis
        }
    
    def calculate_eth_needed_for_tokens(self, token_symbol: str, token_amount: float) -> Dict[str, Any]:
        """
        Calculate how much ETH is needed to acquire a specific amount of tokens.
        Enhanced with progressive quote attempts and better validation.
        
        Args:
            token_symbol: Target token symbol
            token_amount: Desired amount of tokens
            
        Returns:
            Dictionary with ETH calculation results
        """
        try:
            token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
            if not token_info:
                return {
                    'success': False,
                    'error': f'Token {token_symbol} not supported on chain {self.chain_id}'
                }
            
            print(f"🎯 [INFO] Calculating ETH needed for {token_amount:.6f} {token_symbol}")
            
            # Convert token amount to Wei (smallest unit)
            token_amount_wei = int(token_amount * (10 ** token_info.decimals))
            
            # Validate we have minimum ETH for meaningful quotes
            min_eth_for_quotes = 0.002  # Minimum 0.002 ETH (~$5) for meaningful quotes
            if hasattr(self, 'w3'):
                try:
                    # Try to get current ETH balance for validation context
                    # Note: This requires access to wallet manager which might not be available here
                    # We'll add this as a suggestion in the error message
                    pass
                except:
                    pass
            
            print(f"💡 [INFO] Minimum ETH recommended for {token_symbol} quotes: {min_eth_for_quotes:.3f} ETH")
            
            # Progressive quote amounts - start higher to get better liquidity
            # Try multiple amounts in case smaller amounts have poor liquidity
            quote_amounts_eth = [0.01, 0.005, 0.002]  # Start with 0.01 ETH (~$25), then smaller
            
            print(f"📊 [INFO] Will attempt quotes with amounts: {[f'{amt:.3f} ETH' for amt in quote_amounts_eth]}")
            
            # Try progressive quote amounts to find working liquidity
            quote_result = self._try_progressive_quotes("ETH", token_symbol, quote_amounts_eth)
            
            if not quote_result['success']:
                print(f"❌ [ERROR] All quote attempts failed for {token_symbol}")
                return {
                    'success': False,
                    'error': f'Unable to get valid quote for ETH → {token_symbol}: {quote_result.get("error", "Unknown error")}'
                }
            
            # Calculate approximate ETH needed based on the rate
            initial_token_wei = quote_result['to_amount_wei']
            initial_eth_wei = quote_result['from_amount_wei']
            
            if initial_token_wei == 0:
                print(f"❌ [ERROR] Even progressive quotes returned zero tokens for {token_symbol}")
                return {
                    'success': False,
                    'error': f'All quote attempts returned zero {token_symbol} tokens - possible liquidity or API issues'
                }
            
            # Calculate rate with proper decimal conversion
            # Convert Wei amounts to human-readable amounts for rate calculation
            initial_token_amount = initial_token_wei / (10 ** token_info.decimals)  # Convert to USDC units
            initial_eth_amount = initial_eth_wei / (10 ** 18)  # Convert to ETH units
            
            # Calculate rate in human-readable units with safety checks
            if initial_eth_amount <= 0:
                print(f"❌ [ERROR] Invalid ETH amount in quote: {initial_eth_amount}")
                return {
                    'success': False,
                    'error': f'Invalid ETH amount from quote: {initial_eth_amount}'
                }
            
            rate_tokens_per_eth = initial_token_amount / initial_eth_amount
            
            # Validate rate is reasonable (for USDC should be ~2000-4000 per ETH)
            if rate_tokens_per_eth <= 0:
                print(f"❌ [ERROR] Invalid rate calculated: {rate_tokens_per_eth}")
                return {
                    'success': False,
                    'error': f'Invalid rate calculated: {rate_tokens_per_eth} {token_symbol} per ETH'
                }
            
            # Calculate ETH needed in human-readable units, then convert to Wei
            eth_needed_human = token_amount / rate_tokens_per_eth
            estimated_eth_wei = int(self.w3.to_wei(eth_needed_human, 'ether'))
            
            print(f"📊 [INFO] Rate calculation: {rate_tokens_per_eth:.2f} {token_symbol} per ETH")
            print(f"📊 [DEBUG] Quote: {initial_eth_amount:.6f} ETH → {initial_token_amount:.6f} {token_symbol}")
            print(f"💰 [INFO] Estimated ETH needed: {float(self.w3.from_wei(estimated_eth_wei, 'ether')):.6f} ETH")
            
            # Add slippage buffer and ensure minimum viable amount
            slippage_buffer = 1 + (self.config.max_slippage_percent / 100)
            eth_needed_wei = int(estimated_eth_wei * slippage_buffer)
            
            # Ensure we're not going below minimum viable swap amount (0.002 ETH)
            min_swap_wei = self.w3.to_wei(0.002, 'ether')
            if eth_needed_wei < min_swap_wei:
                print(f"⚠️ [WARNING] Calculated ETH amount too small, using minimum: 0.002 ETH")
                eth_needed_wei = min_swap_wei
            
            # Calculate eth_needed_eth outside the success block to avoid scope issues
            eth_needed_eth = float(self.w3.from_wei(eth_needed_wei, 'ether'))
            
            # Optimization: Check if we can reuse the initial quote to avoid second API call
            initial_eth_amount = initial_eth_wei / (10 ** 18)
            difference_ratio = abs(eth_needed_eth - initial_eth_amount) / initial_eth_amount
            
            # If the needed amount is within 20% of our initial quote, reuse it to avoid 429 errors
            reuse_threshold = 0.20  # 20% difference threshold
            
            if difference_ratio <= reuse_threshold:
                print(f"🎯 [OPTIMIZATION] Reusing initial quote: needed {eth_needed_eth:.6f} ETH vs quoted {initial_eth_amount:.6f} ETH (diff: {difference_ratio:.1%})")
                print(f"🚀 [INFO] Avoiding second API call to prevent 429 rate limits")
                
                # Create final_quote from initial quote result, scaled proportionally
                scale_factor = eth_needed_wei / initial_eth_wei
                scaled_token_amount = int(initial_token_wei * scale_factor)
                
                final_quote = {
                    'success': True,
                    'from_token': "ETH",
                    'to_token': token_symbol,
                    'from_amount_wei': eth_needed_wei,
                    'to_amount_wei': scaled_token_amount,
                    'from_amount_eth': eth_needed_eth,
                    'gas_estimate': quote_result.get('gas_estimate', 175000),  # Use estimate from initial
                    'quote_data': {'reused_from_initial': True},
                    'validation': {'valid': True}
                }
                print(f"📊 [SCALED] Estimated {scaled_token_amount} Wei → {scaled_token_amount / (10 ** token_info.decimals):.6f} {token_symbol}")
            else:
                # Get more accurate quote with estimated amount (with 429 retry logic)
                print(f"🔍 [INFO] Getting final quote with {eth_needed_eth:.6f} ETH (diff: {difference_ratio:.1%} > {reuse_threshold:.1%})")
                final_quote = self._get_quote_with_429_retry("ETH", token_symbol, eth_needed_wei, max_retries=3)
            
            if final_quote['success']:
                tokens_received = final_quote['to_amount_wei'] / (10 ** token_info.decimals)
                
                # Validate the swap rate before proceeding
                rate_validation = self._validate_swap_rate("ETH", token_symbol, eth_needed_eth, tokens_received)
                
                print(f"💱 [INFO] ETH needed calculation: {eth_needed_eth:.6f} ETH → {tokens_received:.6f} {token_symbol}")
                print(f"🎯 [INFO] Target: {token_amount:.6f} {token_symbol}, Will receive: {tokens_received:.6f}")
                
                # Check if we'll receive sufficient tokens
                sufficient_tokens = tokens_received >= token_amount
                if not sufficient_tokens:
                    shortage = token_amount - tokens_received
                    print(f"⚠️ [WARNING] Token shortage: will receive {tokens_received:.6f} but need {token_amount:.6f} (short {shortage:.6f})")
                
                # Log validation result
                if rate_validation['validated']:
                    if rate_validation['valid']:
                        print(f"✅ [VALIDATION] Rate validation passed: {rate_validation['reason']}")
                    else:
                        print(f"⚠️ [VALIDATION] Rate validation warning: {rate_validation['reason']}")
                else:
                    print(f"⚠️ [VALIDATION] Rate validation skipped: {rate_validation['reason']}")
                
                return {
                    'success': True,
                    'token_symbol': token_symbol,
                    'target_token_amount': token_amount,
                    'eth_needed_wei': eth_needed_wei,
                    'eth_needed_eth': eth_needed_eth,
                    'expected_tokens_received': tokens_received,
                    'tokens_received_wei': final_quote['to_amount_wei'],
                    'gas_estimate': final_quote['gas_estimate'],
                    'sufficient_output': sufficient_tokens,
                    'rate_validation': rate_validation,
                    'initial_quote_eth': float(self.w3.from_wei(initial_eth_wei, 'ether')),
                    'rate_tokens_per_eth': rate_tokens_per_eth
                }
            else:
                print(f"❌ [ERROR] Final quote failed for {eth_needed_eth:.6f} ETH")
                return {
                    'success': False,
                    'error': f'Final quote failed: {final_quote.get("error", "Unknown error")}'
                }
                
        except Exception as e:
            error_msg = f"ETH calculation failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def _validate_transaction_structure(self, transaction: Dict[str, Any], tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate transaction structure to prevent rawTransaction errors.
        
        Args:
            transaction: Built transaction object
            tx_data: Original transaction data from 1INCH
            
        Returns:
            Dictionary with validation result
        """
        try:
            # Check required fields are present
            required_fields = ['from', 'to', 'value', 'gas', 'gasPrice', 'data', 'nonce', 'chainId']
            missing_fields = [field for field in required_fields if field not in transaction]
            
            if missing_fields:
                return {
                    'valid': False,
                    'error': f'Missing required transaction fields: {missing_fields}'
                }
            
            # Validate addresses are properly formatted
            try:
                Web3.to_checksum_address(transaction['from'])
                Web3.to_checksum_address(transaction['to'])
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Invalid address format: {str(e)}'
                }
            
            # Validate numeric fields are positive
            numeric_fields = ['value', 'gas', 'gasPrice', 'nonce', 'chainId']
            for field in numeric_fields:
                try:
                    value = int(transaction[field])
                    if value < 0:
                        return {
                            'valid': False,
                            'error': f'Negative value for {field}: {value}'
                        }
                except (ValueError, TypeError):
                    return {
                        'valid': False,
                        'error': f'Invalid numeric value for {field}: {transaction[field]}'
                    }
            
            # Validate gas limits are reasonable
            gas_limit = int(transaction['gas'])
            if gas_limit < 21000:  # Minimum gas for any transaction
                return {
                    'valid': False,
                    'error': f'Gas limit too low: {gas_limit} (minimum 21000)'
                }
            
            if gas_limit > 12000000:  # Very high gas limit (block limit)
                return {
                    'valid': False,
                    'error': f'Gas limit too high: {gas_limit} (maximum ~12M)'
                }
            
            # Validate chainId matches our expected network
            if int(transaction['chainId']) != self.chain_id:
                return {
                    'valid': False,
                    'error': f'ChainId mismatch: transaction={transaction["chainId"]}, expected={self.chain_id}'
                }
            
            # Validate data field is properly formatted hex
            data = transaction['data']
            if not isinstance(data, str) or not data.startswith('0x'):
                return {
                    'valid': False,
                    'error': f'Invalid data field format: {data}'
                }
            
            print(f"✅ [VALIDATION] Transaction structure validated successfully")
            print(f"📋 [INFO] From: {transaction['from']}")
            print(f"📋 [INFO] To: {transaction['to']}")
            print(f"📋 [INFO] Value: {transaction['value']} Wei")
            print(f"📋 [INFO] Gas: {transaction['gas']}")
            print(f"📋 [INFO] ChainId: {transaction['chainId']}")
            print(f"📋 [INFO] Nonce: {transaction['nonce']}")
            
            return {
                'valid': True,
                'validated_fields': required_fields
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Transaction validation exception: {str(e)}'
            }
    
    def _validate_swap_parameters(self, swap_params: Dict[str, str], eth_amount_wei: int, token_symbol: str) -> Dict[str, Any]:
        """
        Validate swap parameters to prevent API formatting errors.
        
        Args:
            swap_params: Swap parameters dictionary
            eth_amount_wei: ETH amount in Wei
            token_symbol: Target token symbol
            
        Returns:
            Dictionary with validation result
        """
        try:
            # Validate required parameters
            required_params = ['src', 'dst', 'amount', 'from', 'slippage']
            missing_params = [param for param in required_params if param not in swap_params]
            
            if missing_params:
                return {
                    'valid': False,
                    'error': f'Missing required swap parameters: {missing_params}'
                }
            
            # Validate addresses
            for addr_param in ['src', 'dst', 'from']:
                try:
                    address = swap_params[addr_param]
                    Web3.to_checksum_address(address)
                except Exception as e:
                    return {
                        'valid': False,
                        'error': f'Invalid address format for {addr_param}: {address} - {str(e)}'
                    }
            
            # Validate amount is proper integer string
            try:
                amount_value = int(swap_params['amount'])
                if amount_value != eth_amount_wei:
                    return {
                        'valid': False,
                        'error': f'Amount mismatch: param={amount_value}, expected={eth_amount_wei}'
                    }
                if amount_value <= 0:
                    return {
                        'valid': False,
                        'error': f'Invalid amount: {amount_value} (must be positive)'
                    }
            except (ValueError, TypeError):
                return {
                    'valid': False,
                    'error': f'Invalid amount format: {swap_params["amount"]}'
                }
            
            # Validate slippage percentage
            try:
                slippage = float(swap_params['slippage'])
                if slippage < 0 or slippage > 50:  # 0-50% reasonable range
                    return {
                        'valid': False,
                        'error': f'Invalid slippage: {slippage}% (must be 0-50%)'
                    }
            except (ValueError, TypeError):
                return {
                    'valid': False,
                    'error': f'Invalid slippage format: {swap_params["slippage"]}'
                }
            
            # Validate minTokenAmount if present
            if 'minTokenAmount' in swap_params:
                try:
                    min_amount = int(swap_params['minTokenAmount'])
                    if min_amount < 0:
                        return {
                            'valid': False,
                            'error': f'Invalid minTokenAmount: {min_amount} (must be non-negative)'
                        }
                except (ValueError, TypeError):
                    return {
                        'valid': False,
                        'error': f'Invalid minTokenAmount format: {swap_params["minTokenAmount"]}'
                    }
            
            print(f"✅ [VALIDATION] Swap parameters validated successfully")
            print(f"📋 [INFO] Amount: {swap_params['amount']} Wei ({float(swap_params['amount']) / (10**18):.6f} ETH)")
            print(f"📋 [INFO] From: {swap_params['from']}")
            print(f"📋 [INFO] Slippage: {swap_params['slippage']}%")
            print(f"📋 [INFO] Target: {token_symbol}")
            
            return {
                'valid': True,
                'validated_params': list(swap_params.keys())
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Parameter validation exception: {str(e)}'
            }
    
    def _analyze_transaction_error(self, error_msg: str, transaction: Dict[str, Any], raw_tx_hex: str = None) -> Dict[str, Any]:
        """
        Analyze transaction errors to provide specific diagnostics for -32600 codes.
        
        Args:
            error_msg: Error message from exception
            transaction: Transaction object that failed
            raw_tx_hex: Raw transaction hex (if available)
            
        Returns:
            Dictionary with error analysis and suggestions
        """
        analysis = {
            'error_type': 'unknown',
            'likely_cause': 'unknown',
            'suggestions': [],
            'technical_details': {}
        }
        
        try:
            error_lower = error_msg.lower()
            
            # Check for specific error patterns
            if '-32600' in error_msg or 'rawtx' in error_lower or 'rawTransaction' in error_msg:
                analysis['error_type'] = 'raw_transaction_error'
                analysis['likely_cause'] = 'Malformed raw transaction sent to blockchain node'
                analysis['suggestions'] = [
                    '🔧 Check transaction structure has all required fields (chainId, nonce, etc.)',
                    '🔧 Verify addresses are properly checksummed',
                    '🔧 Ensure gas values are within reasonable limits',
                    '🔧 Confirm network/chainId matches signing parameters',
                    '🔧 Validate raw transaction is properly hex encoded'
                ]
                
                # Add specific diagnostics based on transaction data
                if transaction:
                    analysis['technical_details']['transaction_fields'] = list(transaction.keys())
                    analysis['technical_details']['chain_id'] = transaction.get('chainId')
                    analysis['technical_details']['gas_limit'] = transaction.get('gas')
                    analysis['technical_details']['nonce'] = transaction.get('nonce')
                    
                    # Check for common issues
                    if 'chainId' not in transaction:
                        analysis['suggestions'].insert(0, '🚨 CRITICAL: Missing chainId field in transaction')
                    
                    if transaction.get('gas', 0) < 21000:
                        analysis['suggestions'].insert(0, f'🚨 CRITICAL: Gas limit too low: {transaction.get("gas")}')
                    
                    if transaction.get('nonce', -1) < 0:
                        analysis['suggestions'].insert(0, f'🚨 CRITICAL: Invalid nonce: {transaction.get("nonce")}')
                
                if raw_tx_hex:
                    analysis['technical_details']['raw_tx_length'] = len(raw_tx_hex)
                    analysis['technical_details']['raw_tx_format'] = 'hex' if raw_tx_hex.startswith('0x') else 'invalid'
                    
                    if not raw_tx_hex.startswith('0x'):
                        analysis['suggestions'].insert(0, '🚨 CRITICAL: Raw transaction not in hex format')
            
            elif 'insufficient funds' in error_lower or 'balance' in error_lower:
                analysis['error_type'] = 'insufficient_balance'
                analysis['likely_cause'] = 'Not enough ETH for transaction value + gas'
                analysis['suggestions'] = [
                    '💰 Add more ETH to wallet for transaction + gas fees',
                    '📊 Check current ETH balance vs required amount',
                    '⛽ Consider reducing gas price if transaction is not urgent'
                ]
                
            elif 'nonce' in error_lower:
                analysis['error_type'] = 'nonce_error'
                analysis['likely_cause'] = 'Transaction nonce conflicts with pending transactions'
                analysis['suggestions'] = [
                    '🔄 Wait for pending transactions to complete',
                    '📊 Check transaction nonce against current account nonce',
                    '⏰ Retry transaction after a few minutes'
                ]
                
            elif 'gas' in error_lower:
                analysis['error_type'] = 'gas_error'
                analysis['likely_cause'] = 'Gas-related transaction failure'
                analysis['suggestions'] = [
                    '⛽ Increase gas limit for complex transactions',
                    '💰 Ensure sufficient ETH for gas fees',
                    '📊 Check network gas prices and adjust accordingly'
                ]
                
            else:
                analysis['error_type'] = 'general_transaction_error'
                analysis['likely_cause'] = 'Unspecified transaction error'
                analysis['suggestions'] = [
                    '🔄 Retry transaction after a brief delay',
                    '📊 Check network status and congestion',
                    '🔧 Verify all transaction parameters are correct'
                ]
            
            print(f"🔍 [ERROR ANALYSIS] Type: {analysis['error_type']}")
            print(f"🔍 [ERROR ANALYSIS] Cause: {analysis['likely_cause']}")
            print(f"🔍 [ERROR ANALYSIS] Suggestions:")
            for suggestion in analysis['suggestions'][:3]:  # Show top 3 suggestions
                print(f"  {suggestion}")
                
        except Exception as e:
            print(f"❌ [ERROR] Error analysis failed: {e}")
            analysis['error_type'] = 'analysis_failed'
            
        return analysis
    
    def execute_eth_to_token_swap(self, token_symbol: str, eth_amount_wei: int, 
                                  min_token_amount_wei: int = 0) -> Dict[str, Any]:
        """
        Execute an ETH to ERC20 token swap.
        
        Args:
            token_symbol: Target token symbol
            eth_amount_wei: Amount of ETH to swap (in Wei)
            min_token_amount_wei: Minimum tokens to receive (slippage protection)
            
        Returns:
            Dictionary with swap transaction result
        """
        try:
            if not self.config.enable_swapping:
                return {
                    'success': False,
                    'error': 'Swapping is disabled in configuration'
                }
            
            eth_amount_eth = float(self.w3.from_wei(eth_amount_wei, 'ether'))
            
            # Safety checks
            if eth_amount_eth > self.config.max_eth_per_swap:
                return {
                    'success': False,
                    'error': f'Swap amount {eth_amount_eth:.6f} ETH exceeds maximum {self.config.max_eth_per_swap} ETH'
                }
            
            from_address = self._get_token_address("ETH")
            to_address = self._get_token_address(token_symbol)
            
            if not from_address or not to_address:
                return {
                    'success': False,
                    'error': f'Token address not found for {token_symbol}'
                }
            
            # Build swap parameters with proper formatting validation
            swap_params = {
                'src': from_address,
                'dst': to_address,
                'amount': str(int(eth_amount_wei)),  # Ensure integer string format
                'from': Web3.to_checksum_address(self.host_address),  # Ensure proper address format
                'slippage': f"{self.config.max_slippage_percent}",  # Ensure string format
                'disableEstimate': 'false',
                'allowPartialFill': 'false'
            }
            
            if min_token_amount_wei > 0:
                swap_params['minTokenAmount'] = str(int(min_token_amount_wei))
            
            # Validate swap parameters before API call
            param_validation = self._validate_swap_parameters(swap_params, eth_amount_wei, token_symbol)
            if not param_validation['valid']:
                return {
                    'success': False,
                    'error': f'Swap parameter validation failed: {param_validation["error"]}'
                }
            
            print(f"🔄 [INFO] Executing 1INCH swap: {eth_amount_eth:.6f} ETH → {token_symbol}")
            
            # Get swap transaction data
            response = requests.get(
                self.swap_endpoint,
                params=swap_params,
                headers=self._get_headers(),
                timeout=self.config.swap_timeout_seconds
            )
            
            if response.status_code != 200:
                error_msg = f"1INCH swap API failed: {response.status_code} - {response.text}"
                print(f"❌ [ERROR] {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
            
            swap_data = response.json()
            tx_data = swap_data.get('tx', {})
            
            if not tx_data:
                return {
                    'success': False,
                    'error': 'No transaction data received from 1INCH'
                }
            
            # Build transaction with all required fields for proper signing
            nonce = self.w3.eth.get_transaction_count(self.host_address, 'pending')
            
            transaction = {
                'from': Web3.to_checksum_address(self.host_address),
                'to': Web3.to_checksum_address(tx_data['to']),
                'value': int(tx_data['value']),
                'gas': int(tx_data['gas']),
                'gasPrice': int(tx_data['gasPrice']),
                'data': tx_data['data'],
                'nonce': nonce,
                'chainId': self.chain_id  # CRITICAL: Add chainId for proper signing
            }
            
            # Validate transaction structure before signing
            validation_result = self._validate_transaction_structure(transaction, tx_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': f'Transaction validation failed: {validation_result["error"]}'
                }
            
            print(f"📝 [INFO] Swap transaction: gas={transaction['gas']}, gasPrice={transaction['gasPrice']}")
            
            # Sign transaction with comprehensive validation
            try:
                signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
                
                # Validate signed transaction structure
                if not hasattr(signed_txn, 'rawTransaction'):
                    return {
                        'success': False,
                        'error': 'Signed transaction missing rawTransaction field'
                    }
                
                # Ensure rawTransaction is properly encoded as hex
                raw_tx = signed_txn.rawTransaction
                if isinstance(raw_tx, bytes):
                    raw_tx_hex = self.w3.to_hex(raw_tx)
                else:
                    raw_tx_hex = raw_tx
                
                # Validate hex format
                if not isinstance(raw_tx_hex, str) or not raw_tx_hex.startswith('0x'):
                    return {
                        'success': False,
                        'error': f'Invalid rawTransaction format: {type(raw_tx_hex)} - {raw_tx_hex[:50]}...'
                    }
                
                print(f"✅ [VALIDATION] Signed transaction validated successfully")
                print(f"📋 [INFO] Transaction hash: {signed_txn.hash.hex()}")
                print(f"📋 [INFO] Raw transaction length: {len(raw_tx_hex)} characters")
                
                # Send the properly formatted raw transaction
                tx_hash = self.w3.eth.send_raw_transaction(raw_tx_hex)
                
            except Exception as e:
                error_msg = f"Transaction signing/sending failed: {str(e)}"
                print(f"❌ [ERROR] {error_msg}")
                
                # Check for specific -32600 rawTransaction errors
                error_analysis = self._analyze_transaction_error(str(e), transaction, raw_tx_hex if 'raw_tx_hex' in locals() else None)
                
                return {
                    'success': False,
                    'error': error_msg,
                    'error_analysis': error_analysis
                }
            
            # Wait for confirmation
            print(f"⏳ [INFO] Waiting for swap confirmation: {tx_hash.hex()}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                gas_used = receipt['gasUsed']
                effective_gas_price = receipt.get('effectiveGasPrice', transaction['gasPrice'])
                
                print(f"✅ [SUCCESS] Swap completed! TX: {tx_hash.hex()}")
                print(f"⛽ [INFO] Gas used: {gas_used}, Effective price: {effective_gas_price}")
                
                return {
                    'success': True,
                    'transaction_hash': tx_hash.hex(),
                    'from_token': 'ETH',
                    'to_token': token_symbol,
                    'eth_amount_wei': eth_amount_wei,
                    'eth_amount_eth': eth_amount_eth,
                    'gas_used': gas_used,
                    'gas_price': effective_gas_price,
                    'block_number': receipt['blockNumber'],
                    'swap_data': swap_data
                }
            else:
                return {
                    'success': False,
                    'error': 'Swap transaction failed',
                    'transaction_hash': tx_hash.hex(),
                    'receipt': receipt
                }
                
        except Exception as e:
            error_msg = f"Swap execution failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def swap_eth_for_exact_tokens(self, token_symbol: str, target_token_amount: float) -> Dict[str, Any]:
        """
        Swap ETH to get a specific amount of tokens.
        
        Args:
            token_symbol: Target token symbol
            target_token_amount: Exact amount of tokens needed
            
        Returns:
            Dictionary with swap result
        """
        try:
            print(f"🎯 [INFO] Starting swap for exactly {target_token_amount:.6f} {token_symbol}")
            
            # Calculate ETH needed
            calc_result = self.calculate_eth_needed_for_tokens(token_symbol, target_token_amount)
            
            if not calc_result['success']:
                return calc_result
            
            eth_needed = calc_result['eth_needed_wei']
            expected_tokens = calc_result['expected_tokens_received']
            
            # Safety check: ensure we're not using too much ETH
            eth_needed_eth = float(self.w3.from_wei(eth_needed, 'ether'))
            
            if eth_needed_eth > self.config.max_eth_per_swap:
                return {
                    'success': False,
                    'error': f'Required ETH {eth_needed_eth:.6f} exceeds maximum {self.config.max_eth_per_swap} ETH per swap'
                }
            
            # Calculate minimum tokens with slippage protection
            token_info = self.token_registry.get_token_info(self.chain_id, token_symbol)
            min_tokens = target_token_amount * 0.95  # Accept 5% less due to slippage
            min_token_wei = int(min_tokens * (10 ** token_info.decimals))
            
            # Execute the swap
            swap_result = self.execute_eth_to_token_swap(
                token_symbol=token_symbol,
                eth_amount_wei=eth_needed,
                min_token_amount_wei=min_token_wei
            )
            
            if swap_result['success']:
                print(f"🎉 [SUCCESS] Swapped {eth_needed_eth:.6f} ETH for {token_symbol}")
                
            return swap_result
            
        except Exception as e:
            error_msg = f"Exact token swap failed: {str(e)}"
            print(f"❌ [ERROR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }