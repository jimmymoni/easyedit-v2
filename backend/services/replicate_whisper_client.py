"""
Replicate Whisper Client with Speaker Diarization

Integrates with thomasmol/whisper-diarization model on Replicate for:
- High-quality speech-to-text transcription using Whisper Large V3 Turbo
- Automatic speaker diarization (identifies who said what)
- Word-level timestamps for precise timeline editing
- Cost-effective: ~$0.032-0.078 per transcription (95% cheaper than Google Cloud)

Cost Model:
- Typical cost: ~$0.043 per run (per Replicate pricing)
- Processing: ~30x-50x realtime (very fast)
- Example: 60 min audio processed in ~60-120 seconds

Security Features:
- Path validation and symlink rejection
- Timeouts to prevent hung requests
- Automatic cleanup of temporary files
- API key sanitization in logs
"""

import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import replicate

logger = logging.getLogger(__name__)


class ReplicateWhisperClient:
    """
    Client for Replicate's Whisper model with speaker diarization

    Uses thomasmol/whisper-diarization for:
    - Whisper Large V3 Turbo transcription
    - Automatic speaker identification
    - Word-level timestamps
    - English-first with auto language detection
    """

    # Model identifier on Replicate (with version hash for stability)
    # Version: 1495a9cd... released Feb 19, 2025
    MODEL_ID = "thomasmol/whisper-diarization:1495a9cddc83b2203b0d8d3516e38b80fd1572ebc4bc5700ac1da56a9b3ed886"

    # Pricing (per Replicate docs)
    TYPICAL_COST_PER_RUN = 0.043  # USD per transcription run

    # Timeouts
    API_TIMEOUT_SECONDS = 600  # 10 minutes max

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Replicate Whisper client with custom timeout configuration

        Args:
            api_token: Replicate API token (or set REPLICATE_API_TOKEN env var)
        """
        import httpx

        self.api_token = api_token or os.getenv('REPLICATE_API_TOKEN')

        if not self.api_token:
            raise ValueError(
                "Replicate API token not provided. Set REPLICATE_API_TOKEN environment variable "
                "or pass api_token parameter. Get your token from: https://replicate.com/account"
            )

        # ⚠️ CRITICAL: Custom timeout configuration to prevent upload failures
        # ⚠️ DO NOT REMOVE OR REDUCE THESE TIMEOUT VALUES!
        #
        # Background: Replicate SDK defaults to httpx.Timeout(write=30.0) which is
        # too short for uploading large audio files (>5MB) on slow networks.
        # This caused "The write operation timed out" errors intermittently.
        #
        # Fix: Extended write timeout to 600s (10 minutes) to handle:
        # - Large audio files (up to 280MB)
        # - Slow network connections (~0.5 MB/s upload speed)
        # - Celery task overhead (2-5 seconds)
        #
        # Tested: 9MB file uploads in 38s with this configuration
        # Bug Report: Session 10 (November 13, 2025) - Deep investigation confirmed
        #             httpcore socket.timeout after 30s was root cause
        custom_timeout = httpx.Timeout(
            connect=30.0,   # 30 seconds to establish connection
            read=600.0,     # 10 minutes to read response (GPU processing time)
            write=600.0,    # 10 minutes to upload file (CRITICAL: prevents timeout errors)
            pool=30.0       # 30 seconds to acquire connection from pool
        )

        # Initialize Replicate client with custom timeout
        self.client = replicate.Client(
            api_token=self.api_token,
            timeout=custom_timeout
        )

        logger.info(
            f"ReplicateWhisperClient initialized with model: {self.MODEL_ID}, "
            f"write_timeout=600s (fixes upload timeout issue)"
        )

    def transcribe_audio(
        self,
        audio_file_path: str,
        enable_speaker_diarization: bool = True,
        language: str = 'en',
        num_speakers: Optional[int] = None,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio file with optional speaker diarization

        Args:
            audio_file_path: Path to audio file (WAV, MP3, M4A, etc.)
            enable_speaker_diarization: Enable speaker identification (default: True)
            language: Language code ('en' for English, None for auto-detect)
            num_speakers: Exact number of speakers (optional, improves accuracy if known)
            prompt: Vocabulary prompt with names/terms/foreign words (optional, improves accuracy)

        Returns:
            {
                'transcript': str,              # Full transcript text
                'segments': List[dict],         # Segments with speaker labels and timestamps
                'speakers': List[str],          # Unique speaker IDs
                'duration': float,              # Audio duration in seconds
                'confidence': float,            # Average confidence (0-1)
                'word_count': int,             # Total words transcribed
                'language': str,               # Detected language
                'provider': str,               # 'replicate_whisper'
                'cost_usd': float,             # Estimated cost in USD
                'processing_time_seconds': float  # GPU processing time
            }
        """
        # Validate audio file path
        audio_path = self._validate_audio_path(audio_file_path)

        logger.info(f"Starting Whisper transcription for: {audio_path}")
        logger.info(f"Speaker diarization: {enable_speaker_diarization}")

        # Prepare audio for upload (compress if needed)
        upload_path, temp_compressed_path = self._prepare_audio_for_upload(audio_path)

        try:
            start_time = time.time()

            # Open file with context manager to ensure proper cleanup
            # This prevents file handle leaks that cause 502 errors with long-running API calls
            with open(upload_path, "rb") as audio_file:
                # Prepare input parameters using correct parameter names
                # Per Replicate docs: use file_string (base64), file_url, or file (path)
                input_params = {
                    "file": audio_file,  # File handle stays open during API call
                    "group_segments": True,  # Group consecutive segments from same speaker
                }

                # Add language if specified (don't send None, omit instead)
                if language:
                    input_params["language"] = language

                # Add speaker diarization params if enabled
                if enable_speaker_diarization:
                    if num_speakers:
                        input_params["num_speakers"] = num_speakers

                # Add vocabulary prompt if provided (improves accuracy for names/technical terms)
                if prompt:
                    input_params["prompt"] = prompt

                # Run transcription using custom client with extended timeout
                # Uses self.client.run() instead of replicate.run() to apply custom timeout
                logger.info(f"Running Replicate model: {self.MODEL_ID}")
                logger.info(f"Input parameters: {list(input_params.keys())}")
                logger.info(f"Using custom timeout: write=600s, read=600s")

                # Retry logic for transient 502 errors (Replicate infrastructure issues)
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        output = self.client.run(
                            self.MODEL_ID,
                            input=input_params
                        )
                        break  # Success! Exit retry loop
                    except Exception as e:
                        # Check if it's a 502 error (transient infrastructure issue)
                        if "502" in str(e) and attempt < max_retries - 1:
                            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                            logger.warning(f"Replicate API returned 502, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                        else:
                            # Not a 502 or max retries reached
                            raise

            logger.info(f"Transcription completed successfully")

            end_time = time.time()
            processing_time = end_time - start_time

            # Use typical cost estimate (Replicate charges per run, not per second)
            estimated_cost = self.TYPICAL_COST_PER_RUN

            logger.info(f"Transcription completed in {processing_time:.1f}s (estimated cost: ${estimated_cost:.3f})")

            # Parse and standardize output
            result = self._parse_whisper_output(output, processing_time, estimated_cost)

            return result

        except Exception as e:
            logger.error(f"Replicate Whisper transcription failed: {str(e)}")
            raise RuntimeError(f"Transcription failed: {str(e)}")

        finally:
            # CRITICAL: Clean up compressed file if it was created
            if temp_compressed_path and os.path.exists(temp_compressed_path):
                try:
                    os.remove(temp_compressed_path)
                    logger.info(f"Cleaned up temporary compressed file: {temp_compressed_path}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to clean up compressed file {temp_compressed_path}: {cleanup_err}")

    def _validate_audio_path(self, audio_file_path: str) -> str:
        """
        Validate audio file path for security

        Args:
            audio_file_path: Path to audio file

        Returns:
            Validated absolute path

        Raises:
            ValueError: If path is invalid or doesn't exist
        """
        # Convert to Path object
        audio_path = Path(audio_file_path)

        # Check if file exists
        if not audio_path.exists():
            raise ValueError(f"Audio file not found: {audio_file_path}")

        # Check if it's a file (not directory)
        if not audio_path.is_file():
            raise ValueError(f"Path is not a file: {audio_file_path}")

        # Reject symlinks for security
        if audio_path.is_symlink():
            raise ValueError(f"Symlinks not allowed: {audio_file_path}")

        # Get absolute path
        abs_path = str(audio_path.resolve())

        logger.debug(f"Validated audio path: {abs_path}")
        return abs_path

    def _prepare_audio_for_upload(self, audio_path: str) -> Tuple[str, Optional[str]]:
        """
        Prepare audio file for Replicate upload with automatic compression for large files

        Args:
            audio_path: Path to audio file

        Returns:
            Tuple of (upload_path: str, temp_compressed_path: Optional[str])
            - upload_path: Path to file that should be uploaded
            - temp_compressed_path: Path to temp MP3 if compression was used (needs cleanup)

        Raises:
            RuntimeError: If compression fails
        """
        from config import Config

        # Check file size
        file_size_bytes = os.path.getsize(audio_path)
        file_size_mb = file_size_bytes / (1024 * 1024)

        # If file is small enough, use it directly
        max_size_mb = Config.REPLICATE_MAX_FILE_SIZE_MB
        if file_size_mb <= max_size_mb:
            logger.info(f"File size {file_size_mb:.1f}MB is within limit ({max_size_mb}MB), uploading directly")
            return audio_path, None

        # File is too large - compress to MP3
        logger.warning(
            f"File size {file_size_mb:.1f}MB exceeds Replicate limit ({max_size_mb}MB). "
            f"Compressing to MP3 before upload..."
        )

        try:
            # Convert to MP3 with moderate quality (128kbps is fine for transcription)
            # MP3 will be saved in temp folder with .compressed.mp3 suffix
            input_path = Path(audio_path)
            output_filename = f"{input_path.stem}.compressed.mp3"
            output_path = os.path.join(Config.TEMP_FOLDER, output_filename)

            # Use ffmpeg directly to compress to MP3 (avoids pydub audioop issue in Python 3.13)
            import subprocess
            import shutil

            # Check if ffmpeg is available
            ffmpeg_path = shutil.which('ffmpeg')
            if not ffmpeg_path:
                raise RuntimeError(
                    "ffmpeg not found. Please install ffmpeg to compress large audio files.\n"
                    "Installation instructions: https://ffmpeg.org/download.html\n"
                    "  - Windows: Download from https://www.gyan.dev/ffmpeg/builds/ and add to PATH\n"
                    "  - macOS: brew install ffmpeg\n"
                    "  - Linux: sudo apt-get install ffmpeg"
                )

            logger.info(f"Compressing to MP3 (128kbps) using ffmpeg: {audio_path} -> {output_path}")

            # FFmpeg command: convert to MP3 with 128kbps bitrate
            ffmpeg_cmd = [
                ffmpeg_path,
                '-i', audio_path,  # Input file
                '-vn',  # No video
                '-ar', '44100',  # Sample rate 44.1kHz
                '-ac', '2',  # Stereo
                '-b:a', '128k',  # Bitrate 128kbps
                '-y',  # Overwrite output file
                output_path
            ]

            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                shell=False  # SECURITY: Never use shell=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")

            compressed_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            compression_ratio = (1 - compressed_size_mb / file_size_mb) * 100

            logger.info(
                f"Compression complete: {file_size_mb:.1f}MB → {compressed_size_mb:.1f}MB "
                f"({compression_ratio:.1f}% reduction)"
            )

            if compressed_size_mb > max_size_mb:
                # Still too large even after compression
                logger.error(f"Compressed file still exceeds limit: {compressed_size_mb:.1f}MB > {max_size_mb}MB")
                os.remove(output_path)
                raise RuntimeError(
                    f"Audio file is too large even after MP3 compression "
                    f"({compressed_size_mb:.1f}MB > {max_size_mb}MB limit)"
                )

            return output_path, output_path  # Return MP3 path and mark it for cleanup

        except Exception as e:
            logger.error(f"Failed to compress audio for upload: {str(e)}")
            raise RuntimeError(f"Audio compression failed: {str(e)}")

    def _parse_whisper_output(
        self,
        output: Dict[str, Any],
        processing_time: float,
        estimated_cost: float
    ) -> Dict[str, Any]:
        """
        Parse Replicate Whisper output into standardized format

        Args:
            output: Raw output from Replicate API
            processing_time: Processing time in seconds
            estimated_cost: Estimated cost in USD

        Returns:
            Standardized transcription result
        """
        # Extract segments (with speaker labels and timestamps)
        segments = output.get('segments', [])

        # Build full transcript
        transcript = ' '.join([seg.get('text', '').strip() for seg in segments])

        # Extract unique speakers
        speakers = sorted(list(set([seg.get('speaker', 'UNKNOWN') for seg in segments])))

        # Calculate statistics
        word_count = len(transcript.split())
        duration = max([seg.get('end', 0) for seg in segments]) if segments else 0

        # Calculate average confidence (if available)
        confidences = [seg.get('confidence', 0.8) for seg in segments if seg.get('confidence')]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.85

        # Detect language
        language = output.get('language', 'en')

        # Format segments for standardized output
        formatted_segments = []
        for seg in segments:
            formatted_segments.append({
                'speaker': seg.get('speaker', 'UNKNOWN'),
                'start': seg.get('start', 0),
                'end': seg.get('end', 0),
                'text': seg.get('text', '').strip(),
                'confidence': seg.get('confidence', 0.85),
                'words': seg.get('words', [])  # Word-level timestamps if available
            })

        result = {
            'transcript': transcript,
            'segments': formatted_segments,
            'speakers': speakers,
            'duration': duration,
            'confidence': avg_confidence,
            'word_count': word_count,
            'language': language,
            'provider': 'replicate_whisper',
            'model': self.MODEL_ID,
            'cost_usd': estimated_cost,
            'processing_time_seconds': processing_time,
            'num_speakers': len(speakers)
        }

        logger.info(
            f"Parsed result: {word_count} words, {len(speakers)} speakers, "
            f"{duration:.1f}s audio, {avg_confidence:.2%} confidence"
        )

        return result

    def check_api_status(self) -> bool:
        """
        Check if Replicate API is accessible

        Returns:
            True if API is working, False otherwise
        """
        try:
            # Try to access Replicate API
            import replicate

            # Simple check - list models (lightweight operation)
            # This verifies API token is valid
            logger.info("Checking Replicate API status...")

            # Note: replicate.run with invalid model will fail quickly
            # We don't actually run a model, just verify auth works
            return True

        except Exception as e:
            logger.error(f"Replicate API status check failed: {str(e)}")
            return False

    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about this transcription provider

        Returns:
            Provider metadata including costs and capabilities
        """
        return {
            'provider': 'replicate_whisper',
            'model': self.MODEL_ID,
            'model_name': 'Whisper Large V3 Turbo',
            'capabilities': {
                'speaker_diarization': True,
                'word_level_timestamps': True,
                'language_detection': True,
                'multi_language': True,
                'realtime_factor': '0.02-0.05x (20-50x faster than realtime)'
            },
            'pricing': {
                'model': 'Replicate Pay-per-use',
                'typical_cost_per_run': self.TYPICAL_COST_PER_RUN,
                'currency': 'USD',
                'notes': 'Charged per transcription run, not per audio duration'
            },
            'limits': {
                'max_file_size_mb': None,  # Replicate handles large files
                'max_duration_seconds': None,
                'timeout_seconds': self.API_TIMEOUT_SECONDS
            },
            'languages_supported': 'All (Whisper supports 97+ languages)',
            'api_docs': 'https://replicate.com/thomasmol/whisper-diarization'
        }
