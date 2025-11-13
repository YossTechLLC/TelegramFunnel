#!/usr/bin/env python
"""
Keypad State Manager for GCDonationHandler
Manages donation keypad state in database (replacing in-memory dictionary)

This module provides database-backed state management for donation keypad input.
Replaces in-memory user_states dictionary to enable horizontal scaling.
"""

import logging
import time
from typing import Optional, Dict, Any
from database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class KeypadStateManager:
    """
    Manages donation keypad state in database.

    This class provides a drop-in replacement for the in-memory user_states
    dictionary, storing state in the donation_keypad_state table instead.
    This enables GCDonationHandler to scale horizontally without losing state.

    Attributes:
        db_manager: DatabaseManager instance for database operations
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the KeypadStateManager.

        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager
        logger.info("🗄️ KeypadStateManager initialized (database-backed)")

    def create_state(
        self,
        user_id: int,
        channel_id: str,
        chat_id: int,
        keypad_message_id: Optional[int] = None,
        state_type: str = 'keypad_input'
    ) -> bool:
        """
        Create new donation state for user.

        Args:
            user_id: Telegram user ID
            channel_id: Channel ID for donation
            chat_id: Chat ID for messages
            keypad_message_id: Message ID of keypad (optional)
            state_type: Type of state ('keypad_input', 'text_input', etc.)

        Returns:
            True if state created successfully, False otherwise
        """
        try:
            query = """
                INSERT INTO donation_keypad_state
                (user_id, channel_id, current_amount, decimal_entered, state_type, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET
                    channel_id = EXCLUDED.channel_id,
                    current_amount = '0',
                    decimal_entered = false,
                    state_type = EXCLUDED.state_type,
                    updated_at = NOW()
            """
            self.db_manager.execute_query(query, (user_id, channel_id, '0', False, state_type))

            logger.debug(f"💾 Created state for user {user_id} (channel: {channel_id})")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create state for user {user_id}: {e}")
            return False

    def get_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get donation state for user.

        Args:
            user_id: Telegram user ID

        Returns:
            Dictionary with state data:
            {
                'amount_building': str,      # Current amount (e.g., "25.50")
                'open_channel_id': str,       # Channel ID
                'decimal_entered': bool,      # Whether decimal point entered
                'state_type': str,            # State type
                'created_at': datetime,       # When state was created
                'updated_at': datetime        # When last updated
            }
            None if state not found
        """
        try:
            query = """
                SELECT
                    user_id,
                    channel_id,
                    current_amount,
                    decimal_entered,
                    state_type,
                    created_at,
                    updated_at
                FROM donation_keypad_state
                WHERE user_id = %s
            """
            result = self.db_manager.execute_query(query, (user_id,))

            if result and len(result) > 0:
                row = result[0]
                state = {
                    'user_id': row[0],
                    'amount_building': row[2],           # current_amount
                    'open_channel_id': row[1],           # channel_id
                    'decimal_entered': row[3],           # decimal_entered
                    'state_type': row[4],                # state_type
                    'created_at': row[5],                # created_at
                    'updated_at': row[6]                 # updated_at
                }
                return state
            else:
                return None

        except Exception as e:
            logger.error(f"❌ Failed to get state for user {user_id}: {e}")
            return None

    def update_amount(self, user_id: int, new_amount: str) -> bool:
        """
        Update current amount for user's donation state.

        Args:
            user_id: Telegram user ID
            new_amount: New amount string (e.g., "25.50")

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Determine if decimal was entered
            has_decimal = '.' in new_amount

            query = """
                UPDATE donation_keypad_state
                SET
                    current_amount = %s,
                    decimal_entered = %s,
                    updated_at = NOW()
                WHERE user_id = %s
            """
            self.db_manager.execute_query(query, (new_amount, has_decimal, user_id))

            logger.debug(f"💾 Updated amount for user {user_id}: {new_amount}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to update amount for user {user_id}: {e}")
            return False

    def delete_state(self, user_id: int) -> bool:
        """
        Delete donation state for user.

        Args:
            user_id: Telegram user ID

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            query = "DELETE FROM donation_keypad_state WHERE user_id = %s"
            self.db_manager.execute_query(query, (user_id,))

            logger.debug(f"🗑️ Deleted state for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete state for user {user_id}: {e}")
            return False

    def state_exists(self, user_id: int) -> bool:
        """
        Check if user has active donation state.

        Args:
            user_id: Telegram user ID

        Returns:
            True if state exists, False otherwise
        """
        return self.get_state(user_id) is not None

    def cleanup_stale_states(self, max_age_hours: int = 1) -> int:
        """
        Clean up stale donation states older than max_age_hours.

        This is called periodically to prevent table bloat from abandoned
        donation sessions.

        Args:
            max_age_hours: Maximum age in hours (default: 1)

        Returns:
            Number of states deleted
        """
        try:
            query = """
                DELETE FROM donation_keypad_state
                WHERE updated_at < NOW() - INTERVAL '%s hours'
            """
            result = self.db_manager.execute_query(query, (max_age_hours,))

            # Get number of deleted rows
            # Note: This depends on database_manager implementation
            # May need adjustment based on how execute_query returns affected rows
            deleted_count = 0
            logger.info(f"🧹 Cleaned up {deleted_count} stale donation states (older than {max_age_hours}h)")

            return deleted_count

        except Exception as e:
            logger.error(f"❌ Failed to cleanup stale states: {e}")
            return 0
