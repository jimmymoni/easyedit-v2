import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    SONIOX_API_KEY = os.getenv('SONIOX_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(32)
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    # Security validation
    if SECRET_KEY == 'dev-secret-key-change-in-production':
        raise ValueError("SECURITY ERROR: Default secret key detected! Set SECRET_KEY environment variable.")

    # File Processing Configuration
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '500'))
    MAX_CONTENT_LENGTH = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
    TEMP_FILE_RETENTION_HOURS = int(os.getenv('TEMP_FILE_RETENTION_HOURS', '24'))
    MAX_AUDIO_DURATION_HOURS = int(os.getenv('MAX_AUDIO_DURATION_HOURS', '6'))

    # Audio Processing Settings
    MIN_CLIP_LENGTH_SECONDS = int(os.getenv('MIN_CLIP_LENGTH_SECONDS', '5'))
    SILENCE_THRESHOLD_DB = int(os.getenv('SILENCE_THRESHOLD_DB', '-40'))
    SPEAKER_CHANGE_THRESHOLD_SECONDS = int(os.getenv('SPEAKER_CHANGE_THRESHOLD_SECONDS', '2'))

    # Upload and Temp Directories
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    TEMP_FOLDER = os.path.join(os.path.dirname(__file__), 'temp')

    # Allowed file extensions
    ALLOWED_AUDIO_EXTENSIONS = {'wav', 'mp3', 'm4a', 'aac', 'flac'}
    ALLOWED_DRT_EXTENSIONS = {'drt', 'xml'}

    @staticmethod
    def init_app(app):
        # Ensure upload and temp directories exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.TEMP_FOLDER, exist_ok=True)