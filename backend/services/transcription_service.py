"""
Transcription Service Abstraction Layer

Provides a unified interface for multiple speech-to-text providers (Google Cloud, etc.)
Uses adapter pattern to normalize different API responses into a standard format.

Architecture Benefits:
- Provider-agnostic: Switch providers via configuration without code changes
- Extensible: Add new providers easily by implementing the interface
- Fallback support: Automatically switch to backup provider if primary fails
- Cost optimization: Use the best provider that meets quality and cost needs
- Future-proof: Ready for AWS, Azure, or other transcription services

Usage:
    # Automatic provider selection based on config
    service = TranscriptionServiceFactory.create()

    # Or specify provider explicitly
    service = TranscriptionServiceFactory.create(provider='google_cloud_stt_v2')

    # Transcribe audio with speaker diarization
    result = service.transcribe_audio(
        audio_file_path='/path/to/audio.wav',
        enable_speaker_diarization=True,
        language_code='ml-IN'  # Malayalam-India
    )
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
from config import Config

logger = logging.getLogger(__name__)


class TranscriptionService(ABC):
    """
    Abstract base class for speech-to-text transcription services

    All provider adapters must implement this interface to ensure
    consistent behavior and standardized response format.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the transcription service with API credentials"""
        self.api_key = api_key

    @abstractmethod
    def transcribe_audio(
        self,
        audio_file_path: str,
        enable_speaker_diarization: bool = True,
        language_code: str = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio file with optional speaker diarization

        Args:
            audio_file_path: Path to audio file
            enable_speaker_diarization: Enable speaker identification
            language_code: Language code (e.g., 'ml-IN', 'en-IN', None for auto-detect)

        Returns:
            Standardized transcription result:
            {
                'transcript': str,           # Full transcript text
                'segments': List[dict],      # Speaker segments with timestamps
                'speakers': List[str],       # Unique speaker IDs
                'duration': float,           # Audio duration in seconds
                'confidence': float,         # Overall confidence (0-1)
                'word_count': int,          # Total words transcribed
                'language': str,            # Detected/used language
                'provider': str             # Provider name (sarvam, etc.)
            }
        """
        pass

    @abstractmethod
    def check_api_status(self) -> bool:
        """
        Check if the transcription API is accessible

        Returns:
            bool: True if API is reachable and credentials are valid
        """
        pass

    def get_speaker_segments(self, transcription_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract speaker change points from transcription result

        Default implementation that works with standardized format.
        Providers can override if they have more efficient methods.

        Args:
            transcription_result: Result from transcribe_audio()

        Returns:
            List of speaker segments with timing and text
        """
        return transcription_result.get('segments', [])

    def get_silence_detection_hints(
        self,
        transcription_result: Dict[str, Any],
        min_gap_seconds: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Identify potential silence gaps from transcription timing

        Default implementation that works with standardized format.
        Providers can override if they have more efficient methods.

        Args:
            transcription_result: Result from transcribe_audio()
            min_gap_seconds: Minimum gap duration to consider as silence

        Returns:
            List of silence gaps with start/end times
        """
        silence_gaps = []
        segments = transcription_result.get('segments', [])

        for i in range(len(segments) - 1):
            current_end = segments[i].get('end', 0)
            next_start = segments[i + 1].get('start', 0)
            gap_duration = next_start - current_end

            if gap_duration >= min_gap_seconds:
                silence_gaps.append({
                    'start_time': current_end,
                    'end_time': next_start,
                    'duration': gap_duration,
                    'type': 'speech_gap'
                })

        return silence_gaps


class ReplicateWhisperAdapter(TranscriptionService):
    """Adapter for Replicate Whisper with Speaker Diarization (PRIMARY)"""

    def __init__(self, api_token: Optional[str] = None):
        super().__init__(api_key=api_token)
        from services.replicate_whisper_client import ReplicateWhisperClient
        self.client = ReplicateWhisperClient(api_token=api_token or Config.REPLICATE_API_TOKEN)
        self.provider_name = 'replicate_whisper'

    def transcribe_audio(
        self,
        audio_file_path: str,
        enable_speaker_diarization: bool = True,
        language_code: str = None
    ) -> Dict[str, Any]:
        """Transcribe using Replicate Whisper and normalize response"""
        # Default to English for simplicity (Whisper can auto-detect)
        lang = language_code or 'en'

        # Replicate client returns already normalized format
        result = self.client.transcribe_audio(
            audio_file_path=audio_file_path,
            enable_speaker_diarization=enable_speaker_diarization,
            language=lang
        )

        return result

    def check_api_status(self) -> bool:
        """Check Replicate API accessibility"""
        return self.client.check_api_status()


class TranscriptionServiceFactory:
    """
    Factory for creating transcription service instances

    Uses Replicate Whisper for all transcription (cost-effective, high-quality)

    Architecture allows easy addition of other providers in the future if needed.
    """

    PROVIDERS = {
        # Replicate Whisper (only provider)
        'replicate': ReplicateWhisperAdapter,
        'replicate_whisper': ReplicateWhisperAdapter,
        'whisper': ReplicateWhisperAdapter,
    }

    @classmethod
    def create(cls, provider: Optional[str] = None) -> TranscriptionService:
        """
        Create a transcription service instance

        Args:
            provider: Provider name ('replicate', 'whisper')
                     If None or 'auto', uses Replicate Whisper

        Returns:
            TranscriptionService instance (ReplicateWhisperAdapter)

        Raises:
            ValueError: If Replicate API token not configured
        """
        # Default to Replicate Whisper (only provider)
        selected_provider = provider or 'replicate_whisper'

        # Handle 'auto' for backwards compatibility
        if selected_provider == 'auto':
            selected_provider = 'replicate_whisper'

        # Validate provider
        if selected_provider not in cls.PROVIDERS:
            available = ', '.join(cls.PROVIDERS.keys())
            raise ValueError(
                f"Unknown provider: {selected_provider}. "
                f"Available providers: {available}"
            )

        # Check Replicate API token
        if not Config.REPLICATE_API_TOKEN:
            raise ValueError(
                "Replicate API token not configured. "
                "Set REPLICATE_API_TOKEN in your .env file to enable transcription.\n"
                "Get your token at: https://replicate.com/account\n"
                "Cost: ~$0.078 per hour of audio"
            )

        logger.info(f"Creating Replicate Whisper service")
        return ReplicateWhisperAdapter()

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of available providers

        Returns:
            List containing 'replicate_whisper' if token is configured
        """
        return ['replicate_whisper'] if Config.REPLICATE_API_TOKEN else []

    @classmethod
    def get_provider_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get information about Replicate Whisper provider

        Returns:
            Dictionary with provider details (cost, features, etc.)
        """
        return {
            'replicate_whisper': {
                'name': 'Replicate Whisper with Speaker Diarization',
                'cost_per_hour': 0.078,  # USD
                'cost_breakdown': {
                    'transcription_with_diarization': 0.078,
                },
                'currency': 'USD',
                'languages': '90+ languages (auto-detect)',
                'features': ['speaker_diarization', 'automatic_punctuation', 'word_timestamps', 'multilingual'],
                'best_for': 'Cost-effective transcription with speaker diarization',
                'credentials_env': 'REPLICATE_API_TOKEN',
                'signup_url': 'https://replicate.com/account',
                'configured': bool(Config.REPLICATE_API_TOKEN)
            }
        }
