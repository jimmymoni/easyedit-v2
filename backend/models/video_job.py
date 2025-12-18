"""
Video job data model for Phase 1 implementation.

This module defines the VideoJob dataclass which tracks the complete lifecycle
of a video upload, transcoding, and processing workflow.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class VideoJobStatus(Enum):
    """Status states for video processing jobs"""
    UPLOADING = 'uploading'          # File upload in progress
    UPLOADED = 'uploaded'            # Upload complete, ready for processing
    PROCESSING = 'processing'        # Direct cloud processing (Replicate-only, no transcode)
    TRANSCODING = 'transcoding'      # Transcoding in progress (hybrid mode)
    READY = 'ready'                  # Transcoding complete, proxy available
    ANALYZING = 'analyzing'          # Analysis in progress (transcription + detection)
    ANALYZED = 'analyzed'            # Analysis complete, results available
    FAILED = 'failed'                # Job failed (upload, transcoding, or analysis)
    CANCELLED = 'cancelled'          # Job cancelled by user


@dataclass
class VideoJob:
    """
    Represents a video processing job through its complete lifecycle.

    This model tracks:
    - Original video file information
    - Video metadata (duration, resolution, codec, etc.)
    - Proxy/transcoded video information
    - Transcoding progress and status
    - Timestamps for all lifecycle events

    Example:
        >>> job = VideoJob(
        ...     job_id="abc-123",
        ...     user_id="user_123",
        ...     original_filename="my_video.mp4"
        ... )
        >>> job.status
        <VideoJobStatus.UPLOADING: 'uploading'>
    """

    # Core identifiers
    job_id: str
    user_id: str
    status: VideoJobStatus = VideoJobStatus.UPLOADING

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Original file information
    original_filename: str = ""
    original_path: str = ""
    original_size_bytes: int = 0
    original_format: str = ""

    # Video metadata (extracted from ffprobe)
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""
    bitrate: int = 0
    has_audio: bool = False

    # Proxy file information
    proxy_path: Optional[str] = None
    proxy_size_bytes: Optional[int] = None
    proxy_url: Optional[str] = None

    # Waveform data (Phase 2.2.1)
    waveform_status: str = 'pending'  # pending | generating | ready | failed
    waveform_file: Optional[str] = None  # Path to cached waveform JSON
    waveform_samples: int = 1500  # Number of waveform samples
    waveform_duration: Optional[float] = None  # Audio duration in seconds
    waveform_error: Optional[str] = None  # Error message if waveform generation failed

    # Transcoding progress tracking
    transcode_progress: float = 0.0  # 0.0 to 1.0 (0% to 100%)
    transcode_started_at: Optional[datetime] = None
    transcode_completed_at: Optional[datetime] = None
    transcode_error: Optional[str] = None
    estimated_transcode_time_seconds: Optional[int] = None

    # Analysis data (Phase 2: Cloud Result Loop)
    transcription: Optional[Dict] = None  # Full transcription from Whisper
    analysis: Optional[Dict] = None  # Repeated take detection results
    analysis_started_at: Optional[datetime] = None
    analysis_completed_at: Optional[datetime] = None
    error_message: Optional[str] = None  # General error message (transcoding or analysis)

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure status is a VideoJobStatus enum"""
        if isinstance(self.status, str):
            self.status = VideoJobStatus(self.status)

    @property
    def file_size_mb(self) -> float:
        """Original file size in megabytes"""
        return self.original_size_bytes / (1024 * 1024)

    @property
    def proxy_size_mb(self) -> Optional[float]:
        """Proxy file size in megabytes"""
        if self.proxy_size_bytes is None:
            return None
        return self.proxy_size_bytes / (1024 * 1024)

    @property
    def transcode_progress_percent(self) -> int:
        """Transcoding progress as integer percentage (0-100)"""
        return int(self.transcode_progress * 100)

    @property
    def resolution(self) -> str:
        """Video resolution as string (e.g., "1920x1080")"""
        return f"{self.width}x{self.height}"

    @property
    def is_transcoding_complete(self) -> bool:
        """Check if transcoding is complete"""
        return self.status == VideoJobStatus.READY

    @property
    def is_failed(self) -> bool:
        """Check if job has failed"""
        return self.status == VideoJobStatus.FAILED

    @property
    def proxy_ready(self) -> bool:
        """Check if proxy video is ready for playback"""
        return (
            self.status == VideoJobStatus.READY and
            self.proxy_path is not None and
            self.proxy_url is not None
        )

    @property
    def waveform_ready(self) -> bool:
        """Check if waveform is ready for timeline visualization"""
        return (
            self.waveform_status == 'ready' and
            self.waveform_file is not None
        )

    @property
    def elapsed_transcode_time_seconds(self) -> Optional[int]:
        """Calculate elapsed transcoding time"""
        if self.transcode_started_at is None:
            return None

        end_time = self.transcode_completed_at or datetime.now()
        elapsed = end_time - self.transcode_started_at
        return int(elapsed.total_seconds())

    @property
    def estimated_time_remaining_seconds(self) -> Optional[int]:
        """Estimate remaining transcoding time based on progress"""
        if (
            self.transcode_progress == 0 or
            self.transcode_started_at is None or
            self.status != VideoJobStatus.TRANSCODING
        ):
            return None

        elapsed = self.elapsed_transcode_time_seconds
        if elapsed is None or elapsed == 0:
            return None

        # Calculate based on current progress
        total_estimated = elapsed / self.transcode_progress
        remaining = total_estimated - elapsed
        return max(0, int(remaining))

    def update_status(self, new_status: VideoJobStatus) -> None:
        """
        Update job status and timestamp.

        Args:
            new_status: New status to set
        """
        self.status = new_status
        self.updated_at = datetime.now()

    def start_transcoding(self) -> None:
        """Mark transcoding as started"""
        self.status = VideoJobStatus.TRANSCODING
        self.transcode_started_at = datetime.now()
        self.updated_at = datetime.now()

    def complete_transcoding(self, proxy_path: str, proxy_size_bytes: int, proxy_url: str) -> None:
        """
        Mark transcoding as complete.

        Args:
            proxy_path: Path to proxy video file
            proxy_size_bytes: Size of proxy file in bytes
            proxy_url: URL to access proxy video
        """
        self.status = VideoJobStatus.READY
        self.transcode_progress = 1.0
        self.transcode_completed_at = datetime.now()
        self.proxy_path = proxy_path
        self.proxy_size_bytes = proxy_size_bytes
        self.proxy_url = proxy_url
        self.updated_at = datetime.now()

    def fail_transcoding(self, error_message: str) -> None:
        """
        Mark transcoding as failed.

        Args:
            error_message: Error message describing failure
        """
        self.status = VideoJobStatus.FAILED
        self.transcode_error = error_message
        self.updated_at = datetime.now()

    def update_transcode_progress(self, progress: float) -> None:
        """
        Update transcoding progress.

        Args:
            progress: Progress value between 0.0 and 1.0
        """
        self.transcode_progress = max(0.0, min(1.0, progress))
        self.updated_at = datetime.now()

    def start_cloud_processing(self) -> None:
        """Mark direct cloud processing started (Replicate-only mode, no transcoding)"""
        self.status = VideoJobStatus.PROCESSING
        self.updated_at = datetime.now()

    def start_analysis(self) -> None:
        """Mark analysis as started (transcription + repeated take detection)"""
        self.status = VideoJobStatus.ANALYZING
        self.analysis_started_at = datetime.now()
        self.updated_at = datetime.now()

    def complete_analysis(self, transcription: Dict, analysis: Dict) -> None:
        """
        Mark analysis as complete and store results.

        Args:
            transcription: Full transcription data from Whisper
            analysis: Repeated take detection results (segments, stats, patterns)
        """
        self.transcription = transcription
        self.analysis = analysis
        self.analysis_completed_at = datetime.now()
        self.status = VideoJobStatus.ANALYZED
        self.updated_at = datetime.now()

    def fail_analysis(self, error: str) -> None:
        """
        Mark analysis as failed.

        Args:
            error: Error message describing failure
        """
        self.error_message = error
        self.status = VideoJobStatus.FAILED
        self.updated_at = datetime.now()

    def mark_waveform_generating(self) -> None:
        """Mark waveform generation as in progress"""
        self.waveform_status = 'generating'
        self.updated_at = datetime.now()

    def mark_waveform_ready(self, waveform_file: str, duration: float) -> None:
        """
        Mark waveform generation as complete.

        Args:
            waveform_file: Path to cached waveform JSON file
            duration: Audio duration in seconds
        """
        self.waveform_status = 'ready'
        self.waveform_file = waveform_file
        self.waveform_duration = duration
        self.waveform_error = None
        self.updated_at = datetime.now()

    def mark_waveform_failed(self, error_message: str) -> None:
        """
        Mark waveform generation as failed.

        Args:
            error_message: Error message describing failure
        """
        self.waveform_status = 'failed'
        self.waveform_error = error_message
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert VideoJob to dictionary for API responses.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'job_id': self.job_id,
            'user_id': self.user_id,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),

            # Original file
            'original_filename': self.original_filename,
            'original_size_bytes': self.original_size_bytes,
            'file_size_mb': round(self.file_size_mb, 2),
            'original_format': self.original_format,

            # Video metadata
            'duration_seconds': self.duration_seconds,
            'resolution': self.resolution,
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'codec': self.codec,
            'bitrate': self.bitrate,
            'has_audio': self.has_audio,

            # Proxy
            'proxy_ready': self.proxy_ready,
            'proxy_url': self.proxy_url,
            'proxy_size_mb': round(self.proxy_size_mb, 2) if self.proxy_size_mb else None,

            # Waveform (Phase 2.2.1)
            'waveform_status': self.waveform_status,
            'waveform_ready': self.waveform_ready,
            'waveform_samples': self.waveform_samples,
            'waveform_duration': self.waveform_duration,
            'waveform_error': self.waveform_error,

            # Transcoding
            'transcode_progress': self.transcode_progress,
            'transcode_progress_percent': self.transcode_progress_percent,
            'transcode_started_at': self.transcode_started_at.isoformat() if self.transcode_started_at else None,
            'transcode_completed_at': self.transcode_completed_at.isoformat() if self.transcode_completed_at else None,
            'transcode_error': self.transcode_error,
            'estimated_transcode_time_seconds': self.estimated_transcode_time_seconds,
            'estimated_time_remaining_seconds': self.estimated_time_remaining_seconds,
            'elapsed_transcode_time_seconds': self.elapsed_transcode_time_seconds,

            # Additional metadata
            'metadata': self.metadata,
        }

    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"VideoJob(job_id='{self.job_id}', "
            f"status={self.status.value}, "
            f"filename='{self.original_filename}', "
            f"progress={self.transcode_progress_percent}%)"
        )
