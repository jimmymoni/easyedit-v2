import xml.etree.ElementTree as ET  # Safe for writing (creating elements)
from defusedxml import minidom as defused_minidom  # Secure for parsing
from xml.dom import minidom
from models.timeline import Timeline, Track, Clip
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class FCP7XMLWriter:
    """Writer for Final Cut Pro 7 XML (.xml) timeline files"""

    def __init__(self):
        self.timeline = None

    def write_timeline(self, timeline: Timeline, output_path: str) -> bool:
        """Write Timeline object to FCP7 XML file"""
        try:
            xml_content = self.generate_fcp7_xml(timeline)
            with open(output_path, 'w', encoding='utf-8') as file:
                file.write(xml_content)
            logger.info(f"Successfully wrote FCP7 XML file to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing FCP7 XML file {output_path}: {str(e)}")
            return False

    def generate_fcp7_xml(self, timeline: Timeline) -> str:
        """Generate FCP7 XML content from Timeline object"""
        try:
            # Create root element
            root = ET.Element('xmeml', version='5')

            # Add sequence directly under xmeml root (DaVinci Resolve format)
            # DaVinci expects <xmeml><sequence>, NOT <xmeml><project><children><sequence>
            sequence = self._create_sequence_element(timeline)
            root.append(sequence)

            # Convert to pretty XML string
            xml_str = self._prettify_xml(root)

            # Validate output
            if not xml_str.startswith('<?xml version="1.0"'):
                raise ValueError("Generated XML missing XML declaration")
            if '<xmeml version="5">' not in xml_str:
                raise ValueError("Generated XML missing FCP7 xmeml root element")

            return xml_str

        except Exception as e:
            logger.error(f"Error generating FCP7 XML: {str(e)}")
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

        # Get canonical file block
        canonical_block = timeline.get_canonical_file_block()
        if not canonical_block:
            logger.warning("No canonical file block - clips may not import to DaVinci Resolve correctly")

        # Add media
        media = ET.SubElement(sequence, 'media')

        # Add video tracks
        video_tracks = timeline.get_tracks_by_type('video')
        if video_tracks:
            video = ET.SubElement(media, 'video')

            # Add video tracks FIRST (before format) - DaVinci Resolve structure
            # First track gets is_first_track=True for canonical file block placement
            for idx, track in enumerate(video_tracks):
                track_elem = self._create_track_element(
                    track, timeline.frame_rate, canonical_block,
                    is_first_track=(idx == 0)
                )
                video.append(track_elem)

            # Format comes AFTER tracks in DaVinci Resolve XML
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

        # Add audio tracks
        audio_tracks = timeline.get_tracks_by_type('audio')
        if audio_tracks:
            audio = ET.SubElement(media, 'audio')

            # Add audio tracks - all reference the same file ID (is_first_track=False)
            for track in audio_tracks:
                track_elem = self._create_track_element(
                    track, timeline.frame_rate, canonical_block,
                    is_first_track=False
                )
                audio.append(track_elem)

            format_elem = ET.SubElement(audio, 'format')
            sample_characteristics = ET.SubElement(format_elem, 'samplecharacteristics')

            # Audio format details
            depth = ET.SubElement(sample_characteristics, 'depth')
            depth.text = '16'
            sample_rate_elem = ET.SubElement(sample_characteristics, 'samplerate')
            sample_rate_elem.text = str(timeline.sample_rate)

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

    def _create_track_element(self, track: Track, frame_rate: float,
                             canonical_block: Optional[Dict[str, Any]] = None,
                             is_first_track: bool = False) -> ET.Element:
        """Create track element from Track object"""
        track_elem = ET.Element('track')

        # Add clips - first clip of first track gets full file block
        for idx, clip in enumerate(track.clips):
            is_first_clip = (is_first_track and idx == 0)
            clip_elem = self._create_clipitem_element(clip, frame_rate, canonical_block, is_first_clip)
            track_elem.append(clip_elem)

        return track_elem

    def _create_clipitem_element(self, clip: Clip, frame_rate: float,
                                canonical_block: Optional[Dict[str, Any]] = None,
                                is_first_clip: bool = False) -> ET.Element:
        """Create clipitem - first clip gets full file block, rest reference by ID"""
        clipitem = ET.Element('clipitem', id=f'clipitem-{clip.name}')

        # Add clip name
        name = ET.SubElement(clipitem, 'name')
        name.text = clip.name

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

        # Add enabled status
        enabled = ET.SubElement(clipitem, 'enabled')
        enabled.text = 'TRUE' if clip.enabled else 'FALSE'

        # Add in/out points
        in_point = ET.SubElement(clipitem, 'in')
        in_point.text = str(int((clip.media_start or 0) * frame_rate))

        out_point = ET.SubElement(clipitem, 'out')
        out_point.text = str(int((clip.media_end or clip.duration) * frame_rate))

        # FILE BLOCK - full on first clip, reference-only on subsequent clips
        if canonical_block:
            if is_first_clip:
                # FIRST CLIP: Full canonical file block inline
                file_elem = self._create_canonical_file_element(canonical_block, frame_rate)
                clipitem.append(file_elem)
            else:
                # SUBSEQUENT CLIPS: Reference by ID only (self-closing tag)
                file_ref = ET.SubElement(clipitem, 'file', id=canonical_block['file_id'])
        else:
            # Fallback: inline file block (old behavior for backward compatibility)
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

        # Add filters from canonical block (preserves effects)
        if canonical_block and canonical_block.get('filters'):
            self._add_filters_to_clipitem(clipitem, canonical_block['filters'])

        return clipitem

    def _create_canonical_file_element(self, canonical_block: Dict[str, Any],
                                       frame_rate: float) -> ET.Element:
        """Generate complete file element from canonical block (DaVinci Resolve format)"""
        file_elem = ET.Element('file', id=canonical_block['file_id'])

        # Duration (comes first in DaVinci XML)
        duration = ET.SubElement(file_elem, 'duration')
        duration.text = str(canonical_block.get('duration_frames', 0))

        # Rate
        rate = ET.SubElement(file_elem, 'rate')
        timebase = ET.SubElement(rate, 'timebase')
        timebase.text = str(int(frame_rate))
        ntsc = ET.SubElement(rate, 'ntsc')
        ntsc.text = 'FALSE'

        # Name
        name = ET.SubElement(file_elem, 'name')
        name.text = canonical_block['name']

        # Pathurl
        pathurl = ET.SubElement(file_elem, 'pathurl')
        pathurl.text = canonical_block['pathurl']

        # Timecode (preserve exact original)
        if canonical_block.get('timecode'):
            tc = canonical_block['timecode']
            timecode_elem = ET.SubElement(file_elem, 'timecode')

            if tc.get('string'):
                string = ET.SubElement(timecode_elem, 'string')
                string.text = tc['string']
            if tc.get('displayformat'):
                display = ET.SubElement(timecode_elem, 'displayformat')
                display.text = tc['displayformat']

            # Rate in timecode
            rate = ET.SubElement(timecode_elem, 'rate')
            timebase = ET.SubElement(rate, 'timebase')
            timebase.text = str(int(frame_rate))
            ntsc = ET.SubElement(rate, 'ntsc')
            ntsc.text = 'FALSE'

        # Media characteristics
        media_elem = ET.SubElement(file_elem, 'media')

        # Video characteristics
        if canonical_block.get('samplecharacteristics'):
            video_elem = ET.SubElement(media_elem, 'video')

            # Duration in video element
            duration_vid = ET.SubElement(video_elem, 'duration')
            duration_vid.text = str(canonical_block.get('duration_frames', 0))

            # Sample characteristics
            sc_elem = ET.SubElement(video_elem, 'samplecharacteristics')
            sc = canonical_block['samplecharacteristics']

            if sc.get('width'):
                width = ET.SubElement(sc_elem, 'width')
                width.text = str(sc['width'])
            if sc.get('height'):
                height = ET.SubElement(sc_elem, 'height')
                height.text = str(sc['height'])

        # Audio characteristics
        if canonical_block.get('audio'):
            audio_elem = ET.SubElement(media_elem, 'audio')
            audio = canonical_block['audio']

            if audio.get('channelcount'):
                cc = ET.SubElement(audio_elem, 'channelcount')
                cc.text = str(audio['channelcount'])

        return file_elem

    def _add_filters_to_clipitem(self, clipitem: ET.Element,
                                filters: Dict[str, str]) -> None:
        """Add filter XML strings to clipitem (preserves effects)"""
        for filter_name, filter_xml in filters.items():
            try:
                # Parse stored filter XML string and append
                filter_elem = ET.fromstring(filter_xml)
                clipitem.append(filter_elem)
            except Exception as e:
                logger.warning(f"Failed to add filter {filter_name}: {e}")

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
        # Use defusedxml for secure parsing
        reparsed = defused_minidom.parseString(rough_string)

        # Add XML declaration and DOCTYPE
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        doctype = '<!DOCTYPE xmeml>\n'

        pretty = reparsed.toprettyxml(indent="  ")

        # Remove the first line (minidom adds its own XML declaration)
        lines = pretty.split('\n')[1:]
        pretty_content = '\n'.join(lines)

        return xml_declaration + doctype + pretty_content

    def get_xml_preview(self, timeline: Timeline, max_lines: int = 50) -> str:
        """Get a preview of the FCP7 XML that would be generated"""
        try:
            xml_content = self.generate_fcp7_xml(timeline)
            lines = xml_content.split('\n')
            preview_lines = lines[:max_lines]

            if len(lines) > max_lines:
                preview_lines.append(f"... ({len(lines) - max_lines} more lines)")

            return '\n'.join(preview_lines)

        except Exception as e:
            logger.error(f"Error generating XML preview: {str(e)}")
            return f"Error generating preview: {str(e)}"
