# Email Verification & Account Management Architecture

**Document Version:** 1.0
**Date:** 2025-11-09
**Status:** Design - Ready for Implementation

---

## Executive Summary

This document outlines a comprehensive, secure, and user-friendly architecture for email verification and account management in the GCRegister system. The design shifts from mandatory pre-login email verification to a post-login "soft verification" approach, allowing immediate access while encouraging verification through strategic UI prompts.

### Key Changes

1. **Immediate Login After Signup**: Users automatically logged in upon account creation
2. **Full Feature Access**: Unverified users can use all features without restriction
3. **Visual Verification Prompts**: Clear UI indicators showing verification status
4. **Secure Account Management**: Email and password changes only for verified accounts
5. **OWASP-Compliant Security**: Following industry best practices for all sensitive operations

---

## Table of Contents

1. [Current State vs Desired State](#current-state-vs-desired-state)
2. [System Architecture Overview](#system-architecture-overview)
3. [Database Schema](#database-schema)
4. [Backend API Specifications](#backend-api-specifications)
5. [Frontend Components](#frontend-components)
6. [Security Architecture](#security-architecture)
7. [User Flow Diagrams](#user-flow-diagrams)
8. [Implementation Roadmap](#implementation-roadmap)
9. [Testing Strategy](#testing-strategy)
10. [Migration Path](#migration-path)

---

## Current State vs Desired State

### Current Implementation

```
┌──────────┐     ┌────────────────┐     ┌──────────────┐
│  Signup  │────▶│ Email Sent     │────▶│ Verify Email │
│          │     │ (no login)     │     │              │
└──────────┘     └────────────────┘     └──────┬───────┘
                                               │
                                               ▼
                                         ┌──────────┐
                                         │  Login   │
                                         │ Allowed  │
                                         └──────────┘
```

**Issues:**
- Users cannot login until email verified
- High friction at onboarding
- Lower conversion rates
- Frustrating user experience for quick access needs

### Desired Implementation

```
┌──────────┐     ┌────────────────────────┐
│  Signup  │────▶│ Auto-Login + Dashboard │
│          │     │   (full access)        │
└──────────┘     └───────────┬────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
        ┌────────────────┐      ┌─────────────────┐
        │ "Verify Email" │      │ "Verified" ✓    │
        │  (yellow btn)  │─────▶│  (green btn)    │
        └────────────────┘      └────────┬────────┘
                │                        │
                │                        ▼
                │               ┌──────────────────┐
                │               │ Change Email     │
                │               │ Change Password  │
                └───────────────┤ (only verified)  │
                                └──────────────────┘
```

**Benefits:**
- Zero friction onboarding
- Immediate feature access
- Natural verification flow
- Higher user retention
- OWASP-compliant security

---

## System Architecture Overview

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐   │
│  │ Signup   │  │ Dashboard  │  │ Verification Status  │   │
│  │ Page     │  │ (Header)   │  │ Page                 │   │
│  └──────────┘  └────────────┘  └──────────────────────┘   │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────┐
│                     API LAYER (Flask)                        │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ /signup      │  │ /login      │  │ /verification/*  │  │
│  │ /refresh     │  │ /me         │  │ /account/*       │  │
│  └──────────────┘  └─────────────┘  └──────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────┐
│                   SERVICE LAYER                              │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ AuthService  │  │ TokenService│  │ EmailService     │  │
│  │ - signup     │  │ - generate  │  │ - send_verify    │  │
│  │ - login      │  │ - verify    │  │ - send_change    │  │
│  │ - verify     │  │ - refresh   │  │ - send_confirm   │  │
│  └──────────────┘  └─────────────┘  └──────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────┐
│                   DATA LAYER (PostgreSQL)                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │ registered_users                                   │    │
│  │ - user_id (PK)                                     │    │
│  │ - username (UNIQUE)                                │    │
│  │ - email (UNIQUE)                                   │    │
│  │ - password_hash                                    │    │
│  │ - email_verified (BOOLEAN)                         │    │
│  │ - verification_token, verification_token_expires   │    │
│  │ - pending_email, pending_email_token (NEW)         │    │
│  │ - last_verification_resent_at (NEW)                │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Existing Table: `registered_users`

**Current Columns:**
```sql
user_id                      UUID PRIMARY KEY DEFAULT gen_random_uuid()
username                     VARCHAR(50) UNIQUE NOT NULL
email                        VARCHAR(255) UNIQUE NOT NULL
password_hash                VARCHAR(255) NOT NULL
is_active                    BOOLEAN DEFAULT TRUE
email_verified               BOOLEAN DEFAULT FALSE
verification_token           VARCHAR(500)
verification_token_expires   TIMESTAMP
reset_token                  VARCHAR(500)
reset_token_expires          TIMESTAMP
created_at                   TIMESTAMP DEFAULT NOW()
updated_at                   TIMESTAMP DEFAULT NOW()
last_login                   TIMESTAMP
```

### Required Schema Changes

```sql
-- Migration: Add Email Change Support
-- File: database/migrations/002_add_email_change_support.sql

BEGIN;

-- Add columns for pending email changes
ALTER TABLE registered_users
ADD COLUMN pending_email VARCHAR(255),
ADD COLUMN pending_email_token VARCHAR(500),
ADD COLUMN pending_email_token_expires TIMESTAMP,
ADD COLUMN pending_email_old_notification_sent BOOLEAN DEFAULT FALSE;

-- Add rate limiting for verification email resends
ALTER TABLE registered_users
ADD COLUMN last_verification_resent_at TIMESTAMP,
ADD COLUMN verification_resend_count INTEGER DEFAULT 0;

-- Add tracking for email change requests
ALTER TABLE registered_users
ADD COLUMN last_email_change_requested_at TIMESTAMP;

-- Create index for pending_email lookups (prevent duplicate pending emails)
CREATE INDEX idx_pending_email ON registered_users(pending_email)
WHERE pending_email IS NOT NULL;

-- Create index for token expiration cleanup
CREATE INDEX idx_verification_token_expires ON registered_users(verification_token_expires)
WHERE verification_token_expires IS NOT NULL;

CREATE INDEX idx_pending_email_token_expires ON registered_users(pending_email_token_expires)
WHERE pending_email_token_expires IS NOT NULL;

COMMIT;
```

### Database Constraints & Validation Rules

```sql
-- Ensure pending_email is different from current email
ALTER TABLE registered_users
ADD CONSTRAINT check_pending_email_different
CHECK (pending_email IS NULL OR pending_email != email);

-- Ensure pending_email is unique (no two users can have same pending email)
CREATE UNIQUE INDEX idx_unique_pending_email
ON registered_users(pending_email)
WHERE pending_email IS NOT NULL;
```

---

## Backend API Specifications

### 1. Modified `/signup` Endpoint

**Current Behavior:** Returns user info WITHOUT tokens (verification required)
**New Behavior:** Returns user info WITH tokens (auto-login)

#### Request
```http
POST /auth/signup
Content-Type: application/json

{
  "username": "newuser123",
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

#### Response (200 Created)
```json
{
  "success": true,
  "message": "Account created successfully. Please verify your email.",
  "user_id": "uuid-here",
  "username": "newuser123",
  "email": "user@example.com",
  "email_verified": false,
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

#### Implementation Changes
```python
# api/routes/auth.py (signup endpoint)

@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    User signup endpoint - AUTO LOGIN
    Rate Limited: 5 per 15 minutes
    """
    client_ip = request.remote_addr

    try:
        signup_data = SignupRequest(**request.json)

        with db_manager.get_db() as conn:
            user = AuthService.create_user(
                conn,
                username=signup_data.username,
                email=signup_data.email,
                password=signup_data.password
            )

        # Send verification email (non-blocking)
        email_service = EmailService()
        email_sent = email_service.send_verification_email(
            to_email=user['email'],
            username=user['username'],
            token=user['verification_token']
        )

        # CREATE TOKENS (NEW BEHAVIOR)
        tokens = AuthService.create_tokens(user['user_id'], user['username'])

        # Audit logging
        AuditLogger.log_signup_attempt(
            username=signup_data.username,
            email=user['email'],
            success=True,
            ip=client_ip
        )

        AuditLogger.log_email_verification_sent(
            user_id=user['user_id'],
            email=user['email']
        )

        # Return response WITH TOKENS
        response = {
            'success': True,
            'message': 'Account created successfully. Please verify your email.',
            'user_id': user['user_id'],
            'username': user['username'],
            'email': user['email'],
            'email_verified': False,
            **tokens  # Include access_token, refresh_token, etc.
        }

        print(f"✅ User '{signup_data.username}' signed up and auto-logged in")
        return jsonify(response), 201

    except ValidationError as e:
        # ... existing error handling
    except ValueError as e:
        # ... existing error handling
```

---

### 2. Modified `/login` Endpoint

**Current Behavior:** Rejects login if email not verified
**New Behavior:** Allows login regardless of verification status

#### Implementation Changes
```python
# api/services/auth_service.py

@staticmethod
def authenticate_user(conn, username: str, password: str) -> dict:
    """
    Authenticate a user (ALLOWS UNVERIFIED EMAILS)

    Returns:
        User data dict if authentication successful

    Raises:
        ValueError: If authentication fails
    """
    try:
        cursor = conn.cursor()

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

        # REMOVED: Email verification check
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
            'email_verified': email_verified  # Include status in response
        }

    except Exception as e:
        print(f"❌ Error authenticating user: {e}")
        raise
```

---

### 3. New `/me` Endpoint Enhancement

Add `email_verified` status to user info response.

#### Response
```json
{
  "user_id": "uuid-here",
  "username": "newuser123",
  "email": "user@example.com",
  "email_verified": false,
  "created_at": "2025-11-09T10:30:00Z",
  "last_login": "2025-11-09T10:30:00Z"
}
```

#### Implementation
```python
# api/routes/auth.py

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user info with verification status"""
    try:
        user_id = get_jwt_identity()

        with db_manager.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, email, email_verified, created_at, last_login
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            cursor.close()

            if not row:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            user = {
                'user_id': str(row[0]),
                'username': row[1],
                'email': row[2],
                'email_verified': row[3],  # NEW
                'created_at': row[4].isoformat() if row[4] else None,
                'last_login': row[5].isoformat() if row[5] else None
            }

        return jsonify(user), 200

    except Exception as e:
        print(f"❌ Get current user error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

---

### 4. New `/verification/status` Endpoint

Get detailed verification status for the current user.

#### Request
```http
GET /auth/verification/status
Authorization: Bearer {access_token}
```

#### Response
```json
{
  "email_verified": false,
  "email": "user@example.com",
  "verification_token_expires": "2025-11-10T10:30:00Z",
  "can_resend": true,
  "last_resent_at": null,
  "resend_count": 0
}
```

#### Implementation
```python
# api/routes/auth.py

@auth_bp.route('/verification/status', methods=['GET'])
@jwt_required()
def verification_status():
    """
    Get email verification status for current user

    Returns detailed verification info including resend capabilities
    """
    try:
        user_id = get_jwt_identity()

        with db_manager.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email_verified, email, verification_token_expires,
                       last_verification_resent_at, verification_resend_count
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            cursor.close()

            if not row:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            email_verified, email, token_expires, last_resent, resend_count = row

            # Determine if user can resend (rate limiting: max 1 per 5 minutes)
            can_resend = True
            if last_resent:
                time_since_resend = datetime.utcnow() - last_resent
                can_resend = time_since_resend.total_seconds() > 300  # 5 minutes

            status = {
                'email_verified': email_verified,
                'email': email,
                'verification_token_expires': token_expires.isoformat() if token_expires else None,
                'can_resend': can_resend and not email_verified,
                'last_resent_at': last_resent.isoformat() if last_resent else None,
                'resend_count': resend_count or 0
            }

        return jsonify(status), 200

    except Exception as e:
        print(f"❌ Verification status error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

---

### 5. Modified `/resend-verification` Endpoint

**Current Behavior:** Public endpoint, accepts email
**New Behavior:** Protected endpoint, uses authenticated user

#### Request
```http
POST /auth/verification/resend
Authorization: Bearer {access_token}
```

#### Response
```json
{
  "success": true,
  "message": "Verification email sent successfully",
  "can_resend_at": "2025-11-09T10:35:00Z"
}
```

#### Implementation
```python
# api/routes/auth.py

@auth_bp.route('/verification/resend', methods=['POST'])
@jwt_required()
def resend_verification():
    """
    Resend verification email to authenticated user
    Rate Limited: 1 per 5 minutes per user
    """
    try:
        user_id = get_jwt_identity()
        client_ip = request.remote_addr

        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Get user info and check rate limits
            cursor.execute("""
                SELECT username, email, email_verified,
                       last_verification_resent_at, verification_resend_count
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            username, email, email_verified, last_resent, resend_count = row

            # Check if already verified
            if email_verified:
                return jsonify({
                    'success': False,
                    'error': 'Email already verified'
                }), 400

            # Rate limiting check
            if last_resent:
                time_since_resend = datetime.utcnow() - last_resent
                if time_since_resend.total_seconds() < 300:  # 5 minutes
                    wait_seconds = 300 - int(time_since_resend.total_seconds())
                    return jsonify({
                        'success': False,
                        'error': f'Please wait {wait_seconds} seconds before resending',
                        'retry_after': wait_seconds
                    }), 429

            # Generate new verification token
            token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
            verification_token = token_service.generate_email_verification_token(user_id, email)
            token_expires = TokenService.get_expiration_datetime('email_verification')

            # Update database
            cursor.execute("""
                UPDATE registered_users
                SET verification_token = %s,
                    verification_token_expires = %s,
                    last_verification_resent_at = NOW(),
                    verification_resend_count = COALESCE(verification_resend_count, 0) + 1,
                    updated_at = NOW()
                WHERE user_id = %s
            """, (verification_token, token_expires, user_id))

            cursor.close()

        # Send verification email
        email_service = EmailService()
        email_sent = email_service.send_verification_email(
            to_email=email,
            username=username,
            token=verification_token
        )

        if not email_sent:
            return jsonify({
                'success': False,
                'error': 'Failed to send email'
            }), 500

        # Audit log
        AuditLogger.log_verification_resent(
            email=email,
            user_found=True,
            ip=client_ip
        )

        can_resend_at = datetime.utcnow() + timedelta(minutes=5)

        print(f"✅ Verification email resent to {email}")
        return jsonify({
            'success': True,
            'message': 'Verification email sent successfully',
            'can_resend_at': can_resend_at.isoformat()
        }), 200

    except Exception as e:
        print(f"❌ Resend verification error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

---

### 6. New `/account/change-email` Endpoint

**Security:** Requires verified account + password confirmation
**Flow:** Dual verification (old email notification + new email confirmation)

#### Request
```http
POST /auth/account/change-email
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "new_email": "newemail@example.com",
  "password": "current_password"
}
```

#### Response
```json
{
  "success": true,
  "message": "Confirmation email sent to new address",
  "pending_email": "newemail@example.com",
  "notification_sent_to_old": true
}
```

#### Implementation
```python
# api/routes/auth.py

@auth_bp.route('/account/change-email', methods=['POST'])
@jwt_required()
def request_email_change():
    """
    Request email change (VERIFIED ACCOUNTS ONLY)

    Security Flow (OWASP-compliant):
    1. Verify user is authenticated (JWT)
    2. Verify email is already verified
    3. Verify current password
    4. Check new email isn't in use
    5. Generate token for new email
    6. Send notification to OLD email
    7. Send confirmation to NEW email

    Rate Limited: 3 per hour
    """
    try:
        user_id = get_jwt_identity()

        # Validate request
        data = request.json
        new_email = data.get('new_email')
        password = data.get('password')

        if not new_email or not password:
            return jsonify({
                'success': False,
                'error': 'New email and password required'
            }), 400

        # Validate email format
        try:
            EmailStr.validate(new_email)
        except:
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400

        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Get user info
            cursor.execute("""
                SELECT username, email, password_hash, email_verified
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            username, current_email, password_hash, email_verified = row

            # SECURITY CHECK 1: Email must be verified
            if not email_verified:
                return jsonify({
                    'success': False,
                    'error': 'Email must be verified before changing',
                    'requires_verification': True
                }), 403

            # SECURITY CHECK 2: Verify password
            if not AuthService.verify_password(password, password_hash):
                AuditLogger.log_email_change_failed(
                    user_id=user_id,
                    reason='Invalid password'
                )
                return jsonify({
                    'success': False,
                    'error': 'Invalid password'
                }), 401

            # SECURITY CHECK 3: New email must be different
            if new_email.lower() == current_email.lower():
                return jsonify({
                    'success': False,
                    'error': 'New email must be different from current email'
                }), 400

            # SECURITY CHECK 4: New email not in use
            cursor.execute("""
                SELECT user_id FROM registered_users
                WHERE email = %s OR pending_email = %s
            """, (new_email, new_email))

            if cursor.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'Email already in use'
                }), 400

            # Generate token for new email
            token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
            email_change_token = token_service.generate_email_change_token(user_id, new_email)
            token_expires = TokenService.get_expiration_datetime('email_change')

            # Store pending email change
            cursor.execute("""
                UPDATE registered_users
                SET pending_email = %s,
                    pending_email_token = %s,
                    pending_email_token_expires = %s,
                    pending_email_old_notification_sent = FALSE,
                    last_email_change_requested_at = NOW(),
                    updated_at = NOW()
                WHERE user_id = %s
            """, (new_email, email_change_token, token_expires, user_id))

            cursor.close()

        # Send notification to OLD email
        email_service = EmailService()
        old_notification_sent = email_service.send_email_change_notification(
            to_email=current_email,
            username=username,
            new_email=new_email
        )

        # Send confirmation to NEW email
        new_confirmation_sent = email_service.send_email_change_confirmation(
            to_email=new_email,
            username=username,
            token=email_change_token
        )

        # Update notification status
        if old_notification_sent:
            with db_manager.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE registered_users
                    SET pending_email_old_notification_sent = TRUE
                    WHERE user_id = %s
                """, (user_id,))
                cursor.close()

        # Audit log
        AuditLogger.log_email_change_requested(
            user_id=user_id,
            old_email=current_email,
            new_email=new_email
        )

        print(f"📧 Email change requested: {current_email} → {new_email}")

        return jsonify({
            'success': True,
            'message': 'Confirmation email sent to new address. Please check both email addresses.',
            'pending_email': new_email,
            'notification_sent_to_old': old_notification_sent,
            'confirmation_sent_to_new': new_confirmation_sent
        }), 200

    except Exception as e:
        print(f"❌ Email change request error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

---

### 7. New `/account/confirm-email-change` Endpoint

Confirms email change using token from email link.

#### Request
```http
GET /auth/account/confirm-email-change?token={token}
```

#### Response
```json
{
  "success": true,
  "message": "Email changed successfully",
  "new_email": "newemail@example.com"
}
```

#### Implementation
```python
# api/routes/auth.py

@auth_bp.route('/account/confirm-email-change', methods=['GET'])
def confirm_email_change():
    """
    Confirm email change using token from confirmation email

    Security:
    - Verifies token signature and expiration
    - Checks token matches database
    - Prevents race conditions
    """
    try:
        token = request.args.get('token')

        if not token:
            return jsonify({
                'success': False,
                'error': 'Token required'
            }), 400

        # Verify token
        token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
        token_data = token_service.verify_email_change_token(token)

        user_id = token_data['user_id']
        new_email = token_data['new_email']

        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Get user and verify token matches
            cursor.execute("""
                SELECT username, email, pending_email, pending_email_token,
                       pending_email_token_expires
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            username, current_email, pending_email, db_token, token_expires = row

            # Verify token matches database
            if db_token != token:
                return jsonify({'success': False, 'error': 'Invalid token'}), 400

            # Check expiration
            if token_expires and token_expires < datetime.utcnow():
                return jsonify({'success': False, 'error': 'Token expired'}), 400

            # Verify pending email matches token
            if pending_email != new_email:
                return jsonify({'success': False, 'error': 'Email mismatch'}), 400

            # Check if new email is now taken (race condition check)
            cursor.execute("""
                SELECT user_id FROM registered_users
                WHERE email = %s AND user_id != %s
            """, (new_email, user_id))

            if cursor.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'Email no longer available'
                }), 400

            # Update email
            cursor.execute("""
                UPDATE registered_users
                SET email = %s,
                    pending_email = NULL,
                    pending_email_token = NULL,
                    pending_email_token_expires = NULL,
                    pending_email_old_notification_sent = FALSE,
                    updated_at = NOW()
                WHERE user_id = %s
            """, (new_email, user_id))

            cursor.close()

        # Send confirmation email to new address
        email_service = EmailService()
        email_service.send_email_changed_confirmation(
            to_email=new_email,
            username=username
        )

        # Audit log
        AuditLogger.log_email_changed(
            user_id=user_id,
            old_email=current_email,
            new_email=new_email
        )

        print(f"✅ Email changed: {current_email} → {new_email}")

        return jsonify({
            'success': True,
            'message': 'Email changed successfully',
            'new_email': new_email,
            'redirect_url': '/dashboard'
        }), 200

    except SignatureExpired:
        return jsonify({
            'success': False,
            'error': 'Token expired. Please request a new email change.'
        }), 400
    except BadSignature:
        return jsonify({
            'success': False,
            'error': 'Invalid token.'
        }), 400
    except Exception as e:
        print(f"❌ Email change confirmation error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

---

### 8. New `/account/cancel-email-change` Endpoint

Cancels pending email change (accessible from old email notification).

#### Request
```http
POST /auth/account/cancel-email-change
Authorization: Bearer {access_token}
```

#### Response
```json
{
  "success": true,
  "message": "Email change cancelled"
}
```

---

### 9. New `/account/change-password` Endpoint

**Security:** Requires verified account + current password

#### Request
```http
POST /auth/account/change-password
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "current_password": "OldPass123",
  "new_password": "NewSecurePass456"
}
```

#### Response
```json
{
  "success": true,
  "message": "Password changed successfully"
}
```

#### Implementation
```python
# api/routes/auth.py

@auth_bp.route('/account/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Change password (VERIFIED ACCOUNTS ONLY)

    Security:
    - Requires email verification
    - Requires current password
    - Validates new password strength
    - Sends confirmation email

    Rate Limited: 5 per 15 minutes
    """
    try:
        user_id = get_jwt_identity()

        # Validate request
        data = request.json
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({
                'success': False,
                'error': 'Current and new password required'
            }), 400

        # Validate new password strength
        try:
            # Reuse signup password validation
            from api.models.auth import ResetPasswordRequest
            ResetPasswordRequest.validate_new_password(ResetPasswordRequest, new_password)
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400

        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Get user info
            cursor.execute("""
                SELECT username, email, password_hash, email_verified
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            username, email, password_hash, email_verified = row

            # SECURITY CHECK 1: Email must be verified
            if not email_verified:
                return jsonify({
                    'success': False,
                    'error': 'Email must be verified before changing password',
                    'requires_verification': True
                }), 403

            # SECURITY CHECK 2: Verify current password
            if not AuthService.verify_password(current_password, password_hash):
                AuditLogger.log_password_change_failed(
                    user_id=user_id,
                    reason='Invalid current password'
                )
                return jsonify({
                    'success': False,
                    'error': 'Current password is incorrect'
                }), 401

            # SECURITY CHECK 3: New password must be different
            if current_password == new_password:
                return jsonify({
                    'success': False,
                    'error': 'New password must be different from current password'
                }), 400

            # Hash new password
            new_password_hash = AuthService.hash_password(new_password)

            # Update password
            cursor.execute("""
                UPDATE registered_users
                SET password_hash = %s,
                    updated_at = NOW()
                WHERE user_id = %s
            """, (new_password_hash, user_id))

            cursor.close()

        # Send confirmation email
        email_service = EmailService()
        email_service.send_password_changed_confirmation(
            to_email=email,
            username=username
        )

        # Audit log
        AuditLogger.log_password_changed(
            user_id=user_id,
            email=email
        )

        print(f"🔐 Password changed for user {user_id}")

        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        }), 200

    except Exception as e:
        print(f"❌ Password change error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

---

## Frontend Components

### 1. Modified SignupPage Component

**Changes:** Handle tokens in signup response, auto-navigate to dashboard

```typescript
// src/pages/SignupPage.tsx

import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authService } from '../services/authService';

export default function SignupPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Signup returns tokens now
      const response = await authService.signup(formData);

      // Store tokens (authService handles this)
      // Auto-navigate to dashboard
      navigate('/dashboard');

    } catch (err: any) {
      setError(err.response?.data?.error || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Create Account</h1>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username</label>
            <input
              type="text"
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              required
              minLength={3}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              required
              minLength={8}
              disabled={loading}
            />
            <small className="form-help">
              Must contain 8+ characters, uppercase, lowercase, and a number
            </small>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ width: '100%' }}
          >
            {loading ? 'Creating account...' : 'Sign Up'}
          </button>
        </form>

        <div className="auth-link">
          Already have an account? <Link to="/login">Login</Link>
        </div>
      </div>
    </div>
  );
}
```

---

### 2. New Header Component with Verification Button

**Location:** `src/components/Header.tsx`

```typescript
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/authService';
import './Header.css';

interface HeaderProps {
  user: {
    username: string;
    email_verified: boolean;
  };
}

export default function Header({ user }: HeaderProps) {
  const navigate = useNavigate();

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  const handleVerificationClick = () => {
    navigate('/verification');
  };

  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-logo">
          <h2>GCRegister</h2>
        </div>

        <div className="header-user">
          <span className="username">Welcome, {user.username}</span>

          <button
            onClick={handleVerificationClick}
            className={`btn ${user.email_verified ? 'btn-verified' : 'btn-verify'}`}
          >
            {user.email_verified ? '✓ Verified' : 'Please Verify E-Mail'}
          </button>

          <button onClick={handleLogout} className="btn btn-logout">
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
```

**CSS Styles:** `src/components/Header.css`

```css
.app-header {
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  padding: 1rem 2rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.header-logo h2 {
  margin: 0;
  color: #1f2937;
  font-size: 1.5rem;
}

.header-user {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.username {
  color: #4b5563;
  font-weight: 500;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid;
}

.btn-verify {
  background: #fffbeb;
  color: #92400e;
  border-color: #fbbf24;
}

.btn-verify:hover {
  background: #fef3c7;
  border-color: #f59e0b;
}

.btn-verified {
  background: #f0fdf4;
  color: #166534;
  border-color: #22c55e;
}

.btn-verified:hover {
  background: #dcfce7;
  border-color: #16a34a;
}

.btn-logout {
  background: #ffffff;
  color: #4b5563;
  border-color: #d1d5db;
}

.btn-logout:hover {
  background: #f9fafb;
  border-color: #9ca3af;
}
```

---

### 3. New VerificationStatusPage Component

**Location:** `src/pages/VerificationStatusPage.tsx`

```typescript
import { useState, useEffect } from 'react';
import { authService } from '../services/authService';
import { useNavigate } from 'react-router-dom';
import './VerificationStatusPage.css';

interface VerificationStatus {
  email_verified: boolean;
  email: string;
  verification_token_expires: string | null;
  can_resend: boolean;
  last_resent_at: string | null;
  resend_count: number;
}

export default function VerificationStatusPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<VerificationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [resending, setResending] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const data = await authService.getVerificationStatus();
      setStatus(data);
    } catch (err: any) {
      setError('Failed to load verification status');
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    if (!status?.can_resend) return;

    setResending(true);
    setError('');
    setMessage('');

    try {
      const result = await authService.resendVerification();
      setMessage(result.message);
      // Reload status
      await loadStatus();
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to resend verification email');
    } finally {
      setResending(false);
    }
  };

  const handleManageAccount = () => {
    navigate('/account/manage');
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  if (!status) {
    return <div className="error">Failed to load status</div>;
  }

  return (
    <div className="verification-container">
      <div className="verification-card">
        {/* Verified State */}
        {status.email_verified && (
          <>
            <div className="status-icon verified">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="status-title verified">Email Verified</h1>
            <p className="status-description">
              Your email <strong>{status.email}</strong> has been verified.
            </p>

            <button
              onClick={handleManageAccount}
              className="btn btn-primary"
              style={{ width: '100%' }}
            >
              Manage Account Settings
            </button>
          </>
        )}

        {/* Unverified State */}
        {!status.email_verified && (
          <>
            <div className="status-icon unverified">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="status-title unverified">Email Not Verified</h1>
            <p className="status-description">
              Please verify your email address <strong>{status.email}</strong> to access account management features.
            </p>

            {message && <div className="alert alert-success">{message}</div>}
            {error && <div className="alert alert-error">{error}</div>}

            <div className="verification-info">
              <p>
                {status.resend_count > 0 && (
                  <>Verification emails sent: {status.resend_count}<br /></>
                )}
                {status.last_resent_at && (
                  <>Last sent: {new Date(status.last_resent_at).toLocaleString()}<br /></>
                )}
              </p>
            </div>

            <button
              onClick={handleResendVerification}
              disabled={!status.can_resend || resending}
              className="btn btn-primary"
              style={{ width: '100%' }}
            >
              {resending ? 'Sending...' : 'Resend Verification Email'}
            </button>

            {!status.can_resend && (
              <p className="rate-limit-notice">
                Please wait a few minutes before requesting another verification email.
              </p>
            )}

            <div className="restriction-notice">
              <h3>Account Restrictions</h3>
              <p>
                While your email is unverified, you cannot:
              </p>
              <ul>
                <li>Change your email address</li>
                <li>Change your password</li>
              </ul>
              <p>
                Please verify your email to unlock these features.
              </p>
            </div>
          </>
        )}

        <button
          onClick={() => navigate('/dashboard')}
          className="btn btn-secondary"
          style={{ width: '100%', marginTop: '1rem' }}
        >
          Back to Dashboard
        </button>
      </div>
    </div>
  );
}
```

**CSS:** `src/pages/VerificationStatusPage.css`

```css
.verification-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(to bottom right, #f3f4f6, #e5e7eb);
  padding: 2rem;
}

.verification-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  padding: 2.5rem;
  max-width: 500px;
  width: 100%;
}

.status-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 1.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-icon.verified {
  background: #dcfce7;
  color: #16a34a;
}

.status-icon.unverified {
  background: #fef3c7;
  color: #f59e0b;
}

.status-icon svg {
  width: 48px;
  height: 48px;
}

.status-title {
  text-align: center;
  font-size: 1.75rem;
  margin-bottom: 1rem;
}

.status-title.verified {
  color: #16a34a;
}

.status-title.unverified {
  color: #f59e0b;
}

.status-description {
  text-align: center;
  color: #6b7280;
  margin-bottom: 2rem;
  line-height: 1.6;
}

.verification-info {
  background: #f9fafb;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
  color: #6b7280;
}

.rate-limit-notice {
  text-align: center;
  font-size: 0.875rem;
  color: #f59e0b;
  margin-top: 0.5rem;
}

.restriction-notice {
  background: #fef3c7;
  border: 1px solid #fbbf24;
  border-radius: 8px;
  padding: 1rem;
  margin-top: 1.5rem;
}

.restriction-notice h3 {
  color: #92400e;
  font-size: 1rem;
  margin-bottom: 0.5rem;
}

.restriction-notice p {
  color: #92400e;
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
}

.restriction-notice ul {
  color: #92400e;
  font-size: 0.875rem;
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.alert {
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  text-align: center;
}

.alert-success {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #22c55e;
}

.alert-error {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #ef4444;
}

.btn {
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  font-size: 1rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-secondary {
  background: #f3f4f6;
  color: #4b5563;
}

.btn-secondary:hover {
  background: #e5e7eb;
}
```

---

### 4. New AccountManagePage Component

**Location:** `src/pages/AccountManagePage.tsx`

```typescript
import { useState, useEffect } from 'react';
import { authService } from '../services/authService';
import { useNavigate } from 'react-router-dom';
import './AccountManagePage.css';

export default function AccountManagePage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Email change state
  const [emailFormData, setEmailFormData] = useState({
    new_email: '',
    password: ''
  });
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailMessage, setEmailMessage] = useState('');
  const [emailError, setEmailError] = useState('');

  // Password change state
  const [passwordFormData, setPasswordFormData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState('');
  const [passwordError, setPasswordError] = useState('');

  useEffect(() => {
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      const userData = await authService.getCurrentUser();
      setUser(userData);

      // Redirect if not verified
      if (!userData.email_verified) {
        navigate('/verification');
      }
    } catch (err) {
      navigate('/login');
    } finally {
      setLoading(false);
    }
  };

  const handleEmailChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setEmailLoading(true);
    setEmailError('');
    setEmailMessage('');

    try {
      const result = await authService.requestEmailChange(
        emailFormData.new_email,
        emailFormData.password
      );

      setEmailMessage(result.message);
      setEmailFormData({ new_email: '', password: '' });
    } catch (err: any) {
      setEmailError(err.response?.data?.error || 'Failed to request email change');
    } finally {
      setEmailLoading(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordLoading(true);
    setPasswordError('');
    setPasswordMessage('');

    // Validate passwords match
    if (passwordFormData.new_password !== passwordFormData.confirm_password) {
      setPasswordError('New passwords do not match');
      setPasswordLoading(false);
      return;
    }

    try {
      const result = await authService.changePassword(
        passwordFormData.current_password,
        passwordFormData.new_password
      );

      setPasswordMessage(result.message);
      setPasswordFormData({
        current_password: '',
        new_password: '',
        confirm_password: ''
      });
    } catch (err: any) {
      setPasswordError(err.response?.data?.error || 'Failed to change password');
    } finally {
      setPasswordLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  if (!user || !user.email_verified) {
    return null; // Will redirect
  }

  return (
    <div className="account-container">
      <div className="account-content">
        <h1>Account Management</h1>

        <div className="account-section">
          <h2>Change Email Address</h2>
          <p className="section-description">
            Update your email address. You'll need to verify the new email before the change takes effect.
          </p>

          {emailMessage && <div className="alert alert-success">{emailMessage}</div>}
          {emailError && <div className="alert alert-error">{emailError}</div>}

          <form onSubmit={handleEmailChange}>
            <div className="form-group">
              <label>Current Email</label>
              <input type="email" value={user.email} disabled />
            </div>

            <div className="form-group">
              <label>New Email Address</label>
              <input
                type="email"
                value={emailFormData.new_email}
                onChange={(e) => setEmailFormData({ ...emailFormData, new_email: e.target.value })}
                required
                disabled={emailLoading}
              />
            </div>

            <div className="form-group">
              <label>Confirm Password</label>
              <input
                type="password"
                value={emailFormData.password}
                onChange={(e) => setEmailFormData({ ...emailFormData, password: e.target.value })}
                required
                disabled={emailLoading}
                placeholder="Enter your current password"
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={emailLoading}
            >
              {emailLoading ? 'Processing...' : 'Request Email Change'}
            </button>
          </form>
        </div>

        <div className="account-section">
          <h2>Change Password</h2>
          <p className="section-description">
            Choose a strong password to keep your account secure.
          </p>

          {passwordMessage && <div className="alert alert-success">{passwordMessage}</div>}
          {passwordError && <div className="alert alert-error">{passwordError}</div>}

          <form onSubmit={handlePasswordChange}>
            <div className="form-group">
              <label>Current Password</label>
              <input
                type="password"
                value={passwordFormData.current_password}
                onChange={(e) => setPasswordFormData({ ...passwordFormData, current_password: e.target.value })}
                required
                disabled={passwordLoading}
              />
            </div>

            <div className="form-group">
              <label>New Password</label>
              <input
                type="password"
                value={passwordFormData.new_password}
                onChange={(e) => setPasswordFormData({ ...passwordFormData, new_password: e.target.value })}
                required
                minLength={8}
                disabled={passwordLoading}
              />
              <small className="form-help">
                Must contain 8+ characters, uppercase, lowercase, and a number
              </small>
            </div>

            <div className="form-group">
              <label>Confirm New Password</label>
              <input
                type="password"
                value={passwordFormData.confirm_password}
                onChange={(e) => setPasswordFormData({ ...passwordFormData, confirm_password: e.target.value })}
                required
                minLength={8}
                disabled={passwordLoading}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={passwordLoading}
            >
              {passwordLoading ? 'Changing...' : 'Change Password'}
            </button>
          </form>
        </div>

        <button
          onClick={() => navigate('/dashboard')}
          className="btn btn-secondary"
          style={{ width: '100%', marginTop: '2rem' }}
        >
          Back to Dashboard
        </button>
      </div>
    </div>
  );
}
```

---

### 5. Updated AuthService

**Location:** `src/services/authService.ts`

```typescript
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authService = {
  async signup(data: { username: string; email: string; password: string }) {
    const response = await api.post('/auth/signup', data);
    // Store tokens
    localStorage.setItem('access_token', response.data.access_token);
    localStorage.setItem('refresh_token', response.data.refresh_token);
    return response.data;
  },

  async login(data: { username: string; password: string }) {
    const response = await api.post('/auth/login', data);
    // Store tokens
    localStorage.setItem('access_token', response.data.access_token);
    localStorage.setItem('refresh_token', response.data.refresh_token);
    return response.data;
  },

  async getCurrentUser() {
    const response = await api.get('/auth/me');
    return response.data;
  },

  async getVerificationStatus() {
    const response = await api.get('/auth/verification/status');
    return response.data;
  },

  async resendVerification() {
    const response = await api.post('/auth/verification/resend');
    return response.data;
  },

  async requestEmailChange(new_email: string, password: string) {
    const response = await api.post('/auth/account/change-email', {
      new_email,
      password
    });
    return response.data;
  },

  async changePassword(current_password: string, new_password: string) {
    const response = await api.post('/auth/account/change-password', {
      current_password,
      new_password
    });
    return response.data;
  },

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }
};
```

---

## Security Architecture

### Security Principles (OWASP Compliance)

#### 1. Email Verification Security

✅ **Token Security**
- Cryptographically signed tokens using `itsdangerous`
- Time-limited tokens (24 hours expiration)
- Tokens stored in database for validation
- Single-use tokens (cleared after verification)

✅ **Rate Limiting**
- Resend limited to 1 per 5 minutes per user
- Prevents email bombing attacks
- Tracked via `last_verification_resent_at` and `verification_resend_count`

✅ **User Enumeration Protection**
- Public resend endpoint uses generic messages
- Doesn't reveal if email exists
- Audit logs track actual attempts

#### 2. Email Change Security (OWASP-Compliant)

✅ **Authentication Requirements**
- Requires active JWT session
- Requires email already verified
- Requires current password confirmation

✅ **Dual Verification Flow**
- Notification sent to OLD email (with cancel link)
- Confirmation required from NEW email
- Prevents account takeover if session compromised

✅ **Race Condition Protection**
- Unique constraint on `pending_email`
- Re-check email availability before final confirmation
- Atomic database updates

✅ **Token Security**
- Separate token type for email changes
- Short expiration (1 hour)
- Includes both user_id and new_email in payload

#### 3. Password Change Security

✅ **Authentication Requirements**
- Requires active JWT session
- Requires email verified
- Requires current password

✅ **Password Validation**
- Minimum 8 characters
- Must include uppercase, lowercase, and digit
- New password must differ from current

✅ **Audit Trail**
- All password changes logged
- Confirmation email sent
- Failed attempts logged

#### 4. JWT Token Security

✅ **Token Management**
- Access tokens: 15 minutes expiration
- Refresh tokens: 30 days expiration
- HMAC-SHA256 signing algorithm
- Secure secret key from environment

✅ **Token Claims**
- Standard claims: `sub` (user_id), `exp`, `iat`
- Custom claims: `username`, `email_verified`
- Verification status in claims for client-side UI

#### 5. Database Security

✅ **Constraints**
- UNIQUE constraints on username, email
- CHECK constraint: `pending_email != email`
- UNIQUE index on `pending_email`
- Foreign key integrity

✅ **Sensitive Data**
- Passwords: bcrypt hashed (cost factor 12)
- Tokens: stored hashed or encrypted
- No plain text passwords ever

#### 6. Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/signup` | 5 | 15 minutes |
| `/login` | 10 | 15 minutes |
| `/verification/resend` | 1 | 5 minutes |
| `/account/change-email` | 3 | 1 hour |
| `/account/change-password` | 5 | 15 minutes |
| `/forgot-password` | 3 | 1 hour |

---

## User Flow Diagrams

### Flow 1: New User Signup & Auto-Login

```
┌──────────────────┐
│ User visits      │
│ /signup          │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Fills form:      │
│ - Username       │
│ - Email          │
│ - Password       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ POST /signup     │
│                  │
│ Backend:         │
│ 1. Validate      │
│ 2. Create user   │
│ 3. Generate token│
│ 4. Send email    │
│ 5. CREATE TOKENS │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Response:        │
│ - access_token   │
│ - refresh_token  │
│ - user data      │
│ - email_verified:│
│   false          │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Store tokens     │
│ Navigate to      │
│ /dashboard       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Dashboard shows: │
│ - Full features  │
│ - Header with:   │
│   "Please Verify │
│   E-Mail" button │
│   (yellow)       │
└──────────────────┘
```

### Flow 2: Email Verification Process

```
┌──────────────────┐
│ User clicks      │
│ "Please Verify   │
│ E-Mail" button   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Navigate to      │
│ /verification    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ GET /verification│
│ /status          │
│                  │
│ Shows:           │
│ - Email address  │
│ - Unverified     │
│ - Resend button  │
│ - Restrictions   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ User clicks      │
│ "Resend" button  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ POST /verification│
│ /resend          │
│                  │
│ Backend:         │
│ 1. Check rate    │
│ 2. Gen new token │
│ 3. Send email    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ User checks email│
│ Clicks link      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ GET /verify-email│
│ ?token=...       │
│                  │
│ Backend:         │
│ 1. Verify token  │
│ 2. Mark verified │
│ 3. Clear token   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Success page     │
│ "Email verified!"│
│ Link to dashboard│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Dashboard header │
│ now shows:       │
│ "✓ Verified"     │
│ (green button)   │
└──────────────────┘
```

### Flow 3: Email Change Process (Verified Users)

```
┌──────────────────┐
│ User clicks      │
│ "✓ Verified"     │
│ button           │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Navigate to      │
│ /account/manage  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Fill email form: │
│ - New email      │
│ - Password       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ POST /account/   │
│ change-email     │
│                  │
│ Backend:         │
│ 1. Verify email  │
│    is verified   │
│ 2. Verify pwd    │
│ 3. Check new     │
│    email free    │
│ 4. Generate token│
│ 5. Store pending │
└────────┬─────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌─────────────────┐  ┌────────────────┐
│ Email to OLD:   │  │ Email to NEW:  │
│ - Notification  │  │ - Confirmation │
│ - New email     │  │ - Link with    │
│ - Cancel link   │  │   token        │
└─────────────────┘  └────────┬───────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ User clicks link │
                     │ in NEW email     │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ GET /account/    │
                     │ confirm-email-   │
                     │ change?token=... │
                     │                  │
                     │ Backend:         │
                     │ 1. Verify token  │
                     │ 2. Check email   │
                     │    still free    │
                     │ 3. Update email  │
                     │ 4. Clear pending │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ Success!         │
                     │ Email changed    │
                     │ Confirmation sent│
                     └──────────────────┘
```

### Flow 4: Password Change Process (Verified Users)

```
┌──────────────────┐
│ User on /account/│
│ manage page      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Fill password    │
│ form:            │
│ - Current pwd    │
│ - New pwd        │
│ - Confirm new    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ POST /account/   │
│ change-password  │
│                  │
│ Backend:         │
│ 1. Verify email  │
│    is verified   │
│ 2. Verify current│
│    password      │
│ 3. Validate new  │
│ 4. Hash new pwd  │
│ 5. Update DB     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Success message  │
│ Confirmation     │
│ email sent       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ User receives    │
│ confirmation     │
│ email            │
└──────────────────┘
```

---

## Implementation Roadmap

### Phase 1: Database Changes (Day 1)
- [ ] Create migration script `002_add_email_change_support.sql`
- [ ] Test migration on development database
- [ ] Deploy migration to production
- [ ] Verify schema changes

### Phase 2: Backend API - Core Changes (Days 2-3)
- [ ] Modify `/signup` endpoint to return tokens
- [ ] Modify `/login` endpoint to allow unverified logins
- [ ] Update `/me` endpoint to include `email_verified`
- [ ] Add `email_verified` to JWT claims
- [ ] Test authentication flow

### Phase 3: Backend API - Verification (Days 4-5)
- [ ] Create `/verification/status` endpoint
- [ ] Modify `/verification/resend` endpoint (authenticated)
- [ ] Add rate limiting logic
- [ ] Update audit logging
- [ ] Test verification flow

### Phase 4: Backend API - Account Management (Days 6-8)
- [ ] Create `/account/change-email` endpoint
- [ ] Create `/account/confirm-email-change` endpoint
- [ ] Create `/account/cancel-email-change` endpoint
- [ ] Create `/account/change-password` endpoint
- [ ] Implement TokenService email change methods
- [ ] Create new email templates
- [ ] Test all account management flows

### Phase 5: Frontend - Components (Days 9-10)
- [ ] Create `Header` component with verification button
- [ ] Create `VerificationStatusPage` component
- [ ] Create `AccountManagePage` component
- [ ] Update `SignupPage` for auto-login
- [ ] Add routes to router

### Phase 6: Frontend - Services (Day 11)
- [ ] Update `authService` with new methods
- [ ] Add error handling
- [ ] Add loading states
- [ ] Test API integration

### Phase 7: Testing (Days 12-13)
- [ ] Unit tests for backend services
- [ ] Integration tests for API endpoints
- [ ] Frontend component tests
- [ ] End-to-end user flow tests
- [ ] Security testing
- [ ] Rate limiting tests

### Phase 8: Documentation & Deployment (Day 14)
- [ ] Update API documentation
- [ ] Update user guides
- [ ] Deploy backend changes
- [ ] Deploy frontend changes
- [ ] Monitor production logs
- [ ] User acceptance testing

---

## Testing Strategy

### Backend Testing

#### Unit Tests
```python
# tests/test_auth_service.py

def test_signup_returns_tokens():
    """Test that signup creates user and returns tokens"""
    # Arrange
    signup_data = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'TestPass123'
    }

    # Act
    response = client.post('/auth/signup', json=signup_data)

    # Assert
    assert response.status_code == 201
    assert 'access_token' in response.json
    assert 'refresh_token' in response.json
    assert response.json['email_verified'] == False


def test_login_allows_unverified():
    """Test that login works for unverified users"""
    # Arrange
    create_unverified_user('testuser', 'test@example.com')

    # Act
    response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'TestPass123'
    })

    # Assert
    assert response.status_code == 200
    assert 'access_token' in response.json


def test_email_change_requires_verification():
    """Test that email change requires verified account"""
    # Arrange
    user = create_unverified_user()
    token = get_access_token(user)

    # Act
    response = client.post('/auth/account/change-email',
        headers={'Authorization': f'Bearer {token}'},
        json={'new_email': 'new@example.com', 'password': 'TestPass123'}
    )

    # Assert
    assert response.status_code == 403
    assert 'requires_verification' in response.json
```

#### Integration Tests
```python
# tests/test_verification_flow.py

def test_complete_verification_flow():
    """Test complete email verification flow"""
    # 1. Signup
    signup_resp = client.post('/auth/signup', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'TestPass123'
    })
    assert signup_resp.status_code == 201

    # 2. Get verification status
    token = signup_resp.json['access_token']
    status_resp = client.get('/auth/verification/status',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert status_resp.json['email_verified'] == False

    # 3. Resend verification
    resend_resp = client.post('/auth/verification/resend',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert resend_resp.status_code == 200

    # 4. Verify email
    verify_token = get_verification_token_from_db('test@example.com')
    verify_resp = client.get(f'/auth/verify-email?token={verify_token}')
    assert verify_resp.status_code == 200

    # 5. Check status again
    status_resp2 = client.get('/auth/verification/status',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert status_resp2.json['email_verified'] == True


def test_rate_limiting_resend_verification():
    """Test rate limiting on verification resend"""
    user = create_unverified_user()
    token = get_access_token(user)

    # First resend - should succeed
    resp1 = client.post('/auth/verification/resend',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert resp1.status_code == 200

    # Immediate second resend - should fail
    resp2 = client.post('/auth/verification/resend',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert resp2.status_code == 429
    assert 'retry_after' in resp2.json
```

### Frontend Testing

#### Component Tests
```typescript
// src/pages/VerificationStatusPage.test.tsx

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import VerificationStatusPage from './VerificationStatusPage';
import { authService } from '../services/authService';

jest.mock('../services/authService');

describe('VerificationStatusPage', () => {
  it('shows unverified state for unverified users', async () => {
    authService.getVerificationStatus.mockResolvedValue({
      email_verified: false,
      email: 'test@example.com',
      can_resend: true
    });

    render(
      <MemoryRouter>
        <VerificationStatusPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Email Not Verified')).toBeInTheDocument();
    });

    expect(screen.getByText(/test@example.com/)).toBeInTheDocument();
    expect(screen.getByText('Resend Verification Email')).toBeInTheDocument();
  });

  it('shows verified state for verified users', async () => {
    authService.getVerificationStatus.mockResolvedValue({
      email_verified: true,
      email: 'test@example.com'
    });

    render(
      <MemoryRouter>
        <VerificationStatusPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Email Verified')).toBeInTheDocument();
    });

    expect(screen.getByText('Manage Account Settings')).toBeInTheDocument();
  });

  it('handles resend verification', async () => {
    authService.getVerificationStatus.mockResolvedValue({
      email_verified: false,
      email: 'test@example.com',
      can_resend: true
    });

    authService.resendVerification.mockResolvedValue({
      success: true,
      message: 'Email sent'
    });

    render(
      <MemoryRouter>
        <VerificationStatusPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Resend Verification Email')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Resend Verification Email'));

    await waitFor(() => {
      expect(authService.resendVerification).toHaveBeenCalled();
      expect(screen.getByText('Email sent')).toBeInTheDocument();
    });
  });
});
```

---

## Migration Path

### For Existing Users

#### Scenario 1: Users with Verified Emails
- **Status:** No action needed
- **Experience:** Immediate access to account management
- **Notes:** Can change email/password immediately

#### Scenario 2: Users with Unverified Emails
- **Status:** Can now login
- **Experience:**
  - See "Please Verify E-Mail" button on dashboard
  - Can use all features
  - Cannot change email/password until verified
  - Can request new verification email anytime

#### Scenario 3: Users Who Previously Couldn't Login
- **Status:** Can now login
- **Process:**
  1. Login with existing credentials
  2. See verification prompt
  3. Request new verification email
  4. Verify email
  5. Full account management unlocked

### Database Migration Safety

```sql
-- Pre-migration checks
SELECT COUNT(*) FROM registered_users WHERE email_verified = FALSE;
-- Result: X users need verification emails resent

-- Post-migration verification
SELECT COUNT(*) FROM registered_users WHERE pending_email IS NOT NULL;
-- Result: Should be 0 (no pending changes initially)

SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'registered_users';
-- Result: Verify new indexes exist
```

---

## Email Templates

### 1. Email Verification Email
**Subject:** Please verify your email address

```html
Hi {{username}},

Welcome to GCRegister! Please verify your email address to unlock full account management features.

Click the link below to verify your email:
{{verification_link}}

This link will expire in 24 hours.

You can start using GCRegister immediately, but you'll need to verify your email to:
- Change your email address
- Change your password
- Access advanced account settings

Best regards,
The GCRegister Team
```

### 2. Email Change Notification (Old Email)
**Subject:** Email change requested for your account

```html
Hi {{username}},

A request was made to change the email address for your GCRegister account from:
{{old_email}} → {{new_email}}

If you made this request, no action is needed. The change will be completed once the new email address is verified.

If you did NOT request this change, please take action immediately:
{{cancel_link}}

Best regards,
The GCRegister Team
```

### 3. Email Change Confirmation (New Email)
**Subject:** Confirm your new email address

```html
Hi {{username}},

A request was made to change the email address for your GCRegister account to this address.

Click the link below to confirm this change:
{{confirmation_link}}

This link will expire in 1 hour.

If you did not request this change, you can safely ignore this email.

Best regards,
The GCRegister Team
```

### 4. Email Changed Confirmation
**Subject:** Your email address has been changed

```html
Hi {{username}},

Your email address has been successfully changed to:
{{new_email}}

This is a confirmation that the change is complete. You can now login using your new email address.

If you did not authorize this change, please contact support immediately.

Best regards,
The GCRegister Team
```

### 5. Password Changed Confirmation
**Subject:** Your password has been changed

```html
Hi {{username}},

Your password was successfully changed.

If you made this change, no further action is needed.

If you did NOT change your password, your account may be compromised. Please:
1. Login immediately
2. Change your password
3. Contact support if you need assistance

Best regards,
The GCRegister Team
```

---

## Monitoring & Metrics

### Key Metrics to Track

#### User Behavior Metrics
- **Signup to Dashboard Time:** Should be < 5 seconds
- **Verification Rate:** % of users who verify within 24 hours
- **Verification Abandonment:** % of users who never verify
- **Email Change Success Rate:** % of initiated changes completed
- **Password Change Frequency:** Track for security patterns

#### Security Metrics
- **Failed Password Attempts:** Monitor for brute force
- **Rate Limit Hits:** Track resend abuse attempts
- **Token Expiration Rates:** Adjust expiration if too many expire
- **Email Bounce Rates:** Track delivery issues

#### Performance Metrics
- **API Response Times:**
  - `/signup`: Target < 200ms
  - `/login`: Target < 150ms
  - `/verification/resend`: Target < 300ms
  - `/account/change-email`: Target < 250ms

### Logging Strategy

```python
# Audit logs to create:
✅ User signup (with auto-login flag)
✅ Email verification sent
✅ Email verification completed
✅ Email verification failed (expired, invalid)
✅ Verification resend requested
✅ Email change requested
✅ Email change notification sent
✅ Email change completed
✅ Email change cancelled
✅ Password change successful
✅ Password change failed (wrong password)
```

---

## Conclusion

This architecture provides a **secure, user-friendly, and OWASP-compliant** solution for email verification and account management. Key benefits:

✅ **Zero-Friction Onboarding:** Users get immediate access after signup
✅ **Clear Visual Feedback:** Verification status always visible
✅ **Security First:** All sensitive operations require verification + password
✅ **Industry Best Practices:** Dual verification for email changes, audit logging, rate limiting
✅ **Scalable Design:** Clean separation of concerns, easy to extend
✅ **User Privacy:** No enumeration vulnerabilities, secure token handling

The implementation roadmap provides a clear 14-day path to completion with comprehensive testing at each phase.

---

**Document End**
