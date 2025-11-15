#!/usr/bin/env python3
"""
BroadcastWebAPI - API endpoints for manual broadcast triggers
Handles authentication, authorization, and rate limiting for website requests
"""

import logging
from typing import Dict, Any
from flask import Blueprint, request, jsonify
from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from broadcast_scheduler import BroadcastScheduler
from database_manager import DatabaseManager
from config_manager import ConfigManager

logger = logging.getLogger(__name__)

# Create Flask blueprint
broadcast_api = Blueprint('broadcast_api', __name__)


def create_broadcast_web_api(
    broadcast_scheduler: BroadcastScheduler,
    database_manager: DatabaseManager,
    config_manager: ConfigManager
):
    """
    Create and configure the BroadcastWebAPI.

    Args:
        broadcast_scheduler: BroadcastScheduler instance
        database_manager: DatabaseManager instance
        config_manager: ConfigManager instance

    Returns:
        Flask Blueprint with registered routes
    """

    def get_client_id_from_jwt():
        """
        Extract client_id from JWT token.

        Returns:
            str: User ID from JWT 'sub' claim
        """
        try:
            # Flask-JWT-Extended automatically validates and decodes the token
            client_id = get_jwt_identity()

            if not client_id:
                logger.warning("⚠️ Invalid token payload - missing identity")
                return None

            logger.debug(f"✅ Authenticated client: {client_id[:8]}...")
            return client_id

        except Exception as e:
            logger.error(f"❌ Error extracting client ID: {e}", exc_info=True)
            return None

    @broadcast_api.route('/api/broadcast/trigger', methods=['POST'])
    @jwt_required()
    def trigger_broadcast():
        """
        Manually trigger a broadcast for a specific channel pair.

        Request Body:
        {
            "broadcast_id": "uuid"
        }

        Response (Success):
        {
            "success": true,
            "message": "Broadcast queued for sending",
            "broadcast_id": "uuid"
        }

        Response (Rate Limited):
        {
            "success": false,
            "error": "Rate limit exceeded",
            "retry_after_seconds": 180
        }
        """
        try:
            data = request.get_json()

            if not data or 'broadcast_id' not in data:
                logger.warning("⚠️ Missing broadcast_id in request")
                return jsonify({'error': 'Missing broadcast_id'}), 400

            broadcast_id = data['broadcast_id']
            client_id = get_client_id_from_jwt()

            if not client_id:
                return jsonify({'error': 'Invalid token payload'}), 401

            logger.info(f"📨 Manual trigger request: broadcast={broadcast_id[:8]}..., client={client_id[:8]}...")

            # Check rate limit
            rate_limit_check = broadcast_scheduler.check_manual_trigger_rate_limit(
                broadcast_id, client_id
            )

            if not rate_limit_check['allowed']:
                logger.warning(
                    f"⏳ Rate limit blocked: {rate_limit_check['reason']}"
                )
                return jsonify({
                    'success': False,
                    'error': rate_limit_check['reason'],
                    'retry_after_seconds': rate_limit_check['retry_after_seconds']
                }), 429

            # Queue broadcast
            success = broadcast_scheduler.queue_manual_broadcast(broadcast_id)

            if success:
                logger.info(f"✅ Manual broadcast queued: {broadcast_id[:8]}...")
                return jsonify({
                    'success': True,
                    'message': 'Broadcast queued for sending',
                    'broadcast_id': broadcast_id
                }), 200
            else:
                logger.error(f"❌ Failed to queue broadcast: {broadcast_id[:8]}...")
                return jsonify({
                    'success': False,
                    'error': 'Failed to queue broadcast'
                }), 500

        except Exception as e:
            logger.error(f"❌ Error in trigger_broadcast: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500

    @broadcast_api.route('/api/broadcast/status/<broadcast_id>', methods=['GET'])
    @jwt_required()
    def get_broadcast_status(broadcast_id):
        """
        Get status of a specific broadcast.

        Response:
        {
            "broadcast_id": "uuid",
            "status": "completed",
            "last_sent_time": "2025-11-11T12:00:00Z",
            "next_send_time": "2025-11-12T12:00:00Z",
            "total_broadcasts": 10,
            "successful_broadcasts": 9,
            "failed_broadcasts": 1,
            "consecutive_failures": 0,
            "is_active": true,
            "manual_trigger_count": 2
        }
        """
        try:
            client_id = get_client_id_from_jwt()

            if not client_id:
                return jsonify({'error': 'Invalid token payload'}), 401

            logger.info(f"📊 Status request: broadcast={broadcast_id[:8]}..., client={client_id[:8]}...")

            # Fetch statistics
            stats = database_manager.get_broadcast_statistics(broadcast_id)

            if not stats:
                logger.warning(f"⚠️ Broadcast not found: {broadcast_id[:8]}...")
                return jsonify({'error': 'Broadcast not found'}), 404

            # Verify ownership (client_id should match)
            # Note: stats contains all broadcast_manager fields
            # We need to fetch the entry to check client_id
            broadcast_entry = database_manager.fetch_broadcast_by_id(broadcast_id)

            if not broadcast_entry or str(broadcast_entry.get('client_id')) != str(client_id):
                logger.warning(f"⚠️ Unauthorized status request: {broadcast_id[:8]}...")
                return jsonify({'error': 'Unauthorized'}), 403

            # Convert datetime objects to ISO format strings
            for field in ['last_sent_time', 'next_send_time', 'last_error_time']:
                if field in stats and stats[field]:
                    stats[field] = stats[field].isoformat()

            logger.info(f"✅ Status retrieved: {broadcast_id[:8]}...")
            return jsonify(stats), 200

        except Exception as e:
            logger.error(f"❌ Error in get_broadcast_status: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500

    return broadcast_api
