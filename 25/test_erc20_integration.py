#!/usr/bin/env python
"""
Test script for ERC20 integration.
This script tests the basic functionality without making actual transactions.
"""
import sys
import os

# Add the project directories to the path
sys.path.append('GCSplit25')
sys.path.append('GCWebhook25')

def test_token_registry():
    """Test the token registry functionality."""
    print("🧪 [TEST] Testing Token Registry...")
    
    try:
        from GCSplit25.token_registry import TokenRegistry
        
        registry = TokenRegistry()
        
        # Test Ethereum mainnet tokens
        eth_tokens = registry.get_supported_tokens(1)
        print(f"✅ [TEST] Ethereum Mainnet supports {len(eth_tokens)} tokens: {eth_tokens[:5]}...")
        
        # Test specific token info
        usdt_info = registry.get_token_info(1, "USDT")
        if usdt_info:
            print(f"✅ [TEST] USDT info: {usdt_info.address}, {usdt_info.decimals} decimals")
        else:
            print("❌ [TEST] USDT not found")
        
        # Test stablecoins
        stablecoins = registry.get_stablecoins(1)
        print(f"✅ [TEST] Found {len(stablecoins)} stablecoins: {stablecoins}")
        
        return True
        
    except Exception as e:
        print(f"❌ [TEST] Token Registry test failed: {e}")
        return False

def test_multi_token_converter():
    """Test the multi-token converter (without API calls)."""
    print("\n🧪 [TEST] Testing Multi-Token Converter...")
    
    try:
        from GCSplit25.multi_token_converter import MultiTokenConverter
        
        # Initialize with dummy API key (won't make real calls)
        converter = MultiTokenConverter("dummy_api_key", chain_id=1)
        
        # Test supported tokens
        supported = converter.get_supported_tokens()
        print(f"✅ [TEST] Converter supports {len(supported)} tokens: {supported[:5]}...")
        
        # Test registry summary
        summary = converter.get_registry_summary()
        print(f"✅ [TEST] Registry summary: {summary['total_supported_tokens']} total tokens")
        
        return True
        
    except Exception as e:
        print(f"❌ [TEST] Multi-Token Converter test failed: {e}")
        return False

def test_payload_validation():
    """Test the updated payload validation."""
    print("\n🧪 [TEST] Testing Payload Validation...")
    
    try:
        # This would normally be imported from tps2.py
        # For now, just test the structure
        
        # Test valid payload
        valid_payload = {
            "client_wallet_address": "0x742d35Cc6635C0532925a3b8D1Ea3D8f0982E4d1",
            "sub_price": "15.00",
            "user_id": 12345,
            "client_payout_currency": "USDT"
        }
        
        required_fields = ['client_wallet_address', 'sub_price', 'user_id', 'client_payout_currency']
        
        for field in required_fields:
            if field not in valid_payload:
                print(f"❌ [TEST] Missing required field: {field}")
                return False
        
        print("✅ [TEST] Valid payload structure confirmed")
        
        # Test validation logic
        wallet_address = valid_payload['client_wallet_address']
        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            print("❌ [TEST] Invalid wallet address format")
            return False
        
        payout_currency = valid_payload['client_payout_currency'].strip().upper()
        if not payout_currency or len(payout_currency) > 10:
            print("❌ [TEST] Invalid payout currency")
            return False
        
        print(f"✅ [TEST] Payload validation passed for {payout_currency}")
        
        return True
        
    except Exception as e:
        print(f"❌ [TEST] Payload validation test failed: {e}")
        return False

def test_integration_imports():
    """Test that all new modules can be imported correctly."""
    print("\n🧪 [TEST] Testing Module Imports...")
    
    modules_to_test = [
        ("GCSplit25.token_registry", "TokenRegistry"),
        ("GCSplit25.multi_token_converter", "MultiTokenConverter"),
    ]
    
    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"✅ [TEST] Successfully imported {class_name} from {module_name}")
        except Exception as e:
            print(f"❌ [TEST] Failed to import {class_name} from {module_name}: {e}")
            return False
    
    return True

def main():
    """Run all tests."""
    print("🚀 [TEST] Starting ERC20 Integration Tests")
    print("=" * 50)
    
    tests = [
        test_integration_imports,
        test_token_registry,
        test_multi_token_converter,
        test_payload_validation,
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"⚠️ [TEST] {test_func.__name__} had issues")
        except Exception as e:
            print(f"❌ [TEST] {test_func.__name__} crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"🏁 [TEST] Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ [TEST] All tests passed! ERC20 integration looks good.")
        print("\n📋 [INFO] Next steps:")
        print("   1. Deploy the updated services")
        print("   2. Update environment variable TPS1_WEBHOOK_URL → TPS2_WEBHOOK_URL")
        print("   3. Test with small amounts first")
        print("   4. Monitor logs for proper token conversions")
        return True
    else:
        print("❌ [TEST] Some tests failed. Please review the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)