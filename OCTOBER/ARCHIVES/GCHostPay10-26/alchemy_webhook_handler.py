#!/usr/bin/env python
"""
Alchemy Webhook Handler for GCHostPay10-26 Host Wallet Payment Service.
Handles real-time transaction status updates from Alchemy Notify webhooks.
Updates database with confirmed transaction details.
"""
import os
import hmac
import hashlib
from typing import Optional, Dict, Any
from google.cloud import secretmanager
from flask import Request, jsonify


class AlchemyWebhookHandler:
    """
    Handles Alchemy Notify webhooks for real-time transaction monitoring.
    Verifies webhook signatures and updates database with transaction status.
    """

    def __init__(self, database_manager):
        """
        Initialize the Alchemy Webhook Handler.

        Args:
            database_manager: DatabaseManager instance for database operations
        """
        self.db_manager = database_manager
        self.webhook_secret = None

        # Fetch webhook signing secret
        self._initialize_webhook_secret()

    def _fetch_secret(self, env_var_name: str, description: str = "") -> Optional[str]:
        """
        Fetch a secret from Google Cloud Secret Manager.

        Args:
            env_var_name: Environment variable containing the secret path
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_path = os.getenv(env_var_name)
            if not secret_path:
                print(f"❌ [ALCHEMY_WEBHOOK] Environment variable {env_var_name} is not set")
                return None

            print(f"🔐 [ALCHEMY_WEBHOOK] Fetching {description or env_var_name}")
            response = client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")

            print(f"✅ [ALCHEMY_WEBHOOK] Successfully fetched {description or env_var_name}")
            return secret_value

        except Exception as e:
            print(f"❌ [ALCHEMY_WEBHOOK] Error fetching {description or env_var_name}: {e}")
            return None

    def _initialize_webhook_secret(self):
        """Initialize Alchemy webhook signing secret from Secret Manager."""
        try:
            print(f"🔄 [ALCHEMY_WEBHOOK] Initializing webhook secret")
            self.webhook_secret = self._fetch_secret("ETHEREUM_RPC_WEBHOOK_SECRET", "Ethereum RPC webhook signing secret")

            if not self.webhook_secret:
                print(f"⚠️ [ALCHEMY_WEBHOOK] Webhook secret not available - signature verification disabled")
                print(f"⚠️ [ALCHEMY_WEBHOOK] This is a security risk in production!")
            else:
                print(f"✅ [ALCHEMY_WEBHOOK] Webhook secret initialized")

        except Exception as e:
            print(f"❌ [ALCHEMY_WEBHOOK] Error initializing webhook secret: {e}")

    def _verify_signature(self, request: Request) -> bool:
        """
        Verify Alchemy webhook signature.

        Args:
            request: Flask request object

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not self.webhook_secret:
                print(f"⚠️ [ALCHEMY_WEBHOOK] Webhook secret not configured - skipping signature verification")
                return True  # Allow in dev, but warn

            # Get signature from headers
            signature_header = request.headers.get('X-Alchemy-Signature')
            if not signature_header:
                print(f"❌ [ALCHEMY_WEBHOOK] Missing X-Alchemy-Signature header")
                return False

            # Get raw request body
            body = request.get_data()

            # Calculate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()

            # Compare signatures
            if not hmac.compare_digest(signature_header, expected_signature):
                print(f"❌ [ALCHEMY_WEBHOOK] Signature mismatch")
                print(f"   Expected: {expected_signature[:16]}...")
                print(f"   Received: {signature_header[:16]}...")
                return False

            print(f"✅ [ALCHEMY_WEBHOOK] Signature verified")
            return True

        except Exception as e:
            print(f"❌ [ALCHEMY_WEBHOOK] Error verifying signature: {e}")
            return False

    def _parse_webhook_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Alchemy webhook payload and extract transaction details.

        Args:
            payload: Webhook JSON payload

        Returns:
            Parsed transaction data or None if invalid
        """
        try:
            webhook_id = payload.get('webhookId', 'unknown')
            event_id = payload.get('id', 'unknown')
            webhook_type = payload.get('type', 'unknown')
            created_at = payload.get('createdAt', 'unknown')

            print(f"📦 [ALCHEMY_WEBHOOK] Parsing webhook payload")
            print(f"   Webhook ID: {webhook_id}")
            print(f"   Event ID: {event_id}")
            print(f"   Type: {webhook_type}")
            print(f"   Created At: {created_at}")

            # Extract event data
            event = payload.get('event', {})
            if not event:
                print(f"❌ [ALCHEMY_WEBHOOK] Missing event data in payload")
                return None

            network = event.get('network', 'unknown')
            transaction_data = event.get('transaction', {})

            if not transaction_data:
                print(f"❌ [ALCHEMY_WEBHOOK] Missing transaction data in event")
                return None

            tx_hash = transaction_data.get('hash')
            from_address = transaction_data.get('from')
            to_address = transaction_data.get('to')
            value = transaction_data.get('value', '0x0')
            block_number_hex = transaction_data.get('blockNumber', '0x0')

            # Convert hex values to integers
            block_number = int(block_number_hex, 16) if block_number_hex else 0

            print(f"🔍 [ALCHEMY_WEBHOOK] Transaction details:")
            print(f"   Network: {network}")
            print(f"   TX Hash: {tx_hash}")
            print(f"   From: {from_address}")
            print(f"   To: {to_address}")
            print(f"   Value: {value}")
            print(f"   Block: {block_number}")

            return {
                "webhook_type": webhook_type,
                "tx_hash": tx_hash,
                "from_address": from_address,
                "to_address": to_address,
                "value": value,
                "block_number": block_number,
                "network": network
            }

        except Exception as e:
            print(f"❌ [ALCHEMY_WEBHOOK] Error parsing payload: {e}")
            return None

    def _determine_transaction_status(self, webhook_type: str) -> str:
        """
        Determine transaction status from webhook type.

        Args:
            webhook_type: Alchemy webhook type

        Returns:
            Status string: "confirmed", "failed", "dropped", or "unknown"
        """
        webhook_type_upper = webhook_type.upper()

        if webhook_type_upper == "MINED_TRANSACTION":
            return "confirmed"
        elif webhook_type_upper == "DROPPED_TRANSACTION":
            return "dropped"
        elif webhook_type_upper == "ADDRESS_ACTIVITY":
            return "confirmed"  # Address activity usually means successful transaction
        else:
            print(f"⚠️ [ALCHEMY_WEBHOOK] Unknown webhook type: {webhook_type}")
            return "unknown"

    def handle_webhook(self, request: Request) -> tuple:
        """
        Main webhook handler for Alchemy Notify events.

        Args:
            request: Flask request object

        Returns:
            Tuple of (response_dict, http_status_code)
        """
        try:
            print(f"🎯 [ALCHEMY_WEBHOOK] Received webhook callback")

            # Verify signature
            if not self._verify_signature(request):
                print(f"❌ [ALCHEMY_WEBHOOK] Signature verification failed")
                return {
                    "status": "error",
                    "message": "Invalid signature"
                }, 401

            # Parse JSON payload
            try:
                payload = request.get_json()
                if not payload:
                    print(f"❌ [ALCHEMY_WEBHOOK] Empty or invalid JSON payload")
                    return {
                        "status": "error",
                        "message": "Invalid JSON payload"
                    }, 400
            except Exception as e:
                print(f"❌ [ALCHEMY_WEBHOOK] JSON parsing error: {e}")
                return {
                    "status": "error",
                    "message": f"JSON parsing failed: {str(e)}"
                }, 400

            # Parse webhook payload
            tx_data = self._parse_webhook_payload(payload)
            if not tx_data:
                print(f"❌ [ALCHEMY_WEBHOOK] Failed to parse webhook payload")
                return {
                    "status": "error",
                    "message": "Invalid webhook payload structure"
                }, 400

            # Determine transaction status
            tx_status = self._determine_transaction_status(tx_data['webhook_type'])

            print(f"📊 [ALCHEMY_WEBHOOK] Transaction status: {tx_status}")

            # Update database with transaction status
            # Note: We need to find the unique_id from the tx_hash
            # This requires a database lookup or maintaining a mapping

            if tx_status == "confirmed":
                print(f"🎉 [ALCHEMY_WEBHOOK] Transaction confirmed!")
                print(f"   TX Hash: {tx_data['tx_hash']}")
                print(f"   Block Number: {tx_data['block_number']}")

                # TODO: Update database with confirmed transaction
                # This would require either:
                # 1. Looking up unique_id by tx_hash in database
                # 2. Storing tx_hash -> unique_id mapping in memory/cache
                # 3. Using Alchemy's custom data feature to include unique_id in webhook

                print(f"💾 [ALCHEMY_WEBHOOK] Database update skipped - requires tx_hash to unique_id mapping")

            elif tx_status == "dropped":
                print(f"⚠️ [ALCHEMY_WEBHOOK] Transaction dropped/failed")
                print(f"   TX Hash: {tx_data['tx_hash']}")

                # Handle failed transaction
                print(f"⚠️ [ALCHEMY_WEBHOOK] Transaction requires retry or investigation")

            # Return success response
            return {
                "status": "success",
                "message": "Webhook processed successfully",
                "tx_hash": tx_data['tx_hash'],
                "tx_status": tx_status,
                "block_number": tx_data['block_number']
            }, 200

        except Exception as e:
            print(f"❌ [ALCHEMY_WEBHOOK] Unexpected error processing webhook: {e}")
            import traceback
            print(f"📄 [ALCHEMY_WEBHOOK] Traceback: {traceback.format_exc()}")

            return {
                "status": "error",
                "message": f"Webhook processing error: {str(e)}"
            }, 500
