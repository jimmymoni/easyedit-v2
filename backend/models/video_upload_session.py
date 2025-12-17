"""
Video Upload Session Model for S3 Multipart Uploads

Tracks chunked upload progress, resumability, and completion status.
Follows the same pattern as VideoJob for consistency.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum


class UploadStatus(Enum):
    """Upload session status states"""
    INITIALIZING = 'initializing'  # Creating S3 multipart upload
    UPLOADING = 'uploading'        # Chunks being uploaded
    COMPLETED = 'completed'        # All chunks uploaded and finalized
    ABORTED = 'aborted'            # Upload cancelled
    EXPIRED = 'expired'            # Pre-signed URLs expired
    FAILED = 'failed'              # Upload failed


@dataclass
class VideoUploadSession:
    """
    Represents an S3 multipart upload session.

    This model tracks:
    - S3 multipart upload metadata
    - Chunk completion status
    - Upload progress and timing
    - ETags for multipart completion

    Example:
        >>> session = VideoUploadSession(
        ...     job_id="abc-123",
        ...     upload_id="s3-multipart-id",
        ...     user_id="user_123",
        ...     s3_key="uploads/abc-123/video.mp4",
        ...     bucket="easyedit-videos",
        ...     filename="video.mp4",
        ...     file_size=3221225472,
        ...     total_chunks=308
        ... )
        >>> session.progress
        0.0
    """

    # Core identifiers
    job_id: str                        # Links to VideoJob
    upload_id: str                     # S3 multipart upload ID
    user_id: str                       # User who initiated upload

    # S3 details
    s3_key: str                        # S3 object key
    bucket: str                        # S3 bucket name

    # File information
    filename: str                      # Original filename
    file_size: int                     # Total file size in bytes
    chunk_size: int = 10485760         # Chunk size (10MB default)

    # Upload tracking
    total_chunks: int = 0              # Total number of chunks
    completed_chunks: List[int] = field(default_factory=list)  # Completed part numbers
    etags: Dict[int, str] = field(default_factory=dict)        # part_number -> ETag

    # Status and timing
    status: UploadStatus = UploadStatus.INITIALIZING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0

    # Additional metadata
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        """Ensure status is an UploadStatus enum"""
        if isinstance(self.status, str):
            self.status = UploadStatus(self.status)

    @property
    def progress(self) -> float:
        """Upload progress (0.0 to 1.0)"""
        if self.total_chunks == 0:
            return 0.0
        return len(self.completed_chunks) / self.total_chunks

    @property
    def progress_percent(self) -> int:
        """Upload progress as percentage (0-100)"""
        return int(self.progress * 100)

    @property
    def is_complete(self) -> bool:
        """Check if all chunks are uploaded"""
        return len(self.completed_chunks) == self.total_chunks

    @property
    def missing_chunks(self) -> List[int]:
        """Get list of missing chunk part numbers"""
        all_chunks = set(range(1, self.total_chunks + 1))
        completed = set(self.completed_chunks)
        return sorted(list(all_chunks - completed))

    @property
    def file_size_mb(self) -> float:
        """File size in megabytes"""
        return self.file_size / (1024 * 1024)

    @property
    def file_size_gb(self) -> float:
        """File size in gigabytes"""
        return self.file_size / (1024 * 1024 * 1024)

    @property
    def elapsed_time_seconds(self) -> Optional[int]:
        """Calculate elapsed upload time"""
        if self.created_at is None:
            return None

        end_time = self.completed_at or datetime.now()
        elapsed = end_time - self.created_at
        return int(elapsed.total_seconds())

    def update_status(self, new_status: UploadStatus) -> None:
        """
        Update session status and timestamp.

        Args:
            new_status: New status to set
        """
        self.status = new_status
        self.updated_at = datetime.now()

    def mark_chunk_complete(self, part_number: int, etag: str) -> None:
        """
        Mark a chunk as successfully uploaded.

        Args:
            part_number: Chunk part number (1-based)
            etag: ETag returned by S3 after chunk upload
        """
        if part_number not in self.completed_chunks:
            self.completed_chunks.append(part_number)
            self.completed_chunks.sort()

        self.etags[part_number] = etag
        self.updated_at = datetime.now()

    def mark_complete(self) -> None:
        """Mark upload session as complete"""
        self.status = UploadStatus.COMPLETED
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()

    def mark_failed(self, error_message: str) -> None:
        """
        Mark upload session as failed.

        Args:
            error_message: Error message describing failure
        """
        self.status = UploadStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.now()

    def mark_aborted(self) -> None:
        """Mark upload session as aborted"""
        self.status = UploadStatus.ABORTED
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict:
        """
        Convert VideoUploadSession to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'job_id': self.job_id,
            'upload_id': self.upload_id,
            'user_id': self.user_id,
            's3_key': self.s3_key,
            'bucket': self.bucket,
            'filename': self.filename,
            'file_size': self.file_size,
            'file_size_mb': round(self.file_size_mb, 2),
            'file_size_gb': round(self.file_size_gb, 2),
            'chunk_size': self.chunk_size,
            'total_chunks': self.total_chunks,
            'completed_chunks': self.completed_chunks,
            'progress': self.progress,
            'progress_percent': self.progress_percent,
            'is_complete': self.is_complete,
            'missing_chunks': self.missing_chunks[:10] if len(self.missing_chunks) > 10 else self.missing_chunks,  # Limit for API response
            'missing_chunks_count': len(self.missing_chunks),
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'elapsed_time_seconds': self.elapsed_time_seconds,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'metadata': self.metadata
        }

    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"VideoUploadSession(job_id='{self.job_id}', "
            f"status={self.status.value}, "
            f"filename='{self.filename}', "
            f"progress={self.progress_percent}%, "
            f"chunks={len(self.completed_chunks)}/{self.total_chunks})"
        )
