"""
Video file validation utilities for Phase 1 implementation.

This module provides comprehensive validation for video uploads including:
- File size validation
- Format and codec validation
- Video integrity checks
- Transcode time estimation
"""

import logging
import os
from typing import Tuple, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_video_file_size(file_size: int, max_size_mb: int = 3072) -> Tuple[bool, str]:
    """
    Validate video file size is within acceptable limits.

    Args:
        file_size: File size in bytes
        max_size_mb: Maximum allowed size in MB (default: 3072 MB = 3 GB)

    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if valid
        - (False, "error message") if invalid

    Example:
        >>> validate_video_file_size(2147483648, 3072)  # 2GB file
        (True, "")
        >>> validate_video_file_size(4294967296, 3072)  # 4GB file
        (False, "File size (4096 MB) exceeds maximum allowed size (3072 MB)")
    """
    # Check if file size is zero
    if file_size == 0:
        return False, "File is empty (0 bytes)"

    # Convert to MB for comparison
    file_size_mb = file_size / (1024 * 1024)
    max_size_bytes = max_size_mb * 1024 * 1024

    # Check against maximum
    if file_size > max_size_bytes:
        return False, f"File size ({file_size_mb:.1f} MB) exceeds maximum allowed size ({max_size_mb} MB)"

    # Check for suspiciously small files (less than 1KB)
    if file_size < 1024:
        return False, f"File is too small ({file_size} bytes) to be a valid video"

    logger.debug(f"File size validation passed: {file_size_mb:.1f} MB")
    return True, ""


def validate_video_format(filename: str, allowed_formats: list = None) -> Tuple[bool, str]:
    """
    Validate video file format based on file extension.

    Args:
        filename: Name of the video file
        allowed_formats: List of allowed extensions (default: ['mp4', 'mov', 'mxf', 'avi'])

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> validate_video_format("video.mp4")
        (True, "")
        >>> validate_video_format("video.txt")
        (False, "File format 'txt' is not supported. Allowed formats: mp4, mov, mxf, avi")
    """
    # Default allowed formats
    if allowed_formats is None:
        allowed_formats = ['mp4', 'mov', 'mxf', 'avi']

    # Normalize allowed formats to lowercase
    allowed_formats = [fmt.lower() for fmt in allowed_formats]

    # Extract file extension
    if '.' not in filename:
        return False, "File must have a valid extension"

    extension = filename.rsplit('.', 1)[1].lower()

    # Validate extension
    if extension not in allowed_formats:
        return False, f"File format '{extension}' is not supported. Allowed formats: {', '.join(allowed_formats)}"

    logger.debug(f"Format validation passed: .{extension}")
    return True, ""


def validate_video_codec(metadata: Dict[str, Any], allowed_codecs: list = None) -> Tuple[bool, str]:
    """
    Validate video codec is supported for transcoding.

    Args:
        metadata: Video metadata dictionary from ffprobe
        allowed_codecs: List of allowed codecs (default: ['h264', 'hevc', 'prores', 'dnxhd', 'mpeg4'])

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> metadata = {'codec': 'h264', 'width': 1920, 'height': 1080}
        >>> validate_video_codec(metadata)
        (True, "")
    """
    # Default allowed codecs
    if allowed_codecs is None:
        allowed_codecs = ['h264', 'hevc', 'prores', 'dnxhd', 'mpeg4', 'vp9', 'av1']

    # Normalize to lowercase
    allowed_codecs = [codec.lower() for codec in allowed_codecs]

    # Extract codec from metadata
    codec = metadata.get('codec', '').lower()

    if not codec:
        return False, "Video codec information is missing"

    # Check if codec is supported
    if codec not in allowed_codecs:
        return False, f"Video codec '{codec}' is not supported. Allowed codecs: {', '.join(allowed_codecs)}"

    # Validate resolution exists
    width = metadata.get('width', 0)
    height = metadata.get('height', 0)

    if width == 0 or height == 0:
        return False, "Invalid video resolution (width or height is 0)"

    # Check for reasonable resolution limits (max 8K)
    if width > 7680 or height > 4320:
        return False, f"Video resolution ({width}x{height}) exceeds maximum supported (7680x4320)"

    # Check for minimum resolution (at least 144p)
    if width < 256 or height < 144:
        return False, f"Video resolution ({width}x{height}) is too small (minimum 256x144)"

    logger.debug(f"Codec validation passed: {codec} at {width}x{height}")
    return True, ""


def validate_video_integrity(file_path: str) -> Tuple[bool, str]:
    """
    Validate video file integrity using ffprobe.

    Attempts to read video metadata to ensure file is not corrupted.

    Args:
        file_path: Absolute path to video file

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> validate_video_integrity("/path/to/video.mp4")
        (True, "")
        >>> validate_video_integrity("/path/to/corrupted.mp4")
        (False, "Video file is corrupted or unreadable")
    """
    # Import here to avoid circular dependency
    from services.video_metadata_extractor import validate_video_file_with_ffprobe

    # Check if file exists
    if not os.path.exists(file_path):
        return False, f"Video file not found: {file_path}"

    if not os.path.isfile(file_path):
        return False, f"Path is not a file: {file_path}"

    # Check file permissions
    if not os.access(file_path, os.R_OK):
        return False, f"Cannot read video file (permission denied): {file_path}"

    # Use ffprobe to validate file integrity
    try:
        is_valid = validate_video_file_with_ffprobe(file_path)
        if not is_valid:
            return False, "Video file is corrupted or unreadable"

        logger.debug(f"Integrity validation passed: {file_path}")
        return True, ""

    except Exception as e:
        logger.error(f"Error validating video integrity: {str(e)}")
        return False, f"Failed to validate video integrity: {str(e)}"


def get_estimated_transcode_time(
    duration_seconds: float,
    file_size_bytes: int,
    preset: str = 'fast'
) -> int:
    """
    Estimate transcoding time based on video duration and file size.

    Rough estimation based on:
    - ultrafast preset: ~0.5x realtime (60 min video = 30 min transcode)
    - fast preset: ~1x realtime (60 min video = 60 min transcode)
    - medium preset: ~1.5x realtime (60 min video = 90 min transcode)
    - slow preset: ~2x realtime (60 min video = 120 min transcode)

    Args:
        duration_seconds: Video duration in seconds
        file_size_bytes: Original file size in bytes
        preset: FFmpeg preset ('ultrafast', 'fast', 'medium', 'slow')

    Returns:
        Estimated transcode time in seconds

    Example:
        >>> get_estimated_transcode_time(3600, 3145728000, 'fast')  # 1 hour video, 3GB
        3600  # ~1 hour transcode time
    """
    # Preset speed multipliers (relative to realtime)
    preset_multipliers = {
        'ultrafast': 0.5,
        'fast': 1.0,
        'medium': 1.5,
        'slow': 2.0,
        'slower': 2.5,
        'veryslow': 3.0
    }

    # Get multiplier for preset (default to fast)
    multiplier = preset_multipliers.get(preset.lower(), 1.0)

    # Base estimate on duration
    base_estimate = duration_seconds * multiplier

    # Adjust for file size (larger files may take longer)
    # Add 10% extra time for every GB over 1GB
    file_size_gb = file_size_bytes / (1024 * 1024 * 1024)
    if file_size_gb > 1:
        size_adjustment = 1 + ((file_size_gb - 1) * 0.1)
        base_estimate *= size_adjustment

    # Add a safety margin (20%)
    estimated_time = int(base_estimate * 1.2)

    # Minimum estimate of 10 seconds
    estimated_time = max(10, estimated_time)

    logger.debug(
        f"Estimated transcode time: {estimated_time}s "
        f"(duration={duration_seconds}s, size={file_size_gb:.2f}GB, preset={preset})"
    )

    return estimated_time


def validate_all(
    file_path: str,
    file_size: int,
    filename: str,
    allowed_formats: list = None,
    allowed_codecs: list = None,
    max_size_mb: int = 3072
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Run all video validations in sequence.

    This is a convenience function that runs all validation checks
    and returns the first error encountered, or success with metadata.

    Args:
        file_path: Path to video file
        file_size: File size in bytes
        filename: Original filename
        allowed_formats: List of allowed file formats
        allowed_codecs: List of allowed codecs
        max_size_mb: Maximum file size in MB

    Returns:
        Tuple of (is_valid, error_message, metadata_dict)
        - If valid: (True, "", metadata)
        - If invalid: (False, "error message", {})

    Example:
        >>> is_valid, error, metadata = validate_all("/path/to/video.mp4", 2147483648, "video.mp4")
        >>> if is_valid:
        ...     print(f"Valid video: {metadata['duration']}s")
    """
    from services.video_metadata_extractor import extract_video_metadata

    # Step 1: Validate file size
    is_valid, error = validate_video_file_size(file_size, max_size_mb)
    if not is_valid:
        return False, error, {}

    # Step 2: Validate format
    is_valid, error = validate_video_format(filename, allowed_formats)
    if not is_valid:
        return False, error, {}

    # Step 3: Validate integrity (quick check)
    is_valid, error = validate_video_integrity(file_path)
    if not is_valid:
        return False, error, {}

    # Step 4: Extract metadata (full check)
    try:
        metadata = extract_video_metadata(file_path)
    except Exception as e:
        logger.error(f"Failed to extract metadata: {str(e)}")
        return False, f"Failed to read video metadata: {str(e)}", {}

    # Step 5: Validate codec and resolution
    is_valid, error = validate_video_codec(metadata, allowed_codecs)
    if not is_valid:
        return False, error, metadata

    logger.info(f"All validations passed for: {filename}")
    return True, "", metadata
