"""
Job Manager for async task handling with Celery and Redis
"""

from celery_app import celery_app
from tasks.audio_processing import process_timeline_task, analyze_audio_task, transcribe_audio_task
from tasks.ai_enhancement import enhance_with_ai_task, enhance_transcription_task, generate_content_summary_task
from tasks.file_management import cleanup_files_task, archive_completed_jobs_task, validate_file_integrity_task
from utils.error_handlers import ValidationError, ProcessingError
from datetime import datetime, timedelta
import redis
import json
import logging
import os

logger = logging.getLogger(__name__)

class JobManager:
    """
    Manages async job submission, tracking, and status updates
    """

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        try:
            self.redis_client = redis.from_url(self.redis_url)
            # Test connection
            self.redis_client.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis_client = None

    def submit_timeline_processing(self, job_id: str, audio_file_path: str, drt_file_path: str, options: dict) -> str:
        """
        Submit timeline processing job to background queue
        """
        try:
            # Validate inputs
            if not os.path.exists(audio_file_path):
                raise ValidationError(f"Audio file not found: {audio_file_path}")

            if not os.path.exists(drt_file_path):
                raise ValidationError(f"DRT file not found: {drt_file_path}")

            # Submit task to Celery
            task = process_timeline_task.delay(job_id, audio_file_path, drt_file_path, options)

            # Store job metadata in Redis
            job_data = {
                'job_id': job_id,
                'task_id': task.id,
                'type': 'timeline_processing',
                'status': 'queued',
                'created_at': datetime.now().isoformat(),
                'audio_file': audio_file_path,
                'drt_file': drt_file_path,
                'options': options
            }

            self._store_job_data(job_id, job_data)

            logger.info(f"Timeline processing job {job_id} submitted with task ID {task.id}")
            return task.id

        except Exception as e:
            logger.error(f"Failed to submit timeline processing job {job_id}: {str(e)}")
            raise

    def submit_audio_analysis(self, job_id: str, audio_file_path: str, analysis_options: dict) -> str:
        """
        Submit audio analysis job to background queue
        """
        try:
            if not os.path.exists(audio_file_path):
                raise ValidationError(f"Audio file not found: {audio_file_path}")

            task = analyze_audio_task.delay(audio_file_path, analysis_options)

            job_data = {
                'job_id': job_id,
                'task_id': task.id,
                'type': 'audio_analysis',
                'status': 'queued',
                'created_at': datetime.now().isoformat(),
                'audio_file': audio_file_path,
                'options': analysis_options
            }

            self._store_job_data(job_id, job_data)

            logger.info(f"Audio analysis job {job_id} submitted with task ID {task.id}")
            return task.id

        except Exception as e:
            logger.error(f"Failed to submit audio analysis job {job_id}: {str(e)}")
            raise

    def submit_ai_enhancement(self, job_id: str, timeline_data: dict, transcription_data: dict, audio_analysis: dict) -> str:
        """
        Submit AI enhancement job to background queue
        """
        try:
            task = enhance_with_ai_task.delay(timeline_data, transcription_data, audio_analysis)

            job_data = {
                'job_id': job_id,
                'task_id': task.id,
                'type': 'ai_enhancement',
                'status': 'queued',
                'created_at': datetime.now().isoformat()
            }

            self._store_job_data(job_id, job_data)

            logger.info(f"AI enhancement job {job_id} submitted with task ID {task.id}")
            return task.id

        except Exception as e:
            logger.error(f"Failed to submit AI enhancement job {job_id}: {str(e)}")
            raise

    def submit_transcription(self, job_id: str, audio_file_path: str, options: dict) -> str:
        """
        Submit transcription job to background queue
        """
        try:
            if not os.path.exists(audio_file_path):
                raise ValidationError(f"Audio file not found: {audio_file_path}")

            task = transcribe_audio_task.delay(audio_file_path, options)

            job_data = {
                'job_id': job_id,
                'task_id': task.id,
                'type': 'transcription',
                'status': 'queued',
                'created_at': datetime.now().isoformat(),
                'audio_file': audio_file_path,
                'options': options
            }

            self._store_job_data(job_id, job_data)

            logger.info(f"Transcription job {job_id} submitted with task ID {task.id}")
            return task.id

        except Exception as e:
            logger.error(f"Failed to submit transcription job {job_id}: {str(e)}")
            raise

    def get_job_status(self, job_id: str) -> dict:
        """
        Get current status of a job
        """
        try:
            # Get job data from Redis
            job_data = self._get_job_data(job_id)
            if not job_data:
                raise ValidationError(f"Job {job_id} not found")

            task_id = job_data.get('task_id')
            if not task_id:
                return job_data

            # Get task status from Celery
            task = celery_app.AsyncResult(task_id)

            # Update status based on Celery task state
            celery_status = task.state
            job_status = self._map_celery_status(celery_status)

            # Get additional info from task
            task_info = {}
            if task.info:
                if isinstance(task.info, dict):
                    task_info = task.info
                else:
                    task_info = {'message': str(task.info)}

            # Update job data
            job_data.update({
                'status': job_status,
                'celery_status': celery_status,
                'progress': task_info.get('progress', 0),
                'message': task_info.get('message', 'Processing'),
                'updated_at': datetime.now().isoformat()
            })

            # Add result data if completed
            if celery_status == 'SUCCESS' and task.result:
                job_data['result'] = task.result

            # Add error info if failed
            if celery_status == 'FAILURE':
                job_data['error'] = task_info.get('error', str(task.info))
                job_data['error_type'] = task_info.get('error_type', 'Unknown')

            # Store updated data
            self._store_job_data(job_id, job_data)

            return job_data

        except Exception as e:
            logger.error(f"Failed to get status for job {job_id}: {str(e)}")
            raise

    def get_job_result(self, job_id: str) -> dict:
        """
        Get the final result of a completed job
        """
        job_status = self.get_job_status(job_id)

        if job_status.get('status') != 'completed':
            raise ValidationError(f"Job {job_id} is not completed (status: {job_status.get('status')})")

        return job_status.get('result', {})

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running or queued job
        """
        try:
            job_data = self._get_job_data(job_id)
            if not job_data:
                raise ValidationError(f"Job {job_id} not found")

            task_id = job_data.get('task_id')
            if task_id:
                # Revoke the Celery task
                celery_app.control.revoke(task_id, terminate=True)

            # Update job status
            job_data.update({
                'status': 'cancelled',
                'cancelled_at': datetime.now().isoformat(),
                'message': 'Job cancelled by user'
            })

            self._store_job_data(job_id, job_data)

            logger.info(f"Job {job_id} cancelled")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {str(e)}")
            return False

    def list_jobs(self, limit: int = 50, job_type: str = None, status: str = None) -> list:
        """
        List jobs with optional filtering
        """
        try:
            if not self.redis_client:
                return []

            # Get all job keys
            job_keys = self.redis_client.keys('job:*')
            jobs = []

            for key in job_keys:
                try:
                    job_data = json.loads(self.redis_client.get(key).decode('utf-8'))

                    # Apply filters
                    if job_type and job_data.get('type') != job_type:
                        continue

                    if status and job_data.get('status') != status:
                        continue

                    jobs.append(job_data)

                except Exception as e:
                    logger.warning(f"Failed to parse job data for key {key}: {str(e)}")
                    continue

            # Sort by creation time (newest first)
            jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)

            return jobs[:limit]

        except Exception as e:
            logger.error(f"Failed to list jobs: {str(e)}")
            return []

    def cleanup_old_jobs(self, max_age_days: int = 7) -> int:
        """
        Clean up old job data from Redis
        """
        try:
            if not self.redis_client:
                return 0

            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            job_keys = self.redis_client.keys('job:*')
            cleaned_count = 0

            for key in job_keys:
                try:
                    job_data = json.loads(self.redis_client.get(key).decode('utf-8'))
                    created_at = datetime.fromisoformat(job_data.get('created_at', ''))

                    if created_at < cutoff_time:
                        self.redis_client.delete(key)
                        cleaned_count += 1

                except Exception as e:
                    logger.warning(f"Failed to process job for cleanup {key}: {str(e)}")
                    continue

            logger.info(f"Cleaned up {cleaned_count} old jobs")
            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {str(e)}")
            return 0

    def _store_job_data(self, job_id: str, job_data: dict):
        """Store job data in Redis"""
        if self.redis_client:
            try:
                key = f"job:{job_id}"
                self.redis_client.setex(key, 86400 * 7, json.dumps(job_data))  # 7 day TTL
            except Exception as e:
                logger.error(f"Failed to store job data for {job_id}: {str(e)}")

    def _get_job_data(self, job_id: str) -> dict:
        """Get job data from Redis"""
        if not self.redis_client:
            return {}

        try:
            key = f"job:{job_id}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data.decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to get job data for {job_id}: {str(e)}")

        return {}

    def _map_celery_status(self, celery_status: str) -> str:
        """Map Celery task states to our job statuses"""
        status_mapping = {
            'PENDING': 'queued',
            'STARTED': 'processing',
            'PROGRESS': 'processing',
            'SUCCESS': 'completed',
            'FAILURE': 'failed',
            'RETRY': 'processing',
            'REVOKED': 'cancelled'
        }
        return status_mapping.get(celery_status, 'unknown')

# Global job manager instance
job_manager = JobManager()