# Email Verification & Password Reset Architecture

**Date:** 2025-11-09
**Status:** 🏗️ **ARCHITECTURAL PLAN**
**Version:** 1.0
**Author:** Claude Code

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Security Requirements](#security-requirements)
4. [Architecture Overview](#architecture-overview)
5. [Email Verification Flow](#email-verification-flow)
6. [Password Reset Flow](#password-reset-flow)
7. [Token Generation & Management](#token-generation--management)
8. [Email Service Integration](#email-service-integration)
9. [Rate Limiting & Security](#rate-limiting--security)
10. [Database Schema Updates](#database-schema-updates)
11. [API Endpoints Design](#api-endpoints-design)
12. [Frontend Integration Points](#frontend-integration-points)
13. [Implementation Phases](#implementation-phases)
14. [Security Considerations](#security-considerations)
15. [Testing Strategy](#testing-strategy)
16. [Monitoring & Logging](#monitoring--logging)

---

## Executive Summary

This document outlines a comprehensive, production-ready architecture for implementing email verification and password reset functionality in the GCRegisterAPI-10-26 system. The design follows OWASP best practices and 2025 security standards.

### Goals
- ✅ Implement secure email verification for new user registrations
- ✅ Implement secure password reset flow for existing users
- ✅ Prevent user enumeration attacks
- ✅ Protect against brute-force and automated attacks
- ✅ Ensure compliance with OWASP security guidelines
- ✅ Maintain user experience while maximizing security

### Key Features
- 🔐 Cryptographically secure token generation using `itsdangerous`
- ⏰ Time-limited, single-use tokens
- 📧 Professional email notifications
- 🚦 Rate limiting and CAPTCHA protection
- 🔒 Protection against user enumeration
- 📊 Comprehensive audit logging
- 🔄 Automatic session invalidation on password reset

---

## Current State Analysis

### ✅ What's Working
1. **User Registration:** Basic signup flow creates users in `registered_users` table
2. **Authentication:** Login flow with JWT tokens (access + refresh)
3. **Password Security:** Bcrypt hashing for password storage
4. **Database Schema:** All necessary fields already exist in the schema

### ❌ What's Missing
1. **Email Verification:**
   - `verification_token` field is NULL
   - `verification_token_expires` field is NULL
   - `email_verified` always remains FALSE
   - No verification email sent on signup
   - Users can access system without verified email

2. **Password Reset:**
   - `reset_token` field is NULL
   - `reset_token_expires` field is NULL
   - No password reset endpoint exists
   - Users cannot self-service password recovery

3. **Supporting Infrastructure:**
   - No email sending service configured
   - No rate limiting on auth endpoints
   - No user enumeration protection
   - No audit logging for sensitive operations

### Database Schema (Already Present)
```sql
CREATE TABLE registered_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),              -- ← TO BE POPULATED
    verification_token_expires TIMESTAMP,         -- ← TO BE POPULATED
    reset_token VARCHAR(255),                     -- ← TO BE POPULATED
    reset_token_expires TIMESTAMP,                -- ← TO BE POPULATED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```

---

## Security Requirements

### OWASP Compliance Matrix

Based on **OWASP Forgot Password Cheat Sheet** and **OWASP Authentication Cheat Sheet**:

| Requirement | Implementation | Priority |
|-------------|----------------|----------|
| **Secure Token Generation** | Use `itsdangerous.URLSafeTimedSerializer` with CSPRNG | 🔴 CRITICAL |
| **Token Length** | Minimum 32 bytes (256 bits) | 🔴 CRITICAL |
| **Token Expiration** | Email verification: 24h, Password reset: 1h | 🔴 CRITICAL |
| **Single-Use Tokens** | Clear token from DB after use | 🔴 CRITICAL |
| **User Enumeration Prevention** | Consistent responses for existing/non-existing users | 🔴 CRITICAL |
| **Rate Limiting** | Max 3 requests per hour per email/IP | 🟡 HIGH |
| **HTTPS Only** | All token links use HTTPS | 🔴 CRITICAL |
| **Email Notifications** | Notify on password changes | 🟡 HIGH |
| **Session Invalidation** | Kill all sessions on password reset | 🟡 HIGH |
| **Audit Logging** | Log all verification/reset attempts | 🟢 MEDIUM |
| **CAPTCHA Protection** | On password reset request | 🟢 MEDIUM |

### Token Security Specifications

#### Email Verification Token
```python
{
    'type': 'email_verification',
    'user_id': '<uuid>',
    'email': '<email>',
    'timestamp': '<iso8601>',
    'salt': 'email-verify-v1'
}
```
- **Lifetime:** 24 hours (86400 seconds)
- **Storage:** Database + signed token in email URL
- **Single-use:** Cleared after successful verification
- **Regeneration:** Allowed, invalidates previous token

#### Password Reset Token
```python
{
    'type': 'password_reset',
    'user_id': '<uuid>',
    'email': '<email>',
    'timestamp': '<iso8601>',
    'salt': 'password-reset-v1'
}
```
- **Lifetime:** 1 hour (3600 seconds)
- **Storage:** Database + signed token in email URL
- **Single-use:** Cleared after successful reset
- **Regeneration:** Allowed, max 3 per hour per user

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Registration                         │
│                                                                  │
│  [User Signup] ──> [Create Account] ──> [Generate Token]       │
│                          │                      │                │
│                          │                      v                │
│                          │              [Store in DB]            │
│                          │                      │                │
│                          v                      v                │
│                  [Send Email] <───────── [Create URL]           │
│                          │                                       │
│                          v                                       │
│            [User Clicks Link] ──> [Verify Token] ──> [Activate] │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        Password Reset                            │
│                                                                  │
│  [Forgot Password] ──> [Request Reset] ──> [Check User]        │
│                                │                │                │
│                                │                v                │
│                                │         [Generate Token]        │
│                                │                │                │
│                                v                v                │
│                    [Generic Response] <──[Store in DB]          │
│                                │                │                │
│                                │                v                │
│                                │         [Send Email]            │
│                                │                │                │
│                                v                v                │
│            [User Clicks Link] ──> [Verify Token]                │
│                                         │                        │
│                                         v                        │
│                            [Reset Password] ──> [Invalidate]    │
│                                         │           Sessions     │
│                                         v                        │
│                              [Send Confirmation]                 │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Token Generation** | `itsdangerous.URLSafeTimedSerializer` | Secure, timed, URL-safe tokens |
| **Email Sending** | SendGrid / Mailgun / SMTP | Reliable email delivery |
| **Rate Limiting** | Flask-Limiter + Redis | Prevent abuse |
| **Template Engine** | Jinja2 (built into Flask) | Email HTML templates |
| **Validation** | Pydantic | Request validation |
| **Database** | PostgreSQL (existing) | Token storage |

---

## Email Verification Flow

### Detailed Step-by-Step Flow

#### Phase 1: User Registration
```python
POST /auth/signup
{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123!"
}
```

**Backend Process:**
1. ✅ Validate request data (Pydantic)
2. ✅ Check username/email uniqueness
3. ✅ Hash password (bcrypt)
4. ✅ Create user record with `email_verified=FALSE`
5. 🆕 **Generate verification token:**
   ```python
   serializer = URLSafeTimedSerializer(SECRET_KEY, salt='email-verify-v1')
   token = serializer.dumps({
       'user_id': str(user_id),
       'email': email
   })
   ```
6. 🆕 **Store token in database:**
   ```sql
   UPDATE registered_users
   SET verification_token = %s,
       verification_token_expires = NOW() + INTERVAL '24 hours'
   WHERE user_id = %s;
   ```
7. 🆕 **Send verification email:**
   ```
   Subject: Verify Your Email - TelePay

   Hi {username},

   Welcome to TelePay! Please verify your email address by clicking the link below:

   https://app.telepay.com/verify-email?token={token}

   This link will expire in 24 hours.

   If you didn't create this account, please ignore this email.
   ```
8. ✅ Return success response (WITHOUT tokens - user must verify first)
   ```json
   {
       "success": true,
       "message": "Account created. Please check your email to verify your account.",
       "user_id": "uuid",
       "email": "john@example.com",
       "verification_required": true
   }
   ```

#### Phase 2: Email Verification
```python
GET /auth/verify-email?token=<token>
```

**Backend Process:**
1. 🆕 **Extract token from query string**
2. 🆕 **Deserialize and validate token:**
   ```python
   try:
       serializer = URLSafeTimedSerializer(SECRET_KEY, salt='email-verify-v1')
       data = serializer.loads(token, max_age=86400)  # 24 hours
       user_id = data['user_id']
       email = data['email']
   except SignatureExpired:
       return {'error': 'Verification link has expired'}, 400
   except BadSignature:
       return {'error': 'Invalid verification link'}, 400
   ```
3. 🆕 **Verify token matches database:**
   ```sql
   SELECT verification_token, verification_token_expires, email_verified
   FROM registered_users
   WHERE user_id = %s;
   ```
4. 🆕 **Check expiration and usage:**
   - If `email_verified = TRUE`: Already verified
   - If `verification_token_expires < NOW()`: Expired
   - If `verification_token != token`: Invalid
5. 🆕 **Mark email as verified:**
   ```sql
   UPDATE registered_users
   SET email_verified = TRUE,
       verification_token = NULL,
       verification_token_expires = NULL,
       updated_at = NOW()
   WHERE user_id = %s;
   ```
6. 🆕 **Log verification event:**
   ```python
   logger.info(f"✅ Email verified for user {user_id} ({email})")
   ```
7. 🆕 **Return success response:**
   ```json
   {
       "success": true,
       "message": "Email verified successfully! You can now log in.",
       "redirect_url": "/login"
   }
   ```

#### Phase 3: Resend Verification Email
```python
POST /auth/resend-verification
{
    "email": "john@example.com"
}
```

**Backend Process:**
1. 🆕 **Rate limit check:** Max 3 per hour per email
2. 🆕 **Lookup user by email**
3. 🆕 **Check if already verified:**
   ```sql
   SELECT email_verified FROM registered_users WHERE email = %s;
   ```
4. 🆕 **Generate new token** (invalidates old one)
5. 🆕 **Update database** with new token
6. 🆕 **Send verification email**
7. 🆕 **Return generic success** (don't reveal if email exists)

---

## Password Reset Flow

### Detailed Step-by-Step Flow

#### Phase 1: Request Password Reset
```python
POST /auth/forgot-password
{
    "email": "john@example.com"
}
```

**Backend Process:**
1. 🆕 **Rate limit check:** Max 3 requests per hour per email/IP
2. 🆕 **OPTIONAL: CAPTCHA verification** (recommended for production)
3. 🆕 **Lookup user by email:**
   ```sql
   SELECT user_id, username, email, is_active
   FROM registered_users
   WHERE email = %s;
   ```
4. 🆕 **If user exists and is active:**
   ```python
   # Generate reset token
   serializer = URLSafeTimedSerializer(SECRET_KEY, salt='password-reset-v1')
   token = serializer.dumps({
       'user_id': str(user_id),
       'email': email
   })

   # Store in database
   UPDATE registered_users
   SET reset_token = %s,
       reset_token_expires = NOW() + INTERVAL '1 hour',
       updated_at = NOW()
   WHERE user_id = %s;

   # Send reset email
   send_password_reset_email(email, username, token)
   ```
5. 🆕 **Return GENERIC response** (same for existing/non-existing users):
   ```json
   {
       "success": true,
       "message": "If an account with that email exists, a password reset link has been sent."
   }
   ```

   **Security Note:** This prevents user enumeration attacks by not revealing whether the email exists in the system.

#### Phase 2: Reset Password
```python
POST /auth/reset-password
{
    "token": "<token>",
    "new_password": "NewSecurePass123!"
}
```

**Backend Process:**
1. 🆕 **Validate new password** (strength requirements)
2. 🆕 **Deserialize and validate token:**
   ```python
   try:
       serializer = URLSafeTimedSerializer(SECRET_KEY, salt='password-reset-v1')
       data = serializer.loads(token, max_age=3600)  # 1 hour
       user_id = data['user_id']
       email = data['email']
   except SignatureExpired:
       return {'error': 'Reset link has expired'}, 400
   except BadSignature:
       return {'error': 'Invalid reset link'}, 400
   ```
3. 🆕 **Verify token matches database:**
   ```sql
   SELECT reset_token, reset_token_expires, username, email
   FROM registered_users
   WHERE user_id = %s;
   ```
4. 🆕 **Check token validity:**
   - Token must match database
   - Must not be expired
   - Single-use enforcement
5. 🆕 **Hash new password:**
   ```python
   new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
   ```
6. 🆕 **Update password and clear token:**
   ```sql
   UPDATE registered_users
   SET password_hash = %s,
       reset_token = NULL,
       reset_token_expires = NULL,
       updated_at = NOW()
   WHERE user_id = %s;
   ```
7. 🆕 **Invalidate all existing sessions:**
   ```python
   # Increment a "session_version" field or maintain a session blacklist
   # This ensures stolen session tokens become invalid
   ```
8. 🆕 **Send confirmation email:**
   ```
   Subject: Password Reset Successful - TelePay

   Hi {username},

   Your password has been successfully reset.

   If you did not make this change, please contact support immediately.
   ```
9. 🆕 **Log security event:**
   ```python
   logger.warning(f"🔐 Password reset completed for user {user_id} ({email})")
   ```
10. 🆕 **Return success response:**
    ```json
    {
        "success": true,
        "message": "Password has been reset successfully. Please log in with your new password."
    }
    ```

---

## Token Generation & Management

### Token Service Implementation

**File:** `GCRegisterAPI-10-26/api/services/token_service.py`

```python
#!/usr/bin/env python
"""
🔐 Token Service for Email Verification and Password Reset
Handles secure token generation, validation, and management
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

    def __init__(self):
        """Initialize token service with secret key from environment"""
        self.secret_key = os.getenv('SECRET_KEY')
        if not self.secret_key:
            raise ValueError("SECRET_KEY environment variable must be set")

    def generate_email_verification_token(self, user_id: str, email: str) -> str:
        """
        Generate a secure token for email verification

        Args:
            user_id: User UUID
            email: User email address

        Returns:
            URL-safe signed token string
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

        Args:
            token: URL-safe signed token

        Returns:
            Dict with user_id and email if valid, None otherwise

        Raises:
            SignatureExpired: If token has expired
            BadSignature: If token signature is invalid
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

            # Validate token type
            if data.get('type') != 'email_verification':
                raise BadSignature('Invalid token type')

            return {
                'user_id': data['user_id'],
                'email': data['email']
            }

        except SignatureExpired:
            print(f"❌ Email verification token expired")
            raise
        except BadSignature:
            print(f"❌ Invalid email verification token signature")
            raise

    def generate_password_reset_token(self, user_id: str, email: str) -> str:
        """
        Generate a secure token for password reset

        Args:
            user_id: User UUID
            email: User email address

        Returns:
            URL-safe signed token string
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

        Args:
            token: URL-safe signed token

        Returns:
            Dict with user_id and email if valid, None otherwise

        Raises:
            SignatureExpired: If token has expired
            BadSignature: If token signature is invalid
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

            # Validate token type
            if data.get('type') != 'password_reset':
                raise BadSignature('Invalid token type')

            return {
                'user_id': data['user_id'],
                'email': data['email']
            }

        except SignatureExpired:
            print(f"❌ Password reset token expired")
            raise
        except BadSignature:
            print(f"❌ Invalid password reset token signature")
            raise

    @staticmethod
    def get_expiration_datetime(token_type: str) -> datetime:
        """
        Get expiration datetime for a token type

        Args:
            token_type: 'email_verification' or 'password_reset'

        Returns:
            Datetime object for token expiration
        """
        if token_type == 'email_verification':
            return datetime.utcnow() + timedelta(hours=24)
        elif token_type == 'password_reset':
            return datetime.utcnow() + timedelta(hours=1)
        else:
            raise ValueError(f"Unknown token type: {token_type}")
```

### Token Storage Best Practices

1. **Database Storage:**
   - Store hashed or signed token in database
   - Store expiration timestamp
   - Clear token after successful use (single-use enforcement)
   - Index on token fields for fast lookup

2. **Security Considerations:**
   - Tokens are cryptographically signed (prevents tampering)
   - Tokens include timestamp (automatic expiration)
   - Tokens use unique salts per type (prevents cross-use)
   - Secret key must be stored in environment variables (never in code)
   - Secret key should be rotated periodically

3. **Token Invalidation:**
   ```python
   # Single-use enforcement
   UPDATE registered_users
   SET verification_token = NULL,
       verification_token_expires = NULL
   WHERE user_id = %s;
   ```

---

## Email Service Integration

### Email Service Selection

#### Recommended Options

| Service | Pros | Cons | Free Tier |
|---------|------|------|-----------|
| **SendGrid** | ✅ Reliable, 99.9% uptime<br>✅ Great deliverability<br>✅ Easy API | ❌ Paid after free tier | 100 emails/day |
| **Mailgun** | ✅ Developer-friendly<br>✅ Good documentation<br>✅ EU compliance | ❌ Requires credit card | 5,000 emails/month |
| **Amazon SES** | ✅ Very cheap<br>✅ Scalable<br>✅ AWS integration | ❌ More complex setup<br>❌ Need AWS account | 62,000 emails/month (if in EC2) |
| **SMTP (Gmail)** | ✅ Free<br>✅ Easy setup | ❌ Low limits (500/day)<br>❌ Not for production | 500 emails/day |

**Recommendation:** Start with **SendGrid** for development/testing, migrate to **Amazon SES** for production scale.

### Email Service Implementation

**File:** `GCRegisterAPI-10-26/api/services/email_service.py`

```python
#!/usr/bin/env python
"""
📧 Email Service for GCRegisterAPI-10-26
Handles sending verification and password reset emails
"""
import os
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


class EmailService:
    """Handles email operations"""

    def __init__(self):
        """Initialize email service"""
        self.sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@telepay.com')
        self.from_name = os.getenv('FROM_NAME', 'TelePay')
        self.base_url = os.getenv('BASE_URL', 'https://app.telepay.com')

        if not self.sendgrid_api_key:
            print("⚠️ SENDGRID_API_KEY not set - email sending disabled")

    def send_verification_email(
        self,
        to_email: str,
        username: str,
        token: str
    ) -> bool:
        """
        Send email verification email

        Args:
            to_email: Recipient email
            username: User's username
            token: Verification token

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.sendgrid_api_key:
            print(f"📧 [DEV MODE] Verification email for {to_email}")
            print(f"🔗 Token: {token}")
            return True

        verification_url = f"{self.base_url}/verify-email?token={token}"

        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to_email),
            subject="Verify Your Email - TelePay",
            html_content=self._get_verification_email_template(
                username,
                verification_url
            )
        )

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✅ Verification email sent to {to_email}")
                return True
            else:
                print(f"❌ Failed to send verification email: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error sending verification email: {e}")
            return False

    def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        token: str
    ) -> bool:
        """
        Send password reset email

        Args:
            to_email: Recipient email
            username: User's username
            token: Reset token

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.sendgrid_api_key:
            print(f"📧 [DEV MODE] Password reset email for {to_email}")
            print(f"🔗 Token: {token}")
            return True

        reset_url = f"{self.base_url}/reset-password?token={token}"

        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to_email),
            subject="Password Reset Request - TelePay",
            html_content=self._get_password_reset_email_template(
                username,
                reset_url
            )
        )

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✅ Password reset email sent to {to_email}")
                return True
            else:
                print(f"❌ Failed to send reset email: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error sending reset email: {e}")
            return False

    def send_password_reset_confirmation_email(
        self,
        to_email: str,
        username: str
    ) -> bool:
        """
        Send confirmation email after successful password reset

        Args:
            to_email: Recipient email
            username: User's username

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.sendgrid_api_key:
            print(f"📧 [DEV MODE] Reset confirmation email for {to_email}")
            return True

        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to_email),
            subject="Password Reset Successful - TelePay",
            html_content=self._get_password_reset_confirmation_template(username)
        )

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✅ Reset confirmation email sent to {to_email}")
                return True
            else:
                print(f"❌ Failed to send confirmation email: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error sending confirmation email: {e}")
            return False

    @staticmethod
    def _get_verification_email_template(username: str, verification_url: str) -> str:
        """Get HTML template for verification email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Welcome to TelePay! 🎉</h1>
            </div>

            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p>Hi <strong>{username}</strong>,</p>

                <p>Thanks for signing up! Please verify your email address to activate your account.</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}"
                       style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Verify Email Address
                    </a>
                </div>

                <p style="color: #666; font-size: 14px;">
                    This link will expire in <strong>24 hours</strong>.
                </p>

                <p style="color: #666; font-size: 14px;">
                    If the button doesn't work, copy and paste this link into your browser:<br>
                    <a href="{verification_url}" style="color: #667eea; word-break: break-all;">{verification_url}</a>
                </p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #999; font-size: 12px;">
                    If you didn't create this account, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _get_password_reset_email_template(username: str, reset_url: str) -> str:
        """Get HTML template for password reset email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Password Reset Request 🔐</h1>
            </div>

            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p>Hi <strong>{username}</strong>,</p>

                <p>We received a request to reset your password. Click the button below to create a new password:</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}"
                       style="background: #f5576c; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Reset Password
                    </a>
                </div>

                <p style="color: #666; font-size: 14px;">
                    This link will expire in <strong>1 hour</strong>.
                </p>

                <p style="color: #666; font-size: 14px;">
                    If the button doesn't work, copy and paste this link into your browser:<br>
                    <a href="{reset_url}" style="color: #f5576c; word-break: break-all;">{reset_url}</a>
                </p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #999; font-size: 12px;">
                    If you didn't request a password reset, please ignore this email or contact support if you have concerns.
                </p>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _get_password_reset_confirmation_template(username: str) -> str:
        """Get HTML template for password reset confirmation"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Password Reset Successful ✅</h1>
            </div>

            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p>Hi <strong>{username}</strong>,</p>

                <p>Your password has been successfully reset.</p>

                <p>You can now log in with your new password.</p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #d32f2f; font-size: 14px; font-weight: bold;">
                    ⚠️ If you did not make this change, please contact support immediately.
                </p>
            </div>
        </body>
        </html>
        """
```

### Environment Variables

Add to `.env` or Cloud Run environment:
```bash
# Email Service
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FROM_EMAIL=noreply@telepay.com
FROM_NAME=TelePay
BASE_URL=https://app.telepay.com

# Token Security
SECRET_KEY=<generated-with-os.urandom(32).hex()>
```

---

## Rate Limiting & Security

### Rate Limiting Implementation

**File:** `GCRegisterAPI-10-26/api/middleware/rate_limiter.py`

```python
#!/usr/bin/env python
"""
🚦 Rate Limiting Middleware for GCRegisterAPI-10-26
Protects against brute-force and automated attacks
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask


def setup_rate_limiting(app: Flask) -> Limiter:
    """
    Setup rate limiting for Flask app

    Args:
        app: Flask application instance

    Returns:
        Limiter instance
    """
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://",  # Use Redis in production: "redis://localhost:6379"
        strategy="fixed-window"
    )

    return limiter


# Rate limit decorators for specific endpoints
def rate_limit_auth():
    """Rate limit for authentication endpoints"""
    return "5 per minute"


def rate_limit_email():
    """Rate limit for email-related endpoints"""
    return "3 per hour"


def rate_limit_password_reset():
    """Rate limit for password reset endpoints"""
    return "3 per hour per email"
```

### Rate Limiting Rules

| Endpoint | Limit | Window | Reason |
|----------|-------|--------|--------|
| `POST /auth/signup` | 5 | 15 min | Prevent account spam |
| `POST /auth/login` | 10 | 15 min | Prevent brute-force |
| `POST /auth/resend-verification` | 3 | 1 hour | Prevent email spam |
| `POST /auth/forgot-password` | 3 | 1 hour | Prevent email spam |
| `POST /auth/reset-password` | 5 | 15 min | Prevent brute-force |
| `GET /auth/verify-email` | 10 | 1 hour | Allow retries for expired links |

### User Enumeration Prevention

**Problem:** Attackers can determine if an email exists in the system by observing different responses.

**Solution:** Return identical responses for both existing and non-existing users.

```python
# ❌ BAD - Reveals user existence
@app.route('/auth/forgot-password', methods=['POST'])
def forgot_password_bad():
    email = request.json['email']
    user = get_user_by_email(email)

    if not user:
        return {'error': 'Email not found'}, 404  # ← Leaks information!

    send_reset_email(user)
    return {'message': 'Reset email sent'}, 200


# ✅ GOOD - Same response for all cases
@app.route('/auth/forgot-password', methods=['POST'])
def forgot_password_good():
    email = request.json['email']
    user = get_user_by_email(email)

    if user and user.is_active:
        send_reset_email(user)  # Only send if user exists

    # Same response regardless of user existence
    return {
        'success': True,
        'message': 'If an account with that email exists, a password reset link has been sent.'
    }, 200
```

### CAPTCHA Integration (Optional but Recommended)

**For production, integrate reCAPTCHA v3 or hCaptcha on:**
- Password reset request form
- Signup form (if experiencing bot signups)

```python
import requests

def verify_recaptcha(token: str, action: str) -> bool:
    """
    Verify reCAPTCHA v3 token

    Args:
        token: reCAPTCHA token from frontend
        action: Expected action name (e.g., 'password_reset')

    Returns:
        True if verification passed, False otherwise
    """
    secret_key = os.getenv('RECAPTCHA_SECRET_KEY')

    response = requests.post(
        'https://www.google.com/recaptcha/api/siteverify',
        data={
            'secret': secret_key,
            'response': token
        }
    )

    result = response.json()

    # Check if verification successful and score is good
    return (
        result.get('success', False) and
        result.get('action') == action and
        result.get('score', 0) >= 0.5  # Threshold: 0.5
    )
```

---

## Database Schema Updates

### Migration Plan

**No schema changes needed!** All fields already exist. We just need to start populating them.

### Indexing Strategy

Add indexes for performance on token lookups:

```sql
-- Create indexes for fast token lookups
CREATE INDEX IF NOT EXISTS idx_registered_users_verification_token
ON registered_users(verification_token)
WHERE verification_token IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_registered_users_reset_token
ON registered_users(reset_token)
WHERE reset_token IS NOT NULL;

-- Create index for email lookups (already exists from UNIQUE constraint)
-- No additional index needed for email field
```

### Token Cleanup Job

**Optional:** Schedule a job to clean up expired tokens

```sql
-- Clean up expired verification tokens
UPDATE registered_users
SET verification_token = NULL,
    verification_token_expires = NULL
WHERE verification_token IS NOT NULL
  AND verification_token_expires < NOW();

-- Clean up expired reset tokens
UPDATE registered_users
SET reset_token = NULL,
    reset_token_expires = NULL
WHERE reset_token IS NOT NULL
  AND reset_token_expires < NOW();
```

**Schedule:** Run daily via Cloud Scheduler

---

## API Endpoints Design

### New Endpoints to Implement

#### 1. **Resend Verification Email**
```
POST /auth/resend-verification
Content-Type: application/json

Request:
{
    "email": "john@example.com"
}

Response (200 OK):
{
    "success": true,
    "message": "If an account with that email exists and is unverified, a new verification email has been sent."
}

Errors:
- 429 Too Many Requests (rate limit exceeded)
```

#### 2. **Verify Email**
```
GET /auth/verify-email?token=<token>

Response (200 OK):
{
    "success": true,
    "message": "Email verified successfully! You can now log in.",
    "redirect_url": "/login"
}

Errors:
- 400 Bad Request (token expired or invalid)
- 404 Not Found (user not found)
```

#### 3. **Request Password Reset**
```
POST /auth/forgot-password
Content-Type: application/json

Request:
{
    "email": "john@example.com",
    "recaptcha_token": "<optional-recaptcha-token>"
}

Response (200 OK):
{
    "success": true,
    "message": "If an account with that email exists, a password reset link has been sent."
}

Errors:
- 429 Too Many Requests (rate limit exceeded)
```

#### 4. **Reset Password**
```
POST /auth/reset-password
Content-Type: application/json

Request:
{
    "token": "<reset-token>",
    "new_password": "NewSecurePass123!"
}

Response (200 OK):
{
    "success": true,
    "message": "Password has been reset successfully. Please log in with your new password."
}

Errors:
- 400 Bad Request (token expired, invalid, or password too weak)
```

### Modified Endpoints

#### **Signup** (Modified)
```
POST /auth/signup
Content-Type: application/json

Request:
{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123!"
}

Response (201 Created):
{
    "success": true,
    "message": "Account created. Please check your email to verify your account.",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "john@example.com",
    "email_verified": false,
    "verification_required": true
}

Changes:
- No access/refresh tokens returned until email verified
- verification_required flag added
- Verification email sent automatically
```

#### **Login** (Modified)
```
POST /auth/login
Content-Type: application/json

Request:
{
    "username": "johndoe",
    "password": "SecurePass123!"
}

Response (200 OK) - Email Verified:
{
    "success": true,
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "johndoe",
    "email": "john@example.com",
    "email_verified": true,
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "Bearer",
    "expires_in": 900
}

Response (403 Forbidden) - Email Not Verified:
{
    "success": false,
    "error": "Email not verified. Please check your email for the verification link.",
    "email_verified": false,
    "resend_verification_available": true
}

Changes:
- Check email_verified before issuing tokens
- Return 403 if email not verified
- Allow option to resend verification
```

---

## Frontend Integration Points

### Required Frontend Pages

#### 1. **Verify Email Success Page**
```
GET /verify-email?token=<token>

Shows:
- Success message
- "Go to Login" button
- Helpful next steps
```

#### 2. **Forgot Password Page**
```
GET /forgot-password

Form:
- Email input
- reCAPTCHA widget (optional)
- Submit button

Shows after submit:
- Generic success message
- "Check your email" instructions
```

#### 3. **Reset Password Page**
```
GET /reset-password?token=<token>

Form:
- New password input
- Confirm password input
- Password strength indicator
- Submit button

Validates:
- Token on page load
- Shows error if expired/invalid
- Redirects to login on success
```

### Frontend API Integration Examples

#### TypeScript/React Example
```typescript
// api/auth.ts

export const resendVerificationEmail = async (email: string) => {
  const response = await fetch(`${API_BASE_URL}/auth/resend-verification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });

  return await response.json();
};

export const verifyEmail = async (token: string) => {
  const response = await fetch(
    `${API_BASE_URL}/auth/verify-email?token=${token}`,
    { method: 'GET' }
  );

  return await response.json();
};

export const requestPasswordReset = async (email: string) => {
  const response = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });

  return await response.json();
};

export const resetPassword = async (token: string, newPassword: string) => {
  const response = await fetch(`${API_BASE_URL}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword })
  });

  return await response.json();
};
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1) 🔴 CRITICAL

**Tasks:**
1. ✅ Install dependencies
   ```bash
   pip install itsdangerous sendgrid flask-limiter
   ```
2. ✅ Create `token_service.py`
3. ✅ Create `email_service.py`
4. ✅ Setup environment variables
5. ✅ Create database indexes
6. ✅ Unit tests for token generation/validation

**Deliverables:**
- Working token generation/validation
- Email templates ready
- Dev mode email logging working

**Success Criteria:**
- Can generate and validate tokens
- Email templates render correctly
- All tests pass

---

### Phase 2: Email Verification (Week 1-2) 🟡 HIGH

**Tasks:**
1. ✅ Modify signup endpoint to generate verification tokens
2. ✅ Create `POST /auth/resend-verification` endpoint
3. ✅ Create `GET /auth/verify-email` endpoint
4. ✅ Modify login endpoint to check `email_verified`
5. ✅ Frontend: Verification success page
6. ✅ Frontend: Resend verification UI
7. ✅ Integration tests

**Deliverables:**
- Full email verification flow working
- Users must verify email before login
- Resend functionality working

**Success Criteria:**
- User receives verification email on signup
- Clicking link verifies email
- Can't login without verified email
- Can resend verification email

---

### Phase 3: Password Reset (Week 2) 🟡 HIGH

**Tasks:**
1. ✅ Create `POST /auth/forgot-password` endpoint
2. ✅ Create `POST /auth/reset-password` endpoint
3. ✅ Implement user enumeration protection
4. ✅ Implement session invalidation
5. ✅ Send confirmation email after reset
6. ✅ Frontend: Forgot password page
7. ✅ Frontend: Reset password page
8. ✅ Integration tests

**Deliverables:**
- Full password reset flow working
- Secure against enumeration attacks
- Sessions invalidated on reset

**Success Criteria:**
- User receives reset email
- Token works exactly once
- Password successfully reset
- Old sessions invalidated
- Confirmation email sent

---

### Phase 4: Rate Limiting & Security (Week 3) 🟢 MEDIUM

**Tasks:**
1. ✅ Setup Flask-Limiter with Redis (production)
2. ✅ Apply rate limits to all auth endpoints
3. ✅ Implement CAPTCHA on password reset (optional)
4. ✅ Add audit logging
5. ✅ Security penetration testing
6. ✅ Load testing

**Deliverables:**
- Rate limiting active on all endpoints
- CAPTCHA working (if implemented)
- Audit logs capture all events

**Success Criteria:**
- Rate limits prevent brute-force
- Logs show all auth events
- System handles 100 concurrent requests

---

### Phase 5: Monitoring & Cleanup (Week 3) 🟢 LOW

**Tasks:**
1. ✅ Setup Cloud Scheduler for token cleanup
2. ✅ Create monitoring dashboard
3. ✅ Setup alerting for failures
4. ✅ Documentation updates
5. ✅ Code review & refactoring

**Deliverables:**
- Automated token cleanup
- Monitoring in place
- Complete documentation

**Success Criteria:**
- Expired tokens cleaned daily
- Alerts fire on email failures
- Documentation complete

---

## Security Considerations

### Security Checklist

#### Token Security
- ✅ Tokens generated with `os.urandom()` (CSPRNG)
- ✅ Token length ≥ 32 bytes (256 bits)
- ✅ Tokens cryptographically signed (itsdangerous)
- ✅ Tokens include timestamp (automatic expiration)
- ✅ Tokens use unique salts per type
- ✅ Secret key stored in environment (never in code)
- ✅ Tokens are single-use (cleared after verification)
- ✅ Token expiration enforced (24h for email, 1h for reset)

#### User Enumeration Protection
- ✅ Consistent response times (consider adding artificial delay)
- ✅ Generic error messages (don't reveal user existence)
- ✅ Same response for existing/non-existing users
- ✅ No timing attacks possible

#### Email Security
- ✅ HTTPS-only links
- ✅ No sensitive data in email body
- ✅ From address verified (SPF, DKIM, DMARC)
- ✅ Professional email templates
- ✅ Clear expiration warnings

#### Rate Limiting
- ✅ Per-endpoint limits configured
- ✅ Per-IP limits enforced
- ✅ Per-user limits enforced
- ✅ CAPTCHA on high-risk endpoints

#### Session Management
- ✅ Sessions invalidated on password reset
- ✅ Old sessions killed after reset
- ✅ Logout all devices option available

#### Audit Logging
- ✅ All verification attempts logged
- ✅ All reset attempts logged
- ✅ Failed attempts logged
- ✅ Successful operations logged
- ✅ Log retention policy defined

### OWASP Top 10 Compliance

| OWASP Item | Status | Implementation |
|------------|--------|----------------|
| A01:2021 - Broken Access Control | ✅ Mitigated | Email verification required before access |
| A02:2021 - Cryptographic Failures | ✅ Mitigated | Secure token generation, bcrypt for passwords |
| A03:2021 - Injection | ✅ Mitigated | Parameterized SQL queries |
| A04:2021 - Insecure Design | ✅ Mitigated | Following OWASP design patterns |
| A05:2021 - Security Misconfiguration | ✅ Mitigated | Secure defaults, environment-based config |
| A06:2021 - Vulnerable Components | ✅ Mitigated | Using well-maintained libraries |
| A07:2021 - Identification & Auth Failures | ✅ Mitigated | This entire architecture! |
| A08:2021 - Software & Data Integrity | ✅ Mitigated | Signed tokens prevent tampering |
| A09:2021 - Logging Failures | ✅ Mitigated | Comprehensive audit logging |
| A10:2021 - SSRF | N/A | Not applicable |

---

## Testing Strategy

### Unit Tests

**File:** `GCRegisterAPI-10-26/tests/test_token_service.py`

```python
import pytest
from api.services.token_service import TokenService
from itsdangerous import SignatureExpired, BadSignature
import time


def test_generate_email_verification_token():
    """Test email verification token generation"""
    service = TokenService()
    token = service.generate_email_verification_token(
        user_id='550e8400-e29b-41d4-a716-446655440000',
        email='test@example.com'
    )

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 50  # Tokens should be reasonably long


def test_verify_email_verification_token():
    """Test email verification token validation"""
    service = TokenService()

    token = service.generate_email_verification_token(
        user_id='550e8400-e29b-41d4-a716-446655440000',
        email='test@example.com'
    )

    data = service.verify_email_verification_token(token)

    assert data['user_id'] == '550e8400-e29b-41d4-a716-446655440000'
    assert data['email'] == 'test@example.com'


def test_expired_token():
    """Test that expired tokens are rejected"""
    service = TokenService()
    service.EMAIL_VERIFICATION_MAX_AGE = 1  # 1 second

    token = service.generate_email_verification_token(
        user_id='550e8400-e29b-41d4-a716-446655440000',
        email='test@example.com'
    )

    time.sleep(2)  # Wait for expiration

    with pytest.raises(SignatureExpired):
        service.verify_email_verification_token(token)


def test_tampered_token():
    """Test that tampered tokens are rejected"""
    service = TokenService()

    token = service.generate_email_verification_token(
        user_id='550e8400-e29b-41d4-a716-446655440000',
        email='test@example.com'
    )

    # Tamper with token
    tampered_token = token[:-5] + 'XXXXX'

    with pytest.raises(BadSignature):
        service.verify_email_verification_token(tampered_token)


def test_password_reset_token():
    """Test password reset token generation and validation"""
    service = TokenService()

    token = service.generate_password_reset_token(
        user_id='550e8400-e29b-41d4-a716-446655440000',
        email='test@example.com'
    )

    data = service.verify_password_reset_token(token)

    assert data['user_id'] == '550e8400-e29b-41d4-a716-446655440000'
    assert data['email'] == 'test@example.com'
```

### Integration Tests

**File:** `GCRegisterAPI-10-26/tests/test_auth_flow.py`

```python
import pytest
from app import create_app


@pytest.fixture
def client():
    """Create test client"""
    app = create_app(testing=True)
    with app.test_client() as client:
        yield client


def test_signup_sends_verification_email(client):
    """Test that signup sends verification email"""
    response = client.post('/auth/signup', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'SecurePass123!'
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data['verification_required'] is True
    assert 'access_token' not in data  # No token until verified


def test_login_requires_verified_email(client):
    """Test that login fails for unverified email"""
    # Create user (unverified)
    client.post('/auth/signup', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'SecurePass123!'
    })

    # Try to login
    response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'SecurePass123!'
    })

    assert response.status_code == 403
    data = response.get_json()
    assert 'Email not verified' in data['error']


def test_email_verification_flow(client):
    """Test complete email verification flow"""
    # Signup
    signup_response = client.post('/auth/signup', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'SecurePass123!'
    })

    # Get verification token from email (mocked)
    token = get_verification_token_from_email()

    # Verify email
    verify_response = client.get(f'/auth/verify-email?token={token}')
    assert verify_response.status_code == 200

    # Now login should work
    login_response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'SecurePass123!'
    })

    assert login_response.status_code == 200
    data = login_response.get_json()
    assert 'access_token' in data


def test_password_reset_flow(client):
    """Test complete password reset flow"""
    # Create verified user
    create_verified_user('testuser', 'test@example.com', 'OldPass123!')

    # Request reset
    reset_request = client.post('/auth/forgot-password', json={
        'email': 'test@example.com'
    })
    assert reset_request.status_code == 200

    # Get reset token from email (mocked)
    token = get_reset_token_from_email()

    # Reset password
    reset_response = client.post('/auth/reset-password', json={
        'token': token,
        'new_password': 'NewPass123!'
    })
    assert reset_response.status_code == 200

    # Login with new password
    login_response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'NewPass123!'
    })
    assert login_response.status_code == 200

    # Old password should fail
    old_login = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'OldPass123!'
    })
    assert old_login.status_code == 401
```

### Security Tests

```python
def test_rate_limiting(client):
    """Test that rate limiting works"""
    for _ in range(6):
        response = client.post('/auth/forgot-password', json={
            'email': 'test@example.com'
        })

    # 6th request should be rate limited
    assert response.status_code == 429


def test_user_enumeration_protection(client):
    """Test that responses don't reveal user existence"""
    # Request reset for existing user
    response1 = client.post('/auth/forgot-password', json={
        'email': 'existing@example.com'
    })

    # Request reset for non-existing user
    response2 = client.post('/auth/forgot-password', json={
        'email': 'nonexisting@example.com'
    })

    # Responses should be identical
    assert response1.status_code == response2.status_code
    assert response1.get_json()['message'] == response2.get_json()['message']


def test_token_single_use(client):
    """Test that tokens can only be used once"""
    token = create_reset_token('test@example.com')

    # First use - should work
    response1 = client.post('/auth/reset-password', json={
        'token': token,
        'new_password': 'NewPass123!'
    })
    assert response1.status_code == 200

    # Second use - should fail
    response2 = client.post('/auth/reset-password', json={
        'token': token,
        'new_password': 'AnotherPass123!'
    })
    assert response2.status_code == 400
```

---

## Monitoring & Logging

### Logging Strategy

**File:** `GCRegisterAPI-10-26/api/utils/audit_logger.py`

```python
#!/usr/bin/env python
"""
📊 Audit Logger for Authentication Events
Logs all security-relevant events for monitoring and compliance
"""
import logging
from datetime import datetime
from typing import Optional


class AuditLogger:
    """Handles audit logging for authentication events"""

    def __init__(self):
        """Initialize audit logger"""
        self.logger = logging.getLogger('audit')
        self.logger.setLevel(logging.INFO)

    def log_email_verification_sent(self, user_id: str, email: str):
        """Log verification email sent"""
        self.logger.info(
            f"📧 Verification email sent | "
            f"user_id={user_id} | email={email} | "
            f"timestamp={datetime.utcnow().isoformat()}"
        )

    def log_email_verified(self, user_id: str, email: str):
        """Log successful email verification"""
        self.logger.info(
            f"✅ Email verified | "
            f"user_id={user_id} | email={email} | "
            f"timestamp={datetime.utcnow().isoformat()}"
        )

    def log_email_verification_failed(
        self,
        email: Optional[str],
        reason: str,
        token_excerpt: str
    ):
        """Log failed email verification"""
        self.logger.warning(
            f"❌ Email verification failed | "
            f"email={email or 'unknown'} | reason={reason} | "
            f"token={token_excerpt[:20]}... | "
            f"timestamp={datetime.utcnow().isoformat()}"
        )

    def log_password_reset_requested(self, email: str, user_found: bool):
        """Log password reset request"""
        self.logger.info(
            f"🔐 Password reset requested | "
            f"email={email} | user_found={user_found} | "
            f"timestamp={datetime.utcnow().isoformat()}"
        )

    def log_password_reset_completed(self, user_id: str, email: str):
        """Log successful password reset"""
        self.logger.warning(
            f"✅ Password reset completed | "
            f"user_id={user_id} | email={email} | "
            f"timestamp={datetime.utcnow().isoformat()}"
        )

    def log_password_reset_failed(
        self,
        email: Optional[str],
        reason: str,
        token_excerpt: str
    ):
        """Log failed password reset"""
        self.logger.warning(
            f"❌ Password reset failed | "
            f"email={email or 'unknown'} | reason={reason} | "
            f"token={token_excerpt[:20]}... | "
            f"timestamp={datetime.utcnow().isoformat()}"
        )

    def log_rate_limit_exceeded(
        self,
        endpoint: str,
        ip_address: str,
        user_identifier: Optional[str]
    ):
        """Log rate limit exceeded"""
        self.logger.warning(
            f"🚦 Rate limit exceeded | "
            f"endpoint={endpoint} | ip={ip_address} | "
            f"user={user_identifier or 'unknown'} | "
            f"timestamp={datetime.utcnow().isoformat()}"
        )
```

### Metrics to Monitor

| Metric | Alert Threshold | Action |
|--------|----------------|--------|
| **Email delivery failures** | > 5% failure rate | Check SendGrid status |
| **Token validation failures** | > 10 per hour | Investigate potential attack |
| **Rate limit hits** | > 20 per hour | Check for bot activity |
| **Password resets** | > 50 per day | Monitor for account takeover attempts |
| **Unverified accounts** | > 100 pending > 7 days | Consider cleanup |

### Cloud Logging Queries

**GCP Cloud Logging queries for monitoring:**

```sql
-- Failed email verifications
resource.type="cloud_run_revision"
severity="WARNING"
jsonPayload.message=~"Email verification failed"

-- Password reset requests
resource.type="cloud_run_revision"
jsonPayload.message=~"Password reset requested"

-- Rate limit exceeded
resource.type="cloud_run_revision"
severity="WARNING"
jsonPayload.message=~"Rate limit exceeded"

-- Successful verifications
resource.type="cloud_run_revision"
jsonPayload.message=~"Email verified"
```

---

## Conclusion

This architecture provides a **production-ready, secure, and OWASP-compliant** implementation of email verification and password reset functionality. It balances security, user experience, and operational simplicity.

### Key Strengths
✅ **Security-First:** Follows OWASP best practices
✅ **User-Friendly:** Clear flows and helpful error messages
✅ **Scalable:** Rate limiting and efficient token management
✅ **Maintainable:** Clean code structure and comprehensive tests
✅ **Observable:** Full audit logging and monitoring

### Next Steps
1. Review this architecture with the team
2. Get approval for implementation approach
3. Setup development environment with test email service
4. Begin Phase 1 implementation
5. Test thoroughly before production deployment

---

**Document Version:** 1.0
**Last Updated:** 2025-11-09
**Status:** ✅ **READY FOR REVIEW**

---

## Appendix: Quick Reference

### Token Expiration Times
- **Email Verification:** 24 hours (86400 seconds)
- **Password Reset:** 1 hour (3600 seconds)

### Rate Limits
- **Signup:** 5 per 15 minutes
- **Login:** 10 per 15 minutes
- **Resend Verification:** 3 per hour
- **Forgot Password:** 3 per hour
- **Reset Password:** 5 per 15 minutes

### Environment Variables Required
```bash
SECRET_KEY=<generated-with-os.urandom(32).hex()>
SENDGRID_API_KEY=SG.xxx
FROM_EMAIL=noreply@telepay.com
FROM_NAME=TelePay
BASE_URL=https://app.telepay.com
```

### Dependencies to Install
```bash
pip install itsdangerous sendgrid flask-limiter redis
```

---

**END OF DOCUMENT**
