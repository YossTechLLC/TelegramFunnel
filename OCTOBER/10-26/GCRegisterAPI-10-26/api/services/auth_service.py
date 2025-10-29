#!/usr/bin/env python
"""
🔐 Authentication Service for GCRegisterAPI-10-26
Handles user registration, login, and password management
"""
import bcrypt
from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token, create_refresh_token


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
        Create a new user account

        Args:
            conn: Database connection
            username: Username
            email: Email address
            password: Plain text password (will be hashed)

        Returns:
            User data dict (without password hash)

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
            cursor.close()

            return {
                'user_id': str(user[0]),
                'username': user[1],
                'email': user[2],
                'created_at': user[3].isoformat() if user[3] else None
            }

        except Exception as e:
            print(f"❌ Error creating user: {e}")
            raise

    @staticmethod
    def authenticate_user(conn, username: str, password: str) -> dict:
        """
        Authenticate a user

        Args:
            conn: Database connection
            username: Username
            password: Plain text password

        Returns:
            User data dict if authentication successful

        Raises:
            ValueError: If authentication fails
        """
        try:
            cursor = conn.cursor()

            # Get user
            cursor.execute("""
                SELECT user_id, username, email, password_hash, is_active
                FROM registered_users
                WHERE username = %s
            """, (username,))

            user = cursor.fetchone()
            cursor.close()

            if not user:
                raise ValueError('Invalid username or password')

            user_id, username, email, password_hash, is_active = user

            # Check if account is active
            if not is_active:
                raise ValueError('Account is disabled')

            # Verify password
            if not AuthService.verify_password(password, password_hash):
                raise ValueError('Invalid username or password')

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
                'email': email
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
