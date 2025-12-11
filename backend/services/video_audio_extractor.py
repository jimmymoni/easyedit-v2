"""
Video Audio Extractor Service
Extracts audio track from video files using FFmpeg for transcription
"""
import logging
import os
import subprocess
import json
from typing import Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)


class VideoAudioExtractor:
    """Extract audio from video files using FFmpeg"""

    def __init__(self):
        self.supported_video_formats = ['.mp4', '.mov', '.avi', '.mkv', '.m4v']
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Check if ffmpeg and ffprobe are available"""
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
            logger.error(f"FFmpeg/ffprobe not available: {e}. Video processing will fail.")

            # Get platform-specific installation instructions
            import platform
            system = platform.system().lower()
            if system == 'windows':
                install_msg = "Install from https://www.gyan.dev/ffmpeg/builds/ and add to PATH"
            elif system == 'darwin':
                install_msg = "Install with: brew install ffmpeg"
            else:
                install_msg = "Install with: sudo apt-get install ffmpeg (or your package manager)"

            raise RuntimeError(
                f"FFmpeg is required for video processing. {install_msg}. "
                f"For detailed instructions, visit the Video Editor page."
            )

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

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Get video metadata using ffprobe

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
