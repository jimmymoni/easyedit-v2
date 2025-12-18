#!/usr/bin/env python3
"""
Repair broken edited XML files by:
1. Extracting canonical file block from original XML
2. Replacing duplicate inline file blocks with references
3. Fixing pathurl to point to real media file
4. Validating the repaired XML structure

Usage:
    python repair_broken_xml.py <original.xml> <broken.xml> <output.xml>

Example:
    python repair_broken_xml.py \
        "C:/Users/Tomso/Downloads/22nd  november/Function Creator.xml" \
        "C:/Users/Tomso/Downloads/edited_timeline_dd27ec03.xml" \
        "C:/Users/Tomso/Downloads/edited_timeline_dd27ec03_REPAIRED.xml"
"""

import sys
import os
from pathlib import Path
from defusedxml import ElementTree as DefusedET
import xml.etree.ElementTree as ET
from xml.dom import minidom
import copy


def extract_canonical_file_block(original_xml_path):
    """Extract the canonical file block from original XML"""
    print(f"[*] Reading original XML: {original_xml_path}")

    try:
        tree = DefusedET.parse(original_xml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"[ERROR] Error parsing original XML: {e}")
        return None

    # Find the first <file> element with pathurl (canonical block)
    for file_elem in root.iter('file'):
        pathurl = file_elem.find('pathurl')
        if pathurl is not None and pathurl.text:
            canonical = {
                'id': file_elem.get('id'),
                'element': file_elem
            }
            print(f"[OK] Found canonical file block:")
            print(f"   - ID: {canonical['id']}")
            print(f"   - Path: {pathurl.text}")
            return canonical

    print("[ERROR] No canonical file block found in original XML")
    return None


def repair_edited_xml(original_xml_path, broken_xml_path, output_path):
    """Repair broken edited XML using canonical block from original"""

    # Extract canonical file block
    canonical = extract_canonical_file_block(original_xml_path)
    if not canonical:
        return False

    # Parse broken XML
    print(f"\n[*] Reading broken XML: {broken_xml_path}")
    try:
        broken_tree = DefusedET.parse(broken_xml_path)
        broken_root = broken_tree.getroot()
    except Exception as e:
        print(f"[ERROR] Error parsing broken XML: {e}")
        return False

    # Find sequence
    sequence = broken_root.find('.//sequence')
    if sequence is None:
        print("[ERROR] No sequence found in broken XML")
        return False

    # Find first video clipitem (where canonical block should go)
    media = sequence.find('.//media')
    if media is None:
        print("[ERROR] No media element found")
        return False

    video = media.find('video')
    if video is None:
        print("[ERROR] No video track found")
        return False

    first_video_clip = video.find('.//track/clipitem')
    if first_video_clip is None:
        print("[ERROR] No video clipitems found")
        return False

    print(f"\n[*] Repairing XML structure...")

    # Replace first clip's file block with canonical
    first_file = first_video_clip.find('file')
    if first_file is not None:
        first_video_clip.remove(first_file)

    # Deep copy canonical file element
    new_canonical = copy.deepcopy(canonical['element'])
    first_video_clip.append(new_canonical)
    print(f"[OK] Inserted canonical file block into first video clip")

    # Replace all other file blocks with references
    video_clips_fixed = 0
    audio_clips_fixed = 0

    # Process all video clipitems
    for track in video.findall('track'):
        for clipitem in track.findall('clipitem'):
            if clipitem == first_video_clip:
                continue  # Skip first clip

            file_elem = clipitem.find('file')
            if file_elem is not None and file_elem.find('pathurl') is not None:
                # This is an inline block - replace with reference
                clipitem.remove(file_elem)
                file_ref = ET.SubElement(clipitem, 'file', id=canonical['id'])
                video_clips_fixed += 1

    # Process all audio clipitems
    audio = media.find('audio')
    if audio is not None:
        for track in audio.findall('track'):
            for clipitem in track.findall('clipitem'):
                file_elem = clipitem.find('file')
                if file_elem is not None and file_elem.find('pathurl') is not None:
                    # This is an inline block - replace with reference
                    clipitem.remove(file_elem)
                    file_ref = ET.SubElement(clipitem, 'file', id=canonical['id'])
                    audio_clips_fixed += 1

    print(f"[OK] Replaced {video_clips_fixed} video clip file blocks with references")
    print(f"[OK] Replaced {audio_clips_fixed} audio clip file blocks with references")

    # Write repaired XML
    print(f"\n[*] Writing repaired XML: {output_path}")

    try:
        xml_str = ET.tostring(broken_root, encoding='unicode')
        reparsed = minidom.parseString(xml_str)

        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        doctype = '<!DOCTYPE xmeml>\n'
        pretty = reparsed.toprettyxml(indent="  ")

        # Remove minidom's XML declaration
        lines = pretty.split('\n')[1:]
        pretty_content = '\n'.join(lines)

        final_xml = xml_declaration + doctype + pretty_content

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_xml)

        print(f"[OK] Repair complete!")

        # Validation
        print(f"\n[*] Validating repaired XML...")
        validate_repaired_xml(output_path)

        return True

    except Exception as e:
        print(f"[ERROR] Error writing repaired XML: {e}")
        return False


def validate_repaired_xml(xml_path):
    """Validate the repaired XML structure"""
    try:
        tree = DefusedET.parse(xml_path)
        root = tree.getroot()

        # Count file blocks with pathurl (should be 1)
        file_blocks_with_path = [
            f for f in root.iter('file')
            if f.find('pathurl') is not None
        ]

        # Count all file references
        all_file_refs = list(root.iter('file'))

        print(f"   - Total <file> elements: {len(all_file_refs)}")
        print(f"   - Canonical blocks (with pathurl): {len(file_blocks_with_path)}")
        print(f"   - Reference-only blocks: {len(all_file_refs) - len(file_blocks_with_path)}")

        if len(file_blocks_with_path) == 1:
            pathurl = file_blocks_with_path[0].find('pathurl').text
            print(f"   - Canonical pathurl: {pathurl}")

            # Check if pathurl is valid
            if pathurl.startswith('file://localhost/') and ('/' in pathurl or '\\' in pathurl):
                print(f"[OK] XML structure is valid!")
            else:
                print(f"[WARNING] pathurl may not point to real file")
        else:
            print(f"[WARNING] Expected 1 canonical block, found {len(file_blocks_with_path)}")

    except Exception as e:
        print(f"[ERROR] Validation error: {e}")


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        print("\n[ERROR] Incorrect number of arguments")
        print("Usage: python repair_broken_xml.py <original.xml> <broken.xml> <output.xml>")
        sys.exit(1)

    original_xml = sys.argv[1]
    broken_xml = sys.argv[2]
    output_xml = sys.argv[3]

    # Validate input files exist
    if not os.path.exists(original_xml):
        print(f"[ERROR] Original XML not found: {original_xml}")
        sys.exit(1)

    if not os.path.exists(broken_xml):
        print(f"[ERROR] Broken XML not found: {broken_xml}")
        sys.exit(1)

    print("=" * 70)
    print("XML REPAIR TOOL - DaVinci Resolve Timeline Fixer")
    print("=" * 70)

    success = repair_edited_xml(original_xml, broken_xml, output_xml)

    print("=" * 70)
    if success:
        print("[SUCCESS] Repaired XML ready for DaVinci Resolve import")
        print(f"Output: {output_xml}")
    else:
        print("[FAILED] Could not repair XML")
    print("=" * 70)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
