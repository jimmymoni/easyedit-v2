"""
Celery application configuration for async background processing
"""

from celery import Celery
from config import Config
import os

def make_celery(app=None):
    """Create and configure Celery instance"""

    # Redis configuration
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    celery = Celery(
        'easyedit-v2',
        broker=redis_url,
        backend=redis_url,
        include=[
            'tasks.audio_processing',
            'tasks.ai_enhancement',
            'tasks.file_management'
        ]
    )

    # Celery configuration
    celery.conf.update(
        # Task settings
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,

        # Performance settings
        worker_concurrency=4,
        worker_max_tasks_per_child=100,
        task_acks_late=True,
        worker_prefetch_multiplier=1,

        # Reliability settings
        task_reject_on_worker_lost=True,
        task_ignore_result=False,
        result_expires=3600,  # 1 hour

        # Retry settings
        task_default_retry_delay=60,  # 1 minute
        task_max_retries=3,

        # Rate limiting
        task_default_rate_limit='10/m',  # 10 tasks per minute

        # Route tasks to specific queues
        task_routes={
            'tasks.audio_processing.*': {'queue': 'audio'},
            'tasks.ai_enhancement.*': {'queue': 'ai'},
            'tasks.file_management.*': {'queue': 'files'},
        },

        # Queue priorities
        task_queue_max_priority=10,
        task_default_priority=5,
        worker_disable_rate_limits=False,

        # Monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,
    )

    # Update task base classes if Flask app is provided
    if app:
        class ContextTask(celery.Task):
            """Make celery tasks work with Flask app context"""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    return celery

# Create the Celery instance
celery_app = make_celery()

if __name__ == '__main__':
    celery_app.start()