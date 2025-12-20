"""
Test script to diagnose MP4 moov atom issues.

This script:
1. Downloads a FULL video file from S3 via presigned URL
2. Checks if the MP4 file has a valid moov atom
3. Simulates what Replicate does when processing videos

This helps diagnose why Replicate gets "moov atom not found" errors.
"""

import sys
import io
import boto3
import requests
import os
import struct
from config import Config
from botocore.exceptions import ClientError

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def find_moov_atom(file_path):
    """
    Check if MP4 file has moov atom and where it's located.

    MP4 structure:
    - ftyp: File type box (required, usually at start)
    - mdat: Media data (can be large, sometimes at start for streaming)
    - moov: Movie metadata (CRITICAL for playback)

    For streaming/progressive download, moov should be at START.
    If moov is at END, video can't play until fully downloaded.
    """
    print("\n" + "="*60)
    print("STEP 3: Checking MP4 moov atom position")
    print("="*60)

    try:
        file_size = os.path.getsize(file_path)
        print(f"File size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
        print()

        with open(file_path, 'rb') as f:
            # Read first 100KB to find moov position
            header_data = f.read(102400)  # 100KB

            # MP4 files are made of "atoms" (boxes)
            # Each atom has: [4 bytes size][4 bytes type][data]
            atoms_found = []
            pos = 0

            while pos < len(header_data) - 8:
                # Read atom size and type
                atom_size = struct.unpack('>I', header_data[pos:pos+4])[0]
                atom_type = header_data[pos+4:pos+8].decode('ascii', errors='ignore')

                atoms_found.append({
                    'type': atom_type,
                    'position': pos,
                    'size': atom_size
                })

                print(f"Atom: {atom_type:4s} | Position: {pos:8,} | Size: {atom_size:12,} bytes")

                # Check if this is the moov atom
                if atom_type == 'moov':
                    moov_position = pos
                    moov_size = atom_size

                    print()
                    print("✅ moov atom FOUND!")
                    print(f"   Position: {moov_position:,} bytes into file")
                    print(f"   Size: {moov_size:,} bytes")

                    if moov_position < 1024:  # Within first 1KB
                        print("   Location: START of file (GOOD for streaming)")
                        print("   ✅ Replicate should be able to process this file")
                    else:
                        print(f"   Location: {moov_position / 1024:.1f} KB into file")
                        print("   ⚠️  Not at very start, but should still work")

                    return True

                # Move to next atom
                if atom_size == 0 or atom_size > len(header_data):
                    break
                pos += atom_size

            # moov not found in first 100KB - might be at end of file
            print()
            print("⚠️  moov atom NOT found in first 100KB")
            print("   This could mean:")
            print("   1. moov atom is at END of file (bad for streaming)")
            print("   2. File is corrupt or incomplete")
            print("   3. File is not a valid MP4")
            print()

            # Check last 100KB for moov
            print("Checking last 100KB of file...")
            f.seek(max(0, file_size - 102400))
            tail_data = f.read()

            pos = 0
            while pos < len(tail_data) - 8:
                try:
                    atom_size = struct.unpack('>I', tail_data[pos:pos+4])[0]
                    atom_type = tail_data[pos+4:pos+8].decode('ascii', errors='ignore')

                    if atom_type == 'moov':
                        moov_position = file_size - len(tail_data) + pos
                        print()
                        print("✅ moov atom found at END of file")
                        print(f"   Position: {moov_position:,} bytes ({moov_position / file_size * 100:.1f}% into file)")
                        print(f"   Size: {atom_size:,} bytes")
                        print()
                        print("❌ PROBLEM: moov atom is at END, not START")
                        print("   Replicate needs the moov atom at the beginning")
                        print("   to start processing without downloading entire file.")
                        print()
                        print("   Solution: Re-encode video with 'faststart' flag:")
                        print("   ffmpeg -i input.mp4 -movflags +faststart output.mp4")
                        print()
                        return True

                    if atom_size == 0 or atom_size > len(tail_data):
                        break
                    pos += atom_size
                except:
                    break

            print()
            print("❌ moov atom NOT FOUND")
            print("   File may be corrupt or not a valid MP4")
            return False

    except Exception as e:
        print(f"❌ Error checking moov atom: {e}")
        return False


def test_full_download():
    """Download and verify a full video file from S3."""
    print("\n" + "="*60)
    print("FULL VIDEO DOWNLOAD TEST")
    print("="*60)
    print("This test downloads a complete video to check for issues")
    print()

    # Step 1: List videos
    print("="*60)
    print("STEP 1: Finding test video on S3")
    print("="*60)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
        )

        response = s3_client.list_objects_v2(
            Bucket=Config.S3_VIDEO_BUCKET,
            Prefix='uploads/',
            MaxKeys=10
        )

        if 'Contents' not in response:
            print("❌ No videos found in S3")
            return

        # Find a moderately-sized video for testing (prefer 5-10 MB)
        test_video = None
        for obj in response['Contents']:
            size_mb = obj['Size'] / (1024 * 1024)
            if 4 < size_mb < 15:  # Between 4-15 MB
                test_video = obj
                break

        if not test_video:
            # Just use first video
            test_video = response['Contents'][0]
            size_mb = test_video['Size'] / (1024 * 1024)

        s3_key = test_video['Key']
        file_size = test_video['Size']
        print(f"✅ Selected test video:")
        print(f"   S3 Key: {s3_key}")
        print(f"   Size: {size_mb:.2f} MB ({file_size:,} bytes)")
        print()

        # Step 2: Generate presigned URL and download
        print("="*60)
        print("STEP 2: Downloading full video via presigned URL")
        print("="*60)

        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': Config.S3_VIDEO_BUCKET, 'Key': s3_key},
            ExpiresIn=86400
        )

        print("Presigned URL generated")
        print(f"Downloading {size_mb:.2f} MB...")
        print("(This may take a few seconds)")
        print()

        # Download to temp file
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_path = temp_file.name

        response = requests.get(presigned_url, stream=True, timeout=300)
        response.raise_for_status()

        downloaded_bytes = 0
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded_bytes += len(chunk)

        print(f"✅ Download complete!")
        print(f"   Downloaded: {downloaded_bytes:,} bytes ({downloaded_bytes / (1024*1024):.2f} MB)")
        print(f"   Expected: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
        print()

        if downloaded_bytes != file_size:
            print("⚠️  WARNING: Downloaded size doesn't match S3 size!")
            print("   File may be incomplete or corrupted")
        else:
            print("✅ File size matches - download successful")

        # Step 3: Check moov atom
        has_moov = find_moov_atom(temp_path)

        # Cleanup
        try:
            os.unlink(temp_path)
        except:
            pass

        # Final summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        if downloaded_bytes == file_size and has_moov:
            print("✅ Video download: SUCCESS")
            print("✅ File integrity: OK")
            print("✅ moov atom: FOUND")
            print()
            print("Conclusion:")
            print("The video file itself is fine. Replicate should be able")
            print("to process it. The 'moov atom not found' error might be:")
            print("1. Temporary Replicate API issue")
            print("2. Timeout during Replicate's download")
            print("3. Different video file causing the error")
        elif downloaded_bytes == file_size and not has_moov:
            print("✅ Video download: SUCCESS")
            print("✅ File integrity: OK")
            print("❌ moov atom: NOT FOUND OR AT END")
            print()
            print("PROBLEM IDENTIFIED:")
            print("The video file needs to be re-encoded with 'faststart' flag")
            print("to move moov atom to the beginning of the file.")
            print()
            print("Fix: Re-upload videos with proper encoding, or")
            print("     Add faststart processing in upload pipeline")
        else:
            print("❌ Video download: FAILED or INCOMPLETE")
            print("❌ File integrity: CORRUPTED")
            print()
            print("PROBLEM IDENTIFIED:")
            print("The video file is not downloading completely via presigned URL")
            print("This could explain the 'moov atom not found' error")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_full_download()
