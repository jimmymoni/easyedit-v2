from flask import Flask, request, jsonify, send_file
from flask_cors import CORS, cross_origin
from werkzeug.utils import secure_filename
import os
import uuid
import logging
import time
from datetime import datetime, timedelta

# Import our services
from config import Config
from parsers.xml_parser import FCP7XMLParser
from parsers.xml_writer import FCP7XMLWriter
from services.transcription_service import TranscriptionServiceFactory
try:
    from services.audio_analyzer import AudioAnalyzer
except ImportError:
    # Fallback to simple audio analyzer if librosa dependencies not available
    from services.simple_audio_analyzer import SimpleAudioAnalyzer as AudioAnalyzer
from services.edit_rules import EditRulesEngine
from services.ai_enhancer import AIEnhancementService
from services.content_analyzer import ContentAnalyzer

# Import production utilities
from utils import (
    setup_logging, setup_error_handlers, setup_monitoring,
    error_handler, validate_file_upload, validate_processing_options, validate_job_id,
    validate_json_request, sanitize_filename, log_performance,
    system_monitor, health_checker, with_circuit_breaker,
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

# Enable CORS for frontend integration with credentials support
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Setup production features
setup_error_handlers(app)
setup_monitoring(app)
RequestLogger(app)

# NOTE: WebSocket initialization moved to AFTER route definitions
# to ensure SocketIO wrapper includes all routes

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
                for file_key in ["audio_file", "timeline_file", "output_file"]:
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

# ==============================================================================
# SIMPLE UPLOAD ENDPOINT - NO MIDDLEWARE (DEBUGGING)
# ==============================================================================
@app.route('/simple-upload', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins="*",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    supports_credentials=True
)
def simple_upload():
    """
    BARE MINIMUM UPLOAD - FOR SPEED TESTING
    NO authentication, NO rate limiting, NO validation, NO error handling
    This endpoint exists to test if middleware is causing slowness
    """
    import sys
    print("[SIMPLE-UPLOAD] === FUNCTION CALLED ===", flush=True)
    sys.stdout.flush()

    if request.method == 'OPTIONS':
        print("[SIMPLE-UPLOAD] OPTIONS request", flush=True)
        return '', 200

    try:
        # DEBUG
        print(f"[SIMPLE-UPLOAD] Content-Type: {request.content_type}", flush=True)
        print(f"[SIMPLE-UPLOAD] Files keys: {list(request.files.keys())}")
        print(f"[SIMPLE-UPLOAD] Form keys: {list(request.form.keys())}")
        print(f"[SIMPLE-UPLOAD] Files dict: {dict(request.files)}")

        # Get files directly
        audio = request.files.get('audio')
        timeline = request.files.get('timeline')

        print(f"[SIMPLE-UPLOAD] Audio: {audio}, Timeline: {timeline}")

        if not audio or not timeline:
            return jsonify({"error": "Missing files", "debug": {
                "files_keys": list(request.files.keys()),
                "content_type": request.content_type
            }}), 400

        # Generate simple ID
        job_id = str(uuid.uuid4())

        # Ensure uploads directory exists
        os.makedirs('uploads', exist_ok=True)

        # Save files immediately - NO validation, NO sanitization
        audio_path = os.path.join('uploads', f"{job_id}_audio.wav")
        timeline_path = os.path.join('uploads', f"{job_id}_timeline.xml")

        audio.save(audio_path)
        timeline.save(timeline_path)

        # Register job in processing_jobs dictionary (required by /process/ endpoint)
        processing_jobs[job_id] = {
            'job_id': job_id,
            'audio_file': audio_path,
            'timeline_file': timeline_path,
            'status': 'uploaded',
            'created_at': datetime.now().isoformat()
        }

        # Also register in job manager for tracking
        job_manager.update_job_status(
            job_id=job_id,
            status='uploaded',
            progress=0,
            message='Files uploaded successfully - ready for processing'
        )

        # Store file paths in job data for later retrieval
        job_data = job_manager._get_job_data(job_id)
        job_data['audio_file'] = audio_path
        job_data['timeline_file'] = timeline_path
        job_data['type'] = 'simple_upload'
        job_manager._store_job_data(job_id, job_data)
        print(f"[SIMPLE-UPLOAD] Job registered in job manager: {job_id}", flush=True)

        response_data = {
            "job_id": job_id,
            "message": "Files uploaded successfully",
            "audio_filename": audio.filename,
            "timeline_filename": timeline.filename
        }
        print(f"[SIMPLE-UPLOAD] Returning response: {response_data}", flush=True)

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# REGULAR UPLOAD ENDPOINT (WITH MIDDLEWARE)
# ==============================================================================
@app.route('/upload', methods=['POST'])
@require_auth()
@require_rate_limit("5 per minute, 50 per hour")
@error_handler
def upload_files():
    """Upload audio and FCP7 XML timeline files for processing"""
    start_time = time.time()

    try:
        # DEBUG: Log what we're receiving
        logger.info(f"Upload request - Files keys: {list(request.files.keys())}")
        logger.info(f"Upload request - Form keys: {list(request.form.keys())}")
        logger.info(f"Upload request - Content-Type: {request.content_type}")
        logger.info(f"Upload request - All files: {dict(request.files)}")

        # Check for required files
        audio_file = request.files.get('audio')
        timeline_file = request.files.get('timeline')

        logger.info(f"Audio file object: {audio_file}")
        logger.info(f"Timeline file object: {timeline_file}")

        if audio_file:
            logger.info(f"Audio file - filename: {audio_file.filename}, content_type: {audio_file.content_type}")
        if timeline_file:
            logger.info(f"Timeline file - filename: {timeline_file.filename}, content_type: {timeline_file.content_type}")

        # Validate files using production validation
        validate_file_upload(audio_file, Config.ALLOWED_AUDIO_EXTENSIONS, Config.MAX_FILE_SIZE_MB)
        validate_file_upload(timeline_file, Config.ALLOWED_TIMELINE_EXTENSIONS, Config.MAX_FILE_SIZE_MB)

        # Explicit rejection of .drt files
        if timeline_file and timeline_file.filename.lower().endswith('.drt'):
            return jsonify({
                'error': 'Invalid file format',
                'message': '.drt files are not supported. Please export your timeline as Final Cut Pro 7 XML (.xml) format.'
            }), 400

        # Generate job ID
        job_id = generate_job_id()

        # Save uploaded files with additional sanitization
        audio_clean_name = sanitize_filename(audio_file.filename)
        timeline_clean_name = sanitize_filename(timeline_file.filename)

        audio_filename = secure_filename(f"{job_id}_audio_{audio_clean_name}")
        timeline_filename = secure_filename(f"{job_id}_timeline_{timeline_clean_name}")

        audio_path = os.path.join(Config.UPLOAD_FOLDER, audio_filename)
        timeline_path = os.path.join(Config.UPLOAD_FOLDER, timeline_filename)

        audio_file.save(audio_path)
        timeline_file.save(timeline_path)

        # Initialize job tracking
        processing_jobs[job_id] = {
            "status": "uploaded",
            "created_at": datetime.now(),
            "audio_file": audio_path,
            "timeline_file": timeline_path,
            "progress": 10,
            "message": "Files uploaded successfully"
        }

        logger.info(f"Files uploaded for job {job_id}")

        # Log performance
        duration = time.time() - start_time
        log_performance("file_upload", duration, {
            "job_id": job_id,
            "audio_size": audio_file.content_length or 0,
            "timeline_size": timeline_file.content_length or 0
        })

        return jsonify({
            "job_id": job_id,
            "message": "Files uploaded successfully",
            "audio_filename": audio_file.filename,
            "timeline_filename": timeline_file.filename
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

        # Allow multiple valid statuses for processing
        allowed_statuses = ["uploaded", "ready", "queued"]
        if job["status"] not in allowed_statuses:
            return jsonify({"error": f"Job status is {job['status']}, expected one of {allowed_statuses}"}), 400

        # Get and validate processing options from request
        options = validate_json_request(request)
        validate_processing_options(options)

        # Submit job to background processing queue
        task_id = job_manager.submit_timeline_processing(
            job_id=job_id,
            audio_file_path=job["audio_file"],
            timeline_file_path=job["timeline_file"],
            options=options
        )

        # Check if task completed immediately (Celery eager mode)
        from celery_app import celery_app

        # In eager mode, task executes synchronously and result is available immediately
        if celery_app.conf.task_always_eager:
            # Get result from eager execution
            task = celery_app.AsyncResult(task_id)
            try:
                # In eager mode, result is stored in memory
                task_result = task.result if hasattr(task, 'result') else None

                if task_result:
                    logger.info(f"Task {task_id} completed in eager mode, storing result")
                    job_manager.store_task_result(job_id, task_result)

                    # Update job status to indicate completion
                    job.update({
                        "status": "completed",
                        "task_id": task_id,
                        "progress": 100,
                        "message": "Timeline processed successfully",
                        "submitted_at": datetime.now(),
                        "completed_at": datetime.now(),
                        "processing_options": options,
                        "result": task_result
                    })

                    return jsonify({
                        "job_id": job_id,
                        "task_id": task_id,
                        "status": "completed",
                        "message": "Timeline processed successfully",
                        "result": task_result
                    })
            except Exception as e:
                logger.warning(f"Could not get eager task result: {str(e)}")

        # Normal async mode (or fallback if eager mode fails) - update job status to indicate submission
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

@app.route('/process-shortform/<job_id>', methods=['POST'])
@require_auth()
@require_rate_limit("2 per minute, 20 per hour")
@error_handler
def process_shortform(job_id):
    """Submit short-form content generation to background queue"""
    start_time = time.time()
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        if job_id not in processing_jobs:
            return jsonify({"error": "Job not found"}), 404

        job = processing_jobs[job_id]

        # Allow multiple valid statuses for processing
        allowed_statuses = ["uploaded", "ready", "queued"]
        if job["status"] not in allowed_statuses:
            return jsonify({"error": f"Job status is {job['status']}, expected one of {allowed_statuses}"}), 400

        # Get and validate options from request
        options = validate_json_request(request)

        # Extract short-form specific options
        prompt_type = options.get('prompt_type', 'engaging')
        target_duration = float(options.get('target_duration', 60.0))
        language_code = options.get('language_code', 'ml-IN')

        # Validate prompt type
        valid_prompt_types = ['engaging', 'informative', 'emotional', 'funny', 'tutorial',
                               'inspirational', 'controversial', 'storytelling']
        if prompt_type not in valid_prompt_types:
            return jsonify({
                "error": f"Invalid prompt_type. Must be one of: {', '.join(valid_prompt_types)}"
            }), 400

        # Validate target duration (15-180 seconds)
        if not (15 <= target_duration <= 180):
            return jsonify({
                "error": "target_duration must be between 15 and 180 seconds"
            }), 400

        # Submit short-form processing task
        from tasks.shortform_processing import process_shortform_content

        task = process_shortform_content.apply_async(
            args=[job_id, job["audio_file"], job["timeline_file"], prompt_type, target_duration, language_code],
            task_id=f"shortform_{job_id}"
        )

        task_id = task.id

        # Check if task completed immediately (Celery eager mode)
        from celery_app import celery_app

        if celery_app.conf.task_always_eager:
            try:
                task_result = task.result if hasattr(task, 'result') else None

                if task_result:
                    logger.info(f"Short-form task {task_id} completed in eager mode")
                    job_manager.store_task_result(job_id, task_result)

                    job.update({
                        "status": "completed",
                        "task_id": task_id,
                        "progress": 100,
                        "message": "Short-form content generated successfully",
                        "submitted_at": datetime.now(),
                        "completed_at": datetime.now(),
                        "processing_options": options,
                        "result": task_result
                    })

                    return jsonify({
                        "job_id": job_id,
                        "task_id": task_id,
                        "status": "completed",
                        "message": "Short-form content generated successfully",
                        "result": task_result
                    })
            except Exception as e:
                logger.warning(f"Could not get eager task result: {str(e)}")

        # Normal async mode
        job.update({
            "status": "queued",
            "task_id": task_id,
            "progress": 5,
            "message": "Short-form generation submitted",
            "submitted_at": datetime.now(),
            "processing_options": options
        })

        logger.info(f"Short-form processing job {job_id} submitted with task ID {task_id}")

        return jsonify({
            "job_id": job_id,
            "task_id": task_id,
            "status": "queued",
            "message": "Short-form content generation submitted to background queue",
            "estimated_time": "10-20 minutes",
            "options": {
                "prompt_type": prompt_type,
                "target_duration": target_duration,
                "language_code": language_code
            }
        })

    except Exception as e:
        logger.error(f"Error submitting short-form processing for job {job_id}: {str(e)}")

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
            # Extract result data
            result = job_status.get("result", {})

            response = {
                "job_id": job_id,
                "status": job_status.get("status", "unknown"),
                "progress": job_status.get("progress", 0),
                "message": job_status.get("message", "Processing"),
                "created_at": job_status.get("created_at"),
                "updated_at": job_status.get("updated_at"),
                "task_id": job_status.get("task_id"),
                "type": job_status.get("type", "timeline_processing"),
            }

            # Add result fields if available
            if result:
                response.update({
                    # NO stats field - no automatic editing in GodMode-only architecture
                    "stats": result.get("stats"),  # Optional - only for old jobs (backward compatibility)
                    "transcription_available": result.get("transcription_available", False),
                    "audio_analysis": result.get("audio_analysis", {}),
                    "content_analysis_available": bool(result.get("content_analysis")),
                    "filler_word_detection": result.get("filler_word_detection"),
                    "ai_enhancements": result.get("ai_enhancements"),
                })

            # Add error info if failed
            if job_status.get("error"):
                response.update({
                    "error": job_status.get("error"),
                    "error_type": job_status.get("error_type")
                })

            return jsonify(response)

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
        "stats": job.get("stats"),  # Optional - only for old jobs
        "transcription_available": job.get("transcription_available", False),
        "content_analysis_available": bool(job.get("result", {}).get("content_analysis"))
    })

@app.route('/download/<job_id>', methods=['GET'])
@require_auth()
@require_rate_limit("10 per minute, 100 per hour")
@error_handler
def download_result(job_id):
    """Download processed FCP7 XML file"""
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        # Get job from job_manager instead of old processing_jobs dict
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                return jsonify({"error": "Job not found"}), 404
        except Exception as e:
            logger.error(f"Failed to get job status from job manager: {str(e)}")
            # Fallback to old processing_jobs dict
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        if job_status.get("status") != "completed":
            return jsonify({"error": f"Job status is {job_status.get('status')}, no file available"}), 400

        # Get output file from result
        result = job_status.get("result", {})

        # Check for AI-edited file first, then fallback to regular output_file
        output_file = result.get("ai_edited_output_file") or result.get("output_file")

        # New architecture: no initial XML exists in GodMode-only workflow
        if not output_file:
            return jsonify({
                "error": "No pre-generated timeline available in GodMode-only architecture.",
                "message": "Use God Mode to create custom edits and download from there.",
                "godmode_url": f"/godmode/{job_id}"
            }), 404

        # Check if file exists
        if not os.path.exists(output_file):
            return jsonify({"error": f"Output file not found: {output_file}"}), 404

        return send_file(
            output_file,
            as_attachment=True,
            download_name=f"edited_timeline_{job_id}.xml",
            mimetype='application/xml'
        )

    except Exception as e:
        logger.error(f"Error downloading file for job {job_id}: {str(e)}")
        return jsonify({"error": "Download failed"}), 500

@app.route('/audio/<job_id>', methods=['GET'])
@require_auth()
@require_rate_limit("20 per minute, 200 per hour")
@error_handler
def get_audio_file(job_id):
    """Get uploaded audio file for God Mode waveform viewer"""
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        # Get job from job_manager or fallback to processing_jobs
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        # Get audio file path
        audio_file = job_status.get("audio_file")

        if not audio_file or not os.path.exists(audio_file):
            return jsonify({"error": "Audio file not found"}), 404

        # Determine mimetype based on extension
        _, ext = os.path.splitext(audio_file)
        mime_types = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
            '.flac': 'audio/flac'
        }
        mimetype = mime_types.get(ext.lower(), 'application/octet-stream')

        return send_file(
            audio_file,
            mimetype=mimetype,
            as_attachment=False  # Allow inline playback
        )

    except Exception as e:
        logger.error(f"Error serving audio file for job {job_id}: {str(e)}")
        return jsonify({"error": "Failed to serve audio file"}), 500

@app.route('/audio/<job_id>/edited', methods=['GET'])
@require_auth()
@require_rate_limit("20 per minute, 200 per hour")
@error_handler
def get_edited_audio_file(job_id):
    """Get AI-edited audio file for God Mode waveform viewer"""
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        # Get job from job_manager or fallback to processing_jobs
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        # Get edited audio file path from result
        result = job_status.get("result", {})
        edited_audio_file = result.get("edited_audio_file")

        if not edited_audio_file or not os.path.exists(edited_audio_file):
            return jsonify({"error": "Edited audio file not found. Please run an AI edit first."}), 404

        # Determine mimetype based on extension
        _, ext = os.path.splitext(edited_audio_file)
        mime_types = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
            '.flac': 'audio/flac'
        }
        mimetype = mime_types.get(ext.lower(), 'application/octet-stream')

        return send_file(
            edited_audio_file,
            mimetype=mimetype,
            as_attachment=False  # Allow inline playback
        )

    except Exception as e:
        logger.error(f"Error serving edited audio file for job {job_id}: {str(e)}")
        return jsonify({"error": "Failed to serve edited audio file"}), 500

@app.route('/ai-edit', methods=['POST'])
@require_auth()
@require_rate_limit("10 per minute, 100 per hour")
@error_handler
def ai_edit_timeline():
    """AI-powered timeline editing via natural language prompts"""
    try:
        # Validate request
        data = validate_json_request(request)
        job_id = validate_job_id(data.get('job_id'))
        prompt = data.get('prompt', '').strip()
        params = data.get('params')  # Get params from AI chat handler

        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        # Get job status
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        if job_status.get("status") != "completed":
            return jsonify({"error": "Job must be completed before AI editing"}), 400

        # Get timeline data (would load from processed result)
        from parsers.xml_parser import FCP7XMLParser
        from parsers.xml_writer import FCP7XMLWriter
        from services.ai_editor import AITimelineEditor

        timeline_file = job_status.get("timeline_file")
        if not timeline_file or not os.path.exists(timeline_file):
            return jsonify({"error": "Timeline file not found"}), 404

        # Parse original timeline
        parser = FCP7XMLParser()
        timeline = parser.parse_file(timeline_file)

        # Load transcription data if available
        transcription_data = job_status.get("result", {}).get("transcription")

        # Process with AI editor (pass params for short-form and other operations)
        editor = AITimelineEditor()
        result = editor.process_prompt(prompt, timeline, transcription_data, params)

        if not result.get('success'):
            error_message = result.get('message', 'AI edit failed')
            logger.error(f"AI edit failed for job {job_id}: {error_message}")
            logger.error(f"Params received: {params}")
            return jsonify({
                "job_id": job_id,
                "success": False,
                "message": error_message,
                "prompt": prompt
            }), 400

        # Save edited timeline to disk
        edited_timeline = result.get('timeline')
        output_filename = f"{job_id}_ai_edited.xml"
        output_path = os.path.join(Config.TEMP_FOLDER, output_filename)

        writer = FCP7XMLWriter()
        if writer.write_timeline(edited_timeline, output_path):
            # Generate edited audio file from the edited timeline
            from services.audio_extractor import AudioExtractor

            audio_file = job_status.get("audio_file")
            edited_audio_filename = f"{job_id}_ai_edited_audio.wav"
            edited_audio_path = os.path.join(Config.TEMP_FOLDER, edited_audio_filename)

            extractor = AudioExtractor()
            audio_generated = extractor.extract_audio_from_timeline(
                original_audio_path=audio_file,
                timeline=edited_timeline,
                output_path=edited_audio_path,
                crossfade_ms=50  # 50ms crossfade for smooth transitions
            )

            # Update job status with new edited timeline path and audio path
            if isinstance(job_status.get("result"), dict):
                job_status["result"]["ai_edited_output_file"] = output_path  # Store AI edited timeline separately
                if audio_generated:
                    job_status["result"]["edited_audio_file"] = edited_audio_path
                    logger.info(f"Generated edited audio: {edited_audio_path}")
                else:
                    logger.warning(f"Failed to generate edited audio for job {job_id}")

                job_manager.update_job_status(
                    job_id=job_id,
                    status=job_status.get("status", "completed"),
                    result=job_status["result"]
                )

            logger.info(f"AI edit completed for job {job_id}: {result.get('message')}")

            return jsonify({
                "job_id": job_id,
                "success": True,
                "operation": result.get('operation', 'unknown'),
                "message": result.get('message', 'Edit completed'),
                "changes_made": result.get('changes_made', {}),
                "edited_file": output_path,
                "prompt": prompt
            })
        else:
            return jsonify({"error": "Failed to save edited timeline"}), 500

    except Exception as e:
        logger.error(f"Error processing AI edit: {str(e)}")
        return jsonify({"error": f"AI edit failed: {str(e)}"}), 500


@app.route('/ai-chat', methods=['POST'])
@require_auth()
@error_handler
def ai_chat():
    """Conversational AI endpoint for God Mode chat interface"""
    try:
        # Validate request
        data = validate_json_request(request)
        job_id = validate_job_id(data.get('job_id'))
        message = data.get('message', '').strip()

        if not message:
            return jsonify({"error": "Message is required"}), 400

        # Get job status
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        if job_status.get("status") != "completed":
            return jsonify({"error": "Job must be completed before using AI chat"}), 400

        # Get timeline data
        from parsers.xml_parser import FCP7XMLParser
        from services.ai_chat_handler import AIChatHandler

        timeline_file = job_status.get("timeline_file")
        if not timeline_file or not os.path.exists(timeline_file):
            return jsonify({"error": "Timeline file not found"}), 404

        # Parse timeline
        parser = FCP7XMLParser()
        timeline = parser.parse_file(timeline_file)

        # Load transcription data if available
        transcription_data = job_status.get("result", {}).get("transcription")

        # Process with chat handler
        chat_handler = AIChatHandler()
        response = chat_handler.analyze_message(message, timeline, transcription_data)

        logger.info(f"AI chat response for job {job_id}: needs_confirmation={response.get('needs_confirmation')}")

        return jsonify({
            "job_id": job_id,
            "message": response.get('message'),
            "needs_confirmation": response.get('needs_confirmation', False),
            "options": response.get('options', []),
            "preview_data": response.get('preview_data')
        })

    except Exception as e:
        logger.error(f"Error processing AI chat: {str(e)}")
        return jsonify({"error": f"AI chat failed: {str(e)}"}), 500


@app.route('/ai-greeting/<job_id>', methods=['GET'])
@require_auth()
@error_handler
def ai_get_intelligent_greeting(job_id):
    """Get intelligent greeting with content analysis-based suggestions"""
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        # Get job status
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        if job_status.get("status") != "completed":
            return jsonify({"error": "Job must be completed before accessing God Mode"}), 400

        # Get content analysis if available
        result = job_status.get("result", {})
        content_analysis = result.get("content_analysis")

        # Generate intelligent greeting
        from services.ai_chat_handler import AIChatHandler
        chat_handler = AIChatHandler()
        greeting_response = chat_handler.get_intelligent_greeting(content_analysis)

        logger.info(f"Generated intelligent greeting for job {job_id}: {bool(content_analysis)} analysis available")

        return jsonify({
            "job_id": job_id,
            "greeting": greeting_response.get('message'),
            "needs_confirmation": greeting_response.get('needs_confirmation', False),
            "options": greeting_response.get('options', []),
            "has_analysis": bool(content_analysis)
        })

    except Exception as e:
        logger.error(f"Error generating greeting: {str(e)}")
        return jsonify({"error": f"Greeting generation failed: {str(e)}"}), 500


@app.route('/knowledge-base/<job_id>', methods=['GET'])
@require_auth()
@error_handler
def get_knowledge_base(job_id):
    """Get knowledge base for a completed job"""
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        # Get job status
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        # Get content analysis
        result = job_status.get("result", {})
        content_analysis = result.get("content_analysis", {})

        return jsonify({
            "job_id": job_id,
            "content_analysis": content_analysis
        })

    except Exception as e:
        logger.error(f"Error retrieving knowledge base: {str(e)}")
        return jsonify({"error": f"Failed to retrieve knowledge base: {str(e)}"}), 500


@app.route('/knowledge-base/<job_id>', methods=['PUT'])
@require_auth()
@error_handler
def update_knowledge_base(job_id):
    """Update knowledge base with user edits"""
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        # Validate request
        data = validate_json_request(request)
        updated_kb = data.get('content_analysis')

        if not updated_kb:
            return jsonify({"error": "content_analysis is required"}), 400

        # Get job status
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        # Mark as user-modified
        from datetime import datetime
        if 'metadata' not in updated_kb:
            updated_kb['metadata'] = {}
        updated_kb['metadata']['user_modified'] = True
        updated_kb['metadata']['last_edited'] = datetime.utcnow().isoformat()

        # Update job result
        if 'result' not in job_status:
            job_status['result'] = {}
        job_status['result']['content_analysis'] = updated_kb

        # Persist changes
        job_manager.update_job_status(
            job_id=job_id,
            status=job_status.get("status", "completed"),
            result=job_status['result']
        )

        logger.info(f"Knowledge base updated for job {job_id} by user")

        return jsonify({
            "success": True,
            "message": "Knowledge base updated successfully",
            "content_analysis": updated_kb
        })

    except Exception as e:
        logger.error(f"Error updating knowledge base: {str(e)}")
        return jsonify({"error": f"Failed to update knowledge base: {str(e)}"}), 500


@app.route('/re-analyze/<job_id>', methods=['POST'])
@require_auth()
@error_handler
def re_analyze_job(job_id):
    """Manually re-run content analysis on a completed job"""
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        # Get job status
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                return jsonify({"error": "Job not found"}), 404
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            return jsonify({"error": "Job not found"}), 404

        # Check if job is completed
        if job_status.get("status") != "completed":
            return jsonify({"error": "Job must be completed before re-analysis"}), 400

        # Get transcription data
        result = job_status.get("result", {})
        transcription_data = result.get("transcription")

        if not transcription_data:
            return jsonify({"error": "No transcription data available for analysis"}), 400

        # Run content analysis
        from services.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()

        logger.info(f"Re-analyzing content for job {job_id}")
        content_analysis = analyzer.analyze_content(transcription_data)

        # Update job result with new content_analysis
        result['content_analysis'] = content_analysis
        job_manager.update_job_status(job_id, job_status['status'], result)

        logger.info(f"Re-analysis complete for job {job_id}: {content_analysis.get('main_topic', 'Unknown')}")

        return jsonify({
            "success": True,
            "message": "Content analysis updated successfully",
            "content_analysis": content_analysis
        })

    except Exception as e:
        logger.error(f"Error re-analyzing job: {str(e)}")
        return jsonify({"error": f"Re-analysis failed: {str(e)}"}), 500


@app.route('/ai-preview', methods=['POST'])
@require_auth()
@error_handler
def ai_preview():
    """Generate preview of AI operation before executing"""
    try:
        # Validate request
        data = validate_json_request(request)
        job_id = validate_job_id(data.get('job_id'))
        params = data.get('params', {})

        if not params:
            return jsonify({"error": "Parameters are required"}), 400

        # Get job status
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        if job_status.get("status") != "completed":
            return jsonify({"error": "Job must be completed before preview"}), 400

        # Get timeline data
        from parsers.xml_parser import FCP7XMLParser
        from services.ai_chat_handler import AIChatHandler

        timeline_file = job_status.get("timeline_file")
        if not timeline_file or not os.path.exists(timeline_file):
            return jsonify({"error": "Timeline file not found"}), 404

        # Parse timeline
        parser = FCP7XMLParser()
        timeline = parser.parse_file(timeline_file)

        # Load transcription data if available
        transcription_data = job_status.get("result", {}).get("transcription")

        # Generate preview
        chat_handler = AIChatHandler()
        preview = chat_handler.generate_preview(params, timeline, transcription_data)

        logger.info(f"Generated preview for job {job_id}: {preview.get('operation')}")

        return jsonify({
            "job_id": job_id,
            "preview": preview
        })

    except Exception as e:
        logger.error(f"Error generating preview: {str(e)}")
        return jsonify({"error": f"Preview generation failed: {str(e)}"}), 500


@app.route('/auto-analyze/<job_id>', methods=['POST'])
@require_auth()
@error_handler
def auto_analyze_content(job_id):
    """
    Automatically analyze completed job content and generate intelligent repurposing options.
    This is the proactive God Mode feature that suggests edits based on content type detection.
    """
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        # Get job status
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        # Only analyze completed jobs
        if job_status.get("status") != "completed":
            return jsonify({"error": "Job must be completed before auto-analysis"}), 400

        # Get transcription and audio analysis data
        result = job_status.get("result", {})
        transcription_data = result.get("transcription")
        audio_analysis = result.get("audio_analysis")

        if not transcription_data:
            return jsonify({
                "error": "Transcription data required for content analysis",
                "recommendation": "Enable transcription when processing to use auto-analysis"
            }), 400

        # Initialize content analyzer
        analyzer = ContentAnalyzer()

        # Run content analysis
        logger.info(f"Running auto-analysis for job {job_id}")
        analysis_result = analyzer.analyze_content(
            transcription_data=transcription_data,
            audio_analysis_data=audio_analysis
        )

        # Store analysis in job metadata
        if "content_analysis" not in result:
            result["content_analysis"] = {}

        result["content_analysis"] = {
            "analyzed_at": datetime.now().isoformat(),
            "content_type": analysis_result.get("content_type"),
            "key_moments": analysis_result.get("key_moments", []),
            "repurposing_options": analysis_result.get("repurposing_options", []),
            "stats": analysis_result.get("stats", {}),
            "quality_score": analysis_result.get("quality_score", 0.0)
        }

        # Update job status with analysis using store_task_result
        job_manager.store_task_result(job_id, result)

        content_type = analysis_result.get('content_type', {})
        primary_type = content_type.get('primary_type', 'unknown') if isinstance(content_type, dict) else content_type

        logger.info(
            f"Auto-analysis complete for job {job_id}: "
            f"{primary_type} content, "
            f"{len(analysis_result.get('repurposing_options', []))} options generated"
        )

        return jsonify({
            "job_id": job_id,
            "status": "analyzed",
            "analysis": {
                "content_type": analysis_result.get("content_type"),
                "key_moments_count": len(analysis_result.get("key_moments", [])),
                "repurposing_options": analysis_result.get("repurposing_options", []),
                "stats": analysis_result.get("stats", {}),
                "quality_score": analysis_result.get("quality_score", 0.0),
                "recommendations": analysis_result.get("recommendations", [])
            }
        })

    except Exception as e:
        logger.error(f"Error during auto-analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Auto-analysis failed: {str(e)}"}), 500


@app.route('/timeline-comparison/<job_id>', methods=['GET'])
@require_auth()
@error_handler
def get_timeline_comparison(job_id):
    """Get timeline comparison data (original vs edited) for visual preview"""
    try:
        # Validate job ID
        job_id = validate_job_id(job_id)

        # Get job status
        try:
            job_status = job_manager.get_job_status(job_id)
            if not job_status:
                if job_id not in processing_jobs:
                    return jsonify({"error": "Job not found"}), 404
                job_status = processing_jobs[job_id]
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            if job_id not in processing_jobs:
                return jsonify({"error": "Job not found"}), 404
            job_status = processing_jobs[job_id]

        if job_status.get("status") != "completed":
            return jsonify({"error": "Job must be completed before comparison"}), 400

        # Get original and edited timeline files
        from parsers.xml_parser import FCP7XMLParser

        original_timeline_file = job_status.get("timeline_file")
        # Check for AI edited timeline first, fallback to processed timeline
        edited_timeline_file = (
            job_status.get("result", {}).get("ai_edited_output_file") or
            job_status.get("result", {}).get("output_file")
        )

        if not original_timeline_file or not os.path.exists(original_timeline_file):
            return jsonify({"error": "Original timeline file not found"}), 404

        # Parse original timeline
        parser = FCP7XMLParser()
        original_timeline = parser.parse_file(original_timeline_file)

        # Parse edited timeline (if exists)
        edited_timeline = None
        if edited_timeline_file and os.path.exists(edited_timeline_file):
            edited_timeline = parser.parse_file(edited_timeline_file)

        # Generate comparison data
        comparison = generate_timeline_comparison(original_timeline, edited_timeline)

        return jsonify({
            "job_id": job_id,
            "has_edits": edited_timeline is not None,
            "original": comparison["original"],
            "edited": comparison["edited"],
            "diff": comparison["diff"],
            "stats": comparison["stats"]
        })

    except Exception as e:
        logger.error(f"Error generating timeline comparison: {str(e)}")
        return jsonify({"error": f"Comparison failed: {str(e)}"}), 500

def generate_timeline_comparison(original_timeline, edited_timeline=None):
    """Generate comparison data for visual timeline preview"""

    # Extract clips from original timeline
    original_clips = []
    for track in original_timeline.tracks:
        for clip in track.clips:
            original_clips.append({
                "name": clip.name,
                "start": clip.start_time,
                "end": clip.end_time,
                "duration": clip.duration,
                "track": track.index,
                "track_name": track.name,
                "enabled": clip.enabled
            })

    # Calculate original duration
    original_duration = original_timeline.calculate_duration()

    # If no edited timeline, return only original data
    if not edited_timeline:
        return {
            "original": {
                "clips": original_clips,
                "duration": original_duration,
                "total_clips": len(original_clips)
            },
            "edited": None,
            "diff": {
                "removed_regions": [],
                "kept_regions": original_clips,
                "total_removed_duration": 0,
                "compression_ratio": 1.0
            },
            "stats": {
                "original_duration": original_duration,
                "edited_duration": original_duration,
                "time_saved": 0,
                "clips_removed": 0,
                "compression_percentage": 0
            }
        }

    # Extract clips from edited timeline
    edited_clips = []
    for track in edited_timeline.tracks:
        for clip in track.clips:
            edited_clips.append({
                "name": clip.name,
                "start": clip.start_time,
                "end": clip.end_time,
                "duration": clip.duration,
                "track": track.index,
                "track_name": track.name,
                "enabled": clip.enabled
            })

    # Calculate edited duration
    edited_duration = edited_timeline.calculate_duration()

    # Calculate diff regions (what was removed)
    removed_regions = calculate_removed_regions(original_clips, edited_clips)
    kept_regions = edited_clips

    # Calculate statistics
    total_removed_duration = sum(region["duration"] for region in removed_regions)
    time_saved = original_duration - edited_duration

    # Handle edge cases for division by zero
    if original_duration == 0 and edited_duration == 0:
        # Both timelines are empty
        compression_ratio = 1.0
        compression_percentage = 0
    elif original_duration == 0:
        # Original timeline is empty but edited has content (shouldn't happen, but handle it)
        compression_ratio = 0
        compression_percentage = 0
    else:
        # Normal case: calculate ratio
        compression_ratio = edited_duration / original_duration
        compression_percentage = (1 - compression_ratio) * 100

    return {
        "original": {
            "clips": original_clips,
            "duration": original_duration,
            "total_clips": len(original_clips)
        },
        "edited": {
            "clips": edited_clips,
            "duration": edited_duration,
            "total_clips": len(edited_clips)
        },
        "diff": {
            "removed_regions": removed_regions,
            "kept_regions": kept_regions,
            "total_removed_duration": total_removed_duration,
            "compression_ratio": compression_ratio
        },
        "stats": {
            "original_duration": original_duration,
            "edited_duration": edited_duration,
            "time_saved": time_saved,
            "clips_removed": len(original_clips) - len(edited_clips),
            "compression_percentage": round(compression_percentage, 2)
        }
    }

def calculate_removed_regions(original_clips, edited_clips):
    """Calculate which time regions were removed from the timeline"""
    removed_regions = []

    # Sort clips by start time
    original_sorted = sorted(original_clips, key=lambda c: c["start"])
    edited_sorted = sorted(edited_clips, key=lambda c: c["start"])

    # Simple diff: find original clips that don't exist in edited
    # This is a simplified version - real implementation would be more sophisticated
    edited_times = set()
    for clip in edited_sorted:
        for t in range(int(clip["start"] * 100), int(clip["end"] * 100)):
            edited_times.add(t)

    for clip in original_sorted:
        # Check if this original clip is mostly missing in edited
        original_time_range = range(int(clip["start"] * 100), int(clip["end"] * 100))
        overlap = sum(1 for t in original_time_range if t in edited_times)

        # Handle zero-length clips (avoid division by zero)
        time_range_len = len(list(original_time_range))
        if time_range_len == 0:
            continue  # Skip zero-length clips

        if overlap / time_range_len < 0.5:  # Less than 50% overlap
            removed_regions.append({
                "start": clip["start"],
                "end": clip["end"],
                "duration": clip["duration"],
                "name": clip["name"]
            })

    return removed_regions

@app.route('/transcription/<job_id>', methods=['GET'])
@require_auth()
def get_transcription(job_id):
    """Get transcription data for a job"""
    # Validate job ID
    job_id = validate_job_id(job_id)

    # Get job data from job manager (handles both memory and file storage)
    job = job_manager.get_job_status(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Check if transcription is available in the result
    result = job.get("result", {})
    if not result.get("transcription_available"):
        return jsonify({"error": "No transcription available for this job"}), 404

    # Return transcription data from result
    transcription_data = result.get("transcription")
    if not transcription_data:
        return jsonify({"error": "Transcription data not found"}), 404

    # Transform segments to frontend-expected format with word-level timestamps
    # Frontend expects: {timestamp, speaker, text, confidence, words}
    # Backend provides: {start, end, speaker, text, confidence, words}
    segments = transcription_data.get('segments', [])
    transformed_segments = []

    for seg in segments:
        # Transform word-level data for karaoke-style highlighting
        words = seg.get('words', [])
        transformed_words = []
        for word in words:
            transformed_words.append({
                'word': word.get('word', '').strip(),
                'start': word.get('start', 0),
                'end': word.get('end', 0),
                'confidence': word.get('probability', 0.85)
            })

        transformed_segments.append({
            'timestamp': seg.get('start', 0),  # Use 'start' time as timestamp
            'speaker': seg.get('speaker', 'UNKNOWN'),
            'text': seg.get('text', ''),
            'confidence': seg.get('confidence', 0.85),
            'words': transformed_words  # Include word-level timestamps
        })

    # Return transformed data with metadata
    return jsonify({
        "transcription": transformed_segments,
        "job_id": job_id,
        "metadata": {
            "duration": transcription_data.get('duration', 0),
            "word_count": transcription_data.get('word_count', 0),
            "num_speakers": transcription_data.get('num_speakers', 0),
            "provider": transcription_data.get('provider', 'unknown'),
            "confidence": transcription_data.get('confidence', 0.85)
        }
    })

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

    # Allow multiple valid statuses for preview
    allowed_statuses = ["uploaded", "ready", "queued"]
    if job["status"] not in allowed_statuses:
        return jsonify({"error": f"Preview only available for jobs in status: {allowed_statuses}"}), 400

    try:
        # Use the timeline editing engine to get preview
        from services.timeline_editor import TimelineEditingEngine

        timeline_editor = TimelineEditingEngine()
        preview = timeline_editor.get_processing_preview(
            job["audio_file"],
            job["timeline_file"]
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

# Initialize WebSocket support AFTER all routes are defined
# This ensures the SocketIO wrapper includes all Flask routes
# TEMPORARILY DISABLED FOR DEBUGGING
# websocket_manager.init_app(app)

if __name__ == "__main__":
    # Run startup tasks
    startup()

    # DEBUG: Print all registered routes
    print("\n" + "="*60)
    print("REGISTERED ROUTES:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule} -> {rule.methods}")
    print("="*60 + "\n")

    # Start the server - NO SocketIO for debugging
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
