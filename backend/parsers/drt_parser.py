import defusedxml.ElementTree as ET
import json
from typing import Dict, Any, Optional
from models.timeline import Timeline, Track, Clip
import logging

from utils.error_handlers import ValidationError, ProcessingError

logger = logging.getLogger(__name__)

class DRTParser:
    """Parser for DaVinci Resolve Timeline (.drt) files"""

    def __init__(self):
        self.timeline = None

    def parse_file(self, file_path: str) -> Timeline:
        """Parse a .drt file and return a Timeline object"""
        try:
            if not file_path or not isinstance(file_path, str):
                raise ValidationError("Invalid file path provided")

            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            if not content.strip():
                raise ValidationError("DRT file is empty")

            return self.parse_content(content)

        except FileNotFoundError:
            logger.error(f"DRT file not found: {file_path}")
            raise ValidationError(f"DRT file not found: {file_path}")
        except PermissionError:
            logger.error(f"Permission denied reading DRT file: {file_path}")
            raise ValidationError(f"Permission denied reading DRT file: {file_path}")
        except UnicodeDecodeError as e:
            logger.error(f"Invalid encoding in DRT file {file_path}: {str(e)}")
            raise ValidationError(f"DRT file contains invalid encoding: {str(e)}")
        except (ValidationError, ProcessingError):
            # Re-raise our custom errors
            raise
        except Exception as e:
            logger.exception(f"Unexpected error parsing .drt file {file_path}")
            raise ProcessingError(f"Failed to parse DRT file: {str(e)}")

    def parse_content(self, xml_content: str) -> Timeline:
        """Parse .drt XML content and return a Timeline object"""
        try:
            if not xml_content or not isinstance(xml_content, str):
                raise ValidationError("Invalid XML content provided")

            xml_content = xml_content.strip()
            if not xml_content:
                raise ValidationError("XML content is empty")

            # Basic XML validation
            if not xml_content.startswith('<'):
                raise ValidationError("Content does not appear to be valid XML")

            # Secure XML parsing with defusedxml (automatic XXE protection)
            root = ET.fromstring(xml_content)
            data = self._xml_to_dict(root)

            # Extract timeline information
            timeline_data = self._extract_timeline_data(data)
            if not timeline_data:
                raise ProcessingError("No valid timeline data found in DRT file")

            timeline = self._create_timeline_from_data(timeline_data)
            if not timeline:
                raise ProcessingError("Failed to create timeline from DRT data")

            self.timeline = timeline
            return timeline

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {str(e)}")
            raise ValidationError(f"Invalid XML format: {str(e)}")
        except (ValidationError, ProcessingError):
            # Re-raise our custom errors
            raise
        except Exception as e:
            logger.exception(f"Unexpected error parsing .drt content")
            raise ProcessingError(f"Failed to parse DRT content: {str(e)}")

    def _xml_to_dict(self, element) -> Dict[str, Any]:
        """Convert XML element to dictionary (secure replacement for xmltodict)"""
        result = {}

        # Add attributes
        if element.attrib:
            for key, value in element.attrib.items():
                result[f'@{key}'] = value

        # Add children
        for child in element:
            child_data = self._xml_to_dict(child)
            if child.tag in result:
                # Multiple children with same tag - convert to list
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data

        # Add text content
        if element.text and element.text.strip():
            if result:
                result['#text'] = element.text.strip()
            else:
                return element.text.strip()

        return result

    def _extract_timeline_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract timeline data from parsed XML dictionary"""
        # Navigate through the XML structure to find timeline data
        # Supports both FCP XML (xmeml) and custom formats

        timeline_data = {
            'name': 'Imported Timeline',
            'frame_rate': 25.0,
            'sample_rate': 48000,
            'tracks': [],
            'markers': [],
            'metadata': {}
        }

        try:
            sequence = None

            # Detect FCP XML format - sequence can be at root level or nested
            # When _xml_to_dict processes <xmeml><sequence>, 'sequence' appears at root
            if 'sequence' in data:
                sequence = data['sequence']
                logger.debug("Found FCP XML sequence at root level")

            # Check for nested formats
            elif 'xmeml' in data:
                xmeml_root = data['xmeml']
                logger.debug("Detected nested xmeml structure")

                # Check for direct sequence
                if 'sequence' in xmeml_root:
                    sequence = xmeml_root['sequence']
                    logger.debug("Found sequence in xmeml")

                # Check for project > children > sequence
                elif 'project' in xmeml_root:
                    project = xmeml_root['project']
                    if 'children' in project and 'sequence' in project['children']:
                        sequence = project['children']['sequence']
                        logger.debug("Found nested sequence in project")

            # Fallback to old custom formats
            else:
                root = data.get('resolve', data.get('timeline', data))
                logger.debug("Using legacy format detection")

                # Extract basic timeline properties (old format)
                if 'timeline' in root:
                    timeline_info = root['timeline']
                    timeline_data['name'] = timeline_info.get('@name', 'Imported Timeline')
                    timeline_data['frame_rate'] = float(timeline_info.get('@framerate', 25.0))

                # Extract tracks (old format)
                if 'track' in root:
                    tracks = root['track']
                    if not isinstance(tracks, list):
                        tracks = [tracks]

                    for track_data in tracks:
                        track_info = self._parse_track_data(track_data)
                        if track_info:
                            timeline_data['tracks'].append(track_info)

                # Extract markers (old format)
                if 'marker' in root:
                    markers = root['marker']
                    if not isinstance(markers, list):
                        markers = [markers]

                    for marker_data in markers:
                        marker_info = self._parse_marker_data(marker_data)
                        if marker_info:
                            timeline_data['markers'].append(marker_info)

                return timeline_data

            # Parse FCP XML sequence
            if sequence:
                # Extract timeline name and properties
                timeline_data['name'] = sequence.get('name', 'Imported Timeline')

                # Extract frame rate from rate element
                if 'rate' in sequence:
                    rate = sequence['rate']
                    if 'timebase' in rate:
                        timeline_data['frame_rate'] = float(rate['timebase'])

                # Extract sample rate from format if available
                if 'format' in sequence:
                    format_data = sequence['format']
                    if 'samplecharacteristics' in format_data:
                        sample_chars = format_data['samplecharacteristics']
                        if 'audio' in sample_chars and 'samplerate' in sample_chars['audio']:
                            timeline_data['sample_rate'] = int(sample_chars['audio']['samplerate'])

                # Extract tracks from media element
                if 'media' in sequence:
                    media = sequence['media']
                    track_index = 0

                    # Parse video tracks
                    if 'video' in media:
                        video_data = media['video']
                        video_tracks = video_data.get('track', [])
                        if not isinstance(video_tracks, list):
                            video_tracks = [video_tracks]

                        for video_track in video_tracks:
                            track_info = self._parse_fcp_track(video_track, track_index, 'video', timeline_data['frame_rate'])
                            if track_info:
                                timeline_data['tracks'].append(track_info)
                                track_index += 1

                    # Parse audio tracks
                    if 'audio' in media:
                        audio_data = media['audio']
                        audio_tracks = audio_data.get('track', [])
                        if not isinstance(audio_tracks, list):
                            audio_tracks = [audio_tracks]

                        for audio_track in audio_tracks:
                            track_info = self._parse_fcp_track(audio_track, track_index, 'audio', timeline_data['frame_rate'])
                            if track_info:
                                timeline_data['tracks'].append(track_info)
                                track_index += 1
                else:
                    logger.warning("No media element found in FCP XML sequence")

                logger.info(f"Parsed FCP XML timeline: {timeline_data['name']}, {len(timeline_data['tracks'])} tracks")

        except Exception as e:
            logger.warning(f"Error extracting timeline data: {str(e)}")
            # Return basic structure even if parsing fails

        return timeline_data

    def _parse_fcp_track(self, track_data: Dict[str, Any], track_index: int, track_type: str, fps: float) -> Optional[Dict[str, Any]]:
        """Parse FCP XML track data (from <media><video/audio><track>)"""
        try:
            track_info = {
                'index': track_index,
                'name': f'{track_type.capitalize()} Track {track_index + 1}',
                'type': track_type,
                'clips': []
            }

            # Extract clip items
            clipitems = track_data.get('clipitem', [])
            if not isinstance(clipitems, list):
                clipitems = [clipitems]

            for clipitem in clipitems:
                try:
                    # Parse FCP XML clipitem structure
                    clip_info = {
                        'name': clipitem.get('name', 'Unnamed Clip'),
                        'start_time': float(clipitem.get('start', 0)) / fps,  # Convert frames to seconds
                        'end_time': float(clipitem.get('end', 0)) / fps,
                        'duration': float(clipitem.get('duration', 0)) / fps,
                        'enabled': clipitem.get('enabled', 'TRUE').upper() == 'TRUE'
                    }

                    # Extract in/out points if available
                    if 'in' in clipitem:
                        clip_info['media_in'] = float(clipitem['in']) / fps
                    if 'out' in clipitem:
                        clip_info['media_out'] = float(clipitem['out']) / fps

                    # Extract file information if available
                    if 'file' in clipitem:
                        file_info = clipitem['file']
                        if isinstance(file_info, dict):  # Full file info
                            clip_info['file_name'] = file_info.get('name', '')
                            clip_info['file_path'] = file_info.get('pathurl', '')
                        # else: file reference by id only

                    track_info['clips'].append(clip_info)

                except Exception as e:
                    logger.warning(f"Failed to parse FCP clipitem: {str(e)}")
                    continue

            logger.debug(f"Parsed {track_type} track {track_index} with {len(track_info['clips'])} clips")
            return track_info

        except Exception as e:
            logger.warning(f"Error parsing FCP track: {str(e)}")
            return None

    def _parse_track_data(self, track_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse individual track data"""
        try:
            if not isinstance(track_data, dict):
                logger.warning("Track data is not a dictionary")
                return None

            # Validate required fields
            track_index = track_data.get('@index')
            if track_index is not None:
                try:
                    track_index = int(track_index)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid track index: {track_index}")
                    track_index = 0
            else:
                track_index = 0

            track_info = {
                'index': track_index,
                'name': track_data.get('@name', f"Track {track_index}"),
                'type': track_data.get('@type', 'audio'),
                'clips': []
            }

            # Extract clips from track
            if 'clipitem' in track_data:
                clips = track_data['clipitem']
                if not isinstance(clips, list):
                    clips = [clips]

                for clip_data in clips:
                    try:
                        clip_info = self._parse_clip_data(clip_data)
                        if clip_info:
                            track_info['clips'].append(clip_info)
                    except Exception as e:
                        logger.warning(f"Failed to parse clip in track {track_index}: {str(e)}")
                        continue

            return track_info

        except Exception as e:
            logger.exception(f"Error parsing track data: {str(e)}")
            return None

    def _parse_clip_data(self, clip_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse individual clip data"""
        try:
            # Convert timecode to seconds (simplified conversion)
            start_time = self._timecode_to_seconds(clip_data.get('start', '00:00:00:00'))
            end_time = self._timecode_to_seconds(clip_data.get('end', '00:00:00:00'))

            clip_info = {
                'name': clip_data.get('@name', 'Unnamed Clip'),
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time,
                'enabled': clip_data.get('@enabled', 'TRUE').upper() == 'TRUE'
            }

            # Extract media source information
            if 'file' in clip_data:
                file_info = clip_data['file']
                clip_info['media_start'] = self._timecode_to_seconds(
                    file_info.get('in', '00:00:00:00')
                )
                clip_info['media_end'] = self._timecode_to_seconds(
                    file_info.get('out', '00:00:00:00')
                )

            return clip_info

        except Exception as e:
            logger.warning(f"Error parsing clip data: {str(e)}")
            return None

    def _parse_marker_data(self, marker_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse marker data"""
        try:
            marker_info = {
                'time': self._timecode_to_seconds(marker_data.get('@timecode', '00:00:00:00')),
                'name': marker_data.get('@name', 'Marker'),
                'color': marker_data.get('@color', 'Red')
            }
            return marker_info

        except Exception as e:
            logger.warning(f"Error parsing marker data: {str(e)}")
            return None

    def _timecode_to_seconds(self, timecode: str, fps: float = 25.0) -> float:
        """Convert timecode string to seconds"""
        try:
            if isinstance(timecode, (int, float)):
                return float(timecode)

            # Handle different timecode formats
            if ':' in timecode:
                parts = timecode.split(':')
                if len(parts) == 4:  # HH:MM:SS:FF
                    hours, minutes, seconds, frames = map(int, parts)
                    total_seconds = hours * 3600 + minutes * 60 + seconds + frames / fps
                    return total_seconds
                elif len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds

            # If it's just a number, treat as seconds
            return float(timecode)

        except Exception as e:
            logger.warning(f"Error converting timecode '{timecode}' to seconds: {str(e)}")
            return 0.0

    def _create_timeline_from_data(self, timeline_data: Dict[str, Any]) -> Timeline:
        """Create Timeline object from parsed data"""
        timeline = Timeline(
            name=timeline_data['name'],
            frame_rate=timeline_data['frame_rate'],
            sample_rate=timeline_data['sample_rate']
        )

        # Add tracks
        for track_data in timeline_data['tracks']:
            track = Track(
                index=track_data['index'],
                name=track_data['name'],
                track_type=track_data['type']
            )

            # Add clips to track
            for clip_data in track_data['clips']:
                clip = Clip(
                    name=clip_data['name'],
                    start_time=clip_data['start_time'],
                    end_time=clip_data['end_time'],
                    duration=clip_data['duration'],
                    track_index=track_data['index'],
                    media_start=clip_data.get('media_start'),
                    media_end=clip_data.get('media_end'),
                    enabled=clip_data['enabled']
                )
                track.add_clip(clip)

            timeline.add_track(track)

        # Add markers
        for marker_data in timeline_data['markers']:
            timeline.add_marker(
                time=marker_data['time'],
                name=marker_data['name'],
                color=marker_data['color']
            )

        # Calculate total duration
        timeline.calculate_duration()

        return timeline

    def get_timeline_summary(self) -> Dict[str, Any]:
        """Get a summary of the parsed timeline"""
        if not self.timeline:
            return {"error": "No timeline parsed"}

        return self.timeline.get_timeline_stats()