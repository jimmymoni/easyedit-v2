"""
Authentication and authorization utilities for JWT token handling
"""

import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, current_app, g
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass

class AuthorizationError(Exception):
    """Custom exception for authorization errors"""
    pass

class JWTManager:
    """
    JWT token management for authentication
    """

    def __init__(self, app=None):
        self.app = app
        self.secret_key = None
        self.token_expiry_hours = 24
        self.refresh_token_expiry_days = 30

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize JWT manager with Flask app"""
        self.app = app
        self.secret_key = app.config.get('SECRET_KEY')
        self.token_expiry_hours = app.config.get('JWT_TOKEN_EXPIRY_HOURS', 24)
        self.refresh_token_expiry_days = app.config.get('JWT_REFRESH_TOKEN_EXPIRY_DAYS', 30)

        if not self.secret_key:
            raise ValueError("SECRET_KEY must be configured for JWT authentication")

    def generate_api_key(self) -> str:
        """Generate a secure API key"""
        return f"eev2_{secrets.token_urlsafe(32)}"

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.warning(f"Password verification failed: {str(e)}")
            return False

    def generate_token(self, user_id: str, email: str, role: str = 'user',
                      api_key: str = None) -> Dict[str, Any]:
        """
        Generate JWT access and refresh tokens
        """
        now = datetime.now(timezone.utc)

        # Access token payload
        access_payload = {
            'user_id': user_id,
            'email': email,
            'role': role,
            'api_key': api_key,
            'type': 'access',
            'iat': now,
            'exp': now + timedelta(hours=self.token_expiry_hours),
            'jti': secrets.token_hex(16)  # JWT ID for token revocation
        }

        # Refresh token payload
        refresh_payload = {
            'user_id': user_id,
            'type': 'refresh',
            'iat': now,
            'exp': now + timedelta(days=self.refresh_token_expiry_days),
            'jti': secrets.token_hex(16)
        }

        try:
            access_token = jwt.encode(access_payload, self.secret_key, algorithm='HS256')
            refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm='HS256')

            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': self.token_expiry_hours * 3600,
                'expires_at': access_payload['exp'].isoformat()
            }

        except Exception as e:
            logger.error(f"Token generation failed: {str(e)}")
            raise AuthenticationError("Failed to generate authentication token")

    def verify_token(self, token: str, token_type: str = 'access') -> Dict[str, Any]:
        """
        Verify and decode JWT token
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=['HS256'],
                options={'verify_exp': True}
            )

            # Verify token type
            if payload.get('type') != token_type:
                raise AuthenticationError(f"Invalid token type. Expected: {token_type}")

            return payload

        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise AuthenticationError("Token verification failed")

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Generate new access token using refresh token
        """
        try:
            # Verify refresh token
            payload = self.verify_token(refresh_token, 'refresh')
            user_id = payload['user_id']

            # Here you would typically fetch user details from database
            # For now, we'll create a basic token
            return self.generate_token(
                user_id=user_id,
                email=f"{user_id}@example.com",  # Would fetch from DB
                role='user'  # Would fetch from DB
            )

        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise AuthenticationError("Failed to refresh token")

# Global JWT manager instance
jwt_manager = JWTManager()

def require_auth(require_api_key: bool = False, roles: list = None):
    """
    Decorator to require authentication for routes

    Args:
        require_api_key: If True, requires valid API key in addition to JWT
        roles: List of required roles (e.g., ['admin', 'premium'])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Check for Authorization header
                auth_header = request.headers.get('Authorization')
                if not auth_header:
                    return jsonify({'error': 'Authorization header required'}), 401

                # Extract token
                try:
                    scheme, token = auth_header.split(' ', 1)
                    if scheme.lower() != 'bearer':
                        return jsonify({'error': 'Invalid authorization scheme. Use Bearer token'}), 401
                except ValueError:
                    return jsonify({'error': 'Invalid authorization header format'}), 401

                # Verify token
                payload = jwt_manager.verify_token(token)

                # Store user info in request context
                g.current_user = {
                    'user_id': payload['user_id'],
                    'email': payload['email'],
                    'role': payload.get('role', 'user'),
                    'api_key': payload.get('api_key')
                }

                # Check API key requirement
                if require_api_key and not payload.get('api_key'):
                    return jsonify({'error': 'API key required for this endpoint'}), 403

                # Check role requirements
                if roles and g.current_user['role'] not in roles:
                    return jsonify({'error': f'Insufficient permissions. Required roles: {roles}'}), 403

                return f(*args, **kwargs)

            except AuthenticationError as e:
                return jsonify({'error': str(e)}), 401
            except AuthorizationError as e:
                return jsonify({'error': str(e)}), 403
            except Exception as e:
                logger.error(f"Authentication middleware error: {str(e)}")
                return jsonify({'error': 'Authentication failed'}), 500

        return decorated_function
    return decorator

def require_api_key():
    """
    Decorator specifically for API key authentication (simpler than JWT)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = request.headers.get('X-API-Key') or request.args.get('api_key')

            if not api_key:
                return jsonify({'error': 'API key required'}), 401

            # Basic API key validation (starts with eev2_)
            if not api_key.startswith('eev2_') or len(api_key) < 20:
                return jsonify({'error': 'Invalid API key format'}), 401

            # Store API key in request context
            g.api_key = api_key

            return f(*args, **kwargs)

        return decorated_function
    return decorator

def get_current_user() -> Optional[Dict[str, Any]]:
    """Get current authenticated user from request context"""
    return getattr(g, 'current_user', None)

def generate_demo_token() -> Dict[str, Any]:
    """
    Generate a demo token for testing purposes
    """
    return jwt_manager.generate_token(
        user_id='demo_user',
        email='demo@easyedit.com',
        role='admin',
        api_key=jwt_manager.generate_api_key()
    )