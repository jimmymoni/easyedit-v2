"""
Cloud-first video validation - no local FFmpeg required.

This module provides lightweight validation for cloud video processing.
Only validates file size and extension - actual video integrity and codec
validation is performed by cloud services (Replicate).
"""

import logging
from typing import Tuple
from utils.video_validators import validate_video_file_size, validate_video_format

logger = logging.getLogger(__name__)


def validate_all_cloud_first(
    file_size: int,
    filename: str,
    allowed_formats: list = None,
    max_size_mb: int = 3072
) -> Tuple[bool, str]:
    """
    Validate video for cloud upload (size + extension only).

    No FFmpeg validation - cloud will validate integrity, codec, and resolution.

    This is a lightweight validator that only checks:
    1. File size is within limits
    2. File extension is supported

    The cloud processing service (Replicate) will validate:
    - Video file integrity
    - Codec compatibility
    - Resolution limits
    - Actual video duration and metadata

    Args:
        file_size: File size in bytes
        filename: Original filename
        allowed_formats: List of allowed extensions (default: ['mp4', 'mov', 'mxf', 'avi'])
        max_size_mb: Maximum file size in MB (default: 3072 = 3GB)

    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if valid
        - (False, "error message") if invalid

    Example:
        >>> is_valid, error = validate_all_cloud_first(
        ...     file_size=2147483648,
        ...     filename="video.mp4",
        ...     allowed_formats=['mp4', 'mov'],
        ...     max_size_mb=3072
        ... )
        >>> if is_valid:
        ...     print("Video accepted for cloud processing")
    """
    # Step 1: Validate file size
    is_valid, error = validate_video_file_size(file_size, max_size_mb)
    if not is_valid:
        logger.warning(f"Cloud-first validation failed (size): {error}")
        return False, error

    # Step 2: Validate format (extension only)
    is_valid, error = validate_video_format(filename, allowed_formats)
    if not is_valid:
        logger.warning(f"Cloud-first validation failed (format): {error}")
        return False, error

    logger.info(f"Cloud-first validation passed: {filename} ({file_size / (1024*1024):.1f} MB)")
    return True, ""
