"""
Background upload processing with WebSocket notifications

Handles asynchronous file validation and saving with real-time status updates
via WebSocket to provide instant HTTP 202 responses.
"""

import os
import io
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from werkzeug.datastructures import FileStorage

from config import Config
from utils.error_handlers import validate_file_upload, ValidationError, ProcessingError
from websocket_manager import websocket_manager
from job_manager import job_manager

logger = logging.getLogger(__name__)


def process_upload_background(
    job_id: str,
    audio_file: FileStorage,
    drt_file: FileStorage,
    audio_path: str,
    drt_path: str
) -> None:
    """
    Process file upload in background thread with status updates.

    Workflow:
    1. Update status to 'validating'
    2. Run security validation on both files
    3. Update status to 'saving'
    4. Save files in parallel
    5. Update status to 'ready'

    On error:
    - ValidationError: Clean up files, mark as 'validation_failed'
    - Exception: Clean up files, mark as 'failed'

    Args:
        job_id: Unique job identifier
        audio_file: Audio file object from Flask request
        drt_file: DRT file object from Flask request
        audio_path: Target path for audio file
        drt_path: Target path for DRT file
    """
    try:
        # Phase 1: Validation
        _update_job_status(job_id, 'validating', 15, 'Validating uploaded files...')

        logger.info(f"Starting validation for job {job_id}")

        # Validate audio file (security checks: size, extension, magic numbers)
        try:
            validate_file_upload(
                audio_file,
                Config.ALLOWED_AUDIO_EXTENSIONS,
                Config.MAX_FILE_SIZE_MB
            )
        except ValidationError as e:
            raise ValidationError(f"Audio file validation failed: {str(e)}")

        # Validate DRT file
        try:
            validate_file_upload(
                drt_file,
                Config.ALLOWED_DRT_EXTENSIONS,
                Config.MAX_FILE_SIZE_MB
            )
        except ValidationError as e:
            raise ValidationError(f"DRT file validation failed: {str(e)}")

        logger.info(f"Validation passed for job {job_id}")

        # Phase 2: Parallel file saves
        _update_job_status(job_id, 'saving', 50, 'Saving files to disk...')

        logger.info(f"Starting parallel file saves for job {job_id}")

        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both saves concurrently
            audio_future = executor.submit(_save_file_safely, audio_file, audio_path, 'audio')
            drt_future = executor.submit(_save_file_safely, drt_file, drt_path, 'drt')

            # Wait for both with timeout
            audio_result = audio_future.result(timeout=60)
            drt_result = drt_future.result(timeout=60)

            # Check for save errors
            if not audio_result:
                raise ProcessingError("Failed to save audio file")
            if not drt_result:
                raise ProcessingError("Failed to save DRT file")

        logger.info(f"Files saved successfully for job {job_id}")

        # Phase 3: Mark as ready
        _update_job_status(
            job_id,
            'ready',
            100,
            'Upload complete - ready for processing'
        )

        logger.info(f"Background upload completed for job {job_id}")

    except ValidationError as e:
        # Validation failed - clean up and notify
        logger.warning(f"Validation failed for job {job_id}: {str(e)}")
        _handle_validation_failure(job_id, str(e), audio_path, drt_path)

    except Exception as e:
        # Unexpected error - clean up and notify
        logger.error(f"Unexpected error in background upload for job {job_id}: {str(e)}")
        _handle_save_failure(job_id, str(e), audio_path, drt_path)


def _save_file_safely(file: FileStorage, path: str, file_type: str) -> bool:
    """
    Save file with error handling and logging.

    Args:
        file: File object to save
        path: Target filesystem path
        file_type: Human-readable file type for logging

    Returns:
        True if save succeeded, False otherwise
    """
    try:
        file.save(path)
        logger.debug(f"{file_type.capitalize()} file saved to {path}")
        return True
    except Exception as e:
        logger.error(f"Error saving {file_type} file to {path}: {str(e)}")
        return False


def _update_job_status(job_id: str, status: str, progress: int, message: str) -> None:
    """
    Update job status in persistent storage and broadcast via WebSocket.

    Thread-safe operation that updates both the job_manager and sends
    WebSocket notification to all subscribed clients.

    Args:
        job_id: Job identifier
        status: New status value
        progress: Progress percentage (0-100)
        message: Human-readable status message
    """
    # Update persistent job storage (thread-safe with lock)
    job_manager.update_job_status(job_id, {
        'status': status,
        'progress': progress,
        'message': message
    })

    # Broadcast to WebSocket subscribers
    websocket_manager.broadcast_job_update(job_id, {
        'status': status,
        'progress': progress,
        'message': message
    })

    logger.debug(f"Job {job_id} status updated: {status} ({progress}%) - {message}")


def _handle_validation_failure(
    job_id: str,
    error_msg: str,
    audio_path: str,
    drt_path: str
) -> None:
    """
    Handle validation failure by cleaning up files and notifying frontend.

    Args:
        job_id: Job identifier
        error_msg: Validation error message
        audio_path: Path to audio file (may not exist yet)
        drt_path: Path to DRT file (may not exist yet)
    """
    # Clean up any files that were created
    for path in [audio_path, drt_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Cleaned up file: {path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up {path}: {str(cleanup_error)}")

    # Update status with validation failure
    _update_job_status(
        job_id,
        'validation_failed',
        0,
        f'Validation failed: {error_msg}'
    )

    # Also broadcast failure event
    websocket_manager.broadcast_job_failed(
        job_id,
        error_msg,
        error_type='ValidationError'
    )


def _handle_save_failure(
    job_id: str,
    error_msg: str,
    audio_path: str,
    drt_path: str
) -> None:
    """
    Handle save failure by cleaning up files and notifying frontend.

    Args:
        job_id: Job identifier
        error_msg: Save error message
        audio_path: Path to audio file
        drt_path: Path to DRT file
    """
    # Clean up any partially saved files
    for path in [audio_path, drt_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Cleaned up file after save failure: {path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up {path}: {str(cleanup_error)}")

    # Update status with failure
    _update_job_status(
        job_id,
        'failed',
        0,
        f'Upload failed: {error_msg}'
    )

    # Also broadcast failure event
    websocket_manager.broadcast_job_failed(
        job_id,
        error_msg,
        error_type='ProcessingError'
    )

def process_upload_background_from_data(
    job_id: str,
    audio_data: bytes,
    drt_data: bytes,
    audio_path: str,
    drt_path: str,
    audio_filename: str,
    drt_filename: str
) -> None:
    """
    Process file upload in background thread from in-memory data.
    
    This version works with bytes objects instead of FileStorage to avoid
    request context issues with background threads.
    
    Args:
        job_id: Unique job identifier
        audio_data: Audio file bytes
        drt_data: DRT file bytes
        audio_path: Target path for audio file
        drt_path: Target path for DRT file
        audio_filename: Original audio filename
        drt_filename: Original DRT filename
    """
    try:
        # Phase 1: Validation
        _update_job_status(job_id, 'validating', 15, 'Validating uploaded files...')
        
        logger.info(f"Starting validation for job {job_id}")
        
        # Create mock FileStorage objects for validation
        audio_file = _create_file_storage(audio_data, audio_filename)
        drt_file = _create_file_storage(drt_data, drt_filename)
        
        # Validate audio file
        try:
            validate_file_upload(
                audio_file,
                Config.ALLOWED_AUDIO_EXTENSIONS,
                Config.MAX_FILE_SIZE_MB
            )
        except ValidationError as e:
            raise ValidationError(f"Audio file validation failed: {str(e)}")
        
        # Validate DRT file
        try:
            validate_file_upload(
                drt_file,
                Config.ALLOWED_DRT_EXTENSIONS,
                Config.MAX_FILE_SIZE_MB
            )
        except ValidationError as e:
            raise ValidationError(f"DRT file validation failed: {str(e)}")
        
        logger.info(f"Validation passed for job {job_id}")
        
        # Phase 2: Parallel file saves
        _update_job_status(job_id, 'saving', 50, 'Saving files to disk...')
        
        logger.info(f"Starting parallel file saves for job {job_id}")
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both saves concurrently
            audio_future = executor.submit(_save_bytes_to_file, audio_data, audio_path, 'audio')
            drt_future = executor.submit(_save_bytes_to_file, drt_data, drt_path, 'drt')
            
            # Wait for both with timeout
            audio_result = audio_future.result(timeout=60)
            drt_result = drt_future.result(timeout=60)
            
            # Check for save errors
            if not audio_result:
                raise ProcessingError("Failed to save audio file")
            if not drt_result:
                raise ProcessingError("Failed to save DRT file")
        
        logger.info(f"Files saved successfully for job {job_id}")
        
        # Phase 3: Mark as ready
        _update_job_status(
            job_id,
            'ready',
            100,
            'Upload complete - ready for processing'
        )
        
        logger.info(f"Background upload completed for job {job_id}")
    
    except ValidationError as e:
        # Validation failed - clean up and notify
        logger.warning(f"Validation failed for job {job_id}: {str(e)}")
        _handle_validation_failure(job_id, str(e), audio_path, drt_path)
    
    except Exception as e:
        # Unexpected error - clean up and notify
        logger.error(f"Unexpected error in background upload for job {job_id}: {str(e)}")
        _handle_save_failure(job_id, str(e), audio_path, drt_path)


def _create_file_storage(data: bytes, filename: str) -> FileStorage:
    """Create a FileStorage object from bytes data."""
    stream = io.BytesIO(data)
    return FileStorage(stream=stream, filename=filename, content_type='application/octet-stream')


def _save_bytes_to_file(data: bytes, path: str, file_type: str) -> bool:
    """
    Save bytes data to file with error handling.
    
    Args:
        data: File bytes to save
        path: Target filesystem path
        file_type: Human-readable file type for logging
    
    Returns:
        True if save succeeded, False otherwise
    """
    try:
        with open(path, 'wb') as f:
            f.write(data)
        logger.debug(f"{file_type.capitalize()} file saved to {path}")
        return True
    except Exception as e:
        logger.error(f"Error saving {file_type} file to {path}: {str(e)}")
        return False
