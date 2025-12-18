"""
Video Audio Extractor Service
Extracts audio track from video files using FFmpeg or Replicate cloud models
"""
import logging
import os
import subprocess
import json
import requests
from typing import Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)


class VideoAudioExtractor:
    """Extract audio from video files using FFmpeg or Replicate cloud models"""

    def __init__(self):
        self.supported_video_formats = ['.mp4', '.mov', '.avi', '.mkv', '.m4v']
        self.use_cloud = Config.USE_CLOUD_VIDEO_PROCESSING

        # Only check FFmpeg if not using cloud processing or as fallback
        if not self.use_cloud:
            self._check_ffmpeg()
        else:
            logger.info("Cloud video processing enabled - FFmpeg not required")
            # Initialize Replicate client if using cloud mode
            try:
                from services.replicate_video_client import ReplicateVideoClient
                self.replicate_client = ReplicateVideoClient()
                logger.info("Replicate video client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Replicate client, falling back to local FFmpeg: {e}")
                self.use_cloud = False
                self._check_ffmpeg()

    def _check_ffmpeg(self, raise_on_error=True):
        """
        Check if ffmpeg and ffprobe are available

        Args:
            raise_on_error: If True, raise RuntimeError when FFmpeg is missing.
                          If False, just log a warning.
        """
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=5
            )
            subprocess.run(
                ['ffprobe', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=5
            )
            logger.info("FFmpeg and ffprobe are available for video processing")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            error_msg = f"FFmpeg/ffprobe not available: {e}"

            # Get platform-specific installation instructions
            import platform
            system = platform.system().lower()
            if system == 'windows':
                install_msg = "Install from https://www.gyan.dev/ffmpeg/builds/ and add to PATH"
            elif system == 'darwin':
                install_msg = "Install with: brew install ffmpeg"
            else:
                install_msg = "Install with: sudo apt-get install ffmpeg (or your package manager)"

            full_error_msg = (
                f"FFmpeg is required for video processing. {install_msg}. "
                f"For detailed instructions, visit the Video Editor page."
            )

            if raise_on_error:
                logger.error(f"{error_msg} Video processing will fail.")
                raise RuntimeError(full_error_msg)
            else:
                logger.warning(f"{error_msg} Cloud processing mode is active - FFmpeg not required for upload.")

    def extract_audio(
        self,
        video_path: str,
        output_audio_path: str,
        sample_rate: int = None
    ) -> Dict[str, Any]:
        """
        Extract audio track from video file

        Args:
            video_path: Path to the input video file
            output_audio_path: Where to save the extracted audio (WAV format)
            sample_rate: Audio sample rate (default: from config, 16kHz for speech)

        Returns:
            {
                'success': bool,
                'audio_path': str,
                'duration': float,
                'video_info': {
                    'width': int,
                    'height': int,
                    'fps': float,
                    'codec': str
                }
            }
        """
        # Route to cloud or local extraction
        if self.use_cloud:
            return self._extract_audio_cloud(video_path, output_audio_path, sample_rate)
        else:
            return self._extract_audio_local(video_path, output_audio_path, sample_rate)

    def _extract_audio_local(
        self,
        video_path: str,
        output_audio_path: str,
        sample_rate: int = None
    ) -> Dict[str, Any]:
        """
        Extract audio using local FFmpeg

        Args:
            video_path: Path to the input video file
            output_audio_path: Where to save the extracted audio (WAV format)
            sample_rate: Audio sample rate (default: from config, 16kHz for speech)

        Returns:
            Dict with success, audio_path, duration, video_info
        """
        try:
            # Validate input
            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                return {'success': False, 'error': 'Video file not found'}

            # Check video format
            file_ext = os.path.splitext(video_path)[1].lower()
            if file_ext not in self.supported_video_formats:
                logger.error(f"Unsupported video format: {file_ext}")
                return {'success': False, 'error': f'Unsupported video format: {file_ext}'}

            # Get video info first
            video_info = self.get_video_info(video_path)
            if not video_info.get('success'):
                return {'success': False, 'error': 'Failed to get video info'}

            # Use sample rate from config if not specified
            if sample_rate is None:
                sample_rate = Config.VIDEO_ANALYSIS_SAMPLE_RATE

            logger.info(f"Extracting audio from {video_path} at {sample_rate}Hz")
            logger.info(f"Video info: {video_info['width']}x{video_info['height']}, {video_info['duration']:.1f}s, {video_info['codec']}")

            # FFmpeg command to extract audio
            # -vn: No video
            # -acodec pcm_s16le: WAV format (16-bit PCM)
            # -ar: Sample rate (16000Hz for speech recognition)
            # -ac 1: Mono (transcription doesn't need stereo)
            command = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # WAV format
                '-ar', str(sample_rate),  # Sample rate
                '-ac', '1',  # Mono
                '-y',  # Overwrite output file
                output_audio_path
            ]

            # Execute FFmpeg
            logger.debug(f"Running FFmpeg command: {' '.join(command)}")
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600,  # 10 minute timeout
                check=True
            )

            # Verify output file was created
            if not os.path.exists(output_audio_path):
                logger.error("Audio extraction completed but output file not found")
                return {'success': False, 'error': 'Audio extraction failed'}

            # Get output file size
            audio_size_mb = os.path.getsize(output_audio_path) / (1024 * 1024)
            logger.info(f"Audio extracted successfully: {audio_size_mb:.2f}MB")

            return {
                'success': True,
                'audio_path': output_audio_path,
                'duration': video_info['duration'],
                'audio_size_mb': audio_size_mb,
                'sample_rate': sample_rate,
                'video_info': {
                    'width': video_info['width'],
                    'height': video_info['height'],
                    'fps': video_info['fps'],
                    'codec': video_info['codec']
                }
            }

        except subprocess.TimeoutExpired:
            logger.error("Audio extraction timed out (>10 minutes)")
            return {'success': False, 'error': 'Audio extraction timed out'}
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error during audio extraction: {e.stderr.decode('utf-8', errors='ignore')}")
            return {'success': False, 'error': 'FFmpeg audio extraction failed'}
        except Exception as e:
            logger.error(f"Unexpected error during audio extraction: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _extract_audio_cloud(
        self,
        video_path: str,
        output_audio_path: str,
        sample_rate: int = None
    ) -> Dict[str, Any]:
        """
        Extract audio using Replicate cloud models

        NOTE: Currently uses a workaround since Replicate doesn't have a dedicated
        audio extraction model. For MVP, fall back to local FFmpeg for audio extraction.
        Cloud processing is more beneficial for video cutting/encoding (CPU-intensive).

        Args:
            video_path: Path to the input video file
            output_audio_path: Where to save the extracted audio (WAV format)
            sample_rate: Audio sample rate (default: from config, 16kHz for speech)

        Returns:
            Dict with success, audio_path, duration, video_info
        """
        try:
            logger.info("Cloud audio extraction - falling back to local FFmpeg (audio extraction is fast)")
            # Audio extraction is lightweight and fast with FFmpeg
            # No benefit from cloud processing for this operation
            return self._extract_audio_local(video_path, output_audio_path, sample_rate)

        except Exception as e:
            logger.error(f"Cloud audio extraction failed: {e}")
            logger.info("Falling back to local FFmpeg for audio extraction")
            return self._extract_audio_local(video_path, output_audio_path, sample_rate)

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Get video metadata using ffprobe (local) or basic file info (cloud mode)

        Args:
            video_path: Path to the video file

        Returns:
            {
                'success': bool,
                'duration': float,
                'size_mb': float,
                'width': int,
                'height': int,
                'fps': float,
                'codec': str,
                'audio_codec': str (optional)
            }
        """
        # In cloud mode, return basic metadata without FFmpeg
        # Actual metadata will be extracted during transcode phase
        if self.use_cloud:
            try:
                if not os.path.exists(video_path):
                    logger.error(f"Video file not found: {video_path}")
                    return {'success': False, 'error': 'Video file not found'}

                # Get file size
                size_bytes = os.path.getsize(video_path)
                size_mb = size_bytes / (1024 * 1024)

                logger.info(f"Cloud mode: Returning basic metadata for {video_path} ({size_mb:.2f}MB)")
                logger.info("Full metadata will be extracted during cloud transcode phase")

                # Return basic metadata with placeholder values
                # These will be updated after transcode completes
                return {
                    'success': True,
                    'duration': 0,  # Will be updated after transcode
                    'size_mb': size_mb,
                    'width': 1920,  # Placeholder - will be updated
                    'height': 1080,  # Placeholder - will be updated
                    'fps': 30.0,  # Placeholder - will be updated
                    'codec': 'unknown',  # Will be updated after transcode
                    'audio_codec': 'unknown'  # Will be updated after transcode
                }
            except Exception as e:
                logger.error(f"Error getting basic video info: {str(e)}")
                return {'success': False, 'error': str(e)}

        # Local mode: Use FFmpeg to get detailed metadata
        try:
            # FFprobe command to get video metadata as JSON
            command = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration,size:stream=width,height,r_frame_rate,codec_name,codec_type',
                '-of', 'json',
                video_path
            ]

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=True
            )

            # Parse JSON output
            probe_data = json.loads(result.stdout.decode('utf-8'))

            # Extract format info
            format_info = probe_data.get('format', {})
            duration = float(format_info.get('duration', 0))
            size_bytes = int(format_info.get('size', 0))
            size_mb = size_bytes / (1024 * 1024)

            # Extract stream info (video and audio streams)
            streams = probe_data.get('streams', [])
            video_stream = None
            audio_codec = None

            for stream in streams:
                if stream.get('codec_type') == 'video' and not video_stream:
                    video_stream = stream
                elif stream.get('codec_type') == 'audio' and not audio_codec:
                    audio_codec = stream.get('codec_name', 'unknown')

            if not video_stream:
                logger.error("No video stream found in file")
                return {'success': False, 'error': 'No video stream found'}

            # Parse video properties
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            codec = video_stream.get('codec_name', 'unknown')

            # Parse frame rate (format: "30000/1001" or "30")
            fps_str = video_stream.get('r_frame_rate', '0/1')
            if '/' in fps_str:
                num, den = fps_str.split('/')
                fps = float(num) / float(den) if float(den) != 0 else 0
            else:
                fps = float(fps_str)

            return {
                'success': True,
                'duration': duration,
                'size_mb': size_mb,
                'width': width,
                'height': height,
                'fps': round(fps, 2),
                'codec': codec,
                'audio_codec': audio_codec
            }

        except subprocess.TimeoutExpired:
            logger.error("ffprobe timed out")
            return {'success': False, 'error': 'ffprobe timed out'}
        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe error: {e.stderr.decode('utf-8', errors='ignore')}")
            return {'success': False, 'error': 'ffprobe failed'}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ffprobe JSON output: {str(e)}")
            return {'success': False, 'error': 'Failed to parse video metadata'}
        except Exception as e:
            logger.error(f"Unexpected error getting video info: {str(e)}")
            return {'success': False, 'error': str(e)}
