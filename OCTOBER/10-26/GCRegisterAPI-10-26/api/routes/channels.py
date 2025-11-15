#!/usr/bin/env python
"""
📺 Channel Routes for GCRegisterAPI-10-26
Handles channel registration, viewing, updating, and deletion
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from pydantic import ValidationError

from api.models.channel import ChannelRegistrationRequest, ChannelUpdateRequest
from api.services.channel_service import ChannelService
from api.services.broadcast_service import BroadcastService
from database.connection import db_manager

channels_bp = Blueprint('channels', __name__)


@channels_bp.route('/register', methods=['POST'], strict_slashes=False)
@jwt_required()
def register_channel():
    """
    Register a new channel for the authenticated user

    Request Body: ChannelRegistrationRequest (JSON)
    Returns: 201 Created
    """
    try:
        # Get authenticated user
        user_id = get_jwt_identity()
        claims = get_jwt()
        username = claims.get('username', 'unknown')

        # Validate request data
        channel_data = ChannelRegistrationRequest(**request.json)

        # Check 10-channel limit
        with db_manager.get_db() as conn:
            channel_count = ChannelService.count_user_channels(conn, user_id)
            if channel_count >= 10:
                print(f"❌ User {username} exceeded 10-channel limit")
                return jsonify({
                    'success': False,
                    'error': 'Maximum 10 channels per account'
                }), 400

        # Register channel + create broadcast entry (transactional)
        with db_manager.get_db() as conn:
            try:
                # Step 1: Register channel in main_clients_database
                ChannelService.register_channel(
                    conn,
                    user_id=user_id,
                    username=username,
                    channel_data=channel_data
                )

                # Step 2: Create broadcast_manager entry for this channel
                broadcast_id = BroadcastService.create_broadcast_entry(
                    conn,
                    client_id=user_id,
                    open_channel_id=channel_data.open_channel_id,
                    closed_channel_id=channel_data.closed_channel_id
                )

                # Step 3: Commit transaction (both operations succeed)
                conn.commit()

                print(f"✅ Channel {channel_data.open_channel_id} + Broadcast {broadcast_id} registered by {username}")
                return jsonify({
                    'success': True,
                    'message': 'Channel registered successfully',
                    'channel_id': channel_data.open_channel_id,
                    'broadcast_id': broadcast_id
                }), 201

            except Exception as e:
                # Rollback on any failure (ensures data consistency)
                conn.rollback()
                print(f"❌ Channel + Broadcast registration failed, rolled back: {e}")
                raise

    except ValidationError as e:
        print(f"❌ Channel registration validation error: {e.errors()}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': e.errors()
        }), 400

    except ValueError as e:
        print(f"❌ Channel registration error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except Exception as e:
        print(f"❌ Channel registration internal error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@channels_bp.route('/', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_channels():
    """
    Get all channels for the authenticated user

    Returns: 200 OK with list of channels
    """
    try:
        user_id = get_jwt_identity()

        # Get channels
        with db_manager.get_db() as conn:
            channels = ChannelService.get_user_channels(conn, user_id)

        return jsonify({
            'channels': channels,
            'count': len(channels),
            'max_channels': 10
        }), 200

    except Exception as e:
        print(f"❌ Error fetching channels: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@channels_bp.route('/<channel_id>', methods=['GET'])
@jwt_required()
def get_channel(channel_id):
    """
    Get details for a specific channel

    Args:
        channel_id: Channel ID

    Returns: 200 OK with channel data
    """
    try:
        user_id = get_jwt_identity()

        # Get channel
        with db_manager.get_db() as conn:
            channel = ChannelService.get_channel_by_id(conn, channel_id)

        if not channel:
            return jsonify({
                'success': False,
                'error': 'Channel not found'
            }), 404

        # Authorization check: User must own the channel
        if channel['client_id'] != user_id:
            print(f"❌ Unauthorized access to channel {channel_id}")
            return jsonify({
                'success': False,
                'error': 'Unauthorized'
            }), 403

        return jsonify(channel), 200

    except Exception as e:
        print(f"❌ Error fetching channel: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@channels_bp.route('/<channel_id>', methods=['PUT'])
@jwt_required()
def update_channel(channel_id):
    """
    Update an existing channel

    Args:
        channel_id: Channel ID

    Request Body: ChannelUpdateRequest (JSON, partial)
    Returns: 200 OK with updated channel
    """
    try:
        user_id = get_jwt_identity()

        # Validate request data
        update_data = ChannelUpdateRequest(**request.json)

        # Get existing channel
        with db_manager.get_db() as conn:
            channel = ChannelService.get_channel_by_id(conn, channel_id)

            if not channel:
                return jsonify({
                    'success': False,
                    'error': 'Channel not found'
                }), 404

            # Authorization check
            if channel['client_id'] != user_id:
                print(f"❌ Unauthorized update attempt on channel {channel_id}")
                return jsonify({
                    'success': False,
                    'error': 'Unauthorized'
                }), 403

            # Update channel
            ChannelService.update_channel(conn, channel_id, update_data)

        # Fetch updated channel
        with db_manager.get_db() as conn:
            updated_channel = ChannelService.get_channel_by_id(conn, channel_id)

        print(f"✅ Channel {channel_id} updated successfully")
        return jsonify({
            'success': True,
            'message': 'Channel updated successfully',
            'channel': updated_channel
        }), 200

    except ValidationError as e:
        print(f"❌ Channel update validation error: {e.errors()}")
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'details': e.errors()
        }), 400

    except Exception as e:
        print(f"❌ Error updating channel: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@channels_bp.route('/<channel_id>', methods=['DELETE'])
@jwt_required()
def delete_channel(channel_id):
    """
    Delete a channel

    Args:
        channel_id: Channel ID

    Returns: 200 OK
    """
    try:
        user_id = get_jwt_identity()

        # Get existing channel
        with db_manager.get_db() as conn:
            channel = ChannelService.get_channel_by_id(conn, channel_id)

            if not channel:
                return jsonify({
                    'success': False,
                    'error': 'Channel not found'
                }), 404

            # Authorization check
            if channel['client_id'] != user_id:
                print(f"❌ Unauthorized delete attempt on channel {channel_id}")
                return jsonify({
                    'success': False,
                    'error': 'Unauthorized'
                }), 403

            # Delete channel (CASCADE will auto-delete broadcast_manager entry)
            ChannelService.delete_channel(conn, channel_id)

        print(f"✅ Channel {channel_id} deleted successfully (broadcast_manager entry CASCADE deleted)")
        return jsonify({
            'success': True,
            'message': 'Channel deleted successfully'
        }), 200

    except Exception as e:
        print(f"❌ Error deleting channel: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
