#!/usr/bin/env python3
"""
BroadcastExecutor Service
Executes broadcast operations by sending messages to Telegram channels
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class BroadcastExecutor:
    """
    Executes broadcast operations by sending messages to Telegram channels.

    Responsibilities:
    - Send subscription tier messages to open channels
    - Send donation messages to closed channels
    - Handle Telegram API errors gracefully
    - Update broadcast status via BroadcastTracker
    """

    def __init__(self, telegram_client, broadcast_tracker):
        """
        Initialize the BroadcastExecutor.

        Args:
            telegram_client: TelegramClient instance for sending messages
            broadcast_tracker: BroadcastTracker instance for updating status
        """
        self.telegram = telegram_client
        self.tracker = broadcast_tracker
        self.logger = logging.getLogger(__name__)

    def execute_broadcast(self, broadcast_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single broadcast operation.

        NEW BEHAVIOR:
        1. Delete old open channel message (if exists)
        2. Send new subscription message to open channel
        3. Delete old closed channel message (if exists)
        4. Send new donation message to closed channel
        5. Update message IDs in database

        Args:
            broadcast_entry: Broadcast entry from get_due_broadcasts()

        Returns:
            {
                'success': bool,
                'open_channel_sent': bool,
                'closed_channel_sent': bool,
                'errors': List[str],
                'new_open_message_id': int or None,
                'new_closed_message_id': int or None
            }
        """
        broadcast_id = broadcast_entry['id']
        open_channel_id = broadcast_entry['open_channel_id']
        closed_channel_id = broadcast_entry['closed_channel_id']

        # Get old message IDs for deletion
        old_open_msg_id = broadcast_entry.get('last_open_message_id')
        old_closed_msg_id = broadcast_entry.get('last_closed_message_id')

        self.logger.info(f"🚀 Executing broadcast {str(broadcast_id)[:8]}...")

        # Mark as in-progress
        self.tracker.update_status(broadcast_id, 'in_progress')

        errors = []
        open_sent = False
        closed_sent = False
        new_open_msg_id = None
        new_closed_msg_id = None

        try:
            # STEP 1: Delete old open channel message (if exists)
            if old_open_msg_id:
                self.logger.info(
                    f"🗑️ Deleting old open message {old_open_msg_id} from {open_channel_id}"
                )
                delete_result = self.telegram.delete_message(
                    open_channel_id,
                    old_open_msg_id
                )
                if not delete_result['success']:
                    self.logger.warning(
                        f"⚠️ Could not delete old open message: {delete_result['error']}"
                    )
                    # Continue anyway - not critical

            # STEP 2: Send new subscription message to open channel
            self.logger.info(f"📤 Sending to open channel: {open_channel_id}")
            open_result = self._send_subscription_message(broadcast_entry)
            open_sent = open_result['success']
            new_open_msg_id = open_result.get('message_id')

            if not open_sent:
                error_msg = f"Open channel: {open_result['error']}"
                errors.append(error_msg)
                self.logger.error(f"❌ {error_msg}")

            # STEP 3: Delete old closed channel message (if exists)
            if old_closed_msg_id:
                self.logger.info(
                    f"🗑️ Deleting old closed message {old_closed_msg_id} from {closed_channel_id}"
                )
                delete_result = self.telegram.delete_message(
                    closed_channel_id,
                    old_closed_msg_id
                )
                if not delete_result['success']:
                    self.logger.warning(
                        f"⚠️ Could not delete old closed message: {delete_result['error']}"
                    )
                    # Continue anyway - not critical

            # STEP 4: Send new donation message to closed channel
            self.logger.info(f"📤 Sending to closed channel: {closed_channel_id}")
            closed_result = self._send_donation_message(broadcast_entry)
            closed_sent = closed_result['success']
            new_closed_msg_id = closed_result.get('message_id')

            if not closed_sent:
                error_msg = f"Closed channel: {closed_result['error']}"
                errors.append(error_msg)
                self.logger.error(f"❌ {error_msg}")

            # STEP 5: Update message IDs in database
            if new_open_msg_id or new_closed_msg_id:
                self.tracker.update_message_ids(
                    broadcast_id,
                    open_message_id=new_open_msg_id,
                    closed_message_id=new_closed_msg_id
                )

            # Determine overall success (both must succeed)
            success = open_sent and closed_sent

            # Update broadcast status
            if success:
                self.tracker.mark_success(broadcast_id)
                self.logger.info(
                    f"✅ Broadcast {str(broadcast_id)[:8]}... completed successfully"
                )
            else:
                error_msg = '; '.join(errors)
                self.tracker.mark_failure(broadcast_id, error_msg)
                self.logger.error(
                    f"❌ Broadcast {str(broadcast_id)[:8]}... failed: {error_msg}"
                )

            return {
                'success': success,
                'open_channel_sent': open_sent,
                'closed_channel_sent': closed_sent,
                'errors': errors,
                'broadcast_id': str(broadcast_id),
                'new_open_message_id': new_open_msg_id,
                'new_closed_message_id': new_closed_msg_id
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            errors.append(error_msg)
            self.tracker.mark_failure(broadcast_id, error_msg)
            self.logger.error(f"❌ Broadcast {str(broadcast_id)[:8]}... exception: {e}", exc_info=True)

            return {
                'success': False,
                'open_channel_sent': open_sent,
                'closed_channel_sent': closed_sent,
                'errors': errors,
                'broadcast_id': str(broadcast_id),
                'new_open_message_id': new_open_msg_id,
                'new_closed_message_id': new_closed_msg_id
            }

    def _send_subscription_message(self, broadcast_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send subscription tier message to open channel.

        Args:
            broadcast_entry: Broadcast entry with channel details

        Returns:
            {'success': bool, 'error': str}
        """
        try:
            open_channel_id = broadcast_entry['open_channel_id']
            open_title = broadcast_entry.get('open_channel_title', 'Open Channel')
            open_desc = broadcast_entry.get('open_channel_description', '')
            closed_title = broadcast_entry.get('closed_channel_title', 'Closed Channel')
            closed_desc = broadcast_entry.get('closed_channel_description', '')

            # Build subscription tier buttons
            tier_buttons = []
            for tier_num in (1, 2, 3):
                price = broadcast_entry.get(f'sub_{tier_num}_price')
                time = broadcast_entry.get(f'sub_{tier_num}_time')

                if price is not None and time is not None:
                    tier_buttons.append({
                        'tier': tier_num,
                        'price': float(price),
                        'time': int(time)
                    })

            if not tier_buttons:
                self.logger.warning(f"⚠️ No tier buttons available for {open_channel_id}")
                return {'success': False, 'error': 'No subscription tiers configured'}

            # Send via TelegramClient
            result = self.telegram.send_subscription_message(
                chat_id=open_channel_id,
                open_title=open_title,
                open_desc=open_desc,
                closed_title=closed_title,
                closed_desc=closed_desc,
                tier_buttons=tier_buttons
            )

            return result

        except Exception as e:
            self.logger.error(f"❌ Exception sending subscription message: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _send_donation_message(self, broadcast_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send donation message to closed channel.

        Args:
            broadcast_entry: Broadcast entry with channel details

        Returns:
            {'success': bool, 'error': str}
        """
        try:
            closed_channel_id = broadcast_entry['closed_channel_id']
            donation_message = broadcast_entry.get(
                'closed_channel_donation_message',
                'Consider supporting our channel!'
            )
            open_channel_id = broadcast_entry['open_channel_id']

            # Send via TelegramClient
            result = self.telegram.send_donation_message(
                chat_id=closed_channel_id,
                donation_message=donation_message,
                open_channel_id=open_channel_id
            )

            return result

        except Exception as e:
            self.logger.error(f"❌ Exception sending donation message: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def execute_batch(self, broadcast_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute multiple broadcasts in sequence.

        Args:
            broadcast_entries: List of broadcast entries

        Returns:
            {
                'total': int,
                'successful': int,
                'failed': int,
                'results': List[Dict]
            }
        """
        total = len(broadcast_entries)
        successful = 0
        failed = 0
        results = []

        self.logger.info(f"📊 Executing batch of {total} broadcasts")

        for entry in broadcast_entries:
            result = self.execute_broadcast(entry)

            if result['success']:
                successful += 1
            else:
                failed += 1

            results.append({
                'broadcast_id': result['broadcast_id'],
                'open_channel_id': entry['open_channel_id'],
                'result': result
            })

        self.logger.info(
            f"📊 Batch complete: {successful}/{total} successful, {failed} failed"
        )

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'results': results
        }
