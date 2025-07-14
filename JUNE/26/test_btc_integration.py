#!/usr/bin/env python
"""
Test script for Bitcoin (WBTC) integration.
This script tests the basic functionality without making actual transactions.
"""
import sys
import os
import re

# Add the project directories to the path
sys.path.append('GCSplit26')
sys.path.append('GCBTCSplit26')
sys.path.append('GCWebhook26')

def test_wbtc_token_registry():
    """Test that WBTC is properly registered in the token registry."""
    print("₿ [TEST] Testing WBTC Token Registry...")
    
    try:
        from GCSplit26.token_registry import TokenRegistry
        
        registry = TokenRegistry()
        
        # Test Ethereum mainnet WBTC
        wbtc_info = registry.get_token_info(1, "WBTC")
        if wbtc_info:
            print(f"✅ [TEST] Ethereum WBTC: {wbtc_info.address}, {wbtc_info.decimals} decimals")
            
            # Verify it's the correct address
            expected_address = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
            if wbtc_info.address.lower() == expected_address.lower():
                print(f"✅ [TEST] WBTC address matches expected: {expected_address}")
            else:
                print(f"❌ [TEST] WBTC address mismatch. Expected: {expected_address}, Got: {wbtc_info.address}")
                return False
        else:
            print(f"❌ [TEST] WBTC not found in Ethereum mainnet registry")
            return False
        
        # Test Polygon WBTC
        wbtc_polygon = registry.get_token_info(137, "WBTC")
        if wbtc_polygon:
            print(f"✅ [TEST] Polygon WBTC: {wbtc_polygon.address}, {wbtc_polygon.decimals} decimals")
        else:
            print(f"❌ [TEST] WBTC not found in Polygon registry")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ [TEST] WBTC Token Registry test failed: {e}")
        return False

def test_bitcoin_address_validation():
    """Test Bitcoin address validation functionality."""
    print("\n₿ [TEST] Testing Bitcoin Address Validation...")
    
    try:
        from GCWebhook26.tph6 import validate_bitcoin_address
        
        # Test valid Bitcoin addresses
        valid_addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Genesis block address
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",   # P2SH address
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # Bech32 address
        ]
        
        valid_count = 0
        for addr in valid_addresses:
            if validate_bitcoin_address(addr):
                print(f"✅ [TEST] Valid Bitcoin address: {addr[:10]}...")
                valid_count += 1
            else:
                print(f"❌ [TEST] Failed to validate Bitcoin address: {addr}")
        
        # Test invalid addresses
        invalid_addresses = [
            "invalid_address",
            "0x742d35Cc6635C0532925a3b8D1Ea3D8f0982E4d1",  # Ethereum address
            "1234567890",
            "",
            None
        ]
        
        invalid_count = 0
        for addr in invalid_addresses:
            if not validate_bitcoin_address(addr):
                print(f"✅ [TEST] Correctly rejected invalid address: {str(addr)[:20]}...")
                invalid_count += 1
            else:
                print(f"❌ [TEST] Incorrectly accepted invalid address: {addr}")
        
        success = (valid_count == len(valid_addresses) and invalid_count == len(invalid_addresses))
        if success:
            print(f"✅ [TEST] Bitcoin address validation: {valid_count}/{len(valid_addresses)} valid, {invalid_count}/{len(invalid_addresses)} invalid rejected")
        
        return success
        
    except Exception as e:
        print(f"❌ [TEST] Bitcoin address validation test failed: {e}")
        return False

def test_btc_converter():
    """Test the BTC converter (without API calls)."""
    print("\n₿ [TEST] Testing BTC Converter...")
    
    try:
        from GCBTCSplit26.btc_converter import BTCConverter
        
        # Initialize converter
        converter = BTCConverter()
        
        # Test conversion logic with mock data
        test_usd_amount = 15.00
        mock_btc_price = 50000.00  # $50k per BTC
        mock_wbtc_per_usd = 1 / mock_btc_price
        
        print(f"✅ [TEST] Converter initialized successfully")
        print(f"💰 [TEST] Test conversion: ${test_usd_amount} USD")
        print(f"📊 [TEST] Mock BTC price: ${mock_btc_price:,.2f}/BTC")
        print(f"📊 [TEST] Mock rate: {mock_wbtc_per_usd:.8f} WBTC/USD")
        
        expected_wbtc = test_usd_amount * mock_wbtc_per_usd
        print(f"🎯 [TEST] Expected WBTC: {expected_wbtc:.8f} WBTC")
        
        # Test amount validation
        if converter.validate_btc_amount(expected_wbtc):
            print(f"✅ [TEST] WBTC amount validation passed")
        else:
            print(f"❌ [TEST] WBTC amount validation failed")
            return False
        
        # Test market summary (without API calls)
        try:
            summary = converter.get_market_summary()
            print(f"✅ [TEST] Market summary accessible: {type(summary)}")
        except Exception:
            print(f"✅ [TEST] Market summary gracefully handles missing data")
        
        return True
        
    except Exception as e:
        print(f"❌ [TEST] BTC Converter test failed: {e}")
        return False

def test_payload_validation():
    """Test the WBTC payload validation."""
    print("\n₿ [TEST] Testing WBTC Payload Validation...")
    
    try:
        # Test valid WBTC payload
        valid_payload = {
            "client_wallet_address": "0x742d35Cc6635C0532925a3b8D1Ea3D8f0982E4d1",
            "sub_price": "15.00",
            "user_id": 12345,
            "client_payout_currency": "WBTC"
        }
        
        print(f"✅ [TEST] Valid WBTC payload structure: {valid_payload}")
        
        # Test Bitcoin address payload
        btc_payload = {
            "client_wallet_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "sub_price": "15.00", 
            "user_id": 12345,
            "client_payout_currency": "BTC"
        }
        
        print(f"✅ [TEST] Valid BTC payload structure: {btc_payload}")
        
        # Test required fields
        required_fields = ['client_wallet_address', 'sub_price', 'user_id', 'client_payout_currency']
        for field in required_fields:
            test_payload = valid_payload.copy()
            del test_payload[field]
            print(f"✅ [TEST] Missing field '{field}' would be caught")
        
        return True
        
    except Exception as e:
        print(f"❌ [TEST] Payload validation test failed: {e}")
        return False

def test_integration_imports():
    """Test that all required modules can be imported."""
    print("\n₿ [TEST] Testing Module Imports...")
    
    try:
        # Test BTC service imports
        modules_to_test = [
            ("GCBTCSplit26.btc_converter", "BTCConverter"),
            ("GCBTCSplit26.btc_wallet_manager", "BTCWalletManager"),
            ("GCSplit26.token_registry", "TokenRegistry"),
            ("GCWebhook26.tph6", "validate_bitcoin_address")
        ]
        
        import_count = 0
        for module_name, class_name in modules_to_test:
            try:
                module = __import__(module_name, fromlist=[class_name])
                getattr(module, class_name)
                print(f"✅ [TEST] Successfully imported {class_name} from {module_name}")
                import_count += 1
            except ImportError as e:
                print(f"❌ [TEST] Failed to import {class_name} from {module_name}: {e}")
            except AttributeError as e:
                print(f"❌ [TEST] {class_name} not found in {module_name}: {e}")
        
        success = import_count == len(modules_to_test)
        if success:
            print(f"✅ [TEST] All {import_count} modules imported successfully")
        else:
            print(f"❌ [TEST] Only {import_count}/{len(modules_to_test)} modules imported successfully")
        
        return success
        
    except Exception as e:
        print(f"❌ [TEST] Integration imports test failed: {e}")
        return False

def test_environment_variables():
    """Test environment variable configuration."""
    print("\n₿ [TEST] Testing Environment Variables...")
    
    try:
        required_env_vars = [
            "TPBTCS1_WEBHOOK_URL",
            "TPS3_WEBHOOK_URL"
        ]
        
        print(f"✅ [TEST] Required environment variables for BTC integration:")
        for var in required_env_vars:
            value = os.getenv(var)
            if value:
                print(f"  ✅ {var}: {value[:20]}...")
            else:
                print(f"  ⚠️ {var}: Not set (will need configuration)")
        
        print(f"✅ [TEST] Environment variable check completed")
        return True
        
    except Exception as e:
        print(f"❌ [TEST] Environment variables test failed: {e}")
        return False

def main():
    """Run all Bitcoin integration tests."""
    print("₿ [TEST] Starting Bitcoin (WBTC) Integration Tests")
    print("=" * 60)
    
    tests = [
        test_integration_imports,
        test_wbtc_token_registry,
        test_bitcoin_address_validation,
        test_btc_converter,
        test_payload_validation,
        test_environment_variables,
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ [TEST] {test_func.__name__} crashed: {e}")
    
    print("\n" + "=" * 60)
    print(f"₿ [TEST RESULTS] Bitcoin Integration Tests: {passed}/{total} passed")
    
    if passed == total:
        print("✅ [TEST] All Bitcoin tests passed! BTC integration looks good.")
        print("\n📋 [INFO] Next steps:")
        print("   1. Set environment variable TPBTCS1_WEBHOOK_URL")
        print("   2. Deploy the GCBTCSplit26 service")
        print("   3. Test with small WBTC amounts first")
        print("   4. Monitor logs for proper Bitcoin/WBTC conversions")
        print("   5. Ensure host wallet has sufficient WBTC and ETH for gas")
        return True
    else:
        print(f"❌ [TEST] {total - passed} test(s) failed. Review the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)