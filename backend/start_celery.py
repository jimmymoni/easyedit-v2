#!/usr/bin/env python3
"""
Celery worker startup script for easyedit-v2
"""

import os
import sys
from celery_app import celery_app

def start_worker():
    """Start Celery worker with appropriate configuration"""

    # Set up environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

    # Configure worker options based on environment
    worker_options = [
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--max-tasks-per-child=100',
        '--prefetch-multiplier=1',
        '--hostname=easyedit-worker@%h'
    ]

    # Add queue-specific workers in production
    if os.getenv('ENVIRONMENT') == 'production':
        # Start multiple workers for different queues
        import subprocess
        import time

        workers = [
            {
                'name': 'audio-worker',
                'queues': 'audio',
                'concurrency': 2
            },
            {
                'name': 'ai-worker',
                'queues': 'ai',
                'concurrency': 1
            },
            {
                'name': 'files-worker',
                'queues': 'files',
                'concurrency': 2
            }
        ]

        processes = []

        for worker in workers:
            cmd = [
                'celery', '-A', 'celery_app', 'worker',
                '--hostname', f"{worker['name']}@%h",
                '--queues', worker['queues'],
                '--concurrency', str(worker['concurrency']),
                '--loglevel=info',
                '--max-tasks-per-child=100'
            ]

            print(f"Starting {worker['name']} worker...")
            proc = subprocess.Popen(cmd)
            processes.append(proc)
            time.sleep(2)  # Stagger startup

        # Wait for all workers
        try:
            for proc in processes:
                proc.wait()
        except KeyboardInterrupt:
            print("Shutting down workers...")
            for proc in processes:
                proc.terminate()

    else:
        # Development mode - single worker
        worker_options.extend([
            '--queues=audio,ai,files',
            '--pool=solo' if sys.platform == 'win32' else '--pool=prefork'
        ])

        # Start worker
        celery_app.worker_main(worker_options)

def start_beat():
    """Start Celery beat scheduler for periodic tasks"""
    beat_options = [
        'beat',
        '--loglevel=info',
        '--schedule=/tmp/celerybeat-schedule',
        '--pidfile=/tmp/celerybeat.pid'
    ]

    celery_app.worker_main(beat_options)

def start_flower():
    """Start Flower monitoring interface"""
    flower_options = [
        'flower',
        '--port=5555',
        '--broker_api=http://guest:guest@localhost:15672/api/',
        '--basic_auth=admin:admin123'
    ]

    celery_app.worker_main(flower_options)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Start Celery components')
    parser.add_argument('component', choices=['worker', 'beat', 'flower'],
                       help='Component to start')

    args = parser.parse_args()

    if args.component == 'worker':
        start_worker()
    elif args.component == 'beat':
        start_beat()
    elif args.component == 'flower':
        start_flower()
    else:
        print("Invalid component. Use: worker, beat, or flower")
        sys.exit(1)