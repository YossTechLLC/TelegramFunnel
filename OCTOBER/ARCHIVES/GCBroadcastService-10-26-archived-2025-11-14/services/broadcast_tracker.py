#!/usr/bin/env python3
"""
BroadcastTracker Service
Tracks broadcast state and updates database
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class BroadcastTracker:
    """
    Tracks broadcast state and updates the broadcast_manager table.

    Responsibilities:
    - Update broadcast status (pending → in_progress → completed/failed)
    - Track success/failure statistics
    - Calculate and set next send times
    - Handle error logging
    """

    def __init__(self, db_client, config):
        """
        Initialize the BroadcastTracker.

        Args:
            db_client: DatabaseClient instance
            config: Config instance (for intervals)
        """
        self.db = db_client
        self.config = config
        self.logger = logging.getLogger(__name__)

    def update_status(self, broadcast_id: str, status: str) -> bool:
        """
        Update broadcast status.

        Args:
            broadcast_id: UUID of the broadcast entry
            status: New status ('pending', 'in_progress', 'completed', 'failed', 'skipped')

        Returns:
            True if successful, False otherwise
        """
        return self.db.update_broadcast_status(broadcast_id, status)

    def mark_success(self, broadcast_id: str) -> bool:
        """
        Mark broadcast as successfully completed.

        Updates:
        - broadcast_status = 'completed'
        - last_sent_time = NOW()
        - next_send_time = NOW() + BROADCAST_AUTO_INTERVAL
        - total_broadcasts += 1
        - successful_broadcasts += 1
        - consecutive_failures = 0
        - last_error_message = NULL

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successful, False otherwise
        """
        # Get auto interval from config
        auto_interval_hours = self.config.get_broadcast_auto_interval()
        next_send = datetime.now() + timedelta(hours=auto_interval_hours)

        success = self.db.update_broadcast_success(broadcast_id, next_send)

        if success:
            self.logger.info(
                f"✅ Broadcast {str(broadcast_id)[:8]}... marked as success. "
                f"Next send: {next_send.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        return success

    def mark_failure(self, broadcast_id: str, error_message: str) -> bool:
        """
        Mark broadcast as failed.

        Updates:
        - broadcast_status = 'failed'
        - failed_broadcasts += 1
        - consecutive_failures += 1
        - last_error_message = error_message
        - last_error_time = NOW()
        - is_active = false (if consecutive_failures >= 5)

        Args:
            broadcast_id: UUID of the broadcast entry
            error_message: Error description

        Returns:
            True if successful, False otherwise
        """
        # Truncate error message if too long
        if len(error_message) > 500:
            error_message = error_message[:497] + "..."

        success = self.db.update_broadcast_failure(broadcast_id, error_message)

        if success:
            self.logger.error(
                f"❌ Broadcast {str(broadcast_id)[:8]}... marked as failure: {error_message[:100]}"
            )

        return success

    def reset_consecutive_failures(self, broadcast_id: str) -> bool:
        """
        Reset consecutive failure count (useful for manual re-enable).

        This is typically called when manually reactivating a disabled broadcast.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE broadcast_manager
                    SET consecutive_failures = 0,
                        is_active = true
                    WHERE id = %s
                """, (broadcast_id,))

                conn.commit()
                self.logger.info(f"🔄 Reset consecutive failures: {broadcast_id[:8]}...")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error resetting failures: {e}")
            return False

    def update_message_ids(
        self,
        broadcast_id: str,
        open_message_id: Optional[int] = None,
        closed_message_id: Optional[int] = None
    ) -> bool:
        """
        Update the last sent message IDs for a broadcast.

        This enables deletion of old messages when resending broadcasts.

        Args:
            broadcast_id: UUID of the broadcast entry
            open_message_id: Telegram message ID sent to open channel
            closed_message_id: Telegram message ID sent to closed channel

        Returns:
            True if successful, False otherwise

        Note:
            Only updates provided message IDs (supports partial updates)
        """
        try:
            # Build dynamic update query
            update_fields = []
            params = []

            if open_message_id is not None:
                update_fields.append("last_open_message_id = %s")
                update_fields.append("last_open_message_sent_at = NOW()")
                params.append(open_message_id)

            if closed_message_id is not None:
                update_fields.append("last_closed_message_id = %s")
                update_fields.append("last_closed_message_sent_at = NOW()")
                params.append(closed_message_id)

            if not update_fields:
                self.logger.warning("⚠️ No message IDs provided to update")
                return False

            # Add broadcast_id to params
            params.append(broadcast_id)

            # Construct query
            query = f"""
                UPDATE broadcast_manager
                SET {', '.join(update_fields)}
                WHERE id = %s
            """

            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, tuple(params))
                conn.commit()

                self.logger.info(
                    f"📝 Updated message IDs for broadcast {str(broadcast_id)[:8]}... "
                    f"(open={open_message_id}, closed={closed_message_id})"
                )

                return True

        except Exception as e:
            self.logger.error(f"❌ Failed to update message IDs: {e}")
            # Don't raise - this is supplementary functionality
            return False
