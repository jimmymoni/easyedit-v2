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
from threading import Lock

logger = logging.getLogger(__name__)

class JobManager:
    """
    Manages async job submission, tracking, and status updates
    """

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')

        # File-based persistent storage directory
        self.jobs_dir = os.path.join(os.path.dirname(__file__), 'jobs_data')
        os.makedirs(self.jobs_dir, exist_ok=True)

        # In-memory cache for quick lookups (synced with file storage)
        self._memory_store = {}
        self._memory_lock = Lock()

        # Load existing jobs from file storage on startup
        self._load_jobs_from_disk()

        try:
            self.redis_client = redis.from_url(self.redis_url)
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis for job storage")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {str(e)}. Using file-based job storage.")
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

            # Pre-create job data BEFORE task submission to avoid race condition
            # This ensures the job exists when frontend starts polling for status
            job_data = {
                'job_id': job_id,
                'task_id': None,  # Will be set after task creation
                'type': 'timeline_processing',
                'status': 'queued',
                'created_at': datetime.now().isoformat(),
                'audio_file': audio_file_path,
                'drt_file': drt_file_path,
                'options': options,
                'progress': 0,
                'message': 'Job queued for processing'
            }

            # Store initial job data immediately
            self._store_job_data(job_id, job_data)
            logger.debug(f"Pre-stored job {job_id} in storage before task submission")

            # Submit task to Celery
            task = process_timeline_task.delay(job_id, audio_file_path, drt_file_path, options)

            # Update job metadata with task ID
            job_data['task_id'] = task.id

            # In eager mode, the task executes synchronously and result is immediately available
            from celery_app import celery_app
            if celery_app.conf.task_always_eager:
                try:
                    # Get the result from the eager execution
                    # In eager mode, task.get() returns the result directly without backend
                    task_result = task.get(disable_sync_subtasks=False)
                    if task_result:
                        logger.info(f"Eager mode: Task completed, storing result for job {job_id}")
                        # Update job data with the result
                        job_data.update({
                            'status': 'completed',
                            'result': task_result,
                            'progress': 100,
                            'message': task_result.get('message', 'Processing completed'),
                            'completed_at': datetime.now().isoformat()
                        })
                except Exception as e:
                    logger.warning(f"Could not get eager task result: {str(e)}")

            # Store final job data with task ID and results
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
            # Get job data from storage (Redis or in-memory)
            job_data = self._get_job_data(job_id)
            if not job_data:
                raise ValidationError(f"Job {job_id} not found")

            # If job already has a completed status, return it directly
            if job_data.get('status') in ['completed', 'failed', 'cancelled']:
                return job_data

            task_id = job_data.get('task_id')
            if not task_id:
                return job_data

            # Only query Celery backend if it's available (not in eager mode)
            from celery_app import celery_app
            if celery_app.conf.task_always_eager:
                # In eager mode, return stored job data directly
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
            jobs = []

            if self.redis_client:
                # Get jobs from Redis
                job_keys = self.redis_client.keys('job:*')

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
            else:
                # Get jobs from memory cache (which is loaded from file storage on startup)
                with self._memory_lock:
                    for job_id, job_data in self._memory_store.items():
                        # Apply filters
                        if job_type and job_data.get('type') != job_type:
                            continue

                        if status and job_data.get('status') != status:
                            continue

                        jobs.append(job_data)

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
        """Store job data in Redis or file-based persistent storage"""
        if self.redis_client:
            try:
                key = f"job:{job_id}"
                self.redis_client.setex(key, 86400 * 7, json.dumps(job_data))  # 7 day TTL
            except Exception as e:
                logger.error(f"Failed to store job data in Redis for {job_id}: {str(e)}")
                # Fallback to file-based storage
                self._store_job_to_file(job_id, job_data)
        else:
            # Use file-based persistent storage when Redis is unavailable
            self._store_job_to_file(job_id, job_data)

        # Always cache in memory for quick lookups
        with self._memory_lock:
            self._memory_store[job_id] = job_data

    def _get_job_data(self, job_id: str) -> dict:
        """Get job data from Redis, memory cache, or file storage"""
        # First check memory cache (fastest)
        with self._memory_lock:
            if job_id in self._memory_store:
                return self._memory_store[job_id]

        # Then try Redis if available
        if self.redis_client:
            try:
                key = f"job:{job_id}"
                data = self.redis_client.get(key)
                if data:
                    job_data = json.loads(data.decode('utf-8'))
                    # Cache it in memory
                    with self._memory_lock:
                        self._memory_store[job_id] = job_data
                    return job_data
            except Exception as e:
                logger.error(f"Failed to get job data from Redis for {job_id}: {str(e)}")

        # Finally try file storage
        job_data = self._load_job_from_file(job_id)
        if job_data:
            # Cache it in memory
            with self._memory_lock:
                self._memory_store[job_id] = job_data
            return job_data

        return {}

    def store_task_result(self, job_id: str, result: dict):
        """
        Manually store task result (useful for eager mode where result isn't persisted)
        """
        try:
            job_data = self._get_job_data(job_id)

            if not job_data:
                logger.warning(f"Job {job_id} not found when storing result")
                # Create basic job data
                job_data = {
                    'job_id': job_id,
                    'type': 'timeline_processing',
                    'created_at': datetime.now().isoformat()
                }

            # Update with result
            job_data.update({
                'status': result.get('status', 'completed'),
                'result': result,
                'progress': 100,
                'message': result.get('message', 'Processing completed'),
                'updated_at': datetime.now().isoformat(),
                'completed_at': datetime.now().isoformat()
            })

            self._store_job_data(job_id, job_data)
            logger.info(f"Stored task result for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to store task result for job {job_id}: {str(e)}")

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

    def _store_job_to_file(self, job_id: str, job_data: dict):
        """Store job data to a JSON file for persistence"""
        try:
            file_path = os.path.join(self.jobs_dir, f"{job_id}.json")
            with open(file_path, 'w') as f:
                json.dump(job_data, f, indent=2)
            logger.debug(f"Stored job {job_id} to file storage")
        except Exception as e:
            logger.error(f"Failed to store job {job_id} to file: {str(e)}")

    def _load_job_from_file(self, job_id: str) -> dict:
        """Load job data from a JSON file"""
        try:
            file_path = os.path.join(self.jobs_dir, f"{job_id}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    job_data = json.load(f)
                logger.debug(f"Loaded job {job_id} from file storage")
                return job_data
        except Exception as e:
            logger.error(f"Failed to load job {job_id} from file: {str(e)}")
        return {}

    def _load_jobs_from_disk(self):
        """Load all existing jobs from disk into memory cache on startup"""
        try:
            if not os.path.exists(self.jobs_dir):
                return

            job_files = [f for f in os.listdir(self.jobs_dir) if f.endswith('.json')]
            loaded_count = 0

            with self._memory_lock:
                for filename in job_files:
                    try:
                        job_id = filename.replace('.json', '')
                        file_path = os.path.join(self.jobs_dir, filename)

                        with open(file_path, 'r') as f:
                            job_data = json.load(f)
                            self._memory_store[job_id] = job_data
                            loaded_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to load job file {filename}: {str(e)}")
                        continue

            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count} jobs from file storage into memory")
        except Exception as e:
            logger.error(f"Failed to load jobs from disk: {str(e)}")

# Global job manager instance
job_manager = JobManager()