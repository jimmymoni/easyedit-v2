"""
FFmpeg helper utilities for video processing.

This module provides wrappers and utilities for FFmpeg operations including:
- Checking FFmpeg availability
- Running FFmpeg commands safely
- Parsing FFmpeg output
- Constructing FFmpeg command strings
"""

import logging
import subprocess
import re
import shutil
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def check_ffmpeg_installed() -> bool:
    """
    Check if FFmpeg is installed and accessible.

    Returns:
        True if FFmpeg is available, False otherwise

    Example:
        >>> check_ffmpeg_installed()
        True
    """
    try:
        # Use shutil.which to check if ffmpeg is in PATH
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            logger.debug(f"FFmpeg found at: {ffmpeg_path}")
            return True

        logger.warning("FFmpeg not found in PATH")
        return False
    except Exception as e:
        logger.error(f"Error checking FFmpeg installation: {str(e)}")
        return False


def check_ffprobe_installed() -> bool:
    """
    Check if FFprobe is installed and accessible.

    Returns:
        True if FFprobe is available, False otherwise

    Example:
        >>> check_ffprobe_installed()
        True
    """
    try:
        # Use shutil.which to check if ffprobe is in PATH
        ffprobe_path = shutil.which('ffprobe')
        if ffprobe_path:
            logger.debug(f"FFprobe found at: {ffprobe_path}")
            return True

        logger.warning("FFprobe not found in PATH")
        return False
    except Exception as e:
        logger.error(f"Error checking FFprobe installation: {str(e)}")
        return False


def get_ffmpeg_version() -> Optional[str]:
    """
    Get installed FFmpeg version string.

    Returns:
        Version string (e.g., "4.4.2") or None if not installed

    Example:
        >>> get_ffmpeg_version()
        '4.4.2'
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            # Parse version from output
            # Example: "ffmpeg version 4.4.2-0ubuntu0.22.04.1"
            match = re.search(r'ffmpeg version (\S+)', result.stdout)
            if match:
                version = match.group(1)
                logger.debug(f"FFmpeg version: {version}")
                return version

        logger.warning("Could not parse FFmpeg version")
        return None

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg version check timed out")
        return None
    except FileNotFoundError:
        logger.error("FFmpeg not found")
        return None
    except Exception as e:
        logger.error(f"Error getting FFmpeg version: {str(e)}")
        return None


def build_transcode_command(
    input_path: str,
    output_path: str,
    crf: int = 23,
    preset: str = 'fast',
    max_width: int = 1920,
    max_height: int = 1080,
    audio_bitrate: str = '128k'
) -> list:
    """
    Build FFmpeg transcoding command as list of arguments.

    Creates web-optimized H.264 MP4 with:
    - CRF quality control
    - Fast-start for streaming
    - Scaled resolution (maintains aspect ratio)
    - AAC audio

    Args:
        input_path: Path to input video
        output_path: Path to output video
        crf: CRF quality (18-28, lower = better)
        preset: FFmpeg preset (ultrafast/fast/medium/slow)
        max_width: Maximum output width
        max_height: Maximum output height
        audio_bitrate: Audio bitrate (e.g., '128k')

    Returns:
        List of command arguments for subprocess

    Example:
        >>> build_transcode_command('/input.mp4', '/output.mp4')
        ['ffmpeg', '-i', '/input.mp4', '-c:v', 'libx264', ...]
    """
    # Build scaling filter that maintains aspect ratio
    # scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease
    scale_filter = f"scale='min({max_width},iw)':'min({max_height},ih)':force_original_aspect_ratio=decrease"

    command = [
        'ffmpeg',
        '-i', input_path,                    # Input file
        '-c:v', 'libx264',                   # Video codec: H.264
        '-crf', str(crf),                    # Quality (lower = better, 18-28 range)
        '-preset', preset,                    # Encoding speed preset
        '-movflags', '+faststart',           # Enable fast start for web streaming
        '-vf', scale_filter,                 # Video filter: scale while maintaining aspect ratio
        '-c:a', 'aac',                       # Audio codec: AAC
        '-b:a', audio_bitrate,               # Audio bitrate
        '-progress', 'pipe:1',               # Output progress to stdout
        '-y',                                 # Overwrite output file without asking
        output_path                          # Output file
    ]

    logger.debug(f"Built transcode command: {' '.join(command)}")
    return command


def run_ffmpeg_command(
    command: list,
    timeout: Optional[int] = None
) -> subprocess.CompletedProcess:
    """
    Run FFmpeg command safely with error handling.

    Args:
        command: FFmpeg command as list of arguments
        timeout: Optional timeout in seconds

    Returns:
        CompletedProcess object from subprocess

    Raises:
        subprocess.TimeoutExpired: If command exceeds timeout
        subprocess.CalledProcessError: If FFmpeg returns non-zero exit code

    Example:
        >>> cmd = ['ffmpeg', '-version']
        >>> result = run_ffmpeg_command(cmd)
        >>> result.returncode
        0
    """
    try:
        logger.debug(f"Running FFmpeg command: {' '.join(command)}")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True
        )
        return result

    except subprocess.TimeoutExpired as e:
        logger.error(f"FFmpeg command timed out after {timeout} seconds")
        raise

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg command failed with exit code {e.returncode}")
        logger.error(f"FFmpeg stderr: {e.stderr}")
        raise

    except FileNotFoundError:
        logger.error("FFmpeg executable not found")
        raise RuntimeError("FFmpeg is not installed or not in PATH")

    except Exception as e:
        logger.error(f"Unexpected error running FFmpeg: {str(e)}")
        raise
