#!/usr/bin/env python3
"""
Simplified Flask app to test authentication and rate limiting
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
import time
from datetime import datetime

# Authentication and rate limiting
from utils.auth import jwt_manager, require_auth, require_api_key, generate_demo_token, get_current_user
from utils.rate_limiter import rate_limiter, require_rate_limit, get_rate_limit_status

# Simple logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'test-secret-key-for-development')

# Enable CORS
CORS(app, origins=["*"])  # Allow all origins for testing

# Initialize authentication and rate limiting
jwt_manager.init_app(app)
rate_limiter.init_app(app)

# Authentication routes
@app.route('/auth/demo-token', methods=['GET'])
@require_rate_limit("10 per minute")
def get_demo_token():
    """Generate a demo token for testing"""
    try:
        token_data = generate_demo_token()
        logger.info("Demo token generated")

        return jsonify({
            'status': 'success',
            'message': 'Demo token generated successfully',
            **token_data
        })
    except Exception as e:
        logger.error(f"Demo token generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate demo token'}), 500

@app.route('/auth/refresh', methods=['POST'])
@require_rate_limit("5 per minute")
def refresh_token():
    """Refresh access token using refresh token"""
    try:
        data = request.get_json()
        if not data or 'refresh_token' not in data:
            return jsonify({'error': 'refresh_token is required'}), 400

        new_tokens = jwt_manager.refresh_access_token(data['refresh_token'])
        logger.info("Token refreshed successfully")

        return jsonify({
            'status': 'success',
            'message': 'Token refreshed successfully',
            **new_tokens
        })
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        return jsonify({'error': str(e)}), 401

@app.route('/auth/verify', methods=['GET'])
@require_auth()
def verify_token():
    """Verify current token and return user info"""
    user = get_current_user()
    return jsonify({
        'status': 'success',
        'message': 'Token is valid',
        'user': {
            'user_id': user['user_id'],
            'email': user['email'],
            'role': user['role'],
            'has_api_key': bool(user.get('api_key'))
        }
    })

@app.route('/auth/rate-limits', methods=['GET'])
def get_rate_limits():
    """Get current rate limit status"""
    return jsonify(get_rate_limit_status())

# Test protected endpoints
@app.route('/protected/test', methods=['GET'])
@require_auth()
def protected_test():
    """Test protected endpoint"""
    user = get_current_user()
    return jsonify({
        'message': 'Access granted to protected endpoint',
        'user_id': user['user_id'],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/protected/upload', methods=['POST'])
@require_auth()
@require_rate_limit("5 per minute, 50 per hour")
def test_upload():
    """Test upload endpoint with auth and rate limiting"""
    user = get_current_user()
    return jsonify({
        'message': 'Upload endpoint accessed successfully',
        'user_id': user['user_id'],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/protected/process', methods=['POST'])
@require_auth()
@require_rate_limit("2 per minute, 20 per hour")
def test_process():
    """Test processing endpoint with auth and rate limiting"""
    user = get_current_user()
    return jsonify({
        'message': 'Processing endpoint accessed successfully',
        'user_id': user['user_id'],
        'timestamp': datetime.now().isoformat()
    })

# Public endpoints
@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0-test'
    })

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'message': 'EasyEdit-v2 Authentication Test Server',
        'endpoints': {
            'auth': {
                'demo_token': '/auth/demo-token',
                'verify': '/auth/verify',
                'refresh': '/auth/refresh',
                'rate_limits': '/auth/rate-limits'
            },
            'protected': {
                'test': '/protected/test',
                'upload': '/protected/upload',
                'process': '/protected/process'
            },
            'public': {
                'health': '/health'
            }
        }
    })

if __name__ == '__main__':
    print("Starting EasyEdit-v2 Authentication Test Server...")
    print("Available endpoints:")
    print("  GET  /                     - API overview")
    print("  GET  /health               - Health check")
    print("  GET  /auth/demo-token      - Get demo JWT token")
    print("  POST /auth/refresh         - Refresh JWT token")
    print("  GET  /auth/verify          - Verify JWT token")
    print("  GET  /auth/rate-limits     - Get rate limit status")
    print("  GET  /protected/test       - Protected test endpoint")
    print("  POST /protected/upload     - Protected upload test")
    print("  POST /protected/process    - Protected processing test")
    print("\nServer running on http://localhost:5000")

    app.run(debug=True, host='localhost', port=5000)