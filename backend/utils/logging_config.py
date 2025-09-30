import logging
import logging.handlers
import os
from datetime import datetime
from config import Config

class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output"""

    COLORS = {
        'DEBUG': '\033[94m',    # Blue
        'INFO': '\033[92m',     # Green
        'WARNING': '\033[93m',  # Yellow
        'ERROR': '\033[91m',    # Red
        'CRITICAL': '\033[95m', # Magenta
        'RESET': '\033[0m'      # Reset
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset_color = self.COLORS['RESET']

        # Apply color to the entire message
        record.levelname = f"{log_color}{record.levelname}{reset_color}"
        record.msg = f"{log_color}{record.msg}{reset_color}"

        return super().format(record)

def setup_logging(app_name: str = "easyedit-v2", log_level: str = "INFO"):
    """
    Configure comprehensive logging for the application
    """
    # Create logs directory
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # Set log level
    log_level_obj = getattr(logging, log_level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level_obj)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with color
    console_handler = logging.StreamHandler()
    console_formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level_obj)
    logger.addHandler(console_handler)

    # File handler for all logs
    log_file = os.path.join(log_dir, f'{app_name}.log')
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    # Error file handler
    error_log_file = os.path.join(log_dir, f'{app_name}_errors.log')
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3
    )
    error_handler.setFormatter(file_formatter)
    error_handler.setLevel(logging.ERROR)
    logger.addHandler(error_handler)

    # Performance log handler
    perf_log_file = os.path.join(log_dir, f'{app_name}_performance.log')
    perf_handler = logging.handlers.RotatingFileHandler(
        perf_log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=2
    )
    perf_formatter = logging.Formatter(
        '%(asctime)s - PERF - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    perf_handler.setFormatter(perf_formatter)
    perf_handler.setLevel(logging.INFO)

    # Create performance logger
    perf_logger = logging.getLogger('performance')
    perf_logger.addHandler(perf_handler)
    perf_logger.setLevel(logging.INFO)
    perf_logger.propagate = False

    # API access log handler
    access_log_file = os.path.join(log_dir, f'{app_name}_access.log')
    access_handler = logging.handlers.RotatingFileHandler(
        access_log_file,
        maxBytes=20*1024*1024,  # 20MB
        backupCount=5
    )
    access_formatter = logging.Formatter(
        '%(asctime)s - ACCESS - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    access_handler.setFormatter(access_formatter)
    access_handler.setLevel(logging.INFO)

    # Create access logger
    access_logger = logging.getLogger('access')
    access_logger.addHandler(access_handler)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False

    logger.info(f"Logging configured for {app_name}")
    return logger

def log_performance(operation: str, duration: float, details: dict = None):
    """
    Log performance metrics
    """
    perf_logger = logging.getLogger('performance')
    message = f"Operation: {operation}, Duration: {duration:.3f}s"
    if details:
        message += f", Details: {details}"
    perf_logger.info(message)

def log_api_access(method: str, endpoint: str, status_code: int, duration: float, user_agent: str = None):
    """
    Log API access
    """
    access_logger = logging.getLogger('access')
    message = f"{method} {endpoint} - {status_code} - {duration:.3f}s"
    if user_agent:
        message += f" - {user_agent}"
    access_logger.info(message)

class RequestLogger:
    """Middleware for logging Flask requests"""

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.before_request(self.before_request)
        app.after_request(self.after_request)

        # Store start time in app context
        import flask
        self.request_start_time = None

    def before_request(self):
        import flask
        import time
        flask.g.start_time = time.time()

    def after_request(self, response):
        import flask
        import time

        duration = time.time() - flask.g.start_time

        log_api_access(
            method=flask.request.method,
            endpoint=flask.request.endpoint or flask.request.path,
            status_code=response.status_code,
            duration=duration,
            user_agent=flask.request.headers.get('User-Agent')
        )

        return response