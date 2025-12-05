# TelePay New Architecture Implementation Checklist

**Date:** 2025-11-13
**Status:** IMPLEMENTATION PLAN
**Reference:** NEW_ARCHITECTURE.md
**Goal:** Implement centralized, secure, modular architecture for TelePay10-26

---

## Overview

This checklist guides the implementation of architectural improvements identified in NEW_ARCHITECTURE.md. The focus is on:

1. **Security Hardening** - HMAC signing, IP whitelisting, rate limiting, HTTPS
2. **Modular Code Structure** - Flask blueprints, separate handler modules, clean separation of concerns
3. **Database Optimization** - Connection pooling, proper transaction management
4. **Bot Handler Organization** - Modular handlers, ConversationHandler patterns
5. **Testing & Monitoring** - Comprehensive tests, logging, health checks

---

## Phase 1: Security Hardening (CRITICAL - Week 1)

### 1.1 HMAC Request Signing & Verification

**Objective:** Secure Flask webhook endpoints with HMAC signature verification

**Files to Create:**
- [ ] `TelePay10-26/security/__init__.py`
- [ ] `TelePay10-26/security/hmac_auth.py`
- [ ] `TelePay10-26/security/ip_whitelist.py`
- [ ] `TelePay10-26/security/rate_limiter.py`

**Tasks:**

#### 1.1.1 Create HMAC Authentication Module

**File: `TelePay10-26/security/hmac_auth.py`**

```python
#!/usr/bin/env python
"""
HMAC-based request authentication for webhook endpoints.
Verifies requests from Cloud Run services using shared secret.
"""
import hmac
import hashlib
import logging
from functools import wraps
from flask import request, abort, current_app

logger = logging.getLogger(__name__)


class HMACAuth:
    """
    HMAC signature verification for webhook requests.

    Security Features:
    - SHA256 HMAC signature
    - Timing-safe comparison
    - Configurable secret per endpoint
    - Detailed logging for audit trail
    """

    def __init__(self, secret_key: str):
        """
        Initialize HMAC authenticator.

        Args:
            secret_key: Shared secret for HMAC signing (from Secret Manager)
        """
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key

    def generate_signature(self, payload: bytes) -> str:
        """
        Generate HMAC-SHA256 signature for payload.

        Args:
            payload: Request body as bytes

        Returns:
            Hex-encoded HMAC signature
        """
        signature = hmac.new(
            self.secret_key,
            payload,
            hashlib.sha256
        ).hexdigest()

        return signature

    def verify_signature(self, payload: bytes, provided_signature: str) -> bool:
        """
        Verify HMAC signature using timing-safe comparison.

        Args:
            payload: Request body as bytes
            provided_signature: Signature from X-Signature header

        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature = self.generate_signature(payload)
        return hmac.compare_digest(expected_signature, provided_signature)

    def require_signature(self, f):
        """
        Decorator to require HMAC signature on Flask route.

        Usage:
            @app.route('/webhook', methods=['POST'])
            @hmac_auth.require_signature
            def webhook():
                return jsonify({'status': 'ok'})
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get signature from header
            signature = request.headers.get('X-Signature')

            if not signature:
                logger.warning("⚠️ [HMAC] Missing X-Signature header")
                abort(401, "Missing signature header")

            # Get request payload
            payload = request.get_data()

            # Verify signature
            if not self.verify_signature(payload, signature):
                logger.error(f"❌ [HMAC] Invalid signature from {request.remote_addr}")
                abort(403, "Invalid signature")

            logger.info(f"✅ [HMAC] Valid signature from {request.remote_addr}")
            return f(*args, **kwargs)

        return decorated_function


def init_hmac_auth(secret_key: str) -> HMACAuth:
    """
    Factory function to initialize HMAC authenticator.

    Args:
        secret_key: Shared secret (fetch from Secret Manager)

    Returns:
        HMACAuth instance
    """
    return HMACAuth(secret_key)
```

**Checklist:**
- [ ] Create `security/hmac_auth.py` with HMACAuth class
- [ ] Add signature generation method
- [ ] Add signature verification with timing-safe comparison
- [ ] Create decorator for Flask routes
- [ ] Add detailed logging for audit trail
- [ ] Write unit tests for HMAC verification

#### 1.1.2 Update Cloud Run Services to Send HMAC Signatures

**File: `GCNotificationService-10-26/utils/request_signer.py` (NEW)**

```python
#!/usr/bin/env python
"""
Request signing utility for outbound requests to TelePay10-26.
"""
import hmac
import hashlib
import json
from typing import Dict, Any


class RequestSigner:
    """Signs outbound HTTP requests with HMAC-SHA256."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()

    def sign_request(self, payload: Dict[str, Any]) -> str:
        """
        Generate HMAC signature for JSON payload.

        Args:
            payload: Request body as dictionary

        Returns:
            Hex-encoded HMAC signature
        """
        # Convert to JSON string (deterministic ordering)
        json_payload = json.dumps(payload, sort_keys=True).encode()

        signature = hmac.new(
            self.secret_key,
            json_payload,
            hashlib.sha256
        ).hexdigest()

        return signature
```

**Update GCNotificationService-10-26/service.py:**
```python
# Add to send_notification route
from utils.request_signer import RequestSigner

# Initialize signer (fetch secret from Secret Manager)
signer = RequestSigner(WEBHOOK_SIGNING_SECRET)

# When forwarding to TelePay10-26:
payload = {
    'open_channel_id': data['open_channel_id'],
    'payment_type': data['payment_type'],
    'payment_data': data['payment_data']
}

signature = signer.sign_request(payload)

response = requests.post(
    f"{TELEPAY_LOCAL_URL}/send-notification",
    json=payload,
    headers={'X-Signature': signature},
    timeout=10
)
```

**Checklist:**
- [ ] Create `request_signer.py` in GCNotificationService-10-26
- [ ] Update service.py to sign requests
- [ ] Add WEBHOOK_SIGNING_SECRET to Secret Manager
- [ ] Update GCNotificationService-10-26 to fetch secret
- [ ] Test signature generation/verification end-to-end

### 1.2 IP Whitelist Implementation

**File: `TelePay10-26/security/ip_whitelist.py`**

```python
#!/usr/bin/env python
"""
IP whitelist middleware for Flask endpoints.
Restricts access to known Cloud Run egress IPs.
"""
import logging
from functools import wraps
from flask import request, abort
from ipaddress import ip_address, ip_network
from typing import List

logger = logging.getLogger(__name__)


class IPWhitelist:
    """
    IP-based access control for webhook endpoints.

    Security:
    - Checks X-Forwarded-For header (behind proxy)
    - Supports CIDR notation for IP ranges
    - Logs all access attempts
    """

    def __init__(self, allowed_ips: List[str]):
        """
        Initialize IP whitelist.

        Args:
            allowed_ips: List of allowed IPs/CIDR ranges
                Example: ['10.0.0.0/8', '35.123.45.67']
        """
        self.allowed_networks = [ip_network(ip) for ip in allowed_ips]
        logger.info(f"🔒 [IP_WHITELIST] Initialized with {len(self.allowed_networks)} networks")

    def is_allowed(self, client_ip: str) -> bool:
        """
        Check if client IP is in whitelist.

        Args:
            client_ip: Client IP address string

        Returns:
            True if allowed, False otherwise
        """
        try:
            ip = ip_address(client_ip)

            for network in self.allowed_networks:
                if ip in network:
                    return True

            return False

        except ValueError as e:
            logger.error(f"❌ [IP_WHITELIST] Invalid IP format: {client_ip} - {e}")
            return False

    def require_whitelisted_ip(self, f):
        """
        Decorator to restrict Flask route to whitelisted IPs.

        Usage:
            @app.route('/webhook', methods=['POST'])
            @ip_whitelist.require_whitelisted_ip
            def webhook():
                return jsonify({'status': 'ok'})
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP (handle proxy)
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

            # Handle multiple IPs in X-Forwarded-For (use first one)
            if ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()

            if not self.is_allowed(client_ip):
                logger.warning(f"⚠️ [IP_WHITELIST] Blocked request from {client_ip}")
                abort(403, "Unauthorized IP address")

            logger.info(f"✅ [IP_WHITELIST] Allowed request from {client_ip}")
            return f(*args, **kwargs)

        return decorated_function


def init_ip_whitelist(allowed_ips: List[str]) -> IPWhitelist:
    """
    Factory function to initialize IP whitelist.

    Args:
        allowed_ips: List of allowed IPs/CIDR ranges

    Returns:
        IPWhitelist instance
    """
    return IPWhitelist(allowed_ips)
```

**Configuration: `TelePay10-26/.env.example`**
```bash
# Add IP whitelist configuration
ALLOWED_IPS=10.0.0.0/8,35.190.247.0/24,35.191.0.0/16
```

**Checklist:**
- [ ] Create `security/ip_whitelist.py`
- [ ] Add IPWhitelist class with CIDR support
- [ ] Handle X-Forwarded-For header properly
- [ ] Add configuration for allowed IPs
- [ ] Document Cloud Run egress IP ranges
- [ ] Test with valid/invalid IPs

### 1.3 Rate Limiting

**File: `TelePay10-26/security/rate_limiter.py`**

```python
#!/usr/bin/env python
"""
Rate limiting for Flask endpoints using token bucket algorithm.
Prevents DoS attacks on webhook endpoints.
"""
import time
import logging
from functools import wraps
from flask import request, abort, current_app
from collections import defaultdict
from threading import Lock
from typing import Dict, Tuple

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

        logger.info(f"🚦 [RATE_LIMIT] Initialized: {rate} req/min, burst {burst}")

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
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

            if ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()

            if not self.allow_request(client_ip):
                logger.warning(f"⚠️ [RATE_LIMIT] Rate limit exceeded for {client_ip}")
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
```

**Checklist:**
- [ ] Create `security/rate_limiter.py`
- [ ] Implement token bucket algorithm
- [ ] Make thread-safe with locks
- [ ] Add decorator for Flask routes
- [ ] Configure rate limits per endpoint
- [ ] Test with high request volume

### 1.4 HTTPS Setup with Reverse Proxy

**Objective:** Set up Nginx/Caddy as reverse proxy with Let's Encrypt SSL

**Option A: Caddy (Recommended - Automatic HTTPS)**

**File: `TelePay10-26/Caddyfile` (NEW)**

```caddy
# Caddy configuration for TelePay10-26
# Automatic HTTPS with Let's Encrypt

# Replace with your domain
telepay.yourdomain.com {
    # Automatic HTTPS
    tls {
        email admin@yourdomain.com
    }

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Content-Security-Policy "default-src 'self'"
        X-XSS-Protection "1; mode=block"
    }

    # Reverse proxy to Flask
    reverse_proxy localhost:5000 {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    # Health check endpoint (bypass auth)
    @health {
        path /health
    }
    handle @health {
        reverse_proxy localhost:5000
    }

    # Logging
    log {
        output file /var/log/caddy/telepay.log
        format json
    }
}
```

**Installation Script: `TelePay10-26/setup_caddy.sh` (NEW)**

```bash
#!/bin/bash
# Install and configure Caddy for TelePay10-26

set -e

echo "📦 Installing Caddy..."

# Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

echo "📝 Configuring Caddy..."

# Copy Caddyfile
sudo cp Caddyfile /etc/caddy/Caddyfile

# Create log directory
sudo mkdir -p /var/log/caddy
sudo chown caddy:caddy /var/log/caddy

# Validate configuration
sudo caddy validate --config /etc/caddy/Caddyfile

echo "🚀 Starting Caddy..."

# Enable and start Caddy
sudo systemctl enable caddy
sudo systemctl restart caddy

echo "✅ Caddy installed and configured!"
echo "🔒 HTTPS will be automatically configured on first request"
```

**Option B: Nginx with Let's Encrypt**

**File: `TelePay10-26/nginx/telepay.conf` (NEW)**

```nginx
# Nginx configuration for TelePay10-26

upstream flask_backend {
    server localhost:5000;
}

server {
    listen 80;
    server_name telepay.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name telepay.yourdomain.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/telepay.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/telepay.yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Content-Security-Policy "default-src 'self'" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/telepay_access.log;
    error_log /var/log/nginx/telepay_error.log;

    # Proxy settings
    location / {
        proxy_pass http://flask_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check
    location /health {
        proxy_pass http://flask_backend;
        access_log off;
    }
}
```

**Checklist:**
- [ ] Choose reverse proxy (Caddy or Nginx)
- [ ] Create configuration file
- [ ] Install reverse proxy on VM
- [ ] Configure domain name (DNS A record)
- [ ] Set up Let's Encrypt SSL certificate
- [ ] Test HTTPS connection
- [ ] Verify security headers
- [ ] Update Cloud Run services with HTTPS URL

### 1.5 Update Flask Server with Security Middleware

**File: `TelePay10-26/server_manager.py` (REFACTOR)**

```python
#!/usr/bin/env python
"""
Flask server manager with security middleware.
Refactored to use modular security components.
"""
import socket
import logging
from flask import Flask, request, jsonify
import asyncio

# Import security modules
from security.hmac_auth import init_hmac_auth
from security.ip_whitelist import init_ip_whitelist
from security.rate_limiter import init_rate_limiter

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

    def __init__(self, config: dict):
        """
        Initialize Flask server with security.

        Args:
            config: Configuration dictionary with security settings
        """
        self.flask_app = Flask(__name__)
        self.port = None
        self.notification_service = None
        self.config = config

        # Initialize security components
        self.hmac_auth = init_hmac_auth(config['webhook_signing_secret'])
        self.ip_whitelist = init_ip_whitelist(config['allowed_ips'])
        self.rate_limiter = init_rate_limiter(
            rate=config.get('rate_limit_per_minute', 10),
            burst=config.get('rate_limit_burst', 20)
        )

        # Register security middleware
        self._register_security_middleware()

        # Register routes
        self._register_routes()

        logger.info("🔒 [SERVER] Flask server initialized with security")

    def _register_security_middleware(self):
        """Register security headers and middleware."""

        @self.flask_app.after_request
        def add_security_headers(response):
            """Add security headers to all responses."""
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Content-Security-Policy'] = "default-src 'self'"
            response.headers['X-XSS-Protection'] = '1; mode=block'
            return response

    def _register_routes(self):
        """Register Flask routes with security decorators."""

        @self.flask_app.route('/send-notification', methods=['POST'])
        @self.rate_limiter.limit
        @self.ip_whitelist.require_whitelisted_ip
        @self.hmac_auth.require_signature
        def handle_notification_request():
            """
            Handle notification request from Cloud Run services.

            Security:
            - Rate limited (10 req/min)
            - IP whitelisted (Cloud Run only)
            - HMAC signature required
            """
            try:
                data = request.get_json()

                logger.info(f"📬 [NOTIFICATION] Received request: {data.keys()}")

                # Validate required fields
                required_fields = ['open_channel_id', 'payment_type', 'payment_data']
                for field in required_fields:
                    if field not in data:
                        return jsonify({'error': f'Missing field: {field}'}), 400

                # Check if notification service is initialized
                if not self.notification_service:
                    logger.warning("⚠️ [NOTIFICATION] Service not initialized")
                    return jsonify({'error': 'Notification service not available'}), 503

                # Send notification asynchronously
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                success = loop.run_until_complete(
                    self.notification_service.send_payment_notification(
                        open_channel_id=data['open_channel_id'],
                        payment_type=data['payment_type'],
                        payment_data=data['payment_data']
                    )
                )

                loop.close()

                if success:
                    return jsonify({'status': 'success', 'message': 'Notification sent'}), 200
                else:
                    return jsonify({'status': 'failed', 'message': 'Notification not sent'}), 200

            except Exception as e:
                logger.error(f"❌ [NOTIFICATION] Error: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint (no auth required)."""
            return jsonify({
                'status': 'healthy',
                'notification_service': 'initialized' if self.notification_service else 'not_initialized',
                'security': {
                    'hmac': 'enabled',
                    'ip_whitelist': 'enabled',
                    'rate_limiting': 'enabled'
                }
            }), 200

    def set_notification_service(self, notification_service):
        """Set the notification service instance."""
        self.notification_service = notification_service
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
```

**Checklist:**
- [ ] Refactor `server_manager.py` to use security modules
- [ ] Add HMAC verification to `/send-notification`
- [ ] Add IP whitelist to `/send-notification`
- [ ] Add rate limiting to `/send-notification`
- [ ] Add security headers middleware
- [ ] Update health check with security status
- [ ] Test all security layers end-to-end

---

## Phase 2: Modular Code Structure (Week 2)

### 2.1 Flask Blueprints for API Organization

**Objective:** Organize Flask endpoints using Blueprint pattern for better modularity

**New Directory Structure:**
```
TelePay10-26/
├── api/
│   ├── __init__.py
│   ├── webhooks.py       # Webhook endpoints blueprint
│   ├── health.py          # Health/monitoring blueprint
│   └── admin.py           # Admin endpoints blueprint (future)
├── security/
│   ├── __init__.py
│   ├── hmac_auth.py       # ✅ Created in Phase 1
│   ├── ip_whitelist.py    # ✅ Created in Phase 1
│   └── rate_limiter.py    # ✅ Created in Phase 1
├── bot/
│   ├── __init__.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── command_handler.py
│   │   ├── subscription_handler.py
│   │   ├── donation_handler.py
│   │   └── callback_handler.py
│   ├── conversations/
│   │   ├── __init__.py
│   │   ├── donation_conversation.py
│   │   └── subscription_conversation.py
│   └── utils/
│       ├── __init__.py
│       ├── keyboards.py
│       └── formatters.py
├── services/
│   ├── __init__.py
│   ├── payment_service.py
│   ├── notification_service.py
│   ├── broadcast_service.py
│   └── subscription_service.py
├── models/
│   ├── __init__.py
│   ├── database.py        # Refactored database manager
│   └── connection_pool.py # NEW - Connection pooling
├── config/
│   ├── __init__.py
│   ├── config_manager.py
│   └── secrets_manager.py
└── server_manager.py      # ✅ Updated in Phase 1
```

#### 2.1.1 Create Webhooks Blueprint

**File: `TelePay10-26/api/__init__.py`**

```python
#!/usr/bin/env python
"""
API blueprints package.
Organizes Flask endpoints into modular blueprints.
"""
from flask import Blueprint

# Import blueprints
from .webhooks import webhooks_bp
from .health import health_bp

# Export blueprints
__all__ = ['webhooks_bp', 'health_bp']
```

**File: `TelePay10-26/api/webhooks.py`**

```python
#!/usr/bin/env python
"""
Webhooks blueprint for external service integrations.
Handles incoming webhooks from Cloud Run services.
"""
import asyncio
import logging
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)

# Create blueprint
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')


@webhooks_bp.route('/notification', methods=['POST'])
def handle_notification():
    """
    Handle notification webhook from GCNotificationService.

    Security: Applied by server_manager middleware
    - HMAC signature verification
    - IP whitelist
    - Rate limiting

    Request Body:
    {
        "open_channel_id": "-1003268562225",
        "payment_type": "subscription",
        "payment_data": {...}
    }
    """
    try:
        data = request.get_json()

        logger.info(f"📬 [WEBHOOK] Notification received for channel {data.get('open_channel_id')}")

        # Validate required fields
        required_fields = ['open_channel_id', 'payment_type', 'payment_data']
        for field in required_fields:
            if field not in data:
                logger.warning(f"⚠️ [WEBHOOK] Missing field: {field}")
                return jsonify({'error': f'Missing field: {field}'}), 400

        # Get notification service from app context
        notification_service = current_app.config.get('notification_service')

        if not notification_service:
            logger.error("❌ [WEBHOOK] Notification service not initialized")
            return jsonify({'error': 'Notification service not available'}), 503

        # Send notification asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        success = loop.run_until_complete(
            notification_service.send_payment_notification(
                open_channel_id=data['open_channel_id'],
                payment_type=data['payment_type'],
                payment_data=data['payment_data']
            )
        )

        loop.close()

        if success:
            logger.info(f"✅ [WEBHOOK] Notification sent successfully")
            return jsonify({
                'status': 'success',
                'message': 'Notification sent'
            }), 200
        else:
            logger.warning(f"⚠️ [WEBHOOK] Notification failed")
            return jsonify({
                'status': 'failed',
                'message': 'Notification not sent'
            }), 200

    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/broadcast-trigger', methods=['POST'])
def handle_broadcast_trigger():
    """
    Handle broadcast trigger from GCBroadcastService (future).

    This endpoint can be used to trigger broadcast actions
    directly on the bot instance.
    """
    # Future implementation
    return jsonify({'status': 'not_implemented'}), 501
```

**File: `TelePay10-26/api/health.py`**

```python
#!/usr/bin/env python
"""
Health and monitoring blueprint.
Provides health check and status endpoints.
"""
import logging
from flask import Blueprint, jsonify, current_app

logger = logging.getLogger(__name__)

# Create blueprint
health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.

    Returns service health status and component availability.
    """
    try:
        # Check notification service
        notification_service = current_app.config.get('notification_service')
        notification_status = 'initialized' if notification_service else 'not_initialized'

        # Check database (future - add connection check)
        # db_manager = current_app.config.get('database_manager')
        # db_status = 'connected' if db_manager.is_connected() else 'disconnected'

        return jsonify({
            'status': 'healthy',
            'components': {
                'notification_service': notification_status,
                # 'database': db_status,
                'bot': 'running'  # Future - check bot status
            },
            'security': {
                'hmac': 'enabled',
                'ip_whitelist': 'enabled',
                'rate_limiting': 'enabled',
                'https': 'enabled' if request.is_secure else 'disabled'
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ [HEALTH] Error: {e}", exc_info=True)
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@health_bp.route('/status', methods=['GET'])
def status():
    """
    Detailed status endpoint with metrics.

    Future: Add metrics like request count, error rate, etc.
    """
    return jsonify({
        'status': 'ok',
        'metrics': {
            'uptime': 'TODO',
            'requests_total': 'TODO',
            'errors_total': 'TODO'
        }
    }), 200
```

**Checklist:**
- [ ] Create `api/` directory structure
- [ ] Create `webhooks.py` blueprint
- [ ] Create `health.py` blueprint
- [ ] Move notification endpoint to blueprint
- [ ] Update `server_manager.py` to register blueprints
- [ ] Test blueprint routing

#### 2.1.2 Update Server Manager to Use Blueprints

**File: `TelePay10-26/server_manager.py` (UPDATE)**

```python
def create_app(config: dict):
    """
    Application factory for Flask server.

    Args:
        config: Configuration dictionary

    Returns:
        Flask application instance
    """
    app = Flask(__name__)

    # Store config in app context
    app.config.update(config)

    # Initialize security components
    hmac_auth = init_hmac_auth(config['webhook_signing_secret'])
    ip_whitelist = init_ip_whitelist(config['allowed_ips'])
    rate_limiter = init_rate_limiter(
        rate=config.get('rate_limit_per_minute', 10),
        burst=config.get('rate_limit_burst', 20)
    )

    # Store security in app context
    app.config['hmac_auth'] = hmac_auth
    app.config['ip_whitelist'] = ip_whitelist
    app.config['rate_limiter'] = rate_limiter

    # Register security middleware
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'"
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # Apply security to webhooks blueprint
    from api.webhooks import webhooks_bp
    from api.health import health_bp

    # Add security decorators to webhooks
    for rule in webhooks_bp.url_map.iter_rules():
        if rule.endpoint.startswith('webhooks.'):
            view_func = app.view_functions[rule.endpoint]
            view_func = rate_limiter.limit(view_func)
            view_func = ip_whitelist.require_whitelisted_ip(view_func)
            view_func = hmac_auth.require_signature(view_func)
            app.view_functions[rule.endpoint] = view_func

    # Register blueprints
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(health_bp)

    logger.info("🔒 [SERVER] Flask app created with blueprints")

    return app
```

**Checklist:**
- [ ] Create `create_app()` factory function
- [ ] Register blueprints
- [ ] Apply security middleware to webhooks
- [ ] Test blueprint registration
- [ ] Update `telepay10-26.py` to use factory

### 2.2 Database Connection Pooling

**Objective:** Implement connection pooling for Cloud SQL to improve performance and reliability

**File: `TelePay10-26/models/connection_pool.py` (NEW)**

```python
#!/usr/bin/env python
"""
Database connection pooling for Cloud SQL.
Uses SQLAlchemy with Cloud SQL Connector.
"""
import logging
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import create_engine, pool, text
from sqlalchemy.orm import sessionmaker
from typing import Optional

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    Connection pool manager for Cloud SQL PostgreSQL.

    Features:
    - Cloud SQL Connector integration
    - SQLAlchemy engine with QueuePool
    - Automatic connection recycling
    - Connection health checks
    """

    def __init__(self, config: dict):
        """
        Initialize connection pool.

        Args:
            config: Database configuration
                {
                    'instance_connection_name': 'project:region:instance',
                    'database': 'database_name',
                    'user': 'username',
                    'password': 'password',
                    'pool_size': 5,
                    'max_overflow': 10,
                    'pool_timeout': 30,
                    'pool_recycle': 1800
                }
        """
        self.config = config
        self.connector = None
        self.engine = None
        self.SessionLocal = None

        self._initialize_pool()

    def _get_conn(self):
        """
        Get database connection using Cloud SQL Connector.

        Returns:
            Database connection object
        """
        conn = self.connector.connect(
            self.config['instance_connection_name'],
            "pg8000",
            user=self.config['user'],
            password=self.config['password'],
            db=self.config['database']
        )
        return conn

    def _initialize_pool(self):
        """Initialize SQLAlchemy engine with connection pool."""
        try:
            # Initialize Cloud SQL connector
            self.connector = Connector()

            # Create SQLAlchemy engine with connection pool
            self.engine = create_engine(
                "postgresql+pg8000://",
                creator=self._get_conn,
                poolclass=pool.QueuePool,
                pool_size=self.config.get('pool_size', 5),
                max_overflow=self.config.get('max_overflow', 10),
                pool_timeout=self.config.get('pool_timeout', 30),
                pool_recycle=self.config.get('pool_recycle', 1800),  # 30 minutes
                pool_pre_ping=True,  # Health check before using connection
                echo=False  # Set to True for SQL query logging
            )

            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            logger.info("✅ [DB_POOL] Connection pool initialized")
            logger.info(f"   Pool size: {self.config.get('pool_size', 5)}")
            logger.info(f"   Max overflow: {self.config.get('max_overflow', 10)}")

        except Exception as e:
            logger.error(f"❌ [DB_POOL] Failed to initialize pool: {e}", exc_info=True)
            raise

    def get_session(self):
        """
        Get database session from pool.

        Usage:
            with connection_pool.get_session() as session:
                result = session.execute(text("SELECT * FROM users"))

        Returns:
            SQLAlchemy session
        """
        return self.SessionLocal()

    def execute_query(self, query: str, params: Optional[dict] = None):
        """
        Execute raw SQL query with connection from pool.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            Query result
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result

    def health_check(self) -> bool:
        """
        Check database connection health.

        Returns:
            True if healthy, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ [DB_POOL] Health check passed")
            return True
        except Exception as e:
            logger.error(f"❌ [DB_POOL] Health check failed: {e}")
            return False

    def close(self):
        """Close connection pool and connector."""
        try:
            if self.engine:
                self.engine.dispose()
                logger.info("✅ [DB_POOL] Engine disposed")

            if self.connector:
                self.connector.close()
                logger.info("✅ [DB_POOL] Connector closed")

        except Exception as e:
            logger.error(f"❌ [DB_POOL] Error closing pool: {e}", exc_info=True)


def init_connection_pool(config: dict) -> ConnectionPool:
    """
    Factory function to initialize connection pool.

    Args:
        config: Database configuration

    Returns:
        ConnectionPool instance
    """
    return ConnectionPool(config)
```

**File: `TelePay10-26/models/database.py` (REFACTOR)**

```python
#!/usr/bin/env python
"""
Database manager refactored to use connection pooling.
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from .connection_pool import ConnectionPool
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database manager with connection pooling.

    Refactored to use ConnectionPool for better performance.
    """

    def __init__(self, connection_pool: ConnectionPool):
        """
        Initialize database manager.

        Args:
            connection_pool: ConnectionPool instance
        """
        self.pool = connection_pool
        logger.info("✅ [DB_MANAGER] Initialized with connection pool")

    def fetch_open_channel_list(self) -> Tuple[List[str], Dict[str, Dict]]:
        """
        Fetch list of open channels and their metadata.

        Returns:
            Tuple of (channel_ids, channel_info_map)
        """
        query = """
            SELECT
                open_channel_id,
                closed_channel_title,
                closed_channel_description,
                subscription_price
            FROM client
            WHERE open_channel_id IS NOT NULL
        """

        try:
            result = self.pool.execute_query(query)

            channel_ids = []
            channel_info_map = {}

            for row in result:
                channel_id = str(row[0])
                channel_ids.append(channel_id)
                channel_info_map[channel_id] = {
                    'closed_channel_title': row[1],
                    'closed_channel_description': row[2],
                    'subscription_price': float(row[3]) if row[3] else 0.0
                }

            logger.info(f"✅ [DB] Fetched {len(channel_ids)} channels")
            return channel_ids, channel_info_map

        except Exception as e:
            logger.error(f"❌ [DB] Error fetching channels: {e}", exc_info=True)
            return [], {}

    def get_channel_details_by_open_id(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get channel details by open channel ID.

        Args:
            open_channel_id: Open channel ID

        Returns:
            Dictionary with channel details or None
        """
        query = """
            SELECT
                closed_channel_title,
                closed_channel_description,
                subscription_price
            FROM client
            WHERE open_channel_id = :channel_id
        """

        try:
            result = self.pool.execute_query(query, {'channel_id': open_channel_id})
            row = result.fetchone()

            if row:
                return {
                    'closed_channel_title': row[0],
                    'closed_channel_description': row[1],
                    'subscription_price': float(row[2]) if row[2] else 0.0
                }

            logger.warning(f"⚠️ [DB] Channel not found: {open_channel_id}")
            return None

        except Exception as e:
            logger.error(f"❌ [DB] Error fetching channel details: {e}", exc_info=True)
            return None

    # Add more methods as needed...
```

**Checklist:**
- [ ] Create `models/connection_pool.py`
- [ ] Install dependencies: `sqlalchemy`, `pg8000`, `cloud-sql-python-connector`
- [ ] Refactor `database.py` to use ConnectionPool
- [ ] Update all database queries to use connection pool
- [ ] Add health check method
- [ ] Configure pool parameters in `.env`
- [ ] Test connection pooling under load

### 2.3 Modular Bot Handlers

**Objective:** Organize bot handlers using modular pattern and ConversationHandler

**Directory Structure:**
```
TelePay10-26/bot/
├── __init__.py
├── handlers/
│   ├── __init__.py
│   ├── command_handler.py      # /start, /help commands
│   ├── subscription_handler.py # Subscription flow
│   ├── donation_handler.py     # Donation flow
│   └── callback_handler.py     # Callback query routing
├── conversations/
│   ├── __init__.py
│   ├── donation_conversation.py # Donation ConversationHandler
│   └── subscription_conversation.py # Subscription ConversationHandler
└── utils/
    ├── __init__.py
    ├── keyboards.py            # Keyboard builders
    └── formatters.py           # Message formatters
```

**File: `TelePay10-26/bot/handlers/command_handler.py` (NEW)**

```python
#!/usr/bin/env python
"""
Command handlers for basic bot commands.
/start, /help, etc.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.

    Shows welcome message and channel list.
    """
    user = update.effective_user
    logger.info(f"📱 [BOT] /start command from user {user.id}")

    # Get database manager from context
    db_manager = context.application.bot_data.get('database_manager')

    if not db_manager:
        await update.message.reply_text("❌ Service temporarily unavailable")
        return

    # Fetch channel list
    channel_ids, channel_info = db_manager.fetch_open_channel_list()

    if not channel_ids:
        await update.message.reply_text(
            "👋 Welcome! No channels available at the moment."
        )
        return

    # Build channel list message
    message = "👋 <b>Welcome to TelePay Bot!</b>\n\n"
    message += "Select a channel to subscribe:\n\n"

    for channel_id in channel_ids[:10]:  # Limit to 10
        info = channel_info.get(channel_id, {})
        title = info.get('closed_channel_title', 'Channel')
        price = info.get('subscription_price', 0.0)
        message += f"• {title} - ${price:.2f}/month\n"

    await update.message.reply_text(message, parse_mode='HTML')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = """
<b>TelePay Bot Commands:</b>

/start - Show available channels
/help - Show this help message

<b>How to subscribe:</b>
1. Click /start to see channels
2. Select a channel
3. Choose subscription tier
4. Complete payment

<b>Donations:</b>
Click the 💝 Donate button in any channel to make a one-time donation.
"""
    await update.message.reply_text(help_text, parse_mode='HTML')


def register_command_handlers(application):
    """
    Register command handlers with application.

    Args:
        application: telegram.ext.Application instance
    """
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))

    logger.info("✅ [BOT] Command handlers registered")
```

**File: `TelePay10-26/bot/conversations/donation_conversation.py` (NEW)**

```python
#!/usr/bin/env python
"""
Donation conversation handler using ConversationHandler.
Multi-step conversation for donation flow.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

logger = logging.getLogger(__name__)

# Conversation states
AMOUNT_INPUT, CONFIRM_PAYMENT = range(2)


async def start_donation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start donation conversation.

    User clicked "Donate" button in channel.
    """
    query = update.callback_query
    await query.answer()

    # Parse channel ID from callback data
    # Format: donate_start_{open_channel_id}
    callback_parts = query.data.split('_')
    if len(callback_parts) != 3:
        await query.edit_message_text("❌ Invalid donation link")
        return ConversationHandler.END

    open_channel_id = callback_parts[2]

    # Store channel context
    context.user_data['donation_channel_id'] = open_channel_id

    # Show numeric keypad
    from bot.utils.keyboards import create_donation_keypad

    keypad_message = await context.bot.send_message(
        chat_id=query.message.chat.id,
        text="<b>💝 Enter Donation Amount</b>\n\n"
             "Use the keypad below to enter your donation amount in USD.\n"
             "Range: $4.99 - $9999.99",
        parse_mode="HTML",
        reply_markup=create_donation_keypad("0")
    )

    # Store message ID for later deletion
    context.user_data['keypad_message_id'] = keypad_message.message_id

    logger.info(f"💝 [DONATION] Started conversation for user {update.effective_user.id}")

    return AMOUNT_INPUT


async def handle_keypad_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle keypad button presses.

    Updates the displayed amount as user inputs.
    """
    query = update.callback_query
    callback_data = query.data

    # Get current amount
    current_amount = context.user_data.get('donation_amount_building', '0')

    # Route to appropriate handler based on callback
    if callback_data.startswith('donate_digit_'):
        # Handle digit press
        digit = callback_data.split('_')[2]
        # ... digit logic here

    elif callback_data == 'donate_confirm':
        # User confirmed amount
        return await confirm_donation(update, context)

    elif callback_data == 'donate_cancel':
        # User cancelled
        await query.edit_message_text("❌ Donation cancelled")
        context.user_data.clear()
        return ConversationHandler.END

    # Update keypad display
    from bot.utils.keyboards import create_donation_keypad
    await query.edit_message_reply_markup(
        reply_markup=create_donation_keypad(current_amount)
    )

    return AMOUNT_INPUT


async def confirm_donation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Confirm donation and trigger payment gateway.
    """
    query = update.callback_query

    # Validate amount
    current_amount = context.user_data.get('donation_amount_building', '0')

    try:
        amount_float = float(current_amount)
    except ValueError:
        await query.answer("❌ Invalid amount", show_alert=True)
        return AMOUNT_INPUT

    if amount_float < 4.99:
        await query.answer("⚠️ Minimum donation: $4.99", show_alert=True)
        return AMOUNT_INPUT

    # Store final amount
    context.user_data['donation_amount'] = amount_float

    # Delete keypad message
    keypad_message_id = context.user_data.get('keypad_message_id')
    if keypad_message_id:
        await context.bot.delete_message(
            chat_id=query.message.chat.id,
            message_id=keypad_message_id
        )

    # Send confirmation
    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=f"✅ <b>Donation Confirmed</b>\n"
             f"💰 Amount: <b>${amount_float:.2f}</b>\n"
             f"Preparing your payment gateway...",
        parse_mode="HTML"
    )

    # Trigger payment gateway
    # (Call payment service here)

    logger.info(f"✅ [DONATION] Confirmed ${amount_float:.2f} from user {update.effective_user.id}")

    return ConversationHandler.END


async def timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle conversation timeout."""
    user_id = update.effective_user.id if update.effective_user else 'Unknown'
    logger.warning(f"⚠️ [DONATION] Conversation timeout for user {user_id}")

    # Clean up keypad message
    keypad_message_id = context.user_data.get('keypad_message_id')
    chat_id = context.user_data.get('chat_id')

    if keypad_message_id and chat_id:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=keypad_message_id
            )
        except Exception:
            pass

    context.user_data.clear()
    return ConversationHandler.END


def create_donation_conversation_handler() -> ConversationHandler:
    """
    Create and return ConversationHandler for donations.

    Returns:
        ConversationHandler instance
    """
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_donation, pattern=r'^donate_start_')
        ],
        states={
            AMOUNT_INPUT: [
                CallbackQueryHandler(handle_keypad_input, pattern=r'^donate_')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern=r'^donate_cancel$')
        ],
        conversation_timeout=300,  # 5 minutes
        name='donation_conversation',
        persistent=False  # Set to True with persistence later
    )
```

**Checklist:**
- [ ] Create `bot/handlers/` directory
- [ ] Create `command_handler.py`
- [ ] Create `bot/conversations/` directory
- [ ] Create `donation_conversation.py` with ConversationHandler
- [ ] Create `subscription_conversation.py` with ConversationHandler
- [ ] Create `bot/utils/keyboards.py` for keyboard builders
- [ ] Update `bot_manager.py` to register modular handlers
- [ ] Test conversation flows

---

## Phase 3: Services Layer (Week 3)

### 3.1 Payment Service Module

**File: `TelePay10-26/services/payment_service.py` (NEW)**

```python
#!/usr/bin/env python
"""
Payment service for NowPayments integration.
Handles invoice creation, payment tracking.
"""
import logging
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Payment gateway service for NowPayments.

    Features:
    - Invoice creation
    - Payment tracking
    - IPN callback URL generation
    - Order ID management
    """

    def __init__(self, api_key: str, ipn_callback_url: Optional[str] = None):
        """
        Initialize payment service.

        Args:
            api_key: NowPayments API key
            ipn_callback_url: IPN callback URL for payment notifications
        """
        self.api_key = api_key
        self.ipn_callback_url = ipn_callback_url
        self.api_url = "https://api.nowpayments.io/v1/invoice"

    async def create_invoice(
        self,
        user_id: int,
        amount: float,
        success_url: str,
        order_id: str,
        description: str = "Payment"
    ) -> Dict[str, Any]:
        """
        Create payment invoice with NowPayments.

        Args:
            user_id: Telegram user ID
            amount: Payment amount in USD
            success_url: Success redirect URL
            order_id: Unique order identifier
            description: Payment description

        Returns:
            {
                'success': True/False,
                'invoice_id': '...',
                'invoice_url': 'https://...',
                'error': '...'  # if failed
            }
        """
        payload = {
            'price_amount': amount,
            'price_currency': 'USD',
            'order_id': order_id,
            'order_description': description,
            'success_url': success_url,
            'ipn_callback_url': self.ipn_callback_url,
            'is_fixed_rate': False,
            'is_fee_paid_by_user': False
        }

        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    invoice_id = data.get('id')
                    invoice_url = data.get('invoice_url')

                    logger.info(f"✅ [PAYMENT] Invoice created: {invoice_id}")

                    return {
                        'success': True,
                        'invoice_id': invoice_id,
                        'invoice_url': invoice_url,
                        'data': data
                    }
                else:
                    logger.error(f"❌ [PAYMENT] Invoice creation failed: {response.status_code} - {response.text}")
                    return {
                        'success': False,
                        'error': response.text,
                        'status_code': response.status_code
                    }

        except Exception as e:
            logger.error(f"❌ [PAYMENT] Exception creating invoice: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def generate_order_id(self, user_id: int, channel_id: str) -> str:
        """
        Generate unique order ID.

        Format: PGP-{user_id}|{channel_id}

        Args:
            user_id: Telegram user ID
            channel_id: Channel ID (open_channel_id)

        Returns:
            Order ID string
        """
        return f"PGP-{user_id}|{channel_id}"
```

**Checklist:**
- [ ] Create `services/` directory
- [ ] Create `payment_service.py`
- [ ] Extract payment logic from `start_np_gateway.py`
- [ ] Add comprehensive error handling
- [ ] Add payment status tracking methods
- [ ] Create unit tests for payment service

### 3.2 Notification Service Module

**File: `TelePay10-26/services/notification_service.py` (REFACTOR)**

Extract notification logic from `notification_service.py` into service module with clean interface.

**Checklist:**
- [ ] Move to `services/notification_service.py`
- [ ] Create clean interface for sending notifications
- [ ] Add support for different notification types
- [ ] Add template system for messages
- [ ] Create unit tests

---

## Phase 4: Testing & Monitoring (Week 4)

### 4.1 Unit Tests

**Directory Structure:**
```
TelePay10-26/tests/
├── __init__.py
├── test_security/
│   ├── test_hmac_auth.py
│   ├── test_ip_whitelist.py
│   └── test_rate_limiter.py
├── test_services/
│   ├── test_payment_service.py
│   └── test_notification_service.py
├── test_bot/
│   ├── test_handlers.py
│   └── test_conversations.py
└── conftest.py
```

**File: `TelePay10-26/tests/test_security/test_hmac_auth.py` (NEW)**

```python
#!/usr/bin/env python
"""Unit tests for HMAC authentication."""
import pytest
from security.hmac_auth import HMACAuth


def test_signature_generation():
    """Test HMAC signature generation."""
    hmac_auth = HMACAuth("test_secret_key")
    payload = b'{"test": "data"}'

    signature = hmac_auth.generate_signature(payload)

    assert isinstance(signature, str)
    assert len(signature) == 64  # SHA256 hex = 64 chars


def test_signature_verification_valid():
    """Test signature verification with valid signature."""
    hmac_auth = HMACAuth("test_secret_key")
    payload = b'{"test": "data"}'

    signature = hmac_auth.generate_signature(payload)
    is_valid = hmac_auth.verify_signature(payload, signature)

    assert is_valid is True


def test_signature_verification_invalid():
    """Test signature verification with invalid signature."""
    hmac_auth = HMACAuth("test_secret_key")
    payload = b'{"test": "data"}'

    invalid_signature = "invalid_signature"
    is_valid = hmac_auth.verify_signature(payload, invalid_signature)

    assert is_valid is False


def test_signature_verification_timing_safe():
    """Test that signature verification uses timing-safe comparison."""
    hmac_auth = HMACAuth("test_secret_key")
    payload = b'{"test": "data"}'

    signature = hmac_auth.generate_signature(payload)

    # Modify one character
    tampered_signature = signature[:-1] + ('0' if signature[-1] != '0' else '1')

    is_valid = hmac_auth.verify_signature(payload, tampered_signature)

    assert is_valid is False
```

**Checklist:**
- [ ] Create `tests/` directory structure
- [ ] Write tests for HMAC authentication
- [ ] Write tests for IP whitelist
- [ ] Write tests for rate limiter
- [ ] Write tests for payment service
- [ ] Write tests for bot handlers
- [ ] Set up pytest configuration
- [ ] Run tests with coverage report

### 4.2 Integration Tests

**File: `TelePay10-26/tests/test_integration/test_webhook_flow.py` (NEW)**

```python
#!/usr/bin/env python
"""Integration tests for webhook flow."""
import pytest
from flask import Flask
from server_manager import create_app


@pytest.fixture
def client():
    """Create test client for Flask app."""
    config = {
        'webhook_signing_secret': 'test_secret',
        'allowed_ips': ['127.0.0.1'],
        'rate_limit_per_minute': 100,
        'rate_limit_burst': 200
    }

    app = create_app(config)
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client


def test_webhook_with_valid_signature(client):
    """Test webhook endpoint with valid HMAC signature."""
    # Test implementation
    pass


def test_webhook_without_signature(client):
    """Test webhook endpoint rejects requests without signature."""
    # Test implementation
    pass


def test_webhook_rate_limiting(client):
    """Test rate limiting on webhook endpoint."""
    # Test implementation
    pass
```

**Checklist:**
- [ ] Create integration tests for webhook flow
- [ ] Create integration tests for payment flow
- [ ] Create integration tests for notification flow
- [ ] Test end-to-end with mock Cloud Run services
- [ ] Test database connection pooling under load

### 4.3 Logging & Monitoring

**File: `TelePay10-26/utils/logger.py` (NEW)**

```python
#!/usr/bin/env python
"""
Centralized logging configuration with correlation IDs.
"""
import logging
import uuid
from flask import g, request


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record):
        correlation_id = getattr(g, 'correlation_id', None)
        record.correlation_id = correlation_id or 'N/A'
        return True


def init_logging(level=logging.INFO):
    """
    Initialize logging with correlation IDs.

    Args:
        level: Logging level
    """
    # Create formatter with correlation ID
    formatter = logging.Formatter(
        '[%(correlation_id)s] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Configure root logger
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())

    logging.basicConfig(level=level, handlers=[handler])


def generate_correlation_id():
    """Generate unique correlation ID for request."""
    return str(uuid.uuid4())


def before_request():
    """Flask before_request hook to add correlation ID."""
    g.correlation_id = request.headers.get('X-Correlation-ID', generate_correlation_id())
```

**Checklist:**
- [ ] Create centralized logging configuration
- [ ] Add correlation IDs to all log messages
- [ ] Set up structured logging (JSON format)
- [ ] Configure log levels per module
- [ ] Set up log rotation
- [ ] Integrate with Google Cloud Logging

---

## Phase 5: Deployment & Infrastructure (Week 5)

### 5.1 systemd Service Configuration

**File: `TelePay10-26/telepay.service` (NEW)**

```ini
[Unit]
Description=TelePay10-26 Telegram Bot
After=network.target

[Service]
Type=simple
User=telepay
Group=telepay
WorkingDirectory=/opt/telepay/TelePay10-26
Environment="PATH=/opt/telepay/TelePay10-26/venv/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/telepay/TelePay10-26/venv/bin/python telepay10-26.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/telepay

[Install]
WantedBy=multi-user.target
```

**Installation Script: `TelePay10-26/install_service.sh` (NEW)**

```bash
#!/bin/bash
# Install TelePay as systemd service

set -e

echo "🔧 Installing TelePay systemd service..."

# Create telepay user
sudo useradd -r -s /bin/false telepay || true

# Set up directories
sudo mkdir -p /opt/telepay
sudo cp -r . /opt/telepay/TelePay10-26
sudo chown -R telepay:telepay /opt/telepay

# Set up Python virtual environment
cd /opt/telepay/TelePay10-26
sudo -u telepay python3 -m venv venv
sudo -u telepay venv/bin/pip install -r requirements.txt

# Install systemd service
sudo cp telepay.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telepay.service

echo "✅ Service installed!"
echo "Start with: sudo systemctl start telepay"
echo "Check status: sudo systemctl status telepay"
echo "View logs: sudo journalctl -u telepay -f"
```

**Checklist:**
- [ ] Create systemd service file
- [ ] Create installation script
- [ ] Test service start/stop/restart
- [ ] Configure auto-restart on failure
- [ ] Set up log rotation for systemd journal
- [ ] Document service management commands

### 5.2 Environment Configuration

**File: `TelePay10-26/.env.example` (UPDATE)**

```bash
# TelePay10-26 Configuration

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Database (Cloud SQL)
DB_INSTANCE_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql
DB_NAME=telepaydb
DB_USER=postgres
DB_PASSWORD=your_password_here
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800

# Secret Manager (Google Cloud)
GOOGLE_CLOUD_PROJECT=telepay-459221

# NowPayments
NOWPAYMENTS_API_KEY=your_api_key_here
NOWPAYMENTS_IPN_CALLBACK_URL=https://your-webhook-url.com/ipn

# Security
WEBHOOK_SIGNING_SECRET=your_hmac_secret_here
ALLOWED_IPS=10.0.0.0/8,35.190.247.0/24,35.191.0.0/16

# Rate Limiting
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_BURST=20

# Flask Server
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false

# Reverse Proxy
DOMAIN_NAME=telepay.yourdomain.com
```

**Checklist:**
- [ ] Update `.env.example` with all configuration
- [ ] Document each environment variable
- [ ] Create Secret Manager entries for sensitive values
- [ ] Set up environment variable validation
- [ ] Create configuration loading script

---

## Summary: Implementation Timeline

### Week 1: Security Hardening (CRITICAL)
- ✅ HMAC authentication
- ✅ IP whitelist
- ✅ Rate limiting
- ✅ HTTPS setup
- ✅ Security middleware

### Week 2: Modular Structure
- ✅ Flask blueprints
- ✅ Database connection pooling
- ✅ Modular bot handlers
- ✅ Services layer

### Week 3: Services & Business Logic
- ✅ Payment service
- ✅ Notification service
- ✅ Broadcast service
- ✅ Subscription service

### Week 4: Testing & Quality
- ✅ Unit tests
- ✅ Integration tests
- ✅ Logging & monitoring
- ✅ Documentation

### Week 5: Deployment & Operations
- ✅ systemd service
- ✅ Environment configuration
- ✅ Health monitoring
- ✅ Deployment automation

---

## Testing Checklist

After each phase, verify:

### Security Testing
- [ ] HMAC signature verification works
- [ ] Invalid signatures are rejected
- [ ] IP whitelist blocks unauthorized IPs
- [ ] Rate limiting triggers on excess requests
- [ ] HTTPS redirects HTTP traffic
- [ ] Security headers present in responses

### Functional Testing
- [ ] Payment flow works end-to-end
- [ ] Donation flow works with keypad
- [ ] Notifications are delivered
- [ ] Database queries use connection pool
- [ ] Bot commands work correctly
- [ ] ConversationHandler states work

### Performance Testing
- [ ] Connection pool handles concurrent requests
- [ ] Rate limiting doesn't block legitimate traffic
- [ ] Response times are acceptable
- [ ] Memory usage is stable
- [ ] No connection leaks

### Integration Testing
- [ ] Cloud Run → Local VM communication works
- [ ] Webhooks from NowPayments are processed
- [ ] Telegram Bot API integration works
- [ ] Database operations are reliable
- [ ] Error handling works correctly

---

## Rollback Plan

If issues arise during implementation:

1. **Git Branch Strategy**
   - Create feature branch for each phase
   - Test thoroughly before merging to main
   - Tag stable releases

2. **Database Migrations**
   - Always create rollback scripts
   - Test migrations on clone database first
   - Keep backups before major changes

3. **Service Rollback**
   - Keep previous working version
   - Systemd can quickly switch versions
   - Document rollback procedure

---

## Success Criteria

Implementation is complete when:

- [ ] All security measures implemented and tested
- [ ] Code is modular and well-organized
- [ ] Test coverage >80%
- [ ] Documentation is complete
- [ ] Production deployment successful
- [ ] Performance metrics meet targets
- [ ] No critical bugs in production

---

**END OF IMPLEMENTATION CHECKLIST**
