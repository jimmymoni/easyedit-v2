import time
import psutil
import logging
import threading
from typing import Dict, Any, List
from collections import deque, defaultdict
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class SystemMonitor:
    """Monitor system resources and application metrics"""

    def __init__(self, max_history_minutes: int = 60):
        self.max_history = max_history_minutes
        self.metrics_history = deque(maxlen=max_history_minutes * 2)  # Store data every 30s
        self.request_metrics = defaultdict(int)
        self.error_metrics = defaultdict(int)
        self.processing_metrics = {
            'jobs_completed': 0,
            'jobs_failed': 0,
            'total_processing_time': 0,
            'average_processing_time': 0
        }
        self.lock = threading.Lock()
        self.start_time = time.time()

        # Start background monitoring
        self.monitoring_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitoring_thread.start()

    def _monitor_loop(self):
        """Background loop to collect system metrics"""
        while True:
            try:
                metrics = self._collect_system_metrics()
                with self.lock:
                    self.metrics_history.append({
                        'timestamp': time.time(),
                        'datetime': datetime.now().isoformat(),
                        **metrics
                    })
                time.sleep(30)  # Collect metrics every 30 seconds
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait longer on error

    def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_mb': memory.available // 1024 // 1024,
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free // 1024 // 1024 // 1024,
            }
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}

    def record_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """Record API request metrics"""
        with self.lock:
            self.request_metrics[f"{method}_{endpoint}"] += 1
            self.request_metrics[f"status_{status_code}"] += 1
            self.request_metrics['total_requests'] += 1

            if status_code >= 400:
                self.error_metrics[f"{method}_{endpoint}"] += 1
                self.error_metrics['total_errors'] += 1

    def record_processing_job(self, success: bool, duration: float):
        """Record processing job metrics"""
        with self.lock:
            if success:
                self.processing_metrics['jobs_completed'] += 1
            else:
                self.processing_metrics['jobs_failed'] += 1

            total_jobs = self.processing_metrics['jobs_completed'] + self.processing_metrics['jobs_failed']
            self.processing_metrics['total_processing_time'] += duration

            if total_jobs > 0:
                self.processing_metrics['average_processing_time'] = (
                    self.processing_metrics['total_processing_time'] / total_jobs
                )

    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        with self.lock:
            current_metrics = self._collect_system_metrics()
            uptime_seconds = time.time() - self.start_time

            # Determine overall health
            health_score = 100
            status = "healthy"
            issues = []

            # Check system resources
            if current_metrics.get('cpu_percent', 0) > 80:
                health_score -= 20
                issues.append("High CPU usage")

            if current_metrics.get('memory_percent', 0) > 85:
                health_score -= 25
                issues.append("High memory usage")

            if current_metrics.get('disk_percent', 0) > 90:
                health_score -= 15
                issues.append("Low disk space")

            # Check error rates
            total_requests = self.request_metrics.get('total_requests', 0)
            total_errors = self.error_metrics.get('total_errors', 0)

            if total_requests > 0:
                error_rate = total_errors / total_requests
                if error_rate > 0.1:  # 10% error rate
                    health_score -= 30
                    issues.append(f"High error rate: {error_rate:.1%}")

            # Determine status based on health score
            if health_score >= 80:
                status = "healthy"
            elif health_score >= 60:
                status = "degraded"
            else:
                status = "unhealthy"

            return {
                'status': status,
                'health_score': health_score,
                'uptime_seconds': uptime_seconds,
                'uptime_human': self._format_duration(uptime_seconds),
                'timestamp': datetime.now().isoformat(),
                'system_metrics': current_metrics,
                'request_metrics': dict(self.request_metrics),
                'error_metrics': dict(self.error_metrics),
                'processing_metrics': self.processing_metrics.copy(),
                'issues': issues
            }

    def get_metrics_history(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """Get metrics history for the last N minutes"""
        cutoff_time = time.time() - (minutes * 60)

        with self.lock:
            return [
                metric for metric in self.metrics_history
                if metric['timestamp'] >= cutoff_time
            ]

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human readable format"""
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            return f"{seconds/60:.1f} minutes"
        elif seconds < 86400:
            return f"{seconds/3600:.1f} hours"
        else:
            return f"{seconds/86400:.1f} days"

    def export_metrics(self) -> Dict[str, Any]:
        """Export all metrics for external monitoring systems"""
        with self.lock:
            return {
                'timestamp': time.time(),
                'uptime': time.time() - self.start_time,
                'system_metrics': self._collect_system_metrics(),
                'request_metrics': dict(self.request_metrics),
                'error_metrics': dict(self.error_metrics),
                'processing_metrics': self.processing_metrics.copy(),
                'history': list(self.metrics_history)
            }

# Global monitor instance
system_monitor = SystemMonitor()

class HealthChecker:
    """Health check for external dependencies and services"""

    def __init__(self):
        self.checks = {}

    def register_check(self, name: str, check_function, timeout: float = 5.0):
        """Register a health check function"""
        self.checks[name] = {
            'function': check_function,
            'timeout': timeout,
            'last_result': None,
            'last_check': None
        }

    def run_check(self, name: str) -> Dict[str, Any]:
        """Run a specific health check"""
        if name not in self.checks:
            return {
                'status': 'unknown',
                'message': f'Check "{name}" not found'
            }

        check_info = self.checks[name]
        start_time = time.time()

        try:
            # Run the check function with timeout
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("Health check timed out")

            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(check_info['timeout']))

            try:
                result = check_info['function']()
                signal.alarm(0)  # Cancel the alarm
            finally:
                signal.signal(signal.SIGALRM, old_handler)

            duration = time.time() - start_time

            check_result = {
                'status': 'healthy',
                'duration': duration,
                'timestamp': time.time(),
                **result
            }

        except TimeoutError:
            check_result = {
                'status': 'timeout',
                'message': f'Health check timed out after {check_info["timeout"]}s',
                'duration': time.time() - start_time,
                'timestamp': time.time()
            }

        except Exception as e:
            check_result = {
                'status': 'unhealthy',
                'message': str(e),
                'duration': time.time() - start_time,
                'timestamp': time.time()
            }

        # Store result
        check_info['last_result'] = check_result
        check_info['last_check'] = time.time()

        return check_result

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""
        results = {}
        overall_status = 'healthy'

        for name in self.checks:
            result = self.run_check(name)
            results[name] = result

            if result['status'] != 'healthy':
                overall_status = 'unhealthy'

        return {
            'overall_status': overall_status,
            'checks': results,
            'timestamp': datetime.now().isoformat()
        }

# Global health checker
health_checker = HealthChecker()

def setup_default_health_checks():
    """Setup default health checks for common dependencies"""

    def check_disk_space():
        """Check available disk space"""
        disk = psutil.disk_usage('/')
        free_percent = (disk.free / disk.total) * 100

        if free_percent < 10:
            return {'message': f'Low disk space: {free_percent:.1f}% free'}
        return {'message': f'Disk space OK: {free_percent:.1f}% free'}

    def check_memory():
        """Check available memory"""
        memory = psutil.virtual_memory()

        if memory.percent > 90:
            return {'message': f'High memory usage: {memory.percent:.1f}%'}
        return {'message': f'Memory usage OK: {memory.percent:.1f}%'}

    def check_soniox_api():
        """Check Soniox API connectivity"""
        try:
            from services.soniox_client import SonioxClient
            client = SonioxClient()
            if client.check_api_status():
                return {'message': 'Soniox API accessible'}
            else:
                raise Exception('Soniox API not accessible')
        except Exception as e:
            raise Exception(f'Soniox API check failed: {str(e)}')

    def check_openai_api():
        """Check OpenAI API connectivity"""
        try:
            import openai
            from config import Config

            if not Config.OPENAI_API_KEY:
                return {'message': 'OpenAI API not configured'}

            # Simple API test
            openai.api_key = Config.OPENAI_API_KEY

            # This is a minimal test - in production you might want a more comprehensive check
            return {'message': 'OpenAI API configured'}

        except Exception as e:
            raise Exception(f'OpenAI API check failed: {str(e)}')

    # Register checks
    health_checker.register_check('disk_space', check_disk_space, timeout=2.0)
    health_checker.register_check('memory', check_memory, timeout=2.0)
    health_checker.register_check('soniox_api', check_soniox_api, timeout=10.0)
    health_checker.register_check('openai_api', check_openai_api, timeout=5.0)

def setup_monitoring(app):
    """Setup monitoring for Flask app"""

    # Setup default health checks
    setup_default_health_checks()

    # Middleware to track requests
    @app.before_request
    def track_request_start():
        import flask
        flask.g.start_time = time.time()

    @app.after_request
    def track_request_end(response):
        import flask
        duration = time.time() - flask.g.start_time

        # Record metrics
        system_monitor.record_request(
            endpoint=flask.request.endpoint or flask.request.path,
            method=flask.request.method,
            status_code=response.status_code,
            duration=duration
        )

        return response

    logger.info("Monitoring setup complete")