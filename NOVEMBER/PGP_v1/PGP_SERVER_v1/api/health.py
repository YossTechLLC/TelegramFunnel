#!/usr/bin/env python
"""
Health and monitoring blueprint.
Provides health check and status endpoints.
"""
import logging
from flask import Blueprint, jsonify, current_app, request

logger = logging.getLogger(__name__)

# Create blueprint
health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.

    Returns service health status and component availability.
    No authentication required for health checks.
    """
    try:
        # Check notification service
        notification_service = current_app.config.get('notification_service')
        notification_status = 'initialized' if notification_service else 'not_initialized'

        # Check database (future - add connection check)
        # db_manager = current_app.config.get('database_manager')
        # db_status = 'connected' if db_manager.is_connected() else 'disconnected'

        return jsonify({
            'status': 'healthy',
            'service': 'PGP_SERVER_v1',
            'components': {
                'notification_service': notification_status,
                # 'database': db_status,  # Future implementation
                'bot': 'running',  # Future - check bot status
                'flask_server': 'running'
            },
            'security': {
                'hmac': 'enabled' if current_app.config.get('hmac_auth') else 'disabled',
                'ip_whitelist': 'enabled' if current_app.config.get('ip_whitelist') else 'disabled',
                'rate_limiting': 'enabled' if current_app.config.get('rate_limiter') else 'disabled',
                'https': 'enabled' if request.is_secure else 'disabled',
                'security_headers': 'enabled'
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ [HEALTH] Error: {e}", exc_info=True)
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@health_bp.route('/status', methods=['GET'])
def status():
    """
    Detailed status endpoint with metrics.

    Future: Add metrics like request count, error rate, uptime, etc.
    No authentication required for status checks.
    """
    return jsonify({
        'status': 'ok',
        'metrics': {
            'uptime': 'TODO',
            'requests_total': 'TODO',
            'errors_total': 'TODO',
            'active_connections': 'TODO'
        }
    }), 200
