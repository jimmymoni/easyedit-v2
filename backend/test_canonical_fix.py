"""
Test script to verify canonical file block preservation
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from parsers.xml_parser import FCP7XMLParser
from parsers.xml_writer import FCP7XMLWriter
import xml.etree.ElementTree as ET

def validate_davinci_structure(xml_path: str):
    """Validate XML matches DaVinci Resolve structure"""
    print(f"\n4. Validating DaVinci Resolve structure...")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    checks = []

    # Check 1: xmeml root
    if root.tag == 'xmeml' and root.get('version') == '5':
        checks.append((True, "xmeml root with version='5'"))
    else:
        checks.append((False, f"xmeml root - got {root.tag}"))

    # Check 2: No project wrapper
    project_tags = root.findall('.//project')
    if len(project_tags) == 0:
        checks.append((True, "No <project> wrapper"))
    else:
        checks.append((False, f"Found {len(project_tags)} <project> tags - should be 0"))

    # Check 3: No children wrapper
    children_tags = root.findall('.//children')
    if len(children_tags) == 0:
        checks.append((True, "No <children> wrapper"))
    else:
        checks.append((False, f"Found {len(children_tags)} <children> tags - should be 0"))

    # Check 4: Direct sequence child
    sequences = root.findall('./sequence')
    if len(sequences) == 1:
        checks.append((True, "Exactly 1 <sequence> as direct child of <xmeml>"))
    else:
        checks.append((False, f"Found {len(sequences)} direct <sequence> children - should be 1"))

    # Print results
    all_passed = True
    for passed, description in checks:
        if passed:
            print(f"   [OK] {description}")
        else:
            print(f"   [FAIL] {description}")
            all_passed = False

    return all_passed

def test_canonical_preservation():
    """Test that canonical file block is preserved through parse/write cycle"""

    # Input file
    input_xml = r"C:\Users\Tomso\Downloads\22nd  november\Function Creator.xml"
    output_xml = r"C:\Users\Tomso\Documents\easyedit-v2\backend\test_output_canonical.xml"

    print("=" * 80)
    print("CANONICAL FILE BLOCK PRESERVATION TEST")
    print("=" * 80)

    # Parse original XML
    print(f"\n1. Parsing original XML: {input_xml}")
    parser = FCP7XMLParser()
    timeline = parser.parse_file(input_xml)

    print(f"   Timeline: {timeline.name}")
    print(f"   Duration: {timeline.duration:.2f}s")
    print(f"   Tracks: {len(timeline.tracks)}")
    print(f"   Clips: {sum(len(t.clips) for t in timeline.tracks)}")

    # Check canonical block
    canonical_block = timeline.get_canonical_file_block()
    if canonical_block:
        print(f"\n2. Canonical file block extracted:")
        print(f"   file_id: {canonical_block['file_id']}")
        print(f"   name: {canonical_block['name']}")
        print(f"   pathurl: {canonical_block['pathurl']}")
        print(f"   duration_frames: {canonical_block.get('duration_frames', 'N/A')}")
        print(f"   filters: {list(canonical_block.get('filters', {}).keys())}")
    else:
        print(f"\n2. ❌ ERROR: No canonical file block extracted!")
        return False

    # Write back to XML
    print(f"\n3. Writing timeline to: {output_xml}")
    writer = FCP7XMLWriter()
    success = writer.write_timeline(timeline, output_xml)

    if not success:
        print("   [ERROR] Failed to write timeline!")
        return False

    print(f"   [OK] Successfully wrote timeline")

    # Validate DaVinci Resolve structure
    davinci_structure_valid = validate_davinci_structure(output_xml)

    # Verify output structure
    print(f"\n5. Verifying output XML content...")
    with open(output_xml, 'r', encoding='utf-8') as f:
        output_content = f.read()

    # Check for key elements
    checks = [
        (f'<file id="{canonical_block["file_id"]}">', "Full file block in first clipitem"),
        (canonical_block['pathurl'], "Original pathurl preserved"),
        (canonical_block['name'], "Original filename preserved"),
        ('<filter>', "Filters present"),
    ]

    all_passed = True
    for check_str, description in checks:
        if check_str in output_content:
            print(f"   [OK] {description}")
        else:
            print(f"   [FAIL] MISSING: {description}")
            all_passed = False

    # Count file references
    file_ref_count = output_content.count(f'id="{canonical_block["file_id"]}"')
    print(f"\n6. File ID reference count: {file_ref_count}")
    print(f"   (Should be 1 full block + {sum(len(t.clips) for t in timeline.tracks) - 1} references)")

    if all_passed and davinci_structure_valid:
        print(f"\n{'=' * 80}")
        print("[SUCCESS] TEST PASSED - Canonical file block preserved correctly!")
        print(f"{'=' * 80}")
        print(f"\nYou can now import {output_xml} into DaVinci Resolve to verify.")
        return True
    else:
        print(f"\n{'=' * 80}")
        print("[FAILED] TEST FAILED - Some checks did not pass")
        print(f"{'=' * 80}")
        return False

if __name__ == "__main__":
    try:
        success = test_canonical_preservation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
