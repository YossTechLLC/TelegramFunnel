#!/usr/bin/env python
"""
Cloud Tasks Client for PGP_ORCHESTRATOR_v1 (Payment Processor Service).
Handles creation and dispatch of Cloud Tasks to PGP_INVITE, PGP_SPLIT1, and PGP_ACCUMULATOR.
"""
import json
import time
import datetime
from typing import Optional
from PGP_COMMON.cloudtasks import BaseCloudTasksClient


class CloudTasksClient(BaseCloudTasksClient):
    """
    Client for creating and dispatching Google Cloud Tasks.
    Inherits common methods from BaseCloudTasksClient.
    """

    def __init__(self, project_id: str, location: str, signing_key: str):
        """
        Initialize Cloud Tasks client.

        Args:
            project_id: GCP project ID
            location: Cloud region (e.g., "us-central1")
            signing_key: SUCCESS_URL_SIGNING_KEY for webhook signature
        """
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key=signing_key,
            service_name="PGP_ORCHESTRATOR_v1"
        )

    def enqueue_pgp_invite_telegram_invite(
        self,
        queue_name: str,
        target_url: str,
        encrypted_token: str,
        payment_id: int
    ) -> Optional[str]:
        """
        Enqueue a Telegram invite request to PGP_INVITE (formerly GCWebhook2).

        Args:
            queue_name: Queue name (e.g., "pgp-invite-queue")
            target_url: PGP_INVITE service URL
            encrypted_token: Encrypted token with user/channel data
            payment_id: NowPayments payment_id for idempotency tracking

        Returns:
            Task name if successful, None if failed
        """
        try:
            print(f"📨 [CLOUD_TASKS] Enqueueing Telegram invite to PGP_INVITE")

            payload = {
                "token": encrypted_token,
                "payment_id": payment_id
            }

            # Use inherited create_task method
            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing Telegram invite: {e}")
            return None

    def enqueue_pgp_split1_payment_split(
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
        payout_mode: str = 'instant'
    ) -> Optional[str]:
        """
        Enqueue a payment split request to PGP_SPLIT1 (formerly GCSplit1).

        Args:
            queue_name: Queue name (e.g., "pgp-split1-queue")
            target_url: PGP_SPLIT1 service URL
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
            print(f"💰 [CLOUD_TASKS] Enqueueing payment split to PGP_SPLIT1")
            print(f"👤 [CLOUD_TASKS] User: {user_id}, Channel: {closed_channel_id}")
            print(f"💵 [CLOUD_TASKS] Amount: ${subscription_price} → {payout_currency}")
            print(f"💰 [CLOUD_TASKS] ACTUAL ETH: {actual_eth_amount}")
            print(f"🎯 [CLOUD_TASKS] Payout Mode: {payout_mode}")

            # Prepare webhook payload (same format as old trigger_payment_split_webhook)
            webhook_data = {
                "user_id": user_id,
                "closed_channel_id": closed_channel_id,
                "wallet_address": wallet_address,
                "payout_currency": payout_currency,
                "payout_network": payout_network,
                "sub_price": subscription_price,
                "actual_eth_amount": actual_eth_amount,
                "payout_mode": payout_mode,
                "timestamp": int(time.time())
            }

            # Use inherited create_signed_task method (handles signature automatically)
            return self.create_signed_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=webhook_data
            )

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
        Enqueue a payment accumulation request to PGP_ACCUMULATOR (formerly GCAccumulator).

        Args:
            queue_name: Queue name (e.g., "pgp-accumulator-queue")
            target_url: PGP_ACCUMULATOR service URL
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
            print(f"📊 [CLOUD_TASKS] Enqueueing payment accumulation to PGP_ACCUMULATOR")
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
                # NowPayments fields (optional)
                "nowpayments_payment_id": nowpayments_payment_id,
                "nowpayments_pay_address": nowpayments_pay_address,
                "nowpayments_outcome_amount": nowpayments_outcome_amount
            }

            # Use inherited create_task method
            return self.create_task(
                queue_name=queue_name,
                target_url=target_url,
                payload=payload
            )

        except Exception as e:
            print(f"❌ [CLOUD_TASKS] Error enqueueing payment accumulation: {e}")
            return None
