#!/usr/bin/env python
"""
Token Manager for PGP_BATCHPROCESSOR_v1 (Batch Payout Processor Service).
Handles token encryption for communication with PGP Split1 batch payout endpoint.
"""
import base64
import hmac
import hashlib
import json
from typing import Optional
from PGP_COMMON.tokens import BaseTokenManager


class TokenManager(BaseTokenManager):
    """
    Manages token encryption for PGP_BATCHPROCESSOR_v1.
    Inherits common methods from BaseTokenManager.
    """

    def __init__(self, signing_key: str):
        """
        Initialize the TokenManager.

        Args:
            signing_key: TPS_HOSTPAY_SIGNING_KEY for token encryption
        """
        super().__init__(signing_key=signing_key, service_name="PGP_BATCHPROCESSOR_v1")


    def encrypt_batch_token(
        self,
        batch_id: str,
        client_id: str,
        wallet_address: str,
        payout_currency: str,
        payout_network: str,
        total_amount_usdt: str,  # ✅ Accept string to preserve Decimal precision
        actual_eth_amount: float = 0.0  # ✅ NEW: Summed actual ETH from NowPayments
    ) -> Optional[str]:
        """
        Encrypt token for PGP_SPLIT1_v1 batch payout request.

        Args:
            batch_id: Batch UUID
            client_id: Client's open_channel_id
            wallet_address: Client's payout wallet address
            payout_currency: Target currency (e.g., XMR)
            payout_network: Payout network
            total_amount_usdt: Total USDT to convert (string for precision)
            actual_eth_amount: Summed actual ETH from nowpayments_outcome_amount

        Returns:
            Encrypted token string or None if failed
        """
        try:
            print(f"🔐 [TOKEN] Encrypting batch token for PGP_SPLIT1_v1")
            print(f"🆔 [TOKEN] Batch ID: {batch_id}")
            print(f"🏢 [TOKEN] Client ID: {client_id}")
            print(f"💰 [TOKEN] USDT Amount: ${total_amount_usdt}")
            print(f"💎 [TOKEN] ACTUAL ETH Amount: {actual_eth_amount} ETH")

            # Create payload
            payload = {
                'batch_id': batch_id,
                'client_id': client_id,
                'wallet_address': wallet_address,
                'payout_currency': payout_currency,
                'payout_network': payout_network,
                'amount_usdt': total_amount_usdt,
                'actual_eth_amount': actual_eth_amount  # ✅ NEW: For PGP_HOSTPAY1_v1 payment
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
