#!/usr/bin/env python
"""
Unit tests for SubscriptionManager database delegation.

Tests verify that SubscriptionManager properly delegates all database operations
to DatabaseManager (single source of truth) and contains no SQL queries.
"""
import unittest
import asyncio
import inspect
from unittest.mock import Mock, AsyncMock, patch, MagicMock


class TestSubscriptionManagerDelegation(unittest.TestCase):
    """Test suite for SubscriptionManager database delegation pattern."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock DatabaseManager
        self.mock_db_manager = Mock()
        self.mock_db_manager.fetch_expired_subscriptions = Mock(return_value=[])
        self.mock_db_manager.deactivate_subscription = Mock(return_value=True)

        # Import SubscriptionManager here to avoid import errors
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from subscription_manager import SubscriptionManager

        # Create SubscriptionManager with mock
        self.manager = SubscriptionManager(
            bot_token="fake_token_for_testing",
            db_manager=self.mock_db_manager,
            check_interval=60
        )

    def test_init_parameters(self):
        """Test that __init__ accepts correct parameters."""
        self.assertEqual(self.manager.bot_token, "fake_token_for_testing")
        self.assertEqual(self.manager.db_manager, self.mock_db_manager)
        self.assertEqual(self.manager.check_interval, 60)
        self.assertFalse(self.manager.is_running)

    def test_custom_check_interval(self):
        """Test that custom check_interval is properly stored."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from subscription_manager import SubscriptionManager

        custom_manager = SubscriptionManager(
            bot_token="test_token",
            db_manager=self.mock_db_manager,
            check_interval=30
        )
        self.assertEqual(custom_manager.check_interval, 30)

    def test_check_expired_delegates_to_database(self):
        """Test that check_expired_subscriptions calls DatabaseManager.fetch_expired_subscriptions."""
        # Run async test
        async def run_test():
            await self.manager.check_expired_subscriptions()

        asyncio.run(run_test())

        # Assert DatabaseManager method was called
        self.mock_db_manager.fetch_expired_subscriptions.assert_called_once()

    def test_deactivate_delegates_to_database(self):
        """Test that deactivation delegates to DatabaseManager."""
        # Mock fetch_expired_subscriptions to return a test subscription
        self.mock_db_manager.fetch_expired_subscriptions.return_value = [
            (123456, -1001234567890, '12:00:00', '2025-11-13')
        ]

        # Mock remove_user_from_channel to return True
        async def run_test():
            with patch.object(self.manager, 'remove_user_from_channel', return_value=True):
                await self.manager.check_expired_subscriptions()

        asyncio.run(run_test())

        # Assert deactivate_subscription was called with correct parameters
        self.mock_db_manager.deactivate_subscription.assert_called_once_with(
            123456,
            -1001234567890
        )

    def test_deactivate_called_even_on_removal_failure(self):
        """Test that deactivation is called even if user removal fails."""
        # Mock fetch_expired_subscriptions to return a test subscription
        self.mock_db_manager.fetch_expired_subscriptions.return_value = [
            (123456, -1001234567890, '12:00:00', '2025-11-13')
        ]

        # Mock remove_user_from_channel to return False (failure)
        async def run_test():
            with patch.object(self.manager, 'remove_user_from_channel', return_value=False):
                await self.manager.check_expired_subscriptions()

        asyncio.run(run_test())

        # Assert deactivate_subscription was still called (mark inactive even on failure)
        self.mock_db_manager.deactivate_subscription.assert_called_once_with(
            123456,
            -1001234567890
        )

    def test_no_sql_in_subscription_manager(self):
        """Verify subscription_manager.py doesn't contain SQL keywords."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from subscription_manager import SubscriptionManager

        # Get source code of the SubscriptionManager class
        source = inspect.getsource(SubscriptionManager)

        # SQL keywords that should NOT appear
        sql_keywords = ['SELECT', 'UPDATE', 'INSERT', 'DELETE', 'CREATE', 'DROP', 'ALTER']

        for keyword in sql_keywords:
            self.assertNotIn(keyword, source,
                           f"Found SQL keyword '{keyword}' in SubscriptionManager - should delegate to DatabaseManager")

    def test_statistics_return_structure(self):
        """Test that check_expired_subscriptions returns correct statistics structure."""
        async def run_test():
            stats = await self.manager.check_expired_subscriptions()
            return stats

        stats = asyncio.run(run_test())

        # Verify return structure
        self.assertIn('expired_count', stats)
        self.assertIn('processed_count', stats)
        self.assertIn('failed_count', stats)
        self.assertEqual(stats['expired_count'], 0)
        self.assertEqual(stats['processed_count'], 0)
        self.assertEqual(stats['failed_count'], 0)

    def test_statistics_with_successful_processing(self):
        """Test statistics tracking with successful subscription processing."""
        # Mock fetch_expired_subscriptions to return 2 test subscriptions
        self.mock_db_manager.fetch_expired_subscriptions.return_value = [
            (111111, -1001111111111, '12:00:00', '2025-11-13'),
            (222222, -1001222222222, '13:00:00', '2025-11-13')
        ]

        # Mock remove_user_from_channel to always succeed
        async def run_test():
            with patch.object(self.manager, 'remove_user_from_channel', return_value=True):
                stats = await self.manager.check_expired_subscriptions()
                return stats

        stats = asyncio.run(run_test())

        # Verify statistics
        self.assertEqual(stats['expired_count'], 2)
        self.assertEqual(stats['processed_count'], 2)
        self.assertEqual(stats['failed_count'], 0)

    def test_statistics_with_failed_processing(self):
        """Test statistics tracking with failed subscription processing."""
        # Mock fetch_expired_subscriptions to return 2 test subscriptions
        self.mock_db_manager.fetch_expired_subscriptions.return_value = [
            (111111, -1001111111111, '12:00:00', '2025-11-13'),
            (222222, -1001222222222, '13:00:00', '2025-11-13')
        ]

        # Mock remove_user_from_channel to fail
        async def run_test():
            with patch.object(self.manager, 'remove_user_from_channel', return_value=False):
                stats = await self.manager.check_expired_subscriptions()
                return stats

        stats = asyncio.run(run_test())

        # Verify statistics (failed removals still count as failed)
        self.assertEqual(stats['expired_count'], 2)
        self.assertEqual(stats['processed_count'], 0)
        self.assertEqual(stats['failed_count'], 2)

    def test_statistics_with_mixed_results(self):
        """Test statistics tracking with mixed success/failure."""
        # Mock fetch_expired_subscriptions to return 3 test subscriptions
        self.mock_db_manager.fetch_expired_subscriptions.return_value = [
            (111111, -1001111111111, '12:00:00', '2025-11-13'),
            (222222, -1001222222222, '13:00:00', '2025-11-13'),
            (333333, -1001333333333, '14:00:00', '2025-11-13')
        ]

        # Mock remove_user_from_channel to succeed twice, fail once
        call_count = [0]

        async def mock_remove(user_id, channel_id):
            call_count[0] += 1
            return call_count[0] <= 2  # First 2 succeed, 3rd fails

        async def run_test():
            with patch.object(self.manager, 'remove_user_from_channel', side_effect=mock_remove):
                stats = await self.manager.check_expired_subscriptions()
                return stats

        stats = asyncio.run(run_test())

        # Verify statistics
        self.assertEqual(stats['expired_count'], 3)
        self.assertEqual(stats['processed_count'], 2)
        self.assertEqual(stats['failed_count'], 1)


if __name__ == '__main__':
    print("🧪 Running SubscriptionManager Database Delegation Tests\n")
    print("=" * 70)

    # Run tests with verbose output
    unittest.main(verbosity=2)
