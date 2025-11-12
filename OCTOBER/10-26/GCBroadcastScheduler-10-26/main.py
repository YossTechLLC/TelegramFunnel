#!/usr/bin/env python3
"""
GCBroadcastScheduler-10-26 - Main Application
Flask application for automated and manual broadcast management
"""

import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import our modules
from config_manager import ConfigManager
from database_manager import DatabaseManager
from telegram_client import TelegramClient
from broadcast_tracker import BroadcastTracker
from broadcast_scheduler import BroadcastScheduler
from broadcast_executor import BroadcastExecutor
from broadcast_web_api import create_broadcast_web_api

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Configure CORS
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://www.paygateprime.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# Configure JWT (MUST be before initializing components that use JWT)
from flask_jwt_extended import JWTManager

logger.info("🔐 Initializing JWT authentication...")
config_manager_for_jwt = ConfigManager()
jwt_secret_key = config_manager_for_jwt.get_jwt_secret_key()
app.config['JWT_SECRET_KEY'] = jwt_secret_key
app.config['JWT_ALGORITHM'] = 'HS256'
app.config['JWT_DECODE_LEEWAY'] = 10  # 10 seconds leeway for clock skew
jwt = JWTManager(app)
logger.info("✅ JWT authentication initialized")

# Initialize components
logger.info("🚀 Initializing GCBroadcastScheduler-10-26...")

try:
    # 1. ConfigManager - fetch configuration from Secret Manager
    logger.info("⚙️  Initializing ConfigManager...")
    config_manager = ConfigManager()

    # 2. DatabaseManager - handle database operations
    logger.info("🗄️  Initializing DatabaseManager...")
    database_manager = DatabaseManager(config_manager)

    # 3. TelegramClient - send messages to Telegram
    logger.info("🤖 Initializing TelegramClient...")
    bot_token = config_manager.get_bot_token()
    bot_username = config_manager.get_bot_username()
    telegram_client = TelegramClient(bot_token, bot_username)

    # 4. BroadcastTracker - track broadcast state
    logger.info("📊 Initializing BroadcastTracker...")
    broadcast_tracker = BroadcastTracker(database_manager, config_manager)

    # 5. BroadcastScheduler - scheduling logic
    logger.info("⏰ Initializing BroadcastScheduler...")
    broadcast_scheduler = BroadcastScheduler(database_manager, config_manager)

    # 6. BroadcastExecutor - execute broadcasts
    logger.info("📤 Initializing BroadcastExecutor...")
    broadcast_executor = BroadcastExecutor(telegram_client, broadcast_tracker)

    # 7. BroadcastWebAPI - API endpoints
    logger.info("🌐 Initializing BroadcastWebAPI...")
    broadcast_api = create_broadcast_web_api(
        broadcast_scheduler,
        database_manager,
        config_manager
    )
    app.register_blueprint(broadcast_api)

    logger.info("✅ All components initialized successfully")

except Exception as e:
    logger.error(f"❌ Fatal error during initialization: {e}", exc_info=True)
    raise


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for Cloud Run.

    Returns:
        JSON response with health status
    """
    return jsonify({
        'status': 'healthy',
        'service': 'GCBroadcastScheduler-10-26',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/broadcast/execute', methods=['POST'])
def execute_broadcasts():
    """
    Execute all due broadcasts.

    This endpoint is called by Cloud Scheduler (daily cron job).

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
        # Get optional source from request body
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

        # Calculate execution time even on error
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        return jsonify({
            'success': False,
            'error': str(e),
            'execution_time_seconds': execution_time
        }), 500


@app.before_request
def log_request():
    """Log all incoming requests."""
    logger.info(f"📨 {request.method} {request.path} from {request.remote_addr}")


@app.after_request
def log_response(response):
    """Log all outgoing responses."""
    logger.info(f"📮 {request.method} {request.path} -> {response.status_code}")
    return response


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"❌ Internal server error: {error}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500


# JWT error handlers
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """Handle expired JWT tokens"""
    logger.warning("⚠️ JWT token expired")
    return jsonify({
        'error': 'Token expired',
        'message': 'Session expired. Please log in again.'
    }), 401


@jwt.invalid_token_loader
def invalid_token_callback(error):
    """Handle invalid JWT tokens"""
    logger.warning(f"⚠️ Invalid JWT token: {error}")
    return jsonify({
        'error': 'Invalid token',
        'message': 'Session expired. Please log in again.'
    }), 401


@jwt.unauthorized_loader
def unauthorized_callback(error):
    """Handle missing JWT tokens"""
    logger.warning("⚠️ Missing JWT token")
    return jsonify({
        'error': 'Missing Authorization header',
        'message': 'Authentication required'
    }), 401


if __name__ == "__main__":
    # For local development only
    # Production uses gunicorn (see Dockerfile)
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🌟 Starting development server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
