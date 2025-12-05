#!/usr/bin/env python
"""
Authentication utilities for PGP_v1 services.

This package provides authentication helpers for:
- Service-to-service authentication (IAM identity tokens)
- HMAC signature generation and validation
"""
from .service_auth import (
    ServiceAuthenticator,
    get_authenticator,
    call_authenticated_service
)

__all__ = [
    'ServiceAuthenticator',
    'get_authenticator',
    'call_authenticated_service',
]
