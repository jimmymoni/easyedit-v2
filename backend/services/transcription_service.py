"""
Transcription Service Abstraction Layer

Provides a unified interface for multiple speech-to-text providers (Soniox, Sarvam, etc.)
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
                'provider': str             # Provider name (soniox, sarvam, etc.)
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


class SonioxAdapter(TranscriptionService):
    """Adapter for Soniox Speech-to-Text API"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        from services.soniox_client import SonioxClient
        self.client = SonioxClient(api_key or Config.SONIOX_API_KEY)
        self.provider_name = 'soniox'

    def transcribe_audio(
        self,
        audio_file_path: str,
        enable_speaker_diarization: bool = True,
        language_code: str = None
    ) -> Dict[str, Any]:
        """Transcribe using Soniox API and normalize response"""
        # Soniox client returns already normalized format
        result = self.client.transcribe_audio(
            audio_file_path=audio_file_path,
            enable_speaker_diarization=enable_speaker_diarization
        )

        # Add provider metadata
        result['provider'] = self.provider_name
        result['language'] = language_code or 'auto'

        return result

    def check_api_status(self) -> bool:
        """Check Soniox API accessibility"""
        return self.client.check_api_status()


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

    Handles provider selection based on:
    1. Explicit provider parameter
    2. TRANSCRIPTION_PROVIDER environment variable
    3. Available API keys (fallback logic)
    """

    PROVIDERS = {
        'soniox': SonioxAdapter,
        'sarvam': SarvamAdapter
    }

    @classmethod
    def create(cls, provider: Optional[str] = None) -> TranscriptionService:
        """
        Create a transcription service instance

        Args:
            provider: Provider name ('soniox', 'sarvam', 'auto', or None)
                     If None, uses TRANSCRIPTION_PROVIDER from config
                     If 'auto', selects based on available API keys

        Returns:
            TranscriptionService instance

        Raises:
            ValueError: If provider is invalid or no API keys available
        """
        # Determine which provider to use
        selected_provider = provider or Config.TRANSCRIPTION_PROVIDER

        # Handle 'auto' selection based on available API keys
        if selected_provider == 'auto':
            selected_provider = cls._auto_select_provider()

        # Validate provider
        if selected_provider not in cls.PROVIDERS:
            available = ', '.join(cls.PROVIDERS.keys())
            raise ValueError(
                f"Invalid transcription provider: '{selected_provider}'. "
                f"Available providers: {available}, auto"
            )

        # Get provider class and check API key
        adapter_class = cls.PROVIDERS[selected_provider]

        # Check if API key is available
        if selected_provider == 'soniox' and not Config.SONIOX_API_KEY:
            raise ValueError(
                "Soniox provider selected but SONIOX_API_KEY not configured. "
                "Set SONIOX_API_KEY in your .env file or choose a different provider."
            )

        if selected_provider == 'sarvam' and not Config.SARVAM_API_KEY:
            raise ValueError(
                "Sarvam provider selected but SARVAM_API_KEY not configured. "
                "Set SARVAM_API_KEY in your .env file or choose a different provider."
            )

        # Create and return instance
        logger.info(f"Creating transcription service with provider: {selected_provider}")
        return adapter_class()

    @classmethod
    def _auto_select_provider(cls) -> str:
        """
        Automatically select the best available provider

        Priority order:
        1. Sarvam (cheaper, optimized for Indian languages)
        2. Soniox (fallback, more expensive but high quality)

        Returns:
            Provider name

        Raises:
            ValueError: If no API keys are configured
        """
        # Prefer Sarvam (cheaper and optimized for Malayalam/English)
        if Config.SARVAM_API_KEY:
            logger.info("Auto-selected Sarvam AI (cost-effective, Indian language optimized)")
            return 'sarvam'

        # Fallback to Soniox
        if Config.SONIOX_API_KEY:
            logger.info("Auto-selected Soniox (Sarvam API key not available)")
            return 'soniox'

        # No providers available
        raise ValueError(
            "No transcription API keys configured. "
            "Please set SARVAM_API_KEY or SONIOX_API_KEY in your .env file. "
            "Sarvam is recommended (66% cheaper, optimized for Malayalam/English)."
        )

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of providers with valid API keys configured

        Returns:
            List of available provider names
        """
        available = []

        if Config.SONIOX_API_KEY:
            available.append('soniox')

        if Config.SARVAM_API_KEY:
            available.append('sarvam')

        return available

    @classmethod
    def get_provider_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all supported providers

        Returns:
            Dictionary with provider details (cost, features, etc.)
        """
        return {
            'soniox': {
                'name': 'Soniox',
                'cost_per_hour': 1.02,  # USD
                'currency': 'USD',
                'languages': '60+',
                'features': ['speaker_diarization', 'multilingual', 'high_accuracy'],
                'best_for': 'High-accuracy multilingual transcription',
                'api_key_env': 'SONIOX_API_KEY',
                'configured': bool(Config.SONIOX_API_KEY)
            },
            'sarvam': {
                'name': 'Sarvam AI',
                'cost_per_hour': 0.36,  # USD (Rs. 30)
                'currency': 'USD',
                'languages': '10+ Indian languages',
                'features': ['speaker_diarization', 'code_mixing', 'indian_accents'],
                'best_for': 'Malayalam/English code-mixed speech, Indian accents',
                'api_key_env': 'SARVAM_API_KEY',
                'free_credits': '₹1,000 (~33 hours)',
                'configured': bool(Config.SARVAM_API_KEY)
            }
        }
