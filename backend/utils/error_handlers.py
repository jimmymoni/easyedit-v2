import logging
import traceback
from functools import wraps
from typing import Dict, Any, Callable
from flask import jsonify, request
import time
import mimetypes
import os

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Custom API Exception"""

    def __init__(self, message: str, status_code: int = 500, payload: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}

    def to_dict(self) -> Dict[str, Any]:
        error_dict = {
            'error': self.message,
            'status_code': self.status_code
        }
        error_dict.update(self.payload)
        return error_dict

class ValidationError(APIError):
    """Validation error"""
    def __init__(self, message: str, field: str = None):
        super().__init__(message, status_code=400)
        if field:
            self.payload['field'] = field

class ProcessingError(APIError):
    """Processing error"""
    def __init__(self, message: str, job_id: str = None):
        super().__init__(message, status_code=500)
        if job_id:
            self.payload['job_id'] = job_id

class RateLimitError(APIError):
    """Rate limit error"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, status_code=429)

def handle_api_error(error: APIError):
    """Handle custom API errors"""
    logger.error(f"API Error: {error.message}", exc_info=True)
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

def handle_validation_error(error: ValidationError):
    """Handle validation errors"""
    logger.warning(f"Validation Error: {error.message}")
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

def handle_processing_error(error: ProcessingError):
    """Handle processing errors"""
    logger.error(f"Processing Error: {error.message}", exc_info=True)
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

def handle_generic_exception(error: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {str(error)}", exc_info=True)

    # Don't expose internal error details in production
    import os
    if os.getenv('FLASK_ENV') == 'production':
        message = "An internal server error occurred"
    else:
        message = str(error)

    response = jsonify({
        'error': message,
        'status_code': 500,
        'type': 'internal_server_error'
    })
    response.status_code = 500
    return response

def error_handler(func: Callable) -> Callable:
    """Decorator for handling errors in route functions"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)

            # Log performance
            duration = time.time() - start_time
            if duration > 1.0:  # Log slow requests
                logger.warning(f"Slow request: {func.__name__} took {duration:.2f}s")

            return result

        except APIError as e:
            return handle_api_error(e)
        except ValidationError as e:
            return handle_validation_error(e)
        except ProcessingError as e:
            return handle_processing_error(e)
        except Exception as e:
            return handle_generic_exception(e)

    return wrapper

def validate_file_upload(file, allowed_extensions: set, max_size_mb: int = 500):
    """Validate uploaded files with comprehensive security checks"""
    if not file:
        raise ValidationError("No file provided")

    if file.filename == '':
        raise ValidationError("No file selected")

    # Sanitize filename
    filename = file.filename.strip()
    if not filename or len(filename) > 255:
        raise ValidationError("Invalid filename")

    # Check for path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValidationError("Invalid filename: path traversal detected")

    # Check file extension
    if '.' not in filename:
        raise ValidationError("File must have an extension")

    extension = filename.rsplit('.', 1)[1].lower()
    if extension not in allowed_extensions:
        raise ValidationError(
            f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Check file size
    try:
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise ValidationError(f"File too large. Maximum size: {max_size_mb}MB")

        if file_size == 0:
            raise ValidationError("File is empty")

    except (OSError, AttributeError):
        # If we can't determine size, let Flask handle it with MAX_CONTENT_LENGTH
        pass

    # Read first 2048 bytes for magic number validation
    try:
        file_header = file.read(2048)
        file.seek(0)  # Reset to beginning

        # Validate file content matches extension
        _validate_file_content(file_header, extension, filename)

    except Exception as e:
        logger.warning(f"Could not validate file content: {str(e)}")
        # Don't fail validation if we can't read content, but log the issue

def _validate_file_content(file_header: bytes, extension: str, filename: str):
    """Validate file content matches expected type using magic numbers"""

    # Define expected magic numbers for supported file types
    magic_numbers = {
        'wav': [b'RIFF', b'WAVE'],
        'mp3': [b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'],
        'm4a': [b'ftypM4A', b'ftypisom'],
        'aac': [b'\xff\xf1', b'\xff\xf9'],
        'flac': [b'fLaC'],
        'xml': [b'<?xml', b'<'],
        'drt': [b'<?xml', b'<']
    }

    # Check if file content matches expected type
    if extension in magic_numbers:
        expected_signatures = magic_numbers[extension]
        content_valid = False

        for signature in expected_signatures:
            if file_header.startswith(signature):
                content_valid = True
                break

        if not content_valid:
            # For XML/DRT files, be more lenient with whitespace
            if extension in ['xml', 'drt']:
                stripped_header = file_header.lstrip()
                for signature in expected_signatures:
                    if stripped_header.startswith(signature):
                        content_valid = True
                        break

        if not content_valid:
            raise ValidationError(
                f"File content does not match extension .{extension}. "
                f"File may be corrupted or have incorrect extension."
            )

    # Additional checks for suspicious content
    if b'<script' in file_header.lower() or b'javascript:' in file_header.lower():
        raise ValidationError("File contains potentially malicious content")

    # Check for embedded executables (basic check)
    executable_signatures = [b'MZ', b'PK', b'\x7fELF']
    for sig in executable_signatures:
        if sig in file_header:
            raise ValidationError("File contains executable content")

def validate_job_id(job_id: str) -> str:
    """Validate and sanitize job ID"""
    if not job_id:
        raise ValidationError("Job ID is required")

    if not isinstance(job_id, str):
        raise ValidationError("Job ID must be a string")

    # Remove any whitespace
    job_id = job_id.strip()

    if not job_id:
        raise ValidationError("Job ID cannot be empty")

    # Check length (UUIDs are typically 36 characters with hyphens)
    if len(job_id) > 100:
        raise ValidationError("Job ID is too long")

    # Check for valid characters (alphanumeric and hyphens for UUIDs)
    import re
    if not re.match(r'^[a-zA-Z0-9\-_]+$', job_id):
        raise ValidationError("Job ID contains invalid characters")

    return job_id

def validate_processing_options(options: Dict[str, Any]):
    """Validate processing options"""
    if not isinstance(options, dict):
        raise ValidationError("Processing options must be a dictionary")

    # Check for unexpected keys to prevent injection
    allowed_keys = {
        'enable_transcription', 'enable_speaker_diarization', 'remove_silence',
        'enable_ai_enhancements', 'enable_ai_enhancement', 'min_clip_length',
        'silence_threshold_db', 'speaker_change_threshold', 'quality_preset',
        'output_format', 'detect_filler_words', 'aggressive_filler_removal'
    }

    for key in options.keys():
        if key not in allowed_keys:
            raise ValidationError(f"Unknown option: '{key}'. Allowed options: {', '.join(allowed_keys)}")

    # Validate boolean options
    boolean_options = [
        'enable_transcription', 'enable_speaker_diarization', 'remove_silence',
        'enable_ai_enhancements', 'enable_ai_enhancement', 'detect_filler_words',
        'aggressive_filler_removal'
    ]
    for option in boolean_options:
        if option in options and not isinstance(options[option], bool):
            raise ValidationError(f"Option '{option}' must be a boolean")

    # Validate numeric options
    if 'min_clip_length' in options:
        value = options['min_clip_length']
        if not isinstance(value, (int, float)) or value < 1 or value > 300:
            raise ValidationError("min_clip_length must be between 1 and 300 seconds")

    if 'silence_threshold_db' in options:
        value = options['silence_threshold_db']
        if not isinstance(value, (int, float)) or value < -80 or value > -10:
            raise ValidationError("silence_threshold_db must be between -80 and -10 dB")

    if 'speaker_change_threshold' in options:
        value = options['speaker_change_threshold']
        if not isinstance(value, (int, float)) or value < 0.1 or value > 10:
            raise ValidationError("speaker_change_threshold must be between 0.1 and 10 seconds")

    # Validate string options
    if 'quality_preset' in options:
        value = options['quality_preset']
        allowed_presets = ['low', 'medium', 'high', 'ultra']
        if value not in allowed_presets:
            raise ValidationError(f"quality_preset must be one of: {', '.join(allowed_presets)}")

    if 'output_format' in options:
        value = options['output_format']
        allowed_formats = ['drt', 'xml', 'json']
        if value not in allowed_formats:
            raise ValidationError(f"output_format must be one of: {', '.join(allowed_formats)}")

def validate_json_request(request) -> Dict[str, Any]:
    """Validate and parse JSON request body"""
    if not request.is_json:
        raise ValidationError("Request must contain valid JSON")

    try:
        data = request.get_json()
    except Exception as e:
        raise ValidationError(f"Invalid JSON format: {str(e)}")

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValidationError("JSON body must be an object")

    # Check for excessively large JSON payloads
    if len(str(data)) > 10000:  # 10KB limit
        raise ValidationError("JSON payload too large")

    return data

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and other issues"""
    if not filename:
        raise ValidationError("Filename cannot be empty")

    # Remove path components
    filename = os.path.basename(filename)

    # Remove/replace dangerous characters
    import re
    filename = re.sub(r'[^\w\-_\.]', '_', filename)

    # Prevent hidden files
    if filename.startswith('.'):
        filename = 'file_' + filename[1:]

    # Ensure it's not too long
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250 - len(ext)] + ext

    return filename

class CircuitBreaker:
    """Simple circuit breaker for external API calls"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""

        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half-open'
            else:
                raise APIError("Service temporarily unavailable", status_code=503)

        try:
            result = func(*args, **kwargs)

            # Success - reset circuit breaker
            if self.state == 'half-open':
                self.state = 'closed'
                self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")

            raise e

# Create circuit breakers for external services
soniox_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=120)
openai_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=300)

def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """Decorator for applying circuit breaker to functions"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator

def setup_error_handlers(app):
    """Setup error handlers for Flask app"""

    @app.errorhandler(APIError)
    def handle_api_error_handler(error):
        return handle_api_error(error)

    @app.errorhandler(ValidationError)
    def handle_validation_error_handler(error):
        return handle_validation_error(error)

    @app.errorhandler(ProcessingError)
    def handle_processing_error_handler(error):
        return handle_processing_error(error)

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({
            'error': 'Resource not found',
            'status_code': 404
        }), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return jsonify({
            'error': 'Method not allowed',
            'status_code': 405
        }), 405

    @app.errorhandler(413)
    def handle_payload_too_large(error):
        return jsonify({
            'error': 'File too large',
            'status_code': 413,
            'message': 'Uploaded file exceeds the maximum allowed size'
        }), 413

    @app.errorhandler(500)
    def handle_internal_server_error(error):
        logger.error("Internal server error occurred", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'status_code': 500
        }), 500

def log_error_details(error: Exception, context: Dict[str, Any] = None):
    """Log detailed error information for debugging"""
    error_details = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc()
    }

    if context:
        error_details['context'] = context

    logger.error(f"Detailed error log: {error_details}")
    return error_details