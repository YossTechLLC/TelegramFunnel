#!/usr/bin/env python
"""
Service-to-service authentication for Cloud Run.
Generates identity tokens for calling authenticated Cloud Run services.

Usage Example:
    from PGP_COMMON.auth import call_authenticated_service

    # Simple authenticated call
    response = call_authenticated_service(
        url="https://pgp-orchestrator-v1-xxx.run.app/webhook",
        method="POST",
        json_data={"order_id": "PGP-123", "amount": 29.99}
    )

    if response.status_code == 200:
        print("Success:", response.json())

Security:
- Uses Google Cloud IAM identity tokens for authentication
- Automatically refreshes tokens when expired
- Requires calling service account to have roles/run.invoker on target service
- Works only when running on Google Cloud (Cloud Run, GCE, GKE)

References:
- https://cloud.google.com/run/docs/authenticating/service-to-service
- https://cloud.google.com/python/docs/reference/google-auth/latest
"""
import logging
import requests
from typing import Optional
from google.auth import compute_engine
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)


class ServiceAuthenticator:
    """
    Generates identity tokens for authenticating to Cloud Run services.

    This class handles:
    - Identity token generation using compute engine credentials
    - Token caching to avoid unnecessary API calls
    - Automatic token refresh when expired

    Usage:
        auth = ServiceAuthenticator()
        token = auth.get_identity_token("https://pgp-orchestrator-v1-xxx.run.app")

        response = requests.post(
            "https://pgp-orchestrator-v1-xxx.run.app/webhook",
            headers={"Authorization": f"Bearer {token}"},
            json=payload
        )
    """

    def __init__(self):
        """
        Initialize service authenticator using compute engine credentials.

        This works when running on:
        - Cloud Run
        - Google Compute Engine (GCE)
        - Google Kubernetes Engine (GKE)
        - Cloud Functions

        The service account used is the one assigned to the Cloud Run service.
        """
        self._credentials_cache = {}
        logger.info("🔒 [AUTH] Service authenticator initialized")

    def get_identity_token(self, target_audience: str) -> str:
        """
        Get identity token for calling target Cloud Run service.

        Args:
            target_audience: URL of target Cloud Run service
                           (e.g., "https://pgp-orchestrator-v1-xxx.run.app")

        Returns:
            Identity token (JWT) for Authorization header

        Raises:
            Exception: If token generation fails (e.g., not running on GCP,
                      missing IAM permissions)

        Security:
        - Token is valid for 1 hour
        - Token is automatically refreshed when expired
        - Token audience is locked to target service URL

        Example:
            >>> auth = ServiceAuthenticator()
            >>> token = auth.get_identity_token("https://example.run.app")
            >>> print(token[:20])
            eyJhbGciOiJSUzI1NiIs...
        """
        try:
            # Check cache
            if target_audience in self._credentials_cache:
                credentials = self._credentials_cache[target_audience]
            else:
                # Create credentials with target audience
                credentials = compute_engine.IDTokenCredentials(
                    Request(),
                    target_audience=target_audience
                )
                self._credentials_cache[target_audience] = credentials

            # Refresh token if expired
            if not credentials.valid:
                credentials.refresh(Request())

            token = credentials.token
            logger.debug(f"✅ [AUTH] Identity token generated for {target_audience}")
            return token

        except Exception as e:
            logger.error(f"❌ [AUTH] Failed to generate identity token: {e}")
            logger.error(f"   Target audience: {target_audience}")
            logger.error(f"   Ensure service account has roles/run.invoker on target service")
            raise

    def get_authenticated_session(self, target_audience: str) -> requests.Session:
        """
        Get requests.Session with automatic identity token injection.

        Args:
            target_audience: URL of target Cloud Run service

        Returns:
            Configured requests.Session with Authorization header

        Example:
            >>> auth = ServiceAuthenticator()
            >>> session = auth.get_authenticated_session("https://example.run.app")
            >>> response = session.post("/webhook", json={"data": "value"})
        """
        session = requests.Session()
        token = self.get_identity_token(target_audience)
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        return session


# Global authenticator instance (singleton pattern)
_authenticator: Optional[ServiceAuthenticator] = None


def get_authenticator() -> ServiceAuthenticator:
    """
    Get or create global ServiceAuthenticator instance.

    This uses the singleton pattern to avoid creating multiple authenticators.

    Returns:
        ServiceAuthenticator instance

    Example:
        >>> auth = get_authenticator()
        >>> token = auth.get_identity_token("https://example.run.app")
    """
    global _authenticator
    if _authenticator is None:
        _authenticator = ServiceAuthenticator()
    return _authenticator


def call_authenticated_service(
    url: str,
    method: str = "POST",
    json_data: Optional[dict] = None,
    timeout: int = 30
) -> requests.Response:
    """
    Call authenticated Cloud Run service with automatic token injection.

    This is the recommended way to call authenticated Cloud Run services.
    It handles all the authentication complexity automatically.

    Args:
        url: Full URL of target endpoint
            (e.g., "https://pgp-orchestrator-v1-xxx.run.app/webhook")
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        json_data: JSON payload for request body (optional)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        requests.Response object

    Raises:
        requests.exceptions.RequestException: If HTTP request fails
        Exception: If token generation fails

    Example:
        >>> response = call_authenticated_service(
        ...     url="https://pgp-orchestrator-v1-xxx.run.app/webhook",
        ...     method="POST",
        ...     json_data={"order_id": "PGP-123"}
        ... )
        >>> if response.status_code == 200:
        ...     print("Success:", response.json())

    Security:
    - Automatically generates IAM identity token
    - Uses timing-safe token validation on server side
    - Requires calling service account to have roles/run.invoker
    """
    try:
        # Extract base URL for token audience
        from urllib.parse import urlparse
        parsed = urlparse(url)
        target_audience = f"{parsed.scheme}://{parsed.netloc}"

        # Get authenticator and token
        auth = get_authenticator()
        token = auth.get_identity_token(target_audience)

        # Make authenticated request
        response = requests.request(
            method=method,
            url=url,
            json=json_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=timeout
        )

        logger.info(f"✅ [AUTH] Authenticated {method} to {url}: {response.status_code}")
        return response

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ [AUTH] HTTP request failed: {e}")
        logger.error(f"   URL: {url}")
        logger.error(f"   Method: {method}")
        raise
    except Exception as e:
        logger.error(f"❌ [AUTH] Authenticated request failed: {e}")
        logger.error(f"   URL: {url}")
        raise


# ============================================================================
# Usage Examples
# ============================================================================

if __name__ == '__main__':
    """Test service authentication module."""
    import os

    print("Service Authentication Test")
    print("=" * 80)
    print("")

    # Example 1: Simple authenticated call
    print("Example 1: Simple authenticated call")
    print("-" * 80)
    print("""
from PGP_COMMON.auth import call_authenticated_service

response = call_authenticated_service(
    url="https://pgp-orchestrator-v1-xxx.run.app/webhook",
    method="POST",
    json_data={"order_id": "PGP-123", "amount": 29.99}
)

if response.status_code == 200:
    print("Success:", response.json())
    """)

    # Example 2: Using ServiceAuthenticator directly
    print("")
    print("Example 2: Using ServiceAuthenticator directly")
    print("-" * 80)
    print("""
from PGP_COMMON.auth import ServiceAuthenticator

auth = ServiceAuthenticator()
token = auth.get_identity_token("https://pgp-orchestrator-v1-xxx.run.app")

response = requests.post(
    "https://pgp-orchestrator-v1-xxx.run.app/webhook",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    json={"order_id": "PGP-123"}
)
    """)

    # Example 3: Using authenticated session
    print("")
    print("Example 3: Using authenticated session for multiple calls")
    print("-" * 80)
    print("""
from PGP_COMMON.auth import get_authenticator

auth = get_authenticator()
session = auth.get_authenticated_session("https://pgp-orchestrator-v1-xxx.run.app")

# Multiple calls reuse the same token
response1 = session.post("/webhook/payment", json={"order_id": "PGP-123"})
response2 = session.post("/webhook/status", json={"order_id": "PGP-123"})
    """)

    print("")
    print("=" * 80)
    print("✅ Test complete")
    print("")
    print("⚠️  Note: This module only works when running on Google Cloud")
    print("   (Cloud Run, GCE, GKE, Cloud Functions)")
    print("")
