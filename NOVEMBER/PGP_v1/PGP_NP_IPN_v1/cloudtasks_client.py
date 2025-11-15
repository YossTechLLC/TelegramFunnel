#!/usr/bin/env python
"""
Cloud Tasks Client for PGP_NP_IPN_v1 (NowPayments IPN Handler).
Handles queuing validated payments to orchestrator for routing.
"""
from typing import Optional
from PGP_COMMON.cloudtasks import BaseCloudTasksClient


class CloudTasksClient(BaseCloudTasksClient):
    """
    Manages Cloud Tasks operations for PGP_NP_IPN_v1.
    Inherits common methods from BaseCloudTasksClient.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., "us-central1")
        """
        # PGP_NP_IPN doesn't use signed tasks, so pass empty signing_key
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key="",
            service_name="PGP_NP_IPN_v1"
        )

    # ========================================================================
    # NP-IPN → Orchestrator (Validated Payment)
    # ========================================================================

    def enqueue_gcwebhook1_validated_payment(
        self,
        queue_name: str,
        target_url: str,
        user_id: int,
        closed_channel_id: int,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        subscription_time_days: int,
        subscription_price: float,
        outcome_amount_usd: float,
        nowpayments_payment_id: str,
        nowpayments_pay_address: str,
        nowpayments_outcome_amount: float,
        payment_status: str = 'finished'
    ) -> Optional[str]:
        """
        Enqueue validated payment to orchestrator for routing.

        Args:
            queue_name: Cloud Tasks queue name
            target_url: Orchestrator endpoint URL
            user_id: Telegram user ID
            closed_channel_id: Private channel ID
            wallet_address: User's payout wallet address
            payout_currency: Currency for payout
            payout_network: Network for payout
            subscription_time_days: Subscription duration in days
            subscription_price: Original subscription price
            outcome_amount_usd: Actual USD value (CRITICAL)
            nowpayments_payment_id: NowPayments payment ID
            nowpayments_pay_address: NowPayments payment address
            nowpayments_outcome_amount: Outcome amount in crypto
            payment_status: Payment status (default: 'finished')

        Returns:
            Task name if successful, None otherwise
        """
        print(f"")
        print(f"🚀 [CLOUDTASKS] Creating task to orchestrator...")
        print(f"   Queue: {queue_name}")
        print(f"   Target: {target_url}")
        print(f"   User ID: {user_id}")
        print(f"   Channel ID: {closed_channel_id}")
        print(f"   💰 Outcome USD: ${outcome_amount_usd:.2f}")
        print(f"   ✅ Payment Status: {payment_status}")

        # Build payload with ALL required data
        payload = {
            "user_id": user_id,
            "closed_channel_id": closed_channel_id,
            "wallet_address": wallet_address,
            "payout_currency": payout_currency,
            "payout_network": payout_network,
            "subscription_time_days": subscription_time_days,
            "subscription_price": subscription_price,
            "outcome_amount_usd": outcome_amount_usd,
            "nowpayments_payment_id": nowpayments_payment_id,
            "nowpayments_pay_address": nowpayments_pay_address,
            "nowpayments_outcome_amount": nowpayments_outcome_amount,
            "payment_status": payment_status
        }

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )
