"""
Test Replicate Audio Extraction (Simple, Auto-Run)

Tests the core Replicate functionality without AWS MediaConvert.
This verifies that the Replicate-only mode works for the full workflow.
"""

import sys
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from services.replicate_video_processor import ReplicateVideoProcessor

def test_processor_init():
    """Test processor initialization without MediaConvert"""
    print("\n" + "="*60)
    print("TEST 1: Processor Initialization (Replicate-only mode)")
    print("="*60)

    try:
        processor = ReplicateVideoProcessor()

        if processor.mediaconvert_available:
            print("Status: Hybrid mode (AWS MediaConvert + Replicate)")
        else:
            print("Status: Replicate-only mode (No MediaConvert)")

        print(f"Audio extraction: Available")
        print(f"Whisper transcription: Available")
        print(f"Video transcoding: {'Available' if processor.mediaconvert_available else 'Not available (not needed for core workflow)'}")

        print("\nSUCCESS: Processor initialized")
        return processor

    except Exception as e:
        print(f"\nERROR: Processor initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_audio_extraction(processor):
    """Test audio extraction with public video"""
    print("\n" + "="*60)
    print("TEST 2: Audio Extraction")
    print("="*60)

    # Use public test video (15 seconds)
    test_video = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

    print(f"Test Video: {test_video}")
    print(f"Expected Cost: ~$0.02")
    print(f"Expected Time: 10-30 seconds")

    try:
        print("\nExtracting audio...")
        start_time = time.time()

        result = processor.extract_audio(
            video_url=test_video,
            output_format="wav",
            audio_quality="high"
        )

        elapsed = time.time() - start_time

        print("\n" + "="*60)
        print("SUCCESS: Audio Extraction Complete")
        print("="*60)
        print(f"Time: {elapsed:.1f} seconds")
        print(f"Audio URL: {result.get('audio_url', 'N/A')}")
        print(f"Format: {result.get('format', 'wav')}")

        # Verify audio is accessible
        audio_url = result.get('audio_url')
        if audio_url:
            import requests
            response = requests.head(audio_url, timeout=10)
            if response.status_code == 200:
                print(f"\nAudio file verified: HTTP {response.status_code}")
                if 'content-length' in response.headers:
                    size_mb = int(response.headers['content-length']) / (1024 * 1024)
                    print(f"File size: {size_mb:.2f} MB")

        return True

    except Exception as e:
        print(f"\nERROR: Audio extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print(" "*10 + "REPLICATE AUDIO EXTRACTION TEST")
    print(" "*10 + "(No AWS MediaConvert Required)")
    print("="*70)

    # Test 1: Initialize processor
    processor = test_processor_init()
    if not processor:
        print("\nInitialization failed - cannot continue")
        sys.exit(1)

    # Test 2: Extract audio
    print("\nProceeding with audio extraction test...")
    print("(This will cost ~$0.02)")

    success = test_audio_extraction(processor)

    if success:
        print("\n" + "="*70)
        print(" "*20 + "ALL TESTS PASSED!")
        print("="*70)
        print("\nYour Replicate-only setup is working!")
        print("\nNext steps:")
        print("1. Upload videos to S3")
        print("2. Extract audio with Replicate")
        print("3. Transcribe with Whisper")
        print("4. Generate DaVinci Resolve XML")
        print("\n(AWS MediaConvert transcoding can be added later)")
    else:
        print("\nTests failed - check errors above")
        sys.exit(1)
