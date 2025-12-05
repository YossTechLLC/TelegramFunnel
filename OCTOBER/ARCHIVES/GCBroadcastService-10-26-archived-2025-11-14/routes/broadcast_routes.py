#!/usr/bin/env python3
"""
Broadcast Execution Routes
Handles automated broadcast execution triggered by Cloud Scheduler
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

# Import services
from services.broadcast_scheduler import BroadcastScheduler
from services.broadcast_executor import BroadcastExecutor
from services.broadcast_tracker import BroadcastTracker

# Import clients
from clients.telegram_client import TelegramClient
from clients.database_client import DatabaseClient

# Import utils
from utils.config import Config

logger = logging.getLogger(__name__)

# Create blueprint
broadcast_bp = Blueprint('broadcast', __name__)

# Initialize components (singleton pattern)
config = Config()
db_client = DatabaseClient(config)
telegram_client = TelegramClient(config.get_bot_token(), config.get_bot_username())
broadcast_tracker = BroadcastTracker(db_client, config)
broadcast_scheduler = BroadcastScheduler(db_client, config)
broadcast_executor = BroadcastExecutor(telegram_client, broadcast_tracker)


@broadcast_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for Cloud Run.

    Returns:
        JSON: Health status
    """
    return jsonify({
        'status': 'healthy',
        'service': 'GCBroadcastService-10-26',
        'timestamp': datetime.now().isoformat()
    }), 200


@broadcast_bp.route('/api/broadcast/execute', methods=['POST'])
def execute_broadcasts():
    """
    Execute all due broadcasts.

    Triggered by:
    - Cloud Scheduler (daily cron job)
    - Manual testing via curl

    Request Body (optional):
    {
        "source": "cloud_scheduler" | "manual_test"
    }

    Response:
    {
        "success": true,
        "total_broadcasts": 10,
        "successful": 9,
        "failed": 1,
        "execution_time_seconds": 45.2,
        "results": [...]
    }
    """
    start_time = datetime.now()

    try:
        # Get optional source from request
        data = request.get_json() or {}
        source = data.get('source', 'unknown')

        logger.info(f"🎯 Broadcast execution triggered by: {source}")

        # 1. Get all broadcasts due for sending
        logger.info("📋 Fetching due broadcasts...")
        broadcasts = broadcast_scheduler.get_due_broadcasts()

        if not broadcasts:
            logger.info("✅ No broadcasts due at this time")
            return jsonify({
                'success': True,
                'total_broadcasts': 0,
                'successful': 0,
                'failed': 0,
                'execution_time_seconds': 0,
                'message': 'No broadcasts due'
            }), 200

        # 2. Execute all broadcasts
        logger.info(f"📤 Executing {len(broadcasts)} broadcasts...")
        result = broadcast_executor.execute_batch(broadcasts)

        # Calculate execution time
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        logger.info(
            f"✅ Execution complete: {result['successful']}/{result['total']} successful "
            f"in {execution_time:.2f}s"
        )

        return jsonify({
            'success': True,
            'total_broadcasts': result['total'],
            'successful': result['successful'],
            'failed': result['failed'],
            'execution_time_seconds': execution_time,
            'results': result['results']
        }), 200

    except Exception as e:
        logger.error(f"❌ Error executing broadcasts: {e}", exc_info=True)

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        return jsonify({
            'success': False,
            'error': str(e),
            'execution_time_seconds': execution_time
        }), 500
