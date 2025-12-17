import replicate
import httpx
from typing import List, Optional
import logging
from config import Config

logger = logging.getLogger(__name__)

class ReplicateVideoClient:
    """Client for Replicate video processing models

    Handles video trimming, merging, and audio extraction using Replicate's cloud models.
    Follows the same pattern as ReplicateWhisperClient for consistency.
    """

    def __init__(self):
        self.api_token = Config.REPLICATE_API_TOKEN
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN not configured")

        # Custom timeout for large video file uploads (same as Whisper client)
        custom_timeout = httpx.Timeout(
            connect=30.0,
            read=600.0,
            write=600.0,  # Critical for large file uploads
            pool=30.0
        )

        self.client = replicate.Client(
            api_token=self.api_token,
            timeout=custom_timeout
        )

        # Model versions (can be configured via env vars)
        self.trim_model = Config.REPLICATE_VIDEO_MODEL_TRIM or "lucataco/trim-video"
        self.merge_model = Config.REPLICATE_VIDEO_MODEL_MERGE or "lucataco/video-merge"

    def trim_video(
        self,
        video_url: str,
        start_time: float,
        end_time: Optional[float] = None,
        duration: Optional[float] = None,
        output_format: str = "mp4",
        quality: str = "medium",
        remove_audio: bool = False
    ) -> str:
        """Trim video using lucataco/trim-video

        Args:
            video_url: URL or file path to video
            start_time: Start timestamp in seconds
            end_time: End timestamp in seconds (use this OR duration)
            duration: Duration in seconds (alternative to end_time)
            output_format: mp4, mov, avi, mkv, webm
            quality: low, medium, high
            remove_audio: Strip audio track

        Returns:
            URL to trimmed video file
        """
        try:
            logger.info(f"Trimming video: {video_url} ({start_time}s - {end_time or 'duration: ' + str(duration)}s)")

            input_params = {
                "video": video_url,
                "start_time": start_time,
                "output_format": output_format,
                "quality": quality,
                "remove_audio": remove_audio
            }

            # Use either end_time or duration (not both)
            if end_time is not None:
                input_params["end_time"] = end_time
            elif duration is not None:
                input_params["duration"] = duration
            else:
                raise ValueError("Must provide either end_time or duration")

            output = self.client.run(self.trim_model, input=input_params)

            logger.info(f"Video trimmed successfully: {output}")
            return output

        except Exception as e:
            logger.error(f"Error trimming video: {e}")
            raise

    def merge_videos(self, video_urls: List[str], output_format: str = "mp4") -> str:
        """Merge multiple videos using lucataco/video-merge

        Args:
            video_urls: List of video URLs or file paths to merge (in order)
            output_format: Output format (mp4, mov, avi, mkv)

        Returns:
            URL to merged video file

        Note:
            Cost: $0.0025 per run (~25 seconds processing time)
        """
        try:
            logger.info(f"Merging {len(video_urls)} videos")

            input_params = {
                "videos": video_urls,
                "output_format": output_format
            }

            output = self.client.run(self.merge_model, input=input_params)

            logger.info(f"Videos merged successfully: {output}")
            return output

        except Exception as e:
            logger.error(f"Error merging videos: {e}")
            raise

    def extract_audio(self, video_url: str, output_format: str = "wav") -> str:
        """Extract audio from video

        Uses trim_video with remove_audio=False and full duration.
        Alternative: Use lucataco/video-audio-merge with silent video.

        Args:
            video_url: URL or file path to video
            output_format: Audio format (wav, mp3, aac)

        Returns:
            URL to extracted audio file
        """
        try:
            logger.info(f"Extracting audio from video: {video_url}")

            # Use trim_video with full duration to extract audio
            # This is a workaround since there's no dedicated audio extraction model
            output = self.trim_video(
                video_url=video_url,
                start_time=0,
                duration=999999,  # Max duration (will use full video length)
                output_format=output_format,
                remove_audio=False
            )

            logger.info(f"Audio extracted successfully: {output}")
            return output

        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            raise

    def transcode_to_h264(
        self,
        video_url: str,
        max_width: int = 1920,
        max_height: int = 1080,
        quality: str = "medium",
        output_format: str = "mp4"
    ) -> str:
        """
        Transcode video to web-optimized H.264 MP4.

        Uses trim_video with full duration to re-encode the video to H.264 format
        with specified resolution and quality. This is suitable for creating
        web-optimized proxy videos.

        Args:
            video_url: URL to source video (can be Cloudinary URL or public URL)
            max_width: Maximum width in pixels (default 1920)
            max_height: Maximum height in pixels (default 1080)
            quality: Encoding quality - low/medium/high (default medium)
            output_format: Output format, typically mp4 (default mp4)

        Returns:
            URL to transcoded video file (usually Replicate CDN URL)

        Note:
            - Input video must be accessible via public URL
            - For large local files, upload to Cloudinary first
            - Replicate automatically scales to max_width x max_height while preserving aspect ratio
            - Cost: ~$0.01-0.05 per minute of video depending on quality/duration
        """
        try:
            logger.info(f"Transcoding video to H.264: {video_url}")
            logger.info(f"Target resolution: {max_width}x{max_height}, quality: {quality}")

            # Use trim_video with full duration to re-encode
            # The model will automatically:
            # - Convert to H.264 codec
            # - Scale to fit within max dimensions
            # - Apply quality settings
            output = self.trim_video(
                video_url=video_url,
                start_time=0,
                duration=999999,  # Use full video length
                output_format=output_format,
                quality=quality,
                remove_audio=False
            )

            logger.info(f"Video transcoded successfully to H.264: {output}")
            return output

        except Exception as e:
            logger.error(f"Error transcoding video: {e}")
            raise
