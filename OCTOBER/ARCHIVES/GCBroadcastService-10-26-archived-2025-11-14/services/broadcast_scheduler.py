#!/usr/bin/env python3
"""
BroadcastScheduler Service
Determines which broadcasts should be sent and enforces rate limiting
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class BroadcastScheduler:
    """
    Handles broadcast scheduling logic and rate limiting.

    Responsibilities:
    - Identify broadcasts that are due to be sent
    - Enforce rate limiting for manual triggers
    - Calculate next send times based on intervals
    - Queue broadcasts for execution
    """

    def __init__(self, db_client, config):
        """
        Initialize the BroadcastScheduler.

        Args:
            db_client: DatabaseClient instance
            config: Config instance (for fetching intervals)
        """
        self.db = db_client
        self.config = config
        self.logger = logging.getLogger(__name__)

    def get_due_broadcasts(self) -> List[Dict[str, Any]]:
        """
        Get all broadcast entries that are due to be sent.

        Delegates to DatabaseClient.fetch_due_broadcasts()

        Returns:
            List of broadcast entries with full channel details
        """
        broadcasts = self.db.fetch_due_broadcasts()
        self.logger.info(f"📋 Scheduler found {len(broadcasts)} broadcasts due for sending")
        return broadcasts

    def check_manual_trigger_rate_limit(
        self,
        broadcast_id: str,
        client_id: str
    ) -> Dict[str, Any]:
        """
        Check if a manual trigger is allowed based on rate limiting.

        Rate limit enforced: BROADCAST_MANUAL_INTERVAL (default 5 minutes)

        Args:
            broadcast_id: UUID of the broadcast entry
            client_id: Client UUID requesting the trigger (for verification)

        Returns:
            {
                'allowed': bool,
                'reason': str,
                'retry_after_seconds': int (if not allowed)
            }
        """
        try:
            # Fetch manual interval from Secret Manager
            manual_interval_hours = self.config.get_broadcast_manual_interval()
            manual_interval = timedelta(hours=manual_interval_hours)

            # Get last manual trigger time from database
            trigger_info = self.db.get_manual_trigger_info(broadcast_id)

            if not trigger_info:
                return {
                    'allowed': False,
                    'reason': 'Broadcast entry not found',
                    'retry_after_seconds': 0
                }

            db_client_id, last_trigger = trigger_info

            # Verify ownership
            if str(db_client_id) != str(client_id):
                self.logger.warning(
                    f"⚠️ Unauthorized manual trigger attempt: "
                    f"client {str(client_id)[:8]}... trying to trigger broadcast owned by {str(db_client_id)[:8]}..."
                )
                return {
                    'allowed': False,
                    'reason': 'Unauthorized: User does not own this channel',
                    'retry_after_seconds': 0
                }

            # Check rate limit
            if last_trigger:
                # Always use timezone-aware datetimes
                now = datetime.now(timezone.utc)

                # Ensure last_trigger is timezone-aware
                if last_trigger.tzinfo is None:
                    last_trigger = last_trigger.replace(tzinfo=timezone.utc)

                time_since_last = now - last_trigger

                if time_since_last < manual_interval:
                    retry_after = manual_interval - time_since_last
                    retry_seconds = int(retry_after.total_seconds())

                    self.logger.info(
                        f"⏳ Rate limit active for {str(broadcast_id)[:8]}...: "
                        f"retry in {retry_seconds}s"
                    )

                    return {
                        'allowed': False,
                        'reason': f'Rate limit: Must wait {manual_interval_hours} hours between manual triggers',
                        'retry_after_seconds': retry_seconds
                    }

            # All checks passed
            self.logger.info(f"✅ Manual trigger allowed for {str(broadcast_id)[:8]}...")
            return {
                'allowed': True,
                'reason': 'Manual trigger allowed',
                'retry_after_seconds': 0
            }

        except Exception as e:
            self.logger.error(f"❌ Error checking rate limit: {e}", exc_info=True)
            return {
                'allowed': False,
                'reason': f'Internal error: {str(e)}',
                'retry_after_seconds': 0
            }

    def queue_manual_broadcast(self, broadcast_id: str) -> bool:
        """
        Queue a broadcast for immediate execution (manual trigger).

        Sets next_send_time = NOW() to trigger on next cron run.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successfully queued, False otherwise
        """
        return self.db.queue_manual_broadcast(broadcast_id)

    def calculate_next_send_time(self) -> datetime:
        """
        Calculate the next send time based on BROADCAST_AUTO_INTERVAL.

        Returns:
            Datetime for next scheduled send
        """
        auto_interval_hours = self.config.get_broadcast_auto_interval()
        next_send = datetime.now() + timedelta(hours=auto_interval_hours)
        self.logger.debug(f"📅 Next send time calculated: {next_send.strftime('%Y-%m-%d %H:%M:%S')}")
        return next_send
