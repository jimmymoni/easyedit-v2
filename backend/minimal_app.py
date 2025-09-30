#!/usr/bin/env python3
"""
Minimal production backend for testing core functionality without audio dependencies
"""

from flask import Flask, request, jsonify, send_file, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import uuid
import logging
import time
from datetime import datetime, timedelta

# Import authentication and rate limiting
from utils.auth import jwt_manager, require_auth, require_api_key, generate_demo_token, get_current_user
from utils.rate_limiter import rate_limiter, require_rate_limit, get_rate_limit_status
from utils.error_handlers import (
    error_handler, validate_file_upload, validate_job_id,
    validate_json_request, sanitize_filename
)
from utils.logging_config import setup_logging
from utils.monitoring import system_monitor, health_checker

# Import WebSocket support
from websocket_manager import websocket_manager

# Note: job_manager requires audio dependencies, using mock storage instead

# Setup logging
logger = setup_logging("easyedit-v2-minimal", os.getenv('LOG_LEVEL', 'INFO'))

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-for-testing')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['TEMP_FOLDER'] = os.path.join(os.getcwd(), 'temp')

# Create directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

# Enable CORS
CORS(app, origins=["http://localhost:3000", "http://localhost:5173"])

# Initialize authentication and rate limiting
jwt_manager.init_app(app)
rate_limiter.init_app(app)

# Initialize WebSocket support
websocket_manager.init_app(app)

# Mock job storage
mock_jobs = {}

def generate_job_id():
    return str(uuid.uuid4())

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

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

# Core API endpoints
@app.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check"""
    health_status = system_monitor.get_health_status()

    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0-minimal",
        "system_health": health_status,
        "authentication": "enabled",
        "rate_limiting": "enabled",
        "websockets": "enabled"
    })

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Get system metrics"""
    return jsonify(system_monitor.export_metrics())

@app.route('/upload', methods=['POST'])
@require_auth()
@require_rate_limit("5 per minute, 50 per hour")
@error_handler
def upload_files():
    """Upload audio and DRT files for processing"""
    start_time = time.time()

    try:
        # Validate request
        if 'audio' not in request.files or 'drt' not in request.files:
            return jsonify({
                'error': 'Both audio and drt files are required'
            }), 400

        audio_file = request.files['audio']
        drt_file = request.files['drt']

        # Validate files
        if audio_file.filename == '' or drt_file.filename == '':
            return jsonify({
                'error': 'No files selected'
            }), 400

        # Check file extensions
        audio_extensions = {'wav', 'mp3', 'aac', 'flac', 'm4a'}
        drt_extensions = {'drt', 'xml'}

        if not allowed_file(audio_file.filename, audio_extensions):
            return jsonify({
                'error': f'Invalid audio file format. Allowed: {", ".join(audio_extensions)}'
            }), 400

        if not allowed_file(drt_file.filename, drt_extensions):
            return jsonify({
                'error': f'Invalid DRT file format. Allowed: {", ".join(drt_extensions)}'
            }), 400

        # Generate job ID and save files
        job_id = generate_job_id()

        # Secure filenames
        audio_filename = f"{job_id}_audio_{secure_filename(audio_file.filename)}"
        drt_filename = f"{job_id}_drt_{secure_filename(drt_file.filename)}"

        # Save files
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
        drt_path = os.path.join(app.config['UPLOAD_FOLDER'], drt_filename)

        audio_file.save(audio_path)
        drt_file.save(drt_path)

        # Create mock job entry
        mock_jobs[job_id] = {
            'job_id': job_id,
            'status': 'uploaded',
            'progress': 0,
            'message': 'Files uploaded successfully',
            'created_at': datetime.now().isoformat(),
            'audio_file': audio_path,
            'drt_file': drt_path,
            'audio_filename': audio_filename,
            'drt_filename': drt_filename,
            'upload_time': time.time() - start_time
        }

        logger.info(f"Files uploaded successfully for job {job_id}")

        return jsonify({
            'job_id': job_id,
            'message': 'Files uploaded successfully',
            'audio_filename': audio_filename,
            'drt_filename': drt_filename,
            'upload_time': time.time() - start_time
        })

    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/process/<job_id>', methods=['POST'])
@require_auth()
@require_rate_limit("2 per minute, 20 per hour")
@error_handler
def process_timeline(job_id):
    """Start timeline processing (mock for testing)"""
    try:
        job_id = validate_job_id(job_id)

        if job_id not in mock_jobs:
            return jsonify({'error': 'Job not found'}), 404

        # Get processing options
        options = request.get_json() or {}

        # Update job status to processing
        mock_jobs[job_id].update({
            'status': 'processing',
            'progress': 25,
            'message': 'Mock processing started',
            'processing_options': options
        })

        # Simulate WebSocket update
        websocket_manager.broadcast_job_progress(job_id, 25, "Mock processing started")

        logger.info(f"Mock processing started for job {job_id}")

        return jsonify({
            'job_id': job_id,
            'status': 'processing',
            'message': 'Mock processing started successfully',
            'options': options
        })

    except Exception as e:
        logger.error(f"Error starting processing: {str(e)}")
        return jsonify({'error': 'Processing failed to start'}), 500

@app.route('/status/<job_id>', methods=['GET'])
@require_auth()
def get_job_status(job_id):
    """Get job status"""
    try:
        job_id = validate_job_id(job_id)

        if job_id not in mock_jobs:
            return jsonify({'error': 'Job not found'}), 404

        job = mock_jobs[job_id]

        # Simulate progression for demo
        if job['status'] == 'processing' and job['progress'] < 100:
            job['progress'] = min(job['progress'] + 10, 100)
            if job['progress'] == 100:
                job['status'] = 'completed'
                job['message'] = 'Mock processing completed successfully'

        return jsonify(job)

    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        return jsonify({'error': 'Failed to get job status'}), 500

@app.route('/jobs', methods=['GET'])
@require_auth()
def get_all_jobs():
    """Get all jobs for current user"""
    return jsonify({
        'jobs': list(mock_jobs.values()),
        'total': len(mock_jobs)
    })

@app.route('/download/<job_id>', methods=['GET'])
@require_auth()
@require_rate_limit("10 per minute, 100 per hour")
@error_handler
def download_result(job_id):
    """Download mock result"""
    try:
        job_id = validate_job_id(job_id)

        if job_id not in mock_jobs:
            return jsonify({'error': 'Job not found'}), 404

        job = mock_jobs[job_id]

        if job['status'] != 'completed':
            return jsonify({'error': 'Job not completed yet'}), 400

        # Return the original DRT file as mock result
        return send_file(
            job['drt_file'],
            as_attachment=True,
            download_name=f"{job_id}_processed.drt"
        )

    except Exception as e:
        logger.error(f"Error downloading result: {str(e)}")
        return jsonify({'error': 'Download failed'}), 500

@app.route('/websocket/status', methods=['GET'])
def websocket_status():
    """Get WebSocket connection status"""
    try:
        return jsonify({
            'websocket_enabled': True,
            'connected_clients': websocket_manager.get_connected_clients_count(),
            'endpoint': 'ws://localhost:5000',
            'status': 'available'
        })
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {str(e)}")
        return jsonify({'error': 'Failed to get WebSocket status'}), 500

@app.route('/', methods=['GET'])
def index():
    """API overview"""
    return jsonify({
        'name': 'EasyEdit-v2 Minimal Backend',
        'version': '1.0.0-minimal',
        'status': 'running',
        'features': {
            'authentication': 'enabled',
            'rate_limiting': 'enabled',
            'websockets': 'enabled',
            'file_upload': 'enabled',
            'mock_processing': 'enabled'
        },
        'endpoints': {
            'auth': {
                'demo_token': '/auth/demo-token',
                'verify': '/auth/verify',
                'refresh': '/auth/refresh',
                'rate_limits': '/auth/rate-limits'
            },
            'api': {
                'health': '/health',
                'metrics': '/metrics',
                'upload': '/upload',
                'process': '/process/<job_id>',
                'status': '/status/<job_id>',
                'jobs': '/jobs',
                'download': '/download/<job_id>',
                'websocket_status': '/websocket/status'
            }
        }
    })

if __name__ == '__main__':
    print("Starting EasyEdit-v2 Minimal Backend...")
    print("Features: Authentication, Rate Limiting, WebSockets, Mock Processing")
    print("Server running on http://localhost:5000")

    app.run(debug=True, host='localhost', port=5000)