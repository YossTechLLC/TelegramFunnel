# Email Verification & Password Reset Implementation Checklist

**Date:** 2025-11-09
**Based On:** LOGIN_UPDATE_ARCHITECTURE.md v1.0
**Status:** 🚀 **READY FOR IMPLEMENTATION**

---

## Table of Contents

1. [Prerequisites & Setup](#prerequisites--setup)
2. [Phase 1: Foundation (Week 1)](#phase-1-foundation-week-1)
3. [Phase 2: Email Verification (Week 1-2)](#phase-2-email-verification-week-1-2)
4. [Phase 3: Password Reset (Week 2)](#phase-3-password-reset-week-2)
5. [Phase 4: Rate Limiting & Security (Week 3)](#phase-4-rate-limiting--security-week-3)
6. [Phase 5: Monitoring & Cleanup (Week 3)](#phase-5-monitoring--cleanup-week-3)
7. [Testing & Validation](#testing--validation)
8. [Deployment Checklist](#deployment-checklist)
9. [Code Organization Summary](#code-organization-summary)

---

## How to Use This Checklist

- ✅ Check off items as you complete them
- 🔴 = Critical/Blocking task
- 🟡 = High priority
- 🟢 = Medium/Low priority
- 📁 = File path reference
- ⚠️ = Important note/warning

---

## Prerequisites & Setup

### Environment Setup

- [ ] 🔴 **Install Python dependencies**
  - [ ] Add `itsdangerous>=2.0.0` to `requirements.txt`
  - [ ] Add `sendgrid>=6.9.0` to `requirements.txt`
  - [ ] Add `flask-limiter>=3.0.0` to `requirements.txt`
  - [ ] Add `redis>=4.5.0` to `requirements.txt` (for production rate limiting)
  - [ ] Run `pip install -r requirements.txt` in venv
  - 📁 File: `GCRegisterAPI-10-26/requirements.txt`

- [ ] 🔴 **Generate SECRET_KEY for token signing**
  - [ ] Run: `python3 -c 'import os; print(os.urandom(32).hex())'`
  - [ ] Store output securely (will be added to env vars)
  - [ ] Document key rotation process
  - ⚠️ **Never commit this key to git**

- [ ] 🔴 **Create SendGrid account**
  - [ ] Sign up at https://sendgrid.com
  - [ ] Create API key with "Mail Send" permissions
  - [ ] Verify sender email/domain
  - [ ] Test API key with simple send request
  - [ ] Store API key securely

- [ ] 🟡 **Setup environment variables**
  - [ ] Create `.env.example` file with all required vars
  - [ ] Add `SECRET_KEY` to Cloud Run environment
  - [ ] Add `SENDGRID_API_KEY` to Cloud Run secrets
  - [ ] Add `FROM_EMAIL` to Cloud Run environment
  - [ ] Add `FROM_NAME` to Cloud Run environment
  - [ ] Add `BASE_URL` to Cloud Run environment
  - [ ] Add `RECAPTCHA_SECRET_KEY` (optional, for Phase 4)
  - 📁 File: `GCRegisterAPI-10-26/.env.example`

- [ ] 🟢 **Create directory structure**
  - [ ] Verify `api/services/` exists
  - [ ] Verify `api/middleware/` exists
  - [ ] Verify `api/utils/` exists
  - [ ] Verify `api/models/` exists
  - [ ] Verify `tests/` exists
  - [ ] Create `database/migrations/` if not exists
  - [ ] Create `templates/email/` for email templates (optional)

---

## Phase 1: Foundation (Week 1)

**Goal:** Create core services for token generation and email sending

### 1.1 Token Service Implementation

- [ ] 🔴 **Create TokenService class**
  - [ ] Create new file: `api/services/token_service.py`
  - [ ] Import `URLSafeTimedSerializer` from `itsdangerous`
  - [ ] Import `SignatureExpired`, `BadSignature` exceptions
  - [ ] Define class constants:
    - `EMAIL_VERIFICATION_MAX_AGE = 86400` (24 hours)
    - `PASSWORD_RESET_MAX_AGE = 3600` (1 hour)
  - [ ] Implement `__init__()` method to load `SECRET_KEY` from env
  - 📁 File: `GCRegisterAPI-10-26/api/services/token_service.py`

- [ ] 🔴 **Implement email verification token methods**
  - [ ] Create `generate_email_verification_token(user_id: str, email: str) -> str`
    - [ ] Initialize serializer with salt `'email-verify-v1'`
    - [ ] Create payload with `type`, `user_id`, `email`
    - [ ] Return signed token
  - [ ] Create `verify_email_verification_token(token: str) -> Optional[Dict[str, Any]]`
    - [ ] Initialize serializer with same salt
    - [ ] Load token with `max_age=EMAIL_VERIFICATION_MAX_AGE`
    - [ ] Validate token type is `'email_verification'`
    - [ ] Return dict with `user_id` and `email`
    - [ ] Handle `SignatureExpired` exception
    - [ ] Handle `BadSignature` exception
  - 📁 File: `GCRegisterAPI-10-26/api/services/token_service.py`

- [ ] 🔴 **Implement password reset token methods**
  - [ ] Create `generate_password_reset_token(user_id: str, email: str) -> str`
    - [ ] Initialize serializer with salt `'password-reset-v1'`
    - [ ] Create payload with `type`, `user_id`, `email`
    - [ ] Return signed token
  - [ ] Create `verify_password_reset_token(token: str) -> Optional[Dict[str, Any]]`
    - [ ] Initialize serializer with same salt
    - [ ] Load token with `max_age=PASSWORD_RESET_MAX_AGE`
    - [ ] Validate token type is `'password_reset'`
    - [ ] Return dict with `user_id` and `email`
    - [ ] Handle exceptions appropriately
  - 📁 File: `GCRegisterAPI-10-26/api/services/token_service.py`

- [ ] 🟢 **Add utility method for expiration datetime**
  - [ ] Create static method `get_expiration_datetime(token_type: str) -> datetime`
  - [ ] Return datetime 24h from now for `'email_verification'`
  - [ ] Return datetime 1h from now for `'password_reset'`
  - [ ] Raise `ValueError` for unknown token types
  - 📁 File: `GCRegisterAPI-10-26/api/services/token_service.py`

### 1.2 Email Service Implementation

- [ ] 🔴 **Create EmailService class**
  - [ ] Create new file: `api/services/email_service.py`
  - [ ] Import SendGrid libraries: `SendGridAPIClient`, `Mail`, `Email`, `To`
  - [ ] Import `os` for environment variables
  - [ ] Implement `__init__()` method:
    - [ ] Load `SENDGRID_API_KEY` from env
    - [ ] Load `FROM_EMAIL` from env (default: 'noreply@telepay.com')
    - [ ] Load `FROM_NAME` from env (default: 'TelePay')
    - [ ] Load `BASE_URL` from env (default: 'https://app.telepay.com')
    - [ ] Print warning if `SENDGRID_API_KEY` not set (dev mode)
  - 📁 File: `GCRegisterAPI-10-26/api/services/email_service.py`

- [ ] 🔴 **Implement email verification email method**
  - [ ] Create `send_verification_email(to_email: str, username: str, token: str) -> bool`
  - [ ] Build verification URL: `{BASE_URL}/verify-email?token={token}`
  - [ ] If no API key (dev mode):
    - [ ] Print email details to console
    - [ ] Print token for manual testing
    - [ ] Return True
  - [ ] Create SendGrid Mail object with:
    - [ ] From email and name
    - [ ] To email
    - [ ] Subject: "Verify Your Email - TelePay"
    - [ ] HTML content from template method
  - [ ] Send email via SendGrid API
  - [ ] Handle success (status 200/201/202)
  - [ ] Handle failures with logging
  - [ ] Return boolean success status
  - 📁 File: `GCRegisterAPI-10-26/api/services/email_service.py`

- [ ] 🔴 **Implement password reset email method**
  - [ ] Create `send_password_reset_email(to_email: str, username: str, token: str) -> bool`
  - [ ] Build reset URL: `{BASE_URL}/reset-password?token={token}`
  - [ ] Handle dev mode (print to console)
  - [ ] Create SendGrid Mail object
  - [ ] Subject: "Password Reset Request - TelePay"
  - [ ] Use password reset template
  - [ ] Send and handle response
  - [ ] Return boolean success status
  - 📁 File: `GCRegisterAPI-10-26/api/services/email_service.py`

- [ ] 🟡 **Implement password reset confirmation email**
  - [ ] Create `send_password_reset_confirmation_email(to_email: str, username: str) -> bool`
  - [ ] Handle dev mode
  - [ ] Create SendGrid Mail object
  - [ ] Subject: "Password Reset Successful - TelePay"
  - [ ] Use confirmation template
  - [ ] Send and handle response
  - [ ] Return boolean success status
  - 📁 File: `GCRegisterAPI-10-26/api/services/email_service.py`

- [ ] 🟡 **Create email HTML templates**
  - [ ] Create static method `_get_verification_email_template(username: str, verification_url: str) -> str`
    - [ ] Design responsive HTML email
    - [ ] Include verification button/link
    - [ ] Show 24-hour expiration warning
    - [ ] Include plain-text URL fallback
    - [ ] Add "didn't create account" disclaimer
  - [ ] Create static method `_get_password_reset_email_template(username: str, reset_url: str) -> str`
    - [ ] Design responsive HTML email
    - [ ] Include reset button/link
    - [ ] Show 1-hour expiration warning
    - [ ] Include plain-text URL fallback
    - [ ] Add "didn't request reset" disclaimer
  - [ ] Create static method `_get_password_reset_confirmation_template(username: str) -> str`
    - [ ] Design success confirmation email
    - [ ] Add security warning if user didn't make change
  - 📁 File: `GCRegisterAPI-10-26/api/services/email_service.py`

### 1.3 Database Indexes

- [ ] 🟡 **Create database migration for indexes**
  - [ ] Create new file: `database/migrations/add_token_indexes.sql`
  - [ ] Add partial index on `verification_token`:
    ```sql
    CREATE INDEX IF NOT EXISTS idx_registered_users_verification_token
    ON registered_users(verification_token)
    WHERE verification_token IS NOT NULL;
    ```
  - [ ] Add partial index on `reset_token`:
    ```sql
    CREATE INDEX IF NOT EXISTS idx_registered_users_reset_token
    ON registered_users(reset_token)
    WHERE reset_token IS NOT NULL;
    ```
  - [ ] Document why partial indexes are used (performance + space efficiency)
  - 📁 File: `GCRegisterAPI-10-26/database/migrations/add_token_indexes.sql`

- [ ] 🟡 **Apply database migration**
  - [ ] Connect to `telepaypsql` database
  - [ ] Run migration script
  - [ ] Verify indexes created: `\d registered_users`
  - [ ] Test index usage with EXPLAIN query
  - [ ] Document in PROGRESS.md

### 1.4 Unit Tests for Foundation

- [ ] 🟡 **Create token service tests**
  - [ ] Create new file: `tests/test_token_service.py`
  - [ ] Import `pytest`, `TokenService`, exceptions
  - [ ] Test `generate_email_verification_token()`:
    - [ ] Verify token is not None
    - [ ] Verify token is string
    - [ ] Verify token length > 50 chars
  - [ ] Test `verify_email_verification_token()`:
    - [ ] Generate token, verify it
    - [ ] Check user_id and email in result
  - [ ] Test token expiration:
    - [ ] Set short max_age (1 second)
    - [ ] Wait for expiration
    - [ ] Verify `SignatureExpired` raised
  - [ ] Test tampered token:
    - [ ] Generate valid token
    - [ ] Modify token string
    - [ ] Verify `BadSignature` raised
  - [ ] Test password reset tokens (same tests)
  - [ ] Test `get_expiration_datetime()` utility
  - 📁 File: `GCRegisterAPI-10-26/tests/test_token_service.py`

- [ ] 🟢 **Create email service tests**
  - [ ] Create new file: `tests/test_email_service.py`
  - [ ] Test email service initialization
  - [ ] Test dev mode (no API key):
    - [ ] Verify console output
    - [ ] Verify returns True
  - [ ] Test email template generation:
    - [ ] Verify HTML is valid
    - [ ] Verify URLs included
    - [ ] Verify username personalization
  - [ ] Mock SendGrid API for integration tests
  - 📁 File: `GCRegisterAPI-10-26/tests/test_email_service.py`

### 1.5 Documentation & Review

- [ ] 🟢 **Update project documentation**
  - [ ] Document new environment variables in README
  - [ ] Add setup instructions for email service
  - [ ] Document token service usage
  - [ ] Add troubleshooting section

- [ ] 🟢 **Code review checkpoint**
  - [ ] Review token service implementation
  - [ ] Review email service implementation
  - [ ] Verify proper error handling
  - [ ] Check logging statements use correct emojis
  - [ ] Ensure no secrets in code

---

## Phase 2: Email Verification (Week 1-2)

**Goal:** Implement complete email verification flow

### 2.1 Update Pydantic Models

- [ ] 🟡 **Add new request/response models**
  - [ ] Open file: `api/models/auth.py`
  - [ ] Create `ResendVerificationRequest` model:
    - [ ] Field: `email: EmailStr`
  - [ ] Create `VerifyEmailResponse` model:
    - [ ] Field: `success: bool`
    - [ ] Field: `message: str`
    - [ ] Field: `redirect_url: str = "/login"`
  - [ ] Create `GenericMessageResponse` model:
    - [ ] Field: `success: bool`
    - [ ] Field: `message: str`
  - [ ] Update `AuthResponse` model:
    - [ ] Add optional field: `email_verified: bool = False`
    - [ ] Add optional field: `verification_required: bool = False`
  - 📁 File: `GCRegisterAPI-10-26/api/models/auth.py`

### 2.2 Extend AuthService

- [ ] 🔴 **Add verification token generation to user creation**
  - [ ] Open file: `api/services/auth_service.py`
  - [ ] Import `TokenService` at top
  - [ ] In `create_user()` method, after user INSERT:
    - [ ] Initialize `TokenService`
    - [ ] Generate verification token
    - [ ] Calculate expiration datetime (24h from now)
    - [ ] UPDATE user record with token and expiration:
      ```sql
      UPDATE registered_users
      SET verification_token = %s,
          verification_token_expires = %s
      WHERE user_id = %s
      ```
    - [ ] Return token along with user data
  - 📁 File: `GCRegisterAPI-10-26/api/services/auth_service.py`

- [ ] 🔴 **Create email verification method**
  - [ ] Add new method: `verify_email(conn, token: str) -> Dict[str, Any]`
  - [ ] Initialize `TokenService`
  - [ ] Call `verify_email_verification_token(token)`
  - [ ] Extract `user_id` and `email` from token data
  - [ ] Query database for user:
    ```sql
    SELECT verification_token, verification_token_expires, email_verified, username
    FROM registered_users
    WHERE user_id = %s AND email = %s
    ```
  - [ ] Validate token matches database
  - [ ] Check if already verified (return appropriate message)
  - [ ] Check expiration timestamp
  - [ ] Mark email as verified:
    ```sql
    UPDATE registered_users
    SET email_verified = TRUE,
        verification_token = NULL,
        verification_token_expires = NULL,
        updated_at = NOW()
    WHERE user_id = %s
    ```
  - [ ] Return success response with user data
  - [ ] Handle all error cases (expired, invalid, already used)
  - 📁 File: `GCRegisterAPI-10-26/api/services/auth_service.py`

- [ ] 🔴 **Create resend verification method**
  - [ ] Add new method: `resend_verification_email(conn, email: str) -> bool`
  - [ ] Query user by email:
    ```sql
    SELECT user_id, username, email_verified
    FROM registered_users
    WHERE email = %s
    ```
  - [ ] If user not found, return True (don't reveal existence)
  - [ ] If already verified, return True (don't reveal status)
  - [ ] Generate new verification token
  - [ ] Update database with new token and expiration
  - [ ] Return True (user exists and token generated)
  - 📁 File: `GCRegisterAPI-10-26/api/services/auth_service.py`

- [ ] 🔴 **Update authenticate_user to check email_verified**
  - [ ] In `authenticate_user()` method, after password verification:
  - [ ] Check if `email_verified` is False
  - [ ] If not verified, raise `ValueError('Email not verified. Please check your email for the verification link.')`
  - [ ] Update error messages to be user-friendly
  - 📁 File: `GCRegisterAPI-10-26/api/services/auth_service.py`

### 2.3 Add Email Verification Endpoints

- [ ] 🔴 **Modify signup endpoint**
  - [ ] Open file: `api/routes/auth.py`
  - [ ] Import `EmailService` at top
  - [ ] In `/signup` endpoint, after user creation:
    - [ ] Initialize `EmailService`
    - [ ] Get verification token from user creation result
    - [ ] Call `send_verification_email(email, username, token)`
    - [ ] Log email sending status
  - [ ] Modify response to NOT include tokens:
    - [ ] Remove `access_token` and `refresh_token` from response
    - [ ] Add `verification_required: true`
    - [ ] Add message: "Account created. Please check your email to verify your account."
  - 📁 File: `GCRegisterAPI-10-26/api/routes/auth.py`

- [ ] 🔴 **Create verify-email endpoint**
  - [ ] Add new route: `@auth_bp.route('/verify-email', methods=['GET'])`
  - [ ] Get `token` from query parameters: `request.args.get('token')`
  - [ ] Validate token is provided
  - [ ] Call `AuthService.verify_email(conn, token)`
  - [ ] Return success response:
    ```json
    {
      "success": true,
      "message": "Email verified successfully! You can now log in.",
      "redirect_url": "/login"
    }
    ```
  - [ ] Handle `SignatureExpired` exception (400 error)
  - [ ] Handle `BadSignature` exception (400 error)
  - [ ] Handle `ValueError` exceptions (400 error)
  - [ ] Log verification attempts (success and failure)
  - 📁 File: `GCRegisterAPI-10-26/api/routes/auth.py`

- [ ] 🔴 **Create resend-verification endpoint**
  - [ ] Add new route: `@auth_bp.route('/resend-verification', methods=['POST'])`
  - [ ] Apply rate limiting decorator (implement in Phase 4, placeholder for now)
  - [ ] Validate request data with `ResendVerificationRequest`
  - [ ] Call `AuthService.resend_verification_email(conn, email)`
  - [ ] If user exists and token generated:
    - [ ] Initialize `EmailService`
    - [ ] Send verification email
  - [ ] Return GENERIC response (same for all cases):
    ```json
    {
      "success": true,
      "message": "If an account with that email exists and is unverified, a new verification email has been sent."
    }
    ```
  - [ ] This prevents user enumeration
  - 📁 File: `GCRegisterAPI-10-26/api/routes/auth.py`

- [ ] 🟡 **Update login endpoint response**
  - [ ] In `/login` endpoint, catch the "Email not verified" ValueError
  - [ ] Return 403 Forbidden with specific error:
    ```json
    {
      "success": false,
      "error": "Email not verified. Please check your email for the verification link.",
      "email_verified": false,
      "resend_verification_available": true
    }
    ```
  - [ ] This helps users understand why login failed
  - 📁 File: `GCRegisterAPI-10-26/api/routes/auth.py`

### 2.4 Integration Tests for Email Verification

- [ ] 🟡 **Create auth flow integration tests**
  - [ ] Create new file: `tests/test_auth_flow.py`
  - [ ] Create test client fixture
  - [ ] Test `test_signup_sends_verification_email()`:
    - [ ] POST to `/auth/signup`
    - [ ] Verify 201 response
    - [ ] Verify `verification_required` is True
    - [ ] Verify no `access_token` in response
  - [ ] Test `test_login_requires_verified_email()`:
    - [ ] Create unverified user
    - [ ] POST to `/auth/login`
    - [ ] Verify 403 response
    - [ ] Verify error message mentions verification
  - [ ] Test `test_email_verification_flow()`:
    - [ ] Signup user
    - [ ] Get token (from mock/database)
    - [ ] GET `/auth/verify-email?token={token}`
    - [ ] Verify 200 response
    - [ ] Login should now work
  - [ ] Test `test_resend_verification()`:
    - [ ] POST to `/resend-verification`
    - [ ] Verify generic success message
  - [ ] Test `test_verify_expired_token()`:
    - [ ] Create expired token
    - [ ] Verify 400 error with "expired" message
  - 📁 File: `GCRegisterAPI-10-26/tests/test_auth_flow.py`

### 2.5 Documentation & Review

- [ ] 🟢 **Update API documentation**
  - [ ] Document new endpoints in API docs
  - [ ] Add example requests/responses
  - [ ] Document error codes
  - [ ] Update Postman collection (if exists)

- [ ] 🟢 **Code review checkpoint**
  - [ ] Review all modified auth files
  - [ ] Test email verification flow manually
  - [ ] Verify email templates render correctly
  - [ ] Check error handling completeness

---

## Phase 3: Password Reset (Week 2)

**Goal:** Implement secure password reset functionality

### 3.1 Update Pydantic Models

- [ ] 🟡 **Add password reset models**
  - [ ] Open file: `api/models/auth.py`
  - [ ] Create `ForgotPasswordRequest` model:
    - [ ] Field: `email: EmailStr`
    - [ ] Optional field: `recaptcha_token: Optional[str] = None`
  - [ ] Create `ResetPasswordRequest` model:
    - [ ] Field: `token: str`
    - [ ] Field: `new_password: str`
    - [ ] Add password validator (reuse from SignupRequest)
  - 📁 File: `GCRegisterAPI-10-26/api/models/auth.py`

### 3.2 Extend AuthService for Password Reset

- [ ] 🔴 **Create forgot password method**
  - [ ] Open file: `api/services/auth_service.py`
  - [ ] Add method: `request_password_reset(conn, email: str) -> Optional[Dict[str, Any]]`
  - [ ] Query user by email:
    ```sql
    SELECT user_id, username, email, is_active
    FROM registered_users
    WHERE email = %s
    ```
  - [ ] If user not found, return None (caller will send generic response)
  - [ ] If user not active, return None
  - [ ] Initialize `TokenService`
  - [ ] Generate password reset token
  - [ ] Calculate expiration (1 hour from now)
  - [ ] Update database:
    ```sql
    UPDATE registered_users
    SET reset_token = %s,
        reset_token_expires = %s,
        updated_at = NOW()
    WHERE user_id = %s
    ```
  - [ ] Return dict with `username`, `email`, `token`
  - 📁 File: `GCRegisterAPI-10-26/api/services/auth_service.py`

- [ ] 🔴 **Create reset password method**
  - [ ] Add method: `reset_password(conn, token: str, new_password: str) -> Dict[str, Any]`
  - [ ] Initialize `TokenService`
  - [ ] Verify reset token: `verify_password_reset_token(token)`
  - [ ] Extract `user_id` and `email` from token
  - [ ] Query database:
    ```sql
    SELECT reset_token, reset_token_expires, username, email
    FROM registered_users
    WHERE user_id = %s
    ```
  - [ ] Validate token matches database
  - [ ] Check expiration timestamp
  - [ ] Hash new password with bcrypt
  - [ ] Update password and clear reset token:
    ```sql
    UPDATE registered_users
    SET password_hash = %s,
        reset_token = NULL,
        reset_token_expires = NULL,
        updated_at = NOW()
    WHERE user_id = %s
    ```
  - [ ] Return success with user info
  - [ ] Handle all error cases
  - 📁 File: `GCRegisterAPI-10-26/api/services/auth_service.py`

- [ ] 🟡 **Create session invalidation method (placeholder)**
  - [ ] Add method: `invalidate_all_sessions(conn, user_id: str)`
  - [ ] Add TODO comment for future session management implementation
  - [ ] For now, add to documentation as future enhancement
  - [ ] Consider JWT token blacklist or session version increment
  - 📁 File: `GCRegisterAPI-10-26/api/services/auth_service.py`

### 3.3 Add Password Reset Endpoints

- [ ] 🔴 **Create forgot-password endpoint**
  - [ ] Open file: `api/routes/auth.py`
  - [ ] Add route: `@auth_bp.route('/forgot-password', methods=['POST'])`
  - [ ] Apply rate limiting decorator (Phase 4)
  - [ ] Validate request with `ForgotPasswordRequest`
  - [ ] Extract email from request
  - [ ] Call `AuthService.request_password_reset(conn, email)`
  - [ ] If result is not None (user found):
    - [ ] Initialize `EmailService`
    - [ ] Send reset email: `send_password_reset_email(email, username, token)`
  - [ ] Always return GENERIC response:
    ```json
    {
      "success": true,
      "message": "If an account with that email exists, a password reset link has been sent."
    }
    ```
  - [ ] Log request (but don't log whether user found)
  - [ ] Handle exceptions gracefully
  - 📁 File: `GCRegisterAPI-10-26/api/routes/auth.py`

- [ ] 🔴 **Create reset-password endpoint**
  - [ ] Add route: `@auth_bp.route('/reset-password', methods=['POST'])`
  - [ ] Apply rate limiting decorator
  - [ ] Validate request with `ResetPasswordRequest`
  - [ ] Extract token and new_password
  - [ ] Call `AuthService.reset_password(conn, token, new_password)`
  - [ ] On success:
    - [ ] Call `invalidate_all_sessions(conn, user_id)` (placeholder)
    - [ ] Initialize `EmailService`
    - [ ] Send confirmation: `send_password_reset_confirmation_email(email, username)`
    - [ ] Return success response:
      ```json
      {
        "success": true,
        "message": "Password has been reset successfully. Please log in with your new password."
      }
      ```
  - [ ] Handle `SignatureExpired` (400 - expired)
  - [ ] Handle `BadSignature` (400 - invalid)
  - [ ] Handle `ValueError` (400 - various validation errors)
  - [ ] Log password reset events (security audit)
  - 📁 File: `GCRegisterAPI-10-26/api/routes/auth.py`

### 3.4 Integration Tests for Password Reset

- [ ] 🟡 **Add password reset tests**
  - [ ] Open file: `tests/test_auth_flow.py`
  - [ ] Test `test_password_reset_flow()`:
    - [ ] Create verified user with known password
    - [ ] POST to `/forgot-password` with email
    - [ ] Verify 200 generic response
    - [ ] Get reset token (from mock/database)
    - [ ] POST to `/reset-password` with token and new password
    - [ ] Verify 200 success
    - [ ] Login with new password should work
    - [ ] Login with old password should fail
  - [ ] Test `test_forgot_password_user_enumeration_protection()`:
    - [ ] Request reset for existing user
    - [ ] Request reset for non-existing user
    - [ ] Verify responses are identical
  - [ ] Test `test_reset_token_single_use()`:
    - [ ] Get valid reset token
    - [ ] Use token to reset password (success)
    - [ ] Try to use same token again (should fail)
  - [ ] Test `test_reset_expired_token()`:
    - [ ] Create expired reset token
    - [ ] Verify 400 error with "expired" message
  - 📁 File: `GCRegisterAPI-10-26/tests/test_auth_flow.py`

### 3.5 Documentation & Review

- [ ] 🟢 **Update API documentation**
  - [ ] Document forgot-password endpoint
  - [ ] Document reset-password endpoint
  - [ ] Add security notes about user enumeration protection
  - [ ] Document token expiration times

- [ ] 🟢 **Code review checkpoint**
  - [ ] Review password reset implementation
  - [ ] Verify user enumeration protection works
  - [ ] Test password reset flow manually
  - [ ] Check confirmation email sends correctly

---

## Phase 4: Rate Limiting & Security (Week 3)

**Goal:** Add rate limiting and enhance security

### 4.1 Rate Limiting Setup

- [ ] 🟡 **Create rate limiter configuration**
  - [ ] Create new file: `api/middleware/rate_limiter.py`
  - [ ] Import Flask-Limiter
  - [ ] Create `setup_rate_limiting(app: Flask) -> Limiter` function
  - [ ] Configure Limiter:
    - [ ] `key_func=get_remote_address`
    - [ ] Default limits: `["200 per day", "50 per hour"]`
    - [ ] Storage: `"memory://"` for dev, `"redis://localhost:6379"` for production
    - [ ] Strategy: `"fixed-window"`
  - [ ] Create decorator functions:
    - [ ] `rate_limit_auth()`: Returns `"5 per minute"`
    - [ ] `rate_limit_email()`: Returns `"3 per hour"`
    - [ ] `rate_limit_password_reset()`: Returns `"3 per hour"`
  - 📁 File: `GCRegisterAPI-10-26/api/middleware/rate_limiter.py`

- [ ] 🟡 **Initialize rate limiter in app**
  - [ ] Open file: `app.py`
  - [ ] Import `setup_rate_limiting`
  - [ ] After app creation, call `limiter = setup_rate_limiting(app)`
  - [ ] Store limiter instance for use in routes
  - 📁 File: `GCRegisterAPI-10-26/app.py`

- [ ] 🟡 **Apply rate limiting to endpoints**
  - [ ] Open file: `api/routes/auth.py`
  - [ ] Import limiter from app or create decorator
  - [ ] Apply to `/signup`: `@limiter.limit("5 per 15 minutes")`
  - [ ] Apply to `/login`: `@limiter.limit("10 per 15 minutes")`
  - [ ] Apply to `/resend-verification`: `@limiter.limit("3 per hour")`
  - [ ] Apply to `/forgot-password`: `@limiter.limit("3 per hour")`
  - [ ] Apply to `/reset-password`: `@limiter.limit("5 per 15 minutes")`
  - [ ] Apply to `/verify-email`: `@limiter.limit("10 per hour")`
  - 📁 File: `GCRegisterAPI-10-26/api/routes/auth.py`

- [ ] 🟢 **Setup Redis for production rate limiting**
  - [ ] Install Redis on server or use Cloud Memorystore
  - [ ] Update rate limiter config to use Redis URI
  - [ ] Test rate limiting with Redis backend
  - [ ] Document Redis setup in deployment docs

### 4.2 Audit Logging

- [ ] 🟡 **Create audit logger**
  - [ ] Create new file: `api/utils/audit_logger.py`
  - [ ] Import Python logging module
  - [ ] Create `AuditLogger` class
  - [ ] Implement methods:
    - [ ] `log_email_verification_sent(user_id, email)`
    - [ ] `log_email_verified(user_id, email)`
    - [ ] `log_email_verification_failed(email, reason, token_excerpt)`
    - [ ] `log_password_reset_requested(email, user_found)`
    - [ ] `log_password_reset_completed(user_id, email)`
    - [ ] `log_password_reset_failed(email, reason, token_excerpt)`
    - [ ] `log_rate_limit_exceeded(endpoint, ip, user_identifier)`
  - [ ] Use appropriate log levels (INFO for success, WARNING for security events)
  - [ ] Include timestamps in ISO format
  - [ ] Use existing emoji patterns from codebase
  - 📁 File: `GCRegisterAPI-10-26/api/utils/audit_logger.py`

- [ ] 🟡 **Integrate audit logging into routes**
  - [ ] Open file: `api/routes/auth.py`
  - [ ] Import `AuditLogger`
  - [ ] Create logger instance
  - [ ] Add logging to `/signup`:
    - [ ] Log verification email sent
  - [ ] Add logging to `/verify-email`:
    - [ ] Log successful verification
    - [ ] Log failed verification attempts
  - [ ] Add logging to `/forgot-password`:
    - [ ] Log reset requests
  - [ ] Add logging to `/reset-password`:
    - [ ] Log successful resets
    - [ ] Log failed reset attempts
  - [ ] Add logging to rate limit handler:
    - [ ] Log when rate limits are exceeded
  - 📁 File: `GCRegisterAPI-10-26/api/routes/auth.py`

### 4.3 CAPTCHA Integration (Optional)

- [ ] 🟢 **Setup reCAPTCHA v3**
  - [ ] Create reCAPTCHA v3 site at https://www.google.com/recaptcha/admin
  - [ ] Get site key and secret key
  - [ ] Add `RECAPTCHA_SECRET_KEY` to environment variables
  - [ ] Add `RECAPTCHA_SITE_KEY` to frontend config

- [ ] 🟢 **Create CAPTCHA verification utility**
  - [ ] Create new file: `api/utils/captcha.py`
  - [ ] Import `requests` library
  - [ ] Create `verify_recaptcha(token: str, action: str) -> bool` function
  - [ ] Make POST request to Google reCAPTCHA API
  - [ ] Verify response success, action, and score >= 0.5
  - [ ] Return boolean result
  - 📁 File: `GCRegisterAPI-10-26/api/utils/captcha.py`

- [ ] 🟢 **Add CAPTCHA to high-risk endpoints**
  - [ ] In `/forgot-password` endpoint:
    - [ ] Check if `recaptcha_token` provided
    - [ ] If production, verify CAPTCHA
    - [ ] Reject if CAPTCHA fails
  - [ ] Consider adding to `/signup` if bot signups occur
  - 📁 File: `GCRegisterAPI-10-26/api/routes/auth.py`

### 4.4 Security Tests

- [ ] 🟡 **Add security-focused tests**
  - [ ] Create new file: `tests/test_security.py`
  - [ ] Test `test_rate_limiting()`:
    - [ ] Make 6 requests to `/forgot-password`
    - [ ] Verify 6th request returns 429
  - [ ] Test `test_user_enumeration_protection()`:
    - [ ] Request reset for existing user
    - [ ] Request reset for non-existing user
    - [ ] Measure response times (should be similar)
    - [ ] Verify response bodies identical
  - [ ] Test `test_token_single_use()`:
    - [ ] Use verification token twice
    - [ ] Verify second use fails
    - [ ] Use reset token twice
    - [ ] Verify second use fails
  - [ ] Test `test_token_tampering()`:
    - [ ] Generate valid token
    - [ ] Modify token string
    - [ ] Verify verification fails
  - 📁 File: `GCRegisterAPI-10-26/tests/test_security.py`

### 4.5 Documentation & Review

- [ ] 🟢 **Security documentation**
  - [ ] Document rate limiting strategy
  - [ ] Document audit logging format
  - [ ] Create security checklist for deployment
  - [ ] Document CAPTCHA setup (if implemented)

- [ ] 🟢 **Code review checkpoint**
  - [ ] Review rate limiting implementation
  - [ ] Test rate limits manually
  - [ ] Verify audit logs are generated
  - [ ] Check CAPTCHA integration (if applicable)

---

## Phase 5: Monitoring & Cleanup (Week 3)

**Goal:** Add monitoring, cleanup jobs, and final polish

### 5.1 Token Cleanup Job

- [ ] 🟡 **Create cleanup script**
  - [ ] Create new file: `tools/cleanup_expired_tokens.py`
  - [ ] Import database connection
  - [ ] Create function `cleanup_expired_verification_tokens()`:
    ```sql
    UPDATE registered_users
    SET verification_token = NULL,
        verification_token_expires = NULL
    WHERE verification_token IS NOT NULL
      AND verification_token_expires < NOW()
    ```
  - [ ] Create function `cleanup_expired_reset_tokens()`:
    ```sql
    UPDATE registered_users
    SET reset_token = NULL,
        reset_token_expires = NULL
    WHERE reset_token IS NOT NULL
      AND reset_token_expires < NOW()
    ```
  - [ ] Create `main()` function to run both cleanups
  - [ ] Log cleanup statistics (how many tokens cleaned)
  - [ ] Make script executable
  - 📁 File: `GCRegisterAPI-10-26/tools/cleanup_expired_tokens.py`

- [ ] 🟡 **Setup Cloud Scheduler job**
  - [ ] Create Cloud Scheduler job for daily cleanup
  - [ ] Schedule: `0 2 * * *` (2 AM daily)
  - [ ] Target: Cloud Run service endpoint or Cloud Function
  - [ ] Configure authentication
  - [ ] Test manual trigger
  - [ ] Monitor execution logs

### 5.2 Monitoring & Alerting

- [ ] 🟢 **Create Cloud Logging filters**
  - [ ] Filter for failed email verifications:
    ```
    resource.type="cloud_run_revision"
    severity="WARNING"
    jsonPayload.message=~"Email verification failed"
    ```
  - [ ] Filter for password reset requests:
    ```
    resource.type="cloud_run_revision"
    jsonPayload.message=~"Password reset requested"
    ```
  - [ ] Filter for rate limit exceeded:
    ```
    resource.type="cloud_run_revision"
    severity="WARNING"
    jsonPayload.message=~"Rate limit exceeded"
    ```
  - [ ] Save filters in Cloud Console

- [ ] 🟢 **Setup monitoring dashboard**
  - [ ] Create custom dashboard in Cloud Monitoring
  - [ ] Add charts for:
    - [ ] Email verification success rate
    - [ ] Password reset requests per day
    - [ ] Rate limit hits per hour
    - [ ] Email delivery failures
    - [ ] Token validation failures
  - [ ] Document dashboard URL

- [ ] 🟢 **Configure alerts**
  - [ ] Alert on email delivery failures > 5% rate
  - [ ] Alert on token validation failures > 10/hour
  - [ ] Alert on rate limit hits > 20/hour
  - [ ] Alert on SendGrid quota nearing limit
  - [ ] Configure notification channels (email, Slack)

### 5.3 Documentation & Deployment Prep

- [ ] 🟡 **Update all documentation**
  - [ ] Update main README with new features
  - [ ] Document environment variables
  - [ ] Create deployment guide
  - [ ] Update API documentation
  - [ ] Create troubleshooting guide
  - [ ] Document monitoring setup

- [ ] 🟡 **Create .env.example file**
  - [ ] List all required environment variables
  - [ ] Add comments explaining each variable
  - [ ] Include example values (non-sensitive)
  - [ ] Document where to get API keys
  - 📁 File: `GCRegisterAPI-10-26/.env.example`

- [ ] 🟢 **Code review checkpoint**
  - [ ] Review all new code
  - [ ] Check for code duplication
  - [ ] Verify error handling completeness
  - [ ] Ensure consistent logging
  - [ ] Check code comments and docstrings

---

## Testing & Validation

### Comprehensive Testing Checklist

- [ ] 🔴 **Unit Tests**
  - [ ] All token service tests pass
  - [ ] All email service tests pass
  - [ ] Run: `pytest tests/test_token_service.py -v`
  - [ ] Run: `pytest tests/test_email_service.py -v`
  - [ ] Verify 100% code coverage for new services

- [ ] 🔴 **Integration Tests**
  - [ ] All auth flow tests pass
  - [ ] All security tests pass
  - [ ] Run: `pytest tests/test_auth_flow.py -v`
  - [ ] Run: `pytest tests/test_security.py -v`
  - [ ] Test with real SendGrid API (staging)

- [ ] 🟡 **Manual Testing - Email Verification**
  - [ ] Signup new user, receive verification email
  - [ ] Click verification link, email gets verified
  - [ ] Try to login before verification (should fail)
  - [ ] Try to login after verification (should succeed)
  - [ ] Request resend verification (receive new email)
  - [ ] Try to use expired verification token (should fail)
  - [ ] Try to use verification token twice (should fail)

- [ ] 🟡 **Manual Testing - Password Reset**
  - [ ] Request password reset for existing user
  - [ ] Receive reset email with valid link
  - [ ] Click reset link, submit new password
  - [ ] Login with new password (should succeed)
  - [ ] Try old password (should fail)
  - [ ] Receive confirmation email
  - [ ] Request reset for non-existent user (generic response)
  - [ ] Try to use expired reset token (should fail)
  - [ ] Try to use reset token twice (should fail)

- [ ] 🟡 **Manual Testing - Rate Limiting**
  - [ ] Make 6 signup requests rapidly (6th should fail with 429)
  - [ ] Make 4 password reset requests in 1 hour (4th should fail)
  - [ ] Verify rate limits reset after time window
  - [ ] Test from different IPs (should have separate limits)

- [ ] 🟡 **Manual Testing - Security**
  - [ ] Verify user enumeration protection (identical responses)
  - [ ] Verify tokens can't be tampered with
  - [ ] Verify HTTPS-only links in emails
  - [ ] Verify audit logs are created
  - [ ] Verify no secrets in logs
  - [ ] Verify proper error messages (not revealing sensitive info)

- [ ] 🟢 **Load Testing**
  - [ ] Test 100 concurrent signups
  - [ ] Test 50 concurrent password resets
  - [ ] Verify rate limiting under load
  - [ ] Check database connection pool handling
  - [ ] Monitor memory usage and performance

- [ ] 🟢 **Email Testing**
  - [ ] Test emails in multiple email clients:
    - [ ] Gmail
    - [ ] Outlook
    - [ ] Apple Mail
  - [ ] Verify HTML renders correctly
  - [ ] Verify links are clickable
  - [ ] Test on mobile devices
  - [ ] Check spam folder placement

---

## Deployment Checklist

### Pre-Deployment

- [ ] 🔴 **Environment Variables**
  - [ ] Generate production SECRET_KEY
  - [ ] Store SECRET_KEY in Google Secret Manager
  - [ ] Add SECRET_KEY to Cloud Run
  - [ ] Add SENDGRID_API_KEY to Cloud Run secrets
  - [ ] Set FROM_EMAIL to verified domain
  - [ ] Set FROM_NAME to production name
  - [ ] Set BASE_URL to production URL
  - [ ] Set REDIS_URL for rate limiting (if using Redis)

- [ ] 🔴 **Database**
  - [ ] Run index migration on production database
  - [ ] Verify indexes created successfully
  - [ ] Test query performance with indexes
  - [ ] Backup database before deployment

- [ ] 🔴 **External Services**
  - [ ] Verify SendGrid account active
  - [ ] Verify SendGrid sender verified
  - [ ] Test email sending from production
  - [ ] Check SendGrid quota limits
  - [ ] Setup Redis instance (if using for rate limiting)

- [ ] 🟡 **Code Quality**
  - [ ] All tests passing
  - [ ] Code reviewed and approved
  - [ ] No TODO comments in production code
  - [ ] No console.log or debug statements
  - [ ] Proper error handling everywhere

### Deployment

- [ ] 🔴 **Deploy to Cloud Run**
  - [ ] Build Docker image with new code
  - [ ] Test image locally
  - [ ] Push image to Container Registry
  - [ ] Deploy to Cloud Run (staging first)
  - [ ] Verify health checks pass
  - [ ] Run smoke tests on staging
  - [ ] Deploy to production
  - [ ] Monitor deployment logs

- [ ] 🟡 **Post-Deployment Verification**
  - [ ] Test signup flow end-to-end
  - [ ] Test email verification flow
  - [ ] Test password reset flow
  - [ ] Verify emails are received
  - [ ] Check rate limiting works
  - [ ] Verify audit logs appear in Cloud Logging
  - [ ] Test from multiple browsers/devices

### Post-Deployment

- [ ] 🟡 **Monitoring**
  - [ ] Verify monitoring dashboard shows data
  - [ ] Check alert configurations
  - [ ] Monitor error rates for first 24 hours
  - [ ] Watch for any unusual patterns

- [ ] 🟢 **Documentation**
  - [ ] Update deployment notes
  - [ ] Document any issues encountered
  - [ ] Create runbook for common issues
  - [ ] Update team on new features

- [ ] 🟢 **Cleanup**
  - [ ] Remove old test data
  - [ ] Archive old code branches
  - [ ] Update issue tracker
  - [ ] Schedule token cleanup job

---

## Code Organization Summary

### New Files Created (11 files)

```
GCRegisterAPI-10-26/
├── api/
│   ├── middleware/
│   │   └── rate_limiter.py              ← NEW: Rate limiting setup
│   ├── services/
│   │   ├── token_service.py             ← NEW: Token generation/validation
│   │   └── email_service.py             ← NEW: Email sending with templates
│   └── utils/
│       ├── audit_logger.py              ← NEW: Security event logging
│       └── captcha.py                   ← NEW: reCAPTCHA verification (optional)
├── database/
│   └── migrations/
│       └── add_token_indexes.sql        ← NEW: Database indexes
├── tests/
│   ├── test_token_service.py            ← NEW: Token service tests
│   ├── test_email_service.py            ← NEW: Email service tests
│   ├── test_auth_flow.py                ← NEW: Integration tests
│   └── test_security.py                 ← NEW: Security tests
├── tools/
│   └── cleanup_expired_tokens.py        ← NEW: Token cleanup job
└── .env.example                         ← NEW: Environment variables template
```

### Modified Files (4 files)

```
GCRegisterAPI-10-26/
├── api/
│   ├── models/
│   │   └── auth.py                      ← MODIFIED: Add new request/response models
│   ├── routes/
│   │   └── auth.py                      ← MODIFIED: Add 4 new endpoints, modify 2 existing
│   └── services/
│       └── auth_service.py              ← MODIFIED: Add verification/reset methods
├── app.py                               ← MODIFIED: Initialize rate limiter
└── requirements.txt                     ← MODIFIED: Add new dependencies
```

### File Size Guidelines

- ✅ **token_service.py**: ~200 lines (focused, single responsibility)
- ✅ **email_service.py**: ~300 lines (templates included, but could extract to separate files)
- ✅ **rate_limiter.py**: ~50 lines (configuration only)
- ✅ **audit_logger.py**: ~150 lines (logging methods)
- ✅ **auth_service.py**: ~400 lines after modifications (acceptable for core service)
- ✅ **auth.py routes**: ~450 lines after modifications (could be split if grows further)

### Refactoring Notes

If any file exceeds 500 lines, consider:
- **auth_service.py**: Split into `auth_service.py` and `verification_service.py`
- **auth.py routes**: Split into `auth_routes.py` and `verification_routes.py`
- **email_service.py**: Extract templates to `templates/email/*.html` files

---

## Progress Tracking

### Overall Progress

- [ ] Phase 1: Foundation (0/6 tasks complete)
- [ ] Phase 2: Email Verification (0/5 tasks complete)
- [ ] Phase 3: Password Reset (0/5 tasks complete)
- [ ] Phase 4: Rate Limiting & Security (0/5 tasks complete)
- [ ] Phase 5: Monitoring & Cleanup (0/3 tasks complete)
- [ ] Testing & Validation (0/7 tasks complete)
- [ ] Deployment (0/4 tasks complete)

### Estimated Timeline

- **Week 1:** Phases 1-2
- **Week 2:** Phase 3
- **Week 3:** Phases 4-5 + Testing + Deployment

### Blocked Items

_Document any blockers here:_
- None currently

### Questions/Decisions Needed

_Document any questions or decisions needed:_
- None currently

---

## Notes & Reminders

- ⚠️ **Remember:** Update PROGRESS.md, DECISIONS.md, and BUGS.md as you implement
- ⚠️ **Remember:** Archive to PROGRESS_ARCH.md etc. when files reach ~80% of token limit
- ⚠️ **Remember:** Use existing emoji patterns from codebase in logs
- ⚠️ **Remember:** Never commit secrets or API keys to git
- ⚠️ **Remember:** Test in staging before production deployment
- ⚠️ **Remember:** All new entries to PROGRESS.md, DECISIONS.md, BUGS.md go at the TOP

---

**END OF CHECKLIST**

_This checklist ensures modular, maintainable code that follows best practices. Each task is specific and actionable. Good luck with the implementation!_
