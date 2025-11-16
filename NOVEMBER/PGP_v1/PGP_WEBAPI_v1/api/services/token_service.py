#!/usr/bin/env python
"""
🔐 Token Service for Email Verification and Password Reset
Handles secure token generation, validation, and management

This service uses itsdangerous.URLSafeTimedSerializer to create cryptographically
secure, time-limited tokens for email verification and password reset flows.

Security Features:
- Tokens are cryptographically signed to prevent tampering
- Automatic expiration enforcement (24h for email, 1h for reset)
- Unique salts per token type prevent cross-use
- URL-safe encoding for email links
"""

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import os


class TokenService:
    """Handles token operations for email verification and password reset"""

    # Token expiration times (in seconds)
    EMAIL_VERIFICATION_MAX_AGE = 86400  # 24 hours
    PASSWORD_RESET_MAX_AGE = 3600       # 1 hour
    EMAIL_CHANGE_MAX_AGE = 3600         # 1 hour (NEW: for email change confirmation)

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize token service with secret key

        Args:
            secret_key: Secret key for token signing. If not provided, will attempt
                       to load from SIGNUP_SECRET_KEY environment variable.

        Raises:
            ValueError: If secret_key is not provided and SIGNUP_SECRET_KEY
                       environment variable is not set
        """
        self.secret_key = secret_key or os.getenv('SIGNUP_SECRET_KEY')
        if not self.secret_key:
            raise ValueError("❌ SIGNUP_SECRET_KEY must be provided or set in environment")

    def generate_email_verification_token(self, user_id: str, email: str) -> str:
        """
        Generate a secure token for email verification

        The token contains:
        - type: 'email_verification'
        - user_id: User UUID
        - email: User email address

        Token is signed and time-limited (24 hours).

        Args:
            user_id: User UUID string
            email: User email address

        Returns:
            URL-safe signed token string

        Example:
            >>> service = TokenService()
            >>> token = service.generate_email_verification_token(
            ...     '550e8400-e29b-41d4-a716-446655440000',
            ...     'user@example.com'
            ... )
            >>> print(token)
            'ImFiYzEyMyI.ZZGi1w.K8...'
        """
        serializer = URLSafeTimedSerializer(
            self.secret_key,
            salt='email-verify-v1'
        )

        token = serializer.dumps({
            'type': 'email_verification',
            'user_id': user_id,
            'email': email
        })

        return token

    def verify_email_verification_token(
        self,
        token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify and decode email verification token

        Validates:
        - Token signature (prevents tampering)
        - Token expiration (24 hours)
        - Token type (must be 'email_verification')

        Args:
            token: URL-safe signed token from email link

        Returns:
            Dict with 'user_id' and 'email' if valid, None otherwise
            Example: {'user_id': '550e8400...', 'email': 'user@example.com'}

        Raises:
            SignatureExpired: If token has expired (> 24 hours old)
            BadSignature: If token signature is invalid or tampered with

        Example:
            >>> service = TokenService()
            >>> data = service.verify_email_verification_token(token)
            >>> print(data['user_id'])
            '550e8400-e29b-41d4-a716-446655440000'
        """
        serializer = URLSafeTimedSerializer(
            self.secret_key,
            salt='email-verify-v1'
        )

        try:
            data = serializer.loads(
                token,
                max_age=self.EMAIL_VERIFICATION_MAX_AGE
            )

            # Validate token type for security
            if data.get('type') != 'email_verification':
                print(f"❌ Invalid token type: {data.get('type')}")
                raise BadSignature('Invalid token type')

            return {
                'user_id': data['user_id'],
                'email': data['email']
            }

        except SignatureExpired:
            print(f"⏰ Email verification token expired")
            raise
        except BadSignature as e:
            print(f"❌ Invalid email verification token signature: {e}")
            raise

    def generate_password_reset_token(self, user_id: str, email: str) -> str:
        """
        Generate a secure token for password reset

        The token contains:
        - type: 'password_reset'
        - user_id: User UUID
        - email: User email address

        Token is signed and time-limited (1 hour).

        Args:
            user_id: User UUID string
            email: User email address

        Returns:
            URL-safe signed token string

        Example:
            >>> service = TokenService()
            >>> token = service.generate_password_reset_token(
            ...     '550e8400-e29b-41d4-a716-446655440000',
            ...     'user@example.com'
            ... )
        """
        serializer = URLSafeTimedSerializer(
            self.secret_key,
            salt='password-reset-v1'
        )

        token = serializer.dumps({
            'type': 'password_reset',
            'user_id': user_id,
            'email': email
        })

        return token

    def verify_password_reset_token(
        self,
        token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify and decode password reset token

        Validates:
        - Token signature (prevents tampering)
        - Token expiration (1 hour)
        - Token type (must be 'password_reset')

        Args:
            token: URL-safe signed token from email link

        Returns:
            Dict with 'user_id' and 'email' if valid, None otherwise

        Raises:
            SignatureExpired: If token has expired (> 1 hour old)
            BadSignature: If token signature is invalid or tampered with

        Example:
            >>> service = TokenService()
            >>> data = service.verify_password_reset_token(token)
            >>> print(data['email'])
            'user@example.com'
        """
        serializer = URLSafeTimedSerializer(
            self.secret_key,
            salt='password-reset-v1'
        )

        try:
            data = serializer.loads(
                token,
                max_age=self.PASSWORD_RESET_MAX_AGE
            )

            # Validate token type for security
            if data.get('type') != 'password_reset':
                print(f"❌ Invalid token type: {data.get('type')}")
                raise BadSignature('Invalid token type')

            return {
                'user_id': data['user_id'],
                'email': data['email']
            }

        except SignatureExpired:
            print(f"⏰ Password reset token expired")
            raise
        except BadSignature as e:
            print(f"❌ Invalid password reset token signature: {e}")
            raise

    def generate_email_change_token(self, user_id: str, new_email: str) -> str:
        """
        Generate a secure token for email change confirmation

        The token contains:
        - type: 'email_change'
        - user_id: User UUID
        - new_email: New email address to confirm

        Token is signed and time-limited (1 hour).

        Args:
            user_id: User UUID string
            new_email: New email address to be confirmed

        Returns:
            URL-safe signed token string

        Example:
            >>> service = TokenService()
            >>> token = service.generate_email_change_token(
            ...     '550e8400-e29b-41d4-a716-446655440000',
            ...     'newemail@example.com'
            ... )
        """
        serializer = URLSafeTimedSerializer(
            self.secret_key,
            salt='email-change-v1'
        )

        token = serializer.dumps({
            'type': 'email_change',
            'user_id': user_id,
            'new_email': new_email
        })

        return token

    def verify_email_change_token(
        self,
        token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify and decode email change token

        Validates:
        - Token signature (prevents tampering)
        - Token expiration (1 hour)
        - Token type (must be 'email_change')

        Args:
            token: URL-safe signed token from email link

        Returns:
            Dict with 'user_id' and 'new_email' if valid, None otherwise
            Example: {'user_id': '550e8400...', 'new_email': 'new@example.com'}

        Raises:
            SignatureExpired: If token has expired (> 1 hour old)
            BadSignature: If token signature is invalid or tampered with

        Example:
            >>> service = TokenService()
            >>> data = service.verify_email_change_token(token)
            >>> print(data['new_email'])
            'newemail@example.com'
        """
        serializer = URLSafeTimedSerializer(
            self.secret_key,
            salt='email-change-v1'
        )

        try:
            data = serializer.loads(
                token,
                max_age=self.EMAIL_CHANGE_MAX_AGE
            )

            # Validate token type for security
            if data.get('type') != 'email_change':
                print(f"❌ Invalid token type: {data.get('type')}")
                raise BadSignature('Invalid token type')

            return {
                'user_id': data['user_id'],
                'new_email': data['new_email']
            }

        except SignatureExpired:
            print(f"⏰ Email change token expired")
            raise
        except BadSignature as e:
            print(f"❌ Invalid email change token signature: {e}")
            raise

    @staticmethod
    def get_expiration_datetime(token_type: str) -> datetime:
        """
        Get expiration datetime for a token type

        Used to calculate when to store expiration in database.

        Args:
            token_type: Either 'email_verification', 'password_reset', or 'email_change'

        Returns:
            Datetime object representing when the token will expire

        Raises:
            ValueError: If token_type is not recognized

        Example:
            >>> expires_at = TokenService.get_expiration_datetime('email_verification')
            >>> print(expires_at)
            2025-11-10 12:00:00
        """
        if token_type == 'email_verification':
            return datetime.utcnow() + timedelta(hours=24)
        elif token_type == 'password_reset':
            return datetime.utcnow() + timedelta(hours=1)
        elif token_type == 'email_change':
            return datetime.utcnow() + timedelta(hours=1)
        else:
            raise ValueError(f"❌ Unknown token type: {token_type}")
