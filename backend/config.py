import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    # Replicate Whisper - PRIMARY transcription provider (95% cheaper than Google Cloud)
    REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')  # Get from https://replicate.com/account

    # Google Cloud Speech-to-Text V1 - BACKUP transcription provider
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')  # Path to service account JSON
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')  # GCP project ID

    # OpenAI for AI enhancements (transcript improvement, highlights, summaries)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

    # Cloudinary for large video file uploads (>80MB)
    CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

    # AWS S3 Configuration (for chunked uploads of 3GB+ videos)
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    S3_VIDEO_BUCKET = os.getenv('S3_VIDEO_BUCKET', 'easyedit-videos')

    # S3 Upload Configuration
    S3_CHUNK_SIZE_MB = int(os.getenv('S3_CHUNK_SIZE_MB', '10'))  # 10MB chunks
    S3_MAX_FILE_SIZE_MB = int(os.getenv('S3_MAX_FILE_SIZE_MB', '5120'))  # 5GB max
    S3_PRESIGNED_URL_EXPIRATION = int(os.getenv('S3_PRESIGNED_URL_EXPIRATION', '86400'))  # 24 hours
    S3_MAX_CONCURRENT_CHUNKS = int(os.getenv('S3_MAX_CONCURRENT_CHUNKS', '5'))  # Parallel uploads
    S3_CLEANUP_STALE_UPLOADS_HOURS = int(os.getenv('S3_CLEANUP_STALE_UPLOADS_HOURS', '48'))

    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(32)
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    # Security validation
    if SECRET_KEY == 'dev-secret-key-change-in-production':
        raise ValueError("SECURITY ERROR: Default secret key detected! Set SECRET_KEY environment variable.")

    # File Processing Configuration
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '3500'))  # 3.5GB for video files
    MAX_CONTENT_LENGTH = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
    TEMP_FILE_RETENTION_HOURS = int(os.getenv('TEMP_FILE_RETENTION_HOURS', '24'))
    MAX_AUDIO_DURATION_HOURS = int(os.getenv('MAX_AUDIO_DURATION_HOURS', '6'))

    # Audio Processing Settings
    MIN_CLIP_LENGTH_SECONDS = int(os.getenv('MIN_CLIP_LENGTH_SECONDS', '5'))
    SILENCE_THRESHOLD_DB = int(os.getenv('SILENCE_THRESHOLD_DB', '-40'))
    SPEAKER_CHANGE_THRESHOLD_SECONDS = int(os.getenv('SPEAKER_CHANGE_THRESHOLD_SECONDS', '2'))

    # Audio Conversion Security (SECURITY HARDENED)
    MAX_AUDIO_CONVERSION_SIZE_MB = int(os.getenv('MAX_AUDIO_CONVERSION_SIZE_MB', '100'))
    MAX_CONCURRENT_AUDIO_CONVERSIONS = int(os.getenv('MAX_CONCURRENT_AUDIO_CONVERSIONS', '3'))
    AUDIO_CONVERSION_TIMEOUT_SECONDS = int(os.getenv('AUDIO_CONVERSION_TIMEOUT_SECONDS', '300'))
    MIN_DISK_SPACE_GB = float(os.getenv('MIN_DISK_SPACE_GB', '15.0'))  # Increased for video processing

    # Format-specific size limits (MB) - prevents resource exhaustion
    AUDIO_FORMAT_SIZE_LIMITS = {
        'wav': 100,   # Uncompressed, larger limit
        'mp3': 50,    # Compressed
        'm4a': 50,    # Compressed
        'aac': 50,    # Compressed
        'flac': 75,   # Lossless compression
    }

    # Upload and Temp Directories
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    TEMP_FOLDER = os.path.join(os.path.dirname(__file__), 'temp')

    # Allowed file extensions
    ALLOWED_AUDIO_EXTENSIONS = {'wav', 'mp3', 'm4a', 'aac', 'flac'}
    ALLOWED_TIMELINE_EXTENSIONS = {'xml'}  # Final Cut Pro 7 XML only
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'm4v'}  # Video file support

    # Replicate API Configuration
    # Max file size for direct upload to Replicate (SDK limit ~100MB, use 80MB for safety)
    # Files >80MB will be uploaded to Cloudinary first, then processed
    REPLICATE_MAX_FILE_SIZE_MB = int(os.getenv('REPLICATE_MAX_FILE_SIZE_MB', '80'))
    # Maximum file size for cloud processing (via Cloudinary) - 1GB limit
    CLOUDINARY_MAX_FILE_SIZE_MB = int(os.getenv('CLOUDINARY_MAX_FILE_SIZE_MB', '1024'))

    # Video Processing Configuration
    VIDEO_ANALYSIS_SAMPLE_RATE = int(os.getenv('VIDEO_ANALYSIS_SAMPLE_RATE', '16000'))  # 16kHz for speech recognition
    MIN_SEGMENT_DURATION_SECONDS = int(os.getenv('MIN_SEGMENT_DURATION_SECONDS', '5'))  # Minimum segment to keep
    REPEATED_TAKE_SIMILARITY_THRESHOLD = float(os.getenv('REPEATED_TAKE_SIMILARITY_THRESHOLD', '0.85'))  # Cosine similarity
    VIDEO_ENCODING_PRESET = os.getenv('VIDEO_ENCODING_PRESET', 'medium')  # FFmpeg: faster/fast/medium/slow
    VIDEO_CRF_QUALITY = int(os.getenv('VIDEO_CRF_QUALITY', '23'))  # 18=high quality, 28=low quality

    # Cloud Video Processing - HYBRID CLOUD ARCHITECTURE
    USE_CLOUD_VIDEO_PROCESSING = os.getenv('USE_CLOUD_VIDEO_PROCESSING', 'true').lower() == 'true'
    ENABLE_FFMPEG_FALLBACK = os.getenv('ENABLE_FFMPEG_FALLBACK', 'false').lower() == 'true'  # Fallback to local FFmpeg if cloud fails

    # AWS MediaConvert Configuration (for video transcoding)
    AWS_MEDIACONVERT_ROLE_ARN = os.getenv('AWS_MEDIACONVERT_ROLE_ARN')  # IAM role for MediaConvert
    AWS_MEDIACONVERT_QUEUE = os.getenv('AWS_MEDIACONVERT_QUEUE', 'Default')  # MediaConvert queue name
    AWS_MEDIACONVERT_ENDPOINT = os.getenv('AWS_MEDIACONVERT_ENDPOINT')  # Account-specific endpoint (auto-discovered if not set)

    # Replicate Models for Video Processing (audio extraction, merging, trimming)
    REPLICATE_AUDIO_MODEL = os.getenv('REPLICATE_AUDIO_MODEL', 'lucataco/extract-audio')  # Audio extraction for Whisper
    REPLICATE_VIDEO_MODEL_TRIM = os.getenv('REPLICATE_VIDEO_MODEL_TRIM', 'lucataco/trim-video')  # Video trimming
    REPLICATE_VIDEO_MODEL_MERGE = os.getenv('REPLICATE_VIDEO_MODEL_MERGE', 'foixasoftware/ffmpeg')  # Video concatenation

    # Video Upload & Transcoding Configuration (Phase 1)
    VIDEO_MAX_SIZE_MB = int(os.getenv('VIDEO_MAX_SIZE_MB', '3072'))  # 3GB max upload size
    VIDEO_ALLOWED_FORMATS = ['mp4', 'mov', 'mxf', 'avi']  # Supported video formats
    VIDEO_ALLOWED_CODECS = ['h264', 'hevc', 'prores', 'dnxhd', 'mpeg4']  # Supported video codecs
    VIDEO_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads', 'videos', 'original')
    VIDEO_PROXY_DIR = os.path.join(os.path.dirname(__file__), 'uploads', 'videos', 'proxy')

    # Transcoding Settings
    VIDEO_TRANSCODE_PRESET = os.getenv('VIDEO_TRANSCODE_PRESET', 'fast')  # FFmpeg preset: ultrafast/fast/medium/slow
    VIDEO_TRANSCODE_CRF = int(os.getenv('VIDEO_TRANSCODE_CRF', '23'))  # Quality (18-28, lower = better quality)
    VIDEO_PROXY_MAX_WIDTH = int(os.getenv('VIDEO_PROXY_MAX_WIDTH', '1920'))  # Max proxy width
    VIDEO_PROXY_MAX_HEIGHT = int(os.getenv('VIDEO_PROXY_MAX_HEIGHT', '1080'))  # Max proxy height
    VIDEO_PROXY_AUDIO_BITRATE = os.getenv('VIDEO_PROXY_AUDIO_BITRATE', '128k')  # Audio bitrate for proxy

    @staticmethod
    def init_app(app):
        # Ensure upload and temp directories exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.TEMP_FOLDER, exist_ok=True)

        # Ensure video directories exist (Phase 1)
        os.makedirs(Config.VIDEO_UPLOAD_DIR, exist_ok=True)
        os.makedirs(Config.VIDEO_PROXY_DIR, exist_ok=True)