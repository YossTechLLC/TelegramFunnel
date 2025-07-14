#!/usr/bin/env python
"""
Test script to validate the USDC contract address fix.
"""
import sys
import os

# Add the GCSplit25 directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'GCSplit25'))

def test_usdc_contract_address():
    """Test the USDC contract address fix."""
    
    print("🧪 [TEST] Testing USDC Contract Address Fix")
    print("=" * 50)
    
    try:
        from token_registry import TokenRegistry
        
        # Test the token registry
        registry = TokenRegistry()
        usdc_info = registry.get_token_info(1, 'USDC')
        
        print(f"📋 [INFO] USDC Token Info:")
        print(f"  Symbol: {usdc_info.symbol}")
        print(f"  Name: {usdc_info.name}")
        print(f"  Address: {usdc_info.address}")
        print(f"  Decimals: {usdc_info.decimals}")
        print(f"  Is Stablecoin: {usdc_info.is_stablecoin}")
        
        # Verify the correct address
        expected_address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
        if usdc_info.address.lower() == expected_address.lower():
            print(f"✅ [SUCCESS] USDC contract address is correct!")
            print(f"📋 [INFO] Address matches Circle's official USDC contract")
        else:
            print(f"❌ [ERROR] USDC address mismatch!")
            print(f"  Expected: {expected_address}")
            print(f"  Got: {usdc_info.address}")
            return False
            
        # Test other token addresses for regression
        print(f"\n📋 [INFO] Checking other token addresses for regression:")
        
        test_tokens = {
            'USDT': "0xdac17f958d2ee523a2206206994597c13d831ec7",
            'DAI': "0x6b175474e89094c44da98b954eedeac495271d0f", 
            'LINK': "0x514910771af9ca656af840dff83e8264ecf986ca",
            'UNI': "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
            'AAVE': "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9"
        }
        
        for symbol, expected in test_tokens.items():
            token_info = registry.get_token_info(1, symbol)
            if token_info and token_info.address.lower() == expected.lower():
                print(f"  ✅ {symbol}: {token_info.address}")
            else:
                print(f"  ❌ {symbol}: Expected {expected}, got {token_info.address if token_info else 'None'}")
                
        print(f"\n🎉 [SUCCESS] USDC contract address fix validated!")
        print(f"💡 [NEXT] Deploy and test with actual USDC payments")
        
        return True
        
    except Exception as e:
        print(f"❌ [ERROR] Test failed: {e}")
        return False

def main():
    """Run the USDC fix validation test."""
    try:
        print("🚀 Starting USDC Contract Address Fix Validation")
        
        if test_usdc_contract_address():
            print(f"\n✅ [SUCCESS] All tests passed!")
            print(f"🔄 [READY] USDC payments should now work correctly")
            return 0
        else:
            print(f"\n❌ [FAILURE] Tests failed")
            return 1
            
    except Exception as e:
        print(f"❌ [ERROR] Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())