#!/usr/bin/env python3
"""
Quick validation test to confirm XML structure fix is applied
"""
import sys
import os
import xml.etree.ElementTree as ET

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from models.timeline import Timeline, Track, Clip
from parsers.xml_writer import FCP7XMLWriter

def test_xml_structure_fix():
    """Quick test to verify XML structure is correct"""
    print("\n" + "="*70)
    print("QUICK VALIDATION TEST - XML Structure Fix")
    print("="*70 + "\n")

    # Create a simple timeline
    print("[1] Creating test timeline...")
    timeline = Timeline(
        name="Quick Test Timeline",
        duration=30.0,
        frame_rate=30.0,
        sample_rate=48000
    )

    # Add a video track with 2 clips
    video_track = Track(index=0, name="Video 1", track_type="video")

    clip1 = Clip(
        name="Test Clip 1",
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        track_index=0
    )
    clip2 = Clip(
        name="Test Clip 2",
        start_time=10.0,
        end_time=20.0,
        duration=10.0,
        track_index=0
    )

    video_track.add_clip(clip1)
    video_track.add_clip(clip2)
    timeline.add_track(video_track)

    # Add canonical file block
    timeline.canonical_file_block = {
        'file_id': 'test-file-1',
        'name': 'Test_Video.mp4',
        'pathurl': 'file://localhost/C:/test/Test_Video.mp4',
        'duration_frames': 900,
        'samplecharacteristics': {
            'width': 1920,
            'height': 1080
        }
    }

    print("   [OK] Timeline created with 1 track, 2 clips\n")

    # Generate XML
    print("[2] Generating FCP7 XML...")
    writer = FCP7XMLWriter()
    xml_content = writer.generate_fcp7_xml(timeline)
    print("   [OK] XML generated successfully\n")

    # Parse and validate structure
    print("[3] Validating XML structure...\n")
    root = ET.fromstring(xml_content)

    # Validation checks
    checks = []

    # Check 1: Root is xmeml
    if root.tag == 'xmeml' and root.get('version') == '5':
        checks.append((True, "Root element: <xmeml version='5'>"))
    else:
        checks.append((False, f"Root element incorrect: {root.tag}"))

    # Check 2: NO project wrapper (THIS IS THE FIX)
    project_tags = root.findall('.//project')
    if len(project_tags) == 0:
        checks.append((True, "NO <project> wrapper (FIX APPLIED [OK])"))
    else:
        checks.append((False, f"FOUND {len(project_tags)} <project> tags (FIX NOT APPLIED [X])"))

    # Check 3: NO children wrapper (THIS IS THE FIX)
    children_tags = root.findall('.//children')
    if len(children_tags) == 0:
        checks.append((True, "NO <children> wrapper (FIX APPLIED [OK])"))
    else:
        checks.append((False, f"FOUND {len(children_tags)} <children> tags (FIX NOT APPLIED [X])"))

    # Check 4: Direct sequence child
    sequences = root.findall('./sequence')
    if len(sequences) == 1:
        checks.append((True, "Sequence is DIRECT child of <xmeml> (CORRECT [OK])"))
    else:
        checks.append((False, f"Sequence not direct child (found {len(sequences)})"))

    # Check 5: Canonical file block pattern
    clipitems = root.findall('.//video/track/clipitem')
    if len(clipitems) == 2:
        first_clip_file = clipitems[0].find('./file')
        second_clip_file = clipitems[1].find('./file')

        first_has_children = len(list(first_clip_file)) > 0
        second_has_children = len(list(second_clip_file)) > 0

        if first_has_children and not second_has_children:
            checks.append((True, "File block pattern: First=FULL, Second=REFERENCE (CORRECT [OK])"))
        else:
            checks.append((False, f"File block pattern incorrect"))
    else:
        checks.append((False, f"Expected 2 clipitems, found {len(clipitems)}"))

    # Print results
    all_passed = True
    for passed, description in checks:
        status = "[OK]" if passed else "[FAIL]"
        print(f"   {status} {description}")
        if not passed:
            all_passed = False

    # Show structure preview
    print("\n[4] XML Structure Preview (first 15 lines):\n")
    lines = xml_content.split('\n')[:15]
    for i, line in enumerate(lines, 1):
        print(f"   {i:2d} | {line}")

    # Final result
    print("\n" + "="*70)
    if all_passed:
        print("[SUCCESS] All validations PASSED!")
        print("[SUCCESS] XML structure fix has been APPLIED correctly")
        print("[SUCCESS] Generated XMLs will import to DaVinci Resolve as ONLINE clips")
    else:
        print("[FAILURE] Some validations FAILED")
        print("[FAILURE] XML structure fix may not be applied correctly")
    print("="*70 + "\n")

    return all_passed

if __name__ == "__main__":
    try:
        success = test_xml_structure_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
