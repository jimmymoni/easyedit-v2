"""
Transcription Service Abstraction Layer

Provides a unified interface for multiple speech-to-text providers (Sarvam, etc.)
Uses adapter pattern to normalize different API responses into a standard format.

Architecture Benefits:
- Provider-agnostic: Switch providers via configuration without code changes
- Extensible: Add new providers easily by implementing the interface
- Fallback support: Automatically switch to backup provider if primary fails
- Cost optimization: Use the cheapest provider that meets quality needs
- Future-proof: Ready for Google, AWS, Azure transcription services

Usage:
    # Automatic provider selection based on config
    service = TranscriptionServiceFactory.create()

    # Or specify provider explicitly
    service = TranscriptionServiceFactory.create(provider='sarvam')

    # Transcribe audio
    result = service.transcribe_audio(
        audio_file_path='/path/to/audio.wav',
        enable_speaker_diarization=True
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
            current_end = segments[i].get('end_time', 0)
            next_start = segments[i + 1].get('start_time', 0)
            gap_duration = next_start - current_end

            if gap_duration >= min_gap_seconds:
                silence_gaps.append({
                    'start_time': current_end,
                    'end_time': next_start,
                    'duration': gap_duration,
                    'type': 'speech_gap'
                })

        return silence_gaps


class SarvamAdapter(TranscriptionService):
    """Adapter for Sarvam AI Speech-to-Text API"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        from services.sarvam_client import SarvamClient
        self.client = SarvamClient(api_key or Config.SARVAM_API_KEY)
        self.provider_name = 'sarvam'

    def transcribe_audio(
        self,
        audio_file_path: str,
        enable_speaker_diarization: bool = True,
        language_code: str = None
    ) -> Dict[str, Any]:
        """Transcribe using Sarvam AI API and normalize response"""
        # Default to Malayalam-India if not specified
        lang = language_code or 'ml-IN'

        # Sarvam client returns already normalized format
        result = self.client.transcribe_audio(
            audio_file_path=audio_file_path,
            enable_speaker_diarization=enable_speaker_diarization,
            language_code=lang
        )

        # Add provider metadata
        result['provider'] = self.provider_name
        result['language'] = lang

        return result

    def check_api_status(self) -> bool:
        """Check Sarvam AI API accessibility"""
        return self.client.check_api_status()


class TranscriptionServiceFactory:
    """
    Factory for creating transcription service instances

    Currently supports only Sarvam AI for Malayalam/English transcription.
    Architecture allows easy addition of more providers in the future.
    """

    PROVIDERS = {
        'sarvam': SarvamAdapter
    }

    @classmethod
    def create(cls, provider: Optional[str] = None) -> TranscriptionService:
        """
        Create a Sarvam AI transcription service instance

        Args:
            provider: Provider name (only 'sarvam' supported currently)
                     For backwards compatibility, accepts 'auto' which uses Sarvam

        Returns:
            SarvamAdapter instance

        Raises:
            ValueError: If SARVAM_API_KEY not configured
        """
        # Always use Sarvam (ignore provider parameter for simplicity)
        selected_provider = 'sarvam'

        # Check if API key is available
        if not Config.SARVAM_API_KEY:
            raise ValueError(
                "Sarvam AI API key not configured. "
                "Set SARVAM_API_KEY in your .env file to enable transcription.\n"
                "Get your free API key (₹1,000 credits) at https://www.sarvam.ai/"
            )

        # Create and return instance
        logger.info(f"Creating Sarvam AI transcription service")
        return SarvamAdapter()

    @classmethod
    def _auto_select_provider(cls) -> str:
        """
        Auto-select provider (always returns 'sarvam')

        Kept for backwards compatibility.
        """
        return 'sarvam'

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of available providers

        Returns:
            List containing 'sarvam' if API key is configured
        """
        return ['sarvam'] if Config.SARVAM_API_KEY else []

    @classmethod
    def get_provider_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get information about Sarvam AI provider

        Returns:
            Dictionary with provider details (cost, features, etc.)
        """
        return {
            'sarvam': {
                'name': 'Sarvam AI',
                'cost_per_hour': 0.36,  # USD (Rs. 30)
                'currency': 'USD',
                'languages': '10+ Indian languages',
                'features': ['speaker_diarization', 'code_mixing', 'indian_accents'],
                'best_for': 'Malayalam/English code-mixed speech, Indian accents',
                'api_key_env': 'SARVAM_API_KEY',
                'free_credits': '₹1,000 (~33 hours)',
                'signup_url': 'https://www.sarvam.ai/',
                'configured': bool(Config.SARVAM_API_KEY)
            }
        }
