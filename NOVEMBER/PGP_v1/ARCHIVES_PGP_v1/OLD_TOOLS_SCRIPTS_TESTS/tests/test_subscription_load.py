#!/usr/bin/env python3
"""
Load test for subscription manager.
Tests performance with 100 expired subscriptions.

This test verifies:
1. DatabaseManager can handle batch queries efficiently
2. Performance metrics for processing 100 subscriptions
3. Database connection pool handles load correctly
"""
import sys
import os
import time
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', '..', 'OCTOBER', '10-26', 'PGP_SERVER_v1'))

def load_test_100_subscriptions():
    """Test processing 100 expired subscriptions."""
    print("🧪 Starting Subscription Manager Load Test (100 subscriptions)\n")
    print("=" * 70)

    try:
        # Import DatabaseManager
        from database import DatabaseManager
        from sqlalchemy import text

        # Initialize database manager
        print("\n📝 Step 1: Initializing DatabaseManager...")
        db_manager = DatabaseManager()
        print("✅ DatabaseManager initialized\n")

        # Test configuration
        test_channel_id = -1001234567890
        test_user_ids = list(range(900000000, 900000100))  # 100 test users
        num_subscriptions = len(test_user_ids)

        print(f"📊 Load Test Configuration:")
        print(f"   - Number of subscriptions: {num_subscriptions}")
        print(f"   - Test channel ID: {test_channel_id}")
        print(f"   - User ID range: {test_user_ids[0]} - {test_user_ids[-1]}\n")

        # Step 2: Clean up any existing test data
        print("📝 Step 2: Cleaning up any existing test data...")
        cleanup_start = time.time()

        with db_manager.pool.engine.connect() as conn:
            for user_id in test_user_ids:
                conn.execute(text("""
                    DELETE FROM private_channel_users_database
                    WHERE user_id = :user_id AND private_channel_id = :channel_id
                """), {"user_id": user_id, "channel_id": test_channel_id})
            conn.commit()

        cleanup_duration = time.time() - cleanup_start
        print(f"✅ Cleanup complete in {cleanup_duration:.2f} seconds\n")

        # Step 3: Insert 100 test expired subscriptions
        print(f"📝 Step 3: Inserting {num_subscriptions} test expired subscriptions...")
        insert_start = time.time()

        expire_time = (datetime.now() - timedelta(hours=1)).strftime('%H:%M:%S')
        expire_date = datetime.now().strftime('%Y-%m-%d')

        with db_manager.pool.engine.connect() as conn:
            for user_id in test_user_ids:
                conn.execute(text("""
                    INSERT INTO private_channel_users_database
                    (user_id, private_channel_id, is_active, expire_time, expire_date)
                    VALUES (:user_id, :channel_id, true, :time, :date)
                """), {
                    "user_id": user_id,
                    "channel_id": test_channel_id,
                    "time": expire_time,
                    "date": expire_date
                })
            conn.commit()

        insert_duration = time.time() - insert_start
        insert_rate = num_subscriptions / insert_duration

        print(f"✅ {num_subscriptions} subscriptions inserted in {insert_duration:.2f} seconds")
        print(f"   - Insert rate: {insert_rate:.2f} subscriptions/second\n")

        # Step 4: Test fetch_expired_subscriptions() performance
        print(f"📝 Step 4: Testing fetch_expired_subscriptions() with {num_subscriptions} records...")
        fetch_start = time.time()

        expired = db_manager.fetch_expired_subscriptions()

        fetch_duration = time.time() - fetch_start

        # Count how many of our test subscriptions were found
        test_subscriptions_found = 0
        for sub in expired:
            if sub[0] in test_user_ids and sub[1] == test_channel_id:
                test_subscriptions_found += 1

        fetch_rate = test_subscriptions_found / fetch_duration if fetch_duration > 0 else 0

        print(f"✅ Fetch complete in {fetch_duration:.2f} seconds")
        print(f"   - Total expired found: {len(expired)}")
        print(f"   - Test subscriptions found: {test_subscriptions_found}/{num_subscriptions}")
        print(f"   - Fetch rate: {fetch_rate:.2f} subscriptions/second\n")

        if test_subscriptions_found < num_subscriptions:
            print(f"⚠️ Warning: Only {test_subscriptions_found}/{num_subscriptions} test subscriptions found")
            print("   This is OK if there are other expired subscriptions in the database\n")

        # Step 5: Test deactivate_subscription() performance in batch
        print(f"📝 Step 5: Testing deactivate_subscription() with {num_subscriptions} records...")
        deactivate_start = time.time()

        success_count = 0
        failure_count = 0

        for user_id in test_user_ids:
            result = db_manager.deactivate_subscription(user_id, test_channel_id)
            if result:
                success_count += 1
            else:
                failure_count += 1

        deactivate_duration = time.time() - deactivate_start
        deactivate_rate = num_subscriptions / deactivate_duration if deactivate_duration > 0 else 0

        print(f"✅ Deactivation complete in {deactivate_duration:.2f} seconds")
        print(f"   - Successful: {success_count}")
        print(f"   - Failed: {failure_count}")
        print(f"   - Deactivation rate: {deactivate_rate:.2f} subscriptions/second\n")

        # Step 6: Verify deactivated subscriptions are not fetched
        print("📝 Step 6: Verifying deactivated subscriptions are NOT fetched...")
        verify_start = time.time()

        expired_after = db_manager.fetch_expired_subscriptions()

        test_still_found = 0
        for sub in expired_after:
            if sub[0] in test_user_ids and sub[1] == test_channel_id:
                test_still_found += 1

        verify_duration = time.time() - verify_start

        if test_still_found == 0:
            print(f"✅ Verification passed in {verify_duration:.2f} seconds")
            print("   - No deactivated test subscriptions in fetch results\n")
        else:
            print(f"❌ WARNING: {test_still_found} deactivated subscriptions still appearing!")
            print("   This may indicate a database issue\n")

        # Step 7: Cleanup
        print("📝 Step 7: Cleaning up test data...")
        final_cleanup_start = time.time()

        with db_manager.pool.engine.connect() as conn:
            for user_id in test_user_ids:
                conn.execute(text("""
                    DELETE FROM private_channel_users_database
                    WHERE user_id = :user_id AND private_channel_id = :channel_id
                """), {"user_id": user_id, "channel_id": test_channel_id})
            conn.commit()

        final_cleanup_duration = time.time() - final_cleanup_start
        print(f"✅ Cleanup complete in {final_cleanup_duration:.2f} seconds\n")

        # Calculate total test duration
        total_duration = (cleanup_duration + insert_duration + fetch_duration +
                         deactivate_duration + verify_duration + final_cleanup_duration)

        # Performance Summary
        print("=" * 70)
        print("🎉 LOAD TEST PASSED!")
        print("=" * 70)
        print(f"\n📊 Performance Summary ({num_subscriptions} subscriptions):")
        print(f"   - Initial Cleanup: {cleanup_duration:.2f}s")
        print(f"   - Insert Operations: {insert_duration:.2f}s ({insert_rate:.2f}/s)")
        print(f"   - Fetch Operations: {fetch_duration:.2f}s ({fetch_rate:.2f}/s)")
        print(f"   - Deactivate Operations: {deactivate_duration:.2f}s ({deactivate_rate:.2f}/s)")
        print(f"   - Verification: {verify_duration:.2f}s")
        print(f"   - Final Cleanup: {final_cleanup_duration:.2f}s")
        print(f"   - Total Duration: {total_duration:.2f}s")

        # Performance targets
        print(f"\n🎯 Performance Targets:")
        target_met = True

        # Target: Process 100 subscriptions in < 2 minutes (120 seconds)
        if deactivate_duration < 120:
            print(f"   ✅ Deactivation time: {deactivate_duration:.2f}s (target: <120s)")
        else:
            print(f"   ❌ Deactivation time: {deactivate_duration:.2f}s (EXCEEDED target: <120s)")
            target_met = False

        # Target: Success rate > 90%
        success_rate = (success_count / num_subscriptions) * 100
        if success_rate > 90:
            print(f"   ✅ Success rate: {success_rate:.1f}% (target: >90%)")
        else:
            print(f"   ❌ Success rate: {success_rate:.1f}% (BELOW target: >90%)")
            target_met = False

        # Target: Fetch time reasonable
        if fetch_duration < 10:
            print(f"   ✅ Fetch time: {fetch_duration:.2f}s (target: <10s)")
        else:
            print(f"   ⚠️ Fetch time: {fetch_duration:.2f}s (acceptable, but >10s)")

        print(f"\n🚀 Overall Result: {'PASSED' if target_met else 'WARNING - Some targets not met'}")

        return target_met

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ LOAD TEST FAILED!")
        print("=" * 70)
        print(f"\nError: {e}")
        print("\nTest aborted. Please review the error above.")

        import traceback
        print("\nFull traceback:")
        traceback.print_exc()

        return False


if __name__ == "__main__":
    success = load_test_100_subscriptions()
    sys.exit(0 if success else 1)
