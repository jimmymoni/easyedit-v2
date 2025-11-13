"""
Audio Extractor Service
Generates edited audio files based on timeline clip data
Uses ffmpeg directly for Python 3.13 compatibility (pydub incompatible)
"""
import logging
import os
import subprocess
import tempfile
from typing import List, Dict, Optional
from models.timeline import Timeline, Clip

logger = logging.getLogger(__name__)


class AudioExtractor:
    """Extract and concatenate audio segments based on timeline clips using ffmpeg"""

    def __init__(self):
        self.supported_formats = ['.wav', '.mp3', '.m4a', '.aac', '.flac']
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Check if ffmpeg is available"""
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=5
            )
            logger.info("ffmpeg is available for audio extraction")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"ffmpeg not available: {e}. Audio extraction will fail.")

    def extract_audio_from_timeline(
        self,
        original_audio_path: str,
        timeline: Timeline,
        output_path: str,
        crossfade_ms: int = 50
    ) -> bool:
        """
        Extract audio segments based on timeline clips and concatenate them

        Args:
            original_audio_path: Path to the original audio file
            timeline: Timeline object with clip data
            output_path: Where to save the extracted audio
            crossfade_ms: Milliseconds of crossfade between segments (default: 50ms)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate input file
            if not os.path.exists(original_audio_path):
                logger.error(f"Original audio file not found: {original_audio_path}")
                return False

            # Check if format is supported
            file_ext = os.path.splitext(original_audio_path)[1].lower()
            if file_ext not in self.supported_formats:
                logger.error(f"Unsupported audio format: {file_ext}")
                return False

            logger.info(f"Loading original audio: {original_audio_path}")

            # Get clips from the first audio track
            audio_track = None
            for track in timeline.tracks:
                if track.track_type == 'audio' or 'audio' in track.name.lower():
                    audio_track = track
                    break

            if not audio_track or not audio_track.clips:
                logger.error("No audio clips found in timeline")
                return False

            logger.info(f"Found {len(audio_track.clips)} clips to extract")

            # DEBUG: Log all clip timestamps being extracted
            for i, clip in enumerate(audio_track.clips, 1):
                if clip.enabled:
                    start = clip.media_start if clip.media_start is not None else clip.start_time
                    end = clip.media_end if clip.media_end is not None else clip.end_time
                    logger.info(f"  Clip {i}: media_start={start}s, media_end={end}s, duration={end-start}s")

            # Extract segments using ffmpeg
            temp_segment_files = []
            try:
                for i, clip in enumerate(audio_track.clips):
                    if not clip.enabled:
                        logger.debug(f"Skipping disabled clip {i+1}")
                        continue

                    # Calculate segment boundaries in seconds
                    # Use media_start/media_end if available, otherwise use start_time/end_time
                    if clip.media_start is not None and clip.media_end is not None:
                        start_sec = clip.media_start
                        end_sec = clip.media_end
                    else:
                        start_sec = clip.start_time
                        end_sec = clip.end_time

                    duration = end_sec - start_sec

                    if duration <= 0:
                        logger.warning(f"Invalid clip duration: {duration}s")
                        continue

                    # Create temporary file for this segment
                    temp_segment = tempfile.NamedTemporaryFile(
                        suffix='.wav',
                        delete=False,
                        dir=os.path.dirname(output_path) or None
                    )
                    temp_segment.close()
                    temp_segment_files.append(temp_segment.name)

                    # Extract segment using ffmpeg
                    cmd = [
                        'ffmpeg',
                        '-i', original_audio_path,
                        '-ss', str(start_sec),
                        '-t', str(duration),
                        '-acodec', 'pcm_s16le',  # WAV format
                        '-ar', '44100',  # 44.1kHz sample rate
                        '-y',  # Overwrite output
                        temp_segment.name
                    ]

                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=300  # 5 minute timeout
                    )

                    if result.returncode != 0:
                        logger.error(f"ffmpeg extraction failed for clip {i+1}: {result.stderr.decode()}")
                        continue

                    logger.debug(f"Extracted clip {i+1}: {start_sec}s - {end_sec}s ({duration}s)")

                if not temp_segment_files:
                    logger.error("No valid segments extracted from timeline")
                    return False

                # Concatenate segments using ffmpeg concat filter
                logger.info(f"Concatenating {len(temp_segment_files)} segments")

                # Ensure output directory exists
                output_dir = os.path.dirname(output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)

                if len(temp_segment_files) == 1:
                    # Single segment - just copy
                    import shutil
                    shutil.copy2(temp_segment_files[0], output_path)
                    logger.info("Single segment - copied directly")
                else:
                    # Multiple segments - concatenate with crossfade
                    # Create concat file list for ffmpeg
                    concat_file = tempfile.NamedTemporaryFile(
                        mode='w',
                        suffix='.txt',
                        delete=False,
                        dir=os.path.dirname(output_path) or None
                    )

                    for segment_file in temp_segment_files:
                        concat_file.write(f"file '{segment_file}'\n")
                    concat_file.close()

                    try:
                        # Use ffmpeg concat demuxer for simple concatenation
                        # Note: crossfade would require complex filtergraph, keeping it simple for now
                        cmd = [
                            'ffmpeg',
                            '-f', 'concat',
                            '-safe', '0',
                            '-i', concat_file.name,
                            '-acodec', 'pcm_s16le',
                            '-ar', '44100',
                            '-y',
                            output_path
                        ]

                        result = subprocess.run(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=300
                        )

                        if result.returncode != 0:
                            logger.error(f"ffmpeg concatenation failed: {result.stderr.decode()}")
                            return False

                    finally:
                        # Clean up concat file
                        try:
                            os.unlink(concat_file.name)
                        except:
                            pass

                # Get duration info using ffprobe
                original_duration = self.get_audio_duration(original_audio_path)
                edited_duration = self.get_audio_duration(output_path)

                logger.info(f"Successfully created edited audio: {output_path}")
                if original_duration and edited_duration:
                    logger.info(f"Original duration: {original_duration:.2f}s, Edited duration: {edited_duration:.2f}s")
                    logger.info(f"Compression: {((1 - edited_duration/original_duration) * 100):.1f}%")

                return True

            finally:
                # Clean up temporary segment files
                for temp_file in temp_segment_files:
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")

        except Exception as e:
            logger.error(f"Failed to extract audio from timeline: {str(e)}", exc_info=True)
            return False

    def get_audio_duration(self, audio_path: str) -> Optional[float]:
        """
        Get the duration of an audio file in seconds using ffprobe

        Args:
            audio_path: Path to the audio file

        Returns:
            float: Duration in seconds, or None if error
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=True
            )

            duration = float(result.stdout.decode().strip())
            return duration

        except Exception as e:
            logger.error(f"Failed to get audio duration: {str(e)}")
            return None
