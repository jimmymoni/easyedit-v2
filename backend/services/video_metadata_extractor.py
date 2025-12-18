"""
Video metadata extraction service using FFprobe.

This module provides functionality to extract comprehensive metadata from video files
including duration, resolution, codec, bitrate, frame rate, and audio information.
"""

import logging
import subprocess
import json
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_video_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract comprehensive video metadata using ffprobe.

    Args:
        file_path: Absolute path to video file

    Returns:
        Dictionary containing:
        {
            'duration': float,        # Video duration in seconds
            'width': int,             # Video width in pixels
            'height': int,            # Video height in pixels
            'fps': float,             # Frames per second
            'codec': str,             # Video codec name (e.g., 'h264')
            'bitrate': int,           # Bitrate in bits per second
            'format': str,            # Container format (e.g., 'mp4')
            'has_audio': bool,        # Whether video has audio track
            'audio_codec': str,       # Audio codec name (if present)
            'audio_sample_rate': int, # Audio sample rate (if present)
            'file_size': int          # File size in bytes
        }

    Raises:
        FileNotFoundError: If video file doesn't exist
        ValueError: If ffprobe fails to read video metadata
        RuntimeError: If ffprobe is not installed

    Example:
        >>> metadata = extract_video_metadata("/path/to/video.mp4")
        >>> print(f"{metadata['duration']}s at {metadata['width']}x{metadata['height']}")
        3600.5s at 1920x1080
    """
    # Validate file exists
    video_path = Path(file_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    if not video_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    # Build ffprobe command
    command = [
        'ffprobe',
        '-v', 'quiet',              # Suppress verbose output
        '-print_format', 'json',    # Output as JSON
        '-show_format',             # Show container format info
        '-show_streams',            # Show stream info (video/audio)
        str(video_path)
    ]

    try:
        # Run ffprobe
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr or "Unknown error"
            raise ValueError(f"FFprobe failed to read video: {error_msg}")

        # Parse JSON output
        probe_data = json.loads(result.stdout)

        # Extract metadata
        metadata = _parse_ffprobe_output(probe_data, video_path)

        logger.info(
            f"Extracted metadata: {metadata['duration']:.2f}s, "
            f"{metadata['resolution']}, {metadata['codec']}, "
            f"{metadata['bitrate']//1000}kbps"
        )

        return metadata

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"FFprobe timed out while reading: {file_path}")
    except FileNotFoundError:
        raise RuntimeError("FFprobe is not installed or not in PATH")
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse ffprobe output: {str(e)}")
    except Exception as e:
        logger.error(f"Error extracting video metadata: {str(e)}")
        raise


def _parse_ffprobe_output(probe_data: Dict[str, Any], video_path: Path) -> Dict[str, Any]:
    """
    Parse ffprobe JSON output into structured metadata.

    Args:
        probe_data: Parsed JSON from ffprobe
        video_path: Path to video file (for file size)

    Returns:
        Structured metadata dictionary
    """
    # Extract format information
    format_info = probe_data.get('format', {})
    streams = probe_data.get('streams', [])

    # Find video and audio streams
    video_stream = None
    audio_stream = None

    for stream in streams:
        codec_type = stream.get('codec_type', '')
        if codec_type == 'video' and video_stream is None:
            video_stream = stream
        elif codec_type == 'audio' and audio_stream is None:
            audio_stream = stream

    if not video_stream:
        raise ValueError("No video stream found in file")

    # Extract video metadata
    duration = float(format_info.get('duration', 0))
    if duration == 0:
        # Try to get duration from video stream
        duration = float(video_stream.get('duration', 0))

    width = int(video_stream.get('width', 0))
    height = int(video_stream.get('height', 0))

    # Parse frame rate (can be in various formats like "30/1", "29.97", etc.)
    fps_str = video_stream.get('r_frame_rate', '0/1')
    fps = _parse_frame_rate(fps_str)

    codec = video_stream.get('codec_name', 'unknown')

    # Parse bitrate
    bitrate = int(format_info.get('bit_rate', 0))
    if bitrate == 0:
        # Try to get bitrate from video stream
        bitrate = int(video_stream.get('bit_rate', 0))

    # Get container format
    format_name = format_info.get('format_name', 'unknown')
    # Take first format if multiple (e.g., "mov,mp4,m4a,3gp,3g2,mj2" -> "mov")
    format_name = format_name.split(',')[0]

    # Audio information
    has_audio = audio_stream is not None
    audio_codec = audio_stream.get('codec_name', '') if audio_stream else ''
    audio_sample_rate = int(audio_stream.get('sample_rate', 0)) if audio_stream else 0

    # File size
    file_size = int(format_info.get('size', video_path.stat().st_size))

    return {
        'duration': duration,
        'width': width,
        'height': height,
        'fps': fps,
        'codec': codec,
        'bitrate': bitrate,
        'format': format_name,
        'has_audio': has_audio,
        'audio_codec': audio_codec,
        'audio_sample_rate': audio_sample_rate,
        'file_size': file_size,
        'resolution': f"{width}x{height}"
    }


def _parse_frame_rate(fps_str: str) -> float:
    """
    Parse frame rate from various string formats.

    Args:
        fps_str: Frame rate string (e.g., "30/1", "29.97", "24000/1001")

    Returns:
        Frame rate as float

    Example:
        >>> _parse_frame_rate("30/1")
        30.0
        >>> _parse_frame_rate("29.97")
        29.97
        >>> _parse_frame_rate("24000/1001")
        23.976
    """
    try:
        if '/' in fps_str:
            # Fractional format (e.g., "30/1" or "24000/1001")
            numerator, denominator = fps_str.split('/')
            fps = float(numerator) / float(denominator)
        else:
            # Decimal format (e.g., "29.97")
            fps = float(fps_str)

        return round(fps, 3)
    except (ValueError, ZeroDivisionError):
        logger.warning(f"Could not parse frame rate: {fps_str}")
        return 0.0


def validate_video_file_with_ffprobe(file_path: str) -> bool:
    """
    Validate that a file is a readable video using ffprobe.

    This is a quick integrity check that doesn't extract full metadata.

    Args:
        file_path: Path to video file

    Returns:
        True if file is a valid video, False otherwise

    Example:
        >>> validate_video_file_with_ffprobe("/path/to/video.mp4")
        True
        >>> validate_video_file_with_ffprobe("/path/to/corrupted.mp4")
        False
    """
    try:
        # Quick check - just try to read format info
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_format', file_path],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        logger.debug(f"Video validation failed: {str(e)}")
        return False


def get_video_duration(file_path: str) -> Optional[float]:
    """
    Get video duration in seconds (lightweight operation).

    Args:
        file_path: Path to video file

    Returns:
        Duration in seconds, or None if failed

    Example:
        >>> get_video_duration("/path/to/video.mp4")
        3600.5
    """
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())

        return None
    except Exception as e:
        logger.debug(f"Could not get video duration: {str(e)}")
        return None
