"""
Redis Client for Nonce Tracking (Replay Attack Prevention)

This module provides Redis-based nonce tracking to prevent replay attacks
on HMAC-authenticated endpoints.

Security Fix: C-02 - Replay Attack Prevention
OWASP: A07:2021 - Identification and Authentication Failures
CWE: CWE-294 (Authentication Bypass by Capture-replay)

How it works:
1. Client sends request with HMAC signature + timestamp
2. Server generates nonce: SHA256(payload + timestamp + secret)
3. Server checks if nonce exists in Redis
4. If nonce exists → Reject (replay attack)
5. If nonce doesn't exist → Store nonce in Redis with TTL → Accept request

Dependencies:
- redis: Python Redis client
"""

import hashlib
import logging
from typing import Optional
from google.cloud import secretmanager

# Get logger for this module
logger = logging.getLogger(__name__)

# Try to import redis
try:
    import redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("⚠️ [REDIS_CLIENT] redis not installed - nonce tracking unavailable")


class NonceTrackerError(Exception):
    """Raised when nonce tracking operations fail."""
    pass


class NonceTracker:
    """
    Redis-based nonce tracker for preventing replay attacks.

    Stores request nonces in Redis with TTL to prevent replay attacks.
    Each nonce is derived from request payload + timestamp + secret.

    Attributes:
        redis_client: Redis connection
        default_ttl: Default TTL for nonces (seconds)
        key_prefix: Prefix for Redis keys to avoid collisions
    """

    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        redis_password: Optional[str] = None,
        default_ttl: int = 300,  # 5 minutes default
        key_prefix: str = "nonce:",
        project_id: str = "pgp-live"
    ):
        """
        Initialize NonceTracker with Redis connection.

        Args:
            redis_host: Redis host (if None, fetches from Secret Manager)
            redis_port: Redis port (if None, fetches from Secret Manager)
            redis_password: Redis password (optional for Memorystore)
            default_ttl: Default TTL for nonces in seconds
            key_prefix: Prefix for Redis keys
            project_id: GCP project ID for Secret Manager

        Raises:
            NonceTrackerError: If Redis is unavailable or connection fails
        """
        if not REDIS_AVAILABLE:
            raise NonceTrackerError(
                "Redis nonce tracking unavailable - redis library not installed. "
                "Please install: pip install redis"
            )

        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.project_id = project_id

        # Get Redis connection details from Secret Manager if not provided
        if redis_host is None or redis_port is None:
            try:
                redis_host, redis_port = self._get_redis_config_from_secrets()
            except Exception as e:
                logger.error(f"❌ [REDIS_CLIENT] Failed to get Redis config from secrets: {e}")
                raise NonceTrackerError(f"Failed to get Redis configuration: {e}")

        # Create Redis connection
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=0,  # Use database 0
                socket_connect_timeout=5,
                socket_timeout=5,
                decode_responses=True,  # Automatically decode bytes to strings
                retry_on_timeout=True,
                health_check_interval=30
            )

            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ [REDIS_CLIENT] Connected to Redis at {redis_host}:{redis_port}")

        except (RedisConnectionError, RedisError) as e:
            logger.error(f"❌ [REDIS_CLIENT] Failed to connect to Redis: {e}")
            raise NonceTrackerError(f"Redis connection failed: {e}")

    def _get_redis_config_from_secrets(self) -> tuple[str, int]:
        """
        Fetch Redis host and port from GCP Secret Manager.

        Returns:
            Tuple of (host, port)

        Raises:
            NonceTrackerError: If secrets cannot be fetched
        """
        try:
            client = secretmanager.SecretManagerServiceClient()

            # Get Redis host
            host_secret_name = f"projects/{self.project_id}/secrets/PGP_REDIS_HOST/versions/latest"
            host_response = client.access_secret_version(request={"name": host_secret_name})
            redis_host = host_response.payload.data.decode('UTF-8').strip()

            # Get Redis port
            port_secret_name = f"projects/{self.project_id}/secrets/PGP_REDIS_PORT/versions/latest"
            port_response = client.access_secret_version(request={"name": port_secret_name})
            redis_port = int(port_response.payload.data.decode('UTF-8').strip())

            logger.debug(f"🔍 [REDIS_CLIENT] Fetched Redis config from Secret Manager")
            return redis_host, redis_port

        except Exception as e:
            logger.error(f"❌ [REDIS_CLIENT] Failed to fetch Redis config from Secret Manager: {e}")
            raise

    def generate_nonce(self, payload: str, timestamp: str, secret: str) -> str:
        """
        Generate a unique nonce from request payload + timestamp + secret.

        The nonce is a SHA256 hash to ensure uniqueness and prevent collisions.

        Args:
            payload: Request payload (JSON string or body)
            timestamp: Request timestamp (ISO format string)
            secret: Shared secret for nonce generation

        Returns:
            Nonce as hex string (64 characters)

        Examples:
            >>> generate_nonce('{"user_id": 123}', '2025-11-18T12:00:00Z', 'secret')
            'a1b2c3d4...' (64-char hex string)
        """
        # Combine payload + timestamp + secret
        combined = f"{payload}{timestamp}{secret}"

        # Generate SHA256 hash
        nonce = hashlib.sha256(combined.encode('utf-8')).hexdigest()

        logger.debug(f"🔍 [REDIS_CLIENT] Generated nonce: {nonce[:16]}...")
        return nonce

    def check_and_store_nonce(
        self,
        nonce: str,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Check if nonce exists in Redis, and store it if new.

        This operation is atomic (uses Redis SET NX) to prevent race conditions.

        Args:
            nonce: Nonce to check and store
            ttl_seconds: TTL for nonce (uses default_ttl if None)

        Returns:
            True if nonce is new (stored successfully)
            False if nonce already exists (replay attack detected)

        Raises:
            NonceTrackerError: If Redis operation fails

        Examples:
            >>> check_and_store_nonce('abc123', 300)
            True  # First request
            >>> check_and_store_nonce('abc123', 300)
            False  # Replay attack detected
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        redis_key = f"{self.key_prefix}{nonce}"

        try:
            # Use SET NX (set if not exists) for atomic operation
            # Returns True if key was set (nonce is new)
            # Returns False if key already exists (replay attack)
            was_set = self.redis_client.set(
                redis_key,
                "1",  # Value doesn't matter, we just track existence
                nx=True,  # Only set if key doesn't exist (atomic)
                ex=ttl  # Expire after TTL seconds
            )

            if was_set:
                logger.info(f"✅ [REDIS_CLIENT] Nonce stored (new request): {nonce[:16]}... (TTL: {ttl}s)")
                return True
            else:
                logger.warning(
                    f"⚠️ [REPLAY_ATTACK] Nonce already exists (replay detected): {nonce[:16]}..."
                )
                return False

        except RedisError as e:
            logger.error(f"❌ [REDIS_CLIENT] Redis operation failed: {e}")
            raise NonceTrackerError(f"Failed to check/store nonce: {e}")

    def is_nonce_used(self, nonce: str) -> bool:
        """
        Check if nonce exists in Redis (has been used before).

        This is a read-only operation. Use check_and_store_nonce() for
        atomic check-and-store.

        Args:
            nonce: Nonce to check

        Returns:
            True if nonce has been used before
            False if nonce is new

        Raises:
            NonceTrackerError: If Redis operation fails
        """
        redis_key = f"{self.key_prefix}{nonce}"

        try:
            exists = self.redis_client.exists(redis_key)
            logger.debug(f"🔍 [REDIS_CLIENT] Nonce exists check: {nonce[:16]}... = {bool(exists)}")
            return bool(exists)

        except RedisError as e:
            logger.error(f"❌ [REDIS_CLIENT] Redis operation failed: {e}")
            raise NonceTrackerError(f"Failed to check nonce: {e}")

    def delete_nonce(self, nonce: str) -> bool:
        """
        Delete nonce from Redis.

        This is rarely needed, but can be useful for testing or
        manual cleanup.

        Args:
            nonce: Nonce to delete

        Returns:
            True if nonce was deleted
            False if nonce didn't exist

        Raises:
            NonceTrackerError: If Redis operation fails
        """
        redis_key = f"{self.key_prefix}{nonce}"

        try:
            deleted_count = self.redis_client.delete(redis_key)
            logger.debug(f"🔍 [REDIS_CLIENT] Deleted nonce: {nonce[:16]}... (deleted: {deleted_count})")
            return deleted_count > 0

        except RedisError as e:
            logger.error(f"❌ [REDIS_CLIENT] Redis operation failed: {e}")
            raise NonceTrackerError(f"Failed to delete nonce: {e}")

    def get_nonce_ttl(self, nonce: str) -> Optional[int]:
        """
        Get remaining TTL for a nonce.

        Args:
            nonce: Nonce to check

        Returns:
            Remaining TTL in seconds (None if nonce doesn't exist or no TTL)

        Raises:
            NonceTrackerError: If Redis operation fails
        """
        redis_key = f"{self.key_prefix}{nonce}"

        try:
            ttl = self.redis_client.ttl(redis_key)

            # Redis returns -2 if key doesn't exist, -1 if no TTL
            if ttl == -2:
                logger.debug(f"🔍 [REDIS_CLIENT] Nonce doesn't exist: {nonce[:16]}...")
                return None
            elif ttl == -1:
                logger.warning(f"⚠️ [REDIS_CLIENT] Nonce exists but has no TTL: {nonce[:16]}...")
                return None
            else:
                logger.debug(f"🔍 [REDIS_CLIENT] Nonce TTL: {nonce[:16]}... = {ttl}s")
                return ttl

        except RedisError as e:
            logger.error(f"❌ [REDIS_CLIENT] Redis operation failed: {e}")
            raise NonceTrackerError(f"Failed to get nonce TTL: {e}")

    def clear_all_nonces(self) -> int:
        """
        Clear all nonces from Redis (for testing/cleanup).

        ⚠️ WARNING: Use with caution! This will delete ALL nonce keys.

        Returns:
            Number of nonces deleted

        Raises:
            NonceTrackerError: If Redis operation fails
        """
        try:
            # Find all keys with our prefix
            pattern = f"{self.key_prefix}*"
            keys = list(self.redis_client.scan_iter(match=pattern))

            if keys:
                deleted_count = self.redis_client.delete(*keys)
                logger.warning(
                    f"⚠️ [REDIS_CLIENT] Cleared {deleted_count} nonces from Redis"
                )
                return deleted_count
            else:
                logger.info("✅ [REDIS_CLIENT] No nonces to clear")
                return 0

        except RedisError as e:
            logger.error(f"❌ [REDIS_CLIENT] Redis operation failed: {e}")
            raise NonceTrackerError(f"Failed to clear nonces: {e}")

    def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if Redis is reachable and responding
            False if Redis is unavailable

        Examples:
            >>> tracker.health_check()
            True
        """
        try:
            self.redis_client.ping()
            logger.debug("✅ [REDIS_CLIENT] Health check passed")
            return True
        except (RedisConnectionError, RedisError) as e:
            logger.error(f"❌ [REDIS_CLIENT] Health check failed: {e}")
            return False

    def close(self):
        """
        Close Redis connection.

        Should be called when shutting down the service.
        """
        try:
            self.redis_client.close()
            logger.info("✅ [REDIS_CLIENT] Connection closed")
        except Exception as e:
            logger.warning(f"⚠️ [REDIS_CLIENT] Error closing connection: {e}")


# Global singleton instance (lazy-initialized)
_nonce_tracker: Optional[NonceTracker] = None


def get_nonce_tracker(
    project_id: str = "pgp-live",
    default_ttl: int = 300
) -> NonceTracker:
    """
    Get global NonceTracker instance (singleton pattern).

    Creates instance on first call, returns cached instance on subsequent calls.

    Args:
        project_id: GCP project ID
        default_ttl: Default TTL for nonces (seconds)

    Returns:
        NonceTracker instance

    Raises:
        NonceTrackerError: If initialization fails

    Examples:
        >>> tracker = get_nonce_tracker()
        >>> tracker.check_and_store_nonce('abc123', 300)
        True
    """
    global _nonce_tracker

    if _nonce_tracker is None:
        logger.info("🚀 [REDIS_CLIENT] Initializing global NonceTracker instance")
        _nonce_tracker = NonceTracker(
            project_id=project_id,
            default_ttl=default_ttl
        )

    return _nonce_tracker


# Export public API
__all__ = [
    'NonceTracker',
    'NonceTrackerError',
    'get_nonce_tracker'
]
