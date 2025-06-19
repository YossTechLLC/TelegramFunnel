#!/usr/bin/env python
import os
import time
import struct
import base64
import hmac
import hashlib
from google.cloud import secretmanager

class SecureWebhookManager:
    def __init__(self, signing_key: str = None, base_url: str = "https://tph1-291176869049.us-central1.run.app"):
        """
        Initialize the SecureWebhookManager.
        
        Args:
            signing_key: The HMAC signing key for URLs. If None, will fetch from secrets
            base_url: The base URL for the webhook service
        """
        self.signing_key = signing_key or self.fetch_success_url_signing_key()
        self.base_url = base_url
    
    def fetch_success_url_signing_key(self) -> str:
        """Fetch the signing key from Google Secret Manager."""
        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_name = os.getenv("SUCCESS_URL_SIGNING_KEY")
            if not secret_name:
                raise ValueError("Environment variable SUCCESS_URL_SIGNING_KEY is not set.")
            secret_path = f"{secret_name}"
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"Error fetching the SUCCESS_URL_SIGNING_KEY: {e}")
            return None
    
    def safe_int64(self, val) -> int:
        """
        Convert a value to a safe 64-bit integer for struct packing.
        
        Args:
            val: The value to convert
            
        Returns:
            A 64-bit integer suitable for struct packing
        """
        try:
            val = int(val)
            if val < 0:
                val = 2**64 + val
            if val > 2**64 - 1:
                val = 2**64 - 1
        except Exception:
            val = 0
        return val
    
    def build_signed_success_url(self, tele_open_id: int, closed_channel_id: int, 
                                 client_wallet_address: str = "", client_payout_currency: str = "") -> str:
        """
        Build a cryptographically signed success URL for post-payment redirect.
        
        Args:
            tele_open_id: The user's Telegram ID
            closed_channel_id: The closed channel ID to grant access to
            client_wallet_address: The client's wallet address
            client_payout_currency: The client's preferred payout currency
            
        Returns:
            A signed URL containing the encrypted token
        """
        if not self.signing_key:
            raise ValueError("Signing key is not available")
        
        tele_open_id = self.safe_int64(tele_open_id)
        closed_channel_id = self.safe_int64(closed_channel_id)
        timestamp = int(time.time())
        
        # Ensure wallet address and currency are strings and handle None values
        wallet_address = client_wallet_address or ""
        payout_currency = client_payout_currency or ""
        
        # Encode strings to bytes
        wallet_bytes = wallet_address.encode('utf-8')
        currency_bytes = payout_currency.encode('utf-8')
        
        print(f"[DEBUG] Packing for token: tele_open_id={tele_open_id}, closed_channel_id={closed_channel_id}, timestamp={timestamp}")
        print(f"[DEBUG] Wallet: '{wallet_address}' ({len(wallet_bytes)} bytes), Currency: '{payout_currency}' ({len(currency_bytes)} bytes)")
        
        # Pack the data: 8 bytes user_id, 8 bytes channel_id, 4 bytes timestamp, 
        # 2 bytes wallet_length, N bytes wallet, 2 bytes currency_length, M bytes currency
        packed = struct.pack(">QQI", tele_open_id, closed_channel_id, timestamp)
        packed += struct.pack(">H", len(wallet_bytes)) + wallet_bytes
        packed += struct.pack(">H", len(currency_bytes)) + currency_bytes
        
        # Create HMAC signature
        signature = hmac.new(self.signing_key.encode(), packed, hashlib.sha256).digest()
        
        # Combine data and signature
        payload = packed + signature
        
        # Base64 encode and create token
        token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        
        # Build the complete success URL
        success_url = f"{self.base_url}?token={token}"
        
        print(f"[DEBUG] Complete success URL generated: {success_url}")
        print(f"[DEBUG] Token length: {len(token)} characters")
        print(f"[DEBUG] Payload size: {len(payload)} bytes")
        
        return success_url
    
    def verify_token_format(self, token: str) -> bool:
        """
        Verify that a token has the correct format (for testing purposes).
        
        Args:
            token: The token to verify
            
        Returns:
            True if token format is valid, False otherwise
        """
        try:
            # Pad the token if base64 length is not a multiple of 4
            padding = '=' * (-len(token) % 4)
            raw = base64.urlsafe_b64decode(token + padding)
            
            # Minimum: 8+8+4+2+2+32 = 56 bytes (user_id + channel_id + timestamp + 2 length fields + signature)
            if len(raw) < 56:
                return False
                
            # Check if we can parse the variable length fields
            if len(raw) >= 20:  # At least the fixed part (8+8+4)
                # Try to read wallet length and currency length
                wallet_len = struct.unpack(">H", raw[20:22])[0]
                if len(raw) >= 22 + wallet_len + 2:  # Check if currency length field exists
                    currency_len = struct.unpack(">H", raw[22 + wallet_len:24 + wallet_len])[0]
                    expected_total = 20 + 2 + wallet_len + 2 + currency_len + 32  # +32 for signature
                    return len(raw) == expected_total
            
            return False
        except Exception:
            return False
