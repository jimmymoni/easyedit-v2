import pytest
import os
from pathlib import Path

from parsers.drt_parser import DRTParser
from parsers.drt_writer import DRTWriter


class TestRealDRTFiles:
    """Test parsing and writing of realistic DaVinci Resolve timeline files"""

    @pytest.fixture
    def sample_data_dir(self):
        """Get path to sample data directory"""
        return Path(__file__).parent / 'sample_data'

    @pytest.fixture
    def drt_files(self, sample_data_dir):
        """List of real DRT test files"""
        return [
            sample_data_dir / 'interview_timeline_v17.drt',
            sample_data_dir / 'podcast_timeline_v18.drt',
            sample_data_dir / 'music_production_timeline.drt',
            sample_data_dir / 'webinar_timeline_simple.drt'
        ]

    def test_parse_all_sample_drt_files(self, drt_files):
        """Test parsing all sample DRT files"""
        parser = DRTParser()

        for drt_file in drt_files:
            assert drt_file.exists(), f"Sample DRT file not found: {drt_file}"

            timeline = parser.parse_file(str(drt_file))

            assert timeline is not None, f"Failed to parse {drt_file.name}"
            assert timeline.name != "", f"Timeline name empty for {drt_file.name}"
            assert timeline.duration > 0, f"Invalid duration for {drt_file.name}"
            assert len(timeline.tracks) > 0, f"No tracks found in {drt_file.name}"

            print(f"✓ Parsed {drt_file.name}: {timeline.name} ({timeline.duration}s, {len(timeline.tracks)} tracks)")

    def test_interview_timeline_v17_specifics(self, sample_data_dir):
        """Test specific properties of the DaVinci Resolve 17 interview timeline"""
        parser = DRTParser()
        timeline = parser.parse_file(str(sample_data_dir / 'interview_timeline_v17.drt'))

        assert timeline.name == "Interview Timeline"
        assert timeline.frame_rate == 24  # 24fps
        assert timeline.sample_rate == 48000  # 48kHz audio

        # Should have 2 audio tracks (interview + background music)
        audio_tracks = timeline.get_tracks_by_type('audio')
        assert len(audio_tracks) == 2

        # First track should have 2 clips (interview parts)
        first_track = audio_tracks[0]
        assert len(first_track.clips) == 2
        assert first_track.clips[0].name == "Interview_Audio_01"
        assert first_track.clips[1].name == "Interview_Audio_02"

        # Should have markers
        assert len(timeline.markers) >= 5  # Interview Start, Question 1, Question 2, Break, Resume

    def test_podcast_timeline_v18_specifics(self, sample_data_dir):
        """Test specific properties of the DaVinci Resolve 18 podcast timeline"""
        parser = DRTParser()
        timeline = parser.parse_file(str(sample_data_dir / 'podcast_timeline_v18.drt'))

        assert timeline.name == "Podcast Episode 42"
        assert timeline.frame_rate == 25  # 25fps PAL
        assert timeline.sample_rate == 48000  # 48kHz audio

        # Should have 4 audio tracks (host, guest, intro/outro music, ambience)
        audio_tracks = timeline.get_tracks_by_type('audio')
        assert len(audio_tracks) == 4

        # Host track should span full duration
        host_track = audio_tracks[0]
        assert len(host_track.clips) == 1
        assert host_track.clips[0].duration == 7200  # Full 2-hour podcast

        # Guest track should start at 600 (after intro)
        guest_track = audio_tracks[1]
        assert guest_track.clips[0].start_time == 600

        # Should have many markers for podcast structure
        assert len(timeline.markers) >= 8

    def test_music_production_timeline_specifics(self, sample_data_dir):
        """Test specific properties of the music production timeline"""
        parser = DRTParser()
        timeline = parser.parse_file(str(sample_data_dir / 'music_production_timeline.drt'))

        assert timeline.name == "Song_Recording_Session"
        assert timeline.frame_rate == 30  # 30fps NTSC
        assert timeline.sample_rate == 96000  # High quality 96kHz audio

        # Should have many tracks for multi-track recording
        audio_tracks = timeline.get_tracks_by_type('audio')
        assert len(audio_tracks) >= 8  # Multiple instrument tracks

        # Track names should reflect instruments
        track_names = [track.clips[0].name for track in audio_tracks if track.clips]
        instrument_tracks = [name for name in track_names if any(inst in name.lower()
                           for inst in ['vocal', 'guitar', 'bass', 'drum', 'piano'])]
        assert len(instrument_tracks) >= 6

        # Should have song structure markers
        marker_names = [marker.name for marker in timeline.markers]
        structure_markers = [name for name in marker_names if any(part in name.lower()
                           for part in ['intro', 'verse', 'chorus', 'bridge', 'solo'])]
        assert len(structure_markers) >= 5

    def test_webinar_timeline_simple_specifics(self, sample_data_dir):
        """Test specific properties of the simple webinar timeline"""
        parser = DRTParser()
        timeline = parser.parse_file(str(sample_data_dir / 'webinar_timeline_simple.drt'))

        assert timeline.name == "Webinar_Jan2024"
        assert abs(timeline.frame_rate - 23.98) < 0.01  # 23.98fps
        assert timeline.sample_rate == 44100  # Standard CD quality

        # Should have single audio track
        audio_tracks = timeline.get_tracks_by_type('audio')
        assert len(audio_tracks) == 1

        # Single clip for entire webinar
        assert len(audio_tracks[0].clips) == 1
        assert audio_tracks[0].clips[0].name == "Webinar_Main_Audio"

        # Should have basic content markers
        assert len(timeline.markers) == 4  # Opening, Presentation, Q&A, Closing

    def test_roundtrip_parsing_all_files(self, drt_files, temp_dir):
        """Test parsing and writing back all sample DRT files"""
        parser = DRTParser()
        writer = DRTWriter()

        for drt_file in drt_files:
            # Parse original
            original_timeline = parser.parse_file(str(drt_file))
            assert original_timeline is not None

            # Write to new file
            output_file = os.path.join(temp_dir, f"roundtrip_{drt_file.name}")
            success = writer.write_timeline(original_timeline, output_file)
            assert success == True
            assert os.path.exists(output_file)

            # Parse the written file
            roundtrip_timeline = parser.parse_file(output_file)
            assert roundtrip_timeline is not None

            # Compare key properties
            assert roundtrip_timeline.name == original_timeline.name
            assert roundtrip_timeline.frame_rate == original_timeline.frame_rate
            assert roundtrip_timeline.sample_rate == original_timeline.sample_rate
            assert len(roundtrip_timeline.tracks) == len(original_timeline.tracks)
            assert len(roundtrip_timeline.markers) == len(original_timeline.markers)

            print(f"✓ Roundtrip successful for {drt_file.name}")

    def test_different_frame_rates(self, drt_files):
        """Test handling of different frame rates across DRT files"""
        parser = DRTParser()
        frame_rates = []

        for drt_file in drt_files:
            timeline = parser.parse_file(str(drt_file))
            frame_rates.append(timeline.frame_rate)

        # Should have different frame rates in our test files
        unique_rates = set(frame_rates)
        assert len(unique_rates) >= 3, f"Expected multiple frame rates, got: {unique_rates}"

        # Common frame rates should be present
        common_rates = {23.98, 24, 25, 30}
        found_rates = unique_rates.intersection(common_rates)
        assert len(found_rates) >= 3, f"Expected common frame rates, found: {found_rates}"

    def test_different_sample_rates(self, drt_files):
        """Test handling of different audio sample rates"""
        parser = DRTParser()
        sample_rates = []

        for drt_file in drt_files:
            timeline = parser.parse_file(str(drt_file))
            sample_rates.append(timeline.sample_rate)

        # Should have different sample rates
        unique_rates = set(sample_rates)
        assert len(unique_rates) >= 2, f"Expected multiple sample rates, got: {unique_rates}"

        # Common audio sample rates
        common_audio_rates = {44100, 48000, 96000}
        found_rates = unique_rates.intersection(common_audio_rates)
        assert len(found_rates) >= 2, f"Expected common audio rates, found: {found_rates}"

    def test_track_and_clip_validation(self, drt_files):
        """Test validation of tracks and clips across all files"""
        parser = DRTParser()

        total_tracks = 0
        total_clips = 0

        for drt_file in drt_files:
            timeline = parser.parse_file(str(drt_file))

            for track in timeline.tracks:
                total_tracks += 1
                assert track.track_type in ['audio', 'video'], f"Invalid track type: {track.track_type}"

                for clip in track.clips:
                    total_clips += 1
                    assert clip.start_time >= 0, f"Invalid clip start time: {clip.start_time}"
                    assert clip.end_time > clip.start_time, f"Invalid clip timing: {clip.start_time} -> {clip.end_time}"
                    assert clip.duration > 0, f"Invalid clip duration: {clip.duration}"
                    assert clip.name != "", f"Empty clip name"

        # Should have processed substantial amount of content
        assert total_tracks >= 10, f"Expected multiple tracks across files, got: {total_tracks}"
        assert total_clips >= 15, f"Expected multiple clips across files, got: {total_clips}"

        print(f"✓ Validated {total_tracks} tracks and {total_clips} clips across {len(drt_files)} files")

    def test_marker_validation(self, drt_files):
        """Test validation of markers across all files"""
        parser = DRTParser()

        total_markers = 0

        for drt_file in drt_files:
            timeline = parser.parse_file(str(drt_file))

            for marker in timeline.markers:
                total_markers += 1
                assert marker.name != "", f"Empty marker name in {drt_file.name}"
                assert marker.time >= 0, f"Invalid marker time: {marker.time}"

                # Markers should be within timeline duration
                assert marker.time <= timeline.duration, f"Marker beyond timeline duration: {marker.time} > {timeline.duration}"

        # Should have found markers in our test files
        assert total_markers >= 15, f"Expected multiple markers across files, got: {total_markers}"

        print(f"✓ Validated {total_markers} markers across {len(drt_files)} files")

    def test_file_path_handling(self, drt_files):
        """Test handling of file paths in DRT files"""
        parser = DRTParser()

        for drt_file in drt_files:
            timeline = parser.parse_file(str(drt_file))

            for track in timeline.tracks:
                for clip in track.clips:
                    if hasattr(clip, 'source_file') and clip.source_file:
                        # File paths should be reasonable
                        assert len(clip.source_file) > 0
                        assert not clip.source_file.startswith('\\\\'), "UNC paths should be handled"

                        # Common audio extensions should be present
                        if any(ext in clip.source_file.lower() for ext in ['.wav', '.mp3', '.m4a', '.aiff']):
                            print(f"✓ Found audio file reference: {clip.source_file}")

    def test_xml_version_compatibility(self, drt_files):
        """Test compatibility with different XML versions"""
        parser = DRTParser()

        for drt_file in drt_files:
            # Read raw XML to check version
            with open(drt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Should be able to parse regardless of XML structure variations
            timeline = parser.parse_file(str(drt_file))
            assert timeline is not None, f"Failed to parse {drt_file.name}"

            # Check for XML version indicators
            if 'xmeml version="4"' in content:
                print(f"✓ {drt_file.name}: XML version 4 (older format)")
            elif 'xmeml version="5"' in content:
                print(f"✓ {drt_file.name}: XML version 5 (newer format)")

            # Both should parse successfully
            assert len(timeline.tracks) > 0