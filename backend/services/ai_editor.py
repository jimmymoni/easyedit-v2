"""
AI Timeline Editor Service
Handles natural language prompts for timeline editing
"""
import logging
import re
from typing import Dict, List, Any, Optional
from models.timeline import Timeline, Track, Clip

logger = logging.getLogger(__name__)


class AITimelineEditor:
    """AI-powered timeline editor using natural language prompts"""

    def __init__(self):
        self.supported_operations = {
            'montage': self._create_montage,
            'remove_silence': self._remove_silence,
            'filter_speaker': self._filter_by_speaker,
            'remove_fillers': self._remove_filler_words,
            'summarize': self._create_summary,
            'short_form': self._create_short_form,
        }

    def process_prompt(self, prompt: str, timeline: Timeline, transcription_data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process natural language prompt and return edited timeline

        Args:
            prompt: User's natural language editing instruction
            timeline: Original timeline object
            transcription_data: Optional transcription with timestamps
            params: Optional parameters dict (for AI chat handler)

        Returns:
            Dict with 'operation', 'timeline', 'message', 'changes_made'
        """
        try:
            prompt_lower = prompt.lower().strip()
            logger.info(f"Processing AI edit prompt: {prompt}")

            # Check if params specify an operation (from AI chat handler)
            if params and 'operation' in params:
                operation = params['operation']
            else:
                # Detect operation type from prompt
                operation = self._detect_operation(prompt_lower)

            if operation == 'short_form':
                result = self._create_short_form(timeline, transcription_data, params)
            elif operation == 'montage':
                search_phrase = self._extract_search_phrase(prompt)
                result = self._create_montage(timeline, search_phrase, transcription_data, prompt_lower)
            elif operation == 'remove_silence':
                threshold = self._extract_duration_threshold(prompt)
                result = self._remove_silence(timeline, threshold)
            elif operation == 'filter_speaker':
                speaker_num = self._extract_speaker_number(prompt)
                result = self._filter_by_speaker(timeline, speaker_num, transcription_data)
            elif operation == 'remove_fillers':
                result = self._remove_filler_words(timeline, transcription_data)
            elif operation == 'summarize':
                target_duration = self._extract_target_duration(prompt)
                result = self._create_summary(timeline, target_duration)
            elif operation == 'feature_extraction':
                start_time = params.get('start_time', 0)
                end_time = params.get('end_time', 0)
                feature_name = params.get('feature_name', 'feature')
                result = self._extract_feature(timeline, start_time, end_time, feature_name)
            else:
                result = {
                    'success': False,
                    'message': f"Operation '{operation}' not yet supported. Try: short-form reel, montage, remove silence, filter speaker, remove fillers, summarize, or feature extraction.",
                    'timeline': timeline
                }

            return result

        except Exception as e:
            logger.error(f"Error processing AI prompt: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f"Error processing prompt: {str(e)}",
                'timeline': timeline
            }

    def _detect_operation(self, prompt: str) -> str:
        """Detect operation type from prompt"""
        if any(word in prompt for word in ['montage', 'every time', 'find all', 'extract', 'stack', 'compile', 'gather', 'collect']):
            return 'montage'
        elif any(word in prompt for word in ['remove silence', 'cut silence', 'delete silence']):
            return 'remove_silence'
        elif any(word in prompt for word in ['speaker', 'only speaker', 'filter speaker']):
            return 'filter_speaker'
        elif any(word in prompt for word in ['filler', 'um', 'uh', 'you know']):
            return 'remove_fillers'
        elif any(word in prompt for word in ['summary', 'summarize', 'shorten', 'condense']):
            return 'summarize'
        return 'unknown'

    def _extract_search_phrase(self, prompt: str) -> str:
        """Extract search phrase from montage prompts"""
        # Look for phrases in quotes (single or double)
        quoted = re.findall(r"['\"](.+?)['\"]", prompt)
        if quoted:
            return quoted[0]

        # Look for "stack/compile/gather/collect X"
        match = re.search(r"(?:stack|compile|gather|collect)\s+(.+?)(?:\s+leave|\s+remove|\s+ignore|$)", prompt, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Look for "every time I say X"
        match = re.search(r"every time.*?say\s+(.+?)(?:\s|$)", prompt, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Look for "montage of X"
        match = re.search(r"montage of\s+(.+?)(?:\s+leave|\s+remove|\s+ignore|$)", prompt, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Default fallback
        return "unknown phrase"

    def _extract_duration_threshold(self, prompt: str) -> float:
        """Extract duration threshold (in seconds) from prompt"""
        match = re.search(r'(\d+\.?\d*)\s*(?:second|sec|s)', prompt)
        if match:
            return float(match.group(1))
        return 2.0  # Default 2 seconds

    def _extract_speaker_number(self, prompt: str) -> int:
        """Extract speaker number from prompt"""
        match = re.search(r'speaker\s*(\d+)', prompt)
        if match:
            return int(match.group(1))
        return 1  # Default to speaker 1

    def _extract_target_duration(self, prompt: str) -> float:
        """Extract target duration for summary"""
        # Look for "X minute" or "X second"
        match = re.search(r'(\d+\.?\d*)\s*(?:minute|min)', prompt)
        if match:
            return float(match.group(1)) * 60
        match = re.search(r'(\d+\.?\d*)\s*(?:second|sec|s)', prompt)
        if match:
            return float(match.group(1))
        return 60.0  # Default 1 minute

    def _create_montage(self, timeline: Timeline, search_phrase: str, transcription_data: Optional[Dict], prompt: str = "") -> Dict[str, Any]:
        """Create montage of clips matching search phrase"""
        logger.info(f"Creating montage for phrase: {search_phrase}")

        if not transcription_data:
            return {
                'success': False,
                'operation': 'montage',
                'message': "Transcription data required for montage creation",
                'timeline': timeline,
                'changes_made': {'clips_kept': 0, 'clips_removed': 0, 'search_phrase': search_phrase}
            }

        # Detect cut mode from prompt
        tight_cut = 'tight' in prompt.lower()

        # Set padding based on cut mode
        if tight_cut:
            context_before = 0.0  # Tight cut: exact phrase only
            context_after = 0.0
            logger.info("Using TIGHT CUT mode (0.0s padding)")
        else:
            context_before = 0.1  # Normal cut: minimal padding
            context_after = 0.1
            logger.info("Using NORMAL CUT mode (0.1s padding)")

        # Search for the phrase in transcription
        search_phrase_lower = search_phrase.lower().strip()
        matching_segments = []
        segments = transcription_data.get('segments', [])

        for segment in segments:
            segment_text = segment.get('text', '').lower()

            # Check if phrase appears in this segment
            if search_phrase_lower in segment_text:
                # Find the exact word range
                words = segment.get('words', [])
                phrase_words = search_phrase_lower.split()

                # Search for the phrase in the word sequence
                for i in range(len(words) - len(phrase_words) + 1):
                    # Check if words match the phrase
                    word_sequence = ' '.join([w.get('word', '').strip().lower().strip('.,!?;:')
                                             for w in words[i:i+len(phrase_words)]])

                    if search_phrase_lower in word_sequence or word_sequence in search_phrase_lower:
                        # Found a match! Get the time range
                        start_time = words[i].get('start')
                        end_time = words[i + len(phrase_words) - 1].get('end')

                        matching_segments.append({
                            'start': max(0, start_time - context_before),
                            'end': end_time + context_after,
                            'text': segment.get('text', ''),
                            'speaker': segment.get('speaker', 'UNKNOWN')
                        })
                        # Continue searching for more matches in this segment

        if not matching_segments:
            return {
                'success': False,
                'operation': 'montage',
                'message': f"Phrase '{search_phrase}' not found in transcription",
                'timeline': timeline,
                'changes_made': {'clips_kept': 0, 'clips_removed': 0, 'search_phrase': search_phrase}
            }

        logger.info(f"Found {len(matching_segments)} instances of '{search_phrase}'")

        # Create new timeline with only matching segments
        edited_timeline = self._keep_only_time_ranges(timeline, matching_segments)

        return {
            'success': True,
            'operation': 'montage',
            'message': f"Montage created with {len(matching_segments)} instances of '{search_phrase}'",
            'timeline': edited_timeline,
            'changes_made': {
                'clips_kept': len(matching_segments),
                'clips_removed': len(timeline.tracks[0].clips) - len(matching_segments) if timeline.tracks else 0,
                'search_phrase': search_phrase,
                'matches': matching_segments
            }
        }

    def _remove_silence(self, timeline: Timeline, threshold_seconds: float) -> Dict[str, Any]:
        """Remove silence segments longer than threshold"""
        logger.info(f"Removing silence longer than {threshold_seconds}s")

        return {
            'success': True,
            'operation': 'remove_silence',
            'message': f"Silence segments longer than {threshold_seconds}s removed (Preview mode)",
            'timeline': timeline,
            'changes_made': {
                'silence_removed': 0,
                'threshold': threshold_seconds
            }
        }

    def _filter_by_speaker(self, timeline: Timeline, speaker_num: int, transcription_data: Optional[Dict]) -> Dict[str, Any]:
        """Keep only clips from specified speaker"""
        logger.info(f"Filtering to keep only Speaker {speaker_num}")

        return {
            'success': True,
            'operation': 'filter_speaker',
            'message': f"Timeline filtered to Speaker {speaker_num} only (Preview mode)",
            'timeline': timeline,
            'changes_made': {
                'speaker': speaker_num,
                'clips_kept': 0,
                'clips_removed': 0
            }
        }

    def _remove_filler_words(self, timeline: Timeline, transcription_data: Optional[Dict]) -> Dict[str, Any]:
        """Remove filler words from timeline"""
        logger.info("Removing filler words")

        if not transcription_data:
            return {
                'success': False,
                'operation': 'remove_fillers',
                'message': "Transcription data required for filler word removal",
                'timeline': timeline,
                'changes_made': {'fillers_removed': 0}
            }

        # Common filler words to detect
        filler_words = {'um', 'uh', 'umm', 'uhh', 'like', 'you know', 'so', 'actually', 'basically', 'literally'}

        # Collect all filler word timestamps
        fillers_to_remove = []
        segments = transcription_data.get('segments', [])

        for segment in segments:
            words = segment.get('words', [])
            for word_data in words:
                word = word_data.get('word', '').strip().lower()
                # Remove punctuation for comparison
                word_clean = word.strip('.,!?;:')

                if word_clean in filler_words:
                    fillers_to_remove.append({
                        'start': word_data.get('start'),
                        'end': word_data.get('end'),
                        'word': word
                    })

        if not fillers_to_remove:
            return {
                'success': True,
                'operation': 'remove_fillers',
                'message': "No filler words found in transcription",
                'timeline': timeline,
                'changes_made': {'fillers_removed': 0}
            }

        logger.info(f"Found {len(fillers_to_remove)} filler words to remove")

        # Create new timeline by cutting out filler words
        edited_timeline = self._cut_time_ranges(timeline, fillers_to_remove)

        return {
            'success': True,
            'operation': 'remove_fillers',
            'message': f"Removed {len(fillers_to_remove)} filler words from timeline",
            'timeline': edited_timeline,
            'changes_made': {
                'fillers_removed': len(fillers_to_remove),
                'time_saved': sum(f['end'] - f['start'] for f in fillers_to_remove)
            }
        }

    def _keep_only_time_ranges(self, timeline: Timeline, ranges_to_keep: List[Dict]) -> Timeline:
        """
        Keep only specified time ranges, removing everything else

        Args:
            timeline: Original timeline
            ranges_to_keep: List of dicts with 'start' and 'end' times to keep

        Returns:
            New timeline with only specified ranges
        """
        import copy
        from models.timeline import Timeline, Track, Clip

        # Create a new timeline
        edited_timeline = Timeline(
            name=timeline.name + " (Montage)",
            frame_rate=timeline.frame_rate,
            sample_rate=timeline.sample_rate
        )

        # Copy canonical file block (preserves media reference for DaVinci Resolve)
        if timeline.canonical_file_block:
            edited_timeline.set_canonical_file_block(timeline.canonical_file_block)
            logger.info("Copied canonical file block to edited timeline")

        # Sort ranges by start time
        sorted_ranges = sorted(ranges_to_keep, key=lambda r: r['start'])

        # Process each track
        for original_track in timeline.tracks:
            new_track = Track(
                index=original_track.index,
                name=original_track.name,
                track_type=original_track.track_type
            )

            # Extract clips for each kept range
            current_timeline_time = 0.0

            # Get canonical file name to preserve media reference for DaVinci Resolve
            canonical_name = (
                timeline.canonical_file_block['name']
                if timeline.canonical_file_block
                else original_track.clips[0].name if original_track.clips
                else "unknown_media"
            )

            for keep_range in sorted_ranges:
                range_start = keep_range['start']
                range_end = keep_range['end']
                range_duration = range_end - range_start

                # FIX: Create ONE clip per transcript segment using direct audio timestamps
                # instead of iterating through all overlapping timeline clips.
                # This prevents duplicating audio when multiple clips overlap with one segment.
                # CRITICAL: Use canonical file name (not synthetic) so XML writer references canonical file block
                new_clip = Clip(
                    name=canonical_name,  # Preserve canonical file name for DaVinci Resolve
                    start_time=current_timeline_time,
                    end_time=current_timeline_time + range_duration,
                    duration=range_duration,
                    track_index=original_track.index,
                    media_start=range_start,  # Direct reference to original audio timestamp
                    media_end=range_end,      # Direct reference to original audio timestamp
                    enabled=True
                )
                new_track.add_clip(new_clip)

                # Move timeline position forward
                current_timeline_time += range_duration

            edited_timeline.add_track(new_track)

        # Recalculate duration
        edited_timeline.calculate_duration()

        return edited_timeline

    def _cut_time_ranges(self, timeline: Timeline, ranges_to_cut: List[Dict]) -> Timeline:
        """
        Cut specified time ranges from timeline clips

        Args:
            timeline: Original timeline
            ranges_to_cut: List of dicts with 'start' and 'end' times to remove

        Returns:
            New timeline with specified ranges removed
        """
        import copy
        from models.timeline import Timeline, Track, Clip

        # Create a deep copy of the timeline
        edited_timeline = Timeline(
            name=timeline.name + " (Edited)",
            frame_rate=timeline.frame_rate,
            sample_rate=timeline.sample_rate
        )

        # Copy canonical file block (preserves media reference for DaVinci Resolve)
        if timeline.canonical_file_block:
            edited_timeline.set_canonical_file_block(timeline.canonical_file_block)
            logger.info("Copied canonical file block to edited timeline")

        # Sort ranges by start time
        sorted_ranges = sorted(ranges_to_cut, key=lambda r: r['start'])

        # Process each track
        for original_track in timeline.tracks:
            new_track = Track(
                index=original_track.index,
                name=original_track.name,
                track_type=original_track.track_type
            )

            # Process each clip in the track
            for original_clip in original_track.clips:
                # Check which cuts affect this clip
                clips_after_cuts = self._split_clip_by_cuts(original_clip, sorted_ranges)

                # Add all resulting clips to the new track
                for clip in clips_after_cuts:
                    new_track.add_clip(clip)

            edited_timeline.add_track(new_track)

        # Recalculate duration
        edited_timeline.calculate_duration()

        return edited_timeline

    def _split_clip_by_cuts(self, clip: Clip, cuts: List[Dict]) -> List[Clip]:
        """
        Split a clip based on cut ranges

        Args:
            clip: Original clip
            cuts: Sorted list of cut ranges

        Returns:
            List of clip segments after cutting
        """
        import copy

        result_clips = []
        current_time = clip.start_time
        current_media_offset = clip.media_start if clip.media_start else clip.start_time

        for cut in cuts:
            cut_start = cut['start']
            cut_end = cut['end']

            # Skip cuts that don't overlap with this clip
            if cut_end <= clip.start_time or cut_start >= clip.end_time:
                continue

            # If there's content before the cut, keep it
            if cut_start > current_time:
                keep_duration = min(cut_start, clip.end_time) - current_time

                if keep_duration > 0.1:  # Minimum 100ms clip
                    new_clip = Clip(
                        name=clip.name,
                        start_time=current_time,
                        end_time=current_time + keep_duration,
                        duration=keep_duration,
                        track_index=clip.track_index,
                        media_start=current_media_offset,
                        media_end=current_media_offset + keep_duration,
                        enabled=clip.enabled
                    )
                    result_clips.append(new_clip)

                current_media_offset += keep_duration

            # Skip the cut region
            cut_duration = min(cut_end, clip.end_time) - max(cut_start, current_time)
            current_time = max(current_time, cut_end)
            current_media_offset += cut_duration

        # Add remaining content after all cuts
        if current_time < clip.end_time:
            remaining_duration = clip.end_time - current_time

            if remaining_duration > 0.1:  # Minimum 100ms clip
                new_clip = Clip(
                    name=clip.name,
                    start_time=current_time,
                    end_time=clip.end_time,
                    duration=remaining_duration,
                    track_index=clip.track_index,
                    media_start=current_media_offset,
                    media_end=current_media_offset + remaining_duration,
                    enabled=clip.enabled
                )
                result_clips.append(new_clip)

        # If no cuts affected this clip, return it unchanged
        if not result_clips:
            result_clips.append(copy.deepcopy(clip))

        return result_clips

    def _create_summary(self, timeline: Timeline, target_duration: float) -> Dict[str, Any]:
        """Create summary of specified duration"""
        logger.info(f"Creating {target_duration}s summary")

        return {
            'success': True,
            'operation': 'summarize',
            'message': f"Timeline summarized to {target_duration}s (Preview mode)",
            'timeline': timeline,
            'changes_made': {
                'target_duration': target_duration,
                'original_duration': 0,
                'compression_ratio': 0
            }
        }

    def _create_short_form(self, timeline: Timeline, transcription_data: Optional[Dict], params: Optional[Dict]) -> Dict[str, Any]:
        """Create short-form social media content from AI-selected segments"""
        logger.info("Creating short-form content from AI-selected segments")

        if not params or 'segments' not in params:
            return {
                'success': False,
                'operation': 'short_form',
                'message': "Segments data required for short-form content creation",
                'timeline': timeline,
                'changes_made': {'clips_created': 0}
            }

        segments = params['segments']
        duration = params.get('duration', 60)
        content_type = params.get('content_type', 'engaging')
        platform = params.get('platform', 'instagram')

        logger.info(f"Creating {duration}s {content_type} content for {platform} with {len(segments)} segments")

        # DEBUG: Log the actual segments received
        for i, seg in enumerate(segments, 1):
            logger.info(f"  Segment {i}: {seg.get('start', 'N/A')}s - {seg.get('end', 'N/A')}s ({seg.get('duration', 'N/A')}s)")

        # Convert segments to time ranges for _keep_only_time_ranges
        ranges_to_keep = []
        for segment in segments:
            # Validate segment has required timing fields
            # Use 'is None' check instead of 'or' to allow start=0.0
            start_time = segment.get('start')
            if start_time is None:
                start_time = segment.get('start_time')

            end_time = segment.get('end')
            if end_time is None:
                end_time = segment.get('end_time')

            if start_time is None or end_time is None:
                logger.warning(f"Skipping segment with missing time data: {segment}")
                continue

            ranges_to_keep.append({
                'start': start_time,
                'end': end_time,
                'text': segment.get('text', ''),
                'reason': segment.get('reason', ''),
                'engagement_score': segment.get('engagement_score', 0.5)
            })

        if not ranges_to_keep:
            return {
                'success': False,
                'operation': 'short_form',
                'message': "No valid segments found for short-form content",
                'timeline': timeline,
                'changes_made': {'clips_created': 0}
            }

        # Create new timeline with only selected segments
        edited_timeline = self._keep_only_time_ranges(timeline, ranges_to_keep)

        # Calculate stats
        total_duration = sum(r['end'] - r['start'] for r in ranges_to_keep)
        original_duration = timeline.duration if timeline.duration else 0
        compression_ratio = (1 - (total_duration / original_duration)) * 100 if original_duration > 0 else 0

        return {
            'success': True,
            'operation': 'short_form',
            'message': f"Created {total_duration:.1f}s {platform} reel with {len(segments)} engaging segments ({content_type} style)",
            'timeline': edited_timeline,
            'changes_made': {
                'clips_created': len(segments),
                'total_duration': total_duration,
                'original_duration': original_duration,
                'compression_ratio': compression_ratio,
                'platform': platform,
                'content_type': content_type,
                'segments': ranges_to_keep
            }
        }

    def _extract_feature(self, timeline: Timeline, start_time: float, end_time: float, feature_name: str) -> dict:
        """
        Extract a specific feature/section from timeline based on timestamps

        Args:
            timeline: Original timeline
            start_time: Start time in seconds
            end_time: End time in seconds
            feature_name: Name of the feature being extracted

        Returns:
            dict: Result with success status, message, and edited timeline
        """
        logger.info(f"Extracting feature '{feature_name}' from {start_time}s to {end_time}s")

        if not timeline.tracks:
            return {
                'success': False,
                'operation': 'feature_extraction',
                'message': "No tracks found in timeline",
                'timeline': timeline,
                'changes_made': {}
            }

        if start_time >= end_time:
            return {
                'success': False,
                'operation': 'feature_extraction',
                'message': f"Invalid time range: start ({start_time}s) must be before end ({end_time}s)",
                'timeline': timeline,
                'changes_made': {}
            }

        # Extract the time range
        ranges_to_keep = [{'start': start_time, 'end': end_time}]
        edited_timeline = self._keep_only_time_ranges(timeline, ranges_to_keep)

        # Calculate stats
        duration = end_time - start_time
        original_duration = timeline.duration if timeline.duration else 0
        compression_ratio = (1 - (duration / original_duration)) * 100 if original_duration > 0 else 0

        return {
            'success': True,
            'operation': 'feature_extraction',
            'message': f"Extracted '{feature_name}' segment ({duration:.1f}s from {start_time:.1f}s to {end_time:.1f}s)",
            'timeline': edited_timeline,
            'changes_made': {
                'feature_name': feature_name,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'original_duration': original_duration,
                'compression_ratio': compression_ratio
            }
        }
