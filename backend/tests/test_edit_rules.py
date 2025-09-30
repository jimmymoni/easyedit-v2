import pytest
from unittest.mock import Mock, patch
from services.edit_rules import EditRulesEngine
from models.timeline import Timeline, Track, Clip

class TestEditRulesEngine:
    """Test cases for EditRulesEngine"""

    @pytest.fixture
    def rules_engine(self):
        """Create a rules engine for testing"""
        return EditRulesEngine()

    @pytest.fixture
    def sample_audio_analysis(self):
        """Sample audio analysis data for testing"""
        return {
            'silence_segments': [
                {'start_time': 10.0, 'end_time': 12.0, 'duration': 2.0, 'type': 'silence'},
                {'start_time': 25.0, 'end_time': 28.0, 'duration': 3.0, 'type': 'silence'},
                {'start_time': 45.0, 'end_time': 46.5, 'duration': 1.5, 'type': 'silence'}
            ],
            'speech_segments': [
                {'start_time': 0.0, 'end_time': 10.0, 'duration': 10.0, 'type': 'speech'},
                {'start_time': 12.0, 'end_time': 25.0, 'duration': 13.0, 'type': 'speech'},
                {'start_time': 28.0, 'end_time': 45.0, 'duration': 17.0, 'type': 'speech'},
                {'start_time': 46.5, 'end_time': 60.0, 'duration': 13.5, 'type': 'speech'}
            ],
            'cut_points': [
                {'time': 5.0, 'type': 'energy_cut', 'confidence': 0.8, 'reason': 'Low energy point'},
                {'time': 35.0, 'type': 'energy_cut', 'confidence': 0.7, 'reason': 'Speaker change'},
            ],
            'features': {
                'dynamic_range_db': 45.0,
                'avg_db': -25.0
            }
        }

    def test_default_rules_loaded(self, rules_engine):
        """Test that default rules are loaded correctly"""
        rules = rules_engine.get_rules()

        expected_rules = [
            'min_clip_length', 'silence_threshold_db', 'speaker_change_threshold',
            'remove_silence', 'split_on_speaker_change', 'merge_short_clips',
            'preserve_important_moments', 'energy_based_cutting'
        ]

        for rule in expected_rules:
            assert rule in rules

        # Check default values
        assert rules['min_clip_length'] > 0
        assert rules['silence_threshold_db'] < 0
        assert isinstance(rules['remove_silence'], bool)

    def test_set_rule(self, rules_engine):
        """Test setting individual rules"""
        # Set existing rule
        success = rules_engine.set_rule('min_clip_length', 3.0)
        assert success == True

        rules = rules_engine.get_rules()
        assert rules['min_clip_length'] == 3.0

        # Try to set non-existent rule
        success = rules_engine.set_rule('nonexistent_rule', 123)
        assert success == False

    def test_apply_editing_rules_basic(self, rules_engine, sample_timeline, sample_audio_analysis):
        """Test basic editing rules application"""
        edited_timeline = rules_engine.apply_editing_rules(
            sample_timeline,
            None,  # No transcription
            sample_audio_analysis
        )

        assert isinstance(edited_timeline, Timeline)
        assert edited_timeline.name.endswith('_edited')
        assert len(edited_timeline.tracks) > 0

    def test_remove_silence_segments(self, rules_engine, sample_timeline, sample_audio_analysis):
        """Test silence removal functionality"""
        # Enable silence removal
        rules_engine.set_rule('remove_silence', True)

        # Create a timeline with clips that overlap silence
        timeline = Timeline("Test Timeline")
        track = Track(0, "Audio Track", "audio")

        # Add clips that span silence segments
        clip1 = Clip("Clip 1", 8.0, 15.0, 7.0, 0)  # Overlaps first silence (10-12s)
        clip2 = Clip("Clip 2", 20.0, 30.0, 10.0, 0)  # Overlaps second silence (25-28s)

        track.add_clip(clip1)
        track.add_clip(clip2)
        timeline.add_track(track)

        edited_timeline = rules_engine.apply_editing_rules(
            timeline,
            None,
            sample_audio_analysis
        )

        # Should have more clips after splitting around silence
        edited_track = edited_timeline.get_tracks_by_type('audio')[0]
        assert len(edited_track.clips) >= len(track.clips)

    def test_split_on_speaker_changes(self, rules_engine, sample_timeline, sample_transcription_data):
        """Test splitting clips on speaker changes"""
        rules_engine.set_rule('split_on_speaker_change', True)

        # Create timeline with clips spanning speaker changes
        timeline = Timeline("Test Timeline")
        track = Track(0, "Audio Track", "audio")

        # Add clip that spans both speakers (0-15s covers both Speaker1 and Speaker2)
        clip = Clip("Long Clip", 0.0, 15.0, 15.0, 0)
        track.add_clip(clip)
        timeline.add_track(track)

        edited_timeline = rules_engine.apply_editing_rules(
            timeline,
            sample_transcription_data,
            None
        )

        # Should have split the clip based on speaker changes
        edited_track = edited_timeline.get_tracks_by_type('audio')[0]
        assert len(edited_track.clips) > 1

        # Check that clips have speaker metadata
        for clip in edited_track.clips:
            if clip.metadata:
                assert 'speaker' in clip.metadata

    def test_enforce_minimum_clip_length(self, rules_engine):
        """Test minimum clip length enforcement"""
        rules_engine.set_rule('min_clip_length', 5.0)

        # Create clips with various lengths
        clips = [
            Clip("Short Clip", 0.0, 2.0, 2.0, 0),     # Too short
            Clip("Good Clip", 5.0, 12.0, 7.0, 0),    # Good length
            Clip("Tiny Clip", 15.0, 15.5, 0.5, 0),   # Too short
            Clip("Long Clip", 20.0, 35.0, 15.0, 0)   # Good length
        ]

        filtered_clips = rules_engine._enforce_minimum_clip_length(clips)

        # Should only keep clips >= 5.0 seconds
        assert len(filtered_clips) == 2
        assert filtered_clips[0].name == "Good Clip"
        assert filtered_clips[1].name == "Long Clip"

    def test_merge_short_clips(self, rules_engine):
        """Test merging of short adjacent clips"""
        rules_engine.set_rule('merge_short_clips', True)
        rules_engine.set_rule('speaker_change_threshold', 2.0)

        # Create short adjacent clips
        clips = [
            Clip("Clip 1", 0.0, 3.0, 3.0, 0),    # Short
            Clip("Clip 2", 4.0, 6.0, 2.0, 0),    # Short, close to Clip 1
            Clip("Clip 3", 15.0, 25.0, 10.0, 0), # Good length, far from others
            Clip("Clip 4", 26.0, 28.0, 2.0, 0),  # Short, close to Clip 3
        ]

        merged_clips = rules_engine._merge_short_clips(clips)

        # Should have merged some clips
        assert len(merged_clips) <= len(clips)

        # Check that merged clips have reasonable durations
        for clip in merged_clips:
            assert clip.start_time < clip.end_time
            assert clip.duration == clip.end_time - clip.start_time

    def test_split_clip_around_silence(self, rules_engine):
        """Test splitting a single clip around silence"""
        silence_segments = [
            {'start_time': 10.0, 'end_time': 12.0, 'duration': 2.0, 'type': 'silence'},
            {'start_time': 20.0, 'end_time': 22.0, 'duration': 2.0, 'type': 'silence'}
        ]

        # Clip that spans both silence segments
        clip = Clip("Test Clip", 5.0, 25.0, 20.0, 0)

        result_clips = rules_engine._split_clip_around_silence(clip, silence_segments)

        # Should split into multiple clips around silence
        assert len(result_clips) > 1

        # All resulting clips should be long enough (>= min_clip_length)
        for result_clip in result_clips:
            assert result_clip.duration >= rules_engine.rules['min_clip_length']

        # Result clips should maintain temporal order
        for i in range(len(result_clips) - 1):
            assert result_clips[i].end_time <= result_clips[i + 1].start_time

    def test_apply_cross_track_rules(self, rules_engine, sample_transcription_data):
        """Test cross-track rules application"""
        timeline = Timeline("Test Timeline")

        # Add multiple tracks
        track1 = Track(0, "Audio 1", "audio")
        track2 = Track(1, "Audio 2", "audio")

        track1.add_clip(Clip("Clip 1A", 0.0, 10.0, 10.0, 0))
        track2.add_clip(Clip("Clip 2A", 0.0, 10.0, 10.0, 1))

        timeline.add_track(track1)
        timeline.add_track(track2)

        # Apply cross-track rules (should add markers, etc.)
        rules_engine._apply_cross_track_rules(timeline, sample_transcription_data, None)

        # Should have added some markers for speaker changes
        assert len(timeline.markers) > 0

    def test_get_editing_stats(self, rules_engine):
        """Test editing statistics generation"""
        # Create original timeline
        original = Timeline("Original", duration=60.0)
        original_track = Track(0, "Track", "audio")
        original_track.add_clip(Clip("Clip 1", 0.0, 30.0, 30.0, 0))
        original_track.add_clip(Clip("Clip 2", 30.0, 60.0, 30.0, 0))
        original.add_track(original_track)
        original.calculate_duration()

        # Create edited timeline (shorter)
        edited = Timeline("Edited", duration=40.0)
        edited_track = Track(0, "Track", "audio")
        edited_track.add_clip(Clip("Clip 1A", 0.0, 15.0, 15.0, 0))
        edited_track.add_clip(Clip("Clip 1B", 15.0, 25.0, 10.0, 0))
        edited_track.add_clip(Clip("Clip 2A", 25.0, 40.0, 15.0, 0))
        edited.add_track(edited_track)
        edited.calculate_duration()

        stats = rules_engine.get_editing_stats(original, edited)

        assert isinstance(stats, dict)
        assert stats['original_duration'] == 60.0
        assert stats['edited_duration'] == 40.0
        assert stats['duration_reduction'] == 20.0
        assert stats['compression_ratio'] == 40.0 / 60.0
        assert stats['original_clips'] == 2
        assert stats['edited_clips'] == 3
        assert stats['clips_change'] == 1

    def test_process_track_with_all_rules(self, rules_engine, sample_audio_analysis, sample_transcription_data):
        """Test processing a track with all rules enabled"""
        # Enable all rules
        rules_engine.set_rule('remove_silence', True)
        rules_engine.set_rule('split_on_speaker_change', True)
        rules_engine.set_rule('merge_short_clips', True)
        rules_engine.set_rule('energy_based_cutting', True)

        # Create test track
        track = Track(0, "Test Track", "audio")
        track.add_clip(Clip("Long Clip", 0.0, 50.0, 50.0, 0))

        processed_track = rules_engine._process_track(
            track,
            sample_transcription_data,
            sample_audio_analysis
        )

        assert processed_track is not None
        assert processed_track.name.endswith('_edited')
        assert len(processed_track.clips) > 0

    def test_editing_with_no_transcription(self, rules_engine, sample_timeline, sample_audio_analysis):
        """Test editing without transcription data"""
        edited_timeline = rules_engine.apply_editing_rules(
            sample_timeline,
            None,  # No transcription
            sample_audio_analysis
        )

        assert isinstance(edited_timeline, Timeline)
        # Should still work without transcription, just skip speaker-based rules

    def test_editing_with_no_audio_analysis(self, rules_engine, sample_timeline, sample_transcription_data):
        """Test editing without audio analysis data"""
        edited_timeline = rules_engine.apply_editing_rules(
            sample_timeline,
            sample_transcription_data,
            None  # No audio analysis
        )

        assert isinstance(edited_timeline, Timeline)
        # Should still work without audio analysis, just skip silence-based rules

    def test_empty_timeline_processing(self, rules_engine):
        """Test processing empty timeline"""
        empty_timeline = Timeline("Empty Timeline")

        edited_timeline = rules_engine.apply_editing_rules(
            empty_timeline,
            None,
            None
        )

        assert isinstance(edited_timeline, Timeline)
        assert len(edited_timeline.tracks) == 0
        assert edited_timeline.duration == 0.0

    def test_error_handling_in_processing(self, rules_engine):
        """Test error handling during processing"""
        # Create timeline with problematic data
        timeline = Timeline("Test Timeline")
        track = Track(0, "Test Track", "audio")

        # Add clip with invalid timing
        bad_clip = Clip("Bad Clip", 10.0, 5.0, -5.0, 0)  # End before start
        track.add_clip(bad_clip)
        timeline.add_track(track)

        # Should handle errors gracefully
        try:
            edited_timeline = rules_engine.apply_editing_rules(timeline, None, None)
            # If no exception, that's also acceptable
            assert isinstance(edited_timeline, Timeline)
        except Exception as e:
            # If an exception occurs, it should be a reasonable error
            assert isinstance(e, (ValueError, RuntimeError))

    def test_rules_persistence(self, rules_engine):
        """Test that rule changes persist"""
        original_value = rules_engine.get_rules()['min_clip_length']

        rules_engine.set_rule('min_clip_length', 7.0)
        assert rules_engine.get_rules()['min_clip_length'] == 7.0

        # Rules should persist through multiple operations
        rules_engine.set_rule('remove_silence', False)
        assert rules_engine.get_rules()['min_clip_length'] == 7.0
        assert rules_engine.get_rules()['remove_silence'] == False