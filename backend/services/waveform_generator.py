"""
Waveform Generator Service

Generates waveform peak data from video audio tracks using FFmpeg and numpy.

This service extracts audio from video files, calculates peak envelope,
and downsamples to ~1500 samples for efficient timeline visualization.

Performance target: <5 seconds for 5-minute videos

Author: EasyEdit v2 - Phase 2.2.1
"""

import os
import subprocess
import numpy as np
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_SAMPLE_COUNT = 1500
AUDIO_SAMPLE_RATE = 44100  # 44.1 kHz
WAVEFORM_CACHE_DIR = "temp/waveforms"


def ensure_cache_directory() -> str:
    """
    Ensure waveform cache directory exists.

    Returns:
        Path to cache directory
    """
    cache_dir = Path(WAVEFORM_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return str(cache_dir)


def get_cache_path(job_id: str) -> str:
    """
    Get cache file path for a job ID.

    Args:
        job_id: Video job identifier

    Returns:
        Full path to cached waveform JSON file
    """
    ensure_cache_directory()
    return os.path.join(WAVEFORM_CACHE_DIR, f"waveform_{job_id}.json")


def load_waveform_cache(job_id: str) -> Optional[WaveformData]:
    """
    Load cached waveform data from disk.

    Args:
        job_id: Video job identifier

    Returns:
        WaveformData if cache exists and is valid, None otherwise
    """
    cache_path = get_cache_path(job_id)

    if not os.path.exists(cache_path):
        logger.debug(f"Waveform cache not found for job {job_id}")
        return None

    try:
        with open(cache_path, 'r') as f:
            data = json.load(f)

        waveform = WaveformData.from_dict(data)

        # Validate cached data
        is_valid, error = waveform.validate()
        if not is_valid:
            logger.warning(f"Cached waveform for job {job_id} is invalid: {error}")
            return None

        logger.info(f"Loaded cached waveform for job {job_id} ({waveform.samples} samples)")
        return waveform

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Failed to load waveform cache for job {job_id}: {e}")
        return None


def save_waveform_cache(job_id: str, waveform_data: WaveformData) -> str:
    """
    Save waveform data to cache.

    Args:
        job_id: Video job identifier
        waveform_data: WaveformData to save

    Returns:
        Path to saved cache file

    Raises:
        IOError: If failed to write cache file
    """
    cache_path = get_cache_path(job_id)

    try:
        with open(cache_path, 'w') as f:
            json.dump(waveform_data.to_dict(), f)

        logger.info(f"Saved waveform cache for job {job_id} to {cache_path}")
        return cache_path

    except IOError as e:
        logger.error(f"Failed to save waveform cache for job {job_id}: {e}")
        raise


def extract_audio_peaks_ffmpeg(video_path: str) -> tuple[np.ndarray, float, int]:
    """
    Extract audio from video and return raw PCM samples.

    Uses FFmpeg to:
    1. Extract audio stream
    2. Convert to mono (mix channels)
    3. Resample to 44.1 kHz
    4. Output as 32-bit float PCM

    Args:
        video_path: Path to video file

    Returns:
        Tuple of (audio_samples, duration, sample_rate)
        - audio_samples: numpy array of float32 audio samples
        - duration: audio duration in seconds
        - sample_rate: audio sample rate (44100)

    Raises:
        subprocess.CalledProcessError: If FFmpeg command fails
        ValueError: If no audio stream found in video
    """
    logger.info(f"Extracting audio from video: {video_path}")

    # FFmpeg command to extract audio as PCM
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vn',                    # No video
        '-ac', '1',               # Convert to mono (1 channel)
        '-ar', str(AUDIO_SAMPLE_RATE),  # Resample to 44.1 kHz
        '-f', 'f32le',            # Output as 32-bit float PCM, little-endian
        '-'                       # Output to stdout
    ]

    try:
        # Run FFmpeg and capture audio data
        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )

        # Convert bytes to numpy array of float32
        audio_data = np.frombuffer(result.stdout, dtype=np.float32)

        if len(audio_data) == 0:
            raise ValueError("No audio stream found in video")

        # Calculate duration
        duration = len(audio_data) / AUDIO_SAMPLE_RATE

        logger.info(f"Extracted audio: {len(audio_data)} samples, {duration:.2f}s duration")

        return audio_data, duration, AUDIO_SAMPLE_RATE

    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.decode('utf-8') if e.stderr else 'No error output'
        logger.error(f"FFmpeg failed to extract audio: {stderr_output}")

        # Check if video has no audio stream
        if 'does not contain any stream' in stderr_output or 'No audio' in stderr_output:
            raise ValueError("Video does not contain an audio stream")

        raise RuntimeError(f"FFmpeg audio extraction failed: {stderr_output}")


def calculate_peak_envelope(audio_samples: np.ndarray, target_samples: int) -> np.ndarray:
    """
    Calculate peak envelope from audio samples.

    Uses max pooling to downsample audio to target sample count
    while preserving peak amplitudes.

    Args:
        audio_samples: Raw audio samples (float32)
        target_samples: Target number of peak samples (~1500)

    Returns:
        numpy array of peak values (absolute max values per chunk)
    """
    logger.debug(f"Calculating peak envelope: {len(audio_samples)} samples → {target_samples} peaks")

    # Calculate chunk size for downsampling
    chunk_size = max(1, len(audio_samples) // target_samples)

    # Pad audio to make it evenly divisible by chunk_size
    remainder = len(audio_samples) % chunk_size
    if remainder != 0:
        padding = chunk_size - remainder
        audio_samples = np.pad(audio_samples, (0, padding), mode='constant')

    # Reshape into chunks
    num_chunks = len(audio_samples) // chunk_size
    chunks = audio_samples[:num_chunks * chunk_size].reshape(num_chunks, chunk_size)

    # Calculate absolute max for each chunk (peak envelope)
    peaks = np.max(np.abs(chunks), axis=1)

    logger.debug(f"Peak envelope calculated: {len(peaks)} peaks")

    return peaks


def normalize_peaks(peaks: np.ndarray) -> list[float]:
    """
    Normalize peak values to range [0, 1].

    Args:
        peaks: Raw peak values (numpy array)

    Returns:
        List of normalized peak values in range [0, 1]
    """
    # Find max absolute value
    max_peak = np.max(np.abs(peaks))

    # Avoid division by zero
    if max_peak == 0:
        logger.warning("All peaks are zero (silent audio)")
        return [0.0] * len(peaks)

    # Normalize to [0, 1]
    normalized = (np.abs(peaks) / max_peak).astype(float)

    # Convert to Python list
    peaks_list = normalized.tolist()

    logger.debug(f"Normalized {len(peaks_list)} peaks to range [0, 1]")

    return peaks_list


def generate_waveform(
    video_path: str,
    job_id: str,
    samples: int = DEFAULT_SAMPLE_COUNT,
    force_regenerate: bool = False
) -> WaveformData:
    """
    Generate waveform peak data from video file.

    This is the main entry point for waveform generation.
    It orchestrates the entire process:
    1. Check cache (unless force_regenerate=True)
    2. Extract audio using FFmpeg
    3. Calculate peak envelope
    4. Normalize peaks to [0, 1]
    5. Create WaveformData object
    6. Save to cache
    7. Return WaveformData

    Args:
        video_path: Path to video file (proxy or original)
        job_id: Video job identifier
        samples: Target number of peak samples (default: 1500)
        force_regenerate: If True, ignore cache and regenerate

    Returns:
        WaveformData object with peak data

    Raises:
        FileNotFoundError: If video file doesn't exist
        ValueError: If video has no audio stream
        RuntimeError: If FFmpeg or processing fails
    """
    logger.info(f"Generating waveform for job {job_id}: {video_path}")

    # Check if video file exists
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Check cache first (unless force regenerate)
    if not force_regenerate:
        cached = load_waveform_cache(job_id)
        if cached is not None:
            logger.info(f"Using cached waveform for job {job_id}")
            return cached

    # Extract audio from video
    audio_samples, duration, sample_rate = extract_audio_peaks_ffmpeg(video_path)

    # Calculate peak envelope
    peaks = calculate_peak_envelope(audio_samples, samples)

    # Normalize peaks to [0, 1]
    normalized_peaks = normalize_peaks(peaks)

    # Create WaveformData object
    waveform_data = WaveformData(
        job_id=job_id,
        peaks=normalized_peaks,
        sample_rate=sample_rate,
        duration=duration,
        channels=1,  # Mono (we convert to mono in FFmpeg)
        samples=len(normalized_peaks)
    )

    # Validate waveform data
    is_valid, error = waveform_data.validate()
    if not is_valid:
        raise RuntimeError(f"Generated waveform is invalid: {error}")

    # Save to cache
    cache_path = save_waveform_cache(job_id, waveform_data)
    logger.info(f"Waveform generated successfully: {waveform_data.samples} samples, {waveform_data.duration:.2f}s")

    return waveform_data


def cleanup_old_cache(max_age_hours: int = 24) -> int:
    """
    Remove waveform cache files older than max_age_hours.

    Args:
        max_age_hours: Maximum age in hours (default: 24)

    Returns:
        Number of files deleted
    """
    import time

    cache_dir = Path(WAVEFORM_CACHE_DIR)
    if not cache_dir.exists():
        return 0

    now = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0

    for cache_file in cache_dir.glob("waveform_*.json"):
        file_age = now - cache_file.stat().st_mtime
        if file_age > max_age_seconds:
            try:
                cache_file.unlink()
                deleted_count += 1
                logger.info(f"Deleted old waveform cache: {cache_file.name}")
            except OSError as e:
                logger.error(f"Failed to delete cache file {cache_file.name}: {e}")

    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old waveform cache files")

    return deleted_count
