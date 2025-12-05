#!/usr/bin/env python3
"""
Manual Trigger API Routes
JWT-authenticated endpoints for manual broadcast triggers from website
"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

# Import services
from services.broadcast_scheduler import BroadcastScheduler

# Import clients
from clients.database_client import DatabaseClient

# Import utils
from utils.config import Config
from utils.auth import extract_client_id

logger = logging.getLogger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Initialize components
config = Config()
db_client = DatabaseClient(config)
broadcast_scheduler = BroadcastScheduler(db_client, config)


@api_bp.route('/broadcast/trigger', methods=['POST'])
@jwt_required()
def trigger_broadcast():
    """
    Manually trigger a broadcast for a specific channel pair.

    Requires JWT authentication (from website login).
    Enforces rate limiting (default: 5 minutes between triggers).

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

    Response (Unauthorized):
    {
        "success": false,
        "error": "Unauthorized: User does not own this channel"
    }
    """
    try:
        # Extract and validate request data
        data = request.get_json()

        if not data or 'broadcast_id' not in data:
            logger.warning("⚠️ Missing broadcast_id in request")
            return jsonify({'error': 'Missing broadcast_id'}), 400

        broadcast_id = data['broadcast_id']

        # Extract client ID from JWT
        client_id = extract_client_id()

        if not client_id:
            logger.warning("⚠️ Invalid JWT payload")
            return jsonify({'error': 'Invalid token payload'}), 401

        logger.info(f"📨 Manual trigger request: broadcast={broadcast_id[:8]}..., client={client_id[:8]}...")

        # Check rate limit
        rate_limit_check = broadcast_scheduler.check_manual_trigger_rate_limit(
            broadcast_id, client_id
        )

        if not rate_limit_check['allowed']:
            logger.warning(f"⏳ Rate limit blocked: {rate_limit_check['reason']}")
            return jsonify({
                'success': False,
                'error': rate_limit_check['reason'],
                'retry_after_seconds': rate_limit_check['retry_after_seconds']
            }), 429

        # Queue broadcast for immediate execution
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


@api_bp.route('/broadcast/status/<broadcast_id>', methods=['GET'])
@jwt_required()
def get_broadcast_status(broadcast_id):
    """
    Get status and statistics for a specific broadcast.

    Requires JWT authentication.
    Verifies user owns the broadcast before returning data.

    Response:
    {
        "broadcast_id": "uuid",
        "broadcast_status": "completed",
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
        # Extract client ID from JWT
        client_id = extract_client_id()

        if not client_id:
            return jsonify({'error': 'Invalid token payload'}), 401

        logger.info(f"📊 Status request: broadcast={broadcast_id[:8]}..., client={client_id[:8]}...")

        # Fetch statistics
        stats = db_client.get_broadcast_statistics(broadcast_id)

        if not stats:
            logger.warning(f"⚠️ Broadcast not found: {broadcast_id[:8]}...")
            return jsonify({'error': 'Broadcast not found'}), 404

        # Verify ownership
        broadcast_entry = db_client.fetch_broadcast_by_id(broadcast_id)

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
