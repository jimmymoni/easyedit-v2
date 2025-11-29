"""
Canonical File Block Extractor
Extracts the canonical file metadata and filters from original FCP7 XML
"""

import defusedxml.ElementTree as ET
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def extract_canonical_file_block(original_xml_path: str) -> Dict[str, Any]:
    """
    Extract canonical file block from original FCP7 XML.

    This function extracts the EXACT file metadata and filters from the original
    XML without any modification or interpretation. The extracted data is used
    to preserve file fingerprints when generating edited timelines.

    Args:
        original_xml_path: Path to the original FCP7 XML file

    Returns:
        Dictionary containing exact file metadata and filters:
        {
            "file_id": str,
            "name": str,
            "pathurl": str,
            "duration_frames": int,
            "timecode": {"string": str, "frame": int, "displayformat": str},
            "reel_name": str or None,
            "samplecharacteristics": {"width": int, "height": int, ...},
            "audio": {"channelcount": int, "depth": int, "samplerate": int},
            "filters": {"basic_motion": str, "crop": str, "opacity": str}
        }
    """
    try:
        # Parse XML with defusedxml for security
        tree = ET.parse(original_xml_path)
        root = tree.getroot()

        # Navigate to the first clipitem in video track
        # Path: xmeml/sequence/media/video/track/clipitem
        clipitem = None
        file_elem = None

        # Find sequence
        sequence = root.find('.//sequence')
        if sequence is None:
            raise ValueError("No sequence found in XML")

        # Find media
        media = sequence.find('media')
        if media is None:
            raise ValueError("No media found in sequence")

        # Find video track
        video = media.find('video')
        if video is None:
            raise ValueError("No video track found")

        # Find first track
        track = video.find('track')
        if track is None:
            raise ValueError("No track found in video")

        # Find first clipitem
        clipitem = track.find('clipitem')
        if clipitem is None:
            raise ValueError("No clipitem found in track")

        # Find file element in clipitem
        file_elem = clipitem.find('file')
        if file_elem is None:
            raise ValueError("No file element found in clipitem")

        # Extract file metadata (EXACT values, no modifications)
        # CRITICAL: Do NOT extract filters - DaVinci Resolve compatibility requires clean clips
        canonical_block = {
            "file_id": file_elem.get('id'),
            "name": _get_text(file_elem, 'name'),
            "pathurl": _get_text(file_elem, 'pathurl'),
            "duration_frames": _get_int(file_elem, 'duration'),
            "timecode": _extract_timecode(file_elem),
            "reel_name": _get_text(file_elem.find('reel'), 'name') if file_elem.find('reel') is not None else None,
            "samplecharacteristics": _extract_samplecharacteristics(file_elem),
            "audio": _extract_audio_characteristics(file_elem)
            # "filters": _extract_filters(clipitem)  # REMOVED - breaks DaVinci Resolve import
        }

        logger.info(f"Extracted canonical file block: file_id={canonical_block['file_id']}, "
                   f"name={canonical_block['name']}")
        return canonical_block

    except Exception as e:
        logger.error(f"Failed to extract canonical file block from {original_xml_path}: {str(e)}")
        raise


def _get_text(element, tag: str) -> Optional[str]:
    """Get text content of a child element without modification"""
    if element is None:
        return None
    child = element.find(tag)
    return child.text if child is not None and child.text else None


def _get_int(element, tag: str) -> Optional[int]:
    """Get integer value of a child element"""
    text = _get_text(element, tag)
    try:
        return int(text) if text is not None else None
    except (ValueError, TypeError):
        return None


def _extract_timecode(file_elem) -> Dict[str, Any]:
    """Extract timecode information exactly as it appears"""
    timecode_elem = file_elem.find('timecode')
    if timecode_elem is None:
        return {"string": None, "frame": None, "displayformat": None}

    return {
        "string": _get_text(timecode_elem, 'string'),
        "frame": _get_int(timecode_elem, 'frame'),
        "displayformat": _get_text(timecode_elem, 'displayformat')
    }


def _extract_samplecharacteristics(file_elem) -> Dict[str, Any]:
    """Extract video sample characteristics exactly as they appear"""
    media_elem = file_elem.find('media')
    if media_elem is None:
        return {"width": None, "height": None, "pixelaspectratio": None, "fielddominance": None}

    video_elem = media_elem.find('video')
    if video_elem is None:
        return {"width": None, "height": None, "pixelaspectratio": None, "fielddominance": None}

    sample_chars = video_elem.find('samplecharacteristics')
    if sample_chars is None:
        return {"width": None, "height": None, "pixelaspectratio": None, "fielddominance": None}

    return {
        "width": _get_int(sample_chars, 'width'),
        "height": _get_int(sample_chars, 'height'),
        "pixelaspectratio": _get_text(sample_chars, 'pixelaspectratio'),
        "fielddominance": _get_text(sample_chars, 'fielddominance')
    }


def _extract_audio_characteristics(file_elem) -> Dict[str, Any]:
    """Extract audio characteristics exactly as they appear"""
    media_elem = file_elem.find('media')
    if media_elem is None:
        return {"channelcount": None, "depth": None, "samplerate": None}

    audio_elem = media_elem.find('audio')
    if audio_elem is None:
        return {"channelcount": None, "depth": None, "samplerate": None}

    return {
        "channelcount": _get_int(audio_elem, 'channelcount'),
        "depth": _get_int(audio_elem, 'depth'),
        "samplerate": _get_int(audio_elem, 'samplerate')
    }


def _extract_filters(clipitem_elem) -> Dict[str, str]:
    """
    Extract filter blocks as raw XML strings.

    Preserves the exact filter structure including all parameters,
    effectids, and values. These filters represent the canonical
    Resolve effects that must be preserved.
    """
    filters = {}

    # Find all filter elements
    filter_elements = clipitem_elem.findall('filter')

    for filter_elem in filter_elements:
        # Find the effect name
        effect = filter_elem.find('effect')
        if effect is None:
            continue

        effect_name = _get_text(effect, 'name')
        if effect_name is None:
            continue

        # Convert filter element to XML string
        # This preserves the entire filter structure including all nested elements
        filter_str = ET.tostring(filter_elem, encoding='unicode', method='xml')

        # Map to filter keys based on effect name
        if effect_name == 'Basic Motion':
            filters['basic_motion'] = filter_str
        elif effect_name == 'Crop':
            filters['crop'] = filter_str
        elif effect_name == 'Opacity':
            filters['opacity'] = filter_str
        elif effect_name == 'Audio Levels':
            filters['audio_levels'] = filter_str
        elif effect_name == 'Audio Pan':
            filters['audio_pan'] = filter_str

    return filters
