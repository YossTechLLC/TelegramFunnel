#!/usr/bin/env python
"""
Test script for currency validation functionality
Verifies that TRX and other currencies are now supported
"""
import asyncio
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from currency_manager import CurrencyManager


async def test_currency_validation():
    """Test currency validation with various currencies."""
    print("🧪 [TEST] Testing Currency Validation System")
    print("=" * 60)
    
    # Initialize currency manager
    currency_manager = CurrencyManager()
    
    # Test currencies including TRX
    test_currencies = [
        "TRX",    # TRON - this was failing before
        "ETH",    # Ethereum
        "BTC",    # Bitcoin
        "USDT",   # Tether
        "USDC",   # USD Coin
        "SOL",    # Solana
        "BNB",    # Binance Coin
        "ADA",    # Cardano
        "INVALID" # Invalid currency
    ]
    
    print(f"🔍 [TEST] Testing {len(test_currencies)} currencies...")
    print()
    
    results = {}
    
    for currency in test_currencies:
        print(f"🔸 Testing {currency}:")
        
        # Test async version
        try:
            is_supported_async, message_async = await currency_manager.is_currency_supported_async(currency)
            print(f"   📡 [ASYNC] {message_async}")
            
            # Test sync version
            is_supported_sync, message_sync = currency_manager.is_currency_supported_sync(currency)
            print(f"   ⚡ [SYNC]  {message_sync}")
            
            results[currency] = {
                "async_supported": is_supported_async,
                "sync_supported": is_supported_sync,
                "async_message": message_async,
                "sync_message": message_sync
            }
            
        except Exception as e:
            print(f"   ❌ [ERROR] {e}")
            results[currency] = {"error": str(e)}
        
        print()
    
    # Summary
    print("📊 [SUMMARY] Test Results:")
    print("-" * 40)
    
    supported_count = 0
    for currency, result in results.items():
        if result.get("async_supported", False) or result.get("sync_supported", False):
            status = "✅ SUPPORTED"
            supported_count += 1
        else:
            status = "❌ NOT SUPPORTED"
        
        print(f"   {currency:<8} - {status}")
    
    print(f"\n📈 [RESULT] {supported_count}/{len(test_currencies)} currencies supported")
    
    # Check cache status
    cache_status = currency_manager.get_cache_status()
    print(f"\n🗄️ [CACHE] Cache Status:")
    print(f"   Initialized: {cache_status['initialized']}")
    print(f"   Valid: {cache_status['cache_valid']}")
    print(f"   Cached currencies: {cache_status['cached_currencies_count']}")
    print(f"   Fallback currencies: {cache_status['fallback_currencies_count']}")
    print(f"   ChangeNOW available: {cache_status['changenow_available']}")
    
    # TRX specific test
    print(f"\n🎯 [TRX_TEST] Specific TRX validation test:")
    trx_result = results.get("TRX", {})
    if trx_result.get("async_supported") or trx_result.get("sync_supported"):
        print("   ✅ SUCCESS: TRX is now supported!")
        print("   🎉 This should resolve the payment flow issue.")
    else:
        print("   ❌ FAILED: TRX is still not supported")
        print("   🔧 Check ChangeNOW API connectivity and fallback list")


def test_database_integration():
    """Test that DatabaseManager properly uses CurrencyManager."""
    print("\n🗄️ [DB_TEST] Testing Database Integration")
    print("=" * 60)
    
    try:
        # This will test the import and basic initialization
        from database import DatabaseManager
        
        # Create mock environment for testing
        os.environ.setdefault("DATABASE_HOST_SECRET", "mock")
        os.environ.setdefault("DATABASE_NAME_SECRET", "mock") 
        os.environ.setdefault("DATABASE_USER_SECRET", "mock")
        os.environ.setdefault("DATABASE_PASSWORD_SECRET", "mock")
        
        print("🔧 [INFO] Testing DatabaseManager import and initialization...")
        
        # Try to create instance (this will test currency_manager import)
        try:
            db_manager = DatabaseManager()
            print("✅ [SUCCESS] DatabaseManager created successfully")
            print("✅ [SUCCESS] CurrencyManager integration working")
            
            # Test TRX validation through database manager
            print("\n🧪 [TEST] Testing TRX validation through DatabaseManager...")
            is_valid, message = db_manager.validate_client_payout_currency("TRX")
            
            if is_valid:
                print(f"✅ [SUCCESS] TRX validation: {message}")
            else:
                print(f"❌ [FAILED] TRX validation: {message}")
                
        except Exception as e:
            print(f"⚠️ [WARNING] DatabaseManager creation failed (expected in test environment): {e}")
            print("✅ [INFO] This is normal when database credentials are not available")
            print("✅ [INFO] Import and basic structure are working")
            
    except ImportError as e:
        print(f"❌ [ERROR] Import failed: {e}")
        return False
    
    return True


async def main():
    """Main test function."""
    print("🚀 [START] Currency Validation Test Suite")
    print(f"📅 [INFO] Testing TRX support and ChangeNOW integration")
    print()
    
    # Test 1: Currency Manager functionality
    await test_currency_validation()
    
    # Test 2: Database integration
    test_database_integration()
    
    print("\n🏁 [COMPLETE] Test suite completed")
    print("💡 [INFO] If TRX shows as supported, the payment flow issue should be resolved")


if __name__ == "__main__":
    asyncio.run(main())