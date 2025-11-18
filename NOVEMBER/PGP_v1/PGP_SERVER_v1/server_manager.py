#!/usr/bin/env python
"""
Flask server manager with integrated security middleware and blueprints.
Provides webhook endpoints with HMAC auth, IP whitelist, and rate limiting.
Refactored to use Flask application factory pattern with modular blueprints.
"""
import socket
import logging
import os
from flask import Flask, request, jsonify
import asyncio

# Import security modules
from security.hmac_auth import init_hmac_auth
from security.ip_whitelist import init_ip_whitelist
from security.rate_limiter import init_rate_limiter

# Import security utilities (C-07 fix)
from PGP_COMMON.utils import sanitize_error_for_user, create_error_response

# Import Flask security extensions
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman

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
                'rate_limit_burst': 20,
                'flask_secret_key': 'secret'  # For CSRF protection
            }

    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)

    # 🔒 STEP 1: Configure Flask secret key (required for CSRF)
    # Flask secret key is required for session management and CSRF protection
    flask_secret = os.getenv('FLASK_SECRET_KEY')
    if not flask_secret:
        logger.warning("⚠️ [APP_FACTORY] FLASK_SECRET_KEY not set - using fallback")
        # Fallback: generate a random secret (NOT recommended for production)
        import secrets
        flask_secret = secrets.token_hex(32)

    app.config['SECRET_KEY'] = flask_secret

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

    # 🔒 STEP 2: Initialize CSRF Protection
    # CSRFProtect provides protection against Cross-Site Request Forgery attacks
    csrf = CSRFProtect(app)
    logger.info("🔒 [APP_FACTORY] CSRF protection enabled")

    # Exempt webhook endpoints from CSRF (they use HMAC authentication instead)
    csrf.exempt(webhooks_bp)
    logger.info("🔒 [APP_FACTORY] Webhook endpoints exempted from CSRF (using HMAC)")

    # 🔒 STEP 3: Initialize Security Headers with Talisman
    # Talisman provides comprehensive security headers including CSP, HSTS, etc.
    csp = {
        'default-src': "'self'",
        'script-src': "'self'",
        'style-src': "'self'",
        'img-src': "'self' data:",
        'font-src': "'self'",
        'connect-src': "'self'",
        'frame-ancestors': "'none'",
        'base-uri': "'self'",
        'form-action': "'self'"
    }

    Talisman(
        app,
        force_https=True,
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        strict_transport_security_include_subdomains=True,
        content_security_policy=csp,
        content_security_policy_nonce_in=['script-src'],
        referrer_policy='strict-origin-when-cross-origin',
        session_cookie_secure=True,
        session_cookie_samesite='Lax',
        x_content_type_options=True,
        x_xss_protection=True
    )
    logger.info("🔒 [APP_FACTORY] Security headers configured with Talisman")

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(webhooks_bp)

    logger.info("📋 [APP_FACTORY] Blueprints registered: health, webhooks")

    # Apply security decorators to webhook blueprint endpoints
    if config and hmac_auth and ip_whitelist and rate_limiter:
        # Endpoints that require HMAC + IP whitelist + Rate limiting
        secured_endpoints = [
            'webhooks.handle_notification',
            'webhooks.handle_broadcast_trigger'
        ]

        for endpoint in secured_endpoints:
            if endpoint in app.view_functions:
                view_func = app.view_functions[endpoint]
                # Apply security stack: Rate Limit → IP Whitelist → HMAC
                view_func = rate_limiter.limit(view_func)
                view_func = ip_whitelist.require_whitelisted_ip(view_func)
                view_func = hmac_auth.require_signature(view_func)
                app.view_functions[endpoint] = view_func

        logger.info("🔒 [APP_FACTORY] HMAC+IP+Rate security applied to internal webhooks")

    # Apply rate limiting to external webhooks (NowPayments, Telegram)
    # These endpoints have their own signature verification (IPN sig, Telegram secret token)
    if rate_limiter:
        external_webhooks = [
            'webhooks.handle_nowpayments_ipn',
            'webhooks.handle_telegram_webhook'
        ]

        for endpoint in external_webhooks:
            if endpoint in app.view_functions:
                view_func = app.view_functions[endpoint]
                # Apply only rate limiting (they have built-in signature verification)
                view_func = rate_limiter.limit(view_func)
                app.view_functions[endpoint] = view_func

        logger.info("🔒 [APP_FACTORY] Rate limiting applied to external webhooks (NowPayments, Telegram)")

    # ============================================================================
    # GLOBAL ERROR HANDLERS (C-07: Error Sanitization)
    # ============================================================================

    @app.errorhandler(Exception)
    def handle_exception(e):
        """
        Global error handler that sanitizes error messages based on environment.

        C-07 Fix: Prevents sensitive data exposure through error messages.
        - Production: Returns generic error with error ID
        - Development: Returns detailed error for debugging
        """
        # Get environment (defaults to production for safety)
        environment = os.getenv('ENVIRONMENT', 'production')

        # Sanitize error message (shows details only in development)
        sanitized_message = sanitize_error_for_user(e, environment)

        # Create standardized error response with error ID
        error_response, status_code = create_error_response(
            status_code=500,
            message=sanitized_message,
            include_error_id=True
        )

        # Log full error details internally (always, regardless of environment)
        logger.error(
            f"❌ [ERROR] Unhandled exception in PGP_SERVER_v1",
            extra={
                'error_id': error_response.get('error_id'),
                'error_type': type(e).__name__,
                'environment': environment
            },
            exc_info=True
        )

        return jsonify(error_response), status_code

    @app.errorhandler(400)
    def handle_bad_request(e):
        """Handle 400 Bad Request errors with sanitized messages."""
        error_response, _ = create_error_response(400, str(e))
        return jsonify(error_response), 400

    @app.errorhandler(404)
    def handle_not_found(e):
        """Handle 404 Not Found errors."""
        error_response, _ = create_error_response(404, "Endpoint not found")
        return jsonify(error_response), 404

    logger.info("✅ [APP_FACTORY] Global error handlers configured")

    logger.info("✅ [APP_FACTORY] Flask app created successfully with security stack:")
    logger.info("   ✅ CSRF Protection (flask-wtf)")
    logger.info("   ✅ Security Headers (flask-talisman)")
    logger.info("   ✅ HMAC Authentication (custom)")
    logger.info("   ✅ IP Whitelist (custom)")
    logger.info("   ✅ Rate Limiting (custom)")
    logger.info("   ✅ Error Sanitization (custom)")

    return app