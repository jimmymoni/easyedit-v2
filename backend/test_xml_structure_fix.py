"""
Test script to validate XML structure fixes for DaVinci Resolve compatibility.

This script validates that generated XML follows the correct canonical file block pattern:
1. Canonical <file> block in <media> section (not in clipitem)
2. All clipitems reference file by ID only
3. Audio tracks exist with matching clipitems
4. Correct structure matches reel_90s.xml pattern
"""

import sys
import os
import defusedxml.ElementTree as ET

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers.xml_parser import FCP7XMLParser
from parsers.xml_writer import FCP7XMLWriter


def validate_xml_structure(xml_path: str) -> dict:
    """
    Validate XML structure against DaVinci Resolve requirements.

    Returns dict with validation results and any errors found.
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'stats': {}
    }

    try:
        root = ET.parse(xml_path).getroot()

        # Find media element
        media = root.find('.//media')
        if media is None:
            results['valid'] = False
            results['errors'].append("CRITICAL: No <media> element found")
            return results

        # Rule 1: Canonical file block must be direct child of <media>
        canonical_file = media.find('./file')
        if canonical_file is None:
            results['valid'] = False
            results['errors'].append("CRITICAL: No canonical <file> block in <media> section")
        else:
            file_id = canonical_file.get('id')
            results['stats']['canonical_file_id'] = file_id
            print(f"[OK] Rule 1 PASSED: Canonical file block found in <media>: {file_id}")

        # Rule 2: No file definitions inside clipitems (only references)
        clipitems = root.findall('.//clipitem')
        results['stats']['total_clipitems'] = len(clipitems)

        for idx, clipitem in enumerate(clipitems):
            file_elem = clipitem.find('./file')
            if file_elem is None:
                results['valid'] = False
                results['errors'].append(f"Clipitem {idx+1} ({clipitem.get('id')}) has NO <file> reference")
            elif len(file_elem) > 0:
                # Has children = full file block definition (WRONG)
                results['valid'] = False
                results['errors'].append(
                    f"CRITICAL: Clipitem {idx+1} ({clipitem.get('id')}) contains FULL file block "
                    f"(should be reference only)"
                )

        if results['valid']:
            print(f"[OK] Rule 2 PASSED: All {len(clipitems)} clipitems have file references (no embedded definitions)")

        # Rule 3: All clips reference same file ID
        file_ids = []
        for clipitem in clipitems:
            file_elem = clipitem.find('./file')
            if file_elem is not None:
                file_ids.append(file_elem.get('id'))

        unique_file_ids = set(file_ids)
        if len(unique_file_ids) > 1:
            results['warnings'].append(
                f"Multiple file IDs referenced: {unique_file_ids} (may be intentional for multi-source timelines)"
            )
        elif len(unique_file_ids) == 1:
            results['stats']['referenced_file_id'] = list(unique_file_ids)[0]
            print(f"[OK] Rule 3 PASSED: All clips reference same file: {list(unique_file_ids)[0]}")

        # Rule 4: Audio tracks must exist
        audio_track = root.find('.//audio/track')
        if audio_track is None:
            results['valid'] = False
            results['errors'].append("CRITICAL: No <audio> track found (must have matching audio clipitems)")
        else:
            audio_clips = audio_track.findall('.//clipitem')
            video_clips = root.findall('.//video/track/clipitem')
            results['stats']['audio_clips'] = len(audio_clips)
            results['stats']['video_clips'] = len(video_clips)

            if len(audio_clips) == 0:
                results['valid'] = False
                results['errors'].append("CRITICAL: Audio track exists but has NO clipitems")
            else:
                print(f"[OK] Rule 4 PASSED: Audio track found with {len(audio_clips)} clipitems")

            if len(audio_clips) != len(video_clips):
                results['warnings'].append(
                    f"Audio clips ({len(audio_clips)}) != Video clips ({len(video_clips)})"
                )

        # Rule 5: Check in/out values are not all zero
        zero_in_out_count = 0
        for clipitem in clipitems:
            in_elem = clipitem.find('./in')
            out_elem = clipitem.find('./out')
            if in_elem is not None and out_elem is not None:
                if in_elem.text == '0' and out_elem.text == '0':
                    zero_in_out_count += 1

        if zero_in_out_count > 0:
            results['warnings'].append(
                f"{zero_in_out_count}/{len(clipitems)} clips have <in>0</in><out>0</out> "
                f"(may cause DaVinci Resolve to show zero duration)"
            )
        else:
            print(f"[OK] Rule 5 PASSED: No clips with zero in/out values")

        # Rule 6: Sequence duration should match last clip end time
        sequence_duration_elem = root.find('.//sequence/duration')
        if sequence_duration_elem is not None:
            sequence_duration = int(sequence_duration_elem.text)
            results['stats']['sequence_duration'] = sequence_duration

            # Find max clip end time
            max_end = 0
            for clipitem in root.findall('.//video/track/clipitem'):
                end_elem = clipitem.find('./end')
                if end_elem is not None:
                    end_time = int(end_elem.text)
                    max_end = max(max_end, end_time)

            if sequence_duration != max_end:
                results['valid'] = False
                results['errors'].append(
                    f"CRITICAL: Sequence duration ({sequence_duration}) != last clip end time ({max_end})"
                )
            else:
                print(f"[OK] Rule 6 PASSED: Sequence duration matches timeline ({sequence_duration} frames)")

        # Rule 7: Verify cumulative positioning (sequential start/end)
        video_clipitems = root.findall('.//video/track/clipitem')
        for idx, clipitem in enumerate(video_clipitems):
            start_elem = clipitem.find('./start')
            end_elem = clipitem.find('./end')
            duration_elem = clipitem.find('./duration')

            if start_elem is not None and end_elem is not None and duration_elem is not None:
                start = int(start_elem.text)
                end = int(end_elem.text)
                duration = int(duration_elem.text)

                # Check duration matches end - start
                if duration != (end - start):
                    results['valid'] = False
                    results['errors'].append(
                        f"CRITICAL: Clip {idx+1}: duration ({duration}) != end-start ({end - start})"
                    )

                # Check sequential (start of next = end of previous)
                if idx > 0:
                    prev_end_elem = video_clipitems[idx-1].find('./end')
                    if prev_end_elem is not None:
                        prev_end = int(prev_end_elem.text)
                        if start != prev_end:
                            results['valid'] = False
                            results['errors'].append(
                                f"CRITICAL: Clip {idx+1}: start ({start}) != previous end ({prev_end}) - gap or overlap detected"
                            )

        if results['valid'] and len(video_clipitems) > 0:
            print(f"[OK] Rule 7 PASSED: Clips have sequential cumulative positioning (no gaps/overlaps)")

    except Exception as e:
        results['valid'] = False
        results['errors'].append(f"Exception during validation: {str(e)}")

    return results


def compare_structure_to_gold_standard(generated_xml_path: str, gold_xml_path: str):
    """Compare generated XML structure to gold standard (reel_90s.xml)"""
    print(f"\n{'='*80}")
    print("COMPARING TO GOLD STANDARD (reel_90s.xml)")
    print(f"{'='*80}\n")

    try:
        gen_root = ET.parse(generated_xml_path).getroot()
        gold_root = ET.parse(gold_xml_path).getroot()

        # Compare canonical file block location
        gen_media = gen_root.find('.//media')
        gold_media = gold_root.find('.//media')

        gen_file_in_media = gen_media.find('./file') if gen_media is not None else None
        gold_file_in_media = gold_media.find('./file') if gold_media is not None else None

        if gen_file_in_media is not None and gold_file_in_media is not None:
            print("[OK] MATCH: Both have canonical file block in <media>")
        elif gen_file_in_media is None:
            print("[FAIL] MISMATCH: Generated XML missing canonical file block in <media>")

        # Compare clip reference pattern
        gen_first_clip = gen_root.find('.//clipitem')
        gold_first_clip = gold_root.find('.//clipitem')

        if gen_first_clip is not None and gold_first_clip is not None:
            gen_file = gen_first_clip.find('./file')
            gold_file = gold_first_clip.find('./file')

            gen_has_children = len(gen_file) > 0 if gen_file is not None else False
            gold_has_children = len(gold_file) > 0 if gold_file is not None else False

            if not gen_has_children and not gold_has_children:
                print("[OK] MATCH: Both use file reference (not embedded)")
            elif gen_has_children:
                print("[FAIL] MISMATCH: Generated XML has embedded file block in clipitem")

        # Compare audio track presence
        gen_audio = gen_root.find('.//audio/track')
        gold_audio = gold_root.find('.//audio/track')

        if gen_audio is not None and gold_audio is not None:
            print("[OK] MATCH: Both have audio tracks")
        elif gen_audio is None:
            print("[FAIL] MISMATCH: Generated XML missing audio track")

        print()

    except Exception as e:
        print(f"[FAIL] Error comparing structures: {e}")


def test_parse_and_regenerate(input_xml_path: str, output_xml_path: str):
    """
    Parse XML with xml_parser and regenerate with xml_writer.
    This tests the complete round-trip.
    """
    print(f"\n{'='*80}")
    print("TESTING PARSE -> REGENERATE WORKFLOW")
    print(f"{'='*80}\n")

    try:
        # Parse input XML
        parser = FCP7XMLParser()
        timeline = parser.parse_file(input_xml_path)
        print(f"[OK] Parsed input XML: {timeline.name}")
        print(f"   Duration: {timeline.duration}s")
        print(f"   Frame rate: {timeline.frame_rate}")
        print(f"   Tracks: {len(timeline.tracks)}")

        # Check canonical file block
        if timeline.canonical_file_block:
            print(f"[OK] Canonical file block attached to timeline: {timeline.canonical_file_block['file_id']}")
        else:
            print("[WARN]  No canonical file block attached (will use fallback)")

        # Regenerate XML
        writer = FCP7XMLWriter()
        success = writer.write_timeline(timeline, output_xml_path)

        if success:
            print(f"[OK] Generated output XML: {output_xml_path}")
        else:
            print(f"[FAIL] Failed to generate XML")
            return False

        return True

    except Exception as e:
        print(f"[FAIL] Error during parse/regenerate: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*80)
    print("XML STRUCTURE VALIDATION TEST")
    print("="*80 + "\n")

    # Test 1: Validate gold standard (reel_90s.xml)
    gold_standard_path = r"C:\Users\Tomso\Downloads\reel_90s.xml"

    if os.path.exists(gold_standard_path):
        print("TEST 1: Validating gold standard (reel_90s.xml)")
        print("-" * 80)
        results = validate_xml_structure(gold_standard_path)

        if results['valid']:
            print(f"\n[OK] GOLD STANDARD IS VALID")
        else:
            print(f"\n[FAIL] GOLD STANDARD HAS ERRORS:")
            for error in results['errors']:
                print(f"   - {error}")

        for warning in results['warnings']:
            print(f"[WARN]  {warning}")

        print(f"\nStats: {results['stats']}")
    else:
        print(f"[WARN]  Gold standard not found: {gold_standard_path}")

    # Test 2: Parse gold standard and regenerate
    print(f"\n{'='*80}")
    print("TEST 2: Parse reel_90s.xml and regenerate")
    print("-" * 80)

    output_path = r"C:\Users\Tomso\Documents\easyedit-v2\backend\test_output_regenerated.xml"

    if os.path.exists(gold_standard_path):
        success = test_parse_and_regenerate(gold_standard_path, output_path)

        if success and os.path.exists(output_path):
            # Validate regenerated XML
            print(f"\nValidating regenerated XML...")
            print("-" * 80)
            results = validate_xml_structure(output_path)

            if results['valid']:
                print(f"\n[OK] REGENERATED XML IS VALID")
            else:
                print(f"\n[FAIL] REGENERATED XML HAS ERRORS:")
                for error in results['errors']:
                    print(f"   - {error}")

            for warning in results['warnings']:
                print(f"[WARN]  {warning}")

            # Compare structures
            compare_structure_to_gold_standard(output_path, gold_standard_path)

    # Test 3: Validate broken XML (godmode_timeline_caccf000.xml)
    broken_xml_path = r"C:\Users\Tomso\Downloads\godmode_timeline_caccf000.xml"

    if os.path.exists(broken_xml_path):
        print(f"\n{'='*80}")
        print("TEST 3: Validating broken XML (godmode_timeline_caccf000.xml)")
        print("-" * 80)
        results = validate_xml_structure(broken_xml_path)

        if results['valid']:
            print(f"\n[OK] BROKEN XML IS ACTUALLY VALID (unexpected!)")
        else:
            print(f"\n[FAIL] BROKEN XML HAS ERRORS (expected):")
            for error in results['errors']:
                print(f"   - {error}")

        for warning in results['warnings']:
            print(f"[WARN]  {warning}")

        print(f"\nStats: {results['stats']}")

    print(f"\n{'='*80}")
    print("VALIDATION COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
