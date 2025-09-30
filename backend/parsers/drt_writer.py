import xml.etree.ElementTree as ET
from xml.dom import minidom
from models.timeline import Timeline, Track, Clip
from typing import Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DRTWriter:
    """Writer for DaVinci Resolve Timeline (.drt) files"""

    def __init__(self):
        self.timeline = None

    def write_timeline(self, timeline: Timeline, output_path: str) -> bool:
        """Write Timeline object to .drt file"""
        try:
            xml_content = self.generate_drt_xml(timeline)
            with open(output_path, 'w', encoding='utf-8') as file:
                file.write(xml_content)
            logger.info(f"Successfully wrote .drt file to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing .drt file {output_path}: {str(e)}")
            return False

    def generate_drt_xml(self, timeline: Timeline) -> str:
        """Generate .drt XML content from Timeline object"""
        try:
            # Create root element
            root = ET.Element('xmeml', version='5')

            # Add project element
            project = ET.SubElement(root, 'project')

            # Add project name
            name_elem = ET.SubElement(project, 'name')
            name_elem.text = timeline.name

            # Add children (sequence container)
            children = ET.SubElement(project, 'children')

            # Add sequence
            sequence = self._create_sequence_element(timeline)
            children.append(sequence)

            # Convert to pretty XML string
            return self._prettify_xml(root)

        except Exception as e:
            logger.error(f"Error generating .drt XML: {str(e)}")
            raise

    def _create_sequence_element(self, timeline: Timeline) -> ET.Element:
        """Create sequence element from timeline"""
        sequence = ET.Element('sequence')
        sequence.set('id', 'sequence-1')

        # Add sequence name
        name = ET.SubElement(sequence, 'name')
        name.text = timeline.name

        # Add duration
        duration = ET.SubElement(sequence, 'duration')
        duration.text = str(int(timeline.duration * timeline.frame_rate))

        # Add rate (frame rate)
        rate = ET.SubElement(sequence, 'rate')
        rate_timebase = ET.SubElement(rate, 'timebase')
        rate_timebase.text = str(int(timeline.frame_rate))
        rate_ntsc = ET.SubElement(rate, 'ntsc')
        rate_ntsc.text = 'FALSE'

        # Add format
        format_elem = ET.SubElement(sequence, 'format')
        sample_characteristics = ET.SubElement(format_elem, 'samplecharacteristics')

        # Video characteristics
        rate_elem = ET.SubElement(sample_characteristics, 'rate')
        rate_timebase = ET.SubElement(rate_elem, 'timebase')
        rate_timebase.text = str(int(timeline.frame_rate))
        rate_ntsc = ET.SubElement(rate_elem, 'ntsc')
        rate_ntsc.text = 'FALSE'

        # Audio characteristics
        audio_elem = ET.SubElement(sample_characteristics, 'audio')
        sample_rate_elem = ET.SubElement(audio_elem, 'samplerate')
        sample_rate_elem.text = str(timeline.sample_rate)
        depth = ET.SubElement(audio_elem, 'depth')
        depth.text = '16'

        # Add media
        media = ET.SubElement(sequence, 'media')

        # Add video tracks
        video_tracks = timeline.get_tracks_by_type('video')
        if video_tracks:
            video = ET.SubElement(media, 'video')
            format_elem = ET.SubElement(video, 'format')
            sample_characteristics = ET.SubElement(format_elem, 'samplecharacteristics')

            # Video format details
            rate_elem = ET.SubElement(sample_characteristics, 'rate')
            rate_timebase = ET.SubElement(rate_elem, 'timebase')
            rate_timebase.text = str(int(timeline.frame_rate))

            width = ET.SubElement(sample_characteristics, 'width')
            width.text = '1920'
            height = ET.SubElement(sample_characteristics, 'height')
            height.text = '1080'

            # Add video tracks
            for track in video_tracks:
                track_elem = self._create_track_element(track, timeline.frame_rate)
                video.append(track_elem)

        # Add audio tracks
        audio_tracks = timeline.get_tracks_by_type('audio')
        if audio_tracks:
            audio = ET.SubElement(media, 'audio')
            format_elem = ET.SubElement(audio, 'format')
            sample_characteristics = ET.SubElement(format_elem, 'samplecharacteristics')

            # Audio format details
            depth = ET.SubElement(sample_characteristics, 'depth')
            depth.text = '16'
            sample_rate_elem = ET.SubElement(sample_characteristics, 'samplerate')
            sample_rate_elem.text = str(timeline.sample_rate)

            # Add audio tracks
            for track in audio_tracks:
                track_elem = self._create_track_element(track, timeline.frame_rate)
                audio.append(track_elem)

        # Add timecode
        timecode_elem = ET.SubElement(sequence, 'timecode')
        rate_elem = ET.SubElement(timecode_elem, 'rate')
        rate_timebase = ET.SubElement(rate_elem, 'timebase')
        rate_timebase.text = str(int(timeline.frame_rate))
        rate_ntsc = ET.SubElement(rate_elem, 'ntsc')
        rate_ntsc.text = 'FALSE'

        string_elem = ET.SubElement(timecode_elem, 'string')
        string_elem.text = '01:00:00:00'

        frame_elem = ET.SubElement(timecode_elem, 'frame')
        frame_elem.text = str(int(timeline.frame_rate * 3600))  # 1 hour worth of frames

        # Add markers
        for marker in timeline.markers:
            marker_elem = self._create_marker_element(marker, timeline.frame_rate)
            sequence.append(marker_elem)

        return sequence

    def _create_track_element(self, track: Track, frame_rate: float) -> ET.Element:
        """Create track element from Track object"""
        track_elem = ET.Element('track')

        # Add clips
        for clip in track.clips:
            clip_elem = self._create_clipitem_element(clip, frame_rate)
            track_elem.append(clip_elem)

        return track_elem

    def _create_clipitem_element(self, clip: Clip, frame_rate: float) -> ET.Element:
        """Create clipitem element from Clip object"""
        clipitem = ET.Element('clipitem', id=f'clipitem-{clip.name}')

        # Add clip name
        name = ET.SubElement(clipitem, 'name')
        name.text = clip.name

        # Add enabled status
        enabled = ET.SubElement(clipitem, 'enabled')
        enabled.text = 'TRUE' if clip.enabled else 'FALSE'

        # Add duration
        duration = ET.SubElement(clipitem, 'duration')
        duration.text = str(int(clip.duration * frame_rate))

        # Add rate
        rate = ET.SubElement(clipitem, 'rate')
        rate_timebase = ET.SubElement(rate, 'timebase')
        rate_timebase.text = str(int(frame_rate))
        rate_ntsc = ET.SubElement(rate, 'ntsc')
        rate_ntsc.text = 'FALSE'

        # Add start time
        start = ET.SubElement(clipitem, 'start')
        start.text = str(int(clip.start_time * frame_rate))

        # Add end time
        end = ET.SubElement(clipitem, 'end')
        end.text = str(int(clip.end_time * frame_rate))

        # Add in/out points
        in_point = ET.SubElement(clipitem, 'in')
        in_point.text = str(int((clip.media_start or 0) * frame_rate))

        out_point = ET.SubElement(clipitem, 'out')
        out_point.text = str(int((clip.media_end or clip.duration) * frame_rate))

        # Add file reference
        file_elem = ET.SubElement(clipitem, 'file', id=f'file-{clip.name}')

        file_name = ET.SubElement(file_elem, 'name')
        file_name.text = clip.name

        file_path = ET.SubElement(file_elem, 'pathurl')
        file_path.text = f'file://localhost/{clip.name}'

        # Add rate for file
        file_rate = ET.SubElement(file_elem, 'rate')
        file_rate_timebase = ET.SubElement(file_rate, 'timebase')
        file_rate_timebase.text = str(int(frame_rate))
        file_rate_ntsc = ET.SubElement(file_rate, 'ntsc')
        file_rate_ntsc.text = 'FALSE'

        # Add duration for file
        file_duration = ET.SubElement(file_elem, 'duration')
        file_duration.text = str(int(clip.duration * frame_rate))

        return clipitem

    def _create_marker_element(self, marker: Dict[str, Any], frame_rate: float) -> ET.Element:
        """Create marker element from marker data"""
        marker_elem = ET.Element('marker')

        # Add marker name
        name = ET.SubElement(marker_elem, 'name')
        name.text = marker['name']

        # Add marker comment
        comment = ET.SubElement(marker_elem, 'comment')
        comment.text = marker.get('comment', '')

        # Add marker in/out points (same for marker)
        marker_time_frames = int(marker['time'] * frame_rate)

        in_point = ET.SubElement(marker_elem, 'in')
        in_point.text = str(marker_time_frames)

        out_point = ET.SubElement(marker_elem, 'out')
        out_point.text = str(marker_time_frames + 1)  # Marker duration of 1 frame

        return marker_elem

    def _prettify_xml(self, element: ET.Element) -> str:
        """Return a pretty-printed XML string for the Element"""
        rough_string = ET.tostring(element, 'unicode')
        reparsed = minidom.parseString(rough_string)

        # Add XML declaration and DOCTYPE
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        doctype = '<!DOCTYPE xmeml>\n'

        pretty = reparsed.toprettyxml(indent="  ")

        # Remove the first line (minidom adds its own XML declaration)
        lines = pretty.split('\n')[1:]
        pretty_content = '\n'.join(lines)

        return xml_declaration + doctype + pretty_content

    def get_xml_preview(self, timeline: Timeline, max_lines: int = 50) -> str:
        """Get a preview of the XML that would be generated"""
        try:
            xml_content = self.generate_drt_xml(timeline)
            lines = xml_content.split('\n')
            preview_lines = lines[:max_lines]

            if len(lines) > max_lines:
                preview_lines.append(f"... ({len(lines) - max_lines} more lines)")

            return '\n'.join(preview_lines)

        except Exception as e:
            logger.error(f"Error generating XML preview: {str(e)}")
            return f"Error generating preview: {str(e)}"