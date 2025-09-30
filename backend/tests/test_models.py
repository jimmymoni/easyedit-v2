import pytest
from models.timeline import Timeline, Track, Clip

class TestClip:
    """Test cases for the Clip model"""

    def test_clip_creation(self):
        """Test basic clip creation"""
        clip = Clip(
            name="Test Clip",
            start_time=10.0,
            end_time=20.0,
            duration=10.0,
            track_index=0
        )

        assert clip.name == "Test Clip"
        assert clip.start_time == 10.0
        assert clip.end_time == 20.0
        assert clip.duration == 10.0
        assert clip.track_index == 0
        assert clip.enabled == True

    def test_timecode_conversion(self):
        """Test timecode conversion methods"""
        clip = Clip(
            name="Test Clip",
            start_time=65.5,  # 1 minute, 5.5 seconds
            end_time=125.25,  # 2 minutes, 5.25 seconds
            duration=59.75,
            track_index=0
        )

        # Test start timecode (65.5s = 00:01:05:12 at 25fps)
        assert clip.timecode_start == "00:01:05:12"

        # Test end timecode (125.25s = 00:02:05:06 at 25fps)
        assert clip.timecode_end == "00:02:05:06"

    def test_clip_with_metadata(self):
        """Test clip with metadata"""
        clip = Clip(
            name="Test Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            track_index=0,
            metadata={"speaker": "Speaker1", "confidence": 0.95}
        )

        assert clip.metadata["speaker"] == "Speaker1"
        assert clip.metadata["confidence"] == 0.95

class TestTrack:
    """Test cases for the Track model"""

    def test_track_creation(self):
        """Test basic track creation"""
        track = Track(
            index=0,
            name="Test Track",
            track_type="audio"
        )

        assert track.index == 0
        assert track.name == "Test Track"
        assert track.track_type == "audio"
        assert track.enabled == True
        assert track.locked == False
        assert len(track.clips) == 0

    def test_add_clip_to_track(self):
        """Test adding clips to track"""
        track = Track(index=0, name="Test Track", track_type="audio")

        clip1 = Clip("Clip 1", 0.0, 10.0, 10.0, 0)
        clip2 = Clip("Clip 2", 15.0, 25.0, 10.0, 0)

        track.add_clip(clip1)
        track.add_clip(clip2)

        assert len(track.clips) == 2
        assert track.clips[0].name == "Clip 1"
        assert track.clips[1].name == "Clip 2"

        # Test that clips are sorted by start time
        clip3 = Clip("Clip 3", 5.0, 12.0, 7.0, 0)
        track.add_clip(clip3)

        assert len(track.clips) == 3
        assert track.clips[0].name == "Clip 1"  # starts at 0.0
        assert track.clips[1].name == "Clip 3"  # starts at 5.0
        assert track.clips[2].name == "Clip 2"  # starts at 15.0

    def test_remove_clip_from_track(self):
        """Test removing clips from track"""
        track = Track(index=0, name="Test Track", track_type="audio")

        clip1 = Clip("Clip 1", 0.0, 10.0, 10.0, 0)
        clip2 = Clip("Clip 2", 15.0, 25.0, 10.0, 0)

        track.add_clip(clip1)
        track.add_clip(clip2)

        assert len(track.clips) == 2

        success = track.remove_clip(clip1)
        assert success == True
        assert len(track.clips) == 1
        assert track.clips[0].name == "Clip 2"

        # Test removing non-existent clip
        dummy_clip = Clip("Dummy", 0.0, 5.0, 5.0, 0)
        success = track.remove_clip(dummy_clip)
        assert success == False
        assert len(track.clips) == 1

    def test_get_clips_in_range(self):
        """Test getting clips in time range"""
        track = Track(index=0, name="Test Track", track_type="audio")

        clip1 = Clip("Clip 1", 0.0, 10.0, 10.0, 0)    # 0-10s
        clip2 = Clip("Clip 2", 15.0, 25.0, 10.0, 0)   # 15-25s
        clip3 = Clip("Clip 3", 30.0, 40.0, 10.0, 0)   # 30-40s

        track.add_clip(clip1)
        track.add_clip(clip2)
        track.add_clip(clip3)

        # Test range that overlaps with clip1 and clip2
        clips_in_range = track.get_clips_in_range(5.0, 20.0)
        assert len(clips_in_range) == 2
        assert clips_in_range[0].name == "Clip 1"
        assert clips_in_range[1].name == "Clip 2"

        # Test range that doesn't overlap with any clips
        clips_in_range = track.get_clips_in_range(26.0, 29.0)
        assert len(clips_in_range) == 0

        # Test range that overlaps with all clips
        clips_in_range = track.get_clips_in_range(0.0, 40.0)
        assert len(clips_in_range) == 3

class TestTimeline:
    """Test cases for the Timeline model"""

    def test_timeline_creation(self):
        """Test basic timeline creation"""
        timeline = Timeline(
            name="Test Timeline",
            frame_rate=25.0,
            sample_rate=48000
        )

        assert timeline.name == "Test Timeline"
        assert timeline.frame_rate == 25.0
        assert timeline.sample_rate == 48000
        assert timeline.duration == 0.0
        assert len(timeline.tracks) == 0
        assert len(timeline.markers) == 0

    def test_add_track_to_timeline(self):
        """Test adding tracks to timeline"""
        timeline = Timeline("Test Timeline")

        track1 = Track(0, "Audio Track", "audio")
        track2 = Track(1, "Video Track", "video")

        timeline.add_track(track1)
        timeline.add_track(track2)

        assert len(timeline.tracks) == 2
        assert timeline.tracks[0].name == "Audio Track"
        assert timeline.tracks[1].name == "Video Track"

    def test_add_duplicate_track_index(self):
        """Test adding track with duplicate index raises error"""
        timeline = Timeline("Test Timeline")

        track1 = Track(0, "Track 1", "audio")
        track2 = Track(0, "Track 2", "audio")  # Same index

        timeline.add_track(track1)

        with pytest.raises(ValueError, match="Track with index 0 already exists"):
            timeline.add_track(track2)

    def test_get_track_by_index(self):
        """Test getting track by index"""
        timeline = Timeline("Test Timeline")

        track1 = Track(0, "Audio Track", "audio")
        track2 = Track(2, "Video Track", "video")

        timeline.add_track(track1)
        timeline.add_track(track2)

        found_track = timeline.get_track_by_index(0)
        assert found_track is not None
        assert found_track.name == "Audio Track"

        found_track = timeline.get_track_by_index(2)
        assert found_track is not None
        assert found_track.name == "Video Track"

        found_track = timeline.get_track_by_index(1)
        assert found_track is None

    def test_get_tracks_by_type(self):
        """Test getting tracks by type"""
        timeline = Timeline("Test Timeline")

        audio_track1 = Track(0, "Audio 1", "audio")
        audio_track2 = Track(1, "Audio 2", "audio")
        video_track = Track(2, "Video 1", "video")

        timeline.add_track(audio_track1)
        timeline.add_track(audio_track2)
        timeline.add_track(video_track)

        audio_tracks = timeline.get_tracks_by_type("audio")
        assert len(audio_tracks) == 2

        video_tracks = timeline.get_tracks_by_type("video")
        assert len(video_tracks) == 1

        subtitle_tracks = timeline.get_tracks_by_type("subtitle")
        assert len(subtitle_tracks) == 0

    def test_add_marker(self):
        """Test adding markers to timeline"""
        timeline = Timeline("Test Timeline", frame_rate=25.0)

        timeline.add_marker(10.0, "Marker 1", "Red")
        timeline.add_marker(5.0, "Marker 2", "Blue")  # Earlier time
        timeline.add_marker(15.0, "Marker 3", "Green")

        assert len(timeline.markers) == 3

        # Markers should be sorted by time
        assert timeline.markers[0]["name"] == "Marker 2"  # 5.0s
        assert timeline.markers[1]["name"] == "Marker 1"  # 10.0s
        assert timeline.markers[2]["name"] == "Marker 3"  # 15.0s

        # Check timecode conversion
        assert timeline.markers[0]["timecode"] == "00:00:05:00"
        assert timeline.markers[1]["timecode"] == "00:00:10:00"

    def test_calculate_duration(self):
        """Test timeline duration calculation"""
        timeline = Timeline("Test Timeline")

        track = Track(0, "Test Track", "audio")
        clip1 = Clip("Clip 1", 0.0, 10.0, 10.0, 0)
        clip2 = Clip("Clip 2", 15.0, 30.0, 15.0, 0)  # Ends at 30.0

        track.add_clip(clip1)
        track.add_clip(clip2)
        timeline.add_track(track)

        duration = timeline.calculate_duration()

        assert duration == 30.0
        assert timeline.duration == 30.0

    def test_get_timeline_stats(self):
        """Test timeline statistics"""
        timeline = Timeline("Test Timeline", frame_rate=30.0, sample_rate=44100)

        # Add audio track with clips
        audio_track = Track(0, "Audio Track", "audio")
        clip1 = Clip("Clip 1", 0.0, 10.0, 10.0, 0)
        clip2 = Clip("Clip 2", 15.0, 25.0, 10.0, 0)
        audio_track.add_clip(clip1)
        audio_track.add_clip(clip2)

        # Add video track
        video_track = Track(1, "Video Track", "video")
        clip3 = Clip("Clip 3", 0.0, 20.0, 20.0, 1)
        video_track.add_clip(clip3)

        timeline.add_track(audio_track)
        timeline.add_track(video_track)

        # Add markers
        timeline.add_marker(5.0, "Marker 1")
        timeline.add_marker(15.0, "Marker 2")

        timeline.calculate_duration()
        stats = timeline.get_timeline_stats()

        assert stats["total_duration"] == 25.0
        assert stats["total_clips"] == 3
        assert stats["total_tracks"] == 2
        assert stats["audio_tracks"] == 1
        assert stats["video_tracks"] == 1
        assert stats["markers"] == 2
        assert stats["frame_rate"] == 30.0
        assert stats["sample_rate"] == 44100