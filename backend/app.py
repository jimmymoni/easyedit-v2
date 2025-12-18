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
from parsers.xml_writer import FCP7XMLWriter

# Import production utilities
from utils import (
    setup_logging, setup_error_handlers, setup_monitoring,
    error_handler, validate_file_upload, validate_processing_options, validate_job_id,
    validate_json_request, sanitize_filename, log_performance,
    system_monitor, health_checker, with_circuit_breaker,
    openai_circuit_breaker, RequestLogger
)

# Import WebSocket support for real-time updates
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

# Store for tracking video transcoding jobs (Phase 1)
video_jobs = {}

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

    # Cleanup stale S3 uploads (added for chunked upload support)
    try:
        from services.s3_upload_manager import S3UploadManager

        s3_manager = S3UploadManager(redis_client=None)
        cleaned = s3_manager.cleanup_stale_uploads(
            max_age_hours=Config.S3_CLEANUP_STALE_UPLOADS_HOURS
        )
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} stale S3 uploads")
    except Exception as e:
        logger.error(f"S3 cleanup failed: {str(e)}")

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
@app.route('/jobs', methods=['GET'])
def list_jobs():
    """List all processing jobs from job manager and in-memory storage"""
    try:
        # Get query parameters for filtering
        limit = int(request.args.get('limit', 50))
        job_type = request.args.get('type')
        status = request.args.get('status')

        # Get jobs from job manager (Redis)
        async_jobs = [] # job_manager.list_jobs(limit=limit, job_type=job_type, status=status)

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
        success = [] # job_manager.cancel_job(job_id)

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
        cleaned_jobs = [] # job_manager.cleanup_old_jobs()

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

# ==========================================
# VIDEO EDITOR ENDPOINTS
# ==========================================

@app.route('/video-upload', methods=['POST'])
@require_auth()
@require_rate_limit("5 per minute, 50 per hour")
@error_handler
def upload_video():
    """
    Upload video file for analysis
    Returns job_id and video metadata
    """
    try:
        # Get video file from request
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400

        video_file = request.files['video']

        # Validate video file
        from utils.error_handlers import validate_file_upload
        validate_file_upload(video_file, Config.ALLOWED_VIDEO_EXTENSIONS, Config.MAX_FILE_SIZE_MB)

        # Generate job ID
        import uuid
        job_id = str(uuid.uuid4())

        # Save video file
        from werkzeug.utils import secure_filename
        video_filename = secure_filename(video_file.filename)
        video_path = os.path.join(Config.UPLOAD_FOLDER, f"{job_id}_video_{video_filename}")
        video_file.save(video_path)

        logger.info(f"Video uploaded: {video_path}")

        # Extract video metadata
        from services.video_audio_extractor import VideoAudioExtractor
        extractor = VideoAudioExtractor()
        video_info = extractor.get_video_info(video_path)

        if not video_info.get('success'):
            return jsonify({"error": "Failed to read video metadata"}), 400

        # Create job entry
        job_data = {
            'job_id': job_id,
            'type': 'video_editing',
            'status': 'uploaded',
            'created_at': time.time(),
            'video_file': video_path,
            'video_info': video_info,
            'progress': 5,
            'message': 'Video uploaded successfully'
        }

        processing_jobs[job_id] = job_data

        logger.info(f"Video job created: {job_id}")

        return jsonify({
            "job_id": job_id,
            "message": "Video uploaded successfully",
            "video_filename": video_filename,
            "video_info": {
                "duration": video_info['duration'],
                "size_mb": video_info['size_mb'],
                "width": video_info['width'],
                "height": video_info['height'],
                "fps": video_info['fps'],
                "codec": video_info['codec']
            }
        }), 200

    except Exception as e:
        logger.error(f"Video upload error: {str(e)}", exc_info=True)
        raise  # Let @error_handler decorator sanitize the response

@app.route('/analyze-video/<job_id>', methods=['POST'])
@require_auth()
@require_rate_limit("2 per minute, 20 per hour")
@error_handler
def analyze_video(job_id):
    """
    Analyze video: extract audio, transcribe, detect repeated takes
    Runs in background
    """
    try:
        from utils.error_handlers import validate_job_id
        job_id = validate_job_id(job_id)

        # Get job
        job_data = processing_jobs.get(job_id)  # Removed job_manager fallback
        if not job_data:
            return jsonify({"error": "Job not found"}), 404

        if job_data.get('type') != 'video_editing':
            return jsonify({"error": "Not a video editing job"}), 400

        video_path = job_data.get('video_file')
        if not video_path or not os.path.exists(video_path):
            return jsonify({"error": "Video file not found"}), 404

        # Update status
        job_data['status'] = 'analyzing'
        job_data['progress'] = 10
        job_data['message'] = 'Starting video analysis...'
        processing_jobs[job_id] = job_data

        # Start background processing
        def analyze_video_task():
            try:
                from services.video_audio_extractor import VideoAudioExtractor
                from services.replicate_whisper_client import ReplicateWhisperClient
                from services.repeated_take_detector import RepeatedTakeDetector

                # Step 1: Extract audio
                logger.info(f"[{job_id}] Extracting audio from video...")
                extractor = VideoAudioExtractor()
                audio_filename = f"{job_id}_extracted_audio.wav"
                audio_path = os.path.join(Config.TEMP_FOLDER, audio_filename)

                audio_result = extractor.extract_audio(video_path, audio_path)
                if not audio_result.get('success'):
                    job_data['status'] = 'failed'
                    job_data['message'] = 'Audio extraction failed'
                    processing_jobs[job_id] = job_data
                    return

                job_data['audio_file'] = audio_path
                job_data['progress'] = 20
                job_data['message'] = 'Audio extracted, starting transcription...'
                processing_jobs[job_id] = job_data

                # Step 2: Transcribe audio
                logger.info(f"[{job_id}] Transcribing audio...")
                whisper_client = ReplicateWhisperClient()
                transcription_result = whisper_client.transcribe_audio(audio_path, enable_speaker_diarization=True)

                if not transcription_result:
                    job_data['status'] = 'failed'
                    job_data['message'] = 'Transcription failed'
                    processing_jobs[job_id] = job_data
                    return

                job_data['transcription'] = transcription_result
                job_data['progress'] = 80
                job_data['message'] = 'Transcription complete, detecting repeated takes...'
                processing_jobs[job_id] = job_data

                # Step 3: Detect repeated takes
                logger.info(f"[{job_id}] Detecting repeated takes...")
                detector = RepeatedTakeDetector()
                analysis_result = detector.detect_repeated_takes(
                    transcription_result,
                    job_data.get('video_info', {})
                )

                job_data['analysis'] = analysis_result
                job_data['status'] = 'analyzed'
                job_data['progress'] = 100
                job_data['message'] = 'Analysis complete'
                processing_jobs[job_id] = job_data

                logger.info(f"[{job_id}] Video analysis complete")

            except Exception as e:
                logger.error(f"[{job_id}] Video analysis error: {str(e)}")
                job_data['status'] = 'failed'
                job_data['message'] = f'Analysis failed: {str(e)}'
                processing_jobs[job_id] = job_data

        # Run in thread
        import threading
        thread = threading.Thread(target=analyze_video_task)
        thread.start()

        return jsonify({
            "job_id": job_id,
            "status": "analyzing",
            "message": "Video analysis started",
            "estimated_time": "10-15 minutes"
        }), 200

    except Exception as e:
        logger.error(f"Analyze video error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/video-analysis/<job_id>', methods=['GET'])
@require_auth()
@error_handler
def get_video_analysis(job_id):
    """
    Get analysis status and results for video job (Phase 2: Cloud Result Loop).

    Returns current status of transcoding + analysis, and analysis results when complete.
    Frontend polls this endpoint to track progress and get final analysis data.
    """
    try:
        from models import VideoJob, VideoJobStatus
        from utils.error_handlers import validate_job_id

        job_id = validate_job_id(job_id)

        # Get VideoJob from video_jobs dict
        video_job = video_jobs.get(job_id)
        if not video_job:
            return jsonify({"error": "Job not found"}), 404

        # Map VideoJobStatus to frontend expected status
        status_map = {
            VideoJobStatus.UPLOADED: 'processing',
            VideoJobStatus.TRANSCODING: 'processing',
            VideoJobStatus.READY: 'analyzing',
            VideoJobStatus.ANALYZING: 'analyzing',
            VideoJobStatus.ANALYZED: 'analyzed',
            VideoJobStatus.FAILED: 'failed',
            VideoJobStatus.CANCELLED: 'failed'
        }

        frontend_status = status_map.get(video_job.status, 'processing')

        # Calculate progress based on stage
        if video_job.status == VideoJobStatus.TRANSCODING:
            # Transcoding is 0-70%
            progress = int(video_job.transcode_progress * 70)
        elif video_job.status == VideoJobStatus.READY:
            # Transcode complete, analysis about to start
            progress = 70
        elif video_job.status == VideoJobStatus.ANALYZING:
            # Analysis in progress (70-90%)
            progress = 80
        elif video_job.status == VideoJobStatus.ANALYZED:
            # Complete
            progress = 100
        else:
            # Initial stages
            progress = 10

        # Build response
        response = {
            "job_id": job_id,
            "status": frontend_status,
            "progress": progress,
            "message": f"Status: {video_job.status.value}"
        }

        # Include analysis data if complete
        if video_job.status == VideoJobStatus.ANALYZED and video_job.analysis:
            response["analysis"] = video_job.analysis

        # Include error if failed
        if video_job.status == VideoJobStatus.FAILED:
            response["message"] = video_job.error_message or video_job.transcode_error or "Processing failed"

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Get video analysis error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/apply-video-cuts/<job_id>', methods=['POST'])
@require_auth()
@require_rate_limit("2 per minute, 20 per hour")
@error_handler
def apply_video_cuts(job_id):
    """Apply cuts to video based on user adjustments"""
    try:
        from utils.error_handlers import validate_job_id
        job_id = validate_job_id(job_id)

        # Get request data
        data = request.get_json() or {}
        segment_adjustments = data.get('segment_adjustments', [])
        encoding_method = data.get('encoding_method', 'reencode')

        # Get job
        job_data = processing_jobs.get(job_id)  # Removed job_manager fallback
        if not job_data:
            return jsonify({"error": "Job not found"}), 404

        if job_data.get('status') != 'analyzed':
            return jsonify({"error": "Job must be analyzed first"}), 400

        # Update segments with user adjustments
        analysis = job_data.get('analysis', {})
        segments = analysis.get('segments', [])

        # Apply user adjustments
        adjustment_map = {adj['id']: adj['action'] for adj in segment_adjustments}
        for segment in segments:
            if segment['id'] in adjustment_map:
                segment['action'] = adjustment_map[segment['id']]

        # Filter segments to keep
        segments_to_keep = [s for s in segments if s['action'] == 'keep']

        # Update status
        job_data['status'] = 'processing'
        job_data['progress'] = 10
        job_data['message'] = 'Cutting video...'
        processing_jobs[job_id] = job_data

        # Start background processing
        def cut_video_task():
            try:
                from services.video_editor import VideoEditor

                video_path = job_data.get('video_file')
                output_filename = f"{job_id}_edited_video.mp4"
                output_path = os.path.join(Config.TEMP_FOLDER, output_filename)

                # Cut video
                logger.info(f"[{job_id}] Cutting video with {len(segments_to_keep)} segments...")
                editor = VideoEditor()
                cut_result = editor.cut_video(video_path, segments_to_keep, output_path, method=encoding_method)

                if not cut_result.get('success'):
                    job_data['status'] = 'failed'
                    job_data['message'] = 'Video cutting failed'
                    processing_jobs[job_id] = job_data
                    return

                job_data['output_video_file'] = output_path
                job_data['status'] = 'completed'
                job_data['progress'] = 100
                job_data['message'] = 'Video editing complete'
                processing_jobs[job_id] = job_data

                logger.info(f"[{job_id}] Video cutting complete: {output_path}")

            except Exception as e:
                logger.error(f"[{job_id}] Video cutting error: {str(e)}")
                job_data['status'] = 'failed'
                job_data['message'] = f'Cutting failed: {str(e)}'
                processing_jobs[job_id] = job_data

        # Run in thread
        import threading
        thread = threading.Thread(target=cut_video_task)
        thread.start()

        return jsonify({
            "job_id": job_id,
            "status": "processing",
            "message": "Video cutting started",
            "estimated_time": "5-10 minutes"
        }), 200

    except Exception as e:
        logger.error(f"Apply video cuts error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download-video/<job_id>', methods=['GET'])
@require_auth()
@require_rate_limit("10 per minute, 100 per hour")
@error_handler
def download_cut_video(job_id):
    """Download processed video file"""
    try:
        from utils.error_handlers import validate_job_id
        job_id = validate_job_id(job_id)

        job_data = processing_jobs.get(job_id)  # Removed job_manager fallback
        if not job_data:
            return jsonify({"error": "Job not found"}), 404

        if job_data.get('status') != 'completed':
            return jsonify({"error": "Job not completed"}), 400

        output_video = job_data.get('output_video_file')
        if not output_video or not os.path.exists(output_video):
            return jsonify({"error": "Edited video not found"}), 404

        return send_file(
            output_video,
            as_attachment=True,
            download_name=f"edited_video_{job_id}.mp4",
            mimetype='video/mp4'
        )

    except Exception as e:
        logger.error(f"Download video error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download-video-xml/<job_id>', methods=['GET'])
@require_auth()
@require_rate_limit("10 per minute, 100 per hour")
@error_handler
def download_video_xml(job_id):
    """Download DaVinci Resolve XML timeline"""
    try:
        from utils.error_handlers import validate_job_id
        from services.s3_upload_manager import S3UploadManager
        from flask import redirect

        job_id = validate_job_id(job_id)

        # Get VideoJob (FIXED: use video_jobs, not processing_jobs)
        if job_id not in video_jobs:
            return jsonify({"error": "Job not found"}), 404

        video_job = video_jobs[job_id]

        # Check if analysis is complete
        if video_job.status != VideoJobStatus.ANALYZED:
            return jsonify({
                "error": "Analysis not complete",
                "status": video_job.status.value,
                "message": "Please wait for processing to complete"
            }), 400

        # Get XML S3 key from metadata
        xml_s3_key = video_job.metadata.get('xml_s3_key') if hasattr(video_job, 'metadata') and video_job.metadata else None

        if not xml_s3_key:
            xml_error = video_job.metadata.get('xml_error', 'Unknown error') if hasattr(video_job, 'metadata') and video_job.metadata else 'No XML generated'
            return jsonify({
                "error": "XML not available",
                "details": xml_error
            }), 404

        # Generate presigned download URL
        s3_manager = S3UploadManager()
        download_url = s3_manager.s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': Config.S3_VIDEO_BUCKET,
                'Key': xml_s3_key
            },
            ExpiresIn=3600  # 1 hour
        )

        logger.info(f"Generated XML download URL for job {job_id}")

        # Redirect to presigned URL (browser will download)
        return redirect(download_url)

    except Exception as e:
        logger.error(f"Download video XML error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/video/system-check', methods=['GET', 'OPTIONS'])
@cross_origin(origins="*")
@error_handler
def check_video_system():
    """
    Check if video processing system is ready (FFmpeg or Cloud)

    Returns:
        {
            'status': 'ready' | 'partial' | 'missing',
            'ffmpeg_available': bool,
            'ffprobe_available': bool,
            'message': str,
            'platform': str,
            'install_instructions': {
                'windows': str,
                'macos': str,
                'linux': str
            },
            'install_url': str,
            'ffmpeg_version': str | None,
            'cloud_processing': bool,
            'replicate_configured': bool
        }
    """
    try:
        import subprocess
        import platform

        # Determine platform
        system = platform.system().lower()

        # Check if cloud processing is enabled
        if Config.USE_CLOUD_VIDEO_PROCESSING:
            replicate_configured = bool(Config.REPLICATE_API_TOKEN)

            if replicate_configured:
                return jsonify({
                    'status': 'ready',
                    'mode': 'cloud',
                    'ffmpeg_available': False,
                    'ffprobe_available': False,
                    'message': 'Video processing uses cloud-based Replicate models (no local FFmpeg required)',
                    'platform': system,
                    'cloud_processing': True,
                    'replicate_configured': True,
                    'install_instructions': {
                        'windows': 'Cloud processing is enabled - no FFmpeg installation required',
                        'macos': 'Cloud processing is enabled - no FFmpeg installation required',
                        'linux': 'Cloud processing is enabled - no FFmpeg installation required'
                    },
                    'install_url': 'https://replicate.com',
                    'ffmpeg_version': None
                })
            else:
                # Cloud mode enabled but no API token
                logger.warning("Cloud processing enabled but REPLICATE_API_TOKEN not configured")
                # Fall back to FFmpeg check

        # Check FFmpeg (local mode or fallback)
        ffmpeg_available = False
        ffmpeg_version = None
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=5
            )
            ffmpeg_available = True
            version_line = result.stdout.decode('utf-8').split('\n')[0]
            ffmpeg_version = version_line
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check FFprobe
        ffprobe_available = False
        try:
            subprocess.run(
                ['ffprobe', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=5
            )
            ffprobe_available = True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Determine platform
        system = platform.system().lower()

        # Installation instructions
        install_instructions = {
            'windows': (
                "1. Download FFmpeg from https://www.gyan.dev/ffmpeg/builds/\n"
                "2. Extract the ZIP file to C:\\ffmpeg\n"
                "3. Add C:\\ffmpeg\\bin to your System PATH:\n"
                "   - Search 'Environment Variables' in Windows\n"
                "   - Edit 'Path' variable\n"
                "   - Add new entry: C:\\ffmpeg\\bin\n"
                "4. Restart your terminal/IDE\n"
                "5. Click 'Retry Check' below"
            ),
            'macos': (
                "1. Install Homebrew if not installed: https://brew.sh\n"
                "2. Run: brew install ffmpeg\n"
                "3. Click 'Retry Check' below"
            ),
            'linux': (
                "Ubuntu/Debian:\n"
                "  sudo apt-get update && sudo apt-get install ffmpeg\n\n"
                "RHEL/CentOS:\n"
                "  sudo yum install ffmpeg\n\n"
                "Arch Linux:\n"
                "  sudo pacman -S ffmpeg\n\n"
                "After installation, click 'Retry Check' below"
            )
        }

        # Determine install URL based on platform
        if system == 'windows':
            install_url = 'https://www.gyan.dev/ffmpeg/builds/'
        elif system == 'darwin':
            install_url = 'https://formulae.brew.sh/formula/ffmpeg'
        else:
            install_url = 'https://ffmpeg.org/download.html'

        # Build response
        if ffmpeg_available and ffprobe_available:
            message = f"Video processing is ready. {ffmpeg_version}"
            status = 'ready'
        elif ffmpeg_available and not ffprobe_available:
            message = "FFmpeg found but FFprobe is missing. Please install complete FFmpeg package."
            status = 'partial'
        else:
            message = "FFmpeg is not installed. Video processing will not work until FFmpeg is installed."
            status = 'missing'

        return jsonify({
            'status': status,
            'ffmpeg_available': ffmpeg_available,
            'ffprobe_available': ffprobe_available,
            'message': message,
            'platform': system,
            'install_instructions': install_instructions,
            'install_url': install_url,
            'ffmpeg_version': ffmpeg_version,
            'cloud_processing': False,
            'replicate_configured': bool(Config.REPLICATE_API_TOKEN)
        })

    except Exception as e:
        logger.error(f"System check error: {str(e)}")
        return jsonify({
            'status': 'error',
            'ffmpeg_available': False,
            'ffprobe_available': False,
            'message': f"System check failed: {str(e)}",
            'platform': 'unknown',
            'install_instructions': {
                'windows': 'System check error occurred',
                'macos': 'System check error occurred',
                'linux': 'System check error occurred'
            },
            'install_url': 'https://ffmpeg.org/download.html',
            'ffmpeg_version': None,
            'cloud_processing': False,
            'replicate_configured': False
        }), 500

# ==========================================
# VIDEO AI EDITOR ENDPOINTS
# ==========================================

@app.route('/video/ai-chat', methods=['POST'])
@cross_origin(origins="*")
@require_auth()
@error_handler
def video_ai_chat():
    """
    Process natural language video editing prompt

    Request body:
        {
            "job_id": "uuid",
            "message": "remove repetitive takes"
        }

    Returns:
        {
            "intent": "remove_repeated_takes",
            "confidence": 0.9,
            "message": "I found 5 repeated takes to remove",
            "preview": {
                "operation": "remove_repeated_takes",
                "description": "...",
                "segments_affected": 5,
                "time_saved": 45.2,
                "new_duration": 180.5
            },
            "needs_confirmation": true
        }
    """
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        message = data.get('message')

        if not job_id or not message:
            return jsonify({"error": "job_id and message are required"}), 400

        # Get job data
        job = processing_jobs.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        if job.get('type') != 'video_editing':
            return jsonify({"error": "Not a video editing job"}), 400

        if job.get('status') not in ['analyzed', 'completed']:
            return jsonify({"error": "Video analysis not complete"}), 400

        # Detect intent using AIChatHandler
        from services.ai_chat_handler import AIChatHandler
        handler = AIChatHandler()

        # Use keyword-based detection for video (faster than LLM)
        intent_data = handler._detect_intent_keywords(message)
        intent = intent_data.get('intent')

        logger.info(f"Video AI chat - Intent: {intent} for job {job_id}")

        # Execute operation using VideoAIOperations
        from services.video_ai_operations import VideoAIOperations
        ops = VideoAIOperations(
            job_data=job,
            transcription_data=job.get('transcription')
        )

        # Route to appropriate operation
        preview_result = None

        if intent == 'remove_repeated_takes':
            preview_result = ops.remove_repeated_takes()
        elif intent == 'create_highlight':
            duration = intent_data.get('duration', 60)
            preview_result = ops.create_highlight_reel(duration)
        elif intent == 'remove_silence':
            threshold = 2.0  # Default 2 seconds
            preview_result = ops.remove_silence(threshold)
        elif intent == 'filter_speaker':
            # Extract speaker number from message
            import re
            speaker_match = re.search(r'speaker\s*(\d+)', message.lower())
            if speaker_match:
                speaker_id = speaker_match.group(1)
                preview_result = ops.filter_by_speaker(speaker_id)
            else:
                return jsonify({
                    "error": "Please specify which speaker (e.g., 'Speaker 1')"
                }), 400
        elif intent == 'suggest_cut_points':
            preview_result = ops.suggest_cut_points()
        else:
            return jsonify({
                "error": f"Intent '{intent}' not supported for video editing",
                "message": "Try: 'remove repetitive takes', 'create 60s highlight', 'remove silence', 'keep only Speaker 1', or 'suggest cut points'"
            }), 400

        # Check for errors in operation
        if preview_result.get('error'):
            return jsonify({
                "error": preview_result['error'],
                "message": preview_result.get('description', 'Operation failed')
            }), 500

        # Return response
        return jsonify({
            "intent": intent,
            "confidence": intent_data.get('confidence', 0.8),
            "message": preview_result.get('description', 'Operation completed'),
            "preview": preview_result,
            "needs_confirmation": True
        })

    except Exception as e:
        logger.error(f"Video AI chat error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/video/ai-preview', methods=['POST'])
@cross_origin(origins="*")
@require_auth()
@error_handler
def video_ai_preview():
    """
    Get preview of AI-suggested edits without applying them

    Request body:
        {
            "job_id": "uuid",
            "operation": "remove_repeated_takes",
            "params": {}
        }

    Returns:
        Preview data for visualization
    """
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        operation = data.get('operation')
        params = data.get('params', {})

        if not job_id or not operation:
            return jsonify({"error": "job_id and operation are required"}), 400

        # Get job data
        job = processing_jobs.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Execute operation
        from services.video_ai_operations import VideoAIOperations
        ops = VideoAIOperations(
            job_data=job,
            transcription_data=job.get('transcription')
        )

        # Get preview based on operation
        if operation == 'remove_repeated_takes':
            preview = ops.remove_repeated_takes()
        elif operation == 'create_highlight':
            duration = params.get('duration', 60)
            preview = ops.create_highlight_reel(duration)
        elif operation == 'remove_silence':
            threshold = params.get('threshold', 2.0)
            preview = ops.remove_silence(threshold)
        elif operation == 'filter_speaker':
            speaker_id = params.get('speaker')
            if not speaker_id:
                return jsonify({"error": "speaker parameter required"}), 400
            preview = ops.filter_by_speaker(speaker_id)
        elif operation == 'suggest_cut_points':
            preview = ops.suggest_cut_points()
        else:
            return jsonify({"error": f"Unknown operation: {operation}"}), 400

        return jsonify(preview)

    except Exception as e:
        logger.error(f"Video AI preview error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/video/ai-apply', methods=['POST'])
@cross_origin(origins="*")
@require_auth()
@error_handler
def video_ai_apply():
    """
    Apply AI-suggested edits to timeline

    Request body:
        {
            "job_id": "uuid",
            "operation": "remove_repeated_takes",
            "params": {}
        }

    Returns:
        {
            "success": true,
            "updated_clips": [...],
            "stats": {...}
        }
    """
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        operation = data.get('operation')
        params = data.get('params', {})

        if not job_id or not operation:
            return jsonify({"error": "job_id and operation are required"}), 400

        # Get job data
        job = processing_jobs.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Execute operation
        from services.video_ai_operations import VideoAIOperations
        ops = VideoAIOperations(
            job_data=job,
            transcription_data=job.get('transcription')
        )

        # Apply operation
        if operation == 'remove_repeated_takes':
            result = ops.remove_repeated_takes()
        elif operation == 'create_highlight':
            duration = params.get('duration', 60)
            result = ops.create_highlight_reel(duration)
        elif operation == 'remove_silence':
            threshold = params.get('threshold', 2.0)
            result = ops.remove_silence(threshold)
        elif operation == 'filter_speaker':
            speaker_id = params.get('speaker')
            if not speaker_id:
                return jsonify({"error": "speaker parameter required"}), 400
            result = ops.filter_by_speaker(speaker_id)
        elif operation == 'suggest_cut_points':
            result = ops.suggest_cut_points()
        else:
            return jsonify({"error": f"Unknown operation: {operation}"}), 400

        # Update job with AI-edited segments
        job['ai_edited_segments'] = result.get('segments', [])
        job['ai_operation'] = operation
        job['ai_operation_result'] = result

        # Return updated clips
        return jsonify({
            "success": True,
            "updated_clips": result.get('segments', []),
            "stats": {
                "segments_affected": result.get('segments_affected', 0),
                "time_saved": result.get('time_saved', 0),
                "new_duration": result.get('new_duration', 0)
            },
            "operation": operation
        })

    except Exception as e:
        logger.error(f"Video AI apply error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ==========================================
# PHASE 1: VIDEO TRANSCODING ENDPOINTS
# ==========================================

def _trigger_background_transcode(job_id: str):
    """
    Trigger background transcoding for a video job.

    This function starts a daemon thread that transcodes the video in the background.
    The thread updates the VideoJob status, progress, and proxy information as it works.

    Implementation (Sub-Step 1.9):
    - Launches daemon thread for async processing
    - Thread-safe VideoJob updates
    - Prevents duplicate transcoding for same job
    - Real-time progress tracking
    - Automatic cleanup on errors

    Args:
        job_id: Video job ID to process
    """
    from services.video_background_processor import start_background_transcode

    logger.info(f"[Phase 1] Triggering background transcode for job: {job_id}")

    # Start background transcoding
    success = start_background_transcode(job_id, video_jobs)

    if success:
        logger.info(f"[Phase 1] [OK] Background transcode started for job: {job_id}")
    else:
        logger.warning(f"[Phase 1] [WARNING] Background transcode not started (already processing or job not found): {job_id}")


@app.route('/upload-video', methods=['POST'])
@require_auth()
@require_rate_limit("5 per minute, 50 per hour")
@error_handler
def upload_video_phase1():
    """
    Phase 1: Upload video file for transcoding to web-optimized proxy.

    This endpoint handles:
    - Video file upload with validation
    - Metadata extraction
    - VideoJob creation
    - Triggering background transcoding (placeholder)

    Request:
        Content-Type: multipart/form-data
        Body:
            video: <binary file data> (required)

    Response (Success - 202 Accepted):
        {
            "success": true,
            "job_id": "uuid",
            "message": "Video uploaded successfully",
            "data": {
                "original_filename": "video.mp4",
                "file_size_mb": 2847.5,
                "duration_seconds": 3600.5,
                "resolution": "1920x1080",
                "fps": 30.0,
                "codec": "h264",
                "estimated_transcode_time_seconds": 240,
                "status": "uploaded"
            }
        }

    Response (Error - 400/500):
        {
            "success": false,
            "error": "Error message",
            "code": "ERROR_CODE"
        }
    """
    try:
        # Import statements moved inside try block for proper error hygiene
        from models import VideoJob, VideoJobStatus
        from services.cloud_video_validator import validate_all_cloud_first
        from utils.error_handlers import (
            VideoFileTooLargeError,
            VideoFormatNotSupportedError,
            VideoCorruptedError,
            FFmpegNotFoundError
        )
        # Step 1: Check if video file is in request
        if 'video' not in request.files:
            return jsonify({
                "success": False,
                "error": "No video file provided",
                "code": "NO_FILE_PROVIDED"
            }), 400

        video_file = request.files['video']

        if video_file.filename == '':
            return jsonify({
                "success": False,
                "error": "No file selected",
                "code": "NO_FILE_SELECTED"
            }), 400

        # Step 2: Get file size
        video_file.seek(0, 2)  # Seek to end
        file_size = video_file.tell()
        video_file.seek(0)  # Reset to beginning

        logger.info(f"Video upload started: {video_file.filename} ({file_size / (1024*1024):.1f} MB)")

        # Step 3: Generate job ID and create temporary path
        job_id = generate_job_id()
        current_user = get_current_user()
        user_id = current_user.get('user_id', 'anonymous') if current_user else 'anonymous'

        # Sanitize filename
        original_filename = sanitize_filename(video_file.filename)
        temp_filename = f"{job_id}_{original_filename}"
        temp_path = os.path.join(Config.TEMP_FOLDER, temp_filename)

        # Step 4: Save to temporary location
        logger.debug(f"Saving video to temp location: {temp_path}")
        video_file.save(temp_path)

        # Step 5: Validate file using cloud-first validators (NO FFmpeg)
        logger.info(f"Validating video (cloud-first): {original_filename}")
        is_valid, error_message = validate_all_cloud_first(
            file_size=file_size,
            filename=original_filename,
            allowed_formats=Config.VIDEO_ALLOWED_FORMATS,
            max_size_mb=Config.VIDEO_MAX_SIZE_MB
        )

        if not is_valid:
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

            logger.warning(f"Video validation failed: {error_message}")
            return jsonify({
                "success": False,
                "error": error_message,
                "code": "VALIDATION_FAILED"
            }), 400

        logger.info(f"Cloud-first validation passed: {original_filename}")

        # Step 6: Move to permanent original location
        permanent_filename = f"{job_id}_{original_filename}"
        permanent_path = os.path.join(Config.VIDEO_UPLOAD_DIR, permanent_filename)

        import shutil
        shutil.move(temp_path, permanent_path)
        logger.info(f"Video moved to permanent storage: {permanent_path}")

        # Step 7: Create VideoJob with placeholder metadata
        # Metadata will be filled by cloud processing later
        video_job = VideoJob(
            job_id=job_id,
            user_id=user_id,
            original_filename=original_filename,
            original_path=permanent_path,
            original_size_bytes=file_size,
            original_format=original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'unknown'
            # Metadata placeholders (cloud will fill these later)
            # duration_seconds, width, height, fps, codec, bitrate, has_audio use default values (0/False)
        )

        # Update status to uploaded
        video_job.update_status(VideoJobStatus.UPLOADED)

        # Step 8: Store VideoJob in memory
        video_jobs[job_id] = video_job

        logger.info(f"VideoJob created with placeholder metadata: {job_id} (user={user_id})")

        # Step 9: Trigger background cloud processing
        _trigger_background_transcode(job_id)

        # Step 10: Return success response (without metadata)
        return jsonify({
            "success": True,
            "job_id": job_id,
            "message": "Video uploaded successfully. Metadata will be extracted by cloud processor.",
            "data": {
                "original_filename": original_filename,
                "file_size_mb": round(video_job.file_size_mb, 2),
                "status": video_job.status.value,
                "note": "Video metadata (duration, resolution, codec) will be available after cloud processing"
            }
        }), 202  # 202 Accepted - processing pending

    except VideoFileTooLargeError as e:
        logger.warning(f"Video file too large: {str(e)}")
        # Cleanup temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

        return jsonify({
            "success": False,
            "error": str(e),
            "code": "FILE_TOO_LARGE",
            "file_size_mb": e.payload.get('file_size_mb'),
            "max_size_mb": e.payload.get('max_size_mb')
        }), 400

    except VideoFormatNotSupportedError as e:
        logger.warning(f"Video format not supported: {str(e)}")
        # Cleanup temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

        return jsonify({
            "success": False,
            "error": str(e),
            "code": "INVALID_FORMAT",
            "format": e.payload.get('format'),
            "allowed_formats": e.payload.get('allowed_formats')
        }), 400

    except VideoCorruptedError as e:
        logger.error(f"Video file corrupted: {str(e)}")
        # Cleanup temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

        return jsonify({
            "success": False,
            "error": str(e),
            "code": "CORRUPTED_FILE"
        }), 400

    except FFmpegNotFoundError as e:
        logger.error(f"FFmpeg not found: {str(e)}")
        # Cleanup temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

        return jsonify({
            "success": False,
            "error": str(e),
            "code": "FFMPEG_NOT_FOUND"
        }), 500

    except Exception as e:
        logger.error(f"Video upload error: {str(e)}", exc_info=True)

        # Cleanup temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

        # Cleanup permanent file if it exists
        if 'permanent_path' in locals() and os.path.exists(permanent_path):
            try:
                os.remove(permanent_path)
            except:
                pass

        return jsonify({
            "success": False,
            "error": "An unexpected error occurred during video upload",
            "code": "INTERNAL_ERROR"
        }), 500


# ============================================================================
# S3 CHUNKED UPLOAD ENDPOINTS
# Supports 3GB+ video uploads with resumable chunked upload to S3
# ============================================================================

@app.route('/upload/init', methods=['POST'])
@require_auth()
@require_rate_limit("10 per minute")
@error_handler
def init_chunked_upload():
    """
    Initialize S3 multipart upload session for large video files.

    Request Body (JSON):
    {
        "filename": "my_video.mp4",
        "file_size": 3221225472,  // 3GB in bytes
        "chunk_size": 10485760     // 10MB (optional)
    }

    Response (200 OK):
    {
        "success": true,
        "job_id": "abc-123-def-456",
        "upload_session": {
            "upload_id": "s3-multipart-upload-id",
            "upload_session_id": "abc-123-def-456",
            "s3_key": "uploads/abc-123/my_video.mp4",
            "total_chunks": 308,
            "chunk_urls": [
                {
                    "part_number": 1,
                    "upload_url": "https://s3.amazonaws.com/...",
                    "chunk_index": 0,
                    "start_byte": 0,
                    "end_byte": 10485759,
                    "size": 10485760
                },
                // ... more chunks
            ],
            "expires_at": "2025-12-18T12:00:00Z",
            "chunk_size": 10485760
        }
    }

    Error Responses:
    - 400: Missing required fields
    - 400: File size exceeds maximum (5GB)
    - 400: Invalid filename
    - 401: Unauthorized
    - 500: S3 initialization failed
    """
    try:
        from services.s3_upload_manager import S3UploadManager
        from models import VideoJob, VideoJobStatus

        data = request.get_json()

        # Validate request
        if not data or 'filename' not in data or 'file_size' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: filename, file_size'
            }), 400

        filename = sanitize_filename(data['filename'])
        file_size = int(data['file_size'])
        chunk_size = int(data.get('chunk_size', 10485760))  # 10MB default

        # Validate file size (max 5GB)
        max_size = Config.S3_MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            return jsonify({
                'success': False,
                'error': f'File size ({file_size / (1024**3):.2f}GB) exceeds maximum ({Config.S3_MAX_FILE_SIZE_MB / 1024:.1f}GB)',
                'code': 'FILE_TOO_LARGE'
            }), 400

        # Validate filename extension
        allowed_exts = Config.ALLOWED_VIDEO_EXTENSIONS
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in allowed_exts:
            return jsonify({
                'success': False,
                'error': f'Invalid file extension: .{ext}',
                'allowed_extensions': list(allowed_exts)
            }), 400

        # Generate job ID
        job_id = generate_job_id()
        current_user = get_current_user()
        user_id = current_user.get('user_id', 'anonymous') if current_user else 'anonymous'

        # Initialize S3 multipart upload
        s3_manager = S3UploadManager(redis_client=None)
        upload_session = s3_manager.initialize_multipart_upload(
            job_id=job_id,
            filename=filename,
            file_size=file_size,
            chunk_size=chunk_size
        )

        # Create VideoJob (status: UPLOADING)
        video_job = VideoJob(
            job_id=job_id,
            user_id=user_id,
            status=VideoJobStatus.UPLOADING,
            original_filename=filename,
            original_size_bytes=file_size,
            metadata={
                's3_upload_id': upload_session['upload_id'],
                's3_key': upload_session['s3_key'],
                'upload_method': 's3_multipart'
            }
        )

        # Store VideoJob
        video_jobs[job_id] = video_job

        logger.info(
            f"Chunked upload initialized: job={job_id}, "
            f"size={file_size / (1024**3):.2f}GB, chunks={upload_session['total_chunks']}"
        )

        return jsonify({
            'success': True,
            'job_id': job_id,
            'upload_session': upload_session
        }), 200

    except Exception as e:
        logger.error(f"Failed to initialize chunked upload: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to initialize upload',
            'code': 'INIT_FAILED'
        }), 500


@app.route('/upload/chunk-complete', methods=['POST'])
@require_auth()
@require_rate_limit("100 per minute")  # High rate limit for chunk notifications
@error_handler
def chunk_upload_complete():
    """
    Notify backend that a chunk has been successfully uploaded to S3.

    Request Body (JSON):
    {
        "job_id": "abc-123-def-456",
        "part_number": 1,
        "etag": "s3-etag-value"
    }

    Response (200 OK):
    {
        "success": true,
        "progress": {
            "completed_chunks": [1, 2, 3],
            "total_chunks": 308,
            "progress": 0.0097,  // 0.97%
            "is_complete": false
        }
    }
    """
    try:
        from services.s3_upload_manager import S3UploadManager

        data = request.get_json()

        if not data or 'job_id' not in data or 'part_number' not in data or 'etag' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: job_id, part_number, etag'
            }), 400

        job_id = data['job_id']
        part_number = int(data['part_number'])
        etag = data['etag']

        # Mark chunk as complete
        s3_manager = S3UploadManager(redis_client=None)
        progress_data = s3_manager.mark_chunk_complete(
            job_id=job_id,
            part_number=part_number,
            etag=etag
        )

        # Update VideoJob progress
        if job_id in video_jobs:
            video_job = video_jobs[job_id]
            video_job.transcode_progress = progress_data['progress']
            video_job.updated_at = datetime.now()

        return jsonify({
            'success': True,
            'progress': progress_data
        }), 200

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        logger.error(f"Failed to mark chunk complete: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to update chunk status'
        }), 500


@app.route('/upload/complete', methods=['POST'])
@require_auth()
@require_rate_limit("10 per minute")
@error_handler
def complete_chunked_upload():
    """
    Finalize S3 multipart upload after all chunks are uploaded.

    Request Body (JSON):
    {
        "job_id": "abc-123-def-456"
    }

    Response (200 OK):
    {
        "success": true,
        "job_id": "abc-123-def-456",
        "s3_url": "s3://bucket/uploads/abc-123/video.mp4",
        "message": "Upload completed successfully"
    }

    Response (202 Accepted):
    {
        "success": true,
        "job_id": "abc-123-def-456",
        "message": "Upload finalized, transcoding started"
    }
    """
    try:
        from services.s3_upload_manager import S3UploadManager
        from models import VideoJobStatus

        data = request.get_json()

        if not data or 'job_id' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: job_id'
            }), 400

        job_id = data['job_id']

        # Complete multipart upload
        s3_manager = S3UploadManager(redis_client=None)
        s3_url = s3_manager.complete_multipart_upload(job_id)

        # Update VideoJob
        if job_id in video_jobs:
            video_job = video_jobs[job_id]
            video_job.update_status(VideoJobStatus.UPLOADED)
            video_job.original_path = s3_url  # Store S3 URL
            video_job.transcode_progress = 1.0

            # Trigger background transcoding (cloud-based)
            _trigger_background_transcode(job_id)

            logger.info(f"Upload completed, transcoding started: job={job_id}")

            return jsonify({
                'success': True,
                'job_id': job_id,
                'message': 'Upload finalized, transcoding started'
            }), 202
        else:
            logger.warning(f"VideoJob not found after upload: {job_id}")
            return jsonify({
                'success': True,
                'job_id': job_id,
                's3_url': s3_url,
                'message': 'Upload completed successfully'
            }), 200

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Failed to complete upload: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to finalize upload'
        }), 500


@app.route('/upload/resume', methods=['POST'])
@require_auth()
@require_rate_limit("20 per minute")
@error_handler
def resume_chunked_upload():
    """
    Get upload session status to resume interrupted uploads.

    Request Body (JSON):
    {
        "job_id": "abc-123-def-456"
    }

    Response (200 OK):
    {
        "success": true,
        "job_id": "abc-123-def-456",
        "session": {
            "upload_id": "s3-multipart-upload-id",
            "s3_key": "uploads/abc-123/video.mp4",
            "total_chunks": 308,
            "completed_chunks": [1, 2, 3, 5, 6],  // Missing chunk 4
            "missing_chunks": [4, 7, 8, ..., 308],
            "progress": 0.016,  // 1.6%
            "status": "uploading"
        }
    }

    Response (404 Not Found):
    {
        "success": false,
        "error": "Upload session not found"
    }
    """
    try:
        from services.s3_upload_manager import S3UploadManager

        data = request.get_json()

        if not data or 'job_id' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: job_id'
            }), 400

        job_id = data['job_id']

        # Get upload session
        s3_manager = S3UploadManager(redis_client=None)
        session = s3_manager.get_upload_status(job_id)

        if not session:
            return jsonify({
                'success': False,
                'error': 'Upload session not found'
            }), 404

        # Calculate missing chunks
        all_chunks = set(range(1, session['total_chunks'] + 1))
        completed = set(session['completed_chunks'])
        missing = sorted(list(all_chunks - completed))

        progress = len(completed) / session['total_chunks']

        return jsonify({
            'success': True,
            'job_id': job_id,
            'session': {
                'upload_id': session['upload_id'],
                's3_key': session['s3_key'],
                'total_chunks': session['total_chunks'],
                'completed_chunks': session['completed_chunks'],
                'missing_chunks': missing,
                'progress': progress,
                'status': session['status']
            }
        }), 200

    except Exception as e:
        logger.error(f"Failed to get resume info: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve upload status'
        }), 500


@app.route('/upload/abort', methods=['POST'])
@require_auth()
@require_rate_limit("10 per minute")
@error_handler
def abort_chunked_upload():
    """
    Abort and cleanup an incomplete multipart upload.

    Request Body (JSON):
    {
        "job_id": "abc-123-def-456"
    }

    Response (200 OK):
    {
        "success": true,
        "message": "Upload aborted and cleaned up"
    }
    """
    try:
        from services.s3_upload_manager import S3UploadManager
        from models import VideoJobStatus

        data = request.get_json()

        if not data or 'job_id' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: job_id'
            }), 400

        job_id = data['job_id']

        # Abort upload
        s3_manager = S3UploadManager(redis_client=None)
        success = s3_manager.abort_multipart_upload(job_id)

        # Update VideoJob status
        if job_id in video_jobs:
            video_job = video_jobs[job_id]
            video_job.update_status(VideoJobStatus.CANCELLED)
            video_job.error_message = "Upload cancelled by user"

        if success:
            return jsonify({
                'success': True,
                'message': 'Upload aborted and cleaned up'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to abort upload'
            }), 500

    except Exception as e:
        logger.error(f"Failed to abort upload: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to abort upload'
        }), 500


@app.route('/video-status/<job_id>', methods=['GET'])
@require_auth()
@require_rate_limit("60 per minute")
@error_handler
def get_video_status(job_id: str):
    """
    Get the status of a video processing job.

    This endpoint returns detailed information about a video job including:
    - Current processing status (uploaded, transcoding, ready, failed)
    - Original video metadata (duration, resolution, codec, etc.)
    - Transcoding progress and time estimates
    - Proxy video availability and URL

    Path Parameters:
        job_id: UUID of the video processing job

    Response (Success - 200 OK):
        {
            "success": true,
            "job_id": "uuid",
            "status": "transcoding",  # uploaded, transcoding, ready, failed
            "original_metadata": {
                "filename": "video.mp4",
                "size_bytes": 2987654321,
                "size_mb": 2847.5,
                "format": "mp4",
                "duration_seconds": 3600.5,
                "resolution": "1920x1080",
                "width": 1920,
                "height": 1080,
                "fps": 30.0,
                "codec": "h264",
                "bitrate": 5000000,
                "has_audio": true
            },
            "transcode_progress": 0.65,  # 0.0 to 1.0
            "transcode_progress_percent": 65,  # 0 to 100
            "estimated_time_remaining": 120,  # seconds, null if not transcoding
            "estimated_transcode_time_seconds": 240,  # total estimated time
            "elapsed_transcode_time_seconds": 156,  # elapsed time, null if not started
            "proxy_ready": false,
            "proxy_url": null,  # URL when ready
            "proxy_size_mb": null,  # size when ready
            "transcode_started_at": "2025-12-15T10:30:00Z",  # ISO 8601
            "transcode_completed_at": null,  # ISO 8601 when complete
            "transcode_error": null,  # error message if failed
            "created_at": "2025-12-15T10:25:00Z",
            "updated_at": "2025-12-15T10:30:45Z"
        }

    Response (Job Not Found - 404):
        {
            "success": false,
            "error": "Video job not found: <job_id>",
            "code": "JOB_NOT_FOUND",
            "job_id": "<job_id>"
        }

    Response (Invalid Job ID - 400):
        {
            "success": false,
            "error": "Job ID contains invalid characters",
            "status_code": 400
        }
    """
    from models import VideoJob, VideoJobStatus
    from utils.error_handlers import VideoJobNotFoundError

    try:
        # Step 1: Validate job_id
        job_id = validate_job_id(job_id)

        # Step 2: Look up VideoJob in memory
        if job_id not in video_jobs:
            raise VideoJobNotFoundError(job_id)

        video_job = video_jobs[job_id]

        # Step 3: Check if metadata exists (should always exist after upload)
        if not video_job.original_filename:
            logger.error(f"VideoJob {job_id} missing required metadata")
            return jsonify({
                "success": False,
                "error": f"Video job {job_id} is missing required metadata",
                "code": "MISSING_METADATA",
                "job_id": job_id
            }), 500

        # Step 4: Build response using VideoJob.to_dict()
        job_dict = video_job.to_dict()

        # Step 5: Structure response with organized sections
        response = {
            "success": True,
            "job_id": job_dict['job_id'],
            "user_id": job_dict['user_id'],
            "status": job_dict['status'],

            # Original metadata section
            "original_metadata": {
                "filename": job_dict['original_filename'],
                "size_bytes": job_dict['original_size_bytes'],
                "size_mb": job_dict['file_size_mb'],
                "format": job_dict['original_format'],
                "duration_seconds": job_dict['duration_seconds'],
                "resolution": job_dict['resolution'],
                "width": job_dict['width'],
                "height": job_dict['height'],
                "fps": job_dict['fps'],
                "codec": job_dict['codec'],
                "bitrate": job_dict['bitrate'],
                "has_audio": job_dict['has_audio']
            },

            # Transcoding progress section
            "transcode_progress": job_dict['transcode_progress'],
            "transcode_progress_percent": job_dict['transcode_progress_percent'],
            "estimated_time_remaining": job_dict['estimated_time_remaining_seconds'],
            "estimated_transcode_time_seconds": job_dict['estimated_transcode_time_seconds'],
            "elapsed_transcode_time_seconds": job_dict['elapsed_transcode_time_seconds'],

            # Proxy section
            "proxy_ready": job_dict['proxy_ready'],
            "proxy_url": job_dict['proxy_url'],
            "proxy_size_mb": job_dict['proxy_size_mb'],

            # Timestamps section
            "transcode_started_at": job_dict['transcode_started_at'],
            "transcode_completed_at": job_dict['transcode_completed_at'],
            "transcode_error": job_dict['transcode_error'],
            "created_at": job_dict['created_at'],
            "updated_at": job_dict['updated_at'],

            # Additional metadata
            "metadata": job_dict['metadata']
        }

        logger.debug(f"Video status retrieved for job {job_id}: {video_job.status.value}")
        return jsonify(response), 200

    except VideoJobNotFoundError as e:
        logger.warning(f"Video job not found: {job_id}")
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "JOB_NOT_FOUND",
            "job_id": job_id
        }), 404

    except ValidationError as e:
        logger.warning(f"Invalid job_id: {job_id}")
        return jsonify(e.to_dict()), 400

    except Exception as e:
        logger.error(f"Error retrieving video status for {job_id}: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred while retrieving video status",
            "code": "INTERNAL_ERROR",
            "job_id": job_id
        }), 500


@app.route('/video-proxy/<job_id>', methods=['GET'])
@require_auth()
@require_rate_limit("120 per minute")
@error_handler
def stream_video_proxy(job_id: str):
    """
    Stream the web-optimized proxy video file with HTTP Range support.

    This endpoint serves the transcoded proxy video file for browser playback.
    It supports HTTP Range requests (RFC 7233) to enable video seeking and
    efficient streaming.

    Features:
    - HTTP Range request support (206 Partial Content)
    - Efficient chunked streaming
    - Proper MIME type detection
    - Browser-compatible headers (Accept-Ranges, Content-Range, Content-Length)
    - Authentication and rate limiting

    Path Parameters:
        job_id: UUID of the video processing job

    Request Headers (Optional):
        Range: bytes=<start>-<end>  # For partial content requests

    Response (Success - 200 OK / 206 Partial Content):
        Headers:
            Content-Type: video/mp4
            Accept-Ranges: bytes
            Content-Length: <file_size>
            Content-Range: bytes <start>-<end>/<total>  # Only for 206
            Cache-Control: public, max-age=3600
        Body:
            <video binary data>

    Response (Proxy Not Ready - 425 Too Early):
        {
            "success": false,
            "error": "Proxy video is not ready yet. Current status: transcoding",
            "code": "PROXY_NOT_READY",
            "job_id": "<job_id>",
            "status": "transcoding",
            "progress_percent": 65
        }

    Response (Job Not Found - 404):
        {
            "success": false,
            "error": "Video job not found: <job_id>",
            "code": "JOB_NOT_FOUND",
            "job_id": "<job_id>"
        }

    Response (Proxy File Not Found - 404):
        {
            "success": false,
            "error": "Proxy file not found on disk",
            "code": "PROXY_FILE_NOT_FOUND",
            "job_id": "<job_id>"
        }

    Response (Invalid Range - 416):
        {
            "success": false,
            "error": "Requested range not satisfiable",
            "code": "INVALID_RANGE"
        }
    """
    from models import VideoJob, VideoJobStatus
    from utils.error_handlers import VideoJobNotFoundError
    from flask import Response, make_response
    import mimetypes

    try:
        # Step 1: Validate job_id
        job_id = validate_job_id(job_id)

        # Step 2: Look up VideoJob in memory
        if job_id not in video_jobs:
            raise VideoJobNotFoundError(job_id)

        video_job = video_jobs[job_id]

        # Step 3: Check if proxy is ready
        if not video_job.proxy_ready:
            logger.warning(f"Proxy not ready for job {job_id}, status: {video_job.status.value}")
            return jsonify({
                "success": False,
                "error": f"Proxy video is not ready yet. Current status: {video_job.status.value}",
                "code": "PROXY_NOT_READY",
                "job_id": job_id,
                "status": video_job.status.value,
                "progress_percent": video_job.transcode_progress_percent
            }), 425  # 425 Too Early - resource not yet available

        # Step 4: Check if proxy file exists on disk
        if not video_job.proxy_path or not os.path.exists(video_job.proxy_path):
            logger.error(f"Proxy file missing for job {job_id}: {video_job.proxy_path}")
            return jsonify({
                "success": False,
                "error": "Proxy file not found on disk",
                "code": "PROXY_FILE_NOT_FOUND",
                "job_id": job_id
            }), 404

        proxy_path = video_job.proxy_path
        file_size = os.path.getsize(proxy_path)

        # Step 5: Detect MIME type
        mime_type, _ = mimetypes.guess_type(proxy_path)
        if not mime_type:
            # Default to MP4 for proxy videos
            mime_type = 'video/mp4'

        # Step 6: Parse Range header (if present)
        range_header = request.headers.get('Range', None)

        if range_header:
            # Parse Range: bytes=start-end
            try:
                # Extract byte range
                range_match = range_header.replace('bytes=', '').strip()
                ranges = range_match.split('-')

                # Parse start and end
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1

                # Validate range
                if start >= file_size or start < 0 or end >= file_size or start > end:
                    logger.warning(f"Invalid range request for job {job_id}: {range_header}")
                    return jsonify({
                        "success": False,
                        "error": "Requested range not satisfiable",
                        "code": "INVALID_RANGE"
                    }), 416  # 416 Range Not Satisfiable

                # Calculate content length
                content_length = end - start + 1

                # Step 7: Stream partial content (206 Partial Content)
                def generate_partial():
                    """Generator for streaming partial content"""
                    with open(proxy_path, 'rb') as video_file:
                        video_file.seek(start)
                        remaining = content_length
                        chunk_size = 8192  # 8KB chunks

                        while remaining > 0:
                            chunk = video_file.read(min(chunk_size, remaining))
                            if not chunk:
                                break
                            remaining -= len(chunk)
                            yield chunk

                response = Response(generate_partial(), status=206, mimetype=mime_type)
                response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                response.headers['Content-Length'] = str(content_length)
                response.headers['Accept-Ranges'] = 'bytes'
                response.headers['Cache-Control'] = 'public, max-age=3600'

                logger.debug(f"Streaming partial content for job {job_id}: bytes {start}-{end}/{file_size}")
                return response

            except (ValueError, IndexError) as e:
                logger.warning(f"Malformed range header for job {job_id}: {range_header}")
                return jsonify({
                    "success": False,
                    "error": "Malformed range header",
                    "code": "INVALID_RANGE"
                }), 416

        # Step 8: Stream full content (200 OK)
        def generate_full():
            """Generator for streaming full content"""
            with open(proxy_path, 'rb') as video_file:
                chunk_size = 8192  # 8KB chunks
                while True:
                    chunk = video_file.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        response = Response(generate_full(), status=200, mimetype=mime_type)
        response.headers['Content-Length'] = str(file_size)
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'public, max-age=3600'

        logger.info(f"Streaming full video proxy for job {job_id} ({file_size} bytes)")
        return response

    except VideoJobNotFoundError as e:
        logger.warning(f"Video job not found for streaming: {job_id}")
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "JOB_NOT_FOUND",
            "job_id": job_id
        }), 404

    except ValidationError as e:
        logger.warning(f"Invalid job_id for streaming: {job_id}")
        return jsonify(e.to_dict()), 400

    except Exception as e:
        logger.error(f"Error streaming video proxy for {job_id}: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred while streaming video",
            "code": "INTERNAL_ERROR",
            "job_id": job_id
        }), 500


# ==========================================
# WAVEFORM API (Phase 2.2.1)
# ==========================================

@app.route('/waveform/<job_id>', methods=['GET'])
@require_auth()
@require_rate_limit("60 per minute")
@error_handler
def get_waveform(job_id: str):
    """
    Get waveform peak data for timeline visualization.

    This endpoint returns waveform peak data extracted from the video's audio track.
    The waveform is generated on first request (lazy generation) and cached for
    subsequent requests.

    Features:
    - Lazy generation (generate on first request)
    - Disk caching (fast subsequent requests)
    - ~1500 peak samples (optimized for timeline rendering)
    - Normalized peak values [0, 1]
    - Authentication and rate limiting

    Path Parameters:
        job_id: UUID of the video processing job

    Response (Success - 200 OK):
        {
            "job_id": "abc-123",
            "peaks": [0.0, 0.12, 0.34, ...],  // ~1500 samples
            "sample_rate": 44100,
            "duration": 300.5,
            "channels": 1,
            "samples": 1500,
            "created_at": "2025-12-16T10:30:00Z"
        }

    Response (Waveform Generating - 425 Too Early):
        {
            "success": false,
            "error": "Waveform is being generated. Please try again shortly.",
            "code": "WAVEFORM_GENERATING",
            "job_id": "abc-123",
            "status": "generating"
        }

    Response (Proxy Not Ready - 425 Too Early):
        {
            "success": false,
            "error": "Proxy video must be ready before generating waveform",
            "code": "PROXY_NOT_READY",
            "job_id": "abc-123",
            "proxy_status": "transcoding",
            "progress_percent": 65
        }

    Response (Job Not Found - 404):
        {
            "success": false,
            "error": "Video job not found: abc-123",
            "code": "JOB_NOT_FOUND",
            "job_id": "abc-123"
        }

    Response (Waveform Generation Failed - 500):
        {
            "success": false,
            "error": "Waveform generation failed: No audio stream found",
            "code": "WAVEFORM_GENERATION_FAILED",
            "job_id": "abc-123"
        }
    """
    from models import VideoJob, VideoJobStatus
    from utils.error_handlers import VideoJobNotFoundError
    from services.waveform_generator import generate_waveform, load_waveform_cache

    try:
        # Step 1: Validate job_id
        job_id = validate_job_id(job_id)

        # Step 2: Look up VideoJob in memory
        if job_id not in video_jobs:
            raise VideoJobNotFoundError(job_id)

        video_job = video_jobs[job_id]

        # Step 3: Check if proxy is ready (waveform requires proxy video)
        if not video_job.proxy_ready:
            logger.warning(f"Proxy not ready for waveform generation: job {job_id}, status: {video_job.status.value}")
            return jsonify({
                "success": False,
                "error": "Proxy video must be ready before generating waveform",
                "code": "PROXY_NOT_READY",
                "job_id": job_id,
                "proxy_status": video_job.status.value,
                "progress_percent": video_job.transcode_progress_percent
            }), 425  # 425 Too Early

        # Step 4: Check waveform status
        if video_job.waveform_status == 'generating':
            logger.info(f"Waveform is currently being generated for job {job_id}")
            return jsonify({
                "success": False,
                "error": "Waveform is being generated. Please try again shortly.",
                "code": "WAVEFORM_GENERATING",
                "job_id": job_id,
                "status": "generating"
            }), 425  # 425 Too Early

        if video_job.waveform_status == 'failed':
            logger.error(f"Waveform generation previously failed for job {job_id}: {video_job.waveform_error}")
            return jsonify({
                "success": False,
                "error": f"Waveform generation failed: {video_job.waveform_error}",
                "code": "WAVEFORM_GENERATION_FAILED",
                "job_id": job_id
            }), 500

        # Step 5: Check if waveform is already cached
        if video_job.waveform_status == 'ready' and video_job.waveform_file:
            # Load cached waveform
            cached_waveform = load_waveform_cache(job_id)
            if cached_waveform:
                logger.info(f"Serving cached waveform for job {job_id}")
                return jsonify(cached_waveform.to_dict()), 200
            else:
                logger.warning(f"Waveform status is 'ready' but cache file is missing for job {job_id}")
                # Fall through to regenerate

        # Step 6: Generate waveform (first request or cache miss)
        logger.info(f"Generating waveform for job {job_id}")
        video_job.mark_waveform_generating()

        try:
            # Generate waveform from proxy video
            waveform_data = generate_waveform(
                video_path=video_job.proxy_path,
                job_id=job_id,
                samples=video_job.waveform_samples
            )

            # Mark as ready
            video_job.mark_waveform_ready(
                waveform_file=waveform_data.to_dict().get('created_at', ''),  # Use timestamp as identifier
                duration=waveform_data.duration
            )

            logger.info(f"Waveform generated successfully for job {job_id}: {waveform_data.samples} samples, {waveform_data.duration:.2f}s")

            return jsonify(waveform_data.to_dict()), 200

        except ValueError as e:
            # Video has no audio stream
            error_msg = str(e)
            video_job.mark_waveform_failed(error_msg)
            logger.error(f"Waveform generation failed for job {job_id}: {error_msg}")
            return jsonify({
                "success": False,
                "error": f"Waveform generation failed: {error_msg}",
                "code": "WAVEFORM_GENERATION_FAILED",
                "job_id": job_id
            }), 500

        except Exception as e:
            # Unexpected error
            error_msg = f"Unexpected error during waveform generation: {str(e)}"
            video_job.mark_waveform_failed(error_msg)
            logger.error(f"Waveform generation failed for job {job_id}: {error_msg}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Waveform generation failed due to an internal error",
                "code": "WAVEFORM_GENERATION_FAILED",
                "job_id": job_id
            }), 500

    except VideoJobNotFoundError as e:
        logger.warning(f"Video job not found for waveform request: {job_id}")
        return jsonify({
            "success": False,
            "error": e.message,
            "code": "JOB_NOT_FOUND",
            "job_id": job_id
        }), 404

    except ValidationError as e:
        logger.warning(f"Invalid job_id for waveform request: {job_id}")
        return jsonify(e.to_dict()), 400

    except Exception as e:
        logger.error(f"Error retrieving waveform for {job_id}: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred while retrieving waveform",
            "code": "INTERNAL_ERROR",
            "job_id": job_id
        }), 500


# ==========================================
# ERROR HANDLERS
# ==========================================

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
