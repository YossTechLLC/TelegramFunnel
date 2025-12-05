#!/usr/bin/env python
"""
Expiration Handler for GCSubscriptionMonitor
Core business logic for processing expired subscriptions
"""
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class ExpirationHandler:
    """Handles expired subscription processing workflow"""

    def __init__(self, db_manager, telegram_client):
        """
        Initialize expiration handler.

        Args:
            db_manager: Database manager instance
            telegram_client: Telegram client instance
        """
        self.db_manager = db_manager
        self.telegram_client = telegram_client
        logger.info("🔧 ExpirationHandler initialized")

    def process_expired_subscriptions(self) -> Dict:
        """
        Main processing workflow for expired subscriptions.

        Returns:
            Dictionary with processing statistics:
            {
                "expired_count": int,       # Total expired found
                "processed_count": int,     # Successfully processed
                "failed_count": int,        # Failed to process
                "details": List[Dict]       # Details of each processed subscription
            }
        """
        logger.info("🔍 Starting expired subscriptions check...")

        # Fetch expired subscriptions from database
        expired_subscriptions = self.db_manager.fetch_expired_subscriptions()

        expired_count = len(expired_subscriptions)

        if expired_count == 0:
            logger.info("✅ No expired subscriptions found")
            return {
                "expired_count": 0,
                "processed_count": 0,
                "failed_count": 0,
                "details": []
            }

        logger.info(f"📊 Found {expired_count} expired subscriptions to process")

        processed_count = 0
        failed_count = 0
        details = []

        # Process each expired subscription
        for subscription in expired_subscriptions:
            user_id, private_channel_id, expire_time, expire_date = subscription

            try:
                # Remove user from channel via Telegram Bot API
                removal_success = self.telegram_client.remove_user_sync(
                    user_id=user_id,
                    private_channel_id=private_channel_id
                )

                # Update database regardless of removal success
                # (user may have already left, but we still mark inactive)
                deactivation_success = self.db_manager.deactivate_subscription(
                    user_id=user_id,
                    private_channel_id=private_channel_id
                )

                if removal_success and deactivation_success:
                    processed_count += 1
                    logger.info(
                        f"✅ Successfully processed expired subscription: "
                        f"user {user_id} removed from channel {private_channel_id}"
                    )

                    details.append({
                        "user_id": user_id,
                        "channel_id": private_channel_id,
                        "status": "success",
                        "removed_from_channel": removal_success,
                        "deactivated_in_db": deactivation_success
                    })

                elif deactivation_success:
                    # Removal failed but deactivation succeeded
                    processed_count += 1
                    logger.warning(
                        f"⚠️ Partially processed: user {user_id}, channel {private_channel_id} "
                        f"(removal failed but marked inactive)"
                    )

                    details.append({
                        "user_id": user_id,
                        "channel_id": private_channel_id,
                        "status": "partial",
                        "removed_from_channel": removal_success,
                        "deactivated_in_db": deactivation_success
                    })

                else:
                    # Both operations failed
                    failed_count += 1
                    logger.error(
                        f"❌ Failed to process expired subscription: "
                        f"user {user_id}, channel {private_channel_id}"
                    )

                    details.append({
                        "user_id": user_id,
                        "channel_id": private_channel_id,
                        "status": "failed",
                        "removed_from_channel": removal_success,
                        "deactivated_in_db": deactivation_success
                    })

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"❌ Error processing expired subscription "
                    f"for user {user_id}, channel {private_channel_id}: {e}",
                    exc_info=True
                )

                details.append({
                    "user_id": user_id,
                    "channel_id": private_channel_id,
                    "status": "error",
                    "error": str(e)
                })

        logger.info(
            f"🏁 Expiration processing complete: "
            f"{expired_count} found, {processed_count} processed, {failed_count} failed"
        )

        return {
            "expired_count": expired_count,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "details": details
        }
