#!/usr/bin/env python
import os
import time
import struct
import base64
import hmac
import hashlib
from google.cloud import secretmanager

class SecureWebhookManager:
    def __init__(self, signing_key: str = None, base_url: str = None):
        """
        Initialize the SecureWebhookManager.
        
        Args:
            signing_key: The HMAC signing key for URLs. If None, will fetch from secrets
            base_url: The base URL for the webhook service. If None, will use environment variable or default
        """
        self.signing_key = signing_key or self.fetch_success_url_signing_key()
        # Get base URL from environment variable with fallback to default
        self.base_url = base_url or os.getenv("WEBHOOK_BASE_URL", "https://tph1-291176869049.us-central1.run.app")
    
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
    
    def safe_int48(self, val) -> int:
        """
        Convert a value to a safe 48-bit integer for optimized struct packing.
        
        Args:
            val: The value to convert
            
        Returns:
            A 48-bit integer suitable for struct packing
        """
        try:
            val = int(val)
            if val < 0:
                val = 2**48 + val
            if val > 2**48 - 1:
                val = 2**48 - 1
        except Exception:
            val = 0
        return val
    
    def build_signed_success_url(self, user_id: int, closed_channel_id: int, 
                                 client_wallet_address: str = "", client_payout_currency: str = "",
                                 subscription_time: int = 30) -> str:
        """
        Build a cryptographically signed success URL for post-payment redirect.
        
        Args:
            user_id: The user's ID
            closed_channel_id: The closed channel ID to grant access to
            client_wallet_address: The client's wallet address (max 95 chars)
            client_payout_currency: The client's preferred payout currency (max 4 chars)
            subscription_time: The subscription duration in days (1-999)
            
        Returns:
            A signed URL containing the encrypted token
        """
        if not self.signing_key:
            raise ValueError("Signing key is not available")
        
        # Convert string inputs to integers if needed
        try:
            if isinstance(user_id, str):
                user_id = int(user_id)
            if isinstance(closed_channel_id, str):
                closed_channel_id = int(closed_channel_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid ID format - must be convertible to integer: {e}")
        
        # Validate ID ranges for 48-bit packing
        if not (-2**47 <= user_id <= 2**47 - 1):
            raise ValueError(f"User ID {user_id} out of 48-bit range")
        if not (-2**47 <= closed_channel_id <= 2**47 - 1):
            raise ValueError(f"Channel ID {closed_channel_id} out of 48-bit range")
        
        # Validate subscription time range (1-999 days)
        if not (1 <= subscription_time <= 999):
            raise ValueError(f"Subscription time {subscription_time} out of valid range (1-999 days)")
            
        user_id = self.safe_int48(user_id)
        closed_channel_id = self.safe_int48(closed_channel_id)
        # Use minutes since epoch for compact timestamp (2 bytes, ~45 day cycle)
        timestamp_minutes = int(time.time() // 60) % 65536
        
        # Ensure wallet address and currency are strings and handle None values
        wallet_address = (client_wallet_address or "")[:95]  # Enforce max length
        payout_currency = (client_payout_currency or "")[:4]   # Enforce max length
        
        # Encode strings to bytes
        wallet_bytes = wallet_address.encode('utf-8')
        currency_bytes = payout_currency.encode('utf-8')
        
        # Validate length constraints
        if len(wallet_bytes) > 95:
            raise ValueError(f"Wallet address too long: {len(wallet_bytes)} bytes (max 95)")
        if len(currency_bytes) > 4:
            raise ValueError(f"Currency too long: {len(currency_bytes)} bytes (max 4)")
        
        print(f"[DEBUG] Packing for token: user_id={user_id}, closed_channel_id={closed_channel_id}, timestamp_minutes={timestamp_minutes}, subscription_time={subscription_time}")
        print(f"[DEBUG] Wallet: '{wallet_address}' ({len(wallet_bytes)} bytes), Currency: '{payout_currency}' ({len(currency_bytes)} bytes)")
        
        # Optimized packing: 6 bytes user_id, 6 bytes channel_id, 2 bytes timestamp_minutes,
        # 2 bytes subscription_time, 1 byte wallet_length, N bytes wallet, 1 byte currency_length, M bytes currency
        
        # Pack 48-bit integers as 6 bytes each
        user_id_bytes = user_id.to_bytes(6, 'big')
        channel_id_bytes = closed_channel_id.to_bytes(6, 'big')
        
        # Pack the optimized data structure
        packed = user_id_bytes + channel_id_bytes + struct.pack(">H", timestamp_minutes)
        packed += struct.pack(">H", subscription_time)  # Add subscription time as 2 bytes
        packed += struct.pack(">B", len(wallet_bytes)) + wallet_bytes
        packed += struct.pack(">B", len(currency_bytes)) + currency_bytes
        
        # Create truncated HMAC signature (first 16 bytes for compactness)
        full_signature = hmac.new(self.signing_key.encode(), packed, hashlib.sha256).digest()
        signature = full_signature[:16]  # Truncate to 16 bytes
        
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
            
            # Minimum: 6+6+2+2+1+1+16 = 34 bytes (user_id + channel_id + timestamp + subscription_time + 2 length fields + signature)
            if len(raw) < 34:
                return False
                
            # Check if we can parse the variable length fields
            if len(raw) >= 16:  # At least the fixed part (6+6+2+2)
                # Try to read wallet length and currency length
                wallet_len = struct.unpack(">B", raw[16:17])[0]
                if len(raw) >= 17 + wallet_len + 1:  # Check if currency length field exists
                    currency_len = struct.unpack(">B", raw[17 + wallet_len:18 + wallet_len])[0]
                    expected_total = 16 + 1 + wallet_len + 1 + currency_len + 16  # +16 for signature
                    return len(raw) == expected_total
            
            return False
        except Exception:
            return False
