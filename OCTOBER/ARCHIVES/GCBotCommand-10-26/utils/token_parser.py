#!/usr/bin/env python
"""
Token Parser for GCBotCommand
Parses subscription and donation tokens from /start command
"""
from typing import Dict, Optional
import base64
import logging

logger = logging.getLogger(__name__)

class TokenParser:
    """Parse and decode Telegram bot tokens"""

    @staticmethod
    def decode_hash(hash_part: str) -> Optional[str]:
        """
        Decode hash to channel ID

        Hash format: base64-encoded channel ID
        """
        try:
            decoded_bytes = base64.urlsafe_b64decode(hash_part + '==')  # Add padding
            channel_id = decoded_bytes.decode('utf-8')
            return channel_id
        except Exception as e:
            logger.error(f"❌ Error decoding hash: {e}")
            return None

    def parse_token(self, token: str) -> Dict:
        """
        Parse subscription or donation token

        Token formats:
        - Subscription: {hash}_{price}_{time}  (e.g., "ABC123_9d99_30")
        - Donation: {hash}_DONATE  (e.g., "ABC123_DONATE")

        Returns:
            Dictionary with parsed token data:
            {
                'type': 'subscription' | 'donation' | 'invalid',
                'channel_id': str,
                'price': float (for subscription),
                'time': int (for subscription)
            }
        """
        try:
            # Split token
            parts = token.split('_')

            if len(parts) < 2:
                return {'type': 'invalid'}

            hash_part = parts[0]
            remaining = '_'.join(parts[1:])

            # Decode hash to channel ID
            channel_id = self.decode_hash(hash_part)

            if not channel_id:
                return {'type': 'invalid'}

            # Check if donation token
            if remaining == "DONATE":
                return {
                    'type': 'donation',
                    'channel_id': channel_id
                }

            # Parse subscription token: {price}_{time}
            if '_' in remaining:
                sub_part, time_part = remaining.rsplit('_', 1)

                try:
                    time = int(time_part)
                except ValueError:
                    time = 30  # Default

                # Parse price (format: "9d99" → 9.99)
                price_str = sub_part.replace('d', '.')
                try:
                    price = float(price_str)
                except ValueError:
                    price = 5.0  # Default

                return {
                    'type': 'subscription',
                    'channel_id': channel_id,
                    'price': price,
                    'time': time
                }

            # Old format without time
            price_str = remaining.replace('d', '.')
            try:
                price = float(price_str)
            except ValueError:
                price = 5.0

            return {
                'type': 'subscription',
                'channel_id': channel_id,
                'price': price,
                'time': 30  # Default time
            }

        except Exception as e:
            logger.error(f"❌ Error parsing token: {e}")
            return {'type': 'invalid'}

    @staticmethod
    def encode_hash(channel_id: str) -> str:
        """
        Encode channel ID to hash

        Used for generating tokens (usually done by broadcast service)
        """
        try:
            encoded = base64.urlsafe_b64encode(channel_id.encode('utf-8'))
            return encoded.decode('utf-8').rstrip('=')  # Remove padding
        except Exception as e:
            logger.error(f"❌ Error encoding hash: {e}")
            return ""
