#!/usr/bin/env python
"""
🔧 Account Management Routes for GCRegisterAPI-10-26
Handles email changes and password changes (requires verified email)
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from pydantic import ValidationError
from datetime import datetime, timedelta

from api.models.auth import (
    EmailChangeRequest, EmailChangeResponse,
    PasswordChangeRequest, PasswordChangeResponse
)
from api.services.auth_service import AuthService
from api.services.token_service import TokenService
from api.services.email_service import EmailService
from api.utils.audit_logger import AuditLogger
from database.connection import db_manager
from itsdangerous import SignatureExpired, BadSignature

account_bp = Blueprint('account', __name__)


@account_bp.route('/change-email', methods=['POST'])
@jwt_required()
def change_email():
    """
    Request email change (requires verified email + password)
    Rate Limited: 3 per hour

    Security Checks:
    1. Email must already be verified (403 if not)
    2. Password must be correct (401 if wrong)
    3. New email must be different (400 if same)
    4. New email must not be in use (400 if taken)

    Request Body: EmailChangeRequest (JSON)
    Returns: 200 OK with EmailChangeResponse
    """
    client_ip = request.remote_addr

    try:
        user_id = get_jwt_identity()

        # Validate request data
        change_request = EmailChangeRequest(**request.json)

        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Get user info
            cursor.execute("""
                SELECT username, email, email_verified, password_hash
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404

            username, current_email, email_verified, password_hash = row

            # SECURITY CHECK 1: Email must be verified
            if not email_verified:
                return jsonify({
                    'success': False,
                    'error': 'Email must be verified before changing to a new email'
                }), 403

            # SECURITY CHECK 2: Verify password
            if not AuthService.verify_password(change_request.password, password_hash):
                # Audit log: failed password check
                AuditLogger.log_email_change_failed(
                    user_id=user_id,
                    email=current_email,
                    new_email=change_request.new_email,
                    reason='Invalid password',
                    ip=client_ip
                )
                return jsonify({
                    'success': False,
                    'error': 'Invalid password'
                }), 401

            # SECURITY CHECK 3: New email must be different
            if change_request.new_email == current_email:
                return jsonify({
                    'success': False,
                    'error': 'New email must be different from current email'
                }), 400

            # SECURITY CHECK 4: New email must not be in use
            cursor.execute("""
                SELECT user_id FROM registered_users
                WHERE email = %s OR pending_email = %s
            """, (change_request.new_email, change_request.new_email))

            if cursor.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'Email address already in use'
                }), 400

            # Generate email change token
            token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
            email_change_token = token_service.generate_email_change_token(
                user_id,
                change_request.new_email
            )
            token_expires = TokenService.get_expiration_datetime('email_change')

            # Store pending email change in database
            cursor.execute("""
                UPDATE registered_users
                SET pending_email = %s,
                    pending_email_token = %s,
                    pending_email_token_expires = %s,
                    pending_email_old_notification_sent = TRUE,
                    last_email_change_requested_at = NOW(),
                    updated_at = NOW()
                WHERE user_id = %s
            """, (change_request.new_email, email_change_token, token_expires, user_id))

            cursor.close()

        # Send notification to OLD email
        email_service = EmailService()
        old_email_sent = email_service.send_email_change_notification(
            to_email=current_email,
            username=username,
            new_email=change_request.new_email
        )

        # Send confirmation to NEW email
        confirmation_url = f"{current_app.config.get('FRONTEND_URL', 'http://localhost:3000')}/confirm-email-change?token={email_change_token}"
        new_email_sent = email_service.send_email_change_confirmation(
            to_email=change_request.new_email,
            username=username,
            confirmation_url=confirmation_url
        )

        # Audit log: email change requested
        AuditLogger.log_email_change_requested(
            user_id=user_id,
            old_email=current_email,
            new_email=change_request.new_email,
            ip=client_ip
        )

        print(f"📧 Email change requested: {current_email} → {change_request.new_email}")
        return jsonify({
            'success': True,
            'message': 'Email change initiated. Please check both email addresses.',
            'pending_email': change_request.new_email,
            'notification_sent_to_old': old_email_sent,
            'confirmation_sent_to_new': new_email_sent
        }), 200

    except ValidationError as e:
        print(f"❌ Email change validation error: {e.errors()}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': e.errors()
        }), 400

    except Exception as e:
        print(f"❌ Email change error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@account_bp.route('/confirm-email-change', methods=['GET'])
def confirm_email_change():
    """
    Confirm email change with token from email link

    Query Params: token (email change token from confirmation email)
    Returns: 200 OK with success message
    """
    try:
        # Get token from query parameter
        token = request.args.get('token')

        if not token:
            return jsonify({
                'success': False,
                'error': 'Confirmation token is required'
            }), 400

        # Verify token
        token_service = TokenService(current_app.config.get('SIGNUP_SECRET_KEY'))
        token_data = token_service.verify_email_change_token(token)

        user_id = token_data['user_id']
        new_email = token_data['new_email']

        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Get user and verify pending email change
            cursor.execute("""
                SELECT username, email, pending_email, pending_email_token,
                       pending_email_token_expires
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404

            username, current_email, pending_email, db_token, token_expires = row

            # Verify token matches database
            if db_token != token:
                return jsonify({
                    'success': False,
                    'error': 'Invalid confirmation token'
                }), 400

            # Check token expiration
            if token_expires and token_expires < datetime.utcnow():
                return jsonify({
                    'success': False,
                    'error': 'Confirmation token has expired'
                }), 400

            # Verify pending email matches token
            if pending_email != new_email:
                return jsonify({
                    'success': False,
                    'error': 'Email mismatch - token invalid'
                }), 400

            # RACE CONDITION CHECK: Verify new email still available
            cursor.execute("""
                SELECT user_id FROM registered_users
                WHERE email = %s AND user_id != %s
            """, (new_email, user_id))

            if cursor.fetchone():
                # Email was taken by another user during the process
                cursor.execute("""
                    UPDATE registered_users
                    SET pending_email = NULL,
                        pending_email_token = NULL,
                        pending_email_token_expires = NULL,
                        pending_email_old_notification_sent = FALSE
                    WHERE user_id = %s
                """, (user_id,))
                cursor.close()

                return jsonify({
                    'success': False,
                    'error': 'Email address no longer available'
                }), 409

            # Update email and clear pending fields
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

        # Send success email to new address
        email_service = EmailService()
        email_service.send_email_change_success(
            to_email=new_email,
            username=username
        )

        # Audit log: email change completed
        AuditLogger.log_email_changed(
            user_id=user_id,
            old_email=current_email,
            new_email=new_email
        )

        print(f"✅ Email changed successfully: {current_email} → {new_email}")
        return jsonify({
            'success': True,
            'message': 'Email address updated successfully',
            'redirect_url': '/dashboard'
        }), 200

    except SignatureExpired:
        print(f"⏰ Email change token expired")
        return jsonify({
            'success': False,
            'error': 'Confirmation link has expired. Please request a new email change.'
        }), 400

    except BadSignature:
        print(f"❌ Invalid email change token signature")
        return jsonify({
            'success': False,
            'error': 'Invalid confirmation link'
        }), 400

    except Exception as e:
        print(f"❌ Email change confirmation error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@account_bp.route('/cancel-email-change', methods=['POST'])
@jwt_required()
def cancel_email_change():
    """
    Cancel pending email change

    Requires: Valid access token
    Returns: 200 OK with success message
    """
    try:
        user_id = get_jwt_identity()
        client_ip = request.remote_addr

        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Get pending email for audit log
            cursor.execute("""
                SELECT email, pending_email
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404

            current_email, pending_email = row

            # Clear pending email change
            cursor.execute("""
                UPDATE registered_users
                SET pending_email = NULL,
                    pending_email_token = NULL,
                    pending_email_token_expires = NULL,
                    pending_email_old_notification_sent = FALSE,
                    updated_at = NOW()
                WHERE user_id = %s
            """, (user_id,))

            cursor.close()

        # Audit log: email change cancelled
        if pending_email:
            AuditLogger.log_email_change_cancelled(
                user_id=user_id,
                email=current_email,
                cancelled_email=pending_email,
                ip=client_ip
            )

        print(f"🚫 Email change cancelled for user {user_id}")
        return jsonify({
            'success': True,
            'message': 'Email change request cancelled'
        }), 200

    except Exception as e:
        print(f"❌ Cancel email change error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@account_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Change password (requires verified email + current password)
    Rate Limited: 5 per 15 minutes

    Security Checks:
    1. Email must be verified (403 if not)
    2. Current password must be correct (401 if wrong)
    3. New password must be different (400 if same)
    4. New password must meet strength requirements (Pydantic validator)

    Request Body: PasswordChangeRequest (JSON)
    Returns: 200 OK with PasswordChangeResponse
    """
    client_ip = request.remote_addr

    try:
        user_id = get_jwt_identity()

        # Validate request data
        change_request = PasswordChangeRequest(**request.json)

        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Get user info
            cursor.execute("""
                SELECT username, email, email_verified, password_hash
                FROM registered_users
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404

            username, email, email_verified, current_password_hash = row

            # SECURITY CHECK 1: Email must be verified
            if not email_verified:
                return jsonify({
                    'success': False,
                    'error': 'Email must be verified before changing password'
                }), 403

            # SECURITY CHECK 2: Verify current password
            if not AuthService.verify_password(change_request.current_password, current_password_hash):
                # Audit log: failed password check
                AuditLogger.log_password_change_failed(
                    user_id=user_id,
                    email=email,
                    reason='Invalid current password',
                    ip=client_ip
                )
                return jsonify({
                    'success': False,
                    'error': 'Current password is incorrect'
                }), 401

            # SECURITY CHECK 3: New password must be different
            if AuthService.verify_password(change_request.new_password, current_password_hash):
                return jsonify({
                    'success': False,
                    'error': 'New password must be different from current password'
                }), 400

            # Hash new password
            new_password_hash = AuthService.hash_password(change_request.new_password)

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
        email_service.send_password_reset_confirmation_email(
            to_email=email,
            username=username
        )

        # Audit log: password change successful
        AuditLogger.log_password_changed(
            user_id=user_id,
            email=email,
            ip=client_ip
        )

        print(f"🔐 Password changed successfully for user {user_id}")
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        }), 200

    except ValidationError as e:
        print(f"❌ Password change validation error: {e.errors()}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': e.errors()
        }), 400

    except Exception as e:
        print(f"❌ Password change error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
