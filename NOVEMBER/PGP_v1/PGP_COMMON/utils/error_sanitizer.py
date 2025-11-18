"""
Error message sanitization for production environments.

This module prevents sensitive information disclosure through error messages
by providing environment-aware error handling.

Security Considerations:
- Production: Return generic messages, log details internally
- Development: Show detailed errors for debugging
- All errors get unique IDs for correlation with logs
- Never expose: stack traces, SQL queries, file paths, config values

References:
- OWASP: A04:2021 - Insecure Design
- CWE-209: Information Exposure Through Error Message
- PGP_SERVER_v1/security/ERROR_RESPONSE_STANDARDS.md
"""

import os
import uuid
import logging
import traceback
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_error_id() -> str:
    """
    Generate unique error ID for correlation between user-facing message and logs.

    Returns:
        Unique error ID string (UUID4 format)

    Example:
        >>> error_id = generate_error_id()
        >>> error_id
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    """
    return str(uuid.uuid4())


def get_environment() -> str:
    """
    Get current environment (development, staging, production).

    Returns:
        Environment string, defaults to 'production' if not set

    Environment Variables:
        ENVIRONMENT: 'development', 'staging', or 'production'
        FLASK_ENV: Fallback to Flask environment variable
        K_SERVICE: If set, assume production (Cloud Run indicator)

    Example:
        >>> os.environ['ENVIRONMENT'] = 'development'
        >>> get_environment()
        'development'
    """
    # Check explicit ENVIRONMENT variable
    env = os.getenv('ENVIRONMENT', '').lower()
    if env in ['development', 'dev', 'local']:
        return 'development'
    elif env in ['staging', 'stage', 'test']:
        return 'staging'
    elif env in ['production', 'prod']:
        return 'production'

    # Check Flask environment
    flask_env = os.getenv('FLASK_ENV', '').lower()
    if flask_env == 'development':
        return 'development'

    # If running on Cloud Run (K_SERVICE is set), assume production
    if os.getenv('K_SERVICE'):
        return 'production'

    # Default to production for safety
    return 'production'


def sanitize_error_for_user(
    error: Exception,
    error_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Sanitize error message for user display based on environment.

    Args:
        error: Exception object
        error_id: Optional pre-generated error ID
        context: Optional context dict for logging (not shown to user)

    Returns:
        Sanitized error message string

    Behavior:
        - Development: Return detailed error with stack trace
        - Production: Return generic message with error ID
        - Always logs full details internally

    Example:
        >>> try:
        ...     raise ValueError("Database connection failed: psql://user@host/db")
        ... except Exception as e:
        ...     msg = sanitize_error_for_user(e)
        >>> # Production: "An internal error occurred. Error ID: abc-123"
        >>> # Development: "ValueError: Database connection failed: psql://user@host/db"
    """
    if error_id is None:
        error_id = generate_error_id()

    env = get_environment()

    # Always log full error details internally
    log_error_with_context(error, error_id, context or {})

    # Return message based on environment
    if env == 'development':
        # Development: Show detailed error for debugging
        return f"{type(error).__name__}: {str(error)}"
    else:
        # Production/Staging: Generic message only
        return (
            f"An internal error occurred. "
            f"Error ID: {error_id}. "
            f"Please contact support with this ID."
        )


def log_error_with_context(
    error: Exception,
    error_id: str,
    context: Dict[str, Any]
) -> None:
    """
    Log error with full context to Cloud Logging.

    Args:
        error: Exception object
        error_id: Unique error ID for correlation
        context: Additional context (user_id, endpoint, etc.)

    Logs structured error with:
        - Error ID
        - Error type and message
        - Stack trace
        - Context information
        - Timestamp

    Example:
        >>> try:
        ...     db.execute("SELECT * FROM users")
        ... except Exception as e:
        ...     log_error_with_context(
        ...         e,
        ...         "abc-123",
        ...         {"user_id": 456, "endpoint": "/api/users"}
        ...     )
    """
    # Build structured log entry
    log_data = {
        'error_id': error_id,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'timestamp': datetime.utcnow().isoformat(),
        'environment': get_environment(),
        **context  # Include all context fields
    }

    # Log with full stack trace
    logger.error(
        f"❌ [ERROR] {type(error).__name__}: {str(error)}",
        extra=log_data,
        exc_info=True  # Include full stack trace in Cloud Logging
    )


def sanitize_sql_error(error: Exception, error_id: str) -> str:
    """
    Sanitize SQL-related errors to prevent information disclosure.

    SQL errors can expose:
        - Database structure (table names, column names)
        - Query syntax
        - Connection strings
        - Data types

    Args:
        error: Database exception
        error_id: Error ID for correlation

    Returns:
        Generic database error message

    Example:
        >>> # Original: "column 'user_password' does not exist"
        >>> sanitize_sql_error(exc, "abc-123")
        'A database error occurred. Error ID: abc-123'
    """
    env = get_environment()

    if env == 'development':
        # Development: Show actual SQL error
        return f"Database Error: {str(error)}"
    else:
        # Production: Generic message
        return f"A database error occurred. Error ID: {error_id}"


def sanitize_authentication_error(error: Exception, error_id: str) -> str:
    """
    Sanitize authentication errors to prevent username enumeration.

    Never reveal whether username or password was incorrect.
    Always return same generic message for all auth failures.

    Args:
        error: Authentication exception
        error_id: Error ID for correlation

    Returns:
        Generic authentication error message

    Example:
        >>> # Original: "User 'admin' not found"
        >>> sanitize_authentication_error(exc, "abc-123")
        'Invalid credentials'

        >>> # Original: "Password incorrect for user 'admin'"
        >>> sanitize_authentication_error(exc, "abc-123")
        'Invalid credentials'  # Same message!
    """
    # ALWAYS return same message to prevent username enumeration
    return "Invalid credentials"


def sanitize_validation_error(error: Exception, error_id: str) -> str:
    """
    Sanitize validation errors (safer to show some details).

    Validation errors are generally safe to show partial details
    as they help users correct their input.

    Args:
        error: Validation exception
        error_id: Error ID for correlation

    Returns:
        Sanitized validation error message

    Example:
        >>> # Original: "wallet_address: Invalid Ethereum address format"
        >>> sanitize_validation_error(exc, "abc-123")
        'Validation failed: Invalid address format'
    """
    env = get_environment()

    if env == 'development':
        # Development: Show full validation error
        return f"Validation Error: {str(error)}"
    else:
        # Production: Generic but helpful message
        error_msg = str(error).lower()

        # Extract safe keywords
        if 'address' in error_msg or 'wallet' in error_msg:
            return "Validation failed: Invalid address format"
        elif 'amount' in error_msg or 'price' in error_msg:
            return "Validation failed: Invalid amount"
        elif 'email' in error_msg:
            return "Validation failed: Invalid email format"
        elif 'required' in error_msg:
            return "Validation failed: Missing required field"
        else:
            return f"Validation failed. Error ID: {error_id}"


def should_show_stack_trace() -> bool:
    """
    Determine if stack traces should be shown to users.

    Returns:
        True if development environment, False otherwise

    Example:
        >>> os.environ['ENVIRONMENT'] = 'production'
        >>> should_show_stack_trace()
        False

        >>> os.environ['ENVIRONMENT'] = 'development'
        >>> should_show_stack_trace()
        True
    """
    return get_environment() == 'development'


def get_safe_error_details(error: Exception) -> Dict[str, Any]:
    """
    Extract safe error details for logging (never for user display).

    Args:
        error: Exception object

    Returns:
        Dict with safe error details for internal logging

    Example:
        >>> try:
        ...     raise ValueError("Invalid input")
        ... except Exception as e:
        ...     details = get_safe_error_details(e)
        >>> details
        {
            'type': 'ValueError',
            'message': 'Invalid input',
            'module': '__main__',
            'traceback_lines': 5
        }
    """
    return {
        'type': type(error).__name__,
        'message': str(error),
        'module': type(error).__module__,
        'traceback_lines': len(traceback.format_tb(error.__traceback__))
    }
