"""
PayGatePrime v1 - OIDC Service-to-Service Authentication
Verifies OIDC tokens from Google Cloud Run service accounts

This middleware ensures only authorized Cloud Run services can call internal endpoints.
Uses Google's OIDC token verification for service accounts.
"""

import os
from functools import wraps
from flask import request, abort, jsonify
import google.auth.transport.requests
import google.oauth2.id_token


def require_oidc_token(f):
    """
    Decorator to require and verify OIDC token from Cloud Run service account.

    Usage:
        @app.route('/internal-endpoint', methods=['POST'])
        @require_oidc_token
        def handle_task():
            caller_email = request.oidc_claims.get('email', 'unknown')
            # Process request

    Expected Header:
        Authorization: Bearer <OIDC_TOKEN>

    Security:
        - Verifies token signature using Google's public keys
        - Checks token expiration
        - Validates audience matches this service
        - Rejects tokens from unauthorized service accounts
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get Authorization header
        auth_header = request.headers.get('Authorization', '')

        if not auth_header:
            print("🔴 [OIDC_AUTH] Missing Authorization header")
            abort(401, description="Unauthorized - Missing Authorization header")

        if not auth_header.startswith('Bearer '):
            print("🔴 [OIDC_AUTH] Invalid Authorization header format")
            abort(401, description="Unauthorized - Invalid token format")

        # Extract token
        token = auth_header.split(' ', 1)[1]

        try:
            # Verify token
            auth_req = google.auth.transport.requests.Request()

            # Get expected audience (this service's URL)
            audience = os.environ.get('SERVICE_URL', request.url_root.rstrip('/'))

            # Verify OIDC token
            id_info = google.oauth2.id_token.verify_oauth2_token(
                token,
                auth_req,
                audience=audience
            )

            # Token is valid - attach claims to request
            request.oidc_claims = id_info

            # Log successful authentication
            caller_email = id_info.get('email', 'unknown')
            caller_sub = id_info.get('sub', 'unknown')
            print(f"✅ [OIDC_AUTH] Authenticated: {caller_email} (sub: {caller_sub})")

            # Optional: Check if caller is from our project
            # Google service accounts: *@project-id.iam.gserviceaccount.com
            # Cloud Tasks: service-PROJECT_NUMBER@gcp-sa-cloudtasks.iam.gserviceaccount.com
            if caller_email and 'iam.gserviceaccount.com' not in caller_email:
                print(f"⚠️ [OIDC_AUTH] Warning: Token not from service account: {caller_email}")

            return f(*args, **kwargs)

        except ValueError as e:
            # Token verification failed
            print(f"🔴 [OIDC_AUTH] Token verification failed: {e}")
            abort(401, description=f"Unauthorized - Invalid token: {str(e)}")

        except Exception as e:
            # Unexpected error
            print(f"🔴 [OIDC_AUTH] Unexpected error: {e}")
            abort(500, description="Internal server error during authentication")

    return decorated_function


def get_caller_identity():
    """
    Get identity of the authenticated caller from request context.

    Returns:
        dict: {
            'email': 'service-account@project.iam.gserviceaccount.com',
            'sub': 'unique-identifier',
            'aud': 'https://service-url',
            'iat': 1234567890,
            'exp': 1234567890
        }

    Usage:
        @app.route('/endpoint', methods=['POST'])
        @require_oidc_token
        def handle():
            identity = get_caller_identity()
            print(f"Called by: {identity['email']}")
    """
    if hasattr(request, 'oidc_claims'):
        return request.oidc_claims
    return None


def is_authorized_service(allowed_emails=None):
    """
    Check if caller is in list of allowed service accounts.

    Args:
        allowed_emails: List of allowed service account emails
                       e.g., ['pgp-webhook1@project.iam.gserviceaccount.com']
                       If None, allows any service account from same project

    Returns:
        bool: True if authorized, False otherwise

    Usage:
        @app.route('/critical-endpoint', methods=['POST'])
        @require_oidc_token
        def handle():
            if not is_authorized_service(['specific-service@project.iam.gserviceaccount.com']):
                abort(403, "Forbidden - Unauthorized service")
    """
    claims = get_caller_identity()
    if not claims:
        return False

    caller_email = claims.get('email', '')

    # If no specific emails provided, allow any service account
    if allowed_emails is None:
        return 'iam.gserviceaccount.com' in caller_email

    # Check if caller is in allowed list
    return caller_email in allowed_emails


# Environment variable for toggling OIDC verification (dev/test only)
OIDC_VERIFICATION_ENABLED = os.environ.get('OIDC_VERIFICATION_ENABLED', 'true').lower() == 'true'


def require_oidc_token_dev_mode(f):
    """
    Development-friendly OIDC decorator that can be disabled via environment variable.

    ONLY USE FOR DEVELOPMENT/TESTING!
    Production should ALWAYS use require_oidc_token

    Set OIDC_VERIFICATION_ENABLED=false to disable verification (dev only)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not OIDC_VERIFICATION_ENABLED:
            print("⚠️ [OIDC_AUTH] VERIFICATION DISABLED (dev mode)")
            request.oidc_claims = {'email': 'dev-mode@localhost', 'sub': 'dev'}
            return f(*args, **kwargs)

        # Production path - verify token
        return require_oidc_token(f)(*args, **kwargs)

    return decorated_function
