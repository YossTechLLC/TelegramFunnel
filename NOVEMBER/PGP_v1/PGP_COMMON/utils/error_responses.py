"""
Generic error response helpers for Flask applications.

Provides consistent error response format across all PGP services
with security-conscious message handling.

Response Format:
    {
        "error": "User-friendly error message",
        "error_id": "unique-error-id",
        "status": "error",
        "timestamp": "2025-11-18T12:34:56.789Z"
    }

References:
- OWASP: A04:2021 - Insecure Design
- PGP_SERVER_v1/security/ERROR_RESPONSE_STANDARDS.md
"""

from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from flask import jsonify
from PGP_COMMON.utils.error_sanitizer import (
    generate_error_id,
    sanitize_error_for_user,
    sanitize_sql_error,
    sanitize_authentication_error,
    sanitize_validation_error,
    log_error_with_context
)


def create_error_response(
    message: str,
    status_code: int = 500,
    error_id: Optional[str] = None,
    additional_fields: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create standardized error response.

    Args:
        message: Error message to show user
        status_code: HTTP status code
        error_id: Optional pre-generated error ID
        additional_fields: Optional extra fields to include in response

    Returns:
        Tuple of (response_dict, status_code)

    Example:
        >>> response, code = create_error_response("Invalid request", 400)
        >>> response
        {
            "error": "Invalid request",
            "error_id": "abc-123...",
            "status": "error",
            "timestamp": "2025-11-18T12:34:56.789Z"
        }
        >>> code
        400
    """
    if error_id is None:
        error_id = generate_error_id()

    response = {
        'error': message,
        'error_id': error_id,
        'status': 'error',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }

    # Add any additional fields
    if additional_fields:
        response.update(additional_fields)

    return response, status_code


def create_validation_error_response(
    message: str,
    field: Optional[str] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create validation error response (400 Bad Request).

    Args:
        message: Validation error message
        field: Optional field name that failed validation

    Returns:
        Tuple of (response_dict, 400)

    Example:
        >>> response, code = create_validation_error_response(
        ...     "Invalid email format",
        ...     field="email"
        ... )
        >>> response
        {
            "error": "Invalid email format",
            "field": "email",
            "error_id": "...",
            "status": "error",
            "timestamp": "..."
        }
    """
    additional = {'field': field} if field else None
    return create_error_response(message, 400, additional_fields=additional)


def create_authentication_error_response(
    message: str = "Invalid credentials"
) -> Tuple[Dict[str, Any], int]:
    """
    Create authentication error response (401 Unauthorized).

    Args:
        message: Authentication error message (default: generic)

    Returns:
        Tuple of (response_dict, 401)

    Security Note:
        Default message is intentionally generic to prevent
        username enumeration attacks.

    Example:
        >>> response, code = create_authentication_error_response()
        >>> response['error']
        'Invalid credentials'
        >>> code
        401
    """
    return create_error_response(message, 401)


def create_authorization_error_response(
    message: str = "Unauthorized IP address"
) -> Tuple[Dict[str, Any], int]:
    """
    Create authorization error response (403 Forbidden).

    Args:
        message: Authorization error message

    Returns:
        Tuple of (response_dict, 403)

    Example:
        >>> response, code = create_authorization_error_response()
        >>> code
        403
    """
    return create_error_response(message, 403)


def create_not_found_error_response(
    resource: str = "Resource"
) -> Tuple[Dict[str, Any], int]:
    """
    Create not found error response (404 Not Found).

    Args:
        resource: Name of resource that wasn't found

    Returns:
        Tuple of (response_dict, 404)

    Example:
        >>> response, code = create_not_found_error_response("User")
        >>> response['error']
        'User not found'
    """
    return create_error_response(f"{resource} not found", 404)


def create_rate_limit_error_response(
    retry_after: Optional[int] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create rate limit error response (429 Too Many Requests).

    Args:
        retry_after: Optional seconds until retry allowed

    Returns:
        Tuple of (response_dict, 429)

    Example:
        >>> response, code = create_rate_limit_error_response(retry_after=60)
        >>> response
        {
            "error": "Rate limit exceeded",
            "retry_after": 60,
            ...
        }
    """
    additional = {'retry_after': retry_after} if retry_after else None
    return create_error_response(
        "Rate limit exceeded",
        429,
        additional_fields=additional
    )


def create_database_error_response(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create database error response with sanitized message.

    Args:
        error: Database exception
        context: Optional context for logging

    Returns:
        Tuple of (response_dict, 500)

    Security Note:
        SQL error details are logged internally but NOT shown to user.

    Example:
        >>> try:
        ...     db.execute("SELECT * FROM missing_table")
        ... except Exception as e:
        ...     response, code = create_database_error_response(e)
        >>> # User sees: "A database error occurred"
        >>> # Logs contain: Full SQL error details
    """
    error_id = generate_error_id()

    # Log full error internally
    log_error_with_context(error, error_id, context or {})

    # Return sanitized message
    message = sanitize_sql_error(error, error_id)
    return create_error_response(message, 500, error_id=error_id)


def handle_flask_exception(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Generic Flask exception handler with intelligent error type detection.

    Args:
        error: Exception object
        context: Optional context for logging

    Returns:
        Tuple of (response_dict, status_code)

    Handles:
        - ValueError → 400 (validation error)
        - KeyError → 400 (missing field)
        - FileNotFoundError → 404
        - PermissionError → 403
        - All others → 500

    Example:
        >>> @app.errorhandler(Exception)
        ... def handle_error(e):
        ...     return jsonify(*handle_flask_exception(e))
    """
    error_id = generate_error_id()

    # Log error with context
    log_error_with_context(error, error_id, context or {})

    # Determine error type and response
    error_name = type(error).__name__

    if error_name in ['ValueError', 'ValidationError']:
        # Validation errors (400)
        message = sanitize_validation_error(error, error_id)
        return create_error_response(message, 400, error_id=error_id)

    elif error_name in ['KeyError', 'AttributeError']:
        # Missing required fields (400)
        return create_error_response(
            "Missing required field",
            400,
            error_id=error_id
        )

    elif error_name == 'FileNotFoundError':
        # Resource not found (404)
        return create_error_response(
            "Resource not found",
            404,
            error_id=error_id
        )

    elif error_name in ['PermissionError', 'Forbidden']:
        # Permission denied (403)
        return create_error_response(
            "Permission denied",
            403,
            error_id=error_id
        )

    elif error_name in ['AuthenticationError', 'Unauthorized']:
        # Authentication failed (401)
        message = sanitize_authentication_error(error, error_id)
        return create_error_response(message, 401, error_id=error_id)

    else:
        # Generic internal error (500)
        message = sanitize_error_for_user(error, error_id, context)
        return create_error_response(message, 500, error_id=error_id)


def create_success_response(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    status_code: int = 200
) -> Tuple[Dict[str, Any], int]:
    """
    Create standardized success response.

    Args:
        message: Success message
        data: Optional data to include
        status_code: HTTP status code (default: 200)

    Returns:
        Tuple of (response_dict, status_code)

    Example:
        >>> response, code = create_success_response(
        ...     "Payment processed",
        ...     data={"payment_id": "abc123"}
        ... )
        >>> response
        {
            "status": "success",
            "message": "Payment processed",
            "data": {"payment_id": "abc123"},
            "timestamp": "..."
        }
    """
    response = {
        'status': 'success',
        'message': message,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }

    if data:
        response['data'] = data

    return response, status_code
