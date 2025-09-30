"""
File management background tasks
"""

from celery_app import celery_app
from config import Config
from datetime import datetime, timedelta
import logging
import os
import shutil

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, queue='files', priority=2)
def cleanup_files_task(self, max_age_hours: int = None):
    """
    Background task for cleaning up old files
    """
    try:
        max_age_hours = max_age_hours or Config.TEMP_FILE_RETENTION_HOURS

        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Starting file cleanup'}
        )

        current_time = datetime.now()
        cleanup_stats = {
            'files_removed': 0,
            'bytes_freed': 0,
            'folders_checked': 0
        }

        folders_to_clean = [Config.UPLOAD_FOLDER, Config.TEMP_FOLDER]

        for folder in folders_to_clean:
            if not os.path.exists(folder):
                continue

            cleanup_stats['folders_checked'] += 1

            self.update_state(
                state='PROGRESS',
                meta={'progress': 20 + (cleanup_stats['folders_checked'] * 30), 'message': f'Cleaning {folder}'}
            )

            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)

                try:
                    if os.path.isfile(file_path):
                        # Check file age
                        file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                        if current_time - file_time > timedelta(hours=max_age_hours):
                            # Get file size before deletion
                            file_size = os.path.getsize(file_path)

                            # Remove file
                            os.remove(file_path)

                            cleanup_stats['files_removed'] += 1
                            cleanup_stats['bytes_freed'] += file_size

                            logger.info(f"Cleaned up old file: {filename}")

                    elif os.path.isdir(file_path):
                        # Clean up empty directories
                        try:
                            if not os.listdir(file_path):  # Directory is empty
                                os.rmdir(file_path)
                                logger.info(f"Removed empty directory: {filename}")
                        except OSError:
                            pass  # Directory not empty or other issue

                except Exception as e:
                    logger.warning(f"Could not clean up {file_path}: {str(e)}")
                    continue

        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'File cleanup complete'}
        )

        result = {
            'status': 'completed',
            'stats': cleanup_stats,
            'max_age_hours': max_age_hours,
            'folders_checked': folders_to_clean
        }

        logger.info(f"File cleanup completed: {cleanup_stats['files_removed']} files removed, "
                   f"{cleanup_stats['bytes_freed']} bytes freed")

        return result

    except Exception as e:
        logger.exception("File cleanup failed")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise

@celery_app.task(bind=True, queue='files', priority=1)
def archive_completed_jobs_task(self, jobs_data: dict, archive_after_days: int = 7):
    """
    Background task for archiving completed job data
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': 'Starting job archival'}
        )

        current_time = datetime.now()
        archive_stats = {
            'jobs_archived': 0,
            'files_moved': 0,
            'archive_path': os.path.join(Config.TEMP_FOLDER, 'archive')
        }

        # Ensure archive directory exists
        os.makedirs(archive_stats['archive_path'], exist_ok=True)

        jobs_to_archive = []

        # Find jobs to archive
        for job_id, job_data in jobs_data.items():
            if job_data.get('status') != 'completed':
                continue

            job_age = current_time - job_data.get('created_at', current_time)
            if job_age > timedelta(days=archive_after_days):
                jobs_to_archive.append((job_id, job_data))

        total_jobs = len(jobs_to_archive)

        for i, (job_id, job_data) in enumerate(jobs_to_archive):
            self.update_state(
                state='PROGRESS',
                meta={'progress': 20 + (i / total_jobs * 70), 'message': f'Archiving job {job_id}'}
            )

            try:
                # Move job files to archive
                job_archive_path = os.path.join(archive_stats['archive_path'], job_id)
                os.makedirs(job_archive_path, exist_ok=True)

                # Archive associated files
                for file_key in ['audio_file', 'drt_file', 'output_file']:
                    file_path = job_data.get(file_key)
                    if file_path and os.path.exists(file_path):
                        filename = os.path.basename(file_path)
                        archive_file_path = os.path.join(job_archive_path, filename)

                        shutil.move(file_path, archive_file_path)
                        archive_stats['files_moved'] += 1

                # Save job metadata
                import json
                metadata_file = os.path.join(job_archive_path, 'metadata.json')
                with open(metadata_file, 'w') as f:
                    # Convert datetime objects to strings for JSON serialization
                    serializable_data = {}
                    for key, value in job_data.items():
                        if isinstance(value, datetime):
                            serializable_data[key] = value.isoformat()
                        else:
                            serializable_data[key] = value

                    json.dump(serializable_data, f, indent=2)

                archive_stats['jobs_archived'] += 1

            except Exception as e:
                logger.warning(f"Could not archive job {job_id}: {str(e)}")
                continue

        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'Job archival complete'}
        )

        result = {
            'status': 'completed',
            'stats': archive_stats,
            'archive_after_days': archive_after_days
        }

        logger.info(f"Job archival completed: {archive_stats['jobs_archived']} jobs archived")
        return result

    except Exception as e:
        logger.exception("Job archival failed")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise

@celery_app.task(bind=True, queue='files', priority=8)
def validate_file_integrity_task(self, file_path: str):
    """
    Background task for validating file integrity
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'message': f'Validating {os.path.basename(file_path)}'}
        )

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        validation_result = {
            'file_path': file_path,
            'exists': True,
            'size': os.path.getsize(file_path),
            'readable': False,
            'format_valid': False,
            'errors': []
        }

        # Test file readability
        self.update_state(
            state='PROGRESS',
            meta={'progress': 30, 'message': 'Testing file readability'}
        )

        try:
            with open(file_path, 'rb') as f:
                f.read(1024)  # Read first 1KB
            validation_result['readable'] = True
        except Exception as e:
            validation_result['errors'].append(f"File not readable: {str(e)}")

        # Validate file format based on extension
        self.update_state(
            state='PROGRESS',
            meta={'progress': 60, 'message': 'Validating file format'}
        )

        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in ['.wav', '.mp3', '.m4a', '.aac', '.flac']:
            # Validate audio file
            try:
                from services.audio_analyzer import AudioAnalyzer
                analyzer = AudioAnalyzer()
                if analyzer.load_audio(file_path):
                    validation_result['format_valid'] = True
                else:
                    validation_result['errors'].append("Invalid audio format")
            except Exception as e:
                validation_result['errors'].append(f"Audio validation error: {str(e)}")

        elif file_ext in ['.drt', '.xml']:
            # Validate XML/DRT file
            try:
                from parsers.drt_parser import DRTParser
                parser = DRTParser()
                parser.parse_file(file_path)
                validation_result['format_valid'] = True
            except Exception as e:
                validation_result['errors'].append(f"XML validation error: {str(e)}")

        else:
            validation_result['errors'].append(f"Unsupported file type: {file_ext}")

        self.update_state(
            state='PROGRESS',
            meta={'progress': 100, 'message': 'File validation complete'}
        )

        result = {
            'status': 'completed',
            'validation': validation_result,
            'valid': validation_result['readable'] and validation_result['format_valid']
        }

        return result

    except Exception as e:
        logger.exception(f"File validation failed for {file_path}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'file_path': file_path}
        )
        raise