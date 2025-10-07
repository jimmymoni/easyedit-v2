"""
Timeline Chunker Service
Intelligently splits timelines into 30-second chunks while respecting:
- Clip boundaries (avoid cutting mid-clip)
- Conversation flow (prefer cuts at silence/pauses)
- DRT metadata (maintain timecode references)
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from models.timeline import Timeline, Track, Clip

logger = logging.getLogger(__name__)


@dataclass
class TimelineChunk:
    """Represents a 30-second chunk of the timeline with metadata"""
    chunk_index: int
    start_time: float  # seconds
    end_time: float    # seconds
    duration: float    # seconds
    clips: List[Clip] = field(default_factory=list)
    audio_segment_path: Optional[str] = None  # Path to extracted audio
    original_timeline_offset: float = 0.0  # Offset in original timeline
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary for API response"""
        return {
            'chunk_index': self.chunk_index,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'clip_count': len(self.clips),
            'original_timeline_offset': self.original_timeline_offset,
            'metadata': self.metadata
        }


class TimelineChunkerService:
    """Service for intelligently chunking timelines for 30-second processing"""

    # Chunk configuration
    TARGET_CHUNK_DURATION = 30.0  # Target 30 seconds for Sarvam API
    MIN_CHUNK_DURATION = 25.0     # Minimum chunk size (avoid tiny chunks)
    MAX_CHUNK_DURATION = 30.0     # Maximum chunk size (API limit)

    # Overlap for speaker continuity detection
    CHUNK_OVERLAP_DURATION = 1.0  # 1 second overlap between chunks

    def __init__(self, timeline: Timeline, audio_file_path: str):
        """
        Initialize chunker with timeline and audio

        Args:
            timeline: Parsed Timeline object from DRT
            audio_file_path: Path to audio file
        """
        self.timeline = timeline
        self.audio_file_path = audio_file_path
        self.chunks: List[TimelineChunk] = []

    def create_chunks(
        self,
        silence_segments: Optional[List[Dict[str, Any]]] = None,
        respect_clip_boundaries: bool = True
    ) -> List[TimelineChunk]:
        """
        Split timeline into intelligent 30-second chunks

        Args:
            silence_segments: Optional list of silence segments from audio analysis
            respect_clip_boundaries: If True, prefer to split at clip boundaries

        Returns:
            List of TimelineChunk objects
        """
        logger.info(f"Chunking timeline: {self.timeline.duration:.2f}s total duration")

        # Calculate duration
        if self.timeline.duration == 0:
            self.timeline.calculate_duration()

        # Get all audio clips sorted by time
        audio_clips = self._get_sorted_audio_clips()

        if not audio_clips:
            logger.warning("No audio clips found in timeline")
            return []

        # Generate chunk boundaries
        chunk_boundaries = self._calculate_chunk_boundaries(
            audio_clips,
            silence_segments,
            respect_clip_boundaries
        )

        # Create chunks from boundaries
        self.chunks = self._create_chunks_from_boundaries(chunk_boundaries, audio_clips)

        logger.info(f"Created {len(self.chunks)} chunks from timeline")
        return self.chunks

    def _get_sorted_audio_clips(self) -> List[Clip]:
        """Get all audio clips from timeline, sorted by start time"""
        audio_tracks = self.timeline.get_tracks_by_type('audio')
        all_clips = []

        for track in audio_tracks:
            all_clips.extend(track.clips)

        # Sort by start time
        all_clips.sort(key=lambda c: c.start_time)

        logger.debug(f"Found {len(all_clips)} audio clips across {len(audio_tracks)} tracks")
        return all_clips

    def _calculate_chunk_boundaries(
        self,
        audio_clips: List[Clip],
        silence_segments: Optional[List[Dict[str, Any]]],
        respect_clip_boundaries: bool
    ) -> List[Tuple[float, float]]:
        """
        Calculate optimal chunk boundaries

        Returns:
            List of (start_time, end_time) tuples
        """
        boundaries = []
        current_time = 0.0
        total_duration = self.timeline.duration

        while current_time < total_duration:
            # Target end time
            target_end = min(current_time + self.TARGET_CHUNK_DURATION, total_duration)

            # Find optimal split point near target
            split_point = self._find_optimal_split_point(
                current_time,
                target_end,
                audio_clips,
                silence_segments,
                respect_clip_boundaries
            )

            # Create boundary
            boundaries.append((current_time, split_point))

            # Move to next chunk (with small overlap for speaker continuity)
            current_time = split_point - self.CHUNK_OVERLAP_DURATION
            current_time = max(current_time, split_point)  # Ensure we move forward

        logger.debug(f"Calculated {len(boundaries)} chunk boundaries")
        return boundaries

    def _find_optimal_split_point(
        self,
        start_time: float,
        target_end: float,
        audio_clips: List[Clip],
        silence_segments: Optional[List[Dict[str, Any]]],
        respect_clip_boundaries: bool
    ) -> float:
        """
        Find the best point to split the timeline near target_end

        Priority:
        1. Silence segments (natural pauses)
        2. Clip boundaries (avoid cutting mid-clip)
        3. Target duration (if no good alternatives)
        """
        # Search window around target (±2 seconds)
        search_start = target_end - 2.0
        search_end = min(target_end + 2.0, self.timeline.duration)

        # Option 1: Look for silence segments in search window
        if silence_segments:
            silence_split = self._find_silence_split_point(
                search_start, search_end, silence_segments
            )
            if silence_split:
                logger.debug(f"Split at silence: {silence_split:.2f}s")
                return silence_split

        # Option 2: Look for clip boundaries in search window
        if respect_clip_boundaries:
            clip_split = self._find_clip_boundary_split_point(
                search_start, search_end, audio_clips
            )
            if clip_split:
                logger.debug(f"Split at clip boundary: {clip_split:.2f}s")
                return clip_split

        # Option 3: Use target end (hard split)
        logger.debug(f"Split at target: {target_end:.2f}s (no optimal point found)")
        return target_end

    def _find_silence_split_point(
        self,
        search_start: float,
        search_end: float,
        silence_segments: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Find silence segment in search window"""
        for silence in silence_segments:
            silence_mid = (silence['start_time'] + silence['end_time']) / 2
            if search_start <= silence_mid <= search_end:
                # Split in middle of silence
                return silence_mid
        return None

    def _find_clip_boundary_split_point(
        self,
        search_start: float,
        search_end: float,
        audio_clips: List[Clip]
    ) -> Optional[float]:
        """Find clip boundary (end) in search window"""
        for clip in audio_clips:
            if search_start <= clip.end_time <= search_end:
                # Split at clip end
                return clip.end_time
        return None

    def _create_chunks_from_boundaries(
        self,
        boundaries: List[Tuple[float, float]],
        audio_clips: List[Clip]
    ) -> List[TimelineChunk]:
        """Create TimelineChunk objects from boundaries"""
        chunks = []

        for idx, (start, end) in enumerate(boundaries):
            # Get clips that overlap with this chunk
            chunk_clips = [
                clip for clip in audio_clips
                if not (clip.end_time <= start or clip.start_time >= end)
            ]

            # Create chunk
            chunk = TimelineChunk(
                chunk_index=idx,
                start_time=start,
                end_time=end,
                duration=end - start,
                clips=chunk_clips,
                original_timeline_offset=start,
                metadata={
                    'clip_count': len(chunk_clips),
                    'has_overlap': idx > 0 and start < boundaries[idx - 1][1],
                }
            )

            chunks.append(chunk)

            logger.debug(
                f"Chunk {idx}: {start:.2f}s-{end:.2f}s ({chunk.duration:.2f}s, "
                f"{len(chunk_clips)} clips)"
            )

        return chunks

    def get_chunk_statistics(self) -> Dict[str, Any]:
        """Get statistics about the chunking operation"""
        if not self.chunks:
            return {
                'total_chunks': 0,
                'error': 'No chunks created'
            }

        durations = [chunk.duration for chunk in self.chunks]

        return {
            'total_chunks': len(self.chunks),
            'original_duration': self.timeline.duration,
            'average_chunk_duration': sum(durations) / len(durations),
            'min_chunk_duration': min(durations),
            'max_chunk_duration': max(durations),
            'total_clips': sum(len(chunk.clips) for chunk in self.chunks),
            'chunks': [chunk.to_dict() for chunk in self.chunks]
        }


def create_timeline_chunks(
    timeline: Timeline,
    audio_file_path: str,
    silence_segments: Optional[List[Dict[str, Any]]] = None
) -> List[TimelineChunk]:
    """
    Convenience function to create timeline chunks

    Args:
        timeline: Timeline object
        audio_file_path: Path to audio file
        silence_segments: Optional silence segments from audio analysis

    Returns:
        List of TimelineChunk objects
    """
    chunker = TimelineChunkerService(timeline, audio_file_path)
    return chunker.create_chunks(silence_segments=silence_segments)
