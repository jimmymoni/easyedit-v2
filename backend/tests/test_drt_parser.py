import pytest
import tempfile
import os
from parsers.drt_parser import DRTParser
from parsers.drt_writer import DRTWriter
from models.timeline import Timeline, Track, Clip

class TestDRTParser:
    """Test cases for DRT XML parser"""

    def test_parse_basic_drt_content(self, sample_drt_xml):
        """Test parsing basic DRT XML content"""
        parser = DRTParser()
        timeline = parser.parse_content(sample_drt_xml)

        assert isinstance(timeline, Timeline)
        assert timeline.name == "Test Timeline"
        assert timeline.frame_rate == 25.0

    def test_parse_drt_file(self, temp_dir, sample_drt_xml):
        """Test parsing DRT file from disk"""
        # Create test DRT file
        drt_file_path = os.path.join(temp_dir, 'test_timeline.drt')
        with open(drt_file_path, 'w', encoding='utf-8') as f:
            f.write(sample_drt_xml)

        parser = DRTParser()
        timeline = parser.parse_file(drt_file_path)

        assert isinstance(timeline, Timeline)
        assert timeline.name == "Test Timeline"
        assert len(timeline.tracks) > 0

    def test_parse_tracks_and_clips(self, sample_drt_xml):
        """Test parsing tracks and clips from DRT"""
        parser = DRTParser()
        timeline = parser.parse_content(sample_drt_xml)

        # Should have at least one audio track
        audio_tracks = timeline.get_tracks_by_type('audio')
        assert len(audio_tracks) >= 1

        # Check clips in the first audio track
        audio_track = audio_tracks[0]
        assert len(audio_track.clips) >= 2

        # Verify clip properties
        first_clip = audio_track.clips[0]
        assert first_clip.name == "Test Clip 1"
        assert first_clip.enabled == True
        assert first_clip.start_time >= 0
        assert first_clip.end_time > first_clip.start_time

    def test_timecode_conversion(self):
        """Test timecode to seconds conversion"""
        parser = DRTParser()

        # Test standard timecode format (HH:MM:SS:FF at 25fps)
        assert parser._timecode_to_seconds("00:00:10:00", 25.0) == 10.0
        assert parser._timecode_to_seconds("00:01:30:12", 25.0) == 90.48
        assert parser._timecode_to_seconds("01:00:00:00", 25.0) == 3600.0

        # Test with different frame rates
        assert parser._timecode_to_seconds("00:00:10:00", 30.0) == 10.0
        assert parser._timecode_to_seconds("00:00:01:15", 30.0) == 1.5

        # Test numeric input
        assert parser._timecode_to_seconds(15.5) == 15.5
        assert parser._timecode_to_seconds("15.5") == 15.5

    def test_parse_invalid_xml(self):
        """Test parsing invalid XML raises appropriate error"""
        parser = DRTParser()
        invalid_xml = "<invalid>xml content without proper closing tags"

        with pytest.raises(Exception):
            parser.parse_content(invalid_xml)

    def test_parse_empty_timeline(self):
        """Test parsing timeline with no content"""
        empty_drt = """<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE xmeml>
        <xmeml version="5">
            <project>
                <name>Empty Timeline</name>
                <children>
                    <sequence id="sequence-1">
                        <name>Empty Timeline</name>
                        <duration>0</duration>
                    </sequence>
                </children>
            </project>
        </xmeml>"""

        parser = DRTParser()
        timeline = parser.parse_content(empty_drt)

        assert timeline.name == "Empty Timeline"
        assert len(timeline.tracks) == 0
        assert timeline.duration == 0.0

    def test_get_timeline_summary(self, sample_drt_xml):
        """Test getting timeline summary after parsing"""
        parser = DRTParser()
        timeline = parser.parse_content(sample_drt_xml)

        summary = parser.get_timeline_summary()
        assert isinstance(summary, dict)
        assert "total_duration" in summary
        assert "total_clips" in summary
        assert "total_tracks" in summary

class TestDRTWriter:
    """Test cases for DRT XML writer"""

    def test_generate_basic_drt_xml(self, sample_timeline):
        """Test generating DRT XML from timeline"""
        writer = DRTWriter()
        xml_content = writer.generate_drt_xml(sample_timeline)

        assert isinstance(xml_content, str)
        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml_content
        assert '<!DOCTYPE xmeml>' in xml_content
        assert '<xmeml version="5">' in xml_content
        assert sample_timeline.name in xml_content

    def test_write_timeline_to_file(self, sample_timeline, temp_dir):
        """Test writing timeline to file"""
        writer = DRTWriter()
        output_path = os.path.join(temp_dir, 'output_timeline.drt')

        success = writer.write_timeline(sample_timeline, output_path)

        assert success == True
        assert os.path.exists(output_path)

        # Verify file content
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert '<?xml version="1.0" encoding="UTF-8"?>' in content
            assert sample_timeline.name in content

    def test_roundtrip_parse_write(self, sample_drt_xml, temp_dir):
        """Test parsing DRT and then writing it back (roundtrip)"""
        parser = DRTParser()
        writer = DRTWriter()

        # Parse original
        original_timeline = parser.parse_content(sample_drt_xml)

        # Write to file
        output_path = os.path.join(temp_dir, 'roundtrip_timeline.drt')
        success = writer.write_timeline(original_timeline, output_path)
        assert success == True

        # Parse the written file
        new_timeline = parser.parse_file(output_path)

        # Compare key properties
        assert new_timeline.name == original_timeline.name
        assert new_timeline.frame_rate == original_timeline.frame_rate
        assert len(new_timeline.tracks) == len(original_timeline.tracks)

        # Compare first audio track
        if len(new_timeline.tracks) > 0:
            original_audio_tracks = original_timeline.get_tracks_by_type('audio')
            new_audio_tracks = new_timeline.get_tracks_by_type('audio')

            if len(original_audio_tracks) > 0 and len(new_audio_tracks) > 0:
                orig_track = original_audio_tracks[0]
                new_track = new_audio_tracks[0]

                # Should have same number of clips (approximately - some rounding may occur)
                assert abs(len(orig_track.clips) - len(new_track.clips)) <= 1

    def test_create_track_element(self, sample_timeline):
        """Test creating track element XML"""
        writer = DRTWriter()
        audio_track = sample_timeline.get_tracks_by_type('audio')[0]

        track_element = writer._create_track_element(audio_track, 25.0)

        # Should be an XML element
        assert track_element.tag == 'track'
        assert len(list(track_element)) == len(audio_track.clips)  # Should have clipitem children

    def test_create_clipitem_element(self, sample_timeline):
        """Test creating clipitem element XML"""
        writer = DRTWriter()
        audio_track = sample_timeline.get_tracks_by_type('audio')[0]
        clip = audio_track.clips[0]

        clipitem_element = writer._create_clipitem_element(clip, 25.0)

        assert clipitem_element.tag == 'clipitem'
        assert clipitem_element.get('id') is not None

        # Check for required child elements
        children_tags = [child.tag for child in clipitem_element]
        assert 'name' in children_tags
        assert 'enabled' in children_tags
        assert 'duration' in children_tags
        assert 'start' in children_tags
        assert 'end' in children_tags

    def test_create_marker_element(self):
        """Test creating marker element XML"""
        writer = DRTWriter()
        marker = {
            'time': 10.0,
            'name': 'Test Marker',
            'color': 'Red'
        }

        marker_element = writer._create_marker_element(marker, 25.0)

        assert marker_element.tag == 'marker'

        # Check child elements
        children_tags = [child.tag for child in marker_element]
        assert 'name' in children_tags
        assert 'in' in children_tags
        assert 'out' in children_tags

    def test_get_xml_preview(self, sample_timeline):
        """Test getting XML preview"""
        writer = DRTWriter()
        preview = writer.get_xml_preview(sample_timeline, max_lines=10)

        assert isinstance(preview, str)
        lines = preview.split('\n')
        assert len(lines) <= 12  # max_lines + potential truncation message

        assert '<?xml version="1.0" encoding="UTF-8"?>' in preview
        assert sample_timeline.name in preview

    def test_write_timeline_with_markers(self, temp_dir):
        """Test writing timeline that includes markers"""
        # Create timeline with markers
        timeline = Timeline("Timeline with Markers", frame_rate=25.0)
        audio_track = Track(0, "Audio Track", "audio")
        clip = Clip("Test Clip", 0.0, 10.0, 10.0, 0)
        audio_track.add_clip(clip)
        timeline.add_track(audio_track)

        # Add markers
        timeline.add_marker(2.5, "Intro Marker", "Green")
        timeline.add_marker(7.5, "Outro Marker", "Blue")

        writer = DRTWriter()
        output_path = os.path.join(temp_dir, 'timeline_with_markers.drt')

        success = writer.write_timeline(timeline, output_path)
        assert success == True

        # Verify markers are in the output
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'Intro Marker' in content
            assert 'Outro Marker' in content
            assert '<marker>' in content

    def test_write_empty_timeline(self, temp_dir):
        """Test writing empty timeline"""
        timeline = Timeline("Empty Timeline")

        writer = DRTWriter()
        output_path = os.path.join(temp_dir, 'empty_timeline.drt')

        success = writer.write_timeline(timeline, output_path)
        assert success == True

        # Should still create valid XML
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert '<?xml version="1.0" encoding="UTF-8"?>' in content
            assert "Empty Timeline" in content

    def test_write_to_invalid_path(self, sample_timeline):
        """Test writing to invalid path returns False"""
        writer = DRTWriter()
        invalid_path = "/nonexistent/directory/timeline.drt"

        success = writer.write_timeline(sample_timeline, invalid_path)
        assert success == False