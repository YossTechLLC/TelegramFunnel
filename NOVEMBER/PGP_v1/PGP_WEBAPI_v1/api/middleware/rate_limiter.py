#!/usr/bin/env python
"""
⏱️ Rate Limiting Middleware for PGP_WEBAPI_v1
Configures Flask-Limiter with Redis backend for production
"""
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os


def setup_rate_limiting(app: Flask) -> Limiter:
    """
    Setup rate limiting with Redis backend (production) or memory (dev)

    Args:
        app: Flask application instance

    Returns:
        Limiter instance configured with storage backend
    """
    # Determine storage backend based on environment
    redis_url = os.getenv('REDIS_URL')

    if redis_url:
        # Production: Use Redis for distributed rate limiting
        storage_uri = redis_url
        print(f"⏱️  Rate limiting using Redis: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
    else:
        # Development: Use in-memory storage
        storage_uri = "memory://"
        print("⏱️  Rate limiting using in-memory storage (dev mode)")

    # Initialize limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        storage_uri=storage_uri,
        storage_options={},
        strategy="fixed-window",
        default_limits=["600 per day", "150 per hour"],
        # Custom headers for rate limit info
        headers_enabled=True,
        # Don't swallow errors (fail-open for dev, fail-closed for prod)
        swallow_errors=not redis_url
    )

    print("✅ Rate limiting configured successfully")
    return limiter


def get_rate_limit_error_handler():
    """
    Custom error handler for rate limit exceeded

    Returns:
        Function that handles 429 errors
    """
    def rate_limit_handler(e):
        """Handle rate limit exceeded"""
        from flask import jsonify

        print(f"⚠️  Rate limit exceeded: {e.description}")

        return jsonify({
            'success': False,
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please try again later.',
            'retry_after': e.description
        }), 429

    return rate_limit_handler


# Decorator helpers for common rate limits
def rate_limit_signup():
    """Rate limit for signup endpoint (5 per 15 minutes)"""
    return "5 per 15 minutes"


def rate_limit_login():
    """Rate limit for login endpoint (10 per 15 minutes)"""
    return "10 per 15 minutes"


def rate_limit_email_operations():
    """Rate limit for email operations (3 per hour)"""
    return "3 per hour"


def rate_limit_password_reset():
    """Rate limit for password reset endpoint (5 per 15 minutes)"""
    return "5 per 15 minutes"


def rate_limit_verification():
    """Rate limit for email verification endpoint (10 per hour)"""
    return "10 per hour"
