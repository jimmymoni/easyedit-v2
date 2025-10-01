"""
Audio processing background tasks
"""

from celery import current_task
from celery_app import celery_app
from config import Config
from parsers.drt_parser import DRTParser
from parsers.drt_writer import DRTWriter
try:
    from services.audio_analyzer import AudioAnalyzer
except ImportError:
    # Fallback to simple audio analyzer if librosa dependencies not available
    from services.simple_audio_analyzer import SimpleAudioAnalyzer as AudioAnalyzer
from services.edit_rules import EditRulesEngine
from services.soniox_client import SonioxClient
from utils.error_handlers import ProcessingError, ValidationError
import logging
import os
import time

logger = logging.getLogger(__name__)

def broadcast_progress(job_id: str, progress: int, message: str):
    """Helper function to broadcast progress updates via WebSocket"""
    try:
        from websocket_manager import websocket_manager
        websocket_manager.broadcast_job_progress(job_id, progress, message)
    except Exception as e:
        logger.warning(f"Failed to broadcast WebSocket update: {str(e)}")

def broadcast_completion(job_id: str, result: dict):
    """Helper function to broadcast completion via WebSocket"""
    try:
        from websocket_manager import websocket_manager
        websocket_manager.broadcast_job_completed(job_id, result)
    except Exception as e:
        logger.warning(f"Failed to broadcast WebSocket completion: {str(e)}")

def broadcast_failure(job_id: str, error: str, error_type: str = None):
    """Helper function to broadcast failure via WebSocket"""
    try:
        from websocket_manager import websocket_manager
        websocket_manager.broadcast_job_failed(job_id, error, error_type)
    except Exception as e:
        logger.warning(f"Failed to broadcast WebSocket failure: {str(e)}")

@celery_app.task(bind=True, queue='audio', priority=7)
def process_timeline_task(self, job_id: str, audio_file_path: str, drt_file_path: str, options: dict):
    """
    Background task for processing timeline with audio analysis and editing
    """
    try:
        # Update task progress and broadcast
        progress_message = 'Starting timeline processing'
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': progress_message, 'job_id': job_id}
        )
        broadcast_progress(job_id, 10, progress_message)

        # Validate inputs
        if not os.path.exists(audio_file_path):
            raise ValidationError(f"Audio file not found: {audio_file_path}")

        if not os.path.exists(drt_file_path):
            raise ValidationError(f"DRT file not found: {drt_file_path}")

        # Parse DRT file
        progress_message = 'Parsing timeline file'
        self.update_state(
            state='PROGRESS',
            meta={'progress': 20, 'message': progress_message, 'job_id': job_id}
        )
        broadcast_progress(job_id, 20, progress_message)

        drt_parser = DRTParser()
        timeline = drt_parser.parse_file(drt_file_path)

        # Load and analyze audio with context manager for guaranteed cleanup
        self.update_state(
            state='PROGRESS',
            meta={'progress': 30, 'message': 'Analyzing audio', 'job_id': job_id}
        )

        # SECURITY: Use context manager for guaranteed cleanup
        with AudioAnalyzer() as audio_analyzer:
            if not audio_analyzer.load_audio(audio_file_path):
                raise ProcessingError("Failed to load audio file")

            # Get processing options
            enable_transcription = options.get('enable_transcription', True)
            enable_speaker_diarization = options.get('enable_speaker_diarization', True)
            remove_silence = options.get('remove_silence', True)

            # Analyze audio features
            self.update_state(
                state='PROGRESS',
                meta={'progress': 40, 'message': 'Extracting audio features', 'job_id': job_id}
            )

            audio_analysis = {
                'silence_segments': audio_analyzer.detect_silence() if remove_silence else [],
                'speech_segments': audio_analyzer.detect_speech_segments(),
                'cut_points': audio_analyzer.find_optimal_cut_points(),
                'features': audio_analyzer.analyze_audio_features()
            }
        # Automatic cleanup of audio data and temp files

        # Transcription (if enabled and API key available)
        transcription_data = None
        if enable_transcription and Config.SONIOX_API_KEY:
            self.update_state(
                state='PROGRESS',
                meta={'progress': 60, 'message': 'Transcribing audio', 'job_id': job_id}
            )

            try:
                soniox_client = SonioxClient()
                transcription_data = soniox_client.transcribe_audio(
                    audio_file_path,
                    enable_speaker_diarization
                )
            except Exception as e:
                logger.warning(f"Transcription failed for job {job_id}: {str(e)}")
                # Continue without transcription

        # Apply editing rules
        self.update_state(
            state='PROGRESS',
            meta={'progress': 75, 'message': 'Applying editing rules', 'job_id': job_id}
        )

        edit_engine = EditRulesEngine()
        edited_timeline = edit_engine.apply_editing_rules(
            timeline,
            transcription_data,
            audio_analysis
        )

        # Generate output file
        self.update_state(
            state='PROGRESS',
            meta={'progress': 90, 'message': 'Generating output file', 'job_id': job_id}
        )

        output_filename = f"{job_id}_edited_timeline.drt"
        output_path = os.path.join(Config.TEMP_FOLDER, output_filename)

        drt_writer = DRTWriter()
        success = drt_writer.write_timeline(edited_timeline, output_path)

        if not success:
            raise ProcessingError("Failed to write output timeline file")

        # Generate statistics
        stats = edit_engine.get_editing_stats(timeline, edited_timeline)

        # Complete successfully
        result = {
            'job_id': job_id,
            'status': 'completed',
            'output_file': output_path,
            'stats': stats,
            'transcription_available': transcription_data is not None,
            'audio_analysis': {
                'duration': audio_analysis['features'].get('duration', 0),
                'silence_segments_count': len(audio_analysis['silence_segments']),
                'speech_segments_count': len(audio_analysis['speech_segments']),
                'cut_points_count': len(audio_analysis['cut_points'])
            },
            'processing_time': time.time() - self.request.started,
            'message': 'Timeline processed successfully'
        }

        # Broadcast completion
        broadcast_completion(job_id, result)

        logger.info(f"Timeline processing completed for job {job_id}")
        return result

    except (ValidationError, ProcessingError) as e:
        error_message = str(e)
        error_type = type(e).__name__

        logger.error(f"Processing error for job {job_id}: {error_message}")

        self.update_state(
            state='FAILURE',
            meta={'progress': 100, 'error': error_message, 'job_id': job_id, 'error_type': error_type}
        )

        # Broadcast failure
        broadcast_failure(job_id, error_message, error_type)
        raise

    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        error_type = 'UnexpectedError'

        logger.exception(f"Unexpected error processing job {job_id}")

        self.update_state(
            state='FAILURE',
            meta={'progress': 100, 'error': error_message, 'job_id': job_id, 'error_type': error_type}
        )

        # Broadcast failure
        broadcast_failure(job_id, error_message, error_type)
        raise

@celery_app.task(bind=True, queue='audio', priority=5)
def analyze_audio_task(self, audio_file_path: str, analysis_options: dict):
    """
    Background task for audio analysis only (without timeline processing)
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Loading audio file'}
        )

        # SECURITY: Use context manager for guaranteed cleanup
        with AudioAnalyzer() as audio_analyzer:
            # Load audio
            if not audio_analyzer.load_audio(audio_file_path):
                raise ProcessingError("Failed to load audio file")

            self.update_state(
                state='PROGRESS',
                meta={'progress': 50, 'message': 'Analyzing audio features'}
            )

            # Perform analysis
            analysis_result = {
                'basic_features': audio_analyzer.analyze_audio_features(),
                'summary': audio_analyzer.get_audio_summary()
            }

            # Optional detailed analysis
            if analysis_options.get('detect_silence', True):
                analysis_result['silence_segments'] = audio_analyzer.detect_silence()

            if analysis_options.get('detect_speech', True):
                analysis_result['speech_segments'] = audio_analyzer.detect_speech_segments()

            if analysis_options.get('find_cut_points', True):
                analysis_result['cut_points'] = audio_analyzer.find_optimal_cut_points()

            self.update_state(
                state='PROGRESS',
                meta={'progress': 100, 'message': 'Analysis complete'}
            )

            return {
                'status': 'completed',
                'analysis': analysis_result,
                'file_path': audio_file_path
            }
        # Automatic cleanup of audio data and temp files

    except Exception as e:
        logger.exception(f"Audio analysis failed for {audio_file_path}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'file_path': audio_file_path}
        )
        raise

@celery_app.task(bind=True, queue='audio', priority=3)
def transcribe_audio_task(self, audio_file_path: str, options: dict):
    """
    Background task for audio transcription
    """
    try:
        if not Config.SONIOX_API_KEY:
            raise ProcessingError("Soniox API key not configured")

        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Starting transcription'}
        )

        soniox_client = SonioxClient()
        transcription_data = soniox_client.transcribe_audio(
            audio_file_path,
            options.get('enable_speaker_diarization', False)
        )

        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Transcription complete'}
        )

        return {
            'status': 'completed',
            'transcription': transcription_data,
            'file_path': audio_file_path
        }

    except Exception as e:
        logger.exception(f"Transcription failed for {audio_file_path}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'file_path': audio_file_path}
        )
        raise