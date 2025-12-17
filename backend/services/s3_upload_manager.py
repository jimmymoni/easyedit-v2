"""
S3 Multipart Upload Manager for Large Video Files

Handles:
- AWS S3 multipart upload initiation
- Pre-signed URL generation for direct client uploads
- Chunk completion tracking with Redis/file storage
- Upload session resumption
- Multipart upload finalization and cleanup
"""

import logging
import boto3
import json
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from config import Config

logger = logging.getLogger(__name__)


class S3UploadManager:
    """
    Manages S3 multipart uploads for large video files.

    Features:
    - Direct client-to-S3 uploads (no backend buffering)
    - Pre-signed URLs with configurable expiration
    - Chunk completion tracking (Redis or file-based)
    - Resume support after network failures
    - Automatic cleanup of incomplete uploads
    """

    def __init__(self, redis_client=None):
        """
        Initialize S3 client and storage backend.

        Args:
            redis_client: Optional Redis client for tracking upload state.
                         Falls back to file-based storage if None.
        """
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
        )
        self.bucket = Config.S3_VIDEO_BUCKET
        self.redis_client = redis_client

        # Storage directory for upload session metadata (fallback)
        self.upload_sessions_dir = os.path.join(
            os.path.dirname(__file__),
            '..',
            'upload_sessions'
        )
        os.makedirs(self.upload_sessions_dir, exist_ok=True)

        logger.info(f"S3UploadManager initialized for bucket: {self.bucket}")

    def initialize_multipart_upload(
        self,
        job_id: str,
        filename: str,
        file_size: int,
        chunk_size: int = 10485760  # 10MB default
    ) -> Dict:
        """
        Initialize S3 multipart upload and generate pre-signed URLs for each chunk.

        Args:
            job_id: Unique job identifier (from VideoJob)
            filename: Original filename (sanitized)
            file_size: Total file size in bytes
            chunk_size: Size of each chunk in bytes (default 10MB)

        Returns:
            Dict with:
            - upload_id: S3 multipart upload ID
            - upload_session_id: Internal session ID (job_id)
            - s3_key: S3 object key
            - total_chunks: Number of chunks
            - chunk_urls: List of pre-signed URLs for each chunk
            - expires_at: ISO timestamp when URLs expire

        Raises:
            Exception: If S3 initialization fails
        """
        try:
            # Generate S3 key with job_id prefix
            s3_key = f"uploads/{job_id}/{filename}"

            # Calculate number of chunks
            total_chunks = (file_size + chunk_size - 1) // chunk_size

            logger.info(
                f"Initializing multipart upload: job={job_id}, "
                f"file_size={file_size / (1024**3):.2f}GB, "
                f"chunks={total_chunks}"
            )

            # Initiate multipart upload on S3
            response = self.s3_client.create_multipart_upload(
                Bucket=self.bucket,
                Key=s3_key,
                ContentType='video/mp4',  # Default, will be updated on completion
                Metadata={
                    'job_id': job_id,
                    'original_filename': filename,
                    'file_size': str(file_size),
                    'uploaded_at': datetime.now().isoformat()
                }
            )

            upload_id = response['UploadId']

            # Generate pre-signed URLs for each chunk
            chunk_urls = []
            url_expiration = Config.S3_PRESIGNED_URL_EXPIRATION  # 24 hours default

            for chunk_number in range(1, total_chunks + 1):
                presigned_url = self.s3_client.generate_presigned_url(
                    'upload_part',
                    Params={
                        'Bucket': self.bucket,
                        'Key': s3_key,
                        'UploadId': upload_id,
                        'PartNumber': chunk_number
                    },
                    ExpiresIn=url_expiration
                )

                chunk_urls.append({
                    'part_number': chunk_number,
                    'upload_url': presigned_url,
                    'chunk_index': chunk_number - 1,  # 0-based for frontend
                    'start_byte': (chunk_number - 1) * chunk_size,
                    'end_byte': min(chunk_number * chunk_size, file_size) - 1,
                    'size': min(chunk_size, file_size - (chunk_number - 1) * chunk_size)
                })

            expires_at = datetime.now() + timedelta(seconds=url_expiration)

            # Store upload session metadata
            session_data = {
                'job_id': job_id,
                'upload_id': upload_id,
                's3_key': s3_key,
                'filename': filename,
                'file_size': file_size,
                'chunk_size': chunk_size,
                'total_chunks': total_chunks,
                'completed_chunks': [],  # Track completed part numbers
                'etags': {},  # Map part_number -> ETag
                'status': 'uploading',
                'created_at': datetime.now().isoformat(),
                'expires_at': expires_at.isoformat()
            }

            self._store_session(job_id, session_data)

            logger.info(
                f"Multipart upload initialized: upload_id={upload_id}, "
                f"chunks={total_chunks}, expires_at={expires_at.isoformat()}"
            )

            return {
                'upload_id': upload_id,
                'upload_session_id': job_id,
                's3_key': s3_key,
                'total_chunks': total_chunks,
                'chunk_urls': chunk_urls,
                'expires_at': expires_at.isoformat(),
                'chunk_size': chunk_size
            }

        except ClientError as e:
            logger.error(f"S3 multipart upload initialization failed: {e}")
            raise Exception(f"Failed to initialize S3 upload: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error initializing upload: {e}")
            raise

    def mark_chunk_complete(
        self,
        job_id: str,
        part_number: int,
        etag: str
    ) -> Dict:
        """
        Mark a chunk as successfully uploaded.

        Args:
            job_id: Upload session ID
            part_number: Chunk part number (1-based)
            etag: ETag returned by S3 after chunk upload

        Returns:
            Dict with:
            - completed_chunks: List of completed part numbers
            - total_chunks: Total number of chunks
            - progress: Progress percentage (0.0 to 1.0)
            - is_complete: Boolean indicating if all chunks are uploaded
        """
        session = self._get_session(job_id)
        if not session:
            raise ValueError(f"Upload session {job_id} not found")

        # Add to completed chunks if not already present
        if part_number not in session['completed_chunks']:
            session['completed_chunks'].append(part_number)
            session['completed_chunks'].sort()

        # Store ETag (required for multipart completion)
        session['etags'][str(part_number)] = etag
        session['updated_at'] = datetime.now().isoformat()

        # Update session
        self._store_session(job_id, session)

        completed = len(session['completed_chunks'])
        total = session['total_chunks']
        progress = completed / total
        is_complete = completed == total

        logger.info(
            f"Chunk complete: job={job_id}, part={part_number}, "
            f"progress={progress*100:.1f}% ({completed}/{total})"
        )

        return {
            'completed_chunks': session['completed_chunks'],
            'total_chunks': total,
            'progress': progress,
            'is_complete': is_complete
        }

    def complete_multipart_upload(self, job_id: str) -> str:
        """
        Finalize S3 multipart upload after all chunks are uploaded.

        Args:
            job_id: Upload session ID

        Returns:
            S3 object URL (s3://bucket/key format)

        Raises:
            ValueError: If upload session not found or incomplete
            Exception: If S3 completion fails
        """
        session = self._get_session(job_id)
        if not session:
            raise ValueError(f"Upload session {job_id} not found")

        # Verify all chunks are uploaded
        if len(session['completed_chunks']) != session['total_chunks']:
            missing = set(range(1, session['total_chunks'] + 1)) - set(session['completed_chunks'])
            raise ValueError(
                f"Upload incomplete: {len(missing)} chunks missing: {sorted(list(missing))[:10]}"
            )

        try:
            # Build parts list for S3 (must be sorted by part number)
            parts = []
            for part_num in sorted(session['completed_chunks']):
                etag = session['etags'].get(str(part_num))
                if not etag:
                    raise ValueError(f"Missing ETag for part {part_num}")

                parts.append({
                    'PartNumber': part_num,
                    'ETag': etag
                })

            # Complete multipart upload
            response = self.s3_client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=session['s3_key'],
                UploadId=session['upload_id'],
                MultipartUpload={'Parts': parts}
            )

            s3_url = f"s3://{self.bucket}/{session['s3_key']}"

            # Update session status
            session['status'] = 'completed'
            session['completed_at'] = datetime.now().isoformat()
            session['s3_url'] = s3_url
            session['s3_etag'] = response.get('ETag')
            self._store_session(job_id, session)

            logger.info(f"Multipart upload completed: job={job_id}, url={s3_url}")

            return s3_url

        except ClientError as e:
            logger.error(f"Failed to complete multipart upload: {e}")
            raise Exception(f"Failed to complete S3 upload: {str(e)}")

    def abort_multipart_upload(self, job_id: str) -> bool:
        """
        Abort and cleanup an incomplete multipart upload.

        Args:
            job_id: Upload session ID

        Returns:
            True if aborted successfully, False otherwise
        """
        session = self._get_session(job_id)
        if not session:
            logger.warning(f"Cannot abort: session {job_id} not found")
            return False

        try:
            self.s3_client.abort_multipart_upload(
                Bucket=self.bucket,
                Key=session['s3_key'],
                UploadId=session['upload_id']
            )

            # Update session status
            session['status'] = 'aborted'
            session['aborted_at'] = datetime.now().isoformat()
            self._store_session(job_id, session)

            logger.info(f"Multipart upload aborted: job={job_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to abort multipart upload: {e}")
            return False

    def get_upload_status(self, job_id: str) -> Optional[Dict]:
        """
        Get current upload session status and progress.

        Args:
            job_id: Upload session ID

        Returns:
            Dict with session details or None if not found
        """
        return self._get_session(job_id)

    def list_incomplete_uploads(self, max_age_hours: int = 48) -> List[Dict]:
        """
        List incomplete multipart uploads older than specified age.
        Useful for cleanup of stale uploads.

        Args:
            max_age_hours: Maximum age in hours (default 48)

        Returns:
            List of incomplete upload sessions
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

            response = self.s3_client.list_multipart_uploads(
                Bucket=self.bucket,
                Prefix='uploads/'
            )

            incomplete = []
            for upload in response.get('Uploads', []):
                if upload['Initiated'].replace(tzinfo=None) < cutoff_time:
                    incomplete.append({
                        'upload_id': upload['UploadId'],
                        'key': upload['Key'],
                        'initiated': upload['Initiated'].isoformat()
                    })

            logger.info(f"Found {len(incomplete)} stale uploads older than {max_age_hours}h")
            return incomplete

        except ClientError as e:
            logger.error(f"Failed to list incomplete uploads: {e}")
            return []

    def cleanup_stale_uploads(self, max_age_hours: int = 48) -> int:
        """
        Cleanup incomplete uploads older than specified age.

        Args:
            max_age_hours: Maximum age in hours (default 48)

        Returns:
            Number of uploads cleaned up
        """
        stale_uploads = self.list_incomplete_uploads(max_age_hours)
        cleaned = 0

        for upload in stale_uploads:
            try:
                self.s3_client.abort_multipart_upload(
                    Bucket=self.bucket,
                    Key=upload['key'],
                    UploadId=upload['upload_id']
                )
                cleaned += 1
                logger.info(f"Cleaned up stale upload: {upload['key']}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {upload['key']}: {e}")

        logger.info(f"Cleaned up {cleaned} stale uploads")
        return cleaned

    # --- Storage Backend Methods ---

    def _store_session(self, job_id: str, session_data: dict):
        """Store upload session data in Redis or file storage"""
        if self.redis_client:
            try:
                key = f"s3_upload:{job_id}"
                # 7 day TTL (uploads expire after 24h but keep metadata longer)
                self.redis_client.setex(
                    key,
                    86400 * 7,
                    json.dumps(session_data)
                )
                return
            except Exception as e:
                logger.warning(f"Redis storage failed, falling back to file: {e}")

        # Fallback to file storage
        file_path = os.path.join(self.upload_sessions_dir, f"{job_id}.json")
        with open(file_path, 'w') as f:
            json.dump(session_data, f, indent=2)

    def _get_session(self, job_id: str) -> Optional[dict]:
        """Retrieve upload session data from Redis or file storage"""
        if self.redis_client:
            try:
                key = f"s3_upload:{job_id}"
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data.decode('utf-8'))
            except Exception as e:
                logger.warning(f"Redis retrieval failed, trying file: {e}")

        # Fallback to file storage
        file_path = os.path.join(self.upload_sessions_dir, f"{job_id}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)

        return None
