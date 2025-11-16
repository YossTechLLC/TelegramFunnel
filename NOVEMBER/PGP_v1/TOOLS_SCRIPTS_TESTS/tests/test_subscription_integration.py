#!/usr/bin/env python3
"""
Integration test for subscription expiration workflow.
Tests full end-to-end flow with real database.

This test verifies:
1. DatabaseManager.fetch_expired_subscriptions() works correctly
2. DatabaseManager.deactivate_subscription() works correctly
3. The subscription expiration workflow functions end-to-end
"""
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', '..', 'OCTOBER', '10-26', 'PGP_SERVER_v1'))

def test_subscription_expiration_workflow():
    """Test complete subscription expiration workflow with database."""
    print("🧪 Starting Subscription Expiration Integration Test\n")
    print("=" * 70)

    try:
        # Import DatabaseManager
        from database import DatabaseManager
        from sqlalchemy import text

        # Initialize database manager
        print("\n📝 Step 1: Initializing DatabaseManager...")
        db_manager = DatabaseManager()
        print("✅ DatabaseManager initialized\n")

        # Test user ID and channel ID
        test_user_id = 999999999
        test_channel_id = -1001234567890

        # Step 2: Clean up any existing test data
        print("📝 Step 2: Cleaning up any existing test data...")
        with db_manager.pool.engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM private_channel_users_database
                WHERE user_id = :user_id AND private_channel_id = :channel_id
            """), {"user_id": test_user_id, "channel_id": test_channel_id})
            conn.commit()
        print("✅ Test data cleaned up\n")

        # Step 3: Insert test expired subscription
        print("📝 Step 3: Inserting test expired subscription...")
        expire_time = (datetime.now() - timedelta(hours=1)).strftime('%H:%M:%S')
        expire_date = datetime.now().strftime('%Y-%m-%d')

        with db_manager.pool.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO private_channel_users_database
                (user_id, private_channel_id, is_active, expire_time, expire_date)
                VALUES (:user_id, :channel_id, true, :time, :date)
            """), {
                "user_id": test_user_id,
                "channel_id": test_channel_id,
                "time": expire_time,
                "date": expire_date
            })
            conn.commit()

        print(f"✅ Test subscription inserted:")
        print(f"   - User ID: {test_user_id}")
        print(f"   - Channel ID: {test_channel_id}")
        print(f"   - Expire Time: {expire_time}")
        print(f"   - Expire Date: {expire_date}")
        print(f"   - is_active: true\n")

        # Step 4: Test fetch_expired_subscriptions()
        print("📝 Step 4: Testing DatabaseManager.fetch_expired_subscriptions()...")
        expired = db_manager.fetch_expired_subscriptions()

        # Find our test subscription
        test_subscription = None
        for sub in expired:
            if sub[0] == test_user_id and sub[1] == test_channel_id:
                test_subscription = sub
                break

        if test_subscription:
            print(f"✅ Found test subscription in expired list:")
            print(f"   - User ID: {test_subscription[0]}")
            print(f"   - Channel ID: {test_subscription[1]}")
            print(f"   - Expire Time: {test_subscription[2]}")
            print(f"   - Expire Date: {test_subscription[3]}\n")
        else:
            print("❌ ERROR: Test subscription NOT found in expired list!")
            print(f"   Total expired found: {len(expired)}")
            raise AssertionError("Test subscription not found in expired list")

        # Step 5: Test deactivate_subscription()
        print("📝 Step 5: Testing DatabaseManager.deactivate_subscription()...")
        result = db_manager.deactivate_subscription(test_user_id, test_channel_id)

        if result:
            print("✅ Deactivation successful\n")
        else:
            print("❌ ERROR: Deactivation failed!")
            raise AssertionError("Deactivation returned False")

        # Step 6: Verify subscription is now inactive
        print("📝 Step 6: Verifying subscription marked as inactive...")
        with db_manager.pool.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT is_active
                FROM private_channel_users_database
                WHERE user_id = :user_id AND private_channel_id = :channel_id
            """), {"user_id": test_user_id, "channel_id": test_channel_id})
            row = result.fetchone()

            if row:
                is_active = row[0]
                print(f"   - is_active: {is_active}")

                if is_active is False:
                    print("✅ Subscription successfully marked as inactive\n")
                else:
                    print("❌ ERROR: Subscription still active!")
                    raise AssertionError("Subscription not marked as inactive")
            else:
                print("❌ ERROR: Subscription not found in database!")
                raise AssertionError("Subscription not found after deactivation")

        # Step 7: Verify deactivated subscriptions are NOT in fetch_expired_subscriptions()
        print("📝 Step 7: Verifying deactivated subscriptions are NOT fetched...")
        expired_after = db_manager.fetch_expired_subscriptions()

        test_found_after = False
        for sub in expired_after:
            if sub[0] == test_user_id and sub[1] == test_channel_id:
                test_found_after = True
                break

        if not test_found_after:
            print("✅ Deactivated subscription correctly excluded from fetch\n")
        else:
            print("❌ ERROR: Deactivated subscription still appearing in fetch!")
            raise AssertionError("Deactivated subscription still in expired list")

        # Step 8: Cleanup
        print("📝 Step 8: Cleaning up test data...")
        with db_manager.pool.engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM private_channel_users_database
                WHERE user_id = :user_id AND private_channel_id = :channel_id
            """), {"user_id": test_user_id, "channel_id": test_channel_id})
            conn.commit()
        print("✅ Test data cleaned up\n")

        # Success!
        print("=" * 70)
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("=" * 70)
        print("\n✅ Test Results:")
        print("   1. DatabaseManager.fetch_expired_subscriptions() ✅")
        print("   2. DatabaseManager.deactivate_subscription() ✅")
        print("   3. End-to-end expiration workflow ✅")
        print("   4. Database state verification ✅")
        print("\n🚀 Subscription management is working correctly!")

        return True

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ INTEGRATION TEST FAILED!")
        print("=" * 70)
        print(f"\nError: {e}")
        print("\nTest aborted. Please review the error above.")
        return False


if __name__ == "__main__":
    success = test_subscription_expiration_workflow()
    sys.exit(0 if success else 1)
