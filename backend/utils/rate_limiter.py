"""
Rate limiting utilities using Flask-Limiter with Redis backend
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request, g, current_app
import redis
from typing import Optional, Callable
import logging
import time

logger = logging.getLogger(__name__)

class RateLimitConfig:
    """Rate limiting configuration constants"""

    # General API limits
    GENERAL_RATE_LIMIT = "60 per minute, 1000 per hour"

    # Endpoint-specific limits
    UPLOAD_RATE_LIMIT = "5 per minute, 50 per hour"
    PROCESSING_RATE_LIMIT = "2 per minute, 20 per hour"
    DOWNLOAD_RATE_LIMIT = "10 per minute, 100 per hour"
    STATUS_RATE_LIMIT = "30 per minute, 300 per hour"
    AUTH_RATE_LIMIT = "10 per minute, 100 per hour"

    # Premium user limits (higher than standard)
    PREMIUM_UPLOAD_RATE_LIMIT = "20 per minute, 200 per hour"
    PREMIUM_PROCESSING_RATE_LIMIT = "10 per minute, 100 per hour"
    PREMIUM_GENERAL_RATE_LIMIT = "300 per minute, 5000 per hour"

    # Admin limits (very high)
    ADMIN_RATE_LIMIT = "1000 per minute, 50000 per hour"

def get_rate_limit_key() -> str:
    """
    Generate rate limit key based on user authentication status
    Uses API key, user ID, or IP address in order of preference
    """
    # Check for API key first (most specific)
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return f"api_key:{api_key}"

    # Check for authenticated user
    current_user = getattr(g, 'current_user', None)
    if current_user and current_user.get('user_id'):
        return f"user:{current_user['user_id']}"

    # Fall back to IP address
    return f"ip:{get_remote_address()}"

def get_user_tier() -> str:
    """
    Determine user tier for rate limiting (free, premium, admin)
    """
    current_user = getattr(g, 'current_user', None)
    if current_user:
        role = current_user.get('role', 'user')
        if role == 'admin':
            return 'admin'
        elif role in ['premium', 'pro', 'enterprise']:
            return 'premium'

    return 'free'

def dynamic_rate_limit() -> str:
    """
    Dynamic rate limit based on user tier
    """
    tier = get_user_tier()

    if tier == 'admin':
        return RateLimitConfig.ADMIN_RATE_LIMIT
    elif tier == 'premium':
        return RateLimitConfig.PREMIUM_GENERAL_RATE_LIMIT
    else:
        return RateLimitConfig.GENERAL_RATE_LIMIT

def upload_rate_limit() -> str:
    """Dynamic upload rate limit"""
    tier = get_user_tier()

    if tier == 'admin':
        return RateLimitConfig.ADMIN_RATE_LIMIT
    elif tier == 'premium':
        return RateLimitConfig.PREMIUM_UPLOAD_RATE_LIMIT
    else:
        return RateLimitConfig.UPLOAD_RATE_LIMIT

def processing_rate_limit() -> str:
    """Dynamic processing rate limit"""
    tier = get_user_tier()

    if tier == 'admin':
        return RateLimitConfig.ADMIN_RATE_LIMIT
    elif tier == 'premium':
        return RateLimitConfig.PREMIUM_PROCESSING_RATE_LIMIT
    else:
        return RateLimitConfig.PROCESSING_RATE_LIMIT

class CustomLimiter:
    """
    Enhanced rate limiter with Redis backend and custom features
    """

    def __init__(self, app=None):
        self.limiter = None
        self.redis_client = None

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize rate limiter with Flask app"""
        # Configure Redis connection
        redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')

        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis for rate limiting")

            # Initialize Flask-Limiter with Redis storage
            self.limiter = Limiter(
                key_func=get_rate_limit_key,
                storage_uri=redis_url,
                default_limits=[dynamic_rate_limit],
                headers_enabled=True,  # Include rate limit headers in response
                swallow_errors=True,   # Don't crash app on rate limit errors
                on_breach=self._on_rate_limit_breach
            )
            self.limiter.init_app(app)

        except redis.ConnectionError:
            logger.warning("Redis not available, using in-memory rate limiting")
            # Fallback to in-memory storage
            self.limiter = Limiter(
                key_func=get_rate_limit_key,
                default_limits=[dynamic_rate_limit],
                headers_enabled=True,
                swallow_errors=True,
                on_breach=self._on_rate_limit_breach
            )
            self.limiter.init_app(app)

    def _on_rate_limit_breach(self, request_limit):
        """Handle rate limit breaches"""
        client_id = get_rate_limit_key()
        endpoint = request.endpoint or 'unknown'

        logger.warning(
            f"Rate limit exceeded for {client_id} on {endpoint}: "
            f"{request_limit.limit} {request_limit.per_second} seconds"
        )

        # Could implement additional actions here:
        # - Send alerts for repeated violations
        # - Implement progressive penalties
        # - Log to security monitoring system

    def get_usage_stats(self, key: str) -> dict:
        """Get current usage statistics for a key"""
        if not self.redis_client:
            return {}

        try:
            # Get all rate limit keys for this client
            pattern = f"LIMITER:{key}:*"
            keys = self.redis_client.keys(pattern)

            stats = {}
            for redis_key in keys:
                value = self.redis_client.get(redis_key)
                ttl = self.redis_client.ttl(redis_key)

                # Extract limit info from key
                parts = redis_key.split(':')
                if len(parts) >= 3:
                    limit_type = parts[-1]
                    stats[limit_type] = {
                        'current_usage': int(value) if value else 0,
                        'ttl_seconds': ttl,
                        'reset_time': time.time() + ttl if ttl > 0 else None
                    }

            return stats

        except Exception as e:
            logger.error(f"Failed to get usage stats: {str(e)}")
            return {}

    def reset_limits(self, key: str) -> bool:
        """Reset rate limits for a specific key (admin function)"""
        if not self.redis_client:
            return False

        try:
            pattern = f"LIMITER:{key}:*"
            keys = self.redis_client.keys(pattern)

            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Reset rate limits for {key}: {deleted} keys deleted")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to reset limits for {key}: {str(e)}")
            return False

    def is_rate_limited(self, key: str, limit: str) -> bool:
        """Check if key would be rate limited for given limit"""
        try:
            # This is a simplified check - in practice you'd use limiter's internal logic
            return False
        except Exception:
            return False

# Global rate limiter instance
rate_limiter = CustomLimiter()

def require_rate_limit(limit: str):
    """
    Decorator to apply specific rate limit to a route

    Args:
        limit: Rate limit string (e.g., "5 per minute")
    """
    def decorator(f):
        if rate_limiter.limiter:
            return rate_limiter.limiter.limit(limit)(f)
        return f
    return decorator

def get_rate_limit_status() -> dict:
    """Get current rate limit status for the requesting client"""
    key = get_rate_limit_key()
    tier = get_user_tier()

    stats = rate_limiter.get_usage_stats(key) if rate_limiter else {}

    return {
        'client_key': key.split(':')[0],  # Don't expose full key
        'tier': tier,
        'limits': {
            'general': dynamic_rate_limit(),
            'upload': upload_rate_limit(),
            'processing': processing_rate_limit(),
            'download': RateLimitConfig.DOWNLOAD_RATE_LIMIT,
            'status': RateLimitConfig.STATUS_RATE_LIMIT
        },
        'current_usage': stats,
        'timestamp': time.time()
    }