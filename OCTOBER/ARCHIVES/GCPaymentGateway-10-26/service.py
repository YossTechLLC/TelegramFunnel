#!/usr/bin/env python
"""
GCPaymentGateway-10-26: Self-contained payment invoice creation service
Replaces: TelePay10-26/start_np_gateway.py (PaymentGatewayManager class)
"""

from flask import Flask, request, jsonify
from config_manager import ConfigManager
from database_manager import DatabaseManager
from payment_handler import PaymentHandler
import sys


def create_app():
    """
    Application factory for GCPaymentGateway.
    Creates and configures the Flask application with all dependencies.

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)

    print("🚀 [GATEWAY] Initializing GCPaymentGateway-10-26...")

    # Initialize configuration (fetch secrets from Secret Manager)
    try:
        config_manager = ConfigManager()
        config = config_manager.initialize_config()
        app.config.update(config)
        print("✅ [CONFIG] Configuration loaded successfully")
    except Exception as e:
        print(f"❌ [CONFIG] Failed to load configuration: {e}")
        sys.exit(1)

    # Initialize database manager
    try:
        db_manager = DatabaseManager(config)
        app.db = db_manager
        print("✅ [DATABASE] Database manager initialized")
    except Exception as e:
        print(f"❌ [DATABASE] Failed to initialize database: {e}")
        sys.exit(1)

    # Initialize payment handler
    try:
        payment_handler = PaymentHandler(config, db_manager)
        app.payment_handler = payment_handler
        print("✅ [PAYMENT] Payment handler initialized")
    except Exception as e:
        print(f"❌ [PAYMENT] Failed to initialize payment handler: {e}")
        sys.exit(1)

    # Register routes
    register_routes(app)

    print("✅ [GATEWAY] GCPaymentGateway-10-26 ready to accept requests")

    return app


def register_routes(app):
    """
    Register all Flask routes for the application.

    Args:
        app (Flask): Flask application instance
    """

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint for Cloud Run.

        Returns:
            JSON response with status
        """
        return jsonify({"status": "healthy", "service": "gcpaymentgateway-10-26"}), 200


    @app.route("/create-invoice", methods=["POST"])
    def create_invoice():
        """
        Create a payment invoice via NowPayments API.

        Request JSON:
        {
            "user_id": 6271402111,
            "amount": 9.99,
            "open_channel_id": "-1003268562225",
            "subscription_time_days": 30,
            "payment_type": "subscription",
            "tier": 1,
            "order_id": "PGP-6271402111|-1003268562225"  # Optional
        }

        Returns:
            JSON response with invoice details or error
        """
        print("💳 [GATEWAY] Received invoice creation request")

        # Get request data
        try:
            data = request.get_json()
            if not data:
                print("❌ [GATEWAY] No JSON data provided")
                return jsonify({
                    "success": False,
                    "error": "No JSON data provided"
                }), 400
        except Exception as e:
            print(f"❌ [GATEWAY] Failed to parse JSON: {e}")
            return jsonify({
                "success": False,
                "error": f"Invalid JSON: {str(e)}"
            }), 400

        # Log request details
        print(f"📋 [GATEWAY] Request data:")
        print(f"   👤 User ID: {data.get('user_id')}")
        print(f"   💵 Amount: ${data.get('amount')}")
        print(f"   📺 Channel ID: {data.get('open_channel_id')}")
        print(f"   🎫 Payment Type: {data.get('payment_type')}")
        print(f"   📅 Subscription Days: {data.get('subscription_time_days')}")

        # Create invoice using payment handler
        try:
            result = app.payment_handler.create_invoice(data)

            if result.get("success"):
                print(f"✅ [GATEWAY] Invoice created successfully")
                print(f"   🆔 Invoice ID: {result.get('invoice_id')}")
                print(f"   📄 Order ID: {result.get('order_id')}")
                return jsonify(result), 200
            else:
                print(f"❌ [GATEWAY] Invoice creation failed: {result.get('error')}")
                return jsonify(result), result.get("status_code", 500)

        except Exception as e:
            print(f"❌ [GATEWAY] Unexpected error creating invoice: {e}")
            return jsonify({
                "success": False,
                "error": f"Internal server error: {str(e)}"
            }), 500


# Create app instance for gunicorn
app = create_app()

if __name__ == "__main__":
    """
    Entry point for local development.
    Cloud Run uses gunicorn in production.
    """
    import os

    port = int(os.environ.get("PORT", 8080))

    print(f"🌐 [GATEWAY] Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
