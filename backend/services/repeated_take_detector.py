"""
Repeated Take Detector Service
Detects repeated takes, false starts, and mistakes in video transcriptions
MVP: Pattern-based detection (future: add embeddings for similarity)
"""
import logging
import re
import uuid
from typing import Dict, List, Any, Optional
from config import Config

logger = logging.getLogger(__name__)


class RepeatedTakeDetector:
    """Detect repeated takes and mistakes using pattern matching"""

    def __init__(self):
        # Repetition marker phrases
        self.repetition_markers = [
            r'\bagain\b',
            r'\bone more time\b',
            r'\btry that again\b',
            r'\blet me try again\b',
            r'\blet me start over\b',
            r'\bstart over\b',
            r'\bredo\b',
            r'\bretake\b',
            r'\btake two\b',
            r'\btake three\b',
            r'\bonce more\b',
            r'\bfrom the top\b',
        ]

        # False start indicators
        self.false_start_patterns = [
            r'\bwait\s+no\b',
            r'\bactually\b.*\blet me\b',
            r'\bsorry\s+let me\b',
            r'\bno\s+wait\b',
            r'\buh\s+let me\b',
            r'\blet me just\b',
            r'\bhold on\b',
        ]

        # Filler words for quality scoring
        self.filler_words = ['um', 'uh', 'like', 'you know', 'basically', 'actually', 'literally']

    def detect_repeated_takes(
        self,
        transcription_data: Dict,
        video_info: Dict
    ) -> Dict[str, Any]:
        """
        Main detection pipeline - finds repeated takes and mistakes

        Args:
            transcription_data: Full transcription from Replicate Whisper
            video_info: Video metadata (duration, etc.)

        Returns:
            {
                'segments': List of segments with keep/remove actions,
                'stats': Overall statistics,
                'detected_patterns': Pattern counts
            }
        """
        try:
            logger.info("Starting repeated take detection")

            # Step 1: Segment the transcript into logical chunks
            segments = self._segment_transcript(transcription_data)
            logger.info(f"Created {len(segments)} segments from transcript")

            # Step 2: Detect repetition markers
            segments_with_markers = self._detect_repetition_markers(segments)

            # Step 3: Detect false starts
            segments_with_false_starts = self._detect_false_starts(segments_with_markers)

            # Step 4: Detect filler-heavy sections
            segments_with_quality = self._score_segment_quality(segments_with_false_starts)

            # Step 5: Make keep/remove decisions
            final_segments = self._make_decisions(segments_with_quality)

            # Step 6: Calculate stats
            stats = self._calculate_stats(final_segments, video_info)

            # Count detected patterns
            detected_patterns = {
                'repetition_markers': sum(1 for s in final_segments if s.get('has_repetition_marker')),
                'false_starts': sum(1 for s in final_segments if s.get('has_false_start')),
                'filler_heavy': sum(1 for s in final_segments if s.get('filler_density', 0) > 0.15),
            }

            logger.info(f"Detection complete: {stats['segments_to_remove']} segments marked for removal")

            return {
                'segments': final_segments,
                'stats': stats,
                'detected_patterns': detected_patterns
            }

        except Exception as e:
            logger.error(f"Error in repeated take detection: {str(e)}")
            return {
                'segments': [],
                'stats': {},
                'detected_patterns': {},
                'error': str(e)
            }

    def _segment_transcript(self, transcription_data: Dict) -> List[Dict]:
        """
        Group transcript into logical segments based on:
        - Speaker changes
        - Long pauses (>2 seconds)
        - Natural sentence boundaries
        """
        segments = []
        transcript_segments = transcription_data.get('segments', [])

        if not transcript_segments:
            logger.warning("No segments in transcription data")
            return []

        # Group segments by speaker and pauses
        current_group = []
        current_speaker = None
        last_end_time = 0

        for seg in transcript_segments:
            speaker = seg.get('speaker', 'Speaker 1')
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            text = seg.get('text', '').strip()

            # Check if we should start a new segment
            speaker_changed = current_speaker is not None and speaker != current_speaker
            long_pause = start - last_end_time > 2.0  # >2 second gap

            if (speaker_changed or long_pause) and current_group:
                # Create segment from current group
                segments.append(self._create_segment_from_group(current_group, current_speaker))
                current_group = []

            # Add to current group
            current_group.append(seg)
            current_speaker = speaker
            last_end_time = end

        # Add final group
        if current_group:
            segments.append(self._create_segment_from_group(current_group, current_speaker))

        return segments

    def _create_segment_from_group(self, group: List[Dict], speaker: str) -> Dict:
        """Create a segment from a group of transcript segments"""
        if not group:
            return {}

        start_time = group[0].get('start', 0)
        end_time = group[-1].get('end', 0)
        texts = [seg.get('text', '').strip() for seg in group]
        combined_text = ' '.join(texts)

        return {
            'id': str(uuid.uuid4()),
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'text': combined_text,
            'speaker': speaker,
            'action': 'keep',  # Default action
            'reason': '',
            'confidence': 0.5,  # Default confidence
            'has_repetition_marker': False,
            'has_false_start': False,
            'filler_density': 0.0
        }

    def _detect_repetition_markers(self, segments: List[Dict]) -> List[Dict]:
        """Find explicit restart phrases in segments"""
        for segment in segments:
            text_lower = segment['text'].lower()

            # Check for repetition markers
            for pattern in self.repetition_markers:
                if re.search(pattern, text_lower):
                    segment['has_repetition_marker'] = True
                    logger.debug(f"Repetition marker found in segment at {segment['start_time']:.1f}s: {pattern}")
                    break

        return segments

    def _detect_false_starts(self, segments: List[Dict]) -> List[Dict]:
        """Find false starts (incomplete sentences followed by restarts)"""
        for segment in segments:
            text_lower = segment['text'].lower()

            # Check for false start patterns
            for pattern in self.false_start_patterns:
                if re.search(pattern, text_lower):
                    segment['has_false_start'] = True
                    logger.debug(f"False start found in segment at {segment['start_time']:.1f}s")
                    break

            # Also check for very short segments (<3 seconds) with incomplete sentences
            if segment['duration'] < 3.0 and not segment['text'].strip().endswith(('.', '!', '?')):
                segment['has_false_start'] = True

        return segments

    def _score_segment_quality(self, segments: List[Dict]) -> List[Dict]:
        """Score segment quality based on filler word density"""
        for segment in segments:
            text_lower = segment['text'].lower()
            words = text_lower.split()

            if len(words) == 0:
                segment['filler_density'] = 0.0
                continue

            # Count filler words
            filler_count = 0
            for filler in self.filler_words:
                if ' ' in filler:
                    # Multi-word fillers (e.g., "you know")
                    filler_count += text_lower.count(filler)
                else:
                    # Single-word fillers
                    filler_count += sum(1 for word in words if word == filler)

            segment['filler_density'] = filler_count / len(words)
            segment['filler_count'] = filler_count

        return segments

    def _make_decisions(self, segments: List[Dict]) -> List[Dict]:
        """
        Make keep/remove decisions based on detected patterns

        Removal rules:
        1. Segments with repetition markers → remove
        2. Segments with false starts → remove
        3. Very short segments (<3s) with high filler density (>20%) → remove
        4. After removal marker, next segment is typically the "good take" → keep
        """
        for i, segment in enumerate(segments):
            # Rule 1: Repetition markers
            if segment.get('has_repetition_marker'):
                segment['action'] = 'remove'
                segment['reason'] = 'Repetition marker detected'
                segment['confidence'] = 0.9

                # Mark next segment as "best take" (if it exists)
                if i + 1 < len(segments):
                    segments[i + 1]['reason'] = 'Best take (after retake)'
                    segments[i + 1]['confidence'] = 0.8

            # Rule 2: False starts
            elif segment.get('has_false_start'):
                segment['action'] = 'remove'
                segment['reason'] = 'False start detected'
                segment['confidence'] = 0.85

            # Rule 3: Filler-heavy short segments
            elif segment['duration'] < Config.MIN_SEGMENT_DURATION_SECONDS and segment.get('filler_density', 0) > 0.2:
                segment['action'] = 'remove'
                segment['reason'] = 'Too many fillers in short segment'
                segment['confidence'] = 0.7

            # Rule 4: Keep everything else
            else:
                if not segment.get('reason'):
                    segment['reason'] = 'Normal content'
                    segment['confidence'] = 0.6

        return segments

    def _calculate_stats(self, segments: List[Dict], video_info: Dict) -> Dict[str, Any]:
        """Calculate statistics about the detection results"""
        total_segments = len(segments)
        segments_to_keep = sum(1 for s in segments if s['action'] == 'keep')
        segments_to_remove = sum(1 for s in segments if s['action'] == 'remove')

        # Calculate durations
        original_duration = sum(s['duration'] for s in segments)
        edited_duration = sum(s['duration'] for s in segments if s['action'] == 'keep')

        # Compression ratio
        compression_ratio = edited_duration / original_duration if original_duration > 0 else 1.0

        return {
            'total_segments': total_segments,
            'segments_to_keep': segments_to_keep,
            'segments_to_remove': segments_to_remove,
            'original_duration': round(original_duration, 2),
            'edited_duration': round(edited_duration, 2),
            'time_saved': round(original_duration - edited_duration, 2),
            'compression_ratio': round(compression_ratio, 2)
        }
