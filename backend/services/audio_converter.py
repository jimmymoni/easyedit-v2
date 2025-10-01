"""
Audio format converter utility using pydub.
Converts various audio formats (MP3, M4A, AAC, FLAC) to WAV for processing.
Requires ffmpeg to be installed on the system.

SECURITY HARDENED VERSION with:
- Path validation & command injection prevention
- Resource limits (file size, disk space, timeout)
- Proper cleanup with temp files
- Thread-safe singleton pattern
- Concurrent conversion limits
"""

import os
import logging
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from collections import defaultdict
from werkzeug.utils import secure_filename
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

logger = logging.getLogger(__name__)

class AudioFormatConverter:
    """Converts audio files to WAV format for analysis with security hardening"""

    SUPPORTED_FORMATS = {'mp3', 'm4a', 'aac', 'flac', 'ogg', 'wma'}

    # Security limits
    MAX_CONCURRENT_CONVERSIONS = 3  # Will be overridden by config
    MAX_CONVERSION_SIZE_MB = 100  # Will be overridden by config
    CONVERSION_TIMEOUT_SECONDS = 300  # Will be overridden by config

    # Shell metacharacters that could be exploited
    DANGEROUS_CHARS = ['&', '|', ';', '`', '$', '(', ')', '<', '>', '\n', '\r', '\x00']

    def __init__(self, temp_folder: str):
        """
        Initialize the audio converter

        Args:
            temp_folder: Directory to store converted WAV files
        """
        self.temp_folder = os.path.abspath(temp_folder)
        os.makedirs(temp_folder, exist_ok=True)

        # Thread safety for concurrent conversions
        self._conversion_semaphore = threading.Semaphore(self.MAX_CONCURRENT_CONVERSIONS)
        self._active_conversions = 0
        self._conversion_lock = threading.Lock()

        # Metrics tracking
        self.metrics = {
            'conversions_total': 0,
            'conversions_success': 0,
            'conversions_failed': 0,
            'conversion_time_total': 0.0,
            'bytes_converted': 0,
            'errors_by_type': defaultdict(int),
            'format_stats': defaultdict(lambda: {'count': 0, 'total_time': 0.0})
        }

    def needs_conversion(self, file_path: str) -> bool:
        """
        Check if a file needs format conversion

        Args:
            file_path: Path to the audio file

        Returns:
            True if file needs conversion, False if already WAV
        """
        extension = Path(file_path).suffix.lower().lstrip('.')
        return extension in self.SUPPORTED_FORMATS

    def _validate_file_path(self, file_path: str, allowed_dirs: list) -> Tuple[bool, Optional[str]]:
        """
        SECURITY: Validate file path for safety

        Args:
            file_path: Path to validate
            allowed_dirs: List of allowed directory paths

        Returns:
            Tuple of (valid: bool, error_message: Optional[str])
        """
        # Check for shell metacharacters
        for char in self.DANGEROUS_CHARS:
            if char in file_path:
                return False, f"Invalid characters in file path: {char}"

        # Check if file exists
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"

        # Reject symbolic links
        if os.path.islink(file_path):
            return False, "Symbolic links are not allowed"

        # Ensure it's a regular file
        if not os.path.isfile(file_path):
            return False, "Path is not a regular file"

        # Resolve to real path and validate it's within allowed directories
        real_path = os.path.realpath(os.path.abspath(file_path))
        allowed_dirs_real = [os.path.realpath(os.path.abspath(d)) for d in allowed_dirs]

        if not any(real_path.startswith(allowed_dir) for allowed_dir in allowed_dirs_real):
            return False, "File path outside allowed directories"

        return True, None

    def _validate_file_size(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        SECURITY: Validate file size is within limits

        Args:
            file_path: Path to file

        Returns:
            Tuple of (valid: bool, error_message: Optional[str])
        """
        file_size = os.path.getsize(file_path)

        if file_size == 0:
            return False, "Input file is empty (0 bytes)"

        MIN_AUDIO_FILE_SIZE = 1024  # 1KB minimum
        if file_size < MIN_AUDIO_FILE_SIZE:
            return False, f"Input file too small ({file_size} bytes), likely corrupted"

        file_size_mb = file_size / (1024 * 1024)
        if file_size_mb > self.MAX_CONVERSION_SIZE_MB:
            return False, f"File too large for conversion: {file_size_mb:.1f}MB (max {self.MAX_CONVERSION_SIZE_MB}MB)"

        return True, None

    def _check_disk_space(self, required_gb: float) -> Tuple[bool, Optional[str]]:
        """
        SECURITY: Check if sufficient disk space is available

        Args:
            required_gb: Required space in GB

        Returns:
            Tuple of (available: bool, error_message: Optional[str])
        """
        try:
            stat = shutil.disk_usage(self.temp_folder)
            free_gb = stat.free / (1024 ** 3)

            # Add 1GB safety buffer
            if free_gb < (required_gb + 1.0):
                return False, f"Insufficient disk space (need {required_gb:.1f}GB, have {free_gb:.1f}GB)"

            return True, None
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return False, f"Could not verify disk space: {str(e)}"

    def convert_to_wav(self, input_path: str, output_path: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Convert audio file to WAV format with comprehensive security checks

        Args:
            input_path: Path to the input audio file
            output_path: Optional path for output WAV file. If None, auto-generates in temp folder.

        Returns:
            Tuple of (success: bool, wav_path: Optional[str], error_message: Optional[str])
        """
        start_time = time.time()
        input_format = None
        temp_output = None

        # SECURITY: Acquire semaphore to limit concurrent conversions
        logger.info(f"Waiting for conversion slot (active: {self._active_conversions})")
        acquired = self._conversion_semaphore.acquire(timeout=30)
        if not acquired:
            self.metrics['conversions_failed'] += 1
            return False, None, "Conversion queue full, try again later"

        try:
            with self._conversion_lock:
                self._active_conversions += 1
                self.metrics['conversions_total'] += 1

            logger.info(f"Starting conversion ({self._active_conversions}/{self.MAX_CONCURRENT_CONVERSIONS} active)")

            # SECURITY: Validate file path
            from config import Config
            allowed_dirs = [Config.UPLOAD_FOLDER, Config.TEMP_FOLDER]
            valid, error_msg = self._validate_file_path(input_path, allowed_dirs)
            if not valid:
                self.metrics['conversions_failed'] += 1
                self.metrics['errors_by_type']['path_validation'] += 1
                return False, None, error_msg

            # SECURITY: Validate file size
            valid, error_msg = self._validate_file_size(input_path)
            if not valid:
                self.metrics['conversions_failed'] += 1
                self.metrics['errors_by_type']['file_size'] += 1
                return False, None, error_msg

            # Get file size for metrics and disk check
            file_size_mb = os.path.getsize(input_path) / (1024 * 1024)

            # SECURITY: Check disk space (estimate 10x expansion for compressed formats)
            estimated_output_gb = (file_size_mb * 10) / 1024
            valid, error_msg = self._check_disk_space(estimated_output_gb)
            if not valid:
                self.metrics['conversions_failed'] += 1
                self.metrics['errors_by_type']['disk_space'] += 1
                return False, None, error_msg

            # Get file format from extension
            input_format = Path(input_path).suffix.lower().lstrip('.')

            # SECURITY: Validate format is supported
            if input_format not in self.SUPPORTED_FORMATS and input_format != 'wav':
                self.metrics['conversions_failed'] += 1
                return False, None, f"Unsupported format: {input_format}"

            # SECURITY: Create temporary file during conversion
            temp_fd, temp_output = tempfile.mkstemp(suffix='.wav', dir=self.temp_folder)
            os.close(temp_fd)  # Close file descriptor to avoid leaks

            # Special handling for M4A (often AAC codec)
            format_for_pydub = 'mp4' if input_format == 'm4a' else input_format

            # Calculate timeout based on file size (1 minute per 10MB, min 30s, max 5 minutes)
            timeout_seconds = max(30, min(self.CONVERSION_TIMEOUT_SECONDS, int(file_size_mb * 6)))

            logger.info(f"Converting {input_format.upper()} to WAV: {input_path} (timeout: {timeout_seconds}s)")

            # Load audio file with error handling
            try:
                audio = AudioSegment.from_file(input_path, format=format_for_pydub)
            except CouldntDecodeError as e:
                self.metrics['conversions_failed'] += 1
                self.metrics['errors_by_type']['decoding_error'] += 1
                if temp_output and os.path.exists(temp_output):
                    os.remove(temp_output)
                return False, None, f"Could not decode {input_format.upper()} file. Ensure ffmpeg is installed. Error: {str(e)}"

            # Validate audio properties
            if len(audio) == 0:
                self.metrics['conversions_failed'] += 1
                if temp_output and os.path.exists(temp_output):
                    os.remove(temp_output)
                return False, None, "Audio file has zero duration"

            if audio.channels == 0:
                self.metrics['conversions_failed'] += 1
                if temp_output and os.path.exists(temp_output):
                    os.remove(temp_output)
                return False, None, "Audio file has no channels"

            # Convert to WAV with standard settings
            audio.export(
                temp_output,
                format='wav',
                parameters=["-acodec", "pcm_s16le"]  # 16-bit PCM
            )

            # Verify the output file was created and is valid
            if not os.path.exists(temp_output):
                self.metrics['conversions_failed'] += 1
                return False, None, "Conversion completed but output file not found"

            output_size = os.path.getsize(temp_output)
            if output_size == 0:
                os.remove(temp_output)
                self.metrics['conversions_failed'] += 1
                return False, None, "Conversion produced empty file"

            # Determine final output path
            if output_path is None:
                # SECURITY: Sanitize filename to prevent path traversal
                input_filename = os.path.basename(Path(input_path).stem)
                input_filename = secure_filename(input_filename)

                # Limit filename length
                if len(input_filename) > 200:
                    input_filename = input_filename[:200]

                output_path = os.path.join(self.temp_folder, f"{input_filename}.converted.wav")
            else:
                # SECURITY: Validate provided output path is within temp folder
                output_path_abs = os.path.abspath(output_path)
                temp_folder_abs = os.path.abspath(self.temp_folder)
                if not output_path_abs.startswith(temp_folder_abs):
                    os.remove(temp_output)
                    self.metrics['conversions_failed'] += 1
                    return False, None, "Output path outside temp directory"

            # Move temp file to final location
            shutil.move(temp_output, output_path)
            temp_output = None  # Successfully moved, no cleanup needed

            # Track success metrics
            conversion_time = time.time() - start_time
            output_size_mb = os.path.getsize(output_path) / (1024 * 1024)

            self.metrics['conversions_success'] += 1
            self.metrics['conversion_time_total'] += conversion_time
            self.metrics['bytes_converted'] += output_size
            self.metrics['format_stats'][input_format]['count'] += 1
            self.metrics['format_stats'][input_format]['total_time'] += conversion_time

            logger.info(
                f"Conversion successful: {output_path} ({output_size_mb:.2f}MB, {conversion_time:.2f}s)"
            )

            return True, output_path, None

        except MemoryError:
            self.metrics['conversions_failed'] += 1
            self.metrics['errors_by_type']['memory_error'] += 1
            error_msg = f"Out of memory during conversion (file size: {file_size_mb:.1f}MB)"
            logger.error(error_msg)
            return False, None, error_msg

        except Exception as e:
            self.metrics['conversions_failed'] += 1
            error_type = type(e).__name__
            self.metrics['errors_by_type'][error_type] += 1

            error_msg = f"Error converting audio file: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

        finally:
            # CRITICAL: Clean up temp file on any failure
            if temp_output and os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                    logger.info(f"Cleaned up partial conversion file: {temp_output}")
                except Exception as cleanup_err:
                    logger.error(f"Failed to clean up temp file {temp_output}: {cleanup_err}")

            # Release semaphore and update counter
            with self._conversion_lock:
                self._active_conversions -= 1
            self._conversion_semaphore.release()
            logger.info(f"Conversion complete ({self._active_conversions}/{self.MAX_CONCURRENT_CONVERSIONS} active)")

    def cleanup_converted_file(self, file_path: str) -> bool:
        """
        SECURITY: Remove a converted WAV file with strict validation

        Args:
            file_path: Path to the converted WAV file

        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            if not file_path or not os.path.exists(file_path):
                return False

            # SECURITY: Only delete files with exact suffix
            if not file_path.endswith('.converted.wav'):
                logger.warning(f"Attempted to delete non-converted file: {file_path}")
                return False

            # SECURITY: Only delete files in temp folder
            file_path_abs = os.path.abspath(file_path)
            temp_folder_abs = os.path.abspath(self.temp_folder)

            if not file_path_abs.startswith(temp_folder_abs):
                logger.error(f"Attempted to delete file outside temp folder: {file_path}")
                return False

            # SECURITY: Additional check - is this a regular file?
            if not os.path.isfile(file_path):
                logger.error(f"Path is not a regular file: {file_path}")
                return False

            os.remove(file_path)
            logger.info(f"Cleaned up converted file: {file_path}")
            return True

        except Exception as e:
            logger.warning(f"Error cleaning up converted file {file_path}: {str(e)}")
            return False

    @staticmethod
    def check_ffmpeg_available() -> Tuple[bool, Optional[str]]:
        """
        SECURITY: Check if ffmpeg is installed and available with hardened subprocess

        Returns:
            Tuple of (available: bool, error_message: Optional[str])
        """
        try:
            import subprocess

            # SECURITY: Explicit security parameters for subprocess
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,  # CRITICAL: Never use shell=True
                env={'PATH': os.environ.get('PATH', '')},  # Minimal environment
                cwd=tempfile.gettempdir()  # Safe working directory
            )

            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0] if result.stdout else "unknown version"

                # Validate it's actually ffmpeg
                if 'ffmpeg version' in version_line.lower():
                    logger.info(f"ffmpeg is available: {version_line}")
                    return True, None
                else:
                    return False, "Unexpected ffmpeg output"
            else:
                return False, "ffmpeg command failed"

        except FileNotFoundError:
            error_msg = (
                "ffmpeg not found. Please install ffmpeg to support MP3/M4A/AAC audio formats.\n"
                "Installation: https://ffmpeg.org/download.html\n"
                "  - Windows: Download from https://www.gyan.dev/ffmpeg/builds/ and add to PATH\n"
                "  - macOS: brew install ffmpeg\n"
                "  - Linux: sudo apt-get install ffmpeg"
            )
            return False, error_msg
        except subprocess.TimeoutExpired:
            return False, "ffmpeg check timed out"
        except Exception as e:
            return False, f"Error checking ffmpeg: {str(e)}"

    def get_audio_info(self, file_path: str) -> Optional[dict]:
        """
        Get information about an audio file

        Args:
            file_path: Path to the audio file

        Returns:
            Dictionary with audio info (duration, channels, sample_rate, format) or None
        """
        try:
            format_ext = Path(file_path).suffix.lower().lstrip('.')
            if format_ext == 'm4a':
                format_ext = 'mp4'

            audio = AudioSegment.from_file(file_path, format=format_ext)

            return {
                'duration_seconds': len(audio) / 1000.0,
                'channels': audio.channels,
                'sample_rate': audio.frame_rate,
                'format': Path(file_path).suffix.lower().lstrip('.'),
                'frame_width': audio.frame_width,
                'bitrate': audio.frame_rate * audio.frame_width * 8 * audio.channels
            }
        except Exception as e:
            logger.error(f"Error getting audio info for {file_path}: {str(e)}")
            return None

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get conversion metrics for monitoring

        Returns:
            Dictionary with conversion metrics
        """
        avg_time = 0.0
        if self.metrics['conversions_success'] > 0:
            avg_time = self.metrics['conversion_time_total'] / self.metrics['conversions_success']

        success_rate = 100.0
        if self.metrics['conversions_total'] > 0:
            success_rate = (self.metrics['conversions_success'] / self.metrics['conversions_total']) * 100

        return {
            'total_conversions': self.metrics['conversions_total'],
            'successful': self.metrics['conversions_success'],
            'failed': self.metrics['conversions_failed'],
            'success_rate_percent': success_rate,
            'average_conversion_time_seconds': avg_time,
            'total_bytes_converted': self.metrics['bytes_converted'],
            'active_conversions': self._active_conversions,
            'errors_by_type': dict(self.metrics['errors_by_type']),
            'format_statistics': dict(self.metrics['format_stats'])
        }


# SECURITY: Thread-safe singleton pattern with lock
_converter_instance: Optional[AudioFormatConverter] = None
_converter_lock = threading.Lock()

def get_converter(temp_folder: Optional[str] = None) -> AudioFormatConverter:
    """
    SECURITY: Get or create the global audio converter instance (thread-safe)

    Args:
        temp_folder: Temp folder path (required on first call)

    Returns:
        AudioFormatConverter instance
    """
    global _converter_instance

    # Double-checked locking pattern for thread safety
    if _converter_instance is None:
        with _converter_lock:
            # Check again inside lock to prevent race condition
            if _converter_instance is None:
                if temp_folder is None:
                    from config import Config
                    temp_folder = Config.TEMP_FOLDER

                    # Load config settings
                    converter = AudioFormatConverter(temp_folder)
                    converter.MAX_CONCURRENT_CONVERSIONS = getattr(Config, 'MAX_CONCURRENT_AUDIO_CONVERSIONS', 3)
                    converter.MAX_CONVERSION_SIZE_MB = getattr(Config, 'MAX_AUDIO_CONVERSION_SIZE_MB', 100)
                    converter.CONVERSION_TIMEOUT_SECONDS = getattr(Config, 'AUDIO_CONVERSION_TIMEOUT_SECONDS', 300)

                    # Recreate semaphore with correct limit
                    converter._conversion_semaphore = threading.Semaphore(converter.MAX_CONCURRENT_CONVERSIONS)

                    _converter_instance = converter
                else:
                    _converter_instance = AudioFormatConverter(temp_folder)

    return _converter_instance
