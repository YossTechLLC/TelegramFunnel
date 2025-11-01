#!/usr/bin/env python
"""
Token Manager for GCBatchProcessor-10-26 (Batch Payout Processor Service).
Handles token encryption for communication with GCSplit1 batch payout endpoint.
"""
import base64
import hmac
import hashlib
import json
from typing import Optional


class TokenManager:
    """
    Manages token encryption for GCBatchProcessor-10-26.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: TPS_HOSTPAY_SIGNING_KEY for token encryption
        """
        self.signing_key = signing_key
        print(f"🔐 [TOKEN] TokenManager initialized")

    def encrypt_batch_token(
        self,
        batch_id: str,
        client_id: str,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        total_amount_usdt: str  # ✅ Accept string to preserve Decimal precision
    ) -> Optional[str]:
        """
        Encrypt token for GCSplit1 batch payout request.

        Args:
            batch_id: Batch UUID
            client_id: Client's open_channel_id
            wallet_address: Client's payout wallet address
            payout_currency: Target currency (e.g., XMR)
            payout_network: Payout network
            total_amount_usdt: Total USDT to convert (string for precision)

        Returns:
            Encrypted token string or None if failed
        """
        try:
            print(f"🔐 [TOKEN] Encrypting batch token for GCSplit1")
            print(f"🆔 [TOKEN] Batch ID: {batch_id}")
            print(f"🏢 [TOKEN] Client ID: {client_id}")
            print(f"💰 [TOKEN] Amount: ${total_amount_usdt} USDT")

            # Create payload
            payload = {
                'batch_id': batch_id,
                'client_id': client_id,
                'wallet_address': wallet_address,
                'payout_currency': payout_currency,
                'payout_network': payout_network,
                'amount_usdt': total_amount_usdt
            }

            # Convert to JSON bytes
            payload_bytes = json.dumps(payload).encode('utf-8')

            # Generate HMAC signature
            signature = hmac.new(
                self.signing_key.encode(),
                payload_bytes,
                hashlib.sha256
            ).digest()

            # Combine payload + signature
            token_bytes = payload_bytes + signature[:16]  # Use truncated signature

            # Base64 encode
            token = base64.urlsafe_b64encode(token_bytes).decode('utf-8').rstrip('=')

            print(f"✅ [TOKEN] Token encrypted successfully")

            return token

        except Exception as e:
            print(f"❌ [TOKEN] Error encrypting token: {e}")
            return None
