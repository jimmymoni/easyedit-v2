"""
Speaker Identification Service
Processes timeline chunks with Sarvam API to identify speakers
Builds speaker continuity map across chunks for conversation tracking
"""

import logging
import os
import tempfile
import soundfile as sf
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from services.timeline_chunker import TimelineChunk
from services.elevenlabs_client import ElevenLabsClient
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    """Represents a speaker's utterance in the timeline"""
    speaker_id: str  # e.g., "SPEAKER_1", "SPEAKER_2"
    speaker_label: Optional[str] = None  # e.g., "Host", "Guest 1"
    start_time: float = 0.0  # Global timeline position
    end_time: float = 0.0    # Global timeline position
    duration: float = 0.0
    text: str = ""
    confidence: float = 0.0
    chunk_index: int = 0  # Which chunk this came from
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpeakerProfile:
    """Represents a unique speaker across all chunks"""
    speaker_id: str  # Unified ID across chunks
    speaker_label: Optional[str] = None
    total_speaking_time: float = 0.0
    segment_count: int = 0
    segments: List[SpeakerSegment] = field(default_factory=list)
    chunks_appeared: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            'speaker_id': self.speaker_id,
            'speaker_label': self.speaker_label,
            'total_speaking_time': self.total_speaking_time,
            'segment_count': self.segment_count,
            'chunks_appeared': self.chunks_appeared,
            'metadata': self.metadata
        }


class SpeakerIdentifierService:
    """Service for identifying speakers across timeline chunks"""

    def __init__(self, audio_file_path: str, language_code: str = "ml-IN"):
        """
        Initialize speaker identifier

        Args:
            audio_file_path: Path to full audio file
            language_code: Language for transcription (ml-IN, en-IN, etc.)
        """
        self.audio_file_path = audio_file_path
        self.language_code = language_code
        self.elevenlabs_client = ElevenLabsClient()

        # Results
        self.speaker_segments: List[SpeakerSegment] = []
        self.speaker_profiles: Dict[str, SpeakerProfile] = {}
        self.chunk_results: List[Dict[str, Any]] = []

    def process_chunks(
        self,
        chunks: List[TimelineChunk],
        enable_speaker_mapping: bool = True
    ) -> Tuple[List[SpeakerSegment], Dict[str, SpeakerProfile]]:
        """
        Process all chunks with Sarvam API for speaker identification

        Args:
            chunks: List of TimelineChunk objects
            enable_speaker_mapping: If True, map speakers across chunks

        Returns:
            Tuple of (speaker_segments, speaker_profiles)
        """
        logger.info(f"Processing {len(chunks)} chunks for speaker identification...")

        # Load audio file with soundfile
        try:
            audio_data, sample_rate = sf.read(self.audio_file_path)
            logger.info(f"Loaded audio: {len(audio_data)} samples at {sample_rate}Hz")
        except Exception as e:
            logger.error(f"Failed to load audio file: {e}")
            raise

        # Process each chunk
        for chunk in chunks:
            chunk_result = self._process_single_chunk(chunk, audio_data, sample_rate)
            if chunk_result:
                self.chunk_results.append(chunk_result)

        # Build speaker continuity map
        if enable_speaker_mapping:
            self._build_speaker_continuity_map()

        logger.info(
            f"Identified {len(self.speaker_profiles)} unique speakers "
            f"across {len(self.speaker_segments)} segments"
        )

        return self.speaker_segments, self.speaker_profiles

    def _process_single_chunk(
        self,
        chunk: TimelineChunk,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single chunk with Sarvam API

        Args:
            chunk: TimelineChunk to process
            audio_data: Full audio as numpy array
            sample_rate: Audio sample rate

        Returns:
            Chunk result dictionary or None if failed
        """
        logger.debug(
            f"Processing chunk {chunk.chunk_index}: "
            f"{chunk.start_time:.2f}s - {chunk.end_time:.2f}s"
        )

        # Extract audio segment for this chunk
        chunk_audio_path = None
        try:
            chunk_audio_path = self._extract_chunk_audio(chunk, audio_data, sample_rate)

            # Transcribe with ElevenLabs Scribe API (with speaker diarization)
            result = self.elevenlabs_client.transcribe_audio(
                audio_file_path=chunk_audio_path,
                enable_speaker_diarization=True,
                language_code=self.language_code
            )

            # Parse speaker segments from result
            segments = self._parse_speaker_segments(result, chunk)

            # Store segments
            self.speaker_segments.extend(segments)

            return {
                'chunk_index': chunk.chunk_index,
                'transcript': result.get('transcript', ''),
                'speakers': result.get('speakers', []),
                'segments': [self._segment_to_dict(s) for s in segments],
                'duration': result.get('duration', 0.0),
                'confidence': result.get('confidence', 0.0)
            }

        except Exception as e:
            logger.error(f"Failed to process chunk {chunk.chunk_index}: {e}")
            return None

        finally:
            # Cleanup temp file
            if chunk_audio_path and os.path.exists(chunk_audio_path):
                try:
                    os.remove(chunk_audio_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file: {e}")

    def _extract_chunk_audio(
        self,
        chunk: TimelineChunk,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> str:
        """
        Extract audio segment for chunk and save to temp file

        Args:
            chunk: TimelineChunk to extract
            audio_data: Full audio as numpy array
            sample_rate: Audio sample rate

        Returns:
            Path to temporary audio file
        """
        # Convert seconds to sample indices
        start_sample = int(chunk.start_time * sample_rate)
        end_sample = int(chunk.end_time * sample_rate)

        # Extract segment
        chunk_audio = audio_data[start_sample:end_sample]

        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.wav',
            prefix=f'chunk_{chunk.chunk_index}_'
        )
        sf.write(temp_file.name, chunk_audio, sample_rate)

        logger.debug(f"Extracted chunk audio: {temp_file.name}")
        return temp_file.name

    def _parse_speaker_segments(
        self,
        elevenlabs_result: Dict[str, Any],
        chunk: TimelineChunk
    ) -> List[SpeakerSegment]:
        """
        Parse speaker segments from ElevenLabs Scribe API result

        Args:
            elevenlabs_result: Result from ElevenLabs API
            chunk: TimelineChunk being processed

        Returns:
            List of SpeakerSegment objects
        """
        segments = []

        for segment in elevenlabs_result.get('segments', []):
            # Adjust timestamps to global timeline (add chunk offset)
            global_start = segment.get('start_time', 0.0) + chunk.original_timeline_offset
            global_end = segment.get('end_time', 0.0) + chunk.original_timeline_offset

            speaker_segment = SpeakerSegment(
                speaker_id=segment.get('speaker', 'UNKNOWN'),
                start_time=global_start,
                end_time=global_end,
                duration=global_end - global_start,
                text=segment.get('text', ''),
                confidence=segment.get('confidence', 0.0),
                chunk_index=chunk.chunk_index,
                metadata={
                    'chunk_local_start': segment.get('start_time', 0.0),
                    'chunk_local_end': segment.get('end_time', 0.0),
                    'word_count': len(segment.get('text', '').split())
                }
            )

            segments.append(speaker_segment)

        logger.debug(f"Parsed {len(segments)} speaker segments from chunk {chunk.chunk_index}")
        return segments

    def _build_speaker_continuity_map(self) -> None:
        """
        Build unified speaker profiles across chunks
        Maps "SPEAKER_1" in chunk 0 to same person in chunk 1, etc.
        """
        logger.info("Building speaker continuity map...")

        # Group segments by speaker ID (within each chunk, speakers are already labeled)
        # But we need to map speakers across chunks (SPEAKER_1 in chunk 0 = SPEAKER_1 in chunk 1)

        # For now, use simple heuristic: same speaker_id = same person
        # Future enhancement: use voice embedding similarity

        speaker_map: Dict[str, SpeakerProfile] = {}

        for segment in self.speaker_segments:
            speaker_id = segment.speaker_id

            if speaker_id not in speaker_map:
                # Create new speaker profile
                speaker_map[speaker_id] = SpeakerProfile(
                    speaker_id=speaker_id,
                    speaker_label=self._generate_speaker_label(speaker_id),
                    segments=[],
                    chunks_appeared=[]
                )

            profile = speaker_map[speaker_id]

            # Add segment to profile
            profile.segments.append(segment)
            profile.total_speaking_time += segment.duration
            profile.segment_count += 1

            # Track which chunks this speaker appeared in
            if segment.chunk_index not in profile.chunks_appeared:
                profile.chunks_appeared.append(segment.chunk_index)

        self.speaker_profiles = speaker_map

        logger.info(f"Built profiles for {len(speaker_map)} speakers")

        # Log speaker statistics
        for speaker_id, profile in speaker_map.items():
            logger.info(
                f"  {profile.speaker_label}: "
                f"{profile.total_speaking_time:.1f}s speaking time, "
                f"{profile.segment_count} segments, "
                f"appeared in {len(profile.chunks_appeared)} chunks"
            )

    def _generate_speaker_label(self, speaker_id: str) -> str:
        """Generate human-readable speaker label"""
        # Extract number from speaker_id (e.g., "SPEAKER_1" -> "Speaker 1")
        if speaker_id.startswith("SPEAKER_"):
            num = speaker_id.split("_")[-1]
            return f"Speaker {num}"
        return speaker_id

    def _segment_to_dict(self, segment: SpeakerSegment) -> Dict[str, Any]:
        """Convert SpeakerSegment to dictionary"""
        return {
            'speaker_id': segment.speaker_id,
            'speaker_label': segment.speaker_label,
            'start_time': segment.start_time,
            'end_time': segment.end_time,
            'duration': segment.duration,
            'text': segment.text,
            'confidence': segment.confidence,
            'chunk_index': segment.chunk_index
        }

    def get_conversation_flow(self) -> List[Dict[str, Any]]:
        """
        Get conversation flow (speaker turns in chronological order)

        Returns:
            List of speaker segments in order
        """
        # Sort segments by start time
        sorted_segments = sorted(self.speaker_segments, key=lambda s: s.start_time)

        return [self._segment_to_dict(s) for s in sorted_segments]

    def get_speaker_statistics(self) -> Dict[str, Any]:
        """Get comprehensive speaker statistics"""
        return {
            'total_speakers': len(self.speaker_profiles),
            'total_segments': len(self.speaker_segments),
            'speakers': [profile.to_dict() for profile in self.speaker_profiles.values()],
            'conversation_flow': self.get_conversation_flow()
        }


def identify_speakers_in_chunks(
    audio_file_path: str,
    chunks: List[TimelineChunk],
    language_code: str = "ml-IN"
) -> Tuple[List[SpeakerSegment], Dict[str, SpeakerProfile]]:
    """
    Convenience function to identify speakers in timeline chunks

    Args:
        audio_file_path: Path to audio file
        chunks: List of TimelineChunk objects
        language_code: Language code for transcription

    Returns:
        Tuple of (speaker_segments, speaker_profiles)
    """
    identifier = SpeakerIdentifierService(audio_file_path, language_code)
    return identifier.process_chunks(chunks)
