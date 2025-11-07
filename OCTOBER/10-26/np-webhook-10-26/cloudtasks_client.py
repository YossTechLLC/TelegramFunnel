#!/usr/bin/env python
"""
CloudTasks Client for NP-Webhook
Handles queuing validated payments to GCWebhook1 for orchestration.
"""
import json
from typing import Optional
from google.cloud import tasks_v2

class CloudTasksClient:
    """Client for creating Cloud Tasks to GCWebhook1."""

    def __init__(self, project_id: str, location: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: GCP project ID
            location: GCP location (e.g., 'us-central1')
        """
        self.project_id = project_id
        self.location = location
        self.client = tasks_v2.CloudTasksClient()
        print(f"✅ [CLOUDTASKS] Client initialized for project: {project_id}, location: {location}")

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
        payment_status: str = 'finished'  # ✅ NEW: Default to 'finished' for safety
    ) -> Optional[str]:
        """
        Enqueue validated payment to GCWebhook1 for orchestration.

        This method sends ALL payment configuration data plus the CRITICAL
        outcome_amount_usd field to GCWebhook1 for payout routing decisions.

        Args:
            queue_name: Cloud Tasks queue name
            target_url: GCWebhook1 endpoint URL (should include /process-validated-payment)
            user_id: Telegram user ID
            closed_channel_id: Private channel ID
            wallet_address: User's payout wallet address
            payout_currency: Currency for payout (e.g., 'USDT')
            payout_network: Network for payout (e.g., 'trc20')
            subscription_time_days: Subscription duration in days
            subscription_price: Original declared subscription price
            outcome_amount_usd: ACTUAL USD value from CoinGecko (CRITICAL)
            nowpayments_payment_id: NowPayments payment ID
            nowpayments_pay_address: NowPayments payment address
            nowpayments_outcome_amount: Outcome amount in crypto
            payment_status: NowPayments payment status (default: 'finished')

        Returns:
            Task name if successful, None otherwise
        """
        try:
            print(f"")
            print(f"🚀 [CLOUDTASKS] Creating task to GCWebhook1...")
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
                "outcome_amount_usd": outcome_amount_usd,  # CRITICAL FIELD
                "nowpayments_payment_id": nowpayments_payment_id,
                "nowpayments_pay_address": nowpayments_pay_address,
                "nowpayments_outcome_amount": nowpayments_outcome_amount,
                "payment_status": payment_status  # ✅ NEW: Include status in payload
            }

            # Get queue path
            parent = self.client.queue_path(self.project_id, self.location, queue_name)

            # Create task
            task = {
                'http_request': {
                    'http_method': tasks_v2.HttpMethod.POST,
                    'url': target_url,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps(payload).encode()
                }
            }

            # Submit task
            response = self.client.create_task(request={"parent": parent, "task": task})

            print(f"✅ [CLOUDTASKS] Task created successfully")
            print(f"🆔 [CLOUDTASKS] Task name: {response.name}")
            return response.name

        except Exception as e:
            print(f"❌ [CLOUDTASKS] Failed to create task: {e}")
            import traceback
            traceback.print_exc()
            return None
