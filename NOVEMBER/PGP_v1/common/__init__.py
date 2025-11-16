"""
PayGatePrime v1 - Common Security Modules
Shared security components for all services
"""

from .oidc_auth import require_oidc_token, get_caller_identity, is_authorized_service
from .security_headers import apply_security_headers, apply_internal_security, apply_api_security, apply_web_security
from .validators import (
    PaymentValidator,
    WalletValidator,
    OrderValidator,
    IPNValidator,
    validate_payment_request,
    sanitize_log_amount,
    sanitize_log_wallet
)

__all__ = [
    # OIDC Authentication
    'require_oidc_token',
    'get_caller_identity',
    'is_authorized_service',

    # Security Headers
    'apply_security_headers',
    'apply_internal_security',
    'apply_api_security',
    'apply_web_security',

    # Validators
    'PaymentValidator',
    'WalletValidator',
    'OrderValidator',
    'IPNValidator',
    'validate_payment_request',
    'sanitize_log_amount',
    'sanitize_log_wallet',
]
