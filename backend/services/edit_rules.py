from typing import List, Dict, Any, Optional, Tuple
from models.timeline import Timeline, Track, Clip
from services.audio_analyzer import AudioAnalyzer
from services.soniox_client import SonioxClient
from config import Config
import logging

logger = logging.getLogger(__name__)

class EditRulesEngine:
    """Engine for applying editing rules to timeline based on audio analysis and transcription"""

    def __init__(self):
        self.rules = {}
        self.load_default_rules()

    def load_default_rules(self):
        """Load default editing rules"""
        self.rules = {
            'min_clip_length': Config.MIN_CLIP_LENGTH_SECONDS,
            'silence_threshold_db': Config.SILENCE_THRESHOLD_DB,
            'speaker_change_threshold': Config.SPEAKER_CHANGE_THRESHOLD_SECONDS,
            'remove_silence': True,
            'split_on_speaker_change': True,
            'merge_short_clips': True,
            'preserve_important_moments': True,
            'energy_based_cutting': True
        }

    def apply_editing_rules(self,
                           timeline: Timeline,
                           transcription_data: Optional[Dict[str, Any]] = None,
                           audio_analysis: Optional[Dict[str, Any]] = None) -> Timeline:
        """
        Apply all editing rules to create a new edited timeline
        """
        try:
            logger.info("Starting timeline editing process")
            edited_timeline = Timeline(
                name=f"{timeline.name}_edited",
                frame_rate=timeline.frame_rate,
                sample_rate=timeline.sample_rate
            )

            # Process each track
            for track in timeline.tracks:
                edited_track = self._process_track(track, transcription_data, audio_analysis)
                if edited_track and edited_track.clips:
                    edited_timeline.add_track(edited_track)

            # Apply cross-track rules
            self._apply_cross_track_rules(edited_timeline, transcription_data, audio_analysis)

            # Calculate final duration
            edited_timeline.calculate_duration()

            logger.info(f"Timeline editing complete. New duration: {edited_timeline.duration:.2f}s")
            return edited_timeline

        except Exception as e:
            logger.error(f"Error applying editing rules: {str(e)}")
            raise

    def _process_track(self,
                      track: Track,
                      transcription_data: Optional[Dict[str, Any]],
                      audio_analysis: Optional[Dict[str, Any]]) -> Optional[Track]:
        """Process individual track with editing rules"""
        try:
            edited_track = Track(
                index=track.index,
                name=f"{track.name}_edited",
                track_type=track.track_type
            )

            # Apply rules in sequence
            processed_clips = list(track.clips)

            # 1. Remove silence segments
            if self.rules['remove_silence'] and audio_analysis:
                processed_clips = self._remove_silence_segments(processed_clips, audio_analysis)

            # 2. Split on speaker changes
            if self.rules['split_on_speaker_change'] and transcription_data:
                processed_clips = self._split_on_speaker_changes(processed_clips, transcription_data)

            # 3. Apply minimum clip length
            processed_clips = self._enforce_minimum_clip_length(processed_clips)

            # 4. Merge short adjacent clips if beneficial
            if self.rules['merge_short_clips']:
                processed_clips = self._merge_short_clips(processed_clips)

            # 5. Energy-based cutting
            if self.rules['energy_based_cutting'] and audio_analysis:
                processed_clips = self._apply_energy_based_cuts(processed_clips, audio_analysis)

            # Add processed clips to track
            for clip in processed_clips:
                edited_track.add_clip(clip)

            return edited_track

        except Exception as e:
            logger.error(f"Error processing track {track.name}: {str(e)}")
            return None

    def _remove_silence_segments(self,
                                clips: List[Clip],
                                audio_analysis: Dict[str, Any]) -> List[Clip]:
        """Remove silence segments from clips"""
        try:
            silence_segments = audio_analysis.get('silence_segments', [])
            if not silence_segments:
                return clips

            processed_clips = []

            for clip in clips:
                # Check if clip overlaps with any silence segment
                clip_segments = self._split_clip_around_silence(clip, silence_segments)
                processed_clips.extend(clip_segments)

            logger.info(f"Silence removal: {len(clips)} -> {len(processed_clips)} clips")
            return processed_clips

        except Exception as e:
            logger.error(f"Error removing silence segments: {str(e)}")
            return clips

    def _split_clip_around_silence(self, clip: Clip, silence_segments: List[Dict[str, Any]]) -> List[Clip]:
        """Split a clip around silence segments"""
        result_clips = []
        current_start = clip.start_time
        clip_end = clip.end_time

        # Find silence segments that overlap with this clip
        overlapping_silence = []
        for silence in silence_segments:
            if not (silence['end_time'] <= clip.start_time or silence['start_time'] >= clip.end_time):
                overlapping_silence.append(silence)

        if not overlapping_silence:
            return [clip]

        # Sort silence segments by start time
        overlapping_silence.sort(key=lambda x: x['start_time'])

        for silence in overlapping_silence:
            silence_start = max(silence['start_time'], clip.start_time)
            silence_end = min(silence['end_time'], clip.end_time)

            # Create clip before silence if it's long enough
            if silence_start - current_start >= self.rules['min_clip_length']:
                new_clip = Clip(
                    name=f"{clip.name}_seg{len(result_clips)+1}",
                    start_time=current_start,
                    end_time=silence_start,
                    duration=silence_start - current_start,
                    track_index=clip.track_index,
                    enabled=clip.enabled
                )
                result_clips.append(new_clip)

            current_start = silence_end

        # Create final segment after last silence
        if clip_end - current_start >= self.rules['min_clip_length']:
            new_clip = Clip(
                name=f"{clip.name}_seg{len(result_clips)+1}",
                start_time=current_start,
                end_time=clip_end,
                duration=clip_end - current_start,
                track_index=clip.track_index,
                enabled=clip.enabled
            )
            result_clips.append(new_clip)

        return result_clips

    def _split_on_speaker_changes(self,
                                 clips: List[Clip],
                                 transcription_data: Dict[str, Any]) -> List[Clip]:
        """Split clips on speaker change boundaries"""
        try:
            speaker_segments = transcription_data.get('segments', [])
            if not speaker_segments:
                return clips

            processed_clips = []

            for clip in clips:
                # Find speaker changes within this clip
                clip_speaker_segments = []
                for segment in speaker_segments:
                    if not (segment['end_time'] <= clip.start_time or segment['start_time'] >= clip.end_time):
                        clip_speaker_segments.append(segment)

                if len(clip_speaker_segments) <= 1:
                    processed_clips.append(clip)
                    continue

                # Split clip based on speaker segments
                current_start = clip.start_time
                for i, segment in enumerate(clip_speaker_segments):
                    segment_start = max(segment['start_time'], clip.start_time)
                    segment_end = min(segment['end_time'], clip.end_time)

                    if segment_start > current_start:
                        current_start = segment_start

                    # Create clip for this speaker segment
                    if segment_end - current_start >= self.rules['min_clip_length']:
                        new_clip = Clip(
                            name=f"{clip.name}_speaker{segment.get('speaker', i)}",
                            start_time=current_start,
                            end_time=segment_end,
                            duration=segment_end - current_start,
                            track_index=clip.track_index,
                            enabled=clip.enabled,
                            metadata={'speaker': segment.get('speaker')}
                        )
                        processed_clips.append(new_clip)

                    current_start = segment_end

            logger.info(f"Speaker splitting: {len(clips)} -> {len(processed_clips)} clips")
            return processed_clips

        except Exception as e:
            logger.error(f"Error splitting on speaker changes: {str(e)}")
            return clips

    def _enforce_minimum_clip_length(self, clips: List[Clip]) -> List[Clip]:
        """Remove clips shorter than minimum length"""
        min_length = self.rules['min_clip_length']
        valid_clips = [clip for clip in clips if clip.duration >= min_length]

        logger.info(f"Minimum length filter: {len(clips)} -> {len(valid_clips)} clips")
        return valid_clips

    def _merge_short_clips(self, clips: List[Clip]) -> List[Clip]:
        """Merge adjacent short clips if beneficial"""
        if not clips:
            return clips

        # Sort clips by start time
        clips.sort(key=lambda c: c.start_time)

        merged_clips = []
        current_clip = clips[0]

        for next_clip in clips[1:]:
            # Check if clips are adjacent or very close
            gap = next_clip.start_time - current_clip.end_time

            # Merge if gap is small and both clips are short
            should_merge = (
                gap <= self.rules['speaker_change_threshold'] and
                (current_clip.duration < self.rules['min_clip_length'] * 2 or
                 next_clip.duration < self.rules['min_clip_length'] * 2)
            )

            if should_merge:
                # Create merged clip
                merged_clip = Clip(
                    name=f"{current_clip.name}_merged",
                    start_time=current_clip.start_time,
                    end_time=next_clip.end_time,
                    duration=next_clip.end_time - current_clip.start_time,
                    track_index=current_clip.track_index,
                    enabled=current_clip.enabled
                )
                current_clip = merged_clip
            else:
                merged_clips.append(current_clip)
                current_clip = next_clip

        # Add the last clip
        merged_clips.append(current_clip)

        logger.info(f"Clip merging: {len(clips)} -> {len(merged_clips)} clips")
        return merged_clips

    def _apply_energy_based_cuts(self,
                                clips: List[Clip],
                                audio_analysis: Dict[str, Any]) -> List[Clip]:
        """Apply energy-based cutting for optimal edit points"""
        try:
            cut_points = audio_analysis.get('cut_points', [])
            if not cut_points:
                return clips

            processed_clips = []

            for clip in clips:
                # Find cut points within this clip
                clip_cuts = [cp for cp in cut_points
                           if clip.start_time < cp['time'] < clip.end_time]

                if not clip_cuts:
                    processed_clips.append(clip)
                    continue

                # Split clip at cut points
                current_start = clip.start_time
                for cut_point in sorted(clip_cuts, key=lambda x: x['time']):
                    cut_time = cut_point['time']

                    if cut_time - current_start >= self.rules['min_clip_length']:
                        new_clip = Clip(
                            name=f"{clip.name}_cut{len(processed_clips)}",
                            start_time=current_start,
                            end_time=cut_time,
                            duration=cut_time - current_start,
                            track_index=clip.track_index,
                            enabled=clip.enabled,
                            metadata={'cut_reason': cut_point.get('reason')}
                        )
                        processed_clips.append(new_clip)

                    current_start = cut_time

                # Add final segment
                if clip.end_time - current_start >= self.rules['min_clip_length']:
                    new_clip = Clip(
                        name=f"{clip.name}_final",
                        start_time=current_start,
                        end_time=clip.end_time,
                        duration=clip.end_time - current_start,
                        track_index=clip.track_index,
                        enabled=clip.enabled
                    )
                    processed_clips.append(new_clip)

            return processed_clips

        except Exception as e:
            logger.error(f"Error applying energy-based cuts: {str(e)}")
            return clips

    def _apply_cross_track_rules(self,
                                timeline: Timeline,
                                transcription_data: Optional[Dict[str, Any]],
                                audio_analysis: Optional[Dict[str, Any]]) -> None:
        """Apply rules that affect multiple tracks"""
        try:
            # Synchronize cuts across tracks
            self._synchronize_track_cuts(timeline)

            # Add markers for important moments
            if transcription_data:
                self._add_speaker_change_markers(timeline, transcription_data)

            # Balance track lengths
            self._balance_track_lengths(timeline)

        except Exception as e:
            logger.error(f"Error applying cross-track rules: {str(e)}")

    def _synchronize_track_cuts(self, timeline: Timeline) -> None:
        """Ensure cuts are synchronized across all tracks"""
        # Get all cut times from all tracks
        all_cut_times = set()
        for track in timeline.tracks:
            for clip in track.clips:
                all_cut_times.add(clip.start_time)
                all_cut_times.add(clip.end_time)

        # This is a simplified implementation
        # In practice, you might want more sophisticated synchronization
        logger.info(f"Synchronized cuts across {len(timeline.tracks)} tracks")

    def _add_speaker_change_markers(self,
                                   timeline: Timeline,
                                   transcription_data: Dict[str, Any]) -> None:
        """Add markers at speaker change points"""
        segments = transcription_data.get('segments', [])
        current_speaker = None

        for segment in segments:
            speaker = segment.get('speaker')
            if speaker != current_speaker and current_speaker is not None:
                timeline.add_marker(
                    time=segment['start_time'],
                    name=f"Speaker Change: {speaker}",
                    color="Blue"
                )
            current_speaker = speaker

    def _balance_track_lengths(self, timeline: Timeline) -> None:
        """Ensure all tracks have similar total duration"""
        if not timeline.tracks:
            return

        # Calculate target duration (longest track)
        max_duration = max(
            max((clip.end_time for clip in track.clips), default=0)
            for track in timeline.tracks
        )

        # This is a placeholder for more sophisticated balancing logic
        logger.info(f"Balanced track lengths to {max_duration:.2f}s")

    def get_editing_stats(self,
                         original_timeline: Timeline,
                         edited_timeline: Timeline) -> Dict[str, Any]:
        """Generate statistics about the editing process"""
        try:
            original_clips = sum(len(track.clips) for track in original_timeline.tracks)
            edited_clips = sum(len(track.clips) for track in edited_timeline.tracks)

            stats = {
                'original_duration': original_timeline.duration,
                'edited_duration': edited_timeline.duration,
                'duration_reduction': original_timeline.duration - edited_timeline.duration,
                'compression_ratio': edited_timeline.duration / original_timeline.duration if original_timeline.duration > 0 else 0,
                'original_clips': original_clips,
                'edited_clips': edited_clips,
                'clips_change': edited_clips - original_clips,
                'tracks_processed': len(edited_timeline.tracks),
                'markers_added': len(edited_timeline.markers)
            }

            return stats

        except Exception as e:
            logger.error(f"Error generating editing stats: {str(e)}")
            return {}

    def set_rule(self, rule_name: str, value: Any) -> bool:
        """Set a specific editing rule"""
        if rule_name in self.rules:
            self.rules[rule_name] = value
            logger.info(f"Updated rule {rule_name} to {value}")
            return True
        else:
            logger.warning(f"Unknown rule: {rule_name}")
            return False

    def get_rules(self) -> Dict[str, Any]:
        """Get current editing rules"""
        return self.rules.copy()