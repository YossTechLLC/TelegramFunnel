#!/usr/bin/env python
"""
HTTP Client for GCBotCommand
Makes requests to external services
"""
import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class HTTPClient:
    """HTTP client for calling external services"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()

    def post(self, url: str, data: Dict) -> Optional[Dict]:
        """
        Make POST request to external service

        Args:
            url: Service URL
            data: Request payload

        Returns:
            Response JSON or None on error
        """
        try:
            logger.info(f"📤 POST {url}")
            logger.debug(f"📦 Payload: {data}")

            response = self.session.post(
                url,
                json=data,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )

            response.raise_for_status()

            result = response.json()
            logger.info(f"✅ Response: {result}")

            return result

        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout calling {url}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error calling {url}: {e}")
            return None

        except ValueError as e:
            logger.error(f"❌ Invalid JSON response from {url}: {e}")
            return None

    def get(self, url: str) -> Optional[Dict]:
        """
        Make GET request to external service

        Args:
            url: Service URL

        Returns:
            Response JSON or None on error
        """
        try:
            logger.info(f"📥 GET {url}")

            response = self.session.get(
                url,
                timeout=self.timeout
            )

            response.raise_for_status()

            result = response.json()
            logger.info(f"✅ Response: {result}")

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error calling {url}: {e}")
            return None
