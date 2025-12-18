"""
Background video transcoding service with thread-safe processing.

This module provides background transcoding functionality for uploaded videos.
It launches daemon threads to process videos asynchronously, updates job status,
and tracks progress in real-time.

Features:
- Thread-safe VideoJob updates
- Prevents duplicate transcoding for same job
- Real-time progress tracking
- Automatic cleanup on errors
- Comprehensive logging
"""

import logging
import threading
import os
from typing import Set, Dict
from datetime import datetime

# Import dependencies at module level to avoid caching issues
from models import VideoJob, VideoJobStatus
from services.video_audio_extractor import VideoAudioExtractor
from services.replicate_whisper_client import ReplicateWhisperClient
from services.repeated_take_detector import RepeatedTakeDetector
from config import Config

logger = logging.getLogger(__name__)

# Global state for thread management
_active_jobs: Set[str] = set()  # Track currently processing job_ids
_active_jobs_lock = threading.Lock()  # Lock for active_jobs set
_job_locks: Dict[str, threading.Lock] = {}  # Individual locks per job
_job_locks_lock = threading.Lock()  # Lock for job_locks dict


def start_background_transcode(job_id: str, video_jobs: dict) -> bool:
    """
    Start background transcoding for a video job.

    This function launches a daemon thread to transcode the video in the background.
    It prevents multiple transcoding threads for the same job and ensures thread-safe
    access to the VideoJob object.

    Args:
        job_id: ID of the video job to transcode
        video_jobs: Reference to the global video_jobs dictionary

    Returns:
        True if transcoding was started, False if job is already being processed

    Example:
        >>> video_jobs = {"abc-123": VideoJob(...)}
        >>> success = start_background_transcode("abc-123", video_jobs)
        >>> if success:
        ...     print("Transcoding started in background")
    """
    from models import VideoJob, VideoJobStatus

    # Check if job exists
    if job_id not in video_jobs:
        logger.error(f"Cannot start transcode: job {job_id} not found")
        return False

    # Check if already processing (thread-safe)
    with _active_jobs_lock:
        if job_id in _active_jobs:
            logger.warning(f"Transcode already in progress for job {job_id}")
            return False

        # Mark as active
        _active_jobs.add(job_id)

    # Create a job-specific lock if it doesn't exist
    with _job_locks_lock:
        if job_id not in _job_locks:
            _job_locks[job_id] = threading.Lock()

    # Launch daemon thread
    thread = threading.Thread(
        target=_transcode_worker,
        args=(job_id, video_jobs),
        daemon=True,
        name=f"Transcode-{job_id[:8]}"
    )
    thread.start()

    logger.info(f"Background transcode thread started for job {job_id} (thread: {thread.name})")
    return True


def _cloud_transcode(
    input_path: str,
    output_path: str,
    job_id: str,
    progress_callback,
    max_width: int = 1920,
    max_height: int = 1080
) -> bool:
    """
    Cloud-based video transcoding using Replicate + Cloudinary.

    Workflow:
    1. Upload video to Cloudinary (temporary public URL)
    2. Submit to Replicate for H.264 transcoding
    3. Download result to output_path
    4. Cleanup Cloudinary file

    Args:
        input_path: Local path to input video
        output_path: Local path for output proxy video
        job_id: Video job ID for logging
        progress_callback: Callback function(progress: float)
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels

    Returns:
        True if successful, False otherwise
    """
    import requests
    from services.replicate_video_client import ReplicateVideoClient


    try:
        # Step 1: Upload to Cloudinary (20% progress)
        logger.info(f"[Cloud Transcode] Uploading video to Cloudinary: {input_path}")
        progress_callback(0.1)

        uploader = CloudinaryUploader()
        # Cloudinary public_id format: "easyedit-videos/video_{job_id}"

        progress_callback(0.2)

        # Step 2: Submit to Replicate for transcoding (20% → 80% progress)
        logger.info(f"[Cloud Transcode] Submitting to Replicate for H.264 transcode")
        progress_callback(0.3)

        replicate_client = ReplicateVideoClient()
        transcoded_url = replicate_client.transcode_to_h264(
            max_width=max_width,
            max_height=max_height,
            quality="medium",
            output_format="mp4"
        )

        logger.info(f"[Cloud Transcode] Replicate transcode complete: {transcoded_url}")
        progress_callback(0.8)

        # Step 3: Download result to output_path (80% → 95% progress)
        logger.info(f"[Cloud Transcode] Downloading result from Replicate")

        response = requests.get(transcoded_url, stream=True, timeout=300)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"[Cloud Transcode] Downloaded to: {output_path}")
        progress_callback(0.95)

        # Step 4: Cleanup Cloudinary (95% → 100% progress)
        logger.info(f"[Cloud Transcode] Cleaning up Cloudinary file")
        try:
            logger.info(f"[Cloud Transcode] Cloudinary cleanup successful")
        except Exception as e:
            logger.warning(f"[Cloud Transcode] Cloudinary cleanup failed (non-critical): {e}")

        progress_callback(1.0)
        logger.info(f"[Cloud Transcode] [SUCCESS] - Cloud transcode complete")
        return True

    except Exception as e:
        logger.error(f"[Cloud Transcode] [FAILED] - {str(e)}", exc_info=True)

        # Cleanup Cloudinary on error
        try:
            uploader = CloudinaryUploader()
            logger.info(f"[Cloud Transcode] Cloudinary cleanup after error successful")
        except Exception as cleanup_error:
            logger.warning(f"[Cloud Transcode] Cloudinary cleanup after error failed: {cleanup_error}")

        return False


def _transcode_worker(job_id: str, video_jobs: dict) -> None:
    """
    Worker function that runs in a background thread to transcode a video.

    This function:
    1. Loads the VideoJob from video_jobs
    2. Updates job status to 'transcoding'
    3. Calls the transcoder with a progress callback
    4. Updates VideoJob with progress in real-time
    5. Sets proxy_path and proxy_size on success
    6. Sets error message on failure
    7. Updates timestamps and final status

    All VideoJob updates are thread-safe using per-job locks.

    Args:
        job_id: ID of the video job to transcode
        video_jobs: Reference to the global video_jobs dictionary
    """
    from models import VideoJob, VideoJobStatus
    from services.video_transcoder import transcode_video
    from config import Config
    import os

    logger.info(f"[Transcode Worker] Starting transcode for job {job_id}")

    try:
        # Get job-specific lock
        with _job_locks_lock:
            job_lock = _job_locks.get(job_id)

        if not job_lock:
            logger.error(f"[Transcode Worker] No lock found for job {job_id}")
            return

        # Check processing mode - Replicate-only or Hybrid
        logger.info(f"[DEBUG] Checking processing mode for job {job_id}")
        from services.replicate_video_processor import ReplicateVideoProcessor
        replicate_processor = ReplicateVideoProcessor()
        logger.info(f"[DEBUG] MediaConvert available: {replicate_processor.mediaconvert_available}")

        if not replicate_processor.mediaconvert_available:
            logger.info(f"[Replicate-Only Mode] Skipping transcode for job {job_id}")

            # Update status to PROCESSING
            with job_lock:
                video_job = video_jobs[job_id]
                video_job.start_cloud_processing()

            # Jump directly to analysis (skip transcoding + waveform)
            _run_analysis(job_id, video_jobs, job_lock)
            return

        # If MediaConvert is available, continue with existing transcoding flow below...
        # Load VideoJob (thread-safe read)
        with job_lock:
            if job_id not in video_jobs:
                logger.error(f"[Transcode Worker] Job {job_id} not found in video_jobs")
                return

            video_job = video_jobs[job_id]
            original_path = video_job.original_path
            original_filename = video_job.original_filename

            # Validate original file exists
            if not os.path.exists(original_path):
                logger.error(f"[Transcode Worker] Original file not found: {original_path}")
                video_job.fail_transcoding(f"Original file not found: {original_path}")
                return

            # Generate proxy output path
            # Format: <job_id>_proxy_<original_filename>
            proxy_filename = f"{job_id}_proxy_{original_filename}"
            proxy_path = os.path.join(Config.VIDEO_PROXY_DIR, proxy_filename)

            logger.info(f"[Transcode Worker] Input: {original_path}")
            logger.info(f"[Transcode Worker] Output: {proxy_path}")

            # Mark transcoding as started
            video_job.start_transcoding()

        # Define progress callback (thread-safe)
        def progress_callback(progress: float) -> None:
            """Update job progress in thread-safe manner"""
            try:
                with job_lock:
                    if job_id in video_jobs:
                        video_jobs[job_id].update_transcode_progress(progress)

                        # Log progress at 25% intervals
                        percent = int(progress * 100)
                        if percent % 25 == 0:
                            logger.info(f"[Transcode Worker] Job {job_id} progress: {percent}%")

            except Exception as e:
                logger.error(f"[Transcode Worker] Error updating progress: {str(e)}")

        # Route to cloud or local transcoding based on config
        if Config.USE_CLOUD_VIDEO_PROCESSING:
            # CLOUD TRANSCODING PATHWAY
            logger.info(f"[Transcode Worker] Starting CLOUD transcode for job {job_id}")
            logger.info(f"[Transcode Worker] Settings: quality=medium, max_res={Config.VIDEO_PROXY_MAX_WIDTH}x{Config.VIDEO_PROXY_MAX_HEIGHT}")

            success = _cloud_transcode(
                input_path=original_path,
                output_path=proxy_path,
                job_id=job_id,
                progress_callback=progress_callback,
                max_width=Config.VIDEO_PROXY_MAX_WIDTH,
                max_height=Config.VIDEO_PROXY_MAX_HEIGHT
            )
        else:
            # LOCAL FFmpeg TRANSCODING PATHWAY
            logger.info(f"[Transcode Worker] Starting LOCAL FFmpeg transcode for job {job_id}")
            logger.info(f"[Transcode Worker] Settings: CRF={Config.VIDEO_TRANSCODE_CRF}, "
                       f"preset={Config.VIDEO_TRANSCODE_PRESET}, "
                       f"max_res={Config.VIDEO_PROXY_MAX_WIDTH}x{Config.VIDEO_PROXY_MAX_HEIGHT}")

            success = transcode_video(
                input_path=original_path,
                output_path=proxy_path,
                progress_callback=progress_callback,
                crf=Config.VIDEO_TRANSCODE_CRF,
                preset=Config.VIDEO_TRANSCODE_PRESET,
                max_width=Config.VIDEO_PROXY_MAX_WIDTH,
                max_height=Config.VIDEO_PROXY_MAX_HEIGHT,
                audio_bitrate=Config.VIDEO_PROXY_AUDIO_BITRATE
            )

        # Handle result (thread-safe)
        with job_lock:
            if job_id not in video_jobs:
                logger.error(f"[Transcode Worker] Job {job_id} disappeared during transcoding")
                return

            video_job = video_jobs[job_id]

            if success:
                # Verify output file exists and get size
                if os.path.exists(proxy_path):
                    proxy_size = os.path.getsize(proxy_path)
                    proxy_url = f"/video-proxy/{job_id}"

                    # Mark transcoding as complete
                    video_job.complete_transcoding(
                        proxy_path=proxy_path,
                        proxy_size_bytes=proxy_size,
                        proxy_url=proxy_url
                    )

                    logger.info(f"[Transcode Worker] [SUCCESS] - Job {job_id} completed")
                    logger.info(f"[Transcode Worker] Proxy file: {proxy_path} ({proxy_size} bytes)")

                    # Phase 2.2.1: Generate waveform after proxy is ready
                    try:
                        from services.waveform_generator import generate_waveform

                        logger.info(f"[Waveform Generator] Starting waveform generation for job {job_id}")
                        video_job.mark_waveform_generating()

                        # Generate waveform from proxy video
                        waveform_data = generate_waveform(
                            video_path=proxy_path,
                            job_id=job_id,
                            samples=video_job.waveform_samples
                        )

                        # Mark waveform as ready
                        video_job.mark_waveform_ready(
                            waveform_file=waveform_data.to_dict().get('created_at', ''),
                            duration=waveform_data.duration
                        )

                        logger.info(
                            f"[Waveform Generator] [SUCCESS] - Job {job_id} waveform generated: "
                            f"{waveform_data.samples} samples, {waveform_data.duration:.2f}s"
                        )

                    except ValueError as e:
                        # Video has no audio stream - not a critical error
                        error_msg = f"No audio stream: {str(e)}"
                        video_job.mark_waveform_failed(error_msg)
                        logger.warning(f"[Waveform Generator] ⚠️ WARNING - Job {job_id}: {error_msg}")

                    except Exception as e:
                        # Waveform generation failed, but don't fail the entire job
                        error_msg = f"Waveform generation error: {str(e)}"
                        video_job.mark_waveform_failed(error_msg)
                        logger.error(f"[Waveform Generator] [FAILED] - Job {job_id}: {error_msg}", exc_info=True)

                    # Phase 2: Trigger analysis after transcode + waveform complete
                    logger.info(f"[Transcode Worker] Transcode complete, starting analysis for job {job_id}")
                    _run_analysis(job_id, video_jobs, job_lock)

                else:
                    # Transcode claimed success but file missing
                    error_msg = "Transcode completed but output file not found"
                    video_job.fail_transcoding(error_msg)
                    logger.error(f"[Transcode Worker] [FAILED] - {error_msg}")

            else:
                # Transcode failed
                error_msg = "FFmpeg transcoding failed (see logs for details)"
                video_job.fail_transcoding(error_msg)
                logger.error(f"[Transcode Worker] [FAILED] - Job {job_id}: {error_msg}")

                # Cleanup partial output file if it exists
                if os.path.exists(proxy_path):
                    try:
                        os.remove(proxy_path)
                        logger.info(f"[Transcode Worker] Cleaned up partial output: {proxy_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"[Transcode Worker] Could not cleanup partial file: {cleanup_error}")

    except Exception as e:
        logger.error(f"[Transcode Worker] [EXCEPTION] - Job {job_id}: {str(e)}", exc_info=True)

        # Mark job as failed (thread-safe)
        try:
            with job_lock:
                if job_id in video_jobs:
                    error_msg = f"Unexpected error during transcoding: {str(e)}"
                    video_jobs[job_id].fail_transcoding(error_msg)
        except Exception as update_error:
            logger.error(f"[Transcode Worker] Could not update job status after exception: {update_error}")

    finally:
        # Remove from active jobs (thread-safe)
        with _active_jobs_lock:
            if job_id in _active_jobs:
                _active_jobs.remove(job_id)
                logger.info(f"[Transcode Worker] Job {job_id} removed from active jobs")

        # Cleanup job lock
        with _job_locks_lock:
            if job_id in _job_locks:
                del _job_locks[job_id]


def _run_analysis(job_id: str, video_jobs: dict, job_lock: threading.Lock) -> None:
    """
    Run analysis after transcode completes (Phase 2: Cloud Result Loop).

    This function:
    1. Extracts audio from proxy video
    2. Transcribes with Replicate Whisper
    3. Runs repeated take detector
    4. Stores results in VideoJob

    Args:
        job_id: ID of the video job to analyze
        video_jobs: Reference to the global video_jobs dictionary
        job_lock: Thread lock for this specific job
    """
    logger.info(f"[Analysis Worker] Starting analysis for job {job_id}")

    try:
        # Load VideoJob and mark analysis started
        with job_lock:
            if job_id not in video_jobs:
                logger.error(f"[Analysis Worker] Job {job_id} not found in video_jobs")
                return

            video_job = video_jobs[job_id]
            proxy_path = video_job.proxy_path
            original_s3_url = video_job.original_path  # S3 URL stored during upload

            # Mark analysis started
            video_job.start_analysis()
            logger.info(f"[Analysis Worker] Status updated to ANALYZING for job {job_id}")

        # Step 1: Extract audio from video
        logger.info(f"[Analysis Worker] Step 1/3: Extracting audio")
        audio_filename = f"{job_id}_analysis_audio.wav"
        audio_path = os.path.join(Config.TEMP_FOLDER, audio_filename)

        # Check if we have a transcoded proxy (hybrid mode) or use S3 original (Replicate-only)
        if proxy_path and os.path.exists(proxy_path):
            # Hybrid mode: Extract from local proxy
            logger.info(f"[Analysis Worker] Extracting audio from proxy: {proxy_path}")
            extractor = VideoAudioExtractor()
            audio_result = extractor.extract_audio(proxy_path, audio_path)

            if not audio_result.get('success'):
                error_msg = f"Audio extraction failed: {audio_result.get('message', 'Unknown error')}"
                logger.error(f"[Analysis Worker] {error_msg}")
                with job_lock:
                    video_jobs[job_id].fail_analysis(error_msg)
                return
        else:
            # Replicate-only mode: Extract from S3 original via Replicate
            logger.info(f"[Analysis Worker] Extracting audio from S3 via Replicate")

            try:
                # Generate presigned URL for S3 video access (inline to avoid caching issues)
                import boto3
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
                    region_name=Config.AWS_REGION,
                    endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
                )
                s3_key = f"uploads/{job_id}/{video_job.filename}"
                video_presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': Config.S3_VIDEO_BUCKET, 'Key': s3_key},
                    ExpiresIn=86400
                )
                logger.info(f"[Analysis Worker] Generated presigned URL for {s3_key}")

                # Extract audio via Replicate
                from services.replicate_video_processor import ReplicateVideoProcessor
                replicate_processor = ReplicateVideoProcessor()
                audio_extraction = replicate_processor.extract_audio(
                    video_url=video_presigned_url,
                    output_format="wav",
                    audio_quality="high"
                )

                audio_url = audio_extraction['audio_url']
                logger.info(f"[Analysis Worker] Replicate audio extraction complete: {audio_url}")

                # Download audio to local temp file
                import requests
                response = requests.get(audio_url, stream=True, timeout=300)
                response.raise_for_status()

                with open(audio_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                logger.info(f"[Analysis Worker] Audio downloaded: {audio_path}")

            except Exception as e:
                error_msg = f"Replicate audio extraction failed: {str(e)}"
                logger.error(f"[Analysis Worker] {error_msg}", exc_info=True)
                with job_lock:
                    video_jobs[job_id].fail_analysis(error_msg)
                return

        logger.info(f"[Analysis Worker] Audio extracted: {audio_path}")

        # Step 2: Transcribe with Replicate Whisper
        logger.info(f"[Analysis Worker] Step 2/3: Transcribing audio with Replicate Whisper")

        try:
            whisper_client = ReplicateWhisperClient()
            transcription_result = whisper_client.transcribe_audio(
                audio_path,
                enable_speaker_diarization=True
            )
            logger.info(f"[Analysis Worker] Transcription complete: {transcription_result.get('word_count', 0)} words")
        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            logger.error(f"[Analysis Worker] {error_msg}", exc_info=True)
            with job_lock:
                video_jobs[job_id].fail_analysis(error_msg)
            return

        # Step 3: Detect repeated takes
        logger.info(f"[Analysis Worker] Step 3/3: Running repeated take detection")
        detector = RepeatedTakeDetector()

        with job_lock:
            video_job = video_jobs[job_id]
            video_info = {
                'duration': video_job.duration_seconds,
                'width': video_job.width,
                'height': video_job.height
            }

        analysis_result = detector.detect_repeated_takes(
            transcription_result,
            video_info
        )

        logger.info(f"[Analysis Worker] Detection complete: {analysis_result['stats']['total_segments']} segments analyzed")

        # Step 4: Store results in VideoJob
        with job_lock:
            if job_id not in video_jobs:
                logger.error(f"[Analysis Worker] Job {job_id} disappeared during analysis")
                return

            video_jobs[job_id].complete_analysis(transcription_result, analysis_result)
            logger.info(f"[Analysis Worker] [SUCCESS] - Analysis complete for job {job_id}")

        # Step 4: Generate DaVinci Resolve XML
        logger.info(f"[XML Generator] Generating timeline XML for job {job_id}")

        try:
            # Create timeline from transcription
            timeline = _create_timeline_from_transcription(
                transcription_result=transcription_result,
                video_job=video_job
            )

            # Generate XML
            from parsers.xml_writer import FCP7XMLWriter
            xml_writer = FCP7XMLWriter()
            xml_content = xml_writer.generate_fcp7_xml(timeline)

            # Upload XML to S3
            from services.s3_upload_manager import S3UploadManager
            s3_manager = S3UploadManager()
            xml_s3_key = f"xml/{job_id}/timeline.xml"

            s3_manager.s3_client.put_object(
                Bucket=Config.S3_VIDEO_BUCKET,
                Key=xml_s3_key,
                Body=xml_content.encode('utf-8'),
                ContentType='application/xml',
                Metadata={
                    'job_id': job_id,
                    'generated_at': datetime.now().isoformat()
                }
            )

            # Store XML S3 key in VideoJob metadata
            with job_lock:
                if not hasattr(video_jobs[job_id], 'metadata') or video_jobs[job_id].metadata is None:
                    video_jobs[job_id].metadata = {}
                video_jobs[job_id].metadata['xml_s3_key'] = xml_s3_key
                video_jobs[job_id].metadata['xml_url'] = f"s3://{Config.S3_VIDEO_BUCKET}/{xml_s3_key}"

            logger.info(f"[XML Generator] XML stored: {xml_s3_key}")

        except Exception as e:
            # Don't fail the entire job if XML generation fails
            logger.error(f"[XML Generator] XML generation failed: {e}", exc_info=True)
            with job_lock:
                if not hasattr(video_jobs[job_id], 'metadata') or video_jobs[job_id].metadata is None:
                    video_jobs[job_id].metadata = {}
                video_jobs[job_id].metadata['xml_error'] = str(e)
            logger.warning(f"[XML Generator] Continuing without XML (analysis still complete)")

        # Cleanup audio file
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"[Analysis Worker] Cleaned up audio file: {audio_path}")
        except Exception as cleanup_error:
            logger.warning(f"[Analysis Worker] Could not cleanup audio file: {cleanup_error}")

    except Exception as e:
        logger.error(f"[Analysis Worker] [EXCEPTION] - Job {job_id}: {str(e)}", exc_info=True)

        # Mark job as failed (thread-safe)
        try:
            with job_lock:
                if job_id in video_jobs:
                    error_msg = f"Analysis failed: {str(e)}"
                    video_jobs[job_id].fail_analysis(error_msg)
        except Exception as update_error:
            logger.error(f"[Analysis Worker] Could not update job status after exception: {update_error}")

        logger.info(f"[Transcode Worker] Thread completed for job {job_id}")


def get_active_transcode_jobs() -> Set[str]:
    """
    Get the set of currently active transcoding job IDs.

    This is useful for monitoring and debugging purposes.

    Returns:
        Set of job IDs currently being transcoded

    Example:
        >>> active = get_active_transcode_jobs()
        >>> print(f"Currently transcoding {len(active)} jobs")
    """
    with _active_jobs_lock:
        return _active_jobs.copy()


def is_job_transcoding(job_id: str) -> bool:
    """
    Check if a specific job is currently being transcoded.

    Args:
        job_id: ID of the job to check

    Returns:
        True if job is currently transcoding, False otherwise

    Example:
        >>> if is_job_transcoding("abc-123"):
        ...     print("Job is being processed")
    """
    with _active_jobs_lock:
        return job_id in _active_jobs


def get_transcode_stats() -> dict:
    """
    Get statistics about transcoding operations.

    Returns:
        Dictionary with transcoding statistics

    Example:
        >>> stats = get_transcode_stats()
        >>> print(f"Active jobs: {stats['active_count']}")
    """
    with _active_jobs_lock:
        active_count = len(_active_jobs)
        active_list = list(_active_jobs)

    with _job_locks_lock:
        locks_count = len(_job_locks)

    return {
        'active_count': active_count,
        'active_jobs': active_list,
        'job_locks_count': locks_count
    }


def _create_timeline_from_transcription(
    transcription_result: Dict,
    video_job: 'VideoJob'
) -> 'Timeline':
    """
    Create a Timeline object from Whisper transcription segments.

    For MVP: Single video track with one clip per transcription segment.
    Future enhancement: Multi-layer with talking head/demo/abstract segments.

    Args:
        transcription_result: Output from Whisper client
        video_job: VideoJob with metadata

    Returns:
        Timeline object ready for XML generation
    """
    from models.timeline import Timeline, Track, Clip

    timeline = Timeline(
        name=f"Timeline_{video_job.job_id}",
        frame_rate=video_job.fps or 30.0,
        sample_rate=48000
    )

    # Create video track
    video_track = Track(
        index=1,
        name="Video 1",
        track_type='video'
    )

    # Add one clip per transcription segment
    segments = transcription_result.get('segments', [])
    for i, segment in enumerate(segments):
        clip = Clip(
            name=f"Segment_{i+1}_{segment.get('speaker', 'SPEAKER_00')}",
            start_time=segment['start'],
            end_time=segment['end'],
            duration=segment['end'] - segment['start'],
            track_index=1,
            media_start=segment['start'],
            media_end=segment['end'],
            metadata={
                'text': segment.get('text', ''),
                'speaker': segment.get('speaker', 'SPEAKER_00'),
                'confidence': segment.get('confidence', 0.0)
            }
        )
        video_track.add_clip(clip)

    timeline.add_track(video_track)
    timeline.calculate_duration()

    # Set canonical file block (reference to S3 original)
    timeline.set_canonical_file_block({
        'file_id': 'file-1',
        'name': video_job.original_filename or 'video.mp4',
        'pathurl': video_job.original_path  # S3 URL
    })

    return timeline
