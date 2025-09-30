"""
WebSocket manager for real-time job status updates
"""

from flask_socketio import SocketIO, emit, join_room, leave_room, request
from utils.error_handlers import ValidationError, validate_job_id
import logging
import json
import time

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Manages WebSocket connections and real-time job status broadcasts
    """

    def __init__(self, app=None):
        self.socketio = None
        self.connected_clients = {}  # Track connected clients and their subscriptions
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize SocketIO with Flask app"""
        self.socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode='threading',
            logger=logger,
            engineio_logger=logger
        )

        # Register event handlers
        self.register_handlers()

    def register_handlers(self):
        """Register WebSocket event handlers"""

        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection"""
            client_id = request.sid
            self.connected_clients[client_id] = {
                'connected_at': time.time(),
                'subscribed_jobs': set()
            }

            logger.info(f"Client {client_id} connected")
            emit('connected', {'status': 'success', 'client_id': client_id})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection"""
            client_id = request.sid
            if client_id in self.connected_clients:
                # Leave all job rooms
                for job_id in self.connected_clients[client_id]['subscribed_jobs']:
                    leave_room(f"job_{job_id}")

                del self.connected_clients[client_id]
                logger.info(f"Client {client_id} disconnected")

        @self.socketio.on('subscribe_job')
        def handle_subscribe_job(data):
            """Subscribe client to job status updates"""
            try:
                job_id = data.get('job_id')
                if not job_id:
                    emit('error', {'message': 'job_id is required'})
                    return

                # Validate job ID
                job_id = validate_job_id(job_id)
                client_id = request.sid

                # Join job room
                join_room(f"job_{job_id}")

                # Track subscription
                if client_id in self.connected_clients:
                    self.connected_clients[client_id]['subscribed_jobs'].add(job_id)

                logger.info(f"Client {client_id} subscribed to job {job_id}")
                emit('subscribed', {'job_id': job_id, 'status': 'subscribed'})

            except ValidationError as e:
                emit('error', {'message': str(e)})
            except Exception as e:
                logger.error(f"Error subscribing to job: {str(e)}")
                emit('error', {'message': 'Failed to subscribe to job'})

        @self.socketio.on('unsubscribe_job')
        def handle_unsubscribe_job(data):
            """Unsubscribe client from job status updates"""
            try:
                job_id = data.get('job_id')
                if not job_id:
                    emit('error', {'message': 'job_id is required'})
                    return

                job_id = validate_job_id(job_id)
                client_id = request.sid

                # Leave job room
                leave_room(f"job_{job_id}")

                # Remove from tracking
                if client_id in self.connected_clients:
                    self.connected_clients[client_id]['subscribed_jobs'].discard(job_id)

                logger.info(f"Client {client_id} unsubscribed from job {job_id}")
                emit('unsubscribed', {'job_id': job_id, 'status': 'unsubscribed'})

            except ValidationError as e:
                emit('error', {'message': str(e)})
            except Exception as e:
                logger.error(f"Error unsubscribing from job: {str(e)}")
                emit('error', {'message': 'Failed to unsubscribe from job'})

        @self.socketio.on('get_job_status')
        def handle_get_job_status(data):
            """Get current job status via WebSocket"""
            try:
                job_id = data.get('job_id')
                if not job_id:
                    emit('error', {'message': 'job_id is required'})
                    return

                job_id = validate_job_id(job_id)

                # Get job status from job manager
                from job_manager import job_manager
                job_status = job_manager.get_job_status(job_id)

                if job_status:
                    emit('job_status', {
                        'job_id': job_id,
                        'status': job_status.get('status'),
                        'progress': job_status.get('progress', 0),
                        'message': job_status.get('message'),
                        'timestamp': time.time()
                    })
                else:
                    emit('error', {'message': f'Job {job_id} not found'})

            except ValidationError as e:
                emit('error', {'message': str(e)})
            except Exception as e:
                logger.error(f"Error getting job status: {str(e)}")
                emit('error', {'message': 'Failed to get job status'})

        @self.socketio.on('ping')
        def handle_ping():
            """Handle ping for connection keepalive"""
            emit('pong', {'timestamp': time.time()})

    def broadcast_job_update(self, job_id: str, status_data: dict):
        """
        Broadcast job status update to all subscribed clients
        """
        if not self.socketio:
            return

        try:
            job_id = validate_job_id(job_id)

            update_message = {
                'job_id': job_id,
                'timestamp': time.time(),
                **status_data
            }

            # Broadcast to all clients in the job room
            self.socketio.emit(
                'job_update',
                update_message,
                room=f"job_{job_id}"
            )

            logger.debug(f"Broadcasted job update for {job_id}: {status_data.get('status', 'unknown')}")

        except Exception as e:
            logger.error(f"Error broadcasting job update: {str(e)}")

    def broadcast_job_progress(self, job_id: str, progress: int, message: str = None):
        """
        Broadcast job progress update
        """
        status_data = {
            'progress': progress,
            'message': message or 'Processing...',
            'type': 'progress'
        }
        self.broadcast_job_update(job_id, status_data)

    def broadcast_job_completed(self, job_id: str, result: dict = None):
        """
        Broadcast job completion
        """
        status_data = {
            'status': 'completed',
            'progress': 100,
            'message': 'Processing completed successfully',
            'type': 'completion',
            'result': result or {}
        }
        self.broadcast_job_update(job_id, status_data)

    def broadcast_job_failed(self, job_id: str, error: str, error_type: str = None):
        """
        Broadcast job failure
        """
        status_data = {
            'status': 'failed',
            'progress': 100,
            'message': f'Processing failed: {error}',
            'type': 'failure',
            'error': error,
            'error_type': error_type or 'ProcessingError'
        }
        self.broadcast_job_update(job_id, status_data)

    def get_connected_clients_count(self) -> int:
        """Get number of connected clients"""
        return len(self.connected_clients)

    def get_job_subscribers_count(self, job_id: str) -> int:
        """Get number of clients subscribed to a specific job"""
        try:
            job_id = validate_job_id(job_id)
            count = 0
            for client_data in self.connected_clients.values():
                if job_id in client_data['subscribed_jobs']:
                    count += 1
            return count
        except:
            return 0

    def cleanup_stale_connections(self, max_age_seconds: int = 3600):
        """Clean up stale connections"""
        current_time = time.time()
        stale_clients = []

        for client_id, client_data in self.connected_clients.items():
            if current_time - client_data['connected_at'] > max_age_seconds:
                stale_clients.append(client_id)

        for client_id in stale_clients:
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
                logger.info(f"Cleaned up stale client connection: {client_id}")

        return len(stale_clients)

# Global WebSocket manager instance
websocket_manager = WebSocketManager()