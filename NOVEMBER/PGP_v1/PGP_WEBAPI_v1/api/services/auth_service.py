#!/usr/bin/env python
"""
🔐 Authentication Service for GCRegisterAPI-10-26
Handles user registration, login, and password management
"""
import bcrypt
from datetime import datetime, timedelta
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from typing import Optional, Dict, Any
from api.services.token_service import TokenService
from itsdangerous import SignatureExpired, BadSignature


class AuthService:
    """Handles authentication operations"""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify a password against a hash

        Args:
            password: Plain text password
            password_hash: Bcrypt hash to verify against

        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def create_user(conn, username: str, email: str, password: str) -> dict:
        """
        Create a new user account with email verification token

        Args:
            conn: Database connection
            username: Username
            email: Email address
            password: Plain text password (will be hashed)

        Returns:
            User data dict with verification_token for email sending

        Raises:
            ValueError: If username or email already exists
        """
        try:
            cursor = conn.cursor()

            # Check if username exists
            cursor.execute(
                "SELECT user_id FROM registered_users WHERE username = %s",
                (username,)
            )
            if cursor.fetchone():
                raise ValueError('Username already exists')

            # Check if email exists
            cursor.execute(
                "SELECT user_id FROM registered_users WHERE email = %s",
                (email,)
            )
            if cursor.fetchone():
                raise ValueError('Email already exists')

            # Hash password
            password_hash = AuthService.hash_password(password)

            # Insert user
            cursor.execute("""
                INSERT INTO registered_users (
                    username,
                    email,
                    password_hash,
                    is_active,
                    email_verified,
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, TRUE, FALSE, NOW(), NOW()
                )
                RETURNING user_id, username, email, created_at
            """, (username, email, password_hash))

            user = cursor.fetchone()
            user_id = str(user[0])

            # Generate email verification token
            token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
            verification_token = token_service.generate_email_verification_token(user_id, email)
            token_expires = TokenService.get_expiration_datetime('email_verification')

            # Store token in database
            cursor.execute("""
                UPDATE registered_users
                SET verification_token = %s,
                    verification_token_expires = %s
                WHERE user_id = %s
            """, (verification_token, token_expires, user_id))

            cursor.close()

            print(f"✅ User created: {username} ({email}) - verification required")

            return {
                'user_id': user_id,
                'username': user[1],
                'email': user[2],
                'created_at': user[3].isoformat() if user[3] else None,
                'verification_token': verification_token  # For email sending
            }

        except Exception as e:
            print(f"❌ Error creating user: {e}")
            raise

    @staticmethod
    def authenticate_user(conn, username: str, password: str) -> dict:
        """
        Authenticate a user (ALLOWS UNVERIFIED EMAILS - NEW BEHAVIOR)

        Args:
            conn: Database connection
            username: Username
            password: Plain text password

        Returns:
            User data dict if authentication successful (includes email_verified status)

        Raises:
            ValueError: If authentication fails
        """
        try:
            cursor = conn.cursor()

            # Get user
            cursor.execute("""
                SELECT user_id, username, email, password_hash, is_active, email_verified
                FROM registered_users
                WHERE username = %s
            """, (username,))

            user = cursor.fetchone()
            cursor.close()

            if not user:
                raise ValueError('Invalid username or password')

            user_id, username, email, password_hash, is_active, email_verified = user

            # Check if account is active
            if not is_active:
                raise ValueError('Account is disabled')

            # Verify password
            if not AuthService.verify_password(password, password_hash):
                raise ValueError('Invalid username or password')

            # REMOVED: Email verification check (allow unverified logins)
            # Old code: if not email_verified: raise ValueError(...)

            # Update last_login
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE registered_users
                SET last_login = NOW()
                WHERE user_id = %s
            """, (user_id,))
            cursor.close()

            return {
                'user_id': str(user_id),
                'username': username,
                'email': email,
                'email_verified': email_verified
            }

        except Exception as e:
            print(f"❌ Error authenticating user: {e}")
            raise

    @staticmethod
    def create_tokens(user_id: str, username: str) -> dict:
        """
        Create access and refresh tokens

        Args:
            user_id: User UUID
            username: Username

        Returns:
            Dict with access_token and refresh_token
        """
        # Access token (15 minutes)
        access_token = create_access_token(
            identity=user_id,
            additional_claims={'username': username},
            expires_delta=timedelta(minutes=15)
        )

        # Refresh token (30 days)
        refresh_token = create_refresh_token(
            identity=user_id,
            expires_delta=timedelta(days=30)
        )

        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': 900  # 15 minutes in seconds
        }

    @staticmethod
    def verify_email(conn, token: str) -> Dict[str, Any]:
        """
        Verify email address using verification token

        Args:
            conn: Database connection
            token: Email verification token from URL

        Returns:
            Dict with success status and user info

        Raises:
            SignatureExpired: If token has expired
            BadSignature: If token is invalid
            ValueError: For other validation errors
        """
        try:
            # Verify token signature and expiration
            token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
            token_data = token_service.verify_email_verification_token(token)

            user_id = token_data['user_id']
            email = token_data['email']

            cursor = conn.cursor()

            # Get user and verify token matches database
            cursor.execute("""
                SELECT verification_token, verification_token_expires,
                       email_verified, username
                FROM registered_users
                WHERE user_id = %s AND email = %s
            """, (user_id, email))

            user = cursor.fetchone()

            if not user:
                raise ValueError('User not found or email mismatch')

            db_token, token_expires, already_verified, username = user

            # Check if already verified
            if already_verified:
                print(f"⚠️  Email already verified for user {user_id}")
                return {
                    'success': True,
                    'message': 'Email already verified. You can log in now.',
                    'already_verified': True,
                    'username': username
                }

            # Verify token matches database
            if db_token != token:
                raise ValueError('Invalid verification token')

            # Check expiration (additional check beyond itsdangerous)
            if token_expires and token_expires < datetime.utcnow():
                raise ValueError('Verification token has expired')

            # Mark email as verified
            cursor.execute("""
                UPDATE registered_users
                SET email_verified = TRUE,
                    verification_token = NULL,
                    verification_token_expires = NULL,
                    updated_at = NOW()
                WHERE user_id = %s
            """, (user_id,))

            cursor.close()

            print(f"✅ Email verified for user {user_id} ({email})")

            return {
                'success': True,
                'message': 'Email verified successfully! You can now log in.',
                'username': username,
                'user_id': user_id,
                'email': email
            }

        except SignatureExpired:
            print(f"⏰ Verification token expired")
            raise ValueError('Verification link has expired. Please request a new one.')
        except BadSignature:
            print(f"❌ Invalid verification token signature")
            raise ValueError('Invalid verification link.')
        except Exception as e:
            print(f"❌ Error verifying email: {e}")
            raise

    @staticmethod
    def resend_verification_email(conn, email: str) -> Optional[Dict[str, Any]]:
        """
        Generate new verification token and return user data for resending email

        Returns None if user not found or already verified (for user enumeration protection)

        Args:
            conn: Database connection
            email: Email address

        Returns:
            Dict with user data and token if user exists and unverified, None otherwise
        """
        try:
            cursor = conn.cursor()

            # Get user by email
            cursor.execute("""
                SELECT user_id, username, email_verified
                FROM registered_users
                WHERE email = %s
            """, (email,))

            user = cursor.fetchone()

            if not user:
                # Don't reveal user existence
                print(f"⚠️  Resend verification requested for non-existent email: {email}")
                return None

            user_id, username, email_verified = user

            if email_verified:
                # Don't reveal verification status
                print(f"⚠️  Resend verification requested for already verified user: {user_id}")
                return None

            # Generate new verification token
            token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
            verification_token = token_service.generate_email_verification_token(str(user_id), email)
            token_expires = TokenService.get_expiration_datetime('email_verification')

            # Update database with new token
            cursor.execute("""
                UPDATE registered_users
                SET verification_token = %s,
                    verification_token_expires = %s,
                    updated_at = NOW()
                WHERE user_id = %s
            """, (verification_token, token_expires, user_id))

            cursor.close()

            print(f"✅ New verification token generated for user {user_id} ({email})")

            return {
                'user_id': str(user_id),
                'username': username,
                'email': email,
                'verification_token': verification_token
            }

        except Exception as e:
            print(f"❌ Error resending verification email: {e}")
            raise

    @staticmethod
    def request_password_reset(conn, email: str) -> Optional[Dict[str, Any]]:
        """
        Generate password reset token

        Returns None if user not found or inactive (for user enumeration protection)

        Args:
            conn: Database connection
            email: Email address

        Returns:
            Dict with user data and reset token if user exists and active, None otherwise
        """
        try:
            cursor = conn.cursor()

            # Get user by email
            cursor.execute("""
                SELECT user_id, username, email, is_active
                FROM registered_users
                WHERE email = %s
            """, (email,))

            user = cursor.fetchone()

            if not user:
                # Don't reveal user existence
                print(f"⚠️  Password reset requested for non-existent email: {email}")
                return None

            user_id, username, email, is_active = user

            if not is_active:
                # Don't reveal account status
                print(f"⚠️  Password reset requested for inactive user: {user_id}")
                return None

            # Generate reset token
            token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
            reset_token = token_service.generate_password_reset_token(str(user_id), email)
            token_expires = TokenService.get_expiration_datetime('password_reset')

            # Store token in database
            cursor.execute("""
                UPDATE registered_users
                SET reset_token = %s,
                    reset_token_expires = %s,
                    updated_at = NOW()
                WHERE user_id = %s
            """, (reset_token, token_expires, user_id))

            cursor.close()

            print(f"🔐 Password reset token generated for user {user_id} ({email})")

            return {
                'user_id': str(user_id),
                'username': username,
                'email': email,
                'reset_token': reset_token
            }

        except Exception as e:
            print(f"❌ Error requesting password reset: {e}")
            raise

    @staticmethod
    def reset_password(conn, token: str, new_password: str) -> Dict[str, Any]:
        """
        Reset user password using reset token

        Args:
            conn: Database connection
            token: Password reset token from URL
            new_password: New password (plain text, will be hashed)

        Returns:
            Dict with success status and user info

        Raises:
            SignatureExpired: If token has expired
            BadSignature: If token is invalid
            ValueError: For other validation errors
        """
        try:
            # Verify token signature and expiration
            token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
            token_data = token_service.verify_password_reset_token(token)

            user_id = token_data['user_id']
            email = token_data['email']

            cursor = conn.cursor()

            # Get user and verify token matches database
            cursor.execute("""
                SELECT reset_token, reset_token_expires, username, email
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            user = cursor.fetchone()

            if not user:
                raise ValueError('User not found')

            db_token, token_expires, username, db_email = user

            # Verify token matches database
            if db_token != token:
                raise ValueError('Invalid reset token')

            # Check expiration (additional check beyond itsdangerous)
            if token_expires and token_expires < datetime.utcnow():
                raise ValueError('Reset token has expired')

            # Hash new password
            new_password_hash = AuthService.hash_password(new_password)

            # Update password and clear reset token
            cursor.execute("""
                UPDATE registered_users
                SET password_hash = %s,
                    reset_token = NULL,
                    reset_token_expires = NULL,
                    updated_at = NOW()
                WHERE user_id = %s
            """, (new_password_hash, user_id))

            cursor.close()

            print(f"🔐 Password reset completed for user {user_id} ({email})")

            return {
                'success': True,
                'message': 'Password has been reset successfully. Please log in with your new password.',
                'username': username,
                'email': db_email,
                'user_id': user_id
            }

        except SignatureExpired:
            print(f"⏰ Reset token expired")
            raise ValueError('Reset link has expired. Please request a new one.')
        except BadSignature:
            print(f"❌ Invalid reset token signature")
            raise ValueError('Invalid reset link.')
        except Exception as e:
            print(f"❌ Error resetting password: {e}")
            raise
