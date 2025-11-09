#!/usr/bin/env python
"""
🔐 Authentication Routes for GCRegisterAPI-10-26
Handles user signup, login, and token refresh
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from pydantic import ValidationError
from datetime import timedelta

from api.models.auth import (
    SignupRequest, LoginRequest, RefreshTokenRequest,
    SignupResponse, ResendVerificationRequest, VerifyEmailResponse,
    GenericMessageResponse, ForgotPasswordRequest, ResetPasswordRequest
)
from api.services.auth_service import AuthService
from api.services.email_service import EmailService
from api.utils.audit_logger import AuditLogger
from database.connection import db_manager
from itsdangerous import SignatureExpired, BadSignature

# Import limiter from app.py (will be set by app)
from flask import current_app

auth_bp = Blueprint('auth', __name__)


def get_limiter():
    """Get limiter instance from current app"""
    return current_app.extensions.get('limiter')


@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    User signup endpoint - AUTO LOGIN with tokens
    Rate Limited: 5 per 15 minutes

    Request Body: SignupRequest (JSON)
    Returns: 201 Created with user data AND tokens (auto-login, verification optional)
    """
    # Get client IP for audit logging
    client_ip = request.remote_addr

    try:
        # Check if request has JSON data
        if not request.is_json or request.json is None:
            print(f"❌ Signup error: No JSON data in request. Content-Type: {request.content_type}, Data: {request.data[:200] if request.data else 'None'}")
            return jsonify({
                'success': False,
                'error': 'Request must be JSON with Content-Type: application/json'
            }), 400

        # Validate request data
        signup_data = SignupRequest(**request.json)

        # Create user (includes verification token generation)
        with db_manager.get_db() as conn:
            user = AuthService.create_user(
                conn,
                username=signup_data.username,
                email=signup_data.email,
                password=signup_data.password
            )

        # Send verification email
        email_service = EmailService()
        email_sent = email_service.send_verification_email(
            to_email=user['email'],
            username=user['username'],
            token=user['verification_token']
        )

        if not email_sent:
            print(f"⚠️  Failed to send verification email to {user['email']}")

        # Audit log: successful signup
        AuditLogger.log_signup_attempt(
            username=signup_data.username,
            email=user['email'],
            success=True,
            ip=client_ip
        )

        # Audit log: verification email sent
        AuditLogger.log_email_verification_sent(
            user_id=user['user_id'],
            email=user['email']
        )

        # CREATE TOKENS - Auto-login (NEW BEHAVIOR)
        tokens = AuthService.create_tokens(user['user_id'], signup_data.username)

        # Return response WITH TOKENS - user can login immediately
        response = {
            'success': True,
            'message': 'Account created successfully. Please verify your email to unlock all features.',
            'user_id': user['user_id'],
            'username': signup_data.username,
            'email': user['email'],
            'email_verified': False,
            **tokens  # Include access_token, refresh_token, token_type, expires_in
        }

        print(f"✅ User '{signup_data.username}' signed up and auto-logged in - verification email sent to {user['email']}")
        return jsonify(response), 201

    except ValidationError as e:
        print(f"❌ Signup validation error: {e.errors()}")

        # Audit log: failed signup (validation error)
        if request.json:
            AuditLogger.log_signup_attempt(
                username=request.json.get('username', 'unknown'),
                email=request.json.get('email', 'unknown'),
                success=False,
                reason='Validation error',
                ip=client_ip
            )

        # Convert validation errors to JSON-safe format
        error_details = []
        for error in e.errors():
            error_details.append({
                'field': '.'.join(str(loc) for loc in error['loc']),
                'message': error['msg'],
                'type': error['type']
            })

        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': error_details
        }), 400

    except ValueError as e:
        error_msg = str(e)
        print(f"❌ Signup error: {error_msg}")

        # Audit log: failed signup (duplicate user/email)
        if request.json:
            AuditLogger.log_signup_attempt(
                username=request.json.get('username', 'unknown'),
                email=request.json.get('email', 'unknown'),
                success=False,
                reason=error_msg,
                ip=client_ip
            )

        return jsonify({
            'success': False,
            'error': error_msg
        }), 400

    except Exception as e:
        print(f"❌ Signup internal error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    User login endpoint (allows unverified users)
    Rate Limited: 10 per 15 minutes

    Request Body: LoginRequest (JSON)
    Returns: 200 OK with user data and tokens (includes email_verified status)
    """
    # Get client IP for audit logging
    client_ip = request.remote_addr

    try:
        # Validate request data
        login_data = LoginRequest(**request.json)

        # Authenticate user
        with db_manager.get_db() as conn:
            user = AuthService.authenticate_user(
                conn,
                username=login_data.username,
                password=login_data.password
            )

        # Create tokens
        tokens = AuthService.create_tokens(user['user_id'], user['username'])

        # Audit log: successful login
        AuditLogger.log_login_attempt(
            username=login_data.username,
            success=True,
            ip=client_ip
        )

        # Return response
        response = {
            **user,
            **tokens
        }

        print(f"✅ User '{login_data.username}' logged in successfully")
        return jsonify(response), 200

    except ValidationError as e:
        print(f"❌ Login validation error: {e.errors()}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': e.errors()
        }), 400

    except ValueError as e:
        error_msg = str(e)
        print(f"❌ Login error: {error_msg}")

        # Audit log: failed login
        if request.json:
            AuditLogger.log_login_attempt(
                username=request.json.get('username', 'unknown'),
                success=False,
                reason=error_msg,
                ip=client_ip
            )

        # REMOVED: Email verification error check (no longer blocks login)
        # Authentication failure (invalid credentials or disabled account)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 401

    except Exception as e:
        print(f"❌ Login internal error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Token refresh endpoint

    Requires: Refresh token in Authorization header
    Returns: 200 OK with new access token
    """
    try:
        # Get user identity from refresh token
        user_id = get_jwt_identity()

        # Create new access token
        access_token = create_access_token(
            identity=user_id,
            expires_delta=timedelta(minutes=15)
        )

        print(f"✅ Token refreshed for user {user_id}")
        return jsonify({
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': 900
        }), 200

    except Exception as e:
        print(f"❌ Token refresh error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Get current user info (includes email_verified status)

    Requires: Access token in Authorization header
    Returns: 200 OK with user data including verification status
    """
    try:
        user_id = get_jwt_identity()

        # Get user from database (include email_verified)
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
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404

            user = {
                'user_id': str(row[0]),
                'username': row[1],
                'email': row[2],
                'email_verified': row[3],  # NEW: Include verification status
                'created_at': row[4].isoformat() if row[4] else None,
                'last_login': row[5].isoformat() if row[5] else None
            }

        return jsonify(user), 200

    except Exception as e:
        print(f"❌ Get current user error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/verify-email', methods=['GET'])
def verify_email():
    """
    Email verification endpoint
    Rate Limited: 10 per hour

    Query Params: token (verification token from email)
    Returns: 200 OK with verification success message
    """
    try:
        # Get token from query string
        token = request.args.get('token')

        if not token:
            return jsonify({
                'success': False,
                'error': 'Verification token is required'
            }), 400

        # Verify email with token
        with db_manager.get_db() as conn:
            result = AuthService.verify_email(conn, token)

        # Audit log: successful verification
        if result.get('user_id'):
            AuditLogger.log_email_verified(
                user_id=result['user_id'],
                email=result.get('email', 'unknown')
            )

        print(f"✅ Email verified successfully")
        return jsonify({
            'success': result['success'],
            'message': result['message'],
            'redirect_url': '/dashboard'  # Updated: redirect to dashboard (user may already be logged in)
        }), 200

    except ValueError as e:
        error_msg = str(e)
        print(f"❌ Email verification failed: {error_msg}")

        # Audit log: failed verification
        token = request.args.get('token')
        AuditLogger.log_email_verification_failed(
            email=None,
            reason=error_msg,
            token_excerpt=token
        )

        return jsonify({
            'success': False,
            'error': error_msg
        }), 400

    except Exception as e:
        print(f"❌ Email verification error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """
    Resend verification email endpoint
    Rate Limited: 3 per hour

    Request Body: ResendVerificationRequest (JSON)
    Returns: 200 OK with generic message (prevents user enumeration)
    """
    # Get client IP for audit logging
    client_ip = request.remote_addr

    try:
        # Validate request data
        resend_data = ResendVerificationRequest(**request.json)

        # Try to resend verification email
        with db_manager.get_db() as conn:
            user_data = AuthService.resend_verification_email(conn, resend_data.email)

        # If user exists and is unverified, send email
        user_found = user_data is not None
        if user_data:
            email_service = EmailService()
            email_sent = email_service.send_verification_email(
                to_email=user_data['email'],
                username=user_data['username'],
                token=user_data['verification_token']
            )

            if email_sent:
                print(f"✅ Verification email resent to {user_data['email']}")

        # Audit log: resend attempt (log whether user found, but don't reveal to requester)
        AuditLogger.log_verification_resent(
            email=resend_data.email,
            user_found=user_found,
            ip=client_ip
        )

        # ALWAYS return the same generic response (user enumeration protection)
        return jsonify({
            'success': True,
            'message': 'If an account with that email exists and is unverified, a new verification email has been sent.'
        }), 200

    except ValidationError as e:
        print(f"❌ Resend verification validation error: {e.errors()}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': e.errors()
        }), 400

    except Exception as e:
        print(f"❌ Resend verification error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """
    Request password reset endpoint
    Rate Limited: 3 per hour

    Request Body: ForgotPasswordRequest (JSON)
    Returns: 200 OK with generic message (prevents user enumeration)
    """
    try:
        # Validate request data
        forgot_data = ForgotPasswordRequest(**request.json)

        # Try to generate reset token
        with db_manager.get_db() as conn:
            user_data = AuthService.request_password_reset(conn, forgot_data.email)

        # If user exists and is active, send email
        user_found = user_data is not None
        if user_data:
            email_service = EmailService()
            email_sent = email_service.send_password_reset_email(
                to_email=user_data['email'],
                username=user_data['username'],
                token=user_data['reset_token']
            )

            if email_sent:
                print(f"🔐 Password reset email sent to {user_data['email']}")

        # Audit log: password reset requested (log whether user found, but don't reveal to requester)
        AuditLogger.log_password_reset_requested(
            email=forgot_data.email,
            user_found=user_found
        )

        # ALWAYS return the same generic response (user enumeration protection)
        return jsonify({
            'success': True,
            'message': 'If an account with that email exists, a password reset link has been sent.'
        }), 200

    except ValidationError as e:
        print(f"❌ Forgot password validation error: {e.errors()}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': e.errors()
        }), 400

    except Exception as e:
        print(f"❌ Forgot password error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Reset password endpoint
    Rate Limited: 5 per 15 minutes

    Request Body: ResetPasswordRequest (JSON)
    Returns: 200 OK with success message
    """
    try:
        # Validate request data
        reset_data = ResetPasswordRequest(**request.json)

        # Reset password
        with db_manager.get_db() as conn:
            result = AuthService.reset_password(
                conn,
                token=reset_data.token,
                new_password=reset_data.new_password
            )

        # Audit log: successful password reset
        AuditLogger.log_password_reset_completed(
            user_id=result['user_id'],
            email=result['email']
        )

        # Send confirmation email
        email_service = EmailService()
        email_service.send_password_reset_confirmation_email(
            to_email=result['email'],
            username=result['username']
        )

        print(f"✅ Password reset successful for user {result['user_id']}")
        return jsonify({
            'success': True,
            'message': result['message']
        }), 200

    except ValidationError as e:
        print(f"❌ Reset password validation error: {e.errors()}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': e.errors()
        }), 400

    except ValueError as e:
        error_msg = str(e)
        print(f"❌ Reset password error: {error_msg}")

        # Audit log: failed password reset
        token = request.json.get('token') if request.json else None
        AuditLogger.log_password_reset_failed(
            email=None,
            reason=error_msg,
            token_excerpt=token
        )

        return jsonify({
            'success': False,
            'error': error_msg
        }), 400

    except Exception as e:
        print(f"❌ Reset password internal error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


# ============================================================================
# VERIFICATION ENDPOINTS (Phase 5)
# ============================================================================

@auth_bp.route('/verification/status', methods=['GET'])
@jwt_required()
def get_verification_status():
    """
    Get email verification status for authenticated user

    Returns detailed verification info including resend capabilities
    Requires: Valid access token
    Returns: 200 OK with verification status
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
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404

            email_verified, email, token_expires, last_resent, resend_count = row

            # Calculate if user can resend (rate limiting: 1 per 5 minutes)
            can_resend = True
            if last_resent:
                from datetime import datetime
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

        print(f"✅ Verification status retrieved for user {user_id}")
        return jsonify(status), 200

    except Exception as e:
        print(f"❌ Get verification status error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/verification/resend', methods=['POST'])
@jwt_required()
def resend_verification_authenticated():
    """
    Resend verification email to authenticated user
    Rate Limited: 1 per 5 minutes per user

    Requires: Valid access token
    Returns: 200 OK with success message, 429 if rate limited
    """
    try:
        from datetime import datetime, timedelta
        from api.services.token_service import TokenService

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
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404

            username, email, email_verified, last_resent, resend_count = row

            # Check if already verified
            if email_verified:
                return jsonify({
                    'success': False,
                    'error': 'Email already verified'
                }), 400

            # Rate limiting check (5 minutes)
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
            from flask import current_app
            token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
            verification_token = token_service.generate_email_verification_token(user_id, email)
            token_expires = TokenService.get_expiration_datetime('email_verification')

            # Update database with new token and tracking
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
                'error': 'Failed to send email. Please try again later.'
            }), 500

        # Audit log
        AuditLogger.log_verification_resent(
            email=email,
            user_found=True,
            ip=client_ip
        )

        can_resend_at = datetime.utcnow() + timedelta(minutes=5)

        print(f"✅ Verification email resent to {email} (authenticated)")
        return jsonify({
            'success': True,
            'message': 'Verification email sent successfully',
            'can_resend_at': can_resend_at.isoformat()
        }), 200

    except Exception as e:
        print(f"❌ Resend verification error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
