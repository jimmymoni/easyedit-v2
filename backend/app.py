from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import uuid
import logging
import time
from datetime import datetime, timedelta

# Import our services
from config import Config
from parsers.drt_parser import DRTParser
from parsers.drt_writer import DRTWriter
from services.soniox_client import SonioxClient
try:
    from services.audio_analyzer import AudioAnalyzer
except ImportError:
    # Fallback to simple audio analyzer if librosa dependencies not available
    from services.simple_audio_analyzer import SimpleAudioAnalyzer as AudioAnalyzer
from services.edit_rules import EditRulesEngine
from services.ai_enhancer import AIEnhancementService

# Import production utilities
from utils import (
    setup_logging, setup_error_handlers, setup_monitoring,
    error_handler, validate_file_upload, validate_processing_options, validate_job_id,
    validate_json_request, sanitize_filename, log_performance,
    system_monitor, health_checker, with_circuit_breaker, soniox_circuit_breaker,
    openai_circuit_breaker, RequestLogger
)

# Import async job manager and WebSocket support
from job_manager import job_manager
from websocket_manager import websocket_manager

# Import authentication and rate limiting
from utils.auth import jwt_manager, require_auth, require_api_key, generate_demo_token, get_current_user
from utils.rate_limiter import rate_limiter, require_rate_limit, get_rate_limit_status, upload_rate_limit, processing_rate_limit

# Setup logging first
logger = setup_logging("easyedit-v2", os.getenv('LOG_LEVEL', 'INFO'))

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Enable CORS for frontend integration
CORS(app, origins=["http://localhost:3000", "http://localhost:5173"])

# Setup production features
setup_error_handlers(app)
setup_monitoring(app)
RequestLogger(app)

# Initialize WebSocket support
websocket_manager.init_app(app)

# Initialize authentication and rate limiting
jwt_manager.init_app(app)
rate_limiter.init_app(app)

# Store for tracking processing jobs
processing_jobs = {}

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def generate_job_id():
    return str(uuid.uuid4())

def cleanup_old_files():
    """Clean up old uploaded and processed files"""
    try:
        current_time = datetime.now()
        for folder in [Config.UPLOAD_FOLDER, Config.TEMP_FOLDER]:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    if os.path.isfile(file_path):
                        file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                        if current_time - file_time > timedelta(hours=Config.TEMP_FILE_RETENTION_HOURS):
                            os.remove(file_path)
                            logger.info(f"Cleaned up old file: {filename}")
    except Exception as e:
        logger.error(f"Error during file cleanup: {str(e)}")

def cleanup_old_jobs():
    """Clean up old job entries from memory to prevent memory leaks"""
    try:
        current_time = datetime.now()
        jobs_to_remove = []

        for job_id, job in processing_jobs.items():
            job_age = current_time - job["created_at"]

            # Remove jobs older than retention period
            if job_age > timedelta(hours=Config.TEMP_FILE_RETENTION_HOURS):
                jobs_to_remove.append(job_id)
            # Also remove failed jobs older than 1 hour
            elif job["status"] == "failed" and job_age > timedelta(hours=1):
                jobs_to_remove.append(job_id)
            # Remove completed jobs older than 6 hours
            elif job["status"] == "completed" and job_age > timedelta(hours=6):
                jobs_to_remove.append(job_id)

        # Remove the jobs
        for job_id in jobs_to_remove:
            job = processing_jobs.pop(job_id, None)
            if job:
                # Clean up associated files
                for file_key in ["audio_file", "drt_file", "output_file"]:
                    file_path = job.get(file_key)
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            logger.info(f"Cleaned up job file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Could not remove job file {file_path}: {str(e)}")

                logger.info(f"Cleaned up old job: {job_id}")

        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs from memory")

    except Exception as e:
        logger.error(f"Error during job cleanup: {str(e)}")

def periodic_cleanup():
    """Run periodic cleanup of files and jobs"""
    cleanup_old_files()
    cleanup_old_jobs()

def startup():
    """Initialize app on startup"""
    # Run system dependency checks
    from utils.system_checks import run_startup_checks

    # Run checks in non-strict mode (ffmpeg is optional, will warn but not fail)
    checks_passed = run_startup_checks(strict=False, print_output=True)

    if not checks_passed:
        logger.warning("Some system checks failed - see above for details")

    periodic_cleanup()
    logger.info("easyedit-v2 backend started")

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

@app.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check endpoint"""
    health_status = system_monitor.get_health_status()
    dependency_status = health_checker.run_all_checks()

    overall_status = "healthy"
    if health_status['status'] != 'healthy' or dependency_status['overall_status'] != 'healthy':
        overall_status = "unhealthy"

    return jsonify({
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "system_health": health_status,
        "dependencies": dependency_status
    })

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Get system metrics for monitoring"""
    return jsonify(system_monitor.export_metrics())

@app.route('/upload', methods=['POST'])
@require_auth()
@require_rate_limit("5 per minute, 50 per hour")
@error_handler
def upload_files():
    """Upload audio and DRT files for processing"""
    start_time = time.time()

    try:
        # Check for required files
        audio_file = request.files.get('audio')
        drt_file = request.files.get('drt')

        # Validate files using production validation
        validate_file_upload(audio_file, Config.ALLOWED_AUDIO_EXTENSIONS, Config.MAX_FILE_SIZE_MB)
        validate_file_upload(drt_file, Config.ALLOWED_DRT_EXTENSIONS, Config.MAX_FILE_SIZE_MB)

        # Generate job ID
        job_id = generate_job_id()

        # Save uploaded files with additional sanitization
        audio_clean_name = sanitize_filename(audio_file.filename)
        drt_clean_name = sanitize_filename(drt_file.filename)

        audio_filename = secure_filename(f"{job_id}_audio_{audio_clean_name}")
        drt_filename = secure_filename(f"{job_id}_drt_{drt_clean_name}")

        audio_path = os.path.join(Config.UPLOAD_FOLDER, audio_filename)
        drt_path = os.path.join(Config.UPLOAD_FOLDER, drt_filename)

        audio_file.save(audio_path)
        drt_file.save(drt_path)

        # Initialize job tracking
        processing_jobs[job_id] = {
            "status": "uploaded",
            "created_at": datetime.now(),
            "audio_file": audio_path,
            "drt_file": drt_path,
            "progress": 10,
            "message": "Files uploaded successfully"
        }

        logger.info(f"Files uploaded for job {job_id}")

        # Log performance
        duration = time.time() - start_time
        log_performance("file_upload", duration, {
            "job_id": job_id,
            "audio_size": audio_file.content_length or 0,
            "drt_size": drt_file.content_length or 0
        })

        return jsonify({
            "job_id": job_id,
            "message": "Files uploaded successfully",
            "audio_filename": audio_file.filename,
            "drt_filename": drt_file.filename
        })

    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        raise  # Let error_handler decorator handle the response

@app.route('/process/<job_id>', methods=['POST'])
@require_auth()
@require_rate_limit("2 per minute, 20 per hour")
@error_handler
def process_timeline(job_id):
    """Submit timeline processing to background queue"""
    start_time = time.time()
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        if job_id not in processing_jobs:
            return jsonify({"error": "Job not found"}), 404

        job = processing_jobs[job_id]

        if job["status"] != "uploaded":
            return jsonify({"error": f"Job status is {job['status']}, cannot process"}), 400

        # Get and validate processing options from request
        options = validate_json_request(request)
        validate_processing_options(options)

        # Submit job to background processing queue
        task_id = job_manager.submit_timeline_processing(
            job_id=job_id,
            audio_file_path=job["audio_file"],
            drt_file_path=job["drt_file"],
            options=options
        )

        # Update job status to indicate submission
        job.update({
            "status": "queued",
            "task_id": task_id,
            "progress": 5,
            "message": "Job submitted for processing",
            "submitted_at": datetime.now(),
            "processing_options": options
        })

        logger.info(f"Timeline processing job {job_id} submitted with task ID {task_id}")

        return jsonify({
            "job_id": job_id,
            "task_id": task_id,
            "status": "queued",
            "message": "Timeline processing submitted to background queue",
            "estimated_time": "5-10 minutes"
        })

    except Exception as e:
        logger.error(f"Error submitting timeline processing for job {job_id}: {str(e)}")

        # Update job status on error
        if job_id in processing_jobs:
            processing_jobs[job_id].update({
                "status": "failed",
                "message": f"Failed to submit for processing: {str(e)}"
            })

        raise  # Let error_handler decorator handle the response

@app.route('/status/<job_id>', methods=['GET'])
@require_auth()
def get_job_status(job_id):
    """Get processing job status from job manager and in-memory fallback"""
    # Validate job ID
    job_id = validate_job_id(job_id)

    try:
        # Try to get status from job manager (Redis/Celery)
        job_status = job_manager.get_job_status(job_id)
        if job_status:
            return jsonify({
                "job_id": job_id,
                "status": job_status.get("status", "unknown"),
                "progress": job_status.get("progress", 0),
                "message": job_status.get("message", "Processing"),
                "created_at": job_status.get("created_at"),
                "updated_at": job_status.get("updated_at"),
                "task_id": job_status.get("task_id"),
                "type": job_status.get("type", "timeline_processing"),
                "result": job_status.get("result", {}),
                "error": job_status.get("error"),
                "error_type": job_status.get("error_type")
            })

    except Exception as e:
        logger.warning(f"Failed to get job status from job manager: {str(e)}")

    # Fallback to in-memory storage
    if job_id not in processing_jobs:
        return jsonify({"error": "Job not found"}), 404

    job = processing_jobs[job_id]

    return jsonify({
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "message": job.get("message", "Processing"),
        "created_at": job["created_at"].isoformat(),
        "task_id": job.get("task_id"),
        "stats": job.get("stats", {}),
        "transcription_available": job.get("transcription_available", False)
    })

@app.route('/download/<job_id>', methods=['GET'])
@require_auth()
@require_rate_limit("10 per minute, 100 per hour")
@error_handler
def download_result(job_id):
    """Download processed DRT file"""
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        if job_id not in processing_jobs:
            return jsonify({"error": "Job not found"}), 404

        job = processing_jobs[job_id]

        if job["status"] != "completed":
            return jsonify({"error": f"Job status is {job['status']}, no file available"}), 400

        output_file = job.get("output_file")
        if not output_file or not os.path.exists(output_file):
            return jsonify({"error": "Output file not found"}), 404

        return send_file(
            output_file,
            as_attachment=True,
            download_name=f"edited_timeline_{job_id}.drt",
            mimetype='application/xml'
        )

    except Exception as e:
        logger.error(f"Error downloading file for job {job_id}: {str(e)}")
        return jsonify({"error": "Download failed"}), 500

@app.route('/transcription/<job_id>', methods=['GET'])
def get_transcription(job_id):
    """Get transcription data for a job"""
    # Validate job ID
    job_id = validate_job_id(job_id)

    if job_id not in processing_jobs:
        return jsonify({"error": "Job not found"}), 404

    job = processing_jobs[job_id]

    if not job.get("transcription_available"):
        return jsonify({"error": "No transcription available for this job"}), 404

    # This would need to be stored separately in a real implementation
    return jsonify({"message": "Transcription data would be returned here"})

@app.route('/ai-enhancements/<job_id>', methods=['GET'])
def get_ai_enhancements(job_id):
    """Get AI enhancement data for a completed job"""
    # Validate job ID
    job_id = validate_job_id(job_id)

    if job_id not in processing_jobs:
        return jsonify({"error": "Job not found"}), 404

    job = processing_jobs[job_id]

    if job["status"] != "completed":
        return jsonify({"error": f"Job status is {job['status']}, enhancements not available"}), 400

    ai_enhancements = job.get("ai_enhancements")
    if not ai_enhancements:
        return jsonify({"error": "No AI enhancements available for this job"}), 404

    return jsonify({
        "job_id": job_id,
        "ai_enhancements": ai_enhancements,
        "enhancement_summary": ai_enhancements.get('applied_enhancements', []) if ai_enhancements.get('success') else []
    })

@app.route('/preview/<job_id>', methods=['GET'])
def get_processing_preview(job_id):
    """Get a preview of what processing would do without actually processing"""
    # Validate job ID
    job_id = validate_job_id(job_id)

    if job_id not in processing_jobs:
        return jsonify({"error": "Job not found"}), 404

    job = processing_jobs[job_id]

    if job["status"] != "uploaded":
        return jsonify({"error": "Preview only available for uploaded jobs"}), 400

    try:
        # Use the timeline editing engine to get preview
        from services.timeline_editor import TimelineEditingEngine

        timeline_editor = TimelineEditingEngine()
        preview = timeline_editor.get_processing_preview(
            job["audio_file"],
            job["drt_file"]
        )

        return jsonify({
            "job_id": job_id,
            "preview": preview
        })

    except Exception as e:
        logger.error(f"Error generating preview for job {job_id}: {str(e)}")
        return jsonify({"error": "Failed to generate preview"}), 500

@app.route('/jobs', methods=['GET'])
def list_jobs():
    """List all processing jobs from job manager and in-memory storage"""
    try:
        # Get query parameters for filtering
        limit = int(request.args.get('limit', 50))
        job_type = request.args.get('type')
        status = request.args.get('status')

        # Get jobs from job manager (Redis)
        async_jobs = job_manager.list_jobs(limit=limit, job_type=job_type, status=status)

        # Get jobs from in-memory storage (fallback)
        memory_jobs = []
        for job_id, job in processing_jobs.items():
            # Apply filters
            if job_type and job.get('type', 'timeline_processing') != job_type:
                continue
            if status and job.get('status') != status:
                continue

            memory_jobs.append({
                "job_id": job_id,
                "status": job["status"],
                "created_at": job["created_at"].isoformat(),
                "progress": job.get("progress", 0),
                "type": job.get("type", "timeline_processing"),
                "source": "memory"
            })

        # Combine and deduplicate jobs (prefer async jobs)
        all_jobs = {}
        for job in memory_jobs:
            all_jobs[job["job_id"]] = job

        for job in async_jobs:
            job["source"] = "redis"
            all_jobs[job["job_id"]] = job

        # Convert to list and sort
        jobs_list = list(all_jobs.values())
        jobs_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return jsonify({
            "jobs": jobs_list[:limit],
            "total": len(jobs_list),
            "filters": {
                "type": job_type,
                "status": status,
                "limit": limit
            }
        })

    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        return jsonify({"error": "Failed to list jobs"}), 500

@app.route('/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a running or queued job"""
    try:
        job_id = validate_job_id(job_id)

        # Try to cancel in job manager
        success = job_manager.cancel_job(job_id)

        if success:
            # Also update in-memory storage if exists
            if job_id in processing_jobs:
                processing_jobs[job_id].update({
                    "status": "cancelled",
                    "message": "Job cancelled by user",
                    "cancelled_at": datetime.now()
                })

            return jsonify({
                "job_id": job_id,
                "status": "cancelled",
                "message": "Job cancelled successfully"
            })
        else:
            return jsonify({"error": "Failed to cancel job"}), 500

    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {str(e)}")
        return jsonify({"error": "Failed to cancel job"}), 500

@app.route('/websocket/status', methods=['GET'])
def websocket_status():
    """Get WebSocket connection status and statistics"""
    try:
        return jsonify({
            "websocket_enabled": websocket_manager.socketio is not None,
            "connected_clients": websocket_manager.get_connected_clients_count(),
            "endpoint": "/socket.io/",
            "events": [
                "connect", "disconnect", "subscribe_job", "unsubscribe_job",
                "get_job_status", "ping", "job_update", "job_progress"
            ]
        })
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {str(e)}")
        return jsonify({"error": "Failed to get WebSocket status"}), 500

@app.route('/cleanup', methods=['POST'])
def manual_cleanup():
    """Manually trigger cleanup of old files and jobs"""
    try:
        # Submit async cleanup task
        from tasks.file_management import cleanup_files_task
        task = cleanup_files_task.delay()

        # Also clean up old jobs from Redis
        cleaned_jobs = job_manager.cleanup_old_jobs()

        # Clean up in-memory jobs
        jobs_before = len(processing_jobs)
        periodic_cleanup()
        jobs_after = len(processing_jobs)

        return jsonify({
            "message": "Cleanup submitted",
            "cleanup_task_id": task.id,
            "redis_jobs_cleaned": cleaned_jobs,
            "memory_jobs_removed": jobs_before - jobs_after,
            "remaining_memory_jobs": jobs_after
        })
    except Exception as e:
        logger.error(f"Manual cleanup error: {str(e)}")
        return jsonify({"error": "Cleanup failed"}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large"}), 413

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    # Run startup tasks
    startup()

    # Use SocketIO server for WebSocket support
    if websocket_manager.socketio:
        websocket_manager.socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    else:
        app.run(debug=True, host='0.0.0.0', port=5000)
