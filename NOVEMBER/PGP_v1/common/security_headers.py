"""
PayGatePrime v1 - HTTP Security Headers
Configures Flask-Talisman for XSS, clickjacking, and HTTPS protection

Provides three security profiles:
1. INTERNAL: For Cloud Run services (no browser access)
2. API: For REST APIs (JSON only, no browser)
3. WEB: For frontend (allows safe resources)
"""

from flask_talisman import Talisman


# =============================================================================
# Content Security Policy (CSP) Configurations
# =============================================================================

# INTERNAL SERVICES: Cloud Run services with no browser access
# Most restrictive - blocks all content
INTERNAL_SERVICE_CSP = {
    'default-src': "'none'",           # Block everything by default
    'frame-ancestors': "'none'"        # Prevent being embedded in frames
}

# API SERVICES: REST APIs returning JSON
# Slightly less restrictive - allows self-origin for API responses
API_SERVICE_CSP = {
    'default-src': "'self'",           # Only same-origin resources
    'frame-ancestors': "'none'",       # No embedding
    'form-action': "'self'",           # Forms can only submit to self
    'base-uri': "'self'",              # Restrict base URL
    'object-src': "'none'",            # No Flash, Java, etc.
    'script-src': "'none'",            # No JavaScript (API only)
    'style-src': "'none'"              # No CSS
}

# WEB FRONTEND: React/HTML frontend
# Allows necessary resources for web application
WEB_FRONTEND_CSP = {
    'default-src': "'self'",
    'script-src': [
        "'self'",
        "'unsafe-inline'",             # React inline scripts (consider nonce in production)
        "https://cdn.jsdelivr.net",     # CDN for libraries
    ],
    'style-src': [
        "'self'",
        "'unsafe-inline'",             # Inline styles
        "https://fonts.googleapis.com"  # Google Fonts
    ],
    'font-src': [
        "'self'",
        "https://fonts.gstatic.com"
    ],
    'img-src': [
        "'self'",
        "data:",                        # Data URLs for images
        "https:"                        # HTTPS images
    ],
    'connect-src': [
        "'self'",
        "https://*.run.app",            # Cloud Run API endpoints
    ],
    'frame-ancestors': "'none'",
    'base-uri': "'self'",
    'form-action': "'self'"
}


# =============================================================================
# Security Header Application Functions
# =============================================================================

def apply_security_headers(app, service_type='internal'):
    """
    Apply Flask-Talisman security headers to Flask app.

    Args:
        app: Flask application instance
        service_type: One of 'internal', 'api', or 'web'

    Returns:
        Talisman instance

    Usage:
        from common.security_headers import apply_security_headers

        app = Flask(__name__)
        apply_security_headers(app, service_type='internal')

    Security Headers Applied:
        - Strict-Transport-Security (HSTS): Force HTTPS for 1 year
        - X-Frame-Options: Prevent clickjacking
        - X-Content-Type-Options: Prevent MIME sniffing
        - Content-Security-Policy: Restrict resource loading
        - Referrer-Policy: Control referrer information
    """

    # Select CSP configuration based on service type
    if service_type == 'internal':
        csp = INTERNAL_SERVICE_CSP
        print("🔒 [SECURITY] Applying INTERNAL service security headers (most restrictive)")

    elif service_type == 'api':
        csp = API_SERVICE_CSP
        print("🔒 [SECURITY] Applying API service security headers")

    elif service_type == 'web':
        csp = WEB_FRONTEND_CSP
        print("🔒 [SECURITY] Applying WEB frontend security headers")

    else:
        raise ValueError(f"Invalid service_type: {service_type}. Must be 'internal', 'api', or 'web'")

    # Configure Flask-Talisman
    talisman = Talisman(
        app,

        # Force HTTPS (Cloud Run provides HTTPS)
        force_https=True,
        force_https_permanent=True,

        # HSTS: Tell browsers to always use HTTPS for this domain
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,  # 1 year (recommended)
        strict_transport_security_include_subdomains=True,
        strict_transport_security_preload=True,

        # Content Security Policy
        content_security_policy=csp,
        content_security_policy_report_only=False,   # Enforce, don't just report

        # Referrer Policy: Don't leak URLs to external sites
        referrer_policy='strict-origin-when-cross-origin',

        # Frame Options: Prevent clickjacking
        frame_options='DENY',

        # Feature Policy / Permissions Policy
        # Disable unnecessary browser features
        feature_policy={
            'geolocation': "'none'",
            'microphone': "'none'",
            'camera': "'none'",
            'payment': "'none'" if service_type != 'web' else "'self'"
        }
    )

    print(f"✅ [SECURITY] Security headers configured for {service_type} service")
    return talisman


def apply_internal_security(app):
    """Shortcut for internal Cloud Run services."""
    return apply_security_headers(app, service_type='internal')


def apply_api_security(app):
    """Shortcut for API services (pgp-server-v1, pgp-npwebhook-v1)."""
    return apply_security_headers(app, service_type='api')


def apply_web_security(app):
    """Shortcut for web frontend (pgp-frontend-v1)."""
    return apply_security_headers(app, service_type='web')


# =============================================================================
# Security Header Testing
# =============================================================================

def test_security_headers(app):
    """
    Add test endpoint to verify security headers are present.

    Usage:
        from common.security_headers import test_security_headers
        test_security_headers(app)

    Then:
        curl -I https://your-service.run.app/security-test

    Expected Headers:
        Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
        X-Frame-Options: DENY
        X-Content-Type-Options: nosniff
        Content-Security-Policy: default-src 'none'; frame-ancestors 'none'
    """
    @app.route('/security-test', methods=['GET'])
    def security_test():
        return {
            'status': 'ok',
            'message': 'Security headers applied',
            'service_type': 'Check response headers'
        }, 200

    print("✅ [SECURITY] Test endpoint added: /security-test")


# =============================================================================
# Health Check Exemption (Optional)
# =============================================================================

def exempt_health_checks(talisman):
    """
    Exempt health check endpoints from HTTPS requirement.

    Some monitoring services may call /health over HTTP.
    Only use if absolutely necessary.

    Args:
        talisman: Talisman instance returned by apply_security_headers()

    Usage:
        talisman = apply_security_headers(app, 'internal')
        exempt_health_checks(talisman)
    """
    # Cloud Run health checks come from internal Google infrastructure
    # They should already be HTTPS, so this is rarely needed
    talisman.force_https_exempt = ['/health']
    print("⚠️ [SECURITY] /health endpoint exempted from HTTPS requirement")
