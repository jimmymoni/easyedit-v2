"""
Conversation-Aware Merging Service
Intelligently merges speaker segments into engaging short-form content
- Groups related conversations
- Detects topic transitions
- Removes dead air and off-topic content
- Creates optimal cuts for flow
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from services.speaker_identifier import SpeakerSegment, SpeakerProfile
from models.timeline import Timeline, Track, Clip

logger = logging.getLogger(__name__)


@dataclass
class ConversationSegment:
    """Represents a cohesive conversation segment"""
    segment_id: str
    start_time: float
    end_time: float
    duration: float
    speakers: List[str] = field(default_factory=list)
    utterances: List[SpeakerSegment] = field(default_factory=list)
    topic: Optional[str] = None
    engagement_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'segment_id': self.segment_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'speakers': self.speakers,
            'utterance_count': len(self.utterances),
            'topic': self.topic,
            'engagement_score': self.engagement_score,
            'metadata': self.metadata
        }


class ConversationMergerService:
    """Service for merging speaker segments into cohesive conversations"""

    # Conversation detection parameters
    MAX_PAUSE_BETWEEN_TURNS = 3.0  # seconds - max pause to consider same conversation
    MIN_CONVERSATION_DURATION = 5.0  # seconds - minimum conversation length
    TOPIC_TRANSITION_THRESHOLD = 5.0  # seconds - silence that indicates topic change

    # Engagement scoring weights
    WEIGHT_SPEAKER_CHANGES = 0.3  # More speaker changes = more engaging
    WEIGHT_PACE = 0.3  # Faster pace = more engaging
    WEIGHT_DURATION = 0.2  # Optimal duration (not too short/long)
    WEIGHT_SPEAKER_BALANCE = 0.2  # Balanced speaking time = more engaging

    def __init__(
        self,
        speaker_segments: List[SpeakerSegment],
        speaker_profiles: Dict[str, SpeakerProfile],
        original_timeline: Timeline
    ):
        """
        Initialize conversation merger

        Args:
            speaker_segments: List of speaker segments from identification
            speaker_profiles: Speaker profiles map
            original_timeline: Original parsed timeline
        """
        self.speaker_segments = sorted(speaker_segments, key=lambda s: s.start_time)
        self.speaker_profiles = speaker_profiles
        self.original_timeline = original_timeline

        # Results
        self.conversation_segments: List[ConversationSegment] = []

    def create_conversation_segments(self) -> List[ConversationSegment]:
        """
        Group speaker utterances into cohesive conversation segments

        Returns:
            List of ConversationSegment objects
        """
        logger.info("Creating conversation segments from speaker utterances...")

        if not self.speaker_segments:
            logger.warning("No speaker segments to process")
            return []

        # Group utterances into conversations
        conversations = self._group_into_conversations()

        # Calculate engagement scores
        self._calculate_engagement_scores(conversations)

        # Sort by engagement (best first)
        conversations.sort(key=lambda c: c.engagement_score, reverse=True)

        self.conversation_segments = conversations

        logger.info(
            f"Created {len(conversations)} conversation segments "
            f"(avg score: {sum(c.engagement_score for c in conversations) / len(conversations):.2f})"
        )

        return conversations

    def _group_into_conversations(self) -> List[ConversationSegment]:
        """Group speaker utterances into conversation segments"""
        conversations = []
        current_conversation: List[SpeakerSegment] = []
        conversation_counter = 0

        for i, segment in enumerate(self.speaker_segments):
            if not current_conversation:
                # Start new conversation
                current_conversation.append(segment)
                continue

            # Check if this segment continues the conversation
            prev_segment = current_conversation[-1]
            pause = segment.start_time - prev_segment.end_time

            if pause <= self.MAX_PAUSE_BETWEEN_TURNS:
                # Continue conversation
                current_conversation.append(segment)
            else:
                # Long pause - end current conversation and start new one
                if current_conversation:
                    conv = self._create_conversation_from_utterances(
                        current_conversation,
                        f"CONV_{conversation_counter}"
                    )
                    if conv:
                        conversations.append(conv)
                        conversation_counter += 1

                # Start new conversation
                current_conversation = [segment]

        # Add final conversation
        if current_conversation:
            conv = self._create_conversation_from_utterances(
                current_conversation,
                f"CONV_{conversation_counter}"
            )
            if conv:
                conversations.append(conv)

        logger.debug(f"Grouped utterances into {len(conversations)} conversations")
        return conversations

    def _create_conversation_from_utterances(
        self,
        utterances: List[SpeakerSegment],
        segment_id: str
    ) -> Optional[ConversationSegment]:
        """Create ConversationSegment from list of utterances"""
        if not utterances:
            return None

        start_time = utterances[0].start_time
        end_time = utterances[-1].end_time
        duration = end_time - start_time

        # Filter out too-short conversations
        if duration < self.MIN_CONVERSATION_DURATION:
            return None

        # Get unique speakers
        speakers = list(set(u.speaker_id for u in utterances))

        # Detect topic (simple: use first few words)
        topic = self._detect_topic(utterances)

        return ConversationSegment(
            segment_id=segment_id,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            speakers=speakers,
            utterances=utterances,
            topic=topic,
            metadata={
                'utterance_count': len(utterances),
                'speaker_changes': self._count_speaker_changes(utterances),
                'average_utterance_length': sum(u.duration for u in utterances) / len(utterances)
            }
        )

    def _detect_topic(self, utterances: List[SpeakerSegment]) -> str:
        """Simple topic detection from first few words"""
        if not utterances:
            return "Unknown"

        # Get first 10 words
        words = []
        for utterance in utterances[:3]:  # First 3 utterances
            words.extend(utterance.text.split()[:5])
            if len(words) >= 10:
                break

        return " ".join(words[:10]) + "..."

    def _count_speaker_changes(self, utterances: List[SpeakerSegment]) -> int:
        """Count number of speaker changes in conversation"""
        changes = 0
        prev_speaker = None

        for utterance in utterances:
            if prev_speaker and utterance.speaker_id != prev_speaker:
                changes += 1
            prev_speaker = utterance.speaker_id

        return changes

    def _calculate_engagement_scores(self, conversations: List[ConversationSegment]) -> None:
        """Calculate engagement scores for conversations"""
        logger.debug("Calculating engagement scores...")

        for conv in conversations:
            # Component 1: Speaker changes (more = better, up to a point)
            speaker_changes = conv.metadata.get('speaker_changes', 0)
            changes_score = min(speaker_changes / 5.0, 1.0)  # Normalize to 0-1

            # Component 2: Pace (words per second)
            total_words = sum(len(u.text.split()) for u in conv.utterances)
            pace = total_words / conv.duration if conv.duration > 0 else 0
            pace_score = min(pace / 3.0, 1.0)  # Normalize (3 words/sec = ideal)

            # Component 3: Duration (optimal = 15-45 seconds)
            if 15 <= conv.duration <= 45:
                duration_score = 1.0
            elif conv.duration < 15:
                duration_score = conv.duration / 15.0
            else:  # > 45 seconds
                duration_score = max(1.0 - (conv.duration - 45) / 60.0, 0.1)

            # Component 4: Speaker balance (more balanced = better)
            balance_score = self._calculate_speaker_balance(conv)

            # Calculate weighted score
            conv.engagement_score = (
                self.WEIGHT_SPEAKER_CHANGES * changes_score +
                self.WEIGHT_PACE * pace_score +
                self.WEIGHT_DURATION * duration_score +
                self.WEIGHT_SPEAKER_BALANCE * balance_score
            )

            logger.debug(
                f"{conv.segment_id}: score={conv.engagement_score:.2f} "
                f"(changes={changes_score:.2f}, pace={pace_score:.2f}, "
                f"duration={duration_score:.2f}, balance={balance_score:.2f})"
            )

    def _calculate_speaker_balance(self, conv: ConversationSegment) -> float:
        """Calculate speaker balance score (0-1, higher = more balanced)"""
        if len(conv.speakers) < 2:
            return 0.5  # Neutral score for single speaker

        # Calculate speaking time per speaker
        speaker_times = defaultdict(float)
        for utterance in conv.utterances:
            speaker_times[utterance.speaker_id] += utterance.duration

        # Calculate balance (closer to equal = better)
        times = list(speaker_times.values())
        avg_time = sum(times) / len(times)
        variance = sum((t - avg_time) ** 2 for t in times) / len(times)
        std_dev = variance ** 0.5

        # Normalize: low std_dev = high balance
        balance = 1.0 - min(std_dev / avg_time, 1.0) if avg_time > 0 else 0.5

        return balance

    def create_optimized_timeline(
        self,
        top_n_segments: int = 5,
        target_duration: float = 90.0
    ) -> Timeline:
        """
        Create optimized timeline from best conversation segments

        Args:
            top_n_segments: Number of top segments to include
            target_duration: Target total duration (seconds)

        Returns:
            New Timeline object with optimized content
        """
        logger.info(
            f"Creating optimized timeline: top {top_n_segments} segments, "
            f"target {target_duration}s"
        )

        if not self.conversation_segments:
            logger.error("No conversation segments available")
            return self.original_timeline

        # Select best segments up to target duration
        selected_segments = self._select_segments_for_duration(
            self.conversation_segments,
            top_n_segments,
            target_duration
        )

        # Create new timeline
        optimized_timeline = Timeline(
            name=f"{self.original_timeline.name}_optimized",
            frame_rate=self.original_timeline.frame_rate,
            sample_rate=self.original_timeline.sample_rate,
            metadata={
                'original_duration': self.original_timeline.duration,
                'optimized_duration': sum(s.duration for s in selected_segments),
                'segment_count': len(selected_segments),
                'compression_ratio': sum(s.duration for s in selected_segments) / self.original_timeline.duration
            }
        )

        # Add audio track
        audio_track = Track(
            index=1,
            name="Audio 1",
            track_type="audio"
        )
        optimized_timeline.add_track(audio_track)

        # Add clips for each selected segment
        current_time = 0.0
        for i, segment in enumerate(selected_segments):
            clip = Clip(
                name=f"Segment_{i+1}",
                start_time=current_time,
                end_time=current_time + segment.duration,
                duration=segment.duration,
                track_index=1,
                media_start=segment.start_time,
                media_end=segment.end_time,
                metadata={
                    'conversation_id': segment.segment_id,
                    'engagement_score': segment.engagement_score,
                    'speakers': segment.speakers,
                    'topic': segment.topic
                }
            )
            audio_track.add_clip(clip)
            current_time += segment.duration

            # Add marker for segment start
            optimized_timeline.add_marker(
                clip.start_time,
                f"{segment.topic}" if segment.topic else f"Segment {i+1}",
                color="Orange"
            )

        # Calculate final duration
        optimized_timeline.calculate_duration()

        logger.info(
            f"Created optimized timeline: {optimized_timeline.duration:.2f}s "
            f"({len(selected_segments)} segments, "
            f"{optimized_timeline.duration / self.original_timeline.duration * 100:.1f}% of original)"
        )

        return optimized_timeline

    def _select_segments_for_duration(
        self,
        segments: List[ConversationSegment],
        top_n: int,
        target_duration: float
    ) -> List[ConversationSegment]:
        """Select top segments up to target duration"""
        selected = []
        total_duration = 0.0

        # Sort by engagement score (already sorted)
        for segment in segments[:top_n]:
            if total_duration + segment.duration <= target_duration:
                selected.append(segment)
                total_duration += segment.duration
            elif total_duration < target_duration * 0.9:  # Allow 10% over
                # Trim segment to fit
                remaining = target_duration - total_duration
                if remaining >= self.MIN_CONVERSATION_DURATION:
                    # Create trimmed segment
                    trimmed = ConversationSegment(
                        segment_id=segment.segment_id + "_trimmed",
                        start_time=segment.start_time,
                        end_time=segment.start_time + remaining,
                        duration=remaining,
                        speakers=segment.speakers,
                        utterances=segment.utterances,
                        topic=segment.topic,
                        engagement_score=segment.engagement_score,
                        metadata={**segment.metadata, 'trimmed': True}
                    )
                    selected.append(trimmed)
                    total_duration += remaining
                break

        # Sort selected segments by original start time (chronological order)
        selected.sort(key=lambda s: s.start_time)

        return selected

    def get_merger_statistics(self) -> Dict[str, Any]:
        """Get statistics about conversation merging"""
        if not self.conversation_segments:
            return {'total_conversations': 0}

        return {
            'total_conversations': len(self.conversation_segments),
            'average_duration': sum(c.duration for c in self.conversation_segments) / len(self.conversation_segments),
            'average_engagement_score': sum(c.engagement_score for c in self.conversation_segments) / len(self.conversation_segments),
            'total_speakers': len(self.speaker_profiles),
            'conversations': [c.to_dict() for c in self.conversation_segments[:10]]  # Top 10
        }
