#!/usr/bin/env python
"""
📢 Broadcast Service for PGP_WEBAPI_v1
Handles broadcast_manager table operations
"""
from typing import Optional


class BroadcastService:
    """Handles broadcast_manager operations"""

    @staticmethod
    def create_broadcast_entry(
        conn,
        client_id: str,
        open_channel_id: str,
        closed_channel_id: str
    ) -> str:
        """
        Create a new broadcast_manager entry for a channel pair.

        This method is called during channel registration to automatically
        create the associated broadcast_manager entry that enables the
        "Resend Notification" feature on the dashboard.

        Args:
            conn: Database connection (from db_manager.get_db())
            client_id: User UUID (from registered_users table)
            open_channel_id: Telegram channel ID for open channel
            closed_channel_id: Telegram channel ID for closed channel

        Returns:
            str: UUID of created broadcast_manager entry

        Raises:
            ValueError: If channel pair already exists or invalid data
            Exception: Database errors (FK violations, connection issues, etc.)

        Example:
            >>> with db_manager.get_db() as conn:
            ...     broadcast_id = BroadcastService.create_broadcast_entry(
            ...         conn, user_id, "12345", "67890"
            ...     )
            ...     print(f"Created broadcast_id: {broadcast_id}")
        """
        try:
            cursor = conn.cursor()

            # Insert broadcast_manager entry with initial state
            # Initial state: pending, active, scheduled for immediate processing
            cursor.execute("""
                INSERT INTO broadcast_manager (
                    client_id,
                    open_channel_id,
                    closed_channel_id,
                    next_send_time,
                    broadcast_status,
                    is_active,
                    total_broadcasts,
                    successful_broadcasts,
                    failed_broadcasts,
                    consecutive_failures,
                    manual_trigger_count
                ) VALUES (
                    %s, %s, %s, NOW(), 'pending', true, 0, 0, 0, 0, 0
                )
                RETURNING id
            """, (client_id, open_channel_id, closed_channel_id))

            result = cursor.fetchone()

            if not result:
                raise Exception("Failed to create broadcast_manager entry - no ID returned")

            broadcast_id = str(result[0])
            cursor.close()

            # Log success with emoji pattern (📢 for broadcasts)
            print(f"📢 Created broadcast_manager entry: broadcast_id={broadcast_id}, "
                  f"user={client_id[:8]}..., open_channel={open_channel_id}, "
                  f"closed_channel={closed_channel_id}")

            return broadcast_id

        except Exception as e:
            # Check if it's a duplicate key error (UNIQUE constraint violation)
            error_message = str(e)
            if 'unique_channel_pair' in error_message.lower() or 'duplicate key' in error_message.lower():
                print(f"⚠️ Broadcast entry already exists for channel pair: "
                      f"open={open_channel_id}, closed={closed_channel_id}")
                raise ValueError(f"Broadcast entry already exists for this channel pair: {open_channel_id}/{closed_channel_id}")

            # Check if it's a FK constraint violation (invalid client_id)
            if 'fk_broadcast_client' in error_message.lower() or 'foreign key' in error_message.lower():
                print(f"❌ Invalid client_id (FK violation): {client_id}")
                raise ValueError(f"Invalid client_id: {client_id} does not exist in registered_users")

            # Log other errors
            print(f"❌ Error creating broadcast_manager entry: {e}")
            raise

    @staticmethod
    def get_broadcast_by_channel_pair(
        conn,
        open_channel_id: str,
        closed_channel_id: str
    ) -> Optional[str]:
        """
        Get broadcast_id for a channel pair (if it exists).

        Useful for checking if a broadcast_manager entry already exists
        before attempting to create one.

        Args:
            conn: Database connection
            open_channel_id: Telegram channel ID for open channel
            closed_channel_id: Telegram channel ID for closed channel

        Returns:
            str: UUID of broadcast_manager entry, or None if not found

        Example:
            >>> with db_manager.get_db() as conn:
            ...     broadcast_id = BroadcastService.get_broadcast_by_channel_pair(
            ...         conn, "12345", "67890"
            ...     )
            ...     if broadcast_id:
            ...         print(f"Broadcast entry exists: {broadcast_id}")
        """
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id
                FROM broadcast_manager
                WHERE open_channel_id = %s
                    AND closed_channel_id = %s
            """, (open_channel_id, closed_channel_id))

            result = cursor.fetchone()
            cursor.close()

            if result:
                broadcast_id = str(result[0])
                print(f"📢 Found existing broadcast entry: broadcast_id={broadcast_id}, "
                      f"open_channel={open_channel_id}, closed_channel={closed_channel_id}")
                return broadcast_id
            else:
                print(f"📢 No broadcast entry found for channel pair: "
                      f"open_channel={open_channel_id}, closed_channel={closed_channel_id}")
                return None

        except Exception as e:
            print(f"❌ Error checking broadcast entry: {e}")
            raise
