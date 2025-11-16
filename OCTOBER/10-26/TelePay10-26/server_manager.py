#!/usr/bin/env python
"""
Flask server manager with integrated security middleware and blueprints.
Provides webhook endpoints with HMAC auth, IP whitelist, and rate limiting.
Refactored to use Flask application factory pattern with modular blueprints.
"""
import socket
import logging
from flask import Flask, request, jsonify
import asyncio

# Import security modules
from security.hmac_auth import init_hmac_auth
from security.ip_whitelist import init_ip_whitelist
from security.rate_limiter import init_rate_limiter

# Import blueprints
from api.webhooks import webhooks_bp
from api.health import health_bp

logger = logging.getLogger(__name__)


class ServerManager:
    """
    Flask server with integrated security.

    Security Features:
    - HMAC signature verification
    - IP whitelisting
    - Rate limiting
    - Security headers
    """

    def __init__(self, config: dict = None):
        """
        Initialize Flask server with security and blueprints.

        Args:
            config: Configuration dictionary with security settings
                {
                    'webhook_signing_secret': 'secret',
                    'allowed_ips': ['127.0.0.1', '10.0.0.0/8'],
                    'rate_limit_per_minute': 10,
                    'rate_limit_burst': 20
                }
        """
        self.flask_app = create_app(config)
        self.port = None
        self.notification_service = None  # Will be set by AppInitializer
        self.config = config or {}

        logger.info("🔒 [SERVER] Flask server initialized with blueprints")

    def set_notification_service_on_app(self, notification_service):
        """
        Set notification service in Flask app context.
        Used by blueprints to access notification service.
        """
        self.flask_app.config['notification_service'] = notification_service
        logger.info("📬 [SERVER] Notification service configured in app context")

    def set_notification_service(self, notification_service):
        """
        Set the notification service instance.
        Maintains backward compatibility with old code.
        """
        self.notification_service = notification_service
        self.set_notification_service_on_app(notification_service)
        logger.info("📬 [SERVER] Notification service configured")
    
    def find_free_port(self, start_port=5000, max_tries=20):
        """Find a free port for the Flask server."""
        for port in range(start_port, start_port + max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', port)) != 0:
                    return port
        raise OSError("No available port found for Flask.")
    
    def start(self):
        """Start the Flask server."""
        self.port = self.find_free_port(5000)
        logger.info(f"🔗 Running Flask on port {self.port}")
        self.flask_app.run(host="0.0.0.0", port=self.port)

    def get_app(self):
        """Get the Flask app instance."""
        return self.flask_app


def create_app(config: dict = None):
    """
    Flask application factory.
    Creates and configures Flask app with blueprints and security.

    Args:
        config: Configuration dictionary with security settings
            {
                'webhook_signing_secret': 'secret',
                'allowed_ips': ['127.0.0.1', '10.0.0.0/8'],
                'rate_limit_per_minute': 10,
                'rate_limit_burst': 20
            }

    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)

    # Store config in app context
    if config:
        app.config.update(config)

    # Initialize security components (if config provided)
    hmac_auth = None
    ip_whitelist = None
    rate_limiter = None

    if config:
        try:
            # Initialize HMAC auth
            if 'webhook_signing_secret' in config:
                hmac_auth = init_hmac_auth(config['webhook_signing_secret'])
                app.config['hmac_auth'] = hmac_auth
                logger.info("🔒 [APP_FACTORY] HMAC authentication enabled")

            # Initialize IP whitelist
            if 'allowed_ips' in config:
                ip_whitelist = init_ip_whitelist(config['allowed_ips'])
                app.config['ip_whitelist'] = ip_whitelist
                logger.info("🔒 [APP_FACTORY] IP whitelist enabled")

            # Initialize rate limiter
            rate = config.get('rate_limit_per_minute', 10)
            burst = config.get('rate_limit_burst', 20)
            rate_limiter = init_rate_limiter(rate=rate, burst=burst)
            app.config['rate_limiter'] = rate_limiter
            logger.info("🔒 [APP_FACTORY] Rate limiting enabled")

        except Exception as e:
            logger.error(f"❌ [APP_FACTORY] Error initializing security: {e}", exc_info=True)
            raise

    # Register security headers middleware
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'"
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(webhooks_bp)

    logger.info("📋 [APP_FACTORY] Blueprints registered: health, webhooks")

    # Apply security decorators to webhook blueprint endpoints
    if config and hmac_auth and ip_whitelist and rate_limiter:
        for endpoint in ['webhooks.handle_notification', 'webhooks.handle_broadcast_trigger']:
            if endpoint in app.view_functions:
                view_func = app.view_functions[endpoint]
                # Apply security stack: Rate Limit → IP Whitelist → HMAC
                view_func = rate_limiter.limit(view_func)
                view_func = ip_whitelist.require_whitelisted_ip(view_func)
                view_func = hmac_auth.require_signature(view_func)
                app.view_functions[endpoint] = view_func

        logger.info("🔒 [APP_FACTORY] Security applied to webhook endpoints")

    logger.info("✅ [APP_FACTORY] Flask app created successfully")

    return app