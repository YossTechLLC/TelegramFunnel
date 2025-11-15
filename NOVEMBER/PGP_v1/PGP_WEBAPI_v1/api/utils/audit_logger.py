#!/usr/bin/env python
"""
📋 Audit Logger for PGP_WEBAPI_v1
Security event logging for authentication and verification flows
"""
from datetime import datetime
from typing import Optional


class AuditLogger:
    """Handles security audit logging for authentication events"""

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format"""
        return datetime.utcnow().isoformat() + 'Z'

    @staticmethod
    def _mask_token(token: str, show_chars: int = 8) -> str:
        """
        Mask token for logging (show first N chars only)

        Args:
            token: Token to mask
            show_chars: Number of characters to show

        Returns:
            Masked token string
        """
        if not token or len(token) <= show_chars:
            return "***"
        return f"{token[:show_chars]}...***"

    @staticmethod
    def log_email_verification_sent(user_id: str, email: str) -> None:
        """
        Log when verification email is sent

        Args:
            user_id: User UUID
            email: Email address
        """
        timestamp = AuditLogger._get_timestamp()
        print(f"📧 [AUDIT] {timestamp} - Email verification sent | user_id={user_id} | email={email}")

    @staticmethod
    def log_email_verified(user_id: str, email: str) -> None:
        """
        Log successful email verification

        Args:
            user_id: User UUID
            email: Email address
        """
        timestamp = AuditLogger._get_timestamp()
        print(f"✅ [AUDIT] {timestamp} - Email verified | user_id={user_id} | email={email}")

    @staticmethod
    def log_email_verification_failed(email: Optional[str], reason: str, token_excerpt: Optional[str] = None) -> None:
        """
        Log failed email verification attempt

        Args:
            email: Email address (may be None if token invalid)
            reason: Reason for failure
            token_excerpt: First few chars of token (for debugging)
        """
        timestamp = AuditLogger._get_timestamp()
        email_display = email if email else "unknown"
        token_display = AuditLogger._mask_token(token_excerpt) if token_excerpt else "N/A"

        print(f"❌ [AUDIT] {timestamp} - Email verification FAILED | email={email_display} | reason={reason} | token={token_display}")

    @staticmethod
    def log_password_reset_requested(email: str, user_found: bool) -> None:
        """
        Log password reset request

        Args:
            email: Email address
            user_found: Whether user exists (logged but not revealed to requester)
        """
        timestamp = AuditLogger._get_timestamp()
        status = "user_found" if user_found else "user_not_found"
        print(f"🔐 [AUDIT] {timestamp} - Password reset requested | email={email} | status={status}")

    @staticmethod
    def log_password_reset_completed(user_id: str, email: str) -> None:
        """
        Log successful password reset

        Args:
            user_id: User UUID
            email: Email address
        """
        timestamp = AuditLogger._get_timestamp()
        print(f"✅ [AUDIT] {timestamp} - Password reset COMPLETED | user_id={user_id} | email={email}")

    @staticmethod
    def log_password_reset_failed(email: Optional[str], reason: str, token_excerpt: Optional[str] = None) -> None:
        """
        Log failed password reset attempt

        Args:
            email: Email address (may be None if token invalid)
            reason: Reason for failure
            token_excerpt: First few chars of token (for debugging)
        """
        timestamp = AuditLogger._get_timestamp()
        email_display = email if email else "unknown"
        token_display = AuditLogger._mask_token(token_excerpt) if token_excerpt else "N/A"

        print(f"❌ [AUDIT] {timestamp} - Password reset FAILED | email={email_display} | reason={reason} | token={token_display}")

    @staticmethod
    def log_rate_limit_exceeded(endpoint: str, ip: str, user_identifier: Optional[str] = None) -> None:
        """
        Log when rate limit is exceeded

        Args:
            endpoint: API endpoint that was rate limited
            ip: IP address of requester
            user_identifier: Username or email if authenticated
        """
        timestamp = AuditLogger._get_timestamp()
        user_display = user_identifier if user_identifier else "anonymous"

        print(f"⚠️  [AUDIT] {timestamp} - Rate limit EXCEEDED | endpoint={endpoint} | ip={ip} | user={user_display}")

    @staticmethod
    def log_suspicious_activity(activity_type: str, details: str, ip: str, user_identifier: Optional[str] = None) -> None:
        """
        Log suspicious security activity

        Args:
            activity_type: Type of suspicious activity
            details: Additional details
            ip: IP address
            user_identifier: Username or email if available
        """
        timestamp = AuditLogger._get_timestamp()
        user_display = user_identifier if user_identifier else "anonymous"

        print(f"🚨 [AUDIT] {timestamp} - Suspicious activity: {activity_type} | details={details} | ip={ip} | user={user_display}")

    @staticmethod
    def log_login_attempt(username: str, success: bool, reason: Optional[str] = None, ip: Optional[str] = None) -> None:
        """
        Log login attempt (success or failure)

        Args:
            username: Username attempting to login
            success: Whether login succeeded
            reason: Reason for failure (if applicable)
            ip: IP address of requester
        """
        timestamp = AuditLogger._get_timestamp()
        status = "SUCCESS" if success else "FAILED"
        ip_display = ip if ip else "unknown"
        reason_display = f" | reason={reason}" if reason else ""

        print(f"🔑 [AUDIT] {timestamp} - Login {status} | username={username} | ip={ip_display}{reason_display}")

    @staticmethod
    def log_signup_attempt(username: str, email: str, success: bool, reason: Optional[str] = None, ip: Optional[str] = None) -> None:
        """
        Log signup attempt

        Args:
            username: Username attempting to signup
            email: Email address
            success: Whether signup succeeded
            reason: Reason for failure (if applicable)
            ip: IP address of requester
        """
        timestamp = AuditLogger._get_timestamp()
        status = "SUCCESS" if success else "FAILED"
        ip_display = ip if ip else "unknown"
        reason_display = f" | reason={reason}" if reason else ""

        print(f"📝 [AUDIT] {timestamp} - Signup {status} | username={username} | email={email} | ip={ip_display}{reason_display}")

    @staticmethod
    def log_verification_resent(email: str, user_found: bool, ip: Optional[str] = None) -> None:
        """
        Log verification email resend request

        Args:
            email: Email address
            user_found: Whether user exists (logged but not revealed to requester)
            ip: IP address of requester
        """
        timestamp = AuditLogger._get_timestamp()
        status = "sent" if user_found else "skipped_user_not_found"
        ip_display = ip if ip else "unknown"

        print(f"📧 [AUDIT] {timestamp} - Verification resend | email={email} | status={status} | ip={ip_display}")

    @staticmethod
    def log_email_change_requested(user_id: str, old_email: str, new_email: str, ip: Optional[str] = None) -> None:
        """
        Log email change request

        Args:
            user_id: User UUID
            old_email: Current email address
            new_email: Requested new email address
            ip: IP address of requester
        """
        timestamp = AuditLogger._get_timestamp()
        ip_display = ip if ip else "unknown"

        print(f"📧 [AUDIT] {timestamp} - Email change requested | user_id={user_id} | old={old_email} | new={new_email} | ip={ip_display}")

    @staticmethod
    def log_email_change_failed(user_id: str, email: str, new_email: str, reason: str, ip: Optional[str] = None) -> None:
        """
        Log failed email change attempt

        Args:
            user_id: User UUID
            email: Current email address
            new_email: Attempted new email address
            reason: Reason for failure
            ip: IP address of requester
        """
        timestamp = AuditLogger._get_timestamp()
        ip_display = ip if ip else "unknown"

        print(f"❌ [AUDIT] {timestamp} - Email change failed | user_id={user_id} | email={email} | new={new_email} | reason={reason} | ip={ip_display}")

    @staticmethod
    def log_email_changed(user_id: str, old_email: str, new_email: str) -> None:
        """
        Log successful email change

        Args:
            user_id: User UUID
            old_email: Previous email address
            new_email: New email address (now active)
        """
        timestamp = AuditLogger._get_timestamp()

        print(f"✅ [AUDIT] {timestamp} - Email changed successfully | user_id={user_id} | old={old_email} | new={new_email}")

    @staticmethod
    def log_email_change_cancelled(user_id: str, email: str, cancelled_email: str, ip: Optional[str] = None) -> None:
        """
        Log cancelled email change

        Args:
            user_id: User UUID
            email: Current email address
            cancelled_email: Email change that was cancelled
            ip: IP address of requester
        """
        timestamp = AuditLogger._get_timestamp()
        ip_display = ip if ip else "unknown"

        print(f"🚫 [AUDIT] {timestamp} - Email change cancelled | user_id={user_id} | email={email} | cancelled={cancelled_email} | ip={ip_display}")

    @staticmethod
    def log_password_changed(user_id: str, email: str, ip: Optional[str] = None) -> None:
        """
        Log successful password change

        Args:
            user_id: User UUID
            email: User email address
            ip: IP address of requester
        """
        timestamp = AuditLogger._get_timestamp()
        ip_display = ip if ip else "unknown"

        print(f"🔐 [AUDIT] {timestamp} - Password changed | user_id={user_id} | email={email} | ip={ip_display}")

    @staticmethod
    def log_password_change_failed(user_id: str, email: str, reason: str, ip: Optional[str] = None) -> None:
        """
        Log failed password change attempt

        Args:
            user_id: User UUID
            email: User email address
            reason: Reason for failure
            ip: IP address of requester
        """
        timestamp = AuditLogger._get_timestamp()
        ip_display = ip if ip else "unknown"

        print(f"❌ [AUDIT] {timestamp} - Password change failed | user_id={user_id} | email={email} | reason={reason} | ip={ip_display}")
