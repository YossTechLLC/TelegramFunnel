#!/usr/bin/env python
import os
import time
import struct
import base64
import hmac
import hashlib
from google.cloud import secretmanager

class SecureWebhookManager:
    def __init__(self, signing_key: str = None, base_url: str = "https://invite-webhook-291176869049.us-central1.run.app"):
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
    
    def build_signed_success_url(self, tele_open_id: int, closed_channel_id: int) -> str:
        """
        Build a cryptographically signed success URL for post-payment redirect.
        
        Args:
            tele_open_id: The user's Telegram ID
            closed_channel_id: The closed channel ID to grant access to
            
        Returns:
            A signed URL containing the encrypted token
        """
        if not self.signing_key:
            raise ValueError("Signing key is not available")
        
        tele_open_id = self.safe_int64(tele_open_id)
        closed_channel_id = self.safe_int64(closed_channel_id)
        timestamp = int(time.time())
        
        print(f"[DEBUG] Packing for token: tele_open_id={tele_open_id}, closed_channel_id={closed_channel_id}, timestamp={timestamp}")
        
        # Pack the data: 8 bytes user_id, 8 bytes channel_id, 4 bytes timestamp
        packed = struct.pack(">QQI", tele_open_id, closed_channel_id, timestamp)
        
        # Create HMAC signature
        signature = hmac.new(self.signing_key.encode(), packed, hashlib.sha256).digest()
        
        # Combine data and signature
        payload = packed + signature
        
        # Base64 encode and create token
        token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        
        return f"{self.base_url}?token={token}"
    
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
            # Expected: 8+8+4+32 = 52 bytes (user_id + channel_id + timestamp + signature)
            return len(raw) == 52
        except Exception:
            return False