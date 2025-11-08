#!/usr/bin/env python
"""
🚀 GCRegisterAPI-10-26: REST API for Channel Registration
Flask REST API (no templates, JSON-only responses)

Architecture:
- TypeScript + React SPA frontend (GCRegisterWeb-10-26)
- Flask REST API backend (this service)
- PostgreSQL database (Cloud SQL)
- JWT authentication (stateless)
- CORS-enabled for SPA

Deployment:
- Cloud Run (serverless)
- Environment: Production
- Region: us-central1
"""
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config_manager import config_manager
from api.routes.auth import auth_bp
from api.routes.channels import channels_bp
from api.routes.mappings import mappings_bp

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config = config_manager.get_config()

# Flask configuration
app.config['JWT_SECRET_KEY'] = config['jwt_secret_key']
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 900  # 15 minutes
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 2592000  # 30 days

# Initialize JWT
jwt = JWTManager(app)

# CORS configuration (allow frontend SPA)
# Note: Must be explicit when using credentials
# Strip whitespace from CORS origin (Secret Manager may include newlines)
cors_origins = [
    config['cors_origin'].strip(),
    "http://localhost:5173",  # Local dev
    "http://localhost:3000"   # Alternative local dev
]

# Initialize CORS
CORS(app,
     resources={r"/api/*": {"origins": cors_origins}},
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"],
     expose_headers=["Content-Type", "Authorization"],
     supports_credentials=True,
     max_age=3600)

# Explicit CORS headers for all responses (backup method)
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    print(f"🔍 CORS Debug - Origin: {origin}, Allowed origins: {cors_origins}")
    print(f"🔍 CORS Debug - Origin in list: {origin in cors_origins}")

    if origin in cors_origins:
        print(f"✅ Adding CORS headers for origin: {origin}")
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Authorization'
    else:
        print(f"❌ Origin not in allowed list or missing")

    print(f"🔍 Response headers: {dict(response.headers)}")
    return response

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(channels_bp, url_prefix='/api/channels')
app.register_blueprint(mappings_bp, url_prefix='/api/mappings')


# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint for Cloud Run"""
    return jsonify({
        'status': 'healthy',
        'service': 'GCRegisterAPI-10-26 REST API',
        'version': '1.0',
        'architecture': 'TypeScript + React SPA → Flask REST API',
        'database': 'PostgreSQL (Cloud SQL)',
        'authentication': 'JWT (stateless)'
    }), 200


# Root endpoint (info)
@app.route('/', methods=['GET'])
def root():
    """Root endpoint providing API information"""
    return jsonify({
        'service': 'GCRegisterAPI-10-26',
        'description': 'REST API for Telegram Channel Registration',
        'version': '1.0',
        'endpoints': {
            'authentication': {
                'POST /api/auth/signup': 'User registration',
                'POST /api/auth/login': 'User login',
                'POST /api/auth/refresh': 'Token refresh',
                'GET /api/auth/me': 'Get current user'
            },
            'channels': {
                'POST /api/channels/register': 'Register new channel',
                'GET /api/channels': 'Get user channels',
                'GET /api/channels/<id>': 'Get channel details',
                'PUT /api/channels/<id>': 'Update channel',
                'DELETE /api/channels/<id>': 'Delete channel'
            },
            'mappings': {
                'GET /api/mappings/currency-network': 'Get currency/network mappings'
            },
            'health': {
                'GET /api/health': 'Health check'
            }
        },
        'documentation': 'See GCREGISTER_MODERNIZATION_ARCHITECTURE.md',
        'frontend': 'GCRegisterWeb-10-26 (Cloud Storage + CDN)',
        'cors': 'Enabled for www.paygateprime.com'
    }), 200


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'message': 'The requested API endpoint does not exist'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """Handle expired JWT tokens"""
    return jsonify({
        'success': False,
        'error': 'Token expired',
        'message': 'The access token has expired. Please refresh your token or login again.'
    }), 401


@jwt.invalid_token_loader
def invalid_token_callback(error):
    """Handle invalid JWT tokens"""
    return jsonify({
        'success': False,
        'error': 'Invalid token',
        'message': 'The provided token is invalid'
    }), 401


@jwt.unauthorized_loader
def unauthorized_callback(error):
    """Handle missing JWT tokens"""
    return jsonify({
        'success': False,
        'error': 'Authorization required',
        'message': 'Access token is missing'
    }), 401


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("=" * 80)
    print("🚀 GCRegisterAPI-10-26 Starting")
    print("=" * 80)
    print(f"📍 Port: {port}")
    print(f"🔐 JWT Authentication: Enabled")
    print(f"🌐 CORS Origin: {config['cors_origin']}")
    print(f"💾 Database: Cloud SQL PostgreSQL")
    print(f"📊 Rate Limiting: 200/day, 50/hour")
    print("=" * 80)
    print("✅ Ready to accept requests")
    print("=" * 80)

    app.run(host='0.0.0.0', port=port, debug=False)
