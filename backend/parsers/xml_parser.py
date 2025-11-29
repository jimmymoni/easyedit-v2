import defusedxml.ElementTree as ET
import json
import zipfile
import os
import re
import tempfile
from typing import Dict, Any, Optional
from models.timeline import Timeline, Track, Clip
from parsers.canonical_extractor import extract_canonical_file_block
import logging

from utils.error_handlers import ValidationError, ProcessingError

logger = logging.getLogger(__name__)

class FCP7XMLParser:
    """Parser for Final Cut Pro 7 XML (.xml) timeline files"""

    def __init__(self):
        self.timeline = None

    def parse_file(self, file_path: str) -> Timeline:
        """Parse an FCP7 XML file and return a Timeline object with automatic encoding detection and ZIP support"""
        try:
            if not file_path or not isinstance(file_path, str):
                raise ValidationError("Invalid file path provided")

            # EXTRACT CANONICAL FILE BLOCK FIRST (before parsing content)
            canonical_block = None
            try:
                # For ZIP files, extract XML to temp file first
                if self._is_zip_file(file_path):
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        if 'project.xml' in zip_ref.namelist():
                            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.xml') as temp_file:
                                temp_path = temp_file.name
                                with zip_ref.open('project.xml') as source:
                                    temp_file.write(source.read().decode('utf-8'))

                            canonical_block = extract_canonical_file_block(temp_path)
                            os.remove(temp_path)  # Cleanup
                else:
                    canonical_block = extract_canonical_file_block(file_path)

                if canonical_block:
                    logger.info(f"Extracted canonical file block: ID={canonical_block['file_id']}, name={canonical_block['name']}")
            except Exception as e:
                logger.warning(f"Failed to extract canonical file block: {e}")
                canonical_block = None

            # Check if file is a ZIP archive (some NLEs export both XML and ZIP formats)
            if self._is_zip_file(file_path):
                logger.info("Detected ZIP-format timeline file, extracting project.xml")
                content = self._extract_xml_from_zip(file_path)
            else:
                # Read file with automatic encoding detection
                content = self._read_file_with_encoding_detection(file_path)

            if not content.strip():
                raise ValidationError("Timeline XML file is empty")

            timeline = self.parse_content(content)

            # Attach canonical block to timeline
            if canonical_block and timeline:
                timeline.set_canonical_file_block(canonical_block)
                logger.info(f"Attached canonical file block to timeline")

            return timeline

        except FileNotFoundError:
            logger.error(f"Timeline XML file not found: {file_path}")
            raise ValidationError(f"Timeline XML file not found: {file_path}")
        except PermissionError:
            logger.error(f"Permission denied reading timeline XML file: {file_path}")
            raise ValidationError(f"Permission denied reading timeline XML file: {file_path}")
        except (ValidationError, ProcessingError):
            # Re-raise our custom errors
            raise
        except Exception as e:
            logger.exception(f"Unexpected error parsing timeline XML file {file_path}")
            raise ProcessingError(f"Failed to parse timeline XML file: {str(e)}")

    def _read_file_with_encoding_detection(self, file_path: str) -> str:
        """Read file with automatic encoding detection, trying multiple encodings"""
        # List of encodings to try, in order of preference
        encodings_to_try = ['utf-8', 'windows-1252', 'iso-8859-1', 'utf-16', 'cp1252', 'latin1']

        last_error = None

        for encoding in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    content = file.read()
                    logger.info(f"Successfully read XML file with {encoding} encoding")
                    return content
            except UnicodeDecodeError as e:
                last_error = e
                logger.debug(f"Failed to read with {encoding} encoding: {str(e)}")
                continue
            except Exception as e:
                # Don't try other encodings for non-encoding errors
                raise

        # If all encodings failed, try reading with error handling (replace invalid chars)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                content = file.read()
                logger.warning(f"Read XML file with UTF-8 and character replacement (some characters may be corrupted)")
                return content
        except Exception as e:
            logger.error(f"Failed to read XML file with all encoding attempts: {str(e)}")
            raise ValidationError(f"Timeline XML file contains invalid encoding. Tried: {', '.join(encodings_to_try)}. Last error: {str(last_error)}")

    def _is_zip_file(self, file_path: str) -> bool:
        """Check if file is a ZIP archive by reading magic bytes"""
        try:
            with open(file_path, 'rb') as f:
                magic_bytes = f.read(4)
                # ZIP files start with PK\x03\x04 or PK\x05\x06 (empty archive)
                return magic_bytes.startswith(b'PK\x03\x04') or magic_bytes.startswith(b'PK\x05\x06')
        except Exception as e:
            logger.warning(f"Could not check if file is ZIP: {str(e)}")
            return False

    def _extract_xml_from_zip(self, zip_path: str) -> str:
        """Extract project.xml from timeline ZIP archive with security checks"""
        try:
            if not zipfile.is_zipfile(zip_path):
                raise ValidationError("File appears to be ZIP but is not a valid ZIP archive")

            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # Security: Check for zip bombs (excessive compression)
                total_uncompressed = sum(info.file_size for info in zip_file.infolist())
                if total_uncompressed > 100 * 1024 * 1024:  # 100MB limit
                    raise ValidationError("ZIP archive too large (potential zip bomb)")

                # Look for project.xml in the archive
                xml_files = [name for name in zip_file.namelist() if name.endswith('.xml')]

                if not xml_files:
                    raise ValidationError("No XML files found in timeline ZIP archive")

                # Prefer 'project.xml', otherwise use first XML file
                xml_filename = 'project.xml' if 'project.xml' in xml_files else xml_files[0]

                # Security: Validate filename doesn't contain path traversal
                if '..' in xml_filename or xml_filename.startswith('/'):
                    raise ValidationError("Invalid filename in ZIP archive")

                logger.info(f"Extracting {xml_filename} from timeline ZIP archive")

                # Read XML content
                with zip_file.open(xml_filename) as xml_file:
                    xml_bytes = xml_file.read()

                    # Try to decode with common encodings
                    for encoding in ['utf-8', 'windows-1252', 'iso-8859-1']:
                        try:
                            xml_content = xml_bytes.decode(encoding)
                            logger.info(f"Successfully decoded extracted XML with {encoding}")
                            return xml_content
                        except UnicodeDecodeError:
                            continue

                    # Fallback: decode with error replacement
                    xml_content = xml_bytes.decode('utf-8', errors='replace')
                    logger.warning("Decoded extracted XML with character replacement")
                    return xml_content

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file: {str(e)}")
            raise ValidationError(f"Invalid ZIP archive: {str(e)}")
        except ValidationError:
            # Re-raise our validation errors
            raise
        except Exception as e:
            logger.exception(f"Error extracting XML from ZIP: {str(e)}")
            raise ProcessingError(f"Failed to extract XML from ZIP archive: {str(e)}")

    def parse_content(self, xml_content: str) -> Timeline:
        """Parse FCP7 XML content and return a Timeline object"""
        try:
            if not xml_content or not isinstance(xml_content, str):
                raise ValidationError("Invalid XML content provided")

            # Remove BOM (Byte Order Mark) if present
            if xml_content.startswith('\ufeff'):
                xml_content = xml_content[1:]
                logger.debug("Removed BOM from XML content")

            # Strip whitespace
            xml_content = xml_content.strip()
            if not xml_content:
                raise ValidationError("XML content is empty")

            # Basic XML validation - check for XML start
            if not xml_content.startswith('<'):
                # Log first 100 characters to help debug
                preview = xml_content[:100].replace('\n', '\\n').replace('\r', '\\r')
                logger.error(f"Content does not start with '<'. First 100 chars: {preview}")
                raise ValidationError(f"Content does not appear to be valid XML. Content starts with: {xml_content[:50]}")

            # Sanitize XML: Fix invalid double colons in tag names (DaVinci Resolve export quirk)
            # Replace patterns like <ListMgt::LmPowerNodeList> with <ListMgt_LmPowerNodeList>
            # Also handle closing tags like </ListMgt::LmPowerNodeList>
            original_content = xml_content
            xml_content = re.sub(r'<(/?)(\w+)::(\w+)', r'<\1\2_\3', xml_content)
            if xml_content != original_content:
                logger.info("Sanitized XML: replaced :: with _ in tag names (DaVinci Resolve compatibility fix)")

            # Secure XML parsing with defusedxml (automatic XXE protection)
            root = ET.fromstring(xml_content)

            # Validate FCP7 XML format
            if root.tag != 'xmeml':
                raise ValidationError(
                    f"Invalid timeline XML format. Expected <xmeml> root element, got <{root.tag}>. "
                    "Please export your timeline as Final Cut Pro 7 XML format."
                )

            version = root.get('version')
            if version != '5':
                logger.warning(f"Timeline XML version is '{version}', expected '5' (FCP7). Attempting to parse anyway.")

            data = self._xml_to_dict(root)

            # Extract timeline information
            timeline_data = self._extract_timeline_data(data)
            if not timeline_data:
                raise ProcessingError("No valid timeline data found in XML file")

            timeline = self._create_timeline_from_data(timeline_data)
            if not timeline:
                raise ProcessingError("Failed to create timeline from XML data")

            self.timeline = timeline
            return timeline

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {str(e)}")
            raise ValidationError(f"Invalid XML format: {str(e)}")
        except (ValidationError, ProcessingError):
            # Re-raise our custom errors
            raise
        except Exception as e:
            logger.exception(f"Unexpected error parsing timeline XML content")
            raise ProcessingError(f"Failed to parse timeline XML content: {str(e)}")

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

                    # Extract in/out points (source media references) if available
                    if 'in' in clipitem:
                        clip_info['media_start'] = float(clipitem['in']) / fps  # Fixed: was 'media_in'
                    if 'out' in clipitem:
                        clip_info['media_end'] = float(clipitem['out']) / fps  # Fixed: was 'media_out'

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

            # Extract media source information from <in> and <out> tags (direct children of <clipitem>)
            # These define where in the source media this clip starts/ends
            if 'in' in clip_data:
                clip_info['media_start'] = self._timecode_to_seconds(clip_data['in'])

            if 'out' in clip_data:
                clip_info['media_end'] = self._timecode_to_seconds(clip_data['out'])

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
