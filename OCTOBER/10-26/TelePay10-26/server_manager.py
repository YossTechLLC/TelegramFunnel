#!/usr/bin/env python
import socket
from flask import Flask, request, jsonify
import asyncio

class ServerManager:
    def __init__(self):
        self.flask_app = Flask(__name__)
        self.port = None
        self.notification_service = None  # 🆕 Will be set by AppInitializer

        # Register routes
        self._register_routes()

    def _register_routes(self):
        """Register all Flask routes"""
        # 🆕 Notification endpoint for NOTIFICATION_MANAGEMENT_ARCHITECTURE
        @self.flask_app.route('/send-notification', methods=['POST'])
        def handle_notification_request():
            """
            Handle notification request from np-webhook

            Request body:
            {
                "open_channel_id": "-1003268562225",
                "payment_type": "subscription" | "donation",
                "payment_data": {
                    "user_id": 123456789,
                    "username": "john_doe",
                    "amount_crypto": "0.00034",
                    "amount_usd": "9.99",
                    "crypto_currency": "ETH",
                    "timestamp": "2025-11-11 14:32:15 UTC",
                    // For subscriptions:
                    "tier": 3,
                    "tier_price": "9.99",
                    "duration_days": 30
                }
            }
            """
            try:
                data = request.get_json()

                print(f"📬 [NOTIFICATION API] Received request: {data}")

                # Validate required fields
                required_fields = ['open_channel_id', 'payment_type', 'payment_data']
                for field in required_fields:
                    if field not in data:
                        return jsonify({'error': f'Missing field: {field}'}), 400

                # Check if notification service is initialized
                if not self.notification_service:
                    print(f"⚠️ [NOTIFICATION API] Notification service not initialized")
                    return jsonify({'error': 'Notification service not available'}), 503

                # Send notification asynchronously
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                success = loop.run_until_complete(
                    self.notification_service.send_payment_notification(
                        open_channel_id=data['open_channel_id'],
                        payment_type=data['payment_type'],
                        payment_data=data['payment_data']
                    )
                )

                loop.close()

                if success:
                    return jsonify({'status': 'success', 'message': 'Notification sent'}), 200
                else:
                    return jsonify({'status': 'failed', 'message': 'Notification not sent'}), 200

            except Exception as e:
                print(f"❌ [NOTIFICATION API] Error: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'notification_service': 'initialized' if self.notification_service else 'not_initialized'
            }), 200

    def set_notification_service(self, notification_service):
        """Set the notification service instance"""
        self.notification_service = notification_service
        print("📬 [SERVER] Notification service configured")
    
    def find_free_port(self, start_port=5000, max_tries=20):
        """Find a free port for the Flask server."""
        for port in range(start_port, start_port + max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', port)) != 0:
                    return port
        raise OSError("No available port found for Flask.")
    
    def start(self):
        """Start the Flask server."""
        self.port = self.find_free_port(5000)
        print(f"🔗 Running Flask on port {self.port}")
        self.flask_app.run(host="0.0.0.0", port=self.port)
    
    def get_app(self):
        """Get the Flask app instance."""
        return self.flask_app