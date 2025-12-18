"""
Video transcoding service with real-time progress monitoring.

This module provides functionality to transcode videos to web-optimized H.264 MP4 format
with real-time progress updates via callback functions.
"""

import logging
import subprocess
import os
import re
from typing import Callable, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def transcode_video(
    input_path: str,
    output_path: str,
    progress_callback: Optional[Callable[[float], None]] = None,
    crf: int = 23,
    preset: str = 'fast',
    max_width: int = 1920,
    max_height: int = 1080,
    audio_bitrate: str = '128k'
) -> bool:
    """
    Transcode video to web-optimized H.264 MP4 with real-time progress.

    This function runs FFmpeg transcoding with progress monitoring. The progress_callback
    is called periodically with the current progress (0.0 to 1.0).

    Args:
        input_path: Path to input video file
        output_path: Path for output video file
        progress_callback: Optional callback function(progress: float) called with progress updates
        crf: CRF quality setting (18-28, lower = better quality)
        preset: FFmpeg encoding preset (ultrafast/fast/medium/slow)
        max_width: Maximum output width in pixels
        max_height: Maximum output height in pixels
        audio_bitrate: Audio bitrate (e.g., '128k')

    Returns:
        True if transcoding succeeded, False if failed

    Example:
        >>> def progress_handler(progress):
        ...     print(f"Progress: {progress*100:.1f}%")
        >>> success = transcode_video(
        ...     "/path/to/input.mp4",
        ...     "/path/to/output.mp4",
        ...     progress_callback=progress_handler
        ... )
    """
    from utils.ffmpeg_helpers import build_transcode_command
    from services.video_metadata_extractor import get_video_duration

    # Validate input file
    if not os.path.exists(input_path):
        logger.error(f"Input file does not exist: {input_path}")
        return False

    # Get video duration for progress calculation
    try:
        duration_seconds = get_video_duration(input_path)
        if duration_seconds is None:
            logger.warning("Could not determine video duration, progress updates may be inaccurate")
            duration_seconds = 0
    except Exception as e:
        logger.warning(f"Error getting video duration: {str(e)}")
        duration_seconds = 0

    # Build FFmpeg command
    command = build_transcode_command(
        input_path=input_path,
        output_path=output_path,
        crf=crf,
        preset=preset,
        max_width=max_width,
        max_height=max_height,
        audio_bitrate=audio_bitrate
    )

    # Start transcoding with progress monitoring
    try:
        logger.info(f"Starting transcode: {input_path} -> {output_path}")
        logger.info(f"Settings: CRF={crf}, preset={preset}, max_res={max_width}x{max_height}")

        success = _run_ffmpeg_with_progress(
            command=command,
            duration_seconds=duration_seconds,
            progress_callback=progress_callback
        )

        if success:
            # Verify output file was created
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                logger.info(f"Transcode completed successfully: {output_path} ({output_size} bytes)")

                # Call progress callback one final time with 100%
                if progress_callback:
                    progress_callback(1.0)

                return True
            else:
                logger.error(f"Transcode claimed success but output file not found: {output_path}")
                return False
        else:
            logger.error("Transcode failed")
            return False

    except Exception as e:
        logger.error(f"Error during transcoding: {str(e)}")

        # Cleanup partial output file if it exists
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
                logger.info(f"Cleaned up partial output file: {output_path}")
            except Exception as cleanup_error:
                logger.warning(f"Could not cleanup partial file: {cleanup_error}")

        return False


def _run_ffmpeg_with_progress(
    command: list,
    duration_seconds: float,
    progress_callback: Optional[Callable[[float], None]] = None
) -> bool:
    """
    Run FFmpeg command and parse progress output in real-time.

    Args:
        command: FFmpeg command as list
        duration_seconds: Total video duration for progress calculation
        progress_callback: Callback function for progress updates

    Returns:
        True if FFmpeg exits successfully, False otherwise
    """
    try:
        # Start FFmpeg process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1  # Line buffered
        )

        # Track progress
        last_progress = 0.0

        # Read progress from stdout line by line
        if process.stdout:
            for line in process.stdout:
                line = line.strip()

                # Parse progress information
                progress_data = _parse_progress_line(line)

                if progress_data and duration_seconds > 0:
                    # Calculate progress percentage
                    current_time = progress_data.get('out_time_seconds', 0)
                    progress = min(current_time / duration_seconds, 1.0)

                    # Only call callback if progress changed significantly (>1%)
                    if progress_callback and (progress - last_progress) >= 0.01:
                        progress_callback(progress)
                        last_progress = progress

        # Wait for process to complete
        return_code = process.wait()

        # Read any remaining stderr
        if process.stderr:
            stderr_output = process.stderr.read()
            if stderr_output and return_code != 0:
                logger.error(f"FFmpeg stderr: {stderr_output}")

        if return_code == 0:
            logger.debug("FFmpeg process completed successfully")
            return True
        else:
            logger.error(f"FFmpeg process failed with exit code {return_code}")
            return False

    except Exception as e:
        logger.error(f"Error running FFmpeg with progress: {str(e)}")
        return False


def _parse_progress_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single line of FFmpeg progress output.

    FFmpeg progress format (with -progress pipe:1):
        frame=150
        fps=30.5
        stream_0_0_q=28.0
        total_size=12345678
        out_time_us=5000000
        out_time_ms=5000
        out_time=00:00:05.000000
        dup_frames=0
        drop_frames=0
        speed=1.02x
        progress=continue

    Args:
        line: Single line from FFmpeg progress output

    Returns:
        Dictionary with parsed values, or None if line doesn't contain progress data
    """
    if '=' not in line:
        return None

    # Parse key=value format
    try:
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()

        # We're primarily interested in out_time (current position)
        if key == 'out_time':
            # Parse timecode format: HH:MM:SS.ffffff
            seconds = _parse_timecode_to_seconds(value)
            if seconds is not None:
                return {'out_time_seconds': seconds}

        elif key == 'out_time_us':
            # Microseconds
            try:
                seconds = int(value) / 1_000_000
                return {'out_time_seconds': seconds}
            except (ValueError, ZeroDivisionError):
                pass

        elif key == 'out_time_ms':
            # Milliseconds
            try:
                seconds = int(value) / 1000
                return {'out_time_seconds': seconds}
            except (ValueError, ZeroDivisionError):
                pass

    except Exception as e:
        logger.debug(f"Could not parse progress line: {line} - {str(e)}")

    return None


def _parse_timecode_to_seconds(timecode: str) -> Optional[float]:
    """
    Parse FFmpeg timecode to seconds.

    Format: HH:MM:SS.ffffff or HH:MM:SS

    Args:
        timecode: Timecode string (e.g., "00:01:30.500000")

    Returns:
        Time in seconds, or None if parsing fails

    Example:
        >>> _parse_timecode_to_seconds("00:01:30.500000")
        90.5
        >>> _parse_timecode_to_seconds("01:00:00")
        3600.0
    """
    try:
        # Handle negative timecodes (shouldn't happen but just in case)
        if timecode.startswith('-'):
            return 0.0

        # Split by colon
        parts = timecode.split(':')
        if len(parts) != 3:
            return None

        hours = int(parts[0])
        minutes = int(parts[1])

        # Seconds might have fractional part
        seconds_str = parts[2]
        seconds = float(seconds_str)

        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds

    except (ValueError, IndexError) as e:
        logger.debug(f"Could not parse timecode: {timecode} - {str(e)}")
        return None


def estimate_output_size(
    input_size_bytes: int,
    input_duration: float,
    crf: int = 23,
    target_resolution: tuple = (1920, 1080)
) -> int:
    """
    Estimate output file size after transcoding.

    This is a rough estimation based on typical compression ratios.

    Args:
        input_size_bytes: Input file size in bytes
        input_duration: Video duration in seconds
        crf: CRF quality setting
        target_resolution: Target resolution tuple (width, height)

    Returns:
        Estimated output size in bytes

    Example:
        >>> estimate_output_size(3145728000, 3600, 23, (1920, 1080))  # 3GB, 1 hour
        524288000  # ~500MB estimated
    """
    # Base compression ratio based on CRF
    # Lower CRF = less compression = higher quality = larger file
    crf_ratios = {
        18: 0.7,   # High quality - 70% of original
        20: 0.6,
        23: 0.4,   # Medium quality - 40% of original (default)
        25: 0.3,
        28: 0.2,   # Low quality - 20% of original
    }

    # Get ratio for given CRF (interpolate if needed)
    if crf in crf_ratios:
        ratio = crf_ratios[crf]
    else:
        # Linear interpolation
        if crf < 18:
            ratio = 0.7
        elif crf > 28:
            ratio = 0.2
        else:
            # Find surrounding values
            lower_crf = max([k for k in crf_ratios.keys() if k < crf])
            upper_crf = min([k for k in crf_ratios.keys() if k > crf])
            lower_ratio = crf_ratios[lower_crf]
            upper_ratio = crf_ratios[upper_crf]

            # Interpolate
            t = (crf - lower_crf) / (upper_crf - lower_crf)
            ratio = lower_ratio + t * (upper_ratio - lower_ratio)

    # Resolution adjustment
    # If downscaling significantly, file will be smaller
    target_pixels = target_resolution[0] * target_resolution[1]
    if target_pixels <= 1920 * 1080:
        # Assume input is higher resolution
        resolution_factor = 0.8
    else:
        resolution_factor = 1.0

    # Calculate estimate
    estimated_size = int(input_size_bytes * ratio * resolution_factor)

    # Minimum size: 1MB
    estimated_size = max(estimated_size, 1024 * 1024)

    logger.debug(
        f"Estimated output size: {estimated_size} bytes "
        f"(input={input_size_bytes}, ratio={ratio:.2f}, resolution_factor={resolution_factor})"
    )

    return estimated_size
