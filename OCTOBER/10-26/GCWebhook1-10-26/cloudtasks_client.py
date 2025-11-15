#!/usr/bin/env python
"""
Cloud Tasks Client for GCWebhook1-10-26 (Payment Processor Service).
Handles creation and dispatch of Cloud Tasks to GCWebhook2, GCSplit1, and GCAccumulator.
Extends shared CloudTasksClient with webhook signature support.

Migration Date: 2025-11-15
Extends: _shared/cloudtasks_client.CloudTasksClient
"""
import sys
import json
import time
import hmac
import hashlib
import datetime
from typing import Optional
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

# Add parent directory to Python path for shared library access
sys.path.insert(0, '/home/user/TelegramFunnel/OCTOBER/10-26')

from _shared.cloudtasks_client import CloudTasksClient as SharedCloudTasksClient


class CloudTasksClient(SharedCloudTasksClient):
    """
    GCWebhook1-specific Cloud Tasks client.
    Extends shared CloudTasksClient with webhook signature support for GCSplit1.
    """

    def __init__(self, project_id: str, location: str, signing_key: str):
        """
        Initialize Cloud Tasks client with webhook signing support.

        Args:
            project_id: GCP project ID
            location: Cloud region (e.g., "us-central1")
            signing_key: SUCCESS_URL_SIGNING_KEY for webhook signature
        """
        # Call parent constructor
        super().__init__(project_id, location)

        # Store signing key for webhook signatures
        self.signing_key = signing_key

    # Inherits create_task() from parent SharedCloudTasksClient

    def enqueue_gcwebhook2_telegram_invite(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str,
        payment_id: int
    ) -> Optional[str]:
        """
        Enqueue a Telegram invite request to GCWebhook2.

        Args:
            queue_name: Queue name (e.g., "gcwebhook-telegram-invite-queue")
            target_url: GCWebhook2 service URL
            encrypted_token: Encrypted token with user/channel data
            payment_id: NowPayments payment_id for idempotency tracking

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"📨 [CLOUD_TASKS] Enqueueing Telegram invite to GCWebhook2")

            payload = {
                "token": encrypted_token,
                "payment_id": payment_id
            }

            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing Telegram invite: {e}")
            return None

    def enqueue_gcsplit1_payment_split(
        self,
        queue_name: str,
        target_url: str,
        user_id: int,
        closed_channel_id: int,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        subscription_price: str,
        actual_eth_amount: float = 0.0,
        payout_mode: str = 'instant'  # ✅ NEW: 'instant' or 'threshold'
    ) -> Optional[str]:
        """
        Enqueue a payment split request to GCSplit1.

        Args:
            queue_name: Queue name (e.g., "gcsplit-webhook-queue")
            target_url: GCSplit1 service URL
            user_id: User's Telegram ID
            closed_channel_id: Channel ID
            wallet_address: Client's wallet address
            payout_currency: Client's preferred payout currency
            payout_network: Client's payout network
            subscription_price: Subscription price as string
            actual_eth_amount: ACTUAL ETH from NowPayments outcome (default 0 for backward compat)
            payout_mode: 'instant' or 'threshold' - determines swap currency routing

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"💰 [CLOUD_TASKS] Enqueueing payment split to GCSplit1")
            print(f"👤 [CLOUD_TASKS] User: {user_id}, Channel: {closed_channel_id}")
            print(f"💵 [CLOUD_TASKS] Amount: ${subscription_price} → {payout_currency}")
            print(f"💰 [CLOUD_TASKS] ACTUAL ETH: {actual_eth_amount}")
            print(f"🎯 [CLOUD_TASKS] Payout Mode: {payout_mode}")  # ✅ NEW LOG

            # Prepare webhook payload (same format as old trigger_payment_split_webhook)
            webhook_data = {
                "user_id": user_id,
                "closed_channel_id": closed_channel_id,
                "wallet_address": wallet_address,
                "payout_currency": payout_currency,
                "payout_network": payout_network,
                "sub_price": subscription_price,
                "actual_eth_amount": actual_eth_amount,
                "payout_mode": payout_mode,  # ✅ NEW: Pass payout_mode to GCSplit1
                "timestamp": int(time.time())
            }

            # Add webhook signature
            payload_json = json.dumps(webhook_data)
            signature = hmac.new(
                self.signing_key.encode(),
                payload_json.encode(),
                hashlib.sha256
            ).hexdigest()

            print(f"🔐 [CLOUD_TASKS] Added webhook signature")

            # Create task with signature in headers
            parent = self.client.queue_path(self.project_id, self.location, queue_name)

            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": target_url,
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature
                    },
                    "body": payload_json.encode()
                }
            }

            # Create the task
            response = self.client.create_task(request={"parent": parent, "task": task})

            task_name = response.name
            print(f"✅ [CLOUD_TASKS] Payment split task created")
            print(f"🆔 [CLOUD_TASKS] Task name: {task_name}")

            return task_name

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing payment split: {e}")
            return None

    def enqueue_gcaccumulator_payment(
        self,
        queue_name: str,
        target_url: str,
        user_id: int,
        client_id: int,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        subscription_price: str,
        subscription_id: int,
        nowpayments_payment_id: str = None,
        nowpayments_pay_address: str = None,
        nowpayments_outcome_amount: str = None
    ) -> Optional[str]:
        """
        Enqueue a payment accumulation request to GCAccumulator.

        Args:
            queue_name: Queue name (e.g., "accumulator-payment-queue")
            target_url: GCAccumulator service URL
            user_id: User's Telegram ID
            client_id: Client's channel ID
            wallet_address: Client's wallet address
            payout_currency: Client's preferred payout currency
            payout_network: Client's payout network
            subscription_price: Subscription price as string
            subscription_id: ID from private_channel_users_database
            nowpayments_payment_id: NowPayments payment ID (optional, from IPN)
            nowpayments_pay_address: Customer's payment address (optional, from IPN)
            nowpayments_outcome_amount: Actual received amount (optional, from IPN)

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"📊 [CLOUD_TASKS] Enqueueing payment accumulation to GCAccumulator")
            print(f"👤 [CLOUD_TASKS] User: {user_id}, Client: {client_id}")
            print(f"💵 [CLOUD_TASKS] Amount: ${subscription_price} → USDT accumulation")

            if nowpayments_payment_id:
                print(f"💳 [CLOUD_TASKS] NowPayments payment_id: {nowpayments_payment_id}")
                print(f"📬 [CLOUD_TASKS] Pay address: {nowpayments_pay_address}")
                print(f"💰 [CLOUD_TASKS] Outcome amount: {nowpayments_outcome_amount}")
            else:
                print(f"⚠️ [CLOUD_TASKS] NowPayments payment_id not available (IPN may arrive later)")

            # Prepare payload
            payload = {
                "user_id": user_id,
                "client_id": client_id,
                "wallet_address": wallet_address,
                "payout_currency": payout_currency,
                "payout_network": payout_network,
                "payment_amount_usd": subscription_price,
                "subscription_id": subscription_id,
                "payment_timestamp": datetime.datetime.now().isoformat(),
                # NEW: NowPayments fields (optional)
                "nowpayments_payment_id": nowpayments_payment_id,
                "nowpayments_pay_address": nowpayments_pay_address,
                "nowpayments_outcome_amount": nowpayments_outcome_amount
            }

            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing payment accumulation: {e}")
            return None
