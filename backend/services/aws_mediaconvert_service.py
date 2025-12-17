"""
AWS MediaConvert Service - Cloud Video Transcoding

This service handles video transcoding using AWS Elemental MediaConvert.
Replaces local FFmpeg transcoding with GPU-accelerated cloud processing.

Operations:
- Video transcoding to web-optimized H.264/AAC MP4
- Automatic endpoint discovery
- Job status monitoring
- S3 integration for input/output

Cost: ~$0.0075/minute (~$0.90 per 2-hour video)
"""

import boto3
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from config import Config
import time

logger = logging.getLogger(__name__)


class AWSMediaConvertService:
    """
    AWS MediaConvert service for cloud-based video transcoding.
    """

    def __init__(self):
        """Initialize AWS MediaConvert client"""
        if not Config.AWS_ACCESS_KEY_ID or not Config.AWS_SECRET_ACCESS_KEY:
            raise ValueError("AWS credentials not configured in .env")

        self.region = Config.AWS_REGION
        self.bucket = Config.S3_VIDEO_BUCKET
        self.role_arn = Config.AWS_MEDIACONVERT_ROLE_ARN
        self.queue = Config.AWS_MEDIACONVERT_QUEUE

        # Discover MediaConvert endpoint if not provided
        self.endpoint_url = Config.AWS_MEDIACONVERT_ENDPOINT
        if not self.endpoint_url:
            self.endpoint_url = self._discover_endpoint()

        # Create MediaConvert client
        self.client = boto3.client(
            'mediaconvert',
            region_name=self.region,
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            endpoint_url=self.endpoint_url
        )

        logger.info(f"AWS MediaConvert initialized: {self.endpoint_url}")

    def _discover_endpoint(self) -> str:
        """
        Discover account-specific MediaConvert endpoint.
        Required for creating jobs.

        Returns:
            str: MediaConvert endpoint URL
        """
        try:
            # Create temporary client to discover endpoint
            temp_client = boto3.client(
                'mediaconvert',
                region_name=self.region,
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY
            )

            response = temp_client.describe_endpoints()
            endpoint = response['Endpoints'][0]['Url']

            logger.info(f"Discovered MediaConvert endpoint: {endpoint}")
            return endpoint

        except Exception as e:
            logger.error(f"Failed to discover MediaConvert endpoint: {e}")
            raise

    def transcode_video(
        self,
        input_s3_key: str,
        output_s3_prefix: str,
        max_width: int = 1920,
        max_height: int = 1080,
        video_bitrate: int = 5000000,  # 5 Mbps
        audio_bitrate: int = 128000,   # 128 kbps
        preset: str = "GOOD",  # GOOD, BETTER, BEST quality
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Transcode video to web-optimized H.264/AAC MP4 using AWS MediaConvert.

        Args:
            input_s3_key: S3 key to source video (e.g., "original/job-123/video.mp4")
            output_s3_prefix: S3 prefix for output (e.g., "proxy/job-123/")
            max_width: Maximum width (default 1920 for Full HD)
            max_height: Maximum height (default 1080)
            video_bitrate: Target video bitrate in bps (default 5 Mbps)
            audio_bitrate: Target audio bitrate in bps (default 128 kbps)
            preset: Quality preset (GOOD, BETTER, BEST)
            progress_callback: Optional callback(percent) for progress updates

        Returns:
            {
                'job_id': 'aws-mediaconvert-job-id',
                'status': 'SUBMITTED',
                'output_s3_key': 'proxy/job-123/video.mp4',
                'output_url': 'https://s3.amazonaws.com/...'
            }

        Raises:
            ValueError: If IAM role not configured
            ClientError: If AWS API call fails
        """
        if not self.role_arn:
            raise ValueError(
                "AWS_MEDIACONVERT_ROLE_ARN not configured. "
                "Create IAM role with MediaConvert and S3 permissions"
            )

        try:
            logger.info(f"Starting MediaConvert transcode: s3://{self.bucket}/{input_s3_key}")

            # Build S3 URLs
            input_url = f"s3://{self.bucket}/{input_s3_key}"
            output_url = f"s3://{self.bucket}/{output_s3_prefix}"

            # Create job settings
            job_settings = self._build_job_settings(
                input_url=input_url,
                output_url=output_url,
                max_width=max_width,
                max_height=max_height,
                video_bitrate=video_bitrate,
                audio_bitrate=audio_bitrate,
                preset=preset
            )

            # Submit job
            response = self.client.create_job(
                Role=self.role_arn,
                Settings=job_settings,
                Queue=self.queue,
                UserMetadata={
                    'input_key': input_s3_key,
                    'output_prefix': output_s3_prefix
                }
            )

            job_id = response['Job']['Id']
            status = response['Job']['Status']

            logger.info(f"MediaConvert job created: {job_id} (status: {status})")

            # Build expected output key
            output_s3_key = f"{output_s3_prefix}video.mp4"
            output_public_url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{output_s3_key}"

            return {
                'job_id': job_id,
                'status': status,
                'output_s3_key': output_s3_key,
                'output_url': output_public_url
            }

        except ClientError as e:
            logger.error(f"AWS MediaConvert error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating MediaConvert job: {e}")
            raise

    def _build_job_settings(
        self,
        input_url: str,
        output_url: str,
        max_width: int,
        max_height: int,
        video_bitrate: int,
        audio_bitrate: int,
        preset: str
    ) -> Dict[str, Any]:
        """
        Build MediaConvert job settings for H.264 transcoding.

        This creates a job that outputs web-optimized MP4 with:
        - H.264 video codec (baseline profile for compatibility)
        - AAC audio codec
        - Progressive scan (no interlacing)
        - Fast start enabled (moov atom at beginning)
        - Automatic scaling to fit max dimensions

        Args:
            input_url: S3 URL to source video
            output_url: S3 URL prefix for output
            max_width: Maximum output width
            max_height: Maximum output height
            video_bitrate: Target video bitrate
            audio_bitrate: Target audio bitrate
            preset: Quality preset (GOOD, BETTER, BEST)

        Returns:
            Dict: MediaConvert job settings
        """
        # Map preset to H.264 quality tuning
        quality_tuning_level = {
            "GOOD": "SINGLE_PASS",
            "BETTER": "SINGLE_PASS_HQ",
            "BEST": "MULTI_PASS_HQ"
        }.get(preset, "SINGLE_PASS_HQ")

        job_settings = {
            "Inputs": [
                {
                    "FileInput": input_url,
                    "VideoSelector": {},
                    "AudioSelectors": {
                        "Audio Selector 1": {
                            "DefaultSelection": "DEFAULT"
                        }
                    }
                }
            ],
            "OutputGroups": [
                {
                    "Name": "File Group",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": output_url
                        }
                    },
                    "Outputs": [
                        {
                            "NameModifier": "video",
                            "ContainerSettings": {
                                "Container": "MP4",
                                "Mp4Settings": {
                                    "MoovPlacement": "PROGRESSIVE_DOWNLOAD"  # Fast start
                                }
                            },
                            "VideoDescription": {
                                "Width": max_width,
                                "Height": max_height,
                                "ScalingBehavior": "DEFAULT",  # Fit within dimensions
                                "CodecSettings": {
                                    "Codec": "H_264",
                                    "H264Settings": {
                                        "Profile": "BASELINE",  # Maximum compatibility
                                        "Level": "AUTO",
                                        "RateControlMode": "VBR",
                                        "Bitrate": video_bitrate,
                                        "QualityTuningLevel": quality_tuning_level,
                                        "CodecProfile": "BASELINE",
                                        "GopSize": 90.0,  # 3 seconds at 30fps
                                        "GopSizeUnits": "FRAMES",
                                        "NumberBFramesBetweenReferenceFrames": 2,
                                        "SlowPal": "DISABLED",
                                        "Softness": 0,
                                        "FieldEncoding": "PAFF",
                                        "Telecine": "NONE"
                                    }
                                }
                            },
                            "AudioDescriptions": [
                                {
                                    "AudioSourceName": "Audio Selector 1",
                                    "CodecSettings": {
                                        "Codec": "AAC",
                                        "AacSettings": {
                                            "Bitrate": audio_bitrate,
                                            "CodingMode": "CODING_MODE_2_0",  # Stereo
                                            "SampleRate": 48000,  # 48kHz for video
                                            "RateControlMode": "CBR",
                                            "CodecProfile": "LC",  # Low Complexity profile
                                            "RawFormat": "NONE"
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        return job_settings

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get MediaConvert job status.

        Args:
            job_id: MediaConvert job ID

        Returns:
            {
                'status': 'SUBMITTED|PROGRESSING|COMPLETE|ERROR|CANCELED',
                'progress_percent': 75,
                'error_message': 'Error details if failed',
                'output_url': 'https://... (if complete)'
            }
        """
        try:
            response = self.client.get_job(Id=job_id)
            job = response['Job']

            status = job['Status']
            progress = job.get('JobPercentComplete', 0)

            result = {
                'status': status,
                'progress_percent': progress
            }

            # Add error details if failed
            if status == 'ERROR':
                result['error_message'] = job.get('ErrorMessage', 'Unknown error')

            # Add output URL if complete
            if status == 'COMPLETE':
                # Extract output path from job settings
                outputs = job['Settings']['OutputGroups'][0]['Outputs']
                if outputs:
                    # Output URL is in UserMetadata
                    metadata = job.get('UserMetadata', {})
                    output_prefix = metadata.get('output_prefix', '')
                    result['output_s3_key'] = f"{output_prefix}video.mp4"
                    result['output_url'] = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{result['output_s3_key']}"

            return result

        except ClientError as e:
            logger.error(f"Error getting job status: {e}")
            raise

    def wait_for_completion(
        self,
        job_id: str,
        poll_interval: int = 10,
        timeout: int = 3600,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Wait for MediaConvert job to complete.

        Args:
            job_id: MediaConvert job ID
            poll_interval: Seconds between status checks (default 10)
            timeout: Maximum seconds to wait (default 3600 = 1 hour)
            progress_callback: Optional callback(percent) for progress updates

        Returns:
            Dict: Final job status

        Raises:
            TimeoutError: If job doesn't complete within timeout
            RuntimeError: If job fails
        """
        start_time = time.time()

        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"MediaConvert job {job_id} timed out after {timeout}s")

            # Get job status
            status_result = self.get_job_status(job_id)
            status = status_result['status']
            progress = status_result['progress_percent']

            logger.info(f"MediaConvert job {job_id}: {status} ({progress}%)")

            # Call progress callback
            if progress_callback:
                progress_callback(progress)

            # Check terminal states
            if status == 'COMPLETE':
                logger.info(f"MediaConvert job {job_id} completed successfully")
                return status_result
            elif status == 'ERROR':
                error_msg = status_result.get('error_message', 'Unknown error')
                logger.error(f"MediaConvert job {job_id} failed: {error_msg}")
                raise RuntimeError(f"MediaConvert job failed: {error_msg}")
            elif status == 'CANCELED':
                logger.warning(f"MediaConvert job {job_id} was canceled")
                raise RuntimeError("MediaConvert job was canceled")

            # Wait before next poll
            time.sleep(poll_interval)
