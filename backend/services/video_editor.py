"""
Video Editor Service
Cuts and encodes video based on segment list using FFmpeg or Replicate cloud models
"""
import logging
import os
import subprocess
import tempfile
import requests
from typing import List, Dict, Any
from config import Config

logger = logging.getLogger(__name__)


class VideoEditor:
    """Cut and encode videos using FFmpeg or Replicate cloud models"""

    def __init__(self):
        self.use_cloud = Config.USE_CLOUD_VIDEO_PROCESSING

        # Only check FFmpeg if not using cloud processing or as fallback
        if not self.use_cloud:
            self._check_ffmpeg()
        else:
            logger.info("Cloud video processing enabled - FFmpeg not required for cutting")
            # Initialize Replicate client if using cloud mode
            try:
                from services.replicate_video_client import ReplicateVideoClient
                self.replicate_client = ReplicateVideoClient()
                logger.info("Replicate video client initialized for video editing")
            except Exception as e:
                logger.warning(f"Failed to initialize Replicate client, falling back to local FFmpeg: {e}")
                self.use_cloud = False
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
            logger.info("FFmpeg is available for video editing")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.error(f"FFmpeg not available: {e}. Video editing will fail.")

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
                f"FFmpeg is required for video editing. {install_msg}. "
                f"For detailed instructions, visit the Video Editor page."
            )

    def cut_video(
        self,
        video_path: str,
        segments_to_keep: List[Dict],
        output_path: str,
        method: str = 'reencode'
    ) -> Dict[str, Any]:
        """
        Cut video based on segment list

        Args:
            video_path: Path to input video
            segments_to_keep: List of segments with start_time, end_time
            output_path: Where to save cut video
            method: 'reencode' (reliable) or 'lossless' (fast but may have issues)

        Returns:
            {
                'success': bool,
                'output_path': str,
                'duration': float,
                'file_size_mb': float,
                'processing_time': float,
                'method': str
            }
        """
        try:
            if not os.path.exists(video_path):
                logger.error(f"Input video not found: {video_path}")
                return {'success': False, 'error': 'Input video not found'}

            if not segments_to_keep:
                logger.error("No segments to keep")
                return {'success': False, 'error': 'No segments to keep'}

            # Sort segments by start time
            segments_sorted = sorted(segments_to_keep, key=lambda s: s['start_time'])

            logger.info(f"Cutting video into {len(segments_sorted)} segments")
            logger.info(f"Method: {'cloud' if self.use_cloud else method}")

            # Route to cloud or local processing
            if self.use_cloud:
                return self._cut_video_cloud(video_path, segments_sorted, output_path)
            elif method == 'reencode':
                return self._cut_video_reencode(video_path, segments_sorted, output_path)
            elif method == 'lossless':
                return self._cut_video_lossless(video_path, segments_sorted, output_path)
            else:
                logger.error(f"Unknown method: {method}")
                return {'success': False, 'error': f'Unknown method: {method}'}

        except Exception as e:
            logger.error(f"Error cutting video: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _cut_video_cloud(
        self,
        video_path: str,
        segments: List[Dict],
        output_path: str
    ) -> Dict[str, Any]:
        """
        Cut video using Replicate cloud models

        Uses lucataco/trim-video + lucataco/video-merge:
        1. Upload video file (or use file path if <100MB)
        2. Trim each segment using trim-video
        3. Merge all trimmed segments using video-merge
        4. Download final merged video

        Pro: No local CPU usage, GPU acceleration, works without FFmpeg
        Con: Requires API token, costs ~$0.20-0.50 per video, requires internet
        """
        import time
        start_time = time.time()

        segment_urls = []

        try:
            logger.info(f"Cloud processing: Trimming {len(segments)} segments with Replicate")

            # Check file size
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

            # For files >80MB, upload to Cloudinary first
            if file_size_mb > Config.REPLICATE_MAX_FILE_SIZE_MB:
                # Check if file exceeds Cloudinary limit (1GB)
                if file_size_mb > Config.CLOUDINARY_MAX_FILE_SIZE_MB:
                    logger.error(f"Video file too large for cloud processing ({file_size_mb:.1f}MB > {Config.CLOUDINARY_MAX_FILE_SIZE_MB}MB)")
                    logger.info("Falling back to local FFmpeg processing")
                    return self._cut_video_reencode(video_path, segments, output_path)

                logger.info(f"File size {file_size_mb:.1f}MB exceeds direct upload limit ({Config.REPLICATE_MAX_FILE_SIZE_MB}MB)")
                logger.info("Uploading to Cloudinary for cloud processing...")

                try:
                    uploader = CloudinaryUploader()

                    # Extract job_id from video_path if available (format: video_{job_id}.ext)
                    job_id = os.path.splitext(os.path.basename(video_path))[0]
                    if job_id.startswith('video_'):
                        job_id = job_id[6:]  # Remove 'video_' prefix

                    # Upload and get URL
                    video_url = uploader.upload_video(video_path, job_id)
                    logger.info(f"Uploaded to Cloudinary: {video_url}")

                except Exception as e:
                    logger.error(f"Cloudinary upload failed: {str(e)}")
                    logger.info("Falling back to local FFmpeg processing")
                    return self._cut_video_reencode(video_path, segments, output_path)
            else:
                # Small files: use direct upload to Replicate
                video_url = video_path
                logger.info(f"File size {file_size_mb:.1f}MB - using direct upload to Replicate")

            # Step 1: Trim each segment
            for i, segment in enumerate(segments):
                start = segment['start_time']
                end = segment['end_time']

                logger.info(f"Trimming segment {i+1}/{len(segments)}: {start:.1f}s - {end:.1f}s")

                try:
                    # If using Cloudinary URL, pass URL directly
                    # If using local file, open and pass file object
                        # Using Cloudinary URL (for files >80MB)
                        trimmed_url = self.replicate_client.trim_video(
                            video_url=video_url,  # Pass Cloudinary URL string
                            start_time=start,
                            end_time=end,
                            output_format="mp4",
                            quality="medium"
                        )
                    else:
                        # Using local file (for files <80MB)
                        with open(video_path, 'rb') as video_file:
                            trimmed_url = self.replicate_client.trim_video(
                                video_url=video_file,  # Pass file object
                                start_time=start,
                                end_time=end,
                                output_format="mp4",
                                quality="medium"
                            )

                    segment_urls.append(trimmed_url)
                    logger.info(f"Segment {i+1} trimmed: {trimmed_url}")

                except Exception as e:
                    logger.error(f"Failed to trim segment {i+1}: {e}")
                    raise

            # Step 2: Merge all segments
            if len(segment_urls) == 1:
                # Only one segment, just download it
                final_video_url = segment_urls[0]
                logger.info("Single segment, skipping merge")
            else:
                logger.info(f"Merging {len(segment_urls)} trimmed segments")
                final_video_url = self.replicate_client.merge_videos(
                    video_urls=segment_urls,
                    output_format="mp4"
                )
                logger.info(f"Segments merged: {final_video_url}")

            # Step 3: Download final video
            logger.info(f"Downloading final video from {final_video_url}")
            response = requests.get(final_video_url, timeout=600)  # 10 min timeout
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(response.content)

            # Verify output
            if not os.path.exists(output_path):
                return {'success': False, 'error': 'Failed to download final video'}

            # Get output file info
            output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            processing_time = time.time() - start_time

            # Calculate total duration
            total_duration = sum(s['end_time'] - s['start_time'] for s in segments)

            logger.info(f"Cloud video processing complete: {output_size_mb:.2f}MB, {processing_time:.1f}s")

            # Cleanup: Delete Cloudinary video after processing
                try:
                    uploader = CloudinaryUploader()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup Cloudinary video: {cleanup_error}")

            return {
                'success': True,
                'output_path': output_path,
                'duration': total_duration,
                'file_size_mb': output_size_mb,
                'processing_time': processing_time,
                'method': 'cloud'
            }

        except Exception as e:
            logger.error(f"Cloud video processing failed: {e}")

            # Cleanup: Delete Cloudinary video even if processing failed
                try:
                    uploader = CloudinaryUploader()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup Cloudinary video: {cleanup_error}")

            logger.info("Falling back to local FFmpeg processing")
            # Fallback to local processing
            return self._cut_video_reencode(video_path, segments, output_path)

    def _cut_video_reencode(
        self,
        video_path: str,
        segments: List[Dict],
        output_path: str
    ) -> Dict[str, Any]:
        """
        Cut and re-encode video (reliable method)

        Uses FFmpeg concat demuxer with re-encoding:
        1. Extract each segment to temp file
        2. Create concat list file
        3. Concatenate and re-encode all segments

        Pro: Reliable, clean cuts, optimized file size
        Con: Slower (5-10 min for large video)
        """
        import time
        start_time = time.time()

        temp_files = []
        try:
            # Step 1: Extract each segment to temp file
            logger.info(f"Extracting {len(segments)} segments...")

            for i, segment in enumerate(segments):
                start = segment['start_time']
                duration = segment['end_time'] - segment['start_time']

                # Create temp file for this segment
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.mp4',
                    delete=False,
                    dir=Config.TEMP_FOLDER
                )
                temp_file.close()
                temp_files.append(temp_file.name)

                # FFmpeg command to extract segment
                # -ss: Start time
                # -t: Duration
                # -c copy: Copy codec (fast extraction)
                command = [
                    'ffmpeg',
                    '-i', video_path,
                    '-ss', str(start),
                    '-t', str(duration),
                    '-c', 'copy',  # Fast copy without re-encoding
                    '-y',
                    temp_file.name
                ]

                logger.debug(f"Extracting segment {i+1}/{len(segments)}: {start:.1f}s - {start+duration:.1f}s")
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,  # 5 min per segment
                    check=True
                )

            # Step 2: Create concat list file
            concat_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.txt',
                delete=False,
                dir=Config.TEMP_FOLDER
            )

            for temp_file in temp_files:
                # Escape path for FFmpeg concat
                escaped_path = temp_file.replace('\\', '/').replace("'", "\\'")
                concat_file.write(f"file '{escaped_path}'\n")

            concat_file.close()
            temp_files.append(concat_file.name)

            logger.info("Concatenating and re-encoding segments...")

            # Step 3: Concatenate and re-encode
            # Uses H.264 codec with good quality/size balance
            command = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file.name,
                '-c:v', 'libx264',  # H.264 video codec
                '-preset', Config.VIDEO_ENCODING_PRESET,  # Encoding speed preset
                '-crf', str(Config.VIDEO_CRF_QUALITY),  # Quality (23 = balanced)
                '-c:a', 'aac',  # AAC audio codec
                '-b:a', '192k',  # Audio bitrate
                '-y',
                output_path
            ]

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=1800,  # 30 min timeout
                check=True
            )

            # Verify output
            if not os.path.exists(output_path):
                return {'success': False, 'error': 'Output file not created'}

            # Get output file info
            output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            processing_time = time.time() - start_time

            # Calculate total duration
            total_duration = sum(s['end_time'] - s['start_time'] for s in segments)

            logger.info(f"Video cut complete: {output_size_mb:.2f}MB, {processing_time:.1f}s")

            return {
                'success': True,
                'output_path': output_path,
                'duration': total_duration,
                'file_size_mb': output_size_mb,
                'processing_time': processing_time,
                'method': 'reencode'
            }

        except subprocess.TimeoutExpired:
            logger.error("Video cutting timed out")
            return {'success': False, 'error': 'Video cutting timed out'}
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode('utf-8', errors='ignore')}")
            return {'success': False, 'error': 'FFmpeg video cutting failed'}
        finally:
            # Clean up temp files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to remove temp file {temp_file}: {e}")

    def _cut_video_lossless(
        self,
        video_path: str,
        segments: List[Dict],
        output_path: str
    ) -> Dict[str, Any]:
        """
        Cut video without re-encoding (fast but may have keyframe issues)

        Uses FFmpeg concat with copy codec:
        - Pro: Very fast (1-2 min)
        - Con: May have keyframe issues, limited to same codec

        Implementation: Same as reencode but uses -c copy in concat step
        """
        import time
        start_time = time.time()

        temp_files = []
        try:
            # Extract segments (same as reencode)
            logger.info(f"Extracting {len(segments)} segments (lossless)...")

            for i, segment in enumerate(segments):
                start = segment['start_time']
                duration = segment['end_time'] - segment['start_time']

                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.mp4',
                    delete=False,
                    dir=Config.TEMP_FOLDER
                )
                temp_file.close()
                temp_files.append(temp_file.name)

                command = [
                    'ffmpeg',
                    '-i', video_path,
                    '-ss', str(start),
                    '-t', str(duration),
                    '-c', 'copy',
                    '-y',
                    temp_file.name
                ]

                subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, check=True)

            # Create concat list
            concat_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.txt',
                delete=False,
                dir=Config.TEMP_FOLDER
            )

            for temp_file in temp_files:
                escaped_path = temp_file.replace('\\', '/').replace("'", "\\'")
                concat_file.write(f"file '{escaped_path}'\n")

            concat_file.close()
            temp_files.append(concat_file.name)

            logger.info("Concatenating segments (lossless copy)...")

            # Concatenate with copy codec (no re-encoding)
            command = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file.name,
                '-c', 'copy',  # Copy without re-encoding
                '-y',
                output_path
            ]

            subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, check=True)

            # Get output info
            output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            processing_time = time.time() - start_time
            total_duration = sum(s['end_time'] - s['start_time'] for s in segments)

            logger.info(f"Lossless cut complete: {output_size_mb:.2f}MB, {processing_time:.1f}s")

            return {
                'success': True,
                'output_path': output_path,
                'duration': total_duration,
                'file_size_mb': output_size_mb,
                'processing_time': processing_time,
                'method': 'lossless'
            }

        except subprocess.TimeoutExpired:
            logger.error("Lossless cutting timed out")
            return {'success': False, 'error': 'Lossless cutting timed out'}
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error in lossless cut: {e.stderr.decode('utf-8', errors='ignore')}")
            return {'success': False, 'error': 'FFmpeg lossless cutting failed'}
        finally:
            # Clean up
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to remove temp file: {e}")
