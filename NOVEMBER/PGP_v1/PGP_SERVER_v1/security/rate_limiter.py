#!/usr/bin/env python
"""
Rate limiting for Flask endpoints using token bucket algorithm.
Prevents DoS attacks on webhook endpoints.
"""
import time
import logging
from functools import wraps
from flask import request, abort
from collections import defaultdict
from threading import Lock
from typing import Dict, Tuple
from PGP_COMMON.utils import get_real_client_ip

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for Flask endpoints.

    Features:
    - Per-IP rate limiting
    - Configurable rate and burst
    - Thread-safe
    - Automatic token refill
    """

    def __init__(self, rate: int = 10, burst: int = 20):
        """
        Initialize rate limiter.

        Args:
            rate: Requests per minute
            burst: Maximum burst size
        """
        self.rate = rate  # requests per minute
        self.burst = burst  # max burst
        self.tokens_per_second = rate / 60.0

        # Storage: {ip: (tokens, last_update_time)}
        self.buckets: Dict[str, Tuple[float, float]] = defaultdict(
            lambda: (burst, time.time())
        )
        self.lock = Lock()

        logger.info("🚦 [RATE_LIMIT] Initialized: {} req/min, burst {}".format(
            rate, burst
        ))

    def _refill_tokens(self, ip: str) -> float:
        """
        Refill tokens for IP based on time elapsed.

        Args:
            ip: Client IP address

        Returns:
            Current token count
        """
        tokens, last_update = self.buckets[ip]
        now = time.time()
        elapsed = now - last_update

        # Refill tokens
        new_tokens = min(
            self.burst,
            tokens + (elapsed * self.tokens_per_second)
        )

        self.buckets[ip] = (new_tokens, now)
        return new_tokens

    def allow_request(self, ip: str) -> bool:
        """
        Check if request from IP is allowed.

        Args:
            ip: Client IP address

        Returns:
            True if allowed, False if rate limit exceeded
        """
        with self.lock:
            tokens = self._refill_tokens(ip)

            if tokens >= 1.0:
                # Consume token
                self.buckets[ip] = (tokens - 1.0, time.time())
                return True
            else:
                return False

    def limit(self, f):
        """
        Decorator to apply rate limiting to Flask route.

        Usage:
            @app.route('/webhook', methods=['POST'])
            @rate_limiter.limit
            def webhook():
                return jsonify({'status': 'ok'})

        Security Note:
            Uses get_real_client_ip() to prevent IP spoofing via X-Forwarded-For.
            Cloud Run adds 1 trusted proxy, so we use trusted_proxy_count=1.
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get real client IP (secure against spoofing)
            # Cloud Run environment has 1 trusted proxy
            client_ip = get_real_client_ip(request, trusted_proxy_count=1)

            if not self.allow_request(client_ip):
                logger.warning("⚠️ [RATE_LIMIT] Rate limit exceeded for {}".format(
                    client_ip
                ))
                abort(429, "Rate limit exceeded")

            return f(*args, **kwargs)

        return decorated_function


def init_rate_limiter(rate: int = 10, burst: int = 20) -> RateLimiter:
    """
    Factory function to initialize rate limiter.

    Args:
        rate: Requests per minute
        burst: Maximum burst size

    Returns:
        RateLimiter instance
    """
    return RateLimiter(rate, burst)
