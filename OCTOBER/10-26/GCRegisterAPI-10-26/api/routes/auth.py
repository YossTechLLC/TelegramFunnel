#!/usr/bin/env python
"""
🔐 Authentication Routes for GCRegisterAPI-10-26
Handles user signup, login, and token refresh
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from pydantic import ValidationError
from datetime import timedelta

from api.models.auth import SignupRequest, LoginRequest, RefreshTokenRequest
from api.services.auth_service import AuthService
from database.connection import db_manager

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    User signup endpoint

    Request Body: SignupRequest (JSON)
    Returns: 201 Created with user data and tokens
    """
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

        # Create user
        with db_manager.get_db() as conn:
            user = AuthService.create_user(
                conn,
                username=signup_data.username,
                email=signup_data.email,
                password=signup_data.password
            )

        # Create tokens
        tokens = AuthService.create_tokens(user['user_id'], user['username'])

        # Return response
        response = {
            **user,
            **tokens
        }

        print(f"✅ User '{signup_data.username}' signed up successfully")
        return jsonify(response), 201

    except ValidationError as e:
        print(f"❌ Signup validation error: {e.errors()}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': e.errors()
        }), 400

    except ValueError as e:
        print(f"❌ Signup error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
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
    User login endpoint

    Request Body: LoginRequest (JSON)
    Returns: 200 OK with user data and tokens
    """
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
        print(f"❌ Login error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
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
    Get current user info

    Requires: Access token in Authorization header
    Returns: 200 OK with user data
    """
    try:
        user_id = get_jwt_identity()

        # Get user from database
        with db_manager.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, email, created_at, last_login
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
                'created_at': row[3].isoformat() if row[3] else None,
                'last_login': row[4].isoformat() if row[4] else None
            }

        return jsonify(user), 200

    except Exception as e:
        print(f"❌ Get current user error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
